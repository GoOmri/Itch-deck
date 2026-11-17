"""Your own DOS games (v0.9.19): copy a folder (or a .zip) into <games folder>/dos, SCRiTCH lists it in the
DOS tab and runs it in DOSBox Staging. Nothing is downloaded; no file of the player's is ever deleted."""
import os
import time
import zipfile
from pathlib import Path

from itch_deck import dosbox, dosgames, paths
from itch_deck import installer as I


def _game(root, name, files=("GAME.EXE",), extra=None):
    d = root / name
    d.mkdir(parents=True)
    for f in files:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_bytes(b"MZ" + b"x" * 100)
    for f, data in (extra or {}).items():
        (d / f).write_bytes(data)
    return d


def test_scan_lists_games_and_skips_helpers_and_empty_folders(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "dos"
    _game(root, "Eye_of_the_Beholder", ["EOB.EXE", "SETUP.EXE", "SOUND/SETSOUND.EXE"],
          {"cover.png": b"\x89PNG", "GAME.CUE": b"x"})
    _game(root, "Notes", [], {"readme.txt": b"hi"})           # no program: skipped
    _game(root, "_zips", ["X.EXE"])                           # our own folder: skipped
    _game(root, ".hidden", ["X.EXE"])
    got = dosgames.scan(root)
    assert [g["name"] for g in got] == ["Eye_of_the_Beholder"]
    g = got[0]
    assert g["id"] == "dos-eye-of-the-beholder" and g["title"] == "Eye of the Beholder"
    assert g["exe"] == "EOB.EXE" and g["programs"] == ["EOB.EXE"]        # setup + sound config left out
    assert g["cover"].name == "cover.png" and g["image"] == "GAME.CUE"


def test_program_choice():
    progs = ["A.EXE", "DUNE.BAT", "SUB/DUNE.EXE"]
    assert dosgames.pick_program("Dune", progs) == "DUNE.BAT"                    # name match wins (shallowest first)
    assert dosgames.pick_program("Dune", ["Z.EXE", "DUNE.EXE"]) == "DUNE.EXE"    # name like the folder
    assert dosgames.pick_program("Game", ["Z.EXE", "RUN.BAT"]) == "RUN.BAT"      # the one .bat
    assert dosgames.pick_program("Game", ["A.EXE", "B.EXE"], saved="B.EXE") == "B.EXE"   # saved choice
    assert dosgames.pick_program("Game", ["A.EXE", "B.EXE"], saved="GONE.EXE") == "A.EXE"
    assert dosgames.pick_program("Game", []) is None


def test_zip_is_unpacked_and_kept(tmp_path):
    root = tmp_path / "dos"
    root.mkdir()
    with zipfile.ZipFile(root / "Doom.zip", "w") as z:
        z.writestr("Doom/DOOM.EXE", "MZ")                     # one top folder: no extra level
        z.writestr("Doom/DATA/x.wad", "w")
    with zipfile.ZipFile(root / "Flat.zip", "w") as z:
        z.writestr("FLAT.EXE", "MZ")
    got = dosgames.scan(root)
    assert sorted(g["name"] for g in got) == ["Doom", "Flat"]
    assert (root / "Doom" / "DOOM.EXE").is_file() and (root / "Flat" / "FLAT.EXE").is_file()
    assert (root / "_zips" / "Doom.zip").is_file() and not (root / "Doom.zip").exists()   # kept


def test_unsafe_zip_is_refused(tmp_path):
    root = tmp_path / "dos"
    root.mkdir()
    with zipfile.ZipFile(root / "Evil.zip", "w") as z:
        z.writestr("../outside.txt", "x")
        z.writestr("EVIL.EXE", "MZ")
    assert dosgames.unpack_zips(root) == []
    assert not (tmp_path / "outside.txt").exists() and (root / "Evil.zip").is_file()


def test_launch_own_mounts_the_folder_and_runs_the_program(tmp_path):
    folder = tmp_path / "dos" / "Eye"
    info = {"dir": str(folder), "exe": "EOB/EOB.EXE", "store": "dos", "image": "GAME.CUE"}
    exe, args, cwd = dosbox.launch_own(info, ["/usr/bin/flatpak", "run", "io.github.dosbox-staging"])
    assert exe == Path("/usr/bin/flatpak") and cwd == str(folder)
    assert args[:4] == ["run", f"--filesystem={folder}", f"--cwd={folder}", "io.github.dosbox-staging"]
    cmds = [args[i + 1] for i, a in enumerate(args) if a == "-c"]
    assert cmds[0] == f'mount c "{folder}"' and cmds[-1] == "exit"
    assert cmds[1].startswith("imgmount d ") and "c:" in cmds
    assert cmds[-3:] == ["cd EOB", "EOB.EXE", "exit"]
    assert dosbox.is_own_dos(info) and not dosbox.is_own_dos({"store": "gog"})


class _Lib:
    def __init__(self):
        self.games, self.installs, self.live, self.epic, self.dos = [], {}, {}, None, None

    def apply_installs(self):
        pass

    def set_dos_games(self, entries):
        self.dos = entries

    def by_id(self, gid):
        return None


def _inst(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "games" / "scritch"
    (root / "dos").mkdir(parents=True)
    lib = _Lib()
    return I.Installer(lib, lambda: root), lib, root / "dos"


def test_sync_adds_games_and_remove_keeps_every_file(tmp_path):
    inst, lib, dos = _inst(tmp_path)
    game = _game(dos, "Alley", ["ALLEY.EXE", "OLD.EXE"], {"save1.dat": b"my save"})
    assert inst.sync_dos() == 1
    info = inst.index["dos-alley"]
    assert info["store"] == "dos" and info["dir"] == str(game) and info["exe"] == "ALLEY.EXE"
    assert inst.exe_path("dos-alley") == game / "ALLEY.EXE"
    assert [e["id"] for e in lib.dos] == ["dos-alley"]
    assert inst.set_exe("dos-alley", "OLD.EXE") and inst.index["dos-alley"]["exe_chosen"]
    assert not (game / "install.json").exists()                   # nothing written into the player's folder
    inst.sync_dos()                                               # the chosen program survives a rescan
    assert inst.index["dos-alley"]["exe"] == "OLD.EXE"
    assert inst.move_target("dos-alley", [("SD card", dos.parent), ("Internal storage", tmp_path)]) is None
    # remove from library: the entry goes, the files stay
    assert inst.uninstall("dos-alley") is True
    time.sleep(0.2)
    assert "dos-alley" not in inst.index and (game / "save1.dat").read_bytes() == b"my save"
    assert (game / "ALLEY.EXE").is_file()
    assert inst.sync_dos() == 0                                   # hidden: it does not come straight back
    later = time.time() + 5                                       # copied again (folder changed): back
    (game / "new.exe").write_bytes(b"MZ")
    os.utime(game, (later, later))
    assert inst.sync_dos() == 1 and "dos-alley" in inst.index


def test_scan_without_a_folder_does_nothing_until_asked(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "games" / "scritch"
    lib = _Lib()
    inst = I.Installer(lib, lambda: root)
    assert inst.sync_dos() == 0 and not (root / "dos").exists()    # start-up scan never makes folders
    assert inst.sync_dos(create=True) == 0 and (root / "dos").is_dir()   # Refresh does
