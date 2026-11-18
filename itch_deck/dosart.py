"""Art and info for your own DOS games (v0.9.27): the folder name is cleaned, GOG's public catalog is asked,
and the best fitting product (if any) gives a cover, a description and screenshots.

Everything here is PURE (no network, no files, no pygame): the caller passes in a `fetch(url)` that returns
GOG's JSON. A weak or unclear match gives None, and the game then gets a generated title card.
Library._fetch_dosart does the downloading and the 30 day cache."""
import re
import unicodedata
import urllib.parse

CATALOG = ("https://catalog.gog.com/v1/catalog?limit=10&query=like%3A{q}&order=desc%3Ascore"
           "&productType=in%3Agame%2Cpack&page=1&countryCode=US&locale=en-US&currencyCode=USD")
MIN_SCORE = 60                 # below this a match is too weak: no match at all
ALGO = 3                       # bump when the matching changes: old "no match" answers are asked again

TEXT_VER = 3                   # bump when the text cutting changes: saved texts are fetched and cut again once
EPISODE_WORDS = {"episode", "ep", "chapter", "part"}
# shorthand folder names -> what the stores call the game (obvious ones only)
ALIASES = {("dave",): ["dangerous", "dave"], ("wolf3d",): ["wolfenstein", "3d"],
           ("duke3d",): ["duke", "nukem", "3d"], ("keen",): ["commander", "keen"]}
NOISE = {"shareware", "registered", "full", "retail", "cd", "dos", "cracked", "version", "ver", "cdrom"}
ROMAN = {"ii": 2, "iii": 3, "iv": 4, "vi": 6, "vii": 7, "viii": 8, "ix": 9}
PACK_WORDS = {"complete", "collection", "pack", "bundle", "trilogy", "anthology", "compilation"}
SKIP_LEAD = ("the", "commander")      # "Commander Keen" and "Keen" are the same game
YEAR_RE = re.compile(r"\b(19[89]\d)\b")
GROUP_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}")
SEP_RE = re.compile(r"\s[-–—]\s|:")


def fold(s):
    """Accents folded to plain letters (Pokémon -> Pokemon), signs like (TM) (R) (C) gone."""
    s = (s or "").replace("™", " ").replace("®", " ").replace("©", " ")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _words(text):
    text = text.lower().replace("&", " and ").replace("'", "").replace("’", "")
    return [w for w in re.sub(r"[^a-z0-9]+", " ", text).split() if w]


def parse(name, noise=True):
    """Folder name (or a GOG title with noise=False) -> {"words", "main", "year", "num", "bw", "text"}.
    words: clean lower-case words; main: the words before a " - " or ":" (the subtitle dropped);
    year: a 4 digit year 1980-1999 found in a (...) or [...] group (or at the very end); num: the
    sequel number (Keen 2, Doom II -> 2) or None; bw: words without the number word."""
    s = fold(name).replace("_", " ")
    year = None
    m = YEAR_RE.search(" ".join(GROUP_RE.findall(s)))       # read the year BEFORE the groups are dropped
    if m:
        year = int(m.group(1))
    s = GROUP_RE.sub(" ", s)
    s = re.sub(r"\((?:tm|r|c)\)", " ", s, flags=re.I)
    if noise:
        s = re.sub(r"\.(?:exe|com|bat|zip)\b", " ", s, flags=re.I)
        s = re.sub(r"\bver(?:sion)?\.?\s*v?\d+(?:\.\d+)*[a-z]?\b", " ", s, flags=re.I)
        s = re.sub(r"\bv\d+(?:\.\d+)*[a-z]?\b", " ", s, flags=re.I)
        s = re.sub(r"\b\d+(?:\.\d+)+[a-z]?\b", " ", s)             # 1.1, 1.0.2
        s = re.sub(r"(?i)\b([a-z]{3,})(\d{1,2})\s*$", r"\1 \2", s.strip())    # Doom2 -> Doom 2, Keen4 -> Keen 4
    s = re.sub(r"(?<=\w)\.(?=\w)", " ", s)
    s = re.sub(r"\btm\b", " ", s, flags=re.I) if noise else s    # a bare "tm" ("R-Type" keeps its R)
    # keep the separator for "main": mark it before the punctuation is flattened
    parts = SEP_RE.split(s, maxsplit=1)
    words = _words(s)
    main = _words(parts[0]) if len(parts) > 1 else words
    if noise:
        words = _drop_noise(words)
        main = _drop_noise(main)
        if year is None and len(words) > 1 and re.fullmatch(r"19[89]\d", words[-1]):
            year = int(words[-1])                              # "Doom 1993"
        if year is not None:
            words = [w for i, w in enumerate(words) if not (i > 0 and w == str(year))]
            main = [w for i, w in enumerate(main) if not (i > 0 and w == str(year))]
    if noise:
        words, main = _drop_episode(words), _drop_episode(main)
    num, bw = _number(words)
    _, bmain = _number(main)
    bhead = _head(words)
    headnum = None
    for i, w in enumerate(words):
        if i and ((w.isdigit() and len(w) <= 2) or w in ROMAN):
            headnum = words[:i + 1] if i + 1 < len(words) else None    # "commander keen 3" of "... keen must die"
            break
    return {"words": words, "main": main, "bw": bw, "bmain": bmain, "bhead": bhead, "headnum": headnum, "year": year, "num": num,
            "text": " ".join(words)}


