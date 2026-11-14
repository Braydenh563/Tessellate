# UI modernisation: the dev plan

> Companions: [ROADMAP.md](../ROADMAP.md) (live list: this plan is its top
> priority) · [HANDOVER.md](HANDOVER.md) (what the last session measured and
> left) · [../DESIGN.md](../DESIGN.md) (the rules this plan extends) ·
> [BACKLOG.md](BACKLOG.md) · [HISTORY.md](HISTORY.md) · the retired analysis doc

## The instruction, verbatim

> fix instances like this where there are hard rectangle box background
> colours behind rows. and there are still a lot of inconsistencies in ui
> style, sizing, alignment, positioning, spacing, gaps, margins, colour, style
> aesthetic etc. also sometimes when oeping dropdown menus or panels like for
> tooltips or in the formatting toolbars, the panels will flicker somewhere
> else on the screen then appear in the right place. now that you have done
> the structure fix. I need you to do a consistency fix, and also adjust the
> larger mass spacing and panels for the app. it needs to be professional and
> usable, not overly performative. the aesthetic needs to fit, not just be a
> crude imitation of modern aesthetics. I need you to modernise the ui.

And: "the ui needs to be modernised and proffesionalised for the whole
application ... the application still feels fake, vibe coded and not ready
for professional use. some things feel performative and not at professional
standards in the ui and ux."

## What "fake / vibe coded / performative" means here, concretely

Read against the measurements the last session took (HANDOVER.md, "This
session"), the feeling has five measurable causes. Every phase below attacks
one of them and is judged by a count, not by looking at a screenshot.

1. **Many recipes for one thing.** 17–21 button signatures on a tab; two
   eyebrow recipes; three seg recipes; row gaps of 4/6.4/8/9.6/16px; head
   rows 28/38/40px tall; two card radii. A professional UI has one of each,
   and the eye reads the difference as "assembled from parts".
2. **Decoration doing the work of structure.** Borders inside borders,
   sheen, blobs, shadows and glass everywhere, because tone and whitespace
   were never trusted to group things. Surface tiers started this; it is not
   finished (chips, fields, popovers, the whiteboard panels, the chat dock).
3. **Uneven mass.** 18px card padding on a 1100px card; 12/10/18px shell
   gaps (now one gutter); a hero that is 150px tall for a greeting; widgets
   with 47px of head for one line. Modern layouts are generous at the shell
   and dense inside the component, not the other way round.
4. **Things that move when they should not.** Menus that paint before they
   are placed (fixed for toolbar menus; audit the rest), rows that change
   shape on hover, transitions on layout properties.
5. **Copy and states that are not designed.** Empty states as one grey line,
   errors as toasts, loading as nothing, labels in three tones of voice.

## Rules for the whole plan

- **Measure, change, re-measure.** `scratchpad/ui-sweeps/` holds the sweep
  scripts from the last session (`buttons.js`, `borders.js`, `caps.js`,
  `segs.js`, `rows.js`, `space.js`, `heads.js`, `lib.js`). Each prints a
  signature table per tab. A phase is done when its count is what the phase
  says, in both themes, on the default palette. Run:
  `SCRATCH=<dir> BASE=http://127.0.0.1:<port> PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/<x>.js`
- **Tokens only.** No new px/rem values; `tests/test_style_scale.py` fails
  otherwise. If a phase needs a value the scale lacks, add the token with a
  comment saying which measurement asked for it.
- **Subtract before adding.** Every phase first removes a recipe, a border,
  a shadow, a size, and only then adjusts what is left.
- **One commit per phase, pushed, with the before/after counts in the
  message.** The user's usage is finite; a session that ends mid-phase must
  leave a green, pushed head.
- **Not performative:** no new gradients, glows, animations, badges or
  "AI sparkle" anywhere in this plan. The glass stays where it reads as
  material (the shell, a floating panel) and goes where it reads as effect.

## Decisions made

Standing order 3: a decision recorded here is not re-opened. A missing one
becomes an INBOX entry with a one-line recommendation, which is then taken.

- **A note's time ends its details line, and the line never wraps** (INBOX
  455 (1), 2026-10-03). Chosen over the head row beside the actions: Linear
  and Notion draw a row's date as its last property on the one line of
  facts, and Apple Notes puts it on the details line under the title; the
  head row's corner belongs to the card's actions, and a time that faded
  there on hover is exactly what INBOX 446 reported. What does not fit folds
  into "+N", then to icons, then ellipsis (DESIGN.md, the recipe index), so
  the time is at one x and one distance from the card's bottom on every card.

- **The default look is Quiet utilitarian; the old default is a palette**
  (the owner, 2026-09-23, asked against the unslop audit, which found the
  identity itself to be the tell: indigo accent, purple-blue emblem, lavender
  pastel page gradient and glass panels by default). Chosen: "go the quiet
  utilitarian, but also have the editorial paper, technical mono and the
  current look as ui appearance options". Quiet utilitarian: a neutral warm
  grey ground with no gradient or blobs, solid panels (glass off unless
  chosen), one ink-blue accent, tighter spacing; the content is the colour.
  Editorial paper: off-white paper, strong black type, a single red-orange
  accent for actions, hairline rules in place of card fills. Technical mono:
  a cool graphite ground, monospace for metadata and numbers, a green signal
  accent, square corners. Classic: today's look, kept exactly, as a palette
  anyone can choose. All four ship light and dark sets, like every palette.

- **A picker that adds to a list is an adder, not a `<select>`** (the owner,
  2026-09-12, on the capture form's "Add to document" box, INBOX 116). A
  `<select>` is the right control for choosing *a* value in a form: it shows
  what it holds. Where the answer is a set rather than a value, the picked
  items are chips and the control that adds one is a button that opens the
  app's own menu (`labelledMenu`, DESIGN.md's recipe index), so the control
  never has to lie about holding a value it cannot show. The failure this
  replaces is exactly that lie: the old handler wrote `value = ""` after
  every pick, so the box snapped back to "None" and read as broken.
  Applies wherever the same shape appears next, not only to this row.

- **Two writing columns are two of the same column** (Brief 22, the Write
  with AI panel, 2026-09-12). Where a panel puts two editors side by side,
  each column is a label, the box, one optional field and one line of
  actions, in that order, and the box is the only thing that stretches. What
  it replaces, measured at 1440x900: boxes of 189.2 and 330.3px from
  `rows="7"` and `rows="14"`, a left column ending 107px above the right one
  with nothing in the gap, an instruction input wedged between two buttons
  that do not read it, and an action row of four weights with a text field
  among the buttons. The two optional fields ride the `.ask-composer`
  recipe, which is also what makes the two rows the same height and so the
  two boxes equal: a row that is the same recipe in both columns is the same
  height in both.

**Paragraphs to '?' popovers: the decisions.** Copied whole from
`help-popovers.md` (git history) on 2026-09-14 (INBOX 220) so they
survive its archiving; the numbering is that file's.

1. **Section/group-level intros ("why does this area exist") convert.
   Field-level hints (attached to one specific control) and
   destructive/safety-critical warnings stay inline.** First stated in
   the Appearance/Custom CSS commit `6f31b6b`: hiding "what does turning
   this on do" behind a click, right where the control is, is worse than
   the extra line; hiding a section's own "why does this area exist" text
   is not, since nobody needs it to operate the section moment to moment.
   Governs every item below.

2. **The Tesseract OCR per-package caveat (Packages settings) stays
   inline, decided now.** It is a different shape from every other item
   on this list, and was kept back deliberately in an earlier pass rather
   than converted blind: the caveat text is built by `renderExtras()` in
   `frontend/js/app.js`, one row at a time from server data (`caveat=` on the
   extra's own definition), not static markup in `index.html`, so
   `count.py` structurally cannot see it either way. Decision: leave it
   inline. It reads as a field-level warning attached to one specific
   row's Install/Reinstall/Remove action ("what happens if I click this"),
   not a section-level "why does Packages exist" aside, so decision 1
   already covers it; the different shape (JS-generated per row) is a
   reason the fix would look different, not a reason to weigh the
   question differently. A per-row `data-help-for` pair generated
   dynamically is possible if a future session wants the audit script to
   see it too, but is not needed for the copy rule itself: the caveat is
   already one or two sentences, not a wall of prose.

3. **Account & security's "If you forget your password" pair (the two
   paragraphs around `python -m tessellate --reset-password`) stays
   inline, decided in commit `9f32b22`.** Same reasoning as decision 2,
   applied to a destructive command instead of a per-row caveat: the text
   describes irrecoverable private-note loss right next to the command
   that triggers it, so it is a safety-critical warning attached to one
   action, not a section intro.

4. **Five more items decided the same way, this pass, once
   `count.py`'s remaining list was checked against what actually renders
   around each:**
   - Command palette intro (`#command-palette-intro`, ~line 315): the
     comment directly above it in the markup argues for keeping it
     visible ("What it can do, said out loud... These are real examples...
     they are replaced by the conversation the moment there is one"). The
     paragraph's whole purpose is to be seen before anything else is
     typed; a popover would undo that.
   - Documents' "Where are my documents kept?" dialog (`#doc-storage-dialog`,
     ~line 425), Tensions' "Where you disagreed with yourself" dialog
     (`#tensions-dialog`, ~line 477), Ask's idle screen
     (`#ask-idle`, ~line 956), the document history dialog
     (`#doc-history-dialog`, ~line 3049), and Meeting notes'
     (`#meeting-overlay`, ~line 8223) own intro: all five are already
     inside a `<dialog>` opened from a link-styled button, or (Ask's case)
     a one-time idle screen replaced the moment it is used. Each is
     already the progressive-disclosure step decision 1 asks for; putting
     a `data-help-for` popover inside a dialog that is itself the
     click-to-reveal step would hide the content twice.
   - About's hero tagline ("A 100% offline, local-first notebook...",
     `.about-hero`, ~line 7706): this is the app's own one-line identity
     statement directly under its name and emblem, the shortest and most
     essential text on the page, not an explanatory aside about why the
     About section exists. Converting an app's own tagline on its own
     About page into something the reader has to click to see would be
     backwards.

5. **Field-level hints already decided inline in earlier passes, listed
   here so nobody re-checks them:** the settings-tools sub-group hints
   (`tool-focus-help`/`small-model-help`, already popovers via `e6e48a9`),
   `#progress-motion-row`'s inline hint, the model-latency `<small>`
   under Diagnostics ("How long each kind of job has been taking...",
   ~line 6059 in the old numbering), the thinking-dots motion hint
   (~6439), `#log-terminal-hint`, `#desktop-console-hint`, and
   `#desktop-tray-hint`. Each sits directly beside, or is toggled by, the
   one control it explains.

6. **The two JS strings (`countjs.py`) checked this pass, both decided
   inline, for the same reason as decision 2 (Tesseract):** the
   dashboard's Tensions widget explain line
   (`frontend/js/dashboard.js:3156`, "Similar-notes search finds what
   belongs together...") and the Library skills panel's Background
   workers hint (`frontend/js/library.js:1649`, "Lets the AI work through
   your notebook on its own..."). Both are one or two sentences built
   with `document.createElement`, the same JS-generated shape as the
   Tesseract caveat, and both are short enough that they are not the
   wall-of-prose problem this task targeted. Converting either properly
   needs the trigger and panel created and inserted into the live DOM
   before `initHelpToggles(root)` runs against that subtree (it is only
   ever called once, at load, against the whole document today; no
   dynamic render anywhere in the app calls it a second time yet), which
   is a real behaviour change worth its own render-path regression check
   rather than a same-session, same-commit add. The second pass is built:
   countjs 1+1 to 0 (HISTORY.md, briefs-1011, 2026-10-11).

## Phases 0 to 6: built

Moved whole to HISTORY.md ("Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: UI_MODERNISATION_PLAN)"): a plan holds open work only.

## Verification, every phase

- Sweep tables before/after in the commit message.
- Screenshots, light and dark, both widths, looked at *and* measured (pixel
  samples for any colour claim, `scrollHeight` for any clipping claim).
- `python -m pytest tests/` green; `ruff`; `node --check`.
- The four traps in CLAUDE.md still apply: stale server, stale `app.js`, a
  screenshot is not a measurement, "already exists" is where triage starts.

## Phase 7: the reports from the v0.2.2 round

Items 1 to 5 are built (below). Item 6, the agent activity panel, is owned by the retired agent-skills plan Phase C.

### Built: items 1, 3, 4 and 5

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", UI_MODERNISATION_PLAN.md) on 2026-09-09: a plan holds open work only.

### Decided, 2026-09-13: how the page reader is reached (do not remake)

From INBOX 125: "alsi I want an easier and more accessible way to access the
ocr workspace as a proper and more central feature." Triaged against the
running app first, because "already exists" is where triage starts, and four
doors were already there: the Files row's own filled "Read this" / "Open
reader" (the 2026-09-12 decision above), the image card's kebab, the
lightbox's "Read text with AI" and its kebab's "See text on the page", and the
toast that offers the way back while a read is still running.

What every one of them has in common is the answer: **each door starts from a
file you have already found.** There is no way in from "I want to read
something", and the reader is absent from both of the app's own "what can this
do" surfaces. That is the same gap, in the same words, as the meeting
recorder's ("I would also like the meeting notes popup to be expanded as a
proper feature ... which is also accessible throughout the app, not just from
the dashboard"), and it gets the same answer, because inventing a second
pattern for the same shape is what DESIGN.md's recipe index exists to stop.

- **The command palette and Tools & features, and nothing new.** Ctrl/Cmd-K
  reaches "Read a document or image with AI" from any tab, and the features
  browser lists it beside Attachments, which is the entry a person who does
  not know the reader exists will actually meet. Those two are the app's
  answer to "make X reachable from anywhere"; a fifth per-file door, a nav
  item or a dock button would each be a new pattern for a feature that already
  has four.
- **It opens on a file rather than on a picker**, in this order: the file you
  last had open in it, else the most recently added readable file, else the
  Files sub-tab with a line saying there is nothing to read yet. The reader's
  own rail already lists every image and file in the notebook (it learned to
  load them itself when "if I open it from the lightbox when viewing an image,
  no other files or images show" was reported), so a picker in front of it
  would be a second list of the list it already has.
- **No new markup.** Both entries are rows in existing catalogues, so there is
  no new id, no new surface and nothing for the recipe index to cover.

### Decided, 2026-09-12: what a Files row is for (do not remake)

From INBOX 115, "the files rows in files still needs some ui improvement and
redesign, and better function". The row had grown by accretion: five
full-width blocks in a 1218px column, each carrying one short string, 257px
tall at 1440. The question "what should a file row let you do without opening
anything" is settled here so the next pass adds to a shape rather than
restacking it.

- **Two ranks, not five.** The name is the row. Under it, one wrapping line of
  facts at one rank: what the file is (kind, size, pages, added), whether it
  has been read and how much came out, and where it is used. Under that, the
  description, which is the only prose and the only thing that may take two
  lines. Anything new joins one of those three or it does not go on the row.
- **Four verbs, without opening anything**: open it in the reader (the row's
  one filled control), save a copy of the original, rename, delete. The last
  three live in the kebab, which is where every other list in this app puts
  them. "Save a copy" is the one a file list must have and this one did not:
  nothing in the Library could get a file back out of the notebook.
- **A fact is not a control and a control is not a chip.** The reading badge
  states; the "Used in" chips open the note they name; the kebab acts. A row
  that draws all three the same way is the report this decision answers.

### Decided, 2026-09-12: what the bottom of a picture card is (do not remake)

From INBOX 115 ("the bottom of the image cards in the library images
subsaection needs a desperate redesign and funection") and INBOX 118 after the
first pass ("still poorly designed and look unprofessional"). The Files row
decision above settles a row; this settles the card, which is a different
shape and was being restacked every pass.

- **The card is a picture and one paragraph about it.** Its name is on the
  photograph, its description under it, clamped to two lines, and nothing else
  is a permanent row. A card with nothing in it is short.
- **A fact is a line of text, a disclosure is a control, and neither is the
  other.** Where the picture is used is a count you read (`Used in 2 places`,
  the smallest type on the card, no ground, nothing to press). Whether text
  was found in it is a fold, present only when something is folded. One
  control holding both is what INBOX 118 called unprofessional.
- **Everything you can do to a picture is a row of the card's kebab**, not a
  control on it: open full size, copy the markdown reference, write a
  description, type the text in it, rename, save a copy, the two AI readers,
  and one row per place it is used. Two to three controls on a card at rest,
  against nine to ten before this work.
- **The grid wants equal heights, and the photograph pays for them.** The tile
  is a column, the frame is the one child that grows, with a 9rem floor and a
  16rem ceiling. Measured on six seeded cards at 1440: 261.5px each, bottoms
  within 0.1px, pictures 144 to 249.9px, and 1.0px of slack under the
  emptiest card against 54.5px before. The cost, and it is the accepted one:
  the six descriptions start at six different heights, because the only other
  places to put the difference are a hole under the short cards (what the
  owner reported) or reserved empty rows (what the owner reported first).
- **Provenance is inside the fold**, with the reading it describes. "Described
  by X, read by Y" has been called noise twice (INBOX 56 and the second design
  batch) and is not coming back to the outside of the card.

Built in `75a1d62`, `65cf876` and `4dd3f57`; probed by `scratchpad/ui-sweeps/imagecardfoot.js`
(shape and, with `pixelcontrast.py`, contrast from the rendered pixels) and
`imagecardmenu.js` (the menu rows, run rather than assumed).

**Reported a third time, 2026-09-13, and the decision above is not what was
wrong.** "redesign the bottom text area of the image cards in the library
images subtab again ... the block reads as four unrelated rows of different
weights, and the cards are uneven in height because some have the disclosure
and some do not." Measured before touching anything: the cards were already
equal (261.5px, bottoms within 0.1px), so what reads as uneven is what is
*inside* them, and it was three rows under the picture at three adjacent type
sizes (13.6 / 12 / 11.2px) with a foot running 9.6px to 115.5px across one row.
Three amendments, none of which reopens a bullet above:

- **The count and the fold share one line of facts**, which is the Files rows'
  own `.library-file-meta` shape rather than a new one. They are still two
  objects, one you read and one you press, which is what "a fact is a line of
  text, a disclosure is a control" asks for; they simply no longer take a row
  each. The fold's label on a card is "Text" (the full phrase is its tooltip
  and the heading inside it) because "Used in 2 places" plus a 128.8px chip
  does not fit the 161px a tile has, and a wrapped facts line puts the
  unevenness straight back.
- **The description holds its second line open** (`min-height: 2lh` while
  clamped, picture cards only). A one-line caption left the card 21.8px
  shorter inside than its neighbour, and the grid pays that out as a taller
  photograph, which is the unevenness the report names.
- **A two-row subgrid was built, measured, and taken out**, and this is the
  bullet above being confirmed rather than remade: it does equalise every
  picture (144px) and every foot (118.5px), and it puts the difference back
  as a hole, 75px under the shortest card. The three places to put that
  difference are still a bigger picture, a hole, or unequal cards, and the
  first is still the least bad.

Measured after, at 1440 on the same six seeded cards, in both themes: every
card with a caption and a fact is 240.7px with a 144px picture and a 95.7px
foot, the facts line is 32px whether it carries a chip or a word, the tail
under the last line is 0px, an opened fold takes the card's full width (159px
of 180px, no overflow) and the row grows with it, and contrast is 7.48 / 7.53 /
6.56 in light and 6.47 / 6.44 / 5.06 in dark.

## Phase 8: control docks: one grammar for every tab's head (2 sessions)

**The instruction, verbatim** (after Phases 0–7 were built):

> I would like you to go through the tabs and subtabs and features and
> redesign the controls and elements often in the top docks or bottom docks
> professionally. A lot of them just feel like buttons and elements chucked
> at the top of the main panels. […] So many of the main control elements at
> the top of each tab or subtab feel soo fake and rudimentary, not
> professional, they aren't aligned, they just feel like features there and
> note intentionally designed. Use all your ui and ux skills, features need
> to be properly grouped, use drop downs if you see fit but don't over use
> them, think spacing, alignment, hierarchy, learnability (A MUST! ALL
> ELEMENTS AND CONTTOLS OF THE SAME TYPE AND FUNCTION NEED TO BE, ACT, AND
> PLACED THE SAME APP-WIDE), accessibility.

**Measured at 1440 before this phase** (`scratchpad/…/docks.js`, one row
per dock: controls, distinct control heights, kinds):

| Dock | Controls | Heights | What the eye reads |
| --- | --- | --- | --- |
| Graph toolbar | 28 | 1 / 24 / 25 / 32 | two segments, a select, five buttons, a filled "New note" *and* "Concept maps" in the head row, a count and a legend below, every feature the tab has, in a row |
| Library head + toolbar | 2 + 16 | 18 / 30 / 36 | two switches, a segmented sort **and** a sort select saying the same thing, a view segment, a filter select, then eleven chips |
| Notes toolbar | 14 | 32 / 36 | title, refresh, Select, view segment, search, Semantic, help, sort, page size |
| Whiteboard top bar | 17 | 32 / 36 | back, board select, rename, add, layout select, then search, minimap, five menus, Library, fullscreen |
| Documents header + strip | 9 + 26 | 28 / 32 / 36 | see DOCUMENTS_PLAN.md §3.2 |
| Timeline toolbar | 9 | 24 / 32 | View, a select, Today, Options, Highlight, a filter, a count, help |
| Reminders | 1 + 8 + 4 | 28 / 44 | a magic row, eight presets, four due buttons, three rows of ghost buttons |
| Chat | 1 + 6 | 28 / 36 | a filled New, then a toolbar of six at a different height |

Seven docks, seven layouts. Phases 1–5 fixed the *recipes* (heights,
radii, gaps); what they did not fix is the **grammar**, what goes where,
in what order, in what kind of control, and that is what "chucked at the
top" means.

### The dock grammar (the rule the whole phase enforces)

One dock, three zones, read left to right, the same on every tab and every
sub-tab:

```
[ Title · context ]  [ Search ]  [ Filter ▾ ] [ Sort ▾ ] [ View ⋮⋮ ]   ·   [ Primary ] [ ⋯ ]
   identity            find        narrow       order      how          ·     act      more
```

1. **Identity first**: the title (or breadcrumb) and, when the surface has
   one, its context chip (the board's name, the space, a count). Never a
   control.
2. **Find, narrow, order, view, in that order, always.** Search is the
   first control after the title on every list surface. Filters are one
   `Filter ▾` popover (the Notes sheet from Phase 5 is the model) or a chip
   row *below* the dock, never both. Sort is one select, never a segment
   and a select. View is one segmented control with icons (rows / cards /
   grid), never text.
3. **One primary action, at the right, filled.** `New note`, `New
   document`, `New board`, `Send`. A second filled button in a dock is a
   defect. Everything else is ghost or icon-only.
4. **Utilities at the far right, in a fixed order**: refresh, help, ⋯.
   Refresh is always the same icon in the same place; help is always last.
5. **Seven visible controls per row, then overflow.** An eighth goes into
   `⋯` or a named popover (`Options ▾`, `Insert ▾`). Menus are for verbs
   that are used sometimes; a verb used every minute stays in the row.
6. **One height, one baseline, two gaps.** `--control-h-lg` for every
   control in a dock, `--space-3` inside a group, `--space-4` between
   groups (Phase 2's numbers), the group boundary drawn by gap alone,
   never by a rule or a border.
7. **The same control does the same thing everywhere.** A segmented
   control changes *view*; a select changes *sort or filter*; a switch is a
   *setting* and lives in a popover or in Settings, not in a dock; a chip
   is a *filter you can see*. A control that breaks this on one tab is
   moved, not styled.
8. **Accessible by construction**: every dock is `role="toolbar"` with
   roving tabindex (arrow keys move between controls), every icon-only
   control has `aria-label` and a tooltip, every popover is
   `aria-expanded`/`aria-controls`, focus returns to the opener on close,
   contrast ≥ 4.5:1 measured with `pngpixel.py`.

Phase 8's surface-by-surface work list and its acceptance are built (`tests/test_dock_grammar.py`, `docks.js`); moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: UI_MODERNISATION_PLAN)".

### The two bars that are not docks (added by direct instruction)

- **The top bar** (`#top-bar`: logo, space switcher, notifications, theme,
  settings, lock, quit) and **the tab bar**: one height, one gap, utilities
  in the same order as every dock's, the space switcher as a select-shaped
  control rather than a button that looks like a tab. Phone: the tab bar
  moves to the bottom (Phase 9).
- **The whiteboard top bar** (`#wb-topbar`): a menu bar is its own valid
  pattern (Insert · Edit · Arrange · View · Board) but it follows the
  dock's zones: identity (Boards ‹, board select, rename, new; the Map
  chip, layout, Tidy), find (search, navigator), the menus, actions
  (Library, fullscreen): one height, and its menus on the `.dock-menu`
  recipe so they close on pick, outside click and Escape like every other
  menu. The floating tool palette and the properties panel take the
  popover shell. Nothing on the board may feel like a different app.
### Built, second sitting

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", UI_MODERNISATION_PLAN.md) on 2026-09-09: a plan holds open work only.

## Phase 9: responsive by device, on purpose (1 session)

**The instruction, verbatim:** "Also intentional and adjusted design that
alters specifically for smaller resolutions like for iPad, tablet, iPhone
etc."

Phase 5's phone work was reactive, each 390px finding fixed where it was
found. This phase makes the breakpoints a design, stated once:

(Corrected 2026-10-05, audit FE-11: built as a design but not held. The
audit counted 58 distinct width queries, with `max-width: 600px` and
`min-width: 600px` both matching a 600px window, and 720 the same.
`tests/test_breakpoints.py` now fails on a width on both sides and on any
new width outside the set below; the double matches are gone and the count
is 48. The 720, 640 and 900 groups were moved onto the bands on 2026-10-05:
HISTORY.md, "Moved from the plans, 2026-10-05 (UI_MODERNISATION_PLAN Phase 9,
the off-band widths)"; the whiteboard file's last ten followed (HISTORY.md,
"Moved from the plans, 2026-10-05 (the whiteboard file's off-band widths,
op5)"), and the three groups are empty.)

| Width | Device | What changes, app-wide |
| --- | --- | --- |
| ≥ 1100 | desktop, iPad landscape with a sidebar | the layout above; sidebars open |
| 820–1100 | iPad landscape, small laptop | sidebars collapse to icons; docks keep seven controls; whiteboard properties panel becomes a sheet |
| 600–820 | iPad portrait | one column; sidebars are sheets from the left; docks keep identity + search + `Filter ▾` + primary, the rest in `⋯`; two-up card grids |
| < 600 | iPhone | the phone rules from Phase 5, applied to every tab: strips scroll, one control row, the primary action pinned bottom-right as a floating button, bottom docks (chat composer, the documents formatting bar) above the on-screen keyboard |

Rules: touch targets 44 × 44 CSS px at < 820 (`--target-min` steps up in
the 820 media block, not per component); `env(safe-area-inset-*)` on the
top bar, the status bar and every bottom dock; `hover:` styles gated behind
`@media (hover: hover)`; the tab bar becomes a bottom tab bar at < 600
(thumb reach), with the top bar keeping identity and utilities only;
`prefers-reduced-motion` honoured in the same block.

Acceptance: `errors.js` at **390, 820, 1024 and 1440**, 0 findings on
every tab and sub-tab; `all.sh` gains `WIDTH=820`; a `touch.js` sweep
(Playwright `hasTouch`, `isMobile`) taps every dock control on Notes,
Library and Chat at 390 and asserts each hit target ≥ 44px and that no tap
lands on two controls; screenshots at all four widths in the shots set.

## Built: Phase 9

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", UI_MODERNISATION_PLAN.md) on 2026-09-09: a plan holds open work only.

## Not in this plan

New features. The plan is subtraction and alignment; the feature backlog
(BACKLOG.md) waits until the shell is quiet.

## Phase 10: the Liquid Glass adoptions (½ session)

DESIGN.md's "Taken from Liquid Glass and the HIG" rules 2, 3, 4, 8, 10 and
12, as the placed items below (INBOX 100 to 104). Rules 2, 3 and 12 are
built (100, 101, 103; moved to HISTORY.md, "Moved from the plans,
2026-09-09"). Rule 4's clear variant (102) is built too, as the `--glass-filter-clear`
token and a ratchet (HISTORY.md, "Moved from the plans, 2026-10-04 (the
top bar mode and the glass recipe)"). Rule 10's receding tab bar (104)
is phone work and moves to Phase 11 with the rest of it. Deliberately not taken: refraction and lensing (measured too costly),
title-case headers.

## Phase 11: the phone, done properly

The owner, 2026-09-09: "the mobile view still needs quite a lot of work but
that isn't for this PR, scope and plan it for later sessions." Phase 9's
under-600 rules are moved here whole; this PR ships desktop and tablet.

**Decisions (made here).** The phone is a design of its own, not the
desktop squeezed: one column, one thing at a time, the primary action
within thumb reach, every panel a sheet, every list a full-width row.
Standalone (installed) mode and the browser tab get the same layout;
`env(safe-area-inset-*)` on every fixed edge. Nothing is hidden that the
desktop has; it is reached through a sheet or a ⋯ menu instead.

1. **Navigation.** The five-item bar and its More sheet are built (2026-09-13;
   the block, with its numbers, is in HISTORY.md, "Moved from the plans,
   2026-09-13"). What is left of item 1, in order:

   - The recede (INBOX 104) and the top bar's own reduction are built;
     both blocks are in HISTORY.md ("Moved from the plans, 2026-10-19
     (mobile1314)"). The bar's rework for INBOX 1314 is under "Placed from
     INBOX, 2026-10-19" at the end of this plan.

2. **Notes.** Capture as a full-height sheet from the floating + button;
   the list as full-width rows with swipe actions (pin, bin) matched to
   the row's menu (the HIG rule); filters in a sheet; the note view as a
   page with a back button, its actions in a bottom bar.
Phase 11 item 2 (Notes on a phone) is built, 2026-09-20: the rail gone below 600, filters as the fold, the floating +, swipe actions, the note page. Decision kept: the Capture sub-tab is the sheet (a sheet over it would be a second capture surface). Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: UI_MODERNISATION_PLAN)".
3. **Chat: built** (2026-09-20). Moved to HISTORY.md ("Moved from the plans, 2026-10-10 (Brief 72b)").
4. **Graph: built** (2026-09-20). Moved to HISTORY.md, the same section.
Phase 11 item 5 (Library and Files on a phone) is built, 2026-09-20: the share sheet and the reader full screen with a bottom bar. Decision kept: two-up cards were decided the other way, one full-width column at 600 stands. Sharing a file (an image from the camera roll) is built 2026-11-12 (L-ui-modernisation-7, HISTORY). Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: UI_MODERNISATION_PLAN)".
Phase 11 item 6 (Documents on a phone) is built, 2026-09-20. Decision kept: Edit is the page, not a sheet over it. Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: UI_MODERNISATION_PLAN)".
Phase 11 item 7 (Whiteboard and maps on a phone) is built, 2026-09-20. Decision kept: the board's top bar is not reduced to a kebab (a menu bar is the dock grammar's exception; a phone-shaped board bar is WHITEBOARD_PLAN's). Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: UI_MODERNISATION_PLAN)".
Phase 11 item 8 (Settings, dashboard, timeline, reminders) is built or decided, 2026-09-20: Settings keeps its phone shape. Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: UI_MODERNISATION_PLAN)".
Phase 11 item 9 (Touch: the 44px floor and no hover-only affordance) is built, 2026-09-20. Moved to HISTORY.md, "Moved from the plans, 2026-11-09 (book5-1109: UI_MODERNISATION_PLAN)".
10. **The status bar at 320: taken, the first way.** Measured 2026-09-12,
    after the header was made to fit: at 320 x 844 the page still scrolled
    sideways, 355 in 320, and the bar was the cause (its six surviving items
    need 355px: the AI dot 28, reminders 18, the nav group 147, undo 44, redo
    44, the agent dot 18, plus gaps). The bar is deliberately `nowrap`, since
    a wrapped status bar changes the height of the window's furniture as its
    own text changes, so of the two options here it took the scroller: below
    400 the bar scrolls with the `edge-fade` recipe every other overflowing
    strip uses, and nothing is hidden. Measured after: the page is 320 in 320
    and 360 in 360, and every width from 320 to 1024 is clean. The second
    option, one action and a sheet, is still the right end state and is this
    phase's own item 1.

