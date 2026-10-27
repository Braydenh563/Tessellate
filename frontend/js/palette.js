// palette.js: the popup agent over every tab (Ctrl+K), its twelve starters,
// its turns, its source previews and its conversation menu (split out of
// app.js, the sixth boot-time file after editor.js, dashboard.js,
// timeline.js and settings.js).
//
// Why now: `tests/test_static_compression.py` bounds the gzipped app.js, and
// on 2026-09-24 it went red again at 752,031 bytes after the catalogue's deep
// links landed. The test's own comment says the answer is the next surface
// out of app.js, not a fourth number, so this is that surface. Moved
// verbatim: every line below this header is the text app.js had between
// "// --- Global Command Palette (Ctrl+K) ---" and "// --- spaces".
//
// Loaded after timeline.js and before settings.js (see index.html). Every
// top-level line here reads only what app.js, editor.js, dashboard.js and
// timeline.js have already defined (`$`, `kebabMenu` and the rest) or this
// file's own names. The reverse direction was checked by grepping every name
// this file declares against every other frontend file: app.js calls
// `toggleAgentPalette`, `cmdPaletteOverlay` and `cmdPaletteResults` only
// inside functions and listener closures (the shortcuts table's `askAgent`,
// the status-bar agent button, the catalogue's "Popup agent" row, the
// tab-jump chord), and settings.js reads `agentCurrentTab` behind a `typeof`
// guard, so nothing reaches into this file at parse time.

// --- Global Command Palette (Ctrl+K) ---

//: **The popup agent's twelve starters** (CHAT_PLAN.md decision 9). Four was
//: the count before, and the owner's report was not that they were wrong but
//: that they were all there was: "just defaults to one of the sentence
//: starters", because the things actually wanted of an agent that floats over
//: every tab (make a note of this, remind me, find, summarise the open note,
//: what changed today) were not offered and typing them out is slower than
//: doing the job by hand.
//:
//: Grouped by verb, and each one is a verb with a slot rather than a finished
//: sentence: CHAT_PLAN's research section, from Raycast, where a starter that
//: reads "Remind me to ___" is picked far more often than the same action
//: written as a question. A starter whose text ends in a space is a stem: it
//: is put in the box with the caret after it and waits. One that does not is
//: complete and runs on the press.
const AGENT_STARTERS = [
  { group: "Capture", label: "Make a note of…", text: "Make a note of " },
  { group: "Capture", label: "Add to today's note…", text: "Add to today's note: " },
  { group: "Find", label: "Notes about…", text: "Find my notes about " },
  { group: "Find", label: "What did I write this week?", text: "What did I write this week?" },
  { group: "Find", label: "Open the note about…", text: "Open the note about " },
  { group: "Summarise", label: "The open note", text: "Summarise the note I have open." },
  { group: "Summarise", label: "My week", text: "Summarise what I wrote this week." },
  { group: "Summarise", label: "This conversation", text: "Summarise this conversation." },
  { group: "Remind", label: "Remind me to…", text: "Remind me to " },
  { group: "Remind", label: "What is due?", text: "What is due?" },
  { group: "Do", label: "Tag my untagged notes", text: "Tag my untagged notes." },
  { group: "Do", label: "Link related notes", text: "Link notes that belong together." },
];

//: One glyph per family, and the two groups that are not families of their own
//: take the shape of what they are: the tab group is a place, the recents are a
//: clock. The icons live here rather than on each row of the table above
//: because an icon belongs to the group, and a table that repeats it twelve
//: times is a table with twelve chances to disagree with itself.
const AGENT_STARTER_ICONS = {
  Capture: "note-pencil",
  Find: "magnifying-glass",
  Summarise: "text-align-left",
  Remind: "bell",
  Do: "lightning",
};

//: **And the ones that only make sense where you are** (INBOX 190: "it needs
//: to be more versatile and usable across the whole app, the user should be
//: able to use it as the guiding hand"). The twelve above are the agent's
//: whole repertoire wherever it is opened, which is right for a panel that
//: floats over everything and wrong as the *first* thing offered: opened over
//: a document, "Tag my untagged notes" is the least likely thing anybody
//: wants, and "summarise this document" was not on the list at all.
//:
//: So each tab names two, shown first under the tab's own name, and the
//: twelve follow unchanged. Two rather than five: a starter list long enough
//: to read is a starter list nobody reads, and the box is right there.
const AGENT_TAB_STARTERS = {
  dashboard: [
    { label: "What changed today?", text: "What changed in my notebook today?" },
    { label: "What should I pick up?", text: "What loose ends should I pick up next?" },
  ],
  notes: [
    { label: "Summarise what I have open", text: "Summarise the note I have open." },
    { label: "Tag this note", text: "Suggest tags for the note I have open." },
  ],
  chat: [
    { label: "Summarise this conversation", text: "Summarise this conversation." },
    { label: "File the last answer", text: "Save the last answer as a note." },
  ],
  graph: [
    { label: "What links to this?", text: "What is linked to the note I have open?" },
    { label: "Link related notes", text: "Link notes that belong together." },
  ],
  library: [
    { label: "Summarise what I have open", text: "Summarise the document or board I have open." },
    { label: "What is in here?", text: "What is in the board or map I have open?" },
  ],
  documents: [
    { label: "Summarise this document", text: "Summarise the document I have open." },
    { label: "Pull out the key points", text: "List the key points of the document I have open." },
  ],
  timeline: [
    { label: "What did I write this week?", text: "What did I write this week?" },
    { label: "What changed today?", text: "What changed in my notebook today?" },
  ],
  reminders: [
    { label: "What is due?", text: "What is due?" },
    { label: "Remind me to…", text: "Remind me to " },
  ],
};

//: Which tab the palette is floating over. `switchTab` keeps this in
//: `localStorage` (it is also how the app restores the last tab on a reload),
//: and Documents is its own surface inside the Library tab, so it is asked
//: for separately: a starter offering to summarise "the document I have open"
//: is only sensible where a document actually is open.
function agentCurrentTab() {
  if (!$("tab-documents")?.classList.contains("hidden")) return "documents";
  const tab = (() => {
    try {
      return prefs.get("activeTab", null);
    } catch {
      return null;
    }
  })();
  return AGENT_TAB_STARTERS[tab] ? tab : "notes";
}

//: The tab's own name, taken from the tab strip rather than written out a
//: second time here: the strip is what the reader is looking at, and two
//: copies of a name are two names as soon as one is renamed.
function agentTabLabel(tab) {
  if (tab === "documents") return "Documents";
  const label = document.querySelector(`[data-tab="${tab}"] .tab-label`);
  return (label?.textContent || tab).trim();
}

//: The three most recently used, offered first (the same research note: a
//: quick-action panel that does not remember makes you re-find the one thing
//: you always do). Per browser, in `localStorage`, because it is a habit of
//: this window rather than a fact about the notebook.
const AGENT_STARTERS_RECENT_KEY = "agentStartersRecent";
const AGENT_STARTERS_RECENT_MAX = 3;

function agentStarterRecents() {
  let texts = [];
  try {
    texts = prefs.json(AGENT_STARTERS_RECENT_KEY, []);
  } catch {
    return [];
  }
  if (!Array.isArray(texts)) return [];
  //: Resolved against the table rather than replayed from storage, so a
  //: starter whose wording changed comes back with the new wording, and one
  //: that was removed disappears instead of lingering as a dead chip.
  return texts
    .map((text) => AGENT_STARTERS.find((starter) => starter.text === text))
    .filter(Boolean)
    .slice(0, AGENT_STARTERS_RECENT_MAX);
}

function rememberAgentStarter(text) {
  if (!AGENT_STARTERS.some((starter) => starter.text === text)) return;
  const kept = [text, ...agentStarterRecents().map((s) => s.text).filter((t) => t !== text)];
  try {
    prefs.set(
      AGENT_STARTERS_RECENT_KEY,
      JSON.stringify(kept.slice(0, AGENT_STARTERS_RECENT_MAX))
    );
  } catch {
    /* a browser refusing storage is not a reason to refuse the starter */
  }
}

//: **The acts, from the registry** (CHAT_PLAN section 2, the help row;
//: `acts.palette_rows` through `GET /read/acts`): every act Chat does from one
//: sentence, under "Do" after the table's own two, each titled with its help
//: line, so the palette, the capability line and the Guide say the same thing.
//: Fetched once; until it answers (or with no server) the table stands alone.
const agentActs = { rows: null, asked: false };

function agentActStarters() {
  if (!agentActs.asked) {
    agentActs.asked = true;
    apiJson("/read/acts", { silent: true })
      .then((got) => {
        agentActs.rows = (got.rows || []).filter((row) => row.stem).map((row) => ({ group: "Do", label: row.label, text: row.stem, help: row.help }));
        if (agentActs.rows.length) renderAgentStarters();
      })
      .catch(() => {});
  }
  return agentActs.rows || [];
}

