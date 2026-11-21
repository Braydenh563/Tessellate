// chat.js: the chat tab state, clipping, copying, the empty state and the conversation actions
// (menu, transcript, compress). The web panel, model panel and progress pieces are in chat-web.js,
// chat-model-panel.js and chat-progress.js (L-world-class-770). A classic script sharing the page globals.
// --- chat tab (Wave C) ------------------------------------------------------------

let chatConv = { id: null, turns: [] }; // the open conversation
let chatController = null;
//: Chat's composer queue (CHAT_PLAN B3), made one by palette.js's `composerQueue`, off the boot bytes.
const chatQueue = {
  input: () => $("chat-input"),
  //: Also the save after the stream (Stop is already hidden): a send then made a second conversation (sm-1111 row 25).
  finishing: new Set(),
  busy: () => !$("chat-stop").classList.contains("hidden") || chatQueue.finishing.has(chatConv),
  send: (text) => sendChatMessage(text, { keepBox: true }),
  before: () => $("chat-input").parentElement,
};
let lastChatQuestion = ""; // powers Regenerate / Edit & resend
// Set while an `ask` card (renderAgentQuestion) is on screen waiting for a
// reply. Covers typing a free-text answer into the composer, not just
// clicking one of the option buttons, both are "answering the agent's
// question" and both need answering_agent set (Tier 1 §4), or a typed "yes"
// reads as small talk and strands the thing it was actually answering.
// Consumed (read once, then reset) by the very next sendChatMessage call.
let chatAwaitingAgentAnswer = false;

// A summary standing in for the first `covered` turns when this conversation
// is sent to the model (§35I). Deliberately *beside* the turns rather than
// replacing them: the transcript on screen and the saved conversation are
// untouched, so this narrows what the model reads and loses nothing. Undo is
// therefore setting this back to null.
let chatSummary = null; // { text, covered }

// A hover-reveal row of small actions under a chat bubble. Each action is
// { label, title, onClick }. onClick gets the click event so buttons can
// give inline feedback (e.g. a copy tick).
//: How many actions a message row shows before the rest fold into a ⋯. Five is
//: what fits beside the shortest message this app produces without the row
//: being wider than the bubble it belongs to.
const MSG_ACTIONS_VISIBLE = 5;

//: **What the server takes, in one place** (audit 1031 AI10, AI9): a long
//: question sent whole to a speculative route came back 422 twice per question,
//: and one sent to the finder cost 2.2 s of search at 20,000 characters. Each
//: route's cap is here, and a request clips to it before it is sent.
//: `cap` is `search/query.py`'s `QUESTION_CAP` (a test holds them equal): the
//: most of a question any search reads, warm or not. The chat send
//: itself keeps its own 20,000 (`chatTooLong`): the model gets the whole
//: question. `warmMax`: the warm (`/search/warm`) is for a sentence typed on
//: a pause; a pasted passage is not worth a vector made ahead of Enter, so it
//: is not sent at all. One object, so no new names in the shared scope.
const CLIP_LIMITS = ((cap) => ({ cap, warmMax: 500, warm: cap, search: cap, question: cap, followQuestion: 500, followAnswer: 20000 }))(4000);

//: Over the cap, the opening and the end are kept, not the opening alone
//: (INBOX 1528): a paste with its ask under it reached the server without
//: the ask, which the server's long-question reading (`long_question.py`)
//: then could not find. The last quarter of the cap, at most 1,000.
function clipFor(route, text) {
  const all = String(text ?? ""), cap = CLIP_LIMITS[route];
  if (all.length <= cap) return all;
  const tail = Math.min(1000, cap >> 2);
  return `${all.slice(0, cap - tail - 2)}\n\n${all.slice(-tail)}`;
}