def display(name):
    """Folder name -> (the title a player sees, the year or None). "Commander Keen 3 Keen Must Die
    (1990)(Apogee Software)" -> ("Commander Keen 3 Keen Must Die", 1990). Groups, version words, shareware /
    registered / cd / dos ..., underscores and extra spaces go; subtitles, case and accents stay (a name that
    is all lower case gets capitals). The folder itself and the game's id are never touched."""
    year = parse(name)["year"]
    s = fold_keep(name).replace("_", " ")
    s = GROUP_RE.sub(" ", s)
    s = re.sub(r"\.(?:exe|com|bat|zip)\b", " ", s, flags=re.I)
    s = re.sub(r"\bver(?:sion)?\.?\s*v?\d+(?:\.\d+)*[a-z]?\b", " ", s, flags=re.I)
    s = re.sub(r"\bv\d+(?:\.\d+)*[a-z]?\b", " ", s, flags=re.I)
    s = re.sub(r"\b\d+(?:\.\d+)+[a-z]?\b", " ", s)
    s = re.sub(r"(?<=\w)\.(?=\w)", " ", s)
    toks = []
    for i, w in enumerate(s.split()):
        bare = re.sub(r"[^a-z0-9]", "", w.lower())
        if bare == "tm" or (i and bare in NOISE):
            continue
        toks.append(w)
    if year and len(toks) > 1 and toks[-1] == str(year):
        toks.pop()
    t = " ".join(toks).strip(" -:–—,.")
    if not t:
        t = " ".join(name.replace("_", " ").split()) or name
    if t == t.lower():
        t = " ".join(w[:1].upper() + w[1:] for w in t.split())
    return t, year


PACK_TALK = re.compile(r"\b(?:packs?|bundles?|collections?|compilations?|includes?|including|included|both games|"
                       r"combined products?|all (?:three|four|five|\d+) games|two games|trilogy|bonus|"
                       r"episodes? (?:one|two|\d))\b|\w+\s*\+\s*\w+", re.I)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'A-Z0-9(])")
FILLER_START = re.compile(r"^\W*(?:owners? receives?|you(?:'ll)? (?:also )?(?:get|receive)|includes?|including|"
                          r"key features|features|bonus|contents|what'?s (?:in|included)|this (?:pack|bundle)"
                          r"|(?:the )?(?:pack|bundle|collection) (?:includes|contains))\b", re.I)
BULLET = re.compile(r"^\s*(?:[-*\u2022\u25cf\u00b7]|\d+[.)])\s*\S")


def _is_filler(line):
    return line.rstrip().endswith(":") or bool(FILLER_START.search(line)) or bool(BULLET.match(line))


def short_text(paras, limit=600):
    """A store description cut down for a DOS game page. Each paragraph is read LINE by LINE (GOG sends one block with
    line breaks): the opening lines are kept and reading stops at the first filler line ("Owners Receive:", "Key
    features", "Includes", "Bonus", a bullet list, anything ending with ":"). Sentences about a pack / bundle /
    "combined product" / "A + B" are dropped. At most about `limit` characters, cut at the end of a sentence.
    One paragraph is returned, or [] when nothing is left."""
    for para in paras or []:
        out, stopped = "", False
        for line in str(para).split("\n"):
            line = " ".join(line.split())
            if not line:
                continue
            if _is_filler(line):
                stopped = True
                break
            for x in [y.strip() for y in SENTENCE_RE.split(line) if y.strip()]:
                if PACK_TALK.search(x):
                    continue
                if out and len(out) + 1 > limit - 10:
                    stopped = True
                    break
                if out and len(out) + 1 + len(x) > limit:
                    stopped = True
                    break
                out = f"{out} {x}".strip()
            if stopped:
                break
        if len(out) > limit + 100:                   # one huge sentence: cut at a word
            out = out[:limit].rsplit(" ", 1)[0].rstrip(",;: ") + "\u2026"
        if out:
            return [out]
    return []


