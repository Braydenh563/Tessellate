// The guided tour: one card at a time, anchored to the control it describes.
//
// The app already had a welcome (`#onboarding-overlay`, app.js): a card in the
// middle of the screen with an icon, a title and a paragraph. It says what
// Tessellate is, and it is the right shape for that, but it cannot say WHERE
// anything is, because it covers the thing it is talking about. That gap is
// what this file fills, and the owner named it: "there is no guided tour and
// introduction, with positioned popup cards with back, next, skip, card
// tutorial tour numbers 1/?, dimmed background".
//
// Three rules shape everything below:
//
// 1. **A step is a real element plus a sentence.** No step invents a picture
//    of a control; it names a selector, and if that selector is missing or
//    hidden right now the step is dropped rather than pointed at nothing.
//    That is what makes the tour survive a narrow window, a control that
//    moved, and every later change to the markup: a step whose element has
//    gone simply stops being shown, and the counter renumbers.
// 2. **Short, and in sections.** The owner: "the tour cant be too long
//    because I dont want users skipping it or finding it too hard and giving
//    up". A section is three to five cards and counts its own ("Graph, 2 of
//    4"), and at its last card the tour offers the next section by name or a
//    Finish, so every section is a place to stop and none is a place to get
//    lost. The first run starts at "The basics" and chains on from there;
//    Settings, help and guide starts at any section and chains on the same
//    way (the owner, 2026-09-23: the other sections had to be found in
//    Settings one at a time). TOUR_SECTIONS is the one place that knows what
//    a section is: the replay buttons are built from it, so a section added
//    to that table needs no markup and no handler.
// 3. **It never traps anybody.** Skip is on every card, Escape does the same
//    thing, the choice is remembered beside `onboardingDone`, and nothing
//    here ever opens itself again once it has been finished or skipped.

// The geometry, in CSS pixels. These are window coordinates rather than
// design tokens: they are arguments to `getBoundingClientRect` arithmetic,
// which is why they live here and not in the stylesheet.
const TOUR_GAP = 12; // between the highlighted control and the card
const TOUR_EDGE = 12; // the closest the card may come to the window's edge
const TOUR_PAD = 6; // how far the bright cut-out is held off the control

