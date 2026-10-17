// help-chat.js: Atlas, the app's Guide, as a chat (the sheet `openHelpChat`
// opens from the status bar, the Settings Help row and Ctrl+Shift+H). Moved out
// of settings.js on 2026-10-05 to leave the boot (tests/test_boot_budget.py):
// nothing here runs until someone asks Atlas something. Loaded by
// `LAZY_MODULES.helpChat` (app.js), whose stand-ins for `openHelpChat`,
// `askAtlas` and `renderAtlasStarters` fetch it and call the real ones. The
// chat's markup is parked in `#atlas-host`, reachable only through
// `openHelpChat`, so its handlers are bound here, when it arrives. The Guide's
// names (`GUIDE_NAME` and the rest) stay in settings.js: the status bar reads
// them at boot.

// --- Help mini AI chat (ROADMAP.md item 40's second half) -------------------
// App-guidance only, backed by /help/ask. Deliberately not persisted: the
// spec asked for no database row at all, so the running transcript lives
// only in this module-level array, it survives a tab switch (this module
// never reloads) but not a page reload, exactly as specified.

//: The three offered before anything is asked. Here rather than in settings.js
//: so every piece of Atlas copy is in one file, and read from there.
//:
//: **Answerable, and about where you are** (INBOX 304, the owner: "the help
//: bot is useless, or the suggested questions are bad or both"). Two faults,
//: both measured. The first starter was "Where do reminders live?" and the
//: corpus could not reach its own reminders entry, so the panel's opening
//: offer was a question it answered with "I'm not sure": that half is fixed
//: in `help_chat.py`, and `test_every_question_the_app_offers_to_ask_atlas_is_answerable`
//: now reads both tables here against the corpus so it cannot come back. The
//: second is these three themselves: a fixed set on every tab, two of which
//: asked how to turn something off, which is a strange thing for an app to
//: suggest you ask about it first. The generic three now say what the guide
//: is, where a surface lives, and what the app keeps, and `ATLAS_TAB_STARTERS`
//: below puts the tab you are actually on first.
const ATLAS_STARTERS = [
  "What can you help me with?",
  "Where do reminders live?",
  "What does the app remember about me?",
];

//: Keyed exactly as `AGENT_TAB_STARTERS` is, and read through the same
//: `agentCurrentTab()`, because the two chat surfaces sit over the same tabs
//: and a second way of naming them is a second thing to keep in step. The
//: difference is what they offer: the agent's starters act on your notebook,
//: these ask what the surface in front of you is for. A tab with no entry
//: here simply shows the generic three.
const ATLAS_TAB_STARTERS = {
  dashboard: ["What can the dashboard show me?", "How do I change the widgets?"],
  notes: ["How does the app file a note?", "What is the writing room for?"],
  chat: ["What can the popup agent do that Chat cannot?", "What are skills?"],
  graph: ["What do entity and board nodes add to the graph?", "What is the graph for?"],
  library: ["What goes in the library?", "How does the whiteboard work?"],
  documents: ["Where do my documents live?", "How do I see a document's history?"],
  timeline: ["What does the timeline show?", "What can I do from the timeline?"],
  reminders: ["Where do reminders live?", "How do I make a reminder recurring?"],
};

let helpChatHistory = [];
let helpChatBusy = false;

// Auto-scroll is only welcome while the reader is already at the bottom, 
// asked for directly: scrolling up to re-read an earlier answer must not
// get yanked back down the moment the next reply lands. A ~40px slop covers
// the last row's own height so "basically at the bottom" still counts.
function helpChatIsNearBottom() {
  const list = $("help-chat-messages");
  if (!list) return true;
  return list.scrollHeight - list.scrollTop - list.clientHeight < 40;
}

function helpChatAppendRow(row) {
  const list = $("help-chat-messages");
  if (!list || !row) return;
  //: The self-description stands down as soon as there is a transcript: it
  //: answers "what is this" and the answer above it now does that better.
  const empty = $("help-chat-empty");
  if (empty) empty.hidden = true;
  //: The starters go with it: they are the empty state's other half, and three
  //: chips above a running transcript is the wall the popup agent's own
  //: starters were told about.
  $("help-chat-starters")?.classList.add("hidden");
  renderHelpChatMenu();
  const stick = helpChatIsNearBottom();
  list.appendChild(row);
  if (stick) list.scrollTop = list.scrollHeight;
}

//: A button that opens where a help entry points: a tab, a Settings
//: section, or one row in it, and lands on a control there, lit.
function helpChatOpenButton(link, label) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "chip chip-interactive";
  btn.dataset.guideLand = link.section ? `${link.section}/${link.target || ""}` : link.tab;
  btn.addEventListener("click", () => guideLand(link));
  chipWords(btn, label || link.label);
  return btn;
}

