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
- This file = the working rules, the code map, decisions, known issues, the roadmap and a one-line list of releases.
  New entries for a change go at the END of this file (what changed, what is unverified, what to check on the Deck).
- Everything older (milestones M0-M6, v0.2-v0.9.4, Epic research, design passes, old roadmaps) is in
  docs/history/NOTES-history.md. Search it (grep) instead of reading it all; it is long.
- The CURRENT roadmap is "Roadmap now" below (and the roadmap page, see there).
- The release-by-release notes (v0.9.5 to v0.9.31) are in docs/history/NOTES-history.md, in the section "Moved from NOTES.md on 18 Nov 2026". Search it with grep; do not read it all.

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

## Rules learned the hard way (18 Nov)
- Windows PC: run `python E:\Projects\GIT\tools\check.py` (add --mockups after UI changes). A plain run is all green: tests that need Linux are
  skipped on Windows (tests/windows_known_failures.txt); GitHub's build runs all of them. Ship with `tools\ship.py` (dry run unless --yes).
- A push to main publishes a release when VERSION is new. Only Omri's "push vX.Y.Z" (or "push" right after an offer) counts.
- NEVER poll api.github.com in a loop (60 calls/hour per internet address, shared with the Deck: the app then says "can't reach GitHub").
  After a push look ONCE, later: `python tools\ship.py --feed`.
- Never write into or delete a player's own files (DOS folder, saves): removing a game only forgets or hides it.
- app.log never holds secrets (app.SecretFreeFormatter); Send logs also hides paths and names (logshare.scrub).
- Keep work small: one change at a time, driven by Deck results; no new features while the freeze is on (Omri, 18 Nov).

## Where the newer code is (added since the code map above)
- DOS: dosgames.py (folder scan, programs, zips), dosart.py (GOG, then Steam: art/text), dosbox.py (commands), dos_controls.py +
  assets/dos_controls.json + keynames.py (controller keys per game), dossummary.py (Send logs), app_dos.py (screens/jobs).
- Steam shortcuts ("Add to Steam"): steam_games.py, steam_shortcuts.py, steam_art.py.
- Storage manager: storagemgr.py, app_storage.py, ui/scenes/storage.py. Hide from SCRiTCH: library.py (hidden), ui/scenes/library.py.
- Logs: logshare.py (cleaning), phonelink.py (phone page), app_logs.py. Updates: updater.py. Epic/GOG screens: app_epic.py, app_gog.py.
- Dev only: mockups.py (python run.py --render-mockups DIR), `python run.py --selftest`.

