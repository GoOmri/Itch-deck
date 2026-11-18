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
ALGO = 1                       # bump when the matching changes: old "no match" answers are asked again

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
        s = re.sub(r"\bversion\s+v?\d+(?:\.\d+)*", " ", s, flags=re.I)
        s = re.sub(r"\bv\d+(?:\.\d+)*\b", " ", s, flags=re.I)
        s = re.sub(r"\b\d+(?:\.\d+)+\b", " ", s)             # 1.1, 1.0.2
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
    num, bw = _number(words)
    _, bmain = _number(main)
    bhead = _head(words)
    return {"words": words, "main": main, "bw": bw, "bmain": bmain, "bhead": bhead, "year": year, "num": num,
            "text": " ".join(words)}


def _drop_noise(words):
    out = [w for i, w in enumerate(words) if i == 0 or w not in NOISE]    # "Full Throttle" stays
    return out or words


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
    forms = [full, arabic, " ".join(p["main"]), " ".join(_lead(w)), " ".join(_lead(p["main"]))]
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
        return 66 if set(q) <= set(c) else 0
    if q == c:
        return 100
    if c[:len(q)] == q:
        if q == _lead(cp["bmain"]):
            return 85                                   # "Blood" = the part before the colon of "Blood: Fresh Supply"
        return 70 if len(q) >= 2 else 55                # but a lone word that only starts a title is weak
    if set(q) <= set(c):
        return 62 if len(q) >= 2 else 40       # one common word ("Dave") is too weak on its own
    return 0


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
            best -= 25
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


def pick_cover(prod):
    for k in ("coverVertical", "coverHorizontal"):
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
            "cover": pick_cover(prod), "genres": genres, "score": score}


def find(name, fetch):
    """Look a folder name up. fetch(url) -> GOG's JSON answer (dict with "products"); errors from it
    (Offline) are NOT caught: the caller must not cache an unfinished lookup.
    Returns summary dict or None. Order: the cleaned name and its alternative forms; only when none of them
    fits, the name without its trailing sequel number (less exact, so last)."""
    p = parse(name)
    if not p["words"]:
        return None
    seen = {}
    for q in queries(p):
        data = fetch(CATALOG.format(q=urllib.parse.quote(q, safe="")))
        prods = (data or {}).get("products") if isinstance(data, dict) else None
        for x in prods or []:
            if isinstance(x, dict) and x.get("id") is not None:
                seen.setdefault(str(x["id"]), x)
        hit = choose(p, list(seen.values()))
        if hit:
            return summary(hit["prod"], hit["score"])
    if p["num"] and p["bw"]:                       # "Dave 2": GOG may only have "Dangerous Dave"
        q = " ".join(p["bw"])
        data = fetch(CATALOG.format(q=urllib.parse.quote(q, safe="")))
        prods = data.get("products") if isinstance(data, dict) else None
        for x in prods or []:
            if isinstance(x, dict) and x.get("id") is not None:
                seen.setdefault(str(x["id"]), x)
        hit = choose(p, list(seen.values()), relaxed=True)
        if hit:
            return summary(hit["prod"], hit["score"])
    return None
