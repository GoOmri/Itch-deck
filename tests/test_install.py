"""Offline install tests: build choice, extract (zip exec bits, tar, bare file), exe detection,
the full queue against a local HTTP server (Range resume, cancel, no space), uninstall."""
import http.server
import io
import os
import stat
import tarfile
import threading
import time
import zipfile

import pytest

from itch_deck import installer, library, net, paths
from itch_deck.stores import itch

ELF64 = b"\x7fELF\x02\x01\x01" + b"\0" * 9 + b"\x02\x00\x3e\x00" + b"\0" * 100
ELF32 = b"\x7fELF\x01\x01\x01" + b"\0" * 9 + b"\x02\x00\x03\x00" + b"\0" * 100


@pytest.fixture(autouse=True)
def no_ge_download(monkeypatch):
    """Never fetch the real GE-Proton (0.5 GB) in tests: act like the download failed."""
    from itch_deck import proton

    def offline(*a, **k):
        raise proton.ProtonError("Couldn't download GE-Proton (needed once for Windows games). "
                                 "Retry when you're online.")
    monkeypatch.setattr(proton, "fetch_ge", offline)


def _up(i, fn, **kw):
    u = {"id": i, "filename": fn, "type": "default", "p_linux": True, "updated_at": "2024-01-01"}
    u.update(kw)
    return u


def test_pick_build_rules():
    ups = itch.parse_uploads({"uploads": [
        _up(1, "ost.zip", type="soundtrack"),
        _up(2, "game-demo-linux.zip", traits=["p_linux", "demo"]),
        _up(3, "game-linux32.tar.gz"),
        _up(4, "game-linux64.tar.gz"),
        _up(5, "game-win.zip", p_linux=False, p_windows=True),
        _up(6, "link", storage="external"),
    ]})
    best, others = itch.pick_build(ups, "linux")
    assert best["id"] == 4 and [o["id"] for o in others] == [3, 2]
    assert itch.pick_build(ups, "windows")[0]["id"] == 5
    assert itch.parse_uploads({"uploads": {}}) == [] and itch.parse_uploads({}) == []


def _zip(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, data, mode in files:
            zi = zipfile.ZipInfo(name)
            zi.external_attr = (stat.S_IFREG | mode) << 16
            z.writestr(zi, data)
    return b.getvalue()


def test_extract_zip_keeps_exec_and_find_exe(tmp_path):
    a = tmp_path / "g.zip"
    a.write_bytes(_zip([("Quarry/Quarry.x86_64", ELF64, 0o755), ("Quarry/UnityPlayer.so", ELF64, 0o644),
                        ("Quarry/Quarry_Data/x.dat", b"x", 0o644),
                        ("Quarry/UnityCrashHandler64", ELF64, 0o755),
                        ("Quarry/tools/helper", ELF32, 0o644)]))
    installer.extract(a, tmp_path / "out")
    exe = tmp_path / "out/Quarry/Quarry.x86_64"
    assert os.access(exe, os.X_OK)
    best, alts = installer.find_exe(tmp_path / "out", {"id": "1", "title": "Quiet Quarry",
                                                      "url": "https://d.itch.io/quarry"})
    assert best == "Quarry/Quarry.x86_64" and alts == ["Quarry/tools/helper"]
    assert os.access(tmp_path / "out/Quarry/tools/helper", os.X_OK)   # exec bit restored


def test_extract_rejects_zip_slip(tmp_path):
    a = tmp_path / "bad.zip"
    a.write_bytes(_zip([("../evil.sh", b"#!/bin/sh\n", 0o755)]))
    with pytest.raises(installer.InstallError):
        installer.extract(a, tmp_path / "out")
    assert not (tmp_path / "evil.sh").exists()


def test_extract_tar_and_bare_file(tmp_path):
    a = tmp_path / "g.tar.gz"
    with tarfile.open(a, "w:gz") as tf:
        ti = tarfile.TarInfo("game/run.sh")
        data = b"#!/bin/sh\necho hi\n"
        ti.size, ti.mode = len(data), 0o755
        tf.addfile(ti, io.BytesIO(data))
    installer.extract(a, tmp_path / "t")
    assert installer.find_exe(tmp_path / "t", {"id": "1", "title": "X"})[0] == "game/run.sh"
    b = tmp_path / "7-42-Game.AppImage"
    b.write_bytes(ELF64)
    installer.extract(b, tmp_path / "b")
    assert installer.find_exe(tmp_path / "b", {"id": "7", "title": "Game"})[0] == "Game.AppImage"
    c = tmp_path / "x.rar"
    c.write_bytes(b"Rar!")
    with pytest.raises(installer.InstallError, match="rar"):
        installer.extract(c, tmp_path / "c")


# --- full install against a local server ------------------------------------------------------
class _Handler(http.server.BaseHTTPRequestHandler):
    files, slow = {}, False

    def do_GET(self):  # noqa: N802
        data = self.files.get(self.path)
        if data is None:
            self.send_error(404)
            return
        start = 0
        rng = self.headers.get("Range")
        if rng:
            start = int(rng.split("=")[1].split("-")[0])
            self.send_response(206)
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(len(data) - start))
        self.end_headers()
        for i in range(start, len(data), 4096):
            self.wfile.write(data[i:i + 4096])
            if self.slow:
                time.sleep(0.01)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


