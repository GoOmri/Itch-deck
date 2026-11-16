"""GOG's DOS games through a native Linux DOSBox (v0.9.7), the way Heroic does it.

GOG ships DOS games with its own DOSBox: a Windows one (dosbox.exe) and, in Linux builds, one
built against libraries SteamOS doesn't have (libFLAC, libSDL_sound). Under Proton the Windows
one showed its logo and closed (Eye of the Beholder, 16 Nov). So a GOG game whose play task
starts dosbox.exe runs with DOSBox Staging instead (Flathub io.github.dosbox-staging, or a
dosbox-staging on PATH), with the game's own settings files and folder. Installed once,
without a password (flatpak: system install, else per-user). If it can't be had, the game
falls back to GOG's Windows DOSBox under Proton.

GOG's settings are written for Windows: mount lines like  mount C "..\\cloud_saves" -t overlay.
Each -conf file is copied next to the original as scritch-<name> with "\\" -> "/" in its
[autoexec] mount lines, and that copy is passed instead (the original stays untouched)."""
import logging
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("scritch")

APP = "io.github.dosbox-staging"
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"
DROP_ARGS = {"-noconsole"}            # Windows-only switch


def is_dosbox_game(info):
    return info.get("store") == "gog" and info.get("platform") == "windows" and \
        Path(info.get("exe") or "").name.lower() == "dosbox.exe"


def _flatpak():
    return shutil.which("flatpak")


def _run(cmd, timeout, log_file=None):
    from .runner import child_env
    try:
        out = open(log_file, "a") if log_file else subprocess.DEVNULL
        try:
            r = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, timeout=timeout,
                               env=child_env(), stdin=subprocess.DEVNULL)
        finally:
            if log_file:
                out.close()
        return r.returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        log.info("dosbox: %s: %s", " ".join(cmd[:3]), e)
        return None


def native():
    """The command that starts a native DOSBox Staging, or None."""
    exe = shutil.which("dosbox-staging")
    if exe:
        return [exe]
    fp = _flatpak()
    if fp and _run([fp, "info", APP], 30) == 0:
        return [fp, "run", APP]
    return None


def ensure(log_file=None):
    """DOSBox Staging there, installing it from Flathub if needed (system, else per-user, no
    password either way on SteamOS). Returns native() or None."""
    cmd = native()
    if cmd:
        return cmd
    fp = _flatpak()
    if not fp:
        log.info("dosbox: no flatpak on this system")
        return None
    log.info("dosbox: installing %s from Flathub", APP)
    if _run([fp, "install", "-y", "--noninteractive", "flathub", APP], 900, log_file) != 0:
        _run([fp, "remote-add", "--user", "--if-not-exists", "flathub", FLATHUB], 120, log_file)
        _run([fp, "install", "--user", "-y", "--noninteractive", "flathub", APP], 900, log_file)
    cmd = native()
    log.info("dosbox: %s", "ready" if cmd else "couldn't install")
    return cmd


def _unix_conf(src):
    """Copy of a GOG DOSBox settings file with Windows paths in [autoexec] mount lines turned
    into Linux ones (scritch-<name> next to it). Returns the copy's path."""
    text = src.read_text(errors="replace")
    out, auto = [], False
    for line in text.splitlines():
        s = line.strip().lower()
        if s.startswith("[") and s.endswith("]"):
            auto = s == "[autoexec]"
        elif auto and re.match(r"@?(mount|imgmount)\b", s):
            line = line.replace("\\", "/")
        out.append(line)
    dst = src.with_name("scritch-" + src.name)
    dst.write_text("\n".join(out) + "\n")
    return dst


def launch(info, base_cmd):
    """(exe, args, cwd) for runner.run: native DOSBox Staging with the game's play-task
    arguments, run in the play task's folder (GOG's mount ".." lines are relative to it)."""
    files = Path(info["dir"]) / "files"
    cwd = files / info["cwd"] if info.get("cwd") else (files / info["exe"]).parent
    args, it = [], iter(info.get("args") or [])
    for a in it:
        if a in DROP_ARGS:
            continue
        if a.lower() == "-conf":
            conf = next(it, "")
            p = (cwd / conf.replace("\\", "/")).resolve()
            if p.is_file():
                try:
                    p = _unix_conf(p)
                except OSError as e:
                    log.info("dosbox: can't copy %s: %s", p, e)
            args += ["-conf", str(p)]
            continue
        args.append(a)
    exe = Path(base_cmd[0])
    pre = list(base_cmd[1:])
    if pre[:1] == ["run"]:                         # flatpak: let it see the game, start there
        pre = ["run", f"--filesystem={files}", f"--cwd={cwd}"] + pre[1:]
    return exe, pre + args, str(cwd)
