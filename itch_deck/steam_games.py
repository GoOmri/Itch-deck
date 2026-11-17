"""Add to Steam, per game (v0.9.21, Omri 17 Nov): Options -> "Add to Steam" makes a Steam shortcut for ONE game
that starts SCRiTCH with `--play <game id>` (SCRiTCH then plays that game and exits, so Steam shows its own
screen again), with the game's cover as the tile. "Remove from Steam" takes it out again.

What the Deck experiment (17 Nov) showed: a shortcut written into config/shortcuts.vdf while Steam is running
is NOT seen until Steam restarts, it survives Steam's exit, and removing it from the file while Steam runs
sticks (Steam does not write its memory copy back). So adding and removing take effect on the next Steam
restart, and nothing needs Steam to be closed. The controller layout is left to Steam.

Safety: only shortcuts tagged "SCRiTCH" with this game's launch options are ever added or removed; the file
is backed up before every write (steam_shortcuts.py); art is never written over a picture that is already
there (any extension), and only art SCRiTCH made is removed again."""
import json
import logging
import os
import re
import zlib
from pathlib import Path

from . import paths, steam_art
from . import steam_shortcuts as SS

log = logging.getLogger("scritch")

ID_OK = re.compile(r"^[A-Za-z0-9._-]{1,80}$")       # goes into Steam's launch options: plain characters only
ART = (("p", (600, 900)), ("", (920, 430)), ("_hero", (1920, 620)))     # <appid>p tile, <appid> wide, hero


def record_file():
    return paths.DATA / "steam_games.json"


