"""Epic step 1: sign in with the phone code through legendary, read-only Epic tab. A stand-in
legendary script plays Epic (the workspace can't reach it): auth --code, list --json, auth --delete."""
import json
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from itch_deck import library, paths
from itch_deck.stores import epic

GOOD = "a" * 32
FAKE = r"""#!/bin/sh
# stand-in legendary: config in $LEGENDARY_CONFIG_PATH, library from $FAKE_LIST
case "$1 $2" in
  "auth --code")
    [ "$3" = "@GOOD@" ] || { echo "Login attempt failed" >&2; exit 1; }
    mkdir -p "$LEGENDARY_CONFIG_PATH"
    echo '{"displayName": "omri_epic", "refresh_token": "SECRET"}' > "$LEGENDARY_CONFIG_PATH/user.json";;
  "auth --delete") rm -f "$LEGENDARY_CONFIG_PATH/user.json";;
  "install Fern")
    dir=""; while [ $# -gt 0 ]; do [ "$1" = "--game-folder" ] && dir="$2"; shift; done
    [ -n "$NOSPACE" ] && { echo "[cli] ERROR: Not enough available disk space!" >&2; exit 1; }
    for p in 10.00 55.50 100.00; do
      echo "[DLManager] INFO: = Progress: $p% (1/2), Running for 00:00:01, ETA: 00:00:0${SLOW:-0}" >&2
      echo "[DLManager] INFO:  + Download	- 12.50 MiB/s (raw) / 20.00 MiB/s (decompressed)" >&2
      [ -n "$SLOW" ] && sleep "$SLOW"
    done
    mkdir -p "$dir/Binaries/Win64"; printf 'MZ' > "$dir/Binaries/Win64/Hades.exe"
    printf '{"Fern": {"app_name": "Fern", "install_path": "%s", "executable": "Binaries\\\\Win64\\\\Hades.exe", "version": "%s"}}' "$dir" "${VER:-1}" > "$LEGENDARY_CONFIG_PATH/installed.json";;
  "launch Fern")
    d=$(sed -n 's/.*"install_path": "\([^"]*\)".*/\1/p' "$LEGENDARY_CONFIG_PATH/installed.json")
    printf '{"game_executable": "Binaries/Win64/Hades.exe", "game_directory": "%s", "game_parameters": ["-x"], "user_parameters": [], "egl_parameters": ["-AUTH_PASSWORD=SECRETCODE"], "working_directory": "%s", "environment": {}}' "$d" "$d";;
  "uninstall Fern") echo '{}' > "$LEGENDARY_CONFIG_PATH/installed.json";;
  "list --json")
    [ -f "$LEGENDARY_CONFIG_PATH/user.json" ] || { echo "Login failed, cannot continue!" >&2; exit 1; }
    [ -n "$OFFLINE" ] && { echo "ConnectionError" >&2; exit 1; }
    cat "$FAKE_LIST";;
esac
""".replace("@GOOD@", GOOD)


def _game(name, title, **meta):
    m = {"developer": "Dev Co", "description": "A game.", "keyImages": [
        {"type": "DieselGameBoxTall", "url": "https://x/tall.jpg"},
        {"type": "DieselGameBox", "url": "https://x/wide.jpg"}]}
    m.update(meta)
    return {"app_name": name, "app_title": title, "asset_infos": {"Windows": {"build_version": "1"}},
            "metadata": m, "base_urls": [], "dlcs": []}


LIST = [_game("Fern", "Hades"),
        _game("FernDLC", "Hades Soundtrack", mainGameItem={"id": "x"}),
        _game("Ubi1", "Far Cry 5", customAttributes={"ThirdPartyManagedApp": {"value": "UbisoftConnect"}}),
        {"app_name": "Old", "app_title": "Old Game", "asset_info": {"build_version": "1"}, "metadata": {}}]


def _setup(tmp_path, monkeypatch):
    paths.use_root(tmp_path)
    b = epic.bin_path()
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_text(FAKE)
    b.chmod(0o755)
    lst = tmp_path / "list.json"
    lst.write_text(json.dumps(LIST))
    monkeypatch.setenv("FAKE_LIST", str(lst))
    return epic.EpicStore()


def test_code_from_pasted_page():
    page = '{"warning":"Do not share this code","redirectUrl":"https://x","authorizationCode":"%s","sid":null}' % GOOD
    assert epic.code_from_text(page) == GOOD
    assert epic.code_from_text(f'  "authorizationCode": "{GOOD}",') == GOOD
    assert epic.code_from_text(GOOD) == GOOD
    assert epic.code_from_text("hello there") is None


