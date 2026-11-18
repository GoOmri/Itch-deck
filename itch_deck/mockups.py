"""--render-mockups: every page and state as PNGs, using fake data. No display needed."""
import os
from pathlib import Path

SIZES = [(1280, 800), (1920, 1080)]
REAL = None
ART_DIR = Path("mockup-art")        # render() points it into the output folder


def _tall_art(i):
    """A plain generated tall (2:3) picture, like GOG's box art: for the DOS tab with a blurred edge."""
    import pygame as pg
    ART_DIR.mkdir(parents=True, exist_ok=True)
    f = ART_DIR / f"tall-{i}.png"
    img = pg.Surface((300, 450))
    img.fill(((200, 60, 50), (40, 90, 170))[i % 2])
    pg.draw.circle(img, (250, 220, 90), (150, 190), 90)
    pg.draw.rect(img, (20, 20, 30), (30, 340, 240, 70), border_radius=10)
    pg.image.save(img, str(f))
    return str(f)   # --real DIR: (real library list, picked real game) instead of fake data
STATE_KEYS = ("state", "progress", "speed_mbs", "eta_s", "missing", "phase", "played", "added",
              "genre", "session")


def _wide_art(i):
    """A plain generated WIDE picture (about 16:9), like GOG's horizontal cover: it fills the DOS tile."""
    import pygame as pg
    ART_DIR.mkdir(parents=True, exist_ok=True)
    f = ART_DIR / f"wide-{i}.png"
    img = pg.Surface((640, 360))
    img.fill(((60, 120, 90), (150, 70, 120), (60, 90, 170))[i % 3])
    pg.draw.circle(img, (250, 220, 90), (320, 150), 80)
    pg.draw.rect(img, (20, 20, 30), (60, 270, 520, 60), border_radius=10)
    pg.image.save(img, str(f))
    return str(f)


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
    paths.PAGES, paths.SHOTS, paths.HLTB = root / "pages", root / "shots", root / "hltb.json"
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


def _set(scene, mode=None, **kw):
    """Mockup-only state the app normally sets each frame (free space, control mapping)."""
    for k, v in kw.items():
        setattr(scene, k, v)
    if mode:
        scene.g = dict(scene.g, controls_mode=mode)
    return scene


def _act(scene, text):
    scene.activity = text
    return scene


def _note(scene, text):
    scene.notice = text
    return scene


