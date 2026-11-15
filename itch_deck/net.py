"""Tiny HTTP layer (urllib). Bundled CA certs, so HTTPS works from the PyInstaller binary."""
import json
import socket
import ssl
import urllib.error
import urllib.request

UA = "scritch (+https://github.com/GoOmri/Itch-deck)"


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


def get(url, key=None, timeout=20, accept=None, headers=None, data=None):
    """GET (or POST when data is given). headers override the defaults."""
    global _CTX
    _CTX = _CTX or _ctx()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
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


class Cancelled(Exception):
    """The user cancelled a download."""


def download(url, dest, progress=None, timeout=30, key=None, resume=False, cancel=None,
             on_bytes=None):
    """Stream url to dest (via dest.part). progress(frac) and on_bytes(done, total) are called as
    it goes. resume=True continues an existing .part with a Range request. key goes in an
    unredirected header (never sent on to a CDN). cancel() -> True stops with Cancelled."""
    global _CTX
    _CTX = _CTX or _ctx()
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if resume and part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if key:
        req.add_unredirected_header("Authorization", f"Bearer {key}")
    if have:
        req.add_header("Range", f"bytes={have}-")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            if have and r.status != 206:          # server ignored Range: start over
                have = 0
            total = int(r.headers.get("Content-Length") or 0)
            total, done = (total + have if total else 0), have
            with open(part, "ab" if have else "wb") as f:
                while True:
                    if cancel and cancel():
                        raise Cancelled()
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress and total:
                        progress(done / total)
                    if on_bytes:
                        on_bytes(done, total)
            if total and done < total:
                raise Offline(f"connection dropped at {done}/{total} bytes")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403) and key:
            raise AuthError(f"HTTP {e.code}") from None
        if e.code == 416 and have:                # .part already complete / stale: restart
            part.unlink(missing_ok=True)
            return download(url, dest, progress, timeout, key, False, cancel, on_bytes)
        if e.code in (404, 410):
            raise NotFound(f"HTTP {e.code}") from None
        raise Offline(f"HTTP {e.code}") from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError) as e:
        raise Offline(type(e).__name__) from None
    part.replace(dest)
