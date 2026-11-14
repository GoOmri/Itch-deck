"""P1 Setup: first run, or after itch rejects the key."""
import pygame as pg

from ...input import LEFT, RIGHT
from .. import widgets as W
from .base import Scene

STATUS = {
    "waiting": (False, "Waiting for itch_key.txt in ~/Downloads"),
    "testing": (False, "Key found — checking it with itch.io…"),
    "rejected": (True, "Key rejected by itch.io. Generate a new key and import it again."),
    "offline": (True, "Can't reach itch.io. Check Wi-Fi, then Retry."),
}


class Setup(Scene):
    def __init__(self, t, status="waiting", focus=0, typing=False, typed="", **kw):
        super().__init__(t, **kw)
        self.status, self.focus = status, focus
        self.typing, self.typed = typing, typed

    def buttons(self):
        if self.status == "offline":
            return ["Retry", "Type key"]
        return ["Import key", "Type key"]

    def handle(self, act):
        n = len(self.buttons())
        if act in (LEFT, RIGHT):
            self.focus = (self.focus + (1 if act == RIGHT else -1)) % n

    def hints(self):
        if self.typing:
            return [("A", "Use this key"), ("B", "Cancel")]
        return [("A", "Select"), ("B", "Quit")]

    def draw_page(self, s):
        t = self.t
        w = min(t.w - 2 * t.m, t.u * 100)
        x = int(t.cx - w / 2)
        y = int(t.m * 1.2)
        W.wordmark(t, s, x, y)
        y += t.u * 6.5
        y = W.text(t, s, "Connect your itch.io account", x, y, t.f_h1).bottom + t.u
        y = W.text(t, s, "One time only. The key stays on this Deck.", x, y, t.f_body,
                   color=t.dim).bottom + t.u * 4
        steps = [
            ("On your PC", "itch.io → Settings → API keys → Generate new API key"),
            ("Send it", "Save it as itch_key.txt and send it to the Deck with Warpinator"),
            ("Import", "Press Import key. The file is read and then deleted."),
        ]
        for i, (head, body) in enumerate(steps, 1):
            c = (x + t.u * 2.2, y + t.u * 2.2)
            pg.draw.circle(s, t.panel_hi, c, t.u * 2.2)
            W.text(t, s, str(i), c[0], c[1] + 1, t.f_btn, anchor="center")
            W.text(t, s, head, x + t.u * 6.5, y, t.f_btn)
            W.text(t, s, body, x + t.u * 6.5, y + t.u * 3.8, t.f_body, color=t.dim, maxw=w - t.u * 7)
            y += t.u * 8.5
        y += t.u
        err, msg = STATUS[self.status]
        r = pg.Rect(x, y, w, t.u * 6)
        W.panel(t, s, r, t.error_bg if err else t.panel)
        if err:
            pg.draw.rect(s, t.error, (r.x, r.y, t.u // 2, r.h), border_top_left_radius=t.radius,
                         border_bottom_left_radius=t.radius)
        else:
            W.spinner(t, s, (r.x + int(t.u * 3), r.centery), int(t.u * 1.2), 0.1)
        W.text(t, s, msg, r.x + t.u * (2.5 if err else 6), r.centery, t.f_body, anchor="midleft",
               maxw=w - t.u * 8)
        y = r.bottom + t.u * 4
        if self.typing:
            return self._field(s, x, y, w)
        bx = x
        for i, label in enumerate(self.buttons()):
            bw = W.button_w(t, label)
            W.button(t, s, pg.Rect(bx, y, bw, t.btn_h), label, focused=(i == self.focus))
            bx += bw + t.u * 2.5
        W.text(t, s, "Type key opens a field — press Steam + X for the on-screen keyboard.",
               x, y + t.btn_h + t.u * 2.5, t.f_small, color=t.dim, maxw=w)

    def _field(self, s, x, y, w):
        """Typed/pasted key. Only the start and the length are shown."""
        t = self.t
        r = pg.Rect(x, y, w, t.btn_h)
        W.panel(t, s, r, t.focus_fill)
        k = self.typed
        shown = (k[:4] + "•" * min(len(k) - 4, 28)) if len(k) > 4 else k
        tr = W.text(t, s, shown or " ", r.x + t.u * 2.5, r.centery, t.f_btn, anchor="midleft")
        pg.draw.line(s, t.text_c, (tr.right + 3, r.y + t.u * 1.5), (tr.right + 3, r.bottom - t.u * 1.5), 2)
        W.text(t, s, f"{len(k)} characters", r.right - t.u * 2.5, r.centery, t.f_small, color=t.dim,
               anchor="midright")
        W.text(t, s, "Press Steam + X for the on-screen keyboard, or paste with Ctrl+V (RustDesk).",
               x, r.bottom + t.u * 2.5, t.f_small, color=t.dim, maxw=w)
