"""P4 Settings."""
import pygame as pg

from ...input import UP, DOWN
from .. import widgets as W
from .base import Scene


class Settings(Scene):
    def __init__(self, t, values, version, log_path, focus=0, **kw):
        super().__init__(t, **kw)
        self.v, self.version, self.log_path, self.focus = values, version, log_path, focus

    def groups(self):
        """Settings in 4 short groups (Omri). Only one sub-line: when the library last synced."""
        v = self.v
        return [
            ("Library", [("Refresh library", "", f"Last synced {v['last_sync']}"),
                         ("Re-import API key", "", "")]),
            ("Storage", [("Install location", v["install_label"], ""),  # SD card / Internal storage
                         ("Saves of uninstalled games", v["prefix_size"], "")]),
            ("Games", [("Proton version", v["proton"], ""),
                       ("Pointer speed", v.get("pointer", "Normal"), "")]),
            ("App", [("Update app", v["update"], "")]),
        ]

    def items(self):
        """Flat, in screen order: focus moves through every group (the app acts on labels)."""
        return [row for _, rows in self.groups() for row in rows]

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
        top = W.text(t, s, "Settings", x, y, t.f_h1).bottom + t.sm
        bottom = t.h - t.hint_h - t.lg - t.f_small.get_height()   # above the version line
        row_h, head_h = int(t.u * 8), t.sm + t.f_hint.get_linesize() + t.xs
        layout, y, i = [], 0, 0                  # (group, rows, first index, y) in list coords
        for title, rows in self.groups():
            layout.append((title, rows, i, y))
            y += head_h + len(rows) * (row_h + t.u // 2)
            i += len(rows)
        fy = next(gy + head_h + (self.focus - gi) * (row_h + t.u // 2)
                  for _, rows, gi, gy in layout if gi <= self.focus < gi + len(rows))
        view = bottom - top                      # scroll (no bounce) so the focused row shows
        want = getattr(self, "_want", 0)
        want = min(max(want, fy + row_h - view), fy - (head_h if fy - head_h < want else 0))
        self._want = max(0, min(want, max(0, y - view)))
        self._sy = W.ease(getattr(self, "_sy", None), self._want, back=0)
        s.set_clip(pg.Rect(0, top, t.w, view))
        for title, rows, gi, gy in layout:       # LABEL-style heading, then its rows
            yy = top + gy - int(self._sy[0])
            yy = W.text(t, s, title.upper(), x + t.md, yy + t.sm, t.f_hint, color=t.dim).bottom + t.xs
            f = self.focus - gi if gi <= self.focus < gi + len(rows) else None
            W.rows(t, s, pg.Rect(x, yy, w, 0), rows, f, row_h, key="settings")
        s.set_clip(None)
        line = f"{W.APP_NAME} v{self.version}"         # the log path lives in NOTES, not on screen
        W.text_named(t, s, line, x, t.h - t.hint_h - t.md - t.f_small.get_height(), t.f_small,
                     color=t.dim, maxw=w)
