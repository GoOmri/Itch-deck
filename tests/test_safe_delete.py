"""Deleting folders (audit 17 Nov): uninstall and move only delete folders that really are game
folders inside a games root, and a leftover Proton prefix (it can hold saves) is set aside, not deleted."""
import time

from itch_deck import installer as I
from itch_deck import paths

from test_move import _setup, _wait


def test_only_folders_inside_a_root_may_be_deleted(tmp_path):
    root = tmp_path / "drive" / "scritch"
    (root / "game").mkdir(parents=True)
    other = tmp_path / "elsewhere" / "thing"
    other.mkdir(parents=True)
    assert I.safe_to_delete(root / "game", [root])
    assert not I.safe_to_delete(root, [root])                    # the games folder itself
    assert not I.safe_to_delete(root.parent, [root])             # above it
    assert not I.safe_to_delete(other, [root])                   # somewhere else
    assert not I.safe_to_delete("/", [root])
    assert not I.safe_to_delete(paths.HOME, [paths.HOME.parent])  # the home folder
    assert not I.safe_to_delete("", [root])


def test_uninstall_does_not_delete_a_folder_outside_the_games_folders(tmp_path):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    stray = tmp_path / "important"
    stray.mkdir()
    (stray / "keep.txt").write_text("mine")
    inst.index["7"]["dir"] = str(stray)                           # a damaged install record
    assert inst.uninstall("7") and "7" not in inst.index          # the entry is forgotten ...
    time.sleep(0.3)
    assert (stray / "keep.txt").exists()                          # ... the folder is not touched


def test_uninstall_still_deletes_a_real_game_folder(tmp_path):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    assert inst.uninstall("7")
    for _ in range(100):
        if not game.exists():
            break
        time.sleep(0.02)
    assert not game.exists()


def test_move_keeps_a_leftover_prefix_with_saves(tmp_path):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    left = internal / "_prefixes/moss"                            # saves of an earlier "moss"
    (left / "drive_c").mkdir(parents=True)
    (left / "drive_c/save.dat").write_text("old slot")
    assert inst.move("7", internal, "internal storage")
    _wait(inst)
    kept = [p for p in (internal / "_prefixes").iterdir() if ".kept-" in p.name]
    assert len(kept) == 1 and (kept[0] / "drive_c/save.dat").read_text() == "old slot"
    assert inst.index["7"]["dir"] == str(internal / "moss")


def test_uninstall_deletes_a_game_kept_in_an_older_games_folder(tmp_path):
    """The install location changed since this game was installed: it still gets deleted."""
    from test_move import FakeLib
    paths.use_root(tmp_path / "home")
    old = tmp_path / "custom" / "scritch" / "moss"
    old.mkdir(parents=True)
    (old / "a").write_text("x")
    inst = I.Installer(FakeLib([{"id": "7", "title": "Moss", "state": "installed"}]),
                       lambda: tmp_path / "drive" / "scritch")
    inst.index["7"] = {"dir": str(old), "platform": "linux", "exe": "a"}
    assert inst.uninstall("7")
    for _ in range(100):
        if not old.exists():
            break
        time.sleep(0.02)
    assert not old.exists()
