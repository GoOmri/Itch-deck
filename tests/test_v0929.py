"""v0.9.29: better GOG search, Steam as a second source, short text, scroll marks, closed-at-once message,
stay-open switch, setup toast, DOS summary for Send logs. No network (tests/conftest.py refuses it)."""
import os
import sys
import types
import urllib.parse

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dosart, library, net, paths  # noqa: E402


def G(id_, title, year, kind="game"):
    return {"id": id_, "slug": title.lower().replace(" ", "_"), "title": title, "productType": kind,
            "releaseDate": f"{year}.01.01", "coverHorizontal": f"https://img.test/{id_}_h.jpg",
            "coverVertical": f"https://img.test/{id_}_v.jpg"}


KEEN_PACK = G("2070676386", "Commander Keen Complete Pack", 2014, "pack")
DOOM_REAL = [G("101", "DOOM + DOOM II", 2024, "pack"), G("102", "DOOM", 2016), G("103", "DOOM 3", 2012, "pack"),
             G("104", "DOOM Eternal", 2020), G("105", "DOOM 64", 2020, "pack"), G("106", "DOOM 3: Phobos", 2005)]
# what GOG's catalog answers for a query (checked by hand on 18 Nov); anything else answers nothing
ANSWERS = {
    "commander keen": [KEEN_PACK], "commander keen 2": [KEEN_PACK], "commander keen 4": [KEEN_PACK],
    "bio menace": [G("300", "Bio Menace", 1993)], "dangerous dave": [G("400", "Dangerous Dave Pack", 1991, "pack")],
    "doom": DOOM_REAL, "doom ii": DOOM_REAL, "doom 2": DOOM_REAL,
    "blood": [G("500", "Blood Bowl 2", 2015), G("501", "Bloodstained: Ritual of the Night", 2019)],
    "raptor": [G("510", "Raptor Run", 2019)],
}


def gog_fetch(asked=None):
    def fetch(url):
        q = urllib.parse.unquote(url.split("query=like%3A", 1)[1].split("&", 1)[0])
        if asked is not None:
            asked.append(q)
        return {"products": ANSWERS.get(q, [])}
    return fetch


STEAM = {
    "duke nukem 3d": [{"id": 225140, "name": "Duke Nukem 3D: Megaton Edition", "type": "app"},
                      {"id": 9, "name": "Duke Nukem 3D Soundtrack", "type": "app"}],
    "blood": [{"id": 1010750, "name": "Blood: Fresh Supply", "type": "app"}, {"id": 5, "name": "Blood Bowl", "type": "app"}],
    "raptor": [{"id": 610, "name": "Raptor: Call of the Shadows", "type": "app"}],
    "duke nukem 2": [{"id": 3, "name": "Duke Nukem 2", "type": "app"}, {"id": 4, "name": "Duke Nukem 3D", "type": "app"}],
    "indiana jones and the fate of atlantis": [{"id": 7, "name": "Indiana Jones and the Fate of Atlantis", "type": "app"}],
}


def steam_search(term):
    return STEAM.get(term, [])


def any_(name):
    return dosart.find_any(name, gog_fetch(), steam_search)


# --- 1: better GOG searching ------------------------------------------------------------------------------------
def test_keen_folders_match_the_pack_and_the_dropped_number_gives_art_only():
    for name in ("Commander Keen 1 Marooned on Mars (1990)", "Commander Keen 3 Keen Must Die (1990)(Apogee Software)",
                 "Commander Keen 5 The Armageddon Machine", "Commander Keen 6 Aliens Ate My Baby Sitter"):
        m = any_(name)
        assert m and m["id"] == "2070676386" and m["source"] == "gog" and m.get("fallback") is True, name
    for name in ("Commander Keen 2", "Commander Keen 4"):
        m = any_(name)
        assert m and m["id"] == "2070676386" and not m.get("fallback"), name       # GOG found it with the number


def test_the_search_order_cuts_after_the_number_then_the_series_name():
    asked = []
    dosart.find("Commander Keen 3 Keen Must Die (1990)(Apogee Software)", gog_fetch(asked))
    assert asked[0] == "commander keen 3 keen must die"
    assert "commander keen 3" in asked and asked.index("commander keen 3") < asked.index("commander keen")
    assert asked[-1] == "commander keen"


