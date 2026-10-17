# The world-class plan: from "a demo that works" to a product people switch to

**Status: written by direct instruction, for the sessions after this one
(Opus and Sonnet, with a Fable review when one is available).** The
instruction, condensed: research the competitors, find what they have that
Tessellate does not, find how Tessellate can stand out, and plan every aspect
of the frontend, the backend, the missing features, the poor utility and the
small things that make an app feel professional rather than like a demo; make
the backend revolutionary; revolutionise UI design, backend structure,
agentic harnessing, and the app's abilities without AI.

This document does not repeat `ANALYSIS.md §114` (the competitive teardown
and the 90-day plan) or `MODERNISATION_AUDIT.md` (findings A to H with the
measured numbers). It builds on both and goes where they stop: it names the
system underneath the small things, gives every feature a dossier with a
gate, and specifies a backend and an AI harness that are a generation ahead
of "a FastAPI app that calls Ollama". Read those two first; this one assumes
them. Every brief below is written to be handed to a session on its own.

Reading order for a fresh session: `CLAUDE.md` → `HANDOVER.md` → this
file's §0 and §8 → the dossier for the feature you were given.

---

## 0. The diagnosis in one page

Three separate audits, two nights of live use, and about forty screenshots
from the owner say the same thing in different words: **every feature is
present, and almost none of them is finished.** "Finished" here has a
precise meaning, and the rest of this document is built on it:

1. **It is one thing, not a pile of parts.** A dock is a bar, not eleven
   buttons placed near each other. A menu is a list, not a stack of buttons.
   A card is a surface with content, not a card in a card in a card.
2. **It answers the next question.** A note shows what links to it. A search
   result says why it matched. A skill run says what it did and lets you
   undo it. An empty state says what to do.
3. **It behaves like its siblings.** Same type, same look, same keys, same
   place, everywhere. The owner's rule, verbatim: "ALL ELEMENTS AND CONTROLS
   OF THE SAME TYPE AND FUNCTION NEED TO BE, ACT, AND PLACED THE SAME
   APP-WIDE."
4. **It is designed for the screen it is on.** A phone gets a phone layout,
   not the desktop one squeezed until chrome is 76% of the page.
5. **It can be reached without a mouse and read without perfect eyes.**
   Arrow keys walk every strip; contrast is measured, not assumed.
6. **It never lies about state.** Saved means saved; running means running;
   an error says what failed and what to do.

The owner's own summary of what a professional app is: "the accessibility
and availability of things, placement and grouping of elements, consistent
design, things flowing and feeling connected." Those are not polish tasks
at the end; they are the acceptance criteria for every brief here.

### Why the app feels "off" even where each screen is fine

The owner said he "can't quite place or identify" it. Having measured, it is
five things, and none is a single screen's fault:

- **Too many surfaces.** Glass on a card on a panel on a page. Every layer
  has its own border and radius, so a settings row reads as a button inside
  a card inside a card. The fix is a surface budget: page, panel, card,
  control. Four levels, and a control never draws a box inside a card unless
  it is interactive.
- **Everything is a button.** Meta chips ("2 steps", "Never run"), model
  names, tags, statuses: all drawn with the button recipe. The eye reads
  forty affordances on a screen with six actions. Fix: a "meta" recipe with
  no border and no hover, and a lint that a `<span>` never carries a button
  class.
- **Filled accent everywhere.** Menu items, active chips, toggles, tiles,
  "Run" buttons, all in the same lavender fill, so the one primary action on
  a screen has no way to be found. Fix: one filled control per surface; the
  rest ghost or tinted.
- **Prose where a control should be.** Two-line explanations above and
  below every setting, so a settings page scrolls three screens for eight
  toggles. Fix: one line max, the rest behind the '?' popover.
- **Wrap instead of layout.** Below 1024 the docks and footers wrap into
  stacks; below 600 nothing changes at all. Fix: Phase 9, designed per
  breakpoint.

The same five, with a lint for each, are the "consistency contract" in §1.

---

## 1. The consistency contract (the system under the little things)

Every earlier plan fixed screens. This one fixes the vocabulary, then makes
the screens follow it. The contract is short enough to memorise and each
line has a lint that fails the build, because the app has been made
inconsistent three times by sessions that did not know the rule existed.

- (Odysseus, fourth read 2026-10-10) 

### 1.1 Surfaces (four levels, no more)

| Level | Recipe | Example | Never |
| --- | --- | --- | --- |
| Page | `--bg`, the gutter, nothing else | a tab page | a page border |
| Panel | card fill, glass edge, `--radius`, shadow at rest | a dock, a sidebar, a modal | a panel inside a panel |
| Card | card fill, hairline edge, `--radius-md`, no shadow | a note, a tile, a settings section | a card inside a card |
| Control | one of six recipes below | a button, a field | a control drawing its own card |

Lint: `tests/test_surface_budget.py` walks `index.html` and fails on
`.card .card`, `.panel .panel`, `.card details > summary.btn`, and on any
`.glass` inside `.glass`.

**State 2026-10-04:** (a) built, in `tests/test_consistency_contract.py` (not the `test_surface_budget.py` named above): fails on a card in a card, a panel in a panel, a glass in a glass and a `details > summary.btn` in a card; 0 offences in `index.html`.

### 1.2 Controls (six recipes, one height)

| Recipe | Use | Rest | Hover | Active |
| --- | --- | --- | --- | --- |
| primary | the one action on the surface | accent-surface fill, on-accent ink | brightness | pressed |
| ghost | every other button | no fill, ink | ghost-bg | accent-soft |
| icon | utilities (refresh, help, more) | ghost, square, `--control-h-lg` | ghost-bg | accent-soft |
| field | text/search/select | inset fill, one border, one radius | border ink | accent ring |
| segment | 2 to 5 exclusive choices | one track, ghost items | item ghost-bg | item accent-soft, ink |
| meta | chips, counts, statuses | no border, no hover, muted | none | none |

All six share `--control-h-lg` (36px) on docks and `--control-h` in forms,
`--radius-md`, the same focus ring, the same icon size (1em) and gap
(`--space-2`), and the icon-text centring rule. Lint:
`tests/test_ui_signatures.py` already counts recipes; extend it to assert at
most ONE primary per `[data-dock-name]` and per `.modal`, and that no
`.chip`/`.meta` has a `border` or a `:hover` rule.

**State 2026-10-04:** (a) built: one filled button per dock (`tests/test_dock_grammar.py`); one per modal and per settings pane, and the meta recipe's no border and no hover, in `tests/test_consistency_contract.py`, both strict since 2026-10-04 (design-1004): the five dialogs and panes that held two or three filled buttons hand one fill over with `stagePrimary`, and the 13 chip rules are 0 (a pressable chip is styled through `.chip-interactive`; the label recipe and a suggested tag keep their edge by name, `META_EDGED`). The account is in HISTORY.

### 1.3 Menus (one recipe)

A menu is `.menu` (panel surface, `--space-1` padding, min-width 14rem) with
`.menu-item` rows (ghost, full width, left aligned, icon column 1.25em,
label, optional right-aligned shortcut or check) and `.menu-sep` hairlines.
Opened by a `details` or a button with `aria-expanded`; closes on pick,
outside click and Escape; flips when it would overflow; arrow keys walk it;
typeahead selects. Every menu in the app (dock more, doc toolbar, whiteboard
Insert/Edit/Arrange/View/Board, chat, context menus, nav history) is this
recipe. Lint: a menu item with a non-transparent rest background fails
`test_ui_signatures.py`.

**The "act on this" rows (INBOX 393), where each object stands.** One
vocabulary on every object's own menu, one wording and one glyph per row
(`ph:chat-circle Ask Atlas about this` everywhere). Read from the code
2026-09-23; `tests/test_object_actions.py` holds every "yes" in the Ask
column and the one wording.

| Object, its menu | Open | Ask Atlas about this | Show in graph | Remind me | Link to |
| --- | --- | --- | --- | --- | --- |
| Note, Notes card ⋯ | the card | yes | yes | yes | yes |
| Note, Library card ⋯ | Open in Notes | yes | yes | yes | yes |
| Document, Library card ⋯ | the card | yes | yes | yes | no |
| Board or map, Boards card ⋯ | the card | yes | no | yes | no |
| Reminder, row ⋯ | Open its note, document, board or map | yes | no | n/a | no |
| File, Library card ⋯ | the card | yes (2026-09-23) | no | no | no |

The open rows named here on 2026-09-23 (Remind me on a document and a
board, Show in graph for a document, the Library note card's Remind me and
Link to) were built 2026-10-05; moved to HISTORY.md, "Moved from the plans,
2026-10-05 (nbf1005)". The "no" cells left are not planned.

**State 2026-10-04:** (b) the recipe is held by `tests/test_ui_recipes.py` (hand-built menus may not multiply, a pointer-anchored menu is the recipe, a long kebab is grouped); the rule that a menu item has no rest background is `tests/test_consistency_contract.py` (0 offences).

### 1.4 Bars (docks, heads, toolbars, footers)

A bar is one continuous panel surface. Zones inside it (identity, find,
arrange, actions) are separated by a hairline and equal gaps, never by
boxes. Controls inside are ghost, fields are inset, exactly one primary.
The identity zone never shrinks below its title. A form footer is a bar:
secondary on the left, primary at the far right, and nothing floats over
the primary (the scroll-to-top button hides while a footer is in view).
Lint: `tests/test_dock_grammar.py` (exists) plus a Playwright count in
`docks.js` of distinct control heights per bar (must be 1).

**State 2026-09-24:** (a) built: `tests/test_dock_grammar.py`, and `scratchpad/ui-sweeps/docks.js` reports the distinct control heights per bar.

### 1.5 Copy

Sentence case. No em-dashes (lint: `tests/test_no_em_dashes.py` over
`frontend/` and `src/`). One line of description per section, 70 characters
or fewer; longer help goes behind the '?' popover (`data-help-for`). Empty
states name the next action and carry a button for it. Errors say what
failed and what to do, in that order. Numbers use tabular figures.

**State 2026-09-24:** (a) built: `tests/test_no_em_dashes.py`, `tests/test_ai_name.py`, and the '?' popover recipe (`data-help-for`) standing order 6 names.

### 1.6 Keys (the same everywhere)

`/` focuses the surface's search. Arrows walk tablists, menus, lists,
grids. `Enter` opens, `Space` selects, `Escape` closes the innermost thing.
`Ctrl+K` command palette. `Ctrl+N` new note, `Ctrl+S` save, `Ctrl+B/I`
format. `+`/`-`/`0` zoom on canvases, `F` focus selection. `?` opens the
surface's help. Lint: `tests/test_keymap.py` parses a single `KEYMAP` table
in `app.js` and asserts no key is bound twice on the same surface.

**State 2026-09-24:** (a) built under other names: the one table is `DEFAULT_SHORTCUTS` in `app.js` (it also feeds the palette and the shortcut sheet), and `tests/test_frontend_shortcuts.py` asserts no two shortcuts share a chord and every shortcut has an action. There is no `KEYMAP` and no `test_keymap.py`, and nothing further to build.

### 1.7 Responsive (designed, not wrapped)

Four layouts: phone (≤ 600), tablet portrait (≤ 900), laptop (≤ 1280),
desktop. Each surface declares what it becomes at each: a dock becomes
identity + search + primary + more; a sidebar becomes a sheet; a grid
becomes a list; a canvas tool strip moves to the bottom; the tab bar
becomes a bottom bar with five items and "more". Chrome-to-content ratio
on a phone must be under 35% on every tab (measured by
`scratchpad/audit/chrome.js`; today 76%).

**State 2026-09-24:** (d) superseded by UI_MODERNISATION_PLAN Phase 11, whose gate is `scratchpad/ui-sweeps/phonechrome.js`: non-scrolling chrome at most 25% of the height, stricter than the 35% here (HISTORY, 2026-09-23, has the numbers).

---

### 1.8 Undo (one contract; decision 53, 2026-10-10)

Ctrl or Cmd+Z undoes the last edit where focus is (the editor's own
history, CodeMirror's for documents and code, the board's and the map's
histories). A destructive act that reaches the server (delete, bulk move,
a filing, an import, a skill run's writes) shows the undo bar
(`pushUndo`, `status.js`) with a ten-second window and the undo history
menu; nothing else invents an undo. Lint: `tests/test_undo_contract.py`
fails on a new function whose name contains `undo` outside `status.js`,
the editors' histories and the board history module, unless it calls
`pushUndo`; the six implementations of 2026-10-10 (`offerCategoryUndo`,
`chatDeleteUndo`, `undoDraft`, `pushDocAiUndo`, `activityUndoControl`,
`inlineAiUndo`) are the ratchet's starting list and fold into `pushUndo`
in Brief 51.

## 2. Competitors: what they have that Tessellate does not (checked, not
assumed)

`§114.1` has the positioning teardown. This is the feature-level gap list,
organised by what a switcher would miss on day one. "Have" means shipped
and used, as of mid-2026.

| Capability | Obsidian | Notion | OneNote | Kortex | Logseq | Capacities | Reflect | Tessellate today | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Block editor with slash commands | plugin | yes | no | yes | yes | yes | yes | textarea + toolbar | DOCUMENTS_PLAN Phases 2 to 4 |
| Wiki-links with autocomplete and backlinks pane | yes | yes | no | yes | yes | yes | yes | links exist, no `[[` autocomplete, no pane | Dossier D2 |
| Daily notes / journal with a calendar | plugin | template | no | yes | yes | yes | yes | none | Dossier D6 |
| Properties / typed fields per note | yes | databases | no | yes | yes | object types | tags | category + tags | Dossier D5 (typed properties) |
| Database views (table, board, calendar) | plugin | yes | no | partial | query | yes | no | Timeline table (in progress) | Dossier D7 |
| Canvas / whiteboard | yes | no | yes (ink) | yes | yes | no | no | yes | keep, refine |
| Mind map | plugin | no | no | no | no | no | no | yes | keep, refine (a differentiator) |
| Graph view | yes | no | no | yes | yes | yes | no | yes (SVG) | GRAPH_PLAN |
| Local AI chat over notes | plugin | hosted | Copilot | hosted | plugin | hosted | hosted | yes, offline | keep; make checkable |
| Per-claim citations in answers | no | partial | no | partial | no | partial | partial | source list only | §114 F2-1 |
| Web clipper / read-it-later | yes | yes | yes | yes | no | yes | yes | bookmarks only | Dossier D9 |
| PDF annotation | plugin | no | yes | yes | yes | no | no | text extraction only | Dossier D10 |
| Voice capture with transcript | plugin | yes | yes | no | no | no | yes | yes (Whisper) | keep; add the meeting block |
| Templates | yes | yes | no | yes | yes | yes | yes | yes | keep |
| Spaced repetition / recall | plugin | no | no | no | yes | no | no | none | §114 A1 |
| Sync across devices | paid | yes | yes | yes | yes | yes | yes | none | Dossier B6 (local-first sync) |
| Mobile app | yes | yes | yes | yes | yes | yes | yes | responsive web only | Phase 9, then a PWA shell |
| Import from Notion/Obsidian/Evernote | yes | yes | partial | yes | yes | yes | yes | Markdown folder only | §114 F5-3 |
| Version history per note | yes | yes | yes | yes | git | yes | yes | drafts only | Dossier B4 (event log) |
| Command palette | yes | yes | no | yes | yes | yes | yes | yes | keep; make it complete |
| Plugin / extension API | yes | limited | no | no | yes | no | no | MCP server | Dossier B8 |

**Where Tessellate can stand out** (the things no one on that table has, all
of which the code is already half way to):

1. **The checkable answer.** Every sentence of an AI answer carries the
   note it came from, an "I don't know" is a designed state, and a click
   shows why a result ranked. (§114 combo 1.)
2. **A notebook that files itself and can be audited.** Auto-filing with
   an undo trail and a "why did this go here" for every decision. Nobody
   else does the second half.
3. **Contradictions and tensions as a first-class object.** The
   "disagreed with myself" skill made into a live index and a Dashboard
   widget. (§114 F7-1.)
4. **Mind maps that are notes.** A map node is an entry; a map is a view of
   the notebook. Coggle and XMind cannot link a branch to a note; Obsidian
   cannot make a map at all without a plugin.
5. **A privacy receipt.** A page that proves, from the app's own logs,
   that nothing left the machine. Hosted competitors cannot ship this.
6. **The offline studio.** Audio overview, recall cards, a "brief me before
   the meeting" from the notes, all local. (§114 combo 3.)

**State 2026-09-24:** the Gap column read against the code. Built since the table
was written: `[[` autocomplete (D2), the daily-note backend and `Ctrl+D` (D6),
per-sentence citations with the unsupported-sentence line (CHAT_PLAN Phase
1), version history per note (B1), the palette and shortcut sheet from one
table, and a PWA manifest with a share target. Still a gap: typed properties
on notes (D5), the web clipper (D9), PDF annotation (D10, DOCUMENTS_PLAN),
recall cards (§114 A1), sync (B6), importers beyond Markdown (H6), and a
plugin surface beyond the MCP server (B8). Of the six standouts, 2 and 4 are
built, 1 and 3 are half built (I6, B4), and 5 (a privacy receipt page) and 6
(the offline studio) are not built: no code names either.

**State 2026-10-11 (by grep):** built since: typed properties (`entry/properties.py`),
the web clipper (`clip.html`), importers for notion, obsidian, evernote and
apple (`routes_import.py`), and the privacy receipt (5) as Settings, "Where
your data went" (`core/egress.py`). Still gaps: sync (B6), PDF annotation
(D10), recall cards (A1), the offline studio (6), a plugin surface (B8).

---

## 3. Frontend dossiers (one per surface, each a hand-off brief)

Each dossier: what exists → what is wrong (measured) → the target →
the brief → the gate. Effort is in sessions (S ≈ half a session, M ≈ one,
L ≈ two or more). "Owner" is the model that should do it.

### D1 Dashboard (M, Sonnet after a Fable/Opus design pass)

Exists: hero, Start something tiles, Jump to pills, Run a skill, stat
tiles, 24 widgets with a layout editor. Wrong: three launch rows plus a stat
row is four kinds of chip on one screen; widgets are 24 separate recipes;
the widgets dialog is a settings page inside a modal; the "Boards & maps"
widget shows raw thumbnails. Target: a dashboard that reads top to bottom
as greeting → what needs you (due reminders, drafts, tensions) → start →
your notebook (widgets), with one tile recipe and one widget frame (title,
optional count, optional "more" link, body). Brief: one `.widget` frame
component in `dashboard.js`; every widget renders into it; the layout
editor becomes drag-to-reorder on the grid itself with a "customise" mode
toggle; the widgets dialog keeps only add/remove. Gate: recipe count on
Dashboard ≤ 8 (audit script), all 24 widgets in the frame, 390px chrome ratio
< 35%.

**State 2026-10-05:** (b) every widget renders into one frame (`render(body)` over the `DASH_WIDGETS` table); drag-to-reorder on the grid itself is built (Edit layout makes each card `draggable`, `dashDragOverCard` moves it live, the drop saves the order; dashboard.js, found 2026-10-05, HISTORY.md "Moved from the plans, 2026-10-05 (nbf1005)"). Open: the recipe-count gate was not re-run. S, `dashboard.js`.

**The first screen, INBOX 436 (2026-10-03):** built; the diagnosis, the target and the before and after numbers are in HISTORY.md ("Moved from the plans, 2026-10-03").

### D2 Notes: list, capture, edit (L, Opus)

**Built** (`[[` autocomplete, and the connections rail 2026-09-27). Moved to HISTORY.md, "Moved from the plans, 2026-10-04 (D2 connections rail)", with the 2026-10-04 re-measure. Nothing of D2 is open here.

**Decision (INBOX 571, 2026-10-05):** the rail follows the note being read,
not a note "opened": the card chosen by hand, else the card in view as the
list scrolls; the subject card is marked with a left accent hairline.

### D3 Chat (M, Opus)

Exists: streaming answers, sources list, scope chips (backend), personas,
skills picker, tool cards, conversation sidebar. Wrong: no per-claim
citation; the composer's three rows of chips crowd the input; the sidebar
head is not on the dock grammar (in progress). Target: an answer whose
sentences carry superscript source marks that highlight the note on hover;
a composer that is one field with a "+" menu (attach, scope, persona,
skill) and a send button; the "I don't know" state designed. Brief: §114
F2-1 with `routes_chat.py` emitting `cite` events per sentence; composer
rebuilt on the bar recipe. Gate: 95% of sentences in ten fixture answers
carry a citation; composer height ≤ 2 rows at rest at 1024.

**State 2026-09-24:** (d) superseded by CHAT_PLAN (one composer; per-sentence citations built in its Phase 1).

### D4 Library (M, Sonnet)

Exists: All, Documents, Boards & maps, Images, Files, AI skills, Links,
Contents sub-tabs, each with its own head. Wrong: eight heads, five
recipes; image cards are 900px tall with "Show more" links and chip-buttons;
skills cards have button-shaped meta. Target: one head (the dock grammar),
one card per kind on one card recipe with a fixed preview aspect (16:10),
title, two meta lines, actions in a "..." menu; the image and file cards
open a detail sheet instead of expanding in place. Gate: card height
uniform per view (± 4px), one head recipe, `docks.js` count = 1 per
sub-tab.

**State 2026-09-24:** (d) absorbed by UI_MODERNISATION Phases 8 to 11 and the Library passes (list conventions 18 of 18, OPEN.md); the Files row redesign is INBOX 79 below.

### D5 Properties and tags (M, Opus)

Exists: category, tags, pinned, private, space. Wrong: tags are strings; no
typed fields; no way to say "this note is a person/project/book". Target:
typed properties per note (text, number, date, select, relation), stored
as JSON on the entry (`properties` column, indexed via a generated
`properties_text` for FTS), a property editor in the note head, and a
"kind" property with built-in kinds (person, project, meeting, book, place)
that drive the Library's grouping and the graph's colour rules. Brief:
migration + `/entries/{id}/properties` + editor. Gate: a property
round-trips through the API, FTS finds it, the graph colours by it.

**State 2026-10-05:** built. Typed properties on notes came with GRAPH_PLAN KG4 (2026-10-04); the built-in kinds and the graph's Note type colour on 2026-10-05. Moved to HISTORY.md, "Moved from the plans, 2026-10-05 (nbf1005)".

Built (KG4, then row 10): HISTORY.md, "Moved from the plans, 2026-10-05 (D5)". Left: the Library grouping notes by type.

### D6 Daily notes and the journal (S, Sonnet)

**The backend is built, 2026-09-13 evening.** `POST /entries/daily/{date}`
creates or returns (the matching GET is read-only and 404s, because a GET that
writes sits outside the CSRF defence, which judges methods) (which is what makes the key safe to press from anywhere:
`startTodaysNote` posted a new note every time, so a day opened twice had two
notes and its writing split between them), and `GET /entries/daily?through=&days=`
answers the calendar strip and the streak in one query.
`tests/test_daily_journal.py`. `Ctrl+D` from every tab is built (2026-09-23,
`todaysNote` in `DEFAULT_SHORTCUTS`, stepping aside on an open board by the
decision in HISTORY's INBOX 321; `oi-ctrld.js`). What is left is the strip
itself and the yesterday/tomorrow pair in the note head.

Exists: the daily-note convention (a note whose first line is `# <ISO date>`)
and the Today action, from timeline Phase 4; and now the endpoints above.
Originally: nothing. Target: `Ctrl+D` opens today's note (created from the
Journal template if missing), a calendar strip on the Timeline dock to jump
between days, a "yesterday / tomorrow" pair of links in the note head, a
streak that counts days with a daily note. Brief: `/entries/daily/{date}`
that creates or returns; the calendar strip as a `.segment` of seven with
overflow into a month popover. Gate: the key works from every tab; the
calendar reflects the DB.

**State 2026-10-04:** (b) the strip (seven days, a dot per written day, week arrows) and the day pair in a daily note's card are built (HISTORY, "the consistency contract's missing lints", row 12); the month popover is built too (HISTORY, same section). D6 is done.

### D7 Timeline (L, in progress: see TIMELINE_PLAN.md)

**State 2026-09-24:** (d) owned by TIMELINE_PLAN.md; nothing is tracked here.

### D8 Reminders (S, Sonnet)

Exists: natural-language add, presets menu, list with views. Wrong: the
list and the notes list use different rows; done items vanish rather than
strike through; no snooze. Target: reminder rows on the same row recipe as
notes, snooze (10m, 1h, tomorrow) in the row menu, done rows strike
through and fade, a "today" band at the top. Gate: row recipe shared
(one class), snooze round-trips.

**State 2026-10-05:** built. The reminder row is the notes' row recipe (`ul.entry-list` > `li` > `.entry-meta`, measured by `nbf1005-recheck.js`), done rows strike through, and the 10 minute snooze is on the row's menu beside +1h and tomorrow on the row. Moved to HISTORY.md, "Moved from the plans, 2026-10-05 (nbf1005)".

### D9 Links and the web clipper (M, Opus)

Built 2026-10-05: the brief and its record moved to HISTORY.md, "Moved from the plans, 2026-10-05 (the web clipper, from the browser)".

### D10 Documents and PDFs (L, see DOCUMENTS_PLAN.md; add PDF annotation as
Phase 8: highlight → note with page anchor, rendered by pdf.js vendored)

**State 2026-09-24:** (d) owned by DOCUMENTS_PLAN.md (PDF annotation is not built); nothing is tracked here.

### D11 Whiteboard and mind maps (M, in progress; then MINDMAP_PLAN Phases
4 to 5)

**State 2026-09-24:** (d) owned by WHITEBOARD_PLAN.md and MINDMAP_PLAN.md; nothing is tracked here.

### D12 Graph (L, GRAPH_PLAN.md)

**State 2026-09-24:** (d) owned by GRAPH_PLAN.md; nothing is tracked here.

### D13 Settings (M, Sonnet)

Exists: 3,229 lines of settings.js, ~40 sections. Wrong: prose-heavy,
toggle rows in two recipes, model backend card has three paragraphs.
Target: a two-pane settings (section list left, one section right, search
across all), every section = title + one line + controls, help behind '?',
danger actions in a separate red-edged group at the bottom of their
section. Gate: no paragraph over 120 characters outside a popover; one
toggle-row recipe; the section list is a tablist with arrow keys.

**State 2026-09-24:** (d) absorbed: the two-pane shell with a section list (`#settings-nav`, back and forward) and the '?' popovers are built by UI_MODERNISATION and Brief 4; the prose metric was not re-run here.

### D14 Help, onboarding and the command palette (S, Sonnet)

Exists: help accordion, the welcome overlay, the guided tour (`frontend/js/tour.js`,
DESIGN.md's "A guided tour of the interface": anchored cards over a cut-out
dim, four sections, replayable whole or one section from Settings, help and
guide), `Ctrl+K`. Wrong: the accordion is cards in cards; the palette lacks
half the actions. Target: help as a
searchable list on the panel surface with flat rows; the palette generated
from the same `ACTIONS` table the menus use, so nothing can be missing.
Gate: every `data-action` in the DOM appears in the palette.

**State 2026-10-04:** (b) the palette and the shortcut sheet come from one table (OPEN.md, DOCUMENTS_PLAN row); the gate is built as `tests/test_consistency_contract.py`: the app has no `data-action` attribute, so it reads the two places an action is declared (every `data-tab` button, every `DEFAULT_SHORTCUTS` chord) and fails on one the palette lacks. Four chords had no row and now do (today's note, go back, go forward, reload).

### D15 The shell: top bar, tab bar, bottom bar, sidebars (M, Opus)

Exists: top bar with wordmark, search, utilities (bell, theme, settings,
lock, power) as five square buttons; tab bar; resizable sidebars. Wrong:
the utility cluster is five boxes; on phone the tab bar overflows. Target:
utilities as an icon cluster with hairline separators on the bar surface;
a bottom tab bar on phone (five + more); sidebars as sheets under 900.
Gate: Phase 9 numbers.

**State 2026-09-24:** (d) absorbed by UI_MODERNISATION Phases 9 and 11 (the bottom tab bar on a phone, sheets under 900).

### D16 Write with AI, the writing desk (M, Opus)

**Built 2026-09-20; the dossier (measured before, target, gate, the
built table and its not-verified list) moved to HISTORY.md, "Moved from the plans, 2026-09-24".** State
2026-09-24: nothing open but its two not-verified lines (Stop mid-pass, a
real model's thinking stream) and section 20's open question of a model
badge in the desk's dock.

---

## 4. The backend, made revolutionary (and still SQLite, still offline)

"Revolutionary" here means: architectural moves that make whole classes of
feature cheap that are expensive today, without a server, a cloud or a
second database. Five moves, in dependency order.

### B1 The event log: every change is a fact, the tables are views

**Built.** HISTORY.md, "From WORLD_CLASS_PLAN.md B1 and SESSION_BRIEFS Brief 7: the event log" and "Moved from the plans, 2026-10-10 (WORLD_CLASS B1 and B3 summaries)"; what the log does not yet feed is in `docs/roadmap/archive/agent-remaining/brief7-event-log.md`.

**Decisions made (do not remake).** Copied whole from the agent file
on 2026-09-14 (INBOX 220) so they survive its archiving.

1. **Retention is compaction, and the policy is ninety days with the newest
   five kept.** Deletion would break replay. A run of events older than
   ninety days folds into one snapshot holding the whole state at that
   point; the rows behind it keep action, actor, detail and time and lose
   only their values. Five newest kept rather than twenty because
   `EntryRevision` already keeps the last twenty versions of every note for
   ever, so twenty here was a second copy of the same thing and collapsed
   nothing on an ordinary notebook.
2. **What compaction gives up, it says.** Restoring a version whose values
   are gone answers 410 with the reason; the History sheet renders "The text
   from this change is no longer kept." in that row.
3. **No `VACUUM` in the compaction pass.** The freed pages are reused
   immediately, so the file stops growing, and `ai/autonomous.py`'s
   `_vacuum` already returns them to the disk on its own schedule.
4. **A board's replayable entity is the item, not the board.** A note is one
   row and replays to one dict; a board is a note plus everything on it. So
   `whiteboard_node`, `whiteboard_sketch` and `whiteboard_object` each
   replay through `events.replay`, the board's own events (created,
   duplicated, generated, imported, settings changed) sit on `board`, and a
   board's whole state is the union of its items' replays.
5. **`rename_board` is not wrapped in a write scope.** Its title change goes
   through `manager.update_entry`; a scope would fold that note's own edit
   into the board's event and take it out of the note's history. The board's
   settings get their own event beside the note's, so that request records
   two events on two entities, by design.
6. **A compacted event reports what it is, not an edit.** A snapshot's
   `after` is the whole state, so `/events` read it as one change that set
   every field at once. The feed now reports `changed: []` and `snapshot`,
   the number of events the row stands for, and reports `compacted` on the
   rows whose values were dropped. A count rather than a span of time
   because the count is what the compactor knows and stays right when a
   later run folds more events into the same snapshot; the rows behind it
   keep their own timestamps for a reader that wants the dates.
7. **The AI's board tools write through the same helpers as the routes.**
   Four `@events.writes` helpers at the top of `ai/tools/whiteboard.py`
   (`_place_card`, `_draw_link`, `_place_object`, `_new_board`), and the
   payload builders (`events.node_state` and its two siblings, plus
   `events.board_state`) moved to `core/events.py` so both writers share
   one idea of an entity's state. The two batch tools stay undecorated and
   record one event per item: decorating a loop folds a whole batch into
   one event, which is the shape that lost the replay. The tools' entity
   types follow the routes' vocabulary (`whiteboard_node`,
   `whiteboard_sketch`, `whiteboard_object`, `board`); the old
   `mindmap`, `mindmap_node`, `mindmap_link`, `whiteboard_link` and
   `whiteboard_diagram` names had no reader.
8. **The index lives in `_INDEXES` and in a migration.** The startup path is
   what reaches an existing notebook; the migration is what reaches a
   database upgraded through Alembic alone. Both use IF NOT EXISTS, so they
   cannot disagree.

### B2 The job runtime: durable, resumable, observable

**Built 2026-10-04 for the pool's kinds.** Moved to HISTORY.md, "Moved from the plans, 2026-10-04 (B2 durable jobs)": the `jobs` table, leases with a heartbeat, resume after a kill (a real SIGKILL in `tests/test_jobstore.py`), `GET /jobs`, `GET /jobs/stream`, cancel of a queued job.

**Left:** the other kinds onto the table (re-index, embed, skill run, import, backup, model download: each runs in its own thread with its own cancel today and needs a handler that resumes from a cursor rather than from the start); the activity panel reading `/jobs/stream` instead of polling `/tasks`; a running job cannot be cancelled (cooperative stop per handler). M, Opus.

### B3 The retrieval engine: one index, three signals, explained

**Built.** HISTORY.md, "From WORLD_CLASS_PLAN.md B3 and SESSION_BRIEFS Brief 11: the retrieval engine" and "Moved from the plans, 2026-10-10 (WORLD_CLASS B1 and B3 summaries)"; what is left is in `docs/roadmap/archive/agent-remaining/brief11-retrieval-engine.md`.

**Corrected 2026-10-05 (audit ARCH-07, ARCH-03).** "Three signals" overstated
recall: candidates came from the keyword pass alone, so cosine only re-ranked
keyword hits (`horticulture`, `vegetable patch`, `gardn` all found nothing),
the vocabulary typo fix was never reached from here, and `GET /search`
ignored the active space. Now the matrix's nearest notes join the candidates,
a word the notes never use is corrected once, and the session's space narrows
the index read (`tests/test_search_recall.py`, `tests/test_search_spaces.py`).

**Decisions made** (the three the plan had made differently, revised against
the code and taken; the reasons are in HISTORY):

- A second FTS5 table (`search_index`), not a `kind` column on
  `entries_fts`: that one is external-content over `entries`, so its rowid
  is an entry id and a document could not have a row.
- The index's write path is an `after_flush` hook, not the event log: a
  document edit records no event, so an event-fed index would have gone
  stale on the commonest document write. Brief 7's loud driver is kept
  (`source_for` raises on an unregistered kind).
- `before:`/`after:` are exclusive, `until:`/`since:` inclusive; an
  unreadable date is left in the text rather than guessed at; a query with
  operators is never "time only".

### B4 The knowledge kernel: entities, claims, links, tensions

Today entities and links exist as tables written by skills. Move: a small
kernel that maintains, from the event log, derived tables: `entities`
(people, projects, places, terms; merged by alias), `claims` (a sentence
plus its note, extracted by the model when idle, with a confidence),
`links` (typed: refers-to, contradicts, supports, follows, part-of), and
`tensions` (pairs of claims the model judged incompatible). All derived,
all rebuildable, all with a "computed by <model> at <ts>" stamp shown in the
UI. This is what makes the Tensions widget, derived person/project pages,
per-claim citations and "what changed about X" possible. Gate: rebuild from
scratch on the fixture is deterministic; every derived row cites its
source event.

