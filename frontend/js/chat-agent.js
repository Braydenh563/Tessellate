// chat-agent.js: following a stream, the agent's run timeline, the writing
// room. Moved out of app.js on 2026-09-26 as one contiguous range (INBOX 426
// cc, docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- following a stream without fighting the reader -------------------------------
//
// Asked for directly: the chat and the thinking box should scroll themselves
// as the model writes, "but if the user tries to scroll up it will release the
// lock". Both halves matter: a pane that does not follow makes a long answer
// look frozen, and one that follows unconditionally yanks you back to the
// bottom the moment you try to read what scrolled past.
//
// No "is this scroll programmatic?" flag is needed, which is the usual way
// this gets complicated. Distance from the bottom answers it on its own: a
// scroll we caused lands at zero and stays stuck, and a scroll the reader
// caused moves away from zero and unsticks. Scrolling back down re-sticks,
// so getting the follow behaviour back is the obvious gesture rather than a
// button.
const SCROLL_STICK_SLACK = 40; // px: a scrollbar rarely lands exactly at 0

//: A wheel up, drag down or up key lets go at once, and that gesture's own
//: scroll events cannot re-stick it (INBOX 458: a notch moved less than the
//: slack, so the next token dragged the reader back).
const SCROLL_RELEASE_MS = 300;

function followReleased(element) {
  return performance.now() - Number(element.dataset.releasedAt || 0) < SCROLL_RELEASE_MS;
}

//: A nested scroller (code, table, fold) not at its top takes the wheel up itself.
function nestedTakesWheelUp(target, pane) {
  for (let n = target; n && n !== pane && n.nodeType === 1; n = n.parentElement)
    if (n.scrollTop > 0 && /auto|scroll/.test(getComputedStyle(n).overflowY)) return true;
  return false;
}

function followBottom(element) {
  if (!element || element.dataset.followBound === "1") return;
  element.dataset.followBound = "1";
  element.dataset.stuck = "1";
  const release = () => {
    element.dataset.releasedAt = String(performance.now());
    element.dataset.stuck = "0";
  };
  element.addEventListener("wheel", (event) => event.deltaY < 0 && !nestedTakesWheelUp(event.target, element) && release(), { passive: true });
  let touchY;
  element.addEventListener("touchstart", (event) => (touchY = event.touches[0]?.clientY), { passive: true });
  element.addEventListener("touchmove", (event) => {
    const y = event.touches[0]?.clientY;
    if (y > touchY + 2) release();
    touchY = y;
  }, { passive: true });
  element.addEventListener("keydown", (event) => /^(ArrowUp|PageUp|Home)$/.test(event.key) && release());
  //: A late picture grows the pane and a fold the app collapses mid-turn
  //: shrinks it, neither with a scroll event: follow while stuck (INBOX 534).
  //: Capture, since neither event bubbles.
  for (const type of ["load", "toggle"]) {
    element.addEventListener(type, () => (type === "load" || chatController) && keepAtBottom(element), true);
  }
  //: **Only a scroll UP lets go, never growth** (INBOX 534). A scroll event
  //: lands a frame after the pin that caused it; a block that grew the pane
  //: past the slack in between read as the reader leaving, so following
  //: stopped at the next heading, list or code block and the pane fell
  //: behind the writing (the jump button was the only way back).
  let lastTop = element.scrollTop;
  element.addEventListener(
    "scroll",
    () => {
      const distance =
        element.scrollHeight - element.scrollTop - element.clientHeight;
      const up = element.scrollTop < lastTop;
      lastTop = element.scrollTop;
      if (distance <= SCROLL_STICK_SLACK) {
        if (!followReleased(element)) element.dataset.stuck = "1";
      } else if (up) element.dataset.stuck = "0";
      //: The chat pane is the one place this flag has a visible consequence
      //:, see `syncChatJumpLatest`. Guarded by id rather than wired at the
      //: chat's own call site because `followBottom` is what owns the flag,
      //: and a second listener would have to duplicate the same maths.
      if (element.id === "chat-messages") {
        syncChatJumpLatest();
        noteChatPosition(element, distance <= SCROLL_STICK_SLACK);
      }
    },
    { passive: true }
  );
}

//: **A saved chat reopens where you left it** (WORLD_CLASS_PLAN, Placed
//: 2026-09-09 item 99 (b); documents have had it since `docRestorePosition`).
//: A long thread read halfway reopened at its end. Per conversation, in this
//: browser only (how a person reads, not a fact about the chat), the forty
//: most recent; a thread left at its end stores nothing and opens at its end.
const CHAT_POSITIONS_KEY = "chat-positions";
let chatPositionTimer = 0;

function chatPositions() {
  //: A plain object or `{}`, whatever is stored (`prefs.json`).
  return prefs.json(CHAT_POSITIONS_KEY, {});
}

function noteChatPosition(element, atEnd) {
  const id = chatConv?.id;
  if (!id || (typeof chatStreaming !== "undefined" && chatStreaming)) return;
  clearTimeout(chatPositionTimer);
  chatPositionTimer = setTimeout(() => {
    const map = chatPositions();
    if (atEnd) delete map[id];
    else map[id] = { top: Math.round(element.scrollTop), at: Date.now() };
    const keys = Object.keys(map).sort((a, b) => map[b].at - map[a].at);
    for (const stale of keys.slice(40)) delete map[stale];
    try {
      prefs.set(CHAT_POSITIONS_KEY, JSON.stringify(map));
    } catch {
      // Storage full or refused: the thread opens at its end, as before.
    }
  }, 250);
}

// Scroll to the bottom, unless the reader has scrolled away from it.
function keepAtBottom(element) {
  if (!element) return;
  followBottom(element);
  if (element.dataset.stuck !== "0") element.scrollTop = element.scrollHeight;
}

