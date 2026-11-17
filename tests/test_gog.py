"""GOG: sign in with the phone (pasted address), GOG tab (step 1); install / play / uninstall
through the vendored gogdl (step 2). GOG's web API is stubbed and a stand-in gogdl script plays
the helper for installs (the workspace can't reach GOG); the real vendored gogdl is checked to
start and parse its arguments."""
import json
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

from itch_deck import library, net, paths
from itch_deck.stores import gog

CODE = "Xy9_-" * 20
ADDRESS = f"https://embed.gog.com/on_login_success?origin=client&code={CODE}"
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


def _setup(tmp_path, monkeypatch, api=None, offline=False):
    """GOG stubbed: auth.gog.com/token (CODE good, any other code 400; refresh works unless
    offline), the web API (list pages, user name, product pages)."""
    import urllib.parse
    paths.use_root(tmp_path)
    calls = []

    def get(url, key=None, timeout=20, **kw):
        calls.append((url, key))
        if offline:
            raise net.Offline("URLError: no route")
        if url.startswith(gog.TOKEN_URL):
            q = dict(urllib.parse.parse_qsl(url.split("?", 1)[1]))
            assert q["client_id"] == gog.CLIENT_ID and q["client_secret"] == gog.CLIENT_SECRET
            if q["grant_type"] == "authorization_code" and q["code"] == CODE:
                assert q["redirect_uri"] == gog.REDIRECT
                return json.dumps({"access_token": "TOKEN", "refresh_token": "SECRET",
                                   "expires_in": 3600}).encode()
            if q["grant_type"] == "refresh_token" and q["refresh_token"] == "SECRET":
                return json.dumps({"access_token": "TOKEN2", "refresh_token": "SECRET",
                                   "expires_in": 3600}).encode()
            raise net.Offline("HTTP 400")
        raise net.Offline("no stub for " + url)

    def get_json(url, key=None, timeout=20):
        calls.append((url, key))
        if offline:
            raise net.Offline("URLError: no route")
        if api:
            return api(url, key)
        if "userData" in url:
            return {"username": "omri_gog"}
        if "getFilteredProducts" in url:
            return PAGE2 if "page=2" in url else PAGE1
        if "api.gog.com/products/" in url:
            return PRODUCT
        if "api.gog.com/v2/games/" in url:       # real shape (stores-live CI, 16 Nov)
            return {"_embedded": {"features": [{"name": "Single-player", "id": "single"}] + (
                [{"name": "Controller support", "id": "controller_support"}] if "/3?" in url else [])}}
        raise net.Offline("no stub for " + url)
    monkeypatch.setattr(net, "get", get)
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
    assert st.ready() and not st.connected() and st.user() is None    # no helper to download
    assert st.login(CODE)
    assert st.connected() and st.user() == "omri_gog"
    assert oct(gog.auth_file().stat().st_mode & 0o777) == "0o600"
    assert oct(gog.auth_file().parent.stat().st_mode & 0o777) == "0o700"
    saved = json.loads(gog.auth_file().read_text())[gog.CLIENT_ID]    # gogdl's own format
    assert saved["refresh_token"] == "SECRET" and saved["loginTime"] > 0
    games = {g["id"]: g for g in st.sync()}
    assert set(games) == {"gog-1207658924", "gog-3"}          # the movie is left out
    u = games["gog-1207658924"]
    assert u["platforms"] == ["windows"] and u["store"] == "gog" and u["app_name"] == "1207658924"
    assert u["cover_url"] == "https://images-1.gog-statics.com/abc_392.jpg"
    assert games["gog-3"]["platforms"] == ["linux", "windows"]
    assert all(k == "TOKEN" for url, k in calls if "getFilteredProducts" in url)
    st.logout()
    assert not st.connected() and st.user() is None


def test_old_token_is_refreshed(tmp_path, monkeypatch):
    st, _ = _setup(tmp_path, monkeypatch)
    assert st.login(CODE)
    d = json.loads(gog.auth_file().read_text())
    d[gog.CLIENT_ID]["loginTime"] = 1                          # long expired
    gog.auth_file().write_text(json.dumps(d))
    assert st.token() == "TOKEN2"
    assert st.token() == "TOKEN2"                              # saved: no second refresh needed


