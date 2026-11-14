"""Scene base: a page plus optional overlay (modal/picker) and toast."""
from .. import widgets as W


class Scene:
    def __init__(self, t, toast=None, toast_error=False):
        self.t = t
        self.overlay = None        # ("confirm", title, body, hints) | ("picker", ...) | None
        self.toast, self.toast_error = toast, toast_error

    # subclasses implement
    def draw_page(self, s): ...
    def hints(self): return []

    def draw(self, s):
        s.blit(W.backdrop(self.t), (0, 0))
        self.draw_page(s)
        if self.overlay:
            self.draw_overlay(s)
        W.hint_bar(self.t, s, self.overlay_hints() or self.hints())  # on top of the shade
        if self.toast:
            W.toast(self.t, s, self.toast, self.toast_error)

    def overlay_hints(self):
        if self.overlay and self.overlay[0] == "confirm":
            return self.overlay[3]
        return None

    def draw_overlay(self, s):
        kind, *args = self.overlay
        if kind == "confirm":
            title, body, _hints = args          # hints are drawn by the footer
            W.modal(self.t, s, title, body)
