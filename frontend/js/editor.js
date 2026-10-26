// === EDITOR LAYER ===========================================================
// The "/" menu, the block frames it inserts, and the caret-anchored popup both
// it and the document's own [[ autocomplete are drawn with.
//
// Why this is a separate file rather than more of app.js: app.js is ~27k lines
// and ROADMAP Tier 4 makes the case, correctly, that a big-bang split must
// not share a diff with live edits to the same code. New code in a new file
// moves the line the right way without that risk, the same way graph.js and
// whiteboard.js already did. Loaded after app.js (see index.html), so every
// global it leans on, $, apiJson, allEntries, MD_ACTIONS, markDocDirty,
// renderDocPreview, BUILTIN_TEMPLATES, prefsCache, noteLabel, toast, is
// already defined.
//
// Two design decisions worth stating up front, because both were the cheap
// option *and* the correct one:
//
// 1. **One delegated listener, not one per textarea.** Every handler here is
//    bound once on `document` and dispatches on `event.target`. Binding
//    per-element would have meant a third `input` listener on `entry-content`
//    (it already legitimately has two, see ALLOWED_DOUBLES in
//    tests/test_frontend_handlers.py) and a fresh entry in that allow-list for
//    every surface added later. Delegation is how "one behaviour across many
//    inputs" is supposed to be written, and it means a new editor surface is
//    one line in EDITOR_SURFACES rather than a wiring change.
//
// 2. **Callouts are `> [!kind] Title`, not a custom fence.** That syntax
//    degrades to an ordinary blockquote in any other markdown reader, 
//    GitHub, Obsidian and Typora all already understand it. A custom fence
//    would render as literal junk the moment a note left this app, and
//    "your notes stay portable" is the whole premise of a local-first
//    notebook that stores plain markdown.

// Which textareas get the "/" menu, and what each one is allowed to do. The
// value is the context: an AI command that acts on a document has nowhere to
// run inside the capture box, so commands declare which contexts they suit
// and the menu filters rather than offering something that would no-op.
const EDITOR_SURFACES = {
  "entry-content": "note",
  //: The note *edit* form (note-edit-panels.js's `renderEditForm`), which had none of this
  //: until now: the one editing surface in the app with no "/" menu, no
  //: toolbar and no selection bar. One id, because `editingId` allows exactly
  //: one open edit form at a time.
  "entry-edit-content": "note",
  "doc-content": "document",
  //: The chat composer. Asked for as part of "the chat interface needs
  //: bugfixing and more utility and features" -- "/" did nothing there, the
  //: one text box in the app where a slash menu is the *expected* affordance
  //: (every chat product the user compared this to has one). Its commands are
  //: chat's own: attach, web, plan, skills, mode. See `chatCommands`.
  "chat-input": "chat",
  //: The Agent popup's box (INBOX 1309, the owner: "the popup agent doesnt
  //: have the / command popup like chat"): the same commands, sent here.
  "command-palette-input": "agent",
  //: The skill editor's steps box (DOCUMENTS_PLAN Phase 8c). The plan gives
  //: it the "/" menu and nothing else: it is a list of instructions, not note
  //: text, so it stays a plain textarea with no Live view and no engine, and
  //: `tests/test_note_surface.py`'s `NOT_NOTE_TEXT` says so. Its own context,
  //: because the note commands are all wrong here; see `skillCommands`.
  "skill-steps": "skill",
};

//: **What context an editing surface is.**
//:
//: `EDITOR_SURFACES` is an id-to-context table by construction, and for most
//: of this file's life the hard case was the document's Live view, which was
//: one textarea per paragraph with a generated id: gating on
//: `textarea.id in EDITOR_SURFACES` gave those blocks no "/" menu at all and
//: told them the document AI commands did not apply. Neither failure logged
//: or threw, which is this repo's "a policy silently refusing the work"
//: shape. DOCUMENTS_PLAN Phase 2 made Live and Source one editor, so the
//: generated ids are gone; the surface reports `doc-content` in every view.
//:
//: Returns null, not "note", for anything that is not an editing surface, so
//: callers can tell "not a surface" from "a note".
function editorSurfaceKind(box) {
  //: A surface, an element, or a node inside CodeMirror. The last of those is
  //: why this can no longer be a `instanceof HTMLTextAreaElement` check:
  //: CodeMirror's editable is a `div`, and gating on the textarea would have
  //: silently taken the "/" menu, the selection bar and the inline AI away
  //: from the document editor the moment the engine landed under it. Same
  //: "policy silently refusing the work" shape this file's own comment
  //: records for the Live view.
  const surface = editorSurfaceFor(box);
  if (!surface) return null;
  return surface.id in EDITOR_SURFACES ? EDITOR_SURFACES[surface.id] : null;
}

//: Whatever this is, as a surface, or null. `asSurface` lives in documents.js
//: beside the adapter itself.
//:
//: **That file is not always there, and the guard below used to say it always
//: was.** Its own comment read "which cannot happen in the browser (the script
//: order is fixed)", and that stopped being true the moment documents.js
//: joined the Library's lazy bundle (`LAZY_MODULES`, app.js): index.html loads
//: app.js, editor.js, dashboard.js, settings.js and tour.js, and nothing else
//: until a tab asks for it. So on every fresh load, until the person happened
//: to open Library or Documents, `asSurface` was undefined, this returned
//: null, and `editorHandleInput` bailed on its first line. Measured on the
//: branch head, 2026-09-21: typing "/" in the note capture box gave 0 menu
//: rows and `editorMenuState.open === false`. The same for the note edit box,
//: the chat composer and the skill steps box, which is four of the five
//: surfaces the feature exists for. CLAUDE.md section 6's fourth shape, a
//: policy silently refusing the work, with a comment asserting it could not.
//:
//: The fix is `editorEnsureSurfaceModule` below rather than a second copy of
//: the adapter here: `textareaSurface` hangs off `docSurfaceCache`,
//: `docReplaceRange` and `docMirrorPoint`, and a fork of it would drift.
function editorSurfaceFor(box) {
  if (!box) return null;
  if (box.kind === "textarea" || box.kind === "codemirror") return box;
  //: A board's text box or map topic while it is being typed in carries its
  //: own surface (whiteboard.js `wbEditableSurface`): it is a contenteditable,
  //: which no adapter in documents.js speaks.
  if (box.wbEditorSurface) return box.wbEditorSurface;
  if (typeof asSurface !== "function") {
    editorEnsureSurfaceModule(box);
    return null;
  }
  return asSurface(box);
}

//: Fetch the bundle that carries the surface adapters, once, and pick the
//: interrupted work back up when it lands.
//:
//: `retry` is what makes a fast typist's first "/" still open a menu: the
//: keystroke that found no adapter is replayed against the surface once there
//: is one, so the menu opens a moment late rather than not at all. Without it
//: the first "/" of a session would always be the one that did nothing, which
//: is the worst possible one to lose: it is the keystroke somebody presses to
//: find out whether the feature exists.
let editorSurfaceModulePending = null;
function editorEnsureSurfaceModule(box) {
  if (typeof ensureModule !== "function") return;
  const el = box && box.nodeType === 1 ? box : null;
  if (!el || !(el.id in EDITOR_SURFACES)) return;
  if (!editorSurfaceModulePending) {
    editorSurfaceModulePending = ensureModule("library").catch(() => false);
  }
  editorSurfaceModulePending.then(() => {
    if (typeof asSurface !== "function") return;
    if (document.activeElement !== el) return;
    editorHandleInput(editorSurfaceFor(el));
  });
}

//: **The second route, and the affordance that says either exists.**
//: DOCUMENTS_PLAN 18c: the owner asked for these commands to be "discoverable
//: by the user", and until now the only way in was to already know that "/"
//: did something. Section 18's decision 5 forbids adding to the chrome (a
//: thirteenth button on a twelve-control toolbar teaches nothing), so this is
//: two things that cost no chrome at all:
//:
//: * Ctrl+/ opens the menu with an empty query, from anywhere in one of these
//:   surfaces. A route that is not "type a character into your own text" also
//:   answers the person who wants the list without leaving a stray slash
//:   behind if they change their mind.
//: * Every one of these surfaces says so in its own placeholder, which is the
//:   one piece of copy that is visible exactly while the box is empty and
//:   gone the moment it is not. The capture box already taught `[[` there;
//:   this is the same teaching in the same place.
//:
//: Recorded as a decision in DOCUMENTS_PLAN section 18 rather than taken
//: quietly, because 18c's own gate asked for "the visible route" and the
//: decision above rules out the obvious one.
const EDITOR_MENU_HINT = "Press / for blocks and commands";

//: The keystroke itself goes through `DEFAULT_SHORTCUTS`/`runShortcut`
//: (app.js) rather than through a listener of this file's own, for two
//: reasons. It is then rebindable like every other chord, and it appears in
//: the shortcuts cheat sheet, which is the third of decision 3's three ways a
//: command has to be findable. A second listener here would also fire
//: alongside app.js's chorded dispatcher and insert two slashes.
//:
//: Answers false when there is no editing surface focused, so the dispatcher
//: can fall through to whatever else wants the chord.
function editorOpenMenuByShortcut() {
  const surface = editorSurfaceFor(document.activeElement);
  if (!surface || !editorSurfaceKind(surface)) return false;
  //: The slash is written into the text, not faked: the menu filters on what
  //: follows it and closes when it is deleted, so both routes have to leave
  //: the surface in the same state, or Escape and Backspace would behave
  //: differently depending on how the menu was opened.
  surface.setRangeText("/", surface.selectionStart, surface.selectionEnd, "end");
  surface.dispatchEvent(new InputEvent("input", { bubbles: true, data: "/" }));
  return true;
}

//: The placeholder half. Applied from here rather than written into the
//: markup because one of the four surfaces (`entry-edit-content`) is built in
//: JS every time a note is opened, and a hint that three boxes carry and the
//: fourth does not is worse than none: it teaches that the feature is
//: per-box. Appended to whatever the box already says, once.
function editorHintPlaceholder(box) {
  if (!box || !(box.id in EDITOR_SURFACES)) return;
  //: **Not on the phone's short placeholder.** Below 600 the chat box's
  //: placeholder is cut to "Ask anything…" (`dockChatAttachments`, app.js)
  //: so that autogrow sizes an empty box to one line; the hint appended to
  //: it on focus made it three (measured at 390: "Ask anything… Press / for
  //: blocks and commands." over three lines, 90px of empty box). The
  //: `placeholderHome` it keeps already carries the hint, and comes back
  //: with the width.
  if (box.dataset.placeholderHome) return;
  const current = box.getAttribute("placeholder") || "";
  if (current.includes(EDITOR_MENU_HINT)) return;
  //: **A second line only where there is a second line to spare** (the owner,
  //: 2026-09-21: "the 'press / for blocks and commands' line in the empty chat
  //: bar raises the chat bar height a bit"). A composer that grows to fit its
  //: content measures the placeholder too, so a newline in it makes an empty
  //: box one row taller than the message it is waiting for. The note editor
  //: has the room and reads better with the hint under the prompt; the chat
  //: bar is one row by design, and there the hint joins the sentence.
  const tall = (Number(box.getAttribute("rows")) || 1) > 2;
  //: The joined hint is 492px of text: cut ("Press / for bl") in the box a 700px window leaves.
  if (!tall && innerWidth < 800) return;
  const joined = tall
    ? (current ? `${current}\n${EDITOR_MENU_HINT}.` : `${EDITOR_MENU_HINT}.`)
    : (current ? `${current}  ${EDITOR_MENU_HINT}.` : `${EDITOR_MENU_HINT}.`);
  box.setAttribute("placeholder", joined);
}

function editorHintAllPlaceholders() {
  for (const id of Object.keys(EDITOR_SURFACES)) editorHintPlaceholder(document.getElementById(id));
}

//: Twice: once at boot for the surfaces the markup ships, and once whenever a
//: surface takes focus, which covers the edit form built after boot.
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", editorHintAllPlaceholders);
} else {
  editorHintAllPlaceholders();
}
document.addEventListener("focusin", (event) => editorHintPlaceholder(event.target), true);

//: And warmed on focus, so the bundle is usually already there by the time
//: anything is typed. Focusing an editing surface is the earliest honest
//: signal that these commands are about to be wanted.
//:
//: **But not in the frame of the press.** Arriving on Chat focuses the
//: composer, and fetching the bundle there put 17 scripts (d3, documents.js,
//: the whiteboard files, about 2 MB) on the main thread in the window the
//: page itself is being drawn: the first long task of a first Chat visit
//: (`scratchpad/ui-sweeps/tabenter.js`, 192 ms of `documents.js` at 4x CPU).
//: It waits out the arrival and runs when the page is idle. A key that needs
//: the adapter before then still asks for the bundle itself
//: (`editorSurfaceFor`), so the first "/" is replayed, not lost.
const EDITOR_WARM_DELAY_MS = 2000;
const editorWarm = { timer: 0 };
function editorWarmSurfaceModule(el) {
  clearTimeout(editorWarm.timer);
  editorWarm.timer = setTimeout(() => {
    const run = () => {
      if (document.activeElement === el && typeof asSurface !== "function") editorEnsureSurfaceModule(el);
    };
    if (window.requestIdleCallback) requestIdleCallback(run, { timeout: 2000 });
    else run();
  }, EDITOR_WARM_DELAY_MS);
}
document.addEventListener(
  "focusin",
  (event) => {
    const el = event.target;
    if (!el || el.nodeType !== 1 || !(el.id in EDITOR_SURFACES)) return;
    if (typeof asSurface === "function") return;
    editorWarmSurfaceModule(el);
  },
  true
);

// The callout kinds, their icon and their accessible label. Kept as data
// because three things read it: the "/" menu builds a command per kind, the
// renderer maps a parsed kind onto an icon, and the CSS keys a colour off
// `.callout-{kind}`. A kind added here needs a matching CSS block and nothing
// else.
//: **`ph:` tokens, not emoji, and this was the last place in the app drawing
//: its own alphabet.** The eight kinds carried \u{1F4DD}, \u{1F4A1} and six
//: more, which rendered at the system emoji face and size beside a menu whose
//: every other row is Phosphor: two faces, two weights, one row. Both readers
//: of this table take a token now (the "/" menu row through `setLabel`, the
//: renderer through an `<i class="ph ...">`), and `tests/test_no_glyph_icons.py`
//: carries the eight so they cannot come back.
//:
//: **Obsidian's whole set, with its aliases** (INBOX 421 b: the blocks were
//: "limited in what they can do"). Eight kinds became fourteen: the thirteen
//: Obsidian ships, so a vault's callouts arrive here looking the way they were
//: written, and `toggle`, this app's plain disclosure (a fold with no colour,
//: Notion's toggle) spelled as a callout so it degrades to a quote elsewhere.
//: `about` is the "/" menu's one line for the row and its preview; `aliases`
//: are the other names Obsidian accepts for the same kind. The colour is the
//: stylesheet's (`.callout-{kind}`, `.cm-md-callout-{kind}`), keyed off the
//: palette tokens so every kind has a light and a dark value.
// EDITOR-BLOCKS-BEGIN
const CALLOUT_KINDS = {
  note: { icon: "ph:note", label: "Note", about: "A point worth setting apart" },
  abstract: { icon: "ph:clipboard-text", label: "Summary", about: "The short version, up front", aliases: ["summary", "tldr"] },
  info: { icon: "ph:info", label: "Info", about: "Background the reader may need" },
  todo: { icon: "ph:check-square", label: "To do", about: "Something still to be done" },
  tip: { icon: "ph:lightbulb", label: "Tip", about: "A better way to do it", aliases: ["hint", "important"] },
  success: { icon: "ph:check-circle", label: "Success", about: "What worked, or what is done", aliases: ["check", "done"] },
  question: { icon: "ph:question", label: "Question", about: "An open question", aliases: ["help", "faq"] },
  warning: { icon: "ph:warning", label: "Warning", about: "Careful: this can go wrong", aliases: ["caution", "attention"] },
  failure: { icon: "ph:x-circle", label: "Failure", about: "What did not work", aliases: ["fail", "missing"] },
  danger: { icon: "ph:warning-octagon", label: "Danger", about: "Stop: this does harm", aliases: ["error"] },
  bug: { icon: "ph:bug", label: "Bug", about: "A known fault and its symptoms" },
  example: { icon: "ph:flask", label: "Example", about: "A worked case" },
  quote: { icon: "ph:quotes", label: "Quote", about: "Somebody else's words, set apart", aliases: ["cite"] },
  toggle: { icon: "ph:caret-circle-right", label: "Toggle", about: "Folded away until clicked, no colour" },
};

//: The canonical kind for a name as written (`Warning`, `caution`, `tldr`),
//: or null for a name that is not one.
function calloutKindOf(raw) {
  const name = String(raw || "").toLowerCase();
  if (!name) return null;
  if (Object.prototype.hasOwnProperty.call(CALLOUT_KINDS, name)) return name;
  for (const [kind, meta] of Object.entries(CALLOUT_KINDS)) {
    if ((meta.aliases || []).includes(name)) return kind;
  }
  return null;
}

