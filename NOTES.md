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
- Versions (Omri 14 Nov): middle number = milestone (0.6.x = M6), last number = each release
  inside it. M6 = mouse mode (0.6.0) + Settings polish, error messages, README (0.6.x).
- Write what you changed in NOTES.md before pushing, so the next chat knows.
- Real data for mockups: `python run.py --render-mockups DIR --real DATA` renders with Omri's real
  library (covers, pages, screenshots); random game, or SCRITCH_GAME=<title or id>. DATA = unzipped
  copy of the Deck's ~/.local/share/itch-deck/{library.json,covers,pages,shots} — ask Omri to attach
  it (Archive.zip). NEVER commit it: the repo is public, the art is the developers', the list is his.
- After ANY UI change: re-render mockups (`python run.py --render-mockups DIR`) and publish them as
  `after/` to the gallery artifact https://claude.ai/artifact/9cciLymE4pGMV7rswahZkZ (Omri expects it current).
- Ask Omri before big changes.
- CI (GitHub runner) HAS internet and runs as a normal user; this workspace has NO itch/GitHub
  access and runs as root. So: tests/selftest must never depend on the network (stub downloads;
  never leave a fake api_key in the selftest config), and file modes matter in CI. Before a
  release, run the selftest with itch.io rejecting every key (net.get -> AuthError for itch URLs).
  v0.7.0 needed 3 CI rounds for exactly these (15 Nov).
- A push to main = a release (CI publishes the VERSION in app.py). Bump VERSION for every
  release; since v0.6.3 CI refuses to re-release an existing version (warning, no release). Omri 14 Nov: no release
  until he says, so finished work waits on its branch.

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
Steam genres (branch steam-genres, NOT released; Omri 15 Nov "yes"): steam.pick_genre skips
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

## Code map
- app.py: App = scene switcher (setup/library/game/settings), key import + check thread,
  per-scene _h_<kind>() input. Flags: --windowed, --selftest (fake data, temp dirs), --render-mockups.
  Install/Cancel/Play/Uninstall via game_action(); confirm(title, body, yes, fn) dialog.
  Change build = build picker (M4) + "Program to run" row (M5).
- proton.py: umu-run download/lookup, GE-Proton dir, per-game prefix + env (M4).
- config.py (chmod 600, install_root: SD else ~/Games/itch, proton_versions), net.py (urllib +
  certifi; Offline/AuthError), stores/itch.py (owned-keys, quirk, dedupe), stores/itch_page.py
  (HTML -> description/shots/comments, tolerant), library.py (cache, sync thread, job queue:
  covers prio 1, opened page prio 0, prefetch prio 5, hltb prio 7; page cache 7 days, hltb 30;
  shots -> 1280px jpg). hltb.py: HowLongToBeat client + fmt/summary/length_hours.
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
- pygame-ce, PyInstaller folder build behind a self-unpacking launcher (v0.7.4; onefile before), built on GitHub Actions ubuntu-22.04; tag v* = Release.
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
- DONE (pad-glyphs): glyphs follow the pad in use (pads.py); Settings → Button symbols override.
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
- 2026-11-14 22:07 — v0.6.1 (SD pin + AppImage) after M5 Deck test; % not reported

## Known issues (cosmetic, Omri: "not that bad")
- Launching a child: Steam UI ("Steam menu" / "Back" hint bar) flickers twice. Cause: the gap while
  our display is closed (display.quit -> child window up, and child exit -> display reopen).
  Idea to test later: keep our window up until the child has had ~1 s to map, then quit display;
  on return, draw a "Returning…" frame first. Try in M3 with a real game.
- App start (v0.7.4 tries a fix, see above): Steam logo, then 2 flickers before the window. Likely onefile unpack + SDL fullscreen
  mode switch. Ideas: set_mode(desktop size, NOFRAME) instead of FULLSCREEN; --onedir build.
- Screenshots are centre-cropped to 16:9 (strip + viewer); viewer should letterbox instead. Small.

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
