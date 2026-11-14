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


# the page's one purple button (DESIGN rule 1); Cancel never — the progress bar is the purple thing
SHOT_GROW = 1.12   # focused screenshot grows more than tiles: it's what you're looking at
MAIN_ACTIONS = ("Install", "Retry install", "Play")

class Game(Scene):
    """phase (optional): 'download' | 'extract' | 'installing' | 'proton' — what an active
    install is doing right now. fail_reason: text for a failed install."""

    def __init__(self, t, game, pos=(1, 1), focus=0, phase=None, fail_reason=None,
                 install_path=None, offline=False, card_out=False,
                 section="actions", shot=0, **kw):
        super().__init__(t, **kw)
        self.offline = offline
        self.g, self.pos, self.focus = game, pos, focus
        self.phase = phase or ("download" if game.get("state") == "downloading" else None)
        self.fail_reason = fail_reason
        self.install_path = install_path
        self.section = section     # "actions" | "shots" | "desc"
        self.shot = shot           # focused screenshot
        self.card_out = card_out   # install location is an SD card that isn't in (app sets it)

    @property
    def playable(self):
        return bool(self.g["platforms"] & {"linux", "windows"})

    def actions(self):
        """[(label, icon, enabled)]: ONE main button + the ⚙ Options button (Omri)."""
        st = self.g.get("state")
        if not self.playable:
            main = []
        elif st == "installed":
            main = [("Play", "play", True)]
        elif st == "missing":            # SD card out / files gone: nothing to run
            main = [("Play", "play", False)]
        elif st in ("downloading", "queued") or self.phase:
            return [("Cancel", None, True)]  # nothing else to do while it downloads
        elif self.card_out:              # nowhere to install to until the card is back
            main = [("Retry install" if st == "failed" else "Install", None, False)]
        elif st == "failed":
            main = [("Retry install", None, True)]
        elif self.offline:
            main = [("Install — needs internet", None, False)]
        else:
            main = [("Install", None, True)]
        return main + ([("Options", "gear", True)] if self.options() else [])

    def options(self):
        """⚙ / ☰ Options: everything that isn't the main action."""
        g, st = self.g, self.g.get("state")
        if not self.playable:
            return []
        if st == "installed":
            return ["Uninstall", "Change build", "Controls"]
        if st == "missing":
            return [] if g.get("missing") == "card" else ["Uninstall"]
        if st in ("downloading", "queued") or self.phase:
            return []
        return ["Change build"]

    def open_options(self):
        if self.options():
            self.overlay = ("menu", "Options", "", [(o, "", "") for o in self.options()], 0)

    def handle(self, act):
        n, shots = len(self.actions()), self.g.get("screens", 0)
        if self.overlay and self.overlay[0] in ("picker", "menu"):   # A is handled by the app
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
        h = [("MENU", "Options")] if self.options() else []
        h += [("L1", ""), ("R1", "Prev / next game")]
        if self.actions():
            h.append(("A", "Select"))
        return h + [("B", "Back")]

    def overlay_hints(self):
        if not self.overlay:
            return None
        if self.overlay[0] == "picker":
            return [("A", "Choose"), ("B", "Cancel")]
        if self.overlay[0] == "menu":
            return [("A", "Select"), ("B", "Close")]
        if self.overlay[0] == "viewer":
            return [("◀", ""), ("▶", "Previous / next"), ("B", "Close")]
        return super().overlay_hints()           # confirm dialog: same footer everywhere

    # --- drawing -------------------------------------------------------
    def draw_page(self, s):
        """Page is taller than the screen: hero (cover, info, actions), then About
        (screenshots + full description from the itch page). DOWN scrolls into About."""
        t = self.t
        g = self.g
        key = (id(g), g.get("details_at"), g.get("details_loading"), g.get("state"),
               g.get("controls_label"),
               g.get("cover_file"), self.section, self.shot,   # focus: buttons are live bool(self.overlay),
               self.offline, self.card_out, self.phase, self.fail_reason, self.install_path,
               round(g.get("progress", 0), 3), int(g.get("eta_s", 0)), g.get("size_mb"),
               # buttons are drawn live on top; only the screenshot strip animates inside the page
               W.frame_tick() if W.animating() and self.section == "shots" else 0,
               getattr(self, "_end", 0))
        if getattr(self, "_page_key", None) != key:   # re-layout only when something changed
            self._live_bar = None
            need = max(int(t.h * 2.6), getattr(self, "_end", 0) + t.h)
            canvas = pg.Surface((t.w, need), pg.SRCALPHA)  # transparent: gradient shows through
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
        self._sy = W.ease(getattr(self, "_sy", None), max(0, scroll), back=0)   # scroll: no bounce
        self._hero(s)                            # static: stays put while the page scrolls
        s.blit(canvas, (0, -int(self._sy[0])))
        if getattr(self, "_buttons", None):      # focus fade: only these buttons, every frame
            bx, by, items = self._buttons
            on = self.section == "actions" and not self.overlay
            W.button_row(t, s, bx, by - int(self._sy[0]), items, self.focus if on and items else None)
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

        x = cover_r.right + t.lg
        maxw = t.w - t.m - x
        y = cover_r.y - W.cap_gap(t.f_h1)       # capitals of the title = cover top edge
        y = W.text(t, s, g["title"], x, y, t.f_h1, maxw=maxw).bottom
        parts = ([f"by {g['author']}"] if g.get("author") else []) + \
                ([_mb(g["size_mb"])] if g["size_mb"] else []) + \
                [x for x in (g.get("genre"), g.get("session")) if x]   # itch's own Genre / session
        info = "  ·  ".join(parts) or " "                         # no author: skip the "by"
        r = W.text(t, s, info, x, y, t.f_body, color=t.dim)      # one info line, no loose tags
        if g.get("state") == "installed":                         # state = purple (rule 1)
            ih = int(t.f_body.get_height() * 0.42)
            cx = r.right + t.md
            W.text(t, s, "·", r.right + t.sm * 0.6, y, t.f_body, color=t.dim)
            cx += W.icon_draw(s, "check", (cx + ih * 0.45, r.centery), ih, t.accent) + t.xs
            cx = W.text(t, s, "Installed", cx, y, t.f_body, color=t.accent).right
            ctl = g.get("controls_label") or ""
            if ctl and "auto" not in ctl.lower():                 # only when not the default
                W.text(t, s, f"  ·  {ctl}", cx, y, t.f_body, color=t.dim)
        y = r.bottom + t.sm
        if g.get("short_text"):  # itch's short description; cached, so it shows offline too
            y = W.wrap(t, s, g["short_text"], x, y, t.f_body, min(maxw, t.read_w))
        y += t.md

        if self.actions():              # buttons sit on the cover's bottom edge unless pushed down
            y = max(y, cover_r.bottom - t.btn_h)
        acts = self.actions()                    # one row; LEFT/RIGHT moves focus
        on = self.section == "actions" and not self.overlay
        items = [(lb, ic, en, lb in MAIN_ACTIONS) for lb, ic, en in acts]
        rects = W.button_row(t, s, x, y, items, self.focus if on and acts else None)
        self._buttons = (x, y, items)            # redrawn live over the cached page (cheap focus)
        if self.phase and self.playable and rects:      # progress sits next to Cancel
            px = rects[-1].right + t.lg
            self._progress_inline(s, px, y, min(x + maxw - px, t.read_w))
        if acts:
            y += t.btn_h + t.sm
        msg = self.message()
        if msg:                                  # the one place for messages: under the buttons
            if not acts:                         # no buttons (not playable): box takes their place
                y = max(y, cover_r.bottom - t.btn_h - t.sm)
            kind, title, line = msg
            y = W.notice(t, s, x, y + (t.xs if acts else 0), min(maxw, t.read_w), title, line,
                         kind=kind).bottom + t.sm
        return max(cover_r.bottom, y) + t.lg

    def _about(self, s, y):
        """Screenshots strip + description, read from the game's public itch page and cached."""
        t, g = self.t, self.g
        n = g.get("screens", 0)
        if n:
            y = W.text(t, s, "Screenshots", t.m, y, t.f_h2).bottom + t.sm
            th = int(t.u * 19)                       # same height, each at its own shape
            ws = [int(th * W.shot_aspect(g, i)) for i in range(n)]
            avail = t.w - 2 * t.m
            first = 0
            if self.section == "shots":              # scroll so the focused one fits
                while sum(ws[first:self.shot + 1]) + t.gap * (self.shot - first) > avail:
                    first += 1
            pad = int(th * (SHOT_GROW - 1) / 2)      # room for the focused one to grow
            y += pad
            xx, last = t.m, None
            for i in range(first, n):
                if xx + ws[i] > t.m + avail:
                    break
                r = pg.Rect(xx, y, ws[i], th)
                last, xx = (i, r), xx + ws[i] + t.gap
                foc = self.section == "shots" and i == self.shot and not self.overlay
                k = W.anim(("shot", g["id"], i), 1.0 if foc else 0.0)
                grow = (SHOT_GROW - 1) * k
                if grow:
                    r = r.inflate(r.w * grow, th * grow)
                s.blit(W.rounded(W.screenshot(t, g, i, r.size), t.radius), r)
                if k > 0.5:
                    W.focus_ring(t, s, r)
            if last and last[0] < n - 1:  # more to the right: count on the last visible shot
                W.tag(t, s, f"+{n - 1 - last[0]} more", last[1].right - t.xs,
                      last[1].bottom - t.xs, kind="dark", anchor="bottomright")
            y += th + pad + t.lg
        desc_y = y
        paras = g.get("description") or []
        if paras:
            y = W.text(t, s, "About this game", t.m, y, t.f_h2).bottom + t.sm
            w = min(t.w - 2 * t.m, t.read_w * 1.4)   # long reading: ~95 chars per line
            for para in paras:
                y = W.wrap(t, s, para, t.m, y, t.f_body, w, color=t.text_c) + t.md
            y = W.text(t, s, "From the game's itch.io page", t.m, y, t.f_small, color=t.dim).bottom
        elif not n:
            msg = ("This game's itch.io page no longer exists." if g.get("page_missing") else
                   "Loading details from itch.io…" if g.get("details_loading") or not self.offline
                   and not g.get("details_at") else
                   "More details load the next time you're online." if self.offline else
                   "This game's itch page has no description.")
            y = W.text(t, s, msg, t.m, y, t.f_body, color=t.dim).bottom
        comments_y = y + t.lg
        self._end = self._comments(s, comments_y)
        return desc_y, comments_y

    def _comments(self, s, y):
        """Newest comments from the itch page (cached with it). Long ones cut to 3 lines."""
        t, g = self.t, self.g
        cs = g.get("comments")
        if cs is None:
            return y
        total = g.get("comment_count", len(cs))
        y = W.text(t, s, f"Comments  ·  {total}", t.m, y, t.f_h2).bottom + t.sm
        if not cs:
            return W.text(t, s, "No comments yet.", t.m, y, t.f_body, color=t.dim).bottom
        w = min(t.w - 2 * t.m, t.read_w * 1.4)
        for c in cs:
            y = self._comment(s, c, t.m, y, w)
            shown = c.get("reply_list", [])[:2]          # up to 2 replies, indented
            ind = t.m + t.lg
            for rp in shown:
                y = self._comment(s, rp, ind, y - t.xs, w - t.lg, reply=True)
            more = c.get("replies", 0) - len(shown)
            if more > 0:
                y = W.text(t, s, f"+{more} more repl{'y' if more == 1 else 'ies'}", ind + t.sm,
                           y - t.sm, t.f_small, color=t.dim).bottom + t.md
        if total > len(cs):
            y = W.text(t, s, f"Showing the newest {len(cs)} of {total}", t.m, y, t.f_small,
                       color=t.dim).bottom
        return y

    def _hero(self, s):
        """Big art across the top: the first screenshot (sharp, darkened), or the blurred cover
        when there are none; fades out into the page gradient."""
        t, g = self.t, self.g
        h = t.h                                 # whole screen: About/Comments sit on it too
        shot = bool(g.get("screens"))
        key = (g["id"], g.get("cover_file"), tuple(g.get("shot_files") or ()), shot, t.w, h)
        if getattr(self, "_hero_key", None) == key:
            return s.blit(self._hero_img, (0, 0))
        if shot:                         # softened: colours + composition, never competes with text
            sharp = W.screenshot(t, g, 0, (t.w, h))
            soft = pg.transform.smoothscale(sharp, (max(1, t.w // 10), max(1, h // 10)))
            hero = pg.transform.smoothscale(soft, (t.w, h))
        else:
            small = pg.transform.smoothscale(W.cover(self.t, g, (315, 250)), (24, 14))
            hero = pg.transform.smoothscale(small, (t.w, h))
        dark = pg.Surface((t.w, h), pg.SRCALPHA)
        dark.fill((0, 0, 0, 150))      # keeps text readable, even on bright art
        hero.blit(dark, (0, 0))
        out = pg.Surface((t.w, h), pg.SRCALPHA)
        out.blit(hero, (0, 0))
        mask = pg.Surface((t.w, h), pg.SRCALPHA)
        for yy in range(h):
            a = int(255 - (255 - 90) * (yy / h) ** 0.8) if shot else int(200 * (1 - yy / h) ** 1.4)
            pg.draw.line(mask, (255, 255, 255, a), (0, yy), (t.w, yy))
        out.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
        self._hero_key, self._hero_img = key, out
        s.blit(out, (0, 0))

    def message(self):
        """What to tell the player about this game: (kind, title, line) or None.
        Always drawn as ONE box under the buttons (Omri: consistent). Red only for errors."""
        g = self.g
        if not self.playable:
            if "html" in g["platforms"]:
                return ("info", "Browser game", "Open it on itch.io in a browser.")
            return ("info", "Not playable on the Deck", "It has no Linux or Windows download.")
        st = g.get("state")
        if self.card_out and st in (None, "failed"):
            return ("info", "SD card missing", "Insert it to install this game, or change "
                    "Install location in Settings.")
        if st == "failed":
            return ("error", "Couldn't install", self.fail_reason or "See the log for details.")
        if st == "missing" and g.get("missing") == "card":
            return ("info", "SD card missing", "Insert the card and the game comes back.")
        if st == "missing":
            return ("info", "Game files missing", "Uninstall it, then install it again.")
        if st == "queued":
            return ("info", "Queued", "Starts after the current download.")
        return None

    def _progress_inline(self, s, x, y, w):
        """Progress next to Cancel, inside the button row's height (no extra lines under it)."""
        t, g = self.t, self.g
        bar_h = max(6, t.u)
        lh = t.f_btn.get_linesize()
        top = y + (t.btn_h - (lh + t.sm + bar_h)) // 2
        base = top + t.f_btn.get_ascent()          # label and details share a baseline
        bar = pg.Rect(x, top + lh + t.sm, w, bar_h)
        if self.phase == "download":
            p = g.get("progress", 0)
            label = f"Downloading  {int(p * 100)}%"
            info = (f"{_mb(int(g['size_mb'] * p))} of {_mb(g['size_mb'])}  ·  "
                    f"{g.get('speed_mbs', 0):.1f} MB/s")
            W.progress(t, s, bar, p)
        else:
            label, info = {"extract": "Extracting…", "installing": "Installing…",
                           "proton": "Preparing Proton…", "umu": "Getting umu-launcher…"
                           }[self.phase], ""      # no explanations: the label is enough
            W.progress(t, s, bar, 0)          # track only; draw_page animates the segment live
            self._live_bar = bar
        lr = W.text(t, s, label, x, base, t.f_btn, anchor="baseleft")
        room = max(0, bar.right - lr.right - t.md)
        if t.f_small.size(info)[0] > room:          # too tight (Deck): drop the last detail
            info = info.rsplit("  ·  ", 1)[0]
        W.text(t, s, info, bar.right, base, t.f_small, color=t.dim, anchor="baseright", maxw=room)

    def draw_overlay(self, s):
        if self.overlay[0] == "viewer":
            return self._viewer(s)
        if self.overlay[0] not in ("picker", "menu"):
            return super().draw_overlay(s)
        W.menu(self.t, s, *self.overlay[1:])

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
        r = W.text(t, s, c["author"], x + t.sm, y, f_name)
        wx = r.right + t.sm
        if c.get("dev"):
            wx = W.tag(t, s, "Developer", wx, r.centery, kind="accent",
                       anchor="midleft").right + t.sm
        W.text(t, s, c["when"], wx, r.centery, t.f_small, color=t.dim, anchor="midleft")
        yy = W.wrap(t, s, c["text"], x + t.sm, r.bottom,
                    t.f_small if reply else t.f_body, w - t.sm,
                    color=t.dim if reply else t.text_c, max_lines=2 if reply else 3)
        col = t.accent if c.get("dev") else (t.panel_hi if reply else t.line)
        pg.draw.line(s, col, (x, y), (x, yy), max(2, t.u // 4))
        return yy + t.md