//: A callout's first line with its kind and fold flag changed and nothing
//: else: the quote marker, the title and anything after them stay exactly as
//: written. `fold` is "" (always open), "-" (folded) or "+" (foldable, open).
//: A line with no `[!kind]` marker comes back unchanged.
function calloutRewriteHead(line, kind, fold = "") {
  return String(line).replace(/\[![\w-]+\][-+]?/, `[!${kind}]${fold}`);
}

//: **Letters in order, anywhere** (the "/" menu's search). Returns the
//: indexes of the label's characters that matched, for the highlight, or null.
//: Greedy from the left, which is what a reader scanning the label expects to
//: see lit up.
function editorFuzzyMatch(label, query) {
  const hay = String(label || "").toLowerCase();
  const needle = String(query || "").toLowerCase();
  if (!needle) return [];
  const hits = [];
  let from = 0;
  for (const ch of needle) {
    const at = hay.indexOf(ch, from);
    if (at === -1) return null;
    hits.push(at);
    from = at + 1;
  }
  return hits;
}

//: Rank rows for a query, best first, stable within a tier: a label equal
//: to it ("table" finds Table before Table of contents), a label that
//: starts with it, a word in the label that does, a keyword that does, the
//: label containing it, a keyword containing it, and last the letters in
//: order anywhere in the label ("twcl" finds Two columns). No query keeps the
//: table's own order, which is the grouped menu.
function editorFuzzyRank(rows, query) {
  const needle = String(query || "").toLowerCase().trim();
  if (!needle) return rows.slice();
  const scored = [];
  rows.forEach((row, index) => {
    const label = String(row.label || "").toLowerCase();
    const keywords = (row.keywords || []).map((k) => String(k).toLowerCase());
    let score = -1;
    if (label === needle) score = 0;
    else if (label.startsWith(needle)) score = 0.5;
    else if (label.split(/[\s-]+/).some((word) => word.startsWith(needle))) score = 1;
    else if (keywords.some((k) => k.startsWith(needle))) score = 2;
    else if (label.includes(needle)) score = 3;
    else if (keywords.some((k) => k.includes(needle))) score = 4;
    else if (needle.length > 1 && editorFuzzyMatch(label, needle)) score = 5;
    if (score >= 0) scored.push({ row, score, index });
  });
  scored.sort((a, b) => a.score - b.score || a.index - b.index);
  return scored.map((s) => s.row);
}
//: What an empty callout body says until something is written in it.
function calloutHint(kind) {
  const own = { todo: "Write the task", toggle: "Write what folds away", success: "Write what worked", failure: "Write what failed" };
  const meta = CALLOUT_KINDS[kind];
  return own[kind] || `Write the ${meta ? meta.label.toLowerCase() : "note"}`;
}

// EDITOR-BLOCKS-END

// ---------------------------------------------------------------------------
// Inserting text into an arbitrary textarea
//
// app.js's applyMarkdown() does exactly this job already, but it is hard-wired
// to $("doc-content"), it reads the box, and it calls markDocDirty() and
// renderDocPreview() unconditionally. Rather than duplicate its action table
// (MD_ACTIONS is reused verbatim below), this is the same four insertion
// shapes parameterised by which box to act on, plus a host-notification step
// that does the right thing for whichever surface it landed in.
// ---------------------------------------------------------------------------

// Tell the surrounding app that a textarea's value changed under it.
//
// This is the step that is easy to forget and silent when missed: the capture
// box's character count and localStorage draft both hang off its `input`
// event, and the document's autosave hangs off markDocDirty(). Writing
// `.value` from script fires neither, so a note inserted through this menu
// would look right, count wrong, and never be saved as a draft.
function editorNotifyHost(textarea) {
  if (textarea.isDocument) {
    markDocDirty();
    renderDocPreview();
    return;
  }
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  //: The capture box grows with its content; a scripted write has to ask.
  //: **`.el`, not the surface.** `autoGrow` is app.js's and works on a real
  //: element: it writes `style.height`, and a surface has no `style`. Passing
  //: the surface threw `Cannot set properties of undefined (setting
  //: 'height')` out of every "/" command in the note composer, which still
  //: *inserted* the text, so the menu looked like it worked and the box
  //: silently stopped growing. Found by driving the capture box
  //: (`scratchpad/ui-sweeps/cm-notes.js`), not by reading: the surface wears
  //: enough of a textarea's names that the call site reads as correct.
  if (textarea.classList.contains("autogrow")) {
    autoGrow(textarea.el);
  }
}

// Replace [start, end) with `text`, then place the caret. `select` picks which
// slice of the inserted text ends up selected, so a placeholder can be typed
// straight over: the behaviour wrapDocSelection() already establishes for the
// formatting toolbar, kept identical here so the two feel like one editor.
function editorSplice(textarea, start, end, text, select) {
  //: CodeMirror gets a transaction rather than a whole-document rewrite: one
  //: keeps the editor's own undo history granular, the other collapses every
  //: insertion into "the document became this string".
  if (textarea.kind === "codemirror") {
    textarea.replaceRange(start, end, text);
  } else {
    const value = textarea.value;
    textarea.value = value.slice(0, start) + text + value.slice(end);
  }
  if (select) {
    textarea.setSelectionRange(start + select.from, start + select.to);
  } else {
    const caret = start + text.length;
    textarea.setSelectionRange(caret, caret);
  }
  textarea.focus();
  editorNotifyHost(textarea);
}

//: **The one icon and emoji picker, fetched on first use** (MINDMAP_PLAN.md
//: decision 43): `LAZY_MODULES.iconPicker` names icon-picker.js and its
//: stylesheet, and `LAZY_ENTRY_POINTS.iconPicker` (app.js) stands in for
//: `openIconPicker` until they arrive. This is the one door every caller
//: (the map, the board, both editors) goes through. Resolves once the panel
//: is open; a load that fails (offline, the file gone) does nothing.
function pickIconOrEmoji(options) {
  return openIconPicker(options);
}

//: **An emoji or an icon at the caret** (MINDMAP_PLAN.md decision 46),
//: from the one picker: an emoji as itself, an icon as `:ph-name:`, which
//: the reading view draws. The caret's place is kept while the picker is
//: open, since focus is in its search field by then.
function editorPickGlyph(textarea, anchor = null) {
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  pickIconOrEmoji({
    anchor: anchor || (textarea.kind === "codemirror" ? null : textarea),
    title: "Insert an emoji or icon",
    onPick: (choice) => {
      const text = choice.kind === "emoji" ? choice.value : `:ph-${choice.value}:`;
      editorSplice(textarea, start, end, text, { from: text.length, to: text.length });
    },
  });
}

// Apply one MD_ACTIONS-shaped action to any textarea.
//
// The shapes (wrap / line / block / insert) are app.js's, deliberately: the
// formatting toolbar and this menu must not drift into two dialects of the
// same markdown. Anything the toolbar can insert, "/" can insert identically.
function editorApplyAction(textarea, action) {
  const { selectionStart: start, selectionEnd: end, value } = textarea;
  const selected = value.slice(start, end);

  if (action.wrap) {
    const body = selected || action.placeholder || "";
    const text = action.wrap + body + action.wrap;
    editorSplice(textarea, start, end, text, {
      from: action.wrap.length,
      to: action.wrap.length + body.length,
    });
    return;
  }
  if (action.line) {
    // Prefix the selected lines, or the current one when nothing is selected.
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    const tail = value.slice(end).indexOf("\n");
    const lineEnd = tail === -1 ? value.length : end + tail;
    const target = value.slice(lineStart, Math.max(lineEnd, end));
    const prefixed = target
      .split("\n")
      .map((line) => (line.startsWith(action.line) ? line : action.line + line))
      .join("\n");
    //: An empty line has nothing to select: the caret goes after the
    //: marker, so "/todo" then typing writes the item (measured on a board
    //: text box, 2026-10-10: the selected "- [ ] " was typed over).
    editorSplice(textarea, lineStart, Math.max(lineEnd, end), prefixed, {
      from: target.trim() ? 0 : prefixed.length,
      to: prefixed.length,
    });
    return;
  }
  if (action.block) {
    const body = selected || action.placeholder || "";
    const text = action.block + body + (action.suffix || "");
    editorSplice(textarea, start, end, text, {
      from: action.block.length,
      to: action.block.length + body.length,
    });
    return;
  }
  if (action.insert) {
    editorSplice(textarea, start, end, action.insert);
  }
}

//: **The shapes `editorApplyAction` does not implement.**
//:
//: MD_ACTIONS is bigger than the four shapes above: `custom` (image, footnote,
//: link, indent, undo…) and `pre`/`post` (the HTML-ish sup/sub/underline/
//: comment) are both handled by `applyMarkdown` in documents.js and by nothing
//: here. A "/" command wired straight to one of those through
//: `editorApplyAction` matches no branch and returns silently, this repo's
//: "a policy silently refusing the work" shape, and it would have shipped as
//: three menu rows that do nothing.
//:
//: `applyMarkdown` takes a box id and every editor surface has one, so this
//: is a call rather than a second implementation for the two to drift apart.
function editorApplyNamed(textarea, kind) {
  if (typeof applyMarkdown === "function" && textarea.id) {
    applyMarkdown(kind, textarea.id);
    return;
  }
  editorApplyAction(textarea, (typeof MD_ACTIONS === "object" && MD_ACTIONS[kind]) || {});
}

//: **Put one block on a line of its own.**
//:
//: A board object is a block construct: `renderNoteText` and `renderMarkdown`
//: both only recognise `![[...]]` when the line holds nothing else, so an
//: object inserted mid-sentence renders as literal brackets, which is the
//: silent-refusal shape this repo keeps meeting. The leading newlines are
//: counted rather than always added, so inserting into an empty box does not
//: start the note with two blank lines.
function editorInsertBlock(textarea, markdown) {
  const start = textarea.selectionStart;
  const before = String(textarea.value || "").slice(0, start);
  const lead = !before.length || before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
  editorSplice(textarea, start, textarea.selectionEnd, `${lead}${markdown}\n\n`, null);
}

//: The "/" menu's board object: choose the board, then write its reference.
//:
//: The chooser is `pickLibraryItemDialog`, the app's own one-thing picker,
//: asked for its board source. A fifth chooser for a fifth kind is exactly
//: the "the same object drawn five ways" failure this app already has a rule
//: against, and the dialog hands the row back, so the reference can say
//: whether it is a board or a map without a second request.
//: The "/" menu's bookmark link: the app's one-thing picker on its Bookmarks
//: source (`LIBRARY_PICK_SOURCES`, kind "link"), then `[title](url)` inline
//: at the caret, where the "/" was typed.
async function editorInsertBookmarkLink(textarea) {
  if (typeof pickLibraryItemDialog !== "function") return;
  const at = textarea.selectionStart;
  const chosen = await pickLibraryItemDialog("Which bookmark?", { sources: ["link"] });
  if (!chosen) return;
  const row = chosen.row || {};
  const url = String(row.url || "").replace(/ /g, "%20").replace(/\)/g, "%29");
  if (!url) return;
  const text = String(row.title || chosen.label || url).replace(/[[\]]/g, "");
  textarea.focus();
  editorSplice(textarea, at, at, `[${text}](${url})`, null);
}

async function editorInsertBoardObject(textarea) {
  if (typeof pickLibraryItemDialog !== "function" || typeof boardEmbedMarkdown !== "function") return;
  const chosen = await pickLibraryItemDialog("Which board or map?", { sources: ["board"] });
  if (!chosen) return;
  editorInsertBlock(textarea, boardEmbedMarkdown(chosen.row || { id: chosen.id, title: chosen.label }));
}

// ---------------------------------------------------------------------------
// The command table
// ---------------------------------------------------------------------------

