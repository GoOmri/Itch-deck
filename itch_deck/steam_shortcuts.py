"""Read and write Steam's non-Steam shortcuts (shortcuts.vdf, binary VDF).  (v0.9.21, "Add to Steam")

Standalone on purpose: standard library only, no imports from this package, so the same file runs by
hand on a Deck:   python3 steam_shortcuts.py list | add | check | remove | where

SAFETY
- Before anything is written the file is copied to shortcuts.vdf.scritch-backup-<time>.
- Writes are atomic (temp file, then replace).
- Only shortcuts that carry the tag TAG ("SCRiTCH") are ever removed or changed; yours are not touched.
- Steam keeps its own copy in memory and rewrites the file when it exits, so the safe way to add a
  shortcut is to do it while Steam is closed. `add` says whether Steam is running. The test commands
  (add/check/remove) exist to learn what Steam does when it is running.

The binary format: 0x00 <key> starts a map, 0x01 <key> <string>, 0x02 <key> <int32 little endian>,
0x08 ends a map. The file is  00 "shortcuts" 00 <entries "0","1",...> 08 08."""
import os
import shutil
import struct
import sys
import time
import zlib
from pathlib import Path

TAG = "SCRiTCH"
TEST_NAME = "SCRiTCH test game (safe to delete)"
KEEP_BACKUPS = 5                 # shortcuts.vdf.scritch-backup-<time> files kept next to the file


# --- binary VDF: a list of (type, key, value), nested maps as lists ---------------------------------
def loads(data):
    pos = 0

    def cstr():
        nonlocal pos
        end = data.index(b"\x00", pos)
        s = data[pos:end].decode("utf-8", "surrogateescape")       # byte-exact, even for an old tool's Latin-1
        pos = end + 1
        return s

    def node():
        nonlocal pos
        out = []
        while pos < len(data):
            t = data[pos]
            pos += 1
            if t == 8:
                return out
            key = cstr()
            if t == 0:
                out.append((0, key, node()))
            elif t == 1:
                out.append((1, key, cstr()))
            elif t == 2:
                out.append((2, key, struct.unpack_from("<i", data, pos)[0]))
                pos += 4
            elif t == 7:
                out.append((7, key, struct.unpack_from("<Q", data, pos)[0]))
                pos += 8
            else:
                raise ValueError(f"unknown VDF type {t} at {pos - 1}")
        return out
    try:
        return node()
    except (struct.error, IndexError) as e:                      # a file cut off in the middle of a value
        raise ValueError(f"damaged shortcuts file: {e}") from None


def dumps(tree):
    out = bytearray()

    def put(nodes):
        for t, key, val in nodes:
            out.append(t)
            out.extend(key.encode("utf-8", "surrogateescape") + b"\x00")
            if t == 0:
                put(val)
                out.append(8)
            elif t == 1:
                out.extend(val.encode("utf-8", "surrogateescape") + b"\x00")
            elif t == 2:
                out.extend(struct.pack("<i", val))
            elif t == 7:
                out.extend(struct.pack("<Q", val))
    put(tree)
    out.append(8)
    return bytes(out)


def _field(entry, name):
    low = name.lower()
    for t, k, v in entry:
        if k.lower() == low:
            return v
    return None


def shortcuts_of(tree):
    """The entries of the "shortcuts" map: [(index key, [fields])]."""
    for t, k, v in tree:
        if t == 0 and k.lower() == "shortcuts":
            return [(ek, ev) for et, ek, ev in v if et == 0]
    return []


def tags_of(entry):
    for t, k, v in entry:
        if t == 0 and k.lower() == "tags":
            return [tv for tt, tk, tv in v if tt == 1]
    return []


def shortcut_appid(exe, name):
    """The shortcut's app id as Steam derives it: crc32(exe + name) with the top bit set (the art in
    config/grid/ is named after it). exe is the quoted Exe field, like Steam writes it."""
    return (zlib.crc32((exe + name).encode("utf-8")) & 0xFFFFFFFF) | 0x80000000


def make_entry(name, exe, start_dir=None, launch_options="", icon="", tags=(TAG,)):
    """A shortcut as Steam writes one. exe and start_dir are plain paths; they are quoted here."""
    qexe = f'"{exe}"'
    qdir = f'"{start_dir or os.path.dirname(exe) or "/"}"'
    appid = shortcut_appid(qexe, name)
    signed = appid - (1 << 32) if appid >= (1 << 31) else appid
    return [
        (2, "appid", signed), (1, "AppName", name), (1, "Exe", qexe), (1, "StartDir", qdir),
        (1, "icon", icon), (1, "ShortcutPath", ""), (1, "LaunchOptions", launch_options),
        (2, "IsHidden", 0), (2, "AllowDesktopConfig", 1), (2, "AllowOverlay", 1), (2, "OpenVR", 0),
        (2, "Devkit", 0), (1, "DevkitGameID", ""), (2, "DevkitOverrideAppID", 0),
        (2, "LastPlayTime", 0),
        (0, "tags", [(1, str(i), t) for i, t in enumerate(tags)]),
    ]