//: **Where a topic about a whole tab lands** (CHAT_PLAN 9 row 2): the
//: control the tab is for, rather than its top, which left the eye to find
//: the thing the answer was about.
const GUIDE_TAB_LANDING = {
  notes: "entry-content",
  chat: "chat-input",
  graph: "graph-search",
  reminders: "reminder-magic",
  timeline: "timeline-search",
  library: "library-subtabs",
  dashboard: "dash-find",
  //: The Library's New on a wide window, the open document's title on a
  //: phone (its New is in the drawer, off the left edge).
  documents: "library-docs-new doc-title",
};

//: Resolves to the element once it has a box (a lazy tab's bundle, a
//: section built on open), or null when `ms` runs out.
async function guideShown(find, ms) {
  for (let waited = 0; waited < ms; waited += 100) {
    const el = find();
    if (el?.getClientRects().length) return el;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return null;
}

//: When the named control is not there to see (a row shown only with a
//: model, a phone's folded field), the first control on the page instead:
//: a section's top is a heading, and a heading is nothing to press.
//: On screen across: a drawer's control has a box off the left edge.
function guideOnScreen(el) {
  const box = el?.getClientRects().length ? el.getBoundingClientRect() : null;
  return Boolean(box && box.right > 0 && box.left < window.innerWidth);
}

function guideFirstControl(root) {
  const shown = (el) => guideOnScreen(el) && !el.closest(".hidden, [hidden]") && !el.dataset.helpFor;
  return [...(root?.querySelectorAll("input, select, textarea, button, [role=switch]") || [])].find(shown) || null;
}

async function guideLand(link) {
  closeOverlaysForChord();
  if (link.section) await openSettingsModal(link.section, link.target || null);
  else await switchTab(link.tab);
  //: Notes opens on its list; the topics are about writing one.
  if (link.tab === "notes") showNotesSection("capture");
  const ids = (link.target || (link.section ? "" : GUIDE_TAB_LANDING[link.tab])).split(" ").filter(Boolean);
  const live = (id) => (guideOnScreen($(id)) ? $(id) : null);
  //: A row hidden on purpose (no model, not the desktop app) is not waited for.
  const onPurpose = ids.every((id) => $(id)?.closest(".hidden, [hidden]"));
  const named = onPurpose ? null : await guideShown(() => ids.map(live).find(Boolean), 2000);
  const root = link.section ? $(`settings-${link.section}`) : $(`tab-${link.tab}`);
  //: Waited for too: a pane that builds its rows on open has none at first.
  const el = named || (await guideShown(() => guideFirstControl(root), 2500));
  if (!el) return;
  flashRevealed(el);
  //: flashRevealed scrolls only a menu's own list inside a sheet, and the
  //: phone's Settings is a sheet whose pane is laid out again as its rows
  //: arrive: a row below the fold, or pushed past it, was ringed unseen. So
  //: for a second and a half it is put back in view whenever it has left.
  for (const pause of [300, 500, 700]) {
    await new Promise((resolve) => setTimeout(resolve, pause));
    const box = el.getBoundingClientRect();
    if (box.top < 0 || box.top > window.innerHeight - 40) el.scrollIntoView({ block: "center" });
  }
}

function renderHelpChatMessage(role, content, badges = [], sources = [], system = null) {
  const list = $("help-chat-messages");
  if (!list) return null;
  const row = document.createElement("div");
  row.className = `help-chat-msg is-${role}`;
  //: The reply head (INBOX 471): the setting's face and the name, as in Chat.
  if (role === "assistant") row.appendChild(assistantHeadRow(GUIDE_NAME));
  //: **Atlas's answer, or the app's own help** (INBOX 430, the owner: "a
  //: toggle on each answer between the AI's answer and the system-generated
  //: answer from the app's help"). The turn carries both (`system`, laid out
  //: by `help_chat.system_answer`: a heading, where it lives, the text, the
  //: steps); a tab strip of two above the answer swaps the prose between them.
  //: With no model the answer already is the help's, so there is no toggle,
  //: only the link.
  const prose = document.createElement("div");
  prose.className = "help-chat-prose";
  const both = role === "assistant" && system?.content && !content.includes(system.content);
  if (both) {
    const seg = document.createElement("div");
    //: A tab strip, not a pill (INBOX 715: "i dont like pills like that in
    //: popups"; DESIGN.md, "A popup that chooses a kind").
    seg.className = "tabs-line popup-kinds help-chat-views";
    seg.setAttribute("role", "tablist");
    seg.setAttribute("aria-label", "Which answer to show");
    for (const [key, label] of [["ai", `${GUIDE_NAME}'s answer`], ["help", "From the help"]]) {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.dataset.view = key;
      tab.textContent = label;
      const on = key === "ai";
      tab.classList.toggle("active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
      tab.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        const other = [...seg.children].find((t) => t !== tab);
        other.click();
        other.focus();
      });
      tab.addEventListener("click", () => {
        for (const sibling of seg.children) {
          const chosen = sibling === tab;
          sibling.classList.toggle("active", chosen);
          sibling.setAttribute("aria-selected", chosen ? "true" : "false");
          sibling.tabIndex = chosen ? 0 : -1;
        }
        renderMarkdown(prose, key === "ai" ? content : system.content);
        row.dataset.view = key;
      });
      seg.appendChild(tab);
    }
    row.appendChild(seg);
    row.dataset.view = "ai";
  }
  row.appendChild(prose);
  if (role === "assistant") {
    renderMarkdown(prose, content);
  } else {
    prose.textContent = content;
  }
  //: The link the owner asked for: one button that opens the setting or
  //: tab the answer is about, row and all.
  if (role === "assistant" && system?.open) {
    const open = document.createElement("div");
    open.className = "help-chat-open";
    const where = system.open.section ? "Open Settings, " : "Go to ";
    open.appendChild(helpChatOpenButton(system.open, `${where}${system.open.label}`));
    row.appendChild(open);
  }
  //: **Where the answer came from** (INBOX 224). Atlas answers only from the
  //: app's own help topics, and saying which ones is the difference between a
  //: model that might be making it up and a reference that can be checked: the
  //: reader can open the same topic in Settings, Help and read the whole of
  //: it. Under the answer, in the app's own muted small type, not a chip: a
  //: chip is something to press and these are a citation.
  if (role === "assistant" && sources.length) {
    const from = document.createElement("p");
    from.className = "muted help-chat-source";
    from.textContent = `From the app's help: ${sources.join(", ")}`;
    row.appendChild(from);
  }
  if (badges.length) {
    const badgeRow = document.createElement("div");
    badgeRow.className = "help-chat-badges";
    for (const badge of badges) {
      if (system?.open && badge.label === system.open.label) continue;
      badgeRow.appendChild(helpChatOpenButton(badge));
    }
    row.appendChild(badgeRow);
  }
  helpChatAppendRow(row);
  return row;
}