class FakeStore:
    key = "k"

    def __init__(self, base, uploads):
        self.base, self.uploads = base, uploads

    def list_builds(self, g):
        return itch.parse_uploads({"uploads": self.uploads})

    def download_url(self, g, b):
        return f"{self.base}/{b['filename']}"


def _setup(tmp_path, server, uploads):
    paths.use_root(tmp_path)
    lib = library.Library(FakeStore(server, uploads))
    lib.games = [lib._prep({"id": "5", "title": "Quiet Quarry", "url": "https://d.itch.io/quiet-quarry",
                            "platforms": ["linux"]})]
    inst = installer.Installer(lib, lambda: tmp_path / "games")
    return lib, inst


def _wait(inst, secs=10):
    end = time.time() + secs
    while (inst.queue or inst.current) and time.time() < end:
        time.sleep(0.02)


def test_install_resume_uninstall(tmp_path, server):
    data = _zip([("quarry/quarry", ELF64 + os.urandom(300_000), 0o755)])
    _Handler.files, _Handler.slow = {"/q.zip": data}, False
    lib, inst = _setup(tmp_path, server, [_up(9, "q.zip", size=len(data))])
    # half a download left behind by a quit: the Range request continues it
    part = tmp_path / "games/_downloads/5-9-q.zip.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(data[:100_000])
    assert inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("5")
    assert g["state"] == "installed", g.get("fail_reason")
    exe = inst.exe_path("5")
    assert exe == tmp_path / "games/quiet-quarry/files/quarry/quarry" and os.access(exe, os.X_OK)
    assert (tmp_path / "games/quiet-quarry/install.json").exists()
    assert not list((tmp_path / "games/_downloads").iterdir())
    assert inst.events[-1][0] == "done"
    # the index survives a restart and a library sync
    lib2 = library.Library(None)
    lib2.games = [lib2._prep({"id": "5", "title": "Quiet Quarry", "platforms": ["linux"]})]
    installer.Installer(lib2, lambda: tmp_path / "games")
    assert lib2.by_id("5")["state"] == "installed"
    inst.uninstall("5")
    assert g["state"] is None and "5" not in inst.index
    time.sleep(0.3)
    assert not (tmp_path / "games/quiet-quarry").exists()


