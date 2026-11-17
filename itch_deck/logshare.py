"""Send your logs (v0.9.15): a short, cleaned piece of the logs for pasting into a GitHub issue,
and a full cleaned zip, both served to the phone by phonelink.

Safety first: reports end up in PUBLIC issues. Nothing is uploaded by the app. Everything goes through
scrub() before it leaves the logs: secrets (tokens, keys, sign-in codes), e-mail addresses, the
Deck's user name and folders, the SD card's id, network addresses and account names are hidden. The
phone page shows the text before anyone copies it. The short report holds only the last lines."""
import io
import logging
import os
import re
import zipfile
from pathlib import Path

from . import paths

log = logging.getLogger("scritch")

REPORT_LINES = 150           # last app.log lines in the short report
GAME_LINES = 40              # last lines of the most recent game's log
REPORT_CHARS = 30_000        # a GitHub issue holds ~65,000; stay well under
ZIP_FILE_BYTES = 2_000_000   # per file in the zip (the end of each log)
HIDDEN = "<hidden>"

_SECRET_WORDS = (r"access[_-]?token|refresh[_-]?token|id[_-]?token|token|api[_-]?key|apikey|key|"
                 r"password|passwd|passphrase|pwd|secret|code|session|sid|sess|authorization|auth|"
                 r"cookie|exchange[_-]?code|egl[_-]?parameters?|bearer|credentials?|signature|sig")
_VALUE = r"(?:\"[^\"]*\"|'[^']*'|[^\s\"',&;)}\]]{2,})"       # a quoted string (spaces and all) or a word
_NAME = r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
_RULES = [
    # "Authorization: Bearer abc", "Bearer abc"
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]{6,}"), r"\1 " + HIDDEN),
    # key=value, key: value, "key": "value", camelCase keys too (sessionToken=...)
    (re.compile(r"(?i)(" + _SECRET_WORDS + r")([\"']?\s*[:=]\s*)" + _VALUE), r"\1\2" + HIDDEN),
    # command-line flags with a space: --auth-code abc, -token abc
    (re.compile(r"(?i)(--?(?:auth[_-]?code|exchange[_-]?token|refresh[_-]?token|token|password|"
                r"api[_-]?key|secret|code)\s+)\S+"), r"\1" + HIDDEN),
    # one-time codes and tokens in a URL query
    (re.compile(r"(?i)([?&](?:t|token|code|key|api_key|access_token|sid)=)[^&\s\"']+"),
     r"\1" + HIDDEN),
    # JSON web tokens
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-.]+"), HIDDEN),
    # mixed-case letters + digits, 32+ long: a key. (Plain hex hashes in file names stay.)
    (re.compile(r"\b(?=[A-Za-z0-9_\-]*[a-z])(?=[A-Za-z0-9_\-]*[A-Z])(?=[A-Za-z0-9_\-]*\d)"
                r"[A-Za-z0-9_\-]{32,}\b"), HIDDEN),
    # account names: logged in as "Omri Cohen", connected as X, user: X, username = X
    (re.compile(r"(?i)\b(connected as|signed in as|logged in as|logging in as|login as)\s*[:=]?\s*"
                + _NAME), r"\1 " + HIDDEN),
    (re.compile(r"(?i)\b(user(?:name)?|display[_ ]?name)\s*[:=]\s*" + _NAME), r"\1 " + HIDDEN),
    # numeric account ids: "for user 48628349", Steam's userdata folder, SteamID64
    (re.compile(r"(?i)\b(for user|user[_ ]?id)\s*[:=]?\s*\d{5,}"), r"\1 " + HIDDEN),
    (re.compile(r"/userdata/\d+"), "/userdata/<id>"),
    (re.compile(r"\b7656119\d{10}\b"), "<id>"),
    # e-mail addresses (bounded: a long run of letters must not make the match slow)
    (re.compile(r"[\w.+\-]{1,64}@[\w\-]{1,63}(?:\.[\w\-]{1,63})+"), "<email>"),
    # network addresses (the phone page logs the Deck's LAN address)
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<ip>"),
    # SD card and other mounts: /run/media/<user>/<card id>/..., /media/<user>, /mnt/<user>
    (re.compile(r"/run/media/[^/\s]+/[^/\s]+"), "<sd>"),
    (re.compile(r"\\run\\media\\[^\\\s]+\\[^\\\s]+"), "<sd>"),      # Proton's Z:\run\media\...
    (re.compile(r"/(?:media|mnt)/[^/\s]+"), "<mnt>"),
    # the Deck's user folder and name
    (re.compile(r"/home/[^/\s]+"), "~"),
    (re.compile(r"\\home\\[^\\\s]+"), "~"),
    (re.compile(r"/Users/[^/\s]+"), "~"),
    (re.compile(r"\\Users\\[^\\\s]+"), "~"),
]
MAX_LINE = 2000          # a longer line is cut (base64 / hex dumps are never a useful log line)
NOISE = ("gameoverlayrenderer.so",)       # Steam's overlay preload warning, printed on every run


