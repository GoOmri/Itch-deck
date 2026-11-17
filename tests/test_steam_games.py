"""Add to Steam per game (v0.9.21): a Steam shortcut that starts SCRiTCH with --play <id>, with the game's
cover as its art. Only SCRiTCH's own shortcuts and art are ever added or removed."""
import os
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402
import pytest  # noqa: E402

import sys  # noqa: E402

if os.name == "nt":                                   # mouse.py (imported by app_play) needs Linux's fcntl
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import app_play, paths, steam_art, steam_games  # noqa: E402
from itch_deck import steam_shortcuts as S  # noqa: E402
from test_steam_shortcuts import _raw  # noqa: E402

LAUNCHER = "/home/deck/Applications/scritch/scritch"


@pytest.fixture
def steam(tmp_path):
    paths.use_root(tmp_path / "data")
    user = tmp_path / ".local/share/Steam/userdata/4242"
    (user / "config").mkdir(parents=True)
    (user / "config" / "shortcuts.vdf").write_bytes(_raw())
    pg.init()
    cover = tmp_path / "cover.png"
    surf = pg.Surface((300, 300))
    surf.fill((200, 40, 40))
    pg.image.save(surf, str(cover))
    return types.SimpleNamespace(user=user, roots=steam_art.steam_roots(tmp_path), cover=cover,
                                 vdf=user / "config" / "shortcuts.vdf", grid=user / "config" / "grid")


def _names(steam):
    return [S._field(e, "AppName") for _k, e in S.shortcuts_of(S.read_file(steam.vdf))]


def test_add_makes_one_shortcut_with_the_game_id_and_cover_art(steam):
    g = {"id": "gog-123", "title": "Eye of the Beholder", "cover_file": str(steam.cover)}
    assert not steam_games.available(None, steam.roots) and steam_games.available(LAUNCHER, steam.roots)
    assert steam_games.add(g, LAUNCHER, steam.roots, pg) is True
    entries = dict(S.shortcuts_of(S.read_file(steam.vdf)))
    assert _names(steam) == ["Mine", "Also mine", "Eye of the Beholder"]       # the player's own two are untouched
    e = entries["2"]
    assert S._field(e, "Exe") == f'"{LAUNCHER}"' and S._field(e, "LaunchOptions") == "--play gog-123"
    assert S.tags_of(e) == ["SCRiTCH"] and steam_games.is_added("gog-123", steam.roots)
    appid = S._field(e, "appid") & 0xFFFFFFFF
    made = sorted(p.name for p in steam.grid.iterdir())
    assert made == sorted([f"{appid}p.png", f"{appid}.png", f"{appid}_hero.png"])
    assert pg.image.load(str(steam.grid / f"{appid}p.png")).get_size() == (600, 900)
    assert pg.image.load(str(steam.grid / f"{appid}_hero.png")).get_size() == (1920, 620)
    steam_games.add(g, LAUNCHER, steam.roots, pg)                              # again: no second shortcut
    assert _names(steam).count("Eye of the Beholder") == 1
    assert len(list(steam.vdf.parent.glob("shortcuts.vdf.scritch-backup-*"))) == 1   # one write, one backup


def test_existing_art_is_never_overwritten_and_only_our_art_is_removed(steam):
    g = {"id": "dos-doom-abc123", "title": "Doom", "cover_file": None}          # no cover: a title card
    steam.grid.mkdir(parents=True)
    appid = S.shortcut_appid(f'"{LAUNCHER}"', "Doom")
    (steam.grid / f"{appid}p.jpg").write_bytes(b"the player's own picture")      # another extension counts
    (steam.grid / "999p.png").write_bytes(b"someone else's art")
    assert steam_games.add(g, LAUNCHER, steam.roots, pg)
    assert (steam.grid / f"{appid}p.jpg").read_bytes() == b"the player's own picture"
    assert not (steam.grid / f"{appid}p.png").exists()                           # skipped
    assert (steam.grid / f"{appid}.png").exists() and (steam.grid / f"{appid}_hero.png").exists()
    assert steam_games.remove("dos-doom-abc123", steam.roots) == 1
    assert _names(steam) == ["Mine", "Also mine"]
    assert (steam.grid / f"{appid}p.jpg").exists() and (steam.grid / "999p.png").exists()    # not ours: kept
    assert not (steam.grid / f"{appid}.png").exists() and not (steam.grid / f"{appid}_hero.png").exists()
    assert steam_games.remove("dos-doom-abc123", steam.roots) == 0               # already gone
    assert not steam_games.is_added("dos-doom-abc123", steam.roots)


