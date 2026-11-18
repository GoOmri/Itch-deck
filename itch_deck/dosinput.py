"""Find a DOS game's own keys in the text files that ship with it (readme, manual, help ...) and turn them into a
pad layout (v0.9.30). A DOS game cannot tell its keys at run time, but most come with a text that does.

Pure functions, read-only: the game's folder is never written to or changed. Plain text only (a file with NUL bytes
or many control characters is skipped), at most 300 KB per file and 1 MB in total, depth 2 folders down.

  find_docs(folder) -> the text files worth reading          scan(folder) -> {"sig", "source", "actions", "map", ...}
  extract(text) -> [(role, key, confidence)]                   to_layout(hits) -> {"map", "hints", "wasd", "actions"}

Roles: fire jump use pogo run strafe map menu confirm weapon_next weapon_prev crouch. The result has the same
shape as an entry of assets/dos_controls.json, so the Mapper can use it directly."""
import hashlib
import logging
import os
import re
from pathlib import Path

from . import keynames

log = logging.getLogger("scritch")

MAX_FILE = 300_000
MAX_TOTAL = 1_000_000
MAX_DEPTH = 2
MAX_LINES = 8000
MIN_CONF = 0.5                      # a hit below this is ignored
LAYOUT_CONF = 0.6                   # a role counts toward "found a layout" at this confidence
MIN_ROLES = 2                       # distinct actions needed for a layout from the files
DOC_EXT = (".txt", ".doc", ".1st", ".nfo", ".me", ".man", ".hlp", ".inf", ".asc")
DOC_START = ("readme", "read.me", "manual", "help", "instruct", "controls", "keys", "howto", "how2", "guide", "info")
SKIP_EXT = (".exe", ".com", ".bat", ".dll", ".bin", ".dat", ".zip", ".arj", ".lzh", ".gif", ".pcx", ".bmp", ".wav",
            ".voc", ".mid", ".mod", ".cfg", ".ovl", ".gfx", ".snd", ".tmp", ".sav", ".grp", ".wad", ".pak")

# --- reading ---------------------------------------------------------------------------------------------------
def find_docs(folder):
    """Text files in the game folder (depth <= 2), the most likely ones first. Read-only."""
    folder = Path(folder)
    found = []
    try:
        for dirpath, dirs, files in os.walk(folder, followlinks=False):
            depth = len(Path(dirpath).relative_to(folder).parts)
            if depth >= MAX_DEPTH:
                dirs[:] = []
            for f in files:
                low = f.lower()
                ext = os.path.splitext(low)[1]
                if ext in SKIP_EXT:
                    continue
                if ext in DOC_EXT or low.startswith(DOC_START):
                    p = Path(dirpath) / f
                    try:
                        if p.is_symlink() or not p.is_file():
                            continue
                        st = p.stat()
                    except OSError:
                        continue
                    best = low.startswith(DOC_START) or any(w in low for w in ("readme", "manual", "control", "keys"))
                    found.append((0 if best else 1, depth, low, p, st.st_size, int(st.st_mtime)))
    except OSError:
        pass
    found.sort(key=lambda r: r[:3])
    return [(r[3], r[4], r[5]) for r in found]


def signature(folder):
    """Changes when a doc file is added, removed or edited (names, sizes, mtimes)."""
    parts = [f"{p.relative_to(folder).as_posix()}|{size}|{mt}" for p, size, mt in find_docs(folder)]
    return hashlib.sha1("\n".join(parts).encode("utf-8", "replace")).hexdigest()[:16]


def read_text(path, cap=MAX_FILE):
    """The file as ASCII-ish text (box drawing and other high characters become spaces), or None when it is not
    plain text. cp437 first (DOS), which also reads latin-1 files well enough for key words."""
    try:
        with open(path, "rb") as f:
            data = f.read(cap)
    except OSError:
        return None
    if not data or b"\x00" in data[:4096]:
        return None
    ctrl = sum(1 for b in data[:20000] if b < 32 and b not in (9, 10, 13, 12, 26, 27) or b == 127)
    if ctrl > 0.05 * min(len(data), 20000):
        return None
    try:
        text = data.decode("cp437")
    except UnicodeDecodeError:
        text = data.decode("latin-1", "replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[^\x20-\x7e\t\n]", " ", text)


# --- understanding ----------------------------------------------------------------------------------------------
_NAMED = (r"(?:(?:left|right|l|r)[ .]?)?(?:ctrl|control|ctl|alt|shift|space[ ]?bar|spacebar|space|enter|return|esc|"
          r"escape|tab|f(?:1[0-2]|[1-9]))")
