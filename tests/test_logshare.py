"""Send your logs (v0.9.15): what leaves the Deck is cleaned first (reports go into PUBLIC GitHub
issues), the short report is small, and the phone page serves it only with the one-time password."""
import io
import urllib.error
import urllib.request
import zipfile

import pytest

from itch_deck import logshare, paths, phonelink

# Real shapes from the Deck logs of 16-17 Nov (names, ids and keys changed to made-up ones).
SECRETS = {
    "Authorization: Bearer abcDEF123456xyzSECRET": "abcDEF123456xyzSECRET",
    'refresh {"access_token": "AbCdEfGh1234567890Zz", "refresh_token":"zzzzSECRETzzzz9999"}':
        "SECRETzzzz9999",
    "phone page http://192.168.1.23:41234/?t=Xk3jQ9aLm2wSECRET": "Xk3jQ9aLm2wSECRET",
    "gog: connected as SomeUser123": "SomeUser123",
    "mail me at someone@example.com please": "someone@example.com",
    "api_key=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd": "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd",
    "the key is AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd here": "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd",
    "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.SflKxwRJSMeKKF2QT4fwpM": "eyJhbGciOiJIUzI1NiJ9",
    "egl_parameters = ['-AUTH_PASSWORD=hunter22']": "hunter22",
    "path /run/media/deck/9273cb7b-3106-41c2-9a2d-6bf4ea2730fb/itch/game": "9273cb7b",
    "path /home/someuser/.local/share/scritch": "someuser",
    "/DIR=Z:" + chr(92) + "run" + chr(92) + "media" + chr(92) + "deck" + chr(92) + "9273cb7b-3106": "9273cb7b",
    "lan 10.0.0.7 and 8.8.4.4": "10.0.0.7",
    # found by the reviewer (17 Nov): names with spaces, other separators, camelCase, flags, ids
    'legendary: logged in as "Omri Cohen"': "Cohen",
    "logged in as: omri": "omri",
    "Username = omri": "omri",
    '{"access_token":"abc def ghi"}': "def ghi",
    "sessionToken=abc123xyz": "abc123xyz",
    "authorizationCode=abcdef": "abcdef",
    "passphrase=hunter2": "hunter2",
    "cmd --auth-code abc123SECRET --token tok999": "abc123SECRET",
    "cmd --exchange-token xyz777": "xyz777",
    "/home/x/.local/share/Steam/userdata/123456789/config": "123456789",
    "steam 76561198012345678 here": "76561198012345678",
    "token expired for user 48628349": "48628349",
    "/media/someone/disk/x": "someone",
    "/mnt/bob/x": "bob",
    "Z:" + chr(92) + "Users" + chr(92) + "bob" + chr(92) + "Documents": "bob",
}


@pytest.mark.parametrize("line,secret", list(SECRETS.items()))
def test_secrets_and_personal_details_are_hidden(line, secret):
    out = logshare.scrub(line)
    assert secret not in out, out


def test_normal_log_lines_stay_readable():
    for line in ("pad added: 'Steam Deck Controller' guid=0300b836 -> deck",
                 "ERROR CODE P03: gog-1432575012 (Eye of the Beholder) closed after 1 s, exit 0",
                 "install gog-1: done in 12s -> <sd>/itch/eye-of-the-beholder (exe DOSBOX/DOSBox.exe)",
                 "dosbox: commands ['mount c ..', 'c:', 'start.exe']",
                 "code received (12 chars) after exit code 0"):
        assert logshare.scrub(line) == line, logshare.scrub(line)
    assert "~/.local" in logshare.scrub("/home/deck/.local/share/x")
    assert "<sd>/itch" in logshare.scrub("/run/media/deck/9273cb7b-3106/itch")


@pytest.fixture
def logs(tmp_path):
    paths.use_root(tmp_path / "home")
    d = paths.LOGS
    (d / "games").mkdir(parents=True)
    body = "\n".join(f"2026-11-17 14:0{i % 10} INFO line {i}" for i in range(400))
    (d / "app.log").write_text(body + "\ngog: connected as SomeUser123\n"
                               "ERROR: ld.so: object '/home/deck/.local/share/Steam/steamrt32/"
                               "gameoverlayrenderer.so' from LD_PRELOAD cannot be preloaded\n")
    (d / "games" / "old.log").write_text("old game\n")
    (d / "games" / "eye.log").write_text("# started\nDOSBox says hello\nBearer SECRETSECRET99\n")
    import os
    os.utime(d / "games" / "old.log", (1, 1))
    return d


