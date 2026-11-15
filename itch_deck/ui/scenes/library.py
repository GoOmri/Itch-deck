"""P2 Library (home): All / Installed (+ itch / Epic once 2 stores are connected) tabs,
Sort & filter menu (X), cover grid."""
import pygame as pg

from ...input import UP, DOWN, LEFT, RIGHT, X, L2, R2
from .. import widgets as W
from .base import Scene
from ... import hltb, pads


STORE_NAMES = {"itch": "itch", "epic": "Epic"}
SORTS = (("az", "A–Z"), ("played", "Recently played"), ("added", "Recently added"),
         ("short", "Shortest first"))


def tabs(stores=("itch",)):
    """All · Installed, then one tab per store (Omri 15 Nov: All · Installed · itch · Epic).
    With one store its tab would equal All, so store tabs show only from two stores on."""
    out = [("all", "All"), ("installed", "Installed")]
    if len(stores) > 1:
        out += [(k, STORE_NAMES.get(k, k)) for k in stores]
    return tuple(out)


TABS = tabs()            # default set (itch only); a Library uses self.tabs()
SHOWS = (("all", "Everything"), ("playable", "Playable here"))
LENGTHS = (("any", "Any"), ("short", "Under 2 h"), ("mid", "2–10 h"), ("long", "10 h+"))


def playable(g):
    return bool(g["platforms"] & {"linux", "windows"})


def length_kind(g):
    """Time to beat (HowLongToBeat main story) bucket, "" when unknown."""
    h = hltb.length_hours(g.get("ttb"))
    return "" if not h else ("short" if h < 2 else "mid" if h <= 10 else "long")


def genres(games):
    """Genres in the library, most common first (developers' own itch "Genre")."""
    from collections import Counter
    return [x for x, _ in Counter(g["genre"] for g in games if g.get("genre")).most_common()]


def visible(games, filt="all", sort="az", show="all", genre="any", length="any"):
    """The games a tab shows, in order (the app uses it too, for L1/R1 on the game page)."""
    gs = [g for g in games if playable(g)] if show == "playable" else list(games)
    if genre != "any":
        gs = [g for g in gs if g.get("genre") == genre]
    if length != "any":
        gs = [g for g in gs if length_kind(g) == length]
    if filt == "installed":
        gs = [g for g in gs if g.get("state") in ("installed", "missing")]
    elif filt in STORE_NAMES:                               # a store tab
        gs = [g for g in gs if g.get("store", "itch") == filt]
    if sort == "played":                                    # last played first, then the rest A–Z
        gs.sort(key=lambda g: g.get("played") or "", reverse=True)
    elif sort == "added":
        gs.sort(key=lambda g: g.get("added") or "", reverse=True)
    elif sort == "short":                                   # unknown length last, A–Z
        gs.sort(key=lambda g: hltb.length_hours(g.get("ttb")) or float("inf"))
    return gs


VIEW = {"sort": "az", "show": "all", "genre": "any", "length": "any"}   # a tab with no filter


def _view_prop(name):
    """sort / show / genre / length read and write the CURRENT tab's view (Omri 15 Nov: each tab
    has its own Sort & filter; Installed must not lose games to a filter set on All)."""
    return property(lambda self: self.view()[name],
                    lambda self, v: self.view().__setitem__(name, v))


