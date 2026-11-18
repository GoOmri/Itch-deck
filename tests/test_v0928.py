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


class _Lib:
    """The little bit of Library the DOS scan talks to."""

    def __init__(self):
        self.games, self.installs, self.live, self.epic, self.dos = [], {}, {}, None, None

    def apply_installs(self):
        pass

    def set_dos_games(self, entries):
        self.dos = entries

    def by_id(self, gid):
        return None


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
    assert any(t.lower().startswith("deep") for t in names) and any(t.lower().startswith("zipflat") for t in names)


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


# --- 3: clean display titles ----------------------------------------------------------------------
def test_display_titles_are_tidy_and_the_year_is_read_first():
    from itch_deck import dosart
    d = dosart.display
    assert d("Commander Keen 3 Keen Must Die (1990)(Apogee Software)") == ("Commander Keen 3 Keen Must Die", 1990)
    assert d("Blood (1997)(Monolith)") == ("Blood", 1997)
    assert d("dave2") == ("Dave2", None)
    assert d("doom") == ("Doom", None)
    assert d("Prince_of_Persia_v1.1_[cracked]") == ("Prince of Persia", None)
    assert d("Wolfenstein.3D.shareware") == ("Wolfenstein 3D", None)
    assert d("Full Throttle")[0] == "Full Throttle"
    assert d("Pok\u00e9mon (TM) Co")[0] == "Pok\u00e9mon Co"          # accents stay for showing
    assert d("(1990)(x)")[0] == "(1990)(x)"                          # nothing left: the folder name as it is
    assert dosart_search("Blood (1997)(Monolith)") == "Blood (1997)"


def dosart_search(n):
    from itch_deck import dosart
    return dosart.search_name(n)


def test_the_title_changes_but_ids_and_folders_do_not(tmp_path, monkeypatch):
    inst, lib, sd_dos, _ = inst_two_roots(tmp_path, monkeypatch)
    folder = make_game(sd_dos / "Blood (1997)(Monolith)", "BLOOD.EXE")
    before = sorted(p.name for p in folder.parent.iterdir())
    inst.sync_dos()
    e = lib.dos[0]
    assert e["title"] == "Blood" and e["folder"] == "Blood (1997)(Monolith)"
    assert e["id"] == dosgames.game_id("Blood (1997)(Monolith)")      # the id still follows the folder name
    assert inst.index[e["id"]]["dir"] == str(folder)
    assert sorted(p.name for p in folder.parent.iterdir()) == before


def test_two_games_with_one_title_get_a_short_difference(tmp_path, monkeypatch):
    inst, lib, sd_dos, _ = inst_two_roots(tmp_path, monkeypatch)
    make_game(sd_dos / "Blood (1997)(Monolith)")
    make_game(sd_dos / "Blood (1998)(Other)")
    make_game(sd_dos / "Doom (1993)(id)")
    make_game(sd_dos / "Doom [shareware]")
    make_game(sd_dos / "Alone (1992)(A)")
    make_game(sd_dos / "Alone (1992)(B)")
    inst.sync_dos()
    titles = sorted(e["title"] for e in lib.dos)
    assert "Blood (1997)" in titles and "Blood (1998)" in titles
    assert "Doom (1993)" in titles and "Doom" in titles               # the one without a year keeps the plain title
    assert "Alone (A)" in titles and "Alone (B)" in titles           # same year: what the brackets say
    assert len(set(titles)) == 6


def test_gog_is_asked_with_the_clean_name_and_the_subtitle_less_form():
    from itch_deck import dosart
    p = dosart.parse("Commander Keen 3 Keen Must Die")
    q = dosart.queries(p)
    assert q[0] == "commander keen 3 keen must die" and "commander keen 3" in q
    cat = [{"id": "9", "title": "Commander Keen 3", "slug": "k3", "productType": "game", "releaseDate": "1990.12.14",
            "coverHorizontal": "https://x/h.jpg"}]
    m = dosart.find(dosart.search_name("Commander Keen 3 Keen Must Die (1990)(Apogee Software)"),
                    lambda u: {"products": cat})
    assert m and m["id"] == "9"


