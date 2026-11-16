"""GOG through gogdl (Heroic's GOG helper, GPL-3).

Step 1 (v0.9.0/0.9.1): sign in + library tab. Step 2 (v0.9.2): install / play / uninstall with
the vendored gogdl (itch_deck/vendor, run as `scritch --gogdl …` in its own process).

- Signing in needs NO helper (v0.9.1): SCRiTCH makes gogdl's two token calls itself
  (auth.gog.com/token: authorization_code, refresh_token; Galaxy's public client id + secret)
  and writes the result in gogdl's own auth-file format (DATA/gog/auth.json = {client_id: data
  + loginTime}), so step 2 can run gogdl with --auth-config-path on it. v0.9.0 downloaded gogdl
  for this, but gogdl's GitHub releases are hand-published drafts and the Linux file comes from
  a separate zipapp job: the download failed on the Deck (16 Nov).
- Sign-in = the phone page: GOG's own sign-in (auth.gog.com, Galaxy client id) ends on
  embed.gog.com/on_login_success?origin=client&code=…; the player copies that page's ADDRESS.
- Library = GOG's web API with that token (gogdl has no list command): owned games, paged
  (account/getFilteredProducts). Game page text + screenshots: api.gog.com/products/<id>.

Same rules as Epic: opt-in (tab only after signing in), isolated (errors logged, stay in the
GOG tab; itch and Epic never depend on it)."""
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from .. import net, paths

log = logging.getLogger("scritch")

CLIENT_ID = "46899977096215655"          # GOG Galaxy's public client (what gogdl and Heroic use)
CLIENT_SECRET = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
TOKEN_URL = "https://auth.gog.com/token"
REDIRECT = "https://embed.gog.com/on_login_success?origin=client"
LOGIN_URL = ("https://auth.gog.com/auth?client_id=" + CLIENT_ID +
             "&redirect_uri=https%3A%2F%2Fembed.gog.com%2Fon_login_success%3Forigin%3Dclient"
             "&response_type=code&layout=galaxy")
LIST_URL = "https://embed.gog.com/account/getFilteredProducts?mediaType=1&sortBy=title&page={}"
USER_URL = "https://embed.gog.com/userData.json"
PRODUCT_URL = "https://api.gog.com/products/{}?expand=description,screenshots"
GAME_URL = "https://api.gog.com/v2/games/{}?locale=en-US"   # store data: features (controller)
COVER_SUFFIX = "_392.jpg"                # GOG image formatter: landscape product tile
SHOT_FORMAT = "ggvgl"                    # GOG screenshot formatter: large
PREFIX = "gog-"                          # game ids: never clash with itch / Epic ids
MAX_PAGES = 100


class GogError(Exception):
    """Short, player-safe reason; details are in the log."""


def auth_file():
    return paths.DATA / "gog" / "auth.json"


def user_file():
    return paths.DATA / "gog" / "user.json"


def gogdl_home():
    """gogdl's own config folder (GOGDL_CONFIG_PATH -> <this>/heroic_gogdl): manifests, excludes."""
    return paths.DATA / "gog" / "heroic_gogdl"


def manifest_file(app_name):
    """gogdl's record of the files of an installed Windows build (Linux builds keep theirs
    inside the game folder). A leftover one would make a reinstall skip files, so it goes with
    the game."""
    return gogdl_home() / "manifests" / str(app_name)


def redist_dir():
    """GOG's shared Windows parts (Visual C++, DirectX, GOG's setup tool), one copy for every
    game (gogdl redist). Its .gogdl-redist-manifest holds GOG's dependency list."""
    return paths.DATA / "gog" / "redist"


ISI_ARGS = ["/VERYSILENT", "/DIR={dir}", "/Language=English", "/LANG=english",
            "/ProductId={id}", "/galaxyclient", "/buildId={build}", "/versionName={version}",
            "/nodesktopshorctut", "/nodesktopshortcut"]   # (sic: both spellings, like Heroic)


