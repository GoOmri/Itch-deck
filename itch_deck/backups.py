"""Save backups (Omri 16 Nov: automatic after every play, in a visible Documents folder).

~/Documents/SCRiTCH saves/<Game>/<YYYY-MM-DD HH-MM>.zip, the last KEEP per game, plus about.json
(game id, title, learned Linux folders, fingerprint of the last backup).

What is saved:
- Windows games (itch + Epic): the save part of the game's Proton prefix
  (drive_c/users/steamuser: AppData, Documents, Saved Games), caches left out. Zip paths "win/…".
- Linux games: folders under ~/.local/share, ~/.config, ~/.local/state that the game changed while
  it ran (learned per game, see learn()). Zip paths "home/<path under HOME>".
A backup is only made when the saves changed since the last one (fingerprint of names, sizes,
times). Restore first backs up the current saves ("before restore"), then writes the zip's files
over them (nothing is deleted).
"""
import hashlib
import json
import logging
import os
import re
import time
import zipfile
from pathlib import Path

from . import paths

log = logging.getLogger("scritch")

KEEP = 5
BIG = 100_000_000                       # a single file this big isn't a save (videos, caches)
WIN_DIRS = ("AppData/Roaming", "AppData/LocalLow", "AppData/Local", "Documents", "Saved Games")
SKIP = {"temp", "tmp", "cache", "caches", "shadercache", "shader_cache", "gpucache", "d3dscache",
        "nvidia", "nvidia corporation", "amd", "mesa", "inetcache", "crashdumps", "crashes",
        "microsoft", "packages", "logs", "webcache", "code cache", "unity/cache"}
NOISE = (".log", ".tmp", ".lock", ".pid")   # changes every run, never a save
LINUX_ROOTS = (".local/share", ".config", ".local/state")
NOT_GAMES = {  # folders under the Linux roots that change for other reasons than a game's saves
    "steam", "flatpak", "umu", "scritch", "itch-deck", "trash", "baloo", "mesa_shader_cache",
    "mesa_shader_cache_db", "vulkan", "pulse", "pipewire", "wireplumber", "dconf", "fontconfig",
    "systemd", "xdg-desktop-portal", "gamescope", "mangohud", "decky", "heroic", "lutris",
    "legendary", "chiaki", "chiaki-ng", "kwin", "kded5", "kded6", "plasma", "kdeconnect",
    "recently-used.xbel", "user-places.xbel", "mimeapps.list", "kitware", "sunshine",
    "icons", "applications", "keyrings", "nautilus", "dolphin", "konsole", "akonadi", "kactivitymanagerd",
    "godot/projects", "evolution", "gvfs-metadata", "warpinator", "rustdesk", "firefox", "mozilla",
}


def root():
    return paths.HOME / "Documents" / "SCRiTCH saves"


def _safe(title):
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title or "").strip(" .") or "Game"


def folder(gid, title):
    """The game's backup folder: its title; another game with the same title gets "(id)"."""
    base = root()
    if base.is_dir():
        for d in base.iterdir():
            if (_about(d).get("id")) == gid:
                return d
    d = base / _safe(title)
    if d.exists() and _about(d).get("id") not in (None, gid):
        d = base / f"{_safe(title)} ({gid})"
    return d


def _about(d):
    try:
        return json.loads((Path(d) / "about.json").read_text())
    except (OSError, ValueError):
        return {}


def _save_about(d, a):
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "about.json.tmp"
    tmp.write_text(json.dumps(a, indent=1))
    os.replace(tmp, d / "about.json")


def _skip(rel):
    low = rel.lower()
    return any(part in SKIP for part in low.split("/")) or "unity/cache" in low


def _user_dir(info):
    """drive_c/users/steamuser of a Windows game's prefix (same prefix as app_play uses)."""
    prefix = info.get("prefix")
    if not prefix and info.get("dir"):
        from .proton import prefix_dir
        prefix = prefix_dir(Path(info["dir"]).parent, Path(info["dir"]).name)
    p = Path(prefix)
    for user in (p / "pfx" / "drive_c" / "users" / "steamuser",
                 p / "drive_c" / "users" / "steamuser"):
        if user.is_dir():
            return user
    return p / "drive_c" / "users" / "steamuser"


def _windows(info):
    return info.get("platform") == "windows" and bool(info.get("prefix") or info.get("dir"))


def files(gid, info, d=None):
    """[(path on disk, path in the zip)] of this game's saves now."""
    out = []
    if _windows(info):
        user = _user_dir(info)
        for sub in WIN_DIRS:
            base = user / sub
            for p in _walk(base):
                rel = p.relative_to(user).as_posix()
                if not _skip(rel):
                    out.append((p, "win/" + rel))
    else:
        a = _about(d or folder(gid, ""))
        for rel in a.get("linux_dirs") or []:
            base = paths.HOME / rel
            for p in _walk(base):
                out.append((p, "home/" + p.relative_to(paths.HOME).as_posix()))
    return [(p, n) for p, n in out if _size(p) <= BIG]


def _walk(base):
    if not base.is_dir():
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        rel = Path(dirpath).relative_to(base).as_posix().lower()
        dirnames[:] = [n for n in dirnames if n.lower() not in SKIP
                       and not os.path.islink(os.path.join(dirpath, n))]
        if rel != "." and _skip(rel):
            continue
        for n in filenames:
            p = Path(dirpath) / n
            if not p.is_symlink() and not n.lower().endswith(NOISE):
                found.append(p)
    return found


def _size(p):
    try:
        return p.stat().st_size
    except OSError:
        return BIG + 1