def test_remove_only_touches_this_games_shortcut(steam):
    for gid, title in (("a-1", "Alpha"), ("b-2", "Beta")):
        steam_games.add({"id": gid, "title": title}, LAUNCHER, steam.roots)
    assert steam_games.remove("a-1", steam.roots) == 1
    assert _names(steam) == ["Mine", "Also mine", "Beta"]
    # a shortcut of the player's that merely starts our launcher by hand is not ours to remove
    tree = S.read_file(steam.vdf)
    S.add_shortcut(tree, S.make_entry("Hand made", LAUNCHER, launch_options="--play a-1", tags=("Favorite",)))
    S.write_file(steam.vdf, tree)
    assert steam_games.remove("a-1", steam.roots) == 0 and "Hand made" in _names(steam)


def test_unsafe_ids_and_missing_pieces_are_refused(steam):
    for bad in ("x; rm -rf ~", "a b", "", "a" * 90, "$(x)"):
        with pytest.raises(ValueError):
            steam_games.add({"id": bad, "title": "T"}, LAUNCHER, steam.roots)
    assert steam_games.add({"id": "ok", "title": "T"}, None, steam.roots) is False         # source run: no launcher
    assert steam_games.add({"id": "ok", "title": "T"}, LAUNCHER, []) is False                # no Steam user folder
    assert _names(steam) == ["Mine", "Also mine"]


def test_two_games_with_one_title_get_different_steam_ids(steam):
    steam_games.add({"id": "g-1", "title": "Twin"}, LAUNCHER, steam.roots)
    steam_games.add({"id": "g-2", "title": "Twin"}, LAUNCHER, steam.roots)
    assert _names(steam)[-2:] == ["Twin", "Twin (2)"]
    ids = {S._field(e, "appid") for _k, e in S.shortcuts_of(S.read_file(steam.vdf))}
    assert len(ids) == 4


def test_scritchs_own_tile_art_does_not_land_on_game_shortcuts(steam):
    tree = S.read_file(steam.vdf)
    S.add_shortcut(tree, S.make_entry("itch", LAUNCHER))                         # the main tile
    S.write_file(steam.vdf, tree)
    steam_games.add({"id": "g-1", "title": "Game"}, LAUNCHER, steam.roots)       # same launcher, --play options
    found = steam_art.find_shortcuts(steam.roots, LAUNCHER)
    assert len(found) == 1                                                        # only the main tile


def test_cover_art_has_steams_sizes(steam):
    for cover in (steam.cover, None):
        for _suffix, size in steam_games.ART:
            assert steam_games.compose(pg, cover, "A Rather Long Game Title That Wraps", size).get_size() == size


def test_autoplay_plays_the_game_or_says_it_is_gone(monkeypatch):
    monkeypatch.setattr(app_play.time, "sleep", lambda s: None)
    calls = []
    pgstub = types.SimpleNamespace(event=types.SimpleNamespace(pump=lambda: None),
                                   display=types.SimpleNamespace(flip=lambda: None))
    me = types.SimpleNamespace(
        autoplay="g-1", pg=pgstub, running=True, screen=None, scene=types.SimpleNamespace(toast=None, draw=lambda s: None),
        lib=types.SimpleNamespace(by_id=lambda gid: {"id": gid, "state": "installed"} if gid == "g-1" else None),
        inst=types.SimpleNamespace(index={"g-1": {"dir": "x"}}),
        play=lambda g: calls.append(("play", g["id"])), _splash=lambda *a: calls.append(("splash", a[0])))
    app_play.PlayMixin._autoplay(me)
    assert calls == [("play", "g-1")] and me.running is False and me.autoplay is None
    calls.clear()
    me.autoplay, me.running = "gone", True
    app_play.PlayMixin._autoplay(me)
    assert ("play", "gone") not in calls and calls[0] == ("splash", "That game isn't installed.")
    assert me.running is False


