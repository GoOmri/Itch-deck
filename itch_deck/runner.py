"""Run an installed game as a child process and hand the screen to it (gamescope focus).
Native Linux games, or Windows builds through umu-run + GE-Proton (proton.py)."""
import logging
import os
import subprocess
import sys
import time

from . import paths

log = logging.getLogger("itch-deck")
OVERLAP_S = 1.0          # keep our window up while the game maps its own (less Steam UI flicker)
HOLD_MAX_S = 300         # longest we keep "Preparing Proton…" up (first umu run downloads its runtime)
CRASH_S = 15             # a non-zero exit sooner than this = "closed right after starting"
_proc = None             # the running game, so a quit signal can stop it too


def stop_child(grace=4.0):
    """Close the running game and everything it started (Proton/Wine run several processes):
    SIGTERM to its process group, SIGKILL after `grace` seconds if it's still there."""
    import signal
    import threading
    p = _proc
    if not (p and p.poll() is None):
        return
    log.info("play: stopping game (pid %d)", p.pid)
    try:
        pgid = os.getpgid(p.pid)
    except OSError:
        pgid = None

    def send(sig):
        try:
            if pgid and pgid != os.getpgrp():
                os.killpg(pgid, sig)
            else:
                os.kill(p.pid, sig)
        except OSError:
            pass
    send(signal.SIGTERM)

    def later():
        if p.poll() is None:
            log.info("play: game still running after %.0fs, killing it", grace)
            send(signal.SIGKILL)
    t = threading.Timer(grace, later)
    t.daemon = True
    t.start()


def _bundle_dirs():
    """Where our bundled libs live: the onefile unpack dir (/tmp/_MEIxxxx) or, for the folder
    build (v0.7.4+), <app>/_internal. Also any app/ or app.old/ folder next to the launcher, so a
    previous version's folder (left in *_ORIG after an in-app update) is dropped too."""
    dirs = set()
    mei = getattr(sys, "_MEIPASS", None)
    if mei:
        dirs.add(os.path.realpath(mei))
    launcher = os.environ.get("SCRITCH_LAUNCHER")
    if launcher:
        here = os.path.dirname(os.path.realpath(launcher))
        dirs.update(os.path.join(here, d) for d in ("app", "app.old", "app.new"))
    return dirs


def _no_bundle(value, dirs=None):
    """Drop every PyInstaller lib dir from a path list. After an in-app update the *_ORIG value
    can hold the previous copy's dir, so filter both."""
    dirs = _bundle_dirs() if dirs is None else dirs

    def ours(p):
        if "/_MEI" in p:
            return True
        rp = os.path.realpath(p)
        return any(rp == d or rp.startswith(d + os.sep) for d in dirs)
    keep = [p for p in (value or "").split(":") if p and not ours(p)]
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


def command(exe, size=None, umu=None):
    """Windows .exe -> umu-run <exe>. Scripts on a card without the exec bit (exFAT) still start through sh. Unity games get
    the screen size explicitly: under gamescope some ask for 1x1 and crash (Figment, Unity 2018)."""
    if not os.access(exe, os.X_OK) and exe.suffix.lower() == ".sh":
        return ["/bin/sh", str(exe)]
    cmd = [str(umu), str(exe)] if umu and exe.suffix.lower() == ".exe" else [str(exe)]
    if size and is_unity(exe):
        cmd += ["-screen-fullscreen", "1", "-screen-width", str(size[0]),
                "-screen-height", str(size[1])]
    return cmd


WINDOW_MAX_S = 10        # longest we wait for the game's window before handing over anyway


