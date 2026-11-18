"""v0.9.30: each DOS game has its own controller keys (assets/dos_controls.json, dos_controls.py, mouse.Mapper)."""
import json
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dos_controls as DC, keynames, mouse, pads  # noqa: E402


# --- the file ----------------------------------------------------------------------------------------------------
def _raw():
    def no_dupes(pairs):
        keys = [k for k, _ in pairs]
        assert len(keys) == len(set(keys)), f"duplicate keys in {keys}"
        return dict(pairs)
    return json.loads(DC.FILE.read_text(encoding="utf-8"), object_pairs_hook=no_dupes)


def test_every_entry_in_the_file_is_valid_and_unverified():
    data = _raw()
    assert len(data["games"]) >= 13
    ids = [e["id"] for e in data["games"]]
    assert len(ids) == len(set(ids))
    for e in data["games"]:
        assert DC.problems(e) == [], (e["id"], DC.problems(e))
        assert e["verified"] is False                              # all from memory until tested on a Deck
        for b, k in e["map"].items():
            assert b in DC.BUTTONS and k in keynames.CODES
        for hb, text in e["hints"]:                                # every hint names a button that does something
            if hb not in ("DPAD", "RSTICK"):
                assert hb.lower() in e["map"], (e["id"], hb)
            assert text and "KEY_" not in text and "ctrl" not in text.lower().split()
    assert len(DC.load()) == len(data["games"])


def test_the_mapper_can_press_every_key_the_file_uses():
    for e in DC.load():
        for k in e["map"].values():
            assert keynames.CODES[k] in mouse.KEYS


def test_broken_or_missing_files_fall_back_to_the_default_and_log_once(tmp_path, monkeypatch, caplog):
    import logging
    DC.reset()
    bad = tmp_path / "x.json"
    bad.write_text("{ not json")
    monkeypatch.setattr(DC, "FILE", bad)
    with caplog.at_level(logging.WARNING, logger="scritch"):
        assert DC.load() == [] and DC.match("Doom") is None
        DC._cache["entries"] = None
        DC.load()
    assert len([r for r in caplog.records if "unreadable" in r.getMessage()]) == 1     # once
    p = DC.plan({"title": "Doom"}, "auto")
    assert p["keymap"]["a"] == "ctrl" and p["layout"] == "keysmouse"                    # the default
    DC.reset()
    monkeypatch.setattr(DC, "FILE", tmp_path / "missing.json")
    assert DC.load() == []
    DC.reset()
    one_bad = tmp_path / "y.json"
    one_bad.write_text(json.dumps({"games": [
        {"id": "ok", "names": ["good game"], "layout": "keys", "map": {"a": "ctrl"}, "hints": [["A", "Jump"]]},
        {"id": "bad", "names": ["bad game"], "layout": "keys", "map": {"zz": "ctrl", "a": "nokey"}, "hints": []}]}))
    monkeypatch.setattr(DC, "FILE", one_bad)
    assert [e["id"] for e in DC.load()] == ["ok"]                                        # the broken entry is skipped
    DC.reset()


# --- matching ------------------------------------------------------------------------------------------------------
def test_matching_keeps_the_numbers_apart():
    DC.reset()
    m = lambda t: (DC.match(t) or {}).get("id")  # noqa: E731
    assert m("Doom") == m("Doom II") == m("DOOM (1993)") == m("doom") == "doom"
    assert m("DOOM + DOOM II") == "doom"
    assert m("Doom 3") is None and m("DOOM 64") is None                        # not DOS games here
    assert m("Commander Keen 3 Keen Must Die (1990)(Apogee Software)") == "keen123"
    assert m("Commander Keen 1 Marooned on Mars (1990)") == "keen123"
    assert m("Keen 2") == "keen123"
    for n in (4, 5, 6):
        assert m(f"Commander Keen {n}") == "keen456"
    assert m("Commander Keen 5 The Armageddon Machine") == "keen456"
    assert m("Commander Keen 7") is None and m("Commander Keen Complete Pack") is None
    assert m("dave2") == m("Dave") == m("Dangerous Dave in the Haunted Mansion") == "dave"
    assert m("Dave the Diver 2") is None
    assert m("Bio Menace Episode 1 (1993)(Apogee Software)") == "biomenace"
    assert m("Duke Nukem 2 (1991)") == "duke2" and m("Duke Nukem 3D (1996)(3D Realms)") == "duke3d"
    assert m("Wolfenstein 3D") == "wolf3d" and m("Blood (1997)(Monolith)") == "blood"
    assert m("Blood II") is None and m("Quake") == "quake" and m("Quake II") is None
    assert m("Jazz Jackrabbit") == "jazz" and m("Raptor") == "raptor"
    assert m("Indiana Jones and the Fate of Atlantis") == "indy4"
    assert m("Some Unknown Game") is None and m("") is None and m(None) is None


