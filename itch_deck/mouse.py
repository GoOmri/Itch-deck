"""Mouse / Keys mode: while a mouse- or keyboard-only game runs, the controller drives a
virtual mouse + keyboard.

Steam gives the whole scritch tile one controller layout (plain gamepad), so games that only
read a mouse ignore the pad. Here scritch keeps reading the pad itself (SDL, no window needed)
and writes mouse/keyboard events to a virtual device made through /dev/uinput.

  Mouse: right stick -> pointer        R2 / A -> left click     L2 / X -> right click
         left stick  -> scroll wheel   D-pad  -> arrow keys     B / Start -> Esc
  Keys (keyboard games, e.g. Cosmic Express): D-pad / left stick -> arrows, A -> Space,
         B -> Esc, X -> Z, Y -> X, Menu -> Enter, L1 -> R, R1 -> Shift; right stick + R2 / L2
         still drive the mouse.

Standard library only (fcntl + struct + ctypes). Nothing here may stop a game from starting:
every failure is logged and reported back as a reason string.
"""
import ctypes
import fcntl
import logging
import os
import re
import struct
import threading
import time

log = logging.getLogger("itch-deck")

UINPUT = "/dev/uinput"
EV_SYN, EV_KEY, EV_REL = 0, 1, 2
SYN_REPORT = 0
REL_X, REL_Y, REL_WHEEL = 0, 1, 8
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
KEY_ESC, KEY_ENTER, KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN = 1, 28, 103, 105, 106, 108
KEY_SPACE, KEY_Z, KEY_X, KEY_R, KEY_LEFTSHIFT = 57, 44, 45, 19, 42
KEYS = (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE, KEY_ESC, KEY_ENTER, KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN,
        KEY_SPACE, KEY_Z, KEY_X, KEY_R, KEY_LEFTSHIFT)
STICK_KEY = 0.5                            # Keys mode: left stick past this = an arrow key held

# ioctl numbers (asm-generic): _IOW('U', 100..102, int), _IO('U', 1/2), _IOW('U', 3, uinput_setup)
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
SETUP_FMT = "HHHH80sI"                     # input_id + name[80] + ff_effects_max = 92 bytes
UI_DEV_SETUP = 0x40005503 | (struct.calcsize(SETUP_FMT) << 16)
EVENT_FMT = "llHHi"                        # struct input_event on 64-bit: timeval + type/code/value

SPEEDS = {"slow": 700, "normal": 1200, "fast": 1900}   # pixels per second at full tilt
DEADZONE = 0.15
CURVE = 2.0                                # >1 = fine control near the centre
HZ = 125
WHEEL_STEP_S = 0.12                        # one wheel notch per this many seconds at full tilt


def available():
    """(True, None) or (False, reason) without creating anything."""
    if not os.path.exists(UINPUT):
        return False, f"{UINPUT} doesn't exist"
    if not os.access(UINPUT, os.W_OK):
        return False, f"no permission to write {UINPUT}"
    return True, None


class VirtualMouse:
    def __init__(self, path=UINPUT):
        self.fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        try:
            for ev in (EV_SYN, EV_KEY, EV_REL):
                fcntl.ioctl(self.fd, UI_SET_EVBIT, ev)
            for k in KEYS:
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, k)
            for r in (REL_X, REL_Y, REL_WHEEL):
                fcntl.ioctl(self.fd, UI_SET_RELBIT, r)
            setup = struct.pack(SETUP_FMT, 0x03, 0x1209, 0x5C17, 1, b"scritch mouse", 0)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise

    def emit(self, events):
        if events:
            data = b"".join(struct.pack(EVENT_FMT, 0, 0, t, c, v) for t, c, v in events)
            os.write(self.fd, data + struct.pack(EVENT_FMT, 0, 0, EV_SYN, SYN_REPORT, 0))

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)


