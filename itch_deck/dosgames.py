"""Your own DOS games (v0.9.19, Omri 17 Nov): copy a game folder (or a .zip) into the "dos" folder next
to your other games; SCRiTCH lists each one in the DOS tab and runs it in DOSBox Staging.

Nothing is ever downloaded and no file of yours is ever deleted or changed: "Remove from library" only
forgets the entry (the folder stays hidden until it changes, see removed()). A .zip is unpacked into a
folder next to it and then moved to dos/_zips (kept, never deleted).

Pure file logic, no pygame, no shared state: installer.scan_dos() runs it in a thread, installer.apply_dos()
turns the result into library entries on the main thread."""
import hashlib
import json
import logging
import os
import re
import shutil
import zipfile
from pathlib import Path

from . import dosart, paths

log = logging.getLogger("scritch")

PROGRAM_EXTS = (".exe", ".com", ".bat")
IMAGE_EXTS = (".iso", ".cue")
COVER_NAMES = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp")
# helpers that are not the game (DOS games ship setup / sound-card / uninstall tools next to it)
SKIP_WORDS = ("setup", "install", "uninst", "unwise", "config", "setsound", "sndsetup", "soundset",
              "readme", "dosbox", "vesa", "univbe", "mouse", "emm386", "himem", "pkunzip", "unzip",
              "pkzip", "arj", "lha", "update", "patch", "mscdex", "fixit")
MAX_DEPTH = 2                # programs and disc images: at most this many folders down
UNPACKED = "_zips"           # unpacked .zip files are moved here (kept)
SPACE_MARGIN = 1.2           # free space needed to unpack = the zip's contents * this


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
    """dos-<readable part>-<6 hex of the folder name>: stable, and two folders never share an id
    (Cyrillic or Japanese names all slug to "game"; "A B" and "a-b" slug alike)."""
    return f"dos-{slug(name)[:40]}-{hashlib.sha1(name.encode('utf-8', 'replace')).hexdigest()[:6]}"


def unique_id(name, folder, used):
    """The id for a game folder. The first folder with a name keeps the old id (game_id(name)): hidden marks and
    saves follow it. A SECOND folder with the same name (a copy in another place or on the other drive) used to be
    dropped silently, so a new game could "not show up"; now it gets its own id from its whole path. None when this
    very folder was already listed."""
    gid = game_id(name)
    if gid not in used:
        used[gid] = str(folder)
        return gid
    if used[gid] == str(folder):
        return None
    gid = game_id(f"{name}|{folder}")
    if gid in used:
        return None
    used[gid] = str(folder)
    return gid


def _tag_of(name):
    """What a folder name says in its (...) / [...] groups apart from a year: "(Apogee Software)" -> "Apogee Software"."""
    bits = [g[1:-1].strip() for g in dosart.GROUP_RE.findall(name)]
    return ", ".join(b for b in bits if b and not dosart.YEAR_RE.fullmatch(b))


def disambiguate(entries):
    """Two games that would show the same title get a short difference: the year when they differ, else what the
    folder name says in its brackets, else a number. Only the shown title changes (ids, folders, marks stay)."""
    groups = {}
    for e in entries:
        groups.setdefault(e["title"].casefold(), []).append(e)
    for same in groups.values():
        if len(same) < 2:
            continue
        years = [e.get("year") for e in same if e.get("year")]
        if len(set(years)) == len(years) and len(same) - len(years) <= 1:
            for e in same:
                if e.get("year"):                   # the one without a year keeps the plain title
                    e["title"] = f"{e['title']} ({e['year']})"
            continue
        tags = [_tag_of(e["name"]) for e in same]
        use_tags = all(tags) and len(set(tags)) == len(tags)
        for n, e in enumerate(same):
            e["title"] = f"{e['title']} ({tags[n] if use_tags else n + 1})"
    return entries


def title_of(name):
    """Folder name -> title: underscores to spaces, nothing else ("EOB_1" stays recognisable)."""
    t = re.sub(r"[_]+", " ", name).strip()
    return t or name


def is_helper(path):
    low = Path(path).stem.lower()
    return any(w in low for w in SKIP_WORDS)


SETUP_WORDS = ("setup", "install", "config", "setsound", "sndsetup", "soundset", "update", "patch", "fixit")
SETUPS = {}                   # folder -> its setup programs, filled by survey() (read by scan(): one walk only)


