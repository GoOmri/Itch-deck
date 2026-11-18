"""A DOS summary for Send logs (v0.9.29): one line per own DOS game, so nobody has to describe their games by
hand. Clean title, the program in use, the programs found (names inside the game folder only, never a full
path), the GOG / Steam match (or "no match"), how old that answer is, and the last play result read from app.log.
Everything goes through logshare.scrub() like the logs. Pure: it is given the data, it reads nothing itself."""
import datetime as dt
import os
import re

from . import logshare
from .installer import slug_of

SHORT_GAMES = 40            # the short version (Copy the text / the issue) lists this many games
PLAYED = re.compile(r"play: (\S+) exited (\S+) after (\d+)s")


def _rel(p):
    """A name inside the game's folder. A full path (should never be there) is cut down to its file name."""
    p = str(p or "").replace("\\", "/")
    return os.path.basename(p) if p.startswith("/") or re.match(r"^[A-Za-z]:/", p) else p


def last_plays(app_log_text):
    """slug -> (exit code, seconds) of the LAST "play: <slug> exited N after Ns" line."""
    out = {}
    for m in PLAYED.finditer(app_log_text or ""):
        out[m.group(1)] = (m.group(2), int(m.group(3)))
    return out


def _age(entry, now):
    try:
        d = now - dt.datetime.fromisoformat(entry["at"])
        return f"{d.days} day{'' if d.days == 1 else 's'} ago" if d.days else "today"
    except (KeyError, TypeError, ValueError):
        return "never"


def _keys(entry):
    """What the game's own text files gave (dosinput.py): "from README.TXT (4 actions)" or "none found"."""
    r = (entry or {}).get("result") or {}
    return f"from {_rel(r.get('source'))} ({r.get('actions')} actions)" if r.get("map") else \
        ("none found" if entry else "not read yet")


def lines(games, index, cache, app_log_text, now=None, inputs=None):
    """[(full line, short line)] for every own DOS game, sorted by title."""
    now = now or dt.datetime.now().astimezone()
    plays = last_plays(app_log_text)
    out = []
    for g in sorted((x for x in games if x.get("store") == "dos"), key=lambda x: str(x.get("title")).lower()):
        info = index.get(g["id"]) or {}
        entry = (cache or {}).get(g["id"]) or {}
        m = entry.get("match")
        if m:
            how = f"{m.get('title')} ({m.get('source') or 'gog'}, score {m.get('score')}" + \
                  (", art only" if m.get("fallback") else "") + ")"
        else:
            how = "no match" if entry else "not asked yet"
        rc = plays.get(slug_of(g))
        last = f"{rc[1]} s, exit {rc[0]}" if rc else "not played"
        exe = _rel(info.get("exe"))
        progs = [exe] + [_rel(a) for a in info.get("alternatives") or [] if _rel(a) != exe] if exe else []
        full = (f"- {g.get('title')} | program: {exe or '-'} | programs: {', '.join(progs) or '-'} | "
                f"setups: {', '.join(_rel(x) for x in info.get('setups') or []) or '-'} | match: {how} | "
                f"asked {_age(entry, now)} | keys: {_keys((inputs or {}).get(g['id']))} | last play: {last}")
        short = f"- {g.get('title')} | {exe or '-'} | {how} | {last}"
        out.append((full, short))
    return out


def build(games, index, cache, app_log_text, now=None, inputs=None):
    """(the full text for dos-summary.txt, the short text for the pasted report), both cleaned."""
    rows = lines(games, index, cache, app_log_text, now, inputs)
    if not rows:
        return "", ""
    full = "Own DOS games: %d\n" % len(rows) + "\n".join(r[0] for r in rows)
    short = "Own DOS games: %d%s\n" % (len(rows), "" if len(rows) <= SHORT_GAMES else f" (first {SHORT_GAMES})") + \
        "\n".join(r[1] for r in rows[:SHORT_GAMES])
    return logshare.scrub(full), logshare.scrub(short)
