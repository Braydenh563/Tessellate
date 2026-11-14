// chat.js: the chat tab, message meta, the web panel, citing a page,
// compressing context. Moved out of app.js on 2026-09-26 as one contiguous
// range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md). A classic
// script sharing app.js's globals, loaded in app.js's old order; nothing in an
// earlier file calls into it while the page loads (scratchpad/appjs-map.js
// --check).

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

// --- web panel: search + reader view ----------------------------------------
// Deliberately not an embedded browser. Pages are fetched and stripped to
// text by the backend, so nothing from a third-party site ever executes here.
//
//: **A reading pane, not a form** (the owner, 2026-09-24: "the web browser
//: sidebar needs a major improved modern and professional redesign and
//: feature improvement"). Measured before with
//: `scratchpad/ui-sweeps/webpanel.js`: four boxed controls above the results
//: in two heights and two radii, the engine's state as a box with its own
//: boxed Stop, three worded buttons stacked over the page, and the page text
//: in a bordered box that scrolled inside a column that also scrolled. The
//: shape now is the one every reader pane the owner compares it to shares
//: (Arc's side panel, Safari's reader, Perplexity's sources): a quiet head, one
//: field, a list, and a page.

let webReaderPage = null; // the page currently open in the reader
//: The request in flight, a search or a page, so Stop can cancel it and a
//: second search supersedes the first rather than racing it. Without this a
//: slow first answer could land after a fast second one and replace it.
let webRequest = null;

function webRequestStart() {
  webRequest?.abort();
  const controller = new AbortController();
  webRequest = controller;
  $("web-stop").classList.remove("hidden");
  $("web-panel").setAttribute("aria-busy", "true");
  return controller;
}

function webRequestEnd(controller) {
  //: Only the request that is still current may clear the busy state: an
  //: aborted one finishing late must not hide the Stop of its successor.
  if (webRequest !== controller) return false;
  webRequest = null;
  $("web-stop").classList.add("hidden");
  $("web-panel").removeAttribute("aria-busy");
  return true;
}

function stopWebRequest() {
  const controller = webRequest;
  if (!controller) return;
  controller.abort();
  webRequestEnd(controller);
  const status = $("web-status");
  status.classList.remove("error");
  status.textContent = "Stopped.";
  $("web-query").focus();
}

function webReaderIsOpen() {
  return !$("web-reader").classList.contains("hidden");
}

function closeWebReader() {
  $("web-reader").classList.add("hidden");
  renderWebSearchHistory();
  //: Back lands where it left: on the result that was opened, so the arrow
  //: keys carry on down the list from there rather than from the top.
  const opened = webReaderPage
    ? [...document.querySelectorAll("#web-results .web-result-title")].find(
        (el) => el.dataset.url === webReaderPage.url
      )
    : null;
  (opened || $("web-query")).focus();
}

function toggleWebPanel(force) {
  const panel = $("web-panel");
  const show = force ?? panel.classList.contains("hidden");
  panel.classList.toggle("hidden", !show);
  //: A class the narrow layout's CSS reads, not a `:has()` on the column (AI9).
  panel.closest(".tab-main")?.classList.toggle("web-open", show);
  if (show) {
    // Say up front when searching cannot work, rather than after a search has
    // failed. Web access is off by default, this is a local-first app and
    // that is the right default, so the commonest first experience of this
    // panel is typing a query into a box that was never going to answer. The
    // switch is one click away, and naming where it lives is the difference
    // between a dead end and a setting.
    const status = $("web-status");
    if (prefsCache && !prefsCache.web_search_enabled) {
      status.replaceChildren();
      status.classList.remove("error");
      status.appendChild(
        document.createTextNode("Web access is off. Turn it on in ")
      );
      const link = document.createElement("button");
      link.type = "button";
      link.className = "link-button";
      link.textContent = "Settings, Web search";
      link.addEventListener("click", () => {
        toggleWebPanel(false);
        openSettingsModal("websearch");
      });
      status.appendChild(link);
      status.appendChild(document.createTextNode(" to search from here."));
    } else if (!$("web-results").childElementCount) {
      status.textContent = "";
    }
    //: The "..." is drawn with the head, from what was last known; the
    //: status call below (seconds while Docker answers) only updates it.
    renderWebPanelMenu(webEngineInfo);
    //: Private web search needs SearXNG: the optional-package notice (extra-notice.js).
    if (prefsCache && prefsCache.web_search_enabled && prefsCache.search_provider !== "duckduckgo") extraNoticeMount(panel, "searxng");
    refreshWebSearxngStrip();
    renderWebSearchHistory();
    //: The page you were reading is still there when the panel comes back.
    //: Closing it used to throw the reader away, so glancing at the
    //: conversation cost you your place in the article.
    if (!webReaderIsOpen()) $("web-query").focus();
  } else {
    clearTimeout(webSearxngTimer);
    if (webRequest) {
      webRequest.abort();
      webRequestEnd(webRequest);
    }
  }
}

// Feedforward for whether the private, local SearXNG instance is actually
// running: not just the after-the-fact "answered by SearXNG" a result
// already carries. Deliberately far lighter than Settings, Web search's
// full management UI (install progress, port diagnostics, reinstall): only
// "is it on", as a dot in the head, and "turn it on or off", in the kebab
// beside it.
let webSearxngTimer = null;

function setWebEngineDot(state, provider) {
  const dot = $("web-engine-dot");
  const words = webEngineWords(state, provider);
  dot.dataset.state = state;
  dot.title = words;
  dot.setAttribute("aria-label", words);
}

//: The head's kebab: the engine's one command, the settings behind it, and
//: the recent searches. Rebuilt only when what it would say changes, and
//: never while it is open, since replacing an open menu's opener strands the
//: menu `kebabMenu` has already moved to <body>.
let webPanelMenuKey = "";