// `contexts` omitted means "everywhere". `keywords` exists so that typing
// "warn", "box" or "frame" finds the warning callout, the user asked for
// "specialised boxes and frames", which is nobody's idea of the word
// "callout", and a menu you can only search by its internal vocabulary is a
// menu you have to already know.
//: **One row a command** (O6; `ai/slash.py`'s registry, `GET /chat/commands`),
//: so this menu, `/help` and the route cannot drift (tests/test_slash.py).
//: The list is fetched once, on the first "/"; until it arrives, or offline,
//: one row sends `/help`. A command that takes words fills the box with its
//: name and waits for them; one that takes none runs.
const chatSlash = { list: null };
function chatSlashRows(afterPress, boxId = "chat-input", send = sendChatMessage) {
  if (chatSlash.list === null) {
    chatSlash.list = [];
    apiJson("/chat/commands").then((r) => { chatSlash.list = r.commands || []; if (editorMenuState.trigger) editorRefreshMenu(); }).catch(() => { chatSlash.list = null; });
  }
  if (!chatSlash.list.length) {
    return [{ id: "chat-commands", group: "Commands", icon: "ph:terminal", label: "Commands", hint: "exact answers, no AI", keywords: ["command", "slash", "help"], run: afterPress(() => send("/help")) }];
  }
  const fill = (name) => {
    const box = $(boxId);
    box.value = `/${name} `;
    box.focus();
  };
  return chatSlash.list.map((c) => ({
    id: `chat-cmd-${c.name}`, group: "Commands", icon: "ph:terminal", label: c.usage, hint: c.summary.replace(/\.$/, ""), keywords: [c.name, "command", "slash"],
    run: afterPress(() => (/[[<]/.test(c.usage) ? fill(c.name) : send(`/${c.name}`))),
  }));
}

//: **What "/" offers in the chat box.** Not the note commands: a callout box
//: or a template pasted into a question is nobody's intent, and the document
//: AI actions have nowhere to run here. Each of these presses a control the
//: dock already has, so the menu is a second door to the same rooms and can
//: never drift from what the buttons do. The slash token is removed by
//: `editorRunItem` before `run` is called, so the question is left clean.
function chatCommands() {
  //: Run `fn` once the press that chose the row is over (see `pick`).
  const afterPress = (fn) => () => {
    if (!editorMenuState.pressing) return fn();
    document.addEventListener("mouseup", () => setTimeout(fn), { once: true, capture: true });
  };
  const press = (id) => afterPress(() => document.getElementById(id)?.click());
  //: **On the next frame, not in this one** (the owner, 2026-09-21: pressing
  //: "A document" in the slash menu showed the picker "for a split second but
  //: then disappears"). Both halves run inside the handler for the click that
  //: chose the menu row, so the picker opened, installed its own
  //: close-on-click-outside listener, and then that very click carried on
  //: bubbling to the document and closed it again. Anything that opens a
  //: surface from inside a click has to let the click finish first.
  //:
  //: **And after the button comes up, when a pointer chose it** (the owner,
  //: 2026-10-10: "I tried to press a note on the slash menu in the chat tab
  //: and the panel flickered then nothing happened"). The row runs on
  //: `mousedown`; a press held longer than a frame (measured: 250 ms) let the
  //: picker open before the `mouseup`, and that press's own `click`, on the
  //: page once the menu had gone, was the picker's click-away. A fast click
  //: passed, which is why the frame alone looked like the fix. The Skills
  //: and Web rows open popovers with the same click-away, so `press` waits
  //: too.
  const pick = (source) => afterPress(() => {
    if (typeof openNotePicker !== "function") return;
    requestAnimationFrame(() => {
      openNotePicker();
      //: And the source tab a frame after that: the picker renders its own
      //: markup when it opens, so the button is not there to press yet.
      requestAnimationFrame(() => {
        document
          .querySelector(`#note-picker-sources [data-picker-source="${source}"]`)
          ?.click();
      });
    });
  });
  const mode = (name) => () =>
    document.querySelector(`#chat-mode-seg button[data-chat-mode="${name}"]`)?.click();
  return [
    { id: "chat-attach-note", primary: true, group: "Attach", icon: "ph:note", label: "A note", hint: "as context", keywords: ["attach", "note", "reference", "context"], run: pick("notes") },
    { id: "chat-attach-document", primary: true, group: "Attach", icon: "ph:file-text", label: "A document", hint: "from Documents", keywords: ["attach", "document", "doc"], run: pick("documents") },
    { id: "chat-attach-file", primary: true, group: "Attach", icon: "ph:paperclip", label: "A file", hint: "from the Library", keywords: ["attach", "file", "pdf", "spreadsheet"], run: pick("files") },
    { id: "chat-attach-image", group: "Attach", icon: "ph:image", label: "An image", hint: "from the Library", keywords: ["attach", "image", "picture", "photo", "sketch"], run: pick("images") },
    { id: "chat-upload", primary: true, group: "Attach", icon: "ph:upload-simple", label: "Upload something new", hint: "any file", keywords: ["upload", "new", "file", "attach"], run: press("attach-image") },
    { id: "chat-web", primary: true, group: "This message", icon: "ph:globe", label: "Web search", hint: "toggle", keywords: ["web", "search", "online", "internet"], run: afterPress(() => toggleWebSearch()) },
    { id: "chat-plan", primary: true, group: "This message", icon: "ph:compass", label: "Plan first", hint: "toggle", keywords: ["plan", "steps", "think"], run: press("chat-plan") },
    { id: "chat-skills", primary: true, group: "This message", icon: "ph:lightning", label: "Skills", hint: "run a saved skill", keywords: ["skill", "skills", "run", "workflow"], run: press("chat-skills-btn") },
    { id: "chat-equation", group: "This message", icon: "ph:function", label: "Equation", hint: "build a formula, Alt+=", keywords: ["equation", "math", "maths", "formula", "symbol"], run: afterPress(() => openMathEditor({ target: document.getElementById("chat-input") })) },
    ...POPUP_TOOLS.filter((t) => t.id !== "equation").map((tool) => ({ id: `chat-tool-${tool.id}`, group: "This message", icon: tool.icon, label: tool.name, hint: "opens a panel", keywords: tool.keywords.split(" "), run: afterPress(() => tool.open()) })),
    ...chatSlashRows(afterPress),
    { id: "chat-mode-agent", group: "Mode", icon: "ph:strategy", label: "Agent mode", hint: "let it act on the notebook", keywords: ["agent", "mode", "tools", "act"], run: mode("agent") },
    { id: "chat-mode-chat", group: "Mode", icon: "ph:sparkle", label: "Ask mode", hint: "answer only", keywords: ["ask", "chat", "mode", "answer"], run: mode("chat") },
  ];
}

//: **What "/" offers in the Agent popup** (INBOX 1309): the commands only,
//: run through the popup's own turn (`cmdPaletteAsk`, which streams through
//: the same `/chat/stream` that answers a typed command).
function agentCommands() {
  const afterPress = (fn) => () => {
    if (!editorMenuState.pressing) return fn();
    document.addEventListener("mouseup", () => setTimeout(fn), { once: true, capture: true });
  };
  return chatSlashRows(afterPress, "command-palette-input", (text) => cmdPaletteAsk(text));
}

//: **What "/" offers in a skill's steps box** (DOCUMENTS_PLAN Phase 8c: "the
//: skill editor's steps box gets the `/` menu only"). Not the note commands,
//: for the reason `chatCommands` gives about the chat box and more sharply
//: here: this box's own contract, printed on its label, is "one step per
//: line, in order", so a callout, a table or a two-column fence pasted into
//: it is not a step and nothing downstream renders it. `skills.normalise`
//: reads these lines as instructions, not as markdown.
//:
//: What a steps box actually wants is the two vocabularies the rest of the
//: editor beside it already holds, and cannot be typed correctly from memory:
//: the placeholders the "Ask me for" box declares, whose braces are easy to
//: get wrong, and the exact spelling of the tools this skill is allowed to
//: use, which come from the server's catalogue and drift if guessed. Both are
//: read off the form rather than listed here, the same way chat's commands
//: press controls that already exist, so neither can go stale.
function skillCommands() {
  const insert = (text) => (surface) => {
    const start = surface.selectionStart;
    editorSplice(surface, start, surface.selectionEnd, text);
  };
  const commands = [];
  //: `name` or `name: question`, one per line, which is what `textToInputs`
  //: in app.js parses. Only the name goes in the braces.
  const inputs = (document.getElementById("skill-inputs")?.value || "")
    .split("\n")
    .map((line) => line.split(":")[0].trim())
    .filter(Boolean);
  for (const name of inputs) {
    commands.push({
      id: `skill-input-${name}`,
      primary: true,
      group: "Answers you will be asked for",
      //: The same rule as the board row above: an icon, not a typed glyph.
      icon: "ph:chat-teardrop-text",
      label: `{{${name}}}`,
      hint: "the answer goes here",
      keywords: ["input", "placeholder", "ask", "variable", name],
      run: insert(`{{${name}}}`),
    });
  }
  //: The checked tools, not the whole catalogue: a step naming a tool this
  //: skill is not allowed to use is a step that cannot run.
  const tools = [...document.querySelectorAll("#skill-tool-list input:checked")].map((box) => box.value);
  for (const tool of tools) {
    commands.push({
      id: `skill-tool-${tool}`,
      primary: true,
      group: "Tools this skill may use",
      icon: "ph:wrench",
      label: tool,
      hint: "name it in a step",
      keywords: ["tool", "use", tool],
      run: insert(tool),
    });
  }
  //: An empty menu with no explanation reads as a broken menu. This row says
  //: where the two lists come from, and pressing it does nothing rather than
  //: writing a word nobody asked for.
  if (!commands.length) {
    commands.push({
      id: "skill-nothing-yet",
      primary: true,
      group: "Nothing to offer yet",
      icon: "ph:info", label: "Add an input or tick a tool",
      hint: "then they appear here",
      keywords: ["input", "tool", "help", "empty"],
      run: () => {},
    });
  }
  return commands;
}

//: **The block catalogue** (INBOX 421 b, the owner: the "/" blocks were
//: "confusing to use, and limited in what they can do and how to use them.
//: they need ot be impressive and an actual proper thing").
//:
//: Read against five tools that do this well. Notion's "/" menu is grouped
//: (Basic blocks, Media, Embeds, Advanced), every row a tile, a name and one
//: line of what it does, with a preview of the block beside the list. Craft
//: and Heptabase lean on the same tile-and-line row. Coda puts "Suggested"
//: (what you used last) first and lets Tab jump between sections. Obsidian's
//: command search is fuzzy (letters in order, anywhere) and shows the key
//: that does the same thing. This table is those five ideas, in this app's
//: own components: groups in a fixed order, a tile, a name, a line and the
//: markdown it writes; "Recent" first; fuzzy search (`editorFuzzyRank`);
//: Tab to the next group; a preview drawn by the renderer that will draw the
//: block (`renderMarkdown`), so the preview cannot disagree with the page.
//:
//: **One table for notes and documents.** A row is left out of the capture
//: box only when what it writes needs a document to mean anything (the
//: properties block, a block reference, an anchored comment, the document
//: AI); every block that renders in a note is offered in a note.
const EDITOR_GROUP_ORDER = [
  "Recent", "Basic", "Structure", "Callouts", "Media", "Embeds", "Advanced", "AI", "Templates",
];

//: How many recent blocks lead the menu, and how many are remembered.
const EDITOR_RECENT_SHOWN = 4;
const EDITOR_RECENT_KEPT = 8;
const EDITOR_RECENT_KEY = "editorRecentBlocks";

//: Per viewer, in this browser only: a convenience, never a record, so it
//: is read and written behind try/catch and an empty answer is fine.
function editorRecentIds() {
  try {
    const ids = prefs.json(EDITOR_RECENT_KEY, []);
    return Array.isArray(ids) ? ids.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function editorRememberBlock(id) {
  if (!id) return;
  try {
    const ids = [id, ...editorRecentIds().filter((other) => other !== id)].slice(0, EDITOR_RECENT_KEPT);
    prefs.set(EDITOR_RECENT_KEY, JSON.stringify(ids));
  } catch {
    // Storage blocked: the menu simply has no Recent group.
  }
}

//: **Put a block on lines of its own and select what to type over.**
//: `before` and `after` wrap the placeholder (or the selection, when there is
//: one); blank lines are added only where they are missing, so a block
//: inserted into an empty box does not start it with two empty lines and one
//: inserted between paragraphs does not glue itself to either. A block with
//: nothing to type (a rule, `[TOC]`) leaves the caret on the line after it.
//: `caretInside`: no placeholder text, the caret where it would have started
//: (a callout's body line, which the Live view hints at instead, INBOX 486).
function editorBlock(textarea, before, placeholder = "", after = "", { caretInside = false } = {}) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const value = String(textarea.value || "");
  const body = value.slice(start, end) || placeholder;
  const prior = value.slice(0, start);
  const next = value.slice(end);
  const lead = !prior.length || prior.endsWith("\n\n") ? "" : prior.endsWith("\n") ? "\n" : "\n\n";
  const trail = next.startsWith("\n\n") ? "" : next.startsWith("\n") ? "\n" : "\n\n";
  const text = lead + before + body + after + trail;
  const from = lead.length + before.length;
  if (!body && !after && !caretInside) {
    editorSplice(textarea, start, end, text, { from: text.length, to: text.length });
    return;
  }
  editorSplice(textarea, start, end, text, { from, to: from + body.length });
}

//: The languages the code block's second step offers, in the order people
//: reach for them; the fence word is what GitHub, Obsidian and the Live
//: view's highlighter all key off. Typing after the fence filters them.
const EDITOR_CODE_LANGS = [
  ["Plain text", "text"], ["JavaScript", "js"], ["TypeScript", "ts"], ["Python", "python"],
  ["HTML", "html"], ["CSS", "css"], ["JSON", "json"], ["Shell", "bash"], ["SQL", "sql"],
  ["Markdown", "markdown"], ["YAML", "yaml"], ["Rust", "rust"], ["Go", "go"], ["Java", "java"],
  ["C", "c"], ["C++", "cpp"], ["C#", "csharp"], ["PHP", "php"], ["Ruby", "ruby"],
  ["Swift", "swift"], ["Kotlin", "kotlin"], ["Mermaid diagram", "mermaid"],
];

function editorCodeLanguageRows() {
  return EDITOR_CODE_LANGS.map(([name, fence]) => ({
    id: `code-${fence}`,
    group: "Language",
    icon: "ph:code",
    label: name,
    keys: fence,
    keywords: [fence],
    fence,
  }));
}

function editorBlockRows(context) {
  const inDocument = context === "document";
  const rows = [];
  const add = (row) => rows.push(row);
  const act = (kind) => (t) => editorApplyAction(t, MD_ACTIONS[kind]);

  // --- Basic: the blocks every page is made of. ---------------------------
  add({ id: "h1", group: "Basic", icon: "ph:text-h-one", label: "Heading 1", about: "The title of the page", keys: "#", keywords: ["h1", "title", "heading", "big"], sample: "# A page title", run: act("h1") });
  add({ id: "heading", group: "Basic", icon: "ph:text-h-two", label: "Heading 2", about: "A section, and a place the contents can jump to", keys: "##", keywords: ["h2", "section", "heading", "anchor"], sample: "## A section", run: act("h2") });
  add({ id: "h3", group: "Basic", icon: "ph:text-h-three", label: "Heading 3", about: "A sub-section", keys: "###", keywords: ["h3", "sub", "heading", "small"], sample: "### A sub-section", run: act("h3") });
  add({ id: "bullets", group: "Basic", icon: "ph:list-bullets", label: "Bulleted list", about: "Points in no particular order", keys: "-", keywords: ["list", "bullet", "ul", "points"], sample: "- First point\n- Second point", run: act("ul") });
  add({ id: "numbered", group: "Basic", icon: "ph:list-numbers", label: "Numbered list", about: "Steps, in order", keys: "1.", keywords: ["ordered", "numbered", "list", "ol", "steps"], sample: "1. First step\n2. Second step", run: act("ol") });
  add({ id: "checklist", group: "Basic", icon: "ph:check-square", label: "To-do list", about: "Tick things off as they are done", keys: "- [ ]", keywords: ["task", "todo", "check", "checklist", "list"], sample: "- [x] Research\n- [ ] Draft\n- [ ] Send", run: act("task") });
  add({ id: "quote", group: "Basic", icon: "ph:quotes", label: "Quote", about: "Somebody else's words, set apart", keys: ">", keywords: ["quote", "blockquote", "cite"], sample: "> Words worth keeping.", run: act("quote") });
  add({ id: "quote-cite", group: "Basic", icon: "ph:quotes", label: "Quote with attribution", about: "The words, and who said them", keys: "> ... -- Name", keywords: ["quote", "cite", "attribution", "author", "pull quote", "source"], sample: "> Stay hungry, stay foolish.\n> -- Stewart Brand", run: (t) => editorBlock(t, "> ", "Words worth keeping", "\n> -- Who said it") });
  //: MINDMAP_PLAN decision 46: the one icon and emoji picker, from "/".
  add({ id: "emoji", group: "Basic", icon: "ph:smiley", label: "Emoji or icon", about: "Pick from every emoji and icon", keys: ":fire:", keywords: ["emoji", "icon", "sticker", "symbol", "smiley", "glyph"], run: (t) => editorPickGlyph(t) });
  add({ id: "divider", group: "Basic", icon: "ph:minus", label: "Divider", about: "A hairline between two parts", keys: "---", keywords: ["divider", "rule", "hr", "separator", "line"], sample: "Above\n\n---\n\nBelow", run: (t) => editorBlock(t, "---") });

  // --- Structure: what turns a page of text into a document. ---------------
  add({ id: "toggle", group: "Structure", icon: "ph:caret-circle-right", label: "Toggle", about: "A title that folds its contents away", keys: "> [!toggle]-", keywords: ["toggle", "fold", "collapse", "collapsible", "details", "disclosure", "hide", "accordion"], sample: "> [!toggle]+ What is inside\n> Shown on a click, folded otherwise.", run: (t) => editorBlock(t, "> [!toggle]- ", "Title", "\n> What is inside") });
  add({ id: "callout-fold", group: "Structure", icon: "ph:folder-open", label: "Collapsible callout", about: "A coloured box, folded until clicked", keys: "> [!note]-", keywords: ["fold", "collapse", "collapsible", "callout", "section", "hide"], sample: "> [!note]+ A foldable note\n> Click the title to fold it.", run: (t) => editorBlock(t, "> [!note]- ", "Title", "\n> What is inside") });
  add({ id: "columns", group: "Structure", icon: "ph:columns", label: "Two columns", about: "Side by side, stacked on a phone", keys: ":::columns", keywords: ["columns", "column", "two", "side by side", "split", "layout", "grid"], sample: ":::columns\n**Before**\n\nThe old way.\n:::column\n**After**\n\nThe new way.\n:::", run: (t) => editorBlock(t, ":::columns\n", "Left column", "\n:::column\nRight column\n:::") });
  add({ id: "columns-3", group: "Structure", icon: "ph:squares-four", label: "Three columns", about: "Three side by side, stacked on a phone", keys: ":::columns", keywords: ["columns", "three", "3", "layout", "grid", "side by side"], sample: ":::columns\nOne\n:::column\nTwo\n:::column\nThree\n:::", run: (t) => editorBlock(t, ":::columns\n", "First column", "\n:::column\nSecond column\n:::column\nThird column\n:::") });
  add({ id: "toc", group: "Structure", icon: "ph:list-dashes", label: "Table of contents", about: "Every heading, as links, kept up to date", keys: "[TOC]", keywords: ["toc", "contents", "outline", "index", "headings", "navigation"], sample: "[TOC]\n\n## Introduction\n## Method\n### Results", run: (t) => editorBlock(t, "[TOC]") });
  add({ id: "table", group: "Structure", icon: "ph:table", label: "Table", about: "Rows and columns you can sort and export", keys: "| |", keywords: ["table", "grid", "columns", "rows", "spreadsheet"], sample: "| Task | Owner |\n| --- | --- |\n| Draft | Sam |\n| Review | Ana |", run: (t) => editorApplyNamed(t, "table") });
  add({ id: "break-dots", group: "Structure", icon: "ph:asterisk", label: "Section break", about: "Three dots: a pause inside one topic", keys: "***", keywords: ["break", "section", "dots", "asterism", "divider", "pause"], sample: "End of one part.\n\n***\n\nStart of the next.", run: (t) => editorBlock(t, "***") });
  add({ id: "break-strong", group: "Structure", icon: "ph:equals", label: "Strong divider", about: "A heavy rule: one part ends here", keys: "___", keywords: ["divider", "rule", "thick", "strong", "heavy", "end"], sample: "Part one.\n\n___\n\nPart two.", run: (t) => editorBlock(t, "___") });
  if (inDocument) {
    add({ id: "page-break", group: "Structure", icon: "ph:file-dashed", label: "Page break", about: "What follows starts on a new page when printed", keys: "\\newpage", keywords: ["page", "break", "new page", "print", "pdf", "pagebreak"], sample: "End of chapter one.\n\n\\newpage\n\nChapter two.", run: (t) => editorBlock(t, "\\newpage") });
    add({ id: "properties", group: "Structure", icon: "ph:tag", label: "Properties", about: "Tags, status and dates at the top of the document", keys: "---", keywords: ["properties", "frontmatter", "metadata", "tags", "yaml", "status", "aliases"], run: (t) => editorApplyNamed(t, "properties") });
  }

  // --- Callouts: one row per kind, the kind's own line as its description. -
  for (const [kind, meta] of Object.entries(CALLOUT_KINDS)) {
    if (kind === "toggle") continue;
    add({
      id: `callout-${kind}`,
      group: "Callouts",
      icon: meta.icon,
      tint: kind,
      label: meta.label,
      about: meta.about,
      keys: `> [!${kind}]`,
      keywords: ["callout", "box", "frame", "admonition", "panel", kind, meta.label, ...(meta.aliases || [])],
      sample: `> [!${kind}] ${meta.label}\n> ${meta.about}.`,
      //: The kind's name as the title, once, and an empty body with the caret
      //: in it (INBOX 486: "Note Note" then a stock question as the body was
      //: the kind twice and a sentence to delete before writing).
      run: (t) => editorBlock(t, `> [!${kind}] ${meta.label}\n> `, "", "", { caretInside: true }),
    });
  }

  // --- Media ----------------------------------------------------------------
  add({ id: "image", group: "Media", icon: "ph:image", label: "Image", about: "From a file or a link; pasting or dropping works too", keys: "![](url)", keywords: ["image", "picture", "photo", "figure", "screenshot"], run: (t) => editorApplyNamed(t, "image") });
  if (inDocument) {
    add({ id: "image-caption", group: "Media", icon: "ph:image-square", label: "Image with caption", about: "Centred, with a line under it", keys: "![Caption|center](url)", keywords: ["image", "caption", "figure", "photo", "centre", "center"], run: (t) => editorBlock(t, "![A caption|center](", "https://", ")") });
  }
  add({ id: "codeblock", group: "Media", icon: "ph:code", label: "Code block", about: "Pick a language next; highlighted and copyable", keys: "```", keywords: ["code", "fence", "snippet", "program", "language", "syntax"], sample: "```js\nconst answer = 42;\n```", run: (t) => { editorBlock(t, "```", "", ""); editorBackOverTrail(t); editorOpenMenu(t, "```"); } });
  if (inDocument) {
    //: A starter the document's Live view draws at once (OPEN 1119): an empty
    //: ```mermaid fence drew nothing until its syntax was looked up.
    add({ id: "flowchart", group: "Media", icon: "ph:flow-arrow", label: "Flowchart", about: "Boxes and arrows, drawn from the text", keys: "```mermaid", keywords: ["flowchart", "diagram", "mermaid", "chart", "boxes", "arrows", "process"], sample: "flowchart TD\n  A[Start] --> B[Next]", run: (t) => editorBlock(t, "```mermaid\nflowchart TD\n  A[Start] --> B[Next]\n```", "", "") });
  }
  add({ id: "math", group: "Media", icon: "ph:function", label: "Maths block", about: "A formula on its own line, typeset", keys: "$$ ... $$", keywords: ["math", "maths", "formula", "equation", "latex", "tex", "block"], sample: "$$ e^{i\\pi} + 1 = 0 $$", run: (t) => editorBlock(t, "$$ ", "x^2 + y^2 = z^2", " $$") });
  add({ id: "math-inline", group: "Media", icon: "ph:math-operations", label: "Inline maths", about: "A formula inside a sentence", keys: "$ ... $", keywords: ["math", "inline", "formula", "latex", "tex"], run: act("math") });
  //: DOCUMENTS_PLAN 16: the guided editor (math-editor.js, lazy), Word's Alt+=.
  add({ id: "equation", group: "Media", icon: "ph:function", label: "Equation", about: "Build a formula from a palette, with a live preview", keys: "Alt+=", keywords: ["equation", "math", "maths", "formula", "symbol", "fraction", "greek", "matrix", "integral"], run: (t) => openMathEditor({ target: t }) });
  //: The other popup tools (settings-panes.js `POPUP_TOOLS`): a row each, so "/calc" and "/convert" find them in a note too.
  for (const tool of POPUP_TOOLS.filter((t) => t.id !== "equation")) {
    add({ id: `tool-${tool.id}`, group: "Media", icon: tool.icon, label: tool.name, about: tool.about.split(";")[0], keys: tool.keys, keywords: tool.keywords.split(" "), run: () => tool.open() });
  }

  // --- Embeds: other things in this notebook, and the web. ------------------
  add({ id: "wikilink", group: "Embeds", icon: "ph:link", label: "Link to a note", about: "Pick a note, document or board to link", keys: "[[", keywords: ["link", "note", "wiki", "reference", "connect", "document"], run: (t) => { editorApplyAction(t, { insert: "[[" }); editorOpenMenu(t, "[["); } });
  add({ id: "embed", group: "Embeds", icon: "ph:paperclip", label: "Embed a note or document", about: "Its content, or a card for it, shown here", keys: "![[", keywords: ["embed", "transclude", "include", "inline", "note", "document", "card"], run: (t) => { editorApplyAction(t, { insert: "![[" }); editorOpenMenu(t, "[["); } });
  add({ id: "board-object", group: "Embeds", icon: "ph:squares-four", label: "Board or mind map", about: "A live preview of it, here in the text", keys: "![[board:]]", keywords: ["board", "whiteboard", "map", "mindmap", "canvas", "object", "embed", "attach", "diagram"], run: (t) => editorInsertBoardObject(t) });
  //: A saved bookmark as a link where the caret is (owner, 0.3.31: "I want
  //: to attach bookmark links not just general links ... in notes and other
  //: text areas as well, like the / menu").
  add({ id: "bookmark-link", group: "Embeds", icon: "ph:bookmark-simple", label: "Bookmark link", about: "Pick a saved bookmark and link it here", keys: "[Title](url)", keywords: ["bookmark", "link", "reference", "url", "web", "saved", "source"], run: (t) => editorInsertBookmarkLink(t) });
  add({ id: "link-card", group: "Embeds", icon: "ph:cursor-click", label: "Link card", about: "A web link drawn as a card you press", keys: "[Title](url)", keywords: ["link", "card", "button", "bookmark", "url", "web", "preview"], run: (t) => editorBlock(t, "[", "Title", "](https://)") });
  add({ id: "weblink", group: "Embeds", icon: "ph:globe", label: "Web link", about: "A link inside the sentence", keys: "[text](url)", keywords: ["url", "web", "href", "external", "link"], run: (t) => { const { selectionStart: s, selectionEnd: e, value } = t; const label = value.slice(s, e) || "link text"; editorSplice(t, s, e, `[${label}](https://)`, { from: label.length + 3, to: label.length + 11 }); } });
  if (inDocument) {
    add({ id: "blockref", group: "Embeds", icon: "ph:link-simple", label: "Link to this block", about: "Copies [[Title#^id]] for this paragraph", keys: "#^", keywords: ["block", "reference", "anchor", "paragraph", "permalink", "copy link", "^"], run: (t) => editorApplyNamed(t, "blockref") });
  }

  // --- Advanced --------------------------------------------------------------
  add({ id: "footnote", group: "Advanced", icon: "ph:push-pin", label: "Footnote", about: "A reference here, its text at the foot", keys: "[^1]", keywords: ["footnote", "reference", "cite", "aside", "note"], run: (t) => editorApplyNamed(t, "footnote") });
  add({ id: "comment", group: "Advanced", icon: "ph:eye-slash", label: "Private comment", about: "Kept in the file, never shown", keys: "%% %%", keywords: ["comment", "private", "hidden", "note to self"], run: (t) => editorApplyNamed(t, "comment") });
  if (inDocument) {
    add({ id: "annotate", group: "Advanced", icon: "ph:chat-circle", label: "Comment on this", about: "A remark on these words, listed in the sidebar", keys: "==text== %%", keywords: ["comment", "annotate", "remark", "review", "feedback", "margin"], run: (t) => editorApplyNamed(t, "annotate") });
  }
  const now = new Date();
  const date = now.toLocaleDateString();
  const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  add({ id: "stamp-date", group: "Advanced", icon: "ph:calendar-blank", label: "Today's date", about: date, keys: "", keywords: ["date", "today", "stamp", "day"], run: (t) => editorApplyAction(t, { insert: date }) });
  add({ id: "stamp-time", group: "Advanced", icon: "ph:clock", label: "Time now", about: time, keys: "", keywords: ["time", "now", "stamp", "clock"], run: (t) => editorApplyAction(t, { insert: time }) });
  add({ id: "stamp-datetime", group: "Advanced", icon: "ph:calendar-dots", label: "Date and time", about: `${date} ${time}`, keys: "", keywords: ["date", "time", "timestamp", "stamp", "now", "log"], run: (t) => editorApplyAction(t, { insert: `${date} ${time}` }) });

  return rows;
}

//: After `editorBlock` wrote "```" and its trailing blank line, the caret is
//: past the blank line; the language menu belongs on the fence itself.
function editorBackOverTrail(textarea) {
  const value = String(textarea.value || "");
  let at = textarea.selectionStart;
  while (at > 0 && value[at - 1] === "\n") at -= 1;
  textarea.setSelectionRange(at, at);
}

//: **A context that is the note's rows, cut** (the boards' text boxes, map
//: topics and comments, 2026-10-10): context to the row ids it keeps, filled
//: by the lazy file that owns those surfaces (whiteboard.js
//: `WB_EDITOR_CONTEXT_ROWS`), so the lists cost the boot nothing.
const EDITOR_CONTEXT_ROWS = {};

function editorCommands(context) {
  if (context === "chat") return chatCommands();
  if (context === "agent") return agentCommands();
  if (context === "skill") return skillCommands();
  const keep = EDITOR_CONTEXT_ROWS[context];
  if (keep) return editorBlockRows("note").filter((row) => keep.includes(row.id));
  const commands = editorBlockRows(context);

  // --- AI actions ---
  // Document-only, because these route to the document editor's own AI panel
  // and extract-notes preview. Offering them in the capture box would open a
  // panel pointed at whatever document happened to be loaded, acting on text
  // the user cannot see is worse than not offering the command.
  if (context === "document") {
    commands.push(
      {
        //: **The one AI command that does not open a panel.** First in the
        //: group, because it is the one that answers the ask ("the agent or
        //: ai needs to be more directly integrated into the documents"); the
        //: other two are doors to the side pane, which is the right place for
        //: "review the whole document" and the wrong place for "make this
        //: shorter".
        id: "ai-inline",
        group: "AI",
        icon: "ph:sparkle", label: "Ask Atlas to write here",
        about: "Writes at the cursor, for you to keep or undo",
        keys: "Ctrl+J",
        keywords: ["ai", "write", "inline", "here", "cursor", "ask", "generate", "continue"],
        run: (textarea) => inlineAiOpen(textarea),
      },
      {
        id: "ai-edit",
        group: "AI",
        icon: "ph:sparkle", label: "AI edit this selection",
        about: "Rewrite, expand or tighten what is selected",
        keywords: ["ai", "rewrite", "improve", "expand", "edit"],
        run: () => $("doc-ai")?.click(),
      },
      {
        id: "ai-extract",
        group: "AI",
        icon: "ph:scissors", label: "Extract notes from here",
        about: "Split the document into linked notes",
        keywords: ["ai", "extract", "split", "notes"],
        run: () => $("doc-extract")?.click(),
      }
    );
  }

  // The user's own templates first, then the built-ins, the same "yours
  // before ours" ordering loadTemplates() already uses for the dropdown.
  const custom = (typeof prefsCache !== "undefined" && prefsCache?.custom_templates) || [];
  const builtin = typeof BUILTIN_TEMPLATES !== "undefined" ? BUILTIN_TEMPLATES : [];
  for (const template of [...custom, ...builtin]) {
    if (!template?.name || !template?.content) continue;
    commands.push({
      id: `template-${template.name}`,
      group: "Templates",
      icon: "ph:file-text",
      label: `${template.name}`,
      about: "Insert this template",
      keywords: ["template", template.name],
      sample: noteTemplateText(template.content).replaceAll(NOTE_TEMPLATE_CURSOR, "").split("\n").slice(0, 8).join("\n"),
      //: The variables the Capture box's picker fills (`noteTemplateForUse`,
      //: WORLD_CLASS_PLAN 5 item 4), so a template behaves the same whichever
      //: way it was reached; the caret lands on its `{{cursor}}`. The range is
      //: read before the clipboard is, which can take a moment.
      run: async (textarea) => {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const filled = await noteTemplateForUse(template);
        const at = filled.caret >= 0 ? filled.caret : filled.text.length;
        editorSplice(textarea, start, end, filled.text, { from: at, to: at });
      },
    });
  }

  return commands;
}

// ---------------------------------------------------------------------------
// The popup itself
// ---------------------------------------------------------------------------

const editorMenuState = {
  open: false,
  textarea: null,
  trigger: null, // "/", "[[" or "```" (the code block's language step)
  items: [],
  index: 0,
  start: 0, // index in textarea.value where the trigger token begins
  query: "", // what was typed after the trigger, for the highlight
};

// Where the caret is, in page coordinates.
//
// **One answer for the whole app, asked of the surface itself.** This used to
// be a second mirror implementation: an invisible div with the same text
// metrics, a marker span where the caret is, measured and thrown away, which
// is the only thing a `<textarea>` can do because it exposes no caret
// geometry at all. documents.js has the same technique in `docMirrorPoint`,
// and two copies of a measurement this fiddly is two things to keep in step.
//
// The adapter already has to answer this question for CodeMirror (which does
// have a real API for it, `coordsAtPos`), so it answers it for a textarea too
// and this becomes the one line it always wanted to be. `lineHeight` comes
// back with the point because every caller here places its popup *under* the
// caret's line and needs to know how tall the line is.
function editorCaretPoint(textarea) {
  const at = textarea.coordsAt(textarea.selectionStart);
  return { top: at.top, left: at.left, lineHeight: at.lineHeight, offscreen: Boolean(at.offscreen) };
}

// Put the menu at the caret, then pull it back on screen if it would hang off
// the bottom or the right, a menu you have to scroll the page to read is the
// same as no menu.
//: **Never at a caret the editor has not drawn** (INBOX 421 c). The engine
//: answers "no coordinates" for a position outside the lines it has laid
//: out, and the adapter's fallback for that is the editor's own top left
//: corner, which is the menu "at the top of the screen". The caret is
//: scrolled into view and the menu placed on the next frame; a caret that is
//: still not drawn after that closes the menu rather than parking it.
function editorPositionMenu(textarea, retried = false) {
  const menu = $("editor-menu");
  const { top, left, lineHeight, offscreen } = editorCaretPoint(textarea);
  if (offscreen) {
    if (retried || typeof textarea.scrollIntoView !== "function") return editorCloseMenu();
    textarea.scrollIntoView(textarea.selectionStart);
    requestAnimationFrame(() => {
      if (editorMenuState.open && editorMenuState.textarea === textarea) editorPositionMenu(textarea, true);
    });
    return;
  }
  menu.style.top = "0px";
  menu.style.left = "0px";
  const size = menu.getBoundingClientRect();
  const margin = 8;

  let y = top + lineHeight + 4;
  // Not enough room below: flip above the caret line instead of overflowing.
  if (y + size.height > window.innerHeight - margin) {
    const above = top - size.height - 4;
    y = above > margin ? above : Math.max(margin, window.innerHeight - size.height - margin);
  }
  const x = Math.max(margin, Math.min(left, window.innerWidth - size.width - margin));
  menu.style.top = `${Math.round(y)}px`;
  menu.style.left = `${Math.round(x)}px`;
}

//: The box that keeps the focus names the listbox it types into, so a screen
//: reader hears the menu open and each row the highlight lands on (WCAG 4.1.2).
function editorLinkBox(surface, on) {
  const box = surface?.el;
  if (!box) return;
  for (const name of ["aria-controls", "aria-haspopup", "aria-activedescendant"]) box.removeAttribute(name);
  if (on) {
    box.setAttribute("aria-controls", "editor-menu-list");
    box.setAttribute("aria-haspopup", "listbox");
  }
}

function editorCloseMenu(reason = "") {
  const { textarea, trigger } = editorMenuState;
  editorLinkBox(textarea, false);
  editorMenuState.open = false;
  editorMenuState.textarea = null;
  editorMenuState.items = [];
  $("editor-menu")?.classList.add("hidden");
  //: **A code fence is never left open.** The language step starts from a
  //: written "```", and an unclosed fence turns the rest of the page into
  //: code in every view. Closed any way but by choosing (Escape, a click
  //: elsewhere), the block is finished with whatever language was typed.
  if (trigger === "```" && reason !== "ran" && textarea && editorTokenAt(textarea, "```")) {
    editorFinishFence(textarea, editorTokenAt(textarea, "```").fragment.trim());
  }
}

//: Write the rest of a code block after "```lang" and put the caret on its
//: first line.
function editorFinishFence(textarea, fence) {
  const token = editorTokenAt(textarea, "```");
  if (!token) return;
  const at = token.start + 3;
  const word = String(fence || "").replace(/[^\w#+.-]/g, "");
  editorSplice(textarea, at, textarea.selectionStart, `${word}\n\n\`\`\``, {
    from: word.length + 1,
    to: word.length + 1,
  });
}

// The half-typed token immediately before the caret, or null.
//
// "/" only counts at the start of a line or after whitespace, so "and/or",
// "24/7" and a URL never open the menu. "[[" can appear anywhere, because
// there is nothing else it could plausibly mean.
function editorTokenAt(textarea, trigger) {
  const upto = textarea.value.slice(0, textarea.selectionStart);
  const open = upto.lastIndexOf(trigger);
  if (open === -1) return null;
  const fragment = upto.slice(open + trigger.length);
  // A newline means they moved on and left the token behind.
  if (fragment.includes("\n")) return null;
  if (trigger === "[[" && upto.slice(open).includes("]]")) return null;
  if (trigger === "/") {
    const before = open === 0 ? "\n" : upto[open - 1];
    if (!/\s/.test(before)) return null;
    // A slash command is one word. Once a space is typed it is prose.
    if (/\s/.test(fragment)) return null;
  }
  //: The fence is only ever its own line's start, and a language is a word.
  if (trigger === "```") {
    if (open > 0 && upto[open - 1] !== "\n") return null;
    if (/\s/.test(fragment)) return null;
  }
  return { start: open, fragment };
}

//: Ranked by `editorFuzzyRank` (EDITOR-BLOCKS, tested in node): a label
//: prefix, a word in the label, a keyword, then the letters in order anywhere.
function editorRankCommands(commands, needle) {
  return editorFuzzyRank(commands, needle);
}

// The notes a "[[" token could mean. Private notes are excluded for the same
// reason app.js's own [[ suggest excludes them: they cannot be link targets,
// so offering one is a dead end that also reveals it exists.
function editorLinkMatches(needle) {
  const query = (needle || "").trim().toLowerCase();
  //: **The note you are naming comes before the notes that mention it.** The
  //: list was every note holding the words anywhere, newest first, cut to six,
  //: so in a notebook where newer notes link to "Alpha project" the picker
  //: offered those, Enter took the first, and Alpha project itself was sixth
  //: or not shown (found by the deepflows sweep). Rank 0: the opening line
  //: starts with the words; 1: it holds them; 2: only the body does. The sort
  //: is stable, so the list's own order holds within a rank.
  const opening = (e) => (e.content || "").split("\n")[0].replace(/^#+\s*/, "").toLowerCase();
  const rank = (e) => {
    const line = opening(e);
    return line.startsWith(query) ? 0 : line.includes(query) ? 1 : 2;
  };
  const notes = (typeof allEntries !== "undefined" ? allEntries : [])
    .filter((e) => !e.is_private && (!query || (e.content || "").toLowerCase().includes(query)))
    .map((e, order) => ({ e, order, rank: query ? rank(e) : 0 }))
    .sort((a, b) => a.rank - b.rank || a.order - b.order)
    .map((row) => row.e)
    .slice(0, 6)
    .map((entry) => ({
      id: `note-${entry.id}`,
      group: "Notes",
      icon: "ph:note",
      //: The note's opening line only: its whole text flattened read as the
      //: title then the picture's alt text then the title again (INBOX 784).
      label: noteNamePlain(entry.content, 60) || "(empty note)",
      hint: "note",
      //: The note itself, for the preview: its first lines are what "is
      //: this the one I mean" is answered by (`editorRenderPreview`).
      entry,
      // Link by the note's opening words: that is what resolution matches
      // on. Brackets are stripped first: a note that itself contains a
      // [[link]] would otherwise be inserted verbatim, and the parser would
      // then find the INNER brackets and resolve to the wrong note.
      value: (entry.content || "")
        .split("\n")[0]
        .replace(/\[\[|\]\]/g, "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 60),
    }))
    .filter((item) => item.value);

  // Documents are link targets too, that is Phase B's whole point, and it is
  // why this list is built here rather than reusing app.js's note-only one.
  const documents = (editorDocumentCache || [])
    .filter((doc) => !query || (doc.title || "").toLowerCase().includes(query))
    .slice(0, 4)
    .map((doc) => ({
      id: `doc-${doc.id}`,
      group: "Documents",
      icon: "ph:file-text",
      label: doc.title || "Untitled",
      hint: "document",
      value: (doc.title || "").replace(/\[\[|\]\]/g, "").trim().slice(0, 60),
    }))
    .filter((item) => item.value);

  //: **Files and images**, the third and fourth kinds. They are not wiki-link
  //: targets, there is no name to resolve, only a url, so each carries the
  //: markdown it wants inserted (`item.markdown`, handled in `editorRunItem`):
  //: an embed for a picture, a plain link for anything else.
  const files = (editorFileCache || [])
    .filter((file) => !query || (file.original_name || "").toLowerCase().includes(query))
    .slice(0, 4)
    .map((file) => ({
      id: `file-${file._isAttachment ? "a" : "m"}-${file.id}`,
      group: file._isImage ? "Images" : "Files",
      icon: file._isImage ? "ph:image" : "ph:paperclip",
      label: file.original_name || "File",
      hint: file._isImage ? "image" : "file",
      markdown: `${file._isImage ? "!" : ""}[${(file.original_name || "file").replace(/[[\]]/g, "")}](${file.url})`,
    }));

  //: **Boards.** A board *is* an Entry (`is_board`) and used to be found in
  //: `allEntries`, but `GET /entries` is the notes list and no longer
  //: returns boards at all (reported: a mind map called "test" appeared in
  //: the Notes list as a note), so the source is now `/whiteboard/boards`
  //: through the same index the map chips read. A notebook with boards still
  //: has to be able to link to one.
  //: Not awaited, and only when the index is empty: this function is
  //: synchronous (it runs on every keystroke of a `[[` token), so the most it
  //: can do is ask for the list and let the *next* keystroke show it. The
  //: request itself is cached for 8s inside `loadMapBoardIndex`, so a burst
  //: of typing costs one call.
  if (typeof mapBoardRows === "function" && !mapBoardRows().length
      && typeof loadMapBoardIndex === "function") {
    loadMapBoardIndex();
  }
  const boards = (typeof mapBoardRows === "function" ? mapBoardRows() : [])
    .filter((b) => b.id != null)
    .filter((b) => !query || String(b.title || "").toLowerCase().includes(query))
    .slice(0, 3)
    .map((board) => ({
      id: `board-${board.id}`,
      group: "Boards",
      icon: board.type === "map" ? "ph:tree-structure" : "ph:squares-four",
      label: String(board.title || "Untitled board").slice(0, 60),
      hint: board.type === "map" ? "mind map" : "board",
      //: **The board's title, not its first raw line.** A board's content is
      //: `# My map`, so this used to insert `[[# My map]]`, which resolved
      //: (the resolver matched by prefix) and read as a stray heading marker
      //: inside a sentence. `resolveWikiTarget` matches a board title with or
      //: without the `#`, so links written the old way still resolve. The
      //: board row's own `title` arrives with the `# ` already stripped, so
      //: the cleaning below is only about brackets and runs of whitespace.
      value: String(board.title || "")
        .replace(/\[\[|\]\]/g, "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 60),
    }))
    .filter((item) => item.value);

  return [...notes, ...documents, ...boards, ...files];
}

//: The Library's own gallery payload, fetched once per menu session the same
//: way documents are: `/media` and `/files/gallery` are two calls, and doing
//: them per keystroke would put a request behind every letter typed.
let editorFileCache = null;

async function editorLoadFiles() {
  if (editorFileCache && editorFileCache.length) return;
  const [media, attachments] = await Promise.all([
    //: Read to the end (`apiPagedList`, documents.js): `GET /media` returns
    //: a page now (INBOX 117), and this cache is what the `/` and `[[` menus
    //: offer. A picker missing a file is a file you cannot insert, with
    //: nothing on screen to say it exists.
    apiPagedList("/media", MEDIA_PAGE_SIZE, { silent: true }).catch(() => []),
    apiPagedList("/files/gallery", 200, { silent: true }).catch(() => []),
  ]);
  const rows = [
    ...(Array.isArray(media) ? media : []).map((row) => ({ ...row, _isAttachment: false })),
    ...(Array.isArray(attachments) ? attachments : []).map((row) => ({
      ...row,
      _isAttachment: true,
      url: `/files/${row.id}`,
    })),
  ];
  //: `_isImage` decides embed-or-link, and it is decided here once rather
  //: than by each caller re-sniffing the extension, the same split
  //: `library.js` makes for the gallery.
  editorFileCache = rows.map((row) => ({
    ...row,
    _isImage: /\.(png|jpe?g|gif|webp|bmp|svg|avif|heic|heif|tiff?)$/i.test(row.original_name || ""),
  }));
}

// Documents are fetched once per menu session rather than per keystroke.
let editorDocumentCache = null;

//: **The menu, drawn** (INBOX 421 b). Two columns inside one popup: the list
//: (`#editor-menu-list`, the listbox) and, where the window has room for it,
//: a preview of the row the keyboard or the pointer is on
//: (`#editor-menu-preview`). A row is a tile holding the block's icon, its
//: name over one line of what it does, and the markdown it writes as a key
//: hint on the right: the same three facts a Notion or Craft row carries, in
//: this app's tokens. Group headings stay pinned while their rows scroll.
//:
//: Built with createElement throughout: a row's label can be a note's own
//: title (the `[[` picker), and note text is never parsed as markup.
function editorMenuIcon(item) {
  if (item.icon) return item.icon;
  return "ph:dot-outline";
}

function editorMenuList() {
  return $("editor-menu-list") || $("editor-menu");
}

function editorRenderMenu() {
  const menu = $("editor-menu");
  const list = editorMenuList();
  const { items, index, trigger, query } = editorMenuState;
  if (!items.length) return editorCloseMenu();

  list.replaceChildren();
  let lastGroup = null;
  items.forEach((item, position) => {
    if (item.group && item.group !== lastGroup) {
      list.appendChild(richPickerGroup(item.group, { className: "editor-menu-group" }));
      lastGroup = item.group;
    }
    //: **The rich picker's row** (rich-picker.js, DESIGN.md's recipe index):
    //: the recipe was taken out of this menu, so this is the one place it is
    //: drawn from and every other picker draws the same row. A callout's tile
    //: wears its kind's ink (`tint`, the `--callout-accent` the block itself
    //: will), so the colour is chosen before the block exists; the keycap is
    //: the markdown the row writes, the part that teaches the syntax behind
    //: the menu so the next time it can simply be typed.
    const row = richPickerRow({
      icon: editorMenuIcon(item),
      tint: item.tint,
      label: item.label,
      about: item.about || item.hint,
      keys: item.keys,
      query: trigger === "/" ? query : "",
      id: `editor-menu-row-${position}`,
      className: "editor-menu-item",
    });
    row.dataset.index = String(position);

    // mousedown, not click: the textarea must not lose focus first, or the
    // caret position the insertion depends on is already gone.
    row.addEventListener("mousedown", (event) => {
      event.preventDefault();
      //: Said to `run` for the press's length: a row that opens a surface
      //: waits for the button to come up (`chatCommands`'s `pick`).
      editorMenuState.pressing = true;
      try {
        editorRunItem(position);
      } finally {
        editorMenuState.pressing = false;
      }
    });
    //: The pointer chooses what the preview shows, without redrawing the
    //: list under it. `mousemove`, not `mouseenter`: a menu that opens under
    //: a pointer resting where the last click was gets an enter event on
    //: whatever row lands there, and took the highlight off the best match
    //: before a key was pressed (measured: Recent's first row lost to the
    //: fourth row down). Only a pointer that moves is choosing.
    row.addEventListener("mousemove", () => {
      if (editorMenuState.index !== position) editorSetActive(position, false);
    });
    list.appendChild(row);
  });

  menu.classList.remove("hidden");
  editorSetActive(Math.min(index, items.length - 1), true);
  editorPositionMenu(editorMenuState.textarea);
}

//: **The preview**, for "/" rows and for a note a "[[" row would link to
//: (an excerpt and its first picture, `richPickerNote`), and only with room for it (44rem, the
//: width the template dialog's preview also needs before it shows). What it
//: renders is the row's `sample`, through `renderMarkdown`, the renderer the
//: page itself uses, so the preview is the block and not a picture of it.
//: Inert and hidden from assistive tech: the row already says what it is.
const EDITOR_PREVIEW_MIN = 704;

function editorRenderPreview(item) {
  const menu = $("editor-menu");
  const pane = $("editor-menu-preview");
  if (!menu || !pane) return;
  const says = editorMenuState.trigger === "/" || (editorMenuState.trigger === "[[" && Boolean(item?.entry));
  const show = Boolean(item) && says && window.innerWidth >= EDITOR_PREVIEW_MIN;
  menu.classList.toggle("editor-menu-wide", show);
  pane.classList.toggle("hidden", !show);
  if (!show) return;
  if (pane.dataset.for === item.id) return;
  pane.dataset.for = item.id || "";
  let sample = null;
  if (item.sample) {
    sample = document.createElement("div");
    renderMarkdown(sample, item.sample);
    //: A narrow pane: the bar's Copy is an icon like its ⋯, so the caption
    //: keeps one line and the two buttons sit side by side.
    for (const copy of sample.querySelectorAll(".code-copy")) {
      copy.classList.add("icon-only");
      copy.querySelector(".ph-text")?.remove();
    }
  }
  richPickerPreview(pane, {
    icon: editorMenuIcon(item),
    tint: item.tint,
    label: item.label,
    about: item.about || item.hint,
    sample,
    keys: item.keys,
  });
  if (item.entry) richPickerNote(pane, item);
}

//: Move the highlight without redrawing the list: the row's classes, the
//: listbox's `aria-activedescendant`, the preview, and (from the keyboard)
//: the row scrolled into the list's view.
function editorSetActive(position, reveal) {
  const list = editorMenuList();
  const { items } = editorMenuState;
  if (!items.length || !list) return;
  const next = Math.max(0, Math.min(position, items.length - 1));
  editorMenuState.index = next;
  for (const row of list.querySelectorAll(".editor-menu-item")) {
    const on = Number(row.dataset.index) === next;
    row.classList.toggle("active", on);
    row.setAttribute("aria-selected", String(on));
    if (on) {
      list.setAttribute("aria-activedescendant", row.id);
      editorMenuState.textarea?.el?.setAttribute("aria-activedescendant", row.id);
      if (reveal) editorRevealRow(list, row);
    }
  }
  editorRenderPreview(items[next]);
}

//: Scrolled within the list only: `scrollIntoView` would also scroll the page
//: behind a fixed popup, and a page scroll closes this menu.
function editorRevealRow(list, row) {
  //: The first row of a group (a Tab jump lands on one) brings its heading
  //: to the top with it, so the jump shows the whole group opening rather
  //: than one row at the bottom edge.
  const before = row.previousElementSibling;
  if (before && before.classList.contains("editor-menu-group")) {
    //: Measured by rects from the row, not `offsetTop` of the heading: a
    //: pinned (sticky) heading reports where it is stuck, not where it sits.
    const inList = row.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
    list.scrollTop = Math.max(0, inList - before.offsetHeight - list.clientTop);
    return;
  }
  const header = list.querySelector(".editor-menu-group");
  const pad = header ? header.offsetHeight : 0;
  const top = row.offsetTop - pad;
  const bottom = row.offsetTop + row.offsetHeight;
  if (top < list.scrollTop) list.scrollTop = Math.max(0, top);
  else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight;
  //: The first row of the list also shows its group's heading.
  if (Number(row.dataset.index) === 0) list.scrollTop = 0;
}

//: The index of the first row of each group, in order.
function editorGroupStarts() {
  const starts = [];
  let last = null;
  editorMenuState.items.forEach((item, i) => {
    if (i === 0 || item.group !== last) starts.push(i);
    last = item.group;
  });
  return starts;
}

function editorNextGroupStart(step) {
  const starts = editorGroupStarts();
  const at = editorMenuState.index;
  let current = 0;
  starts.forEach((start, i) => {
    if (start <= at) current = i;
  });
  return starts[(current + step + starts.length) % starts.length];
}

// Apply the highlighted item: drop the trigger token that summoned the menu,
// then let the item do its work at that spot.
function editorRunItem(position) {
  const { textarea, trigger, items } = editorMenuState;
  const item = items[position];
  if (!item || !textarea) return editorCloseMenu();

  //: The language step: the fence and the typed word stay, and the rest of
  //: the block is written after them.
  if (item.fence !== undefined) {
    editorCloseMenu("ran");
    editorFinishFence(textarea, item.fence);
    return;
  }

  const token = editorTokenAt(textarea, trigger);
  if (token) {
    // Remove "/table" (or "[[part") so the command's own text replaces it.
    const keep = trigger === "[[" ? token.start + trigger.length : token.start;
    textarea.value =
      textarea.value.slice(0, keep) + textarea.value.slice(textarea.selectionStart);
    textarea.setSelectionRange(keep, keep);
  }
  editorCloseMenu("ran");
  //: Remembered under its own id, not its "Recent" copy's.
  if (trigger === "/" && item.id && typeof item.run === "function") editorRememberBlock(item.recentOf || item.id);

  if (item.markdown !== undefined) {
    //: **A file is not a `[[wiki link]]`.** Wiki links resolve by *name*
    //: against notes and documents; an image or an attachment has a url and
    //: no name to resolve, so an item like that carries the markdown it wants
    //: inserted and the opening `[[` the trigger left behind is removed
    //: first. Asked for as "cross-link everything: notes, documents, files,
    //: maps from anywhere", the picker covered two of the four.
    const at = textarea.selectionStart;
    const open = trigger === "[[" ? at - trigger.length : at;
    editorSplice(textarea, open, at, item.markdown, null);
  } else if (item.value !== undefined) {
    // A link target: close the brackets and step past them.
    const at = textarea.selectionStart;
    editorSplice(textarea, at, at, `${item.value}]]`, null);
  } else if (typeof item.run === "function") {
    item.run(textarea);
  }
}

function editorOpenMenu(textarea, trigger) {
  //: The word list the documents editor draws at the caret gives way.
  if (typeof hideDocComplete === "function") hideDocComplete();
  editorMenuState.open = true;
  editorMenuState.textarea = textarea;
  editorLinkBox(textarea, true);
  editorMenuState.trigger = trigger;
  editorMenuState.index = 0;
  const pane = $("editor-menu-preview");
  if (pane) delete pane.dataset.for;
  editorRefreshMenu();
}

// Recompute what the menu should show for whatever is currently before the
// caret. Called on every keystroke while open.
//: **In the chat box, the commands first** (INBOX 1300 C05, the owner: "I
//: wouldn't know the other's are there unless I scroll down quite far"):
//: they are what only this menu has; every other row is a button on the
//: dock as well. The first command sat at 443 px in a 384 px menu.
function editorBareSlashRows(context, recent, grouped) {
  const lead = context === "chat" || context === "agent" ? grouped.filter((row) => row.group === "Commands") : [];
  return [...lead, ...recent, ...grouped.filter((row) => !lead.includes(row))];
}

function editorRefreshMenu() {
  const { textarea, trigger } = editorMenuState;
  if (!textarea || !trigger) return editorCloseMenu();
  const token = editorTokenAt(textarea, trigger);
  if (!token) return editorCloseMenu();

  const changed = editorMenuState.query !== token.fragment;
  editorMenuState.start = token.start;
  editorMenuState.query = token.fragment;
  const context = editorSurfaceKind(textarea) || "note";
  let items;
  if (trigger === "/") {
    const all = editorCommands(context);
    if (token.fragment) {
      items = editorRankCommands(all, token.fragment).slice(0, 40);
    } else {
      //: **Everything, grouped, with what you used last first.** The old
      //: menu showed a curated shortlist with nothing typed, which is how
      //: most of its blocks went unfound ("limited in what they can do and
      //: how to use them"); with pinned group headings and Tab between
      //: groups the whole catalogue is one keystroke per group away.
      const byId = new Map(all.map((row) => [row.id, row]));
      const recent = editorRecentIds()
        .map((id) => byId.get(id))
        .filter(Boolean)
        .slice(0, EDITOR_RECENT_SHOWN)
        .map((row) => ({ ...row, group: "Recent", recentOf: row.id }));
      const order = (row) => {
        const at = EDITOR_GROUP_ORDER.indexOf(row.group);
        return at === -1 ? EDITOR_GROUP_ORDER.length : at;
      };
      const grouped = all
        .map((row, i) => ({ row, i }))
        .sort((a, b) => order(a.row) - order(b.row) || a.i - b.i)
        .map((entry) => entry.row);
      items = editorBareSlashRows(context, recent, grouped);
    }
  } else if (trigger === "```") {
    items = editorRankCommands(editorCodeLanguageRows(), token.fragment);
  } else {
    items = editorLinkMatches(token.fragment).slice(0, 20);
  }

  editorMenuState.items = items;
  //: A new query starts at the best match; the same query (a redraw) keeps
  //: the row the reader was on.
  editorMenuState.index = changed ? 0 : Math.min(editorMenuState.index, Math.max(0, items.length - 1));
  editorRenderMenu();
}

// ---------------------------------------------------------------------------
// Wiring: one delegated listener per event, for every surface at once
// ---------------------------------------------------------------------------

//: **Called, not only listened for.** A `<textarea>` raises `input` for every
//: character and this file has always hung the trigger check off that. The
//: engine does not: CodeMirror applies a typed character itself, through its
//: own transaction pipeline, and no bubbling `input` reaches this listener at
//: all. Measured, not reasoned: with the engine mounted the "/" menu and the
//: `[[` picker simply never opened, and nothing logged, which is this repo's
//: "a policy silently refusing the work" shape in the one place it is hardest
//: to notice, because both menus look like they are just not wanted yet.
//:
//: So the body is a function, and documents.js's update listener calls it for
//: the engine. One implementation, two ways in.
function editorHandleInput(textarea) {
  if (!textarea) return;
  if (!editorSurfaceKind(textarea)) return;

  if (editorMenuState.open && editorMenuState.textarea === textarea) {
    editorRefreshMenu();
    return;
  }
  // Not open yet: does what was just typed start a token?
  //
  //: "[[" is this menu's in every surface, the note box included (INBOX 430,
  //: the owner on the note box's own list: "this dropdown should show below
  //: the line being written in a separate popup panel like the / command
  //: menu, not below the textbox"). The note box had kept an older list of
  //: its own, `#wiki-suggest`, drawn in the flow under the whole box; it is
  //: gone, and the box has one mechanism for both triggers, placed at the
  //: caret by `editorPlaceMenu`.
  for (const trigger of ["/", "[["]) {
    if (editorTokenAt(textarea, trigger)) {
      if (trigger === "[[") {
        // Fetch documents once, then redraw, the list opens on notes alone
        // and gains documents a moment later rather than blocking on a fetch.
        if (editorDocumentCache === null) {
          editorDocumentCache = [];
          //: Paged to the end, same reason as the file cache above: a
          //: document missing from this list is a `[[link]]` the menu
          //: cannot offer, silently.
          apiPagedList("/documents", DOCUMENTS_PAGE_SIZE)
            .then((docs) => {
              editorDocumentCache = Array.isArray(docs) ? docs : [];
              if (editorMenuState.open) editorRefreshMenu();
            })
            .catch(() => {
              editorDocumentCache = [];
            });
        }
        //: Files and images the same way: the menu opens on what is already
        //: in memory and gains the rest a moment later, rather than making
        //: the first keystroke wait on two requests.
        if (editorFileCache === null) {
          editorFileCache = [];
          editorLoadFiles().then(() => {
            if (editorMenuState.open) editorRefreshMenu();
          });
        }
      }
      editorOpenMenu(textarea, trigger);
      return;
    }
  }
}

document.addEventListener("input", (event) => {
  //: The engine's own edits arrive through `editorHandleInput` above, called
  //: from documents.js's update listener. Anything from inside the view that
  //: *does* raise a DOM `input` (a paste, in some browsers) would otherwise
  //: run the check a second time and reopen a menu the first pass closed.
  if (typeof docEventFromCm === "function" && docEventFromCm(event.target)) return;
  editorHandleInput(editorSurfaceFor(event.target));
});

document.addEventListener(
  "keydown",
  (event) => {
    if (!editorMenuState.open) return;
    //: Compared as *surfaces*: the event target inside CodeMirror is whichever
    //: line element the caret is in, never the object the menu was opened on.
    const surface = editorSurfaceFor(event.target);
    if (surface !== editorMenuState.textarea) {
      //: **The same box under a new engine.** The note capture box is a
      //: textarea until the note engine mounts over it, which happens when
      //: the bundle lands after the first focus: a "/" typed in that gap
      //: opened the menu on the textarea, and every key after the mount came
      //: from the engine and was ignored here (measured: Tab wrote two
      //: spaces into the note with the menu still open). Same id, same box:
      //: the menu follows it.
      if (!surface || !editorMenuState.textarea || !surface.id || surface.id !== editorMenuState.textarea.id) return;
      editorMenuState.textarea = surface;
    }
    const { items } = editorMenuState;

    //: Arrows walk the rows (wrapping), Home and End jump to the ends, Tab
    //: and Shift+Tab jump to the first row of the next or previous group
    //: (Coda's gesture, and the only fast way through a menu of sixty rows),
    //: Enter chooses, Escape closes. Tab chooses instead in a list with one
    //: group, where there is nowhere to jump, which is what it always did in
    //: the `[[` picker.
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      if (!items.length) return;
      event.preventDefault();
      const last = items.length - 1;
      const next =
        event.key === "Home" ? 0
          : event.key === "End" ? last
            : (editorMenuState.index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      editorSetActive(next, true);
      return;
    }
    if (event.key === "Tab" && editorGroupStarts().length > 1) {
      event.preventDefault();
      event.stopPropagation();
      editorSetActive(editorNextGroupStart(event.shiftKey ? -1 : 1), true);
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      if (!items.length) return;
      event.preventDefault();
      // stopPropagation as well as preventDefault: the capture box submits on
      // Ctrl+Enter and the document editor has its own Enter handling, and
      // choosing from a menu must not also trigger the surface behind it.
      event.stopPropagation();
      editorRunItem(editorMenuState.index);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      editorCloseMenu("escape");
    }
  },
  true // capture phase, so the menu answers before the surface's own handlers
);

// Clicking anywhere else, or moving the caret with the mouse, dismisses it.
document.addEventListener("mousedown", (event) => {
  if (!editorMenuState.open) return;
  if ($("editor-menu")?.contains(event.target)) return;
  editorCloseMenu();
});

// Scrolling the *page* moves the caret out from under a menu anchored to it,
// so the menu closes. Scrolling *inside the menu itself* must not, reported
// directly: "the popup options for commands aren't scrollable and disappear
// when I try to scroll them". This listener is on the capture phase, so it saw
// the menu's own wheel-scroll before it reached the menu and shut it every
// time, which is exactly the shape of bug that makes a list look un-scrollable
// rather than merely short.
//:
//: **And it follows the caret rather than closing on every scroll** (INBOX
//: 421 c: "sometimes it doesnt open at all"). Typing the "/" that opens the
//: menu can itself scroll: the editor keeps the caret in view, so a "/" on
//: the last visible line scrolls the editor by a line, and that scroll closed
//: the menu the keystroke had just opened (measured at 390 wide: a "/" at the
//: end of a document opened nothing). The menu is re-placed at the caret on
//: the next frame, and closes only when the caret has left the window.
let editorFollowFrame = 0;
document.addEventListener(
  "scroll",
  (event) => {
    if (!editorMenuState.open) return;
    const menu = $("editor-menu");
    if (menu && (event.target === menu || menu.contains(event.target))) return;
    if (editorFollowFrame) return;
    editorFollowFrame = requestAnimationFrame(() => {
      editorFollowFrame = 0;
      const { textarea } = editorMenuState;
      if (!editorMenuState.open || !textarea) return;
      const at = editorCaretPoint(textarea);
      const gone = at.offscreen || at.top + at.lineHeight < 0 || at.top > window.innerHeight;
      if (gone) editorCloseMenu();
      else editorPositionMenu(textarea, true);
    });
  },
  true
);

window.addEventListener("resize", () => editorMenuState.open && editorCloseMenu());

// ---------------------------------------------------------------------------
// The selection toolbar
// ---------------------------------------------------------------------------
//
// Asked for with a link to Obsidian's editing-toolbar plugin: *"pease upgrade
// the way the toolbar works in everything to be like this obsidian toolbar
// plugin. Ive used it and it is great."*
//
// The thing that plugin actually changes is **where the buttons are**, not
// which ones exist: this app's fixed toolbar already has more of them. A bar
// that follows the text you selected puts formatting where you are looking,
// instead of at the top of a panel you may have scrolled a screen away from.
//
// Built on the two pieces that were already here: `editorCaretPoint` (a
// textarea has no Range, so the caret is measured with a mirror element) and
// `applyMarkdown` (documents.js), so this adds a *place*, not a second opinion
// about what `**` means. Nothing here knows any markdown.
const SELECTION_BAR_ACTIONS = [
  { md: "bold", label: "ph:text-b", title: "Bold (Ctrl+B)" },
  { md: "italic", label: "ph:text-italic", title: "Italic (Ctrl+I)" },
  { md: "strike", label: "ph:text-strikethrough", title: "Strikethrough" },
  { md: "highlight", label: "ph:highlighter", title: "Highlight" },
  { md: "code", label: "ph:code", title: "Inline code" },
  { md: "link", label: "ph:link", title: "Link" },
  { md: "h2", label: "ph:text-h", title: "Heading" },
  { md: "quote", label: "ph:quotes", title: "Quote" },
  { turn: true, label: "ph:swap", title: "Turn into" },
  //: **Not a formatting action, and it says so with a rule beside it.**
  //: REDESIGN.md §R7.1 item 1, quoted from the request: *"able to highlight
  //: text and say something in the chat and the agent gets the context of
  //: what is highlighted and cursor position."* It is the highest ratio of
  //: "feels capable" to work in that whole section, and this bar is already
  //: the thing on screen the moment a selection exists, a second control
  //: somewhere else would be a second thing to find.
  { ask: true, label: "ph:chat-teardrop-text", title: "Ask Atlas about this selection" },
  //: **The second half of that pair: change it here, rather than talk about
  //: it there.** Asking sends the selection to the chat and leaves the text
  //: alone; this rewrites the selection in place. They belong next to each
  //: other because the choice between them is the whole decision, and a
  //: selection is the moment it gets made. Document surfaces only: see
  //: `inlineAiAvailable`, so the button is skipped where it could not work.
  { inlineAi: true, label: "ph:sparkle", title: "Rewrite this with AI (Ctrl+J)" },
];

const selectionBarState = { textarea: null };

function selectionBarElement() {
  let bar = $("selection-bar");
  if (bar) return bar;
  //: Built once, lazily, rather than sitting in index.html: it belongs to this
  //: file's behaviour, and a hidden bar in the markup would be one more thing
  //: for the id/duplicate-listener lints to police for no gain.
  bar = document.createElement("div");
  bar.id = "selection-bar";
  bar.className = "selection-bar hidden";
  bar.setAttribute("role", "toolbar");
  bar.setAttribute("aria-label", "Format the selection");
  for (const action of SELECTION_BAR_ACTIONS) {
    if (action.ask) {
      //: A hairline, so "ask about this" does not read as a ninth way to
      //: change the text. Same separator the chat dock's control strip uses
      //: between its own groups.
      const rule = document.createElement("span");
      rule.className = "selection-bar-rule";
      rule.setAttribute("aria-hidden", "true");
      bar.appendChild(rule);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small icon-button";
    if (action.inlineAi) {
      button.dataset.inlineAi = "1";
      button.dataset.needsModel = "Rewriting with Atlas needs a model";
      button.dataset.modelOffer = "Ask Atlas about this selection, beside it, answers from your notes without one.";
    }
    if (action.md) button.dataset.md = action.md;
    if (action.turn) button.dataset.turn = "1";
    button.title = action.title;
    button.setAttribute("aria-label", action.title);
    setLabel(button, action.label);
    //: `mousedown`, not `click`, and prevented: a click would first move focus
    //: out of the textarea, and the browser drops the selection on the way, 
    //: so by the time the handler ran there would be nothing selected to wrap.
    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const textarea = selectionBarState.textarea;
      if (!textarea) return;
      if (action.turn) {
        if (typeof docTurnIntoMenu === "function") docTurnIntoMenu(textarea.id, button);
        return;
      }
      if (action.ask) {
        askAboutSelection(textarea);
        selectionBarHide();
        return;
      }
      if (action.inlineAi) {
        //: With no model this is the gate's offer (`data-model-offer`): the
        //: press says why, rather than opening a bar that cannot answer.
        if (button.getAttribute("aria-disabled") === "true") {
          openModelOffer(button);
          return;
        }
        //: The selection is read from the textarea *before* the bar takes
        //: focus, which `inlineAiOpen` does on its first two lines, the same
        //: reason this whole handler is on `mousedown`.
        inlineAiOpen(textarea);
        return;
      }
      applyMarkdown(action.md, textarea.id);
      //: Deliberately *not* hidden here. `applyMarkdown` leaves the text it
      //: wrapped selected, so the bar re-anchors to it on the next
      //: `selectionchange`, which is what lets bold-then-italic be two
      //: presses rather than a re-selection between them. Hiding it made the
      //: bar blink out and straight back in.
    });
    bar.appendChild(button);
  }
  document.body.appendChild(bar);
  return bar;
}

function selectionBarHide() {
  selectionBarState.textarea = null;
  $("selection-bar")?.classList.add("hidden");
}

function selectionBarShow(textarea) {
  const bar = selectionBarElement();
  selectionBarState.textarea = textarea;
  //: Shown only where it can run. A control that is present and refuses is
  //: worse than one that is absent: the first teaches that the feature is
  //: broken, the second that it belongs to documents.
  const magic = bar.querySelector("[data-inline-ai]");
  if (magic) magic.hidden = !inlineAiAvailable(textarea);
  //: **No prose formatting over code** (the owner, 2026-09-24, INBOX 409:
  //: bold, italic, highlight, heading and quote drawn over a .json file,
  //: where every one of them would write markdown into the code). A code
  //: document keeps the two actions that mean something there, ask Atlas and
  //: rewrite in place; the formatting eight and their rule are hidden.
  const code = editorSurfaceKind(textarea) === "document"
    && typeof docFileType === "function" && docFileType().previewable === false;
  for (const button of bar.querySelectorAll("[data-md], [data-turn], .selection-bar-rule")) button.hidden = code;
  const turn = bar.querySelector("[data-turn]");
  if (turn && !code) turn.hidden = typeof docTurnIntoMenu !== "function";
  //: **Never a second copy of the phone's formatting bar.** Below 600 the
  //: document has its own bar at the foot (`#doc-phone-bar`, a `.thumb-bar`),
  //: and this one drew the same Bold, Italic, Heading and Link again over the
  //: text, ten 44px targets in a 499px pill that ran 117px past a 390px
  //: window with Ask and Rewrite off its edge (measured, docphonebar.js).
  //: What the foot already carries is read off the foot itself, so the two
  //: cannot drift; what is left (strike, highlight, code, quote, ask,
  //: rewrite) fits the window.
  const foot = editorSurfaceKind(textarea) === "document" ? $("doc-phone-bar") : null;
  if (!code && foot && getComputedStyle(foot).display !== "none") {
    const onFoot = new Set([...foot.querySelectorAll("[data-md]")].map((b) => b.dataset.md));
    for (const button of bar.querySelectorAll("[data-md]")) button.hidden = onFoot.has(button.dataset.md);
  }
  bar.classList.remove("hidden");
  //: Anchored to the *start* of the selection, which is where the eye is when
  //: a selection is made left-to-right, and measured after the bar is visible
  //: so its size is real rather than zero.
  const { top, left, lineHeight } = editorCaretPoint(textarea);
  //: A bar that wrapped (CSS caps it at the window's width) is two rows, and
  //: a pill's round ends do not fit two rows of round buttons.
  const shown = [...bar.querySelectorAll("button")].filter((b) => !b.hidden);
  bar.classList.toggle("is-wrapped", shown.length > 1 && shown.at(-1).offsetTop > shown[0].offsetTop);
  const size = bar.getBoundingClientRect();
  const margin = 8;
  //: **The boundary is the editing pane, and now that is the surface itself.**
  //: This used to need a special case: the Live view gave every paragraph its
  //: own box, so the caret's box was the top of *that paragraph*, and the rule
  //: below read every selection in Live as "on the first line, flip the bar
  //: below it". Measured at the time: selecting inside the third paragraph put
  //: the bar at y=358 against a selection at y=328, under the words instead of
  //: above them. With one editor in every view the surface's own rectangle is
  //: the pane's, and the special case goes.
  const boxTop = textarea.getBoundingClientRect().top;
  let y = top - size.height - 6;
  //: **Above the line, unless that means on top of the fixed toolbar.** Every
  //: editing surface in this app has its own formatting row immediately above
  //: the textarea, so a selection on the *first* line put this bar straight
  //: over it: measured, and it read as two toolbars stacked rather than as a
  //: bar belonging to the selection. Below the line in that case: it covers
  //: the next line of the note instead, which is text you can scroll to and
  //: not a control you might press by mistake.
  if (y < Math.max(margin, boxTop)) y = top + (lineHeight || 20) + 6;
  let x = Math.max(margin, Math.min(left, window.innerWidth - size.width - margin));
  //: **A board's text is placed against the selection itself** (INBOX 817,
  //: the owner: the bar "stays where it opened" when the map pans, and can
  //: sit across the topic). The caret line above is right for a page that
  //: scrolls, where a line is a line; on a board the box moves under the bar
  //: with every pan and zoom frame (`wbZoomFrameWork` calls `selectionBarSync`
  //: once a frame), and a multi-line selection's first line is not its edge.
  //: Above the selection with an 8px gap, below it when there is no room
  //: above, so the bar never lies on the text being formatted.
  const onBoard = textarea.id === "wb-topic-edit" || textarea.id === "wb-text-edit";
  const live = onBoard && textarea.el?.isContentEditable ? window.getSelection() : null;
  const range = live?.rangeCount ? live.getRangeAt(0).getBoundingClientRect() : null;
  if (range && (range.width || range.height)) {
    const gap = 8;
    y = range.top - size.height - gap;
    if (y < margin) y = range.bottom + gap;
    if (y + size.height > window.innerHeight - margin) y = Math.max(margin, range.top - size.height - gap);
    x = Math.max(margin, Math.min(range.left, window.innerWidth - size.width - margin));
  }
  bar.style.top = `${Math.round(y)}px`;
  bar.style.left = `${Math.round(x)}px`;
}

//: One predicate, so the selection bar and the "/" menu cannot disagree about
//: what an editing surface is. They did: this used to be its own class check
//: while the "/" menu gated on `EDITOR_SURFACES` alone, which is how the live
//: view ended up with a selection bar and no slash menu.
function isEditorSurface(node) {
  return editorSurfaceKind(node) !== null;
}

function selectionBarSync() {
  //: The inline AI bar anchors to the same caret and leaves its answer
  //: *selected* on purpose, so without this the two bars stack on top of each
  //: other the moment an answer lands, and the one underneath is the one with
  //: Keep and Undo on it.
  if (inlineAiState.phase !== "idle") return selectionBarHide();
  //: **A caret in a plain box asks nothing of the adapters.** `selectionchange`
  //: fires when a composer takes focus, and resolving the surface fetched the
  //: whole Library bundle there (`editorSurfaceFor`) just to find that nothing
  //: was selected: the same long task `editorWarmSurfaceModule` waits out.
  const raw = document.activeElement;
  if (typeof asSurface !== "function" && raw && raw.selectionStart !== undefined && raw.selectionStart === raw.selectionEnd) {
    return selectionBarHide();
  }
  const active = editorSurfaceFor(document.activeElement);
  if (!isEditorSurface(active)) {
    return selectionBarHide();
  }
  //: A caret is not a selection. Nothing appears until there is text to act
  //: on, which is what keeps this from being a bar that hovers over the note
  //: while you type.
  if (active.selectionStart === active.selectionEnd) return selectionBarHide();
  selectionBarShow(active);
}

//: `selectionchange` is the one event that fires for *every* way a selection
//: can change, drag, shift+arrow, double-click, select-all, undo, where
//: mouseup/keyup each miss several. It fires on `document`, not the element.
document.addEventListener("selectionchange", selectionBarSync);
//: The bar is positioned in viewport coordinates against a caret that moves
//: when anything scrolls, so it re-anchors rather than drifting away from the
//: text it belongs to. Capture, because the scroller is usually a descendant.
document.addEventListener("scroll", () => selectionBarState.textarea && selectionBarSync(), true);
window.addEventListener("resize", () => selectionBarState.textarea && selectionBarSync());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && selectionBarState.textarea) selectionBarHide();
});

//: How much text either side of the selection travels with it. Enough that a
//: pronoun in the selection ("why does *it* do that?") has an antecedent, and
//: small enough that a selection made in a 40,000-character document does not
//: quietly become the whole document, the harness budgets tool *results*
//: (§R5 item 4) but the question itself is not a tool result, so nothing else
//: would bound this.
const SELECTION_CONTEXT_MARGIN = 240;

//: Where the selection sits, in a form the model can be told about and the
//: app can re-check later. `line`/`column` are 1-based because that is what
//: every editor in the world shows the user, and the number is going into a
//: chip they read.
function selectionContextFrom(textarea) {
  //: **One set of coordinates.** This used to translate a live-view
  //: paragraph's own offsets into the document's, because Live gave every
  //: paragraph its own box and left alone this would have told the model
  //: "line 2" for the last paragraph of a long document. DOCUMENTS_PLAN
  //: Phase 2 made Live and Source one editor, so a selection is already in
  //: the document's coordinates wherever it was made.
  return selectionOffsets(textarea, textarea.selectionStart, textarea.selectionEnd);
}

function selectionOffsets(textarea, start, end) {
  const value = textarea.value;
  const text = value.slice(start, end);
  const upToCaret = value.slice(0, end);
  const line = upToCaret.split("\n").length;
  const column = end - (upToCaret.lastIndexOf("\n") + 1) + 1;
  return {
    surfaceId: textarea.id,
    kind: editorSurfaceKind(textarea) || "note",
    start,
    end,
    text,
    line,
    column,
    before: value.slice(Math.max(0, start - SELECTION_CONTEXT_MARGIN), start),
    after: value.slice(end, end + SELECTION_CONTEXT_MARGIN),
  };
}

//: The label on the chip, and the only place that knows which surface belongs
//: to which thing. `entry-content` deliberately has no id: it is a note being
//: written that does not exist yet, and a selection from it is still worth
//: asking about: the text is what matters, not a row in the database.
function selectionContextSource(surfaceId) {
  if (surfaceId === "doc-content") {
    const doc = typeof currentDoc !== "undefined" ? currentDoc : null;
    return { title: doc?.title || "this document", entityKind: "document", entityId: doc?.id ?? null };
  }
  if (surfaceId === "entry-edit-content") {
    const entry =
      typeof allEntries !== "undefined" && typeof editingId !== "undefined"
        ? allEntries.find((e) => e.id === editingId)
        : null;
    return {
      title: entry ? noteLabel(entry, 40) : "this note",
      entityKind: "note",
      entityId: entry?.id ?? null,
    };
  }
  return { title: "the note you're writing", entityKind: "note", entityId: null };
}

function askAboutSelection(textarea) {
  //: The *resolved* surface, not the textarea that was focused: a live-view
  //: block reports itself as `doc-content` (see `selectionContextFrom`), and
  //: looking the label up by the block's own id would call a document "the
  //: note you're writing".
  const where = selectionContextFrom(textarea);
  const context = { ...where, ...selectionContextSource(where.surfaceId) };
  if (!context.text.trim()) return;
  attachSelectionContext(context);
}

// ---------------------------------------------------------------------------
// Create-on-miss: a link to something that does not exist yet
// ---------------------------------------------------------------------------

// confirmDialog's three-way sibling. Built here rather than generalising
// confirmDialog because that function's contract is a boolean, and widening it
// to return a string would mean auditing all of its call sites for a truthy
// check that now passes on "cancel".
//
// The DOM shape, the captured Escape handler, the backdrop click and the
// "focus the safe option, not the committing one" rule are all copied from
// confirmDialog deliberately: a second dialog that behaves differently from
// the app's own is worse than no dialog.
function editorChoiceDialog(message, choices) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay";
    overlay.setAttribute("role", "dialog");
    // aria-modal, because this one genuinely is: the page behind it is inert
    // until it is answered. (The focus trap keys off exactly this attribute, 
    // see HANDOVER.md on the 13 anchored popovers that must NOT carry it.)
    overlay.setAttribute("aria-modal", "true");

    const card = document.createElement("div");
    card.className = "card modal-card confirm-card";
    const text = document.createElement("p");
    text.className = "confirm-text";
    for (const part of String(message).split(/\n{2,}/)) {
      const line = document.createElement("span");
      line.textContent = part;
      text.append(line, document.createElement("br"));
    }
    const row = document.createElement("div");
    row.className = "row confirm-actions";

    let settled = false;
    const close = (answer) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      returnFocus?.focus?.();
      resolve(answer);
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close(null);
      }
    };

    const returnFocus = document.activeElement;
    const cancel = smallButton("Cancel", "Leave the link unresolved", () => close(null));
    row.appendChild(cancel);
    for (const choice of choices) {
      row.appendChild(
        smallButton(choice.label, choice.title || choice.label, () => close(choice.value), false)
      );
    }
    card.append(text, row);
    overlay.appendChild(card);
    wireBackdropClose(overlay, () => close(null));
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(overlay);
    // Cancel takes focus: a stray Enter must not be the thing that creates a
    // note, the same reasoning confirmDialog uses for its destructive button.
    cancel.focus();
  });
}