def test_report_is_short_clean_and_has_the_newest_game_log(logs):
    text = logshare.report("0.9.15")
    assert text.startswith("SCRiTCH 0.9.15")
    assert "line 399" in text and "line 100" not in text         # only the last lines
    assert "SomeUser123" not in text and "SECRETSECRET99" not in text
    assert "gameoverlayrenderer" not in text                      # Steam's warning is noise
    assert "DOSBox says hello" in text and "old game" not in text
    assert len(text) <= logshare.REPORT_CHARS + 50


def test_report_keeps_the_end_when_too_long(logs):
    (logs / "app.log").write_text("\n".join("x" * 400 + str(i) for i in range(500)))
    text = logshare.report("0.9.15", app_lines=500)
    assert len(text) <= logshare.REPORT_CHARS + 50 and "x" * 400 + "499" in text
    assert text.startswith("SCRiTCH 0.9.15") and "older lines left out" in text


def test_zip_holds_every_log_cleaned(logs):
    z = zipfile.ZipFile(io.BytesIO(logshare.zip_bytes("0.9.15")))
    names = z.namelist()
    assert {"about.txt", "app.log", "games/eye.log", "games/old.log"} <= set(names)
    everything = "".join(z.read(n).decode() for n in names)
    assert "SomeUser123" not in everything and "SECRETSECRET99" not in everything


def test_save_zip_goes_to_documents(logs):
    import datetime as dt
    f = logshare.save_zip("0.9.15", dt.datetime(2026, 11, 17, 14, 5))
    assert f.parent == paths.HOME / "Documents" / "SCRiTCH logs"
    assert f.name == "scritch-logs-2026-11-17-1405.zip" and zipfile.is_zipfile(f)


def test_issue_link_is_prefilled():
    url = logshare.issue_url("0.9.15")
    assert url.startswith("https://github.com/GoOmri/Itch-deck/issues/new?")
    assert "template=bug_report.yml" in url and "version=0.9.15" in url


class _Logs:
    zip_name = "scritch-logs.zip"

    def report(self):
        return "SCRiTCH 0.9.15\n<b>not html</b> & Bearer-free"

    def zip(self):
        return b"PK-fake-zip"

    def issue(self):
        return "https://github.com/GoOmri/Itch-deck/issues/new?template=bug_report.yml&version=0.9.15"


@pytest.fixture
def link(monkeypatch):
    monkeypatch.setattr(phonelink, "lan_ip", lambda: "127.0.0.1")
    p = phonelink.PhoneLink("logs", lambda t: None)
    p.logs = _Logs()
    assert p.start()
    yield p
    p.stop()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def test_phone_page_shows_report_copy_issue_and_zip(link):
    code, body, _ = _get(link.url)
    page = body.decode()
    assert code == 200 and "Copy the text" in page and "Open a GitHub issue" in page
    assert "&lt;b&gt;not html&lt;/b&gt;" in page and "<b>not html</b>" not in page   # escaped
    assert "execCommand" in page                                   # works on plain http too
    code, data, hdr = _get(link.url.split("?")[0] + "zip?t=" + link.token)
    assert code == 200 and data == b"PK-fake-zip" and hdr["Content-Type"] == "application/zip"
    assert "attachment" in hdr["Content-Disposition"]


def test_phone_logs_need_the_one_time_password(link):
    base = link.url.split("?")[0]
    assert _get(base)[0] == 403
    assert _get(base + "zip")[0] == 403
    assert _get(base + "zip?t=wrong")[0] == 403
    assert _get(base + "?t=wrong")[0] == 403


def test_a_huge_line_does_not_make_cleaning_slow():
    import time
    t0 = time.time()
    out = logshare.scrub("A" * 60000 + "\n" + "x" * 50 + "\n")
    assert time.time() - t0 < 3 and "long line cut" in out and len(out) < 3000


def test_a_game_called_2048_is_still_the_latest_game_log(logs):
    (logs / "games" / "2048.log").write_text("2048 output\n")
    (logs / "games" / "eye.1.log").write_text("older run\n")        # a rotated log is skipped
    import os, time
    os.utime(logs / "games" / "2048.log", (time.time() + 5, time.time() + 5))
    text = logshare.report("0.9.15")
    assert "2048 output" in text and "older run" not in text


def test_the_logs_link_takes_no_posts(link):
    import urllib.parse
    data = urllib.parse.urlencode({"t": link.token, "text": "hello"}).encode()
    base = link.url.split("?")[0]
    try:
        urllib.request.urlopen(base + "send", data=data, timeout=5)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 400
