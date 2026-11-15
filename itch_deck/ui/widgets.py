"""Drawing helpers shared by every scene. All take the Theme `t` and a target surface `s`."""
import colorsys
import math
import zlib

import pygame as pg

from .. import pads

class _LRU(dict):
    """Drawn-image cache: drops the oldest entries instead of emptying itself (emptying made
    every cover reload from disk at once while scrolling)."""
    def __init__(self, cap):
        super().__init__()
        self.cap = cap

    def __setitem__(self, k, v):
        if k in self:
            super().__delitem__(k)
        super().__setitem__(k, v)
        while len(self) > self.cap:
            super().__delitem__(next(iter(self)))


_cover_cache = _LRU(900)
_src_cache = _LRU(400)        # decoded cover files, already shrunk (no disk read per size)
SRC_MAX = 720                 # longest side kept in memory: a focused TV tile is ~460 px wide
LIVE = False   # True in the running app: animate. False for mockups: draw the end state.


APP_NAME = "SCRiTCH"          # shown name; folders are "scritch" (v0.8.2), repo + package keep itch


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
    if val[0] != target * 1000.0:                 # busy until this tween has FINISHED, however
        end = val[3] + (ms or MOTION_MS) / 1000   # slow a frame is (a heavy page re-render took
        _busy_until = max(_busy_until, end + 0.05, time.monotonic() + 0.05)   # >50 ms: froze)
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


def wrap_lines(font, txt, maxw):
    """Word-wrap txt into lines that fit maxw pixels."""
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
    return lines


def wrap(t, s, txt, x, y, font, maxw, color=None, max_lines=None):
    """Draw word-wrapped text; returns the bottom y. max_lines cuts with an ellipsis."""
    lines = wrap_lines(font, txt, maxw)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit(font, lines[-1] + " …", maxw) if font.size(lines[-1] + " …")[0] > maxw \
            else lines[-1] + " …"
    for ln in lines:
        y = text(t, s, ln, x, y, font, color).bottom
    return y


NAME_RE = None


def name_runs(txt, color, accent, white):
    """THE name rule (DESIGN rule 1), in one place: wherever the app name appears in txt
    (any capitalisation), it is spelled SCRiTCH with every letter purple and the i white.
    Returns [(text, colour)] runs to draw left to right."""
    global NAME_RE
    import re
    if NAME_RE is None:
        NAME_RE = re.compile(re.escape(APP_NAME), re.I)
    runs, pos = [], 0
    for m in NAME_RE.finditer(txt):
        if m.start() > pos:
            runs.append((txt[pos:m.start()], color))
        runs += [("SCR", accent), ("i", white), ("TCH", accent)]
        pos = m.end()
    if pos < len(txt):
        runs.append((txt[pos:], color))
    return runs


def render_text(t, font, txt, color):
    """Every piece of on-screen text is rendered here, so the name is always right."""
    color = color or t.text_c
    if APP_NAME.lower() not in txt.lower():
        return font.render(txt, True, color)
    runs = name_runs(txt, color, t.accent, t.text_c)
    full = "".join(r for r, _ in runs)
    img = pg.Surface((font.size(full)[0], font.get_height()), pg.SRCALPHA)
    done = ""
    for part, col in runs:
        img.blit(font.render(part, True, col), (font.size(done)[0], 0))   # advance by the text
        done += part                                                       # so far: kerning
    return img


