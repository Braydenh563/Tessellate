// ask-compose.js: the Ask box's AI switch (INBOX 688, 714, K6, K34).
//
// The owner: "is there a way to do very good imitations of ai responses but
// using string concatenation with the app when the ai isnt available with the
// option to toggle between them in the ask subtab??" The answer itself is the
// server's (`ai/composer.py`): every sentence quoted from a note, only the
// connective words written by the app. This file is the switch that asks for
// it, `#ask-use-ai` in index.html: one compact switch row on the app's
// pill-switch recipe (06-timeline-dialogs.css). It replaced a two-segment
// pill ("AI | From your notes") that "doesnt feel modern and professional"
// (INBOX 714); only the control changed, the stored choice did not.
//
// - On is an AI-composed answer, off is "From your notes". The choice is this
//   device's (`prefs`, "ask-answer-from", "ai" or "notes"), read by
//   `streamChatEvents` on every notes-only turn and sent as `answer_from`.
// - With no model running "From your notes" is the answer whatever is stored,
//   so the switch shows off and disabled with the exact cause (askAiOffCause); the stored choice is
//   left alone, and the switch comes back the moment a model does.
// - `askQuestion` and the helpers only it uses (`setAsking`, `askStatusText`,
//   `renderChatMeta`, ...) moved here from capture-ask.js on 2026-11-01 (boot
//   diet, audit row 21): a click on Ask, Enter in the box or a recent question
//   is a `LAZY_ENTRY_POINTS`-style stand-in (lazy-entries.js) that fetches this
//   file first. Nobody reads its return.
// - Lazy and preloaded three seconds after boot (app.js), because the boot
//   scripts are at their gzip cap; until the first status lands the markup's
//   neutral state (unchecked, enabled) stands, and the server composes
//   regardless when no model runs.

const ASK_ANSWER_FROM_KEY = "ask-answer-from";

//: The title when a model answers.
const ASK_AI_ON_TITLE = "Atlas answers with your model, citing your notes. Off: answers are quoted from your notes, with no AI";

//: **The exact cause, not "no model"** (K34, the owner: it "disables itself"
//: with no word why). Three causes, in the order they can be told apart: the
//: server does not answer (its URL, so a wrong port shows), it answers with
//: nothing pulled, or the chosen chat model is not among what it has.
function askAiOffCause() {
  const s = modelStatus || {};
  const server = s.provider && s.provider !== "ollama" ? "The model server" : "Ollama";
  if (s.ollama_running === false) return `${server} is not answering${s.base_url ? ` at ${s.base_url}` : ""}.`;
  if (!(s.installed_models || []).length) return `${server} is answering but has no models pulled.`;
  return `The chat model "${s.chat_model || "none chosen"}" is not installed.`;
}

function askAnswerFrom() {
  if (aiIsOff()) return "notes";
  return prefs.get(ASK_ANSWER_FROM_KEY) === "notes" ? "notes" : "ai";
}

function renderAskUseAi() {
  const box = $("ask-use-ai");
  if (!box) return;
  //: Neutral until the first status lands: unchecked and enabled, so the
  //: switch never flips from "looks active" to "disabled".
  if (!modelStatus) return;
  const off = aiIsOff();
  box.checked = askAnswerFrom() === "ai";
  box.disabled = off;
  const cause = off ? askAiOffCause() : "";
  const label = box.closest("label");
  if (label) label.title = off ? `${cause} Answers come from your notes. Connect a model in Settings, Models.` : ASK_AI_ON_TITLE;
  //: The Ask notice names the cause too, after the poll rebuilds it.
  const text = document.querySelector("#ask-offline .ai-offline-text");
  const line = off ? `${cause} Ask shows the matching records below.` : "";
  if (text && line && text.textContent !== line) text.textContent = line;
}

function wireAskUseAi() {
  const box = document.getElementById("ask-use-ai");
  if (!box || box.dataset.wired) return;
  box.dataset.wired = "1";
  box.addEventListener("change", () => {
    //: A click before the switch caught up with a model that is off stores nothing (INBOX 1601).
    if (box.disabled || aiIsOff()) return renderAskUseAi();
    prefs.set(ASK_ANSWER_FROM_KEY, box.checked ? "ai" : "notes");
    renderAskUseAi();
  });
  //: **Following the model without a hook in the boot scripts.** The status
  //: poll redraws `#ask-offline` on every tick (`renderAiOfflineNotice`),
  //: showing it exactly when no model answers; watching it keeps the switch
  //: in step with the model starting and stopping, and rewrites the notice's
  //: sentence with the cause (its button already opens Settings, Models).
  const offline = $("ask-offline");
  //: **And the AI pill's level** (INBOX 1601): the notice does not change when it is hidden, or when it was
  //: drawn before this file loaded, so the switch stayed in its neutral look (reads as on) until a click.
  //: The pill's `data-level` changes on every status that differs; one observer watches both.
  const watch = new MutationObserver(renderAskUseAi);
  if (offline) watch.observe(offline, { attributes: true, attributeFilter: ["class"], childList: true });
  const pill = $("ai-status");
  if (pill) watch.observe(pill, { attributes: true, attributeFilter: ["data-level"] });
  document.addEventListener("ask-answerer-changed", renderAskUseAi);
  renderAskUseAi();
}

onSurface("notes", wireAskUseAi);

//: **A sentence said from a note is drawn as one** (CHAT_PLAN decision 33):
//: an answer composed from the notes marks each of its rows `said`, "quoted"
//: (the note's words as written) or "shifted" (said back to the person who
//: wrote them, "I went" as "you went", the row keeping the note's own words
//: as `original`). Each is wrapped in `.said` (ask-compose-lazy.css: plain
//: text in full ink, no bar and no grey, INBOX 1602; never quotation marks,
//: which are not the note's and broke grounding when they were added to the
//: text); a shifted one
//: carries the note's own words as its hover text, and the citation peek
//: shows them too. Found by the letters the citations use
//: (`citationTextIndex`); a sentence that crosses an element edge is left
//: as it is rather than broken apart. Called after every paint, so a
//: sentence already wrapped is skipped.
//: Its sheet comes with this file, through the lazy loader that stamps it
//: (app.js `lazyScript`); naming it in `LAZY_MODULES` would grow app.js past
//: its gzip ratchet (`test_static_compression.py`).

function markSaidSentences(targets, sentences) {
  for (const g of sentences || []) {
    if (g.said !== "quoted" && g.said !== "shifted") continue;
    const key = citationKey(g.sentence);
    if (key.length < 12) continue;
    const index = citationTextIndex(targets);
    const at = index.text.indexOf(key);
    if (at === -1) continue;
    const [first, from] = index.at[at];
    const [last, to] = index.at[at + key.length - 1];
    if (first.parentElement?.closest(".said")) continue;
    const range = document.createRange();
    range.setStart(first, from);
    range.setEnd(last, to + 1);
    const span = document.createElement("span");
    span.className = g.said === "shifted" ? "said said-shifted" : "said";
    if (g.said === "shifted" && g.original) span.title = `In your note: ${g.original}`;
    try {
      range.surroundContents(span);
    } catch {
      // Crosses an element edge (a bold word inside the sentence): left plain.
    }
  }
}

//: **An act's card, with no model** (CHAT_PLAN decision 38): the exact change
//: in one line, the notes it names, and either Confirm and Cancel (a delete,
//: a rename, a move or a tag waits for them) or, once it ran (a reminder, a
//: new note, a pin), what was done and Undo. Confirm and Undo both post the
//: steps to `/chat/command/run`, which runs only the tools an act may use.
const ACT_ITEMS_SHOWN = 5;

//: The notes a bulk act names (X14): the first five, then "Show all N" for the rest; null when there are none.
function actItemList(items) {
  if (!items || !items.length) return null;
  const list = document.createElement("ul");
  list.className = "act-items";
  items.forEach((title, at) => {
    const row = document.createElement("li");
    row.textContent = title;
    if (at >= ACT_ITEMS_SHOWN) row.hidden = true;
    list.appendChild(row);
  });
  if (items.length > ACT_ITEMS_SHOWN) {
    const more = document.createElement("li");
    const button = smallButton(`Show all ${items.length}`, "List every note this changes", () => {
      for (const row of list.children) row.hidden = false;
      more.remove();
    });
    more.appendChild(button);
    list.appendChild(more);
  }
  return list;
}