//: **The "still writing" pill, for when the writing is off-screen.**
//:
//: Reported: "I also scrolled up while still streaming the response and the
//: generating and animation disappeared." Nothing had broken: the indicator
//: lives at the end of the transcript, and scrolling back through a long
//: answer puts the end of the transcript below the fold. `followBottom`
//: already records that the reader has taken over, as `data-stuck="0"` on the
//: pane, and deliberately stops auto-scrolling when it happens; what was
//: missing is any way for the app to keep saying "still working" once the
//: place it was saying it has scrolled away.
//:
//: So the pill is shown by exactly that flag, wears the app's own indicator
//: while a turn is live, and falls back to a plain jump-to-latest the rest of
//: the time: which is a control a long transcript wants anyway and this one
//: never had. `chatStreaming` is the same state the stop button reads, so the
//: two cannot disagree about whether a turn is running.
function syncChatJumpLatest() {
  const button = $("chat-jump-latest");
  const pane = $("chat-messages");
  if (!button || !pane) return;
  //: INBOX 34: re-derived from the live rect each call, not the stored flag:
  //: `replaceChildren()` on a new chat fires no scroll event, so a stale
  //: `data-stuck="0"` kept the pill up over an empty transcript.
  //: INBOX 1590: the pill sits in a strip of its own under the transcript
  //: (`.has-jump-gap`), never over a source card or a Next chip. The strip
  //: exists when the transcript overflows the height it would have WITH the
  //: strip, whichever state it is in now, so adding it cannot flip the
  //: overflow it was added for.
  const transcript = pane.parentElement;
  const hasMessages = Boolean(pane.querySelector(".msg"));
  if (transcript?.classList.contains("chat-transcript")) {
    const had = transcript.classList.contains("has-jump-gap");
    const spare = pane.scrollHeight - pane.clientHeight; // read before the strip changes the pane's height
    if (!had) transcript.classList.add("has-jump-gap");
    const gap = parseFloat(getComputedStyle(transcript).paddingBottom) || 0;
    //: **`spare > 0` first (INBOX 1696, "spasm up and down really fast").** A pane never reports a scrollHeight
    //: under its clientHeight, so a thread that fits reads a spare of 0 and `0 + gap` beat the slack on every
    //: other call: the strip went on, off, on, off at each stream delta, resizing the pane by 45px each time
    //: (69 reversals in 3.5s at 4x). A strip is only for a thread that really overflows.
    const needed = hasMessages && spare > 0 && spare + (had ? 0 : gap) > SCROLL_STICK_SLACK;
    if (!needed) transcript.classList.remove("has-jump-gap");
    //: A pane that was following the end keeps following it through the resize.
    if (needed !== had && pane.dataset.stuck !== "0") pane.scrollTop = pane.scrollHeight;
  }
  const distance = pane.scrollHeight - pane.scrollTop - pane.clientHeight;
  //: Far from the bottom is "away" only once the reader left (`followBottom`);
  //: growth under a following pane is the pin's to close (INBOX 534).
  const scrolledAway = distance > SCROLL_STICK_SLACK && pane.dataset.stuck === "0";
  if (distance <= SCROLL_STICK_SLACK && !followReleased(pane)) pane.dataset.stuck = "1";
  const overflowing = pane.scrollHeight - pane.clientHeight > SCROLL_STICK_SLACK;
  //: And never on a transcript with no messages: the owner's screenshot of a
  //: new chat had the pill under the welcome, which is "latest" of nothing.
  button.classList.toggle("hidden", !(scrolledAway && overflowing && hasMessages));
  const streaming = Boolean(chatStreaming);
  button.classList.toggle("is-generating-pill", streaming);
  const label = $("chat-jump-latest-label");
  if (label) label.textContent = streaming ? "Still writing" : "Jump to latest";
  const dots = $("chat-jump-latest-dots");
  if (!dots) return;
  //: Rebuilt only when the phase actually changes: `typingDots` starts an
  //: interval (and, with motion on, CSS animations), and replacing it on every
  //: scroll event would restart both several times a second.
  if (streaming && !dots.firstChild) dots.appendChild(typingDots("Writing"));
  if (!streaming) dots.replaceChildren();
}

//: **What the notebook gave a message, as one card** (INBOX 1460, DESIGN.md
//: "A notebook item on a message"). A note, document, mind map or library
//: file is the staged file card (`attachmentChip`) with its kind's glyph and
//: one muted line (a note's: "Note · 3 days ago"), in the composer with a
//: remove x and above the sent question without. A press previews it
//: (`attachmentPeek`, the citation peek with an Open button); `open` is the
//: card's own door, the one the preview's Open button takes. The name is the
//: note's first line as words, cut at its end only by the card's ellipsis.
const NOTEBOOK_KINDS = {
  note: { icon: "ph-note", word: "Note", open: (i) => flashEntry(i.id) },
  map: { icon: "ph-tree-structure", word: "Mind map", open: (i) => openWhiteboardBoard(i.id) },
  file: { icon: "", word: "File", open: (i) => focusLibraryFile(i.name, `/files/${i.id}`) },
  document: {
    icon: "ph-file-text",
    word: "Document",
    open: (i) => {
      switchTab("documents");
      openDocument(i.id);
    },
  },
};
//: A diagram is an `mmd` document.
NOTEBOOK_KINDS.diagram = { ...NOTEBOOK_KINDS.document, icon: "ph-flow-arrow", word: "Diagram" };