def test_a_damaged_file_is_a_clean_error_for_is_added_and_add(steam):
    steam.vdf.write_bytes(_raw()[:-12])
    assert steam_games.is_added("g-1", steam.roots) is False          # the Options menu must not crash
    with pytest.raises(ValueError):
        steam_games.add({"id": "g-1", "title": "T"}, LAUNCHER, steam.roots)
    assert steam.vdf.read_bytes() == _raw()[:-12]                       # and the file is untouched


def test_art_is_recorded_even_when_a_later_picture_fails_and_on_a_re_add(steam, monkeypatch):
    g = {"id": "g-1", "title": "Game", "cover_file": None}
    real = steam_games.compose
    calls = []

    def flaky(pg_, cover, title, size):
        calls.append(size)
        if len(calls) == 2:
            raise RuntimeError("disk full")
        return real(pg_, cover, title, size)
    monkeypatch.setattr(steam_games, "compose", flaky)
    assert steam_games.add(g, LAUNCHER, steam.roots, pg)                  # the shortcut is in
    rec = steam_games._record()["g-1"]["users"]["4242"]
    assert len(rec["art"]) == 1 and (steam.grid / rec["art"][0]).exists()   # the picture that was made is recorded
    monkeypatch.setattr(steam_games, "compose", real)
    steam_games.remove("g-1", steam.roots)
    steam_games.add(g, LAUNCHER, steam.roots, pg)
    steam.vdf.write_bytes(_raw())                                           # the player removed it by hand in Steam
    steam_games.add(g, LAUNCHER, steam.roots, pg)                           # our old art is still there: still ours
    assert len(steam_games._record()["g-1"]["users"]["4242"]["art"]) == 3
    steam_games.remove("g-1", steam.roots)
    assert not any(steam.grid.iterdir())                                    # nothing of ours is left behind


def _autoplay_stub(game, calls, toast_error=False, backup=None):
    pgstub = types.SimpleNamespace(event=types.SimpleNamespace(pump=lambda: None),
                                   display=types.SimpleNamespace(flip=lambda: None))
    return types.SimpleNamespace(
        autoplay="g-1", pg=pgstub, running=True, screen=None, _backup_thread=backup,
        scene=types.SimpleNamespace(toast="x", toast_error=toast_error, draw=lambda s: calls.append("draw")),
        lib=types.SimpleNamespace(by_id=lambda gid: game),
        inst=types.SimpleNamespace(index={"g-1": {"dir": "x"}}),
        play=lambda g: calls.append("play"), _splash=lambda *a: calls.append(a))


def test_autoplay_says_the_right_thing_waits_for_the_backup_and_ends_quietly(monkeypatch):
    monkeypatch.setattr(app_play.time, "sleep", lambda s: None)
    calls = []
    app_play.PlayMixin._autoplay(_autoplay_stub({"id": "g-1", "state": "missing", "missing": "card"}, calls))
    assert calls[0] == ("SD card missing.", "Put the card back, then start it again.")      # not "reinstall it"
    calls.clear()
    joined = []
    th = types.SimpleNamespace(join=lambda t: joined.append(t))
    app_play.PlayMixin._autoplay(_autoplay_stub({"id": "g-1", "state": "installed"}, calls, False, th))
    assert calls == ["play"] and joined == [8]                         # the saves backup gets time to finish
    calls.clear()                                                       # "closed" (not an error) does not hold the screen
    app_play.PlayMixin._autoplay(_autoplay_stub({"id": "g-1", "state": "installed"}, calls, False))
    assert "draw" not in calls
    calls.clear()                                                       # a real "couldn't start" does stay a moment
    ticks = iter(range(0, 100))
    monkeypatch.setattr(app_play.time, "time", lambda: next(ticks))     # a fake clock: no real 5 seconds
    app_play.PlayMixin._autoplay(_autoplay_stub({"id": "g-1", "state": "installed"}, calls, True))
    assert calls.count("draw") >= 1