def test_cancel_and_failures(tmp_path, server):
    big = _zip([("a/a", ELF64 + os.urandom(2_000_000), 0o755)])
    _Handler.files, _Handler.slow = {"/big.zip": big}, True
    lib, inst = _setup(tmp_path, server, [_up(9, "big.zip", size=len(big))])
    inst.enqueue(lib.games[0])
    end = time.time() + 5
    while lib.games[0].get("progress", 0) == 0 and time.time() < end:
        time.sleep(0.02)
    inst.cancel("5")
    _wait(inst)
    assert lib.games[0]["state"] is None
    assert not list((tmp_path / "games/_downloads").glob("5-*"))
    # the game page gets a few plain words (words.short); the full reason is only in the log
    _Handler.slow = False
    inst.lib.store.uploads = [_up(9, "w.zip", p_linux=False, p_windows=True)]
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert lib.games[0]["state"] == "failed" and lib.games[0]["fail_reason"] == "No internet"  # GE fetch
    inst.lib.store.uploads = [_up(9, "big.zip", size=10 ** 15)]
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert "Not enough space" in lib.games[0]["fail_reason"]
    # offline mid-way: failed with a retry message
    inst.lib.store.uploads = [_up(9, "missing.zip", size=10)]
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert lib.games[0]["fail_reason"] == "No internet"


def test_runner_env_and_crash():
    from itch_deck import runner
    assert runner.crashed(1, 2) and runner.crashed(None, 0) and not runner.crashed(0, 600)
    assert not runner.crashed(1, 600)


def test_child_env_drops_bundle_libs(monkeypatch):
    from itch_deck import runner
    env = {"LD_LIBRARY_PATH": "/tmp/_MEInew", "LD_LIBRARY_PATH_ORIG": "/tmp/_MEIold:/usr/lib/x",
           "LD_PRELOAD": "/s/gameoverlayrenderer.so", "HOME": "/h"}
    out = runner.child_env(env)
    assert out["LD_LIBRARY_PATH"] == "/usr/lib/x" and "LD_LIBRARY_PATH_ORIG" not in out
    assert out["LD_PRELOAD"] == "/s/gameoverlayrenderer.so"     # Steam overlay stays
    assert "LD_LIBRARY_PATH" not in runner.child_env({"LD_LIBRARY_PATH": "/tmp/_MEIx"})


def test_unity_gets_screen_size(tmp_path):
    from itch_deck import runner
    exe = tmp_path / "Figment.x86_64"
    exe.write_bytes(ELF64)
    exe.chmod(0o755)
    assert runner.command(exe, (1280, 800)) == [str(exe)]
    (tmp_path / "Figment_Data").mkdir()
    assert runner.command(exe, (1280, 800))[1:] == ["-screen-fullscreen", "1", "-screen-width",
                                                    "1280", "-screen-height", "800"]


# --- M4: Windows builds via umu + GE-Proton -------------------------------------------------
def _fake_proton(tmp_path):
    """A GE-Proton folder + a umu-run in place, so installs don't hit the network."""
    d = paths.STEAM_TOOLS / "GE-Proton9-20"
    d.mkdir(parents=True)
    (d / "proton").write_text("#!/bin/sh\n")
    paths.UMU.parent.mkdir(parents=True, exist_ok=True)
    paths.UMU.write_text("#!/bin/sh\n")
    return d


def test_find_win_exe_and_installer_check(tmp_path):
    root = tmp_path / "w"
    for name, data in (("Figment/Figment.exe", b"MZ" + b"\0" * 5000), ("Figment/UnityCrashHandler32.exe", b"MZ"),
                       ("Figment/Figment_Data/x.dat", b"x"), ("Figment/redist/vcredist_x86.exe", b"MZ"),
                       ("Figment/tools/config.exe", b"MZ")):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    best, alts = installer.find_exe(root, {"id": "1", "title": "Figment"}, "windows")
    assert best == "Figment/Figment.exe" and alts == ["Figment/tools/config.exe"]
    from itch_deck import proton
    setup = tmp_path / "setup.exe"
    setup.write_bytes(b"MZ" + b"\0" * 100 + b"Inno Setup Setup Data")
    assert proton.is_installer(setup) and not proton.is_installer(root / best)
    installer.extract(setup, tmp_path / "o", allow_exe=True)  # M5: installers are allowed through
    assert installer.find_installer(tmp_path / "o").name == "setup.exe"
    with pytest.raises(installer.InstallError):            # Linux builds never take a bare .exe
        installer.extract(root / best, tmp_path / "o2")
    installer.extract(root / best, tmp_path / "o3", allow_exe=True)
    assert (tmp_path / "o3/Figment.exe").exists()