def search_name(name):
    """What the GOG lookup is asked: the clean title with its year in brackets ("Blood (1997)")."""
    t, y = display(name)
    return f"{t} ({y})" if y else t


def fold_keep(s):
    """Signs like (TM) (R) (C) removed; accents stay (this is for showing)."""
    s = (s or "").replace("™", " ").replace("®", " ").replace("©", " ")
    return re.sub(r"\((?:tm|r|c)\)", " ", s, flags=re.I)


def _drop_noise(words):
    out = [w for i, w in enumerate(words) if i == 0 or w not in NOISE]    # "Full Throttle" stays
    return out or words


def _drop_episode(words):
    """"bio menace episode 1" -> "bio menace" ("episode 1" is a part of the game, not a sequel)."""
    for i, w in enumerate(words):
        if i and w in EPISODE_WORDS and i + 1 < len(words) and (
                (words[i + 1].isdigit() and len(words[i + 1]) <= 2) or words[i + 1] in ROMAN):
            return words[:i] + words[i + 2:]
    return list(words)


def _head(words):
    """The words before the sequel number ("keen 4 secret of the oracle" -> "keen"); else all of them."""
    for i, w in enumerate(words):
        if i and ((w.isdigit() and len(w) <= 2) or w in ROMAN):
            return words[:i]
    return list(words)


def _number(words):
    """(sequel number or None, the words without that number word). Only a number after the first word
    counts ("1942" and "7th Guest" are names); lone i / v / x are not read as numbers."""
    for i, w in enumerate(words):
        if i and ((w.isdigit() and len(w) <= 2) or w in ROMAN):
            return (int(w) if w.isdigit() else ROMAN[w]), words[:i] + words[i + 1:]
    return None, list(words)


def _lead(ws):
    ws = list(ws)
    while len(ws) > 1 and ws[0] in SKIP_LEAD:
        ws = ws[1:]
    return ws


def queries(p):
    """The search texts to try, best first (at most 4); then the number-less one for the last try."""
    w = p["words"]
    full = " ".join(w)
    arabic = " ".join(str(ROMAN[x]) if x in ROMAN else x for x in w)
    forms = [full, " ".join(p["headnum"] or []), arabic, " ".join(p["main"]), " ".join(_lead(w)), " ".join(_lead(p["main"]))]
    out = []
    for f in forms:
        if f and f not in out:
            out.append(f)
    return out[:4]


def year_of(prod):
    for k in ("releaseDate", "storeReleaseDate"):
        m = re.match(r"\s*(\d{4})", str((prod or {}).get(k) or ""))
        if m:
            return int(m.group(1))
    return None


def is_pack(prod, cp):
    return (prod.get("productType") or "").lower() == "pack" or bool(PACK_WORDS & set(cp["words"]))


def _title_score(qbw, cp, pack):
    """0 = no match; else 40..100 (exact > starts with > contains every word)."""
    q, c = _lead(qbw), _lead(cp["bw"])
    if not q or not c:
        return 0
    if pack:
        if not set(q) <= set(c):
            return 0
        core = {w for w in c if w not in PACK_WORDS and w != "and"}
        if len(q) < 2 and core != set(q):          # one common word ("Dave") in a bigger title ("Dave the Diver
            return 40                              # Bundle", "Golf Classics Collection"): too weak, same as singles
        return 66
    if q == c:
        return 100
    if c[:len(q)] == q:
        if q == _lead(cp["bmain"]):
            return 85                                   # "Blood" = the part before the colon of "Blood: Fresh Supply"
        return 70 if len(q) >= 2 else 55                # but a lone word that only starts a title is weak
    if set(q) <= set(c):
        return 62 if len(q) >= 2 else 40       # one common word ("Dave") is too weak on its own
    return 0


def pack_has(cp, n):
    """Does a pack with this title contain sequel number n? "Commander Keen Complete Pack" (no numbers): any.
    "DOOM + DOOM II": 1 and 2 (a base name that shows twice also stands for number 1). "DOOM 3": only 3.
    Several numbers: everything between the smallest and the biggest ("Keen 4 - 6")."""
    nums = {int(w) if w.isdigit() else ROMAN[w] for i, w in enumerate(cp["words"])
            if i and ((w.isdigit() and len(w) <= 2) or w in ROMAN)}
    if not nums:
        return True
    if len(cp["bw"]) > len(set(cp["bw"])):
        nums.add(1)
    return min(nums) <= n <= max(nums)


