"""v0.9.30 review round: files are an overlay and never worse than the table, Esc stays on Start, the DOSBox manual is
skipped, the scan reads a bounded amount, wording."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dos_controls as DC, dosinput as DI  # noqa: E402
from test_v0930b import KEEN, doc  # noqa: E402

INDY_README = "Space = pause the game\nF1 - Save/load menu\nEnter = select\nEsc = quit to the menu\n"
DOSBOX_README = """Special Keys
ALT-ENTER    Switch to full screen and back.
ALT-PAUSE    Pause emulation.
CTRL-F1      Start the keymapper.
CTRL-F4      Change between mounted floppy/CD images.
CTRL-F5      Save a screenshot.
CTRL-F7      Decrease frameskip.
CTRL-F11     Slow down emulation (Decrease DOSBox cycles).
CTRL-F12     Speed up emulation (Increase DOSBox cycles).
"""


def found(text, wasd=False):
    return DI.to_layout(DI.extract(text), wasd=wasd)


# --- 1: files are an overlay, never worse than the table ----------------------------------------------------------------
def test_indiana_jones_stays_playable_on_auto_whatever_its_readme_says():
    assert DI.to_layout(DI.extract(INDY_README)) is None                       # pause / select / menu are not real actions
    res = {"sig": "x", **(DI.to_layout(DI.extract(KEEN)) or {})}               # even a readme with real actions
    p = DC.plan({"title": "Indiana Jones and the Fate of Atlantis"}, "auto", res)
    assert p["layout"] == "mouse" and p["keymap"]["a"] == "lmb" and p["keymap"]["y"] == "esc" and p["source"] == "list"


def test_a_doom_like_readme_without_game_actions_keeps_the_table():
    p = DC.plan({"title": "Doom"}, "auto", DI.to_layout(DI.extract(INDY_README)))
    assert p["source"] == "list" and p["keymap"]["a"] == "ctrl" and p["keymap"]["b"] == "space"


def test_files_replace_only_the_buttons_they_name_and_keep_the_mouse():
    res = DI.to_layout(DI.extract("Alt = fire\nShift = run"))                  # two real actions
    assert res["map"] == {"a": "alt", "l1": "shift"}
    p = DC.plan({"title": "Doom"}, "auto", res)
    base = DC.match("Doom")["map"]
    assert p["source"] == "files" and p["keymap"]["a"] == "alt" and p["keymap"]["l1"] == "shift"
    for b in ("b", "x", "y", "start", "back", "r1"):
        assert p["keymap"].get(b) == base.get(b), b                            # everything else from the table
    assert p["keymap"]["start"] == "esc" and p["layout"] == "keysmouse"        # the mouse is kept
    d = DC.plan({"title": "Unknown"}, "auto", res)                             # no entry: the default is the base
    assert d["keymap"]["b"] == "alt" and d["keymap"]["a"] == "alt" and d["keymap"]["x"] == "space"
    assert d["keymap"]["start"] == "esc" and d["keymap"]["y"] == "enter" and d["keymap"]["r1"] == "tab"
    assert d["layout"] == "keysmouse"
    hints = dict((h[0], h[1]) for h in p["hints"])
    assert hints["A"] == "Fire" and hints["L1"] == "Run" and hints["Y"] == "Menu select"    # base hints stay


def test_one_real_action_is_not_enough_and_a_wasd_file_overlays_the_sticks():
    assert DI.to_layout(DI.extract("Ctrl = fire")) is None
    res = found("W - move forward\nA - move left\nS - move back\nD - move right\nSpace - fire\nE - use", wasd=True)
    p = DC.plan({"title": "Unknown"}, "auto", res)
    assert p["keymap"]["up"] == "w" and p["keymap"]["a"] == "space" and p["keymap"]["start"] == "esc"


# --- 2: Esc always on Start ---------------------------------------------------------------------------------------------
def test_pause_and_quit_keys_are_never_mapped():
    assert DI.to_layout(DI.extract("P = pause\nEsc = menu")) is None
    res = found("Ctrl = fire\nSpace = open doors\nQ = quit to DOS\nEsc = menu\nP = pause")
    assert res["map"] == {"a": "ctrl", "x": "space"}
    assert "q" not in res["map"].values() and "p" not in res["map"].values() and "start" not in res["map"]
    p = DC.plan({"title": "Unknown"}, "auto", res)
    assert p["keymap"]["start"] == "esc" and "q" not in p["keymap"].values()


# --- 3: the DOSBox manual ---------------------------------------------------------------------------------------------------
def test_the_dosbox_manual_gives_no_actions(tmp_path):
    assert DI.extract(DOSBOX_README) == []
    folder = doc(tmp_path, DOSBOX_README, "README.TXT")
    assert "map" not in DI.scan(folder)
    d = folder / "DOSBox"
    d.mkdir()
    (d / "README.TXT").write_text(KEEN)
    (folder / "dosbox-staging-notes.txt").write_text(KEEN)
    names = [p.name for p, _s, _m in DI.find_docs(folder)]
    assert names.count("README.TXT") == 1 and "dosbox-staging-notes.txt" not in names   # nothing from a dosbox path


# --- 4: a bounded scan --------------------------------------------------------------------------------------------------------
def test_two_hundred_binary_help_files_read_a_bounded_amount(tmp_path):
    folder = doc(tmp_path, "nothing here\n")
    for i in range(200):
        (folder / f"H{i:03d}.HLP").write_bytes(b"\x00\x01\x02" * 50000)
    docs = DI.find_docs(folder)
    assert len(docs) <= DI.MAX_FILES
    res = DI.scan(folder)
    assert res["read"] <= DI.MAX_FILES * DI.SNIFF and res["read"] < DI.MAX_TOTAL
    counter = [0]
    assert DI.read_text(folder / "H000.HLP", counter=counter) is None and counter[0] == DI.SNIFF   # 4 KB to decide
    assert "map" not in res


def test_readme_like_files_come_first_and_every_read_is_counted(tmp_path):
    folder = doc(tmp_path, KEEN, "README.TXT")
    for i in range(60):
        (folder / f"zz{i:02d}.txt").write_text("filler\n" * 50)
    (folder / "MANUAL.DOC").write_text("Jump: Ctrl\n")
    names = [p.name for p, _s, _m in DI.find_docs(folder)]
    assert names[0] == "README.TXT" and names[1] == "MANUAL.DOC" and len(names) == DI.MAX_FILES
    big = doc(tmp_path / "b", "text line\n" * 100_000, "README.TXT")
    c = [0]
    assert DI.read_text(big / "README.TXT", counter=c) is not None and c[0] == DI.MAX_FILE


# --- 5: wording --------------------------------------------------------------------------------------------------------------
def test_the_dim_lines_say_where_the_keys_came_from_in_one_sentence_each():
    assert DC.plan({"title": "Doom"})["source_text"] == "From our list. Not tested, so a key may be wrong."
    assert DC.plan({"title": "Unknown"})["source_text"] == "Controls are a guess. Some keys may be wrong."
    res = DI.to_layout(DI.extract("Alt = fire\nShift = run"))
    assert DC.plan({"title": "Unknown"}, "auto", res)["source_text"] == "From the game's own files. A key may be wrong."
    for t in DC.SOURCE_TEXT.values():
        assert "Tell us" not in t


def test_the_options_controls_row_hint_stays_on_one_line_at_both_sizes():
    from itch_deck import theme
    from itch_deck.ui import widgets as W
    for size in ((1280, 800), (1920, 1080)):
        pg.init()
        pg.display.set_mode((64, 64))
        t = theme.Theme(pg, size)
        long_hint = "Cross Fire  ·  Circle Open doors  ·  Square Run  ·  Triangle Menu select"
        rows = [("Remove from library", "", ""), ("Controls", "Auto · Keys", long_hint)]
        s = pg.Surface(size)
        r = W.menu(t, s, "Options", "", rows, 1)
        row_w = r.w - 2 * (t.lg - t.md)
        cut = W.fit(t.f_small, long_hint, row_w * 0.6)
        assert t.f_small.size(cut)[0] <= row_w * 0.6 and (cut == long_hint or cut.endswith("…"))