function notebookCard(item, extra = {}) {
  const kind = NOTEBOOK_KINDS[item.kind] || NOTEBOOK_KINDS.document;
  const entry = item.kind === "note" ? allEntries.find((e) => e.id === item.id) : null;
  const board = item.kind === "map" ? mapBoardById(item.id) : null;
  const name = (item.kind === "note" ? noteNamePlain(entry?.content ?? item.name, 160) || "Untitled note" : item.name) || kind.word;
  const facts = [kind.word, entry?.created_at ? relativeTime(entry.created_at) : "", board ? mapCountLabel(board) : ""].filter(Boolean).join(" · ");
  //: Sent, a note shows its next words (two lines) in place of the kind line;
  //: staged, the card stays the file card's height.
  const rest = !extra.onRemove && entry ? plainText(stripFrontmatter(entry.content).trim().split("\n").slice(1).join("\n")).slice(0, 160) : "";
  const card = attachmentChip({
    name,
    icon: kind.icon || undefined,
    facts: item.kind === "file" ? undefined : rest || facts,
    title: `Preview ${kind.word.toLowerCase()} “${name}”`,
    onOpen: (event) => {
      const door = event.currentTarget;
      const keyboard = event.detail === 0;
      Promise.all(["/css/reply-kit-lazy.css", "/js/citation-peek.js", "/js/attachment-peek.js"].map(lazyScript)).then(() => attachmentPeek({ ...item, name, entry, facts }, door, () => kind.open(item), keyboard));
    },
    ...extra,
  });
  card.dataset.kind = item.kind;
  if (rest) card.querySelector(".att-chip-facts").classList.add("att-chip-lines");
  return card;
}

//: The seed for the person's own mark: their profile name, or "You".
function userMarkSeed() {
  return (prefsCache?.display_name || "").trim() || "You";
}

//: **Every mark of the person on screen, redrawn at once** (DESIGN.md's
//: recipe index: "A mark generated from a name"). A holder says it is the
//: person's by carrying `data-user-mark="<size>"`: the profile's head, the
//: Settings head and each of the chat's own bubbles. Called when the
//: preferences arrive and after a save, so a renamed profile redraws the
//: bubbles already in the thread as well as the next one, and the three
//: can never show two different people.
function paintUserMarks() {
  const seed = userMarkSeed();
  //: The faces come after the page (`afterCharacters`, lazy-entries.js).
  afterCharacters(() => {
    for (const holder of document.querySelectorAll("[data-user-mark]")) {
      //: A face drawn from this name stays; the Settings preview replaces it (B47).
      const size = +holder.dataset.userMark || 18;
      if (holder.firstChild?.key === seed + size) continue;
      const face = nameMark(seed, size);
      face.key = seed + size;
      holder.replaceChildren(face);
    }
  });
  const head = document.getElementById("profile-head-name");
  if (head) head.textContent = (prefsCache?.display_name || "").trim() || "Your profile";
  //: The companion, when it is you (INBOX 426 d, the owner: "I changed my
  //: name but the companion which was me didnt update"): it redraws when
  //: the name it is drawn from has changed, and does nothing otherwise.
  syncNameMarkBuddy();
}

//: A user bubble and the cards above it go together (every place a turn is
//: deleted, edited away or regenerated calls this).
function dropChatBubble(node) {
  node.cards?.remove();
  node.remove();
}
//: **The one Thinking fold** (INBOX 457), on every surface that shows
//: reasoning; `tests/test_ui_recipes.py` holds it to this builder.
function thinkingFold(open = true) {
  const el = document.createElement("details");
  el.className = "agent-step thinking-fold";
  el.open = open;
  const summary = document.createElement("summary");
  summary.className = "fold-summary";
  setLabel(summary, "ph:sparkle Thinking");
  const body = document.createElement("div");
  body.className = "thinking";
  el.append(summary, body);
  return el;
}

//: Reasoning as Markdown, data fences out, newest line in view (INBOX 489).
function thinkingPaint(fold, raw) {
  const body = fold.querySelector(".thinking");
  if (!body.paint) body.paint = liveMarkdownRenderer(body, () => keepAtBottom(body));
  body.paint(String(raw || "").replace(/<<<(?:end )?data[^<>]{0,40}>>>/g, ""));
}

function thinkingFoldIn(host) {
  return host.querySelector(".thinking-fold") || host.appendChild(thinkingFold(false));
}

//: **Each reply wears the face of the persona that answered it** (the
//: owner, 2026-09-27: "should we update the assistant chat bubble app logos
//: to the persona avatars used for those specific chat messages??"; decided
//: yes). Atlas, the app's own voice (the default persona, a turn saved with
//: no persona, or one named Atlas), wears Atlas's own face (atlas.js: the
//: bust from 28px, the face icon under it); any other persona its generated face (`nameMark`, DESIGN.md's
//: recipe index: "A mark generated from a name"). The app's emblem is for
//: the app itself, and no reply is the app speaking.
//:
//: **One drawing per face, copied for every reply** (the chat pass's
//: long-chat measure, `chataudit.js` part `long`: a 150-turn chat opened in
//: 939ms when every reply built its own emblem, 410 to 441ms once they were
//: copied). The first reply of a key draws; every later one is a deep copy
//: of that drawing's nodes, which costs no layout of its own and no p5.
//: Keyed on what the drawing depends on: who, the size, Atlas's look and
//: style (a change of look redraws the heads already on the page through
//: `atlasRepaint`, and the new key draws the next reply in the new look).
//: A face under 28px never moves (`watchNameMark`), so a copy needs no
//: observer of its own.
const chatHeadSources = new Map();

function chatHeadIsAtlas(name) {
  const who = String(name || "").trim().toLowerCase();
  return !who || who === String(aiNameNow()).toLowerCase() || who === "atlas";
}

function chatHeadKey(name, size) {
  const atlas = chatHeadIsAtlas(name);
  const look = atlas && typeof atlasLook === "function" ? atlasLook() : "";
  const style = atlas && typeof atlasStyle === "function" ? atlasStyle() : "";
  return `${atlas ? "atlas" : `p:${name}`}|${size}|${look}|${style}`;
}

