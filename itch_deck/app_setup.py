"""Setup page: importing and checking the itch API key.
Mixed into App (app.py); split out of app.py on 15 Nov, code unchanged."""
import logging
import re
import threading

from . import config, net, paths
from .input import (A, B, TEXT, BKSP, ENTER, PASTE)
from .stores.itch import ItchStore
from .app_common import QUIT_DLG
from .phonelink import PhoneLink

log = logging.getLogger("itch-deck")


def key_from_text(text):
    """The itch API key out of whatever the phone pasted (the key, or a line around it)."""
    words = re.findall(r"[A-Za-z0-9_-]{16,}", text or "")
    return max(words, key=len) if words else (text or "").strip()


class SetupMixin:
    # --- phone login (QR) ------------------------------------------------
    def _phone_start(self):
        if self.phone and self.phone.httpd:
            self.phone_stop_at = 0
            return
        self.phone = PhoneLink("itch", self._phone_got, lambda: self.phone_status)
        if not self.phone.start():
            self.phone = None

    def _phone_got(self, text):          # server thread: hand over to the main loop
        self.phone_status = "Checking it on your Deck…"
        self.phone_text = text

    def _phone_tick(self, now):
        p = self.phone
        if not p:
            return
        if self.phone_stop_at and now > self.phone_stop_at:
            p.stop()
            self.phone, self.phone_stop_at = None, 0
            return
        if self.kind != "setup":
            return
        sc = self.scene
        if self.phone_text and sc.status != "testing":
            text, self.phone_text = self.phone_text, None
            sc.typing = False
            self.check_key(key_from_text(text))
        if p.tick():                      # the one-time password ran out: new QR
            sc.qr, sc.url = p.qr(), p.short_url


    def try_import(self, auto=False):
        f = paths.KEY_FILE
        if not f.exists():
            if not auto:
                self.say("No itch_key.txt in Downloads yet.", error=True)
            return
        self.tried_mtime = f.stat().st_mtime
        txt = f.read_text(errors="replace").strip()
        key = txt.split()[0] if txt else ""
        if not key:
            if not auto:
                self.say("itch_key.txt is empty.", error=True)
            return
        self.check_key(key, f)

    def check_key(self, key, file=None):
        self.scene.status, self.scene.typing = "testing", False
        self.inp.set_text_mode(False)

        def work():
            try:
                user = ItchStore(key).check_key()
                self.key_result = ("ok", key, file, user)
            except net.AuthError:
                self.key_result = ("rejected", key, file, None)
            except net.Offline as e:
                log.info("key check offline: %s", e)
                self.key_result = ("offline", key, file, None)
            except Exception:  # noqa: BLE001
                log.exception("key check failed")
                self.key_result = ("offline", key, file, None)
        threading.Thread(target=work, daemon=True, name="keycheck").start()

    def _key_done(self):
        status, key, file, user = self.key_result
        self.key_result = None
        log.info("key check: %s", status)
        if status != "ok":
            self.pending_key = key if status == "offline" else None
            self.scene.status = status
            self.phone_status = {"rejected": "Key rejected by itch. Generate a new one and paste "
                                             "it again.",
                                 "offline": "Your Deck can't reach itch.io. Check its Wi-Fi."
                                 }.get(status, "")
            return
        self.cfg["api_key"], self.cfg["itch_user"] = key, user
        config.save(self.cfg)
        if file:
            try:
                file.unlink()
            except OSError:
                log.warning("could not delete %s", file)
        self.pending_key = None
        self.phone_status = f"Connected as {user}. Look at your TV."
        self.lib.store, self.lib.auth_failed = ItchStore(key), False
        self.go_library()
        self.lib.start_sync()
        self.say(f"Connected to itch.io as {user}.")

    def _h_setup(self, act):
        sc = self.scene
        if sc.status == "testing":
            return
        if sc.typing:
            kind, val = act if isinstance(act, tuple) else (act, None)
            if kind == TEXT:
                sc.typed = (sc.typed + val.strip())[:128]
            elif kind == BKSP:
                sc.typed = sc.typed[:-1]
            elif kind == PASTE:
                sc.typed = (sc.typed + self._clipboard())[:128]
            elif kind in (ENTER, A) and sc.typed:
                self.check_key(sc.typed)
            elif kind == B:
                sc.typing = False
                self.inp.set_text_mode(False)
            return
        if isinstance(act, tuple):
            return
        if act == A:
            label = sc.buttons()[sc.focus]
            if label == "Type key":
                sc.typing, sc.typed = True, ""
                self.inp.set_text_mode(True)
            elif label == "Retry" and self.pending_key:
                self.check_key(self.pending_key, paths.KEY_FILE if paths.KEY_FILE.exists() else None)
            else:
                self.try_import()
        elif act == B:
            if sc.back:                    # came from Settings: the old key still works
                prev = getattr(self, "settings_back", "library")
                self.go_settings()
                self.settings_back = prev  # Settings' own B still returns where it came from
            else:                          # first run / rejected key: nothing to go back to
                sc.overlay = QUIT_DLG
        else:
            sc.handle(act)

    def _clipboard(self):
        try:
            sc = self.pg.scrap
            if not sc.get_init():
                sc.init()
            return (sc.get_text() or "").strip()
        except Exception:  # noqa: BLE001
            return ""
