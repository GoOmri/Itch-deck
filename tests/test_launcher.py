"""The release file = packaging/launcher.sh + the app folder (tar.gz). Unpacks once per version
into app/ (previous kept as app.old/), then starts app/scritch directly; a broken download
never removes a working app."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "packaging" / "pack.sh"


def _release(tmp, version, out):
    src = tmp / f"src{version}"
    src.mkdir()
    exe = src / "scritch"
    exe.write_text(f'#!/bin/sh\necho "v{version} launcher=$SCRITCH_LAUNCHER args=$*"\n')
    exe.chmod(0o755)
    (src / "_internal").mkdir()
    (src / "_internal" / "lib.so").write_bytes(os.urandom(50_000))
    subprocess.run(["sh", str(PACK), str(src), version, str(out)], check=True)
    return out


def _run(path, tmp):
    env = dict(os.environ, XDG_STATE_HOME=str(tmp / "state"))
    return subprocess.run([str(path), "--x"], capture_output=True, text=True, env=env)


def _log(tmp):
    return (tmp / "state/scritch/logs/launcher.log").read_text()


def test_unpack_once_update_and_broken_download(tmp_path):
    home = tmp_path / "Applications/itch-deck"
    home.mkdir(parents=True)
    tile = home / "itch-deck"
    _release(tmp_path, "1.0", tile)
    r = _run(tile, tmp_path)
    assert r.stdout.strip() == f"v1.0 launcher={tile} args=--x"
    assert (home / "app/VERSION").read_text().strip() == "1.0"
    assert (home / "app/_internal/lib.so").exists() and not (home / "app.new").exists()
    _run(tile, tmp_path)                                    # second start: no unpack
    assert _log(tmp_path).count("unpacked") == 1

    new = _release(tmp_path, "1.1", home / "itch-deck.new")  # what the updater does
    os.replace(tile, home / "itch-deck.old")
    os.replace(new, tile)
    assert _run(tile, tmp_path).stdout.startswith("v1.1")
    assert (home / "app.old/VERSION").read_text().strip() == "1.0"

    broken = _release(tmp_path, "1.2", tmp_path / "broken")
    data = broken.read_bytes()
    tile.write_bytes(data[: len(data) - 30_000])            # cut off mid-download
    r = _run(tile, tmp_path)
    assert r.returncode == 0 and r.stdout.startswith("v1.1")   # the working app still starts
    assert "couldn't unpack v1.2" in _log(tmp_path)
    assert (home / "app/VERSION").read_text().strip() == "1.1" and not (home / "app.new").exists()


def test_broken_first_install_exits(tmp_path):
    rel = _release(tmp_path, "1.0", tmp_path / "itch-deck")
    data = rel.read_bytes()
    rel.write_bytes(data[: len(data) - 30_000])
    assert _run(rel, tmp_path).returncode == 1


def test_child_env_drops_folder_build_libs(tmp_path, monkeypatch):
    from itch_deck import runner
    home = tmp_path / "Applications/itch-deck"
    (home / "app/_internal").mkdir(parents=True)
    (home / "app.old/_internal").mkdir(parents=True)
    monkeypatch.setenv("SCRITCH_LAUNCHER", str(home / "itch-deck"))
    env = {"LD_LIBRARY_PATH": f"{home}/app/_internal",
           "LD_LIBRARY_PATH_ORIG": f"{home}/app.old/_internal:/usr/lib/x"}
    assert runner.child_env(env)["LD_LIBRARY_PATH"] == "/usr/lib/x"


def test_launcher_logs_into_old_folder_until_the_app_moves_it(tmp_path):
    """v0.8.2: the launcher runs before the app renames itch-deck -> scritch. It must not create
    state/scritch first, or the app would find both folders and leave the old one behind."""
    (tmp_path / "state/itch-deck/logs").mkdir(parents=True)
    tile = _release(tmp_path, "1.0", tmp_path / "itch-deck")
    assert _run(tile, tmp_path).returncode == 0
    assert not (tmp_path / "state/scritch").exists()
    assert "unpacked v1.0" in (tmp_path / "state/itch-deck/logs/launcher.log").read_text()
