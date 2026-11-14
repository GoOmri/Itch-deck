"""P2 Library (home): store tab, All/Installed filter, cover grid."""
import pygame as pg

from ...input import UP, DOWN, LEFT, RIGHT, X, L2, R2
from .. import widgets as W
from .base import Scene


class Library(Scene):
    def __init__(self, t, games, filt="all", focus=0, syncing=None, sync_page=0,
                 offline_since=None, offline=False, **kw):
        super().__init__(t, **kw)
        self.games, self.filt, self.focus = games, filt, focus
        self.syncing, self.sync_page = syncing, sync_page   # None | "first" | "bg"
        self.offline_since = offline_since
        self.offline = offline          # True with no cache yet: nothing to show
        self.activity = None            # "Covers 40/120", "Downloading 45% · Game"… (top bar)

    @property
    def shown(self):
        if self.filt == "installed":
            return [g for g in self.games if g.get("state") == "installed"]
        return self.games

    # --- input ---------------------------------------------------------
    def handle(self, act):
        n, c = len(self.shown), self.t.grid_cols
        if act == X:
            self.filt = "installed" if self.filt == "all" else "all"
            self.focus, self._first, self._sy = 0, 0, None
        elif n:
            step = {LEFT: -1, RIGHT: 1, UP: -c, DOWN: c, L2: -3 * c, R2: 3 * c}.get(act, 0)
            if step:
                self.focus = max(0, min(n - 1, self.focus + step))

    # --- drawing -------------------------------------------------------
    def hints(self):
        if self.syncing == "first":
            return [("B", "Quit")]
        return [("MENU", "Settings"), ("Y", "Refresh"), ("L1", ""), ("R1", "Tabs"), ("A", "Open"),
                ("B", "All games" if self.filt == "installed" else "Quit")]

    def draw_page(self, s):
        t = self.t
        y = self._top_bar(s)
        if self.syncing == "first":
            return self._center_msg(s, y, f"Syncing library… page {self.sync_page}",
                                    "This is only slow the first time.", spinner=True)
        if not self.shown:
            if self.filt == "installed":
                return self._center_msg(s, y, "Nothing installed yet.",
                                        "Press X to see all your games.")
            if self.offline:
                return self._center_msg(s, y, "Can't reach itch.io.",
                                        "Check Wi-Fi, then press Y to try again.", refresh=True)
            return self._center_msg(s, y, "No games yet.",
                                    "Games you buy or claim on itch show up here.", refresh=True)
        self._grid(s, y)

    def _top_bar(self, s):
        t = self.t
        cy = t.m * 0.5 + t.u * 3
        r = W.pill(t, s, "itch", t.m, cy, fill=t.accent, color=t.on_accent, font=t.f_btn,
                   anchor="midleft")
        x = r.right + t.u * 5
        for key, label in (("all", "All"), ("installed", "Installed")):
            on = self.filt == key
            lr = W.text(t, s, label, x, cy, t.f_btn, color=t.text_c if on else t.faint,
                        anchor="midleft")
            if on:
                pg.draw.rect(s, t.accent, (lr.x, lr.bottom + t.u * 0.5, lr.w, max(2, t.u // 3)))
            x = lr.right + t.u * 3
        n = len(self.shown)
        right = t.w - t.m
        if self.offline_since:
            right = W.offline_mark(t, s, right, cy, self.offline_since)
        rr = W.text(t, s, f"{n} game{'s' if n != 1 else ''}", right, cy, t.f_small,
                    color=t.dim, anchor="midright")
        act = self.activity or ("Refreshing library" if self.syncing == "bg" else None)
        if act:                         # background work, hidden when done
            sep = W.text(t, s, "·", rr.x - t.u * 1.5, cy, t.f_small, color=t.faint, anchor="midright")
            ar = W.text(t, s, act, sep.x - t.u * 1.5, cy, t.f_small, color=t.dim, anchor="midright",
                        maxw=int(t.w * 0.38))
            W.spinner(t, s, (int(ar.x - t.u * 2.5), int(cy)), int(t.u * 1.2), 0.15)
        return int(cy + t.u * 6)

    def _center_msg(self, s, y, title, sub, spinner=False, refresh=False):
        t = self.t
        cy = (y + t.h - t.hint_h) / 2
        if spinner:
            W.spinner(t, s, (int(t.cx), int(cy - t.u * 7)), int(t.u * 3), 0.2)
        W.text(t, s, title, t.cx, cy, t.f_h2, anchor="center")
        W.text(t, s, sub, t.cx, cy + t.u * 4.5, t.f_body, color=t.dim, anchor="center")
        if refresh:
            g = W.glyph(t, s, "Y", 0, -100)  # measure
            lbl = t.f_body.size("Refresh")[0]
            x = t.cx - (g + t.u + lbl) / 2
            W.glyph(t, s, "Y", x, cy + t.u * 10)
            W.text(t, s, "Refresh", x + g + t.u, cy + t.u * 10, t.f_body, anchor="midleft")

    def _grid(self, s, top):
        t = self.t
        cols = t.grid_cols
        tw = (t.w - 2 * t.m - t.gap * (cols - 1)) / cols
        th = tw * t.cover_ratio
        row_h = th + t.u * 1.2 + t.f_small.get_height() * 2 + t.gap
        pad = int(tw * (t.focus_scale - 1) / 2 + t.outline + 2)
        area = pg.Rect(0, top, t.w, t.h - t.hint_h - top)
        visible = max(1, int((area.h - pad) // row_h))
        frow = self.focus // cols
        first = getattr(self, "_first", 0)          # scroll only when focus leaves the view
        first = min(max(first, frow - visible + 1), frow)
        self._first = first
        self._sy = W.ease(getattr(self, "_sy", None), first * row_h)
        sy = self._sy[0]
        r0 = int(sy // row_h)
        s.set_clip(area)
        y0 = top + pad - sy
        for i, g in enumerate(self.shown):
            row, col = divmod(i, cols)
            if row < r0 or row > r0 + visible + 1:
                continue
            rect = pg.Rect(int(t.m + col * (tw + t.gap)), int(y0 + row * row_h),
                           int(tw), int(th))
            if i != self.focus:
                W.tile(t, s, g, rect)
        if self.shown:  # focused tile last, so its outline sits on top
            row, col = divmod(self.focus, cols)
            rect = pg.Rect(int(t.m + col * (tw + t.gap)), int(y0 + row * row_h),
                           int(tw), int(th))
            W.tile(t, s, self.shown[self.focus], rect, focused=True)
        s.set_clip(None)