def _shots(t, version):
    from . import fake, pads
    from .app_play import QUIT_HINT
    from .ui import widgets as W
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
        "dos_row": ("DOS games", "SD card \u00b7 3 games", "Folder: scritch/dos"),
        "manage": "12 games \u00b7 38.4 GB", "symbols": "Auto · Steam Deck",
        "epic": "Connected as omri",
    }
    # Epic step 1 (read-only): a few sample games marked as Epic, sorted in with itch's
    epic_titles = ["Lantern Keep", "Orbit Orchard", "Salt & Signal", "Tidewright", "Velvet Vault",
                   "Wren Station"]
    epic_games = [dict(g, id="epic-" + g["id"], title=title, store="epic", state=None, url=None,
                       screens=0, size_mb=0, ttb=None)
                  for g, title in zip(lib[:: max(1, n // 6)], epic_titles)]
    both = sorted(lib + epic_games, key=lambda g: g["title"].lower())
    # GOG: a few sample games marked as GOG (installable since v0.9.2)
    gog_titles = ["Amber Atlas", "Cinder Choir", "Moss & Mortar", "Quiet Quarry Deluxe", "Rook Harbor"]
    gog_games = [dict(g, id="gog-" + g["id"], title=title, store="gog", state=None, url=None,
                      screens=0, size_mb=0, ttb=None, author="")
                 for g, title in zip(lib[1:: max(1, n // 5)], gog_titles)]
    three = sorted(both + gog_games, key=lambda g: g["title"].lower())
    picker = ("picker", "Choose a build",
              "Recommended: native Linux first, then a plain Windows zip.",
              [(name, "Recommended" if rec else "", sub) for name, sub, rec in fake.uploads()], 0)
    store_names = ["Quiet Quarry", "Moss & Rivets", "Amber Atlas", "Cinder Choir", "Bramble Run", "Night Orchard",
                   "Pocket Volcano", "Sundial Thieves", "Glass Harbour", "Tin Lantern", "Paper Tiger", "Low Tide"]
    store_items = [{"id": f"s{i}", "title": n, "size_mb": mb, "drive": "SD card" if i % 3 else "Internal",
                    "played": f"2026-11-{17 - i:02d}T20:00:00" if i % 4 else ""}
                   for i, (n, mb) in enumerate(zip(store_names, (4300, 1900, 1650, 1200, 940, 760, 520, 410, 330, 120, 64, 12)))]
    store_drives = [{"name": "SD card", "free": 112_000_000_000, "total": 256_000_000_000},
                    {"name": "Internal storage", "free": 41_000_000_000, "total": 233_000_000_000}]
    quit_dlg = ("confirm", "Quit SCRiTCH?", "Downloads in progress pause and resume next time.",
                [("A", "Quit"), ("B", "Cancel")])

    def with_flags(scene, **flags):                  # game-dict flags the app sets (hidden...)
        scene.g = dict(scene.g, **flags)             # a copy: the shared fake library stays as it is
        return scene

    def with_steam(scene, on=False):                 # Options shows Add to / Remove from Steam
        scene.g.update(steam_ok=True, on_steam=on)
        return scene

    def with_overlay(scene, ov):
        scene.overlay = ov
        return scene

    class Splash:                      # App._splash frame, for the quit-hint glyphs
        def __init__(self, msg, sub):
            self.msg, self.sub = msg, sub

        def draw(self, s):
            W.splash(t, s, self.msg, self.sub)

    from .ui.scenes.epic import EpicConnect, GogConnect, LogsShare
    from .ui.scenes.storage import StorageManager

    if pads.current == "ps":           # DualSense set: the screens where its glyphs show
        return [
            ("ps_04_library", Library(t, lib, focus=idx["Bramble Run"], syncing="bg")),
            ("ps_06j_library_filter_empty", Library(t, lib, focus=0, genre="Racing")),
            ("ps_09_library_quit", with_overlay(Library(t, lib, focus=0), quit_dlg)),
            ("ps_15_game_installed", game("Moss & Rivets",
                                          install_path="/run/media/deck/SD/itch/moss-and-rivets")),
            ("ps_21_settings", Settings(t, dict(settings_vals, symbols="Auto · PlayStation"),
                                        version, "~/.local/state/scritch/logs/app.log",
                                        focus=7)),        # Button symbols
            ("ps_25_starting", Splash("Starting Moss & Rivets…", QUIT_HINT)),
            ("ps_02b_setup_typing", Setup(t, "waiting", typing=True, typed="Xk3vQ2b7f19aa0c4d6e8")),
        ]
    return [
        ("25_starting", Splash("Starting Moss & Rivets…", QUIT_HINT)),
        ("06d_library_installed_own_filter", Library(t, lib, filt="installed", focus=0, views={
            "all": dict(sort="az", show="all", genre="Puzzle", length="short"),
            "installed": dict(sort="played", show="all", genre="any", length="any")})),
        ("01_setup_waiting", Setup(t, "waiting", qr=_qr(), url=PHONE_URL)),
        ("01b_setup_no_network", Setup(t, "waiting")),
        ("02_setup_rejected", Setup(t, "rejected", qr=_qr(), url=PHONE_URL)),
        ("02b_setup_typing", Setup(t, "waiting", typing=True, typed="Xk3vQ2b7f19aa0c4d6e8")),
        ("03_library_first_sync", Library(t, lib, syncing="first", sync_page=3)),
        ("04_library", Library(t, lib, focus=idx["Bramble Run"], syncing="bg")),
        ("05_library_scrolled", Library(t, lib, focus=n - 2)),
        ("05b_library_downloading", _act(Library(t, lib, focus=1), "Downloading 42% · Quiet Quarry (+1)")),
        ("05e_library_covers_loading", _act(Library(t, [dict(g, cover_url="x", cover_file=None)
                                                   if i % 3 else g for i, g in enumerate(lib)],
                                                  focus=1), "Covers 40/120")),
        ("05c_library_covers", _act(Library(t, lib, focus=1), "Covers 40/120")),
        ("05d_library_update", _note(_act(Library(t, lib, focus=1), "Covers 40/120"),
                                     "Update v0.3.4 available · Settings")),
        ("06_library_installed", Library(t, lib, filt="installed", focus=1)),
        ("06g_library_filtered", Library(t, lib, focus=0, length="short")),
        ("06h_library_filtered_two", Library(t, lib, focus=0, genre="Puzzle", length="short")),
        ("06b_library_recent", Library(t, lib, sort="played", focus=0)),   # Recent = a sort now
        ("06i_library_sort_filter_none", _menu(Library(t, lib, focus=0), 0)),
        ("06j_library_filter_empty", Library(t, lib, focus=0, genre="Racing")),
        ("06c_library_sort_filter", _menu(Library(t, lib, focus=0, sort="short", genre="Puzzle"), 3)),
        ("07_library_offline", Library(t, lib, focus=0, offline_since="12 Nov")),
        ("08_library_empty", Library(t, [])),
        ("09_library_quit", with_overlay(Library(t, lib, focus=0), quit_dlg)),
        ("10_library_toast", Library(t, lib, focus=idx["Grave Gardener"],
                                     toast="Grave Gardener closed right after starting. Try Change build.",
                                     toast_error=True)),
        ("10b_library_toast_code", Library(t, lib, focus=idx["Grave Gardener"],
                                           toast="Couldn't refresh the library · Code L01",
                                           toast_error=True)),
        ("15z_game_options_hide", with_overlay(game("Quiet Quarry"), (
            "menu", "Options", "", [("Change build", "", ""), ("Hide from SCRiTCH", "", "")], 1))),
        ("15za_game_hide_confirm", with_overlay(game("Quiet Quarry"), (
            "confirm", "Hide Quiet Quarry from SCRiTCH?",
            ["It stays in your store account.", "Sort & filter > Show > Hidden games brings it back."],
            [("A", "Hide"), ("B", "Cancel")], "main"))),
        ("15zb_game_hidden_options", with_overlay(with_flags(game("Quiet Quarry"), hidden=True), (
            "menu", "Options", "", [("Show in SCRiTCH", "", "")], 0))),
        ("06k_library_hidden", Library(t, [dict(g, hidden=True) for g in lib[:3]], show="hidden", focus=0)),
        ("06l_library_hidden_empty", Library(t, lib, show="hidden", focus=0)),
        ("06m_library_filter_hidden", _menu(Library(t, [dict(g, hidden=(i % 5 == 0)) for i, g in enumerate(lib)],
                                                     focus=0, show="hidden"), 1)),
        ("11_game_not_installed", game("Quiet Quarry")),
        ("11b_game_free_space", _set(game("Quiet Quarry"), free_mb=42_300)),
        ("11c_game_no_space", _set(game("Quiet Quarry"), free_mb=120)),
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
        ("15c_game_update", game("Harbor Ghosts")),
        ("15h_game_everything", _set(Game(t, dict(by["Quiet Quarry"], title="The Extraordinarily Long Adventures of Pip",
                                              author="Somebody With A Long Studio Name Games",
                                              genre="Interactive Fiction", size_mb=12_800,
                                              ttb={"main": 14.6, "done": 40}, controls_mode="keys",
                                              short_text="A very long short description that keeps going for a while, "
                                              "far past one line, to see what happens to the buttons below it. "
                                              "It even runs onto a third line, so it gets cut here and reads "
                                              "in full under About this game."),
                                     pos=(1, 30)), free_mb=4_100)),
        ("15g_game_mouse_controls", _set(game("Moss & Rivets"), mode="mouse")),
        ("15f_game_other_downloading", _act(game("Moss & Rivets"), "Downloading 42% · Quiet Quarry (+1)")),
        ("15b_game_options", with_overlay(game("Moss & Rivets"), (
            "menu", "Options", "", [("Uninstall", "", ""), ("Change build", "", ""),
                                    ("Controls", "Auto · Pad", ""), ("Saves", "", "")], 0))),
        ("15x_game_options_add_steam", with_overlay(with_steam(game("Moss & Rivets")), (
            "menu", "Options", "", [("Uninstall", "", ""), ("Change build", "", ""),
                                    ("Controls", "Auto · Pad", ""), ("Saves", "", ""),
                                    ("Add to Steam", "", "")], 4))),
        ("15y_game_options_remove_steam", with_overlay(with_steam(game("Moss & Rivets"), True), (
            "menu", "Options", "", [("Uninstall", "", ""), ("Change build", "", ""),
                                    ("Controls", "Auto · Pad", ""), ("Saves", "", ""),
                                    ("Remove from Steam", "", "")], 4))),
        ("15n_game_options_move", with_overlay(game("Moss & Rivets"), (
            "menu", "Options", "", [("Uninstall", "", ""), ("Change build", "", ""),
                                    ("Controls", "Auto · Pad", ""), ("Saves", "", ""),
                                    ("Move to internal storage", "", "")], 4))),
        ("15o_game_move_confirm", with_overlay(game("Moss & Rivets"), (
            "confirm", "Move Moss & Rivets to internal storage?",
            ["The game and its saves move together.", "You can play again when it's done."],
            [("A", "Move"), ("B", "Cancel")], "main"))),
        ("15p_game_moving", _set(Game(t, dict(by["Moss & Rivets"], state="downloading", phase="move",
                                              progress=0.45, move_to="internal storage"),
                                      pos=(idx["Moss & Rivets"] + 1, n)), phase="move")),
        ("15m_game_options_controls", with_overlay(game("Moss & Rivets"), (
            "menu", "Options", "", [("Uninstall", "", ""), ("Change build", "", ""),
                                    ("Controls", "Mouse", ""), ("Saves", "", "")], 2))),
        ("15k_game_saves", with_overlay(game("Moss & Rivets"), (
            "picker", "Saves", "Backed up after each play. A puts one back.",
            [("16 Nov, 21:40", "Latest", "48 KB"), ("16 Nov, 18:05", "", "47 KB"),
             ("15 Nov, 22:12", "Before restore", "45 KB"), ("14 Nov, 20:31", "", "31 KB"),
             ("12 Nov, 19:02", "", "12 KB")], 1))),
        ("15l_game_saves_confirm", with_overlay(game("Moss & Rivets"), (
            "confirm", "Put back the saves from 16 Nov, 18:05?",
            ["Your saves now are backed up first.", "You can go back to them."],
            [("A", "Put back"), ("B", "Cancel")], "main"))),
        ("16_game_failed", game("Grave Gardener",           # nothing to act on: the code
                                fail_reason="Code W09")),  # (same code + reason in the log)
        ("16b_game_failed_build", game("Grave Gardener", fail_reason="Try another build in Options")),
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
            [("Program to run", "MossAndRivets.exe", f"3 programs found · {pads.name('A')} to choose")] +
            [(n, "Installed" if i == 0 else "", sub) for i, (n, sub, _r) in enumerate(fake.uploads())],
            0))),
        ("21_settings", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log")),
        ("21a_settings_account", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=2)),
        ("21c_settings_storage", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=6)),
        ("21e_settings_epic", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=3)),
        ("21f_settings_epic_in", Settings(t, dict(settings_vals, epic="Connected as omri"), version, "~/.local/state/scritch/logs/app.log", focus=3)),
        ("21i_settings_downloading", _act(Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=2), "Downloading 42% · Quiet Quarry")),
        ("21g_settings_app_refresh", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=1)),
        ("21h_settings_games_controls", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=9)),
        ("26_epic_connect", EpicConnect(t, "phone", qr=_qr(), url=PHONE_URL)),
        ("26b_epic_getting_ready", EpicConnect(t, "prep", qr=_qr(), url=PHONE_URL, progress=0.4)),
        ("26c_epic_rejected", EpicConnect(t, "rejected", qr=_qr(), url=PHONE_URL)),
        ("21j_settings_gog", Settings(t, dict(settings_vals, gog="Not connected"), version, "~/.local/state/scritch/logs/app.log", focus=4)),
        ("21k_settings_help", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=12)),
        ("28_send_logs", LogsShare(t, "phone", qr=_qr(), url=PHONE_URL)),
        ("28b_send_logs_no_wifi", LogsShare(t, "nonet")),
        # --- DOS games folder (v0.9.19): the Settings row, the "Add DOS games" box, a DOS game's page ---
        ("22_storage_manager", StorageManager(t, store_items, store_drives, sort="size", focus=1)),
        ("22b_storage_selected", StorageManager(t, store_items, store_drives, selected={"s1", "s3", "s4"}, focus=3)),
        ("22c_storage_confirm", with_overlay(StorageManager(t, store_items, store_drives,
                                                            selected={"s1", "s3", "s4"}, focus=3), (
            "confirm", "Uninstall 3 games?", ["Frees about 4.0 GB.", "Windows saves are kept."],
            [("A", "Uninstall"), ("B", "Cancel")]))),
        ("22d_storage_empty", StorageManager(t, [], store_drives)),
        ("22e_storage_az", StorageManager(t, store_items, store_drives, sort="az", focus=0)),
        ("21m_dos_row", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=5)),
        ("21o_dos_howto", with_overlay(Settings(t, settings_vals, version,
                                                "~/.local/state/scritch/logs/app.log", focus=5), (
            "confirm", "Add DOS games",
            ["Copy game folders or .zip files into scritch/dos", "on your SD card, then press Refresh."],
            [("A", "Refresh"), ("B", "Cancel")], "main"))),
        ("15u_game_dos_own", Game(t, dict(gog_games[0], store="dos", state="installed", dos=True, programs=2,
                                          author="", platforms={"linux"}, controls_value="Auto \u00b7 Keys"),
                                  pos=(1, 3))),
        ("15v_game_dos_options", with_overlay(Game(t, dict(gog_games[0], store="dos", state="installed", dos=True,
                                              programs=2, author="", platforms={"linux"},
                                              controls_value="Auto \u00b7 Keys"), pos=(1, 3)), (
            "menu", "Options", "", [("Remove from library", "", ""), ("Controls", "Auto \u00b7 Keys", ""),
                                    ("Program to run", "", "")], 0))),
        ("15zd_game_dos_programs", with_overlay(Game(t, dict(gog_games[0], store="dos", state="installed", dos=True,
                                              programs=14, author="", platforms={"linux"}), pos=(1, 3)), (
            "picker", "Choose the program",
            "Pick the program that starts the game. A setup program runs once, the next time you play.",
            [(f"BLOOD{i}.EXE" if i < 9 else f"SETUP{i}.EXE", "In use" if i == 0 else "Setup" if i >= 9 else "",
              "Top folder") for i in range(14)], 11))),
        ("15w_game_dos_remove", with_overlay(Game(t, dict(gog_games[0], store="dos", state="installed", dos=True,
                                             author="", platforms={"linux"}), pos=(1, 3)), (
            "confirm", "Remove Amber Atlas?",
            ["Your game files stay in the folder.", "Sort & filter > Show > Hidden games brings it back."],
            [("A", "Remove"), ("B", "Cancel")], "main"))),
        ("27_gog_connect", GogConnect(t, "phone", qr=_qr(), url=PHONE_URL)),
        ("27b_gog_rejected", GogConnect(t, "rejected", qr=_qr(), url=PHONE_URL)),
        ("06g_library_gog_tab", Library(t, three, filt="gog", focus=0, stores=("itch", "epic", "gog"))),
        ("06h_library_dos_tab", Library(t, [dict(g, dos=True, state="installed") for g in gog_games[:2]],
                                        filt="dos", focus=0, stores=("itch", "epic", "gog"))),
        ("06n_library_dos_cards", Library(t, [dict(g, dos=True, store="dos", state="installed", cover_file=None,
                                                   title=ti, id="dos-card-" + g["id"]) for g, ti in zip(gog_games, (
            "Dave", "Eye of the Beholder II: The Legend of Darkmoon", "Keen 4", "Blake Stone"))],
                                          filt="dos", focus=0, stores=("itch", "epic", "gog"))),
        ("15zc_game_dos_gog_text", Game(t, dict(gog_games[0], store="dos", state="installed", dos=True, programs=1,
                                               author="", platforms={"linux"}, cover_file=None,
                                               title="Commander Keen", comments=None, comment_count=0,
                                               description=["Billy Blaze, eight-year-old genius, builds a spaceship "
                                                            "and sets off to save the galaxy.",
                                                            "Run, jump and pogo through hostile worlds."],
                                               details_from="GOG", controls_value="Auto · Keys"),
                                       pos=(1, 3))),
        ("06o_library_dos_tall_art", Library(t, [dict(g, dos=True, store="dos", state="installed", id="dos-tall-" + g["id"],
                                                      title=ti, cover_file=cf) for g, ti, cf in zip(
            gog_games, ("Commander Keen", "Doom II", "Dave"), (_tall_art(0), _tall_art(1), None))],
                                             filt="dos", focus=0, stores=("itch", "epic", "gog"))),
        ("06p_library_dos_wide_art", Library(t, [dict(g, dos=True, store="dos", state="installed", id="dos-wide-" + g["id"],
                                                      title=ti, cover_file=cf) for g, ti, cf in zip(
            gog_games, ("Commander Keen 3", "Blood", "Dave2", "Doom"), (_wide_art(0), _wide_art(1), None, _tall_art(0)))],
                                             filt="dos", focus=1, stores=("itch", "epic", "gog"))),
        ("15q_game_gog", Game(t, dict(gog_games[1], platforms={"windows"}, size_mb=2_300),
                              pos=(2, len(gog_games)))),
        ("15r_game_gog_downloading", Game(t, dict(gog_games[1], platforms={"windows"}, size_mb=2_300,
                                                  state="downloading", phase="download", progress=0.37,
                                                  speed_mbs=18.4, eta_s=95), pos=(2, len(gog_games)))),
        ("15t_game_gog_versions", with_overlay(
            Game(t, dict(gog_games[1], platforms={"windows", "linux"}, size_mb=2_300, state="installed"),
                 pos=(2, len(gog_games))),
            ("picker", "Choose a version", "A installs it. Your saves are kept.",
             [("Linux", "Installed", ""), ("Windows", "", "")], 1))),
        ("15s_game_gog_options", with_overlay(
            Game(t, dict(gog_games[1], platforms={"windows"}, size_mb=2_300, state="installed",
                         move_to="internal storage"), pos=(2, len(gog_games))),
            ("menu", "Options", "", [("Uninstall", "", ""), ("Controls", "Auto · Pad", ""),
                                     ("Saves", "", ""), ("Move to internal storage", "", "")], 0))),
        ("06e_library_two_stores", Library(t, both, focus=1, stores=("itch", "epic"))),
        ("06f_library_epic_tab", Library(t, both, filt="epic", focus=0, stores=("itch", "epic"))),
        ("15d_game_epic", Game(t, epic_games[1], pos=(2, len(epic_games)))),
        ("15e_game_epic_details", Game(t, dict(epic_games[1], screens=4, details_from="Epic", comments=None,
                                                details_at="2026-11-15T18:00:00",
                                                description=["Tend a moonlit orchard that drifts between planets.",
                                                             "Plant, graft and trade with the travellers who stop by. "
                                                             "Every season the orbit shifts and new fruit grows."]),
                                       pos=(2, len(epic_games)), section="shots")),
        ("21d_settings_update", Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=0)),
        ("21b_settings_disconnect", with_overlay(
            Settings(t, settings_vals, version, "~/.local/state/scritch/logs/app.log", focus=2), (
                "confirm", "Sign out of itch?",
                ["SCRiTCH forgets the key. Installed games still play.",
                 "To revoke it: itch.io → Settings → API keys."],
                [("A", "Sign out"), ("B", "Cancel")]))),
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
    global ART_DIR
    ART_DIR = out / "_art"
    files = []
    from . import pads
    for kind in ("deck", "ps"):        # every screen with Deck glyphs + a DualSense set
        pads.set_current(kind)
        for size in SIZES:
            t = Theme(pg, size)
            for name, scene in _shots(t, version):
                s = pg.Surface(size)
                scene.draw(s)
                f = out / f"{size[0]}x{size[1]}_{name}.png"
                pg.image.save(s, str(f))
                files.append(f)
    pads.set_current("deck")
    pg.quit()
    return files
