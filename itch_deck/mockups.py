"""--render-mockups: every page and state as PNGs, using fake data. No display needed."""
import os
from pathlib import Path

SIZES = [(1280, 800), (1920, 1080)]
REAL = None   # --real DIR: (real library list, picked real game) instead of fake data
STATE_KEYS = ("state", "progress", "speed_mbs", "eta_s", "missing", "phase", "played", "added",
              "genre", "session")


def load_real(root, pick=None):
    """Omri's cached itch data (library.json, covers/, pages/, shots/ — never in the repo).
    Returns (games, one game for the game-page states: `pick` title/id, else random)."""
    import os
    import random
    from pathlib import Path
    from . import paths
    from .library import Library
    root = Path(root)
    paths.LIBRARY, paths.COVERS = root / "library.json", root / "covers"
    paths.PAGES, paths.SHOTS = root / "pages", root / "shots"
    lib = Library(None)
    for g in lib.games:
        lib._apply_page(g)
    games = lib.games
    pick = pick or os.environ.get("SCRITCH_GAME")
    if pick:
        g = next(x for x in games if pick.lower() in (x["id"], x["title"].lower()))
    else:
        ok = [x for x in games if x.get("screens", 0) >= 3 and x.get("description")
              and x.get("comments") and x["platforms"] & {"linux", "windows"}]  # every state has content
        g = random.choice(ok)
    print(f"real data: {len(games)} games, game page = {g['title']} ({g['id']})")
    return games, g


def _realify(lib):
    """Real games in the grid, wearing the fake states (installed, downloading, ...) by position."""
    games, _ = REAL
    out = []
    for i, r in enumerate(games):
        g = dict(r)
        g.update({k: lib[i % len(lib)][k] for k in STATE_KEYS if k in lib[i % len(lib)]})
        out.append(g)
    return out


def _menu(scene, focus):
    scene.overlay = ("menu",)                  # menu_open reads overlay[4] only via menu_next
    scene.menu_open(focus)
    return scene


def _act(scene, text):
    scene.activity = text
    return scene


def _note(scene, text):
    scene.notice = text
    return scene


