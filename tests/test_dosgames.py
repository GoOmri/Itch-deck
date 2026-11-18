"""Your own DOS games (v0.9.19): copy a folder (or a .zip) into <games folder>/dos, SCRiTCH lists it in the
DOS tab and runs it in DOSBox Staging. Nothing is downloaded; no file of the player's is ever deleted."""
import os
import time
import zipfile
from pathlib import Path

from itch_deck import dosbox, dosgames, paths
from itch_deck import installer as I


ALLEY = dosgames.game_id("Alley")


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
    assert g["id"] == dosgames.game_id("Eye_of_the_Beholder") and g["title"] == "Eye of the Beholder"
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
    info = inst.index[ALLEY]
    assert info["store"] == "dos" and info["dir"] == str(game) and info["exe"] == "ALLEY.EXE"
    assert inst.exe_path(ALLEY) == game / "ALLEY.EXE"
    assert [e["id"] for e in lib.dos] == [ALLEY]
    assert inst.set_exe(ALLEY, "OLD.EXE") and inst.index[ALLEY]["exe_chosen"]
    assert not (game / "install.json").exists()                   # nothing written into the player's folder
    inst.sync_dos()                                               # the chosen program survives a rescan
    assert inst.index[ALLEY]["exe"] == "OLD.EXE"
    assert inst.move_target(ALLEY, [("SD card", dos.parent), ("Internal storage", tmp_path)]) is None
    # remove from library: the entry goes, the files stay
    assert inst.uninstall(ALLEY) is True
    time.sleep(0.2)
    assert ALLEY not in inst.index and (game / "save1.dat").read_bytes() == b"my save"
    assert (game / "ALLEY.EXE").is_file()
    lib.hidden = {ALLEY}                                          # the app hides it (v0.9.26: Hidden games filter)
    assert inst.sync_dos() == 0 and ALLEY not in inst.index       # a refresh does not bring it back as installed
    assert [e["id"] for e in lib.dos] == [ALLEY]                  # but it stays in the library list, to be unhidden
    lib.hidden = set()                                            # "Show in SCRiTCH": the next scan lists it again
    assert inst.sync_dos() == 1 and ALLEY in inst.index


def test_scan_without_a_folder_does_nothing_until_asked(tmp_path):
    paths.use_root(tmp_path / "home")
    root = tmp_path / "games" / "scritch"
    lib = _Lib()
    inst = I.Installer(lib, lambda: root)
    assert inst.sync_dos() == 0 and not (root / "dos").exists()    # start-up scan never makes folders
    assert inst.sync_dos(create=True) == 0 and (root / "dos").is_dir()   # Refresh does


def test_ids_never_collide(tmp_path):
    root = tmp_path / "dos"
    names = ["A B", "a-b", "Doom", "\u0418\u0433\u0440\u0430", "\u30b2\u30fc\u30e0", "Doom 2", "doom_2"]
    if os.name != "nt":
        names.append("doom")                                      # (Windows folders ignore letter case)
    for n in names:
        _game(root, n)
    got = dosgames.scan(root)
    ids = [g["id"] for g in got]
    assert len(got) == len(names) and len(set(ids)) == len(names)     # every folder is its own game
    assert dosgames.game_id("Alley") == dosgames.game_id("Alley")        # and the id is stable


def test_a_zip_the_module_cannot_read_does_not_stop_the_scan(tmp_path, monkeypatch):
    root = tmp_path / "dos"
    root.mkdir()
    with zipfile.ZipFile(root / "Old.zip", "w") as z:
        z.writestr("OLD.EXE", "MZ")
    _game(root, "Fine")
    real = zipfile.ZipFile.extractall

    def boom(self, *a, **k):
        raise NotImplementedError("compression type 6 (implode)")
    monkeypatch.setattr(zipfile.ZipFile, "extractall", boom)
    got = dosgames.scan(root)                                    # must not raise
    assert [g["name"] for g in got] == ["Fine"]
    assert (root / "Old.zip").is_file() and not (root / "Old.unpacking").exists()
    monkeypatch.setattr(zipfile.ZipFile, "extractall", real)
    assert sorted(g["name"] for g in dosgames.scan(root)) == ["Fine", "Old"]    # fine again later


def test_a_zip_that_does_not_fit_is_left_alone(tmp_path, monkeypatch):
    import shutil
    root = tmp_path / "dos"
    root.mkdir()
    with zipfile.ZipFile(root / "Big.zip", "w") as z:
        z.writestr("BIG.EXE", "MZ" + "x" * 5000)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: shutil._ntuple_diskusage(10_000, 9_000, 100))
    assert dosgames.unpack_zips(root) == [] and (root / "Big.zip").is_file()


def test_a_removed_game_copied_again_as_a_zip_comes_back_as_a_new_folder(tmp_path):
    root = tmp_path / "dos"
    old = _game(root, "Doom", ["DOOM.EXE"], {"save.dat": b"mine"})
    with zipfile.ZipFile(root / "Doom.zip", "w") as z:
        z.writestr("DOOM.EXE", "MZ")
    # visible folder with the same name: the zip is skipped (already there)
    assert dosgames.unpack_zips(root, hide={}) == [] and (root / "Doom.zip").is_file()
    # that folder was removed from the library: the zip becomes "Doom (2)"; the old folder is untouched
    assert dosgames.unpack_zips(root, hide={"Doom": time.time()}) == ["Doom (2)"]
    assert (root / "Doom (2)" / "DOOM.EXE").is_file() and (old / "save.dat").read_bytes() == b"mine"


def test_folder_names_with_a_double_quote_are_skipped(tmp_path):
    root = tmp_path / "dos"
    if os.name != "nt":                                           # (Windows can't make such a folder)
        _game(root, 'Say "hi"')
    _game(root, "Fine")
    assert [g["name"] for g in dosgames.scan(root)] == ["Fine"]


def test_survey_does_not_look_deeper_than_two_folders(tmp_path):
    d = _game(tmp_path / "dos", "Deep", ["A.EXE", "B/C/D/E/TOO_DEEP.EXE"])
    progs, image, size = dosgames.survey(d)
    assert progs == ["A.EXE"] and image is None and size > 0


def test_the_dos_folder_name_is_reserved_and_never_deleted(tmp_path):
    inst, lib, dos = _inst(tmp_path)
    root = dos.parent
    _game(dos, "Alley", ["ALLEY.EXE"])
    g = {"id": "5", "title": "DOS"}                               # an itch game whose folder name would be "dos"
    assert inst._game_dir(root, g) != root / "dos"
    for reserved in ("dos", "_prefixes", "_moving", "_downloads"):
        assert not I.safe_to_delete(root / reserved, [root])
    assert I.safe_to_delete(root / "some-game", [root])


def test_a_scan_runs_in_a_thread_and_is_applied_afterwards(tmp_path):
    inst, lib, dos = _inst(tmp_path)
    _game(dos, "Alley", ["ALLEY.EXE"])
    result = inst.scan_dos()                                      # what the thread does: no shared state touched
    assert ALLEY not in inst.index and lib.dos is None
    assert inst.apply_dos(result) == 1 and ALLEY in inst.index and [e["id"] for e in lib.dos] == [ALLEY]
    assert inst.apply_dos(None) is None                           # SD card out: nothing changes
