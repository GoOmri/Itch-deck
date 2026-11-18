"""app.log never holds a token or sign-in code, even when a helper (legendary, gogdl) prints one in an error."""
import io
import logging

from itch_deck import app, logshare


def test_secrets_are_hidden_but_debug_text_stays():
    s = logshare.scrub_secrets
    assert "abc123xyz789" not in s("legendary auth: code=abc123xyz789 failed")
    assert "abcdef123456" not in s("Authorization: Bearer abcdef123456")
    assert "SECRETVALUE99" not in s("GET https://x/y?token=SECRETVALUE99&a=1")
    assert "abcdEFGH12345" not in s("refresh_token: 'abcdEFGH12345'")
    assert "xyz" not in s("gogdl --auth-code xyz9999 auth")
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123"
    assert jwt not in s("got " + jwt)
    # what the debugging needs stays readable
    for keep in ("play: blood exited 0 after 5s", "ERROR CODE P01: game closed after 1 s, exit 0",
                 "exit code: 0", "dosart dos-doom-fe046a: DOOM + DOOM II (1317223010, score 66)",
                 "/run/media/deck/9273cb7b/itch/dos/DOS/Blood (1997)(Monolith)"):
        assert s(keep) == keep


def test_the_log_formatter_hides_secrets_in_messages_and_tracebacks():
    stream = io.StringIO()
    h = logging.StreamHandler(stream)
    h.setFormatter(app.SecretFreeFormatter("%(levelname)s %(message)s"))
    lg = logging.getLogger("scritch.test_scrub")
    lg.setLevel(logging.INFO)
    lg.propagate = False
    lg.addHandler(h)
    try:
        lg.info("epic: legendary auth -> 1\n  error: invalid code=SECRETCODE12345")
        try:
            raise RuntimeError("refresh_token=LEAKEDTOKEN987 was rejected")
        except RuntimeError:
            lg.exception("sign-in failed")
    finally:
        lg.removeHandler(h)
    out = stream.getvalue()
    assert "SECRETCODE12345" not in out and "LEAKEDTOKEN987" not in out
    assert "legendary auth -> 1" in out and "sign-in failed" in out and "RuntimeError" in out


def test_formatter_never_raises(monkeypatch):
    def boom(text):
        raise ValueError("x")
    monkeypatch.setattr(logshare, "scrub_secrets", boom)
    rec = logging.LogRecord("scritch", logging.INFO, __file__, 1, "plain line", None, None)
    assert app.SecretFreeFormatter("%(message)s").format(rec) == "plain line"
