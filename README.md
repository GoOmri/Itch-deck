<h1><picture>
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-on-light.svg">
  <img src="itch_deck/assets/logo.svg" alt="SCRiTCH" height="56">
</picture></h1>

A controller-first launcher for your **itch.io** library on the **Steam Deck**. It shows up as one
Steam tile in Game Mode. From there you can browse the games you own, install them, play and
uninstall, all with the pad. Windows games run through GE-Proton automatically.

- Your whole itch library, plus free games you added to your itch **collections**
- Game pages with the full description, screenshots and comments (cached for offline use)
- One-button installs: download, unpack, done. Windows installers (Inno Setup, NSIS) run silently
- Linux games run natively, Windows games run through umu-launcher + GE-Proton (one prefix per
  game, so your saves survive an uninstall)
- **Mouse and Keys modes** for games that ignore the pad: the pad becomes a mouse (and keyboard)
- **Game updates:** a newer build on itch shows *Update* on the tile; Options → Update gets it
- **Button symbols** follow your controller (Steam Deck, DualSense, Xbox)
- Installs to the SD card by default, and updates itself from Settings

It's a single Linux binary (Python + pygame-ce, built with PyInstaller). Nothing gets installed on
the Deck's system, and you never need a terminal.

## Setup (about 10 minutes, once)

You need a Steam Deck (or another SteamOS / Linux PC) and an itch.io account.

