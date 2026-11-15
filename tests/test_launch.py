"""Game launch handover: wait for the game's window, hide ours, show it again (v0.6.5)."""
import os
import shutil
import subprocess
import sys
import time

import pytest

from itch_deck import runner


def test_window_watch_without_display(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    w = runner.WindowWatch()
    assert not w.ok and not w.appeared()     # caller falls back to the OVERLAP_S timer
    w.close()


CHILD = """
import time, pygame as pg
time.sleep(0.6)
pg.display.init(); pg.display.set_mode((320, 200)); pg.display.flip()
t = time.time()
while time.time() - t < 2: pg.event.pump(); time.sleep(0.05)
"""


@pytest.fixture
def xserver():
    if not shutil.which("Xvfb"):
        pytest.skip("no Xvfb")
    disp = ":97"
    x = subprocess.Popen(["Xvfb", disp, "-screen", "0", "800x600x24"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    yield disp
    x.terminate()
    x.wait(5)


def test_window_watch_sees_the_game_window(xserver, monkeypatch, tmp_path):
    monkeypatch.setenv("DISPLAY", xserver)
    w = runner.WindowWatch()
    assert w.ok and not w.appeared()
    env = dict(os.environ, DISPLAY=xserver, SDL_VIDEODRIVER="x11", SDL_AUDIODRIVER="dummy")
    child = subprocess.Popen([sys.executable, "-c", CHILD], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while not w.appeared() and time.time() - t0 < 8:
        time.sleep(0.05)
    seen = time.time() - t0
    child.wait(10)
    w.close()
    assert 0.4 < seen < 8, seen               # after the child's 0.6 s start-up, not at once


def test_quit_combo_needs_both_buttons_held():
    from itch_deck import mouse
    fired = []
    c = mouse.QuitCombo(None, {}, lambda: fired.append(1))
    both, one = {"back": True, "start": True}, {"start": True}
    c.feed(both, 0.0)
    c.feed(both, 1.9)
    assert not fired
    c.feed(one, 2.0)                          # let go of one: the timer starts over
    c.feed(both, 2.1)
    c.feed(both, 4.0)
    assert not fired
    c.feed(both, 4.2)
    assert fired == [1]
    c.feed(both, 9.0)                         # fires once
    assert fired == [1] and c.fired


def test_stop_child_closes_the_whole_game(tmp_path, monkeypatch):
    """A game that starts helpers (Proton/Wine do): all of them go, not just the first."""
    import threading
    from itch_deck import paths
    paths.use_root(tmp_path)
    pidfile = tmp_path / "helper.pid"
    exe = tmp_path / "game.sh"
    exe.write_text(f"#!/bin/sh\nsleep 60 &\necho $! > {pidfile}\nwait\n")
    exe.chmod(0o755)
    out = {}
    th = threading.Thread(target=lambda: out.update(rc=runner.run(exe, "g")), daemon=True)
    th.start()
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text().strip():
            break
        time.sleep(0.05)
    helper = int(pidfile.read_text())
    runner.stop_child(grace=1.0)
    th.join(10)
    assert not th.is_alive() and out["rc"][0] != 0
    time.sleep(0.3)
    try:                                      # gone, or a zombie (killed, not yet reaped)
        state = open(f"/proc/{helper}/stat").read().rsplit(")", 1)[1].split()[0]
    except FileNotFoundError:
        state = "gone"
    assert state in ("gone", "Z"), f"helper still running ({state})"
