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
