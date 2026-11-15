"""Phone login page (v0.7): one-time password, expiry, the key reaching the app."""
import json
import urllib.error
import urllib.parse
import urllib.request

import pytest

from itch_deck import phonelink
from itch_deck.app_setup import key_from_text


@pytest.fixture
def link(monkeypatch):
    monkeypatch.setattr(phonelink, "lan_ip", lambda: "127.0.0.1")
    got = []
    p = phonelink.PhoneLink("itch", got.append, lambda: "Checking it on your Deck…")
    assert p.start()
    p.got = got
    yield p
    p.stop()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post(p, token, text):
    base = p.url.split("/?")[0]
    data = urllib.parse.urlencode({"t": token, "text": text}).encode()
    try:
        with urllib.request.urlopen(base + "/send", data=data, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_page_needs_the_one_time_password(link):
    base = link.url.split("/?")[0]
    assert _get(link.url)[0] == 200 and "Open itch API keys" in _get(link.url)[1]
    assert _get(base + "/")[0] == 403
    assert _get(base + "/?t=wrong")[0] == 403
    code, body = _get(base + "/status?t=" + link.token)
    assert code == 200 and json.loads(body)["status"].startswith("Checking")


def test_key_reaches_the_app(link):
    code, body = _post(link, link.token, "  key: AbCdEf0123456789abcdefABCDEF0123456789xy \n")
    assert code == 200 and "Checking it on your Deck" in body and "You can close this tab" in body
    assert link.got and key_from_text(link.got[0]) == "AbCdEf0123456789abcdefABCDEF0123456789xy"
    assert _post(link, "wrong", "x" * 40)[0] == 403
    assert len(link.got) == 1


def test_password_expires(link, monkeypatch):
    old_url = link.url
    monkeypatch.setattr(phonelink, "TTL", 0)
    assert _get(old_url)[0] == 403                # out of time: refused
    monkeypatch.setattr(phonelink, "TTL", 300)
    assert link.tick() is False                   # still within the (restored) TTL
    link.born -= 301
    assert link.tick() is True and link.url != old_url   # new password -> new QR
    assert _get(old_url)[0] == 403 and _get(link.url)[0] == 200


def test_big_or_empty_posts(link):
    assert _post(link, link.token, "x" * 9000)[0] == 400
    code, body = _post(link, link.token, "   ")
    assert code == 200 and "Nothing was pasted" in body and not link.got


def test_qr_matrix(link):
    m = link.qr()
    assert m and len(m) == len(m[0]) >= 21


def test_key_from_text():
    assert key_from_text("abc") == "abc"
    assert key_from_text("Your key:\nZZZZZZZZZZZZZZZZZZZZ (copied)") == "ZZZZZZZZZZZZZZZZZZZZ"
