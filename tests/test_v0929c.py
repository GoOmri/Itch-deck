"""v0.9.29 review round: Steam wrong-match safety, Part III stays a number, Steam failures, one-program message."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dosart, library, net, paths  # noqa: E402
from test_v0929 import G, gog_fetch  # noqa: E402


def item(id_, name):
    return {"id": id_, "name": name, "type": "app"}


def steam_with(answers, years=None):
    """(search, details) stubs: answers = {term: items}; years = {appid: release year}."""
    years = years or {}
    return (lambda term: answers.get(term, []),
            lambda appid: {"year": years.get(appid), "header": f"https://shared.test/{appid}/header.jpg?t=1"})


def steam_find(name, answers, years=None):
    s, d = steam_with(answers, years)
    return dosart.find_steam(name, s, d)


# --- 1: Steam wrong-match safety -----------------------------------------------------------------------------------
def test_two_subtitle_candidates_mean_no_match_the_dune_and_prince_of_persia_cases():
    dune = {"dune": [item(1, "Dune: Awakening"), item(2, "Dune: Spice Wars"), item(3, "Dune Sandbox")]}
    assert steam_find("Dune (1992)", dune) is None
    pop = {"prince of persia": [item(4, "Prince of Persia: The Lost Crown"), item(5, "Prince of Persia: The Sands of Time")]}
    assert steam_find("Prince of Persia (1989)", pop) is None
    assert dosart.find("Prince of Persia (1989)", gog_fetch()) is None            # GOG said no match too
    two_same = {"alone in the dark": [item(6, "Alone in the Dark"), item(7, "Alone in the Dark")]}
    assert steam_find("Alone in the Dark", two_same) is None                   # two same-named apps: not guessed


def test_exactly_one_subtitle_match_is_still_accepted():
    m = steam_find("Raptor", {"raptor": [item(610, "Raptor: Call of the Shadows"), item(9, "Raptor Rampage")]})
    assert m and m["id"] == "610" and not m.get("fallback")
    assert steam_find("Blood", {"blood": [item(1, "Blood: Fresh Supply"), item(5, "Blood Bowl")]})["id"] == "1"


def test_a_far_off_year_gives_art_only_and_the_real_header_address_is_used():
    ans = {"alone in the dark": [item(10, "Alone in the Dark")], "rise of the triad": [item(11, "Rise of the Triad")],
           "duke nukem 3d": [item(434050, "Duke Nukem 3D: 20th Anniversary World Tour")]}
    years = {10: 2024, 11: 2013, 434050: 2016}
    for name, aid in (("Alone in the Dark (1992)", 10), ("Rise of the Triad (1994)", 11), ("Duke Nukem 3D (1996)", 434050)):
        m = steam_find(name, ans, years)
        assert m and m["id"] == str(aid) and m["fallback"] is True, name        # art only
        assert m["cover"] == f"https://shared.test/{aid}/header.jpg?t=1"        # the address Steam answered with
    ok = steam_find("Duke Nukem 3D (2016)", ans, years)                          # the year agrees: full match
    assert ok and not ok.get("fallback")
    plain = steam_find("Duke Nukem 3D", ans, years)                              # no year in the folder: full match
    assert plain and not plain.get("fallback")
    no_year_known = dosart.find_steam("Duke Nukem 3D (1996)", lambda t: ans.get(t, []))     # no details: the old address
    assert no_year_known["cover"].endswith("/434050/header.jpg") and "cdn.akamai" in no_year_known["cover"]


def test_steam_skips_soundtracks_season_passes_demos_betas_and_servers():
    for bad in ("Raptor Soundtrack", "Raptor Sound Track", "Raptor Original Sound", "Raptor OST", "Raptor Season Pass",
                "Raptor DLC", "Raptor Art Book", "Raptor Artbook", "Raptor Demo", "Raptor Playtest", "Raptor Beta",
                "Raptor Dedicated Server", "Raptor Expansion Pass"):
        assert steam_find("Raptor", {"raptor": [item(1, bad)]}) is None, bad
    assert steam_find("Raptor", {"raptor": [item(1, "Raptor")]})["id"] == "1"
    assert steam_find("Betamax", {"betamax": [item(1, "Betamax")]}) is not None       # whole words only


# --- 2: Part III stays a sequel number --------------------------------------------------------------------------------
def test_part_iii_is_a_number_and_episode_is_not():
    assert dosart.parse("Back to the Future Part III (1991)")["num"] == 3
    assert dosart.parse("Bio Menace Episode 1")["num"] is None
    assert dosart.parse("Game Chapter 2")["num"] == 2
    cat = {"back to the future part iii": [G("900", "Back to the Future: The Game - 30th Anniversary Edition", 2015)],
           "back to the future": [G("900", "Back to the Future: The Game - 30th Anniversary Edition", 2015)]}

    def fetch(url):
        import urllib.parse
        q = urllib.parse.unquote(url.split("query=like%3A", 1)[1].split("&", 1)[0])
        return {"products": cat.get(q, [])}
    assert dosart.find("Back to the Future Part III (1991)", fetch) is None
    steam = {"back to the future part iii": [item(1, "Back to the Future: The Game - 30th Anniversary Edition")],
             "back to the future": [item(1, "Back to the Future: The Game - 30th Anniversary Edition")]}
    assert steam_find("Back to the Future Part III (1991)", steam) is None


# --- 3: Steam failures --------------------------------------------------------------------------------------------------
def test_a_steam_error_never_throws_away_a_gog_result():
    def boom(term):
        raise net.Offline("HTTP 500")
    keen = "Commander Keen 5"
    m = dosart.find_any(keen, gog_fetch(), boom)                    # GOG art-only, Steam raising
    assert m["source"] == "gog" and m["fallback"] is True
    full = dosart.find_any("Commander Keen 2", gog_fetch(), boom)   # GOG full match: Steam is not even asked
    assert full["source"] == "gog" and not full.get("fallback")


def test_no_gog_result_and_steam_down_raises_so_nothing_is_cached():
    import pytest

    def boom(term):
        raise net.Offline("HTTP 500")
    with pytest.raises(dosart.SteamUnavailable):
        dosart.find_any("Raptor", gog_fetch(), boom)
    assert dosart.STEAM_STATE["down"] is True


def test_after_a_429_no_more_steam_calls_this_run():
    import pytest
    calls = []

    def search(term):
        calls.append(term)
        raise net.Offline("HTTP 429")
    with pytest.raises(dosart.SteamUnavailable):
        dosart.find_any("Raptor", gog_fetch(), search)
    n = len(calls)
    assert n >= 1
    with pytest.raises(dosart.SteamUnavailable):
        dosart.find_any("Blood", gog_fetch(), search)
    assert len(calls) == n                                          # Steam was not asked again
    assert dosart.find_any("Commander Keen 5", gog_fetch(), search)["source"] == "gog"   # GOG-only results still work


def test_the_library_does_not_cache_a_steam_failure_and_does_not_retry_it_this_run(tmp_path, monkeypatch):
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    gog_calls = []

    def get_json(url, key=None, timeout=20):
        if "catalog.gog.com" in url:
            gog_calls.append(url)
            return {"products": []}
        raise net.Offline("HTTP 429")
    monkeypatch.setattr(net, "get_json", get_json)
    lib = library.Library(None)
    lib.set_dos_games([{"id": "d1", "title": "Raptor", "cover": None, "folder": "Raptor"}])
    lib._worker and lib._worker.join(timeout=20)
    assert not lib._dosart and not (paths.DATA / "dosart.json").exists()     # nothing cached: retried next start
    n = len(gog_calls)
    lib.set_dos_games([{"id": "d1", "title": "Raptor", "cover": None, "folder": "Raptor"}])
    lib._worker and lib._worker.join(timeout=20)
    assert len(gog_calls) == n                                               # and not again in this run


def test_questions_to_one_site_are_paced(tmp_path, monkeypatch):
    paths.use_root(tmp_path / "home")
    slept = []
    monkeypatch.setattr(library.time, "sleep", lambda s: slept.append(s))
    lib = library.Library(None)
    lib._paced("gog", lambda: 1)
    lib._paced("gog", lambda: 2)
    assert slept and 0 < slept[-1] <= library.NET_PAUSE_S
    n = len(slept)
    lib._paced("steam", lambda: 3)                                           # another site: no wait
    assert len(slept) == n


# --- 4: one program: a plain message ------------------------------------------------------------------------------------
def test_one_program_message_does_not_mention_options(tmp_path, monkeypatch):
    from test_v0929b import _app
    a, g, dosbox, runner = _app(tmp_path, monkeypatch, programs=("A.EXE",))
    monkeypatch.setattr(runner, "run", lambda *x, **k: (0, 1.0))
    a.go_game(g)
    a.play(g)
    assert a.scene.toast == "That program closed straight away."
