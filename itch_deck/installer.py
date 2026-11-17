"""Installs (Linux builds; Windows builds run through umu + GE-Proton, see proton.py). One download at a time from a queue that survives a restart:
uploads -> pick build -> free-space check -> resumable download -> extract -> find the
executable -> install.json. The worker thread only writes plain dict fields; the UI reads them.

Game fields it sets (also kept in lib.live so a library sync can't drop them):
state: None | "queued" | "downloading" | "installed" | "failed"
phase: "download" | "extract", progress 0..1, speed_mbs, eta_s, fail_reason, size_mb."""
import datetime as dt
import json
import logging
import os
import re
import shutil
import stat
import tarfile
import threading
import time
import zipfile
from pathlib import Path

from . import config, net, paths, proton, words
from .stores.itch import pick_build, split_parts

log = logging.getLogger("scritch")
SPACE_FACTOR = 2.5            # download + extracted copy + slack
SKIP_EXE = ("unins", "crashhandler", "crash_handler", "crashpad", "vc_redist", "dxsetup",
            "unitycrash", "chrome-sandbox", "chrome_sandbox", "notification_helper")
SKIP_WIN = ("setup", "redist", "dxweb", "dotnet", "oalinst", "physx", "vcrun", "directx",
            "cefsharp", "createdump", "dump_syms")


class InstallError(words.Coded):
    """A reason to show the user on the game page ("Couldn't install" box)."""


def _gb(n):
    return f"{n / 1e9:.1f} GB"


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.tmp_for(path)          # install + update-check threads both write the index
    tmp.write_text(json.dumps(dict(data) if isinstance(data, dict) else data, indent=1))
    tmp.replace(path)


def slug_of(g):
    """'https://dev.itch.io/quiet-quarry' -> 'quiet-quarry' (title as fallback)."""
    s = (g.get("url") or "").rstrip("/").rsplit("/", 1)[-1] if g.get("url") else ""
    s = re.sub(r"[^a-z0-9]+", "-", (s or g.get("title") or "").lower()).strip("-")
    return s or f"game-{g['id']}"


# --- extract ------------------------------------------------------------------------------
def _inside(root, target):
    root, target = os.path.realpath(root), os.path.realpath(target)
    return target == root or target.startswith(root + os.sep)


