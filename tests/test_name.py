"""The name rule (DESIGN rule 1): SCRiTCH, every letter purple, the i white — everywhere."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame as pg  # noqa: E402

from itch_deck import phonelink  # noqa: E402
from itch_deck.theme import Theme  # noqa: E402
from itch_deck.ui import widgets as W  # noqa: E402

A, WH, C = "purple", "white", "base"


def test_runs_spell_and_colour_the_name_in_any_case():
    for txt in ("Quit SCRiTCH?", "quit scritch?", "QUIT SCRITCH?"):
        runs = W.name_runs(txt, C, A, WH)
        assert [r for r, c in runs if c != C] == ["SCR", "i", "TCH"]
        assert dict((r, c) for r, c in runs)["i"] == WH
        assert all(c == A for r, c in runs if r in ("SCR", "TCH"))


def test_rendered_i_is_white_and_letters_purple():
    pg.init()
    t = Theme(pg, (1280, 800))
    img = W.render_text(t, t.f_h1, "SCRiTCH", None)
    f = t.f_h1
    def colours(a, b):            # opaque pixels of the text between x=a and x=b
        out = set()
        for x in range(int(a), int(b)):
            for y in range(img.get_height()):
                p = img.get_at((x, y))
                if p.a > 250:
                    out.add(tuple(p)[:3])
        return out
    s_end = f.size("SCR")[0]
    i_end = f.size("SCRi")[0]
    assert tuple(t.accent) in colours(0, s_end) and tuple(t.text_c) not in colours(0, s_end)
    assert tuple(t.text_c) in colours(s_end + 1, i_end - 1)
    assert tuple(t.accent) not in colours(s_end + 1, i_end - 1)


def test_phone_pages_use_the_same_rule():
    page = phonelink.form_page("itch", "tok")
    assert phonelink.named("Back to SCRiTCH") == 'Back to <span class="nm">SCR<i>i</i>TCH</span>'
    assert ".nm{color:#9d6bff}.nm i{color:#fff" in page
    # the logo sits on top of every page; the heading under it doesn't repeat the name
    assert '<main><svg class="logo" role="img" aria-label="SCRiTCH"' in page
    assert "<h1>Connect itch</h1>" in page and "<title>Connect itch to SCRiTCH</title>" in page
