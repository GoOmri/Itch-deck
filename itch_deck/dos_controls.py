"""Per-game controller keys for DOS games (v0.9.30). DOS games expect a keyboard and a mouse; each game uses its
own keys (Ctrl jumps in Keen, Ctrl fires in Doom ...). assets/dos_controls.json lists, for the games we know, which
pad button presses which key and the plain-words lines the game page shows. A game without an entry gets the
default layout below. Everything here is non-fatal: a missing or broken file, or a broken entry, is logged once and
the default is used."""
import json
import logging
from pathlib import Path

from . import keynames

log = logging.getLogger("scritch")

FILE = Path(__file__).parent / "assets" / "dos_controls.json"
BUTTONS = ("a", "b", "x", "y", "l1", "r1", "l2", "r2", "start", "back")
DIRS = ("up", "down", "left", "right")             # in a map: the key the D-pad / left stick presses (default arrows)
HINT_BUTTONS = tuple(b.upper() for b in BUTTONS) + ("DPAD", "RSTICK")
LAYOUTS = ("keys", "keys+mouse", "mouse")          # in the file; "keys" = no pointer, "keys+mouse" = right stick too
MAP_LAYOUT = {"keys": "keys", "keys+mouse": "keysmouse", "mouse": "mouse"}

# no entry for the game: left stick + D-pad = arrows, A Ctrl, B Alt, X Space, Y Enter, L1 Shift, R1 Tab,
# Menu = Esc, right stick + R2 / L2 = the mouse (as the old Keys layout)
DEFAULT = {"name": "Default", "layout": "keys+mouse", "verified": True, "note": "",
           "map": {"a": "ctrl", "b": "alt", "x": "space", "y": "enter", "l1": "shift", "r1": "tab", "start": "esc"},
           "hints": [["A", "Ctrl"], ["B", "Alt"], ["X", "Space"], ["Y", "Enter"], ["L1", "Shift"], ["R1", "Tab"],
                     ["START", "Esc"]]}

_cache = {"entries": None}
_warned = set()


def _warn_once(key, msg, *a):
    if key not in _warned:
        _warned.add(key)
        log.warning(msg, *a)


def problems(entry):
    """What is wrong with one entry (a list of short texts); [] when it is fine."""
    bad = []
    if not isinstance(entry, dict):
        return ["not an object"]
    names = entry.get("names")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) and n.strip() for n in names):
        bad.append("names")
    if entry.get("layout") not in LAYOUTS:
        bad.append("layout")
    m = entry.get("map")
    if not isinstance(m, dict):
        bad.append("map")
        m = {}
    for b, k in m.items():
        if b not in BUTTONS and b not in DIRS:
            bad.append(f"button {b}")
        if k not in keynames.CODES:
            bad.append(f"key {k}")
    hints = entry.get("hints")
    if not isinstance(hints, list) or not hints:
        bad.append("hints")
        hints = []
    for h in hints:
        if not (isinstance(h, list) and len(h) == 2 and h[0] in HINT_BUTTONS and isinstance(h[1], str) and h[1].strip()):
            bad.append(f"hint {h}")
    if "not" in entry and not (isinstance(entry["not"], list) and all(isinstance(n, str) for n in entry["not"])):
        bad.append("not")
    if not isinstance(entry.get("verified", False), bool):
        bad.append("verified")
    return bad


def _words(title):
    """A title as lower-case words with sequel numbers as digits ("Doom II" -> doom 2)."""
    from . import dosart
    ws = dosart.parse(str(title or ""))["words"]
    return [str(dosart.ROMAN[w]) if i and w in dosart.ROMAN else w for i, w in enumerate(ws)]


def load():
    """The valid entries of the file (each gets "_names": normalised word lists). Cached; never raises."""
    if _cache["entries"] is not None:
        return _cache["entries"]
    out = []
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        items = data.get("games") if isinstance(data, dict) else data
        for i, e in enumerate(items or []):
            bad = problems(e)
            if bad:
                _warn_once(("entry", i), "dos controls: entry %d (%s) skipped: %s", i,
                           (e or {}).get("id") if isinstance(e, dict) else "?", ", ".join(bad))
                continue
            e = dict(e, _names=[_words(n) for n in e["names"]], _not=[_words(n) for n in e.get("not") or []])
            out.append(e)
    except (OSError, ValueError) as err:
        _warn_once("file", "dos controls: %s unreadable (%s): every DOS game gets the default keys", FILE.name, err)
    _cache["entries"] = out
    return out


