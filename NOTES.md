# itch-deck — working notes (read this first in a new chat)

Plan doc: https://claude.ai/artifact/3UHDDdBhbp2BFbKZwvqvRg

## Current milestone
M0 spike — PASSED on Deck 14 Nov (checklist 1–6 all ✓). Focus hand-off to child and back works.
M1 mockups — BUILT 14 Nov (v0.1.0), awaiting Omri's look approval / change list.
  Gallery: https://claude.ai/artifact/9cciLymE4pGMV7rswahZkZ (21 states × Deck + TV size)
Next: apply M1 feedback, then M2 real library (ask Omri before starting).

## Code map
- app.py: M0 loop still runs at launch (scenes not wired in yet — M2). Flags: --windowed,
  --selftest, --render-mockups DIR.
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

## Token usage log (Omri's Pro plan %, as he reports it — add a line each time)
- 2026-11-14 00:08 — 72% at start of M0 build (planning + M0 in one chat)

## Known issues (cosmetic, Omri: "not that bad")
- Launching a child: Steam UI ("Steam menu" / "Back" hint bar) flickers twice. Cause: the gap while
  our display is closed (display.quit -> child window up, and child exit -> display reopen).
  Idea to test later: keep our window up until the child has had ~1 s to map, then quit display;
  on return, draw a "Returning…" frame first. Try in M3 with a real game.
- App start: Steam logo, then 2 flickers before the window. Likely onefile unpack + SDL fullscreen
  mode switch. Ideas: set_mode(desktop size, NOFRAME) instead of FULLSCREEN; --onedir build.
- M0 input only maps A/B/X/Y/Start/D-pad/left stick. LB/RB, LT/RT, Back/Select not mapped yet
  (needed per controller map) — add in the M2/M3 input pass.
