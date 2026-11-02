// citation-peek.js: the card that opens beside a citation mark or an attached
// file's name (hover, focus or press), moved out of capture-ask.js on
// 2026-11-01 for the gzip budget (tests/test_static_compression.py, boot diet 3).
//
// Every caller is a lazy file (answer-kit.js, ask-compose.js, reply-kit.js,
// attachment-peek.js), and each bundle that carries one lists this file first
// (LAZY_MODULES in app.js, lazy-entries.js, chat-agent.js's attachment load).

const citationPeekState = { panel: null, link: null, pinned: false, openTimer: 0, closeTimer: 0, restoring: false };
const CITATION_PEEK_CONTEXT = 90;

function scheduleCitationPeekClose() {
  clearTimeout(citationPeekState.openTimer);
  clearTimeout(citationPeekState.closeTimer);
  if (citationPeekState.pinned) return;
  //: Long enough to cross the 10px between the mark and the card.
  citationPeekState.closeTimer = setTimeout(() => closeCitationPeek(), 220);
}

//: Where the note's words begin once its title line is said above them (audit
//: 1031 N14, INBOX 1518): the heading or bold first line whose words are the
//: card's title is not repeated as the first line of the body. 0 when the
//: first line is not the title.
function citationTitleEnd(text, title) {
  const at = text.indexOf("\n");
  const first = plainText(at < 0 ? text : text.slice(0, at));
  const named = plainText(String(title || "")).replace(/…$/, "");
  return at > 0 && first && named && (first === named || named.startsWith(first) || first.startsWith(named)) ? at + 1 : 0;
}

function citationPeekText(content, start, end, title = "") {
  const text = String(content || "");
  const lead = citationTitleEnd(text, title);
  const hasPassage = Number.isInteger(start) && Number.isInteger(end) && end > start && end <= text.length;
  if (!hasPassage) {
    const opening = plainText(text.slice(lead));
    return { before: "", passage: "", after: opening.length > 280 ? `${opening.slice(0, 279)}…` : opening };
  }
  const from = Math.max(start >= lead ? lead : 0, start - CITATION_PEEK_CONTEXT);
  const to = Math.min(text.length, end + CITATION_PEEK_CONTEXT);
  //: `plainText` trims, so the spacing at each join is put back from the
  //: note itself: a space where the note had one, none where the passage
  //: ends against its own full stop.
  const before = plainText(text.slice(from, start));
  const after = plainText(text.slice(end, to));
  const gapBefore = /\s/.test(text[start - 1] || "") ? " " : "";
  const gapAfter = /\s/.test(text[end] || "") ? " " : "";
  return {
    before: before ? `${from > lead ? "…" : ""}${before}${gapBefore}` : "",
    passage: plainText(text.slice(start, end)),
    after: after ? `${gapAfter}${after}${to < text.length ? "…" : ""}` : "",
  };
}

