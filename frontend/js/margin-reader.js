// The margin reader in the document editor (WORLD_CLASS_PLAN I2, H8).
//
// A second reader beside the text, from the person's own notes: while a
// document is being written, a quiet column to the right of the editor fills
// with at most three cards about the paragraph under the caret, each typed
// (repeats, contradicts, answers, a date, related) and each naming the
// sentence in another note it is about. Nothing is ever written into the
// text: a card offers Open, Not this, and for a date, Make a reminder.
//
// Off by default, one switch in the dock's menu ("While you write"),
// remembered per device like the other writing switches beside it.
// Loaded with the Library bundle after documents.js, and reads only its
// `docCmView` and `currentDoc` (one global scope, classic scripts).
//
// The timing is the plan's: 1.2 s after typing stops in a paragraph; one
// request in flight; a reply for a paragraph that has since changed is
// dropped. The first request is the fast local reading (under 300 ms with
// no model); when it found something to judge, a second request asks the
// model (`judge`), and its answer replaces the first only if the paragraph
// is still the same.

const MARGIN_KEY = "doc-margin-reader";
const MARGIN_PAUSE_MS = 1200;
const MARGIN_KIND_WORDS = {
  repeats: "Repeats",
  contradicts: "Differs",
  answers: "Answers",
  date: "Date",
  related: "Related",
};

//: The reader's state in this editing session, one name in the shared scope.
const marginState = { on: false, timer: null, inFlight: false, paragraph: "", top: 0 };
//: Sources shown, or dismissed, in this editing session: never shown twice.
const marginSeen = new Set();
//: Holds source ids and, for a date card, `date:<when>` keys (see `marginCardKey`).
const marginDismissed = new Set();

//: What "Not this" remembers a card by: its source note, or for a date card,
//: which has none, the day it names. Without one the card came back (X27).
function marginCardKey(card) {
  if (card.source_entry_id) return card.source_entry_id;
  return card.kind === "date" && card.when ? `date:${card.when}` : null;
}

//: A margin that cannot read stays quiet, but the lag log (Settings, Logs)
//: now has the reason; the log is a lazy module, so it may not be there yet.
function marginLogError(error) {
  window.lagNoteError?.(`Margin reader: ${error?.message || error}`, error?.stack);
}

function marginParagraphAtCaret() {
  const view = typeof docCmView !== "undefined" ? docCmView : null;
  if (!view) return null;
  const doc = view.state.doc;
  let first = doc.lineAt(view.state.selection.main.head).number;
  let last = first;
  while (first > 1 && doc.line(first - 1).text.trim() !== "") first--;
  while (last < doc.lines && doc.line(last + 1).text.trim() !== "") last++;
  const from = doc.line(first).from;
  const text = doc.sliceString(from, doc.line(last).to).trim();
  let top = 0;
  try {
    const coords = view.coordsAtPos(from);
    const wrap = $("doc-source-wrap").getBoundingClientRect();
    if (coords) top = Math.max(0, coords.top - wrap.top);
  } catch {
    top = 0;
  }
  return { text, top, ordinal: first };
}

function marginCard(card) {
  const box = document.createElement("article");
  box.className = `doc-margin-card is-${card.kind}`;
  const head = document.createElement("div");
  head.className = "doc-margin-card-head";
  head.append(chip(MARGIN_KIND_WORDS[card.kind] || card.kind, `item-label${card.kind === "contradicts" ? " is-warn" : ""}`));
  if (card.judged_by) head.append(chip("from the model", "item-label"));
  const text = document.createElement("p");
  text.className = "doc-margin-card-text";
  text.textContent = card.text;
  const reason = document.createElement("p");
  reason.className = "doc-margin-card-reason";
  reason.textContent = card.reason || "";
  const actions = document.createElement("div");
  actions.className = "doc-margin-card-actions";
  const button = (label, onClick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small";
    b.textContent = label;
    b.addEventListener("click", onClick);
    actions.append(b);
    return b;
  };
  if (card.kind === "date") {
    button("Make a reminder", async (event) => {
      event.currentTarget.disabled = true;
      try {
        const made = await apiJson("/reminders", { method: "POST", body: JSON.stringify({ text: marginState.paragraph.slice(0, 200), due_at: card.when }) });
        reminderMadeUndo(made);
        toast(`Reminder set for ${card.phrase}.`);
      } catch (error) {
        toast(error.message || "Couldn't make that reminder.", true);
        event.currentTarget.disabled = false;
      }
    });
  } else if (card.source_entry_id) {
    button("Open", () => flashEntry(card.source_entry_id));
  }
  button("Not this", () => {
    const key = marginCardKey(card);
    if (key) marginDismissed.add(key);
    box.remove();
  });
  box.append(head, text);
  if (card.reason) box.append(reason);
  box.append(actions);
  return box;
}

