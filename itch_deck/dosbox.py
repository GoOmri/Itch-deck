"""GOG's DOS games through a native Linux DOSBox (v0.9.7), the way Heroic does it.

GOG ships DOS games with its own DOSBox: a Windows one (dosbox.exe) and, in Linux builds, one
built against libraries SteamOS doesn't have (libFLAC, libSDL_sound). Under Proton the Windows
one showed its logo and closed (Eye of the Beholder, 16 Nov). So a GOG game whose play task
starts dosbox.exe runs with DOSBox Staging instead (Flathub io.github.dosbox-staging, or a
dosbox-staging on PATH), with the game's own settings files and folder. Installed once,
without a password (flatpak: system install, else per-user). If it can't be had, the game
falls back to GOG's Windows DOSBox under Proton.

GOG's settings are written for Windows: mount lines like  mount C "..\\cloud_saves" -t overlay.
Each -conf file is copied next to the original as scritch-<name> without its [autoexec]; those
commands go to DOSBox as -c (mount paths with "/"), then GOG's own -c ("exit"). See _split_conf."""
import logging
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


def _split_conf(src):
    """A copy of a GOG DOSBox settings file without its [autoexec] section (scritch-<name>, bytes
    kept as they are: GOG writes CP437 boxes), and that section's commands. SCRiTCH passes the
    commands itself as -c (v0.9.9): DOSBox Staging ran none of GOG's [autoexec] (EOB: text mode,
    then shut down after 1 s). Messages, pause and cls are left out; Windows paths in mount lines
    become Linux ones."""
    text = src.read_bytes().decode("latin-1")
    keep, cmds, auto = [], [], False
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith("[") and low.endswith("]"):
            auto = low == "[autoexec]"
            if auto:
                continue
        if not auto:
            keep.append(line)
            continue
        if not s or low.split()[0].lstrip("@") in ("cls", "pause", "exit", "echo", "rem") or \
                low.startswith(("#", "::", "@echo")):
            continue
        if low.split()[0] in ("mount", "imgmount"):
            s = s.replace("\\", "/")
        cmds.append(s)
    dst = src.with_name("scritch-" + src.name)
    dst.write_bytes(("\n".join(keep) + "\n").encode("latin-1"))
    return dst, cmds


def launch(info, base_cmd):
    """(exe, args, cwd) for runner.run: native DOSBox Staging with the game's play-task
    arguments, run in the play task's folder (GOG's mount ".." lines are relative to it)."""
    files = Path(info["dir"]) / "files"
    cwd = files / info["cwd"] if info.get("cwd") else (files / info["exe"]).parent
    args, cmds, tail, it = [], [], [], iter(info.get("args") or [])
    for a in it:
        if a in DROP_ARGS:
            continue
        if a.lower() == "-conf":
            conf = next(it, "")
            from .stores.gog import _ci          # GOG's names come from Windows: any letter case
            p = _ci(cwd, conf).resolve()
            if not p.is_file():                  # v0.9.11 Deck log: "Can't open custom config file"
                try:
                    names = sorted(c.name for c in p.parent.iterdir())[:60]
                except OSError:
                    names = []
                log.info("dosbox: settings file %s not found; folder has: %s", p, names)
            if p.is_file():
                try:
                    p, more = _split_conf(p)
                    cmds += more
                except OSError as e:
                    log.info("dosbox: can't copy %s: %s", p, e)
            args += ["-conf", str(p)]
            continue
        if a.lower() == "-c":                     # GOG's own -c ("exit") go after the game
            tail += ["-c", next(it, "")]
            continue
        args.append(a)
    for c in cmds:
        args += ["-c", c]
    args += tail
    log.info("dosbox: commands %s", cmds)
    exe = Path(base_cmd[0])
    pre = list(base_cmd[1:])
    if pre[:1] == ["run"]:                         # flatpak: let it see the game, start there
        pre = ["run", f"--filesystem={files}", f"--cwd={cwd}"] + pre[1:]
    return exe, pre + args, str(cwd)


# --- your own DOS games (v0.9.19): <games folder>/dos/<game> ---------------------------------------
def is_own_dos(info):
    """An install record made by itch_deck/dosgames.py (store "dos")."""
    return info.get("store") == "dos"


def launch_own(info, base_cmd, once=None, stay=False):
    """(exe, args, cwd) for runner.run: DOSBox Staging with the game's folder as drive C, a disc image as
    drive D when the folder has one, then the chosen program. The game's saves stay in its folder.
    Sub folders are entered with cd (DOS games use short 8.3 names)."""
    folder = Path(info["dir"])
    # once: a setup program picked in "Program to run" runs instead of the game, this Play only (Installer.take_once)
    rel = (once or info.get("exe") or "").replace("\\", "/")
    parts = [p for p in rel.split("/") if p]
    cmds = [f'mount c "{folder}"']
    image = info.get("image")
    if image:
        cmds.append(f'imgmount d "{folder / image}" -t iso')
    cmds.append("c:")
    cmds += [f"cd {p}" for p in parts[:-1]]
    if parts:
        cmds.append(parts[-1])
    if not stay:                                   # "Stay open when the game ends": DOSBox stays at the prompt to read
        cmds.append("exit")                        # what the program printed (leave with the View + Menu shortcut)
    args = [x for c in cmds for x in ("-c", c)]
    log.info("dosbox: own game %s: %s", folder.name, cmds)
    exe, pre = Path(base_cmd[0]), list(base_cmd[1:])
    if pre[:1] == ["run"]:                         # flatpak: let it see the game, start there
        pre = ["run", f"--filesystem={folder}", f"--cwd={folder}"] + pre[1:]
    return exe, pre + args, str(folder)