function renderWebPanelMenu(engine) {
  const host = $("web-panel-menu");
  if (!host) return;
  const hasHistory = loadWebSearchHistory().length > 0;
  const key = `${engine?.state || ""}|${engine?.running ? 1 : 0}|${hasHistory ? 1 : 0}`;
  if (key === webPanelMenuKey && host.firstChild) return;
  if (host.querySelector("[aria-expanded='true']")) return;
  webPanelMenuKey = key;
  const items = [];
  if (engine) {
    if (engine.state === "installing") {
      items.push({
        label: "ph:hourglass Installing SearXNG",
        title: "SearXNG is installing; Settings, Web search shows its progress",
        disabled: true,
        run: () => openSettingsModal("websearch"),
      });
    } else if (engine.running) {
      items.push({
        label: "ph:stop-circle Stop SearXNG",
        title: "Stop the local SearXNG instance",
        run: () => ensureModule("webClip").then(() => setWebSearxngRunning(false)),
      });
    } else {
      items.push({
        label: engine.state === "absent" ? "ph:download-simple Install SearXNG" : "ph:play Start SearXNG",
        title:
          engine.state === "absent"
            ? "Install SearXNG locally and start it, searches then never leave this machine"
            : "Start the local SearXNG instance",
        run: () => ensureModule("webClip").then(() => setWebSearxngRunning(true)),
      });
    }
  }
  items.push({
    label: "ph:gear-six Web search settings",
    title: "Choose the engine and manage SearXNG in Settings",
    run: () => openSettingsModal("websearch"),
  });
  if (hasHistory) {
    items.push({
      label: "ph:clock-counter-clockwise Clear recent searches",
      title: "Forget the searches listed under the field",
      run: clearWebSearchHistory,
    });
  }
  host.replaceChildren(kebabMenu(items, "Web search options"));
}

//: **The engine's last known state, so the menu is not empty while Docker
//: answers** (the owner, 2026-10-10: "the start searxng button doesnt appear
//: for a while"; driven with the status call held 4000 ms: the control came
//: at 4017 ms). A fresh page has no answer yet and the call can take seconds,
//: so the settled one is kept under `webEngine` and drawn first; the call
//: still has the last word.
let webEngineInfo = prefs.json("webEngine");

async function refreshWebSearxngStrip() {
  await ensureModule("webClip");
  const provider = (prefsCache && prefsCache.search_provider) || "auto";
  clearTimeout(webSearxngTimer);
  if (prefsCache && !prefsCache.web_search_enabled) {
    setWebEngineDot("off", provider);
  } else if (provider === "duckduckgo") {
    setWebEngineDot("remote", provider);
  }
  //: DuckDuckGo never touches SearXNG, so the dot above keeps saying DuckDuckGo
  //: answers; the menu still offers the engine's command, since starting it is
  //: how someone on DuckDuckGo gets to try SearXNG (B55: the item was "gone").
  const info = await apiJson("/websearch/searxng/status").catch(() => null);
  if (!info || !info.backend) {
    // No usable backend (Docker or a virtualenv) to run it at all, Settings
    // → Web search explains why; there is nothing to start from here.
    webEngineInfo = null;
    if (!prefsCache || prefsCache.web_search_enabled) setWebEngineDot("remote", provider);
    renderWebPanelMenu(null);
    return;
  }
  const running = info.state === "running" && info.responding;
  const state = info.installing
    ? "installing"
    : running
      ? "running"
      : { running: "starting", absent: "absent" }[info.state] || "stopped";
  webEngineInfo = { state, running };
  prefs.setJSON("webEngine", webEngineInfo);
  if (!prefsCache || prefsCache.web_search_enabled) setWebEngineDot(provider === "duckduckgo" ? "remote" : state, provider);
  renderWebPanelMenu(webEngineInfo);
  // Keep polling while it settles, same as Settings' own richer view:
  // otherwise "starting" can stick with no way to tell it's still moving.
  if (state === "installing" || state === "starting") {
    webSearxngTimer = setTimeout(refreshWebSearxngStrip, state === "installing" ? 2000 : 3000);
  }
}

// Last few distinct web queries, newest first, asked for directly ("missing
// features... history"). Client-side only: these are the person's own past
// searches, same privacy tier as the search itself (already opt-in, already
// logged locally via manager.log_action), nothing new leaves the machine.
const WEB_SEARCH_HISTORY_KEY = "webSearchHistory";
function loadWebSearchHistory() {
  try {
    const raw = prefs.json(WEB_SEARCH_HISTORY_KEY, []);
    return Array.isArray(raw) ? raw.filter((q) => typeof q === "string") : [];
  } catch {
    return [];
  }
}

//: Forget the web panel's recents with the way back for ten seconds, and a row
//: in Settings, Recent changes (search-suggest.js `clearRecentSearches`, lazy).
function clearWebSearchHistory() {
  ensureModule("searchSuggest").then(() => clearRecentSearches("web"));
}

// "Ask about this" used to drop `About <url>, ` into the chat box and stop
// there. The model cannot open a URL, so it answered from the address text,
// which is why this read as simply not working (user-reported). It now closes
// the web panel, writes a question naming the page, and lets the agent's
// read_url tool fetch it. The tool needs web search on, so that is checked
// first and offered rather than failing silently.
async function askAboutPage(url, title) {
  if (!(prefsCache && prefsCache.web_search_enabled)) {
    toast("Turn on Web search first, reading a page needs it.", "info");
    return;
  }
  // Reading a page is a tool call, so agent mode has to be on for this turn.
  const input = $("chat-input");
  const label = (title || "").trim() || url;
  input.value = `Read ${url} and tell me about it, "${label}".`;
  toggleWebPanel(false);
  input.focus();
  // Sent with tools forced on, whatever the toggle says: the request is
  // meaningless without the one tool that can fetch the page.
  await sendChatMessage(undefined, { useTools: true });
}

//: The reader itself is in web-clip.js (lazy; the boot gzip ratchet).
function openWebReader(url) {
  $("web-status").textContent = "Opening…";
  ensureModule("webClip").then(() => showWebReader(url));
}

//: The reader's blocks as plain Markdown, shared by Save as note and Cite in
//: chat so the two cannot disagree about what the page says.
function webPageMarkdown(page) {
  return (page.blocks || [])
    .map((b) =>
      b.type === "heading"
        ? `\n${"#".repeat(Math.min(6, (b.level || 2) + 1))} ${b.text}`
        : b.type === "li"
          ? `- ${b.text}`
          : b.text
    )
    .join("\n")
    .trim();
}