def test_windows_install_then_change_build(tmp_path, server):
    win = _zip([("Figment/Figment.exe", b"MZ" + os.urandom(50_000), 0o644)])
    lin = _zip([("figment/Figment.x86_64", ELF64 + os.urandom(1000), 0o755)])
    _Handler.files, _Handler.slow = {"/w.zip": win, "/l.zip": lin}, False
    lib, inst = _setup(tmp_path, server, [_up(7, "w.zip", p_linux=False, p_windows=True, size=len(win))])
    # no GE-Proton yet: a clear reason, nothing downloaded
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert lib.games[0]["state"] == "failed" and lib.games[0]["fail_reason"] == "No internet"
    _fake_proton(tmp_path)
    inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("5")
    assert g["state"] == "installed", g.get("fail_reason")
    info = inst.index["5"]
    assert info["platform"] == "windows" and info["exe"] == "Figment/Figment.exe"
    assert info["prefix"] == str(tmp_path / "games/_prefixes/quiet-quarry")
    # Change build -> the Linux upload; the Windows prefix is untouched
    inst.lib.store.uploads = [_up(7, "w.zip", p_linux=False, p_windows=True, size=len(win)),
                              _up(8, "l.zip", size=len(lin))]
    assert not inst.enqueue(g)                       # already installed with the chosen build
    assert inst.enqueue(g, upload_id=8)
    _wait(inst)
    assert g["state"] == "installed" and inst.index["5"]["platform"] == "linux"
    assert inst.choices["5"] == 8 and not (tmp_path / "games/quiet-quarry/files/Figment").exists()
    # a failing change keeps the installed build and says why in a toast
    inst.lib.store.uploads.append(_up(9, "gone.zip", p_linux=False, p_windows=True, size=10))
    inst.enqueue(g, upload_id=9)
    _wait(inst)
    assert g["state"] == "installed" and inst.index["5"]["upload_id"] == 8
    assert inst.choices["5"] == 8 and inst.events[-1][0] == "error"


def test_umu_command_env_and_zipapp(tmp_path):
    from itch_deck import proton, runner
    paths.use_root(tmp_path)
    exe = tmp_path / "Figment.exe"
    exe.write_bytes(b"MZ")
    (tmp_path / "Figment_Data").mkdir()
    cmd = runner.command(exe, (1280, 800), umu=paths.UMU)
    assert cmd[:2] == [str(paths.UMU), str(exe)] and cmd[2:4] == ["-screen-fullscreen", "1"]
    assert proton.proton_dir({}) is None
    d = _fake_proton(tmp_path)
    assert proton.proton_dir({}) == d and proton.proton_dir({"proton": "nope"}) == d
    pre = tmp_path / "pfx-test"
    e = proton.env(d, pre)
    assert e["WINEPREFIX"] == str(pre) and e["GAMEID"] == "umu-default" and proton.first_run(pre)
    (pre / "system.reg").write_text("")
    assert not proton.first_run(pre)
    t = tmp_path / "umu.tar"
    with tarfile.open(t, "w") as tf:
        data = b"#!/usr/bin/env python3\n"
        ti = tarfile.TarInfo("umu/umu-run")
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))
    paths.UMU.unlink()
    proton.install_umu_tar(t)
    assert paths.UMU.read_bytes() == data and os.access(paths.UMU, os.X_OK)


# --- M5 -------------------------------------------------------------------------------------
FAKE_UMU = r"""#!/bin/sh
# fake umu-run: "installs" into the /DIR= or /D= target, builds the prefix
setup="$1"; shift
for a in "$@"; do
  case "$a" in /DIR=*) d="${a#/DIR=}";; /D=*) d="${a#/D=}";; esac
done
[ -n "$FAIL" ] && exit 3
[ -n "$HANG" ] && sleep 30
d=$(printf '%s' "${d#Z:}" | tr '\\' '/')
mkdir -p "$d/bin" "$WINEPREFIX"
printf 'MZgame' > "$d/bin/Quiet Quarry.exe"; printf 'MZ' > "$d/unins000.exe"
touch "$WINEPREFIX/system.reg"
echo "installed $setup into $d"
echo "beside setup: $(ls "$(dirname "$setup")" | tr '\n' ' ')"
"""
INNO = b"MZ" + b"\0" * 200 + b"Inno Setup Setup Data (6.2.0)" + b"\0" * 2000


