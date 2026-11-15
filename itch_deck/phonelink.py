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
            ('<a class="btn pri" href="https://itch.io/user/settings/api-keys" target="_blank" '
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
                    return self._send(403, expired_page())
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
                    return self._send(403, expired_page())
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
main{max-width:30rem;margin:0 auto;padding:1.4rem;
padding-top:max(3rem,calc(env(safe-area-inset-top) + 1.6rem))}h1{font-size:1.35rem;margin:.2rem 0 1rem}
ol{padding-left:1.2rem}li{margin:.7rem 0}small{color:#9a9ab0}
.btn,button{display:inline-block;box-sizing:border-box;min-width:11rem;background:#2c2e48;color:#fff;
padding:.9rem 1.6rem;border:0;border-radius:.6rem;text-decoration:none;text-align:center;
font:700 1.05rem system-ui,sans-serif;cursor:pointer}textarea{width:100%;box-sizing:border-box;min-height:6rem;
background:#1d1f33;color:#fff;border:1px solid #3a3c58;border-radius:.6rem;padding:.7rem;font:inherit}
button,.btn.pri{background:#6846b8}button:active,.btn.pri:active{background:#9d6bff}
form button{display:block;width:100%;margin-top:.8rem}button:disabled{background:#2c2e48;color:#9a9ab0;cursor:default}
/* ONE button style (DESIGN, Buttons): white text; main = deep purple, bright while pressed
   (same as the app); as wide as the block it belongs to; grey until it can do something */.err{color:#ff8a8a}
.nm{color:#9d6bff}.nm i{color:#fff;font-style:normal}.note{color:#9a9ab0;font-size:.85rem}
.wide{display:block;text-align:center}
.res{min-height:calc(100vh - 6rem);display:flex;flex-direction:column;justify-content:center;
align-items:center;text-align:center}.res[hidden]{display:none}
.ico{width:6.5rem;height:6.5rem;border-radius:50%;display:flex;align-items:center;justify-content:center;
margin-bottom:1.4rem}.ico svg{width:3.2rem;height:3.2rem}
.ico.ok{background:rgba(95,211,138,.16);color:#5fd38a}.ico.bad{background:rgba(255,138,138,.16);color:#ff8a8a}
.ico.old{background:#1d1f33;color:#9a9ab0}
.spin{width:4.6rem;height:4.6rem;margin:1rem 0 2.3rem;animation:r 4.5s linear infinite}
.spin circle{fill:none;stroke-width:4.4}.spin .tr{stroke:#2c2e48}
.spin .hd{stroke:#9d6bff;stroke-dasharray:6 200;animation:c 1.4s cubic-bezier(.65,0,.35,1) infinite}
@keyframes r{to{transform:rotate(360deg)}}
@keyframes c{0%{stroke-dasharray:6 200;stroke-dashoffset:0}50%{stroke-dasharray:96 200;stroke-dashoffset:-10}
100%{stroke-dasharray:6 200;stroke-dashoffset:-125.7}}
/* busy = chasing edges: the front races ahead, the back catches up (same as the app).
   The back edge travels one full circle (2πr = 125.7) so each loop ends where the next starts */
.res h2{font-size:1.75rem;line-height:1.2;margin:0 0 .5rem}.res p{color:#9a9ab0;margin:0 0 1.8rem;max-width:20rem}
.res .btn,.res button{margin:0}"""


NAME_HTML = '<span class="nm">SCR<i>i</i>TCH</span>'   # the name rule: purple, white i


def named(text):
    """Escape text for HTML and draw the app name the SCRiTCH way (same rule as the app)."""
    return re.sub("scritch", NAME_HTML, html.escape(text), flags=re.I)


def result(kind, head, line, action=""):
    """THE phone result block (Omri): centred and lowered, big icon + headline + one line.
    kind: wait (purple spinner) | ok (green ✓ — the ONLY green, phone pages only) |
    bad (red ✗) | old (grey ↻)."""
    svg = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" '
           'stroke-linecap="round" stroke-linejoin="round">{}</svg>')    # drawn, exactly centred
    icon = {"wait": '<svg class="spin" viewBox="0 0 50 50"><circle class="tr" cx="25" cy="25" r="20"/>'
                    '<circle class="hd" cx="25" cy="25" r="20" transform="rotate(-90 25 25)"/></svg>',
            "ok": '<div class="ico ok">' + svg.format('<path d="M5 12.5l4.5 4.5L19 7.5"/>') + '</div>',
            "bad": '<div class="ico bad">' + svg.format('<path d="M7 7l10 10M17 7L7 17"/>') + '</div>',
            "old": '<div class="ico old">' + svg.format('<path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5"/>')
                   + '</div>'}   # no backslashes inside f-strings: CI runs Python 3.11
    return (f'<div class="res" id="{kind}">{icon[kind]}<h2 id="{kind}h">{named(head)}</h2>'
            f'<p id="{kind}p">{named(line)}</p>{action}</div>')


def expired_page():
    return _page("This code has expired", result("old", "This code has expired",
                                                  "Scan the QR code on your TV again."), heading=False)


def _page(title, body, heading=True):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{html.escape(title)}</title>'
            f'<style>{CSS}</style></head><body><main>{f"<h1>{named(title)}</h1>" if heading else ""}{body}</main>'
            f'</body></html>')


def form_page(purpose, token, error="", text=""):
    p = PAGES[purpose]
    steps = "".join(f"<li>{s}{f'<br><small>{html.escape(n)}</small>' if n else ''}</li>"
                    for s, n in p["steps"])
    err = f'<p class="err">{html.escape(error)}</p>' if error else ""
    return _page(p["title"], f"""<ol>{steps}</ol>{err}
<form method="post" action="/send"><input type="hidden" name="t" value="{html.escape(token)}">
<textarea name="text" placeholder="{html.escape(p['field'])}" autocomplete="off"
autocapitalize="off" spellcheck="false">{html.escape(text)}</textarea><button>Send to your Deck</button></form>
<script>{{const x=document.querySelector('textarea'),b=document.querySelector('form button'),
u=()=>b.disabled=!x.value.trim();x.addEventListener('input',u);u()}}</script>
<p class="note">Only use this on your home Wi-Fi. The key goes straight to your Deck and is stored
only there.</p>""")


def split_status(s):
    """'Key rejected by itch. Generate a new one…' -> ('Key rejected by itch', 'Generate…')."""
    head, _, rest = s.partition(". ")
    return head.rstrip("."), rest


def sent_page(token, preview=None):
    """After Send: a big centred result. preview=(kind, status) renders one state without the
    script's help (mockups); normally the script polls the Deck and switches states."""
    t = json.dumps(token)
    kind, status = preview or ("wait", "")
    ok_h, ok_p = split_status(status) if kind == "ok" else ("", "")
    bad_h, bad_p = split_status(status) if kind == "bad" else ("", "")
    hide = lambda k: "" if k == kind else " hidden"           # noqa: E731
    body = (result("wait", "Checking your key…", "Checking it on your Deck…").replace(
                '<div class="res"', f'<div class="res"{hide("wait")}', 1)
            + result("ok", ok_h, ok_p, '<p class="note">You can close this tab.</p>'
                     ).replace('<div class="res"', f'<div class="res"{hide("ok")}', 1)
            + result("bad", bad_h, bad_p, f'<a class="btn pri" href="/?t={html.escape(token)}">'
                     'Try another key</a>').replace('<div class="res"', f'<div class="res"{hide("bad")}', 1))
    return _page("Sent", body + f"""
<script>const t={t};let n=0;
function show(id,s){{for(const k of ['wait','ok','bad'])document.getElementById(k).hidden=k!==id;
 const i=s.indexOf('. ');document.getElementById(id+'h').textContent=(i<0?s:s.slice(0,i)).replace(/[.]$/,'');
 document.getElementById(id+'p').textContent=i<0?'':s.slice(i+2);}}
function poll(){{fetch('/status?t='+encodeURIComponent(t)).then(r=>r.ok?r.json():null).then(j=>{{
 const s=(j&&j.status)||'';
 if(/^Connected/.test(s))return show('ok',s);
 if(/rejected|can't reach/i.test(s))return show('bad',s);
 if(++n<40)setTimeout(poll,1500);}}).catch(()=>{{if(++n<40)setTimeout(poll,1500)}})}}
poll()</script>""", heading=False)
