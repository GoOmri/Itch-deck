"""Installs (M3: Linux builds). One download at a time from a queue that survives a restart:
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

from . import net, paths
from .stores.itch import pick_build

log = logging.getLogger("itch-deck")
SPACE_FACTOR = 2.5            # download + extracted copy + slack
SKIP_EXE = ("unins", "crashhandler", "crash_handler", "crashpad", "vc_redist", "dxsetup",
            "unitycrash", "chrome-sandbox", "chrome_sandbox", "notification_helper")


class InstallError(Exception):
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
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
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


def extract(archive, dest):
    """zip (keeps exec bits), tar.*, 7z (if py7zr is bundled), or a single runnable file."""
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
    if ext in ("rar", "dmg", "apk", "exe", "msi", "pkg", "deb", "rpm", "jar"):
        raise InstallError(f".{ext} downloads aren't supported.")
    # a bare executable (AppImage, .x86_64, .sh, …): copy it in as-is
    out = dest / re.sub(r"^\d+-\d+-", "", archive.name)   # drop our "<game>-<upload>-" prefix
    shutil.copyfile(archive, out)
    os.chmod(out, 0o755)


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


def _script(path):
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def find_exe(root, g):
    """Best runnable file under root, plus the other candidates (relative paths). Also sets the
    exec bit on every ELF and script, since archives often lose it (pitfall #7)."""
    root = Path(root)
    title = re.sub(r"[^a-z0-9]", "", (g.get("title") or "").lower())
    slug = re.sub(r"[^a-z0-9]", "", slug_of(g))
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


# --- installer -----------------------------------------------------------------------------
class Installer:
    def __init__(self, lib, root_fn):
        self.lib, self.root_fn = lib, root_fn
        self.index = _read_json(paths.INSTALLS, {})        # gid -> {dir, exe, upload_id, ...}
        self.queue = [gid for gid in _read_json(paths.QUEUE, []) if gid not in self.index]
        self.current = None
        self.events = []          # ("done"|"failed", gid, text) for the UI thread to toast
        self._cancel = set()
        self._thread = None
        self._lock = threading.Lock()
        lib.installs, lib.live = self.index, {}
        lib.apply_installs()

    # --- queue (called from the UI thread) ---
    def resume(self):
        """Downloads that were running or queued when the app last quit."""
        if self.queue:
            log.info("install queue resumed: %s", self.queue)
            for gid in self.queue:
                self._upd(gid, state="queued", phase=None)
            self._start()

    def enqueue(self, g):
        gid = g["id"]
        with self._lock:
            if gid in self.queue or gid in self.index:
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
        self._upd(gid, state=None, phase=None)

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
                self.events.append(("done", gid, f"{title} is installed."))
            except net.Cancelled:
                log.info("install %s: cancelled", gid)
                self._cleanup_download(gid)
                self._upd(gid, state=None, phase=None, progress=0)
            except (net.Offline, net.NotFound) as e:
                log.info("install %s: network (%s)", gid, e)
                self._fail(gid, title, "Lost the connection to itch.io. Retry when you're online "
                                       "(the download continues where it stopped).")
            except net.AuthError:
                self._fail(gid, title, "itch.io rejected the API key. Re-import it in Settings.")
            except InstallError as e:
                log.info("install %s: %s", gid, e)
                self._fail(gid, title, str(e))
            except Exception:  # noqa: BLE001
                log.exception("install %s failed", gid)
                self._fail(gid, title, "Something went wrong. Details are in the log.")
            finally:
                with self._lock:
                    if self.queue and self.queue[0] == gid:
                        self.queue.pop(0)
                    self._cancel.discard(gid)
                    self._save_queue()

    def _fail(self, gid, title, reason):
        self._upd(gid, state="failed", phase=None, fail_reason=reason)
        self.events.append(("failed", gid, f"Couldn't install {title}."))

    def _cleanup_download(self, gid):
        dl = self._dl_dir()
        for f in dl.glob(f"{gid}-*") if dl.exists() else []:
            f.unlink(missing_ok=True)

    def _dl_dir(self):
        return Path(self.root_fn()) / "_downloads"

    def _install(self, g):
        gid, store = g["id"], self.lib.store
        if not store:
            raise InstallError("Not connected to itch.io yet.")
        t0 = time.time()
        builds = store.list_builds(g)
        build, others = pick_build(builds, "linux")
        if not build:
            win, _ = pick_build(builds, "windows")
            raise InstallError("This game only has a Windows build. Windows games come in the "
                               "next update." if win else "No Linux download found for this game.")
        if others:
            log.info("install %s: picked %s over %s", gid, build["filename"],
                     [o["filename"] for o in others])
        size = build["size"]
        self._upd(gid, size_mb=size // 1_000_000)

        root = Path(self.root_fn())
        try:
            root.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(root).free
        except OSError as e:
            raise InstallError(f"Can't write to the install folder {root}.") from e
        dl = self._dl_dir() / f"{gid}-{build['id']}-{re.sub(r'[^A-Za-z0-9._-]', '_', build['filename'])}"
        have = dl.with_name(dl.name + ".part")
        have = have.stat().st_size if have.exists() else 0
        if size and free + have < size * SPACE_FACTOR:
            raise InstallError(f"Not enough space: needs about {_gb(size * SPACE_FACTOR)}, "
                               f"{_gb(free)} free.")
        dl.parent.mkdir(parents=True, exist_ok=True)
        for old in dl.parent.glob(f"{gid}-*"):          # an older build's leftovers
            if not old.name.startswith(dl.name):
                old.unlink(missing_ok=True)

        if not dl.exists():
            self._upd(gid, state="downloading", phase="download", progress=0, speed_mbs=0, eta_s=0)
            log.info("install %s: download %s (%d MB)%s", gid, build["filename"], size // 1_000_000,
                     f", resuming at {have // 1_000_000} MB" if have else "")
            net.download(store.download_url(g, build), dl, key=getattr(store, "key", None),
                         resume=True, cancel=lambda: gid in self._cancel, on_bytes=self._meter(gid))
        self._upd(gid, state="downloading", phase="extract", progress=1)

        dest = self._game_dir(root, g)
        tmp = dest / "files.new"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            extract(dl, tmp)
            exe, alts = find_exe(tmp, g)
            if not exe:
                raise InstallError("No program to run was found in the download.")
        except InstallError:
            shutil.rmtree(tmp, ignore_errors=True)
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
                "filename": build["filename"], "platform": "linux", "exe": exe, "alternatives": alts[:10],
                "size": used, "date": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "dir": str(dest)}
        _write_json(dest / "install.json", info)
        self.index[gid] = info
        _write_json(paths.INSTALLS, self.index)
        dl.unlink(missing_ok=True)
        log.info("install %s: done in %.0fs -> %s (exe %s; %d other candidates)", gid,
                 time.time() - t0, dest, exe, len(alts))
        self._upd(gid, state="installed", phase=None, progress=0, fail_reason=None,
                  size_mb=used // 1_000_000)

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

    def uninstall(self, gid):
        """Forget the install now; delete the files in the background (big games take a while).
        Proton prefixes (M4) live elsewhere and are kept, so saves survive."""
        info = self.index.pop(gid, None)
        _write_json(paths.INSTALLS, self.index)
        self._upd(gid, state=None, phase=None)
        if info:
            log.info("uninstall %s: %s", gid, info["dir"])
            threading.Thread(target=shutil.rmtree, args=(info["dir"],), kwargs={"ignore_errors": True},
                             daemon=True, name="uninstall").start()
