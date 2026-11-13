"""Turns SDL controller + keyboard events into actions. Any pad works."""
UP, DOWN, LEFT, RIGHT, A, B, X, Y, START = "UP", "DOWN", "LEFT", "RIGHT", "A", "B", "X", "Y", "START"
DEADZONE = 16000
REPEAT_MS = (350, 120)  # first delay, then repeat


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
        k = pg
        self.keymap = {k.K_UP: UP, k.K_DOWN: DOWN, k.K_LEFT: LEFT, k.K_RIGHT: RIGHT,
                       k.K_RETURN: A, k.K_ESCAPE: B, k.K_BACKSPACE: B}
        b = pg
        self.btnmap = {b.CONTROLLER_BUTTON_A: A, b.CONTROLLER_BUTTON_B: B,
                       b.CONTROLLER_BUTTON_X: X, b.CONTROLLER_BUTTON_Y: Y,
                       b.CONTROLLER_BUTTON_START: START,
                       b.CONTROLLER_BUTTON_DPAD_UP: UP, b.CONTROLLER_BUTTON_DPAD_DOWN: DOWN,
                       b.CONTROLLER_BUTTON_DPAD_LEFT: LEFT, b.CONTROLLER_BUTTON_DPAD_RIGHT: RIGHT}

    def _add(self, index):
        try:
            if self.ctl.is_controller(index):
                c = self.ctl.Controller(index)
                self.pads[c.id] = c
        except Exception:  # noqa: BLE001
            pass

    def pad_names(self):
        return [c.name for c in self.pads.values()]

    def flush(self):
        self.pg.event.clear()
        self.stick_dir = None

    def poll(self):
        pg, out = self.pg, []
        for e in pg.event.get():
            if e.type == pg.QUIT:
                out.append("QUIT_EVENT")
            elif e.type == pg.KEYDOWN and e.key in self.keymap:
                out.append(self.keymap[e.key])
            elif e.type == pg.CONTROLLERDEVICEADDED:
                self._add(e.device_index)
            elif e.type == pg.CONTROLLERDEVICEREMOVED:
                self.pads.pop(e.instance_id, None)
            elif e.type == pg.CONTROLLERBUTTONDOWN and e.button in self.btnmap:
                out.append(self.btnmap[e.button])
        out += self._stick()
        return out

    def _stick(self):
        """Left stick as D-pad with key-repeat, from any pad."""
        d = None
        for c in self.pads.values():
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