def _umu(tmp_path):
    _fake_proton(tmp_path)
    paths.UMU.write_text(FAKE_UMU)
    paths.UMU.chmod(0o755)


def test_silent_inno_install(tmp_path, server):
    data = _zip([("QuietQuarry_Setup.exe", INNO, 0o644)])
    _Handler.files, _Handler.slow = {"/s.zip": data}, False
    lib, inst = _setup(tmp_path, server, [_up(7, "s.zip", p_linux=False, p_windows=True, size=len(data))])
    _umu(tmp_path)
    phases = []
    real = inst._upd
    inst._upd = lambda gid, **kw: (phases.append(kw.get("phase")), real(gid, **kw))
    inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("5")
    assert g["state"] == "installed", g.get("fail_reason")
    info = inst.index["5"]
    assert info["installer"] == "inno" and info["exe"] == "bin/Quiet Quarry.exe"
    files = tmp_path / "games/quiet-quarry/files"
    assert not (files / "QuietQuarry_Setup.exe").exists() and not (files.parent / "files.inst").exists()
    assert "installing" in phases or "proton" in phases
    log_ = (paths.LOGS / "games/quiet-quarry-install.log").read_text()
    assert "/VERYSILENT" in log_ and "/DIR=Z:" in log_


def test_split_parts_rules():
    ups = itch.parse_uploads({"uploads": [
        _up(1, "StrangerMore_setup.exe", p_linux=False, p_windows=True),
        _up(2, "StrangerMore_setup-1.bin", p_linux=False),
        _up(3, "StrangerMore_setup-2a.bin", p_linux=False, p_windows=True),
        _up(4, "game-linux-64.bin"),                       # a Linux build, not a slice
        _up(5, "soundtrack.zip", p_linux=False, type="soundtrack"),
    ]})
    best, others = itch.pick_build(ups, "windows")
    assert best["id"] == 1 and others == []                # slices never picked, even tagged Windows
    assert itch.pick_build(ups, "linux")[0]["id"] == 4
    assert [u["id"] for u in itch.split_parts(best, ups)] == [2, 3]
    renamed = itch.parse_uploads({"uploads": [_up(1, "Stranger More.exe", p_linux=False, p_windows=True),
                                              _up(2, "setup-1.bin", p_linux=False)]})
    assert [u["id"] for u in itch.split_parts(renamed[0], renamed)] == [2]   # exe renamed: all slices
    assert itch.split_parts(ups[3], ups) == []             # only for .exe builds


def test_split_installer_downloads_all_pieces(tmp_path, server):
    bin1, bin2 = os.urandom(200_000), os.urandom(150_000)
    _Handler.files, _Handler.slow = {"/setup.exe": INNO, "/setup-1.bin": bin1, "/setup-2.bin": bin2}, False
    lib, inst = _setup(tmp_path, server, [
        _up(7, "setup.exe", p_linux=False, p_windows=True, size=len(INNO)),
        _up(8, "setup-1.bin", p_linux=False, size=len(bin1)),
        _up(9, "setup-2.bin", p_linux=False, size=len(bin2))])
    _umu(tmp_path)
    progress = []
    real = inst._upd
    inst._upd = lambda gid, **kw: (progress.append(kw["progress"]) if "progress" in kw else None,
                                   real(gid, **kw))
    inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("5")
    assert g["state"] == "installed", g.get("fail_reason")
    log_ = (paths.LOGS / "games/quiet-quarry-install.log").read_text()
    assert "setup-1.bin" in log_ and "setup-2.bin" in log_ and "setup.exe" in log_
    dl = [p for p in progress if p not in (0, 1)]
    assert dl == sorted(dl) and max(dl) <= 1              # one bar across all pieces, never back
    assert not list((tmp_path / "games/_downloads").glob("5-*"))   # downloads cleaned up
    assert inst.index["5"]["upload_id"] == 7


