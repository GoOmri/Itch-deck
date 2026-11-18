"""P3 Game page: big cover, info, state, actions. Picker (O1) and Confirm (O2) overlay it."""
import pygame as pg

from ...input import UP, DOWN, LEFT, RIGHT, A, B
from .. import widgets as W
from ... import hltb
from .base import Scene


def _mb(mb):
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


# the page's one purple button (DESIGN rule 1); Cancel never — the progress bar is the purple thing
SHOT_GROW = 1.12   # focused screenshot grows more than tiles: it's what you're looking at
MAIN_ACTIONS = ("Install", "Retry install", "Play")

def _now():
    import time
    return time.monotonic()


CONTROL_WORDS = {"mouse": "Trackpad as mouse", "keys": "Buttons as keyboard"}   # pad: nothing to say


class Game(Scene):
    def footer_status(self):
        act = self.activity                     # this game's own download shows by its button
        return (None if act and self.g.get("title", "") in act else act), self.notice

    """phase (optional): 'download' | 'extract' | 'installing' | 'proton' — what an active
    install is doing right now. fail_reason: text for a failed install."""

    def __init__(self, t, game, pos=(1, 1), focus=0, phase=None, fail_reason=None,
                 install_path=None, offline=False, card_out=False, behind=False,
                 section="actions", shot=0, **kw):
        super().__init__(t, **kw)
        self.offline = offline
        self.g, self.pos, self.focus = game, pos, focus
        self.phase = phase or ("download" if game.get("state") == "downloading" else
                               "queued" if game.get("state") == "queued" else None)
        self.behind = behind       # queued behind another game's download (app sets it)
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
        elif st == "installed" and self.g.get("update"):   # Play · Update · ⚙ (Omri)
            main = [("Play", "play", True), ("Update", None, True)]
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
        """Options + the Add to / Remove from Steam row (set by the app: steam_ok, on_steam)."""
        if self.g.get("hidden"):
            return ["Show in SCRiTCH"]                   # a hidden game: the way back
        rows = self._options()
        if rows and self.g.get("state") == "installed" and self.g.get("steam_ok"):
            rows = rows + ["Remove from Steam" if self.g.get("on_steam") else "Add to Steam"]
        if self.g.get("state") in (None, "failed") and not self.phase:
            rows = rows + ["Hide from SCRiTCH"]           # not installed: hiding it loses nothing
        return rows

    def _options(self):
        """⚙ / ☰ Options: everything that isn't the main action."""
        g, st = self.g, self.g.get("state")
        if not self.playable:
            return []
        if g.get("store") == "dos":                    # your own DOS game: files are never deleted
            if st == "installed":
                return ["Remove from library", "Controls"] + (
                    ["Program to run"] if g.get("programs", 1) > 1 else [])
            return ["Remove from library"] if st == "missing" else []
        epic = g.get("store") == "epic" or (       # one build: no Change build. GOG: only when it
            g.get("store") == "gog" and not {"linux", "windows"} <= set(g["platforms"]))  # has both
        if st == "installed":
            return (["Uninstall", "Controls"] if epic else
                    ["Uninstall", "Change build", "Controls"]) + ["Saves"] + \
                ([f"Move to {g['move_to']}"] if g.get("move_to") else [])
        if st == "missing":
            return [] if g.get("missing") == "card" else ["Uninstall"]
        if st in ("downloading", "queued") or self.phase:
            return []
        return [] if epic else ["Change build"]

    RARE = ("Change build", "Saves", "Program to run", "Add to Steam", "Remove from Steam")

    def menu_split(self):
        """(rows shown in Options, rows behind "More"). A long list (an installed itch game has six) keeps
        the everyday ones and tucks the rest under one "More" row (Omri, Deck test 17 Nov)."""
        rows = self.options()
        rare = [r for r in rows if r in self.RARE or r.startswith("Move to ")]
        if len(rows) <= 4 or len(rare) < 2:
            return rows, []
        return [r for r in rows if r not in rare] + ["More"], rare

    def open_options(self, focus=0, more=False):
        """☰ / ⚙ Options. Controls shows its setting (◀ ▶ change it, like Sort & filter).
        more=True: the list behind the "More" row."""
        if self.options():
            head, rare = self.menu_split()
            labels, title = (rare, "More") if more and rare else (head, "Options")
            rows = [(o, self.g.get("controls_value", "") if o == "Controls" else "", "") for o in labels]
            self.overlay = ("menu", title, "", rows, max(0, min(focus, len(rows) - 1)))

    def handle(self, act):
        n, shots = len(self.actions()), self.g.get("screens", 0)
        if self.overlay and self.overlay[0] in ("picker", "menu"):   # A is handled by the app
            kind, title, sub, items, focus = self.overlay
            if act in (UP, DOWN) and items:
                focus = max(0, min(len(items) - 1, focus + (1 if act == DOWN else -1)))
                self.overlay = (kind, title, sub, items, focus)
            elif act == B:
                if kind == "menu" and title == "More":               # back to Options, on its More row
                    self.open_options(len(self.menu_split()[0]) - 1)
                else:
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
                if self.section == "shots":      # the focused screenshot shrinks back: keep
                    import time                  # redrawing the page until it has (v0.9.3)
                    self._shots_settle = time.monotonic() + 0.6
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
            items, f = self.overlay[3], self.overlay[4]
            if items and items[f][0] == "Controls":
                return [("◀", ""), ("▶", "Change"), ("B", "Close")]
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
               g.get("controls_label"), g.get("controls_mode"), str(g.get("ttb")), str(g.get("update")),
               g.get("cover_file"), self.section, self.shot,   # focus: buttons are live bool(self.overlay),
               self.offline, self.card_out, self.phase, self.behind, self.fail_reason, self.install_path,
               round(g.get("progress", 0), 3), int(g.get("eta_s", 0)), g.get("size_mb"),
               (getattr(self, "free_mb", None) or 0) // 1000,   # GB steps: no re-layout per MB
               # buttons are drawn live on top; only the screenshot strip animates inside the page
               W.frame_tick() if W.animating() and (self.section == "shots" or
                                                    _now() < getattr(self, "_shots_settle", 0)) else 0,
               getattr(self, "_end", 0))
        if getattr(self, "_page_key", None) != key:   # re-layout only when something changed
            self._live_bar = self._live_fill = None
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
        if getattr(self, "_live_fill", None):    # download %: eases toward each new value
            bar, p = self._live_fill
            if p < getattr(self, "_fill_last", 0):  # a new download / retry: start from there
                self._fill = None
            self._fill_last = p
            self._fill = W.ease(getattr(self, "_fill", None), p * 1000, W.FILL_MS, 0)
            W.progress(t, s, bar.move(0, -int(self._sy[0])), self._fill[0] / 1000)
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
        y = W.wrap(t, s, g["title"], x, y, t.f_h1, maxw, max_lines=2)    # long titles: 2 lines
        if g.get("author"):                                       # who made it: one quiet line
            y = W.text(t, s, f"by {g['author']}", x, y, t.f_body, color=t.dim, maxw=maxw).bottom
        y += t.sm
        # the facts: icon + value pairs, scannable at a glance (state first, purple = yours)
        items = [("check", "Installed", t.accent)] if g.get("state") == "installed" else []
        if g["size_mb"]:
            size, col = _mb(g["size_mb"]), None
            free = getattr(self, "free_mb", None)
            if free is not None and self.playable and \
                    g.get("state") not in ("installed", "downloading", "queued", "missing"):
                size += f"  ·  {_mb(free)} free"                # space, before installing
                col = t.error if g["size_mb"] > free else None
            items.append(("disk", size, col))
        if g.get("genre"):
            items.append(("tag", g["genre"], None))
        ttb = g.get("ttb") or {}
        hours = ttb.get("main") or ttb.get("done")                # main story; completionist cut
        if hours:
            items.append(("clock", f"{hltb.fmt(hours)} to beat", None))
        mode = g.get("controls_mode") if self.playable else None
        if mode in CONTROL_WORDS:                                 # what SCRiTCH converts
            items.append(("mouse" if mode == "mouse" else "keys", CONTROL_WORDS[mode], None))
        if items:
            y = W.facts(t, s, x, y, items, maxw) + t.md
        self._tag_cut = False
        if g.get("short_text"):  # itch's short description; cached, so it shows offline too
            tw = min(maxw, t.read_w)                  # 2 lines max; a longer one opens About
            self._tag_cut = len(W.wrap_lines(t.f_body, g["short_text"], tw)) > 2
            y = W.wrap(t, s, g["short_text"], x, y, t.f_body, tw, max_lines=2)
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
            kind, title, line = msg
            if not acts:                         # no buttons: the box takes their place, its
                y = max(y, cover_r.bottom - W.notice_h(t, line))     # bottom on the cover's
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
        paras = ([g["short_text"]] if getattr(self, "_tag_cut", False) else []) + \
            (g.get("description") or [])              # a cut tagline reads in full here
        if paras:
            y = W.text(t, s, "About this game", t.m, y, t.f_h2).bottom + t.sm
            w = min(t.w - 2 * t.m, t.read_w * 1.4)   # long reading: ~95 chars per line
            for para in paras:
                y = W.wrap(t, s, para, t.m, y, t.f_body, w, color=t.text_c) + t.md
            src = {"Epic": "From Epic Games", "Steam": "From Steam", "GOG": "From GOG"}.get(
                g.get("details_from"), "From the game's itch.io page")
            if g.get("details_from") == "Epic" and n:
                src += " · screenshots from Steam"
            y = W.text(t, s, src, t.m, y, t.f_small, color=t.dim).bottom
        elif not n and g.get("store") in ("epic", "gog"):
            msg = ("Loading details…" if g.get("details_loading") or not self.offline
                   and not g.get("details_at") else
                   "More details load the next time you're online." if self.offline else
                   "No more details for this game.")
            y = W.text(t, s, msg, t.m, y, t.f_body, color=t.dim).bottom
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
        if not self.playable:          # few plain words (Omri: casual players, no tech terms)
            if "html" in g["platforms"]:
                return ("info", "Browser game", "Play it on itch.io.")
            return ("info", "Can't be played here", None)
        st = g.get("state")
        if self.card_out and st in (None, "failed"):
            return ("info", "SD card missing", "Insert it to install.")
        if st == "failed":
            return ("error", "Couldn't install", self.fail_reason)
        if st == "missing" and g.get("missing") == "card":
            return ("info", "SD card missing", "Insert it to play.")
        if st == "missing":
            return ("info", "Game files missing", "Reinstall to play.")
        return None

    def _progress_inline(self, s, x, y, w):
        """Progress next to Cancel, inside the button row's height (no extra lines under it)."""
        t, g = self.t, self.g
        bar_h = max(6, t.u)
        lh = t.f_btn.get_linesize()
        top = y + (t.btn_h - (lh + t.sm + bar_h)) // 2
        base = top + t.f_btn.get_ascent()          # label and details share a baseline
        bar = pg.Rect(x, top + lh + t.sm, w, bar_h)
        if self.phase == "ge":                     # one-time GE-Proton download before the game
            p = g.get("progress", 0)
            label = f"Getting GE-Proton  {int(p * 100)}%"
            info = f"One time only  ·  {g.get('speed_mbs', 0):.1f} MB/s"
            W.progress(t, s, bar, 0)
            self._live_fill = (bar, p)            # fill glides live (draw_page), never jumps
        elif self.phase == "move":
            p = g.get("progress", 0)
            label = f"Moving to {g.get('move_to') or 'the other drive'}  {int(p * 100)}%"
            info = ""                             # the label is enough (rule 10)
            W.progress(t, s, bar, 0)
            self._live_fill = (bar, p)
        elif self.phase == "download":
            p = g.get("progress", 0)
            label = f"Downloading  {int(p * 100)}%"
            info = (f"{_mb(int(g['size_mb'] * p))} of {_mb(g['size_mb'])}  ·  " if g.get("size_mb")
                    else "") + f"{g.get('speed_mbs', 0):.1f} MB/s"   # size unknown: speed only
            W.progress(t, s, bar, 0)
            self._live_fill = (bar, p)
        else:
            label, info = {"extract": "Extracting…", "installing": "Installing…",
                           "proton": "Preparing Proton…", "umu": "Getting umu-launcher…",
                           "queued": "Queued" if self.behind else "Starting…"
                           }[self.phase], ""      # no explanations: the label is enough
            if self.phase == "queued" and self.behind:
                info = "After the current download"
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
        W.menu(self.t, s, *self.overlay[1:], arrows=self.overlay[0] == "menu")

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
