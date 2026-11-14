"""All colours, sizes, fonts and timings. Restyle here; layout scales from window size."""
from pathlib import Path

FONTS = Path(__file__).parent / "assets" / "fonts"


class Theme:
    # colours
    bg = (18, 18, 18)
    panel = (34, 34, 34)
    panel_hi = (48, 48, 48)
    line = (60, 60, 60)
    text_c = (240, 240, 240)
    dim = (150, 150, 150)
    faint = (100, 100, 100)
    accent = (157, 107, 255)  # purple: focus, progress, selection — the one accent colour
    on_accent = (20, 16, 30)
    error = (235, 77, 77)     # red is only for errors
    error_bg = (52, 32, 34)
    shade_a = 170             # modal backdrop alpha
    dimmed_a = 150            # overlay alpha on unplayable tiles
    child_bg = (120, 20, 30)
    # pad glyph colours (Xbox layout, which is what Steam Input presents)
    glyph = {"A": (98, 180, 76), "B": (220, 72, 62), "X": (60, 130, 220), "Y": (232, 188, 52)}
    # motion / timing
    focus_scale = 1.06
    focus_ms = 120            # ease-out
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
        self.radius = self.u
        self.outline = 3
        self.btn_h = self.u * 7
        self.btn_w = self.u * 50
        self.hint_h = self.u * 8
        self.top_h = self.u * 11
        self.grid_cols = max(3, min(6, int((self.w - 2 * self.m + self.gap) // (self.u * 26 + self.gap))))
        self._fonts = {}
        f = self.font
        self.f_title = f("SemiBold", self.u * 4.4)
        self.f_h1 = f("Bold", self.u * 5.2)
        self.f_h2 = f("SemiBold", self.u * 3.2)
        self.f_body = f("Regular", self.u * 2.7)
        self.f_small = f("Medium", self.u * 2.2)
        self.f_btn = f("SemiBold", self.u * 3)
        self.f_glyph = f("Bold", self.u * 2.1)

    def font(self, weight, size):
        key = (weight, int(size))
        if key not in self._fonts:
            self._fonts[key] = self.pg.font.Font(str(FONTS / f"Inter-{weight}.otf"), int(size))
        return self._fonts[key]

    def text(self, s, txt, x, y, font, color=None, center=False):
        img = font.render(txt, True, color or self.text_c)
        r = img.get_rect()
        if center:
            r.center = (int(x), int(y))
        else:
            r.topleft = (int(x), int(y))
        s.blit(img, r)

    def button(self, s, label, x, y, focused=False):
        pg = self.pg
        r = pg.Rect(int(x), int(y), self.btn_w, self.btn_h)
        pg.draw.rect(s, self.panel, r, border_radius=self.u)
        if focused:
            pg.draw.rect(s, self.accent, r, width=max(3, self.u // 3), border_radius=self.u)
        self.text(s, label, r.x + self.u * 3, r.centery - self.f_btn.get_height() / 2, self.f_btn)

    def hint_bar(self, s, txt):
        self.text(s, txt, self.m, self.h - self.m, self.f_body, color=self.dim)

    def modal(self, s, title, hint):
        pg = self.pg
        shade = pg.Surface((self.w, self.h), pg.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        s.blit(shade, (0, 0))
        r = pg.Rect(0, 0, self.u * 60, self.u * 22)
        r.center = (int(self.cx), int(self.h / 2))
        pg.draw.rect(s, self.panel, r, border_radius=self.u)
        self.text(s, title, r.centerx, r.y + self.u * 8, self.f_title, center=True)
        self.text(s, hint, r.centerx, r.y + self.u * 16, self.f_body, color=self.dim, center=True)
