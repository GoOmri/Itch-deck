"""Art and info for your own DOS games (v0.9.27): name cleaning, choosing the right GOG product, the 30 day cache,
the title card, and "the folder's own cover always wins". Nothing here uses the network: GOG's answers are fixed
fake data and every download is a stub (tests/conftest.py also refuses the real network)."""
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
from itch_deck import dosart, dosgames, library, net, paths  # noqa: E402
from itch_deck import installer as I  # noqa: E402


def P(id_, title, year, kind="game", cover=True):
    return {"id": id_, "slug": title.lower().replace(" ", "_"), "title": title, "productType": kind,
            "releaseDate": f"{year}.01.01", "storeReleaseDate": "2019-05-05",
            "coverVertical": f"https://img.test/{id_}_v.jpg" if cover else None,
            "coverHorizontal": f"https://img.test/{id_}_h.jpg",
            "screenshots": ["https://img.test/{formatter}.jpg"], "features": []}


CATALOG = [
    P("1", "DOOM (1993)", 1993), P("2", "DOOM II", 1994), P("3", "DOOM 3", 2004), P("4", "DOOM", 2016),
    P("5", "DOOM + DOOM II", 2015, "pack"),
    P("10", "Commander Keen Complete Pack", 2014, "pack"),
    P("20", "Dangerous Dave in the Haunted Mansion", 1991), P("21", "Dave the Diver", 2023),
    P("30", "Blood: Fresh Supply", 1997), P("31", "Blood II: The Chosen", 1998),
    P("32", "Blood Omen: Legacy of Kain", 1996),
    P("40", "Wolfenstein 3D", 1992), P("41", "Return to Castle Wolfenstein", 2001),
]


def fake_fetch(catalog=CATALOG, calls=None):
    def fetch(url):
        if calls is not None:
            calls.append(url)
        assert url.startswith("https://catalog.gog.com/v1/catalog?")
        return {"products": catalog}
    return fetch


def found(name, catalog=CATALOG):
    m = dosart.find(name, fake_fetch(catalog))
    return m["id"] if m else None


# --- name cleaning ------------------------------------------------------------------------------
def test_cleaning_drops_signs_versions_and_noise():
    assert dosart.parse("Prince_of_Persia_v1.1_[cracked]")["text"] == "prince of persia"
    assert dosart.parse("Wolfenstein 3D (TM) shareware")["text"] == "wolfenstein 3d"
    assert dosart.parse("Duke Nukem™ (R) 3D")["text"] == "duke nukem 3d"
    assert dosart.parse("Stunts version 1.1 (c) 1990")["text"] == "stunts"
    assert dosart.parse("Pokémon & Friends")["text"] == "pokemon and friends"
    assert dosart.parse("Lemmings.registered.cd.DOS")["text"] == "lemmings"
    assert dosart.parse("DOOM2.EXE v1.9")["text"] == "doom 2"
    assert dosart.parse("R-Type")["text"] == "r type"             # a lone R is not a sign
    assert dosart.parse("Full Throttle")["text"] == "full throttle"   # "full" as the first word is the name
    assert dosart.parse("  Ka__boom  ")["text"] == "ka boom"


def test_year_is_read_before_the_group_is_dropped():
    assert dosart.parse("Doom (1993)")["year"] == 1993
    assert dosart.parse("Cool Game [shareware 1991]")["year"] == 1991
    assert dosart.parse("Doom 1993")["year"] == 1993
    assert dosart.parse("Doom (2016)")["year"] is None            # not a DOS-era year
    assert dosart.parse("Doom")["year"] is None
    assert dosart.parse("1942")["text"] == "1942" and dosart.parse("1942")["year"] is None


def test_sequel_numbers():
    assert dosart.parse("Doom II")["num"] == 2
    assert dosart.parse("Keen 3")["num"] == 3
    assert dosart.parse("Commander Keen 1")["num"] == 1
    assert dosart.parse("Doom")["num"] is None
    assert dosart.parse("Wolfenstein 3D")["num"] is None
    assert dosart.parse("7th Guest")["num"] is None


def test_queries_have_alternative_forms():
    q = dosart.queries(dosart.parse("Commander_Keen_-_Invasion_of_the_Vorticons"))
    assert q[0] == "commander keen invasion of the vorticons" and "commander keen" in q and "keen" in q
    assert len(q) <= 4
    assert "doom 2" in dosart.queries(dosart.parse("Doom II"))