def extract(archive, dest, allow_exe=False):
    """zip (keeps exec bits), tar.*, 7z (if py7zr is bundled), or a single runnable file
    (a bare .exe only for Windows builds: a game or an installer, which _install runs silently)."""
    archive, dest = Path(archive), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                target = dest / info.filename
                if not _inside(dest, target):
                    raise InstallError("The download has unsafe file paths.")
                mode = info.external_attr >> 16
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if stat.S_ISLNK(mode):
                    link = z.read(info).decode("utf-8", "replace")
                    if _inside(dest, target.parent / link):
                        target.unlink(missing_ok=True)
                        os.symlink(link, target)
                    continue
                with z.open(info) as src, open(target, "wb") as out:
                    while True:                 # small chunks + yield: the UI stays smooth
                        chunk = src.read(256 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                        time.sleep(0)
                if mode & 0o111:
                    os.chmod(target, (mode & 0o777) | 0o600)
        return
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            try:
                tf.extractall(dest, filter="data")
            except TypeError:                       # Python without extraction filters
                for m in tf.getmembers():
                    if not _inside(dest, dest / m.name) or m.issym() and \
                            not _inside(dest, (dest / m.name).parent / m.linkname):
                        raise InstallError("The download has unsafe file paths.")
                tf.extractall(dest)
            except tarfile.FilterError:
                raise InstallError("The download has unsafe file paths.") from None
        return
    if name.endswith(".7z"):
        try:
            import py7zr
        except ImportError:
            raise InstallError(".7z downloads aren't supported yet.") from None
        with py7zr.SevenZipFile(archive) as z:
            z.extractall(dest)
        return
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext == "exe" and allow_exe:
        pass                                        # a bare game .exe or a setup.exe (M5)
    elif ext in ("rar", "dmg", "apk", "exe", "msi", "pkg", "deb", "rpm", "jar"):
        raise InstallError(f".{ext} downloads aren't supported.")
    # a bare executable (AppImage, .x86_64, .sh, …): copy it in as-is
    out = dest / re.sub(r"^\d+-\d+-", "", archive.name)   # drop our "<game>-<upload>-" prefix
    shutil.copyfile(archive, out)
    os.chmod(out, 0o755)


def _size(path):
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _place(src, dst):
    """Hard link (same drive: instant, no extra space), else copy. The download stays until the
    install succeeds, so Retry doesn't download again."""
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


# --- find the executable --------------------------------------------------------------------
def _elf(path):
    """(is_elf, is_64bit_x86) from the ELF header, without loading anything."""
    try:
        with open(path, "rb") as f:
            h = f.read(20)
    except OSError:
        return False, False
    if h[:4] != b"\x7fELF" or len(h) < 20:
        return False, False
    machine = int.from_bytes(h[18:20], "little")
    return True, machine == 0x3E


def is_appimage(path):
    """ELF with the AppImage magic ("AI" + type) at offset 8."""
    try:
        with open(path, "rb") as f:
            h = f.read(11)
    except OSError:
        return False
    return h[:4] == b"\x7fELF" and h[8:11] in (b"AI\x01", b"AI\x02")


def unpack_appimage(root, exe, timeout=600):
    """AppImages need libfuse2 to mount themselves, which SteamOS doesn't ship (they exit 127).
    Unpack it once (--appimage-extract needs no FUSE) and run its AppRun. Returns the new exe
    (relative to root), or the old one if unpacking fails (the game env then has
    APPIMAGE_EXTRACT_AND_RUN=1 as a fallback)."""
    import subprocess
    from .runner import child_env
    src = Path(root) / exe
    out = src.parent / "squashfs-root"
    shutil.rmtree(out, ignore_errors=True)
    try:
        r = subprocess.run([str(src), "--appimage-extract"], cwd=src.parent, env=child_env(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
        ok = r.returncode == 0 and (out / "AppRun").exists()
        err = r.stderr[-300:]
    except (OSError, subprocess.TimeoutExpired) as e:
        ok, err = False, e
    if not ok:
        log.warning("appimage %s: unpack failed (%s), keeping it as is", exe, err)
        shutil.rmtree(out, ignore_errors=True)
        return exe
    src.unlink()
    log.info("appimage %s: unpacked", exe)
    return str((out / "AppRun").relative_to(root))


def _script(path):
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def find_exe(root, g, platform="linux"):
    """Best runnable file under root, plus the other candidates (relative paths). Also sets the
    exec bit on every ELF and script, since archives often lose it (pitfall #7)."""
    root = Path(root)
    title = re.sub(r"[^a-z0-9]", "", (g.get("title") or "").lower())
    slug = re.sub(r"[^a-z0-9]", "", slug_of(g))
    if platform == "windows":
        return _find_win_exe(root, title, slug)
    found = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            p = Path(dirpath) / fn
            low = fn.lower()
            if p.is_symlink() or ".so" in low or low.endswith((".dll", ".pck", ".pak", ".dat")):
                continue
            is_elf, x64 = _elf(p)
            is_sh = not is_elf and (low.endswith(".sh") or low.endswith(".appimage")) and _script(p)
            if not (is_elf or is_sh):
                continue
            try:
                os.chmod(p, p.stat().st_mode | 0o755)
            except OSError:
                pass
            if any(k in low for k in SKIP_EXE):
                continue
            stem = re.sub(r"[^a-z0-9]", "", low.rsplit(".", 1)[0] if "." in low else low)
            named = len(stem) >= 3 and any(n and (stem in n or n in stem) for n in (title, slug))
            depth = len(p.relative_to(root).parts)
            ok_arch = x64 or is_sh
            launcher = is_sh and stem in ("start", "run", "launch", "play")
            score = (ok_arch, named or launcher, -depth, is_elf, p.stat().st_size)
            found.append((score, str(p.relative_to(root))))
    found.sort(reverse=True)
    names = [f for _, f in found]
    return (names[0] if names else None), names[1:]


def find_installer(root):
    """A setup.exe in the top two levels (Inno / NSIS / InstallShield signature): installers
    named like the game first, then ones called setup/install, then the biggest."""
    found = []
    for dirpath, _dirs, files in os.walk(root):
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth > 1:
            continue
        for fn in files:
            p = Path(dirpath) / fn
            if fn.lower().endswith(".exe") and proton.is_installer(p):
                named = any(k in fn.lower() for k in ("setup", "install"))
                found.append(((named, -depth, p.stat().st_size), p))
    found.sort(key=lambda x: x[0], reverse=True)
    return found[0][1] if found else None


def _find_win_exe(root, title, slug):
    """Windows build: the .exe named like the game, shallowest, biggest. Helpers skipped."""
    found = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            low = fn.lower()
            if not low.endswith(".exe") or any(k in low for k in SKIP_EXE + SKIP_WIN):
                continue
            p = Path(dirpath) / fn
            stem = re.sub(r"[^a-z0-9]", "", low[:-4])
            named = len(stem) >= 3 and any(n and (stem in n or n in stem) for n in (title, slug))
            depth = len(p.relative_to(root).parts)
            found.append(((named, -depth, p.stat().st_size), str(p.relative_to(root))))
    found.sort(reverse=True)
    names = [f for _, f in found]
    return (names[0] if names else None), names[1:]


UPDATE_EVERY_S = 6 * 3600


def update_for(info, builds):
    """("update", build) when itch has a newer build than the installed one: the same upload
    with a newer date or a new butler build id, or (upload gone) the build picked in its place.
    ("baseline", build) for installs made before we recorded dates; (None, build|None) else."""
    cur = next((u for u in builds if u["id"] == info.get("upload_id")), None)
    if cur is None:
        repl, _ = pick_build(builds, info.get("platform") or "linux")
        return ("update", repl) if repl else (None, None)
    if "upload_updated" not in info:
        return "baseline", cur
    newer = bool(cur.get("updated")) and bool(info["upload_updated"]) and \
        cur["updated"] > info["upload_updated"]
    rebuilt = bool(cur.get("build_id")) and bool(info.get("build_id")) and \
        cur["build_id"] != info["build_id"]
    return ("update", cur) if newer or rebuilt else (None, cur)


# --- installer -----------------------------------------------------------------------------

MOVING = "_moving"           # <root>/_moving: a move's copy until it's checked (then renamed)


class MoveCancelled(Exception):
    pass


def safe_to_delete(path, roots):
    """True only for a folder strictly INSIDE one of the games folders (roots). Never a root itself,
    the home folder, or something outside them: uninstall and move delete folders named in
    install.json, and a damaged record must not be able to wipe the wrong place (audit 17 Nov)."""
    try:
        p = Path(path).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    if len(p.parts) < 3 or p == paths.HOME.resolve():
        return False
    for r in roots:
        try:
            rr = Path(r).resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if p != rr and rr in p.parents:
            return True
    return False


def _tree_size(p):
    total = 0
    for dirpath, _, files in os.walk(p):
        for f in files:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total


def _tree_count(p):
    return sum(len(files) + len(dirs) for _, dirs, files in os.walk(p))


def _copy_tree(src, dst, tick):
    """Copy src to dst (links as links, modes and times kept), calling tick(bytes) as it goes."""
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for dirpath, dirs, files in os.walk(src):
        rel = Path(dirpath).relative_to(src)
        out = dst / rel
        for d in list(dirs):
            sp = Path(dirpath) / d
            if sp.is_symlink():
                os.symlink(os.readlink(sp), out / d)
                dirs.remove(d)                   # os.walk doesn't follow it anyway
            else:
                (out / d).mkdir(exist_ok=True)
        for f in files:
            sp, dp = Path(dirpath) / f, out / f
            if sp.is_symlink():
                os.symlink(os.readlink(sp), dp)
                continue
            with open(sp, "rb") as a, open(dp, "wb") as b:
                while chunk := a.read(4 << 20):
                    b.write(chunk)
                    tick(len(chunk))
            shutil.copystat(sp, dp, follow_symlinks=False)
        try:
            shutil.copystat(dirpath, out)
        except OSError:
            pass


def fix_registry(prefix, old_root, new_root):
    """A setup program may write its install folder into the prefix's registry (Z:\\run\\…).
    After a move, point those at the new folder: the .reg files are text, so replace the old
    games folder with the new one (Windows form, escaped as in .reg files, and the plain form)."""
    def win(p):
        return "Z:" + str(p).replace("/", "\\")
    pairs = []
    for drive in ("Z:", "z:"):
        o, n = drive + win(old_root)[2:] + "\\", drive + win(new_root)[2:] + "\\"   # whole names
        pairs += [(o.replace("\\", "\\\\"), n.replace("\\", "\\\\")), (o, n)]
    pairs.append((str(old_root) + "/", str(new_root) + "/"))
    n_fixed = 0
    for reg in ("system.reg", "user.reg", "userdef.reg"):
        for f in (Path(prefix) / reg, Path(prefix) / "pfx" / reg):
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8", errors="surrogateescape")
            new = text
            for a, b in pairs:
                new = new.replace(a, b)
            if new != text:
                n_fixed += 1
                tmp = f.with_name(f.name + ".tmp")
                tmp.write_text(new, encoding="utf-8", errors="surrogateescape")
                os.replace(tmp, f)
    if n_fixed:
        log.info("move: registry paths updated in %d file(s) of %s", n_fixed, prefix)
    return n_fixed

class Installer:
    def __init__(self, lib, root_fn, cfg=None):
        self.lib, self.root_fn, self.cfg = lib, root_fn, cfg if cfg is not None else {}
        self.index = _read_json(paths.INSTALLS, {})        # gid -> {dir, exe, upload_id, ...}
        self.choices = _read_json(paths.BUILDS, {})        # gid -> upload id (Change build)
        self.queue = [gid for gid in _read_json(paths.QUEUE, []) if not self._done(gid)]
        self.current = None
        self.events = []          # ("done"|"failed", gid, text) for the UI thread to toast
        self._cancel = set()
        self._thread = None
        self._lock = threading.Lock()
        self.updating = set()     # gids queued as updates (same upload id may be reinstalled)
        self.moving = None        # gid being moved to the other drive (Move to SD card / internal)
        lib.installs, lib.live = self.index, {}
        lib.on_epic_sync = self.check_epic_updates
        lib.on_gog_sync = self.check_gog_updates
        lib.apply_installs()

    # --- queue (called from the UI thread) ---
    def resume(self):
        """Downloads that were running or queued when the app last quit."""
        if self.queue:
            log.info("install queue resumed: %s", self.queue)
            for gid in self.queue:
                self._upd(gid, state="queued", phase=None)
            self._start()

    def _done(self, gid):
        """Installed, and with the build the user chose (a Change build reinstall isn't)."""
        info = self.index.get(gid)
        return bool(info) and gid not in self.updating and \
            self.choices.get(gid, info["upload_id"]) == info["upload_id"]

    def enqueue(self, g, upload_id=None):
        """upload_id: a build picked in Change build (remembered for reinstalls too)."""
        gid = g["id"]
        with self._lock:
            if gid in self.queue:
                return False
            if upload_id is not None:
                self.choices[gid] = upload_id
                _write_json(paths.BUILDS, self.choices)
            if self._done(gid):
                return False
            self.queue.append(gid)
            self._save_queue()
        self._upd(gid, state="queued", phase=None, fail_reason=None, progress=0)
        log.info("install %s (%s): queued", gid, g.get("title"))
        self._start()
        return True

    def cancel(self, gid):
        with self._lock:
            if gid == self.current:
                self._cancel.add(gid)              # the worker stops at the next chunk
                return
            if gid in self.queue:
                self.queue.remove(gid)
                self._save_queue()
        self._revert_choice(gid)
        self._upd(gid, state="installed" if gid in self.index else None, phase=None)

    def busy(self, gid):
        return gid in self.queue

    def _save_queue(self):
        _write_json(paths.QUEUE, list(self.queue))

    def _start(self):
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True, name="install")
            self._thread.start()

    def _upd(self, gid, **kw):
        """Set install fields on the game (and in lib.live, which a sync re-applies)."""
        if kw.get("state") in (None, "installed"):
            self.lib.live.pop(gid, None)
        else:
            self.lib.live.setdefault(gid, {}).update(kw)
        g = self.lib.by_id(gid)
        if g is not None:
            g.update(kw)

    # --- worker ---
    def _run(self):
        while True:
            with self._lock:
                if not self.queue:
                    self.current = None
                    return
                gid = self.current = self.queue[0]
            g = self.lib.by_id(gid)
            title = g["title"] if g else gid
            try:
                if g is None:
                    raise InstallError("This game isn't in your library any more.")
                self._install(dict(g))
                self.events.append(("done", gid, f"{title} is updated." if gid in self.updating
                                    else f"{title} is ready to play."))
            except net.Cancelled:
                log.info("install %s: cancelled", gid)
                self._cleanup_download(gid)
                self._revert_choice(gid)
                self._upd(gid, state="installed" if gid in self.index else None, phase=None,
                          progress=0)
            except (net.Offline, net.NotFound) as e:
                log.info("install %s: network (%s)", gid, e)
                self._fail(gid, title, "Lost the connection to itch.io. Retry when you're online "
                                       "(the download continues where it stopped).")
            except net.AuthError:
                self._fail(gid, title, "itch.io rejected the API key. Sign in to itch again in Settings.")
            except (InstallError, proton.ProtonError) as e:
                log.info("install %s: %s", gid, e)
                self._fail(gid, title, str(e), e.code)
            except Exception as e:  # noqa: BLE001
                log.exception("install %s failed", gid)
                self._fail(gid, title, f"Something went wrong ({type(e).__name__}: {e}).", "I01")
            finally:
                with self._lock:
                    if self.queue and self.queue[0] == gid:
                        self.queue.pop(0)
                    self._cancel.discard(gid)
                    self.updating.discard(gid)
                    self._save_queue()

    def _fail(self, gid, title, reason, code=None):
        """The full reason goes to the log; the player sees a few plain words (words.short), or
        the error code when there's nothing they can act on."""
        log.info("install %s failed: %s", gid, reason)
        hint = words.short(reason)
        if not hint:
            code = code or "I01"
            words.log_code(code, f"install {gid} ({title}): {reason}")
            hint = f"Code {code}"
        if gid in self.index:                 # an update / Change build: the old build stays
            self._revert_choice(gid)
            self._upd(gid, state="installed", phase=None, fail_reason=None)
            what = f"Couldn't update {title}." if gid in self.updating else "Couldn't change the build."
            self.events.append(("error", gid, f"{what} {hint}." if hint else what))
            return
        self._upd(gid, state="failed", phase=None, fail_reason=hint)
        self.events.append(("failed", gid, f"Couldn't install {title}."))

    # --- updates (newer build of an installed game on itch) ---
    def check_updates(self, gids=None, force=False):
        """Ask itch for the builds of installed games and mark the ones with a newer build
        (install.json "update"; Library._apply_install copies it to the game). Runs in a
        background thread; quiet when offline. Each game at most every UPDATE_EVERY_S unless
        force (the game page asks once per open)."""
        store = self.lib.store
        if not store:
            return 0
        now, found = time.time(), 0
        for gid in list(gids if gids is not None else self.index):
            info, g = self.index.get(gid), self.lib.by_id(gid)
            if not info or g is None or gid == self.current or gid in self.queue:
                continue
            if (info.get("store") or "itch") != "itch":   # Epic: check_epic_updates; GOG: step 3
                continue
            if not force and now - info.get("checked", 0) < UPDATE_EVERY_S:
                continue
            try:
                builds = store.list_builds(g)
            except (net.Offline, net.AuthError):
                log.info("updates: offline, stopped")
                break
            except Exception as e:  # noqa: BLE001
                log.info("updates %s: %s", gid, e)
                continue
            kind, b = update_for(info, builds)
            info["checked"] = now
            if kind == "baseline":            # installed before v0.7.3: remember what we have
                info["upload_updated"], info["build_id"] = b.get("updated") or "", b.get("build_id")
            if kind == "update":
                info["update"] = {"upload_id": b["id"], "filename": b["filename"],
                                  "updated": b.get("updated") or ""}
                log.info("updates %s: newer build %s (%s)", gid, b["filename"], b.get("updated"))
                found += 1
            else:
                info.pop("update", None)
            self._save_info(gid, info)
            g["update"] = info.get("update")
        return found

    def check_epic_updates(self):
        """After each Epic sync: an installed Epic game whose build differs from Epic's newest
        gets the Update badge/button (Update = legendary downloads only what changed)."""
        store = self.lib.epic
        if not store:
            return 0
        latest, have, found = getattr(store, "latest", {}), store.installed(), 0
        for gid, info in list(self.index.items()):
            if info.get("store") != "epic" or gid == self.current or gid in self.queue:
                continue
            app = info.get("app_name")
            cur, new = (have.get(app) or {}).get("version"), latest.get(app)
            if cur and new and cur != new:
                info["update"] = {"upload_id": app, "filename": app, "updated": ""}
                log.info("updates %s: epic build %s -> %s", gid, cur, new)
                found += 1
            else:
                info.pop("update", None)
            self._save_info(gid, info)
            g = self.lib.by_id(gid)
            if g is not None:
                g["update"] = info.get("update")
        return found

    def _save_info(self, gid, info):
        try:
            _write_json(Path(info["dir"]) / "install.json", info)
        except OSError:
            pass                               # SD card out: the index still has it
        _write_json(paths.INSTALLS, self.index)

    def update(self, g):
        """Options → Update: reinstall with the newer build; the old one stays if it fails."""
        gid = g["id"]
        info = self.index.get(gid) or {}
        up = info.get("update")
        if not up:
            return False
        self.updating.add(gid)
        if up["upload_id"] != info.get("upload_id"):
            self.choices[gid] = up["upload_id"]
            _write_json(paths.BUILDS, self.choices)
        if not self.enqueue(g):
            self.updating.discard(gid)
            return False
        return True

    def _revert_choice(self, gid):
        info = self.index.get(gid)
        if info and self.choices.get(gid) not in (None, info["upload_id"]):
            self.choices[gid] = info["upload_id"]
            _write_json(paths.BUILDS, self.choices)

    def _choose(self, gid, builds):
        """(build, platform): the Change build choice if it still exists, else Linux, else
        Windows (pitfall #3 order)."""
        want = self.choices.get(gid)
        if want is not None:
            b = next((u for u in builds if u["id"] == want), None)
            if b and (b["linux"] or b["windows"]):
                return b, "linux" if b["linux"] else "windows"
            log.info("install %s: chosen upload %s is gone, picking again", gid, want)
        for plat in ("linux", "windows"):
            b, others = pick_build(builds, plat)
            if b:
                if others:
                    log.info("install %s: picked %s over %s", gid, b["filename"],
                             [o["filename"] for o in others])
                return b, plat
        return None, None

    def _cleanup_download(self, gid):
        dl = self._dl_dir()
        for f in dl.glob(f"{gid}-*") if dl.exists() else []:
            f.unlink(missing_ok=True)

    def _dl_dir(self):
        return Path(self.root_fn()) / "_downloads"

    def _install(self, g):
        if g.get("store") == "epic":
            return self._install_epic(g)
        if g.get("store") == "gog":
            return self._install_gog(g)
        gid, store = g["id"], self.lib.store
        if not store:
            raise InstallError("Not connected to itch.io yet.", "I03")
        t0 = time.time()
        builds = store.list_builds(g)
        build, platform = self._choose(gid, builds)
        if not build:
            raise InstallError("No Linux or Windows download found for this game.", "I02")
        log.info("install %s: %s build %s", gid, platform, build["filename"])
        if platform == "windows" and not proton.proton_dir(self.cfg):
            self._upd(gid, state="downloading", phase="ge", progress=0, speed_mbs=0, eta_s=0)
            proton.fetch_ge(cancel=lambda: gid in self._cancel, on_bytes=self._meter(gid))
        parts = split_parts(build, builds) if platform == "windows" else []
        if parts:
            log.info("install %s: installer comes in %d more pieces %s", gid, len(parts),
                     [p["filename"] for p in parts])
        size = build["size"] + sum(p["size"] for p in parts)
        self._upd(gid, size_mb=size // 1_000_000)

        root = Path(self.root_fn())
        if config.card_missing(root):
            raise InstallError("SD card missing. Insert it, or choose another install location "
                               "in Settings.")
        try:
            root.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(root).free
        except OSError as e:
            log.warning("install %s: can't write to %s: %s", gid, root, e)
            raise InstallError(f"Can't write to the {config.drive_name(root)}. Check it isn't full "
                               "or read-only.") from e
        dls = [(b, self._dl_dir() / f"{gid}-{b['id']}-{re.sub(r'[^A-Za-z0-9._-]', '_', b['filename'])}")
               for b in [build, *parts]]
        dl = dls[0][1]
        have = sum(_size(f) or _size(f.with_name(f.name + ".part")) for _b, f in dls)
        if size and free + have < size * SPACE_FACTOR:
            raise InstallError(f"Not enough space on the {config.drive_name(root)}: needs about "
                               f"{_gb(size * SPACE_FACTOR)}, {_gb(free)} free.")
        dl.parent.mkdir(parents=True, exist_ok=True)
        for old in dl.parent.glob(f"{gid}-*"):          # an older build's leftovers
            if not any(old.name.startswith(f.name) for _b, f in dls):
                old.unlink(missing_ok=True)

        meter, done = self._meter(gid), 0               # one bar for all pieces
        for b, f in dls:
            if not f.exists():
                self._upd(gid, state="downloading", phase="download", progress=done / size if size else 0,
                          speed_mbs=0, eta_s=0)
                part = f.with_name(f.name + ".part")
                at = part.stat().st_size if part.exists() else 0
                log.info("install %s: download %s (%d MB)%s", gid, b["filename"], b["size"] // 1_000_000,
                         f", resuming at {at // 1_000_000} MB" if at else "")
                net.download(store.download_url(g, b), f, key=getattr(store, "key", None),
                             resume=True, cancel=lambda: gid in self._cancel,
                             on_bytes=lambda d, t, off=done: meter(off + d, max(size, off + t)))
            done += f.stat().st_size
        if platform == "windows" and not proton.umu_path():
            self._upd(gid, state="downloading", phase="umu", progress=1)
            proton.fetch_umu(cancel=lambda: gid in self._cancel)
        self._upd(gid, state="downloading", phase="extract", progress=1)
        free = shutil.disk_usage(root).free             # space may have gone during the download
        if size and free < size * (SPACE_FACTOR - 1):
            raise InstallError(f"Not enough space on the {config.drive_name(root)} to unpack: needs "
                               f"about {_gb(size * (SPACE_FACTOR - 1))}, {_gb(free)} free. The "
                               "download is kept, so Retry continues from here.")

        dest = self._game_dir(root, g)
        tmp = dest / "files.new"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            extract(dl, tmp, allow_exe=platform == "windows")
            exe, alts = find_exe(tmp, g, platform)
            setup = None
            if platform == "windows":
                if exe and proton.is_installer(tmp / exe):
                    setup = tmp / exe
                elif not exe:
                    setup = find_installer(tmp)
            if setup:
                for _b, f in dls[1:]:                   # the pieces sit next to setup.exe
                    _place(f, setup.parent / re.sub(r"^\d+-\d+-", "", f.name))
                kind = self._silent_install(gid, g, setup, tmp, root, dest)
                exe, alts = find_exe(tmp, g, platform)
                if not exe:
                    raise InstallError("The installer finished, but no program to run was found.")
            if not exe:
                raise InstallError("No program to run was found in the download.")
            if platform != "windows" and is_appimage(tmp / exe):
                exe, alts = unpack_appimage(tmp, exe), []
        except (InstallError, proton.ProtonError, net.Cancelled):
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.rmtree(dest / "files.inst", ignore_errors=True)
            raise
        except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError) as e:
            shutil.rmtree(tmp, ignore_errors=True)
            dl.unlink(missing_ok=True)                  # corrupt: download again next time
            log.warning("install %s: extract failed: %s", gid, e)
            raise InstallError("The download couldn't be unpacked.") from None
        files = dest / "files"
        shutil.rmtree(files, ignore_errors=True)
        tmp.replace(files)
        used = sum(f.stat().st_size for f in files.rglob("*") if f.is_file() and not f.is_symlink())
        info = {"game_id": gid, "title": g.get("title"), "upload_id": build["id"],
                "upload_updated": build.get("updated") or "", "build_id": build.get("build_id"),
                "filename": build["filename"], "platform": platform, "exe": exe, "alternatives": alts[:10],
                "size": used, "date": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "dir": str(dest)}
        if setup:
            info["installer"] = kind
        if platform == "windows":                      # saves live here; kept on uninstall
            info["prefix"] = str(proton.prefix_dir(root, dest.name))
        _write_json(dest / "install.json", info)
        self.index[gid] = info
        _write_json(paths.INSTALLS, self.index)
        for _b, f in dls:
            f.unlink(missing_ok=True)
        log.info("install %s: done in %.0fs -> %s (exe %s; %d other candidates)", gid,
                 time.time() - t0, dest, exe, len(alts))
        self._upd(gid, state="installed", phase=None, progress=0, fail_reason=None,
                  size_mb=used // 1_000_000, update=None)

    def _install_epic(self, g):
        """Epic game through legendary: GE-Proton + umu first (like an itch Windows build), then
        `legendary install` straight into <root>/<game>/files (it resumes an interrupted one),
        one progress bar from legendary's own progress lines."""
        from .stores.epic import EpicError
        gid, store = g["id"], self.lib.epic
        if not store or not store.connected():
            raise InstallError("Connect Epic Games in Settings first.")
        t0 = time.time()
        if not proton.proton_dir(self.cfg):
            self._upd(gid, state="downloading", phase="ge", progress=0, speed_mbs=0, eta_s=0)
            proton.fetch_ge(cancel=lambda: gid in self._cancel, on_bytes=self._meter(gid))
        if not proton.umu_path():
            self._upd(gid, state="downloading", phase="umu", progress=1)
            proton.fetch_umu(cancel=lambda: gid in self._cancel)
        old = self.index.get(gid)                  # Update: legendary patches where it is
        root = Path(old["dir"]).parent if old else Path(self.root_fn())
        if config.card_missing(root):
            raise InstallError("SD card missing. Insert it, or choose another install location "
                               "in Settings.")
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.warning("install %s: can't write to %s: %s", gid, root, e)
            raise InstallError(f"Can't write to the {config.drive_name(root)}.") from e
        dest = Path(old["dir"]) if old else self._game_dir(root, g)
        files = dest / "files"
        files.mkdir(parents=True, exist_ok=True)
        logs = paths.LOGS / "games"
        logs.mkdir(parents=True, exist_ok=True)
        self._upd(gid, state="downloading", phase="queued", progress=0, speed_mbs=0, eta_s=0)
        log.info("install %s: epic %s -> %s", gid, g.get("app_name"), files)

        def prog(frac, mbs, eta):                 # first line: "Starting…" -> "Downloading"
            self._upd(gid, phase="download", progress=min(frac, 0.999), speed_mbs=mbs, eta_s=eta)
        try:
            exe = store.install(g["app_name"], files, on_progress=prog,
                                on_size=lambda mb: self._upd(gid, size_mb=mb),
                                cancel=lambda: gid in self._cancel,
                                log_file=logs / f"{dest.name}-install.log")
        except EpicError as e:
            raise InstallError(f"Couldn't install: {e}.", "I04") from None
        used = sum(f.stat().st_size for f in files.rglob("*") if f.is_file() and not f.is_symlink())
        info = {"game_id": gid, "title": g.get("title"), "store": "epic",
                "app_name": g["app_name"], "upload_id": g["app_name"], "platform": "windows",
                "filename": g["app_name"], "exe": exe, "alternatives": [], "size": used,
                "date": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "dir": str(dest), "prefix": str(proton.prefix_dir(root, dest.name))}
        _write_json(dest / "install.json", info)
        self.index[gid] = info
        _write_json(paths.INSTALLS, self.index)
        log.info("install %s: done in %.0fs -> %s (exe %s)", gid, time.time() - t0, dest, exe)
        self._upd(gid, state="installed", phase=None, progress=0, fail_reason=None,
                  size_mb=used // 1_000_000, update=None)

    def _install_gog(self, g):
        """GOG game through the vendored gogdl: the Linux build when GOG has one (GOG's own
        installer, unpacked by gogdl; start.sh starts it), else Windows through GE-Proton + umu.
        Change build (v0.9.5) picks "linux" / "windows" (self.choices). gogdl downloads into
        <root>/<game>/files and resumes; one progress bar from its progress lines. An update
        (same platform) patches files in place; a platform change installs into files.new and
        swaps only when it worked (the old build stays if it fails). Windows builds also get
        GOG's shared parts + a first-run setup list (run on the first Play, stores/gog)."""
        from .stores import gog as gog_mod
        from .stores.gog import NO_PLAY, GogError
        gid, store = g["id"], self.lib.gog
        if not store or not store.connected():
            raise InstallError("Sign in to GOG in Settings first.")
        chosen = self.choices.get(gid)
        plats = [chosen] if chosen in ("linux", "windows") else store.platforms_for(g)
        if not plats:
            raise InstallError("GOG has no Linux or Windows build of this game.", "I02")
        t0 = time.time()
        old = self.index.get(gid)
        root = Path(old["dir"]).parent if old else Path(self.root_fn())
        if config.card_missing(root):
            raise InstallError("SD card missing. Insert it, or choose another install location "
                               "in Settings.")
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.warning("install %s: can't write to %s: %s", gid, root, e)
            raise InstallError(f"Can't write to the {config.drive_name(root)}.") from e
        dest = Path(old["dir"]) if old else self._game_dir(root, g)
        logs = paths.LOGS / "games"
        logs.mkdir(parents=True, exist_ok=True)
        log_file = logs / f"{dest.name}-install.log"
        self._upd(gid, state="downloading", phase="queued", progress=0, speed_mbs=0, eta_s=0)
        last = None
        for n, plat in enumerate(plats):
            try:
                about = store.info(g["app_name"], plat)
            except GogError as e:
                raise InstallError(f"Couldn't install: {e}.", "I05") from None
            if not about:
                log.info("install %s: gog has no %s build", gid, plat)
                continue
            if plat == "windows":
                if not proton.proton_dir(self.cfg):
                    self._upd(gid, state="downloading", phase="ge", progress=0, speed_mbs=0, eta_s=0)
                    proton.fetch_ge(cancel=lambda: gid in self._cancel, on_bytes=self._meter(gid))
                if not proton.umu_path():
                    self._upd(gid, state="downloading", phase="umu", progress=1)
                    proton.fetch_umu(cancel=lambda: gid in self._cancel)
                self._upd(gid, state="downloading", phase="queued", progress=0)
            in_place = bool(old) and old.get("platform") == plat      # an update: patch files
            files = dest / ("files" if in_place or not old else "files.new")
            have = _tree_size(files) if files.exists() else 0
            free = shutil.disk_usage(root).free
            need = about["need"] - have
            if about["need"] and need > free:
                raise InstallError(f"Not enough space on the {config.drive_name(root)}: needs about "
                                   f"{_gb(need)}, {_gb(free)} free.")
            files.mkdir(parents=True, exist_ok=True)
            log.info("install %s: gog %s %s build %s (%s) -> %s, ~%s%s", gid, g["app_name"], plat,
                     about.get("build"), about.get("version"), files, _gb(about["need"]),
                     " (update)" if in_place else "")
            if about["need"]:                     # GOG's list has no sizes: show this one
                self._upd(gid, size_mb=about["need"] // 1_000_000)

            def prog(frac, mbs, eta):             # first line: "Starting…" -> "Downloading"
                self._upd(gid, phase="download", progress=min(frac, 0.999), speed_mbs=mbs,
                          eta_s=eta)
            try:
                run = store.install(g["app_name"], plat, files, on_progress=prog,
                                    cancel=lambda: gid in self._cancel, log_file=log_file,
                                    fresh=not in_place)
                break
            except GogError as e:
                if str(e) == NO_PLAY:
                    raise InstallError("GOG's files have no program to start.", "I06") from None
                last = e
                if plat == "linux" and n + 1 < len(plats) and str(e) == "Couldn't install":
                    log.info("install %s: gog linux build failed, trying windows", gid)
                    shutil.rmtree(files, ignore_errors=True)
                    store.forget(g["app_name"])
                    continue
                raise InstallError(f"Couldn't install: {e}.", "I05") from None
        else:
            raise InstallError(f"Couldn't install: {last or 'no build'}.", "I05")
        if files.name == "files.new":             # platform changed: swap now that it worked
            shutil.rmtree(dest / "files", ignore_errors=True)
            files.replace(dest / "files")
            files = dest / "files"
        steps = []
        if plat == "windows":                     # GOG's shared parts + first-run setup list
            self._upd(gid, phase="installing", progress=1)
            try:
                ids = list(about.get("deps") or [])
                if any(files.glob("goggame-*.script")):    # GOG's setup tool runs them (ISI)
                    ids.append("ISI")
                repo = store.redist(ids, cancel=lambda: gid in self._cancel, log_file=log_file)
                steps = gog_mod.setup_steps(files, g["app_name"], about.get("deps"), repo,
                                            about.get("build"), about.get("version"))
            except GogError as e:                 # the game may still start without them
                log.warning("install %s: gog shared parts not downloaded: %s", gid, e)
            if Path(run["exe"]).name.lower() == "dosbox.exe":   # DOS game: native DOSBox (v0.9.7)
                from . import dosbox
                dosbox.ensure(log_file)
        used = _tree_size(files)
        info = {"game_id": gid, "title": g.get("title"), "store": "gog",
                "app_name": g["app_name"], "upload_id": plat, "platform": plat,
                "filename": g["app_name"], "exe": run["exe"], "args": run["args"],
                "cwd": run["cwd"], "alternatives": [], "size": used,
                "build_id": about.get("build"), "version": about.get("version"),
                "date": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "dir": str(dest), "setup_steps": steps,
                "setup_done": bool(in_place and (old or {}).get("setup_done"))}
        if run.get("setup"):
            info["setup"] = True              # GOG setup scripts (code P03 if it then fails)
            log.info("install %s: gog game ships first-run setup scripts", gid)
        if steps:
            log.info("install %s: first-run setup: %s", gid, ", ".join(s_["name"] for s_ in steps))
        if plat == "windows":
            info["prefix"] = (old or {}).get("prefix") or str(proton.prefix_dir(root, dest.name))
        _write_json(dest / "install.json", info)
        self.index[gid] = info
        _write_json(paths.INSTALLS, self.index)
        log.info("install %s: done in %.0fs -> %s (exe %s)", gid, time.time() - t0, dest, run["exe"])
        self._upd(gid, state="installed", phase=None, progress=0, fail_reason=None,
                  size_mb=used // 1_000_000, update=None)

    def check_gog_updates(self, force=False):
        """After each GOG sync (Y refreshes too): ask GOG for the newest
        build of each installed GOG game (gogdl info, at most every UPDATE_EVERY_S per game)
        and mark the ones that changed (Update button, like Epic)."""
        from .stores.gog import GogError
        store, now, found = self.lib.gog, time.time(), 0
        if not store:
            return 0
        for gid, info in list(self.index.items()):
            if info.get("store") != "gog" or gid == self.current or gid in self.queue:
                continue
            if not force and now - info.get("checked", 0) < UPDATE_EVERY_S:
                continue
            plat = info.get("platform") or "windows"
            try:
                about = store.info(info["app_name"], plat)
            except GogError as e:
                log.info("updates: gog %s", e)
                break
            info["checked"] = now
            if about:
                key = "build_id" if plat == "windows" else "version"
                cur, new = info.get(key), about.get("build" if plat == "windows" else "version")
                if cur and new and str(cur) != str(new):
                    info["update"] = {"upload_id": plat, "filename": info["app_name"], "updated": ""}
                    log.info("updates %s: gog %s -> %s", gid, cur, new)
                    found += 1
                else:
                    info.pop("update", None)
            self._save_info(gid, info)
            g = self.lib.by_id(gid)
            if g is not None:
                g["update"] = info.get("update")
        return found

    def _silent_install(self, gid, g, setup, tmp, root, dest):
        """Run setup.exe (Inno / NSIS) with no window into dest/files.inst, inside the game's
        own prefix, then put the result where the extracted files were (tmp). Returns the kind."""
        kind = proton.installer_kind(setup)
        if kind not in proton.SILENT_KINDS:
            name = {"installshield": "InstallShield"}.get(kind, "an unknown type")
            raise InstallError(f"This build uses an installer ({name}) that can't run silently. "
                               "Try another build with Change build.")
        pdir, umu = proton.proton_dir(self.cfg), proton.umu_path()
        if not pdir or not umu:
            raise InstallError("Windows installers need GE-Proton and umu-launcher. Retry.", "W10")
        target = dest / "files.inst"
        shutil.rmtree(target, ignore_errors=True)
        logs = paths.LOGS / "games"
        logs.mkdir(parents=True, exist_ok=True)
        self._upd(gid, state="downloading", phase="installing", progress=1)
        proton.run_installer(umu, setup, kind, target,
                             proton.env(pdir, proton.prefix_dir(root, dest.name)),
                             logs / f"{dest.name}-install.log",
                             cancel=lambda: gid in self._cancel,
                             on_phase=lambda ph: self._upd(gid, phase=ph))
        shutil.rmtree(tmp, ignore_errors=True)          # the setup.exe is not needed any more
        target.replace(tmp)
        log.info("install %s: %s installer done", gid, kind)
        return kind

    def _game_dir(self, root, g):
        d = root / slug_of(g)
        other = _read_json(d / "install.json", {}).get("game_id")
        if other and other != g["id"]:                 # two games with the same slug
            d = root / f"{slug_of(g)}-{g['id']}"
        return d

    def _meter(self, gid):
        """Progress callback: %, MB/s over the last ~3 s, ETA. Updates ~4x a second."""
        samples, last = [], [0.0]

        def on_bytes(done, total):
            now = time.monotonic()
            if now - last[0] < 0.25 and done < total:
                return
            last[0] = now
            samples.append((now, done))
            while len(samples) > 2 and now - samples[0][0] > 3:
                samples.pop(0)
            dt_, db = now - samples[0][0], done - samples[0][1]
            speed = db / dt_ if dt_ > 0.2 else 0
            self._upd(gid, progress=done / total if total else 0, speed_mbs=speed / 1e6,
                      eta_s=(total - done) / speed if speed and total else 0)
        return on_bytes

    # --- uninstall / lookup ---
    def exe_path(self, gid):
        info = self.index.get(gid)
        if not info:
            return None
        return Path(info["dir"]) / "files" / info["exe"]

    def programs(self, gid):
        """Runnable files found at install time (chosen one first) that still exist."""
        info = self.index.get(gid)
        if not info:
            return []
        files = Path(info["dir"]) / "files"
        out = [info["exe"]] + [a for a in info.get("alternatives", []) if a != info["exe"]]
        return [p for p in out if (files / p).is_file()]

    def set_exe(self, gid, rel):
        """Program picker: run this file from now on (kept in install.json, so restarts and
        updates keep it). The old choice stays in the list."""
        info = self.index.get(gid)
        if not info or rel not in self.programs(gid) or rel == info["exe"]:
            return False
        alts = [info["exe"]] + [a for a in info.get("alternatives", []) if a not in (rel, info["exe"])]
        info["exe"], info["alternatives"], info["exe_chosen"] = rel, alts, True
        _write_json(Path(info["dir"]) / "install.json", info)
        _write_json(paths.INSTALLS, self.index)
        log.info("install %s: program set to %s", gid, rel)
        return True

    # --- move between SD card and internal storage (16 Nov) ---
    def move_target(self, gid, choices):
        """(label, games folder) of the other drive, or None. choices = config.install_choices()."""
        info = self.index.get(gid)
        if not info or len(choices) < 2 or self.moving or gid == self.current or gid in self.queue:
            return None
        here = Path(info["dir"]).parent
        mine = [c for c in choices if Path(c[1]) == here]
        if not mine or config.card_missing(info["dir"]):
            return None
        return next(c for c in choices if c is not mine[0])

    def move(self, gid, dest_root, label):
        """Copy the game + its Proton folder to dest_root, check, switch, then delete the old
        copy. Until the switch the old copy is untouched and used; cancel = old copy stays."""
        if self.moving or gid not in self.index:
            return False
        self.moving = gid
        self._cancel.discard(gid)
        self._upd(gid, state="downloading", phase="move", progress=0, move_to=label)
        threading.Thread(target=self._move_thread, args=(gid, Path(dest_root), label),
                         daemon=True, name="move").start()
        return True

    def cancel_move(self, gid):
        if self.moving == gid:
            self._cancel.add(gid)

    def _move_thread(self, gid, dest_root, label):
        g = self.lib.by_id(gid) or {"title": gid}
        try:
            self._move(gid, dest_root)
            self.events.append(("done", gid, f"{g['title']} moved to {label}."))
        except MoveCancelled:
            log.info("move %s: cancelled", gid)
        except Exception as e:  # noqa: BLE001
            hint = words.short(str(e)) if isinstance(e, InstallError) else None
            if not hint:
                code = getattr(e, "code", None) or "M01"
                log.exception("move %s failed", gid)
                words.log_code(code, f"move {gid} ({g['title']}) to {dest_root}: {e}")
                msg = words.with_code(f"Couldn't move {g['title']}.", code)
            else:
                msg = f"Couldn't move {g['title']}. {hint}."
            self.events.append(("error", gid, msg))
        finally:
            self.moving = None
            self._cancel.discard(gid)
            self._upd(gid, state="installed" if gid in self.index else None, phase=None,
                      progress=0, move_to=None)
            shutil.rmtree(dest_root / MOVING, ignore_errors=True)

    def _move(self, gid, dest_root):
        info = dict(self.index[gid])
        src = Path(info["dir"])
        name = src.name
        src_root = src.parent
        src_pfx = Path(info["prefix"]) if info.get("prefix") else proton.prefix_dir(src_root, name)
        dst, dst_pfx = dest_root / name, proton.prefix_dir(dest_root, name)
        stage = dest_root / MOVING
        jobs = [(src, stage / "game")] + ([(src_pfx, stage / "prefix")] if src_pfx.is_dir() else [])
        total = sum(_tree_size(a) for a, _ in jobs)
        dest_root.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(dest_root).free
        if total + 200_000_000 > free:
            raise InstallError(f"Not enough space ({total // 1_000_000} MB needed, "
                               f"{free // 1_000_000} MB free).")
        for taken in (dst, dst_pfx):              # a leftover of ours that no install uses
            if taken.exists():
                if any(Path(i.get("dir", "")) == taken or Path(i.get("prefix") or "/") == taken
                       for i in self.index.values()):
                    raise InstallError("A game with the same folder is already there.", "M02")
                if taken == dst_pfx and taken.is_dir() and any(taken.iterdir()):   # saves of an
                    n, aside = 0, taken.with_name(f"{taken.name}.kept-{int(time.time())}")  # uninstalled game:
                    while aside.exists():                                          # keep them
                        n += 1
                        aside = taken.with_name(f"{taken.name}.kept-{int(time.time())}-{n}")
                    os.rename(taken, aside)
                    log.info("move %s: kept the old prefix as %s", gid, aside)
                elif safe_to_delete(taken, [dest_root]):
                    shutil.rmtree(taken, ignore_errors=True)
                else:
                    raise InstallError("A game with the same folder is already there.", "M02")
        shutil.rmtree(stage, ignore_errors=True)
        done = [0]

        def tick(n):
            done[0] += n
            if gid in self._cancel:
                raise MoveCancelled()
            self._upd(gid, progress=min(done[0] / total, 0.999) if total else 0.999)
        for a, b in jobs:
            _copy_tree(a, b, tick)
        for a, b in jobs:                         # check: same files, same sizes
            if _tree_size(a) != _tree_size(b) or _tree_count(a) != _tree_count(b):
                raise InstallError("The copy didn't match the original.", "M03")
        if gid in self._cancel:
            raise MoveCancelled()
        dst_pfx.parent.mkdir(parents=True, exist_ok=True)
        os.rename(stage / "game", dst)            # same drive: instant
        if (stage / "prefix").is_dir():
            os.rename(stage / "prefix", dst_pfx)
            fix_registry(dst_pfx, src_root, dest_root)
        info.update(dir=str(dst))
        if info.get("prefix") or src_pfx.is_dir():
            info["prefix"] = str(dst_pfx)
        if info.get("store") == "epic" and self.lib.epic:
            self.lib.epic.moved(info.get("app_name"), dst)
        self.index[gid] = info                    # the switch: from here on, the new copy
        _write_json(paths.INSTALLS, self.index)
        log.info("move %s: %s -> %s (%d MB)", gid, src, dst, total // 1_000_000)
        self._upd(gid, progress=1)
        shutil.rmtree(src, ignore_errors=True)    # the old copy
        if src_pfx.is_dir():
            shutil.rmtree(src_pfx, ignore_errors=True)

    def clean_moves(self, roots):
        """A move cut short (Deck off, app killed) leaves <root>/_moving: delete it at start."""
        for r in roots:
            p = Path(r) / MOVING
            if p.is_dir() and not config.card_missing(str(p)):
                log.info("move: removing leftover %s", p)
                shutil.rmtree(p, ignore_errors=True)

    def delete_roots(self):
        """Folders games may be deleted under: where installs go now, both drive choices, and the
        scritch/itch games folder of every game already installed (older installs, moved games)."""
        roots = []
        try:
            roots.append(self.root_fn())
        except Exception:  # noqa: BLE001 - a missing card must not stop an uninstall's bookkeeping
            pass
        roots += [r for _name, r in config.install_choices()]
        for i in self.index.values():
            par = Path(i.get("dir") or "/").parent
            if par.name in ("itch", "scritch"):
                roots.append(par)
        return roots

    def uninstall(self, gid):
        """Forget the install now; delete the files in the background (big games take a while).
        Proton prefixes live in <root>/_prefixes and are kept, so saves survive."""
        cur = self.index.get(gid)
        if cur and config.card_missing(cur["dir"]):    # can't delete it, so don't forget it
            log.info("uninstall %s: refused, SD card missing (%s)", gid, cur["dir"])
            return False
        roots = self.delete_roots()                    # before the pop: its own games folder counts
        info = self.index.pop(gid, None)
        _write_json(paths.INSTALLS, self.index)
        if self.choices.pop(gid, None) is not None:   # a fresh install starts from the default
            _write_json(paths.BUILDS, self.choices)    # build again (v0.9.8)
        self._upd(gid, state=None, phase=None)
        if info and info.get("store") == "gog" and self.lib.gog:     # gogdl's manifest goes too
            self.lib.gog.forget(info.get("app_name"))
        if info and info.get("store") == "epic" and self.lib.epic:   # legendary forgets it too
            threading.Thread(target=self.lib.epic.uninstall, args=(info.get("app_name"),),
                             daemon=True, name="epic-uninstall").start()
        if info and not safe_to_delete(info["dir"], roots):
            log.warning("uninstall %s: NOT deleting %s (not inside a games folder)", gid, info["dir"])
        elif info:
            log.info("uninstall %s: %s", gid, info["dir"])
            threading.Thread(target=shutil.rmtree, args=(info["dir"],), kwargs={"ignore_errors": True},
                             daemon=True, name="uninstall").start()
        return True