**State 2026-10-05:** typed links (KG3: `LINK_TYPES` plus a person's own relation types, with inverses), the derived tensions table, its rebuild determinism and the Tensions widget are built (HISTORY, "row 18: the derived tensions table"). Left: derived person and project pages beyond KG5's entity page, per-claim citations, and "what changed about X".

**Decisions made, 2026-10-05 (recommendations taken):** (1) B4's link
vocabulary is the one KG3 built, not a second one: refers-to is a wiki-origin
link (`origin="wiki"`), follows is `continues`, part-of is a person's own
relation type; adding five more built-ins would split one meaning across two
names. (2) The derived tensions table is a view: the source of a scan's
finding and of every decision is an event (`AuditLog`, `entity_type=
"tension"`), the night shift's findings stay in `derived_facts`, and the
accepted state is the `contradicts` link; the table is rebuilt when any of the
three moves, never written directly. (3) One pair, one row: the earliest
finding names it, and a link is "accepted" whoever made it; accepted and then
unlinked is a dismissal, so the pair is not offered again. (4) "Cites its
source event": the scan's own event, the link's `linked` event, or for a night
finding the later note's newest event when it was read. (5) Forgetting what
was derived (Settings, Learned) takes the findings and decisions with the
facts; a person's `contradicts` link stays.

### B5 The AI harness: plan, act, verify, budget, learn

Today: a step is a turn (MODERNISATION_AUDIT E1); tool contracts exist
(AGENT_SKILLS_REFORM Phases A to C). Move:

- **Typed tools with contracts** (exists) plus **pre/post conditions**
  checked in Python, not by the model: a `file_note` tool refuses a
  category that does not exist; a `merge_notes` tool requires both ids to
  be live.
- **A planner that emits a plan object** (exists as A2) that the executor
  runs step by step with a **token and time budget** per run, a **verifier**
  step that re-reads the changed rows and checks the skill's stated
  postcondition (e.g. "every note now has ≥ 1 tag"), and a **repair loop**
  of at most two rounds.
- **Small-model mode** (exists) made the default under 8B: one tool per
  turn, forced JSON via grammar when the backend supports it (llama.cpp
  and Ollama both do), few-shot from the skill's own eval cases.
- **Evals as fixtures** (A6 exists): every skill ships with three
  notebooks and expected outcomes; `pytest -m evals` runs them against
  the fake transport; a nightly local run against a real model writes
  `docs/MODELS.md` (the "I don't know" bench, §114 F2-2).
- **Learning from corrections**: when a user moves an auto-filed note,
  the kernel records a `correction` event; the filing prompt is built with
  the last N corrections for that category (§114 F1-1). No training, no
  telemetry, and the notebook gets better at filing itself.

Gate: on the eval fixtures, a 3B model completes ≥ 80% of built-in skills
with zero invalid tool calls; every run shows plan, steps, verification and
an undo button.

**State 2026-10-05:** (b) built: the verifier and budget (Brief 13, `tests/test_harness_verifier.py`), small-model mode in `run_agent` (audit A4), learning from filing corrections (`ai/learning.py`), and (row 19) pre and post conditions per tool (`ai/tools/contracts.py`) and the forced round decoded under a call schema on Ollama (llama.cpp already had it through `tool_choice`): HISTORY.md, "Moved from the plans, 2026-10-05 (row 19)". Open: the 3B gate (evals at 80%) and a 4B pass, which is section 9's breadth and needs a real model.

### B6 Local-first sync (L, later; design now)

Because B1 makes every change an event, sync is: export the log since a
cursor as an encrypted file, import elsewhere, resolve by last-writer-wins
per field with the event history kept (no CRDT needed for a single-user
notebook; conflicts become two versions in History). Transport: a folder
(iCloud/Dropbox/Syncthing) or a LAN pairing over the existing server with a
QR code. Gate: two instances round-trip 1,000 events with no loss.

**State 2026-09-24:** (c) not built; H5 below is the same row. L, design first.

### B7 The API contract

One error shape (exists, B3 in PLAN.md), cursor pagination on every list
(finish D4 in the audit), ETags on entries, `If-Match` on writes (so the
editor cannot clobber a background AI edit), an OpenAPI schema behind the
auth gate, and a `/capabilities` endpoint the UI reads once so features
appear only when their backend is there (OCR, embeddings, TTS).

**State 2026-10-05:** built (cursors on every paged list, ETags and `If-Match` on entries, `/capabilities`); moved to HISTORY.md, "Moved from the plans, 2026-10-05 (B7)". Left: the page's own lists following `X-Next-Cursor` on scroll, and the page reading `/capabilities` once to hide a control whose backend is not installed. S.

**Corrected 2026-10-05 (audit ARCH-12, ARCH-13, ARCH-04).** The error shape did not cover a request that failed validation: a 422 was FastAPI's own `{detail: [...]}` with no `code`, echoing the input (a password among them). It is one shape now (`tests/test_validation_error_shape.py`). "Every list takes a `limit`" holds only for functions named `list_*`, which is what the lint keys on: `/graph`, `/suggestions`, `/entries/link-suggestions`, `/documents/outline` and `/entries/query` are not covered (open). Cursor pagination exists for `GET /entries` (`after`, `X-Next-Cursor`; `tests/test_entries_keyset_paging.py`); the client still pages by offset (frontend audit FE-05).

### B8 Extensions

The MCP server exists. Move: the same tool registry that serves MCP serves
a `/tools` HTTP API and a "user skills" folder of Markdown skills (already
the skill format). That is the plugin API: a skill is a Markdown file with
tool calls; a tool is a Python function registered with a contract. Gate:
a skill dropped into the folder appears in the picker without a restart.

**State 2026-10-05:** built (the user skills folder, read per request); moved to HISTORY.md, "Moved from the plans, 2026-10-05 (B8, H4)". Left: a tool registered from the folder (a Python function with a contract) is not built, by design for now: a skill is Markdown, and code from a folder would need the trust model BACKLOG §29 names.

---

## 5. Abilities without AI (the app must be excellent with the model off)

The owner's phrase: "features of the application even without AI." Today
too much routes through the model. Each of these is pure code:

1. **Search operators** everywhere: `tag:`, `kind:`, `in:space`, `before:`,
   `after:`, `has:file`, `is:pinned`, quoted phrases, `-not`. One parser,
   used by Notes, Library, Timeline, Chat scope, the palette.
2. **Saved searches as smart folders** in the Notes sidebar (backend exists).
3. **Backlinks and unlinked mentions** (a plain FTS query for the title).
4. **Templates with variables** (`{{date}}`, `{{title}}`, `{{clipboard}}`,
   cursor position).
5. **Bulk actions** from any selection: tag, move, merge, export, delete,
   make a map, add to board.
6. **Export** any selection as Markdown folder, one document, PDF (print
   CSS), OPML for maps, PNG for boards.
7. **Import** Markdown folders with wiki-links preserved, Notion zips,
   Evernote enex, Apple Notes HTML.
8. **Keyboard everything** (§1.6) and a **shortcut sheet** on `?`.
9. **Word count, reading time, outline** for every document (exists for
   documents; extend to notes).
10. **A real trash** with restore and 30-day purge (exists as bin; make it
    consistent for every kind).

**State 2026-09-24:** all ten built; the item-by-item read moved to HISTORY.md, "Moved from the plans, 2026-10-11 (rows agent)". Still not checked: whether the Library, Timeline and palette share the Notes box's query parser.

---

## 6. Measuring "professional" without telemetry

Every gate above is a number a script produces on the sandbox. The ones
worth a Dashboard-of-the-project (a Markdown table in `HANDOVER.md`,
updated per session):

| Metric | Script | Today | Target |
| --- | --- | --- | --- |
| Distinct control recipes on the busiest screen | `scratchpad/audit/recipes.js` | 22 (Chat) | ≤ 8 |
| Control heights per bar | `docks.js` | 1 to 4 | 1 |
| Chrome ratio at 390 | `audit/chrome.js` | 76% | < 35% |
| Paragraphs > 120 chars outside popovers | `audit/prose.js` | ~60 | 0 |
| Em-dashes in `frontend/` + `src/` | `test_no_em_dashes.py` | ~9,000 | 0 |
| Contrast failures, both themes | `contrast.js` | 0 after fix | 0 |
| Console errors across all tabs at 3 widths | `errors.js` | 0 | 0 |
| Tablists without arrow keys | `audit/keys.js` | 0 after fix | 0 |
| Idle requests per minute | `scratchpad/ui-sweeps/idle.js` | **2 on 2026-09-21**, the gate met (`/models/status` backs off to a two-minute ceiling while its answer does not change, `/reminders` once a minute; was 4, and 14 before that). Timer wakes in the same minute went 124 to 5, and idle CPU 6.06% of one core to 5.55%: INBOX 266 item 7 | ≤ 2 |
| First paint of Graph on 2k notes | `graph-fixture.js` | n/a (SVG) | < 300ms |
| Search p95 on 5k notes | `tests/test_search_perf.py` | 14.2 ms median at 3,000 notes, 4 statements, flat (8.4 at 200, 10.5 at 1,000), 2026-09-12 | < 200ms |
| Capture write cost | the same probe against `POST /entries` | 9.0 ms and 16 statements at 1,206 notes, identical at 56 and 406, 2026-09-12 | flat |
| Resurfacing read | `ai/resurface` | 6.7 ms at 800 notes after its index; 23.0 ms with no LIMIT and 58.7 ms with a LIMIT and no index | flat |
| Skill eval pass rate, 3B model | `pytest -m evals` | n/a | ≥ 80% |

**State 2026-09-24:** a reference table, not a work item. The rows still reading n/a (the graph's first paint on 2k notes, the 3B eval pass rate) are open under GRAPH_PLAN and section 9.

---

## 7. The small things (a checklist that sessions keep reopening)

Each of these has been reported by the owner at least once. They are cheap
and they are what "refined" means. A session that has an hour left should
take five of these.

- Icon and label centred in every button, chip and menu item (measure).
- Focus rings visible on every control in both themes.
- Hover states on every clickable thing; cursor pointer only on clickable
  things.
- Disabled looks disabled and says why on hover.
- Every list has an empty state with an action; every empty state uses the
  same recipe.
- Every destructive action confirms in the same dialog recipe and offers
  undo where possible.
- Every async action shows progress in the same place (the button itself
  for < 2s, the Running-now panel for longer).
- Toasts: one recipe, bottom centre on phone, bottom right on desktop,
  with an action where one applies.
- Dates: relative under 7 days, absolute after; one formatter.
- Numbers: tabular figures in tables and stats.
- Truncation: titles ellipsise, never clip; the full text in `title`.
- Scroll: only the content scrolls, never the page under a dock; sticky
  heads stick.
- Selection: text is selectable everywhere text is (no `user-select: none`
  on content, including mind map nodes).
- Keyboard: Escape always closes the innermost thing; Enter in a single
  field dialog submits it.
- Touch: 44px targets on phone, no hover-only affordances.
- Motion: 150ms ease-out for state, 250ms for layout, none under
  reduced-motion.
- Copy: sentence case, no em-dashes, no "Oops", no exclamation marks.
- Modals: one width scale (24, 32, 44rem), title + body + footer, footer
  actions right-aligned with the primary last.
- Forms: labels above fields, one column under 600, required marked,
  errors inline under the field.
- Links: underlined on hover only, accent colour, external ones marked.
- (Odysseus, fourth read 2026-10-10) 

**State 2026-09-24:** (d) a standing checklist, not a row: the sweeps in `scratchpad/ui-sweeps/` hold most of it, and nothing here is scheduled on its own.

---

## Audit, 2026-09-13 night (INBOX 209: "poke holes in this application")

**Moved whole to HISTORY.md, "Moved from the plans, 2026-09-24".** A1 to A7 and A9 are done (the first
A1 to A6 rows in the table were the pre-fix copies of the same findings).
State 2026-10-04: A8's '?' help on every tab's dock is built (HISTORY, "the
consistency contract's missing lints"); the other three A8 items were not
re-measured here.

## 8. Execution order for the coming week (Opus/Sonnet sessions)

### What is left, 2026-09-24 (INBOX 399: "what is left in the world class plan??")

Every row of this plan read against the code, HISTORY, OPEN.md and INBOX on
2026-09-24; each row below carries a "State 2026-09-24" line where it
stands. Ranked by impact: what a person meets daily, then what unblocks the
most, then the rest. Size in sessions (S half, M one, L two or more).
Mirrored in `agent-remaining/OPEN.md`, table B.

| # | Row | What is left | Size | Where |
| --- | --- | --- | --- | --- |
| 1 | ~~F3, §16~~ | ~~`semantic_search` reads and parses every vector per request~~ built 2026-09-24: scores against the engine's matrix; 5,000 notes 19 to 74 ms before, 1.0 to 1.2 ms after (`tests/test_semantic_search_matrix.py`) | done | HISTORY |
| 2 | ~~§12, Brief 15~~ | ~~S1, S2, S3, the rest of S5, S6, `/debug/health` paths~~ built 2026-09-24; ~~`tests/test_lan.py`, the switch and its Settings toggle~~ built 2026-09-26; ~~LAN mode over IPv6~~ built 2026-10-04 (`netbind.listening_socket`, one dual-stack socket; the `[::1]` launcher test skips where the machine has no IPv6) | done | HISTORY |
| 3 | ~~B2~~ | ~~durable jobs: a table, leases, resume after a kill, `/jobs/stream`~~ built 2026-10-04 for the pool's six kinds (`core/jobstore.py`, `tests/test_jobstore.py`); the other kinds and the panel on the stream built 2026-10-11 (Brief 9, briefs-1011); the folder import built 2026-10-17 | S | HISTORY; B2 |
| 4 | ~~D2, 261~~ | ~~the connections rail always visible on desktop, which is also where `GET /resurface/near` would show~~ built 2026-09-27 (`#notes-rail` at 1280 and wider, the sheet below, by decision); re-measured 2026-10-04 with `notesrail.js` on the showcase notebook, 30/30 light and 30/30 dark at 1440, 1280, 1024 and 390 | done | HISTORY; D2 |
| 5 | ~~I1, H1~~ | ~~the tension and answered-question passes~~ built 2026-10-04 (`facts._pair_passes`, `tests/test_night_pairs.py`); 2,000 notes, a first run 39 to 57 s with no model, 130 to 215 s with a fake judge (gate 5 min), card 39 to 84 ms; left: pass 2's kinds (dates, duplicates, entities) as derived facts | done | HISTORY |
| 6 | ~~§14.3, I6, H2~~ | ~~chunk vectors, then paragraph anchors, three signal bars per sentence and the side-by-side view~~ built 2026-10-04 (`chunk_vectors`, `search/chunks.py`, `tests/test_chunk_vectors.py`, `tests/test_evidence_spec.py`); seeded 1,000 notes, recall@5 0.01 to 0.42; left: "wrong" on a card as a correction (I7) | done | HISTORY |
| 7 | ~~I3, H2~~ | ~~the questions view, `GET /questions`, the Ask scope, the answered-by link~~ built 2026-10-04 (`ai/questions.py`, `routes_questions.py`, Notes, Questions; `tests/test_questions_spec.py`, 500 questions listed under 100 ms) | done | HISTORY |
| 8 | ~~Placed 2026-09-13~~ | ~~`/files/gallery`'s five callers onto `apiPagedList`, then its default to 200~~ built 2026-09-24 (`tests/test_gallery_paging.py`) | done | HISTORY |
| 9 | ~~§16~~ | ~~cache `similar_pairs` for link suggestions and tensions~~ built 2026-09-24: keyed by the matrix's version; 5,000 notes 322 to 104 ms a repeat request (`tests/test_similar_pairs_cache.py`) | done | HISTORY |
| 10 | ~~D5~~ | ~~typed properties on notes (documents have them)~~ built: the properties, the table under a note's title and note types with KG4 (2026-10-04); the five built-in kinds and the graph's Note type colour 2026-10-05 (`tests/test_note_kinds_d5.py`); left: the Library grouping notes by type (the graph colouring and a type's own colour: `tests/test_note_types_graph_d5.py`) | done | HISTORY |
| 11 | ~~§17~~ | ~~review queue, filing style, explain this note, most opened this month (S each); tidy proposals, charts from questions (M each); `.ics` export built 2026-09-26~~ built 2026-10-05 (`routes_vision.py`, `ask-chart.js`; `tests/test_vision_rows_row11.py`) | done | HISTORY |
| 12 | ~~D6~~ | ~~the calendar strip, the yesterday/tomorrow pair and the month popover~~ built 2026-10-04 (`timeline.js`, `note-cards.js`; HISTORY, "the consistency contract's missing lints") | done | HISTORY |
| 13 | ~~§1, D14~~ | ~~the lints not written: surface budget, one primary per modal, meta without border or hover, a menu item's rest background, every `data-action` in the palette~~ built 2026-10-04 (`tests/test_consistency_contract.py`); left: the two ratchets (5 modals with 2 to 3 filled buttons, 13 chip rules) | done | HISTORY |
| 14 | ~~A8~~ | ~~the '?' help on every tab's dock (Chat and Graph have it)~~ built 2026-10-04: Dashboard and Reminders were the two docks without one (`tests/test_dock_help_507.py` fails on a dock with none) | done | HISTORY |
| 15 | ~~§1.3~~ | ~~Remind me on documents and boards (the reminder must point at other kinds first), Show in graph for a document, the Library note card's Remind me and Link to~~ built 2026-10-05 (`Reminder.document_id`, `target_kind`; `tests/test_reminder_targets_row15.py`) | done | HISTORY |
| 16 | ~~B7~~ | ~~cursor pagination, ETags and `If-Match` on entries, `/capabilities`~~ built 2026-10-05 (`api/paging.py`, `routes_capabilities.py`, `tests/test_api_contract_b7.py`); left: the page's own lists following the cursor on scroll, and the page reading `/capabilities` to hide what is not installed | done | HISTORY |
| 17 | ~~B8, H4~~ | ~~a user skills folder picked up without a restart; `/api/v1`; the agent named on an external write~~ built 2026-10-05 (`ai/skill_folder.py`, `api/versioning.py`, `events.as_agent`, `tests/test_local_service_h4.py`); left: the MCP server running the same tool tests as the in-app agent, and confirm cards for an outside agent's destructive call | done | HISTORY |
| 18 | ~~B4~~ | ~~typed links, a derived tensions table, rebuild determinism, the Tensions widget~~ built 2026-10-05 (`tensions` table rebuilt from events, night facts and links, `tests/test_tensions_table_b4.py`; typed links were KG3); left: derived person and project pages, per-claim citations, "what changed about X" | done | HISTORY |
| 19 | B5, §9 | ~~per-tool pre and post conditions, grammar-forced JSON, concurrent tool calls, Ollama's native dialect~~ built 2026-10-05 (`ai/tools/contracts.py`, `OllamaClient.forced_call_format`, `tests/test_tool_contracts.py`, `tests/test_provider_sockets.py` over a real socket); left: evals at 3B and 4B on a real model, and a real Ollama | M | HISTORY; `tests/test_skills_evals.py` |
| 20 | ~~I7~~ | ~~the "Learned from you" line with a filing accuracy number~~ built 2026-10-05 (`learning.filing_accuracy`, `GET /learned/summary`, `tests/test_learned_accuracy.py`); 24 notes, 5 moved: 67% to 92% | done | HISTORY |
| 21 | ~~I8, H3~~ | ~~the model bench~~ built 2026-10-05: `ai/bench.py`, `/models/bench`, Settings, Models, Test my models (`tests/test_bench_spec.py`); left: a run against a real model for the 30-minute and rerun gates | done | HISTORY |
| 22 | ~~I2, H8~~ | ~~the margin reader~~ built 2026-10-05 for documents: `ai/margin.py`, `POST /editor/read`, `margin-reader.js` (`tests/test_margin_reader_spec.py`); left: the note editor, typing latency in Chromium | S | HISTORY; I2 |
| 23 | ~~I5, H8~~ | ~~time travel: `as_of` on chat, then-and-now~~ built 2026-10-05 (`ai/timetravel.py`; 200 candidates rewound in under a second); left: a model's judgement over the pairs, past texts re-embedded, cards grouped by month | done | HISTORY |
| 24 | ~~D9~~ | ~~the web clipper~~ built 2026-10-05: `POST /links/clip-page` from the browser, the Clip to Tessellate bookmark and `clip.html` (`tests/test_webclip_page.py`) | done | HISTORY |
| 25 | H6, §5.7 | ~~Notion, Obsidian, Evernote and Apple Notes import; keyboard-complete; a WCAG audit; a first-run path timed to a first answer~~ built 2026-10-05 (HISTORY); left: multi-window | M | H6 |
| 26 | ~~H7~~ | ~~boot JS under 1 MB~~ built (691,724 bytes as served, `tests/test_boot_budget.py` gates it; the corrected 2026-10-05 measure, H7); every list over 200 rows measured 2026-10-05 (chunk-on-scroll, scroll p95 under 25 ms, `ui-sweeps/s2-1005.js` MODE=rows); first paint measured 2026-10-05 (`boottime.js`, fresh data dir, 1440, five cold loads, load average 10 on four cores): DOMContentLoaded median 585 ms, first contentful paint median 272 ms, dashboard panel readable (text in it, splash gone) median 974 ms (920 to 1,326); not optimised; left: the 300 ms line on the reference laptop with a quiet machine, and the 974 ms to the dashboard's text | S | `boottime.js` |
| 27 | ~~H9~~ | ~~usage ledger, time to first answer, simple mode, a perf budget in CI, an axe sweep, a global capture hotkey, fault injection in `errors.js`, speculative retrieval~~ built 2026-10-05 (HISTORY); left: `boottime.js` in the CI workflow | S | HISTORY |
| 28 | §19 | torch still loads at launch for a notebook with notes (a preference, or ONNX); the Phosphor subset; lazy stylesheets; ~~the whole `EXPLAIN QUERY PLAN` pass; queue back-pressure~~ built 2026-10-05 (HISTORY, "Moved from the plans, 2026-10-05 (19.3, 19.5)"); the Windows frozen startup | S to M | `ai/embeddings.py`, `index.html` |
| 29 | §10 | F1 a `prefs` module, F5 `api.stream`/`api.upload` and the no-bare-fetch lint, F7's threads onto the pool (the ratchet is built), F10 a `readings` table, F12 a store (F4 built 2026-09-26) | S to L | §10 |
| 30 | ~~§5~~ | ~~notes' unlinked mentions, word count and reading time; `{{clipboard}}` and a cursor mark; move to a space and export from a selection; the bin for documents and reminders~~ built: unlinked mentions with KG1 (2026-10-04); the rest 2026-10-05 (`tests/test_selection_actions_row30.py`, `tests/test_bin_documents_reminders_row30.py`) | done | HISTORY |
| 31 | ~~Placed 2026-09-09~~ | ~~1 capture into the selected space and a bulk move; 99 (b) scroll restore, (c) the AI dot's latency tooltip, (d) Paste as note; 92's row redesign; 97 RapidOCR; 79 and 22 to 23 not re-checked; 261's vault re-key (`POST /auth/rotate-vault-key`) has no UI~~ built or found built 2026-10-05 (`tests/test_placed_0909_row31.py`, `scratchpad/ui-sweeps/nbf1005-recheck.js`); 97 decided not to build (a new Python dependency) | done | HISTORY |
| 32 | 301 | the navigation and undo audit table, then the fixes | M | every surface |
| 33 | ~~§21~~ | ~~rows 1 and 2 on the notice recipe, row 12's "check the address" in the status line, row 13's update size in the About page~~ built 2026-10-05 (`tests/test_failure_ways_out_row33.py`) | done | HISTORY |
| 34 | ~~D1, D8, §13~~ | ~~drag on the grid; the reminder row recipe and a 10m snooze; the minimap's NaN rects, the tab bar at 600 to 819px, a whiteboard menu sweep, the tidy layout past five nodes (all not re-checked)~~ built or measured 2026-10-05: drag on the grid found built, the 10m snooze built, the rest measured clean (`nbf1005-recheck.js`); left with its owner: the whiteboard menu sweep (WHITEBOARD_PLAN) | done | HISTORY |
| 35 | §2 | the offline studio (the privacy receipt, its record, API and Settings page, built 2026-09-26) | L | new |
| 36 | B6, H5 | sync without a server | L | design first |
| 37 | Audio | deferred until the owner says go | L | the audio section |
| 38 | §20 | three open questions, each the owner's decision | none | §20 |

The 2026-09-08 week table that stood here is superseded by the list above
(its rows are either built or carried into it) and moved to HISTORY.md, "Moved from the plans, 2026-09-24".

---

## 9. On testing with a real model in the sandbox

The dev-only runner was built 2026-09-20; its record moved to HISTORY.md, "Moved from the plans, 2026-09-24".

**What is still open here.** The evals themselves: `tests/test_skills_evals.py`
holds the AGENT_SKILLS_REFORM acceptance gate and is the only eval module so
far. Everything else CLAUDE.md section 4 lists as unproven (concurrent tool
calls at index 1 and beyond, Ollama's native tool-call dialect) is still
unproven, and each wants its own eval beside that one.

**State 2026-09-24:** (b) the runner and one eval module exist; open is breadth: the same gate at 3B and 4B, and an eval each for concurrent tool calls at index 1 and beyond and for Ollama's native tool-call dialect. M.

---

## 10. Flaws found by static probes (cheap to reproduce, each with its command)

Run from the repo root. Each line is a class of bug, not a single bug; the
count is the size of the class today. A session that takes one of these
should fix the class and add the lint that keeps it fixed.

| # | Flaw | Evidence | Why it matters | Fix (and lint) |
| --- | --- | --- | --- | --- |
| F1 | 57 distinct `localStorage` keys read ad hoc, 14 of them `JSON.parse`d | `grep -o 'localStorage.getItem("[^"]*")' frontend/js/*.js \| sort -u \| wc -l` | This is the shape of the worst UI bug in the project's history (two settings missing from `APPEARANCE_DEFAULTS` wrote `NaN` into CSS): a value invalid where it is used, set somewhere else. Corrupt or missing storage throws inside JSON.parse and takes the caller's whole init with it. | One `prefs` module: a schema with defaults and a version per key, `prefs.get(key)` never throws and never returns undefined, migration on version bump. Lint: no direct `localStorage.getItem` outside `prefs.js`. |
| F2 | 25 list endpoints, 3 accept `limit` | `grep -n "^def list_" -A 6 src/memorymap/api/routes_*.py \| grep -c limit` | Every list is O(notebook). A 5k-note notebook makes the Library, Timeline and Graph tabs multi-second. (MODERNISATION_AUDIT D4.) | Cursor pagination on all 25 with one helper, `?limit=&cursor=`, `next_cursor` in the body; the frontend's list renderers page on scroll. Lint: a test enumerates routers and asserts every `list_*` takes `limit`. |
| F4 | **Re-measured 2026-09-13: 147 broad handlers, of which 52 say nothing at all.** `scratchpad/probe_excepts.py` reports both numbers, because the grep below counts every handler and the ones that cost something are the silent subset: a handler that logs with `exc_info` is the fix, not the flaw. Original figure: 88 `except Exception:` / bare `except:` in `src/` | `grep -rn "except Exception:\|except:" src/memorymap --include=*.py \| wc -l` | Failures become silence (the "features that never ran once" shape). | Each one either re-raises as the error contract, logs with `exc_info` to the logbuffer, or is narrowed. Lint: ruff `BLE001` enabled with a per-site `# noqa: BLE001 <reason>`. |
| F5 | 13 raw `fetch()` calls beside `api()` | `grep -n 'fetch(\`\|fetch("' frontend/js/*.js \| grep -v "api\b"` | Each re-implements the auth header, the error contract and the offline path; one is `/chat/stream`, the most important call in the app. | `api.stream()` and `api.upload()` helpers; the 13 sites move onto them. Lint: no bare `fetch(` outside `api.js`. |
| F7 | Threads in 16 modules share SQLAlchemy sessions created per call | `grep -rln "threading.Thread" src/tessellate` | SQLite is fine with this only while each thread opens its own session and nobody passes ORM objects across; nothing enforces it, and the "Could not refresh instance" 500 seen this session was exactly that shape. | B2 job runtime: one worker, jobs get a fresh session, results are plain dicts. Lint: `Thread(` allowed only in `core/jobs.py`. |
| F10 | Extracted text, captions and OCR live in three columns with three UIs | `grep -n "vision_ocr_text\|ocr_text\|caption" src/tessellate/api/routes_files.py \| wc -l` | The Files card shows one, hides one, and the search indexes some; the owner's "only the first line" report was one symptom. | One `readings` table (`media_id, kind, page, text, model, ts`), one renderer, all kinds indexed (B3). |
| F11 | The graph, dashboard constellation and map thumbnails are three renderers | `grep -c "forceSimulation" frontend/js/graph.js frontend/js/dashboard.js frontend/js/whiteboard.js` | Three physics, three colour maps, three sets of bugs. | GRAPH_PLAN §3: one renderer with `size: "pane" | "tile" | "full"`. |
| F12 | Frontend state lives in module globals, DOM and localStorage with no single owner | MODERNISATION_AUDIT C2 | Every "the list did not refresh" bug. | A small store: `state.get/set/subscribe` per slice, renderers subscribe; introduced slice by slice (notes list first). |

F3, F6, F8 and F9 are done and moved to HISTORY.md, "Moved from the plans, 2026-09-24".

Two flaws this session found by driving the app, recorded here so they are
fixed as classes: a new board was created through a path that also created
a note (entries and boards share a table and a create path; the filter
belongs in one place), and a dialog's `<details>` did not close on Escape
(now handled globally; the lint is "every `details` menu closes on Escape",
in `docks.js`).

**State 2026-09-24:** the rows left:

- F1 built 2026-10-05: `prefs.js`, every read through it but the three scripts that run before it (HISTORY.md, "Moved from the plans, 2026-10-05 (F1, F5, F12)"). Left: the writes (`localStorage.setItem`) through `prefs.set`.
- F2 (b) every list takes `limit` (`tests/test_list_limits.py`); cursors on
  every paged list built 2026-10-05 (row 16), and the notes list follows
  them. Left: the other lists' renderers paging on scroll by cursor. M.
- F4 built 2026-09-26: BLE001 is enabled (HISTORY.md, "Moved from the
  plans, 2026-09-26").
- F5 built 2026-10-05: `api.upload`, `api.stream`, the lint (HISTORY.md, "Moved from the plans, 2026-10-05 (F1, F5, F12)").
- F7 (b) the pool is built (A3); a ratchet holds the thread sites
  (`tests/test_flaw_class_lints.py`). 2026-10-05: the re-index (a `batch`
  lane of its own) and the model capability probe moved onto the pool, the
  ratchet lowered by two (HISTORY.md, "Moved from the plans, 2026-10-05
  (F7, F10)"). Left: the model downloads, the embedding warm-up (kept apart on
  purpose, see its comment), the scheduler, the searxng and update threads. M.
- F10 built 2026-10-05 as a view: `readings`, `GET /files/readings`, every kind indexed (HISTORY.md, "Moved from the plans, 2026-10-05 (F7, F10)"). Left: one renderer in the Files card reading the route.
- F11 (d) GRAPH_PLAN section 3 owns it.
- F12 (b) 2026-10-05: `store.js` and its first slice, `notes` (HISTORY.md, "Moved from the plans, 2026-10-05 (F1, F5, F12)"). Left: the next slices (reminders, the current note), each surface subscribing in place of its own copy. L.

---

## 11. The week, session by session (Opus/Sonnet), and the quarter

Superseded twice: by section 18's order (2026-09-14) and by the open list
at the top of section 8 (2026-09-24). The day-by-day table, the quarter and
the Fable hand-off list moved to HISTORY.md, "Moved from the plans, 2026-09-24"; everything in them that is
still open is a row of that list.

---

## 12. Security review (read, not penetration-tested; each item names the file)

The threat model matters: the app binds 127.0.0.1 by default, so most of
these are "fine on localhost, real the day LAN mode ships". They are
listed so LAN mode cannot ship without them (Brief 15).

S1 to S15 are fixed, tested or recorded, and moved to HISTORY.md, "Moved
from the plans, 2026-09-24": S1 (the media cookie), S2 (the per-client
throttle), S3 (imports confined to home and the data folder), the rest of S5
(the fetch lint sees every way out) and S6's redirect half were built that
day. S6's other half, the configured model address on the privacy receipt,
was built 2026-09-26 with the receipt's API (HISTORY.md, "Moved from the
plans, 2026-09-26"). What is left is the rest of Brief 15 below.

**Brief 15 is built** (2026-09-24 and 2026-09-26, HISTORY.md): the
hardening, `tests/test_lan.py` against the real launcher on 0.0.0.0,
and the switch in Settings, Account and security. IPv6 built 2026-10-04
(HISTORY.md, "row 2: LAN mode over IPv6"). Nothing is left of Brief 15.

**Security audit, 2026-10-05:** SEC-01 to SEC-09, SEC-11 to SEC-13, SEC-15
and SEC-16 fixed (HISTORY.md, "Security audit fixes, 2026-10-05"); SEC-08's
real fix, LAN mode over HTTPS with a certificate made on this computer, the
same day, and SEC-10, a folder import safe to run again, and SEC-14, answers that quoted a note
redacted when it goes private (HISTORY.md, "Security audit, second pass").
SEC-17, a floor of 8 for new passwords and a warning above it, the same
day, and SEC-02's last step (a tainted turn opens without a card only a
page its search returned or a site the person named). Nothing from the
audit is open.

**Decisions made** (the owner, 2026-10-05; do not remake):

1. **Auto-update: "Ask once".** The first launch asks once, in the terminal
   (start.sh, when there is a terminal to answer in) or in the app, whether
   to check for updates automatically, and remembers the answer
   (`update_choice_made`). Until it is answered nothing about updating
   touches the network: the launchers neither pull nor reach the remote, the
   doctor included. Settings, About keeps the switches and a "Check for
   updates" button, which checks once whatever the switch says. The packaged
   app asks in the app; there, yes means "tell me", and installing stays
   behind its own switch.
2. **LAN HTTPS: "Yes, self-signed HTTPS".** On the first LAN start the app
   makes a self-signed certificate with `cryptography` (no network), kept in
   the data folder at 0600, and serves HTTPS on the network; loopback stays
   HTTP. Settings, LAN shows the certificate's fingerprint, so a phone user
   can check the one-time warning, with "Regenerate certificate". The help
   says the traffic is encrypted and explains the warning.
- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 
- (Odysseus, fourth read 2026-10-10) 

## 13. Open bugs and gaps from the merged agent reports (with owners)

Each of these was found by measuring and deferred with evidence; the
`agent-remaining/*.md` file named carries the file, id and next step.

- Whiteboard board-preview minimap NaN rects: not reproduced 2026-10-05 (six
  boards, 0 errors at 1440 and 390, `errors.js`); see worldclass-1005c.md.
- 1024px still wraps the Writing Room controls and the capture attachment
  row. Owner: consistency.md.
- Tab bar scrolls between 600 and 819px; short tab captions below 480 are
  a copy decision for the owner. Owner: responsive.md.
- Notes (8) and Graph (9) docks are over the seven-control ceiling. Owner:
  docks.md; the fix is a second "more" group, not hiding.
- ~~`#wb-topbar` is 104px at 390.~~ One row, 54px, since 2026-10-11 (WHITEBOARD_PLAN decision 39).
- ~~The whiteboard's five menus were restyled but never driven.~~ Driven:
  `kebab-viewport.js` opens all five at three window sizes (15 cases OK) and
  `wbtopbar.js` gates their keyboard and ARIA (WHITEBOARD_PLAN 43; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)").
- The SVG graph path stays behind a flag until the drag gate is met on a
  quieter machine. Owner: GRAPH_PLAN Phase 2.
- Timeline: everything (audited, not built). Owner: Brief 5.
- 54 paragraphs still outside popovers. Owner: Brief 4.
- `#library-media-refresh` is misnamed; Settings has two heading indents.
  Owner: docks.md.
- Tidy layout never measured past five nodes; a newly opened map leaves
  its root under the top bar. Owner: mindmap.md item H.

**State 2026-10-05:** measured (`scratchpad/ui-sweeps/nbf1005-recheck.js`): a board's preview draws its blocks with no NaN rect and no console error (the renderer was replaced, `mapPreview` in note-cards.js); the tab bar fits at 600, 640, 700, 760 and 819px (scrollWidth equals clientWidth); the tidy layout is measured past five nodes (maplayouts.js at 12 and 200 topics, 0 overlapping pairs, HISTORY.md). Still open with their owners: the whiteboard's menus driven by a sweep (the whiteboard agent), the SVG graph flag (GRAPH_PLAN Phase 2), a new map's root under the top bar (WHITEBOARD_PLAN 7).

**State 2026-09-24:** re-read against OPEN.md and the code: the
Notes and Graph docks are at 6 controls (OPEN.md B, 2026-09-20);
`#library-media-refresh` no longer exists; the Timeline was built
(TIMELINE_PLAN); the Writing Room was rebuilt as the writing desk (D16, in
HISTORY); the 54 paragraphs were Brief 4's. Not re-checked here, so still open
with their owners: the board-preview minimap's NaN rects, the tab bar between
600 and 819px, the whiteboard's five menus driven by a sweep, the SVG graph
flag (GRAPH_PLAN Phase 2), the tidy layout past five nodes (MINDMAP_PLAN).

## 14. The core algorithms, read line by line (2026-09-08)

The owner asked whether the core algorithms are the best they can be, and
what would revolutionise the app decisively. Read, not assumed:
`search_manager.py`, `embeddings.py`, `janitor.categorise`, `intent.py`,
`grounding.py`, `_ensure_fts5`.

### What is already good

- Keyword search is FTS5 with `bm25()`, tag boost, prefix fallback,
  vocabulary-based spelling correction, then an OR fallback. Sound.
- Semantic search is brute-force cosine with a z-score relative floor,
  scored on `(id, vector)` tuples, fine to about 50k notes.
- Fusion is reciprocal rank fusion, then a two-hop graph expansion.
- Filing asks the model first, falls back to the embedding centroid, and
  logs the method. Every decision is explainable.

### What was wrong, and is fixed this session

Both fixes (stemming, and grounding from touched notes) moved to HISTORY.md, "Moved from the plans, 2026-09-24".

### The moves that would outshine everything else, in order of leverage

1. **A learning loop that never leaves the machine.** Every correction the
   owner makes is a training signal nobody uses: a re-filed note, a
   dismissed link suggestion, a result opened after a question, an
   accepted "related" chip. Store each as an event (B1), and let three
   algorithms read them: filing gets the nearest already-filed notes and
   the owner's past corrections as evidence in the prompt (k-NN
   few-shot from the notebook itself, which is the single biggest
   accuracy lever for a small model); search gets a per-note boost from
   what was opened after similar questions, with decay; link suggestions
   never resurface a dismissed pair and raise the prior of an accepted
   neighbourhood. No competitor does this offline. Size M; spec tests
   first (`tests/test_learning_spec.py`, strict xfail).
2. **Index everything** (B3). Documents, files' extracted text, board
   nodes and bookmarks are not in FTS5 or the vector table, so Ask cannot
   see them unless attached by hand. This is the largest capability hole
   in the app and is already specified; it goes first among the backend
   moves.
3. **Chunked vectors and sentence-level citations.** One vector per note
   loses long notes and every document. Embed paragraphs (one row per
   chunk, `entry_id, ordinal, vector`), retrieve chunks, and ground each
   answer sentence by cosine against chunks when an embedding backend is
   up, falling back to the lexical scorer. A citation then points at the
   paragraph, and the chip quotes it. Size M.
4. **Claims and tensions** (B4): the invention that no notebook has. It is
   expensive (a model idle loop) and depends on 1 to 3; keep it after them.

What is not worth doing: replacing RRF, replacing bm25, or an approximate
nearest-neighbour index below 50k notes. The measured costs are elsewhere.

**State 2026-09-24:** 1 is (b): the loop is built for
filing (`ai/learning.py`, corrections in `AuditLog`) and search
(`open_after_ask`); dismissed link pairs and accepted neighbourhoods were not
traced. 2 is built (B3). 3 is built 2026-10-04 (row 6; HISTORY, "row 6: paragraph vectors and evidence cards").
4 is B4, (b).

## 15. Inventions: eight things no notebook does, specified for Opus and Sonnet

Written 2026-09-08 by direct instruction ("invent world class features
... something the likes of which the world hasn't seen yet"). Each one is
specified to the level a session can build from without a design pass:
what the person sees, why it is new, what already exists to build on
(checked in the code, file named), the data, the endpoints, the algorithm,
the tests written first, the gate, the size and the model. Dependencies are
explicit; the order at the end respects them.

### The asymmetry these exploit

Every cloud notebook rations model calls, because each call costs money.
Tessellate's model is local, idle 99% of the time, and free per token. That
is the one thing a cloud product cannot copy: **the notebook can spend
hours of model time on itself while nobody is watching**, and show its
work in the morning. Inventions 1, 3, 5 and 8 are built on that. The
second asymmetry is that the corpus is one person's own thinking, not the
web: contradictions, repeated ideas, unanswered questions and forgotten
notes are *signal* here, where in a search engine they are noise.
Inventions 2, 4 and 6 are built on that. Invention 7 is the loop that makes
the other seven get better with use.

### I1 The night shift: the notebook that understands itself while you sleep

**What the person sees.** A "While you were away" card on the Dashboard
each morning: "Read 14 new notes. Found 3 claims that disagree with older
ones, 2 questions you answered without noticing, 6 dates, 4 people. 2
notes look like duplicates." Each line opens a review list where every
item is accept / dismiss / open the note, and each item shows *which note
and which sentence* it came from and *which model, when* decided it. Off
by default, one switch in Settings > Background tasks, with a token budget
per night and a battery guard.

**Why it is new.** Notion AI, Mem and Reflect do a summary on demand.
Nobody runs a standing, budgeted, auditable analysis of the whole
notebook on the owner's own machine, with provenance on every derived
fact, that the owner can reject line by line and that learns from the
rejections (I7).

**Builds on.** `ai/autonomous.py` (the scheduler: interval, battery guard,
snooze, a barred-destructive-tools agent pass; start() wired in app
lifespan), `ai/entities.py` (`extract_entities_pass`, `Entity`,
`EntityMention`), the tensions pipeline in `api/routes_entries.py`
(`TENSION_CANDIDATE_THRESHOLD`, `accept_tension`, dismissed set in a
preference), `EntryDate` and `reminder_parser.py` (dates), the near
duplicate check on save, `entry_revisions` (so "new since last run" is a
revision cursor, not a timestamp guess).

**Data.** One new table `derived_facts` (id, kind in {claim, question,
duplicate, tension, entity, date}, entry_id, revision_id, span_start,
span_end, text, payload JSON, confidence 0 to 1, model, computed_at,
status in {new, accepted, dismissed}, run_id). One `night_runs` table
(id, started_at, finished_at, cursor_revision_id, tokens_spent, budget,
counts JSON, stopped_reason). Every existing derived thing (entity
mention, tension) gets a `run_id` column so the morning card can group by
run. Nothing is written to a note. Ever.

**Endpoints.** `GET /night/latest` (the card), `GET /night/runs/{id}/facts?
kind=&status=` (the review list, paged), `POST /night/facts/{id}` (status
accept or dismiss; accept of a `tension` calls the existing accept path;
accept of a `date` creates the reminder through the existing reminder
route; accept of a `duplicate` opens the existing merge), `POST /night/run`
(manual, for testing and for "run now").

**Algorithm.** A run is a plan of passes with a shared budget: (1) cursor:
revisions since the last run; (2) cheap passes first, no model: dates
(`reminder_parser`), duplicates (embedding cosine over new notes against
all, threshold from the save-time check), entities (regex plus the
existing pass); (3) model passes, each note once, one prompt per note that
returns a JSON list of claims and open questions (the schema is in the
prompt, the parser rejects anything else); (4) tensions: for each new claim,
top-k similar claims by cosine, then one model call per pair above the
threshold asking "compatible / incompatible / unrelated" with a one-line
reason; (5) answered questions: for each open question, top-k similar
claims written *later*; one model call asks "does this answer it". Stop
when the budget is spent; record where; resume from the cursor next night.
Small-model mode: passes 3 to 5 use the small prompt variants
(`AGENT_SKILLS_REFORM` Phase B), one item per call.

**Tests first** (`tests/test_night_shift_spec.py`, strict xfail until each
passes): a run over the fixture notebook with the fake model produces the
expected counts per kind; every fact cites an entry, a revision and a
span inside it; a second run with no new revisions produces zero facts
and spends zero tokens; a budget of N stops the run with
`stopped_reason=budget` and a cursor before the unprocessed notes;
dismissing a fact hides it from `/night/latest` and writes a
`corrections` event (I7); a run is skipped on battery; nothing in
`entries` changes (row hash before and after).

**Gate.** On the 2,000-note fixture, a full first run under the fake model
finishes in under 5 minutes wall clock and the card renders under 100ms
from `/night/latest`. **Size** L (two sessions). **Model** Opus for the
runner and prompts, Sonnet for the review UI on the modal and list
recipes.

**State 2026-10-04:** passes 1, 3, 4 and 5, `night_runs`, `GET /night/latest` and the morning card are built (HISTORY, "row 5: tensions and answered questions"). Left: pass 2's cheap kinds (dates, duplicates, entities) as `derived_facts` rows, with the accept of a date (a reminder) and of a duplicate (the merge). H1 below is the same row.

### I2 The margin reader: a second reader in the editor, from your own notes

Built 2026-10-05 for documents: the spec and its record moved to HISTORY.md, "Moved from the plans, 2026-10-05 (the margin reader)". Left: the same column in the note editor; typing latency measured in Chromium.

### I3 Open questions: the notebook keeps a list of what you have not answered

Built 2026-10-04 (row 7): moved to HISTORY.md, "Moved from the plans, 2026-10-04 (row 7: open questions)", with the answered-by link's decision. Nothing is left here: the night pass retrying an open question as notes arrive is pass 5 (row 5).

### I4 Resurfacing: the ideas you are about to forget, when they matter

**Built 2026-09-12; the record and the spec moved to HISTORY.md, "Moved from the plans, 2026-09-24".** State
2026-09-24: the one part left is the margin row in the note editor, which
is I2's surface and waits for I2.

### I5 Time travel over meaning: what did I think about X in March?

**What the person sees.** A date control on Ask ("as of…") and a
"Then and now" panel on any note: the note as it was on that date, and a
two-column diff of the *claims* (not the text) between then and now: "Then:
the batch size should stay at 32. Now: 64 after the memory fix." Ask with
a date answers from the notebook as it stood then, citing the revision.

**Why it is new.** Version history exists everywhere. Answering a question
*from the notebook as it was*, and diffing what you believed rather than
what you typed, does not exist anywhere.

**Builds on.** `entry_revisions` (already written before every change,
quiet-period coalesced), I1's claims with `revision_id`, the Ask box, the
grounding scorer (it grounds against revision text the same way).

**Data.** No new table. Claims already carry `revision_id`; `GET
/entries/{id}/claims?as_of=` resolves the revision at that date.

**Endpoints.** `POST /chat/stream` gains `as_of: date | null`; retrieval
runs over revision text at that date (FTS5 over a temporary table of
as-of contents for the candidate set, vectors re-embedded on demand and
cached by revision id); `GET /entries/{id}/then-and-now?as_of=` returns
`{then: [claims], now: [claims], changed: [(then_id, now_id, kind)]}`
where kind is `revised | dropped | new`, from claim cosine plus the fake
or real model's judgement.

**Tests first** (`tests/test_time_travel_spec.py`): a note edited on
three dates answers a question differently as of each date, citing the
right revision; the then-and-now diff on the fixture reports one revised,
one dropped, one new; an `as_of` before the notebook existed returns an
empty, honest answer rather than today's.

**Gate.** As-of retrieval under 1s at 5k notes for a 200-candidate set.
**Size** M. **Model** Opus.

**State 2026-10-05:** (b) built (row 23): `as_of` on `/chat/stream`, `GET` and `POST /entries/{id}/then-and-now`, the clock on Ask and Then and now in a note's History (`ai/timetravel.py`, `tests/test_time_travel_spec.py`): HISTORY.md, "Moved from the plans, 2026-10-05 (row 23: time travel)". Not built: the model's judgement over the claim pairs (the pairing is by shared words), re-embedding past texts (as-of retrieval ranks then-texts by words), `GET /entries/{id}/claims?as_of=` (claims carry no `revision_id`), and the answer's cards grouped by month (H8).

### I6 Evidence cards: answers you can audit sentence by sentence

Built 2026-10-04 (row 6): moved to HISTORY.md, "Moved from the plans, 2026-10-04 (row 6: paragraph vectors and evidence cards)". Left: "wrong" on a card as a correction (I7, H2's second half).

### I7 The corrections loop: every "no" makes the notebook better

**What the person sees.** Nothing new to do. Re-file a note, dismiss a
suggestion, mark a tension wrong, pick a different search result, say
"never again" to a card: the app records it and changes its behaviour.
Settings shows a small "Learned from you" panel: "37 corrections. Filing
accuracy 71% to 89% over the last 200 notes. Reset."

**Why it is new.** Offline apps do not learn; online apps learn on the
server from everyone. A per-person model that lives in the SQLite file,
is inspectable, resettable and explains itself is not something anyone
ships.

**Builds on.** `AuditLog` (re-file events already logged as
"recategorised -> X"), the dismissed sets kept as preferences, `janitor.
categorise` (the prompt), `search_manager._rank` (the fusion), the link
suggestion route.

**Data.** `corrections` (id, kind in {refile, dismiss_link, accept_link,
dismiss_tension, dismiss_resurface, open_after_ask, dismiss_fact}, subject
JSON, from_value, to_value, at). `learned_boosts` (kind, key, weight,
updated_at), rebuilt from `corrections` on demand (derived, so Reset is a
delete).

**Algorithm.** Filing: the prompt gets the three nearest already-filed
notes with their categories *and* the last three refile corrections whose
from_value matches the model's likely answer ("you moved notes like this
from Work to Projects twice"); the centroid fallback subtracts a category
the owner has refiled away from twice. Search: `open_after_ask` adds a
boost of 0.15 per open to that note for questions with cosine over 0.8 to
the asked question, decaying by half every 30 days, applied inside the
fusion as a fourth ranked list. Links and tensions: a dismissed pair
never returns; an accepted pair raises the threshold weight of its
two categories by a small constant. All weights bounded; all shown in the
panel.

**Tests first** (`tests/test_learning_spec.py`): a refile is recorded and
appears in the next filing prompt for a similar note; after two refiles
away from a category the centroid path no longer chooses it; an
`open_after_ask` reorders the next similar question's results; a
dismissed link pair is absent from `/entries/link-suggestions`; Reset
empties `learned_boosts` and behaviour returns to baseline; the panel's
accuracy number equals the fixture's computed value.

**Gate.** Filing accuracy on the eval fixture with 20 synthetic
corrections improves by at least 10 points; search p95 unchanged. **Size**
M. **Model** Opus for the prompt and fusion changes, Sonnet for the panel.

**State 2026-09-24:** (b) the loop is built (`ai/learning.py`: corrections as `AuditLog` rows by decision, boosts with decay, the centroid exclusion, `open_after_ask`). Corrected 2026-10-05 (audit ARCH-08): the centroid exclusion had no caller and the corrections query could not see the re-files `update_entry` records; both are wired now (`janitor._semantic_category`, `tests/test_save_cost_flat.py`); the "Learned from you" line with a filing accuracy number is not in Settings. S.

**State 2026-10-05:** (b) the loop's store is built (`ai/learning.py`: corrections as `AuditLog` rows by decision, boosts with decay, `open_after_ask`), and its centroid consumer is wired (`learning.excluded_categories`, called by `janitor._semantic_category`; audit ARCH-08, fixed 2026-10-05, and a refile made in the app reaches it since row 20 fixed `corrections(kind="refile")`); and its evidence half is wired too (`librarian.evidence_note` in `filing_prompt`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)", I7). The "Learned from you" line with a filing accuracy number is in Settings (row 20): HISTORY.md, "Moved from the plans, 2026-10-05 (row 20)". Left: the gate's eval (filing accuracy with 20 synthetic corrections up 10 points) needs a real model, and "wrong" on an evidence card as a correction.

### I8 The model bench: which local model is best on *your* notebook

Built 2026-10-05: the spec and its record moved to HISTORY.md, "Moved from the plans, 2026-10-05 (the model bench)".

### I9 What the notebook learned: one place to see, edit, delete and switch it all off

**Built. Backend 2026-09-13 (HISTORY.md, "Built, I9's whole backend and the
first pass of I1"); the Settings section 2026-09-19 (HISTORY.md, "Built,
I9's Settings section").** What is still open here is the kinds I1's later
passes add (tensions, duplicates, entities, dates) and the "Learned: manage"
link (the bulk actions and `POST /learned/bulk` were built together on
2026-09-23, agent-remaining/OPEN.md's Backend section has the measurement) from each invention's own surface. The text
below is kept because it is the spec for those.

Added by direct instruction: "give the user the ability to see what the
notebook has learned and to be able to edit, delete and manage it so in
case the AI models get things wrong the user can fix it, also a way to
toggle the features on and off." This is not a ninth feature beside the
eight; it is the contract every one of them ships under. **No invention
above is built until its rows appear here.**

**What the person sees.** Settings > "What the notebook learned" (its
own section, next to Background tasks). At the top, one switch per
invention, each with a one-line description and a `?` popover: Night
shift (I1), Margin reader (I2), Open questions (I3), Resurfacing (I4),
Evidence checks (I6), Learning from corrections (I7), Model bench (I8).
Time travel (I5) has no switch; it only reads revisions. Off means: the
feature computes nothing, shows nothing, and its existing rows are kept
but inert (a banner in the section says "paused, N items kept"). A master
switch "Pause all learning" sets every one off in one click.

Below the switches, one table with a kind filter and a search box, every
row a fact the app derived rather than the person wrote: claims,
questions, tensions, duplicates, entity merges, dates, learned boosts
(I7), resurfacing decisions, filing corrections. Each row shows: the text,
the note and sentence it came from (click to open, scrolled to the span),
which model and when, the confidence, its status, and three actions:
**Edit** (the text, the entity name, the category, the weight: an edited
row is marked "edited by you" and is never overwritten by a later run),
**Delete** (gone, and recorded as a correction so the same fact is not
re-derived next run), **Reset to what the model said** (for an edited
row). Bulk: select all in the filter, delete or accept. At the bottom:
"Forget everything learned" (deletes every derived row and every boost,
keeps notes and revisions untouched, asks once), and "Export what the
notebook learned" (one JSON file, so the person can read it outside the
app).

Each invention's own surface (the morning card, a margin card, a question
row, a resurfacing card) carries a small "Learned: manage" link to this
section filtered to that kind, so a wrong fact can be fixed where it is
met, not only in Settings.

**Why it matters.** A model that is wrong quietly is worse than no model.
Every derived thing in this app is inspectable, attributable and
reversible, and the person can turn the model's judgement off entirely
and keep the notebook. That is the promise that lets the eight inventions
run unattended.

**Builds on.** `derived_facts` and `night_runs` (I1), `corrections` and
`learned_boosts` (I7), `note_scores` (I4), the preference store for the
switches, the Settings section recipe (D13), the list and modal recipes.

**Data.** `derived_facts` gains `edited_by_user: bool`, `original_text`,
`original_payload` (for Reset). `corrections` gains kind
`delete_fact`, `edit_fact`. Switches are preferences named
`learn.<invention>.enabled` (default off for I1, I2, I7, I8; on for I3,
I4, I6 once their upstream is on) plus `learn.paused` (master).

**Endpoints.** `GET /learned?kind=&q=&status=&page=` (the table, paged),
`PATCH /learned/{id}` (`{text | payload | status}`, sets `edited_by_user`),
`DELETE /learned/{id}` (writes the correction), `POST /learned/{id}/reset`,
`POST /learned/bulk` (`{ids, action}`), `DELETE /learned` (forget
everything; requires `{confirm: true}`), `GET /learned/export` (JSON),
`GET|PUT /learned/switches`.

**Rules the runners obey** (each a test): a runner checks its switch
before every pass and exits cleanly when off; a runner never overwrites a
row with `edited_by_user`; a deleted fact's `(entry_id, kind, text
hash)` is in `corrections` and the runner skips re-deriving it; `learn.
paused` stops every runner within one poll interval; the table never
shows a row from a note the person cannot open (private, binned).

**Tests first** (`tests/test_learned_spec.py`, strict xfail until built):
the section lists a fact from each kind with its source span; editing a
claim marks it and survives a re-run of the night shift over the same
note; deleting a fact writes a correction and the next run does not
re-create it; Reset restores the model's text; "Forget everything" leaves
`entries` and `entry_revisions` byte-identical and every derived table
empty; each switch off yields zero new rows from its runner and a 204 with
`{paused: true}` from its endpoints; the export round-trips (import is
not offered; the file is for reading); the master switch flips all seven
and the section shows "paused" on each.

**Gate.** The table renders 2,000 rows paged under 100ms per page; every
row's "open source" lands on the span (Playwright: the span's rect inside
the viewport); the section passes `test_dock_grammar.py`,
`test_style_scale.py` and the CSP lint. **Size** M. **Model** Opus for the
runner contract and endpoints, Sonnet for the table on the list recipe.

**Order.** I9's table and switches are built with I7 (the first invention
in the order below), so from the first learned boost onward there is a
place to see it; each later invention adds its kinds to the same table.

**State 2026-09-24:** (b) as the paragraph above says: the kinds I1's later passes add, and the "Learned: manage" link on each invention's surface.

### Order and dependencies

```
§14.2 chunk vectors  →  I6 evidence cards
B1 event log (or the corrections table alone)  →  I7 corrections loop
I1 night shift  →  I3 questions, I5 time travel (claims), I8 bench (budget)
I1 + §14.2      →  I2 margin reader
nothing         →  I4 resurfacing, I7 (with its own corrections table)
```

Start with I9's switches and table together with I7, then I4 (no
dependencies, both improve every existing feature), then §14.2 and I6,
then I1, then I3, I2, I5, I8. Each adds its rows to I9 as it lands. Each is one
brief row in SESSION_BRIEFS when its turn comes; none is built ad hoc.

### What was deliberately left out

Autocomplete and "write it for me": every competitor has it and it makes
the notebook sound like the model. Cloud sync of the derived tables: the
inventions work because the data never leaves. A plugin marketplace before
B8: an extension surface without the event log is a support burden with
no lever behind it.

## 16. The backend, read for structure, silent failure and lag (2026-09-08)

Static probes over `src/tessellate` (`scratchpad/probe_backend.py`), each
number reproducible. Security is in §12 and was not repeated; nothing new
was found there beyond what §12 lists.

**Complexity is concentrated, which is good news.** Four functions carry
most of it and are the only ones worth restructuring:

| Function | Lines | Branches |
| --- | --- | --- |
| `ai/agent.py run_agent` | 788 | 71 |
| `ai/skill_runner.py run_skill` | 493 | 48 |
| `api/routes_chat.py chat_stream` | 384 | 46 |
| `api/routes_graph.py graph` | 298 | 37 |

Move: `run_agent` into a `Turn` object with one method per round phase
(prompt, call, dispatch, feed back, finish), which is also what B5's
verifier needs to sit between "call" and "feed back"; `chat_stream` into
prepare, route, stream, ground, with `lines()` a generator over a small
state object. No behaviour change; the existing tests are the gate
(`test_agent_*`, `test_chat_*`, `test_agent_plan.py`). Size M, Opus,
after B5's spec tests exist so the split serves them.

**Silent failure.** 129 `except Exception` handlers, 18 of them `pass`
(`embeddings.py` 234, 254, 261, 444; `entities.py` 141;
`reminder_parser.py` 205; `tools/_common.py` 337; `vision_ocr.py` 320;
`routes_settings.py` 1515; `routes_spaces.py` 219; `atomic_io.py` 41;
`pdfpages.py` 186, 240; `security.py` 407; `taskhistory.py` 90;
`manager.py` 811; `searxng_install.py` 499, 560). Rule for the pass:
each becomes `logger.debug` with the exception, or a comment naming the
failure it swallows and why that is right. Sonnet, one session, one
commit per file, no behaviour change.

The embed-cache lock fixed 2026-09-08 moved to HISTORY.md, "Moved from the plans, 2026-09-24".

**Lag, measured by reading, to be measured by running.**

- `semantic_search` reading every vector per query: built 2026-09-24, moved
  to HISTORY.md, "Moved from the plans, 2026-09-24".
- `similar_pairs` computed per request for link suggestions and tensions:
  built 2026-09-24, moved to HISTORY.md, "Moved from the plans, 2026-09-24".
- The frontend runs nine `setInterval` polls; MODERNISATION_AUDIT measured
  14 idle requests a minute. Move: one `/events` SSE stream (B1's log is
  the natural source) and the polls become subscriptions. Size M, Opus.
- Five route files exceed 1,750 lines (`routes_files.py` at 2,998). Not a
  bug; a session cost. Split by resource when each is next touched, never
  as its own task.

**Consistency findings.** Route handlers are wired by decorator, so a
"defined once, never referenced" probe is noise for them; excluding
decorated functions leaves under ten candidates, all private helpers
behind a feature flag. Not worth a session.

**State 2026-09-24:** the split is done
(audit A5, in HISTORY); the silent `pass` handlers were narrowed (audit A6)
and the rule is F4 above; the lag items: `semantic_search` (F3) is built 2026-09-24;
`similar_pairs` for link suggestions and tensions is built 2026-09-24; the polls-to-SSE move is (d), superseded by F6's idle gate being met at 2
requests a minute; the route-file sizes are a standing rule, not a row.

**Corrected 2026-10-05 (audit ARCH-22, ARCH-10).** The split regressed:
`agent._dispatch_call` is 448 lines, `run_agent` 439,
`skill_runner._run_one_step` 425, `create_app` 336, `routes_chat._stream_lines`
334, and 24 functions pass 150 lines (open). "No import cycles" counted
`import` statements only; with the `importlib.import_module` edges the
package's own comments use to step round the lint, there are three cycle
groups, the largest fifteen modules. `tests/test_import_module_cycles.py` now
counts those edges and holds both numbers as a ratchet (open: shrink them).

## 23. Filing and the taxonomy: candidates, a decision, an explanation (2026-10-10; Brief 39b)

The owner's words: "Should we include a library of common possible categories and
even ways to join words to make custom categories and then there can be a
similarity search for new or existing category filing and concatenation for new
categories, suggested alternative existing and new categories, same for tags. It
should be a thing where it decides if it is closer to an existing category or a
new category, and maybe it can even provide suggestions for merging categories
and alternate category names"; "some categories might not just be gym or
Fitness but gym & fitness"; "Study and university tags are suggested on the top
note no matter what the note is about"; "Still lots of issues with filing
without the ai model running". INBOX 730 answered that filing without a model
exists (lexical filing, centroids, nearest neighbours); this section makes it
good and explained.

### What exists (checked)
`ai/lexical_filing.py` (TF-IDF votes, category-name votes, tag votes with
`TAG_NAME_VOTE`, `TAG_MIN_VOTE`), `ai/janitor.py` (`_semantic_category`,
centroids over the embedder, nearest neighbours), Tidy's rule reviews
(`frontend/js/tidy.js`), the Gemini branch's `ai/taxonomy.py` (18 categories,
FlashText; superseded by the pack below).

### Decisions, 2026-10-10 (do not re-decide)
1. **Seed data, not a classifier.** The Perplexity "final consolidated pack"
   (5.0.0: `memorymap_taxonomy.json` 527 categories and 6,478 assignments,
   `memorymap_occupations.json` 1,109 roles, `memorymap_entities.json`,
   `memorymap_facets.json`, `memorymap_context_rules.json` as a spec, 64 passing
   tests) lands as JSON under `src/tessellate/ai/data/taxonomy/` (about 470 KB),
   loaded lazily on the first filing, matched by the vendored FlashText as
   **candidate generation only**. Its module's API shape (`analyze_note`,
   `extract_categories`, `extract_occupations`, `extract_entities`,
   `reset_taxonomy_processors`) replaces Gemini's `ai/taxonomy.py`; its tests
   come with it. Credits in THIRD_PARTY.md.
2. **The decision is the person's categories first.** For each existing
   category: a name or alias match to the pack's topics ("Gym" is Fitness), the
   TF-IDF votes shared with notes already filed there, the centroid cosine when
   the embedder runs, a recency prior. A **new** category is proposed only when
   no existing one clears its threshold; a **composite** ("Gym & fitness") only
   when two topics tie within ten percent and both occur in the note. New and
   composite names are proposals until accepted once; then they are the
   person's and are matched like any other.
3. **Every filing is explained** in one line on the suggested-category chip and
   in Tidy (CHAT_PLAN decision 39): the words shared, the notes it joins, the
   measure that decided.
4. **Merge and rename suggestions** live in Tidy: two categories whose topic
   sets overlap at least 0.6 and whose centroids are within 0.15 become a row
   "Merge Gym and Fitness?" with counts; alternate names come from the pack's
   labels (`entry/tidy.py` `_rows_category_names`; the person's own titles
   were dropped, 2026-10-11: a note's title is not a name for its category).
   Applying asks; undo is one press.
5. **Tags** take the same candidates, capped at three, each explained; a tag is
   never proposed on a note that contains none of its words (the "Study and
   university" bug: find the vote that did it, with a test).
6. **Sensitive topics** (health, relationships, finance, legal, identity:
   Tessellate's own list of 49, `ai/data/taxonomy/memorymap_filing.json`; the
   pack carries no flag) are suggested, never auto-filed, unless the person turned
   auto-filing on for them in Settings. Amended 2026-10-10 (INBOX 770): on
   every path, the chat model's and the embedder's included: built the same
   day (`janitor._unless_held`, `lexical_filing.holds_sensitive`).
7. **A personal lexicon** from the pack's reviewed-vocabulary utilities: the
   person's corrections ("Work, not Software") become aliases stored per
   notebook and weighed first; nothing is learned from automatic predictions.
8. **Measurement first.** `tests/fixtures/filing/` grows to 120 hand-labelled
   notes (varied kinds and lengths, pasted text, jokes, captions, several
   sensitive); top-1 accuracy with and without the embedder, before and after
   every step, recorded here. Below 0.8 top-1 without a model the step is not
   done.
9. **Contextual rules** (the pack's 30 seed rules and 50 acceptance fixtures)
   are the phase after: a small interpreter for positive and competing context
   patterns within the sentence, measured on those fixtures, only once steps 1
   to 8 hold.

### Steps
1 to 4 built 2026-10-10 (filing-1010): HISTORY.md, "Moved from the plans,
2026-10-10 (filing-1010)", with the numbers. Step 6, built 2026-10-11 (tagsearch-1011):
`memorymap_everyday.json` adds general words to the pack's topics; no model,
top-1 0.417 to 0.617 filed (0.792 with sensitive notes suggested), and on 48
held-out notes 0.458 to 0.667 (0.833). Open: decision 8's 0.8 *filed* (the
strict xfail stays; 19 of 120 are sensitive and held by decision 6, so 0.84 is
its ceiling); the owner reviews the vocabulary file; step 5's Built block.

## Placed from INBOX, 2026-09-09

The owner's reports this plan owns, moved whole from INBOX.md with their numbers (never reused). Each becomes a phase row when its phase is written; until then this list is the phase.

1. **Deleting a space leaves its notes in "All spaces".** Read and not
   reproduced in code: `routes_spaces.delete_space` hard-deletes every
   workspace-scoped row in one transaction and
   `tests/test_space_delete_cascades.py` proves it. The likeliest cause is
   notes captured while "All spaces" was selected: those carry the default
   workspace, not the space, so deleting the space cannot touch them. Fix
   the cause of the confusion, not the cascade: (a) show the space chip on
   every note card and in the edit form; (b) the capture form files into
   the *selected* space and says which; (c) a "Move to space" bulk action.
   Owner: D2 and D5. If the owner can reproduce with a note that shows the
   space chip, reopen as a backend bug.
15. Decided, nothing to fix (the strip is the native title bar); moved to
    HISTORY.md, "Moved from the plans, 2026-09-24".

22. **Settings > Packages rows misaligned** (icon, text and the install
    button on different baselines). Owner: consistency.md item 4; the
    alignment sweep must include Settings > Packages and Settings > Help.
23. **Settings > Help gaps** (accordion rows touch, sections have no
    rhythm). Owner: help-popovers.md, with item 22.
26. **"Things that feel off that I cannot place."** After the consistency
    and docks lists close, one review pass per tab with the vendored
    design skills (`.claude/skills/README.md`) against DESIGN.md, writing
    findings as consistency.md rows, not fixing ad hoc. Owner:
    consistency.md, last item.

62. Decided (the strip stays opt-in); moved to HISTORY.md, "Moved from the plans, 2026-09-24".

99. **Quick wins (Fable, 05:20): five features the plans did not list,
    each a day or less, each with the site.** (a) Undo on every delete
    toast: notes, boards, documents and reminders already soft-delete;
    `toastAction(msg, "Undo", () => restore)` at each delete call site
    (grep `toast(` beside `DELETE`), so a wrong click never reaches the
    bin. (b) "Reopen where I left off": documents and chats restore
    scroll position per id (localStorage `scroll:<kind>:<id>`), the
    Dashboard "Continue" tile (INBOX 60) reads the same keys. (c) The AI
    dot's tooltip shows the last answer's latency and the model's context
    use ("granite4.1:3b, 2.1 s, 39% of window"), from data the chat
    header already has. (d) A "Paste as note" global shortcut
    (Ctrl+Shift+V anywhere) that captures the clipboard as a new note
    with the AI filing it, the fastest capture path on a desktop. (e)
    Search operators in the Notes search box (`tag:`, `space:`,
    `before:`, `after:`, `has:file`), parsed client-side into the existing
    filters, with the operators listed in the box's '?' popover.
79. **Files sub-tab rows "could still use a massive redesign upgrade", and
    clicking the file name does nothing**. Owner: Library dossier
    (WORLD_CLASS 4), Opus: one row recipe (thumbnail, name as the one
    link that opens the reader, meta line, reading state as a small
    disclosure, actions in a kebab), the name clickable.
92. **Suggested links panel UI refine** (screenshot: rows of quoted
    pairs, a wide "Why?" input, a percent chip, Link and X). Owner: Opus,
    next slot: two note chips joined by an arrow, the score as a small
    bar, the reason field collapsed behind "Add a reason", Link primary
    per row, a "Link all above 70%" action in the head.
97. **OCR alternative to pytesseract**, asked directly. Answer: RapidOCR
    (PaddleOCR models on onnxruntime, pip-installable, no system binary,
    better on photos and mixed layouts, about 60 MB of models, Apache-2)
    is the one to offer; EasyOCR needs torch (never). Placed as a
    Settings > Packages option beside Tesseract, same reading pipeline,
    the reader named on the row. Owner: next session, Sonnet (backend
    adapter with a fake in tests) plus the Packages row.
98. The same decision as 62; moved with it.

**State 2026-10-05:** every item below is built or decided; the list stays
as the record of what was placed. Built 2026-10-05 (HISTORY.md, "Moved from
the plans, 2026-10-05 (nbf1005)"): 1's Move to space (row 30), 99 (b), (c)
and (d), 92's row, 22's last 5px and 261's re-key button; found built: 1's
capture into the selected space (`updateCaptureSpaceLabel`), 23 and 79
(79 re-checked 2026-10-05 by op4-1005: every Library card kind is a select,
one open control and one kebab, the Files row "Read this" plus a nine-row
kebab). 97 was decided not to build as a dependency (the owner, 2026-10-05:
"make sure it is fully local and doesnt use any external libraries that
arent vendored"); it is built as an optional extra instead, on the person's
own press like faster-whisper, never imported unless installed, and
Tesseract stays the reader whenever it is ready: HISTORY.md, "Moved from the
plans, 2026-10-05 (row 31 item 97, RapidOCR as an optional extra)". Whether
an optional pip extra meets the fully-local rule is the owner's to confirm
(INBOX-worthy if they say no: remove the `rapidocr` row and its bundle place).

**State 2026-09-24:** 1 (b): a space chip is drawn on
note cards; capture into the selected space and a "Move to space" bulk action
were not found. 22 and 23 were not re-checked (their agent files are
archived). 26 is a standing review, (d). 99: (a) undo toasts are built (H9
records it) and (e) the operators are built (section 5 item 1); (b) scroll
restore per id, (c) the AI dot's latency and context tooltip and (d) Paste as
note were not found, S each. 79 was not re-checked. 92 (b): "Add a reason"
sits behind a menu row now; the chips-and-arrow row and "Link all above 70%"
were not found. 97 (c): no RapidOCR adapter. M.

## 17. The original vision, audited (2026-09-09)

The owner's first notes, written months before a line of code (the
"AI Assistant Personal Database Management" list and the May 2026 master
reference), read against what exists. Almost all of it is built; the seven
rows marked open are the vision's own features nobody has planned since,
and they go first in the next session's World-class section.

| The original idea | Today |
| --- | --- |
| Type anything, a local AI files it; guided mode when you want to choose | Built (capture, Let the AI decide, guided) |
| Two AIs: a Janitor that files and never talks, a Librarian that answers and never writes | Built as the filing step and the chat; the librarian tags, links and flags duplicates in the background |
| A conversational answer and the raw database results side by side | Built (Ask: the answer beside the matching records) |
| Confidence on every filing, low ones flagged for review | Built half: the score shows; **open: a review queue** (below) |
| The AI tidies the database over time: merges near-duplicate categories, removes empty ones, respects manual changes | Built half: duplicates flagged, links suggested; **open: category tidy proposals** |
| Preferences for how the database is structured | **Open: a filing style preference** |
| Recycle bin, 30 days, configurable, clearable | Built |
| 100% offline, models local; optional web search for context | Built (models through Ollama, not bundled, by decision; web search opt-in) |
| File attachments copied into the app's folder | Built (Files, three readings per image, PDFs read page by page) |
| Google Drive plus Notion plus NotebookLM | Built as Library, Documents and Ask with sources |
| AI-generated data visualisation | **Open: charts from questions** |
| Last five queries; most-accessed information | Built (Ask history); **open: most-opened widget** |
| A log of everything entered, accessed, altered, archived | Built (activity log) |
| Manual links, or tell the AI about a link | Built |
| The graph like Obsidian's | Built (the canvas graph, Phases 1 to 5) |
| Submit a whole Markdown file as an entry | Built (documents import) |
| A whiteboard or canvas, submitted as an entry, editable later | Built (whiteboard, mind maps) |
| Export in bulk or in part | Built (JSON, CSV, Markdown, zip) |
| Login with a hashed password | Built (bcrypt, throttled) |
| A profile the AI uses, built over time, opt-out and delete | Built (About you; What it remembers) |
| Speech to text; the AI reads answers aloud; explains what you entered | Built (Whisper, read aloud); **open: "explain this note"** |
| Reminders, maybe a calendar | Built (reminders); **open: calendar export and month view** |
| Fine-tuning | Dropped, correctly, in the May document |

**The seven open rows, as quick rows for the next session (WORLD_CLASS,
after Brief 18 section A):**

1. **Review queue.** A Notes filter "Needs review" for filings under 60%
   confidence and anything filed Uncategorised, with Accept, Refile and
   Split per row; the count on the dashboard. Backend: `confidence` and
   `category_id` exist; one query. Size S.
2. **Tidy categories.** The librarian proposes merges (two categories
   whose embeddings and names are near) and removals (empty for 30 days)
   as a proposal list in Settings > What it remembers; nothing moves
   until accepted; manual renames are remembered as "do not merge". Size M.
3. **Filing style.** A preference (by topic, by project, by time) added
   to the filing prompt and to the category namer, with three examples
   each; the default is by topic. Size S.
4. **Charts from questions.** Ask answers a counting or trend question
   ("how many notes per category this month", "my race times") with a
   bar or line drawn from the records, the data table under it, the
   chart exportable as PNG. Size M.
5. **Most opened.** A dashboard widget of the ten notes opened most this
   month (the view counter exists on the node panel). Size S.
6. **Explain this note.** A note action that reads the note aloud and
   then says what it links to and why, from the link reasons. Size S.
7. **Calendar.** `.ics` export per reminder and for all, and a month view
   beside the reminders list. Size M.

The principle the first notes state and the app keeps: the AI is a
servant, not a gatekeeper; everything it does can be seen, edited and
undone.

**State 2026-10-05:** all seven built; the six that were open moved to
HISTORY.md, "Moved from the plans, 2026-10-05 (nbf1005)". Not built from row
1's sketch: Split per row (no note has a split action anywhere in the app;
Accept and moving the category are the row's two answers).

**State 2026-09-24:** the seven rows: 1 review queue (c),
S. 2 tidy categories (b): the agent has `merge_categories`

**Decisions made, 2026-10-05 (recommended, not confirmed):** (1) the
review queue's line is the card's `REVIEW_THRESHOLD`, 50, not row 1's
"under 60%": a note in the queue then always wears the "check this" chip
that says why, and one number cannot drift from the other
(`manager.REVIEW_CONFIDENCE`). Its count sits in the Categories widget,
not a widget of its own. Split is Extract notes over the whole note.

**State 2026-09-24:** the seven rows: 1 review queue: built 2026-10-05
(HISTORY.md, "Moved from the plans, 2026-10-05 (section 17)"). 2 tidy categories (b): the agent has `merge_categories`
(`ai/tools/categories.py`); the proposal list is not built, M. 3 filing style
(c), S. 4 charts from questions (c), M. 5 most opened (b): the Most used
widget lists the notes opened or matched most, all time
(`/entries/most-accessed`); "this month" needs an open log, S (its picker
line was wrong and was fixed 2026-09-24). 6 explain this note (c), S. 7
calendar: built. The month view (`#reminder-calendar`) and, 2026-09-26,
`.ics` export with its two buttons (HISTORY.md, "Moved from the plans,
2026-09-26").

## Placed from INBOX, 2026-09-13

F2's frontend half (five callers read `/files/gallery` whole) was built
2026-09-24 and moved to HISTORY.md, "Moved from the plans, 2026-09-24".

## 18. The next horizon, written 2026-09-14 at the close of PR 144

**Where the plan stands.** Built and moved to HISTORY: B1 the event log,
B3 the retrieval engine with explanations, B5's verifier and budget
(Brief 13), I4 resurfacing with its dashboard surface, I9 the learned
store with its Settings page, the first pass of I1, the tensions kernel
behind B4 (`ai/tensions.py`, `ai/entities.py`), and the whole of the
consistency contract in §1 as lints. The audit above (A1 to A9) lands in
this PR: the bounded job pool is the first half of B2. Open, in the order
they pay back: B2's resume-after-kill, I3 open questions, I6 evidence
cards, I8 the model bench, I2 the margin reader, I5 time travel, B7 the
API contract, B8 extensions, B6 sync. The dossiers D1 to D15 were largely
absorbed by UI phases 0 to 11 and the per-surface plans; what each still
owes is one line in `agent-remaining/OPEN.md`.

**What "revolutionary" has to mean now.** The two asymmetries in §15 hold:
the model is free and idle, and the corpus is one mind. Every cloud
notebook in the §2 table has since shipped a chat box over notes; none has
shipped a notebook that works on itself overnight, shows its reasoning
sentence by sentence, or can be audited and corrected as a habit. That
gap is the product. The horizon below is ordered so each item makes the
next one measurable, and each names its gate, because a feature without a
number is a demo.

### H1 The night shift, finished (I1 second pass; L, Opus)

What exists: `ai/autonomous.py` and `ai/janitor.py` run scheduled passes;
`core/events.py` records every change; I9 shows what was learned. What is
missing is the morning: a report card that says what the notebook did
while you slept, with one undo per line. Build: a `night_runs` table (run
id, started, finished, model, passes, changes, cost in tokens and
seconds); a dashboard card "Overnight" listing each change as a sentence
with Undo and Never again (the I7 correction); a Settings row for the
window (start, stop, battery guard). Gate: a seeded notebook of 200 notes
runs a night in under ten minutes on a 4B model against the fake
transport, every change is undoable, and the report card's count equals
the event log's count for that run. Test first: `tests/test_night_runs.py`.

**State 2026-10-04:** the same as I1 above.

### H2 Evidence cards and open questions (I6 then I3; L, Opus)

What exists: the Ask answer object carries per-sentence citations
(`test_ask_answer_object.py`); the chat's checkable answers. Build I6 as
the surface: each sentence of an answer is a card that opens to the
passage, the note, the date and the retrieval score's three parts (§4
B3), with "wrong" as a correction that retrains the ranker's weights
(I7). Then I3: a question the model could not answer from the notebook
becomes a row in "Open questions" with the notes that came closest, and
the night shift retries it when new notes arrive. Gate: 95% of sentences
cited on the seeded notebook; a corrected citation changes the next
answer's ranking (asserted, not eyeballed).

**State 2026-10-04:** I6 built (row 6) and I3 built (row 7), both in HISTORY; left here: "wrong" on a card retraining the ranker (I7).

### H3 The model bench (I8; M, Opus)

Built 2026-10-05 with I8: moved to HISTORY.md, "Moved from the plans, 2026-10-05 (the model bench)".

### H4 The notebook as a local service for other agents (B7 and B8; M, Opus)

The next year's local agents (coding agents, desktop assistants) will want
a memory. Tessellate already has the tools (58 in `ai/tools/`), the
permission gates and the audit log. Build: a versioned `/api/v1` contract
generated from the routers (schema behind auth, B7), and an MCP server in
`src/tessellate/mcp/` exposing the same tools with the same "asks first"
rules, so any local agent can read and write the notebook and every write
lands in the event log with the agent named. Gate: the MCP server passes
the same tool tests as the in-app agent; an external write shows in the
activity panel within one poll.

**State 2026-10-05:** built (`/api/v1`, the agent named on an outside write over MCP and HTTP); moved to HISTORY.md, "Moved from the plans, 2026-10-05 (B8, H4)". Left: the gate's first half, the MCP server passing the in-app agent's own tool tests, is not run. S.

### H5 Sync without a server (B6; L, design first)

Design now, build after H1 to H4: an encrypted append-only export of the
event log (B1 makes this possible) to a folder the person already syncs
(any file-sync tool), and an importer that replays another device's log
with last-writer-wins per field and a conflict list for the rest. No
server, no account. Gate: two data dirs converge after each replays the
other's log; a conflicting edit appears once, in the Library, with both
versions.

**State 2026-09-24:** (c), B6.

### H6 Professional use (the PR after 144; M, mixed)

The owner's stated next block: refinements for daily professional use.
The list, each with its gate: one-click recovery (INBOX 253: a launcher that
repairs a start that fails, and a Repair shortcut beside the app, gated by
a deliberately broken venv coming back without a prompt); import from Obsidian, Notion export and
Apple Notes (round-trip test per format); print and PDF export of a
document with its citations; keyboard-complete (every dock action
reachable, `keys.js` extended to every tab); a WCAG AA audit with
`contrast.js` and `touch.js` as the standing gates; multi-window on the
desktop (a document in its own window); a first-run tour that ends in a
first note and a first question, measured by time to first answer.

**Decisions made.**

1. **Release artifact naming: `<name>-<version>-<platform>-<arch>.<ext>`,
   one scheme across every installer.** INBOX 266 asked for version,
   platform and architecture in every installer's name, "so two files
   downloaded a month apart from different machines are distinguishable in
   a Downloads folder, and a 64-bit build and a future 32-bit or ARM one
   never overwrite each other." Built and applied to all four release
   artifacts `.github/workflows/release.yml` produces: the Windows `.exe`
   (`packaging/windows/installer.iss`'s `OutputBaseFilename`,
   `MemoryMap-AI-Setup-{#MyAppVersion}-windows-x86_64`), the Windows `.msi`
   (`MemoryMap-AI-$env:TESSELLATE_VERSION-windows-x86_64.msi`, built by
   `packaging/windows/installer.wxs`), and the Linux `.tar.gz` and `.zip`
   (`MemoryMap-AI-${VERSION}-linux-x86_64.{tar.gz,zip}`). `x86_64` rather
   than Inno's own `x64` spelling: it is what `uname -m` prints and what
   the Linux side already used, and one spelling across platforms is worth
   more than matching one installer's internal vocabulary. Both the
   `.tar.gz` (item 2) and the `.msi` (item 3, shipped beside the `.exe`,
   not instead of it, with its own "Repair MemoryMap AI" shortcut per
   INBOX 253) already existed before this entry was picked up; the naming
   pass (item 4) is what is new, and `tests/test_release_smoke_step.py`
   (`test_windows_exe_filename_carries_name_version_platform_and_arch`,
   `..._msi_filename_...`, `..._zip_filename_...`) is the lint: it parses
   `release.yml` and `installer.iss` as text and fails if any artifact's
   name loses its version, platform or architecture. Not verified on a
   real release run: no tag push or Windows/WiX runner exists in this
   sandbox, so the check is that the workflow and installer sources parse
   and read as intended, not that `wix build`/`ISCC.exe` actually produced
   a file with that name.

**State 2026-10-05:** (b) done: one-click recovery (253), the release naming (decision 1), the four importers, keyboard-complete for every dock, the WCAG audit and the first-run path timed to a first answer (HISTORY, "row 25, the importers and the keyboard" and "H9, polish in use; the rest of row 25"). Open: print and PDF of a document with its citations (the print stylesheet exists; citations in it were not checked) and multi-window.

### H7 The speed budget (A1 continued; S each)

Boot JS under 1 MB compressed (from 1.7 MB), first paint under 300 ms on
the reference laptop, every list over 200 rows virtualised, `/entries`
paged everywhere. `scratchpad/ui-sweeps/boottime.js` is the gate and its
numbers go in the CHANGELOG with each step.

**State 2026-09-24:** (b) boot JS went 1,699 to 1,072 KB (A1, in HISTORY) against the 1 MB line; first paint under 300 ms and virtualising every list over 200 rows were not measured here. S each. Lists past 200 measured 2026-10-05 (`ui-sweeps/s2-1005.js` MODE=rows, 300 rows, 1440, under load): Reminders 9,756 nodes, scroll p95 24 to 25ms; Timeline 2,148 nodes, p95 19 to 22ms; Library docs 12,090 nodes (40 a card), p95 32 to 42ms, worst 57 to 66ms; a `content-visibility` row for the Library was inconclusive (41 and 128ms worst), not applied.

**Corrected 2026-10-05 (audit FE-06).** The 1,072 KB did not hold: nine days later boot JS was 1,384 KB gzipped (own 1,294 plus d3), and `boottime.js` was never in `gate.sh`, so nothing stopped it. The gate is now `tests/test_boot_budget.py`, which gzips every boot script and stylesheet as served and fails over its caps (measured plus 2%, only lowered). With comments stripped at serve time (`api/asset_strip.py`, FE-01) boot JS measured 691,724 bytes (d3 92,459 of it) and boot CSS 179,712. p5 was still fetched after load and d3 was a boot script (FE-07): both off the boot since 2026-10-05, d3 with the graph and library bundles, the emblem a 2D canvas.

**Performance pass, 2026-10-03 (INBOX 441 item 6, measured).** Method: a 500-note notebook seeded through `POST /entries` (the app boots against it), a 5,000-note copy grown by direct insert for the scale numbers, every boot route and tab route timed through `TestClient` with SQLAlchemy statement counts and `EXPLAIN QUERY PLAN` on every distinct statement, and Playwright with CDP (event timing, a sampling CPU profile, a trace) for the page. The sandbox was at a load average near 100 while this ran, so every pair below was measured on the same machine in the same minutes (interleaved, base checkout against this one) and the milliseconds are for comparing, not for quoting.

| What | Before | After |
| --- | --- | --- |
| `GET /entries/reference-counts` for sixty cards, run at every unlock, 500 notes | 242 statements, 172 ms | 6 statements, 53 ms |
| the same, 5,000 notes | 2,267 ms | 388 ms |
| the same, in the browser at boot (500 notes) | 392 ms | 154 ms |
| `GET /insights/heatmap`, 5,000 recent notes (loaded every note whole to read its day) | 179 ms | 24 ms |
| `GET /insights/stats`, same | 184 ms | 55 ms |
| `GET /media` (the "used in" scan loaded every note, document and board object), 5,000 notes | 140 ms | 9 ms |
| the first click of a session (the unlock): its handlers, `new AudioContext()` inside the gesture | 44 to 56 ms | under 1 ms (made at idle just after; the context is running) |
| 900 lookups by `parent_id`, a note's board cards and its reminders, 5,000 notes, 4,000 cards, 1,500 reminders | 604 ms | 2.9 ms (six indexes in `_INDEXES`) |
| a whole boot, unlock to settled, 500 notes (3 interleaved runs, median) | 1,378 ms, API time 3.1 s | 1,282 ms, API time 2.8 s |

**Measured and left alone, with the number that says why.** SQLite pragmas: `cache_size` 64 MB and `mmap_size` 256 MB moved a scan of a 19 MB database from 3 to 2 ms and nothing else, against memory held per pooled connection, so they stay unset (WAL, `synchronous=NORMAL`, `busy_timeout`, `temp_store` are already set). Polling: an idle minute is 2 requests, the gate; the three `/models/status` and `/tasks` calls in the first seconds are the 1 s cadence while the filing model warms, by design. Listeners: `leaks.js` reads 0 listeners and about 20 nodes a round over five rounds of seven tabs. Layout: the whole boot spends 38 ms in layout and 51 ms in style recalculation, so the forced-layout reading `tabContentWidth` shows in a sampling profile is attribution, not cost. Batching the note cards' clamp checks into one read-then-write frame was tried and made no difference to typing in the search box (both about 150 ms of one layout over 12 keystrokes, interleaved), so it was taken back out. The three request pages of `/entries` at boot are the paging contract and the first paints at once. (Corrected 2026-10-05, audit ARCH-04: three pages was 500 notes; the loop reads until `X-Total-Count`, 26 pages and 2.3 MB at 5,000 notes. A keyset cursor exists server-side; the reader-by-reader client change is the frontend audit's FE-05.)

**Found, not fixed.** The Graph tab's `GET /graph` is 600 ms and 2.5 MB at 5,000 notes (per-note dict building, two `readable_content` calls and a regex each; a payload cache keyed on `_graph_fingerprint` would need the vault and space state in the key). `p5.min.js` is the largest boot asset (247 KB on the wire, about 85 to 135 ms of parse and setup) and is still needed by the dashboard constellation and the emblem; porting those two to canvas 2D, as `bg-art.js` already was, removes it from boot. `enhanceAllSelects` wraps 99 `<select>`s at boot (about 50 ms), most inside Settings panes nobody has opened. Creating a note costs about 300 ms in this sandbox, all of it the embedding model.

### H8 Time travel and the margin reader (I5, I2; M each, Opus)

I5: "what did I think about X in March" as a first-class query, the
retrieval engine's date signal exposed as a slider on the Ask surface,
with the answer's cards grouped by month. I2: the second reader in the
document editor, a margin that fills with the person's own related notes
as they write, from the same engine, with the link-strength explanation
under each. Both reuse B3; both gate on the 150 ms budget for a
keystroke-to-margin update.

**State 2026-10-05:** I2, the margin reader, built for documents (HISTORY, "the margin reader"); I5 open (row 23).

**State 2026-10-05:** I5 (b), built as row 23 (HISTORY.md, "Moved from the plans, 2026-10-05 (row 23: time travel)"), without the month grouping or a date slider (a day picker); I2 (c).

### H9 Polish in use (the owner's question, 2026-09-14; S to M each)

Built 2026-10-05, every row: moved to HISTORY.md, "Moved from the plans, 2026-10-05 (H9, polish in use; the rest of row 25)". Left: `boottime.js` in the CI workflow itself (the budget that runs on every push is `tests/test_perf_budget.py`).

### The order, and the rule

H7 first (it makes every later measurement honest), then H9's perf gate
and usage ledger, then H1, H2, H3, H6, H4, H8, H5. One horizon item per PR, its Built block moved to HISTORY at
the end, its numbers in the CHANGELOG. Nothing above is started until
`OPEN.md` is empty for the surface it touches: a revolution on top of an
unfixed report is how the "fixed again" rounds happened.

## 19. The architecture and framework review (2026-09-20, INBOX 266)

The owner, twice: *"We need to do a full architecture analysis and make sure
that we are actually using the right architecture and backend functions ... I
need you to fully analyse the architecture and framework decisions and make
sure that they are all the best they can be"*, with *"Lightweight as
possible"* beside it.

**This is a first pass over the load-bearing decisions, every claim
measured.** It is not the whole stack: it is the choices that cost the most
if they are wrong. Where a decision is sound the entry says so and why, since
a review that only lists faults is a review nobody can act on.

### 19.1 The one number that matters: 776 MB resident, idle

Measured on a running instance with nobody touching it, from
`/proc/<pid>/smaps_rollup`:

| | |
| --- | --- |
| RSS | 776 MB |
| PSS | 478 MB |
| Anonymous (not file-backed: allocations, model weights) | 429 MB |

And what the process has mapped, counted from `/proc/<pid>/maps`: **436
shared objects from scipy, 117 from sklearn, 29 from torch.** That is the
`sentence-transformers` stack, loaded by the `embedding-warmup` thread on
every launch.

**Why this is the finding and not a curiosity.** The packaging already treats
semantic search as optional: `packaging/windows/memorymap.spec` excludes
torch and sentence-transformers from the installer with a comment saying
Settings, Packages fetches them on demand, *"a few hundred MB for a feature
this build already has a working path to install on demand"*. So the shipped
build's position is that this is optional, and the running app's position is
that it loads at startup regardless. Those disagree.

Three directions, cheapest first, none yet taken:

1. **Load on first use, not at launch.** The warm-up exists to avoid a pause
   on the first semantic query; a notebook that never runs one pays 429 MB
   for a pause it will never have. Whether the warm-up should be a
   preference, or triggered by the first search, is the decision.
2. **ONNX Runtime instead of torch** for inference. Same model, a fraction of
   the resident cost, no scipy or sklearn in the import graph. This is the
   change with the best ratio and the most work.
3. **Confirm scipy and sklearn are reachable at all at query time.** Vectors
   are stored as raw float32 and compared with numpy (`ai/embeddings.py`), so
   the scientific stack may be a load-time import only. If so it is 553
   shared objects mapped for nothing.

**State 2026-09-24:** (b) direction 1 is half taken: numpy is imported lazily (`tests/test_lazy_heavy_imports.py`) and the warm-up waits for the first page and skips an empty notebook (`tests/test_embedding_warmup.py`), but a notebook with notes still loads torch at launch. Directions 2 (ONNX) and 3 (is scipy reachable) are (c). M.

### 19.2 The frontend is 5.9 MB decoded, and that is mostly fine

Measured with the Navigation and Resource Timing APIs on a cold load:

| | |
| --- | --- |
| Resources | 50 |
| Decoded total | 5,914 KB (js 1,283, other 4,410, font 144, css 76) |
| `index.html` decoded | 661 KB |
| DOMContentLoaded | 182 ms |
| JS heap after boot | 18 MB |
| DOM nodes | 7,844 |
| CSS rules | 5,844 |

**The honest reading: weight is not costing what it would cost a web app.**
This is served over loopback to a local process, so 5.9 MB is not a download
and DOMContentLoaded at 182 ms says so. The costs that are real are parse
time on a slow machine, the 18 MB heap, and the installer's size. A bundler
and code splitting would be a large change to a codebase that deliberately
has no build step (`CLAUDE.md`: "No build step: `frontend/js/*.js` and
`frontend/css/*.css` are served as-is"), and the measurement does not justify
paying for it yet.

Two things are worth doing anyway, both small:

- **Phosphor ships 1,530 glyphs; the app names 504.** A subset font is a
  build step for one file and turns 144 KB into roughly 50 KB. It is also
  the single largest asset on first load.
- **All eleven stylesheets are linked eagerly**, 1.8 MB on disk for every
  surface including the ones not open. The files are already split by
  surface, so this is a `media`/`disabled` attribute question rather than a
  restructure.

`p5.min.js` is 1 MB and is **already lazy** (`app.js` injects the tag when
the dashboard art runs), which is the right answer and is recorded here so
nobody "discovers" it again.

**State 2026-09-24:** (c) both: `Phosphor.woff2` is still 147 KB whole, and all twelve stylesheets are linked eagerly. S each.

### 19.3 SQLite is the right store, and the reasons are not the obvious ones

The owner named this as the example. It holds, but the usual justification
("it's simple") is not the strong one:

- **One file is the backup story.** The app's export, restore and "your notes
  are yours" promises are all one file copy. A server-based store (Postgres)
  would need a dump step, a running daemon, a port, and a version match
  between the data and the binary that opens it. For an app whose entire
  pitch is offline and local, that is not a trade, it is a different product.
- **A document store (files on disk, one per note) is the real alternative**,
  and it is what Obsidian does. It loses transactions across a link edit, and
  this app's data model is a graph: a note, its links, its embeddings, its
  derived facts and its board positions change together. SQLite gives that
  atomically; a folder of markdown does not.
- **The scale is right.** SQLite is comfortable to hundreds of thousands of
  rows, and the measured notebook this project tests against is 4,005 notes.
  The ceiling is not close.

**What is worth checking and has not been**: whether the schema's indexes
match the queries the app actually runs, especially the note list's sort
paths and the search fallback. That is a measurement (`EXPLAIN QUERY PLAN`
over the real query set), not an opinion, and it is the sort of thing that
turns a 0.9 s list load into a 0.2 s one.

**State 2026-10-05:** built; moved to HISTORY.md, "Moved from the plans, 2026-10-05 (19.3, 19.5)". Left: the full reads (the graph, duplicates, resurfacing read every live note, 70 to 100 ms at 5,000) are reads of everything by design, not index misses; nothing runs `ANALYZE`, and turning it on is a separate measurement.

### 19.4 Idle compute: the assumption did not hold

Asked as *"are things running when they arent necessary and taking up extra
compute??"*. Measured both halves:

- **Backend**: 4 threads with the app idle, **0 `threading.Timer`s**. The one
  scheduler (`ai/autonomous.py`) blocks on `Event.wait(interval)`, and its
  own comment records that it used to wake 21,600 times per cycle and was
  fixed.
- **Frontend**, per tab over 30 s with nobody touching it: **2 to 6 requests
  a minute**, main thread **0.6% to 2.6%** busy. The dashboard is the
  highest, which is its animated widget.

Two small things, neither urgent: four independent one-second timers repaint
four different clocks (`tickClocks`, `paintStatusClockDetail`,
`paintDashClock`, `paintChatTimer`) where one tick could drive all four, and
the scheduler thread exists even when the feature is switched off.

**On "containers spun up as needed, like serverless"**: that shape solves a
problem this app does not have. Serverless exists to stop *idle server* cost
across many tenants; here there is one user, one process, on their own
machine, and process startup is the thing a person waits for. The right
version of that instinct is 19.1: load the expensive thing when it is first
needed rather than at launch.

**State 2026-09-24:** (d) the four one-second clocks are still separate timers; the section itself calls them not urgent, and F6's idle gate is met.

### 19.5 What the review has not covered yet

Named so the next session does not mistake this for complete: the FastAPI and
SQLAlchemy layer's own shape (are the ORM's lazy loads causing N+1s on the
list paths?), the event bus, the job queue's back-pressure, the frozen
build's startup profile on Windows, and the `EXPLAIN QUERY PLAN` pass in
19.3. Each is a measurement with a command, in the manner of §10.

**State 2026-10-05:** (b) N+1 on the list paths has a test (`tests/test_scale_query_counts.py`); the job queue's back-pressure is measured and built (HISTORY.md, "Moved from the plans, 2026-10-05 (19.3, 19.5)"); the event bus and the Windows frozen startup are open. S each.

## Placed from INBOX, 2026-09-21

261. **Found by scan, 2026-09-19 (the session, not the owner).** Ten routes
    the app serves that `frontend/js/*.js` never names, from
    `scratchpad/probe_dead_routes.py` (new; run it with `PYTHONPATH=src`).
    Four more were in this list and are now wired: `GET /learned` and its
    whole lifecycle, `POST /night/run`, `GET /search/stats` and
    `POST /drafts/title`. What is left, triaged:
    - `GET|POST /entries/daily/{day}`, `POST /resurface/compute` and
      `GET /openapi.json`: not the frontend's to call. The daily-note pair
      is the agent's "add to today's note" tool and says so in app.js; the
      compute half of resurfacing is the scheduler's, and its module
      docstring is explicit that the read is the fast one; `/openapi.json`
      is FastAPI's own. **Nothing to do.**
    - `POST /insights/digest` and `GET /whiteboard/images`: superseded and
      recorded as such (`/insights/digest/stream` is what the dashboard
      calls; BACKLOG says `/media` replaced the board image listing).
      **Recommendation:** leave them, or delete them in a sweep of their
      own; either is defensible and neither is urgent.
    - `GET /insights/on-this-day`: superseded by choice. The widget filters
      `allEntries` in the browser, which is one fewer request and is
      correct once the notebook has finished paging in.
      **Recommendation:** leave it, and say so in the route's docstring, so
      the next scan does not re-open this.
    - `GET /tags`: done (moved to HISTORY.md, "Moved from the plans, 2026-09-24").

    - `GET /settings/events`: built 2026-09-23 as the Dashboard's Recent
      activity widget (moved to HISTORY.md, "Moved from the plans, 2026-09-24"); the Timeline half is
      declined by decision (a second clock on one page).

    - `GET /resurface/near/{entry_id}`: "the faded notes closest to the one
      being read", built and tested, and there is nowhere in the app that
      reads a note. Checked before recommending anything: a note is a card
      in a list, and the only thing resembling a detail view is the inline
      edit form (`editingId`), which is a form. `lastOpenedEntryId` exists
      but only feeds the agent's "what am I looking at" subject. So this is
      a surface, not a wire-up, and probably why it was never wired.
      **Recommendation:** decide the surface first. The cheapest honest one
      is a row inside the edit form, under the tags, reusing
      `paintFadedNotes` from dashboard.js (the route returns the same
      `_card` shape the dashboard widget already renders); the better one
      is the note detail view this app does not have, which is a plan item
      rather than an INBOX item. **Built** (row 4's `#notes-rail`:
      `note-panels.js` calls `GET /resurface/near/{id}`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)").
    `POST /auth/rotate-vault-key` was on this list until the probe learned
    to read `` `/auth/${mode === "setup" ? "setup" : "unlock"}` ``; it is
    still uncalled, and re-keying the vault has no UI. Filed here rather
    than fixed: it is the one route in the app that rewrites every private
    note, and a button for it wants its own session. **Built 2026-10-05**
    (`settings-controls.js` calls `POST /auth/rotate-vault-key`, nbf1005; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)"); the other 261 lines are decided (nothing to do).

285 (indexless tool-call fragments) was fixed 2026-09-24 and moved to
HISTORY.md, "Moved from the plans, 2026-09-24".

283 (an absent OpenAI-dialect backend reported as running) was fixed
2026-09-24 and moved to HISTORY.md, "Moved from the plans, 2026-09-24".

## Placed from INBOX, 2026-09-21 (two app-wide contracts)

301. **The owner, 2026-09-21, verbatim:** "the application wide
    forward/backward navigation and undo/redo dont work for everything
    everywhere." Two app-wide contracts, both of which are the kind that
    cannot be fixed surface by surface without drifting again. Next step is
    an audit before any fix: every surface, what it pushes to history and
    what it makes undoable, as a table. Placed into WORLD_CLASS_PLAN.

**State 2026-09-24:** (c) the audit table (every surface, what it pushes to history, what it makes undoable) does not exist yet. M.

## Audio in the notebook: the architecture decided 2026-09-21, the build deferred

The owner, 2026-09-21, in one message: recording tracks and storing them as
notes or as objects like whiteboards and mind maps, attaching them to notes,
an audio library like voice memos paired with meeting notes, transcription
and perhaps live transcription, better text to speech, and separately a
background music player over a folder of songs he already owns. Then, in the
next breath: "idk if these are too big tasks though, maybe should be saved
for later??"

He is right on both counts, and both halves of that are recorded here so the
answer does not have to be found again.

**It is genuinely missing, and the code says so rather than being silent.**
`routes_files.py` line 56: video and audio "are still out (no player exists
for either yet; audio specifically is tracked as a gap)", and the upload path
refuses them at line 92 with "video and audio attachments aren't yet". So
this is a hole, not a rebuild, which for this project is worth stating
plainly.

**And it is too big for a session.** Audio as a first-class thing touches
storage, the upload allowlist, a new surface, attachment, search, and
probably an optional native helper for transcription. That is several
sessions. Nothing here is built until the owner says go. What follows is the
decision, so that when he does, the work starts at the first phase rather
than at this argument.

**Decision 1: two different features that must never share a store.** The
owner drew this line himself and it is the right one. Background music is
not notebook content: it is a player over files he already keeps, never
indexed, never searched, never a note, and nothing about it should ever
appear in a notebook view. Recorded audio is notebook content: a voice memo
is a thing he made, and it belongs with his notes. The separation is
structural rather than a flag on one kind, because a flag is how the two end
up confused, which is precisely what he asked to avoid.

**Decision 2: a recording is an object, not an attachment.** He asked
whether they could be "notes or objects like whiteboards and mindmaps".
Objects. A board and a map are already first-class things that can be
referenced from a note, and a recording behaves the same way: it has its own
identity, it can be opened on its own, and it can be pointed at from any
number of notes. Making it an attachment instead would bury it inside
whichever note happened to receive it first.

**Decision 3: it is not mp3, and it must not be called mp3.** A browser's
`MediaRecorder` produces webm or ogg carrying opus, and wav at best. Mp3
would mean shipping an encoder into the page. The feature is named for what
the recorder actually produces, and the word mp3 stays out of the interface
so nobody is promised a format the app does not make.

**Decision 4: transcription is optional and local, on the llama.cpp
precedent.** `scratchpad/llama-dev.sh` and `tests/test_skills_evals.py`
(2026-09-20) already establish how an optional native helper is allowed to
exist here: the suite never depends on it, no mode of `scripts/gate.sh`
reaches for it, and without its environment variables every test that needs
it skips at collection. Transcription follows that shape exactly or it does
not ship. The app ships with no model and that does not change.

**Decision 5: live transcription is a separate question from
transcription**, and is not promised alongside it. Transcribing a finished
recording and transcribing a stream are different problems with different
tools, and treating them as one feature is how the second one drags the
first.

**Phases, when the owner says go.** Each is a session's worth and each stands
alone, so the feature can stop after any of them and still be whole: the
recorder and the object, with the allowlist opened only as far as the object
needs; the audio library as a surface, with playback; references from notes,
using the machinery boards and maps already use; transcription behind the
optional-helper contract; then, and only then, the streaming question. The
background player is a separate row again, and its own open question is
whether the app may read a folder outside its data directory, which is with
the research agent now.

**Not decided, and his to make**: whether the offline promise admits an
explicitly opt-in online extra, which is what a connection to a streaming
music service would need. Recorded elsewhere as a pending decision.

**Research in flight**, not a commitment: whisper.cpp and vosk for speech to
text, piper and kokoro for speech, evaluated on licence and on cost against
this app's constraints. The evaluation is cheap and is worth having whether
or not any of it is ever built.

**State 2026-10-10:** go. The owner's 2026-10-10 list asks for all four (INBOX 759, decision taken by the orchestrator); 28.5 and Briefs 80 to 83 carry the work.

## 20. A model per feature (asked for directly, 2026-09-21)

The owner: *"also allow the user to alter the model they use for that
specific feature if they wish such as for the write with ai area, the chat
tab and document ai assistant. allow these to be easily individually altered
and reset and for there to be a mass reset for all individually altered ai
model preferences."*

Built 2026-09-21; the record is in HISTORY.md, "Moved from the plans". What
stays here is the decisions, because they are what the next feature row is
added against, and what is still open.

### Decisions made

1. **A second layer over the roles, not a replacement for them.**
   `ai/model_manager.py` already has chat, utility, vision, ocr and embedding
   roles. A feature override resolves to the feature's own model if one is
   set and to the role it belongs to otherwise. One table, `FEATURES`, maps
   each feature key to its role, and one seam, `for_feature(key)`, hands back
   a manager view whose `chat_model()` / `utility_model()` answer for that
   feature. A new feature is a row in that table, not a new setting, a new
   route and a new control.
2. **The first pass is four rows**: the Chat tab, the writing desk (Write
   with Atlas), the documents AI assistant and the Guide. The Guide is in
   because it is the same shape exactly, one surface, one model call, one
   role to fall back to. **The skills runner is deliberately out**: a skill
   run goes through `agent.run_agent` on `chat_model()`, the same loop the
   chat tab's agent mode uses, so a "skills" row would have moved only
   `skill_runner._replan`'s small recovery call and left the model that runs
   every step where it was. Giving skills a model of their own means giving
   `run_agent` a feature to run under, which belongs in AGENT_SKILLS_REFORM.
3. **Settings is the canonical place**, because that is where a mass reset
   makes sense: one list, a row per feature naming the model and whether it
   is inherited, a per-row reset live only while that row is overridden, and
   one reset for all of them that says how many it would clear.
4. **Each surface also gets the picker in the menu it already has**, never a
   new control in its chrome: the Chat tab's `kebabMenu`, the writing desk's
   `details.dock-menu`, the documents editor's `details.dock-menu`. One
   `openSheet` behind all three, so the wording cannot drift.
5. **An unset feature stores absence, never the resolved name**, and resolves
   through its role at read time. Storing the name would look identical on
   the day it was written and then silently leave every untouched feature
   behind the first time the chat model is changed in Settings.
6. **The sub-tab is "Write with Atlas."** The tab button said "Write with AI"
   while the heading of the panel it opens already said "Write with Atlas",
   so the app contradicted itself on one screen.

### Still open

- **The feature list is inside `#models-config`**, which Settings hides whole
  when no backend is answering. So with the model server down there is no way
  to see or clear a feature override, and the app's own "no model" advice is
  what shows instead. Defensible (every other model picker is in there too)
  but worth revisiting if anyone reports it.
- **The Guide's row is the answer to INBOX 288 but not to its cause.** Smart
  model routing off silently moves the Guide, an interactive panel, onto the
  chat model, because the switch is written for background jobs. Either the
  switch's copy should say which surfaces it moves, or the Guide should stop
  being one of them. **Decided by the owner 2026-09-24: the Guide stays on
  the utility model whatever the switch says** (`utility_resolution`,
  `test_with_smart_routing_off_the_guide_keeps_the_utility_model`).
- **A per-feature model is shown on the Chat tab and nowhere else.** The
  chat pill (`#chat-active-model`) reads the pinned model now, but the
  writing desk and the documents assistant say which model they are on only
  inside their own menus. Neither has a pill to put it in, so this is a
  design question (does a writing desk want a model badge in its dock?)
  rather than an oversight.

**State 2026-09-24:** (c) three open questions, each a decision rather than built work; none has been reported since.

## 21. Every failure names its way out (INBOX 272 part 1, 2026-09-21)

The owner, verbatim: "make sure all features and alternatives are easily
knoticable by and offered for the user. like if the embedding model fails
or has an error, it suggests to download nomic-embed-text. if duck duck go
is rate limiting it automatically tries searxng and if it isnt installed it
suggests it. and same for many other instances." INBOX 272 called this a class; the survey, its fourteen rows and the
record of rows 9 to 11 built on 2026-09-21 moved to HISTORY.md, "Moved from the plans, 2026-09-24". The lint
that holds it is `tests/test_failure_remedies.py`.

State 2026-10-05: what the survey left open (rows 1, 2, 12 and 13) is
built; moved to HISTORY.md, "Moved from the plans, 2026-10-05 (nbf1005)".

## 22. The professional baseline and the devibecode programme (2026-09-27)

The owner, verbatim: "poke holes in the app. find issues, both really large
scale, not necessarily bugs, and small. things that every professional app
has and people expect to just be there ... Identify areas where the design
isnt up to the standard it should be. make a plan to further devibecode each
interface and panel and make full use of multiple and all of your available
ui/ux and web design skills". Decided the same day: **desktop first, and the
desktop that matters is a small uni laptop** (1366x768 at 125% scaling, which
leaves 1093x614 CSS px, and 1280x720), then tablets; CSS is still written
mobile first, as the owner's web design class teaches. Measured with
`scratchpad/proprobe.js` (session scratchpad) at 1093x614@1.25, 1280x720 and
1536x864@1.25.

### 22.1 Large gaps (what every professional app has)

1. ~~**No URLs.**~~ **Built:** `router.js` gives every view a hash (`#/notes/12`, `#/chat/45`, `#/docs/7`, `#/library/images`, `#/settings/appearance`), the in-app Back and Forward run on `popstate`, a reload restores the view and the window title names it (HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)").
2. **The laptop screen is mostly chrome.** At 1093x614 the top bar (72px),
   sub-tabs (55), the list toolbar (55) and the status bar (37) take about
   36% of the height: the Notes list shows 2.3 cards and the Dashboard's
   widgets start below the fold. Target: a height-aware density (Compact
   applied by default under 700px of height, with the setting still in
   Appearance), sub-tabs merged into the list toolbar where a surface has
   both, and the status bar folding into the top bar under 680px. Gate: 4
   note cards and the first dashboard widget above the fold at 1093x614. M,
   Opus.
3. **Tabs lose their names on a laptop.** Under about 1100px the tab strip
   is icons only with the active tab labelled, so six of seven tabs are
   guesses. Target: short labels kept down to 1024px (the strip has room once
   the spaces picker shrinks to an icon), tooltips with the shortcut below
   it, and the strip centred (INBOX 430). S, Sonnet.
4. **Leaving with unsaved work.** Built 2026-09-27 for the note edit form,
   the Capture box and a document mid-autosave, the three surfaces with a
   plain dirty flag (HISTORY.md, "Moved from the plans, 2026-09-27"), and a
   chat mid-stream (2026-10-11, `chatMidStream`). Left: a board mid-drag, which
   has no such flag yet. S, Sonnet.
5. **Two windows, one note.** Built 2026-09-27 for the note edit form and
   the document editor (HISTORY.md, "Moved from the plans, 2026-09-27").
   Left: the other note writers (a card's checkbox, the graph's tag edit,
   the lightbox caption) send no `base_hash` yet and stay unchecked. S,
   Sonnet.
6. **The server can go away.** Built 2026-09-27: a persistent banner
   ("Can't reach MemoryMap. Retrying...") with a Retry action, raised by
   `api()`'s own network-error catch and cleared by the next successful
   request or a backoff poll against `/health` (HISTORY.md, "Moved from the
   plans, 2026-09-27"). Left: queuing or refusing a write with the same
   message while it is up. S, Sonnet.
7. ~~**No screen-reader pass, ever.**~~ **Built apart from a real screen reader:** one `<main id="app-main">` (was three), the axe-core sweep (`scratchpad/ui-sweeps/axe.js`, run by `all.sh` when axe-core is at `AXE_JS`; 0 findings at 1440 in both themes), the main landmark, separator values and editor names fixed by it (HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)"). **Not verified:** no session has driven the app with an actual screen reader.
8. **Data safety is there but hidden.** Backups exist
   (`routes_backups.py`), revisions exist (`EntryRevision`), export exists,
   but none is on the Dashboard or in the note menu as "Version history",
   "Export", "Back up now". Target: version history in every note and
   document menu with a diff, a "Last backup" line in Settings and on the
   About page, and a first-run prompt to choose a backup folder. M, Opus.
9. ~~**Offline promise, visible.**~~ Built 2026-10-11 (row 1641): the Local chip; HISTORY.md, "Moved from the plans, 2026-10-11 (rows agent)".

### 22.2 Small things people expect (each S, Sonnet unless noted)

- The window title names the view and the open item (22.1.1).
- Ctrl+S, Ctrl+Z and Escape behave the same in every editor and dialog
  (the key contract, 1.6, has no lint for Escape yet).
- Search highlights the match inside the note it opens, and remembers the
  last few queries.
- Every destructive action has an Undo toast, not only deletes of notes.
- Every date and time follows one setting (12 or 24 hour, the locale's
  order); the status bar clock, the timeline and the reminders do not agree
  today on whether seconds show.
- Drag and drop of files onto any page imports them (Library only today).
- Every list with more than 20 rows can be filtered by typing.
- Right-click works on every card and row, with a hold as its twin on touch.
- A "Copy diagnostics" button on the About page (versions, model, recent
  errors) for bug reports from test users.
- The status bar's "!" dot says what it means on hover and click.
- The "Default Space" chip is hidden when only one space exists (it is on
  every card today and says nothing).

### 22.3 Where the design is below standard (measured or seen, 2026-09-27)

- **Density and rhythm.** Cards carry 24px of padding and 17px body text at
  every width; on a laptop the list reads like a phone app scaled up.
- **Hierarchy in Settings.** Section heads are the same weight as labels
  (in the Sonnet batch).
- **Icon consistency.** Mixed stroke weights between Phosphor regular and
  the bold ones on the status bar; one weight app-wide.
- **Empty states.** The Chats sidebar's empty text is body size and grey on
  grey; empty states should use one recipe (icon, one line, one action).
- **Toasts** overlap content (the reminder toast covers the dashboard head
  at 1093x614); they belong in a reserved corner above the status bar.
- **Glass** is still on some surfaces the performance plan listed for
  removal; the glass-off list lint should cover every blurred surface.

### 22.4 The devibecode programme: one surface at a time, every skill

Each pass takes one surface through the same seven steps, so no surface is
"done" by a different standard:

1. **Audit** with `unslop-ui` (the AI-tells checklist) and
   `web-design-guidelines` (Vercel's interface guidelines), writing each
   finding with its selector.
2. **Research** the surface type in the vendored `ui-ux-pro-max` corpus
   (`python .claude/skills/ui-ux-pro-max/scripts/search.py "<surface>" --domain ux`
   and `--domain style`), and in `apple-design` for its motion and sheets.
3. **Tokens** through `design-system`: every value on the surface resolves
   to a token; new ones are added to DESIGN.md with their lint.
4. **Design** with `frontend-design` for the direction, inside DESIGN.md's
   recipes (standing order 11).
5. **Measure** at the laptop matrix (1093x614@1.25, 1280x720, 1366x768,
   1536x864@1.25, 1920x1080) and tablets (1024x768, 820x1180), light and
   dark, reduced motion on and off, with errors.js, contrast.js, touch.js
   and a surface sweep.
6. **Shots** before and after, in the report, for the owner to judge.
7. **Owner review**, then the next surface.

Order, by how often the owner is on it: the shell (D15, with 22.1.1 to 3),
Notes (D2), the Dashboard (D1), Chat (D3), Settings (D13), Library (D4),
Documents (D10), the Graph (D12), the Whiteboard and maps (D11), the
Timeline (D7), Reminders (D8), Help and the palette (D14), the companion
and Atlas (continuous). Opus for each design pass; Sonnet for the
measured follow-ups it lists.

### 22.5 Where the app goes next (release path)

Versions follow semantic versioning before 1.0: a patch (0.3.x) for fixes,
a minor (0.x.0) for a set of new features, and a number changes only when a
release is published, however many commits land between. So the pace is
not too fast; the rule is simply one number per published release.

- **0.3.x (now):** finish INBOX 430, green CI, the full suite, then publish.
- **0.4.0, "laptop perfect":** 22.1 items 1 to 6, and the devibecode
  programme through the shell, Notes, Dashboard, Chat and Settings.
- **0.5.0, "the notebook that thinks":** the night shift's review UI, the
  margin reader (I2), open questions (I3), resurfacing (I4), the web
  clipper's frontend, AI templates everywhere.
- **0.6.0, "many devices":** LAN polish for tablets, local-first sync
  design (B6) made real, extensions (B8).
- **1.0.0:** a stable API (B7), a screen-reader-audited UI, the installer
  and update path proven on clean Windows machines, and the docs complete.

## Placed from INBOX, 2026-09-27 (399)

399. **The owner, 2026-09-23 night, verbatim.** "what is left in the world
    class plan?? can you poke more holes in the application for bugs,
    security, poor learnaility/utility/usability/accessibility and more??
    make sure everything works on the windows packaged installer and the
    version it installs. make sure all the update features in the about
    settings page as well as the auto updates in the bat and sh files work.
    keep design consistent, expand professional and modern design. maximise
    usability and learnability. poke holes in the application as in find
    bugs, security flaws places where there is unintuitive design, poor
    information architecture, poor design, poor ui and ux, poor
    learnability/usability/heirarchy/spacing and more. hit the open items and
    plans in open.md. finish all unfinished work. majorly optimise at the
    level of professional applications. make everything feel like it is a
    professional application and not just a demo. maximise use of affordances
    and semiotics. look at websites like motion.dev for ui and component
    refinement, bklit.ui, kokonut ui etc so make sure none of the ui elements
    are unprofessionally designed or act in a wierd way. ... dont let my
    additions distract you, add them to the list and continue, never leave
    anything half finished, not properly done, or untouched."
    Placed as four agent briefs, run as slots free: (1) WORLD_CLASS_PLAN
    rows not built, grepped first, with the list reported back; (2) a hole
    poke (bugs, security, a11y, IA, spacing) with a finding table and fixes;
    (3) the Windows installer, the installed version and the update paths
    (About's updater, `start-*.bat`/`.sh` auto-update), tested in a scratch
    copy per CLAUDE.md's trap; (4) component refinement against motion.dev,
    kokonut and bklit patterns (motion, hover, focus, press states).
    Part (4) built c3bbefc: every transition on `--motion-*` and `--ease-*`
    (`tests/test_motion_tokens.py`), a hover is a colour never a filter
    (with INBOX 405), toasts and '?' popovers fade in with 4px of travel,
    toasts fade out, skeletons in the Library and Timeline. Menus' exit left
    to the menu agent (archive/agent-remaining/perfpolish.md).

## Placed from INBOX, 2026-10-03 (INBOX 403, the standing bar)

Moved whole from INBOX when INBOX 435 arrived (the tray holds under
twenty). It is the bar every pass in this plan is measured against.

403. **The owner, 2026-09-23 night, verbatim.** "for me, trust in the
    application isn't just the information it shows but that is very much a
    key point, it is also how cleanly and professionally the application ui
    is designed and works. the less professional or unclean any part of the
    ui is, no matter how small, I instantly doubt the applicationa dn wonder
    if it is worth putting any time into as it feels unreliable. things like
    having that small gap between the edge of the note connection pill chips
    on the right and the 'x' delete button, as well as poorly designed
    dropdown menus with bd widths, poor spacing, poor alignment, poor
    heirarchy, positioning, poor learnability, not intuitive controls poor
    information architecture and more. keep doing what you are doing" The
    standing bar for every pass (INBOX 399's hole-poke and refinement briefs
    carry it). Named: the connection pill's x inset, orchestrator; menus
    (widths, spacing, alignment), a sweep of every menu for width, padding
    and row alignment.

## Placed from INBOX, 2026-10-03 (INBOX 391, 392)

391. **The owner, 2026-09-23, with the Gemini/Antigravity pass on
    `fix/gemini-fixes-5` (1e63d87, 2c3e16e): "fix and refine the changes
    attempted by gemini ... fix the ui, fix the ux, fix bugs, revert and refine
    risky or bad changes, implement the attempted fixes and improvements but
    better."** Reports in the same drop, and where each stands on this branch:
    packaged-exe splash (fixed: bootloader Splash); installer optional packages
    (fixed: `--install-extras`, frozen `--target` folder); `ModuleNotFoundError`
    traceback and no nomic-embed-text suggestion (fixed); Notes dock and
    dashboard tiles wrapping at 100% (fixed, measured at 1184); edit scrolls to
    top and blank Notes page on first edit (fixed: `applyDocGutter` lazy entry
    point); 29/30/31 notes (fixed: drafts out of every count); no select all
    (fixed, one toggle per bar); table cells in live view (fixed, focus kept);
    whiteboard undo for formatting and map styles (fixed); mind maps missing from
    Find anything, weekly digest filler and "tonight", per-feature model
    picker, agent activity panel alignment, image filter sketches/uploads,
    notification when a closed panel's answer finishes (agents running).
    Decisions, taken 2026-09-23 with the owner: **no fine-tuned bundled model**
    (the owner agreed: a stock small instruct model plus this app's prompts is
    cheaper to keep current; revisit only with an eval set that shows a gap).
    **Laya** (Convai's open-weight decision model, the open alternative to
    Jev: ModernBERT-large, 421M params, Apache 2.0 so AGPL-compatible, typed
    choice/score/boolean outputs with probabilities) **is not adopted now**,
    for three measured reasons from the published benchmarks: zero-shot it
    scores below a plain baseline (0.362 vs 0.461) and only wins after
    per-domain fine-tuning, which this app cannot do for each person's own
    categories; it degrades past about 20 labels (0.425 on Banking77's 77),
    and notebooks grow past that; its context is 512 tokens, shorter than many
    notes. Filing stays on embeddings plus the chat model. Where it could earn
    a place later: small fixed-choice decisions (intent routing in chat, "is
    this a reminder") as an optional extra on the same torch install as
    search by meaning, gated on an eval set showing it beats the current
    prompt on those questions.

392. **The owner, 2026-09-23, verbatim, for after 391:** "poke holes in the
    application as in find bugs, security flaws places where there is
    unintuitive design, poor information architecture, poor design, poor ui and
    ux, poor learnability/usability/heirarchy/spacing and more. hit the open
    items and plans in open.md. finish all unfinished work. majorly optimise at
    the level of professional applications. make everything feel like it is a
    professional application and not just a demo. maximise use of affordances
    and semiotics. look at websites like motion.dev for ui and component
    refinement, bklit.ui, kokonut ui etc so make sure none of the ui elements are
    unprofessionally designed or act in a wierd way. I have found the mind map
    is very unintuitive to use, really slow to pan and move around, the controls
    and tools are annoying to find and use, the connections in the bottom bar
    are different from the ones the mind map nodes use and it just needs a
    whole professional refinement. same with the code mirror live view in the
    documents editor, the live view needs a lot better md rendering and it is
    hard to edit things like tables and other elements and it could look a lot
    nicer rendered, and usability ux could be improved. also the code document
    types dont act like a code editor with errors, suggestions and that needs to
    be imporved. indenting and dedenting across the app also doesnt come in the
    form it should." Placement: the mind map half joins MINDMAP_PLAN row
    13a-view (INBOX 312's pan cost) plus a connector-parity row (the bottom
    bar's link tools must draw what map edges draw); live view and code
    diagnostics join DOCUMENTS_PLAN; indent/dedent (Tab/Shift+Tab on list
    items and selections in every text surface) is a WORLD_CLASS_PLAN
    consistency rule with a lint. Added the same hour, verbatim: "also for
    after, the mobile view is still bery broken, takes up a lot of the screen
    and the design needs a lot of improvement." Placement: UI_MODERNISATION_PLAN
    phone phases; measure chrome height against content at 390x844 first.
    That half is built (2026-09-23): UI_MODERNISATION_PLAN Phase 11 item 12,
    gated by `scratchpad/ui-sweeps/phonechrome.js` at 390, 768 and 1024.
    Later the same day, verbatim: "make sure the whole of the app ui is
    repsponsive, not just for mobile but any ui resolution. though mobile-first
    design is I'm told a good practice" and "when I say mobile and responsive
    design, I mean actually intentionally deisgning for those resolutions, and
    not just adapting to them. like actually making the features be intended
    and designed for those resolutions" (phone agent briefed: a phone intent
    per surface, tablet widths swept too), with slides asking the software to
    reduce CPU, RAM, network and storage (standing: measure before claiming,
    as the pan trace did). Also reported and fixed on the branch: the mind map
    label drag drifting and starting a selection box; the chat header naming
    llama3.2 while another model answered; no prompt when search by meaning
    failed; a picture captioned and read several times over.

## Placed from INBOX, 2026-10-03 (the tray at its cap)

Open, moved whole from INBOX so the tray stays under twenty; each is worked from here by impact.

410. **The owner, 2026-09-24, verbatim, with screenshots of the writing
    dictionary, New from a template, the map's radial menus and two linked
    map nodes.** "also improve how the \"check with ai\" feature works in the
    documents editor, allow the suggestions panel to be docked on the right
    instead if the user wishes and redesign the dictionary panel as it is
    ugly and needs a proper professional modern redesign." "also when
    selecting a template, I want to be able to confirm my template
    selection, not have it instantly be made when I press it" "is there a
    way to make these mind map item radial options fit better in the
    radials?? also what if the user asks the guide for all the hidden
    features, keybinds, controls, utility and more for features like the
    whiteboard, mindmap and documents editor etc. can it answer those??"
    "also fix the ci and codeql errors" "when I relink or newly link two
    mindmap nodes, they clump together??" "drag selection on the whiteboard
    and mindmap is laggy as well". Read from the screenshots: the radial's
    labelled pills overhang the ring (a 2-item edge ring and the 6-item node
    ring both); a relinked node lands on top of its new parent instead of
    being laid out as its child. CI: four routing rows fixed 2026-09-24 (three
    moved to topics added that day, "Can Atlas write for me?" gets a new
    write-with-atlas topic). Placed: documents (check with AI, dockable
    suggestions, dictionary), templates (confirm), the Guide's per-surface
    controls reference, map (radial fit, relink layout, marquee lag), in
    agent briefs as slots free.
    **Templates (confirm) built 2026-09-24** (bf54953): a click chooses,
    Use this template, Enter or a double click makes it; sweep
    `templatepick.js`. 
    **The Guide's part built 2026-09-24** (guide-controls agent): a controls
    reference per surface and a hidden features entry, routed by what the
    question asks c05c684; 55 bank questions (177, top-1 99.4%, top-3 100%)
    1385b0e; a freshness test against every bound key a164dc2; the caps
    (a 422 after a long answer and on the fifth question, the reply cut
    mid-list) 5cb7f8f. Map part built (radial fit 13c41d7, relink b449623, marquee 18b8c15).
    **The documents' part built 2026-09-24** (the documents agent): Check
    with AI runs in place, streamed into the suggestions panel with Apply,
    Dismiss and Stop, a no-model notice with Settings, Models, and Discuss in
    chat with no long prompt (so no skill nudge, the INBOX 413 half)
    (cd5dec1, `aicheck.js`); the panel docks at the bottom or on the right,
    resizable, remembered, always bottom at 720px and below (a8c822a,
    `prosedock.js`); the dictionary as a settings sheet (bbeda8e,
    `dictsheet.js`); the Capture box's templates confirm too (26e8d9b,
    `notetemplatepick.js`). Nothing of 410 is open now; it stays for the
    orchestrator to resolve with 413.

421. **The owner, 2026-09-24, verbatim, with screenshots (placed in agent
    briefs, two at a time).** (a) "in the radials on the mind map, the items
    like "add beside" and "cross-link" are very close to the edges (inner and
    outer) of the radial and arent centered nicely. also when I press the
    more button the dropdown menu appears in the top left of my screen"
    (desktop app; the pie-ring agent could not reproduce the corner with a
    real click). **(a) built** (INBOX 421 agent): labels centred with 10px to
    both arcs and dividers (1.4 -> 11.4px, mapradialfit.js); More anchors to
    the sector read at pointerdown, (0,0) refused and logged, the canvas host
    no longer scrolls on focus (mapradialmore.js 33/33). The desktop corner
    itself was still not reproduced headless: the console now names any
    corner placement, so the owner's log will say which route it was. (b) "the / command blocks and frames need a massive
    redesign, expansion and improvement, the icons dont render in the live
    view in the documents editor ... they need ot be impressive and an actual
    proper thing the user's can use to properly structure out their
    documents and notes." (live-view callout icon fixed 6e072b2; built
    2026-09-24: the grouped block inserter, 14 callout kinds, columns in
    notes, contents, rules, cited quotes, maths, the block bar and document
    cards, `slashmenu.js`, `blocksrender.js`, `blockbar.js`.) (c)
    "sometimes document editor dropdowns appear at the top of the screen and
    other times it is fine, sometimes it doesnt open at all" (the spelling
    menu, top of the window; fixed 2026-09-24: placed from the
    finding, never a detached element's empty box; the double-click's first
    press; the "/" menu follows a scroll; `menuanchor.js` 15/15). (d) "there's no 'x' close button on the trace
    popup row in the graph" (**built**: an X at the strip's end that leaves
    trace mode; Done only cleared the ends; graphtraceclose.js). (e) OCR: "I cant delete the ocr entry in the
    workspace or the lightbox and the text in the lightbox doesnt even appear
    in the ocr workspace" (workspace delete fixed 6e072b2; the lightbox
    showed a vision reading of "Test, Test, ..." hundreds of times, a
    degenerate model loop the app should cut; **built**: loops cut where a
    reading is produced, each lightbox reading deletable, the workspace shows
    both stored readings and no longer blanks a stored one when the reader
    is the model; ocrreadings.js 6/6). (f) The file row in the
    Library ("PDF · 121 KB · added ... Read · 808 words, Open reader, Used
    in"): "needs a bit more modern and ui refinement and the second row
    elements arent aligned and dont really match" (fixed: one size, one
    line box, middot groups, "Read this" a link). (g) "the lightbox buttons
    below the image are greyed out?? i opened the image from within a note".
    (**built**: not disabled, the row was the theme's ghost ink on the dark
    scrim, 1.37:1 in light from every door; now the scrim's own recipe,
    8.28:1; lightboxentry.js) (h) View toggles with no clear active state (fixed c920174). (i) "have
    you included all the new optional packages in the packages settings
    page??" and "move the preferences settings page up a bit and maybe also
    turn it a bit into the user's own personal local profile where they can
    put info about themselves and their name for the ai to use as context
    and there can also be the generated profile image". (j) "I clicked a note
    linked in the sources of an ai chat reply and it took me to that note,
    but when I pressed the back navigation button it opened the settings
    panel??" (not reproduced: chat then flashEntry then Back lands on chat,
    also with chat opened from inside Settings; needs the exact path).

423. **Found, not fixed, by the agents of 2026-09-24 (placed for the next
    pass; one line each, recommendation first).** (a) The mind map's pie
    ring does not take focus when it opens, so Enter and the arrows still
    act on the board while it shows: recommend it takes focus when opened
    from the keyboard only. (b) DOCX export writes `:::columns`, `[TOC]` and
    `[!kind]` as plain text: map them to Word columns, a TOC field and a
    shaded box. (c) Inline `$x$` maths is plain symbols in Read view: render
    it through the same TeX-to-MathML path as `$$`. (fixed: `INLINE_MATH_RE`
    (app.js) now claims a `$…$` span with no space inside either delimiter
    and no digit right after the close; `unlatex` carries it through
    untouched instead of symbol-swapping it, and `renderInlineMarkdown` cuts
    it out and draws it with `mdInlineMathElement`, the same `docMathRender`
    the `$$` blocks use. `tests/test_inline_math.py`.) (d) The OCR workspace's
    message for a vision reading still suggests installing Tesseract: word
    it by reader. (fixed: `_regions_for` (routes_files.py) checks
    `ocr.tesseract_available()` before wording the "no page positions"
    message; installed but not chosen now says "Switch to Tesseract", missing
    still says "Install Tesseract". `tests/test_ocr_regions.py`.) (e) At
    150% zoom the lightbox picture overlaps its caption
    line. (f) Stored readings that already contain a repeated-line loop are
    not cleaned: offer "Clean up" in the reading menu. (fixed: a broom
    button beside Delete reading, in the OCR workspace and the lightbox's
    other-readings list, POSTs `/files/{id}/ocr-clean-loops` or
    `/media/{id}/ocr-clean-loops`, which runs `cut_reading_loops` over
    whichever of `vision_ocr_text`/`ocr_text` are set and saves what
    changed; the panel repaints from the response. `tests/test_ocr_clean_loops.py`,
    live-checked with `scratchpad/ui-sweeps/ocrcleanloops.js`.) (g) `_desktop_port()` took any Tessellate on the port for this one: built
    (HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)", 423(g)). (h) Chat replies saved before
    2026-09-24 always show Atlas's mark (their persona was never stored).
    (i) The server-mode process takes 5 to 9s to exit after uvicorn
    finishes: find the thread that holds it. (fixed: every sync route
    (almost all of them) runs on one of anyio's own "AnyIO worker thread"
    objects, which is not a daemon thread and only stops itself on a
    done-callback that can miss `uvicorn.run()` tearing the loop down;
    measured leaving one alive, `daemon=False`, right after "Finished
    server process". `_stop_lingering_worker_threads` (`__main__.py`,
    called right after `uvicorn.run()` returns) asks it to stop and bounds
    the wait to 1s. `tests/test_server_shutdown.py` reproduces the leftover
    thread with a real `uvicorn.Server` running `create_app()` and checks
    the fix clears it.)
    (j) `gate.sh --sweeps` on 25d7d56 (fixture data dir /tmp/mm-me):
    asktab.js 3 findings, libreadingfoot.js "reading visible: false" and
    "no card with a reading", tagoffer.js 2 failures (manual route and the
    empty tag row flag). Triage each as app bug or stale sweep before
    fixing; the reader's 36px page box is fixed (25d7d56).

424. **Audit of 2026-09-24 (performance measured in Playwright on a
    400-note, 1,200-link, 250-object board, 120-topic map, 30-image
    fixture, at 1440x900, 1x and 4x CPU with CDP profiles; UX walked at
    1440 and 390). Fixed in this pass: the media poll outliving the
    Library, the outline rebuilt per typing pause (515ms to 12ms), the
    avatar follow frame's document-wide query (279ms to 20ms per 60 moves),
    the unnamed "Toggle Sidebar" button. Open, one line each: measurement,
    cause, recommendation.**
    (a) Board, dragging a multi-selection: 44 long tasks, 8.6s of them for
    40 moves at 4x (max 560ms); `objDragMove` calls `wbUpdateSelectionBar`
    every move, and `wbItemBBox` runs a document-wide
    `querySelector('.node-card[data-id=...]')` per item (2.6s); recommend an
    id-to-element map from the render pass and the bar updated once a frame.
    (fixed: `objDragMove` 5,167ms → 167ms, profile busy 6.1s → 1.0s, longest
    task 901ms → 213ms, same harness and fixture at 4x; element cache in
    `wbItemBBox`, the bar queued once a frame, the chrome groups found once
    per gesture, the editing check scoped to the board. Bar position mid-drag
    identical to base over 10 moves, `perf5/barcheck.js`.) Still open on the
    board, a pan: a devtools.timeline trace of 40 moves at 4x is 43 long
    tasks, 3.5s, of which `Layerize` is 2.4s and script 0.2s; it stays with
    the grid sync, the cull, the bar, the navigator and both SVG transforms
    switched off (`perf5/pantrace.js` VARIANT), so it is the compositor's
    layer assignment of ~250 painted objects per frame, not a handler.
    (fixed 2026-09-26: the objects were not the cause, their grips were.
    Nine per card, invisible but in the tree, each scaled by
    `--wb-inv-zoom`, split the board into 256 layers; `display: none` at
    rest gives 138. Two runs each at 4x, 40 moves, `gwperf.js`: long tasks
    33/38 (2.5/2.7s) to 2/2 (136ms), `Layerize` 1.8/1.7s to 0.34/0.35s,
    median frame 67/50 to 17/17ms; the zoom's long tasks 2.0s to 0.5s.
    Grips on hover and selection unchanged, fade kept, `wbpanlayers.js` 6/6,
    3/6 on base.)
    (b) Graph node drag at 4x: 137 long tasks, every frame over 33ms (max
    550ms); `graphMinimapPaint` rebuilds the minimap's SVG on every worker
    tick (1.56s of `createElementNS`/`setAttribute`/`replaceChildren`);
    recommend painting the minimap to a canvas, at most once a frame.
    (fixed: `graphMinimapPaint` 1,502ms → 514ms, profile busy 3.6s → 2.0s
    for the same 40-move drag at 4x; the ticks queue one paint a frame, the
    paint moves the existing dots and lines and skips unchanged attributes,
    and a minimap that is off, on a hidden tab or in a hidden window is not
    painted. Kept as SVG: the sweeps count its circles. Dots, lines and
    positions identical to base, `perf5/minicheck.js`, `minimap6b.js`.)
    (c) Graph wheel zoom at 4x: 31 long tasks, 13.7s, p95 frame 583ms;
    `gcDraw` re-measures every label (`measureText` 152ms) per frame;
    recommend caching label widths per node and font size.
    (fixed: `measureText` 165ms → 0 over 16 wheel steps at 4x; a label is
    measured once per text at a reference size and scaled with the zoom,
    dropped when the font changes.)
    (d) Graph tab switch at 1x: 25 long tasks, 1.6s, 50 of 59 frames over
    33ms; each visit refetches `/graph` and restarts the layout, and
    idle on Graph at 4x is still 3.7s of main-thread work per 10s
    (worker ticks plus minimap); recommend reusing the last settled layout
    when the notes' version has not changed.
    (fixed for the layout, not the fetch: main-thread task time in the 12s
    after a revisit at 4x 6,746ms → 1,382ms; a layout whose inputs, pins,
    lines, forces and world match the last one to settle, with every note
    where it left off, starts at rest and is framed as before; any change of
    input heats it as before. Idle once settled was already ~5ms per 2s: the
    cost was the re-settle. Still refetched each visit.)
    (e) Mind map expand of the root (120 topics) at 4x: one 1,336ms task;
    `renderWbObjects` rebuilds every node through `wbBuildMapNode`
    (`setAttribute` 354ms); recommend keyed updates so an expand only
    builds the nodes it reveals.
    (fixed: the join was already keyed, so an expand of the root does reveal
    all 119; what it no longer does is build them. A folded topic's element
    is kept and taken back, for the same datum only. Two runs each at 4x:
    longest task 899/1,115ms → 597/442ms, profile busy 781/1,016ms →
    456/319ms, `wbBuildMapNode` 321/419ms → 0. Markup after a fold round
    trip identical to base apart from attribute order, and a taken-back
    topic's chevron still folds it, `perf5/mapreuse.js`.)
    (f) Lightbox next/previous at 4x: 13 long tasks for 5 presses (p95
    350ms); `show` calls `applyZoom`, which calls `scrollTo` (375ms of
    forced layout) even when already at fit; recommend scrolling only when
    the zoom actually changed.
    (fixed: `show` 457/360ms → 37/28ms and `scrollTo` 406/305ms → 0 over
    five presses at 4x, two runs each; profile busy 580/465ms → 128/118ms.
    Fit scrolls only a scroller its own scroll events, or a pan, say is off
    its origin, so a PDF read halfway down still goes back to the top.
    `lightboxfit.js` 42/42 on both.)
    (g) Library tab switch at 1x: 10 long tasks, 580ms (4x: 3.4s, max
    683ms); `loadLibrary` refetches `/library` and rebuilds every card each
    visit; recommend the same version check as (d).
    (open, needs a decision: skipping the rebuild when `/library` answers
    the same would also keep the selection, which a reload clears on
    purpose, and leave relative dates as they were drawn. Recommend: keep
    the cards on screen during the refetch, skip the rebuild when the answer
    is identical, and clear the selection either way.) (Fixed with that
    recommendation: an identical answer drawn under five minutes ago is not
    redrawn unless something is selected; 189 grid mutations over three
    revisits before, 0 after.)
    (h) Every tab switch at 4x: `revealTab` 70 to 110ms self time, mostly
    `querySelectorAll("textarea.autogrow")` then `autoGrow` on each visible
    one (forced layout per box); recommend autogrowing only the new tab's
    boxes.
    (fixed, the autogrow part: every check is read in one pass and only a box
    measured while hidden, or whose text, width, font or cap changed, is
    grown; 0 to 12ms per switch. Not the 70 to 110ms: split step by step
    (`perf5/revealsplit2.js`, 14 switches at 4x) it is `button.tabIndex =`
    796ms, which forces the style recalc of the page just shown, then 203ms
    of its layout; autogrow was 30ms of revealTab's 1,318ms. That is the new
    tab's own style and layout, forced early, and moving it was measured to
    gain nothing (the note on `revealActiveTab`).)
    (i) Typing in a note at 4x: 56 of 204 frames over 33ms; each keystroke
    mirrors the editor into the hidden textarea and dispatches `input`,
    which runs `autoGrow` (448ms self) on a box nobody sees; recommend
    skipping autogrow for a box whose editor is mounted.
    (fixed: `autoGrow` 492/532ms → 16/17ms over the 50-character run at 4x,
    profile busy 2,448/2,790ms → 1,874/1,713ms. The mirror is left to the
    stylesheet's `height: 100%`, which an old inline height had overridden:
    measured after 14 lines, base mirror 315px under a 398px editor, now
    398px; the editor and its box are unchanged, `perf5/capcheck.js`.)
    (j) The brand emblem's p5 loop draws at 24fps on every tab while idle
    (`_draw` about 70ms per 8s at 1x on Dashboard and Chat, and it shows up
    inside every drag profile); recommend pausing it after a few seconds
    without input, as the mood timer already tracks.
    (already fixed by b944d2c, which the audit's worktree predates: the
    emblem is drawn once and turned by CSS. Measured on this head, 8s idle
    at 1x: 0ms of script on Dashboard and Chat, `perf5/idleprof.js`.)
    (k) Library shows at most 200 of each kind (`PER_KIND_LIMIT`,
    routes_library.py) and its chip counts are the count returned: with 400
    notes the chip reads "Notes 198", and a plain Library search for the
    oldest note ("Note 17 summary") says "Nothing matching" while
    `/entries?q=` finds it; recommend true counts and a server search (or
    paging) once a kind passes the cap. (Fixed: counts and the overview
    are real totals, `truncated` names the cut kinds, `/library?q=` matches
    before the cut and the client swaps those kinds in while searching; a
    line under the grid says "Showing the newest 186 of 339 notes. Search
    to reach the rest." Measured on 339 notes: the chip reads 339, a search
    for the oldest note finds it. Test in tests/test_library.py.)
    (l) Settings: 18 sections in 4 groups; "Profile & preferences" sits
    under Atlas but holds the recycle bin, chat history, notifications and
    writing, is the only section with its own Save button, and repeats a
    "Web search" heading that only links to the Web search section;
    recommend "Profile" under Atlas, a "General" section under Your
    notebook, save on change, and the pointer heading removed. (Fixed:
    Profile keeps the name, look and About me; General, first under Your
    notebook, holds the bin, chat history, answer style, search relevance,
    notifications and writing; both save on change; the Web search pointer
    heading is gone; the Ask tab's relevance link and the catalogue go to
    General.)
    (m) Settings sections are long: Tools 7,592px tall at 1440 (12,058px at
    390), Appearance 4,537px with 105 controls, Logs 515 controls;
    recommend collapsed groups (`details`) with the first open, per
    DESIGN.md.
    (n) One thing, several names: Chat (tab), "Ask" (Notes sub-tab and
    status bar), "Write with Atlas" (Notes sub-tab), Atlas (Settings group);
    Skills (Settings) vs "AI skills" (Library sub-tab); recommend one noun
    per thing in DESIGN.md's copy rules and a lint.
    (o) Library: 8 sub-tabs plus 13 chips in All, several the same filter
    twice (Documents chip and sub-tab; Boards and Mind maps chips and the
    "Boards & maps" sub-tab; Files chip and sub-tab); 101 visible controls
    at 1440; recommend the chips be the only kind filter in All.
    (p) Documents have a tab page with no tab-bar button: the way in is the
    Library's Documents sub-tab, and the tab bar then highlights Library;
    recommend a breadcrumb back to the Library in the editor's dock. (Fixed:
    a "Documents" breadcrumb opens the dock, back to the Library's
    Documents list, measured at the title's height.)
    (q) Notes tab: 109 visible controls at 1440, 19 of them under 24px
    (the link chips on each card); recommend the link chips behind a count
    ("6 links") on the card, expanded on hover or focus. (Fixed: the
    first three links show, the rest wait behind "+N more links", which
    opens them in place.)
    (r) Memory is clean: 30 tab switches moved the heap 21.7 to 22.3MB,
    DOM nodes 48,888 to 49,297, listeners flat. Idle Chat once measured
    599 layouts per 10s at 4x and did not reproduce (0 in a later 5s
    check): watch for it.

425. **The owner, 2026-09-24 (after the usage reset), with screenshots.**
    Avatars: (a) "the avatar shows even when the app is on the lock screen.
    it should only show when the app is unlocked"; (b) "is there a way to
    make the corner companion more lifelike and less a circle just chilling
    somewhere on the screen?? give it life", and "an adaptive companion
    avatar placement feature where set areas are assigned as possible areas
    for a companion to sit or chill around while not being in the way on
    every interface and page. and the companion can even interact with the
    close ui like hand from a top bar, sit on a bottom bar, walk a top a
    feature ... just so I dont move it to one area, and then it is annoying
    for it to be there on another page" (fixed: the companion is one
    drawn character with a body, and per tab it takes a perch measured from
    the real UI (hanging from the top bar or a panel's underside, sitting on
    or standing at a top edge with its legs dangling or tucked, tucked behind
    the bottom bar as a last resort), never over a control; a spot you drop
    it on is kept per tab against its panel; a weighted behaviour picker
    with cooldowns runs one decision every 4 to 12s; commits 4b4f1d4 to
    5c19f45); (c) "may shuffled avatar reset and
    didnt persist"; (d) "how does the shuffle work?? does it still base it
    on what is entered for the name??" (fixed: Your look says it keeps what
    the name says and any part you chose and redraws the rest, db38ea1);
    (e) "I want the persona avatar to
    appear next to where you set the persona for the dashboard greeting";
    (f) "I set the dashboard greeting to another persona, but when I hit
    regenerate, it said asking Atlas"; (g) "I changed personas for the
    dashboard greeting and the avatar/icon changed as I had set it, but when
    I changed the persona again, it didnt change again"; (h) "the whole
    thing with the avatars needs a proper polish and bug fix ... a full ui
    and ux upgrade to properly fit the application" (fixed: every generated
    face is one designed character, d1e74fd; swept at 1440 and 390, light
    and dark: row alignment within 0.5px at every list site, no clipping
    but the large view's ears (fixed), speech bubbles kept inside the
    window, the companion no longer over the chat composer's settings or
    the phone's Library tab). Documents: (i) "can
    there be a document full screen mode so there is more space ... maybe
    the top bar needs a bit of redesigning or the interface on the document
    editor needs a bit of visual adjusting to allow for more room. also
    tables are still really annoying to use and edit in the documents live
    view" (fixed: focus mode on the dock and F11 hides every band of chrome,
    a fading floating bar keeps title, words, save state and Exit, 228px to
    71px above the first line and 520px to 830px of writing at 1440x900;
    the dock is one 36px row, 49px back in the normal view; Live tables keep
    the column on the arrows, Enter goes down and adds a row, the arrows
    leave a table at either end of the document, a spreadsheet paste fills
    cells or makes a table, the cell menu rides the edited row; the AI
    assistant's head and verbs redesigned; commits da89a75 to 260bb2a).
    Settings: (j) "remove the need for saving preferences in the
    settings and just have it auto save like the rest of the settings"
    (fixed: preferences autosave and the Save button is hidden, `#prefs-save`
    and `#prefs-status` in `index.html`, INBOX 426 u);
    (k) "should these text boxes be aligned to the right??" (the
    Preferences number fields; answered, no change: measured, all four
    sit on the pane's one field column at x=812, the same left edge as
    Display name and the answer-style select, and flushing them right
    would give each a different left edge because their units differ); (l) "Improve how custom theme cards are
    displayed" (name truncated "Sea of P...", delete button crowding it; fixed: saved looks get a 10rem track,
    the name wraps to two lines before it truncates, delete is a badge on
    the card corner; measured 183px cards, no name clipped at 1440).
    Dashboard: (m) "the search bar on the dashboard has a glass aesthetic
    even when it is off"
    (fixed: its ground was a 4% tint over the page art; the tint now sits
    on `--card`, which glass off makes solid). Backgrounds: (n) Mycelium start points more
    organic, smoother faded transitions; (o) optimise Microbes (fixed, both,
    e5a8c4b and b8ad914: scattered spores, staggered threads, a 2s
    cross-fade between generations; Microbes 3.0 to 2.2ms a frame; also
    Constellation 3.5 to 2.4ms, Mesh and Orbs moved to 15/30fps canvases,
    whole-browser CPU about halved. Still open: Constellation and Microbes
    just over the 2ms budget on a loaded machine, 0.3 to 1MB/s of canvas
    garbage from fractional coordinates, pause on blur only after 30s, the
    dead CSS path and `bg-*` keyframes in 03-dashboard-widgets.css, a faint
    upscale texture in the dark mesh, 4x-throttle numbers not re-run). (p) "see if there are any more areas to reduce
    lag ... like the avatars and other animations" (the audit agent, 424).
    (q) "on the dashboard when on the focused view, the hero section row is
    ugly and needs improvement and I dont agree with the search bar being on
    the same line and changing width depending on how long the welcome
    message is" (fixed: the owner's decision reverses INBOX 296's one-row
    head; Focused is Full's head at a smaller scale, a 71px banner with the
    greeting and name nudge, the summary under them and the time on the
    right, and the search full width beneath it at 1408px whatever the
    greeting says; measured at 1440 and 390).

