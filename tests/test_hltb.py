"""Time to beat (HowLongToBeat): matching, formatting, the client protocol (stubbed), library."""
import json

from itch_deck import hltb, library, net, paths
from itch_deck.ui.scenes.library import length_kind, visible


def row(name, main=0, done=0, alias=""):
    return {"game_id": 1, "game_name": name, "game_alias": alias, "comp_main": main, "comp_100": done}


def test_norm_and_strict_match():
    assert hltb.norm("Celeste™: Farewell!") == "celeste farewell"
    assert hltb.norm("Ori & the Blind Forest") == "ori and the blind forest"
    rows = [row("Celeste 2", 3600), row("Celeste", 8 * 3600, 40 * 3600)]
    assert hltb.pick("CELESTE", rows)["game_name"] == "Celeste"
    assert hltb.pick("Celest", rows) is None                       # close isn't enough
    assert hltb.pick("Cosmic Express", [row("Cosmic Express Deluxe", 3600)]) is None
    assert hltb.pick("CE", [row("Cosmic Express", 3600, alias="CE, Cosmo")])
    assert hltb.pick("Celeste", [row("Celeste")]) is None          # listed but no times


def test_format():
    assert hltb.fmt(0.3) == "~20 min" and hltb.fmt(0.01) == "~5 min"
    assert hltb.fmt(2.4) == "~2.5 h" and hltb.fmt(4.0) == "~4 h" and hltb.fmt(14.6) == "~15 h"
    assert hltb.summary({"main": 4.1, "done": 9.0}) == "Main story ~4 h  ·  Completionist ~9 h"
    assert hltb.summary({"main": None, "done": 2}) == "Completionist ~2 h"
    assert hltb.summary(None) == ""


def test_client_protocol(monkeypatch):
    calls = []

    def fake_get(url, timeout=20, headers=None, data=None, **kw):
        calls.append((url, headers, data))
        if url == hltb.BASE:
            return b'<script src="/_next/static/chunks/a.js"></script><script src="/_next/static/chunks/b.js">'
        if url.endswith("a.js"):
            return b"nothing here"
        if url.endswith("b.js"):
            return b'fetch("/api/seek/abc",{method:"POST",body:x})'
        if "/init" in url:
            return json.dumps({"token": "T", "hpKey": "k1", "hpVal": "v1"}).encode()
        assert url == hltb.BASE + "api/seek/abc" and data
        body = json.loads(data)
        assert body["k1"] == "v1" and body["searchTerms"] == ["circa", "infinity"]
        assert headers["x-auth-token"] == "T"
        return json.dumps({"data": [row("Circa Infinity", 2 * 3600, 5 * 3600)]}).encode()

    monkeypatch.setattr(net, "get", fake_get)
    c = hltb.Client()
    assert c.lookup("Circa Infinity") == {"main": 2.0, "done": 5.0, "id": 1}
    n = len(calls)
    assert c.lookup("Circa Infinity") and len(calls) == n + 1      # session reused: search only


def test_client_failure_is_offline(monkeypatch):
    def boom(*a, **k):
        raise net.Offline("down")
    monkeypatch.setattr(net, "get", boom)
    try:
        hltb.Client().lookup("x")
        assert False
    except net.Offline:
        pass


def test_length_filter_and_sort():
    gs = [{"title": t, "ttb": ttb, "platforms": {"linux"}} for t, ttb in
          (("A", {"main": 12}), ("B", None), ("C", {"main": 0.5}), ("D", {"main": None, "done": 5}))]
    assert [length_kind(g) for g in gs] == ["long", "", "short", "mid"]
    assert [g["title"] for g in visible(gs, sort="short")] == ["C", "D", "A", "B"]
    assert [g["title"] for g in visible(gs, length="mid")] == ["D"]


def test_library_caches_and_stops_when_down(tmp_path, monkeypatch):
    paths.use_root(tmp_path)
    lib = library.Library(None)
    g = {"id": "g1", "title": "Circa Infinity", "platforms": {"windows"}}
    lib.games = [g]
    monkeypatch.setattr(hltb.Client, "lookup", lambda self, t: {"main": 2.0, "done": 5.0, "id": 9})
    lib._fetch_hltb(g)
    assert g["ttb"] == {"main": 2.0, "done": 5.0}
    assert library.Library(None)._ttb("g1") == {"main": 2.0, "done": 5.0}   # survives restart
    assert lib._hltb_fresh("g1")
    lib.queue_hltb()
    assert lib.jobs["hltb"] == [0, 0]                            # fresh: not asked again
    g2 = {"id": "g2", "title": "Nope", "platforms": {"linux"}}
    lib.games.append(g2)
    monkeypatch.setattr(hltb.Client, "lookup", lambda self, t: None)
    lib._fetch_hltb(g2)
    assert g2["ttb"] is None and lib._hltb_fresh("g2")           # "not on HLTB" is remembered too
    lib._hltb_down = True
    lib.queue_hltb()
    assert lib.jobs["hltb"] == [0, 0]