function renderActCard(holder, event) {
  //: The theme is a preference of this page (`applyThemeChoice`), so the server's `set_theme` step only
  //: acknowledges it: the page applies it here, and the step that undoes it names the theme that was showing.
  function applyThemeSteps(steps, result) {
    const step = (steps || []).find((one) => one.name === "set_theme");
    if (!step || !result) return result;
    const before = prefs.get("theme", null) || "system";
    applyThemeChoice(step.arguments.theme, true);
    for (const inverse of result.undo || []) if (inverse.name === "set_theme") inverse.arguments = { theme: before };
    return result;
  }
  //: The card a typed yes or no answered: found by its id, which stays on it after a send marks it not pending.
  const waitingCard = (reply) => [...document.querySelectorAll(".tool-confirm")].filter((card) => (reply.consent_id ? card.consentId === reply.consent_id : !reply.label || card.dataset.askedAct === reply.label)).at(-1);
  //: "cancel" said in the chat (CHAT_PLAN X17): the server's reply closes the
  //: card it names (the last open one with that label, the one the page sent as
  //: `pending_act` in `chatHistoryToSend`), nothing else is drawn.
  if (event.cancel) {
    const open = waitingCard(event);
    if (open) open.replaceWith(toolChip("ph:x Cancelled: nothing was changed."));
    return;
  }
  //: A typed yes ran the card that waited (`ai/consent.py`): it is settled, not pressed twice.
  if (event.settle) {
    const waiting = waitingCard(event);
    if (waiting) waiting.remove();
    refreshAfterToolChanges(); // what the typed yes wrote, as Confirm does
    if (!event.done) return;
  }
  const restored = typeof event.state === "string";
  if (event.state === "cancelled" || event.state === "undone") return void holder.appendChild(toolChip(`ph:${event.state === "undone" ? "check" : "x"} ${event.notice}`));
  const card = document.createElement("div");
  card.className = "tool-confirm";
  const run = (steps, then) =>
    apiJson("/chat/command/run", { method: "POST", body: JSON.stringify({ steps, skipped: event.skipped || [], consent_id: steps === event.steps ? event.consent_id || null : null }) })
      .then((result) => (refreshAfterToolChanges(), then(applyThemeSteps(steps, result))))
      .catch((error) => toast(error.message, true));
  const line = (label, ...more) => {
    const text = document.createElement("p");
    setLabel(text, label);
    card.replaceChildren(text, ...more);
  };
  //: Every act's inverse goes on the app-wide undo stack too (WORLD_CLASS
  //: decision 53, the act registry's `inverse`), so Ctrl+Z after an act takes
  //: it back like any other change. Redo runs the act's steps again and keeps
  //: the inverse of that run, whose ids are new.
  const post = (steps) =>
    apiJson("/chat/command/run", { method: "POST", body: JSON.stringify({ steps, skipped: event.skipped || [] }) }).then((result) => {
      refreshAfterToolChanges();
      return applyThemeSteps(steps, result);
    });
  //: `said`: the answer above already read this sentence (a reminder, a new
  //: note or a pin ran at once), so the card carries only Undo; drawing the
  //: sentence again made the bubble say it twice. The words stay on the card
  //: as its accessible name, and a run with nothing to undo draws no card.
  const done = (summary, undo, steps, said = false, again = false) => {
    delete card.dataset.pendingAct;
    //: A Confirmed card wrote: Regenerate on this answer asks first (sm-1111 row 16, `confirmRerun`).
    const answer = card.closest(".msg");
    if (answer) answer.dataset.wrote = "1";
    const row = document.createElement("div");
    row.className = "row";
    if (undo?.length) {
      let inverse = undo;
      const action = again
        ? null
        : pushUndo(
            summary.replace(/^Done:\s*/, "").replace(/\.$/, ""),
            () => post(inverse),
            async () => {
              const redone = await post(steps);
              inverse = redone.undo || [];
            }
          );
      row.appendChild(
        smallButton("Undo", "Take this back", () =>
          run(inverse, () => {
            if (action) settleUndoFromToast(action);
            chatHistoryToSend.settle(card, event, "undone");
            card.replaceWith(toolChip("ph:arrow-counter-clockwise Undone."));
          })
        )
      );
    }
    if (said) {
      card.setAttribute("role", "group");
      card.setAttribute("aria-label", summary);
      card.replaceChildren(...row.childNodes.length ? [row] : []);
      return;
    }
    line(`ph:check-circle ${summary}`, row);
  };
  //: A typed yes ran the step on the server; the page applies the theme it named, once (a restored card already did).
  if (event.done && !restored) applyThemeSteps(event.steps, event);
  if (event.done || event.state === "done") done(event.summary || event.label, event.undo, event.steps, Boolean(event.done), restored);
  else {
    const notice = document.createElement("p");
    notice.className = "muted";
    notice.textContent = event.notice;
    const row = document.createElement("div");
    row.className = "row";
    const itemList = actItemList(event.items);
    row.append(
      smallButton("Confirm", "Do this", () =>
        run(event.steps, (result) => {
          chatHistoryToSend.settle(card, event, "done");
          done(result.summary, result.undo, event.steps);
        }),
      false),
      smallButton("Cancel", "Don't do this", () => {
        chatHistoryToSend.settle(card, event, "cancelled");
        card.replaceWith(toolChip("ph:x Cancelled: nothing was changed."));
      })
    );
    //: The line above the card already says the change (L57: the bubble read it twice); the label stays on the group for a screen reader.
    if (event.label_said) {
      card.setAttribute("role", "group");
      card.setAttribute("aria-label", event.label);
      card.replaceChildren(notice, ...(itemList ? [itemList] : []), row);
    } else line(`ph:warning ${event.label}`, notice, ...(itemList ? [itemList] : []), row);
    if (event.state === "expired") {
      for (const button of row.querySelectorAll("button")) button.disabled = true;
      return void holder.appendChild(card);
    }
    //: Open until Confirm settles it (`done` clears this) or Cancel replaces the card; the page tells the server (`chatHistoryToSend`).
    card.dataset.pendingAct = card.dataset.askedAct = event.label || "";
    card.consentId = event.consent_id || ""; // the server holds what a typed yes runs (`chatHistoryToSend`)
  }
  if (card.childElementCount) holder.appendChild(card);
  chatScrollToEnd();
}