def test_the_art_cache_key_follows_the_clean_title_not_the_folder_or_the_disambiguator(tmp_path):
    from itch_deck import library
    paths.use_root(tmp_path / "home")
    lib = library.Library(None)
    lib._fetch_dosart = lambda *a, **k: None
    lib.set_dos_games([{"id": "d1", "title": "Blood (1997)", "folder": "Blood (1997)(Monolith)", "cover": None}])
    g = lib.by_id("d1")
    assert lib._dosart_name(g) == "Blood (1997)"
    g2 = {"id": "d2", "title": "Blood", "folder": "BLOOD_v1.1"}
    assert lib._dosart_name(g2) == "BLOOD"


# --- 4: art lookups are not starved by the big queues -----------------------------------------------
def test_dos_art_jobs_run_before_covers_pages_and_hltb(tmp_path, monkeypatch):
    from itch_deck import library
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.Library, "_work", lambda self: None)       # only look at the queue
    lib = library.Library(None)
    lib.games = [{"id": f"i{n}", "title": f"I{n}", "store": "itch", "platforms": {"linux"}, "cover_url": "x",
                  "url": "https://x/" + str(n)} for n in range(30)]
    lib.queue_covers()
    lib.queue_prefetch()
    lib.queue_hltb()
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}, {"id": "d2", "title": "Blood", "cover": None}])
    order = []
    while not lib._q.empty():
        order.append(lib._q.get()[2:])
    kinds = [k for k, _ in order]
    assert kinds[:2] == ["dosart", "dosart"], kinds[:5]
    assert kinds.count("dosart") == 2 and kinds.count("cover") == 30


def test_every_scan_queues_the_art_jobs_again_for_new_games(tmp_path, monkeypatch):
    from itch_deck import library
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.Library, "_work", lambda self: None)
    lib = library.Library(None)
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
    assert ("dosart", "d1") in lib._queued
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}, {"id": "d2", "title": "Blood", "cover": None}])
    assert ("dosart", "d2") in lib._queued


def test_the_page_you_open_still_comes_before_the_art_jobs(tmp_path, monkeypatch):
    from itch_deck import library
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.Library, "_work", lambda self: None)
    lib = library.Library(None)
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
    g = {"id": "i1", "title": "I", "store": "itch", "platforms": {"linux"}, "url": "https://x/1"}
    lib.games.append(g)
    lib.ensure_details(g)
    first = lib._q.get()
    assert first[2:] == ("page", "i1")


# --- 5: the wide GOG cover is the tile art ---------------------------------------------------------------
def _png(path, size, color):
    s = pg.Surface(size)
    s.fill(color)
    pg.image.save(s, str(path))
    return Path(path).read_bytes()


def _prod(**k):
    return dict({"id": "7", "title": "Doom", "slug": "doom", "productType": "game", "releaseDate": "1993.12.10",
                 "coverHorizontal": "https://img.test/wide.jpg", "coverVertical": "https://img.test/tall.jpg"}, **k)


def test_the_wide_cover_is_preferred_and_the_tall_one_is_the_fallback():
    from itch_deck import dosart
    assert dosart.pick_cover(_prod()).endswith("wide.jpg")
    assert dosart.pick_cover(_prod(coverHorizontal=None)).endswith("tall.jpg")
    assert dosart.pick_cover(_prod(coverHorizontal="//img.test/w.jpg")) == "https://img.test/w.jpg"
    m = dosart.summary(_prod())
    assert m["cover"].endswith("wide.jpg") and m["cover_tall"].endswith("tall.jpg")      # the tall one is kept for later


