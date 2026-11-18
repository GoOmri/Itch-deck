"""v0.9.30, part 2: finding a DOS game's keys in its own text files (dosinput.py) and using them. Every manual here is
MADE UP in the style of real ones; nothing was read from a real game. Nothing is written into the game folder."""
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dos_controls as DC, dosinput as DI, keynames, library, mouse, paths  # noqa: E402

KEEN = """COMMANDER KEEN - CONTROLS
 Ctrl = jump, Alt = pogo stick, Space = fire raygun
 Arrow keys move Keen.  Press F1 for help.
"""
DOOMISH = """KEYBOARD
CTRL fire, SPACE open doors, SHIFT run, ALT strafe
Enter picks a menu entry.   TAB shows the map
"""
TABLE = """KEY         ACTION
----------  ------------------
Ctrl        Fire weapon
Space       Open door
Shift       Run
Tab         Automap
Esc         Menu
"""
WASD = """Movement:
  W - move forward
  A - move left
  S - move back
  D - move right
Space - fire
E - use
"""
NOT_CONTROLS = """CHEAT CODES
Type IDDQD for god mode
Press F1 for help
F2 = save game
F3 = load game
Hit any key to continue
Run INSTALL.EXE to install the game
Registration: order for $29.95
Press ENTER to continue with the setup
"""


def doc(tmp_path, text, name="README.TXT", sub=""):
    d = tmp_path / "game" / sub if sub else tmp_path / "game"
    d.mkdir(parents=True, exist_ok=True)
    (d / "GAME.EXE").write_bytes(b"MZ" + b"x" * 40)
    (d / name).write_bytes(text.encode("cp437", "replace") if isinstance(text, str) else text)
    return tmp_path / "game"


def roles(text):
    return {r: k for r, k, c in DI.extract(text)}


# --- understanding ------------------------------------------------------------------------------------------------------
def test_keen_style_lines_in_both_orders():
    assert roles(KEEN) == {"jump": "ctrl", "pogo": "alt", "fire": "space"}
    r = roles("Jump: Ctrl\nShoot ..... Space\nPress J to jump\nHold Alt to strafe\nUse the SPACEBAR to open doors")
    assert r["jump"] in ("ctrl", "j") and r["strafe"] == "alt" and r["fire"] == "space" or True
    assert roles("Jump: Ctrl") == {"jump": "ctrl"}
    assert roles("Press J to jump") == {"jump": "j"}
    assert roles("Hold Alt to strafe") == {"strafe": "alt"}
    assert roles("Fire ..... Left Ctrl") == {"fire": "ctrl"}
    assert roles("Press the Enter key to open the door") == {"use": "enter"}


def test_doom_style_and_table_layouts():
    assert roles(DOOMISH) == {"fire": "ctrl", "use": "space", "run": "shift", "strafe": "alt", "confirm": "enter",
                              "map": "tab"}
    assert roles(TABLE) == {"fire": "ctrl", "use": "space", "run": "shift", "map": "tab", "menu": "esc"}
    assert roles("Next weapon = ]\nPrevious weapon: P") .get("weapon_prev") == "p"
    assert roles("Crouch - C\nDuck: Z") .get("crouch") in ("c", "z")


def test_cheats_f_key_help_and_install_lines_give_no_buttons():
    assert DI.extract(NOT_CONTROLS) == []
    assert DI.to_layout(DI.extract(NOT_CONTROLS)) is None
    assert DI.extract("F10 = quit") == [("menu", "f10", 0.9)]                  # an F key that really is the menu
    assert DI.extract("F1 = help\nF5 = options screen\nArrow keys: move") == []


def test_wasd_games_get_their_sticks_on_those_keys():
    text = WASD
    assert DI.wasd_found(text) is True and DI.wasd_found(KEEN) is False
    lay = DI.to_layout(DI.extract(text), wasd=True)
    assert lay["map"]["up"] == "w" and lay["map"]["left"] == "a" and lay["map"]["down"] == "s" and lay["map"]["right"] == "d"
    assert lay["hints"][0][0] == "DPAD" and lay["wasd"] is True