//: **The web pages an answer read** (CHAT_PLAN decisions 37 and 66): one
//: fold under the answer in the Thinking fold's look (`.web-fold`,
//: ask-compose-lazy.css), its summary the count, each result a card (INBOX
//: 1300 C06: "a websearch shows the link as a clickable card not just a
//: url"): a globe tile, its title, its site and two lines of what it says. A
//: press anywhere on the card reads the page here (`readWebPage`); the arrow
//: opens it in the browser. Only http and https addresses are drawn.
//: `{ read: true }` is a page the model read (`read_url`) or one address on
//: its own: the summary names the page and opening the fold reads it, the
//: same reader, so a fetch is a disclosure that opens the page in place.
function renderWebSources(holder, sources, { read = false } = {}) {
  const pages = (sources || []).filter((source) => /^https?:\/\//.test(source.url || ""));
  if (!pages.length) return null;
  const fold = document.createElement("details");
  fold.className = "agent-step web-fold";
  const summary = document.createElement("summary");
  summary.className = "fold-summary";
  const first = pages[0];
  const site = first.domain || sourceHost(first.url);
  setLabel(
    summary,
    read
      ? `ph:file-text Read ${site || "a page"}: ${first.title && first.title !== first.url ? first.title : sourceHost(first.url) || first.url}`
      : `ph:globe Web results: ${pages.length} ${pages.length === 1 ? "page" : "pages"}`
  );
  const list = document.createElement("ol");
  list.className = "web-results-list";
  list.setAttribute("aria-label", "Web pages read for this answer");
  const reader = document.createElement("div");
  reader.className = "web-reader hidden";
  for (const source of pages) {
    const item = document.createElement("li");
    item.className = "web-result-card";
    const tile = document.createElement("span");
    tile.className = "web-result-tile";
    setLabel(tile, "ph:globe");
    tile.setAttribute("aria-hidden", "true");
    const body = document.createElement("div");
    body.className = "web-result-body";
    const head = document.createElement("div");
    head.className = "web-result-head";
    const title = document.createElement("button");
    title.type = "button";
    title.className = "linklike web-result-title card-open";
    title.textContent = source.title || source.domain || sourceHost(source.url);
    title.title = "Read this page here";
    title.addEventListener("click", () => readWebPage(fold, list, reader, source));
    const open = document.createElement("a");
    open.className = "ghost icon-only small web-result-open";
    open.href = source.url;
    open.target = "_blank";
    open.rel = "noopener noreferrer";
    open.setAttribute("aria-label", `Open ${source.domain || sourceHost(source.url) || "the page"} in the browser`);
    open.title = "Open in the browser";
    setLabel(open, "ph:arrow-square-out");
    head.append(title, open);
    const where = document.createElement("span");
    where.className = "muted web-result-site";
    where.textContent = source.domain || sourceHost(source.url);
    body.append(head, where);
    if (source.snippet) {
      const line = document.createElement("p");
      line.className = "muted web-result-line";
      line.textContent = source.snippet;
      body.appendChild(line);
    }
    item.append(tile, body);
    list.appendChild(item);
  }
  fold.append(summary, list, reader);
  if (read) {
    list.classList.add("hidden");
    fold.addEventListener("toggle", () => {
      if (fold.open && !reader.childElementCount) readWebPage(fold, list, reader, first, { back: false });
    });
  }
  holder.appendChild(fold);
  return fold;
}

//: **A result read in place** (decision 66; INBOX 1300 C06: "a dropdown that
//: opens a semi large panel with the extracted and formatted contents inside
//: as well as a link and data"): the page's readable blocks as Markdown
//: (`webPageMarkdown`, the reader's own), never its markup; over them its
//: title, its address as a link, and one facts line (site, words, minutes to
//: read, when it was read).
async function readWebPage(fold, list, reader, source, { back: withBack = true } = {}) {
  fold.open = true;
  list.classList.add("hidden");
  reader.classList.remove("hidden");
  const parts = [];
  if (withBack) {
    const back = document.createElement("button");
    back.type = "button";
    back.className = "ghost small web-reader-back";
    setLabel(back, "ph:arrow-left Back to results");
    back.addEventListener("click", () => {
      reader.classList.add("hidden");
      reader.replaceChildren();
      list.classList.remove("hidden");
    });
    parts.push(back);
  }
  const status = document.createElement("p");
  status.className = "muted";
  status.textContent = `Reading ${source.domain || sourceHost(source.url) || "the page"}`;
  reader.replaceChildren(...parts, status);
  try {
    const page = await apiJson(`/websearch/read?url=${encodeURIComponent(source.url)}`);
    const title = document.createElement("h4");
    title.className = "web-reader-title";
    title.textContent = page.title || source.title || source.domain;
    const where = document.createElement("p");
    where.className = "muted web-reader-where";
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = page.url || source.url;
    where.appendChild(link);
    const at = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const facts = document.createElement("p");
    facts.className = "library-file-meta web-reader-facts";
    const said = [page.domain || sourceHost(page.url || source.url)];
    if (page.words) said.push(`${Number(page.words).toLocaleString()} words`);
    if (page.read_minutes) said.push(`${page.read_minutes} min read`);
    said.push(`read at ${at}`);
    facts.textContent = said.filter(Boolean).join(" · ");
    const body = document.createElement("div");
    body.className = "web-reader-text";
    const markdown = webPageMarkdown(page);
    if (markdown) renderMarkdown(body, markdown);
    else {
      for (const block of String(page.text || "").split(/\n{2,}/).filter((b) => b.trim())) {
        const para = document.createElement("p");
        para.textContent = block.trim();
        body.appendChild(para);
      }
    }
    status.replaceWith(title, where, facts, body);
  } catch (error) {
    status.textContent = error.message;
  }
}

//: **The answer's shape follows its kind** (CHAT_PLAN decision 71): a count
//: leads with its number drawn large (`.digest-figure`), and a who answer
//: is a card (`.digest-card`: the person's name over what the notes say).
//: A comparison is a table and what is left a checklist already, in the
//: Markdown the answer arrives as; the table is set to fit and read in the
//: body's type (`.digest-table`), not the model table's export bar. Built from the text, so the citation
//: marks inside it keep their places.
function digestShape(answerEl, shape, figureText) {
  if (!answerEl) return;
  const first = answerEl.querySelector("p");
  if (shape === "count" && first && first.firstChild?.nodeType === Node.TEXT_NODE) {
    //: The figure is the server's reading (`_lead_figure`, through the one
    //: reader of units, CHAT_PLAN decision 46): found here by its text.
    const lead = first.firstChild;
    const at = figureText ? lead.textContent.indexOf(figureText) : -1;
    if (at < 0 || at > 14) return;
    const rest = lead.splitText(at);
    rest.splitText(figureText.length);
    const figure = document.createElement("span");
    figure.className = "digest-figure";
    figure.textContent = rest.textContent;
    rest.replaceWith(figure);
  } else if (shape === "who" && first) {
    const name = (first.textContent.match(/^([A-Z][\w'-]*(?: [A-Z][\w'-]*)?) /) || [])[1];
    if (!name) return;
    const card = document.createElement("div");
    card.className = "digest-card";
    const head = document.createElement("div");
    head.className = "digest-card-head";
    setLabel(head, `ph:user ${name}`);
    const offer = answerEl.querySelector("p:last-of-type");
    const body = [...answerEl.children].filter((el) => el.tagName === "P" && !(el === offer && el.textContent.trim().endsWith("?")));
    first.before(card);
    card.append(head, ...body);
  } else if (shape === "compare") {
    const block = answerEl.querySelector(".md-table-block");
    if (!block) return;
    block.classList.add("digest-table");
    block.dataset.tableView = "fit";
  }
}

//: **Short by default, More expands** (CHAT_PLAN B5): the lines past the
//: short answer arrive cited and are folded here behind one plain-tier
//: "Show five more", found by the bold label each opens with (the server's
//: `support.more.labels`), so the marks inside them keep their numbers.
//: Pressed, they show and the button stays (focus with it), reading "Show fewer".
function digestMore(answerEl, more) {
  if (!answerEl || !more) return;
  const wanted = new Set((more.labels || []).map((l) => `${l}:`));
  //: A line said as prose has no bold label: found by the words it opens with.
  const starts = (more.starts || []).filter(Boolean);
  if (!wanted.size && !starts.length) return;
  const folded = [...answerEl.querySelectorAll(":scope > p")].filter((p) => {
    const lead = p.firstElementChild;
    if (lead && lead.tagName === "STRONG" && p.firstChild === lead && wanted.has(lead.textContent.trim())) return true;
    const said = p.textContent.replace(/\s+/g, " ").trim();
    return starts.some((start) => said.startsWith(start));
  });
  if (!folded.length) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "linklike digest-more";
  setLabel(button, `ph:caret-down ${more.label}`);
  button.setAttribute("aria-expanded", "false");
  for (const p of folded) p.hidden = true;
  folded[0].before(button);
  //: The button stays and toggles (INBOX 1767 a): it kept focus, so no folded
  //: line (the "More loosely related" label, say) takes a ring it never had.
  button.addEventListener("click", () => {
    const open = button.getAttribute("aria-expanded") !== "true";
    for (const p of folded) p.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    setLabel(button, open ? "ph:caret-up Show fewer" : `ph:caret-down ${more.label}`);
  });
}

//: The digest's one offer (CHAT_PLAN decision 70, B12): its last line, a
//: question the answer asks ("Remind you to ask the tutor on Thursday?"),
//: made the button that does it. Plain tier (`.linklike`): an action in
//: running text. A reminder goes through the same door Quick add uses
//: (`/reminders/parse`, rules first, the person's clock); a checklist or a
//: note is a new note. Each one says what it did, with Undo.
//: A call's asks ("yo brotato", `vocative.py`), waiting for the Ask box's
//: follow-on strip, which is drawn just after the offer.
let askOfferAsks = null;