//: The help copy of whatever tab is open, as one block, capped. Read from the
//: `.help-body` popovers the surface already carries (`data-help-for`, the
//: recipe every help '?' in the app uses), so this is the wording the reader
//: can see for themselves rather than a second description written for the
//: model and free to drift from it.
//:
//: The cap is the server's own (`help_chat.MAX_CONTEXT_CHARS`), repeated here
//: so a long tab does not send forty kilobytes to be thrown away.
const HELP_CONTEXT_CHARS = 1200;

//: **Measured before it was trusted, and the first version sent nothing.**
//: `.help-body` is the `data-help-for` popover's own element, and a count in
//: the running app (`scratchpad/ui-sweeps/agentwide.js`) says there are 41 of
//: them and every one is inside the Settings modal or a dialog: not one tab
//: carries any. So the popovers are kept (a tab that grows one is covered
//: from that day) and the tab's controls are added, which every tab does
//: have: a dock of buttons whose `title` and `aria-label` are the app's own
//: words for what each one does.
//:
//: **Attributes only, never the text on screen.** This chat's whole promise
//: is that it cannot read your notebook, and a tab is full of your notebook:
//: `textContent` anywhere near a list of notes would put a note in a prompt
//: by accident, which is the sort of leak nobody notices until it is in a log.
//: `title` and `aria-label` on a control are authored markup and can hold
//: nothing a person wrote.
function helpChatOnScreenHelp() {
  const tab = agentCurrentTab();
  const root = tab ? document.getElementById(`tab-${tab}`) : null;
  if (!root) return "";
  const parts = [];
  const push = (text) => {
    const clean = (text || "").replace(/\s+/g, " ").trim();
    if (clean) parts.push(clean);
  };
  for (const body of root.querySelectorAll(".help-body")) push(body.textContent);
  const seen = new Set();
  for (const control of root.querySelectorAll('.dock [title], [role="toolbar"] [title]')) {
    //: Only what is actually on screen: a dock hides half its controls behind
    //: a menu or a mode, and describing the ones that are not there is worse
    //: than describing none.
    if (!control.offsetParent) continue;
    const name = control.getAttribute("aria-label") || "";
    const line = name && name !== control.title ? `${name}: ${control.title}` : control.title;
    if (seen.has(line)) continue;
    seen.add(line);
    push(line);
    if (parts.join("\n").length > HELP_CONTEXT_CHARS) break;
  }
  if (!parts.length) return "";
  return `Controls on the ${tab} tab, as the app labels them:\n${parts.join("\n")}`.slice(
    0,
    HELP_CONTEXT_CHARS
  );
}

//: **Stop** (the owner, 2026-09-14: "there's no way to stop a response on
//: the atlas interface window"). While a question is out, the send button
//: is the stop button: same place, same size, a square glyph, and a click
//: aborts the request through the fetch signal or halts the reveal where it
//: is. The composer's submit is a form submit; while busy the button is
//: `type="button"` so a click reaches the stop handler and not the form.
let helpChatAbort = null;

