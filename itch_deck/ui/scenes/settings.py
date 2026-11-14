"""P4 Settings."""
import pygame as pg

from ...input import UP, DOWN
from .. import widgets as W
from .base import Scene


class Settings(Scene):
    def __init__(self, t, values, version, log_path, focus=0, **kw):
        super().__init__(t, **kw)
        self.v, self.version, self.log_path, self.focus = values, version, log_path, focus

    def items(self):
        v = self.v
        return [
            ("Install location", v["install_label"], f"{v['install_path']} · {v['free']} free · new installs only"),
            ("Proton version", v["proton"], "Used for Windows games"),
            ("Saves of uninstalled games", v["prefix_size"], "Kept so reinstalling keeps your progress · A to delete"),
            ("Refresh library", "", f"Last synced {v['last_sync']}"),
            ("Update app", v["update"], "Downloads the newest version from GitHub. Old one kept as backup."),
            ("Re-import API key", "", "Reads ~/Downloads/itch_key.txt again"),
        ]

    def press_key(self):
        return ("row", self.items()[self.focus][0])

    def handle(self, act):
        n = len(self.items())
        if act in (UP, DOWN):
            self.focus = (self.focus + (1 if act == DOWN else -1)) % n

    def hints(self):
        return [("A", "Select"), ("B", "Back")]

    def draw_page(self, s):
        t = self.t
        w = min(t.w - 2 * t.m, t.u * 110)
        x = int(t.cx - w / 2)
        y = int(t.m * 0.9)
        y = W.text(t, s, "Settings", x, y, t.f_h1).bottom + t.u * 3
        row_h = int(min(t.u * 8.5, (t.h - t.hint_h - y - t.u * 8) / len(self.items()) - t.u // 2))
        W.rows(t, s, pg.Rect(x, y, w, 0), self.items(), self.focus, row_h)
        W.text(t, s, f"{W.APP_NAME} v{self.version}   ·   Log: {self.log_path}", x,
               t.h - t.hint_h - t.u * 3, t.f_small, color=t.dim, anchor="bottomleft", maxw=w)