class Mapper:
    """Pad state -> uinput events. Pure (no I/O), so it can be tested.
    state: rx, ry, ly in -1..1; lt, rt in 0..1; a, b, x, start, up, down, left, right bools."""

    BUTTONS = (("click", BTN_LEFT), ("rclick", BTN_RIGHT), ("esc", KEY_ESC),
               ("up", KEY_UP), ("down", KEY_DOWN), ("left", KEY_LEFT), ("right", KEY_RIGHT),
               ("space", KEY_SPACE), ("enter", KEY_ENTER), ("z", KEY_Z), ("x", KEY_X),
               ("r", KEY_R), ("shift", KEY_LEFTSHIFT))

    def __init__(self, speed="normal", layout="mouse"):
        self.layout = layout                      # "mouse" | "keys"
        self.px_s = SPEEDS.get(speed, SPEEDS["normal"])
        self.rem = [0.0, 0.0]
        self.held = set()
        self.wheel = 0.0

    @staticmethod
    def _curve(v):
        a = abs(v)
        if a < DEADZONE:
            return 0.0
        return (1 if v > 0 else -1) * ((a - DEADZONE) / (1 - DEADZONE)) ** CURVE

    def step(self, st, dt):
        out = []
        for i, axis, code in ((0, "rx", REL_X), (1, "ry", REL_Y)):
            self.rem[i] += self._curve(st.get(axis, 0.0)) * self.px_s * dt
            move = int(self.rem[i])
            if move:
                self.rem[i] -= move
                out.append((EV_REL, code, move))
        keys = self.layout == "keys"
        wy = 0.0 if keys else self._curve(st.get("ly", 0.0))   # Keys: left stick = arrows
        if wy:
            self.wheel += abs(wy) * dt / WHEEL_STEP_S
            if self.wheel >= 1:
                self.wheel -= 1
                out.append((EV_REL, REL_WHEEL, -1 if wy > 0 else 1))   # stick down = scroll down
        else:
            self.wheel = 0.0
        if keys:
            lx, ly = st.get("lx", 0.0), st.get("ly", 0.0)
            want = {
                "click": st.get("rt", 0) > 0.5, "rclick": st.get("lt", 0) > 0.5,
                "esc": st.get("b"), "enter": st.get("start"),
                "up": st.get("up") or ly < -STICK_KEY, "down": st.get("down") or ly > STICK_KEY,
                "left": st.get("left") or lx < -STICK_KEY, "right": st.get("right") or lx > STICK_KEY,
                "space": st.get("a"), "z": st.get("x"), "x": st.get("y"),
                "r": st.get("l1"), "shift": st.get("r1"),
            }
        else:
            want = {
                "click": st.get("rt", 0) > 0.5 or st.get("a"),
                "rclick": st.get("lt", 0) > 0.5 or st.get("x"),
                "esc": st.get("b") or st.get("start"),
                "up": st.get("up"), "down": st.get("down"),
                "left": st.get("left"), "right": st.get("right"),
            }
        for name, code in self.BUTTONS:
            if bool(want.get(name)) != (name in self.held):
                on = bool(want.get(name))
                out.append((EV_KEY, code, 1 if on else 0))
                (self.held.add if on else self.held.discard)(name)
        return out

    def release_all(self):
        out = [(EV_KEY, code, 0) for name, code in self.BUTTONS if name in self.held]
        self.held.clear()
        return out


def _sdl():
    """The SDL2 library pygame already loaded (PyInstaller unpacks it under _MEI), so its
    SDL_GameControllerUpdate refreshes the same pads without a window or event pump."""
    try:
        with open("/proc/self/maps") as f:
            for line in f:
                path = line.split()[-1] if line.strip() else ""
                if re.search(r"/libSDL2-2[.-][^/]*\.so[^/]*$", path) or path.endswith("/libSDL2-2.0.so.0"):
                    lib = ctypes.CDLL(path)
                    lib.SDL_GameControllerUpdate.restype = None
                    return lib
    except (OSError, AttributeError):
        pass
    return None


def read_pads(pg, pads):
    """Combined state of every open pad: the biggest stick value wins (Steam shows the same
    controller twice: the Deck's own + the Steam Virtual Gamepad), buttons are OR'ed."""
    st = {"rx": 0.0, "ry": 0.0, "lx": 0.0, "ly": 0.0, "lt": 0.0, "rt": 0.0}
    btn = {"a": pg.CONTROLLER_BUTTON_A, "b": pg.CONTROLLER_BUTTON_B, "x": pg.CONTROLLER_BUTTON_X,
           "y": pg.CONTROLLER_BUTTON_Y, "l1": pg.CONTROLLER_BUTTON_LEFTSHOULDER,
           "r1": pg.CONTROLLER_BUTTON_RIGHTSHOULDER,
           "start": pg.CONTROLLER_BUTTON_START, "back": pg.CONTROLLER_BUTTON_BACK,
           "up": pg.CONTROLLER_BUTTON_DPAD_UP,
           "down": pg.CONTROLLER_BUTTON_DPAD_DOWN, "left": pg.CONTROLLER_BUTTON_DPAD_LEFT,
           "right": pg.CONTROLLER_BUTTON_DPAD_RIGHT}
    axes = {"rx": pg.CONTROLLER_AXIS_RIGHTX, "ry": pg.CONTROLLER_AXIS_RIGHTY,
            "lx": pg.CONTROLLER_AXIS_LEFTX, "ly": pg.CONTROLLER_AXIS_LEFTY, "lt": pg.CONTROLLER_AXIS_TRIGGERLEFT,
            "rt": pg.CONTROLLER_AXIS_TRIGGERRIGHT}
    for c in list(pads.values()):
        try:
            for k, a in axes.items():
                v = c.get_axis(a) / 32767.0
                if abs(v) > abs(st[k]):
                    st[k] = max(-1.0, min(1.0, v))
            for k, b in btn.items():
                st[k] = st.get(k) or bool(c.get_button(b))
        except Exception:  # noqa: BLE001  - a pad unplugged mid-game
            continue
    return st