def text(t, s, txt, x, y, font, color=None, anchor="topleft", maxw=None):
    if maxw:
        txt = fit(font, txt, maxw)
    img = render_text(t, font, txt, color)
    if anchor in ("baseleft", "baseright"):   # sit on a shared baseline (mixed font sizes)
        anchor, y = ("topleft" if anchor == "baseleft" else "topright"), y - font.get_ascent()
    r = img.get_rect(**{anchor: (int(x), int(y))})
    s.blit(img, r)
    return r


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
        rgb = _src(path)
        w, h = rgb.get_size()
        k = (min if contain else max)(size[0] / w, size[1] / h)
        big = pg.transform.smoothscale(rgb, (max(1, round(w * k)), max(1, round(h * k))))
        out = pg.Surface(size)
        out.fill((0, 0, 0))
        out.blit(big, ((size[0] - big.get_width()) // 2, (size[1] - big.get_height()) // 2))
    except Exception:  # noqa: BLE001  - broken download: fall back to placeholder
        out = None
    _cover_cache[key] = out
    return out


def _src(path):
    """A cover file decoded once, as 32-bit, at most SRC_MAX px (Epic's art is 2560 px)."""
    img = _src_cache.get(path)
    if img is None:
        raw = pg.image.load(path)
        img = pg.Surface(raw.get_size(), 0, 32)    # palette GIF/PNG -> 32-bit for smoothscale
        img.blit(raw, (0, 0))
        w, h = img.get_size()
        if max(w, h) > SRC_MAX:
            k = SRC_MAX / max(w, h)
            img = pg.transform.smoothscale(img, (max(1, round(w * k)), max(1, round(h * k))))
        _src_cache[path] = img
    return img


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
PS_SHAPE = {"A": "cross", "B": "circle", "X": "square", "Y": "triangle"}   # SDL A = south = ✕
_shape_cache = {}


def _shape(name, d, ink):
    """DualSense face symbol (or the ⧉ View icon) as a d×d ink image, drawn 4× and scaled down
    so the strokes stay smooth. Outlines = filled shape minus a transparent inner shape."""
    key = (name, d, tuple(ink))
    if key in _shape_cache:
        return _shape_cache[key]
    k = 4
    D = d * k
    img = pg.Surface((D, D), pg.SRCALPHA)
    c, w, clear = D / 2, max(k * 2, D * 0.085), (0, 0, 0, 0)
    if name == "cross":
        a = D * 0.19
        for sx in (1, -1):
            pg.draw.line(img, ink, (c - a, c - sx * a), (c + a, c + sx * a), int(w * 1.15))
    elif name == "circle":
        pg.draw.circle(img, ink, (c, c), D * 0.22)
        pg.draw.circle(img, clear, (c, c), D * 0.22 - w)
    elif name == "square":
        a = D * 0.2
        pg.draw.rect(img, ink, (c - a, c - a, 2 * a, 2 * a))
        pg.draw.rect(img, clear, (c - a + w, c - a + w, 2 * (a - w), 2 * (a - w)))
    elif name == "triangle":
        r, cy = D * 0.25, c + D * 0.03          # a bit low: optically centred in the circle
        pts = [(c + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
               for a in (-90, 30, 150)]
        pg.draw.polygon(img, ink, pts)
        ri = r - 2 * w                          # inner triangle: same centre, stroke w all round
        pg.draw.polygon(img, clear, [(c + ri * math.cos(math.radians(a)),
                                      cy + ri * math.sin(math.radians(a))) for a in (-90, 30, 150)])
    elif name == "view":                         # ⧉: back square outlined, front square solid
        a, o, w = D * 0.21, D * 0.1, max(k * 2, D * 0.1)
        bx, by = c - a - o, c - a - o
        pg.draw.rect(img, ink, (bx, by, 2 * a, 2 * a), border_radius=int(D * 0.04))
        pg.draw.rect(img, clear, (bx + w, by + w, 2 * a - 2 * w, 2 * a - 2 * w),
                     border_radius=int(D * 0.02))
        pg.draw.rect(img, ink, (c - a + o, c - a + o, 2 * a, 2 * a), border_radius=int(D * 0.04))
    out = pg.transform.smoothscale(img, (d, d))
    _shape_cache[key] = out
    return out


def _ps_small(btn, h, col):
    """DualSense Create (BACK) / Options (MENU) as on the pad (Omri's reference, 15 Nov): a small
    oblong button leaning a little outward (Create's top to the left, Options' to the right),
    with its icon printed just above it: Create = three short strokes fanning out (\\ | /),
    Options = three horizontal lines. Solid white like every glyph. h = glyph height."""
    key = ("ps_small", btn, h, tuple(col))
    if key in _shape_cache:
        return _shape_cache[key]
    k = 4
    H = h * k
    W_ = int(H * 0.5)
    img = pg.Surface((W_, H), pg.SRCALPHA)
    cx = W_ / 2
    lean = -8 if btn == "BACK" else 8            # degrees; + = top leans right
    pw, ph = int(H * 0.34), int(H * 0.62)        # the button: about 1 : 2 like the pad
    pill_img = pg.Surface((pw, ph), pg.SRCALPHA)
    pg.draw.rect(pill_img, col, (0, 0, pw, ph), border_radius=pw // 2)
    pill_img = pg.transform.rotate(pill_img, -lean)
    img.blit(pill_img, pill_img.get_rect(center=(cx, H - ph / 2 - H * 0.02)))
    lw = max(k * 2, int(H * 0.075))
    top, bot = H * 0.02, H * 0.27                # icon band above the button
    if btn == "BACK":                            # three strokes on rays from a point below
        ox, oy = cx, bot + H * 0.16
        for a in (-38, 0, 38):
            r = math.radians(a)
            r0, r1 = (oy - bot) + H * 0.02, oy - top
            dx, dy = math.sin(r), -math.cos(r)
            pg.draw.line(img, col, (ox + dx * r0, oy + dy * r0), (ox + dx * r1, oy + dy * r1), lw)
            for end in (r0, r1):               # round caps
                pg.draw.circle(img, col, (ox + dx * end, oy + dy * end), lw / 2)
    else:                     # three horizontal lines, as wide as the button, gaps = line width
        lo = (bot + H * 0.03 - top) / 5
        for i in range(3):
            y = top + lo * (2 * i + 0.5)
            pg.draw.rect(img, col, (cx - pw * 0.5, y - lo / 2, pw, lo), border_radius=int(lo / 2))
    out = pg.transform.smoothscale(img, (W_ // k, h))
    _shape_cache[key] = out
    return out


def text_glyphs(t, s, line, cx, top, font, color):
    """One centred line with pad glyphs inline: "Press {X} to change it." draws the real X /
    square glyph for the pad in use instead of its name."""
    import re
    parts = re.split(r"\{(\w+)\}", line)               # text, btn, text, btn, …
    gap = t.u * 0.5
    sizes = [font.size(p)[0] if i % 2 == 0 else glyph(t, pg.Surface((1, 1)), p, 0, 0) + 2 * gap
             for i, p in enumerate(parts)]
    x, cy = cx - sum(sizes) / 2, top + font.get_height() / 2
    for i, (p, w) in enumerate(zip(parts, sizes)):
        if i % 2 == 0:
            text(t, s, p, x, cy, font, color=color, anchor="midleft")
        else:
            glyph(t, s, p, x + gap, cy)
        x += w


def glyph(t, s, btn, x, cy, ink=None, kind=None):
    """Steam-style button glyph: solid white shape, label knocked out in the dark ink colour.
    Follows the pad in use (pads.current, or kind=):
      Deck / Xbox: A B X Y letters in a circle; ☰ MENU and ⧉ BACK pills; L1 R1 L2 R2 squares
                   (Xbox: LB RB LT RT).
      DualSense:   ✕ ○ □ △ drawn in the circle; Create / Options drawn as on the pad (small
                   leaning button, icon above it: _ps_small); L1 R1 L2 R2.
    ◀ ▶ = circle. Left edge at x, centred on cy. Returns width. Labels centre on their bounds."""
    kind = kind or pads.current
    d = int(t.u * 3.0)
    c, ink = t.glyph_c, ink or t.glyph_ink
    if btn == "START":
        btn = "MENU"
    if kind == "ps" and btn in ("MENU", "BACK"):    # drawn like the pad: icon over a small pill
        img = _ps_small(btn, int(d * 1.25), c)
        s.blit(img, img.get_rect(midleft=(int(x), int(cy))))
        return img.get_width()
    if btn in ("MENU", "BACK"):
        r = pg.Rect(int(x), int(cy - d * 0.42), int(d * 1.45), int(d * 0.84))
        pg.draw.rect(s, c, r, border_radius=r.h // 2)
        if btn == "BACK":
            img = _shape("view", r.h, ink)
            s.blit(img, img.get_rect(center=r.center))
            return r.w
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
    if kind == "ps" and btn in PS_SHAPE:
        ctr = (int(x + d / 2), int(cy))
        pg.draw.aacircle(s, c, ctr, d // 2)
        pg.draw.circle(s, c, ctr, d // 2 - 1)
        img = _shape(PS_SHAPE[btn], d, ink)
        s.blit(img, img.get_rect(center=ctr))
        return d
    label = pads.name(btn, kind) if btn in pads.NAMES[kind] else btn
    img = t.f_glyph.render(label, True, ink)
    img = img.subsurface(img.get_bounding_rect())
    if len(label) == 1:
        ctr = (int(x + d / 2), int(cy))
        pg.draw.aacircle(s, c, ctr, d // 2)
        pg.draw.circle(s, c, ctr, d // 2 - 1)
        s.blit(img, img.get_rect(center=ctr))
        return d
    r = pg.Rect(int(x), int(cy - d / 2), max(d, img.get_width() + int(t.u * 1.0)), d)
    pg.draw.rect(s, c, r, border_radius=max(2, int(d * 0.18)))
    s.blit(img, img.get_rect(center=r.center))
    return r.w


def splash(t, s, msg, sub=None):
    """The plain "Starting… / Returning…" frame. sub = text, or a glyph_line parts list."""
    s.blit(backdrop(t), (0, 0))
    text(t, s, msg, t.cx, t.h / 2, t.f_h2, anchor="center")
    if isinstance(sub, list):                 # words + pad glyphs (the quit hint)
        glyph_line(t, s, sub, t.cx, t.h / 2 + t.u * 6 - t.f_body.get_height() / 2, t.f_body,
                   color=t.dim)
    elif sub:
        text(t, s, sub, t.cx, t.h / 2 + t.u * 6, t.f_body, color=t.dim, anchor="center")


def glyph_line(t, s, parts, cx, y, font, color=None):
    """One centred line mixing words and pad glyphs: ["To quit: hold", ("BACK",), "+", ...].
    Glyphs follow the pad in use, so the sentence always names the buttons you hold."""
    gap = font.size(" ")[0]
    items = []
    for p in parts:
        if isinstance(p, tuple):
            items.append(("g", p[0], glyph(t, pg.Surface((1, 1)), p[0], 0, 0)))
        else:
            img = render_text(t, font, p, color or t.text_c)
            items.append(("t", img, img.get_width()))
    total = sum(w for *_, w in items) + gap * (len(items) - 1)
    x = cx - total / 2
    mid = y + font.get_ascent() - font.metrics("H")[0][3] / 2   # glyphs centre on the capitals
    for kind, what, w in items:
        if kind == "g":
            glyph(t, s, what, x, mid)
        else:
            s.blit(what, (int(x), int(y)))
        x += w + gap
    return pg.Rect(int(cx - total / 2), int(y), int(total), font.get_height())


def hint_bar(t, s, items, activity=None, notice=None):
    """Steam-style footer: actions right-aligned, white UPPERCASE labels.
    items: [(button, label), ...]; an empty label pairs the glyph with the next one (L1 R1).
    Left side = background work (chasing spinner + dim text), else update news in purple."""
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
    room = int(x - t.lg - t.m)                     # left side never runs into the actions
    if activity:
        sr = int(t.u * 1.2)
        spinner(t, s, (t.m + sr, cy), sr, 0.15)
        text(t, s, activity, t.m + sr * 2 + t.sm, cy, t.f_small, color=t.dim, anchor="midleft",
             maxw=room - sr * 2 - t.sm)
    elif notice:
        text(t, s, notice, t.m, cy, t.f_small, color=t.accent, anchor="midleft", maxw=room)
    for (btn, label), (gw, lw) in zip(items, widths):
        glyph(t, s, btn, x, cy)
        x += gw + gap
        if label:
            text(t, s, label.upper(), x, cy, t.f_hint, color=t.text_c, anchor="midleft")
            x += lw + sep


# --- controls ---------------------------------------------------------------
def _i_disk(b, d, w, c):                 # size: a drive
    pg.draw.rect(b, c, (d * .1, d * .22, d * .8, d * .56), w, border_radius=int(d * .1))
    pg.draw.line(b, c, (d * .1, d * .56), (d * .9, d * .56), w)
    pg.draw.circle(b, c, (d * .74, d * .67), w * 0.7)


def _i_tag(b, d, w, c):                  # genre: a label tag
    pts = [(d * .12, d * .2), (d * .52, d * .2), (d * .88, d * .52), (d * .54, d * .86),
           (d * .12, d * .5)]
    pg.draw.polygon(b, c, pts, w)
    pg.draw.circle(b, c, (d * .32, d * .38), w * 0.8)


def _i_clock(b, d, w, c):                # time to beat
    pg.draw.circle(b, c, (d / 2, d / 2), d * .4, w)
    pg.draw.line(b, c, (d / 2, d / 2), (d / 2, d * .26), w)
    pg.draw.line(b, c, (d / 2, d / 2), (d * .68, d * .6), w)


def _i_mouse(b, d, w, c):                # controls: trackpad as mouse
    pg.draw.rect(b, c, (d * .26, d * .1, d * .48, d * .8), w, border_radius=int(d * .24))
    pg.draw.line(b, c, (d / 2, d * .14), (d / 2, d * .38), w)


def _i_keys(b, d, w, c):                 # controls: buttons as keyboard
    pg.draw.rect(b, c, (d * .06, d * .24, d * .88, d * .52), w, border_radius=int(d * .08))
    for i in range(4):
        pg.draw.circle(b, c, (d * (.24 + i * .17), d * .42), w * 0.75)
    pg.draw.line(b, c, (d * .3, d * .6), (d * .7, d * .6), w)


_LINE_ICONS = {"disk": _i_disk, "tag": _i_tag, "clock": _i_clock, "mouse": _i_mouse,
               "keys": _i_keys}


def facts(t, s, x, y, items, maxw):
    """Game facts as one calm row of icon + value pairs (wraps if it must):
    items = [(icon, text, color or None)]. Icons dim, values white, a wide gap between.
    Returns the bottom y."""
    f = t.f_body
    ih = int(f.get_height() * 0.8)
    gap, row_h = t.lg, f.get_linesize() + t.sm
    cx, cy = x, y + f.get_height() / 2
    for icon, txt, col in items:
        w = ih + t.sm + f.size(txt)[0]
        if cx > x and cx + w > x + maxw:                 # next line
            cx, cy = x, cy + row_h
        iw = icon_draw(s, icon, (cx + ih / 2, cy), ih * (0.7 if icon == "check" else 1),
                       col or t.dim)
        iw = max(iw, ih)                                  # same slot for every icon: values align
        text(t, s, txt, cx + iw + t.sm, cy, f, color=col or t.text_c, anchor="midleft")
        cx += w + gap
    return int(cy + f.get_height() / 2)


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
    if name in ("left", "right"):        # small value arrows (◀ ▶ around a setting)
        sg = 1 if name == "right" else -1
        a = h * 0.5
        pts = [(cx - sg * a * 0.8, cy - a), (cx - sg * a * 0.8, cy + a), (cx + sg * a * 0.8, cy)]
        pg.draw.polygon(s, color, pts)
        pg.draw.aalines(s, color, True, pts)
        return int(a * 1.6)
    if name in _LINE_ICONS:              # outline icons for the game page facts (supersampled)
        k, d = 4, int(h * 4)
        big = pg.Surface((d, d), pg.SRCALPHA)
        _LINE_ICONS[name](big, d, max(2, int(d * 0.11)), color)
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
    elif not enabled:                              # greyed out, but focus still clearly shows
        fill, col = mix(t.panel, t.focus_fill, k * 0.75), mix(t.faint, t.dim, k)
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
    img = render_text(t, t.f_hint, label.upper(), col)      # name rule holds in tags too
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


def wordmark(t, s, x, y, anchor="topleft", size=3.2):
    """The logo: SCRiTCH in bold, letters purple, the lowercase i white. No pill.
    Drawn letter by letter (advance = width of the text so far, so kerning stays right)."""
    f = t.font("Bold", t.u * size)
    if anchor in ("baseleft", "baseright"):
        anchor, y = ("topleft" if anchor == "baseleft" else "topright"), y - f.get_ascent()
    box = pg.Rect(0, 0, f.size(APP_NAME)[0], f.get_height())
    setattr(box, anchor, (int(x), int(y)))
    s.blit(render_text(t, f, APP_NAME, None), box)      # same name rule as all text
    return box


def pill(t, s, label, x, y, fill=None, color=None, font=None, anchor="topleft"):
    font = font or t.f_small
    img = render_text(t, font, label, color)
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


CHASE_S = 1.4          # one grow + shrink of the busy arc


def chase(phase=0.0):
    """Busy arc as (start, sweep) in turns: the front edge races ahead, then the back edge
    catches up, while the whole thing turns slowly. Same motion as the phone page spinner."""
    if not LIVE:
        return phase % 1, 0.6                    # mockups: one calm still pose
    import time
    lo, hi = 0.06, 0.78
    d = hi - lo
    x = time.monotonic() / CHASE_S + phase
    n, k = int(x), x - int(x)
    io = lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
    head = n * d + d * io(min(1.0, k * 2)) + lo
    tail = n * d + d * io(max(0.0, k * 2 - 1))
    spin = time.monotonic() * 0.22
    return (tail + spin) % 1, head - tail


def ring(t, s, center, r, frac, width=None, busy=False):
    """Download progress ring. busy=True (unpacking / waiting): the chasing arc instead."""
    width = width or max(3, r // 4)
    start, sweep = chase() if busy else (0, max(0.0, min(1.0, frac)))
    img = _arc(r, width, start, sweep, t.accent, (255, 255, 255, 60), disc=(0, 0, 0, t.chip_a))
    s.blit(img, img.get_rect(center=center))


def spinner(t, s, center, r, phase=0.0, width=None):
    width = width or max(3, r // 5)
    start, sweep = chase(phase)
    img = _arc(r, width, start, sweep, t.accent, t.panel_hi)
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
        fill = pg.Rect(rect.x, rect.y, max(rect.h, int(rect.w * frac)), rect.h)
        if not LIVE or frac >= 1:
            pg.draw.rect(s, t.accent, fill, border_radius=rect.h // 2)
            return
        import time                              # filling: a soft light sweeps along it
        img = pg.Surface(fill.size, pg.SRCALPHA)
        pg.draw.rect(img, t.accent, img.get_rect(), border_radius=rect.h // 2)
        bw = max(rect.h * 4, int(rect.w * 0.18))
        band = _cover_cache.get(("bar-shine", bw, rect.h))
        if band is None:
            band = pg.Surface((bw, rect.h))
            for x in range(bw):
                v = int(42 * math.sin(math.pi * x / bw) ** 2)     # 40% softer (Omri)
                pg.draw.line(band, (v, v, v), (x, 0), (x, rect.h))
            _cover_cache[("bar-shine", bw, rect.h)] = band
        ph = time.monotonic() / BAR_SHINE_S % 1
        img.blit(band, (int(-bw + ph * (fill.w + bw * 2)), 0), special_flags=pg.BLEND_RGB_ADD)
        s.blit(img, fill)


BUSY_SWEEP_S = 0.75   # one end-to-end bounce of the indeterminate bar
BAR_SHINE_S = 1.6     # one light sweep along a filling progress bar
FILL_MS = 900         # progress fills glide to each new value (updates arrive in chunks)


# --- tiles ------------------------------------------------------------------
def tile(t, s, game, rect, focused=False):
    """Library tile: cover in rect, title under it. rect is the unscaled cover area."""
    playable = game["platforms"] & {"linux", "windows"}
    k = anim(("tile", game["id"]), 1.0 if focused else 0.0)
    grow = (t.focus_scale - 1) * k
    r = rect.inflate(rect.w * grow, rect.h * grow) if grow else rect
    loading = game.get("cover_url") and not game.get("cover_file")
    if loading:                       # cover on its way: dark purple with a passing shine
        _LOADING.add(game["id"])
        shimmer(t, s, r)
    else:
        if 0.001 < k < 0.999:         # growing / shrinking: scale the finished big one (cheap)
            full = rect.inflate(rect.w * (t.focus_scale - 1), rect.h * (t.focus_scale - 1))
            img = pg.transform.smoothscale(_tile_img(t, game, full.size, playable), r.size)
        else:
            img = _tile_img(t, game, r.size, playable)
        key = ("cover-in", game["id"])
        if game["id"] in _LOADING:    # just arrived: fade in over the shimmer, no pop
            _LOADING.discard(game["id"])
            _ANIM.pop(key, None)
            anim(key, 1.0, start=0.0, ms=MOTION_MS * 2)
        a = anim(key, 1.0, ms=MOTION_MS * 2) if key in _ANIM else 1.0
        if a < 0.99:
            shimmer(t, s, r)
            img = img.copy()
            img.set_alpha(int(255 * max(0.0, a)))
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


_LOADING = set()                      # tiles that showed the shimmer: their cover fades in
SHINE_S = 1.6                         # one sweep of the shine


def shimmer(t, s, r):
    """Cover placeholder while it downloads: dark purple, a soft light band sweeping across.
    Tiles are offset by position, so a row shimmers as one wave."""
    import time
    base = _cover_cache.get(("shimmer", r.size))
    if base is None:
        base = pg.Surface(r.size, pg.SRCALPHA)
        pg.draw.rect(base, mix(t.panel, t.accent_btn, 0.28), base.get_rect(), border_radius=t.radius)
        _cover_cache[("shimmer", r.size)] = base
    band = _cover_cache.get(("shine", r.h))
    if band is None:                  # soft vertical band, light in the middle, leaning a little
        bw = max(8, r.h // 2)
        band = pg.Surface((bw, r.h * 2))
        for x in range(bw):
            v = int(22 * math.sin(math.pi * x / bw) ** 2)
            pg.draw.line(band, (v, v, v + 4), (x, 0), (x, r.h * 2))
        band = pg.transform.rotozoom(band, -14, 1)          # smooth edges
        _cover_cache[("shine", r.h)] = band
    img = base.copy()
    ph = ((time.monotonic() / SHINE_S) - r.x / (t.w * 1.5)) % 1 if LIVE else 0.45
    x = int(-band.get_width() + ph * (r.w + band.get_width() * 2))
    img.blit(band, (x, (r.h - band.get_height()) // 2), special_flags=pg.BLEND_RGB_ADD)
    s.blit(img, r.topleft)
    if LIVE:
        global _busy_until
        _busy_until = max(_busy_until, time.monotonic() + 0.05)   # keep frames coming


def _tile_img(t, game, size, playable):
    """Rounded (and dimmed when not playable) cover at one size, made once, not every frame."""
    key = ("tile", game["id"], game.get("cover_file"), size, bool(playable), t.radius)
    img = _cover_cache.get(key)
    if img is None:
        img = rounded(cover(t, game, size), t.radius)
        if not playable:
            o = pg.Surface(size, pg.SRCALPHA)
            pg.draw.rect(o, (0, 0, 0, t.dimmed_a), o.get_rect(), border_radius=t.radius)
            img.blit(o, (0, 0))
        _cover_cache[key] = img
    return img


_WAS_BUSY = set()       # games seen downloading: their ✓ pops in once when they finish


def mark_done(gid):
    """An install just finished: pop the ✓ the next time its tile is drawn."""
    _WAS_BUSY.add(gid)


def _badges(t, s, game, r, playable):
    pad = t.u
    st = game.get("state")
    if st in ("downloading", "queued"):
        _WAS_BUSY.add(game["id"])
    # top-right: install state
    if st == "installed" and game.get("update"):       # newer build on itch
        tag(t, s, "Update", r.right - pad, r.y + pad, kind="accent", anchor="topright")
    elif st == "installed":
        key = ("check-pop", game["id"])
        if game["id"] in _WAS_BUSY:                   # just finished: pop in (the one "done" spring)
            _WAS_BUSY.discard(game["id"])
            _ANIM.pop(key, None)
            anim(key, 1.0, start=0.0, back=TAB_BACK)
        k = anim(key, 1.0, back=TAB_BACK) if key in _ANIM else 1.0
        if k > 0.02:
            c = (r.right - pad - t.u * 1.6, r.y + pad + t.u * 1.6)
            pg.draw.circle(s, t.accent, c, t.u * 1.6 * k)
            icon_draw(s, "check", c, max(1, int(t.u * 1.4 * k)), t.on_accent)
    elif st == "downloading":
        ring(t, s, (int(r.right - pad - t.u * 1.6), int(r.y + pad + t.u * 1.6)), int(t.u * 1.6),
             anim(("ring", game["id"]), game.get("progress", 0), ms=FILL_MS),   # glides
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
    pad = t.lg
    # body text wraps inside the dialog, never runs past it (design rule: dialogs)
    paras = body if isinstance(body, list) else [body]
    need = max([t.f_h2.size(title)[0]] + [t.f_body.size(p)[0] for p in paras]) + pad * 2
    w = min(t.w - 2 * t.m, max(t.read_w * 0.8, min(need, t.read_w)))   # widen, then wrap
    lines = [ln for para in (body if isinstance(body, list) else [body])
             for ln in (wrap_lines(t.f_body, para, w - 2 * pad) or [""])]
    h = pad * 2 + t.f_h2.get_linesize() + t.sm + len(lines) * t.f_body.get_linesize()
    h += (t.lg + t.btn_h) if buttons else 0
    r = pg.Rect(0, 0, w, h)
    r.center = (int(t.cx), int((t.h - t.hint_h) / 2))
    panel(t, s, r)
    y = text(t, s, title, r.x + pad, r.y + pad, t.f_h2).bottom + t.sm
    for ln in lines:
        y = text(t, s, ln, r.x + pad, y, t.f_body, color=t.dim).bottom
    if buttons:
        button_row(t, s, r.x + pad, y + t.lg,       # the action is red, Cancel grey
                   [(b, None, True, "danger" if i == 0 else False) for i, b in enumerate(buttons)],
                   focus)
    return r


def details_box(t, s, title, sub, lines):
    """Game ⚙ → Details: the last lines of the game's log, small and dim (for troubleshooting;
    the screen elsewhere keeps to short plain words)."""
    shade(t, s)
    pad = t.lg
    w = min(t.w - 2 * t.m, int(t.read_w * 1.5))
    lh = t.f_small.get_linesize()
    room = t.h - t.hint_h - 2 * t.m - 2 * pad - t.f_h2.get_linesize() - lh - t.md
    lines = lines[-max(1, room // lh):]
    h = 2 * pad + t.f_h2.get_linesize() + lh + t.md + max(1, len(lines)) * lh
    r = pg.Rect(0, 0, w, h)
    r.center = (int(t.cx), int((t.h - t.hint_h) / 2))
    panel(t, s, r)
    y = text(t, s, title, r.x + pad, r.y + pad, t.f_h2).bottom
    y = text(t, s, sub, r.x + pad, y, t.f_small, color=t.dim).bottom + t.md
    for ln in lines or ["Nothing logged for this game yet."]:
        y = text(t, s, ln, r.x + pad, y, t.f_small, color=t.text_c, maxw=w - 2 * pad).bottom
    return r


def menu(t, s, title, sub, items, focus, arrows=False):
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
         items, focus, row_h, key=("menu", title), arrows=arrows)
    return r


def toast(t, s, msg, error=False):
    k = anim(("toast", msg), 1.0, start=0.0)       # slides up + fades in once
    img = render_text(t, t.f_body, msg, None)
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


ACTION_ROW = "\0action"      # value that makes a row's label purple (a reset like Clear filters)
OFF_ROW = "\0off"            # same row when it can't do anything yet: faint, never focused


def rows(t, s, rect, items, focus, row_h=None, key="rows", arrows=False):
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
        action, off = value == ACTION_ROW, value == OFF_ROW   # purple at rest, white when lit
        if action or off:
            value = ""
        text(t, s, label, r.x + pad, ly, t.f_btn, anchor="midleft",
             color=t.faint if off else t.accent if action and i != focus else t.text_c)
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
        elif value and arrows and i == focus:      # ◀ value ▶: LEFT/RIGHT change it
            ah = int(t.f_body.get_height() * 0.36)
            x = r.right - pad - ah
            icon_draw(s, "right", (x + ah * 0.5, r.centery), ah, t.text_c)
            vr = text(t, s, value, x - t.sm, r.centery, t.f_body, color=t.text_c, anchor="midright")
            icon_draw(s, "left", (vr.x - t.sm - ah * 0.5, r.centery), ah, t.text_c)
        elif value:
            text(t, s, value, r.right - pad, r.centery, t.f_body, color=t.dim, anchor="midright")
        if i < len(items) - 1 and focus not in (i, i + 1):   # divider, not next to the lit row
            ly = r.bottom + t.u // 4
            pg.draw.line(s, t.line, (r.x + pad, ly), (r.right - pad, ly))
        y += row_h + t.u // 2
