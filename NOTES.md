# itch-deck — working notes (read this first in a new chat)

Plan doc: https://claude.ai/artifact/3UHDDdBhbp2BFbKZwvqvRg

## Working on this repo (Omri, 14 Nov — several chats work on it in parallel)
- Start of every session: `git fetch origin` and `git pull --rebase origin main`. Read NOTES.md.
- Work on your own branch (e.g. `m4-proton`, `feel-pass`). Never commit straight to main.
- main = ready to ship. Merge to main only when the work is finished: first merge the latest
  origin/main into your branch, run `python -m pytest -q tests` and `python run.py --selftest`,
  then push. If a push is rejected, pull and merge again; never force-push main.
- Releases (bump VERSION in app.py + tag vX.Y.Z) are done by ONE chat at a time. Before tagging:
  check `git branch -r --no-merged origin/main` for finished branches and ask Omri whether to
  include them.
- UI must follow the "Design pass" rules below: W.button (grey, focus lights up, accent=True only for the page's main action: Install/Play/Update),
  W.tag for labels, 5 theme font sizes, purple only for progress/state, t.dim for readable grey,
  app name = W.APP_NAME ("scritch").
- Write what you changed in NOTES.md before pushing, so the next chat knows.
- Real data for mockups: `python run.py --render-mockups DIR --real DATA` renders with Omri's real
  library (covers, pages, screenshots); random game, or SCRITCH_GAME=<title or id>. DATA = unzipped
  copy of the Deck's ~/.local/share/itch-deck/{library.json,covers,pages,shots} — ask Omri to attach
  it (Archive.zip). NEVER commit it: the repo is public, the art is the developers', the list is his.
- After ANY UI change: re-render mockups (`python run.py --render-mockups DIR`) and publish them as
  `after/` to the gallery artifact https://claude.ai/artifact/9cciLymE4pGMV7rswahZkZ (Omri expects it current).
- Ask Omri before big changes.

## Current milestone
M4 DONE (v0.4.2). Next: M5. v0.4.1 = M4 + design
  pass; build picker shows "Installed" as an accent tag like "Recommended" (W.rows).
v0.4.1 Deck test 14 Nov: Figment WINDOWS build (Change build -> figment-windows-32.zip) installs,
  "Preparing Proton…", short black screen, then plays with pad ✓. Linux build still crashes
  (known, stays). Game showed Xbox/Steam glyphs, not PS: Steam Input hands Proton games a virtual
  Xbox pad. Possible later test: tile with Steam Input off + PROTON_ENABLE_HIDRAW=1 (risky: our
  app + Deck's own controls rely on Steam Input). Steam -> Exit game closes the whole tile incl.
  our app: by design (Steam ends the tile's process tree; v0.3.0 showed it can't be refused).
  To get back to scritch, quit from the game's own menu.
v0.4.2 (Omri): install folder path removed from the game page (Settings still shows the root).
M4 — DONE 14 Nov (Figment Windows build via Proton plays; quitting from the game menu returns to
  its page ✓; Steam -> Exit game closing the tile is intended, Omri confirmed).
M5 edge cases — RELEASED v0.5.0 14 Nov (with the design-system + feel pass work), NOT yet tested on Deck.
  - SD card: config.card_missing(path) = under /run/media with no mount (never mkdir there:
    tmpfs). Install -> "SD card missing" error. Installed game whose dir is gone -> state
    "missing" (g["missing"] = "card"|"files"): tile tag, game page text, Play/Uninstall greyed
    (files-missing allows Uninstall). Installer.uninstall refuses (returns False) on a missing
    card. App._check_mounts every 2 s re-applies states (card back = installed again).
    Installed tab includes "missing".
  - Space: messages name the drive (config.drive_name); 2nd check before unpack (size × 1.5),
    download kept for Retry.
  - Program picker: Installer.programs/set_exe (install.json exe + alternatives, exe_chosen).
    "Program to run" = first row of Change build (only if >1 program); also offline / when no
    other builds. Program list tags current one "In use".
  - Silent installers: proton.installer_kind (inno/nsis/installshield), run_installer = umu-run
    setup.exe in the game's prefix, Inno /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /NOICONS
    /NOCANCEL /DIR=Z:\…, NSIS /S /D=Z:\… ; installs into <game>/files.inst then becomes files/.
    Phases "proton" (new prefix) -> "installing" (indeterminate bar). 15 min timeout, cancel
    kills the process group. Log: logs/games/<slug>-install.log. install.json "installer".
    InstallShield / other -> "can't run silently, try Change build". Bare setup.exe uploads allowed.
  - HTML5 / not playable: tile caption replaced by a dark tag on the art (W.tag).
  Deck checklist v0.5.0: 1 Update app. 2 Take the SD card out (or eject in Desktop Mode): SD games
  show "SD card missing", Play/Uninstall greyed, Install says SD card missing; card back -> normal
  within ~2 s. 3 An Inno-installer game (Windows setup.exe) installs with NO window: "Preparing
  Proton…"/"Installing…", then Play works. 4 A game with several programs: Change build -> Program
  to run -> pick another -> Play starts it. 5 Browser games tagged on the art.
  If broken: app.log "installer:", "install <id>:"; logs/games/<slug>-install.log.
M0 spike — PASSED on Deck 14 Nov (checklist 1–6 all ✓). Focus hand-off to child and back works.
M1 mockups — APPROVED 14 Nov. Gallery: https://claude.ai/artifact/9cciLymE4pGMV7rswahZkZ
M2 real library — v0.2.0 Deck test 14 Nov: 1,2,4,6,7 ✓. Count 129 = matches (itch shows 133 incl.
  non-game products). Fixed in v0.2.1: platforms come from owned-keys "traits" (all showed "No
  download"); long description/comments scroll inside the section (DOWN steps, then next section);
  "Loading details…" while fetching; prefetch throttled 1.5 s/game.
  Log (v0.2.0): pages DO load (desc + 4–8 shots); "no details" was the 3–5 s fetch on open (0.2.0
  only fetched on open) + one 404 page treated as offline. v0.2.2: 404 -> "page no longer exists",
  not retried; stricter comments-markup check. 1 of 10 pages parsed comments (305112, 10). If the
  warning persists, samples are saved to logs/pages/<id>.html (max 5) — ask Omri for one.
  Pads seen: "Steam Deck Controller", "Steam Virtual Gamepad" (DualSense via Steam).
  SteamVirtualGamepadInfo = path to ~/.local/share/Steam/config/virtualgamepadinfo.txt (read it
  for glyph auto-detect).
  itch.io is blocked from Claude's workspace: API + page parsing tested only with fixtures.
  First things to check on Deck if broken: app.log lines "itch sync:", "page <id>:", "pad added:".
Self-update pulled forward from M6 into v0.2.3 (Omri asked): updater.py checks GitHub latest at
  launch (quiet) + Settings → Update app (A: check / download / restart). Swaps binary in place,
  keeps itch-deck.old; restart = os.execve with PYINSTALLER_RESET_ENVIRONMENT=1. UNTESTED on Deck.
  Rollback by hand: rename itch-deck.old back in Dolphin.
v0.2.3 Deck test 14 Nov: all ✓ (comments OK on real pages). Spinner was static -> fixed.
v0.2.4 "feel" pass (Omri asked): hold-to-repeat on D-pad/arrows/stick (300 ms, then 85 ms);
  smooth eased scrolling (widgets.ease, LIVE flag: app animates, mockups snap) on library grid
  (scrolls only when focus leaves view) and game page (DOWN steps 0.18 screen in long sections);
  game page canvas cached by state key (20 ms -> 1.4 ms/frame). First real Update-app test.
v0.2.4 Deck test: all ✓, in-app update works. Omri: hold scroll ~50% too fast -> v0.2.5 repeat
  85 -> 170 ms (input.REPEAT_MS). Glide speed (W.ease speed 16/14) unchanged.
v0.2.6 (Omri): button labels centred; Settings Update row = info text + purple pill button on the
  right (Check/Update/Restart/Retry, rows() value tuple); Library L1/R1 = switch tabs (X still
  toggles, hidden from hints); L2/R2 held repeat at FAST_MS (300, 85) = several speeds:
  D-pad 170 ms/step, triggers 3 rows per 85 ms. Game page L1/R1 still prev/next game.
M2 — DONE 14 Nov (v0.2.6 on Deck, all ✓).
M3 native install — v0.3.0 built 14 Nov, NOT yet tested on Deck. Linux builds only.
  installer.py: queue (one at a time, data/queue.json, resumed at launch) -> uploads -> pick_build
  (stores/itch.py: skip non-default/external, full > demo, 64-bit > 32/ARM, newest) -> space check
  (size × 2.5) -> net.download (Range resume from _downloads/<gid>-<upload>-<file>.part, key in an
  unredirected header, cancel flag) -> extract to files.new (zip keeps exec bits, tar filter=data,
  7z only if py7zr, bare AppImage/ELF copied) -> find_exe (ELF header x86_64, name ~ title/slug,
  shallow; SKIP_EXE list; chmod +x all ELF/scripts) -> files/ + install.json + data/installed.json.
  Install state lives in lib.live too, so a sync can't drop it. Uninstall: index first, rmtree in bg.
  runner.py: child env drops PyInstaller's LD_LIBRARY_PATH (selftest asserts no _MEI); game output
  -> logs/games/<slug>.log. Flicker experiment: our window stays up OVERLAP_S=1 s after the child
  starts, then display.quit; "Starting…"/"Returning…" splash frames. Crash toast: rc≠0 <15 s or <3 s.
  Top bar: "Downloading 42% · Game (+N)" / "Refreshing library" / "Covers 40/120" / "Game details
  12/90" (Library.jobs counters), hidden when idle. Windows-only -> "next update" message.
  If broken on Deck, check app.log "install <id>:", "uploads <id>:", "play:".
v0.3.0 Deck test 14 Nov: 1-4,7,9,10 ✓. ✗ Figment installed but didn't launch (crash toast) —
  waiting for logs/games/figment.log + app.log "uploads/install/play" lines. ✗ Steam -> Exit game
  ignored (stuck "Exiting game", app kept running), mid-install and after a play.
v0.3.1: own SIGTERM/SIGHUP/SIGINT handler installed before pygame.init + SDL_NO_SIGNAL_HANDLERS
  (logs "signal N: quitting"), stops a running game, Timer 3 s -> os._exit; main ends with
  os._exit(0). Verified: SIGTERM exits source + frozen binary, no leftover process. Spinner/ring
  now supersampled 4x (widgets._arc, cached); tile ring spins while unpacking / 0%.
  "Cancel install" button -> "Cancel". Crash toast no longer says "Try Change build" (M5).
v0.3.1 Deck test 14 Nov: quit mid-download ✓ (Steam button + our Quit; log shows signal 2/15),
  resume ✓, Bleed 2 (bare -bin installer upload, exe data/Bleed2.bin.x86_64) installs, plays with
  pad, returns to game page ✓. Figment: SIGABRT in vkCreateInstance (gamescope WSI layer assert)
  with /tmp/_MEI libs loaded -> cause: after the in-app update restart, LD_LIBRARY_PATH_ORIG held
  the OLD copy's _MEI dir. ✗ pad connected after launch did nothing (no "pad added" line).
v0.3.2: runner.child_env strips every /_MEI entry (also *_ORIG), updater execve uses it too;
  verified frozen with a stale _MEI in env. Input: JOYDEVICEADDED too, _add dedupes by instance id
  and logs failures, rescan() every 2 s. Indeterminate bar glides (ping-pong) and the game page
  re-renders per frame while extracting. Installed tab: B -> All (hint "All games").
  If Figment still crashes after a FRESH launch from the tile: try Unity "-force-glcore" (M5 per-game
  launch options), since Bleed 2 (GL) works.
v0.3.2 Deck test 14 Nov: pad hotplug ✓, extracting animation ✓. Figment now gets past Vulkan
  (Mesa GL threads up), black screen, then SIGSEGV in game code -> Mono abort, exit -6 after 6 s.
  Not our libs any more. Unknown if it runs at all on SteamOS: test it as its own non-Steam shortcut.
  Unity's real error is in ~/.config/unity3d/<company>/Figment/Player.log. Ideas for M5 per-game
  launch options: -force-glcore, -screen-fullscreen 0, -screen-width 1280 -screen-height 800;
  also try OVERLAP_S=0 (our window still up when Unity picks its resolution?).
Player.log (~/.config/unity3d/Bedtime Digital Games/Figment/, no prefs file saved): Unity 2018.2,
  GL 4.6 OK, then "requesting fullscreen 1 x 1", crash in the Theora logo video. v0.3.3: Unity games
  (<exe stem>_Data or UnityPlayer.so next to exe) get -screen-fullscreen 1 -screen-width/height =
  our display size. Command line is written at the top of logs/games/<slug>.log.
v0.3.3 Deck: resolution fix works ("requesting fullscreen 1280 x 800"), Figment STILL crashes on
  its logo splash scene ("Receiving unhandled NULL exception"; stack symbols are junk). Also
  "Unable to preload libsteam_api.so / ScreenSelector.so". Not a launcher issue as far as we can
  tell -> stop chasing. Plan: Figment has figment-windows-32.zip -> try it via Proton once M4 +
  Change build exist. Optional check: run Figment.x86_64 as its own non-Steam shortcut.
v0.3.4 (Omri): top bar shows app update state in accent colour (available / Updating % /
  installed · restart), update toast removed; platform pills removed from game page; extract bar
  segment drawn live over the cached page (no full re-render) + extract yields GIL per 256 KB.
M3 — DONE 14 Nov (Bleed 2 installs, plays, uninstalls from the pad). Figment = known issue -> M5.
M4 Windows via umu + GE-Proton — v0.4.0 built 14 Nov, NOT yet tested on Deck.
  proton.py: umu_path (our zipapp at DATA/umu/umu-run, else PATH), fetch_umu (GitHub latest
  release asset *-zipapp.tar -> umu-run; install phase "umu" = "Getting umu-launcher…"),
  proton_dir (Settings choice, else newest GE-Proton in compatibilitytools.d; needs a "proton"
  file), env = WINEPREFIX <root>/_prefixes/<game dir name>, PROTONPATH, GAMEID=umu-default
  (NOT umu-<itch id>: umu-<number> = a Steam app id in umu's fix db). is_installer = Inno/NSIS/
  InstallShield bytes -> "installer, later update" (M5).
  installer: _choose = Change build choice (data/builds.json, kept for reinstalls) else Linux
  else Windows; Windows needs GE-Proton BEFORE download; find_exe(platform="windows") = .exe named
  like the game, shallow, big (SKIP_WIN: setup/redist/dotnet/…); bare .exe allowed for Windows.
  install.json gets platform + prefix. Change build on an installed game = reinstall over it;
  cancel/fail keeps the old build (toast "Couldn't change the build: …", kind "error").
  runner: .exe -> [umu-run, exe] (+Unity screen args), env written at the top of the game log;
  first run (no system.reg in prefix) keeps our "Starting… / Preparing Proton…" splash up until
  the prefix exists (max 300 s), then hands over the screen.
  Change build = picker (O1): uploads fetched in a thread ("Loading builds…"), Recommended first,
  current one tagged "Installed", A installs. Needs internet.
  Deck checklist v0.4.0: 1 Update app -> 0.4.0. 2 Figment -> Change build -> figment-windows-32.zip
  installs (first time "Getting umu-launcher…"). 3 Play: "Preparing Proton…" splash (very first
  umu run also downloads the Steam Linux Runtime, can take minutes), game runs with pad. 4 Quit
  game -> back on game page. 5 Steam -> Exit game while it runs: does wine linger? 6 Uninstall +
  reinstall Windows build: saves still there (_prefixes kept). 7 Change build back to Linux.
  If broken: app.log "install <id>:", "umu:", "play:"; logs/games/<slug>.log (env + umu output).
Design pass (own session, Omri 14 Nov): one consistent graphic language. Audit of v0.3.2 renders:
  1. Buttons: 3 looks (focused = panel + purple outline; unfocused = bare text, e.g. Change build /
     Uninstall; Settings Update = small filled purple pill). -> ONE button component, states
     normal / focused / disabled (+ maybe primary). Update row uses it.
  2. Pills overloaded: "itch" tab, Installed, Recommended, Update button, platform tags, Failed,
     "+1 more". -> tags (info, not pressable) look clearly different from buttons.
  3. Type scale: too many small sizes (top-bar status, "itch · 22 of 30", "Screenshots", picker
     details, install path). -> fixed scale of 4–5 sizes in theme, readable on TV.
  4. Focus: tiles/buttons/rows each slightly different. -> one focus style, one radius.
  5. Tile download ring sits on a heavy black disc. -> lighter badge.
  6. Section labels: "Screenshots" tiny grey vs "About this game" h2. -> same style.
  7. (older) Screenshots centre-cropped to 16:9; viewer should letterbox.
  Plan: shared parts first (theme tokens + widgets), then every page; render before/after
  sheets; update the M1 gallery artifact. Ask Omri before starting (medium change).
  DONE 14 Nov on branch design-pass (merged with v0.4.0), all 7 items + Omri's follow-ups:
  - Name shown = "scritch" (W.APP_NAME: wordmark, window title, quit dialog, Settings footer).
    Binary / data folders / repo / updater ASSET still itch-deck (renaming needs a data move).
  - PURPLE = "happening / yours" ONLY: progress, rings, spinners, ✓ badge, Installed/Recommended/
    Developer tags, tab underline — and the Play button (only coloured button;
    accent_btn, focused = accent). Never focus. Omri rejected purple-fill focus, white-fill focus
    and purple outline on buttons.
  - FOCUS = light: buttons/rows/fields grey panel_hi + dim text -> focus_fill + white text.
    Pictures (tiles, screenshots) = grow + thin light outline (focus_line). Tune focus_fill on TV.
  - Type: 5 sizes only: f_h1 5.2u, f_h2 3.2u (ALL section headers), f_body/f_btn 2.7u,
    f_small 2.4u (meta), f_hint 2.0u bold UPPERCASE (footer + tags).
  - W.button is the only button (Settings Update row too); W.tag(kind=) for info labels (squared,
    uppercase, never pressable); W.wordmark; one radius t.radius; tile ring on translucent chip.
  - Alignment: top bar on one baseline (text anchor "baseleft"/"baseright"); game hero column =
    cover height (first line cap = cover top, buttons on cover bottom unless pushed by status).
  - Viewer letterboxes real screenshots (contain=True); strip thumbs still crop.
  - faint grey only for disabled/separators; readable secondary text = dim.
  - Removed dead Theme.button/hint_bar/modal/text.
  Feel pass (14 Nov, branch feel-pass, after v0.4.1): widgets.anim(key, target) = eased 0..1
  per widget key (("btn", label), ("row", label), ("tile", gid), ("shot", gid, i), ("toast", msg));
  MOTION_SPEED 22 (~120 ms). Buttons/rows fade into focus_fill, tiles/shots grow smoothly,
  toast slides up + fades in. A press = widgets.press(scene.press_key()) -> 6% dip, PRESS_S 0.18.
  Page switch = App._set snapshots the old frame, App._fade fades it out (theme.page_fade_ms 160).
  Game page canvas redraws only while W.animating(). Mockups unchanged (LIVE off = end state).
  UNTESTED on Deck: check feel + frame rate on the game page during focus moves.
  Design system (14 Nov, branch design-system): DESIGN.md = the rules (read it before UI work).
  theme: space xs/sm/md/lg/xl (1/2/3/5/8u) + m; widths read_w 80u, page_w 110u. W.notice
  (error/busy) replaces 3 hand-drawn boxes + unused W.banner; modal = body only (actions in
  footer); empty Library no longer repeats Y Refresh; W.icon_draw (play, check) replaces ✓ ▶
  font chars; game status: not playable / missing = one "note" style, failed = W.notice.
  Motion v2 (14 Nov, Omri): W.spring = the one curve (ease-in-out-back, SPRING_BACK 1.1) for
  everything via W.ease (time-based tween, MOTION_MS 240). Focus = sliding plate (W.plate /
  button_row / rows key=...), tab underline slides, pages slide+fade (App._transition,
  theme.page_ms 260, direction by depth). Busy bar bounces (BUSY_SWEEP_S 0.75) with stretch.
  Motion v3 (Omri: "bouncy backfired"): sliding plate + press dip REMOVED; buttons/rows light up
  in place. SPRING_BACK 0 (calm) everywhere except the tab underline (TAB_BACK 1.1). Pages swipe
  (page_slide_u 12); Library content swipes on tab switch (direction: Installed = right).
  Omri 14 Nov: name = "SCRiTCH" (W.APP_NAME), always purple in text (W.text_named); logo = purple letters, white i; scrolling = no overshoot (ease back=0).
  Gallery = before/ (v0.3.2) + after/ with a Before/After/Side-by-side switch (AFTER_LABEL in index).

v0.5.1 (14 Nov): design round 2 released — motion v2 (spring curve, sliding focus plate + tab
  underline, page slide+fade), one purple main action per page, Update button purple when waiting.

v0.5.2 (Omri): B = Back on every screen except Library. Setup opened from Settings (Re-import
  API key) has back=True: B -> Settings, hint "Back". First run / rejected key: B still = Quit dialog.

## Found 14 Nov: free games with no price aren't in the library
- Hyperbole (nilsdesle, Inno test game) has plain Download buttons, no "Download Now / name your
  price" step. Downloading it creates NO download key, so it never shows in /profile/owned-keys,
  and scritch only syncs owned keys. Same for every itch game with payments switched off.
- Children of Solarus (first Inno pick) is gone from itch.
- BUILT v0.5.3 (Omri said go): ItchStore.sync also syncs COLLECTIONS. Was: also sync the user's itch COLLECTIONS (the "Add To
  Collection" button on any game page). itch API: GET /profile/collections, then
  /collections/{id}/collection-games (paginated). Merge into the library, dedupe by game id; no
  download_key_id needed: stores/itch.py already calls /games/{id}/uploads without one for free
  games. Small change (sync + dedupe + a fixture test). Verify the endpoints with the real key on
  the Deck log first, since itch is blocked from the workspace.
- Hyperbole's Windows upload is a bare "Hyperbole_setup_0.9.12 BETA.exe" (294 MB, no zip) ->
  the bare-setup.exe path of M5. Mac zip is skipped. Good installer test once collections sync.
- Omri 14 Nov: work on notes freely, but NO app release until he says.

v0.5.3: collections sync. After owned keys: GET /profile/collections, then per collection
  /collections/{id}/collection-games?page=N (also accepts the older {"games": [...]} shape), until
  an empty page. Owned wins on duplicates (keeps its key); games with min_price > 0 that you don't
  own are skipped (can't download); added games get source="collection", no download_key_id.
  Any collections error (403, offline, odd JSON) is logged and the owned list is still used.
  UNVERIFIED against live itch (blocked here). Deck: app.log "itch sync: collections [...] -> N
  free games added, M paid skipped". Panzer Marshal is in Omri's "cats" collection = test game.
  Not handled: Inno split installers (setup.exe + setup-1.bin as separate uploads, e.g. Stranger More).

v0.5.3 Deck test 14 Nov (Panzer Marshal via "cats" collection): collections sync ✓ ("cats" -> 3
  free games). NSIS silent install ✓ (3.2.13 x64-Setup.exe, /S /D=, exit 0 after 69 s, exe
  "Panzer Marshal.exe" found). Play ✗: Chromium/Electron FATAL rand_util_win.cc "Check failed:
  hmod" (ProcessPrng / bcryptprimitives missing) under GE-Proton8-11, the newest on the Deck ->
  needs GE-Proton 9+. Also: after returning from a game, "pad added: DualSense" every 2 s:
  Input._add stored pads under c.id but deduped by joystick instance id.
v0.5.4 (released 14 Nov, branch pad-fix-proton-hint): pads keyed by instance id;
  runner.crash_hint(slug) reads the game log for known causes (rand_util_win.cc -> "needs a
  newer GE-Proton (9 or later)"), shown instead of the generic crash toast.

v0.5.4 Deck 14 Nov: Omri installed GE-Proton11-12 (Settings picked it) -> Panzer Marshal runs
  (title screen, new game) = M5 installer path works end to end. No input from Deck pad or
  DualSense: the game is mouse/touch only (itch: "Inputs: Mouse, Touchscreen"), and the tile's
  Steam Input layout is plain Gamepad (pitfall #5). Workarounds: Deck touchscreen; tile layout
  "Gamepad with Mouse Trackpad". Real fix later = per-game Steam tile with its own layout.

v0.6.0 MOUSE MODE (Omri asked, before M6): itch_deck/mouse.py. While a game runs with effective
  controls "mouse", MouseMode reads the pads WITHOUT a window (ctypes SDL_GameControllerUpdate on
  the SDL2 lib pygame loaded, found in /proc/self/maps) at 125 Hz and writes to a virtual
  "scritch mouse" made via /dev/uinput (stdlib fcntl/struct, UI_DEV_SETUP API).
  Map: right stick -> pointer (deadzone .15, curve ^2, slow/normal/fast = 700/1200/1900 px/s at
  full tilt, Settings -> Pointer speed), R2/A left click, L2/X right click, left stick -> wheel,
  D-pad -> arrows, B/Start -> Esc. Biggest stick across pads wins (Deck pad + Steam Virtual
  Gamepad both open), buttons OR'ed. Started in play()'s release() after display.quit, stopped
  after the game exits (all keys released). Any failure = log "mouse mode: off (reason)" + toast
  "Mouse mode isn't available: ..." after the game; the game always starts.
  Per game: game page "Controls" button cycles Auto -> Pad -> Mouse (cfg["controls"][gid]); tag
  next to Installed shows "Mouse controls · auto". Auto = mouse when the itch page's Inputs row
  lists Mouse/Touchscreen and no gamepad/controller/joystick (itch_page.parse_inputs; page cache
  now stores "inputs"; older cached pages count as stale and refetch on open).
  UNVERIFIED on Deck: /dev/uinput permission (SteamOS uaccess?) and pad reads with no window.
  Check app.log "mouse mode: on/off (...)". Gallery updated (15, 20, 21, 23, 24).

## Future (optional) milestones
- M7 browser games (Omri 14 Nov: optional, after M6). Plan: download the HTML5 upload zip (itch's
  own app plays these offline), serve it from a local http.server (fixed port per game so
  localStorage saves survive; send COOP/COEP headers for Godot 4 web), launch Chromium flatpak
  --kiosk like a game (display handoff as runner.run). Needs Chromium from Discover once.
  Open: games hosted only on the dev's site stay "browser only"; a quit shortcut (web games have
  no Quit); keyboard-only games need a Steam Input layout. ~1–2 sessions + 30 min Deck.

## Code map
- app.py: App = scene switcher (setup/library/game/settings), key import + check thread,
  per-scene _h_<kind>() input. Flags: --windowed, --selftest (fake data, temp dirs), --render-mockups.
  Install/Cancel/Play/Uninstall via game_action(); confirm(title, body, yes, fn) dialog.
  Change build = build picker (M4) + "Program to run" row (M5).
- proton.py: umu-run download/lookup, GE-Proton dir, per-game prefix + env (M4).
- config.py (chmod 600, install_root: SD else ~/Games/itch, proton_versions), net.py (urllib +
  certifi; Offline/AuthError), stores/itch.py (owned-keys, quirk, dedupe), stores/itch_page.py
  (HTML -> description/shots/comments, tolerant), library.py (cache, sync thread, job queue:
  covers prio 1, opened page prio 0, prefetch prio 5; page cache 7 days; shots -> 1280px jpg).
- paths.use_root(dir) redirects everything (tests/selftest). tests/test_itch.py runs in CI.
- theme.py: all colours/sizes/fonts/timings. Inter bundled in assets/fonts (OFL).
  Grid: 4 cols at 1280×800, 5 at 1920×1080 (from width).
- ui/widgets.py: cover placeholder, tile (+badges), button, pill, ring, spinner, progress,
  modal, toast, banner, rows, hint bar, wrap.
- ui/scenes/: base (overlay + toast + hint bar), setup, library, game (+picker), settings.
  Each has draw(s) and handle(act) for focus moves; scene switching comes in M2.
- fake.py: 30 invented games + upload list for mockups/tests. mockups.py: the shot list.
- CI: --add-data itch_deck/assets; renders mockups (crash test) and uploads them as artifact.

## Decisions
- pygame-ce, PyInstaller onefile, built on GitHub Actions ubuntu-22.04; tag v* = Release.
- Windows games: umu-launcher + GE-Proton. Prefixes in <install root>/_prefixes/<slug> (saves survive uninstall).
- Install root default: SD card, changeable in Settings (new installs only).
- Installers: always silent, store-like (Install -> progress -> Play). Fail = "Couldn't install" + log.
- Non-playable + HTML5 games: shown dimmed + tagged. Sort A–Z. Placeholder tile art.
- API key: typed/pasted into Setup field via RustDesk in Desktop Mode (run with --windowed). Never in repo.
- While a game runs, the app closes its display (pygame.display.quit) and reopens after.
- M1 feedback (14 Nov): accent PURPLE #9D6BFF; RED only for errors (theme.error). No Proton/WIN badge
  on art. Offline = small cloud icon in top bar, no banner; Install shows "needs internet".
  Crash toast only if a game dies soon after start: "<game> closed right after starting. Try Change
  build." (no exit codes in UI; details stay in the log). Picker shows the developer's file names,
  platform/size/date, and a "Recommended" pill (Linux native > Windows zip > installer).
  Game page shows itch short_text (API, cached). Initials covers = placeholder only.
- Background: soft diagonal gradient dark blue (bg_from, top-left) -> dark purple (bg_to, bottom-right),
  like Omri's Game Night app; panels are cool navy-greys. widgets.backdrop(t), cached per size.
- ◀ ▶ glyphs are drawn triangles (smaller, optically centred), not font characters.
- Glyphs = Steam's visual language (Omri sent a Steam Deck screenshot as the reference): SOLID white
  shapes with the label knocked out in dark ink (glyph_c / glyph_ink). A B X Y = circle, L1 R1 L2 R2 =
  small rounded square, ☰ (hint key MENU) = white pill. Footer: actions RIGHT-aligned, labels white
  BOLD UPPERCASE (f_hint); order = extra actions first, then A, B always last. Bumpers are L1/R1.
- Open: glyph labels Auto/Xbox/PlayStation — M2 logs pad names/GUIDs + SteamVirtualGamepadInfo;
  read them from the Deck log, then add a Settings override.
- M2 input: L1/R1 (prev/next game), L2/R2 (triggers, page up/down), Back mapped. Keyboard in
  --windowed: arrows, Enter=A, Esc=B, x/y, m=Start, q/e=L1/R1, PgUp/PgDn=L2/R2.
- Key entry: Warpinator file is auto-picked up (polled every 2 s on Setup); "Type key" field takes
  Steam+X keyboard text or Ctrl+V (RustDesk). Bad key -> Setup "rejected"; no net -> Retry.
- Comments: shown only if parsed (forum games / parse miss -> section hidden). Dev = flag text
  "Developer" or owner class — UNVERIFIED against live itch markup.
- DECIDED (Omri: important for choosing games): full description + screenshots on the game page.
  Not in itch's API -> read the game's public itch page (url from owned-keys), parse description
  (HTML -> paragraphs, v1 text only) + screenshot URLs, cache text + downscaled shots (offline OK).
  Fetch lazily on page open + low-priority background prefetch. Fragile if itch changes HTML:
  fall back to short_text, log the parse failure. Build in M2.
- DECIDED: comments from the public page too (same fetch + cache as description). Newest first, max
  ~10, author + date + text (3 lines max), developer comments get a purple bar + tag. Replies are
  INDENTED under their comment (max 2 shown, 2 lines each, smaller), then "+N more replies".
  Games that use a community forum instead of comments: show nothing (or a count) — check in M2.
- Game page layout: hero (34% cover, info, actions in ONE ROW, L/R moves) then DOWN -> screenshots
  strip (A = full-screen viewer, L/R browse) -> DOWN -> "About this game" -> DOWN -> Comments.

## Token usage log (Omri's Pro plan %, as he reports it — add a line each time)
- 2026-11-14 00:08 — 72% at start of M0 build (planning + M0 in one chat)
- 2026-11-14 11:24 — 73% → 76% for M1 mockups (+ logging M0 Deck results) = 3%
- 2026-11-14 12:01 — 80% → 81% for M2 build = 1%
- 2026-11-14 15:23 — 82% after M2 fixes v0.2.1–0.2.3 (+ self-update); v0.2.4 feel pass starts here
- 2026-11-14 16:39 — 83% at start of M3 build
- 2026-11-14 17:43 — 87% at start of design pass
- 2026-11-14 18:10 — 88% at start of M4 build
- 2026-11-14 18:44 — 92% at start of M5 build

## Known issues (cosmetic, Omri: "not that bad")
- Launching a child: Steam UI ("Steam menu" / "Back" hint bar) flickers twice. Cause: the gap while
  our display is closed (display.quit -> child window up, and child exit -> display reopen).
  Idea to test later: keep our window up until the child has had ~1 s to map, then quit display;
  on return, draw a "Returning…" frame first. Try in M3 with a real game.
- App start: Steam logo, then 2 flickers before the window. Likely onefile unpack + SDL fullscreen
  mode switch. Ideas: set_mode(desktop size, NOFRAME) instead of FULLSCREEN; --onedir build.
- Screenshots are centre-cropped to 16:9 (strip + viewer); viewer should letterbox instead. Small.
