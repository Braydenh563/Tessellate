// autocorrect.js: autocorrect outside the document editor (Brief 94 (b),
// INBOX 850, the owner: "is there an autocorrect feature with the ability to
// undo it?? everwhere on the app??").
//
// A lazy piece, fetched on the first focus of a box it serves (wiring.js). The
// boxes carry `data-autocorrect` in index.html (Capture, quick note, the chat
// and Ask composers, the graph's note boxes, Write with the AI, the titles)
// and note-edit-panels.js sets it on the edit form's two fields; never a
// search box, a link, a tag or code field (tests/test_autocorrect.py).
// The document editor keeps its own per-document switch and table
// (`DOC_AUTOCORRECT`, documents.js); this table holds all of it plus the
// owner's own slips (Brief 90's fixtures).
//
// One switch, Settings, General, Writing (`autocorrect`, on by default). A
// correction is underlined for five seconds, and a click on the underline opens
// a small menu (keep, put back, edit); Ctrl+Z or Backspace straight after it
// puts the word back at once, and the
// toast carries Undo. A word put back is not corrected again this session,
// and a word in the dictionary never is.

//: **Unambiguous typos only**, the editor's bar: a key is a string that is not
//: a word in any English text, because the cost of being wrong is a silent
//: change to what was typed. The first block is the editor's table; the
//: second the owner's, from tests/fixtures/owner_typos.json (Brief 90),
//: without the slips that are real words ("thes", "ny", "ro", "mut").
const AUTOCORRECT_TYPOS = {
  teh: "the", adn: "and", taht: "that", tehn: "then", thsi: "this",
  thier: "their", recieve: "receive", recieved: "received", seperate: "separate",
  seperated: "separated", occured: "occurred", occuring: "occurring",
  definately: "definitely", wich: "which", becuase: "because", becasue: "because",
  alot: "a lot", accomodate: "accommodate", acheive: "achieve", acheived: "achieved",
  arguement: "argument", beleive: "believe", calender: "calendar",
  concious: "conscious", embarass: "embarrass", enviroment: "environment",
  existance: "existence", goverment: "government", independant: "independent",
  neccessary: "necessary", occassion: "occasion", persistant: "persistent",
  publically: "publicly", recomend: "recommend", refered: "referred",
  succesful: "successful", tommorow: "tomorrow", untill: "until",
  wierd: "weird", writting: "writing", youre: "you're", ot: "to",

  hwo: "how", cna: "can", ahve: "have", mroe: "more", whre: "where", odf: "of",
  knoe: "know", becuas: "because", everwhere: "everywhere", everyhting: "everything",
  everthign: "everything", anythigng: "anything", somthing: "something",
  redeisgn: "redesign", resesign: "redesign", noficiations: "notifications",
  proffesionalising: "professionalising", proffesionalise: "professionalise",
  professionaly: "professionally", percieve: "perceive", recieves: "receives",
  heirarchy: "hierarchy", iomprove: "improve", imrpoving: "improving",
  throrough: "thorough", propper: "proper", statisitcal: "statistical",
  statstics: "statistics", generateing: "generating", featrues: "features",
  geaph: "graph", themnselves: "themselves", architectual: "architectural",
  effcient: "efficient", enought: "enough", excerts: "excerpts",
  expendature: "expenditure", majprly: "majorly", indpired: "inspired",
  libararies: "libraries", workspae: "workspace", smoothlly: "smoothly",
  stlying: "styling", vissually: "visually", utlities: "utilities",
  wierdly: "weirdly", ocnstellation: "constellation",
};

const AUTOCORRECT_SECONDS = 5;
//: A pointer resting on the underline asks after this long, and not at all
//: while keys are still going down (the menu takes the focus).
const AUTOCORRECT_HOVER_MS = 350;
const AUTOCORRECT_TYPING_MS = 900;
const autocorrectState = { key: 0 };
//: The keystrokes that finish a word: the only moment a correction is
//: unambiguous. Mid-word it would rewrite "teh" on the way to "tehran".
const AUTOCORRECT_ENDS = /^[\s.,;:!?)\]]$/;
const autocorrectRefused = new Set();
let autocorrectLast = null, autocorrectBusy = false;