// The sections, in the order the whole tour plays them. Each step is:
//
//   target  a CSS selector for the real element the card points at
//   side    where the card would like to sit; it flips and clamps if it
//           cannot fit there, and never covers the element
//   title   three or four words
//   text    one sentence, sentence case, no exclamation marks
//   tab     the tab that has to be showing for the target to be visible
//   notes   the Notes sub-tab ("capture", "browse", "writing-room", "ask")
//           the target lives in
//   or      a second selector, used when `target` is not on screen at this
//           window size because the control has moved behind another one
//           (on a phone Settings and Timeline live in More)
//   orText  what the card says when it is pointing at `or` instead, which
//           has to say where the control went, or the card describes a gear
//           while lighting up a button labelled More
//   library a Library sub-tab (its `data-target`) to press first
//   wb      where the Boards & maps sub-tab has to be: "landing" (the list of
//           boards), "board" or "map" (the newest one of that kind, opened;
//           the tour never makes one, see `tourContext`)
//   settings  the Settings section to open; the modal stays open between
//           two steps that both name one, and closes for any other step
//   unless  a name in TOUR_NEEDS, with `unlessText`: the words the card
//           says instead when that is false of this notebook
//   need    a name in TOUR_NEEDS: the step is kept only when that is true
//           of this notebook when its section starts (a card's menu needs a
//           card, a map's controls need a map)
//   media   a media query the window must match for the step to be in the
//           run at all, for a control that only exists on one side of a
//           breakpoint (the chat list is a sidebar on a laptop and a button
//           in the dock on a phone)
//
//: **Every main feature has a section, and a section walks INTO it** (the
//: owner, 2026-09-23: "If I want to do the other sections of the tour, I have
//: to go into the help settings and click the other tour section buttons, and
//: they dont guide me through the other main features"). The old four
//: sections pointed at the Graph, Timeline and Library *tab buttons* and said
//: what was behind them; each section here opens the feature and points at
//: three to five of its own controls, one sentence each. They are played one
//: after the other: the last card of a section offers the next one by name,
//: so no run ever needs Settings to find the rest.
const TOUR_SECTIONS = [
  {
    id: "basics",
    label: "The basics",
    blurb: "Where everything lives, and what is running",
    steps: [
      {
        target: "#tab-bar",
        side: "bottom",
        title: "Your tabs",
        text: "Every part of Tessellate is one of these. Notes is where you write, the others read what you wrote.",
      },
      {
        target: "#space-switcher-btn",
        side: "bottom",
        title: "Spaces",
        text: "A space is a separate notebook, work and home for instance, and this says which one you are looking at.",
      },
      {
        target: "#ai-status",
        side: "top",
        title: "Atlas, on this machine",
        text: "This dot says what the local model is doing. It runs on this computer, so your notes are never sent away to be read.",
      },
      {
        target: "#settings-btn",
        side: "bottom",
        title: "Settings",
        text: "Themes, the model, backups and this tour again all live behind the gear.",
        or: "#phone-more-btn",
        orText: "Settings is in More on a small screen: themes, the model, backups and this tour again.",
      },
    ],
  },
  {
    id: "notes",
    label: "Notes",
    blurb: "Capture, your notes, writing with Atlas and asking",
    steps: [
      {
        target: "#entry-content",
        side: "bottom",
        tab: "notes",
        notes: "capture",
        title: "Capture a thought",
        text: "Type anything here: a thought, a list, a link. Two square brackets point at another note.",
      },
      {
        target: "#save-btn",
        side: "top",
        tab: "notes",
        notes: "capture",
        title: "Save it",
        text: "Save files the note, and Atlas picks its category unless you set one.",
      },
      {
        target: "#note-search",
        side: "bottom",
        tab: "notes",
        notes: "browse",
        title: "Your notes",
        text: "Every note you have saved is listed here. Type to filter the list as you go.",
      },
      {
        target: "#draft-thoughts",
        side: "right",
        tab: "notes",
        notes: "writing-room",
        title: "Writing room",
        text: "Put rough thoughts here, in any order, and Atlas drafts them into finished writing.",
      },
      {
        target: "#question",
        side: "bottom",
        tab: "notes",
        notes: "ask",
        title: "Ask your notes",
        text: "Ask a question and the answer comes from your own notes, with the ones it used.",
      },
    ],
  },
  {
    id: "chat",
    label: "Chat",
    blurb: "Conversations with Atlas about your notes",
    steps: [
      {
        target: "#chat-input",
        side: "top",
        tab: "chat",
        title: "Ask anything",
        text: "Type a question here. Atlas answers from your notes and names the ones it read.",
      },
      {
        target: "#chat-mode-seg",
        side: "top",
        tab: "chat",
        title: "Ask or act",
        text: "Ask only reads. Agent mode can also tag, link and organise, and asks before changing a note.",
      },
      {
        target: "#chat-dock-more-btn",
        side: "top",
        tab: "chat",
        title: "Length and persona",
        text: "This gear sets how long the answers are and which persona gives them.",
      },
      {
        target: "#conversation-list",
        side: "right",
        tab: "chat",
        //: 820, not 600: from 600 to 819.98 (and on any coarse pointer) the
        //: chat sidebar is a sheet parked off screen at x -243 until its hinge
        //: is pressed, so there is nothing here to point at (700x900 planned
        //: 4 and showed 3: `scratchpad/ui-sweeps/tour.js`).
        media: "(min-width: 820px) and (pointer: fine)",
        title: "Your conversations",
        text: "Every chat is kept here. Pick one to carry on where you left off.",
      },
      {
        target: ".phone-sidebar-opener[aria-controls=chat-sidebar]",
        side: "bottom",
        tab: "chat",
        media: "(max-width: 599.98px)",
        title: "Your conversations",
        text: "This opens every chat you have had. Pick one to carry on where you left off.",
      },
    ],
  },
  {
    id: "graph",
    label: "Graph",
    blurb: "A map of how your notes connect",
    steps: [
      {
        target: "#graph-zoom",
        side: "left",
        tab: "graph",
        title: "Moving around",
        text: "Drag the map to move, zoom here or with the wheel, and click a note to open it.",
      },
      {
        target: "#graph-search",
        side: "bottom",
        tab: "graph",
        title: "Highlight notes",
        text: "Type a word and the notes that match it light up on the map.",
      },
      {
        target: "#graph-options-toggle",
        side: "bottom",
        tab: "graph",
        title: "Display options",
        text: "Options set the layout, colours, how notes pull together and what the map shows. Trace is here too.",
      },
    ],
  },
  {
    id: "library",
    label: "Library",
    blurb: "Everything you have made, in one place",
    steps: [
      {
        target: "#library-subtabs",
        side: "bottom",
        tab: "library",
        library: "library-view-documents",
        title: "One place for everything",
        text: "All, documents, boards and maps, images and files each have a sub-tab here.",
      },
      {
        target: "#library-search",
        side: "bottom",
        tab: "library",
        library: "library-view-documents",
        title: "Search the library",
        text: "Find anything you have kept by a word in it.",
      },
      {
        target: "#library-grid .library-card-menu > button",
        side: "left",
        tab: "library",
        library: "library-view-documents",
        need: "entries",
        title: "A card's menu",
        text: "Every card has one: open it, chat about it, export it or put it away.",
      },
      {
        target: "#library-new-doc",
        side: "bottom",
        tab: "library",
        library: "library-view-documents",
        title: "Make something new",
        text: "Create starts a new note, document, board or mind map.",
      },
      {
        target: "#library-subtab-docs",
        side: "bottom",
        tab: "library",
        library: "library-view-documents",
        title: "Documents",
        text: "Long pieces of writing live here, and each one opens in its own editor.",
      },
    ],
  },
  {
    id: "boards",
    label: "Boards",
    blurb: "Free canvases for cards, sketches and shapes",
    steps: [
      {
        target: "#wb-boards-new-menu",
        side: "bottom",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "landing",
        title: "New board",
        text: "New, then Whiteboard, starts an empty canvas that you arrange by hand. Every board and map you make is listed below it.",
      },
      {
        target: "#wb-tool-group",
        side: "top",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "board",
        title: "The tools",
        text: "Select, pan, draw, and add shapes and pictures from this rail.",
        or: "#wb-tools-opener",
        orText: "On a small screen this button opens the tools: select, pan, draw, shapes and pictures.",
      },
      {
        target: "#wb-add-note",
        side: "bottom",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "board",
        title: "Notes on a board",
        text: "Notes opens your notebook beside the board, so you can drag any note on as a card.",
      },
      {
        target: "#wb-back-to-boards",
        side: "bottom",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "board",
        title: "Back to the list",
        text: "This goes back to every board and mind map you have made.",
      },
    ],
  },
  {
    id: "maps",
    label: "Mind maps",
    blurb: "Ideas that branch out from one centre",
    steps: [
      {
        target: "#wb-boards-new-menu",
        side: "bottom",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "landing",
        title: "New mind map",
        text: "New, then Mind map, starts from one central idea. Inside it, Tab adds a branch and Enter adds one beside it.",
        //: Said instead when the notebook has no map yet (INBOX 426 y): the
        //: map's own cards are dropped from the run then, and this card is
        //: the one that says why and what to press.
        unless: "map",
        unlessText: "You have no mind map yet. New, then Mind map, starts one from a central idea; its own tools show once you have one.",
      },
      {
        target: "#wb-map-add-root",
        side: "top",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "map",
        need: "map",
        media: "(min-width: 600px)",
        title: "Add a topic",
        text: "This adds a new top-level topic beside the ones the map already has.",
      },
      {
        target: "#wb-map-focus-here",
        side: "top",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "map",
        need: "map",
        media: "(min-width: 600px)",
        title: "Focus on a branch",
        text: "This shows the selected branch and its neighbours, and hides the rest.",
      },
      {
        target: "#wb-map-tidy",
        side: "top",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "map",
        need: "map",
        media: "(min-width: 600px)",
        title: "Tidy the layout",
        text: "This lays every topic you have not pinned out again, neatly.",
      },
      {
        // Below 600 the map's rail is one button that opens it as a sheet.
        target: "#wb-tools-opener",
        side: "top",
        tab: "library",
        library: "library-view-whiteboard",
        wb: "map",
        need: "map",
        media: "(max-width: 599.98px)",
        title: "The map's tools",
        text: "This opens the map's tools: add a topic, focus on one branch, or tidy the layout.",
      },
    ],
  },
  {
    id: "timeline",
    label: "Timeline",
    blurb: "Your notebook in the order it happened",
    steps: [
      {
        target: "#timeline-view-seg",
        side: "bottom",
        tab: "timeline",
        title: "Feed or table",
        text: "Read your notebook as a feed, day by day, or as a table you can sort.",
        // Below 1100 the dock folds this switch into Options (app.js,
        // `foldDockArrange`); Options also groups by time, so its own card
        // is left to the wide window.
        or: "#timeline-options-menu",
        orText: "On a smaller window Options holds the feed or table switch, and groups the timeline by day, week or month.",
      },
      {
        target: "#timeline-kinds-menu",
        side: "bottom",
        tab: "timeline",
        title: "Choose the kinds",
        text: "Kinds picks what is shown: notes, boards, documents and reminders.",
      },
      {
        target: "#timeline-options-menu",
        side: "bottom",
        tab: "timeline",
        // Below 1100 the view switch folds into Options, and the card before
        // this one already points there (its `or`).
        media: "(min-width: 1100px)",
        title: "Group by time",
        text: "Options groups the timeline by day, week, month or year.",
      },
      {
        target: "#timeline-jump-today",
        side: "bottom",
        tab: "timeline",
        title: "Back to today",
        text: "Today scrolls the timeline back to now.",
      },
    ],
  },
  {
    id: "reminders",
    label: "Reminders",
    blurb: "Things to be told about later",
    steps: [
      {
        target: "#reminder-magic",
        side: "bottom",
        tab: "reminders",
        title: "Say it in words",
        text: "Type a reminder as a sentence, call mum tomorrow evening, and the local model sets the time.",
        // Below 1100 the form is a sheet that New reminder opens (app.js,
        // `openReminderCompose`), so the card points at the door to it.
        or: "#reminders-new",
        orText: "Add a reminder opens the form: type one as a sentence and the local model sets the time.",
      },
      {
        target: "#reminder-presets-menu",
        side: "bottom",
        tab: "reminders",
        media: "(min-width: 1100px)",
        title: "Quick set",
        text: "Quick set picks a common time, in an hour or tonight, in one press.",
      },
      {
        target: "#reminder-filter",
        side: "top",
        tab: "reminders",
        title: "Your reminders",
        text: "Everything you have set is listed below. These show what is open, done or all of it.",
      },
      {
        target: "#reminder-view-toggle",
        side: "bottom",
        tab: "reminders",
        title: "List or calendar",
        text: "Your reminders as a list here, or Calendar for the Timeline's calendar, where a reminder drags to another day.",
        // Below 1100 the dock folds its arrange zone into More (app.js,
        // `foldDockArrange`).
        or: "#reminders-more-menu",
        orText: "More holds the list and calendar buttons on a smaller window, with the sorting.",
      },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    blurb: "Appearance, the model and help",
    steps: [
      {
        target: "#settings-search",
        side: "right",
        settings: "appearance",
        title: "Search settings",
        text: "Type what you are after and the matching settings are found for you.",
      },
      {
        target: "#settings-nav-appearance",
        side: "right",
        media: "(min-width: 820px)",
        settings: "appearance",
        title: "Appearance",
        text: "Themes, colours, fonts and the look of every surface.",
      },
      {
        target: "#avatar-buddy-row",
        side: "left",
        settings: "appearance",
        title: "A companion",
        text: "Turn on a small character that finds a free spot on each page and reacts to what you do.",
      },
      {
        target: "#settings-nav-models",
        side: "right",
        media: "(min-width: 820px)",
        settings: "models",
        title: "Models",
        text: "Which local model Atlas runs on, and how to connect one.",
      },
      {
        target: "#settings-nav-help",
        side: "right",
        media: "(min-width: 820px)",
        settings: "help",
        title: "Help and this tour",
        text: "Guides, the welcome and every part of this tour, whenever you want them again.",
      },
      {
        // Below 820 the section list is this one picker (the strip is hidden).
        target: "#settings-nav .settings-jump",
        side: "bottom",
        settings: "appearance",
        media: "(max-width: 819.98px)",
        title: "Every section",
        text: "Pick a section here: Appearance for the look, Models for Atlas, Help for this tour again.",
      },
    ],
  },
  {
    id: "status",
    label: "Status bar",
    blurb: "Shortcuts along the bottom edge, from any tab",
    steps: [
      {
        target: "#status-command",
        side: "top",
        //: Hidden from 600 to 819.98 and on any coarse pointer
        //: (`10-responsive.css`, the status bar's icon-only band), so a step
        //: here has nothing to point at at those widths.
        media: "(max-width: 599.98px), (min-width: 820px) and (pointer: fine)",
        title: "Commands",
        text: "Ctrl and K, or a press here, searches and runs anything by name.",
      },
      {
        target: "#status-agent",
        side: "top",
        title: "Ask",
        text: "Ask the agent to do something for you, from any tab.",
      },
      {
        target: "#status-guide",
        side: "top",
        title: "Guide",
        text: "Ask Atlas how the app works without leaving the page you are on.",
      },
      {
        target: "#status-find",
        side: "top",
        title: "Find",
        text: "Search every note, document and file you keep, and the app itself.",
      },
    ],
  },
];

// The three layers, shown together and hidden together. `#tour-block` is the
// press-catcher: one element holding the four panels that surround the hole,
// so showing and hiding it is one class change rather than four.
const TOUR_LAYERS = ["tour-block", "tour-spot", "tour-card"];

//: The four panels, in the one order everything that touches them uses.
const TOUR_PANEL_IDS = [
  "tour-block-top",
  "tour-block-right",
  "tour-block-bottom",
  "tour-block-left",
];

// The run in progress, or null. `steps` is a flattened copy rather than a
// reference into the table above, because a step whose element turns out to be
// hidden is spliced out of it, and the table has to stay whole for the next
// run (a window widened between two runs brings that step back).
let tourRun = null;

// --- helpers ----------------------------------------------------------------

//: "Visible" here means "worth pointing at": in the document, laid out, and
//: not painted out. Three separate ways to be invisible, and all three happen
//: in this app: `.hidden` (display: none, so a zero box), a responsive rule
//: that drops a control below a width (also a zero box), and an element faded
//: to nothing mid-transition. A step that survives all three has a rectangle
//: the cut-out can sit on.
function tourVisible(el) {
  if (!el || !el.isConnected) return false;
  const box = el.getBoundingClientRect();
  if (box.width < 1 || box.height < 1) return false;
  const style = getComputedStyle(el);
  if (style.visibility === "hidden" || style.display === "none") return false;
  //: A fourth way: **inside a closed `<details>`**, and it is how a docked
  //: control folded into a dock's ⋯ looks. The menu's list keeps its layout
  //: box while the menu is shut (measured at 390: New mind map, folded into
  //: the boards dock's ⋯, answered a 241x36 box with nothing painted), so
  //: every check above says yes to a button nobody can see. Only the
  //: menu's own summary is on screen.
  const shut = el.parentElement?.closest("details:not([open])");
  if (shut && !shut.querySelector(":scope > summary")?.contains(el)) return false;
  return Number(style.opacity || "1") > 0.05;
}

//: The element a step actually points at, which is not always the element it
//: names. `enhanceSelect` (sheets-selects.js) wraps every `<select>` in the app in a
//: `.select-shell` and puts a button in front of it, leaving the native
//: control in place but out of the layout: measured on the capture form's
//: category picker, `#entry-category` is a 0x0 box behind a 129x30 opener, so
//: a step naming it would be dropped for having nothing to point at while the
//: control it means sits right there on screen. The same rule DESIGN.md
//: already states for focus ("never `select.focus()`", the native control is
//: not the thing the person is looking at), applied to geometry.
function tourAnchorFor(el) {
  return el ? el.closest(".select-shell") || el : el;
}

//: **Laid out is not the same as on screen**, and the difference is what
//: INBOX 280 is. `tourVisible` answers "this element has a box and is not
//: painted out", which a control scrolled away, pushed past an edge or parked
//: off the page all satisfy. The cut-out is then asked to sit on a rectangle
//: that is not in the window, and everything downstream of it goes wrong at
//: once (see `tourSpotlight`).
//:
//: A few pixels of overlap is not enough to point at, so this asks for a
//: usable amount of the control to be inside the window rather than for the
//: rectangles to merely touch.
const TOUR_ON_SCREEN_MIN = 8;

function tourOnScreen(el) {
  if (!el) return false;
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const box = el.getBoundingClientRect();
  const across = Math.min(box.right, vw) - Math.max(box.left, 0);
  const down = Math.min(box.bottom, vh) - Math.max(box.top, 0);
  return across >= TOUR_ON_SCREEN_MIN && down >= TOUR_ON_SCREEN_MIN;
}

//: **On screen is not the same as in front**, and this is the case that made
//: every step after the first look broken (2026-09-23, measured). A control
//: can be laid out, inside the window and at full opacity while a sheet, the
//: command palette, the features browser or the shortcut sheet is drawn over
//: it. The tour then cut its hole around the control and the hole showed the
//: overlay: with the Atlas guide open, all four steps of the basics answered
//: `elementFromPoint` with `.sheet-overlay`, not the control. `tourVisible`
//: and `tourOnScreen` both said yes to every one of them.
//:
//: So a target is also asked what is actually on top of it, at five points
//: rather than one (a toast or a floating button over one corner is not a
//: covered control), ignoring the tour's own layers, which are drawn around
//: the hole and never in it. A point that lands on the control, on something
//: inside it, or on an ancestor of it (the gap between two tab buttons is the
//: tab bar) counts as uncovered.
//:
//: **A toast is not an overlay.** It is gone in seconds, and one that
//: happens to be up when a step is judged used to cost that step for good:
//: measured, a section finished with Finish leaves its "That is the tour"
//: toast over the bottom of the window, and the next run's Chat mode and
//: Graph zoom steps were dropped under it. `#toast-box` is skipped like the
//: tour's own layers.
function tourCovered(el) {
  if (!el) return true;
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const box = el.getBoundingClientRect();
  let counted = 0;
  let covered = 0;
  for (const [fx, fy] of [[0.5, 0.5], [0.2, 0.3], [0.8, 0.3], [0.2, 0.7], [0.8, 0.7]]) {
    const x = box.left + box.width * fx;
    const y = box.top + box.height * fy;
    if (x < 0 || y < 0 || x >= vw || y >= vh) continue;
    counted += 1;
    const top = document
      .elementsFromPoint(x, y)
      .find((node) => !node.closest("#tour-block, #tour-spot, #tour-card, #toast-box"));
    if (!top || !(el.contains(top) || top.contains(el))) covered += 1;
  }
  return counted === 0 || covered * 2 > counted;
}

//: Which element a step points at right now, and whether it is the step's
//: own control or its `or` one. The first of the two that is laid out wins,
//: so a window resized across the phone breakpoint moves the card from the
//: gear to More and back instead of dropping the step and renumbering the
//: counter under the person's eyes. When neither is laid out the step's own
//: element is returned, so the caller's "nothing to point at" is a judgement
//: about the control the step is really about.
function tourResolve(step) {
  const own = tourAnchorFor(document.querySelector(step.target));
  if (tourVisible(own) || !step.or) return { el: own, alt: false };
  const other = tourAnchorFor(document.querySelector(step.or));
  if (tourVisible(other)) return { el: other, alt: true };
  return { el: own, alt: false };
}

//: The whole judgement in one place: a box, inside the window, with nothing
//: of anybody else's drawn over it.
function tourUsable(el) {
  return tourVisible(el) && tourOnScreen(el) && !tourCovered(el);
}

//: **Set, measure, correct by the difference, never trust the first number.**
//: DESIGN.md's rule for any popup placed in the window's own coordinates, and
//: it is not defensive programming: a `position: fixed` element takes its
//: frame from the nearest ancestor carrying a `filter`, `transform` or
//: `backdrop-filter`, and this app puts a filter on `.card` whenever the
//: background art is on. A word menu measured with the art on once asked for
//: `left: 952` and drew at 1245. The tour's three elements are children of
//: `<body>` precisely so that cannot happen, and the correction pass stays
//: anyway: it costs one extra `getBoundingClientRect` per step and it is the
//: difference between a card beside a button and a card in another postcode.
function tourPlaceFixed(el, left, top) {
  //: Placed, so it may be seen (hidden in `openTour` until now).
  if (el.id === "tour-card") el.style.visibility = "";
  //: **Measured against a probe that never moves, then checked a frame
  //: later** (INBOX 397, the owner's desktop window, three reports). The
  //: old pass wrote a position, read the element straight back and added
  //: the difference. That is right for a containing block and wrong for
  //: anything that makes the element's own box lag behind its style (a
  //: transition, an animation, a compositor that has not caught up): the
  //: read-back is where the box *was*, the "correction" doubles the move,
  //: and the owner's screenshots show exactly that, the ring the right size
  //: and 620px to one side, right on one run and left on the next, with the
  //: card thrown off the window the same way. Headless Chromium never showed
  //: it at any size, scale or with real scrollbars.
  //:
  //: The frame's origin is read from `#tour-origin`, a 0x0 fixed box at
  //: 0,0 in the same parent that nothing ever moves, so an ancestor's
  //: filter or transform is still accounted for, and the element's own
  //: state cannot poison the number. The element is then read back once,
  //: after a frame, and nudged only if it is still somewhere else.
  //:
  //: **No nudge a frame later any more** (INBOX 426 y, image 87: after "Next:
  //: Notes" the ring was drawn in the wrong corner, and the log said
  //: "tour-spot asked for 336,275, drew at 1128,4; moved"). The nudge added
  //: the difference it read one frame on, and a frame is not long enough
  //: for a tab switch to settle: whatever was still moving then (the frame
  //: the layers are laid out in, the control itself) moved again after the
  //: nudge, and the nudge's own distance was left in. The wanted box is kept
  //: on the element instead, and `tourWatchFrame` compares it with what is
  //: drawn on every frame the tour is up, placing again from a fresh origin
  //: whenever the two disagree, for as long as they do.
  const origin = tourOrigin();
  el.style.left = `${Math.round(left - origin.left)}px`;
  el.style.top = `${Math.round(top - origin.top)}px`;
  el._tourWant = { left: Math.round(left), top: Math.round(top) };
}

//: **The tour follows what it points at, every frame it is up** (INBOX 426
//: y). A step was placed once, when its control's box had held still for
//: two frames, and again only on a resize or a scroll event. A control can
//: move without either: content loading above it (a tab's list arriving, a
//: face drawn, a fold opening), a transform settling on a layer between it
//: and the window. Images 95 and 96 are that: the companion step's card over
//: its own control until Next then Back placed it again. So while a card is
//: showing, each frame reads the control's box and where the card and the
//: ring were actually drawn, and places the step again when the control
//: moved or either layer is not where it was asked to be. One
//: `getBoundingClientRect` of each per frame; a layer that refuses to land
//: (something outside the tour holding it) is left alone after ten tries
//: rather than chased for ever.
function tourWatch() {
  if (tourWatch.frame) return;
  tourWatch.frame = requestAnimationFrame(tourWatchFrame);
}

function tourWatchFrame() {
  tourWatch.frame = 0;
  const run = tourRun;
  if (!run) return;
  tourWatch.frame = requestAnimationFrame(tourWatchFrame);
  const card = document.getElementById("tour-card");
  if (!run.el || !card || card.getAttribute("aria-busy") === "true") return;
  const box = run.el.getBoundingClientRect();
  const key = [box.left, box.top, box.width, box.height].map(Math.round).join(",");
  const drift = (el) => {
    if (!el || el.classList.contains("hidden") || !el._tourWant) return false;
    const drawn = el.getBoundingClientRect();
    return Math.abs(drawn.left - el._tourWant.left) > 1.5 || Math.abs(drawn.top - el._tourWant.top) > 1.5;
  };
  const moved = key !== run.watchKey;
  const off = drift(card) || drift(document.getElementById("tour-spot"));
  if (!moved && !off) {
    run.watchMisses = 0;
    return;
  }
  run.watchKey = key;
  if (!moved && (run.watchMisses = (run.watchMisses || 0) + 1) > 10) return;
  if (!tourVisible(run.el) || !tourOnScreen(run.el)) return;
  tourPosition();
}

//: The window-coordinate origin of the frame the tour's layers are laid out
//: in: (0, 0) unless an ancestor gives fixed boxes a frame of its own.
function tourOrigin() {
  let probe = document.getElementById("tour-origin");
  if (!probe) {
    probe = document.createElement("div");
    probe.id = "tour-origin";
    probe.setAttribute("aria-hidden", "true");
    for (const [k, v] of Object.entries({
      position: "fixed", left: "0px", top: "0px", width: "0px", height: "0px",
      visibility: "hidden", pointerEvents: "none", transition: "none", animation: "none",
    })) probe.style[k] = v;
    const card = document.getElementById("tour-card");
    (card?.parentElement || document.body).appendChild(probe);
  }
  return probe.getBoundingClientRect();
}

function tourClamp(value, low, high) {
  // `low` wins when the window is narrower than the card plus its two
  // margins: a negative range has to resolve to the near edge rather than to
  // a number outside the window on the other side.
  return Math.max(low, Math.min(value, high));
}

function tourOverlap(a, b) {
  const w = Math.min(a.left + a.width, b.right) - Math.max(a.left, b.left);
  const h = Math.min(a.top + a.height, b.bottom) - Math.max(a.top, b.top);
  return w > 0 && h > 0 ? w * h : 0;
}

//: One candidate box per side, each already clamped into the window, so the
//: choice below is made between boxes that are all legal rather than between
//: boxes that would have to be fixed up afterwards. The preferred side leads,
//: its opposite follows (a card that does not fit below a control almost
//: always fits above it), then the two perpendicular ones.
function tourCandidates(target, side, size) {
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const maxLeft = vw - TOUR_EDGE - size.width;
  const maxTop = vh - TOUR_EDGE - size.height;
  const centreX = tourClamp(
    target.left + target.width / 2 - size.width / 2,
    TOUR_EDGE,
    Math.max(TOUR_EDGE, maxLeft)
  );
  const centreY = tourClamp(
    target.top + target.height / 2 - size.height / 2,
    TOUR_EDGE,
    Math.max(TOUR_EDGE, maxTop)
  );
  const boxes = {
    bottom: { left: centreX, top: target.bottom + TOUR_GAP },
    top: { left: centreX, top: target.top - TOUR_GAP - size.height },
    right: { left: target.right + TOUR_GAP, top: centreY },
    left: { left: target.left - TOUR_GAP - size.width, top: centreY },
  };
  const opposite = { bottom: "top", top: "bottom", left: "right", right: "left" };
  const order = [side, opposite[side], "bottom", "top", "right", "left"];
  const seen = new Set();
  const out = [];
  for (const name of order) {
    if (!boxes[name] || seen.has(name)) continue;
    seen.add(name);
    const raw = boxes[name];
    // Whether the side it asked for actually had the room is recorded BEFORE
    // clamping, because clamping always produces a box inside the window and
    // would otherwise make every side look as though it fitted.
    const fits =
      raw.left >= TOUR_EDGE - 0.5 &&
      raw.top >= TOUR_EDGE - 0.5 &&
      raw.left <= maxLeft + 0.5 &&
      raw.top <= maxTop + 0.5;
    out.push({
      name,
      fits,
      left: tourClamp(raw.left, TOUR_EDGE, Math.max(TOUR_EDGE, maxLeft)),
      top: tourClamp(raw.top, TOUR_EDGE, Math.max(TOUR_EDGE, maxTop)),
      width: size.width,
      height: size.height,
    });
  }
  return out;
}

//: The choice: a side that leaves the control uncovered beats one that does
//: not, and among equals the side the step asked for wins. Covering the
//: control is the one failure this whole file exists to avoid, so it is
//: weighted far above not quite fitting: a card pushed against the edge of the
//: window is still readable, a card sitting on top of the thing it is
//: describing is the centred slide carousel again.
function tourChoose(target, side, size) {
  let best = null;
  for (const box of tourCandidates(target, side, size)) {
    const score = tourOverlap(box, target) * 1000 + (box.fits ? 0 : 1);
    if (!best || score < best.score) best = { ...box, score };
  }
  return best;
}

// --- painting one step ------------------------------------------------------

//: The dim, and the presses, in one set of four rectangles. Four panels around
//: the hole rather than one sheet across the window, and the reason is the
//: owner's report of 2026-09-20: "it doesnt let the user click the highglighted
//: items". A tour that says "press Save" and then eats the press is worse than
//: no tour, because the person believes the control is broken. `#tour-block`
//: used to be `inset: 0`, and `document.elementFromPoint` at the centre of
//: every one of the fifteen steps answered `tour-block`: the dim layer, not the
//: control.
//:
//: Four panels, laid out from the same rectangle the cut-out uses, leave that
//: rectangle with nothing of the tour's over it at all, so a press inside it
//: reaches the page and a press anywhere else is still swallowed (the step
//: cannot be taken out from under its own card). The four have to be kept in
//: step on every scroll and resize, which is why they are written here, in the
//: one function that already runs on every reflow, and never anywhere else.
//:
//: **Since 2026-09-21 these four also paint the dim** (04-chat-dock-appearance,
//: the note over `.tour-block`). It used to be one `box-shadow` spread 100vmax
//: from the cut-out, which no test could read; these four are the rectangles
//: the sweep below already measures, so an uncovered strip is now a failing
//: test rather than a photograph.
function tourBlockPanels(left, top, right, bottom) {
  //: **`innerWidth`, not `clientWidth`, and the difference is the bug the
  //: owner photographed twice.** `clientWidth` stops at the scrollbar;
  //: `innerWidth` includes its gutter. The panels are `position: fixed`, so
  //: they are laid out against the window, and sizing them to the narrower
  //: number leaves the gutter uncovered: the page goes dark and a bright band
  //: stands at the right edge, the full height of the window, which is exactly
  //: what his screenshots show. It never appeared in a sweep because headless
  //: Chromium draws overlay scrollbars that take no space, so the gutter here
  //: is 0 and the two numbers agree; on Windows they differ by about 17px, and
  //: on a page with its own scrolling column by more.
  //:
  //: Covering a few pixels too many is free, because these panels are a flat
  //: scrim with nothing to line up against. Covering too few is the fault.
  const vw = Math.max(document.documentElement.clientWidth, window.innerWidth || 0);
  const vh = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);
  const panels = {
    "tour-block-top": { left: 0, top: 0, width: vw, height: Math.max(0, top) },
    "tour-block-bottom": {
      left: 0,
      top: Math.min(vh, bottom),
      width: vw,
      height: Math.max(0, vh - bottom),
    },
    "tour-block-left": {
      left: 0,
      top: Math.max(0, top),
      width: Math.max(0, left),
      height: Math.max(0, Math.min(vh, bottom) - Math.max(0, top)),
    },
    "tour-block-right": {
      left: Math.min(vw, right),
      top: Math.max(0, top),
      width: Math.max(0, vw - right),
      height: Math.max(0, Math.min(vh, bottom) - Math.max(0, top)),
    },
  };
  for (const [id, box] of Object.entries(panels)) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.style.width = `${Math.round(box.width)}px`;
    el.style.height = `${Math.round(box.height)}px`;
    tourPlaceFixed(el, box.left, box.top);
  }
}

