"""Connect Epic Games (Settings → Sources → Epic): get legendary once, phone QR sign-in,
then the Epic tab fills in the background. Mixed into App (app.py)."""
import logging
import threading

from . import config
from .input import B

log = logging.getLogger("scritch")


class EpicMixin:
    def go_epic(self):
        from .stores.epic import EpicStore
        from .ui.scenes.epic import EpicConnect
        store = EpicStore()
        job = self.epic_job = {"store": store, "frac": None, "ready": store.ready(),
                               "error": None, "text": None, "result": None, "busy": False}
        self.phone_status = ""
        self._phone_start("epic", self._epic_got)
        if not job["ready"]:
            threading.Thread(target=self._epic_fetch, daemon=True, name="epic-get").start()
        self._set("epic", EpicConnect(self.t, status=self._epic_status(),
                                      qr=self.phone and self.phone.qr(),
                                      url=self.phone and self.phone.short_url))

    def _epic_fetch(self):
        from .stores.epic import EpicError, fetch_legendary
        job = self.epic_job
        try:
            fetch_legendary(on_bytes=lambda d, t: job.__setitem__("frac", d / t if t else None))
            job["ready"] = True
        except EpicError as e:
            job["error"] = "offline"
            log.info("epic: %s", e)

    def _epic_status(self):
        job = self.epic_job
        if job["busy"]:
            return "checking"
        if job["error"]:
            return job["error"]
        if not job["ready"]:
            return "prep"
        return "phone" if self.phone else "nonet"

    def _epic_got(self, text):            # server thread: hand over to the main loop
        self.phone_status = "Signing in…"
        self.epic_job["text"] = text

    def _epic_login(self, text):
        from .stores.epic import EpicError, code_from_text
        job = self.epic_job
        code = code_from_text(text)
        try:
            if not code:
                log.info("epic: no code in what the phone sent (%d chars)", len(text))
                job["result"] = ("rejected", None)
            elif job["store"].login(code):
                job["result"] = ("ok", job["store"].user())
            else:
                job["result"] = ("rejected", None)
        except EpicError as e:
            log.info("epic: sign-in failed: %s", e)
            job["result"] = ("offline", None)
        finally:
            job["busy"] = False

    def _epic_tick(self, now):
        if self.kind != "epic":
            return
        job, sc = self.epic_job, self.scene
        if self.phone and self.phone.tick():          # one-time password ran out: new QR
            sc.qr, sc.url = self.phone.qr(), self.phone.short_url
        if job["text"] and job["ready"] and not job["busy"]:
            text, job["text"] = job["text"], None
            job["busy"], job["error"] = True, None
            threading.Thread(target=self._epic_login, args=(text,), daemon=True,
                             name="epic-auth").start()
        if job["text"] and job["error"] == "offline" and not job["ready"]:   # helper never came
            job["text"] = None
            self.phone_status = "Your Deck can't reach Epic. Check its Wi-Fi."
        res, job["result"] = job["result"], None
        if res and res[0] == "ok":
            user = res[1] or "Epic"
            self.phone_status = f"Connected as {user}. Head back to your Deck."
            self.cfg["epic"] = True
            config.save(self.cfg)
            self.lib.epic = job["store"]
            self.lib.start_epic_sync()
            log.info("epic: connected as %s", user)
            self.filt = "epic"                         # show the new tab (fills in a moment)
            self.go_library()
            self.say(f"Connected to Epic as {user}.")
            return
        if res:
            job["error"] = res[0]
            self.phone_status = {"rejected": "Code rejected by Epic. Sign in again and send the "
                                             "new page.",
                                 "offline": "Your Deck can't reach Epic. Check its Wi-Fi."}[res[0]]
        sc.status, sc.progress = self._epic_status(), job["frac"]

    def _h_epic(self, act):
        if act == B:
            self.go_settings()

    # --- Settings row --------------------------------------------------------------
    def _epic_label(self):
        """Settings → Sources → Epic."""
        if self.lib.epic and self.lib.epic.connected():
            return f"Connected as {self.lib.epic.user() or 'Epic'}"
        return "Signed out" if self.lib.epic else "Not connected"

    def _disconnect_epic(self):
        store = self.lib.epic
        self.lib.drop_epic()
        self.cfg.pop("epic", None)
        config.save(self.cfg)
        if self.filt == "epic":
            self.filt = "all"
        if store:                                      # sign out on Epic's side too (online)
            threading.Thread(target=store.logout, daemon=True, name="epic-out").start()
        log.info("settings: epic disconnected")
        if self.kind == "settings":
            self.scene.v["epic"] = self._epic_label()
        self.say("Epic disconnected.")
