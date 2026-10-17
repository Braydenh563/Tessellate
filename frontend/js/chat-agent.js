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
  const id = typeof chatConv !== "undefined" && chatConv && chatConv.id;
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

//: Called where a saved conversation finishes drawing: back to the place it
//: was left, or to its end when there is none.
function restoreChatPosition(id) {
  const saved = chatPositions()[id];
  const pane = $("chat-messages");
  if (!saved || !pane) return chatScrollToEnd();
  requestAnimationFrame(() => {
    pane.dataset.stuck = "0";
    pane.scrollTop = Math.min(saved.top, pane.scrollHeight);
    syncChatJumpLatest();
  });
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
  const distance = pane.scrollHeight - pane.scrollTop - pane.clientHeight;
  //: Far from the bottom is "away" only once the reader left (`followBottom`);
  //: growth under a following pane is the pin's to close (INBOX 534).
  const scrolledAway = distance > SCROLL_STICK_SLACK && pane.dataset.stuck === "0";
  if (distance <= SCROLL_STICK_SLACK && !followReleased(pane)) pane.dataset.stuck = "1";
  const overflowing = pane.scrollHeight - pane.clientHeight > SCROLL_STICK_SLACK;
  //: And never on a transcript with no messages: the owner's screenshot of a
  //: new chat had the pill under the welcome, which is "latest" of nothing.
  const hasMessages = Boolean(pane.querySelector(".msg"));
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

function chatScrollToEnd() {
  if (chatScrollQueued) return;
  chatScrollQueued = true;
  requestAnimationFrame(() => {
    chatScrollQueued = false;
    keepAtBottom($("chat-messages"));
    //: Called here as well as on scroll: a turn starting or ending changes
    //: what the pill says, and neither of those is a scroll event.
    syncChatJumpLatest();
  });
}

// The files a message carried, under the message that carried them.
//
// Reported directly: "images and files uploaded into a chat conversation
// arent rendered with the chat messages, the captions arent viewable…and they
// arent previewable or quick navigatable to their stored location in the
// library or documents etc or viewable in a better environment". All of that
// was true: the composer showed a thumbnail chip until you pressed send, and
// then the picture vanished from the conversation entirely, the ids were
// stored (for the model and for media_gc) and nothing ever drew them again.
//
// `attachments` comes hydrated from `GET /conversations/{id}` on reload and is
// built locally on a live send, so both paths render the same thing.
function chatAttachmentStrip(attachments) {
  if (!attachments || !attachments.length) return null;
  const strip = document.createElement("div");
  strip.className = "msg-attachments";
  const images = attachments.filter((a) => a.kind === "image");

  for (const item of attachments) {
    if (item.kind === "image") {
      const figure = document.createElement("figure");
      figure.className = "msg-attachment msg-attachment-image";
      const img = document.createElement("img");
      img.src = mediaSrc(item.url);
      img.alt = item.caption || item.name || "";
      img.loading = "lazy";
      img.title = "Click to view it full size";
      // An upload deleted from the Library long after this message was sent
      // resolves to a row that no longer has a file. Hiding the broken tile
      // is what the gallery does; saying so is better than a grey box.
      img.addEventListener("error", () => {
        figure.classList.add("msg-attachment-missing");
        img.remove();
        const gone = document.createElement("p");
        gone.className = "muted text-sm";
        gone.textContent = `“${item.name}” isn't in your library any more.`;
        figure.prepend(gone);
      });
      img.addEventListener("click", () =>
        openLightbox(
          images.map((i) => ({
            filename: i.name,
            getUrl: () => mediaSrc(i.url),
            caption: i.caption || "",
            text: i.text || "",
          })),
          images.indexOf(item)
        )
      );
      figure.appendChild(img);

      // The caption, which is the half the report names twice. Shown under
      // the thumbnail rather than only in the lightbox: a picture in a
      // conversation is often referred to by what it shows.
      if (item.caption) {
        const caption = document.createElement("figcaption");
        caption.className = "muted text-sm";
        caption.textContent = item.caption;
        figure.appendChild(caption);
      }

      //: **The other half nothing said out loud.** Asked for directly: "in
      //: the chat, when an image and/or document is captioned and ocr is
      //: used it should be tagged under the image in the chat bubble." The
      //: caption was already shown above; `item.text` (the vision-OCR or
      //: Tesseract reading) was resolved by the backend the whole time
      //: (`_hydrate_attachments` in routes_conversations.py) and handed to
      //: the lightbox on click, but nothing in the bubble itself said a
      //: reading existed at all, so the only way to learn one was there was
      //: to open the picture and look.
      //:
      //: A badge, not the text itself: this app has already learned that
      //: lesson once (`ai/embeddings.py`'s `MAX_MEDIA_TEXT_CHARS` note on why
      //: a whole page of transcription does not belong inline in a note), and
      //: a chat bubble is an even worse place for a page of OCR text to land
      //: uninvited. Same "Read · N words" shape the Files sub-tab's reading
      //: list already uses, so the same fact reads the same way everywhere it
      //: appears.
      if (item.text) {
        const words = item.text.trim().split(/\s+/).length;
        const badge = document.createElement("button");
        badge.type = "button";
        badge.className = "chip msg-attachment-read-badge";
        setLabel(badge, `ph:scan Read · ${words.toLocaleString()} words`);
        badge.title = "Text was found in this picture, click it to see the page";
        //: Same lightbox call the thumbnail itself uses, so "click the
        //: picture" and "click the badge that says there is text on it" land
        //: on the same place rather than becoming two different doors.
        badge.addEventListener("click", () =>
          openLightbox(
            images.map((i) => ({
              filename: i.name,
              getUrl: () => mediaSrc(i.url),
              caption: i.caption || "",
              text: i.text || "",
            })),
            images.indexOf(item)
          )
        );
        figure.appendChild(badge);
      }

      const actions = document.createElement("div");
      actions.className = "msg-attachment-actions";
      actions.appendChild(
        smallButton("ph:image Library", `Find “${item.name}” in your library`, () =>
          // One helper, because the media view is two sub-tabs now and a PDF
          // has to land on Files rather than on Images. See
          // `focusLibraryFile` in library.js.
          focusLibraryFile(item.name, item.url || item.name)
        )
      );
      figure.appendChild(actions);
      strip.appendChild(figure);
      continue;
    }

    if (item.kind === "note") {
      // A note: the chip carries its first line and opens it in Notes. Same
      // shape as the document chip below and for the same reason, the note's
      // full text is already one click away and repeating it in the bubble
      // would bury the question that was asked about it.
      const noteChip = document.createElement("button");
      noteChip.type = "button";
      noteChip.className = "chip msg-attachment msg-attachment-note";
      setLabel(noteChip, `ph:paperclip ${item.name}`);
      noteChip.title = `Open this note (#${item.id})`;
      // `flashEntry` is the app's one "take me to this note" path: it also
      // switches sub-tab, clears the filters that would hide the card, and
      // announces the jump. Re-implementing three of those here is how they
      // drift apart.
      noteChip.addEventListener("click", () => flashEntry(item.id));
      strip.appendChild(noteChip);
      continue;
    }

    if (item.kind === "map") {
      // A mind map attached to the question (MINDMAP_PLAN.md §5 item 11).
      // `mapChip` is the app's one map chip, so a map in a sent bubble reads
      // exactly as it does in a note, on the timeline and in a dashboard row
      //, the whole point of §5 item 12. `msg-attachment` on top of it so it
      // sits in the strip like every other kind.
      const board = mapBoardById(item.id) || { id: item.id, title: item.name, type: "map" };
      const chipEl = mapChip(board);
      chipEl.classList.add("msg-attachment");
      strip.appendChild(chipEl);
      continue;
    }

    if (item.kind === "file") {
      // A Library file. Same shape as the document chip below, and the same
      // reason -- its text may be a hundred pages -- but it opens in the
      // Library's Files sub-tab rather than in the Documents editor, because
      // that is where an Attachment row actually lives.
      const fileChip = document.createElement("button");
      fileChip.type = "button";
      fileChip.className = "chip msg-attachment msg-attachment-doc";
      setLabel(fileChip, `ph:paperclip ${item.name}`);
      fileChip.title = `Find “${item.name}” in your library`;
      fileChip.addEventListener("click", () => focusLibraryFile(item.name, `/files/${item.id}`));
      strip.appendChild(fileChip);
      continue;
    }

    // A document: there is nothing to preview inline (its text may be a
    // hundred pages), so the chip is the navigation.
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip msg-attachment msg-attachment-doc";
    setLabel(chip, `ph:file-text ${item.name}`);
    chip.title = `Open “${item.name}” in Documents`;
    chip.addEventListener("click", () => {
      switchTab("documents");
      openDocument(item.id);
    });
    strip.appendChild(chip);
  }
  return strip;
}

//: The seed for the person's own mark: their profile name, or "You".
function userMarkSeed() {
  return ((prefsCache && prefsCache.display_name) || "").trim() || "You";
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
  for (const holder of document.querySelectorAll("[data-user-mark]")) {
    holder.replaceChildren(nameMark(seed, Number(holder.dataset.userMark) || 18));
  }
  const head = $("profile-head-name");
  if (head) head.textContent = ((prefsCache && prefsCache.display_name) || "").trim() || "Your profile";
  //: The companion, when it is you (INBOX 426 d, the owner: "I changed my
  //: name but the companion which was me didnt update"): it redraws when
  //: the name it is drawn from has changed, and does nothing otherwise.
  if (typeof syncNameMarkBuddy === "function") syncNameMarkBuddy();
}

function userMarkEl() {
  const mark = document.createElement("span");
  mark.className = "msg-user-mark";
  mark.setAttribute("aria-hidden", "true");
  mark.dataset.userMark = "18";
  mark.appendChild(nameMark(userMarkSeed(), 18));
  return mark;
}

function addBubble(role, text, attachments = null) {
  clearChatEmptyState();
  lazyScript("/js/chat-time.js"); // each message's time; the file stamps bubbles as they appear
  const bubble = document.createElement("div");
  bubble.className = `msg ${role}`;
  //: The words as sent, so ArrowUp in an empty composer can reopen the last
  //: question for editing without reading them back out of the rendered DOM.
  if (role === "user" && typeof text === "string") bubble.dataset.sent = text;

  const label = document.createElement("div");
  label.className = "msg-role";
  // **The user's turn is named for a screen reader only.** The owner once
  // asked for a user avatar in the label row, then later had the row hidden
  // (08-consistency.css: on your own side of your own conversation "You"
  // said nothing the alignment did not), so the label is read, not seen.
  if (role === "user") {
    const name = document.createElement("span");
    name.textContent = "You";
    label.append(name);
  } else {
    label.textContent = assistantLabel();
  }
  const body = document.createElement("div");
  body.className = "msg-body";
  body.textContent = text;
  bubble.append(label, body);
  //: **The person's own mark** (INBOX 409: "auto generate other icons in
  //: other places like potentially the user chat bubbles"). Generated from
  //: the profile name the way a persona's is, so it is theirs and the same
  //: every time; "You" when no name is set. It sits on the bubble's top
  //: right corner, positioned rather than in the flow, so the bubble's size,
  //: padding and text are exactly what they were (chatmarks.js measures
  //: that): the label row that used to hold an avatar is hidden on purpose.
  if (role === "user") bubble.appendChild(userMarkEl());
  const strip = chatAttachmentStrip(attachments);
  if (strip) bubble.appendChild(strip);

  if (role === "user") {
    bubble.appendChild(
      chatMessageActions([
        { label: "ph:copy", title: "Copy", onClick: (e) => copyToClipboard(text, e.currentTarget) },
        { label: "ph:pencil-simple", title: "Edit this question", onClick: () => lazyScript("/js/chat-edit.js").then(() => editAndResend(bubble, text)) },
        { label: "ph:trash", title: "Delete this message", onClick: () => removeChatBubble(bubble) },
      ])
    );
  }
  $("chat-messages").appendChild(bubble);
  chatScrollToEnd();
  return bubble;
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

// --- the agent's run, as an ordered timeline --------------------------------------
// A turn used to render into three fixed slots, thinking, then every tool chip,
// then the answer: regardless of when those things actually happened. For a
// multi-step agent run that destroys the one thing worth seeing: the order. A
// model that thought, searched, thought again and then answered looked
// identical to one that answered immediately.
//
// So steps are appended as the events arrive. Consecutive deltas of the same
// kind extend the current step; a different kind starts a new one, which is
// what produces the thinking → tool → tool → answer chain the user follows.
//: `options.afterAnswerPaint` runs after every live paint of a prose step: a
//: paint rebuilds the step from raw markdown, so the citation numbers placed
//: while the answer streams (`grounding_live`, INBOX 320) have to be written
//: again each time, as the Ask tab's own renderer does.
function agentTimeline(holder, options = {}) {
  let current = null; // the step still being written into
  const answerSteps = []; // every prose step, in order
  const thinkingSteps = [];
  const record = []; // a serialisable copy, for persistence

  //: **The step group** ("Finished 5 steps", asked for as Perplexity's):
  //: tool calls behind one line, open while running, closed once the answer
  //: starts. A new group after each answer, so order stays true.
  let group = null;

  const groupSummary = (entry) => {
    const n = entry.count;
    const word = n === 1 ? "step" : "steps";
    setLabel(
      entry.summary,
      entry.done ? `ph:check-circle Finished ${n} ${word}` : `ph:spin Working: ${n} ${word}`,
    );
  };

  const ensureGroup = () => {
    if (group) return group;
    const el = document.createElement("details");
    el.className = "agent-step agent-step-group";
    el.open = true;
    const summary = document.createElement("summary");
    summary.className = "agent-step-group-summary";
    const body = document.createElement("div");
    body.className = "agent-step-group-body";
    el.append(summary, body);
    holder.appendChild(el);
    group = { el, summary, body, count: 0, done: false };
    groupSummary(group);
    return group;
  };

  //: Closed and relabelled, not removed. The steps stay reachable, that is
  //: the difference between a summary and a spinner that ate the evidence.
  const closeGroup = () => {
    if (!group) return;
    group.done = true;
    groupSummary(group);
    group.el.open = false;
    group = null;
  };

  const foldEarlierThinking = () => {
    // Reasoning that has produced output is finished, collapse it so the
    // answer isn't buried under it, but leave it there to reopen.
    for (const step of thinkingSteps) step.el.open = false;
  };

  const startThinking = () => {
    const el = thinkingFold();
    const body = el.querySelector(".thinking");
    holder.appendChild(el);
    current = { kind: "thinking", el, body, raw: "" };
    thinkingSteps.push(current);
    return current;
  };

  const startAnswer = () => {
    //: **Only the step being written wears the caret.** Reported with a
    //: screenshot of an agent run: "the blinking cursor bubbles at the end of
    //: the text stayed at the end of each paragraph and didnt disappear" --
    //: every finished answer step in the run still carried one, so a five-step
    //: run showed five carets and only the last of them meant anything.
    //:
    //: `finalise()` cleared them, but only once the whole run ended. A step is
    //: finished the moment the next one starts, which is here.
    for (const step of answerSteps) step.el.classList.remove("is-streaming", "is-generating");
    foldEarlierThinking();
    //: The steps that led here fold up as the prose begins, which is exactly
    //: what Perplexity does and why its answers read as answers rather than
    //: as logs. Anything the model does *after* this opens a fresh group.
    closeGroup();
    const el = document.createElement("div");
    // **`is-streaming` is the only thing on screen that says the answer is
    // still arriving.** Reported directly: "there are no animations for chat
    // generation." The typing dots that run before the first token are
    // removed the moment one arrives (`clearPending`), and from then until
    // the turn ends the text simply grows, no caret, no cursor, nothing.
    // Every chat interface has this affordance because without it a slow
    // local model producing a token a second is indistinguishable from a
    // finished short answer.
    //
    // A class plus a CSS `::after`, not an appended element: the answer body
    // is re-rendered from scratch on every frame by `liveMarkdownRenderer`,
    // so a real node would be destroyed and recreated ~30 times a second (and
    // would land inside whatever block the markdown happened to end with).
    // A pseudo-element is untouched by that and is removed by `finalise`.
    //: **No `is-generating` on the answer itself.** Reported: "the text is
    //: right up against the overly animated borders as well", with a
    //: screenshot of an answer inside a pulsing ring *inside* a bubble
    //: already wearing one. Two rings around one sentence is one too many,
    //: and the inner one is the redundant one: the bubble's rail says the
    //: turn is working and the caret says this answer is still arriving.
    //: `is-streaming` stays, because that is the caret.
    el.className = "agent-step step-answer bubble-answer is-streaming";
    holder.appendChild(el);
    current = {
      kind: "answer",
      el,
      body: el,
      raw: "",
      render: liveMarkdownRenderer(el, options.afterAnswerPaint || null),
    };
    answerSteps.push(current);
    return current;
  };

  // The plan a skill declared, drawn before anything runs. The timeline has
  // always shown what happened; a skill is the first thing that knows what is
  // *meant* to happen, so it says so up front (roadmap §18).
  const plans = [];
  const startPlan = (plan) => {
    const el = document.createElement("details");
    el.className = "agent-step step-plan";
    el.open = true;
    const summary = document.createElement("summary");
    // A saved skill and a plan the model drew for this one request run through
    // the same code, so the card has to say which it is, "Skill Weekly review" is
    // a job the user set up, "Plan fix my categories" is one the model worked out
    // just now, and confusing the two makes the skill list look like it has
    // entries nobody added.
    //: A turn's own card (`kind: "turn"`, agent.py `_TurnCard`) is a third shape.
    const icon = { plan: "ph:compass", turn: "ph:list-checks" }[plan.kind] || "ph:lightning";
    setLabel(summary, `${icon} ${plan.skill}`);
    el.appendChild(summary);
    const items = [];
    if ((plan.steps && plan.steps.length) || plan.kind === "turn") {
      const list = document.createElement("ol");
      list.className = "plan-steps";
      plan.steps.forEach((step, index) => {
        const item = document.createElement("li");
        item.textContent = step;
        if (plan.writes) item.appendChild(planStepWrites(plan.writes[index]));
        list.appendChild(item);
        items.push(item);
      });
      el.appendChild(list);
    }
    if (plan.tools && plan.tools.length) {
      const line = document.createElement("div");
      line.className = "plan-tools";
      line.textContent = `Tools for this run: ${plan.tools.join(", ")}`;
      el.appendChild(line);
    }
    holder.appendChild(el);
    const entry = { el, items, plan: { ...plan, states: plan.states || {} } };
    plans.push(entry);
    // Replaying a finished run: paint the states it ended with.
    for (const [index, state] of Object.entries(entry.plan.states)) {
      markStep(entry, Number(index), state.state, state.reason, state);
    }
    current = null;
    return el;
  };

  // A step's state, shown on the plan itself. The timeline records what
  // happened; this is the only place that says how far through it got.
  const markStep = (entry, index, state, reason, event = {}) => {
    let item = entry.items[index];
    //: A turn's card grows a row per round; a skill's steps are fixed.
    if (!item && entry.plan.kind === "turn" && event.text) {
      item = document.createElement("li");
      entry.el.querySelector(".plan-steps")?.appendChild(item);
      entry.items[index] = item;
      entry.plan.steps = [...(entry.plan.steps || []), event.text];
    }
    if (!item) return;
    //: `attempt`/`of` ride along with the state so a replayed run shows the
    //: same "attempt 2 of 3" a live one did. They are only present on a
    //: `retrying` event, and an older saved run has neither, which
    //: `stepStateWords` renders as attempt 1 of 1 rather than as a crash.
    entry.plan.states[index] = {
      state,
      reason,
      attempt: event.attempt,
      of: event.of,
      //: The rewritten step travels with the state so a replayed run shows the
      //: instruction that actually ran, not the one that failed.
      text: state === "replanned" ? event.text : entry.plan.states[index]?.text,
    };
    item.className = `plan-step plan-step-${state}`;
    item.dataset.state = state;
    const note = item.querySelector(".plan-step-reason");
    if (note) note.remove();
    //: **A re-planned step is a different step, so the checklist says so.**
    //: The runner rewrites a step it could not finish and runs it again at
    //: the same index; leaving the old wording on screen would make the next
    //: `running` look like a repeat of a step that had already failed, with
    //: no sign that anything changed. `textContent`, never markup: this is
    //: model-written text.
    if ((state === "replanned" || entry.plan.kind === "turn") && event.text) {
      item.textContent = event.text;
      entry.plan.steps = entry.plan.steps.map((old, i) => (i === index ? event.text : old));
    }
    //: **`retrying` says why, in the same words the activity panel uses.**
    //: Phase A's runner re-prompts a step whose contract was not met and emits
    //: this state for each attempt; without the sentence, a step being
    //: re-prompted for the third time is indistinguishable on screen from one
    //: quietly running, which is the "it ran no tools and moved on" report all
    //: over again one layer up. `stalled` gets it for the same reason: it is
    //: the state that *ends* a run, and "why did this stall?" should not need
    //: a second click.
    //: **A finished step with a caveat says it on the row.** `done` carries a
    //: reason in two cases and neither was drawn: a step that ran out of
    //: pages with notes left unread, and one whose change turned out not to
    //: be needed (`no_change`). Both are the same class of thing the states
    //: below already explain: a green tick that means less than it looks
    //: like. The owner's report is the reason this matters, a step that says
    //: "I unlinked the ones that did not hold up" over an untouched notebook
    //: reads exactly like one that did the work.
    if (
      (state === "failed" ||
        state === "stalled" ||
        state === "retrying" ||
        state === "replanned" ||
        state === "done" ||
        state === "paging") &&
      (reason || state === "retrying" || state === "replanned" || state === "paging")
    ) {
      const why = document.createElement("span");
      why.className = "plan-step-reason";
      why.textContent =
        state === "retrying" || state === "replanned" || state === "paging"
          ? `, ${stepStateWords(state, { ...event, reason })}`
          : `, ${reason}`;
      item.appendChild(why);
    }
    //: Each step's diff after (row 3): what it wrote, each with its Undo.
    if (state === "done" && event.changes?.length) {
      const box = document.createElement("div");
      box.className = "plan-step-changes";
      for (const change of event.changes) box.appendChild(changeRow(change));
      item.appendChild(box);
    }
  };

  return {
    holder,
    //: What a step currently says, for Phase D's "edit a step's text and
    //: re-run just that step": the re-planned wording when the runner rewrote
    //: it, the original otherwise, so the box opens on the instruction that
    //: actually ran rather than on the one in the catalogue.
    stepText(index) {
      const entry = plans.at(-1);
      if (!entry) return "";
      return entry.plan.states?.[index]?.text || entry.plan.steps?.[index] || "";
    },
    plan(event) {
      startPlan(event);
    },
    step(event) {
      const entry = plans.at(-1);
      if (entry) markStep(entry, event.index, event.state, event.reason, event);
      // Each step's prose is its own block. Without this, step 2's first
      // sentence lands on the end of step 1's paragraph ("…with no tags.Read
      // them.") because nothing between them closed the step.
      current = null;
    },
    failRunningStep(reason) {
      const entry = plans.at(-1);
      if (!entry) return;
      for (const [index, state] of Object.entries(entry.plan.states)) {
        if (state.state === "running") markStep(entry, Number(index), "failed", reason);
      }
    },
    // What the run actually changed, with the call that puts each one back.
    // Prose claiming something happened is exactly what this replaces.
    result(event, options = {}) {
      const changes = event.changes || [];
      //: **The verification is shown even when nothing changed**, which is
      //: most of the time: half the shipped skills are reports, and "this run
      //: changed nothing" is exactly the claim their verify block checks
      //: (Brief 13). A read-only run used to render nothing at all here, so
      //: the only evidence it had done its job was its own prose.
      const check = event.verification || null;
      if (!changes.length && !check) return;
      const box = document.createElement("div");
      box.className = "skill-result";
      box.dataset.changes = JSON.stringify(changes);
      if (check) box.dataset.verification = JSON.stringify(check);
      const span = event.undo_span || null;
      if (span) box.dataset.undoSpan = JSON.stringify(span);
      if (changes.length) {
        const title = document.createElement("div");
        title.className = "skill-result-title";
        title.textContent = `What changed (${changes.length})`;
        //: **The run's own Undo** (AGENT_SKILLS_REFORM): everything the run
        //: wrote, as one plan to confirm (`undoSkillRun`, note-history.js).
        //: One change has its row's own Undo, so it is offered from two.
        if (span && changes.length > 1) {
          //: The run's Undo puts everything back at once, so the per-write
          //: entries on the app's stack and the rows' own Undo buttons come
          //: off too: left, a later Ctrl+Z (or a row's Undo) would run an
          //: inverse that is already applied (Brief 101b).
          const settleRun = () => {
            for (const change of changes) {
              const action = change.undo ? agentUndoActions.get(JSON.stringify(change.undo)) : null;
              if (action && undoStack.includes(action)) settleUndoFromToast(action);
            }
            for (const row of box.querySelectorAll(".skill-change")) {
              row.classList.add("skill-change-undone");
              row.querySelectorAll("[data-change-undo]").forEach((button) => button.remove());
            }
          };
          const all = smallButton("ph:arrow-counter-clockwise Undo the run", "Put back every note this run changed", () => undoSkillRun(span, all, settleRun));
          title.append(" ", all);
        }
        box.appendChild(title);
        for (const change of changes) box.appendChild(changeRow(change, options));
      }
      if (check) box.appendChild(verificationRow(check));
      holder.appendChild(box);
      current = null;
    },
    thinking(delta) {
      const step = current?.kind === "thinking" ? current : startThinking();
      step.raw += delta;
      // The pane has its own max-height and scrollbar; `thinkingPaint` keeps
      // the newest line in view after each paint.
      thinkingPaint(step.el, step.raw);
    },
    answer(delta) {
      const step = current?.kind === "answer" ? current : startAnswer();
      step.raw += delta;
      step.render(step.raw);
    },
    // A tool call is a row inside the current step group, see `ensureGroup`.
    tool(node) {
      foldEarlierThinking();
      const entry = ensureGroup();
      entry.body.appendChild(node);
      entry.count += 1;
      groupSummary(entry);
      current = null; // whatever comes next begins a fresh step
    },
    //: The turn is over: whatever group is still open stops saying "Working".
    //: Called from the stream's `finally`, so it runs on an error and an
    //: abort too: a group left mid-sentence is how a stopped turn ends up
    //: looking like a running one forever.
    finish() {
      closeGroup();
      //: Any trailing progress line still in this holder goes with it. The
      //: turn's own `pending` node is removed by the stream, but a skill run
      //: replayed into a rebuilt bubble can leave one behind, and a "Writing
      //: the answer…" under a finished answer is the exact thing reported.
      for (const stale of holder.querySelectorAll(".step-pending")) stale.remove();
    },
    // Replay a saved run (reopening a conversation).
    replay(steps) {
      for (const step of steps || []) {
        //: `serialise` spreads the plan over `kind`, so a skill's card saves
        //: as "skill" and a turn's as "turn"; both were dropped on reopen.
        if (["plan", "skill", "turn"].includes(step.kind) && Array.isArray(step.steps)) {
          startPlan(step);
          if (plans.at(-1)) plans.at(-1).el.open = false;
        } else if (step.kind === "result") {
          this.result(step);
        } else if (step.kind === "thinking" && step.text) {
          this.thinking(step.text);
          if (current) current.el.open = false;
          current = null;
        } else if (step.kind === "answer" && step.text) {
          const node = startAnswer();
          node.raw = step.text;
          renderMarkdown(node.body, step.text);
          //: A replayed answer has already finished. `startAnswer` builds the
          //: node in its live, mid-stream state, so without this a reloaded
          //: conversation blinks a caret at the end of every answer in it, 
          //: and, now that the two travel together, pulses the generating ring
          //: around all of them forever.
          node.el.classList.remove("is-streaming", "is-generating");
          current = null;
        } else if (step.kind === "tool") {
          //: `step` is passed through, so a replayed tool row keeps the
          //: arguments/result disclosure the live one had. Without it a
          //: reloaded conversation silently lost what each call actually did
          //:, the same turn showed less of itself the second time you looked
          //: at it, which is the shape behind "tools render fine in the chat
          //: initially but then I come back to them after reloading".
          this.tool(toolChip(step.label, step.ok !== false, step));
        }
      }
    },
    noteStep(entry) {
      record.push(entry);
    },
    // Everything the model actually said, for copying, reading aloud and the
    // history sent with the next question.
    text() {
      return answerSteps.map((s) => s.raw).join("\n\n").trim();
    },
    thinkingText() {
      return thinkingSteps.map((s) => s.raw).join("\n\n").trim();
    },
    // Re-render each prose step properly once streaming has finished.
    finalise() {
      //: The live renderer's armed paint is cancelled first: see its own
      //: `stop`. Anything the caller adds to this prose afterwards (the
      //: citation markers) would otherwise be wiped by a timer that was
      //: scheduled before the turn ended.
      for (const step of answerSteps) step.render?.stop?.();
      for (const step of answerSteps) renderMarkdown(step.body, step.raw);
      // The caret goes out with the stream that justified it. Called from
      // every exit path this timeline has, a finished turn, an error, and
      // Stop: because a caret left blinking on an answer that stopped
      // arriving is a worse lie than never having shown one.
      for (const step of answerSteps) step.el.classList.remove("is-streaming", "is-generating");
      foldEarlierThinking();
    },
    // The box to put a message into when the model produced nothing at all.
    ensureAnswerBox() {
      const step = answerSteps.at(-1) || startAnswer();
      //: **Whatever goes in here is already finished.**
      //:
      //: Reported: *"the blinker animation still shows at the end of finished
      //: responses"*, with a screenshot of the caret blinking after "The
      //: model finished without writing anything." That message is written by
      //: the app, after `finalise()` has already run, and `startAnswer` builds
      //: its node in the live, mid-stream state: a caret on a sentence that
      //: was never streaming and no later pass to take it down.
      step.el.classList.remove("is-streaming", "is-generating");
      return step.body;
    },
    // Editing an answer replaces the model's prose with the user's own, so the
    // separate prose steps collapse into the one block they typed. The
    // reasoning and tool steps around them are left alone, those record what
    // actually happened and aren't the user's to rewrite.
    replaceAnswer(markdown) {
      // Same race as `finalise`: an armed paint would put the model's prose
      // back over the text the user just typed.
      for (const step of answerSteps) step.render?.stop?.();
      for (const step of answerSteps.slice(1)) step.el.remove();
      answerSteps.length = Math.min(answerSteps.length, 1);
      const step = answerSteps[0] || startAnswer();
      step.raw = markdown;
      renderMarkdown(step.body, markdown);
      current = null;
      return step.body;
    },
    // The element answer-editing hides while its textarea is open.
    answerElement() {
      return (answerSteps.at(-1) || startAnswer()).el;
    },
    hasAnswer() {
      return answerSteps.some((s) => s.raw.trim());
    },
    // The timeline in the order it happened, for saving with the turn.
    serialise() {
      const out = [];
      //: **Groups are walked into, not over.** Tool rows used to be direct
      //: children of the holder; they are inside a `<details>` now, and a
      //: loop over `holder.children` alone would have silently stopped
      //: saving every tool call, the exact shape of the `.tool-chip-wrap`
      //: regression this function's own comment below already records.
      const walk = (parent) => {
      for (const node of parent.children) {
        if (node.classList.contains("agent-step-group")) {
          walk(node.querySelector(".agent-step-group-body") || node);
          continue;
        }
        if (node.classList.contains("step-plan")) {
          const entry = plans.find((p) => p.el === node);
          // The states go with it, so reopening a chat shows how far the run
          // got rather than an untouched plan.
          if (entry) out.push({ kind: "plan", ...entry.plan });
        } else if (node.classList.contains("skill-result")) {
          out.push({
            kind: "result",
            changes: JSON.parse(node.dataset.changes || "[]"),
            verification: JSON.parse(node.dataset.verification || "null"),
            undo_span: JSON.parse(node.dataset.undoSpan || "null"),
          });
        } else if (node.classList.contains("thinking-fold")) {
          const step = thinkingSteps.find((s) => s.el === node);
          if (step?.raw) out.push({ kind: "thinking", text: step.raw });
        } else if (node.classList.contains("step-answer")) {
          const step = answerSteps.find((s) => s.el === node);
          if (step?.raw) out.push({ kind: "answer", text: step.raw });
        } else if (node.toolStep) {
          //: **Anything that carried its own saved form is saved**, whatever
          //: it is drawn as. The class checks below only know the shapes that
          //: existed when they were written, and a card added later, a
          //: confirmation, a proposal, a question, was silently dropped from
          //: the saved turn, which is one half of "a lot of the steps and
          //: agent process disappears when I come back to it".
          out.push(node.toolStep);
        } else if (node.classList.contains("tool-chip") || node.classList.contains("tool-chip-wrap")) {
          //: `.tool-chip-wrap` has to be matched as well as `.tool-chip`:
          //: `classList.contains` is an exact token match, so once a row that
          //: touched something got wrapped with its chips, this branch stopped
          //: seeing it at all and the call vanished from the reopened chat.
          out.push(
            node.toolStep || {
              kind: "tool",
              label: node.textContent,
              ok: !node.classList.contains("tool-chip-error"),
            },
          );
        }
      }
      };
      walk(holder);
      return out;
    },
  };
}

//: What a saved turn records as its writer: the persona's name, or null for
//: the app's own voice. Null rather than "Atlas" so a reply keeps the emblem
//: after the AI is renamed, and so a turn saved before personas were
//: recorded (no key at all) and one written by the default read the same.
function savedPersona(name) {
  return personaDisplayName(name) === aiNameNow() ? null : name;
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

function paintPersonaAvatar(holder, persona, size = 20) {
  const name = personaDisplayName(persona);
  //: The app's own voice wears whatever Appearance, Assistant avatar says
  //: (`assistantAvatar`); any other persona keeps the face drawn from its name.
  if (chatHeadIsAtlas(name)) {
    paintAssistantAvatar(holder, size);
    return;
  }
  const key = chatHeadKey(name, size);
  const source = chatHeadSources.get(key);
  if (source) {
    holder.replaceChildren(source.cloneNode(true));
    return;
  }
  //: Nothing to draw a face with yet (the faces script failing to load):
  //: the persona's own fallback, never an empty box.
  if (typeof nameMark !== "function") {
    fillPersonaMark(holder, name, size);
    return;
  }
  const face = nameMark(name, size);
  chatHeadSources.set(key, face);
  holder.replaceChildren(face.cloneNode(true));
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
//: 20 nodes a head. No Atlas to draw (the faces script failing to
//: load): the emblem, never an empty box.
function assistantAvatar(size = 20) {
  const emblem = typeof atlasAvatar !== "function" || (typeof appearancePref === "function" && appearancePref("assistant-avatar", "atlas") === "emblem");
  if (emblem) {
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
  holder.replaceChildren(assistantAvatar(size));
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

// An assistant bubble: an avatar, the step timeline, and a matching-records slot.
//
// **`persona` is whoever wrote this reply**, never read off the live picker
// (the owner: "if different personas are used in different chats for the
// chat messages the avatars need to persist for what persona was used").
// The live path passes the persona it sent; a reopened chat passes the one
// saved on the turn, where null (an older turn, or the default) is the app's
// own voice. Switching persona later repaints nothing already on the page.
function addAssistantBubble(persona = null) {
  clearChatEmptyState();
  const bubble = document.createElement("div");
  bubble.className = "msg assistant";
  const writer = personaDisplayName(persona);
  //: Read back by the transcript copy, so each reply is named by its writer.
  bubble.dataset.persona = writer;

  const label = document.createElement("div");
  label.className = "msg-role msg-role-assistant";
  const avatar = document.createElement("span");
  avatar.className = "msg-avatar";
  avatar.setAttribute("aria-hidden", "true");
  const name = document.createElement("span");
  name.textContent = writer;
  label.append(avatar, name);
  bubble.appendChild(label);
  // NB: the emblem is drawn after the bubble is in the DOM, p5 can't size a
  // canvas inside a detached element, which left the avatar blank until some
  // later render happened to redraw it.

  // Every step, reasoning, tool calls, prose, lands here in event order.
  const stepsHolder = document.createElement("div");
  stepsHolder.className = "agent-steps";

  const recordsHolder = document.createElement("div");
  // Same "grounded in" chip strip the Ask tab shows (renderAnswerGrounding): 
  // that function only ever wrote to the Ask tab's single fixed element, so a
  // Chat-tab notes question got the "grounding" SSE event from the backend
  // (it's emitted for any non-conversational /chat/stream call, not just the
  // Ask box) but nothing ever rendered it. One holder per bubble, since Chat
  // has many turns where Ask has one answer.
  const groundingHolder = document.createElement("div");
  groundingHolder.className = "answer-grounding hidden";

  bubble.append(stepsHolder, recordsHolder, groundingHolder);
  $("chat-messages").appendChild(bubble);
  paintPersonaAvatar(avatar, writer, 20); // now attached, so p5 can measure and draw
  chatScrollToEnd();
  //: Late-bound: the stream that owns this bubble sets `afterAnswerPaint`
  //: once it has the turn's grounding rows to place (`sendChatMessage`).
  const paintHooks = { afterAnswerPaint: null };
  const timeline = agentTimeline(stepsHolder, { afterAnswerPaint: () => paintHooks.afterAnswerPaint?.() });
  return { bubble, stepsHolder, recordsHolder, groundingHolder, timeline, paintHooks };
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
          }),
        });
        if (result && result.error) throw new Error(result.error);
        const action = agentUndoActions.get(JSON.stringify(change.undo));
        if (action) settleUndoFromToast(action);
        row.classList.add("skill-change-undone");
        setLabel(label, `${change.label || change.tool}, undone`);
        undo.remove();
        loadEntries();
      } catch (error) {
        undo.disabled = false;
        toast(error.message || "Couldn't undo that.", true);
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
  if (diff.more) viewer.append(`${diff.more} more lines changed`);
  return viewer;
}

//: The writes a plan's step will make, said before it runs (row 3, the
//: server's `plan_writes`): the exact act, the tool it names, or that it reads.
function planStepWrites(writes) {
  //: A div, not a styled span: the boot stylesheet is at its byte cap.
  const line = document.createElement("div");
  line.className = "plan-step-writes muted";
  line.textContent = writes?.length ? `Writes: ${writes.join("; ")}` : "Reads only";
  return line;
}

//: **A run's write goes on the app-wide undo stack** (row 4, WORLD_CLASS
//: decision 53): Ctrl+Z after a run takes back its last write, and a run
//: stopped at step 2 leaves step 1's writes there. Redo runs the call again
//: and keeps the inverse of that run. The run's own Undo stays for the whole.
//: The stack entry for each change's undo, so a row's own Undo (the step's
//: list, the run's change list: copies of the change, not the same object)
//: takes it off the stack and Ctrl+Z cannot run it twice.
const agentUndoActions = new Map();
function pushAgentChangeUndo(change, call) {
  if (!change?.undo) return;
  let inverse = change.undo;
  const exec = (body) => apiJson("/chat/tools/execute", { method: "POST", body: JSON.stringify(body) });
  const key = JSON.stringify(change.undo);
  agentUndoActions.set(key, pushUndo(
    (change.label || change.tool).replace(/^ph:[\w-]+\s*/, ""),
    () => exec({ name: inverse.tool, arguments: inverse.arguments, steps: inverse.steps }).then(refreshAfterToolChanges),
    async () => {
      const again = await exec({ name: call.name, arguments: call.arguments });
      inverse = again.undo || inverse;
      refreshAfterToolChanges();
    }
  ));
}

//: **The plan, approved once** (row 3, the Copilot agent panel's shape): the
//: steps and what each will write, then Run the plan or Not now. Nothing runs
//: until it is pressed; a destructive step still asks on its own card.
function planProposalCard(holder, event, run) {
  const card = document.createElement("div");
  card.className = "tool-confirm plan-proposal";
  const head = document.createElement("p");
  setLabel(head, `ph:compass ${event.goal}`);
  const list = document.createElement("ol");
  list.className = "plan-steps";
  event.steps.forEach((step, index) => {
    const item = document.createElement("li");
    item.textContent = step;
    item.appendChild(planStepWrites(event.writes?.[index]));
    list.appendChild(item);
  });
  const row = document.createElement("div");
  row.className = "row";
  row.append(
    smallButton("Run the plan", "Run every step; each one's writes are listed above and can be undone", () => {
      card.replaceWith(toolChip(`ph:play Running ${event.steps.length} steps`));
      run();
    }, false),
    smallButton("Not now", "Run nothing", () => card.replaceWith(toolChip("ph:x Not run: nothing was changed.")))
  );
  card.append(head, list, row);
  holder.appendChild(card);
  return card;
}

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

//: **What the tool touched, shown rather than named.** Asked for: "the chat
//: and agent should be the ultimate notebook handler, drafting and previewing
//: notes … showing rendered note previews then user can edit".
//:
//: A chip alone could only take you away from the conversation: press it and
//: you are in the Notes tab, having lost the answer you were reading. So the
//: chip *opens the thing in place*, rendered with the app's own markdown
//: renderer, with Open and Edit under it, and pressing it again closes it.
//: Leaving is now a decision rather than the only option.
//:
//: Fetched on demand, never carried in the tool event: a replayed transcript
//: (a conversation reopened days later) then previews the note as it is now,
//: not as it was, and a turn that touched six notes does not put six note
//: bodies into the message that stores it.
async function toolPreviewBody(item, holder) {
  setLabel(holder, "ph:spin Loading…");
  try {
    if (item.kind === "document") {
      const doc = await apiJson(`/documents/${item.id}`);
      holder.replaceChildren();
      const title = document.createElement("strong");
      title.textContent = doc.title || `Document #${item.id}`;
      const body = document.createElement("div");
      body.className = "tool-preview-body";
      renderMarkdown(body, doc.content || "");
      holder.append(title, body);
    } else {
      const entry = await apiJson(`/entries/${item.id}`);
      holder.replaceChildren();
      const body = document.createElement("div");
      body.className = "tool-preview-body";
      renderMarkdown(body, entry.content || "");
      holder.appendChild(body);
    }
  } catch (error) {
    holder.replaceChildren();
    const failed = document.createElement("p");
    failed.className = "muted";
    //: The real reason, not a euphemism: a deleted note and an unreachable
    //: backend are different problems and only one of them is worth retrying.
    failed.textContent = error?.message || "That note could not be loaded.";
    holder.appendChild(failed);
  }
}

//: One card. `spec` is the `CARD_KINDS` entry for its kind, so the actions
//: under it are that kind's own: Open plus Edit for a note, Open plus View
//: for an image, Open plus Mark done for a reminder. Open is the one every
//: kind has, which is why it is built here rather than in each entry.
function toolPreviewPanel(item, spec) {
  const panel = document.createElement("div");
  panel.className = "tool-preview";
  const holder = document.createElement("div");
  holder.className = "tool-preview-content";
  const actions = document.createElement("div");
  actions.className = "row tool-preview-actions";
  actions.appendChild(
    smallButton("ph:arrow-square-out Open", spec.title, () => spec.open(item)),
  );
  for (const button of spec.actions?.(item) || []) actions.appendChild(button);
  panel.append(holder, actions);
  //: A kind with no `preview` of its own is one whose body has to be fetched
  //:, notes and documents, which are read fresh so a conversation reopened
  //: days later previews the note as it is *now*.
  (spec.preview || toolPreviewBody)(item, holder);
  return panel;
}

//: The chip strip under a tool call. Takes card items that already carry
//: their `kind`, so both callers: the typed `cards` envelopes and an old
//: transcript's `touched` list: end up in the same renderer.
function toolCardChips(items) {
  const row = document.createElement("div");
  row.className = "tool-touched-wrap";
  const chips = document.createElement("div");
  chips.className = "row tool-touched";
  const previews = document.createElement("div");
  previews.className = "tool-previews";
  for (const item of items) {
    // Older transcripts (stored before `kind` existed) have notes only.
    const spec = CARD_KINDS[item.kind] || CARD_KINDS.note;
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip result-reason-chip result-reason-connected tool-touched-chip";
    //: The label is the thing's own first words, straight off the tool event,
    //: so it is Markdown and is rendered as such. 120 rather than a tight cut:
    //: the strip already ellipsises in CSS, and cutting here would flatten
    //: every label long enough to need it.
    setNoteLabel(chip, spec.icon, item.label || `#${item.id}`, 120);
    //: A kind with `preview: false` opens rather than expands, because there
    //: is nothing sensible to inline. A map's content as an Entry is the
    //: single line `# My map`, so the in-place preview every other kind gets
    //: would show that string and call it the map, worse than no preview,
    //: because it looks like the map is empty.
    if (spec.preview === false) {
      chip.title = spec.title;
      chip.addEventListener("click", (clickEvent) => {
        clickEvent.stopPropagation();
        spec.open(item.id);
      });
      chips.appendChild(chip);
      continue;
    }
    chip.setAttribute("aria-expanded", "false");
    chip.title = `${spec.title}: press to preview it here`;
    let panel = null;
    chip.addEventListener("click", (clickEvent) => {
      clickEvent.stopPropagation();
      if (panel) {
        panel.remove();
        panel = null;
        chip.setAttribute("aria-expanded", "false");
        chip.classList.remove("active");
        return;
      }
      panel = toolPreviewPanel(item, spec);
      previews.appendChild(panel);
      chip.setAttribute("aria-expanded", "true");
      chip.classList.add("active");
    });
    chips.appendChild(chip);
  }
  row.append(chips, previews);
  return row;
}

//: The typed envelopes `ai/cards.py` sends: `[{kind, items:[…]}]`, already in
//: kind order and already capped per kind. Flattened onto one strip on
//: purpose: a tool call that touched a note, its board and a reminder is one
//: action, and three headed sections would make it read as three.
function toolCardsRow(cards) {
  if (!Array.isArray(cards)) return null;
  const items = [];
  for (const group of cards) {
    if (!group || !Array.isArray(group.items)) continue;
    for (const item of group.items) {
      if (item && (item.id !== undefined || group.kind === "board")) {
        items.push({ ...item, kind: group.kind });
      }
    }
  }
  return items.length ? toolCardChips(items) : null;
}

function toolTouchedRow(touched) {
  if (!Array.isArray(touched) || !touched.length) return null;
  return toolCardChips(touched);
}

//: What `serialise` needs to write this row back out, parked on the node
//: itself. The transcript is rebuilt by walking the DOM, and a chip's
//: arguments, result summary and touched items have no representation there, 
//: scraping `textContent` recovered the label and lost everything else, so a
//: reopened conversation showed less of itself the second time you looked at
//: it. Stored as a property rather than a `data-` attribute because a result
//: summary runs to 4000 characters and does not belong in an attribute.
function markToolStep(node, step) {
  node.toolStep = step;
  return node;
}

function toolChip(label, ok = true, event = null) {
  const step = {
    kind: "tool",
    label,
    ok,
    arguments: event?.arguments || null,
    result_summary: event?.result_summary || null,
    touched: event?.touched || null,
    //: Saved with the turn, so a reopened conversation gets its cards back, 
    //: the same reason `touched` is here. Both are kept: a transcript written
    //: before `cards` existed still has `touched`, and `cardsRow` below falls
    //: back to it rather than showing a call that touched things as one that
    //: touched nothing.
    cards: event?.cards || null,
  };
  //: **Cards first, `touched` as the fallback.** They describe the same call,
  //: so drawing both would list every note twice; `cards` is the superset
  //: (five kinds against two), and `touched` is what an old saved turn has.
  const cardsRow = () => toolCardsRow(event?.cards) || toolTouchedRow(event?.touched);
  if (event && (event.arguments || event.result_summary)) {
    const details = document.createElement("details");
    details.className = `tool-chip ${ok ? "" : "tool-chip-error"}`.trim();
    
    const summary = document.createElement("summary");
    setLabel(summary, label);
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "tool-chip-body";
    if (event.arguments && Object.keys(event.arguments).length > 0) {
      const argsPre = document.createElement("pre");
      argsPre.className = "tool-chip-args";
      argsPre.textContent = JSON.stringify(event.arguments, null, 2);
      body.appendChild(argsPre);
    }
    if (event.result_summary) {
      const resPre = document.createElement("pre");
      resPre.className = "tool-chip-result";
      resPre.textContent = event.result_summary;
      body.appendChild(resPre);
    }
    details.appendChild(body);
    //: Outside the disclosure on purpose: the whole point is that it is
    //: visible while the call is happening, without a click.
    const touched = cardsRow();
    if (touched) {
      const wrap = document.createElement("div");
      wrap.className = "tool-chip-wrap";
      wrap.append(details, touched);
      return markToolStep(wrap, step);
    }
    return markToolStep(details, step);
  }

  const item = document.createElement("div");
  item.className = `tool-chip ${ok ? "" : "tool-chip-error"}`.trim();
  setLabel(item, label);
  const touched = cardsRow();
  if (touched) {
    const wrap = document.createElement("div");
    wrap.className = "tool-chip-wrap";
    wrap.append(item, touched);
    return markToolStep(wrap, step);
  }
  return markToolStep(item, step);
}

// A destructive tool call parked for approval (Wave G). Nothing has
// happened yet: Confirm actually runs it via /chat/tools/execute.
function renderToolConfirm(holder, event) {
  //: An act's card lives with the composer's page code (ask-compose.js).
  if (event.type === "act") return ensureModule("askCompose").then(() => renderActCard(holder, event));
  const card = document.createElement("div");
  card.className = "tool-confirm";
  const text = document.createElement("p");
  setLabel(text, `ph:warning Atlas wants to: ${event.label || event.name}`);
  
  const contentArea = document.createElement("div");
  
  if (event.name === "edit_note" && event.arguments.content) {
    // async fetch for diff
    apiJson(`/entries/${event.arguments.note_id}`).then(res => {
      const oldContent = res.content || "";
      const newContent = event.arguments.content;
      if (oldContent !== newContent) {
        //: DOM nodes, not an innerHTML template (SEC-16): a note's own text
        //: goes in as text, so no escaping has to be remembered.
        const viewer = document.createElement("div");
        viewer.className = "diff-viewer";
        const removed = document.createElement("div");
        removed.className = "diff-removed";
        removed.textContent = `- ${oldContent}`;
        const added = document.createElement("div");
        added.className = "diff-added";
        added.textContent = `+ ${newContent}`;
        viewer.append(removed, added);
        contentArea.replaceChildren(viewer);
      }
    }).catch(() => {});
  }

  const row = document.createElement("div");
  row.className = "row";
  row.appendChild(
    smallButton(
      "Confirm",
      "Run this action",
      async () => {
        try {
          const result = await apiJson("/chat/tools/execute", {
            method: "POST",
            body: JSON.stringify({ name: event.name, arguments: event.arguments }),
          });
          card.replaceWith(toolChip(`ph:check-circle ${result.label || event.label || event.name}`));
          toast("Done: check Activity for the audit trail.");
          refreshAfterToolChanges();
        } catch (error) {
          toast(error.message, true);
        }
      },
      false
    )
  );
  row.appendChild(
    smallButton("Cancel", "Don't do this", () => {
      card.replaceWith(toolChip("ph:x Cancelled: nothing was changed."));
    })
  );
  card.append(text, contentArea, row);
  holder.appendChild(card);
  chatScrollToEnd();
}

//: "open settings", "go to the graph" (decision 38): the place, opened.
function actNavigate(surface) {
  if (surface === "settings") openSettingsModal();
  else switchTab(surface);
}

// The model would like to remember something about you (§39B).
//
// This card is the whole point of the change behind it. `save_user_preference`
// used to write a standing instruction straight into every future system
// prompt: no confirmation, no notice, and the only trace was a list in
// Settings nobody had a reason to open. A model that over-read one sentence
// ("use British English for this one, actually") gave itself a permanent rule
// its user never agreed to, and would then keep obeying it for weeks.
//
// So the tool now *proposes*: the row is written inactive and flagged, it is
// excluded from the prompt, and this card is where it becomes real. Declining
// keeps the row (switched off) on purpose, the tool's duplicate check reads
// every preference, so a kept "no" is what stops the model suggesting the same
// thing again an hour later.
function renderMemoryProposal(holder, proposal) {
  const card = document.createElement("div");
  card.className = "tool-confirm memory-proposal";

  const text = document.createElement("p");
  setLabel(text, "ph:brain Remember this for next time?");

  const quote = document.createElement("blockquote");
  quote.className = "memory-proposal-text";
  quote.textContent = proposal.content;

  const note = document.createElement("p");
  note.className = "muted";
  note.textContent =
    "Saved preferences are added to Atlas's instructions in every later " +
    "conversation. Nothing is in force until you say yes.";

  const row = document.createElement("div");
  row.className = "row";

  let answered = false;
  const answer = async (accept) => {
    if (answered) return;
    answered = true;
    try {
      await apiJson(`/memory/${proposal.id}/answer`, {
        method: "POST",
        body: JSON.stringify({ accept }),
      });
      pushRequestUndo(accept ? "Remembered a preference" : "Declined a preference", `/memory/${proposal.id}`, "PATCH", { proposed: true, active: false }, { proposed: false, active: accept }, () => renderMemorySettings());
    } catch (error) {
      answered = false;
      toast(error.message, true);
      return;
    }
    card.replaceWith(
      toolChip(
        accept
          ? `ph:check-circle Remembered: “${proposal.content}”`
          : "ph:x Not remembered."
      )
    );
    // The Settings list is the other view of the same row; if it happens to
    // be open behind the chat, leaving it stale shows a pending question the
    // user has already answered.
    renderMemorySettings().catch(() => {});
  };

  row.appendChild(
    smallButton("Remember it", "Add this to Atlas's standing instructions", () => answer(true), false)
  );
  row.appendChild(smallButton("No thanks", "Don't save this preference", () => answer(false)));

  card.append(text, quote, note, row);
  holder.appendChild(card);
  chatScrollToEnd();
}

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

function settlePendingAgentQuestion(answer) {
  if (pendingAgentQuestion) pendingAgentQuestion.settle(answer);
}

function renderAgentQuestion(holder, event) {
  const card = document.createElement("div");
  card.className = "tool-confirm agent-ask";
  const text = document.createElement("p");
  setLabel(text, `ph:question ${event.question}`);
  const row = document.createElement("div");
  row.className = "row agent-ask-options";

  let chosen = null;
  let settled = false;
  const buttons = [];
  const other = document.createElement("input");
  other.type = "text";
  other.className = "agent-ask-other-input";
  other.placeholder = "Or write your own answer…";
  other.setAttribute("aria-label", "Your own answer");
  const send = smallButton("ph:paper-plane-right Send answer", "Send this answer", () => submit(), false);
  send.disabled = true;
  const sync = () => {
    send.disabled = !(chosen || other.value.trim());
    for (const button of buttons) {
      button.setAttribute("aria-pressed", button.dataset.option === chosen ? "true" : "false");
    }
  };
  for (const option of event.options || []) {
    const button = smallButton(option, `Choose: ${option}`, () => {
      // A second click on the chosen one clears it, as a toggle does.
      chosen = chosen === option ? null : option;
      if (chosen) other.value = "";
      sync();
    });
    button.dataset.option = option;
    button.setAttribute("aria-pressed", "false");
    buttons.push(button);
    row.appendChild(button);
  }
  other.addEventListener("input", () => {
    if (other.value.trim()) chosen = null;
    sync();
  });
  other.addEventListener("keydown", (keyEvent) => {
    if (keyEvent.key === "Enter") {
      keyEvent.preventDefault();
      submit();
    }
  });
  const settle = (answer) => {
    if (settled) return;
    settled = true;
    if (pendingAgentQuestion && pendingAgentQuestion.card === card) pendingAgentQuestion = null;
    card.replaceWith(toolChip(`ph:question ${event.question} → ${answer}`));
  };
  const submit = () => {
    const answer = other.value.trim() || chosen;
    if (!answer || settled) return;
    settle(answer);
    sendChatMessage(answer);
  };
  const otherRow = document.createElement("div");
  otherRow.className = "row agent-ask-other";
  otherRow.append(other, send);
  const note = document.createElement("p");
  note.className = "muted";
  note.textContent = "Pick one or write your own, then send. Typing in the chat bar answers it too.";
  card.append(text, row, otherRow, note);
  holder.appendChild(card);
  pendingAgentQuestion = { card, settle };
  chatScrollToEnd();
}

function refreshAfterToolChanges() {
  loadEntries().catch(() => {});
  loadReminders().catch(() => {});
  loadMostUsed();
}

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

//: Turn every control inside a rendered fragment into inert markup, keeping
//: its text and its classes. Used where a rendered preview is placed inside a
//: card that is itself clickable: the preview should still *look* like the
//: note, and must not contain a second thing to press.
function deactivateControls(root) {
  for (const node of root.querySelectorAll("a, button, input, [tabindex]")) {
    if (node.tagName === "INPUT") {
      node.disabled = true;
      node.tabIndex = -1;
      continue;
    }
    const flat = document.createElement("span");
    flat.className = node.className;
    while (node.firstChild) flat.appendChild(node.firstChild);
    node.replaceWith(flat);
  }
}

function chatSourcesFrom({ meta, toolEvents, touched }) {
  const seen = new Set();
  const sources = [];
  const add = (source) => {
    const key = `${source.kind}:${source.id}`;
    if (!source.label || seen.has(key)) return;
    seen.add(key);
    sources.push(source);
  };
  //: One line of the note itself, so a card says what it *is* rather than
  //: only what it is called. Asked for: "dropdown previews".
  const preview = (text) => {
    const flat = String(text || "").replace(/\s+/g, " ").trim();
    return flat.length > 180 ? `${flat.slice(0, 180)}…` : flat;
  };
  for (const entry of meta?.raw_results || []) {
    const label = noteLabel(entry, 60);
    //: A note has no title, so its label *is* its opening words, which means
    //: the preview has to start where the label stopped, or the card prints
    //: the same sentence twice (measured: it did).
    const flat = String(entry.content || "").replace(/\s+/g, " ").trim();
    const head = label.replace(/…$/, "");
    //: The label is elided at 60 characters, which usually lands mid-word, so
    //: the remainder starts mid-word too, and the card read "ling and why it
    //: matters for gradients." (measured, in a screenshot). Dropping the
    //: partial first word costs nothing and is the difference between a
    //: preview and a typo.
    const rest = flat.startsWith(head)
      ? flat.slice(head.length).replace(/^\S*\s+/, "")
      : flat;
    //: A board or a mind map is a row of `raw_results` too (INBOX 744: "whiteboard
    //: shows as a note and clicking it takes me to the notes page").
    const board = entry.board_kind;
    add({
      kind: board === "map" ? "map" : board ? "board" : "note",
      id: entry.id,
      label,
      snippet: board ? "" : preview(rest),
      //: The note itself rides along, so the card can show its picture and its
      //: attached files rather than only a line of its text. Reported: "the
      //: sources in the chat responses dont render inline md, images or files."
      entry,
      open: board ? () => openWhiteboardBoard(entry.id) : (event) => openNoteAtPassage(entry.id, event?.currentTarget),
    });
  }
  for (const item of touched || []) {
    const opener = TOUCHED_KINDS[item.kind] || TOUCHED_KINDS.note;
    //: A touched row carries an id and a label and nothing else, but the note
    //: behind it is already loaded, so the card need not be the poorer for it.
    //: A map is excluded from that lookup along with a document: its Entry
    //: content is the single line `# My map`, so "one line of the thing
    //: itself" would print the title a second time as its own preview.
    const known =
      item.kind === "document" || item.kind === "map"
        ? null
        : (typeof allEntries !== "undefined" ? allEntries : []).find(
            (row) => row.id === item.id
          ) || null;
    add({
      //: The kind is carried through rather than collapsed to note/document,
      //: so a map's source card gets the map icon and opens the board. It used
      //: to be a two-way ternary, which meant every kind added later silently
      //: became a note: the shape that makes a new kind look like it works.
      kind: item.kind === "document" || item.kind === "map" ? item.kind : "note",
      id: item.id,
      label: item.label,
      snippet: known ? preview(String(known.content || "").replace(/\s+/g, " ")) : "",
      entry: known,
      open: () => opener.open(item.id),
    });
  }
  for (const event of toolEvents || []) {
    const kind = SOURCE_TOOLS[event?.tool || event?.name];
    if (!kind || event.ok === false) continue;
    //: **The real rows, when the backend sent them.** `event.sources`
    //: (agent.py's `_tool_sources`) carries a title, an address and a line of
    //: the page for every result a read tool actually consulted, which is
    //: what a card, a preview and a working link all need and what the prose
    //: label alone could never provide.
    const rows = Array.isArray(event.sources) ? event.sources : [];
    if (rows.length) {
      for (const row of rows) {
        add({
          kind,
          id: row.url || `${event.tool}-${row.title}`,
          label: row.title || row.url,
          snippet: preview(row.snippet),
          url: row.url || "",
        });
      }
      continue;
    }
    //: The fallback for a tool that named no rows: its own label, minus the
    //: icon token. Still better than dropping the source entirely, it says
    //: the answer read *something* outside the notebook.
    const label = String(event.label || "").replace(/^ph:[\w-]+\s*/, "");
    add({ kind, id: `${event.tool || event.name}-${sources.length}`, label, snippet: "" });
  }
  //: Web pages first (the owner, 2026-10-10): a page the turn went out to
  //: read is the newest thing in it. One order, so the numbers in the answer
  //: and on the cards stay the same.
  return [...sources.filter((s) => s.kind === "web"), ...sources.filter((s) => s.kind !== "web")];
}

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

//: **The Sources panel: cards, previews and real links.**
//:
//: Reported twice: *"improve the ui of the sources as well in the chat"* and
//: then, specifically, *"ui and usability, what is shown about the sources,
//: dropdown previews, hyperlinks etc."*
//:
//: It was a list of one-line strings: no preview, no address, and, for
//: anything off the web, nothing clickable at all, because the tool events
//: never carried a URL to click (fixed in agent.py's `_tool_sources`). What a
//: reader wants from this panel is the same three things every search result
//: in the world shows: what it is, where it came from, and enough of it to
//: judge whether to open it.
//:
//: Numbered, because the numbers are what make a citation mean something: a
//: card is "[3] arxiv.org", so an answer that says "[3]" has somewhere to
//: point. A web card is a real `<a href>`, middle-click, copy link address
//: and open-in-new-tab all work, which no button can offer.
function chatSourcesPanel(input) {
  //: `input.sources` when the caller has already built the list, so the
  //: numbers on these rows are the same numbers the inline citations used.
  //: Two derivations of "the same" order is how they drift apart, which is
  //: what INBOX 81's second half is about.
  const sources = input.sources || chatSourcesFrom(input);
  if (!sources.length) return null;
  //: **The number on a card is the number in the answer**, which stops being
  //: the card's own position the moment this panel is handed a subset (the
  //: Ask tab passes only the sources its records column is not already
  //: showing). `numberFrom` is the full list the citation markers were
  //: numbered against; without it a panel of two would call them 1 and 2 and
  //: disagree with the [4] and [5] printed in the answer above it.
  const numbering = input.numberFrom || sources;
  //: `row`: one-line rows instead of cards, open (the popup agent's).
  const row = input.row;
  const details = document.createElement("details");
  details.className = "chat-sources";
  details.open = Boolean(row);
  const summary = document.createElement("summary");
  summary.className = "chat-sources-summary";
  //: The heading counts by kind, "4 notes · 2 files", rather than saying
  //: "6 sources". A reader deciding whether to open this wants to know what
  //: is in it, and the breakdown is the same length as the total was.
  const counts = CHAT_SOURCE_GROUPS.map((g) => {
    const n = sources.filter((s) => s.kind === g.key).length;
    return n ? `${n} ${n === 1 ? g.one : g.many}` : null;
  }).filter(Boolean);
  const mode = input.meta?.search_mode;
  const how = mode && mode !== "none" ? ` · ${SEARCH_MODE_LABELS[mode] || mode}` : "";
  setLabel(summary, `ph:books Sources: ${counts.join(" · ")}${how}`);
  summary.title = "What this answer drew on, click to see each source";
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "chat-sources-body";
  const grid = document.createElement("div");
  grid.className = row ? "chat-sources-list" : "chat-sources-grid";
  const icons = Object.fromEntries(CHAT_SOURCE_GROUPS.map((g) => [g.key, g.icon]));
  sources.forEach((source, index) => {
    if (row) return grid.appendChild(row(source, icons));
    //: Three shapes, one card. A web source is an anchor, a local one that
    //: can be opened is a button, and one that can be neither is a plain
    //: block: because a control that does nothing when pressed is worse
    //: than no control, which this app has been told before.
    let card;
    if (source.url) {
      card = document.createElement("a");
      card.href = safeHref(source.url);
      card.target = "_blank";
      //: `noopener` is not optional on a target=_blank link to a page this
      //: app did not write: without it the opened page gets a handle on this
      //: window and can navigate it.
      card.rel = "noopener noreferrer";
      card.title = source.url;
    } else if (source.open) {
      card = document.createElement("button");
      card.type = "button";
      card.title = "Open this";
      card.addEventListener("click", source.open);
    } else {
      card = document.createElement("div");
    }
    card.className = `chat-source-card${source.url || source.open ? " is-openable" : ""}`;
    //: Which note this card is, so a citation marker in the answer can find
    //: its own card and show the passage it came from (`showCitedPassage`).
    //: An id rather than the index, because the panel caps its rows and the
    //: numbering falls back past the cap.
    if (source.kind === "note" && source.id != null) card.dataset.noteId = String(source.id);
    const head = document.createElement("span");
    head.className = "chat-source-head";
    const number = document.createElement("span");
    number.className = "chat-source-index";
    const at = numbering.indexOf(source);
    number.textContent = String((at === -1 ? index : at) + 1);
    const title = document.createElement("span");
    title.className = "chat-source-title";
    setLabel(title, `${icons[source.kind] || "ph:note"} ${source.label}`);
    head.append(number, title);
    card.appendChild(head);
    //: **A source card is a note preview, and every other note preview in this
    //: app renders.** Reported: *"the sources in the chat responses dont render
    //: inline md, images or files etc."*, the snippet was `textContent`, so a
    //: note reading `**Due Friday**: see ![](/media/x.png)` printed its own
    //: asterisks and the literal text of an image it was holding.
    //:
    //: Three things, in the order the eye wants them: the picture (embedded or
    //: attached: `noteRowImage`, dashboard.js, which exists because an
    //: attached image appears nowhere in the note's markdown), the text with
    //: its markdown rendered, and a chip per non-image attachment so a note
    //: that is really a wrapper around a PDF says so.
    const image = source.entry ? noteRowImage(source.entry) : null;
    if (image) {
      const thumb = document.createElement("img");
      thumb.className = "chat-source-thumb";
      thumb.src = mediaSrc(image.url);
      thumb.alt = image.alt || "";
      thumb.loading = "lazy";
      card.classList.add("has-thumb");
      card.appendChild(thumb);
    }
    if (source.snippet) {
      const snippet = document.createElement("p");
      snippet.className = "chat-source-snippet";
      //: `compact` because this is a two-line preview inside a card, not a
      //: note body: it is the same flag the timeline and widget previews pass.
      //: Wiki links are unwrapped first, renderInlineMarkdown is inline-only
      //: and does not know `[[…]]`, so without this a linked note printed its
      //: own brackets.
      //: Block markers stripped wherever one starts a word (a heading's `#`
      //: printed as text, owner's screenshot), and a snippet that opens with
      //: the note's own title, which is the card's title line already, starts
      //: after it instead of saying it twice.
      let text = source.snippet
        .replace(/\[\[([^[\]]{1,120})\]\]/g, "$1")
        .replace(/(^|\s)#{1,6}\s+/g, "$1")
        .replace(/(^|\s)>\s+/g, "$1")
        .trim();
      const label = String(source.label || "").trim();
      if (label && text.toLowerCase().startsWith(label.toLowerCase())) {
        text = text.slice(label.length).replace(/^[\s:.,-]+/, "");
      }
      renderInlineMarkdown(snippet, text, null, true);
      //: **The card is itself a control**, so nothing inside it may be one.
      //: renderInlineMarkdown emits real `<a>`s and file chips for links, and
      //: an anchor nested inside this card's own `<a>`/`<button>` is both
      //: invalid and unreachable by keyboard, the outer control swallows it.
      //: The formatting is what was asked for; the second click target was not.
      deactivateControls(snippet);
      if (text) card.appendChild(snippet);
    }
    const files = (source.entry?.attachments || []).filter((file) => !file.is_image);
    if (files.length) {
      const strip = document.createElement("span");
      strip.className = "chat-source-files";
      for (const file of files.slice(0, 3)) {
        const chip = document.createElement("span");
        chip.className = "chip chat-source-file";
        setLabel(chip, `ph:paperclip ${file.filename || "file"}`);
        chip.title = file.filename || "";
        strip.appendChild(chip);
      }
      if (files.length > 3) {
        const more = document.createElement("span");
        more.className = "chip chat-source-file muted";
        chipWords(more, `+${files.length - 3}`);
        strip.appendChild(more);
      }
      card.appendChild(strip);
    }
    const foot = document.createElement("span");
    foot.className = "chat-source-foot muted";
    const group = CHAT_SOURCE_GROUPS.find((g) => g.key === source.kind);
    foot.textContent = source.url ? sourceHost(source.url) || "the web" : group?.one || source.kind;
    card.appendChild(foot);
    grid.appendChild(card);
  });
  body.appendChild(grid);
  details.appendChild(body);
  //: **On a phone the sources are a sheet** (UI_MODERNISATION_PLAN Phase 11
  //: item 3). Opened in place, the grid of cards unfolds inside a bubble in
  //: a 340px-tall transcript and pushes the answer it belongs to off the
  //: screen. The same body, moved into the sheet recipe for as long as it
  //: is open and put back on close, so a source card built once is the one
  //: that opens, on either surface.
  summary.addEventListener("click", (event) => {
    if (!window.matchMedia(PHONE_TABS).matches || typeof openSheet !== "function") return;
    event.preventDefault();
    openSheet({
      label: "Sources",
      name: "sources",
      returnFocus: summary,
      build: (card) => card.appendChild(body),
      onClose: () => details.appendChild(body),
    });
  });
  return details;
}

function renderRecordsDetails(holder, meta) {
  if (!meta.raw_results.length) return;
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.className = "muted";
  const label = SEARCH_MODE_LABELS[meta.search_mode] || meta.search_mode;
  summary.textContent = `${meta.raw_results.length} matching note${
    meta.raw_results.length === 1 ? "" : "s"
  } (${label}): click one to open it`;
  // The tune-sensitivity shortcut used to live here too, repeated on every
  // single message's own disclosure. Reported directly: it belongs as one
  // persistent control (`#chat-tune-search`, wired near the Chat dock's
  // other "how it answers" settings) instead of message metadata.
  details.appendChild(summary);
  const list = document.createElement("ul");
  list.className = "entry-list";
  // Same provenance badges as the Ask tab (matchReasonBadge / renderRawResults
  // above): the backend's "meta" SSE event already carries match_info and
  // connected_ids for a chat turn, same shape as an Ask turn's; this just
  // hadn't been wired up here, so a chat search result showed no reason at
  // all while the identical Ask result did.
  const connected = new Set(meta.connected_ids || []);
  const matchInfo = meta.match_info || {};
  const scored = everyRowScored(meta.raw_results, matchInfo, connected);
  for (const entry of meta.raw_results) {
    const row = clickableResult(entry);
    const badge = matchReasonBadge(matchInfo[entry.id], scored);
    if (badge) {
      if (connected.has(entry.id)) row.classList.add("result-connected");
      if (matchInfo[entry.id]?.type === "connected_2hop") row.classList.add("result-connected-2hop");
      placeResultBadge(row, badge);
    }
    list.appendChild(row);
  }
  details.appendChild(list);
  holder.appendChild(details);
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

//: **The five asks the free-text instruction was being used for**, written
//: down once. A chip sets what to write and, where it helps, a first line in
//: the thoughts box; nothing runs until Draft is pressed, so a chip is a
//: starting point rather than a button that spends a minute of a local
//: model's time on a guess.
const DRAFT_QUICKSTARTS = [
  { label: "Write up my notes", icon: "ph:note-pencil", kind: "note", title: "Turn what is in the box into one organised note" },
  { label: "Carry on writing", icon: "ph:pencil-line", kind: "continue", title: "Keep writing from where the draft stops, in the same voice" },
  { label: "Say it plainly", icon: "ph:chat-text", kind: "rewrite", tone: "plain", title: "The same draft in plain words" },
  { label: "Bullets to prose", icon: "ph:text-align-left", kind: "expand", title: "Open the bullet points out into paragraphs" },
  { label: "Prose to bullets", icon: "ph:list-bullets", kind: "bullets", title: "Close the writing back up into bullet points" },
  //: The language is the last one chosen in the kind menu's "Translate into"
  //: group, Spanish until one has been; the menu shows which, and changing
  //: it there is how another language is picked.
  { label: "Translate", icon: "ph:translate", kind: "translate", title: "Translate what is in the box, into the language chosen in the menu" },
];

//: **Translate a note from where it is read** (INBOX 405). Writing room
//: already translates; this takes the note there, loaded and set to the last
//: language picked, rather than asking the reader to copy it across. Nothing
//: runs until Draft is pressed, like every other starting point on the desk,
//: and a desk that already holds writing is asked about before it is
//: replaced.
async function translateNoteInDesk(entry) {
  const busy = $("draft-thoughts").value.trim() || $("draft-text").value.trim();
  if (busy && !(await confirmDialog("Replace what is in the Writing room with this note?"))) return;
  switchTab("notes");
  showNotesSection("writing-room");
  $("draft-thoughts").value = entry.content || "";
  $("draft-text").value = "";
  $("draft-kind").value = draftTranslateKind();
  $("draft-kind").dispatchEvent(new Event("change"));
  saveDraftLocally();
  toast("Pick the language in the menu beside Draft, then press Draft.");
  $("draft-kind").closest(".select-shell")?.querySelector("button")?.focus();
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

function renderDraftQuickstarts() {
  const host = $("draft-quickstarts");
  if (!host) return;
  host.replaceChildren();
  for (const start of DRAFT_QUICKSTARTS) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "library-chip";
    chip.title = start.title;
    setLabel(chip, `${start.icon} ${start.label}`);
    chip.addEventListener("click", () => {
      $("draft-kind").value = start.kind === "translate" ? draftTranslateKind() : start.kind;
      if (start.tone) $("draft-tone").value = start.tone;
      markDraftQuickstart(start.kind);
      saveDraftLocally();
      $("draft-thoughts").focus();
    });
    host.appendChild(chip);
  }
  markDraftQuickstart($("draft-kind").value);
}

//: The chip and the select say the same thing, so picking either marks the
//: other: two controls that disagree about what the next pass will do is the
//: defect this feature is full of everywhere else it has been tried.
function markDraftQuickstart(kind) {
  const host = $("draft-quickstarts");
  if (!host) return;
  [...host.children].forEach((chip, index) => {
    const own = DRAFT_QUICKSTARTS[index]?.kind;
    chip.classList.toggle(
      "active",
      own === kind || (own === "translate" && String(kind).startsWith("translate-"))
    );
  });
}

function renderDraftSources() {
  const host = $("draft-sources");
  const count = $("draft-sources-count");
  if (!host) return;
  host.replaceChildren();
  host.classList.toggle("hidden", draftSources.length === 0);
  count.textContent = draftSources.length
    ? `${draftSources.length} note${draftSources.length === 1 ? "" : "s"} to write from`
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
    chip.title = `${version.words} words, ${version.at}`;
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
    words: trimmed.split(/\s+/).length,
    at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
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
  setLabel(save, draftNoteId === null ? "ph:floppy-disk Save as note" : "ph:floppy-disk Save to that note");
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
  const words = text ? text.split(/\s+/).length : 0;
  return words ? `${words} word${words === 1 ? "" : "s"}` : "";
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
  button.disabled = !!draftController || draftUndoStack.length === 0;
  button.title = draftUndoStack.length
    ? `Go back to the version before the last AI pass (${draftUndoStack.length} available)`
    : "Nothing to undo yet";
}

function undoDraft() {
  const previous = draftUndoStack.pop();
  if (!previous) return;
  //: The same entry the status bar holds, run from the pane's own button, so
  //: its redo knows what the pass had written.
  if (previous.action) {
    settleUndoFromToast(previous.action);
    previous.action.undo();
  } else putDraftBack(previous);
  $("draft-status").classList.remove("error");
  $("draft-status").textContent = "Went back to the previous version.";
  announce("Restored the draft from before the last AI pass.");
}

// One-shot AI calls (drafting, document edits) had no way out: press the
// button by mistake or watch it stall, and the only options were waiting or
// reloading the page. Each now runs against an AbortController so it can be
// cancelled, and shows that it's working while it does.
let draftController = null;

function cancelDraft() {
  draftController?.abort();
}

// What was last folded into the draft. Kept so a second pass doesn't resend
// thoughts the model has already used, which is the problem clearing the box
// was solving, at the cost of destroying the user's own writing.
let foldedThoughts = "";