// --- citing a web page in the chat ---------------------------------------------
//: **Cite in chat** attaches a page to the next message as a chip, the way a
//: selection or a note does, so the question is yours rather than the canned
//: one "Ask about this" sends. What the model is given is the text the reader
//: already fetched, so it needs no tool call and no second fetch, and it works
//: in Ask mode as well as Agent.
//:
//: One page at a time, like a selection: a citation is "this, about which I
//: am about to ask", not a collection.
let attachedWebPage = null;
//: The page the last answer cited, for a spoken ask about that page (`webFollowUp`).
//: A field rather than a top-level `let` (the global-scope ratchet): it was
//: taken out as "never read" while chat-attach.js still read it, so every
//: Chat send threw a ReferenceError (found by Brief 67's sweep).
const chatWeb = { lastUrl: null };
//: The budget for the page's text in the prompt. A long article runs to
//: tens of thousands of characters; the opening of a page is where its claim
//: is, and a local model's context is the scarcest thing in the round.
const WEB_CITE_CHARS = 6000;

async function citeWebPage(pageOrResult) {
  let page = pageOrResult;
  //: A result row has a snippet, not the page: fetch it first, through the
  //: same route the reader uses, so what is cited is what the reader shows.
  if (!page.blocks && !page.text) {
    try {
      page = await apiJson(`/websearch/read?url=${encodeURIComponent(page.url)}`);
    } catch (error) {
      toast(error.message || "Couldn't read that page.", true);
      return;
    }
  }
  attachedWebPage = {
    url: page.url,
    title: page.title || page.domain || page.url,
    domain: page.domain || "",
    text: (webPageMarkdown(page) || page.text || "").slice(0, WEB_CITE_CHARS),
  };
  renderWebPageAttachment();
  //: The composer is beside the panel above 1100px; below it the panel covers
  //: the conversation, so it closes to show the chip it just made.
  if (webPanelIsNarrow()) toggleWebPanel(false);
  const input = $("chat-input");
  input?.focus();
  announce(`${attachedWebPage.title} attached to your next message.`);
}

function renderWebPageAttachment() {
  const box = $("chat-web-attachment");
  if (!box) return;
  box.replaceChildren();
  box.classList.toggle("hidden", !attachedWebPage);
  if (!attachedWebPage) return;
  box.appendChild(
    attachmentChip({
      name: attachedWebPage.title,
      icon: "ph-globe",
      facts: attachedWebPage.domain || "Page",
      title: `${attachedWebPage.title} (${attachedWebPage.url})`,
      removeTitle: "Don't send this page with your message",
      onRemove: () => {
        attachedWebPage = null;
        renderWebPageAttachment();
        announce("Page removed.");
      },
    }),
  );
}

// What the backend says about the model in use. Fetched when the Models
// screen is drawn rather than polled: none of it changes while the app runs.
//: **The context window, per model, set by hand.**
//:
//: Asked for (INBOX 77): "the window itself should be manageable by the user
//: and auto when set ... a `num_ctx` preference per model in Settings, Models
//: with Auto (the model file's value) or a number, sent on every request; the
//: badge shows 'used / window'". The badge half shipped first; this is the
//: window half.
//:
//: The box edits whichever chat model is selected and the app stores one entry
//: per model (`model_context_windows` in preferences), so switching models
//: switches what the box says rather than carrying one machine-wide number
//: across a 4k model and a 32k one. Empty is auto, which is stored as the
//: absence of a number: `usable_context` in provider.py then reads the window
//: from the model file or the server's catalog exactly as it always has.
//:
//: **Saved on change and on blur, not on a Save button**, because this screen
//: has no Save button and every other control on it writes as you touch it. A
//: number box fires `change` when it is committed (Enter, or focus leaving),
//: which is the event that means "I meant that", and `input` would PUT once
//: per keystroke while somebody types 16384.
let modelContextModel = "";

function renderModelContextBox(modelName, spec) {
  const box = $("model-context-window");
  const note = $("model-context-note");
  if (!box) return;
  modelContextModel = modelName || "";
  const windows = (prefsCache && prefsCache.model_context_windows) || {};
  const set = Number(windows[modelContextModel]);
  //: Not `box.value = set || ""`: a stored 0 is not a window, and writing "0"
  //: into the box would show a number that means auto, which is the one thing
  //: this control must never do.
  box.value = set > 0 ? String(set) : "";
  box.disabled = !modelContextModel;
  const usable = spec && spec.usable_context;
  //: B56: the empty box says what Auto found, not only the word.
  box.placeholder = usable ? `Auto (${Number(usable).toLocaleString()})` : "Auto";
  if (!note) return;
  if (!modelContextModel) {
    note.textContent = "";
    return;
  }
  //: The note says what is actually in force, which is the only way to tell
  //: "auto found 32k" apart from "auto fell back to 4k", and those look
  //: identical in an empty box.
  note.textContent = set > 0
    ? `Running ${modelContextModel} at ${set.toLocaleString()} tokens. Clear the box for auto.`
    : spec && spec.context_reason
      ? `Auto: ${spec.context_reason}`
      : usable
      ? `Auto: ${Number(usable).toLocaleString()} tokens, from the model.`
      : "Auto: the app uses the model's own window.";
}

async function renderModelSpec(modelName) {
  const box = $("model-spec");
  if (!box) return;
  const spec = await apiJson(`/models/spec?name=${encodeURIComponent(modelName || "")}`, {
    silent: true,
  }).catch(() => null);
  if (!spec) {
    box.classList.add("hidden");
    renderModelContextBox(modelName, null);
    return;
  }
  renderModelContextBox(modelName, spec);
  // Tri-state, and the third state is the point: null means "this backend
  // doesn't report capabilities", which is not the same as "no". Saying "no"
  // about a model that works fine would send someone chasing a problem that
  // isn't there.
  // `== null`, not `=== null`: the whole point of this helper is that "not
  // declared" must never render as a confident "no" (§35C), and a *missing*
  // key is exactly as unknown as an explicit null. With `===` an absent field
  // fell through to the falsy branch and printed "no", the reported bug,
  // surviving in the one case nobody checked.
  const canDo = (value) => (value == null ? "not reported" : value ? "yes" : "no");
  const rows = [
    ["Size", spec.parameters],
    ["Quantisation", spec.quantisation],
    ["Family", spec.family],
    // Two windows, deliberately. A 128k model is *run* at less because the KV
    // cache scales with the window, without both numbers the percentage on
    // each message looks wrong to anyone who knows what the model can hold.
    [
      "Reads at once",
      spec.context_length
        ? `${compactTokens(spec.usable_context)} tokens` +
          (spec.context_length > spec.usable_context
            ? ` (it can hold ${compactTokens(spec.context_length)})`
            : "")
        : null,
    ],
    ["Loaded at", spec.loaded_context_length ? compactTokens(spec.loaded_context_length) : null],
    ["Can use tools", canDo(spec.supports_tools)],
    // "Can think: no" was reported for a model that visibly thinks (§35C),
    // and the label was the lie rather than the value: this is the *declared*
    // capability, whether the backend supports a thinking toggle, and a
    // model can still emit inline <think> tags without declaring it, which
    // `split_thinking` picks up and shows. Saying "declared" makes the two
    // facts distinguishable instead of contradictory.
    ["Thinking switch", canDo(spec.supports_thinking)],
    ["Can see images", canDo(spec.supports_vision)],
  ].filter(([, value]) => value != null && value !== "");

  box.replaceChildren();
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    box.append(dt, dd);
  }
  box.classList.toggle("hidden", rows.length === 0);

  renderModelHealthNote(spec);
}

