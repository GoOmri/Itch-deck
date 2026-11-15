"""What the player reads when something goes wrong: a few plain words, never a technical reason.

Omri (15 Nov): SCRiTCH is for casual players. No long lines, no terms like "runnable file",
"installer", "library", "Proton". The full reason always goes to app.log; the screen gets at most
a short hint the player can act on, or nothing.
"""

# (words in the technical reason, what the player reads) - first match wins
_HINTS = (
    ("SD card missing", "SD card missing"),
    ("space", "Not enough space"),
    ("Can't write to", "Storage is full or read-only"),
    ("connection", "No internet"),
    ("online", "No internet"),
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