// Clicking a [[link]] whose target does not exist yet.
//
// A link you typed on purpose is the clearest possible statement that the
// thing ought to exist, so the dead end becomes an offer. Creation stays
// user-confirmed and never happens in the background: silently materialising
// notes from typos is precisely the failure mode this app's autonomous agent
// is deliberately conservative about, and a notebook that grows notes you did
// not ask for is worse than one that makes you click twice.
async function offerToCreateWikiTarget(name) {
  //: A board reference keeps its bar (it is read just below); any other link
  //: offers to create the note its target names, not `Target|Shown`.
  const wanted = String(wikiLinkTarget(name) || "").trim();
  if (!wanted) return;

  //: **A board reference is not a name that can be created** (INBOX 309).
  //: `[[board:12|House jobs]]` addresses one board by id, and the only
  //: reason it fails to resolve is that the board has gone. Offering to
  //: create "a note beginning board:12|House jobs" would make a note nobody
  //: wants and still leave the link dead, which is the dead end this
  //: function exists to remove, not a new one.
  const ref = boardEmbedRef(wanted);
  if (ref) {
    toast(`\u201c${ref.title || "That board"}\u201d is no longer in your notebook.`);
    return;
  }

  const choice = await editorChoiceDialog(
    `Nothing called “${wanted}” exists yet.\n\nCreate it, and this link will resolve to it.`,
    [
      { value: "note", label: "Create note", title: `Start a note beginning "${wanted}"` },
      { value: "document", label: "Create document", title: `Start a document titled "${wanted}"` },
    ]
  );
  if (!choice) return;

  try {
    if (choice === "note") {
      // The note's content opens with the link text, because that is what
      // resolution matches on: a note created here that did not start with
      // the name would leave the very link that made it still unresolved.
      const entry = await apiJson("/entries", {
        method: "POST",
        body: JSON.stringify({ content: `${wanted}\n\n`, defer_filing: true }),
      });
      await refreshEntries([entry.id]);
      pushEntryCreateUndo(entry, `Created the note “${wanted}”`);
      toast(`Created “${wanted}”.`);
      if (entry?.id) flashEntry(entry.id);
      return;
    }

    const doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: wanted, content: "" }),
    });
    // Keep the resolver's cache honest, or the link stays unresolved until
    // something else happens to refetch documents.
    if (doc) {
      editorDocumentCache = [...(editorDocumentCache || []), doc];
      offerCreateUndo(doc);
      toast(`Created “${wanted}”.`);
      openDocument(doc.id);
    }
  } catch (error) {
    toast(error.message || "Could not create that.", true);
  }
}