def test_the_wide_cover_is_downloaded_for_the_tile_and_a_folder_cover_still_wins(tmp_path, monkeypatch):
    from itch_deck import library, net
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    wide = _png(tmp_path / "w.png", (640, 360), (10, 120, 200))
    got = []

    def get(url, key=None, timeout=20, **k):
        got.append(url)
        return wide

    def get_json(url, key=None, timeout=20):
        if "catalog.gog.com" in url:
            return {"products": [_prod()]}
        return {"description": {"full": "<p>Text.</p>"}, "screenshots": []}
    monkeypatch.setattr(net, "get", get)
    monkeypatch.setattr(net, "get_json", get_json)
    lib = library.Library(None)
    own = tmp_path / "dos" / "Doom"
    own.mkdir(parents=True)
    own_png = own / "cover.png"
    _png(own_png, (200, 300), (1, 2, 3))
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}, {"id": "d2", "title": "Doom 2 x", "cover": own_png}])
    lib._worker and lib._worker.join(timeout=20)
    assert [u for u in got if "wide.jpg" in u] and not [u for u in got if "tall.jpg" in u]
    assert "dosart" in lib.by_id("d1")["cover_file"]
    assert Path(lib.by_id("d2")["cover_file"]).parent == paths.COVERS            # the folder's cover.png wins


def test_an_old_tall_cover_from_v0927_is_replaced_by_the_wide_one(tmp_path, monkeypatch):
    from itch_deck import library, net
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    wide = _png(tmp_path / "w.png", (640, 360), (10, 120, 200))
    monkeypatch.setattr(net, "get", lambda url, key=None, timeout=20, **k: wide)
    monkeypatch.setattr(net, "get_json", lambda url, key=None, timeout=20: {"products": [_prod()]} if "catalog" in url
                        else {"description": {"full": "<p>T.</p>"}, "screenshots": []})
    lib = library.Library(None)
    art = lib._dosart_dir()
    art.mkdir(parents=True)
    old = art / "d1.jpg"
    _png(old, (300, 450), (200, 0, 0))
    lib._dosart["d1"] = {"key": "Doom", "algo": 1, "at": "2020-01-01T00:00:00+00:00",
                         "match": {"id": "7", "title": "Doom", "cover": "https://img.test/tall.jpg"}}
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
    lib._worker and lib._worker.join(timeout=20)
    cf = lib.by_id("d1")["cover_file"]
    pic = pg.image.load(cf)
    assert pic.get_width() > pic.get_height()                                     # the wide one now


def test_a_wide_cover_fills_the_tile_without_blurred_bars(tmp_path):
    from itch_deck.ui import widgets as W
    t = _theme()
    f = tmp_path / "wide.png"
    _png(f, (640, 360), (255, 0, 0))
    img = W.cover(t, {"id": "w1", "title": "X", "store": "dos", "cover_file": str(f)}, (272, 216))
    for x, y in ((2, 108), (269, 108), (136, 2), (136, 213)):
        assert img.get_at((x, y))[0] > 240, (x, y)                                  # red everywhere: no bars


# --- 6: a short GOG description without pack talk ---------------------------------------------------------
PACK_TEXT = ("Billy Blaze builds a rocket ship and flies to Mars to save his parents. "
             "Run, jump and pogo through hostile worlds full of deadly aliens. "
             "This pack includes all three episodes of the trilogy. "
             "Play both games in one bundle with DOOM + DOOM II. "
             "Fight your way through 27 levels of pure arcade action, with a secret in every corner. "
             "Part of the Classic Collection. " + "More words about the game that go on and on. " * 30)


def test_the_description_is_one_short_paragraph_without_pack_talk():
    from itch_deck import dosart
    out = dosart.short_text(["", PACK_TEXT, "Second paragraph."])
    assert len(out) == 1 and 100 < len(out[0]) <= 700
    low = out[0].lower()
    for bad in ("pack", "bundle", "collection", "includes", "both games", "doom + doom"):
        assert bad not in low, bad
    assert out[0].startswith("Billy Blaze") and out[0].endswith((".", "!", "?", "\u2026"))
    assert "pogo" in low