function renderAgentStarters() {
  const box = $("command-palette-starters");
  if (!box) return;
  box.replaceChildren();
  const groups = [];
  //: Where you are, first: see AGENT_TAB_STARTERS for why. `slice()` because
  //: the loop below appends into whichever group it last pushed, and the tab
  //: table is a constant: without the copy, opening the palette twice on the
  //: same tab grew that tab's row permanently.
  const tab = agentCurrentTab();
  const here = AGENT_TAB_STARTERS[tab];
  if (here) groups.push([`On ${agentTabLabel(tab)}`, here.slice(), "map-pin"]);
  const recent = agentStarterRecents();
  if (recent.length) groups.push(["Recent", recent, "clock-counter-clockwise"]);
  for (const starter of [...AGENT_STARTERS, ...agentActStarters()]) {
    const last = groups[groups.length - 1];
    if (last && last[0] === starter.group) last[1].push(starter);
    else groups.push([starter.group, [starter], AGENT_STARTER_ICONS[starter.group]]);
  }
  for (const [name, items, icon] of groups) {
    const label = document.createElement("p");
    //: `.eyebrow` is the app's one small-label recipe (01-forms-settings.css,
    //: DESIGN.md's recipe index); `.starter-verb` only makes it span the two
    //: columns of the starter grid and rule a hairline under itself.
    label.className = "starter-verb eyebrow";
    label.textContent = name;
    box.appendChild(label);
    for (const item of items) {
      const button = document.createElement("button");
      button.type = "button";
      //: **A row, not a pill** (INBOX 231, the owner: "these suggested
      //: questions in the popup agent are really ugly and that area needs a
      //: better modern and more professional redesign"). `ghost small` drew
      //: fourteen bordered pills in two columns, which is fourteen outlines
      //: competing with each other and with the box above them. `.starter`
      //: alone is DESIGN.md's row recipe instead: no edge at rest, the ground
      //: arriving with the pointer. The class stays on the button, so the
      //: table above, the click handler and the recents are untouched.
      button.className = "starter";
      //: **The family's icon, on every one of its members** (INBOX 205, the
      //: owner: "I want you to improve and redesign the suggestions and quick
      //: prompts in the popup agent"). Fourteen identical text pills in a
      //: two-column grid is a wall: the eye has to read every label to find
      //: the one it wants, and the five verbs the set is built around were
      //: carried only by a heading three rows up. One glyph per family makes
      //: the group legible from the chip itself, which is what lets the set be
      //: scanned by shape rather than read in full.
      setLabel(button, `ph:${icon} ${item.label}`);
      button.dataset.example = item.text;
      button.title = item.help || (/\s$/.test(item.text)
        ? `Start a message: ${item.text.trim()}…`
        : `Ask: ${item.text}`);
      box.appendChild(button);
    }
  }
}

//: **What "the open note" means** (decision 9's "Use the open note" toggle,
//: which scopes a run to the entry on screen). In order: the document open in
//: the editor while the Library's document pane is showing, then the note
//: being edited, then the last note opened in this session. The palette floats
//: over every tab, so "on screen" has to be answered from what the app knows
//: rather than from what happens to be scrolled into view.
function agentOpenSubject() {
  const showing = (name) => !$(`tab-${name}`)?.classList.contains("hidden");
  if (showing("documents") && typeof currentDoc !== "undefined" && currentDoc?.id) {
    return { kind: "document", id: currentDoc.id, label: currentDoc.title || "this document" };
  }
  //: **A board is not a note, and saying so was the whole report** (INBOX
  //: 189, the owner: "I think the test note the popup agent is referring to
  //: is the mind map I just made called test"). A board and a mind map are
  //: `Entry` rows like everything else here, so the last thing opened can be
  //: one of them, and this called it a note: the toggle offered "Use test",
  //: the run sent it as `note_ids`, and the model was handed a note whose
  //: whole content is `# test`. `mapBoardById` is the one place that knows
  //: which entry ids are boards, and a board row carries its own `type`, so a
  //: map is named a map and a board a board.
  const asBoard = (id) => {
    const board = mapBoardById(id);
    if (!board) return null;
    const kind = (board.type || "map") === "map" ? "map" : "board";
    return { kind, id, label: board.title || `${kind} ${id}` };
  };
  //: The canvas first: a board open in front of you is more "the thing on
  //: screen" than whichever note was last opened before you came here.
  const wbView = $("library-view-whiteboard");
  const openBoardId = typeof window !== "undefined" ? window.currentBoardId : null;
  if (openBoardId && wbView && !wbView.classList.contains("hidden") && showing("library")) {
    return asBoard(openBoardId) || { kind: "board", id: openBoardId, label: `board ${openBoardId}` };
  }
  const noteId = editingId || lastOpenedEntryId;
  if (!noteId) return null;
  const board = asBoard(noteId);
  if (board) return board;
  const entry = (typeof allEntries !== "undefined" ? allEntries : []).find(
    (row) => row.id === noteId
  );
  return { kind: "note", id: noteId, label: entry ? noteLabel(entry, 40) : `note ${noteId}` };
}

//: What each kind is called in the toggle's label and its tooltip. A table
//: rather than a chain of ternaries: five states were asked for by name
//: (INBOX 190), and a table is what makes it obvious when one is missing.
const AGENT_SUBJECT_WORDS = {
  note: "note",
  document: "document",
  map: "mind map",
  board: "board",
};