# --- choosing -----------------------------------------------------------------------------------
def test_doom_doom2_doom3_do_not_mix():
    assert found("Doom (1993)") == "1"                 # year 1993, not the 2016 game
    assert found("Doom") == "1"                        # no year: the original beats the 2016 one
    assert found("Doom II") == "2"
    assert found("DOOM2") == "2"
    assert found("Doom 3") == "3"


def test_keen_only_a_pack_exists_and_is_used_for_every_episode():
    for name in ("Commander Keen 1", "Keen 1", "Keen 2", "Keen 3", "Commander Keen",
                 "Commander Keen - Invasion of the Vorticons", "Keen_4_Secret_of_the_Oracle"):
        assert found(name) == "10", name


def test_a_single_product_beats_a_pack():
    cat = CATALOG + [P("11", "Commander Keen 4: Secret of the Oracle", 1991)]
    assert found("Keen 4", cat) == "11"
    assert found("Keen 1", cat) == "10"                # Keen 1 is not Keen 4: the pack is all there is


def test_years_decide_and_weak_matches_give_nothing():
    assert found("Wolfenstein 3D") == "40"
    assert found("Wolfenstein 3D (1992)") == "40"
    two = [P("50", "Alone in the Dark", 1992), P("51", "Alone in the Dark", 2008)]
    assert found("Alone in the Dark", two) == "50"                    # earlier release first
    assert found("Alone in the Dark [1993]", two) == "50"             # +/-1 year is allowed
    assert found("Dave") is None                                      # one common word: too weak
    assert found("Dangerous Dave") == "20"
    assert found("Blood") == "30"
    assert found("Blood 2") == "31"
    assert found("Qwerty Zxcvb Nothing") is None
    assert found("Some Made Up Game 1995") is None
    assert found("") is None and found("v1.1 (1990)") is None


def test_two_different_games_that_fit_equally_give_no_match():
    cat = [P("60", "Star Siege Alpha", 1995), P("61", "Star Siege Omega", 1996)]
    assert found("Star Siege", cat) is None


def test_a_missing_number_falls_back_to_the_name_without_it():
    cat = [P("70", "Dangerous Dave", 1990)]
    assert found("Dangerous Dave 2", cat) == "70"      # last try: the name without its number
    assert found("Dangerous Dave 2", [P("71", "Dangerous Dave 3", 1991)]) is None


def test_broken_answers_are_tolerated():
    assert dosart.find("Doom", lambda u: None) is None
    assert dosart.find("Doom", lambda u: {"products": [None, 3, {"title": "x"}, {"id": 1}]}) is None
    assert dosart.find("Doom", lambda u: {"nothing": 1}) is None


# --- the library: cache, covers, text, own cover --------------------------------------------------
def png(path, size=(300, 450), color=(200, 40, 40)):
    s = pg.Surface(size)
    s.fill(color)
    pg.image.save(s, str(path))
    return path.read_bytes()


class Net:
    """Stubs every GOG call. calls = list of urls."""

    def __init__(self, monkeypatch, tmp_path, catalog=CATALOG):
        self.calls, self.catalog = [], catalog
        self.pic = png(tmp_path / "pic.png")
        monkeypatch.setattr(net, "get_json", self.get_json)
        monkeypatch.setattr(net, "get", self.get)

    def get_json(self, url, key=None, timeout=20):
        self.calls.append(url)
        if url.startswith("https://catalog.gog.com/"):
            return {"products": self.catalog}
        if url.startswith("https://api.gog.com/products/"):
            return {"description": {"full": "<p>Billy Blaze saves the galaxy.</p><p>Pogo!</p>"},
                    "screenshots": [{"formatter_template_url": "https://img.test/s_{formatter}.jpg"}]}
        raise net.Offline("no stub for " + url)

    def get(self, url, key=None, timeout=20, **k):
        self.calls.append(url)
        if url.startswith("https://img.test/"):
            return self.pic
        raise net.Offline("no stub for " + url)

    def catalog_calls(self):
        return [c for c in self.calls if "catalog.gog.com" in c]


