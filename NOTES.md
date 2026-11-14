# itch-deck — working notes (read this first in a new chat)

Plan doc: https://claude.ai/artifact/3UHDDdBhbp2BFbKZwvqvRg

## Current milestone
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
Design pass (own session, Omri 14 Nov): one consistent graphic language — e.g. Settings Update
  button is a pill, should match the standard button. Collect items here until then.
v0.3.2 Deck test 14 Nov: pad hotplug ✓, extracting animation ✓. Figment now gets past Vulkan
  (Mesa GL threads up), black screen, then SIGSEGV in game code -> Mono abort, exit -6 after 6 s.
  Not our libs any more. Unknown if it runs at all on SteamOS: test it as its own non-Steam shortcut.
  Unity's real error is in ~/.config/unity3d/<company>/Figment/Player.log. Ideas for M5 per-game
  launch options: -force-glcore, -screen-fullscreen 0, -screen-width 1280 -screen-height 800;
  also try OVERLAP_S=0 (our window still up when Unity picks its resolution?).
M3 — DONE 14 Nov (Bleed 2 installs, plays, uninstalls from the pad). Figment = known issue -> M5.
Next: M4 (umu + GE-Proton) in a new chat.

## Code map
- app.py: App = scene switcher (setup/library/game/settings), key import + check thread,
  per-scene _h_<kind>() input. Flags: --windowed, --selftest (fake data, temp dirs), --render-mockups.
  Install/Cancel/Play/Uninstall via game_action(); confirm(title, body, yes, fn) dialog.
  Change build = toast until M5 (picker).
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

## Known issues (cosmetic, Omri: "not that bad")
- Launching a child: Steam UI ("Steam menu" / "Back" hint bar) flickers twice. Cause: the gap while
  our display is closed (display.quit -> child window up, and child exit -> display reopen).
  Idea to test later: keep our window up until the child has had ~1 s to map, then quit display;
  on return, draw a "Returning…" frame first. Try in M3 with a real game.
- App start: Steam logo, then 2 flickers before the window. Likely onefile unpack + SDL fullscreen
  mode switch. Ideas: set_mode(desktop size, NOFRAME) instead of FULLSCREEN; --onedir build.
- Screenshots are centre-cropped to 16:9 (strip + viewer); viewer should letterbox instead. Small.
