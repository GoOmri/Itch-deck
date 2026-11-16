"""GOG through gogdl (Heroic's GOG helper, GPL-3).

Step 1 (v0.9.0, this file): sign in + a read-only library tab. Step 2 adds install / play.

- gogdl is downloaded on demand (first Sign in to GOG), never bundled: the release asset
  gogdl_linux_x86_64 of Heroic-Games-Launcher/heroic-gogdl, saved as DATA/gog/gogdl.
- gogdl keeps the sign-in in OUR file (DATA/gog/auth.json, --auth-config-path), never Heroic's.
  `gogdl auth --code C` signs in; `gogdl auth` prints a working token (refreshes it when old).
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
import subprocess
import time

from .. import net, paths

log = logging.getLogger("scritch")

LATEST = "https://api.github.com/repos/Heroic-Games-Launcher/heroic-gogdl/releases/latest"
ASSET = "gogdl_linux_x86_64"
CLIENT_ID = "46899977096215655"          # GOG Galaxy's public client id (what gogdl uses)
REDIRECT = "https://embed.gog.com/on_login_success?origin=client"
LOGIN_URL = ("https://auth.gog.com/auth?client_id=" + CLIENT_ID +
             "&redirect_uri=https%3A%2F%2Fembed.gog.com%2Fon_login_success%3Forigin%3Dclient"
             "&response_type=code&layout=galaxy")
LIST_URL = "https://embed.gog.com/account/getFilteredProducts?mediaType=1&sortBy=title&page={}"
USER_URL = "https://embed.gog.com/userData.json"
PRODUCT_URL = "https://api.gog.com/products/{}?expand=description,screenshots"
COVER_SUFFIX = "_392.jpg"                # GOG image formatter: landscape product tile
SHOT_FORMAT = "ggvgl"                    # GOG screenshot formatter: large
PREFIX = "gog-"                          # game ids: never clash with itch / Epic ids
MAX_PAGES = 100


class GogError(Exception):
    """Short, player-safe reason; details are in the log."""


def bin_path():
    return paths.DATA / "gog" / "gogdl"


def auth_file():
    return paths.DATA / "gog" / "auth.json"


def user_file():
    return paths.DATA / "gog" / "user.json"


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


def fetch_gogdl(cancel=None, on_bytes=None):
    """One-time download of gogdl (a single Linux program, ~15 MB)."""
    dest = bin_path()
    try:
        rel = net.get_json(LATEST)
        asset = next((a for a in rel.get("assets") or [] if a.get("name") == ASSET), None)
        if not asset:
            log.warning("gog: no %s in gogdl %s (%s)", ASSET, rel.get("tag_name"),
                        [a.get("name") for a in rel.get("assets") or []])
            raise GogError("Couldn't get the GOG helper")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name("gogdl.new")
        net.download(asset["browser_download_url"], tmp, cancel=cancel, on_bytes=on_bytes)
        if tmp.stat().st_size < 1_000_000:
            raise GogError("Couldn't get the GOG helper")
        os.chmod(tmp, 0o755)
        os.replace(tmp, dest)
        log.info("gog: gogdl %s installed", rel.get("tag_name"))
    except (net.Offline, net.NotFound, net.AuthError) as e:
        log.warning("gog: gogdl download failed: %s", e)
        raise GogError("No internet") from None


class GogStore:
    name = "gog"

    def ready(self):
        b = bin_path()
        return b.is_file() and os.access(b, os.X_OK)

    def connected(self):
        try:
            return bool(json.loads(auth_file().read_text()).get(CLIENT_ID))
        except (OSError, ValueError, AttributeError):
            return False

    def user(self):
        try:
            return json.loads(user_file().read_text()).get("username") or "GOG"
        except (OSError, ValueError, AttributeError):
            return None

    def _run(self, args, timeout):
        from ..runner import child_env               # never hand our bundled libs to gogdl
        d = auth_file().parent
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)                           # holds the GOG sign-in
        cmd = [str(bin_path()), "--auth-config-path", str(auth_file()), *args]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               env=child_env(), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            log.warning("gog: gogdl %s timed out", args[0])
            raise GogError("GOG didn't answer") from None
        except OSError as e:
            log.warning("gog: can't run gogdl: %s", e)
            raise GogError("Couldn't start the GOG helper") from None
        tail = (r.stderr or "").strip().splitlines()[-6:]
        log.info("gog: gogdl %s -> %s%s", args[0], r.returncode,
                 ("\n  " + "\n  ".join(tail)) if tail else "")
        return r

    @staticmethod
    def _json(r):
        try:
            return json.loads((r.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return None

    def login(self, code):
        """True when GOG accepted the code. Raises GogError when GOG can't be reached."""
        auth_file().unlink(missing_ok=True)
        user_file().unlink(missing_ok=True)
        r = self._run(["auth", "--code", code], timeout=60)
        data = self._json(r)
        if not isinstance(data, dict) or not data.get("access_token"):
            if "failed to reach" in (r.stderr or "").lower():
                raise GogError("Couldn't reach GOG")
            log.info("gog: code rejected")
            return False
        os.chmod(auth_file(), 0o600)
        self._save_user(data["access_token"])
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
        """A working access token (gogdl refreshes it when old). Raises GogError."""
        if not self.connected():
            raise GogError("Not signed in")
        data = self._json(self._run(["auth"], timeout=30))
        if isinstance(data, dict) and data.get("access_token"):
            return data["access_token"]
        raise GogError("Couldn't reach GOG")

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
