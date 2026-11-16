"""GOG step 1: sign in with the phone (pasted address) through gogdl, read-only GOG tab. A stand-in
gogdl script plays the helper and GOG's web API is stubbed (the workspace can't reach GOG)."""
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

from itch_deck import library, net, paths
from itch_deck.stores import gog

CODE = "Xy9_-" * 20
ADDRESS = f"https://embed.gog.com/on_login_success?origin=client&code={CODE}"
FAKE = r"""#!/bin/sh
# stand-in gogdl: --auth-config-path FILE auth [--code C]
f="$2"; shift 2
if [ "$1 $2" = "auth --code" ]; then
  [ -n "$OFFLINE" ] && { echo "[AUTH] ERROR: Failed to reach GOG (ConnectionError)" >&2; echo '{"error": true}'; exit 0; }
  [ "$3" = "@CODE@" ] || { echo '{"error": true}'; exit 0; }
  echo '{"46899977096215655": {"access_token": "TOKEN", "refresh_token": "SECRET", "expires_in": 3600, "loginTime": 1}}' > "$f"
  echo '{"access_token": "TOKEN", "refresh_token": "SECRET"}'
elif [ "$1" = "auth" ]; then
  [ -n "$OFFLINE" ] && { echo null; exit 0; }
  [ -f "$f" ] && echo '{"access_token": "TOKEN"}' || echo null
fi
""".replace("@CODE@", CODE)

PAGE1 = {"totalPages": 2, "products": [
    {"id": 1207658924, "title": "Unreal Gold", "image": "//images-1.gog-statics.com/abc",
     "worksOn": {"Windows": True, "Mac": False, "Linux": False}, "category": "Shooter",
     "isGame": True},
    {"id": 2, "title": "Some Movie", "image": "//x/m", "worksOn": {}, "isGame": False}]}
PAGE2 = {"totalPages": 2, "products": [
    {"id": 3, "title": "Stardew Valley", "image": "//x/s",
     "worksOn": {"Windows": True, "Linux": True}, "category": "Role-playing"}]}
PRODUCT = {"description": {"lead": "Lead.", "full": "<p>First para.</p><p>Second para.</p>"},
           "screenshots": [{"image_id": "s1", "formatter_template_url":
                            "https://images.gog-statics.com/s1_{formatter}.jpg"}]}


def _setup(tmp_path, monkeypatch, api=None):
    paths.use_root(tmp_path)
    b = gog.bin_path()
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_text(FAKE)
    b.chmod(0o755)
    calls = []

    def get_json(url, key=None, timeout=20):
        calls.append((url, key))
        if api:
            return api(url, key)
        if "userData" in url:
            return {"username": "omri_gog"}
        if "getFilteredProducts" in url:
            return PAGE2 if "page=2" in url else PAGE1
        if "api.gog.com/products/" in url:
            return PRODUCT
        raise net.Offline("no stub for " + url)
    monkeypatch.setattr(net, "get_json", get_json)
    return gog.GogStore(), calls


def test_code_from_pasted_address():
    assert gog.code_from_text(ADDRESS) == CODE
    assert gog.code_from_text("  " + ADDRESS + "\n") == CODE
    assert gog.code_from_text(CODE) == CODE
    assert gog.code_from_text("hello there") is None
    assert gog.code_from_text("https://embed.gog.com/on_login_success?origin=client") is None


def test_login_url_is_galaxys():
    assert "client_id=" + gog.CLIENT_ID in gog.LOGIN_URL and "response_type=code" in gog.LOGIN_URL
    assert "on_login_success" in gog.LOGIN_URL


def test_sign_in_list_sign_out(tmp_path, monkeypatch):
    st, calls = _setup(tmp_path, monkeypatch)
    assert st.ready() and not st.connected() and st.user() is None
    assert st.login(CODE)
    assert st.connected() and st.user() == "omri_gog"
    assert oct(gog.auth_file().stat().st_mode & 0o777) == "0o600"
    assert oct(gog.auth_file().parent.stat().st_mode & 0o777) == "0o700"
    games = {g["id"]: g for g in st.sync()}
    assert set(games) == {"gog-1207658924", "gog-3"}          # the movie is left out
    u = games["gog-1207658924"]
    assert u["platforms"] == ["windows"] and u["store"] == "gog" and u["app_name"] == "1207658924"
    assert u["cover_url"] == "https://images-1.gog-statics.com/abc_392.jpg"
    assert games["gog-3"]["platforms"] == ["linux", "windows"]
    assert all(k == "TOKEN" for url, k in calls if "getFilteredProducts" in url)
    st.logout()
    assert not st.connected() and st.user() is None


