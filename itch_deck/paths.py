"""Every on-disk location in one place."""
import os
from pathlib import Path

HOME = Path.home()
NAME, OLD_NAME = "scritch", "itch-deck"   # folder names (v0.8.2 renamed them, see migrate())
_BASES = {"CONFIG": Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")),
          "DATA": Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")),
          "LOGS": Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state"))}
CONFIG = _BASES["CONFIG"] / NAME
DATA = _BASES["DATA"] / NAME
LOGS = _BASES["LOGS"] / NAME / "logs"

CONFIG_FILE = CONFIG / "config.json"
LIBRARY = DATA / "library.json"
COVERS = DATA / "covers"
PAGES = DATA / "pages"        # cached itch page details (description, comments) per game
SHOTS = DATA / "shots"        # downscaled screenshots per game
INSTALLS = DATA / "installed.json"   # game id -> install folder, exe (index of install.json files)
QUEUE = DATA / "queue.json"          # download queue, resumed at next launch
PLAYED = DATA / "played.json"        # game id -> last time played (Library "Recent" tab)
HLTB = DATA / "hltb.json"            # game id -> HowLongToBeat hours (time to beat)
BUILDS = DATA / "builds.json"        # game id -> upload id chosen with Change build
UMU = DATA / "umu" / "umu-run"       # umu-launcher zipapp (downloaded on the first Windows install)
KEY_FILE = HOME / "Downloads" / "itch_key.txt"
STEAM_TOOLS = HOME / ".steam" / "root" / "compatibilitytools.d"
_LOCK = []                           # open lock file of the running copy (kept for its lifetime)


def lock_instance():
    """Only ONE copy may run: two copies write the same caches (v0.7.1 Deck log: two started 4 s
    apart after an update restart -> every hltb.json write raced). flock is released by the
    kernel when the process dies or exec()s (fd is close-on-exec), so the updater's execve
    restart re-takes it cleanly. Returns None when we own the lock, else the other copy's pid
    text ("?" if unknown)."""
    import fcntl
    DATA.mkdir(parents=True, exist_ok=True)
    f = open(DATA / "scritch.lock", "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.seek(0)
        other = f.read().strip() or "?"
        f.close()
        return other
    f.seek(0)
    f.truncate()
    f.write(str(os.getpid()))
    f.flush()
    _LOCK[:] = [f]
    return None


def migrate(bases=None):
    """v0.8.2: the folders were called itch-deck, now scritch. Run at start, before anything
    opens a file. For each of config / data / state: old folder there and new one not -> rename
    (same disk, so nothing is copied and no space is needed), then leave a link at the old name
    pointing to the new one, so an older version (rollback) still finds everything. If the
    rename fails, keep using the old folder this run and try again next start. Returns lines
    for the log (logging isn't set up yet when this runs)."""
    global CONFIG, DATA, LOGS, CONFIG_FILE
    notes = []
    for key, base in (bases or _BASES).items():
        old, new = base / OLD_NAME, base / NAME
        try:
            if old.is_symlink() or not old.is_dir():
                continue                  # nothing to move, or already moved (old = our link)
            if new.exists():
                notes.append(f"folders: both {old} and {new} exist, using {new}")
                continue
            os.rename(old, new)
            notes.append(f"folders: moved {old} -> {new}")
        except OSError as e:
            notes.append(f"folders: couldn't move {old} ({e}), using it as it is")
            if bases is None:
                inner = old / "logs" if key == "LOGS" else old
                globals()[key] = inner
                CONFIG_FILE = CONFIG / "config.json"
                _repoint()
            continue
        try:
            old.symlink_to(NAME)          # relative link: itch-deck -> scritch
        except OSError as e:
            notes.append(f"folders: no link at {old} ({e})")
    return notes


def _repoint():
    """Recompute the files inside DATA after DATA changed (migrate fallback)."""
    global LIBRARY, COVERS, PAGES, SHOTS, INSTALLS, QUEUE, PLAYED, HLTB, BUILDS, UMU
    LIBRARY, COVERS, PAGES, SHOTS = DATA / "library.json", DATA / "covers", DATA / "pages", DATA / "shots"
    INSTALLS, QUEUE, PLAYED = DATA / "installed.json", DATA / "queue.json", DATA / "played.json"
    HLTB, BUILDS, UMU = DATA / "hltb.json", DATA / "builds.json", DATA / "umu" / "umu-run"


def tmp_for(path):
    """A temp name next to `path` that no other thread or process uses (atomic replace)."""
    import threading
    path = Path(path)
    return path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")


def use_root(root):
    """Point every path inside `root` (selftest/tests: never touch the real config or cache)."""
    global HOME, CONFIG, DATA, LOGS, CONFIG_FILE, LIBRARY, COVERS, PAGES, SHOTS, KEY_FILE, STEAM_TOOLS, \
        INSTALLS, QUEUE, BUILDS, UMU, PLAYED, HLTB
    HOME = Path(root)
    CONFIG, DATA, LOGS = HOME / "config", HOME / "data", HOME / "logs"
    CONFIG_FILE, LIBRARY = CONFIG / "config.json", DATA / "library.json"
    COVERS, PAGES, SHOTS = DATA / "covers", DATA / "pages", DATA / "shots"
    INSTALLS, QUEUE = DATA / "installed.json", DATA / "queue.json"
    PLAYED, HLTB = DATA / "played.json", DATA / "hltb.json"
    BUILDS, UMU = DATA / "builds.json", DATA / "umu" / "umu-run"
    KEY_FILE = HOME / "Downloads" / "itch_key.txt"
    STEAM_TOOLS = HOME / "compatibilitytools.d"
