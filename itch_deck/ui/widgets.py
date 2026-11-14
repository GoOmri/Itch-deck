"""Drawing helpers shared by every scene. All take the Theme `t` and a target surface `s`."""
import colorsys
import math
import zlib

import pygame as pg

_cover_cache = {}
LIVE = False   # True in the running app: animate. False for mockups: draw the end state.


APP_NAME = "SCRiTCH"          # shown name; binary, data folders and repo keep itch-deck for now


def spring(x, back=None):
    """THE motion curve (DESIGN rule 9): slow start, quick middle, small overshoot, settle.
    An ease-in-out-back with a mild back (SPRING_BACK)."""
    x = max(0.0, min(1.0, x))
    c = (SPRING_BACK if back is None else back) * 1.525
    if x < 0.5:
        return (2 * x) ** 2 * ((c + 1) * 2 * x - c) / 2
    return ((2 * x - 2) ** 2 * ((c + 1) * (2 * x - 2) + c) + 2) / 2


def ease(cur, target, ms=None, back=None):
    """Time-based tween toward target on the spring curve; retargets smoothly mid-flight.
    State tuple: (value, from, to, start_time) — callers keep it and read [0].
    Snaps when not LIVE or on first use (mockups show the end state)."""
    import time
    now = time.monotonic()
    target = float(target)
    if cur is None or not LIVE:
        return (target, target, target, now)
    val, frm, to, t0 = cur
    if target != to:                       # new destination: start from where we are now
        frm, to, t0 = val, target, now
    k = (now - t0) * 1000 / (ms or MOTION_MS)
    val = to if k >= 1 else frm + (to - frm) * spring(k, back)
    return (val, frm, to, t0)


# --- motion -----------------------------------------------------------------
# Widgets are stateless, so animated amounts live here, keyed by what they belong to
# (("btn", label), ("row", label), ("tile", game id), ("toast", msg)). Mockups (LIVE off) snap.
_ANIM = {}
_busy_until = 0.0


def anim(key, target, start=None, ms=None, back=None):
    """Eased 0..1 amount for `key` heading to `target`. start=0 makes a new key animate in
    (default: a new key starts at its target). Values may overshoot 0..1 a little (spring)."""
    global _busy_until
    import time
    cur = _ANIM.get(key)
    if cur is None and start is not None and LIVE:
        v = start * 1000.0
        cur = (v, v, v, time.monotonic())
    val = ease(cur, target * 1000.0, ms, back)
    if val[0] != target * 1000.0:
        _busy_until = time.monotonic() + 0.05
    _ANIM[key] = val
    if len(_ANIM) > 400:
        _ANIM.clear()
    return val[0] / 1000.0


def animating():
    """True while anything above is still moving (cached pages use it to keep redrawing)."""
    import time
    return LIVE and time.monotonic() < _busy_until


def mix(a, b, k):
    k = max(0.0, min(1.0, k))                     # spring overshoot must not break colours
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


MOTION_MS = 240       # every focus / tile / scroll / toast / page move (one tempo)
SPRING_BACK = 0.0     # overshoot of spring(): 0 = calm ease-in-out (Omri: no bounce)
TAB_BACK = 1.1        # the one springy thing: the All/Installed underline


# --- basics -----------------------------------------------------------------
def fit(font, txt, maxw):
    """Cut text with an ellipsis so it fits maxw pixels."""
    if font.size(txt)[0] <= maxw:
        return txt
    while txt and font.size(txt + "…")[0] > maxw:
        txt = txt[:-1]
    return txt.rstrip() + "…"


def wrap(t, s, txt, x, y, font, maxw, color=None, max_lines=None):
    """Draw word-wrapped text; returns the bottom y. max_lines cuts with an ellipsis."""
    lines, line = [], ""
    for word in txt.split():
        trial = f"{line} {word}".strip()
        if font.size(trial)[0] > maxw and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit(font, lines[-1] + " …", maxw) if font.size(lines[-1] + " …")[0] > maxw \
            else lines[-1] + " …"
    for ln in lines:
        y = text(t, s, ln, x, y, font, color).bottom
    return y


