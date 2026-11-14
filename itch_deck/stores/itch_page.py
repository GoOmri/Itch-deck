"""Reads a game's public itch page: full description, screenshot URLs, newest comments.
Not in itch's API, so this parses HTML. Tolerant on purpose: if itch changes its markup we
get fewer fields, never a crash, and the caller logs what was missing."""
import re
from html import unescape
from html.parser import HTMLParser

BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "tr"}
VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "col", "embed"}
MAX_COMMENTS = 10
MAX_REPLIES = 2


def _cls(attrs):
    return set((dict(attrs).get("class") or "").split())


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # [(tag, roles)] roles: set of what this element opened
        self.desc_parts = None   # list of text chunks while inside the description
        self.desc_done = False
        self.shots = []
        self.posts = []          # top-level comments, each with "reply_list"
        self.cur = None          # comment being read
        self.field = None        # "author" | "date" | "body" | "flag"
        self.more_link = False

    # --- helpers -----------------------------------------------------------------
    def _in(self, role):
        return any(role in r for _, r in self.stack)

    def _depth_of(self, role):
        for i in range(len(self.stack) - 1, -1, -1):
            if role in self.stack[i][1]:
                return i
        return -1

    def handle_starttag(self, tag, attrs):
        a, c, roles = dict(attrs), _cls(attrs), set()
        if tag in VOID:
            if tag == "br" and self.desc_parts is not None:
                self.desc_parts.append("\n")
            if tag == "br" and self.field == "body" and self.cur is not None:
                self.cur["text"] += " "
            return
        if tag in BLOCK and self.desc_parts is not None:
            self.desc_parts.append("\n\n")
        if "formatted_description" in c and not self.desc_done and self.desc_parts is None:
            roles.add("desc")
            self.desc_parts = []
        if "screenshot_list" in c:
            roles.add("shots")
        if tag == "a" and self._in("shots") and a.get("href", "").startswith("http"):
            self.shots.append(a["href"])
        if "community_post_replies" in c:
            roles.add("replies")
        if "community_post" in c:
            roles.add("post")
            reply = self._in("replies")
            self.cur = {"author": "", "date": "", "text": "", "dev": False, "reply": reply,
                        "replies": 0, "reply_list": []}
            if c & {"is_game_owner", "is_owner", "is_dev", "by_owner", "is_developer"}:
                self.cur["dev"] = True
            if reply and self.posts:
                parent = self.posts[-1]
                parent["replies"] += 1
                if len(parent["reply_list"]) < MAX_REPLIES:
                    parent["reply_list"].append(self.cur)
            elif not reply:
                self.posts.append(self.cur)
        if self.cur is not None and self._in("post") | ("post" in roles):
            if "post_author" in c:
                roles.add("f:author")
            elif "post_date" in c:
                roles.add("f:date")
                self.cur["date"] = a.get("title") or ""
            elif "post_body" in c:
                roles.add("f:body")
            elif c & {"author_flag", "post_flag", "dev_flag"} or "flag" in " ".join(c):
                roles.add("f:flag")
        if tag == "a" and "load_more" in " ".join(c):
            self.more_link = True
        self.stack.append((tag, roles))
        self._set_field()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        # pop to the matching tag (HTML in the wild is not always balanced)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, roles in self.stack[i:]:
                    if "desc" in roles:
                        self.desc_done = True
                    if "post" in roles:
                        self.cur = None
                del self.stack[i:]
                break
        self._set_field()

    def _set_field(self):
        self.field = None
        for _, roles in reversed(self.stack):
            for f in ("author", "date", "body", "flag"):
                if "f:" + f in roles:
                    self.field = f
                    return
            if "post" in roles:
                return

    def handle_data(self, data):
        if self.desc_parts is not None and not self.desc_done:
            self.desc_parts.append(data)
        if self.cur is None or not self.field:
            return
        if self.field == "author":
            self.cur["author"] += data.strip()
        elif self.field == "body":
            self.cur["text"] += data
        elif self.field == "flag" and data.strip().lower() in ("developer", "dev", "creator", "owner"):
            self.cur["dev"] = True
        elif self.field == "date" and not self.cur["date"]:
            self.cur["date"] = data.strip()


def _paragraphs(parts):
    raw = unescape("".join(parts or []))
    out = []
    for block in re.split(r"\n\s*\n", raw):
        line = re.sub(r"[ \t\r\f\v]+", " ", block).strip()
        line = re.sub(r" *\n *", "\n", line)
        if line:
            out.append(line)
    return out


def parse_row(html, name):
    """One row of the itch page's "More information" table as a list of values, e.g.
    parse_row(html, "Genre") -> ["Puzzle", "Adventure"]. [] if the developer left it out."""
    m = re.search(r"<td[^>]*>\s*" + re.escape(name) + r"\s*</td>\s*<td[^>]*>(.*?)</td>",
                  html, re.S | re.I)
    if not m:
        return []
    text = re.sub(r"<[^>]+>", "", m.group(1))
    return [x.strip() for x in text.replace("&amp;", "&").split(",") if x.strip()]


def parse_inputs(html):
    """The "Inputs" row of the More information table, e.g. ["Mouse", "Touchscreen"]."""
    return parse_row(html, "Inputs")


def parse(html):
    """-> {"description": [paragraphs], "shots": [urls], "comments": [...], "has_more": bool}"""
    p = _Parser()
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001  - keep whatever was read so far
        pass
    comments = []
    for c in p.posts[:MAX_COMMENTS]:
        for x in [c] + c["reply_list"]:
            x["text"] = re.sub(r"\s+", " ", x["text"]).strip()
            x.pop("reply", None)
        if c["text"] or c["author"]:
            comments.append(c)
    seen, shots = set(), []
    for u in p.shots:
        if u not in seen:
            seen.add(u)
            shots.append(u)
    return {"description": _paragraphs(p.desc_parts), "shots": shots, "comments": comments,
            "inputs": parse_inputs(html),
            "genre": parse_row(html, "Genre")[:1],              # first genre only (filter + info)
            "session": " ".join(parse_row(html, "Average session")),   # e.g. "About an hour"
            "comment_count": len(p.posts), "has_more": p.more_link or len(p.posts) > MAX_COMMENTS,
            "saw_comments_markup": bool(re.search(r'class="(?:[^"]* )?community_post[ "]', html))}