def test_sign_in_list_sign_out(tmp_path, monkeypatch):
    st = _setup(tmp_path, monkeypatch)
    assert st.ready() and not st.connected()
    assert st.login("b" * 32) is False                      # Epic says no
    assert st.login(GOOD) and st.user() == "omri_epic"
    assert oct(epic.config_dir().stat().st_mode)[-3:] == "700"  # holds the sign-in
    games = {g["title"]: g for g in st.sync()}
    assert set(games) == {"Hades", "Far Cry 5", "Old Game"}     # DLC left out
    h = games["Hades"]
    assert h["id"] == "epic-Fern" and h["store"] == "epic" and h["platforms"] == ["windows"]
    assert h["cover_url"] == "https://x/wide.jpg" and h["author"] == "Dev Co"
    assert games["Far Cry 5"]["platforms"] == ["other"] and games["Old Game"]["platforms"] == ["windows"]
    assert "SECRET" not in json.dumps(list(games.values()))
    monkeypatch.setenv("OFFLINE", "1")
    try:
        st.sync()
        raise AssertionError("offline sync must raise")
    except epic.EpicError:
        pass
    st.logout()
    assert not st.connected()


def test_library_keeps_stores_apart(tmp_path, monkeypatch):
    st = _setup(tmp_path, monkeypatch)
    st.login(GOOD)
    lib = library.Library(None)
    lib.games = [lib._prep({"id": "5", "title": "Bleed 2", "platforms": ["linux"]})]
    lib.epic = st
    monkeypatch.setattr(lib, "queue_covers", lambda: None)
    monkeypatch.setattr(lib, "queue_hltb", lambda: None)
    assert lib.start_epic_sync()
    end = time.time() + 10
    while lib.epic_syncing and time.time() < end:
        time.sleep(0.02)
    titles = [g["title"] for g in lib.games]
    assert titles == sorted(titles, key=str.lower) and "Bleed 2" in titles and "Hades" in titles

    class Itch:                                     # an itch refresh must not drop Epic games
        def sync(self, on_page=None):
            return [{"id": "5", "title": "Bleed 2", "platforms": ["linux"]}]
    lib.store = Itch()
    monkeypatch.setattr(lib, "queue_prefetch", lambda: None)
    lib._sync()
    assert lib.by_id("epic-Fern") and lib.by_id("5")
    saved = json.loads(paths.LIBRARY.read_text())["games"]
    assert any(g.get("store") == "epic" for g in saved)            # survives a restart

    monkeypatch.setenv("OFFLINE", "1")             # Epic down: its games stay, itch untouched
    assert lib.sync_epic() is False and lib.epic_error and lib.by_id("epic-Fern") and lib.by_id("5")
    lib.drop_epic()
    assert not any(g.get("store") == "epic" for g in lib.games) and lib.by_id("5")


def test_tabs_and_epic_game_page():
    import pygame as pg
    pg.init()
    from itch_deck.theme import Theme
    from itch_deck.ui.scenes.game import Game
    from itch_deck.ui.scenes.library import Library
    t = Theme(pg, (1280, 800))
    games = [{"id": "5", "title": "Bleed 2", "platforms": {"linux"}, "state": None},
             {"id": "epic-Fern", "title": "Hades", "platforms": {"windows"}, "store": "epic", "state": None}]
    sc = Library(t, games, stores=("itch", "epic"))
    assert [k for k, _ in sc.tabs()] == ["all", "installed", "itch", "epic"]
    sc.filt = "epic"
    assert [g["title"] for g in sc.shown] == ["Hades"]
    gp = Game(t, games[1])
    assert [a[0] for a in gp.actions()] == ["Install", "Options"]
    assert gp.options() == ["Hide from SCRiTCH"]                         # no Change build (v0.9.23: Hide is the one row)
    games[1]["state"] = "installed"
    assert Game(t, games[1]).options() == ["Uninstall", "Controls", "Saves", "Hide from SCRiTCH"]


