# SCRiTCH — design principles

One graphic language, Steam Deck native, readable from the couch. Every value lives in
`theme.py`; every shape comes from `ui/widgets.py`; phone pages share the same rules in
`phonelink.py`. If a screen needs something new, add it there first, then use it.

Each principle says the rule and **why**. When a new case comes up, follow the why.

---

## 1. The name is the brand — always SCRiTCH
Capitals, lowercase **i**; every letter purple, the i white. Everywhere: logo, titles,
dialogs, footers, tags, toasts, phone pages. Never one colour, never lowercase.
*Why:* it's the one thing people remember. A name that changes shape looks like two apps.
*How it's kept:* ONE place draws it — `W.render_text` (all app text) and `phonelink.named`
(HTML); `tests/test_name.py` fails if it breaks. (Only the OS window title can't be coloured.)

## 2. Colour means something, or it isn't there
- **Purple = happening or yours:** progress, rings, spinners, the ✓ badge, Installed /
  Recommended / Developer tags, the selected tab — and the page's ONE main button
  (Install / Retry install, Play, Update / Restart). While downloading the progress is the
  purple thing; Cancel stays grey.
- **Red = error, or an action that deletes or closes** (Quit, Uninstall in their dialogs).
- **Green = one place only:** the phone page's confirmed "Connected". Never in the app.
- **Everything else is neutral:** blue→purple gradient background, navy-grey surfaces
  (`panel`, `panel_hi`), three text colours (`text_c` content, `dim` secondary, `faint` disabled).
*Why:* if colour is decoration, it stops meaning anything. One purple button tells you what
to do next (like Steam, PS5, Xbox); red is only scary when it's rare.

## 3. Focus is light, not colour
Buttons, rows, fields: grey → lit (`focus_fill`), text dim → white; no outline. Pictures
(tiles, screenshots) grow 6% with a thin light line (`focus_line`). Exactly one thing is
focused, always visible.
*Why:* purple already means "main action". If focus were purple too, you couldn't tell
"this is selected" from "this is the important one".

## 4. Buttons: one style, sized by what they belong to
- **Text is always white.** A main button is **deep purple at rest** (#6846b8, 6.7:1) and
  **bright when focused (app) or pressed (phone)** (#9d6bff). Red buttons work the same way.
  Grey for everything else. *Why:* white on bright purple fails contrast (3.5:1); deep at
  rest reads, bright on focus shows it's live.
- **A button is as wide as the block it belongs to.** Alone under a form or a full-width
  field → full width of that block (phone "Send to your Deck"). In a row or a result →
  sized to its text with a minimum width (`W.button_w`, phone `min-width:11rem`), never
  stretched. Same height and text size everywhere. *Why:* width shows what the button acts
  on; a lone button floating next to a wide field looks unfinished.
- **A button that can't do anything yet is grey**, and turns purple the moment it can
  (Send: grey until something is pasted). *Why:* it says "do this first", without words.

## 5. Few parts, used the same way everywhere
| Need | Use |
|---|---|
| Press something | `W.button_row` / `W.button`; `accent=True` only for the main action |
| Label a fact | `W.tag(kind=neutral/accent/error/dark)` — squarer radius (`t.tag_r`) so it never looks pressable |
| A list to pick from | `W.rows`; small menus (Options, Sort & filter, build picker) = `W.menu` |
| Something went wrong / is waiting | `W.notice(kind="error"/"busy")` |
| Say something briefly | `W.toast` |
| Ask yes / no | `W.modal` with its buttons inside |
| Show which pad buttons do what | `W.hint_bar`; in a sentence with glyphs `W.glyph_line`; in plain text `pads.name("A")` |
| Phone result | `phonelink.result()` |
Shape: one radius (`t.radius`) for panels, buttons, rows, images, dialogs, toasts. Fully
round only for progress bars, rings and pad glyphs. Icons are drawn (`W.icon_draw`, phone
SVG), never font characters.
*Why:* every new part is something to learn. Same job → same part → nothing to learn twice.

**Glyphs speak the pad in your hands.** Footer, dialogs and sentences show the buttons of the
pad pressed last (Settings → Button symbols overrides): Deck = A B X Y + ⧉ ☰, DualSense =
✕ ○ □ △ + CREATE / OPTIONS pills, Xbox = A B X Y + LB RB LT RT. Texts never hard-code a button
("A to check" → `pads.name("A")`). *Why:* "press A" on a DualSense is a riddle.

## 6. One place for each thing
- **Game page:** ONE main button (Play / Install / Retry install; Cancel while downloading)
  + a square **⚙ Options** next to it. Uninstall, Change build, Controls live in Options;
  ☰ opens it too (on a game page ☰ = Options, never Settings).
- **Install progress is one module** next to Cancel: Starting…, Queued, Getting GE-Proton,
  Downloading %, Extracting…. No boxes appearing and disappearing under it.
- **Messages about a game** go in ONE box under its buttons (`W.notice`). Never above.
- **Pad actions** are in the footer: right-aligned, B always last; empty states don't repeat
  them. **Yes/no dialogs** (Quit, Uninstall) show their buttons inside: [action, Cancel],
  action focused first, ◀ ▶ to switch.
- **Library:** tabs All · Installed · Recent (L1/R1) — no more tabs. **X = Sort & filter:**
  Sort (A–Z / Recently added / Shortest first), Show (Everything / Playable here), Genre (Any +
  the library's genres), Length (Any / Under 2 h / 2–10 h / 10 h+ from HowLongToBeat main
  story; unknown only under Any, sorted last). Remembered. ◀ ▶ or A change a value, each value
  shows its count, the title the live total, "Clear filters" when filtering, the top bar the
  active filters ("Puzzle · 26 games"). Genre goes in the info line; time to beat gets its own
  dim line ("Main story ~4 h · Completionist ~9 h"), or nothing if HLTB doesn't know the game
  (strict title match: no time beats a wrong time).
- **Settings** (from the Library's ☰): grouped Library · Storage · Games · App under
  LABEL-style headings; the list scrolls instead of squeezing.
*Why:* when everything has one home, people stop searching. Buttons scattered over a page
read as "too much".

## 7. Type: five sizes
TITLE 5.2u · SECTION 3.2u · BODY 2.7u · META 2.4u · LABEL 2.0u bold UPPERCASE.
Every section header is SECTION; LABEL is only for the footer, tags and Settings headings;
sentence case everywhere else ("Change build").
*Why:* fewer sizes = clear hierarchy from couch distance.

## 8. Space and width: a scale, not numbers
- Space: XS 1u · S 2u · M 3u · L 5u · XL 8u, page margin 6u. Inside a component XS/S, padding
  M; between items M; between sections L.
- Width: **read** (`read_w` 80u) for short text, dialogs, status (long reading up to 1.4×);
  **page** (`page_w` 110u) for Setup and Settings; grid and screenshot strip use the margins.
*Why:* consistent gaps make things line up without thinking about it. Re-check with
`grep -n "t\.u \*" itch_deck/ui/scenes/*.py` — what's left should be sizes, not gaps.

## 9. Motion is calm; waiting is alive
- One tempo: `W.spring`, no overshoot (`SPRING_BACK` 0), `MOTION_MS` 240 ms. Pages swipe in
  (from the right going deeper, left going back); Library content swipes between tabs;
  tiles/screenshots grow on focus; toasts slide up; scrolling glides.
- The ONE springy thing: the tab underline (`TAB_BACK`).
- Buttons and rows never move — focus lights them in place.
- Waiting: **the chasing arc** (`W.chase`, used by `W.spinner`, the tile busy ring and the
  phone `.spin`): the front edge races ahead, the back edge catches up, the whole thing turns
  slowly (`CHASE_S` 1.4 s). The indeterminate bar glides end to end (`BUSY_SWEEP_S` 0.75 s).
- No sound or vibration of our own; Steam's are enough. Mockups show the end state.
*Why:* moving things you're about to press feels unstable; still things that are working
feel frozen. So: calm where you act, alive where you wait.

## 10. Words: only what the player needs
Short, plain, sentence case. "…" means in progress. No exit codes or jargon (details go to the
log). Errors say what happened and what to do. No explanations of how things work
("installer runs silently"): if it doesn't help decide or act, cut it.
Dialogs: at most 2 short sentences, one per line, always wrapped inside the box (`W.modal`
wraps; pass a list of lines). Text is never cut off.
*Why:* every extra line is something to read with a controller in your hands.

## Phone pages follow the same principles
Dark page, the name rule, the button rule, grey notes #9a9ab0, content below the notch
(safe-area top padding). Results (checking / connected / rejected / expired) are centred,
with a big round SVG icon (chasing spinner, green ✓, red ✗, grey ↻), a headline, one grey
line and one button.
