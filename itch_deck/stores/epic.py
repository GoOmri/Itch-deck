"""Epic Games, step 1 (read-only): the library Heroic already knows.

Heroic runs legendary (the open-source Epic client) with its config under
<heroic config>/legendaryConfig/legendary. legendary keeps:
  user.json             the Epic sign-in (displayName); we never touch the tokens
  metadata/<app>.json   one file per owned game or DLC: app_name, app_title, asset_infos
                        (platform -> build), metadata (Epic catalog item: description,
                        developer, keyImages, mainGameItem for DLC, customAttributes)
Reading those files needs no network and can't disturb Heroic's sign-in. They are as fresh as
Heroic's last library refresh. Installing / playing Epic games is step 2 (legendary itself).

Epic decision (Omri 15 Nov): opt-in (tab only after Settings -> Epic -> Connect), isolated
(any Epic error stays here and is logged; itch never depends on it)."""
import json
import logging
from pathlib import Path

log = logging.getLogger("itch-deck")

# Heroic as a flatpak (SteamOS / Discover) first, then a native install
HEROIC_DIRS = (".var/app/com.heroicgameslauncher.hgl/config/heroic/legendaryConfig/legendary",
               ".config/heroic/legendaryConfig/legendary")
# landscape art first: tiles are wider than tall (DieselGameBoxTall is the portrait box)
COVER_TYPES = ("DieselGameBox", "OfferImageWide", "DieselStoreFrontWide", "Thumbnail",
               "DieselGameBoxTall")
PREFIX = "epic-"                         # game ids: never clash with itch's numeric ids


def legendary_dir(home=None):
    """Heroic's legendary folder with a signed-in user, or None."""
    home = Path(home or Path.home())
    for rel in HEROIC_DIRS:
        d = home / rel
        if (d / "user.json").is_file():
            return d
    return None


def user_name(d):
    try:
        u = json.loads((Path(d) / "user.json").read_text())
        return u.get("displayName") or u.get("display_name") or "Epic"
    except (OSError, ValueError):
        return None


def _cover(meta):
    imgs = {i.get("type"): i.get("url") for i in meta.get("keyImages") or [] if isinstance(i, dict)}
    return next((imgs[k] for k in COVER_TYPES if imgs.get(k)), None)


def game_from_file(data):
    """One metadata/<app>.json -> a library game dict (None for DLC and broken files)."""
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
        "platforms": sorted(plats) or ["other"],
        "store": "epic",
        "app_name": data["app_name"],
    }


class EpicStore:
    name = "epic"

    def __init__(self, home=None):
        self.home = home

    def connected(self):
        return legendary_dir(self.home) is not None

    def user(self):
        d = legendary_dir(self.home)
        return user_name(d) if d else None

    def sync(self):
        """All owned Epic games (DLC left out), sorted later with the rest of the library."""
        d = legendary_dir(self.home)
        if not d:
            raise FileNotFoundError("no Heroic Epic sign-in")
        games, bad = {}, 0
        for f in sorted((d / "metadata").glob("*.json")):
            try:
                g = game_from_file(json.loads(f.read_text()))
            except (OSError, ValueError):
                bad += 1
                continue
            if g:
                games[g["id"]] = g
        log.info("epic sync: %d games from %s%s", len(games), d, f" ({bad} unreadable)" if bad else "")
        return list(games.values())