//: The cut-out. The hole in the dim is the rectangle the four panels above are
//: laid out around, and this element only draws the ring inside it, so the
//: control is the page at full strength with an accent outline on it. It never
//: takes a press (`pointer-events: none`); the four panels are what take them.
//: The tour with no cut-out: the card, centred, over a page that is not
//: dimmed and not covered. Used when there is nothing on screen to point at,
//: which is the one case where a dim is worse than none: a dim needs a hole,
//: and a hole that is not in the window darkens everything and highlights
//: nothing (INBOX 280: "the whole page dimmed except a ~100px vertical strip
//: at the right edge, no card, nothing highlighted").
function tourClearSpotlight() {
  document.getElementById("tour-spot").classList.add("hidden");
  for (const id of TOUR_PANEL_IDS) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.style.width = "0px";
    el.style.height = "0px";
  }
}

//: Lay the cut-out on the control, and answer whether it could be done.
//:
//: **The clamped box can be empty, and an empty one used to be written out
//: anyway.** With a target off the right edge, `left` clamps to the target
//: and `right` clamps to the window, so `right - left` goes *negative*:
//: `width: -994px` is invalid, the declaration is dropped, and the element
//: silently keeps the width it had on the previous step. The cut-out then
//: sits off the page at the wrong size, its own `box-shadow` (which is the
//: dim) lands somewhere nobody asked for, and the page is dark everywhere
//: except whatever band the shadow's edge happens to fall on. Measured, at
//: 2000x1140 with the target moved to x 3000: the spot was placed at 2994
//: still carrying the previous step's 708px width. That is CLAUDE.md's
//: invalid-value trap, and it is INBOX 280's screenshot.
//:
//: So the box is checked before it is written, and an empty one draws no
//: cut-out at all rather than a broken one.
function tourSpotlight(target) {
  const spot = document.getElementById("tour-spot");
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const left = Math.max(0, target.left - TOUR_PAD);
  const top = Math.max(0, target.top - TOUR_PAD);
  const right = Math.min(vw, target.right + TOUR_PAD);
  const bottom = Math.min(vh, target.bottom + TOUR_PAD);
  const width = right - left;
  const height = bottom - top;
  if (width < 1 || height < 1) {
    tourClearSpotlight();
    return false;
  }
  spot.classList.remove("hidden");
  spot.style.width = `${Math.round(width)}px`;
  spot.style.height = `${Math.round(height)}px`;
  tourPlaceFixed(spot, left, top);
  tourBlockPanels(left, top, right, bottom);
  return true;
}