**What is actually open here, measured (2026-09-13, at 360, 390 and 820).**
Before building any of the ten items above, the running app was measured, because
two of them turned out to be mostly done and one of them turned out to be a
different problem than the list says.

- **The bottom tab bar exists and is five columns** (`#phone-tab-dock`,
  10-responsive.css; `dockTabBar`, app.js). Measured at 390, 360 and 320: five
  columns, every caption whole, one row, flush to the bottom edge, no sideways
  scroll. The block is in HISTORY.md.
- **Touch is clean across the band.** `touch.js` with `hasTouch` and
  `isMobile`: 17 surfaces, 0 findings at 390, 360 and 320. The last of them was
  the settings sheet's head being squashed to 36px around a 44px control row
  (fixed 2026-09-13, 10-responsive.css); the same squash is there at every
  width and is invisible above 360 because the head does not wrap, so the
  general fix is open work for whoever owns that surface.
- **The sheets: one recipe, two in place, and the boundary between them is now
  written down** (2026-09-13). `openSheet` builds a *modal bottom* sheet out of
  nothing; the two that predate it are *in-place* sheets, elements already on
  the page that become one inside a band. They are not being moved onto
  `openSheet`, and that is a decision rather than a postponement: each would
  lose the thing it was built for (the sidebar keeps a rail on screen carrying
  its own opener, which is the way back; the graph's is deliberately not modal,
  so the map it came from stays visible as the sheet's origin), and it would
  mean moving a live subtree in and out of a dialog on every open. What they do
  share, from this session, is the dismissal: `wireInPlaceSheetDismissal` in
  app.js gives both a captured Escape, a press outside and focus back on the
  opener. DESIGN.md's "A sheet" row carries the boundary;
  `tests/test_ui_recipes.py` holds the ratchet at two and the shared dismissal.
  Measured with `scratchpad/ui-sweeps/sheetdismiss.js` at 390: the sidebar
  sheet opens from its rail, a captured Escape closes it past a handler on
  `document.body` that stops Escape (the bubbling one it had never saw that
  event at all), a press outside closes it, and focus lands back on the toggle
  with `aria-expanded="false"`; the More sheet the same.
- **A finding at 820, which is not a phone at all: fixed** (2026-09-13). The
  header was 112px there, two rows, on a band whose own rule says "the tabs are
  icons, and the header is one row", and the buttons were 36px tall. The block,
  with its arithmetic, is in HISTORY.md ("Moved from the plans, 2026-09-13").

11. **Gates.** `scratchpad/ui-sweeps/phone.js` exists (2026-09-13) and holds
    four of them per tab at 390x844 and 430x932: no horizontal scroll (page and
    inside every surface), no control under 44px, one column, and the primary
    action's y reported. Two of the list are not in it, for reasons worth
    keeping: **the primary action's position is reported and not failed**,
    because four of the seven tabs have no filled action at all (the graph's is
    a menu row) and inventing one is a design decision a sweep does not get to
    make; and **the composer above a simulated keyboard cannot be measured
    here**, because the sandbox has no soft keyboard and Playwright does not
    fake one, so `visualViewport` never shrinks. Two taps to anything is in
    `phonetabs.js` and `phonemore.js` already.

    **errors.js and contrast.js at 390: done** (2026-09-20). errors.js already
    took a width and is clean at 1024, 820 and 390 (0 errors, 0 layout
    findings each). contrast.js took **no viewport at all** and had therefore
    only ever run at `boot`'s default 1440x900, which is the whole reason this
    line was open. It takes WIDTH/HEIGHT now, a touch context below 600, and
    two things it had to learn to reach a phone: Settings opens through
    `openSettingsModal` rather than `#settings-btn` (hidden below 600, where
    Settings is a row in the header's `...` menu) and its sections are reached
    the same way (the section strip is hidden below 600), so every one of the
    twelve had been "ok" at phone width by never being looked at. It also
    reports **how many text elements it measured**, because "ok" and "nothing
    rendered" printed the same line before, and that count caught one on its
    first run: `whiteboard` was in its tab list with no `#tab-whiteboard` to
    open, so `revealTab` hid every page and the sweep measured an empty window
    at every width it has ever run at. A board is opened from Boards & maps now
    and measures 88 text elements at 390. Result: 33 surfaces per run, 0
    low-contrast, at 390, 820 and 1440 in light and dark.

    The owner screenshot set was dropped (owner 2026-11-12, LEDGER L762):
    anything needing the owner's eye is asked as its own question with numbers.

12. **Content gets the screen: built** (2026-09-23, INBOX 392: "the mobile
    view is still very broken, takes up a lot of the screen"). Gate:
    `scratchpad/ui-sweeps/phonechrome.js` (chrome at most 25% of the height,
    content in the top 40%, no sideways scroll, no cut picker, 44px targets,
    no row drawing over its own text, nothing fixed on the tab bar), PASS at
    390x844, 768x1024 and 1024x768 in the new default look. Before and after
    at 390: chat chrome 266 to 170px, notes 206 to 164, the reminders list
    from y=836 to 188, the library's first card from 407 to 304. The block
    with its numbers is in HISTORY.md ("Moved from the plans, 2026-09-23").

    **What each surface is for on a phone** (the owner, 2026-09-23: "actually
    intentionally designing for those resolutions, and not just adapting to
    them"), which decides what is first on its screen:
    - Dashboard: see what is due and start something; the greeting, search
      and the two launch rows, then the widgets.
    - Notes: find a note and read it; the row is the note (swipe to star or
      bin, tap to open, ⋯ for the rest), capture is the floating +.
    - Chat: ask and read the answer; one head row, the transcript, and a
      composer whose second row is mode, attach and the gear; the model and
      tools live in the gear's sheet.
    - Library: find a thing and open it; one head row, the kind chips in
      one sideways row, cards of three lines.
    - Timeline: scan what happened when; the table, the floating Today.
    - Reminders: see what is due and tick it off; the list is the page,
      adding is the floating + and a sheet.
    - A board: look and move around; the canvas under one bar, two fingers
      for the camera, the tool sheet at the foot.

    **Decisions (made here).** Below 600 the status bar is not a bar: Back,
    Undo and the AI dot move into the header and every other control is a row
    of the header menu, returning as a bar only for a running job, offline or
    power saver (this moves the AI dot out of the status bar item 1 left it
    in, because the bar itself left the screen). A coarse pointer gets the
    44px floor at every width, not only below 820 (supersedes band 2's
    tab-strip-only floor; an iPad in landscape is 1024). A form that fills a
    narrow first screen is a sheet from the list's own filled action (below
    1100, Reminders). Below 600 a ⋯ menu is an action sheet
    (`openKebabSheet`); a menu at the pointer stays at the pointer.

    Open: the selection ticks on Library cards and reminder
    rows draw a 44px box at rest, where a smaller drawn box in a 44px target
    would read lighter; Settings scrolls sideways in two sections at 768.
    The list, with ids, is `phone.md` (git history).

## Phase 12: density, refinement and WCAG 2.2 (the owner, 2026-10-10; Brief 41)

The owner's words, verbatim: "the ui still needs a more modern and professional
polish. I think an issue might be that some of the ui elements, controls and
dropdowns are too large and bulky and have too large spacing and margins around
them and gaps around panels?? like the vs code ui is a lot more cleaner and
refined and the sidebar is still floating but its more subtle, the controls are
smaller and intentional, not wierdly bunched. I think a lot of surfaces need this
modern redesign. also on microsoft teams I noticed on the sub menu bars, there
are grey underlined hover states, and when I hover over icons, no semi
highlighted border box appears behind them, I just hover over or click on them
and the icons themselves change to the highlighted colour." "also I think the
topbar is a little large but idk maybe not. maybe research design principles or
standards?? ensure wcag 2.2 accessibility is followed and complied with." "all
the controls and docks on each page and dropdown menus and popup menus and
stuff just need a major polish and refinement and they all need to be
consistent across the app. think maximum learnability, minimalist and
instinctive to use." "the reminder dropdowns for setting datetimes and stuff,
they need a custom style. I also think there needs to be a better and more
primary calendar feature paired with the reminders." "on vs code selected lines
have their line number bolded, the line subtly bordered and there are also
indentation lines." "Note metadata and chat bubble metadata still feels
incredibly messy, not modern, and unrefined." "Some tooltip buttons are circles
and some are rounded squares."

### Decisions, 2026-10-10 (do not re-decide)
1. **A density scale in tokens.** Control heights 28px (dense: docks, toolbars,
   sub-menu bars), 32px (default: forms, menus), 40px (touch, phone); icon
   buttons square at the row's height; gaps on a 4px grid (4, 8, 12, 16); panel
   padding 12px; the sidebar gutter 8px; the topbar 44px measured (today's
   number recorded first). One token set in `00-tokens-shell.css`; no literal
   heights in the other files (`test_style_scale.py` extends to heights).
2. **The hover grammar.** An icon button changes its icon colour on hover and
   focus (no box behind it); a sub-menu bar item takes a 2px underline (Teams);
   a text button keeps its box; a row takes a tint. Active states keep a box
   with the accent at low alpha. Recorded in DESIGN.md with a lint in
   `test_ui_recipes.py` (no `.ghost:hover { background` on icon-only buttons).
   **Amended 2026-10-10 (INBOX 784/788, the owner: "not all buttons have the
   same hover states"):** an icon button takes the same quiet box as a text
   button, glyph to full ink, never an accent tint; DESIGN.md rule 4 and the
   "One hover for every button" recipe hold it.
3. **One radius per class** from tokens: pill for segments and chips, the
   button radius for buttons (circles only for the companion and avatars),
   the panel radius for panels and menus. Tooltips and help triggers are the
   same shape everywhere (the owner's "circles and rounded squares").
4. **WCAG 2.2 AA as a sweep** (`scratchpad/ui-sweeps/axe.js`, tag wcag22aa):
   target size at least 24 by 24 CSS px (2.5.8); focus visible with a 2px ring
   at 3:1 against its background (2.4.11, 2.4.13); text contrast 4.5:1 and UI
   contrast 3:1; every drag action has a non-drag alternative (2.5.7: boards
   and maps move by arrow keys and menus; reorders have Move up and down);
   help in a consistent place (3.2.6: the ? popover at the section head);
   redundant entry avoided (3.3.7); the lock screen allows paste and a password
   manager (3.3.8). The sweep runs per surface and its counts go in this phase.
5. **Custom pickers.** Date and time (reminders, the timeline, documents'
   properties) on the sheets-selects recipe: a month grid with keyboard
   navigation, a time list in the person's clock format, typed entry accepted
   (`when.py` parses it), today and clear actions, measured at 1440 and 390.
6. **A calendar view** of reminders and dated notes: TIMELINE_PLAN's Calendar
   mode (month and week), not a new tab; reminders draggable between days with
   a keyboard alternative; the day strip (INBOX 561) becomes its week row.
7. **Metadata rows**: one muted line per card or bubble, chips only for state
   (pinned, due, unsaved), the kind icon first, the time last and pinned to the
   card's corner (INBOX 745 (a)); the same rule on note cards, chat bubbles,
   library cards and timeline rows; a census before and after
   (`perf2-1005-census.js` counts and heights).
8. **The code editor's active line** (DOCUMENTS 21): bold line number, a subtle
   full-width border, indent guides; the writing checks everywhere rule is
   DOCUMENTS 21's.
9. **Research is recorded, then applied.** The agent reads the ui-ux-pro-max
   skill's UX guidelines and styles, the Apple HIG and Fluent 2 density and
   hover sections, VS Code's workbench metrics and WCAG 2.2's new criteria, and
   records the ten rules it takes (with the number each sets) in DESIGN.md
   before changing CSS. "Reasoned UI is not observed UI": every change is
   measured in Chromium at 1440, 1024 and 390, light and dark, and the sweeps
   (errors, docks, contrast, touch, axe) pass on the head.

### Steps
1. The census: today's control heights, gaps, radii, hover boxes, topbar height,
   per surface (the numbers in this phase).
2. Tokens and the scale (1), topbar and docks first.
3. The hover grammar and radius classes (2, 3) with their lints.
4. The WCAG 2.2 sweep (4) and its fixes, surface by surface.
5. Pickers (5), then the calendar mode (6).
6. Metadata rows (7); the editor's active line (8).
7. DESIGN.md, help, CHANGELOG; the Built block to HISTORY.

Steps 1 to 4 and 6, and step 5's pickers, built 2026-10-10 (Brief 41): moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION Phase 12)"). Open:
- 7 on chat bubbles and library cards; 1's panel padding 12 and sidebar gutter 8, not yet measured.

## Settings information architecture (INBOX 444)

The owner, 2026-10-03: "a major expansion, improvement and modern/professional
ui/ux redesign of the models settings page suggested downloads section ... the
settings needs better designing, rearrangement, better internal navigation and
cleaning up." Measured first with `scratchpad/ui-sweeps/settingsia.js`
(1440x900 and 390x844, a fake Ollama so Models is whole: `scratchpad/
fake_ollama_server.py`).

**Before:** 20 sections; 30,557px of settings at desktop width and 51,331px at
390; 65 groups, 1,097 controls (253 of them Logs rows), 44 help popovers; 47
one-line descriptions that wrap at 1440, 170 at 390. Models 4,737px at 1440
and 10,275px at 390, with the search engine, the search index and (two
sections away, in General) the search relevance floor that tunes them. Nine
concerns set from two or three sections (a background job's model: Models and
Tasks; web search: Tools and Web search; search relevance and the index:
Models and General; clearing old data: General and Import & export; how Atlas
answers: Models, Tools and General). Suggested downloads: 31 rows, 29
identical filled Download buttons, a 2,237px box (6,313px at 390), no
mention of memory or of whether a model fits this computer. The nav had four
groups, a search that only hid nav buttons, arrow-key walking, and no index
inside a 4,000px section.

### Decisions made

1. **Six nav groups, by what the person is doing:** AI (Models, Search and
   index, Personas, Skills, Tools it can use, What it remembers, What it
   learned, Web search); Notebook (Profile, General, Templates, Import &
   export); Look and feel (Appearance, Keyboard shortcuts); Privacy and
   security (Account & security, Privacy); System (Packages, Background
   tasks, Logs); Help and About. Profile sits with the notebook, not the AI:
   it is the person's own record. `tests/test_settings_ia.py` pins the order.
2. **One new section, `searchindex` ("Search and index"):** the search
   engine, the search index and the search relevance floor, which were in
   Models (two) and General (one). Measured reason: Models was the second
   longest pane and the three are one concern.
3. **Answer style moves from General to Personas:** it is Atlas's voice, and
   the Personas pane already says so. General is left with the recycle bin,
   chat history, notifications and writing.
4. **Settings that guard something stay beside it.** "Keep Atlas on this
   machine" stays with the backend address it guards; the Privacy pane
   reports, it does not duplicate.
5. **Every existing id and `data-section` is kept.** A deep link that names a
   control is resolved to the section that holds the control now
   (`openSettingsModal` reads `closest(".settings-section")`), so a later move
   cannot strand a link; callers were also updated, and a lint
   (`test_a_link_names_the_section_that_holds_its_target`) keeps them honest.
6. **No section is merged away this round.** Templates, Skills and Personas
   list rows and the sampling sliders were fixed and are guarded by
   `tests/test_badge_recipe.py`; they are not touched.
7. **Internal navigation is one lazy file, `settings-find.js`** (loaded with
   the first open of Settings, so outside the boot gzip budget, which sits
   842 bytes under its cap). The nav search existed (it hid the sections whose
   text lacked the word); it now also lists the matching settings (a group
   head or a control's label, with the section and group), capped at eight,
   and a press opens the section and rings the setting. A long section (four
   group heads or more, at least 1.5 windows tall) gets a sticky index of its
   heads with the current one in `aria-current="location"`. The hash route
   `#/settings/<section>` already existed (router.js) and is kept as the only
   deep link; no per-setting hash. Enter on a nav entry (or a click) puts the
   focus on the section heading; the arrow keys still walk the list and keep
   the focus in it. Recipes: two rows in DESIGN.md, linted.
8. **Suggested downloads are model cards**, grouped by purpose (chat and
   filing, bigger machines, search, images, reading text), `settings-models.js`.
   One starting pick per group, in the catalogue's own words, labelled "our
   starting pick" and not a benchmark; it is the one filled button in its
   group. The server owns the numbers: the memory a model asks for
   (`ram_gb`: stated where the catalogue says "Needs ~16 GB", else the
   download size x 1.15 + 0.7 GB rounded up to a half), what it is good at,
   and the fit verdict against this computer's memory (`GET /models/hardware`,
   standard library only): Fits under 60% of memory, Tight to 85%, Too big
   above. System memory only; a GPU's own memory is not measured, and the page
   says so behind its '?'. A too-big download asks first. "Hide models too big
   for this computer" is a per-viewer switch.
9. **Download another model** takes an Ollama name or a Hugging Face link or
   `hf.co/` name, says what it is before anything downloads
   (`POST /models/inspect`, no network, no claim of a size), and then it is a
   card like the others, with the same progress and Cancel. `/models/pull`
   refuses what the check refuses. Only ollama.com and Hugging Face names are
   accepted; a name carrying another registry's address is refused.
10. **The Tools and Appearance panes stay one pane each, indexed** (the owner, L771:
    keep one pane, add the jump row). Measured 2026-11-14 (scratchpad/ui-sweeps/settingslong.js):
    Tools 5,850px with 5 heads, Appearance 1,267px with 8, every head one index press away and
    landing 58px down (under the 50px title); Tools' one long stretch is the 51-tool list
    (4,434px), whose filter brings a match into one screen ("web": 3 rows, 189px). (The Installed models list is model cards now, and the
    background-job "duplicate" was two settings, the utility model and the
    autonomous pass's own override, whose default now names the model it
    falls back to: HISTORY.md, "Moved from the plans, 2026-10-05 (444
    decision 10: the installed models as model cards)".)

## Placed from INBOX, 2026-11-11 (tray at its cap)

- **Partly built (compalive-1109, 1 commit each).** In-app: hour chime, idle return, battery low, window maximised and restored; desk: eleven acts; desk-only left: window opened, closed, dragged (no browser meaning); app-only left 35 (see `compalive-1109.md` (git history)). **Owner, 2026-11-09:** "also does the in-app companion have the same life and complex mechanics and actions and things it can do as the desktop companion?? they need to be just as good as each other". Measured (tests/test_companion_catalogue_1108.py): 8 entries are desk-only (battery low, hour chime, idle return, five window events) and 49 are app-only (juggle, meditate, lounge, hangs, sloth, the note and search reactions and their transitions); acts an hour, app 39.1 against desk 35.7 (test_companion_weights). **desklane-1109:** (a) desk reactions window_opened, window_closed and window_dragged built 9c989e9 (tests/test_overlay_react_1700.py); (b) the in-app-only acts that need frames before the desk can draw them, none rendered: dangle, kick_legs (legs-over frames on a window top), hang_one_hand, hang_by_feet, sloth (arm and inverted hang frames), chair (a chair prop), the positions lean, lounge, cross_legged, edge_dangle, back_float (a frame each) and lower.drift, move.afield; the note and search reactions (graph_laid, long_note, note_binned, private_note, remark, reminder_bell, search_found, search_nothing) need an events feed from the app's server to the overlay, not frames. Window events stay desk-only (no browser meaning).

## Placed from INBOX, 2026-10-05 (ledger triage)

460. **The owner, 2026-10-03 night, verbatim.** "I keep experiencing scroll
     jump when scrolling with two fingers on my trackpad?? idk". Placed: the
     orchestrator (reproduce with synthetic wheel streams; suspects: a
     scroll listener that writes scrollTop, scroll snapping, smooth
     scroll-behaviour on a wheel-driven scroller, anchoring).
     **Measured 2026-10-03, not reproduced**: 300 seeded notes, 250 wheel
     steps of 40px down and 250 up in headless Chromium (`.tab-main`
     scroller): no step moved more than 6px off its delta; 4 steps moved 0
     where the list paused to load its next page. Suspects left: the
     Notes rows' `content-visibility: auto` with a 132px guess (rows now
     70 to 160px) meeting a precision trackpad's momentum, which headless
     does not emulate, and the windowed list's page load at the end. Next:
     the owner's tab and window size, then a real-device trace.
     **Measured again 2026-10-05, not reproduced** (the smoothness agent,
     `scratchpad/ui-sweeps/smooth1005-wheel.js`): trackpad-shaped streams
     through CDP (140 wheel events of 6 to 10px, eased, every 8ms) down and
     up the notes list, the notes list entered 60% deep and scrolled up
     first (its rows between never drawn), a Settings pane, a 60-message
     chat thread and a 160-paragraph document: on all 10 streams no frame
     stepped back and none moved more than 1.5 times what was sent in it,
     and the distance moved equalled the distance sent. No listener writes
     a scrollTop under a wheel, no scroller snaps or smooth-scrolls. Left:
     a real precision touchpad's momentum phase, which CDP cannot send.

## Placed from the owner's list, 2026-10-10


Entries are the owner's words, then the recommendation. Bugs come first, then design requests.

### Bugs

- The first-run popups bullet is built (uiset): HISTORY.md, "Moved from the plans, 2026-10-11 (uiset, the first-run queue)".
- "I pressed done and it just didnt give me the tour at all??"
  Recommendation: Done starts the tour or closes it cleanly, with the handoff in Brief 37 (INBOX 745 (d)). Also carried by Brief 37 (tour handoff).
- "says done but the bar is still there??"
  Recommendation: the bar goes when Done is pressed, and the first-run state is checked on reload. Also carried by Brief 37 (first-run queue).
- "that's the box in the corner I was telling you temporarily appeared"
  Recommendation: reproduce on a fresh profile and name the box in the owner's terms before fixing it; the first-run queue in Brief 37 is the likely owner. Also carried by Brief 37.
- "I pressed install on the documents package and the progress bars appeared for the vision package and the documents package didn’t progress at all"
  Recommendation: each package's progress is bound to its own install job; test two installs at once. Also carried by Brief 37 (packages progress).
- "Also it failed to let me view the pdf doc I had as the package wasn’t installex, it should have given me a link to nav to where I can install it or just an install button directly"
  Recommendation: the PDF viewer shows an install button for its package in place of the document. No brief carries it; Brief 37 (packages progress) is the nearest.
- "There's overlap on these settings tabs in the sidebar"
  Recommendation: measure the overlap of the settings tabs at the sidebar width, then fix the layout. Also carried by Brief 41 (Settings two-pane).

### Design requests

- "very messy"
  Recommendation (taken): the surface is unnamed, so the Brief 41 density census finds the worst one; carried by L-ui-modernisation-53.
- "this panel looks like a demo and not professional"
  Recommendation: name the panel, then give it the designed empty, error and first-run states that ROADMAP Direction (reliability gate) asks for. Also carried by Brief 41.
- "is it possible to add and customise the metadata a little more??"
  Recommendation: custom note properties, shown in the metadata rows with one control recipe. Also carried by Brief 38 (custom note properties) and Brief 37 (metadata rows).
- "Note metadata and chat bubble metadata still feels incredibly messy, not modern, and unrefined. The whole app needs another ui/ux modernisation, professionalisation, and ui/ux enhancement improvement in many places."
  Recommendation: one metadata row recipe for notes and bubbles, measured for height and gap. Also carried by Brief 41 (density) and Brief 37 (metadata rows).
- "Some tooltip buttons are circles and some are rounded squares. Should they have backgrounds or borders that are visible??"
  Recommendation: one radius per control class and one visible border rule for tooltip buttons, from DESIGN.md tokens. Also carried by Brief 41 (one radius per control class).
- "No vertical gap"
  Recommendation: the owner has not named the surface; find the gap by the density census and fix it under the spacing tokens. Also carried by Brief 41 (gaps).
- "idk if it is just me but the ui still needs a more modern and professional polish. I think an issue might be that some of the ui elements, controls and dropdowns are too large and bulky and have too large spacing and margins around them and gaps around panels?? like the vs code ui is a lot more cleaner and refined and the sidebar is still floating but its more subtle, the controls are smaller and"
  Recommendation: the density census (control heights, gaps, radii, topbar height) before and after, against the VS Code reference. Also carried by Brief 41 (UI density).
- "also I think the topbar is a little large but idk maybe not. maybe research design principles or standards?? ensure wcag 2.2 accessibility is followed and complied with"
  Recommendation: measure the topbar height against the density target and run the axe sweep per surface. Also carried by Brief 41 (WCAG 2.2).
- "Ive been screenhotting parts of the perplexity interface and others but there are soo many more modern examples and ways to structure stuff. I think that all the controls and docks on each page and dropdown menus and popup menus and stuff just need a major polish and refinement and they all need to be consistent across the app. think maximum learnability, minimalist and instinctive to use. refined"
  Recommendation: one control recipe for every dock, dropdown and popup (kebabMenu, .dock, the tokens in DESIGN.md), checked by the ratchets in test_ui_recipes.py. Also carried by Brief 41 (UI density and refinement).
- "feel like there should be a subtle like meatball icon in the top right on the same line as the quick access title on aligned to the right above the quick access menu to allow for easier and more intuitive access to these buttons?? maybe not idk"
  Recommendation: build it only if the density census shows the quick access buttons are hard to find; use the kebabMenu recipe. No brief carries it; Brief 41 is the nearest.
- "do way to view logs of bg processes"
  Recommendation: a background tasks log in settings, read from the job runtime. Also carried by Brief 37 (logs of background tasks).
- "there's no option to have the ocr workspace in the quick access section in the dashboard, it also isnt accessible in the cmd palatte or find anything search"
  Recommendation: add the OCR workspace to quick access and to the command palette and search. Also carried by Brief 37 (OCR in quick access and palette).
- "The whole begin the app for the first time workflow is a mess, popups and notifications  clash with each other, the tour gets cancelled, to much goes on, and on the tour it is hard to see the other features  around the things highlighted."
  Recommendation: one first-run flow with a single queue, a tour that can be finished, and spotlight steps that leave the neighbouring features visible; measured on a fresh profile. Also carried by Brief 37 (first-run queue and tour handoff).
- "The packages install progress bars and stuff are very messy and need refinement and better information architecture and ux needs to be done for when features aren’t accessible because of an uninstalled package"
  Recommendation: one install panel with per-package progress and a link from any locked feature to it. Also carried by Brief 37 (packages progress).
- "There needs to be more utility on all features app wide and more ui/ux cleansing"
  Recommendation: this is the Brief 41 refinement pass plus the Brief 38 topic and note-property work applied on every surface. Also carried by Brief 41 and Brief 38.

### 12z Learnability, 2026-10-10 (INBOX 749)

The owner asked for "learnability" by name; no plan measured it. Five
numbers, each a Playwright run on a fresh profile, kept in
`scratchpad/ui-sweeps/learn.js` and reported in Brief 41's five lines:

| Measure | Today | Bar |
| --- | --- | --- |
| Time from first paint to a saved note, with no help opened | unmeasured | under 60 s |
| Tour steps whose target is visible and non-empty (INBOX 745) | unmeasured | all |
| Controls with a `data-help-for` popover, per surface | unmeasured | every control not self-describing |
| Guide questions answered from `help_chat.py` for the twenty first-week tasks | unmeasured | 20 of 20 |
| Keyboard shortcuts discoverable from the surface (a sheet or a tooltip) | unmeasured | all |

Decision: learnability work is a row here, measured by these five, never a
new plan; the first-run queue (Brief 37) and the Guide's topics carry it.

## Phase 13: the design review, every surface against the principles (Fable, 2026-10-10)

The owner, 2026-10-10: "do the same thing for the apps design, learnability,
structure, accessibility, usability, hierarchy, how tools and elements are
arranged, styled, bundled, positioned, spaced, colour ... what is poorly
designed ... for all surfaces." Phase 12 took the owner's observations
(density, hover, pickers, metadata, circles). This phase takes the
principles, measures the stylesheet and the markup against each, and names
what is poorly designed with its number.

**Method and limit.** The stylesheet was measured (16 files, 73,672 lines,
2,603 selectors, 412 custom properties) and `index.html` parsed (1,015
buttons, 15 dialogs, 110 selects, 278 inputs, 22 textareas, 347 dock
classes, 98 help popovers, 7 tabs). Brief 56 then observed the rendering
(2026-10-10; Chromium at 1440x900 and 390x844 touch; a notebook of 38 notes,
5 documents, a board and a map): `scratchpad/ui-sweeps/hierarchy.js` for the
counts, `contrast.js` (46 surfaces, both widths, both themes), `axe.js` (axe-core
with the wcag22aa tag; there is no `axe.js`, this is the sweep the plan
meant) and `a11yname.js`. "Visible" is `checkVisibility()` with a box of at
least 4 px; "in view" is also inside the first viewport. Each "Today" below is
an observed number unless it says "markup".

### 13.1 The principles, each as a rule with a measurement

DESIGN.md already carries contrast, alignment, repetition and proximity
(its "principles" section) and the recipe index. These are the rest, in
the order a person meets them, with what the code says today.

| # | Principle | The rule here | Today, measured | Judgement |
| --- | --- | --- | --- | --- |
| 1 | Hierarchy | one primary action per surface; three levels of emphasis (primary, quiet, ghost); the eye lands on the content, then the one action | 1,015 buttons in the markup. Visible at rest at 1440 (390): Notes list 316 (268; 63 and 24 in the first view, 38 note cards), capture 19, writing room 27, Ask 19, Chat 26 (19), Graph 11 (9), Timeline 17 (16), Reminders 20 (14), Documents 22 (10), a Library section 14 to 99 (the Skills list 99), an open board 35 (8), an open map 30 (10), a Settings section 28 to 167 (4 to 141), the Dashboard 24; the chrome adds 25 (11). Filled (accent) buttons: exactly one on 16 of 20 surfaces at 1440; two on the Dashboard (Save, Generate this week's dig) and the writing room (Compose, Save); none on Boards and Contents; at 390 the floating New note makes it two on Ask and three on the writing room. `.primary` is on 0 visible buttons (the fill is the base `button` rule) | one primary is nearly met (decision 20 holds on 16 of 20); the count of doors is the problem: Notes 316, Settings help 167, Skills 99 |
| 2 | Grouping (proximity, common region) | related controls share a container; a dock folds by width, never by count; unrelated groups are two spacing steps apart | 347 dock classes; `test_dock_grammar` holds the grammar. Of 14 content docks at 1440, 6 show more than seven items: Notes 10, Graph 9, Library 9, Chat 8, Timeline 8, Boards 8 (Library docs and media 7); at 390 none does, because 4 to 21 rows per dock sit in the folded menu | built 2026-11-01 (INBOX 1520): every dock folds by width, nothing by count (HISTORY, "Moved from the plans, 2026-11-01") |
| 3 | Alignment and rhythm | everything on the 4 px grid; one left edge per column | spacing literals off the scale: 7.2, 6.4, 4.5, 3.6 and 26.4 px (rem arithmetic leaking into px); the scale lint allows them because they are not in the spacing properties it reads | close the escape |
| 4 | Consistency (one recipe per need) | one value per role | 46 distinct font sizes (`0.8rem` 48 uses, `0.85rem` 34, `0.75rem` 27, `0.92rem` 24, all off the token ramp); 35 radius expressions; 59 `50%` circles (decision 3 allows avatars and the companion only); 75 distinct shadows against 3 elevation tokens; 96 distinct transitions; two z-index systems (1 to 60, and 1010 to 1040) | the ramp exists and is bypassed; each bypass is one decision below |
| 5 | Feedback and state | every control declares rest, hover, focus-visible, active and disabled together | 418 selectors with a hover rule, 282 of them with no focus rule (`.icon-btn`, `.graph-zoom-btn`, `.doc-dock-menu-btn`, `.wb-library-item` among them). Observed: a 40-press Tab walk over 14 surfaces, the chrome, the status bar and 7 Settings sections found 312 stops whose look did not change, 110 distinct controls (every status bar item, `.ghost.small` buttons, select openers among them) | a keyboard user sees two thirds of the app without its hover feedback; 110 controls give no sign of focus |
| 6 | Signifiers | an icon-only button has a label; one tooltip shape; a tool names its cursor | The 13 markup buttons with no text, `aria-label` or `title` are the status bar's 12 and the Logs copy row; JS paints each before it can be seen. Observed: 0 visible controls without a name across 20 surfaces, 6 menus each and 19 dialogs, at both widths; the 7 empty ones in the DOM are hidden until used and named when shown (chat model badge, map task, note and link markers). 93 icon-only buttons in the Notes list (59 at 390) are named by `title` alone. Real gaps: 20 task checkboxes in note cards with no label (axe critical `label`), the Dashboard heatmap scroller not keyboard-focusable, one 23.6 px tag span at 390. Tooltip shapes mixed (the owner) | the 13 are retracted as a defect and pinned by a test; the gap is the task checkboxes; the shape is decision 3 |
| 7 | Recognition over recall (learnability) | every action is in its surface's dock or menu, in the command palette with its shortcut, and in the Guide; no gesture without a visible alternative | 36 rebindable shortcuts in the table; 549 key checks outside it; the palette lists what the table knows | the shortcuts a person can learn are the table's; the rest are undiscoverable |
| 8 | Error prevention and recovery | undo over confirm (WORLD_CLASS 1.8); confirm only the irreversible; validation inline, at the field | six undo implementations; 98 confirm call sites (95 `confirmDialog`, 1 `window.confirm`, 1 unsaved-work prompt, 1 tool-call confirm) against 46 undo call sites; 18 markup overlays plus the built confirm, all centred cards at both widths | one undo contract (rule 1.8); the confirms are twice the undos |
| 9 | Progressive disclosure | the first view shows what most people need; the rest behind details, Customise or a menu | 278 inputs and 110 selects in the markup. At rest at 1440: Notes 1 text field and 1 select (and 20 task checkboxes), capture 3 and 1, writing room 4 and 4, Reminders 4 and 2; a Settings section 1 to 6 inputs and 0 to 3 selects, but 28 to 167 buttons and 9 of 20 sections with no filled button | the fields are few; the buttons are the load; Settings is the test case (decision 52) |
| 10 | Fitts and Hick | targets at least `--target-min`; the primary action at the pointer's resting place; menus under nine items or grouped | `--target-min` 86 uses, `44px` 5 literals; `test_a_long_kebab_menu_is_grouped` holds | the literals fold into the token |
| 11 | Colour as meaning | accent for the primary action and state; semantic colours for semantics only; chrome has no decorative colour | 265 hex and 323 rgb literals: 190 and 198 in the themes file (its job), 74 and 110 in tokens (its job), 52 and 26 in `08-consistency.css`, 28 and 65 in `02-chat-graph.css`, 26 and 7 in `06-timeline-dialogs.css` (not their job) | colour that is not a token cannot follow a theme or a palette; 200 literals outside the two files that own colour |
| 12 | Type | one ramp of seven tokens; body at 14 to 15 px; line height 1.45 to 1.5; nothing under `--text-xs` | the ramp is used 681 times; the four off-ramp rems 133 times | map the four to tokens and close the rem escape in `test_style_scale` |
| 13 | Motion | three tokens; motion explains a change of place or state and nothing else; reduced motion answered | `--motion-slow` 65, `--motion-base` 41, `--motion-fast` 28; literals `0s` 11, `80ms`, `250ms`; 35 reduced-motion blocks (linted) | slow is the commonest duration, which is backwards for an app that should feel fast |
| 14 | Specificity and the stylesheet's own structure | a rule lives with its component; no `!important` | 171 `!important` (45 in `02-chat-graph.css`, 40 in `08-consistency.css`, 40 in `07-whiteboard-misc.css`); `08-consistency.css` is 11,631 lines of corrections appended after the component files; `10-responsive.css` is 3,002 lines with 109 phone blocks away from their components; 236 selectors matched by no markup (census 24) | the consistency layer is where inconsistency is patched, not where it is prevented |
| 15 | Density | Phase 12 | Phase 12 | Brief 41 |
| 16 | Accessibility | WCAG 2.2 AA | Phase 12 decision 4. Observed: contrast 0 below 4.5 on 46 surfaces at 1440 and 390 in both themes; axe (wcag2a to wcag22aa) 2 rules at 1440 and 3 at 390 in both themes (task checkboxes without a label, 20 nodes; the heatmap scroller; at 390 one 23.6 px target) | Brief 41; principle 5 is the largest a11y gap this review found (110 controls) |

### 13.2 Surface by surface

| Surface | Hierarchy | Grouping and arrangement | Consistency | Learnability | The gap in one line |
| --- | --- | --- | --- | --- | --- |
| Shell: topbar, tabs, status | the brand, seven tabs, search, the model pill and the status compete at one weight; the header holds 13 buttons at 1440 (6 at 390) | the status bar carries 12 items in 37 px at 1440 and none at 390 (the phone shell takes them) | the header is 64 px at 1440 and 58 at 390, measured against a 28 to 32 px grammar | tabs are learnable; the status pill's meanings are not | one weight for everything; the status bar needs three states, not nine items |
| Sidebar (categories, spaces) | categories, spaces, tags and the rail at equal weight | the rail duplicates the sidebar's job on the phone | the floating sidebar's gutter is 8 px by decision 1 | drag targets with no visible alternative on desktop | a hierarchy of two (spaces over categories) and one rail recipe |
| Notes list and note card | title, facts line, body, chips at one weight; the facts line is a lint now | `entryItem` 915 lines builds a card with up to nine affordances: 316 buttons for 38 cards (about 8 each), 93 icon-only ones named by `title` alone | metadata rule (Phase 12 decision 7) | the inline query grammar is invisible | one muted metadata line; the query help in the box |
| Note editor and capture | the editor's bar, the selection bar, the inline AI and the slash menu are four surfaces for one task | the capture form's adders (documents, tags, templates) sit above the text | selection bar linted (`one sticky recipe`) | slash is discoverable (the hint), the selection bar is not | fold the four into two (bar and slash); the capture box shows the text first |
| Ask answer | the answer, its citations, sources, evidence, figures and the trail are six blocks | `renderAnswerSupport`, `renderEvidenceView`, `renderAskAnswerFoot`: three feet | citations `[**Title**]` since triage | a reader cannot tell which block to read first | answer first, sources as one foot, the rest behind one toggle |
| Chat | bubbles, meta lines, tool chips, the rail, attachments, the mode segment | `sendChatMessage` 1,079 lines renders and sends | metadata rule | the modes (Ask, Chat, Agent) are a segment with no explanation at rest | one bubble recipe with the meta line, one explanation line per mode |
| Documents and code | DOCUMENTS 17 and 21 | the live view bar and the block bar | `docCmTheme` 871 lines of theme | the slash menus are one system (DOCUMENTS 18) | Brief 42 |
| Whiteboard and mind map | the radial, the tool palette, the format panel, the properties sheet, the dock: five | `initWhiteboard` 3,730 lines | draw.io programme | the radial is a toolbar not a menu (linted) | the format panel as draw.io's one panel (programme phase 2) |
| Graph | the options folds (three) | GRAPH decisions | `gcDraw` 729 lines | folds are learnable | Brief 38 |
| Timeline | feed, table, scrubber | one row model | row tokens | keys documented in the plan, not the UI | Phase 5 adds the calendar; the keys go in the help popover |
| Library | gallery, activity, filters | `filterLibraryImagesGallery` 1,546 lines | chips as `.library-chip` | the filter well recipe | split along the seams (Brief 45) |
| Dashboard | greeting, clock, art, timer, streak, digest, widgets, quick links, features | nine blocks, 24 buttons, two filled (Save, Generate this week's dig) and a 4-item dock | widgets sized by `sizeDashWidgets` | the catalogue is a second navigation | "continue and today" (WORLD_CLASS decision 51) |
| Settings | 179 keys over panes; 20 sections, first view (models) 32 buttons | 28 to 167 buttons a section at 1440, one filled button on 11 of 20 | help on 105 rows | no search | WORLD_CLASS decision 52 |
| Dialogs and sheets | 18 markup overlays plus the built confirm, the sheet recipe linted | the 18 that render open as centred cards at 1440 and at 390 (337 px wide, 27 px gutters); none is pinned to an edge. By size at 390: 8 should be bottom sheets (extract 218 px, history 97, connections 126, binned 196, run a skill 155, board keys 168, meeting 294, features 157), 2 stay dialogs (confirm, welcome), 4 are page-sized (OCR 765, Settings 798, Shortcuts 798, Sketch 712), 4 are palettes (command, agent, finder, improve); one (document AI) did not render closed | one recipe (the lint) | consistent dismissal | 8 become sheets at 390 (13c) |
| Menus | kebab menus linted and grouped | hand-built menus ratcheted | one recipe | consistent | hold |
| Toasts and notifications | toast, undo bar, server-down banner, AI-offline notice, notifications panel: five channels | `status.js` 81 functions | one toast host | a person cannot predict which channel speaks | three channels: toast (transient), the undo bar (actionable), the panel (history) |
| Phone | the bottom tab bar, the FAB, the more sheet, folded docks | `phone-shell.js` 46 functions; `10-responsive.css` 109 blocks | the shell bands | the folded docks hide actions behind a kebab | phone rules live with their component (decision 19) |

### 13.3 Decisions, 2026-10-10 (do not re-decide; numbered after Phase 12's 8)

9. **A token budget.** 412 custom properties to under 200 by 0.8; a new
   token needs a recipe that uses it twice; `test_style_scale` ratchets the
   count downwards.
10. **Colour literals live in two files** (`00-tokens-shell.css` and
    `05-sidebars-themes.css`); every other hex or rgb is a token
    reference. The 200 outside them move to tokens; the lint fails on a new
    one.
11. **The four off-ramp sizes map to the ramp** (`0.75rem` to `--text-xs`,
    `0.8rem` and `0.85rem` to `--text-sm`, `0.92rem` to `--text-md`); the
    lint closes the rem escape.
12. **One layer scale as tokens:** `--layer-raised` 2, `--layer-sticky` 10,
    `--layer-dock` 20, `--layer-popover` 40, `--layer-sheet` 50,
    `--layer-modal` 60, `--layer-toast` 70, `--layer-lock` 80. The 1010 to
    1040 set folds in; a literal z-index above 2 fails the lint.
13. **Shadows are the three elevation tokens plus the focus ring;** 75 to 4.
14. **Motion is the tokens;** `--motion-base` is the default, `--motion-slow`
    only for a surface entering or leaving; a literal duration fails the
    lint.
15. **Hover and focus-visible are declared together.** A `:hover` rule on an
    interactive selector has a `:focus-visible` twin with the same visible
    change; `tests/test_hover_focus_pairs.py` ratchets the 282 down.
16. **`!important` budget 171 to 0 by 0.8,** by specificity, with a ratchet.
17. **Circles are avatars, the companion and the colour swatches;** 59 to
    that count, the rest `--radius-pill` or the button radius.
18. **`08-consistency.css` dissolves into the component files** by 0.8: each
    rule moves beside the component it corrects, or becomes the recipe; a
    ratchet caps its line count downwards and no new rule may be added to it.
19. **Phone rules live with their component;** `10-responsive.css` keeps
    only the shell bands; the same ratchet.
20. **One primary action per surface, counted.** Brief 56 measures visible
    `.primary` buttons per page at rest; the number must be one.
21. **Three notification channels:** toast (transient, six seconds), the
    undo bar (actionable, rule 1.8), the panel (history); the server-down
    banner and the AI-offline notice are toasts with the keep action.
22. **The Ask answer is answer, then one foot** (sources), everything else
    behind one "Evidence" toggle.
23. **The bar is a professionally designed product, and the references are named** (the owner, 2026-10-10, INBOX 755: "make the design on par and better than a modern professionaly designed web and app interface. research for inspiration and guidance if needed"). 13.R, before 13c: a reference read of six products the owner's users already know (a notes app, a task app, a browser, a code editor, a whiteboard, and the platform guidelines, Apple HIG and Material 3), one paragraph each in the retired analysis doc naming the pattern taken and the measurement it sets (rest density, primary count, dialog shape, motion length, type ramp), never a screenshot copied. Every 13.2 row then cites the reference its target comes from. The vendored design skill is consulted and overruled where the references disagree (HANDOVER "Skills").
24. **The lockup is "Tessellate" alone, centred over its tagline (the owner, 2026-10-27).** Verbatim: "im wondering if we should remove the "notes" from Tessellate notes" on the splash as it makes it look not symmetrical and off, sme in the readme file." The word "notes" beside or after the name is gone from the Windows splash (`scripts/splash.ps1`), the README header, the About group, the page and window titles and the website title; the desktop loading window and the boot splash stack the mark over the name, so the name's centre sits on the mark's and the tagline's. Measured (a Playwright sweep of getBoundingClientRect centres, light and dark): boot splash mark 671.8, name 743.2 before, 720 and 720 after; loading window 600 and 600 with the tagline at 600; About 840.8 and 840.8, lock 720 and 720. A lockup that adds a word again is the owner's choice.
25. **Search by meaning downloads only after a yes (the owner, 2026-10-27).** Nothing is fetched, neither the package nor the model, until the one-time question is answered yes. The first save that needs it sets `awaiting_consent`, `/models/status` carries `semantic_offer`, and a notice in the toast recipe says "about 2 GB from huggingface.co and pypi.org" with Download and No thanks (closing is a no); the answer is `semantic_auto_install` (default off) with `semantic_choice_made`, both written by one PUT. Search runs on keywords meanwhile and shows no error. Settings, Search and index, Download search by meaning turns it on later and starts the download at once. `TESSELLATE_NO_AUTO_INSTALL` stays the hard off-switch; `tests/test_outbound_inventory.py` passes without it.

### 13.4 Phases with gates

| Phase | Builds | Gate | Brief |
| --- | --- | --- | --- |
| 13.0 Measure | visible controls and primaries per page at rest at 1440 and 390, the dialogs classified, the 13 unlabelled buttons plus the JS-built ones, `axe.js` and `contrast.js` per surface, the confirms counted, `hierarchy.js` written | 13.1 and 13.2 re-written with numbers; a list of every offence per decision | 56 (Sonnet, medium); measured 2026-10-10, numbers in 13.1 and 13.2, sweep `hierarchy.js` |
| 13a The stylesheet's grammar | open: decision 12's eight-step layer scale (115 literals ratcheted), 13's shadows to tokens (7 ratcheted left of 19; the 7 are one-offs: three role-colour glows, two scroll-edge fades, the lightbox, one reversed hairline; `ui13a-1018.md` (git history)), 16's `!important` (96 ratcheted left of 128: the full-screen states are done; the rest are motion switches, print, the companion and overrides of script-set inline styles), the six `CIRCLES_LEFT` and 198 colour literals; 9, 10, 11, 14, 15 and 17 are built (HISTORY.md, "Moved from the plans, 2026-10-11 (UI_MODERNISATION 13a, Brief 57, the stylesheet's grammar)"; remaining list `grammar57-1011.md` (git history)) | every ratchet green; `contrast.js` and `errors.js` unchanged; no visual change except the hover and focus twins (measured by `getComputedStyle` on ten controls) | 57 (Opus, high) |
| 13b The stylesheet's structure | built 2026-11-12 (HISTORY.md, "Moved from the plans, 2026-11-12 (UI plan 13b, the stylesheet's structure)"); left: LEDGER L-ui-modernisation-51 (231 cascade-blocked Library-only rules); -30 and -31 are in HISTORY.md | the two ratchets; the sweeps unchanged; file count and line count recorded before and after | 58 (Opus, high) |
| 13.R The references | decision 23: six references read, the pattern and the number each sets, written into the retired analysis doc and cited from 13.2 | every 13.2 row names its reference; no target without a number | 57 (Opus, high), first step |
| 13c The surfaces | the 13.2 rows not owned elsewhere: the shell's weights and the status bar's three states, the sidebar's hierarchy and rail, the capture form's order, the Ask answer's foot (decision 22), the chat bubble recipe, the notification channels (decision 21), the dialogs that become sheets | each row's before and after numbers from Brief 56's sweep; `docks.js`, `contrast.js`, `touch.js`, `axe.js` green on every surface | 59 (Opus, high) |

Phase 12 (Brief 41) runs first; 13a and 13b are mechanical enough to run
beside it; 13c follows 13a.

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC3, D3 scales, axes and number formats for the Ask and statistics charts** (M, rank 3). `ask-chart.js` `askChartTicks` returns at most five integer ticks and the charts are hand-built SVG; D3 ships scale 32, shape 63, axis 4 and format 24 exports with 1, 0, 0 and 0 called. Measure: a chart with a 0 to 1,240 range gets round ticks (`scaleLinear().nice().ticks(5)`) and thousands separators; `contrast.js` and `docks.js` stay green; the chart's PNG export (`askChartPng`) still renders.
- **VC9, one icon picker** (S, rank 9). `pickIconOrEmoji` (all 1,530 Phosphor glyphs and the emoji groups) has 3 call sites (`editor.js`, `whiteboard-library.js`, `whiteboard-map.js`); Spaces choose their icon through their own `spaceIconPicker` (`spaces-find.js` lines 424 and 434). Measure: Spaces create and edit open the shared picker, `spaceIconPicker` is deleted, and the Space icon still validates server-side (`_validate_icon`).
- **VC14, Phosphor's fill weight for active states** (S, rank 14). One of six weights ships (`Phosphor.woff2` 147,380 bytes, regular only); an active or selected nav item is the usual home of the fill weight. Measure: the extra font bytes for the fill build, and the active-state contrast (`contrast.js`) with the fill glyph; drop the row if the bytes are not worth one state.

## Deepened 2026-10-10: statistics (Brief 72b, decision 71)

Measured with `scratchpad/ui-sweeps/deepen72b.js` (fresh data dir, no model,
96 notes, 12 reminders; 1440 and 390). The owner asked for "user and usage
and notebook statistics". Today there is no statistics surface; the numbers
are spread over four places. The dashboard: painted in 141 ms at 1440 and
573 ms at 390; ten sections (Reminders, Recently added, Favourites, Quick
capture, Recent documents, Boards and maps, Weekly digest, On this day,
Activity heatmap); 31 to 34 numbers on screen; `/insights/stats` answers in
13 to 79 ms with 5 keys (`total_entries`, `categories`, `per_day`, `days`,
`to_review`); 0 overlaps, 0 past the edge. Usage: Settings, General, "what
you use" (`#usage-box`, 3 clicks): "Most used: Dashboard tab 18, Chat tab 3,
..." and "Not used in 90 days (82)". The notebook in chat
(`notebook_stats.answer`, ten kinds): the count in 829 ms, the top tags in
1,416 ms. The graph's `#graph-stats` chip and the mind map's statistics item.
The palette's "statistics" finds nothing. All of it is deterministic. **The
bar:** Day One and Apple Journal (streaks, words, places), Screen Time's
weekly report (usage, against last week), GitHub's contribution graph,
Obsidian's vault statistics.

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | expansion | Statistics page: built | Built by Brief 89; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION statistics and utilities, Brief 89)") | |
| 2 | expansion | Weekly review card: built | Built by Brief 89; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION statistics and utilities, Brief 89)") | |
| 3 | redesign | Its charts from the Ask chart recipe on D3 scales (VC3 above) | no tick label overlap at 390; one chart recipe in DESIGN.md | 11, 7 |
| 4 | fix | The usage list's 82 unused features feed the weekly offer (12z, rule 6) | the dashboard offers one a week | 6 |
| 5 | optimisation | Chat's statistics answers: built | Built by Brief 89; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION statistics and utilities, Brief 89)") | |
| 6 | expansion | Statistics inside a window or topic ("notes about the harbor this month"; CHAT_PLAN catalogue A18) | the A18 rows at 1.0 | 12 |

**Briefs.** 37 (row 4), 65 (row 6), 75 (row 3), 89 (rows 1, 2, 5).

## Deepened 2026-10-10: utilities (Brief 72b, decision 71)

Same sweep. "More utilities": today the small tools are the dashboard's
focus session (a timer that notifies, `dashboard.js` near line 3906), the
reminders' parser, the documents editor's word goal, counts and reading
time, and the chat's statistics. `ai/arithmetic.py` exists, but chat
answered "what is 15% of 240" with a note and "convert 5 km to miles" with
"Nothing in the notes" (CHAT_PLAN foundation 7). The palette has 80
commands; "calculator", "timer", "convert", "word count", "stop the model",
"activity" and "health" each find 0 commands (only "Search everything for
..."). Settings' "Tools it can use" is the agent's tool switches, not a tools
pane for the person. No model needed for any of it. **The bar:** Raycast
(calculator, units, currency from a dated table, date maths, timers,
snippets and clipboard history, all in the bar), Alfred, Spotlight's inline
sums and conversions, PowerToys Run.

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | expansion | Utilities inline in the palette and the chat from one module: "15% of 240", "5 km in miles", "days until 25 Dec", "3pm Tokyo in London"; the answer is the first row, Enter copies (CHAT_PLAN decisions 47, 54, 56) | a 40-phrase set at 1.0 in both; 0 to 40 | 12, 2 |
| 2 | expansion | Timer and stopwatch: built | Built by Brief 89; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION statistics and utilities, Brief 89)") | |
| 3 | expansion | Selection counts: built | Built by Brief 89; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION statistics and utilities, Brief 89)") | |
| 4 | expansion | Templates from the palette: built | Built by Brief 89; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION statistics and utilities, Brief 89)") | |
| 5 | fix | A Guide topic per utility: built | Built by Brief 89; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (UI_MODERNISATION statistics and utilities, Brief 89)") | |

**Briefs.** 65 and 66 (row 1), 89 (rows 2 to 5).

## Deepened 2026-10-10: the command palette and Find anything (Brief 72b, decision 71)

Same sweep. The palette: Ctrl+K opens it at both widths; open 42 to 506 ms
at 1440, 222 ms at 390; 80 commands and 89 rows at rest; 0 overlaps and 0
past the edge at both widths. Of 18 queries, commands are found for
reminder, timeline, undo, agent, backup (2 rows), guide (the tour, not the
Guide) and calendar ("Open today's note"); none for "ocr", "read text from
image", "stop the model", "statistics", "calculator", "timer", "convert",
"word count", "find anything", "activity" and "health". Find anything
(`openFinder`, `spaces-find.js`): open 44 to 151 ms; "harbor" 18 results (16
notes, 2 reminders) in 840 ms; "Sam" 30 in 819 ms ("showing results for
sam"); "last week" 30 in 544 ms (words or a window, not verified); "boiler
pressur" 18 in 851 ms; "settings backup" 2 in 777 ms; "ocr" 0, with no
suggestion; 9 kind filters; 2 targets under 24 px. **The bar:** Raycast and
Alfred (one bar for commands, objects and answers, learned ranking, aliases,
results within a frame of each keystroke), Spotlight's top hit, Linear's
context-aware actions, VS Code's prefixes.

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | **Built 2026-10-10 (Brief 90; HISTORY "UI_MODERNISATION the palette, Brief 90")**: typed text reaches every catalogue feature, act and setting (`paletteFeatureRows`, `paletteActRows`, `paletteSettingRows`) | 7 of 18 words empty to 0 at 1440 and 390 (the other 4 of the 11 were found by rows added since the sweep); 0 catalogue features missing (`tests/test_palette_coverage.py`) | 2, 6 |
| 2 | optimisation | Find anything 544 to 851 ms after the last keystroke: under 150 ms per keystroke at 96 notes, under 300 ms at 5,000 | the sweep's per-query ms | 25g budget |
| 3 | fix | **Built 2026-10-10 (Brief 90; HISTORY "UI_MODERNISATION the palette, Brief 90")**: the palette's Nearest row and the handoff's why; Find anything's empty state with one way on (kind, dictionary spelling, nearest feature) | "ocr" finds the OCR workspace in both; calculater, remidner, ocrr, statstics 0 to 1 nearest | 4, 6 |
| 4 | fix | "last week", "in March" are windows through the one reading (decision 47) | every result dated inside the window | 10, 12 |
| 5 | expansion | **Built 2026-10-10 (Brief 90; HISTORY "UI_MODERNISATION the palette, Brief 90")**: `palettePick` (prefs `palette-picks`), `PALETTE_ALIASES`, the reason in each row's title | the row run before is first for 0 of 10 repeated queries to 10 of 10 | 2 |
| 6 | expansion | Utilities inline (the utilities block above) and the quick-add grammar's parsed act as the first row (CHAT_PLAN F2) | Brief 66's gate | 12, 2 |
| 7 | fix | **Built 2026-10-10 (Brief 90; HISTORY "UI_MODERNISATION the palette, Brief 90")**: the field is the band's hit area | 2 to 0 under 24 px at 1440 and 390; touch.js Find anything 0 under 44 px at 390 | 9 |

**Briefs.** 47 (rows 2, 4), 66 (row 6), 90 (rows 1, 3, 5, 7).

INBOX 776 to 783 (the owner's morning UI reports) are built (uipolish): HISTORY.md, "Moved from the plans, 2026-10-11 (UI_MODERNISATION, the morning reports)".

## Placed from INBOX, 2026-10-10 (the owner's afternoon reports)

Owners: uipolish (789), polish2 (790 to 792 and 788's design fixes), DOCUMENTS_PLAN for 788's features.

- INBOX 788, UI and features, documents and code, the owner 2026-10-10 22:35Z, six screenshots. "the topic edit popup needs a redesign and fix. are there any improvements made to the general document editor?? can you improve how references show with the buttons on them?? this outline tab of the sidebar is a little awkward and poorly designed. also in the code editor, this popup is poorly designed and spaced and stuff" then "the code ide and its panels need a design fix. also can you add code templates as document templates as well??", "maybe even add a code modules library like with the whiteboard and mindmap??", "and a way to better interact with the ai as a coding asistant like in vs code??" (Shots: the graph topic edit popup, name field crowding "7 notes"; a References row with Aa and x; the documents Outline tab; the code editor diagnostic "Expected ':'" with its fix button; the IDE bottom panel tabs and toolbar; the Console input.)
- INBOX 789, UI, the owner 2026-10-10 22:38Z, two screenshots. "not all buttons have the same hover states?? all the ui styles across the app need to be consistent, modern and professional." (All spaces gets a filled background; the top-right icons only tint.)
- INBOX 790, UI and bug, the owner 2026-10-10 22:40Z, three screenshots. "can you resesign or restyle these buttons in the ocr workspace header??" then "clicking that star button in the find anything panel just darkens the background and doesnt do anything. also I feel like the favourite active versions should be filled, not just a yellow outline. also when scrolling down, I feel like the sub menu bars are a little hard to see and access as they are so short height wise??"
- INBOX 791, UI, mind map, the owner 2026-10-10 22:42Z, three screenshots. "these buttons on the mindmap nodes are a little hard to see and interact with. also labels look pixelated" and "this side tab looks a little messy and needs a redesign" (the node's + and copy buttons; a blurry link label; the "This map" panel.)
- INBOX 792, UI, mind map, whiteboard and fit, the owner 2026-10-10 22:45Z, three screenshots. "also i dont think i should be typing in these outline options in the sidebar unless i like double click on them ore press an edit button on the side in the mind map. also on the whiteboard can you improve these arrow options and also show examples in the options as well?? there is only one actual arrow option for the links. also I feel like there should be the option to hide the flap in the corder of sticky notes. also the fitting to screen featurs on the graph, mind map, and whiteboard should be based on what panels are currently showing and the screen resolution/size."
- INBOX 793, UI, whiteboard, the owner 2026-10-10 22:48Z, two screenshots: "also I think the view and board dropdown menus in the whiteboard need a bit of a redesign and/or restyle" (Board: section heads, plain rows, then label-and-action rows like "Export ... Export...", "This board itself ... Delete"; View: two columns of toggles, the Grid select and shortcut rows.)
- INBOX 794, UI, whiteboard library, the owner 2026-10-10 22:52Z, screenshot: "also the previews in the library arent vissually accurate to what is actually placed and are a bit misleading" (the Library's General shapes draw grey filled shapes with a light outline; placed shapes take the board's colour, line and fill, e.g. a cyan-outlined triangle.)
- INBOX 795, UI, the owner 2026-10-10 22:55Z, two screenshots: "just make sure that the app actually recieves a propper ui polish and refinement. there are still some awkward sections. also I think the ui can be redesigned or made better on this panel like with the buttons. and in the popup for individual notes, there should be an option to open the sidebar." (the Connections panel and popup: a full-width bordered button per board and per note.) Owner: uipolish.
- INBOX 790 to 793 are built (canvasui-1010): see HISTORY.md, "Moved from the plans, 2026-10-11 (canvasui-1010)".

## Placed from INBOX, 2026-10-11 (the owner's sweep request)

Owners: the uisweep agent (Sonnet, measure and the mechanical fixes), then Briefs 57, 58 and 59 (Opus) on its findings, ahead of 61 to 63.

- INBOX 800, UI, the owner 2026-10-11 02:40Z, verbatim: "Can you do another devibecoding, ui/ux modernisation and professionalisation sweep across all ui faces??" Placed: every surface at 1440 and 390, both themes, through `devibe.js`, `vibecheck.js`, `hierarchy.js`, `consistency.js`, `hoverbox.js`, `focusring.js`, `contrast.js` and `axe.js`; the findings, each with its number, go to `uisweep-1011.md` (git history); mechanical ones fixed in the sweep, design ones taken by Briefs 57 to 59 in that order.

## Placed from INBOX, 2026-10-11 (the owner on buttons, OCR and the constellation)

Owners: grammar57 (button families), the ownerfix agent (Sonnet) for the rest.

- INBOX 803, UI and bugs, the owner 2026-10-11 03:35Z to 03:45Z, screenshots (Loose ends, While you were away, Kinds of link, the OCR workspace, the constellation in both themes), verbatim: "Im still iffy about the design use of these buttons styles in some places... also the select button in the all notes top bar is rectangular and not square, should it be square?? in the questions subtab and possibly elsewhere, the icons in the rows get underlined as well." ... "on the ocr workspace, when rapid ocr and potentially the others are reading the text, if that image already has a description or caption, it doesnt show until the image's ocr is read." ... "The ocr workspae regions are a little off, there is an awkward squashed text box at the bottom of the right text area. Should the notebook ocnstellation have an off white background on light mode like with dark?? Also when I switch back and forth between light and dark mode, the notebook constellation adjusts suddenly or jolts a bit and doesn't have a smooth fade transition. Also when I click the capture a note textbox in the capture subtab for the first time, it adjusts a bit because the line numbers werent originally showing." Recommendations, taken: outlined bordered buttons inside dashboard cards become the quiet recipe, and counted chips (link kinds, claims) become chips, not buttons; an icon-only toolbar button is square; a row link never underlines its icon; the caption shows before reading starts; the empty region editor below the read text is not drawn when it has nothing; the constellation sits on a tinted well in light too and fades between themes; the capture box reserves its line-number gutter from the first paint. Then, 03:50Z, three screenshots of the code editor (the assistant's Quick fix, Format, Run tests, Find usages; the snippets panel's Save selection; the toolbar's Format, Run, Assistant, Snippets, each a tinted bordered box): "Im also iffy about the design and use/style of these buttons". Recommendation, taken: a toolbar is quiet buttons in one dock (DESIGN.md `.dock`), the one primary action filled; suggested actions in a panel are quiet rows or chips, never a grid of tinted boxes.

## Placed from INBOX, 2026-10-11 (bars, notifications and tours; grammar57)

- 809, the owner, verbatim: "is there a way to redesign areas in the app like these??" (Help, "Welcome and tours": fourteen bordered tinted buttons and one filled "Start the tour"). Target: one primary, each tour a row with its line and length, the recipe wherever a button wall is found.
- 811, the owner, verbatim: "something about the design or smth of those buttons in the notifications and buttons in notifications in the noficiations panel is bugging me, can you try redesigning them or fixing it somehow?? I cant quite place it". Target: Undo a quiet text button on the meta line beside the time; read and dismiss on hover and focus in every row, never replacing the time; "Undo expired" as meta text; stale "Started:" rows are the transparency agent's.
- 813, the owner, verbatim: "also idk but I feel like it looks awkward when some things have borders and other things dont in a header but idk im not an expert. and some dropdowns have different ui styles?? all ui styles and elements needs to be consistent across the app." Target: one bar select (the dock's filled, borderless one), one filter trigger, one view switch order (list, grid), only the primary filled in a bar; a lint counts each.

## Placed from INBOX, 2026-10-11 (voice notes, live captions, the focus timer; voiceup)

- INBOX 828, the owner 2026-10-11, verbatim (the Voice note dialog: transcribing, then "couldn't be transcribed"): "also if I record a meeting or audio thing for a transcription and it is loading, if I close it, can I leave it in running in the background, and access it when it is done or open up the panel again to check on it?? can I get a notification when it is done?? also can I stop it from transcribing or even as a bg process?? the voice note feature and ui needs a massive redeisgn and upgrade, things like noise supression, voice enhancement, audio input devices and ports etc need to be managable, and idk if the line animation even works. also where is the live transcription?? where is the live captions?? are they features yet?? hwo do I use and access them. ..." The failure in the screenshot was PyAV 14 refusing faster-whisper's `metadata_errors` argument: fixed 2026-10-11 (`voice._decode_samples`, tests in `test_voice_api.py`).
- INBOX 829, the owner 2026-10-11, verbatim (the Focus timer widget): "can you redesign the focus timer as well??" (board and map previews are in WHITEBOARD_PLAN; the toast's buttons went to grammar57 with 811).

Measured from the code: live captions exist (captions.js, Brief 82) but are reached only from the command palette, so the owner could not find them; the voice note has no device, noise or gain control; transcription runs inside the dialog's request.

V1 to V8 (voice notes, live captions, the focus timer) are built (70f2622cc, 72fc97ee8, 1a27526f8); the decisions moved to HISTORY.md, "Moved from the plans, 2026-11-10 (s10b-1110)".

## Placed from INBOX, 2026-10-11 (Tidy, undoing a pattern, menu gaps)

- INBOX 830, the owner 2026-10-11, verbatim (Tidy's "Category names" review, empty; Patterns rows with Confirm and Not right; "Recent runs (3)"): "this tidy panel is poorly designed and needs a ui/ux fix, redesign and/or restructure. also if I have confirmed a pattern then I cant undo it. also some dropdown menus across the app have wierd gaps at the start and end"

Decisions made:
- T3. A confirmed or rejected pattern keeps an Undo on its row and in "What it learned" (owner: learnaudit, with decision 68).

Rows: T3 (learnaudit); T1, T2 and T4 are built (HISTORY.md, "Moved from the plans, 2026-11-02 (a30b)").

## Placed from INBOX, 2026-10-19 (mobile1314)

- INBOX 1314, the owner 2026-10-19, verbatim: "the mobile view needs a bit of redesign and layout/nav reworking because it is annoing to use and the bottom nav bar just doesnt make sense with how it works and is layed out and is annoying to use."
- Measured before (390x844 and 360x740, light and dark, a touch context; `phonemore.js`, `phonetabs.js`, `phonechrome.js`, `phone.js`): More drew as the bar's first column (x=0), not its last: `#tab-bar { order: 3 }`, two header-era rules in 02 and 05, still applied inside `#phone-tab-dock`. Columns Notes, Chat, Graph, Library and More, 78x57 at 390 and 72x57 at 360; Dashboard (home, one of Simple mode's four) behind More while Graph held a column. More's sheet: seven rows, three pages and four tools, undivided. Two buttons called More (the header's menu and the bar's). Pressing the tab you are on did nothing. A reminder's +1h was 39.6x44 (a coarse-pointer floor of 38px against the 44 decision); at 360 the timeline's seven days were 41.8px and its head 322px in a 300px card. No sideways scroll on any tab; every page ends at the bar's top (786/786) and every last control scrolls clear of it.
- Decision (taken per standing order 3): the bar is Dashboard, Notes, Chat, Library, More, left to right; Graph, Timeline and Reminders are More's first group.
- Built 2026-10-19: the order rules gone; the four columns; More's sheet in a lazy file (`phone-more.js`) with pages, a hairline, then tools, the page in hand `aria-current`; the header menu named "App menu"; the active tab pressed again scrolls its page to the top (`tabPageScroller`); the coarse-pointer floor 44; the timeline under 380 (the existing 380 block in 10-responsive.css) wraps its year menu and lets the day well take the card's padding (44.5px days). Guide topic `phone-nav`. After: `phonemore.js`, `phonetabs.js`, `phone.js` (390, 360, dark) 0 findings.
- Not verified: a real phone (safe-area insets resolve to 0 in headless Chromium); the smooth scroll-to-top under reduced motion on a device.

## Placed from INBOX, 2026-10-27 (speed and smoothness, 1415)

**The owner, 2026-10-27, verbatim.** "can you work on optimising everything, making transitions and adjustments smoother, dropdown panels and popups that appear smoother, better transitions, fail states, no glitches or visible lag etc, very very fast to use and flick between everything". With a lag log from their machine (Windows, 2026-10-27 08:13 to 08:21 UTC).
     Done (HISTORY, lag 1415): the forced layouts in the zoom keydown, dashboard map size, OCR fit and pinch, boot emblems and Settings focus. Re-read 2026-11-14 against the code: (2) is built (`routes_models.py` `prewarm_installed` asks at launch, polls wait 0.05 s and 0.2 s cold, then serve the last answer: INBOX 1419, 1426, 1492), (3) is DESIGN.md's Motion section (durations, curves, a menu leaves the way it came, reduced motion), (4) is DESIGN.md's `surfaceFailed(el, what, retry)` recipe (`tests/test_ui_recipes.py`, `vibefail.js`). (6), carried by L-ui-modernisation-54: a lag budget sweep per tab (input under 100 ms, frame under 50 ms): `scratchpad/ui-sweeps/tablag.js` measures it; loaded machine 2026-11-14, 1440x900: every tab under 100 ms input on a repeat visit except Graph (88 to 104 ms) and the first Graph visit (184 ms with its lazy load); a quiet-machine run decides. Not reproduced on this machine; the owner's Windows lines, on the same row: Timeline first load 1180 ms, `app.js` `Response.json.then` layout, tab button onclick 85 to 135 ms, boot `status.js` build 1295 ms.

## Placed from INBOX, 2026-10-29 (1435 Appearance panel, 1436 sketch and noise art)

**1435** (Appearance quick panel): built e22c9f8, moved to HISTORY.md ("Moved from the plans, 2026-10-29 (appearance 1435)"); leftovers in `appearance-1435.md` (git history).

**1436** (Wander and Drift, paused art as a picture, the cheaper-equivalent pass): built, moved to HISTORY.md ("Moved from the plans, 2026-10-29 (backgrounds 1436)"); left over in `bgart-1436.md` (git history).

## Placed from INBOX, 2026-10-31

- 1351 (the owner, 2026-10-25, verbatim in HISTORY): usable daily for life and uni, fast, reliable, accurate, no bug found in five minutes of use; standing, served by every polish and speed agent.

## Placed from INBOX, 2026-11-04 (1657, what the two lag rounds left)

- **1657 left.** At 4x CPU on the dashboard with Atlas walking: the tail beat is 1.85 to 2.2 ms a call (target under 1 ms, or the sway as a group transform on the compositor); the buddy arrival (`nameMarkBuddyArrive`, avatars.js, 216 ms) and shell-reminders.js (156 ms) are the first layout flush after other boot code dirtied the page, so the fix is to find the writer, not the reader; keydown max 136 ms over 22 keys (the owner's 1848 ms did not reproduce). Check: the same measures from `/tmp/lagw/lag.js` (copy it into `scratchpad/ui-sweeps/` first) with each under its target.

## Placed from INBOX, 2026-11-09 (what 1698 left)

1643. **Owner's log, 2026-11-04 02:23Z:** "raf 439ms on graph: graph-canvas.js gcRequestDraw 54 calls/s, 8.1ms each" for at least 10 s on the graph tab. Recommendation: the graph redraws only while something moves (layout settling, a drag, a hover change) and stops when still; measure calls/s idle after settle. 2026-11-04 later: not reproduced (idle 0 draws/s at 36 and 336 notes, 4x CPU); every self-requested frame (glides, fade-ins, the composed hover) now counts toward one 300-frame bound, reset by any outside request (eef88b5, d809297). Open until the owner's next log shows no gcRequestDraw line; the 03:08Z pointerout and atlas.js lines did not reproduce either (handlers 0 to 2 ms). **(b) Owner's log, 2026-11-08:** "input 312ms on notes: pointerup on span.tab-label in #tab-btn-notes" (twice, also on dashboard "on an element that has gone"); "frame 269ms on dashboard: inline TimerHandler:setTimeout 266ms"; "frame 207ms on dashboard: 172ms before rendering ... the page loading". Recommendation: profile the Notes tab switch and the dashboard 266 ms timer with the lag reporter's own trace. **(c) Owner's log, 2026-11-08 10:52:** "input 712ms on chat: keydown on textarea#chat-input" and "frame 589ms on chat: avatars.js nameMarkBuddyTempo 13ms; 7ms; 7ms" when sending the Agent-mode greeting (handed to the chat 1693 b agent). Lag pass 2026-11-08 (`lag-1108.md` (git history)): the Notes tab 312 ms is native style and layout over 9,228 elements (JS under 150 ms), the dashboard 266 ms timer did not reproduce, the chat Enter cost is one needed layout; 1634 d throw guard after a window is shown merged (cc0ca315). Open: a per-selector style trace on a quiet machine, `content-visibility` on old chat turns. **lag-1109:** the graph at 44 notes at 4x CPU: idle 0 gcRequestDraw/s, a 3 s hover 25 draws (8/s, 36 ms in all), idle again 4 s later; still not reproduced.

1698-lag. **Owner, 2026-11-09, lag logs:** notes view frames of 270 to 1018 ms "before rendering with no script over 5ms" that grow over the session; "raf 166ms on graph: graph-canvas.js gcRequestDraw 55 calls/s"; "whiteboard-library.js BUTTON#wb-side-tab-library.onclick 194ms (forced layout 177ms)"; "library.js openDoc 148ms (forced layout 58ms)"; "panel-movable.js done 228ms (forced layout 224ms)", "diagram-split.js stop 167ms (forced layout 167ms)", "obj-drag.js objDragMove 206ms (forced layout 198ms)". **lag-1109 (850e0f0):** `avatars.js release` (forced layout 2965 ms) fixed (drop reads the ledges first; hover strokes judged once a frame); a 60-cycle soak of tab switches, Settings and drags kept elements flat (12.8k), so no leak: the growth is a larger page to lay out. Open: the library tab click, openDoc, panel-movable `done`, diagram-split `stop` and objDragMove forced layouts, each from a trace on a large notebook (none reproduced on 44 notes); count `document.querySelectorAll("*").length` each minute over an hour of real use.

## Placed from INBOX, 2026-11-09 (the tray at its cap)

1671. **Owner, 2026-11-04 10:45Z (Windows):** "for some reason I cant windows button left or right arrow split screen the app?? it looks like it is about to do it but then it resets back to the non maximised window", then "wait now it worked?? idk but it didnt work for like 10 times??". Not reproducible off Windows. `min_size=(420, 500)` (`__main__.py:1770`) is below any half screen, and nothing calls `restore()` but `_bring_forward`, so the lead is a busy UI thread: Snap is undone when the window does not answer its size messages in time, and the same minutes logged 1 s input frames with no script in them (INBOX 1667, the dashboard's style and layout). Recommendation: recheck after 1667's layout fix; if it recurs, log WM_SIZE handling time in the desktop log.

1645. **Owner, 2026-11-04 (screenshots: the desktop card, square, Atlas cut at the foot; the menu card with Atlas in its right half):** "also can the desktop companion be transparent and polished and refined?? it still isnt right and it gets cut off and it doesnt move and it just isnt what I want it to be right now" (with 1638: "look at these as an example: DesktopGoose, goose"). Recommendation (taken): build the goose-style overlay of the design note placed in BACKLOG 16 (rows O1 to O5): a native layered, transparent, click-through-where-clear, topmost window on its own thread in this process (per-monitor-V2 on that thread), drawing pre-rendered frames of Atlas (both looks, rendered here with Playwright, transparent background), walking along the bottom of the work area, sitting, sleeping, noticing the pointer, dragged and dropped with a fall; the quick panel stays the small web window opened beside it on a click. On Windows it is the default, with the card window as the fallback when the overlay fails (logged). Scope: nothing that touches other windows. **Built (O1 to O4), owner check O5 pending on Windows.**

## Placed from W34, 2026-11-11 (gap5: open perf and tooling rows, sized)

- **Settings body as per-pane templates (L; perfset-1108).** The body is one template of 2,700 nodes (settings-body.js), model cards attach 16 x 6 listeners per open (settings-models.js:327, 440), `wireSettingsFolds` attaches 19 fold toggles (settings.js), and a search match that moves to another pane re-runs `showSettingsSection`. First step: delegate the model-card and fold clicks from the pane root, then split the body into one `<template>` per pane built on first view (`onSurface`, settings-body.js:63). Check: Settings open frame 138 ms (settings.js onclick 97 ms, 4x CPU, w34-fix2) to under 100 ms, with `test_frontend_ids` and `test_manual_parity` green. Needs a quiet machine to measure (load 10 hid it).
- **Style cost of the 3.5 MB sheet (L; owner-asks-audit-1108 1667 m, 1643 b, lag-1109:9).** Tab clicks at 4x are 32 to 112 ms of script inside 142 to 551 ms frames (Notes 32 to 58, Dashboard 73 to 81, Library 48, Chat 112) against 678 `:has(` selectors; the rest is native style and layout, and no handler is over 100 ms. First step: a per-selector style profile (Chromium's selector stats through a trace) on the Notes tab, then rewrite the costliest `:has(` selectors as a class set by script. Done when the Notes tab click frame falls under 200 ms at 4x. Not yet profiled: the first step may show the sheet is not the cost.
- **Backdrop click walks the router back and re-opens the Dashboard (M; owner-asks-audit-1108 1620).** One 580 ms frame: router.js:223 `onpopstate` 223 ms of script, then `renderDashboard` (about 69 ms) via `goToTabHistory` (navigation.js:1094). First step: when the entry being returned to is the tab already on screen and nothing changed, skip `openHistoryEntry`'s render and only restore scroll. Check: the same sweep, frame under 250 ms; the blind-tester on Back, Forward and the history menu.
- **Meeting recorder wired at load (M; row21-1109:43).** meetings.js:2441 to 2514 wires the recorder and recordings list when the bundle loads (61 elements); the openers are `openMeetingRecorder` (:961) and `openVoiceNote` (:986). First step: move the recorder wiring into `onSurface("meeting")` and call it from both openers. Check: a trace on a 5,000-note notebook showing the boot-time cost it saves (not yet measured: if under 5 ms, close the row as not worth it).
- **Graph options panel read at boot (M; row21-1109:44).** `#graph-options` ids are read by prefs.js, navigation.js:1995, wiring.js:1125 and avatars.js at boot (249 elements). First step: move those reads behind a `graphOptionsReady()` that builds the panel on first need; `tests/test_frontend_ids.py` is the check.
- **Boot CSS cap room and p5 (M; row21-1109:45).** A ratchet change. Owner decided 2026-11-12: keep `BOOT_CSS_CAP` where it is and free room (dissolve 08-consistency.css in 13b, move surface-only rules into lazy sheets), then lower the cap to the measured size in the same commit. Never raise it.
- **Lazy-bundle call lint is blind to bare function names and destructured bindings (L; lzc-1101).** `tests/test_lazy_bundle_calls.py` `reads` (:850) has no scope, so widening `_top_level_bindings` (:736) gave about 30 false reads (2026-11-02 attempt). First step: block-scope tracking in `reads` (a brace-depth stack of declared names), then widen the bindings. Done when a fixture with a shadowing `const` in a block passes and the real tree shows no new failures.
- **The board step in the perf probe (M; owner-asks-audit-1108 1667 f).** No probe step opens a board. First step: add one step that opens a 300-item board and records the first-paint long tasks. Needs a large seeded board (`seed-boards.js`).

## Placed from INBOX, 2026-11-11 (the tray at its cap: companion motion items and the chat Sources rows)

1606. **Owner, 2026-11-03 (screenshot, the enlarged companion viewer):** "when I move my mouse up and down somewhat fast over atlas's head like im patting it, it shift's atlas's position up by like 30px for a second or two". A quick pointer pat over the head in the viewer lifts Atlas about 30px for a second or two. Recommendation: a pat is a reaction in place; whatever lifts the figure (a hop or dodge triggered by repeated pointer entries) is not run in the viewer, or runs without a vertical offset there; a test drives repeated pointerover events and measures the figure's top. **Not reproduced (a31q):** about 8 variations (fast, slow, jitter, 1440 and 2560 wide, float and stand); the figure's top moved at most 9.7px and the buddy box 0. Carried by L-ui-modernisation-55 (the owner's window size and pose, or a recording).
1670. **Owner, 2026-11-04 10:27Z (two screenshots: Atlas hanging upside down on a bush in the in-app scene; the desktop companion sitting on the taskbar edge):** "the companion still sometimes get cut off a little on the ride. it doesnt move and it still sits like 20px above the bottom bar which I assume is what it is perched on. it is also not animated except for sometimes jumping a little up and down in y position and maybe twitching a little when the mouse is near". Follows 1663 (frames re-rendered, FLOAT_BAND): the desktop perch gap over the taskbar, the frame cut on a ride, and the idle desk companion barely animating (no roam, no idle loop, only small hops and a twitch near the cursor). Recommendation: measure the frame's transparent foot margin against `perches.py`'s taskbar top, test that idle runs a loop and roams, and fix in the overlay engine. Also (10:29Z): "the desktop companion was atlas and male until I unlocked it and it changed to my female preference setting that I had it as" (fixed: the last unlocked look and motion are kept in the desktop prefs and stand while locked); and (10:30Z) "the companion doesnt move". Owner 10:36Z (four screenshots: Quick search panel with a large empty band above the title and the close button pushed out; Quick note's field squashed to one clipped line, its placeholder cut through the middle; the search results card and the close button as a big grey square): "also I cant drag the companion to hang on another section of the top fo my screem, it always falls. I want the desktop companion to have just as much life and realistic npc feel as the actual companion in the app. also when I press search the panel that appears isnt right. the quick note gets squashed. the ui in each of those popups needs a lot of cleaning and refinement. also it keeps flickering or jolting or smth, it isnt clean, it doesnt sit cleanly over my screen and instead floats high, it doesnt do other things, can it sit on and interact with other things on my screen?? can it fly around and be a curious npc?? can it tuck behind my taskbar or the edge of my screen or top of my screen?? can it have the same and better life than it does in the app, micro movements, actions, behaviour, interaction and more". Then: "transitions and micro behaviours as well, different ways to move close range and further away", and "can the desktop companion also have more option on selection in the popup menu??" (both in the 1670 workflow, wf_d87990ee-fca). Then, 10:55Z (screenshots: hanging from the top edge, idle mid-screen): "it hangs off my screen top edge fine but it sits sooo far above my taskbar which I assume it is sitting on. also it bobs up and down quite fast when idle in place which I think it should be more slow and graceful (mind you if it is the regular companion and not atlas it shouldnt float and should instead walk, run, climb, crouch, sit, lie down etc. it just bobs up and down really fast and also it keeps crossing right in the middle of my screen which is distracting. also when it is moving it looks like it is walking backwards as it's body and head dont turn or look or move in position. also its tail needs better and more realistic movement and physics (for the desktop and in app companion), same with the lower whisp body and the nebular. also the nebular flow keeps flickering in and out for the desktop companion" Then, 11:00Z: "also the only way to have it hang from the top of my screen is to throw it up there, if I try to drag it, I cant bring it closer than like 20px from the top of my screen, also it has no transition or long distance move animations like the regular companion and it has no other behaviours or emotions and no real life to it", then two screenshots: "see rn it is moving to the left" and "and this it it m,oving to the right" (the same front-facing pose both ways). Then, 11:02Z: "also it moves across my screen a lot and is distracting and stuff, I want it to be a buddy not a nucance. the desktop goose was designed to be annoying and walk all over your screen as it is a prank, this companion needs to be intentionally designed and fun to have around" Then, 11:05Z: "the desktop companion needs to be a really complex npc, it needs really realistic behaviour, really detailed micro expressions and transitions between movements and actions, it needs a lot of actions and activities it can perform or do while idle, it needs ot be really smooth in its movement and travel, it needs to be very varied and natural, it needs to be very lightweight and smooth to run. it needs ot be the best and most realistic npc I have ever seen", then "also make sure it runs properly on linux as well". Then, 11:10Z (refines the buddy rule): "also the companion can still move across my screen or move around, it just needs to do it smoothly and in a way thaty the user will look over yk??" Then, 12:17Z (screenshots: the desktop companion over the Claude sidebar, then mid-screen over the chat): "it keeps bobbing really fast and the nebular flow around it keeps blinking in and out", and "also in the last 2 minutes it has crossed my screen completely and just chilled in the middle like rn". Then, 12:20Z (screenshots: the in-app companion and the desktop one, both in the arms-up hang pose, the desktop one in mid-air above the taskbar): "also it was hanging but then I threw it down and now it is stuck like this". Built 2026-11-04 13:00Z (236fd45, from the 12:17Z and 12:20Z reports): bob 4 px at 0.22 Hz with the walk and idle frames re-rendered steady (wash step about 6%, was 30%); not hidden for a maximised window (state 2, was 2 s every 30 s); a throw from a hang lands and leaves the hang pose, desktop and in-app. Unverified on real Windows. Open: the crossed-the-screen roaming (row B running). Owner, 2026-11-04 13:15Z: "also the desktop companion cant sit still, it has like adhd, it constantly moves and keeps jumping up and down or bobbing like it cant sit still". Recommendation (taken): at rest it is still: no bob while it sits or stands (breathing at most 1 px, slower than 0.1 Hz), long settled spells of minutes, a hop or fidget only as a rare chosen act; measured as vertical travel per minute at rest on the engine with fakes, checked against row B. Owner, 2026-11-04 13:22Z (screenshot: the desktop companion floating over the bottom of a chat app's text box while the owner types): "also the companion doesnt long distance travel as in teleport or vanish or walk off one side and appear on the other side walking from there, it instead decides to slowly make its way riiiight across my screen while Im trying to do something and even while Im typing this it is covering my text bar". Recommendation (taken): a long trip leaves by the nearest screen edge (or fades out at its spot) and comes back in from the far edge, never a slow crossing of the middle; while the person types (keyboard activity, or a caret in the foreground window) it does not move into or rest over the foreground window's caret or text box, and if it is already over one it steps aside to the nearest edge or the taskbar; its home spots are edges and the taskbar, not the middle. Owner, 2026-11-04 13:25Z: "also why does it bob up and down so much, it is floating, and it does it so fast". Placed with 13:15Z: a hovering floater drifts at most 2 px, slower than 0.1 Hz; the bob only while it travels (wmpj1mqin). Owner, 2026-11-04 13:28Z: "and then it basicallky doesnt move while it is hanging and it doesnt hang for a while because it falls down to the bottom again and starts bouncing". Placed with 13:15Z (whvqxijj3): a hang lasts tens of seconds to minutes and is alive (slow swing, glances, sway), it lets go by choice, and a landing is one soft settle with no bounce. Owner, 2026-11-04 13:32Z: "what about bortaling or vanishing in a puff or gliding places, or jumping around or climbing". Placed with 13:15Z (wdi8tdsvx): a travel repertoire (portal ring, puff, glide near edges, jumps between window tops, climbing a window side, edge exit and re-entry), chosen by distance and mood and varied; reduced motion is a fade. Owner, 2026-11-04 14:10Z (clarifies 13:15Z): "also when I mean sit still, it can still move and have life to it where it is, I just dont want ti bouncing up and down like an energetic child". Placed with 13:15Z: at rest it stays alive in place (glances, ear and tail moves, breathing, a stretch, grooming, a shift of weight, head turns), with no vertical bounce or hop loop; rest means no y travel, not no motion. Owner, 2026-11-04 14:14Z: "also the desktop companion doesnt move smoothly, it is very framey and not seamless". Recommendation (taken): measure first on the engine with fakes, then fix the class: (1) pacing: host.py wakes by `SetTimer`, whose 15.6 ms granularity turns the 33 ms walk tick into 31 or 47 ms steps (judder); while moving, pace by the display (DwmFlush or a high-resolution waitable timer, about 60 Hz), and let the window position follow time, not tick count; (2) positions: the float bob and sway are redrawn every 0.125 s (8 Hz steps), so any motion that moves the window updates at the move rate; (3) cycles: idle is 12 frames at 8 fps and walk 6 frames, so render more in-betweens (about 24 idle at 16 fps, 12 walk) within the frames' byte budget; (4) a pose change blends over about 120 ms instead of a hard cut. Acceptance on the simulation: frame-to-frame interval while moving 16.7 ms plus or minus 3, no step over 3 px at walk speed, idle wakes no higher at rest (rest still sleeps). Queued after the desk-still run (wdi8tdsvx) on its branch. Owner, 2026-11-04 15:40Z, verbatim: "now the desktop companion when it is idle doesnt have any subtle animation to it at all, cant it be like the regular companion??". Recommendation (taken, refines 14:10Z, does not remake it): at rest the window stays put (no bob, no sway, no trips), but the figure keeps living in place the way the in-app companion does, without pause: breathing, blinks, a slow tail and ear sway, and the occasional glance, all drawn inside the still window; asleep, a slower breath. Paced light: at most 12 redraws a second at rest, and none of the window moves, so CPU stays near the burst-only figure (report draws per minute before and after). Done after desk-smooth (same engine and frames). Owner, 2026-11-04 15:45Z, verbatim: "also nearly every time I throw it no matter how hard, ti goes to the top to hang from the top edge (the desktop companion)". Lead: a thrown floater has no gravity (`_do_fly`: `FLOAT_DRAG` decay and a `FLOAT_PULL` to its hover), so any upward part of a throw carries it to the ceiling, and `_hit_ceiling` takes hold on any contact at any speed. Recommendation (taken): the ceiling catches only a throw that arrives fast and mostly upward (else it bounces down off the top like the side walls and drifts back to its hover); the release grab (`_grab_edge`) only when let go, not thrown, within reach. Measure the share of throws that end hanging over a seeded spread of angles and speeds, before and after; target under 15 percent of a uniform spread, and only the hard upward ones. Owner, 2026-11-04 16:40Z, verbatim: "the atlas desktop companion when it is idle doesnt really have any animation ro subtle movement to it at all and it randomly jitters up and down. I want to to feel alive like the regular companion and be more naturala nd biological". Placed with 15:40Z (wf_001b3d32-e0c, in review): the jitter is new. Lead: the 24 idle frames (desk-smooth) or the 120 ms pose blend drawing frames whose figure baselines differ, so a cycle or a blend steps the body up and down inside a still window. Recommendation (taken): measure the figure's bounding-box top and bottom per idle frame and per blend step (alpha bbox on the rendered frames); no step over 1 px between neighbours, the window 0 px; the life in place is continuous and organic (breath as a slow ease, blinks at irregular 2 to 7 s, a tail and wisp sway with phase lag, glances with a head turn), at most 12 redraws a second. Owner, 2026-11-04 17:05Z, verbatim: "also the way that the desktop companion rotates int he air is not realistic at all, it like rotates by 45 degrees each time and at 1 second intervals". Cause: a throw's tumble is 8 pre-rotated frames (`SPIN_STEPS = 8`, sprites.py and engine.py, 45 degrees apart), and the spin rate follows the current flight speed (`SPIN_RATE * min(1, speed / ...)`, engine.py about line 2003), so as the throw slows each 45 degree frame holds for about a second. Recommendation (taken): rotate continuously (rotate at draw time, or at least 24 to 36 steps with the 120 ms blend between them); angular velocity set at release from the throw's speed and the hand's swirl, then decaying by its own drag, with a bounce or wall contact changing it, not tied to the current speed; it rights itself with an eased turn as it settles. Acceptance on the simulation: no step over 15 degrees between drawn frames, frame interval while tumbling 16.7 ms plus or minus 3, the angle's rate continuous (no jump over 30 percent between ticks except at a contact). **Fixed 70ef502 (16:40Z and 17:05Z):** in the air the window moves 0 px (was up to 4), the wave hop 0 px (was 3), a look blends over 0.24 s, a sit blinks, blink gaps irregular from 2.05 s (mean 4.6), the tail no longer repeats, a tumble turns in steps under 15 degrees and rights itself. Open: nothing ran on real Windows. **E18 true.** The desk companion ride, perch gap and idle life are W15 (open; real Windows unverified); e1c7298, 8b3db9c and c19a902 are on base but the owner's 11:00Z points are not closed. Desk half w15-1111: no engine change in this pass; the desk sitting gap and the idle loop need the Windows run (OPEN W15).
1683. **Owner, 2026-11-04 23:35Z (Windows, screenshot of the desk Atlas beside its right-click menu: Companion, Settings, Stay here), verbatim:** "with thw atlas companion I still dont see much organic or natural subtle movement with the lower body whisps and the nebular streams. also with the fact that it is like a cat npc, I still want it to have more and more detailed behaviour and decision trees and behaviours, and actions it can do with props and more. the desktop companion menu is quote short(edit: it was only short the first time I right clicked it after startup) and I still feel like it could do with a massive massive detailed animation and npc behaviour tree and and just allround improvement, its rotating when thrown and while it is falling is still horrible. also the whole desktop companion feels really laggy and framey and it doesnt have any of that natural smooth feel at all." Recommendation (taken): four classes. (a) Smoothness: measure the overlay's real frame interval on Windows (sleep granularity, timer resolution, per-frame work, frame count of each act) and pace frames on a steady clock with interpolated position, so motion is even at the display rate; (b) throw and fall rotation: angular motion from the throw's own velocity with damping, continuous (no stepped angles), and a settle to upright on landing; (c) the lower-body wisps and nebula streams move all the time with layered, phase-offset noise and follow-through from the body's motion, never a still or looped-looking tail; (d) the menu measured short on its first open after start: size it after its rows exist. The deeper behaviour tree and props join 1678 (BACKLOG), built next. Owner, 2026-11-04 23:45Z, verbatim: "atlas's tail and other and subtle idle body movements also feel like a png that doesnt smoothly wrap around so it does a movement then cuts back to the start". Recommendation (taken): (e) every looping act and idle cycle (tail, breath, sway, wisps) wraps seamlessly: the last frame leads into the first (periodic curves, first and last pose equal in value and velocity, no hold or reset frame), and a change between acts or cycle variants blends from the current pose instead of restarting; measured as the pose jump at the wrap (no larger than an ordinary frame step) for every loop in the frame set and the in-app rig. Owner, 2026-11-05 00:05Z, verbatim: "also the natural and biological and really detailed lower body whispy movement and the nebular movement and subtle animations I mentioned apply to the in-app companion as well". Taken: (c) and (e) are built in the shared rig, so the in-app Atlas gets them first and the desk frames carry them; each is measured in the app at 1440 as well as on the desk. Owner, 2026-11-05 00:10Z, verbatim: "also yeah, the desktop companion doesnt react to or interact what is on my screen at all, all it does is sit on the taskbar and poof to change postions along it, I can drag it up to hang from the top edge but it falls down within like a minute or two and it doesnt even move anymore other than poofing, also is poofing the only movement it has now?? because that;s all Ive seen". Found: travel.py never walks a leg longer than a share of the width or through the middle third (an older "slow crawl across the screen" complaint), so most legs are a puff or portal; window perches exist (engine.py CLIMB_EVERY, PERCH_FOR 20 to 50 s) but the owner has never seen one on Windows, so the window list may come back empty there; motion runs at about 30 Hz. Recommendation (taken): (f) travel by its body first: walk or glide at a lively pace (a run or a series of hops for long legs, not a slow crawl), jump up onto window tops, climb window sides, drop between windows; puff and portal become rare flourishes; (g) find why no window is perched on Windows (log what the window list returns, cloaked, minimised and DPI-scaled windows, the fake win32 layer against real EnumWindows shapes) and make it perch, ride a moved window and hop off a closed one; (h) a hang ends by its own choice (it pulls itself up onto the edge, swings and drops to a perch, or lets go with a reaction), never a plain fall on a timer. Owner, 2026-11-05 00:15Z, verbatim: "wait it just moved a little to the right, but then it poofed back to where it was almost instantly". Likely class for (f): a short walk that ends inside the middle third is undone by `out_of_middle` (travel.py) with a puff; a leg must never be reversed by a rule it already obeyed. Parts f, g, h: Fixed e1c7298 (travel by body), 8b3db9c (perches, rides, hops off), c19a902 (a hang ends by choice); numbers in `desk-1670.md` (git history); real Windows unverified. Owner, 2026-11-05 00:20Z, verbatim: "it it possible to sometimes walk of one side and come back on the other or even to do that if  thrown?? cna it climb up the side of windows or the side of the screen?? cna it tuck behind the task bar or side or top edges?? can it tuck behind a smaller window thaty isnt full screen?? can it imspect stuff and react to more events and have really detailed and varied actions and not all the same stuff every time, go really depp on this, make it incredibly smooth, all micro actions and frames, no visible frame changes, smooth trransitions in bodu movement between behaviours and actions, varied travel for short and long distance,". Recommendation (taken): (i) wrap-around: a walk off one side comes back in from the other (the `edge` mode, made common), and a throw past a side does the same, keeping its speed; climbing up a window side and a screen side, then onto the top; tucking behind the taskbar and the side and top edges (the existing peek, from every edge), and behind a smaller window (placed just under that window in the stacking order, peeking round its edge, coming out when the window moves or closes); inspecting things (a window corner, the clock, the cursor, a new window) as acts; (j) smoothness everywhere: continuous motion between every act (blend from the current pose, no cut), micro actions layered on any act, varied travel (stroll, run, hop chain, glide, climb, wrap-around, rare puff) chosen by distance and mood, no act repeated in a row. Built with 1678 and 1684 (the shared mind and the on-machine render that gives every in-app pose to the desk). Then, 2026-11-05 00:10Z, verbatim: "also when I throw the desktop companion and it rotates it doesnt perfectly land on its feet it often lands on its head and just stays at a 45 degree angle for a couple seconds before it instant resets, I want it to either land on tis feet, land on its back or stomach and like skid or smth or fall off, can it flail?? can it smack into the screen edge and slide down or potentially go through it and come out the other side?? if it is skidding down a surface can it scrabble for purchcase?? can it climb and pull itself up?? if it is standiong on a window and I move the windown, can it potentialy fly out of the way or if it was like on a beanbag or sidding down or lying down can it potentially slide off or acctidantally fall off like the chair tilts back and it needs to poof or portal somehwere else and then ti looks worried or miffed lol? or other wise it cna be anchored to the window. its small stuff like this, dont stop there, add more, also can you add these to the in-app companion as well??" Recommendation (taken): (k) landing by outcome, never a held tilt or a snap: the spin at contact picks feet (a crouch and settle), back or belly (a skid with friction that ends in a roll up), or a bounce off the ledge; a flail while airborne; a hit on a screen edge squashes and slides down it, or wraps through to the far side when fast; a slide down a surface scrabbles and either grips and pulls up or drops; a perch on a moved window rides it (anchored) or, on a fast move, is thrown off with a flail, a poof or portal to safety and a miffed or worried look; a lean-back on a prop can tip it over by chance. The same outcomes in the in-app companion (one shared physics and outcome table). Then, 2026-11-05 00:20Z, verbatim: "just make the companion (both desktop and in-app) really varied and complex in event and decision trees, it needs to be the best npc my desktop has ever had and more". Recommendation (taken): (l) one shared mind for both companions (BACKLOG 1678): needs (energy, curiosity, boredom, comfort, mood) that rise and fall, a utility pick over every act with weights from the needs, the time of day, the screen and the pointer, memory of the last acts so nothing repeats, chains of acts with a goal (fetch a prop, use it, put it away), and reactions that interrupt by priority; measured by a seeded hour-long run (distinct acts, longest repeat, chains completed). **2026-11-05 01:45Z to 02:00Z, the owner, verbatim:** (m) "I cant properly resize the companion when it is hanging, can the resize circle move to the bottom right instead if it is hanging?" (fixed 9d5fd92, measured 2 px from the figure's right and bottom, a press reaches it). (n) "the lower body and nebular still have no movement or subtle organic natural animation to them, they dont even ahve different variations or change based on body position". (o) "when clicking on it for the first time the desktop companion popup menu appears really short in height, also its landing after being thrown is still very not smooth and framey and no organic at all" (screenshot: the desk menu showing two and a half rows with a scrollbar), then "it lands well but then it turns like 90 degrees for a couplke second then turns back" (screenshot: Atlas on its side over a window). Parts (a), (b), (d) merged abb372f after these reports; the sim on abb372f shows 0 of 80 seeded throws holding a tilt of 30 degrees or more after landing, so recheck on Windows first. (p) "like keep going deeper and deeper with the complexity of the companion and atlas, both in appa dn desktop, rn the desktop one feels very subpar compared to the in-app one. go bakc trhough my conversation history and analyse all my requests for the companion and incorporate them all into the workflows". Recommendation: one ledger of every owner companion ask (`companion-asks.md` (git history): verbatim, surface, built and measured or not, evidence), then every missing or desk-only-missing ask is in scope for the companion lane, desk parity with the in-app companion first. (q) "also the desk atlas agent workflow doesnt seem to be doing those things for the in-app one as well??" (the wisps work, 0f94048, is in both; frame pacing, throw rotation and the menu were desk-only; every later 1683 part is built for both companions). (r) "also I cant resize the desktop companion like I can on the in-app one". Recommendation: the desk figure gets the in-app size handle's behaviour (a corner handle shown on hover, a pull away from the stand or hang point sizes it, a double-click resets, the size remembered and shared with Appearance). (s) Orchestrator: tests/test_overlay_x11.py::test_on_a_real_server_the_window_is_placed_shaped_to_the_figure_and_the_desktop_is_read fails under load (-n 3 with the overlay suite; once in CI on 3.12) and passes alone 39 of 39: find the race in the Xvfb start or the first map, wait on a real signal. (t) **2026-11-05 02:08Z, the owner (screenshot of the desk menu), verbatim:** "also what does the come here button do, it seems useless". Found: `_come` (engine.py:1236) walks to within COME_GAP of the pointer, but the menu is opened on the figure, so the pointer is already beside it and the 60 px "close enough" test makes it stay put; `out_of_middle` also keeps the goal out of the middle third, and it only ever goes along the ground. Recommendation (taken): "Come here" means follow me: after the menu closes it waits for the pointer to move, then comes to it wherever it is (the middle of the screen, onto a window top, a climb or a glide), reacts when it arrives (a happy look, a hop), and keeps company for COME_FOR; a second "Come here" while it is following stops it; the row's help says so. The same in the in-app companion's menu. (u) **2026-11-05 02:10Z, the owner, verbatim:** "also the take a nap doesnt stick for the desktop companion, it doesnt go somewhere else, it only ever poofs and it doesnt portal or walk off screen and back on somehwere else, it needs a lot fo expansion". Recommendation (taken): a nap holds until it is woken (a poke, a drag, a menu command, or its own long nap of minutes, never the roam or trip timers), shown as sleep with breathing and a settle into a comfy spot first; "Go somewhere else" and every roam leg pick a travel by distance and mood with no repeat in a row (walk, run, hop chain, climb over, glide, portal out and in, walk off one edge and come back from the other, a puff only rarely), measured as the mix over 200 seeded legs on the desk and in the app. **Progress (wisp-1109, a1683 a / 1696 w):** measured first, the desk's lower body was already a per-tick flow warp that is never identical for 2 s at rest (seeded sit, 20 s: 457 to 482 changed hem pixels a tick, 100 percent of ticks, hem centroid span 1.1 to 1.3 px; walk 450 to 650 a tick); what was missing is that it ignored the breath (hem rise against the swell r 0.0 to 0.24). Now the hem lifts a beat after the chest with each strand later than the last (`FLOW_BREATH` 1.5 px, same flow view and same wakes, rest wake bar unchanged); the stop's lag, overshoot and settle are pinned (-5.0 px leant, +2.5 px overshoot, settled in 3 s). Real Windows unverified; amplitude is held under the 4 degree join, so say if it still reads too still. Desk half w15-1111: the hop chain on a perch has a seeded measure and test (a5b795b81); new travel art (L9) and the deeper behaviour tree stay open.
    - **(u) fixed 66d494d:** a nap holds 150 to 300 s (pointer, caret, roam and follow do not wake it; a poke, drag, menu command or the timer does, ending in a stretch), settles out of the middle third first; wander legs mix walk 35, run 32, edge 17, portal 16, puff 1.5 (the floater glide 33, swoop 34); the in-app table aligned (smoke 3 to 0.25). Not verified on real Windows. (g), (r) and (s) of 1683 are built since (the status line below).
    - **(v) Fixed (merge of worktree-agent-ac37f259ec14fa51d, 861795d): every throw kind is laid upright 0.5 s after first floor contact, both gaits, walker's feet on the floor (were 9 px high); unverified on real Windows.** **The owner 2026-11-05 03:20Z (Windows; screenshot: the desk Atlas on the floor above the taskbar, still drawn tilted about 45 degrees, its tail curled round), verbatim:** "also it keeps turning even after it lands when I throw it (desktop companion)". Recommendation (taken): once a thrown figure is on the floor it rights within a bounded time (under 0.6 s) and is laid upright, never tumbling or tilted while sliding or at rest; reproduce on the seeded sim with throws of several speeds and swirls (soft, hard, a corner bounce), measure the time from first floor contact to `laid` and the angle at rest, pin both.
    - **(w) the owner 2026-11-05 03:25Z (Windows), verbatim:** "also it alwasy chooses the taskbar as a perch, it never chooses to hang and it doesnt interact witht he othe rhtings on my screen". The owner's log (01:51 to 01:52Z): "windows listed ~490, standable top edges 1, worth the trip 0 (458 invisible, 12 cloaked, 11 tool window, 7 minimised, 2 maximised, 1 no frame, 1 own overlay, 1 perch)". Recommendation (taken): the desk companion uses what is on the screen: a maximised window's title bar and the screen top are hang spots, the bottom edge of a floating window is a hang spot, a window top is a perch, the taskbar is one choice among them (never the only one while others are in reach); hanging is a chosen act with its own weight, not only the end of a throw; a seeded sim with the owner's mix (one maximised window, the taskbar, a floating window) shows each choice over 200 trips; the log line names the hang spots too.
    - **(w) and (g) built 8d7ae01, 20c6a91:** maximised windows kept as hang spots (title bar, work-area top, a floating window's bottom edge); hanging is a chosen trip; no destination kind three times running; log counts hang spots. Seeded sim, 200 trips, floor/window/hang: owner mix before 100/0/0 (taskbar only), after 58/0/42; with a floating window 54/46/0 to 38/33/29. Not verified on real Windows. **(x) the owner 2026-11-07, re-sent the (e) to (k) asks from the last session and added "also portalling".** Measured against the code: built are landing outcomes (feet, back, belly, skid, bounce: `landing.py`), the flail and wall scrabble (`engine._air_wobble`), throw wrap-around, riding a dragged window (`engine._ride_sideways`), and portal as a travel mode (`travel.MODES`). Open: (1) after a scrabble, grip and pull up onto the edge, or drop; (2) a window moved fast flings a figure off it with a flail; one that is lying, sitting or on a prop may slide or tip off, then it poofs or portals somewhere else and looks worried or miffed; slow moves keep it anchored; (3) tuck behind a smaller window and peek round its edge; (4) portal used as the escape after a fall-off and kept in the travel mix, its share measured by the seeded one-hour simulation; (5) the in-app companion gets the same outcomes (scrabble, pull-up, fling, the miffed face). Recommendation (taken): one Sonnet build after companion-s merges (same files: engine.py, landing.py, companion-throw.js), tests first, simulated on FakeWin32; Windows check by the owner. **(y) the owner 2026-11-07 14:40Z, verbatim:** "also make it peek out from behind the taskbar and other windows or sidebars or the bottom or other edegs if the taskbar isnt showing or is anchored to a different edge. make it really dynamic, perform the deep dives, ABSOLUTELY MAKE SURE YOU HAVE MISSED NOTHING AND WILL COVER EVERYTHING IN MY REQUESTS, KEEP DOING MY ORIGINAL REQUESTS, DO EVERYTHING AND IMPRESS ME PLEASE. Im going to sleep :D" Recommendation (taken): peeking reads the real taskbar edge (SHAppBarMessage ABM_GETTASKBARPOS, any of four edges, auto-hide state) and every docked appbar or sidebar, peeks from behind the taskbar, any screen edge when the taskbar is hidden, and the edges of smaller windows (z-order just under them); folded into the 1683 (x) build. A coverage ledger of every owner ask in 1683 (a) to (y) and 1692 (a) to (q) is written first, each row marked built, partly built or open with the file and test, and the deep dive closes only when every row is built or carries a reason.
    - **Status per sub-item, 2026-11-09 (travel-1109), measured against the code:** built are (a) to (e), (f) to (h) (e1c7298, 8b3db9c, c19a902), (i) to (l), (m), (o), (q), (r) (desk size handle, Group 3), (t), (u), (v), (w), (g); (x) 1 to 5 and (y) are built (CHANGELOG "Desk companion edges", "Companions use edges more", "In-app companion (INBOX 1683 x and k)": scrabble then pull-up or drop, a fast window move flings with a flail and a miffed face, tuck behind a smaller window, `win32.bars` for any taskbar edge or sidebar, portal as the escape); (s) the race found: Xvfb writes the display number and its newline as two writes, the test read the number alone and closed its end, the second write failed ("Cannot write display number to fd", logged 10 times in 8 loaded runs) and the server exited; the test now reads to the newline, and waits on the server process (a dead server ends the wait at once, else up to 60 s) instead of fixed 15 s tries. **Travel mix (the standing ask: seen travel, not teleport):** a ground leg can now be a chain of hops (`travel.MODES` "jump" was only used to get onto a window; `engine._hop_arc`: one arc per 1.1 figure widths, 0.16 of the height at the top, eased in with the pace and out over the last span, a crouch first, the hop picture while airborne, the body never leaves the floor). Seeded, six seeds, both gaits, a simulated hour each (261 and 272 legs): jump 3.4% to 8.8%, walk 10.3% to 11.0%, run 5.7% to 3.3%, glide 18.4% to 17.6%, vanishes (blink, portal, puff) 23.4% to 21.7%, puff 0.4% to 0.7%, no mode over 18%. tests/test_overlay_hops_1109.py. **Carried:** the desk half of B1, B3, B5, B6 (pose-keyed lower-body and nebula variants rendered into the frames) by L-ui-modernisation-57; the Windows check of everything above by L-ui-modernisation-56.
1696. **Owner, 2026-11-08 13:33Z to 13:45Z, seven drops, verbatim:** (a) "when the desktop companion is falling, it stops and glitches at like 8 frames per second or smth as it is falling in the downward arc". (b) (screenshot: the feminine Atlas tumbling over the top of a File Explorer window, not maximised, on a 2560x1504 screen at 200%) "I tried to drag the desktop companion onto the top of my file explorer window but it just fell and didnt register at all, it cant register my screen events or objects at all 😞 also sometimes it just floats from the bottom up to like 2/3rds up my screen then up to hang from the top of the screen then falls down after like a minute, when it is hanging it never stays up there veryt long, idk why it stopped like half way up my screen and idk why it was even just moving up across my screen, its animation didnt change so it just looked more like a bug than an actual biological movement or decision". (c) (screenshots: Settings rows; a "modified" or selected row's blue left bar sits a few px left of its card on one row and right against the panel edge on another) "some blue vertical selected or modified lines on settings items are fine but others are like right against the edge on the left, they need to be consistent". (d) (screenshot: What it learned, "The week of 20 July was a busy week", From 10 notes: a link reads "The Complete Social Skills Guide**") "there are some md asterisks that are left over in the what it learned link??". (e) (screenshot: the Settings nav with "Account & security" selected at the very bottom edge, cut by the scroller) "if I select something right at the bottom in the settings sidebar and other sidebars, I feel it should scroll a little down to give comfortable room for the selected item unless it is the last item". (f) the owner's log 13:33 to 13:44: "Lag: input 592ms on dashboard: pointerout on div.row.space-between in #dash-grid"; "frame 489ms on dashboard: animation loops (top: atlas-motion.js after) 6ms"; "frame 216ms on dashboard: app.js Response.json.then 195ms (forced layout 89ms) [apiJson /preferences from settings-panes.js renderPrefs, /jobs/last-runs from settings.js refreshJobRuns, /preferences from personas-pane.js renderPersonas]"; "input 456ms on dashboard: pointerout on div in #settings-nav"; "frame 292ms on dashboard: inline TimerHandler:setTimeout 284ms"; desk scan at 13:34:19 "windows listed 11, standable top edges 0, worth the trip 0, hang spots 0 (487 invisible, 17 cloaked, 11 tool window, 9 minimised, 2 no frame, 1 own overlay)". Recommendation (taken): (a) measure picture builds per second and their cost during a fall at dpi 192 on FakeWin32 (lead: a spun or fall picture rebuilt per angle step, `runner` turn key and `spun_at`); target the display rate with no build over 8 ms, cached or precomputed spins; (b) a release over a window's top edge perches on it from a fresh scan at the release (not the last periodic scan), with a log line naming why an edge was dropped (Explorer may be counted "no frame" or cloaked); a rise to a hang spot is a seen move (climb, cloud, blink), never a stand frame sliding up, and never stops part way; a hang lasts minutes by mood, not about one; (c) one inset for the selected and modified bar on every Settings row (a token), with a lint; (d) note titles in link lists are read without markdown marks (`**`, `__`, `#`), one shared helper, with a test; (e) the selected item in Settings and every sidebar list scrolls into view with one row of room below it unless it is the last (scroll-margin, a recipe in DESIGN.md); (f) the two pointerout lags and the renderPrefs forced layout traced and cut, measured before and after. **Then, 13:50Z, verbatim:** (g) "I still cant clcik off diagram elements, also I still dont think you have made those major behaviour and npc life like a AAA game"; (h) "also every time I change things like the activity on the desktop companion, it closes the popup menu and I have to reclick it to open it and see what the new state is"; (i) "I pressed go somewhere else, it just stayed as it was and started moving to the left and didnt really have any change in animation or body position or motion, but then it got halfway across my taskbar and it just poofed back to where it was"; (j) "also it just sits there, t doesnt react to anything that happens on my screen, it doesnt do activities like sit down or fish ot sleep, or read or idk whatever else Ive mentioned ot you can come up with, it just doesnt have that life I keep asking for". Recommendation (taken): (g) deselect on an empty press, outside the picture or Escape, every kind (ui agent); (h) a choice that changes a setting keeps the desk menu open with the new tick, a move closes it (desk agent); (i) a menu wander arrives with a seen gait and becomes home (desk agent); (j) the presence spells (sit with tea, read, doodle, fish, stargaze, blanket nap, plant) ship in 6a2921d2; next a design pass on reactions to screen events (window opened, closed, moved, focused, minimised, a full-screen app, media playing, notifications, idle and return, the time of day) and travel targets that need no window, measured by a seeded hour and checked by the owner on Windows. **Then, 13:52Z to 13:58Z, verbatim:** (k) (screenshot: the feminine desk Atlas floating mid-air near the desktop icons, top left) "now its not even hanging from the top of my screen"; (l) "throwing the in-app companion actually froze my app": "Lag: input 6456ms on dashboard: pointerout on p#dash-submessage.dash-submessage", "frame 7627ms on dashboard: companion-throw.js spotNow 7500ms (forced layout 6905ms); settings.js BUTTON#settings-btn.onclick 26ms (forced layout 22ms); app.js DIV#settings-modal.onclick 23ms", "frame 294ms: animation loops (top: companion-throw.js next) 128ms (forced layout 117ms); avatars.js ResizeObserverCallback 19ms"; (m) "sending a message to the chat still causes it to spasam up and down really fast", with "input 456ms on chat: keydown on textarea#chat-input" and "frame 349ms on chat: avatars.js nameMarkBuddyTempo"; (n) (screenshot: the Writing room, "Your thoughts" holding the raw text "[[Uni is done!! :D]]" after a note was added from the Tray) "the writing room doesnt handle or render attachments". Recommendation (taken): (l) first, the same hour: the 6.9 s is a whole-page layout paid by the first read after Settings opened and closed (the 1634 d and 1667 fixes moved the read, not the cost); profile that layout at 4x CPU (style recalc from :has or wide selectors over about 16,000 elements, the Settings modal kept laid out while closed) and cut it at the source, with a ratchet on the layout after a Settings open and close; (k) a hang spot at the screen top is always offered, with a test; (m) reproduce on a throttled CPU (1693 b); **built 2026-11-08:** the jump strip toggled on every call in a chat that fits the pane, resizing the transcript 45 px (51 to 69 reversals in 3.5 s at 4x, 0 after); the companion's `nameMarkBuddyTempo` style flush is left in `chatspasm-1108.md` (git history); (n) a note dropped or added from the Tray into the Writing room becomes an attachment chip whose text the writer uses, not a raw [[link]], with a test. **Then, 14:00Z to 14:05Z, verbatim:** (o) (screenshots: an answer's "Elsewhere in your notebook" and "Why this answer" toggles; the Elsewhere list opens above "Ask next", the Why trail below it) "elsewhere in you notebook stuff appears above the ask next stuff, but the why this answer stuff appears below, also their visual style of the buttons doesn indicate that they are a dropdown and different from the ask next stuff"; (p) (screenshot: the Models notice "Ollama is not running ... then press Download.") "should \"Download\" be in an inline code block?"; (q) the owner's log 14:01 to 14:04: "frame 216ms on notes: documents.js SCRIPT[src=\"/vendor/codemirror/codemirror.min.js\"].onload 106ms (forced layout 42ms)", "frame 317ms on notes: 314ms before rendering with no script over 5ms in it", "raf 157ms on chat: graph-canvas.js gcRequestDraw 28 calls/s, 5.6ms each", "frame 277ms on dashboard: phone-shell.js BUTTON#tab-btn-dashboard.onclick 172ms (forced layout 82ms)"; (r) "also are you going to do an atlas-feminine design pass??" then "what about the general generated companions? or the customised ones?"; (s) "if the composer is unsure as to if the user is asking about their notes or intending to web search, should it ask and offer the two options as buttons to quickly select or to cancel and do smth else that the user writes or smth?? idk". Recommendation (taken): (o) both panels open in one place, below the toggle row and above Ask next, and the toggles read as disclosures (a chevron that turns, aria-expanded, the toggle recipe, not the chip look of Ask next), with a test; (p) no: code style is for code, paths and keys; a button named in copy stays plain text, capitalised as it reads; unchanged; (q) the codemirror onload layout read moved to the next frame, the graph redraw loop stops while the graph is hidden (28 calls/s on chat), the dashboard tab click's forced layout traced, each measured before and after; (r) yes: an Atlas feminine design pass (proportions, face, hair, dress, poses at 64 and 128 px, both themes), then the same pass rule for generated and customised companions (every generated look and every custom part judged at the same sizes, with a picture ratchet), after the throw freeze and the desk hang; (s) yes: when the router's notes and web scores are close, the answer slot shows one line "Your notes or the web?" with two buttons ("Search my notes", "Search the web") and the composer stays editable to type something else; no model needed, offline it offers notes only, with a test on the threshold. **Then, 14:15Z to 14:35Z, verbatim:** (t) "incognito mode for chat? that already exists right??" (answered: yes, Private chat); "private spaces as well?" (placed with 1695); (u) "can you also complete all of the small items in the backlog and plans?"; (v) "does the in-app companion have all the activities as well?? I want the desktop companion to be just as good as the in-app one and vice versa"; (w) (screenshot: the feminine desk Atlas on the taskbar) "atlas's right arm or the one on the left keeps going up and down, I think it is an animation cycle?? the tail is framed in that it isnt a smooth animation, the lwoer body doesnt change at all, also it periodically poofs and dissappears in stars but it never moves and juststays in the same place"; (x) "also the desktop companion's wave animation doesnt have the arm move so it looks liek a nazi salute :("; "selecting large as a size on the desktop companion did nothing"; (y) "also atlas as the desktop companion had a book out but it was still looking straight ahead and wast looking at the book at all and its arms wered changed, it didnt change body position it has no life, no biological movement, no realism"; (screenshot: reading, the brows down) "also why does it look so mad while its reading, id it like that the whole time?? maybe it can be reacting to what ito is reading idk. can it react to stuff on my page like if Im researching and it picks out key words or smth and reacts to it idk"; (z) (screenshots: the in-app and desk feminine Atlas side by side) "also are the feminine atlas deskto0p companion's arms more buff than the in-app companion??"; "the nebular flwo still doesnt change and the lowerbody doesnt have any organic naturalness to it, they just stay the exact same like they are frozen in time or the same frame". Recommendation (taken): (u) yes, after this PR's urgent items: a scout lists every plan and BACKLOG row sized small (one file, under an hour), then Sonnet agents take them in batches of five, one PR per batch; (v) one activity table for both (presence spells and in-app acts), each act drawn by both, with a parity test that fails when one has an act the other lacks; (w) the idle cycle's arm frames held one pose (the arm left up between frames), the tail's 24 frames step at 6 fps (raise to 12 fps with in-betweens), the lower body and the nebula stream get their own moving layers drawn per tick (offset and sway), not baked into the frame; the poof with no move is a portal that picked its own spot: a portal always arrives somewhere at least a third of a screen away, or is not taken; (x) the wave is a six-frame arm swing (built 2026-11-08), the size menu's Large is traced on Windows (the size reaches the runner and rebuilds the frames, with a log line); (y) a spell has its own frames: eyes down at the prop, arms holding it, body leaning, a page turn every few seconds and a face that follows a mood track (calm by default, a smile now and then), never the brows-down default; reacting to the page's words stays local and opt-in (window titles only, never content, a Settings switch off by default); (z) one arm drawing for both: the desk frames come from the live rig at device scale 2 and are solidified, which thickens soft edges; the solidify ramp is checked against the in-app arm width with a ratchet in px. **Then, 14:40Z to 15:10Z, verbatim:** (aa) (screenshots: the plant spell, the pot beside the figure; the figure partly under a translucent taskbar) "also coukld it be like it is holding the pot with the tail?? I also have a translucent taskbar. does it change based on if the taskbar is showing or not or if it is hidden or an app is being used that covers the taskbar or if the taskbar is docked on a different edge and stuff?? I still cant place it on top of a window or have it react to things on my screen :("; (bb) "the screen scrolls again when I throw the in-app companion (sometimes)"; (cc) (screenshot: a document with List, Numbered and Task buttons; a line "- Wizard covers: ..." shows a raw dash among rendered bullets) "can there be different types of dot points or numbered lists?? liek different styles?? what about other code mirror things??"; (dd) "also can the atlas companion have a lot and i mean A LOT more biological animation and frame and movement options and variation?? like with the tail, lower body, body position, transitions, movement, actions, behaviour, facial expressions and more??". Recommendation (taken): (aa) the plant spell holds the pot in the tail curl (a tail pose frame); the desk reads the work area, not the screen, on every display change (taskbar hidden, auto-hide, on any edge, a full-screen app covering it) and stands on the work area bottom, or the screen bottom when the taskbar is hidden or covered, with a FakeWin32 test per case; the window drop stays (b); (bb) reproduce with a seeded throw at several speeds and find which scroller moves (scrollTop logged per frame), fixed at the source with a test; (cc) yes: list styles per list (bullet: disc, circle, square, dash; numbered: 1., 1), a., i.) from the list button's menu, kept in the markdown (a marker style, not CSS only), and a line starting "- " after a wrapped item renders as a bullet (the raw dash is a bug); other CodeMirror features the docs editor lacks are listed by a scout against the CodeMirror extension list (fold, multiple cursors, bracket matching, search panel, autocomplete, lint gutter) and the useful ones become small rows; (dd) yes: an Opus design pass writes the Atlas variation catalogue (tail poses and loops, lower body sways, body positions, transitions between every pair, idle acts, reactions, a face set with blinks, glances and moods), one table both the in-app and the desk draw from, then Sonnet builders take it in batches with a seeded-hour variety ratchet (no pose held over its budget, at least N distinct acts an hour). **Then, 15:15Z to 15:30Z, verbatim:** (ee) "make the companion a lot more smooth, did you add that energy and behaviour mechanisms and choice thing to the companion>?" (answered: yes, needs, mood and a utility choice on the desk, energy, curiosity and sociability in-app; the stiffness is the frames, taken by deskframes-1108 and (dd)); "keep going please, keep pushing, triage effectively, high impact changes and make sure you have missed nothing"; (ff) "did you do the same thing wiht the feminine atlas as with the masculine one?"; (gg) (screenshot: the masculine Atlas head, a pale semicircular arc over the crown between the ears) "that semicircular arc or curve on the top of masculine atlas's head looks like female hair or a tiara idk". Recommendation (taken): (ff) no: atlasm-1108 was his pass (the shoulder join fix covers both); her pass is (r), next when an agent slot frees, on the same measures (proportions, face, brows and lids carrying moods, at 64 and 128 px, both themes); (gg) the crown arc on his head is cut or reshaped into a short swept fringe that reads as his, judged at 64 and 128 px against hers, in the same pass. **Then, 15:35Z to 15:50Z:** (hh) "also why does the desktop companion have liek a white paste around its mouth someitmes" (screenshots: the feminine desk Atlas, a pale blotch around and under the mouth in several frames; one sitting with a pencil and paper, the brows down); (ii) "its arms arent evben moving the pencil, its eyws arent looking at the activity, , its tail and lower body could change position and stuff to acommodate the new position or activity"; (jj) the owner's log 14:51 to 14:53: "input 376ms on dashboard: pointerout on span.ph-text in #lock-submit", "frame 275ms on dashboard: notes-list.js Response.json.then 106ms [apiJson /entries/most-accessed from dashboard.js, /chat/recent from dashboard.js]", "input 832ms on dashboard: pointerout on button.quick-link.quick-action in #dash-quicklinks", "frame 1030ms on dashboard: animation loops (top: avatars.js nameMarkBuddyKeepUp) 8ms", "frame 263ms on dashboard: companion-menu.js TimerHandler:setTimeout 19ms; animation loops (top: atlas-motion.js atlasRigFrame) 13ms". Recommendation (taken): (hh) sent to deskframes-1108 (it is re-rendering every frame): find the mouth patch (the solidify ramp or a gloss layer at device scale 2), fix it, ratchet the mouth region; (ii) with (y): every spell gets its own frame set, rendered from the in-app act (eyes on the prop, the hand moving the pencil over 4 to 6 frames, a lean, the tail and lower body curled into a seat pose), a desk spell agent after deskframes-1108 lands, checked frame by frame; **Built 2026-11-08 (merge a079e26c):** (jj, chatspasm leftover) the tempo look waits for a drawn frame and pauses while a reply streams (forced style 108 to 193 ms to 0), and the mood hand-over waits out a moving pointer (pointerout max 320 to 464 ms down to 232 to 344); the 1030 ms frame and (q) the CodeMirror and tab-click rows were not reproduced at 4x, leads in `lagjj-1108.md` (git history). Measured since (`animrecalc-1108.md` (git history)): every Atlas loop is composited; the cost is each main frame restyling 69 to 79 running animations (13 to 20 ms a recalc). Decision taken (recommendation, the emblem precedent): the planet loops pause at `:root.is-idle` like the emblem. Built on agent/animrecalc-1108 (46ede45a) and not merged: 57 of 79 loops held, recalcs 11.7 to 10.5 a second and ms 182 to 204, within noise, so a change to the look with no measured gain stays out; the cost is the 22 body loops and the wake frames, which change the look at rest. (jj) the pointerout lags are the lag1696 builder's (now three targets: #dash-grid, #settings-nav, #dash-quicklinks and the lock button, so one delegated handler); the 1030 ms frame and the dashboard's two fetches are carried by L-ui-modernisation-54. (bb) not reproduced: 48 flicks in 8 directions at 2 speeds and slow carries held at all four edges left every scroller still (the throwscroll sweeps, removed once the grab fix landed); one earlier pass saw #tab-dashboard scroll 0 to 659 px in growing steps with no script scroll call, on the first dashboard visit after sign-in (not anchoring: it started at 0; the steps grow like the browser's selection autoscroll, so the likely cause is a press that just missed a moving companion and dragged a page selection instead); next: a grab slop of a few px around the drawn companion while it moves, and the sweep repeated with a walking companion. Measured 2026-11-08 (`scratchpad/ui-sweeps/buddyhit1696.js`): Atlas sitting is drawn 19 px left, 26 px right and 47 px below its 64 by 92 handle, and 482 of 702 points on the drawing let a press through to the page (the sit and stand handles end at the seat and soles by design, so a button under it stays usable). A press on the drawn tail or nebula is therefore a press on the page, and a pull from there is a text selection that autoscrolls: the lead. Fix (taken): a press on the drawing outside the handle that becomes a pull (4 px) is taken as a grab of the companion and starts no selection; a plain click still goes through to what is under it; a seeded test presses each drawn region and pulls. (kk) 15:55Z: "also the desktop companion doesnt have as many subtle interactions like shaking it makes it turn upside down or flail and get dizzy, the in-app companion cna be better. they need soo much more depth". Recommendation (taken): with (v) and (dd): the parity table lists every interaction (shake to dizzy, upside down, flail, pet, poke, tickle, drop, catch, hold still, fling into a wall, carry over things) beside every act, the desk gains each one the in-app has (shake read from the drag's reversals on the runner, dizzy stars and a wobble frame set), and the design catalogue (dd) adds new interactions for both. (cc) the raw dash, not reproduced: 15 placements of a "- " line (after a wrapped, lazy, numbered, task, nested, tab, quote, fence, heading or bold line) all drew a bullet with the caret elsewhere (`scratchpad/ui-sweeps/listdash1696.js`); a raw dash shows on the caret's own line by design, so the likely causes are the caret or a pasted look-alike dash (U+2010 to U+2014, "•"), which is not markdown; next: the list styles build turns a pasted look-alike marker into "- " on paste. **Built 2026-11-08 (merge 2b26c508):** (gg) his crest a short swept cut; (r, ff) her light-page and brow pass and three generated parts (unicorn, headband, dress), rows 4 to 12 left in `atlasf1696-1108c.md` (git history); (s) Your notes or the web? with two buttons; (bb) a pull from the drawing is a grab (0 of 17 pulls grabbed before, 14 of 14 after; touch pulls left); (cc) list styles, menus and the paste fix, left in `ui1696c-1108c.md` (git history). **Built 76b77b1 (checked 2026-11-09 by uib1):** (c) the changed-row bar sits 8 px from the text on every row (tests/test_settings_row_bar.py); (d) note titles in link lists drop Markdown marks (tests/test_note_title_plain_1696.py); (e) a picked sidebar row keeps a row of room via `nearestScrollParent.reveal` (tests/test_row_room_1696.py); (g) an empty press, outside the picture or Escape lets go of the pick in every diagram kind (tests/test_diagram_let_go_1696.py); the tests of these files and test_ui_recipes.py pass (302). Not run in a browser at 1440 and 390 px. **Built 2026-11-09 (l, n, o):** (l) the 7.5 s was `spotNow` re-reading 149 to 299 boxes behind a whole-page layout (the throw landing, fixed earlier; test_companion_edges_kept_1696.py): Settings open then an immediate layout read is now 74 to 79 ms and 0 ms after close at 4x CPU, 8,751 elements; (n) a Tray note joins the notes the draft is written from, test_writing_room_tray_1696.py (0fad02e); (o) the foot's chips carry the turning caret and both panels open under the chip row, above Ask next, test_answer_foot_disclosure_1696.py (637560a). desklane-1109 (checked, 2026-11-09):** (a) built f35ace0: the fall picture is one quarter transposed per angle, no rotate on the overlay thread, 0.3 ms median (tests/test_overlay_spin_1696.py); (b) built 76b77b1: a release over a top perches from a fresh scan with a drop log line, the rise is a blink or cloud and a hang lasts minutes (tests/test_overlay_release_1696.py, test_overlay_hang_rise_1696.py); (h) built 76b77b1: tests/test_desk_menu_keep_1696.py; (i) built 76b77b1 with bde9740, ebebc18, a1d6179: tests/test_overlay_wander_1696.py; (k) built 2229e7a: the top is offered with the windows option off and no window open, 2 of 2 cases from 1 of 2 (tests/test_overlay_hang_top_1696.py); (aa) work area and taskbar on each of four edges, hidden, auto-hide and a full-screen cover on FakeWin32 built 76b77b1 (tests/test_overlay_edges_1107.py, test_companion_taskbar_1107.py); the pot in the tail curl needs a tail-curl frame, not rendered; (kk) every interaction the app has is in the catalogue as built on both sides (shake and dizzy adadb95, poke, pet, rub, pat, tickle c68505d, flail, fling, drop); eight more (hold still, carry over, catch mid-air, tail pull, drag skid, toss up, pointer chase) are built on neither side. Not real Windows. Open: the pot in the tail curl (frames), kk's eight new interactions (design catalogue). **(j, v, dd) part built (life-1109, 42c6b44ed):** four catalogue reactions built on both sides (dusk stretch, morning hello, typing rest nod, back from a full-screen app), entries built on neither 86 to 82, the parity test now reads the in-app rows a lazy file adds; media playing and (w)'s per-tick lower body stay open (life-1109.md ranked list). **Progress (wisp-1109, a1683 a / 1696 w):** measured first, the desk's lower body was already a per-tick flow warp that is never identical for 2 s at rest (seeded sit, 20 s: 457 to 482 changed hem pixels a tick, 100 percent of ticks, hem centroid span 1.1 to 1.3 px; walk 450 to 650 a tick); what was missing is that it ignored the breath (hem rise against the swell r 0.0 to 0.24). Now (an act in place, 20 s, seeds 1 to 3) 1124 to 1270 changed hem pixels a tick and a centroid span of 1.6 to 1.7 px, ticks 42 to 48 against 50 to 53 before (no wake added); the hem lifts a beat after the chest with each strand later than the last (`FLOW_BREATH` 1.5 px, same flow view and same wakes, rest wake bar unchanged); the stop's lag, overshoot and settle are pinned (-5.0 px leant, +2.5 px overshoot, settled in 3 s). Real Windows unverified; amplitude is held under the 4 degree join, so say if it still reads too still. Desk half w15-1111: (a) the periodic reads no longer share a tick with a fall (3.0 reads per flight to 0.0, 4bc274f96) and a slow tick is logged, so the next Windows log decides what is left; (b) the perch scan at release is built (w15-1110), the window-scan cause on the owner's machine waits on the next Windows log (B66, carried by L-ui-modernisation-56); (c) to (g) belong to the in-app half.
1719. **Owner, 2026-11-09 ~14:45Z, verbatim:** "If I throw the companion up hard is it possible for it to keep flying up and eventually fall down based on how hard the throw was?? can the in-app and desktop companion have more life and biological design to them? what about the composer, are there any more issues or lacking understanding with it?? there are still some response issues with responses. also keep optimising and working through all the deep dive audit and fable findings, finish all the stuff in the plans as well and anything in the inbox or handover and anything found while youre working" Found: a hard upward throw today either takes hold of the ceiling (`_ceiling_holds`, engine.py:3505) or bounces off it; it never leaves the screen. Recommendation (taken): (a) both companions: a throw past a speed line leaves through the top (a ceiling with no open side above), stays out of view for a time that grows with the throw's speed (ballistic: rise time v/g, capped), then falls back in from the top near where it left with a flail and a landing by outcome; the ceiling hang stays for a hard throw that is not past the line; measured by a seeded sweep of throw speeds (time away against speed, monotonic) on the desk (FakeWin32) and in the app; (b) more life and biological design on both: a design pass (judge rung) over breathing, weight shift, micro-saccades, blinks by mood, ear and tail follow-through, secondary motion of the wisps from body acceleration, fatigue over the day, then Sonnet batches, each measured (pose variety per minute, no frozen part over 2 s at rest); (c) composer: a new deep-audit round on the composer (answer shapes, English, understanding, ranking), its findings built in batches; the owner is asked for examples of the remaining "response issues" in the next summary; (d) standing scope confirmed: audits, Fable findings, plans, INBOX, HANDOVER, anything found, up to the BACKLOG. Desk half w15-1111: (a) re-measured on the seeded sweep: time away grows monotonically with throw speed, 2500 to 3200 px/s gives 1.01 to 8.0 s away, below the line it hangs or bounces; (b) and (c) are the design pass and the composer round, open.
   - (b) progress, life2-1109: seed fix, vertical follow-through, startle exhale, in-app eye steps, stand lean drift and floater breath built on both sides where listed; see `life-1109.md` (git history) "life2-1109" for numbers and what is left.
   (a) built in throwtop-1109, see CHANGELOG: desk 1.0 to 8.0 s away (seeded sweep, float and walk, 5 speeds: 1.01, 2.70, 4.61, 6.30, 8.00 s), in-app about 0.6 to 4.6 s fully above the top (drag caps it). Not real Windows.
   **(b) part built (life-1109, 42c6b44ed):** the design pass is `life-1109.md` (git history) (15 checklist rows, in-app and desk); blinks by mood and tiredness on the desk (seeded: sleepy 23.9 a minute for 0.63 s, curious 12.6, startled 12.1, happy 16.5 for 0.28 s; all were 16.5 for 0.28 s) and breath by exertion and mood on both (desk sit after a walk 1.5x quicker, eased within a minute; in-app playback rate 1.5 on a walk, under 1.05 in 50 s; both were fixed), one `vitals` table in companion-catalogue.json. Remains: the ranked list in life-1109.md (vertical follow-through, settle after a startle, micro-saccades, the stand loop's drift, media).
1721. **Owner, 2026-11-10 ~09:50 local, real Windows, verbatim:** "when I pat the desktop companion when it is hanging it doesnt react. also I still dont see really any biological movement or positioning or subtle animation or anything that looks realistic or any changes for the lower body whisp on atlas and the purple ribbon nebular flow that surrounds it. also I dont see the desktop companion doing many activities, it just stands there or teleports occasionally or switches the direction it is facing, also when I is in the bottom corner, it tends to just stay there and periodically vanish and reappear in the exact same spot. also it doesnt hang from the exact top of browser tabs". Log: "standable top edges 0, worth the trip 0, hang spots 1" with a maximised browser; drops onto Shell_TrayWnd counted as tool window; typing_burst unanswered while hanging. In-app lag: avatars.js ondblclick 127 ms (forced layout 104 ms), nameMarkBuddyTempo forced layout 25 ms, an avatars.js setTimeout 190 ms (forced layout 133 ms). Screenshots: hanging about 30 px below the tab strip top; resting at the taskbar corner. Placed: (a) pat while hanging, (b) hang height on browser tabs, (c) corner loop with no standable tops, lag in avatars.js: agents deskfix-1110 and lagav-1110; (d) activity variety and (e) visible lower-body and ribbon motion: an Opus design pass next. Desk half w15-1111: (a) to (c) are built and measured (test_overlay_deskfix_1110); the vanish-and-reappear loop in the corner is tracked as B66, and every away/back flip of the app window now logs its source and interval (5dceb54f8); the next Windows log decides it. (d) and (e) stay with the Opus design pass.
1712. **Owner, 2026-11-09 (screenshot under a chat answer: six numbered rows, "1 Why did the student eat his homework? Because the...", "2 something lol something -> found it during school a...", "3 Leafeon Pokemon image test WallpaperEngineOverri..." with a picture, "4 Girl with bell ..." with a picture, "5 Gary The Moss Monster :D ..." with a sketch, "6 What my notes currently leave out, however, is the c..."; the rows with a picture run about 300 px further right than the others; then Next: "What else do my notes say about university?", "Open ...")):** "why do some of these extend so far to the right??". Not yet traced: `.chat-sources-grid` (02-chat-graph.css:4381) gives equal columns, so the rows drawn may be another list (answer-kit.js); measure the live DOM first. **Not reproduced (uifix-1109, 2026-11-09).** Measured with 6 notes holding wide pictures (attached and embedded, 1600x900 and 6000x1200) among plain ones, 1100 to 1920 px: the Chat tab's Sources grid draws equal cards (550 px at 1100, 393 px two-up at 1440, 274 px four-up at 1920), the popup agent's Sources list (`cmdSourceRow`, numbered 1 to 6, then Show N more) equal 399 px rows, the Ask tab's records equal 530 px; none draws a picture in a numbered row, so the owner's list is still unfound. Next: ask for the window width and whether it was the popup agent, the Chat tab or the Ask tab. Composer spoke 2026-11-11: no composer or engine cause (the rows are the Sources grid, a frontend layout); still needs the window width and the tab from the owner to reproduce.


### Decisions made: Q34, the desktop pet outside the window (owner go, LEDGER.md:24, 2026-11-11)

- **The pet is the desktop companion already built** (BACKLOG 16, INBOX 1464 onwards; `core/desk_companion.py`, `core/overlay`, `frontend/desktop-companion.html`): a small frameless on-top window served by the app on 127.0.0.1 and drawn by the app's own avatar files, with the see-through native figure on Windows and X11. No second app and no `/pet` page: a second page would layer over this one. It already does what Q34 names: click for Quick note (new note), Quick search (quick open; Enter opens the first match in the app), New reminder, Open today and Open Tessellate; a due reminder arrives as a card to click; drag; Hide for 10 minutes (kept, decided in 1670) and Turn off. No act without the person: every note or reminder is one they write and save, and the companion never files, edits or deletes on its own (the consent order of 2026-11-10). Launch: Settings, Appearance, "Show the companion on the desktop" (off by default) or the tray menu; a browser tab says in one line that it needs the desktop app. Reach: Windows first (built, checked on the owner's machine); Linux X11 built and checked on FakeX11 only; Wayland stays in the app; macOS gets the card window, unverified (no Mac). Privacy: local only, the page calls only the app's own routes with the app's token, no outbound host. Measured 2026-11-11 (fake pywebview host, set_size resizes the page): the overlay panel fits at device scale 1 and 2 (menu 248x252, note 320x340, search 340x219, context 248x195, inner scroll 0); the card window's menu scrolled 95 px and its context 24 px in the fixed 248x312 and 248x268, now measured to fit (tests/test_desk_card_fit_q34.py). Only a real desktop can check on-top, transparency, taskbar and DPI placement.