_KEYTOK = rf"(?:{_NAMED}|[A-Za-z0-9])"
_SEP = r"(?:=>|->|=|:|\.{2,}|--|-|–|—)"
_NOT_CONTROLS = re.compile(r"(?i)\b(cheat|code|god ?mode|invincib|iddqd|idkfa|password|any key|install|setup|registration|"
                           r"order|price|copy|diskette|floppy|memory|ram\b|sound ?blaster|config|modem|"
                           r"save game|load game|type)\b")
CLAUSE_SPLIT = re.compile(r"\s*[,;|]\s*|\s+and\s+")


def norm_key(tok):
    """A key as written -> a name in keynames.CODES, or None (arrows, unknown, F11/F12 ...)."""
    t = re.sub(r"[ .]", "", str(tok).lower())
    t = re.sub(r"^(left|right|l|r)(?=ctrl|control|ctl|alt|shift)", "", t)
    t = {"control": "ctrl", "ctl": "ctrl", "spacebar": "space", "return": "enter", "escape": "esc"}.get(t, t)
    t = t.replace("spacebar", "space")
    return t if t in keynames.CODES else None


def classify(action):
    """What a key does, from the words around it: a role or None."""
    a = " " + re.sub(r"[^a-z0-9]+", " ", str(action).lower()) + " "
    if re.search(r" (next|forward) (weapon|gun)| (weapon|gun) (next|up) ", a):
        return "weapon_next"
    if re.search(r" (prev|previous|last|back) (weapon|gun)| (weapon|gun) (prev|previous|down) ", a):
        return "weapon_prev"
    if re.search(r" (change|select|switch|cycle) (weapons?|guns?) ", a):
        return "weapon_next"
    for role, words in (("pogo", ("pogo",)), ("jump", ("jump", "leap")),
                        ("fire", ("fire", "shoot", "attack", "gun", "blast", "laser", "raygun", "ray gun", "zap")),
                        ("use", ("open", "use", "activate", "door", "switch", "action", "operate", "talk", "push")),
                        ("run", ("run", "speed", "fast", "sprint")),
                        ("strafe", ("strafe", "sidestep", "side step", "slide")),
                        ("map", ("automap", "map", "overhead")),
                        ("menu", ("menu", "pause", "quit", "escape")),
                        ("crouch", ("crouch", "duck", "sneak")),
                        ("confirm", ("confirm", "accept", "select"))):
        if any(f" {w} " in a or f" {w}s " in a or f" {w}ing " in a for w in words):
            return role
    return None


def _clause_hits(c):
    """[(role, key, confidence)] from one clause of a line."""
    c = c.strip(" \t.*-•>|#")
    if not c or len(c) > 90:
        return []
    out = []

    def add(key, action, conf):
        k, role = norm_key(key), classify(action)
        if role == "menu" and k == "enter":        # "Enter picks a menu entry" is the confirm key, not the menu key
            role = "confirm"
        if k and role:
            out.append((role, k, conf))

    m = re.search(rf"(?i)\b(?:press|hit|hold|use|push|tap)\s+(?:the\s+)?(?:key\s+)?({_KEYTOK})(?:\s+key)?\s+(?:to|for)\s+(.+)", c)
    if m:
        add(m.group(1), m.group(2), 0.8)
        return out
    m = re.match(rf"(?i)^({_KEYTOK})\s*{_SEP}\s*(.+)$", c)
    if m:
        add(m.group(1), m.group(2), 0.9)
        if out:
            return out
    m = re.match(rf"(?i)^(.+?)\s*{_SEP}\s*({_KEYTOK})\s*$", c)
    if m:
        add(m.group(2), m.group(1), 0.9)
        if out:
            return out
    m = re.match(rf"(?i)^({_NAMED})\s{{2,}}(.+)$", c)
    if m:
        add(m.group(1), m.group(2), 0.7)
        if out:
            return out
    m = re.match(rf"(?i)^(.+?)\s{{2,}}({_NAMED})\s*$", c)
    if m:
        add(m.group(2), m.group(1), 0.7)
        if out:
            return out
    m = re.match(rf"(?i)^({_NAMED})\s+(?:to|for)\s+(.+)$", c)
    if m:
        add(m.group(1), m.group(2), 0.6)
        if out:
            return out
    m = re.match(rf"(?i)^({_NAMED})\s+(.+)$", c)
    if m:
        add(m.group(1), m.group(2), 0.6)
    return out


def extract(text):
    """[(role, key, confidence)] for every control found in a text; the best hit per (role) is kept by the caller."""
    hits = []
    for n, line in enumerate(str(text).split("\n")):
        if n >= MAX_LINES:
            break
        if not line.strip() or _NOT_CONTROLS.search(line):
            continue
        clauses = []
        if len(line) < 160:                         # two key phrases on one line, far apart: "CTRL fire     TAB map"
            for part in re.split(rf"(?i)\s{{3,}}(?={_NAMED}\b)", line):
                clauses += CLAUSE_SPLIT.split(part)
        if len(clauses) > 1:
            for c in clauses:                       # "Ctrl = jump, Alt = pogo stick": a pair per clause
                hits += _clause_hits(c)
        else:
            hits += _clause_hits(line)
    return [h for h in hits if h[2] >= MIN_CONF]


