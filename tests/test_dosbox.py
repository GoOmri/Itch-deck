"""v0.9.7: GOG's DOS games run with a native DOSBox Staging (dosbox.py). A stand-in flatpak."""
import os

from itch_deck import dosbox

FAKE_FLATPAK = """#!/bin/sh
echo "flatpak $*" >> "$LOGF"
case "$1" in
  info) [ -f "$MARK" ] && exit 0 || exit 1 ;;
  install) [ -n "$SYSTEM_FAILS" ] && [ "$2" != "--user" ] && exit 1; touch "$MARK"; exit 0 ;;
  remote-add) exit 0 ;;
esac
exit 0
"""


def _fake(tmp_path, monkeypatch, system_fails=False):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "flatpak").write_text(FAKE_FLATPAK)
    (b / "flatpak").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:/usr/bin:/bin")
    monkeypatch.setenv("MARK", str(tmp_path / "installed"))
    monkeypatch.setenv("LOGF", str(tmp_path / "calls"))
    if system_fails:
        monkeypatch.setenv("SYSTEM_FAILS", "1")
    return b / "flatpak"


def test_installs_once_then_found(tmp_path, monkeypatch):
    fp = _fake(tmp_path, monkeypatch)
    assert dosbox.native() is None
    assert dosbox.ensure() == [str(fp), "run", dosbox.APP]
    assert dosbox.ensure() == [str(fp), "run", dosbox.APP]          # no second install
    assert (tmp_path / "calls").read_text().count(" install ") == 1


def test_falls_back_to_a_user_install(tmp_path, monkeypatch):
    _fake(tmp_path, monkeypatch, system_fails=True)
    assert dosbox.ensure()
    calls = (tmp_path / "calls").read_text()
    assert "remote-add --user --if-not-exists flathub" in calls and "install --user -y" in calls


def test_launch_uses_game_settings_with_linux_paths(tmp_path):
    files = tmp_path / "eob" / "files"
    (files / "DOSBOX").mkdir(parents=True)
    (files / "DOSBOX" / "DOSBox.exe").write_text("MZ")
    (files / "dosbox_eob1.conf").write_text("[sdl]\nfullscreen=true\n")
    (files / "dosbox_eob1_single.conf").write_text(
        '[autoexec]\ncls\nmount c ".."\nmount C "..\\cloud_saves" -t overlay\nc:\nstart.exe\nexit\n')
    info = {"store": "gog", "platform": "windows", "dir": str(tmp_path / "eob"),
            "exe": "DOSBOX/DOSBox.exe", "cwd": "DOSBOX",
            "args": ["-conf", "../dosbox_eob1.conf", "-conf", "../dosbox_eob1_single.conf",
                     "-noconsole", "-c", "exit"]}
    assert dosbox.is_dosbox_game(info)
    exe, args, cwd = dosbox.launch(info, ["/usr/bin/flatpak", "run", dosbox.APP])
    assert str(exe) == "/usr/bin/flatpak" and cwd == str(files / "DOSBOX")
    assert args[:3] == ["run", f"--filesystem={files}", f"--cwd={files / 'DOSBOX'}"]
    assert args[3] == dosbox.APP and "-noconsole" not in args and args[-2:] == ["-c", "exit"]
    single = files / "scritch-dosbox_eob1_single.conf"
    assert str(single) in args and 'mount C "../cloud_saves" -t overlay' in single.read_text()
    assert "\\" in (files / "dosbox_eob1_single.conf").read_text()    # original untouched
    assert not dosbox.is_dosbox_game(dict(info, exe="Bin/Game.exe"))


def test_frozen_helper_processes_dont_reach_the_app():
    """run.py calls multiprocessing.freeze_support() before anything (v0.9.6 logged
    'unrecognized arguments: -B -S -I -c from multiprocessing.resource_tracker ...')."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "run.py")).read()
    assert src.index("freeze_support()") < src.index("--gogdl") < src.index("from itch_deck.app")