def _record():
    try:
        d = json.loads(record_file().read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_record(d):
    try:
        record_file().parent.mkdir(parents=True, exist_ok=True)
        record_file().write_text(json.dumps(d, indent=1))
    except OSError as e:
        log.info("steam games: can't save %s: %s", record_file(), e)


def launch_options(gid):
    return f"--play {gid}"


def files(roots=None):
    """Every Steam user's shortcuts.vdf whose userdata folder exists."""
    return SS.shortcut_files(roots if roots is not None else steam_art.steam_roots())


def available(launcher, roots=None):
    """Add to Steam makes sense: a real build (a launcher file) and a Steam user folder."""
    return bool(launcher) and bool(files(roots))


def _mine(entry, gid):
    return SS.TAG in SS.tags_of(entry) and SS._field(entry, "LaunchOptions") == launch_options(gid)


def is_added(gid, roots=None):
    for f in files(roots):
        try:
            if any(_mine(e, gid) for _k, e in SS.shortcuts_of(SS.read_file(f))):
                return True
        except (OSError, ValueError, IndexError):
            continue
    return False


def _unique_name(tree, title, exe):
    """Two shortcuts with the same name and file get the same Steam id: add a number if needed."""
    taken = {(SS._field(e, "AppName"), SS._field(e, "Exe")) for _k, e in SS.shortcuts_of(tree)}
    name, n = title, 1
    while (name, f'"{exe}"') in taken:
        n += 1
        name = f"{title} ({n})"
    return name


# --- art ---------------------------------------------------------------------------------------------
def _fit(pg, img, box, fill=False):
    """img scaled to fit inside (or, fill=True, to cover) the box, keeping its shape."""
    w, h = img.get_size()
    k = (max if fill else min)(box[0] / w, box[1] / h)
    return pg.transform.smoothscale(img, (max(1, int(w * k)), max(1, int(h * k))))


def compose(pg, cover, title, size):
    """One art picture: the cover (when there is one) over a darkened, blurred copy of itself, or a plain
    title card when the game has no cover."""
    W, H = size
    surf = pg.Surface((W, H))
    img = None
    if cover:
        try:
            img = pg.image.load(str(cover))
        except (pg.error, OSError, FileNotFoundError):
            img = None
    if img is not None:
        bg = _fit(pg, img, (W, H), fill=True)
        small = pg.transform.smoothscale(bg, (max(1, bg.get_width() // 16), max(1, bg.get_height() // 16)))
        bg = pg.transform.smoothscale(small, bg.get_size())                  # cheap blur
        surf.blit(bg, ((W - bg.get_width()) // 2, (H - bg.get_height()) // 2))
        shade = pg.Surface((W, H), pg.SRCALPHA)
        shade.fill((8, 8, 20, 150))
        surf.blit(shade, (0, 0))
        fg = _fit(pg, img, (int(W * 0.96), int(H * 0.96)))
        surf.blit(fg, ((W - fg.get_width()) // 2, (H - fg.get_height()) // 2))
        return surf
    hue = zlib.crc32(title.encode("utf-8")) % 360                              # a plain title card
    col = pg.Color(0)
    col.hsva = (hue, 45, 38, 100)
    surf.fill(col)
    pg.font.init()
    words = title.split()
    for px in range(max(24, H // 7), 19, -4):                   # the biggest type in which the whole title fits
        font = pg.font.Font(None, px)
        lines, cur = [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if font.size(t)[0] <= W * 0.86 or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) * font.get_linesize() <= H * 0.7 and all(font.size(ln)[0] <= W * 0.9 for ln in lines):
            break
    y = (H - len(lines) * font.get_linesize()) // 2
    for ln in lines:
        img = font.render(ln, True, (240, 240, 244))
        surf.blit(img, ((W - img.get_width()) // 2, y))
        y += font.get_linesize()
    return surf


def write_art(pg, grid, appid, cover, title):
    """Cover art as Steam names it, never over a picture that exists. Returns the file names written."""
    written = []
    grid.mkdir(parents=True, exist_ok=True)
    for suffix, size in ART:
        stem = f"{appid}{suffix}"
        if steam_art._exists(grid, stem):
            continue
        tmp = grid / (stem + ".png.scritch-tmp.png")
        pg.image.save(compose(pg, cover, title, size), str(tmp))
        os.replace(tmp, grid / (stem + ".png"))
        written.append(stem + ".png")
    return written


# --- add / remove ----------------------------------------------------------------------------------------
def add(g, launcher, roots=None, pg=None):
    """Add a shortcut for game g to every Steam user. Returns True when it is in Steam's file(s) now
    (already there counts). Raises ValueError for a game id that isn't safe, OSError when a file can't be
    written. pg = pygame, for the art (None: no art)."""
    gid = g["id"]
    if not ID_OK.match(gid or ""):
        raise ValueError(f"game id {gid!r} can't go into Steam's launch options")
    fs = files(roots)
    if not fs or not launcher:
        return False
    rec, did = _record(), False
    for f in fs:
        tree = SS.read_file(f)
        if any(_mine(e, gid) for _k, e in SS.shortcuts_of(tree)):
            did = True
            continue
        name = _unique_name(tree, g.get("title") or gid, str(launcher))
        entry = SS.make_entry(name, str(launcher), str(Path(launcher).parent), launch_options(gid))
        SS.add_shortcut(tree, entry)
        SS.write_file(f, tree)                     # the whole read-modify-write takes milliseconds
        appid = SS._field(entry, "appid") & 0xFFFFFFFF
        did = True
        user = f.parent.parent
        art = []
        if pg is not None:
            try:
                art = write_art(pg, user / "config" / "grid", appid, g.get("cover_file"), g.get("title") or gid)
            except Exception:  # noqa: BLE001  - the shortcut is in; the art is a bonus
                log.exception("steam games: art for %s failed", gid)
        rec.setdefault(gid, {}).setdefault("users", {})[user.name] = {"appid": appid, "art": art}
        log.info("steam games: added %s to %s (appid %d, art %s)", gid, user.name, appid, art)
    _save_record(rec)
    return did


def remove(gid, roots=None):
    """Remove game gid's shortcut (ours only) and the art SCRiTCH made for it. Returns how many shortcuts
    were removed (0: there was none)."""
    fs = files(roots)
    n, rec = 0, _record()
    for f in fs:
        tree = SS.read_file(f)
        gone = SS.remove_shortcuts(tree, SS.TAG, match=lambda e: _mine(e, gid))
        if gone:
            SS.write_file(f, tree)
            n += gone
    for user, info in (rec.pop(gid, {}).get("users") or {}).items():
        for r in (roots if roots is not None else steam_art.steam_roots()):
            grid = Path(r) / "userdata" / user / "config" / "grid"
            for name in info.get("art") or []:
                try:
                    (grid / name).unlink()
                except OSError:
                    pass
    _save_record(rec)
    log.info("steam games: removed %s (%d shortcut(s))", gid, n)
    return n