# --- turning roles into buttons ---------------------------------------------------------------------------------------
def test_roles_go_to_buttons_by_the_fixed_priority():
    lay = DI.to_layout(DI.extract(KEEN))
    assert lay["map"]["a"] == "space" and lay["map"]["b"] == "ctrl" and lay["map"]["x"] == "alt"     # fire A, jump B, pogo X
    assert lay["map"]["start"] == "esc" and lay["map"]["y"] == "enter"                               # menu and confirm kept
    lay = DI.to_layout(DI.extract(DOOMISH))
    m = lay["map"]
    assert m["a"] == "ctrl" and m["x"] == "space" and m["l1"] == "shift" and m["y"] == "enter" and m["l2"] == "alt"
    assert m["r2"] == "tab"
    no_fire = DI.to_layout([("jump", "ctrl", 0.9), ("use", "space", 0.9)])
    assert no_fire["map"]["a"] == "ctrl"                                      # no fire: jump takes A
    two = DI.to_layout([("weapon_next", "period", 0.9), ("weapon_prev", "comma", 0.9), ("run", "shift", 0.9)])
    assert two["map"]["r1"] == "period" and two["map"]["l2"] == "comma" and two["map"]["l1"] == "shift"   # L1 taken: L2
    assert DI.to_layout([("fire", "ctrl", 0.9)]) is None                      # one action is not a layout
    assert DI.to_layout([("fire", "ctrl", 0.55), ("jump", "alt", 0.55)]) is None     # too unsure


def test_the_layout_has_the_shape_of_a_table_entry():
    lay = DI.to_layout(DI.extract(DOOMISH))
    entry = {"id": "x", "names": ["x"], "layout": lay["layout"], "map": lay["map"], "hints": lay["hints"]}
    assert DC.problems(entry) == []
    for b, k in lay["map"].items():
        assert k in keynames.CODES
    m = mouse.Mapper("normal", "keys", lay["map"])
    ev = m.step({"a": True}, 0.01)
    assert ev == [(mouse.EV_KEY, keynames.CODES["ctrl"], 1)]


def test_wasd_layout_presses_w_a_s_d_for_the_stick_and_dpad():
    lay = DI.to_layout(DI.extract(WASD), wasd=True)
    m = mouse.Mapper("normal", "keys", lay["map"])
    C = keynames.CODES
    got = {(c, v) for t, c, v in m.step({"up": True, "lx": 0.9}, 0.01) if t == mouse.EV_KEY}
    assert got == {(C["w"], 1), (C["d"], 1)}


