"""Windows games (M4): umu-launcher + GE-Proton. One prefix per game in
<install root>/_prefixes/<slug>, outside the game folder, so saves survive an uninstall."""
import logging
import os
import shutil
import tarfile
from pathlib import Path

from . import config, net, paths

log = logging.getLogger("itch-deck")
UMU_LATEST = "https://api.github.com/repos/Open-Wine-Components/umu-launcher/releases/latest"
GE_LATEST = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
GE_SPACE = 2_500_000_000      # bytes free needed on internal storage (~0.5 GB download + ~1.5 GB)

NEED_GE = "GE-Proton isn't installed. Get it in Settings → Proton version."


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


def fetch_ge(cancel=None, on_bytes=None):
    """One-time download of the newest GE-Proton into Steam's compatibilitytools.d, where Steam
    and ProtonUp-Qt see it too (~0.5 GB download, ~1.5 GB unpacked, internal storage). The
    download resumes if interrupted and is checked against the release's sha512 file.
    Returns the installed folder name."""
    try:
        rel = net.get_json(GE_LATEST)
        assets = rel.get("assets") or []
        tar = next((a for a in assets if a.get("name", "").endswith(".tar.gz")), None)
        sha = next((a for a in assets if a.get("name", "").endswith(".sha512sum")), None)
        if not tar:
            raise ProtonError("Couldn't find GE-Proton to download. Details are in the log.")
        if tar["name"][:-7] in config.proton_versions():
            return tar["name"][:-7]
        paths.STEAM_TOOLS.mkdir(parents=True, exist_ok=True)
        dl = paths.DATA / "ge" / tar["name"]
        dl.parent.mkdir(parents=True, exist_ok=True)
        have = dl.with_name(dl.name + ".part")
        have = have.stat().st_size if have.exists() else 0
        free = shutil.disk_usage(paths.STEAM_TOOLS).free
        if free + have < GE_SPACE:
            raise ProtonError(f"GE-Proton needs about {GE_SPACE / 1e9:.1f} GB on internal "
                              f"storage; {free / 1e9:.1f} GB free.")
        if not dl.exists():
            log.info("ge-proton: download %s (%d MB)", tar["name"], tar.get("size", 0) // 1_000_000)
            net.download(tar["browser_download_url"], dl, resume=True, cancel=cancel,
                         on_bytes=on_bytes)
        if sha:
            want = net.get(sha["browser_download_url"]).decode(errors="replace").split()[0]
            if _sha512(dl) != want.lower():
                dl.unlink(missing_ok=True)
                raise ProtonError("The GE-Proton download was damaged. Retry to download it again.")
    except (net.Offline, net.NotFound, net.AuthError) as e:
        log.warning("ge-proton: download failed: %s", e)
        raise ProtonError("Couldn't download GE-Proton (needed once for Windows games). "
                          "Retry when you're online.") from None
    name = install_ge_tar(dl)
    dl.unlink(missing_ok=True)
    log.info("ge-proton: installed %s", name)
    return name


def _sha512(path):
    import hashlib
    h = hashlib.sha512()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install_ge_tar(tar_path):
    """Unpack a GE-Proton tarball (one top folder with a 'proton' script) into STEAM_TOOLS.
    Unpacks next to it first, then renames, so a half-done unpack never looks installed.
    Members that would land outside the folder (absolute paths, '..', links pointing out) are
    refused."""
    tmp = paths.STEAM_TOOLS / ".scritch-unpack"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    root = tmp.resolve()
    try:
        with tarfile.open(tar_path) as tf:
            members = tf.getmembers()
            for m in members:
                dest = (root / m.name).resolve()
                bad = not str(dest).startswith(str(root) + os.sep) or m.isdev()
                if m.issym() or m.islnk():
                    base = dest.parent if m.issym() else root
                    target = (base / m.linkname).resolve()
                    bad = bad or not str(target).startswith(str(root) + os.sep)
                if bad:
                    raise ProtonError("The GE-Proton download looks wrong (unsafe paths). "
                                      "Details are in the log.")
            if hasattr(tarfile, "tar_filter"):        # Python's own guard as a second layer
                tf.extractall(tmp, members=members, filter="tar")
            else:
                tf.extractall(tmp, members=members)
        tops = [d for d in tmp.iterdir() if d.is_dir()]
        if len(tops) != 1 or not (tops[0] / "proton").exists():
            raise ProtonError("The GE-Proton download had an unexpected layout. Details are in "
                              "the log.")
        final = paths.STEAM_TOOLS / tops[0].name
        if final.exists():
            shutil.rmtree(final)
        tops[0].rename(final)
        return final.name
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


def leftover_prefixes(roots, installed):
    """Prefixes (saves) of games that aren't installed any more, under each root's _prefixes/.
    installed = game folder names that are installed (their prefix has the same name)."""
    out = []
    for r in roots:
        d = Path(r) / "_prefixes"
        if config.card_missing(d):
            continue
        try:
            out += [k for k in d.iterdir() if k.is_dir() and k.name not in installed]
        except OSError:
            pass
    return out


def dir_size(path):
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


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


def installer_kind(path):
    """'inno' | 'nsis' | 'installshield' | None, from signatures in the first 2 MB of an .exe."""
    try:
        with open(path, "rb") as f:
            head = f.read(2_000_000)
    except OSError:
        return None
    if b"Inno Setup" in head:
        return "inno"
    if b"NullsoftInst" in head or b"Nullsoft" in head:
        return "nsis"
    if b"InstallShield" in head:
        return "installshield"
    return None


def is_installer(path):
    return installer_kind(path) is not None


SILENT_KINDS = ("inno", "nsis")
INSTALL_TIMEOUT_S = 15 * 60


def win_path(path):
    """Proton maps Z: to the Linux root."""
    return "Z:" + str(path).replace("/", "\\")


def silent_args(kind, target):
    """Command-line switches that install with no window into target."""
    if kind == "inno":
        return ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/NOICONS",
                "/NOCANCEL", f"/DIR={win_path(target)}"]
    if kind == "nsis":
        return ["/S", f"/D={win_path(target)}"]       # /D= must be last and unquoted
    raise ProtonError("This installer type can't run silently.")