function helpChatSetBusy(busy) {
  const sendBtn = $("help-chat-send");
  if (!sendBtn) return;
  sendBtn.type = busy ? "button" : "submit";
  //: `data-needs-model` may have disabled the button; a request that is out
  //: must be stoppable regardless, so the disabled state is parked while
  //: busy and put back after.
  if (busy) {
    sendBtn.dataset.wasDisabled = sendBtn.disabled ? "1" : "";
    sendBtn.disabled = false;
  } else if (sendBtn.dataset.wasDisabled === "1") {
    sendBtn.disabled = true;
    delete sendBtn.dataset.wasDisabled;
  }
  sendBtn.title = busy ? "Stop" : "Ask Atlas";
  sendBtn.setAttribute("aria-label", sendBtn.title);
  sendBtn.classList.toggle("is-stop", busy);
  const icon = sendBtn.querySelector("i");
  if (icon) icon.className = busy ? "ph ph-stop" : "ph ph-paper-plane-right";
}

function helpChatStop() {
  if (!helpChatBusy) return;
  helpChatAbort?.abort();
}

async function submitHelpChatQuestion(question) {
  if (helpChatBusy || !question.trim()) return;
  helpChatBusy = true;
  const input = $("help-chat-input");
  helpChatAbort = new AbortController();
  const signal = helpChatAbort.signal;
  //: The answer's row, and whether the turn failed, for the notice a turn
  //: that ends behind a closed sheet posts (see the `finally` below).
  let answerRow = null;
  let failed = false;
  helpChatSetBusy(true);
  renderHelpChatMessage("user", question);
  // Same "thinking" indicator every other AI-backed surface uses
  // (typingDots(), app.js) rather than a static "Thinking…" line: asked
  // for directly, kept deliberately simple since this reply never streams
  // token-by-token: no "writing" phase, just the wait and then the caret
  // settling below.
  const pending = document.createElement("div");
  pending.className = "help-chat-msg is-assistant is-pending";
  pending.append(assistantHeadRow(GUIDE_NAME));
  //: The app's phase vocabulary (INBOX 649): "Reaching Atlas…" until the
  //: first token, then "is thinking" and "is writing" as the stream says so.
  const pendingLine = typeof progressLine === "function" ? progressLine(null, { persona: GUIDE_NAME }) : null;
  pending.appendChild(pendingLine || document.createTextNode("Reaching Atlas…"));
  helpChatAppendRow(pending);
  if (input) input.value = "";
  try {
    //: **Streamed, with the thinking shown while it is being done.**
    //: Reported: the reply "will be blurted out really fast like it isnt
    //: streaming but just outputting at once", and the thinking "only shows
    //: up after the response is finished". Both were honest descriptions of
    //: what this did: `/help/ask` answers in one piece, so the writing was a
    //: timer here rather than a model typing, and nothing about the turn
    //: could be shown until all of it existed. `/help/ask/stream` sends the
    //: thinking and the answer as they are produced.
    //:
    //: `helpChatStreamTurn` falls back to the one-shot call and the old
    //: reveal when a stream cannot be opened, so a proxy that buffers, or a
    //: build where the route is missing, still answers.
    const result = await helpChatStreamTurn({
      pending,
      line: pendingLine,
      signal,
      //: **Where the question was asked from** (INBOX 190: "give it more
      //: knowledge"). The Guide opens over every tab now, so the tab is half
      //: the question: "how does this work?" means one thing on the Graph tab
      //: and another on Reminders. `context` is the app's own help copy for
      //: what is on screen, which is better reference material than anything
      //: this could be told about a surface in the abstract, and it is already
      //: written, reviewed and kept in step with the UI by the lints.
      body: {
        question,
        history: helpChatHistory,
        tab: agentCurrentTab(),
        context: helpChatOnScreenHelp(),
      },
    });
    const content = result?.content || "Sorry, I couldn't answer that.";
    //: What was on screen when the turn ended: the streamed text itself, or,
    //: on the fallback path, whatever the timed reveal had reached.
    const shown = result?.shown ?? (await helpChatReveal(pending, content, signal));
    pending.remove();
    //: Stopped mid-reveal: what was shown stays, marked, and the history
    //: keeps the whole answer so a follow-up still makes sense to the model.
    answerRow = renderHelpChatMessage(
      "assistant",
      signal.aborted ? `${shown.trimEnd()} (stopped)` : content,
      signal.aborted ? [] : result?.badges || [],
      signal.aborted ? [] : result?.sources || [],
      signal.aborted ? null : result?.system || null
    );
    if (answerRow && result?.greeting && !signal.aborted) renderHelpChatGreeting(answerRow);
    if (answerRow && result?.asks?.length && !signal.aborted) renderHelpChatAsks(answerRow, result.asks, result.asks_to);
    helpChatHistory.push({ role: "user", content: question });
    helpChatHistory.push({ role: "assistant", content });
  } catch (error) {
    pending.remove();
    if (signal.aborted || error?.name === "AbortError") {
      renderHelpChatMessage("assistant", "Stopped.");
    } else {
      failed = true;
      answerRow = renderHelpChatMessage("assistant", "Something went wrong asking that, try again.");
    }
  } finally {
    //: **Closed before the answer arrived** (the owner, 2026-09-23). Closing
    //: the sheet puts the chat back in its hidden host and does not stop the
    //: turn, so the answer lands where nobody can see it; this says it came,
    //: with the way back to it. Not when stopped, and not when the sheet is
    //: open, where the answer is its own notice.
    if (answerRow && !signal.aborted && !document.querySelector('[data-sheet="guide"]')
      && typeof noticeUnwatchedAnswer === "function") {
      answerRow.dataset.answerId = `guide-${Date.now()}`;
      noticeUnwatchedAnswer("guide", question, answerRow.dataset.answerId, { failed });
    }
    helpChatBusy = false;
    helpChatAbort = null;
    helpChatSetBusy(false);
    renderHelpChatMenu();
    input?.focus();
  }
}

