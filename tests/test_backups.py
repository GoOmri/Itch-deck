"""Save backups (16 Nov): automatic after play, ~/Documents/SCRiTCH saves/<Game>/, last 5,
only when the saves changed; restore backs up the current saves first."""
import os
import time
import zipfile

from itch_deck import backups, paths


def _w(p, text, age=0):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    if age:
        t = time.time() - age
        os.utime(p, (t, t))


def _win(tmp_path):
    prefix = tmp_path / "games/_prefixes/moss"
    user = prefix / "drive_c/users/steamuser"
    _w(user / "AppData/LocalLow/Studio/Moss/save1.dat", "slot1")
    _w(user / "AppData/LocalLow/Studio/Moss/Player.log", "log")          # noise
    _w(user / "AppData/Local/Temp/junk.bin", "x")                        # cache
    _w(user / "AppData/Local/Studio/ShaderCache/a.bin", "x")             # cache
    _w(user / "Documents/My Games/Moss/options.ini", "vol=5")
    return {"platform": "windows", "prefix": str(prefix), "dir": str(tmp_path / "games/moss")}, user


def test_windows_backup_keep_and_restore(tmp_path):
    paths.use_root(tmp_path)
    info, user = _win(tmp_path)
    z = backups.backup("7", "Moss & Rivets", info)
    assert z and z.parent == tmp_path / "Documents/SCRiTCH saves/Moss & Rivets"
    names = set(zipfile.ZipFile(z).namelist())
    assert names == {"win/AppData/LocalLow/Studio/Moss/save1.dat",
                     "win/Documents/My Games/Moss/options.ini"}
    assert backups.backup("7", "Moss & Rivets", info) is None          # nothing changed
    _w(user / "AppData/LocalLow/Studio/Moss/Player.log", "new log")      # noise only
    assert backups.backup("7", "Moss & Rivets", info) is None
    os.replace(z, z.parent / "2026-11-01 10-00-00.zip")
    for i in range(7):                                                   # keep the last 5
        _w(user / "AppData/LocalLow/Studio/Moss/save1.dat", "slot" + "x" * (i + 2))
        os.replace(backups.backup("7", "Moss & Rivets", info),
                   z.parent / f"2026-11-1{i} 10-00-00.zip")
    backups.prune(z.parent)
    assert [b.name[:10] for b in backups.listing("7")] == \
        ["2026-11-16", "2026-11-15", "2026-11-14", "2026-11-13", "2026-11-12"]
    old = backups.listing("7")[-1]
    want = zipfile.ZipFile(old).read("win/AppData/LocalLow/Studio/Moss/save1.dat").decode()
    _w(user / "AppData/LocalLow/Studio/Moss/save1.dat", "current progress")
    backups.restore("7", "Moss & Rivets", info, old)
    assert (user / "AppData/LocalLow/Studio/Moss/save1.dat").read_text() == want
    assert old in backups.listing("7") and len(backups.listing("7")) == backups.KEEP  # kept
    before = [b for b in backups.listing("7") if "before restore" in b.name]
    assert before and zipfile.ZipFile(before[0]).read(
        "win/AppData/LocalLow/Studio/Moss/save1.dat") == b"current progress"
    assert backups.backup("7", "Moss & Rivets", info) is None          # restored = no new backup
    assert backups.label(before[0])[1] == "Before restore"


def test_linux_learns_save_folders(tmp_path):
    paths.use_root(tmp_path)
    home = tmp_path
    _w(home / ".local/share/godot/app_userdata/Grave Gardener/old.dat", "x", age=3600)
    _w(home / ".config/OtherGame/save.dat", "x", age=3600)            # not touched while playing
    since = time.time() - 5
    _w(home / ".local/share/godot/app_userdata/Grave Gardener/slot.save", "garden")
    _w(home / ".local/share/Steam/config/x.vdf", "steam")              # not a game
    _w(home / ".config/kdeglobals", "kde")                             # loose file
    _w(home / ".config/unity3d/Bedtime/Figment/prefs", "p")
    _w(home / ".config/unity3d/Bedtime/Figment/Player.log", "noise")
    new = backups.learn("5", "Grave Gardener", since)
    assert new == [".config/unity3d/Bedtime/Figment",
                   ".local/share/godot/app_userdata/Grave Gardener"]
    assert backups.learn("5", "Grave Gardener", since) == []           # already known
    info = {"platform": "linux", "dir": str(tmp_path / "games/grave")}
    z = backups.backup("5", "Grave Gardener", info)
    names = set(zipfile.ZipFile(z).namelist())
    assert "home/.local/share/godot/app_userdata/Grave Gardener/old.dat" in names
    assert "home/.config/unity3d/Bedtime/Figment/prefs" in names
    assert not any("Player.log" in n or "Steam" in n or "OtherGame" in n for n in names)
    (home / ".local/share/godot/app_userdata/Grave Gardener/slot.save").write_text("lost")
    backups.restore("5", "Grave Gardener", info, z)
    assert (home / ".local/share/godot/app_userdata/Grave Gardener/slot.save").read_text() == "garden"


def test_nothing_to_save_and_same_title(tmp_path):
    paths.use_root(tmp_path)
    assert backups.backup("9", "Quiet Quarry", {"platform": "linux"}) is None
    assert backups.listing("9") == []
    info, _ = _win(tmp_path)
    a = backups.backup("7", "Twin", info)
    b = backups.backup("8", "Twin", info)
    assert a.parent.name == "Twin" and b.parent.name == "Twin (8)"
    assert backups.folder("8", "Twin") == b.parent


def test_restore_ignores_unsafe_paths(tmp_path):
    paths.use_root(tmp_path)
    info, user = _win(tmp_path)
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("win/../../../../escaped.txt", "x")
        zf.writestr("win/Documents/ok.txt", "ok")
    backups.restore("7", "Moss", info, z)
    assert (user / "Documents/ok.txt").read_text() == "ok"
    assert not any(p.name == "escaped.txt" for p in tmp_path.rglob("escaped.txt"))
