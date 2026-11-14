"""Motion bookkeeping: an animation must count as 'moving' until it has finished, even when a
frame takes longer than the old 50 ms window (the game-page focus froze on heavy pages)."""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
from itch_deck.ui import widgets as W  # noqa: E402


def test_animating_lasts_until_the_tween_ends():
    W.LIVE = True
    try:
        W.anim(("test", "focus"), 0.0)          # settled at 0
        W.anim(("test", "focus"), 1.0)          # start moving to 1
        time.sleep(0.12)                        # a slow frame: longer than 50 ms
        assert W.animating()
        time.sleep(W.MOTION_MS / 1000)
        W.anim(("test", "focus"), 1.0)
        assert round(W._ANIM[("test", "focus")][0]) == 1000
    finally:
        W.LIVE = False