def test_a_first_paragraph_that_is_only_pack_talk_gives_way_to_the_next():
    from itch_deck import dosart
    assert dosart.short_text(["Includes both games. A great bundle."]) == []
    assert dosart.short_text(["Includes both games.", "A fast platformer. Great fun."]) == ["A fast platformer. Great fun."]
    assert dosart.short_text(None) == [] and dosart.short_text([]) == []
    one = dosart.short_text(["word " * 400])
    assert len(one[0]) <= 620 and one[0].endswith("\u2026")                 # no sentence end: cut at a word


def test_the_saved_page_holds_only_the_short_text(tmp_path, monkeypatch):
    import json
    from itch_deck import library, net
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    monkeypatch.setattr(net, "get", lambda url, key=None, timeout=20, **k: _png(tmp_path / "c.png", (640, 360), (9, 9, 9)))
    monkeypatch.setattr(net, "get_json", lambda url, key=None, timeout=20: {"products": [_prod()]} if "catalog" in url
                        else {"description": {"full": "<p>" + PACK_TEXT + "</p><p>Another.</p>"}, "screenshots": []})
    lib = library.Library(None)
    lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
    lib._worker and lib._worker.join(timeout=20)
    d = json.loads((paths.PAGES / "d1.json").read_text())
    assert len(d["description"]) == 1 and "bundle" not in d["description"][0].lower()


# --- 7: Program to run -------------------------------------------------------------------------------------
def test_default_pick_avoids_support_programs_but_keeps_real_games():
    pick = dosgames.pick_program
    assert pick("Bio Menace", ["TECHSUPP.EXE", "BM1.EXE", "BM2.EXE"]) == "BM1.EXE"
    assert pick("Bio Menace", ["ORDERING.EXE", "VENDOR.EXE", "HINTS.EXE", "BM1.EXE"]) == "BM1.EXE"
    assert pick("Game", ["trainer.exe", "cheat.com", "GO.BAT"]) == "GO.BAT"
    assert pick("Game", ["TECHSUPP.EXE"]) == "TECHSUPP.EXE"                 # only that: still better than nothing
    assert pick("Mouse Hunt", ["MOUSEH.EXE"]) == "MOUSEH.EXE"
    for real in ("HELPFUL.EXE", "TECHNOID.EXE", "INFORMER.EXE", "HINTERLD.EXE", "ORDEAL.EXE", "SUPPORTED.EXE"):
        assert not dosgames.is_support(real), real
    assert pick("Game", ["A.EXE", "B.EXE"], saved="TECHSUPP.EXE") == "A.EXE"
    assert pick("Game", ["TECHSUPP.EXE", "B.EXE"], saved="TECHSUPP.EXE") == "TECHSUPP.EXE"    # a saved choice wins
    assert pick("Tech", ["TECH.EXE", "Z.EXE"]) == "TECH.EXE"                 # the name like the folder wins


def test_setup_programs_are_listed_marked_and_never_the_default(tmp_path, monkeypatch):
    inst, lib, sd_dos, _ = inst_two_roots(tmp_path, monkeypatch)
    make_game(sd_dos / "Blood", "BLOOD.EXE", ["SETUP.EXE", "SNDSETUP.EXE", "TOOLS/INSTALL.COM", "DOSBOX.EXE"])
    inst.sync_dos()
    gid = dosgames.game_id("Blood")
    info = inst.index[gid]
    assert info["exe"] == "BLOOD.EXE"
    assert sorted(info["setups"]) == ["SETUP.EXE", "SNDSETUP.EXE", "TOOLS/INSTALL.COM"]      # dosbox.exe is junk
    ch = inst.program_choices(gid)
    assert ch[0] == ("BLOOD.EXE", "use") and [k for _p, k in ch[1:]] == ["setup"] * 3
    assert inst.set_exe(gid, "SETUP.EXE") is False                          # a setup can not become the default
    assert inst.run_once(gid, "SETUP.EXE") and inst.index[gid]["exe"] == "BLOOD.EXE"
    from itch_deck import dosbox
    exe, args, cwd = dosbox.launch_own(inst.index[gid], ["dosbox"], once=inst.take_once(gid))
    assert "SETUP.EXE" in args and "BLOOD.EXE" not in args
    exe, args, cwd = dosbox.launch_own(inst.index[gid], ["dosbox"], once=inst.take_once(gid))   # next Play: the game
    assert "BLOOD.EXE" in args and "SETUP.EXE" not in args