//: One streamed turn of the help chat, written into `pending` as it arrives.
//:
//: Returns the same `{content, badges, sources}` the one-shot route returns,
//: plus `shown`, the text that actually reached the screen (they differ when
//: the reader stopped the answer half way). Falls back to `/help/ask` and the
//: timed reveal on any failure to open or read the stream, so the panel
//: answers even where streaming does not survive the trip.
async function helpChatStreamTurn({ pending, signal, body, line = null }) {
  let response;
  try {
    //: Through `api.stream` (F5). It was hand-rolled, and without
    //: `X-Auth-Token` a locked app answered 401, this threw "no stream", and
    //: the fallback below answered in one piece: the owner's "streaming is
    //: also broken" was exactly that, on every locked notebook, while the
    //: streamed route tested green. Silent, so a refusal falls back below.
    response = await api.stream("/help/ask/stream", {
      method: "POST",
      silent: true,
      signal,
      body: JSON.stringify(body),
    });
    if (!response.body) throw new Error("no stream");
  } catch (error) {
    if (signal?.aborted || error?.name === "AbortError") throw error;
    return apiJson("/help/ask", {
      method: "POST",
      signal,
      body: JSON.stringify(body),
    });
  }

  pending.classList.remove("is-pending");
  pending.classList.add("is-streaming");
  pending.replaceChildren(assistantHeadRow(GUIDE_NAME));
  //: **The thinking, on the app's own streamed-reasoning recipe** (INBOX 287,
  //: the owner: "the thinking box doesnt properly render in it either at
  //: least while streaming").
  //:
  //: It used to be a bare `<div>` clipped by CSS to `max-height: 2.6em`.
  //: Measured mid-stream on the running panel: 29px tall, holding 262px of
  //: text, no label and no way to open it, so what was on screen was one and
  //: a half lines from the middle of a sentence in grey. Nothing about that
  //: said "this is the model reasoning", which is what "doesn't properly
  //: render" is describing.
  //:
  //: The app's one Thinking fold (INBOX 457). It folds when the answer
  //: starts, as `foldEarlierThinking` does.
  const think = thinkingFold();
  let thinkRaw = "";
  think.hidden = true;
  const prose = document.createElement("div");
  //: Named so the streaming caret can reach into it. The bubble's last child
  //: is this wrapper, not the paragraph inside it, so the `::after` that draws
  //: the caret landed on a line of its own under the answer (the owner,
  //: 2026-09-21: "the writing caret in the atlas help panel is on the line
  //: below not after the text being streamed"). The rule in
  //: 01-forms-settings.css walks one level further for this class.
  prose.className = "help-chat-prose";
  //: The thinking first, then the phase line, then the answer (the owner,
  //: 2026-10-10: "on the guide the thinking shows below the thinking
  //: indicator and stuff with no gap either"; measured 1px between the line's
  //: foot and the fold). The line says what is happening now, so it sits
  //: next to where the answer will appear, and goes when the answer is
  //: complete (below). The fold's gap is `--space-2` (help-chat-lazy.css).
  pending.append(think);
  if (line) pending.append(line);
  pending.append(prose);
  const list = $("help-chat-messages");
  const toBottom = () => keepAtBottom(list);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  let text = "";
  let done = null;
  //: `raw`, not `line`: that name is the progress line above, and a string
  //: shadowing it threw on the first delta ("Something went wrong").
  const take = (raw) => {
    if (!raw.trim()) return;
    let event;
    try { event = JSON.parse(raw); } catch { return; }
    if (event.type === "thinking") {
      think.hidden = false;
      line?.setPhase("thinking");
      thinkRaw += event.text || "";
      thinkingPaint(think, thinkRaw);
    } else if (event.type === "delta") {
      //: Folded the moment there is an answer to read, not when the turn
      //: ends: by then the reader has already had to scroll past it.
      if (think.open && !text) think.open = false;
      line?.setPhase("writing");
      text += event.text || "";
      renderMarkdown(prose, text);
    } else if (event.type === "done") {
      done = event;
    }
    toBottom();
  };
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffered += decoder.decode(chunk.value, { stream: true });
    const lines = buffered.split("\n");
    buffered = lines.pop() || "";
    for (const raw of lines) take(raw);
  }
  take(buffered);
  line?.remove();
  return {
    content: done?.content || text,
    badges: done?.badges || [],
    sources: done?.sources || [],
    system: done?.system || null,
    greeting: !!done?.greeting,
    asks: done?.asks || [],
    asks_to: done?.asks_to || "chat",
    shown: text,
  };
}