def test_rejected_code_and_offline(tmp_path, monkeypatch):
    st, _ = _setup(tmp_path, monkeypatch)
    assert not st.login("w" * 60) and not st.connected()
    st, _ = _setup(tmp_path, monkeypatch, offline=True)
    with pytest.raises(gog.GogError, match="Couldn't reach GOG"):
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
    d = json.loads(gog.auth_file().read_text())
    d[gog.CLIENT_ID].update(loginTime=1, refresh_token="REVOKED")
    gog.auth_file().write_text(json.dumps(d))
    with pytest.raises(gog.GogError, match="Signed out of GOG"):   # refresh refused
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


def test_game_page_installs_like_epic():
    """v0.9.2: GOG games get Install / Play like Epic; ⚙ has no Change build (one build)."""
    import pygame as pg
    pg.display.init()
    pg.font.init()
    from itch_deck.theme import Theme
    from itch_deck.ui.scenes.game import Game
    game = {"id": "gog-3", "title": "Stardew Valley", "platforms": {"windows"}, "store": "gog",
            "size_mb": 0, "state": None, "screens": 0}
    sc = Game(Theme(pg, (1280, 800)), game)
    assert [a[0] for a in sc.actions()] == ["Install", "Options"]
    assert sc.options() == ["Hide from SCRiTCH"]                         # one build: no Change build (v0.9.23: Hide)
    assert sc.message() is None
    sc = Game(Theme(pg, (1280, 800)), dict(game, state="installed"))
    assert [a[0] for a in sc.actions()] == ["Play", "Options"]
    assert sc.options() == ["Uninstall", "Controls", "Saves"]
    both = dict(game, state="installed", platforms={"windows", "linux"})     # v0.9.5
    assert Game(Theme(pg, (1280, 800)), both).options() == ["Uninstall", "Change build",
                                                             "Controls", "Saves"]


def test_tabs_with_three_stores():
    from itch_deck.ui.scenes.library import tabs
    assert [k for k, _ in tabs(("itch", "epic", "gog"))] == ["all", "installed", "itch", "epic", "gog"]
    assert dict(tabs(("itch", "gog")))["gog"] == "GOG"


