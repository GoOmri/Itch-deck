"""Steam library art for the SCRiTCH tile, drawn from Omri's logo (itch_deck/assets/logo.svg).

    python packaging/steam_art.py            # writes packaging/steam-art/*.png

Steam names: tile (portrait 600x900), wide tile (920x430), hero (banner, 3840x1240),
logo (shown over the hero, transparent) and icon (256x256). Background = the app's own
gradient (theme.bg_from -> bg_to) with a soft purple glow, so the tile matches what opens.
"""
import io
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame as pg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from itch_deck.theme import Theme  # noqa: E402

SVG = (ROOT / "itch_deck" / "assets" / "logo.svg").read_text()
OUT = ROOT / "packaging" / "steam-art"
VB_W, VB_H = 740.12, 131.95
I_BOX = (346.0, -2.0, 48.7, 136.0)        # the i alone (dot + stem), for the icon


def svg(text, w, h):
    return pg.image.load_sized_svg(io.BytesIO(text.encode()), (int(w), int(h)))


def logo(w):
    return svg(SVG, w, w * VB_H / VB_W)


def the_i(h):
    x, y, w, hh = I_BOX
    s = re.sub(r'viewBox="[^"]*"', f'viewBox="{x} {y} {w} {hh}"', SVG, count=1)
    return svg(s, h * w / hh, h)


def backdrop(t, size, glow_at=(0.5, 0.45), glow_r=0.55):
    w, h = size
    g = pg.Surface((2, 2))                 # 2x2 corners, smooth-scaled = a soft diagonal gradient
    mid = [(a + b) // 2 for a, b in zip(t.bg_from, t.bg_to)]
    g.set_at((0, 0), t.bg_from), g.set_at((1, 0), mid), g.set_at((0, 1), mid), g.set_at((1, 1), t.bg_to)
    s = pg.transform.smoothscale(pg.transform.smoothscale(g, (8, 8)), size)
    n = 64                                 # glow: concentric circles, small, then scaled up
    glow = pg.Surface((n, n), pg.SRCALPHA)
    for r in range(n // 2, 0, -1):
        a = int(70 * (1 - r / (n / 2)) ** 2)
        pg.draw.circle(glow, (*t.accent, a), (n // 2, n // 2), r)
    d = int(max(w, h) * glow_r * 2)
    glow = pg.transform.smoothscale(glow, (d, d))
    s.blit(glow, glow.get_rect(center=(int(w * glow_at[0]), int(h * glow_at[1]))))
    return s


def main():
    pg.init()
    t = Theme(pg, (1280, 800))
    OUT.mkdir(parents=True, exist_ok=True)

    def card(size, logo_w, at=(0.5, 0.5), **kw):
        s = backdrop(t, size, glow_at=at, **kw)
        img = logo(logo_w)
        s.blit(img, img.get_rect(center=(int(size[0] * at[0]), int(size[1] * at[1]))))
        return s

    pg.image.save(card((600, 900), 470, at=(0.5, 0.42), glow_r=0.5), OUT / "tile.png")
    pg.image.save(card((920, 430), 600, glow_r=0.6), OUT / "wide-tile.png")
    pg.image.save(backdrop(t, (3840, 1240), glow_at=(0.72, 0.4), glow_r=0.45), OUT / "hero.png")
    lg = logo(1280)                        # Steam draws this over the hero
    pg.image.save(lg, OUT / "logo.png")
    ic = backdrop(t, (256, 256), glow_r=0.6)
    i = the_i(190)
    ic.blit(i, i.get_rect(center=(128, 128)))
    mask = pg.Surface((256, 256), pg.SRCALPHA)
    pg.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=48)
    icon = pg.Surface((256, 256), pg.SRCALPHA)
    icon.blit(ic, (0, 0))
    icon.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
    pg.image.save(icon, OUT / "icon.png")
    print("steam art ->", OUT)


if __name__ == "__main__":
    main()