function marginRender(cards) {
  const host = $("doc-margin");
  if (!host) return;
  const list = document.createElement("div");
  list.className = "doc-margin-cards";
  //: Pinned to the paragraph: the stack starts level with it, and a column
  //: that is stacked under the editor (narrow panes) ignores the offset.
  list.style.setProperty("--doc-margin-offset", `${Math.round(marginState.top)}px`);
  for (const card of cards) {
    if (card.source_entry_id) marginSeen.add(card.source_entry_id);
    list.append(marginCard(card));
  }
  host.replaceChildren(list);
}

async function marginAsk(judge) {
  const at = marginParagraphAtCaret();
  if (!at || at.text.length < 12) return;
  if (marginState.inFlight) {
    marginSchedule();
    return;
  }
  marginState.inFlight = true;
  marginState.paragraph = at.text;
  marginState.top = at.top;
  const body = {
    paragraph: at.text,
    ordinal: at.ordinal,
    document_id: currentDoc ? currentDoc.id : null,
    exclude: [...marginDismissed].filter(Number.isInteger),
    judge,
  };
  let followUp = false;
  try {
    const reply = await apiJson("/editor/read", { method: "POST", body: JSON.stringify(body) });
    const now = marginParagraphAtCaret();
    if (!marginState.on || !now || now.text !== at.text) return; // the paragraph moved on
    if (reply.off) {
      $("doc-margin").replaceChildren(marginOffNote());
      return;
    }
    const cards = (reply.cards || []).filter((c) => !marginDismissed.has(marginCardKey(c)));
    marginRender(cards);
    const judgeable = cards.some((c) => c.kind === "related" || c.kind === "repeats");
    followUp = !judge && judgeable;
  } catch (error) {
    // A margin that cannot read says nothing rather than a toast per pause.
    marginLogError(error);
  } finally {
    marginState.inFlight = false;
  }
  if (followUp) marginAsk(true);
}

function marginOffNote() {
  const p = document.createElement("p");
  p.className = "muted text-sm";
  p.textContent = "The margin reader is switched off in Settings, What it learned.";
  return p;
}

function marginSchedule() {
  if (!marginState.on) return;
  clearTimeout(marginState.timer);
  marginState.timer = setTimeout(() => marginAsk(false), MARGIN_PAUSE_MS);
}

function applyMarginReader(on) {
  marginState.on = on;
  const button = $("doc-margin-reader");
  if (button) {
    button.setAttribute("aria-pressed", String(on));
    button.title = on ? "Hide the margin reader" : "Show notes of yours about the paragraph you are writing, in the margin";
  }
  $("doc-margin")?.classList.toggle("hidden", !on);
  $("doc-source-wrap")?.classList.toggle("has-margin", on);
  if (on) marginSchedule();
  else $("doc-margin")?.replaceChildren();
}

$("doc-margin-reader")?.addEventListener("click", () => {
  try {
    prefs.set(MARGIN_KEY, marginState.on ? "0" : "1");
  } catch {
    // A private window can refuse storage; the switch still applies for now.
  }
  applyMarginReader(!marginState.on);
});

//: Typing and moving the caret both mean "this paragraph": the editor's own
//: DOM events, so this file needs no hook inside the CodeMirror setup.
for (const type of ["keyup", "mouseup"]) {
  $("doc-editor")?.addEventListener(type, marginSchedule);
}

try {
  if (prefs.get(MARGIN_KEY, null) === "1") applyMarginReader(true);
} catch {
  // No storage: the margin starts off, which is its default anyway.
}
