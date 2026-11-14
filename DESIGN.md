# scritch — design rules

One graphic language, Steam Deck native, readable from the couch. Every value lives in
`theme.py`; every shape comes from `ui/widgets.py`. If a screen needs something new, add it
there first, then use it.

## 1. Colour = meaning
- **Purple** means *happening or yours*: progress, rings, spinners, the ✓ badge, Installed /
  Recommended / Developer tags, the selected tab, the name, and the Play button and Update / Restart (only when an update is waiting). Never focus,
  never decoration.
- **Red** means *error*, nothing else.
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
| Press something | `W.button` (only Play and Update get `accent=True`) |
| Label a fact | `W.tag(kind=neutral/accent/error/dark)` |
| A list to pick from | `W.rows` |
| Say something went wrong / is waiting | `W.notice(kind="error"/"busy")` |
| Say something briefly | `W.toast` |
| Ask yes / no | `W.modal` (body only — actions live in the footer) |
| Show which buttons do what | `W.hint_bar` |

## 6. Actions live in the footer, once
Every pad action appears exactly once, in the footer: right-aligned, B always last. Dialogs
and empty states don't repeat them in their body.

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

## 9. Motion = one tempo
- State changes ease in ~120 ms (`MOTION_SPEED`); pages cross-fade in 160 ms; A press dips 6%.
- Nothing moves on its own except spinners and progress.
- Mockups show the end state.

## 10. Words
- Short, plain, sentence case.
- "…" means *in progress*.
- No exit codes or jargon on screen; details go in the log.
- Errors say what happened and what to do next.

---

## Audit log
- 14 Nov: all 7 audit items fixed (spacing scale, 2 widths, W.notice, actions only in the
  footer, 3 text colours, toast radius, drawn icons). Re-audit with:
  `grep -n "t\.u \*" itch_deck/ui/scenes/*.py` — what's left should be sizes, not gaps.