// ---------------------------------------------------------------------------
// Syntax highlighting for the file viewer (REDESIGN.md §R7.1 item 3)
// ---------------------------------------------------------------------------
//
// **Written here rather than pulled in.** This app is offline by construction
//, there is no CDN to load highlight.js from and no bundler to vendor it
// with, and a 900 KB library shipped for one panel would be the largest
// single asset in the project. Four token classes cover what makes code
// readable at a glance: comments recede, strings and numbers stand out from
// identifiers, keywords carry the structure. That is most of the value of a
// full grammar for none of the weight.
//
// **The colours are existing semantic tokens, not new ones.** `--muted` for
// comments, `--ok` for strings, `--warn` for numbers, `--accent` for
// keywords: each already has a light and a dark value, so this follows the
// theme for free and adds nothing for `tests/test_style_scale.py` to police.
//
// **Every pattern here is linear.** CI runs CodeQL, which has caught a real
// polynomial-ReDoS in this repo before; the string rules use the
// `[^"\\\n]|\\.` shape whose alternatives are disjoint on their first
// character, and nothing nests a quantifier inside a quantifier.

//: What a suffix is written in. The value is the profile name below; a suffix
//: that is missing gets `generic`, which still finds strings, numbers and
//: both comment styles: worth having for a `.conf` nobody thought about.
const CODE_LANGUAGES = {
  js: "c", mjs: "c", cjs: "c", ts: "c", tsx: "c", jsx: "c", java: "c",
  c: "c", h: "c", cpp: "c", hpp: "c", cs: "c", go: "c", rs: "c", swift: "c",
  kt: "c", php: "c", scss: "c", css: "css",
  py: "hash", rb: "hash", sh: "hash", bash: "hash", zsh: "hash",
  yaml: "hash", yml: "hash", toml: "hash", ini: "hash", cfg: "hash", r: "hash",
  sql: "sql", json: "json", html: "markup", htm: "markup", xml: "markup",
};