def _shots(t, version):
    from . import fake
    from .ui.scenes.game import Game
    from .ui.scenes.library import Library
    from .ui.scenes.settings import Settings
    from .ui.scenes.setup import Setup

    PHONE_URL = "192.168.1.20:41817/?t=Xb2kQ9fA3mE"

    def _qr():
        import qrcode
        q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data("http://" + PHONE_URL)
        q.make(fit=True)
        return q.get_matrix()

    lib = fake.library()
    by = {g["title"]: g for g in lib}
    idx = {g["title"]: i for i, g in enumerate(lib)}
    n = len(lib)

    def game(title, **kw):
        if REAL:                         # the picked real game, in this fake game's state
            g = dict(REAL[1])
            fp = by[title]["platforms"]
            if not fp & {"linux", "windows"}:          # browser / not playable: a real one like it
                want = (lambda x: x["platforms"] & {"html", "linux", "windows"} == {"html"}) \
                    if "html" in fp else \
                       (lambda x: not x["platforms"] & {"linux", "windows", "html"})
                g = dict(next((x for x in REAL[0] if want(x)), g))
            g.update({k: by[title][k] for k in STATE_KEYS if k in by[title]})
            g["size_mb"] = g.get("size_mb") or by[title]["size_mb"]
            return Game(t, g, pos=(idx[title] + 1, n), **kw)
        return Game(t, by[title], pos=(idx[title] + 1, n), **kw)

    if REAL:
        lib = _realify(lib)
        n = len(lib)

    settings_vals = {
        "install_label": "SD card", "install_path": "/run/media/deck/SD/itch", "free": "112 GB",
        "proton": "Auto · GE-Proton9-20", "prefix_size": "2 games · 1.2 GB", "last_sync": "today 11:02", "itch_user": "omri",
        "update": (f"v{version[:-1]}9 available", "Update"),
    }
    picker = ("picker", "Choose a build",
              "Recommended: native Linux first, then a plain Windows zip.",
              [(name, "Recommended" if rec else "", sub) for name, sub, rec in fake.uploads()], 0)
    quit_dlg = ("confirm", "Quit SCRiTCH?", "Downloads in progress pause and resume next time.",
                [("A", "Quit"), ("B", "Cancel")])

    def with_overlay(scene, ov):
        scene.overlay = ov
        return scene

    return [
        ("01_setup_waiting", Setup(t, "waiting", qr=_qr(), url=PHONE_URL)),
        ("01b_setup_no_network", Setup(t, "waiting")),
        ("02_setup_rejected", Setup(t, "rejected", qr=_qr(), url=PHONE_URL)),
        ("02b_setup_typing", Setup(t, "waiting", typing=True, typed="Xk3vQ2b7f19aa0c4d6e8")),
        ("03_library_first_sync", Library(t, lib, syncing="first", sync_page=3)),
        ("04_library", Library(t, lib, focus=idx["Bramble Run"], syncing="bg")),
        ("05_library_scrolled", Library(t, lib, focus=n - 2)),
        ("05b_library_downloading", _act(Library(t, lib, focus=1), "Downloading 42% · Quiet Quarry (+1)")),
        ("05c_library_covers", _act(Library(t, lib, focus=1), "Covers 40/120")),
        ("05d_library_update", _note(_act(Library(t, lib, focus=1), "Covers 40/120"),
                                     "Update v0.3.4 available · Settings")),
        ("06_library_installed", Library(t, lib, filt="installed", focus=1)),
        ("06b_library_recent", Library(t, lib, filt="recent", focus=0)),
        ("06c_library_sort_filter", _menu(Library(t, lib, focus=0, sort="added", genre="Puzzle"), 2)),
        ("07_library_offline", Library(t, lib, focus=0, offline_since="12 Nov")),
        ("08_library_empty", Library(t, [])),
        ("09_library_quit", with_overlay(Library(t, lib, focus=0), quit_dlg)),
        ("10_library_toast", Library(t, lib, focus=idx["Grave Gardener"],
                                     toast="Grave Gardener closed right after starting. Try Change build.",
                                     toast_error=True)),
        ("11_game_not_installed", game("Quiet Quarry")),
        ("12_game_downloading", game("Hollow Lighthouse")),
        ("12c_game_queued", game("Paper Comet", behind=True)),
        ("12b_game_offline", game("Quiet Quarry", offline=True)),
        ("11b_game_screenshots", game("Quiet Quarry", section="shots", shot=1)),
        ("11c_game_description", game("Quiet Quarry", section="desc")),
        ("11d_game_screenshot_view", with_overlay(game("Quiet Quarry", section="shots", shot=1),
                                                  ("viewer",))),
        ("11e_game_comments", game("Quiet Quarry", section="comments")),
        ("13_game_installing", game("Ninefold Tower", phase="installing")),
        ("14_game_preparing_proton", game("Orbit Bakery", phase="proton")),
        ("15_game_installed", game("Moss & Rivets",
                                   install_path="/run/media/deck/SD/itch/moss-and-rivets")),
        ("15b_game_options", with_overlay(game("Moss & Rivets"), (
            "menu", "Options", "", [("Uninstall", "", ""), ("Change build", "", ""),
                                    ("Controls", "", "")], 0))),
        ("16_game_failed", game("Grave Gardener",
                                fail_reason="No runnable file found in the download (Windows build).")),
        ("17_game_browser", game("Frog Parliament")),
        ("18_game_not_playable", game("Velvet Static")),
        ("19_game_picker", with_overlay(game("Quiet Quarry"), picker)),
        ("20_game_confirm_uninstall", with_overlay(game("Starfall Ferry"), (
            "confirm", "Uninstall Starfall Ferry?", ["Frees 412 MB.", "Your saves are kept."],
            [("A", "Uninstall"), ("B", "Cancel")]))),
        ("22_game_sd_missing", game("Pocket Volcano")),
        ("22b_game_sd_missing_install", game("Cinder Choir", card_out=True)),
        ("23_game_program_picker", with_overlay(game("Moss & Rivets"), (
            "picker", "Choose the program", "Pick the file that starts the game. Helpers like "
            "crash reporters are left out.",
            [("MossAndRivets.exe", "In use", "Top folder"), ("Launcher.exe", "", "Top folder"),
             ("MossAndRivets-DX11.exe", "", "bin")], 0))),
        ("24_game_picker_with_program", with_overlay(game("Moss & Rivets"), (
            "picker", "Choose a build", "A installs it. Saves of Windows builds are kept separately.",
            [("Program to run", "MossAndRivets.exe", "3 programs found · A to choose")] +
            [(n, "Installed" if i == 0 else "", sub) for i, (n, sub, _r) in enumerate(fake.uploads())],
            0))),
        ("21_settings", Settings(t, settings_vals, version, "~/.local/state/itch-deck/logs/app.log")),
        ("21b_settings_disconnect", with_overlay(
            Settings(t, settings_vals, version, "~/.local/state/itch-deck/logs/app.log"), (
                "confirm", "Disconnect itch?",
                ["scritch forgets the key. Installed games still play.",
                 "To revoke it: itch.io → Settings → API keys."],
                [("A", "Disconnect"), ("B", "Cancel")]))),
    ]


def render(outdir, version, real=None):
    global REAL
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame as pg
    from .theme import Theme
    pg.init()
    REAL = load_real(real) if real else None
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for size in SIZES:
        t = Theme(pg, size)
        for name, scene in _shots(t, version):
            s = pg.Surface(size)
            scene.draw(s)
            f = out / f"{size[0]}x{size[1]}_{name}.png"
            pg.image.save(s, str(f))
            files.append(f)
    pg.quit()
    return files
