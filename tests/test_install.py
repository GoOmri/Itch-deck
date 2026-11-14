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
    # Windows-only and "no space" give a reason on the game page
    _Handler.slow = False
    inst.lib.store.uploads = [_up(9, "w.zip", p_linux=False, p_windows=True)]
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert lib.games[0]["state"] == "failed" and "Windows" in lib.games[0]["fail_reason"]
    inst.lib.store.uploads = [_up(9, "big.zip", size=10 ** 15)]
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert "Not enough space" in lib.games[0]["fail_reason"]
    # offline mid-way: failed with a retry message
    inst.lib.store.uploads = [_up(9, "missing.zip", size=10)]
    inst.enqueue(lib.games[0])
    _wait(inst)
    assert "Retry" in lib.games[0]["fail_reason"]


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