# --- plans: default, Auto, forced -------------------------------------------------------------------------------------
def test_the_default_for_a_game_without_an_entry():
    p = DC.plan({"title": "Unknown Game"}, "auto")
    assert p["eff"] == "keys" and p["layout"] == "keysmouse" and p["verified"] is False and p["source"] == "default"
    assert p["keymap"] == {"a": "ctrl", "b": "alt", "x": "space", "y": "enter", "l1": "shift", "r1": "tab",
                           "start": "esc"}
    assert p["hints"][0] == ["A", "Ctrl"]


def test_auto_picks_the_games_entry_and_the_player_can_force_a_mode():
    keen = {"title": "Commander Keen 4"}
    a = DC.plan(keen, "auto")
    assert a["eff"] == "keys" and a["layout"] == "keys" and a["keymap"]["b"] == "alt" and a["verified"] is False
    assert DC.plan(keen, "keys")["keymap"] == a["keymap"]                      # forced Keys: still the game's keys
    pad = DC.plan(keen, "gamepad")
    assert pad["eff"] == "gamepad" and pad["keymap"] is None and pad["hints"] is None
    assert DC.plan(keen, "mouse")["layout"] == "mouse" and DC.plan(keen, "mouse")["keymap"] is None
    indy = {"title": "Indiana Jones and the Fate of Atlantis"}
    i = DC.plan(indy, "auto")
    assert i["eff"] == "mouse" and i["layout"] == "mouse" and i["keymap"]["y"] == "esc"
    assert DC.plan(indy, "keys")["keymap"]["a"] == "ctrl"                      # forced Keys on a mouse game: default keys


def test_only_dos_games_get_a_plan_in_the_app(tmp_path):
    from itch_deck import app as appmod, paths
    paths.use_root(tmp_path / "home")
    a = appmod.App(windowed=True)
    itch = {"id": "i1", "title": "Doom", "store": "itch", "platforms": {"linux"}, "inputs": ["Gamepad"]}
    assert a.controls_plan(itch) is None and a.controls_of(itch) == ("auto", "gamepad")     # unchanged
    own = {"id": "d1", "title": "Doom", "store": "dos", "platforms": {"linux"}}
    assert a.controls_plan(own)["keymap"]["a"] == "ctrl" and a.controls_of(own) == ("auto", "keys")
    gogdos = {"id": "gog-1", "title": "Doom II", "store": "gog", "dos": True, "platforms": {"windows"}}
    assert a.controls_plan(gogdos)["name"] == "doom"                          # GOG DOS games too
    a.cfg["controls"] = {"d1": "gamepad"}
    assert a.controls_of(own) == ("gamepad", "gamepad")
    a.cfg["controls"] = {"d1": "nonsense"}
    assert a.controls_of(own)[0] == "auto"


# --- the mapper -------------------------------------------------------------------------------------------------------
C = keynames.CODES


def keys_of(ev):
    return {(c, v) for t, c, v in ev if t == mouse.EV_KEY}


def test_a_keymap_presses_the_games_keys_and_releases_them():
    m = mouse.Mapper("normal", "keys", DC.plan({"title": "Commander Keen 4"})["keymap"])
    ev = m.step({"a": True, "b": True, "x": True}, 0.01)
    assert keys_of(ev) == {(C["ctrl"], 1), (C["alt"], 1), (C["space"], 1)}
    assert m.step({"a": True, "b": True, "x": True}, 0.01) == []              # held: no repeat
    ev = m.step({"b": True, "up": True}, 0.01)
    assert keys_of(ev) == {(C["ctrl"], 0), (C["space"], 0), (C["up"], 1)}
    assert keys_of(m.step({"lx": 0.9}, 0.01)) == {(C["alt"], 0), (C["up"], 0), (C["right"], 1)}   # the stick = arrows
    assert sorted(keys_of(m.release_all())) == [(C["right"], 0)] and m.codes == set()


def test_keys_only_has_no_pointer_and_keysmouse_has_pointer_and_clicks():
    keys = mouse.Mapper("normal", "keys", {"a": "ctrl"})
    assert keys.step({"rx": 1.0, "rt": 1.0}, 0.1) == []                        # nothing: no pointer, no click
    km = mouse.Mapper("normal", "keysmouse", {"a": "ctrl"})
    ev = km.step({"rx": 1.0, "rt": 1.0, "lt": 1.0}, 0.1)
    assert (mouse.EV_REL, mouse.REL_X, 120) in ev
    assert keys_of(ev) == {(mouse.BTN_LEFT, 1), (mouse.BTN_RIGHT, 1)}
    on_keys = mouse.Mapper("normal", "keysmouse", {"r2": "ctrl", "l2": "alt"})  # triggers given to keys: no clicks
    assert keys_of(on_keys.step({"rt": 1.0, "lt": 1.0}, 0.01)) == {(C["ctrl"], 1), (C["alt"], 1)}


