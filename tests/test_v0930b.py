"""v0.9.30, part 2: the Controls block on a DOS game's page draws the pad's icons. (The reader for the game's own text
files was removed in v0.9.31.)"""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dos_controls as DC  # noqa: E402


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
         "dos_source": "From our list. Not tested, so a key may be wrong."}
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
        assert "From our list. Not tested, so a key may be wrong." in texts and not any("Tell us" in x for x in texts)
        seen[kind] = sc
    assert seen["deck"] is not seen["ps"]
