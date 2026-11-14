"""Run an installed game as a child process and hand the screen to it (gamescope focus).
M3: native Linux games. M4 adds umu-run + GE-Proton for Windows builds."""
import logging
import os
import subprocess
import sys
import time

from . import paths

log = logging.getLogger("itch-deck")
OVERLAP_S = 1.0          # keep our window up while the game maps its own (less Steam UI flicker)
CRASH_S = 15             # a non-zero exit sooner than this = "closed right after starting"


def child_env():
    """Our environment minus what PyInstaller adds: its LD_LIBRARY_PATH points at our bundled
    SDL/libs, which would break games that ship their own."""
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        for var in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
            orig = env.pop(var + "_ORIG", None)
            if orig is not None:
                env[var] = orig
            elif var == "LD_LIBRARY_PATH":
                env.pop(var, None)
    return env


def command(exe):
    """Scripts on a card without the exec bit (exFAT) still start through sh."""
    if not os.access(exe, os.X_OK) and exe.suffix.lower() == ".sh":
        return ["/bin/sh", str(exe)]
    return [str(exe)]


def run(exe, slug, on_started=None, pump=None):
    """Start exe, call on_started() after OVERLAP_S (or sooner if it already exited), wait.
    pump() keeps our window alive during the overlap. Returns (returncode, seconds)."""
    logs = paths.LOGS / "games"
    logs.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(logs / f"{slug}.log", "w") as out:
        out.write(f"# {exe}\n# started {time.ctime(t0)}\n")
        out.flush()
        try:
            proc = subprocess.Popen(command(exe), cwd=exe.parent, env=child_env(), stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        except OSError as e:
            log.warning("play: could not start %s: %s", exe, e)
            out.write(f"# could not start: {e}\n")
            return None, 0.0
        log.info("play: started %s (pid %d)", exe, proc.pid)
        while proc.poll() is None and time.time() - t0 < OVERLAP_S:
            if pump:
                pump()
            time.sleep(0.03)
        if on_started:
            on_started()
        rc = proc.wait()
        secs = time.time() - t0
        out.write(f"# exit code {rc} after {secs:.0f}s\n")
    log.info("play: %s exited %s after %.0fs", slug, rc, secs)
    return rc, secs


def crashed(rc, secs):
    return rc is None or (rc != 0 and secs < CRASH_S) or secs < 3
