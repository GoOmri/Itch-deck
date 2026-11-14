"""Mouse mode: while a mouse-only game runs, the controller drives a virtual mouse.

Steam gives the whole scritch tile one controller layout (plain gamepad), so games that only
read a mouse ignore the pad. Here scritch keeps reading the pad itself (SDL, no window needed)
and writes mouse/keyboard events to a virtual device made through /dev/uinput.

  right stick -> pointer        R2 / A -> left click     L2 / X -> right click
  left stick  -> scroll wheel   D-pad  -> arrow keys     B / Start -> Esc

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
KEYS = (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE, KEY_ESC, KEY_ENTER, KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN)

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
               ("up", KEY_UP), ("down", KEY_DOWN), ("left", KEY_LEFT), ("right", KEY_RIGHT))

    def __init__(self, speed="normal"):
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
        wy = self._curve(st.get("ly", 0.0))
        if wy:
            self.wheel += abs(wy) * dt / WHEEL_STEP_S
            if self.wheel >= 1:
                self.wheel -= 1
                out.append((EV_REL, REL_WHEEL, -1 if wy > 0 else 1))   # stick down = scroll down
        else:
            self.wheel = 0.0
        want = {
            "click": st.get("rt", 0) > 0.5 or st.get("a"),
            "rclick": st.get("lt", 0) > 0.5 or st.get("x"),
            "esc": st.get("b") or st.get("start"),
            "up": st.get("up"), "down": st.get("down"),
            "left": st.get("left"), "right": st.get("right"),
        }
        for name, code in self.BUTTONS:
            if bool(want[name]) != (name in self.held):
                out.append((EV_KEY, code, 1 if want[name] else 0))
                (self.held.add if want[name] else self.held.discard)(name)
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
    st = {"rx": 0.0, "ry": 0.0, "ly": 0.0, "lt": 0.0, "rt": 0.0}
    btn = {"a": pg.CONTROLLER_BUTTON_A, "b": pg.CONTROLLER_BUTTON_B, "x": pg.CONTROLLER_BUTTON_X,
           "start": pg.CONTROLLER_BUTTON_START, "up": pg.CONTROLLER_BUTTON_DPAD_UP,
           "down": pg.CONTROLLER_BUTTON_DPAD_DOWN, "left": pg.CONTROLLER_BUTTON_DPAD_LEFT,
           "right": pg.CONTROLLER_BUTTON_DPAD_RIGHT}
    axes = {"rx": pg.CONTROLLER_AXIS_RIGHTX, "ry": pg.CONTROLLER_AXIS_RIGHTY,
            "ly": pg.CONTROLLER_AXIS_LEFTY, "lt": pg.CONTROLLER_AXIS_TRIGGERLEFT,
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


class MouseMode:
    """Runs the mapper on a thread for the length of one game."""

    def __init__(self, pg, pads, speed="normal"):
        self.pg, self.pads, self.mapper = pg, pads, Mapper(speed)
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
        log.info("mouse mode: on (%d pad(s), %d px/s)", len(self.pads), self.mapper.px_s)
        return True

    def _run(self):
        last = time.monotonic()
        try:
            while not self._stop.wait(1 / HZ):
                now = time.monotonic()
                self.sdl.SDL_GameControllerUpdate()
                self.dev.emit(self.mapper.step(read_pads(self.pg, self.pads), now - last))
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
    """'mouse' when itch lists only mouse/keyboard/touch inputs, else 'gamepad'."""
    low = [i.lower() for i in inputs or []]
    if not low:
        return "gamepad"
    pad = any(k in i for i in low for k in ("gamepad", "controller", "joystick"))
    pointer = any(k in i for i in low for k in ("mouse", "touch"))
    return "mouse" if pointer and not pad else "gamepad"