//: Keywords worth colouring, per family. Deliberately not exhaustive: a
//: keyword list that tries to be complete is a maintenance burden that buys
//: nothing: what the eye uses is the *shape* of the control flow, and these
//: are the words that carry it.
const CODE_KEYWORDS = {
  c: "abstract async await break case catch class const continue default delete do else enum export extends false final finally for from function goto if implements import in instanceof interface let new null package private protected public return static struct super switch this throw throws true try typeof var void while yield",
  hash: "and as assert async await break case class continue def del elif else end except false finally for from global if import in is lambda module nil none not or pass raise return self true try unless until while with yield",
  sql: "add all alter and as asc between by case create delete desc distinct drop else exists from group having in inner insert into is join left limit not null on or order outer right select set table then union update values where",
  json: "true false null",
  css: "important media import supports keyframes from to and not only",
  markup: "",
  generic: "false null true",
};

//: One scanner, built once per family. Order inside the alternation *is* the
//: precedence: comments and strings first, so a `#` inside a string or the
//: word `if` inside a comment is not re-coloured as something else.
const codeScanners = new Map();

// ---------------------------------------------------------------------------
// Inline AI: the AI at the caret, not in a panel
// ---------------------------------------------------------------------------
//
// Asked for directly: *"the agent or ai needs to be more directly integrated
// into the documents."* Everything the document editor already had, AI edit,
// extract notes, rephrase, translate, check with AI, is a *panel*: you leave
// the text, open a side pane, ask, read, accept, come back. That is a fine
// place for "review this whole document" and the wrong place for "make this
// sentence shorter", which is the thing writers actually do fifty times an
// hour. Notion answers it with `/ai`, Cursor with Ctrl+K, Word with the
// rewrite popover; all three put the request *where the caret is* and put the
// result *into the text*, with one keystroke to keep it and one to undo it.
//
// Three deliberate constraints, each of which is why this is ~200 lines and
// not a second AI panel:
//
// 1. **No new endpoint.** `POST /documents/{id}/ai-edit` already takes an
//    instruction, an optional selection and a verb, already returns the
//    revised text without saving it, and already reports `ollama_running`
//    false with a message when the model is not there. A third code path to
//    the same model would be a third place for the offline message, the
//    thinking trace and the token budget to drift.
// 2. **Nothing is written until it is accepted, and "accepted" is the
//    default, not a modal.** The result goes straight into the text, selected,
//    with Keep / Try again / Undo underneath. Undo restores the exact prior
//    value and caret, because `before` is captured whole; a diff would be
//    prettier and would not survive the AI reflowing a paragraph.
// 3. **Document surfaces only.** The endpoint needs a document id, and the
//    capture box has none. The command and the shortcut both check, rather
//    than opening a bar that would fail on submit.