def helper_cmd():
    """How to start the vendored gogdl: our own binary in its hidden mode (frozen build), or
    run.py from the source tree."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--gogdl"]
    run = Path(__file__).resolve().parents[2] / "run.py"
    return [sys.executable, str(run), "--gogdl"]


def code_from_text(text):
    """The sign-in code out of what the phone pasted: the on_login_success address (or any
    text with code=…), or just the code. None if there's nothing like it."""
    text = (text or "").strip()
    m = re.search(r"[?&#]code=([A-Za-z0-9_\-]{20,})", text)
    if m:
        return m.group(1)
    words = re.findall(r"[A-Za-z0-9_\-]{40,}", text)
    return words[0] if len(words) == 1 and text == words[0] else None


def _https(url):
    url = (url or "").strip()
    return ("https:" + url) if url.startswith("//") else url or None


def game_from_json(p):
    """One getFilteredProducts entry -> a library game dict; None for non-games / broken."""
    if not isinstance(p, dict) or not p.get("id") or not p.get("title"):
        return None
    if p.get("isGame") is False:
        return None
    works = p.get("worksOn") or {}
    plats = [k for k, v in (("linux", "Linux"), ("windows", "Windows")) if works.get(v)]
    img = _https(p.get("image"))
    return {
        "id": PREFIX + str(p["id"]),
        "title": str(p["title"]).strip(),
        "author": "",
        "cover_url": (img + COVER_SUFFIX) if img else None,
        "url": None,                                 # no itch page to read
        "short_text": "",
        "platforms": plats or ["other"],
        "store": "gog",
        "app_name": str(p["id"]),                    # GOG product id
        "category": (p.get("category") or "").strip(),
    }


def page_from_json(d):
    """api.gog.com/products/<id> -> (paragraphs, screenshot urls)."""
    from .steam import html_paras
    desc = (d or {}).get("description") or {}
    paras = html_paras(desc.get("full") or desc.get("lead") or "")
    shots = []
    for s in (d or {}).get("screenshots") or []:
        tpl = (s or {}).get("formatter_template_url") or ""
        if "{formatter}" in tpl:
            shots.append(_https(tpl.replace("{formatter}", SHOT_FORMAT)))
        elif (s or {}).get("image_id"):
            shots.append(f"https://images.gog-statics.com/{s['image_id']}_{SHOT_FORMAT}.jpg")
    return paras, shots