def test_installer_failures(tmp_path, server, monkeypatch):
    from itch_deck import proton
    shield = b"MZ" + b"\0" * 100 + b"InstallShield" + b"\0" * 100
    _Handler.files, _Handler.slow = {"/is.exe": shield, "/s.exe": INNO}, False
    lib, inst = _setup(tmp_path, server, [_up(7, "is.exe", p_linux=False, p_windows=True, size=len(shield))])
    _umu(tmp_path)
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert lib.games[0]["state"] == "failed" and \
        lib.games[0]["fail_reason"] == "Try another build in Options"   # InstallShield: another build
    monkeypatch.setenv("FAIL", "1")                 # installer exits with an error
    inst.lib.store.uploads = [_up(8, "s.exe", p_linux=False, p_windows=True, size=len(INNO))]
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert lib.games[0]["state"] == "failed" and lib.games[0]["fail_reason"] == "Code W09"
    assert not (tmp_path / "games/quiet-quarry/files.new").exists()
    assert proton.silent_args("nsis", "/a/b")[-1] == "/D=Z:\\a\\b"
    monkeypatch.delenv("FAIL")
    monkeypatch.setenv("HANG", "1")                 # a hung installer is stopped
    with pytest.raises(proton.ProtonError, match="didn't finish"):
        proton.run_installer(paths.UMU, tmp_path / "x.exe", "inno", tmp_path / "t",
                             {"WINEPREFIX": str(tmp_path / "p")}, tmp_path / "i.log", timeout=1)


def test_sd_card_missing(tmp_path, server, monkeypatch):
    from itch_deck import config
    media = tmp_path / "media"
    monkeypatch.setattr(config, "MEDIA", media)
    card = media / "deck/SD/itch"
    assert config.card_missing(card) and config.drive_name(card) == "SD card"
    assert not config.card_missing(tmp_path / "games")
    data = _zip([("quarry/quarry", ELF64, 0o755)])
    _Handler.files, _Handler.slow = {"/q.zip": data}, False
    lib, inst = _setup(tmp_path, server, [_up(9, "q.zip", size=len(data))])
    inst.root_fn = lambda: card
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert "SD card missing" in lib.games[0]["fail_reason"] and not media.exists()
    # an installed game on a card that was taken out
    inst._upd("5", state=None, fail_reason=None)
    inst.index["5"] = {"game_id": "5", "dir": str(card / "quiet-quarry"), "exe": "q", "upload_id": 9}
    lib.apply_installs()
    g = lib.by_id("5")
    assert g["state"] == "missing" and g["missing"] == "card"
    assert inst.uninstall("5") is False and "5" in inst.index
    # card back -> installed again
    (card / "quiet-quarry/files").mkdir(parents=True)
    lib.apply_installs()
    assert g["state"] == "installed" and "missing" not in g


def test_program_picker_choice(tmp_path, server):
    data = _zip([("q/quarry", ELF64 + b"x" * 5000, 0o755), ("q/editor", ELF64, 0o755)])
    _Handler.files, _Handler.slow = {"/q.zip": data}, False
    lib, inst = _setup(tmp_path, server, [_up(9, "q.zip", size=len(data))])
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert inst.programs("5") == ["q/quarry", "q/editor"]
    assert inst.set_exe("5", "q/editor") and not inst.set_exe("5", "nope")
    assert inst.exe_path("5").name == "editor" and inst.programs("5") == ["q/editor", "q/quarry"]
    import json
    saved = json.loads((tmp_path / "games/quiet-quarry/install.json").read_text())
    assert saved["exe"] == "q/editor" and saved["exe_chosen"]


def test_crash_hint_old_proton(tmp_path):
    from itch_deck import runner
    paths.use_root(tmp_path)
    (paths.LOGS / "games").mkdir(parents=True)
    (paths.LOGS / "games/pm.log").write_text("[1114/205806.280:FATAL:rand_util_win.cc(60)] Check failed: hmod.\n")
    assert runner.crash_hint("pm") == "Try another Proton in Settings."
    assert runner.crash_hint("nope") is None