// A model health card: every number above already existed, but nothing said
// what it *means*: "this model has an 8k window" doesn't answer "will it
// forget what I said earlier in a long chat" (BACKLOG.md §95 item A.2).
// Mirrors ai/context.py's own shares (CHARS_PER_TOKEN, OUTPUT_RESERVE_SHARE,
// HISTORY_SHARE) rather than asking the backend, since this is explicitly a
// rough estimate: context.py's own docstring: "approximately right on every
// model beats being exactly right on one", and an average exchange length
// is itself a guess, so a precise-looking number here would be a false
// promise the actual conversation could contradict either way.
function renderModelHealthNote(spec) {
  const note = $("model-spec-health");
  if (!note) return;
  const usable = spec && spec.usable_context;
  if (!usable) {
    note.classList.add("hidden");
    return;
  }
  const CHARS_PER_TOKEN = 4;
  const OUTPUT_RESERVE_SHARE = 0.15;
  const HISTORY_SHARE = 0.15;
  const AVG_CHARS_PER_EXCHANGE = 500; // a short question + a real answer
  const historyChars =
    usable * CHARS_PER_TOKEN * (1 - OUTPUT_RESERVE_SHARE) * HISTORY_SHARE;
  const roughTurns = Math.round(historyChars / AVG_CHARS_PER_EXCHANGE / 5) * 5;

  if (roughTurns < 5) {
    note.textContent =
      "A small window: a back-and-forth chat will start losing earlier messages within a few exchanges. Notes and documents are unaffected; only the conversation itself is short-lived.";
  } else if (roughTurns <= 40) {
    note.textContent = `What this means for you: a long chat will start dropping its earliest messages after roughly ${roughTurns} exchanges. Atlas can still recall anything from further back by re-reading the note or asking again, it just won't be sitting in view.`;
  } else {
    note.textContent =
      "A large window: a normal conversation is very unlikely to ever run out of room.";
  }
  note.classList.remove("hidden");
}

// Both pickers for the response preset: the Chat toolbar's and the Notes
// quick-ask box's. Two controls, one stored preference, the quick-ask box
// always obeyed the saved mode and simply had no way to set it, so this is a
// second way in rather than a second setting. Listed rather than found by
// class so a stray `.small-select` can never join by accident.
const RESPONSE_MODE_SELECTS = ["response-mode-select", "ask-mode-select"];

// The response presets, fetched once. Served by /chat/modes rather than
// listed here so adding a fourth is a change to `ai/presets.py` alone (§11).
//: The answer is read once and painted again when the Chat pane is built.
const loadResponseModes = (() => {
  let body = null;
  const paint = () => {
    const selects = RESPONSE_MODE_SELECTS.map((id) => document.getElementById(id)).filter(Boolean);
    if (!selects.length || !body || !body.modes) return;
    const active = body.modes.find((m) => m.id === body.active);
    for (const select of selects) {
      select.replaceChildren();
      for (const mode of body.modes) {
        const option = document.createElement("option");
        option.value = mode.id;
        option.textContent = mode.label;
        option.title = mode.description;
        if (mode.id === body.active) option.selected = true;
        select.appendChild(option);
      }
      if (active) select.title = active.description;
    }
  };
  onSurface("chat", paint);
  return async () => {
    body = await apiJson("/chat/modes", { silent: true }).catch(() => null);
    paint();
  };
})();

// Picking in one picker moves the other. Without this the two would drift
// apart the moment either was touched, and the one you weren't looking at
// would be lying about what the next answer will do.
async function setResponseMode(chosen) {
  for (const id of RESPONSE_MODE_SELECTS) {
    const select = $(id);
    if (!select) continue;
    select.value = chosen;
    const option = select.selectedOptions[0];
    select.title = (option && option.title) || "";
  }
  // Changing the picker changes the default too, otherwise someone who works
  // in Quick would re-pick it on every reload. The *request* still carries the
  // mode per turn, so this is "remember what I chose" rather than a second
  // setting that can disagree with the dropdown.
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ response_mode: chosen }),
  }).catch(() => {});
}

//: A persona's mark into its holder: the generated face for every persona
//: but the app's own voice, which keeps the app's emblem. Shared by the
//: persona rows in Settings and the chat's persona picker, so the two
//: cannot draw one persona two ways.
function fillPersonaMark(holder, name, size = 20) {
  if (!holder) return;
  //: Nothing to draw a face from (no name yet): the app's own animated mark,
  //: never an empty box (the owner: "the default for no avatar selected
  //: should be the animated app logo everywhere").
  if (!name) {
    renderEmblem(holder, size, { animate: true });
    return;
  }
  //: Atlas has a face of its own now (`atlasMark`, avatars.js): the logo's
  //: ring of linked notes orbiting a globe in the accent colour. `nameMark`
  //: draws it for the assistant's name. The chat's reply label keeps the
  //: live logo, so the app's mark and Atlas's face both stay in the app.
  //: The faces arrive after the page (`afterCharacters`, lazy-entries.js).
  afterCharacters(() => holder.replaceChildren(nameMark(name === aiNameNow() ? "Atlas" : name, size)), () => plainHead(holder, name));
}