def run_installer(umu, setup, kind, target, game_env, log_file, cancel=None, on_phase=None,
                  timeout=INSTALL_TIMEOUT_S):
    """Run a Windows installer silently through umu in the game's prefix. Blocks until it ends.
    on_phase("proton") while umu builds a new prefix, then on_phase("installing")."""
    import os
    import signal
    import subprocess
    import time
    from . import runner
    Path(target).mkdir(parents=True, exist_ok=True)
    cmd = [str(umu), str(setup)] + silent_args(kind, target)
    env = runner.child_env()
    env.update(game_env)
    env.setdefault("WINEDEBUG", "-all")
    prefix = game_env.get("WINEPREFIX")
    phase = None
    t0 = time.monotonic()
    with open(log_file, "w") as out:
        out.write(f"# installer ({kind}): {' '.join(cmd)}\n# env: {game_env}\n")
        out.flush()
        log.info("installer: %s %s -> %s", kind, Path(setup).name, target)
        try:
            proc = subprocess.Popen(cmd, cwd=Path(setup).parent, env=env, stdout=out,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True)
        except OSError as e:
            log.warning("installer: couldn't start %s: %s", setup, e)
            raise ProtonError("Couldn't start the installer. Details are in the log.") from None

        def kill():
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
        while proc.poll() is None:
            want = "proton" if prefix and first_run(prefix) else "installing"
            if want != phase and on_phase:
                phase = want
                on_phase(want)
            if cancel and cancel():
                kill()
                raise net.Cancelled()
            if time.monotonic() - t0 > timeout:
                kill()
                log.warning("installer: no exit after %d s, stopped", timeout)
                raise ProtonError("The installer didn't finish (stopped after 15 min).")
            time.sleep(0.5)
    rc = proc.returncode
    log.info("installer: exit %s after %.0f s", rc, time.monotonic() - t0)
    if rc != 0:
        raise ProtonError("The installer stopped with an error. Details are in the log.")