function openCitationPeek(link, source, { pinned }) {
  clearTimeout(citationPeekState.openTimer);
  clearTimeout(citationPeekState.closeTimer);
  if (!link.isConnected) return;
  if (citationPeekState.link === link && citationPeekState.panel) {
    citationPeekState.pinned ||= pinned;
    return;
  }
  closeCitationPeek();
  const entry = source.entry || allEntries.find((e) => e.id === source.noteId) || null;
  const content = entry?.content || source.label || "";
  const panel = document.createElement("div");
  panel.className = "help-popover citation-peek";
  panel.id = "citation-peek";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", `Source ${source.number}`);
  const go = () => {
    closeCitationPeek();
    if (source.open) return source.open();
    openNoteAtPassage(source.noteId, citationPeekText(source.entry?.content, source.start, source.end).passage);
  };
  //: The whole preview is the way in (INBOX 80: "clicking the preview panel
  //: itself goes there"), as one button: one tab stop and one target, not a
  //: card with a click handler a keyboard cannot reach.
  const preview = document.createElement("button");
  preview.type = "button";
  preview.className = "citation-peek-preview";
  const head = document.createElement("span");
  head.className = "citation-peek-head";
  const number = document.createElement("span");
  number.className = "citation-peek-number";
  number.textContent = String(source.number);
  const title = document.createElement("span");
  title.className = "citation-peek-title";
  title.textContent = source.title || noteLabel({ content }, 80);
  head.append(number, title);
  const body = document.createElement("span");
  body.className = "citation-peek-body";
  const { before, passage, after } = citationPeekText(content, source.start, source.end, title.textContent);
  const mark = document.createElement("mark");
  mark.textContent = passage;
  body.append(before, ...(passage ? [mark] : []), after);
  preview.append(head, body);
  //: The words the mark matched on (INBOX 76), so a number on the wrong
  //: note reads as the wrong words rather than looking as right as any other.
  if (Array.isArray(source.terms) && source.terms.length) {
    const terms = document.createElement("span");
    terms.className = "library-file-meta citation-peek-terms";
    terms.textContent = `Matched on ${source.terms.map((t) => `“${t}”`).join(", ")}`;
    preview.append(terms);
  }
  //: The verdict and the three signals (row 6).
  const evidence = evidenceBlock({ signals: source.signals, verdict: source.verdict });
  if (evidence) preview.append(evidence);
  preview.addEventListener("click", go);
  const foot = document.createElement("div");
  foot.className = "citation-peek-foot";
  const meta = document.createElement("span");
  meta.className = "library-file-meta citation-peek-meta";
  const facts = [entry?.category, entry?.created_at ? relativeTime(entry.created_at) : ""].filter(Boolean);
  meta.textContent = facts.join(" · ");
  foot.append(meta, smallButton(`ph:arrow-square-out Open ${source.what || "note"}`, source.what ? `Open this ${source.what}` : "Open this note in Notes", go));
  panel.append(preview, foot);
  ensureModule("askCompose").then(() => {
    const verdictRow = citationVerdictRow(source, content);
    if (verdictRow && foot.parentNode === panel) panel.insertBefore(verdictRow, foot);
  }).catch(() => {});
  panel.addEventListener("mouseenter", () => clearTimeout(citationPeekState.closeTimer));
  panel.addEventListener("mouseleave", () => scheduleCitationPeekClose());
  panel.addEventListener("focusout", (event) => {
    if (!panel.contains(event.relatedTarget) && event.relatedTarget !== link) scheduleCitationPeekClose();
  });
  //: The panel sits at the end of <body>, and a pinned peek ignores focusout,
  //: so Tab past Open note left it open at the end of the page until Escape.
  //: Tab off either end hands the page back at the mark, as Escape does.
  panel.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const stops = panel.querySelectorAll("button");
    if (document.activeElement !== stops[event.shiftKey ? 0 : stops.length - 1]) return;
    event.preventDefault();
    closeCitationPeek({ restoreFocus: true });
  });
  document.body.appendChild(panel);
  Object.assign(citationPeekState, { panel, link, pinned });
  link.setAttribute("aria-expanded", "true");
  link.setAttribute("aria-controls", panel.id);
  placeHelpPopover(panel, link);
}

function closeCitationPeek({ restoreFocus = false } = {}) {
  clearTimeout(citationPeekState.openTimer);
  clearTimeout(citationPeekState.closeTimer);
  const { panel, link } = citationPeekState;
  if (!panel) return;
  const hadFocus = panel.contains(document.activeElement);
  panel.remove();
  link?.setAttribute("aria-expanded", "false");
  link?.removeAttribute("aria-controls");
  Object.assign(citationPeekState, { panel: null, link: null, pinned: false });
  if ((restoreFocus || hadFocus) && link?.isConnected) {
    //: Marked while the focus is handed back, so the mark's own focus
    //: handler does not open the peek that is being closed.
    citationPeekState.restoring = true;
    try {
      link.focus({ preventScroll: true });
    } finally {
      citationPeekState.restoring = false;
    }
  }
}

//: Escape and a press anywhere else close a peek. Captured, and the Escape
//: spent (`preventDefault`), because the chat's own Escape stops a streaming
//: answer, and a reader closing a preview mid-answer did not ask for that.
document.addEventListener(
  "keydown",
  (event) => {
    if (event.key !== "Escape" || !citationPeekState.panel) return;
    event.preventDefault();
    event.stopPropagation();
    closeCitationPeek({ restoreFocus: true });
  },
  true
);
document.addEventListener("pointerdown", (event) => {
  const { panel, link } = citationPeekState;
  if (!panel || panel.contains(event.target) || link?.contains(event.target)) return;
  closeCitationPeek();
});
//: The peek is placed in window coordinates beside a digit inside a
//: scrolling transcript. When the transcript moves the card follows the
//: digit, and once the digit has left the scroller's visible box it closes,
//: rather than pointing at nothing. Followed, not closed on the first
//: event: focusing a mark by Tab scrolls it into view, which would
//: otherwise close the peek the focus had just opened.
document.addEventListener(
  "scroll",
  (event) => {
    const { panel, link } = citationPeekState;
    if (!panel || panel.contains(event.target)) return;
    requestAnimationFrame(() => {
      if (citationPeekState.panel !== panel) return;
      const at = link.getBoundingClientRect();
      const box = event.target instanceof Element ? event.target.getBoundingClientRect() : null;
      const gone = !link.isConnected || !at.height || at.bottom < 0 || at.top > window.innerHeight
        || (box && (at.bottom < box.top || at.top > box.bottom));
      if (gone) closeCitationPeek();
      else placeHelpPopover(panel, link);
    });
  },
  true
);
