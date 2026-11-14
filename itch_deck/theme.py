"""All colours, sizes, fonts and timings. Restyle here; layout scales from window size."""
from pathlib import Path

FONTS = Path(__file__).parent / "assets" / "fonts"


class Theme:
    # colours
    bg = (16, 16, 30)          # flat fallback (overlays); pages use the gradient below
    bg_from = (12, 14, 26)     # gradient top-left: dark blue (matches Game Night)
    bg_to = (34, 24, 58)       # gradient bottom-right: dark purple
    panel = (32, 32, 50)
    panel_hi = (48, 46, 72)
    line = (64, 62, 90)
    text_c = (240, 240, 240)
    dim = (150, 150, 150)
    faint = (100, 100, 100)
    accent = (157, 107, 255)  # purple = progress + state ("happening / yours"), never focus
    accent_btn = (104, 70, 184)   # Play button, not focused (focused = accent)
    accent_tint = (58, 44, 98)    # accent tag fill (Installed, Recommended, Developer)
    accent_soft = (196, 168, 255) # text on accent_tint
    on_accent = (20, 16, 30)
    error = (235, 77, 77)     # red is only for errors
    error_bg = (52, 32, 34)
    error_soft = (255, 150, 150)  # text on error_bg (Failed tag)
    focus_fill = (88, 86, 124)    # focused button / row: lit up, no colour
    focus_line = (225, 225, 238)  # thin light edge on focused pictures (tiles, screenshots)
    tag_bg = (44, 46, 68)         # neutral tag fill (platform, size)
    chip_a = 150                  # translucent dark chip behind tile badges
    shade_a = 170             # modal backdrop alpha
    dimmed_a = 150            # overlay alpha on unplayable tiles
    child_bg = (120, 20, 30)
    glyph_c = (240, 240, 240)  # pad glyphs: solid white shape (Steam style)
    glyph_ink = (14, 14, 14)   # letter knocked out of the white shape
    hint_bg = (9, 10, 20)
    # motion / timing
    focus_scale = 1.06
    focus_ms = 120            # ease-out (widgets.MOTION_SPEED)
    page_fade_ms = 160        # cross-fade between pages
    toast_s = 4.0
    # grid
    cover_ratio = 250 / 315   # itch cover h / w

    def __init__(self, pg, size):
        self.pg = pg
        self.w, self.h = size
        self.cx = self.w / 2
        self.u = max(8, round(self.h / 90))          # base unit (~9 px at 800p, 12 at 1080p)
        self.m = self.u * 6                           # outer margin
        self.gap = self.u * 3                         # grid gap
        self.radius = self.u          # THE radius: tiles, buttons, rows, panels, screenshots
        self.tag_r = max(3, self.u // 2)  # tags: squarer than buttons on purpose
        self.outline = max(3, self.u // 3)  # picture focus edge (W.focus_ring)
        self.btn_h = self.u * 7
        self.btn_w = self.u * 50
        self.hint_h = self.u * 8
        self.top_h = self.u * 11
        self.grid_cols = max(3, min(6, int((self.w - 2 * self.m + self.gap) // (self.u * 26 + self.gap))))
        self._fonts = {}
        f = self.font
        # type scale — 5 sizes only, nothing else on screen:
        #   TITLE 5.2u · SECTION 3.2u · BODY 2.7u · META 2.4u · LABEL 2.0u (bold uppercase)
        self.f_h1 = f("Bold", self.u * 5.2)        # page / game title
        self.f_h2 = f("SemiBold", self.u * 3.2)    # section headers, dialog titles
        self.f_body = f("Regular", self.u * 2.7)   # text
        self.f_btn = f("SemiBold", self.u * 2.7)   # buttons, row labels (= body size)
        self.f_small = f("Medium", self.u * 2.4)   # meta: captions, sub-lines, status
        self.f_hint = f("Bold", self.u * 2.0)      # footer + tags, always UPPERCASE
        self.f_glyph = self.f_hint

    def font(self, weight, size):
        key = (weight, int(size))
        if key not in self._fonts:
            self._fonts[key] = self.pg.font.Font(str(FONTS / f"Inter-{weight}.otf"), int(size))
        return self._fonts[key]
