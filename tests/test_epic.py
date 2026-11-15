"""Epic step 1: read-only Epic tab from Heroic's legendary files (no network, no tokens touched)."""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from itch_deck import library, paths
from itch_deck.stores import epic

FLATPAK = ".var/app/com.heroicgameslauncher.hgl/config/heroic/legendaryConfig/legendary"


def _heroic(home, games, user="omri_epic"):
    d = home / FLATPAK
    (d / "metadata").mkdir(parents=True)
    (d / "user.json").write_text(json.dumps({"displayName": user, "access_token": "SECRET"}))
    for name, data in games.items():
        (d / "metadata" / f"{name}.json").write_text(json.dumps(data) if isinstance(data, dict) else data)
    return d


def _game(name, title, **meta):
    m = {"developer": "Dev Co", "description": "A game.", "keyImages": [
        {"type": "DieselGameBoxTall", "url": "https://x/tall.jpg"},
        {"type": "DieselGameBox", "url": "https://x/wide.jpg"}]}
    m.update(meta)
    return {"app_name": name, "app_title": title, "asset_infos": {"Windows": {"build_version": "1"}},
            "metadata": m, "base_urls": []}


GAMES = {
    "Fern": _game("Fern", "Hades"),
    "FernDLC": _game("FernDLC", "Hades Soundtrack", mainGameItem={"id": "x"}),
    "Ubi1": _game("Ubi1", "Far Cry 5", customAttributes={"ThirdPartyManagedApp": {"value": "UbisoftConnect"}}),
    "Old": {"app_name": "Old", "app_title": "Old Game", "asset_info": {"build_version": "1"}, "metadata": {}},
    "Broken": "{not json",
}


def test_reads_heroic_library(tmp_path):
    assert epic.EpicStore(tmp_path).connected() is False
    _heroic(tmp_path, GAMES)
    st = epic.EpicStore(tmp_path)
    assert st.connected() and st.user() == "omri_epic"
    games = {g["title"]: g for g in st.sync()}
    assert set(games) == {"Hades", "Far Cry 5", "Old Game"}             # DLC + broken file left out
    h = games["Hades"]
    assert h["id"] == "epic-Fern" and h["store"] == "epic" and h["platforms"] == ["windows"]
    assert h["cover_url"] == "https://x/wide.jpg" and h["author"] == "Dev Co"   # landscape art first
    assert games["Far Cry 5"]["platforms"] == ["other"]                # Ubisoft: not installable
    assert games["Old Game"]["platforms"] == ["windows"]               # old single-asset file
    assert "SECRET" not in json.dumps(list(games.values()))            # tokens never copied


def test_library_keeps_stores_apart(tmp_path, monkeypatch):
    paths.use_root(tmp_path / "data")
    home = tmp_path / "home"
    _heroic(home, GAMES)
    lib = library.Library(None)
    lib.games = [lib._prep({"id": "5", "title": "Bleed 2", "platforms": ["linux"]})]
    lib.epic = epic.EpicStore(home)
    monkeypatch.setattr(lib, "queue_covers", lambda: None)
    monkeypatch.setattr(lib, "queue_hltb", lambda: None)
    assert lib.sync_epic()
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
    assert {g.get("store") for g in saved} >= {"epic"}                 # survives a restart

    lib.epic = epic.EpicStore(tmp_path / "nobody")  # Heroic signed out: Epic fails, itch untouched
    assert lib.sync_epic() is False and lib.epic_error and lib.by_id("5")
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