def _score(q, prod, relaxed):
    """Score of one catalog product for the folder name q, or None when it can not be the game."""
    title = str(prod.get("title") or "")
    cp = parse(title, noise=False)
    if not cp["words"]:
        return None
    pack = is_pack(prod, cp)
    qnum = None if relaxed else q["num"]
    if not pack and (qnum or 1) != (cp["num"] or 1):   # a pack holds every episode; a single product must fit
        return None                                    # (no number = number 1: Doom is not Doom II)
    if pack and not pack_has(cp, qnum or 1):           # Doom 3 / Doom 64 are not inside "DOOM + DOOM II"
        return None
    best = max(_title_score(q["bw"], cp, pack),
               _title_score(q["bmain"], cp, pack) - 3 if q["bmain"] != q["bw"] else 0,
               _title_score(q["bhead"], cp, pack) - 3 if q["bhead"] != q["bw"] else 0)
    if best <= 0:
        return None
    if relaxed:
        best -= 8
    y, cy = q["year"], year_of(prod)
    if y and cy:
        d = abs(cy - y)
        if d == 0:
            best += 20
        elif d == 1:
            best += 12
        elif not pack:                             # a pack's date is the pack's, not the game's
            best -= 45                             # a game more than a year off its year loses to a pack
    if (prod.get("productType") or "game").lower() == "game":
        best += 4                                  # a single game beats a pack
    return best


def choose(name, products, relaxed=False):
    """Best catalog product for a folder name, or None. products = the "products" list of GOG's answer.
    Weak or unclear (two different games nearly tied) = None."""
    q = name if isinstance(name, dict) else parse(name)
    ranked = []
    for prod in products or []:
        if not isinstance(prod, dict) or not prod.get("id"):
            continue
        sc = _score(q, prod, relaxed)
        if sc is None or sc < MIN_SCORE:
            continue
        # equal scores: the original (earlier) release first, then the lower id
        ranked.append((-sc, year_of(prod) or 9999, str(prod.get("id")), prod, sc))
    if any(is_pack(r[3], parse(str(r[3].get("title")), False)) for r in ranked):
        # A DOS folder is not a 2000s remake: when a pack fits, a single game released in 2000 or later is
        # out (searching "doom" gives "DOOM (2016)" and the pack "DOOM + DOOM II" that holds the 1993 game).
        ranked = [r for r in ranked if (year_of(r[3]) or 0) < 2000
                  or is_pack(r[3], parse(str(r[3].get("title")), False))]
    if not ranked:
        return None
    ranked.sort(key=lambda r: r[:3])
    top = ranked[0]
    for other in ranked[1:]:
        if other[2] == top[2]:
            continue
        near = top[4] - other[4] < 5
        same_words = parse(str(top[3].get("title")), False)["bw"] == parse(str(other[3].get("title")), False)["bw"]
        both_packs = is_pack(top[3], parse(str(top[3].get("title")), False)) and \
            is_pack(other[3], parse(str(other[3].get("title")), False))
        if near and top[4] < 100 and not same_words and not both_packs:
            return None                            # two different games fit about equally: do not guess
        break
    return {"prod": top[3], "score": top[4]}


def pick_cover(prod, wide=True):
    """The cover for the library tile: GOG's WIDE picture (coverHorizontal; the tile is nearly 5:4, so it fills the
    tile with a small crop) and only when there is none the tall one (shown whole over a blurred copy)."""
    keys = ("coverHorizontal", "coverVertical") if wide else ("coverVertical", "coverHorizontal")
    for k in keys:
        u = str((prod or {}).get(k) or "").strip()
        if u:
            return ("https:" + u) if u.startswith("//") else u
    return None


def summary(prod, score=None):
    """The small, saveable record of a match (goes into the cache file)."""
    genres = []
    for g in (prod.get("genres") or []):
        n = g.get("name") if isinstance(g, dict) else g
        if n:
            genres.append(str(n))
    return {"id": str(prod["id"]), "title": str(prod.get("title") or ""), "slug": prod.get("slug") or "",
            "year": year_of(prod), "type": prod.get("productType") or "game",
            "cover": pick_cover(prod), "cover_tall": pick_cover(prod, wide=False), "genres": genres,
            "score": score}


def _alias_parse(p):
    """The folder name's shorthand written out ("dave2" -> "dangerous dave 2"), or None."""
    full = ALIASES.get(tuple(p["bw"]))
    if not full:
        return None
    text = " ".join(full + ([str(p["num"])] if p["num"] else []))
    q = parse(text)
    q["year"] = p["year"]
    return q