//: **The assistant's face, decided in one place** (INBOX 463 (2), the owner:
//: "customise the assistant/ai chat message bubbles across all chat
//: interfaces to be either atlas or the animated app logo"). Appearance,
//: Assistant avatar stores `atlas` (the default: what every head wore before)
//: or `emblem`. Every head of the app's own voice asks here, through
//: `paintAssistantAvatar` (Chat, the popup agent, the Atlas guide and help
//: heads); none draws its own, and tests/test_ui_recipes.py holds that.
//: Atlas's own face at the size it is drawn at: under 28px that is its face
//: icon (`atlasDraw`'s tiny level, a miniature bust, 115 nodes), the same Atlas
//: the bust shows larger. The bust itself at 20px drew the whole figure to
//: crop it, 218 nodes a reply: 32,700 nodes in a 150-turn chat, and the first
//: paint went from 580 to 981ms (chatheads.js). The emblem is the app's
//: mark as a few SVG layers (assistant-avatar.js, lazy; `emblemArt`), about
//: 20 nodes a head. Called only once the faces are in (`paintAssistantAvatar`).
function assistantAvatar(size = 20) {
  if (appearancePref("assistant-avatar", "atlas") === "emblem") {
    const box = document.createElement("span");
    box.className = "assistant-emblem";
    box.setAttribute("aria-hidden", "true");
    box.style.setProperty("--emblem-size", `${size}px`);
    assistantEmblemInto(box, size);
    return box;
  }
  const key = chatHeadKey("", size);
  let face = chatHeadSources.get(key);
  if (!face) {
    face = size >= 28 ? atlasAvatar(size, "calm") : atlasDraw(size, "calm");
    chatHeadSources.set(key, face);
  }
  return face.cloneNode(true);
}

//: A head holder remembers its size, so a change of the setting repaints it
//: where it stands (`repaintAssistantAvatars`) rather than at the next reply.
function paintAssistantAvatar(holder, size = 20) {
  holder.dataset.assistantAvatar = String(size);
  //: After the faces (`afterCharacters`, lazy-entries.js): the first heads are
  //: asked for while the scripts load, before `appearancePref` exists.
  afterCharacters(() => holder.replaceChildren(assistantAvatar(size)), () => emblemHead(holder, size));
}

function repaintAssistantAvatars(emblemsOnly = false) {
  for (const holder of document.querySelectorAll("[data-assistant-avatar]")) {
    if (emblemsOnly && !holder.querySelector(".assistant-emblem")) continue;
    if (holder.isConnected) paintAssistantAvatar(holder, Number(holder.dataset.assistantAvatar) || 20);
  }
}

function paintAssistantHeads() {
  for (const holder of document.querySelectorAll("[data-assistant-head]")) {
    if (!holder.firstChild) paintAssistantAvatar(holder, 20);
  }
}

// One "the AI did something" chip in a bubble (Wave G).
// One line of a skill's result: what changed, a way to see it, and, where
// an inverse exists: a way to put it back. The undo is a tool call the
// server handed us, run through the same endpoint the confirm button uses.
function changeRow(change, options = {}) {
  const row = document.createElement("div");
  row.className = "skill-change";
  const label = document.createElement("span");
  label.className = "skill-change-label";
  // `setLabel`, not `.textContent`: a tool's own `label` carries this app's
  // "ph:icon-name Rest of the text" convention (see `_merge_categories` and
  // friends in ai/tools/categories.py, which write exactly that shape), and
  // assigning it raw printed the icon spec as visible text, reported with
  // a screenshot of three agent rows all reading "ph:folder Merged …".
  setLabel(label, change.label || change.tool);
  row.appendChild(label);

  if (change.note_id && change.tool === "delete_note") {
    // A binned note is not in the browse list flashEntry looks in, it is
    // reachable only through the Library's own Bin filter until it is
    // cleared or restored. See flashLibraryItem's own comment.
    row.appendChild(
      smallButton("View in bin", "Show this note in the bin", () =>
        flashLibraryItem("archived", change.note_id)
      )
    );
  } else if (change.note_id) {
    row.appendChild(
      smallButton("View", "Show this note", () => {
        switchTab("notes");
        showNotesSection("browse"); // focusing inside a hidden section does nothing
        flashEntry(change.note_id);
      })
    );
  }
  // The other half of "take me to the thing the agent just changed", the
  // groundwork (`agent._change_document_id`) has resolved a document's real
  // id on every write since §21, but this was the one place that data never
  // reached a button: `create_document`'s own change events carried it and
  // nothing here ever read it.
  if (change.document_id) {
    row.appendChild(
      smallButton("View", "Open this document", () => openDocumentFromNote(change.document_id))
    );
  }
  // ROADMAP.md Tier 2 §13: the same View button, extended to the two kinds
  // that never had a `_change_*_id` resolver at all: a reminder set or
  // completed this turn, and a category a note landed in.
  if (change.reminder_id) {
    row.appendChild(
      smallButton("View", "Show this reminder", () => flashReminder(change.reminder_id))
    );
  }
  if (change.category_name) {
    row.appendChild(
      smallButton("View", "Show this category", () => flashCategory(change.category_name))
    );
  }
  if (change.undo) {
    const undo = smallButton("Undo", "Put this back the way it was", async () => {
      undo.disabled = true;
      try {
        const result = await apiJson("/chat/tools/execute", {
          method: "POST",
          //: `steps` carries a batch undo (several notes or board items).
          body: JSON.stringify({
            name: change.undo.tool,
            arguments: change.undo.arguments,
            steps: change.undo.steps,
            sig: change.undo.sig,
          }),
        });
        if (result?.error) throw new Error(result.error);
        const action = agentUndoActions.get(JSON.stringify(change.undo));
        if (action) settleUndoFromToast(action);
        row.classList.add("skill-change-undone");
        setLabel(label, `${change.label || change.tool}, undone`);
        undo.remove();
        loadEntries();
      } catch (error) {
        undo.disabled = false;
        toast(error.message || voiceLine("failed", { what: "undo that change" }), true);
      }
    });
    undo.dataset.changeUndo = "1";
    row.appendChild(undo);
  }
  if (change.diff) row.appendChild(changeDiff(change.diff));
  return row;
}

