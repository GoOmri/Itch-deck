"""Every on-disk location in one place."""
import os
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "itch-deck"
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "itch-deck"
LOGS = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "itch-deck" / "logs"
