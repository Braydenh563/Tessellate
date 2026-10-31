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
  const box = $("ask-use-ai");
  if (!box || box.dataset.wired) return;
  box.dataset.wired = "1";
  box.addEventListener("change", () => {
    if (box.disabled) return;
    prefs.set(ASK_ANSWER_FROM_KEY, box.checked ? "ai" : "notes");
    renderAskUseAi();
  });
  //: **Following the model without a hook in the boot scripts.** The status
  //: poll redraws `#ask-offline` on every tick (`renderAiOfflineNotice`),
  //: showing it exactly when no model answers; watching it keeps the switch
  //: in step with the model starting and stopping, and rewrites the notice's
  //: sentence with the cause (its button already opens Settings, Models).
  const offline = $("ask-offline");
  if (offline) new MutationObserver(renderAskUseAi).observe(offline, { attributes: true, attributeFilter: ["class"], childList: true });
  renderAskUseAi();
}

wireAskUseAi();

//: **The name in "[**Dentist**]" opens the note** (the 2026-10-10 triage,
//: decision 5). An answer written without a model cites each note by its
//: title in square brackets (`composer.PHRASES["cite_open"]`), and the
//: grounding row carries that title (`title`), so the match is exact rather
//: than a guess from opening words. Hover or focus shows the citation peek
//: (capture-ask.js), the passage the sentence came from, as a numbered mark
//: does; a press or Enter goes to the note itself, never to the Sources
//: disclosure. The bold name itself is the control (a link role, focusable),
//: so the sentence reads and wraps as before and no stylesheet rule is
//: needed: the global `:focus-visible` ring and the peek are its states.
//: Called by `addInlineCitations` after every paint; a name already wired
//: carries `data-note-id` and is skipped.
function linkCitedTitles(targets, sentences, byId, numberFor) {
  const byTitle = new Map();
  for (const g of sentences || []) if (g.title && !byTitle.has(g.title)) byTitle.set(g.title, g);
  for (const target of targets) {
    for (const name of target.querySelectorAll("strong:not([data-note-id])")) {
      const g = byTitle.get(name.textContent.trim());
      //: "[**Dentist**]", or "[board **Harbor board**]" for a board, a map,
      //: a document or a file (CHAT_PLAN decision 37: the citation says its kind).
      const bracketed = /\[(?:board |map |document |file |page )?$/.test(name.previousSibling?.textContent || "") && /^\]/.test(name.nextSibling?.textContent || "");
      if (!g || !bracketed) continue;
      name.dataset.noteId = String(g.note_id);
      name.tabIndex = 0;
      name.setAttribute("role", "link");
      const kind = g.kind && g.kind !== "note" ? g.kind : "note";
      name.setAttribute("aria-label", `Open the ${kind === "map" ? "mind map" : kind} ${g.title}`);
      name.style.cursor = "pointer";
      const describe = () => ({
        noteId: g.note_id, number: numberFor.get(citeKey(g.kind, g.note_id)), entry: g.kind === "document" ? undefined : byId.get(g.note_id), label: g.label,
        start: g.start, end: g.end, signals: g.signals, verdict: g.verdict, terms: g.terms,
      });
      name.addEventListener("mouseenter", () => scheduleCitationPeek(name, describe));
      name.addEventListener("mouseleave", () => scheduleCitationPeekClose());
      name.addEventListener("focus", () => {
        if (!citationPeekState.restoring) openCitationPeek(name, describe(), { pinned: false });
      });
      name.addEventListener("blur", (event) => {
        if (!citationPeekState.panel?.contains(event.relatedTarget)) scheduleCitationPeekClose();
      });
      //: Each kind opens in its own place (INBOX 744): a document in the
      //: editor, a map or a board on its canvas, a file in the Library.
      const open = (event) => {
        event.stopPropagation();
        closeCitationPeek();
        if (kind === "document") openDocumentFromNote(g.note_id);
        else if (kind === "map" || kind === "board") openWhiteboardBoard(g.note_id);
        else if (kind === "file") focusLibraryFile(g.title, `/files/${g.note_id}`);
        else if (kind === "web" && /^https?:\/\//.test(g.url || "")) window.open(g.url, "_blank", "noopener");
        else flashEntry(g.note_id);
      };
      name.addEventListener("click", open);
      name.addEventListener("keydown", (event) => event.key === "Enter" && open(event));
    }
  }
}

//: **A sentence said from a note is drawn as one** (CHAT_PLAN decision 33):
//: an answer composed from the notes marks each of its rows `said`, "quoted"
//: (the note's words as written) or "shifted" (said back to the person who
//: wrote them, "I went" as "you went", the row keeping the note's own words
//: as `original`). Each is wrapped in `.said` (ask-compose-lazy.css, a left
//: rule in the quote style; never quotation marks, which are not the note's
//: and broke grounding when they were added to the text); a shifted one
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
function renderActCard(holder, event) {
  const card = document.createElement("div");
  card.className = "tool-confirm";
  const run = (steps, then) =>
    apiJson("/chat/command/run", { method: "POST", body: JSON.stringify({ steps, skipped: event.skipped || [] }) })
      .then((result) => (refreshAfterToolChanges(), then(result)))
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
      return result;
    });
  //: `said`: the answer above already read this sentence (a reminder, a new
  //: note or a pin ran at once), so the card carries only Undo; drawing the
  //: sentence again made the bubble say it twice. The words stay on the card
  //: as its accessible name, and a run with nothing to undo draws no card.
  const done = (summary, undo, steps, said = false) => {
    const row = document.createElement("div");
    row.className = "row";
    if (undo?.length) {
      let inverse = undo;
      const action = pushUndo(
        summary.replace(/^Done:\s*/, "").replace(/\.$/, ""),
        () => post(inverse),
        async () => {
          const again = await post(steps);
          inverse = again.undo || [];
        }
      );
      row.appendChild(
        smallButton("Undo", "Take this back", () =>
          run(inverse, () => {
            settleUndoFromToast(action);
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
  if (event.done) done(event.summary || event.label, event.undo, event.steps, true);
  else {
    const notice = document.createElement("p");
    notice.className = "muted";
    notice.textContent = event.notice;
    const row = document.createElement("div");
    row.className = "row";
    row.append(
      smallButton("Confirm", "Do this", () => run(event.steps, (result) => done(result.summary, result.undo, event.steps)), false),
      smallButton("Cancel", "Don't do this", () => card.replaceWith(toolChip("ph:x Cancelled: nothing was changed.")))
    );
    line(`ph:warning ${event.label}`, notice, row);
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
//: Pressed, they show and the first of them takes focus.
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
  button.addEventListener("click", () => {
    for (const p of folded) p.hidden = false;
    button.remove();
    folded[0].tabIndex = -1;
    folded[0].focus({ preventScroll: true });
  });
}

//: The digest's one offer (CHAT_PLAN decision 70, B12): its last line, a
//: question the answer asks ("Remind you to ask the tutor on Thursday?"),
//: made the button that does it. Plain tier (`.linklike`): an action in
//: running text. A reminder goes through the same door Quick add uses
//: (`/reminders/parse`, rules first, the person's clock); a checklist or a
//: note is a new note. Each one says what it did, with Undo.
//: A call's asks ("yo brotato", `vocative.py`), waiting for the Ask box's
//: follow-up strip, which is drawn just after the offer.
let askOfferAsks = null;

function digestOffer(answerEl, offer) {
  //: An "ask" offer is what to say next: the follow-up chips draw it, in
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
  const line = [...answerEl.querySelectorAll("p")].reverse().find((p) => p.textContent.trim() === offer.label);
  if (!line) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "linklike digest-offer";
  button.dataset.surface = offer.surface || "";
  button.textContent = offer.label;
  button.addEventListener("click", async () => {
    button.disabled = true;
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
        line.textContent = "Starting SearXNG… the first run downloads it, so give it a minute.";
        try {
          const body = await apiJson("/websearch/searxng/start", { method: "POST" });
          if (typeof prefsCache !== "undefined") prefsCache = await apiJson("/preferences").catch(() => prefsCache);
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
      if (undo) {
        offerUndo(
          label,
          said,
          async () => {
            await undo();
            line.replaceChildren(button);
            line.classList.remove("muted");
            button.disabled = false;
          },
          async () => {
            await redo();
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
  }).catch((error) => toast(error.message || "Could not make the map.", true));
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
function renderAskWhy(lines) {
  const holder = $("ask-why");
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
  $("ask-answer-foot")?.classList.remove("hidden");
}

//: **A follow-up is a question that keeps the answer above it** (decision 8:
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
        body: JSON.stringify({ question, answer }),
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
      question,
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
    body.textContent = "Could not read your notes just now.";
    body.closest("details").dataset.failed = "1";
  }
}
