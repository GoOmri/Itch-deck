"""Tiny HTTP layer (urllib). Bundled CA certs, so HTTPS works from the PyInstaller binary."""
import json
import socket
import ssl
import urllib.error
import urllib.request

UA = "itch-deck (+https://github.com/GoOmri/itch-deck)"


class Offline(Exception):
    """Network unreachable / timed out / server error."""


class NotFound(Exception):
    """HTTP 404: the page/file is gone. Not a network problem, don't retry."""


class AuthError(Exception):
    """itch rejected the API key."""


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


_CTX = None


def get(url, key=None, timeout=20, accept=None):
    global _CTX
    _CTX = _CTX or _ctx()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    if accept:
        req.add_header("Accept", accept)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403) and key:
            raise AuthError(f"HTTP {e.code}") from None
        if e.code in (404, 410):
            raise NotFound(f"HTTP {e.code}") from None
        raise Offline(f"HTTP {e.code}") from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError) as e:
        raise Offline(type(e).__name__ + ": " + str(getattr(e, "reason", e))) from None


def get_json(url, key=None, timeout=20):
    data = json.loads(get(url, key, timeout, accept="application/json"))
    errs = data.get("errors") if isinstance(data, dict) else None
    if errs:
        msg = " ".join(map(str, errs))
        if "key" in msg.lower() or "auth" in msg.lower():
            raise AuthError(msg)
        raise Offline(msg)
    return data