def pad_from_json(d):
    """Any "features" list in GOG's store data (v2 games: _embedded.features [{id, name}];
    catalog: [{slug, name}]) -> True if one of them is controller support, False if none is;
    None when there's no feature list at all."""
    lists = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "features" and isinstance(v, list):
                    lists.append(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    if not lists:
        return None
    for f in (f for lst in lists for f in lst):
        words = " ".join(str(f.get(k) or "") for k in ("id", "slug", "name")) \
            if isinstance(f, dict) else str(f)
        if "controller" in words.lower():
            return True
    return False


class GogStore:
    name = "gog"

    def ready(self):
        """Nothing to download for signing in (step 2 brings gogdl for installs)."""
        return True

    def connected(self):
        return bool(self._creds())

    def user(self):
        try:
            return json.loads(user_file().read_text()).get("username") or "GOG"
        except (OSError, ValueError, AttributeError):
            return None

    def _creds(self):
        try:
            c = json.loads(auth_file().read_text()).get(CLIENT_ID)
            return c if isinstance(c, dict) and c.get("refresh_token") else None
        except (OSError, ValueError, AttributeError):
            return None

    def _ask(self, **params):
        """One auth.gog.com/token call -> its JSON. False when GOG refused (bad / used / old
        code or refresh token); raises GogError when GOG can't be reached."""
        q = urllib.parse.urlencode({"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                                    **params})
        try:
            data = json.loads(net.get(TOKEN_URL + "?" + q, timeout=30))
        except net.NotFound:
            return False
        except net.Offline as e:
            if str(e).startswith("HTTP 4"):          # 400 / 401: GOG said no
                log.info("gog: token %s refused (%s)", params.get("grant_type"), e)
                return False
            log.warning("gog: token %s: %s", params.get("grant_type"), e)
            raise GogError("Couldn't reach GOG") from None
        except ValueError:
            raise GogError("Couldn't reach GOG") from None
        if not isinstance(data, dict) or not data.get("access_token"):
            log.info("gog: token %s: no token in the answer", params.get("grant_type"))
            return False
        data["loginTime"] = time.time()
        return data

    def _save(self, data):
        """gogdl's own auth file format ({client_id: token data}), so step 2's gogdl uses it."""
        d = auth_file().parent
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)                           # holds the GOG sign-in
        tmp = auth_file().with_name("auth.json.tmp")
        tmp.write_text(json.dumps({CLIENT_ID: data}))
        os.chmod(tmp, 0o600)
        os.replace(tmp, auth_file())

    def login(self, code):
        """True when GOG accepted the code. Raises GogError when GOG can't be reached."""
        data = self._ask(grant_type="authorization_code", code=code, redirect_uri=REDIRECT)
        if not data:
            log.info("gog: code rejected")
            return False
        self._save(data)
        self._save_user(data["access_token"])
        log.info("gog: signed in")
        return True

    def _save_user(self, token):
        try:
            u = net.get_json(USER_URL, key=token)
            name = u.get("username") or "GOG"
        except Exception as e:  # noqa: BLE001  - the name is a nicety
            log.info("gog: user name unknown (%s)", e)
            name = "GOG"
        tmp = user_file().with_name("user.json.tmp")
        tmp.write_text(json.dumps({"username": name}))
        os.replace(tmp, user_file())

    def token(self):
        """A working access token, refreshed when it's about to run out. Raises GogError."""
        c = self._creds()
        if not c:
            raise GogError("Not signed in")
        if time.time() < c.get("loginTime", 0) + c.get("expires_in", 0) - 60:
            return c["access_token"]
        data = self._ask(grant_type="refresh_token", refresh_token=c["refresh_token"])
        if not data:
            raise GogError("Signed out of GOG")
        data.setdefault("refresh_token", c["refresh_token"])
        self._save(data)
        return data["access_token"]

    def logout(self):
        """Forget the sign-in (GOG has no sign-out call for this kind of token)."""
        auth_file().unlink(missing_ok=True)
        user_file().unlink(missing_ok=True)

    def sync(self):
        """All owned GOG games. Needs the network; raises GogError."""
        tok = self.token()
        games, page, pages = {}, 1, 1
        try:
            while page <= min(pages, MAX_PAGES):
                d = net.get_json(LIST_URL.format(page), key=tok, timeout=30)
                pages = int(d.get("totalPages") or 1)
                for p in d.get("products") or []:
                    g = game_from_json(p)
                    if g:
                        games[g["id"]] = g
                page += 1
                time.sleep(0.2)
        except net.AuthError as e:
            log.warning("gog sync: token refused (%s)", e)
            raise GogError("Signed out of GOG") from None
        except (net.Offline, net.NotFound, ValueError, TypeError, AttributeError) as e:
            log.warning("gog sync: %s", e)
            raise GogError("Couldn't reach GOG") from None
        log.info("gog sync: %d games (%d pages)", len(games), pages)
        return list(games.values())

    def details(self, app_name):
        """(paragraphs, screenshot urls) for a game page. Public API, no sign-in needed."""
        return page_from_json(net.get_json(PRODUCT_URL.format(app_name), timeout=25))

    def controller(self, app_name):
        """GOG's "Controller support" feature: True / False, or None when GOG's store data
        has no feature list (or can't be read). Public API, no sign-in needed."""
        try:
            return pad_from_json(net.get_json(GAME_URL.format(app_name), timeout=25))
        except net.Offline:
            raise
        except Exception as e:  # noqa: BLE001  - a bonus: never fail the page
            log.info("gog: features of %s: %s", app_name, e)
            return None

    # --- step 2: install / play / uninstall (v0.9.2) ---------------------------------
    def platforms_for(self, g):
        """Builds to try, best first: Linux when GOG has one, else Windows (through Proton)."""
        have = set(g.get("platforms") or [])
        return [p for p in ("linux", "windows") if p in have]

    def _env(self):
        from ..runner import child_env               # never hand our bundled libs on
        return dict(child_env(), GOGDL_CONFIG_PATH=str(gogdl_home().parent),
                    PYTHONUNBUFFERED="1", PYINSTALLER_RESET_ENVIRONMENT="1")

    def _cmd(self, *args):
        return [*helper_cmd(), "--auth-config-path", str(auth_file()), *args]

    def _prepare(self, app_name):
        """A fresh token in auth.json (gogdl refreshes too, but our refresh says *why* it fails)
        and gogdl's exclude file, which its downloaders open without checking it exists."""
        self.token()
        ex = gogdl_home() / "exclude" / str(app_name)
        ex.parent.mkdir(parents=True, exist_ok=True)
        if not ex.exists():
            ex.write_text("")

    def info(self, app_name, platform):
        """gogdl info: {"need": bytes on disk or 0, "build": build id, "version": name}.
        None when GOG has no such build. Raises GogError."""
        self._prepare(app_name)
        try:
            r = subprocess.run(self._cmd("info", str(app_name), "--platform", platform,
                                         "--lang", "en-US", "--skip-dlcs"),
                               capture_output=True, text=True, timeout=180, env=self._env(),
                               stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise GogError("Couldn't reach GOG") from None
        except OSError as e:
            log.warning("gog: can't start gogdl: %s", e)
            raise GogError("Couldn't start the GOG helper") from None
        data = None
        for line in reversed((r.stdout or "").splitlines()):
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                except ValueError:
                    pass
                break
        if r.returncode != 0 or not isinstance(data, dict):
            tail = (r.stderr or "").strip().splitlines()[-6:]
            log.info("gog: info %s %s -> %s\n  %s", app_name, platform, r.returncode,
                     "\n  ".join(tail))
            _raise_for("\n".join(tail), none_ok=True)
            return None
        return {"need": _disk_size(data), "build": data.get("buildId"),
                "version": data.get("versionName"), "folder": data.get("folder_name"),
                "deps": [str(d) for d in data.get("dependencies") or []]}

    def redist(self, ids, cancel=None, log_file=None):
        """Download GOG's shared Windows parts for these dependency ids into redist_dir(). gogdl
        replaces that folder's contents with exactly the ids it's given, so every id ever asked
        for is passed (redist_ids.json). Returns GOG's dependency list (depots) or {}."""
        known_f = paths.DATA / "gog" / "redist_ids.json"
        try:
            known = set(json.loads(known_f.read_text()))
        except (OSError, ValueError, TypeError):
            known = set()
        want = sorted(known | set(ids))
        d = redist_dir()
        d.mkdir(parents=True, exist_ok=True)
        if want:
            self._prepare("redist")
            self._stream(self._cmd("redist", "--ids", ",".join(want), "--path", str(d)), cancel,
                         log_file, None, "redist")
            known_f.write_text(json.dumps(want))
        try:
            return json.loads((d / ".gogdl-redist-manifest").read_text())
        except (OSError, ValueError):
            return {}

    def install(self, app_name, platform, folder, on_progress=None, cancel=None, log_file=None,
                fresh=True):
        """Download the build straight into folder (gogdl `update`: no extra folder level). An
        interrupted one resumes (gogdl's .gogdl-resume in folder). fresh: forget an old manifest
        first, so nothing counts as already there. on_progress(frac, mb_s, eta_s); cancel() ->
        True stops (raises Cancelled). Returns launch_info(folder, …). Raises GogError."""
        self._prepare(app_name)
        if log_file:
            open(log_file, "w").close()               # one install = one log
        if fresh and not (Path(folder) / ".gogdl-resume").exists():
            manifest_file(app_name).unlink(missing_ok=True)
        cmd = self._cmd("update", str(app_name), "--platform", platform, "--path", str(folder),
                        "--lang", "en-US", "--skip-dlcs")
        self._stream(cmd, cancel, log_file, on_progress, f"install {app_name} ({platform})")
        return launch_info(folder, app_name, platform)

    def _stream(self, cmd, cancel, log_file, on_progress, what):
        """Run gogdl, feed its progress lines to on_progress, stop it on cancel (Cancelled),
        raise a short GogError when it fails."""
        from ..net import Cancelled
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 bufsize=1, env=self._env(), stdin=subprocess.DEVNULL,
                                 start_new_session=True)
        except OSError as e:
            log.warning("gog: can't start gogdl: %s", e)
            raise GogError("Couldn't start the GOG helper") from None
        tail, speed = [], 0.0
        out = open(log_file, "a") if log_file else None
        stopper = None
        try:
            if cancel:                                # cancel even while gogdl is quiet
                import threading
                stopper = threading.Event()

                def watch():
                    while not stopper.wait(0.5):
                        if cancel() and p.poll() is None:
                            _stop(p)
                            return
                threading.Thread(target=watch, daemon=True, name="gog-cancel").start()
            for line in p.stdout:
                if out:
                    out.write(line)
                tail = (tail + [line.rstrip()])[-25:]
                m = PROGRESS.search(line)
                if m and on_progress:
                    h, mi, s_ = (int(x) for x in m.group(2, 3, 4))
                    on_progress(float(m.group(1)) / 100, speed, h * 3600 + mi * 60 + s_)
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
        text = "\n".join(tail)
        if p.returncode != 0 or "Traceback (most recent call last)" in text:
            log.info("gog: %s -> %s\n  %s", what, p.returncode, "\n  ".join(tail[-8:]))
            _raise_for(text)

    def forget(self, app_name):
        """The game was uninstalled: drop gogdl's manifest so a reinstall downloads everything."""
        manifest_file(app_name).unlink(missing_ok=True)


PROGRESS = re.compile(r"= Progress: ([\d.]+) \d+/\d+.*?ETA: (\d+):(\d+):(\d+)")
SPEED = re.compile(r"\+ Download\s*-\s*([\d.]+) MiB/s")
NO_PLAY = "no play task"        # InstallError text for code I06


def _raise_for(text, none_ok=False):
    """gogdl's last lines -> a short GogError (none_ok: return quietly when nothing matched)."""
    low = text.lower()
    if "disk space" in low:
        raise GogError("Not enough space")
    if "401" in low or "unauthorized" in low or "failed to refresh credentials" in low:
        raise GogError("Signed out of GOG")
    if any(w in low for w in ("connectionerror", "max retries", "name resolution",
                              "failed to reach", "timed out", "read timed out")):
        raise GogError("Couldn't reach GOG")
    if not none_ok:
        raise GogError("Couldn't install")


def _disk_size(data):
    """Bytes on disk from gogdl info: Linux = disk_size; Windows = the shared files ("*") plus
    the English ones."""
    if isinstance(data.get("disk_size"), (int, float)):   # Linux (disk_size can be 0 there)
        return int(max(data["disk_size"], data.get("download_size") or 0))
    size = data.get("size") or {}
    total = 0
    for k in ("*", "en-US"):
        v = size.get(k) if isinstance(size, dict) else None
        if isinstance(v, dict):
            total += int(v.get("disk_size") or 0)
    return total


def _ci(root, rel):
    """root/rel, matching each part case-insensitively (GOG's paths come from Windows)."""
    cur = Path(root)
    for part in [x for x in rel.replace("\\", "/").split("/") if x and x != "."]:
        nxt = cur / part
        if not nxt.exists() and cur.is_dir():
            low = part.lower()
            nxt = next((c for c in cur.iterdir() if c.name.lower() == low), nxt)
        cur = nxt
    return cur


def launch_info(folder, app_name, platform):
    """How to start an installed GOG game, relative to folder:
    {"exe", "args", "cwd", "setup"}. Linux builds: start.sh (GOG's own launcher script).
    Windows: the primary play task of goggame-<id>.info (path, arguments, workingDir; the game
    root when no workingDir, like gogdl/Heroic). "setup": the game ships first-run setup
    scripts (goggame-*.script) that SCRiTCH doesn't run yet (error code P03 if it then fails).
    Raises GogError(NO_PLAY) when there's nothing to start."""
    folder = Path(folder)
    if platform == "linux":
        sh = folder / "start.sh"
        if not sh.is_file():
            raise GogError(NO_PLAY)
        try:
            sh.chmod(sh.stat().st_mode | 0o111)
        except OSError:
            pass
        return {"exe": "start.sh", "args": [], "cwd": "", "setup": False}
    infos = sorted(folder.glob("goggame-*.info"), key=lambda f: f.name != f"goggame-{app_name}.info")
    tasks = []
    for f in infos:
        try:
            tasks = json.loads(f.read_text(encoding="utf-8-sig")).get("playTasks") or []
        except (OSError, ValueError, AttributeError):
            tasks = []
        if tasks:
            break
    files = [t for t in tasks if isinstance(t, dict) and t.get("path")
             and t.get("type", "FileTask") == "FileTask"]
    task = next((t for t in files if t.get("isPrimary")), files[0] if files else None)
    if not task:
        raise GogError(NO_PLAY)
    exe = _ci(folder, task["path"])
    if not exe.is_file():
        raise GogError(NO_PLAY)
    args = task.get("arguments") or []
    if isinstance(args, str):                     # gogdl does the same with a string
        try:
            args = shlex.split(args.replace("\\", "/"))
        except ValueError:
            args = args.split()
    cwd = _ci(folder, task.get("workingDir") or "")
    return {"exe": exe.relative_to(folder).as_posix(), "args": [str(a) for a in args],
            "cwd": cwd.relative_to(folder).as_posix() if cwd.is_dir() else "",
            "setup": any(folder.glob("goggame-*.script"))}


def setup_steps(folder, app_name, deps, repo, build=None, version=None):
    """GOG's first-run setup for a Windows build, as SCRiTCH will run it on the first Play:
    [{"name", "base": "redist"|"game", "path", "args"}] (paths relative, so Move doesn't break
    them). deps = the game's dependency ids (gogdl info); repo = GOG's dependency list
    (redist()). GOG's setup tool (ISI) runs last when the game ships goggame-*.script files."""
    depots = {d.get("dependencyId"): d for d in (repo or {}).get("depots") or []
              if isinstance(d, dict)}
    steps = []
    for dep in deps or []:
        exe = (depots.get(dep) or {}).get("executable") or {}
        path = (exe.get("path") or "").replace("\\", "/")
        if not path:
            continue
        try:
            args = shlex.split(exe.get("arguments") or "")
        except ValueError:
            args = (exe.get("arguments") or "").split()
        steps.append({"name": dep, "base": "redist" if path.startswith("__redist") else "game",
                      "path": path, "args": args})
    if any(Path(folder).glob("goggame-*.script")):
        isi = (depots.get("ISI") or {}).get("executable") or {}
        steps.append({"name": "ISI", "base": "redist",
                      "path": (isi.get("path") or "__redist/ISI/scriptinterpreter.exe").replace("\\", "/"),
                      "args": [a.format(dir="{dir}", id=app_name, build=build or "",
                                        version=version or "") for a in ISI_ARGS]})
    return steps


def step_exe(step, folder):
    """Where a setup step's program is (case-insensitive; redist files may sit with or without
    the __redist folder level). None if it isn't there."""
    bases = [redist_dir()] if step["base"] == "redist" else [Path(folder)]
    rels = [step["path"]]
    if step["path"].startswith("__redist/"):
        rels.append(step["path"][len("__redist/"):])
    for b in bases:
        for r in rels:
            p = _ci(b, r)
            if p.is_file():
                return p
    return None


def windows_path(p):
    return "Z:" + str(p).replace("/", "\\")


OK_CODES = (0, 1638, 3010, 1641)      # 1638 already installed, 3010/1641 = reboot wanted


def run_setup(steps, folder, umu, env, log_file, timeout=900):
    """Run each step through umu in the game's prefix, quietly. Returns the names that failed
    (missing file, error exit, too slow); the game is started anyway."""
    from ..runner import child_env
    failed = []
    with open(log_file, "a") as out:
        for st in steps:
            exe = step_exe(st, folder)
            if exe is None:
                out.write(f"# {st['name']}: {st['path']} not found\n")
                failed.append(st["name"])
                continue
            args = [a.replace("{dir}", windows_path(folder)) for a in st["args"]]
            out.write(f"# {st['name']}: {exe} {' '.join(args)}\n")
            out.flush()
            try:
                r = subprocess.run([str(umu), str(exe), *args], cwd=str(exe.parent),
                                   env=dict(child_env(), **env), stdout=out,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   timeout=timeout, start_new_session=True)
                rc = r.returncode
            except (OSError, subprocess.TimeoutExpired) as e:
                rc = f"{type(e).__name__}"
            out.write(f"# {st['name']}: exit {rc}\n")
            if rc not in OK_CODES:
                failed.append(st["name"])
    return failed


def _stop(p):
    """Stop gogdl and its download workers (own process group); it keeps a resume file."""
    import signal
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(10)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass


if __name__ == "__main__":     # live check (CI, .github/workflows/stores-live.yml): ids -> pad?
    import sys as _sys
    logging.basicConfig(level=logging.INFO)
    for _id in _sys.argv[1:]:
        _raw = net.get_json(GAME_URL.format(_id), timeout=25)
        print(_id, "controller:", pad_from_json(_raw), "features:",
              json.dumps((_raw.get("_embedded") or {}).get("features"))[:400])
