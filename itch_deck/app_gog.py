"""Sign in to GOG (Settings → Sources → GOG): phone QR sign-in (the player pastes the address
GOG ends on), then the GOG tab fills in the background. Same flow as app_epic.py, minus the
helper download (signing in to GOG needs none since v0.9.1). Mixed into App (app.py)."""
import logging
import threading

from . import config
from .input import B

log = logging.getLogger("scritch")


class GogMixin:
    def go_gog(self):
        from .stores.gog import GogStore
        from .ui.scenes.epic import GogConnect
        store = GogStore()
        job = self.gog_job = {"store": store, "frac": None, "ready": store.ready(),
                              "error": None, "text": None, "result": None, "busy": False}
        self.phone_status = ""
        self._phone_start("gog", self._gog_got)
        self._set("gog", GogConnect(self.t, status=self._gog_status(),
                                    qr=self.phone and self.phone.qr(),
                                    url=self.phone and self.phone.short_url))

    def _gog_status(self):
        job = self.gog_job
        if job["busy"]:
            return "checking"
        if job["error"]:
            return job["error"]
        if not job["ready"]:
            return "prep"
        return "phone" if self.phone else "nonet"

    def _gog_got(self, text):             # server thread: hand over to the main loop
        self.phone_status = "Signing in…"
        self.gog_job["text"] = text

    def _gog_login(self, text):
        from .stores.gog import GogError, code_from_text
        job = self.gog_job
        code = code_from_text(text)
        try:
            if not code:
                log.info("gog: no code in what the phone sent (%d chars)", len(text))
                job["result"] = ("rejected", None)
            elif job["store"].login(code):
                job["result"] = ("ok", job["store"].user())
            else:
                job["result"] = ("rejected", None)
        except GogError as e:
            log.info("gog: sign-in failed: %s", e)
            job["result"] = ("offline", None)
        finally:
            job["busy"] = False

    def _gog_tick(self, now):
        if self.kind != "gog":
            return
        job, sc = self.gog_job, self.scene
        if self.phone and self.phone.tick():          # one-time password ran out: new QR
            sc.qr, sc.url = self.phone.qr(), self.phone.short_url
        if job["text"] and job["ready"] and not job["busy"]:
            text, job["text"] = job["text"], None
            job["busy"], job["error"] = True, None
            self.phone_status = "Signing in…"
            threading.Thread(target=self._gog_login, args=(text,), daemon=True,
                             name="gog-auth").start()
        res, job["result"] = job["result"], None
        if res and res[0] == "ok":
            user = res[1] or "GOG"
            self.phone_status = f"Connected as {user}. Head back to your Deck."
            self.cfg["gog"] = True
            config.save(self.cfg)
            self.lib.gog = job["store"]
            self.lib.start_gog_sync()
            log.info("gog: connected as %s", user)
            self.filt = "gog"                          # show the new tab (fills in a moment)
            self.go_library()
            self.say(f"Connected to GOG as {user}.")
            return
        if res:
            job["error"] = res[0]
            self.phone_status = {"rejected": "Code rejected by GOG. Sign in again and send the "
                                             "new address.",
                                 "offline": "Your Deck can't reach GOG. Check its Wi-Fi."}[res[0]]
        sc.status, sc.progress = self._gog_status(), job["frac"]

    def _h_gog(self, act):
        if act == B:
            self.go_settings()

    # --- Settings row --------------------------------------------------------------
    def _gog_label(self):
        """Settings → Sources → GOG."""
        if self.lib.gog and self.lib.gog.connected():
            return f"Connected as {self.lib.gog.user() or 'GOG'}"
        return "Signed out" if self.lib.gog else "Not connected"

    def _disconnect_gog(self):
        store = self.lib.gog
        self.lib.drop_gog()
        self.cfg.pop("gog", None)
        config.save(self.cfg)
        if self.filt == "gog":
            self.filt = "all"
        if store:
            store.logout()                             # local only: deletes the sign-in file
        log.info("settings: gog disconnected")
        if self.kind == "settings":
            self.scene.v["gog"] = self._gog_label()
        self.say("GOG disconnected.")