def test_the_program_list_scrolls_and_fits_both_screens(tmp_path):
    from itch_deck.ui import widgets as W
    for size in ((1280, 800), (1920, 1080)):
        pg.init()
        pg.display.set_mode((64, 64))
        from itch_deck import theme
        t = theme.Theme(pg, size)
        s = pg.Surface(size)
        items = [(f"PROGRAM{i}.EXE", "Setup" if i > 15 else "", "Top folder") for i in range(30)]
        W.forget_menu("Choose the program")
        sub = "Pick the program that starts the game. A setup program runs once, the next time you play."
        seen_first = []
        for focus in (0, 5, 12, 29, 20, 0):
            r = W.menu(t, s, "Choose the program", sub, items, focus)
            assert r.top >= 0 and r.bottom <= t.h - t.hint_h, (size, focus, r)   # inside the screen, above the footer
            seen_first.append(W._MENU_FIRST["Choose the program"])
        assert seen_first[0] == 0 and seen_first[3] > 0 and seen_first[-1] == 0      # it scrolled down and back
        fit_rows = int((r.h - 2 * t.lg) // 1)
        assert r.h > 0
        # the focused row is always among the rows drawn
        for focus in range(30):
            W.menu(t, s, "Choose the program", sub, items, focus)
            first = W._MENU_FIRST["Choose the program"]
            assert first <= focus
        short = [("A.EXE", "In use", "Top folder"), ("B.EXE", "", "Top folder")]
        W.forget_menu("Choose the program")
        r = W.menu(t, s, "Choose the program", sub, short, 0)
        assert W._MENU_FIRST["Choose the program"] == 0 and r.h < t.h / 2        # short lists are not stretched


def test_picking_a_setup_runs_it_once_and_picking_a_program_changes_the_default(tmp_path, monkeypatch):
    import types as T
    from itch_deck import app_game
    inst, lib, sd_dos, _ = inst_two_roots(tmp_path, monkeypatch)
    make_game(sd_dos / "Blood", "BLOOD.EXE", ["BLOOD2.EXE", "SETUP.EXE"])
    inst.sync_dos()
    gid = dosgames.game_id("Blood")
    app = T.SimpleNamespace(inst=inst, said=[])
    app.say = lambda m, **k: app.said.append(m)
    app.picker = None
    app.scene = T.SimpleNamespace(overlay=None)
    app.lib = T.SimpleNamespace(by_id=lambda i: None)
    mixin = app_game.GameMixin if hasattr(app_game, "GameMixin") else None
    assert mixin is not None
    mixin._program_picker(app, gid)
    title, sub, items = app.scene.overlay[1], app.scene.overlay[2], app.scene.overlay[3]
    assert [i[1] for i in items] == ["In use", "", "Setup"] and "once" in sub
    app.scene.overlay = ("picker", title, sub, items, 2)                       # pick the setup
    mixin._pick(app, app.scene)
    assert inst.index[gid]["exe"] == "BLOOD.EXE" and inst.once[gid] == "SETUP.EXE"
    mixin._program_picker(app, gid)
    app.scene.overlay = ("picker", title, sub, items, 1)                       # pick the other program
    mixin._pick(app, app.scene)
    assert inst.index[gid]["exe"] == "BLOOD2.EXE"


# --- 8: Manage games ---------------------------------------------------------------------------------------
def _sm_items(n=40):
    return [{"id": f"g{i}", "title": f"Game {i}", "size_mb": (i * 37) % 900 + 10, "drive": "SD card",
             "store": "itch", "played": "2026-11-0%d" % (i % 9 + 1) if i % 3 else ""} for i in range(n)]


def test_manage_games_says_select_not_tick_and_x_hint_waits_for_a_selection():
    from itch_deck.input import A
    from itch_deck.ui.scenes.storage import StorageManager
    sc = StorageManager(_theme(), _sm_items(5))
    h = sc.hints()
    assert ("A", "Select") in h and ("X", "Uninstall") not in h
    assert not any("tick" in b.lower() for _a, b in h)
    sc.handle(A)
    assert ("X", "Uninstall") in sc.hints()


def test_x_with_nothing_selected_does_nothing_in_the_app(monkeypatch):
    import types as T
    from itch_deck import app_storage
    from itch_deck.input import X
    from itch_deck.ui.scenes.storage import StorageManager
    said, asked = [], []
    me = T.SimpleNamespace(scene=StorageManager(_theme(), _sm_items(5)), say=lambda *a, **k: said.append(a),
                           confirm=lambda *a, **k: asked.append(a), cfg={})
    app_storage.StorageMixin._h_storage(me, X)
    assert said == [] and asked == []


def test_changing_the_sort_keeps_the_focus_on_the_same_game():
    from itch_deck.input import DOWN, Y
    from itch_deck.ui.scenes.storage import StorageManager
    sc = StorageManager(_theme(), _sm_items(40), sort="size")
    for _ in range(7):
        sc.handle(DOWN)
    gid = sc.rows()[sc.focus]["id"]
    for _ in range(4):                                    # through every sort order and round again
        sc.handle(Y)
        assert sc.rows()[sc.focus]["id"] == gid, sc.sort
    sc2 = StorageManager(_theme(), [], sort="size")
    sc2.handle(Y)                                         # an empty list: nothing to keep, nothing breaks
    assert sc2.focus == 0


def test_the_manage_list_glides_and_draws_inside_both_screens():
    from itch_deck import theme
    from itch_deck.input import DOWN, Y
    from itch_deck.ui import widgets as W
    from itch_deck.ui.scenes.storage import StorageManager
    for size in ((1280, 800), (1920, 1080)):
        pg.init()
        pg.display.set_mode((64, 64))
        t = theme.Theme(pg, size)
        sc = StorageManager(t, _sm_items(60), drives=[{"name": "SD card", "free": 5e10, "total": 2.5e11}])
        s = pg.Surface(size)
        old = W.LIVE
        W.LIVE = True
        try:
            sc.draw_page(s)
            for _ in range(40):
                sc.handle(DOWN)
            sc.handle(Y)
            sc.draw_page(s)                               # first frame after the jump: the list starts moving
            assert sc._sy[0] <= sc._sy[2] and sc.first > 0
            sc.draw_page(s)
        finally:
            W.LIVE = old
        assert s.get_clip() == pg.Rect(0, 0, *size)       # the clip is put back


def test_where_the_second_b_goes():
    """Answer for the checklist: Manage games -> B -> Settings -> B -> library (opened from the library) or the
    game page of the game that was focused (opened from a game page)."""
    import types as T
    from itch_deck import app_settings, app_storage
    from itch_deck.input import B
    went = []
    for opened_from, expect in (("library", "library"), ("game", "game")):
        me = T.SimpleNamespace(settings_back=opened_from, lib_focus_id="x", kind="storage")
        me.go_settings = lambda me=me: setattr(me, "settings_back", "storage")     # what App.go_settings does
        me.scene = T.SimpleNamespace(side=True)
        me.lib = T.SimpleNamespace(by_id=lambda i: {"id": i})
        me.go_game = lambda g: went.append("game")
        me.go_library = lambda: went.append("library")
        app_storage.StorageMixin._h_storage(me, B)                                # B in Manage games -> Settings
        assert me.settings_back == opened_from
        app_settings.SettingsMixin._h_settings(me, B)                             # B in Settings (side bar)
        assert went[-1] == expect


# --- 10: a failing press or frame must not kill the app, and must leave a trace ---------------------------------
def test_a_failing_press_is_logged_and_the_app_carries_on(tmp_path, caplog):
    import logging
    from itch_deck import app as appmod
    from itch_deck.input import B
    paths.use_root(tmp_path / "home")
    a = appmod.App(windowed=True)
    a.lib._fetch_dosart = lambda *x, **k: None
    assert appmod.App.strict is False
    real = a.handle
    calls = []

    def bad(act):
        calls.append(act)
        if len(calls) == 1:
            raise KeyError("boom")
        return real(act)
    a.handle = bad
    with caplog.at_level(logging.ERROR, logger="scritch"):
        a.run(max_frames=4, script={0: B, 1: B})
    assert len(calls) == 2                                    # the second press was still handled
    assert any("frame failed" in r.getMessage() and r.exc_info for r in caplog.records)   # with its traceback
    assert a.scene.toast and "went wrong" in a.scene.toast


def test_many_failures_in_a_row_go_back_to_the_library_and_strict_mode_raises(tmp_path):
    import pytest
    from itch_deck import app as appmod
    paths.use_root(tmp_path / "home")
    a = appmod.App(windowed=True)
    went = []
    a.go_library = lambda: went.append(1)
    for _ in range(5):
        try:
            raise ValueError("x")
        except ValueError:
            a._frame_failed()
    assert went == [1]
    appmod.App.strict = True
    try:
        with pytest.raises(ValueError):
            try:
                raise ValueError("y")
            except ValueError:
                a._frame_failed()
    finally:
        appmod.App.strict = False


def test_b_on_a_dos_game_page_and_in_its_program_list_do_not_raise(tmp_path, monkeypatch):
    """Omri's Bio Menace report. Not reproduced here: B on the page, B in the Program to run list, B after a game
    ran and closed, B on a hidden game's page all go back cleanly."""
    from itch_deck import app as appmod, dosbox, runner
    from itch_deck.input import A, B, START
    paths.use_root(tmp_path / "home")
    appmod.App.strict = True
    try:
        a = appmod.App(windowed=True)
        a.lib._fetch_dosart = lambda *x, **k: None
        dos = tmp_path / "dos"
        make_game(dos / "Bio Menace", "BM1.EXE", ["TECHSUPP.EXE", "SETUP.EXE"])
        a.inst.dos_roots = lambda: [dos]
        a.inst.dos_root = lambda: dos
        a.inst.sync_dos()
        g = next(x for x in a.lib.games if x["store"] == "dos")
        assert a.inst.index[g["id"]]["exe"] == "BM1.EXE"          # not the technical-support program
        a.filt = "dos"
        a.go_game(g)
        a.handle(B)
        assert a.kind == "library"
        a.go_game(g)
        a._program_picker(g["id"])
        a.handle(B)
        assert a.kind == "game" and not a.scene.overlay
        a.handle(B)
        assert a.kind == "library"
        monkeypatch.setattr(dosbox, "native", lambda: ["dosbox"])
        monkeypatch.setattr(runner, "run", lambda *x, **k: (0, 9.0))
        a.go_game(g)
        a.play(g)
        a.update()
        a.handle(B)
        assert a.kind == "library"
        a.go_game(g)
        monkeypatch.setattr(runner, "run", lambda *x, **k: (1, 1.0))
        a.play(g)
        a.handle(B)
        assert a.kind == "library"
    finally:
        appmod.App.strict = False
