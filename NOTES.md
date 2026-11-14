# itch-deck — working notes (read this first in a new chat)

Plan doc: https://claude.ai/artifact/3UHDDdBhbp2BFbKZwvqvRg

## Current milestone
M4 built (v0.4.0) — waiting for the Deck test (checklist under M4 below). v0.4.1 = M4 + design
  pass; build picker shows "Installed" as an accent tag like "Recommended" (W.rows).
v0.4.1 Deck test 14 Nov: Figment WINDOWS build (Change build -> figment-windows-32.zip) installs,
  "Preparing Proton…", short black screen, then plays with pad ✓. Linux build still crashes
  (known, stays). Game showed Xbox/Steam glyphs, not PS: Steam Input hands Proton games a virtual
  Xbox pad. Possible later test: tile with Steam Input off + PROTON_ENABLE_HIDRAW=1 (risky: our
  app + Deck's own controls rely on Steam Input). Steam -> Exit game closes the whole tile incl.
  our app: by design (Steam ends the tile's process tree; v0.3.0 showed it can't be refused).
  To get back to scritch, quit from the game's own menu.
v0.4.2 (Omri): install folder path removed from the game page (Settings still shows the root).
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
    Developer tags, tab underline, wordmark — and the Play button (only coloured button;
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
  Next (asked): animation + feedback (A press, focus fade, page transitions, toast slide).
  Gallery = before/ (v0.3.2) + after/ with a Before/After/Side-by-side switch (AFTER_LABEL in index).

## Code map
- app.py: App = scene switcher (setup/library/game/settings), key import + check thread,
  per-scene _h_<kind>() input. Flags: --windowed, --selftest (fake data, temp dirs), --render-mockups.
  Install/Cancel/Play/Uninstall via game_action(); confirm(title, body, yes, fn) dialog.
  Change build = build picker (M4); exe picker + silent installers still M5.
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

## Known issues (cosmetic, Omri: "not that bad")
- Launching a child: Steam UI ("Steam menu" / "Back" hint bar) flickers twice. Cause: the gap while
  our display is closed (display.quit -> child window up, and child exit -> display reopen).
  Idea to test later: keep our window up until the child has had ~1 s to map, then quit display;
  on return, draw a "Returning…" frame first. Try in M3 with a real game.
- App start: Steam logo, then 2 flickers before the window. Likely onefile unpack + SDL fullscreen
  mode switch. Ideas: set_mode(desktop size, NOFRAME) instead of FULLSCREEN; --onedir build.
- Screenshots are centre-cropped to 16:9 (strip + viewer); viewer should letterbox instead. Small.
