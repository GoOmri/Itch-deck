"""v0.9.29, part 2: scroll marks, closed-at-once message, stay open, setup toast, DOS summary."""
import os
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame as pg  # noqa: E402

if os.name == "nt":
    sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))
from itch_deck import paths  # noqa: E402


def _theme(size=(1280, 800)):
    from itch_deck import theme
    pg.init()
    pg.display.set_mode((64, 64))
    return theme.Theme(pg, size)


# --- 4: scroll marks -------------------------------------------------------------------------------------------------
def test_a_long_list_shows_chevrons_and_a_bar_and_a_short_one_does_not():
    from itch_deck.ui import widgets as W
    for size in ((1280, 800), (1920, 1080)):
        t = _theme(size)
        items = [(f"P{i}.EXE", "", "Top folder") for i in range(30)]
        W.forget_menu("Choose the program")
        s = pg.Surface(size)
        s.fill((0, 0, 0))
        r = W.menu(t, s, "Choose the program", "Pick one.", items, 12)
        cx = r.right - t.u
        strip = [s.get_at((cx, y))[:3] for y in range(r.y, r.bottom)]
        assert strip.count(t.dim) > 10 and t.line in strip              # thumb (dim) and track (line)
        W.forget_menu("Short")
        s.fill((0, 0, 0))
        r2 = W.menu(t, s, "Short", "", items[:3], 0)
        assert not any(s.get_at((r2.right - t.u, y))[:3] == t.dim for y in range(r2.y, r2.bottom))


# --- 5: closed straight away ----------------------------------------------------------------------------------------
def _app(tmp_path, monkeypatch, programs=("A.EXE", "B.EXE")):
    from itch_deck import app as appmod, dosbox, runner
    from test_v0928 import make_game
    paths.use_root(tmp_path / "home")
    a = appmod.App(windowed=True)
    a.lib._fetch_dosart = lambda *x, **k: None
    dos = tmp_path / "dos"
    make_game(dos / "Indy", programs[0], list(programs[1:]))
    a.inst.dos_roots = lambda: [dos]
    a.inst.dos_root = lambda: dos
    a.inst.sync_dos()
    g = next(x for x in a.lib.games if x["store"] == "dos")
    monkeypatch.setattr(dosbox, "native", lambda: ["dosbox"])
    return a, g, dosbox, runner


def test_a_program_that_closes_at_once_gets_a_friendly_message_and_a_button(tmp_path, monkeypatch, caplog):
    import logging
    from itch_deck.input import A
    a, g, dosbox, runner = _app(tmp_path, monkeypatch)
    monkeypatch.setattr(runner, "run", lambda *x, **k: (0, 1.0))
    a.go_game(g)
    with caplog.at_level(logging.INFO, logger="scritch"):
        a.play(g)
    assert a.scene.overlay and a.scene.overlay[0] == "confirm"
    assert a.scene.overlay[1] == "That program closed straight away."
    assert "Program to run" in " ".join(a.scene.overlay[2])
    assert ("A", "Program to run") in a.scene.overlay[3]
    assert any("P01" in r.getMessage() for r in caplog.records)           # the log keeps the code
    a.handle(A)                                                           # the button opens the list
    assert a.scene.overlay and a.scene.overlay[0] == "picker"


def test_a_single_program_gets_a_plain_message_and_other_cases_keep_the_old_way(tmp_path, monkeypatch):
    a, g, dosbox, runner = _app(tmp_path, monkeypatch, programs=("A.EXE",))
    monkeypatch.setattr(runner, "run", lambda *x, **k: (0, 1.0))
    a.go_game(g)
    a.play(g)
    assert not a.scene.overlay and "closed straight away" in a.scene.toast and a.scene.toast_error
    monkeypatch.setattr(runner, "run", lambda *x, **k: (0, 60.0))        # a normal play: no message at all
    a.go_game(g)
    a.play(g)
    assert not a.scene.toast or "straight away" not in a.scene.toast
    monkeypatch.setattr(runner, "run", lambda *x, **k: (1, 1.0))         # a real crash: the old words
    a.go_game(g)
    a.play(g)
    assert "couldn't start" in a.scene.toast


# --- 6: stay open ----------------------------------------------------------------------------------------------------
def test_stay_open_leaves_out_the_final_exit(tmp_path, monkeypatch):
    a, g, dosbox, runner = _app(tmp_path, monkeypatch)
    info = a.inst.index[g["id"]]
    _e, args, _c = dosbox.launch_own(info, ["dosbox"])
    assert args[-1] == "exit" and args[-2] == "-c"
    _e, args, _c = dosbox.launch_own(info, ["dosbox"], stay=True)
    assert "exit" not in args and args[-1] == "A.EXE"


def test_the_options_row_toggles_in_the_config_and_play_uses_it(tmp_path, monkeypatch):
    seen = []
    a, g, dosbox, runner = _app(tmp_path, monkeypatch)
    monkeypatch.setattr(runner, "run", lambda exe, *x, **k: (seen.append(k.get("args")) or (0, 60.0)))
    monkeypatch.setattr("itch_deck.config.save", lambda cfg: None)
    a.go_game(g)
    a.open_options(a.scene)
    row = next(r for r in a.scene.overlay[3] if r[0] == "Stay open when the game ends")
    assert row[1] == "Off" and row[2] == "To read an error message"
    a.game_action(g, "Stay open when the game ends")
    assert a.cfg["dos_stay_open"] == [g["id"]]
    assert next(r for r in a.scene.overlay[3] if r[0].startswith("Stay open"))[1] == "On"
    a.play(g)
    assert "exit" not in seen[-1]
    a.game_action(g, "Stay open when the game ends")
    assert a.cfg["dos_stay_open"] == []
    a.go_game(g)
    a.play(g)
    assert "exit" in seen[-1]
    assert sorted(p.name for p in (tmp_path / "dos" / "Indy").iterdir()) == ["A.EXE", "B.EXE"]