427. **Open from INBOX 426, 2026-09-26: two calls only the owner can make.**
    Everything else in 426 (a to cc) is built and in HISTORY, "INBOX
    resolved, 2026-09-26"; the agents' smaller leftovers are in
    `agent-remaining/OPEN.md`, "Left by the 0.3.3 agents".
    (1) **Atlas's anatomy, the owner's read of rounds 3 and 4.** The trace
    proofs put the masculine look at 88% of the reference sprite's height
    and the feminine look's hair a third shorter than the definitive stand's;
    the owner's review names the next round (hands and feet, the head to body
    join, the tail's ribbon, the chest star). Judge it in the avatar lab
    (`tools/avatar-lab.html`, Both looks, All poses) or the README's
    `docs/screenshots/atlas-hero.png` and `atlas-poses.png`.
    Recommendation: none to take on the owner's behalf; this is taste.
    (2) **The companion's pin near an edge.** A companion pinned within 160px
    of the window's right or bottom edge keeps its distance from that edge
    when the window is resized (so it moves with the edge); one pinned further
    in keeps its place. Whether the owner reads the first as "it still
    moves" (426 l) is not known. Recommendation, taken unless the owner says
    otherwise: keep it, since a pin by the edge that stayed put would end up
    off screen or under the scroll bar on a narrower window, which is 426 k.