def reset():
    _cache["entries"] = None
    _warned.clear()


def match(title):
    """The entry for a game title, or None. A name matches when the title STARTS with its words and the next
    word is not another sequel number ("doom" is not "doom 3"); the longest matching name wins."""
    words = _words(title)
    best, best_len = None, 0
    for e in load():
        if any(words[:len(v)] == v for v in e["_not"] if v):          # "dave the diver" is not Dangerous Dave
            continue
        for n in e["_names"]:
            if not n or words[:len(n)] != n or len(n) <= best_len:
                continue
            nxt = words[len(n)] if len(words) > len(n) else ""
            if nxt.isdigit() and len(nxt) <= 2:
                continue
            best, best_len = e, len(n)
    return best


def is_dos(g):
    """Own DOS games and GOG's DOS games (both run in DOSBox)."""
    return bool(g.get("dos") or g.get("store") == "dos")


def label(button, name_of):
    """Words for a hint's button on the pad in use. name_of = pads.name (Cross / Circle on a DualSense)."""
    return {"DPAD": "D-pad", "RSTICK": "Right stick"}.get(button) or name_of(button)


def hint_text(hints, name_of, limit=None):
    """"A Fire  ·  B Open doors" in plain words, with the names of the pad in use."""
    items = [f"{label(b, name_of)} {t}" for b, t in hints[:limit]]
    return "  ·  ".join(items)


SOURCE_TEXT = {"files": "From the game's own files. A key may be wrong.",
               "list": "From our list. Not tested, so a key may be wrong.",
               "verified": "", "default": "Controls are a guess. Some keys may be wrong."}
HINT_ORDER = ("DPAD", "RSTICK", "A", "B", "X", "Y", "L1", "R1", "L2", "R2", "START", "BACK")


def extracted_ok(x):
    """A dosinput.scan() result that holds a usable layout."""
    return bool(isinstance(x, dict) and isinstance(x.get("map"), dict) and x["map"] and x.get("hints")
                and all(k in keynames.CODES for k in x["map"].values()))


def _overlay(base, found):
    """The game's own files on top of the table entry (or the default): only the buttons the files named a real
    action for are replaced, everything else (Esc on Start, Enter on Y, the mouse ...) stays from the base."""
    keymap = dict(base["map"])
    keymap.update(found["map"])
    hints = {h[0]: list(h) for h in base["hints"]}
    for h in found["hints"]:
        hints[h[0]] = list(h)
    return {"layout": "keys+mouse", "map": keymap, "name": "files",
            "hints": [hints[b] for b in HINT_ORDER if b in hints]}


def plan(g, setting="auto", extracted=None):
    """What SCRiTCH does with the pad for a DOS game. setting = the game's Controls row: auto | gamepad | mouse |
    keys. extracted = dosinput.scan() of the game's own text files (or None). Source order: a verified entry of the
    list, else the table entry or the default with the buttons the game's files named put on top (never for a
    point-and-click entry), else an untested list entry, else the default.
    Returns {"eff": "gamepad"|"keys"|"mouse", "layout": the Mapper layout or None, "keymap": {...} or None,
    "hints": [[button, text]...] or None, "verified": bool, "source": files|list|verified|default,
    "source_text": plain words, "name": str}."""
    entry = match(g.get("title"))
    if setting == "gamepad":
        return {"eff": "gamepad", "layout": None, "keymap": None, "hints": None, "verified": True, "name": "",
                "source": "default", "source_text": ""}
    if setting == "mouse":                                   # forced: the plain mouse layout of every game
        return {"eff": "mouse", "layout": "mouse", "keymap": None, "hints": None, "verified": True, "name": "",
                "source": "default", "source_text": ""}
    if entry and setting != "auto" and entry["layout"] == "mouse":
        entry = None                                         # forced Keys on a point-and-click game
    if entry and entry.get("verified") is True:
        use, source = entry, "verified"
    elif extracted_ok(extracted) and not (entry and entry["layout"] == "mouse"):
        use, source = _overlay(entry or DEFAULT, extracted), "files"
    elif entry:
        use, source = entry, "list"
    else:
        use, source = DEFAULT, "default"
    layout = MAP_LAYOUT[use["layout"]]
    return {"eff": "mouse" if layout == "mouse" else "keys", "layout": layout, "keymap": dict(use["map"]),
            "hints": [list(h) for h in use["hints"]], "verified": source == "verified",
            "source": source, "source_text": SOURCE_TEXT[source],
            "name": use.get("name") or use.get("id") or "", "note": use.get("note") or ""}