def scrub(text):
    """The text with secrets and personal details hidden, line by line. A line over MAX_LINE
    characters is cut (and a long line could make a pattern slow). (The user name is hidden through
    the folders it sits in: a bare "deck" is also in "Steam Deck", so it isn't replaced on its own.)"""
    out = []
    for line in text.split("\n"):
        if len(line) > MAX_LINE:
            line = line[:MAX_LINE] + " …(long line cut)"
        for rx, rep in _RULES:
            line = rx.sub(rep, line)
        out.append(line)
    return "\n".join(out)


def _tail(path, lines):
    try:
        data = Path(path).read_text(errors="replace")
    except OSError:
        return []
    return [l for l in data.splitlines() if not any(n in l for n in NOISE)][-lines:]


def _rotated(name):
    """slug.1.log / slug.2.log are older runs; "2048.log" is a game called 2048."""
    parts = name.split(".")
    return len(parts) >= 3 and parts[-2].isdigit()


def _latest_game_log():
    d = paths.LOGS / "games"
    try:
        logs = [p for p in d.glob("*.log") if p.is_file() and not p.name.endswith("-install.log")
                and not p.name.endswith("-setup.log") and not _rotated(p.name)]
        return max(logs, key=lambda p: p.stat().st_mtime) if logs else None
    except (OSError, ValueError):
        return None


def system_line():
    """SteamOS / distro name from /etc/os-release, or ''."""
    try:
        for l in Path("/etc/os-release").read_text().splitlines():
            if l.startswith("PRETTY_NAME="):
                return l.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def report(version, app_lines=REPORT_LINES, game_lines=GAME_LINES):
    """The short text for a GitHub issue: version, system, the last app.log lines and the end of
    the most recent game's log, all through scrub(). At most REPORT_CHARS (the END is kept)."""
    head = f"SCRiTCH {version}\nSystem: {system_line() or 'unknown'}\n\n"
    app = _tail(paths.LOGS / "app.log", app_lines)
    parts = ["--- app.log (last lines) ---"] + (app or ["(empty)"])
    g = _latest_game_log()
    if g:
        parts += ["", f"--- game log: {g.name} (last lines) ---"] + (_tail(g, game_lines) or ["(empty)"])
    body = scrub("\n".join(parts))
    room = REPORT_CHARS - len(head)
    if len(body) > room:                      # keep the version line; drop the OLDEST lines
        body = "(older lines left out)\n" + body[-room:]
    return scrub(head) + body


def zip_bytes(version):
    """Every log file, cleaned, as one zip (the end of each file when it is big)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("about.txt", scrub(f"SCRiTCH {version}\nSystem: {system_line() or 'unknown'}\n"
                                      "Secrets, e-mail addresses, user name, folders and network "
                                      "addresses are hidden.\n"))
        files = []
        try:
            files = [p for p in paths.LOGS.rglob("*") if p.is_file()]
        except OSError:
            pass
        for p in sorted(files):
            try:
                data = p.read_bytes()[-ZIP_FILE_BYTES:].decode(errors="replace")
            except OSError:
                continue
            z.writestr(p.relative_to(paths.LOGS).as_posix(), scrub(data))
    return buf.getvalue()


def save_zip(version, when):
    """Write the zip to ~/Documents/SCRiTCH logs/ (a visible folder). Returns the path."""
    d = paths.HOME / "Documents" / "SCRiTCH logs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"scritch-logs-{when:%Y-%m-%d-%H%M}.zip"
    f.write_bytes(zip_bytes(version))
    return f


REPO = "GoOmri/Itch-deck"


def issue_url(version):
    """New-issue page of the repo, with the issue form's version and system fields filled in."""
    from urllib.parse import urlencode
    q = urlencode({"template": "bug_report.yml", "version": version,
                   "system": system_line() or "SteamOS"})
    return f"https://github.com/{REPO}/issues/new?{q}"
