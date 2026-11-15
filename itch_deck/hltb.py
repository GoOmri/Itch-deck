"""Time to beat from HowLongToBeat (unofficial: the site's own search API, like howlongtobeatpy).

HLTB hides its search endpoint behind a name that changes with each site build, so a session:
  1. reads the home page, finds the endpoint in one of its /_next/static/chunks/*.js files
     (falls back to /api/s),
  2. GETs <endpoint>/init for a short-lived token,
  3. POSTs the search with that token.
Only an exact (normalised) title or alias match counts: a wrong time is worse than none.
Stdlib only (via net). Any failure -> net.Offline, and the caller just shows nothing."""
import json
import re
import time
import unicodedata

from . import net

BASE = "https://howlongtobeat.com/"
# HLTB turns away unknown clients; a plain browser UA is what every HLTB client sends.
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
MAX_CHUNKS = 40
_POST = re.compile(r'fetch\s*\(\s*["\']/api/([a-zA-Z0-9_/]+)[^"\']*["\']\s*,\s*{[^}]*method:\s*'
                   r'["\']POST["\']', re.S | re.I)


def norm(title):
    """"Celeste™: Farewell Edition!" -> "celeste farewell edition"."""
    t = unicodedata.normalize("NFKD", re.sub("[™®©]", "", title or "")).encode("ascii", "ignore").decode().lower()
    t = t.replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def hours(sec):
    return round((sec or 0) / 3600, 2) or None


def pick(title, rows):
    """The row whose name or alias equals the title (normalised), else None."""
    want = norm(title)
    if not want:
        return None
    for r in rows:
        names = [r.get("game_name") or ""] + (r.get("game_alias") or "").split(",")
        if want in (norm(n) for n in names) and (r.get("comp_main") or r.get("comp_100")
                                                  or r.get("comp_all")):
            return r
    return None


def fmt(h):
    """2.4 -> "~2.5 h", 0.3 -> "~20 min", 14.6 -> "~15 h"."""
    if not h:
        return ""
    if h < 1:
        return f"~{max(5, round(h * 60 / 5) * 5)} min"
    if h < 10:
        v = round(h * 2) / 2
        return f"~{v:g} h"
    return f"~{round(h)} h"


def summary(t):
    """{"main": 4.1, "done": 9.0} -> "Main story ~4 h  ·  Completionist ~9 h"."""
    if not t:
        return ""
    bits = [f"Main story {fmt(t.get('main'))}" if t.get("main") else "",
            f"Completionist {fmt(t.get('done'))}" if t.get("done") else ""]
    return "  ·  ".join(b for b in bits if b)


def length_hours(t):
    """One number for the Length filter / sort: main story, else completionist."""
    return (t or {}).get("main") or (t or {}).get("done")


class Client:
    def __init__(self):
        self.endpoint = None      # "api/xyz"
        self.auth = None          # (token, key, value)

    def _get(self, url, **kw):
        return net.get(url, timeout=20, headers={"User-Agent": UA, "Referer": BASE}, **kw)

    def _endpoint(self):
        html = self._get(BASE).decode("utf-8", "replace")
        for src in re.findall(r'<script[^>]+src="([^"]*/_next/static/chunks/[^"]+)"', html)[:MAX_CHUNKS]:
            try:
                m = _POST.search(self._get(BASE + src.lstrip("/")).decode("utf-8", "replace"))
            except net.NotFound:
                continue
            if m:
                return "api/" + m.group(1).rstrip("/")
        return "api/s"

    def _session(self):
        self.endpoint = self.endpoint or self._endpoint()
        d = json.loads(self._get(f"{BASE}{self.endpoint}/init?t={int(time.time() * 1000)}"))
        key = next((v for k, v in d.items() if "key" in k.lower()), None)
        val = next((v for k, v in d.items() if "val" in k.lower()), None)
        self.auth = (d.get("token"), key, val)

    def search(self, title):
        """Raw result rows for a title (one retry with a fresh session if HLTB says no)."""
        for attempt in (0, 1):
            if not self.auth:
                self._session()
            tok, key, val = self.auth
            body = {"searchType": "games", "searchTerms": norm(title).split(), "searchPage": 1,
                    "size": 20, "useCache": True,
                    "searchOptions": {"games": {"userId": 0, "platform": "", "sortCategory": "popular",
                                                "rangeCategory": "main", "rangeTime": {"min": 0, "max": 0},
                                                "gameplay": {"perspective": "", "flow": "", "genre": "",
                                                             "difficulty": ""},
                                                "rangeYear": {"max": "", "min": ""}, "modifier": "hide_dlc"},
                                      "users": {"sortCategory": "postcount"},
                                      "lists": {"sortCategory": "follows"},
                                      "filter": "", "sort": 0, "randomizer": 0}}
            hdr = {"User-Agent": UA, "Referer": BASE, "Origin": BASE.rstrip("/"),
                   "Content-Type": "application/json", "Accept": "*/*"}
            if key:
                body[key] = val
                hdr.update({"x-auth-token": str(tok), "x-hp-key": str(key), "x-hp-val": str(val)})
            try:
                raw = net.get(BASE + self.endpoint, timeout=20, headers=hdr,
                              data=json.dumps(body).encode())
                return json.loads(raw).get("data") or []
            except (net.Offline, net.NotFound, ValueError):
                self.auth = None
                if attempt:
                    self.endpoint = None          # site rebuilt: rediscover next time
                    raise net.Offline("HowLongToBeat search failed") from None
        return []

    def lookup(self, title):
        """{"main": h, "done": h, "id": hltb id} or None when HLTB has no exact match."""
        r = pick(title, self.search(title))
        if not r:
            return None
        return {"main": hours(r.get("comp_main")), "done": hours(r.get("comp_100")),
                "id": r.get("game_id")}


if __name__ == "__main__":        # python -m itch_deck.hltb "Title" ...  (CI live check)
    import sys
    c, found = Client(), 0
    for name in sys.argv[1:]:
        t = c.lookup(name)
        found += bool(t)
        print(f"{name}: {summary(t) or 'not found'}  (endpoint {c.endpoint})")
    sys.exit(0 if found else 1)
