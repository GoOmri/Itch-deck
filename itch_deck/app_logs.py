"""Send your logs (Settings -> Help): a phone page with the cleaned end of the log and a zip (see
logshare.py), and A saves the zip to Documents/SCRiTCH logs. Mixed into App (app.py)."""
import datetime as dt
import logging
import threading

from . import dossummary, logshare, paths
from .input import A, B

log = logging.getLogger("scritch")


class _Provider:
    """What the phone page asks for; built when a request comes in, so it is always current."""
    def __init__(self, version, dos=None):
        self.version = version
        self._dos = dos or (lambda: ("", ""))          # -> (full text, short text) of the own DOS games
        self.zip_name = f"scritch-logs-{dt.datetime.now():%Y-%m-%d-%H%M}.zip"

    def report(self):
        return logshare.report(self.version, dos_short=self._dos()[1])

    def zip(self):
        return logshare.zip_bytes(self.version, dos_text=self._dos()[0])

    def issue(self):
        return logshare.issue_url(self.version, logshare.compact(dos_short=self._dos()[1]))


class LogsMixin:
    def go_logs(self):
        from .app import VERSION
        from .ui.scenes.epic import LogsShare
        self.phone_status = ""
        self._phone_start("logs", lambda text: None)
        if self.phone:
            self.phone.logs = _Provider(VERSION, self._dos_summary)
        self._set("logs", LogsShare(self.t, status="phone" if self.phone else "nonet",
                                    qr=self.phone and self.phone.qr(),
                                    url=self.phone and self.phone.short_url))

    def _dos_summary(self):
        """(full, short) text about the own DOS games, built when the phone asks (never raises)."""
        try:
            try:
                text = (paths.LOGS / "app.log").read_text(errors="replace")[-1_000_000:]
            except OSError:
                text = ""
            return dossummary.build(list(self.lib.games), dict(self.inst.index), dict(self.lib._dosart), text)
        except Exception:  # noqa: BLE001
            log.exception("dos summary failed")
            return "", ""

    def _logs_tick(self, now):
        if self.kind != "logs":
            return
        if self.phone and self.phone.tick():          # the one-time password ran out: new QR
            self.scene.qr, self.scene.url = self.phone.qr(), self.phone.short_url

    def _h_logs(self, act):
        if act == B:
            self.go_settings()
        elif act == A:
            from .app import VERSION

            def save():
                try:
                    f = logshare.save_zip(VERSION, dt.datetime.now(), dos_text=self._dos_summary()[0])
                    log.info("logs: saved %s", f)
                    self.backup_note = ("Saved to Documents/SCRiTCH logs.", False)
                except OSError as e:
                    log.info("logs: can't save: %s", e)
                    self.backup_note = ("Couldn't save the logs.", True)
            threading.Thread(target=save, daemon=True, name="logs-save").start()
