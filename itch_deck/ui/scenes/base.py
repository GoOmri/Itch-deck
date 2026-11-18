"""Scene base: a page plus optional overlay (modal/picker) and toast."""
from .. import widgets as W


class Scene:
    def __init__(self, t, toast=None, toast_error=False):
        self.t = t
        self.overlay = None        # ("confirm", title, body, hints) | ("picker", ...) | None (see the property)
        self.confirm_focus = 0     # confirm dialog: 0 = its action, 1 = Cancel
        self.toast, self.toast_error = toast, toast_error

    @property
    def overlay(self):
        return getattr(self, "_overlay", None)

    @overlay.setter
    def overlay(self, v):
        old = getattr(self, "_overlay", None)
        if v and len(v) > 1 and v[0] in ("picker", "menu") and not (old and len(old) > 1 and old[0] == v[0] and old[1] == v[1]):
            W.forget_menu(v[1])                 # newly opened: its focus appears in place, no slide
        self._overlay = v

    # subclasses implement
    def draw_page(self, s): ...
    def hints(self): return []

    activity = notice = None            # background work / update news, set by the app each frame

    def footer_status(self):
        """Footer left: what's happening in the background (empty when nothing is)."""
        return self.activity, self.notice

    def draw(self, s):
        s.blit(W.backdrop(self.t), (0, 0))
        self.draw_page(s)
        if self.overlay:
            self.draw_overlay(s)
        W.hint_bar(self.t, s, self.overlay_hints() or self.hints(), *self.footer_status())  # over the shade
        if self.toast:
            W.toast(self.t, s, self.toast, self.toast_error)

    def overlay_hints(self):
        if self.overlay and self.overlay[0] == "confirm":
            return [("A", "Select"), ("B", "Cancel")]
        return None

    def draw_overlay(self, s):
        kind, *args = self.overlay
        if kind == "confirm":
            title, body, hints, *style = args       # style "main": not destructive -> purple
            W.modal(self.t, s, title, body, [hints[0][1], "Cancel"], self.confirm_focus,
                    danger=style != ["main"])