430. **The owner, 2026-09-27 afternoon, with 37 screenshots (verbatim in the
    session; condensed here, each placed with an agent).** Bugs: agent turn
    "Invalid format string" on Windows (**fixed** 180e522); chat citation
    renumbered to 1 on reload while its peek shows source 8; scroll jumps in
    chat with a sources fold open; layout flickers between two states every
    second in devtools responsive mode; top bar not centred at small widths;
    lightbox meatball menu does nothing; OCR workspace not reachable from
    Images; '?' popover in Capture does not scroll with a touchpad; tools
    list draws a second divider over column two's first row; Privacy's
    Since launch / All time pill has no active state; capture preview
    crushes line numbers; Atlas spills out of its ring in the tour.
    Phone and tablet: graph controls overlap, Documents editor cut off,
    whiteboard will not pan by touch, lightbox, skill logs sidebar (gap,
    shadow, no hover-expand), gap under the bottom bar, the agent-runs bar
    on phones, Contents dates overflow, a portrait-shaped graph. Asks:
    links widget and a rename of Library's Links; notice banners carry
    their action with a confirm; settings section heads; the agent popup's
    avatar circles; guide: AI/system answer toggle, much more help, cleaner
    formatting; model per feature offers "same as chat/utility model";
    note forms use the live view with a source toggle, no Preview; AI
    templates (generate, edit, regenerate) and every template in Settings;
    Windows tray menu extended; constellation in the background art and a
    better constellation; graph node size by a toggle, Arc fit, Tree
    centred; companion: perches on every tab, dodges popups, less
    distracting, lifelike motion and transitions, a show/hide hotkey and
    palette action (done: Ctrl+Shift+Y, rebindable, palette and Find
    anything rows that say Hide or Show, PR 162); Atlas less chunky, masculine limbs, tilted rings with
    orbiting bodies, a taller nebula; generated faces vary expression per
    character. Questions: prompt injection, chat header divider. Rules:
    two or three agents, Sonnet where quality holds, concise.
    **Added 2026-09-27 midday (the owner, verbatim):** "also can you extend
    this menu a bit maybe with sub-sections if necessary, for things such as
    a quick link to the profile/personas/appearences tab, toggling various
    features such as masculine/feminine, which companion is displayed etc."
    (the companion's right-click menu). Its screenshot also shows that menu
    opening at the window's top left with the companion at the bottom right:
    recheck on the current head after a0d957a. Decided the same day: desktop
    first with small laptops (1366x768 at 125%, 1280x720) and tablets next;
    Links is renamed Bookmarks; the two map kinds are named separately;
    releases stay on 0.3.3 for now.
    **Added (the owner):** tab changes: the companion lingers on the old tab
    a moment then pops in elsewhere. Wanted: it stays behind on quick tab
    flicks and only follows after the person settles on a tab; it enters
    smoothly (walks on from the side, climbs up from the bottom bar, climbs
    down from the top bar, or materialises), never a sudden pop; a "reduce
    actions" setting so waves and gestures come less often; more stances,
    Atlas's masculine and feminine each with their own.

## Placed from INBOX, 2026-10-04 (design work for the next Opus slots)

Briefs 485, 496, 493, 484, 486 and 490 are all built (each carries its "Built:" line in HISTORY.md, "INBOX resolved": 485 the Attach panel `6236875`, 496 Contents and the Boards and maps load `f58c264` `e489bda`, 493 the graph's look `4af88c6` `5a3d6eb` `a506e0f`, 484 the leader menu `64fa7a5`, 486 callouts `cb7c30d`, 490 the follow-up trail `fabdcbf`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)").

507. **From the dock audit (479, `scratchpad/dock-audit-479.md`), found and
     not fixed.** Graph: fold the View menu into the gear (two ways in).
     Boards and maps: one "New" with board and mind map inside (8 controls
     today). Zoom controls: one orientation and order on Graph, board and
     map. Help '?' on the Library's All, Documents and Bookmarks sub-tabs.
     Reminders: one "Add" per card. The documents dock onto the shared dock
     recipe (DOCUMENTS_PLAN). Sonnet-sized except the zoom unification.

## Placed from INBOX, 2026-10-05 (OPEN.md triage)

- ~~**Move a batch of notes to another space**~~ Built (row 30: `batch-space.js`, `POST /spaces/{id}/move-notes`, an Undo that moves them back, `tests/test_selection_actions_row30.py`; HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WORLD_CLASS_PLAN)").
- **The Guide's corpus and the Help accordion are kept in step by hand**
  (guide; the synonym column it asked for exists, `help_chat.py`'s keyword
  table). Brief: give the accordion's thirteen `<details>` ids, convert them
  to the named family under `test_ui_recipes.py`'s ratchet, then a lint that
  every accordion id has a Guide topic. Sonnet, M.

434. **The owner, 2026-10-03, verbatim.** "Can you make sure everything in
     the frontend, backend, function, utility and process for how the user
     can write notes and make a note is insanely easy and fast?? It needs to
     be world class. It it the whole reason for this notebook after all. It
     needs to be very accurate, fast, easy, not complicated but with advanced
     features, very robust and to actually work. It needs to be better than
     all other notebooks out there, have multiple ways it can be done, have
     extensive capabilities, and be the absolute gem of the app. It needs to
     be this amazing even when the ai isn't available or accessible and then
     even better with it."
     Placed (one brief, after the frontend/js move lands): (1) a measured
     audit of every way a note is made (Capture, New note, palette, keys,
     paste, drop, share, templates, daily note, from a selection, desktop
     quick capture) against Apple Notes, Obsidian, Bear, Keep and Drafts:
     time from intent to typing, keystrokes to saved, what is lost on a
     crash or a dead server; (2) filing without a model (local rules from
     the notebook's own categories and tags, so "no AI" still files well),
     better with one; (3) robustness (draft kept through reloads and
     crashes, offline save queued, never a lost keystroke); (4) the gaps
     the audit finds, fixed by impact, each measured.
     Built across 2026-10-03 and 2026-10-04 (capture audit, filing speed); both progress records moved to HISTORY.md,
     "Moved from the plans, 2026-10-10 (measure60)". Open: staged pictures and files cannot be held offline; the desktop window,
     real clipboards and a server crash between commit and answer are not verified.

## Placed from the owner's list, 2026-10-10

Entries are the owner's words, then the recommendation. Bugs come first, then design requests, then ideas.

### Bugs

- "I pressed a restart button and it failed: {"[1007/230819.346:ERROR:ui\gfx\win\window_impl.cc:172] Failed to unregister class Chrome_WidgetWin_0. Error = 1411"}"
  Recommendation: the desktop restart path (`src/tessellate/__main__.py`, the webview start) treats this unregister error as non-fatal and relaunches; reproduce it on Windows, which this sandbox cannot run. No brief carries it; Brief 17 (launchers) is the nearest.
- "this didnt work "https://192.168.0.107:8443", on my phone it said the page was unsecure, and then I clicked continue, and it said "safari can't open the page because the connection was lost.". I do have a vpn/custom dns sever through adguard active but that shouldnt be a hindrance. also the security needs to be improved if possible for this to work on phone."
  Recommendation: phone access over HTTPS, with the "connection was lost" cause found on iOS Safari, a one-page trust guide with a QR code, and a local CA option. Also carried by Brief 40 (the phone over HTTPS) and Brief 15 (network hardening).
- "it says the connection isnt secure and the page cant be reached" / "on brave browser on my phone"
  Recommendation: the same trust flow as the entry above, checked in Brave on a phone. Also carried by Brief 40 (the phone over HTTPS).
- "Also I still cant access the application on my phone, the connection just doesn’t go through and there are security issues with a not trustworthy connection and more."
  Recommendation: the phone path is a gate in Brief 40's research and Brief 15's hardening; the result is a measured reachability check from a second device. Also carried by Brief 40 and Brief 15.
- "Still lots of issues with filing without the ai model running but it should still work right because the embedding model is running??" / "I filed a note with no ai model running, did it use the embedding model??"
  Recommendation: with the model off and the embedder on, the filing path names the signal that filed the note; measure top-1 accuracy with the embedder on and off on the 120-note fixture. Also carried by Brief 39b (lexical filing and the embedder).
- "Also can things still work with all the similarity stuff for the composer and filing and other stuff if sentence-transformers isnt installed??"
  Recommendation: the similarity path runs with no sentence-transformers installed, and a test covers that case. Also carried by Brief 39b and Brief 35 (no new dependencies).
- "Study and university tags are suggested on the top note if it has no tags no matter what the note is about"
  Recommendation: reproduce the "Study" tag suggestion on the fixture, fix it, and keep the fixture as a test. Also carried by Brief 39b (the "Study" bug reproduced then gone).

### Design requests

- "is it possible to customise the domain name on the network accessible url??"
  Recommendation: an optional local host name for the LAN address (a mDNS or hosts-file name) shown with the trust guide. Also carried by Brief 40 (the phone over HTTPS).
- "Should we integrate it as a docker build and image and make it available as a docker app as well??"
  Recommendation: a Dockerfile and compose file with offline model volumes, and the measured image size in the report. Also carried by Brief 40 (a Docker image).
- "Is it possible to make use of python libraries that the user already may have installed globally on their computer so the user doesn’t have to install the same dependancies twice?? Like sentence transformers, or torch, or triton etc?? Idk"
  Recommendation: a setup choice to use system site packages, with its risks written down. Also carried by Brief 40 (reusing the system Python packages).
- "Does the mcp server work or need to be improved?? I don’t think it has been properly integrated as a feature yet."
  Recommendation: run the MCP server, list its tools, and report what is broken before any integration work. Also carried by Brief 40 (whether the MCP server works).
- "Does the user have to be connected to the interned for the initial install for installing all the dependencies?? Should the user be informed of that if that is the case??"
  Recommendation: state the answer and show it on the install screen if the answer is yes. Also carried by Brief 40 (whether a first install needs the internet).
- "what is this app file installer?? can this app use it and is it free??"
  Recommendation: answer it in the Brief 40 research with the licence and whether the app can call it. Also carried by Brief 40 and Brief 17 (the installer).
- "Also I feel like we should reference all the vendored repos and libraries somewhere to give them credit."
  Recommendation: a credits list in Help, generated from `docs/THIRD_PARTY.md`, with each licence file. Also carried by Brief 35 (the credits file).
- "I also want to integrate and use the new vendored repositories and libraries better and also see if there are more complimentary libraries and repos we can vendor…"
  Recommendation: each vendored library gets one named use in the engine, with a test, and a keep or drop row in ANALYSIS.md. Also carried by Brief 40 (candidate vendorable libraries) and ROADMAP Direction policy 1.
- "Filing and suggested tags and categories and stuff need a lot of improving. Should we include a library of common possible categories and even ways to join words to make custom categories and then there can be a similaity search for new or existing category filing and concatenation for new categorie"
  Recommendation: a seed category library (the taxonomy pack) with joins for custom categories, and a similarity search over new and existing categories. Also carried by Brief 39b (candidates, decision and merge suggestions) and ROADMAP Direction policy 3.
- "just continue and research categories and tags etc. make it extensive and also dynamic. some categories for example might not just be "gym" or 'Fitness" but "gym & fitness" yk??"
  Recommendation: category names are phrases ("gym & fitness"), matched by the taxonomy's keyword candidates. Also carried by Brief 39b (the taxonomy).
- "I think meeting notes should be different or at least partially separate from dictation and audio transcribing. Can there be an auto captioning and transcribing tool live as well?? Maybe a way to record store and edit mp3 audio notes like with Apple voice memos?? What about ai free translations?"
  Recommendation: meeting notes, dictation, voice memos and live captions as separate entries in the audio section; translation is an offline engine question. Also carried by ROADMAP Direction track 11 (audio in the notebook).

### Ideas

- "I want to deep analyse this repo and see if we can cake a use/replicate/take a lot from it https://github.com/haifengl/smile.git"
  Recommendation: the smile read goes into ANALYSIS.md with the algorithms worth a small Python port (clustering, keyword extraction). Also carried by Brief 40 (haifengl/smile).
- "are there any other libraries that could be used that I and u havent found or mentioned??"
  Recommendation: the candidate-library table in Brief 40 answers this, with keep or drop for each. Also carried by Brief 40.
- "did you vendor the other libraries and binaries?? do we need to?? what else is there to do??"
  Recommendation: answer in ANALYSIS.md: which libraries are vendored, which are pip dependencies, and which are dropped under policy 1. Also carried by Brief 40 and ROADMAP Direction policy 1.
- "doesnt harper use a binary though?? are there any other repos or libraries that we can vendor??"
  Recommendation: Harper is a WebAssembly build in the frontend; the Brief 40 table records any other WASM or pure Python candidate. Also carried by Brief 40.

## Placed from Brief 40, 2026-10-10 (the phone over HTTPS)

The owner: "https://192.168.0.107:8443 ... safari said the page was
unsecure, I clicked continue, and it said safari can't open the page because
the connection was lost", the same in Brave on the phone, AdGuard DNS active.

**What was measured on this computer** (`scratchpad` probe, a
`uvicorn` server with the app's own `core/lancert.py` certificate, driven with
`openssl s_client` and `curl`; no phone was available):
- TLS 1.2 and 1.3 both negotiate (`TLS_AES_256_GCM_SHA384`, a 256-bit key); no
  ALPN, so HTTP/1.1 only. Neither is a plausible cause.
- The certificate names the LAN address as an IP SAN and a request to a name
  it does not carry fails (`curl: no alternative certificate subject name
  matches target host name '192.168.0.231'`). **`lancert.ensure()` never
  compares the names with the machine's current addresses** (it checks only
  the expiry), so after a router hands the computer a new address the
  certificate on disk keeps the old one for up to 825 days and the phone is
  told "wrong name". Measured: a second `ensure()` with a new address list
  returned the original names and the same fingerprint.
- The leaf is self-issued, 825 days, with SAN, basicConstraints and EKU
  serverAuth but no keyUsage. Apple limits certificates that chain to a
  trusted root to 398 days; the exemption is for roots the user installed,
  and a clicked-through self-signed leaf is not one.
- The front end uses NDJSON over `fetch`, not WebSocket or EventSource
  (`capture-ask.js` line 2544, `settings.js` line 1018), so a WebSocket over
  an untrusted certificate is not the cause. The session token travels in a
  header; only the media cookie is `Secure` and `SameSite=Strict`
  (`routes_auth.py` lines 156 to 272), and what Safari does with a `Secure`
  cookie on a clicked-through page is not verified.
- `HostCheckMiddleware` lets any numeric Host through, so the rebinding
  guard is not refusing the phone.

**Likely causes, ranked** (none reproduced; "connection was lost" is
`NSURLErrorNetworkConnectionLost`, the server or something between closing a
connection that had opened):
1. The phone's per-connection trust: Safari opens several parallel
   connections and a clicked-through exception on a self-signed leaf is
   per-session, so the page's later connections can fail the handshake and be
   dropped. A certificate the phone trusts properly removes this.
2. A stale name (above), after a DHCP change, shown the same way as a plain
   untrusted warning.
3. AdGuard on the phone: a DNS profile does not touch an IP address, but the
   AdGuard app's local VPN mode and iOS 14's Local Network permission for
   Safari and Brave can drop traffic to a private address; Brave on iOS is
   WebKit too, which is why both browsers fail alike.
4. The Windows firewall profile (Public blocks, Private allows) answering the
   first request and not the next; the launchers add no rule.

**Fix shape, in order** (one brief, Opus):
1. **A local CA, mkcert style, made with `cryptography` (already a
   dependency)**: an EC P-256 CA kept in `lan-tls/` (0600), a leaf signed by
   it for 397 days with keyUsage and the SAN, remade by `ensure()` whenever
   the current addresses are not all in the SAN (the stale-name fix) and 30
   days before expiry. The phone installs the CA once; every later address
   change is invisible to it.
2. **Settings, Other devices, "Trust this notebook on your phone"**: a QR
   code to `http://<ip>:8000/lan/trust` (a plain-http route that serves only
   the public CA certificate and the guide, nothing else, and is on only
   while the panel is open), the CA's SHA-256 fingerprint beside it to compare
   after installing, and a one-page guide per phone: iPhone and iPad
   (download the profile, Settings, Profile Downloaded, Install, then
   General, About, Certificate Trust Settings, switch on full trust), Android
   (Settings, Security, Install a certificate, CA certificate), and a note
   that Brave on iOS uses the system trust.
3. **A plain-http option for the home network**, off by default, with the
   password warning in one sentence ("anyone on this Wi-Fi can read it") and
   the existing refusal without a password. It is also the bisect: if
   `http://<ip>:8000` works on the phone and https does not, it is trust; if
   neither, it is the network, the firewall or AdGuard's local VPN.
4. **A diagnostics line in Settings, Network**: the addresses now, the names
   the certificate carries (green when every address is covered, amber with
   "Regenerate" when not), days left, the CA fingerprint, and a count of
   failed TLS handshakes since start (from uvicorn's log), so "connection
   lost" has a number beside it.
5. Add a Windows Defender Firewall rule at the opt-in (private profile only),
   or print the one-line `netsh` command when turning the switch on.
Help moves with it (standing order 13): `ai/help_topics_more.py` "lock"
topic, the `data-help-for` on the switch, `tests/test_manual_parity.py`.
- (Odysseus, fourth read 2026-10-10) 

## 24. Codebase census, 2026-10-10

Brief 45 part 1, numbers only. Produced by `python scratchpad/census/census.py` (stdlib, about 40 s; `--full` lists every row, `--section N` one section); section 24.6 is `scratchpad/ui-sweeps/errors.js`. The script header states the limits (JS is scanned, not parsed; names are matched as tokens). Part 2 reads these.

### 24.1 Size and complexity

#### 1.1 Python (src/tessellate, vendor excluded)
223 files, 131372 lines, 3674 functions, 128 over 80 lines, summed complexity 20809.

| file | lines | functions | longest (lines) | over 80 | max cx | sum cx |
| --- | --- | --- | --- | --- | --- | --- |
| src/tessellate/api/routes_whiteboard.py | 5428 | 128 | _board_preview (198) | 7 | 35 | 851 |
| src/tessellate/ai/question_noise.py | 5242 | 14 | repair (43) | 0 | 23 | 121 |
| src/tessellate/ai/tools/__init__.py | 4878 | 90 | execute_tool (115) | 6 | 31 | 669 |
| src/tessellate/api/routes_files.py | 3931 | 91 | analyse_attachment (181) | 6 | 47 | 544 |
| src/tessellate/api/routes_entries.py | 3835 | 107 | list_entries (145) | 11 | 41 | 674 |
| src/tessellate/entry/manager.py | 3519 | 138 | _hard_delete (179) | 2 | 24 | 561 |
| src/tessellate/ai/agent.py | 3153 | 49 | run_agent (416) | 5 | 78 | 486 |
| src/tessellate/api/routes_settings.py | 3015 | 82 | get_preferences (137) | 2 | 26 | 383 |
| src/tessellate/ai/composer.py | 2980 | 90 | compose (191) | 4 | 74 | 932 |
| src/tessellate/core/database.py | 2729 | 25 | _ensure_alembic_baseline (102) | 3 | 10 | 95 |
| src/tessellate/api/routes_chat.py | 2609 | 55 | _stream_lines (289) | 5 | 86 | 440 |
| src/tessellate/__main__.py | 2582 | 62 | _start_tray (330) | 5 | 20 | 269 |
| src/tessellate/ai/help_chat.py | 2480 | 15 | _matching_topics (74) | 0 | 26 | 108 |
| src/tessellate/ai/composer_tables.py | 2034 | 2 | _build (16) | 0 | 8 | 10 |
| src/tessellate/core/extras.py | 1840 | 48 | _run_install (139) | 1 | 23 | 293 |
| src/tessellate/ai/skills.py | 1774 | 25 | normalise (110) | 1 | 33 | 198 |
| src/tessellate/api/routes_graph.py | 1765 | 43 | _build_graph (321) | 3 | 45 | 324 |
| src/tessellate/ai/skill_runner.py | 1587 | 26 | _run_one_step (425) | 2 | 53 | 236 |
| src/tessellate/search/engine.py | 1499 | 48 | search (145) | 2 | 69 | 363 |
| src/tessellate/api/app.py | 1475 | 47 | _register_error_handlers (163) | 4 | 21 | 166 |
| src/tessellate/ai/help_topics_more.py | 1458 | 0 | - (0) | 0 | 0 | 0 |
| src/tessellate/ai/librarian.py | 1447 | 33 | build_messages (116) | 1 | 15 | 190 |
| src/tessellate/api/routes_documents.py | 1447 | 45 | import_document (99) | 2 | 16 | 157 |
| src/tessellate/ai/provider.py | 1440 | 48 | extract_text_tool_calls (150) | 1 | 30 | 254 |
| src/tessellate/api/routes_auth.py | 1433 | 53 | rotate_vault_key (142) | 1 | 15 | 210 |

(top 25 of 223 files by lines; `--full` lists all)

#### 1.2 JavaScript (frontend/js)
115 files, 189722 lines, 5530 functions, 278 over 80 lines, summed complexity 39215.

| file | lines | functions | longest (lines) | over 80 | max cx | sum cx |
| --- | --- | --- | --- | --- | --- | --- |
| frontend/js/documents.js | 20621 | 610 | docLivePlugin (1517) | 22 | 189 | 3936 |
| frontend/js/whiteboard.js | 19811 | 560 | initWhiteboard (3730) | 26 | 653 | 4914 |
| frontend/js/library.js | 11669 | 276 | filterLibraryImagesGallery (1546) | 20 | 113 | 2034 |
| frontend/js/whiteboard-map.js | 9195 | 333 | wbBuildMapNode (301) | 11 | 42 | 2236 |
| frontend/js/avatars.js | 9098 | 286 | drawCharacter (800) | 11 | 512 | 3099 |
| frontend/js/graph.js | 5660 | 124 | renderGraphSvg (1254) | 11 | 168 | 925 |
| frontend/js/dashboard.js | 5054 | 156 | startArt (276) | 12 | 34 | 947 |
| frontend/js/graph-canvas.js | 4995 | 133 | gcDraw (729) | 9 | 220 | 1297 |
| frontend/js/settings.js | 4492 | 142 | openSettingsModal (168) | 7 | 45 | 739 |
| frontend/js/documents-code.js | 4399 | 134 | docCodeScan (425) | 4 | 132 | 1153 |
| frontend/js/atlas.js | 3702 | 103 | atlasBuild (287) | 5 | 80 | 625 |
| frontend/js/notes-list.js | 3516 | 115 | appendInlineRun (220) | 8 | 52 | 850 |
| frontend/js/capture-ask.js | 3277 | 95 | askQuestion (311) | 4 | 87 | 694 |
| frontend/js/chat-attach.js | 3006 | 73 | sendChatMessage (1079) | 4 | 176 | 562 |
| frontend/js/chat-agent.js | 2953 | 88 | agentTimeline (488) | 6 | 43 | 547 |
| frontend/js/status.js | 2887 | 97 | openNotifications (197) | 4 | 28 | 589 |
| frontend/js/navigation.js | 2831 | 65 | renderMarkdown (408) | 5 | 74 | 438 |
| frontend/js/chat.js | 2808 | 89 | messageMetaLine (146) | 4 | 36 | 499 |
| frontend/js/editor.js | 2569 | 74 | editorLinkMatches (115) | 3 | 35 | 432 |
| frontend/js/timeline.js | 2441 | 70 | timelineRowElement (134) | 3 | 26 | 456 |
| frontend/js/sheets-selects.js | 2419 | 62 | enhanceSelect (242) | 7 | 41 | 378 |
| frontend/js/note-cards.js | 2406 | 46 | entryItem (915) | 2 | 169 | 457 |
| frontend/js/app.js | 2390 | 54 | startApp (187) | 4 | 32 | 329 |
| frontend/js/bg-art.js | 2244 | 46 | bgArtRun (153) | 2 | 47 | 288 |
| frontend/js/menus.js | 2210 | 56 | entryOverflowMenu (393) | 7 | 29 | 350 |

(top 25 of 115 files by lines; `--full` lists all)

#### 1.3 Ten most complex Python functions
| function | file:line | lines | cx |
| --- | --- | --- | --- |
| _stream_lines | src/tessellate/api/routes_chat.py:2083 | 289 | 86 |
| run_agent | src/tessellate/ai/agent.py:2738 | 416 | 78 |
| compose | src/tessellate/ai/composer.py:2655 | 191 | 74 |
| collect | src/tessellate/api/routes_tasks.py:50 | 356 | 71 |
| search | src/tessellate/search/engine.py:1077 | 145 | 69 |
| follow_on | src/tessellate/ai/composer.py:2173 | 105 | 62 |
| _retrieve | src/tessellate/search/search_manager.py:1053 | 215 | 57 |
| _run_one_step | src/tessellate/ai/skill_runner.py:848 | 425 | 53 |
| restore_board | src/tessellate/api/routes_board_history.py:334 | 129 | 49 |
| analyse_attachment | src/tessellate/api/routes_files.py:446 | 181 | 47 |

#### 1.4 Ten most complex JavaScript functions
| function | file:line | lines | cx |
| --- | --- | --- | --- |
| initWhiteboard | frontend/js/whiteboard.js:10401 | 3730 | 653 |
| drawCharacter | frontend/js/avatars.js:1721 | 800 | 512 |
| gcDraw | frontend/js/graph-canvas.js:1541 | 729 | 220 |
| build | frontend/js/documents.js:7422 | 942 | 189 |
| sendChatMessage | frontend/js/chat-attach.js:1478 | 1079 | 176 |
| entryItem | frontend/js/note-cards.js:1371 | 915 | 169 |
| renderGraphSvg | frontend/js/graph.js:1801 | 1254 | 168 |
| nameMood | frontend/js/avatars.js:395 | 488 | 141 |
| docCodeScan | frontend/js/documents-code.js:2906 | 425 | 132 |
| renderWhiteboard | frontend/js/whiteboard.js:16408 | 864 | 126 |

#### 1.5 Functions over 80 lines
406 in total (128 Python, 278 JavaScript). Top 20 by length:

| function | file:line | lines | cx |
| --- | --- | --- | --- |
| initWhiteboard | frontend/js/whiteboard.js:10401 | 3730 | 653 |
| openLightbox | frontend/js/lightbox-view.js:25 | 1888 | 54 |
| filterLibraryImagesGallery | frontend/js/library.js:7890 | 1546 | 113 |
| docLivePlugin | frontend/js/documents.js:6941 | 1517 | 52 |
| renderGraphSvg | frontend/js/graph.js:1801 | 1254 | 168 |
| sendChatMessage | frontend/js/chat-attach.js:1478 | 1079 | 176 |
| build | frontend/js/documents.js:7422 | 942 | 189 |
| entryItem | frontend/js/note-cards.js:1371 | 915 | 169 |
| docCmTheme | frontend/js/documents.js:18486 | 871 | 1 |
| renderWhiteboard | frontend/js/whiteboard.js:16408 | 864 | 126 |
| drawCharacter | frontend/js/avatars.js:1721 | 800 | 512 |
| renderWbObjects | frontend/js/whiteboard.js:17554 | 780 | 96 |
| gcDraw | frontend/js/graph-canvas.js:1541 | 729 | 220 |
| nameMood | frontend/js/avatars.js:395 | 488 | 141 |
| agentTimeline | frontend/js/chat-agent.js:504 | 488 | 43 |
| mapPreview | frontend/js/note-cards.js:386 | 467 | 69 |
| nameMarkBuddyBuild | frontend/js/avatars.js:8526 | 444 | 47 |
| _run_one_step | src/tessellate/ai/skill_runner.py:848 | 425 | 53 |
| docCodeScan | frontend/js/documents-code.js:2906 | 425 | 132 |
| cmdPaletteAsk | frontend/js/palette.js:831 | 418 | 42 |

### 24.2 Duplicated blocks

338 files, 203831 normalised lines (blank and comment lines dropped); window 8 lines; shingles with fewer than 4 distinct lines or under 100 characters are skipped.
133 duplicated blocks (groups of 2+ places); 2636 distinct source lines sit inside a duplicated block (1.3% of normalised lines).

| normalised lines | places | file:line |
| --- | --- | --- |
| 41 | 2 | src/tessellate/ai/composer_tables.py:1578, src/tessellate/ai/composer_tables.py:1808 |
| 37 | 2 | src/tessellate/ai/question_noise.py:152, src/tessellate/ai/question_noise.py:4410 |
| 21 | 2 | src/tessellate/api/routes_files.py:774, src/tessellate/api/routes_files.py:1675 |
| 19 | 2 | src/tessellate/api/routes_auth.py:630, src/tessellate/api/routes_auth.py:738 |
| 18 | 2 | src/tessellate/ai/ollama_client.py:764, src/tessellate/ai/ollama_client.py:889 |
| 18 | 2 | frontend/js/notes-list.js:1963, frontend/js/notes-list.js:2290 |
| 17 | 2 | frontend/js/documents-code.js:1626, frontend/js/documents-prose.js:1718 |
| 17 | 2 | frontend/js/whiteboard.js:17005, frontend/js/whiteboard.js:17937 |
| 16 | 2 | src/tessellate/ai/ollama_client.py:799, src/tessellate/ai/openai_client.py:896 |
| 16 | 2 | frontend/js/library.js:3953, frontend/js/library.js:7191 |
| 14 | 2 | src/tessellate/api/routes_library.py:392, src/tessellate/api/routes_library.py:506 |
| 14 | 2 | frontend/js/whiteboard.js:5176, frontend/js/whiteboard.js:5304 |
| 13 | 2 | src/tessellate/ai/ollama_client.py:688, src/tessellate/ai/openai_client.py:825 |
| 13 | 2 | src/tessellate/api/routes_files.py:2617, src/tessellate/api/routes_files.py:3069 |
| 13 | 2 | src/tessellate/api/routes_settings.py:2693, src/tessellate/api/routes_settings.py:2852 |
| 13 | 2 | frontend/js/library.js:10293, frontend/js/whiteboard.js:10319 |
| 13 | 2 | frontend/js/whiteboard.js:13581, frontend/js/whiteboard.js:13719 |
| 12 | 3 | src/tessellate/api/routes_auth.py:978, src/tessellate/api/routes_auth.py:1060, src/tessellate/api/routes_auth.py:1262 |
| 12 | 2 | src/tessellate/ai/ollama_client.py:728, src/tessellate/ai/openai_client.py:855 |
| 12 | 2 | frontend/js/documents.js:8487, frontend/js/documents.js:9001 |
| 12 | 2 | frontend/js/suggestions-inbox.js:114, frontend/js/tidy.js:158 |
| 11 | 3 | frontend/js/documents-prose.js:390, frontend/js/documents.js:6287, frontend/js/documents.js:15013 |
| 11 | 3 | frontend/js/library.js:8423, frontend/js/library.js:8579, frontend/js/library.js:8767 |
| 11 | 2 | src/tessellate/api/routes_entries.py:1284, src/tessellate/api/routes_entries.py:2545 |
| 11 | 2 | src/tessellate/api/routes_whiteboard.py:5344, src/tessellate/api/routes_whiteboard.py:5417 |
| 11 | 2 | src/tessellate/core/extras.py:1153, src/tessellate/core/extras.py:1334 |
| 11 | 2 | src/tessellate/core/security.py:333, src/tessellate/core/security.py:353 |
| 11 | 2 | src/tessellate/search/engine.py:771, src/tessellate/search/engine.py:811 |
| 11 | 2 | frontend/js/categories-panel.js:68, frontend/js/tag-manager.js:458 |
| 11 | 2 | frontend/js/categories-panel.js:225, frontend/js/tag-manager.js:581 |

(top 30 of 133 blocks by size)

### 24.3 Dead-code candidates

Corpus: identifier tokens in frontend/ (js, html, css), src/ and tests/, vendor excluded; strings and comments count as uses. A candidate is a name whose only occurrence is its own definition (grep count after the definition, 0). The last column is the count of uses in tests/ alone (a name used only by tests is listed with a non-zero count).

#### 3.1 Top-level functions in the 27 classic scripts: 1221 defined, 0 candidates

(none)

#### 3.2 Python defs in src/tessellate: 3674 defined, 40 candidates (excluded as called by a framework: dunder methods, 346 decorated defs such as route handlers and validators, and SQLAlchemy type hooks)

| def | file:line | uses in tests |
| --- | --- | --- |
| capture_signals | src/tessellate/__main__.py:585 | 0 |
| scheduler_alive | src/tessellate/ai/autonomous.py:249 | 2 |
| phrase_options | src/tessellate/ai/composer.py:263 | 13 |
| _yes_no_wrapped | src/tessellate/ai/composer.py:455 | 0 |
| today_line | src/tessellate/ai/composer_voice.py:490 | 1 |
| title_for | src/tessellate/ai/composer_voice.py:639 | 3 |
| suggested_searches | src/tessellate/ai/composer_voice.py:667 | 1 |
| suggest_entities | src/tessellate/ai/entities.py:104 | 5 |
| extract_concepts | src/tessellate/ai/fast_matcher.py:31 | 0 |
| unfence | src/tessellate/ai/fence.py:61 | 3 |
| note_passage_scores | src/tessellate/ai/grounding.py:298 | 2 |
| feature_model | src/tessellate/ai/model_manager.py:484 | 14 |
| reset_jobs | src/tessellate/ai/model_manager.py:831 | 7 |
| reset_for_tests | src/tessellate/ai/needle_provider.py:185 | 38 |
| forget_ollama_binary | src/tessellate/ai/offline.py:47 | 2 |
| is_llama_cpp | src/tessellate/ai/openai_client.py:319 | 2 |
| extract_categories | src/tessellate/ai/taxonomy.py:98 | 0 |
| notebook_began | src/tessellate/ai/timetravel.py:154 | 0 |
| budget_for_window | src/tessellate/ai/tools/__init__.py:4487 | 5 |
| reset_for_tests | src/tessellate/api/routes_update.py:171 | 38 |
| backup_if_due | src/tessellate/core/backup.py:250 | 4 |
| strip_comments | src/tessellate/core/docexport.py:97 | 1 |
| handle_starttag | src/tessellate/core/docview.py:193 | 17 |
| handle_endtag | src/tessellate/core/docview.py:234 | 16 |
| handle_data | src/tessellate/core/docview.py:262 | 5 |
| reset_for_tests | src/tessellate/core/embedmodels.py:795 | 38 |
| reset_for_tests | src/tessellate/core/embedswitch.py:389 | 38 |
| payload_bytes | src/tessellate/core/events.py:591 | 6 |
| reset_for_tests | src/tessellate/core/extras.py:1796 | 38 |
| queued_count | src/tessellate/core/jobs.py:407 | 3 |
| running_count | src/tessellate/core/jobs.py:411 | 2 |
| reset_for_tests | src/tessellate/core/passes.py:263 | 38 |
| is_open | src/tessellate/core/vault.py:68 | 10 |
| has_recovery | src/tessellate/core/vault.py:235 | 0 |
| handle_starttag | src/tessellate/core/webclip.py:206 | 17 |
| handle_endtag | src/tessellate/core/webclip.py:230 | 16 |
| handle_data | src/tessellate/core/webclip.py:244 | 5 |
| set_category | src/tessellate/entry/manager.py:226 | 2 |
| vectors_by_id | src/tessellate/search/engine.py:1396 | 7 |
| sources_for_kind | src/tessellate/search/index.py:198 | 1 |

### 24.4 Coupling of the classic scripts

27 classic scripts in index.html order (app.js to agent-activity.js); 1838 top-level names defined (1837 distinct); 648 read by another script.

#### 4.1 Per script (a name counts as read when another script contains it as an identifier token)

| script | globals defined | read elsewhere | reader scripts |
| --- | --- | --- | --- |
| app.js | 100 | 63 | 23 |
| prefs.js | 10 | 6 | 20 |
| store.js | 2 | 1 | 1 |
| note-cards.js | 61 | 18 | 9 |
| menus.js | 43 | 17 | 11 |
| lightbox.js | 13 | 9 | 3 |
| selection.js | 38 | 6 | 4 |
| notes-list.js | 155 | 49 | 21 |
| capture-ask.js | 130 | 35 | 14 |
| chat.js | 116 | 56 | 18 |
| chat-agent.js | 94 | 47 | 11 |
| chat-attach.js | 94 | 46 | 12 |
| sheets-selects.js | 76 | 22 | 19 |
| skills.js | 72 | 16 | 11 |
| shell-reminders.js | 71 | 29 | 15 |
| markdown.js | 49 | 29 | 4 |
| navigation.js | 90 | 26 | 21 |
| router.js | 22 | 6 | 7 |
| settings-panes.js | 62 | 14 | 15 |
| media.js | 42 | 18 | 3 |
| status.js | 155 | 46 | 23 |
| ai-tools.js | 60 | 30 | 6 |
| phone-shell.js | 73 | 13 | 16 |
| wiring.js | 58 | 15 | 9 |
| settings-wiring.js | 57 | 12 | 5 |
| spaces-find.js | 58 | 9 | 6 |
| agent-activity.js | 37 | 10 | 4 |

#### 4.2 Downward references (a script naming a global defined only in a later script)

Anywhere in the file (including inside functions, which run later and are legal): 424 names over 140 script pairs. At brace depth 0 (runs at load; IIFE and object-literal bodies are depth 1 and are not seen): 2 names over 2 pairs.

At load (depth 0):

| script | defined later in | names | examples |
| --- | --- | --- | --- |
| chat-agent.js | sheets-selects.js | 1 | aiNameNow |
| wiring.js | spaces-find.js | 1 | openFinder |

Anywhere (top 15 pairs by name count):

| script | defined later in | names |
| --- | --- | --- |
| note-cards.js | notes-list.js | 22 |
| status.js | ai-tools.js | 14 |
| notes-list.js | markdown.js | 12 |
| app.js | status.js | 12 |
| chat-attach.js | status.js | 11 |
| chat.js | sheets-selects.js | 10 |
| menus.js | notes-list.js | 8 |
| selection.js | status.js | 8 |
| note-cards.js | status.js | 8 |
| skills.js | status.js | 7 |
| shell-reminders.js | status.js | 7 |
| capture-ask.js | status.js | 7 |
| capture-ask.js | settings-wiring.js | 7 |
| menus.js | status.js | 6 |
| notes-list.js | status.js | 6 |

#### 4.3 The fifteen globals read by the most other scripts

| global | defined in | reader scripts |
| --- | --- | --- |
| toast | status.js | 22 |
| $ | app.js | 21 |
| apiJson | app.js | 21 |
| setLabel | app.js | 21 |
| prefs | prefs.js | 20 |
| api | app.js | 16 |
| switchTab | navigation.js | 16 |
| confirmDialog | app.js | 14 |
| smallButton | app.js | 14 |
| loadEntries | notes-list.js | 14 |
| toastAction | status.js | 12 |
| chip | app.js | 11 |
| copyToClipboard | chat.js | 11 |
| prefsCache | settings-panes.js | 11 |
| renderEntries | notes-list.js | 10 |

### 24.5 Counts

#### 5.1 TODO, FIXME, XXX, HACK (src/tessellate, frontend/js, frontend/css, index.html; vendor excluded)

Totals: TODO 0, FIXME 0, XXX 0, HACK 0.

#### 5.2 Ten largest files by bytes

frontend/js:

| file | bytes | lines |
| --- | --- | --- |
| frontend/js/whiteboard.js | 975984 | 19811 |
| frontend/js/documents.js | 964068 | 20621 |
| frontend/js/library.js | 564789 | 11669 |
| frontend/js/avatars.js | 497076 | 9098 |
| frontend/js/whiteboard-map.js | 432391 | 9195 |
| frontend/js/graph.js | 267187 | 5660 |
| frontend/js/dashboard.js | 240995 | 5054 |
| frontend/js/graph-canvas.js | 228977 | 4995 |
| frontend/js/atlas.js | 225772 | 3702 |
| frontend/js/settings.js | 206353 | 4492 |

frontend/css:

| file | bytes | lines |
| --- | --- | --- |
| frontend/css/07-whiteboard-misc.css | 534476 | 13496 |
| frontend/css/08-consistency.css | 530280 | 11631 |
| frontend/css/01-forms-settings.css | 240750 | 6747 |
| frontend/css/05-sidebars-themes.css | 233359 | 6726 |
| frontend/css/04-chat-dock-appearance.css | 231725 | 6392 |
| frontend/css/02-chat-graph.css | 230235 | 6694 |
| frontend/css/00-tokens-shell.css | 217837 | 4681 |
| frontend/css/03-dashboard-widgets.css | 171667 | 5161 |
| frontend/css/06-timeline-dialogs.css | 148530 | 4200 |
| frontend/css/10-responsive.css | 120837 | 3002 |

src/tessellate (vendor excluded):

| file | bytes | lines |
| --- | --- | --- |
| src/tessellate/api/routes_whiteboard.py | 240186 | 5428 |
| src/tessellate/ai/tools/__init__.py | 213773 | 4878 |
| src/tessellate/ai/question_noise.py | 186754 | 5242 |
| src/tessellate/api/routes_files.py | 185904 | 3931 |
| src/tessellate/api/routes_entries.py | 173879 | 3835 |
| src/tessellate/ai/agent.py | 154772 | 3153 |
| src/tessellate/entry/manager.py | 149080 | 3519 |
| src/tessellate/core/database.py | 147726 | 2729 |
| src/tessellate/ai/help_chat.py | 147179 | 2480 |
| src/tessellate/api/routes_settings.py | 142810 | 3015 |

#### 5.3 Backend routes with no test file naming their path

478 routes (`@router.*`-style decorators with the router's own prefix; any `include_router(prefix=...)` is not added). 54 have no path match in tests/: a `{param}` segment matches any run of non-space, non-quote characters, so this undercounts untested routes.

| route file | untested routes |
| --- | --- |
| src/tessellate/api/routes_documents.py | 12 |
| src/tessellate/api/routes_entries.py | 10 |
| src/tessellate/api/routes_board_library.py | 6 |
| src/tessellate/api/routes_conversations.py | 6 |
| src/tessellate/api/routes_whiteboard.py | 4 |
| src/tessellate/api/routes_meetings.py | 3 |
| src/tessellate/api/routes_properties.py | 2 |
| src/tessellate/api/routes_reminders.py | 2 |
| src/tessellate/api/routes_tidy.py | 2 |
| src/tessellate/api/routes_bench.py | 1 |
| src/tessellate/api/routes_categories.py | 1 |
| src/tessellate/api/routes_files.py | 1 |
| src/tessellate/api/routes_learned.py | 1 |
| src/tessellate/api/routes_mentions.py | 1 |
| src/tessellate/api/routes_questions.py | 1 |

#### 5.4 CSS class and id names in frontend/css used by no markup or script

3758 distinct class or id names in selector preludes; 236 appear as no token in index.html or frontend/js (names built by string concatenation, and classes added by Python-rendered HTML, would be false candidates).

| css file | unused names (a name in two files counts in both) |
| --- | --- |
| 08-consistency.css | 131 |
| 05-sidebars-themes.css | 30 |
| 07-whiteboard-misc.css | 23 |
| 02-chat-graph.css | 20 |
| 03-dashboard-widgets.css | 17 |
| 09-editor.css | 9 |
| 01-forms-settings.css | 7 |
| 04-chat-dock-appearance.css | 6 |
| 00-tokens-shell.css | 6 |
| 10-responsive.css | 4 |
| 06-timeline-dialogs.css | 4 |
| library-lazy.css | 3 |

#### 5.5 Frontend ids and handlers

| measure | count |
| --- | --- |
| id attributes in index.html | 2227 |
| distinct ids | 2227 |
| ids looked up by $("id") or getElementById in frontend/js | 1812 |
| looked-up ids with no element in index.html (runtime-created or missing) | 52 |
| ids bound with $("id").addEventListener("event") | 812 |
| bound ids with no element in index.html | 9 |
| index.html ids named by no token in frontend/js | 273 |

### 24.6 Console errors per surface

errors.js against a fresh data dir on this branch (9 tabs, library and notes subtabs, 19 Settings sections, light theme).

| width | page and console errors | layout findings |
| --- | --- | --- |
| 1440px | 0 | 0 |
| 1024px | 0 | 0 |
| 820px | 0 | 0 |
| 390px | 0 | 0 |

Not covered: dark theme (THEME=dark), a seeded large notebook, the fault pass (FAULTS=1).

### 24.6b Interaction timings, 2026-10-10

Measured by the `measure` agent (Brief 46) in a headless Chromium against a
data dir with 5,001 notes (seeded through `POST /entries`, 978 s, about 5 per
second), 1 document of 50,001 words and 1 board of 500 text objects. **The
machine was saturated while every number below was taken** (4 cores, load
average 8 to 10 from other sessions' browsers and servers), so the wall times
are upper bounds: a trivial `GET /entries?limit=1` took 1.6 to 2.6 s and a
static `GET /` 0.9 s on the same server in the same minutes. They rank
interactions against each other; they are not budgets. Re-run on an idle
machine before `tests/test_budgets.py` (Brief 53) fixes a figure.

| Interaction | Measured (p50 unless noted) | Command |
| --- | --- | --- |
| Seed 5,001 notes | 978 s, three concurrent writers | `.venv/bin/python scratchpad/ui-sweeps/measure-seed.py 8794 5000` |
| Boot, cold context | DOMContentLoaded 10,468 ms, first contentful paint 4,484 ms, lock field visible 11,581 ms (5 runs) | `node scratchpad/ui-sweeps/measure-interactions.js` (PHASE=boot) |
| Unlock to interactive (lock overlay hidden, curtain gone, dashboard hero visible) | 4,461 ms; a reload with the stored token 5,842 ms | same |
| Notes list paint, tab switch to rows | 261 ms (107 to 617 over 10 runs); 61 rows of 5,003 in the DOM | PHASE=list |
| `GET /search`, "garden" | hybrid 2,425 ms, keyword 1,815 ms (20 hits) | PHASE=search |
| `GET /search`, "dentist budget" | hybrid 3,489 ms, keyword 3,404 ms (20 hits) | PHASE=search |
| `GET /search`, "Note 4242" | hybrid 4,959 ms (6 hits), keyword 2,544 ms (1 hit) | PHASE=search |
| Notes list query box, last keystroke to rows changed | "garden" 238 ms, "dentist budget" 260 ms, "Note 4242" 168 ms; settled 256, 273, 168 ms | PHASE=keybox |
| Board open, 500 objects, call to all 500 `.wb-object` plus two frames | first open 2,551 ms; four later opens 55, 77, 88, 100 ms | `node scratchpad/ui-sweeps/measure-objects.js` (PHASE=board) |
| Document open, 50,001 words (308,327 characters) | 740 ms (557 to 986 over 5 runs), `openDocument` call to resolved plus two frames | PHASE=doc |
| Server CPU, 60 s idle, dashboard tab open | 66.2% then 63.3% of one core, resident 1.95 to 2.13 GB | `SERVER_PID=n node scratchpad/ui-sweeps/measure-idle.js` |
| Server CPU, 60 s idle, notes tab open | 16.0% then 2.0% of one core, resident 0.92 to 1.0 GB | same |
| Resident memory | 0.74 GB just after start; 8.5 GB on the first server after 35 minutes of seeding and sweeps (not reproduced) | `/proc/PID/status` VmRSS |
| Seed 500 board objects | 52 s through `POST /whiteboard/objects` (104 ms each) | PHASE=board |
| 20-note bundle | `POST /backups/bundle` 0.09 s, 46,214 bytes: `memorymap.db` (692,224 bytes, 57 tables) plus every file under `media/` and `uploads/` (here one 67-byte png) | `.venv/bin/python scratchpad/ui-sweeps/measure-bundle.py 8795` |

Static counts, from the code (`python scratchpad/ui-sweeps/measure-*.py`):

- **Dashboard** (`measure-widgets.py`, `measure-objects.js` PHASE=widgets):
  `DASH_WIDGETS` holds 29 widgets (the plan said 25); `featureCatalog` is a
  separate list of 125 rows. With all on, in a notebook of plain notes,
  stats, streak, heatmap and pace hold no button, link or row; the other 25
  hold at least one. Not run with reminders or bookmarks present.
- **Settings** (`measure-settings-help.py`): `PreferencesBody` has 72 fields
  (86 distinct keys are read or written through `get_preference` and
  `set_preference` in `src/tessellate/`; the plan's 179 is not a count of
  either). `index.html` holds 105 `data-help-for` popovers, 69 of them
  inside the Settings modal. By the script's rule (a popover in the same
  `<h3>` block as the control, else a muted line within four lines): 31 keys
  have a popover, 0 a plain help line, 10 have neither (`recycle_bin_days`,
  `conversation_retention_days`, `search_min_similarity`,
  `search_relative_z_margin`, `communication_style`, `display_name`,
  `web_search_enabled`, `searxng_autostart`, `session_idle_ttl_minutes`,
  `searxng_url`), and 31 have no Settings control the script could find.
- **Keyboard** (`measure-keys.py`): `DEFAULT_SHORTCUTS` has 31 entries (the
  plan said 36). 574 `.key ===`-style checks in 62 files: 513 test a
  convention key the table leaves unrebindable, 14 a letter that ends a table
  chord, 47 any other literal (`whiteboard.js` 8, `settings-panes.js` 5,
  `documents.js`, `whiteboard-library.js`, `settings-wiring.js`, `library.js`
  and `timeline.js` 4 each, the rest 3 or fewer). `toLowerCase()` and
  `switch (e.key)` forms are not counted.
- **Undo** (`measure-undo.py`): 50 functions with "undo" in the name in 21
  files, 13 of which call `pushUndo` (called from 27 files). The rest: the
  `wb*Undo*` set in `whiteboard.js`, `docUndo*` in `documents.js`, `undoDraft`
  in `chat-agent.js`, `inlineAiUndo`, `undoSkillRun`, `undoImport`, the
  activity feed's `activityUndo*`, and `undo-store.js` (IndexedDB).
- **Search index** (`src/tessellate/search/index.py:46`): `KINDS = ("note",
  "document", "board", "map", "file", "bookmark", "reminder")`, eight
  sources registered (lines 665 to 746; two for `file`). `GET /search` calls
  `engine.search` (`routes_search.py`), not `search_manager._retrieve`, which
  is Ask's notes-only path. Chat messages are not indexed. A live call
  returned `counts: {note: 5003, document: 1, board: 1, map: 0, file: 0,
  bookmark: 0, reminder: 0}` and a board among the hits for "measure".
  A "Find anything" dialog already calls it (`spaces-find.js:907`,
  `index.html:705`); the notes list also calls it with
  `kind=note,board,map` (`notes-list.js:1727`).
- **History**: `api/versioning.py` is the `/api/v1` prefix middleware and
  keeps nothing. Per-note history is `EntryRevision` (`core/database.py:1290`),
  full text and tags before each edit, `MAX_REVISIONS = 20` per note
  (`entry/manager.py:3468`), listed and restorable (`routes_entries.py:3095`,
  `:3241`), with a panel in `note-history.js`. Documents keep
  `DocumentRevision` (`:1547`), boards `whiteboard-history.js`.

## 25. The whole app against world class, 2026-10-10 (Fable)

The owner, 2026-10-10: "have you analysed the whole app and extended each
plan?? i need this app world class." Sections 23 and 24, CHAT_PLAN Phase 6,
UI Phase 12 and WHITEBOARD's draw.io programme each took one surface. This
section takes every surface, including the ones no plan owns (search,
import and export, first run, settings, the phone, data safety, performance,
undo, the keyboard), says what the bar is, what the code shows today, and
where the gap is owned. The gaps with no owner get phases 25a to 25g below
and Briefs 46 to 53.

**Limit, stated first.** The "today" column is read from the code (section
24's census, the route files, the function lists of `timeline.js`,
`phone-shell.js`, `status.js`, `notes-list.js`, `capture-ask.js`,
`editor.js`, `dashboard.js`, `search_manager.py`, `sw.js`,
`settings-wiring.js`) and the plans, not from a browser. Brief 46 measures
every row before anything in 25a to 25g is built; a row's number replaces
its reading here when it lands.

### 25.1 The bar

World class for a local notebook is five things, each measurable:

1. **Nothing is lost.** A crash, a power cut, a bad update or a wrong click
   never costs a note; every destructive act has an undo with a window and
   a history; restore is tested, not trusted.
2. **Every task takes the fewest motions,** and all of them work from the
   keyboard. The reference is VS Code's command palette and Things' capture:
   one key to start, type, Enter, done.
3. **The app answers from the notes without a model, and better with one**
   (ROADMAP Direction, "two engines, one answer").
4. **Each surface stands against the best single-purpose tool** a person
   could pick instead (the parity programme), and shares one object model.
5. **It is one product:** one vocabulary (section 1), one density (Phase
   12), one undo, one search, one help.

### 25.2 Surface by surface

| Surface | The bar (reference) | Today, from the code | The gap, in one line | Owner |
| --- | --- | --- | --- | --- |
| Capture | Drafts, Apple Notes: one key, type, filed on save | `capture-ask.js` 72 functions: tag suggestions, templates, document adder, filing status | the filing decision is not explained or confidently shown (23) | Brief 39b |
| Notes list | Bear, Obsidian: instant at 10,000 notes, an inline query | measured: 261 ms from tab switch to rows at 5,003 notes (61 rows in the DOM); a query keystroke to rows changed 168 to 260 ms; `notes-list.js` 94 functions (24.6b) | the query grammar is invisible; no bulk actions; paint cost at 5,000 unmeasured (Brief 43 item 2 found a 23 s badge) | 25a, Brief 43 |
| Note editor | Obsidian, Bear: live preview, slash, wiki links, backlinks, outline | `editor.js` 65 functions: slash menu, link matches, selection bar, inline AI | one editor everywhere (DOCUMENTS Phase 8) still open; find and replace inside a note | Brief 42 |
| Documents | Word, Notion, Typora | measured: 740 ms to open 50,001 words; `documents.js` 20,621 lines, `build` cx 189 (24.6b) | DOCUMENTS 17, 20, 21 | Brief 42 |
| Code editor | VS Code | `documents-code.js` 4,399 lines, `docCodeScan` cx 132 | multi-cursor, regex find and replace, folding, bracket pairs, diagnostics (DOCUMENTS 21) | Brief 42 |
| Whiteboard | draw.io, Excalidraw, tldraw | measured: 500 objects open in 2,551 ms first, 55 to 100 ms after; `whiteboard.js` 19,811 lines, `initWhiteboard` 3,730 (24.6b) | WHITEBOARD "The draw.io programme"; split along seams (45 part 2) | Briefs 36, 44, 45 |
| Mind map | Coggle, XMind | `whiteboard-map.js` 9,195 lines | MINDMAP 13, 14 | Brief 36 |
| Graph | Obsidian graph, Logseq | `graph.js` plus `graph-canvas.js` 10,655 lines, `renderGraphSvg` 1,254 | GRAPH "The knowledge graph" open rows | Brief 38 |
| Timeline and calendar | Fantastical, Google Calendar agenda, Day One | `timeline.js` 59 functions: feed and table, scrubber, day notes, a month popover | no month grid, week view, drag to reschedule, reminders on the grid, ICS in and out | TIMELINE Phase 5 |
| Ask, no model | a grounded answer with numbered sources | `composer.py` 2,980 lines, `compose` cx 74 | CHAT Phase 6 | Brief 39 |
| Chat and agent | Claude, ChatGPT: a run you can read and resume | `chat*.js` 8,767 lines, `sendChatMessage` 1,079 lines | Brief 37; AGENT_SKILLS Phase E | Briefs 37, 54 |
| Search | Spotlight, Alfred, Obsidian search: one box, every kind, operators, saved | measured: `GET /search` already indexes notes, documents, boards, maps, files, bookmarks and reminders (not chat), and a "Find anything" dialog calls it; p50 1.8 to 5.0 s at 5,003 notes on a loaded machine (24.6b) | boards, maps, documents, files, chat and reminders are not in one box; the operators are undocumented; no saved searches; no result kinds | 25a |
| Filing, tags, properties, relations | Notion properties, Obsidian tags | section 23; `routes_properties.py`, `routes_relations.py`, `routes_tags.py` | 23; properties on every object (0.7 "one object model") | Briefs 39b, 38 |
| Library and files | Apple Photos, Finder | `library.js` 11,669 lines, `filterLibraryImagesGallery` 1,546 lines | structure (split, 45 part 2); the gallery's one function does everything | Brief 45, 43 |
| Dashboard | Craft, Notion home: continue and today | measured: 29 widgets; 4 are display only (stats, streak, heatmap, pace), 25 hold a button, link or row; `dashboard.js` 93 functions (24.6b) | no widget can name a measured use; see decision 51 | Phase 12 row |
| Reminders and tasks | Things, Todoist | `routes_reminders.py`, `routes_tasks.py` (`collect` cx 71), the tray | recurring, snooze, natural dates everywhere, delivery when the window is closed | TIMELINE Phase 5 |
| Settings | VS Code settings: searchable, each with a description and a default, reset per item | measured: `PreferencesBody` 72 fields; 105 help popovers (69 in the Settings modal); 10 keys with a control and no help; a settings search box already exists (`settings-find.js`) (24.6b) | no search across settings; no modified marker or per-item reset; no settings export | 25f |
| Help and guide | a searchable manual with a "?" on every control | 51 plus 35 Guide topics; `test_manual_parity`; the manual (25c, built 2026-10-11) | "what changed" is Settings, About, What's new (CHANGELOG, already built) | 25c |
| First run | Linear: value in 60 seconds, the model optional and said so | `first-run.spec.js`, the first steps and the sample notebook (25c, built 2026-10-11) | the first-run queue still asks three questions before the dashboard (welcome, recovery key, updates) | 25c |
| Settings | VS Code settings: searchable, each with a description and a default, reset per item | measured: `PreferencesBody` 72 fields; 105 help popovers (69 in the Settings modal); 10 keys with a control and no help; a settings search box already exists (`settings-find.js`) (24.6b) | built 2026-10-11 (25f): rows, reset, the settings file | 25f |
| Help and guide | a searchable manual with a "?" on every control | 51 plus 35 Guide topics; `test_manual_parity` | no offline manual page with search; no "what changed" | 25c |
| First run | Linear: value in 60 seconds, the model optional and said so | `first-run.spec.js`, `gettingStartedCard`, the name nudge | no sample notebook; the three-step path is implicit | 25c |
| Import and export | Obsidian, Notion, Evernote, Apple Notes in; a markdown folder out | `app_import.py` (five sources, a Tessellate folder the fifth), `export_folder.py` (the whole notebook as a markdown folder with sidecars and attachments, `GET /export/folder`), the import report page, web clip, media upload; export per note `.md`, per document md, zip, docx; backups and a bundle | built 2026-10-10 (25b); left: a 5,000-note write is 45.9 s on the loaded sandbox (one commit per note) | 25b |
| Data safety | never lose a note | measured: bundle is `memorymap.db` (all 57 tables) plus `media/` and `uploads/`; per-note history is `EntryRevision`, 20 per note, with a panel; `versioning.py` is the `/api/v1` middleware (24.6b) | restore is not verified by a test; no integrity check at boot; versions not visible per note; crash recovery of a draft unmeasured | 25e |
| Phone and PWA | installable, an offline shell, a share target | `phone-shell.js` 2,139 lines; `sw.js` 59 lines and by design no cache (a transparent worker) | no offline shell; the hashed asset URLs make a safe cache possible now (decision 49) | 25d, Brief 40 |
| Performance | VS Code: boot under a second on old hardware | measured: boot 10.5 s DOMContentLoaded and 4.5 s to interactive on a saturated machine; idle server 63 to 66% of a core with the dashboard open, 2 to 16% on Notes; 319,799 bytes gzipped over 27 scripts (24.6b) | budgets exist for weight only; none for interaction time | 25g |
| Accessibility | WCAG 2.2 AA | Phase 12 | Phase 12 | Brief 41 |
| Security | a stated threat model | section 12; CSP; the LAN mode (Brief 40 placed) | rate limits on auth; session expiry; the threat model written down | 12 addendum |
| Undo | one model: Ctrl+Z where focus is, an undo bar for server actions | measured: 50 "undo" functions in 21 files, 13 call `pushUndo`; the others are the board, document, chat draft, inline AI, skill run and import implementations (24.6b) | six implementations, no contract | decision 53 |
| Keyboard | every action reachable; a generated shortcuts sheet | measured: `DEFAULT_SHORTCUTS` 31 entries; 574 key checks, 513 conventions, 14 table keys, 47 other (24.6b) | the 549 checks are the ones not in the table; the sheet must be generated from the table | Phase 12 row |
| Languages | one | English only; no i18n layer | decision 50 | none |
| OCR workspace | Google Keep's OCR, Apple Live Text | measured 2026-10-10: 22 to 25 controls, 98 to 240 ms to open, 0 of 5 reading acts undo (28.4) | not in quick access; the palette row says "AI"; no undo; no pinch zoom | 28.4, Brief 79 |
| Audio: meetings, transcription, captions, translator | Otter, Voice Memos, Live Captions, Apple Translate | measured 2026-10-10: Record refuses with no Whisper add-on; no live captions; no offline translator (28.5) | the recording is not an object; the meeting summary needs a model | 28.5, Briefs 80 to 83 |

### 25.3 Decisions, 2026-10-10 (do not re-decide)

46. **One search box, every kind.** Search is a surface, not a filter on the
    notes list: notes, documents, boards, maps, files, chat turns and
    reminders in one result list with a kind chip each, the operators
    (`tag:`, `in:`, `before:`, `after:`, `has:`, `is:`, quotes, minus)
    documented in the box's help, and saved searches as sidebar rows. The
    engine stays `search_manager.py`; the box is new.
47. **The calendar is the timeline's third view** (feed, table, calendar),
    not a surface. Month and week grids, reminders and day notes on the
    grid, drag to reschedule; ICS export of reminders and ICS import as
    reminders. No external calendar sync before 1.0.
48. **Milestone 0.5 is data safety.** Nothing in 0.6 ships before the
    restore test (25e) is green in CI.
49. **The service worker caches by stamped URL only.** Every local CSS and
    JS URL is `?v=<version>-<hash>`, so a cache keyed on the full URL can
    never serve a stale file; the shell (`/`, the manifest, the icons) is
    cached with a network-first fetch. This reverses the 2026-09 "no cache"
    decision because its reason (stale files) is gone.
    *Reconciled 2026-10-10:* it agrees with the owner's "fail to load when the
    backend is closed" once the offline answer is an honest page
    (`offline.html`, with Retry); the shell itself stays uncached.
50. **English only to 1.0.** No i18n layer before a second language is
    asked for; copy stays where it is used.
51. **The dashboard is "continue and today".** A widget stays if Brief 46
    can name a measured use (opened, clicked, or the thing it shows acted
    on); the rest move behind "Customise", off by default.
52. **Settings get search, a modified marker and reset per item before
    any new setting is added.** A setting is a row with a name, one line of
    description, its default, and a reset; the panes stay.
53. **One undo contract,** added to section 1 as rule 1.9: Ctrl or Cmd+Z
    undoes the last edit where focus is; a destructive server action shows
    the undo bar with a ten-second window and a history; nothing else
    invents an undo. The six implementations fold into `pushUndo`.
54. **Budgets are per interaction,** not only per byte: boot to first
    paint, first interaction, list paint at 5,000 notes, search at 5,000
    notes, board open at 500 objects, document open at 50,000 words, each
    with a number in `tests/test_budgets.py` run on the fixture, measured
    on the four-core sandbox and set at 1.5 times the measurement.

### 25.4 Phases with gates (each a brief; measure first)

| Phase | Builds | Gate | Brief |
| --- | --- | --- | --- |
| 25.0 Measure | the "today" column: every row's number with its command or sweep (`errors.js`, `routes_bench`, `getBoundingClientRect`, timings) | the table above re-written with numbers; section 24.6 extended | 46 (Sonnet, medium) |
| 25a Search | the box (`search.js`, new, lazy), the result list with kinds, the operators and their help, saved searches, keyboard-only use; documents, boards, maps, files, chat and reminders indexed through the existing engine | a sweep that finds one of each kind by query; operators tested in `test_search_box.py`; under 100 ms at 5,000 notes | 47, built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (WORLD_CLASS 25a, Brief 47)") |
| 25b Import and export | built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (WORLD_CLASS 25b, Brief 48)") | export then import of the 500-note fixture equal on every field; the report lists every skip | 48, built: 0 differences on 503 notes and boards, 60 of 60 attachments, 5 of 5 skips named, Stop in 0.005 s |
| 25c First run and help | built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (WORLD_CLASS 25c, Brief 49)") | `first-run.spec.js` extended; the manual page's search finds every control name (`test_manual_parity`) | 49, built: 41 of 41 named controls found (35 before), first note found again in 11 acts without the name step, every one on screen |
| 25d PWA shell | built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (WORLD_CLASS 25d, Brief 50)") | offline reload shows an honest page, never the shell; an edited file is never served stale (two stamps are two cache keys, `test_two_stamps_for_the_same_file_are_two_cache_keys`) | 50 (Sonnet, high) |
| 25e Never lose a note | the restore test in CI (backup, restore into a scratch dir, compare counts and bodies), an integrity check at boot with a one-line notice, per-note versions visible (a "Versions" row in the note menu, from `versioning.py`), draft recovery after a killed server | `test_restore_roundtrip.py` green; a killed server loses no typed draft (a Playwright test) | 51, built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (WORLD_CLASS 25e, Brief 51)"): restore equal for ten kinds, quick_check 30 ms at 5,000 notes, draft spec 1 passed, undo lint 10 to 7 |
| 25f Settings | built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (WORLD_CLASS 25f, Brief 52)") | every setting reachable by search; `test_settings_rows.py` walks every key (75, not 179) | 52, built: 60 of 60 shown rows found by search, 60 of 60 cleared by reset, 33 of 33 back to the server default, file round trip 0 differences |
| 25g Budgets | built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (WORLD_CLASS 25g, Brief 53)") | the six numbers in the README's performance table; CI fails when one exceeds its cap | 53, built: first paint 713 ms, first interaction 4,639, list 139, search 30, board 108, document 359; caps 1.5 times each |

Phase E of AGENT_SKILLS_REFORM (Brief 54) and TIMELINE Phase 5 (Brief 55)
are written in their plans.

### 25.5 Not verified

Everything in 25.2's "today" column until Brief 46 lands. In particular:
whether `routes_search` already indexes documents and boards (the engine's
`_retrieve` may; the box does not show it); whether `versioning.py` keeps
per-note history or only edit stamps; whether the bundle export is a
complete notebook.

## 26. The backend against world class, 2026-10-10 (Fable)

The owner, 2026-10-10: "after your design review, do the same for the
backend." Sections 4 (B1 to B7), 12 (security), 16 (structure and silent
failure), 19 (architecture) and 22 (the professional baseline) each read a
part. This section reads the whole, with today's numbers, and places the
gaps.

**Measured from the code** (not run): 470 routes over 58 router files
(entries 55, files 43, settings 40, documents 32, whiteboard 25); 54 routes
with no test naming their path (census 24.5: documents 12, entries 10,
board library 6, conversations 6); 223 Python files, 131,372 lines, 3,674
functions, 128 over 80 lines; 306 `except Exception` of which 21 end in
`pass`, `continue` or `return None` with no log line; 6 bare `except:`;
461 log calls; 36 `print(` outside the CLI; 32 thread or executor sites;
21 tables; 44 indexes; WAL, foreign keys on, `busy_timeout` 5000,
`synchronous NORMAL`, `temp_store MEMORY`; one worker enforced
(`refuse_multiple_workers`); the error envelope (`detail`, `code`, `hint`,
`ref`); cursors, ETags and `/api/v1` (B7); the event log (B1), durable jobs
(B2) and the retrieval engine (B3) built; the kernel (B4) and harness (B5)
part built; sync (B6) designed only.

### 26.1 Judgement, by layer

| Layer | The bar | Today | Judgement |
| --- | --- | --- | --- |
| Routes | thin: parse, call a service, shape the answer | `routes_whiteboard.py` 5,428 lines (128 functions, `_board_preview` 198 lines renders a preview inside a route file); `routes_entries.py` 3,835; `routes_files.py` 3,931 (`analyse_attachment` 181 lines); `routes_chat.py` `_stream_lines` 289 lines, cx 86 | business logic lives in the route files; only `entry/manager.py` is a service in the proper sense. Services per domain (board, document, file, chat) are the structural fix, and the route tests already prove behaviour unchanged |
| Services and domain | one module per domain, tested directly | `entry/manager.py` 3,519 lines, 138 functions, `_hard_delete` 179 lines | the one service is itself a monolith; split along entries, filing, links, deletion |
| The AI package | small modules, data out of code | 60 flat modules; `question_noise.py` 5,242 lines and `composer_tables.py` 2,034 lines are tables written as Python; `tools/__init__.py` 4,878 lines holds 67 tools and their execution; `agent.py` `run_agent` 416 lines, cx 78; `skill_runner.py` `_run_one_step` 425 lines | data as code costs import time (triage measured `composer` 0.75 s cold, 0.08 s after lighter imports) and makes a table edit a code review; one file per tool family; `run_agent` and `_run_one_step` are the two functions most in need of a state machine |
| Errors | every failure names its way out (section 21); nothing swallowed silently | the envelope is built; 21 silent swallows; 36 prints | a lint ratchets swallows to zero (each becomes a narrower exception or a log line with the reason); prints to the logger |
| Data | SQLite tuned; every FK indexed; migrations for every schema change; versions derivable | pragmas right; 44 indexes on 21 tables; the alembic baseline; the event log holds every write | per-note versions from the event log (25e) rather than a new table; an index audit (every FK and every column in a `WHERE` of a hot query) is Brief 60's |
| Background work | every thread is a job: durable, visible, stoppable | B2 covers the pool's kinds; 32 thread sites remain ad hoc (embedding, warm-ups, watchers, the tray) | a registry: a thread not started through `jobruns` or a named `core/background.py` entry fails a lint; every entry has a stop |
| Concurrency | one writer, SQLite's rules respected | one worker enforced; `busy_timeout` 5 s; `edit_conflicts.py` and ETags | sound; the risk is a long write inside a request (imports, bulk moves): those go through jobs |
| API | one contract, versioned, documented | B7 built; OpenAPI behind the unlock | the page should read `/capabilities` once (B7's left row); the 54 untested routes get a test each or are removed |
| Security | section 12 | unlock middleware, Host and Origin checks, CSP, the space guard, the media router's own dependency | rate limit on `/auth`, session expiry, a written threat model for LAN mode (Brief 40) |
| Performance | idle under 1 percent CPU, resident under 300 MB without the embedding model | 776 MB resident idle measured 2026-09-20 (19.1), mostly the embedding model; idle compute fixed (19.4) | Brief 46 re-measures with and without the embedder; the model loads lazily on first use |
| Tests | every route named by a test; the specs strict-xfail | about 9,000 tests; 54 routes untested; e2e 11 specs; five spec files | the 54; a property test for the composer's realiser (Phase 6) and for `when.py` |

### 26.2 Decisions, 2026-10-10 (do not re-decide)

55. **Routes are thin.** A route parses, calls one service function, shapes
    the answer. Services live in `src/tessellate/<domain>/service.py`
    (board, document, file, chat, settings), each tested directly; the
    route tests stay as they are and prove no behaviour changed. Extraction
    order: whiteboard, files, entries, chat.
56. **Data is data.** Tables (`question_noise`, `composer_tables`, the help
    topics) are JSON under `src/tessellate/data/` (the taxonomy stays under
    `src/tessellate/ai/data/taxonomy/`, 23.1), loaded
    lazily and cached; `tests/test_import_time.py` caps `import
    tessellate.ai.composer` at 0.2 s cold and the app's import at 1.5 s.
57. **No silent swallow.** `except Exception` ends in a log line with the
    reason and the way out, or becomes a named exception;
    `tests/test_no_silent_except.py` ratchets 21 to 0. `print` outside the
    CLI fails ruff (`T201`).
58. **Every background thread is a job or registered.** `core/background.py`
    holds the registry (name, started, stop); `jobruns` for anything with
    progress; a lint fails a `threading.Thread(` outside the two.
59. **Every route has a test naming its path**, or it goes.
    `tests/test_routes_named.py` is the ratchet, seeded with the 54.
60. **Versions come from the event log,** not a versions table (25e).
61. **The two long runners become state machines:** `run_agent` and
    `_run_one_step` each as a `Step` enum with one function per state, so a
    stage can be tested alone; Phase E (AGENT_SKILLS) builds on it.
62. **The embedder loads on first use** and unloads after an idle hour
    (a setting, default on); the resident number is measured before and
    after.
63. **A complexity and per-frame census, with ratchets** (the owner, 2026-10-10, INBOX 756: "do the same for the backend. do architectual analysis. look for high complexity and high volumes of excessive calculations per frame etc."). Backend: cyclomatic complexity over `src/` (radon, or the `ast` walk in `scripts/complexity.py` if radon is not vendored), every function over 15 listed with its file and line, the ten worst named in 26.1, and a ratchet at today's count; import graph cycles listed; the hot routes profiled under `cProfile` with the showcase notebook, the top ten by cumulative time recorded. Frontend: every `requestAnimationFrame`, `pointermove`, `scroll`, `wheel`, `ResizeObserver`, `MutationObserver` and `setInterval` handler in `frontend/js` listed with its file and line and what it recomputes; a Chromium performance trace on the whiteboard, the graph, the mind map and the companion at rest and under a drag, long tasks over 50 ms and frames over 16 ms counted, layout thrash (a read after a write in one handler) found by `scratchpad/ui-sweeps/frames.js`; a ratchet on the at-rest frame work (zero long tasks at rest on every surface). Findings become rows in the surface plans, never fixes in the census commit.

### 26.3 Phases with gates

| Phase | Builds | Gate | Brief |
| --- | --- | --- | --- |
| 26.0 Measure | decision 63's complexity and per-frame census; import times, resident memory with and without the embedder, the index audit (every FK and hot `WHERE`), the 54 untested routes listed, the 21 swallows listed, the 32 thread sites classified | numbers in this section | 60, built 2026-10-10 (26.4 and 26.5 hold the numbers) |
| 26a Lints | decisions 57, 58, 59 as ratchets; the prints folded | all three green with their seeds | 60, built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (WORLD_CLASS 26.0 and 26a, Brief 60)"): seeds 21, 49, 26; complexity 260 over 15; wake sources 97 rows |
| 26b Services | decision 55 for whiteboard and files | route tests unchanged and green; `routes_whiteboard.py` under 1,500 lines | 61, built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (SESSION_BRIEFS triage, briefs-1011)"): 5,808 to 1,438 lines; files 4,028 to 1,905; entries and chat left |
| 26c Data | decision 56 for the four tables; the import-time test | `test_import_time.py` green; the composer eval unchanged (grounded 1.0) | 62 (Opus, high) |
| 26d Runners | decision 61; the embedder's lazy load (62) | the agent and skill tests unchanged; the resident number recorded | 63 (Opus, high); 62 built 2026-10-11: 491 MB loaded, 376 MB after the idle unload, reload 3.2 s (HISTORY "Brief 63 part 1, the embedder") |

### 26.4 Measured, 2026-10-10 (Brief 60, numbers only)

Machine: 4 cores at load average 4 to 9 from other sessions, so every wall time is a loaded figure. The scripts are in the Brief 60 report; the three counts that became ratchets are in `tests/`.

| Measure | Number | Note |
| --- | --- | --- |
| `import tessellate.api.app`, cold | 2.9 to 3.8 s (3.3 s under `-X importtime`), 205 `memorymap` modules, torch not loaded | decision 56 caps this at 1.5 s: not met |
| Heaviest `memorymap` imports (cumulative / self) | `ai.autonomous` 767 / 0 ms (pulls `ai.agent` 503), `ai.help_chat` 271 / 261, `api.routes_search` 226 / 226, `api.routes_chat` 148, `core.database` 145, `api.routes_documents` 146, `api.routes_whiteboard` 135, `api.routes_files` 129 | `fastapi.openapi.models` 128 |
| Import of single modules | `ai.composer` 0.11 s, `ai.question_noise` 0.02 s (cap 0.2 s: met), `ai.agent` 0.94 s, `search.engine` 0.62 s | standalone, after `ai.agent`'s own deps |
| Resident memory, empty notebook | 11 MB bare interpreter; 108 MB after import; 129 MB after startup; 130 MB after 5 s idle | embedder not loaded at startup (torch and sentence_transformers absent from `sys.modules`) |
| Resident memory with the embedder | 647 MB after the first `embed_text` (`BAAI/bge-small-en-v1.5`, torch 2.14 CPU), first embed 6.6 s | so the embedder is already lazy on an empty notebook; the 776 MB of 19.1 included a notebook's warmed matrix and a loaded model. Not measured: a populated notebook (the warm-up thread loads the model when vectors exist) |
| Tables / explicit indexes / foreign keys | 56 / 78 / 29 (the plan's 21 and 44 counted ORM classes and named indexes) | |
| Foreign keys with no index leading on the column | 5: `entity_mentions.entry_id`, `entity_mentions.entity_id`, `document_bookmarks.document_id`, `document_bookmarks.bookmark_id`, `entry_bookmarks.bookmark_id` | deleting an entry or entity scans `entity_mentions` |
| `Model.col` filter pairs in `src` with no leading index | 64 of 125; most used: `entries.is_deleted` x121, `entries.is_private` x54, `entries.is_board` x37, `entries.is_draft` x21, `audit_log.entity_id` x16, `entries.content` x15 (a `LIKE`), `categories.name` x9, `documents.archived_at` x9 | flags are low-cardinality, so a partial index on live entries is the candidate, not one per flag; `audit_log.entity_id` and `entity_mentions.*` are the plain misses. Not measured: query plans at 5,000 notes |
| Routes | 498 method and path pairs, 437 distinct paths (FastAPI 0.143 route table, `include_router` prefixes counted) | the 470 of the opening paragraph came from a decorator regex |
| Routes whose path no test names | 49 (census 24.5 said 54 and undercounts: its `{param}` wildcard matched any run of characters) | seeded in `tests/test_routes_named.py`; documents 14, entries 9, conversations 6, board library 5, whiteboard 4, reminders 2, categories 2, tidy 2, one each for learned, media, models, questions, review-queue. Path match only: a route reached by a loop over verbs (`f"/documents/{id}/{verb}"`) counts as unnamed |
| Broad `except` (bare, `Exception`, `BaseException`) | 315, of which 0 bare, 237 carry a `# noqa: BLE001` reason | |
| Broad `except` that neither logs nor re-raises | 89; 21 of those end in `pass`, `continue` or `return None` | the 21 are seeded in `tests/test_no_silent_except.py`; the other 68 return a fallback value and are not ratcheted |
| `print(` outside the command line | 0 in `src` (25, all in `__main__.py`); 71 in `scratchpad/`, 1 each in four tests | the plan's 36 was wrong; ruff `T201` is on for `src` with `__main__.py` exempt |
| Thread, timer, executor and task sites outside `core/jobs.py` and `core/jobruns.py` | 26: 4 server and tray (`__main__`: boot thread, two serve tasks, tray), 7 user-started long jobs (autonomous 2, model pull, embedding download, SearXNG install, update 2), 8 startup and one-shot helpers (embedding warm-up, package auto-install, SearXNG start, model-list probe, DNS probe, filing-chat deadline, SearXNG pump, web prefetch executor), 2 timers (shutdown, durable-queue resume), 5 request background tasks | seeded in `tests/test_background_registry.py`; `core/background.py` does not exist yet, so no site is registered, only counted |

### 26.5 Complexity, cycles, hot routes and frames, 2026-10-10 (decision 63, numbers only)

| Measure | Number |
| --- | --- |
| Functions over cyclomatic 15 (`scripts/complexity.py`, same rule as 24.1) | 260 of about 3,700; 133 over 20, 49 over 30, 12 over 50. Seeded in `tests/complexity_seed.json` by `tests/test_complexity.py` (new or growing fails, shrinking is forced) |
| The ten worst | `ai/factgraph.py::_note_facts` 105, `api/routes_chat.py::_stream_lines` 105, `ai/agent.py::run_agent` 78, `ai/composer.py::_compose` 72, `api/routes_tasks.py::collect` 71, `api/routes_chat.py::_plain_events` 70, `search/engine.py::search` 69, `ai/recognise.py::span` 66, `ai/composer.py::_follow_one` 65, `ai/lexical_filing.py::decide` 59 (then `search_manager._retrieve` 57, `skill_runner._run_one_step` 53) |
| Import cycles | none at load (235 modules, 922 edges); one group of 20 modules (the `ai` package) when imports inside functions count; both held by `tests/test_complexity.py` |
| Hot routes, cProfile in-process (`scripts/profile_routes.py`, the README showcase notebook: 71 notes, 3 documents, a board, a map, 4 chats), median of 5 | `/entries` 52 ms (109 KB), `/insights/patterns` 28, `/categories` 28, `/resurface` 26, `/documents` 24, `/activity` 23, `/graph` 22 (45 KB), `/most-opened` 22 (2 bytes), `/insights/stats` 19, `/search` 13. A 2-byte answer costs 22 ms, so the middleware chain is the floor, not the route |
| Top of the profile (cumulative, app code only) | `list_entries` 59 ms a call, of it `_to_out_bulk` 26 ms and `_to_out` 0.48 ms a note (375 calls) with `_tag_reasons` 0.11 ms a note; `insights.from_session` 19 ms; `graph._payload_key` 10 ms of the graph's 10; `links_for_entries_bulk` 5 ms. `_to_out` at 0.48 ms a note is about 2.4 s for a page of 5,000 notes: not measured at that size |
| Frontend wake sources (`python scripts/handlers.py`) | 138 `requestAnimationFrame` (whiteboard.js 18, documents.js 14, avatars.js 9), 58 `pointermove`/`mousemove` (whiteboard.js 15), 35 scroll, 7 wheel, 31 `ResizeObserver` (library.js 5), 38 `MutationObserver` (avatars.js 5), 9 `IntersectionObserver`, 12 `setInterval`. Always on: `atlas.js:3624` mood check, `avatars.js:6198` every 1.5 s, `bg-art.js:1991` covered and idle check, `status.js:829` reminder poll; the rest run only while a timer, a meeting or a focus session is open. Per-file counts of four kinds are seeded in `tests/wake_sources_seed.json` (`tests/test_frontend_wake_sources.py`) |
| Frames, `scratchpad/ui-sweeps/frames.js`, 3 s each, companion off except its own row, load 5 to 9 on 4 cores | whiteboard rest 0 long tasks, 0 gaps over 20 ms; drag 1 gap over 20 ms of 253. Mind map rest 0 and 0; drag 4 gaps over 20 ms of 605, 1 long task of 50 ms. Graph rest 1, 9 and 10 long tasks (58 to 70 ms each, script 150 to 170 ms a second) and 38 to 52 gaps over 20 ms; drag 12 to 44 of 302, 0 to 4 long tasks. Companion (Atlas) rest 4 to 6 long tasks and 37 to 45 gaps over 20 ms; the pointer sweep and wheel 201 to 510 gaps over 20 ms of 278 to 611, 7 to 58 long tasks, worst gap 250 to 367 ms |
| At-rest ratchet | `REST_BUDGET` in `frames.js`: whiteboard 0, mind map 0, graph 10, companion 6 long tasks in 3 s; the sweep exits 1 above it. The target is zero on all four; graph and companion are the two to fix |

Not verified: the frame figures are one machine under load (a quiet re-run is the number to trust); the `recalcs` counter equals the frame count on every surface including a control, so it is not read as a finding; the companion row is a pointer sweep, because the companion has no drag; the profile runs sync handlers inline (no thread pool), so it is a single-request figure.

## 27. Every feature, its utility and its popups, 2026-10-10 (Fable)

The owner, 2026-10-10: "then a pass for the features, implementation,
utility, and everything to do with each main feature and popup and stuff in
the app." Section 25 placed each surface against its bar; this section
reads what each feature offers and where its utility is thin, and takes
the popups one by one.

**Measured from the markup and the code:** 15 `<dialog>`s; kebab menus from
one recipe at 38 call sites (library 12, documents 4, chat 4); the note's
overflow menu carries about 30 items; 49 slash commands in the editor; 67
tools in the registry (56 shown to MCP); up to 30 skills; four import
sources; three export shapes per document and one per note.

### 27.1 Feature by feature: what it offers, what a professional expects, the gap

| Feature | Offers today | Expected and missing | Place |
| --- | --- | --- | --- |
| Notes | capture, filing, tags, categories, spaces, properties, relations, wiki links, backlinks, history, duplicate, translate, remind, attach, move, download `.md`, explain, improve, expand into a document, add to a board | find and replace in a note; bulk edit (tags, category, properties) from a selection; pin and archive as first-class states; a note's versions visible (25e); templates with variables | 25a (bulk), 25e, Brief 42 |
| The note menu | about 30 items in one list | a menu under nine items or grouped (1.3); the AI items as one "Atlas" group, the structure items as one, the destructive at the end | Brief 59 |
| Filing | taxonomy votes to existing categories, model filing, the no-model keyword map, explanations in section 23 | confidence shown and a one-press correction that teaches (23); suggested merges of near-duplicate categories; a "why here" on every card | Brief 39b |
| Search | hybrid retrieval, graph expansion, learned order | one box, operators, kinds, saved searches (25a) | Brief 47 |
| Ask | grounded answer, citations as `[**Title**]` with peek, sources, evidence, figures, trail, as-of | the engine (Phase 6): acts, insights, a dialogue that holds; one foot (13.3 decision 22) | Brief 39 |
| Chat and agent | modes, attachments, tools, skills, plans, the rail, drafts with undo, compress | a run you can read and resume as a page (AGENT_SKILLS C); reliability per skill (E); the model-off state that says what still works | Briefs 37, 54 |
| Documents | blocks, tables, embeds, properties, columns, slash menus, live view, code mode, writing checks, history, AI history, dictionary, word goal, templates, storage, export md, zip, docx | DOCUMENTS 17, 20, 21; comments and suggestions as a review mode; outline navigation; find and replace with regex | Brief 42 |
| Code editor | CodeMirror 6, Emmet, scan | multi-cursor, folding, bracket pairs, diagnostics, a command palette inside the editor, format on save (DOCUMENTS 21) | Brief 42 |
| Whiteboard | the programme's 288 rows | the programme | Briefs 36, 44 |
| Mind map | MINDMAP 13 and 14 | MINDMAP 13 and 14 | Brief 36 |
| Graph | filters, display folds, local map, typed links, tensions | KG rows; a "what changed about X" | Brief 38 |
| Timeline | feed, table, scrubber, day notes, kinds | the calendar (Phase 5) | Brief 55 |
| Reminders and tasks | parse, due, snooze?, the tray, notifications | recurring, snooze with choices, natural dates in every date field, delivery when the window is closed, the calendar | Brief 55 |
| Library | gallery, OCR, vision, filters, activity | split (45); bulk tag and move; a file's places (which notes, boards) | Briefs 45, 43 |
| Dashboard | nine blocks | "continue and today" (decision 51) | Brief 59 |
| Settings | 75 keys, panes, help on 105; search, reset, modified, export built (25f) | appearance keys kept per browser (see agent-remaining/settings52-1011.md) | Brief 52 |
| Import | Notion, Obsidian, Evernote, Apple Notes, web clip, media | the report page, progress, a markdown folder in, the round trip (25b) | Brief 48 |
| Export | per note `.md`, per document md, zip, docx, the bundle | the whole notebook as a folder (25b); boards and maps as SVG and PNG with the notes they link; a document as PDF | Brief 48 |
| Backups | create, list, restore, bundle, schedule line, second-copy folder | the tested restore, the boot check (25e, built) | Brief 51 |
| Help | Guide chat, popovers, manual parity, the manual (25c) | none open here | Brief 49, built |
| Skills and tools | 67 tools, 30 skills, MCP | Phase E; one file per tool family (26) | Briefs 54, 63 |
| Spaces | create, edit, delete dialogs, the space guard | a space's own dashboard line and its export; moving a note between spaces with its links kept | Brief 59 row |
| Meetings | notes, summary | the redesign (INBOX 643, 644; ROADMAP "Next PR" item 1) | Brief 59 row |

### 27.2 The popups, one by one

| Popup | Kind today | Right kind | Note |
| --- | --- | --- | --- |
| `recovery-key-dialog` | dialog | dialog | irreversible; keep |
| `space-create-dialog`, `space-edit-dialog` | dialog | sheet | a form of two fields is a sheet, not a modal |
| `space-delete-dialog` | dialog | dialog | destructive; keep, with the undo bar after |
| `doc-storage-dialog`, `doc-template-dialog`, `note-template-dialog`, `wb-template-dialog` | dialog | sheet | pickers are sheets |
| `wb-import-dialog` | dialog | sheet with progress | an import is a job (26) |
| `quick-note` | dialog | sheet | capture from anywhere is a sheet at the bottom on the phone, a centred sheet on desktop |
| `doc-history-dialog`, `doc-ai-history-dialog` | dialog | panel | a history is read beside the document, not over it |
| `doc-word-goal-dialog`, `doc-dictionary-dialog`, `dash-widgets-dialog` | dialog | sheet | settings of one surface |
| the note overflow menu | kebab, about 30 items | kebab, grouped, under nine visible | decision 1.3 |
| the toast, the undo bar, the server-down banner, the AI-offline notice, the notifications panel | five channels | three (13.3 decision 21) | Brief 59 |
| the help popovers (98) | `data-help-for` | keep | one shape (Phase 12 decision 3) |
| the command palette | one recipe | keep; every action listed (13.1 row 7) | Brief 41 |

Brief 56 classifies the fifteen by the sweep; Brief 59 moves the ones
above. A dialog that stays is one that must interrupt (irreversible,
a key, a password).

### 27.3 Decisions, 2026-10-10 (do not re-decide)

63. **A popup is a dialog only when it must interrupt;** a form, a picker
    or a setting is a sheet; a history is a panel. The table above is the
    ruling for the fifteen.
64. **A menu over nine items is grouped,** and the note menu's groups are
    Atlas, structure, share, destructive, in that order.
65. **Bulk edit is a feature of selection,** not of each surface: the
    selection bar recipe gains tag, category, property, move and delete
    with the undo bar, and every list surface uses it.
66. **Exports are complete:** a board or map exports as SVG and PNG with
    the notes it links as a folder; a document as PDF (through the
    browser's print to PDF with a print stylesheet, no new dependency).

## 28. The trust contract, 2026-10-10 (INBOX 750)

The owner, 2026-10-10: "all of this makes me lose trust in the app and then
I dont want to invest my time and actual study notes or life notes into it".
Sections 25 to 27 say what each surface should be. This section says what
every surface must never do, as fourteen rules with a measure each. A brief
is done only when the rules below hold for the surfaces it touched (decision
68), so the rules are the acceptance bar, not another list.

### 28.1 The rules, each with its measure

| # | Rule | Measure (the sweep or lint, and its bar) |
| --- | --- | --- |
| 1 | **Undo and redo everywhere.** Every change on every surface is one undo step; Ctrl+Z and Ctrl+Shift+Z act on the surface that has focus; a destructive act shows the undo bar. | `scratchpad/ui-sweeps/undo.js`: the mutating actions per surface (from the act registry, CHAT_PLAN decision 51) against those that undo; bar 100%. `measure-undo.py` counts `pushUndo` today. today: 25 data-changing controls pressed in light, 5 undone by Ctrl+Z (3 of 16 in dark); in the code 80 of 274 server-writing functions name an undo path; settings 0 of 13 (28.4). |
| 2 | **Three clicks to anything.** Every surface, setting and object is three clicks from the dashboard and one from the palette or Find anything. | `reach.js`: the click graph from the nav, menus and palette registry; bar: no node deeper than 3, none missing from the palette. today: 55 destinations found from the dashboard (1, 14, 36, 3 and 1 at depths 0 to 4, crawl complete to depth 4), 1 deeper than 3, 16 with no palette command (of 80 commands); dark: 55 destinations, 1 deeper than 3, 14 without a command (28.4). |
| 3 | **Nothing is lost.** A change is saved within a second; a draft survives a crash and a reload; a deletion goes to the bin for 30 days; a backup runs daily by default and restores (section 25e, Brief 51). | `test_never_lose.py` and the backup round trip; bar: every path in the table of 25e green. |
| 4 | **An error explains and offers.** Every error-level toast says what happened, why, and one action (retry, an alternative, open the setting); network-level failures retry themselves first. | `test_error_toasts.py` extended: an error toast without an action fails; the retry count in `api()` measured. |
| 5 | **Background work is visible and stoppable.** One Activity panel lists every running job (indexing, embedding, model load, generation, imports, OCR, transcription, backups, the agent) with Stop; stopping the model unloads it (`keep_alive: 0` for Ollama, the managed runner killed). | `/activity` lists every registered job; a lint fails a long-running task that does not register; a sweep stops a generation and sees the model unload. |
| 6 | **Every feature can be found.** Each has a Guide topic, a palette command and a help popover; the dashboard offers one unused feature a week. | `test_manual_parity.py`; palette registry against the feature list; bar: none missing. |
| 7 | **Nothing clashes or overflows.** At 320, 390, 820, 1024, 1440: no clipped text, no sibling rects overlapping in a bar, no `scrollWidth` past `clientWidth` where nothing scrolls. | `overlap.js` added to `chrome.js` and `docks.js`; bar 0 per width. today (light, 12 surfaces; overflow / docks / clipped text): 320: 95 / 0 / 6; 390: 14 / 0 / 5; 820: 28 / 0 / 17; 1024: 30 / 0 / 19; 1440: 23 / 0 / 15 (28.4). |
| 8 | **The phone works, the iPhone first.** The app opens on an iPhone over the LAN (the certificate flow in Settings, Phone), installs as a PWA, and every surface is usable with a thumb. | A WebKit run of the sweeps at 390 by 844; the LAN certificate test; a release is blocked while the iPhone cannot open it (decision 67). |
| 9 | **WCAG 2.2 AA.** | `axe.js`, `srtree.js`, `zoom.js`; bar 0 findings per theme (Phase 12). |
| 10 | **One information architecture.** One vocabulary (DESIGN.md's terms table), the same act in the same menu position on every surface, settings grouped by task. | `test_ui_signatures.py` and a terms lint over `index.html`, the Guide and Settings; bar: every term from the table, none of its banned synonyms. |
| 11 | **One design.** Heights, alignment and spacing from tokens; a computed-style snapshot at every CSS phase gate. | `test_style_scale.py`; `snapshot.js` (ANALYSIS "Odysseus, fourth read" take 7); bar: no untokened length in the controls' computed styles. |
| 12 | **Excellent without a model.** Every feature keeps its surface and its deterministic path with no model configured; the AI adds, never gates. | the sweeps run once with no model; bar: no surface shows a dead control. |
| 13 | **A friend can start.** Install to first saved note in under five minutes with no terminal; the first run is one queue (Phase 12, Brief 37). | `learn.js` (UI_MODERNISATION 12z); a scripted first run on a clean profile. |
| 14 | **The notebook says how it is.** A Health page: the last backup, the last error, what is running, the data dir's size, an integrity check in one click. | `/health` fields and a sweep that reads the page; bar: every field present and dated. |

### 28.2 Decisions, 2026-10-10 (do not re-decide)

67. **The iPhone is a release blocker.** No release while rule 8 fails.
68. **The rules are the acceptance bar.** A brief's report lists rules 1, 2,
    4, 7 and 11 for the surfaces it touched with their numbers; a report
    without them is not done.
69. **Reminders reach the desktop and the browser without a push server.**
    The desktop launcher posts the operating system's notification for a
    due reminder (Windows toast, macOS and Linux notify); a browser tab or
    the installed PWA uses the Notification API while it is open; nothing
    goes through a third party (the offline rule). TIMELINE_PLAN carries the
    rows (Brief 72b).
70. **One Activity panel, one recipe.** Every long-running job registers
    with the same `jobs` service (start, progress, stop) and shows in the
    same `.dock` panel; the agent's run list (`agent-activity.js`) becomes a
    tab of it.
71. **The deepening is per feature, measured.** For each feature the owner
    named, its plan gains a "Deepened 2026-10-10" block: what renders today
    (measured), the professional bar, the detailed rows (fix, redesign,
    expansion, optimisation), each with its measure and the trust rules it
    answers. Written by Briefs 72a and 72b, built by the briefs they name.

### 28.3 Phases

| Phase | Brief | Deliverable |
| --- | --- | --- |
| T0 measure | 74 (Sonnet) | `undo.js`, `reach.js`, `overlap.js` written and run; the numbers into 28.1's rows |
| T1 deepen | 72a, 72b (Opus) | every named feature's plan deepened per decision 71 |
| T2 build | 73 (Opus) | the Activity panel and model stop (rule 5), the error contract (rule 4), the Health page (rule 14) |
| T3 hold | every later brief | decision 68 in every report |

### 28.4 Deepened 2026-10-10: the OCR workspace (Brief 72a, decision 71)

Measured with `scratchpad/ui-sweeps/deepen72a.js` (fresh data dir, no model,
no Tesseract, a 900 by 400 PNG of three lines, three runs; ranges across
runs). Today: 22 to 25 controls at 1440, 11 to 12 at 390; open 98 to 240 ms
at 1440, 474 to 1,335 ms at 390; 3 clicks from the dashboard (Library,
Files, the row); not in quick access; one palette row, "Read a document or
image with AI", though Tesseract and RapidOCR read with no model; 0 of 5
reading acts undo (save an edited reading, delete a page reading, clean
loops, a region read, an engine install; static read of `library.js`); at
1440 nothing overflows, at 390 2 to 3 controls sit past the right edge
(`ocr-reader`, `ocr-rapidocr-install`, "Install Tesseract"); with no engine
and no model the engine line says "Tesseract isn't installed. Install it
here, or start an AI model in Settings, to read pages." and offers Install;
2 AI controls stay enabled. Pinch zoom (the owner's bug) was not driven.
**The bar:** Google Keep's "Grab image text" (one tap, the text editable
beside the image), Apple Live Text (select words on the image in place),
Acrobat for highlights and comments on a PDF page.

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | **Found built 2026-10-10 (Brief 79 checked; `tests/test_ocr_workspace_717.py`)**: quick access, Find anything and the palette row "OCR workspace: read a document or image" | quick access present; palette 1 click; a search for "ocr" finds it | 2, 6, 10 |
| 2 | fix | **Built 2026-10-10 (Brief 79; HISTORY "WORLD_CLASS 28.4, Brief 79")**: undo for the five reading acts; a deleted reading goes to the bin (`BinnedReading`) | `ocr79.js` 0/5 to 5/5 at 1440 and 390 | 1, 3 |
| 3 | fix | **Built 2026-10-10 (Brief 79; HISTORY "WORLD_CLASS 28.4, Brief 79")**: pinch zoom about the pointer, Ctrl+wheel and two fingers | `ocr79.js`: Ctrl+wheel Fit to 150%, drift 0; touch at 390 Fit to 176% (nothing before) | 8, 11 |
| 4 | fix | **Built 2026-10-10 (Brief 79; HISTORY "WORLD_CLASS 28.4, Brief 79")**: the reader menu spans the window under 600; Read sheds its icon last | past the edge 3 to 0 at 390, 4 to 0 at 320 | 7, 8 |
| 5 | fix | **Built 2026-10-10 (Brief 79; HISTORY "WORLD_CLASS 28.4, Brief 79")**: RapidOCR first with its size, then Tesseract; Read, region Read and Describe `aria-disabled` with the reason | AI controls disabled with a reason 0/1 to 1/1, 0 dead | 12, 4, 13 |
| 6 | fix | Reading and installs are jobs in the Activity panel with progress per page and Stop (decision 70) | a 20-page PDF lists and stops | 5 |
| 7 | redesign | **Built 2026-10-10 (Brief 79; HISTORY "WORLD_CLASS 28.4, Brief 79")**: Live Text, each word of `extract_regions` over the picture | a drag-select copies 3 lines in order (regions answer stubbed) | 6, 12 |
| 8 | expansion | Highlights and comments on a PDF page stored in the notebook; the encrypted-PDF prompt; the outline panel verified (ANALYSIS, pdfcraft) | a highlight survives a reload; a locked PDF asks once | 3, 4 |
| 9 | optimisation | **Built 2026-10-10 (Brief 79; HISTORY "WORLD_CLASS 28.4, Brief 79")**: the dock fitted by halving, once per size | 390 open 398/246/683 to 353/127/387 ms | 13 |

Briefs: 37 (row 1), 42 (row 8's highlights), 73 (row 6), 79 (rows 2 to 5,
7, 9).

### 28.5 Deepened 2026-10-10: the audio set (Brief 72a, decision 71)

Meeting notes, transcription, live captions, translator. The decisions of
"Audio in the notebook" (1 to 5) stand. The go is taken (INBOX 759, the state line above).
Measured as 28.4: "New meeting" is 1 click on the dashboard and opens in 23
to 61 ms (7 controls); the meeting sheet opens in 27 to 39 ms with 4
controls; the recorder (palette "Record a meeting or lecture") in 7 to 17
ms with 4; nothing overflows at 1440 or 390. With no Whisper add-on Record
refuses before recording ("Voice notes need an add-on that isn't installed
yet...") so no audio is kept; Summarise ("Find the decisions and action items") stays enabled
and its route answers 503 with no model (read, not driven); 1 of 6 meeting
acts undo (Summarise; not create, remind, save into a note, save as a note
or a document). Live captions: none. Translator: none offline; a document's
"Translate this" hands the passage to chat (a model). Chromium's Web Speech
sends audio to a server, so it is out (the offline rule).
**The bar:** Otter (a live transcript with speakers and timestamps, a word
plays from its moment, summary and actions), Apple Voice Memos (record,
trim, a library), Windows Live Captions (on-device, over any app), Apple
Translate (offline language packs).

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | **Built 2026-10-10 (Brief 80; HISTORY "WORLD_CLASS 28.5, Brief 80")**: a recording is an object (`recordings`, decision 2); transcription only with the add-on | no add-on: a 5 s take kept, "Saved a 0:05 recording (webm)" | 12, 3 |
| 2 | fix | **Built 2026-10-10 (Brief 81; HISTORY "WORLD_CLASS 28.5, Brief 81")**: the meeting's decisions and actions found with no model; the model rewords the same list | 1 to 0 dead controls of 4; the sample's 3 of 3 decisions and 3 of 3 actions | 12, 4 |
| 3 | redesign | **Built 2026-10-10 (Brief 80; HISTORY "WORLD_CLASS 28.5, Brief 80")**: the Audio group: New meeting, Record, Voice note, Dictate, Recordings, Live captions (Brief 82); Translate waits for `/voice/status` `translate` (Brief 83) | 5/5 one press from the palette and one click as a tile, 1440 and 390 | 2, 6, 10 |
| 4 | fix | **Built 2026-10-10 (Brief 80; HISTORY "WORLD_CLASS 28.5, Brief 80")**: create, remind, save into, save as a meeting, save as a document on `pushUndo` | 1/6 to 6/6 | 1 |
| 5 | fix | **Built 2026-10-10 (Brief 80; HISTORY "WORLD_CLASS 28.5, Brief 80")**: a 10 s slice appended per chunk; `POST /recordings/recover` at start | tab killed at 2:00: "Recording recovered", 1:50 (110,306 ms) kept | 3 |
| 6 | expansion | **Built 2026-10-10 (Brief 80; HISTORY "WORLD_CLASS 28.5, Brief 80")**: Library, Recordings: play, 0.5 to 2x, the saved waveform (seek), markers (M and a button), trim to a new wav, delete to the bin | `audio80.js` ACT=library at 1440 and 390: each act passes, seek 2.25 of 2.25 s, overflow 0 | 6 |
| 7 | expansion | **Built 2026-10-10 (Brief 81; HISTORY "WORLD_CLASS 28.5, Brief 81")**: a timestamped transcript: a line seeks the audio, SRT and VTT out | every line within 0.27 s, 1440 and 390; SRT and VTT byte for byte | 6 |
| 8 | fix | Transcription is a job with progress and Stop (decision 70) | a 60-minute file lists, reports, stops | 5 |
| 9 | expansion | Live captions: built against a fake helper; open: the packaged helper download and a run on the reference laptop | Built by Brief 82; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (WORLD_CLASS 28.5 row 9, live captions, Brief 82)"); the open rows are in archive/agent-remaining/caption82-1010.md | |
| 10 | expansion | **Built 2026-10-10 (Brief 83; HISTORY "WORLD_CLASS 28.5, Brief 83")**: Translate this, offline (Bergamot, MPL-2.0, in a page Worker; English to Spanish as the package "Translate offline"); documents, notes, readings; a caption is a selection like any other; live captions translate under the dock's Translate button (libr-1011, fake translator in tests, needs device) | 94-word paragraph warm in Chromium: median 591 ms, 27 of 29 runs under 1 s (load 6 to 9 on 4 shared cores); 27.2 MB download, 41.8 MB on disk | 12 |
| 11 | expansion | **Built 2026-10-10 (Brief 81; HISTORY "WORLD_CLASS 28.5, Brief 81")**: speaker labels behind the model gate (ANALYSIS keeps it) | 2 speakers labelled on the sample (fake transport) | 12 |

Briefs: 73 (row 8), 80 (rows 1, 3 to 6), 81 (rows 2, 7, 11), 82 (row 9),
83 (row 10).

Decisions made (libr-1011, 2026-10-11): a recording is a search kind (`recording`, title plus transcript lines), and a note reaches it through `entry_id`, not an embed syntax; the meeting note keeps plain transcript text and the timed lines stay on the recording; a trim of a long take warns about memory and stays in the page until the app ships a container writer; a second translation pair brings its own picker, none before; RapidOCR stays an optional extra (it runs on this computer once installed).

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC8, the word list in search typo tolerance and the question-noise real-word check** (M, rank 8). `ai/question_noise.py` names `frontend/vendor/wordlist/en.txt` in a comment and never reads it; the search engine does not consult it either (the list is read by `documents.js` alone). A query word absent from the list and one edit from a word in the notebook is a typo. Measure: on the 30 misspelt queries of the existing noise table, recall at 10 before and after; no change on correctly spelt queries; the list loads once and costs under 50 ms at start.
### 28.6 T0 numbers, 2026-10-10

Brief 74 measured rules 1, 2 and 7 on 12 surfaces (`undo.js`, `reach.js`, `overlap.js`, `measure-writes.py` in `scratchpad/ui-sweeps/`): 124 controls pressed, 25 changed the notebook, 5 undone (statically 80 of 274 server-writing functions name an undo path); 55 destinations, 1 deeper than 3 clicks, 16 without a palette command; overflow/clipped 95/6, 14/5, 28/17, 30/19, 23/15 at 320 to 1440, docks 0 intersections. The table by surface and the findings by selector are in [`archive/agent-remaining/trust-1010.md`](archive/agent-remaining/trust-1010.md) (section "T0 numbers").

## Placed from INBOX, 2026-10-10 (filing suggestions)

- INBOX 781: built 2026-10-11, HISTORY.md, "Moved from the plans, 2026-10-11 (WORLD_CLASS 23, INBOX 781, filing suggestions)". Open: `docs/roadmap/archive/agent-remaining/filing-1010.md`.

## Placed from the settings agent, 2026-10-11 (a decision taken by standing order 3)

- 25f: the 14 appearance settings kept only in this browser do not follow the person to a second browser. Decision, taken: mirror them all to the notebook's preferences except `perf` (performance mode is a property of the machine). Owner: a Sonnet brief after the running ones.

## Decided by the rows agent, 2026-10-11 (standing order 3; house2 ledger rows)

- 1586, panel heads: `h3.panel-head` and the board's `h3.wb-sidebar-title` name a whole card or column, so they are titles (`--text-body`, 600, ink, the dialog title's voice); a label over one group inside a panel (`.doc-outline-title`) stays the eyebrow. Built, DESIGN.md's panel-head row.
- 1641, the Local chip: the receipt's verdict for this launch (`GET /privacy/verdict`, the same `egress.verdict` the receipt prints) sits in the header's first cluster as an icon and one word (Local, Local network, Online in `--warn`); one press opens Settings, Privacy. Below 1100 it is the icon alone; below 600 it leaves the bar for the phone's More menu (a live row carrying its word). Refreshed every five minutes, never a stream. DESIGN.md's Local chip row.
- 1643, type to filter: one recipe, `listFilter` (sheets-selects.js), shown past twelve rows, hiding misses with an empty-state row and Escape to clear; applied to the two longest lists that had none (the keyboard shortcuts, 31 rows; the space menu). The eight hand-built filters stay as they are, named in `HAND_BUILT_FILTERS` so a ninth must use the recipe.
- 1595, readable font: Font's fifth choice, Readable, is Atkinson Hyperlegible (SIL OFL 1.1, latin, 400 and 700 with italics, about 80 KB vendored under `frontend/vendor/atkinson/` with its licence), served from the app's own origin so it works offline and under `font-src 'self'`. It sets `--ui-font` only; documents keep their own face.
- 1588, dependency audit: `.github/workflows/dependency-audit.yml` runs `pip-audit` over `requirements.txt` on a weekly cron, on a change to the requirements and by hand; `continue-on-error` until a first clean run is seen, then it blocks. CI only: the app makes no request.
- 1661, memory growth: measured, no leak found, nothing changed. The server under a seeded session (`scratchpad/ui-sweeps/memserver.py`: three notes and every path the app's boot and tab switches ask for, per lap) went 446 to 600 MB resident over 10 minutes (78 notes, 1,300 requests) and was back at 509 MB idle; with no seeding, 6,150 requests over 10 minutes held 503 to 521 MB (509 to 507). The 8.5 GB of the first report did not recur. The browser half (`scratchpad/ui-sweeps/memgrowth.js`, heap after a forced GC and DOM nodes per lap) read 12.6 to 14.4 MB and 16,566 to 17,900 nodes over two laps before the sandbox's memory limit killed the renderer, three times; a 10-minute browser run on a machine with memory to spare is the open half.
