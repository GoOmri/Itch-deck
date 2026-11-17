"""Your own DOS games (v0.9.19, Omri 17 Nov): copy a game folder (or a .zip) into the "dos" folder next
to your other games; SCRiTCH lists each one in the DOS tab and runs it in DOSBox Staging.

Nothing is ever downloaded and no file of yours is ever deleted: "Remove from library" only forgets the
entry (and the entry stays hidden until the folder is copied again, see removed()). A .zip is unpacked
into a folder next to it and then moved to dos/_zips (kept, never deleted).

Pure file logic, no pygame: installer.sync_dos() turns the result into library entries."""
import json
import logging
import re
import shutil
import zipfile
from pathlib import Path

from . import paths

log = logging.getLogger("scritch")

PROGRAM_EXTS = (".exe", ".com", ".bat")
IMAGE_EXTS = (".iso", ".cue")
COVER_NAMES = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp")
# helpers that are not the game (DOS games ship setup / sound-card / uninstall tools next to it)
SKIP_WORDS = ("setup", "install", "uninst", "unwise", "config", "setsound", "sndsetup", "soundset",
              "readme", "dosbox", "vesa", "univbe", "mouse", "emm386", "himem", "pkunzip", "unzip",
              "pkzip", "arj", "lha", "update", "patch", "mscdex", "fixit")
MAX_DEPTH = 2
UNPACKED = "_zips"           # unpacked .zip files are moved here (kept)


def dos_dir(root):
    """The folder players copy games into: <games folder>/dos (follows Install location)."""
    return Path(root) / "dos"


def state_file():
    return paths.DATA / "dos.json"


def _state():
    try:
        d = json.loads(state_file().read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(d):
    try:
        state_file().parent.mkdir(parents=True, exist_ok=True)
        state_file().write_text(json.dumps(d, indent=1))
    except OSError as e:
        log.info("dosgames: can't save %s: %s", state_file(), e)


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "game"


def game_id(name):
    return "dos-" + slug(name)


def title_of(name):
    """Folder name -> title: underscores to spaces, nothing else ("EOB_1" stays recognisable)."""
    t = re.sub(r"[_]+", " ", name).strip()
    return t or name


def is_helper(path):
    low = Path(path).stem.lower()
    return any(w in low for w in SKIP_WORDS)


def programs(folder):
    """Runnable files (.exe .com .bat) in the game folder, relative with '/' separators: shallow
    first, helpers (setup, sound config...) left out."""
    folder, out = Path(folder), []
    try:
        for p in folder.rglob("*"):
            rel = p.relative_to(folder)
            if len(rel.parts) > MAX_DEPTH + 1 or not p.is_file():
                continue
            if p.suffix.lower() in PROGRAM_EXTS and not is_helper(p):
                out.append(rel.as_posix())
    except OSError:
        return []
    return sorted(out, key=lambda r: (r.count("/"), r.lower()))


def pick_program(folder_name, progs, saved=None):
    """The program to run: the saved choice if it is still there, else the one that looks like the game
    (a name equal to the folder's, a single .bat, or the only file); else the first (shallowest)."""
    if saved and saved in progs:
        return saved
    if not progs:
        return None
    stem = slug(folder_name)
    for p in progs:
        if slug(Path(p).stem) == stem:
            return p
    bats = [p for p in progs if p.lower().endswith(".bat") and "/" not in p]
    if len(bats) == 1:
        return bats[0]
    return progs[0]


def cd_image(folder):
    """A disc image in the folder (.iso / .cue, a .cue first), relative path, or None."""
    folder = Path(folder)
    try:
        found = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS
                 and len(p.relative_to(folder).parts) <= MAX_DEPTH + 1]
    except OSError:
        return None
    found.sort(key=lambda p: (p.suffix.lower() != ".cue", len(p.relative_to(folder).parts), p.name.lower()))
    return found[0].relative_to(folder).as_posix() if found else None


