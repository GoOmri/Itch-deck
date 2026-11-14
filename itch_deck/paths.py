"""Every on-disk location in one place."""
import os
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "itch-deck"
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "itch-deck"
LOGS = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "itch-deck" / "logs"

CONFIG_FILE = CONFIG / "config.json"
LIBRARY = DATA / "library.json"
COVERS = DATA / "covers"
PAGES = DATA / "pages"        # cached itch page details (description, comments) per game
SHOTS = DATA / "shots"        # downscaled screenshots per game
KEY_FILE = HOME / "Downloads" / "itch_key.txt"
STEAM_TOOLS = HOME / ".steam" / "root" / "compatibilitytools.d"


def use_root(root):
    """Point every path inside `root` (selftest/tests: never touch the real config or cache)."""
    global HOME, CONFIG, DATA, LOGS, CONFIG_FILE, LIBRARY, COVERS, PAGES, SHOTS, KEY_FILE, STEAM_TOOLS
    HOME = Path(root)
    CONFIG, DATA, LOGS = HOME / "config", HOME / "data", HOME / "logs"
    CONFIG_FILE, LIBRARY = CONFIG / "config.json", DATA / "library.json"
    COVERS, PAGES, SHOTS = DATA / "covers", DATA / "pages", DATA / "shots"
    KEY_FILE = HOME / "Downloads" / "itch_key.txt"
    STEAM_TOOLS = HOME / "compatibilitytools.d"