function personaOptions() {
  // Built-ins + the user's custom personas (deduped: an edited built-in
  // is stored under the same name); the active one pre-selected.
  const select = $("persona-select");
  const custom = (prefsCache && prefsCache.personas) || [];
  const active = personaDisplayName(prefsCache && prefsCache.active_persona);
  const names = [
    ...new Set([aiNameNow(), "Coach", "Analyst", ...custom.map((p) => p.name)]),
  ];
  // name -> its prompt, so the dropdown can describe each persona on hover.
  const overrides = new Map(custom.map((p) => [p.name, p]));
  const describe = (name) => {
    const prompt = (overrides.get(name) || {}).prompt || builtinPersonas()[name] || "";
    return prompt.length > 200 ? prompt.slice(0, 199) + "…" : prompt;
  };
  select.replaceChildren();
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    option.title = describe(name); // hover shows what this persona does
    if (name === active) option.selected = true;
    select.appendChild(option);
  }
  // Also surface the active persona's description on the closed select itself.
  //: While no model runs the gate (`syncModelGatedControls`) has put the reason
  //: in the title; the description waits in `enabledTitle` for its return.
  if (select.dataset.enabledTitle !== undefined) select.dataset.enabledTitle = describe(active);
  else select.title = describe(active);
  // The full prompt, not the hover excerpt: the preview panel exists precisely so
  // the instructions the model is given aren't a 200-character preview.
  const fullPrompt = (name) =>
    (overrides.get(name) || {}).prompt || builtinPersonas()[name] || "";
  //: The preview shows the text the model gets, so `{ai_name}` is filled
  //: here the way `librarian.fill_ai_name` fills it on the server.
  const showPrompt = (name) => {
    $("persona-prompt-text").textContent =
      fullPrompt(name).replaceAll("{ai_name}", aiNameNow()) || "This persona adds no instructions of its own.";
  };
  showPrompt(active);
  //: A native select cannot draw a picture in an option, so the chosen
  //: persona's mark sits beside it and follows the choice.
  fillPersonaMark($("persona-select-mark"), select.value);
  select.onchange = () => {
    if (select.dataset.enabledTitle !== undefined) select.dataset.enabledTitle = describe(select.value);
    else select.title = describe(select.value);
    showPrompt(select.value);
    fillPersonaMark($("persona-select-mark"), select.value);
  };
}

// You could choose a persona but never read what it told the model to do, 
// which makes the choice a guess. This shows the actual system prompt.
function togglePersonaPrompt() {
  const panel = $("persona-peek-panel");
  const showing = panel.classList.toggle("hidden");
  $("persona-peek").setAttribute("aria-expanded", !showing);
}

// A running total for the whole conversation. Per-message counts can't tell
// you when a thread has grown heavy enough to be worth starting over.
function renderChatUsage(tokens) {
  const el = $("chat-usage");
  if (!el) return;
  const total = Number(tokens) || 0;
  el.hidden = total === 0;
  el.textContent = total ? `${formatTokens(total)} tokens` : "";
  renderChatTurnCount();
}

//: **The conversation-level context meter.**
//:
//: Fed from the last turn's `stats` (prompt tokens against the window the turn
//: was budgeted for: `context_tokens`, which `ollama_client` has always sent).
//: Thresholds are Odysseus's: quiet under 70%, a warning at 70, a real alarm
//: at 85, because past about 85 the next turn starts losing the oldest part of
//: its own prompt and the answer quietly gets worse with nothing on screen
//: saying why.
function renderChatContextMeter(stats) {
  const pill = $("chat-context");
  if (!pill) return;
  const used = stats && Number(stats.prompt_tokens);
  const window = stats && Number(stats.context_tokens);
  if (!used || !window) {
    pill.hidden = true;
    return;
  }
  const pct = Math.min(100, Math.round((used / window) * 100));
  pill.hidden = false;
  // INBOX 77: "text wrong ... the badge shows 'used / window'". A raw
  // percentage answered "how full", which the colour already says at a
  // glance; the two counts answer the question a percentage cannot, how
  // much room is actually left to work with.
  pill.textContent = `${compactTokens(used)} / ${compactTokens(window)}`;
  pill.classList.toggle("is-warn", pct >= 70 && pct < 85);
  pill.classList.toggle("is-danger", pct >= 85);
  const approx = stats.usage_source === "estimated" ? "about " : "";
  pill.title = `The last turn used ${approx}${compactTokens(used)} of the model's ${compactTokens(window)} context window. Open for what fills it.`;
  //: The popover's rows (usage-ledger.js, lazy: the boot gzip ratchet).
  ensureModule("usageLedger").then(() => renderChatContextPop(stats, used, window, pct));
}


//: How long the thread is, beside what it has cost: Compress and Fork both answer "this has got long", which a token count does not say in a unit anyone thinks in.
function renderChatTurnCount() {
  const el = $("chat-turns");
  if (!el) return;
  const turns = (chatConv && chatConv.turns && chatConv.turns.length) || 0;
  el.hidden = turns === 0;
  el.textContent = turns === 1 ? "1 exchange" : `${turns} exchanges`;
}

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
    toast(error?.message || "Couldn't summarise this conversation.");
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

// Three-dot "the model is about to speak" indicator (Wave D).
// "The model is working." Under reduced motion the bouncing dots are frozen by
// the blanket animation rules, three motionless dots say nothing at all, and
// read as a rendering fault rather than as progress. So when motion is off,
// this becomes a word instead of a gesture. Silence is not an acceptable
// substitute for either.
//: **Battery-efficient mode, as the two generative pictures see it**
//: (INBOX 260). The setting pauses the background AI tasks and the graph's
//: similarity work, and for a long time reached nothing in the browser: a
//: person who turned on a setting with "battery" in its name and watched
//: the dashboard's constellation keep drawing would reasonably call that
//: broken, whatever the help text said. So it is a third input to the motion
//: resolution `startArt` (dashboard.js) and `startBgArt` (settings.js)
//: already share with reduced motion and Performance mode, and the help text
//: says so now.
//:
//: Here rather than beside the other two because app.js is the first script
//: the page loads and `prefsCache` is its own; the `typeof` guard is the
//: same one every cross-file reading in this app carries, since a picture
//: can start before the preferences have landed.
function batteryModeOn() {
  return Boolean(prefsCache && prefsCache.battery_efficient_mode);
}