//: A target below the fold is reached by moving the nearest scrolling
//: ancestor's own `scrollTop`, never by `scrollIntoView`: DESIGN.md's rule for
//: bringing a marked row into view, and the reason is that `scrollIntoView`
//: walks every scrolling ancestor including the page, which here would mean
//: the whole tab shifting under a card already positioned against it.
function tourBringIntoView(el) {
  //: Sideways first, for the docks that scroll along instead of wrapping on
  //: a phone: measured at 390, the Timeline's Feed or table switch sat at x
  //: 192 to 417 in a 390 window, a third of it past the edge, and the card
  //: then lit a control you could not see all of.
  for (let row = el.parentElement; row && row !== document.body; row = row.parentElement) {
    const across = getComputedStyle(row);
    if (/(auto|scroll)/.test(across.overflowX) && row.scrollWidth > row.clientWidth + 1) {
      const box = el.getBoundingClientRect();
      const host = row.getBoundingClientRect();
      if (box.left < host.left + TOUR_EDGE || box.right > host.right - TOUR_EDGE) {
        row.scrollLeft += box.left - host.left - Math.max(0, (host.width - box.width) / 2);
      }
      break;
    }
  }
  const vh = document.documentElement.clientHeight;
  let node = el.parentElement;
  while (node && node !== document.body) {
    const style = getComputedStyle(node);
    const scrolls =
      /(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 1;
    if (scrolls) {
      const box = el.getBoundingClientRect();
      const host = node.getBoundingClientRect();
      if (box.top < host.top + TOUR_EDGE || box.bottom > host.bottom - TOUR_EDGE) {
        node.scrollTop += box.top - host.top - (host.height - box.height) / 2;
      }
      return;
    }
    node = node.parentElement;
  }
  const box = el.getBoundingClientRect();
  if (box.top < TOUR_EDGE || box.bottom > vh - TOUR_EDGE) {
    const scroller = document.scrollingElement || document.documentElement;
    scroller.scrollTop += box.top - (vh - box.height) / 2;
  }
}

function tourPosition() {
  if (!tourRun) return;
  //: A stranded step has no anchor, so the card goes to the middle of the
  //: window and the spotlight and its four panels are taken down: a hole cut
  //: around nothing is a hole in the middle of the screen.
  if (!tourRun.el) {
    //: The spotlight and its four panels come down: a hole cut around nothing
    //: is a hole in the middle of the screen, and four panels each stretched
    //: over the whole window is a flat grey page, which is what the first
    //: attempt at this did. `tourClearSpotlight` is the one that already knows
    //: how to take them down, and the centring below is the same arithmetic
    //: the `!lit` case uses further down, clamped to the window so the card
    //: cannot end up off the top right corner.
    tourClearSpotlight();
    const card = document.getElementById("tour-card");
    if (!card) return;
    card.dataset.side = "centre";
    const size = card.getBoundingClientRect();
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;
    tourPlaceFixed(
      card,
      tourClamp((vw - size.width) / 2, TOUR_EDGE, Math.max(TOUR_EDGE, vw - TOUR_EDGE - size.width)),
      tourClamp((vh - size.height) / 2, TOUR_EDGE, Math.max(TOUR_EDGE, vh - TOUR_EDGE - size.height))
    );
    return;
  }
  const card = document.getElementById("tour-card");
  const target = tourRun.el.getBoundingClientRect();
  const lit = tourSpotlight(target);
  // The card's own size is measured on screen, with this step's text already
  // in it: the height changes by a whole line between steps, and a placement
  // computed from the previous step's height is a card that overlaps.
  const size = card.getBoundingClientRect();
  if (!lit) {
    //: Nothing to point at, so the card stops pointing: centred, with the
    //: page neither dimmed nor covered. A step reaches this only when its
    //: control went off screen after it was placed (a resize, a scroll under
    //: it); a step that starts that way is dropped in `tourShow` instead.
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;
    card.dataset.side = "centre";
    tourPlaceFixed(
      card,
      tourClamp((vw - size.width) / 2, TOUR_EDGE, Math.max(TOUR_EDGE, vw - TOUR_EDGE - size.width)),
      tourClamp((vh - size.height) / 2, TOUR_EDGE, Math.max(TOUR_EDGE, vh - TOUR_EDGE - size.height))
    );
    return;
  }
  const place = tourSheetPlace(target, size) || tourChoose(target, tourRun.step.side, size);
  card.dataset.side = place.name;
  tourPlaceFixed(card, place.left, place.top);
}

//: The phone's card is a sheet, docked to the edge of the window away from the
//: control, the width of the window less its gutters (the width is CSS's,
//: `.tour-card` under the phone breakpoint). A 336px card placed beside a
//: control on a 390px screen had nowhere to go but on top of the page's other
//: half, and its position jumped from step to step as the controls moved
//: between the header and the tab bar; a sheet that only ever sits at the top
//: or the bottom is the phone's own shape for "something about this screen".
//: Null above the breakpoint, and null when the control is so tall that both
//: docks would cover it, where the side-by-side placer does better.
const TOUR_SHEET_QUERY = "(max-width: 599.98px)";

function tourSheetPlace(target, size) {
  if (!window.matchMedia(TOUR_SHEET_QUERY).matches) return null;
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const left = tourClamp((vw - size.width) / 2, TOUR_EDGE, Math.max(TOUR_EDGE, vw - TOUR_EDGE - size.width));
  const docks = {
    "docked-bottom": { left, top: Math.max(TOUR_EDGE, vh - TOUR_EDGE - size.height) },
    "docked-top": { left, top: TOUR_EDGE },
  };
  const lowHalf = target.top + target.height / 2 > vh / 2;
  const order = lowHalf ? ["docked-top", "docked-bottom"] : ["docked-bottom", "docked-top"];
  for (const name of order) {
    const box = { ...docks[name], width: size.width, height: size.height };
    if (tourOverlap(box, target) === 0) return { name, ...box };
  }
  return null;
}

function tourRender() {
  const run = tourRun;
  const place = tourSectionPlace(run);
  document.getElementById("tour-section").textContent = run.step.sectionLabel;
  //: **A stranded step still says something** (INBOX 315). `run.el` is null
  //: when the last step of a run has nothing on screen to point at: the tour
  //: keeps the card rather than closing, because a tour that vanishes
  //: mid-gesture reads as the feature breaking, so the card has to explain
  //: itself instead of pointing at a corner of the window.
  const card = document.getElementById("tour-card");
  card?.classList.toggle("tour-card-stranded", Boolean(run.stranded));
  // "2 of 4", the owner's "card tutorial tour numbers", beside the section's
  // chip, so the head reads "Graph, 2 of 4". It counts THIS section's steps
  // in this run, not the whole run: forty-odd cards counted as one number
  // reads as a chore, four reads as a moment. It renumbers when a step is
  // dropped for having no element, so it can never promise a step the tour
  // is not going to show.
  document.getElementById("tour-count").textContent = `${place.at + 1} of ${place.total}`;
  document.getElementById("tour-title").textContent = run.step.title;
  const lacking = run.step.unless && run.context && !TOUR_NEEDS[run.step.unless]?.(run.context);
  const text = run.alt && run.step.orText
    ? run.step.orText
    : lacking && run.step.unlessText
      ? run.step.unlessText
      : run.step.text;
  document.getElementById("tour-text").textContent = run.stranded
    ? `${text} This control is not on screen at this window size, so there is nothing to point at here.`
    : text;
  document.getElementById("tour-back").disabled = run.index === 0;
  //: **The last card of a section names the next one** (the owner,
  //: 2026-09-23). "Next: Chat" is the primary and goes straight on into that
  //: section without leaving the tour; the ghost on the other end of the row
  //: becomes "Finish", which ends the tour as a finish (remembered, and the
  //: toast says where the rest is) rather than as a skip. The very last card
  //: of the run says Done.
  const next = document.getElementById("tour-next");
  const skip = document.getElementById("tour-skip");
  next.textContent = place.next
    ? `Next: ${place.next}`
    : run.index >= run.steps.length - 1
      ? "Done"
      : "Next";
  skip.textContent = place.next ? "Finish" : "Skip";
  run.atSectionEnd = Boolean(place.next);
}

//: Where the current step sits in its own section, and what comes after it.
//: The run is one flat list across every section it will play, so Back walks
//: into the previous section as naturally as Next walks into the next one,
//: and the section is read off each step. That is also what keeps the count
//: honest: a step dropped from the run is dropped from its section's count.
function tourSectionPlace(run) {
  const here = run.steps[run.index] || run.step;
  const id = here.sectionId;
  const mine = run.steps.filter((step) => step.sectionId === id);
  const following = run.steps[run.index + 1];
  const last = !following || following.sectionId !== id;
  return {
    at: Math.max(0, mine.indexOf(here)),
    total: Math.max(1, mine.length),
    next: last && following ? following.sectionLabel : "",
  };
}

async function tourFrame() {
  // Two frames: one for the tab switch or sub-tab change to take effect, one
  // for the layout that follows it. Measuring in the first frame reads the
  // outgoing tab's geometry, which is how a card ends up beside where a
  // control used to be.
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  );
}

