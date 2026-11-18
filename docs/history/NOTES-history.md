# SCRiTCH notes: history up to v0.9.4 (moved out of NOTES.md on 17 Nov)
Old milestones, release logs, research, design passes and superseded roadmaps. Kept for reference;
the working rules and the current state are in NOTES.md.

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
  design-next (branch, NOT merged): ia-pass + game-page-v2 combined, plus: game page = ONE main button + square ⚙ Options (Uninstall / Change build / Controls; ☰ opens it too), ONE message box under
  the buttons for every game state (Game.message(): failed=error, SD/files missing, queued, not
  playable=info; W.notice kind "info"), confirm dialogs show [action, Cancel] buttons (LEFT/RIGHT,
  sc.confirm_focus), Install location = "SD card"/"Internal storage" only, no "by" when no author.
  IA pass (branch ia-pass, NOT merged yet): game page = Play/Install + Change build only,
  Uninstall/Controls in ☰ Options (W.menu "menu" overlay; ☰ no longer opens Settings from a game);
  Library tabs All/Installed/Recent, X = Sort & filter (cfg library_sort/library_show; visible() in
  scenes/library.py is the one filter, app._shown uses it); data: stores/itch "added" (key
  created_at), paths.PLAYED + Library.mark_played (on play). Settings grouped + scrolls.
  Genre / Average session (14 Nov): itch_page.parse_row(html, name) reads any "More information"
  row (Inputs uses it too); page cache gets "genre" ([first]) + "session"; caches without "genre"
  refetch once. Filters in Sort & filter (cfg library_genre / library_session). Greyed-out
  buttons now show focus clearly (Figment "focus doesn't move" = SD-missing greyed buttons).
  FIXED 14 Nov: game-page focus froze on most real games (from launch). W.anim's "busy" lasted 50 ms
  but a real page re-render took longer -> next frame thought nothing moved. Now busy lasts until
  the tween ends; game buttons are drawn LIVE over the cached page (Game._buttons), focus left the
  cache key -> focus move = ~3 ms/frame instead of a full re-render. tests/test_motion.py.
  Lesson: test UI with --real data / App + /tmp copy of the cache, not only fake.py.
  Filters v2: Library.menu_open/menu_next(label, step), _count(), filter_summary(); W.rows arrows=.
  Library.queue_prefetch now also refetches page caches without "genre" (fills Genre/session in bg).
  NAME RULE (Omri 15 Nov, repeated many times — get it right): SCRiTCH, letters purple, i WHITE,
  EVERYWHERE. W.render_text() draws every on-screen string and applies it automatically (any case
  in the source text); phone pages: phonelink.named(). Don't draw text any other way.
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
  Inno split installers (setup.exe + setup-1.bin as separate uploads, e.g. Stranger More): v0.7.4.

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
  v0.6.0 Deck 14 Nov: WORKS (Omri). /dev/uinput is writable on SteamOS and pad reads with no
  window work; Panzer Marshal playable with right stick + R2.
  Check app.log "mouse mode: on/off (...)". Gallery updated (15, 20, 21, 23, 24).

M5 Deck test (v0.6.0, 14 Nov evening): 1 uninstall + reinstall Panzer Marshal ✓; 2 card out ->
  SD games missing, Play/Uninstall greyed ✓; 3 ✗ install with card out WORKED, into
  ~/Games/itch (no install_root in config -> install_root() fell back to internal when no card);
  4 card back -> playable ✓ ("install <id>: folder back"); 5 no browser games seen (probably none
  in his library); 6 B -> Settings ✓; 7 design/feel OK for now; 8 Panzer Marshal Linux build
  (PanzerMarshal_3.2.14_linux_64.bin, bare file) exited 127 after 0 s. Guess: an AppImage, which
  needs libfuse2 (not on SteamOS) and exits 127 without it. Game log not seen yet.