def text(t, s, txt, x, y, font, color=None, anchor="topleft", maxw=None):
    if maxw:
        txt = fit(font, txt, maxw)
    img = font.render(txt, True, color or t.text_c)
    if anchor in ("baseleft", "baseright"):   # sit on a shared baseline (mixed font sizes)
        anchor, y = ("topleft" if anchor == "baseleft" else "topright"), y - font.get_ascent()
    r = img.get_rect(**{anchor: (int(x), int(y))})
    s.blit(img, r)
    return r


def text_named(t, s, txt, x, y, font, color=None, maxw=None):
    """Like text() (topleft), but the app name inside txt is drawn purple (every letter;
    only the logo has the white i). Returns the rect of the whole line."""
    if maxw:
        txt = fit(font, txt, maxw)
    i = txt.find(APP_NAME)
    if i < 0:
        return text(t, s, txt, x, y, font, color)
    parts = [(txt[:i], color or t.text_c), (APP_NAME, t.accent), (txt[i + len(APP_NAME):], color or t.text_c)]
    cx = x
    for part, col in parts:
        if part:
            s.blit(font.render(part, True, col), (int(cx), int(y)))
        cx += font.size(part)[0]
    return pg.Rect(int(x), int(y), font.size(txt)[0], font.get_height())


def cap_gap(font):
    """Empty space between the top of a text box and the top of its capitals."""
    return font.get_ascent() - font.metrics("H")[0][3]


def x_mid(font):
    """Height above the baseline of the middle of lowercase letters (to centre icons on text)."""
    return font.metrics("x")[0][3] / 2


def rounded(img, radius):
    """Copy of img with rounded corners (alpha mask)."""
    out = pg.Surface(img.get_size(), pg.SRCALPHA)
    out.blit(img, (0, 0))
    mask = pg.Surface(img.get_size(), pg.SRCALPHA)
    pg.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=int(radius))
    out.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
    return out


def backdrop(t):
    """Soft diagonal gradient: dark blue (top-left) to dark purple (bottom-right)."""
    key = ("bg", t.w, t.h)
    if key not in _cover_cache:
        sw, sh = 48, 30
        small = pg.Surface((sw, sh))
        (r1, g1, b1), (r2, g2, b2) = t.bg_from, t.bg_to
        for y in range(sh):
            for x in range(sw):
                k = min(1.0, max(0.0, (x / sw) * 0.55 + (y / sh) * 0.75 - 0.15))
                k = k * k * (3 - 2 * k)  # smoothstep, keeps it soft
                small.set_at((x, y), (int(r1 + (r2 - r1) * k), int(g1 + (g2 - g1) * k), int(b1 + (b2 - b1) * k)))
        _cover_cache[key] = pg.transform.smoothscale(small, (t.w, t.h))
    return _cover_cache[key]


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