// `label` is the reduced-motion fallback: with animations off the dots can't
// convey "working", so a word has to. Callers that already print their own
// sentence beside the indicator pass theirs in, the weekly digest used to
// append " Thinking about your week…" next to the default, and it rendered as
// "Thinking… Thinking about your week…" (user-reported).
//: **Progress is feedback, not decoration, and it gets its own switch.**
//:
//: Reported three times, the last with a screenshot of a frozen italic
//: "Thinking…": *"the thinking and writing animation is completely broken,
//: doesn't move"*, and then the instruction that settles the design, 
//: *"make them happen even if animations are stalled, or make them paused
//: separately to the rest like the background art."*
//:
//: The background art already has exactly that shape (`bg-motion`: auto /
//: moving / still), so this follows it rather than inventing a second idea.
//: The difference is the **default**: the art defaults to `auto` because it
//: is decoration, and this defaults to `always` because a progress indicator
//: that has stopped is indistinguishable from an app that has hung. Turning
//: off "animations and transitions" is a statement about chrome; it was
//: never a request to be left unable to tell whether the model is working.
//:
//: The OS's own `prefers-reduced-motion` is still honoured under `auto`, and
//: `alive()` below is what stops that meaning *dead*, see its own comment.
function progressMotionWanted() {
  const choice = document.documentElement.dataset.progressMotion || "always";
  if (choice === "still") return false;
  //: **"Always" means always, including through the platform setting**, by
  //: direct instruction: *"make sure the animations run even with prefer
  //: reduced motion on, like the rotating generated logos."* My first pass
  //: exempted the OS setting on accessibility grounds and was overruled, it
  //: is the user's own app, the choice is theirs, and it is one select away
  //: from `auto`, which does respect the platform. The CSS counter-rule in
  //: 02-chat-graph.css carries the same decision for the same reason.
  if (choice === "always") return true;
  return !reducedMotionWanted();
}

// `label` is the reduced-motion fallback: with animations off the dots can't
// convey "working", so a word has to. Callers that already print their own
// sentence beside the indicator pass theirs in, the weekly digest used to
// append " Thinking about your week…" next to the default, and it rendered as
// "Thinking… Thinking about your week…" (user-reported).
//: The writing motif: three nodes and the edge being drawn between them, 
//: the same node-and-edge vocabulary the graph, the concept maps and the app's
//: own mark are built from. Inline SVG with attributes rather than a `style`
//: string, because this app's CSP drops inline styles (CLAUDE.md, "a policy
//: silently refusing the work"); everything that moves is done in CSS.
//: **An interval that belongs to a node, and survives that node being moved.**
//:
//: The pattern this replaces was `if (!node.isConnected) return
//: clearInterval(timer)`, correct about the leak it was guarding (an interval
//: that outlives its element grows with every turn of a long conversation) and
//: wrong about what "gone" means. **A node that is being re-parented is
//: disconnected for an instant**, and this app re-parents the streaming
//: indicator on purpose: `reattachStreamingTurn` appends every node of the
//: live turn back into `#chat-messages` whenever the pane is rebuilt, and
//: `clearPending` moves the pending line to the end of the steps.
//:
//: One tick landing inside one of those windows killed the timer for good.
//: The node came back, the animation did not, and it froze mid-cycle showing
//: its three dots standing still, reported as "the text streaming animation
//: stops moving and just shows as 3 lines", and again as "I scrolled up while
//: still streaming the response and the generating and animation disappeared",
//: which is the same timer dying during the re-render that scrolling caused.
//:
//: So: skip the work while detached, and only give up once the node has stayed
//: gone for `GRACE_TICKS` in a row. A re-parent is one frame; ten ticks is
//: several seconds, which is far longer than any re-render and still bounded,
//: so the leak the original guard was written for cannot come back.
const LIVING_INTERVAL_GRACE_TICKS = 10;

function aiWritingTrace() {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "ai-writing-trace");
  svg.setAttribute("viewBox", "0 0 34 12");
  svg.setAttribute("aria-hidden", "true"); // the container already announces itself
  const line = document.createElementNS(NS, "path");
  line.setAttribute("class", "ai-writing-edge");
  line.setAttribute("d", "M4 8 L17 4 L30 8");
  svg.append(line);
  const nodes = [
    [4, 8],
    [17, 4],
    [30, 8],
  ];
  nodes.forEach(([cx, cy], index) => {
    const dot = document.createElementNS(NS, "circle");
    dot.setAttribute("class", `ai-writing-node ai-writing-node-${index + 1}`);
    dot.setAttribute("cx", cx);
    dot.setAttribute("cy", cy);
    dot.setAttribute("r", "2");
    svg.append(dot);
  });
  return svg;
}

//: **Two phases**: `thinking` keeps the dots, `writing` draws a short run of
//: nodes joined by a line (this app's motif). Both sit stacked in one box and
//: cross-fade, so the swap never shifts layout; the SVG goes after the dot
//: spans because `:nth-child(2)`/`(3)` time the bounce by position.
//: **A mouse wheel must scroll a horizontal strip.** Reported: "if the tabs
//: bar becomes scrollable, I cant do it with mouse, only with touch or my
//: trackpad."
//:
//: That is the browser's behaviour, not a bug in the strip: a wheel emits
//: `deltaY`, and an element that only overflows on X ignores it, so a
//: trackpad (which emits real `deltaX` on a two-finger swipe) and a
//: touchscreen work while a wheel does nothing at all. Every app with a tab
//: strip translates the axis by hand; this is that, once, for all of them.
//:
//: Three conditions before it takes over, so it never steals a gesture that
//: meant something else: the element must actually overflow horizontally, the
//: gesture must be vertical-only (`deltaX === 0`, a trackpad's own horizontal
//: swipe is left alone), and the scroll must have somewhere to go in that
//: direction, so at either end the page scrolls normally instead of the strip
//: swallowing the wheel.
//:
//: `passive: false` because it calls `preventDefault`; that is the whole
//: point, and it is scoped to elements that pass the test above.
function wheelScrollsHorizontally(element) {
  if (!element || element.dataset.wheelX === "1") return;
  element.dataset.wheelX = "1";
  element.addEventListener(
    "wheel",
    (event) => {
      if (event.deltaX !== 0 || event.shiftKey) return;
      // Do not steal vertical scroll if the target is inside a scrollable dropdown/menu
      if (event.target.closest(".select-menu, .action-menu, .doc-dock-menu-list, .library-image-menu-list, .wb-board-menu")) return;
      
      const room = element.scrollWidth - element.clientWidth;
      if (room <= 1) return;
      const atStart = element.scrollLeft <= 0 && event.deltaY < 0;
      const atEnd = element.scrollLeft >= room - 1 && event.deltaY > 0;
      if (atStart || atEnd) return;
      element.scrollLeft += event.deltaY;
      event.preventDefault();
    },
    { passive: false }
  );
}
window.wheelScrollsHorizontally = wheelScrollsHorizontally;

