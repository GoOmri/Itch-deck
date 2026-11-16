"""Move a game between the SD card and internal storage (16 Nov): copy to <root>/_moving, check,
rename into place, switch the install record (and Epic's), fix registry paths, delete the old copy.
Until the switch the old copy is untouched; cancel / failure / crash leave it as it was."""
import json
import os
import time
from pathlib import Path

from itch_deck import installer as I
from itch_deck import paths


class FakeLib:
    def __init__(self, games):
        self.games, self.installs, self.live, self.epic = games, {}, {}, None

    def apply_installs(self):
        pass

    def by_id(self, gid):
        return next((g for g in self.games if g["id"] == gid), None)


def _setup(tmp_path):
    paths.use_root(tmp_path / "home")
    sd, internal = tmp_path / "sd/itch", tmp_path / "home/Games/scritch"
    game = sd / "moss"
    (game / "files/data").mkdir(parents=True)
    (game / "files/Moss.exe").write_bytes(b"MZ" + b"x" * 5000)
    (game / "files/data/level1.pak").write_bytes(b"y" * 20000)
    os.symlink("Moss.exe", game / "files/start")
    pfx = sd / "_prefixes/moss"
    (pfx / "drive_c/users/steamuser/Documents").mkdir(parents=True)
    (pfx / "drive_c/users/steamuser/Documents/save.dat").write_text("slot")
    (pfx / "dosdevices").mkdir()
    os.symlink("/", pfx / "dosdevices/z:")
    (pfx / "system.reg").write_text(
        '"InstallPath"="Z:\\\\' + "\\\\".join(str(game).strip("/").split("/")) + '"\n')
    lib = FakeLib([{"id": "7", "title": "Moss & Rivets", "state": "installed"}])
    inst = I.Installer(lib, lambda: sd)
    inst.index["7"] = {"dir": str(game), "prefix": str(pfx), "platform": "windows", "exe": "Moss.exe"}
    return inst, lib, sd, internal, game, pfx


def _wait(inst):
    for _ in range(200):
        if not inst.moving:
            return
        time.sleep(0.02)
    raise AssertionError("move didn't finish")


def test_move_to_internal_and_back(tmp_path):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    choices = [("SD card", sd), ("Internal storage", internal)]
    assert inst.move_target("7", choices) == ("Internal storage", internal)
    assert inst.move("7", internal, "internal storage")
    _wait(inst)
    new, new_pfx = internal / "moss", internal / "_prefixes/moss"
    assert inst.index["7"]["dir"] == str(new) and inst.index["7"]["prefix"] == str(new_pfx)
    assert json.loads(paths.INSTALLS.read_text())["7"]["dir"] == str(new)
    assert (new / "files/data/level1.pak").stat().st_size == 20000
    assert os.readlink(new / "files/start") == "Moss.exe"            # links stay links
    assert os.readlink(new_pfx / "dosdevices/z:") == "/"
    assert (new_pfx / "drive_c/users/steamuser/Documents/save.dat").read_text() == "slot"
    reg = (new_pfx / "system.reg").read_text()
    assert "home\\\\Games\\\\scritch\\\\moss" in reg and "sd\\\\itch" not in reg
    for _ in range(50):                                              # old copy deleted (thread)
        if not game.exists() and not pfx.exists():
            break
        time.sleep(0.02)
    assert not game.exists() and not pfx.exists()
    assert not (internal / I.MOVING).exists()
    assert ("done", "7", "Moss & Rivets moved to internal storage.") in inst.events
    assert lib.games[0]["state"] == "installed" and lib.games[0].get("move_to") is None
    assert inst.move_target("7", choices) == ("SD card", sd)          # and back
    inst.move("7", sd, "SD card")
    _wait(inst)
    assert inst.index["7"]["dir"] == str(sd / "moss") and (sd / "moss/files/Moss.exe").exists()


def test_not_enough_space_keeps_everything(tmp_path, monkeypatch):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    monkeypatch.setattr(I.shutil, "disk_usage", lambda p: type("U", (), {"free": 1000})())
    inst.move("7", internal, "internal storage")
    _wait(inst)
    kind, _, msg = inst.events[-1]
    assert kind == "error" and msg == "Couldn't move Moss & Rivets. Not enough space."
    assert inst.index["7"]["dir"] == str(game) and (game / "files/Moss.exe").exists()
    assert not (internal / "moss").exists() and not (internal / I.MOVING).exists()


def test_cancel_and_bad_copy_keep_the_old_copy(tmp_path, monkeypatch):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    real = I._copy_tree

    def cancel_midway(a, b, tick):
        inst.cancel_move("7")
        real(a, b, tick)
    monkeypatch.setattr(I, "_copy_tree", cancel_midway)
    inst.move("7", internal, "internal storage")
    _wait(inst)
    assert inst.index["7"]["dir"] == str(game) and not (internal / "moss").exists()
    assert not (internal / I.MOVING).exists() and not inst.events          # cancel: no toast
    monkeypatch.setattr(I, "_copy_tree", real)
    counts = iter(range(1000))
    monkeypatch.setattr(I, "_tree_count", lambda p: next(counts))         # never the same
    inst.move("7", internal, "internal storage")
    _wait(inst)
    kind, _, msg = inst.events[-1]
    assert kind == "error" and msg.endswith("Code M03")
    assert inst.index["7"]["dir"] == str(game) and (game / "files/Moss.exe").exists()


def test_epic_record_follows_and_leftovers_cleaned(tmp_path):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    from itch_deck.stores import epic
    cdir = epic.config_dir()
    cdir.mkdir(parents=True)
    (cdir / "installed.json").write_text(json.dumps({"Moss": {"install_path": str(game),
                                                               "executable": "Moss.exe"}}))
    store = epic.EpicStore.__new__(epic.EpicStore)
    lib.epic = store
    inst.index["7"].update(store="epic", app_name="Moss")
    inst.move("7", internal, "internal storage")
    _wait(inst)
    rec = json.loads((cdir / "installed.json").read_text())["Moss"]
    assert rec["install_path"] == str(internal / "moss") and rec["executable"] == "Moss.exe"
    (sd / I.MOVING / "game").mkdir(parents=True)                           # a move cut short
    inst.clean_moves([sd, internal])
    assert not (sd / I.MOVING).exists()


def test_no_move_while_busy_or_without_a_card(tmp_path):
    inst, lib, sd, internal, game, pfx = _setup(tmp_path)
    assert inst.move_target("7", [("Internal storage", internal)]) is None    # no card
    inst.queue.append("7")
    assert inst.move_target("7", [("SD card", sd), ("Internal storage", internal)]) is None
    inst.queue.clear()
    assert inst.move_target("8", [("SD card", sd), ("Internal storage", internal)]) is None
    assert Path(inst.index["7"]["dir"]) == game
