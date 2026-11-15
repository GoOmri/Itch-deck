"""Mouse mode: stick -> pointer mapping, buttons, auto rule, itch Inputs parse, uinput check."""
from itch_deck import mouse
from itch_deck.stores import itch_page


def test_pointer_moves_with_deadzone_and_curve():
    m = mouse.Mapper("normal")
    assert m.step({"rx": 0.1, "ry": -0.1}, 0.1) == []              # inside the deadzone
    full = m.step({"rx": 1.0}, 0.1)
    assert full == [(mouse.EV_REL, mouse.REL_X, 120)]               # 1200 px/s * 0.1 s
    m2 = mouse.Mapper("normal")
    half = sum(v for _, c, v in m2.step({"rx": 0.6}, 0.1) if c == mouse.REL_X)
    assert 0 < half < 40                                            # curve: half tilt is slow
    assert m.step({"ry": -1.0}, 0.05) == [(mouse.EV_REL, mouse.REL_Y, -60)]
    assert mouse.Mapper("slow").px_s < mouse.Mapper("fast").px_s


def test_subpixel_moves_add_up():
    m = mouse.Mapper("slow")
    total = sum(v for _ in range(125) for _, c, v in m.step({"rx": 0.3}, 1 / 125))
    assert total > 0                                                # slow drift still moves


def test_buttons_press_and_release_once():
    m = mouse.Mapper()
    assert m.step({"rt": 0.9}, 0.01) == [(mouse.EV_KEY, mouse.BTN_LEFT, 1)]
    assert m.step({"rt": 0.9, "a": True}, 0.01) == []               # still held: no repeat
    assert m.step({}, 0.01) == [(mouse.EV_KEY, mouse.BTN_LEFT, 0)]
    ev = m.step({"x": True, "b": True, "up": True}, 0.01)
    assert (mouse.EV_KEY, mouse.BTN_RIGHT, 1) in ev and (mouse.EV_KEY, mouse.KEY_ESC, 1) in ev
    assert (mouse.EV_KEY, mouse.KEY_UP, 1) in ev
    assert sorted(m.release_all()) == sorted([(mouse.EV_KEY, c, 0) for c in
                                              (mouse.BTN_RIGHT, mouse.KEY_ESC, mouse.KEY_UP)])


def test_left_stick_scrolls():
    m = mouse.Mapper()
    ev = [e for _ in range(20) for e in m.step({"ly": 1.0}, 0.05)]
    assert ev and all(e == (mouse.EV_REL, mouse.REL_WHEEL, -1) for e in ev)


def test_auto_mode():
    assert mouse.auto_mode(["Mouse", "Touchscreen"]) == "mouse"
    assert mouse.auto_mode(["Keyboard", "Mouse"]) == "keys"      # Keys keeps the mouse too
    assert mouse.auto_mode(["Keyboard"]) == "keys"                # e.g. Cosmic Express
    assert mouse.auto_mode(["Keyboard", "Mouse", "Xbox controller"]) == "gamepad"
    assert mouse.auto_mode(["Gamepad (any)"]) == "gamepad"
    assert mouse.auto_mode([]) == "gamepad" and mouse.auto_mode(None) == "gamepad"


def test_parse_inputs_row():
    html = ('<table><tr><td>Author</td><td><a>Nicu</a></td></tr><tr><td>Inputs</td>'
            '<td><a href="/games/input-mouse">Mouse</a>, <a href="/x">Touchscreen</a></td></tr></table>')
    assert itch_page.parse_inputs(html) == ["Mouse", "Touchscreen"]
    assert itch_page.parse_inputs("<p>no table</p>") == []
    assert itch_page.parse(html)["inputs"] == ["Mouse", "Touchscreen"]


def test_uinput_check_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(mouse, "UINPUT", str(tmp_path / "nope"))
    ok, why = mouse.available()
    assert not ok and "doesn't exist" in why
    mm = mouse.MouseMode(None, {"p": object()})
    assert mm.start() is False and mm.error
    mm.stop()


def test_setup_struct_and_ioctl_size():
    import struct
    assert struct.calcsize(mouse.SETUP_FMT) == 92 and mouse.UI_DEV_SETUP == 0x405C5503
    assert struct.calcsize(mouse.EVENT_FMT) == 24


def test_parse_genre_and_session_rows():
    html = ('<table><tr><td>Genre</td><td><a>Puzzle</a>, <a>Adventure</a></td></tr>'
            '<tr><td>Average session</td><td>About an hour</td></tr></table>')
    assert itch_page.parse_row(html, "Genre") == ["Puzzle", "Adventure"]
    assert itch_page.parse_row(html, "Average session") == ["About an hour"]
    assert itch_page.parse_row(html, "Inputs") == []



def test_keys_layout():
    m = mouse.Mapper("normal", layout="keys")
    ev = m.step({"a": True, "x": True, "y": True, "start": True, "l1": True, "r1": True,
                 "b": True}, 0.01)
    down = {c for t, c, v in ev if t == mouse.EV_KEY and v == 1}
    assert down == {mouse.KEY_SPACE, mouse.KEY_Z, mouse.KEY_X, mouse.KEY_ENTER, mouse.KEY_R,
                    mouse.KEY_LEFTSHIFT, mouse.KEY_ESC}
    assert mouse.BTN_LEFT not in down                    # A is Space here, not a click
    # left stick = arrow keys (not the scroll wheel), released when centred
    ev = m.step({"lx": -0.9, "ly": 0.8}, 0.01)
    assert {(c, v) for t, c, v in ev if t == mouse.EV_KEY} >= {(mouse.KEY_LEFT, 1), (mouse.KEY_DOWN, 1)}
    assert not any(t == mouse.EV_REL and c == mouse.REL_WHEEL for t, c, v in ev)
    ev = m.step({}, 0.01)
    assert {(c, v) for t, c, v in ev if t == mouse.EV_KEY} >= {(mouse.KEY_LEFT, 0), (mouse.KEY_DOWN, 0)}
    # right stick + R2 still drive the mouse
    ev = m.step({"rx": 1.0, "rt": 1.0}, 0.05)
    assert any(t == mouse.EV_REL and c == mouse.REL_X and v > 0 for t, c, v in ev)
    assert (mouse.EV_KEY, mouse.BTN_LEFT, 1) in ev
    assert {c for t, c, v in m.release_all()} >= {mouse.BTN_LEFT}


def test_mouse_layout_unchanged():
    m = mouse.Mapper("normal")
    ev = m.step({"a": True, "ly": 1.0}, 0.2)
    assert (mouse.EV_KEY, mouse.BTN_LEFT, 1) in ev
    assert any(t == mouse.EV_REL and c == mouse.REL_WHEEL for t, c, v in ev)
