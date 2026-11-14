"""Drawing helpers shared by every scene. All take the Theme `t` and a target surface `s`."""
import colorsys
import math
import zlib

import pygame as pg

_cover_cache = {}


# --- basics -----------------------------------------------------------------
def fit(font, txt, maxw):
    """Cut text with an ellipsis so it fits maxw pixels."""
    if font.size(txt)[0] <= maxw:
        return txt
    while txt and font.size(txt + "…")[0] > maxw:
        txt = txt[:-1]
    return txt.rstrip() + "…"


def wrap(t, s, txt, x, y, font, maxw, color=None):
    """Draw word-wrapped text; returns the bottom y."""
    line = ""
    for word in txt.split():
        trial = f"{line} {word}".strip()
        if font.size(trial)[0] > maxw and line:
            y = text(t, s, line, x, y, font, color).bottom
            line = word
        else:
            line = trial
    if line:
        y = text(t, s, line, x, y, font, color).bottom
    return y


def text(t, s, txt, x, y, font, color=None, anchor="topleft", maxw=None):
    if maxw:
        txt = fit(font, txt, maxw)
    img = font.render(txt, True, color or t.text_c)
    r = img.get_rect(**{anchor: (int(x), int(y))})
    s.blit(img, r)
    return r


def rounded(img, radius):
    """Copy of img with rounded corners (alpha mask)."""
    out = pg.Surface(img.get_size(), pg.SRCALPHA)
    out.blit(img, (0, 0))
    mask = pg.Surface(img.get_size(), pg.SRCALPHA)
    pg.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=int(radius))
    out.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
    return out


def shade(t, s, alpha=None, rect=None):
    rect = rect or s.get_rect()
    o = pg.Surface(rect.size, pg.SRCALPHA)
    o.fill((0, 0, 0, t.shade_a if alpha is None else alpha))
    s.blit(o, rect.topleft)


def panel(t, s, rect, color=None, radius=None):
    pg.draw.rect(s, color or t.panel, rect, border_radius=int(t.radius if radius is None else radius))


# --- placeholder cover art --------------------------------------------------
def _hue(seed, n):
    return ((zlib.crc32(f"{seed}:{n}".encode()) % 1000) / 1000.0)


