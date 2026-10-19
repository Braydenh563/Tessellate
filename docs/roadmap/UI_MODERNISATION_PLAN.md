# UI modernisation: the dev plan for the next session

> Companions: [ROADMAP.md](../ROADMAP.md) (live list: this plan is its top
> priority) · [HANDOVER.md](HANDOVER.md) (what the last session measured and
> left) · [../DESIGN.md](../DESIGN.md) (the rules this plan extends) ·
> [BACKLOG.md](BACKLOG.md) · [HISTORY.md](HISTORY.md) · [ANALYSIS.md](ANALYSIS.md)

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
`archive/agent-remaining/help-popovers.md` on 2026-09-14 (INBOX 220) so they
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
   on this list, and was left open deliberately in an earlier pass rather
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
   rather than a same-session, same-commit add. Left inline; `countjs.py`
   will keep reporting TOTAL 2 until a future pass does that properly.

## Phases 0 to 6: built

Moved whole to HISTORY.md ("Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: UI_MODERNISATION_PLAN)"): a plan holds open work only.

## Verification, every phase

- Sweep tables before/after in the commit message.
- Screenshots, light and dark, both widths, looked at *and* measured (pixel
  samples for any colour claim, `scrollHeight` for any clipping claim).
- `python -m pytest tests/` green; `ruff`; `node --check`.
- The four traps in CLAUDE.md still apply: stale server, stale `app.js`, a
  screenshot is not a measurement, "already exists" is where triage starts.

## Phase 7: the reports from the v0.2.2 round that are still open

Each one was triaged against the running app this session; these are the ones
that need building rather than fixing.

1. **The lightbox is an image viewer showing a document.** Reported: "the
   lightbox needs improving for file and pdf previews, no sections or info are
   below it really compared to the images." An image gets caption, read text,
   badges and usage under it; a PDF gets the page and nothing else. It should
   carry the same block, plus what only a document has: page count, which pages
   have been read, and a way into the OCR Workspace at that page.
2. ~~**Line numbers as a setting, in all three editors.**~~ **Built** (HISTORY.md, "Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: UI_MODERNISATION_PLAN)"; `mountGutterFor`, `docGutterWanted` in documents.js).
3. **Captioning for documents, not just photographs.** Reported: "image
   captioning, how it is done and displayed needs to be refined for pdf
   documents and other similar documents. with graphs, images and diagrams in
   them." A page of slides is not a photograph: the caption prompt, and where
   the answer is shown, both assume one image with one subject. Needs a
   per-page, per-figure model and a place to show it that is not a single line
   under a thumbnail.
4. **Region select → read just that.** Asked as a question, and it is a good
   one: "can there be a way for the user to manually outline and single out
   regions on a pdf or similar document and then the ai will read what is in
   those regions?? like maybe the user can outline a graph or diagram on a pdf
   slide and then the user cna get the image or ocr model to analyse and caption
   that thing." The workspace already draws region boxes from Tesseract and
   already has a page raster; this is a drag-to-draw on that layer, a crop, and
   the existing read/caption call on the crop. Scoped small, high value.
5. **The Files sub-tab has to show more than a row can hold.** OCR text for a
   long document does not fit where a photo's caption fits; the row needs a
   summary plus a way to open the reading, not a clamped paragraph.
6. **The agent activity panel**, see
   [AGENT_SKILLS_REFORM.md](AGENT_SKILLS_REFORM.md) Phase C, which owns it.

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

### The work, surface by surface

Each is one commit, before/after inventory in the message, driven in
Chromium at 1440 / 1024 / 820 / 390.

1. **The lint first.** `tests/test_dock_grammar.py`: statically, for every
   element marked `data-dock`, at most one `.primary`/filled button, no
   `input[type=checkbox]` outside a popover, no text-only segmented control,
   and the utilities in order. `scratchpad/ui-sweeps/docks.js` becomes the
   runtime sweep: controls per row, heights per row, zone order.
2. **Graph** (worst first): title + count; search; `Layout ▾` and
   `Colour ▾` as one `View ▾` popover holding both segments and the
   options; saved views as one select with save/delete inside it; `Refresh`,
   `Export` into `⋯`; one primary (`New note`); `Concept maps` becomes a
   link in the identity zone. 28 → ≤ 9 visible.
3. **Library** (All and every sub-tab, one recipe): title; search; `Filter
   ▾` (semantic, include bin, kind); one sort select; one view segment;
   `＋ Create`; refresh; help. The chip row stays *below* as the visible
   filter. The duplicate segmented sort goes. Sub-tabs (Documents, Boards,
   Images, Files, Links, Contents, Skills) take the identical zones with
   their own words.