//: Which tab is actually showing, asked of the markup rather than of
//: `localStorage`. `switchTab` writes `activeTab` (app.js), so the two agree
//: most of the time, but "most of the time" is the wrong standard for the
//: guard that decides whether the tour navigates at all: a restore, a history
//: step or a tab entered before the key was written all leave the stored name
//: and the painted tab disagreeing, and a tour that trusts the key then skips
//: the switch and points its card at a control on a page nobody is looking at.
//: The pressed tab button is the page you can see.
function tourActiveTab() {
  const pressed = document.querySelector('#tab-bar [role="tab"].active');
  return pressed?.dataset?.tab || prefs.get("activeTab", null) || "";
}

//: A tab switch is not finished when `switchTab` resolves. The tab's own
//: content is loaded after it (notes, the library, the graph all fetch), and
//: for a beat the element this step names is in the DOM at zero height. The
//: old code measured once, two frames after the switch, found nothing to point
//: at and **dropped the step** (`tourShow` splices it out): on a fast empty
//: notebook every step survived, which is why this was never seen here, and on
//: a real one the steps that live inside a tab are exactly the ones that go.
//: From outside that is the owner's report, "it doesnt automatically switch
//: pages on different steps": the tour appears to stay where it was, because
//: the steps that would have moved it have quietly stopped existing.
//:
//: So a step that navigated waits for its element, up to TOUR_WAIT_MS, and
//: only a target that never arrives costs its step. The wait is per frame
//: rather than on a timer: a frame is when layout has settled, and a target
//: that is ready in one frame costs one frame.
//:
//: **Only a step that navigated waits the long wait.** A step naming a
//: control that is always on the page (the tab bar, the status bar, the gear)
//: has nothing on its way: if it is not laid out now a responsive rule dropped
//: it at this width, and `openTour` has already left such a step out. It still
//: gets TOUR_SETTLE_MS, for the overlay the tour has just closed to leave.
const TOUR_WAIT_MS = 1500;