def test_pad_kept_by_instance_id():
    from itch_deck import input as inp

    class J:
        def __init__(self, i): self.i = i
        def get_instance_id(self): return 7          # instance ids grow after a display re-open
        def get_guid(self): return "g"

    class C:
        def __init__(self, i): self.id, self.name = i, "DualSense"

    class Ctl:
        Controller = C
        @staticmethod
        def is_controller(i): return True

    class PG:
        class joystick:
            Joystick = J
            @staticmethod
            def get_count(): return 1

    o = object.__new__(inp.Input)
    o.pg, o.ctl, o.pads = PG, Ctl, {}
    o.rescan(); o.rescan(); o.rescan()
    assert list(o.pads) == [7]


def test_pin_install_root(tmp_path, monkeypatch):
    from itch_deck import config
    media = tmp_path / "media"
    monkeypatch.setattr(config, "MEDIA", media)
    monkeypatch.setattr(config, "sd_card", lambda: None)
    cfg = {}
    assert not config.pin_install_root(cfg, [str(tmp_path / "home/Games/itch/x")])  # internal only
    assert not cfg                                  # no card seen yet: default stays
    assert config.pin_install_root(cfg, [str(media / "deck/SD/itch/game")])   # card out, games on it
    assert cfg["install_root"] == str(media / "deck/SD/itch")
    assert config.card_missing(config.install_root(cfg))       # -> installs say "SD card missing"
    monkeypatch.setattr(config, "sd_card", lambda: media / "deck/NEW")
    assert not config.pin_install_root(cfg)         # already pinned: never moves by itself
    cfg2 = {}
    assert config.pin_install_root(cfg2) and cfg2["install_root"] == str(media / "deck/NEW/scritch")   # new card: v0.8.2 name