4. **Notes**: the toolbar from Phase 5 already has search-first and a
   filters sheet at ≤ 600; apply the sheet at every width as `Filter ▾`, one
   sort select, the view segment, `Select` into `⋯`.
5. **Whiteboard**: identity (back · board select · rename) left; search;
   the five menus stay (they are verbs used sometimes) but at one height
   and one gap; minimap, Library, fullscreen as utilities right; the map
   controls (chip, layout, Tidy) as the context chip and a `Layout ▾`.
6. **Documents**: DOCUMENTS_PLAN.md Phase 1 owns the editor's own chrome;
   the *Documents list* dock follows item 3.
7. **Timeline, Reminders, Chat, Dashboard**: Timeline onto the grammar
   (View segment with icons, `Options ▾`, search, Today as the primary);
   Reminders' three rows of ghost buttons become one row (the magic field)
   plus one `Presets ▾` popover, with the due chips as the visible filter;
   Chat's toolbar at the dock height with `New chat` as the one filled
   control; the Dashboard hero's clock and greeting as identity, its two
   quick actions as primary + ghost.
8. **Settings sections** already have one form recipe (Phase 5.1); their
   heads take the grammar's identity zone only.

Acceptance: `docks.js` reports **one height per dock**, zone order correct
on every tab and sub-tab, ≤ 7 visible controls per row, exactly one filled
control per dock; `test_dock_grammar.py` green; `errors.js` 0 findings at
all four widths; a keyboard-only pass (Tab into each dock, arrows across
it, Enter opens a popover, Escape closes it and returns focus) scripted in
`scratchpad/ui-sweeps/keys.js`.

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