//: An edit's lines out and in (`agent._change_diff`), on the diff recipe
//: the confirm card already draws (`.diff-viewer`).
function changeDiff(diff) {
  const viewer = document.createElement("div");
  viewer.className = "diff-viewer";
  for (const [kind, sign] of [["removed", "-"], ["added", "+"]]) {
    for (const line of diff[kind] || []) {
      const el = document.createElement("div");
      el.className = `diff-${kind}`;
      el.textContent = `${sign} ${line}`;
      viewer.appendChild(el);
    }
  }
  if (diff.more) viewer.append(`${nounCount(diff.more, "more line", "more lines")} changed`);
  return viewer;
}

//: **A run's write goes on the app-wide undo stack** (row 4, WORLD_CLASS
//: decision 53): Ctrl+Z after a run takes back its last write, and a run
//: stopped at step 2 leaves step 1's writes there. Redo runs the call again
//: and keeps the inverse of that run. The run's own Undo stays for the whole.
//: The stack entry for each change's undo, so a row's own Undo (the step's
//: list, the run's change list: copies of the change, not the same object)
//: takes it off the stack and Ctrl+Z cannot run it twice.
const agentUndoActions = new Map();
//: **The live action line: which notes a tool call actually reached for.**
//:
//: Asked for: "is it also possible to have live action lines show on the chat
//: ui, to show and visually show as the ai accesses specific notes, files and
//: stuff??"
//:
//: The transcript already said *that* a tool ran, and hid what it returned in
//: a JSON disclosure. What it could not say is *which note*, and an id inside
//: a blob of JSON is not something a person can act on, which is the same
//: complaint that produced the command palette's note links.
//:
//: The backend reads these from the tool's own result rather than from the
//: arguments it was called with, so this row says what happened rather than
//: what the model asked for. Chips open the note, like every other note chip
//: in this app; nothing renders when a call touched nothing.
// Notes and documents share an id space only by accident, id 12 is a
// different object in each table, so the chip has to carry the kind the
// backend decided (`_touched_kind`) and route on it. Clicking a document
// chip through `flashEntry` would open an unrelated note, or nothing.
const TOUCHED_KINDS = {
  note: { icon: "ph:note", title: "Open this note", open: (id) => flashEntry(id) },
  document: {
    icon: "ph:file-text",
    title: "Open this document",
    open: (id) => openDocumentFromNote(id),
  },
  //: A mind map the turn read or built (MINDMAP_PLAN.md §5 item 12: "the chat
  //: transcript"). Deliberately a row in *this* table rather than a new panel:
  //: the four map tools already report what they touched through the same
  //: `touched` channel every other tool uses, so a map becomes a chip in the
  //: line that already exists. `preview: false` because a map's preview is a
  //: picture, not markdown: `toolPreviewBody` fetches `/entries/{id}` and
  //: renders it, which for a board would render the string "# My map".
  map: {
    icon: "ph:tree-structure",
    title: "Open this mind map",
    open: (id) => openWhiteboardBoard(id),
    preview: false,
  },
};