//: What the toggle actually sends. A document and a note go to different
//: fields, because `_attached_documents` and `_attached_notes` read different
//: tables and a document sent as a note reaches the model as a title.
//: A request that says "I have open" means the open thing whether or not
//: the box is ticked: the starter "Summarise the note I have open" sent
//: nothing when it was not, and was answered about no note at all.
function agentScopeForRun(text = "") {
  const box = $("command-palette-use-note");
  if (!box || !(box.checked || /\b(?:i have|i've got) open\b/i.test(text))) return {};
  const subject = agentOpenSubject();
  if (!subject) return {};
  //: **And the kind goes to the server, not just to the label** (INBOX 189).
  //: `board_ids` has its own reader (`_attached_boards`, routes_chat.py),
  //: which hands the model the map's outline under "Mind map: <title>"; the
  //: same id sent as `note_ids` reaches it as an entry whose entire content
  //: is `# <name>`. Naming it correctly on screen and then sending it as
  //: something else would have fixed half the report.
  if (subject.kind === "document") return { documentIds: [subject.id] };
  if (subject.kind === "map" || subject.kind === "board") return { boardIds: [subject.id] };
  return { noteIds: [subject.id] };
}

//: Whether the board index has been asked for since the palette was opened.
//: See the call below for why it is asked for at all.
let agentBoardIndexAsked = false;

//: Enabled only when there is something to use, and the label says what that
//: something is: a tick box offering to scope a run to nothing is the "control
//: that does nothing when pressed" this app has been told about before.
function syncAgentOpenNoteToggle() {
  const box = $("command-palette-use-note");
  const label = $("command-palette-use-note-label");
  //: The words live in a span inside the label, not in the label itself: a
  //: label's `textContent` includes the checkbox, so writing the new wording
  //: onto the label would delete the control it is labelling.
  const text = $("command-palette-use-note-text");
  if (!box || !label || !text) return;
  //: **The index that tells a map from a note has to be there to be read.**
  //: `mapBoardById` answers from a cache filled by whichever surface last drew
  //: board chips, and the palette opens over every tab, including ones that
  //: have never asked for boards at all. Without this the fix for INBOX 189
  //: would work on the Library tab and nowhere else, which is worse than not
  //: working: it would look fixed. Asked for once per opening (the flag is
  //: cleared by `toggleAgentPalette`), and the repaint is what puts the right
  //: word on the label when the answer arrives.
  if (!agentBoardIndexAsked) {
    agentBoardIndexAsked = true;
    loadMapBoardIndex().then(() => syncAgentOpenNoteToggle()).catch(() => {});
  }
  const subject = agentOpenSubject();
  if (!subject) box.checked = false;
  //: Hidden rather than disabled when nothing is open (row 1's count of
  //: disabled controls): the help popover says what it is for.
  label.classList.toggle("hidden", !subject);
  //: **"The open note" answered a question nobody could** (INBOX 190, the
  //: owner: "what does 'the open note' mean?? what does opening a note even
  //: entail?? how does one open a note??"). Two faults in one line. It named
  //: a category where it could name the thing, so the answer to "which note?"
  //: was a definite article; and with nothing open it still said "the open
  //: note", which is a checkbox describing something that does not exist.
  //: Now it says what kind the thing is and what it is called, and when there
  //: is nothing it says what would count as something.
  const word = subject ? AGENT_SUBJECT_WORDS[subject.kind] || subject.kind : null;
  //: **One short line, and the sentence behind it** (INBOX 208). The empty
  //: state used to carry its own instructions in the label, "Nothing open to
  //: use (open a note, document, board or map first)", which is a caption for
  //: a checkbox written as a paragraph: three lines at 390 and two at 1440, on
  //: a row that is otherwise one control high. A label says what the control
  //: does; the tooltip below, which has always carried the longer sentence,
  //: says what to do about it. The open case keeps the thing's name, which is
  //: the point of INBOX 190, and the CSS ellipsises a long one rather than
  //: wrapping it, so the title repeats it in full.
  text.textContent = subject ? `Use this ${word}: ${subject.label}` : "Nothing open to use";
  label.title = subject
    ? `Send this ${word}, ${subject.label}, with what you ask, so the agent works on it`
    : "Open a note, a document, a board or a mind map first, then the agent can work on it";
}

const cmdPaletteOverlay = $("command-palette-overlay");
const cmdPaletteInput = $("command-palette-input");
const cmdPaletteResults = $("command-palette-results");

// Opened and closed by `runShortcut("askAgent")`, see DEFAULT_SHORTCUTS.
// This deliberately has no `document.addEventListener` chord of its own:
// binding one here is what let this overlay collide with the navigation
// palette on Ctrl+K, and then with the sketch pad on Ctrl+Shift+K, twice
// without anything noticing.
function toggleAgentPalette() {
  //: **On a phone the agent is a sheet** (AGENT_SKILLS_REFORM "Deepened
  //: 2026-10-10" row 2). It went to the Chat tab, which left the shortcut,
  //: the More sheet's row and the palette's row all opening something else.
  if (window.matchMedia(PHONE_TABS).matches) return agentPhoneSheet();
  if (cmdPaletteOverlay.classList.contains("hidden")) {
    cmdPaletteOverlay.opener = document.activeElement;
    cmdPaletteOverlay.classList.remove("hidden");
    //: Both on open rather than once at boot: which starters are recent and
    //: what counts as the open note are answers about the moment the palette
    //: is reached for, and it is reached for from every tab.
    renderAgentStarters();
    syncAgentPaletteAvailability();
    agentBoardIndexAsked = false;
    syncAgentOpenNoteToggle();
    cmdPaletteInput.focus();
  } else {
    cmdPaletteOverlay.classList.add("hidden");
  }
}

//: The palette's own parts, moved into `openSheet` and put back when it
//: has gone (DESIGN.md "A sheet": the markup moved in, never a second copy).
//: The head stays behind but for its '?', which joins the sheet's head.
function agentPhoneSheet() {
  const open = document.querySelector('.sheet-overlay[data-sheet="agent"] .sheet-close');
  if (open) return open.click();
  const card = cmdPaletteOverlay.querySelector(".command-palette-card");
  const parts = [...card.children].filter((el) => !el.classList.contains("command-palette-head"));
  const help = card.querySelector(".command-palette-head .graph-help-toggle");
  openSheet({
    label: "Agent",
    name: "agent",
    build: (sheet) => {
      //: Beside the title, as the desktop head has it (`.help-head`).
      const title = sheet.querySelector(".sheet-title");
      const near = document.createElement("span");
      near.className = "row help-head";
      title.replaceWith(near);
      near.append(title, help);
      sheet.append(...parts);
    },
    onGone: () => {
      card.querySelector(".command-palette-head .help-head").append(help);
      card.append(...parts);
    },
  });
  //: After `openSheet` has put the card in the page: these read their
  //: elements by id, which finds nothing while the card is still being built.
  renderAgentStarters();
  syncAgentPaletteAvailability();
  agentBoardIndexAsked = false;
  syncAgentOpenNoteToggle();
}

//: Shut on both shapes: the overlay hidden and no agent sheet up.
function agentPaletteShut() {
  return cmdPaletteOverlay.classList.contains("hidden") && !document.querySelector('[data-sheet="agent"]');
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !cmdPaletteOverlay.classList.contains("hidden")) {
    cmdPaletteOverlay.classList.add("hidden");
  }
});

cmdPaletteOverlay.addEventListener("click", (e) => {
  if (e.target === cmdPaletteOverlay) {
    cmdPaletteOverlay.classList.add("hidden");
  }
});

// The head's Close. Escape and a click on the backdrop both already closed this
// surface and neither is visible, which is the half of "redesigned with the
// consistent modern look" that is not paint: every other dialog in the app
// offers a control you can see and this one asked you to know a key.
$("command-palette-close").addEventListener("click", () => toggleAgentPalette());

//: The header's agent button moved to the status bar with INBOX 207; the slot's own
//: listener sits beside the rest of the bar's, and the chord is named in its
//: tooltip, which is how anybody finds out a chord exists.

//: **The agent bar keeps a conversation, and says so.** Reported: "the popup
//: agent needs more features, capability, and learnability, there's no way to
//: clear the chat and start over, idk what it can do, and even if it works".
//: Every one of those was true of the same handler:
//:
//: - It sent `history: []` on every turn, so a follow-up ("now file that as a
//:   note") could not refer to the answer above it. It was a series of
//:   unrelated one-shot questions in a window that looked like a chat.
//: - There was no way to clear it, so the only reset was reloading the app.
//: - Its whole affordance was "Press Enter to send", which says nothing about
//:   what it can be asked to *do*.
//: - Every failure came out as "Error communicating with agent.", the one
//:   message that guarantees "idk if it even works", and it threw away
//:   `err.message`, which is exactly where `describe_http_error`'s diagnosis
//:   of a failing model arrives.
const cmdPaletteTurns = [];
let cmdPaletteRun = null;

function cmdPaletteReset() {
  cmdPaletteTurns.length = 0;
  cmdPaletteResults.replaceChildren();
  $("command-palette-intro")?.classList.remove("hidden");
  $("command-palette-status").textContent = "";
  renderCmdPaletteMenu();
}

//: **Keeping a conversation that was never meant to be kept** (INBOX 215, the
//: owner: "I want to be able to save conversations with the popup agent as a
//: permanent chat session"). The palette holds its turns in `cmdPaletteTurns`
//: and nothing else: it is a scratch window over whatever tab you are on, and
//: Start over throws the lot away. This posts them as a real conversation, the
//: same shape the Chat tab writes, and hands you the thread.
//:
//: The first turn creates it (the route makes the title from the question) and
//: the rest are appended, which is exactly the sequence the Chat tab performs
//: live; there is no bulk endpoint and adding one to save a round trip per
//: turn would be a second way to write the same row.
async function cmdPaletteSaveAsChat() {
  if (!cmdPaletteTurns.length) return;
  const status = $("command-palette-status");
  setLabel(status, "ph:spin Saving…");
  try {
    const [first, ...rest] = cmdPaletteTurns;
    const conversation = await apiJson("/conversations", {
      method: "POST",
      body: JSON.stringify({ question: first.question, answer: first.answer }),
    });
    for (const turn of rest) {
      await apiJson(`/conversations/${conversation.id}/turns`, {
        method: "POST",
        body: JSON.stringify({ question: turn.question, answer: turn.answer }),
      });
    }
    //: **The confirmation is a toast with an action, not a link in the status
    //: line.** The status line is one line that ellipsises (it sits in a row
    //: with a toggle and a menu, INBOX 208), so a title of any length would
    //: have pushed the way in off the end of it. `toastAction` is the app's
    //: own recipe for "it is done, and here is the thing": the message names
    //: the conversation, the button opens it, and nothing switches tab
    //: underneath a panel that is still open unless it is pressed.
    setLabel(status, "ph:check-circle Saved as a chat");
    let savedRow = null;
    pushUndo(
      `Saved a chat as “${conversation.title}”`,
      async () => {
        savedRow = (await apiJson(`/conversations/${conversation.id}`, { method: "DELETE" })).restore;
        loadConversationList().catch(() => {});
      },
      async () => {
        if (savedRow) await apiJson("/conversations/restore", { method: "POST", body: JSON.stringify(savedRow) });
        loadConversationList().catch(() => {});
      }
    );
    toastAction(`Saved as "${conversation.title}"`, "Open it", () => {
      toggleAgentPalette();
      switchTab("chat");
      return openConversation(conversation.id);
    }, { go: { open: "conversation", id: conversation.id } });
    //: The list behind the Chat tab's sidebar is stale the moment this lands,
    //: and it is cheap to refresh: without it the new thread is missing until
    //: something else happens to reload it.
    loadConversationList().catch(() => {});
    renderCmdPaletteMenu();
  } catch (error) {
    setLabel(status, "ph:warning-circle Could not save this conversation");
  }
}

//: The foot's one menu. Rebuilt rather than wired once, because what it offers
//: depends on whether there is anything to save yet, and a menu that offers a
//: dead row is the "control that does nothing when pressed" this app keeps
//: being told about. `kebabMenu` is the recipe (DESIGN.md's index).
function renderCmdPaletteMenu() {
  const host = $("command-palette-menu");
  if (!host || typeof kebabMenu !== "function") return;
  const saved = cmdPaletteTurns.length;
  host.replaceChildren(
    kebabMenu(
      [
        {
          label: "ph:floppy-disk Save as chat",
          title: saved
            ? "Keep this conversation in the Chat tab"
            : "Ask the agent something first, then this can keep the conversation",
          disabled: !saved,
          run: () => (saved ? cmdPaletteSaveAsChat() : undefined),
        },
        {
          label: "ph:arrow-counter-clockwise Start over",
          title: "Forget this conversation and start over",
          disabled: !saved,
          run: () => (saved ? cmdPaletteReset() : undefined),
        },
      ],
      "More actions for this conversation"
    )
  );
}

function cmdPaletteBusy(busy) {
  //: No `aiIsOff()` here any more: with no model the agent still runs acts
  //: and readings (`ai/starter_acts.py`), so only a run in hand closes the box.
  cmdPaletteInput.disabled = busy;
  $("command-palette-stop")?.classList.toggle("hidden", !busy);
  $("command-palette-menu")?.classList.toggle("hidden", busy);
  //: **The state line is written by the run, not by this** (INBOX 190: the
  //: agent should say "what it is working on and which tool ran"). This used
  //: to write "Working…" on the way in and blank on the way out, which is a
  //: status line that has never once said anything a person could not see
  //: from the spinner. `cmdPaletteAsk` now writes the question, then each
  //: tool as it runs, then what the turn came to; all this does is clear a
  //: line left over from the run before.
  if (busy) setLabel($("command-palette-status"), "ph:spin Working…");
  if (!busy) cmdPaletteInput.focus();
}

//: **The palette says what it did, the way the Chat tab does.** Reported:
//: "the popup agent is still missing many things like the semantic search,
//: token count, thinking boxes, metadata, persona used, model used... the
//: popup agent should be an application wide utility tool."
//:
//: **One muted line, Chat's own** (INBOX 458, the owner: "the source
//: metadata needs improving ui/ux wise"). It was a row of five bordered
//: pills, one per fact, wrapping to two lines in a 600px panel: the
//: block-per-fact shape DESIGN.md's facts-line recipe rules out. This is
//: `messageMetaLine` (chat.js), the line under every Chat answer: what the
//: turn cost first, the mode and the model quieter beside it, the token
//: counts and rounds on its tooltip, and a long model id cut short with the
//: whole name on hover. The search mode moved to the sources' own summary
//: ("Sources: 3 notes · meaning + keywords"), where Chat says it, and the
//: persona is the name and face at the top of this same bubble, so neither
//: is said twice. `persona` stays a parameter so the line can never name a
//: different writer from the head.
function cmdPaletteFacts({ stats, meta, persona, elapsedMs, toolCount }) {
  const line = messageMetaLine({
    model: stats?.model || meta?.answered_by,
    elapsedMs,
    stats,
    toolCount,
    rounds: stats?.round || 0,
    usedTools: true,
  });
  if (persona) line.dataset.persona = persona;
  return line.childElementCount ? line : null;
}

//: **What the agent found has to be reachable, not recited.** Reported with a
//: screenshot of the palette answering "You can find your notes about gaming
//: in notes id 3, 43 and 49": *"i have no clue what the notes numbers are,
//: there are no links to notes, no way to actually find and navigate to the
//: things it found, there is no semantic search results that appear."*
//:
//: Every word of that was a fair reading of what the code did. `onMeta`, the
//: event carrying `raw_results`, the notes retrieval actually surfaced, was
//: wired to `() => {}` here, so the one surface that knew which notes the turn
//: had found threw them away and left the model to describe them in prose. A
//: row id is the app's internal handle; printing it at a person is the same
//: mistake as the audit log's raw `entity_type`, and worse, because there is
//: nothing they can do with it.
//:
//: Two halves, and both are needed. The row below the answer is the *result
//: set*: it exists even when the model's prose forgets to mention a note, and
//: it is the semantic search result the report says is missing. The linkifier
//: is for the prose itself: a model that says "note id 43" is naming something
//: real, so that phrase becomes the button that opens it rather than a number
//: to go hunting for.
const CMD_NOTE_REF = /\bnotes?\s*(?:id|#)?\s*(\d{1,7})\b/gi;

//: Opening a note means leaving the palette, it is an overlay over the app it
//: is about to navigate. Closing it first is what makes "find it" and "go to
//: it" one gesture instead of a jump that happens behind a panel.
function cmdPaletteGoToNote(id) {
  cmdPaletteOverlay.classList.add("hidden");
  flashEntry(id);
}

//: **What this turn drew on: one list, Chat's Sources panel** (INBOX 458).
//: It was two blocks under the bubble, "Found in N notes" and "Opened N
//: items", the second repeating most of the first (a `search_notes` call
//: opens the very notes retrieval found), each a grid of pills holding a
//: note's whole text run together. `chatSourcesFrom` keys every source on
//: kind and id, so a note found and then opened is one row, and
//: `cmdSourceRow` draws each as the note's title, its category dot and
//: its date. Every row closes the palette before it opens
//: its note: the palette is an overlay over the app it is about to
//: navigate, and "find it" and "go to it" should be one gesture.
function cmdPaletteSources({ meta, touched }) {
  const sources = chatSourcesFrom({ meta, touched }).map((source) =>
    source.open
      ? {
          ...source,
          open: () => {
            cmdPaletteOverlay.classList.add("hidden");
            source.open();
          },
        }
      : source,
  );
  const panel = chatSourcesPanel({ sources, meta, row: cmdSourceRow });
  //: Past six the rest wait behind one "Show N more": eleven rows of
  //: provenance under a two-line answer is the panel reporting on itself.
  const rest = panel ? [...panel.querySelectorAll(".chat-source-row")].slice(6) : [];
  if (rest.length) {
    for (const extra of rest) extra.hidden = true;
    const more = document.createElement("button");
    more.type = "button";
    more.className = "link-button chat-sources-more";
    more.textContent = `Show ${rest.length} more`;
    more.addEventListener("click", () => {
      for (const extra of rest) extra.hidden = false;
      more.remove();
    });
    panel.querySelector(".chat-sources-body").appendChild(more);
  }
  return panel;
}

//: **A source as one compact row** (INBOX 458, the owner: "the source
//: metadata needs improving ui/ux wise"). The rows were bordered pills, each
//: the note's whole text run together and cut mid-word. A row is what a
//: reader scans for: the note's title, its category as the dot every other
//: surface draws (`paintCategoryDot`), and when it was last written, on
//: `.timeline-row`'s quiet-row shape (no border at rest, the ground arriving
//: with the pointer). Drawn by `chatSourcesPanel`'s `row` hook, so the
//: summary, the counts and the sheet on a phone stay the Sources panel's own.
function cmdSourceRow(source, icons, number) {
  const row = document.createElement(source.url ? "a" : source.open ? "button" : "div");
  if (source.url) {
    row.href = safeHref(source.url);
    row.target = "_blank";
    row.rel = "noopener noreferrer";
  } else if (source.open) {
    row.type = "button";
    row.addEventListener("click", source.open);
  }
  row.className = "chat-source-row";
  if (source.kind === "note" && source.id != null) row.dataset.noteId = String(source.id);
  const entry = source.entry;
  const mark = document.createElement("span");
  mark.setAttribute("aria-hidden", "true");
  if (entry?.category) {
    mark.className = "chat-source-row-dot";
    paintCategoryDot(mark, entry.category);
  } else {
    mark.className = "chat-source-row-kind";
    setLabel(mark, icons[source.kind] || "ph:note");
  }
  const title = document.createElement("span");
  title.className = "chat-source-row-title";
  title.textContent = entry?.title || noteNamePlain(entry?.content) || source.label;
  const date = document.createElement("span");
  date.className = "chat-source-row-date";
  const when = entry?.edited_at || entry?.created_at;
  date.textContent = source.url ? sourceHost(source.url) : when ? relativeTime(when) : "";
  row.append(mark, title, date);
  row.title = [title.textContent, entry?.category, date.textContent].filter(Boolean).join(" · ");
  //: The number the answer's in-text mark carries, inside the title's cell so
  //: the row keeps its three columns.
  if (source.kind === "note") {
    const index = document.createElement("span");
    index.className = "chat-source-index";
    index.textContent = number;
    title.prepend(index, " ");
  }
  return row;
}

//: One reference, as a control. Extracted because a list of ids builds several
//: of these and they must be identical, a note you can open should not look
//: like two different things in the same sentence.
//: **The link says which note it opens, and that is a correctness feature
//: rather than a nicety.** Reported: "the bubble tea note it mentioned was
//: my bubble tea mind map, but the link it gave and grounded was my
//: shakespeare note". The id in a link comes from the model's own prose
//: (`CMD_NOTE_REF` matches the "68" in "note #68"), and a model that writes
//: the wrong id produces a link that goes somewhere the answer never meant.
//: Nothing here can tell a right id from a wrong one: only the person
//: reading the sentence knows which note they were promised.
//:
//: So the tooltip carries the note's own opening words, labelled the same
//: way the source chips below the answer are labelled and from the same
//: retrieved entry. When the model gets it right the tooltip agrees with
//: the sentence; when it gets it wrong the disagreement is visible before
//: the click rather than after it. `entry` is optional because a caller
//: without one is still better off with a working link than none.
//: **The link says which note it opens, in the sentence, before it is
//: clicked** (INBOX 112).
//:
//: Reported with two screenshots: an answer that read "You only have one note
//: (note #68) in your notebook, and its content is simply '# bubble tea'",
//: with both chips labelled "bubble tea", and clicking "note #68" opened a
//: Shakespeare sonnet parody. Traced: the destination is not wrong.
//: `flashEntry` selects `li[data-id="${id}"]`, so the button opens exactly the
//: id the text names, and the run-of-ids walk below only ever links an id this
//: turn actually retrieved. What went wrong is upstream of the app: the model
//: wrote an id that belonged to a different note than the one its own sentence
//: was describing, and the app then dressed that number up as a citation, which
//: is what made a model's mistake read as the app sending you somewhere at
//: random.
//:
//: A tooltip was the first answer and it is not enough: you have to hover a
//: thing you have no reason to distrust. So the note's own opening words go
//: *in* the link, beside the model's own wording, which is left exactly as it
//: was written. When the model is right the link reads "note #68 · bubble tea"
//: and confirms itself; when it is wrong it reads "note #68 · Act I, Scene I"
//: and the mismatch is visible in the sentence without clicking anything. The
//: app cannot make a small local model cite correctly, and it can stop
//: repeating the claim as though it had checked it.
//: The first line of a note, as a name. Empty when there is nothing to show,
//: so the caller can leave the reference bare rather than print "(empty
//: note)" in the middle of a sentence.
function cmdNoteName(entry) {
  const first = String(entry?.content || "")
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.length > 0);
  if (!first) return "";
  const clean = notePreviewText(first)
    .replace(/\s+/g, " ")
    .trim();
  if (!clean) return "";
  return clean.length > 24 ? `${clean.slice(0, 23).trimEnd()}\u2026` : clean;
}

function cmdNoteLink(text, id, entry = null) {
  const link = document.createElement("button");
  link.type = "button";
  link.className = "cmd-note-link";
  const said = document.createElement("span");
  said.textContent = text;
  link.appendChild(said);
  //: **The note's first line, not `noteLabel`'s preview of the whole note.**
  //: `noteLabel` runs the entire content through the markdown stripper and
  //: collapses it to one line, which is right for a card ("Act I, Scene I A
  //: sonnet parody") and wrong here: this is a name inside a sentence, and
  //: what a reader recognises a note by is its heading. 24 characters, not
  //: `noteLabel`'s 40, for the same reason: three linked ids in one list at 40
  //: each is a paragraph of titles in the middle of an answer.
  const preview = cmdNoteName(entry);
  if (preview) {
    const name = document.createElement("span");
    name.className = "cmd-note-link-name";
    name.textContent = preview;
    link.appendChild(name);
  }
  link.title = preview ? `Open note ${id}: "${preview}"` : `Open note ${id}`;
  link.addEventListener("click", () => cmdPaletteGoToNote(id));
  return link;
}

//: Turns "note id 43" in the rendered answer into a button that opens note 43.
//:
//: Walks text nodes and splits them, the same shape `addInlineCitations` uses
//: for the Ask box's citation markers: and for the same reason: the answer is
//: already safe DOM built by `renderMarkdown`, and going back to a string to
//: regex over it would be re-introducing the innerHTML this function's own
//: neighbourhood was fixed to stop using. Only ids the turn actually retrieved
//: are linked, so a model inventing "note id 900" leaves plain text behind
//: rather than a button that goes nowhere.
function cmdPaletteLinkNotes(root, results) {
  //: A map rather than a set: every link now carries the note's own opening
  //: words in its tooltip (see `cmdNoteLink`), so the entry has to travel
  //: with the id rather than just the fact that the id was retrieved.
  const known = new Map((results || []).map((entry) => [entry.id, entry]));
  if (!known.size) return;
  const queue = [root];
  while (queue.length) {
    const node = queue.shift();
    if (node.nodeType === Node.ELEMENT_NODE) {
      if (node.classList?.contains("cmd-note-link")) continue;
      queue.unshift(...node.childNodes);
      continue;
    }
    if (node.nodeType !== Node.TEXT_NODE) continue;
    CMD_NOTE_REF.lastIndex = 0;
    const match = CMD_NOTE_REF.exec(node.textContent);
    if (!match) continue;
    const id = Number(match[1]);
    if (!known.has(id)) continue;
    const tail = node.splitText(match.index);
    const rest = tail.splitText(match[0].length);
    tail.replaceWith(cmdNoteLink(match[0], id, known.get(id)));
    //: **The rest of the list, which is where the report actually lands.** A
    //: model writes "notes id 3, 43 and 49", one phrase naming the id, then
    //: bare numbers. Linking only the head leaves two of the three notes as
    //: unreachable digits, which is the complaint verbatim. So after a match,
    //: keep eating `, 43` / ` and 49` for as long as the next number is one
    //: this turn actually retrieved. An unknown id ends the run rather than
    //: being skipped over: past it the numbers are no longer reliably part of
    //: this list, and guessing is how "$150 to $68" in the very next sentence
    //: of that screenshot would have become two note links.
    let cursor = rest;
    for (;;) {
      const more = /^(\s*(?:,|and|,\s*and)\s*)(\d{1,7})\b/i.exec(cursor.textContent);
      if (!more) break;
      const nextId = Number(more[2]);
      if (!known.has(nextId)) break;
      const numStart = cursor.splitText(more[1].length);
      const after = numStart.splitText(more[2].length);
      numStart.replaceWith(cmdNoteLink(more[2], nextId, known.get(nextId)));
      cursor = after;
    }
    //: `cursor` carries everything after the run, including any further
    //: mentions in the same sentence, re-queueing it is what stops the first
    //: reference in a paragraph being the only one that becomes a link.
    queue.unshift(cursor);
  }
}

//: **Files on the popup agent's next message** (attach-1026 A2, A3). The owner:
//: "if i attach documents to the popup agent, they arent chipped so I cant
//: remove them ... what if I upload a document but I dont want it saved to the
//: app and I want to delete it before I send it", and "it only accepts images
//: and pdfs".
//:
//: A file waits here, in the browser, as a chip (`attachmentChip`, the one
//: recipe Chat uses). Nothing is uploaded until Enter, so removing a chip
//: before sending leaves nothing on the server to delete. On send an image
//: goes to `/media/upload` and anything else is imported as a document, the
//: split the Chat tab's attach button makes (`attachChatFiles`); the ids ride
//: on the request. If one fails, the uploads already made are deleted again
//: and the message is not sent, so a failed send leaves nothing behind.
const AGENT_MAX_FILES = 4;
const agentStaged = [];

function agentRenderChips() {
  const box = $("command-palette-attachments");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", agentStaged.length === 0);
  for (const item of agentStaged) {
    const name = item.file.name;
    box.appendChild(
      attachmentChip({
        name,
        size: item.file.size,
        thumb: item.objectUrl,
        state: item.state,
        progress: item.progress,
        error: item.error,
        title: `${name}: held in this window until you send, nothing is saved to the app before that`,
        removeTitle: `Remove “${name}” (nothing was saved)`,
        onRemove: item.state === "uploading" ? null : () => agentUnstage(item),
      }),
    );
  }
}

function agentUnstage(item) {
  if (item.objectUrl) URL.revokeObjectURL(item.objectUrl);
  agentStaged.splice(agentStaged.indexOf(item), 1);
  agentRenderChips();
  announce(`Removed ${item.file.name}. ${agentStaged.length} file(s) attached.`);
}

function agentStageFiles(files) {
  let skipped = 0;
  for (const file of files) {
    if (agentStaged.length >= AGENT_MAX_FILES) {
      skipped++;
      continue;
    }
    const objectUrl = isImageFile(file) ? URL.createObjectURL(file) : "";
    agentStaged.push({ file, objectUrl, state: "ready", progress: 0, error: "" });
  }
  if (skipped) toast(`Four files at most go with one message, ${skipped} left out.`, "info");
  agentRenderChips();
  cmdPaletteInput.focus();
}

async function agentUploadOne(file) {
  const form = new FormData();
  form.append("file", file);
  const init = { method: "POST", headers: authHeaders(), body: form };
  if (isImageFile(file)) return { mediaId: (await apiJson("/media/upload", init)).id };
  try {
    return { documentId: (await apiJson("/documents/import", init)).id };
  } catch (error) {
    // A PDF whose words cannot be read is kept in the Library, as in Chat.
    if (await keepUnreadableChatFile(file, error)) return {};
    throw error;
  }
}

//: Uploads the staged files for this message and returns what the request
//: carries, or null when one failed (its chip then says why and stays).
async function agentCommitFiles() {
  const sent = { imageMediaIds: [], documentIds: [], chips: [] };
  for (const [index, item] of agentStaged.entries()) {
    Object.assign(item, { state: "uploading", progress: index / agentStaged.length });
    agentRenderChips();
    try {
      const got = await agentUploadOne(item.file);
      if (got.mediaId) sent.imageMediaIds.push(got.mediaId);
      if (got.documentId) sent.documentIds.push(got.documentId);
    } catch (error) {
      for (const other of agentStaged) other.state = "ready";
      Object.assign(item, { state: "error", error: error.message || "Could not attach" });
      agentRenderChips();
      for (const id of sent.imageMediaIds) await apiJson(`/media/${id}`, { method: "DELETE" }).catch(() => null);
      // An imported document would otherwise be duplicated by the retry.
      for (const id of sent.documentIds) await apiJson(`/documents/${id}`, { method: "DELETE" }).catch(() => null);
      return null;
    }
  }
  sent.chips = agentStaged.map((item) => attachmentChip({ name: item.file.name, size: item.file.size, thumb: item.objectUrl }));
  agentStaged.length = 0;
  agentRenderChips();
  return sent;
}

async function cmdPaletteAsk(text, { plan = null } = {}) {
  const sentFiles = await agentCommitFiles();
  if (!sentFiles) {
    cmdPaletteInput.value = text;
    cmdPaletteGrow();
    return;
  }
  $("command-palette-intro")?.classList.add("hidden");

  const userMsg = document.createElement("div");
  userMsg.className = "msg user";
  userMsg.textContent = text;
  for (const chipEl of sentFiles.chips) userMsg.appendChild(chipEl);
  userMsg.appendChild(userMarkEl());
  //: **The same three actions the Chat tab's own bubbles carry.** Reported:
  //: *"I cant copy edit or resend any messages in the popup agent. it still
  //: lacks a lot of features."* The palette had none of them, a question you
  //: mistyped could only be retyped from memory, and an answer could only be
  //: selected by hand.
  //:
  //: `chatMessageActions` is the Chat tab's own row, reused rather than
  //: rebuilt: the palette is supposed to be the same assistant in a smaller
  //: window, and two different action rows for one idea is how they drift.
  //: Edit puts the text back in the box rather than opening an editor, 
  //: there is one input here and it is right below, so the shortest path to
  //: "ask that again, differently" is to hand it back.
  userMsg.appendChild(
    chatMessageActions([
      { label: "ph:copy", title: "Copy", onClick: (e) => copyToClipboard(text, e.currentTarget) },
      {
        label: "ph:pencil-simple",
        title: "Edit and ask again",
        onClick: () => {
          cmdPaletteInput.value = text;
          cmdPaletteInput.focus();
          cmdPaletteInput.setSelectionRange(text.length, text.length);
          autoGrow(cmdPaletteInput);
        },
      },
      {
        label: "ph:arrow-clockwise",
        title: "Ask this again",
        onClick: () => cmdPaletteAsk(text),
      },
    ])
  );
  cmdPaletteResults.appendChild(userMsg);

  const agentMsg = document.createElement("div");
  //: `.is-generating` is the app's one "this is working" signal
  //: (01-forms-settings.css). It goes on the bubble that is filling, not on a
  //: spinner parked elsewhere, so what pulses is the thing being waited for.
  agentMsg.className = "msg assistant is-generating";
  //: What a notification finds this answer by, if the palette is shut when
  //: it finishes (`noticeUnwatchedAnswer`).
  agentMsg.dataset.answerId = `agent-${Date.now()}`;
  //: **The same avatar-circle header Chat's own assistant bubbles carry**
  //: (`addAssistantBubble`, chat-agent.js), reused rather than rebuilt: "the
  //: popup agent's reply rows should use the persona avatar circles, the
  //: same as Chat's own bubbles." d640710 tried this before persona faces
  //: existed on this branch (a generic emblem, `.msg-role`/`.msg-avatar`
  //: with no persona behind it) and did not survive the app.js split; this
  //: is the reconciled version, built on what c941505 actually landed for
  //: Chat.
  //:
  //: The persona is resolved now, at send time, the same value the request
  //: below sends and the `cmdPaletteFacts` line carries, not read back off
  //: a live picker that may have moved on by the time a slow answer lands
  //: (`paintPersonaAvatar`'s own comment on `addAssistantBubble` makes the
  //: same argument for Chat).
  const askedPersona = (prefsCache && prefsCache.active_persona) || null;
  const askedWriter = personaDisplayName(askedPersona);
  const agentLabel = document.createElement("div");
  agentLabel.className = "msg-role msg-role-assistant";
  const agentAvatar = document.createElement("span");
  agentAvatar.className = "msg-avatar";
  agentAvatar.setAttribute("aria-hidden", "true");
  const agentWriterName = document.createElement("span");
  agentWriterName.textContent = askedWriter;
  agentLabel.append(agentAvatar, agentWriterName);
  agentMsg.appendChild(agentLabel);
  //: **Chat's own step column** (INBOX 457/458): the thinking fold, the steps
  //: fold and the answer go into an `.agent-steps` holder under the head, as
  //: they do in `addAssistantBubble`, so the popup gets the same order, the
  //: same rail and nodes once there is more than one step, and the same
  //: spacing between them, from the same rules (02-chat-graph.css), rather
  //: than parts appended straight onto the bubble in whatever order their
  //: events arrived.
  const stepsHolder = document.createElement("div");
  stepsHolder.className = "agent-steps";
  agentMsg.appendChild(stepsHolder);
  //: **What the tools did, as the same fold the Chat tab shows.** Reported:
  //: "tool calls dont show" in the popup agent. The palette answered every
  //: tool event with one word on the status line ("Working…") and threw the
  //: event away, so a turn that read three notes and edited one looked, once
  //: it had finished, exactly like a turn that had done nothing. The Chat
  //: tab's answer bubble folds its calls under "Finished N steps"
  //: (`agent-step-group`); this is that fold, fed by the same `toolChip`
  //: builder, so a call reads the same in both places. It is created on the
  //: first tool event rather than up front: a turn with no calls has nothing
  //: to fold and should not show an empty one.
  let stepsFold = null;
  let stepCount = 0;
  //: A plan's checklist, ticks and change list are Chat's own
  //: (`agentTimeline`), made on the run's first plan event.
  let runTimeline = null;
  const planTimeline = () => runTimeline || (runTimeline = agentTimeline(stepsHolder));
  const foldSummary = (done) => {
    if (!stepsFold) return;
    const word = stepCount === 1 ? "step" : "steps";
    setLabel(
      stepsFold.querySelector("summary"),
      done ? `ph:check-circle Finished ${stepCount} ${word}` : `ph:spin Working: ${stepCount} ${word}`,
    );
  };
  const addStep = (event) => {
    if (!stepsFold) {
      stepsFold = document.createElement("details");
      stepsFold.className = "agent-step agent-step-group";
      const summary = document.createElement("summary");
      summary.className = "agent-step-group-summary";
      const body = document.createElement("div");
      body.className = "agent-step-group-body";
      stepsFold.append(summary, body);
      stepsHolder.insertBefore(stepsFold, answerBox);
    }
    stepCount += 1;
    stepsFold.querySelector(".agent-step-group-body").appendChild(
      toolChip(event?.label || "Tool call", event?.ok !== false, event),
    );
    foldSummary(false);
  };
  //: **The answer has a box of its own, and the caret rides that box.**
  //: Reported: "there's no writing caret when the message is streaming in
  //: the popup agent". The Chat tab's caret is `.is-streaming > :last-child
  //: ::after` (01-forms-settings.css) on the answer's own element; the
  //: palette rendered its answer straight into the bubble, whose last child
  //: is the action row, so the class had nowhere to sit that would put the
  //: caret after the words. The answer box is the last thing before the
  //: actions, and `is-streaming` comes off with `is-generating` below.
  //: **The class waits for the first token** (INBOX 187, the owner: "the
  //: writing carette shows on the popup agent when the 3-dot animation is
  //: showing and it is waiting for a model response which it shouldnt"). Set
  //: here, the caret's `> :last-child::after` arm landed on the typing dots
  //: themselves, so the wait was drawn as three bouncing dots with a blinking
  //: block beside them: two indicators for one state, and the one that means
  //: "text is arriving" lit while none was. The dots own the "nothing yet"
  //: state and the caret owns "writing", which is the rule the Ask box has
  //: followed since it was built (`onAnswer` there adds the same class on its
  //: first delta, not before the request).
  const answerBox = document.createElement("div");
  answerBox.className = "agent-step step-answer bubble-answer";
  //: Chat's own waiting line, musing included.
  //: Driven by `streamChat` below (`progress`), INBOX 649.
  const askLine = progressLine(null, { persona: askedPersona, words: true });
  answerBox.appendChild(askLine);
  stepsHolder.appendChild(answerBox);
  cmdPaletteResults.appendChild(agentMsg);
  paintPersonaAvatar(agentAvatar, askedWriter, 20); // now attached, so p5 can measure and draw
  //: The answer's own row, added now and reading `answerRaw` at click time: 
  //: the text does not exist yet, and binding a copy of an empty string is
  //: how "Copy" ends up copying nothing on a fast answer. It stays the
  //: bubble's last child: the sources and the facts line go in above it
  //: (INBOX 458: it hung over the "Found in N notes" heading when those
  //: were drawn after the bubble).
  const actionRow = agentMsg.appendChild(
    chatMessageActions([
      {
        label: "ph:copy",
        title: "Copy this answer",
        onClick: (e) => copyToClipboard(answerRaw, e.currentTarget),
      },
      {
        label: "ph:arrow-clockwise",
        title: "Ask again for a different answer",
        onClick: () => cmdPaletteAsk(text),
      },
    ])
  );
  //: A new question always brings the pane to the bottom and follows it
  //: again; from here on it follows only while the reader stays there
  //: (`keepAtBottom`, INBOX 458: "I cant scroll up while the popup agent is
  //: responding", every token used to set `scrollTop` unconditionally).
  cmdPaletteResults.dataset.stuck = "1";
  keepAtBottom(cmdPaletteResults);

  // Was hand-rolled against `/chat` (the non-streaming endpoint, a single
  // JSON object) as though it were the NDJSON `/chat/stream` shape: so
  // `msg.type` was never "content" and this never actually rendered an
  // answer at all (a "feature that never ran once", CLAUDE.md's own
  // category for this). It also built the answer with
  // `innerHTML = answerText.replace(...)` and no escaping: a real,
  // reachable XSS the moment the parsing bug above was fixed, since a
  // model can echo a note's own text back verbatim. Fixed by reusing this
  // file's one real streaming client (`streamChat`) and its one safe
  // renderer (`renderMarkdown`, DOM nodes only, never innerHTML) instead
  // of a second, parallel, broken implementation of both.
  let answerRaw = "";
  let answered = false;
  //: Stopped by the reader, which is the one ending that needs no notice.
  let stopped = false;
  let found = [];
  //: Keyed on kind *and* id, because a note 3 and a document 3 are two
  //: different things and both may be touched in one turn.
  const touched = new Map();
  let meta = null;
  let stats = null;
  const panels = []; // the app's panels under the answer (INBOX 1300 C06)
  let thinkingRaw = "";
  //: In-text numbers, Chat's own call (`addInlineCitations`) on the `grounding`
  //: rows (BACKLOG, the owner 2026-10-12: popup answers had a Sources list and
  //: no marks). The numbering is `chatSourcesFrom` over this turn's meta and
  //: touched items, the list `cmdPaletteSources` draws, so a digit in the
  //: prose is the digit on its row. Re-placed after every paint, which
  //: rebuilds the answer.
  let cites = null;
  const cite = (event) => {
    if (event) cites = event.sentences || [];
    if (cites?.length) addInlineCitations(answerBox, cites, found, chatSourcesFrom({ meta, touched: [...touched.values()] }));
  };
  //: The box the reasoning is written into while it is being produced, made
  //: on the first delta rather than up front so a turn that never thinks out
  //: loud does not grow an empty one.
  let thinkingBox = null;
  //: Which tool ran last, for the line the run ends on. The label is the
  //: harness's own (`ph:books Listed notes (…)`), so the icon token has to be
  //: stripped before it can be quoted inside another label.
  let lastToolLabel = "";
  let why = "";
  const startedAt = performance.now();
  const run = (cmdPaletteRun = new AbortController());
  const agentScope = agentScopeForRun(text);
  cmdPaletteBusy(true);
  //: What it is working on, in the person's own words, cut to a line. A
  //: status that says "Working…" over a thirty-second run is the app saying
  //: it is busy; this is the app saying what it is busy with, which is the
  //: difference between waiting and wondering.
  const shortAsk = text.length > 48 ? `${text.slice(0, 47).trimEnd()}…` : text;
  setLabel($("command-palette-status"), `ph:spin Working on: ${shortAsk}`);
  try {
    await streamChat({
      progress: askLine,
      question: text,
      // The same window the Ask box uses, and for the same reason: enough
      // for a follow-up to mean something, short enough that a small local
      // model is not re-reading a transcript every turn.
      history: cmdPaletteTurns.slice(-MAX_CLIENT_HISTORY),
      //: **"Use the open note"** (decision 9). The subject is resolved at send
      //: time, not when the box was ticked: the palette stays open across a
      //: conversation and the person may well have opened something else
      //: between turns, and the tick means "whatever I am looking at".
      ...agentScope,
      imageMediaIds: sentFiles.imageMediaIds,
      documentIds: [...(agentScope.documentIds || []), ...sentFiles.documentIds],
      useTools: true, // the palette is meant to act on the notebook, like Chat
      plan,
      onPlan: (event) => planTimeline().plan(event),
      onStep: (event) => planTimeline().step(event),
      onResult: (event) => {
        answered = true;
        planTimeline().result(event);
      },
      //: Approved once (row 3): the steps and their writes, then Run the plan.
      onRunPlan: (event) => {
        answered = true;
        planProposalCard(stepsHolder, event, () =>
          cmdPaletteAsk(event.goal, { plan: { goal: event.goal, steps: event.steps } })
        );
      },
      signal: cmdPaletteRun.signal,
      //: `raw_results` is the notes retrieval surfaced for this turn. It used
      //: to be discarded here, which is why the palette could only describe
      //: what it found and never show it.
      onMeta: (event) => {
        meta = event;
        found = event?.raw_results || [];
      },
      //: **Written as it is thought.** Reported: "the popup agent doesnt
      //: stream thinking ... the thinking only shows up after the response is
      //: finished". It was accumulated here and prepended at the end, on the
      //: reasoning that the box is closed so nobody could see it: true of the
      //: box, and beside the point for the wait, which is the part of a turn
      //: where the reasoning is the only thing there is to show. The box is
      //: open while the turn runs and closes when the answer arrives, so a
      //: finished turn still reads answer-first.
      //:
      //: `textContent`, not a re-render: the cost the old comment was
      //: avoiding was markdown, and this is plain text.
      //:
      //: **Under the name, not over it** (INBOX 457, the owner: "the thinking
      //: box appears above the atlas message bubble title and avatar in the
      //: popup agent"). It was `prepend`ed, which put it before the head.
      //: Every assistant bubble reads head, thinking, steps, answer, sources,
      //: facts, actions, and the fold is the app's one (`thinkingFold`).
      onThinking: (delta) => {
        thinkingRaw += delta;
        if (!thinkingBox) {
          thinkingBox = thinkingFold();
          stepsHolder.prepend(thinkingBox);
        }
        thinkingPaint(thinkingBox, thinkingRaw);
        keepAtBottom(cmdPaletteResults);
      },
      //: An agent turn reports once per round. Same accumulation the Chat tab
      //: does: output tokens add up, the prompt is the largest one sent, and
      //: one estimated round makes the whole figure an estimate.
      onStats: (event) => {
        if (!stats) {
          stats = { ...event };
          return;
        }
        stats.model = event.model || stats.model;
        stats.prompt_tokens = Math.max(stats.prompt_tokens || 0, event.prompt_tokens || 0);
        stats.output_tokens = (stats.output_tokens || 0) + (event.output_tokens || 0);
        stats.round = Math.max(stats.round || 0, event.round || 0);
        if (event.usage_source === "estimated") stats.usage_source = "estimated";
      },
      onTool: (event) => {
        //: The reasoning that led to a call is finished, so it folds, the
        //: same move Chat's timeline makes (`foldEarlierThinking`).
        if (thinkingBox) thinkingBox.open = false;
        addStep(event);
        //: A page the model read opens in place above the answer (INBOX 1300 C06).
        if (event.ok && event.tool === "read_url") drawAnswerPanels(stepsHolder, [{ web: event.sources, read: true }], answerBox);
        keepAtBottom(cmdPaletteResults);
        // Something visible while a tool runs, so a long silence reads as
        // work rather than as nothing happening.
        //: `setLabel`, not `textContent`. A tool event's label carries this
        //: app's icon token, `ph:books Listed notes (…)`, and `setLabel` is
        //: the one function that turns that into the glyph. Writing it as text
        //: printed the token itself: reported with a screenshot reading
        //: "Running ph:books Listed notes ([\"Thoughts & Ideas\"])…". The label
        //: has to be composed before the icon is resolved, since the token is
        //: only recognised at the start of the string.
        setLabel(
          $("command-palette-status"),
          event?.label ? `${event.label} …` : "Working…",
        );
        lastToolLabel = (event?.label || "").replace(/^ph:[\w-]+\s*/, "");
        for (const item of event?.touched || []) {
          touched.set(`${item.kind}:${item.id}`, item);
        }
        pushAgentChangeUndo(event?.change, event);
        //: **The rest of the app has to hear about it too.**
        //:
        //: Reported: *"the popup agent made a note, but there was no way to
        //: go to it, it didn't appear in the notes tab and only appeared in
        //: the library."* Both halves are this one line. The Chat tab has
        //: called `loadEntries()` on a change event since it was built; the
        //: palette never did, so `allEntries`, which the Notes tab renders
        //: from, and which the palette's own chips resolve titles against, 
        //: still held the notebook as it was before the agent wrote to it.
        //: The Library looked correct only because it re-fetches when opened.
        //:
        //: Not awaited: this runs mid-stream and the answer must keep
        //: arriving while the list refreshes behind it.
        if ((event?.changes || []).length) loadEntries();
      },
      //: Dropped here, each ended as "(no answer)".
      //: An act's card (Confirm, or Done with Undo), drawn by Chat's own
      //: `renderToolConfirm`: with no model this is how a write arrives.
      onConfirm: (event) => {
        answered = true;
        renderToolConfirm(stepsHolder, event);
      },
      onUnsupported: (e) => (why = e?.message || why),
      onPanel: (event) => panels.push(event),
      onWebSources: (event) => panels.push({ web: event.sources }),
      onHint: (e) => (why = why || e?.text || ""),
      onGrounding: cite,
      onGroundingLive: cite,
      onAnswerFinal: (e) => {
        if (!e?.text) return;
        answered = true;
        renderMarkdown(answerBox, (answerRaw = e.text));
        cite();
      },
      onAnswer: (delta) => {
        answered = true;
        answerRaw += delta;
        //: Idempotent, and cheap: `classList.add` on a class already there is
        //: a no-op, so this costs nothing per delta and saves a flag.
        answerBox.classList.add("is-streaming");
        if (thinkingBox) thinkingBox.open = false;
        renderMarkdown(answerBox, answerRaw);
        cite();
        keepAtBottom(cmdPaletteResults);
      },
    });
    answerBox.classList.remove("is-streaming");
    foldSummary(true);
    if (!answered) answerBox.textContent = why || "The model wrote nothing. Try again, or rephrase.";
    else {
      //: Linked once, at the end, rather than on every delta: mid-stream the
      //: text can be "note id 4" on its way to "note id 43", and a link built
      //: from that half-arrived number would point at the wrong note.
      //: Retrieval's notes *and* the notes tools opened: an `edit_note` turn
      //: retrieves nothing, so "note id 43" in its answer had no link at all.
      cmdPaletteLinkNotes(agentMsg, [
        ...found,
        ...[...touched.values()].filter((item) => item.kind === "note"),
      ]);
      cmdPaletteTurns.push({ question: text, answer: answerRaw });
      if (panels.length) drawAnswerPanels(answerBox, panels);
      finishReply(answerBox, { composed: meta?.composed, head: agentLabel, model: stats?.model || meta?.answered_by, engine: Boolean(meta) });
      //: The first turn is what turns "Save as chat" from a dead row into a
      //: live one, so the menu is rebuilt here rather than only on reset.
      renderCmdPaletteMenu();
    }
    //: Below the answer, and always when there were results, the model's
    //: prose is free to summarise or to leave a note out, but what retrieval
    //: found should not depend on whether it got a mention. One list for
    //: what was searched and what was opened (`cmdPaletteSources`), inside
    //: the bubble and above its action row, so the row hangs under the
    //: bubble rather than over the list.
    const sources = cmdPaletteSources({ meta, touched: [...touched.values()] });
    if (sources) agentMsg.insertBefore(sources, actionRow);
    //: The reasoning stays where it was written, folded now, with the
    //: trailing blank lines trimmed.
    if (thinkingBox) {
      thinkingBox.open = false;
      thinkingPaint(thinkingBox, thinkingRaw.trim());
    }
    const metaRow = cmdPaletteFacts({
      meta,
      stats,
      elapsedMs: Math.round(performance.now() - startedAt),
      toolCount: stepCount,
      //: The persona this turn was actually *sent* with (`askedPersona`,
      //: captured when the bubble was made and its avatar painted), not a
      //: fresh read of the picker: a slow answer finishing after the person
      //: switched personas used to name the *new* one here while the avatar
      //: above still (correctly) wore the one that wrote it, two different
      //: claims about who answered on one turn.
      persona: askedPersona,
    });
    if (metaRow) agentMsg.insertBefore(metaRow, actionRow);
    keepAtBottom(cmdPaletteResults);
  } catch (err) {
    if (err?.name === "AbortError") {
      stopped = true;
      answerBox.textContent = answerRaw || "(stopped)";
    } else {
      // The message, not a euphemism for it. A failing model's real reason
      // arrives here (see `describe_http_error` in ai/ollama_client.py) and
      // "Error communicating with agent." threw all of it away.
      answerBox.textContent = err?.message || "The agent could not be reached.";
      agentMsg.classList.add("error");
    }
  } finally {
    answerBox.classList.remove("is-streaming");
    foldSummary(true);
    agentMsg.classList.remove("is-generating");
    //: Only this turn's own run: Run the plan can start the next turn before
    //: this one's `finally`, and clearing that one's controller left Stop
    //: with nothing to stop (measured: a stopped plan wrote its step 2).
    if (cmdPaletteRun === run) {
      cmdPaletteRun = null;
      cmdPaletteBusy(false);
    }
    //: The end of the run, said once and left there: what the turn did is
    //: still the answer to "what happened" a minute later, and a line that
    //: blanks itself the moment it could be read is a line nobody reads.
    const word = stepCount === 1 ? "step" : "steps";
    setLabel(
      $("command-palette-status"),
      stepCount
        ? `ph:check-circle Done, ${stepCount} ${word}, last: ${lastToolLabel || "a tool"}`
        : answered
          ? "ph:check-circle Answered"
          : "ph:warning-circle Nothing came back",
    );
    //: Shut before the answer arrived: say so, once, with the way back to it.
    if (!stopped && agentPaletteShut()) {
      noticeUnwatchedAnswer("agent", text, agentMsg.dataset.answerId, {
        failed: agentMsg.classList.contains("error"),
      });
    }
  }
}

// The palette's input is a `<textarea>` (see index.html for why), so it has
// to be told to behave like a command bar rather than a text box: Enter
// sends, Shift+Enter, and any of the IME/composition states below, insert a
// newline. `isComposing` matters for anyone typing Japanese, Chinese or Korean:
// Enter commits the candidate word there, and sending on it would fire the
// agent at half a sentence every time.
function cmdPaletteGrow() {
  // Reset first: without it the box only ever ratchets taller, because
  // scrollHeight can never come back below a height already set on it.
  cmdPaletteInput.style.height = "auto";
  const max = 9 * 16; // ~9rem, then it scrolls, the palette is not an editor
  cmdPaletteInput.style.height = `${Math.min(cmdPaletteInput.scrollHeight, max)}px`;
}

cmdPaletteInput.addEventListener("input", cmdPaletteGrow);

//: **The starters are reachable from the keyboard** (INBOX 190's "more ui, ux
//: and functionality refinements to be more professional"). A command bar
//: whose suggestions can only be clicked is a command bar that makes you
//: reach for the mouse in the middle of typing, which is the one thing this
//: surface exists to avoid. Down from the box enters the list, Up and Down
//: walk it, Enter runs the one in hand (a `<button>` does that itself), and
//: Escape hands the caret back to the box rather than closing the panel from
//: under a person who was only browsing.
function agentStarterButtons() {
  return [...document.querySelectorAll("#command-palette-starters [data-example]:not([disabled])")];
}

function agentFocusStarter(delta) {
  const buttons = agentStarterButtons();
  if (!buttons.length) return false;
  const at = buttons.indexOf(document.activeElement);
  //: From the box, Down opens at the top and Up at the bottom, which is what
  //: every menu in this app does and what a person reaching for the last
  //: starter expects.
  const next = at === -1 ? (delta > 0 ? 0 : buttons.length - 1) : at + delta;
  if (next < 0) {
    cmdPaletteInput.focus();
    return true;
  }
  buttons[Math.min(next, buttons.length - 1)].focus();
  return true;
}

$("command-palette-starters")?.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    if (agentFocusStarter(e.key === "ArrowDown" ? 1 : -1)) e.preventDefault();
    return;
  }
  if (e.key === "Escape") {
    //: Not `stopPropagation` on the way out of the panel: Escape twice should
    //: still close it, and the second press arrives with the caret in the box.
    e.stopPropagation();
    cmdPaletteInput.focus();
  }
});