//: **The one switch for every door into the tour** (the welcome's last slide,
//: the replay strip in Settings, the offer toast, About's button). It was
//: turned off on 2026-09-21 (the owner: "disable the start the tour button so
//: the user cant press it until we enable it again when the guided tour isnt
//: broken") and back on on 2026-09-23, once every step of every section was
//: walked at 1440x900, 1184x760 and 390x844 by `scratchpad/ui-sweeps/tour.js`
//: with the overlays, the phone and the resize cases that had been breaking
//: it. Turning it off again is this line and nothing else.
const TOUR_ENABLED = true;

//: A step that did not navigate still gets a short wait, because the tour
//: closes whatever was over the page before every step (`tourClearTheWay`),
//: and a sheet or a palette on its way out takes a frame or two to leave.
const TOUR_SETTLE_MS = 400;

//: Waits for the step's control to be laid out **and to have stopped
//: moving**: the same box on two frames running. A tab that has just been
//: switched to lays itself out over several frames (the notes list arrives,
//: the capture box grows to its text), and a card placed against the first
//: of those boxes points at where the control was a frame ago. Answers the
//: resolved `{ el, alt }` (see `tourResolve`) whether or not it got there;
//: the caller decides what an element that never settled costs.
async function tourWaitForTarget(step) {
  const navigated = Boolean(step.tab || step.notes || step.settings);
  const deadline = Date.now() + (navigated ? TOUR_WAIT_MS : TOUR_SETTLE_MS);
  let last = "";
  for (;;) {
    const found = tourResolve(step);
    // Before the visibility test: a hover-only control is not visible until
    // its card is revealed, and would otherwise time out and be dropped.
    tourReveal(found.el);
    if (tourVisible(found.el)) {
      const box = found.el.getBoundingClientRect();
      const key = [box.left, box.top, box.width, box.height].map(Math.round).join(",");
      if (key === last) return found;
      last = key;
    } else {
      last = "";
    }
    if (Date.now() >= deadline) return found;
    await tourFrame();
  }
}

//: **Everything the app can have open over the page, closed** (the owner,
//: 2026-09-21: "the tour should automatically navigate the user and open or
//: close the appropriate tabs and popups for the user"). Each close is
//: guarded by its own "is it open" test and by `typeof`, because several of
//: these closers do more than hide (the settings modal and the palette hand
//: focus back to whatever opened them, the notifications panel marks what it
//: showed as read), and running them when nothing is open would move focus
//: or state for no reason.
//:
//: Measured before this existed, one tour per overlay, basics section at
//: 1440x900: with the Atlas guide, the command palette, the features browser
//: or the shortcut sheet open, every step's target was under the overlay
//: (`elementFromPoint` at its centre answered the overlay, 4 of 4 steps each),
//: so the hole in the dim showed the overlay rather than the control.
//:
//: `step` is the step about to be shown, or nothing when the tour is opening.
//: The one overlay a step may ask to keep is Settings: its own section's
//: steps point at controls inside the modal, so closing it before each of
//: them would close the very thing the card is describing.
function tourClearTheWay(step) {
  const shown = (id) => {
    const el = document.getElementById(id);
    return Boolean(el) && !el.classList.contains("hidden");
  };
  const call = (name) => {
    if (typeof window[name] === "function") window[name]();
  };
  const keepSettings = Boolean(step && step.settings);
  if (!keepSettings && settingsModalOpen()) {
    call("closeSettingsModal");
  }
  if (shown("palette-overlay")) call("closePalette");
  if (shown("features-overlay")) call("closeFeatures");
  if (shown("shortcuts-overlay")) call("closeShortcuts");
  if (shown("notif-panel")) call("closeNotifications");
  // The agent's palette has no closer of its own; hiding it is what its own
  // Escape and backdrop handlers do (app.js, `toggleAgentPalette`).
  if (shown("command-palette-overlay")) {
    document.getElementById("command-palette-overlay").classList.add("hidden");
  }
  call("closeActionMenus");
  call("closeFinder");
  // Every `openSheet` sheet (the Atlas guide, More on a phone, the action
  // sheets) closes through its own X, which runs its `onClose` and hands
  // focus back; removing the element would skip both. Topmost first.
  for (const sheet of [...document.querySelectorAll(".sheet-overlay")].reverse()) {
    sheet.querySelector(".sheet-close")?.click();
  }
  // The docks' `<details>` menus (Filter, the kebabs): an open one hangs over
  // the page below its dock, which is where the next step's control often is.
  for (const menu of document.querySelectorAll("details.dock-menu[open], details.doc-dock-menu[open]")) {
    menu.open = false;
  }
}

//: Getting the app to the place where this step's element is on screen. Both
//: calls are guarded rather than assumed: they live in app.js, which is loaded
//: before this file, and a page served without it should fail loudly there
//: rather than quietly here.
async function tourNavigate(step) {
  //: **The tour drives the app, including getting out of the way of itself**
  //: (the owner, 2026-09-21: "the tour should automatically navigate the user
  //: and open or close the appropriate tabs and popups for the user"). Starting
  //: it from Settings, Help is the case that made this necessary: the modal
  //: stays over the page, so every target behind it measures as not visible,
  //: every step is dropped, and the run empties. Nothing else in the app can
  //: be trusted to have closed either, so the tour closes what is open before
  //: it navigates, rather than pointing at a control under a sheet.
  tourClearTheWay(step);
  if (step.settings) {
    await tourOpenSettings(step.settings);
    tourOpenFoldsAround(step);
    await tourFrame();
    return;
  }
  if (step.tab) {
    if (tourActiveTab() !== step.tab) await switchTab(step.tab);
  }
  if (step.notes) showNotesSection(step.notes);
  if (step.library) tourLibraryView(step.library);
  if (step.wb) await tourWhiteboard(step.wb);
  await tourFrame();
}

//: A Library sub-tab, pressed only when it is not already the pressed one:
//: pressing the whiteboard's sub-tab while a board is open would be a
//: navigation of its own (it records history and can leave the canvas).
function tourLibraryView(target) {
  const button = document.querySelector(`#library-subtabs button[data-target="${target}"]:not([data-media-kind])`);
  if (button && button.getAttribute("aria-selected") !== "true") button.click();
}

//: The Boards & maps sub-tab has two faces, the list of boards and a board
//: open on its canvas, and a step names which one it needs. **The tour never
//: makes a board.** "board" opens the newest free canvas there is, falling
//: back to the default board every notebook already has (`id: null`, the
//: one the gallery pins first); "map" opens the newest mind map, and its
//: steps carry `need: "map"`, so a notebook with no map never reaches this
//: with nothing to open: it is shown New mind map and told what that makes.
async function tourWhiteboard(face) {
  const canvas = document.getElementById("wb-canvas-view");
  const onCanvas = Boolean(canvas) && !canvas.classList.contains("hidden");
  if (face === "landing") {
    if (onCanvas && typeof wbShowBoardsLanding === "function") wbShowBoardsLanding();
    return;
  }
  const context = tourRun?.context || {};
  const id = face === "map" ? context.map : context.board;
  if (face === "map" && id == null) return;
  if (onCanvas && (window.currentBoardId ?? null) === (id ?? null)) return;
  await openWhiteboardBoard(id ?? null);
}

//: **A settings step opens the fold its control is folded into** (INBOX 426
//: y). Appearance's groups are `details.settings-fold`s, closed by default
//: except Themes, and a control in a closed one has no box, so the
//: companion step was dropped from every run on a fresh notebook and shown
//: only where the reader happened to have opened "Atlas and faces". The
//: folds the tour opens are closed again when it ends (`tourClose`), so
//: the reader's own choice of what is open is what they come back to.
function tourOpenFoldsAround(step) {
  let el = null;
  try {
    el = document.querySelector(step.target);
  } catch {
    return;
  }
  for (let fold = el?.closest("details:not([open])"); fold; fold = fold.parentElement?.closest("details:not([open])")) {
    fold.open = true;
    if (tourRun) (tourRun.openedFolds ||= []).push(fold);
  }
}

//: Settings is a modal rather than a tab, so its steps open it (once) and
//: move between its sections, and `tourClearTheWay` leaves it up for them.
async function tourOpenSettings(section) {
  const open =
    typeof settingsModalOpen === "function"
      ? settingsModalOpen()
      : !document.getElementById("settings-modal")?.classList.contains("hidden");
  if (!open) {
    if (tourRun) tourRun.openedSettings = true;
    await openSettingsModal(section);
  } else if (typeof showSettingsSection === "function") {
    showSettingsSection(section);
  }
}

//: What the notebook has, asked once when a section that depends on it
//: starts: the newest mind map and the newest free board, from the one board
//: index every surface shares (`loadMapBoardIndex`, app.js). Only read, never
//: written: a failure here answers "none", which costs the map's steps and
//: nothing else.
async function tourContext() {
  let rows = [];
  try {
    const index = typeof loadMapBoardIndex === "function" ? await loadMapBoardIndex(true) : null;
    rows = index ? [...index.values()] : [];
  } catch (error) {
    rows = [];
  }
  const newest = (list) => list.reduce((best, row) => (!best || row.id > best.id ? row : best), null);
  return {
    map: newest(rows.filter((row) => row.type === "map"))?.id ?? null,
    board: newest(rows.filter((row) => row.type !== "map"))?.id ?? null,
  };
}

//: The `need` names a step can carry, each a question about this notebook.
//: A step whose answer is no is taken out of its section before the
//: section's first card is drawn, so the count is right from that card on.
const TOUR_NEEDS = {
  map: (context) => context.map != null,
  entries: () => typeof allEntries !== "undefined" && Array.isArray(allEntries) && allEntries.length > 0,
};

//: Run once per section, as the walk enters it: fetches what the section's
//: `need`s ask about and drops the steps that cannot be shown, keeping the
//: walk on the same step (or the nearest one in the direction it was going).
async function tourPrepareSection(run, sectionId) {
  run.prepared.add(sectionId);
  const asks = run.steps.some((step) => step.sectionId === sectionId && (step.need || step.wb));
  if (!asks) return;
  run.context = await tourContext();
  const keep = run.steps.map(
    (step) => step.sectionId !== sectionId || !step.need || Boolean(TOUR_NEEDS[step.need]?.(run.context))
  );
  let at = run.index;
  if (run.direction < 0) {
    while (at >= 0 && !keep[at]) at -= 1;
  } else {
    while (at < keep.length && !keep[at]) at += 1;
  }
  run.steps = run.steps.filter((_, i) => keep[i]);
  if (at < 0) {
    run.index = 0;
    run.direction = 1;
  } else {
    run.index = keep.slice(0, at).filter(Boolean).length;
  }
}