function digestOffer(answerEl, offer) {
  //: An "ask" offer is what to say next: the follow-on chips draw it, in
  //: Chat on the answer's own bubble (kept with the turn), in Ask next.
  if (offer?.kind === "ask") {
    const bubble = answerEl?.closest(".msg.assistant");
    if (bubble) {
      //: Drawn now, saved by `offerFollowups` once the turn is saved: a write
      //: here raced the turn's save and emptied the reply (INBOX 1300 C42).
      renderFollowups(bubble, offer.asks);
    } else askOfferAsks = offer.asks;
    return;
  }
  if (!answerEl || !offer || !offer.label) return;
  //: A choice ("That could be Export or Export chat. Which one?") is one
  //: offer a line, each its own link (`find_it.answer`).
  for (const other of offer.also || []) digestOffer(answerEl, other);
  const line = [...answerEl.querySelectorAll("p")].reverse().find((p) => p.textContent.trim() === (offer.line || offer.label));
  if (!line) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "linklike digest-offer";
  button.dataset.surface = offer.surface || "";
  button.textContent = offer.label;
  if (offer.state && offer.state !== "pending") {
    line.textContent = offer.notice || offer.summary || "Done.";
    return void line.classList.add("muted");
  }
  button.addEventListener("click", async () => {
    button.disabled = true;
    if (offer.offer_id && chatHistoryToSend.heldOffer === offer.offer_id) chatHistoryToSend.heldOffer = ""; // pressed: a later yes must not make it twice
    try {
      let undo = null;
      let redo = null;
      let said = "";
      let label = "";
      if (offer.kind === "open") {
        //: A page, not a thing made: nothing to undo, and the line stays.
        //: "settings:tasks" opens that section; "ask-history" the panel
        //: beside the Ask box (A3's records answers).
        //: "reveal:<key>[:<arg>]" lands on one control and rings it, the way
        //: a Tools and features row does (`revealFeature`); "tab:<tab>" is a tab.
        if (offer.surface.startsWith("reveal:")) revealFeature(...offer.surface.slice(7).split(":"));
        else if (offer.surface.startsWith("tab:")) switchTab(offer.surface.slice(4));
        else if (offer.surface === "statistics") openStatistics();
        else if (offer.surface === "ask-history") { if (!askHistoryOpen) toggleAskHistoryPanel(); }
        else if (offer.surface.startsWith("settings:")) openSettingsModal(offer.surface.slice("settings:".length));
        else if (offer.surface === "web-panel") toggleWebPanel(true);
        else actNavigate(offer.surface);
        button.disabled = false;
        return;
      }
      if (offer.kind === "searxng-start") {
        //: The search service a web search needed (INBOX 1490): started
        //: through the door Settings uses, which also points web search at it.
        //: The line says what happened; the buttons beside it stay.
        try {
          await ensureModule("webClip");
          const body = await startSearxng(true, (text) => { line.textContent = text; });
          line.textContent = `SearXNG is running at ${body.url}. Ask again and web search will use it.`;
          line.classList.add("muted");
        } catch (error) {
          line.replaceChildren(button);
          button.disabled = false;
          toast(error.message, true);
        }
        return;
      }
      if (offer.kind === "reminder") {
        const made = await apiJson("/reminders/parse", {
          method: "POST",
          body: JSON.stringify({ text: offer.text, tz_offset_minutes: -new Date().getTimezoneOffset() }),
        });
        const repeats = { daily: ", then every day", weekly: ", then every week", monthly: ", then every month" }[made.recurring] || "";
        said = `Reminder set: ${made.text}, ${relativeWhen(made.due_at)}${repeats}.`;
        label = "Set a reminder from an answer";
        const repaint = () => loadReminders();
        undo = () => apiJson(`/reminders/${made.id}`, { method: "DELETE" }).then(repaint);
        redo = () => apiJson(`/reminders/${made.id}/restore`, { method: "POST" }).then(repaint);
        repaint();
      } else if (offer.kind === "checklist" || offer.kind === "note") {
        const items = (offer.items || []).map((item) => `- [ ] ${item}`).join("\n");
        const content = offer.kind === "checklist" ? `${offer.text}\n\n${items}` : offer.text;
        const made = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content, defer_filing: true }) });
        said = `Saved a note: ${noteNamePlain(offer.text, 80)}.`;
        label = "Saved a note from an answer";
        undo = () => apiJson(`/entries/${made.id}`, { method: "DELETE" }).then(() => refreshEntries([made.id]));
        redo = () => apiJson(`/entries/${made.id}/restore`, { method: "POST" }).then(() => refreshEntries([made.id]));
        refreshEntries([made.id]).catch(() => {});
      }
      line.textContent = said;
      line.classList.add("muted");
      chatHistoryToSend.settle(line, offer, "done", { summary: said });
      if (undo) {
        offerUndo(
          label,
          said,
          async () => {
            await undo();
            chatHistoryToSend.settle(line, offer, "undone");
            line.replaceChildren(button);
            line.classList.remove("muted");
            button.disabled = false;
          },
          async () => {
            await redo();
            chatHistoryToSend.settle(line, offer, "done", { summary: said });
            line.textContent = said;
            line.classList.add("muted");
          }
        );
      }
    } catch (error) {
      button.disabled = false;
      toast(error.message, true);
    }
  });
  line.replaceChildren(button);
}

//: **Wrong fact and Pin as true on a cited line** (CHAT_PLAN B31, B32): the
//: one verdict pair (`insightLine`, DESIGN.md), sent for each sentence of
//: the note the line was made from. Not right leaves them out of every
//: answer from the next turn on; Confirm pins them, said as the person's
//: own word with the day. Each is a learned row, so the undo is its Delete.
function citationVerdictRow(source, content) {
  const parts = (source.parts || []).length
    ? source.parts
    : [{ note_id: source.noteId, source: String(content || "").slice(source.start, source.end), start: source.start, end: source.end }];
  const usable = parts.filter((part) => Number.isInteger(part.note_id) && Number.isInteger(part.start) && part.end > part.start && part.source);
  if (!usable.length || usable.length !== parts.length) return null;
  const send = async (_line, verdict) => {
    const kind = verdict === "confirm" ? "pinned" : "wrong";
    const ids = [];
    for (const part of usable) {
      const made = await apiJson("/learned/verdict", {
        method: "POST",
        body: JSON.stringify({ verdict: kind, note_id: part.note_id, sentence: part.source, start: part.start, end: part.end, line: source.line || "" }),
      });
      ids.push(made.id);
    }
    offerUndo(
      kind === "pinned" ? "Pinned a line as true" : "Marked a line wrong",
      kind === "pinned" ? "Pinned: your answers say it as your word from now on." : "Marked wrong: your answers leave it out from now on.",
      () => Promise.all(ids.map((id) => api(`/learned/${id}`, { method: "DELETE" }))),
      () => Promise.all(ids.map((id) => api(`/learned/${id}/restore`, { method: "POST" })))
    );
    return { kind };
  };
  return insightLine({}, "Is this line right?", (row, verdict) => {
    row.textContent = verdict === "confirmed" ? "Pinned as true." : "Marked wrong.";
  }, "muted citation-peek-verdicts", send);
}

function askAnswerMenu() {
  const slot = $("ask-answer-more");
  if (!slot || slot.firstChild) return;
  slot.appendChild(
    kebabMenu(
      [
        {
          label: "ph:note-pencil Save as a note",
          title: "Keep this answer as a new note",
          run: () => askKept && saveSelectionAsNote(askKept.text),
        },
        {
          label: "ph:file-text Save as a document",
          title: "Keep this answer in Documents, titled with the question",
          run: () => askKeepAsDocument(),
        },
        {
          label: "ph:graph Make a mind map of its notes",
          title: "A mind map of the notes this answer cites",
          run: () => askKeepAsMap(),
        },
      ],
      "More ways to keep this answer"
    )
  );
}

function askKeptTitle() {
  const question = (askKept?.question || "Answer").replace(/[?.!\s]+$/, "").trim();
  return question.slice(0, 1).toUpperCase() + question.slice(1, 100);
}

async function askKeepAsDocument() {
  if (!askKept?.text) return toast("There is no answer to keep yet.");
  const title = askKeptTitle();
  try {
    const doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title, content: `# ${title}\n\n${askKept.text}\n` }),
    });
    pushUndo(
      "Saved an answer as a document",
      () => api(`/documents/${doc.id}`, { method: "DELETE" }),
      () => api(`/documents/${doc.id}/restore`, { method: "POST" })
    );
    toastAction("Saved to your documents.", "Open it", () => {
      switchTab("documents");
      openDocument(doc.id);
    }, { go: { open: "doc", id: doc.id } });
  } catch (error) {
    toast(error.message || "Couldn't save that document.", true);
  }
}

async function askKeepAsMap() {
  const ids = askKept?.noteIds || [];
  if (!ids.length) return toast("This answer cites no notes to map.");
  const name = askKeptTitle();
  const board = await apiJson("/whiteboard/maps/from-notes", {
    method: "POST",
    body: JSON.stringify({ name, note_ids: ids }),
  }).catch((error) => toast(error.message || "Couldn't make the map.", true));
  if (!board?.id) return;
  pushUndo(
    "Made a mind map from an answer",
    () => api(`/entries/${board.id}`, { method: "DELETE" }),
    () => api(`/entries/${board.id}/restore`, { method: "POST" })
  );
  toastAction(
    `Mind map \u201c${name}\u201d made from ${nounCount(ids.length, "note")}.`,
    "Open",
    async () => {
      await openWhiteboardBoard(board.id);
      await wbMapTidyFresh();
    },
    { go: { open: "board", id: board.id } }
  );
}

//: Each line an answer volunteered (CHAT_PLAN decision 73) carries Confirm
//: and Not right, as in Chat: one row each, under the answer.
function renderAskInsights(found) {
  const holder = $("ask-insights");
  if (!holder) return;
  holder.replaceChildren();
  const open = (found || []).filter((insight) => !insight.confirmed);
  holder.classList.toggle("hidden", !open.length);
  for (const insight of open) {
    holder.appendChild(
      //: Said in the answer already (the owner, 2026-10-11: say it once):
      //: the row only asks whether it is right.
      insightLine(insight, insight.in_answer ? (insight.rule === "drift" ? "Is that open plan right?" : "Is that pattern right?") : `Pattern: ${insight.short}.`, (row, verdict, result) => {
        row.textContent = verdict === "confirmed" ? `Confirmed: ${result.line}` : verdict === "done" ? "Marked done" : "Not right: it will not be shown again.";
      }, "muted")
    );
  }
  if (open.length) $("ask-answer-foot")?.classList.remove("hidden");
}