# --- step 2: install / play / uninstall ------------------------------------------------
FAKE_GOGDL = r"""
import json, os, sys, time
a = sys.argv[1:]
assert a[0] == "--auth-config-path" and os.path.isfile(a[1]), a
cmd, app = a[2], a[3]
assert os.environ["GOGDL_CONFIG_PATH"].endswith("/gog")
if cmd != "redist":
    plat = a[a.index("--platform") + 1]
    assert os.path.isfile(os.path.join(os.environ["GOGDL_CONFIG_PATH"], "heroic_gogdl", "exclude", app))
mode = os.environ.get("FAKE", "")
if cmd == "redist":
    ids = a[a.index("--ids") + 1].split(",")
    path = a[a.index("--path") + 1]
    os.makedirs(os.path.join(path, "__redist", "MSVC2017"), exist_ok=True)
    os.makedirs(os.path.join(path, "__redist", "ISI"), exist_ok=True)
    open(os.path.join(path, "__redist", "MSVC2017", "VC_redist.x86.exe"), "w").write("MZ")
    open(os.path.join(path, "__redist", "ISI", "scriptinterpreter.exe"), "w").write("MZ")
    json.dump({"build_id": "1", "HGLInstalled": ids, "depots": [
        {"dependencyId": "MSVC2017", "executable": {"path": "__redist/MSVC2017/VC_redist.x86.exe",
                                                    "arguments": "/install /quiet /norestart"}},
        {"dependencyId": "DirectX", "executable": {"path": "_CommonRedist\\DirectX\\DXSETUP.exe",
                                                   "arguments": "/silent"}},
        {"dependencyId": "ISI", "executable": {"path": "__redist/ISI/scriptinterpreter.exe",
                                               "arguments": ""}}]},
              open(os.path.join(path, ".gogdl-redist-manifest"), "w"))
    sys.exit(0)
if cmd == "info":
    if plat == "linux" and "nolinux" in mode:
        print("[LINUX] ERROR: no installer", file=sys.stderr); sys.exit(1)
    if plat == "linux":
        print(json.dumps({"disk_size": 5000, "download_size": 4000, "versionName": "1.6"}))
    else:
        need = 10 ** 15 if "huge" in mode else 7000
        print(json.dumps({"size": {"*": {"disk_size": need, "download_size": 1},
                                   "en-US": {"disk_size": 100}},
                          "buildId": os.environ.get("BUILD", "B42"), "versionName": "1.6.8",
                          "dependencies": ["MSVC2017", "DirectX"]}))
    sys.exit(0)
assert cmd == "update", cmd
path = a[a.index("--path") + 1]
if "nospace" in mode:
    print("Unable to proceed, Not enough disk space"); sys.exit(2)
if plat == "linux" and "badlinux" in mode:
    print("Traceback (most recent call last):\nTypeError: 'NoneType'", file=sys.stderr); sys.exit(1)
for i, p in enumerate((10.0, 55.5, 99.9)):
    print(f"[PROGRESS] INFO: = Progress: {p:.02f} {int(p)}/100, Running for: 00:00:0{i}, ETA: 00:01:0{i}",
          file=sys.stderr, flush=True)
    print("[PROGRESS] INFO:  + Download\t- 12.50 MiB/s (raw) / 20.00 MiB/s (decompressed)",
          file=sys.stderr, flush=True)
    time.sleep(float(os.environ.get("SLOW", "0")))
os.makedirs(os.path.join(path, "Bin"), exist_ok=True)
if plat == "linux":
    open(os.path.join(path, "start.sh"), "w").write("#!/bin/sh\necho linux\n")
else:
    open(os.path.join(path, "Bin", "Game.EXE"), "w").write("MZ")
    if "noplay" not in mode:
        open(os.path.join(path, f"goggame-{app}.info"), "w").write(json.dumps({"playTasks": [
            {"category": "document", "type": "URLTask", "link": "https://gog.com"},
            {"isPrimary": True, "type": "FileTask", "path": "bin\\game.exe",
             "arguments": "-skipintro -data 'Saves Folder'", "workingDir": "BIN"}]}))
    if "script" in mode:
        open(os.path.join(path, f"goggame-{app}.script"), "w").write("{}")
    os.makedirs(os.path.join(path, "_CommonRedist", "DirectX"), exist_ok=True)
    open(os.path.join(path, "_CommonRedist", "DirectX", "DXSETUP.exe"), "w").write("MZ")
"""


def _gog_inst(tmp_path, monkeypatch, plats=("windows",)):
    import sys
    from itch_deck import installer
    from test_install import _umu
    st, _ = _setup(tmp_path, monkeypatch)
    assert st.login(CODE)
    fake = tmp_path / "fake_gogdl.py"
    fake.write_text(FAKE_GOGDL)
    monkeypatch.setattr(gog, "helper_cmd", lambda: [sys.executable, str(fake)])
    _umu(tmp_path)                                  # GE-Proton + umu in place (no downloads)
    lib = library.Library(None)
    lib.gog = st
    g = gog.game_from_json({"id": 3, "title": "Stardew Valley", "image": "//x/s",
                            "worksOn": {"Windows": "windows" in plats, "Linux": "linux" in plats}})
    lib.games = [lib._prep(g)]
    return st, lib, installer.Installer(lib, lambda: tmp_path / "games")


