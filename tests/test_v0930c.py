"""v0.9.30 review round: wording of the dim source lines and the Controls row hint."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dos_controls as DC  # noqa: E402


# --- 5: wording --------------------------------------------------------------------------------------------------------------
def test_the_dim_lines_say_where_the_keys_came_from_in_one_sentence_each():
    assert DC.plan({"title": "Doom"})["source_text"] == "From our list. Not tested, so a key may be wrong."
    assert DC.plan({"title": "Unknown"})["source_text"] == "Controls are a guess. Some keys may be wrong."
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