//: **Why this answer** (CHAT_PLAN B30, INBOX 805): how the answer was made,
//: as a job's lines (what the question was read as, what was searched and
//: matched, who wrote it and in what shape, what it cited, how long it
//: took), each stamped with the seconds since the question. Folded under
//: the answer in the Thinking fold's look (`.why-fold`), shut until wanted.
//: Chat's bubble and the popup agent's draw the same fold (`drawWhyTrail`).
function renderAskWhy(lines, holder = $("ask-why")) {
  if (!holder) return;
  holder.replaceChildren();
  holder.classList.toggle("hidden", !(lines || []).length);
  if (!(lines || []).length) return;
  const fold = document.createElement("details");
  fold.className = "agent-step why-fold";
  const summary = document.createElement("summary");
  summary.className = "fold-summary";
  setLabel(summary, "ph:path Why this answer");
  const list = document.createElement("ol");
  list.className = "why-lines";
  list.setAttribute("aria-label", "How this answer was made");
  for (const line of lines) {
    const item = document.createElement("li");
    const at = document.createElement("span");
    at.className = "why-at";
    at.textContent = `${Number(line.at || 0).toFixed(2)} s`;
    const text = document.createElement("span");
    text.textContent = line.text || "";
    item.append(at, text);
    list.appendChild(item);
  }
  fold.append(summary, list);
  holder.appendChild(fold);
  holder.closest("#ask-answer-foot")?.classList.remove("hidden");
}

//: The same fold under a Chat bubble or a popup agent's answer: a holder
//: placed in `parent` (before `before`), filled by `renderAskWhy`.
function drawWhyTrail(parent, lines, before = null) {
  if (!(lines || []).length) return;
  const holder = document.createElement("div");
  holder.className = "why-trail";
  parent.insertBefore(holder, before);
  renderAskWhy(lines, holder);
}

//: **A follow-on is a question that keeps the answer above it** (decision 8:
//: "'Ask again' chips become follow-ups that carry the previous answer as
//: context"). The chips themselves are `/chat/followups`, the same second
//: model call the Chat tab makes after a turn is on screen, and clicking one
//: calls `askQuestion`, which sends `conversation` as history: so the context
//: is carried by the path every Ask turn already takes, not by a second one
//: built for chips.
//:
//: Silent on every failure, including the AI not running: an answer that
//: arrived is not made worse by having nothing to offer after it.
async function renderAskFollowups(question, answer, given = null) {
  const strip = $("ask-followups");
  if (!strip) return;
  given = given || askOfferAsks;
  askOfferAsks = null;
  strip.replaceChildren();
  strip.classList.add("hidden");
  if (!question || !answer) return;
  //: `given`: a composed answer's own next questions, already in hand.
  let picks = given || [];
  if (!given) {
    try {
      picks = await apiJson("/chat/followups", {
        method: "POST",
        silent: true,
        body: JSON.stringify({ question: clipFor("followQuestion", question), answer: clipFor("followAnswer", answer) }),
      });
    } catch {
      return;
    }
  }
  if (!Array.isArray(picks) || !picks.length) return;
  const label = document.createElement("span");
  label.className = "muted answer-grounding-label";
  label.textContent = "Ask next:";
  strip.appendChild(label);
  for (const pick of picks) {
    //: The hint is the chip's title; `chip`'s second argument is its class,
    //: and the sentence once went there, as seven class names.
    const next = chip(pick, "", () => {
      askTrailPending = [...askTrail, conversation.length - 1];
      $("question").value = pick;
      askQuestion(pick);
    });
    next.title = "Ask this next, keeping the answer above as context";
    strip.appendChild(next);
  }
  strip.classList.remove("hidden");
  $("ask-answer-foot")?.classList.remove("hidden");
}

//: **Both answers, one question** (K26, the owner: "if the ai is running then
//: the user can see both the ai and composer response"). Called after every
//: Ask turn. A model's answer gets (1) a card above it when the composer had
//: something to say first (`panel: "pre_answer"`: the personal digest, a place in the
//: app), never in place of the text, and (2) a "From your notes" fold under
//: it: one press fetches the composed answer for the same question
//: (`peek`, so Ask history does not keep it as a second turn), opened and
//: shut again without a second fetch. A composed, counted or hinted answer
//: has no model text to set it beside, so nothing is drawn.
function renderAskBoth(question, meta, panels) {
  const pre = panels.find((event) => event.panel === "pre_answer");
  const cardHost = $("ask-pre");
  const foldHost = $("ask-notes");
  cardHost?.replaceChildren();
  foldHost?.replaceChildren();
  if (!meta || meta.composed || !meta.answered_by) return;
  if (pre && cardHost) cardHost.appendChild(askPreAnswerCard(pre));
  if (foldHost) foldHost.appendChild(askFromNotesFold(question, conversation.slice(-MAX_CLIENT_HISTORY - 1, -1)));
}

function askPreAnswerCard(pre) {
  const card = document.createElement("div");
  card.className = "ask-pre-answer answer answer-composed";
  const body = document.createElement("div");
  renderMarkdown(body, pre.text || "");
  card.appendChild(body);
  if (pre.offer) digestOffer(body, pre.offer);
  return card;
}

function askFromNotesFold(question, history) {
  const fold = document.createElement("details");
  fold.className = "agent-step web-fold from-notes-fold";
  const summary = document.createElement("summary");
  summary.className = "fold-summary";
  setLabel(summary, "ph:note From your notes");
  summary.title = "The answer quoted from your notes, with no AI";
  const body = document.createElement("div");
  body.className = "answer answer-composed from-notes-body";
  fold.append(summary, body);
  let fetched = false;
  fold.addEventListener("toggle", () => {
    if (!fold.open || fetched) return;
    fetched = true;
    fetchComposedPeek(question, history, body);
  });
  return fold;
}

async function fetchComposedPeek(question, history, body) {
  setLabel(body, "ph:spin Reading your notes…");
  let text = "";
  try {
    await streamChatEvents({
      //: Clipped: the peek is a second read of the same question, and the
      //: server searches the first 4,000 characters of it either way.
      question: clipFor("question", question),
      history,
      notesOnly: true,
      peek: true,
      useTools: false,
      onMeta: () => {},
      onAnswer: (delta) => {
        text += delta;
      },
    });
    renderMarkdown(body, text || "Nothing in your notes answers this.");
    body.classList.toggle("muted", !text);
  } catch (error) {
    body.textContent = "Couldn't read your notes just now.";
    body.closest("details").dataset.failed = "1";
  }
}

