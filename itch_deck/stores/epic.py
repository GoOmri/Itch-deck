"""Epic Games through legendary (the open-source Epic client, GPL-3).

Step 1 (this file): sign in + a read-only library tab. Step 2 adds install / play.

- legendary is downloaded on demand (first Connect), never bundled: the release asset
  legendary_linux_x64 of legendary-gl/legendary, saved as DATA/epic/legendary.
- SCRiTCH keeps its OWN legendary settings folder (DATA/epic/config, LEGENDARY_CONFIG_PATH), so
  it never touches Heroic's or anyone else's Epic sign-in.
- Sign-in = the phone page: Epic's web login (legendary.gl/epiclogin) ends on a page of JSON with
  an "authorizationCode"; the player pastes that page, we run `legendary auth --code <code>`.
  The code works once and only for a few minutes.
- Library = `legendary list --json`: legendary's Game.__dict__ per game (app_name, app_title,
  asset_infos {Platform: build}, metadata = Epic catalog item: description, developer,
  keyImages, mainGameItem for DLC, customAttributes) plus "dlcs".

Epic decision (Omri 15 Nov): opt-in (tab only after Settings -> Epic Games -> Connect),
isolated (any Epic error is logged and stays in the Epic tab; itch never depends on it)."""
import json
import logging
import os
import re
import shutil
import subprocess

from .. import net, paths

log = logging.getLogger("scritch")

LATEST = "https://api.github.com/repos/legendary-gl/legendary/releases/latest"
ASSET = "legendary_linux_x64"
LOGIN_URL = "https://legendary.gl/epiclogin"
# landscape art first: tiles are wider than tall (DieselGameBoxTall is the portrait box)
COVER_TYPES = ("DieselGameBox", "OfferImageWide", "DieselStoreFrontWide", "Thumbnail",
               "DieselGameBoxTall")
PREFIX = "epic-"                         # game ids: never clash with itch's numeric ids


class EpicError(Exception):
    """Short, player-safe reason; details are in the log."""


def bin_path():
    return paths.DATA / "epic" / "legendary"


def config_dir():
    return paths.DATA / "epic" / "config"


def code_from_text(text):
    """The authorizationCode out of whatever the phone pasted: Epic's whole JSON page, the
    "authorizationCode": "…" line, or just the code. None if there's nothing like it."""
    text = (text or "").strip()
    m = re.search(r'"?authorizationCode"?\s*[:=]\s*"?([A-Za-z0-9]{16,})', text)
    if m:
        return m.group(1)
    words = re.findall(r"\b[0-9a-fA-F]{32}\b", text)
    return words[0] if len(words) == 1 else None


def _cover(meta):
    imgs = {i.get("type"): i.get("url") for i in meta.get("keyImages") or [] if isinstance(i, dict)}
    return next((imgs[k] for k in COVER_TYPES if imgs.get(k)), None)


def game_from_json(data):
    """One legendary game (list --json entry or metadata/<app>.json) -> a library game dict;
    None for DLC and broken entries."""
    if not isinstance(data, dict) or not data.get("app_name"):
        return None
    meta = data.get("metadata") or {}
    if meta.get("mainGameItem"):                     # DLC: belongs to its game
        return None
    attrs = meta.get("customAttributes") or {}
    third = (attrs.get("ThirdPartyManagedApp") or attrs.get("ThirdPartyManagedProvider") or {})
    plats = set()
    if not third.get("value"):                       # Ubisoft / EA games install elsewhere
        assets = {k.lower() for k in (data.get("asset_infos") or {})}
        if "asset_infos" not in data and data.get("asset_info"):
            assets.add("windows")                    # legendary's older single-asset files
        if "windows" in assets:
            plats.add("windows")
    return {
        "id": PREFIX + data["app_name"],
        "title": (data.get("app_title") or meta.get("title") or data["app_name"]).strip(),
        "author": meta.get("developer") or "",
        "cover_url": _cover(meta),
        "url": None,                                 # no itch page to read
        "short_text": (meta.get("description") or "").strip(),
        "long_text": (meta.get("longDescription") or "").strip(),   # game page "About"
        "platforms": sorted(plats) or ["other"],
        "store": "epic",
        "app_name": data["app_name"],
    }