def test_rejected_code_and_offline(tmp_path, monkeypatch):
    st, _ = _setup(tmp_path, monkeypatch)
    assert not st.login("w" * 60) and not st.connected()
    monkeypatch.setenv("OFFLINE", "1")
    with pytest.raises(gog.GogError):
        st.login(CODE)


def test_sync_failures_are_short(tmp_path, monkeypatch):
    def refused(url, key):
        raise net.AuthError("HTTP 401")
    st, _ = _setup(tmp_path, monkeypatch, api=refused)
    with pytest.raises(gog.GogError, match="Not signed in"):
        st.sync()
    assert st.login(CODE)
    with pytest.raises(gog.GogError, match="Signed out of GOG"):
        st.sync()
    monkeypatch.setenv("OFFLINE", "1")                       # gogdl can't refresh the token
    with pytest.raises(gog.GogError, match="Couldn't reach GOG"):
        st.sync()


def test_library_merge_keeps_other_stores(tmp_path, monkeypatch):
    st, _ = _setup(tmp_path, monkeypatch)
    lib = library.Library()
    lib.games = [lib._prep({"id": "1", "title": "Itch Game", "platforms": ["linux"]}),
                 lib._prep({"id": "epic-Fern", "title": "Hades", "platforms": ["windows"],
                            "store": "epic", "app_name": "Fern"})]
    lib.gog = st
    assert not lib.sync_gog()                                # not signed in: nothing changes
    assert len(lib.games) == 2 and lib.gog_error
    st.login(CODE)
    assert lib.sync_gog()
    assert {g["id"] for g in lib.games} == {"1", "epic-Fern", "gog-1207658924", "gog-3"}
    assert lib.sync_gog() and len(lib.games) == 4            # a second sync doesn't duplicate
    lib2 = library.Library()                                 # survives a restart (cache)
    g = lib2.by_id("gog-3")
    assert g["store"] == "gog" and g["category"] == "Role-playing" and g["platforms"] == {"linux", "windows"}
    lib.drop_gog()
    assert {g["id"] for g in lib.games} == {"1", "epic-Fern"} and lib.gog is None


def test_gog_page_text_shots_genre(tmp_path, monkeypatch):
    st, calls = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(library.Library, "_save_shots", lambda self, g, urls: len(urls))
    lib = library.Library()
    g = lib._prep(gog.game_from_json(PAGE2["products"][0]))
    lib.games = [g]
    assert lib._has_details(g)
    lib._fetch_page(g)
    assert g["description"] == ["First para.", "Second para."]
    assert g["genre"] == "Role Playing" and g["details_from"] == "GOG"
    assert any("api.gog.com/products/3" in u and k is None for u, k in calls)   # public, no token
    page = json.loads(lib._page_file(g).read_text())
    assert page["shots"] == 1
    paras, shots = gog.page_from_json(PRODUCT)
    assert shots == ["https://images.gog-statics.com/s1_ggvgl.jpg"]


def test_game_page_is_read_only():
    import pygame as pg
    pg.display.init()
    pg.font.init()
    from itch_deck.theme import Theme
    from itch_deck.ui.scenes.game import Game
    game = {"id": "gog-3", "title": "Stardew Valley", "platforms": {"windows"}, "store": "gog",
            "size_mb": 0, "state": None, "screens": 0}
    sc = Game(Theme(pg, (1280, 800)), game)
    assert sc.read_only and not sc.options()
    assert [a for a in sc.actions() if a[0] in ("Install", "Play")] == []
    assert sc.message() == ("info", "Coming soon", "Installing GOG games is next.")


def test_tabs_with_three_stores():
    from itch_deck.ui.scenes.library import tabs
    assert [k for k, _ in tabs(("itch", "epic", "gog"))] == ["all", "installed", "itch", "epic", "gog"]
    assert dict(tabs(("itch", "gog")))["gog"] == "GOG"
