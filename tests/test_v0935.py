"""v0.9.35: Sort & filter > Biggest first. Sizes come from the install record (no new source)."""
import os

from itch_deck import dosgames
from itch_deck.ui.scenes.library import SORTS, visible


def _g(gid, title, state=None, mb=0, **kw):
    return dict(id=gid, title=title, state=state, size_mb=mb, platforms={"linux"}, **kw)


def _ids(games, **kw):
    return [g["id"] for g in visible(games, sort="big", **kw)]


def test_menu_text():
    assert dict(SORTS)["big"] == "Biggest first"


def test_sized_first_biggest_first_then_rest_az():
    games = [_g("n2", "Zed"), _g("a", "Small", "installed", 50), _g("n1", "Alpha"),
             _g("b", "Huge", "installed", 5000), _g("c", "Mid", "installed", 700),
             _g("d", "Away", "missing", 900),
             _g("dl", "Downloading", "downloading", 3000)]     # size of a download, not on the Deck yet
    assert _ids(games) == ["b", "d", "c", "a", "n1", "dl", "n2"]


def test_ties_a_to_z_and_installed_with_zero_size_is_unknown():
    games = [_g("x", "beta", "installed", 100), _g("y", "Alpha", "installed", 100),
             _g("z", "Zero", "installed", 0), _g("w", "Able", None)]
    assert _ids(games) == ["y", "x", "w", "z"]


def test_works_on_installed_tab_and_bad_size_is_unknown():
    games = [_g("a", "A", "installed", 10), _g("b", "B", "installed", 20),
             _g("c", "C", None), _g("e", "E", "installed", None)]
    assert _ids(games, filt="installed") == ["b", "a", "e"]
    games[0]["size_mb"] = "junk"
    assert _ids(games, filt="installed") == ["b", "a", "e"]


def test_dos_folder_size_counts_files_skips_symlinks_and_survives_missing(tmp_path):
    game, outside = tmp_path / "Game", tmp_path / "outside"
    game.mkdir()
    outside.mkdir()
    (game / "GAME.EXE").write_bytes(b"x" * 1000)
    (game / "DATA").mkdir()
    (game / "DATA" / "a.dat").write_bytes(b"y" * 500)
    (outside / "big.bin").write_bytes(b"z" * 100_000)
    try:
        os.symlink(outside, game / "link", target_is_directory=True)
        os.symlink(outside / "big.bin", game / "bigfile")
    except (OSError, NotImplementedError):
        pass                                           # no symlinks on this machine: skip that part
    assert dosgames.survey(game)[2] == 1500
    assert dosgames.survey(tmp_path / "nope")[2] == 0   # missing card / folder: no crash


def test_scan_records_size_in_bytes_for_own_dos_games(tmp_path):
    g = tmp_path / "Doom"
    g.mkdir()
    (g / "DOOM.EXE").write_bytes(b"x" * 2_000_000)
    got = dosgames.scan(tmp_path, hide={})
    assert [e["size"] for e in got] == [2_000_000]     # installer.apply_dos keeps it in the install record