def _from_file(path, size, contain=False):
    """Image file scaled to cover `size` (centre-cropped), or with contain=True fitted inside it
    on black (letterbox). None if missing/unreadable."""
    key = ("file", path, size, contain)
    if key in _cover_cache:
        return _cover_cache[key]
    try:
        img = pg.image.load(path)
        rgb = pg.Surface(img.get_size(), 0, 32)   # palette GIF/PNG -> 32-bit for smoothscale
        rgb.blit(img, (0, 0))
        w, h = rgb.get_size()
        k = (min if contain else max)(size[0] / w, size[1] / h)
        big = pg.transform.smoothscale(rgb, (max(1, round(w * k)), max(1, round(h * k))))
        out = pg.Surface(size)
        out.fill((0, 0, 0))
        out.blit(big, ((size[0] - big.get_width()) // 2, (size[1] - big.get_height()) // 2))
    except Exception:  # noqa: BLE001  - broken download: fall back to placeholder
        out = None
    if len(_cover_cache) > 600:
        _cover_cache.clear()
    _cover_cache[key] = out
    return out


def cover(t, game, size):
    """Cover image: the cached itch cover if downloaded, else a generated placeholder."""
    if game.get("cover_file"):
        img = _from_file(game["cover_file"], size)
        if img:
            return img
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


_ASPECT = {}


def shot_aspect(game, i):
    """Width/height of screenshot i: from the cached file, else the game's known shapes, else 16:9."""
    files = game.get("shot_files") or []
    if i < len(files):
        a = _ASPECT.get(files[i])
        if a is None:
            try:
                w, h = pg.image.load(files[i]).get_size()
                a = max(0.5, min(2.4, w / h))
            except Exception:  # noqa: BLE001
                a = 16 / 9
            _ASPECT[files[i]] = a
        return a
    shapes = game.get("shot_aspects") or [16 / 9]
    return shapes[i % len(shapes)]


def screenshot(t, game, i, size, contain=False):
    """Screenshot i (cached from the itch page), else a 16:9 placeholder.
    contain=True (full-screen viewer): whole image, letterboxed — never cropped."""
    files = game.get("shot_files") or []
    if i < len(files):
        img = _from_file(files[i], size, contain)
        if img:
            return img
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
    if size[0] < 800:                    # small placeholder: a "player" + HUD; hero-size: scenery only
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
    if btn in ("◀", "▶"):  # drawn, not font glyphs: smaller and optically centred
        ctr = (x + d / 2, cy)
        pg.draw.aacircle(s, c, (int(ctr[0]), int(ctr[1])), d // 2)
        pg.draw.circle(s, c, (int(ctr[0]), int(ctr[1])), d // 2 - 1)
        a, hh = d * 0.20, d * 0.22   # half-width / half-height of the triangle
        sgn = 1 if btn == "▶" else -1
        ox = ctr[0] + sgn * d * 0.04  # nudge toward the point so it *looks* centred
        pts = [(ox - sgn * a, ctr[1] - hh), (ox - sgn * a, ctr[1] + hh), (ox + sgn * a, ctr[1])]
        pg.draw.polygon(s, ink, pts)
        pg.draw.aalines(s, ink, True, pts)
        return d
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
    cy, gap, sep = r.centery, t.u * 0.7, t.md      # glyph↔label (optical), between actions
    widths = []
    for btn, label in items:  # measure first, then draw from the right edge
        gw = glyph(t, pg.Surface((1, 1)), btn, 0, 0)
        lw = t.f_hint.size(label.upper())[0] if label else 0
        widths.append((gw, lw))
    total = sum(gw + (gap + lw + sep if lw else gap) for gw, lw in widths) - sep
    x = t.w - t.m - total
    for (btn, label), (gw, lw) in zip(items, widths):
        glyph(t, s, btn, x, cy)
        x += gw + gap
        if label:
            text(t, s, label.upper(), x, cy, t.f_hint, color=t.text_c, anchor="midleft")
            x += lw + sep


# --- controls ---------------------------------------------------------------
def icon_draw(s, name, center, size, color):
    """Drawn icons (never font characters, so they match the footer glyphs): "play", "check".
    size = icon height in px. Returns its width."""
    cx, cy, h = center[0], center[1], size
    if name == "play":
        a = h * 0.45
        ox = cx + h * 0.05                       # nudge toward the point: optically centred
        pts = [(ox - a, cy - h / 2), (ox - a, cy + h / 2), (ox + a, cy)]
        pg.draw.polygon(s, color, pts)
        pg.draw.aalines(s, color, True, pts)
        return int(a * 2)
    if name == "gear":                   # 8 teeth + hole, supersampled for smooth edges
        k = 4
        d = int(h * k)
        big = pg.Surface((d, d), pg.SRCALPHA)
        c, r1, r2 = d / 2, d * 0.5, d * 0.36
        pts = []
        for i in range(8):
            a = i * math.pi / 4
            for da, rr in ((-0.30, r2), (-0.18, r1), (0.18, r1), (0.30, r2)):
                pts.append((c + rr * math.cos(a + da), c + rr * math.sin(a + da)))
        pg.draw.polygon(big, color, pts)
        pg.draw.circle(big, color, (c, c), r2)
        pg.draw.circle(big, (0, 0, 0, 0), (c, c), d * 0.15)
        img = pg.transform.smoothscale(big, (int(h), int(h)))
        s.blit(img, img.get_rect(center=(int(cx), int(cy))))
        return int(h)
    if name == "check":
        w = max(2, round(h * 0.2))
        pts = [(cx - h * 0.42, cy + h * 0.02), (cx - h * 0.12, cy + h * 0.32),
               (cx + h * 0.45, cy - h * 0.32)]
        pg.draw.lines(s, color, False, pts, w)
        return int(h * 0.9)
    return 0


def focus_ring(t, s, rect):
    """Focus edge for pictures (tiles, screenshots): thin light outline, not colour."""
    pg.draw.rect(s, t.focus_line, rect.inflate(t.outline * 2, t.outline * 2), t.outline,
                 border_radius=t.radius + t.outline)


def button(t, s, rect, label, focused=False, enabled=True, icon=None, accent=False, key=None):
    """The one button: all the same grey. Focus (= hover on a pad) lights it up — no colour,
    no outline. accent=True (Play, Update only) = purple; focused it lights up to bright accent."""
    key = key or ("btn", label)
    k = anim(key, 1.0 if focused else 0.0)          # eased focus amount
    if accent == "danger" and enabled:             # Quit / Uninstall: red (Omri)
        fill, col = mix(t.danger_btn, t.error, k), t.text_c
    elif accent and enabled:
        fill, col = mix(t.accent_btn, t.accent, k), t.text_c
    elif not enabled:
        fill, col = mix(t.panel, t.panel_hi, k), t.faint
    else:
        fill, col = mix(t.panel_hi, t.focus_fill, k), mix(t.dim, t.text_c, k)
    panel(t, s, rect, fill)
    _btn_label(t, s, rect, label, icon, col)


def button_row(t, s, x, y, items, focus, key=None):
    """A row of buttons; each lights up in place when focused (nothing slides).
    items: [(label, icon, enabled, accent)]; focus = index or None. Returns the rects."""
    rects, bx = [], x
    for i, (label, icon, en, acc) in enumerate(items):
        r = pg.Rect(int(bx), int(y), button_w(t, label, icon), t.btn_h)
        button(t, s, r, label, focused=(i == focus), enabled=en, icon=icon, accent=acc)
        rects.append(r)
        bx = r.right + t.sm
    return rects


def _btn_label(t, s, rect, label, icon, col):
    if icon == "gear":                             # icon-only button
        icon_draw(s, "gear", rect.center, int(rect.h * 0.46), col)
        return
    gap, ih = t.sm, int(t.f_btn.get_height() * 0.5)
    w = t.f_btn.size(label)[0] + ((int(ih * 0.9) + gap) if icon else 0)
    x = rect.centerx - w / 2                       # icon + label centred as one group
    if icon:
        x += icon_draw(s, icon, (x + ih * 0.45, rect.centery), ih, col) + gap
    text(t, s, label, x, rect.centery, t.f_btn, color=col, anchor="midleft")


def button_w(t, label, icon=None):
    """Natural width of a button (label + padding), at least btn_min. ⚙ = square."""
    if icon == "gear":
        return t.btn_h
    w = t.f_btn.size(label)[0] + (t.f_btn.get_height() * 0.5 + t.sm if icon else 0)
    return int(max(t.u * 18, w + t.md * 2))


TAG_KINDS = {"neutral": ("tag_bg", "text_c"), "accent": ("accent_tint", "accent_soft"),
             "error": ("error_bg", "error_soft"), "dark": (None, "text_c")}


def tag(t, s, label, x, y, kind="neutral", anchor="topleft", icon_name=None):
    """Info label — never pressable: squared corners, LABEL size, UPPERCASE.
    kinds: neutral (platform, size), accent (Installed, Recommended, Developer),
    error (Failed), dark (on top of images, e.g. '+2 more')."""
    fill_k, col_k = TAG_KINDS[kind]
    col = getattr(t, col_k)
    img = t.f_hint.render(label.upper(), True, col)
    ih = int(t.f_hint.get_height() * 0.5)
    iw = int(ih * 0.9) + t.xs if icon_name else 0
    r = pg.Rect(0, 0, img.get_width() + iw + t.u * 1.6, int(t.f_hint.get_height() + t.u * 0.7))
    setattr(r, anchor, (int(x), int(y)))
    if fill_k:
        pg.draw.rect(s, getattr(t, fill_k), r, border_radius=t.tag_r)
    else:
        chip = pg.Surface(r.size, pg.SRCALPHA)
        pg.draw.rect(chip, (0, 0, 0, t.chip_a + 40), chip.get_rect(), border_radius=t.tag_r)
        s.blit(chip, r)
    if icon_name:
        icon_draw(s, icon_name, (r.x + t.u * 0.8 + ih * 0.45, r.centery), ih, col)
    s.blit(img, img.get_rect(center=(r.centerx + iw // 2, r.centery)))
    return r


def wordmark(t, s, x, y, anchor="topleft"):
    """The logo: SCRiTCH in bold, letters purple, the lowercase i white. No pill.
    Drawn letter by letter (advance = width of the text so far, so kerning stays right)."""
    f = t.font("Bold", t.u * 3.2)
    if anchor in ("baseleft", "baseright"):
        anchor, y = ("topleft" if anchor == "baseleft" else "topright"), y - f.get_ascent()
    box = pg.Rect(0, 0, f.size(APP_NAME)[0], f.get_height())
    setattr(box, anchor, (int(x), int(y)))
    for i, ch in enumerate(APP_NAME):
        col = t.text_c if ch == "i" else t.accent
        s.blit(f.render(ch, True, col), (box.x + f.size(APP_NAME[:i])[0], box.y))
    return box


def pill(t, s, label, x, y, fill=None, color=None, font=None, anchor="topleft"):
    font = font or t.f_small
    img = font.render(label, True, color or t.text_c)
    r = pg.Rect(0, 0, img.get_width() + t.u * 1.8, img.get_height() + t.u * 0.6)
    setattr(r, anchor, (int(x), int(y)))
    pg.draw.rect(s, fill or (0, 0, 0), r, border_radius=r.h // 2)
    s.blit(img, img.get_rect(center=r.center))
    return r


_ARCS = {}
_SS = 4          # supersampling: draw arcs 4x larger, smoothscale down = smooth edges


def _arc(r, width, start, sweep, color, track, disc=None):
    """Anti-aliased ring/arc image (cached). start/sweep in turns (0..1), 0 = 12 o'clock."""
    start = round(start * 120) / 120            # 120 steps per turn: smooth, cache stays small
    key = (r, width, start, round(sweep, 3), color, track, disc)
    img = _ARCS.get(key)
    if img is not None:
        return img
    pad = 3
    R, Wd = r * _SS, width * _SS
    size = (r + pad) * 2 * _SS
    c = (size / 2, size / 2)
    big = pg.Surface((size, size), pg.SRCALPHA)
    if disc:
        pg.draw.circle(big, disc, c, R + 2 * _SS)
    if track:
        pg.draw.circle(big, track, c, R, Wd)
    if sweep > 0:
        n = max(8, int(160 * sweep))
        pts_o, pts_i = [], []
        for i in range(n + 1):
            a = 2 * math.pi * (start + sweep * i / n) - math.pi / 2
            pts_o.append((c[0] + R * math.cos(a), c[1] + R * math.sin(a)))
            pts_i.append((c[0] + (R - Wd) * math.cos(a), c[1] + (R - Wd) * math.sin(a)))
        pg.draw.polygon(big, color, pts_o + pts_i[::-1])
    img = pg.transform.smoothscale(big, (size // _SS, size // _SS))
    if len(_ARCS) > 600:
        _ARCS.clear()
    _ARCS[key] = img
    return img


def frame_tick():
    """Changes every frame in the live app: put it in a cache key to keep something animated."""
    import time
    return int(time.monotonic() * 60) if LIVE else 0


def _turn():
    import time
    return time.monotonic() * 1.2 if LIVE else 0.0


def ring(t, s, center, r, frac, width=None, busy=False):
    """Download progress ring. busy=True (unpacking / waiting): a spinning arc instead."""
    width = width or max(3, r // 4)
    if busy:                                     # lively: spins + the arc breathes long/short
        tt = _turn() * 1.5
        start, sweep = tt % 1, 0.18 + 0.42 * (0.5 - 0.5 * math.cos(tt * 2.4))
    else:
        start, sweep = 0, max(0.0, min(1.0, frac))
    img = _arc(r, width, start, sweep, t.accent, (255, 255, 255, 60), disc=(0, 0, 0, t.chip_a))
    s.blit(img, img.get_rect(center=center))


def spinner(t, s, center, r, phase=0.0, width=None):
    width = width or max(3, r // 5)
    img = _arc(r, width, (phase + _turn()) % 1, 0.75, t.accent, t.panel_hi)
    s.blit(img, img.get_rect(center=center))


def progress(t, s, rect, frac=None, phase=0.3):
    """frac=None draws an indeterminate bar that glides back and forth (live app)."""
    stretch = 1.0
    if frac is None and LIVE:                    # bouncy: springs end to end, stretches
        import time                              # mid-flight, squashes at the ends
        x = time.monotonic() / BUSY_SWEEP_S % 2
        x, back = (x, False) if x < 1 else (x - 1, True)
        phase = spring(x)
        phase = 1 - phase if back else phase
        stretch = 0.6 + 1.1 * math.sin(math.pi * x)
    pg.draw.rect(s, t.panel_hi, rect, border_radius=rect.h // 2)
    if frac is None:
        seg = max(rect.h, int(rect.w * 0.22 * stretch))
        x = rect.x + int((rect.w - seg) * max(0.0, min(1.0, phase)))
        pg.draw.rect(s, t.accent, (x, rect.y, seg, rect.h), border_radius=rect.h // 2)
    elif frac > 0:
        pg.draw.rect(s, t.accent, (rect.x, rect.y, max(rect.h, int(rect.w * frac)), rect.h),
                     border_radius=rect.h // 2)


BUSY_SWEEP_S = 0.75   # one end-to-end bounce of the indeterminate bar


# --- tiles ------------------------------------------------------------------
def tile(t, s, game, rect, focused=False):
    """Library tile: cover in rect, title under it. rect is the unscaled cover area."""
    playable = game["platforms"] & {"linux", "windows"}
    k = anim(("tile", game["id"]), 1.0 if focused else 0.0)
    grow = (t.focus_scale - 1) * k
    r = rect.inflate(rect.w * grow, rect.h * grow) if grow else rect
    img = rounded(cover(t, game, r.size), t.radius)
    if not playable:
        img = img.copy()
        o = pg.Surface(r.size, pg.SRCALPHA)
        pg.draw.rect(o, (0, 0, 0, t.dimmed_a), o.get_rect(), border_radius=t.radius)
        img.blit(o, (0, 0))
    s.blit(img, r.topleft)
    if k > 0.5:
        focus_ring(t, s, r)
    _badges(t, s, game, r, playable)
    ty = r.bottom + t.xs
    col = t.text_c if (focused or playable) else t.faint
    text(t, s, game["title"], rect.x, ty, t.f_small, color=col, maxw=rect.w)
    if not playable:                  # info tag on the art, like the other tile badges
        tag(t, s, "Browser game" if "html" in game["platforms"] else "Not playable here",
            r.x + t.u, r.bottom - t.u, kind="dark", anchor="bottomleft")


def _badges(t, s, game, r, playable):
    pad = t.u
    st = game.get("state")
    # top-right: install state
    if st == "installed":
        c = (r.right - pad - t.u * 1.6, r.y + pad + t.u * 1.6)
        pg.draw.circle(s, t.accent, c, t.u * 1.6)
        icon_draw(s, "check", c, int(t.u * 1.4), t.on_accent)
    elif st == "downloading":
        ring(t, s, (int(r.right - pad - t.u * 1.6), int(r.y + pad + t.u * 1.6)), int(t.u * 1.6),
             game.get("progress", 0),
             busy=game.get("phase") in ("extract", "installing") or not game.get("progress"))
    elif st == "queued":
        tag(t, s, "Queued", r.right - pad, r.y + pad, kind="dark", anchor="topright")
    elif st == "missing":
        tag(t, s, "SD card missing" if game.get("missing") == "card" else "Files missing",
            r.right - pad, r.y + pad, kind="dark", anchor="topright")
    elif st == "failed":
        tag(t, s, "Failed", r.right - pad, r.y + pad, kind="error", anchor="topright")
    # no platform badge: Linux vs Windows/Proton is handled for the user, not shown on the art


def offline_mark(t, s, right, cy, since):
    """Small, quiet offline indicator for the top bar: cloud with a slash + 'Offline · <date>'."""
    r = text(t, s, f"Offline · synced {since}", right, cy, t.f_small, color=t.faint, anchor="baseright")
    u, cx = t.u, r.x - t.u * 2.6
    cy -= x_mid(t.f_small)
    c = t.faint
    pg.draw.circle(s, c, (int(cx - u * 0.6), int(cy + u * 0.2)), int(u * 0.7))
    pg.draw.circle(s, c, (int(cx + u * 0.2), int(cy - u * 0.3)), int(u * 0.95))
    pg.draw.circle(s, c, (int(cx + u * 0.9), int(cy + u * 0.25)), int(u * 0.6))
    pg.draw.rect(s, c, (int(cx - u * 0.6), int(cy + u * 0.1), int(u * 1.5), int(u * 0.75)))
    pg.draw.line(s, t.bg, (cx - u * 1.6, cy - u * 1.3), (cx + u * 1.7, cy + u * 1.4), max(4, u // 2))
    pg.draw.line(s, c, (cx - u * 1.5, cy - u * 1.2), (cx + u * 1.6, cy + u * 1.3), max(2, u // 4))
    return r.x - t.u * 2.6 - t.u * 1.7 - t.sm   # left of the cloud, then a gap


# --- overlays ---------------------------------------------------------------
def modal(t, s, title, body, buttons=None, focus=0):
    """Yes/no dialog with its buttons inside (Omri): [action, "Cancel"], focus lights one."""
    shade(t, s)
    lines = body if isinstance(body, list) else [body]
    pad = t.lg
    h = pad * 2 + t.f_h2.get_linesize() + t.sm + len(lines) * t.f_body.get_linesize()
    h += (t.lg + t.btn_h) if buttons else 0
    need = max([t.f_h2.size(title)[0]] + [t.f_body.size(ln)[0] for ln in lines]) + pad * 2
    r = pg.Rect(0, 0, min(t.w - 2 * t.m, max(t.read_w * 0.8, need)), h)
    r.center = (int(t.cx), int((t.h - t.hint_h) / 2))
    panel(t, s, r)
    y = text_named(t, s, title, r.x + pad, r.y + pad, t.f_h2).bottom + t.sm
    for ln in lines:
        y = text(t, s, ln, r.x + pad, y, t.f_body, color=t.dim).bottom
    if buttons:
        button_row(t, s, r.x + pad, y + t.lg,       # the action is red, Cancel grey
                   [(b, None, True, "danger" if i == 0 else False) for i, b in enumerate(buttons)],
                   focus)
    return r


def menu(t, s, title, sub, items, focus):
    """THE small list dialog: build picker, game Options (☰), Sort & filter (X).
    items: [(label, value, sub)] like W.rows. Actions are in the footer."""
    shade(t, s)
    w = min(t.w - 2 * t.m, t.read_w)
    row_h = int(t.u * (8.5 if any(i[2] for i in items) else 7))
    pad = t.lg
    head = t.f_h2.get_linesize() + (t.f_small.get_linesize() if sub else 0) + t.md
    h = pad * 2 + head + len(items) * (row_h + t.u // 2)
    r = pg.Rect(0, 0, w, h)
    r.center = (int(t.cx), int((t.h - t.hint_h) / 2))
    panel(t, s, r)
    ty = text(t, s, title, r.x + pad, r.y + pad, t.f_h2).bottom
    if sub:
        text(t, s, sub, r.x + pad, ty, t.f_small, color=t.dim)
    # rows sit inset by (pad - row padding) so their text lines up with the title
    rows(t, s, pg.Rect(r.x + pad - t.md, r.y + pad + head, r.w - 2 * (pad - t.md), 0),
         items, focus, row_h, key=("menu", title))
    return r


def toast(t, s, msg, error=False):
    k = anim(("toast", msg), 1.0, start=0.0)       # slides up + fades in once
    img = t.f_body.render(msg, True, t.text_c)
    dot = t.u * 0.7 if error else 0                 # red dot = this toast is an error
    r = pg.Rect(0, 0, img.get_width() + t.md * 2 + (dot * 2 + t.sm if error else 0),
                img.get_height() + t.sm * 2)
    box = pg.Surface(r.size, pg.SRCALPHA)
    lr = box.get_rect()
    panel(t, box, lr, t.panel_hi)
    x = t.md
    if error:
        pg.draw.circle(box, t.error, (x + dot, lr.centery), dot)
        x += dot * 2 + t.sm
    box.blit(img, img.get_rect(midleft=(x, lr.centery)))
    if k < 1:
        box.set_alpha(int(255 * max(0.0, min(1.0, k))))
    r.midbottom = (int(t.cx), int(t.h - t.hint_h - t.md + (1 - k) * t.md))
    s.blit(box, r)


def notice(t, s, x, y, w, title, body=None, kind="error"):
    """Status box. kind="error": red bar + error_bg (red only for errors);
    kind="info": neutral panel (SD card missing, queued…); kind="busy": neutral + spinner."""
    lh = t.f_btn.get_linesize() + (t.f_small.get_linesize() if body else 0)
    vpad = t.md if body else t.sm                 # one-liners stay slim
    r = pg.Rect(int(x), int(y), int(w), int(lh + vpad * 2))
    panel(t, s, r, t.error_bg if kind == "error" else t.panel)
    if kind == "error":
        pg.draw.rect(s, t.error, (r.x, r.y, max(3, t.u // 2), r.h),
                     border_top_left_radius=t.radius, border_bottom_left_radius=t.radius)
        tx = r.x + t.md
    elif kind == "busy":
        spinner(t, s, (r.x + t.md + t.u, r.centery), int(t.u * 1.2), 0.1)
        tx = r.x + t.md + t.u * 2 + t.sm
    else:
        tx = r.x + t.md
    ty = r.y + vpad
    text(t, s, title, tx, ty, t.f_btn if body else t.f_body, maxw=r.right - tx - t.md)
    if body:
        text(t, s, body, tx, ty + t.f_btn.get_linesize(), t.f_small, color=t.dim,
             maxw=r.right - tx - t.md)
    return r


def rows(t, s, rect, items, focus, row_h=None, key="rows"):
    """Settings/Picker list; the focused row lights up in place. items: [(label, value, sub)]."""
    row_h = row_h or int(t.u * 8.5)
    pad = t.md                                     # inset inside the row
    y = rect.y
    for i, (label, value, sub) in enumerate(items):
        r = pg.Rect(rect.x, y, rect.w, row_h)
        k = anim((key, label), 1.0 if i == focus else 0.0)
        if k > 0.01:
            panel(t, s, r, mix(t.panel_hi, t.focus_fill, k))
        ly = r.centery - (t.f_small.get_height() // 2 if sub else 0)
        text(t, s, label, r.x + pad, ly, t.f_btn, anchor="midleft")
        if sub:
            text(t, s, sub, r.x + pad, ly + t.f_btn.get_height() * 0.55, t.f_small,
                 color=t.dim, anchor="topleft", maxw=r.w * 0.6)
        if isinstance(value, tuple):               # (info text, purple action button or None)
            info, btn = value
            x = r.right - pad
            if btn:                                # the real button (row focus = its focus)
                br = pg.Rect(0, 0, button_w(t, btn), int(t.btn_h * 0.8))
                br.midright = (x, r.centery)
                button(t, s, br, btn, focused=(i == focus),       # row focus = A presses it
                       accent=btn in ("Update", "Restart"))      # purple only when one is waiting
                x = br.x - t.sm
            text(t, s, info, x, r.centery, t.f_body, color=t.dim, anchor="midright")
        elif value in ("Recommended", "Installed", "In use"):     # state tags (build picker)
            tag(t, s, value, r.right - pad, r.centery, kind="accent", anchor="midright")
        elif value:
            text(t, s, value, r.right - pad, r.centery, t.f_body, color=t.dim, anchor="midright")
        if i < len(items) - 1 and focus not in (i, i + 1):   # divider, not next to the lit row
            ly = r.bottom + t.u // 4
            pg.draw.line(s, t.line, (r.x + pad, ly), (r.right - pad, ly))
        y += row_h + t.u // 2