//: **Work that follows an answer waits for the answer's frame** (audit 1031
//: AI9): the quick-access lists, the suggested-question chips and the reminder offer
//: started in the same task that painted the last token, so the first frame
//: after the answer carried them too (a 4x phone send: 922 ms in 9 long tasks).
//: The browser's idle time, and no later than a second and a half; without
//: `requestIdleCallback`, a short timer. A property of `CLIP_LIMITS`, not a
//: name of its own: the shared scope's name count only goes down.
CLIP_LIMITS.afterAnswer = (fn) => (window.requestIdleCallback || ((later) => setTimeout(later, 120)))(fn, { timeout: 1500 });

//: **One action list for an assistant message, wherever it was built.**
//:
//: There were two: the live stream's and the reopened-conversation path's, and
//: they had already drifted, the replayed one had Edit and no Read aloud, the
//: live one the reverse, and a bug fixed in one stayed in the other. This is
//: the same "two implementations of one control" lesson the Library kebab
//: taught, applied before it costs another round.
//:
//: The order is Odysseus's footer order, with this app's own capture actions
//: after it: what you do to the *answer* first, what you do with it second.
function bodyTextWithCitations(node) {
  const links = [...node.querySelectorAll(".answer-citation-link")];
  const digits = links.map((l) => l.textContent);
  links.forEach((l) => { l.textContent = `[${l.textContent}]`; l.before(" "); });
  try {
    return node.innerText.trim();
  } finally {
    links.forEach((l, i) => { l.previousSibling.remove(); l.textContent = digits[i]; });
  }
}

// "8192" is a number you have to read; "8k" is one you can glance at. Under a
// thousand stays exact, because rounding 900 to "1k" would be a lie in the
// direction that matters when the window is nearly full.
function compactTokens(n) {
  if (n == null) return "?";
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n);
}

// Copying has to work in three descending steps. `navigator.clipboard` exists
// only in a SECURE CONTEXT: fine on http://localhost, `undefined` on a LAN
// address or a tunnel, which made every copy button a no-op (worst on the Logs
// screen, where the text is the error you are reporting). So: the modern API,
// then `execCommand` (works on plain http), then the text in a selected
// textarea so Ctrl+C still gets it out.
function copyViaTextarea(text) {
  const staging = document.createElement("textarea");
  staging.value = text;
  // Off-screen rather than hidden: a display:none element cannot be selected,
  // and the selection is the whole mechanism here.
  staging.setAttribute("readonly", "");
  staging.style.position = "fixed";
  staging.style.top = "-1000px";
  staging.style.opacity = "0";
  document.body.appendChild(staging);
  staging.select();
  staging.setSelectionRange(0, text.length);
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  }
  staging.remove();
  return copied;
}

function flashCopied(button) {
  if (!button) return;
  // innerHTML, not textContent: an icon-only button (setLabel(el, "ph:...")
  // with no trailing text) renders as a bare <i> with empty textContent, so
  // saving/restoring textContent silently wiped the icon back to blank once
  // the checkmark's timeout fired instead of putting it back.
  //: A second press inside 1.2 s keeps the real icon (INBOX 1423).
  if (!button._copiedWas) button._copiedWas = button.innerHTML;
  clearTimeout(button._copiedTimer);
  setLabel(button, "ph:check");
  button.classList.add("is-done");
  button._copiedTimer = setTimeout(() => {
    button.innerHTML = button._copiedWas;
    button._copiedWas = null;
    button.classList.remove("is-done");
  }, 1200);
}

async function copyToClipboard(text, button) {
  if (!text) return false;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      flashCopied(button);
      return true;
    }
  } catch {
    // Permission refused or the context is not what it claimed, fall through
    // rather than reporting failure while a working path is still untried.
  }
  if (copyViaTextarea(text)) {
    flashCopied(button);
    return true;
  }
  lazyScript("/js/chat-edit.js").then(() => showCopyFallback(text));
  return false;
}

//: `showCopyFallback`, the last resort, is chat-edit.js's (lazy: the boot
//: gzip ratchet); `copyToClipboard` fetches it when it is needed.

//: `editAndResend`, a question edited in place, is chat-edit.js (lazy: the
//: boot gzip ratchet; the Edit button in chat-agent.js fetches it first).

