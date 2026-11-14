"""Offline tests: owned-keys quirks, pagination, itch page parsing, cache round-trip."""
import json

from itch_deck import library, net, paths
from itch_deck.stores import itch, itch_page


def _key(i, **g):
    base = {"id": i, "title": f"Game {i}", "user": {"username": "dev"}, "cover_url": "https://x/c.png",
            "url": f"https://dev.itch.io/g{i}", "p_linux": True}
    base.update(g)
    return {"id": 1000 + i, "game": base}


def test_owned_keys_list_object_and_empty():
    assert len(itch.parse_owned_keys({"owned_keys": [_key(1), _key(2)]})) == 2
    assert len(itch.parse_owned_keys({"owned_keys": {"0": _key(1)}})) == 1
    assert itch.parse_owned_keys({"owned_keys": {}}) == []
    assert itch.parse_owned_keys({}) == []


def test_platforms():
    assert itch.platforms_of({"p_windows": True, "p_osx": True}) == {"windows", "mac"}
    assert itch.platforms_of({"type": "html"}) == {"html"}
    assert itch.platforms_of({"classification": "soundtrack"}) == {"soundtrack"}
    assert itch.platforms_of({}) == {"other"}
    assert itch.platforms_of({"traits": ["p_linux", "p_windows", "can_be_bought"]}) == {"linux", "windows"}


def test_sync_pages_and_dedupe(monkeypatch):
    pages = {1: [_key(1), _key(2)], 2: {"0": _key(2, title="dup")}, 3: [_key(3)], 4: {}}
    seen = []

    def fake(url, key=None, timeout=20):
        n = int(url.rsplit("=", 1)[1])
        seen.append(n)
        return {"owned_keys": pages.get(n, [])}
    monkeypatch.setattr(net, "get_json", fake)
    games = itch.ItchStore("k").sync()
    assert [g["id"] for g in games] == ["1", "2", "3"]
    assert seen == [1, 2, 3, 4]


PAGE = """<html><body>
<div class="formatted_description user_formatted"><p>First &amp; best.</p><p>Line one<br>line two</p>
<ul><li>Feature A</li><li>Feature B</li></ul></div>
<div class="screenshot_list"><a href="https://img.itch.zone/a.png"><img></a>
<a href="https://img.itch.zone/b.png"><img></a></div>
<div class="community_post" id="post-1"><div class="post_header">
 <span class="post_author"><a href="#">alice</a></span>
 <span class="post_date" title="2024-01-01 10:00:00"><a>1 year ago</a></span></div>
 <div class="post_body user_formatted"><p>Runs great on Deck.</p></div>
 <div class="community_post_replies">
  <div class="community_post is_reply"><span class="post_author"><a>devname</a></span>
   <span class="author_flag">Developer</span><div class="post_body"><p>Thanks!</p></div></div>
  <div class="community_post"><span class="post_author"><a>bob</a></span><div class="post_body">Same</div></div>
  <div class="community_post"><span class="post_author"><a>carl</a></span><div class="post_body">+1</div></div>
 </div></div>
<div class="community_post"><span class="post_author"><a>dora</a></span><div class="post_body">Second</div></div>
</body></html>"""


def test_page_parse():
    p = itch_page.parse(PAGE)
    assert p["description"][0] == "First & best."
    assert "Line one\nline two" in p["description"]
    assert p["shots"] == ["https://img.itch.zone/a.png", "https://img.itch.zone/b.png"]
    c = p["comments"]
    assert [x["author"] for x in c] == ["alice", "dora"]
    assert c[0]["text"] == "Runs great on Deck." and c[0]["date"].startswith("2024")
    assert c[0]["replies"] == 3 and len(c[0]["reply_list"]) == 2
    assert c[0]["reply_list"][0]["dev"] is True and c[0]["reply_list"][0]["text"] == "Thanks!"


def test_page_parse_garbage_never_crashes():
    p = itch_page.parse("<div class='formatted_description'><p>unclosed <b>bold")
    assert p["description"] == ["unclosed bold"]
    assert itch_page.parse("")["comments"] == []


def test_cache_roundtrip(tmp_path):
    paths.use_root(tmp_path)
    lib = library.Library()
    lib.games = [lib._prep(itch.game_from_key(_key(5, p_windows=True)))]
    lib.synced_at = "2026-11-14T10:00:00+02:00"
    lib.save_cache()
    lib2 = library.Library()
    assert lib2.games[0]["platforms"] == {"linux", "windows"}
    assert json.loads(paths.LIBRARY.read_text())["games"][0]["title"] == "Game 5"