//: **The tour never leaves a dim with no card** (the owner, 2026-09-23 night,
//: from the desktop window: "I pressed next on the first panel of the guided
//: tour, and it dissappeared while keeping the page dimmed and pushed the top
//: bar down by a couple pixels", started from Settings, help). Not reproduced
//: in a headless run at 1333, 1440, 1600 or 2000 wide, which says the fault is
//: in something this machine does not have, not that there is no fault. So
//: whatever the walk runs into, the outcome is bounded: an exception becomes
//: the centred card, a card that ends up off the window or behind something
//: is re-centred, and both say what happened in Settings, Logs (console
//: output is captured there), so the next report carries its own numbers.
async function tourStep() {
  const run = tourRun;
  if (!run) return;
  tourPinShell();
  try {
    await tourShow();
  } catch (error) {
    console.warn("Tour: a step failed, showing the card centred", error);
    if (tourRun !== run) return;
    tourStrand(run);
  }
  if (tourRun === run) tourVerifyCard();
}

//: The centred card for a step with nothing it can point at, the same state
//: the last-step case below reaches (INBOX 315), reachable from anywhere.
function tourStrand(run) {
  run.el = null;
  run.step = run.step || run.steps[Math.max(0, Math.min(run.index, run.steps.length - 1))];
  run.alt = false;
  run.stranded = true;
  document.getElementById("tour-card")?.removeAttribute("aria-busy");
  tourRender();
  tourPosition();
  document.getElementById("tour-next")?.focus();
}

//: The app is a fixed shell: the tabs scroll inside themselves and the page
//: never does (`body { overflow: hidden }`). Hidden is not unscrollable,
//: though: a focus or a scroll aimed at an element near an edge can still
//: move the document a few pixels, and every fixed-position box the tour
//: measured moves with it. "The top bar pushed down by a couple pixels" is
//: that movement. Pinned back to the top before each step.
function tourPinShell() {
  for (const el of [document.scrollingElement, document.documentElement, document.body]) {
    if (el && (el.scrollTop || el.scrollLeft)) {
      console.warn(`Tour: the page itself was scrolled (${el.tagName} ${el.scrollLeft},${el.scrollTop}); put back`);
      el.scrollTop = 0;
      el.scrollLeft = 0;
    }
  }
}

//: Placed is not shown: the card must be inside the window and be the thing
//: drawn at its own centre. When it is not, it goes to the middle, where
//: nothing but the tour's own dim can be.
function tourVerifyCard(tries = 0) {
  const card = document.getElementById("tour-card");
  if (!card || card.classList.contains("hidden") || card.getAttribute("aria-busy") === "true") return;
  const box = card.getBoundingClientRect();
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const inside = box.width > 0 && box.height > 0 && box.left >= -1 && box.top >= -1 &&
    box.right <= vw + 1 && box.bottom <= vh + 1;
  // A toast over the card is not the card lost (the toast box stacks above
  // everything, the tour included, and is gone in seconds): measured, the
  // Finish toast of one run re-centred the phone's docked card of the next.
  const hit =
    inside &&
    document
      .elementsFromPoint(box.left + box.width / 2, box.top + box.height / 2)
      .find((node) => !node.closest("#toast-box"));
  if (inside && hit && card.contains(hit)) return;
  //: **The root answering is not an answer.** While a view transition runs
  //: (the Library's list re-renders through `startViewTransition`,
  //: library.js), hit testing lands on its pseudo-element tree and
  //: `elementsFromPoint` returns `<html>` for every point in the window,
  //: the tour's own card included. Measured at 390: the Library, Boards and
  //: Mind maps cards were re-centred for being "not on screen" while sitting
  //: exactly where they were placed. Asked again once the transition has
  //: had time to finish, and only a real miss moves the card.
  if (inside && hit === document.documentElement && tries < 6) {
    const run = tourRun;
    setTimeout(() => {
      if (tourRun === run) tourVerifyCard(tries + 1);
    }, 150);
    return;
  }
  console.warn(
    `Tour: the card was not on screen (box ${Math.round(box.left)},${Math.round(box.top)} ` +
      `${Math.round(box.width)}x${Math.round(box.height)} in ${vw}x${vh}, ` +
      `front ${hit ? hit.id || hit.className || hit.tagName : "none"}); centred`
  );
  const size = card.getBoundingClientRect();
  card.dataset.side = "centre";
  tourPlaceFixed(
    card,
    tourClamp((vw - size.width) / 2, TOUR_EDGE, Math.max(TOUR_EDGE, vw - TOUR_EDGE - size.width)),
    tourClamp((vh - size.height) / 2, TOUR_EDGE, Math.max(TOUR_EDGE, vh - TOUR_EDGE - size.height))
  );
}

//: A card's actions show on hover only, so a step pointing at one framed an
//: empty square (INBOX 745 d). The card holding the target takes `tour-reveal`,
//: which the hover rules also match, for as long as the step shows.
function tourReveal(el) {
  for (const card of document.querySelectorAll(".tour-reveal")) card.classList.remove("tour-reveal");
  el?.closest?.(".library-card")?.classList.add("tour-reveal");
}

async function tourShow() {
  const run = tourRun;
  tourReveal(null);
  //: **One walk at a time.** Next pressed twice while a tab is loading used to
  //: start a second walk over the same run while the first was still
  //: awaiting, and the two then spliced and rendered over each other. Each
  //: walk takes a ticket and stands down as soon as a newer one exists.
  run.seq = (run.seq || 0) + 1;
  const seq = run.seq;
  const stale = () => tourRun !== run || run.seq !== seq;
  document.getElementById("tour-card")?.setAttribute("aria-busy", "true");
  while (run.index >= 0 && run.index < run.steps.length) {
    const step = run.steps[run.index];
    //: A section's `need`s are settled as the walk enters it, before its
    //: first card, so the count that card shows is the count it keeps.
    if (!run.prepared.has(step.sectionId)) {
      await tourPrepareSection(run, step.sectionId);
      if (stale()) return;
      continue;
    }
    await tourNavigate(step);
    // The awaits above give the tour time to have been skipped, or restarted
    // from Settings, while a tab was loading. Whatever happens next belongs to
    // whichever run is current, not to this one.
    if (stale()) return;
    const { el, alt } = await tourWaitForTarget(step);
    if (stale()) return;
    //: Brought into view first, then judged: a control below the fold of a
    //: scrolling panel is a step worth showing once the panel has been
    //: scrolled to it, and only a control that is still not in the window
    //: after that has nothing to point at.
    if (tourVisible(el)) {
      tourBringIntoView(el);
      //: **Judged after the scroll, not during it** (INBOX 315). Bringing a
      //: control into view moves a scroller, and the box read in the same
      //: task is the box it had before the move. A step measured there looks
      //: off screen when it is about to be on it, and an off-screen step is
      //: dropped, so a single mistimed measurement could eat the rest of the
      //: run one step at a time. One frame is what the move needs.
      await tourFrame();
      if (stale()) return;
    }
    if (!tourUsable(el)) {
      // A step with nothing to point at is dropped from this run, rather than
      // shown empty or left pointing at the corner of the window.
      //
      //: **Except the last one, which would empty the run in silence**
      //: (INBOX 315: the owner pressed Next on the first step and the tour
      //: vanished, leaving the tab it had navigated to with no card and no
      //: dim). Falling out of this loop calls `tourClose`, which is right
      //: when somebody has reached the end and wrong when the end reached
      //: them: a tour that disappears mid-gesture reads as the whole feature
      //: breaking, which is exactly how it was reported. So the run keeps its
      //: last step and says what happened, with the card centred, rather than
      //: closing as though the tour were over.
      if (run.steps.length <= 1) {
        run.el = null;
        run.step = step;
        run.alt = false;
        run.stranded = true;
        document.getElementById("tour-card")?.removeAttribute("aria-busy");
        tourRender();
        tourPosition();
        document.getElementById("tour-next")?.focus();
        return;
      }
      run.steps.splice(run.index, 1);
      if (run.direction < 0) run.index -= 1;
      if (run.index < 0) {
        run.index = 0;
        run.direction = 1;
      }
      continue;
    }
    run.stranded = false;
    run.el = el;
    run.alt = alt;
    run.step = step;
    document.getElementById("tour-card")?.removeAttribute("aria-busy");
    tourRender();
    tourPosition();
    run.watchKey = "";
    tourWatch();
    // Focus lands inside the card, on the control that moves the tour on, so
    // Enter and Space do the obvious thing the moment a card appears. The card
    // itself is the `aria-modal` dialog, so app.js's Tab trap keeps focus in
    // here until the tour ends.
    document.getElementById("tour-next").focus();
    return;
  }
  tourClose(true);
}

// --- the run ----------------------------------------------------------------

//: The steps a run plays: the named section **and every section after it**,
//: in table order, or all of them. A run started from one section's button
//: chains on to the rest exactly as the whole tour does (the owner,
//: 2026-09-23), and each section's last card is where it can be finished.
function tourStepsFor(sectionId) {
  const steps = [];
  const from = sectionId ? TOUR_SECTIONS.findIndex((section) => section.id === sectionId) : 0;
  if (from < 0) return steps;
  for (const section of TOUR_SECTIONS.slice(from)) {
    for (const step of section.steps) {
      if (step.media && !window.matchMedia(step.media).matches) continue;
      // Present in the markup at all is the cheap half of the test and it is
      // stable (a control in a tab that is not showing is still in the DOM);
      // whether it can actually be seen is decided in `tourShow`, once the
      // tour has navigated to it. A step inside a tab is let through
      // unasked, because what it names can be drawn by the tab itself (a
      // library card's menu exists only once the library has been listed).
      if (step.tab || step.settings || document.querySelector(step.target)) {
        steps.push({ ...step, sectionId: section.id, sectionLabel: section.label });
      }
    }
  }
  return steps;
}