// Re-run the most recent question and REPLACE the previous answer in place
// (user request: a redo shouldn't stack a second answer below the old one).
// The original "you" bubble stays; only the assistant bubble is swapped.
//: `questionForBubble` is chat-edit.js, its one caller (boot gzip ratchet).

//: **Regenerate from *this* answer, not just the last one.**
//:
//: Odysseus's message footer has had this since it shipped, and it is the one
//: that matters on a long thread: the answer you want re-done is rarely the
//: newest. Everything after the question is removed first, an answer
//: regenerated in the middle of a thread that keeps the turns built on the old
//: one is a transcript that contradicts itself.
const regenerateFromBubble = (bubble, opts) => lazyScript("/js/chat-edit.js").then(() => regenerateFrom(bubble, opts));

//: How many times the last question has been asked again (`retries`, kept on
//: the function, not a top-level let): sent as `attempt`, so an answer
//: composed from the notes is worded anew (CHAT_PLAN decision 34).
const regenerateLastAnswer = () => lazyScript("/js/chat-edit.js").then(() => regenerateLast());

//: One line offering Atlas a question, for the empty states that are a person
//: looking at a surface they have not used yet. Built here rather than written
//: into three blocks of markup, for the same reason the popover line is.
//: `label` is for a question too long for a phone's line, said shorter; the
//: question sent is still `question`.
function atlasSuggestion(question, label = `Ask Atlas: ${question}`) {
  const line = document.createElement("p");
  line.className = "muted help-atlas";
  //: **An offer, drawn as the app's other offers.** It was a `.linklike`, an
  //: underlined accent line that read as a web link out of the app (the
  //: owner, of the empty chat: styled "as an underlined web link"). It wears
  //: the suggestion chip the chat's own starters wear (08-consistency.css,
  //: `.atlas-starter`), with Atlas's compass in front, because pressing it
  //: asks a question the same way theirs do.
  const ask = document.createElement("button");
  ask.type = "button";
  ask.className = "atlas-suggest";
  setLabel(ask, `ph:compass ${label}`);
  ask.title = "Opens Atlas with this question";
  ask.addEventListener("click", () => askAtlasAbout(question));
  line.appendChild(ask);
  return line;
}

//: The starters are not coming (or took too long): the skeletons go and an
//: empty box hides, as `loadChatSuggestions` leaves it when it has no picks.
function chatEmptySettle(empty) {
  if (!empty.classList.contains("chat-empty-waiting")) return;
  empty.classList.remove("chat-empty-waiting");
  const suggest = $("chat-suggest");
  if (!suggest || !empty.contains(suggest)) return;
  clearSkeletons(suggest);
  suggest.classList.toggle("hidden", !suggest.children.length);
}

