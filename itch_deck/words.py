"""What the player reads when something goes wrong: a few plain words, never a technical reason.

Omri (15 Nov): SCRiTCH is for casual players. No long lines, no terms like "runnable file",
"installer", "library", "Proton". The full reason always goes to app.log; the screen gets at most
a short hint the player can act on, or nothing.

Error codes (Omri 16 Nov, instead of the Details log view): when there's no hint the player can act
on, the screen shows a short code ("Code W09") and the log gets the same code on its own line
("ERROR CODE W09: …"), so a code a player reports leads straight to what happened. No codes on
errors that already say what to do. Every code is listed once in CODES.
"""
import logging

log = logging.getLogger("scritch")

# code -> what it means (for us; the player only sees the code). Letter = where it happened.
CODES = {
    # I = install
    "I01": "install: unexpected error (traceback in the log)",
    "I02": "itch: no Linux or Windows download for this game",
    "I03": "itch: install started without an itch key",
    "I04": "Epic: legendary couldn't install the game",
    # W = Windows games, GE-Proton, umu-launcher
    "W01": "umu-launcher: no download found in its GitHub release",
    "W02": "GE-Proton: no download found in its GitHub release",
    "W03": "GE-Proton: download damaged (checksum)",
    "W04": "GE-Proton: archive has unsafe paths",
    "W05": "GE-Proton: archive has an unexpected layout",
    "W06": "umu-launcher: archive has no umu-run",
    "W07": "Windows installer: couldn't start",
    "W08": "Windows installer: didn't finish in 15 min",
    "W09": "Windows installer: stopped with an error",
    "W10": "Windows installer: GE-Proton or umu-launcher missing at install time",
    "W11": "GE-Proton: unexpected error while getting it (Settings)",
    # P = play
    "P01": "game: closed straight away, no known hint",
    "P02": "Mouse or Keys mode didn't start",
    # L = library
    "L01": "library: refresh failed (not offline, not the key)",
    # U = app update
    "U01": "app update: download failed",
    # M = move a game (SD card <-> internal)
    "M01": "move: unexpected error (traceback in the log)",
    "M02": "move: a folder with the same name is already in use there",
    "M03": "move: the copy didn't match the original (old copy kept)",
    # S = save backups
    "S01": "save backup: couldn't write the backup",
    "S02": "save backup: couldn't restore",
}


class Coded(Exception):
    """An error with a code from CODES (None = it already says what to do)."""

    def __init__(self, msg, code=None):
        super().__init__(msg)
        assert code is None or code in CODES, code
        self.code = code


def log_code(code, reason):
    """The code on its own line in app.log, with the full reason."""
    log.error("ERROR CODE %s: %s", code, reason)


def with_code(msg, code):
    """'Couldn't refresh the library.' + L01 -> 'Couldn't refresh the library · Code L01'"""
    return f"{msg.rstrip('.')} · Code {code}"

# (words in the technical reason, what the player reads) - first match wins
_HINTS = (
    ("SD card missing", "SD card missing"),
    ("space", "Not enough space"),
    ("Can't write to", "Storage is full or read-only"),
    ("connection", "No internet"),
    ("online", "No internet"),
    ("No internet", "No internet"),
    ("API key", "Sign in to itch again"),
    ("Signed out of Epic", "Connect Epic again"),
    ("Connect Epic Games", "Connect Epic again"),
    # the build itself is the problem: another build usually works (⚙ Options → Change build)
    ("program to run", "Try another build in Options"),
    ("couldn't be unpacked", "Try another build in Options"),
    ("aren't supported", "Try another build in Options"),
    ("unsafe file paths", "Try another build in Options"),
    ("can't run silently", "Try another build in Options"),
    ("isn't in your library", "Refresh your library"),
)


def short(reason):
    """A technical reason -> a hint of a few words the player can act on, or None."""
    low = (reason or "").lower()
    return next((say for needle, say in _HINTS if needle.lower() in low), None)