//: Resolves to the text shown so far: the whole answer, or, when the signal
//: fired mid-reveal, the words that had appeared by then. Still the path a
//: fallback to `/help/ask` takes; the streamed turn writes its own text.
function helpChatReveal(row, content, signal = null) {
  return new Promise((resolve) => {
    row.classList.remove("is-pending");
    row.classList.add("is-streaming");
    row.replaceChildren(assistantHeadRow(GUIDE_NAME));
    const prose = document.createElement("div");
    prose.className = "help-chat-prose";
    row.append(prose);
    const still = document.documentElement.dataset.motion === "reduced" || content.length < 40;
    const words = content.split(/(\s+)/);
    let shown = 0;
    const step = () => {
      if (signal?.aborted) {
        resolve(words.slice(0, shown).join(""));
        return;
      }
      shown = still ? words.length : Math.min(words.length, shown + 2);
      renderMarkdown(prose, words.slice(0, shown).join(""));
      const list = $("help-chat-messages");
      if (list) list.scrollTop = list.scrollHeight;
      if (shown >= words.length) {
        setTimeout(() => resolve(content), 150);
        return;
      }
      setTimeout(step, 24);
    };
    step();
  });
}

$("help-chat-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  submitHelpChatQuestion($("help-chat-input")?.value || "");
});
$("help-chat-send")?.addEventListener("click", (event) => {
  if (!helpChatBusy) return; // a plain send is the form's submit
  event.preventDefault();
  helpChatStop();
});

//: New chat, which was a labelled button in the head row and is a menu row
//: now (INBOX 224): the head says who is talking, and a second labelled button
//: up there was what made that row two buttons wide. `kebabMenu` is the app's
//: one menu recipe.
function helpChatNewChat() {
  helpChatHistory = [];
  const list = $("help-chat-messages");
  //: Everything except the self-description, which is what an empty chat is
  //: supposed to show: `replaceChildren()` took it with the transcript and
  //: left a blank rectangle under the field.
  if (list) {
    for (const child of [...list.children]) {
      if (child.id !== "help-chat-empty") child.remove();
    }
  }
  const empty = $("help-chat-empty");
  if (empty) empty.hidden = false;
  $("help-chat-starters")?.classList.remove("hidden");
  $("help-chat-input")?.focus();
}

function renderHelpChatMenu() {
  const host = $("help-chat-menu");
  if (!host || typeof kebabMenu !== "function") return;
  //: "Said" is what the transcript shows, not only what the model answered:
  //: a question stopped before its answer never reaches the history, and
  //: New chat stayed disabled over a transcript with a question and
  //: "Stopped." in it (the owner, 2026-09-14: "I cant select new chat on
  //: the atlas panel if I stopped a response and didnt let it finish").
  const said = helpChatHistory.length > 0 || Boolean($("help-chat-messages")?.querySelector(".help-chat-msg"));
  host.replaceChildren(
    kebabMenu(
      [
        {
          label: "ph:arrow-counter-clockwise New chat",
          title: said
            ? "Forget this conversation and start over"
            : "Nothing asked yet, so there is nothing to clear",
          disabled: !said,
          run: () => (said ? helpChatNewChat() : undefined),
        },
        //: Every topic Atlas answers from, as one page (manual.js, 25c).
        {
          label: "ph:book-open-text Open the manual",
          title: "Every help topic on one page: search it, read it through or print it",
          run: () => lazyScript("/js/manual.js").then((ok) => ok && openManual()),
        },
      ],
      "More actions for this chat"
    )
  );
}

//: The three questions Atlas is opened for, read from `ATLAS_STARTERS` in
//: app.js: every piece of Atlas copy lives in that one table beside
//: `ATLAS_PROMPTS`, and both hosts here read it (INBOX 224).
//:
//: Both hosts are filled from here, and either may be absent (the Settings
//: modal is built once and the sheet exists only while it is open), so this
//: fills whichever it finds.
function renderAtlasStarters() {
  for (const id of ["help-chat-starters", "atlas-row-starters"]) {
    const host = $(id);
    if (!host) continue;
    host.replaceChildren();
    //: The tab you are on decides which three (INBOX 304). Guarded the same
    //: way the table itself was: settings.js runs whether or not app.js has.
    const questions =
      typeof atlasStartersFor === "function"
        ? atlasStartersFor(agentCurrentTab())
        : typeof ATLAS_STARTERS === "object"
          ? ATLAS_STARTERS
          : [];
    for (const question of questions) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "ghost small atlas-starter";
      chip.textContent = question;
      chip.title = `Ask Atlas: ${question}`;
      //: From the Settings row the chip has to open the sheet first; from
      //: inside the sheet it is already open and this is a no-op.
      chip.addEventListener("click", () => {
        openHelpChat();
        askAtlas(question);
      });
      host.appendChild(chip);
    }
  }
}

