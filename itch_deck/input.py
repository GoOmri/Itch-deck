"""Turns SDL controller + keyboard events into actions. Any pad works."""
import logging
import os
import time

from . import pads as PADS

UP, DOWN, LEFT, RIGHT, A, B, X, Y, START = "UP", "DOWN", "LEFT", "RIGHT", "A", "B", "X", "Y", "START"
L1, R1, L2, R2, BACK = "L1", "R1", "L2", "R2", "BACK"
TEXT, BKSP, ENTER, PASTE = "TEXT", "BKSP", "ENTER", "PASTE"   # text-entry mode only
DEADZONE = 16000
TRIGGER_ON = 20000
log = logging.getLogger("scritch")
REPEAT_MS = (300, 170)  # hold: first delay, then repeat every 170 ms (stick, D-pad, arrows)
DIRS = (UP, DOWN, LEFT, RIGHT)
FAST_MS = (300, 85)     # L2/R2 held: page jumps repeat at the old fast speed


def _ms():
    """Milliseconds for key repeat. Not pygame.time.get_ticks: that stays 0 unless pygame.init()
    ran, and the app skips pygame.init() (it opens the audio device; SCRiTCH has no sound)."""
    return int(time.monotonic() * 1000)


class Input:
    kinds, _guessed, last_pad = {}, frozenset(), None   # defaults; __init__/_kinds replace them

    def __init__(self, pg):
        self.pg = pg
        from pygame._sdl2 import controller
        self.ctl = controller
        controller.init()
        self.pads = {}
        self.kinds = {}            # instance id -> "deck" / "ps" / "xbox" (pads.resolve)
        self._guessed = set()      # ids that fell back to "xbox": asked again on rescan
        self.last_pad = None       # instance id of the pad pressed last (glyphs follow it)
        for i in range(controller.get_count()):
            self._add(i)
        self.stick_dir = None
        self.stick_next = 0
        self.text_mode = False
        self.btn_dir = None        # direction held on a D-pad / arrow key
        self.page_held, self.page_next = None, 0   # L2/R2 (trigger or PgUp/PgDn) held
        self.trig = {}             # (pad, axis) -> pressed
        log.info("SteamVirtualGamepadInfo=%r", os.environ.get("SteamVirtualGamepadInfo"))
        k = pg
        self.keymap = {k.K_UP: UP, k.K_DOWN: DOWN, k.K_LEFT: LEFT, k.K_RIGHT: RIGHT,
                       k.K_RETURN: A, k.K_ESCAPE: B, k.K_BACKSPACE: B, k.K_x: X, k.K_y: Y,
                       k.K_m: START, k.K_q: L1, k.K_e: R1, k.K_PAGEUP: L2, k.K_PAGEDOWN: R2}
        b = pg
        self.btnmap = {b.CONTROLLER_BUTTON_A: A, b.CONTROLLER_BUTTON_B: B,
                       b.CONTROLLER_BUTTON_X: X, b.CONTROLLER_BUTTON_Y: Y,
                       b.CONTROLLER_BUTTON_START: START, b.CONTROLLER_BUTTON_BACK: BACK,
                       b.CONTROLLER_BUTTON_LEFTSHOULDER: L1, b.CONTROLLER_BUTTON_RIGHTSHOULDER: R1,
                       b.CONTROLLER_BUTTON_DPAD_UP: UP, b.CONTROLLER_BUTTON_DPAD_DOWN: DOWN,
                       b.CONTROLLER_BUTTON_DPAD_LEFT: LEFT, b.CONTROLLER_BUTTON_DPAD_RIGHT: RIGHT}

    def _add(self, index):
        try:
            iid = self.pg.joystick.Joystick(index).get_instance_id()
            if iid in self.pads:
                return
            if self.ctl.is_controller(index):
                c = self.ctl.Controller(index)
                self.pads[iid] = c         # by instance id, like the dedupe above and REMOVED
                                           # events (c.id is not it: after a game run the pad
                                           # was re-opened every 2 s)
                guid = ""
                try:
                    guid = self.pg.joystick.Joystick(index).get_guid()
                except Exception:  # noqa: BLE001
                    pass
                self._kinds()
                log.info("pad added: %r guid=%s -> %s", c.name, guid, self.kinds.get(iid))
            else:
                log.info("joystick %d is not a game controller, ignored", index)
        except Exception as e:  # noqa: BLE001
            log.warning("pad %d could not be opened: %s", index, e)

    def _kinds(self):
        """Re-work out every pad's kind (a hot-plugged pad can be the generic "Steam Virtual
        Gamepad"; Steam's slot file says what it really is)."""
        names = [(iid, c.name) for iid, c in self.pads.items()]
        known = {i: k for i, k in self.kinds.items() if i in self.pads and i not in self._guessed}
        unsure = [i for i, n in names if i not in known and PADS.kind_from_name(n) is None]
        self._guessed = set()
        self.kinds = PADS.resolve(names, PADS.steam_slots() if unsure else [], known, self._guessed)
        for i in unsure:
            if i not in self._guessed:
                log.info("pad %r = %s (Steam's slot list)", self.pads[i].name, self.kinds[i])

    def kind(self):
        """Kind of pad to show glyphs for: the last one pressed (pads.pick)."""
        return PADS.pick(self.kinds, self.last_pad)

    def _used(self, iid):
        if iid != self.last_pad and iid in self.pads:
            self.last_pad = iid
            log.info("pad in use: %r (%s)", self.pads[iid].name, self.kinds.get(iid))

    def rescan(self):
        """Backstop for missed hotplug events: open any pad we don't have yet."""
        try:
            n = self.pg.joystick.get_count()
        except Exception:  # noqa: BLE001
            return
        for i in range(n):
            self._add(i)
        if self._guessed & set(self.pads):
            self._kinds()          # Steam may write its slot file after the pad appeared

    def flush(self):
        self.pg.event.clear()
        self.stick_dir = self.btn_dir = self.page_held = None
        self.trig = {}

    def set_text_mode(self, on):
        self.text_mode = on
        (self.pg.key.start_text_input if on else self.pg.key.stop_text_input)()

    def _text_key(self, e):
        pg = self.pg
        if e.key == pg.K_BACKSPACE:
            return BKSP
        if e.key in (pg.K_RETURN, pg.K_KP_ENTER):
            return ENTER
        if e.key == pg.K_ESCAPE:
            return B
        if e.key == pg.K_v and e.mod & pg.KMOD_CTRL:
            return PASTE
        return None

    def _trigger(self, e):
        pg = self.pg
        if e.axis not in (pg.CONTROLLER_AXIS_TRIGGERLEFT, pg.CONTROLLER_AXIS_TRIGGERRIGHT):
            return None
        k, on = (e.instance_id, e.axis), e.value > TRIGGER_ON
        was = self.trig.get(k, False)
        self.trig[k] = on if on or e.value < TRIGGER_ON // 2 else was
        act = L2 if e.axis == pg.CONTROLLER_AXIS_TRIGGERLEFT else R2
        if on and not was:
            return self._press(act)
        if not self.trig[k] and self.page_held == act:
            self.page_held = None
        return None

    def poll(self):
        pg, out = self.pg, []
        for e in pg.event.get():
            if e.type == pg.QUIT:
                out.append("QUIT_EVENT")
            elif self.text_mode and e.type == pg.TEXTINPUT:
                out.append((TEXT, e.text))
            elif self.text_mode and e.type == pg.KEYDOWN:
                a = self._text_key(e)
                if a:
                    out.append(a)
            elif e.type == pg.KEYDOWN and e.key in self.keymap:
                out.append(self._press(self.keymap[e.key]))
            elif e.type == pg.KEYUP and self.keymap.get(e.key) == self.btn_dir:
                self.btn_dir = None
            elif e.type == pg.KEYUP and self.keymap.get(e.key) == self.page_held:
                self.page_held = None
            elif e.type == pg.CONTROLLERAXISMOTION:
                if abs(e.value) > DEADZONE:
                    self._used(e.instance_id)
                a = self._trigger(e)
                if a:
                    out.append(a)
            elif e.type in (pg.CONTROLLERDEVICEADDED, pg.JOYDEVICEADDED):
                self._add(e.device_index)
            elif e.type == pg.CONTROLLERDEVICEREMOVED:
                self.pads.pop(e.instance_id, None)
                self._kinds()
            elif e.type == pg.CONTROLLERBUTTONDOWN:
                self._used(e.instance_id)
                if e.button in self.btnmap:
                    out.append(self._press(self.btnmap[e.button]))
            elif e.type == pg.CONTROLLERBUTTONUP and self.btnmap.get(e.button) == self.btn_dir:
                self.btn_dir = None
        now = _ms()
        if now >= getattr(self, "next_scan", 0):
            self.next_scan = now + 2000
            self.rescan()
        out += self._stick()
        if self.page_held and _ms() >= self.page_next:
            self.page_next = _ms() + FAST_MS[1]
            out.append(self.page_held)
        return out

    def _press(self, act):
        """A direction press starts hold-to-repeat (the first step is the press itself)."""
        if act in (L2, R2):
            self.page_held, self.page_next = act, _ms() + FAST_MS[0]
        if act in DIRS:
            self.btn_dir = self.stick_dir = act
            self.stick_next = _ms() + REPEAT_MS[0]
        return act

    def _stick(self):
        """Held D-pad/arrow, else left stick from any pad, as directions with key-repeat."""
        d = self.btn_dir
        for c in ([] if d else self.pads.values()):
            try:
                y = c.get_axis(self.pg.CONTROLLER_AXIS_LEFTY)
                x = c.get_axis(self.pg.CONTROLLER_AXIS_LEFTX)
            except Exception:  # noqa: BLE001
                continue
            if abs(y) > DEADZONE and abs(y) >= abs(x):
                d = DOWN if y > 0 else UP
            elif abs(x) > DEADZONE:
                d = RIGHT if x > 0 else LEFT
            if d:
                break
        now = _ms()
        if d is None:
            self.stick_dir = None
            return []
        if d != self.stick_dir:
            self.stick_dir, self.stick_next = d, now + REPEAT_MS[0]
            return [d]
        if now >= self.stick_next:
            self.stick_next = now + REPEAT_MS[1]
            return [d]
        return []
