"""v0.9.25 (Omri, Deck test 18 Nov): a zip of many DOS games = many tiles, DOS folders on both drives, one
fetch per missing page per week, a short Options list with a "More" row, Steam tiles go with the game."""
import datetime as dt
import json
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import app_game, config, dosgames, library, paths  # noqa: E402
from itch_deck.input import A, B  # noqa: E402
from itch_deck.ui.scenes.game import Game  # noqa: E402



def _game(root, name, files=("GAME.EXE",)):
    d = root / name
    d.mkdir(parents=True)
    for f in files:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_bytes(b"MZ" + b"x" * 100)
    return d


# --- DOS collections -----------------------------------------------------------------------------------
def test_a_folder_of_many_games_gives_one_tile_per_game(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "dos"
    big = root / "DOS"
    for name, exe in (("Doom", "DOOM.EXE"), ("Raptor", "RAPTOR.EXE"), ("Blood (1997)", "BLOOD.EXE")):
        _game(big, name, [exe])
    _game(big, "Setup tools", ["SETUP.EXE"])                       # a helper folder is not a game
    got = dosgames.scan(root)
    assert sorted(g["name"] for g in got) == ["Blood (1997)", "Doom", "Raptor"]
    assert all(g["dir"].startswith(str(big)) for g in got)


def test_a_game_with_tool_folders_stays_one_game(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "dos"
    _game(root, "Keen", ["KEEN.EXE", "DATA/LEVEL.EXE", "EDIT/EDIT.EXE"])      # its own program: not a collection
    _game(root, "Two", ["A/A.EXE", "B/B.EXE"])                                # only two folders: one game
    assert sorted(g["name"] for g in dosgames.scan(root)) == ["Keen", "Two"]


def test_a_removed_game_inside_a_collection_stays_hidden(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "dos"
    for name in ("Doom", "Raptor", "Blood"):
        _game(root / "DOS", name, [name.upper() + ".EXE"])
    got = dosgames.scan(root, hide={"Raptor": 4_000_000_000})
    assert sorted(g["name"] for g in got) == ["Blood", "Doom"]


def test_dos_folders_on_both_drives_are_read(tmp_path, monkeypatch):
    from itch_deck import installer as I
    paths.use_root(tmp_path / "home")
    sd, internal = tmp_path / "sd/scritch", tmp_path / "home/Games/scritch"
    _game(sd / "dos", "FromSD", ["A.EXE"])
    _game(internal / "dos", "FromInternal", ["B.EXE"])
    monkeypatch.setattr(config, "install_choices", lambda: [("SD card", sd), ("Internal storage", internal)])
    inst = I.Installer.__new__(I.Installer)
    inst.root_fn, inst.index = (lambda: sd), {}
    names = sorted(e["name"] for e in inst.scan_dos()["entries"])
    assert names == ["FromInternal", "FromSD"]
    assert inst.dos_roots() == [sd / "dos", internal / "dos"]


# --- details prefetch ----------------------------------------------------------------------------------
def test_a_page_that_is_gone_is_not_asked_again_for_a_week(tmp_path, monkeypatch):
    lib = library.Library.__new__(library.Library)
    f = tmp_path / "page.json"
    monkeypatch.setattr(lib, "_page_file", lambda g: f, raising=False)
    g = {"id": "1", "store": "itch"}
    now = library._now().isoformat(timespec="seconds")
    f.write_text(json.dumps({"fetched": now, "missing": True}))
    assert lib._has_page_fields(g)                                          # fetched just now: leave it
    old = (library._now() - dt.timedelta(days=8)).isoformat(timespec="seconds")
    f.write_text(json.dumps({"fetched": old, "missing": True}))
    assert not lib._has_page_fields(g)                                      # a week later: try once more
    f.write_text(json.dumps({"missing": True}))
    assert not lib._has_page_fields(g)                                      # no date: try again


def _scene(**kw):
    from itch_deck.theme import Theme
    pg.init()
    g = {"id": "x", "title": "X", "platforms": {"linux", "windows"}, "store": "itch", "state": "installed",
         "programs": 1}
    g.update(kw)
    return Game(Theme(pg, (1280, 800)), g)


# --- Steam tiles ---------------------------------------------------------------------------------------
def test_uninstall_drops_the_steam_tile_and_says_so(monkeypatch):
    from itch_deck import steam_games
    removed, said = [], []
    monkeypatch.setattr(steam_games, "is_added", lambda gid: gid == "x")
    monkeypatch.setattr(steam_games, "remove", lambda gid: removed.append(gid) or 1)
    me = types.SimpleNamespace(inst=types.SimpleNamespace(uninstall=lambda gid: True), scene=types.SimpleNamespace(focus=3),
                               say=lambda m, error=False: said.append(m))
    me._drop_steam_tile = lambda gid: app_game.GameMixin._drop_steam_tile(me, gid)
    app_game.GameMixin._uninstall(me, {"id": "x", "title": "Kids", "store": "itch"})
    assert removed == ["x"] and said[-1] == "Kids was uninstalled. Its Steam tile goes after a Steam restart."
    app_game.GameMixin._uninstall(me, {"id": "y", "title": "Other", "store": "itch"})
    assert removed == ["x"] and said[-1] == "Other was uninstalled."        # no tile: nothing to say


def test_a_steam_file_problem_never_breaks_an_uninstall(monkeypatch):
    from itch_deck import steam_games

    def boom(gid):
        raise OSError("locked")
    monkeypatch.setattr(steam_games, "is_added", boom)
    assert app_game.GameMixin._drop_steam_tile(types.SimpleNamespace(), "x") is False


# --- Send logs -----------------------------------------------------------------------------------------
def test_the_save_hint_is_under_the_steps_not_the_top():
    from itch_deck.theme import Theme
    from itch_deck.ui.scenes.epic import LogsShare
    pg.init()
    t = Theme(pg, (1280, 800))
    s = pg.Surface((t.w, t.h))
    sc = LogsShare(t, status="phone", qr=[[(r + c) % 3 == 0 for c in range(29)] for r in range(29)], url="http://x")
    sc.draw_page(s)                                                         # draws without error, hint included
    assert "press A" not in sc.SUB.lower() and ("A", "Save a copy") in sc.hints()


# --- reviewer findings (v0.9.25) -------------------------------------------------------------------------
def test_games_only_on_the_other_drive_are_found_and_kept(tmp_path, monkeypatch):
    from itch_deck import installer as I
    paths.use_root(tmp_path / "home")
    sd, internal = tmp_path / "sd/scritch", tmp_path / "home/Games/scritch"      # no dos folder on the SD card
    _game(internal / "dos", "OnlyInternal", ["B.EXE"])
    monkeypatch.setattr(config, "install_choices", lambda: [("SD card", sd), ("Internal storage", internal)])
    inst = I.Installer.__new__(I.Installer)
    inst.root_fn, inst.index = (lambda: sd), {}
    got = inst.scan_dos()                                                      # a plain refresh (create=False)
    assert [e["name"] for e in got["entries"]] == ["OnlyInternal"]
    assert not (sd / "dos").exists()                                           # nothing was made


def test_an_old_removed_mark_on_the_big_folder_does_not_hide_the_games_inside(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "dos"
    for name in ("Doom", "Raptor", "Blood"):
        _game(root / "DOS", name, [name.upper() + ".EXE"])
    got = dosgames.scan(root, hide={"DOS": 4_000_000_000})          # "Remove from library" on the old single tile
    assert sorted(g["name"] for g in got) == ["Blood", "Doom", "Raptor"]


def test_game_names_that_contain_a_helper_word_are_still_games(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "dos"
    for name in ("Mouse Hunt", "Patch Adams", "Marjorie's Quest", "Setup"):
        _game(root / "DOS", name, ["GAME.EXE"])
    assert sorted(g["name"] for g in dosgames.scan(root)) == ["Marjorie's Quest", "Mouse Hunt", "Patch Adams"]


# --- v0.9.26 (Omri, Deck test 18 Nov) -------------------------------------------------------------------------
def test_a_long_dialog_title_wraps_inside_the_box():
    from itch_deck.theme import Theme
    from itch_deck.ui import widgets as W
    pg.init()
    t = Theme(pg, (1280, 800))
    s = pg.Surface((t.w, t.h))
    short = W.modal(t, s, "Remove Doom?", ["Files stay."], ["Remove", "Cancel"])
    long_ = W.modal(t, s, "Remove Eye of the Beholder III: Assault on Myth Drannor from your library?",
                    ["Files stay."], ["Remove", "Cancel"])
    assert long_.width <= t.w - 2 * t.m and long_.height > short.height          # taller, not wider than the screen


def test_a_menu_that_opens_starts_with_its_focus_in_place():
    from itch_deck.ui import widgets as W
    sc = _scene()
    key = (("menu", "Options"), "Uninstall")
    W._ANIM[key] = (700.0, 0.0, 1000.0, 0.0)                                      # left over from the last time
    sc.overlay = ("menu", "Options", "", [("Uninstall", "", "")], 0)
    assert key not in W._ANIM
    W._ANIM[key] = (500.0, 0.0, 1000.0, 0.0)
    sc.overlay = ("menu", "Options", "", [("Uninstall", "", "")], 0)              # UP/DOWN re-sets the same menu
    assert key in W._ANIM                                                         # no reset: the slide stays


def test_a_hidden_dos_game_has_no_install_button_and_only_the_way_back():
    sc = _scene(store="dos", state=None, hidden=True, platforms={"linux"})
    assert [a[0] for a in sc.actions()] == ["Options"] and sc.options() == ["Show in SCRiTCH"]


def test_removing_a_dos_game_hides_it_and_showing_it_scans_again(monkeypatch):
    saved, scans, said = [], [], []
    monkeypatch.setattr(config, "save", lambda cfg: saved.append(dict(cfg)))
    removed = []
    me = types.SimpleNamespace(cfg={}, inst=types.SimpleNamespace(uninstall=lambda gid: removed.append(gid) or True),
                               lib=types.SimpleNamespace(set_hidden=lambda ids: None),
                               go_library=lambda: None, say=lambda m, error=False: said.append(m),
                               _start_dos_scan=lambda **k: scans.append(1))
    me._set_hidden = lambda g, hide: app_game.GameMixin._set_hidden(me, g, hide)
    g = {"id": "dos-alley", "title": "Alley", "store": "dos"}
    app_game.GameMixin._remove_dos(me, g)
    assert removed == ["dos-alley"] and me.cfg["hidden"] == ["dos-alley"] and not scans
    app_game.GameMixin._set_hidden(me, g, False)
    assert me.cfg["hidden"] == [] and scans == [1]                                # unhidden: its folder is read again