def cover(t, game, size):
    """Cover image for a game. Real covers come later (M2); now a generated placeholder."""
    key = (game["id"], size)
    if key in _cover_cache:
        return _cover_cache[key]
    w, h = 315, 250
    base = pg.Surface((w, h))
    h1, h2 = _hue(game["id"], 1), _hue(game["id"], 2)
    c1 = [int(v * 255) for v in colorsys.hsv_to_rgb(h1, 0.55, 0.55)]
    c2 = [int(v * 255) for v in colorsys.hsv_to_rgb(h2, 0.65, 0.22)]
    for y in range(h):
        k = y / h
        pg.draw.line(base, [int(c1[i] * (1 - k) + c2[i] * k) for i in range(3)], (0, y), (w, y))
    deco = pg.Surface((w, h), pg.SRCALPHA)
    kind = zlib.crc32(game["id"].encode()) % 3
    for n in range(5):
        r = 30 + (zlib.crc32(f"{game['id']}{n}".encode()) % 90)
        x = zlib.crc32(f"x{game['id']}{n}".encode()) % w
        y = zlib.crc32(f"y{game['id']}{n}".encode()) % h
        col = (255, 255, 255, 18 + n * 4)
        if kind == 0:
            pg.draw.circle(deco, col, (x, y), r)
        elif kind == 1:
            pg.draw.polygon(deco, col, [(x - r, h), (x, y - r // 2), (x + r, h)])
        else:
            pg.draw.rect(deco, col, (x - r // 2, y - r // 2, r, r), border_radius=8)
    base.blit(deco, (0, 0))
    initials = "".join(wd[0] for wd in game["title"].split()[:2]).upper()
    img = t.font("Bold", 96).render(initials, True, (255, 255, 255))
    img.set_alpha(215)
    base.blit(img, img.get_rect(center=(w // 2, h // 2)))
    out = pg.transform.smoothscale(base, size)
    _cover_cache[key] = out
    return out


def screenshot(t, game, i, size):
    """Placeholder screenshot (16:9). Real ones come from the itch page in M2."""
    key = ("shot", game["id"], i, size)
    if key in _cover_cache:
        return _cover_cache[key]
    w, h = 320, 180
    base = pg.Surface((w, h))
    hue = (_hue(game["id"], 1) + i * 0.07) % 1
    top = [int(v * 255) for v in colorsys.hsv_to_rgb(hue, 0.35, 0.65)]
    bot = [int(v * 255) for v in colorsys.hsv_to_rgb((hue + 0.1) % 1, 0.55, 0.25)]
    for y in range(h):
        k = y / h
        pg.draw.line(base, [int(top[c] * (1 - k) + bot[c] * k) for c in range(3)], (0, y), (w, y))
    gy = 120 + (zlib.crc32(f"{game['id']}{i}g".encode()) % 30)
    pts = [(0, gy)] + [(x, gy - (zlib.crc32(f"{game['id']}{i}{x}".encode()) % 28)) for x in range(20, w, 40)] + [(w, gy), (w, h), (0, h)]
    pg.draw.polygon(base, [max(0, c - 25) for c in bot], pts)
    px = 40 + (zlib.crc32(f"{game['id']}{i}p".encode()) % 220)
    pg.draw.rect(base, (245, 240, 230), (px, gy - 34, 14, 22), border_radius=3)
    pg.draw.rect(base, (0, 0, 0), (8, 8, 70, 10), border_radius=3)
    pg.draw.rect(base, (230, 230, 230), (10, 10, 40, 6), border_radius=2)
    out = pg.transform.smoothscale(base, size)
    _cover_cache[key] = out
    return out


# --- pad glyphs and hint bar ------------------------------------------------
def glyph(t, s, btn, x, cy, ink=None):
    """Steam-style button glyph: solid white shape, label knocked out in the dark ink colour.
    A B X Y / ◀ ▶ = circle; L1 R1 L2 R2 = small rounded square; MENU = pill with ☰.
    Left edge at x, centred on cy. Returns width. Labels centre on their own bounds."""
    d = int(t.u * 3.0)
    c, ink = t.glyph_c, ink or t.glyph_ink
    if btn == "MENU":
        r = pg.Rect(int(x), int(cy - d * 0.42), int(d * 1.45), int(d * 0.84))
        pg.draw.rect(s, c, r, border_radius=r.h // 2)
        bw, gap, lw = int(d * 0.5), max(2, int(d * 0.16)), max(2, round(d * 0.08))
        for k in (-1, 0, 1):
            yy = r.centery + k * gap
            pg.draw.line(s, ink, (r.centerx - bw // 2, yy), (r.centerx + bw // 2 - 1, yy), lw)
        return r.w
    img = t.f_glyph.render(btn, True, ink)
    img = img.subsurface(img.get_bounding_rect())
    if len(btn) == 1:
        ctr = (int(x + d / 2), int(cy))
        pg.draw.aacircle(s, c, ctr, d // 2)
        pg.draw.circle(s, c, ctr, d // 2 - 1)
        s.blit(img, img.get_rect(center=ctr))
        return d
    r = pg.Rect(int(x), int(cy - d / 2), max(d, img.get_width() + int(t.u * 1.0)), d)
    pg.draw.rect(s, c, r, border_radius=max(2, int(d * 0.18)))
    s.blit(img, img.get_rect(center=r.center))
    return r.w


def hint_bar(t, s, items):
    """Steam-style footer: actions right-aligned, white UPPERCASE labels.
    items: [(button, label), ...]; an empty label pairs the glyph with the next one (L1 R1)."""
    r = pg.Rect(0, t.h - t.hint_h, t.w, t.hint_h)
    pg.draw.rect(s, t.hint_bg, r)
    cy, gap = r.centery, t.u * 0.7
    widths = []
    for btn, label in items:  # measure first, then draw from the right edge
        gw = glyph(t, pg.Surface((1, 1)), btn, 0, 0)
        lw = t.f_hint.size(label.upper())[0] if label else 0
        widths.append((gw, lw))
    total = sum(gw + (gap + lw + t.u * 3.5 if lw else gap) for gw, lw in widths) - t.u * 3.5
    x = t.w - t.m - total
    for (btn, label), (gw, lw) in zip(items, widths):
        glyph(t, s, btn, x, cy)
        x += gw + gap
        if label:
            text(t, s, label.upper(), x, cy, t.f_hint, color=t.text_c, anchor="midleft")
            x += lw + t.u * 3.5


# --- controls ---------------------------------------------------------------
def button(t, s, rect, label, focused=False, enabled=True, icon=None):
    panel(t, s, rect, t.panel_hi if focused else t.panel)
    if focused:
        pg.draw.rect(s, t.accent, rect.inflate(t.outline * 2, t.outline * 2), t.outline,
                     border_radius=t.radius + t.outline)
    col = t.text_c if enabled else t.faint
    x = rect.x + t.u * 2.5
    if icon:
        x = text(t, s, icon, x, rect.centery, t.f_btn, color=t.accent if enabled else t.faint,
                 anchor="midleft").right + t.u * 1.5
    text(t, s, label, x, rect.centery, t.f_btn, color=col, anchor="midleft")


def pill(t, s, label, x, y, fill=None, color=None, font=None, anchor="topleft"):
    font = font or t.f_small
    img = font.render(label, True, color or t.text_c)
    r = pg.Rect(0, 0, img.get_width() + t.u * 1.8, img.get_height() + t.u * 0.6)
    setattr(r, anchor, (int(x), int(y)))
    pg.draw.rect(s, fill or (0, 0, 0), r, border_radius=r.h // 2)
    s.blit(img, img.get_rect(center=r.center))
    return r


def ring(t, s, center, r, frac, width=None):
    """Download progress ring."""
    width = width or max(3, r // 4)
    pg.draw.circle(s, (0, 0, 0), center, r + 2)
    pg.draw.circle(s, t.line, center, r, width)
    if frac > 0:
        pts_o, pts_i = [], []
        n = max(2, int(60 * frac))
        for i in range(n + 1):
            a = -math.pi / 2 + 2 * math.pi * frac * i / n
            pts_o.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
            pts_i.append((center[0] + (r - width) * math.cos(a), center[1] + (r - width) * math.sin(a)))
        pg.draw.polygon(s, t.accent, pts_o + pts_i[::-1])


def spinner(t, s, center, r, phase=0.0, width=None):
    width = width or max(3, r // 5)
    pg.draw.circle(s, t.panel_hi, center, r, width)
    pts_o, pts_i = [], []
    for i in range(31):
        a = phase * 2 * math.pi + 1.5 * math.pi * i / 30
        pts_o.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
        pts_i.append((center[0] + (r - width) * math.cos(a), center[1] + (r - width) * math.sin(a)))
    pg.draw.polygon(s, t.accent, pts_o + pts_i[::-1])


def progress(t, s, rect, frac=None, phase=0.3):
    """frac=None draws an indeterminate (moving) bar."""
    pg.draw.rect(s, t.panel_hi, rect, border_radius=rect.h // 2)
    if frac is None:
        seg = rect.w // 4
        x = rect.x + int((rect.w - seg) * phase)
        pg.draw.rect(s, t.accent, (x, rect.y, seg, rect.h), border_radius=rect.h // 2)
    elif frac > 0:
        pg.draw.rect(s, t.accent, (rect.x, rect.y, max(rect.h, int(rect.w * frac)), rect.h),
                     border_radius=rect.h // 2)


# --- tiles ------------------------------------------------------------------
def tile(t, s, game, rect, focused=False):
    """Library tile: cover in rect, title under it. rect is the unscaled cover area."""
    playable = game["platforms"] & {"linux", "windows"}
    r = rect
    if focused:
        r = rect.inflate(rect.w * (t.focus_scale - 1), rect.h * (t.focus_scale - 1))
    img = rounded(cover(t, game, r.size), t.radius)
    if not playable:
        img = img.copy()
        o = pg.Surface(r.size, pg.SRCALPHA)
        pg.draw.rect(o, (0, 0, 0, t.dimmed_a), o.get_rect(), border_radius=t.radius)
        img.blit(o, (0, 0))
    s.blit(img, r.topleft)
    if focused:
        pg.draw.rect(s, t.accent, r.inflate(t.outline * 2, t.outline * 2), t.outline,
                     border_radius=t.radius + t.outline)
    _badges(t, s, game, r, playable)
    ty = r.bottom + t.u * 1.2
    col = t.text_c if (focused or playable) else t.faint
    text(t, s, game["title"], rect.x, ty, t.f_small, color=col, maxw=rect.w)
    if not playable:
        tag = "Browser game" if "html" in game["platforms"] else "Not playable here"
        text(t, s, tag, rect.x, ty + t.f_small.get_height(), t.f_small, color=t.faint, maxw=rect.w)


def _badges(t, s, game, r, playable):
    pad = t.u
    st = game.get("state")
    # top-right: install state
    if st == "installed":
        c = (r.right - pad - t.u * 1.6, r.y + pad + t.u * 1.6)
        pg.draw.circle(s, t.accent, c, t.u * 1.6)
        text(t, s, "✓", c[0], c[1] + 1, t.f_glyph, color=t.on_accent, anchor="center")
    elif st == "downloading":
        ring(t, s, (int(r.right - pad - t.u * 2.2), int(r.y + pad + t.u * 2.2)), int(t.u * 2.2),
             game.get("progress", 0))
    elif st == "queued":
        pill(t, s, "Queued", r.right - pad, r.y + pad, anchor="topright")
    elif st == "failed":
        pill(t, s, "Failed", r.right - pad, r.y + pad, fill=t.error, color=t.on_accent,
             anchor="topright")
    # no platform badge: Linux vs Windows/Proton is handled for the user, not shown on the art


def offline_mark(t, s, right, cy, since):
    """Small, quiet offline indicator for the top bar: cloud with a slash + 'Offline · <date>'."""
    r = text(t, s, f"Offline · synced {since}", right, cy, t.f_small, color=t.faint, anchor="midright")
    u, cx = t.u, r.x - t.u * 2.6
    c = t.faint
    pg.draw.circle(s, c, (int(cx - u * 0.6), int(cy + u * 0.2)), int(u * 0.7))
    pg.draw.circle(s, c, (int(cx + u * 0.2), int(cy - u * 0.3)), int(u * 0.95))
    pg.draw.circle(s, c, (int(cx + u * 0.9), int(cy + u * 0.25)), int(u * 0.6))
    pg.draw.rect(s, c, (int(cx - u * 0.6), int(cy + u * 0.1), int(u * 1.5), int(u * 0.75)))
    pg.draw.line(s, t.bg, (cx - u * 1.6, cy - u * 1.3), (cx + u * 1.7, cy + u * 1.4), max(4, u // 2))
    pg.draw.line(s, c, (cx - u * 1.5, cy - u * 1.2), (cx + u * 1.6, cy + u * 1.3), max(2, u // 4))
    return r.x - t.u * 4.5


# --- overlays ---------------------------------------------------------------
def modal(t, s, title, body, hints, width_u=64):
    shade(t, s)
    lines = body if isinstance(body, list) else [body]
    h = t.u * 10 + len(lines) * t.f_body.get_linesize() + t.u * 8
    need = max([t.f_h2.size(title)[0]] + [t.f_body.size(ln)[0] for ln in lines]) + t.u * 8
    r = pg.Rect(0, 0, min(t.w - 2 * t.m, max(t.u * width_u, need)), h)
    r.center = (int(t.cx), int(t.h / 2))
    panel(t, s, r, radius=t.u * 1.5)
    y = r.y + t.u * 4
    y = text(t, s, title, r.x + t.u * 4, y, t.f_h2).bottom + t.u * 2
    for ln in lines:
        y = text(t, s, ln, r.x + t.u * 4, y, t.f_body, color=t.dim).bottom
    x, cy = r.x + t.u * 4, r.bottom - t.u * 4
    for btn, label in hints:
        x += glyph(t, s, btn, x, cy) + t.u
        x = text(t, s, label, x, cy, t.f_body, anchor="midleft").right + t.u * 4
    return r


def toast(t, s, msg, error=False):
    img = t.f_body.render(msg, True, t.text_c)
    r = pg.Rect(0, 0, img.get_width() + t.u * 6, img.get_height() + t.u * 3)
    r.midbottom = (int(t.cx), t.h - t.hint_h - t.u * 3)
    panel(t, s, r, t.panel_hi, radius=r.h // 2)
    if error:
        pg.draw.circle(s, t.error, (r.x + t.u * 2.2, r.centery), t.u * 0.7)
    s.blit(img, img.get_rect(midleft=(r.x + t.u * (3.6 if error else 3), r.centery)))


def banner(t, s, msg, y):
    r = pg.Rect(t.m, int(y), t.w - 2 * t.m, int(t.u * 4.5))
    panel(t, s, r, t.error_bg)
    pg.draw.rect(s, t.error, (r.x, r.y, t.u // 2, r.h), border_top_left_radius=t.radius,
                 border_bottom_left_radius=t.radius)
    text(t, s, msg, r.x + t.u * 2.5, r.centery, t.f_small, anchor="midleft")
    return r


def rows(t, s, rect, items, focus, row_h=None):
    """Settings/Picker list. items: [(label, value, sub)] — value/sub may be ''."""
    row_h = row_h or int(t.u * 8.5)
    y = rect.y
    for i, (label, value, sub) in enumerate(items):
        r = pg.Rect(rect.x, y, rect.w, row_h)
        if i == focus:
            panel(t, s, r, t.panel_hi)
            pg.draw.rect(s, t.accent, r.inflate(t.outline * 2, t.outline * 2), t.outline,
                         border_radius=t.radius + t.outline)
        ly = r.centery - (t.f_small.get_height() // 2 if sub else 0)
        text(t, s, label, r.x + t.u * 2.5, ly, t.f_btn, anchor="midleft")
        if sub:
            text(t, s, sub, r.x + t.u * 2.5, ly + t.f_btn.get_height() * 0.55, t.f_small,
                 color=t.dim, anchor="topleft", maxw=r.w * 0.6)
        if value == "Recommended":
            pill(t, s, value, r.right - t.u * 2.5, r.centery, fill=t.accent, color=t.on_accent,
                 anchor="midright")
        elif value:
            text(t, s, value, r.right - t.u * 2.5, r.centery, t.f_body, color=t.dim, anchor="midright")
        if i != focus and i < len(items) - 1:
            pg.draw.line(s, t.panel, (r.x + t.u * 2, r.bottom), (r.right - t.u * 2, r.bottom))
        y += row_h + t.u // 2
