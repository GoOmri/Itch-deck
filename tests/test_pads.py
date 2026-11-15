"""Per-controller glyphs: which pad is which (names + Steam's slot file), and what is drawn.
Names/GUIDs are the ones the Deck logged on 14-15 Nov (DualSense via Steam, the Deck's own pad)."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

from itch_deck import pads  # noqa: E402

SLOTS = """[slot 0]
name=#SettingsController_SteamController
VID=0x28de
PID=0x1205
handle=0x0000aaaaaaaaaaaa
type=steam
[slot 1]
name=DualSense Wireless Controller
VID=0x054c
PID=0x0ce6
handle=0x000bbbbbbbbbbbbb
type=ps5
"""


def test_kind_from_logged_names():
    assert pads.kind_from_name("Steam Deck Controller") == "deck"
    assert pads.kind_from_name("DualSense Wireless Controller") == "ps"
    assert pads.kind_from_name("PS4 Controller") == "ps"
    assert pads.kind_from_name("Wireless Controller") == "ps"         # SDL's DualShock 4 name
    assert pads.kind_from_name("Xbox Series X Controller") == "xbox"
    assert pads.kind_from_name("Steam Virtual Gamepad") is None        # hot-plugged: unknown
    assert pads.kind_from_name("8BitDo Pro 2") == "xbox"               # unknown brand: letters


def test_steam_slot_file(tmp_path):
    f = tmp_path / "virtualgamepadinfo.txt"
    f.write_text(SLOTS)
    assert pads.steam_slots(str(f)) == ["deck", "ps"]
    assert pads.steam_slots(str(tmp_path / "missing.txt")) == []
    assert pads.steam_slots("") == [] or os.environ.get("SteamVirtualGamepadInfo")


def test_generic_virtual_pad_gets_the_left_over_kind():
    # 14 Nov log: Deck pad named, DualSense connected later shows as "Steam Virtual Gamepad"
    got = pads.resolve([(0, "Steam Deck Controller"), (1, "Steam Virtual Gamepad")], ["deck", "ps"])
    assert got == {0: "deck", 1: "ps"}
    # both named: the file isn't needed
    assert pads.resolve([(0, "Steam Deck Controller"), (3, "DualSense Wireless Controller")], []) \
        == {0: "deck", 3: "ps"}
    # no file / nothing left: generic falls back to letters
    assert pads.resolve([(5, "Steam Virtual Gamepad")], []) == {5: "xbox"}


def test_pick_follows_last_pressed_pad():
    kinds = {0: "deck", 1: "ps"}
    assert pads.pick(kinds, last=0) == "deck"
    assert pads.pick(kinds, last=1) == "ps"
    assert pads.pick(kinds) == "ps"             # before any press: the pad that isn't the Deck's
    assert pads.pick({0: "deck"}) == "deck"
    assert pads.pick({}) == "deck"
    assert pads.pick(kinds, last=9) == "ps"     # unplugged pad


def test_button_names_in_text():
    assert pads.name("A", "ps") == "Cross" and pads.name("Y", "ps") == "Triangle"
    assert (pads.name("BACK", "ps"), pads.name("START", "ps")) == ("Create", "Options")
    assert (pads.name("BACK", "deck"), pads.name("START", "deck")) == ("View", "Menu")
    assert pads.name("L1", "xbox") == "LB"
    pads.set_current("ps")
    try:
        from itch_deck.ui.scenes.setup import KEYBOARD
        assert KEYBOARD() == "PS + Square"
        assert pads.name("A") == "Cross"
    finally:
        pads.set_current("deck")
    assert pads.name("A") == "A"


def _theme():
    pg.init()
    from itch_deck.theme import Theme
    return Theme(pg, (1280, 800))


def test_glyphs_differ_per_pad():
    from itch_deck.ui import widgets as W
    t = _theme()

    def shot(btn, kind):
        s = pg.Surface((200, 60))
        w = W.glyph(t, s, btn, 10, 30, kind=kind)
        return w, pg.image.tobytes(s, "RGB")

    for btn in ("A", "B", "X", "Y", "BACK", "MENU"):
        assert shot(btn, "deck")[1] != shot(btn, "ps")[1], btn
    # DualSense: four different symbols, same circle size as the Deck's letters
    imgs = {shot(b, "ps")[1] for b in "ABXY"}
    assert len(imgs) == 4
    assert shot("A", "ps")[0] == shot("A", "deck")[0]
    assert shot("BACK", "deck")[1] != shot("MENU", "deck")[1]   # ⧉ is not ☰
    assert shot("L1", "xbox")[0] >= shot("L1", "deck")[0]       # LB
    assert shot("START", "deck")[1] == shot("MENU", "deck")[1]


def test_quit_hint_line_uses_the_pad_in_use():
    from itch_deck.app_play import QUIT_HINT
    from itch_deck.ui import widgets as W
    t = _theme()
    out = {}
    for kind in ("deck", "ps"):
        pads.set_current(kind)
        s = pg.Surface((t.w, t.h))
        out[kind] = W.glyph_line(t, s, QUIT_HINT, t.cx, 300, t.f_body).w
    pads.set_current("deck")
    assert out["ps"] != out["deck"]         # Create / Options drawn like the pad, not ⧉ / ☰
    assert out["deck"] < t.w * 0.8 and out["ps"] < t.w * 0.8


class _Pad:
    def __init__(self, name):
        self.name = name

    def get_axis(self, _):
        return 0


def test_input_follows_the_pad_you_press(tmp_path, monkeypatch):
    f = tmp_path / "virtualgamepadinfo.txt"
    f.write_text(SLOTS)
    monkeypatch.setenv("SteamVirtualGamepadInfo", str(f))
    pg.init()
    from itch_deck.input import Input
    inp = Input(pg)
    inp.pads = {10: _Pad("Steam Deck Controller"), 11: _Pad("Steam Virtual Gamepad")}
    inp._kinds()
    assert inp.kinds == {10: "deck", 11: "ps"}
    assert inp.kind() == "ps"                       # DualSense on: its glyphs before a press
    for iid, want in ((10, "deck"), (11, "ps"), (10, "deck")):
        pg.event.post(pg.event.Event(pg.CONTROLLERBUTTONDOWN, instance_id=iid,
                                     button=pg.CONTROLLER_BUTTON_A))
        assert "A" in inp.poll()
        assert inp.kind() == want
    pg.event.post(pg.event.Event(pg.CONTROLLERDEVICEREMOVED, instance_id=10))
    inp.poll()
    assert inp.kind() == "ps"                       # Deck pad gone -> the DualSense


def test_known_kinds_stick_and_guesses_are_retried():
    g = set()
    assert pads.resolve([(1, "Steam Virtual Gamepad")], ["deck", "ps"], known={1: "ps"}) == {1: "ps"}
    assert pads.resolve([(7, "Steam Virtual Gamepad")], [], guessed=g) == {7: "xbox"} and g == {7}


def test_dualsense_create_options_like_the_pad():
    """Omri's reference: small button leaning outward, icon above (Create fan, Options ≡)."""
    from itch_deck.ui import widgets as W
    t = _theme()
    h = int(t.u * 3.0 * 1.25)
    cr, op = W._ps_small("BACK", h, t.glyph_c), W._ps_small("MENU", h, t.glyph_c)
    assert cr.get_height() == h and cr.get_width() < h            # taller than wide
    assert pg.image.tobytes(cr, "RGBA") != pg.image.tobytes(op, "RGBA")
    for img in (cr, op):                     # icon band on top, gap, then the button
        rows = [any(img.get_at((x, y)).a > 128 for x in range(img.get_width()))
                for y in range(img.get_height())]
        assert rows[img.get_height() // 8] and rows[-img.get_height() // 4]
