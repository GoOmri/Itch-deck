"""GE-Proton downloaded by scritch (v0.7): safe unpack, checksum, resume-friendly install."""
import hashlib
import io
import tarfile

import pytest

from itch_deck import config, net, paths, proton


def _tar(path, members):
    with tarfile.open(path, "w:gz") as tf:
        for name, kind, data in members:
            ti = tarfile.TarInfo(name)
            if kind == "dir":
                ti.type = tarfile.DIRTYPE
                tf.addfile(ti)
            elif kind == "sym":
                ti.type, ti.linkname = tarfile.SYMTYPE, data
                tf.addfile(ti)
            else:
                ti.size = len(data)
                ti.mode = 0o755
                tf.addfile(ti, io.BytesIO(data))


@pytest.fixture
def home(tmp_path, monkeypatch):
    paths.use_root(tmp_path)
    return tmp_path


GOOD = [("GE-Proton9-1", "dir", None), ("GE-Proton9-1/proton", "file", b"#!/bin/sh\n"),
        ("GE-Proton9-1/files", "dir", None), ("GE-Proton9-1/files/lib", "sym", "../proton")]


def test_install_ge_tar(home):
    t = home / "ge.tar.gz"
    _tar(t, GOOD)
    assert proton.install_ge_tar(t) == "GE-Proton9-1"
    assert (paths.STEAM_TOOLS / "GE-Proton9-1" / "proton").exists()
    assert "GE-Proton9-1" in config.proton_versions()
    assert not (paths.STEAM_TOOLS / ".scritch-unpack").exists()


@pytest.mark.parametrize("bad", [
    [("GE-Proton9-1/proton", "file", b"x"), ("../evil", "file", b"x")],
    [("GE-Proton9-1/proton", "file", b"x"), ("/tmp/evil", "file", b"x")],
    [("GE-Proton9-1/proton", "file", b"x"), ("GE-Proton9-1/l", "sym", "../../../etc/passwd")],
])
def test_unsafe_tar_refused(home, bad):
    t = home / "bad.tar.gz"
    _tar(t, bad)
    with pytest.raises(proton.ProtonError):
        proton.install_ge_tar(t)
    assert not any(p.name == "GE-Proton9-1" for p in paths.STEAM_TOOLS.iterdir())


def test_fetch_ge_checks_the_sha(home, monkeypatch):
    src = home / "src.tar.gz"
    _tar(src, GOOD)
    good_sha = hashlib.sha512(src.read_bytes()).hexdigest()
    sha = {"v": good_sha}
    monkeypatch.setattr(net, "get_json", lambda url: {"assets": [
        {"name": "GE-Proton9-1.tar.gz", "browser_download_url": "u/tar", "size": 1},
        {"name": "GE-Proton9-1.sha512sum", "browser_download_url": "u/sha"}]})
    monkeypatch.setattr(net, "get", lambda url, **k: f"{sha['v']}  GE-Proton9-1.tar.gz\n".encode())

    def fake_dl(url, dest, **k):
        dest.write_bytes(src.read_bytes())
        if k.get("on_bytes"):
            k["on_bytes"](10, 10)
    monkeypatch.setattr(net, "download", fake_dl)
    monkeypatch.setattr(proton.shutil, "disk_usage", lambda p: type("U", (), {"free": 10**12})())
    sha["v"] = "0" * 128
    with pytest.raises(proton.ProtonError, match="damaged"):
        proton.fetch_ge()
    assert not config.proton_versions()
    sha["v"] = good_sha
    seen = []
    assert proton.fetch_ge(on_bytes=lambda d, t: seen.append(d)) == "GE-Proton9-1"
    assert seen and config.proton_versions() == ["GE-Proton9-1"]
    assert proton.fetch_ge() == "GE-Proton9-1"        # already there: no second download


def test_fetch_ge_needs_space(home, monkeypatch):
    monkeypatch.setattr(net, "get_json", lambda url: {"assets": [
        {"name": "GE-Proton9-1.tar.gz", "browser_download_url": "u", "size": 1}]})
    monkeypatch.setattr(proton.shutil, "disk_usage", lambda p: type("U", (), {"free": 10**9})())
    with pytest.raises(proton.ProtonError, match="GB free"):
        proton.fetch_ge()