def test_appimage_unpack(tmp_path):
    img = tmp_path / "game.bin"
    img.write_bytes(b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\0" * 32)
    assert installer.is_appimage(img)
    assert not installer.is_appimage(tmp_path / "nope")
    # stand-in AppImage: a script that does what --appimage-extract does
    img.write_text("#!/bin/sh\n[ \"$1\" = --appimage-extract ] || exit 3\n"
                   "mkdir -p squashfs-root && printf '#!/bin/sh\\n' > squashfs-root/AppRun\n")
    img.chmod(0o755)
    assert installer.unpack_appimage(tmp_path, "game.bin") == "squashfs-root/AppRun"
    assert not img.exists()
    bad = tmp_path / "bad.bin"
    bad.write_text("#!/bin/sh\nexit 1\n")
    bad.chmod(0o755)
    assert installer.unpack_appimage(tmp_path, "bad.bin") == "bad.bin" and bad.exists()


def test_crash_hint_missing_lib(tmp_path, monkeypatch):
    from itch_deck import runner
    monkeypatch.setattr(paths, "LOGS", tmp_path)
    (tmp_path / "games").mkdir()
    (tmp_path / "games/pm.log").write_text("./pm.bin: error while loading shared libraries: "
                                           "libnss3.so: cannot open shared object file\n")
    assert runner.crash_hint("pm") == "Try another build in Options."


def test_leftover_prefixes(tmp_path, monkeypatch):
    from itch_deck import config, proton
    monkeypatch.setattr(config, "MEDIA", tmp_path / "media")
    root = tmp_path / "games"
    for name in ("kept", "gone"):
        (root / "_prefixes" / name / "drive_c").mkdir(parents=True)
        (root / "_prefixes" / name / "drive_c" / "save.dat").write_bytes(b"x" * 1000)
    left = proton.leftover_prefixes([root, tmp_path / "nothing"], {"kept"})
    assert [p.name for p in left] == ["gone"] and proton.dir_size(left[0]) == 1000
    # a card that's out is skipped, not treated as empty or deleted
    assert proton.leftover_prefixes([tmp_path / "media/deck/SD/itch"], set()) == []


def test_install_choices(tmp_path, monkeypatch):
    from itch_deck import config
    monkeypatch.setattr(config, "sd_card", lambda: None)
    assert [n for n, _ in config.install_choices()] == ["Internal storage"]
    monkeypatch.setattr(config, "sd_card", lambda: tmp_path / "SD")
    assert config.install_choices()[0] == ("SD card", tmp_path / "SD/scritch")   # no games yet: new name
    (tmp_path / "SD/itch").mkdir(parents=True)                      # games already there: kept
    assert config.install_choices()[0] == ("SD card", tmp_path / "SD/itch")


# --- game updates (v0.7.3) ------------------------------------------------------------------
def test_update_for_rules():
    ups = itch.parse_uploads({"uploads": [_up(9, "q.zip", updated_at="2026-11-10", build_id=3)]})
    base = {"upload_id": 9, "platform": "linux", "upload_updated": "2026-11-10", "build_id": 3}
    assert installer.update_for(base, ups)[0] is None
    assert installer.update_for(dict(base, upload_updated="2026-11-01"), ups)[0] == "update"
    assert installer.update_for(dict(base, build_id=2), ups)[0] == "update"
    old = {"upload_id": 9, "platform": "linux"}                       # installed before v0.7.3
    assert installer.update_for(old, ups)[0] == "baseline"
    kind, b = installer.update_for(dict(base, upload_id=7), ups)       # dev replaced the upload
    assert kind == "update" and b["id"] == 9
    assert installer.update_for(dict(base, upload_id=7), [])[0] is None


def test_update_found_installed_and_cleared(tmp_path, server):
    v1 = _zip([("quarry/quarry", ELF64 + b"v1" * 1000, 0o755)])
    v2 = _zip([("quarry/quarry", ELF64 + b"v2" * 1000, 0o755)])
    _Handler.files, _Handler.slow = {"/q.zip": v1}, False
    ups = [_up(9, "q.zip", size=len(v1), updated_at="2026-11-10")]
    lib, inst = _setup(tmp_path, server, ups)
    inst.enqueue(lib.games[0])
    _wait(inst)
    g = lib.by_id("5")
    assert g["state"] == "installed" and inst.index["5"]["upload_updated"] == "2026-11-10"
    assert inst.check_updates(force=True) == 0 and not g.get("update")
    # the developer replaces the file on itch
    _Handler.files = {"/q.zip": v2}
    ups[0].update(size=len(v2), updated_at="2026-11-14")
    assert inst.check_updates() == 0                      # checked moments ago: not asked again
    assert inst.check_updates(force=True) == 1
    assert g["update"]["upload_id"] == 9
    assert '"update"' in (tmp_path / "games/quiet-quarry/install.json").read_text()   # survives
    lib2 = library.Library(None)
    lib2.games = [lib2._prep({"id": "5", "title": "Quiet Quarry", "platforms": ["linux"]})]
    installer.Installer(lib2, lambda: tmp_path / "games")
    assert lib2.by_id("5")["update"]                      # ... a restart
    assert inst.update(g)                                  # same upload id: still reinstalls
    _wait(inst)
    assert g["state"] == "installed" and not g.get("update")
    assert b"v2" in inst.exe_path("5").read_bytes()
    assert inst.events[-1] == ("done", "5", "Quiet Quarry is updated.")
    assert inst.index["5"]["upload_updated"] == "2026-11-14"



def test_player_words_are_short_and_plain():
    """Omri 15 Nov: casual players - a few plain words, no technical reasons on screen."""
    from itch_deck import runner, words
    assert words.short("Not enough space on the SD card: needs about 2.1 GB, 0.4 GB free.") \
        == "Not enough space"
    assert words.short("Lost the connection to itch.io. Retry when you're online") == "No internet"
    assert words.short("itch.io rejected the API key. Re-import it in Settings.") == "Sign in to itch again"
    assert words.short("No program to run was found in the download.") == "Try another build in Options"
    assert words.short("Something odd happened.") is None
    for say in [s for _, s in words._HINTS] + [h for _, h in runner.HINTS]:
        assert len(say.split()) <= 6, say
