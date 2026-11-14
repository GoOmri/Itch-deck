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
_proc = None             # the running game, so a quit signal can stop it too


def stop_child():
    p = _proc
    if p and p.poll() is None:
        log.info("play: stopping game (pid %d)", p.pid)
        p.terminate()


def _no_bundle(value):
    """Drop every PyInstaller unpack dir (/tmp/_MEIxxxx) from a path list. After an in-app
    update the *_ORIG value can hold the previous copy's dir, so filter both."""
    keep = [p for p in (value or "").split(":") if p and "/_MEI" not in p]
    return ":".join(keep)


def child_env(base=None):
    """Our environment minus what PyInstaller adds: its LD_LIBRARY_PATH points at our bundled
    SDL/libstdc++/libssl, which breaks games (Figment crashed in Vulkan init with them)."""
    env = dict(os.environ if base is None else base)
    for var in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        orig = env.pop(var + "_ORIG", None)
        val = _no_bundle(orig if orig is not None else env.get(var))
        if val:
            env[var] = val
        else:
            env.pop(var, None)
    return env


def is_unity(exe):
    return (exe.parent / f"{exe.stem}_Data").is_dir() or (exe.parent / "UnityPlayer.so").exists()


def command(exe, size=None):
    """Scripts on a card without the exec bit (exFAT) still start through sh. Unity games get
    the screen size explicitly: under gamescope some ask for 1x1 and crash (Figment, Unity 2018)."""
    if not os.access(exe, os.X_OK) and exe.suffix.lower() == ".sh":
        return ["/bin/sh", str(exe)]
    cmd = [str(exe)]
    if size and is_unity(exe):
        cmd += ["-screen-fullscreen", "1", "-screen-width", str(size[0]),
                "-screen-height", str(size[1])]
    return cmd


def run(exe, slug, on_started=None, pump=None, size=None):
    global _proc
    """Start exe, call on_started() after OVERLAP_S (or sooner if it already exited), wait.
    pump() keeps our window alive during the overlap. Returns (returncode, seconds)."""
    logs = paths.LOGS / "games"
    logs.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(logs / f"{slug}.log", "w") as out:
        out.write(f"# {exe}\n# started {time.ctime(t0)}\n")
        out.flush()
        try:
            cmd = command(exe, size)
            out.write(f"# {' '.join(cmd)}\n")
            out.flush()
            proc = subprocess.Popen(cmd, cwd=exe.parent, env=child_env(), stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        except OSError as e:
            log.warning("play: could not start %s: %s", exe, e)
            out.write(f"# could not start: {e}\n")
            return None, 0.0
        _proc = proc
        log.info("play: started %s (pid %d)", exe, proc.pid)
        while proc.poll() is None and time.time() - t0 < OVERLAP_S:
            if pump:
                pump()
            time.sleep(0.03)
        if on_started:
            on_started()
        rc = proc.wait()
        _proc = None
        secs = time.time() - t0
        out.write(f"# exit code {rc} after {secs:.0f}s\n")
    log.info("play: %s exited %s after %.0fs", slug, rc, secs)
    return rc, secs


def crashed(rc, secs):
    return rc is None or (rc != 0 and secs < CRASH_S) or secs < 3