def lib_with(tmp_path, title="Commander Keen 1", cover=None):
    paths.use_root(tmp_path / "home")
    lib = library.Library(None)
    entry = {"id": dosgames.game_id(title), "title": title, "cover": cover}
    lib.set_dos_games([entry])
    return lib, entry


def run_jobs(lib):
    lib._worker and lib._worker.join(timeout=20)
    return lib


def no_sleep(monkeypatch):
    monkeypatch.setattr(library.time, "sleep", lambda s: None)


def test_a_match_gives_cover_text_screens_and_is_cached(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    st = Net(monkeypatch, tmp_path)
    lib, e = lib_with(tmp_path)
    g = lib.by_id(e["id"])
    run_jobs(lib)
    assert g["cover_file"] and str(paths.DATA / "dosart") in g["cover_file"]    # our own folder, not the player's
    assert g["description"] == ["Billy Blaze saves the galaxy.", "Pogo!"]
    assert g["details_from"] == "GOG" and g["screens"] == 1 and g["inputs"] == ["Keyboard", "Mouse"]
    n = len(st.catalog_calls())
    assert n >= 1
    # a new start of the app: everything comes from files, GOG is not asked again
    lib2 = library.Library(None)
    lib2.set_dos_games([e])
    run_jobs(lib2)
    assert len(st.catalog_calls()) == n
    g2 = lib2.by_id(e["id"])
    assert g2["cover_file"] and g2["description"] == g["description"]


def test_no_match_is_cached_too_and_gives_the_title_card(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    st = Net(monkeypatch, tmp_path)
    lib, e = lib_with(tmp_path, "Zxqv Plorb")
    run_jobs(lib)
    g = lib.by_id(e["id"])
    assert not g.get("cover_file") and not g.get("description")
    n = len(st.catalog_calls())
    assert n >= 1
    lib.set_dos_games([e])                             # a scan again (Refresh / Y)
    run_jobs(lib)
    lib.queue_dosart()
    run_jobs(lib)
    assert len(st.catalog_calls()) == n                # "no match" is remembered for 30 days
    pg.init()
    pg.display.set_mode((64, 64))
    from itch_deck import theme
    from itch_deck.ui import widgets as W
    t = theme.Theme(pg, (1280, 800))
    img = W.cover(t, g, (315, 250))
    assert img.get_size() == (315, 250)
    assert img.get_at((157, 20))[:3] != (0, 0, 0)                   # drawn, not empty
    assert W.title_card(t, g, (315, 250)) is img        # the card, made once


def test_cache_runs_out_after_30_days_and_a_new_name_is_asked_again(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    st = Net(monkeypatch, tmp_path)
    lib, e = lib_with(tmp_path)
    run_jobs(lib)
    n = len(st.catalog_calls())
    old = dt.datetime.now().astimezone() - dt.timedelta(days=31)
    lib._dosart[e["id"]]["at"] = old.isoformat(timespec="seconds")
    lib.queue_dosart()
    run_jobs(lib)
    assert len(st.catalog_calls()) > n                 # 31 days: asked again
    n = len(st.catalog_calls())
    lib.games[0]["title"] = "Commander Keen 2"         # the folder got another name
    lib.queue_dosart()
    run_jobs(lib)
    assert len(st.catalog_calls()) > n


def test_refresh_may_bypass_the_cache_only_once_a_day(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    st = Net(monkeypatch, tmp_path)
    lib, e = lib_with(tmp_path)
    run_jobs(lib)
    n = len(st.catalog_calls())
    lib.queue_dosart(force=True)                       # asked just now: left alone
    run_jobs(lib)
    assert len(st.catalog_calls()) == n
    lib._dosart[e["id"]]["at"] = (dt.datetime.now().astimezone() - dt.timedelta(days=2)).isoformat(timespec="seconds")
    lib.queue_dosart(force=True)
    run_jobs(lib)
    assert len(st.catalog_calls()) > n
    n = len(st.catalog_calls())
    lib.queue_dosart(force=True)                       # and not again the same day
    run_jobs(lib)
    assert len(st.catalog_calls()) == n


def test_the_folders_own_cover_always_wins(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    st = Net(monkeypatch, tmp_path)
    folder = tmp_path / "dos" / "Commander Keen 1"
    folder.mkdir(parents=True)
    own = folder / "cover.png"
    own_bytes = png(own, (200, 300), (10, 200, 10))
    lib, e = lib_with(tmp_path, cover=own)
    g = lib.by_id(e["id"])
    run_jobs(lib)
    assert os.path.dirname(g["cover_file"]) == str(paths.COVERS)          # the copy of cover.png
    assert g["description"]                                               # the text still comes from GOG
    assert not any("_v.jpg" in c for c in st.calls)                       # the GOG cover was not even fetched
    assert own.read_bytes() == own_bytes and sorted(os.listdir(folder)) == ["cover.png"]
    lib2 = library.Library(None)                                          # next start: still the folder's
    assert os.path.dirname(lib2.by_id(e["id"])["cover_file"]) == str(paths.COVERS)


def test_nothing_is_written_into_the_players_folder(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    Net(monkeypatch, tmp_path)
    paths.use_root(tmp_path / "home")
    root = tmp_path / "dos"
    d = root / "Commander Keen 1"
    d.mkdir(parents=True)
    (d / "KEEN1.EXE").write_bytes(b"MZ" + b"x" * 100)
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    inst = I.Installer.__new__(I.Installer)          # only the DOS scan is used
    lib = library.Library(None)
    inst.lib, inst.index, inst.root_fn = lib, {}, lambda: root
    inst.dos_roots = lambda: [root]
    inst.dos_root = lambda: root
    inst.apply_dos(inst.scan_dos())
    run_jobs(lib)
    assert lib.games and lib.games[0]["store"] == "dos" and lib.games[0].get("description")
    after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    assert after == before


def test_failures_fall_back_and_cache_nothing(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    paths.use_root(tmp_path / "home")

    def boom(*a, **k):
        raise net.Offline("no route")
    monkeypatch.setattr(net, "get_json", boom)
    lib = library.Library(None)
    e = {"id": dosgames.game_id("Doom"), "title": "Doom", "cover": None}
    lib.set_dos_games([e])
    run_jobs(lib)
    g = lib.by_id(e["id"])
    assert not g.get("cover_file") and not lib._dosart            # offline: nothing is cached, asked again later
    assert not (paths.DATA / "dosart.json").exists()


def test_a_cover_that_is_not_a_picture_is_dropped(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    st = Net(monkeypatch, tmp_path)
    st.pic = b"<html>error</html>"
    lib, e = lib_with(tmp_path)
    run_jobs(lib)
    g = lib.by_id(e["id"])
    assert not g.get("cover_file")
    assert list((paths.DATA / "dosart").glob("*")) == []
    assert g["description"]                                  # the text is still used


def test_hidden_games_are_not_looked_up(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    st = Net(monkeypatch, tmp_path)
    paths.use_root(tmp_path / "home")
    lib = library.Library(None)
    lib.hidden = {dosgames.game_id("Doom")}
    lib.set_dos_games([{"id": dosgames.game_id("Doom"), "title": "Doom", "cover": None}])
    run_jobs(lib)
    assert st.catalog_calls() == []


def test_cache_file_format(tmp_path, monkeypatch):
    no_sleep(monkeypatch)
    Net(monkeypatch, tmp_path)
    lib, e = lib_with(tmp_path, "Doom II")
    run_jobs(lib)
    d = json.loads((paths.DATA / "dosart.json").read_text())
    assert d[e["id"]]["match"]["id"] == "2" and d[e["id"]]["key"] == "Doom II"


def test_tall_art_is_shown_whole_not_cut(tmp_path):
    pg.init()
    pg.display.set_mode((64, 64))
    from itch_deck import theme
    from itch_deck.ui import widgets as W
    t = theme.Theme(pg, (1280, 800))
    f = tmp_path / "tall.png"
    s = pg.Surface((300, 450))
    s.fill((255, 0, 0))
    pg.image.save(s, str(f))
    img = W.cover(t, {"id": "x1", "title": "X", "store": "dos", "cover_file": str(f)}, (315, 250))
    assert img.get_at((157, 125))[0] > 240         # the picture in the middle
    assert img.get_at((5, 125))[0] < 200           # dark blurred sides, not more red
    wide = W.cover(t, {"id": "x2", "title": "X", "store": "itch", "cover_file": str(f)}, (315, 250))
    assert wide.get_at((5, 125))[0] > 240          # other stores: filled as before