def _log_text_fields(data):
    """Which text Epic's catalog gives us (for a fuller game page later): how many games have
    each field, and one short sample of the long description so we can see its format."""
    counts, sample = {}, None
    for e in data:
        meta = (e or {}).get("metadata") or {}
        if meta.get("mainGameItem"):
            continue
        for k in ("description", "longDescription", "shortDescription", "technicalDetails"):
            v = meta.get(k)
            if isinstance(v, str) and v.strip():
                counts[k] = counts.get(k, 0) + 1
                if k == "longDescription" and sample is None:
                    sample = (e.get("app_title"), v.strip()[:160])
        shots = [i for i in meta.get("keyImages") or [] if "screenshot" in str(i.get("type", "")).lower()]
        if shots:
            counts["screenshots"] = counts.get("screenshots", 0) + 1
    log.info("epic text fields: %s%s", counts or "none",
             f"; long description sample ({sample[0]}): {sample[1]!r}" if sample else "")


def fetch_legendary(cancel=None, on_bytes=None):
    """One-time download of legendary (a single Linux program, a few MB)."""
    dest = bin_path()
    try:
        rel = net.get_json(LATEST)
        asset = next((a for a in rel.get("assets") or [] if a.get("name") == ASSET), None)
        if not asset:
            log.warning("epic: no %s in legendary %s (%s)", ASSET, rel.get("tag_name"),
                        [a.get("name") for a in rel.get("assets") or []])
            raise EpicError("Couldn't get the Epic helper")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name("legendary.new")
        net.download(asset["browser_download_url"], tmp, cancel=cancel, on_bytes=on_bytes)
        if tmp.stat().st_size < 1_000_000:
            raise EpicError("Couldn't get the Epic helper")
        os.chmod(tmp, 0o755)
        os.replace(tmp, dest)
        log.info("epic: legendary %s installed", rel.get("tag_name"))
    except (net.Offline, net.NotFound, net.AuthError) as e:
        log.warning("epic: legendary download failed: %s", e)
        raise EpicError("No internet") from None


