"""P3 Game page: big cover, info, state, actions. Picker (O1) and Confirm (O2) overlay it."""
import pygame as pg

from ...input import UP, DOWN, LEFT, RIGHT, A, B
from .. import widgets as W
from .base import Scene

PLATFORM = {"linux": "Linux", "windows": "Windows", "html": "Browser",
            "mac": "macOS only", "android": "Android only", "soundtrack": "Soundtrack",
            "book": "Book", "other": "No download"}


def _mb(mb):
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


class Game(Scene):
    """phase (optional): 'download' | 'extract' | 'installing' | 'proton' — what an active
    install is doing right now. fail_reason: text for a failed install."""

    def __init__(self, t, game, pos=(1, 1), focus=0, phase=None, fail_reason=None,
                 install_path=None, offline=False,
                 section="actions", shot=0, **kw):
        super().__init__(t, **kw)
        self.offline = offline
        self.g, self.pos, self.focus = game, pos, focus
        self.phase = phase or ("download" if game.get("state") == "downloading" else None)
        self.fail_reason = fail_reason
        self.install_path = install_path
        self.section = section     # "actions" | "shots" | "desc"
        self.shot = shot           # focused screenshot

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
            return [("Cancel", None, True)]
        if st == "failed":
            return [("Retry install", None, True), ("Change build", None, True)]
        if self.offline:
            return [("Install — needs internet", None, False)]
        return [("Install", None, True), ("Change build", None, True)]

    def handle(self, act):
        n, shots = len(self.actions()), self.g.get("screens", 0)
        if self.overlay and self.overlay[0] == "picker":   # A (choose) is handled by the app
            kind, title, sub, items, focus = self.overlay
            if act in (UP, DOWN) and items:
                focus = max(0, min(len(items) - 1, focus + (1 if act == DOWN else -1)))
                self.overlay = (kind, title, sub, items, focus)
            elif act == B:
                self.overlay = None
            return
        if self.overlay and self.overlay[0] == "viewer":
            if act in (LEFT, RIGHT):
                self.shot = (self.shot + (1 if act == RIGHT else -1)) % shots
                self.overlay = ("viewer",)
            elif act == B:
                self.overlay = None
            return
        order = ["actions"] + (["shots"] if shots else []) + ["desc"] + \
            (["comments"] if self.g.get("comments") else [])
        if act in (UP, DOWN):
            off, step = getattr(self, "off", 0), int(self.t.h * 0.18)
            if act == DOWN and off < getattr(self, "_max_off", 0):
                self.off = off + step            # scroll within a long description/comments
                return
            if act == UP and off > 0:
                self.off = max(0, off - step)
                return
            i = order.index(self.section) + (1 if act == DOWN else -1)
            new = order[max(0, min(len(order) - 1, i))]
            if new != self.section:
                self.section, self.off = new, 0
        elif act in (LEFT, RIGHT):
            d = 1 if act == RIGHT else -1
            if self.section == "actions" and n:
                self.focus = max(0, min(n - 1, self.focus + d))
            elif self.section == "shots":
                self.shot = max(0, min(shots - 1, self.shot + d))
        elif act == A and self.section == "shots":
            self.overlay = ("viewer",)

    def hints(self):
        if self.section == "shots":
            return [("A", "View full screen"), ("B", "Back")]
        if self.section in ("desc", "comments"):
            return [("B", "Back")]
        # Steam order: extra actions first, then A, with B always last (far right)
        h = [("L1", ""), ("R1", "Prev / next game")]
        if self.actions():
            h.append(("A", "Select"))
        return h + [("B", "Back")]

    def overlay_hints(self):
        if not self.overlay:
            return None
        if self.overlay[0] == "picker":
            return [("A", "Choose"), ("B", "Cancel")]
        if self.overlay[0] == "viewer":
            return [("◀", ""), ("▶", "Previous / next"), ("B", "Close")]
        return [("A", "Uninstall"), ("B", "Cancel")]

    # --- drawing -------------------------------------------------------
    def draw_page(self, s):
        """Page is taller than the screen: hero (cover, info, actions), then About
        (screenshots + full description from the itch page). DOWN scrolls into About."""
        t = self.t
        g = self.g
        key = (id(g), g.get("details_at"), g.get("details_loading"), g.get("state"),
               g.get("cover_file"), self.section, self.focus, self.shot, bool(self.overlay),
               self.offline, self.phase, self.fail_reason, self.install_path,
               round(g.get("progress", 0), 3), int(g.get("eta_s", 0)), g.get("size_mb"),
               getattr(self, "_end", 0))
        if getattr(self, "_page_key", None) != key:   # re-layout only when something changed
            self._live_bar = None
            need = max(int(t.h * 2.6), getattr(self, "_end", 0) + t.h)
            canvas = pg.Surface((t.w, need), pg.SRCALPHA)  # transparent: gradient shows through
            self._hero(canvas)
            about_y = self._top(canvas)
            desc_y, comments_y = self._about(canvas, about_y)
            self._page = (canvas, about_y, desc_y, comments_y)
            self._page_key = key[:-1] + (getattr(self, "_end", 0),)
        canvas, about_y, desc_y, comments_y = self._page
        view = t.h - t.hint_h - 2 * t.m          # long sections scroll inside themselves
        self._max_off = {"desc": max(0, comments_y - desc_y - view),
                         "comments": max(0, getattr(self, "_end", 0) - comments_y - view)
                         }.get(self.section, 0)
        self.off = min(getattr(self, "off", 0), self._max_off)
        scroll = {"actions": 0, "shots": about_y - t.m, "desc": desc_y - t.m + self.off,
                  "comments": comments_y - t.m + self.off}[self.section]
        self._sy = W.ease(getattr(self, "_sy", None), max(0, scroll), speed=14)
        s.blit(canvas, (0, -int(self._sy[0])))
        if self._live_bar:                       # indeterminate bar: cheap per-frame overlay
            W.progress(t, s, self._live_bar.move(0, -int(self._sy[0])), None, phase=0.35)

    def _top(self, s):
        t, g = self.t, self.g
        cw = int((t.w - 2 * t.m) * 0.34)
        cover_r = pg.Rect(t.m, t.m, cw, int(cw * t.cover_ratio))
        img = W.rounded(W.cover(t, g, cover_r.size), t.radius)
        if not self.playable:
            o = pg.Surface(cover_r.size, pg.SRCALPHA)
            pg.draw.rect(o, (0, 0, 0, t.dimmed_a), o.get_rect(), border_radius=t.radius)
            img.blit(o, (0, 0))
        s.blit(img, cover_r)

        x = cover_r.right + t.u * 5
        maxw = t.w - t.m - x
        y = cover_r.y - W.cap_gap(t.f_small)    # capitals of the first line = cover top edge
        W.text(t, s, f"itch  ·  {self.pos[0]} of {self.pos[1]}", x, y, t.f_small, color=t.dim)
        y += t.u * 3.4
        y = W.text(t, s, g["title"], x, y, t.f_h1, maxw=maxw).bottom
        y = W.text(t, s, f"by {g['author']}", x, y, t.f_body, color=t.dim).bottom + t.u * 1.5
        if g.get("short_text"):  # itch's short description; cached, so it shows offline too
            y = W.wrap(t, s, g["short_text"], x, y, t.f_body, min(maxw, t.u * 80)) + t.u * 1.5

        px = x
        if g["size_mb"]:
            px = W.tag(t, s, _mb(g["size_mb"]), px, y).right + t.u
        if g.get("state") == "installed":
            W.tag(t, s, "✓ Installed", px, y, kind="accent")
        y += t.u * 5

        y = self._status(s, x, y, maxw)
        if self.actions():              # buttons sit on the cover's bottom edge unless pushed down
            y = max(y, cover_r.bottom - t.btn_h)
        bx = x
        for i, (label, icon, en) in enumerate(self.actions()):  # one row; LEFT/RIGHT moves
            bw = W.button_w(t, label, icon)
            W.button(t, s, pg.Rect(bx, y, bw, t.btn_h), label, enabled=en, icon=icon,
                     play=(label == "Play"),
                     focused=(self.section == "actions" and i == self.focus and not self.overlay))
            bx += bw + t.u * 1.5
        if self.actions():
            y += t.btn_h + t.u * 1.5
        if self.install_path and g.get("state") == "installed":
            y = W.text(t, s, self.install_path, x, y, t.f_small, color=t.dim, maxw=maxw).bottom
        return max(cover_r.bottom, y) + t.u * 5

    def _about(self, s, y):
        """Screenshots strip + description, read from the game's public itch page and cached."""
        t, g = self.t, self.g
        n = g.get("screens", 0)
        if n:
            y = W.text(t, s, "Screenshots", t.m, y, t.f_h2).bottom + t.u * 2
            th = int(t.u * 17)
            tw = int(th * 16 / 9)
            fits = max(1, int((t.w - 2 * t.m + t.gap) // (tw + t.gap)))
            first = max(0, min(self.shot - fits + 1, n - fits)) if self.section == "shots" else 0
            for k, i in enumerate(range(first, min(n, first + fits))):
                r = pg.Rect(t.m + k * (tw + t.gap), y, tw, th)
                foc = self.section == "shots" and i == self.shot and not self.overlay
                if foc:
                    r = r.inflate(tw * (t.focus_scale - 1), th * (t.focus_scale - 1))
                s.blit(W.rounded(W.screenshot(t, g, i, r.size), t.radius), r)
                if foc:
                    W.focus_ring(t, s, r)
            if first + fits < n:  # more to the right: count on the last visible shot
                last = pg.Rect(t.m + (fits - 1) * (tw + t.gap), y, tw, th)
                W.tag(t, s, f"+{n - first - fits} more", last.right - t.u, last.bottom - t.u,
                      kind="dark", anchor="bottomright")
            y += th + t.u * 5
        desc_y = y
        paras = g.get("description") or []
        if paras:
            y = W.text(t, s, "About this game", t.m, y, t.f_h2).bottom + t.u * 2
            w = min(t.w - 2 * t.m, t.u * 125)
            for para in paras:
                y = W.wrap(t, s, para, t.m, y, t.f_body, w, color=(205, 205, 205)) + t.f_body.get_linesize() * 0.6
            y = W.text(t, s, "From the game's itch.io page", t.m, y + t.u, t.f_small, color=t.dim).bottom
        elif not n:
            msg = ("This game's itch.io page no longer exists." if g.get("page_missing") else
                   "Loading details from itch.io…" if g.get("details_loading") or not self.offline
                   and not g.get("details_at") else
                   "More details load the next time you're online." if self.offline else
                   "This game's itch page has no description.")
            y = W.text(t, s, msg, t.m, y, t.f_body, color=t.dim).bottom
        comments_y = y + t.u * 5
        self._end = self._comments(s, comments_y)
        return desc_y, comments_y

    def _comments(self, s, y):
        """Newest comments from the itch page (cached with it). Long ones cut to 3 lines."""
        t, g = self.t, self.g
        cs = g.get("comments")
        if cs is None:
            return y
        total = g.get("comment_count", len(cs))
        y = W.text(t, s, f"Comments  ·  {total}", t.m, y, t.f_h2).bottom + t.u * 2
        if not cs:
            return W.text(t, s, "No comments yet.", t.m, y, t.f_body, color=t.dim).bottom
        w = min(t.w - 2 * t.m, t.u * 125)
        for c in cs:
            y = self._comment(s, c, t.m, y, w)
            shown = c.get("reply_list", [])[:2]          # up to 2 replies, indented
            ind = t.m + t.u * 5
            for rp in shown:
                y = self._comment(s, rp, ind, y - t.u, w - t.u * 5, reply=True)
            more = c.get("replies", 0) - len(shown)
            if more > 0:
                y = W.text(t, s, f"+{more} more repl{'y' if more == 1 else 'ies'}", ind + t.u * 2.5,
                           y - t.u * 1.5, t.f_small, color=t.dim).bottom + t.u * 2.5
        if total > len(cs):
            y = W.text(t, s, f"Showing the newest {len(cs)} of {total}", t.m, y, t.f_small,
                       color=t.dim).bottom
        return y

    def _hero(self, s):
        """Blurred, darkened cover across the top, fading out into the page gradient."""
        t = self.t
        h = int(t.h * 0.75)
        key = (self.g["id"], self.g.get("cover_file"), t.w, h)
        if getattr(self, "_hero_key", None) == key:
            return s.blit(self._hero_img, (0, 0))
        small = pg.transform.smoothscale(W.cover(self.t, self.g, (315, 250)), (24, 14))
        hero = pg.transform.smoothscale(small, (t.w, h))
        dark = pg.Surface((t.w, h), pg.SRCALPHA)
        dark.fill((0, 0, 0, 150))
        hero.blit(dark, (0, 0))
        out = pg.Surface((t.w, h), pg.SRCALPHA)
        out.blit(hero, (0, 0))
        mask = pg.Surface((t.w, h), pg.SRCALPHA)
        for yy in range(h):
            a = int(200 * (1 - yy / h) ** 1.4)
            pg.draw.line(mask, (255, 255, 255, a), (0, yy), (t.w, yy))
        out.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
        self._hero_key, self._hero_img = key, out
        s.blit(out, (0, 0))

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
            W.panel(t, s, r, t.error_bg)
            pg.draw.rect(s, t.error, (r.x, r.y, t.u // 2, r.h), border_top_left_radius=t.radius,
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
                "umu": ("Getting umu-launcher…", "One-time download for Windows games"),
            }[self.phase]
            W.text(t, s, label, x, y, t.f_btn)
            W.progress(t, s, bar, 0)          # track only; draw_page animates the segment live
            self._live_bar = bar
        W.text(t, s, sub, x, bar.bottom + t.u * 1.2, t.f_small, color=t.dim, maxw=maxw)
        return bar.bottom + t.u * 6

    def draw_overlay(self, s):
        if self.overlay[0] == "viewer":
            return self._viewer(s)
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
        W.panel(t, s, r)
        W.text(t, s, title, r.x + t.u * 4, r.y + t.u * 3.5, t.f_h2)
        W.text(t, s, sub, r.x + t.u * 4, r.y + t.u * 8, t.f_small, color=t.dim)
        W.rows(t, s, pg.Rect(r.x + t.u * 2, r.y + t.u * 13, r.w - t.u * 4, 0), items, focus, row_h)

    def _viewer(self, s):
        """Full-screen screenshot viewer."""
        t, n = self.t, self.g.get("screens", 0)
        s.fill((0, 0, 0))
        avail = pg.Rect(t.m, t.m, t.w - 2 * t.m, t.h - t.hint_h - 2 * t.m)
        w = min(avail.w, int(avail.h * 16 / 9))
        r = pg.Rect(0, 0, w, int(w * 9 / 16))
        r.center = avail.center
        if self.shot < len(self.g.get("shot_files") or []):
            r = avail                   # real image: fit the whole thing, any aspect (letterbox)
        s.blit(W.screenshot(t, self.g, self.shot, r.size, contain=True), r)
        W.text(t, s, f"{self.shot + 1} / {n}", t.w - t.m, t.m * 0.5, t.f_small, color=t.dim,
               anchor="midright")
        W.text(t, s, self.g["title"], t.m, t.m * 0.5, t.f_small, color=t.dim, anchor="midleft")

    def _comment(self, s, c, x, y, w, reply=False):
        """One comment (or an indented reply). Returns the y for the next one."""
        t = self.t
        f_name = t.f_small if reply else t.f_btn
        r = W.text(t, s, c["author"], x + t.u * 2.5, y, f_name)
        wx = r.right + t.u * 1.5
        if c.get("dev"):
            wx = W.tag(t, s, "Developer", wx, r.centery, kind="accent",
                       anchor="midleft").right + t.u * 1.5
        W.text(t, s, c["when"], wx, r.centery, t.f_small, color=t.dim, anchor="midleft")
        yy = W.wrap(t, s, c["text"], x + t.u * 2.5, r.bottom + t.u * 0.3,
                    t.f_small if reply else t.f_body, w - t.u * 2.5,
                    color=(190, 190, 190) if reply else (205, 205, 205), max_lines=2 if reply else 3)
        col = t.accent if c.get("dev") else (t.panel_hi if reply else t.line)
        pg.draw.line(s, col, (x, y), (x, yy), max(2, t.u // 4))
        return yy + t.u * 2.5