def test_epic_install_play_uninstall(tmp_path, monkeypatch):
    """Install through legendary into <root>/<game>/files with one progress bar, then Play
    starts it via umu with Epic's sign-in args kept out of the log; Uninstall tells legendary."""
    from itch_deck import installer, runner
    from test_install import _umu, _wait
    st = _setup(tmp_path, monkeypatch)
    st.login(GOOD)
    _umu(tmp_path)                                  # GE-Proton + umu in place (no downloads)
    lib = library.Library(None)
    lib.epic = st
    lib.games = [lib._prep(epic.game_from_json(LIST[0]))]
    inst = installer.Installer(lib, lambda: tmp_path / "games")
    seen = []
    real = inst._upd
    inst._upd = lambda gid, **kw: (seen.append(kw.get("progress")), real(gid, **kw))
    inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("epic-Fern")
    assert g["state"] == "installed", g.get("fail_reason")
    info = inst.index["epic-Fern"]
    assert info["store"] == "epic" and info["exe"] == "Binaries/Win64/Hades.exe"
    assert inst.exe_path("epic-Fern").exists() and info["prefix"].endswith("_prefixes/hades")
    prog = [p for p in seen if p not in (None, 0)]
    assert prog and prog == sorted(prog) and max(prog) < 1        # 0.1 -> 0.555 -> 0.999
    assert (paths.LOGS / "games/hades-install.log").read_text().count("Progress") == 3

    lp = st.launch_params("Fern")
    assert lp["egl_parameters"] == ["-AUTH_PASSWORD=SECRETCODE"]
    exe = paths.HOME / "fake-game.sh"               # the game itself: a script that prints its args
    exe.write_text("#!/bin/sh\necho args: \"$@\"\n")
    exe.chmod(0o755)
    rc, _ = runner.run(exe, "hades", args=lp["game_parameters"], secret_args=lp["egl_parameters"],
                       cwd=lp["working_directory"])
    log_ = (paths.LOGS / "games/hades.log").read_text()
    assert rc == 0 and "args: -x -AUTH_PASSWORD=SECRETCODE" in log_      # the game gets it
    assert log_.count("SECRETCODE") == 1 and "<Epic sign-in arguments hidden>" in log_   # our line doesn't

    assert inst.uninstall("epic-Fern")
    end = time.time() + 5
    while st.installed().get("Fern") is not None and time.time() < end:
        time.sleep(0.05)
    assert "Fern" not in st.installed() and "epic-Fern" not in inst.index


def test_epic_install_fails_plainly_and_cancels(tmp_path, monkeypatch):
    from itch_deck import installer, words
    from test_install import _umu, _wait
    st = _setup(tmp_path, monkeypatch)
    st.login(GOOD)
    _umu(tmp_path)
    lib = library.Library(None)
    lib.epic = st
    lib.games = [lib._prep(epic.game_from_json(LIST[0]))]
    inst = installer.Installer(lib, lambda: tmp_path / "games")
    monkeypatch.setenv("NOSPACE", "1")
    inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("epic-Fern")
    assert g["state"] == "failed" and words.short(g["fail_reason"]) == "Not enough space"
    monkeypatch.delenv("NOSPACE")
    monkeypatch.setenv("SLOW", "2")                 # cancel mid-download: legendary is stopped
    inst.enqueue(lib.games[0])
    time.sleep(1.0)
    inst.cancel("epic-Fern")
    _wait(inst, secs=15)
    assert lib.by_id("epic-Fern")["state"] is None and "epic-Fern" not in inst.index


def test_itch_games_not_duplicated_after_restart(tmp_path, monkeypatch):
    """v0.7.6 bug: cached itch games came back with store null, so every itch refresh kept the
    old copies (3 of each after two refreshes). Old caches with duplicates are repaired on load."""
    paths.use_root(tmp_path)
    paths.LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    bad = {"id": "5", "title": "Bleed 2", "platforms": ["linux"], "store": None}
    epic_g = {"id": "epic-Fern", "title": "Hades", "platforms": ["windows"], "store": "epic"}
    paths.LIBRARY.write_text(json.dumps({"synced_at": None, "games": [bad, bad, bad, epic_g]}))

    class Itch:
        def sync(self, on_page=None):
            return [{"id": "5", "title": "Bleed 2", "platforms": ["linux"]}]
    lib = library.Library(Itch())
    lib.load_cache()
    assert [g["id"] for g in lib.games] == ["5", "epic-Fern"]       # repaired on load
    for k in ("queue_covers", "queue_prefetch", "queue_hltb"):
        monkeypatch.setattr(lib, k, lambda: None)
    for _ in range(3):                                              # refresh, restart, refresh…
        lib._sync()
        lib = library.Library(Itch())
        lib.load_cache()
        for k in ("queue_covers", "queue_prefetch", "queue_hltb"):
            monkeypatch.setattr(lib, k, lambda: None)
    assert sorted(g["id"] for g in lib.games) == ["5", "epic-Fern"]


def test_big_covers_are_shrunk(tmp_path):
    """Epic sends 2560 px art: saved at most 720 px so scrolling never decodes huge images."""
    import pygame as pg
    from pathlib import Path
    f = Path(tmp_path) / "epic-Fern.jpg"
    pg.image.save(pg.Surface((2560, 1440)), str(f))
    out = library.shrink_cover(f)
    assert out.name == "epic-Fern.small.jpg" and not f.exists()
    assert max(pg.image.load(str(out)).get_size()) == 720
    small = Path(tmp_path) / "5.png"
    pg.image.save(pg.Surface((315, 250)), str(small))
    assert library.shrink_cover(small) == small                     # itch-sized: untouched


