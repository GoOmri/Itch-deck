"""DOS tab (v0.9.19, Omri 17 Nov): the games that run in DOSBox get their own tab, shown only once
there is one. Step 1: installed GOG DOS games (their play task is dosbox.exe)."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

from itch_deck.ui.scenes.library import Library, tabs, visible  # noqa: E402


def test_tab_only_when_a_dos_game_exists():
    assert [k for k, _ in tabs(("itch", "gog"))] == ["all", "installed", "itch", "gog"]
    got = tabs(("itch", "epic", "gog"), dos=True)
    assert [k for k, _ in got] == ["all", "installed", "itch", "epic", "gog", "dos"]
    assert dict(got)["dos"] == "DOS"
    assert tabs(("itch",), dos=True)[-1] == ("dos", "DOS")          # also with a single store


def test_the_dos_tab_lists_only_dos_games():
    games = [{"id": "a", "title": "A", "platforms": {"windows"}, "dos": True, "store": "gog"},
             {"id": "b", "title": "B", "platforms": {"windows"}, "store": "gog"},
             {"id": "c", "title": "C", "platforms": {"linux"}, "store": "itch"}]
    assert [g["id"] for g in visible(games, "dos")] == ["a"]
    assert len(visible(games, "all")) == 3                          # the rest is unchanged


def _scene(games, filt="all"):
    pg.init()
    from itch_deck.theme import Theme
    return Library(Theme(pg, (1280, 800)), games, filt=filt, stores=("itch", "gog"))


def test_the_tab_comes_and_goes_with_the_games():
    g = {"id": "gog-1", "title": "Eye", "platforms": {"windows"}, "store": "gog"}
    sc = _scene([g], filt="dos")
    assert sc.filt == "all" and "dos" not in dict(sc.tabs())       # an old "dos" tab with no DOS games
    g["dos"] = True                                                 # installed -> the tab appears
    assert "dos" in dict(sc.tabs())
    sc.next_tab(-1)                                                 # L1 from All wraps to the last tab
    assert sc.filt == "dos" and [x["id"] for x in sc.shown] == ["gog-1"]


def test_install_marks_dosbox_games(tmp_path):
    from itch_deck import library
    lib = library.Library.__new__(library.Library)
    lib.live = {}
    g1, g2 = {"id": "gog-1", "title": "Eye"}, {"id": "gog-2", "title": "Other"}
    lib.installs = {"gog-1": {"dir": str(tmp_path), "store": "gog", "platform": "windows",
                              "exe": "DOSBOX/DOSBox.exe", "size": 5},
                    "gog-2": {"dir": str(tmp_path), "store": "gog", "platform": "windows",
                              "exe": "Game.exe", "size": 5}}
    lib._apply_install(g1)
    lib._apply_install(g2)
    assert g1["dos"] is True and g2["dos"] is False
    lib.installs.pop("gog-1")                                       # uninstalled: no longer DOS
    lib._apply_install(g1)
    assert "dos" not in g1
