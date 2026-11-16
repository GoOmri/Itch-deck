"""Error codes (16 Nov, instead of Details): no hint the player can act on -> a short code on
screen and the same code on its own line in the log. Every code used is listed once."""
import logging
import re
from pathlib import Path

from itch_deck import words

SRC = Path(__file__).resolve().parent.parent / "itch_deck"


def test_every_code_used_is_listed_and_every_listed_code_is_used():
    used = set()
    for f in SRC.rglob("*.py"):
        if f.name == "words.py":
            continue
        used |= set(re.findall(r'"([IWPLEUSM]\d\d)"', f.read_text()))
    assert used == set(words.CODES), (used ^ set(words.CODES))
    assert all(re.fullmatch(r"[IWPLEUSM]\d\d", c) for c in words.CODES)


def test_no_screen_text_mentions_the_log():
    for f in SRC.rglob("*.py"):
        assert "Details are in the log" not in f.read_text(), f.name


def test_coded_error_and_display(caplog):
    e = words.Coded("The installer stopped with an error.", "W09")
    assert e.code == "W09" and str(e) == "The installer stopped with an error."
    assert words.with_code("Couldn't refresh the library.", "L01") == \
        "Couldn't refresh the library · Code L01"
    with caplog.at_level(logging.INFO, logger="scritch"):
        words.log_code("W09", "install 5: stopped")
    assert "ERROR CODE W09: install 5: stopped" in caplog.text
    try:
        words.Coded("x", "Z99")
    except AssertionError:
        pass
    else:
        raise AssertionError("unknown code accepted")


def test_install_failure_shows_hint_or_code(caplog):
    """installer._fail: a hint the player can act on wins; otherwise the code (I01 if none)."""
    from itch_deck.installer import Installer
    upd = {}
    fake = type("F", (), {"index": {}, "events": [], "updating": set(),
                          "_upd": lambda self, gid, **k: upd.update(k)})()
    with caplog.at_level(logging.INFO, logger="scritch"):
        Installer._fail(fake, "5", "Quiet Quarry", "Not enough space on the SD card.", "W09")
        assert upd["fail_reason"] == "Not enough space" and "ERROR CODE" not in caplog.text
        Installer._fail(fake, "5", "Quiet Quarry", "The installer stopped with an error.", "W09")
        assert upd["fail_reason"] == "Code W09" and "ERROR CODE W09" in caplog.text
        Installer._fail(fake, "5", "Quiet Quarry", "Something went wrong (KeyError: 'x').")
        assert upd["fail_reason"] == "Code I01" and "ERROR CODE I01" in caplog.text


def test_epic_no_internet_is_a_hint_not_a_code():
    assert words.short("Couldn't install: No internet.") == "No internet"
