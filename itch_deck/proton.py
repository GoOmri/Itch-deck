"""Windows games (M4): umu-launcher + GE-Proton. One prefix per game in
<install root>/_prefixes/<slug>, outside the game folder, so saves survive an uninstall."""
import logging
import shutil
import tarfile
from pathlib import Path

from . import config, net, paths

log = logging.getLogger("itch-deck")
UMU_LATEST = "https://api.github.com/repos/Open-Wine-Components/umu-launcher/releases/latest"


class ProtonError(Exception):
    """A reason to show the user (install failed / can't play)."""


def umu_path():
    """Our downloaded umu-run zipapp, else one on PATH."""
    if paths.UMU.exists():
        return paths.UMU
    w = shutil.which("umu-run")
    return Path(w) if w else None


def fetch_umu(cancel=None):
    """One-time download of the umu-run zipapp (release asset *-zipapp.tar, ~1 MB)."""
    try:
        rel = net.get_json(UMU_LATEST)
        asset = next((a for a in rel.get("assets") or []
                      if a.get("name", "").endswith("zipapp.tar")), None)
        if not asset:
            raise ProtonError("Couldn't find umu-launcher to download. Details are in the log.")
        paths.UMU.parent.mkdir(parents=True, exist_ok=True)
        tmp = paths.UMU.parent / "umu.tar"
        net.download(asset["browser_download_url"], tmp, cancel=cancel)
    except (net.Offline, net.NotFound, net.AuthError) as e:
        log.warning("umu: download failed: %s", e)
        raise ProtonError("Couldn't download umu-launcher (needed once for Windows games). "
                          "Retry when you're online.") from None
    install_umu_tar(tmp)
    tmp.unlink(missing_ok=True)
    log.info("umu: installed %s from %s", rel.get("tag_name"), asset["name"])


def install_umu_tar(tar_path):
    with tarfile.open(tar_path) as tf:
        m = next((m for m in tf.getmembers() if m.isfile() and Path(m.name).name == "umu-run"), None)
        if m is None:
            raise ProtonError("The umu-launcher download had no umu-run in it.")
        data = tf.extractfile(m).read()
    new = paths.UMU.with_suffix(".new")
    new.write_bytes(data)
    new.chmod(0o755)
    new.replace(paths.UMU)


def proton_dir(cfg):
    """Chosen GE-Proton folder (Settings), else the newest installed one. None if missing."""
    names = config.proton_versions()
    want = cfg.get("proton")
    name = want if want in names else (names[0] if names else None)
    if not name:
        return None
    d = paths.STEAM_TOOLS / name
    return d if (d / "proton").exists() else None


def prefix_dir(root, slug):
    return Path(root) / "_prefixes" / slug


def first_run(prefix):
    """No prefix yet: umu sets up the runtime + prefix (~30 s, longer the very first time)."""
    p = Path(prefix)
    return not ((p / "system.reg").exists() or (p / "pfx" / "system.reg").exists())


def env(proton, prefix):
    """umu settings for one game. GAMEID stays umu-default: "umu-<number>" means a Steam app id
    in umu's fix database, so an itch id there could pull in fixes for an unrelated game."""
    Path(prefix).mkdir(parents=True, exist_ok=True)
    return {"WINEPREFIX": str(prefix), "PROTONPATH": str(proton), "GAMEID": "umu-default"}


def is_installer(path):
    """Inno Setup / NSIS / InstallShield signatures in the first 2 MB of an .exe."""
    try:
        with open(path, "rb") as f:
            head = f.read(2_000_000)
    except OSError:
        return False
    return any(sig in head for sig in (b"Inno Setup", b"Nullsoft", b"NullsoftInst",
                                       b"InstallShield"))