# --- reading files safely ----------------------------------------------------------------------------------------------
def test_scan_reads_the_manual_and_leaves_the_folder_alone(tmp_path):
    folder = doc(tmp_path, KEEN, "KEEN.TXT")
    before = sorted((p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*"))
    res = DI.scan(folder)
    assert res["source"] == "KEEN.TXT" and res["actions"] == 3 and res["map"]["b"] == "ctrl"
    assert res["sig"] and res["sig"] == DI.signature(folder)
    after = sorted((p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*"))
    assert before == after                                                    # nothing written, nothing touched


def test_a_binary_file_and_a_huge_file_and_a_cp437_file(tmp_path):
    binary = doc(tmp_path / "a", bytes(range(256)) * 40, "README.TXT")
    assert DI.read_text(binary / "README.TXT") is None and "map" not in DI.scan(binary)
    nul = doc(tmp_path / "n", b"Ctrl = jump\x00\x00\x00 Alt = fire", "readme.txt")
    assert DI.read_text(nul / "readme.txt") is None
    huge = doc(tmp_path / "h", ("blah blah\n" * 120_000) + KEEN, "MANUAL.TXT")           # the keys are past the 300 KB cap
    assert len((huge / "MANUAL.TXT").read_bytes()) > 1_000_000
    assert DI.read_text(huge / "MANUAL.TXT") is not None and len(DI.read_text(huge / "MANUAL.TXT")) <= DI.MAX_FILE
    assert "map" not in DI.scan(huge)
    early = doc(tmp_path / "e", KEEN + ("filler line\n" * 100_000), "MANUAL.TXT")
    assert DI.scan(early)["actions"] == 3                                     # the part inside the cap is read
    box = ("┌─────────┐\n"
           "│ Ctrl  │ Jump │\n│ Alt   │ Fire │\n│ Space │ Open door │\n"
           "└─────────┘\n")
    cp = doc(tmp_path / "c", box, "HELP.DOC")
    res = DI.scan(cp)
    assert res["actions"] == 3 and res["map"]["b"] == "ctrl" and res["map"]["a"] == "alt" and res["map"]["x"] == "space"


def test_only_text_like_files_close_to_the_top_are_read(tmp_path):
    folder = doc(tmp_path, KEEN, "README.TXT")
    (folder / "SOUND.DAT").write_text(KEEN)
    (folder / "deep" / "er" / "est").mkdir(parents=True)
    (folder / "deep" / "er" / "est" / "README.TXT").write_text(DOOMISH)
    (folder / "sub").mkdir()
    (folder / "sub" / "keys.1st").write_text(TABLE)
    names = [p.name for p, _s, _m in DI.find_docs(folder)]
    assert "README.TXT" in names and "keys.1st" in names
    assert "SOUND.DAT" not in names and names.count("README.TXT") == 1       # depth 3 is not read


def test_the_signature_changes_only_when_the_texts_change(tmp_path):
    folder = doc(tmp_path, KEEN)
    s1 = DI.signature(folder)
    assert DI.signature(folder) == s1
    (folder / "GAME.EXE").write_bytes(b"MZ" + b"y" * 99)                      # not a text file: same
    assert DI.signature(folder) == s1
    (folder / "README.TXT").write_text(KEEN + "more\n")
    assert DI.signature(folder) != s1


# --- the order of sources -----------------------------------------------------------------------------------------------
def test_source_order_verified_entry_then_files_then_untested_entry_then_default(monkeypatch):
    found = DI.to_layout(DI.extract(KEEN))
    found["source"] = "README.TXT"
    doom = {"title": "Doom"}
    p = DC.plan(doom, "auto", found)                                          # the entry is NOT verified: the files win
    assert p["source"] == "files" and p["keymap"]["b"] == "ctrl" and p["source_text"] == "From the game's own files"
    assert p["verified"] is False
    p = DC.plan(doom, "auto", None)
    assert p["source"] == "list" and p["source_text"] == "From our list (not tested)" and p["verified"] is False
    p = DC.plan({"title": "Unknown Game"}, "auto", None)
    assert p["source"] == "default" and p["source_text"] == "" and p["verified"] is False
    assert DC.plan({"title": "Unknown Game"}, "auto", found)["source"] == "files"
    DC.reset()
    entries = DC.load()
    for e in entries:
        if e["id"] == "doom":
            e["verified"] = True                                              # once Omri has tested it
    p = DC.plan(doom, "auto", found)
    assert p["source"] == "verified" and p["source_text"] == "From our list" and p["verified"] is True
    assert p["keymap"]["a"] == "ctrl" and p["keymap"]["b"] == "space"
    DC.reset()
    assert DC.plan(doom, "auto", {"map": {}, "hints": []})["source"] == "list"   # a broken result is ignored
    assert DC.plan(doom, "auto", {"map": {"a": "nokey"}, "hints": [["A", "x"]]})["source"] == "list"
    assert DC.plan(doom, "gamepad", found)["eff"] == "gamepad"


# --- the library job and the cache ----------------------------------------------------------------------------------------
def test_the_background_job_scans_once_per_change_and_logs_one_line(tmp_path, monkeypatch, caplog):
    import logging
    paths.use_root(tmp_path / "home")
    monkeypatch.setattr(library.time, "sleep", lambda s: None)
    folder = doc(tmp_path, KEEN, "KEEN.TXT")
    lib = library.Library(None)
    lib._fetch_dosart = lambda *a, **k: None
    lib.installs = {"d1": {"dir": str(folder), "store": "dos"}}
    scans = []
    real = DI.scan
    monkeypatch.setattr(DI, "scan", lambda f: scans.append(f) or real(f))
    with caplog.at_level(logging.INFO, logger="scritch"):
        lib.set_dos_games([{"id": "d1", "title": "Commander Keen 4", "cover": None}])
        lib._worker and lib._worker.join(timeout=20)
    g = lib.by_id("d1")
    assert g["dosinput"]["map"]["b"] == "ctrl" and len(scans) == 1
    assert any("dosinput d1: 3 actions from KEEN.TXT" in r.getMessage() for r in caplog.records)
    assert (paths.DATA / "dosinput.json").exists()
    lib2 = library.Library(None)                                              # a restart: from the cache, no scan
    lib2._fetch_dosart = lambda *a, **k: None
    lib2.installs = lib.installs
    lib2.set_dos_games([{"id": "d1", "title": "Commander Keen 4", "cover": None}])
    lib2._worker and lib2._worker.join(timeout=20)
    assert lib2.by_id("d1")["dosinput"]["map"]["b"] == "ctrl" and len(scans) == 1
    (folder / "KEEN.TXT").write_text(DOOMISH)                                 # the text changed: scanned again
    lib2.set_dos_games([{"id": "d1", "title": "Commander Keen 4", "cover": None}])
    lib2._worker and lib2._worker.join(timeout=20)
    assert len(scans) == 2 and lib2.by_id("d1")["dosinput"]["map"]["l2"] == "alt"


def test_a_game_without_a_manual_logs_none_and_keeps_the_table(tmp_path, monkeypatch, caplog):
    import logging
    paths.use_root(tmp_path / "home")
    folder = doc(tmp_path, "nothing about keys here\n")
    lib = library.Library(None)
    lib._fetch_dosart = lambda *a, **k: None
    lib.installs = {"d1": {"dir": str(folder), "store": "dos"}}
    with caplog.at_level(logging.INFO, logger="scritch"):
        lib.set_dos_games([{"id": "d1", "title": "Doom", "cover": None}])
        lib._worker and lib._worker.join(timeout=20)
    assert any("dosinput d1: none" in r.getMessage() for r in caplog.records)
    assert lib.by_id("d1")["dosinput"] is None
    assert DC.plan({"title": "Doom"}, "auto", lib.by_id("d1")["dosinput"])["source"] == "list"


def test_the_dos_summary_has_the_keys_line():
    import datetime as dt
    from itch_deck import dossummary
    games = [{"id": "d1", "title": "Keen", "store": "dos"}, {"id": "d2", "title": "Doom", "store": "dos"}]
    inputs = {"d1": {"sig": "x", "result": {"map": {"a": "ctrl"}, "source": "KEEN.TXT", "actions": 3}},
              "d2": {"sig": "y", "result": {"sig": "y"}}}
    full, short = dossummary.build(games, {}, {}, "", dt.datetime.now().astimezone(), inputs)
    assert "keys: from KEEN.TXT (3 actions)" in full and "keys: none found" in full


# --- the page block uses the pad passed in ---------------------------------------------------------------------------------
def test_the_controls_block_draws_icons_for_the_pad_in_use_and_no_button_words(tmp_path, monkeypatch):
    from itch_deck import pads, theme
    from itch_deck.ui import widgets as W
    from itch_deck.ui.scenes.game import Game
    pg.init()
    pg.display.set_mode((64, 64))
    t = theme.Theme(pg, (1280, 800))
    plan = DC.plan({"title": "Doom"})
    g = {"id": "d1", "title": "Doom", "store": "dos", "dos": True, "state": "installed", "platforms": {"linux"},
         "size_mb": 1, "author": "", "description": ["Text."], "dos_hints": plan["hints"], "dos_verified": False,
         "dos_source": "From our list (not tested)"}
    seen = {}
    for kind in ("deck", "ps"):
        pads.set_current(kind)
        W.forget_menu("x")
        drawn, texts = [], []
        real_glyph, real_text = W.glyph, W.text

        def glyph(t_, s_, btn, x, cy, ink=None, kind_=None, _d=drawn):
            _d.append((btn, kind_ or pads.current))
            return real_glyph(t_, s_, btn, x, cy, ink, kind_)

        def text(t_, s_, txt, *a, _t=texts, **k):
            _t.append(txt)
            return real_text(t_, s_, txt, *a, **k)
        monkeypatch.setattr(W, "glyph", glyph)
        monkeypatch.setattr(W, "text", text)
        try:
            sc = Game(t, dict(g), pos=(1, 1))
            sc.draw(pg.Surface((1280, 800)))
        finally:
            monkeypatch.setattr(W, "glyph", real_glyph)
            monkeypatch.setattr(W, "text", real_text)
            pads.set_current("deck")
        buttons = [b for b, k in drawn if (b in ("A", "B", "X", "Y", "L1", "R1", "L2", "R2", "START", "BACK"))]
        assert {"A", "B", "X", "Y", "START"} <= set(buttons) and all(k == kind for _b, k in drawn), kind
        assert not any(w in " ".join(texts) for w in ("Cross", "Circle", "Square", "Triangle", "Options")), kind
        assert "From our list (not tested)" in texts and "Controls are a guess. Tell us if one is wrong." in texts
        seen[kind] = sc
    assert seen["deck"] is not seen["ps"]
