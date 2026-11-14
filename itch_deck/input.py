"""Turns SDL controller + keyboard events into actions. Any pad works."""
import logging
import os

UP, DOWN, LEFT, RIGHT, A, B, X, Y, START = "UP", "DOWN", "LEFT", "RIGHT", "A", "B", "X", "Y", "START"
L1, R1, L2, R2, BACK = "L1", "R1", "L2", "R2", "BACK"
TEXT, BKSP, ENTER, PASTE = "TEXT", "BKSP", "ENTER", "PASTE"   # text-entry mode only
DEADZONE = 16000
TRIGGER_ON = 20000
log = logging.getLogger("itch-deck")
REPEAT_MS = (300, 170)  # hold: first delay, then repeat every 170 ms (stick, D-pad, arrows)
DIRS = (UP, DOWN, LEFT, RIGHT)


class Input:
    def __init__(self, pg):
        self.pg = pg
        from pygame._sdl2 import controller
        self.ctl = controller
        controller.init()
        self.pads = {}
        for i in range(controller.get_count()):
            self._add(i)
        self.stick_dir = None
        self.stick_next = 0
        self.text_mode = False
        self.btn_dir = None        # direction held on a D-pad / arrow key
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
            if self.ctl.is_controller(index):
                c = self.ctl.Controller(index)
                self.pads[c.id] = c
                guid = ""
                try:
                    guid = self.pg.joystick.Joystick(index).get_guid()
                except Exception:  # noqa: BLE001
                    pass
                log.info("pad added: %r guid=%s", c.name, guid)
        except Exception:  # noqa: BLE001
            pass

    def pad_names(self):
        return [c.name for c in self.pads.values()]

    def flush(self):
        self.pg.event.clear()
        self.stick_dir = self.btn_dir = None

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
        if on and not was:
            return L2 if e.axis == pg.CONTROLLER_AXIS_TRIGGERLEFT else R2
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
            elif e.type == pg.CONTROLLERAXISMOTION:
                a = self._trigger(e)
                if a:
                    out.append(a)
            elif e.type == pg.CONTROLLERDEVICEADDED:
                self._add(e.device_index)
            elif e.type == pg.CONTROLLERDEVICEREMOVED:
                self.pads.pop(e.instance_id, None)
            elif e.type == pg.CONTROLLERBUTTONDOWN and e.button in self.btnmap:
                out.append(self._press(self.btnmap[e.button]))
            elif e.type == pg.CONTROLLERBUTTONUP and self.btnmap.get(e.button) == self.btn_dir:
                self.btn_dir = None
        out += self._stick()
        return out

    def _press(self, act):
        """A direction press starts hold-to-repeat (the first step is the press itself)."""
        if act in DIRS:
            self.btn_dir = self.stick_dir = act
            self.stick_next = self.pg.time.get_ticks() + REPEAT_MS[0]
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
        now = self.pg.time.get_ticks()
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
