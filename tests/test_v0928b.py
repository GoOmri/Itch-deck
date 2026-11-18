"""v0.9.28 review round: error catcher, run-once flag, version words, stable ids, long names."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import dosgames, paths  # noqa: E402
from itch_deck import installer as I  # noqa: E402
from test_v0928 import inst_two_roots, make_game  # noqa: E402


def _app_for(tmp_path):
    from itch_deck import app as appmod
    paths.use_root(tmp_path / "home")
    a = appmod.App(windowed=True)
    a.lib._fetch_dosart = lambda *x, **k: None
    return appmod, a


def _boom(msg):
    def f(*a, **k):
        raise RuntimeError(msg)
    return f


def test_one_error_is_written_once_and_repeats_are_only_counted(tmp_path, caplog):
    import logging
    appmod, a = _app_for(tmp_path)
    with caplog.at_level(logging.ERROR, logger="scritch"):
        for _ in range(4):
            try:
                raise KeyError("same")          # the same line every time
            except KeyError:
                a._frame_failed()
    assert len([r for r in caplog.records if r.exc_info]) == 1
    assert not [r for r in caplog.records if "same error again" in r.getMessage()]    # within 5 s: only counted
    try:
        raise ValueError("another")
    except ValueError:
        a._frame_failed()
    assert len([r for r in caplog.records if r.exc_info]) == 2                     # a different error gets its own


def test_a_failing_draw_then_recovery(tmp_path):
    appmod, a = _app_for(tmp_path)
    a.go_library()
    calls = []
    real = a.scene.draw

    def draw(s):
        calls.append(1)
        if len(calls) <= 3:
            raise RuntimeError("one tile")
        return real(s)
    a.scene.draw = draw
    a.run(max_frames=8)                                  # fails 3 times, then draws fine: the app lives
    assert len(calls) >= 5


def test_a_screen_that_never_recovers_stops_with_the_real_error(tmp_path):
    import pytest
    appmod, a = _app_for(tmp_path)
    a.go_library = lambda: None
    a.update = _boom("update never works")
    with pytest.raises(RuntimeError):
        a.run(max_frames=2000)                           # 3 trips, or 15 in 10 s: then the real error comes out


def test_a_failing_update_does_not_flood_the_log(tmp_path, caplog):
    import logging
    import pytest
    appmod, a = _app_for(tmp_path)
    a.update = _boom("update")
    a.go_library = lambda: None
    with caplog.at_level(logging.ERROR, logger="scritch"), pytest.raises(RuntimeError):
        a.run(max_frames=2000)
    assert len([r for r in caplog.records if r.exc_info]) == 1          # one traceback, not one per frame


def test_a_raising_apply_dos_never_stops_later_refreshes(tmp_path):
    appmod, a = _app_for(tmp_path)
    a.inst.apply_dos = _boom("disk")
    a.dos_busy = True
    a.dos_note = {"result": {"entries": []}, "tell": False, "failed": False}
    a._dos_tick(0)
    assert a.dos_busy is False                           # reset in a finally
    started = []
    a.inst.scan_dos = lambda create=False: started.append(1) or {"entries": []}
    a._start_dos_scan()
    assert a.dos_busy is True


def test_the_setup_flag_lives_in_memory_survives_a_rescan_and_runs_once(tmp_path, monkeypatch):
    from itch_deck import dosbox
    inst, lib, sd_dos, _ = inst_two_roots(tmp_path, monkeypatch)
    make_game(sd_dos / "Blood", "BLOOD.EXE", ["SETUP.EXE"])
    make_game(sd_dos / "Other", "O1.EXE", ["O2.EXE"])
    inst.sync_dos()
    blood, other = dosgames.game_id("Blood"), dosgames.game_id("Other")
    assert inst.run_once(blood, "SETUP.EXE")
    assert inst.set_exe(other, "O2.EXE")                  # saves installed.json
    inst.sync_dos()                                       # a rescan keeps the flag
    assert "once" not in paths.INSTALLS.read_text() and "once" not in str(inst.index)
    _e, args, _c = dosbox.launch_own(inst.index[blood], ["dosbox"], once=inst.take_once(blood))
    assert "SETUP.EXE" in args
    _e, args, _c = dosbox.launch_own(inst.index[blood], ["dosbox"], once=inst.take_once(blood))
    assert "BLOOD.EXE" in args and "SETUP.EXE" not in args
    inst.run_once(blood, "SETUP.EXE")
    fresh = I.Installer(lib, inst.root_fn)                # an app restart or a --play start: the game runs normally
    assert fresh.take_once(blood) is None


def test_version_words_are_dropped_whole():
    from itch_deck import dosart
    for n in ("Duke Nukem 3D v1.3d", "Duke Nukem 3D V1.3D", "Duke Nukem 3D ver 1.3d", "Duke Nukem 3D version 1.3d"):
        assert dosart.display(n)[0].lower() == "duke nukem 3d", n
        assert dosart.parse(n)["text"] == "duke nukem 3d", n
        assert dosart.search_name(n).lower() == "duke nukem 3d"       # and that is what GOG is asked
    for n, t in (("Game v1.0a", "Game"), ("Game v2.1b", "Game"), ("Game V1.2", "Game"), ("Game ver 1.1", "Game"),
                 ("Game version 1.1", "Game"), ("Wolfenstein 3D", "Wolfenstein 3D")):
        assert dosart.display(n)[0] == t, n


def test_second_copy_ids_do_not_depend_on_the_mount_path(tmp_path):
    ids = []
    for prefix in ("run/media/deck/CARD-A", "run/media/deck/other label"):
        base = tmp_path / prefix / "itch" / "dos"
        make_game(base / "doom")
        make_game(base / "DOS" / "doom")
        for i in range(3):
            make_game(base / "DOS" / f"g{i}")
        paths.use_root(tmp_path / ("home" + str(len(ids))))
        got = dosgames.scan(base, hide={})
        ids.append(sorted((e["name"], e["id"]) for e in got))
    assert ids[0] == ids[1]
    assert len({i for _n, i in ids[0]}) == 5


def test_a_very_long_program_name_is_cut_and_never_touches_the_setup_label():
    from itch_deck import theme
    from itch_deck.ui import widgets as W
    for size in ((1280, 800), (1920, 1080)):
        pg.init()
        pg.display.set_mode((64, 64))
        t = theme.Theme(pg, size)
        s = pg.Surface(size)
        name = "A" * 60 + ".EXE"
        items = [(name, "Setup", "GAMES/DEEP/" + "FOLDER/" * 12), ("SHORT.EXE", "In use", "Top folder")]
        W.forget_menu("Choose the program")
        r = W.menu(t, s, "Choose the program", "Pick one.", items, 0)
        assert r.left >= 0 and r.right <= t.w
        w = min(t.w - 2 * t.m, t.read_w)
        room = (w - 2 * (t.lg - t.md)) - 2 * t.md - (t.f_body.size("Setup")[0] + t.md)
        cut = W.fit(t.f_btn, name, room)
        assert cut.endswith("…") and t.f_btn.size(cut)[0] <= room
