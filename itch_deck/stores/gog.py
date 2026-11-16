"""GOG through gogdl (Heroic's GOG helper, GPL-3).

Step 1 (v0.9.x, this file): sign in + a read-only library tab. Step 2 adds install / play.

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
import time
import urllib.parse

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
