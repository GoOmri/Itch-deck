"""Small things shared by app.py and its parts (app_*.py)."""

QUIT_DLG = ("confirm", "Quit SCRiTCH?", "Downloads in progress pause and resume next time.",
            [("A", "Quit"), ("B", "Cancel")])
LATER = "Comes in a later update."

def _gb(n):
    return f"{n / 1e9:.0f} GB" if n >= 10e9 else f"{n / 1e9:.1f} GB"
