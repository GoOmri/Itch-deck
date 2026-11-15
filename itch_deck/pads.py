"""Which controller is in use, and what its buttons are called (glyphs + texts).

Under Steam every pad is a Steam virtual pad: the GUID vendor is always 28de (Valve), so it can't
tell a DualSense from the Deck (v0.7.1 Deck log). The NAME can: "Steam Deck Controller",
"DualSense Wireless Controller". A pad connected while we run is sometimes just "Steam Virtual
Gamepad"; then Steam's own list (env SteamVirtualGamepadInfo -> virtualgamepadinfo.txt, one
[slot N] per pad with type=steam/ps5/...) says which kinds exist, and the generic pads get the
kinds that no named pad has taken.

Kinds: "deck" (A B X Y, ⧉ View, ☰ Menu), "ps" (✕ ○ □ △, Create, Options), "xbox" (A B X Y, View,
Menu, LB RB LT RT; also the fallback for anything unknown).
"""
import logging
import os
import re

log = logging.getLogger("scritch")

KINDS = ("deck", "ps", "xbox")
LABEL = {"auto": "Auto", "deck": "Steam Deck", "ps": "PlayStation", "xbox": "Xbox"}
CHOICES = ("auto", "deck", "ps", "xbox")          # Settings → Button symbols, in cycle order

# Text names of the buttons (input action -> word), used in sentences ("A to check").
NAMES = {
    "deck": {"A": "A", "B": "B", "X": "X", "Y": "Y", "BACK": "View", "START": "Menu",
             "MENU": "Menu", "L1": "L1", "R1": "R1", "L2": "L2", "R2": "R2", "GUIDE": "Steam"},
    "ps": {"A": "Cross", "B": "Circle", "X": "Square", "Y": "Triangle", "BACK": "Create",
           "START": "Options", "MENU": "Options", "L1": "L1", "R1": "R1", "L2": "L2", "R2": "R2",
           "GUIDE": "PS"},
    "xbox": {"A": "A", "B": "B", "X": "X", "Y": "Y", "BACK": "View", "START": "Menu",
             "MENU": "Menu", "L1": "LB", "R1": "RB", "L2": "LT", "R2": "RT", "GUIDE": "Xbox"},
}

# Steam's type= values in virtualgamepadinfo.txt -> our kinds.
STEAM_TYPES = {"steam": "deck", "steamdeck": "deck", "ps3": "ps", "ps4": "ps", "ps5": "ps",
               "xbox360": "xbox", "xboxone": "xbox", "xboxelite": "xbox"}

current = "deck"        # what glyphs and texts show now (App sets it every frame)


def set_current(kind):
    global current
    current = kind if kind in KINDS else "deck"


def name(btn, kind=None):
    """Word for a button on the pad in use: name("A") -> "Cross" on a DualSense."""
    return NAMES[kind or current].get(btn, btn)


def kind_from_name(pad_name):
    """deck / ps / xbox from SDL's controller name, or None for Steam's generic virtual pad."""
    n = (pad_name or "").lower()
    if "steam deck" in n:
        return "deck"
    if re.search(r"dualsense|dualshock|playstation|\bps[345]\b|sony", n) or \
            n.strip() == "wireless controller":        # SDL's name for a DualShock 4
        return "ps"
    if "xbox" in n or "x-box" in n:
        return "xbox"
    if "steam virtual gamepad" in n or "steam controller" in n or not n:
        return None
    return "xbox"


def steam_slots(path=None):
    """Kinds of the pads Steam lists, in slot order ([] when the file isn't there)."""
    path = path or os.environ.get("SteamVirtualGamepadInfo")
    if not path:
        return []
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    out = []
    for block in re.split(r"^\[slot \d+\]\s*$", txt, flags=re.M)[1:]:
        m = re.search(r"^type=(\S+)", block, flags=re.M)
        if m:
            out.append(STEAM_TYPES.get(m.group(1).lower(), "xbox"))
    return out


def resolve(pads, slots, known=None, guessed=None):
    """pads: [(id, name)] in open order; slots: steam_slots(); known: {id: kind} already worked
    out (a pad keeps its kind: when the Deck pad goes, its slot must not pass to the DualSense).
    Named/known pads keep their kind; generic ones take Steam's kinds that are left over.
    Ids that had to fall back to "xbox" are added to `guessed` (worth asking again later).
    Returns {id: kind}."""
    known = known or {}
    kinds = {pid: known.get(pid) or kind_from_name(n) for pid, n in pads}
    left = list(slots)
    for k in kinds.values():
        if k in left:
            left.remove(k)
    for pid, k in kinds.items():
        if k is None:
            if left:
                kinds[pid] = left.pop(0)
            else:
                kinds[pid] = "xbox"
                if guessed is not None:
                    guessed.add(pid)
    return kinds


def pick(kinds, last=None):
    """Kind to show: the pad pressed last; before any press, a pad that isn't the Deck's own
    (someone with a DualSense on the TV uses that), else the Deck."""
    if last in kinds:
        return kinds[last]
    others = [k for k in kinds.values() if k != "deck"]
    return others[0] if others else "deck"