async function askQuestion(preset) {
  const status = $("ask-status");
  const questionBox = $("question");

  const question = (preset ?? questionBox.value).trim();
  if (!question) {
    //: Sentence case and no exclamation mark: DESIGN.md's copy rule, and
    //: `tests/test_no_em_dashes.py`'s neighbour rules exist because this one
    //: kept coming back.
    askStatusText("Type a question first.");
    status.classList.add("error");
    return;
  }
  //: A chip's question takes its parent's chain plus the parent; asking the
  //: same question again (Retry) keeps the chain; anything typed starts afresh.
  if (askTrailPending) askTrail = askTrailPending;
  else if (question !== lastQuestion) askTrail = [];
  askTrailPending = null;
  renderAskTrail();
  lastQuestion = question;
  //: A chip, a follow-on or Retry asks without typing: the box shows it
  //: anyway (K29, "I forgot instantly"), the one place the question is said;
  //: a "You asked:" line above the answer said it twice (INBOX 1301).
  if (preset != null) questionBox.value = question;

  // A new answer is coming, hide the suggestion/recent chips and the
  // per-answer action buttons until it lands.
  $("suggested-questions").classList.add("hidden");
  hide("copy-btn", "speak-btn", "ask-answer-more");
  //: Regenerate stays and shows the ring while it runs (INBOX 1423).
  const retryBtn = $("retry-btn");
  if (!retryBtn.classList.contains("hidden")) setBusy(retryBtn, true, "");
  askKept = null;
  setAsking(true);
  status.classList.remove("error");
  // Reset the output areas for the new answer.
  const answerBox = $("ai-answer");
  const thinkingHost = $("thinking-box");
  const thinkingBox = thinkingFoldIn(thinkingHost);
  const thinkingText = thinkingBox.querySelector(".thinking");
  answerBox.textContent = "";
  $("ask-pre").textContent = $("ask-notes").textContent = "";
  //: A counting or trend question gets its chart beside the answer
  //: (WORLD_CLASS_PLAN section 17 row 4): asked in parallel, from the
  //: records, so it lands whether or not the model answers.
  const chartHost = $("ask-chart");
  if (chartHost) {
    chartHost.replaceChildren();
    chartHost.classList.add("hidden");
    delete chartHost.dataset.streamed;
    //: A chart the answer's own stream drew (`onChart` below) is not wiped by
    //: the parallel fetch coming back empty (L-chat-60).
    if (question.length <= 500) ensureModule("askHistory").then(() => renderAskChart(question, chartHost, () => lastQuestion === question && !chartHost.dataset.streamed)).catch(() => {});
  }
  //: After the reset, not before it: the progress line lives inside the
  //: answer box now, so creating it first would only have it wiped.
  //: No words of its own: `streamChat` drives the phase line from the events
  //: (INBOX 649), "Reaching Atlas…" until the server says it is searching.
  const progress = askStatusBusy(null);
  //: **The wait is on screen** (INBOX 727, the owner: "there's no searching
  //: animation or indicator for when I enter a search in the ask tab and
  //: nothing has shown yet"). The phase line was drawn inside a results grid
  //: still hidden until the first event (measured: 0x0 for the whole wait),
  //: so the grid opens now, the records column saying it is searching until
  //: `onMeta` replaces the row.
  const searching = document.createElement("li");
  searching.className = "muted";
  setLabel(searching, "ph:spin Searching your notes…");
  $("raw-results").replaceChildren(searching);
  document.querySelector(".chat-half:last-child")?.classList.remove("hidden");
  $("chat-results").classList.remove("hidden");
  $("ask-idle")?.classList.add("hidden");
  $("ai-answer-grounding").replaceChildren();
  $("ai-answer-grounding").classList.add("hidden");
  //: The whole foot goes with it, not only the grounding chips: a sources
  //: disclosure still expanded from the previous question is a list of notes that
  //: have nothing to do with the one being asked.
  clearAskAnswerFoot();
  thinkingText.textContent = "";
  thinkingBox.thinkingRaw = "";
  thinkingHost.classList.add("hidden");
  thinkingBox.open = false;

  //: **On before the request, off in the `finally`.** The ring marks the
  //: thing producing the output for as long as it is being produced: added on
  //: the first token instead, it says nothing during the wait that is the
  //: part actually worth marking, which is the Chat tab's own recorded bug
  //: one surface over.
  answerBox.classList.add("is-generating");
  let answerRaw = "";
  let stopped = false;
  let groundingRawResults = []; // set by onMeta, read by onGrounding
  let groundedSupport = null; // how much of the answer the notes backed
  let groundedInsights = []; // the lines it volunteered (decision 73)
  let answerWhy = []; // how it was made (B30)
  let answerOffer = null; // a counted answer's offer (decision 70)
  let answerTip = ""; // the pick-up line, under the answer as in Chat (audit 1028 E52)
  const answerPanels = []; // the app's panels under the answer (INBOX 1300 C06)
  let composedNext = []; // a composed answer's own next questions (INBOX 725)
  let turnFrame = null; // what the composed answer showed, echoed with the next turn
  //: Kept beyond the callback that receives them, because the answer element
  //: is rebuilt after the stream ends and the markers have to be put back.
  let groundedSentences = [];
  //: Kept for the same reason: the answer object (CHAT_PLAN decision 3) is
  //: built once, after the stream, from every event the turn produced, and
  //: three of those events arrive long before the last token.
  let relatedItems = [];
  let answerStats = null;
  let answerMeta = null;
  // The box explained itself instead of answering, so the final markdown
  // pass, the saved turn and the answer actions all sit this one out.
  let hinted = false;
  //: **Numbered while it streams** (INBOX 320, the owner: "the numbers only
  //: appear after the ai response is finished"). The backend now grounds each
  //: sentence as it completes and sends the rows so far (`grounding_live`);
  //: the records column is numbered from them at once, and the markers are
  //: put back into the prose after every live paint, which rebuilds it. The
  //: numbering is the same `citationNumbers` over the same source order the
  //: finished answer uses (`chatSourcesFrom` over this turn's meta), so a
  //: digit that appears mid-answer is the digit it keeps.
  let liveSources = null;
  const placeLiveCitations = () => {
    if (groundedSentences.length) {
      addInlineCitations(answerBox, groundedSentences, groundingRawResults, liveSources);
    }
  };
  const renderLive = liveMarkdownRenderer(answerBox, placeLiveCitations);
  askController = new AbortController();
  try {
    // Stream: raw results arrive first, then thinking/answer tokens live.
    await streamChat({
      progress,
      question,
      history: conversation.slice(-MAX_CLIENT_HISTORY),
      // Sent per turn now that this box has its own picker. It always obeyed
      // the *saved* mode via the server's fallback; carrying it explicitly is
      // what makes changing the box's dropdown affect the very next answer
      // rather than only the one after the preference round-trips.
      mode: $("ask-mode-select")?.value || null,
      useTools: false, // the quick-ask box is pure Q&A; actions live in the Chat tab
      // This box interrogates the notebook and nothing else (§35A). Sent as a
      // flag rather than left to the classifier, which is right about "hey"
      // being small talk: it is this surface that doesn't want small talk.
      notesOnly: true,
      scope: askScope || null,
      asOf: askAsOf(),
      signal: askController.signal,
      onMeta: (meta) => {
        renderChatMeta(meta);
        answerMeta = meta;
        groundingRawResults = meta.raw_results || [];
      },
      onThinking: (delta) => {
        //: Only a stray placeholder, never the progress line itself: that is
        //: the thing saying what is happening, and it stays until the first
        //: answer token replaces it.
        for (const stray of answerBox.querySelectorAll(".typing-dots, .typing-label")) {
          if (!progress || !progress.contains(stray)) stray.remove();
        }
        // Auto-expand while the model reasons (user request).
        thinkingHost.classList.remove("hidden");
        thinkingBox.open = true;
        thinkingBox.thinkingRaw = (thinkingBox.thinkingRaw || "") + delta;
        thinkingPaint(thinkingBox, thinkingBox.thinkingRaw); // follows the newest line
      },
      onAnswer: (delta) => {
        //: The first answer token is the moment "waiting" becomes "writing",
        //: so the indicator changes with it. `setPhase` is idempotent, so
        //: calling it on every delta costs nothing.
        answerBox.querySelector(".typing-dots")?.setPhase?.("writing");
        if (thinkingBox.open) thinkingBox.open = false; // reasoning done → tuck away
        answerRaw += delta;
        // Same caret the Chat tab's timeline gets, for the same reason, see
        // `.is-streaming` in 01-forms-settings.css. Set here rather than
        // before the request because the dots own the "nothing yet" state.
        answerBox.classList.add("is-streaming", "is-generating");
        renderLive(answerRaw); // markdown renders AS it streams (user request)
        //: The indicator's shape and words follow the stage (`streamChat`
        //: sets "writing" before this runs): a three-dot "thinking" animation
        //: beside the sentence "writing" is the mismatch reported of Chat.
        if (progress && progress.previousElementSibling !== answerBox) answerBox.after(progress);
      },
      onHint: (event) => {
        // Not an answer, so it does not go through the markdown renderer or
        // into the conversation: it is the box explaining itself.
        hinted = true;
        renderAskHint(answerBox, event);
        askStatusText("");
      },
      //: Collected, not drawn: it is a field of the answer object and is
      //: rendered with the rest of the foot once the stream is over. Drawing
      //: it here is what put it inside `#ai-answer-grounding`, which the
      //: grounding event then cleared out from under it.
      onRelated: (event) => {
        relatedItems = event.items || [];
      },
      onStats: (event) => {
        answerStats = event;
      },
      //: The server took a greeting or a sign-off off the answer, so the text
      //: on screen is not the text anything else will use. Repainted from the
      //: trimmed version, and `answerRaw` moves with it: the grounding markers
      //: placed a moment later are offsets into *this* string.
      onAnswerFinal: (event) => {
        answerRaw = event.text || answerRaw;
        renderLive(answerRaw);
      },
      onGroundingLive: (event) => {
        groundedSentences = event.sentences || [];
        liveSources = chatSourcesFrom({ meta: answerMeta, toolEvents: [], touched: [], sentences: groundedSentences });
        numberMatchingRecords(
          $("ai-answer-grounding"),
          citationNumbers(groundedSentences, liveSources)
        );
        placeLiveCitations();
      },
      onGrounding: (event) => {
        //: **Remembered here, drawn once at the end.** This used to draw the
        //: chips and the markers the moment the event arrived, which is
        //: before the answer has finished streaming and before the Sources
        //: panel exists. Both were then wrong in the way the owner reported:
        //: the markers were placed into prose that was still growing (and
        //: thrown away by the final markdown pass a moment later), and the
        //: chips were numbered with nothing to agree with, so the digits did
        //: not match the panel the foot drew underneath them.
        groundedSentences = event.sentences || [];
        //: Remembered with them and drawn in the same pass, for the same
        //: reason: the answer is still streaming when this arrives, so a
        //: notice placed now would sit above prose that is still growing.
        groundedSupport = event.support || null;
        groundedInsights = Array.isArray(event.insights) ? event.insights : [];
        composedNext = Array.isArray(event.next) ? event.next : [];
      },
      onFrame: (frame) => { turnFrame = frame || null; },
      onOffer: (event) => {
        answerOffer = event.offer || null;
      },
      onTip: (event) => { answerTip = event.text || ""; },
      //: Drawn with the foot, once the answer's text is final.
      onPanel: (event) => answerPanels.push(event),
      //: The chart a no-model answer made (a window's counts, a graph ask):
      //: the box above the answer, the same recipe Chat draws (L-chat-60).
      onChart: (event) => ensureModule("askHistory").then(() => {
        if (!chartHost || !event.chart) return;
        chartHost.dataset.streamed = "1";
        chartHost.classList.remove("hidden");
        drawAskChart(chartHost, event.chart);
      }),
      //: The web pages a composed answer read, as cards (decision 66), drawn
      //: with the panels for the same reason.
      onWebSources: (event) => answerPanels.push({ web: event.sources }),
      onWhy: (event) => {
        answerWhy = Array.isArray(event.lines) ? event.lines : [];
      },
    });

    //: **The live renderer's armed paint is cancelled before anything else**
    //: (`liveMarkdownRenderer`'s own `stop`, and the same call the Chat tab's
    //: `finalise` has made since INBOX 40). Reported as *"grounding and
    //: in-text referencing not working now"* and, more precisely, *"doesn't
    //: stick"*: measured, the markers were placed, all three of them, and a
    //: `setTimeout` armed up to `LIVE_RENDER_INTERVAL_MS` before the stream
    //: ended then fired and repainted this box from the raw markdown, which
    //: removes every one of them. The prose is identical either way, so
    //: nothing about it looks like a race; only the little numbers go.
    //:
    //: The Ask tab was the one caller of this renderer that never stopped it.
    //: The fix is the call, not a delay: a timer cancelled cannot fire late,
    //: whereas a longer wait only makes the race rarer.
    renderLive.stop();
    // Final render (catches anything after the last animation frame).
    if (!hinted) renderMarkdown(answerBox, answerRaw);
    //: **And the citations go back in.** Reported: *"in the ask tab, no inline
    //: or grounding links to the notes viewed and referenced appear."* The
    //: markers were being inserted, `onGrounding` fires during the stream and
    //: `addInlineCitations` writes them straight into the answer, and then
    //: the line above rebuilt the whole answer element from the raw markdown
    //: and threw every one of them away. The grounding event arrives *before*
    //: `done`, so this was true of every answer that had any: the feature ran,
    //: correctly, and its output survived for a few milliseconds.
    //:
    //: Applied once, here, rather than during the stream, because the live
    //: render is what makes the answer readable as it arrives and the markers
    //: simply have to be the last thing written, against the finished text.
    if (!hinted) {
      //: The notes this answer cited ride with the turn, as Chat's do, so
      //: "how much does it cost" after an Ask answer names what "it" was.
      conversation.push({ question, answer: answerRaw, objects: chatTurnObjects(liveSources), ...(turnFrame ? { frame: turnFrame } : {}) });
      show("retry-btn", "copy-btn", "speak-btn", "new-chat-btn");
      //: What the ⋯ keeps (B12): the answer as written, and the notes it cites.
      askKept = {
        question,
        text: answerRaw,
        noteIds: [...new Set(groundedSentences.map((row) => row.note_id).filter((id) => Number.isInteger(id)))],
      };
      ensureModule("askCompose").then(() => askAnswerMenu()).catch(() => {});
      show("ask-answer-more");
      //: **The answer object, rendered** (CHAT_PLAN Phase 3). Built after the
      //: stream rather than updated event by event, because two of its fields
      //: (the sentences and the sources they came from) are only complete when
      //: the last event has arrived, and a foot that rearranges itself under a
      //: reader mid-answer is worse than one that appears when the answer does.
      //: Built before the grounding is drawn rather than after, so the chips
      //: and the markers can be numbered from the panel's own list of sources
      //: (`citationNumbers`). The Chat tab has done this since the panel
      //: existed; the Ask tab numbered each of the three for itself, which is
      //: the "numbers wont match the grounding" that was reported.
      const answer = answerObject({
        question,
        text: answerRaw,
        grounding: groundedSentences,
        meta: answerMeta,
        related: relatedItems,
        stats: answerStats,
      });
      if (groundedSentences.length) {
        renderAnswerGrounding(
          $("ai-answer-grounding"),
          groundedSentences,
          groundingRawResults,
          answerBox,
          question,
          answer.sources,
          groundedSupport,
          answerMeta?.picture_alts || null
        );
      }
      placeAnswerFigures(answerBox, answerMeta, question);
      renderAskAnswerFoot(answer, answerMeta);
      ensureModule("askCompose").then(() => renderAskInsights(groundedInsights)).catch(() => {});
      ensureModule("askCompose").then(() => { renderAskWhy(answerWhy); renderAskBoth(question, answerMeta, answerPanels); }).catch(() => {});
      if (answerOffer) ensureModule("askCompose").then(() => digestOffer(answerBox, answerOffer)).catch(() => {});
      if (answerTip) answerBox.appendChild(Object.assign(document.createElement("p"), { className: "muted answer-tip", textContent: answerTip }));
      if (answerPanels.length) drawAnswerPanels(answerBox, answerPanels);
      //: `composed`, and `match_info` for each record's reason (INBOX 1310,
      //: `replyRecordCards`); only these, so a new meta key cannot steer it.
      finishReply(answerBox, { composed: answerMeta?.composed, match_info: answerMeta?.match_info });
      //: Not awaited: it is a second model call, and the answer is already on
      //: screen. The same contract `offerFollowups` has in the Chat tab. An
      //: answer composed from the notes brings its own (INBOX 725), built
      //: from what it found and did not say, and asks no model for them.
      const followups = () => renderAskFollowups(question, answerRaw, answerMeta?.composed ? composedNext : null);
      CLIP_LIMITS.afterAnswer(() => ensureModule("askCompose").then(followups).catch(() => {}).then(announceAskFoot));
    }
    askStatusText("");
    // Asking changes both quick-access lists, and, for a real (non-hint)
    // answer: the browsable history too. One frame after the answer's own.
    CLIP_LIMITS.afterAnswer(() => {
      loadRecentQuestions();
      loadMostUsed();
      if (!hinted) {
        loadAskHistoryBadge();
        if (askHistoryOpen) loadAskHistoryPage(true);
      }
    });
  } catch (error) {
    if (error.name === "AbortError") {
      stopped = true;
      //: Same reason as the success path above: Stop is an exit too, and an
      //: armed paint outlives the turn it belongs to.
      renderLive.stop();
      renderMarkdown(answerBox, answerRaw); // keep what streamed so far
      askStatusText("Stopped.");
      show("retry-btn", "copy-btn", "speak-btn");
    } else {
      askStatusText(error.message);
      status.classList.add("error");
    }
  } finally {
    // Every exit path, including Stop and an error: a caret still blinking on
    // an answer that stopped arriving is worse than never showing one.
    answerBox.classList.remove("is-streaming", "is-generating");
    progress?.remove();
    setBusy($("retry-btn"), false);
    askController = null;
    matchReasonBadge.reveal();
    setAsking(false);
    // The question used to be cleared here, which left an answer on screen with
    // nothing saying what it answered (user-reported). It stays in the box, 
    // ready to refine and re-ask, and is echoed above the answer so the pair
    // reads together even after you start typing the next one.
    if (!stopped) questionBox.select();
  }
}