//: The correction the text up to the caret asks for, or null. Pure, so the
//: rule is tested in node: a finished word, not part of a link, a path, a
//: tag, a mention or code, not an acronym, in the table, and neither in the
//: dictionary nor put back already.
function autocorrectFind(upto) {
  const match = /([A-Za-z]+)([\s.,;:!?)\]]{1,2})$/.exec(upto);
  if (!match) return null;
  const typed = match[1];
  const start = upto.length - match[0].length;
  const before = upto.slice(0, start);
  if (/[\w#@/\\:.~`'=<>&|$%^*+-]$/.test(before)) return null;
  //: An odd number of backticks before it is inside code, inline or fenced.
  if ((before.match(/`/g) || []).length % 2) return null;
  if (typed.length > 1 && typed === typed.toUpperCase()) return null;
  const lower = typed.toLowerCase();
  const better = Object.hasOwn(AUTOCORRECT_TYPOS, lower) ? AUTOCORRECT_TYPOS[lower] : "";
  if (!better || autocorrectRefused.has(lower)) return null;
  if ((prefsCache?.writing_dictionary || []).includes(lower)) return null;
  const fixed = typed[0] === lower[0] ? better : better[0].toUpperCase() + better.slice(1);
  return { start, typed, fixed, sep: match[2] };
}

//: Run on the keystroke that finished a word, in one box.
function autocorrectAt(box) {
  const on = prefsCache?.autocorrect !== false;
  if (!on || !box) return false;
  const { from, to } = box.selection();
  if (from !== to) return false;
  const found = autocorrectFind(box.text.slice(0, from));
  if (!found) return false;
  autocorrectForget();
  autocorrectBusy = true;
  try {
    box.replace(found.start, found.start + found.typed.length, found.fixed);
  } finally {
    autocorrectBusy = false;
  }
  const caret = from + found.fixed.length - found.typed.length;
  box.setSelection(caret);
  const entry = { box, ...found, caret, text: box.text };
  autocorrectLast = entry;
  autocorrectMark(entry);
  toastAction(`Corrected “${found.typed}” to “${found.fixed}”.`, "Undo", () => autocorrectUndo(entry), { record: false });
  return true;
}

//: Put the word back. From the underline or the toast it works for as long as
//: the corrected word is still where it was; the caret keeps its place.
function autocorrectUndo(entry = autocorrectLast) {
  if (!entry) return false;
  const end = entry.start + entry.fixed.length;
  if (entry.box.text.slice(entry.start, end) !== entry.fixed) return autocorrectForget(entry);
  const at = entry.box.selection().from;
  autocorrectBusy = true;
  try {
    entry.box.replace(entry.start, end, entry.typed);
  } finally {
    autocorrectBusy = false;
  }
  entry.box.setSelection(at >= end ? at + entry.typed.length - entry.fixed.length : at);
  autocorrectRefused.add(entry.typed.toLowerCase());
  autocorrectForget(entry);
  return true;
}

function autocorrectForget(entry = autocorrectLast) {
  if (!entry) return false;
  clearTimeout(entry.timer);
  clearTimeout(entry.hover);
  entry.mark?.remove();
  entry.mark = null;
  if (autocorrectLast === entry) autocorrectLast = null;
  return false;
}

//: The underline: a button over the corrected word, a child of `body` placed
//: in the window's coordinates (DESIGN.md's popup recipe), one layer above the
//: box it sits on. A press does not take focus from the box.
function autocorrectMark(entry) {
  const mark = document.createElement("button");
  mark.type = "button";
  mark.className = "autocorrect-mark";
  mark.tabIndex = -1;
  mark.title = `Corrected from “${entry.typed}”. Click to keep it, put it back or edit it.`;
  mark.setAttribute("aria-label", `Corrected “${entry.typed}” to “${entry.fixed}”: keep, put back or edit`);
  mark.style.zIndex = autocorrectLayer(entry.box.el);
  mark.addEventListener("mousedown", (event) => event.preventDefault());
  mark.addEventListener("click", () => autocorrectMenu(entry));
  //: **Hover asks too** (INBOX 904 B04: "hover over it and confirm it, edit it,
  //: or rewind"). A mouse resting on the word opens the click's menu; leaving
  //: first cancels it; a finger has no hover and keeps the click.
  mark.addEventListener("pointerenter", (event) => {
    if (event.pointerType !== "mouse") return;
    clearTimeout(entry.hover);
    const ask = () => {
      if (!entry.mark || entry.asked) return;
      if (Date.now() - autocorrectState.key < AUTOCORRECT_TYPING_MS) entry.hover = setTimeout(ask, AUTOCORRECT_HOVER_MS);
      else autocorrectMenu(entry);
    };
    entry.hover = setTimeout(ask, AUTOCORRECT_HOVER_MS);
  });
  mark.addEventListener("pointerleave", () => clearTimeout(entry.hover));
  document.body.appendChild(mark);
  entry.mark = mark;
  entry.timer = setTimeout(() => autocorrectForget(entry), AUTOCORRECT_SECONDS * 1000);
  autocorrectPlace(entry);
}

//: **A click on the underline asks, it does not undo** (INBOX 904 B09: "when I
//: clicked the word that was underlined, it instantly reverted"). The app's one
//: menu-at-a-point recipe, under the word: Keep it (the underline goes), Put
//: back what was typed, or Edit it (the word is selected in its box, so typing
//: replaces it). The five-second timer stops while it is open: a menu that
//: closed itself under the pointer would be the same surprise again.
function autocorrectMenu(entry) {
  const rect = entry.mark?.getBoundingClientRect();
  if (!rect || typeof openMenuAtPoint !== "function") return;
  entry.asked = true;
  clearTimeout(entry.hover);
  clearTimeout(entry.timer);
  entry.timer = setTimeout(() => autocorrectForget(entry), 60 * 1000);
  openMenuAtPoint(
    [
      { label: `ph:check Keep “${entry.fixed}”`, title: "Leave the corrected word as it is", run: () => autocorrectForget(entry) },
      { label: `ph:arrow-counter-clockwise Put back “${entry.typed}”`, title: "Restore what you typed, and leave it alone from now on", run: () => autocorrectUndo(entry) },
      { label: "ph:pencil-simple Edit the word", title: "Select it so you can type over it", run: () => autocorrectEdit(entry) },
    ],
    `Autocorrected “${entry.typed}”`,
    rect.left,
    rect.bottom + 4
  );
  //: Under the word; but a menu that flipped up from the window's edge lands on
  //: the very word it is about, so a frame later (once the recipe has placed and
  //: focused it) it is moved to sit over the word instead.
  requestAnimationFrame(() => {
    const menu = document.querySelector(".action-menu.action-menu-escaped") || (typeof pointerMenuHost !== "undefined" && pointerMenuHost?.querySelector(".action-menu"));
    const box = menu?.getBoundingClientRect();
    if (!box || !(box.top < rect.bottom && box.bottom > rect.top)) return;
    menu.style.bottom = "auto";
    menu.style.top = `${Math.max(8, rect.top - 4 - box.height)}px`;
  });
}

//: The document editor's own correction (documents.js `docAutocorrectAt`), shown
//: with the same underline and menu. The document keeps the replacement, the
//: toast and Ctrl+Z (its own history step), so the entry is `native`: the key
//: handler below leaves it alone. Put back adds the word to the same refused
//: set the document reads.
function autocorrectShow(surface, start, typed, fixed) {
  if (!surface?.view?.dom || typeof surface.coordsAt !== "function") return false;
  //: The file may have been fetched since the keystroke: still the same word?
  if (surface.text.slice(start, start + fixed.length) !== fixed) return false;
  autocorrectForget();
  const box = autocorrectSurface(surface);
  const entry = { box, start, typed, fixed, sep: "", caret: surface.selection().from, text: box.text, native: true };
  autocorrectLast = entry;
  autocorrectMark(entry);
  return true;
}

//: The corrected word selected in its box, for typing over it.
function autocorrectEdit(entry) {
  const end = entry.start + entry.fixed.length;
  if (entry.box.text.slice(entry.start, end) !== entry.fixed) return autocorrectForget(entry);
  entry.box.select(entry.start, end);
  return autocorrectForget(entry);
}

//: Placed, and placed again when anything scrolls; a word out of view hides it.
function autocorrectPlace(entry) {
  const mark = entry?.mark;
  if (!mark) return;
  const rect = entry.box.rect(entry.start, entry.start + entry.fixed.length);
  mark.hidden = !rect || rect.width < 1;
  if (mark.hidden) return;
  mark.style.left = `${rect.left}px`;
  mark.style.top = `${rect.top}px`;
  mark.style.width = `${rect.width}px`;
  mark.style.height = `${rect.height}px`;
}

function autocorrectLayer(el) {
  let top = 0;
  for (let node = el; node && node !== document.body; node = node.parentElement) {
    const z = Number.parseInt(getComputedStyle(node).zIndex, 10);
    if (z > top) top = z;
  }
  return String(top + 1);
}

//: A plain `<input>` or `<textarea>`. `insertText` keeps the browser's own
//: undo history whole; `setRangeText` is the fallback where it is refused.
function autocorrectField(el) {
  return {
    el,
    get text() { return el.value; },
    selection: () => ({ from: el.selectionStart, to: el.selectionEnd }),
    replace(from, to, text) {
      el.focus();
      el.setSelectionRange(from, to);
      if (!document.execCommand("insertText", false, text)) {
        el.setRangeText(text, from, to, "end");
        el.dispatchEvent(new Event("input", { bubbles: true }));
      }
    },
    setSelection: (at) => el.setSelectionRange(at, at),
    select(from, to) {
      el.focus();
      el.setSelectionRange(from, to);
    },
    rect: (from, to) => autocorrectFieldRect(el, from, to),
  };
}

//: A note box once its editor has mounted (documents.js `cmSurface`).
function autocorrectSurface(surface) {
  return {
    el: surface.view.dom,
    get text() { return surface.text; },
    selection: () => surface.selection(),
    replace: (from, to, text) => surface.replaceRange(from, to, text),
    setSelection: (at) => surface.setSelection(at),
    select(from, to) {
      surface.focus();
      surface.setSelection(from, to);
    },
    rect(from, to) {
      const a = surface.coordsAt(from);
      const b = surface.coordsAt(to);
      if (a.offscreen || b.top !== a.top) return null;
      return { left: a.left, top: a.top, width: b.left - a.left, height: a.bottom - a.top };
    },
  };
}

//: The word's box in a plain field: the mirror technique (`docMirrorPoint` in
//: documents.js is its caret twin, lazy with the Library, and this file loads
//: without it), measuring a span around the word rather than a caret. A word
//: scrolled out of the box gets no underline.
const AUTOCORRECT_MIRROR_PROPS = [
  "boxSizing", "width", "borderLeftWidth", "borderRightWidth", "borderTopWidth",
  "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
  "fontFamily", "fontSize", "fontWeight", "fontStyle", "letterSpacing",
  "lineHeight", "textTransform", "textIndent", "whiteSpace", "wordSpacing",
  "tabSize",
];

function autocorrectFieldRect(el, from, to) {
  const style = getComputedStyle(el);
  const mirror = document.createElement("div");
  mirror.className = "doc-caret-mirror"; // off-screen, with its border fix
  for (const prop of AUTOCORRECT_MIRROR_PROPS) mirror.style[prop] = style[prop];
  const line = el instanceof HTMLInputElement;
  mirror.style.whiteSpace = line ? "pre" : "pre-wrap";
  mirror.style.overflowWrap = line ? "normal" : "break-word";
  mirror.textContent = el.value.slice(0, from);
  const word = document.createElement("span");
  word.textContent = el.value.slice(from, to);
  mirror.appendChild(word);
  document.body.appendChild(mirror);
  const box = el.getBoundingClientRect();
  const frame = mirror.getBoundingClientRect();
  const at = word.getBoundingClientRect();
  mirror.remove();
  const left = box.left + (at.left - frame.left) - el.scrollLeft;
  //: A one-line field centres its text in its height; a textarea starts it
  //: at the padding, as the mirror does.
  const top = line ? box.top + (box.height - at.height) / 2 : box.top + (at.top - frame.top) - el.scrollTop;
  if (left < box.left || left + at.width > box.right + 1 || top < box.top || top + at.height > box.bottom + 1) return null;
  return { left, top, width: at.width, height: at.height };
}

//: The box has changed since: the keys go back to their own jobs, and an
//: underline goes once the text before it moves.
function autocorrectMoved(el) {
  const entry = autocorrectLast;
  if (!entry || autocorrectBusy || entry.box.el !== el) return;
  const end = entry.start + entry.fixed.length;
  if (entry.box.text.slice(0, end) !== entry.text.slice(0, end)) autocorrectForget(entry);
}

function autocorrectFresh(entry, target) {
  if (!entry || !(entry.box.el === target || entry.box.el.contains(target))) return false;
  const { from, to } = entry.box.selection();
  return from === to && from === entry.caret && entry.box.text === entry.text;
}

document.addEventListener(
  "input",
  (event) => {
    const el = event.target;
    if (autocorrectBusy || !(el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement)) return;
    if (!el.matches("[data-autocorrect]")) return;
    autocorrectMoved(el);
    //: A mounted note box's own textarea only mirrors its editor (an event
    //: from script); its typing arrives as "note-typed" below.
    if (!event.isTrusted) return;
    const typed = event.inputType === "insertLineBreak" ? "\n" : event.inputType === "insertText" ? event.data : "";
    if (typed && AUTOCORRECT_ENDS.test(typed)) autocorrectAt(autocorrectField(el));
  },
  true
);

//: documents.js raises this after a typed change in a mounted note box, a
//: microtask after the editor's own update.
document.addEventListener("note-typed", (event) => {
  const host = event.target;
  if (!host.matches?.("[data-autocorrect]") || !event.detail) return;
  const box = autocorrectSurface(event.detail);
  autocorrectMoved(box.el);
  autocorrectAt(box);
});

//: Ctrl+Z or Backspace straight after a correction puts the word back, before
//: the box's own handling sees the key.
document.addEventListener(
  "keydown",
  (event) => {
    autocorrectState.key = Date.now();
    const entry = autocorrectLast;
    if (!entry || event.altKey || event.isComposing) return;
    //: The document's own correction keeps its own Ctrl+Z; only the underline
    //: needs to hear that the text moved.
    if (entry.native) {
      setTimeout(() => autocorrectMoved(entry.box.el), 50);
      return;
    }
    const undo = (event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "z";
    const back = event.key === "Backspace" && !event.ctrlKey && !event.metaKey;
    if (!(undo || back) || !autocorrectFresh(entry, event.target)) return;
    event.preventDefault();
    event.stopPropagation();
    autocorrectUndo(entry);
  },
  true
);

document.addEventListener("focusout", (event) => {
  const entry = autocorrectLast;
  if (entry && (entry.box.el === event.target || entry.box.el.contains(event.target))) {
    //: The underline only: the toast's Undo still works.
    entry.mark?.remove();
    entry.mark = null;
  }
});
window.addEventListener("scroll", () => autocorrectPlace(autocorrectLast), true);