def add_shortcut(tree, entry):
    """Append entry to the shortcuts map (made if missing). Returns its index key."""
    for t, k, v in tree:
        if t == 0 and k.lower() == "shortcuts":
            nxt = max([int(ek) for et, ek, ev in v if et == 0 and ek.isdigit()] + [-1]) + 1
            v.append((0, str(nxt), entry))
            return str(nxt)
    tree.insert(0, (0, "shortcuts", [(0, "0", entry)]))
    return "0"


def remove_shortcuts(tree, only_tag=TAG, name=None, match=None):
    """Drop shortcuts that carry only_tag (and, when given, have this AppName and pass match(entry)).
    Returns how many.
    The rest is renumbered 0,1,2,... as Steam does."""
    for t, k, v in tree:
        if t == 0 and k.lower() == "shortcuts":
            keep, gone = [], 0
            for et, ek, ev in v:
                if et == 0 and only_tag in tags_of(ev) and (name is None or _field(ev, "AppName") == name) \
                        and (match is None or match(ev)):
                    gone += 1
                else:
                    keep.append((et, ek, ev))
            v[:] = [(et, str(i), ev) for i, (et, ek, ev) in enumerate(keep)]
            return gone
    return 0


# --- files --------------------------------------------------------------------------------------------
def steam_roots(home=None):
    home = Path(home or Path.home())
    seen, out = set(), []
    for p in (home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root"):
        try:
            r = p.resolve()
        except OSError:
            continue
        if r.is_dir() and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def shortcut_files(roots=None):
    """Every config/shortcuts.vdf (one per Steam user), existing or not (the user's folder counts)."""
    out = []
    for r in roots or steam_roots():
        ud = r / "userdata"
        if ud.is_dir():
            out += [u / "config" / "shortcuts.vdf" for u in sorted(ud.iterdir())
                    if u.is_dir() and u.name.isdigit() and u.name != "0"]
    return out


def read_file(path):
    path = Path(path)
    return loads(path.read_bytes()) if path.exists() and path.stat().st_size else []


def write_file(path, tree, backup=True):
    """Atomic write; the old file is kept as shortcuts.vdf.scritch-backup-<time> first."""
    path = Path(path)
    if backup and path.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() // 1_000_000 % 1000:03d}"
        shutil.copy2(path, path.with_name(f"{path.name}.scritch-backup-{stamp}"))
        old = sorted(path.parent.glob(path.name + ".scritch-backup-*"))      # keep the newest few only
        for b in old[:-KEEP_BACKUPS]:
            try:
                b.unlink()
            except OSError:
                pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".scritch-tmp")
    tmp.write_bytes(dumps(tree))
    os.replace(tmp, path)


def steam_running():
    """True when a 'steam' process exists (Linux /proc)."""
    try:
        for p in Path("/proc").iterdir():
            if p.name.isdigit():
                try:
                    if (p / "comm").read_text().strip() == "steam":
                        return True
                except OSError:
                    pass
    except OSError:
        pass
    return False


# --- command line: the Deck experiment -----------------------------------------------------------------
def _cmd_list(files):
    for f in files:
        print(f"\n{f}  ({f.stat().st_size if f.exists() else 0} bytes)")
        for k, e in shortcuts_of(read_file(f)):
            print(f"  [{k}] {_field(e, 'AppName')!r}  exe={_field(e, 'Exe')}  tags={tags_of(e)}")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "list"
    files = shortcut_files()
    if cmd == "where":
        print("Steam folders:", steam_roots() or "none found")
        print("shortcut files:", [str(f) for f in files] or "none found")
        print("Steam running:", steam_running())
        return 0
    if not files:
        print("No Steam user folder found. Run `where` and send me the output.")
        return 1
    if cmd == "list":
        _cmd_list(files)
        return 0
    if cmd == "verify":                      # read-only: can we read and write back YOUR file byte for byte?
        for f in files:
            if not f.exists():
                print(f, "-> no file yet")
                continue
            data = f.read_bytes()
            try:
                same = dumps(loads(data)) == data
            except (ValueError, IndexError, struct.error) as e:
                print(f, "-> CAN'T READ IT:", e)
                continue
            print(f, "->", "round trip OK (identical bytes)" if same else "DIFFERENT after a round trip, tell me")
        return 0
    if cmd == "check":
        print("Steam running:", steam_running())
        for f in files:
            names = [_field(e, "AppName") for k, e in shortcuts_of(read_file(f))]
            print(f, "->", "TEST SHORTCUT IS IN THE FILE" if TEST_NAME in names else "test shortcut NOT in the file",
                  f"({len(names)} shortcuts)")
        return 0
    if cmd == "add":
        print("Steam running:", steam_running(), "(this is what the experiment is about)")
        for f in files:
            tree = read_file(f)
            if TEST_NAME in [_field(e, "AppName") for k, e in shortcuts_of(tree)]:
                print(f, "-> already there")
                continue
            add_shortcut(tree, make_entry(TEST_NAME, "/usr/bin/true", "/usr/bin/"))
            write_file(f, tree)
            print(f, "-> test shortcut added (backup kept next to the file)")
        return 0
    if cmd == "remove":
        for f in files:
            tree = read_file(f)
            n = remove_shortcuts(tree, TAG, TEST_NAME)
            if n:
                write_file(f, tree)
            print(f, "->", f"removed {n} test shortcut(s)" if n else "no test shortcut there")
        return 0
    print("use: list | where | add | check | remove")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
