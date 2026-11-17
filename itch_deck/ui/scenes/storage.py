"""Manage games: the installed games by size, tick several, uninstall them together (storagemgr.py)."""
import pygame as pg

from ... import storagemgr as SM
from ...input import UP, DOWN, L2, R2, A, Y
from .. import widgets as W
from .base import Scene


def _gb(n):
    return f"{n / 1e9:.0f} GB" if n >= 10e9 else f"{n / 1e9:.1f} GB"


class StorageManager(Scene):
    def __init__(self, t, items, drives=(), sort="size", selected=None, focus=0, **kw):
        super().__init__(t, **kw)
        self.items, self.drives, self.sort = list(items), list(drives), sort
        self.selected = set(selected or ())
        self.focus, self.first = focus, 0

    # --- data ---------------------------------------------------------------------------------------
    def rows(self):
        return SM.ordered(self.items, self.sort)

    def set_items(self, items):
        """New data (a game was uninstalled): the selection keeps only games that are still there."""
        self.items = list(items)
        self.selected &= {e["id"] for e in self.items}
        self.focus = max(0, min(self.focus, len(self.items) - 1))

    def selected_mb(self):
        return SM.total_mb(self.items, self.selected)

    # --- input -----------------------------------------------------------------------------------------
    def handle(self, act):
        rows, n = self.rows(), len(self.items)
        if act in (UP, DOWN, L2, R2) and n:
            step = {UP: -1, DOWN: 1, L2: -6, R2: 6}[act]
            self.focus = (self.focus + step) % n if abs(step) == 1 else max(0, min(n - 1, self.focus + step))
        elif act == A and rows:
            gid = rows[self.focus]["id"]
            self.selected ^= {gid}
        elif act == Y:
            keys = [k for k, _ in SM.SORTS]
            self.sort = keys[(keys.index(self.sort) + 1) % len(keys)]

    def hints(self):
        h = [("A", "Tick"), ("Y", "Sort: " + dict(SM.SORTS)[self.sort])]
        if self.selected:
            h.append(("X", "Uninstall"))
        return h + [("B", "Back")]

    # --- drawing -----------------------------------------------------------------------------------------
    def draw_page(self, s):
        t = self.t
        w = min(t.w - 2 * t.m, t.page_w)
        x = int(t.cx - w / 2)
        y = W.text(t, s, "Manage games", x, t.m, t.f_h1).bottom + t.xs
        y = W.text(t, s, "Tick games and uninstall them together to free space. Windows saves are kept.",
                   x, y, t.f_small, color=t.dim, maxw=w).bottom + t.sm
        for d in self.drives:                                    # SD card: 112 GB free of 256 GB
            line = f"{d['name']}:  {_gb(d['free'])} free of {_gb(d['total'])}"
            y = W.text(t, s, line, x, y, t.f_small, color=t.text_c).bottom + t.xs
        y += t.xs
        rows = self.rows()
        total = SM.total_mb(self.items)
        left = f"{len(rows)} game{'' if len(rows) == 1 else 's'}  ·  {SM.mb_text(total)}"
        W.text(t, s, left, x, y, t.f_small, color=t.dim)
        if self.selected:
            sel = f"{len(self.selected)} selected  ·  frees {SM.mb_text(self.selected_mb())}"
            W.text(t, s, sel, x + w, y, t.f_small, color=t.accent, anchor="topright")
        y += t.f_small.get_height() + t.sm
        if not rows:
            W.text(t, s, "No installed games.", t.cx, int(t.h * 0.45), t.f_h2, anchor="midtop")
            W.text(t, s, "Games you install show up here.", t.cx, int(t.h * 0.45) + t.f_h2.get_height() + t.xs,
                   t.f_body, color=t.dim, anchor="midtop")
            return
        row_h = int(t.u * 7)
        gap = t.u // 2
        room = t.h - t.hint_h - t.sm - y
        per = max(1, room // (row_h + gap))
        if self.focus < self.first:                          # keep the focused row on screen
            self.first = self.focus
        elif self.focus >= self.first + per:
            self.first = self.focus - per + 1
        self.first = max(0, min(self.first, max(0, len(rows) - per)))
        pad = t.md
        for i in range(self.first, min(len(rows), self.first + per)):
            e = rows[i]
            r = pg.Rect(x, y, w, row_h)
            k = W.anim(("stor", e["id"]), 1.0 if i == self.focus else 0.0)
            if k > 0.01:
                W.panel(t, s, r, W.mix(t.panel_hi, t.focus_fill, k))
                W.focus_sweep(t, s, r, k)
            box = pg.Rect(0, 0, int(row_h * 0.46), int(row_h * 0.46))
            box.midleft = (r.x + pad, r.centery)
            on = e["id"] in self.selected
            if on:
                pg.draw.rect(s, t.accent, box, border_radius=max(2, box.w // 6))
                W.icon_draw(s, "check", box.center, int(box.h * 0.9), (20, 15, 34))
            else:
                pg.draw.rect(s, t.dim, box, 2, border_radius=max(2, box.w // 6))
            text_x = box.right + pad
            size = W.text(t, s, SM.mb_text(e["size_mb"]), r.right - pad, r.centery, t.f_body,
                          color=t.text_c, anchor="midright")
            drive = W.text(t, s, e["drive"], size.x - t.md, r.centery, t.f_small, color=t.dim, anchor="midright")
            W.text(t, s, e["title"], text_x, r.centery, t.f_btn, anchor="midleft",
                   color=t.text_c, maxw=drive.x - t.md - text_x)
            y += row_h + gap
