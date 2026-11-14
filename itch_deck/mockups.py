"""--render-mockups: every page and state as PNGs, using fake data. No display needed."""
import os
from pathlib import Path

SIZES = [(1280, 800), (1920, 1080)]


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

    lib = fake.library()
    by = {g["title"]: g for g in lib}
    idx = {g["title"]: i for i, g in enumerate(lib)}
    n = len(lib)

    def game(title, **kw):
        return Game(t, by[title], pos=(idx[title] + 1, n), **kw)

    settings_vals = {
        "install_label": "SD card", "install_path": "/run/media/deck/SD/itch", "free": "112 GB",
        "proton": "GE-Proton9-20", "prefix_size": "1.2 GB", "last_sync": "today 11:02",
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
        ("01_setup_waiting", Setup(t, "waiting")),
        ("02_setup_rejected", Setup(t, "rejected")),
        ("02b_setup_typing", Setup(t, "waiting", typing=True, typed="Xk3vQ2b7f19aa0c4d6e8")),
        ("03_library_first_sync", Library(t, lib, syncing="first", sync_page=3)),
        ("04_library", Library(t, lib, focus=idx["Bramble Run"], syncing="bg")),
        ("05_library_scrolled", Library(t, lib, focus=n - 2)),
        ("05b_library_downloading", _act(Library(t, lib, focus=1), "Downloading 42% · Quiet Quarry (+1)")),
        ("05c_library_covers", _act(Library(t, lib, focus=1), "Covers 40/120")),
        ("05d_library_update", _note(_act(Library(t, lib, focus=1), "Covers 40/120"),
                                     "Update v0.3.4 available · Settings")),
        ("06_library_installed", Library(t, lib, filt="installed", focus=1)),
        ("07_library_offline", Library(t, lib, focus=0, offline_since="12 Nov")),
        ("08_library_empty", Library(t, [])),
        ("09_library_quit", with_overlay(Library(t, lib, focus=0), quit_dlg)),
        ("10_library_toast", Library(t, lib, focus=idx["Grave Gardener"],
                                     toast="Grave Gardener closed right after starting. Try Change build.",
                                     toast_error=True)),
        ("11_game_not_installed", game("Quiet Quarry")),
        ("12_game_downloading", game("Hollow Lighthouse")),
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
        ("16_game_failed", game("Grave Gardener",
                                fail_reason="No runnable file found in the download (Windows build).")),
        ("17_game_browser", game("Frog Parliament")),
        ("18_game_not_playable", game("Velvet Static")),
        ("19_game_picker", with_overlay(game("Quiet Quarry"), picker)),
        ("20_game_confirm_uninstall", with_overlay(game("Starfall Ferry"), (
            "confirm", "Uninstall Starfall Ferry?", ["Frees 412 MB.", "Your saves are kept."],
            [("A", "Uninstall"), ("B", "Cancel")]))),
        ("22_game_sd_missing", game("Pocket Volcano")),
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
    ]


def render(outdir, version):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame as pg
    from .theme import Theme
    pg.init()
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
