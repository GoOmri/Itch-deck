"""Connect Epic Games / GOG: QR for the phone, three steps, one status line (same layout as
Setup). GogConnect = the same page with GOG's words."""
from .. import widgets as W
from .base import Scene
from .setup import Setup

STATUS = {                     # (error?, text)
    "prep": (False, "Getting ready…"),
    "phone": (False, "Waiting for your phone…"),
    "checking": (False, "Signing in to Epic…"),
    "rejected": (True, "Epic didn't accept that. Sign in again and send the new page."),
    "offline": (True, "Can't reach Epic. Check Wi-Fi, then try again."),
    "nonet": (True, "Connect your Deck to Wi-Fi to sign in."),
}


class EpicConnect(Setup):
    TITLE = "Connect Epic Games"
    STEPS = [("Scan the QR code", "Use your phone's camera."),
             ("Sign in to Epic", "Tap Open Epic sign-in on the page."),
             ("Copy and send", "Copy the page Epic shows, paste it, tap Send.")]
    STATUS = STATUS
    SUB = "One time only. Your sign-in stays on this Deck."

    def __init__(self, t, status="prep", qr=None, url=None, progress=None, **kw):
        Scene.__init__(self, t, **kw)
        self.status, self.qr, self.url, self.progress = status, qr, url, progress
        self.focus, self.typing, self.back = 0, False, True

    def buttons(self):
        return []

    def handle(self, act):
        pass

    def hints(self):
        return [("B", "Back")]

    def draw_page(self, s):
        t = self.t
        w = min(t.w - 2 * t.m, t.page_w)
        x = int(t.cx - w / 2)
        y = W.wordmark(t, s, x, t.m).bottom + t.md
        y = W.text(t, s, self.TITLE, x, y, t.f_h1).bottom + t.xs
        y = W.text(t, s, self.SUB, x, y, t.f_body, color=t.dim).bottom + t.md
        if self.qr:
            steps = self.STEPS
            side = min(int(t.h * 0.30), int(w * 0.30))
            top = y
            y = self._steps(s, steps, x, y, w - side - t.lg)
            y = max(y, self._qr(s, x + w - side, top, side).bottom) + t.sm
        err, msg = self.STATUS.get(self.status, self.STATUS["prep"])
        if self.status == "prep" and self.progress:
            msg = f"Getting ready… {int(self.progress * 100)}%"
        W.notice(t, s, x, y, w, msg, kind="error" if err else "busy")


class GogConnect(EpicConnect):
    TITLE = "Connect GOG"
    STEPS = [("Scan the QR code", "Use your phone's camera."),
             ("Sign in to GOG", "Tap Open GOG sign-in on the page."),
             ("Copy and send", "Copy the page's address, paste it, tap Send.")]
    STATUS = dict(STATUS, checking=(False, "Signing in to GOG…"),
                  rejected=(True, "GOG didn't accept that. Sign in again and send the new address."),
                  offline=(True, "Can't reach GOG. Check Wi-Fi, then try again."))


class LogsShare(EpicConnect):
    """Settings -> Help -> Send logs: a QR code for the phone page that shows the cleaned end of the
    log (to copy into a GitHub issue); A also saves the full cleaned zip into Documents."""
    TITLE = "Send your logs"
    SUB = "Scan the code, or press A to save the logs as a zip in Documents."
    STEPS = [("Scan the QR code", "Use your phone's camera."),
             ("Read the text", "Secrets and names are hidden."),
             ("Open the issue", "Tap the purple button. Your log is filled in.")]
    STATUS = {"prep": (False, "Getting ready…"),
              "phone": (False, "Ready on your phone. The link works for a few minutes."),
              "nonet": (True, "No Wi-Fi. Press A to save the logs, then send the file.")}

    def hints(self):
        return [("A", "Save a copy"), ("B", "Back")]