function openTour(sectionId) {
  // Whatever is open over the page is closed before anything is judged, so
  // the chrome steps below are judged against the page and not the overlay.
  tourClearTheWay();
  //: **A step that can never be shown at this size is left out before the
  //: count is written, not dropped in the middle of the run.** The chrome
  //: steps (no tab to switch to) point at controls that are always on the
  //: page when they exist at all, so whether they are laid out now is the
  //: whole answer: the status bar's Commands is not drawn on a phone and never
  //: will be during this run. Dropping it only when the walk reached it made
  //: the counter read "10 of 15", then "11 of 14", which reads as the tour
  //: losing its place. Steps inside a tab are still judged when reached,
  //: because their tab is not showing yet.
  const steps = tourStepsFor(sectionId || null).filter(
    (step) => step.settings || step.tab || step.notes || tourVisible(tourResolve(step).el)
  );
  if (!steps.length) {
    if (typeof toast === "function") {
      toast("There is nothing to show in that part of the tour.");
    }
    document.dispatchEvent(new Event("tour-closed"));
    return;
  }
  tourRun = {
    steps,
    index: 0,
    direction: 1,
    el: null,
    step: null,
    // The sections whose `need`s have been settled (`tourPrepareSection`),
    // and what the notebook had when they were.
    prepared: new Set(),
    context: {},
    // Where the focus came from, so it can be handed back exactly there when
    // the tour ends, whether it ends at the last card, at Skip or at Escape.
    returnFocus: document.activeElement,
  };
  //: **Hidden until it has a place** (INBOX 745 (d): "a wierd blank tour
  //: panel showed in the top left corner for a couple seconds then it righted
  //: itself"). The card was shown with the layers, empty and at its last
  //: position, while the first step's tab and lazy code loaded. It keeps its
  //: box (visibility, not display, so it can be measured) and is shown by
  //: `tourPlaceFixed` once the step's text is in it and it has been placed.
  //: Inline rather than a class: the boot CSS budget (test_boot_budget.py).
  document.getElementById("tour-card").style.visibility = "hidden";
  for (const id of TOUR_LAYERS) document.getElementById(id).classList.remove("hidden");
  tourStep();
}

function tourClose(finished) {
  if (!tourRun) return;
  const run = tourRun;
  tourRun = null;
  tourReveal(null);
  for (const id of TOUR_LAYERS) document.getElementById(id).classList.add("hidden");
  //: The first-run queue's cue that the screen is the next surface's.
  document.dispatchEvent(new Event("tour-closed"));
  // Finished or skipped, the answer is the same: this person has been offered
  // the tour and nothing may offer it to them again by itself. Kept beside
  // `onboardingDone`, and mirrored to the notebook's own preferences by
  // app.js's MIRRORED_UI_EXTRAS, because a desktop shell that loses its
  // profile is exactly how "onboarding shows every time" was reported.
  try {
    prefs.set("tourDone", "1");
  } catch (error) {
    // A browser with storage blocked still gets the tour, it just cannot
    // remember that it did. Refusing to run would be the worse failure.
  }
  //: Settings, if the tour opened it, is closed with the tour: it was opened
  //: to be pointed at, and left up it covers the page the focus goes back to.
  if (run.openedSettings && settingsModalOpen()) {
    if (typeof closeSettingsModal === "function") closeSettingsModal();
  }
  //: And the folds it opened to reach a control are folded again.
  for (const fold of run.openedFolds || []) fold.open = false;
  run.returnFocus?.focus?.();
  if (finished) {
    toast("That is the tour. Settings, help and guide has it again whenever you want it.");
  }
}

function tourNext() {
  if (!tourRun) return;
  if (tourRun.index >= tourRun.steps.length - 1) {
    tourClose(true);
    return;
  }
  tourRun.index += 1;
  tourRun.direction = 1;
  tourStep();
}

function tourBack() {
  if (!tourRun || tourRun.index === 0) return;
  tourRun.index -= 1;
  tourRun.direction = -1;
  tourStep();
}

// --- wiring -----------------------------------------------------------------

document.getElementById("tour-next").addEventListener("click", tourNext);
document.getElementById("tour-back").addEventListener("click", tourBack);
//: Skip mid-section, Finish at a section's last card (`tourRender` relabels
//: it): the same way out, but a Finish is a tour completed, with its toast.
document.getElementById("tour-skip").addEventListener("click", () =>
  tourClose(Boolean(tourRun && tourRun.atSectionEnd))
);
//: The way out, in the corner of the card where every panel in this app keeps
//: it. Skip was already there and does the same thing, but the owner did not
//: read it as the exit: "it has no visible way to exit or quit it like a
//: button or smth so I had to guess by pressing the escape button". Skip reads
//: as "not this part" beside Back and Next; an X in the head reads as "close
//: this". Both stay, because they are the same act reached two ways, and
//: Escape is the third.
document.getElementById("tour-close").addEventListener("click", () => tourClose(false));

//: Captured, and it stops the event: the arrow keys move between tabs in this
//: app and Escape closes whatever is open, and both would fire underneath a
//: tour that is using them for its own steps. Tab is deliberately NOT handled
//: here: the card is a `[role="dialog"][aria-modal="true"]`, which is what
//: app.js's own trap looks for, so focus is already held inside it by the
//: app's one implementation of that rule rather than by a second one.
document.addEventListener(
  "keydown",
  (event) => {
    if (!tourRun) return;
    const key = event.key;
    //: **The hole is the page, so typing in it has to be typing.** The dim
    //: leaves the highlighted control pressable (the "Type anything" step
    //: lights the capture box so it can be tried), and before this the arrow
    //: keys inside it moved the tour instead of the caret and Enter took the
    //: tour a step on instead of starting a new line. Keys aimed at a field
    //: outside the card are the field's; Escape still ends the tour.
    const target = event.target;
    const typing =
      target instanceof Element &&
      !target.closest("#tour-card") &&
      (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
    if (typing && key !== "Escape") return;
    if (key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      tourClose(false);
    } else if (key === "ArrowRight" || key === "ArrowDown") {
      event.preventDefault();
      event.stopPropagation();
      tourNext();
    } else if (key === "ArrowLeft" || key === "ArrowUp") {
      event.preventDefault();
      event.stopPropagation();
      tourBack();
    } else if (key === "Enter" && !(event.target instanceof HTMLButtonElement)) {
      // A focused button already turns Enter into a click of its own; this is
      // for the case where focus is on the card rather than on a control.
      event.preventDefault();
      tourNext();
    }
  },
  true
);

//: A window resized, or a surface scrolled under a step, moves the control the
//: card is pointing at, and a card left where it was is then pointing at
//: nothing. Captured on scroll so it hears scrolling inside a panel too, which
//: does not bubble.
function tourReflow() {
  if (!tourRun || !tourRun.el || !tourRun.step) return;
  //: A resize can carry the window across the phone breakpoint, where a step
  //: with an `or` control moves between the two (the gear and More). Asked
  //: again here, so the card follows the control that is showing rather than
  //: dropping the step because the one it started on went away.
  const found = tourResolve(tourRun.step);
  if (found.el !== tourRun.el && tourVisible(found.el)) {
    tourRun.el = found.el;
    tourRun.alt = found.alt;
    tourRender();
  }
  if (!tourVisible(tourRun.el) || !tourOnScreen(tourRun.el)) {
    // The control went away under the tour (a window narrowed past the width
    // that shows it, a panel scrolled it out of the window). The step goes
    // with it rather than the card hanging on beside a rectangle that is not
    // there any more.
    tourStep();
    return;
  }
  tourPosition();
}
window.addEventListener("resize", tourReflow);
window.addEventListener("scroll", tourReflow, true);

//: Settings, help and guide: one filled button for the whole tour, then one
//: row per section, built from TOUR_SECTIONS so a section added to that
//: table arrives here on its own. **A row, not a wall** (INBOX 804, the
//: owner: fourteen tinted, bordered buttons in one block): each section is a
//: quiet `button.tour-row`, its name over its one-line blurb, in a list, so a
//: section says what it covers before it is pressed. The settings modal is
//: closed first, because the tour points at controls the modal is covering.
function renderTourReplay() {
  const box = document.getElementById("tour-replay-buttons");
  if (!box) return;
  box.replaceChildren();
  const start = (sectionId) => {
    if (!TOUR_ENABLED) return;
    if (typeof closeSettingsModal === "function") closeSettingsModal();
    // On the next frame, not in the same one as the close: the first step's
    // rectangle is measured against the page the modal was covering.
    requestAnimationFrame(() => openTour(sectionId));
  };
  const all = document.getElementById("tour-start-btn");
  if (all && !all.dataset.wired) {
    all.dataset.wired = "1";
    all.addEventListener("click", () => start(null));
  }
  if (all && !TOUR_ENABLED) tourDisable(all);
  for (const section of TOUR_SECTIONS) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small tour-row";
    const name = document.createElement("span");
    name.className = "tour-row-name";
    name.textContent = section.label;
    const blurb = document.createElement("span");
    blurb.className = "tour-row-blurb";
    blurb.textContent = section.blurb;
    button.append(name, blurb);
    button.addEventListener("click", () => start(section.id));
    if (!TOUR_ENABLED) tourDisable(button);
    li.append(button);
    box.appendChild(li);
  }
}

//: A lazy bundle now (`tour`, app.js): `onDomReady` runs it at once when the
//: file arrives after the page has loaded, which is every time.
onDomReady(renderTourReplay);

//: One place for the words, so every disabled door says the same thing and
//: says why rather than just refusing.
function tourDisable(button) {
  button.disabled = true;
  button.title = "The guided tour is being fixed and is turned off for now.";
  button.setAttribute("aria-label", button.title);
}