class WindowWatch:
    """Notices when a new, visible top-level window appears on the X display (the game's), so
    we hand the screen over exactly then instead of after a fixed delay. Uses libX11 through
    ctypes (already loaded by SDL; nothing to install). ok is False when there's no X display
    or no libX11: the caller then falls back to OVERLAP_S."""

    def __init__(self, min_size=64):
        import ctypes
        import ctypes.util
        self.ok, self.min = False, min_size
        if not os.environ.get("DISPLAY"):
            return
        try:
            x = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        except OSError:
            return
        c = ctypes
        Win = c.c_ulong

        class Attrs(c.Structure):
            _fields_ = [("x", c.c_int), ("y", c.c_int), ("width", c.c_int), ("height", c.c_int),
                        ("border_width", c.c_int), ("depth", c.c_int), ("visual", c.c_void_p),
                        ("root", Win), ("class_", c.c_int), ("bit_gravity", c.c_int),
                        ("win_gravity", c.c_int), ("backing_store", c.c_int),
                        ("backing_planes", c.c_ulong), ("backing_pixel", c.c_ulong),
                        ("save_under", c.c_int), ("colormap", c.c_ulong),
                        ("map_installed", c.c_int), ("map_state", c.c_int),
                        ("all_event_masks", c.c_long), ("your_event_mask", c.c_long),
                        ("do_not_propagate_mask", c.c_long), ("override_redirect", c.c_int),
                        ("screen", c.c_void_p)]
        x.XOpenDisplay.restype = c.c_void_p
        x.XOpenDisplay.argtypes = [c.c_char_p]
        x.XDefaultRootWindow.restype = Win
        x.XDefaultRootWindow.argtypes = [c.c_void_p]
        x.XQueryTree.argtypes = [c.c_void_p, Win, c.POINTER(Win), c.POINTER(Win),
                                 c.POINTER(c.POINTER(Win)), c.POINTER(c.c_uint)]
        x.XGetWindowAttributes.argtypes = [c.c_void_p, Win, c.POINTER(Attrs)]
        x.XFree.argtypes = [c.c_void_p]
        x.XCloseDisplay.argtypes = [c.c_void_p]
        # A window can vanish between listing and asking about it; Xlib's default error
        # handler would then exit the whole app. Ignore errors instead.
        self._handler = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p)(lambda d, e: 0)
        x.XSetErrorHandler(self._handler)
        self.dpy = x.XOpenDisplay(None)
        if not self.dpy:
            return
        self.x, self.c, self.Win, self.Attrs = x, c, Win, Attrs
        self.root = x.XDefaultRootWindow(self.dpy)
        self.before = self._visible()
        self.ok = True

    def _visible(self):
        c, x = self.c, self.x
        root, parent = self.Win(), self.Win()
        kids, n = c.POINTER(self.Win)(), c.c_uint()
        if not x.XQueryTree(self.dpy, self.root, c.byref(root), c.byref(parent),
                            c.byref(kids), c.byref(n)):
            return set()
        out = set()
        a = self.Attrs()
        for i in range(n.value):
            w = kids[i]
            if x.XGetWindowAttributes(self.dpy, w, c.byref(a)) and a.map_state == 2 \
                    and a.width >= self.min and a.height >= self.min:   # 2 = IsViewable
                out.add(w)
        if kids:
            x.XFree(kids)
        return out

    def appeared(self):
        """True once a visible window exists that wasn't there when we started watching."""
        return bool(self._visible() - self.before) if self.ok else False

    def close(self):
        if self.ok:
            self.x.XCloseDisplay(self.dpy)
            self.ok = False


def run(exe, slug, on_started=None, pump=None, size=None, umu=None, extra_env=None, hold=None):
    """Start exe, call on_started() after OVERLAP_S (or sooner if it already exited), wait.
    pump() keeps our window alive during the overlap; hold() -> True keeps it up longer (Proton
    still building the prefix). Returns (returncode, seconds)."""
    global _proc
    logs = paths.LOGS / "games"
    logs.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(logs / f"{slug}.log", "w") as out:
        out.write(f"# {exe}\n# started {time.ctime(t0)}\n")
        out.flush()
        try:
            cmd = command(exe, size, umu)
            env = child_env()
            env.setdefault("APPIMAGE_EXTRACT_AND_RUN", "1")   # AppImage left packed: no FUSE needed
            if extra_env:
                env.update(extra_env)
                env.pop("PYTHONHOME", None)            # umu-run is a Python zipapp
                env.pop("PYTHONPATH", None)
                out.write("".join(f"# {k}={v}\n" for k, v in extra_env.items()))
            out.write(f"# {' '.join(cmd)}\n")
            out.flush()
            proc = subprocess.Popen(cmd, cwd=exe.parent, env=env, stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True)   # own group: closed as a whole
        except OSError as e:
            log.warning("play: could not start %s: %s", exe, e)
            out.write(f"# could not start: {e}\n")
            return None, 0.0
        _proc = proc
        log.info("play: started %s (pid %d)", exe, proc.pid)
        watch = WindowWatch()

        def waiting():
            el = time.time() - t0
            if hold and el < HOLD_MAX_S and hold():
                return True                          # Proton still building the prefix
            if watch.ok:                             # hand over when the game's window is up
                return el < WINDOW_MAX_S and not watch.appeared()
            return el < OVERLAP_S

        while proc.poll() is None and waiting():
            if pump:
                pump()
            time.sleep(0.05)
        log.info("play: handing over after %.1fs (%s)", time.time() - t0,
                 "exited" if proc.poll() is not None else
                 "window seen" if watch.ok and watch.appeared() else
                 "timer" if not watch.ok else "no window yet")
        watch.close()
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


HINTS = (  # (text in the game's log, a few plain words after "<game> couldn't start.")
    # the cause stays in the log (app.log "play: <id> crashed (<needle>)"); the player gets a
    # next step only, no technical terms (Omri 15 Nov)
    ("rand_util_win.cc", "Try another Proton in Settings."),          # needs GE-Proton 9+
    ("error while loading shared libraries", "Try another build in Options."),
    ("libfuse", "Reinstall it to fix this."),                         # AppImage without FUSE
)


def crash_hint(slug):
    """A known cause found in the game's log, or None."""
    try:
        text = (paths.LOGS / "games" / f"{slug}.log").read_text(errors="replace")[-20000:]
    except OSError:
        return None
    return next((msg for needle, msg in HINTS if needle in text), None)