def wasd_found(text):
    """True when the text lists W A S D as movement keys."""
    mv = 0
    for m in re.finditer(r"(?im)\b([wasd])\b\s*(?:=|:|-|–)\s*(?:move|walk|go|turn|strafe|forward|back|backward|left|right|up|down)", str(text)):
        mv += 1
    return mv >= 3 or bool(re.search(r"(?i)\bw\W{0,3}a\W{0,3}s\W{0,3}d\b\s*(?:keys?|to move|=\s*move|:)", str(text)))


# role -> buttons in order of preference; roles are given buttons in this order, first free button wins
ROLE_ORDER = ("fire", "jump", "use", "pogo", "run", "menu", "confirm", "weapon_next", "weapon_prev", "strafe", "map", "crouch")
PREFER = {"fire": ("a", "b"), "jump": ("b", "a", "x"), "use": ("x", "y"), "pogo": ("x", "y", "b"), "run": ("l1", "r1"),
          "menu": ("start",), "confirm": ("y",), "weapon_next": ("r1", "r2"), "weapon_prev": ("l1", "l2"),
          "strafe": ("l2", "r2"), "map": ("r2", "back"), "crouch": ("l2", "r2", "back")}
WORDS = {"fire": "Fire", "jump": "Jump", "use": "Open / use", "pogo": "Pogo stick", "run": "Run", "menu": "Menu",
         "confirm": "Menu select", "weapon_next": "Next weapon", "weapon_prev": "Previous weapon",
         "strafe": "Sidestep (hold)", "map": "Map", "crouch": "Crouch"}
BUTTON_ORDER = ("a", "b", "x", "y", "l1", "r1", "l2", "r2", "start", "back")


def to_layout(hits, wasd=False):
    """Roles -> buttons by the fixed priority. Returns {"map", "hints", "wasd", "actions", "layout"} or None when
    fewer than MIN_ROLES distinct actions were found with decent confidence."""
    best = {}
    for role, key, conf in hits:
        if role not in best or conf > best[role][1]:
            best[role] = (key, conf)
    good = {r: v for r, v in best.items() if v[1] >= LAYOUT_CONF}
    if len(good) < MIN_ROLES:
        return None
    if "fire" not in good and "jump" in good:        # no fire: jump takes A
        order = ("jump",) + tuple(r for r in ROLE_ORDER if r != "jump")
    else:
        order = ROLE_ORDER
    used, bmap, roles = set(), {}, {}
    for role in order:
        if role not in good:
            continue
        prefs = PREFER[role]
        if role == "jump" and "fire" not in good:
            prefs = ("a", "b", "x")
        for b in prefs:
            if b not in used:
                used.add(b)
                bmap[b] = good[role][0]
                roles[b] = role
                break
    if "start" not in bmap:
        bmap["start"], roles["start"] = "esc", "menu"          # a menu button always
    if "y" not in bmap:
        bmap["y"], roles["y"] = "enter", "confirm"
    hints = [[b.upper(), WORDS[roles[b]]] for b in BUTTON_ORDER if b in bmap]
    if wasd:
        bmap.update({"up": "w", "left": "a", "down": "s", "right": "d"})
        hints.insert(0, ["DPAD", "Move (W A S D)"])
    return {"map": bmap, "hints": hints, "wasd": bool(wasd), "actions": len(good), "layout": "keys"}


def scan(folder):
    """Read the game's text files and build a layout. Always returns a dict with "sig"; "map" is there only when
    the files gave a layout. Never raises, never writes."""
    folder = Path(folder)
    out = {"sig": ""}
    try:
        out["sig"] = signature(folder)
        total, per_file = 0, []
        alltext = []
        for p, size, _mt in find_docs(folder):
            if total >= MAX_TOTAL:
                break
            text = read_text(p)
            if text is None:
                continue
            total += min(size, MAX_FILE)
            hits = extract(text)
            if hits:
                per_file.append((len({h[0] for h in hits}), p.name, hits))
            alltext.append(text)
        if not per_file:
            return out
        merged = [h for _n, _name, hs in per_file for h in hs]
        lay = to_layout(merged, wasd=any(wasd_found(t) for t in alltext))
        if lay:
            lay["source"] = max(per_file)[1]
            out.update(lay)
    except Exception:  # noqa: BLE001  - a strange file must never stop anything
        log.exception("dosinput: scan of %s failed", folder.name)
    return out
