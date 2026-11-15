"""Phone login: a tiny one-time web page on the home network, opened by scanning a QR code.

The phone does the copy and paste (an itch API key, later an Epic code); the Deck only shows the QR
and waits. Safety: the page only runs while the QR is on screen, the URL carries a random one-time
password (wrong or missing -> 403), a password is good for TTL seconds and is replaced after a
key was accepted, bodies are capped, and nothing but the posted text reaches the app.
Plain HTTP on the local network: fine at home, the QR screen says not to use public Wi-Fi."""
import html
import re
import json
import logging
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

log = logging.getLogger("itch-deck")
TTL = 300                    # seconds a one-time password (and so a QR code) is valid
MAX_BODY = 8192


def lan_ip():
    """This machine's address on the local network, or None (no network / only loopback).
    A UDP 'connect' sends nothing; it only makes the OS pick the outgoing interface."""
    for probe in ("10.255.255.255", "192.168.255.255", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 1))
                ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
        except OSError:
            continue
    return None


PAGES = {
    "itch": {
        "title": "Connect itch to SCRiTCH",
        "steps": [
            ('<a class="btn" href="https://itch.io/user/settings/api-keys" target="_blank" '
             'rel="noopener">Open itch API keys</a>', "Log in to itch if it asks."),
            ("Tap <b>Generate new API key</b>, then copy the key.", ""),
            ("Come back to this tab and paste it below.", ""),
        ],
        "field": "Paste your itch API key",
    },
}


class PhoneLink:
    """purpose: a key of PAGES. on_text(text) is called (server thread) with what the phone sent;
    status() -> short text the phone page shows while it waits for the Deck's answer."""

    def __init__(self, purpose, on_text, status=lambda: ""):
        self.purpose, self.on_text, self.status = purpose, on_text, status
        self.httpd = self.thread = None
        self.ip = None
        self._new_token()

    def _new_token(self):
        self.token = secrets.token_urlsafe(8)
        self.born = time.time()

    @property
    def url(self):
        return f"http://{self.ip}:{self.httpd.server_address[1]}/?t={self.token}" if self.httpd else None

    @property
    def short_url(self):                      # what's printed under the QR, to type if needed
        return self.url.split("://", 1)[1] if self.httpd else None

    def start(self, port=0):
        self.ip = lan_ip()
        if not self.ip:
            log.info("phonelink: no local network address, phone login off")
            return False
        link = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):        # keep tokens out of the log
                pass

            def _ok(self, t):
                return t is not None and secrets.compare_digest(t, link.token) and \
                    time.time() - link.born < TTL

            def _send(self, code, body, ctype="text/html; charset=utf-8"):
                data = body.encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                u = urlparse(self.path)
                t = (parse_qs(u.query).get("t") or [None])[0]
                if not self._ok(t):
                    return self._send(403, _page("This code has expired",
                                                 "<p>Scan the QR code on your TV again.</p>"))
                if u.path == "/status":
                    return self._send(200, json.dumps({"status": link.status()}),
                                      "application/json")
                if u.path != "/":
                    return self._send(404, "")
                return self._send(200, form_page(link.purpose, link.token))

            def do_POST(self):
                u = urlparse(self.path)
                n = int(self.headers.get("Content-Length") or 0)
                if u.path != "/send" or n <= 0 or n > MAX_BODY:
                    return self._send(400, "")
                form = parse_qs(self.rfile.read(n).decode(errors="replace"))
                t = (form.get("t") or [None])[0]
                if not self._ok(t):
                    return self._send(403, _page("This code has expired",
                                                 "<p>Scan the QR code on your TV again.</p>"))
                text = (form.get("text") or [""])[0].strip()
                if not text:
                    return self._send(200, form_page(link.purpose, link.token, "Nothing was pasted."))
                log.info("phonelink: %s text received (%d chars)", link.purpose, len(text))
                link.on_text(text)
                return self._send(200, sent_page(link.token))

        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        except OSError as e:
            log.warning("phonelink: can't listen: %s", e)
            return False
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="phone")
        self.thread.start()
        log.info("phonelink: %s page on %s port %d", self.purpose, self.ip,
                 self.httpd.server_address[1])
        return True

    def tick(self):
        """Called by the app now and then: a new password when the old one ran out. True if the
        URL changed (the QR must be redrawn)."""
        if self.httpd and time.time() - self.born >= TTL:
            self._new_token()
            return True
        return False

    def renew(self):
        self._new_token()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            log.info("phonelink: stopped")

    def qr(self):
        """QR code of the URL as a list of rows of bools (no quiet zone), or None."""
        if not self.httpd:
            return None
        try:
            import qrcode
        except ImportError:
            return None
        q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(self.url)
        q.make(fit=True)
        return q.get_matrix()


CSS = """body{margin:0;background:#10101e;color:#f0f0f0;font:17px/1.45 system-ui,sans-serif}
main{max-width:30rem;margin:0 auto;padding:1.4rem}h1{font-size:1.35rem;margin:.2rem 0 1rem}
ol{padding-left:1.2rem}li{margin:.7rem 0}small{color:#9a9ab0}
.btn{display:inline-block;background:#2c2e48;color:#fff;padding:.6rem 1rem;border-radius:.6rem;
text-decoration:none;font-weight:600}textarea{width:100%;box-sizing:border-box;min-height:6rem;
background:#1d1f33;color:#fff;border:1px solid #3a3c58;border-radius:.6rem;padding:.7rem;font:inherit}
button{margin-top:.8rem;width:100%;padding:.9rem;border:0;border-radius:.6rem;background:#9d6bff;
color:#141020;font:700 1.05rem system-ui,sans-serif}.err{color:#ff8a8a}
.nm{color:#9d6bff}.nm i{color:#fff;font-style:normal}.note{color:#9a9ab0;font-size:.85rem}"""


NAME_HTML = '<span class="nm">SCR<i>i</i>TCH</span>'   # the name rule: purple, white i


def named(text):
    """Escape text for HTML and draw the app name the SCRiTCH way (same rule as the app)."""
    return re.sub("scritch", NAME_HTML, html.escape(text), flags=re.I)


def _page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{CSS}</style></head><body><main><h1>{named(title)}</h1>{body}</main>'
            f'</body></html>')


def form_page(purpose, token, error=""):
    p = PAGES[purpose]
    steps = "".join(f"<li>{s}{f'<br><small>{html.escape(n)}</small>' if n else ''}</li>"
                    for s, n in p["steps"])
    err = f'<p class="err">{html.escape(error)}</p>' if error else ""
    return _page(p["title"], f"""<ol>{steps}</ol>{err}
<form method="post" action="/send"><input type="hidden" name="t" value="{html.escape(token)}">
<textarea name="text" placeholder="{html.escape(p['field'])}" autocomplete="off"
autocapitalize="off" spellcheck="false"></textarea><button>Send to your Deck</button></form>
<p class="note">Only use this on your home Wi-Fi. The key goes straight to your Deck and is stored
only there.</p>""")


def sent_page(token):
    return _page("Sent", f"""<p id="s">Checking it on your Deck…</p>
<p><a class="btn" href="/?t={html.escape(token)}">Paste a different key</a></p>
<script>const t={json.dumps(token)};let n=0;function poll(){{fetch('/status?t='+encodeURIComponent(t))
.then(r=>r.ok?r.json():null).then(j=>{{if(j&&j.status)document.getElementById('s').textContent=j.status;
if(++n<40&&!(j&&/Connected|rejected/i.test(j.status||'')))setTimeout(poll,1500)}})
.catch(()=>{{document.getElementById('s').textContent='Done here. Look at your TV.'}})}}poll()</script>""")