// Trackpads send small deltaX values along with deltaY when scrolling vertically.
// If a dropdown lacks horizontal scroll, browsers often ignore `overscroll-behavior` 
// on that axis and chain the deltaX to the nearest horizontally scrollable ancestor.
// When the ancestor scrolls, `closeActionMenusOnScroll` fires and closes the menu.
// [REMOVED] The manual wheel event handler was removed because `menu.scrollTop += event.deltaY`
// breaks two-finger trackpad scrolling. Instead, `closeActionMenusOnScroll` now checks 
// if the cursor is actively hovering the menu, and if so, it ignores the ancestor scroll event.

//: Every horizontal strip in the app, in one list. A strip added later gets
//: this by being added here, which is cheaper than each surface remembering.
function wireHorizontalWheelScrolling() {
  const strips = [
    "#tab-bar",
    "#notes-subtabs",
    "#library-subtabs",
    ".doc-toolbar",
    ".seg.edge-fade",
    ".edge-fade",
  ];
  for (const selector of strips) {
    for (const element of document.querySelectorAll(selector)) {
      wheelScrollsHorizontally(element);
    }
  }
}
window.wireHorizontalWheelScrolling = wireHorizontalWheelScrolling;

//: **Recursive, not `livingInterval`.** That helper (this file, above) fixes
//: one period for the whole life of the timer; a jittered 3.75-to-5.25s gap
//: needs a new random delay every tick, so this reimplements its one other
//: idea by hand: a node re-parented for a frame (this app re-parents a live
//: turn's own elements on purpose, see `livingInterval`'s comment) is not a
//: node that is gone, so a handful of short rechecks are given before the
//: timer actually stops, rather than the leak the naive
//: `if (!node.isConnected) return` guard used to be.
//: 1.5x the first 2.5-to-3.5s gap: the owner found that pace a little too
//: fast to read a phrase before it changed (2026-09-28).
const THINKING_WORD_MIN_MS = 3750;
const THINKING_WORD_JITTER_MS = 1500;
const THINKING_WORD_RECHECK_MS = 500;
const THINKING_WORD_GRACE_TICKS = 4;

function scheduleThinkingWordTick(dots, wordEl, list, index, missingTicks) {
  dots._thinkingWordTimer = setTimeout(() => {
    //: **Stop on phase "writing"**, checked here rather than only in
    //: `setPhase`, so the one tick already in flight when the phase flips
    //: mid-wait cannot still land a rotation moments after the answer has
    //: started.
    if (dots.dataset.phase === "writing") return;
    if (!dots.isConnected) {
      if (missingTicks + 1 >= THINKING_WORD_GRACE_TICKS) return; // gone for good
      scheduleThinkingWordTick(dots, wordEl, list, index, missingTicks + 1);
      return;
    }
    const next = (index + 1) % list.length;
    //: The exact crossfade `.progress-musing` uses (this file, `progressLine`):
    //: remove the class, force a reflow, add it back, so the transition
    //: restarts on an element already on screen rather than coalescing into
    //: nothing.
    wordEl.classList.remove("is-shown");
    void wordEl.offsetWidth;
    wordEl.textContent = list[next];
    wordEl.classList.add("is-shown");
    scheduleThinkingWordTick(dots, wordEl, list, next, 0);
  }, missingTicks > 0 ? THINKING_WORD_RECHECK_MS : THINKING_WORD_MIN_MS + Math.random() * THINKING_WORD_JITTER_MS);
}

//: Only for the enhanced-motion indicator (dots + the writing trace): under
//: reduced motion `typingDots` never reaches this, and its own single word
//: already satisfies "show one word, no rotation" without help.
function startThinkingWordRotation(dots, persona) {
  const list = thinkingWordsFor(persona);
  const wordEl = document.createElement("span");
  wordEl.className = "typing-thinking-word";
  //: **Not announced per word.** The row's own `aria-label` (set once, by
  //: the caller) is what a screen reader reads, "Thinking"; a value that
  //: changes several times a minute read aloud each time would be noise, not
  //: help, so the word is decorative.
  wordEl.setAttribute("aria-hidden", "true");
  //: No reserved width: sized to the longest phrase it pushed "Thinking" and
  //: the tips far to the right (the owner at release, twice). The word sits
  //: last in its row, so a shorter or longer phrase moves nothing after it.
  wordEl.textContent = list[0];
  dots.appendChild(wordEl);
  //: The first word arrives the same way every later one does (a frame after
  //: attach, so the transition has something to animate from) rather than
  //: starting already shown, which is one fewer rule for this word to answer
  //: to differently from every other rotation it does.
  requestAnimationFrame(() => wordEl.classList.add("is-shown"));
  scheduleThinkingWordTick(dots, wordEl, list, 0, 0);
}

function stopThinkingWordRotation(dots) {
  clearTimeout(dots._thinkingWordTimer);
  dots._thinkingWordTimer = null;
}

//: **One phase vocabulary for every chat surface** (INBOX 649, the owner: the
//: "thinking..." text "should change based on the state like for if it is
//: waiting for the first token, thinking, or writing etc. maybe the wording
//: can be more atlas themed ... just to help with information architecture").
//: Decided, not to be remade: waiting for the first token "Reaching Atlas…",
//: a model loading "Waking the model…", retrieval "Reading your notes…",
//: reasoning tokens "Atlas is thinking…", answer text "Atlas is writing…", a
//: tool call "Atlas is <tool verb>…". With no model connected, "Working it
//: out without a model…" (INBOX 801). A persona's name replaces Atlas. The
//: indicator keeps its own two shapes (dots, or the writing trace under
//: "writing", which CSS keys off `data-phase`); only the words have six
//: states. Every surface
//: drives it through `progressLine(...).setPhase(name, detail)`, and the shared
//: stream client (`streamChat`, capture-ask.js) does so from the events that
//: really arrive, so no surface invents a stage.
const PROGRESS_PHASES = {
  reaching: (who) => `Reaching ${who}…`,
  loading: () => "Waking the model…",
  //: With no model connected (INBOX 801, the owner: "It said waking a model
  //: when no model is connected"): the app's own engine is answering.
  engine: () => "Working it out without a model…",
  reading: () => "Reading your notes…",
  thinking: (who) => `${who} is thinking…`,
  writing: (who) => `${who} is writing…`,
  tool: (who, verb) => `${who} is ${verb || "using a tool"}…`,
};