## Roadmap now (18 Nov; page https://claude.ai/artifact/Hkk8SQChbBUBbAJ1yVEbqo)
- FREEZE on new features. Next: the Deck checklist (https://claude.ai/artifact/XTgTWAaRGnpCpobvkD6TRo), then Omri's results.
- Waiting: controller test logs (for "hide extra controllers", Bleed 2; Omri 18 Nov: too tiring, parked), Blood sound error (DOS on hold), Indiana Jones program (a demo, left). Move progress bar: works (Omri 18 Nov). v0.9.32 Hide checks all good (Omri 19 Nov). 3.2 (Steam tile came back after uninstall) CLOSED 19 Nov, see the end of this file. Next: nothing open; waiting for Omri's next Deck result.
- Idea (Omri 19 Nov, not built): Show on the game page which store the game is from (itch, Epic, GOG, DOS).
- Idea (Omri 19 Nov, not built): Remove own DOS games from the Installed tab (they stay in the DOS tab).
- Idea (Omri 19 Nov, not built): Sort by size (game size on disk) in Sort & filter.
- Decided against (Omri 18 Nov): "X on a tile opens its options"; options stay inside the game page. Skipped: merging Epic/GOG code, splitting long functions.
- Parked: universal Sort & filter across tabs (Omri 19 Nov; it is per tab on purpose, 15 Nov), DLC and cloud saves for Epic/GOG, browser games, "pick another match" for DOS art. Decided against: emulators/ROM library,
  a Steam tile for every game, IGDB, fetching DOS games for the player.

## Releases (one line each; full text in docs/history/NOTES-history.md)
- v0.9.5 RELEASED 16 Nov (branch v095-gog; Omri "go and push" 14:45) = GOG versions + first-run setup + updates
- v0.9.6 RELEASED 16 Nov (branch v095b-gog-fix; Omri "push" 15:55) = Eye of the Beholder fixes
- v0.9.7 RELEASED 16 Nov (branch v097-dosbox; Omri "go and push" 16:22) = GOG DOS games via native DOSBox
- v0.9.8 RELEASED 16 Nov (branch v098-logs; Omri "go ahead" 17:50) = logs that survive + forget version on uninstall
- v0.9.9 (branch v099-dosbox-autoexec, waits for "push") = DOSBox Staging runs GOG's start commands
- v0.9.10 (17 Nov, branch v0910-gog-heroic-setup, pushed to main at Omri's request; tests only run on Windows partially) = GOG first-run setup like Heroic's se...
- v0.9.11 (17 Nov, branch v0911-fix-gog-setup, NOT pushed - waits for Omri) = FIX for v0.9.10's first-run setup
- v0.9.12 (17 Nov, branch v0912-dosbox-conf-lookup, NOT pushed - waits for Omri) = EOB: DOSBox couldn't open GOG's settings files
- v0.9.13 (17 Nov, branch v0913-safe-deletes) = safer deleting (from the read-only audit of 17 Nov)
- v0.9.14 (17 Nov, branch v0914-tidy) = tidy-up from the audit (no behaviour change)
- v0.9.15 (17 Nov, branch v0915-send-logs) = Settings -> Help -> Send logs (roadmap item 2)
- v0.9.16 (17 Nov, branch v0916-logs-fixes; waits for "push v0.9.16") = fixes from Omri's Deck test of Send logs
- v0.9.17 (17 Nov, branch v0917-logs-copy-fix; waits for "push v0.9.17") = the real cause of "Copy does nothing"
- README update (17 Nov, branch v0918-readme; docs only, NO version bump = a push builds no release) = roadmap item 3 "Ready to share"
- v0.9.18 (17 Nov, branch v0919-dos-tab; waits for "push v0.9.18") = DOS tab, step 1 (roadmap item 4)
- v0.9.19 (17 Nov, branch v0920-dos-sketch; waits for "push v0.9.19") = DOS tab step 2: your own DOS games (roadmap 4)
- v0.9.20 (17 Nov, branch v0921-sources; waits for "push v0.9.20") = Settings: "Accounts" group -> "Sources" with the DOS row
- Add to Steam per game: plan + Deck experiment (17 Nov, branch v0922-steam-shortcuts; no VERSION bump, nothing uses it yet)
- v0.9.21 (17 Nov, branch v0922-steam-shortcuts; waits for "push v0.9.21") = Add to Steam per game (roadmap 6)
- v0.9.21 CI fix (17 Nov): the first build of v0.9.21 FAILED on GitHub (pytest), so no release was made and the Deck stayed on .20
- v0.9.22 (17 Nov, branch v0924-art-fix; waits for "push v0.9.22") = Add to Steam: art failed on the Deck
- v0.9.23 (17 Nov, branch v0925-hide-games; waits for "push v0.9.23") = Hide from SCRiTCH (roadmap 4)
- v0.9.23 CI fix (18 Nov): the build failed in the SMOKE TEST (`scritch --selftest`), not in pytest
- v0.9.24 (18 Nov, branch v0926-storage-manager; waits for "push v0.9.24") = Storage manager (Settings > Storage > Manage games)
- v0.9.25 (18 Nov, branch v0925-deck-feedback; waits for "push v0.9.25") = Omri's Deck-test feedback
- v0.9.26 (18 Nov, branch v0926-deck-feedback2; waits for "push v0.9.26") = more Deck feedback
- v0.9.27 (18 Nov, branch v0927-dos-art; waits for "push v0.9.27") = art and info for your own DOS games (part 1)
- v0.9.28 (18 Nov, branch v0928-dos-fixes; waits for "push v0.9.28") = DOS fixes from Omri's Deck test
- v0.9.29 (18 Nov, branch v0929-dos-art2; waits for "push v0.9.29") = DOS art round 2 (real Deck data) + small DOS helpers
- v0.9.30 (18 Nov, branch v0930-dos-controls; waits for "push v0.9.30") = each DOS game has its own controller keys
- v0.9.31 prep (18 Nov, branch v0931-test-tools; tests only, no VERSION bump) = a plain test run is all green on Windows
- v0.9.31 prep (18 Nov, branch v0931-scrub-logs; maintenance A, no VERSION bump yet) = app.log can never hold a token
- v0.9.31 prep: text-file reader removed (Omri 18 Nov, he never asked for it by name)
- v0.9.31 RELEASED 18 Nov (Omri: "push the update") = log scrub, test skip list, text-file reader removed
- v0.9.32 prep (18 Nov, branch v0932-hide-any-game; no VERSION bump) = "Hide from SCRiTCH" works for EVERY game
  - Offered (last row of Options) for installed, missing and not-installed games, store or own DOS; not while downloading/queued/moving. A hidden game stays hidden even when installed (auto-unhide, on_unhide and _forget_hidden are gone). Own DOS games: "Remove from library" is now "Hide from SCRiTCH" (same forget-the-entry code, files never touched; Refresh does not bring it back, Show in SCRiTCH does). Manage games already lists hidden installed games (no filter on "hidden").
  - UNVERIFIED on the Deck. Check: hide an installed itch game (gone from All, still in Hidden games, still in Settings > Storage > Manage games), hide a DOS game and press Refresh (stays hidden), Show in SCRiTCH brings it back; Install from the Hidden list. Log line: "hidden: <id> hidden / shown again".
  - Old configs: a game that had been auto-unhidden is simply not in the list; nothing to migrate.
- v0.9.32 RELEASED 18 Nov (Omri: "Push v0.9.32") = Hide from SCRiTCH for every game (branch v0932-hide-any-game)
- v0.9.33 RELEASED 19 Nov (Omri: "Push" right after my offer) = own DOS games are not in the Installed tab (branch v0933-dos-not-in-installed)
- v0.9.34 RELEASED 19 Nov (Omri: "Push v0.9.34") = store label (ITCH.IO / EPIC / GOG / DOS) on the game page (branch v0934-store-label)
- v0.9.35 RELEASED 19 Nov (Omri: "Push v0.9.35") = Sort & filter: Biggest first (branch v0935-sort-by-size)

## v0.9.32 CI fix (19 Nov): the first build of v0.9.32 FAILED in the SMOKE TEST, so no release was made (Deck stayed on .31)
- Cause: app.py _selftest_gog asserted the installed game's Options == ["Uninstall", "Controls", "Saves"]; v0.9.32 adds "Hide from SCRiTCH" last. Same lesson as v0.9.23: grep app.py's selftest for what a screen offers after a UI change.
- Fix: that one assertion now expects "Hide from SCRiTCH" at the end. UNVERIFIED: the selftest cannot run past the Epic part on Windows, so only GitHub's build proves it.

## 3.2 Steam tiles that vanished / came back: CLOSED (19 Nov, Omri's Deck tests; no code change)
- Symptoms: Epic games (FEZ = epic-Bluebird, Celeste = epic-Salt) added with Add to Steam were gone after a Steam restart; Kids (removed 18 Nov 10:08, log shows it) was back in shortcuts.vdf with the SCRiTCH tag.
- Our code did its part: app.log showed "added ..." / "removed ..." and itch + DOS adds and a remove stuck. Nothing in SCRiTCH removes a tile except Uninstall / Remove from Steam.
- Most likely cause (NOT proven): Steam kept an OLD copy of its list in memory (long-running session) and wrote it back over our edit when it exited.
- Clean slate (one-off script scratch/clean_steam_tiles.py, run in Desktop Mode with Steam CLOSED, removed only tagged --play tiles, kept a backup): after it, an itch and an Epic game both added and showed after a Steam restart; an uninstalled game's tile was gone after a restart. So Add / Remove work when Steam starts from a clean file.
- If it happens again: restart Steam properly (Switch to Desktop, then Return to Gaming Mode) before changing tiles; send app.log. Idea if it returns: a tile check in the log at SCRiTCH start/exit (not built).

## v0.9.33 (branch v0933-dos-not-in-installed, not released)
- Your own DOS games (from the dos folder) no longer show in the Installed tab. They stay in All, DOS and Hidden. GOG/Epic/itch games that run in DOSBox stay in Installed.
- Change: visible() in itch_deck/ui/scenes/library.py. Tests in tests/test_dos_tab.py. Selftest has no Installed-tab check, so nothing else needed.
- UNVERIFIED on the Deck. Check: Installed tab has no own DOS games; DOS tab still lists them.

## v0934-store-label (branch, not released, VERSION unchanged)
- Game page shows a small grey tag with the store under "by author": ITCH.IO, EPIC, GOG or DOS. Names live in `W.store_label` / `W.STORE_LABELS` (widgets.py); library tab names (`STORE_NAMES`) unchanged. No store key = itch. Only own DOS-folder games (store "dos") say DOS; GOG/Epic/itch games in DOSBox keep their store.
- Tests: tests/test_v0934.py. Selftest has no game-page text asserts, so nothing to update.
- Layout: tag is its own line (long titles/authors cannot collide). It adds ~35 px, so on pages with a long title plus many facts the buttons sit a little lower than the cover edge.
- UNVERIFIED on Deck. Check: the tag on a few game pages of each store, and one very long title.

## v0.9.35 prep (branch v0935-sort-by-size, VERSION unchanged)
- Sort & filter has a new Sort value "Biggest first" (SORTS and visible() in ui/scenes/library.py, `size_on_deck`). Installed (or missing) games with a size come first, biggest first, ties A-Z; everything else after them, A-Z. Each tab keeps its own sort.
- Sizes: no new source. The library's size_mb already comes from the install record (library._apply_install). Your own DOS games ALREADY get a size: dosgames.scan() walks each folder in a background thread (at start and on Refresh; symlinks not followed, unreadable folder = 0) and installer.apply_dos() saves it in the install record as "size". So no extra measuring or cache was built. A DOS game under 1 MB counts as unknown.
- Tests: tests/test_v0935.py. Selftest has no assertions about the sort list. DESIGN.md Sort line updated.
- UNVERIFIED on the Deck. Check: Biggest first on All and on Installed (sized games on top, rest A-Z); a DOS game sits among the sized ones after the start scan; nothing freezes.