class QuitCombo:
    """Hold View + Menu (DualSense: Create + Options) for HOLD_S while a game runs -> on_quit().
    For games that ignore the pad, so there's always a way back to scritch. Fed by mouse mode's
    loop when that runs (one reader of the pads), else by its own thread."""
    HOLD_S = 2.0

    def __init__(self, pg, pads, on_quit):
        self.pg, self.pads, self.on_quit = pg, pads, on_quit
        self.t0 = None
        self.fired = False
        self._stop = threading.Event()
        self._thread = None

    def feed(self, st, now):
        if self.fired:
            return
        if st.get("back") and st.get("start"):
            if self.t0 is None:
                self.t0 = now
            elif now - self.t0 >= self.HOLD_S:
                self.fired = True
                log.info("play: quit shortcut held, closing the game")
                self.on_quit()
        else:
            self.t0 = None

    def start(self):
        """Own polling thread (when mouse mode isn't running)."""
        sdl = _sdl()
        if not sdl or not self.pads:
            log.info("play: quit shortcut off (%s)", "no SDL" if not sdl else "no controller")
            return

        def run():
            try:
                while not self._stop.wait(0.05):
                    sdl.SDL_GameControllerUpdate()
                    self.feed(read_pads(self.pg, self.pads), time.monotonic())
            except Exception:  # noqa: BLE001
                log.exception("quit shortcut stopped")
        self._thread = threading.Thread(target=run, daemon=True, name="quitcombo")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(1)


class MouseMode:
    """Runs the mapper on a thread for the length of one game."""

    def __init__(self, pg, pads, speed="normal", layout="mouse"):
        self.pg, self.pads, self.mapper = pg, pads, Mapper(speed, layout)
        self.combo = None          # QuitCombo fed from this loop while mouse mode runs
        self.dev = self.sdl = self._thread = None
        self._stop = threading.Event()
        self.error = None

    def start(self):
        """True if running; else self.error says why (the game starts either way)."""
        ok, why = available()
        if not ok:
            self.error = why
        else:
            self.sdl = _sdl()
            if not self.sdl:
                self.error = "couldn't find SDL to read the controller"
            elif not self.pads:
                self.error = "no controller connected"
            else:
                try:
                    self.dev = VirtualMouse()
                except OSError as e:
                    log.warning("mouse mode: uinput: %s", e)
                    self.error = "couldn't create the virtual mouse"
        if self.error:
            log.warning("mouse mode: off (%s)", self.error)
            return False
        self._thread = threading.Thread(target=self._run, daemon=True, name="mouse")
        self._thread.start()
        log.info("%s mode: on (%d pad(s), %d px/s)", self.mapper.layout, len(self.pads),
                 self.mapper.px_s)
        return True

    def _run(self):
        last = time.monotonic()
        try:
            while not self._stop.wait(1 / HZ):
                now = time.monotonic()
                self.sdl.SDL_GameControllerUpdate()
                st = read_pads(self.pg, self.pads)
                if self.combo:
                    self.combo.feed(st, now)
                self.dev.emit(self.mapper.step(st, now - last))
                last = now
        except Exception:  # noqa: BLE001
            log.exception("mouse mode stopped")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(1)
        if self.dev:
            try:
                self.dev.emit(self.mapper.release_all())
            except OSError:
                pass
            self.dev.close()
            self.dev = None
            log.info("mouse mode: off")


def auto_mode(inputs):
    """From itch's Inputs row: 'gamepad' if a pad/controller/joystick is listed (or nothing is),
    else 'keys' if a keyboard is (Keys mode keeps the mouse too), else 'mouse' (mouse / touch)."""
    low = [i.lower() for i in inputs or []]
    if not low:
        return "gamepad"
    if any(k in i for i in low for k in ("gamepad", "controller", "joystick")):
        return "gamepad"
    if any("keyboard" in i for i in low):
        return "keys"
    if any(k in i for i in low for k in ("mouse", "touch")):
        return "mouse"
    return "gamepad"