## Phase 11: the phone, done properly (1 to 2 sessions, next session or later)

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
   - **The rail is gone below 600: built** (2026-09-20, with item 3's
     sidebar half). Measured first (`scratchpad/ui-sweeps/phonesidebar.js`):
     at 390 the Notes list started at x=82 (13px gutter, the 52px sidebar
     rail, 16px card padding) for one 44px toggle at the top of the strip
     and nothing else down it, so rows ran 262px in 390. Now every sidebar
     (`SIDEBAR_IDS`) parks fully off screen below 600, the page beside it
     pads 0, and it opens from a `.dock-nav` button at the leading edge of
     its own dock's head (`mountPhoneSidebarOpeners`), pressing the
     sidebar's own toggle so the sheet logic stays in one place. After, on
     Notes, Chat and Documents at 390: closed sidebar right edge 0, page
     padding 0, opener 44x44 first in the dock, the sheet opens at x=0 with
     its closer showing and Escape closes it; at 768 the tablet keeps its
     52px rail and the opener is hidden.
   - **Filters in a sheet: already the fold** (measured 2026-09-20). Below
     1100 `foldDockArrange` moves every dock's arrange zone (sort, view,
     page size) into its own `...` menu, so at 390 the notes dock shows
     search, Filter, Select, refresh, help and the menu, and nothing else.
     What was wrong was the rows: the opener took a row of its own (the
     identity zone's phone basis is 100%), and the search input could not
     shrink (`min-width: min-content` below 1100) so Filter wrapped under
     it. Fixed in the 600 band: the opener shares the title's row, the
     input gives, a dock with an opener and no find zone (Chat) wraps its
     actions under the title. Dock heights at 390, before and after: notes
     250 to 166 (three rows), chat 166 to 114 (two), timeline 198 to 146,
     graph 143, library 146 and reminders 94 unchanged.
   - **The floating +: built** (2026-09-20). The Notes dock never had a
     primary (Capture is a sub-tab), so it has one now: "New note", filled,
     at the right before the utilities, which the grammar asked for and the
     desktop dock measures at seven controls with one filled (`docks.js`).
     Below 600 `FAB_IDS` floats it as the + above the tab bar, where it
     opens Capture with the caret in the box and hides while Capture is
     showing. **Decision:** the Capture sub-tab is the sheet. On a phone
     the sub-tab is already a full-height page holding nothing but the
     box; a sheet over it would be a second capture surface, so the + opens
     the sub-tab. Found on the way and fixed at the source: the first
     showing of Capture wraps the box for its gutter and then upgrades it
     to the live editor, and both moves dropped the focus a person had just
     asked for (measured: focus in at 7598ms, gone at 7737, nothing active
     at 1200ms after the press); each now carries it over. Measured after
     (`phonecapture.js`): the + is 44px at bottom right above the tab bar,
     one press lands the caret in the live editor, the + is gone while
     Capture shows, and at 1024 the button is back in the dock, filled.
   - **Swipe actions: built** (2026-09-20). Right favourites, left bins,
     each the row's own control (`.favourite-btn`; `binNoteWithUndo`, the
     function the row menu's "Move to bin" calls, undo toast and all), never
     a second copy. Measured with real touch events through CDP
     (`scratchpad/ui-sweeps/phoneswipe.js`): a 40px swipe reveals 40px of
     underlay, does not arm and settles to 0; 110px right arms and the note
     is a favourite; a 6x80 vertical drag never moves the row; 110px left
     arms and the note is in the bin with the undo toast up. No page
     errors; `phone.js` 0 findings.
   - **The note page: built** (2026-09-20), and item 2 is complete. A tap on
     a row (not on a control, not the lift-off of a swipe) opens the note as
     the sheet recipe's `page` variant: the whole screen, a back chevron,
     the list's own card unclamped inside, and that card's own actions
     moved into a `.thumb-bar` at the foot, so nothing is rendered twice
     and the page's actions are the row's. Bin or Archive from the page
     reloads the list and the page closes when its note is gone. Measured
     (`scratchpad/ui-sweeps/phonenotepage.js`): the page is 0 to 844 with
     a 0px radius, a note clamped to 198px in the list is 1440px on the
     page in a scrolling list, the bar holds 4 buttons at 44px with its
     bottom at 844, the close is labelled Back with the chevron, Escape and
     the chevron both return focus to the row, a tap on the row's star
     opens nothing, and a tap at 1024 opens nothing. Found by `phone.js`
     on the way: "Show more" under a clamped note was 80x22 at 390; it
     takes the row's floor now.
3. **Chat: built** (2026-09-20). Moved to HISTORY.md ("Moved from the plans, 2026-10-10 (Brief 72b)").
4. **Graph: built** (2026-09-20). Moved to HISTORY.md, the same section.
5. **Library and Files: built** (2026-09-20). Two-up cards, the reader
   full-screen with a bottom bar; upload from the share sheet.
   - **Two-up cards: decided the other way, not remade.** The 600 band in
     07-whiteboard-misc.css makes the card grids one full-width column
     with the measurement that decided it (at 390 the masonry gave two
     164px columns, a card too narrow for its own title, and a reading
     order that went down, up, down). Measured 2026-09-20: 24 Library
     cards in one column at 390. Stands.
   - **The share sheet: built** (2026-09-20). The installed app is a Web
     Share Target (`manifest.webmanifest`, the GET form: no service worker,
     and the query survives the lock screen). A page, a link or a
     selection shared to Tessellate opens it at `/` with `share_title`,
     `share_text` and `share_url`; once the entries have loaded
     (`takeSharedIntake`, a boot step) the three become one capture (the
     title as a heading, the text, the link on its own line), Capture
     opens with the caret in the box, and the query is cleared so a
     reload shares nothing twice. `tests/test_share_target.py` holds the
     two halves to the same three names; measured by
     `scratchpad/ui-sweeps/phoneshare.js` at 390. Not built: a file (an
     image from the camera roll) needs the POST form and a service
     worker.
   - **The reader full screen with a bottom bar: built** (2026-09-20), and
     item 5 is complete. Measured at 390x844 first
     (`scratchpad/ui-sweeps/libreader.js`, this item's gate): the reader (the
     OCR workspace) was a 342x776 card inset 24px from each edge with a 14px
     rounded top, its way out an X; the Regions checkbox label was 36px tall,
     a zoom segment button 35px wide, the two rail tabs 13x25 and the find
     box 343x20. **And a bug older than the phone band**: the three panes are
     a grid of two columns below 1100 with three children in it, so the
     reading pane fell into an implicit second row. At 390 the 1fr column
     collapsed and the transcription was **0px wide**; at 1024 the hidden
     rail's own column still took **593px** of empty space while the page was
     squeezed into the 320px column beside it and the reading dropped to a row
     underneath. Hiding `.ocr-rail` was never enough: the column goes too, and
     the selector needed `.ocr-panes > .ocr-rail-column` because the column's
     own `display: flex` is declared below that band in the same stylesheet.
     After, at 1024: page 593x656 and reading 320x656, side by side; at 1440
     the three columns are 144 / 747 / 416, unchanged.
     On a phone the reader is the sheet recipe's `page` variant, the same two
     classes `openSheet` puts on the note page, stamped by `ocrPhonePage` in
     app.js because `tests/test_ui_recipes.py` holds that only the recipe's own
     file may write a variant class (it caught the first attempt, from
     library.js). The reading's five actions move into a `.thumb-bar` and move
     back above 600, the way the note page moves a row's actions: same buttons,
     same ids, same handlers. Measured after at 390: the card is 0,0 to
     390x844 with a 0px radius, one column of panes, the rail column 0, no
     control under 44px, the bar holding 5 buttons with its bottom at 844, the
     way out labelled Back with the chevron, Escape closes it, and crossing to
     1024 with it open puts the five actions back in the reading's own foot
     and the X back in the head.
6. **Documents: built** (2026-09-20), most of it already there and
   measured before anything was added. Measured at 390 with a fresh
   document (`scratchpad/ui-sweeps/phonedocs.js`): a phone now opens a
   document in the Rendered view when nothing is stored (Live Preview
   above 600, a stored choice wins at every width); Edit is the page
   itself with the live editor, the formatting strip hidden and the
   selection bar (`#doc-phone-bar`, seven 44px buttons) at the foot above
   the keyboard edge; the outline is the Outline tab of the sidebar sheet,
   opened from the head's opener (item 2's), with all seven headings.
   **Decision:** Edit is the page, not a sheet over it; on a phone the
   document is already the whole screen and a sheet over a page that is
   itself the editor would be two editors. At 1024 the default is Live
   Preview as before.