cmdPaletteInput.addEventListener("keydown", (e) => {
  if ((e.key === "ArrowDown" || e.key === "ArrowUp") && !e.shiftKey) {
    //: Only when the box is empty, or the arrows would stop being the arrows
    //: of a multi-line field halfway through writing a paragraph in it.
    if (!cmdPaletteInput.value && agentFocusStarter(e.key === "ArrowDown" ? 1 : -1)) {
      e.preventDefault();
      return;
    }
  }
  if (e.key !== "Enter" || e.shiftKey || e.isComposing || e.keyCode === 229) return;
  e.preventDefault(); // or the newline lands in the box we are about to clear
  cmdPaletteSend();
});

//: Enter and the Send button take the same path.
function cmdPaletteSend() {
  const text = cmdPaletteInput.value.trim();
  if (!text) return;
  cmdPaletteInput.value = "";
  cmdPaletteGrow();
  cmdPaletteAsk(text);
  cmdPaletteInput.focus();
}
$("command-palette-send").addEventListener("click", cmdPaletteSend);


$("command-palette-attach")?.addEventListener("click", () => $("command-palette-attach-input").click());
$("command-palette-attach-input")?.addEventListener("change", (e) => {
  agentStageFiles(Array.from(e.target.files));
  e.target.value = "";
});