// The welcome shown in an empty chat so the page isn't a blank box.
function renderChatEmptyState() {
  const box = $("chat-messages");
  if (box.querySelector(".msg") || box.querySelector(".chat-empty")) return;
  if (chatConv.private) return chatPrivateEmpty(box);
  const empty = document.createElement("div");
  empty.className = "chat-empty";
  const emblem = document.createElement("div");
  emblem.id = "chat-empty-emblem";
  emblem.className = "emblem emblem-centred";
  emblem.setAttribute("aria-hidden", "true");
  const title = document.createElement("p");
  title.className = "empty-title";
  // Personas already voice the AI's replies and the dashboard greeting
  // (librarian.resolve_persona_prompt's own docstring: "the voice the user
  // picked is used consistently everywhere"), this was the one place left
  // that stayed generic regardless of which persona was active, so opening
  // a new chat under "Coach" or a custom persona still greeted you as
  // nobody in particular (ROADMAP Tier 3 §21).
  const activePersona = personaDisplayName(prefsCache && prefsCache.active_persona);
  //: The default librarian is Atlas (INBOX 225): the empty chat says so by
  //: name, and the explanation that used to sit under it as a paragraph is
  //: one line with the rest behind the app's '?' (the owner: "the text below
  //: it needs to be updated and potentially moved to a '?' tooltip button").
  const aiName = aiNameNow();
  title.textContent =
    activePersona === aiName ? `Explore your notebook with ${aiName}` : `Chat with your ${activePersona}`;
  const blurb = document.createElement("p");
  blurb.className = "muted chat-empty-line";
  //: No trailing space: the '?' that used to follow this sentence is in the
  //: corner now (INBOX 236), and a line ending in a space is a line that
  //: centres a pixel off.
  //: In Atlas's own voice (INBOX 394 b), and still the same promise: the
  //: answers come from the notes, with the notes they came from.
  //: **One line, at every width** (the orchestrator's review, 2026-09-26:
  //: `chatemptyhelp.js` failing its one-line check at 1280). The blurb is
  //: capped at 52ch and the sentence it replaced was 95 characters, two lines
  //: at 1024, 1280, 1366 and 1440 alike (measured, 529px wide each time).
  //: This one is 518px at all four, one line.
  blurb.append(
    document.createTextNode(
      activePersona === aiName
        ? "Ask me anything, and I'll show you the notes behind the answer."
        : "Ask anything; the answers come from your saved notes."
    )
  );
  //: The '?' is the dock's now (INBOX 479; INBOX 236 had taken it out of
  //: the middle of this welcome to its corner). Its words name the persona.
  const helpText = $("chat-help-text");
  if (helpText) {
    helpText.textContent =
      `${aiName} answers from your saved notes and shows the notes behind each ` +
      "answer. In Agent mode it can also create, tag, link and organise notes " +
      "for you, and asks before changing a note.";
  }
  empty.append(emblem, title, blurb);
  //: One line about the other assistant (INBOX 224). The empty chat is where
  //: somebody asks the app a question it cannot answer from notes, "how do I
  //: turn this off", and Atlas is the one that can.
  //: Said shorter (INBOX 464 (16)): the default label named Atlas twice in
  //: one line and took two lines at 390.
  empty.appendChild(atlasSuggestion("What can Atlas change in my notebook?", "Ask Atlas what it can change"));
  //: **The starters belong in the empty state, not in a strip above the
  //: composer.** Measured at 1440px: the welcome was a 326px column of centred
  //: text in a 1062px pane with four suggestion chips jammed against the
  //: composer 550px below it, two halves of one invitation, as far apart as
  //: the layout allowed. `#chat-suggest` still exists and is still filled by
  //: `loadChatSuggestions`; it is *moved here* while the pane is empty and
  //: goes back to the dock the moment a message arrives, so nothing else has
  //: to know where it lives.
  const suggest = $("chat-suggest");
  if (suggest && !suggest.classList.contains("hidden")) {
    empty.appendChild(suggest);
  } else if (suggest) {
    //: **The card is drawn at once, the starters are skeletons** (the owner,
    //: 2026-10-12: the page "appears a second or two late and all at once").
    //: It used to wait unseen for them (INBOX 580: it grew round them in
    //: view, 222 to 296px, layout shift 0.015). Now the mark and the heading
    //: paint on the first frame and `#chat-suggest` holds four skeleton
    //: pieces in the starters' own box, so nothing moves when the real ones
    //: replace them (`loadChatSuggestions` calls `clearSkeletons`, which
    //: settles them in). A render with no fetch coming (`pending` unset a
    //: tick later) settles at once; a fetch that hangs settles at 3s.
    empty.classList.add("chat-empty-waiting");
    suggest.replaceChildren();
    suggest.classList.remove("hidden");
    showSkeletons(suggest, 4, "span");
    empty.appendChild(suggest);
    setTimeout(() => loadChatSuggestions.pending || chatEmptySettle(empty), 0);
    setTimeout(() => chatEmptySettle(empty), 3000);
  }
  box.appendChild(empty);
  // Animated like the ai-mark: a new chat is the AI waiting, and the slow
  // turn says so. Stills itself under Settings, Appearance, Motion.
  renderEmblem(emblem, 52, { animate: true }); // after insertion: see addAssistantBubble
  fitChatEmpty();
  //: **Watched, but never from inside the observer's own callback** (the
  //: owner's log, 2026-09-24: "ResizeObserver loop completed with undelivered
  //: notifications", many a second, with the web panel opened and widened).
  //: The callback only notes the pane's new size; the fit runs on the next
  //: frame, only for a change of 2px or more, and flips the welcome at most
  //: once in 500ms, so no arrangement of panes can make it chase itself.
  if (!fitChatEmpty.watching && typeof ResizeObserver === "function") {
    fitChatEmpty.watching = true;
    let last = { w: 0, h: 0 };
    let queued = false;
    new ResizeObserver((entries) => {
      const rect = entries.at(-1).contentRect;
      if (Math.abs(rect.width - last.w) < 2 && Math.abs(rect.height - last.h) < 2) return;
      last = { w: rect.width, h: rect.height };
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        fitChatEmpty();
      });
    }).observe(box);
  }
}