7. **Whiteboard and maps: built** (2026-09-20), and one third of it was
   already there. Measured at 390x844 on a fresh board first
   (`scratchpad/ui-sweeps/wbphone.js`, this item's gate). Before: a pinch
   with the default Select tool scaled the board by exactly **1.000**,
   because `wbZoomFilter` gave touch to the camera only while the Pan tool
   was held, so a phone could not move or zoom a board without first going
   to find that tool; the tool rail was a 364x56 band under a 364x604
   canvas holding **835px of tools scrolled through a 358px window**, so 16
   of its 31 buttons were on screen and the Shapes section showed one of
   its seven; and the board's own top bar was 88px of two rows with all
   **eleven** of its controls at 36px against this band's 44px floor. The
   mind map's + handles were **already 44x44** and already shown on a
   selected node, so that third of the item is a measurement rather than a
   change.

   After: two fingers are always the camera and one finger still belongs to
   the tool (the same split Figma, Excalidraw and Procreate use, and no tool
   here is drawn with two), measured at 1.000 to 3.500 for the same pinch
   with Select in hand. The rail below 600 is one button saying which tool
   is in hand, and it opens the sheet recipe holding `#wb-tool-group`
   itself, moved in and put back on close, so a tool added to the rail is in
   the sheet with no second edit: 390x527, 12 visible tools, none under
   44px, and picking one closes the sheet and selects it. The top bar takes
   the band's floor, 88px to 104px, which is one step of height for eleven
   targets that can be hit. Whiteboard.js's three hand-rolled 500ms holds
   are `wireLongPress` now, so they inherit the swallowed lift that item 4
   added and whiteboard.js joins the long-press lint's file list; the fourth
   right-click, bound through d3 on a selection that is rebound every
   render, keeps its own hold, and the lint's docstring says why.
   **The bar at 820, and the band between: measured and fixed** (2026-09-20,
   `scratchpad/ui-sweeps/wbtopbar820.js`, on an open board). Two things this
   item left behind. First, from 600 to 819 the band's own rule reads "below
   820 the pointer is a finger" (`--target-min` is 2.75rem on `:root` there),
   and all thirteen of the bar's controls were still **36px tall** at 768,
   because the rule this item wrote lived in the 600 band and the bar declares
   its own control height, which nothing in it read; the icon-only ones had
   taken the width and not the height, which is how it stayed invisible. It is
   in the 819.98 band now: at 768 the bar is 104px and two rows with every
   control at 44. Second, below 56rem the five menu toggles drop their words
   and rendered **25.8px wide**, the narrowest controls in the app and under
   the *global* 28px floor, so at 820 five of thirteen failed a floor that has
   nothing to do with touch. They take the floor from 600 up now (at 820, 28;
   at 768, 44).

   **At 820 itself the band's 44px floor is deliberately not introduced**, and
   that is band 2's existing decision rather than a new one: 10-responsive.css
   records why `--target-min` was redeclared on `#tab-bar` alone there and not
   on `:root` ("raising every dock control in the band to 44px is a real change
   with its own measurements to take"). Measured at 820x1180 after: the bar is
   784x46, one row, thirteen controls all 36px tall, nothing under 28, no
   sideways scroll; at 1440 it is unchanged at 1392x46. Found and not fixed,
   placed in WHITEBOARD_PLAN with its numbers: below 600 the bar runs 75px past
   its own right edge at 320 and 5px at 390, and the only fix that does not
   redesign it costs a row (152px at 390, 200px at 320), which is the
   phone-shaped board bar this item already assigned to that plan.

   **Decision: the board's top bar is not reduced to a kebab** the way the
   app header was (item 1). It is a menu bar, which the dock grammar already
   names as this surface's exception (Insert, Edit, Arrange, View, Board),
   and three of its eleven controls are those menus. Raising it to the touch
   floor is what this item needs; a phone-shaped board bar is
   WHITEBOARD_PLAN's, not this item's, and is named there.

   The whiteboard sweep at 390 had to learn the sheet: its ink-swatch check
   scrolled the rail sideways to find the swatch, and the swatch is in the
   sheet at that width now. It opens the sheet and closes it, and reads the
   swatch as red rather than as exactly `rgb(255, 0, 0)`, because inside the
   sheet the pixel is painted through the card's own glass (measured: 249,
   1, 3). 24/24 at 390 and 24/24 at 1440 after it; `wbcontextphone.js` 5/5,
   so the context bar work that landed this week is untouched.
8. **Settings, dashboard, timeline, reminders: built or decided**
   (2026-09-20). Measured at 390 first: the dashboard's 24 widgets are
   already one column. Settings already has its phone shape, decided and
   measured before this (07-whiteboard-misc.css: the section strip hidden,
   a jump select beside the search in one row, every section in one
   scroll; "2337px of scroll inside 308px at 390" is the number that
   chose it), so the page list with a back button is not remade. Built
   here: a phone opens the timeline as the table when no view is stored
   (`timelineViewMode`; a choice wins at every width; the table is 330px
   in 390 with no sideways scroll, and its column sorts take the 44px
   floor), and a reminder row swiped right is done, through its own Done
   checkbox, with nothing to the left (`initRowSwipe`, now one function
   for any list of rows, the underlay's words read from the row's own
   `data-swipe-right` and `data-swipe-left`). Measured by
   `scratchpad/ui-sweeps/phonereminders.js`.
9. **Touch: built** (2026-09-20). The 44px half is built (2026-09-13, the
   block is in HISTORY.md, "Moved from the plans, 2026-09-13"):
   `scratchpad/ui-sweeps/phone.js` walks every tab whole rather than dock by
   dock and reports 0 findings at 390x844 and 430x932. Long-press replacing
   right-click is items 4 and 7's `wireLongPress`, app-wide and lint-held.

   **No hover-only affordance: swept properly and two found**
   (`scratchpad/ui-sweeps/hoveronly.js`, this half's gate). It reads the app's
   own stylesheets for every rule whose selector carries `:hover` and whose
   body sets `opacity`, `visibility` or `display` (45 of the 243 `:hover`
   rules), strikes the `:hover` out to get the element at rest, walks eleven
   stops across every tab with `hover: none`, `any-hover: none` and
   `pointer: coarse` emulated through CDP, and then **taps** each candidate
   for real, because a reveal on hover is only a fault when nothing a finger
   can do produces it. Three candidates; the AI dot's popup is fine (hidden
   at rest, revealed by a tap, `toggleAiStatusPopup`).

   The other two were the same bug, and it is worth writing down because it
   is invisible in review: **a `hover: none` override written at a lower
   specificity than the rule it overrides does nothing at all.** Both the
   Library card's ⋯ and the document row's ⋯ already had
   `@media (hover: none) { .library-card-menu { opacity: 1 } }`, written as
   the short name, against a base rule of `.menu-wrap.library-card-menu
   { opacity: 0 }` (compound, and deliberately so, for a positioning bug its
   own comment records). Measured: a 44x44 button at opacity 0 on every
   Library card and every document row at 390, still 0 after a real tap. Both
   overrides now match their base rule's specificity. After: 0 hover-only
   affordances at 320, 390 and 430, the AI popup the one candidate and it
   taps open.
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

    Still open: the screenshot set for the owner.

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
    The list, with ids, is `archive/agent-remaining/phone.md`.

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

- (Odysseus, fourth read 2026-10-10) 

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
- 5b, the calendar mode (decision 6): TIMELINE_PLAN section 9, Brief 55.
- 8, indent guides in the code editor: Brief 42 (DOCUMENTS 25 row 3); the active line is built.
- 7 on chat bubbles and library cards; 1's panel padding 12 and sidebar gutter 8, not yet measured.
- One focus ring at 1:1 (Chat, an `.active` button whose ring takes the ground's colour; `focusring.js`).

## Placed from INBOX, 2026-09-09 to 2026-10-03 (all built)

Built, each block in HISTORY.md: 100, 101 and 103 ("Moved from the plans, 2026-09-09"); 60, 102, 104 and 279 ("Moved from the plans, 2026-10-05 (UI_MODERNISATION_PLAN's built INBOX blocks)"); 94 ("Moved from the plans, 2026-10-05 (UI_MODERNISATION_PLAN 94 and 282, found built)").
The evening batch of 2026-09-09, and 164, 165, 186, 282, 296 and 393: all built and moved whole to HISTORY.md ("Moved from the plans, 2026-10-05", the UI_MODERNISATION_PLAN blocks; 296 under "INBOX resolved, 2026-09-21").

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
10. **Not done, left open:** the Tools and Appearance panes are still long
    (4,247px and 1,296px at desktop width) and are indexed rather than
    split. (The Installed models list is model cards now, and the
    background-job "duplicate" was two settings, the utility model and the
    autonomous pass's own override, whose default now names the model it
    falls back to: HISTORY.md, "Moved from the plans, 2026-10-05 (444
    decision 10: the installed models as model cards)".)

## Placed from INBOX, 2026-10-05 (OPEN.md triage)

- The Files rows' two rhythms: a measuring error, closed; HISTORY.md, "Moved
  from the plans, 2026-10-05 (UI_MODERNISATION_PLAN: the Files rows' two
  rhythms, a measuring error)".
- The picker's other four sources: built; HISTORY.md, "Moved from the plans,
  2026-10-05 (UI_MODERNISATION_PLAN: the attach picker's tiles)".

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

## Placed from INBOX, 2026-10-05 (header bars, Settings navigation)

621 and 622 are built. Moved whole to [`HISTORY.md`](HISTORY.md) ("Moved from the plans, 2026-10-05 (INBOX 621 and 622: the header bars and the Settings navigation)"), with what they measured before and after.

## Placed from the owner's list, 2026-10-10

- **INBOX 760, card dates.** The time floats mid-card on a card the grid stretched taller than its content (about 110px under it on the tallest card, 40px on short ones); "1 week ago· edited" has lost its space. Pin the details line to the card's bottom edge, measured on a row of unequal cards; the space restored. Carddate agent.
- **INBOX 761, mind maps listed as notes.** The Ask results show a mind map as an Uncategorised note card; check every reader of notes (Ask, Notes, search, graph, timeline, dashboard counts, Find anything, palette) and exclude what a board keeps behind its topics, with a test per reader. Mapnotes agent.
- **INBOX 762, "just now" on an untouched mind map.** The Library card's modified time moved without the owner; find what writes `updated_at` on a board when it is only opened, listed, indexed, searched or thumbnailed, stop it, and pin it with a test. Mapnotes agent.
- **INBOX 767, the no-model notice.** One row at 1440 (icon, one short sentence, the action as a link-styled button, the X at the end), wraps to two only under 600px; the five surfaces share it (`renderAiOfflineNotice`). Measured: notice height equals one line height plus padding at 1440; copy under 90 characters. Notice agent.

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
- "These elements in the lightbox aren’t the same height"
  Recommendation: give lightbox controls one height token and measure their heights in the sweep. No brief carries it; Brief 41 (density) is the nearest.

### Design requests

- "very messy"
  Recommendation: the owner has not named the surface; ask for the screen when the next session starts, and meanwhile run the Brief 41 density census to find the worst surface. No brief carries it by name.
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
| 2 | Grouping (proximity, common region) | related controls share a container; a dock folds past seven items; unrelated groups are two spacing steps apart | 347 dock classes; `test_dock_grammar` holds the grammar. Of 14 content docks at 1440, 6 show more than seven items: Notes 10, Graph 9, Library 9, Chat 8, Timeline 8, Boards 8 (Library docs and media 7); at 390 none does, because 4 to 21 rows per dock sit in the folded menu | desktop docks overflow by count while the phone folds by width; fold by count at 1440 as well |
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
| Graph | the options folds (three) | GRAPH decisions | `renderGraphSvg` 1,254 lines | folds are learnable | Brief 38 |
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
23. **The bar is a professionally designed product, and the references are named** (the owner, 2026-10-10, INBOX 755: "make the design on par and better than a modern professionaly designed web and app interface. research for inspiration and guidance if needed"). 13.R, before 13c: a reference read of six products the owner's users already know (a notes app, a task app, a browser, a code editor, a whiteboard, and the platform guidelines, Apple HIG and Material 3), one paragraph each in ANALYSIS.md naming the pattern taken and the measurement it sets (rest density, primary count, dialog shape, motion length, type ramp), never a screenshot copied. Every 13.2 row then cites the reference its target comes from. The vendored design skill is consulted and overruled where the references disagree (HANDOVER "Skills").

### 13.4 Phases with gates

| Phase | Builds | Gate | Brief |
| --- | --- | --- | --- |
| 13.0 Measure | visible controls and primaries per page at rest at 1440 and 390, the dialogs classified, the 13 unlabelled buttons plus the JS-built ones, `axe.js` and `contrast.js` per surface, the confirms counted, `hierarchy.js` written | 13.1 and 13.2 re-written with numbers; a list of every offence per decision | 56 (Sonnet, medium); measured 2026-10-10, numbers in 13.1 and 13.2, sweep `hierarchy.js` |
| 13a The stylesheet's grammar | open: decision 12's eight-step layer scale (115 literals ratcheted), 13's shadows to tokens (7 ratcheted left of 19; the 7 are one-offs: three role-colour glows, two scroll-edge fades, the lightbox, one reversed hairline; `agent-remaining/ui13a-1018.md`), 16's `!important` (117 ratcheted left of 128: the full-screen states are done; the rest are motion switches, print, the companion and overrides of script-set inline styles), the six `CIRCLES_LEFT` and 198 colour literals; 9, 10, 11, 14, 15 and 17 are built (HISTORY.md, "Moved from the plans, 2026-10-11 (UI_MODERNISATION 13a, Brief 57, the stylesheet's grammar)"; remaining list `archive/agent-remaining/grammar57-1011.md`) | every ratchet green; `contrast.js` and `errors.js` unchanged; no visual change except the hover and focus twins (measured by `getComputedStyle` on ten controls) | 57 (Opus, high) |
| 13b The stylesheet's structure | decisions 18 and 19: dissolve the consistency and responsive files into the components; remove the 236 unused selectors | the two ratchets; the sweeps unchanged; file count and line count recorded before and after | 58 (Opus, high) |
| 13.R The references | decision 23: six references read, the pattern and the number each sets, written into ANALYSIS.md and cited from 13.2 | every 13.2 row names its reference; no target without a number | 57 (Opus, high), first step |
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
- INBOX 796, bug, graph, the owner 2026-10-10 23:00Z, two screenshots: "dropdown menus in the graph dont close when another is opened causing a visual clash and overlay for all 3 of these buttons" (the ?, settings and ⋯ menus in the graph head open on top of each other.) Owner: graphfeel.
- INBOX 790 to 793 are built (canvasui-1010): see HISTORY.md, "Moved from the plans, 2026-10-11 (canvasui-1010)".

## Placed from INBOX, 2026-10-11 (the owner's sweep request)

Owners: the uisweep agent (Sonnet, measure and the mechanical fixes), then Briefs 57, 58 and 59 (Opus) on its findings, ahead of 61 to 63.

- INBOX 800, UI, the owner 2026-10-11 02:40Z, verbatim: "Can you do another devibecoding, ui/ux modernisation and professionalisation sweep across all ui faces??" Placed: every surface at 1440 and 390, both themes, through `devibe.js`, `vibecheck.js`, `hierarchy.js`, `consistency.js`, `hoverbox.js`, `focusring.js`, `contrast.js` and `axe.js`; the findings, each with its number, go to `archive/agent-remaining/uisweep-1011.md`; mechanical ones fixed in the sweep, design ones taken by Briefs 57 to 59 in that order.

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

Decisions made:
- V1. Transcription is a background run in the one ledger (transparency): closing the dialog never stops it; the Recordings row shows its progress; a notification says done or failed with Open; Stop sits on the row and in the running panel. A recording in progress survives the dialog too, as a shell pill with its timer, Pause and Stop.
- V2. Input: a device picker (every microphone the browser lists, remembered), noise suppression, echo cancellation and automatic gain as switches (the browser's own constraints), a live level meter and a 3-second mic test; in the dialog and in Settings, Voice.
- V3. Enhancement on save, local: a high-pass and loudness normalise pass on the kept audio, a switch, on by default; the original is kept until the transcript is accepted.
- V4. The level line draws the analyser's real signal and is measured to move; with reduced motion it is a static meter.
- V5. Live transcription: while recording, the captions pipeline writes the words into the dialog as they are spoken; the full pass replaces them after.
- V6. Live captions are reachable where a person looks: a Captions button in the voice note dialog and the Recordings bar, a row in the shell's tools menu, the palette, and a Guide topic "How do I get live captions".
- V7. The dialog redesigned from DESIGN recipes: name field, one large record control with the timer, the level line, the device chip, Pause, Stop and Discard; after saving, the transcript's first lines and Open.
- V8. The focus timer: a ring with the time large, presets as a segmented control plus a custom stepper, Start and Pause as one primary, a chime and a notification at the end, an optional break cycle, and today's focused minutes.

Rows (owner: voiceup, Opus, after libraryup): V1 to V8, each a commit with a test, measured at 1440 and 390, help moving with it (standing order 13).

## Placed from INBOX, 2026-10-11 (Tidy, undoing a pattern, menu gaps)

- INBOX 830, the owner 2026-10-11, verbatim (Tidy's "Category names" review, empty; Patterns rows with Confirm and Not right; "Recent runs (3)"): "this tidy panel is poorly designed and needs a ui/ux fix, redesign and/or restructure. also if I have confirmed a pattern then I cant undo it. also some dropdown menus across the app have wierd gaps at the start and end"

Decisions made:
- T1. Tidy is one list of reviews with counts; a review opens in place with a back link (not a bordered button beside a small title), its one-line description, and its rows. An empty review says so in one line with no selection bar: All, None and the disabled action show only when there are rows.
- T2. Recent runs is a quiet disclosure row (DESIGN "Row actions"), not a full-width bordered box.
- T3. A confirmed or rejected pattern keeps an Undo on its row and in "What it learned" (owner: learnaudit, with decision 68).
- T4. A menu's first and last items sit one menu padding from its edge, never a group label's or a separator's gap (owner: grammar57, with 813's one dropdown grammar).

Rows: T1 and T2 (owner: voiceup, with V7's dialog work); T3 learnaudit; T4 grammar57.

## Placed from INBOX, 2026-10-19 (mobile1314)

- INBOX 1314, the owner 2026-10-19, verbatim: "the mobile view needs a bit of redesign and layout/nav reworking because it is annoing to use and the bottom nav bar just doesnt make sense with how it works and is layed out and is annoying to use."
- Measured before (390x844 and 360x740, light and dark, a touch context; `phonemore.js`, `phonetabs.js`, `phonechrome.js`, `phone.js`): More drew as the bar's first column (x=0), not its last: `#tab-bar { order: 3 }`, two header-era rules in 02 and 05, still applied inside `#phone-tab-dock`. Columns Notes, Chat, Graph, Library and More, 78x57 at 390 and 72x57 at 360; Dashboard (home, one of Simple mode's four) behind More while Graph held a column. More's sheet: seven rows, three pages and four tools, undivided. Two buttons called More (the header's menu and the bar's). Pressing the tab you are on did nothing. A reminder's +1h was 39.6x44 (a coarse-pointer floor of 38px against the 44 decision); at 360 the timeline's seven days were 41.8px and its head 322px in a 300px card. No sideways scroll on any tab; every page ends at the bar's top (786/786) and every last control scrolls clear of it.
- Decision (taken per standing order 3): the bar is Dashboard, Notes, Chat, Library, More, left to right; Graph, Timeline and Reminders are More's first group.
- Built 2026-10-19: the order rules gone; the four columns; More's sheet in a lazy file (`phone-more.js`) with pages, a hairline, then tools, the page in hand `aria-current`; the header menu named "App menu"; the active tab pressed again scrolls its page to the top (`tabPageScroller`); the coarse-pointer floor 44; the timeline under 380 (the existing 380 block in 10-responsive.css) wraps its year menu and lets the day well take the card's padding (44.5px days). Guide topic `phone-nav`. After: `phonemore.js`, `phonetabs.js`, `phone.js` (390, 360, dark) 0 findings.
- Not verified: a real phone (safe-area insets resolve to 0 in headless Chromium); the smooth scroll-to-top under reduced motion on a device.

## Placed from INBOX, 2026-10-19 (peek sidebar header, split button; next PR)

1344. **The owner, 2026-10-19, verbatim** (screenshot, dark: a chat answer's head, the Atlas avatar, "Atlas", and a grey "Composer" badge). "can you also add a hover/click tooltip popup with a disclaimer and description for the composer message badge to inform the user how it isnt an ai and give some details?? maybe find some other ways to make it clear as well"
     Next: the badge opens a `data-help-for` popover (hover and click) saying the answer was written without an AI model, from your notes' own words and the app's counts, how to tell it apart, and how to turn on a model; the same on "From your notes"; consider a one-line note under the first composer answer of a session.
