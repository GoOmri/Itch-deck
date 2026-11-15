"""Sort & filter: the library behind the menu must not move while values change (Omri, v0.7.2)."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402


def _scene():
    pg.init()
    from itch_deck import fake
    from itch_deck.theme import Theme
    from itch_deck.ui.scenes.library import Library
    t = Theme(pg, (1280, 800))
    return t, Library(t, fake.library(), focus=5)


def _page(sc, t):
    s = pg.Surface((t.w, t.h))
    sc.draw_page(s)
    return pg.image.tobytes(s, "RGB")


def test_background_frozen_while_filtering_then_updates():
    t, sc = _scene()
    before = _page(sc, t)
    sc.menu_open()
    frozen = _page(sc, t)
    assert frozen == before
    for label, step in (("Sort", 1), ("Sort", 1), ("Show", 1), ("Length", -1)):
        sc.overlay = sc.overlay[:4] + ([r[0] for r in sc.overlay[3]].index(label),)
        sc.menu_next(label, step)
        assert _page(sc, t) == frozen, label          # nothing moves behind the menu
    sc.overlay = None
    from itch_deck.ui import widgets as W
    W.anim(("tabswipe", id(sc)), 1.0, start=1.0)     # end of the fade: the new result shows
    assert _page(sc, t) != frozen


def test_tabs_all_installed_then_stores():
    from itch_deck.ui.scenes.library import tabs, visible
    assert [k for k, _ in tabs(("itch",))] == ["all", "installed"]       # one store: no store tab
    assert [k for k, _ in tabs(("itch", "epic"))] == ["all", "installed", "itch", "epic"]
    games = [{"id": "1", "title": "A", "platforms": {"linux"}, "store": "epic"},
             {"id": "2", "title": "B", "platforms": {"linux"}, "played": "2026-11-14T10:00:00"},
             {"id": "3", "title": "C", "platforms": {"linux"}, "played": "2026-11-15T10:00:00"}]
    assert [g["id"] for g in visible(games, "epic")] == ["1"]
    assert [g["id"] for g in visible(games, "itch")] == ["2", "3"]        # no "store" = itch
    assert [g["id"] for g in visible(games, sort="played")] == ["3", "2", "1"]


def test_old_recent_tab_falls_back_to_all():
    t, _ = _scene()
    from itch_deck import fake
    from itch_deck.ui.scenes.library import Library
    assert Library(t, fake.library(), filt="recent").filt == "all"
