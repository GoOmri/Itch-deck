# scritch — design rules

One graphic language, Steam Deck native, readable from the couch. Every value lives in
`theme.py`; every shape comes from `ui/widgets.py`. If a screen needs something new, add it
there first, then use it.

## 1. Colour = meaning
- **Purple** means *happening or yours*: progress, rings, spinners, the ✓ badge, Installed /
  Recommended / Developer tags, the selected tab, the name, and the Play button. Never focus,
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
- Tags: `t.tag_r` (squarer, so they never look pressable).
- Fully round: only progress bars, rings and pad glyphs.

## 5. Components (only these)
| Need | Use |
|---|---|
| Press something | `W.button` (only Play gets `play=True`) |
| Label a fact | `W.tag(kind=neutral/accent/error/dark)` |
| A list to pick from | `W.rows` |
| Say something went wrong | `W.notice` (red bar + text) |
| Say something briefly | `W.toast` |
| Ask yes / no | `W.modal` (body only — actions live in the footer) |
| Show which buttons do what | `W.hint_bar` |

## 6. Actions live in the footer, once
Every pad action appears exactly once, in the footer: right-aligned, B always last. Dialogs
and empty states don't repeat them in their body.

## 7. Space = 5 steps
XS 1u · S 2u · M 3u · L 5u · XL 8u, plus the page margin (6u).
- Inside a component: XS / S.
- Between items: M.
- Between sections: L.
- Around a page: margin.

## 8. Width = 2 measures
- **Read** (~75u): paragraphs, dialogs, short text.
- **Page** (~110u): Setup and Settings columns.

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

## Where the code breaks these (14 Nov audit)
1. **Space:** ~40 different spacing values (0.3u … 10u). → move to the 5 steps (rule 7).
2. **Width:** 7 different content widths (64, 70, 80, 100, 110, 125u). → 2 measures (rule 8).
3. **Notice:** the red error box is drawn by hand in 3 places (setup, game failed,
   `W.banner`). → one `W.notice`.
4. **Actions twice:** the quit / uninstall dialogs show A/B inside the dialog *and* in the
   footer; the empty Library shows "Y Refresh" in the body *and* the footer. → footer only.
5. **Text colours:** description and replies use two extra hard-coded greys (205 / 190).
   → `text_c` / `dim`.
6. **Toast** is a full pill, the only round panel. → `t.radius`.
7. **Icons:** ✓ and ▶ are font characters, while ◀ ▶ in the footer are drawn shapes.
   → draw all icons (check, play, cloud, triangles) so they match. (Low priority.)