def cover_of(folder):
    folder = Path(folder)
    for n in COVER_NAMES:
        for p in (folder / n, folder / n.upper()):
            if p.is_file():
                return p
    try:                                   # any case: Cover.JPG
        for p in folder.iterdir():
            if p.is_file() and p.name.lower() in COVER_NAMES:
                return p
    except OSError:
        pass
    return None


def tree_size(folder):
    total = 0
    try:
        for p in Path(folder).rglob("*"):
            try:
                if p.is_file() and not p.is_symlink():
                    total += p.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


# --- hidden ("removed") games ----------------------------------------------------------------------
def removed():
    """folder name -> unix time it was removed from the library. Such a folder stays hidden until it
    is changed after that (copied again), so a removed game does not come straight back."""
    d = _state().get("removed")
    return d if isinstance(d, dict) else {}


def remember_removed(name, when):
    st = _state()
    st.setdefault("removed", {})[name] = when
    _save_state(st)


def forget_removed(name):
    st = _state()
    if st.get("removed", {}).pop(name, None) is not None:
        _save_state(st)


def _hidden(folder, hide):
    ts = hide.get(folder.name)
    try:
        return ts is not None and folder.stat().st_mtime <= ts
    except OSError:
        return True


# --- .zip files ------------------------------------------------------------------------------------
def unpack_zips(root):
    """Unpack every .zip in root into a folder named like the zip (unless one exists), then move the zip
    to root/_zips (kept). A zip with one top folder inside is unpacked without that extra level.
    Unsafe paths (../ or absolute) are refused. Returns the folder names made."""
    root, made = Path(root), []
    try:
        zips = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".zip")
    except OSError:
        return made
    for z in zips:
        dest = root / z.stem
        if dest.exists():
            continue
        tmp = root / (z.stem + ".unpacking")
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            with zipfile.ZipFile(z) as zf:
                names = [n for n in zf.namelist() if n and not n.endswith("/")]
                bad = [n for n in zf.namelist() if n.startswith(("/", "\\")) or ".." in Path(n).parts
                       or (len(n) > 1 and n[1] == ":")]
                if bad or not names:
                    log.info("dosgames: %s skipped (%s)", z.name, "unsafe paths" if bad else "empty")
                    continue
                zf.extractall(tmp)
            tops = {n.split("/")[0] for n in names}
            if len(tops) == 1 and all("/" in n for n in names):      # one top folder: skip that level
                (tmp / next(iter(tops))).rename(dest)
            else:
                tmp.rename(dest)
            shutil.rmtree(tmp, ignore_errors=True)
            (root / UNPACKED).mkdir(exist_ok=True)
            target = root / UNPACKED / z.name
            if not target.exists():
                z.rename(target)
            made.append(z.stem)
            log.info("dosgames: unpacked %s", z.name)
        except (OSError, zipfile.BadZipFile, ValueError) as e:
            log.info("dosgames: can't unpack %s: %s", z.name, e)
            shutil.rmtree(tmp, ignore_errors=True)
    return made


# --- the scan ----------------------------------------------------------------------------------------
def scan(root, choices=None, hide=None):
    """Every game folder in root (after unpacking zips): [{"name", "id", "title", "dir", "exe",
    "programs", "cover", "image"}]. choices = {game id: chosen program}; hide = removed()."""
    root, out = Path(root), []
    choices = choices or {}
    hide = removed() if hide is None else hide
    if not root.is_dir():
        return out
    unpack_zips(root)
    try:
        folders = sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))
                          and not p.name.endswith(".unpacking")), key=lambda p: p.name.lower())
    except OSError:
        return out
    for f in folders:
        if _hidden(f, hide):
            continue
        progs = programs(f)
        if not progs:
            log.info("dosgames: %s has no .exe/.com/.bat, skipped", f.name)
            continue
        gid = game_id(f.name)
        out.append({"name": f.name, "id": gid, "title": title_of(f.name), "dir": str(f),
                    "exe": pick_program(f.name, progs, choices.get(gid)), "programs": progs,
                    "cover": cover_of(f), "image": cd_image(f)})
    return out