v0.6.1 (Omri chose "remember the SD card", 14 Nov): config.pin_install_root saves the SD card
  (sd_card()/itch, or the root of games already installed on a card) as cfg["install_root"] the
  first time it's seen: at start and in App._check_mounts (every 2 s). Card out later -> installs
  fail with "SD card missing". Never moves once set (Settings will change it, M6).
  AppImages: installer.is_appimage (ELF + "AI\x01/\x02" at offset 8); after find_exe on a Linux
  build, unpack_appimage runs `<file> --appimage-extract` (no FUSE needed) and the exe becomes
  squashfs-root/AppRun; on failure it stays packed and runner sets APPIMAGE_EXTRACT_AND_RUN=1 for
  every game. crash_hint "libfuse" -> "Uninstall and install it again".
  Deck checklist v0.6.1: 1 Update app. 2 Settings shows the SD card as install location (app.log
  "install root pinned"). 3 Eject card -> Install any game -> "SD card missing". 4 Card back.
  5 Panzer Marshal -> Change build -> linux .bin -> Install -> Play (app.log "appimage ...:
  unpacked"). If 5 fails: send logs/games/panzermarshal.log.
  Games installed to ~/Games/itch during test 3 (A Good Snowman, Anarcute) stay there and work.
v0.6.1 Deck 14 Nov: pin ✓ ("install root pinned: /run/media/deck/9273…/itch"); card out ->
  install fails "SD card missing" ✓; card back -> install works, BUT the red error stayed on the
  game page (Omri: want a small pop-up that the card is back). Panzer Marshal .bin still exit 127
  after 0 s, and NO "appimage" log line -> it is NOT an AppImage (no AI magic). 127 from a started
  ELF = most likely "error while loading shared libraries" (a lib SteamOS lacks). Need
  logs/games/panzermarshal.log to know which lib.
  CONFIRMED (game log): libwebkit2gtk-4.0.so.37 missing (a Tauri app; SteamOS has no webkit2gtk-4.0).
  Not fixable by us -> the Windows build is the way; the new crash hint says so. M5 DONE.
Branch card-back (NOT on main, NOT released — Omri 14 Nov: no app release until he says;
  remember a push to main = a release, CI publishes VERSION): App._check_mounts tracks
  card_missing(install root); on change toasts "SD card removed." / "SD card is back." and on
  back clears failed installs whose fail_reason starts "SD card missing". runner HINTS: "error
  while loading shared libraries" -> "needs a library SteamOS doesn't have. Try Change build ->
  the Windows build." VERSION still 0.6.1 on the branch: bump when releasing.

v0.6.2 = rest of M6 (Omri said go 14 Nov, after design-next was done; branch card-back has
  design-next merged in + SD card toasts + missing-library hint):
  - Settings: every row works, A hint names the action (Settings.ACTION). Install location cycles
    config.install_choices() (SD card if mounted, Internal ~/Games/itch); new installs only; value
    "SD card (missing)" when pinned card is out. Proton version cycles Auto (newest) + each
    GE-Proton (cfg["proton"] None = auto; value "Auto · GE-ProtonX"). Saves of uninstalled games
    = proton.leftover_prefixes(roots, installed folder names) under every root in use (skips a
    missing card), sized in a thread (App._scan_saves, "Checking…"), A -> red confirm -> rmtree
    in a thread -> rescan. "Comes in a later update." no longer reachable from Settings.
  - Messages: no raw exceptions / exit codes / paths in the UI (installer start error, installer
    exit code, "Can't write to the <drive>", mouse-mode uinput error -> log). proton.NEED_GE one
    text for "GE-Proton isn't installed…". Mouse mode toast: "Mouse mode didn't start (…). The
    game ran without it."
  - README.md: setup (release, tile, GE-Proton, key), buttons, Settings, troubleshooting table,
    logs, file layout, known limits, dev commands.
  - selftest drives Settings (rows act, saves found + deleted). Mockup 21 values updated.
  Deck checklist v0.6.2: 1 Update app -> 0.6.2. 2 Settings: Install location toggles SD/Internal
    (toast), set it back to SD. 3 Proton version cycles Auto / your versions. 4 Saves of
    uninstalled games shows a size (Figment's Windows prefix if uninstalled) -> A -> Delete.
    5 Card out/in on a game page: "SD card removed." / "SD card is back.", the red error clears.
    6 Panzer Marshal Linux build -> Play -> message says to try the Windows build.
    7 Read README on GitHub: anything unclear?

v0.6.2 Deck 14 Nov: all ✓ except 5: toasts show, but the game page didn't change. Repro: the
  installed-game case updates fine; a NOT-installed game kept a normal Install with the card out.
  Fix (branch card-back, NOT released — Omri: don't push yet): Game.card_out (App sets it from
  _card_out each frame, in the page cache key): Install / Retry install greyed + info box "SD card
  missing · Insert it to install this game, or change Install location in Settings." Mockup 22b.
  VERSION still 0.6.2 on the branch: bump to 0.6.3 when releasing.

v0.6.3 (Omri: finish M6 and push, 14 Nov): card-back = design-next + design's direct main pushes
  (genre/session length, focus-freeze fix) + SD card toasts + card-out game page + M6. Note: design
  pushed main twice at 0.6.2 without a bump, which replaced the v0.6.2 binary; CI now skips the
  release when the tag exists. M6 DONE once the v0.6.3 Deck check passes.

v0.6.4 (15 Nov, Omri "push update"): only change = design's "Filters v2" (pushed to main 14 Nov
  23:20 at 0.6.3; CI correctly skipped re-releasing v0.6.3). Version bump only.

v0.6.5 (branch v065-launch-split, 15 Nov; NOT merged/released - Omri: "build and don't push"):
  - Launch: runner.WindowWatch (libX11 via ctypes, XSetErrorHandler no-op) hands over when a NEW
    viewable >=64 px top-level window appears (max WINDOW_MAX_S=10, no DISPLAY/libX11 -> old
    OVERLAP_S timer). app_play._hide_window: pygame.Window.from_display_module().hide() instead of
    display.quit(); _show_window on exit = instant (Deck log showed 0.9 s reopen gap = Steam UI
    flicker). SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1 (main) so mouse mode still reads pads while
    our window is hidden. config "launch_release": "quit" = old behaviour (fallback if gamescope
    misbehaves). Tested on Xvfb: handover at the game's window (1.6 s for a 1.5 s-start game),
    10 s timeout for a windowless child; tests/test_launch.py (skips without Xvfb).
    Deck check: Linux game + Windows game: no Steam UI between Starting…/game/Returning…; game
    gets focus + pad; return works; mouse-mode game still moves the pointer. If the game opens
    BEHIND or input is dead: set "launch_release": "quit" in config.json and tell me.
  - app.py split into mixins (code unchanged, AST-compared: 45/45 methods identical): app_setup
    (key import), app_settings, app_game (game page, picker, uninstall, controls), app_play
    (play/hide/show/splash), app_common (QUIT_DLG, LATER, _gb). app.py 969 -> 486 lines.
  - Epic research (no code): see "Epic tab" below.

v0.7.0 (same branch v065-launch-split, 15 Nov; NOT released - waits for Omri's push; includes
  v0.6.5). Roadmap v2 = plan doc section 9. Licence GPL-3 (Omri 15 Nov; needed to bundle legendary).
  - Phone login: phonelink.PhoneLink = ThreadingHTTPServer on 0.0.0.0:<random>, URL
    http://<lan_ip>:<port>/?t=<secrets.token_urlsafe(8)>, TTL 300 s (tick() -> new token + QR),
    403 without the token, POST /send (<=8 KB) -> on_text (server thread) -> App.phone_text ->
    _phone_tick (main loop) -> check_key(key_from_text). /status for the phone's "Checking… /
    Connected as X". Started in go_setup (also Settings -> Re-import), stopped 6 s after leaving
    Setup. No LAN IP -> qr None -> old 3-step Warpinator layout. QR = qrcode 8.2 (BSD, pure
    Python) drawn as rects on a white plate. Setup buttons: Import file / Type key.
  - GE-Proton: proton.fetch_ge (GitHub latest GloriousEggroll/proton-ge-custom, *.tar.gz +
    *.sha512sum, resume, 2.5 GB free check, DATA/ge/) -> install_ge_tar (refuses abs/../links
    out, + tarfile filter="tar", unpack to .scritch-unpack then rename into STEAM_TOOLS).
    Installer phase "ge" before a Windows game's download (game page "Getting GE-Proton N%").
    Settings Proton row "Not installed · A to download" -> App._get_ge thread, row shows %.
  - Settings "Disconnect itch" (value = itch user; cfg itch_user saved on key success) -> confirm
    -> api_key removed, lib.store None, Setup.
  - README: setup now 1 Desktop Mode step; phone login, GE-Proton auto, Licence section.
  Deck checklist v0.7.0: 1 Update app. 2 Settings -> Disconnect itch -> Setup shows a QR. 3 Scan
    with the phone -> page opens -> Open itch API keys -> generate -> paste -> Send -> TV says
    Connected, phone says Connected. 4 Settings -> Proton version: your GE-Proton (Auto). 5 (only
    if you want) launch checklist from v0.6.5. If 3 fails: is the phone on the same Wi-Fi? try
    the address under the QR in the phone's browser; send app.log lines "phonelink:".

v0.7.0 Deck test (15 Nov): phone login ✓ (new key), Circa Infinity (Windows) ✓ "plays perfectly",
  Cosmic Express (Linux) installs + shows its title screen but ignores the pad -> couldn't exit.
v0.7.1 (branch v071-fixes, NOT released):
  - Dialogs (DESIGN rule, Omri): W.modal widens up to read_w, then wraps (wrap_lines); bodies are
    lists of <=2 short lines. Disconnect + Delete saves texts shortened.
  - Phone page after Send: polls /status -> big green "✓ Connected as X" + "Close this tab"
    (window.close(); browsers may refuse -> "You can close this tab now"), red result + "Try
    another key" on reject. Page stays up 10 s after leaving Setup (was 6).
  - Install progress = one module (DESIGN rule): queued shows in the progress row ("Starting…",
    or "Queued · After the current download" when Game.behind), no message box under it.
  - Quit shortcut: mouse.QuitCombo, hold BACK + START (View + Menu / Create + Options) 2 s ->
    runner.stop_child(): games now start in their own session (start_new_session) and stop_child
    SIGTERMs the whole group, SIGKILL after 4 s (Proton/Wine helpers too; also used by Steam's
    Exit). Fed by mouse mode's loop when that runs (one pad reader), else its own thread.
    "Starting…" splash shows the hint; closing this way toasts "<game> closed." (not a crash).
  - Cosmic Express ignoring the pad = the game (keyboard only?); the shortcut is the way out.
  Deck checklist v0.7.1: 1 Settings -> Disconnect itch: text fits, no cut. 2 Phone: green
    Connected + Close tab. 3 Install a game: progress row only, nothing pops under it. 4 Cosmic
    Express -> hold View + Menu 2 s -> back in scritch, toast "closed". 5 Same on a Windows game.
  - Time to beat = HowLongToBeat (Omri: "we need time to beat, especially with Epic"); itch's
    Average session is gone (game page + filter). hltb.py = own stdlib client (howlongtobeatpy
    pulls aiohttp/bs4/fake_useragent): home page -> /_next chunk with the POST /api/... endpoint
    (fallback api/s) -> GET <ep>/init?t= -> token (15 Nov: token only, no hp key/val; the token
    is bound to the UA, so one UA per session) -> POST search with x-auth-token. Strict match:
    normalised name or alias must be equal. Library job "hltb" prio 7 (after pages), 1.5 s
    apart, hltb.json per game id, rechecked after 30 days (misses too); one Offline -> skip the
    rest this run. Game page: dim line "Main story ~4 h · Completionist ~9 h", nothing if
    unknown. Library X: Length (Any/Under 2 h/2–10 h/10 h+) + Sort "Shortest first" (unknown last).
    LESSON: my workspace can't reach HLTB; .github/workflows/hltb-live.yml runs
    `python -m itch_deck.hltb <titles>` on branch pushes touching hltb.py (15 Nov: Celeste 8.5 h,
    Circa Infinity 5 h, Cosmic Express 7.5 h, Baba Is You 7.5 h, fake title not found). build.yml
    runs it too, warning only. If times vanish on the Deck, HLTB changed: run that workflow.
  LESSON (15 Nov, v0.7.4): a ": " inside a workflow step name breaks the YAML and GitHub runs
    NOTHING (0 s failure named after the file). Before pushing workflow changes:
    python3 -c "import yaml; yaml.safe_load(open('.github/workflows/build.yml'))".
  LESSON (15 Nov): CI is Python 3.11 — no backslashes inside f-string {} (3.12+ only). Before
    releasing also run `python3.11 -m pytest -q tests` (3.11 + deps are installed in the workspace).
  Deck checklist +6: library X -> Length / Shortest first fill in after a minute; game page shows
    the time line for a known game (Circa Infinity), nothing for an obscure one.
v0.7.1 RELEASED 15 Nov (main cbc5e2d; first build failed on Python 3.11 f-string backslashes).
v0.7.2 RELEASED 15 Nov (Omri "push update"): pad-glyphs + single-instance + phone-result (phone
  Connected page: no 'Close this tab', plain note). Checked: pytest 3.13 + 3.11 (79), selftest
  3.13 + 3.11, selftest with itch rejecting every key, mockups. Deck checklist = the two below.
Per-controller glyphs (in v0.7.2):
  Deck log answered the open question: under Steam BOTH pads are Valve virtual pads (GUID vendor
  28de: Deck 030079f6de28..., DualSense 0300b836de28...), so GUIDs are useless. NAMES work:
  "Steam Deck Controller" / "DualSense Wireless Controller"; a pad hot-plugged while we run is
  sometimes "Steam Virtual Gamepad" -> Steam's virtualgamepadinfo.txt ([slot N] type=steam/ps5)
  says which kinds exist; generic pads take the kinds no named pad has (pads.resolve).
  - pads.py: kind_from_name, steam_slots, resolve (known kinds stick: removing the Deck pad must
    not hand its slot to the DualSense; "xbox" fallbacks are re-asked on rescan), pick (last pad
    pressed; before any press, a non-Deck pad), NAMES per kind, name(btn), current (set by
    App.update every frame from App.pad_kind()).
  - input.py: Input.kinds / last_pad (button down or stick/trigger past DEADZONE), kind();
    log "pad added: ... -> ps", "pad in use: ...".
  - widgets.glyph(kind=): DualSense ✕ ○ □ △ drawn (4x supersampled, widgets._shape), CREATE /
    OPTIONS word pills; Deck/Xbox ⧉ View pill (BACK) + ☰ (MENU/START); Xbox LB RB LT RT.
    W.glyph_line = sentence with glyphs; W.splash = the Starting/Returning frame (App._splash +
    mockups). QUIT_HINT is a parts list: "To quit a game: hold [⧉] + [☰] for 2 seconds".
  - Texts: updater "A to check", program picker, offline "press Y", Setup "Steam + X" (PS: "PS +
    Square") all via pads.name. Settings → App → "Button symbols": Auto · <detected> / Steam Deck
    / PlayStation / Xbox (cfg button_symbols). Kept 4 Settings groups (row went into App).
  - Mockups: every screen renders with Deck glyphs + a ps_* set (library, quit, game, settings
    focused on Button symbols, starting splash, setup typing); 25_starting = quit hint.
  Deck checklist: 1 Start with only the Deck: footer A B X Y, ☰; Starting… shows hold ⧉ + ☰.
    2 Connect the DualSense while SCRiTCH runs, press a button on it: footer turns ✕ ○ □ △ /
    OPTIONS within a press (app.log "pad ... = ps (Steam's slot list)" if it came in generic).
    3 Press a Deck button: back to Deck glyphs. 4 Start a game with the DualSense: splash says
    hold CREATE + OPTIONS. 5 Settings → Button symbols cycles; Auto shows what's detected.
    If wrong: send app.log lines "pad added", "pad in use", "pad ... = ".
v0.7.3 RELEASED 15 Nov (Omri "push update"; branch filter-and-ps-glyphs). From Omri's v0.7.2 Deck test:
  - Sort & filter: ◀ ▶ moved the library behind the menu (re-sort + scroll reset under the
    shade). Library.draw_page now draws a frozen snapshot while the menu is open; on close, if
    filters changed, the content fades in. tests/test_library_menu.py (fails on the old code).
  - DualSense Create / Options were word pills; Omri: must look like the real pad. Reference he
    sent (Ackhsly game-assets sheet): small oblong buttons, about 1:2, leaning ~8° OUTWARD
    (Create top-left, Options top-right), icon just above: Create = three short strokes fanning
    out (\ | /), Options = three horizontal lines. widgets._ps_small draws that solid white
    (4x supersampled), glyph height 1.25 d. He chose "icon above" over "icon inside".
  - Tabs (Omri 15 Nov): All · Installed · itch · Epic. Store tabs show only from 2 connected
    stores (Library(stores=...); app passes none yet = itch only, so All · Installed today).
    Recent tab -> Sort "Recently played" (played desc, then A–Z). Game "store" field, default itch.
  - Game updates: install.json "upload_updated" (upload updated_at) + "build_id" (butler);
    installer.update_for(); Installer.check_updates() in a thread: after sync every 30 min (each
    game at most every 6 h) and forced for the game whose page opens. Found -> install.json
    "update" {upload_id, filename, updated}; tile tag "Update" (accent), info box "Update
    available" → Play · Update · ⚙, Update button = Installer.update(): reinstall over (same upload
    id allowed via Installer.updating), fail keeps the old build ("Couldn't update X: …").
    Installs from before v0.7.3 get a baseline on the first check (no false update).
    UNVERIFIED against live itch: whether updated_at changes on a file replace (build_id does
    for butler pushes). Deck: app.log "updates <id>: newer build".
  - Keys controls mode: Controls Auto / Pad / Mouse / Keys. mouse.Mapper(layout="keys"):
    D-pad + left stick (0.5) = arrows, A Space, B Esc, X Z, Y X, Menu Enter, L1 R, R1 Shift,
    right stick + R2/L2 = mouse. auto_mode: pad listed -> gamepad, keyboard -> keys, mouse/touch
    -> mouse. For Cosmic Express (keyboard only, ignored the pad).
  - Omri 15 Nov (screenshots): update = its own button, Play · Update · ⚙ (no info box, not in
    Options). And: NO technical/long text in the app for casual players. words.short() maps
    install reasons to a few plain words (or nothing), full reason in app.log ("install <id>
    failed: …"); crash toast "<game> couldn't start." + runner.HINTS short next step; game page
    boxes cut to title + ≤ 4 words. DESIGN rule 10 rewritten. Open (Omri): later, a way to give
    specific errors to players who want to troubleshoot (e.g. a details view) — not now.
  Deck checklist v0.7.3: 1 Sort & filter: ◀ ▶ changes values, library behind stays still, new
    result fades in on close. 2 DualSense: Create / Options look like the pad (footer + Starting).
    3 Tabs: All · Installed; Sort has Recently played. 4 Cosmic Express → Options → Controls
    (should say Keys · auto) → play with the D-pad, A, X (undo). 5 Updates: hard to force — check
    app.log for "updates" lines (no errors); if a game of yours got a new build, it shows Update.
  Plan agreed 15 Nov (Omri "okay" to all): v0.7.4 = faster start (onedir?) + Inno split installers;
    then M7 browser games; Epic v0.8/v0.9 with "each game as its own Steam tile" in the same step.
v0.7.4 RELEASED 15 Nov (Omri "push update"; branch v074-start-split = split installers + faster start + settings-sidebar):
  - Split installers (BUILT): stores/itch.split_parts(build, uploads) = Inno slices uploaded
    separately (setup.exe + setup-1.bin, -2a.bin…; same stem first, else every slice-named .bin
    without a Linux tag when the exe was renamed). pick_build skips slices (is_part), so they never
    show in Change build. Installer downloads build + slices as _downloads/<gid>-<upload>-<file>,
    one progress bar over the total, space check on the total, hard-links the slices next to
    setup.exe (copy if another drive) before the silent install; downloads kept until success.
    UNVERIFIED against live itch: whether itch tags the .bin uploads with a platform. Deck test:
    Stranger More -> Install; app.log "installer comes in N more pieces".
  - Faster start (BUILT, Omri 15 Nov: "faster start and split installers in the same update"):
    release file = packaging/launcher.sh + tar.gz of the PyInstaller FOLDER build
    (packaging/pack.sh, packaging/build.sh -> release/itch-deck; CI uses it). Same asset name
    "itch-deck", same tile path, >5 MB, so v0.7.3's updater takes it. Launcher: app/VERSION !=
    its version -> unpack to app.new, app -> app.old, app.new -> app (fail = keep the old app,
    log to logs/launcher.log; no app at all = exit 1); then exec app/itch-deck with
    SCRITCH_LAUNCHER=<itself>. updater.launcher_path() = that file (replaced on update, restart
    execs it). runner._bundle_dirs: child_env strips sys._MEIPASS + app/ app.old/ app.new/ lib
    dirs (selftest asserts no "/_internal" in a game's env). tests/test_launcher.py.
    In the app: pygame.display/font/joystick init instead of pygame.init() (no audio device;
    input.py key repeat uses time.monotonic since get_ticks needs pygame.init), cfg loaded before
    the display, borderless desktop-size window (NOFRAME) instead of FULLSCREEN (no mode switch;
    config "window": "fullscreen" = old way), backdrop painted + flipped right after set_mode.
    Measured here (dummy video): 0.46 s onefile vs 0.13 s via launcher to "display open".
    Disk: ~45 MB file + ~120 MB app/ (+ app.old/ after the next update).
  - Settings sidebar (design chat's origin/settings-sidebar) merged in (Omri: in v0.7.4, not 0.7.5).
  Deck checklist v0.7.4: 1 Settings -> App -> Update (from v0.7.3): restarts into v0.7.4 (the
    first start after an update unpacks once, Steam logo a bit longer). 2 Quit, start from the
    tile: quicker? how many flickers now? 3 Screen looks right (full size, no border, overlay
    OK); if not: "window": "fullscreen" in config.json and tell me. 4 Bleed 2 (Linux) + Circa
    Infinity (Windows) still start. 5 Stranger More: Install -> Play. 6 Settings: ▲▼ / A / B
    feel right. 7 Holding the D-pad scrolls at the same speed as before.
    If broken: logs/launcher.log + app.log. Rollback: rename itch-deck.old to itch-deck.
v0.7.4 Deck test (15 Nov): faster start ✓ "no flicker, opens really quick". Library "37 games" = a
  saved Length filter on All (sync was fine: 129 + 3 every time) -> Omri: filters per tab.
  Bleed 2 ignores the DualSense unless the DualSense started the tile: Steam makes the launching
  pad player 1 and Bleed 2 reads only player 1. Not ours; workaround = start SCRiTCH with the pad
  you'll play with. Later idea (research): hide the other pads from single-player games.
v0.7.5 RELEASED 15 Nov (Omri "push"; branch v075-tabs-splash):
  - Sort & filter per tab: Library.views {tab: {sort, show, genre, length}}, sort/show/genre/length
    are properties on the current tab's view; cfg "library_views" (old library_* keys -> All on
    first load, App._views). Installed starts unfiltered. Mockup 06d. tests/test_library_menu.py.
  - Launch splash: open_display draws W.launch_splash (big logo, SPLASH_U 9u) as the first frame;
    the first page fades in over it (fade_dir 0 = no slide). Steam's logo before our window stays
    (can't draw there). Mockup 00_launch. Gallery updated (+ Settings sidebar 21a/21c/21d).
  - itch answering {"errors": ...} mid-sync raises stores.itch.SyncError (library kept) instead of
    being read as the end of the list.
  Deck checklist v0.7.5: 1 Update. 2 Start from the tile: logo, then the library fades in. 3 All
    keeps your filter; Installed shows every installed game; set a sort on Installed, switch tabs,
    come back: each tab kept its own. 4 Restart SCRiTCH: both remembered.
v0.7.5 Deck test (15 Nov): all ✓. Omri: the launch logo only flashes (start too quick) -> removed
  on branch v076-no-splash (first frame = plain background, no fade; W.launch_splash, mockup 00
  and DESIGN line gone). NOT released.
Epic step 1 RELEASED v0.7.6 15 Nov (Omri "push update"; with the no-launch-logo change; Omri 15 Nov: "build the way a fresh user will", no Heroic): read-only Epic tab.
  - stores/epic.py: legendary downloaded on first Connect (GitHub legendary-gl/legendary latest,
    asset legendary_linux_x64 -> DATA/epic/legendary; >1 MB check). OWN config dir DATA/epic/config
    (LEGENDARY_CONFIG_PATH, chmod 700) = never touches Heroic. login(code) = `auth --code`, ok when
    user.json exists; sync() = `list --json` (legendary Game.__dict__ entries; DLC via
    metadata.mainGameItem skipped; Ubisoft/EA customAttributes ThirdPartyManaged* -> ["other"];
    old "asset_info" = Windows; ids "epic-<app_name>"; cover DieselGameBox first); logout() =
    `auth --delete` + rmtree config. code_from_text(): authorizationCode from the pasted JSON page,
    or a lone 32-hex code. EpicError = short reason; legendary stderr tail goes to app.log.
  - Phone: phonelink PAGES["epic"]: button -> https://legendary.gl/epiclogin (legendary's redirect
    to Epic's login; ends on JSON with authorizationCode, one use, a few minutes). sent_page texts
    per purpose ("Signing in…", "Try again"). _phone_start(purpose, on_text): one page at a time.
  - app_epic.EpicMixin: go_epic() = scene "epic" (ui/scenes/epic.EpicConnect: QR + 3 steps +
    status prep %/phone/checking/rejected/offline/nonet), legendary fetch thread, phone text ->
    login thread -> ok: cfg epic, lib.epic, start_epic_sync, filt "epic", library, toast. B = back
    to Settings. Settings row "Epic Games": Connected as X (A Disconnect: confirm, logout in a
    thread) / Not connected / Signed out (A Connect).
  - Library: epic games merged into lib.games (itch _sync keeps non-itch games); start_epic_sync()
    thread at start (if legendary + config) and on Y; failure = log "epic sync failed", cached
    Epic games kept, itch untouched. Cache keeps store + app_name. queue_prefetch skips url-less.
  - Game page for Epic: no buttons, "Coming soon · Installing Epic games is next." (Game.read_only).
  - Tests: tests/test_epic.py (stand-in legendary script), selftest drives Connect -> phone text
    -> Epic tab -> Disconnect. Mockups 06e, 06f, 15d, 21e, 26, 26b, 26c.
  UNVERIFIED against real Epic (workspace can't reach it): the login page text, list --json speed
  on a real library, token lifetime. Deck log: "epic:", "epic sync".
  Deck checklist v0.7.6: 1 Update. 2 Start: no launch logo, library at once. 3 Settings → Account
    → Epic Games → A: "Getting ready…" then QR. 4 Phone: Open Epic sign-in → sign in → copy the
    whole page → paste → Send: phone "Connected as …", TV jumps to the Epic tab, games + covers
    fill in. 5 Epic game page says Coming soon. 6 Y: itch + Epic still there. 7 Restart: Epic tab
    still there. 8 Disconnect: tab and games gone. If 4 fails: app.log lines "epic:".
v0.7.6 Deck test (15 Nov): all ✓ (Epic sign-in + tab work end to end).
DECISION (Omri 15 Nov): NO per-game Steam tiles for now. He starts games from SCRiTCH; Mouse /
  Keys modes + the quit combo already cover what tiles would solve. Tiles need a Steam restart
  (shortcuts.vdf is read at Steam start) or a Decky plugin. If other players ask: an opt-in
  "Add to Steam" in a game's Options. Next: Epic step 2 (install / play Epic games).
Epic step 2 RELEASED v0.7.7 15 Nov (Omri "All": with fix-dupes + design branch settings-accounts):
  - stores/epic.py EpicStore.install(app, folder, on_progress, cancel, log_file): `legendary install
    <app> -y --game-folder <root>/<game>/files --platform Windows --skip-sdl --skip-dlcs` in its own
    process group; progress from its log lines ("= Progress: N% … ETA: hh:mm:ss", "+ Download - N
    MiB/s"); cancel = watcher thread SIGTERM to the group (legendary keeps a resume file, re-run
    continues); exit != 0 -> EpicError("Not enough space" / "Signed out of Epic" / "Couldn't install");
    exe from legendary's installed.json "executable" (backslashes -> /). Output -> logs/games/
    <slug>-install.log. launch_params(app) = `launch --json --no-wine --skip-version-check`, retry
    with --offline. uninstall(app) = `uninstall -y --keep-files --skip-uninstaller`.
  - installer.Installer._install_epic: GE-Proton + umu first (like itch Windows), card/space checks,
    index entry store "epic", app_name, upload_id = app_name, platform windows, prefix
    <root>/_prefixes/<game> (saves kept). check_updates skips Epic. uninstall also tells legendary.
  - app_play: Epic = launch_params -> exe/args/cwd; egl_parameters (Epic's one-time sign-in
    token) passed as runner.run(secret_args=) and NEVER logged ("<Epic sign-in arguments hidden>").
  - Game page: Epic games get Install/Play like itch; Options = Uninstall, Controls (no Change build).
  - words: "Signed out of Epic" -> "Connect Epic again". Tests: tests/test_epic.py (stand-in legendary
    installs with real-format progress lines, launch json, uninstall, no space, cancel).
  Not yet: Epic updates (games play even if out of date), DLC, cloud saves.
  UNVERIFIED on a real Epic game: progress line format of the current legendary, launch json,
    how a real game runs under umu + GE-Proton (anti-cheat/EOS-online games won't).
  Deck checklist (Epic step 2): 1 Update. 2 Pick a small free Epic game → Install: progress bar with
    % / speed / time left. 3 Cancel halfway, Install again: continues. 4 Play: splash, game starts,
    pad works; hold quit combo returns. 5 Options: Uninstall, Controls (no Change build). 6 Uninstall.
    If broken: app.log "epic:", "install epic-…", logs/games/<game>-install.log and <game>.log.
v0.7.6 BUG (Omri 15 Nov 17:30): itch games x3 in the library. save_cache wrote "store": null for
  itch games; after a restart _sync's "keep non-itch games" (g.get("store","itch") != "itch") kept
  them -> one more copy per refresh. Fix (branch fix-dupes): _prep sets store = store or "itch";
  load_cache drops duplicate ids (repairs old caches). LESSON: g.get(k, default) doesn't cover a
  key saved as null; normalise in _prep. Test: test_itch_games_not_duplicated_after_restart.
OPEN for the design chat (Omri 15 Nov 17:47): the active-filter text was removed from the library
  top bar (v0.7.7) because Omri read "Under 2 h" as his playtime. But a hidden filter is what made
  "37 games" look like missing games this morning, and filters are now per tab. Wanted: the active
  filter shown clearly AS a filter, near the filters (e.g. a chip "Filter: Under 2 h", or on the X
  Sort & filter hint), not as loose text by the count. Omri is taking this to the design chat.
v0.7.7 Deck test (15 Nov): all ✓. Omri: R2 fast scroll choppy, app sluggish; Epic game pages said
  "Loading details from itch.io…" forever.
  Fix RELEASED v0.7.8 15 Nov (with design branch filter-hint; Omri "push update"): Epic keyImages are 2560 px -> library.shrink_cover()
  saves covers at most 720 px (<id>.small.jpg) in the cover worker; covers saved before are shrunk
  once in a background thread (files > 400 KB). widgets: _src() decodes each cover file once
  (shrunk) instead of per size; _LRU caches drop oldest instead of clearing everything at 600;
  _tile_img() caches the rounded (+dimmed) tile; the focus grow animation scales the finished big
  tile instead of loading/scaling the file every frame. Game page: Epic games skip the itch
  "About" message. Bench (/tmp, 130 games, a row every 3 frames, this server ~3-4x a Deck): 2560 px
  covers p95 58 ms / 26 frames > 33 ms -> 720 px covers p95 ~11 ms / 0-1; background shrink
  doesn't stall drawing (pygame releases the GIL).
Epic game pages (v0.7.9, Omri: "yes" to Epic text + Steam; IGDB rejected: needs a Twitch secret
  key per app/user): library._fetch_epic_page = Epic catalog longDescription (game_from_json
  "long_text", markdown/HTML -> steam.html_paras) first; stores/steam.py storesearch (no key) with
  EXACT normalised title match (case, ™®©, punctuation, & = and) -> appdetails: screenshots (max
  MAX_SHOTS, saved like itch shots), genre (filters), and the text when Epic has none. Saved as
  the page json with "source" Epic/Steam (g["details_from"]); footer "From Epic Games ·
  screenshots from Steam" / "From Steam". No match = nothing. Epic games are prefetched like itch.
Steam genres RELEASED v0.8.0 15 Nov (with Epic updates, Details, design-polish, menu-fixed): steam.pick_genre skips
  labels that aren't genres (Indie, Casual, Free to Play, Early Access, Massively Multiplayer,
  Violent, Gore, Nudity, Sexual Content) and uses itch's words (RPG -> Role Playing, Education ->
  Educational). Page json keeps "steam_genres" (full list); v0.7.9 Epic pages without it are
  cleaned at read time (library._genre) and refetched once by the prefetch.
v0.8.0 additions (Omri 15 Nov "yes"):
  - Epic updates: EpicStore.sync keeps .latest {app: Windows build_version} from list --json;
    Library.sync_epic -> on_epic_sync = Installer.check_epic_updates: installed.json "version" !=
    latest -> info/g "update" (badge + Play · Update · ⚙). Update = same _install_epic (legendary
    `install` on an installed game patches only what changed), in the game's existing folder
    (old["dir"]), even if the install location changed since. Update needs lib.epic (not itch).
  - Details (Omri's troubleshooting idea): game ⚙ → Details (installed, or failed) =
    W.details_box with the last lines of logs/games/<slug>-install.log (failed) or <slug>.log
    (last run), else app.log lines with the game id; api_key/key/token/password/code= values
    blanked, tabs -> spaces, 160 chars max. Mockup 16b. Tests in tests/test_epic.py.
Earlier: Epic descriptions (Omri 15 Nov): only the catalog's short "description" shows (game page header).
  v0.7.8 logs "epic text fields: {...}" after each Epic sync (counts of description /
  longDescription / shortDescription / technicalDetails / screenshot keyImages + one long sample).
  Next: if many have longDescription -> show it as "About this game" (cheap, no new requests);
  Epic store pages (full text + screenshots) only if the catalog is thin (unofficial, fragile).
v0.8.0 Deck test (15 Nov): all ✓ except the install-done feedback: no toast, no ✓ pop when Omri
  waited on the game page (toast skipped on the game's own page; pop needed the library to have
  drawn the tile busy). Fix on branch done-feedback (NOT released): App._install_events always
  toasts "done" and calls W.mark_done(gid) so the ✓ pops next time the tile shows (RELEASED v0.8.1 with design-polish progress glide + shine). Test in
  tests/test_library_menu.py.
OPEN (Omri 15 Nov: "ruminate some other time"): Details shows raw log lines - useless to a casual
  player. Idea on the table: "Get help" = the plain reason + a QR that opens the full log on the
  phone (phonelink) to send to whoever helps; no log text on the TV. Not decided.
v0.8.4 RELEASED 16 Nov (Omri: "you can push when done") = ROADMAP 1, save backups (branch
  save-backups). Omri: automatic after every play, visible Documents folder.
  - backups.py: ~/Documents/SCRiTCH saves/<Title>/<YYYY-MM-DD HH-MM-SS>[ before restore].zip, KEEP 5,
    about.json (id, title, linux_dirs, fingerprint). Same title, other game -> "<Title> (<id>)".
    Windows (itch + Epic): prefix drive_c/users/steamuser {AppData/Roaming, LocalLow, Local,
    Documents, Saved Games}, SKIP cache-like dir names, files > 100 MB and *.log/.tmp/.lock/.pid.
    Linux: learn() after each play = folders under ~/.local/share, ~/.config, ~/.local/state with
    files modified since play start (NOT_GAMES list: Steam, flatpak, KDE, …; godot/app_userdata/X
    and unity3d/<studio>/<game> one/two levels deeper, love/X). Backup only when the fingerprint
    (names, sizes, mtimes) changed. Not covered: games that save inside their own install folder.
  - Restore: backup(note="before restore", protect=z) first (prune never deletes the zip being
    restored: bug found by test), writes files over (nothing deleted), path-traversal guarded,
    then stores the restored fingerprint (no new backup until the saves change).
  - App: app_play._backup_after_play (thread; toast via self.backup_note, shown in update()).
    ⚙ menu "Saves" on installed games -> picker ("saves") -> confirm "Put back" -> thread.
    Codes S01 (backup failed), S02 (restore failed).
  - Tests: tests/test_backups.py (Windows keep-5 + restore + undo, Linux learning, same title,
    unsafe zip). Selftest: the fake game writes a save -> learned, backed up, put back.
  - Mockups 15b (Saves in ⚙), 15k_game_saves, 15l_game_saves_confirm (15i/15j are the design
    chat's). Gallery: the design chat owns its layout now; add screens with publish_files
    mode PATCH + a small edit_version in "Current work". Never mode replace.
  Deck checklist v0.8.4: 1 Update. 2 Play any game a few minutes and save in it; quit -> "Saves
    backed up." 3 ⚙ → Saves lists it. 4 Dolphin: Documents/SCRiTCH saves/<game>/ has a zip.
    5 Play again without saving -> no new backup. 6 Put back the older one -> "Saves put back."
    and the game loads it; Saves now shows a "Before restore" entry.
GOG PLAN (sent to Omri 16 Nov 11:12, waiting for "go" on step 1; code chat handed over to a new chat):
  Helper = Heroic's gogdl (GPL-3, Python; gogdl manages auth itself, tokens in a json file we
  choose, e.g. DATA/gog/auth.json). Opt-in like Epic: tab only after connecting, helper downloaded
  on demand; if gogdl has no Linux release binary, vendor it (pure Python + requests) inside our
  build instead. Check this first.
  Sign-in by phone: QR -> phone page -> "Open GOG sign-in" (auth.gog.com, Galaxy client id) ->
  GOG ends on embed.gog.com/on_login_success?...code=… -> player copies that page's ADDRESS,
  pastes it on our phone page -> Send -> gogdl auth with the code -> "Connected as …".
  Library: GOG API (owned games + product details: text, screenshots; covers); genre + time to
  beat like other stores. Tabs: All · Installed · itch · Epic · GOG; GOG games in All like Epic.
  Steps, one update each: v0.9.0 sign-in + read-only GOG tab (medium, 1 session). v0.9.1 install /
  play / uninstall (Windows via Proton like itch; Linux native when GOG has it; launch from
  goggame-<id>.info playTasks; save backups + Move work automatically) (medium-large, own Deck
  round). v0.9.2 game updates (small-medium). Later: GOG DLC, GOG cloud saves (gogdl save-sync).
GOG step 1 = v0.9.0 RELEASED 16 Nov (Omri "go" 11:17, "push" 11:28; branch gog-signin; was
  built at 0.8.5, bumped on release. Other unmerged branch at release: design-tabs only = scrapped).
  - gogdl check: release asset gogdl_linux_x86_64 (PyInstaller, built on ubuntu-24.04) exists ->
    downloaded on demand like legendary (DATA/gog/gogdl, >1 MB check). gogdl has NO library list
    command: it only does sign-in + token refresh (`--auth-config-path DATA/gog/auth.json auth
    [--code C]`, prints JSON; {"error": true} on a bad code, stderr "Failed to reach GOG" offline).
  - stores/gog.py: code_from_text (code= in the pasted address, or a lone long code), login ->
    auth.json 600 (dir 700) + user.json {username} from embed.gog.com/userData.json; token() =
    `gogdl auth` (refreshes); sync = embed.gog.com/account/getFilteredProducts?mediaType=1&page=N
    with the token (isGame false skipped; worksOn -> platforms; image + "_392.jpg" cover;
    category kept as g["category"]); ids "gog-<product id>", app_name = product id. details() =
    api.gog.com/products/<id>?expand=description,screenshots (public): description.full HTML ->
    steam.html_paras, screenshots formatter "ggvgl". logout = delete auth.json + user.json (local).
    GogError short reasons: "Not signed in" / "Signed out of GOG" (401) / "Couldn't reach GOG".
  - library: lib.gog, start_gog_sync/sync_gog/drop_gog (same isolation as Epic; keeps itch + Epic
    games), _fetch_gog_page (genre = category in itch words via _GOG_GENRES, source "GOG"),
    cache keeps "category".
  - App: app_gog.GogMixin (copy of the Epic flow: go_gog, scene "gog" = ui/scenes/epic.GogConnect
    = EpicConnect with TITLE/STEPS/STATUS class attributes), phonelink PAGES["gog"] (button = GOG
    Galaxy login URL; "copy its address"), Settings → Accounts row "Sign in to GOG" / "Sign out of
    GOG" (row added after Epic: Storage/Games rows shifted one index; mockups 21c=5, 21h=7).
    Tabs All · Installed · itch · Epic · GOG (App._stores). Y and Settings → Refresh library now
    sync every store (Refresh library didn't sync Epic before; DESIGN §6 says it should).
  - Game page for GOG: Game.read_only -> no buttons, no ⚙, info box "Coming soon · Installing GOG
    games is next."; cover not dimmed; "From GOG" under About.
  - Tests: tests/test_gog.py (stand-in gogdl script + stubbed net.get_json: code parsing, sign
    in/list/sign out, rejected/offline, sync errors, merge keeps other stores + no duplicates +
    survives restart, page text/shots/genre, read-only page, 3 store tabs). Selftest _selftest_gog
    (sign in via phone text -> GOG tab -> Coming soon page -> sign out). Mockups 21j, 27, 27b,
    06g_library_gog_tab, 15q_game_gog; Deck gallery "Current work" updated (PATCH). Phone pages
    gallery NOT yet updated with the GOG phone page (its index.html is 68 KB; do it with the
    release if Omri wants).
  - Checked: pytest 3.13 + 3.11 (139), selftest 3.13 + 3.11, selftest with itch rejecting every
    key, mockups (176).
  UNVERIFIED against real GOG (workspace can't reach it): the _392.jpg cover suffix, category
    field names, whether the phone browser shows the on_login_success address with the code,
    gogdl binary running on SteamOS. Deck log: "gog:", "gog sync", "page gog-…".
  Deck checklist v0.9.0: 1 Update. 2 Settings → Accounts → Sign in to GOG: "Getting ready…" then
    QR. 3 Phone: Open GOG sign-in → sign in → copy the address of the blank page → paste → Send:
    phone "Connected as …", Deck jumps to the GOG tab, games + covers fill in. 4 Open a GOG game:
    text + screenshots, Coming soon box. 5 Y: itch, Epic, GOG all still there. 6 Restart: GOG tab
    still there. 7 Sign out of GOG: tab and games gone.
v0.9.0 Deck test (16 Nov 11:41): ✗ Deck "Can't reach GOG. Check Wi-Fi", phone stuck on "Signing
  in…". Cause (most likely, no log yet): the gogdl download failed. gogdl's build.yaml makes the
  Linux file in a separate zipapp job and publishes releases as hand-made DRAFTS, so the asset
  name/presence on "latest" isn't reliable; my v0.9.0 check only read the workflow. The phone hung
  because the login waited for job["ready"], which never came, so phone_status never changed.
Fix v0.9.1 RELEASED 16 Nov (Omri "push" 11:51; branch gog-fix-signin; only other branch design-tabs = scrapped):
  - stores/gog.py signs in WITHOUT gogdl: _ask() = GET auth.gog.com/token (client id + secret
    from gogdl/auth.py; grant authorization_code with redirect_uri, or refresh_token); HTTP 4xx =
    refused (False), other failures = GogError "Couldn't reach GOG". _save() writes gogdl's own
    format {CLIENT_ID: data + loginTime} (600, dir 700) so step 2's gogdl can use it. token()
    refreshes 60 s before expiry; refused refresh = "Signed out of GOG". ready() = True;
    fetch_gogdl / bin_path / subprocess removed. Step 2 must decide how gogdl comes (vendor the
    pure-Python package into our build, or the zipapp asset if a release has it).
  - Phone never stuck: Epic's tick clears waiting phone text and says "can't reach Epic" when
    legendary couldn't be fetched (same bug, Epic side).
  - Tests: test_gog.py stubs net.get for auth.gog.com/token (+ refresh test). Selftest stubs
    GogStore._ask. Checked pytest 3.13 + 3.11 (140), selftest both, itch-reject selftest, mockups.
  Deck checklist v0.9.1 = v0.9.0's GOG list (steps 2-7). If it fails: app.log lines "gog:".
v0.9.1 Deck test (16 Nov 11:58): all ✓ (Omri). GOG step 1 DONE. Next: GOG step 2 (install / play).
GOG step 2 = v0.9.2, APPROVED by Omri 16 Nov 12:00 (handed to a new code chat), and he said:
  PUSH WHEN DONE (no extra "push" needed for this one update; still check other branches first,
  and still run every check). Plan as sent: vendor gogdl into our build (pure Python + requests,
  GPL-3, run in-process / as a hidden `scritch --gogdl …` mode via sys.executable — NOT the GitHub
  release asset, which is unreliable); install via `gogdl download <id> --platform linux|windows
  --path <root>/<game>` with progress + cancel + resume like Epic; Linux build when GOG has one,
  else Windows via umu + GE-Proton; launch from goggame-<id>.info playTasks (primary task, path,
  arguments, workingDir); ⚙ = Uninstall / Controls / Saves / Move (no Change build); auth file =
  DATA/gog/auth.json (already gogdl's format, written by stores/gog.py since v0.9.1). Risk: games
  needing redist / first-run setup -> error code, fix per game after the Deck test.
v0.9.3 RELEASED 16 Nov (branch v093-fixes; Omri "include everything, go and push") = v0.9.2 Deck test fixes
  + design chat's design-notice-align (merged in; only design-tabs left unmerged = scrapped).
  v0.9.2 Deck test (Serious Sam, GOG): installed + played ✓. ✗ "0 MB of 0 MB" (GOG/Epic lists
  have no sizes); ✗ Auto = Pad (GOG has no Inputs row) -> pad ignored until Keys; B = Esc in Keys
  is by design (Esc = pause menu). ✗ game page: back UP from screenshots left the screenshot
  focus outline drawn. Omri also wants focus "a little greyer" + a light sweep.
  - Size: GOG = gogdl info "need" -> size_mb before the download; Epic = legendary "Install size:
    N MiB" line (EpicStore.install on_size). Both show "Starting…" (phase "queued") until the
    helper's first progress line. Game page: unknown size -> speed only, never "0 MB of 0 MB".
  - Controls Auto for GOG / Epic: page json "pad" (True/False/None) -> "inputs" via
    library.inputs_for (True -> Gamepad, False -> Keyboard+Mouse = Keys, None -> Pad). GOG:
    api.gog.com/v2/games/<id>?locale=en-US _embedded.features id "controller_support"
    (gog.pad_from_json, walks any "features" list). Epic: Steam appdetails categories
    "Full/Partial Controller Support" (steam.pad_from); no Steam match -> None. Pages without
    "pad" refetch once. VERIFIED live by .github/workflows/stores-live.yml (branch pushes touching
    gog.py / steam.py): Stardew True, Heroes 3 False, Serious Sam TFE (1440163901) False; Steam
    Celeste True, Heroes 3 HD False. GOG's flag is sometimes missing on pad games: Controls
    override stays.
  - Game page: leaving the screenshot strip keeps redrawing the cached page 0.6 s
    (Game._shots_settle) so the focused screenshot shrinks back (was frozen grown + outlined).
    Play WAS focused on entry (bright purple) but didn't read as focus -> the sweep.
  - Focus look (theme focus_fill (88,86,124) -> (92,92,112), greyer) + W.focus_sweep: soft
    leaning light band across focused buttons (incl. purple / red ones) and rows, every 2.8 s,
    moving 40% of it; mockups draw it halfway. DESIGN §3 updated. UI files touched by the code
    chat on Omri's request (tell the design chat).
  - Tests: test_gog controller flag + refetch, Starting -> size before download. Checked pytest
    3.13 + 3.11 (147), selftest both, itch-reject selftest, mockups (180).
  Deck checklist v0.9.3: Starting… then MB of size (GOG + Epic); Serious Sam ⚙ Controls = Auto ·
  Keys (after its page reloads once); focus sweep on buttons/rows; screenshots -> up -> no outline.
GOG step 2 = v0.9.2 RELEASED 16 Nov (branch gog-install; pushed under Omri's "push when done").
  Other unmerged branches at release: design-tabs (scrapped) and design-notice-align (design chat,
  12:02, game-page notice alignment; NOT merged, told Omri).
  - gogdl VENDORED: itch_deck/vendor/gogdl = heroic-gogdl 6c6ef53 (1.4.0), unchanged + LICENSE;
    vendor/README.md says how to update it. Its C extension gogdl_xdelta3 (patch files, only
    for updates) is a stand-in that raises -> GOG STEP 3 must build it or update by chunks.
    Runs as a hidden mode of our own binary: run.py / __main__ `--gogdl <args>` ->
    itch_deck/gogdl_mode.run (multiprocessing "fork", no pygame). build.sh: --paths
    itch_deck/vendor --collect-submodules gogdl --hidden-import gogdl_xdelta3 requests;
    requirements + requests. CI checks `release/scritch --gogdl --version` = 1.4.0. Checked
    here: frozen build runs gogdl, requests + certifi bundled ("info" reached the proxy).
  - stores/gog.py: helper_cmd() (frozen: [exe, --gogdl]; source: run.py), env = child_env +
    GOGDL_CONFIG_PATH=DATA/gog (gogdl's manifests/exclude in DATA/gog/heroic_gogdl). _prepare:
    our token refresh + an empty exclude/<id> file (gogdl opens it unchecked). info() = `gogdl
    info` -> need bytes ("*" + en-US disk_size, Linux disk_size), build id, version.
    install() = `gogdl update <id> --platform P --path <game>/files --lang en-US --skip-dlcs`
    (update = no extra folder level; empty folder = full download; .gogdl-resume resumes),
    progress "= Progress: 37.00 a/b … ETA: hh:mm:ss" + "+ Download - N MiB/s", cancel = SIGTERM
    to its group. Fresh install drops a leftover manifest (else files count as present).
    launch_info(): Linux = start.sh (chmod +x); Windows = goggame-<id>.info primary FileTask
    (path/workingDir matched case-insensitively, string arguments shlex-split like gogdl, cwd =
    game root when no workingDir, like gogdl). "setup" = goggame-*.script present (first-run
    setup we don't run). forget() = delete manifest (uninstall).
  - installer._install_gog: Linux build when GOG lists Linux, else Windows (GE-Proton + umu
    first); Linux failing with "Couldn't install" -> Windows tried. Space check from info.
    install.json: store gog, app_name, platform, exe, args, cwd, build_id, version, prefix
    (Windows), setup. Codes: I05 (gogdl failed), I06 (nothing to start), P03 (crash + setup
    scripts). words: "Sign in to GOG again", "Couldn't reach GOG" -> No internet.
    check_updates skips every non-itch store.
  - app_play: GOG args/cwd from install.json. Game page: read_only gone; GOG ⚙ = Uninstall /
    Controls / Saves / Move (no Change build, like Epic). Saves + Move need nothing GOG-specific.
  - FIXED (bug since v0.7.6): App start with an itch key but NO Epic went to Setup ("waiting")
    and GOG only synced when Epic was connected (else attached to the Epic if). Now inside
    `if key:`; both stores sync on their own.
  - Tests: test_gog.py stand-in gogdl (Windows + Linux + fallback, progress, space x2, I06,
    cancel, setup flag, signed out, launch_info), real vendored gogdl --version/--help + import
    with the xdelta stand-in. Selftest: GOG game installs (stubbed) -> Play + ⚙ -> uninstall.
    Mockups 15q (Install), 15r (downloading), 15s (⚙). Checked pytest 3.13 + 3.11 (145),
    selftest 3.13 + 3.11, itch-reject selftest, mockups (180), PyInstaller build.
  UNVERIFIED (no GOG here): real gogdl downloads on the Deck (fork workers in the frozen
    build, 1 GiB shared memory), Linux installer layout (start.sh at the root), how many
    Windows games need their first-run setup (VC++ etc.; P03).
  Deck checklist v0.9.2: see the release message (install Windows game, cancel/resume, play,
    quit combo, saves, move, uninstall, Linux-build game, a game failing -> code).
v0.8.5 RELEASED 16 Nov 11:00 (Omri "push") = Move games + Controls row + design-balance docs.
  Omri 16 Nov 10:30 "go" incl. the registry address fix.
  - installer: move_target(gid, config.install_choices()) -> the other drive (needs 2 choices,
    game not queued/downloading/moving, card present). move() -> thread _move: size check (+200 MB),
    copy game + prefix into <dest>/_moving/{game,prefix} (_copy_tree: links as links, chunked,
    tick() = progress + cancel), check same size + count, os.rename into place (same drive),
    fix_registry(prefix, old_root, new_root) (.reg text: Z:\\…\\ escaped + plain, whole folder
    names), update index (dir, prefix) + Epic installed.json install_path (EpicStore.moved), write
    installed.json = THE SWITCH, then rmtree old game + prefix. Before the switch nothing old is
    touched. Cancel (MoveCancelled) / errors -> old copy kept, _moving removed. clean_moves() at
    start removes a <root>/_moving left by a crash. Codes M01 (unexpected), M02 (folder taken by
    another install), M03 (copy mismatch). State while moving: downloading/phase "move", move_to.
  - UI: ⚙ "Move to SD card" / "Move to internal storage" (App.open_options computes it), purple
    confirm, game page "Moving to … 45%" + Cancel ("Cancel the move?"), footer "Moving 45% · Title".
    W.modal(danger=False) + confirm(..., main=True) = purple action for non-destructive confirms
    (Move, Put back); Uninstall/Quit stay red. Mockups 15n/15o/15p, 15l now purple.
  - Tests: tests/test_move.py (both ways + registry + links + Epic record + space + cancel + bad
    copy + leftovers + not while busy). Selftest moves the fake game.
  Deck checklist v0.8.5: 1 Update. 2 ⚙ on an installed game: Controls row ◀ ▶ changes it
    (Auto shows its pick). 3 Move a small Linux game to internal and back: progress, "moved to",
    plays. 4 Move one Windows game that came with a setup.exe, then play it + check saves.
    5 Start a move and Cancel: game stays and plays. 6 An Epic game: move, play.
Controls row (branch controls-row, NOT released; Omri 16 Nov 10:20 "like the filter sorter"): the
  ⚙ Options menu's Controls row shows its setting (App.controls_value: "Auto · Pad" / Pad / Mouse /
  Keys) and ◀ ▶ (or A) change it in place, menu stays open (_h_game; cycle_controls(step)).
  Footer on that row: ◀ ▶ Change. Toast only for Mouse/Keys (how the mapping works). Game page
  line unchanged (only shows for Mouse/Keys). Mockups 15b (value), 15m_game_options_controls.
  Selftest drives it.
ROADMAP NOW (Omri 16 Nov 09:38, replaces the list below; done: 1 rename = v0.8.2, 2 error codes
  = v0.8.3). One item per update, plan + size first: 1 Save backups (copy a game's saves to a safe
  folder + restore; all stores). 2 Recently played as a Sort & filter sort. 3 Move a game between
  SD and internal (⚙ menu, saves too). 4 GOG tab like Epic (Heroic's gogdl helper on demand, phone
  sign-in with pasted address; ~2-3 updates). 5 Epic DLC. 6 Epic cloud saves. 7 Ready to share
  (postponed: "still more to build"). Not picked: favourites / hiding games. Hide extra pads:
  Omri asked why (explained 16 Nov), undecided. Design work moves to a fresh DESIGN chat
  (branches design-<topic>); this chat = code, merges, releases.
ROADMAP (Omri 15 Nov 20:23, after v0.8.1; page: https://claude.ai/artifact/Hkk8SQChbBUBbAJ1yVEbqo),
  one item per update, in this order:
  1 Rename folders itch-deck -> scritch (moves user data: plan + size first, migration with
    fallback, keep old paths readable). 2 "Get help" instead of Details (plain reason + QR that
    opens the full log on the phone via phonelink; no log text on the TV). 3 Ready to share
    (README / install steps for strangers, fresh-Deck first-run check, logo SVG from Omri).
  4 Epic DLC. 5 Epic cloud saves (legendary sync-saves; risky: own update + test round).
  Later: browser games, opt-in "Add to Steam" per game, hide extra pads for player-1-only games.
  Decided against: auto Steam tiles, IGDB (secret key), reading Epic from Heroic.
  Needs a Deck test, not code: itch update detection, split installer (Stranger More), Epic long
  descriptions count ("epic text fields" log line), Epic game updates.
v0.8.3 RELEASED 16 Nov (Omri "push" 09:19) = ROADMAP item "error codes instead of Details" (branch error-codes; Omri
  "go" 16 Nov 01:11). Omri 16 Nov: no log, no QR, no new buttons on the TV; keep the log on disk.
  - words.CODES = the one list (letter = where: I install, W Windows/GE/umu, P play, L library,
    U app update; E reserved for Epic sign-in if ever needed). words.Coded(msg, code) is the base of
    InstallError and ProtonError. Rule: words.short() hint the player can act on WINS; only when
    there's no hint does the screen get "Code X" and app.log "ERROR CODE X: <full reason>"
    (words.log_code). Messages that already say what to do get no code.
  - Where: installer._fail (game page "Couldn't install / Code W09", toast when off the page; I01 =
    unexpected, logged with traceback), play crash without hint P01, Mouse/Keys P02, library refresh
    L01, Settings GE-Proton download (hint or code, W11 = unexpected), app update download U01
    (shown in the Settings update row). "Details are in the log" removed from every message.
    words hint added: "No internet" (EpicError text) -> "No internet".
  - Details removed: game ⚙ menu entry, app_game.details_lines, W.details_box, mockup 16b_game_details,
    its test. Mockups: 16_game_failed shows "Code W09", new 10b_library_toast_code. Gallery
    republished (3 screens). tests/test_codes.py: every code used is listed and every listed code is
    used, no screen text mentions the log, hint beats code, I01 fallback.
  - README "Reporting a problem" (tell us the code; attach ~/.local/state/scritch/logs/app.log if
    asked) belongs to ROADMAP "Ready to share".
v0.8.2 RELEASED 15 Nov (Omri "push"; branch rename-scritch) = ROADMAP 1, folder rename:
  - paths: NAME "scritch", OLD_NAME "itch-deck". paths.migrate() runs first thing in main (before
    logging/config/lock): per XDG base (config / data / state) old real dir + no new -> os.rename
    (same disk: no copy, no space, instant) + relative symlink itch-deck -> scritch, so a rollback
    to v0.8.1 still finds everything. Both exist -> use new, log, never merge/delete. Rename fails
    -> that folder stays in use under the old name this run (paths._repoint), retried next start.
    app.log lines "folders: moved …". tests/test_migrate.py.
  - launcher.sh: app binary app/scritch (PyInstaller --name scritch). It logs into state/itch-deck/
    logs while that's still a real folder and state/scritch doesn't exist, so it never creates
    the new folder before the app moves the old one (test in test_launcher.py).
  - Release: build.sh makes release/scritch + a copy release/itch-deck; CI publishes BOTH (v0.8.1
    and older only look for "itch-deck"). updater.ASSETS = ("scritch", "itch-deck"), first found.
    Keep publishing itch-deck for a while (until nobody is on <= v0.8.1).
  - NOT renamed (Omri agreed): the tile's folder ~/Applications/itch-deck/ (launcher doesn't care
    about its folder name; README says ~/Applications/scritch/scritch for new users; Omri can move
    his by hand + edit the tile Target); existing games folders "itch" (Wine prefixes + legendary
    store full paths). config.games_dir(base) = base/itch if it exists, else base/scritch (new
    users; Epic games live there too). Python package itch_deck + GitHub repo name: unchanged
    (package rename = conflicts with the design chat; repo rename maybe at ROADMAP 3).
  - Logger name "scritch" everywhere, net UA "scritch (+repo)", argparse prog, README paths.
  - Checked: pytest 3.13 + 3.11 (117), selftest 3.13 + 3.11 (also run with old-layout XDG dirs:
    moved + links), selftest with itch rejecting every key, mockups (only the version number
    changed: 21, 21d, 21g -> gallery not republished). Real PyInstaller build run as Omri's Deck:
    v0.8.1-style ~/Applications/itch-deck/{itch-deck, app/itch-deck} + old XDG dirs -> new file
    in the tile path unpacks app/scritch (old app -> app.old), folders moved, old launcher.log kept,
    pinned SD install_root untouched.
  Deck checklist v0.8.2: 1 Settings -> App -> Update -> restarts into v0.8.2. 2 Library, covers,
    filters, itch + Epic sign-ins all still there (nothing to sign in again). 3 Dolphin (hidden
    files on): ~/.config, ~/.local/share, ~/.local/state each have a scritch folder and an
    itch-deck link (arrow icon). 4 Install + play one small game; uninstall it. 5 Quit, start from
    the tile again. If anything is missing: ~/.local/state/scritch/logs/app.log lines "folders:".
    Rollback: rename itch-deck.old to itch-deck in ~/Applications/itch-deck/ (old version reads
    the same data through the links).
Two copies bug (in v0.7.2): v0.7.1 Deck log shows two app
  copies after the update restart (11:25:56 + 11:25:59; also 14 Nov 16:27 after v0.2.4) -> every
  HLTB line twice + hltb.tmp FileNotFoundError x15. Cause not proven (2nd start args=[], 3-4 s
  after the execve restart). Fix: paths.lock_instance() (flock DATA/scritch.lock, freed on
  exit/exec; 2nd copy logs "another copy is already running (pid N), quitting"), paths.tmp_for()
  per process/thread temp names (library._write_json, config.save). tests/test_instance.py.
  Deck check after release: update app -> app.log shows ONE "start" after "restarting into", or
  the "another copy" line; no hltb.tmp errors.

## Epic decision (Omri 15 Nov): ONE codebase, no fork, no second build. Epic is (1) opt-in: the
  Epic tab only exists after Settings -> Connect Epic; until then scritch = itch only, exactly as
  now; (2) isolated: legendary runs as a separate process, Epic errors stay in the Epic tab, itch
  never depends on it; (3) downloaded on demand: legendary is fetched on first Connect Epic (like
  umu / GE-Proton), NOT bundled. Licence GPL-3 anyway.

## Epic tab - research 15 Nov (Omri: only if importing the library is easy)
  legendary (open-source Epic CLI, Python) does it all: list (JSON), install -y, launch
  --dry-run (gives the command to run ourselves via umu + GE-Proton, like itch Windows games),
  uninstall. Login is the hard part (browser + copy an authorizationCode) BUT Heroic is already on
  his Deck: it runs legendary with its config under <heroic config>/legendaryConfig (flatpak:
  ~/.var/app/com.heroicgameslauncher.hgl/config/heroic/). If he's logged in to Epic in Heroic,
  scritch can reuse that login: no login screen at all. Plan if wanted: step 1 (1 session) =
  read-only Epic tab (library + covers via Heroic's legendary login) = the "is importing easy" test;
  step 2 (1-2 sessions) = install/progress/uninstall/launch through legendary + umu.
  Limits: anti-cheat/EOS-online games won't work (same as Heroic). Heroic can already add Epic
  games as Steam tiles, so the tab is mainly "one library".

## Future (optional) milestones
- M7 browser games (Omri 14 Nov: optional, after M6). Plan: download the HTML5 upload zip (itch's
  own app plays these offline), serve it from a local http.server (fixed port per game so
  localStorage saves survive; send COOP/COEP headers for Godot 4 web), launch Chromium flatpak
  --kiosk like a game (display handoff as runner.run). Needs Chromium from Discover once.
  Open: games hosted only on the dev's site stay "browser only"; a quit shortcut (web games have
  no Quit); keyboard-only games need a Steam Input layout. ~1–2 sessions + 30 min Deck.

## Token usage log (Omri's Pro plan %, as he reports it — add a line each time)
- 2026-11-14 00:08 — 72% at start of M0 build (planning + M0 in one chat)
- 2026-11-14 11:24 — 73% → 76% for M1 mockups (+ logging M0 Deck results) = 3%
- 2026-11-14 12:01 — 80% → 81% for M2 build = 1%
- 2026-11-14 15:23 — 82% after M2 fixes v0.2.1–0.2.3 (+ self-update); v0.2.4 feel pass starts here
- 2026-11-14 16:39 — 83% at start of M3 build
- 2026-11-14 17:43 — 87% at start of design pass
- 2026-11-14 18:10 — 88% at start of M4 build
- 2026-11-14 18:44 — 92% at start of M5 build
- 2026-11-14 22:07 — v0.6.1 (SD pin + AppImage) after M5 Deck test; % not reported

## Phone Send + chasing spinner + principles (15 Nov)
- Phone form: Send is full width of the form, grey (disabled) until something is pasted, then
  purple (small inline script; server still answers "Nothing was pasted." without JS).
- Busy spinners chase: `W.chase()` (front edge races ahead, back edge catches up, slow turn,
  `CHASE_S` 1.4 s) drives `W.spinner` and `W.ring(busy=True)`; phone `.spin` is the same
  motion as an SVG dash animation. Mockups draw one still pose.
- DESIGN.md rewritten as 10 principles, each with its reason. Rules unchanged except buttons:
  "a button is as wide as the block it belongs to".

## Settings sidebar (15 Nov, Omri picked option A)
- Settings = categories left (App · Account · Storage · Games · Controls), settings right.
  Omri: more future proof for more platforms and settings. Version + update live in the App
  card (the version line at the bottom that overlapped the list is gone).
- `Settings.focus` is still a flat index (app + selftest act on `items()[focus]`); setting it
  jumps into that category. `side` = focus on the category list; app_settings routes A/B to
  the scene while on the sidebar / to leave a category.
- Shown names differ from internal labels (`settings.SHOWN`); the app still acts on the old ones.

## Settings regroup for Epic (15 Nov, Omri)
- App = update card + Refresh library (syncs every store). Accounts = per store, same words:
  "Sign out of itch" / "Use a new itch key" / "Sign in to Epic" or "Sign out of Epic" (name on
  the right). Games and Controls merged into "Games & controls". Epic dialog: "Sign out of Epic?".
- Expect more moves while Epic lands; categories are cheap to reshuffle in `Settings.groups()`
  (app acts on internal labels, `shown()` makes the words).
- Library top bar: filter summary removed (count only).

## Filter visible as a filter (15 Nov)
- Omri removed the plain "Under 2 h" because it read like his playtime, then games looked missing.
  Now: purple tag "FILTER: UNDER 2 H" + "12 of 30 games" in the top bar; a tab the filter
  empties says "No games match this filter. Press X to change it." (not "No games yet").
- Footer left = background work on every screen (spinner + text) or the update notice; the
  Library top bar keeps only filter tag, count and offline. `Scene.footer_status()`; the app
  sets `scene.activity` / `scene.notice` every frame.
- Grid never scrolls past the last row (last row sits on the bottom edge; a tab that fits
  doesn't scroll). A–Z strip in the right margin when sorted A–Z and the list scrolls: the
  focused game's letter purple, letters with games dim, others faint. Indicator only.
- "Use a new itch key" removed (Omri): sign out + sign in covers a revoked key and a different
  account, and itch now reads like Epic (one row). Rejected-key error: "Sign in to itch again".
- A–Z strip slides in from the right while moving, out 1.5 s after the last move (`ABC_HOLD_S`).
- Sort & filter: "Clear filters" row label is purple (`W.ACTION_ROW`), white when lit (Omri: text, not a button).

## Genre fix (15 Nov)
- Genres were empty in v0.7.8: genre/inputs lived only in the saved page and were read back
  only when a game page opened; start-up and every sync rebuilt games without them, and the
  prefetch skips games whose page already has a genre. `_prep` now reads genre + inputs from
  the saved page for every game (test: test_genre_survives_restart_and_sync).
- Sort & filter keeps one size: Clear filters is always there (`W.OFF_ROW` = faint, skipped
  by ▲▼, until a filter is on). Empty-state lines draw pad glyphs inline (`W.text_glyphs`,
  "Press {X} to change it.").

## Polish batch (15 Nov)
- Game page: control mapping on line 2 (from itch Inputs, only when not plain pad); free space
  after the size before installing (red if it won't fit).
- "… is ready to play." toast + ✓ pops on the tile when an install finishes.
- Build problems say "Try another build in Options"; missing game "Refresh your library".
- A–Z: L2/R2 jump to previous / next letter (back = start of this letter first).
- Covers: dark purple shimmer while loading, fade in on arrival.
- Game page balance (buttons under the text instead of on the cover's bottom edge): mockup
  only, waiting for Omri.

## Todo (Omri)
- Logo font: pick a font, then make SCRiTCH an outlined SVG (colours baked in) used by the app
  wordmark, the phone pages and the README, so it looks the same everywhere. Check the licence.

## Design chat 16 Nov (branch design-balance: DESIGN.md + NOTES only)
- Galleries were behind: the Deck gallery held only the last batch (3 screens), the phone gallery
  had no Epic pages and said v0.7. Both rebuilt (see working rules above).
- DECIDED (Omri): no "balance". Game page buttons stay on the cover's bottom edge so every page
  looks the same whatever the description length. In DESIGN.md §6.
- DECIDED (Omri): Setup's technical words (API keys, itch_key.txt, ~/Downloads, Warpinator,
  Steam + X, RustDesk, the QR address) are needed for onboarding. DESIGN.md §10 exception.
- SCRAPPED (Omri 16 Nov): centred tab carousel (chosen tab dead centre, row slides, opacity
  ramp, soft band). It clashed with the info on the right (count, filter tag). Tabs stay next to
  the logo with the purple underline. Don't re-propose. Branch design-tabs = scrapped, NEVER
  merge it (couldn't delete it from here; Omri can delete it on GitHub).

## Logo (16 Nov, branch design-logo)
- Omri's SVG: `itch_deck/assets/logo.svg`; `W.wordmark` draws it (cap height of Inter Bold at
  `size`, same baseline/box as before), text fallback if SDL_image can't read SVG. Phone pages
  inline it on top (`phonelink.LOGO`); headings under it drop " to SCRiTCH" (tab title keeps it).
  README uses `<picture>` with `docs/logo-on-light.svg` (white parts -> #10101e) for GitHub light.
- Steam art: `packaging/steam_art.py` -> `packaging/steam-art/` tile 600x900, wide-tile 920x430,
  hero 3840x1240, logo (transparent), icon 256 (the i alone). README step 4 sets it by hand.
  FOR THE CODE CHAT (optional): the app could copy these into Steam's grid folder itself
  (userdata/<id>/config/grid/<shortcut appid>p.png, .png, _hero.png, _logo.png, _icon.png).

## Design merges 16 Nov (code chat, Omri 13:14)
- design-balance + design-notice-align were already in main (v0.9.3); design-logo merged (fast-forward)
  after main: pytest 3.13 + 3.11 (147), selftest both, itch-reject selftest, mockups (180).
- packaging/steam-art/*.png were NOT in design-logo: .gitignore has *.png, so the README link
  pointed at nothing. Generated with packaging/steam_art.py and added with `git add -f` (144 KB).
  Regenerate + `git add -f` again whenever the logo changes.
- Not a release: VERSION stays 0.9.3 (CI builds, skips releasing). The logo ships with the next one.

## ROADMAP 3 "Ready to share" — new item (Omri 16 Nov 13:24): SCRiTCH sets its own Steam art
- Ship packaging/steam-art/*.png in the release (build.sh --add-data, like assets).
- On start: find SCRiTCH's own non-Steam shortcut = the entry in
  ~/.local/share/Steam/userdata/<user>/config/shortcuts.vdf (binary VDF, every <user>) whose Exe
  is our launcher (SCRITCH_LAUNCHER; also the old ~/Applications/itch-deck/ path). Its "appid"
  field (signed int32 in the file -> unsigned for file names).
- Copy into userdata/<user>/config/grid/: <appid>p.png (tile), <appid>.png (wide tile),
  <appid>_hero.png, <appid>_logo.png. Never overwrite: skip any name that already exists with
  ANY extension (.png/.jpg/.webp: the player's own or SteamGridDB's art).
- Icon: Steam does NOT read <appid>_icon.png from grid/; the tile icon is shortcuts.vdf's "icon"
  key, and Steam rewrites shortcuts.vdf while running. Options: copy icon.png next to the
  launcher and tell the player to pick it (one README line), or write the key only while Steam
  is closed. Decide with Omri when building.
- Steam shows new grid files after a Steam restart (or Game Mode reload) at worst. Read-only on
  shortcuts.vdf; a test with a hand-made binary VDF. Then README step 4 (set art by hand) goes.
- Size: small-medium (VDF reader + copy + tests), one update.

## v0.9.4 RELEASED 16 Nov = Steam art set automatically (branch steam-art-auto + design-art-stars; Omri "push update" 13:35;
  only design-tabs left unmerged = scrapped)
- Pulled forward from ROADMAP 3 (item above). itch_deck/steam_art.py: read_vdf (binary VDF, types
  0/1/2/7/8), find_shortcuts (every Steam root + userdata/<user>; entry whose Exe resolves to the
  launcher, updater.launcher_path(); appid & 0xFFFFFFFF), apply() copies tile/wide-tile/hero/logo
  as <appid>p/<appid>/<appid>_hero/<appid>_logo .png; skips names that exist as any picture type;
  once per user/appid (DATA/steam_art.json, so art removed on purpose stays gone); icon.png ->
  <launcher dir>/scritch-icon.png for the player (Steam reads the icon from shortcuts.vdf, which
  we never write). Started in a thread from App.__init__; only in real builds (launcher known).
- build.sh: --add-data packaging/steam-art:steam-art (art_dir() = _MEIPASS/steam-art). The design
  chat can keep changing the PNGs: each build ships what's in packaging/steam-art (git add -f!).
- README step 4 = only the icon now.
- Tests tests/test_steam_art.py (hand-made VDF, negative appid, no overwrite, once, broken vdf,
  art shipped). Checked pytest 3.13 + 3.11 (151), selftest both, itch-reject, mockups, PyInstaller
  build has _internal/steam-art. UNVERIFIED on the Deck: real shortcuts.vdf of his tile
  (~/Applications/itch-deck/itch-deck), when Steam shows the art.

## ROADMAP NOW (Omri 16 Nov 13:41; replaces every list above; page https://claude.ai/artifact/Hkk8SQChbBUBbAJ1yVEbqo)
One item per update, plan + size first, wait for "go" and "push":
1 Deck test round (no code): v0.9.4 checklist + 2-3 GOG games (one Linux, one big Windows).
2 GOG first-run setup (goggame-*.script / redist: runtimes etc., P03) + GOG updates (v0.9.5).
3 Hide extra controllers for player-1-only games (Bleed 2). Research first.
4 Opt-in "Add to Steam" for one game (⚙; own tile + controller layout; needs a Steam restart).
  Still decided against: automatic tiles for every game.
5 DLC for Epic and GOG (one ⚙ entry, both stores).
6 Ready to share (logo + Steam art done; README for new players, fresh-Deck check).
7 Cloud saves for Epic and GOG (off by default; own update + test round; risky).
Later: browser games.


# Moved from NOTES.md on 18 Nov 2026 (v0.9.5 to v0.9.31, release by release; nothing was changed or dropped)

## v0.9.5 RELEASED 16 Nov (branch v095-gog; Omri "go and push" 14:45) = GOG versions + first-run setup + updates
Deck test 16 Nov: Eye of the Beholder (GOG Linux build) exited at once: its bundled DOSBox needs
libFLAC.so.8 (not on SteamOS); message said "Try another build in Options" but GOG had none.
- Change build for GOG (only when GOG lists Linux AND Windows): picker "Choose a version" Linux /
  Windows (app_game._gog_versions; choices[gid] = "linux"/"windows"; GOG upload_id = platform
  from now on, old installs had app_name). Switching installs into files.new, swaps on success
  (fail = old build stays). Crash hint "Try another build in Options." (runner.TRY_OTHER_BUILD)
  -> GOG: "Try the Windows version in Options." when Linux build + Windows exists, else code P01.
- First-run setup (Windows): gogdl info "dependencies" ids; after install `gogdl redist --ids <ALL
  ids ever asked> --path DATA/gog/redist` (gogdl replaces the folder with exactly those ids:
  DATA/gog/redist_ids.json keeps the union). gog.setup_steps -> install.json "setup_steps"
  [{name, base redist|game, path, args}] (+ ISI scriptinterpreter.exe with Heroic's args incl.
  /DIR=Z:\… when goggame-*.script exist), "setup_done". app_play._gog_first_run on the first
  Play: gog.run_setup runs each through umu in the game prefix (OK exits 0/1638/3010/1641, 15 min
  each), splash "Preparing <game>… First run only", log logs/games/<slug>-setup.log; failures
  logged, setup flag -> P03 on a quick crash. Redist download failure doesn't fail the install.
- Updates: Installer.check_gog_updates after each GOG sync (lib.on_gog_sync): gogdl info per game
  (every 6 h, force=True ignores), Windows build_id / Linux version differ -> "update". Update =
  same platform -> in place (fresh=False keeps gogdl's manifest: only changed files). gogdl_mode
  sets v2.Patch.get -> None (no xdelta3 here: chunk updates). setup_done kept across updates.
- Linux size: _disk_size = max(disk_size, download_size) (Deck log showed 0 for EOB Linux).
- Tests test_gog: setup steps + paths, run_setup with a fake umu (args, Z:\ dir, failure list),
  change version both ways + failed switch keeps Linux, update check + in-place update. Mockup
  15t_game_gog_versions. Checked pytest 3.13 + 3.11 (153), selftest both, itch-reject, mockups (182).
UNVERIFIED (no GOG here): real redist manifest paths (__redist/... under DATA/gog/redist?), ISI
  args on real games, update detection on a real patched GOG game.

## v0.9.6 RELEASED 16 Nov (branch v095b-gog-fix; Omri "push" 15:55) = Eye of the Beholder fixes
- v0.9.5 Deck: EOB Windows build showed DOSBox ~2 s then exit 0. setup log: "ISI: __redist/ISI/
  scriptinterpreter.exe not found" (redist ids never included ISI). DOSBOX/stdout.txt: only
  "Loading primary settings from ...AppData\Local\DOSBox\dosbox-0.74-2.1.conf": the game's -conf
  "..\dosbox_eob1.conf" / "..\dosbox_eob1_single.conf" (autoexec: pause, mount c "..", start.exe)
  were never read. stdout.txt was in files/DOSBOX = cwd right.
- Fix 1: _install_gog adds "ISI" to the redist ids when goggame-*.script exist. app_play
  _gog_needs_setup: run the first-run setup again when a step's file is missing (heals v0.9.5
  installs); first-run fetches missing redist parts itself (lib.gog.redist) before running.
  setup_done only when every step's file exists.
- Fix 2: gog.windows_args at Play (Windows GOG builds): an argument that names an existing file
  relative to the working dir becomes a full Z:\ path. Cause not proven (Proton cwd vs "/"),
  this covers both. Next if it still fails: native DOSBox (gogdl uses dosbox-staging/flatpak if
  present) or a GOG DOSBox fix list.
- Tests: ISI asked, windows_args. pytest 3.13 + 3.11 (155), selftest.

## v0.9.7 RELEASED 16 Nov (branch v097-dosbox; Omri "go and push" 16:22) = GOG DOS games via native DOSBox
- v0.9.6 Deck: EOB Windows build (GOG's dosbox.exe under Proton) still showed its logo and closed;
  the Linux build's bundled DOSBox misses libFLAC.so.8 / libSDL_sound-1.0.so.1. Setup log: ISI ran
  (exit 0). Also every gogdl run in the frozen app printed "scritch: error: unrecognized arguments:
  -B -S -I -c from multiprocessing.resource_tracker import main;main(N)": multiprocessing's
  resource tracker re-runs sys.executable (= our binary).
- Fix 1: run.py / __main__ call multiprocessing.freeze_support() first (PyInstaller's hook runs
  those helper processes). Checked on a real PyInstaller build: the tracker command exits 0.
- Fix 2: itch_deck/dosbox.py (like Heroic/gogdl launch): GOG Windows builds whose play task is
  dosbox.exe run with DOSBox Staging: dosbox-staging on PATH, else flatpak io.github.dosbox-staging
  (ensure(): `flatpak install -y --noninteractive flathub` system, else remote-add --user +
  install --user; at install time and, if missing, at Play with splash "Getting DOSBox… One time
  only"). launch(): play-task args, -noconsole dropped, each -conf -> scritch-<name> copy next to
  it with "\\" -> "/" in [autoexec] mount/imgmount lines (GOG: mount C "..\\cloud_saves" -t overlay);
  flatpak run --filesystem=<files> --cwd=<play-task folder>. No Proton, no first-run setup for
  those. No DOSBox to be had -> old Proton path.
- Tests tests/test_dosbox.py (stand-in flatpak: install once, user fallback; launch args + conf
  copy; run.py order). UNVERIFIED: flatpak install on SteamOS without a password (system), staging
  reading GOG's 0.74 confs (output=overlay, -t overlay), the [sdl] fullscreen under gamescope.

## v0.9.8 RELEASED 16 Nov (branch v098-logs; Omri "go ahead" 17:50) = logs that survive + forget version on uninstall
- v0.9.7 Deck (app.log): 17:39 EOB Windows: "dosbox: installing io.github.dosbox-staging" -> ready in 4 s
  (flatpak system install worked without a password), play "dosbox native", flatpak started,
  window seen at 1.0 s, exited 0 after 1 s -> P03. 17:40 Omri switched to Linux; that run
  overwrote eye-of-the-beholder.log, so DOSBox Staging's own message was lost. CAUSE OF THE 1 s
  EXIT STILL UNKNOWN (guesses: a GOG conf line staging rejects, e.g. "-t overlay", or the pause).
- runner.keep_logs: <slug>.log -> .1.log -> .2.log (last 3 runs). Crash: app.log gets the game
  log's last 15 lines (runner.log_tail, overlay preload noise dropped).
- Installer.uninstall drops self.choices[gid] (a reinstall came back as the version picked
  last time, e.g. Linux).
- Omri (16 Nov): doesn't want to spend much more time on EOB. Next: one Play of the Windows build
  -> eye-of-the-beholder.log / app.log "game log ends" lines; if not quick, park EOB.

## v0.9.9 (branch v099-dosbox-autoexec, waits for "push") = DOSBox Staging runs GOG's start commands
- v0.9.8 Deck (app.log 17:55, "game log ends"): DOSBox Staging started, showed 80x25 text mode,
  then shut everything down after 1 s, exit 0: none of GOG's [autoexec] ran (no pause, no
  start.exe), only the final "-c exit".
- dosbox._split_conf: copy each -conf as scritch-<name> WITHOUT [autoexec] (bytes kept via
  latin-1: GOG's CP437 boxes; v0.9.7 re-encoded them as UTF-8), and return its commands minus
  cls/pause/echo/rem/exit; mount/imgmount paths "\\" -> "/". launch passes them as -c, then GOG's
  own -c ("exit"). Copy-protection notice + pause no longer shown (the in-game question stays).

## v0.9.10 (17 Nov, branch v0910-gog-heroic-setup, pushed to main at Omri's request; tests only run on Windows partially) = GOG first-run setup like Heroic's setup.ts
- stores/gog.setup_steps now follows Heroic: game's own setup first (ISI when the saved gogdl manifest says
  scriptInterpreter, or goggame-*.script exist; else the product's temp_executable from DATA/gog/heroic_gogdl/
  support/<id>/), then the shared parts. ISI args gained /lang-code=en-US + /supportDir=; /LANG=English.
  PHYSXLEGACY runs as `msiexec /i … /qb`; ScummVM games get a Linux /DIR. Redist steps run with the redist
  folder as cwd, ISI/setup with the game folder (Heroic's startFolder). Takes effect on (re)install.
- NOT changed: DOS games (dosbox.exe) still skip Proton setup. EOB's 1 s DOSBox exit is still unexplained;
  Heroic passes the play-task args unchanged (conf autoexec intact), we strip [autoexec] since v0.9.9.
  Next, if it still P03s: send logs/games/eye-of-the-beholder.log + app.log "game log ends".
- tests/test_gog.py: 11 of 22 fail on Windows even before this (POSIX stand-ins); need a Linux run.

## v0.9.11 (17 Nov, branch v0911-fix-gog-setup, NOT pushed - waits for Omri) = FIX for v0.9.10's first-run setup
- v0.9.10 BUG (found by the reviewer agent): run_setup used `cmd` and `cwd` that were never defined
  (a replace in my edit silently didn't apply) -> NameError on every first-run setup step, caught in
  app_play, so no redist/ISI ran and the game could end in P03. Fixed: cmd = [umu, exe, *args] (or
  [umu, msiexec, /i, exe, *args] for the PhysX step), cwd = redist folder for shared parts, game folder
  for ISI. ScummVM's linux_dir flag is now read. Checked by calling run_setup with a missing umu
  (no NameError, steps logged). LESSON: check every edit landed (diff/grep), don't trust "no output".
- gog.required(step): a product's temp_executable ("support" step) is optional, so a missing file
  can't make the setup rerun on every Play. tests/test_gog.py expects ISI first now.
- UNVERIFIED: where gogdl puts support/<id>/ files, msiexec through umu, ScummVM path, ISI fetched
  only at first Play when the manifest says scriptInterpreter but no goggame-*.script exist (needs internet).

## v0.9.12 (17 Nov, branch v0912-dosbox-conf-lookup, NOT pushed - waits for Omri) = EOB: DOSBox couldn't open GOG's settings files
- v0.9.11 Deck logs (deck-logs/, never commit): EOB Windows build + native DOSBox Staging: game log says
  "CONFIG: Can't open custom config file .../files/dosbox_eob1.conf" (+ _single.conf) and app.log
  "dosbox: commands []" -> our copy step never found the files (is_file False), DOSBox ran with its
  default settings, ran only GOG's "-c exit", closed after 1 s = P03. Same for Eye of the Beholder II.
  So the earlier autoexec theories were wrong: the files weren't found at all.
- Fix (a GUESS at the cause): dosbox.launch finds the -conf file with gog._ci (any letter case, like
  GOG's other paths). If it is STILL missing, app.log gets "dosbox: settings file ... not found;
  folder has: [names]" so the next log shows what GOG really installed (maybe the files are named
  differently, or ISI creates them -> then we need to run ISI before DOSBox).
- Also seen: v0.9.11 first-run setup works for Windows games without DOSBox (ISI exit 0 in setup log).
  Epic cover downloads fail for 6 games: URLs contain spaces (net.get must quote the path) - not fixed yet.
- UNVERIFIED: whether case is the cause. Check app.log for the "folder has:" line.
- v0.9.12 ADDED (after reading Heroic + vendored gogdl, Omri asked "can't we see how they do it?"): gogdl's
  `--support <dir>` (Heroic games.ts passes join(gogSupportPath, id) on install/update/repair). Without it
  gogdl puts GOG's "support" files in <game>/gog-support, while we told ISI /supportDir=DATA/gog/
  heroic_gogdl/support/<id> (empty) -> ISI had nothing to build the game's DOSBox settings files from.
  Now: gog.install passes --support support_dir(id); run_setup uses <game>/gog-support for ISI on older
  installs; app_play runs the first-run setup (ISI) BEFORE launching DOSBox for GOG DOS games (it used to
  skip setup for them; Heroic runs it for every Windows game). This is the likely real cause of EOB's missing
  dosbox_eob*.conf. UNVERIFIED on the Deck. Check logs: eye-of-the-beholder-setup.log (ISI exit code),
  then app.log "dosbox: commands [...]" should be non-empty; if the .conf is still missing, the
  "folder has:" line lists the files.
- v0.9.12 also: net.get percent-encodes spaces in URLs (net._safe_url): 6 Epic covers failed with
  InvalidURL "control characters" (names like "Store Primary Promo (Landscape)-...jpg"). Checked the helper
  on sample URLs; UNVERIFIED on the Deck (covers should show after a sync).

## ROADMAP NOW (Omri 17 Nov; replaces the 16 Nov list; audience = friends / a few Deck owners; priority = solid first, then features)
One item per update, plan + size first, wait for "go" and "push":
1 Deck check of v0.9.12 (no code): Epic covers show, Eye of the Beholder I + II play (Windows build, mouse via
  Keys mode), one big Windows GOG game, one Linux GOG game, itch games still fine. Fix what it finds.
2 Share logs (new, small): Settings -> "Copy logs" puts a zip of logs/ + app.log in an easy folder (and shows
  where), so friends can send them without a terminal or RustDesk. (Getting logs off the Deck took many steps.)
3 Ready to share: README for new players (install, first run, GE-Proton, where logs are), error texts
  friendly, fresh-Deck check (new user, empty data, no GE-Proton).
4 DOS tab, step 1: GOG DOS games shown in a DOS tab (only when one exists). Step 2: add-your-own folders (user's
  own games; we never fetch games). Step 3: game page for them. Typing = Steam's keyboard (Steam + X) as today.
  Designer agent sketches the folder-picker screen with Omri before step 2.
5 Hide extra controllers for player-1-only games (Bleed 2). Research first.
6 Opt-in "Add to Steam" for one game (own tile + layout; needs a Steam restart).
PARKED (Omri 17 Nov): DLC for Epic and GOG; cloud saves for Epic and GOG; browser games.
Rules: coder -> reviewer -> (designer if a screen changed) -> Omri says push. Agents in E:\Projects\GIT\.claude\agents.

## v0.9.13 (17 Nov, branch v0913-safe-deletes) = safer deleting (from the read-only audit of 17 Nov)
- installer.safe_to_delete(path, roots): a folder is deleted only when it is strictly inside a games root
  (never the root itself, home, or somewhere else). Uninstall computes the roots BEFORE popping the game
  from the index (install location now, both drive choices, the itch/scritch folder of every installed game
  incl. this one); a damaged install.json can no longer make uninstall rmtree the wrong place (it logs
  "NOT deleting ..." and still forgets the entry).
- Move: a leftover Proton prefix at the destination (can hold saves) is renamed `<name>.kept-<time>` instead
  of deleted (Settings -> Saves of uninstalled games lists it). Other leftovers: deleted only when safe.
- Reviewer-agent found 3 gaps, all fixed (roots after pop, file where a prefix should be, name clash).
- Tests: tests/test_safe_delete.py (4 of 5 need Linux: they reuse test_move._setup with symlinks). UNVERIFIED
  on the Deck. Audit leftovers not done: merge duplicated Epic/GOG code, dead code list, .gitignore gaps,
  split NOTES.md, `requests` possibly unused, check that helper output (legendary/gogdl stderr) never holds tokens.


## v0.9.14 (17 Nov, branch v0914-tidy) = tidy-up from the audit (no behaviour change)
- Removed code nothing used (grep-verified, each had zero other references): Input.pad_names, mockups._with,
  PhoneLink.renew, itch_page._depth_of, dosbox.SKIP_CMDS + unused `import re`, scenes.game.PLATFORM,
  scenes.library.TABS. .gitignore: .pytest_cache/, *.log, and !packaging/steam-art/*.png (no more `git add -f`).
- NOTES.md split: this file kept the rules, code map, decisions, known issues and everything from v0.9.5;
  all older notes moved unchanged to docs/history/NOTES-history.md (checked: no line lost).
- Checked: Windows pytest before/after = same 50 failed / 104 passed (the failures are the Linux-only tests);
  all touched modules compile. CI is the real test. Left from the audit: merging the duplicated Epic/GOG
  code (app_epic/app_gog, library sync, installer start/end), long functions, `requests` is needed by the
  vendored gogdl (keep), check helper stderr can't hold tokens.

## v0.9.15 (17 Nov, branch v0915-send-logs) = Settings -> Help -> Send logs (roadmap item 2)
- Omri's decision: the phone page copies the LAST LINES of the log so people can paste them into a GitHub
  issue. Safety rules (reports are public): nothing is uploaded by the app and there is no GitHub token in it;
  itch_deck/logshare.py scrub() hides secrets (Bearer/key=value/JSON tokens/URL codes/JWT/long mixed-case
  strings), e-mails, IPv4, account names ("connected as X"), /home/<user> -> ~, /run/media/<user>/<id> -> <sd>
  (also Proton's backslash form). The short report = version + system + last 150 app.log lines + last 40 lines
  of the newest game log, max 30,000 chars (oldest dropped, version line kept). The page shows the text in an
  editable box first; Copy uses execCommand (the clipboard API needs https; the phone page is plain http).
  Also on the page: "Open a GitHub issue" (prefilled version/system via .github/ISSUE_TEMPLATE/bug_report.yml
  field ids) and the full cleaned zip (private use). Same one-time link/expiry as the sign-in pages.
- Deck screen LogsShare (scenes/epic.py, app_logs.py): QR + 3 steps; A saves the zip to ~/Documents/SCRiTCH
  logs/ (toast), B back. New Settings group "Help" at the END (no existing row index moved).
- Tested against the real Deck logs in deck-logs/: no /home/deck, SD id, e-mail, IP or token left.
  tests/test_logshare.py (21, run on Windows too). Mockups 21k, 28, 28b rendered and looked at.
- UNVERIFIED on the Deck/phone: QR scan, Copy button on iOS/Android browsers over http, zip download.
  Not done: scrubbing is pattern based (a secret in an odd format could slip through; the person reads the
  text before posting), no "private" route besides the zip.
- Reviewer-agent findings on v0.9.15, all fixed: scrub() ran quadratic on one very long line (now line by
  line, lines over 2000 chars cut, e-mail pattern bounded); names with spaces/quotes ("Omri Cohen"), "as:",
  "Username = x", quoted secrets with spaces, camelCase keys, `--auth-code x` flags, Steam userdata/SteamID64/
  "for user N" ids, /media|/mnt/<user>, Z:\Users\<user> now hidden; a game called "2048" is no longer skipped as
  a rotated log; POST to a logs link = 400 (was a KeyError). 3 new tests + 15 new scrub cases.
- tests/test_phone.py::test_big_or_empty_posts fails on Windows with or without this change (socket quirk).

## v0.9.16 (17 Nov, branch v0916-logs-fixes; waits for "push v0.9.16") = fixes from Omri's Deck test of Send logs
- v0.9.15 Deck test: QR, page, issue link (version/system filled), zip, A-save, expiry all fine. Problems:
  (4) Copy did nothing in the phone browser (script is correct; checked with node; cause unknown: browser,
  plain http). Text too long to read. (7) nothing on the Deck screen said A saves a zip.
- Fix: the issue link now carries a SHORT cleaned log (logshare.compact(), <= 2,200 chars, end of app.log +
  newest game log) as the issue form's `log` field, so nothing has to be copied; the page's main button is
  that link. The longer text + Copy stay below ("Want to share more?"): textarea is readonly (no keyboard
  popping up), clearer message and button label when copy works or not. Report 150 -> 60 app lines, 40 -> 30
  game lines. Deck screen: "Scan the code, or press A to save the logs as a zip in Documents."
- Tests: compact fits a link (< 7,500 chars), is scrubbed; no log field when none. UNVERIFIED: GitHub's form
  prefill of `log` on a phone, and whether Copy works now.

## v0.9.17 (17 Nov, branch v0917-logs-copy-fix; waits for "push v0.9.17") = the real cause of "Copy does nothing"
- Omri (Galaxy S24, Chrome) on v0.9.16: Copy did nothing and showed no message. Cause (found by loading the real
  page in headless Edge and clicking): the inline logo SVG on every phone page has ids like "c", so
  getElementById('c') returned the LOGO, not the button; the click handler sat on the logo. v0.9.15 and
  v0.9.16 both had it. My earlier checks (node syntax check, a fake DOM) could not see it.
- Fix: unique ids (lg-text, lg-copy, lg-msg) + tests/test_logshare.py::test_page_ids_are_unique... (every id
  unique, every getElementById target present once). Headless check after the fix: the click runs and sets a
  message (headless has no real touch, so copy itself is refused there; UNVERIFIED on the phone).
- Page is far less text: one purple button + 2 lines; "More" (closed) holds the longer text, Copy and the zip.
  Deck screen: QR 30% -> 42% of the height on this screen only (LogsShare.QR_SIZE), step texts shorter.
- LESSON: test phone pages in a real browser engine (Edge headless: --headless=new --dump-dom with a harness
  script that clicks), not only by reading the JS. Check every page that inlines LOGO for id clashes.

## README update (17 Nov, branch v0918-readme; docs only, NO version bump = a push builds no release) = roadmap item 3 "Ready to share"
- Omri: keep the README developer-style (not a friends' landing page); no clean-install Deck check (he won't do it).
- README now covers: itch + Epic + GOG (tabs), GOG sign-in/versions/first-run setup/DOS games in DOSBox Staging,
  updates on all stores, save backups + Saves, Move, Send logs (purple button, More = copy/zip), an error-code
  table (from words.CODES), more troubleshooting rows, where files live (gog/, Documents/SCRiTCH saves + logs),
  known limits (GOG/Epic no DLC/cloud saves, GOG Linux libs, DOS needs Flathub once).
- words.CODES P03 text updated (first-run setup runs since v0.9.5). Error texts otherwise already plain: short(),
  codes only when there is nothing to act on (checked, no change).
- CLAUDE.md (E:\Projects\GIT) now says: touch ONLY E:\Projects\GIT (no temp/system folders). Scratch files go in
  E:\Projects\GIT\scratch\ (outside the repo).

## v0.9.18 (17 Nov, branch v0919-dos-tab; waits for "push v0.9.18") = DOS tab, step 1 (roadmap item 4)
- Omri's answers (17 Nov): add-your-own = a DOS games FOLDER (no folder picker), tab only when a DOS game exists,
  folder next to the other games (Install location: <root>/dos), cover = cover.jpg/png in the game folder else a
  title card, .zip files in the folder get unpacked, two releases, quit = the existing View+Menu combo.
  Step 2 (the folder, scan, tiles, which-file picker, CD images, Remove entry that never deletes files, zip
  unpack) is the NEXT release; designer agent sketches the Settings row/empty state first.
- Step 1 (this release): Library._apply_install sets g["dos"] for installed games whose install.json is a
  DOSBox game (dosbox.is_dosbox_game); scenes/library.tabs(stores, dos) adds ("dos","DOS") LAST and only when
  Library.dos (any game has the flag, so it appears/disappears live); visible(filt="dos"); empty message
  "No DOS games yet. DOS games you install from GOG show up here."; a stale "dos" tab falls back to All.
  Only INSTALLED GOG DOS games show (an uninstalled GOG game isn't known to be DOS yet).
- Tests tests/test_dos_tab.py (4). Mockup 06h_library_dos_tab rendered and looked at. UNVERIFIED on the Deck.
  Deck: install Eye of the Beholder -> a DOS tab appears (L1/R1) with it; uninstall -> the tab goes.
- Reviewer-agent findings on v0.9.18, both fixed: App.go_library now copies the scene's tab back to self.filt
  (a stale "dos" left the game page at "1 of 0"); Library.next_tab falls back to All if its tab is gone
  (ValueError). Test added.

## v0.9.19 (17 Nov, branch v0920-dos-sketch; waits for "push v0.9.19") = DOS tab step 2: your own DOS games (roadmap 4)
- Omri's decisions: a dos FOLDER (no picker), row A "DOS games | SD card · 3 games | Folder: scritch/dos" in
  Settings -> Storage, box "Add DOS games" (path shown, OK button is "Refresh", main/purple), zip files unpacked.
- itch_deck/dosgames.py (pure files): dos_dir(root)=<games folder>/dos; scan() unpacks zips (zip-slip refused, zip
  moved to dos/_zips, kept), lists folders with .exe/.com/.bat (helpers like setup/sound config skipped, depth<=2),
  pick_program (saved choice > name like the folder > the one .bat > first), cd_image (.cue/.iso -> drive D),
  cover.jpg/png; removed() hides a folder until its mtime is newer than the removal. State: DATA/dos.json.
- Installer.sync_dos(create) -> index entries store "dos" (dir = the game folder itself; exe relative; NO "files"
  level, NO install.json written into the player's folder) + lib.set_dos_games (covers copied+shrunk into COVERS).
  Start-up/Y scan never creates the folder; Refresh in the box does. remove_dos(): forget only, files untouched
  (uninstall() routes there). exe_path/programs/set_exe/move_target know store dos.
- Play: dosbox.launch_own = DOSBox Staging, -c mount c "<folder>", imgmount d, c:, cd <sub>, <exe>, exit
  (flatpak --filesystem/--cwd like the GOG path); no backups (saves live in the folder). Game page Options:
  "Remove from library", Controls (Auto = Keys: inputs Keyboard+Mouse), "Program to run" when >1 program.
- UNVERIFIED on the Deck: everything (no DOS game folders here). Check: Settings -> Storage -> DOS games -> A ->
  Refresh (folder is made); copy a DOS game folder + a .zip in with Dolphin; Refresh -> DOS tab with tiles; Play ->
  DOSBox opens with the game; quit with View+Menu 2 s; Options -> Remove from library keeps the folder.
  Known limits: long (non 8.3) sub folder names for cd; Windows 3.x/95 games; no pad config per game.
- Tests: tests/test_dosgames.py (7, run on Windows too). Mockups 21m, 21o, 15u/v/w rendered and looked at.
- Reviewer-agent findings on v0.9.19, all fixed: (1) an itch game titled "DOS" got <root>/dos as its folder and
  uninstall/move could wipe the player's DOS games: _game_dir reserves dos/_prefixes/_moving, safe_to_delete never
  deletes those names; (2) ids collided (non-ASCII names all slugged to "game"): id = dos-<slug>-<6 hex of the
  folder name>, stable; (3) an odd zip (old PKZIP compression, password) stopped the whole scan: per-zip
  `except Exception`, skipped with a log line; free-space check before unpacking; (4) the scan changed the shared
  index from a thread: scan_dos() (thread, touches nothing shared) + apply_dos() (main thread, in App._dos_tick);
  a choice made meanwhile survives; (5) Refresh pressed during a scan was lost: it is queued (dos_queued);
  (6) a removed game's .zip copied again comes back as "<name> (2)" (old folder untouched); (7) one os.walk
  per game (depth 2 for programs/images), folder names with a double quote skipped, own games are not sent to
  HowLongToBeat. Not changed: no scan without an itch key (the app needs one to reach the library).
  Tests: tests/test_dosgames.py now 15 (run on Windows).

## v0.9.20 (17 Nov, branch v0921-sources; waits for "push v0.9.20") = Settings: "Accounts" group -> "Sources" with the DOS row
- Omri: the DOS games folder belongs next to the stores. Settings groups now: App, Sources (itch, Epic, GOG, DOS games),
  Storage (Install location, Saves of uninstalled games), Games & controls, Help. Row indexes after Sources move by one
  (mockups updated: Storage focus 6, Games 8, Help 11, DOS row 5). README/comments say Settings -> Sources.
- HISTORY REWRITE (17 Nov, Omri's choice after GitHub blocked a push for exposing his email): all 26 commits that carried
  his real email were rewritten to 14329843+GoOmri@users.noreply.github.com on ALL branches and tags and force-pushed
  (commit hashes changed, trees identical; v0.9.19 and older releases keep working, they hang on tag names). Nobody had
  cloned the repo; GitHub Support was NOT asked to purge the old objects (they stay reachable by direct SHA for an
  unknown time). Any chat still holding old branches must `git fetch` + reset to origin. Use that noreply email from
  now on (also in CLAUDE.md).

## Add to Steam per game: plan + Deck experiment (17 Nov, branch v0922-steam-shortcuts; no VERSION bump, nothing uses it yet)
- Omri's answers: per-game opt-in in Options ("Add to Steam" / "Remove from Steam"), tile art = the game's cover fitted to
  Steam's sizes, controller layout left to Steam (a message says so), and he agreed to a Deck experiment first.
- Plan: (1) `--play <game id>` start mode (play one game, then exit; allowed next to the single-instance lock);
  (2) itch_deck/steam_shortcuts.py = binary VDF reader/WRITER (stdlib only, standalone, tests/test_steam_shortcuts.py:
  byte-for-byte round trip, add, remove only our own "SCRiTCH"-tagged entries, backup + atomic write);
  (3) art: cover -> <appid>p / <appid> / <appid>_hero via steam_art's never-overwrite rules; (4) Options entries + toast
  "Restart Steam to see it"; (5) maybe later: per-game controller layout (poorly documented, own research).
- MAIN RISK: Steam rewrites shortcuts.vdf from memory when it exits, so an edit made while Steam runs can be lost. The
  experiment (E:\Projects\GIT\deck-experiments\steam_shortcuts.py, run with python3 in Desktop Mode: where / verify /
  list / add / check / remove) tells us what survives: Steam running vs closed, Game Mode switch, Steam restart.
- UNVERIFIED: that our writer's bytes match what real Steam files look like (verify checks his real file read-only).

## v0.9.21 (17 Nov, branch v0922-steam-shortcuts; waits for "push v0.9.21") = Add to Steam per game (roadmap 6)
- Deck experiment results (Omri, 17 Nov): a shortcut written into shortcuts.vdf while Steam RUNS is not seen until
  Steam restarts (Desktop -> Game Mode switch did it); it survived Steam's exit; removing it from the file while
  Steam runs sticks and Steam did NOT write its copy back. Our reader/writer round-trips his real file byte for byte
  (20 shortcuts from other tools). => adding/removing needs no closed Steam, only a restart to show.
- Omri's choices: per-game opt-in in Options for EVERY installed game, cover as the tile, controller layout left to
  Steam, short message "Added to Steam. Restart Steam to see it.", ONE release.
- itch_deck/steam_shortcuts.py (standalone; list/where/verify/add/check/remove CLI used in the experiment),
  itch_deck/steam_games.py (add/remove/is_added/available + art), `scritch --play <id>` (App(autoplay=...): no update
  check/sync/art; _autoplay in app_play plays the game, keeps a crash message up 5 s, then quits). Shortcut = the
  launcher (updater.launcher_path()) + LaunchOptions "--play <id>" + tag "SCRiTCH"; AppName = title ("(2)" if the
  same title+file exists). Id must match [A-Za-z0-9._-]{1,80} (it goes into Steam's launch options).
- Art: <appid>p.png 600x900, <appid>.png 920x430, <appid>_hero.png 1920x620 from the cover (fitted over a darkened
  blurred copy) or a title card (type shrinks to fit); never over a picture that exists (any extension); the files
  made are recorded in DATA/steam_games.json so Remove deletes only those. steam_art.find_shortcuts skips "--play"
  entries (SCRiTCH's own tile art must not land on game tiles).
- Options row "Add to Steam"/"Remove from Steam" (last row of an installed game's menu, only when a Steam user
  folder exists and this is a real build). Codes T01/T02.
- UNVERIFIED on the Deck: the whole flow with a real game: Add -> restart Steam -> tile with art -> start it ->
  game runs -> quit -> back in Steam; Remove -> restart -> gone. Also adding while IN Game Mode (same file, same
  expected behaviour). Single-instance lock: if SCRiTCH is already running, --play quits (log "another copy").
- Tests: tests/test_steam_shortcuts.py (7), tests/test_steam_games.py (8). Mockups 15x/15y rendered and looked at.
- Reviewer-agent findings on v0.9.21, all fixed: (1) a Steam tile quit before the saves backup thread finished
  (os._exit killed it): _autoplay joins the backup thread for up to 8 s; (2) a cut-off shortcuts.vdf raised
  struct.error and crashed the Options menu: loads() now raises ValueError, is_added/add handle it, file untouched;
  (3) art made before a later failure / on a re-add was not recorded and could be orphaned: the record is saved per
  user and keeps earlier art, Remove deletes all of it; (4) a missing SD card showed "isn't installed": now "SD card
  missing. Put the card back..."; (5) "X closed." no longer holds the screen 5 s (only errors do); (6) a Steam tile
  pressed while the old copy is closing waits up to 6 s for the single-instance lock; (7) backups: newest 5 kept,
  names include milliseconds, non-UTF-8 titles round-trip byte for byte (surrogateescape).
- STILL UNVERIFIED (said by the reviewer too): Steam may rewrite shortcuts.vdf from memory when a non-Steam shortcut is
  changed or played. SCRiTCH itself runs as a non-Steam shortcut, so adding while IN Game Mode could be undone when
  SCRiTCH exits, and a removed tile could come back. The experiment only covered Steam exiting. First Deck test must
  add in Game Mode, restart Steam, and check `python3 steam_shortcuts.py list` afterwards.

## v0.9.21 CI fix (17 Nov): the first build of v0.9.21 FAILED on GitHub (pytest), so no release was made and the Deck stayed on .20
- Cause: tests/test_codes.py only knew code letters [IWPLEUSM]; the new Add to Steam codes T01/T02 made it report
  "listed but never used". Fixed: letter T added to both patterns. Nothing else differed from v0.9.20 (compared the whole
  suite old vs new).
- LESSON: on this Windows PC run the suite with PYTHONUTF8=1 and a fcntl stand-in on PYTHONPATH (python -m pytest -q
  tests): without UTF-8 mode some Linux-only checks (test_codes) fail for the wrong reason here, which hid this one.
  And ALWAYS look at the build's result after a push (api.github.com/repos/GoOmri/Itch-deck/actions/runs).

## v0.9.22 (17 Nov, branch v0924-art-fix; waits for "push v0.9.22") = Add to Steam: art failed on the Deck
- Deck test of v0.9.21 (Omri): Add worked (toast, tile after a Steam restart, KIDS starts with --play, Remove makes the tile
  go away), BUT the tile had no art. app.log: "steam games: art for <id> failed" (traceback line not seen). Reproduced here:
  KIDS' cover is an 8-bit indexed picture and pygame's smoothscale raises "Only 24-bit or 32-bit surfaces can be smoothly
  scaled". Fix: steam_games._to32 converts a cover to 32 bits first; an unreadable/undrawable cover falls back to a title
  card; no usable font (frozen build) = a plain coloured tile instead of an error; pressing Add on a game that is already
  added now draws its missing art (no second shortcut, one write).
- If art is STILL missing on the Deck: `grep -B2 -A12 "steam games" ~/.local/state/scritch/logs/app.log | tail -40` shows the
  traceback; `ls -la ~/.local/share/Steam/userdata/<id>/config/grid` shows the files (expect <appid>p.png, <appid>.png,
  <appid>_hero.png for the shortcut's appid).
- Tests: indexed + broken cover, fallback, no font, add-again. Whole Steam feature: 15 + 7 tests.

## ROADMAP NOW (Omri 17 Nov evening; replaces the earlier 17 Nov list; page https://claude.ai/artifact/Hkk8SQChbBUBbAJ1yVEbqo)
Released: v0.9.13 safer deleting, 0.9.14 tidy-up + NOTES split, 0.9.15-0.9.17 Send logs, 0.9.18 DOS tab, 0.9.19 own DOS
games folder, 0.9.20 Settings "Sources", 0.9.21-0.9.22 Add to Steam per game (0.9.21 build failed once on a test, fixed).
1 Deck tests (no code): Add to Steam cover art in v0.9.22 (Remove + Add again, restart Steam), own DOS folder with a real
  game and a zip, older leftovers (itch game updates, split installers, Epic updates).
2 Hide extra controllers for player-1-only games (Bleed 2). Research first.
3 Maintenance (no new features): merge the duplicated Epic/GOG code (app_epic/app_gog, library sync, installer start/end),
  split the longest functions, check helper stderr (legendary/gogdl) can never put a token into app.log.
4 Hide from SCRiTCH (Omri's idea 17 Nov): hide a game's tile on this Deck only (store accounts unchanged); Settings ->
  Hidden games brings it back. Own DOS games already have Remove from library. Small.
5 Storage manager (Omri chose it 17 Nov): installed games by size, pick several with the pad, uninstall at once, clear
  old save backups. Medium.
IDEAS CONSIDERED AND DROPPED (Omri 17 Nov): collections (filters already cover it), per-game control modes (already
  exist), "what should I play?", phone-to-Deck link sharing (niche). Maybe later: play time + last played, per-game
  DOSBox settings (only if a game needs them).
PARKED: DLC for Epic and GOG; cloud saves for Epic and GOG; browser games.
DECIDED AGAINST: console emulators / a ROM library (Omri 17 Nov: not planned), a Steam tile for every game, IGDB,
  fetching DOS games for the player.
LESSON (17 Nov): do NOT poll api.github.com in a loop. Unauthenticated calls are 60 per hour PER INTERNET ADDRESS, and the
  Deck shares Omri's home address: my polling made the Deck's app say "can't reach GitHub" until the hour reset.
  After a push look ONCE, a little later (github.com/GoOmri/Itch-deck/releases is fine to read), never a loop.

## v0.9.23 (17 Nov, branch v0925-hide-games; waits for "push v0.9.23") = Hide from SCRiTCH (roadmap 4)
- Omri's choices: only games that are NOT installed can be hidden; purple "Hide" confirm; the way back is a library
  FILTER (Sort & filter -> Show -> "Hidden games"), not a Settings row; this Deck only, store accounts untouched.
- cfg "hidden" = list of game ids; Library.hidden / set_hidden(ids) (App passes cfg at start); Library._apply_install sets
  g["hidden"] = id in hidden and state not installed/missing/downloading/queued (installing a hidden game brings it back).
  visible(): show="hidden" lists only hidden, every other Show value excludes them (all tabs). Empty message
  "No hidden games. Hide a game from its Options and it shows up here."
- Game page Options: "Hide from SCRiTCH" for state None/failed and not busy (also non-playable games and Epic/GOG
  pages, which had no Options before: their page now shows Install + Options); a hidden game's Options = "Show in
  SCRiTCH" (no confirm). App._set_hidden saves config, hides -> back to the library + toast "X is hidden.".
- tests/test_epic.py + test_gog.py: the not-installed Epic/GOG page now has Options ["Hide from SCRiTCH"]. New
  tests/test_hidden.py (5). Mockups 15z/15za/15zb, 06k/06l/06m rendered and looked at. UNVERIFIED on the Deck.
- Deck check: open a not-installed game -> Options -> Hide -> Hide: tile gone from All and its store tab; X -> Show ->
  Hidden games: it is there; open it -> Options -> Show in SCRiTCH: back. Restart SCRiTCH: still hidden. Hide survives a sync.
- Reviewer-agent findings on v0.9.23, fixed: (1) the hidden flag was only recalculated at start or on a sync, so a hidden game
  that got installed stayed hidden (Options = only "Show in SCRiTCH") and a later uninstall hid it again: Library.refresh_hidden
  runs on every install-state change (Installer._upd) and forgets the id (on_unhide -> App drops it from config "hidden");
  (2) the top bar said "2 of 50 games" inside the Hidden filter: now just "2 games"; (3) the Genre filter offered genres of
  hidden games: it uses the games of the current Show. Tests 7 in tests/test_hidden.py.
- Steam tile art (Omri 17 Nov, after seeing v0.9.22 on his Deck: "an image on a blurred copy of itself because the tile is high"):
  in the same release as Hide from SCRiTCH. (1) Epic keeps its portrait box image (stores/epic.py `tall_url`, types
  DieselGameBoxTall/DieselStoreFrontTall/OfferImageTall; library cache keeps it); Add to Steam downloads it once (steam_games.
  fetch_tall, 8 s timeout, offline = the normal cover) and uses it for the <appid>p portrait tile only. (2) compose(): a cover
  FILLS the tile (cropped) when that cuts at most 45 % of it (steam_games.fills: square/tall covers on the tall tile, wide
  covers on the wide tile), else fitted over a darkened blurred copy ("more squared", his words). itch has one cover only;
  GOG might have a vertical image format (UNVERIFIED, not done); own DOS games: a tall cover.png in the folder is used.
  Existing tiles keep their art (never overwritten): Remove + Add again to get the new look.
- Reviewer-agent findings on the tall art (v0.9.23), fixed: (1) a download that is not a picture (an HTML error page, cut-off file)
  was cached forever and gave a title card: fetch_tall writes <id>-tall.jpg.part, checks it loads as a picture, then renames;
  a damaged cached file is deleted and fetched again; (2) the screen waited on the download once per Steam user: it is fetched
  ONCE before the user loop, in a thread, and gives up after 8 s in total; (3) a fill could come out 1 px short (a black line
  at one edge): sizes round up when filling; a transparent cover shows the dark tile, not black. Tests 22 in test_steam_games.py.

## v0.9.23 CI fix (18 Nov): the build failed in the SMOKE TEST (`scritch --selftest`), not in pytest
- Cause: itch_deck/app.py _selftest_gog asserted a not-installed GOG game page has actions == ["Install"]; v0.9.23 added the
  Options button (Hide from SCRiTCH) so it is ["Install", "Options"]. I had updated test_epic/test_gog but not this assertion.
- How it was found: the build file now lists failing test names as annotations; pytest passed and the job's steps showed
  "Smoke test" as the failing step (api.github.com/repos/GoOmri/Itch-deck/actions/runs/<id>/jobs). The selftest can be run
  locally up to the Epic part with PYTHONUTF8=1, a fcntl stand-in on PYTHONPATH and SDL_VIDEODRIVER=dummy.
- LESSON: when a UI change alters what a screen offers, grep app.py's selftest for assertions about it, and run
  `python run.py --selftest` as far as it goes before pushing.

## v0.9.24 (18 Nov, branch v0926-storage-manager; waits for "push v0.9.24") = Storage manager (Settings > Storage > Manage games)
- Omri's choices: opens from Settings > Storage; games only (save backups later); sort switchable Size / A-Z / Last played (Y, remembered in
  config "storage_sort"). Replaces the WIP note above.
- itch_deck/storagemgr.py (entries: installed, not "missing", not store "dos"; size from the game or the install record; drive
  SD card/Internal; ordered; total_mb; mb_text; drives() = free/total of SD card + internal), ui/scenes/storage.py (StorageManager:
  drive lines, count + "N selected · frees X", scrolling rows with a checkbox; A tick, Y sort, X uninstall, B back),
  app_storage.py (go_storage, _h_storage, red confirm "Uninstall N games? Frees about X. Windows saves are kept.", one
  Installer.uninstall per game with its v0.9.13 delete guards; a failure (SD card out) = error toast, the rest still goes;
  free space refreshed every 2 s while the folders are deleted in the background). Settings row value "12 games · 38.4 GB".
  The Storage group is now Install location, Saves of uninstalled games, Manage games (Games & controls rows are one index
  later in mockups: 9, Help 12).
- Tests: tests/test_storage.py (8, run on Windows). Mockups 22_storage_manager, 22b_selected, 22c_confirm, 22d_empty, 22e_az
  rendered and looked at. UNVERIFIED on the Deck. Not done: moving ticked games to the other drive (Options -> Move exists per
  game), clearing save backups.
- Deck check: Settings > Storage > Manage games: drives show free space; games by size; A ticks, count + "frees X" update;
  Y changes the order; X > Uninstall removes them (free space grows a few seconds later); an SD card out = "Couldn't uninstall...".
- Reviewer-agent findings on v0.9.24, fixed: (1) ticking several Epic games started several `legendary uninstall` runs that each
  rewrite installed.json: EpicStore.uninstall now takes a lock (one at a time); (2) B from Manage games sent Settings' own B to the
  Library instead of the game page it came from: settings_back is restored; (3) after a partial failure only the games that
  really went lose their tick; (4) removed the old WIP note. Not changed (minor): drives() runs on the main thread every 2 s (same
  cost as _check_mounts), the list is only refreshed after an uninstall, after Y the highlight stays on the same position.

## v0.9.25 (18 Nov, branch v0925-deck-feedback; waits for "push v0.9.25") = Omri's Deck-test feedback
- DOS: a folder with no program of its own and 3 or more game folders inside (what DOS.zip unpacks to) now gives one tile per
  game (`dosgames.collection`). Helper-named folders (setup...) do not count. The old "DOS" tile goes on the next Refresh; no
  file is touched. Removing one game inside remembers that sub-folder's name.
- DOS folders on BOTH drives: `Installer.dos_roots()` reads scritch/dos on the SD card and on internal storage (first the one for
  the install location; the other only if it exists). Settings > DOS games still shows the install location's folder only.
- "Game details 1/5" on every Y: a page that itch answered with 404 was saved without a genre, so `_has_page_fields` was
  False and it was fetched again each time. Now a "missing" page counts as done for 7 days. UNVERIFIED that Omri's 5 are all 404s.
- Game page Options: an installed itch game had 6 rows. Now Uninstall, Controls, More; More holds Change build, Saves, Move to...,
  Add/Remove Steam (`Game.menu_split`, only when the list has more than 4 rows and at least 2 of them are in RARE). B in More goes
  back to Options. Epic/GOG/DOS lists (4 or fewer) are unchanged. Selftest's Move step opens More first.
- Uninstall (game page and Manage games) also removes the game's Steam tile (`_drop_steam_tile`; says "Its Steam tile goes after
  a Steam restart"). A Steam file error never stops the uninstall.
- Send logs: the "A saves a copy" hint moved from the grey subtitle into a box under the steps (the subtitle is shorter now).
- Move progress bar "stuck at the start": the Game scene draws the fill correctly when fed rising progress (checked headless), so
  the cause is NOT found. The move now logs "move <id>: N% of M MB copied" every 10% in app.log. UNVERIFIED / OPEN: on the Deck,
  move a game and send app.log: if the percents rise, the problem is drawing; if not, it is the copy loop.
- NOT built: "X on a tile opens its options". X is Sort & filter, Y Refresh, Menu Settings in the library. Needs a new button (ask Omri).
- Check on the Deck: DOS.zip splits into tiles; zip on internal storage is found; Y no longer says Game details every time;
  Options shows More; uninstalling Kids removes its Steam tile after a Steam restart; Send logs shows the box under step 3.
- Reviewer findings on v0.9.25, fixed: (1) a missing dos folder on the install drive stopped the scan before the other drive was read,
  and the games already listed from there vanished (they were only dropped from the list, no file touched); (2) an old "removed" mark
  on the single "DOS" tile hid the games inside it; (3) folder names containing a helper word ("Mouse Hunt", "Patch Adams") were
  skipped: now only whole names like Setup/Tools/Editor are helpers. KNOWN, not fixed: a game that keeps its programs only in 3+
  sub-folders and none at the top is split into tiles, and a collection cut down to 2 games turns back into one tile.
- v0.9.25 CI fix: the first build of v0.9.25 failed on Linux in test_only_the_newest_backups_are_kept (4 backups instead of 5). Two
  shortcuts.vdf writes in the same millisecond got the same backup name, so the second copy overwrote the first. Backup names are now
  made unique (-1, -2 ...). Real but tiny bug, not caused by the v0.9.25 changes. No release v0.9.25 existed (build stopped at tests).

## v0.9.26 (18 Nov, branch v0926-deck-feedback2; waits for "push v0.9.26") = more Deck feedback
- Removed the "More" row again (Omri). The game Options list is flat as before v0.9.25 (itch installed game: 6 rows).
- Removing one of your own DOS games now HIDES it (config "hidden", same as Hide from SCRiTCH) instead of forgetting it by folder
  name. It shows under Sort & filter > Show > Hidden games; its page has "Show in SCRiTCH" (no Install button); showing it starts a
  DOS scan, which lists the folder again. Scans now list every folder (hide={}) and the old "removed" marks in dos.json are IGNORED, so
  games removed with v0.9.19 to v0.9.25 come back as installed on the next Refresh. apply_dos puts hidden games in the library list
  but not in the install index. Files are still never touched.
- DOS game page: the description line is "A DOS game from your own folder. Put a cover.png in its folder to give it artwork." (was
  "Loading details from itch.io…"). Itch's line is now just "Loading details…". Artwork for DOS games: only cover.png/jpg in the folder
  (no online lookup, no generated title card) - ask Omri if he wants one.
- Dialog titles wrap (W.modal) so "Remove <long name>" stays in the box; the Remove text is shorter.
- A menu or picker that opens starts with its focus in place (Scene.overlay setter calls W.forget_menu), no slide from the last time.
- Send logs: the Save hint box is narrower (more room before the QR address).
- Move progress bar (Omri: a thin bit of purple, then stops): probable cause = a progress update on every 4 MB chunk made the page re-draw ~25 times/s and starve the screen. Updates are now at most every 0.4 s. UNVERIFIED (not reproduced here); app.log has "move <id>: N% ..." lines either way.
- UNVERIFIED on the Deck: all of the above.

## v0.9.27 (18 Nov, branch v0927-dos-art; waits for "push v0.9.27") = art and info for your own DOS games (part 1)
- Each DOS game now asks GOG's public catalog (catalog.gog.com, no key, no login) for a match. A match gives the tall cover,
  GOG's description and screenshots (same page fields as GOG/Epic pages: "From GOG"). No match = a generated title card
  (dark blue-purple, thin purple line, the name in Inter Bold, wrapped). The folder's own cover.png/jpg ALWAYS wins for the cover
  (GOG text still shows). Nothing is ever written into the player's DOS folder: GOG art lives in data/dosart/, the text in pages/,
  the answers in data/dosart.json.
- New itch_deck/dosart.py (pure, no network/files): parse() cleans the folder name (signs, v1.1, shareware/registered/full/retail/cd/dos/cracked,
  [..] and (..) groups, ".exe", Doom2 -> Doom 2, & = and, accents folded) and reads a year 1980-1999 out of the groups first;
  queries() = up to 4 search texts (full, Doom II -> Doom 2, before the subtitle, without a leading Commander/The);
  choose() scores candidates (exact 100 > starts-with 85/70 > contains-all 62; a lone word that only starts a title is too weak),
  sequel numbers must agree (Doom / Doom II / Doom 3; no number = 1), a pack (productType pack or Complete/Collection...) is
  accepted for any episode but a single product beats it; year hint: equal +20, +/-1 +12, else -25 (not for packs); no hint: the earlier
  release wins; minimum 60, two different games within 5 points = NO match (title card). Last try: the name without its trailing number.
- library.py: job kind "dosart" (priority 6, after covers/pages, 1.5 s pause between games, hidden games skipped), cache per game
  in data/dosart.json for 30 days, "no match" too; another name = new lookup. The Refresh box (Settings > DOS games) asks again for
  games whose answer is older than a day (a Refresh may not bypass the cache more than once a day). Offline = nothing cached, asked again later.
  A cover that is not a picture is dropped. If the match changes, the old art/text go (our own files only).
- widgets.py: title_card(); for store "dos" a tall (or very wide) cover is shown WHOLE over a dark blurred copy (like the Steam tile)
  instead of a middle slice; other stores unchanged. The game page text: GOG's text replaces the "A DOS game from your own folder..." line
  (that line stays when there is no text).
- tests/conftest.py: every test's net.get / net.get_json refuses ("offline") unless the test stubs it. selftest(): the DOS lookup is stubbed.
  tests/test_dosart.py (22 tests). Mockups 06n (title cards) and 15zc (DOS page with GOG text) added, rendered and looked at.
- Tests on Windows: 44 failed / 271 passed, the same 44 failures as main (list in scratch/base3.txt); selftest fails on main and here at the same
  Epic step (Windows). Mockups render (230).
- UNVERIFIED (no Deck, no real GOG here): the live catalog answer (only fake answers were tested; field names from Omri's 18 Nov check:
  id, title, releaseDate, productType, coverVertical, genres is a guess and tolerated if missing), how good the matches are on real folder names,
  how the tall cover looks on the Deck, the real api.gog.com/products answer for a pack id.
- Check on the Deck: put a Keen and a Doom folder in dos/, Settings > DOS games > Refresh: after a minute they get a cover + text ("From GOG");
  a made-up folder name gets the title card; a folder with its own cover.png keeps it; the dos folder has no new files. app.log lines:
  "dosart <id>: <title> (<gog id>, score N)" or "dosart <id>: no match, title card".
- Not done / ideas: wrong matches can be fixed only by renaming the folder; no per-game "pick another" yet (ask Omri).
- v0.9.27 review fixes (same release): a rescan during a cover download no longer loses the cover (the CURRENT entry gets it); a broken cover or failed text is tried once per cache entry ("cover_tried"/"text_tried"), not on every scan; packs follow the same rules as games (one common word is too weak; the folder's sequel number must be inside the pack: Doom 3 / Doom 64 do not match "DOOM + DOOM II"; when a pack fits, a single game from 2000 or later (DOOM 2016) is dropped, and a game more than a year off the folder's year loses); the number-dropped last try (dosart.find, the `if p["num"] and p["bw"]` block near the end) KEEPS the folder's title and uses only GOG's art (no description: match["fallback"]); the DOS page line about cover.png only shows when there is no cover; title card font never below the theme meta size, ellipsis on the last line, long words cut; mockups 06o (tall art with blurred edge) added, 15zc has no Comments. Tests: 30 in test_dosart.py; 44 failed / 279 passed, same 44 failures as main.

## v0.9.28 (18 Nov, branch v0928-dos-fixes; waits for "push v0.9.28") = DOS fixes from Omri's Deck test
- SCAN BUG ("new folders and zips do not show"): NOT reproduced with a layout like his (dos/DOS/18 games + new top-level folders + new zips,
  on two roots): the scan, the install index and the DOS tab all listed every game. Causes found and fixed, any of which would hide new games:
  (1) a game folder with the SAME NAME as one already listed (e.g. the same games copied again, or inside DOS/ and at top level) was dropped
  silently (the id comes from the folder name): now the first keeps its id, a second same-named folder gets its own id from its path (other
  drive keeps the old "first drive wins" rule); (2) each drive is read in BOTH names, itch/dos and scritch/dos (games_dir() picks only one,
  so files copied into the other were never read); (3) one folder that raised an error stopped the whole scan: now it is logged and skipped;
  (4) own DOS games that were hidden (Remove) were not in the DOS tab's Hidden filter, so re-copied games that match an old removed name
  looked "missing" (fix 2 below). app.log now has "dos: <folder> -> N games" per folder. If it still happens, send app.log.
- Hidden own DOS games show in the DOS tab under Show > Hidden games (the filter and the tab now also test store == "dos").
- DOS titles are tidy: "Commander Keen 3 Keen Must Die (1990)(Apogee Software)" -> "Commander Keen 3 Keen Must Die" (dosart.display; year
  read first; subtitles stay). Same titles get the year, else the brackets text, else (2). Ids and folders do not change. The GOG search uses the
  clean title + year, also tries "commander keen 3" (name before the subtitle); cache key = that clean name (ALGO 2: asked again once).
- Art lookups first: dosart jobs have priority 0 (were 6, behind 500+ covers/pages); the page you open is -1. queue_dosart runs after every scan.
- Wide GOG cover (coverHorizontal, ~16:9) is the tile art; it is cropped to fill the tile (small crop, no blurred bars). The tall one is kept in
  the cache (cover_tall) and is the fallback; a tall picture is still shown whole over a blurred copy. Old tall art from v0.9.27 is replaced.
  The folder's cover.png still wins. File shape used: whatever coverHorizontal is (jpg/webp), saved in data/dosart/<id>.*, shrunk to 720 px.
- GOG text: only the first paragraph, cut at a sentence (about 600 characters), sentences about a pack/bundle/collection/"includes"/"both games"/
  "A + B" dropped. A match found without its sequel number (the last try) still gives art only, no text, and never GOG's title.
- Program to run: the list scrolls (max what fits above the footer, "3 / 18" at the top right, long sub text wraps). Setup/install/config
  programs are listed with "Setup" at the right; picking one runs it ONCE at the next Play (default unchanged; kept in memory, a rescan forgets it).
  The default program skips trainer/cheat/tech/support/help/order/info/readme/vendor/hint names (whole words and short DOS forms like TECHSUPP,
  ORDERING; "Mouse Hunt", "Helpful Harry", "Technoid" are fine); saved choice and a name equal to the folder still win first.
- Manage games: "Tick" -> "Select"; X with nothing selected does nothing (no message); Y keeps the focus on the same game and the list glides.
- Crash safety (Omri: B crashes SCRiTCH on Bio Menace): NOT reproduced (B on the page, in the program list, after play, after a crash, on a hidden
  game: all fine in a headless run). The real cause may be an error that left no trace: an exception in a press or frame used to end the app
  without a line in app.log. Now run() logs "frame failed" with the traceback, shows "Something went wrong. It is in the log." and goes on (5 in
  3 s -> back to the library); uncaught errors in the main program and in threads are logged too. Selftest/tests run strict (errors raise).
- Answer for the checklist: Manage games -> B -> Settings (a NEW Settings page, on its category list) -> B -> the library if Settings was opened from
  the library, or the game page of the focused game if it was opened from a game page.
- Tests: tests/test_v0928.py (33). Windows: 44 failed / 312 passed, the same 44 failures as main (scratch/base3.txt); selftest stops at the same Epic
  step as on main (Windows). Mockups 06n/06o/06p (title cards, tall and wide art), 15zd (program list), 236 render.
- UNVERIFIED (no Deck, no real GOG): the real coverHorizontal shape and size; the scan bug on Omri's real folders; Bio Menace's real program names
  (TECHSUPP is a guess); the crash itself; how the program list looks with a real 30-program game.
- Check on the Deck: Refresh with new folders/zips on SD and internal: the DOS tab lists them (app.log "dos: ... -> N games" per folder); titles are
  clean; "dosart <id>:" lines appear for all DOS games within a minute or two; tiles show a wide cover; GOG text is short; Program to run on Blood: a
  Setup row runs once; Bio Menace starts the game; Manage games hints; B on a DOS page - if it crashes, app.log now says why.
- v0.9.28 review fixes: the error catcher writes each distinct error's traceback ONCE (repeats only counted, a short line every 5 s), stops with the real error after 3 trips to the library or 15 failures in 10 s, says plainly "Something went wrong."; a failed apply_dos can no longer block later Refreshes; the "run setup once" flag is a memory-only dict on the Installer (never saved, a rescan keeps it, a restart forgets it); versions like v1.3d / ver 1.1 are dropped whole; a long program name is cut with an ellipsis before the "Setup" label; the pick toast says "It will run once the next time you play."
- A second same-named folder's id now comes from its path INSIDE the dos folder (not the mount path), so a changed card label keeps it; it can still change if the first same-named folder is removed or a folder is moved (the first one holds the plain id).

## v0.9.29 (18 Nov, branch v0929-dos-art2; waits for "push v0.9.29") = DOS art round 2 (real Deck data) + small DOS helpers
- GOG search (dosart.find): after the cleaned name and its forms, the shorthand written out (alias table: dave -> dangerous dave, wolf3d, duke3d, keen), then the series name cut BEFORE the number ("commander keen 3 keen must die" -> "commander keen 3" -> "commander keen"). A match found by dropping the number is marked "fallback": art only, no text, the title stays the folder's (a pack that lists its own numbers, e.g. DOOM + DOOM II, is refused for Doom 3). "Episode N" is read as part of the game: "Bio Menace Episode 1 (1993)" = "Bio Menace". Tests use the real answers Omri checked by hand (fake catalog in tests/test_v0929.py).
- Steam is the SECOND source when GOG has no strong match (dosart.find_any / find_steam, stores/steam.py): strong title match only (same title, or the folder title before a ":" / " - " subtitle), same number, year ignored, no soundtracks/DLC. Wide header image for the tile, short description, screenshots, "From Steam". A GOG art-only match loses to a strong Steam match. Same cache as GOG (data/dosart.json, source stored in the match, 30 days, "no match" too, cover/text tried flags). ALGO 3: every DOS game is asked once more.
- Text: store text is read line by line; kept = the opening lines up to the first filler line ("Owners Receive:", a line ending ":", Includes, Key features, Bonus, bullets, numbered lists); pack/bundle/"combined product"/"A + B" sentences dropped; about 600 characters. TEXT_VER 3 is saved with the page: text saved by 0.9.27/0.9.28 is fetched and cut again once.
- Program to run list (shared W.menu): chevrons up/down, a thin scroll bar on the right, and the "n / total" counter whenever the list scrolls.
- Own DOS game whose program ends within 3.5 s with exit 0 ("closed straight away", the P01 log line stays): a dialog "That program closed straight away." / "Try another one under Options, Program to run." with a Program to run button (plain toast when there is only one program). Other games and real crashes keep the old words.
- Options: "Keep window open after the game" (Off; hint "Helps you read an error message"; A or left/right). On = DOSBox gets no final "exit" and stays at the DOS prompt; leave with View + Menu. Stored in config "dos_stay_open" (ids), never in the game folder.
- A run-once setup program that closes: toast "Setup closed. The next Play starts the game."
- Send logs: dossummary.py writes one line per own DOS game (clean title, program in use, programs and setups as names inside the folder, GOG/Steam match or "no match", age of the answer, last play "N s, exit X" from app.log). Zip: dos-summary.txt; Copy the text: the first 40 games; the issue link: about 700 characters of it. All through logshare.scrub() (tests: no token, home folder or path leaks).
- Tests: tests/test_v0929.py + test_v0929b.py. UNVERIFIED (nothing run on the Deck): the real Steam answers (names of search items, header image address cdn.akamai.steamstatic.com), how Steam header art crops in the tile, the real "closed in 1 s" exit code on the Deck (assumed 0), how Stay open looks in DOSBox Staging, the chevrons on a real screen.
- Check on the Deck: app.log "dosart <id>: ... (gog|steam <id>, score N[, art only])" for Keen 1/3/5/6 (art only), Bio Menace Episode 1, Duke Nukem 3D, Blood, Raptor; Doom page text is short; Indiana Jones shows the new dialog; Options > Stay open; Send logs has the DOS lines.
- v0.9.29 review fixes: Steam is stricter. Two different games that fit = no match, a "Title: Subtitle" match needs exactly ONE such item ("Dune" has Awakening AND Spice Wars; Prince of Persia too), more skip words (sound track, season pass, art book, playtest, beta, dedicated server, expansion pass...), and when the folder has a year and Steam's release year is more than 1 year off (a remake like Alone in the Dark, Duke Nukem 3D 20th Anniversary) the match is ART ONLY (no text). The tile uses the header image address appdetails returns (the old akamai address only when it is missing). "Part II / Chapter 2" stay sequel numbers; only "episode"/"ep" are dropped.
- A Steam error never throws away a GOG result; GOG found nothing + Steam down = nothing cached (SteamUnavailable), asked again at the next start, not again in this run; after a 429 / offline answer Steam is not asked again in this run; art-job questions to one site are paced 1.5 s apart (the ALGO bump no longer bursts ~20 games).
- Wording: "Keep window open after the game" (hint "Helps you read an error message"); one program closing at once says just "That program closed straight away."; the scroll bar sits a little further in. Mockups 15zh (Setup closed toast), 15zi (From Steam). Still UNVERIFIED on the Deck: real Steam answers and years, the pacing in real use.

## v0.9.30 (18 Nov, branch v0930-dos-controls; waits for "push v0.9.30") = each DOS game has its own controller keys
- Problem (Omri on the Deck): the one "Keys" layout fits no DOS game (could not shoot in Dave 2, proceed in Keen 3, select in Doom's menu).
- itch_deck/assets/dos_controls.json (human-editable): entries {id, names, [not], layout keys|keys+mouse|mouse, map button->key, hints [[button, plain words]], note, verified}. A name matches when the cleaned title STARTS with its words (Doom II = doom 2) and the next word is not another sequel number ("doom" is not "doom 3"; "not" vetoes like "dave the diver"). Entries: Doom + Doom II, Keen 1-3, Keen 4-6, Dangerous Dave / dave2, Bio Menace, Duke Nukem 2, Duke Nukem 3D, Wolfenstein 3D, Blood, Quake, Jazz Jackrabbit, Raptor, Indiana Jones and the Fate of Atlantis (point and click: layout mouse). ALL FROM MEMORY, every entry has verified:false (the page then says "Controls are a guess. Tell us if one is wrong."). NOT SURE: Space as the pogo stick in Keen 1-3; Dave's jetpack/climb keys; Bio Menace and Duke Nukem 2 action keys (Space); Duke Nukem 3D weapon keys (number keys are not on the pad; L1/R1 = step left/right instead); Quake's Shift = run and sidestep keys; Blood's sidestep keys; whether Esc is Indy's menu. Send corrections and the file is edited.
- No entry = the default: left stick + D-pad arrows, A Ctrl, B Alt, X Space, Y Enter, L1 Shift, R1 Tab, Menu Esc, right stick + R2/L2 = mouse. For own DOS games AND GOG DOS games the Controls row's Auto picks the game's entry (else the default); Pad / Mouse / Keys still force a mode (Keys = the game's keys, or the default for a mouse game; Mouse = the plain mouse layout). Other games: nothing changed.
- mouse.Mapper has a keymap mode (layouts keys = no pointer, keysmouse = keys + right stick pointer + R2/L2 clicks unless the map gives the triggers keys, mouse); new keynames.py lists the keys the virtual keyboard can press (Ctrl, Alt, Tab, digits, letters, comma, period, F1-F10, mouse buttons). dos_controls.py loads/validates/matches; a missing or broken file or entry is logged once and the default is used.
- Game page: under the description a "Controls" block with the real button glyphs (DualSense shows its own), one line per few buttons; the Controls row in Options has a one-line hint ("A Fire · B Open doors · X Run"); picking a controls mode says the same. Mockups 15zj (Doom), 15zk (Keen 3) in scratch/mock30.
- Tests: tests/test_v0930.py. UNVERIFIED (nothing run on the Deck): every key in the file, how DOSBox takes the keys from the virtual keyboard, how the Controls block looks on a real page.
- Keys from the game's own files (dosinput.py): scans the folder read-only (depth 2; *.txt *.doc *.1st *.nfo *.me, readme/manual/help/instruct/controls/keys*; plain text only, 300 KB per file, 1 MB total, cp437 with box drawing turned to spaces), finds "Ctrl = jump" / "Jump: Ctrl" / "Press J to jump" / "Hold Alt to strafe" / table and "CTRL fire, SPACE open doors" lines, ignores cheat codes, F-key help, install lines; roles (fire jump use pogo run strafe map menu confirm weapon crouch) go to buttons by a fixed priority (fire A, jump B, use X, run L1, menu Start, confirm Y ...), WASD manuals put the sticks on W A S D. Needs 2+ distinct actions. Source order on the page: verified list entry, files, untested list entry, default. Dim line under the block: "From the game's own files" / "From our list (not tested)" / nothing for the default; "Controls are a guess. Tell us if one is wrong." for everything but a verified entry. Result cached per game in data/dosinput.json with a signature of the text files (names, sizes, times); run on the library queue (priority 0) after each scan; app.log "dosinput <id>: N actions from X" or "none", and the DOS summary has a "keys:" part.
- The Controls block is two columns of "[pad icon] action" (W.glyph follows the pad in use: Deck letters, DualSense shapes, pills). Mockups 15zj/15zk (Deck) and ps_15zj/ps_15zk (DualSense) in scratch/mock30. Tests (tests/test_v0930b.py) use MADE-UP manuals only: Keen-style, Doom-style, a table, WASD, cheats/F-keys, a binary file, a huge file, a cp437 box table. UNVERIFIED: how well it reads REAL manuals (all of them are untested), and every key.
- v0.9.30 review fixes: keys from the game's files are only an OVERLAY on the table entry (else the default): they replace just the buttons they named a real action for (fire jump use pogo run strafe weapon crouch; at least 2 needed; menu/confirm/pause/quit never count), keep the mouse (keys+mouse), and are never used on a point-and-click entry (Indiana Jones stays playable); Esc always stays on Start, Enter on Y, P/Q/"quit" keys are never mapped.
- The DOSBox manual is skipped (paths containing dosbox, lines about emulation, full screen, keymapper, cycles, Alt-Enter, Ctrl-F..); the scan counts EVERY byte read (binary files too) toward 1 MB, sniffs 4 KB before reading more, and looks at 40 files at most, readme/manual/controls/keys/help/instruct first (a test with 200 binary .hlp files).
- Wording: dim line "From our list. Not tested, so a key may be wrong." / "From the game's own files. A key may be wrong." / "Controls are a guess. Some keys may be wrong." (nothing for a verified entry), an S gap before it, D-pad / Right stick in body size and normal colour. Mockup 15zl (Options with the Controls hint, one line at both sizes).

## v0.9.31 prep (18 Nov, branch v0931-test-tools; tests only, no VERSION bump) = a plain test run is all green on Windows
- tests/windows_known_failures.txt lists the tests that need Linux (paths like /run/media, fake helper scripts, fcntl, file modes). tests/conftest.py skips exactly those on Windows only, and puts a stand-in `fcntl` module in place so the mouse tests load. On Linux (CI) nothing is skipped. Windows run: 395 passed, 46 skipped. If you fix one of these tests, delete its line.
- test_phone.py::test_big_or_empty_posts is in the list too: it is flaky on Windows (ConnectionAbortedError), also on main.
- New tools outside the repo, in E:\Projects\GIT\tools: check.py (tests, --mockups, --selftest on Linux) and ship.py (dry run unless --yes; checks clean tree, VERSION, no-reply e-mail, merges with --no-ff, pushes; --feed shows the newest releases once).
- The standing rules for agents now live in E:\Projects\GIT\.claude\agents\coder.md and reviewer.md, so briefs only need the task.
- Unverified: nothing here touches the app. CI on Linux still has to run the full suite once.

## v0.9.31 prep (18 Nov, branch v0931-scrub-logs; maintenance A, no VERSION bump yet) = app.log can never hold a token
- Why: when legendary or gogdl failed, the last lines of their error text were written to app.log as they came. Send logs cleaned them, but the file on the Deck did not.
- logshare.scrub_secrets() hides only secrets (the first 6 rules of scrub: Bearer, key=value, --auth-code flags, ?token= in URLs, JWTs, 32+ mixed-case keys). app.SecretFreeFormatter runs every record (message and traceback) through it, for app.log and the console. Paths, ids and names stay in app.log (they are needed to debug) and are hidden only when logs are shared (scrub). It never raises.
- Checked against Omri's real app.log of 18 Nov: 27 of 2251 lines change, all long Epic artwork file names in old cover errors (over-hiding noise only). "exit code: 0", "ERROR CODE P01", paths and dosart lines are untouched.
- Tests: tests/test_scrub_secrets.py. Unverified: how a real legendary/gogdl error looks (needs the Deck); the patterns are the same ones that already protect Send logs.
- NOT done (maintenance B/C): merging the duplicated Epic/GOG code and splitting long functions. Omri decides later.

## v0.9.31 prep: text-file reader removed (Omri 18 Nov, he never asked for it by name)
- dosinput.py and everything that used it is gone: the background job, data/dosinput.json reading, the "keys from files" part of the DOS summary, and the "From the game's own files" line. Controls now come only from the table (assets/dos_controls.json) or the default layout. A leftover data/dosinput.json on a Deck is never read and not deleted.
- Unverified on the Deck: that a DOS game page still shows its Controls block and the dim line; app.log should no longer have any "dosinput" lines.

## v0.9.31 RELEASED 18 Nov (Omri: "push the update") = log scrub, test skip list, text-file reader removed
- Contains the three "v0.9.31 prep" sections above. VERSION 0.9.31. Check on the Deck: DOS game pages still show Controls; app.log has no secrets and no "dosinput" lines; the app starts and updates as before.