function renderChatMeta(meta) {
  $("search-mode").textContent = SEARCH_MODE_LABELS[meta.search_mode] || meta.search_mode;
  // "offline" only when Ollama is genuinely down, not merely because a
  // question found nothing to answer from.
  //: A composed answer (INBOX 688) says so on the chip, and its card takes
  //: the quote style the composer's lead is drawn in (`.answer-composed`).
  $("ai-answer").classList.toggle("answer-composed", !!meta.composed);
  //: "Atlas" heads the answer; the chip says where it came from (CHAT_PLAN
  //: decision 36): "Atlas's assistant, from your notes" with no model, "Atlas, <model>" with one.
  if (meta.composed) setAnsweredBy("Atlas's assistant, from your notes", "Atlas's assistant answered from your notes, with no model: every sentence comes from a note");
  else if (meta.answered_by) setAnsweredBy(`Atlas, ${meta.answered_by}`, `Atlas answered with ${meta.answered_by}`);
  else if (meta.ollama_running === false) {
    setAnsweredBy("chat model offline", "The chat model is not running, so nothing answered this");
  } else setAnsweredBy("", "");
  const rawList = $("raw-results");
  rawList.replaceChildren();
  if (meta.raw_results.length === 0 && meta.search_mode === "none") {
    // Nothing was searched for, the message was not a question about the
    // notes. "No matching records" would report a failed search that never
    // happened, which is the half of the greeting case that read as broken.
    $("chat-results").classList.remove("hidden");
  $("ask-idle")?.classList.add("hidden");
    document.querySelector(".chat-half:last-child")?.classList.add("hidden");
    return;
  }
  document.querySelector(".chat-half:last-child")?.classList.remove("hidden");
  //: Under 600px Matching records is one closed row (INBOX 1843, 10-responsive.css).
  const fold = $("ask-records-fold");
  $("ask-records-count").textContent = String(meta.raw_results.length);
  if (!fold.dataset.wired) {
    fold.dataset.wired = "1";
    fold.addEventListener("click", () => fold.setAttribute("aria-expanded", String(fold.getAttribute("aria-expanded") !== "true")));
  }
  if (meta.search_mode === "outside_range" && meta.raw_results.length) {
    // Matched what was asked about, not when it was asked about, the note
    // is real, the stated time was just wrong (reported directly: a joke
    // asked about as "two weeks ago" that was actually three). Said before
    // the results, not folded silently into them, so this never reads as a
    // date-scoped answer it isn't.
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = meta.when_phrase
      ? `Nothing about this in “${meta.when_phrase}”: here's what matched from another time:`
      : "Nothing in that time range, here's what matched from another time:";
    rawList.appendChild(li);
  }
  if (meta.raw_results.length === 0) {
    const li = document.createElement("li");
    li.className = "muted";
    // A dated question that found nothing has *two* facts to report, and only
    // saying the first is what makes an empty result look like a broken
    // search: nothing matched, **and** the window you named is why it was
    // looking so narrowly. Naming the phrase is also the fastest route to the
    // fix, because the next thing to try is asking again without it.
    li.textContent =
      meta.search_mode === "dated" && meta.when_phrase
        ? `Nothing matching “${meta.when_phrase}”. Try asking without it.`
        : "No matching records.";
    rawList.appendChild(li);
  }
  // Notes that came along because they are *connected* to a match are labelled
  // as such. Without it the panel shows notes about something else with no
  // explanation, which reads as the search having misfired, and the whole
  // point of pulling them in is that the person can see the connection.
  const connected = new Set(meta.connected_ids || []);
  const matchInfo = meta.match_info || {};
  //: **A percentage on every card or on none** (INBOX 728, the owner: "how
  //: come only some of the ask tab matching records notes green arrows have %
  //: number similarity and others dont show a number??"). A row that came by
  //: recency or a date has no score; beside it a number on its neighbours
  //: read as a missing one. Then the chips keep their words and the number
  //: moves to the title.
  const scored = everyRowScored(meta.raw_results, matchInfo, connected);
  for (const entry of meta.raw_results) {
    const row = clickableResult(entry);
    const badge = matchReasonBadge(matchInfo[entry.id], scored);
    if (badge) {
      if (connected.has(entry.id)) row.classList.add("result-connected");
      if (matchInfo[entry.id]?.type === "connected_2hop") row.classList.add("result-connected-2hop");
      //: In the facts line, after the date, as one more quiet fact (INBOX
      //: 510): on a row of its own it was a filled pill louder than the note.
      placeResultBadge(row, badge);
    }
    rawList.appendChild(row);
  }
  //: The reference count is a fact the card draws from a cache the *note
  //: list* fills, so a result row rendered before that list has been opened
  //: had nowhere to read it from and drew nothing. The same patch-in the
  //: note list uses, pointed at this list: one implementation, and a second
  //: one is how the two would come to disagree about what "linked by" counts.
  ensureCardCounts(rawList, _entriesLoadGeneration);
  matchReasonBadge.hold(rawList);
  ensureModule("replyKit").then(() => replyRecordCards(rawList, meta.raw_results, matchInfo, scored)).then(() => matchReasonBadge.hold(rawList)).catch(() => {});
  $("chat-results").classList.remove("hidden");
  $("ask-idle")?.classList.add("hidden");
}