def _fingerprint(fl):
    h = hashlib.sha1()
    for p, n in sorted(fl, key=lambda x: x[1]):
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"{n}|{st.st_size}|{int(st.st_mtime)}\n".encode())
    return h.hexdigest()


def backup(gid, title, info, note="", protect=None):
    """Zip the saves if they changed since the last backup. Returns the zip path, or None when
    there was nothing (new) to save. Raises OSError when writing fails."""
    d = folder(gid, title)
    fl = files(gid, info, d)
    if not fl:
        return None
    a = _about(d)
    fp = _fingerprint(fl)
    if fp == a.get("fingerprint") and not note:
        return None
    d.mkdir(parents=True, exist_ok=True)
    name = time.strftime("%Y-%m-%d %H-%M-%S") + (f" {note}" if note else "") + ".zip"
    z = d / name
    tmp = d / (name + ".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, n in fl:
            try:
                zf.write(p, n)
            except OSError as e:               # a file vanished or can't be read: skip it
                log.info("backup %s: skipped %s (%s)", gid, n, e)
    os.replace(tmp, z)
    a.update({"id": gid, "title": title, "fingerprint": fp})
    _save_about(d, a)
    prune(d, protect)
    log.info("backup %s: %s (%d files)", gid, z.name, len(fl))
    return z


def prune(d, protect=None):
    """Keep the newest KEEP; `protect` (the zip being restored) is never deleted."""
    zips = [z for z in list_zips(d) if protect is None or Path(z) != Path(protect)]
    for z in zips[KEEP - (1 if protect is not None and Path(protect).exists() else 0):]:
        try:
            z.unlink()
        except OSError:
            pass


def list_zips(d):
    """Newest first."""
    if not Path(d).is_dir():
        return []
    return sorted(Path(d).glob("*.zip"), key=lambda p: p.name, reverse=True)


def listing(gid, title=""):
    return list_zips(folder(gid, title))


def label(z):
    """'2026-11-16 09-50-12 before restore.zip' -> ('16 Nov, 09:50', 'Before restore')"""
    m = re.match(r"(\d{4})-(\d\d)-(\d\d) (\d\d)-(\d\d)", z.name)
    if not m:
        return z.stem, ""
    t = time.strptime("-".join(m.groups()[:3]), "%Y-%m-%d")
    when = f"{t.tm_mday} {time.strftime('%b', t)}, {m.group(4)}:{m.group(5)}"
    return when, ("Before restore" if "before restore" in z.name else "")


def restore(gid, title, info, z):
    """Back up what's there now ("before restore"), then write the zip's files back."""
    d = folder(gid, title)
    backup(gid, title, info, note="before restore", protect=z)
    if _windows(info):
        bases = {"win": _user_dir(info)}
    else:
        bases = {"home": paths.HOME}
    n = 0
    with zipfile.ZipFile(z) as zf:
        for m in zf.infolist():
            top, _, rel = m.filename.partition("/")
            if m.is_dir() or top not in bases or not rel:
                continue
            dest = (bases[top] / rel).resolve()
            if not str(dest).startswith(str(bases[top].resolve()) + os.sep):
                log.warning("restore %s: unsafe path %s", gid, m.filename)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".scritch-restore")
            with zf.open(m) as src, open(tmp, "wb") as out:
                while chunk := src.read(1 << 20):
                    out.write(chunk)
            os.replace(tmp, dest)
            n += 1
    a = _about(d)
    a["fingerprint"] = _fingerprint(files(gid, info, d))   # restored state = no new backup
    _save_about(d, a)
    prune(d, protect=z)
    log.info("restore %s: %s (%d files)", gid, z.name, n)
    return n


def learn(gid, title, since):
    """Linux games: remember the save folders the game changed while it ran (modified after
    `since`). Folder = the game's own folder under ~/.local/share, ~/.config or ~/.local/state
    (godot/app_userdata/<game>, unity3d/<studio>/<game>, love/<game>: one level deeper)."""
    found = set()
    for r in LINUX_ROOTS:
        base = paths.HOME / r
        if not base.is_dir():
            continue
        for p in _changed(base, since):
            parts = p.relative_to(base).parts
            if len(parts) < 2 and p.is_file():
                continue                       # a loose file in ~/.config: not a game folder
            low = [x.lower() for x in parts]
            if low[0] in NOT_GAMES or "/".join(low[:2]) in NOT_GAMES:
                continue
            depth = 3 if low[0] in ("godot", "unity3d") else 2 if low[0] == "love" else 1
            if len(parts) <= depth:
                continue
            found.add((Path(r) / Path(*parts[:depth])).as_posix())
    if not found:
        return []
    d = folder(gid, title)
    a = _about(d)
    known = list(a.get("linux_dirs") or [])
    new = [f for f in sorted(found) if f not in known]
    if new:
        a.update({"id": gid, "title": title, "linux_dirs": known + new})
        _save_about(d, a)
        log.info("backup %s: learned save folders %s", gid, new)
    return new


def _changed(base, since, depth=6):
    out = []

    def walk(d, n):
        try:
            it = list(os.scandir(d))
        except OSError:
            return
        for e in it:
            if e.is_symlink():
                continue
            low = e.name.lower()
            if n == 0 and low in NOT_GAMES:
                continue
            try:
                if e.is_dir():
                    if n < depth and low not in SKIP:
                        walk(e.path, n + 1)
                elif e.stat().st_mtime >= since and not low.endswith(NOISE):
                    out.append(Path(e.path))
            except OSError:
                pass
    walk(base, 0)
    return out