function clearChatEmptyState() {
  const empty = $("chat-messages").querySelector(".chat-empty");
  if (!empty) return;
  //: The chips are on loan from the dock (see `chatEmptyState`), so they go
  //: home before the welcome is thrown away, removing them with it would
  //: lose the element every other caller still holds by id.
  const suggest = empty.querySelector("#chat-suggest");
  if (suggest) {
    suggest.classList.add("hidden");
    clearSkeletons(suggest);
    document.querySelector(".chat-dock")?.prepend(suggest);
  }
  empty.remove();
}

// --- the conversation actions menu, the transcript and compressing context -----------

//: **The ⋯ that holds everything you do to a whole conversation.**
//:
//: Reported: the header "feels fake, with features and ui elements like
//: buttons just slapped on there with no design thought". Four ghost buttons
//: of equal weight, one of them a red Delete, sat opposite the title on
//: every conversation, so the most destructive action in the tab was also one
//: of its most prominent controls, and the row read as a pile rather than as
//: a header.
//:
//: Fork and Compress rows click their visible buttons, so the disabled state
//: and handler stay in one place; Export and Delete have no button of their
//: own (Brief 88: the hidden proxies stacked over Fork) and call theirs.
function mountChatActionsMenu() {
  const host = $("chat-actions-menu");
  if (!host || host.childElementCount) return;
  const click = (id) => () => $(id)?.click();
  host.appendChild(
    kebabMenu(
      [
        //: Grouped (DESIGN.md: past five rows a menu is): this chat, a copy of
        //: it kept somewhere, and the one that ends it. Eight rows read as one
        //: list before (menus.js).
        { label: "ph:pencil-simple Rename this chat", group: "chat", run: () => renameCurrentConversation() },
        { label: "ph:ghost Private chat", group: "chat", run: () => chatPrivateToggle() },
        { label: "ph:git-branch Fork this chat", group: "chat", title: $("chat-fork")?.title, run: click("chat-fork") },
        {
          label: "ph:arrows-in Compress the earlier messages",
          group: "chat",
          title: $("chat-compress")?.title,
          run: click("chat-compress"),
        },
        { ...featureModelMenuItem("chat"), group: "chat" },
        //: The way into Activity when nothing runs: its status slot appears only while something does (HR6).
        { label: "ph:activity Activity and past runs", group: "chat", run: () => openActivity("runs") },
        { label: "ph:download-simple Export as Markdown", group: "keep", run: () => exportChatMarkdown() },
        {
          //: Odysseus's "Save to Documents", which lands better here than it
          //: does there: this app *has* a Documents tab, and a conversation
          //: worth keeping is usually worth keeping beside the notes it drew
          //: on rather than as a file in a downloads folder.
          label: "ph:file-text Save this chat as a document",
          group: "keep",
          run: () => chatKeep("doc"),
        },
        {
          label: "ph:tree-structure Make a mind map of this chat",
          group: "keep",
          run: () => chatKeep("map", chatTranscriptText(), $("chat-title")?.textContent),
        },
        {
          label: "ph:copy Copy the whole transcript",
          group: "keep",
          run: async () => {
            const text = chatTranscriptText();
            if (!text) return toast("There is nothing to copy yet.");
            copyToClipboard(text);
          },
        },
        { ...appLinkMenuItem("chat", () => chatConv.id), group: "keep" },
        { label: "ph:trash Delete this chat", group: "end", danger: true, run: () => deleteCurrentChat() },
      ],
      "More actions for this conversation"
    )
  );
}