//: Built at boot and again after every turn: see `renderCmdPaletteMenu`.
renderCmdPaletteMenu();
$("command-palette-stop")?.addEventListener("click", () => cmdPaletteRun?.abort());
$("command-palette-intro")?.addEventListener("click", (e) => {
  const example = e.target.closest("[data-example]");
  if (!example) return;
  const starter = example.dataset.example;
  rememberAgentStarter(starter);
  cmdPaletteInput.value = starter;
  cmdPaletteGrow();
  cmdPaletteInput.focus();
  //: A complete starter runs; a stem ("Make a note of ") is left for the
  //: person to finish, with the caret already after it. The test is the
  //: trailing space, not the question mark it used to be: half the twelve are
  //: instructions rather than questions ("Tag my untagged notes."), and every
  //: one of those sat in the box waiting for an Enter that said nothing.
  if (!/\s$/.test(starter)) {
    cmdPaletteInput.value = "";
    cmdPaletteAsk(starter.trim());
  }
});

//: **Notes in the command palette** (audit, 2026-10-03: "manage",
//: "categories", "#food" and "move" found nothing). Rows in the editor
//: group's shape (`docPaletteCommands`): a group, a label, a `run`.
//: `paletteMatches` (settings-panes.js) adds them with the typed query and
//: filters them by label like any other row; the per-category and per-tag
//: rows wait for a query so the empty list stays the app's own commands.
//: Each `run` waits a task: the palette runs a row on Enter's keydown, and a
//: sheet that opens and focuses its first row there took that Enter's
//: keypress as a press on it (measured: the Move sheet closed unseen).
const paletteLater = (fn) => () => setTimeout(fn);
