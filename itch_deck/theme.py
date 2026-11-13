"""All colours, sizes and fonts. Restyle here; layout scales from window height."""


class Theme:
    bg = (18, 18, 18)
    panel = (34, 34, 34)
    text_c = (240, 240, 240)
    dim = (150, 150, 150)
    accent = (250, 92, 92)   # itch-ish red
    child_bg = (120, 20, 30)

    def __init__(self, pg, size):
        self.pg = pg
        self.w, self.h = size
        self.cx = self.w / 2
        self.u = max(8, round(self.h / 90))          # base unit (~9 px at 800p, 12 at 1080p)
        self.m = self.u * 6                           # outer margin
        self.btn_h = self.u * 7
        self.btn_w = self.u * 50
        f = pg.font.Font
        self.f_title = f(None, self.u * 5)
        self.f_body = f(None, self.u * 3)
        self.f_btn = f(None, self.u * 4)

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
