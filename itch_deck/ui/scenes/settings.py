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
            # sub-lines only where the info is needed (Omri): where games go, when last synced
            ("Install location", v["install_label"], f"{v['install_path']} · {v['free']} free"),
            ("Proton version", v["proton"], ""),
            ("Saves of uninstalled games", v["prefix_size"], ""),
            ("Refresh library", "", f"Last synced {v['last_sync']}"),
            ("Update app", v["update"], ""),
            ("Pointer speed", v.get("pointer", "Normal"), ""),
            ("Re-import API key", "", ""),
        ]

    def handle(self, act):
        n = len(self.items())
        if act in (UP, DOWN):
            self.focus = (self.focus + (1 if act == DOWN else -1)) % n

    def hints(self):
        return [("A", "Select"), ("B", "Back")]

    def draw_page(self, s):
        t = self.t
        w = min(t.w - 2 * t.m, t.page_w)
        x = int(t.cx - w / 2)
        y = t.m
        y = W.text(t, s, "Settings", x, y, t.f_h1).bottom + t.md
        row_h = int(min(t.u * 8.5, (t.h - t.hint_h - y - t.xl) / len(self.items()) - t.u // 2))
        W.rows(t, s, pg.Rect(x, y, w, 0), self.items(), self.focus, row_h, key="settings")
        line = f"{W.APP_NAME} v{self.version}"         # the log path lives in NOTES, not on screen
        W.text_named(t, s, line, x, t.h - t.hint_h - t.md - t.f_small.get_height(), t.f_small,
                     color=t.dim, maxw=w)