def test_vendored_gogdl_starts():
    """The real vendored gogdl runs as our hidden mode and knows its commands (no network)."""
    import subprocess
    r = subprocess.run([*gog.helper_cmd(), "--version"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "1.4.0", r.stderr
    r = subprocess.run([*gog.helper_cmd(), "update", "--help"], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0 and "--platform" in r.stdout and "--path" in r.stdout
    import sys
    sys.path.insert(0, str(paths.Path(gog.__file__).parents[1] / "vendor"))
    try:
        import gogdl.dl.workers.task_executor  # noqa: F401  - needs our xdelta3 stand-in
        import gogdl_xdelta3
        with pytest.raises(RuntimeError):
            gogdl_xdelta3.patch("a", "b", "c")
    finally:
        sys.path.pop(0)


def test_gog_windows_install_play_uninstall(tmp_path, monkeypatch):
    from test_install import _wait
    st, lib, inst = _gog_inst(tmp_path, monkeypatch)
    seen = []
    real = inst._upd
    inst._upd = lambda gid, **kw: (seen.append(kw.get("progress")), real(gid, **kw))
    gog.manifest_file("3").parent.mkdir(parents=True, exist_ok=True)
    gog.manifest_file("3").write_text("{}")         # left over: must not survive a fresh install
    inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("gog-3")
    assert g["state"] == "installed", g.get("fail_reason")
    info = inst.index["gog-3"]
    assert info["store"] == "gog" and info["platform"] == "windows"
    assert info["exe"] == "Bin/Game.EXE" and info["cwd"] == "Bin"          # case-insensitive
    assert info["args"] == ["-skipintro", "-data", "Saves Folder"]
    assert info["build_id"] == "B42" and info["prefix"].endswith("_prefixes/stardew-valley")
    assert inst.exe_path("gog-3").is_file() and not info.get("setup")
    assert not gog.manifest_file("3").exists()
    prog = [p for p in seen if p not in (None, 0)]
    assert prog and prog == sorted(prog) and max(prog) <= 1
    assert (paths.LOGS / "games/stardew-valley-install.log").read_text().count("Progress") == 3
    assert [st["name"] for st in info["setup_steps"]] == ["MSVC2017", "DirectX"]
    assert info["setup_steps"][0]["args"] == ["/install", "/quiet", "/norestart"]
    assert all(gog.step_exe(st, paths.Path(info["dir"]) / "files") for st in info["setup_steps"])
    assert info["upload_id"] == "windows" and info["setup_done"] is False
    assert inst.uninstall("gog-3") and "gog-3" not in inst.index


def test_gog_linux_build_first_and_windows_fallback(tmp_path, monkeypatch):
    from test_install import _wait
    st, lib, inst = _gog_inst(tmp_path, monkeypatch, plats=("windows", "linux"))
    inst.enqueue(lib.games[0])
    _wait(inst)
    info = inst.index["gog-3"]
    assert info["platform"] == "linux" and info["exe"] == "start.sh" and "prefix" not in info
    assert os.access(inst.exe_path("gog-3"), os.X_OK)
    assert inst.uninstall("gog-3")
    monkeypatch.setenv("FAKE", "badlinux")          # Linux build breaks -> the Windows one
    inst.enqueue(lib.games[0])
    _wait(inst)
    info = inst.index["gog-3"]
    assert info["platform"] == "windows" and info["exe"] == "Bin/Game.EXE"
    assert not (paths.Path(info["dir"]) / "files" / "start.sh").exists()


def test_gog_install_fails_plainly_and_cancels(tmp_path, monkeypatch):
    from itch_deck import words
    from test_install import _wait
    st, lib, inst = _gog_inst(tmp_path, monkeypatch)
    for mode, want in (("nospace", "Not enough space"), ("huge", "Not enough space")):
        monkeypatch.setenv("FAKE", mode)
        inst.enqueue(lib.games[0])
        _wait(inst)
        g = lib.by_id("gog-3")
        assert g["state"] == "failed" and words.short(g["fail_reason"]) == want, (mode, g)
    monkeypatch.setenv("FAKE", "noplay")            # nothing to start: a code, not a guess
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert lib.by_id("gog-3")["fail_reason"] == "Code I06"
    monkeypatch.setenv("FAKE", "")
    monkeypatch.setenv("SLOW", "2")                 # cancel mid-download: gogdl is stopped
    inst.enqueue(lib.games[0])
    time.sleep(1.0)
    inst.cancel("gog-3")
    _wait(inst, secs=15)
    assert lib.by_id("gog-3")["state"] is None and "gog-3" not in inst.index
    monkeypatch.delenv("SLOW")
    monkeypatch.setenv("FAKE", "script")            # first-run setup scripts: remembered (P03)
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert inst.index["gog-3"]["setup"] is True
    lib.gog = None                                  # signed out: a plain hint
    inst.uninstall("gog-3")
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert words.short(lib.by_id("gog-3")["fail_reason"]) == "Sign in to GOG again"


def test_launch_info_reads_primary_task(tmp_path):
    (tmp_path / "Game").mkdir()
    (tmp_path / "Game" / "run.exe").write_text("MZ")
    (tmp_path / "goggame-9.info").write_text(json.dumps({"playTasks": [
        {"type": "FileTask", "path": "Game\\Run.exe", "arguments": ["-a"]},
        {"type": "FileTask", "path": "missing.exe", "isPrimary": False}]}))
    r = gog.launch_info(tmp_path, "9", "windows")
    assert r == {"exe": "Game/run.exe", "args": ["-a"], "cwd": ".", "setup": False}
    with pytest.raises(gog.GogError):
        gog.launch_info(tmp_path / "Game", "9", "linux")


def test_controls_auto_from_store_controller_flag(tmp_path, monkeypatch):
    """v0.9.3: GOG / Epic have no itch Inputs row; the store's controller flag stands in, so
    Auto picks Pad for controller games and Keys (with the mouse) for the others."""
    from itch_deck import mouse
    from itch_deck.stores import steam
    assert gog.pad_from_json({"_embedded": {"features": [{"id": "controller_support"}]}}) is True
    assert gog.pad_from_json({"_embedded": {"features": [{"id": "single"}]}}) is False
    assert gog.pad_from_json({"title": "x"}) is None
    assert steam.pad_from({"categories": [{"description": "Partial Controller Support"}]})
    assert not steam.pad_from({"categories": [{"description": "Single-player"}]})
    assert mouse.auto_mode(library.inputs_for(True)) == "gamepad"
    assert mouse.auto_mode(library.inputs_for(False)) == "keys"
    assert mouse.auto_mode(library.inputs_for(None)) == "gamepad"
    st, _ = _setup(tmp_path, monkeypatch)
    lib = library.Library(None)
    lib.gog = st
    pad_game = lib._prep(gog.game_from_json(PAGE2["products"][0]))          # id 3: controller
    keys_game = lib._prep(gog.game_from_json(PAGE1["products"][0]))         # no controller
    lib.games = [pad_game, keys_game]
    monkeypatch.setattr(lib, "_save_shots", lambda g, urls: 0)
    for g in lib.games:
        lib._fetch_gog_page(g)
    assert mouse.auto_mode(pad_game["inputs"]) == "gamepad"
    assert mouse.auto_mode(keys_game["inputs"]) == "keys"
    page = json.loads(lib._page_file(keys_game).read_text())
    page.pop("pad")                                  # saved by v0.9.2: fetched once more
    lib._page_file(keys_game).write_text(json.dumps(page))
    assert not lib._has_page_fields(keys_game) and lib._has_page_fields(pad_game)


def test_install_shows_starting_then_size(tmp_path, monkeypatch):
    """v0.9.3: "Starting…" until the first progress line, and GOG's size instead of 0 MB."""
    from test_install import _wait
    st, lib, inst = _gog_inst(tmp_path, monkeypatch)
    seen = []
    real = inst._upd
    inst._upd = lambda gid, **kw: (seen.append(dict(kw)), real(gid, **kw))
    inst.enqueue(lib.games[0])
    _wait(inst)
    phases = [k["phase"] for k in seen if "phase" in k]
    assert phases.index("queued") < phases.index("download")
    first_dl = next(i for i, k in enumerate(seen) if k.get("phase") == "download")
    assert any("size_mb" in k for k in seen[:first_dl])     # size known before the bar moves


def test_gog_first_run_setup_runs_quietly(tmp_path, monkeypatch):
    """v0.9.5: the first-run steps run through umu with their quiet arguments; GOG's setup tool
    gets the game folder as a Windows path; a failing step is reported, the rest still runs."""
    from test_install import _wait
    monkeypatch.setenv("FAKE", "script")
    st, lib, inst = _gog_inst(tmp_path, monkeypatch)
    inst.enqueue(lib.games[0])
    _wait(inst)
    info = inst.index["gog-3"]
    assert [s_["name"] for s_ in info["setup_steps"]] == ["ISI", "MSVC2017", "DirectX"]
    umu = tmp_path / "fake-umu"
    umu.write_text('#!/bin/sh\necho RAN "$@"\ncase "$1" in *DXSETUP*) exit 5;; esac\nexit 0\n')
    umu.chmod(0o755)
    files = paths.Path(info["dir"]) / "files"
    log_f = tmp_path / "setup.log"
    failed = gog.run_setup(info["setup_steps"], files, umu, {"WINEPREFIX": "/x"}, log_f)
    text = log_f.read_text()
    assert failed == ["DirectX"]
    assert "VC_redist.x86.exe /install /quiet /norestart" in text
    assert "/DIR=Z:" + str(files).replace("/", "\\") in text and "/ProductId=3" in text


def test_gog_change_version_and_update(tmp_path, monkeypatch):
    """v0.9.5: Change build = Linux / Windows (old build stays until the new one works); a newer
    GOG build marks Update, which patches in place and keeps first-run setup done."""
    from test_install import _wait
    st, lib, inst = _gog_inst(tmp_path, monkeypatch, plats=("windows", "linux"))
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert inst.index["gog-3"]["platform"] == "linux"
    monkeypatch.setenv("FAKE", "nospace")               # switching fails: Linux stays
    inst.enqueue(lib.games[0], upload_id="windows")
    _wait(inst)
    info = inst.index["gog-3"]
    assert info["platform"] == "linux" and (paths.Path(info["dir"]) / "files/start.sh").exists()
    monkeypatch.setenv("FAKE", "")
    inst.enqueue(lib.games[0], upload_id="windows")
    _wait(inst)
    info = inst.index["gog-3"]
    files = paths.Path(info["dir"]) / "files"
    assert info["platform"] == "windows" and (files / "Bin/Game.EXE").exists()
    assert not (files / "start.sh").exists() and not (paths.Path(info["dir"]) / "files.new").exists()
    info["setup_done"] = True
    assert inst.check_gog_updates() == 0                # same build: nothing
    monkeypatch.setenv("BUILD", "B43")
    assert inst.check_gog_updates() == 0                # checked a moment ago
    assert inst.check_gog_updates(force=True) == 1 and lib.by_id("gog-3")["update"]
    assert inst.update(lib.by_id("gog-3"))
    _wait(inst)
    info = inst.index["gog-3"]
    assert info["build_id"] == "B43" and info["setup_done"] is True and not info.get("update")


def test_gog_setup_tool_is_downloaded(tmp_path, monkeypatch):
    """v0.9.5b: a game with goggame-*.script asks gogdl for ISI too (v0.9.5 forgot: "not found")."""
    import sys
    from test_install import _wait
    monkeypatch.setenv("FAKE", "script")
    st, lib, inst = _gog_inst(tmp_path, monkeypatch)
    asked = []
    real = st.redist
    monkeypatch.setattr(st, "redist", lambda ids, **kw: (asked.append(list(ids)), real(ids, **kw))[1])
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert "ISI" in asked[0]
    info = inst.index["gog-3"]
    isi = next(s_ for s_ in info["setup_steps"] if s_["name"] == "ISI")
    assert gog.step_exe(isi, paths.Path(info["dir"]) / "files")


def test_file_arguments_become_windows_paths(tmp_path):
    """Eye of the Beholder: DOSBox's -conf "..\\dosbox_eob1.conf" as a full Z:\\ path."""
    (tmp_path / "DOSBOX").mkdir()
    (tmp_path / "dosbox_eob1.conf").write_text("")
    args = ["-conf", "../dosbox_eob1.conf", "-conf", "..\\missing.conf", "-noconsole", "-c", "exit"]
    out = gog.windows_args(args, tmp_path / "DOSBOX")
    assert out[1] == "Z:" + str((tmp_path / "dosbox_eob1.conf").resolve()).replace("/", "\\")
    assert out[0] == "-conf" and out[3] == "..\\missing.conf" and out[4:] == ["-noconsole", "-c", "exit"]


def test_uninstall_forgets_the_chosen_version(tmp_path, monkeypatch):
    """v0.9.8: after Uninstall, Install starts from the default (Linux first) again, not the
    version picked last time."""
    from test_install import _wait
    st, lib, inst = _gog_inst(tmp_path, monkeypatch, plats=("windows", "linux"))
    inst.enqueue(lib.games[0], upload_id="windows")
    _wait(inst)
    assert inst.index["gog-3"]["platform"] == "windows" and inst.choices["gog-3"] == "windows"
    assert inst.uninstall("gog-3") and "gog-3" not in inst.choices
