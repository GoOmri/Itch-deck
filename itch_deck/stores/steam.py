"""Steam's public store data, used only to fill Epic game pages (text when Epic has none,
screenshots, genre). No key, no sign-in: the same endpoints Steam's own store pages use.

Matching is strict: a Steam game is used only when its name equals the Epic title after
normalising (case, ™/®, punctuation, "&" = "and"). No match -> nothing (never a wrong game)."""
import logging
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote

from .. import net

log = logging.getLogger("scritch")

SEARCH = "https://store.steampowered.com/api/storesearch/?term={q}&l=english&cc=US"
DETAILS = "https://store.steampowered.com/api/appdetails?appids={id}&l=english&cc=US"


def norm(title):
    t = (title or "").lower().replace("&", " and ")
    t = re.sub(r"[™®©]", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def find(title):
    """Steam app id whose name matches title exactly (normalised), or None."""
    want = norm(title)
    if not want:
        return None
    data = net.get_json(SEARCH.format(q=quote(title)), timeout=20)
    for item in (data or {}).get("items") or []:
        if item.get("type", "app") == "app" and norm(item.get("name")) == want:
            return item.get("id")
    return None


# Steam labels that aren't a kind of game (skipped), and Steam names that itch calls otherwise
NOT_GENRES = {"indie", "casual", "free to play", "early access", "massively multiplayer",
              "violent", "gore", "nudity", "sexual content"}
TO_ITCH = {"RPG": "Role Playing", "Education": "Educational"}


def pick_genre(genres):
    """First real genre in itch's words ("RPG" -> "Role Playing"), or "" if Steam only has
    labels like Indie / Casual / Free to Play."""
    for name in genres or []:
        if name and name.strip().lower() not in NOT_GENRES:
            return TO_ITCH.get(name.strip(), name.strip())
    return ""


def details(appid):
    """{"paras": [...], "shots": [url, ...], "genre": str} or None."""
    data = net.get_json(DETAILS.format(id=appid), timeout=20) or {}
    entry = data.get(str(appid)) or {}
    if not entry.get("success"):
        return None
    d = entry.get("data") or {}
    shots = [s.get("path_full") for s in d.get("screenshots") or [] if s.get("path_full")]
    genres = [x.get("description") for x in d.get("genres") or [] if x.get("description")]
    return {"paras": html_paras(d.get("about_the_game") or d.get("detailed_description") or ""),
            "shots": shots, "genre": pick_genre(genres), "genres": genres}


# --- text ------------------------------------------------------------------------------
class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "li", "ul", "ol", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.out.append("\n\n" if tag != "br" else "\n")
        if tag == "li":
            self.out.append("• ")

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_data(self, data):
        self.out.append(data)


def html_paras(html):
    """HTML or Markdown-ish store text -> plain paragraphs (images, links, markup dropped)."""
    if not html:
        return []
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", html)                 # markdown images
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)                # [text](link) -> text
    md = re.sub(r"^\s*#{1,6}\s*", "", md, flags=re.M)               # # headings
    md = re.sub(r"(\*\*|__)(.+?)\1", r"\2", md)                     # **bold**
    md = re.sub(r"^\s*[-*]\s+", "• ", md, flags=re.M)               # - list items
    p = _Text()
    p.feed(md)
    raw = unescape("".join(p.out))
    paras = []
    for block in re.split(r"\n\s*\n", raw):
        line = re.sub(r"[ \t\r\f\v]+", " ", block).strip()
        line = re.sub(r" *\n *", "\n", line)
        if line and not (paras and paras[-1] == line):
            paras.append(line)
    return paras[:40]