def test_epic_page_text_from_epic_shots_from_steam(tmp_path, monkeypatch):
    """Epic's long text first; Steam (exact title match only) adds screenshots + genre, and the
    text when Epic has none. A near-miss Steam title is never used."""
    import io
    import pygame as pg
    from itch_deck import net
    from itch_deck.stores import steam
    paths.use_root(tmp_path)
    buf = io.BytesIO()
    pg.image.save(pg.Surface((64, 36)), buf, "x.png")
    png = buf.getvalue()
    search = {"items": [{"id": 7, "name": "Hades II", "type": "app"},
                        {"id": 9, "name": "HADES™", "type": "app"}]}
    app = {"9": {"success": True, "data": {
        "about_the_game": "<h2>Defy the god</h2><p>Battle out of <b>hell</b>.</p><ul><li>Fast</li></ul>",
        "screenshots": [{"path_full": "https://s/1.jpg"}, {"path_full": "https://s/2.jpg"}],
        "genres": [{"description": "Action"}, {"description": "Indie"}]}}}
    asked = []

    def get_json(url, key=None, timeout=20):
        asked.append(url)
        return search if "storesearch" in url else app
    monkeypatch.setattr(net, "get_json", get_json)
    monkeypatch.setattr(net, "get", lambda url, *a, **k: png)
    lib = library.Library(None)
    g = lib._prep(dict(epic.game_from_json(LIST[0]), long_text="# Hades\n\nA **rogue-like** [dungeon](https://x) crawler."))
    lib.games = [g]
    lib._fetch_page(g)
    assert g["description"] == ["Hades", "A rogue-like dungeon crawler."] and g["details_from"] == "Epic"
    assert g["screens"] == 2 and g["genre"] == "Action" and g["comments"] is None
    assert lib._has_page_fields(g)                                   # new pages aren't refetched
    assert any("appids=9" in u for u in asked)                       # HADES™ matched, Hades II not

    g2 = lib._prep(dict(epic.game_from_json(LIST[0]), long_text=""))
    lib._fetch_page(g2)
    assert g2["details_from"] == "Steam"
    assert g2["description"] == ["Defy the god", "Battle out of hell.", "• Fast"]

    search["items"] = [{"id": 7, "name": "Hades II", "type": "app"}]  # no exact match: nothing
    g3 = lib._prep(dict(epic.game_from_json(LIST[0]), id="epic-X", long_text=""))
    lib._fetch_page(g3)
    assert g3["description"] == [] and g3["screens"] == 0 and g3["details_at"]
    assert steam.norm("Tom Clancy's® Ghost & Recon™") == "tom clancy s ghost and recon"


def test_steam_genre_is_a_real_genre_in_itch_words(tmp_path):
    from itch_deck.stores.steam import pick_genre
    assert pick_genre(["Indie", "Casual", "RPG", "Action"]) == "Role Playing"
    assert pick_genre(["Free to Play", "Massively Multiplayer", "Strategy"]) == "Strategy"
    assert pick_genre(["Indie", "Casual"]) == "" and pick_genre([]) == ""
    paths.use_root(tmp_path)                       # a v0.7.9 Epic page with "Indie": hidden + refetched
    lib = library.Library(None)
    g = lib._prep(epic.game_from_json(LIST[0]))
    f = lib._page_file(g)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"fetched": "2026-11-15T18:00:00", "description": [], "genre": ["Indie"],
                             "inputs": [], "source": "Epic"}))
    g = lib._prep(epic.game_from_json(LIST[0]))
    assert g["genre"] == "" and not lib._has_page_fields(g)


def test_epic_update_badge_and_update(tmp_path, monkeypatch):
    """Epic's newest build differs from the installed one -> Update; Update patches in place."""
    from itch_deck import installer
    from test_install import _umu, _wait
    st = _setup(tmp_path, monkeypatch)
    st.login(GOOD)
    _umu(tmp_path)
    lib = library.Library(None)
    lib.epic = st
    for k in ("queue_covers", "queue_hltb"):
        monkeypatch.setattr(lib, k, lambda: None)
    lib.sync_epic()
    inst = installer.Installer(lib, lambda: tmp_path / "games")
    inst.enqueue(lib.by_id("epic-Fern"))
    _wait(inst)
    assert st.installed()["Fern"]["version"] == "1"
    assert inst.check_epic_updates() == 0 and not lib.by_id("epic-Fern").get("update")
    newer = [dict(e, asset_infos={"Windows": {"build_version": "2"}}) if e["app_name"] == "Fern" else e
             for e in LIST]
    (tmp_path / "list.json").write_text(json.dumps(newer))
    lib.sync_epic()                                  # sync -> on_epic_sync -> badge
    g = lib.by_id("epic-Fern")
    assert g["update"] and inst.index["epic-Fern"]["update"]
    monkeypatch.setenv("VER", "2")
    inst.update(g)
    _wait(inst)
    assert st.installed()["Fern"]["version"] == "2" and not lib.by_id("epic-Fern").get("update")
    assert inst.check_epic_updates() == 0