//: **A greeting gets three things to ask** (INBOX 787: "hey" was answered
//: with the open tab's topic). The reply says who is answering; the tab's
//: starters go under it as chips, the same ones the empty state offers.
function renderHelpChatGreeting(row) {
  helpChatChips(row, atlasStartersFor(agentCurrentTab()), (question) => askAtlas(question), "Ask Atlas: ");
}

function helpChatChips(row, items, pick, titled) {
  const host = document.createElement("div");
  host.className = "help-chat-badges";
  for (const item of items) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "ghost small atlas-starter";
    chip.textContent = item;
    chip.title = titled + item;
    chip.addEventListener("click", () => pick(item));
    host.appendChild(chip);
  }
  row.appendChild(host);
}

//: B11, B86: asked what to ask, the asks are chips that fill Chat's or
//: Ask's box (not sent), in the greeting's chip recipe.
function renderHelpChatAsks(row, asks, to) {
  helpChatChips(row, asks, (ask) => fillAskBox(ask, to), to === "notes" ? "Put in Notes, Ask: " : "Put in Chat: ");
}

async function fillAskBox(text, to) {
  if (to === "notes") {
    await switchTab("notes");
    showNotesSection("ask");
  } else {
    await switchTab("chat");
  }
  const box = $(to === "notes" ? "question" : "chat-input");
  if (!box) return;
  box.value = text;
  box.dispatchEvent(new Event("input", { bubbles: true }));
  //: After the tab switch's own focus.
  setTimeout(() => {
    box.focus();
    box.setSelectionRange?.(text.length, text.length);
  }, 140);
}

//: The one way in with a question already chosen: used by the starters, and
//: by every other place in the app that offers an Atlas question (INBOX 224's
//: second half). Sends it rather than only typing it, because a chip that
//: fills a box and waits is a chip that has done half a job.
function askAtlas(question) {
  const input = $("help-chat-input");
  //: An empty question is the plain "open Atlas" door (the palette command,
  //: the shortcut): open the sheet, put the caret in the field, ask nothing.
  if (!question) {
    input?.focus();
    return;
  }
  if (input) input.value = question;
  submitHelpChatQuestion(question);
}

//: **The Guide, and it has a name now** (INBOX 190, the owner: "maybe give it
//: more knowledge and capabilitie/function and give it a fitting name??";
//: INBOX 193 recorded the recommendation and CHAT_PLAN section 4 decision 13
//: took it). "Guide" rather than a person's name or a mascot: it explains the
//: app and nothing else, it has no access to the notebook, and a name that
//: implies a personality would be the second thing in this app claiming to be
//: an assistant. The heading it already carried said "Ask the guide", so the
//: name was half-chosen and only needed saying out loud.
//:
//: **One instance, moved, not a second one built.** The chat is a stateful
//: surface (a running transcript held in `helpChatHistory`, a form, a clear
//: button, three handlers bound by id), and the way to make it reachable from
//: two more places without any of that drifting is to move the one that
//: exists into the sheet and put it back afterwards. Duplicating the markup
//: would duplicate the ids, which the frontend lints refuse for good reason.
let helpChatHome = null;

let helpChatSheetClose = null;

