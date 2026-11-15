"""v0.8.2: the folders itch-deck -> scritch. Renamed (not copied) at start, old name left as a
link so a rolled-back older version still finds everything; a failed rename keeps the old one."""
import os
from pathlib import Path

from itch_deck import config, paths, updater


def _bases(tmp):
    return {k: tmp / k.lower() for k in ("CONFIG", "DATA", "LOGS")}


def test_moves_each_folder_and_leaves_a_link(tmp_path):
    b = _bases(tmp_path)
    (b["CONFIG"] / "itch-deck").mkdir(parents=True)
    (b["CONFIG"] / "itch-deck/config.json").write_text('{"api_key": "k"}')
    (b["DATA"] / "itch-deck/covers").mkdir(parents=True)
    (b["DATA"] / "itch-deck/covers/1.jpg").write_bytes(b"x")
    (b["LOGS"] / "itch-deck/logs").mkdir(parents=True)
    notes = paths.migrate(b)
    assert len([n for n in notes if "moved" in n]) == 3
    for base in b.values():
        old, new = base / "itch-deck", base / "scritch"
        assert new.is_dir() and not new.is_symlink()
        assert old.is_symlink() and os.readlink(old) == "scritch"
    assert (b["CONFIG"] / "scritch/config.json").read_text() == '{"api_key": "k"}'
    assert (b["DATA"] / "itch-deck/covers/1.jpg").read_bytes() == b"x"     # old path still reads
    assert paths.migrate(b) == []                                            # second start: nothing


def test_fresh_install_and_both_present(tmp_path):
    b = _bases(tmp_path)
    assert paths.migrate(b) == []                       # nothing there: nothing made
    assert not any(p.exists() for p in b.values())
    (b["DATA"] / "itch-deck").mkdir(parents=True)
    (b["DATA"] / "scritch").mkdir(parents=True)
    notes = paths.migrate(b)
    assert "both" in notes[0] and (b["DATA"] / "itch-deck").is_dir()   # never merged or deleted


def test_failed_rename_keeps_using_the_old_folder(tmp_path, monkeypatch):
    b = _bases(tmp_path)
    (b["DATA"] / "itch-deck").mkdir(parents=True)
    monkeypatch.setattr(paths, "_BASES", b)
    for k in ("CONFIG", "DATA", "LOGS", "CONFIG_FILE", "LIBRARY", "COVERS", "PAGES", "SHOTS",
              "INSTALLS", "QUEUE", "PLAYED", "HLTB", "BUILDS", "UMU"):
        monkeypatch.setattr(paths, k, getattr(paths, k))      # restored after the test

    config_before = paths.CONFIG

    def no(*a):
        raise OSError("read-only")
    monkeypatch.setattr(os, "rename", no)
    notes = paths.migrate()
    assert any("couldn't move" in n for n in notes)
    assert paths.DATA == b["DATA"] / "itch-deck" and paths.COVERS == b["DATA"] / "itch-deck/covers"
    assert paths.CONFIG == config_before                     # nothing old there: untouched


def test_games_folder_keeps_itch_but_new_users_get_scritch(tmp_path):
    assert config.games_dir(tmp_path) == tmp_path / "scritch"
    (tmp_path / "itch").mkdir()
    assert config.games_dir(tmp_path) == tmp_path / "itch"


def test_updater_takes_either_release_name(monkeypatch):
    u = updater.Updater("0.8.1")
    u.state = "idle"
    rel = {"tag_name": "v0.8.2", "assets": [
        {"name": "itch-deck", "browser_download_url": "old"},
        {"name": "scritch", "browser_download_url": "new"}]}
    monkeypatch.setattr(updater.net, "get_json", lambda *a, **k: rel)
    u._check(quiet=True)
    assert (u.state, u.url) == ("available", "new")
    rel["assets"] = rel["assets"][:1]                 # a release from before the rename
    u.state = "idle"
    u._check(quiet=True)
    assert (u.state, u.url) == ("available", "old")
