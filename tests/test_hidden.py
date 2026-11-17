"""Hide from SCRiTCH (v0.9.23, Omri 17 Nov): hide a game that is not installed (this Deck only; the store account
is untouched). It is gone from every tab and comes back through Sort & filter > Show > Hidden games."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":                                   # mouse.py (imported by app_game) needs Linux's fcntl
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import app_game, config, library, paths  # noqa: E402
from itch_deck.ui.scenes.game import Game  # noqa: E402
from itch_deck.ui.scenes.library import Library, SHOWS, visible  # noqa: E402


def _games():
    return [{"id": "a", "title": "A", "platforms": {"windows"}, "store": "gog", "state": None},
            {"id": "b", "title": "B", "platforms": {"linux"}, "store": "itch", "state": "installed"},
            {"id": "c", "title": "C", "platforms": {"other"}, "store": "itch", "state": None, "hidden": True},
            {"id": "d", "title": "D", "platforms": {"windows"}, "store": "epic", "state": None, "hidden": True}]


def test_hidden_games_leave_every_tab_and_show_in_their_own_filter():
    g = _games()
    for filt in ("all", "installed", "itch", "gog", "epic"):
        assert not any(x.get("hidden") for x in visible(g, filt)), filt
    assert [x["id"] for x in visible(g, "all")] == ["a", "b"]
    assert [x["id"] for x in visible(g, "all", show="playable")] == ["a", "b"]
    assert [x["id"] for x in visible(g, "all", show="hidden")] == ["c", "d"]
    assert [x["id"] for x in visible(g, "epic", show="hidden")] == ["d"]            # per tab, like every filter
    assert dict(SHOWS)["hidden"] == "Hidden games"


def test_the_flag_follows_the_ids_and_never_hides_an_installed_game(tmp_path):
    lib = library.Library.__new__(library.Library)
    lib.live, lib.installs = {}, {}
    lib.games = [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]
    lib.set_hidden(["a", "b", "gone"])
    assert [g["hidden"] for g in lib.games] == [True, True]
    lib.installs = {"b": {"dir": str(tmp_path), "store": "gog", "platform": "windows", "exe": "x", "size": 1}}
    lib.set_hidden(["a", "b"])                                    # b got installed: it comes back by itself
    assert [g["hidden"] for g in lib.games] == [True, False]
    lib.set_hidden([])
    assert not any(g["hidden"] for g in lib.games)


def _scene(g):
    pg.init()
    from itch_deck.theme import Theme
    return Game(Theme(pg, (1280, 800)), g, pos=(1, 1))


def test_options_offer_hide_only_for_games_that_are_not_installed():
    base = {"id": "x", "title": "X", "platforms": {"windows"}, "store": "gog"}
    assert _scene(dict(base, state=None)).options() == ["Hide from SCRiTCH"]                    # one build: only Hide
    assert _scene(dict(base, state="failed")).options() == ["Hide from SCRiTCH"]
    itch = dict(base, store="itch", platforms={"linux", "windows"}, state=None)
    assert _scene(itch).options() == ["Change build", "Hide from SCRiTCH"]
    assert "Hide from SCRiTCH" not in _scene(dict(base, state="installed")).options()
    assert _scene(dict(base, state="downloading")).options() == []                              # busy: nothing
    assert _scene(dict(base, state=None, hidden=True)).options() == ["Show in SCRiTCH"]         # the way back
    mac = dict(base, store="itch", platforms={"mac"}, state=None)                              # can't play it here
    assert _scene(mac).options() == ["Hide from SCRiTCH"] and [a[0] for a in _scene(mac).actions()] == ["Options"]


def test_the_filter_menu_has_the_hidden_choice_and_an_empty_message():
    pg.init()
    from itch_deck.theme import Theme
    t = Theme(pg, (1280, 800))
    sc = Library(t, _games(), stores=("itch", "gog"))
    sc.menu_open()                                                # (menu_next works on the open menu)
    seen = []
    for _ in range(3):
        seen.append(dict((r[0], r[1]) for r in sc.menu_items())["Show"].split("  (")[0])
        sc.menu_next("Show")
    assert seen == ["Everything", "Playable here", "Hidden games"] and sc.show == "all"     # a full round
    sc.menu_next("Show")
    sc.menu_next("Show")
    assert sc.show == "hidden" and [g["id"] for g in sc.shown] == ["c", "d"]
    assert dict((r[0], r[1]) for r in sc.menu_items())["Show"] == "Hidden games  (2)"        # with its count
    sc2 = Library(t, [{"id": "a", "title": "A", "platforms": {"linux"}, "store": "itch"}], stores=("itch",))
    sc2.show = "hidden"
    s = pg.Surface((t.w, t.h))
    sc2.draw_page(s)                                              # "No hidden games." draws without an error


def test_app_hides_and_shows_a_game_and_keeps_it_in_the_config(tmp_path, monkeypatch):
    paths.use_root(tmp_path / "home")
    saved, said, went = [], [], []
    monkeypatch.setattr(config, "save", lambda cfg: saved.append(list(cfg.get("hidden") or [])))
    lib = types.SimpleNamespace(set_hidden=lambda ids: went.append(("lib", sorted(ids))))
    me = types.SimpleNamespace(cfg={}, lib=lib, say=lambda m, error=False: said.append(m),
                               go_library=lambda: went.append("library"))
    g = {"id": "gog-1", "title": "Eye"}
    app_game.GameMixin._set_hidden(me, g, True)
    assert me.cfg["hidden"] == ["gog-1"] and saved == [["gog-1"]] and "library" in went
    assert said[-1] == "Eye is hidden."
    app_game.GameMixin._set_hidden(me, {"id": "x", "title": "X"}, True)
    assert me.cfg["hidden"] == ["gog-1", "x"]
    app_game.GameMixin._set_hidden(me, g, False)
    assert me.cfg["hidden"] == ["x"] and said[-1] == "Eye is shown again."
    app_game.GameMixin._set_hidden(me, g, False)                 # again: nothing breaks
    assert me.cfg["hidden"] == ["x"]
    asked = []
    me2 = types.SimpleNamespace(confirm=lambda *a, **k: asked.append((a, k)), _set_hidden=lambda *a: None)
    app_game.GameMixin.game_action(me2, g, "Hide from SCRiTCH")
    title, body, action = asked[0][0][:3]
    assert "Hide Eye from SCRiTCH?" == title and "Hidden games" in body[1] and action == "Hide"
    assert asked[0][1] == {"main": True}                          # the purple, non-destructive button


def test_installing_a_hidden_game_brings_it_back_at_once_and_it_stays_back(tmp_path):
    """Reviewer, v0.9.23: the flag was only recalculated at start or on a sync, so a hidden game that was installed
    stayed hidden (and offered only 'Show in SCRiTCH'), and a later uninstall hid it again."""
    from itch_deck import installer as I
    lib = library.Library.__new__(library.Library)
    lib.live, lib.installs = {}, {}
    lib.games = [{"id": "a", "title": "A", "state": None}]
    forgotten = []
    lib.on_unhide = forgotten.append
    lib.set_hidden(["a"])
    assert lib.games[0]["hidden"] is True
    inst = I.Installer.__new__(I.Installer)
    inst.lib = lib
    inst._upd("a", state="downloading", progress=0.3)             # it starts downloading: no longer hidden
    assert lib.games[0]["hidden"] is False and forgotten == ["a"] and "a" not in lib.hidden
    inst._upd("a", state="installed")
    inst._upd("a", state=None)                                    # uninstalled later: it must NOT be hidden again
    lib.set_hidden(lib.hidden)
    assert lib.games[0]["hidden"] is False


def test_hidden_filter_counts_and_genres(tmp_path):
    pg.init()
    from itch_deck.theme import Theme
    t = Theme(pg, (1280, 800))
    games = [{"id": "a", "title": "A", "platforms": {"linux"}, "store": "itch", "genre": "Puzzle"},
             {"id": "b", "title": "B", "platforms": {"linux"}, "store": "itch", "genre": "Racing", "hidden": True}]
    sc = Library(t, games, stores=("itch",))
    sc.menu_open()
    sc.menu_next("Genre")
    assert sc.genre == "Puzzle"                                   # the hidden game's genre is not offered here
    sc.menu_next("Genre")
    assert sc.genre == "any"
    sc.show = "hidden"
    sc.menu_next("Genre")
    assert sc.genre == "Racing" and [g["id"] for g in sc.shown] == ["b"]
    sc.draw_page(pg.Surface((t.w, t.h)))                          # the top bar says "1 game", not "1 of 1 games"