def _gather(fetch, queries_, seen):
    for q in queries_:
        data = fetch(CATALOG.format(q=urllib.parse.quote(q, safe="")))
        prods = (data or {}).get("products") if isinstance(data, dict) else None
        for x in prods or []:
            if isinstance(x, dict) and x.get("id") is not None:
                seen.setdefault(str(x["id"]), x)


def find(name, fetch):
    """Look a folder name up on GOG. fetch(url) -> GOG's JSON answer (dict with "products"); errors from it
    (Offline) are NOT caught: the caller must not cache an unfinished lookup. Returns summary dict or None.
    Stage 1: the cleaned name and its forms (and the shorthand written out: dave -> dangerous dave).
    Stage 2 (only if stage 1 found nothing): the series name cut BEFORE the number ("commander keen 3 keen must
    die" -> "commander keen"): that match is marked "fallback" and gives art only, never the text."""
    p = parse(name)
    if not p["words"]:
        return None
    seen = {}
    tries = [p] + [a for a in [_alias_parse(p)] if a]
    asked = set()
    for cp in tries:
        for q in queries(cp):
            if q in asked:
                continue
            asked.add(q)
            _gather(fetch, [q], seen)
            hit = choose(cp, list(seen.values()))
            if hit:
                return summary(hit["prod"], hit["score"])
    for cp in tries:                               # stage 2: without the number
        head = " ".join(cp["bhead"]) if cp["num"] else ""
        if not head or head in asked:
            continue
        asked.add(head)
        _gather(fetch, [head], seen)
        q2 = parse(head)
        q2["year"] = cp["year"]
        usable = [x for x in seen.values()         # a pack with its own numbers must hold the folder's number
                  if not is_pack(x, parse(str(x.get("title")), False)) or pack_has(parse(str(x.get("title")), False), cp["num"])]
        hit = choose(q2, usable)
        if hit:                                    # Omri 18 Nov: wrong art is OK here, but only the ART is used
            m = summary(hit["prod"], hit["score"])     # (GOG's text would describe another game)
            m["fallback"] = True
            m["source"] = "gog"
            return m
    return None


# --- Steam as a second source -------------------------------------------------------------------
STEAM_NOT_THE_GAME = {"soundtrack", "dlc", "demo", "ost", "artbook", "wallpaper", "expansion", "upgrade"}
STEAM_HEADER = "https://cdn.akamai.steamstatic.com/steam/apps/{id}/header.jpg"


def steam_choose(p, items):
    """Best Steam search result for the folder name p, or None. Strong matches only: the same title, or the
    folder title followed by a ":" / " - " subtitle ("Raptor" = "Raptor: Call of the Shadows"). The year is
    ignored (remasters); a numbered folder never matches another number."""
    best = None
    q = _lead(p["bw"])
    if not q:
        return None
    for it in items or []:
        if not isinstance(it, dict) or it.get("id") is None or (it.get("type") or "app") != "app":
            continue
        cp = parse(str(it.get("name") or ""), noise=False)
        if not cp["words"] or STEAM_NOT_THE_GAME & set(cp["words"]):
            continue
        if (p["num"] or 1) != (cp["num"] or 1):
            continue
        c = _lead(cp["bw"])
        if q == c:
            sc = 100
        elif c[:len(q)] == q and q == _lead(cp["bmain"]):
            sc = 85
        else:
            continue
        if best is None or sc > best[0]:
            best = (sc, it)
    return best


def find_steam(name, search):
    """Same folder name on Steam. search(term) -> the "items" list of Steam's store search. Returns a summary
    (source "steam", the wide header picture as cover) or None. Errors (Offline) are not caught."""
    p = parse(name)
    if not p["words"]:
        return None
    seen, asked = [], set()
    tries = [p] + [a for a in [_alias_parse(p)] if a]
    for cp in tries:
        for q in queries(cp)[:3]:
            if q in asked:
                continue
            asked.add(q)
            seen += [x for x in (search(q) or []) if isinstance(x, dict)]
            hit = steam_choose(cp, seen)
            if hit:
                it = hit[1]
                return {"id": str(it["id"]), "title": str(it.get("name") or ""), "slug": "", "year": None,
                        "type": "game", "cover": STEAM_HEADER.format(id=it["id"]), "cover_tall": None,
                        "genres": [], "score": hit[0], "source": "steam"}
    return None


def find_any(name, fetch_gog, search_steam):
    """GOG first; a number-dropped GOG match (art only) loses to a strong Steam match; no GOG match: Steam.
    Result carries "source": "gog" or "steam"."""
    m = find(name, fetch_gog)
    if m and not m.get("fallback"):
        m["source"] = "gog"
        return m
    st = find_steam(name, search_steam) if search_steam else None
    if st:
        return st
    if m:
        m["source"] = "gog"
    return m