class Library(Scene):
    sort, show, genre, length = (_view_prop(n) for n in ("sort", "show", "genre", "length"))

    def __init__(self, t, games, filt="all", focus=0, syncing=None, sync_page=0,
                 offline_since=None, offline=False, sort="az", show="all", genre="any",
                 length="any", stores=("itch",), views=None, **kw):
        super().__init__(t, **kw)
        self.stores = tuple(stores)
        if filt not in dict(self.tabs()):     # e.g. an old "recent" tab, or Epic disconnected
            filt = "all"
        self.games, self.filt, self.focus = games, filt, focus
        # X menu per tab: {tab: {sort, show, genre, length}} (saved in config by the app);
        # without views, the sort/show/genre/length arguments are the current tab's
        self.views = views if views is not None else \
            {filt: dict(sort=sort, show=show, genre=genre, length=length)}
        self.syncing, self.sync_page = syncing, sync_page   # None | "first" | "bg"
        self.offline_since = offline_since
        self.offline = offline          # True with no cache yet: nothing to show
        self.activity = None            # "Covers 40/120", "Downloading 45% · Game"… (top bar)
        self.notice = None              # app update state (top bar, accent colour, no spinner)

    def view(self):
        return self.views.setdefault(self.filt, dict(VIEW))

    @property
    def shown(self):
        return visible(self.games, self.filt, self.sort, self.show, self.genre, self.length)

    def filtered(self):
        """True when Show / Genre / Length narrow the list (Sort only orders it)."""
        return (self.show, self.genre, self.length) != ("all", "any", "any")

    def filter_summary(self):
        """Short words for the top bar, e.g. "Puzzle · Under 2 h" (empty when nothing filters)."""
        bits = [dict(SHOWS)[self.show] if self.show != "all" else "",
                self.genre if self.genre != "any" else "",
                dict(LENGTHS)[self.length] if self.length != "any" else ""]
        return "  ·  ".join(b for b in bits if b)

    def _count(self, **change):
        """How many games this tab would show with one setting changed (counts in the menu)."""
        v = dict(filt=self.filt, sort=self.sort, show=self.show, genre=self.genre,
                 length=self.length)
        v.update(change)
        return len(visible(self.games, **v))

    def menu_items(self):
        """X: Sort & filter. Each row shows its value; filter values carry their game count."""
        def n(**c):
            return f"  ({self._count(**c)})"
        rows = [("Sort", dict(SORTS)[self.sort], ""),
                ("Show", dict(SHOWS)[self.show] + n(show=self.show), ""),
                ("Genre", ("Any" if self.genre == "any" else self.genre) + n(genre=self.genre), ""),
                ("Length", dict(LENGTHS)[self.length] + n(length=self.length), "")]
        if self.filtered():
            rows.append(("Clear filters", "", ""))
        return rows

    def menu_open(self, f=0):
        rows = self.menu_items()
        self.overlay = ("menu", "Sort & filter", f"{len(self.shown)} games", rows,
                        max(0, min(f, len(rows) - 1)))

    def menu_next(self, label, step=1):
        """Change one setting by `step` (LEFT/RIGHT = -1/+1, A = +1); "Clear filters" resets."""
        def turn(cur, keys):
            return keys[(keys.index(cur) + step) % len(keys)] if cur in keys else keys[0]
        if label == "Sort":
            self.sort = turn(self.sort, [k for k, _ in SORTS])
        elif label == "Show":
            self.show = turn(self.show, [k for k, _ in SHOWS])
        elif label == "Genre":
            self.genre = turn(self.genre, ["any"] + genres(self.games))
        elif label == "Length":
            self.length = turn(self.length, [k for k, _ in LENGTHS])
        elif label == "Clear filters":
            self.show, self.genre, self.length = "all", "any", "any"
        self.focus, self._first, self._sy = 0, 0, None
        self.menu_open(self.overlay[4] if label != "Clear filters" else 1)

    def tabs(self):
        return tabs(self.stores)

    def next_tab(self, step):
        keys = [k for k, _ in self.tabs()]
        self.filt = keys[(keys.index(self.filt) + step) % len(keys)]
        self.focus, self._first, self._sy = 0, 0, None

    # --- input ---------------------------------------------------------
    def handle(self, act):
        n, c = len(self.shown), self.t.grid_cols
        if self.overlay and self.overlay[0] == "menu":
            kind, title, sub, items, f = self.overlay
            if act in (UP, DOWN):
                self.overlay = (kind, title, sub, items, (f + (1 if act == DOWN else -1)) % len(items))
            return
        if act == X:
            self.menu_open()
        elif n:
            step = {LEFT: -1, RIGHT: 1, UP: -c, DOWN: c, L2: -3 * c, R2: 3 * c}.get(act, 0)
            if step:
                self.focus = max(0, min(n - 1, self.focus + step))

    # --- drawing -------------------------------------------------------
    def hints(self):
        if self.syncing == "first":
            return [("B", "Quit")]
        return [("MENU", "Settings"), ("X", "Sort & filter"), ("L1", ""), ("R1", "Tabs"),
                ("A", "Open"), ("B", "All games" if self.filt != "all" else "Quit")]

    def overlay_hints(self):
        if self.overlay and self.overlay[0] == "menu":
            return [("◀", ""), ("▶", "Change"), ("B", "Close")]
        return super().overlay_hints()

    def draw_overlay(self, s):
        if self.overlay[0] == "menu":
            return W.menu(self.t, s, *self.overlay[1:], arrows=True)
        return super().draw_overlay(s)

    def draw_page(self, s):
        t = self.t
        state = (self.sort, self.show, self.genre, self.length)
        if self.overlay and self.overlay[0] == "menu":
            # Sort & filter open: the library behind stays STILL (Omri, v0.7.2: ◀ ▶ re-sorted
            # and scrolled the grid under the shade). The menu title shows the live count; the
            # new result fades in when the menu closes.
            if getattr(self, "_frozen", None) is None or self._frozen[0] != s.get_size():
                buf = pg.Surface(s.get_size(), pg.SRCALPHA)
                self._draw_live(buf)
                self._frozen = (s.get_size(), buf, state)
            s.blit(self._frozen[1], (0, 0))
            return
        frozen, self._frozen = getattr(self, "_frozen", None), None
        if frozen is not None and frozen[2] != state:      # filters changed: fade the new grid in
            self._tab_dir = 0
            W._ANIM.pop(("tabswipe", id(self)), None)
        self._draw_live(s)

    def _draw_live(self, s):
        t = self.t
        y = self._top_bar(s)
        key = ("tabswipe", id(self))
        if getattr(self, "_tab_filt", self.filt) != self.filt:      # tab changed: swipe in
            keys = [k for k, _ in self.tabs()]                      # tab to the right: from right
            self._tab_dir = 1 if keys.index(self.filt) > keys.index(self._tab_filt) else -1
            W._ANIM.pop(key, None)                                  # restart from 0
        self._tab_filt = self.filt
        k = W.anim(key, 1.0, start=0.0 if key not in W._ANIM and hasattr(self, "_tab_dir")
                   else None, ms=t.page_ms)
        if k < 1:                       # content slides in from the tab's side and fades in
            buf = pg.Surface(s.get_size(), pg.SRCALPHA)
            self._content(buf, y)
            buf.set_alpha(int(255 * max(0.0, min(1.0, k * 1.5))))
            s.blit(buf, (int((1 - k) * t.u * t.page_slide_u * getattr(self, "_tab_dir", 1)), 0))
            return
        self._content(s, y)

    def _content(self, s, y):
        t = self.t
        if self.syncing == "first":
            return self._center_msg(s, y, f"Syncing library… page {self.sync_page}",
                                    "This is only slow the first time.", spinner=True)
        if not self.shown:
            if self.filt == "installed":
                return self._center_msg(s, y, "Nothing installed yet.",
                                        "Install a game from All and it shows up here.")
            if self.filt in STORE_NAMES and not self.filtered():
                name = STORE_NAMES[self.filt]
                return self._center_msg(s, y, f"No {name} games yet.",
                                        f"Games in your {name} library show up here.")
            if self.offline:
                return self._center_msg(s, y, "Can't reach itch.io.",
                                        f"Check Wi-Fi, then press {pads.name('Y')} to try again.", refresh=True)
            return self._center_msg(s, y, "No games yet.",
                                    "Games you buy or claim on itch show up here.", refresh=True)
        self._grid(s, y)

    def _top_bar(self, s):
        t = self.t
        base = int(t.m + t.xs)              # everything in the top bar sits on this baseline
        r = W.wordmark(t, s, t.m, base, anchor="baseleft")
        x = r.right + t.lg
        for key, label in self.tabs():
            on = self.filt == key
            lr = W.text(t, s, label, x, base, t.f_btn, color=t.text_c if on else t.dim,
                        anchor="baseleft")
            if on:                       # underline slides between tabs (spring)
                ux = W.anim(("tab", "x"), lr.x, back=W.TAB_BACK)
                uw = W.anim(("tab", "w"), lr.w, back=W.TAB_BACK)
                pg.draw.rect(s, t.accent, (int(ux), base + t.xs, int(uw), max(2, t.u // 3)))
            x = lr.right + t.md
        n = len(self.shown)
        right = t.w - t.m
        if self.offline_since:
            right = W.offline_mark(t, s, right, base, self.offline_since)
        count = f"{n} game{'s' if n != 1 else ''}"
        rr = W.text(t, s, count, right, base, t.f_small, color=t.dim, anchor="baseright")
        act = self.activity or ("Refreshing library" if self.syncing == "bg" else None)
        if act:                         # background work, hidden when done
            sep = W.text(t, s, "·", rr.x - t.sm, base, t.f_small, color=t.dim, anchor="baseright")
            ar = W.text(t, s, act, sep.x - t.sm, base, t.f_small, color=t.dim, anchor="baseright",
                        maxw=int(t.w * 0.38))
            sr = int(t.u * 1.2)
            W.spinner(t, s, (int(ar.x - t.sm - sr), int(base - W.x_mid(t.f_small))), sr, 0.15)
            rr = pg.Rect(ar.x - t.sm - sr * 2, ar.y, 0, ar.h)
        if self.notice:                 # e.g. app update ready: purple = "happening"
            sep = W.text(t, s, "·", rr.x - t.sm, base, t.f_small, color=t.dim, anchor="baseright")
            W.text(t, s, self.notice, sep.x - t.sm, base, t.f_small, color=t.accent,
                   anchor="baseright", maxw=int(t.w * 0.3))
        return int(base + t.lg)

    def _center_msg(self, s, y, title, sub, spinner=False, refresh=False):
        t = self.t
        cy = (y + t.h - t.hint_h) / 2
        if spinner:
            W.spinner(t, s, (int(t.cx), int(cy - t.xl)), int(t.u * 3), 0.2)
        r = W.text(t, s, title, t.cx, cy, t.f_h2, anchor="center")
        W.text(t, s, sub, t.cx, r.bottom + t.xs, t.f_body, color=t.dim, anchor="midtop")
        # refresh: Y is already in the footer (DESIGN rule 6), not repeated here

    def _grid(self, s, top):
        t = self.t
        cols = t.grid_cols
        tw = (t.w - 2 * t.m - t.gap * (cols - 1)) / cols
        th = tw * t.cover_ratio
        row_h = th + t.xs + t.f_small.get_height() * 2 + t.gap
        pad = int(tw * (t.focus_scale - 1) / 2 + t.outline + 2)
        area = pg.Rect(0, top, t.w, t.h - t.hint_h - top)
        visible = max(1, int((area.h - pad) // row_h))
        frow = self.focus // cols
        first = getattr(self, "_first", 0)          # scroll only when focus leaves the view
        first = min(max(first, frow - visible + 1), frow)
        self._first = first
        self._sy = W.ease(getattr(self, "_sy", None), first * row_h, back=0)   # scroll: no bounce
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