//: **A tool result as things with actions, one renderer per kind** (PLAN.md
//: §4 A1). `TOUCHED_KINDS` above covers the two kinds the backend's `touched`
//: list has ever carried; `cards.py` now sends five, because a file, a board
//: and a reminder are equally openable and had no representation at all, a
//: `search_files` result was a JSON blob behind a disclosure, and every
//: reminder the agent set was a sentence.
//:
//: Deliberately the *same* chip-opens-a-card interaction the touched row
//: already had, rather than a second strip beside it: the chip is the handle
//: and the panel it opens is the card, with that kind's real actions under
//: it. `toolTouchedRow` is now a thin adapter onto this, so an old saved
//: transcript (which has only `touched`) renders through exactly one code
//: path, not a fork that ages differently.
//:
//: Nothing here interpolates user text into markup, every label goes through
//: `setLabel`/`textContent`, and the note and document bodies go through the
//: app's own markdown renderer, the same as everywhere else.
const CARD_KINDS = {
  note: {
    icon: "ph:note",
    title: "Open this note",
    open: (item) => flashEntry(item.id),
    actions: (item) => [
      smallButton("ph:pencil-simple Edit", "Open this note with the editor on", () => {
        //: The same two steps the note list's own Edit does, in the order that
        //: works from here: `flashEntry` switches tab and re-renders, and
        //: `editingId` is what that render reads to open the editor. Set it
        //: first and the jump would clear it.
        flashEntry(item.id);
        openNoteEditor(item.id);
      }),
    ],
  },
  document: {
    icon: "ph:file-text",
    title: "Open this document",
    open: (item) => openDocumentFromNote(item.id),
  },
  file: {
    icon: "ph:paperclip",
    title: "Find this file in the Library",
    //: `focusLibraryFile` (library.js) picks Images or Files from the url and
    //: searches for the name, the three steps this would otherwise be.
    open: (item) => focusLibraryFile(item.label, item.url || item.label),
    actions: (item) =>
      isImageCardUrl(item.url)
        ? [
            smallButton("ph:image View", "Open the full-size image", () =>
              openLightbox([{ filename: item.label, getUrl: () => mediaSrc(item.url) }], 0),
            ),
          ]
        : [],
    //: No fetch: a file's own reading is already on the card as `snippet`
    //: (the OCR/caption line `search_files` returned), and re-reading a
    //: scanned PDF to show one line of it would be the expensive way to say
    //: the same thing. An image gets the lightbox instead, which is the real
    //: full-size view rather than a thumbnail.
    preview: (item, holder) => cardTextPreview(item, holder, "Nothing was read out of this file."),
  },
  board: {
    icon: "ph:squares-four",
    title: "Open this board",
    //: `id` is genuinely nullable here and that is not sloppiness: `null` is
    //: the default board, which is what every whiteboard tool means when it
    //: is given no `board_id` (see `_whiteboard_board_filter` in
    //: ai/tools/whiteboard.py). `?? null` keeps that meaning intact.
    open: (item) => openWhiteboardBoard(item.id ?? null),
    preview: (item, holder) => cardTextPreview(item, holder, "An empty board."),
  },
  //: A mind map the turn read or built (MINDMAP_PLAN.md §5 item 12). Opens
  //: the board; its "preview" is one line, because a board's Entry content is
  //: the single line `# My map` and rendering that as the map would look like
  //: an empty map. `cards.py` sends these as `board`, this entry covers the
  //: `touched` fallback, which names the kind `map`.
  map: {
    icon: "ph:tree-structure",
    title: "Open this mind map",
    open: (item) => openWhiteboardBoard(item.id ?? null),
    preview: (item, holder) => cardTextPreview(item, holder, "A mind map: open it to see the tree."),
  },
  reminder: {
    icon: "ph:alarm",
    title: "Go to Reminders",
    open: () => switchTab("reminders"),
    actions: (item) =>
      item.done
        ? []
        : [
            smallButton("ph:check-circle Mark done", "Complete this reminder", async () => {
              try {
                await reminderPutUndoably(item.id, "Completed a reminder", { done: false }, { done: true });
                item.done = true;
                toast("Reminder marked done.");
                //: Only when the tab is actually showing them, `loadReminders`
                //: re-renders a list that is not on screen otherwise, and the
                //: dashboard's own poll will pick the change up regardless.
                if (prefs.get("activeTab", null) === "reminders") loadReminders();
              } catch (error) {
                toast(error?.message || "That reminder could not be updated.");
              }
            }),
          ],
    preview: (item, holder) => {
      holder.replaceChildren();
      const line = document.createElement("div");
      line.className = "tool-preview-body";
      const due = item.due_at ? new Date(item.due_at) : null;
      line.textContent = due && !Number.isNaN(due.valueOf())
        ? `${item.done ? "Done" : "Due"} ${whenText(due)}`
        : item.done
          ? "Done"
          : "No due date.";
      holder.appendChild(line);
    },
  },
};

//: Which file urls have a full-size view worth offering. A local test rather
//: than library.js's `isImageUrl`, which is not on `window`, duplicating one
//: regex is cheaper than widening another file's surface, and this list only
//: has to be right about what the lightbox can show.
function isImageCardUrl(url) {
  return /\.(png|jpe?g|jfif|gif|webp|bmp|svg|avif|heic|heif|tiff?)$/i.test(String(url || ""));
}

//: The preview for a kind whose text the card already carries. `empty` is
//: said out loud rather than left blank: a panel that opens on nothing reads
//: as a failure to load, which is a different fact from "this file had no
//: text in it".
function cardTextPreview(item, holder, empty) {
  holder.replaceChildren();
  const body = document.createElement("div");
  body.className = "tool-preview-body";
  body.textContent = item.snippet || empty;
  if (!item.snippet) body.classList.add("muted");
  holder.appendChild(body);
}

//: A card that waits on the person is output, never a step: prose folds the
//: step group shut (`closeGroup`) and the Confirm goes with it (audit 1029
//: H1). Every such card is drawn by this, into `recordsHolder`; `tests/test_waiting_cards.py` checks.
const showWaiting = (holder, render, ...args) => render(holder, ...args);

// The agent stopped to ask something. Its options become buttons, and picking
// one sends that text as the next message, so the answer travels through the
// ordinary conversation history rather than through any parked server state.
// Nothing to expire, nothing lost on a reload, and the exchange reads back in
// the saved chat like the short question-and-answer it was.
//: **The question the model asked, while it waits** (INBOX 169, the owner:
//: "should ask user have a textbox in it for the other option?? and the ask
//: user tool should be select and submit, not instant submit when clicked";
//: and 171: an answer typed in the chat bar left the card standing, so the
//: "Other" button then sent a second answer and two replies streamed at
//: once). One card is pending at a time; `pendingAgentQuestion` is how the
//: chat bar's own send settles it, and how a second answer cannot be sent.
let pendingAgentQuestion = null;

//: **One Sources panel, the way every serious answer surface has one.**
//:
//: Reported: *"semantic search and other used notes dont show up in the chat
//: and are not accessible"*, and, of the retrieval line, *"if it says read
//: 9 notes or smth, it should probably show as a better log."*
//:
//: The evidence was there and scattered. Retrieved notes went into a
//: `<details>` whose summary was a sentence; files the agent opened went
//: nowhere at all, because `search_files`/`read_file` are tools and tool rows
//: are a log of *actions*, not a list of *sources*; web pages the same. So a
//: turn that read four files and two notes showed two of the six, under a
//: heading that did not say the word "sources".
//:
//: This is the one place that answers "what is this based on", grouped by
//: kind with a count per group, every row openable. Perplexity's panel is the
//: reference and the reason is not fashion: a reader checking an answer wants
//: the *set* of things it drew on, and a chronological log of calls is the
//: wrong shape for that question even when it contains the same facts.
//:
//: It is built from what already arrived, nothing here re-fetches, and
//: nothing is invented: a source appears because an event named it.
const CHAT_SOURCE_GROUPS = [
  { key: "web", icon: "ph:globe", one: "web page", many: "web pages" },
  { key: "note", icon: "ph:note", one: "note", many: "notes" },
  { key: "document", icon: "ph:file-text", one: "document", many: "documents" },
  { key: "file", icon: "ph:paperclip", one: "file", many: "files" },
  //: A map the turn read or wrote (MINDMAP_PLAN.md §5 item 12). Its icon has
  //: to be listed here as well as in `TOUCHED_KINDS`, because the Sources
  //: panel reads *this* table for the glyph and the count line, a kind
  //: missing from it falls back to `ph:note`, which is how a new kind ends up
  //: looking like it works while calling itself a note.
  { key: "map", icon: "ph:tree-structure", one: "mind map", many: "mind maps" },
  { key: "board", icon: "ph:pencil-circle", one: "board", many: "boards" },
];

