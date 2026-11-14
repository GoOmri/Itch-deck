"""itch-deck M0 spike: full-screen window, controller input, child-launch focus test."""
import argparse
import logging
import os
import subprocess
import sys
import time

from . import paths, theme
from .input import Input, A, B, UP, DOWN, START

log = logging.getLogger("itch-deck")
VERSION = "0.1.0"


def setup_logging():
    paths.LOGS.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    h = RotatingFileHandler(paths.LOGS / "app.log", maxBytes=1_000_000, backupCount=3)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h, logging.StreamHandler()])


def self_cmd(*extra):
    """Command that re-runs this program (works frozen and from source)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *extra]
    return [sys.executable, "-m", "itch_deck", *extra]


class App:
    def __init__(self, windowed=False, child=False):
        import pygame
        self.pg = pygame
        self.windowed, self.child = windowed, child
        pygame.init()
        self.inp = Input(pygame)
        self.open_display()
        self.items = ["Launch test game", "Quit"]
        self.focus = 0
        self.dialog = None          # None or "quit"
        self.status = "Press A on 'Launch test game' to test focus hand-off."
        self.last_btn = "-"
        self.running = True
        self.started = time.time()

    # --- display -------------------------------------------------------
    def open_display(self):
        pg = self.pg
        pg.display.init()
        pg.font.init()
        if self.windowed:
            self.screen = pg.display.set_mode((1280, 800))
        else:
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        pg.display.set_caption("itch-deck")
        pg.mouse.set_visible(False)
        self.theme = theme.Theme(pg, self.screen.get_size())
        log.info("display open %s driver=%s", self.screen.get_size(), pg.display.get_driver())

    def close_display(self):
        self.pg.display.quit()

    # --- child launch test --------------------------------------------
    def launch_test_game(self):
        cmd = self_cmd("--child") + (["--windowed"] if self.windowed else [])
        log.info("launch child %s", cmd)
        self.close_display()
        t0 = time.time()
        try:
            rc = subprocess.run(cmd).returncode
        except Exception as e:  # noqa: BLE001
            rc = f"error {e}"
        dt = time.time() - t0
        log.info("child exited rc=%s after %.1fs", rc, dt)
        self.open_display()
        self.inp.flush()
        self.status = f"Test game closed (exit {rc}, {dt:.0f}s). Back in itch-deck."

    # --- loop ---------------------------------------------------------
    def handle(self, act):
        self.last_btn = act
        if self.child:
            if act in (A, B):
                self.running = False
            return
        if self.dialog == "quit":
            if act == A:
                self.running = False
            elif act == B:
                self.dialog = None
            return
        if act == UP:
            self.focus = (self.focus - 1) % len(self.items)
        elif act == DOWN:
            self.focus = (self.focus + 1) % len(self.items)
        elif act == A:
            if self.items[self.focus] == "Quit":
                self.dialog = "quit"
            else:
                self.launch_test_game()
        elif act in (B, START):
            self.dialog = "quit"

    def draw(self):
        t, s = self.theme, self.screen
        if self.child:
            s.fill(t.child_bg)
            t.text(s, "TEST GAME", t.cx, t.h * 0.4, t.f_title, center=True)
            t.text(s, "If you see this, focus hand-off works. Press A or B to exit.",
                   t.cx, t.h * 0.5, t.f_body, center=True)
            self.pg.display.flip()
            return
        s.fill(t.bg)
        t.text(s, f"itch-deck  ·  M0 spike  ·  v{VERSION}", t.m, t.m, t.f_title)
        y = t.m + t.f_title.get_height() + t.u * 2
        for i, label in enumerate(self.items):
            t.button(s, label, t.m, y, focused=(i == self.focus and not self.dialog))
            y += t.btn_h + t.u
        y += t.u * 2
        pads = self.inp.pad_names() or ["no controller detected"]
        for line in [self.status, f"Controllers: {', '.join(pads)}", f"Last input: {self.last_btn}"]:
            t.text(s, line, t.m, y, t.f_body, color=t.dim)
            y += t.f_body.get_height() + t.u
        t.hint_bar(s, "A Select    B Quit    Steam menu > Exit game also works")
        if self.dialog == "quit":
            t.modal(s, "Quit itch-deck?", "A Yes    B No")
        self.pg.display.flip()

    def run(self, max_frames=None, script=None):
        clock = self.pg.time.Clock()
        frame = 0
        while self.running:
            for act in self.inp.poll():
                if act == "QUIT_EVENT":
                    self.running = False
                else:
                    self.handle(act)
            if script and frame in script:
                self.handle(script[frame])
            if self.child and time.time() - self.started > 60:
                self.running = False  # safety: never trap the user
            self.draw()
            clock.tick(60)
            frame += 1
            if max_frames and frame >= max_frames:
                break
        self.pg.quit()


def main(argv=None):
    p = argparse.ArgumentParser(prog="itch-deck")
    p.add_argument("--windowed", action="store_true", help="1280x800 window (Desktop Mode)")
    p.add_argument("--child", action="store_true", help="internal: dummy test game")
    p.add_argument("--selftest", action="store_true", help="headless smoke test")
    p.add_argument("--screenshot", help="with --selftest: save last frame as PNG")
    p.add_argument("--render-mockups", metavar="DIR", help="save every page/state as PNGs to DIR")
    a = p.parse_args(argv)
    setup_logging()
    log.info("start v%s args=%s", VERSION, argv or sys.argv[1:])

    if a.render_mockups:
        from .mockups import render
        files = render(a.render_mockups, VERSION)
        print(f"{len(files)} mockups -> {a.render_mockups}")
        return 0

    if a.selftest:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        app = App(windowed=True)
        app.run(max_frames=5, script={1: DOWN, 2: UP})
        if a.screenshot:
            import pygame
            pygame.init()
            app2 = App(windowed=True)
            app2.draw()
            pygame.image.save(app2.screen, a.screenshot)
            pygame.quit()
        print("selftest ok")
        return 0

    App(windowed=a.windowed, child=a.child).run()
    return 0