const inlineAiState = {
  textarea: null,
  //: The range the answer replaces, captured when the bar opens. Held rather
  //: than re-read on submit because clicking into the bar's own input moves
  //: focus out of the textarea, and several browsers drop the selection on the
  //: way: the same trap `selectionBarElement` documents for `mousedown`.
  start: 0,
  end: 0,
  //: The whole textarea value before anything was inserted. Undo restores this
  //: verbatim. Cheap: a document big enough for this to matter is already
  //: being held in `.value` twice by the live view.
  before: "",
  //: The instruction, kept so "Try again" does not make you retype it.
  instruction: "",
  phase: "idle", // idle | asking | working | review
  controller: null,
};

//: The bar is one element reused for every invocation, built lazily for the
//: same reason `selectionBarElement` is: it belongs to this file's behaviour,
//: and a hidden copy in index.html would be one more thing for the duplicate-id
//: and duplicate-listener lints to police for nothing.
function inlineAiElement() {
  let bar = $("inline-ai");
  if (bar) return bar;

  bar = document.createElement("div");
  bar.id = "inline-ai";
  bar.className = "inline-ai hidden";
  bar.setAttribute("role", "dialog");
  bar.setAttribute("aria-label", "Ask Atlas to write here");

  const row = document.createElement("div");
  row.className = "inline-ai-row";

  const icon = document.createElement("span");
  icon.className = "inline-ai-icon";
  icon.setAttribute("aria-hidden", "true");
  setLabel(icon, "ph:sparkle");
  row.appendChild(icon);

  const input = document.createElement("input");
  input.id = "inline-ai-input";
  input.className = "inline-ai-input";
  input.type = "text";
  input.autocomplete = "off";
  input.setAttribute("aria-label", "What should Atlas do here?");
  row.appendChild(input);

  const run = document.createElement("button");
  run.id = "inline-ai-run";
  run.type = "button";
  run.className = "primary small";
  run.textContent = "Ask";
  run.addEventListener("click", () => inlineAiSubmit());
  row.appendChild(run);

  const close = document.createElement("button");
  close.id = "inline-ai-close";
  close.type = "button";
  close.className = "ghost small icon-button";
  close.title = "Close (Esc)";
  close.setAttribute("aria-label", "Close");
  setLabel(close, "ph:x");
  close.addEventListener("click", () => inlineAiClose());
  row.appendChild(close);

  bar.appendChild(row);

  //: The scope line. Without it the bar is a text field floating over a
  //: document with no statement of what it is about to change, which is the
  //: one thing a writer needs to know before pressing Enter.
  const scope = document.createElement("p");
  scope.id = "inline-ai-scope";
  scope.className = "inline-ai-scope";
  bar.appendChild(scope);

  const review = document.createElement("div");
  review.id = "inline-ai-review";
  review.className = "inline-ai-review hidden";
  for (const [act, label, cls] of [
    ["keep", "Keep", "primary small"],
    ["retry", "Try again", "ghost small"],
    ["undo", "Undo", "ghost small"],
  ]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = cls;
    button.dataset.act = act;
    button.textContent = label;
    button.addEventListener("click", () => {
      if (act === "keep") inlineAiClose();
      else if (act === "undo") inlineAiUndo();
      else inlineAiRetry();
    });
    review.appendChild(button);
  }
  bar.appendChild(review);

  document.body.appendChild(bar);
  return bar;
}