//: Which tools produce a *source* rather than a change, and what kind each
//: one yields. Read off the tool name because that is the only thing the
//: event carries that says what was consulted, the label is prose and the
//: result is bounded (§R5 item 4), so neither can be parsed for this.
const SOURCE_TOOLS = {
  search_files: "file",
  read_file: "file",
  read_url: "web",
  web_search: "web",
};

//: The address a card shows under its title, the host, not the whole URL.
//: "arxiv.org" is what tells a reader whether to trust a source; the path is
//: forty characters saying the same thing less legibly.
function sourceHost(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

// --- the writing room: thoughts in, a note out -----------------------------------
// The draft is deliberately kept in the browser (and localStorage) rather than
// in the database. A half-finished draft isn't a note, and quietly filling the
// notebook with them would be worse than occasionally losing one.

const DRAFT_STORE = "writingRoomDraft";

//: The notes this draft is being written from: `{id, label}`, in the order
//: they were picked. Ids go to the server, which reads the notes itself: the
//: client saying what a note contains would be one more copy of the truth.
let draftSources = [];

//: Every draft this session produced, oldest first, so any of them can be
//: come back to. Undo steps back one pass; this is the desk full of earlier
//: pages beside it, and it is the half a single undo cannot give you (a pass
//: you liked, three passes ago).
let draftVersions = [];
const MAX_DRAFT_VERSIONS = 12;

//: Matches `MAX_SOURCES` in api/routes_drafts.py, which is the one that
//: actually binds: this only stops the picker offering a seventh.
const DRAFT_MAX_SOURCES = 6;


function saveDraftLocally() {
  try {
    prefs.set(
      DRAFT_STORE,
      JSON.stringify({
        thoughts: $("draft-thoughts").value,
        draft: $("draft-text").value,
        tags: $("draft-tags").value,
        kind: $("draft-kind").value,
        tone: $("draft-tone").value,
        length: $("draft-length").value,
        sources: draftSources,
        versions: draftVersions,
        noteId: draftNoteId,
        noteLabel: draftNoteLabel,
      })
    );
  } catch {
    /* storage full or blocked, the draft is still on screen */
  }
}

function restoreDraftLocally() {
  try {
    const saved = prefs.json(DRAFT_STORE, null);
    if (!saved) return;
    $("draft-thoughts").value = saved.thoughts || "";
    $("draft-text").value = saved.draft || "";
    $("draft-tags").value = saved.tags || "";
    // A stored value that is no longer an option would leave the select
    // showing its first option while sending the old one, so each is only
    // taken when the select actually holds it.
    for (const [id, value] of [
      ["draft-kind", saved.kind],
      ["draft-tone", saved.tone],
      ["draft-length", saved.length],
    ]) {
      const select = $(id);
      if (value && [...select.options].some((o) => o.value === value)) select.value = value;
    }
    draftSources = Array.isArray(saved.sources) ? saved.sources.slice(0, DRAFT_MAX_SOURCES) : [];
    draftVersions = Array.isArray(saved.versions) ? saved.versions.slice(-MAX_DRAFT_VERSIONS) : [];
    draftNoteId = Number.isInteger(saved.noteId) ? saved.noteId : null;
    draftNoteLabel = saved.noteLabel || "";
    renderDraftSources();
    renderDraftVersions();
    renderDraftTarget();
    updateDraftCount();
  } catch {
    /* unreadable: start clean rather than throwing on load */
  }
}

function draftTranslateKind() {
  let code = "es";
  try {
    code = prefs.get("draft-translate", null) || "es";
  } catch {
    /* storage blocked: the default stands */
  }
  return `translate-${code}`;
}

function renderDraftSources() {
  const host = $("draft-sources");
  const count = $("draft-sources-count");
  if (!host) return;
  host.replaceChildren();
  host.classList.toggle("hidden", !draftSources.length);
  count.textContent = draftSources.length
    ? `${nounCount(draftSources.length, "note")} to write from`
    : "";
  for (const source of draftSources) {
    const chip = document.createElement("span");
    chip.className = "chip draft-source-chip";
    const text = document.createElement("span");
    text.className = "draft-source-text";
    text.textContent = source.label;
    text.title = source.label;
    const drop = document.createElement("button");
    drop.type = "button";
    drop.className = "ghost small icon-only draft-source-drop";
    drop.setAttribute("aria-label", `Stop writing from "${source.label}"`);
    drop.title = "Stop writing from this note";
    setLabel(drop, "ph:x");
    drop.addEventListener("click", () => {
      draftSources = draftSources.filter((s) => s.id !== source.id);
      renderDraftSources();
      saveDraftLocally();
    });
    chip.append(text, drop);
    host.appendChild(chip);
  }
}

function renderDraftVersions() {
  const host = $("draft-versions");
  if (!host) return;
  host.replaceChildren();
  host.classList.toggle("hidden", draftVersions.length < 2);
  if (draftVersions.length < 2) return;
  const label = document.createElement("span");
  label.className = "muted draft-versions-label";
  label.textContent = "Earlier drafts";
  host.appendChild(label);
  draftVersions.forEach((version, index) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `library-chip${version.text === $("draft-text").value ? " active" : ""}`;
    chip.title = `${nounCount(version.words, "word")}, ${version.at}`;
    chip.textContent = `v${index + 1}`;
    chip.addEventListener("click", () => {
      pushDraftUndo();
      $("draft-text").value = version.text;
      updateDraftCount();
      renderDraftVersions();
      saveDraftLocally();
      setDraftStatus(`Back to version ${index + 1}.`);
      announce(`Restored draft version ${index + 1}.`);
    });
    host.appendChild(chip);
  });
}