//: Returns the progress line itself, because the caller drives it: `setStatus`
//: for the words and `setPhase("writing")` for the moment the dots become the
//: writing trace. A fresh one per turn, since the component owns timers that
//: stop themselves when it leaves the page.
//: **The progress line belongs in the bubble it is filling** (the owner,
//: 2026-09-21): in `#ai-answer`, where the answer will appear, not in
//: `#ask-status` above the whole block, and with no second set of dots.
function askStatusBusy(text) {
  const box = $("ai-answer");
  if (!box) return null;
  $("ask-status")?.classList.remove("error");
  $("ask-status")?.replaceChildren();
  box.replaceChildren();
  //: No `persona` to pass: the Ask box has no persona picker of its own, it
  //: always answers in the notebook's own voice, so `thinkingWordsFor(null)`
  //: resolving to that default persona's list is already the right answer.
  const line = progressLine(text, { words: true });
  line.classList.add("ask-progress");
  box.appendChild(line);
  //: **And brought into view, because it is now further down the page than
  //: the old one was.** `#ask-status` sat directly under the question box, so
  //: it was always in sight; the answer bubble is below the asked question
  //: and below the thinking disclosure, which expands as the model reasons and
  //: pushes the bubble further down. Reported as "nothing happens except the
  //: send button changing to stop": the indicator was there and off screen,
  //: which is the same thing as not having one.
  requestAnimationFrame(() => {
    try {
      line.scrollIntoView({ block: "nearest", behavior: reducedMotionWanted() ? "auto" : "smooth" });
    } catch {
      //: An older engine without the options object still gets the default.
      line.scrollIntoView();
    }
  });
  return line;
}

// The Ask box's "that isn't a question about your notes" card (§35A).
//
// Deliberately not rendered as an answer. Reported after the first version:
// a paragraph of instructions where the answer goes, next to a results panel
// saying "No matching records", reads as the app having broken rather than as
// guidance. Here the examples are buttons, a way forward from the same place,
// which also teaches the shape of a question that works.
function renderAskHint(box, hint) {
  box.replaceChildren();
  const card = document.createElement("div");
  card.className = "ask-hint";
  const text = document.createElement("p");
  text.className = "ask-hint-text";
  text.textContent = hint.text;
  card.appendChild(text);
  const row = document.createElement("div");
  row.className = "row ask-hint-examples";
  for (const example of hint.examples || []) {
    row.appendChild(
      smallButton(example, `Ask: ${example}`, () => {
        $("question").value = example;
        askQuestion(example);
      })
    );
  }
  if (row.childElementCount) card.appendChild(row);
  box.appendChild(card);
}

//: **The answer and its foot are said aloud** (UX review 1031, M11): the box
//: has no live region, so nothing told a screen reader an answer, its related
//: notes, sources or follow-ups had arrived. Counts are of what is showing.
function announceAskFoot() {
  const shown = (selector) => [...document.querySelectorAll(selector)].filter((el) => !el.closest(".hidden")).length;
  const parts = [
    ["related note", shown("#ask-answer-related .answer-related-chip")],
    ["source", shown("#ask-answer-sources .chat-source-card")],
    ["suggested question", shown("#ask-followups .chip-interactive")],
  ].filter(([, count]) => count);
  announce(["Answer ready.", ...parts.map(([noun, count]) => `${nounCount(count, noun)}.`)].join(" "));
}

//: Time travel on Ask (WORLD_CLASS_PLAN I5, row 23): the day the next answer
//: reads the notebook as of, or null. Only while the line is showing, so
//: "Back to now" needs nothing else to undo.
function askAsOf() {
  const row = $("ask-as-of-row");
  const value = $("ask-as-of")?.value || "";
  return row && !row.classList.contains("hidden") && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}

//: **What the Ask tab shows while the model works** (INBOX 298: 250 of 250
//: streaming frames had nothing moving). The Chat tab's two components, not
//: a new control: `.is-generating` from before the request to its `finally`,
//: and one `progressLine` for the whole turn, returned so the caller drives
//: `setStatus` and `setPhase("writing")`; fresh per turn, its timers stop
//: themselves when it leaves the page.
function askStatusText(text = "") {
  const status = $("ask-status");
  if (!status) return null;
  status.replaceChildren();
  status.textContent = text;
  return status;
}

// Ask ⇄ Stop while a stream is in flight.
function setAsking(active) {
  $("ask-btn").classList.toggle("hidden", active);
  $("stop-btn").classList.toggle("hidden", !active);
  $("question").disabled = active;
}

//: **The trail above an Ask answer** (INBOX 490): the questions this one
//: followed on from, each a link (`followupTrail`, chat-attach.js) that opens
//: that earlier answer in place under the trail, since Ask shows one answer
//: at a time and there is no earlier turn on screen to scroll to.
function renderAskTrail() {
  const host = $("ask-trail");
  if (!host) return;
  const turns = askTrail.map((i) => conversation[i]).filter(Boolean);
  host.replaceChildren();
  host.classList.toggle("hidden", !turns.length);
  if (!turns.length) return;
  const peek = document.createElement("div");
  peek.className = "ask-trail-peek answer hidden";
  peek.id = "ask-trail-peek";
  let shown = -1;
  const trail = followupTrail(turns.map((turn) => turn.question), (i, link) => {
    shown = shown === i ? -1 : i;
    for (const other of trail.querySelectorAll(".chat-trail-link")) {
      other.setAttribute("aria-expanded", other === link && shown === i);
    }
    peek.classList.toggle("hidden", shown === -1);
    if (shown !== -1) renderMarkdown(peek, turns[i].answer || "");
  });
  for (const link of trail.querySelectorAll(".chat-trail-link")) {
    link.setAttribute("aria-expanded", "false");
    link.setAttribute("aria-controls", peek.id);
  }
  host.append(trail, peek);
}