### 1. Get the app
1. Switch to **Desktop Mode**. Open the
   [latest release](https://github.com/GoOmri/Itch-deck/releases/latest) in Firefox and
   download `scritch`.
2. In Dolphin, make the folder `~/Applications/scritch/` and move the file into it.
3. Right-click the file → **Properties → Permissions** → tick **Is executable**.

### 2. Add it to Steam
1. Steam → **Games → Add a Non-Steam Game to My Library → Browse**, then pick
   `~/Applications/scritch/scritch`.
2. In the tile's **Properties**, rename it (for example *SCRiTCH*). Leave **Compatibility**
   off, because it's a native Linux app.
3. Back in Game Mode: tile → controller icon → pick the **Gamepad** template.

That's the only Desktop Mode step. Everything below happens in Game Mode.

### 3. Connect itch with your phone
1. Open scritch. The Setup screen shows a **QR code**.
2. Scan it with your phone (same Wi-Fi as the Deck). A small page from your Deck opens.
3. Tap **Open itch API keys** → **Generate new API key** → copy it.
4. Back on that page, paste it and tap **Send**. The TV says *Connected as …* and your library
   syncs.

The page only works while the QR code is on screen, the QR carries a one-time password, and it
expires after 5 minutes (a new QR appears). Use it on your home Wi-Fi only: the page is plain
HTTP on your local network.

No phone, or the page won't open (some routers block devices from reaching each other)? Use
**Import file**: save the key as `itch_key.txt` and send it to the Deck's `~/Downloads` with
Warpinator. Or **Type key**, with Steam + X for the on-screen keyboard.

The key is stored only in `~/.config/scritch/config.json`, which only your user can read.
Settings → **Disconnect itch** makes scritch forget it; to revoke it as well, delete it on itch.io
→ Settings → API keys.

### Epic Games (optional, early)
Settings → Account → **Epic Games** → A shows a QR code. Scan it, tap **Open Epic sign-in**, sign
in, then copy the page of text Epic shows, paste it and tap Send. Your Epic library becomes its
own tab (All · Installed · itch · Epic). The code on that page works once and only for a few
minutes, so do it in one go. SCRiTCH downloads the small open-source Epic helper
([legendary](https://github.com/legendary-gl/legendary)) the first time and keeps its own Epic
sign-in, separate from Heroic. Epic games install and play like itch Windows games (GE-Proton,
saves kept on uninstall). Not yet: Epic game updates, DLC, cloud saves. Games with anti-cheat or
online-only Epic features won't run (same as in Heroic).

### 4. GE-Proton (for Windows games)
Nothing to do: the first time you install a Windows game, scritch downloads the newest
**GE-Proton** (about 0.5 GB, once) into Steam's compatibility tools folder, where Steam and
ProtonUp-Qt see it too. To get it ahead of time: Settings → **Proton version**. Already have
GE-Proton from ProtonUp-Qt? scritch uses it.

## Using it

| Button | Library | Game page | Settings |
|---|---|---|---|
| D-pad / left stick | Move | Move | Move |
| A | Open game | Press the focused button | Change the focused setting |
| B | Quit | Back | Back |
| X / L1 / R1 | Switch tabs | Previous / next game (L1/R1) | — |
| Y | Refresh library | — | — |
| L2 / R2 | Page up / down | — | — |
| Start (☰) | Settings | Options | Back |

- **Sort & filter (X in the library):** sort A–Z, by date added, or *Shortest first*; filter by
  Genre or Length (Under 2 h / 2–10 h / 10 h+). Lengths come from
  [HowLongToBeat](https://howlongtobeat.com), looked up in the background and refreshed monthly.
  Games HLTB doesn't know (many small itch games) show no time rather than a wrong one.
- **Installing:** press Install. The download runs in the background (one at a time) and resumes
  if you quit. Then the button turns into **Play**.
- **Change build:** some games have several downloads (Linux, Windows, 32/64-bit, demos). Options
  → Change build lets you pick another one. If a Linux build won't start, try the Windows build.
- **Controls:** Options → Controls switches between *Auto*, *Pad*, *Mouse* and *Keys*. *Auto*
  reads the game's itch page: a controller listed → Pad, a keyboard → Keys, only mouse or
  touchscreen → Mouse. In **Mouse** mode the right stick moves the pointer and R2 / A
  left-clicks. L2 / X right-clicks, the left stick scrolls, and B / Start is Esc. In **Keys**
  mode the D-pad and left stick are the arrow keys, A = Space, B = Esc, X = Z, Y = X,
  Menu = Enter, L1 = R, R1 = Shift, and the right stick + R2 / L2 still work as a mouse.
- **Updates:** SCRiTCH checks itch for newer builds of installed games. The tile shows *Update*,
  and Options → Update installs it; if that fails, the old build stays.
- **Quitting a game:** use the game's own Quit, or **hold View + Menu (DualSense: Create +
  Options) for 2 seconds**: scritch closes the game and everything it started, and comes back.
  Handy for games that ignore the controller. Steam → *Exit game* also works, but it closes
  scritch too, because Steam ends the whole tile.

### Settings
- **Install location:** SD card or internal storage. This only applies to new installs;
  installed games stay where they are. If the SD card is out, installs say "SD card missing".
- **Saves of uninstalled games:** Windows games keep their saves after an uninstall, so a
  reinstall picks them up again. This row shows how much space those saves take, and A deletes
  them.
- **Proton version:** *Auto* (newest GE-Proton) or a fixed version.
- **Pointer speed:** slow / normal / fast, for Mouse and Keys mode.
- **Button symbols:** *Auto* follows the controller you pressed last; or fix it to Steam Deck,
  PlayStation or Xbox.
- **Update app:** checks GitHub for a new version, downloads it and restarts. The previous
  version is kept as `scritch.old` next to the app, in case you need to go back: rename it
  back to `scritch` in Dolphin.

## When something goes wrong

| You see | Try |
|---|---|
| "Can't reach itch.io" | Check Wi-Fi. Games you've installed still play offline. |
| "Key rejected" | Make a new API key and send it again (Settings → Re-import API key). |
| The QR page won't open on the phone | Same Wi-Fi? Some routers isolate devices: use Import file or Type key. |
| "SD card missing" | Put the card back. scritch notices within a couple of seconds. |
| "Couldn't download GE-Proton" | Check Wi-Fi and press Retry; the download resumes. |
| "…can't run silently" | The installer type isn't supported. Try Options → Change build. |
| A game closes right after starting | Try Change build (Windows instead of Linux, or 64-bit). |
| "needs a newer GE-Proton" | Settings → Proton version → pick the newest (or Auto). |
| A game's controls do nothing | It may need a mouse or keyboard: Options → Controls → Mouse or Keys. To get out: hold View + Menu for 2 s. |

**Logs** (open them in Dolphin; turn on *Show hidden files*):
- `~/.local/state/scritch/logs/app.log`: what scritch did
- `~/.local/state/scritch/logs/games/<game>.log`: the game's own output from its last run,
  including the exact command line
- `~/.local/state/scritch/logs/games/<game>-install.log`: the output of a Windows installer

## Where things live

```
~/Applications/scritch/scritch          the file Steam starts (unpacks the app once per version)
~/Applications/scritch/app/             the app itself (app.old/ = the version before)
~/.config/scritch/config.json           settings + API key
~/.local/share/scritch/                 library cache, covers, game pages, times to beat, umu-launcher
~/.local/share/scritch/epic/            the Epic helper (legendary) and your Epic sign-in
~/.local/state/scritch/logs/            logs
<SD card>/scritch/<game>/               installed games (or ~/Games/scritch/ on internal storage)
<SD card>/scritch/_prefixes/<game>/     Windows saves (Proton prefixes)
```
Used it before v0.8.2? Your folders were called `itch-deck`: the first start of v0.8.2 renames
them to `scritch` and leaves an `itch-deck` link behind. The app folder you added to Steam and
the games folder (`itch`) stay where they are.

## Known limits
- **Browser (HTML5) games** are listed and tagged, but they can't be played from scritch yet.
- **Paid games in collections** are only listed if you own them. Free ones are added.
- Some Linux builds need libraries SteamOS doesn't ship (for example `libwebkit2gtk`). They stop
  straight away. Use the Windows build instead.
- All games share the tile's Steam Input layout. Keyboard-only games need a custom layout, or the
  Deck's touchscreen.

## For developers
```
pip install -r requirements.txt pytest
python -m pytest -q tests          # unit tests (itch API from fixtures, installer, mouse mode)
python run.py --selftest           # headless run through every screen with fake data
python run.py --windowed           # run it on a desktop (keyboard: arrows, Enter, Esc, x, y, m)
python run.py --render-mockups out # PNGs of every screen
sh packaging/build.sh              # release/scritch: folder build packed behind a launcher
```
Every push to `main` builds the binary on GitHub Actions (Ubuntu 22.04) and publishes a release
named after `VERSION` in `itch_deck/app.py`. Read `NOTES.md` (working notes and decisions) and
`DESIGN.md` (UI rules) before changing things.

## Licence
scritch is free software under the **GNU General Public License v3.0** (see `LICENSE`). You may
use, change and share it; versions you share must stay under the GPL with their source code.
It carries a copy of [gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) (GPL-3, Heroic
Games Launcher) for GOG downloads: `itch_deck/vendor/`.