# --- 7: setup finished ------------------------------------------------------------------------------------------------
def test_a_closed_setup_says_the_next_play_starts_the_game(tmp_path, monkeypatch):
    a, g, dosbox, runner = _app(tmp_path, monkeypatch, programs=("A.EXE", "SETUP.EXE"))
    seen = []
    monkeypatch.setattr(runner, "run", lambda exe, *x, **k: (seen.append(k.get("args")) or (0, 20.0)))
    assert a.inst.run_once(g["id"], "SETUP.EXE")
    a.go_game(g)
    a.play(g)
    assert "SETUP.EXE" in seen[-1] and a.scene.toast == "Setup closed. The next Play starts the game."
    a.go_game(g)
    a.play(g)
    assert "A.EXE" in seen[-1] and "SETUP.EXE" not in seen[-1]


# --- 8: DOS summary for Send logs -------------------------------------------------------------------------------------
def test_the_dos_summary_has_what_support_needs_and_leaks_nothing():
    import datetime as dt
    from itch_deck import dossummary
    from itch_deck.installer import slug_of
    games = [{"id": "d1", "title": "Blood", "store": "dos"}, {"id": "d2", "title": "Raptor", "store": "dos"},
             {"id": "x", "title": "Itch Game", "store": "itch"}]
    index = {"d1": {"exe": "BLOOD.EXE", "alternatives": ["SETUP/CFG.EXE", "/home/deck/Games/dos/Blood/EVIL.EXE"],
                    "setups": ["SETUP.EXE"]},
             "d2": {"exe": "R.EXE", "alternatives": [], "setups": []}}
    now = dt.datetime.now().astimezone()
    cache = {"d1": {"at": (now - dt.timedelta(days=3)).isoformat(),
                    "match": {"title": "Doom + Doom II", "source": "gog", "score": 66, "fallback": True}},
             "d2": {"at": now.isoformat(), "match": None}}
    s1 = slug_of(games[0])
    log_text = (f"x play: {s1} exited 0 after 1s\nx play: {s1} exited 0 after 55s\n"
                "token=SECRETSECRET1234 /home/deck/x\n")
    full, short = dossummary.build(games, index, cache, log_text, now)
    assert "Itch Game" not in full and full.startswith("Own DOS games: 2")
    assert "Blood | program: BLOOD.EXE" in full and "match: Doom + Doom II (gog, score 66, art only)" in full
    assert "asked 3 days ago" in full and "last play: 55 s, exit 0" in full
    assert "Raptor" in full and "no match" in full and "not played" in full
    assert "setups: SETUP.EXE" in full and "SETUP/CFG.EXE" in full
    for bad in ("/home/deck", "SECRETSECRET", "Games/dos"):
        assert bad not in full and bad not in short, bad
    assert "EVIL.EXE" in full                                           # only the file name of a full path
    full2, _s = dossummary.build([{"id": "d3", "title": "api_key=ABCDEF1234567890 /home/omri/x", "store": "dos"}],
                                 {}, {}, "", now)
    assert "ABCDEF1234567890" not in full2 and "/home/omri" not in full2
    many = [{"id": f"d{i}", "title": f"Game {i}", "store": "dos"} for i in range(60)]
    f3, s3 = dossummary.build(many, {}, {}, "", now)
    assert s3.count("\n- ") + 1 == 40 and "first 40" in s3 and f3.count("\n- ") + 1 == 60


def test_the_summary_goes_into_the_zip_and_the_pasted_text_within_the_caps(tmp_path):
    import io
    import zipfile
    from itch_deck import logshare
    paths.use_root(tmp_path / "home")
    paths.LOGS.mkdir(parents=True, exist_ok=True)
    (paths.LOGS / "app.log").write_text("line\n" * 50)
    short = "Own DOS games: 60\n" + "\n".join(f"- Game {i} | G.EXE | no match | 1 s, exit 0" for i in range(60))
    z = zipfile.ZipFile(io.BytesIO(logshare.zip_bytes("0.9.29", dos_text="Own DOS games: 1\n- A | token=ABCDEFGH123456")))
    assert "dos-summary.txt" in z.namelist() and "ABCDEFGH123456" not in z.read("dos-summary.txt").decode()
    assert "dos-summary.txt" not in zipfile.ZipFile(io.BytesIO(logshare.zip_bytes("0.9.29"))).namelist()
    rep = logshare.report("0.9.29", dos_short=short)
    assert "--- own DOS games ---" in rep and len(rep) <= logshare.REPORT_CHARS
    comp = logshare.compact(dos_short=short)
    assert comp.startswith("Own DOS games: 60") and len(comp) <= logshare.COMPACT_CHARS + 100
    assert "--- app.log" in comp
    assert "own DOS" not in logshare.compact()
