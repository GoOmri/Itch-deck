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


def test_the_flag_follows_the_ids_even_for_an_installed_game(tmp_path):
    lib = library.Library.__new__(library.Library)
    lib.live, lib.installs = {}, {}
    lib.games = [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]
    lib.set_hidden(["a", "b", "gone"])
    assert [g["hidden"] for g in lib.games] == [True, True]
    lib.installs = {"b": {"dir": str(tmp_path), "store": "gog", "platform": "windows", "exe": "x", "size": 1}}
    lib.set_hidden(["a", "b"])                                    # v0.9.32: b is installed and stays hidden
    assert [g["hidden"] for g in lib.games] == [True, True]
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
    assert _scene(dict(base, state="installed")).options()[-1] == "Hide from SCRiTCH"          # v0.9.32: any game
    assert _scene(dict(base, state="installed", steam_ok=True)).options()[-2:] == ["Add to Steam", "Hide from SCRiTCH"]
    assert _scene(dict(base, state="missing", missing="files")).options() == ["Uninstall", "Hide from SCRiTCH"]
    assert _scene(dict(base, state="downloading")).options() == []                              # busy: nothing
    assert _scene(dict(base, state="queued")).options() == []
    itch_in = dict(base, store="itch", platforms={"linux"}, state="installed")
    assert _scene(itch_in).options() == ["Uninstall", "Change build", "Controls", "Saves", "Hide from SCRiTCH"]
    dos = dict(base, store="dos", platforms={"linux"}, state="installed", dos=True, programs=2)
    assert _scene(dos).options() == ["Controls", "Program to run", "Keep window open after the game",
                                     "Hide from SCRiTCH"]
    assert _scene(dict(dos, state=None)).options() == ["Hide from SCRiTCH"]
    assert _scene(dict(dos, hidden=True)).options() == ["Show in SCRiTCH"]
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


def test_a_hidden_game_stays_hidden_when_it_is_installed_or_uninstalled(tmp_path):
    from itch_deck import installer as I
    lib = library.Library.__new__(library.Library)
    lib.live, lib.installs = {}, {}
    lib.games = [{"id": "a", "title": "A", "state": None}]
    lib.set_hidden(["a"])
    inst = I.Installer.__new__(I.Installer)
    inst.lib = lib
    for st in ("downloading", "installed", None):
        inst._upd("a", state=st)
        assert lib.games[0]["hidden"] is True and "a" in lib.hidden, st


def test_hiding_an_own_dos_game_asks_and_forgets_the_entry_only(monkeypatch):
    asked, done = [], []
    me = types.SimpleNamespace(confirm=lambda *a, **k: asked.append((a, k)),
                               _remove_dos=lambda g: done.append(g["id"]), _set_hidden=lambda *a: done.append("plain"))
    g = {"id": "dos-1", "title": "Doom", "store": "dos"}
    app_game.GameMixin.game_action(me, g, "Hide from SCRiTCH")
    title, body, action, fn = asked[0][0][:4]
    assert title == "Hide Doom from SCRiTCH?" and action == "Hide" and "files stay" in body[0]
    assert "Hidden games" in body[1] and asked[0][1] == {"main": True}
    fn()
    assert done == ["dos-1"]


def test_dos_hide_and_show_round_trip(tmp_path, monkeypatch):
    from itch_deck import installer as I
    paths.use_root(tmp_path / "home")
    root = tmp_path / "games" / "dos"
    (root / "Doom").mkdir(parents=True)
    (root / "Doom" / "DOOM.EXE").write_bytes(b"x" * 10)
    lib = library.Library.__new__(library.Library)
    lib.live, lib.installs, lib.games, lib.hidden = {}, {}, [], set()
    inst = I.Installer.__new__(I.Installer)
    inst.lib, inst.index, inst.choices, inst.cfg = lib, {}, {}, {}
    inst.dos_root = lambda: root
    inst.dos_roots = lambda: [root]
    monkeypatch.setattr(I.config, "card_missing", lambda p: False)
    monkeypatch.setattr(lib, "set_dos_games", lambda games: None, raising=False)
    assert inst.sync_dos() == 1 and len(inst.index) == 1
    gid = next(iter(inst.index))
    inst.uninstall(gid)                                           # what Hide does for a DOS game
    lib.hidden = {gid}
    assert inst.sync_dos() == 0 and gid not in inst.index         # Refresh: it does not come back
    assert (root / "Doom" / "DOOM.EXE").exists()                  # the player's files are untouched
    lib.hidden = set()                                            # Show in SCRiTCH + the scan it starts
    assert inst.sync_dos() == 1 and gid in inst.index


def test_manage_games_lists_a_hidden_installed_game(tmp_path):
    from itch_deck import storagemgr
    games = [{"id": "a", "title": "A", "state": "installed", "hidden": True, "size_mb": 500}]
    index = {"a": {"dir": str(tmp_path), "store": "itch", "size": 500_000_000}}
    assert [e["id"] for e in storagemgr.entries(games, index)] == ["a"]


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