def test_bio_menace_episode_1_is_bio_menace():
    p = dosart.parse("Bio Menace Episode 1 (1993)(Apogee Software)")
    assert p["text"] == "bio menace" and p["year"] == 1993 and p["num"] is None
    m = any_("Bio Menace Episode 1 (1993)(Apogee Software)")
    assert m["id"] == "300" and not m.get("fallback")
    assert dosart.display("Bio Menace Episode 1 (1993)(Apogee Software)")[0] == "Bio Menace Episode 1"   # title stays


def test_the_shorthand_folder_names_find_the_game():
    for name in ("dave", "dave2", "Dave"):
        m = dosart.find(name, gog_fetch())
        assert m and m["id"] == "400", name


def test_doom_picks_the_pack_and_blood_raptor_stay_unmatched_on_gog():
    assert any_("Doom (1993)")["id"] == "101" and any_("Doom II")["id"] == "101"
    for name in ("Blood (1997)(Monolith)", "Raptor", "Duke Nukem 3D (1996)(3D Realms)", "Duke Nukem 2 (1991)"):
        assert dosart.find(name, gog_fetch()) is None, name


# --- 2: Steam as the second source ----------------------------------------------------------------------------------
def test_steam_matches_only_strong_titles_and_ignores_the_year():
    m = any_("Duke Nukem 3D (1996)(3D Realms)")
    assert m["source"] == "steam" and m["id"] == "225140" and m["cover"].endswith("/225140/header.jpg")
    assert any_("Blood (1997)(Monolith)")["id"] == "1010750"            # "Blood" = start of "Blood: Fresh Supply"
    assert any_("Raptor")["id"] == "610"
    assert any_("Duke Nukem 2 (1991)")["id"] == "3"                     # a numbered folder: the same number only
    assert any_("Indiana Jones and the Fate of Atlantis")["source"] == "steam"
    assert any_("dosbox-ssf2t") is None and any_("msppcv12") is None   # not games


def test_steam_needs_the_same_number_and_skips_soundtracks():
    assert dosart.find_steam("Duke Nukem 3", lambda t: STEAM["duke nukem 2"]) is None
    assert dosart.find_steam("Duke Nukem 3D", lambda t: [{"id": 9, "name": "Duke Nukem 3D Soundtrack", "type": "app"}]) is None
    assert dosart.find_steam("Raptor", lambda t: [{"id": 1, "name": "Raptor Rampage Deluxe", "type": "app"}]) is None


def test_gog_art_only_loses_to_a_strong_steam_match():
    steam = [{"id": 77, "name": "Commander Keen 5", "type": "app"}]
    assert dosart.find("Commander Keen 5", gog_fetch())["fallback"] is True          # GOG alone: art only
    m = dosart.find_any("Commander Keen 5", gog_fetch(), lambda t: steam)
    assert m["source"] == "steam" and m["id"] == "77"


# --- 3: short text ------------------------------------------------------------------------------------------------
DOOM_TEXT = ("<b>The original DOOM</b> and DOOM II are back with new ports.<br>Fight through hordes of demons on Mars "
             "and in Hell. Every level is a maze of secrets and traps.<br><br>Owners Receive:<br>- DOOM<br>- DOOM II<br>"
             "- TNT: Evilution<br>- The Plutonia Experiment<br>Play online with friends.<br>Key features of this combined "
             "product: more words.")


def test_the_doom_block_is_cut_at_the_first_filler_line():
    from itch_deck.stores import steam
    paras = steam.html_paras(DOOM_TEXT)
    out = dosart.short_text(paras)
    assert len(out) == 1
    t = out[0]
    assert "demons on Mars" in t and "maze of secrets" in t
    for bad in ("Owners", "TNT", "Plutonia", "Play online", "combined", "Key features"):
        assert bad not in t, bad
    assert len(t) <= 700


def test_filler_lines_and_bullets_stop_the_text():
    assert dosart.short_text(["A fast game.\nIncludes two games.\nMore."]) == ["A fast game."]
    assert dosart.short_text(["A fast game.\n- one\n- two"]) == ["A fast game."]
    assert dosart.short_text(["A fast game.\nWhat is in the box:\nNothing."]) == ["A fast game."]
    assert dosart.short_text(["A fast game.\n1. First\n2. Second"]) == ["A fast game."]
    assert dosart.short_text(["Bonus: stuff.", "Real text. More text."]) == ["Real text. More text."]
    assert dosart.short_text([]) == [] and dosart.short_text(["Includes DOOM + DOOM II."]) == []