//: Anchored the same way the "/" menu is, and for the same reason: a bar that
//: opens at the top of a full-height document editor reads as belonging to the
//: toolbar rather than to the sentence you were writing. Flips above the line
//: when there is no room below, and is clamped into the viewport on both axes.
function inlineAiPosition() {
  const bar = $("inline-ai");
  const textarea = inlineAiState.textarea;
  if (!bar || !textarea) return;
  const { top, left, lineHeight } = editorCaretPoint(textarea);
  const size = bar.getBoundingClientRect();
  const margin = 8;
  let y = top + (lineHeight || 20) + 6;
  if (y + size.height > window.innerHeight - margin) {
    const above = top - size.height - 6;
    y = above > margin ? above : Math.max(margin, window.innerHeight - size.height - margin);
  }
  const x = Math.max(margin, Math.min(left, window.innerWidth - size.width - margin));
  bar.style.top = `${Math.round(y)}px`;
  bar.style.left = `${Math.round(x)}px`;
}

//: What the bar says it is about to do. Two shapes, because "write something
//: here" and "change this" are different requests and a single placeholder
//: that covers both ("Ask the AI…") tells you nothing about which one you are
//: making.
function inlineAiDescribeScope() {
  const { before, start, end } = inlineAiState;
  const selected = before.slice(start, end);
  const scope = $("inline-ai-scope");
  const input = $("inline-ai-input");
  if (!scope || !input) return;
  //: A code document is spoken to in code's words (the owner, 2026-10-11):
  //: lines, not words, and code asks, not "fix the grammar".
  const code = inlineAiIsCode();
  if (selected.trim()) {
    const count = code ? selected.replace(/\n$/, "").split("\n").length : selected.trim().split(/\s+/).length;
    const unit = code ? (count === 1 ? "line" : `${count} lines`) : (count === 1 ? "word" : `${count} words`);
    scope.textContent = `Rewrites the ${unit} you selected. Enter to ask, Esc to cancel.`;
    input.placeholder = code ? "Explain, simplify, add types…" : "Tighten this / fix the grammar / make it formal…";
  } else {
    scope.textContent = code ? "Writes code at the cursor. Enter to ask, Esc to cancel." : "Writes at the cursor. Enter to ask, Esc to cancel.";
    input.placeholder = code ? "A function that… / a test for…" : "Write an intro paragraph / a table of the options…";
  }
  inlineAiSyncModel();
}

function inlineAiIsCode() {
  return inlineAiState.textarea?.id === "doc-content" && typeof docFileType === "function" && !docFileType().previewable;
}

//: **With no model the bar stays, disabled, with the reason** (DOCUMENTS_PLAN
//: decision, 2026-10-11: never hidden). The field is read-only and says so,
//: and Ask is the gate's offer: a press says why and what works now, with
//: Set up a model. A model connecting gives both back (`mm-model-gate`).
function inlineAiSyncModel() {
  const input = $("inline-ai-input");
  const run = $("inline-ai-run");
  if (!input || !run) return;
  const off = aiIsOff();
  run.dataset.needsModel = "Rewriting with Atlas needs a model";
  run.dataset.modelOffer = inlineAiIsCode()
    ? "Quick fix (Alt+Enter), Format (Shift+Alt+F) and Find usages work without one."
    : "The spelling and grammar fixes, find and the outline work without one.";
  input.readOnly = off;
  input.setAttribute("aria-disabled", String(off));
  if (off) {
    input.placeholder = "Needs a model: connect one in Settings";
    input.title = `${run.dataset.needsModel}. ${AI_OFFLINE_HINT}.`;
  } else {
    input.removeAttribute("title");
  }
  if (off) run.setAttribute("aria-disabled", "true");
  else run.removeAttribute("aria-disabled");
}

document.addEventListener("mm-model-gate", () => {
  if (inlineAiState.textarea && inlineAiState.phase === "asking") inlineAiDescribeScope();
});

//: True when this surface can reach `POST /documents/{id}/ai-edit`, a
//: document textarea *and* a document actually open. Checked by both doors
//: (the "/" command and the shortcut) rather than letting the bar open and
//: fail on submit, which is the shape that teaches people a feature is broken.
function inlineAiAvailable(textarea) {
  if (editorSurfaceKind(textarea) !== "document") return false;
  return Boolean(typeof currentDoc !== "undefined" && currentDoc && currentDoc.id);
}

function inlineAiOpen(textarea, instruction = "") {
  if (!inlineAiAvailable(textarea)) {
    toast("Open a document first, inline AI writes into the document you're editing.");
    return;
  }
  const bar = inlineAiElement();
  inlineAiState.textarea = textarea;
  inlineAiState.start = textarea.selectionStart;
  inlineAiState.end = textarea.selectionEnd;
  inlineAiState.before = textarea.value;
  inlineAiState.instruction = instruction;
  inlineAiState.phase = "asking";

  //: The selection bar and this bar both anchor to the caret, so they would
  //: sit on top of each other the moment this opens over a selection.
  selectionBarHide();

  bar.classList.remove("hidden");
  $("inline-ai-review").classList.add("hidden");
  const input = $("inline-ai-input");
  input.disabled = false;
  input.value = instruction;
  setBusy($("inline-ai-run"), false);
  inlineAiDescribeScope();
  inlineAiPosition();
  input.focus();
  input.select();
}

//: Closing keeps whatever is in the text. That is deliberate and it is the
//: same choice every editor with this feature makes: the result is already
//: visible in the document, so the surprising outcome would be it vanishing
//: when the bar goes away. Undo is a button, and the app's own Ctrl+Z still
//: works on the textarea afterwards.
function inlineAiClose() {
  const textarea = inlineAiState.textarea;
  inlineAiState.controller?.abort();
  inlineAiState.controller = null;
  inlineAiState.textarea = null;
  inlineAiState.phase = "idle";
  $("inline-ai")?.classList.add("hidden");
  //: Focus goes back to the text, not to whatever the browser picks. Without
  //: this, dismissing the bar leaves the caret nowhere and the next keystroke
  //: is lost.
  textarea?.focus();
}

function inlineAiUndo() {
  const { textarea, before, start, end } = inlineAiState;
  if (!textarea) return inlineAiClose();
  textarea.value = before;
  textarea.setSelectionRange(start, end);
  editorNotifyHost(textarea);
  inlineAiClose();
}

function inlineAiRetry() {
  const { textarea, before, start, end, instruction } = inlineAiState;
  if (!textarea) return;
  //: Put the text back *before* re-asking, or the second answer is written on
  //: top of the first and the third on top of that.
  textarea.value = before;
  textarea.setSelectionRange(start, end);
  editorNotifyHost(textarea);
  inlineAiOpen(textarea, instruction);
}

async function inlineAiSubmit() {
  if (inlineAiState.phase === "working") return;
  const { textarea, start, end, before } = inlineAiState;
  if (!textarea) return;
  if (aiIsOff()) return openModelOffer($("inline-ai-run"));
  const instruction = $("inline-ai-input").value.trim();
  const selection = before.slice(start, end);
  //: "Write" needs an instruction: there is nothing else to go on. "Edit"
  //: does too: a selection alone says *what*, never *what to do to it*.
  if (!instruction) {
    $("inline-ai-scope").textContent = "Say what you'd like: for example, “make this two sentences”.";
    $("inline-ai-input").focus();
    return;
  }
  inlineAiState.instruction = instruction;
  inlineAiState.phase = "working";
  const run = $("inline-ai-run");
  setBusy(run, true, "Writing…");
  $("inline-ai-input").disabled = true;
  $("inline-ai-scope").textContent = "Thinking locally… Esc to cancel.";

  const controller = new AbortController();
  inlineAiState.controller = controller;
  try {
    const data = await apiJson(`/documents/${currentDoc.id}/ai-edit`, {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({
        instruction,
        selection,
        verb: selection.trim() ? "edit" : "write",
      }),
    });
    //: The model is not running. Say so *in the bar* and leave it open with
    //: the instruction intact, rather than closing and firing a toast the
    //: user has to read somewhere else while their sentence is gone.
    if (data.ollama_running === false) {
      inlineAiState.phase = "asking";
      setBusy(run, false);
      $("inline-ai-input").disabled = false;
      $("inline-ai-scope").textContent = data.message || "The local model isn't running.";
      inlineAiPosition();
      return;
    }
    const revised = String(data.revised ?? "");
    if (!revised.trim()) {
      inlineAiState.phase = "asking";
      setBusy(run, false);
      $("inline-ai-input").disabled = false;
      $("inline-ai-scope").textContent = "The model returned nothing. Try asking differently.";
      return;
    }
    //: `replaced_selection` comes from the server rather than being inferred
    //: here, because the server is what decided whether the selection or the
    //: whole document was the target, inferring it a second time is how the
    //: two would drift.
    const to = data.replaced_selection ? end : start;
    editorSplice(textarea, start, to, revised, { from: 0, to: revised.length });
    //: The inserted text ends up *selected*. That is the highlight, a
    //: textarea cannot paint a range any other way, and it also means the
    //: next thing typed replaces it, which is what "try it and see" should
    //: feel like.
    inlineAiState.phase = "review";
    $("inline-ai-input").disabled = false;
    $("inline-ai-review").classList.remove("hidden");
    $("inline-ai-scope").textContent =
      data.thinking ? `Done. ${data.thinking}` : "Done: keep it, ask again, or undo.";
    setBusy(run, false);
    inlineAiPosition();
    //: Focus the primary action, so Enter keeps and Esc keeps-and-closes. The
    //: textarea keeps the selection either way.
    $("inline-ai-review").querySelector('[data-act="keep"]')?.focus();
  } catch (error) {
    if (controller.signal.aborted) return;
    inlineAiState.phase = "asking";
    setBusy(run, false);
    $("inline-ai-input").disabled = false;
    $("inline-ai-scope").textContent = error?.message || "That didn't work. Try again.";
  } finally {
    if (inlineAiState.controller === controller) inlineAiState.controller = null;
  }
}

//: Enter submits, Esc dismisses, handled on the bar rather than globally so
//: neither key is stolen from the document behind it.
document.addEventListener("keydown", (event) => {
  if (inlineAiState.phase === "idle") return;
  const bar = $("inline-ai");
  if (!bar || bar.classList.contains("hidden")) return;
  if (!bar.contains(event.target)) return;
  if (event.key === "Enter" && event.target.id === "inline-ai-input") {
    event.preventDefault();
    inlineAiSubmit();
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    //: Esc while the model is still writing cancels the request and leaves the
    //: document untouched; Esc afterwards keeps the result, matching the
    //: "closing keeps" rule above.
    if (inlineAiState.phase === "working") {
      inlineAiState.controller?.abort();
      inlineAiClose();
      return;
    }
    inlineAiClose();
  }
});

//: Clicking away keeps the result and closes, the same as Esc. Not on
//: `mousedown` inside the bar, obviously, and not while the model is writing, 
//: a stray click should not throw away work that is seconds from arriving.
document.addEventListener("mousedown", (event) => {
  if (inlineAiState.phase === "idle" || inlineAiState.phase === "working") return;
  const bar = $("inline-ai");
  if (!bar || bar.contains(event.target)) return;
  //: **Not the press that opened it.** The selection bar's sparkle opens this
  //: on `mousedown`, and that same event then bubbles here from a target
  //: outside this bar, so the rewrite closed in the instant it opened (the
  //: owner, 2026-09-24: "doesnt work or appear to do anything"; traced as
  //: open, then close, from one press).
  if (event.target.closest?.(".selection-bar")) return;
  inlineAiClose();
});

window.addEventListener("resize", () => inlineAiState.textarea && inlineAiPosition());
