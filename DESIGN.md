# scritch — design rules

One graphic language, Steam Deck native, readable from the couch. Every value lives in
`theme.py`; every shape comes from `ui/widgets.py`. If a screen needs something new, add it
there first, then use it.

## 1. Colour = meaning
- **Purple** means *happening or yours*: progress, rings, spinners, the ✓ badge, Installed /
  Recommended / Developer tags, the selected tab. Never focus, never decoration.
- The name is written SCRiTCH and is always purple (`W.text_named` in text). Only the logo
  (`W.wordmark`) has the white i.
- **One purple button per page: its main action** (like Steam, PS5, Xbox): Install (or Retry
  install) when not installed, Play when installed, Update / Restart when an update is waiting.
  While downloading there is none: the progress bar is the purple thing, Cancel stays grey.
- **Red** means *error*, or an action that deletes or closes (Quit, Uninstall buttons in
  their dialogs). Nothing else.
- **Everything else is neutral.** Background: blue→purple gradient. Surfaces: cool navy greys
  (`panel`, `panel_hi`).
- **Three text colours only:** `text_c` (content), `dim` (secondary), `faint` (disabled only).

## 2. Focus = light
- Buttons, rows, fields: grey → lit (`focus_fill`), text dim → white. No outline, no colour.
- Pictures (tiles, screenshots): grow 6% + thin light outline (`focus_line`).
- Exactly one thing is focused, always visible.

## 3. Type = 5 sizes
TITLE 5.2u · SECTION 3.2u · BODY 2.7u · META 2.4u · LABEL 2.0u bold UPPERCASE.
- Every section header uses SECTION ("Screenshots" = "About this game" = "Comments").
- LABEL is for the footer and tags only.
- Sentence case everywhere else ("Change build", not "Change Build").

## 4. Shape
- One radius (`t.radius`) for every panel, button, row, image, dialog and toast.
- Icons are drawn (`W.icon_draw`: play, check; footer ◀ ▶), never font characters.
- Tags: `t.tag_r` (squarer, so they never look pressable).
- Fully round: only progress bars, rings and pad glyphs.

## 5. Components (only these)
| Need | Use |
|---|---|
| Press something | `W.button_row` (a row) / `W.button` (one); `accent=True` only for the page's main action |
| Label a fact | `W.tag(kind=neutral/accent/error/dark)` |
| A list to pick from | `W.rows` |
| Say something went wrong / is waiting | `W.notice(kind="error"/"busy")` |
| Say something briefly | `W.toast` |
| Ask yes / no | `W.modal` (body only — actions live in the footer) |
| Show which buttons do what | `W.hint_bar` |

## 5b. Where things go (Omri, 14 Nov)
- **Game page:** ONE main button (Play / Install / Retry install; Cancel while downloading)
  + a square **⚙ Options** button next to it. Everything else (Uninstall, Change build,
  Controls) is in that menu; ☰ opens it too. ☰ on a game page = its Options, never Settings.
- **Library:** tabs All · Installed · Recent (L1/R1) — no more tabs (Omri). **X = Sort &
  filter**: Sort (A–Z / Recently added), Show (Everything / Playable here), Genre (Any + the
  genres in the library), Session (Any / Short / Long, from itch's "Average session"; itch has
  no time-to-beat). Remembered in config. Genre + session also show in the game's info line.
  In the menu: ◀ ▶ (or A) change the focused value, each filter value shows its game count,
  the title shows the live total, "Clear filters" appears when something filters, and the top
  bar shows the active filters ("Puzzle · 26 games").
- **Settings:** grouped (Library · Storage · Games · App) under LABEL-style headings; the list
  scrolls instead of squeezing rows. Settings is reached from the Library's ☰.
- All small lists (Options, Sort & filter, build picker) are the same `W.menu`.

## 6. Actions: footer, and buttons in dialogs
Every pad action is in the footer: right-aligned, B always last. Empty states don't repeat
them. Yes/no dialogs (Quit, Uninstall) DO show their buttons inside: [action, Cancel], the
action focused first, ◀ ▶ to switch (Omri). Messages about a game go in ONE box under its
buttons (`W.notice`: red for errors, neutral otherwise).

## 7. Space = 5 steps
XS 1u · S 2u · M 3u · L 5u · XL 8u, plus the page margin (6u).
- Inside a component: XS / S between its parts, M as its padding.
- Between items: M.
- Between sections: L.
- Around a page: margin.

## 8. Width = 2 measures
- **Read** (`read_w`, 80u): short text, dialogs, status boxes. Long reading (About,
  comments) may go to 1.4× read.
- **Page** (`page_w`, 110u): Setup and Settings columns.

Full-width content (grid, screenshot strip) uses the margins.

## 9. Motion = calm, one tempo
- Every move uses `W.spring` with no overshoot (`SPRING_BACK` 0: slow start, smooth settle)
  over `MOTION_MS` (240 ms). Omri: no bounce.
- What moves: pages swipe in (from the right going deeper, from the left going back), the
  Library content swipes when switching All/Installed, tiles and screenshots grow on focus,
  toasts slide up, scrolling glides.
- The ONE springy thing: the All/Installed underline (`TAB_BACK`). Omri likes it.
- Buttons and rows never move: focus lights them up in place (a short fade). No sliding
  highlight, no press dip.
- Waiting should feel lively: the busy bar bounces end to end (`BUSY_SWEEP_S` 0.75 s),
  stretching mid-flight; the tile ring spins and breathes.
- No sound or vibration of our own (Omri, 14 Nov): Steam's own UI sounds/haptics are enough.
- Mockups show the end state.

## 10. Words
- Short, plain, sentence case.
- "…" means *in progress*.
- No exit codes or jargon on screen; details go in the log.
- Errors say what happened and what to do next.
- Only text the player needs: no explanations of how things work ("installer runs silently",
  "used for Windows games"). If it isn't needed to decide or act, it goes.

---

## Audit log
- 14 Nov: all 7 audit items fixed (spacing scale, 2 widths, W.notice, actions only in the
  footer, 3 text colours, toast radius, drawn icons). Re-audit with:
  `grep -n "t\.u \*" itch_deck/ui/scenes/*.py` — what's left should be sizes, not gaps.
