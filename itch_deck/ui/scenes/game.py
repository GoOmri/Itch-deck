"""P3 Game page: big cover, info, state, actions. Picker (O1) and Confirm (O2) overlay it."""
import pygame as pg

from ...input import UP, DOWN
from .. import widgets as W
from .base import Scene

PLATFORM = {"linux": "Linux", "windows": "Windows · Proton", "html": "Browser",
            "mac": "macOS only", "soundtrack": "Soundtrack"}


def _mb(mb):
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


class Game(Scene):
    """phase (optional): 'download' | 'extract' | 'installing' | 'proton' — what an active
    install is doing right now. fail_reason: text for a failed install."""

    def __init__(self, t, game, pos=(1, 1), focus=0, phase=None, fail_reason=None,
                 install_path=None, **kw):
        super().__init__(t, **kw)
        self.g, self.pos, self.focus = game, pos, focus
        self.phase = phase or ("download" if game.get("state") == "downloading" else None)
        self.fail_reason = fail_reason
        self.install_path = install_path

    @property
    def playable(self):
        return bool(self.g["platforms"] & {"linux", "windows"})

    def actions(self):
        """[(label, icon, enabled)]"""
        st = self.g.get("state")
        if not self.playable:
            return []
        if st == "installed":
            return [("Play", "▶", True), ("Uninstall", None, True), ("Change build", None, True)]
        if st in ("downloading", "queued") or self.phase:
            return [("Cancel install", None, True)]
        if st == "failed":
            return [("Retry install", None, True), ("Change build", None, True)]
        return [("Install", None, True), ("Change build", None, True)]

    def handle(self, act):
        n = len(self.actions())
        if n and act in (UP, DOWN):
            self.focus = (self.focus + (1 if act == DOWN else -1)) % n

    def hints(self):
        h = [("A", "Select"), ("B", "Back"), ("LB", ""), ("RB", "Prev / next game")]
        if self.phase or self.g.get("state") in ("downloading", "queued"):
            h.insert(2, ("X", "Hold to cancel"))
        if not self.actions():
            h = h[1:]
        return h

    def overlay_hints(self):
        if not self.overlay:
            return None
        if self.overlay[0] == "picker":
            return [("A", "Choose"), ("B", "Cancel")]
        return [("A", "Uninstall"), ("B", "Cancel")]

    # --- drawing -------------------------------------------------------
    def draw_page(self, s):
        t, g = self.t, self.g
        self._hero(s)
        cw = int((t.w - 2 * t.m) * 0.40)
        ch = int(cw * t.cover_ratio)
        cover_r = pg.Rect(t.m, t.m + t.u * 2, cw, ch)
        img = W.rounded(W.cover(t, g, cover_r.size), t.u * 1.5)
        if not self.playable:
            o = pg.Surface(cover_r.size, pg.SRCALPHA)
            pg.draw.rect(o, (0, 0, 0, t.dimmed_a), o.get_rect(), border_radius=int(t.u * 1.5))
            img.blit(o, (0, 0))
        s.blit(img, cover_r)

        x = cover_r.right + t.u * 6
        maxw = t.w - t.m - x
        y = cover_r.y
        W.text(t, s, f"itch  ·  {self.pos[0]} of {self.pos[1]}", x, y, t.f_small, color=t.faint)
        y += t.u * 3.5
        y = W.text(t, s, g["title"], x, y, t.f_h1, maxw=maxw).bottom + t.u * 0.5
        y = W.text(t, s, f"by {g['author']}", x, y, t.f_body, color=t.dim).bottom + t.u * 2

        px = x
        plat = [p for p in ("linux", "windows", "html", "mac", "soundtrack") if p in g["platforms"]]
        for p in plat:
            px = W.pill(t, s, PLATFORM[p], px, y, fill=t.panel_hi).right + t.u
        if g["size_mb"]:
            px = W.pill(t, s, _mb(g["size_mb"]), px, y, fill=t.panel_hi).right + t.u
        if g.get("state") == "installed":
            W.pill(t, s, "✓ Installed", px, y, fill=t.accent, color=t.on_accent)
        y += t.u * 6

        y = self._status(s, x, y, maxw)
        bw = min(maxw, t.u * 44)
        acts = self.actions()
        for i, (label, icon, en) in enumerate(acts):
            W.button(t, s, pg.Rect(x, y, bw, t.btn_h), label, focused=(i == self.focus and not self.overlay),
                     enabled=en, icon=icon)
            y += t.btn_h + t.u * 1.5
        if self.install_path and g.get("state") == "installed":
            W.text(t, s, self.install_path, x, y + t.u, t.f_small, color=t.faint, maxw=maxw)

    def _hero(self, s):
        """Blurred, darkened cover across the top as a backdrop."""
        t = self.t
        small = pg.transform.smoothscale(W.cover(self.t, self.g, (315, 250)), (24, 14))
        hero = pg.transform.smoothscale(small, (t.w, int(t.h * 0.75)))
        s.blit(hero, (0, 0))
        fade = pg.Surface((t.w, int(t.h * 0.75)), pg.SRCALPHA)
        for yy in range(fade.get_height()):
            a = int(185 + 70 * (yy / fade.get_height()))
            pg.draw.line(fade, (*t.bg, min(255, a)), (0, yy), (t.w, yy))
        s.blit(fade, (0, 0))

    def _status(self, s, x, y, maxw):
        t, g = self.t, self.g
        w = min(maxw, t.u * 70)
        if not self.playable:
            if "html" in g["platforms"]:
                lines = ("Browser game", "Browser games can't be played from here yet. "
                         "Open it on itch.io in a browser.")
            else:
                lines = ("Not playable on the Deck", "This has no Linux or Windows download "
                         "(for example macOS-only, a soundtrack or a book).")
            y = W.text(t, s, lines[0], x, y, t.f_h2).bottom + t.u
            return W.wrap(t, s, lines[1], x, y, t.f_body, min(maxw, t.u * 70), color=t.dim) + t.u * 4
        if g.get("state") == "failed":
            r = pg.Rect(x, y, w, t.u * 10)
            W.panel(t, s, r, (52, 34, 34))
            pg.draw.rect(s, t.accent, (r.x, r.y, t.u // 2, r.h), border_top_left_radius=t.radius,
                         border_bottom_left_radius=t.radius)
            W.text(t, s, "Couldn't install", r.x + t.u * 2.5, r.y + t.u * 1.6, t.f_btn)
            W.text(t, s, self.fail_reason or "See the log for details.", r.x + t.u * 2.5,
                   r.y + t.u * 5.6, t.f_small, color=t.dim, maxw=w - t.u * 4)
            return r.bottom + t.u * 3
        if g.get("state") == "queued":
            y = W.text(t, s, "Queued — starts after the current download", x, y, t.f_body,
                       color=t.dim).bottom
            return y + t.u * 3
        if not self.phase:
            return y
        bar = pg.Rect(x, y + t.u * 4.5, w, max(6, t.u))
        if self.phase == "download":
            p = g.get("progress", 0)
            W.text(t, s, f"Downloading  {int(p * 100)}%", x, y, t.f_btn)
            m, sec = divmod(int(g.get("eta_s", 0)), 60)
            W.text(t, s, f"{g.get('speed_mbs', 0):.1f} MB/s · {m}:{sec:02d} left", bar.right, y + t.u * 0.6,
                   t.f_small, color=t.dim, anchor="topright")
            W.progress(t, s, bar, p)
            sub = f"{_mb(int(g['size_mb'] * p))} of {_mb(g['size_mb'])}"
        else:
            label, sub = {
                "extract": ("Extracting…", "Unpacking the download"),
                "installing": ("Installing…", "The game's installer is running silently. "
                                              "No progress % for installers."),
                "proton": ("Preparing Proton…", "First run only — about 30 s"),
            }[self.phase]
            W.text(t, s, label, x, y, t.f_btn)
            W.progress(t, s, bar, None, phase=0.35)
        W.text(t, s, sub, x, bar.bottom + t.u * 1.2, t.f_small, color=t.dim, maxw=maxw)
        return bar.bottom + t.u * 6

    def draw_overlay(self, s):
        if self.overlay[0] != "picker":
            return super().draw_overlay(s)
        t = self.t
        _, title, sub, items, focus = self.overlay
        W.shade(t, s)
        w = min(t.w - 2 * t.m, t.u * 80)
        row_h = int(t.u * 8.5)
        h = t.u * 14 + len(items) * (row_h + t.u // 2) + t.u * 3
        r = pg.Rect(0, 0, w, h)
        r.center = (int(t.cx), int((t.h - t.hint_h) / 2))
        W.panel(t, s, r, radius=t.u * 1.5)
        W.text(t, s, title, r.x + t.u * 4, r.y + t.u * 3.5, t.f_h2)
        W.text(t, s, sub, r.x + t.u * 4, r.y + t.u * 8, t.f_small, color=t.dim)
        W.rows(t, s, pg.Rect(r.x + t.u * 2, r.y + t.u * 13, r.w - t.u * 4, 0), items, focus, row_h)
