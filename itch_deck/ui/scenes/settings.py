"""P4 Settings: categories on the left, their settings on the right (like the Deck's own
Settings; room for more platforms and options later)."""
import pygame as pg

from ...input import UP, DOWN, LEFT, RIGHT, A, B
from .. import widgets as W
from .base import Scene

# What the player reads. The app still acts on the internal labels (left).
SHOWN = {"Disconnect itch": "Sign out of itch",
         "Install location": "Install games to", "Saves of uninstalled games": "Old save data",
         "Proton version": "Windows support"}


def epic_in(value):
    return str(value).startswith("Connected")


def shown(label, value, sub):
    """Row as the player reads it: every store says the same 'Sign in to / Sign out of X'."""
    if label in ("Epic", "GOG"):
        return (f"Sign out of {label}", str(value)[len("Connected as "):], sub) \
            if epic_in(value) else (f"Sign in to {label}", "", sub)
    return SHOWN.get(label, label), value, sub


class Settings(Scene):
    def __init__(self, t, values, version, log_path, focus=None, **kw):
        super().__init__(t, **kw)
        self.v, self.version, self.log_path = values, version, log_path
        self.side, self.cat, self.row = True, 0, 0     # focus starts on the category list
        if focus is not None:
            self.focus = focus

    def groups(self):
        v = self.v
        return [
            ("App", "Updates and your library.",
             [("Update app", v["update"], ""),
              ("Refresh library", "", f"Last synced {v['last_sync']}")]),
            ("Sources", "Where your games come from.",             # the stores, then your own DOS folder
             [("Disconnect itch", v.get("itch_user", ""), ""),
              ("Epic", v.get("epic", ""), ""),
              ("GOG", v.get("gog", ""), "")] + ([v["dos_row"]] if v.get("dos_row") else [])),
            ("Storage", "Where games go and what they leave behind.",
             [("Install location", v["install_label"], ""),          # SD card / Internal storage
              ("Saves of uninstalled games", v["prefix_size"], ""),
              ("Manage games", v.get("manage", ""), "")]),                # installed games by size (v0.9.24)
            ("Games & controls", "How games run and how you control them.",
             [("Proton version", v["proton"], ""),
              ("Button symbols", v.get("symbols", "Auto"), ""),
              ("Pointer speed", v.get("pointer", "Normal"), "")]),
            ("Help", "Something not working? Send your logs.",
             [("Send logs", "", "")]),
        ]

    def items(self):
        """Flat, in screen order (the app acts on items()[focus] labels)."""
        return [row for _, _, rows in self.groups() for row in rows]

    @property
    def focus(self):
        return sum(len(r) for _, _, r in self.groups()[:self.cat]) + self.row

    @focus.setter
    def focus(self, i):                                # jump straight to a setting
        for c, (_, _, rows) in enumerate(self.groups()):
            if i < len(rows):
                self.side, self.cat, self.row = False, c, i
                return
            i -= len(rows)

    def waiting(self):
        """An app update is waiting: a purple dot on App."""
        u = self.v.get("update")
        return isinstance(u, tuple) and u[1] in ("Update", "Restart")

    def handle(self, act):
        n = len(self.groups())
        rows = self.groups()[self.cat][2]
        if self.side:
            if act in (UP, DOWN):
                self.cat = (self.cat + (1 if act == DOWN else -1)) % n
                self.row = 0
            elif act in (RIGHT, A):
                self.side = False
        elif act in (UP, DOWN):
            self.row = (self.row + (1 if act == DOWN else -1)) % len(rows)
        elif act in (LEFT, B):
            self.side = True

    ACTION = {"Refresh library": "Refresh", "Install location": "Change",
              "Saves of uninstalled games": "Delete", "Proton version": "Change",
              "Pointer speed": "Change", "Update app": "Check", "Disconnect itch": "Sign out",
              "Button symbols": "Change", "Send logs": "Open", "DOS games": "Open", "Manage games": "Open",
              "DOS games folder": "Open"}

    def hints(self):
        if self.side:
            return [("A", "Open"), ("B", "Back")]
        label, value, _ = self.items()[self.focus]
        act = self.ACTION.get(label, "Select")
        if label in ("Epic", "GOG"):
            act = "Sign out" if epic_in(value) else "Sign in"
        if label == "Proton version" and str(self.v.get("proton", "")).startswith("Not installed"):
            act = "Download"
        if label == "Update app" and isinstance(value, tuple):
            if not value[1] and ("…" in value[0] or "%" in value[0]):
                return [("B", "Back")]                  # checking / downloading
            act = value[1] or "Check"
        return [("A", act), ("B", "Back")]

    def draw_page(self, s):
        t = self.t
        sw = int(t.w * 0.26)                             # sidebar
        side = pg.Surface((sw, t.h - t.hint_h), pg.SRCALPHA)
        side.fill((0, 0, 0, 90))
        s.blit(side, (0, 0))
        x = t.m
        y = W.text(t, s, "Settings", x, t.m, t.f_h1).bottom + t.lg
        rh = int(t.u * 7)
        for c, (name, _, _) in enumerate(self.groups()):
            r = pg.Rect(x - t.md, y, sw - x, rh)
            on = c == self.cat
            k = W.anim(("setcat", name), 1.0 if on and self.side else (0.45 if on else 0.0))
            if k > 0.01:
                W.panel(t, s, r, W.mix(t.panel_hi, t.focus_fill, min(1.0, k)))
            W.text(t, s, name, r.x + t.md, r.centery, t.f_btn, anchor="midleft",
                   color=t.text_c if on else t.dim)
            if name == "App" and self.waiting():
                pg.draw.circle(s, t.accent, (r.right - t.md, r.centery), max(3, t.u // 2))
            y += rh + t.xs

        name, about, rows = self.groups()[self.cat]       # the chosen category, always shown
        px = sw + t.lg
        pw = min(t.w - px - t.m, t.page_w)
        y = W.text(t, s, name, px, t.m + t.sm, t.f_h2).bottom + t.xs
        y = W.text(t, s, about, px, y, t.f_small, color=t.dim, maxw=pw).bottom + t.md
        f = None if self.side else self.row
        if rows[0][0] == "Update app":                     # App: the card, then its rows
            card = pg.Rect(px, y, pw, int(t.u * 12))
            self._app_card(s, card, f == 0)
            rows, y = rows[1:], card.bottom + t.md
            f = None if f in (None, 0) else f - 1
        W.rows(t, s, pg.Rect(px, y, pw, 0), [shown(*r) for r in rows], f, int(t.u * 8), key="settings")

    def _app_card(self, s, r, focused):
        """Version + update in one card; its button is the only thing to press."""
        t = self.t
        info, btn = self.v["update"]
        k = W.anim(("setcard",), 1.0 if focused and not btn else 0.0)   # no button: the card lights
        W.panel(t, s, r, W.mix(t.panel, t.focus_fill, k))
        ty = r.centery - t.f_small.get_height() // 2
        W.text(t, s, f"{W.APP_NAME} v{self.version}", r.x + t.md, ty, t.f_btn, anchor="midleft")
        W.text(t, s, info, r.x + t.md, ty + t.f_btn.get_height() * 0.55, t.f_small,
               color=t.dim, maxw=r.w * 0.6)
        if btn:
            br = pg.Rect(0, 0, W.button_w(t, btn), t.btn_h)
            br.midright = (r.right - t.md, r.centery)
            W.button(t, s, br, btn, focused=focused, accent=btn in ("Update", "Restart"))