function progressPhaseText(phase, persona = null, detail = null) {
  if (!PROGRESS_PHASES[phase]) return null;
  return PROGRESS_PHASES[phase](personaDisplayName(persona), detail);
}

//: **A tool's own label, as the verb of the sentence.** The harness labels a
//: call in the past tense once it has run (`ph:books Listed notes`, `Searched
//: notes for “x”`), the only label there is; its first word becomes the
//: present participle ("listing notes", "searching notes for “x”"). Regular
//: past tenses lose their `ed` and gain `ing` (`Saved` to `saving`, `Tagged` to
//: `tagging`), the few irregulars the harness uses are listed, and a label that does not
//: open with a verb ("No path between #1 and #2") gives null, which the phase
//: renders as "using a tool".
const TOOL_VERB_IRREGULAR = { read: "reading", found: "finding", put: "putting", got: "getting", took: "taking", drew: "drawing" };

//: `words`: opt in, not automatic. Most callers (an OCR read, a caption, a
//: generic "Loading…") are not "the AI is thinking about your question",
//: and a persona's voice rotating beside them would be decoration with
//: nothing behind it. `persona`: whoever is answering, resolved once by the
//: caller (the same value the request itself was sent with, `chat-attach.js`'s
//: own `sentPersona`, `palette.js`'s `askedPersona`), never read back off a
//: live picker here.
function typingDots(label = null, { persona = null, words = false } = {}) {
  label = label || progressPhaseText("reaching", persona);
  const dots = document.createElement("span");
  //: `typing-dots` is kept as the class even though this is now two
  //: indicators: existing CSS keys off it, and so does the code that removes
  //: the indicator when the first token lands
  //: (`querySelector(".typing-dots, .typing-label")`). Renaming it would have
  //: been a silent breakage in surfaces this change never meant to touch.
  dots.className = "typing-dots";
  dots.dataset.phase = "thinking";
  dots.setAttribute("role", "status");
  dots.setAttribute("aria-label", label);
  dots.setStatus = (next) => {
    dots.setAttribute("aria-label", next);
  };
  if (progressMotionWanted()) {
    //: `.typing-dot`, not a bare `<span>`: the thinking word appended below
    //: is a *fourth* span in this row, and `.typing-dots span` (01-forms
    //: -settings.css) matched it too, leaking a dot's circle, fill and
    //: bounce onto it (the owner's "a long line... an annoying pulse").
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement("span");
      dot.className = "typing-dot";
      dots.appendChild(dot);
    }
    dots.appendChild(aiWritingTrace());
    //: Idempotent, because the streaming callbacks that drive this fire on
    //: every delta: setting the same phase again must not restart the
    //: cross-fade or the line would stutter on each token.
    dots.setPhase = (phase) => {
      const next = phase === "writing" ? "writing" : "thinking";
      dots.dataset.phaseName = phase;
      if (dots.dataset.phase !== next) {
        dots.dataset.phase = next;
        if (next === "writing") stopThinkingWordRotation(dots);
      }
    };
    if (words && wantsThinkingWords()) {
      startThinkingWordRotation(dots, persona);
    }
    return dots;
  }

  //: **INBOX 36: stepping a dot's colour once a second did not read as
  //: alive.** The previous fix here (a class moving from dot to dot) was
  //: reasoned, not observed, and the owner's desktop shell still showed a
  //: flat row of dots: `.typing-dots-stepped span.is-on` swapped `--border`
  //: for `--accent`, a colour change with no size, position or brightness
  //: cue big enough to notice out of the corner of an eye while reading an
  //: answer. Reported again, unchanged: "the streaming indicator still does
  //: not animate."
  //:
  //: A word that changes is unambiguous in a way three near-identical dots
  //: never were, and a *slow* opacity pulse is movement of the one kind
  //: `prefers-reduced-motion` guidance treats as safe: no translation, no
  //: scaling, nothing that can trigger vestibular symptoms, just a fade
  //: between two brightness levels over several seconds. The word itself
  //: still changes with the phase, the same "value changing is information"
  //: reasoning the old stepped dots were built on, just legible this time.
  dots.classList.add("typing-dots-stepped");
  const word = document.createElement("span");
  word.className = "typing-word";
  //: The caller's own words first (`label` is this branch's whole voice), then
  //: the phase vocabulary's, so a standalone indicator under reduced motion
  //: says "Atlas is writing…" rather than one of two bare words.
  word.textContent = label;
  dots.appendChild(word);
  dots.setPhase = (phase, detail) => {
    const next = phase === "writing" ? "writing" : "thinking";
    dots.dataset.phaseName = phase;
    dots.dataset.phase = next;
    const text = progressPhaseText(phase, persona, detail);
    if (text && word.textContent !== text) word.textContent = text;
  };
  return dots;
}

// **A working signal that says what it is working on.** Under reduced
// motion the dots become one static word, so the label the stream updates
// (what it is doing now, from events that actually happened, never a guessed
// stage) is what keeps a long turn from reading as dead.
//: Lines shown while you wait are fixed facts about this app, not model
//: whimsy: a fixed list cannot hallucinate a privacy claim.
const PROGRESS_MUSINGS = [
  "Everything here runs on your machine, nothing is sent anywhere.",
  "Your notes are plain markdown on disk. You can read them without this app.",
  "Searching uses meaning and keywords together, then merges the two rankings.",
  "A note you never tagged is still findable, the links between notes count too.",
  "Private notes are held back from Atlas, even when it asks for them.",
  "Ask mode reads. Agent mode asks before changing a note.",
  "Long answers are slower on a small model, not stuck.",
  "Every tool call Atlas makes is listed under the answer, with what it touched.",
  "Type [[ in any note to link to another one.",
  "Select text anywhere you can edit and ask Atlas about just that passage.",
];

//: How long to wait before showing one. A turn that finishes in a second
//: should never flash a sentence nobody had time to read.
const MUSING_DELAY_MS = 2500;
//: And how long each stays. Long enough to read twice, short enough that a
//: minute-long wait is not one sentence.
const MUSING_ROTATE_MS = 7000;

// Coalesce scroll-to-end into one write per animation frame. It used to run
// on every streamed token, forcing a synchronous reflow each time, a big
// source of jank on long answers.
let chatScrollQueued = false;