//: The transcript as text, the thing a person actually wants when they say
//: "copy this chat", and previously only reachable by exporting a file.
function chatTranscriptText() {
  const parts = [];
  for (const msg of $("chat-messages")?.querySelectorAll(".msg") || []) {
    const who = msg.classList.contains("user") ? "You" : msg.dataset.persona || aiNameNow();
    const body = msg.querySelector(".msg-body, .bubble-answer");
    //: A user bubble's words as sent: a long question's body is drawn clipped (`addBubble`).
    const text = msg.dataset.sent ?? (body ? bodyTextWithCitations(body) : "");
    if (text) parts.push(`**${who}:** ${text}`);
  }
  return parts.join("\n\n");
}

// --- compressing this conversation's context (§35I) --------------------------
//
// Asked for directly: *"there should be a tool as well as a manual command or
// something to be able to compress chat context on longer chats so the AI can
// better continue."* This is the manual half, which §35I says ships first
// because it cannot misfire: you press it, you read what it produced, and only
// then does the model see it instead of the turns it replaces.
//
// Nothing is deleted. The transcript on screen and the saved conversation keep
// every turn: `chatSummary` only changes what `chatHistoryToSend` hands the
// model, so Undo is one assignment.

// How many turns to leave alone at the end. Compressing the exchange you are
// still in the middle of is how a summary loses the thing you are talking
// about right now.
const KEEP_RECENT_TURNS = 2;

async function compressChatContext() {
  const covered = chatConv.turns.length - KEEP_RECENT_TURNS;
  if (covered < 2) {
    toast("There isn't enough conversation to compress yet.");
    return;
  }
  const button = $("chat-compress");
  setBusy(button, true, "Summarising…");
  try {
    const result = await apiJson("/chat/compress", {
      method: "POST",
      body: JSON.stringify({ history: chatConv.turns.slice(0, covered) }),
    });
    showCompressReview(result, covered);
  } catch (error) {
    toast(error?.message || voiceLine("failed", "summarise this conversation"));
  } finally {
    setBusy(button, false);
  }
}

function compressSizeText(n) {
  return n < 1000 ? `${Math.round(n)} characters` : `${Math.round(n / 10) / 100}k characters`;
}

// The summary, before it is used, editable, because a summary you cannot
// correct is one you have to trust blindly, and this one is about to be the
// model's only memory of the first half of the conversation.
function showCompressReview(result, covered) {
  const panel = $("chat-compress-panel");
  const box = $("chat-compress-text");
  box.value = result.summary;
  $("chat-compress-stats").textContent =
    `${covered} messages → ${compressSizeText(result.chars_after)} ` +
    `(was ${compressSizeText(result.chars_before)}). Edit it if it missed something.`;
  panel.classList.remove("hidden");
  panel.dataset.covered = String(covered);
  box.focus();
}

function applyCompression() {
  const text = $("chat-compress-text").value.trim();
  const covered = Number($("chat-compress-panel").dataset.covered || 0);
  if (!text || covered < 1) return;
  chatSummary = { text, covered };
  $("chat-compress-panel").classList.add("hidden");
  renderCompressionState();
  toast(`Using a summary in place of the first ${covered} messages.`);
}

// The badge that says the model is reading a summary rather than the thread,
// with the way back. A compression the user cannot see is a conversation
// quietly answering from something they never read.
function renderCompressionState() {
  const badge = $("chat-compressed");
  if (!badge) return;
  badge.classList.toggle("hidden", !chatSummary);
  if (chatSummary) {
    setLabel(badge.firstElementChild, `ph:arrows-in first ${chatSummary.covered} summarised`);
  }
}