def survey(folder):
    """One walk of the game folder: (programs, disc image, size in bytes). Programs (.exe .com .bat, helpers
    left out) are relative with '/' separators, shallow first; the image is the first .cue (else .iso);
    only MAX_DEPTH folders down are looked at for both. Symlinks are not followed and not counted."""
    folder = Path(folder)
    progs, images, size, setups = [], [], 0, []
    try:
        for dirpath, dirs, files in os.walk(folder, followlinks=False):
            rel_dir = Path(dirpath).relative_to(folder)
            depth = len(rel_dir.parts)
            for f in files:
                p = Path(dirpath) / f
                try:
                    if p.is_symlink():
                        continue
                    size += p.stat().st_size
                except OSError:
                    continue
                if depth > MAX_DEPTH:
                    continue
                rel = (rel_dir / f).as_posix() if depth else f
                ext = Path(f).suffix.lower()
                if ext in PROGRAM_EXTS and not is_helper(f):
                    progs.append(rel)
                elif ext in PROGRAM_EXTS and any(w in Path(f).stem.lower() for w in SETUP_WORDS):
                    setups.append(rel)                 # listed in "Program to run" as setup, never the default
                elif ext in IMAGE_EXTS:
                    images.append(rel)
    except OSError:
        pass
    progs.sort(key=lambda r: (r.count("/"), r.lower()))
    setups.sort(key=lambda r: (r.count("/"), r.lower()))
    SETUPS[str(folder)] = setups
    images.sort(key=lambda r: (not r.lower().endswith(".cue"), r.count("/"), r.lower()))
    return progs, (images[0] if images else None), size


def programs(folder):
    return survey(folder)[0]


HELPER_FOLDERS = ("setup", "install", "tools", "utils", "util", "drivers", "sound", "docs", "doc", "patch",
                  "patches", "update", "config", "editor", "editors")
COLLECTION_MIN = 3           # a folder with this many game folders inside (and no program of its own) is a collection


def collection(folder):
    """A folder that only holds game folders (a zip of 20 games unpacks to one): {subfolder: survey} for
    each game inside, or {} when this is a game itself. Needs no program directly inside, and at least
    COLLECTION_MIN subfolders that each hold one (setup / editor tools don't count as games)."""
    folder = Path(folder)
    subs = []
    try:
        for p in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            if p.is_file() and p.suffix.lower() in PROGRAM_EXTS and not is_helper(p.name):
                return {}                                    # it has a program of its own: one game
            if p.is_dir() and not p.is_symlink() and not p.name.startswith((".", "_")) \
                    and p.name.lower().strip() not in HELPER_FOLDERS:    # whole name: "Mouse Hunt" is a game
                subs.append(p)
    except OSError:
        return {}
    found = {}
    for p in subs:
        s = survey(p)
        if s[0]:
            found[p] = s
    return found if len(found) >= COLLECTION_MIN else {}


def cd_image(folder):
    return survey(folder)[1]


def tree_size(folder):
    return survey(folder)[2]


# Programs that are about the game, not the game (a technical-support or order-form program started instead of Bio
# Menace). Only the DEFAULT pick avoids them; they stay in the list. Whole words of the name, or the short 8.3 forms
# DOS games use ("TECHSUPP", "ORDERING"); a real game like "Mouse Hunt", "Helpful Harry" or "Technoid" is not hit.
SUPPORT_WORDS = {"trainer", "cheat", "cheats", "tech", "support", "help", "order", "ordering", "info", "readme",
                 "vendor", "hint", "hints", "orderfrm", "orderform", "techsupp", "techsupport", "techhelp",
                 "techinfo", "vendinfo", "orderinf", "orderinfo"}


def is_support(rel):
    """True for a program that only looks like support / order / cheat help (judged by its file name)."""
    stem = Path(rel).stem.lower()
    words = [w for w in re.split(r"[^a-z0-9]+", stem) if w]
    return stem in SUPPORT_WORDS or (bool(words) and all(w in SUPPORT_WORDS for w in words))


def pick_program(folder_name, progs, saved=None):
    """The program to run: the saved choice if it is still there, else the one that looks like the game
    (a name equal to the folder's, a single .bat, or the only file); else the first (shallowest).
    Support / order / cheat helpers (is_support) are only taken when nothing else is there."""
    if saved and saved in progs:
        return saved
    if not progs:
        return None
    stem = slug(folder_name)
    for p in progs:
        if slug(Path(p).stem) == stem:
            return p
    real = [p for p in progs if not is_support(p)] or list(progs)
    bats = [p for p in real if p.lower().endswith(".bat") and "/" not in p]
    if len(bats) == 1:
        return bats[0]
    return real[0]


def cover_of(folder):
    folder = Path(folder)
    try:                                   # any letter case: Cover.JPG
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.name.lower() in COVER_NAMES:
                return p
    except OSError:
        pass
    return None


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
def _unique(root, stem):
    n = 2
    while (root / f"{stem} ({n})").exists():
        n += 1
    return root / f"{stem} ({n})"


