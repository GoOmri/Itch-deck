"""v0.9.4: SCRiTCH sets its own Steam art (steam_art.py). A hand-made binary shortcuts.vdf."""
import json
import struct

from itch_deck import paths, steam_art


def _vdf(entries):
    def s(k, v):
        return b"\x01" + k.encode() + b"\x00" + v.encode() + b"\x00"

    def i(k, v):
        return b"\x02" + k.encode() + b"\x00" + struct.pack("<i", v)
    out = b"\x00shortcuts\x00"
    for n, (appid, exe) in enumerate(entries):
        out += b"\x00" + str(n).encode() + b"\x00" + i("appid", appid) + s("AppName", "x") + \
            s("Exe", f'"{exe}"') + s("StartDir", '"/x"') + b"\x00tags\x00\x08" + b"\x08"
    return out + b"\x08\x08"


def _steam(tmp_path, entries, user="12345"):
    root = tmp_path / "Steam"
    cfg = root / "userdata" / user / "config"
    cfg.mkdir(parents=True)
    (cfg / "shortcuts.vdf").write_bytes(_vdf(entries))
    return root, cfg / "grid"


def _art(tmp_path):
    src = tmp_path / "art"
    src.mkdir()
    for n in ("tile.png", "wide-tile.png", "hero.png", "logo.png", "icon.png"):
        (src / n).write_bytes(n.encode())
    return src


def test_reads_binary_vdf_and_unsigned_appid(tmp_path):
    launcher = tmp_path / "Applications/itch-deck/itch-deck"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n")
    root, _ = _steam(tmp_path, [(-123456789, "/usr/bin/other"), (-2000000000, str(launcher))])
    found = steam_art.find_shortcuts([root], launcher)
    assert [a for _, a in found] == [(-2000000000) & 0xFFFFFFFF] == [2294967296]


def test_copies_art_once_never_overwrites(tmp_path):
    paths.use_root(tmp_path / "home")
    launcher = tmp_path / "Applications/scritch/scritch"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n")
    root, grid = _steam(tmp_path, [(-5, str(launcher))])
    appid = (-5) & 0xFFFFFFFF
    grid.mkdir(parents=True)
    (grid / f"{appid}_hero.jpg").write_bytes(b"mine")          # the player's own banner
    (grid / f"{appid}.json").write_text("{}")                   # logo position: not a picture
    written = steam_art.apply(launcher, roots=[root], src=_art(tmp_path))
    assert sorted(written) == sorted([f"{appid}p.png", f"{appid}.png", f"{appid}_logo.png"])
    assert (grid / f"{appid}p.png").read_bytes() == b"tile.png"
    assert not (grid / f"{appid}_hero.png").exists() and (grid / f"{appid}_hero.jpg").read_bytes() == b"mine"
    assert (launcher.parent / "scritch-icon.png").read_bytes() == b"icon.png"
    assert json.loads((paths.DATA / "steam_art.json").read_text()) == [f"12345/{appid}"]
    (grid / f"{appid}p.png").unlink()                           # removed on purpose: stays gone
    assert steam_art.apply(launcher, roots=[root], src=tmp_path / "art") == []
    assert not (grid / f"{appid}p.png").exists()


def test_other_shortcuts_and_broken_files_are_left_alone(tmp_path):
    paths.use_root(tmp_path / "home")
    launcher = tmp_path / "scritch"
    launcher.write_text("")
    root, grid = _steam(tmp_path, [(-7, "/home/deck/Games/other")])
    bad = root / "userdata" / "999" / "config"
    bad.mkdir(parents=True)
    (bad / "shortcuts.vdf").write_bytes(b"\x00shortcuts\x00\x09junk")
    assert steam_art.apply(launcher, roots=[root], src=_art(tmp_path)) == []
    assert not grid.exists()


def test_release_ships_the_art():
    assert {"tile.png", "wide-tile.png", "hero.png", "logo.png", "icon.png"} <= \
        {p.name for p in steam_art.art_dir().iterdir()}
