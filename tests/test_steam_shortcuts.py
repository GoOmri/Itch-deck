"""steam_shortcuts.py: Steam's non-Steam shortcut file (binary VDF). Round trip, add, remove only our own,
backup and atomic write. The file is standalone (run by hand on a Deck), so it is also run as a script."""
import struct
import subprocess
import sys
from pathlib import Path

from itch_deck import steam_shortcuts as S

SCRIPT = Path(S.__file__)


def _raw():
    """A shortcuts.vdf built by hand, byte by byte, the way Steam writes it (not through dumps)."""
    def entry(idx, appid, name, exe, tags):
        b = b"\x00" + idx.encode() + b"\x00"
        b += b"\x02appid\x00" + struct.pack("<i", appid)
        b += b"\x01AppName\x00" + name.encode() + b"\x00"
        b += b"\x01exe\x00" + exe.encode() + b"\x00"              # old Steam wrote lower-case keys
        b += b"\x02IsHidden\x00" + struct.pack("<i", 0)
        b += b"\x00tags\x00"
        for i, t in enumerate(tags):
            b += b"\x01" + str(i).encode() + b"\x00" + t.encode() + b"\x00"
        b += b"\x08"                                               # end of tags
        b += b"\x08"                                               # end of this shortcut
        return b
    body = entry("0", -1234, "Mine", '"/home/deck/mine"', ["Favorite"]) + \
        entry("1", -77, "Also mine", '"/usr/bin/other"', [])
    return b"\x00shortcuts\x00" + body + b"\x08" + b"\x08"


def test_round_trip_is_byte_for_byte():
    raw = _raw()
    assert S.dumps(S.loads(raw)) == raw
    names = [S._field(e, "AppName") for k, e in S.shortcuts_of(S.loads(raw))]
    assert names == ["Mine", "Also mine"]
    assert S.tags_of(S.shortcuts_of(S.loads(raw))[0][1]) == ["Favorite"]


def test_app_id_is_the_signed_steam_id():
    e = S.make_entry("Game", "/opt/g/run", "/opt/g")
    appid = S.shortcut_appid('"/opt/g/run"', "Game")
    assert appid >= 1 << 31 and S._field(e, "appid") == appid - (1 << 32)      # stored as a signed int32
    assert S._field(e, "Exe") == '"/opt/g/run"' and S._field(e, "StartDir") == '"/opt/g"'
    assert S.tags_of(e) == ["SCRiTCH"]
    assert S.dumps(S.loads(S.dumps([(0, "shortcuts", [(0, "0", e)])]))) == S.dumps([(0, "shortcuts", [(0, "0", e)])])


def test_add_goes_last_and_nothing_else_changes():
    tree = S.loads(_raw())
    before = S.shortcuts_of(tree)
    idx = S.add_shortcut(tree, S.make_entry("New", "/x/y", "/x"))
    after = S.shortcuts_of(S.loads(S.dumps(tree)))
    assert idx == "2" and [k for k, _ in after] == ["0", "1", "2"]
    assert after[:2] == before                                      # the player's shortcuts are untouched
    empty = []
    assert S.add_shortcut(empty, S.make_entry("First", "/x/y")) == "0" and S.shortcuts_of(empty)


def test_remove_only_touches_our_own_tagged_shortcuts():
    tree = S.loads(_raw())
    S.add_shortcut(tree, S.make_entry("Ours A", "/a"))
    S.add_shortcut(tree, S.make_entry("Ours B", "/b"))
    assert S.remove_shortcuts(tree, S.TAG, "Ours A") == 1
    names = [S._field(e, "AppName") for k, e in S.shortcuts_of(tree)]
    assert names == ["Mine", "Also mine", "Ours B"]                  # renumbered, the others stay
    assert S.remove_shortcuts(tree) == 1
    assert [S._field(e, "AppName") for k, e in S.shortcuts_of(tree)] == ["Mine", "Also mine"]
    assert S.remove_shortcuts(tree) == 0                             # a "Favorite" shortcut is never removed


def test_write_keeps_a_backup_and_is_atomic(tmp_path):
    f = tmp_path / "userdata" / "123" / "config" / "shortcuts.vdf"
    f.parent.mkdir(parents=True)
    f.write_bytes(_raw())
    tree = S.read_file(f)
    S.add_shortcut(tree, S.make_entry("New", "/x/y"))
    S.write_file(f, tree)
    backups = list(f.parent.glob("shortcuts.vdf.scritch-backup-*"))
    assert len(backups) == 1 and backups[0].read_bytes() == _raw()   # the old file, unchanged
    assert not list(f.parent.glob("*.scritch-tmp"))
    assert len(S.shortcuts_of(S.read_file(f))) == 3
    assert S.read_file(tmp_path / "missing.vdf") == []               # no file yet: an empty list


def test_files_are_found_per_steam_user(tmp_path):
    (tmp_path / ".local/share/Steam/userdata/4242/config").mkdir(parents=True)
    (tmp_path / ".local/share/Steam/userdata/0").mkdir(parents=True)          # Steam's placeholder user
    roots = S.steam_roots(tmp_path)
    assert [f.parts[-3] for f in S.shortcut_files(roots)] == ["4242"]


def test_runs_by_hand_on_its_own(tmp_path):
    """The Deck experiment: python3 steam_shortcuts.py where | add | check | list | remove."""
    user = tmp_path / ".local/share/Steam/userdata/4242/config"
    user.mkdir(parents=True)
    (user / "shortcuts.vdf").write_bytes(_raw())
    env = {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PATH": ""}

    def run(*a):
        return subprocess.run([sys.executable, str(SCRIPT), *a], capture_output=True, text=True, env=env).stdout
    assert "4242" in run("where")
    assert "round trip OK" in run("verify")
    assert "NOT in the file" in run("check")
    assert "test shortcut added" in run("add")
    assert "IN THE FILE" in run("check") and "SCRiTCH test game" in run("list")
    assert "already there" in run("add")
    assert "removed 1" in run("remove")
    assert "NOT in the file" in run("check")
    assert S.dumps(S.loads((user / "shortcuts.vdf").read_bytes())) == (user / "shortcuts.vdf").read_bytes()
    assert [S._field(e, "AppName") for k, e in S.shortcuts_of(S.read_file(user / "shortcuts.vdf"))] == \
        ["Mine", "Also mine"]                                       # back to exactly the player's own two
