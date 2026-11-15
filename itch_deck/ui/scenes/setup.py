"""P1 Setup: first run, or after itch rejects the key."""
import pygame as pg

from ...input import LEFT, RIGHT
from .. import widgets as W
from .base import Scene
from ... import pads


def KEYBOARD():
    """Steam's on-screen keyboard chord on the pad in use: Steam + X / PS + Square / Xbox + X."""
    return f"{pads.name('GUIDE')} + {pads.name('X')}"

STATUS = {
    "waiting": (False, "Waiting for itch_key.txt in ~/Downloads"),
    "phone": (False, "Waiting for your phone…"),
    "testing": (False, "Key found — checking it with itch.io…"),
    "rejected": (True, "Key rejected by itch.io. Generate a new key and import it again."),
    "offline": (True, "Can't reach itch.io. Check Wi-Fi, then Retry."),
}


class Setup(Scene):
    def __init__(self, t, status="waiting", focus=0, typing=False, typed="", back=False,
                 qr=None, url=None, **kw):
        super().__init__(t, **kw)
        self.status, self.focus = status, focus
        self.qr, self.url = qr, url    # phone login: QR matrix + its address (None = no network)
        self.back = back           # opened from Settings (a key already works): B goes back
        self.typing, self.typed = typing, typed

    def buttons(self):
        if self.status == "offline":
            return ["Retry", "Type key"]
        return ["Import file" if self.qr else "Import key", "Type key"]

    def handle(self, act):
        n = len(self.buttons())
        if act in (LEFT, RIGHT):
            self.focus = (self.focus + (1 if act == RIGHT else -1)) % n

    def hints(self):
        if self.typing:
            return [("A", "Use this key"), ("B", "Cancel")]
        return [("A", "Select"), ("B", "Back" if self.back else "Quit")]

    def draw_page(self, s):
        t = self.t
        w = min(t.w - 2 * t.m, t.page_w)
        x = int(t.cx - w / 2)
        y = t.m
        y = W.wordmark(t, s, x, y).bottom + t.md
        y = W.text(t, s, "Connect your itch.io account", x, y, t.f_h1).bottom + t.xs
        y = W.text(t, s, "One time only. The key stays on this Deck.", x, y, t.f_body,
                   color=t.dim).bottom + t.md
        if self.qr:
            steps = [
                ("Scan the QR code", "Use your phone's camera."),
                ("Get a key on itch", "Open itch API keys → Generate → copy."),
                ("Paste and send", "Paste it on the page, tap Send."),
            ]
            side = min(int(t.h * 0.30), int(w * 0.30))   # QR column
            top = y
            y = self._steps(s, steps, x, y, w - side - t.lg)
            qb = self._qr(s, x + w - side, top, side)
            y = max(y, qb.bottom) + t.sm
        else:
            steps = [
                ("On your PC", "itch.io → Settings → API keys → Generate new API key"),
                ("Send it", "Save it as itch_key.txt and send it to the Deck with Warpinator"),
                ("Import", "Press Import key. The file is read and then deleted."),
            ]
            y = self._steps(s, steps, x, y, w) + t.sm
        st = "phone" if self.qr and self.status == "waiting" else self.status
        err, msg = STATUS[st]
        y = W.notice(t, s, x, y, w, msg, kind="error" if err else "busy").bottom + t.md
        if self.typing:
            return self._field(s, x, y, w)
        W.button_row(t, s, x, y, [(lb, None, True, False) for lb in self.buttons()],
                     self.focus, key=("plate", "setup"))
        W.text(t, s, f"No phone? Import file (itch_key.txt via Warpinator) or Type key ({KEYBOARD()})."
               if self.qr else
               f"Type key opens a field — press {KEYBOARD()} for the on-screen keyboard.",
               x, y + t.btn_h + t.md, t.f_small, color=t.dim, maxw=w)

    def _steps(self, s, steps, x, y, w):
        t = self.t
        rad = int(t.u * 2.2)                      # step number disc
        tx = x + rad * 2 + t.md
        for i, (head, body) in enumerate(steps, 1):
            c = (x + rad, y + t.f_btn.get_linesize() // 2)
            pg.draw.circle(s, t.panel_hi, c, rad)
            W.text(t, s, str(i), c[0], c[1] + 1, t.f_btn, anchor="center")
            hy = W.text(t, s, head, tx, y, t.f_btn).bottom
            y = W.text(t, s, body, tx, hy, t.f_body, color=t.dim, maxw=x + w - tx).bottom + t.sm
        return y

    def _qr(self, s, x, y, side):
        """The phone-login QR on a white plate (dark modules, 2-module quiet zone), address below."""
        t = self.t
        n = len(self.qr)
        mod = max(2, int((side - 2 * t.sm) // (n + 4)))
        plate = pg.Rect(x, y, mod * (n + 4), mod * (n + 4))
        pg.draw.rect(s, (255, 255, 255), plate, border_radius=t.sm)
        ox, oy = plate.x + 2 * mod, plate.y + 2 * mod
        for r, row in enumerate(self.qr):
            for c, on in enumerate(row):
                if on:
                    s.fill((0, 0, 0), (ox + c * mod, oy + r * mod, mod, mod))
        b = W.text(t, s, self.url or "", plate.centerx, plate.bottom + t.xs, t.f_small,
                   color=t.dim, anchor="midtop")
        return W.text(t, s, "Home Wi-Fi only", plate.centerx, b.bottom, t.f_small,
                      color=t.dim, anchor="midtop")

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
        W.text(t, s, f"Press {KEYBOARD()} for the on-screen keyboard, or paste with Ctrl+V (RustDesk).",
               x, r.bottom + t.md, t.f_small, color=t.dim, maxw=w)
