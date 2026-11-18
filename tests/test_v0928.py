"""v0.9.28: DOS scan, hidden DOS games, clean titles, art order, wide covers, short text, program picker,
Manage games, crash checks. No network anywhere (tests/conftest.py refuses it)."""
import os
import sys
import types
import zipfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dosgames, paths  # noqa: E402
from itch_deck import installer as I  # noqa: E402
from tests.test_dosgames import _Lib  # noqa: E402


def make_game(d, exe="GAME.EXE", extra=()):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    if exe:
        (d / exe).write_bytes(b"MZ" + b"x" * 50)
    for e in extra:
        (d / e).parent.mkdir(parents=True, exist_ok=True)
        (d / e).write_bytes(b"MZ" + b"y" * 20)
    return d


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for k in files:
            z.writestr(k, b"MZ" + b"z" * 10)


def layout(dos, tag=""):
    """What Omri has: dos/DOS/<18 games> next to new top-level folders and new zips."""
    for i in range(18):
        make_game(dos / "DOS" / f"old{tag}{i}")
    make_game(dos / f"Commander Keen 3 Keen Must Die (1990)(Apogee Software){tag}", "KEEN3.EXE")
    make_game(dos / f"Blood (1997)(Monolith){tag}", "BLOOD.EXE", ["SETUP.EXE", "SNDSETUP.EXE"])
    make_game(dos / f"dave2{tag}", "DAVE.EXE")
    make_game(dos / f"doom{tag}", "DOOM.BAT", ["DOOM.EXE", "DOOM2.EXE"])
    make_game(dos / f"deep{tag}" / "BIO", "BIO.EXE")                  # program one level down
    make_zip(dos / f"zipone{tag}.zip", [f"zipone{tag}/Z.EXE"])        # one game, with a top folder
    make_zip(dos / f"zipflat{tag}.zip", ["F.EXE", "F.DAT"])           # one game, no top folder
    make_zip(dos / f"zipmany{tag}.zip", [f"zipmany{tag}/g{tag}{i}/G.EXE" for i in range(4)])   # a collection


def inst_two_roots(tmp_path, monkeypatch):
    paths.use_root(tmp_path / "home")
    sd = tmp_path / "sd"
    root = sd / "itch"
    internal = paths.HOME / "Games" / "scritch"
    monkeypatch.setattr(I.config, "install_choices", lambda: [("SD card", root), ("Internal storage", internal)])
    monkeypatch.setattr(I.config, "card_missing", lambda p: False)
    (root / "dos").mkdir(parents=True)
    (internal / "dos").mkdir(parents=True)
    lib = _Lib()
    return I.Installer(lib, lambda: root), lib, root / "dos", internal / "dos"


def test_every_game_folder_and_zip_in_every_root_is_listed(tmp_path, monkeypatch):
    inst, lib, sd_dos, int_dos = inst_two_roots(tmp_path, monkeypatch)
    layout(sd_dos, "s")
    layout(int_dos, "i")
    n = inst.sync_dos()
    names = sorted(e["title"] for e in lib.dos)
    per_root = 18 + 5 + 2 + 4
    assert n == 2 * per_root, (n, names)
    assert any(t.startswith("deep") for t in names) and any(t.startswith("zipflat") for t in names)


def test_the_same_game_name_twice_in_one_root_gives_two_tiles(tmp_path, monkeypatch):
    inst, lib, sd_dos, _ = inst_two_roots(tmp_path, monkeypatch)
    for i in range(3):
        make_game(sd_dos / "DOS" / f"g{i}")
    make_game(sd_dos / "doom")                    # a collection's game and a top-level game with one name
    make_game(sd_dos / "DOS" / "doom")
    assert inst.sync_dos() == 5
    ids = [e["id"] for e in lib.dos]
    assert len(set(ids)) == 5
    assert dosgames.game_id("doom") in ids        # the first one keeps the old id


def test_the_other_name_of_the_games_folder_is_read_too(tmp_path, monkeypatch):
    inst, lib, sd_dos, int_dos = inst_two_roots(tmp_path, monkeypatch)
    alt = paths.HOME / "Games" / "itch" / "dos"   # "itch" exists next to "scritch": both are read
    make_game(alt / "alt game")
    make_game(int_dos / "scritch game")
    assert inst.sync_dos() == 2


def test_one_broken_folder_does_not_hide_the_others(tmp_path, monkeypatch):
    inst, lib, sd_dos, _ = inst_two_roots(tmp_path, monkeypatch)
    make_game(sd_dos / "a")
    make_game(sd_dos / "b")
    real = dosgames.survey

    def bad(f):
        if Path(f).name == "a":
            raise RuntimeError("boom")
        return real(f)
    monkeypatch.setattr(dosgames, "survey", bad)
    assert inst.sync_dos() == 1


# --- 2: hidden own DOS games live in the DOS tab's Hidden filter ----------------------------------
def test_a_hidden_own_dos_game_shows_in_the_dos_tab_hidden_filter():
    from itch_deck.ui.scenes.library import visible
    own = {"id": "d1", "title": "D", "platforms": {"linux"}, "store": "dos", "state": None, "hidden": True}
    seen = {"id": "d2", "title": "E", "platforms": {"linux"}, "store": "dos", "state": "installed", "dos": True}
    games = [own, seen]
    assert [g["id"] for g in visible(games, "dos", show="hidden")] == ["d1"]
    assert [g["id"] for g in visible(games, "dos")] == ["d2"]
    assert [g["id"] for g in visible(games, "dos", show="all")] == ["d2"]


def test_the_dos_tab_exists_when_only_hidden_dos_games_are_left():
    from itch_deck.ui.scenes.library import Library
    t = _theme()
    g = {"id": "d1", "title": "D", "platforms": {"linux"}, "store": "dos", "state": None, "hidden": True}
    lib = Library(t, [g], stores=("itch",))
    assert ("dos", "DOS") in lib.tabs()


def _theme():
    from itch_deck import theme
    pg.init()
    pg.display.set_mode((64, 64))
    return theme.Theme(pg, (1280, 800))
