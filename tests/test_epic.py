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
    [ "$3" = "%s" ] || { echo "Login attempt failed" >&2; exit 1; }
    mkdir -p "$LEGENDARY_CONFIG_PATH"
    echo '{"displayName": "omri_epic", "refresh_token": "SECRET"}' > "$LEGENDARY_CONFIG_PATH/user.json";;
  "auth --delete") rm -f "$LEGENDARY_CONFIG_PATH/user.json";;
  "list --json")
    [ -f "$LEGENDARY_CONFIG_PATH/user.json" ] || { echo "Login failed, cannot continue!" >&2; exit 1; }
    [ -n "$OFFLINE" ] && { echo "ConnectionError" >&2; exit 1; }
    cat "$FAKE_LIST";;
esac
""" % GOOD


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


def test_tabs_and_read_only_game_page():
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
    assert gp.actions() == [] and gp.message()[1] == "Coming soon"