class EpicStore:
    name = "epic"

    latest = {}                      # app_name -> newest Windows build_version (from sync)

    def ready(self):
        b = bin_path()
        return b.is_file() and os.access(b, os.X_OK)

    def connected(self):
        return (config_dir() / "user.json").is_file()

    def user(self):
        try:
            u = json.loads((config_dir() / "user.json").read_text())
            return u.get("displayName") or "Epic"
        except (OSError, ValueError):
            return None

    def _run(self, args, timeout):
        from ..runner import child_env               # never hand our bundled libs to legendary
        cdir = config_dir()
        cdir.mkdir(parents=True, exist_ok=True)
        os.chmod(cdir, 0o700)                        # holds the Epic sign-in
        env = dict(child_env(), LEGENDARY_CONFIG_PATH=str(cdir))
        try:
            r = subprocess.run([str(bin_path()), *args], capture_output=True, text=True,
                               timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            log.warning("epic: legendary %s timed out", args[0])
            raise EpicError("Epic didn't answer") from None
        except OSError as e:
            log.warning("epic: can't run legendary: %s", e)
            raise EpicError("Couldn't start the Epic helper") from None
        tail = (r.stderr or "").strip().splitlines()[-6:]
        log.info("epic: legendary %s -> %s%s", args[0], r.returncode,
                 ("\n  " + "\n  ".join(tail)) if tail else "")
        return r

    def login(self, code):
        """True when Epic accepted the code (user.json written)."""
        (config_dir() / "user.json").unlink(missing_ok=True)
        self._run(["auth", "--code", code], timeout=90)
        return self.connected()

    def logout(self):
        if self.ready() and self.connected():
            try:
                self._run(["auth", "--delete"], timeout=30)
            except EpicError:
                pass
        shutil.rmtree(config_dir(), ignore_errors=True)

    def sync(self):
        """All owned Epic games (DLC left out). Needs the network; raises EpicError."""
        if not self.connected():
            raise EpicError("Not signed in")
        r = self._run(["list", "--json"], timeout=300)
        try:
            data = json.loads(r.stdout or "null")
        except ValueError:
            data = None
        if r.returncode != 0 or not isinstance(data, list):
            raise EpicError("Couldn't reach Epic")
        games, latest = {}, {}
        for entry in data:
            g = game_from_json(entry)
            if g:
                games[g["id"]] = g
                win = next((v for k, v in (entry.get("asset_infos") or {}).items()
                            if k.lower() == "windows"), None) or {}
                if win.get("build_version"):
                    latest[entry["app_name"]] = win["build_version"]
        self.latest = latest
        log.info("epic sync: %d games", len(games))
        _log_text_fields(data)
        return list(games.values())

    # --- step 2: install / launch / uninstall --------------------------------------
    def _env(self):
        from ..runner import child_env
        return dict(child_env(), LEGENDARY_CONFIG_PATH=str(config_dir()))

    def install(self, app_name, folder, on_progress=None, cancel=None, log_file=None):
        """Download + install into folder (exactly). Resumes an interrupted install of the same
        folder. on_progress(frac, mib_s, eta_s); cancel() -> True stops (raises Cancelled).
        Returns the game's exe path relative to folder."""
        from ..net import Cancelled
        cmd = [str(bin_path()), "install", app_name, "-y", "--game-folder", str(folder),
               "--platform", "Windows", "--skip-sdl", "--skip-dlcs"]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 bufsize=1, env=self._env(), stdin=subprocess.DEVNULL,
                                 start_new_session=True)
        except OSError as e:
            log.warning("epic: can't run legendary: %s", e)
            raise EpicError("Couldn't start the Epic helper") from None
        tail, speed = [], 0.0
        out = open(log_file, "w") if log_file else None
        stopper = None
        try:
            if cancel:                                # cancel even while legendary is quiet
                import threading
                stopper = threading.Event()

                def watch():
                    while not stopper.wait(0.5):
                        if cancel() and p.poll() is None:
                            _stop(p)
                            return
                threading.Thread(target=watch, daemon=True, name="epic-cancel").start()
            for line in p.stdout:
                if out:
                    out.write(line)
                tail = (tail + [line.rstrip()])[-15:]
                m = PROGRESS.search(line)
                if m and on_progress:
                    h, mi, s = (int(x) for x in m.group(2, 3, 4))
                    on_progress(float(m.group(1)) / 100, speed, h * 3600 + mi * 60 + s)
                m = SPEED.search(line)
                if m:
                    speed = float(m.group(1)) * 1.048576     # MiB/s -> MB/s
            p.wait()
        finally:
            if stopper:
                stopper.set()
            if out:
                out.close()
        if cancel and cancel():
            raise Cancelled()
        text = "\n".join(tail).lower()
        if p.returncode != 0:
            log.info("epic: install %s -> %s\n  %s", app_name, p.returncode, "\n  ".join(tail[-6:]))
            if "disk space" in text:
                raise EpicError("Not enough space")
            if "login" in text and "fail" in text:
                raise EpicError("Signed out of Epic")
            raise EpicError("Couldn't install")
        rec = self.installed().get(app_name) or {}
        exe = rec.get("executable") or ""
        if not exe:
            raise EpicError("Couldn't install")
        return exe.replace("\\", "/")

    def installed(self):
        """legendary's own record of what it installed: {app_name: {install_path, executable…}}."""
        try:
            return json.loads((config_dir() / "installed.json").read_text())
        except (OSError, ValueError):
            return {}

    def launch_params(self, app_name):
        """How to start the game: legendary's LaunchParameters (exe, args incl. Epic's sign-in
        token for games that check it, working dir). Offline mode if Epic can't be reached."""
        for extra in ([], ["--offline"]):
            r = self._run(["launch", app_name, "--json", "--no-wine", "--skip-version-check", *extra],
                          timeout=60)
            try:
                data = json.loads(r.stdout or "null")
            except ValueError:
                data = None
            if r.returncode == 0 and isinstance(data, dict) and data.get("game_executable"):
                return data
        raise EpicError("Couldn't start")

    def uninstall(self, app_name):
        """Make legendary forget the install (SCRiTCH deletes the files itself)."""
        if self.ready() and app_name in self.installed():
            try:
                self._run(["uninstall", app_name, "-y", "--keep-files", "--skip-uninstaller"],
                          timeout=60)
            except EpicError:
                pass


PROGRESS = re.compile(r"Progress: ([\d.]+)%.*?ETA: (\d+):(\d+):(\d+)")
SPEED = re.compile(r"\+ Download\s*-\s*([\d.]+) MiB/s")


def _stop(p):
    """Stop legendary and its download workers (own process group); it keeps a resume file."""
    import signal
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(10)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
