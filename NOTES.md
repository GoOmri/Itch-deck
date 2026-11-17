# SCRiTCH (repo itch-deck) — working notes (read this first in a new chat)

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
  copy of the Deck's ~/.local/share/scritch/{library.json,covers,pages,shots} — ask Omri to attach
  it (Archive.zip). NEVER commit it: the repo is public, the art is the developers', the list is his.
- After ANY UI change: re-render mockups (`python run.py --render-mockups DIR`) and republish the
  gallery https://claude.ai/artifact/9cciLymE4pGMV7rswahZkZ (Omri expects it current). Since 16 Nov
  it shows EVERY 1280x800 screen grouped (Setup, Library, Game page, Settings, Starting, Epic
  sign-in, DualSense) with a "Current work" section on top; changed screens go there with a
  one-line caption. Phone pages: https://claude.ai/artifact/2S5bbx6s8viDAjEsF4VY4d (itch + Epic
  flows, rendered from phonelink's own HTML; republish when phonelink.py changes).
- Ask Omri before big changes.
- CI (GitHub runner) HAS internet and runs as a normal user; this workspace has NO itch/GitHub
  access and runs as root. So: tests/selftest must never depend on the network (stub downloads;
  never leave a fake api_key in the selftest config), and file modes matter in CI. Before a
  release, run the selftest with itch.io rejecting every key (net.get -> AuthError for itch URLs).
  v0.7.0 needed 3 CI rounds for exactly these (15 Nov).
- A push to main = a release (CI publishes the VERSION in app.py). Bump VERSION for every
  release; since v0.6.3 CI refuses to re-release an existing version (warning, no release). Omri 14 Nov: no release
  until he says, so finished work waits on its branch.

## Where things are (split 17 Nov)
- This file = the working rules, the code map, decisions, known issues and the notes from v0.9.5 on.
- Everything older (milestones M0-M6, v0.2-v0.9.4, Epic research, design passes, old roadmaps) is in
  docs/history/NOTES-history.md. Search it (grep) instead of reading it all; it is long.
- The CURRENT roadmap is the "ROADMAP NOW (Omri 17 Nov ...)" section near the end of this file.

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

## Known issues (cosmetic, Omri: "not that bad")
- Launching a child: Steam UI ("Steam menu" / "Back" hint bar) flickers twice. Cause: the gap while
  our display is closed (display.quit -> child window up, and child exit -> display reopen).
  Idea to test later: keep our window up until the child has had ~1 s to map, then quit display;
  on return, draw a "Returning…" frame first. Try in M3 with a real game.
- App start (v0.7.4 tries a fix, see above): Steam logo, then 2 flickers before the window. Likely onefile unpack + SDL fullscreen
  mode switch. Ideas: set_mode(desktop size, NOFRAME) instead of FULLSCREEN; --onedir build.
- Screenshots are centre-cropped to 16:9 (strip + viewer); viewer should letterbox instead. Small.

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