function rememberDraftVersion(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) return;
  if (draftVersions.length && draftVersions[draftVersions.length - 1].text === trimmed) return;
  draftVersions.push({
    text: trimmed,
    words: wordCount(trimmed),
    at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", ...clockOptions() }),
  });
  if (draftVersions.length > MAX_DRAFT_VERSIONS) draftVersions.shift();
  renderDraftVersions();
}

//: **The note this draft came from, when it came from one.** Set by "Carry on
//: from a note" and by nothing else. While it is set, Save writes back to
//: that note instead of filing a second copy of it, which is the whole
//: difference between carrying a note on and rewriting it somewhere else.
let draftNoteId = null;
let draftNoteLabel = "";

function renderDraftTarget() {
  const chip = $("draft-target");
  const save = $("draft-save");
  chip.classList.toggle("hidden", draftNoteId === null);
  chip.textContent = draftNoteId === null ? "" : `Carrying on: ${draftNoteLabel}`;
  chip.title = draftNoteId === null ? "" : `Saving writes back to "${draftNoteLabel}"`;
  setLabel(save, draftNoteId === null ? "ph:floppy-disk Save as note" : "ph:floppy-disk Save to note");
  $("draft-save-menu-slot")?.classList.toggle("hidden", draftNoteId !== null);
  save.title = draftNoteId === null
    ? ""
    : `Write this back to "${draftNoteLabel}" rather than filing a second copy`;
}

function clearDraftTarget() {
  draftNoteId = null;
  draftNoteLabel = "";
  renderDraftTarget();
}

//: One place that writes the status line, because "error" is a class that
//: sticks: a failure followed by a success used to leave the red on.
function setDraftStatus(text, isError = false) {
  const status = $("draft-status");
  status.classList.toggle("error", !!isError);
  status.textContent = text;
}

//: Both panes' counts (CHAT_PLAN, INBOX 63: "a word count per pane"), from
//: one function so every place that changes either box keeps both honest.
function paneWordCount(id) {
  const text = ($(id)?.value || "").trim();
  const words = wordCount(text);
  return words ? nounCount(words, "word") : "";
}

function updateDraftCount() {
  $("draft-count").textContent = paneWordCount("draft-text");
  const thoughts = $("draft-thoughts-count");
  if (thoughts) thoughts.textContent = paneWordCount("draft-thoughts");
}

// Every AI pass is undoable. "Draft it" replaces the draft AND clears the
// thoughts box, so without this a revision you didn't like destroyed both your
// previous wording and the notes you wrote it from, with nothing to go back
// to. Handing your writing to the AI should never be a one-way door.
const draftUndoStack = [];
const MAX_DRAFT_UNDO = 20;

//: Rule 1.8: each point is also one entry on the app's undo stack, so the
//: pane's Undo, the status bar's, Ctrl+Z outside a field and the history menu
//: are one history. The entry's redo puts back what the pass had written,
//: read when the undo runs, because the pass is still arriving when the
//: point is taken.
function pushDraftUndo() {
  const point = {
    thoughts: $("draft-thoughts").value,
    draft: $("draft-text").value,
  };
  let after = null;
  point.action = pushUndo(
    "Writing desk: the last AI pass",
    () => {
      after = { thoughts: $("draft-thoughts").value, draft: $("draft-text").value };
      const at = draftUndoStack.indexOf(point);
      if (at !== -1) draftUndoStack.splice(at, 1);
      putDraftBack(point);
    },
    () => {
      if (!after) return;
      draftUndoStack.push(point);
      putDraftBack(after);
    }
  );
  draftUndoStack.push(point);
  if (draftUndoStack.length > MAX_DRAFT_UNDO) draftUndoStack.shift();
  updateDraftUndoButton();
}

function putDraftBack(point) {
  $("draft-thoughts").value = point.thoughts;
  // Stepping back past a pass means those thoughts were not folded in after
  // all: otherwise the next Draft would skip them and silently drop an idea.
  foldedThoughts = "";
  $("draft-text").value = point.draft;
  updateDraftCount();
  updateDraftUndoButton();
  saveDraftLocally();
}

function updateDraftUndoButton() {
  const button = $("draft-undo");
  // `draftController` as well as the stack: the undo point for a pass is
  // pushed at its first token, not before the call, so without this the
  // button came back to life half way through a stream and an Undo pressed
  // there would restore the old draft while the new one was still arriving
  // over the top of it.
  button.disabled = !!draftController || !draftUndoStack.length;
  button.title = draftUndoStack.length
    ? `Go back to the version before the last AI pass (${draftUndoStack.length} available)`
    : "Nothing to undo yet";
}

// One-shot AI calls (drafting, document edits) had no way out: press the
// button by mistake or watch it stall, and the only options were waiting or
// reloading the page. Each now runs against an AbortController so it can be
// cancelled, and shows that it's working while it does.
let draftController = null;

// What was last folded into the draft. Kept so a second pass doesn't resend
// thoughts the model has already used, which is the problem clearing the box
// was solving, at the cost of destroying the user's own writing.
let foldedThoughts = "";