def test_old_saved_text_is_fetched_and_cut_again_once(tmp_path, monkeypatch):
    import json
    from itch_deck import net as N
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    calls = []

    def get_json(url, key=None, timeout=20):
        calls.append(url)
        if "catalog.gog.com" in url:
            return {"products": [G("7", "Doom", 1993)]}
        if "api.gog.com" in url:
            return {"description": {"full": DOOM_TEXT}, "screenshots": []}
        return {"items": []}
    monkeypatch.setattr(N, "get_json", get_json)
    monkeypatch.setattr(N, "get", lambda *a, **k: b"not a picture")
    lib = library.Library(None)
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
    lib._worker and lib._worker.join(timeout=20)
    page = paths.PAGES / "d1.json"
    d = json.loads(page.read_text())
    assert d["text_ver"] == dosart.TEXT_VER and "Owners" not in d["description"][0]
    d.update({"text_ver": 2, "description": ["Long old text. " * 80]})              # what v0.9.27 / 0.9.28 saved
    page.write_text(json.dumps(d))
    n = len([c for c in calls if "api.gog.com" in c])
    lib2 = library.Library(None)
    lib2.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
    lib2._worker and lib2._worker.join(timeout=20)
    assert len([c for c in calls if "api.gog.com" in c]) == n + 1                    # once
    assert len(json.loads(page.read_text())["description"][0]) < 700
    lib3 = library.Library(None)
    lib3.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
    lib3._worker and lib3._worker.join(timeout=20)
    assert len([c for c in calls if "api.gog.com" in c]) == n + 1                    # and not again


def test_a_steam_match_gives_header_short_text_screens_and_the_from_steam_label(tmp_path, monkeypatch):
    import json
    from itch_deck import net as N
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    s = pg.Surface((460, 215))
    s.fill((9, 99, 199))
    pic = tmp_path / "h.png"
    pg.image.save(s, str(pic))
    data = pic.read_bytes()
    got = []

    def get_json(url, key=None, timeout=20):
        got.append(url)
        if "catalog.gog.com" in url:
            return {"products": []}
        if "storesearch" in url:
            return {"items": STEAM["raptor"]}
        if "appdetails" in url:
            return {"610": {"success": True, "data": {
                "short_description": "Fly a fighter through a hostile sky. Blast everything.",
                "about_the_game": "<p>Long text.</p>", "header_image": "x", "genres": [{"description": "Action"}],
                "screenshots": [{"path_full": "https://img.test/s1.jpg"}]}}}
        raise net.Offline("no stub " + url)
    monkeypatch.setattr(N, "get_json", get_json)
    monkeypatch.setattr(N, "get", lambda url, key=None, timeout=20, **k: data)
    lib = library.Library(None)
    lib.set_dos_games([{"id": "d1", "title": "Raptor", "cover": None, "folder": "Raptor"}])
    lib._worker and lib._worker.join(timeout=20)
    g = lib.by_id("d1")
    assert g["title"] == "Raptor" and "dosart" in g["cover_file"] and g["screens"] == 1
    assert g["description"] == ["Fly a fighter through a hostile sky. Blast everything."]
    assert g["details_from"] == "Steam"
    e = json.loads((paths.DATA / "dosart.json").read_text())["d1"]
    assert e["match"]["source"] == "steam" and e["match"]["id"] == "610"
    n = len(got)
    lib2 = library.Library(None)
    lib2.set_dos_games([{"id": "d1", "title": "Raptor", "cover": None, "folder": "Raptor"}])
    lib2._worker and lib2._worker.join(timeout=20)
    assert len(got) == n                                                              # cached 30 days


def test_steam_failures_fall_back_and_nothing_is_written_to_the_players_folder(tmp_path, monkeypatch):
    from itch_deck import net as N
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    folder = tmp_path / "dos" / "Raptor"
    folder.mkdir(parents=True)
    (folder / "R.EXE").write_bytes(b"MZ")

    def get_json(url, key=None, timeout=20):
        if "catalog.gog.com" in url:
            return {"products": []}
        if "storesearch" in url:
            return {"items": STEAM["raptor"]}
        raise net.Offline("HTTP 500")                      # appdetails fails
    monkeypatch.setattr(N, "get_json", get_json)
    monkeypatch.setattr(N, "get", lambda *a, **k: b"junk")
    lib = library.Library(None)
    lib.set_dos_games([{"id": "d1", "title": "Raptor", "cover": None, "folder": "Raptor"}])
    lib._worker and lib._worker.join(timeout=20)
    g = lib.by_id("d1")
    assert not g.get("cover_file") and not g.get("description")                      # the title card
    assert sorted(os.listdir(folder)) == ["R.EXE"]