def test_the_default_layout_emits_the_default_keys():
    m = mouse.Mapper("normal", "keysmouse", DC.DEFAULT["map"])
    st = {"a": True, "b": True, "x": True, "y": True, "l1": True, "r1": True, "start": True}
    assert keys_of(m.step(st, 0.01)) == {(C[k], 1) for k in ("ctrl", "alt", "space", "enter", "shift", "tab", "esc")}


def test_the_point_and_click_layout():
    m = mouse.Mapper("normal", "mouse", DC.plan({"title": "Indiana Jones and the Fate of Atlantis"})["keymap"])
    ev = m.step({"a": True, "b": True, "y": True, "rx": 1.0}, 0.1)
    assert keys_of(ev) == {(mouse.BTN_LEFT, 1), (mouse.BTN_RIGHT, 1), (C["esc"], 1)}
    assert (mouse.EV_REL, mouse.REL_X, 120) in ev
    assert keys_of(m.step({}, 0.01)) <= {(mouse.BTN_LEFT, 0), (mouse.BTN_RIGHT, 0), (C["esc"], 0)}


def test_an_unknown_key_in_a_map_is_ignored_not_fatal():
    m = mouse.Mapper("normal", "keys", {"a": "ctrl", "b": "no-such-key"})
    assert keys_of(m.step({"a": True, "b": True}, 0.01)) == {(C["ctrl"], 1)}


def test_the_old_layouts_are_untouched():
    m = mouse.Mapper("normal", layout="keys")
    ev = m.step({"a": True, "x": True, "start": True}, 0.01)
    assert keys_of(ev) == {(mouse.KEY_SPACE, 1), (mouse.KEY_Z, 1), (mouse.KEY_ENTER, 1)}


# --- words for the player --------------------------------------------------------------------------------------------
def test_the_hint_text_uses_the_names_of_the_pad_in_use():
    hints = DC.plan({"title": "Doom"})["hints"]
    deck = DC.hint_text(hints, lambda b: pads.name(b, "deck"), 3)
    ps = DC.hint_text(hints, lambda b: pads.name(b, "ps"), 3)
    assert deck.startswith("A Fire  ·  B Open doors  ·  X Run")
    assert ps.startswith("Cross Fire  ·  Circle Open doors  ·  Square Run")
    assert "Options" in DC.hint_text([["START", "Menu"]], lambda b: pads.name(b, "ps"))
    assert DC.hint_text([["DPAD", "Move"], ["RSTICK", "Look"]], pads.name) == "D-pad Move  ·  Right stick Look"
    assert DC.hint_text([["L1", "Step"]], lambda b: pads.name(b, "xbox")) == "LB Step"


def _page(tmp_path, g):
    from itch_deck import theme
    from itch_deck.ui.scenes.game import Game
    pg.init()
    pg.display.set_mode((64, 64))
    t = theme.Theme(pg, (1280, 800))
    sc = Game(t, g, pos=(1, 1))
    s = pg.Surface((1280, 800))
    sc.draw(s)
    return sc, s


def _doom(**k):
    plan = DC.plan({"title": "Doom"})
    return dict({"id": "d1", "title": "Doom", "store": "dos", "dos": True, "state": "installed", "platforms": {"linux"},
                 "size_mb": 10, "author": "", "description": ["A short text."], "details_from": "GOG",
                 "dos_hints": plan["hints"], "dos_verified": False, "controls_mode": "keys",
                 "controls_hint": "A Fire  ·  B Open doors  ·  X Run"}, **k)


def test_the_game_page_shows_the_controls_block_and_the_guess_line(tmp_path):
    sc, s = _page(tmp_path, _doom())
    assert sc._end > 0
    h_with = sc._end
    sc2, _s = _page(tmp_path, _doom(dos_hints=None))
    assert h_with > sc2._end                                       # the block takes room under the text
    rows = None
    sc.open_options()
    rows = sc.overlay[3]
    ctl = next(r for r in rows if r[0] == "Controls")
    assert ctl[2] == "A Fire  ·  B Open doors  ·  X Run"           # the one-line hint on the Controls row


def test_the_controls_block_is_drawn_for_both_pads(tmp_path):
    for kind in ("deck", "ps"):
        pads.set_current(kind)
        try:
            sc, s = _page(tmp_path, _doom(dos_verified=True))
            assert sc._end > 0
        finally:
            pads.set_current("deck")
