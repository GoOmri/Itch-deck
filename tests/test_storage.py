"""Manage games (v0.9.24, Omri 17 Nov): installed games by size, select several, uninstall them together."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":                                   # mouse.py (imported by app_settings/app_storage) needs fcntl
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import app_settings, app_storage, config, paths, storagemgr as SM  # noqa: E402
from itch_deck.input import A, B, DOWN, L2, R2, UP, X, Y  # noqa: E402
from itch_deck.ui.scenes.settings import Settings  # noqa: E402
from itch_deck.ui.scenes.storage import StorageManager  # noqa: E402


def _data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MEDIA", tmp_path / "media")
    sd = tmp_path / "media/deck/SD/scritch"
    internal = tmp_path / "home/Games/scritch"
    games = [{"id": "a", "title": "Alpha", "state": "installed", "size_mb": 900, "played": "2026-11-10T10:00:00"},
             {"id": "b", "title": "beta", "state": "installed", "size_mb": 4300, "played": ""},
             {"id": "c", "title": "Gamma", "state": "installed", "size_mb": 0, "played": "2026-11-17T09:00:00"},
             {"id": "d", "title": "Delta", "state": None, "size_mb": 100},                     # not installed
             {"id": "e", "title": "Echo", "state": "missing", "size_mb": 100},                  # card out
             {"id": "dos-x", "title": "Own DOS", "state": "installed", "size_mb": 5},           # your own DOS game
             {"id": "f", "title": "Foxtrot", "state": "installed", "size_mb": 12, "played": "2026-11-16T09:00:00"}]
    index = {"a": {"dir": str(sd / "alpha")}, "b": {"dir": str(internal / "beta")},
             "c": {"dir": str(sd / "gamma"), "size": 2_500_000_000},                            # size from the record
             "e": {"dir": str(sd / "echo")}, "dos-x": {"dir": str(internal / "dos/x"), "store": "dos"},
             "f": {"dir": str(internal / "foxtrot")}}
    return games, index


def test_only_installed_games_that_can_be_uninstalled_are_listed(tmp_path, monkeypatch):
    games, index = _data(tmp_path, monkeypatch)
    got = {e["id"]: e for e in SM.entries(games, index)}
    assert sorted(got) == ["a", "b", "c", "f"]                      # not: d (not installed), e (missing), dos-x
    assert got["c"]["size_mb"] == 2500                              # no size on the game: the install record's
    assert got["a"]["drive"] == "SD card" and got["b"]["drive"] == "Internal"


def test_orders_and_totals(tmp_path, monkeypatch):
    games, index = _data(tmp_path, monkeypatch)
    items = SM.entries(games, index)
    assert [e["id"] for e in SM.ordered(items, "size")] == ["b", "c", "a", "f"]            # largest first
    assert [e["id"] for e in SM.ordered(items, "az")] == ["a", "b", "f", "c"]               # A-Z ignores case
    assert [e["id"] for e in SM.ordered(items, "played")] == ["c", "f", "a", "b"]           # newest first, never last
    assert SM.total_mb(items) == 900 + 4300 + 2500 + 12 and SM.total_mb(items, {"a", "f"}) == 912
    assert SM.mb_text(12) == "12 MB" and SM.mb_text(940) == "940 MB" and SM.mb_text(1900) == "1.9 GB"


def test_drives_report_free_space(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "sd_card", lambda: None)
    monkeypatch.setattr(paths, "HOME", tmp_path)                    # a folder that exists (other tests move HOME)
    got = SM.drives()
    assert [d["name"] for d in got] == ["Internal storage"] and got[0]["total"] >= got[0]["free"] > 0


def _scene(tmp_path, monkeypatch, **kw):
    games, index = _data(tmp_path, monkeypatch)
    pg.init()
    from itch_deck.theme import Theme
    return StorageManager(Theme(pg, (1280, 800)), SM.entries(games, index), [], **kw)


def test_the_scene_ticks_sorts_and_keeps_its_selection_honest(tmp_path, monkeypatch):
    sc = _scene(tmp_path, monkeypatch)
    assert [e["id"] for e in sc.rows()] == ["b", "c", "a", "f"] and sc.hints()[-1] == ("B", "Back")
    assert ("X", "Uninstall") not in sc.hints()                      # nothing ticked yet
    sc.handle(A)                                                     # the focused row is the biggest: b
    sc.handle(DOWN)
    sc.handle(DOWN)
    sc.handle(A)                                                     # third row: a
    assert sc.selected == {"b", "a"} and sc.selected_mb() == 5200 and ("X", "Uninstall") in sc.hints()
    sc.handle(A)
    assert sc.selected == {"b"}                                      # A again unticks it
    sc.handle(Y)                                                     # Y: next order, the ticks stay with their games
    assert sc.sort == "az" and sc.selected == {"b"} and dict(sc.hints())["Y"] == "Sort: A-Z"
    sc.handle(Y)
    sc.handle(Y)
    assert sc.sort == "size"                                         # a full round
    sc.focus = 0
    sc.handle(UP)
    assert sc.focus == 3                                             # UP from the top wraps to the last
    sc.handle(L2)
    sc.handle(R2)
    assert 0 <= sc.focus <= 3
    sc.set_items([e for e in sc.items if e["id"] != "b"])            # b got uninstalled: its tick goes with it
    assert sc.selected == set() and sc.focus <= 2


def test_the_scene_draws_long_lists_scrolled_empty_and_with_drives(tmp_path, monkeypatch):
    games, index = _data(tmp_path, monkeypatch)
    pg.init()
    from itch_deck.theme import Theme
    t = Theme(pg, (1280, 800))
    many = [{"id": f"g{i}", "title": f"Game number {i}", "size_mb": 100 + i, "drive": "SD card", "played": ""}
            for i in range(60)]
    sc = StorageManager(t, many, [{"name": "SD card", "free": 112e9, "total": 256e9}], selected={"g3"}, focus=0)
    s = pg.Surface((t.w, t.h))
    sc.draw_page(s)
    assert sc.first == 0
    for _ in range(30):
        sc.handle(DOWN)
    sc.draw_page(s)
    assert 0 < sc.first <= sc.focus                                   # the focused row scrolled into view
    StorageManager(t, [], []).draw_page(s)                            # "No installed games."


def _app(me_extra=None):
    saved, said, asked, went = [], [], [], []
    inst_calls, dropped = [], []
    sc = types.SimpleNamespace(selected=set(), sort="size", items=[], drives=[], handled=[],
                               selected_mb=lambda: 0)
    sc.handle = lambda act: sc.handled.append(act)
    sc.set_items = lambda items: went.append(("items", len(items)))
    me = types.SimpleNamespace(scene=sc, cfg={}, inst=types.SimpleNamespace(
        index={}, uninstall=lambda gid: (inst_calls.append(gid), gid != "bad")[1]),
        lib=types.SimpleNamespace(games=[]), say=lambda m, error=False: said.append((m, error)),
        confirm=lambda *a, **k: asked.append((a, k)), go_settings=lambda: went.append("settings"),
        _drop_steam_tile=lambda gid: dropped.append(gid))
    me._storage_uninstall = lambda ids: app_storage.StorageMixin._storage_uninstall(me, ids)
    me.dropped = dropped
    return me, sc, saved, said, asked, went, inst_calls


def test_app_buttons_confirm_uninstall_and_remember_the_sort(monkeypatch):
    saved = []
    monkeypatch.setattr(config, "save", lambda cfg: saved.append(dict(cfg)))
    monkeypatch.setattr(SM, "entries", lambda games, index: [])
    monkeypatch.setattr(SM, "drives", lambda: [])
    me, sc, _s, said, asked, went, calls = _app()
    app_storage.StorageMixin._h_storage(me, B)
    assert went == ["settings"]
    n_said = len(said)
    app_storage.StorageMixin._h_storage(me, X)                           # nothing selected: X does nothing at all
    assert len(said) == n_said and not asked
    sc.selected, sc.selected_mb = {"b", "a"}, (lambda: 5200)
    app_storage.StorageMixin._h_storage(me, X)
    (title, body, action, fn), kw = asked[0][0][:4], asked[0][1]
    assert title == "Uninstall 2 games?" and body[0] == "Frees about 5.2 GB." and action == "Uninstall"
    assert "main" not in kw                                               # the red, destructive button
    assert calls == []                                                    # nothing happens before the confirm
    fn()
    assert calls == ["a", "b"] and sc.selected == set()
    assert said[-1] == ("2 games uninstalled. Freeing 0 MB.", False)      # (sizes come from the scene's items)
                                                              # Y changes the order: remembered
    sc.handle = lambda act: setattr(sc, "sort", "az")
    app_storage.StorageMixin._h_storage(me, Y)
    assert me.cfg["storage_sort"] == "az" and saved[-1]["storage_sort"] == "az"


def test_one_failed_uninstall_is_said_plainly_and_the_rest_still_goes(monkeypatch):
    monkeypatch.setattr(SM, "entries", lambda games, index: [])
    monkeypatch.setattr(SM, "drives", lambda: [])
    me, sc, _s, said, _asked, _went, calls = _app()
    sc.items = [{"id": "a", "size_mb": 900}, {"id": "bad", "size_mb": 100}, {"id": "c", "size_mb": 50}]
    app_storage.StorageMixin._storage_uninstall(me, ["a", "bad", "c"])
    assert calls == ["a", "bad", "c"]                                     # one failing (SD card out) stops nothing
    assert said[-1] == ("Couldn't uninstall some games. Is the SD card in?", True)


def test_settings_has_the_manage_games_row_in_storage():
    sc = Settings.__new__(Settings)
    sc.v = {"update": ("v", ""), "last_sync": "now", "install_label": "SD card", "prefix_size": "1 game",
            "proton": "Auto", "manage": "12 games · 38.4 GB"}
    groups = dict((n, rows) for n, _, rows in sc.groups())
    storage = groups["Storage"]
    assert [r[0] for r in storage] == ["Install location", "Saves of uninstalled games", "Manage games"]
    assert storage[2][1] == "12 games · 38.4 GB" and Settings.ACTION["Manage games"] == "Open"


def test_epic_uninstalls_never_run_together(monkeypatch):
    """Reviewer v0.9.23: legendary rewrites installed.json on every uninstall; Manage games can start several at once."""
    import threading
    import time
    from itch_deck.stores import epic
    st = epic.EpicStore.__new__(epic.EpicStore)
    running, peak = [0], [0]

    def fake_run(args, timeout=0, **k):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        time.sleep(0.05)
        running[0] -= 1
    st._run = fake_run
    st.ready = lambda: True
    st.installed = lambda: {"a": 1, "b": 1, "c": 1, "d": 1}
    threads = [threading.Thread(target=st.uninstall, args=(n,)) for n in "abcd"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak[0] == 1


def test_back_goes_where_settings_came_from_and_failed_games_stay_ticked(monkeypatch):
    monkeypatch.setattr(SM, "entries", lambda games, index: [])
    monkeypatch.setattr(SM, "drives", lambda: [])
    me, sc, _s, said, _asked, went, calls = _app()
    me.settings_back = "game"
    me.go_settings = lambda: setattr(me, "settings_back", "storage")      # what App.go_settings does
    app_storage.StorageMixin._h_storage(me, B)
    assert me.settings_back == "game"                                      # not "storage": B twice returns to the game
    sc.items = [{"id": "a", "size_mb": 10}, {"id": "bad", "size_mb": 20}]
    sc.selected = {"a", "bad"}
    app_storage.StorageMixin._storage_uninstall(me, ["a", "bad"])
    assert sc.selected == {"bad"} and said[-1][1] is True                  # the failed one is still ticked


def test_uninstalling_in_manage_games_also_drops_the_steam_tiles():
    """v0.9.25 (Omri, Deck test): an uninstalled game stayed in Steam."""
    me, sc, _s, said, _asked, _went, calls = _app()
    sc.items = [{"id": "a", "size_mb": 10}, {"id": "bad", "size_mb": 20}, {"id": "c", "size_mb": 5}]
    sc.selected = {"a", "bad", "c"}
    app_storage.StorageMixin._storage_uninstall(me, ["a", "bad", "c"])
    assert me.dropped == ["a", "c"]                                        # not the one that failed