def unpack_zips(root, hide=None):
    """Unpack every .zip in root into a folder named like the zip, then move the zip to root/_zips
    (kept). A zip with one top folder inside is unpacked without that extra level. Refused: unsafe paths
    (../ or absolute), too little free space, anything the zip module can't read (old PKZIP methods,
    passwords): those zips are left where they are, with a line in the log. A zip whose folder already
    exists is skipped, unless that folder was removed from the library: then it comes back as a new
    folder "<name> (2)" (the old folder is never touched). Returns the folder names made."""
    root, made = Path(root), []
    hide = removed() if hide is None else hide
    try:
        zips = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".zip")
    except OSError:
        return made
    for z in zips:
        dest = root / z.stem
        if dest.exists():
            if z.stem not in hide:
                log.info("dosgames: %s skipped, the folder %s is already there", z.name, z.stem)
                continue
            dest = _unique(root, z.stem)                     # a removed game copied again
        tmp = root / (dest.name + ".unpacking")
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            with zipfile.ZipFile(z) as zf:
                infos = zf.infolist()
                names = [i.filename for i in infos if i.filename and not i.is_dir()]
                bad = [i.filename for i in infos if i.filename.startswith(("/", "\\"))
                       or ".." in Path(i.filename).parts or (len(i.filename) > 1 and i.filename[1] == ":")]
                if bad or not names:
                    log.info("dosgames: %s skipped (%s)", z.name, "unsafe paths" if bad else "empty")
                    continue
                need = sum(i.file_size for i in infos)
                free = shutil.disk_usage(root).free
                if need * SPACE_MARGIN > free:
                    log.info("dosgames: %s skipped (needs %d MB, %d MB free)", z.name, need // 10**6,
                             free // 10**6)
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
            made.append(dest.name)
            log.info("dosgames: unpacked %s", z.name)
        except Exception as e:  # noqa: BLE001  - old PKZIP methods (NotImplementedError), passwords
            log.info("dosgames: can't unpack %s: %s: %s", z.name, type(e).__name__, e)   # (RuntimeError)
            shutil.rmtree(tmp, ignore_errors=True)
    return made


# --- the scan ----------------------------------------------------------------------------------------
def scan(root, choices=None, hide=None, used=None):
    """Every game folder in root (after unpacking zips): [{"name", "id", "title", "dir", "exe",
    "programs", "cover", "image", "size"}]. choices = {game id: chosen program}; hide = removed().
    Reads and unpacks files only; touches no shared state, so it may run in a thread."""
    root, out = Path(root), []
    choices = choices or {}
    hide = removed() if hide is None else hide
    if not root.is_dir():
        return out
    unpack_zips(root, hide)
    try:
        folders = sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))
                          and not p.name.endswith(".unpacking")), key=lambda p: p.name.lower())
    except OSError:
        return out
    used = {} if used is None else used         # id -> folder: the same name twice gets two tiles

    def add(f, progs, image, size):
        gid = unique_id(f.name, f, used)
        if gid is None:
            return
        title, year = dosart.display(f.name)    # the shown title is tidy; the folder and the id stay as they are
        out.append({"name": f.name, "id": gid, "title": title, "year": year, "dir": str(f),
                    "exe": pick_program(f.name, progs, choices.get(gid)), "programs": progs,
                    "setups": list(SETUPS.get(str(f), [])),
                    "cover": cover_of(f), "image": image, "size": size})

    for f in folders:
        try:
            _scan_folder(f, hide, add)
        except Exception:  # noqa: BLE001  - one odd folder must not hide all the others
            log.exception("dosgames: %s skipped", f.name)
    return out


def _scan_folder(f, hide, add):
    """One top-level folder of the dos folder: a collection gives a tile per game inside, else one tile."""
    games = collection(f)                       # v0.9.25: DOS.zip with many games inside = many tiles
    if not games and _hidden(f, hide):          # (a mark left by removing the old single "DOS" tile
        return                                  # must not hide the games inside it)
    if games:
        log.info("dosgames: %s holds %d games, each gets its own tile", f.name, len(games))
        for sub, (progs, image, size) in games.items():
            if '"' in sub.name or _hidden(sub, hide):
                continue
            add(sub, progs, image, size)
        return
    if '"' in f.name:                           # DOSBox's mount command can't quote such a name
        log.info("dosgames: %s skipped, the folder name has a double quote", f.name)
        return
    progs, image, size = survey(f)
    if not progs:
        log.info("dosgames: %s has no .exe/.com/.bat, skipped", f.name)
        return
    add(f, progs, image, size)