function openHelpChat() {
  const group = $("help-chat-group");
  if (!group) return null;
  //: Already open: put the caret back in the field rather than stacking a
  //: second sheet over the first, which is what two entry points into one
  //: surface otherwise produce.
  if (document.querySelector('[data-sheet="guide"]')) {
    $("help-chat-input")?.focus();
    return null;
  }
  helpChatHome = { parent: group.parentNode, next: group.nextSibling };
  const menu = $("help-chat-menu");
  const menuHome = menu ? { parent: menu.parentNode, next: menu.nextSibling } : null;
  //: **The '?' belongs beside the line it lengthens, not beside the field**
  //: (INBOX 270). DESIGN.md's help recipe is one line in place and the rest
  //: behind a '?': the line in place here is the head's "About the app, never
  //: your notes", and the '?' was three rows below it in the composer, where
  //: the only thing it sat beside was a text field it does not describe. In
  //: the head it is what the popup agent's own '?' is, next to the title,
  //: and the composer goes back to the two controls every other composer in
  //: this app has. Moved rather than duplicated, for the reason the whole
  //: chat is moved rather than duplicated: one copy, one set of ids.
  const helpToggle = group.querySelector('[data-help-for="help-chat-help"]');
  const helpToggleHome = helpToggle
    ? { parent: helpToggle.parentNode, next: helpToggle.nextSibling }
    : null;
  const close = openSheet({
    label: GUIDE_TITLE,
    name: "guide",
    //: Anchored bottom right rather than across the foot of the window (INBOX
    //: 224): a chat is a column, and the full-width sheet gave Atlas 1356px
    //: lines at 1440. The variant is a class on the recipe, so every other
    //: sheet in the app is untouched.
    variant: "corner",
    modal: false,
    build: (card) => {
      card.appendChild(group);
      group.classList.add("atlas-docked");
      //: The head says who is talking, once: the mark, the name and the
      //: one-line description that used to sit in a second block under a
      //: second "Atlas" (the owner: "redesign this top section"). The
      //: kebab sits top right beside the close, where a menu is expected,
      //: rather than fourth in the composer row.
      const head = card.querySelector(".sheet-head");
      const title = head?.querySelector(".sheet-title");
      if (title) {
        const mark = group.querySelector(".atlas-mark")?.cloneNode(true);
        //: A copied canvas is blank: the head is painted again in its new home.
        if (mark && typeof paintAssistantAvatar === "function") paintAssistantAvatar(mark, Number(mark.dataset.atlasAvatar) || 32);
        const words = document.createElement("span");
        words.className = "atlas-head-words";
        const name = document.createElement("span");
        name.className = "atlas-head-name";
        name.textContent = GUIDE_TITLE;
        const line = document.createElement("span");
        line.className = "muted atlas-head-line";
        line.textContent = GUIDE_LINE;
        words.append(name, line);
        title.replaceChildren(...(mark ? [mark] : []), words);
      }
      //: Title, '?', kebab, close: the surface, what it is, what else you can
      //: do with it, the way out. Inserted in that order, each before the X,
      //: which is the one control the recipe puts there itself.
      if (helpToggle && head) head.insertBefore(helpToggle, head.querySelector(".sheet-close"));
      if (menu && head) head.insertBefore(menu, head.querySelector(".sheet-close"));
    },
    onClose: () => {
      //: Back exactly where it was, so the Help pane is whole the next time
      //: it is opened. `insertBefore` with a null `next` appends, which is
      //: the correct behaviour when it was the last child.
      group.classList.remove("atlas-docked");
      //: **A popover outlives the panel it explains** unless this says so.
      //: `openSheet` takes Escape in the capture phase and stops it, so the
      //: '?' popover's own Escape handler never runs: measured before this
      //: line, opening the '?' and pressing Escape closed the panel and left
      //: the popover sitting on `document.body` over the app, with its home
      //: inside a `hidden` host it could never be seen to belong to again.
      if (typeof closeHelpPopovers === "function") closeHelpPopovers();
      if (helpToggle && helpToggleHome) helpToggleHome.parent.insertBefore(helpToggle, helpToggleHome.next);
      if (menu && menuHome) menuHome.parent.insertBefore(menu, menuHome.next);
      if (helpChatHome) helpChatHome.parent.insertBefore(group, helpChatHome.next);
      helpChatHome = null;
      helpChatSheetClose = null;
    },
  });
  helpChatSheetClose = close;
  //: **After `openSheet` returns, not inside its `build`.** `build` is handed
  //: the card before the card is in the document, so both of these looked the
  //: chat up by id and found nothing: the starters survived only because they
  //: are also built once at boot, and the kebab did not survive at all (it was
  //: empty until the first answer happened to rebuild it).
  renderAtlasStarters();
  renderHelpChatMenu();
  //: `openSheet` focuses the first focusable in the card, which here is the
  //: head's '?' toggle. The field is what a person opening a chat wants.
  $("help-chat-input")?.focus();
  return close;
}

// Moved from wiring.js (boot gzip): every caller is in this file.
//: The tab's questions first, topped up from the generic three, capped at
//: three: the same count the panel was designed around ("Three, not a wall",
//: index.html), and the same cap the reference notes themselves have.
function atlasStartersFor(tab) {
  const here = ATLAS_TAB_STARTERS[tab] || [];
  const out = here.slice(0, 3);
  for (const question of ATLAS_STARTERS) {
    if (out.length >= 3) break;
    if (!out.includes(question)) out.push(question);
  }
  return out;
}

//: **The reply head of surfaces that are not a Chat bubble** (INBOX 471): the
//: guide's rows build one (`assistantHeadRow`), Ask's answer and the writing
//: room's draft carry static `[data-assistant-head]` holders that
//: `paintAssistantHeads` fills once; all paint through `paintAssistantAvatar`,
//: so the Appearance setting and its live repaint reach them.
function assistantHeadRow(name = aiNameNow()) {
  const row = document.createElement("div");
  row.className = "msg-role msg-role-assistant";
  const avatar = document.createElement("span");
  avatar.className = "msg-avatar";
  avatar.setAttribute("aria-hidden", "true");
  const who = document.createElement("span");
  who.textContent = name;
  row.append(avatar, who);
  paintAssistantAvatar(avatar, 20);
  return row;
}
