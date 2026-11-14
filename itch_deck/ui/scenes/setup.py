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

    def press_key(self):
        return None if self.typing else ("btn", self.buttons()[self.focus])

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
        w = min(t.w - 2 * t.m, t.page_w)
        x = int(t.cx - w / 2)
        y = t.m
        y = W.wordmark(t, s, x, y).bottom + t.md
        y = W.text(t, s, "Connect your itch.io account", x, y, t.f_h1).bottom + t.xs
        y = W.text(t, s, "One time only. The key stays on this Deck.", x, y, t.f_body,
                   color=t.dim).bottom + t.md
        steps = [
            ("On your PC", "itch.io → Settings → API keys → Generate new API key"),
            ("Send it", "Save it as itch_key.txt and send it to the Deck with Warpinator"),
            ("Import", "Press Import key. The file is read and then deleted."),
        ]
        rad = int(t.u * 2.2)                      # step number disc
        tx = x + rad * 2 + t.md
        for i, (head, body) in enumerate(steps, 1):
            c = (x + rad, y + t.f_btn.get_linesize() // 2)
            pg.draw.circle(s, t.panel_hi, c, rad)
            W.text(t, s, str(i), c[0], c[1] + 1, t.f_btn, anchor="center")
            hy = W.text(t, s, head, tx, y, t.f_btn).bottom
            y = W.text(t, s, body, tx, hy, t.f_body, color=t.dim, maxw=x + w - tx).bottom + t.sm
        y += t.sm
        err, msg = STATUS[self.status]
        y = W.notice(t, s, x, y, w, msg, kind="error" if err else "busy").bottom + t.md
        if self.typing:
            return self._field(s, x, y, w)
        bx = x
        for i, label in enumerate(self.buttons()):
            bw = W.button_w(t, label)
            W.button(t, s, pg.Rect(bx, y, bw, t.btn_h), label, focused=(i == self.focus))
            bx += bw + t.sm
        W.text(t, s, "Type key opens a field — press Steam + X for the on-screen keyboard.",
               x, y + t.btn_h + t.md, t.f_small, color=t.dim, maxw=w)

    def _field(self, s, x, y, w):
        """Typed/pasted key. Only the start and the length are shown."""
        t = self.t
        r = pg.Rect(x, y, w, t.btn_h)
        W.panel(t, s, r, t.focus_fill)
        k = self.typed
        shown = (k[:4] + "•" * min(len(k) - 4, 28)) if len(k) > 4 else k
        tr = W.text(t, s, shown or " ", r.x + t.md, r.centery, t.f_btn, anchor="midleft")
        pg.draw.line(s, t.text_c, (tr.right + 3, r.y + t.sm), (tr.right + 3, r.bottom - t.sm), 2)
        W.text(t, s, f"{len(k)} characters", r.right - t.md, r.centery, t.f_small, color=t.dim,
               anchor="midright")
        W.text(t, s, "Press Steam + X for the on-screen keyboard, or paste with Ctrl+V (RustDesk).",
               x, r.bottom + t.md, t.f_small, color=t.dim, maxw=w)
