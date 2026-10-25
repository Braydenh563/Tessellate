// documents-prose.js: the prose tools (split out of documents.js on
// 2026-09-24).
//
// What is here: the PROSE-TOOLS region as it stood in documents.js, whole
// and verbatim: grammar (Harper, in the documents editor and in the note
// boxes), suggestion mode (DOC-SUGGEST), the accessibility check and read
// aloud, plus `docProseToolExtensions`, the one hook `docCmExtensions` calls
// for all of them. The rules they sit beside (the prose check, the status
// bar, the dictionary, the finding shapes) stayed in documents.js: they are
// shared with the code side and the note surfaces.
//
// **Loaded in the Library bundle, before documents.js**, for the same reason
// documents-code.js is (see its header): this file's top level reads nothing
// from documents.js, and documents.js's top-level wiring names functions
// defined here, so listing this file first means they exist before any of
// that wiring can run.

// PROSE-TOOLS-BEGIN
// =============================================================================
// Prose tools: grammar, accessibility (INBOX 401 and 404, prose side)
// =============================================================================
//
// The rules above read the shape of the text. What they cannot do, by their
// own header's admission, is grammar: its/it's, agreement, "a apple". Harper
// (Automattic, Apache-2.0, vendored in `frontend/vendor/harper/`) can, on this
// machine, in a worker (`harper-worker.js`), with no model and no network.
//
// **Measured before it was wired** (`scratchpad/ui-sweeps/p2-harper.js`):
// nothing of it is fetched at boot, so the boot budget (WORLD_CLASS_PLAN H7)
// does not move and it is not an install-it-yourself extra; the first check
// costs 1.75 s cold (fetch plus compile of the 15.9 MB binary, off the main
// thread) and every check after that about 100 ms for 1,400 words, in the
// worker. So it loads on the first prose document or note box that asks, and
// the editor never waits for it: until it answers, the rule findings stand on
// their own, exactly as they did before it existed.
//
// **Spelling stays with the dictionary.** Harper has its own spelling lints,
// and they are dropped: this app's dictionary is the one the reader can add
// to, and two checkers disagreeing about one word is the fastest way to teach
// a writer to ignore both.

const DOC_GRAMMAR_WORKER_URL = "/js/harper-worker.js";
//: Harper's lint kinds this app does not take (see above).
const DOC_GRAMMAR_SKIP_KINDS = new Set(["Spelling"]);
//: The quiet between keystrokes before a note box is checked. Longer than
//: the document's own pass because each ask costs the worker a whole lint.
const DOC_GRAMMAR_NOTE_DEBOUNCE_MS = 600;

let docGrammarWorker = null;
let docGrammarError = "";
let docGrammarSeq = 0;
const docGrammarWaiting = new Map();
//: The document's last answer: the text it was for and its findings.
let docGrammarCache = { text: null, findings: [] };
let docGrammarAsking = null;

//: On unless the reader turned it off, and never once it has failed: a
//: binary that did not load will not load on the next keystroke either.
function docGrammarEnabled() {
  if (docGrammarError) return false;
  if (typeof Worker !== "function") return false;
  return !(typeof prefsCache === "object" && prefsCache && prefsCache.grammar_check === false);
}

function docGrammarFail(reason) {
  docGrammarError = reason || "the grammar checker did not load";
  console.warn("Grammar check off for this session:", docGrammarError);
  for (const resolve of docGrammarWaiting.values()) resolve(null);
  docGrammarWaiting.clear();
  if (docGrammarWorker) docGrammarWorker.terminate();
  docGrammarWorker = null;
}

//: The files the worker loads, in its own import order (harper-worker.js
//: names the two vendored modules; the binary is fetched by the second).
const DOC_GRAMMAR_FILES = [
  DOC_GRAMMAR_WORKER_URL,
  "/vendor/harper/BinaryModule-BmeyZWwZ.js",
  "/vendor/harper/slimBinary.js",
];

async function docGrammarWhy() {
  const found = [];
  if (typeof WebAssembly !== "object") found.push("this browser has no WebAssembly");
  for (const file of DOC_GRAMMAR_FILES) {
    try {
      //: `api()` throws on a refusal and carries its status, so a 404 here reads as one.
      const response = await api(file, { cache: "no-store", silent: true });
      const type = (response.headers.get("content-type") || "").split(";")[0].trim();
      if (!/javascript/i.test(type)) found.push(`${file} came as ${type || "no type"}, not JavaScript`);
    } catch (error) {
      found.push(error && error.status ? `${file} answered ${error.status}` : `${file} did not load: ${error && error.message ? error.message : error}`);
    }
  }
  return found.join("; ") || "every file it loads answered as JavaScript";
}

//: One lint of `text`, or null when there is no checker. Never rejects: a
//: caller that has to catch is a caller that one day will not.
function docGrammarAsk(text) {
  if (!docGrammarEnabled()) return Promise.resolve(null);
  if (!docGrammarWorker) {
    try {
      //: Stamped like every other local script, so a new release never
      //: runs last release's worker; the vendored files it imports are not,
      //: by the cache-busting rule for `vendor/`.
      const stamp = typeof lazyAssetStamp === "function" ? lazyAssetStamp(DOC_GRAMMAR_WORKER_URL) : "";
      docGrammarWorker = new Worker(`${DOC_GRAMMAR_WORKER_URL}${stamp}`, { type: "module" });
    } catch (error) {
      docGrammarFail(String(error && error.message ? error.message : error));
      return Promise.resolve(null);
    }
    docGrammarWorker.addEventListener("message", (event) => {
      const data = event.data || {};
      const resolve = docGrammarWaiting.get(data.id);
      if (!data.ok) return docGrammarFail(data.error);
      if (!resolve) return;
      docGrammarWaiting.delete(data.id);
      resolve(data.lints || []);
    });
    //: A worker whose script fails to load says so here and nowhere else,
    //: and with no message: a module worker refused for its type, its CSP or
    //: a 404 on one of its imports fires a bare event (INBOX 804, the
    //: owner's Windows log said only "did not start"). So the reason is
    //: looked for: each file it loads, fetched the way the worker fetches it
    //: (through the service worker), with its status and type.
    docGrammarWorker.addEventListener("error", (event) => {
      event.preventDefault?.();
      if (event.message) return docGrammarFail(event.message);
      docGrammarWhy().then((why) => docGrammarFail(`the grammar worker did not start (${why})`));
    });
  }
  const id = ++docGrammarSeq;
  return new Promise((resolve) => {
    docGrammarWaiting.set(id, resolve);
    docGrammarWorker.postMessage({ id, text, dialect: docSpellingVariant() });
  });
}

//: Harper writes code in backticks and, now and then, a dash this app's copy
//: rule does not allow. Said in the app's own voice instead. The dash is
//: built from its code point so the no-dash lint still reads this file clean.
const DOC_GRAMMAR_DASH = new RegExp(`\\s*${String.fromCharCode(0x2014)}\\s*`, "g");

function docGrammarMessage(message) {
  return String(message || "")
    .replace(/`([^`]+)`/g, "“$1”")
    .replace(DOC_GRAMMAR_DASH, ": ")
    .trim();
}

//: **A wiki link is this app's syntax, not prose.** Harper reads markdown and
//: skips code, but `[[Another doc]]` is not markdown to it: "a [[Another
//: doc]] chip" came back as a redundancy ("Use another on its own") whose
//: only fix was "aNother", measured in the live view 2026-10-04. A lint that
//: touches a link or an embed (`![[...]]`) is dropped; one beside it is kept.
const DOC_GRAMMAR_WIKI = /!?\[\[[^\]\n]+\]\]/g;

function docGrammarOutside(text) {
  const spans = [];
  for (const match of String(text).matchAll(DOC_GRAMMAR_WIKI)) {
    spans.push([match.index, match.index + match[0].length]);
  }
  return (lint) => !spans.some(([from, to]) => lint.start < to && lint.end > from);
}

//: Harper's lints as this app's findings. `replacement` stays null on
//: purpose: "Fix all" applies without asking, and a grammar suggestion is a
//: judgement, so it is always offered and never applied in bulk.
function docGrammarFindings(lints, text) {
  const out = [];
  const outside = docGrammarOutside(text);
  for (const lint of lints || []) {
    if (DOC_GRAMMAR_SKIP_KINDS.has(lint.kind)) continue;
    if (!(lint.end > lint.start) || lint.end > text.length) continue;
    if (!outside(lint)) continue;
    const span = text.slice(lint.start, lint.end);
    const alternatives = [];
    for (const suggestion of lint.suggestions || []) {
      const option = suggestion.kind === "InsertAfter" ? span + suggestion.text : suggestion.text;
      if (option !== span && !alternatives.includes(option)) alternatives.push(option);
    }
    out.push({
      rule: "grammar",
      source: "harper",
      harperKind: lint.kind,
      message: docGrammarMessage(lint.message),
      start: lint.start,
      end: lint.end,
      text: span,
      replacement: null,
      alternatives,
    });
  }
  return out;
}

//: **Last answer, moved with the edits since.** A check is ~100 ms behind the
//: text, so between a keystroke and its answer the old findings are carried
//: across rather than dropped: everything before the first changed character
//: keeps its offset, everything after the last one moves by the length
//: difference, and anything the edit touched is let go. Without this every
//: grammar underline would blink out on each keystroke and back a beat later.
function docProseRemap(findings, from, to) {
  if (from === to) return findings;
  let head = 0;
  const limit = Math.min(from.length, to.length);
  while (head < limit && from.charCodeAt(head) === to.charCodeAt(head)) head += 1;
  let tail = 0;
  while (
    tail < limit - head &&
    from.charCodeAt(from.length - 1 - tail) === to.charCodeAt(to.length - 1 - tail)
  ) {
    tail += 1;
  }
  const shift = to.length - from.length;
  const cut = from.length - tail;
  const out = [];
  for (const finding of findings) {
    if (finding.end <= head) out.push(finding);
    else if (finding.start >= cut) out.push({ ...finding, start: finding.start + shift, end: finding.end + shift });
  }
  return out;
}

//: Ask for the document's text unless it is already asked for or answered.
//: One ask in flight: the answer to a stale ask repaints and the repaint asks
//: again, so a burst of typing costs one lint per pause, not one per key.
//: Nothing to check is no reason to start the checker (audit 2026-10-05,
//: FE-03): the load-time paint of an empty editor started the worker and
//: compiled the 15.9 MB grammar WASM on every first Library visit. It starts
//: on the first document opened (or typed into) with grammar on.
function docGrammarRequest(text) {
  if (!text || !text.trim()) return;
  if (!docGrammarEnabled() || docGrammarAsking !== null || docGrammarCache.text === text) return;
  docGrammarAsking = text;
  docGrammarAsk(text).then((lints) => {
    docGrammarAsking = null;
    if (lints === null) return renderDocProse();
    docGrammarCache = { text, findings: docGrammarFindings(lints, text) };
    renderDocProse();
  });
}

// --- link offers (DOCUMENTS_PLAN VC5) ---------------------------------------
//
// Where the text names another note or document, the server (`link_offers.py`,
// the vendored FlashText) answers the first mention of each; the offer is a
// finding like any other, with the `[[link]]` as its one answer. It is never
// applied by "Fix all": a link is the writer's choice, not a correction.
//: The quiet before the text is sent: one ask per pause, not one per key.
const DOC_LINK_OFFER_QUIET_MS = 700;
//: The server's own cap on the text it will scan.
const DOC_LINK_OFFER_MAX_CHARS = 400000;
//: The last answer, for the document and text it was for. `timer` is the
//: pending ask; a newer keystroke replaces it.
const DOC_LINK_OFFERS = { doc: null, text: null, findings: [], asking: null, timer: 0 };

//: The switch (Settings, Writing; the dictionary dialog) and the names the
//: writer put away for good. On unless turned off, like the grammar check.
function docLinkOfferEnabled() {
  return !(typeof prefsCache === "object" && prefsCache && prefsCache.link_offers === false);
}

function docLinkOfferIgnoredNames() {
  const kept = typeof prefsCache === "object" && prefsCache ? prefsCache.link_offer_ignored : null;
  return new Set((Array.isArray(kept) ? kept : []).map((name) => String(name).toLowerCase()));
}

//: "Not this name, ever": kept on the notebook, because an offer to link a
//: common word is wrong in every document, not only this one. Settings, Writing
//: lists how many are kept and lets them all come back. Undo puts it back.
async function docLinkOfferIgnore(name) {
  const clean = String(name || "").trim();
  if (!clean) return;
  const save = async (names) => {
    prefsCache = await apiJson("/preferences", {
      method: "PUT",
      body: JSON.stringify({ link_offer_ignored: names }),
    }).catch(() => prefsCache);
    renderDocProse();
    if (typeof renderDocProsePanel === "function") renderDocProsePanel();
  };
  const before = [...docLinkOfferIgnoredNames()];
  const lower = clean.toLowerCase();
  if (before.includes(lower)) return;
  await save([...before, lower]);
  offerUndo(
    `No more link offers for “${clean}”`,
    `Link offers for “${clean}” are off.`,
    () => save(before),
    () => save([...before, lower])
  );
}

function docLinkOfferFindings(offers) {
  return offers.map((offer) => ({
    rule: "link-offer",
    source: "notes",
    name: offer.name,
    message: `This names the ${offer.kind} “${offer.name}”. Turn it into a link`,
    start: offer.start,
    end: offer.end,
    text: offer.text,
    replacement: offer.link,
    alternatives: [],
  }));
}

async function docLinkOfferAsk(text, docId) {
  const state = DOC_LINK_OFFERS;
  state.asking = text;
  let body = null;
  try {
    const response = await api("/documents/link-offers", {
      method: "POST",
      body: JSON.stringify({ text, document_id: docId }),
      silent: true,
      readOnly: true,
    });
    body = await response.json();
  } catch (error) {
    body = null;
  }
  state.asking = null;
  if (!body || !Array.isArray(body.offers)) return;
  state.doc = docId;
  state.text = text;
  state.findings = docLinkOfferFindings(body.offers);
  renderDocProse();
}

//: Ask once the writer pauses, unless this text is already answered or on its
//: way. Nothing to scan is no reason to ask.
function docLinkOfferRequest(text) {
  const state = DOC_LINK_OFFERS;
  const docId = currentDoc && currentDoc.id ? currentDoc.id : null;
  if (!docLinkOfferEnabled()) return;
  if (!text || !text.trim() || text.length > DOC_LINK_OFFER_MAX_CHARS) return;
  if (state.asking === text || (state.text === text && state.doc === docId)) return;
  clearTimeout(state.timer);
  state.timer = setTimeout(() => docLinkOfferAsk(text, docId), DOC_LINK_OFFER_QUIET_MS);
}

//: The last answer moved with the edits since, and only for the document it
//: was asked about.
function docLinkOfferCurrent(text) {
  const state = DOC_LINK_OFFERS;
  const docId = currentDoc && currentDoc.id ? currentDoc.id : null;
  if (!docLinkOfferEnabled() || state.text === null || state.doc !== docId) return [];
  const ignored = docLinkOfferIgnoredNames();
  return docProseRemap(state.findings, state.text, text).filter(
    (finding) => !ignored.has(String(finding.name || "").toLowerCase())
  );
}

//: The findings the prose tools add, merged into the rules' own list. A span
//: a rule already holds keeps the rule's finding: the rule is the one with a
//: dictionary and an "always correct" behind it.
function docProseExtras(text, found) {
  const extra = [];
  if (docGrammarEnabled()) {
    docGrammarRequest(text);
    if (docGrammarCache.text !== null) {
      extra.push(...docProseRemap(docGrammarCache.findings, docGrammarCache.text, text));
    }
  }
  //: Accessibility is about the document's structure rather than its words,
  //: so it neither yields to a rule's finding on the same span nor is
  //: skipped where a link's address or a tag starts: that is where it looks.
  const access = docAccessFindings(text).filter((finding) => !docProseIgnored.has(docProseKey(finding)));
  docLinkOfferRequest(text);
  const offered = docLinkOfferCurrent(text);
  if (!extra.length && !access.length && !offered.length) return found;
  const skip = docProseSkipMask(text);
  const offers = offered.filter(
    (finding) =>
      skip[finding.start] !== 1 &&
      text.slice(finding.start, finding.end) === finding.text &&
      !docProseIgnored.has(docProseKey(finding))
  );
  const taken = found.filter((finding) => !DOC_FINDING_SKIP.has(finding.rule));
  //: A note's name is often a proper noun the dictionary has never seen: the
  //: offer to link it replaces the "likely typo" on the same span.
  const named = (finding) => offers.some((offer) => offer.start <= finding.start && finding.end <= offer.end);
  const merged = found.filter((finding) => finding.rule !== "spelling" || !named(finding)).concat(access, offers);
  for (const finding of extra) {
    if (skip[finding.start] === 1) continue;
    if (text.slice(finding.start, finding.end) !== finding.text) continue;
    if (docProseIgnored.has(docProseKey(finding))) continue;
    if (taken.some((rule) => rule.start < finding.end && finding.start < rule.end)) continue;
    merged.push(finding);
  }
  return merged.sort((a, b) => a.start - b.start);
}

// --- grammar in the note boxes ------------------------------------------------
//
// The note editors have no findings plugin (see `noteSurfaceExtensions`): the
// document's list is at the document's offsets. This is the note's own, one
// list per view, checked by the same worker and drawn in the same underline.
// A press on one opens its answers at the pointer through `openMenuAtPoint`.

let noteGrammarEffect = null;

function noteGrammarPlugin(CM) {
  const { Decoration, ViewPlugin } = CM.view;
  if (!noteGrammarEffect) noteGrammarEffect = CM.state.StateEffect.define();
  const effect = noteGrammarEffect;

  function build(view, findings) {
    const text = view.state.doc.toString();
    const ranges = [];
    findings.forEach((finding, index) => {
      if (text.slice(finding.start, finding.end) !== finding.text) return;
      ranges.push(
        Decoration.mark({
          class: "cm-finding cm-finding-grammar",
          attributes: { "data-note-grammar": String(index), title: finding.message },
        }).range(finding.start, finding.end)
      );
    });
    return Decoration.set(ranges, true);
  }

  return ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.view = view;
        this.findings = [];
        this.checked = null;
        this.timer = 0;
        this.decorations = Decoration.none;
        this.schedule();
      }
      schedule() {
        clearTimeout(this.timer);
        if (!docGrammarEnabled()) return;
        this.timer = setTimeout(() => this.check(), DOC_GRAMMAR_NOTE_DEBOUNCE_MS);
      }
      check() {
        const text = this.view.state.doc.toString();
        if (!text.trim() || text === this.checked) return;
        docGrammarAsk(text).then((lints) => {
          if (lints === null || this.destroyed) return;
          if (this.view.state.doc.toString() !== text) return this.schedule();
          const skip = docProseSkipMask(text);
          this.checked = text;
          this.findings = docGrammarFindings(lints, text).filter((finding) => skip[finding.start] !== 1);
          this.view.dispatch({ effects: effect.of(null) });
        });
      }
      update(update) {
        if (update.docChanged) {
          const before = update.startState.doc.toString();
          this.findings = docProseRemap(this.findings, before, update.state.doc.toString());
          this.schedule();
        }
        const told = update.transactions.some((tr) => tr.effects.some((e) => e.is(effect)));
        if (update.docChanged || told) this.decorations = build(update.view, this.findings);
      }
      destroy() {
        this.destroyed = true;
        clearTimeout(this.timer);
      }
    },
    {
      decorations: (plugin) => plugin.decorations,
      eventHandlers: {
        mousedown(event, view) {
          const mark = event.target instanceof Element && event.target.closest("[data-note-grammar]");
          if (!mark || event.button !== 0) return false;
          const finding = this.findings[Number(mark.getAttribute("data-note-grammar"))];
          if (!finding) return false;
          event.preventDefault();
          noteGrammarMenu(view, this, finding, event.clientX, event.clientY);
          return true;
        },
      },
    }
  );
}

//: The answers to one grammar finding in a note: each suggestion as a row,
//: then "Ignore". Recomputed against the text as it is at the press, for the
//: reason `docProseFix` gives.
function noteGrammarMenu(view, plugin, finding, x, y) {
  if (typeof openMenuAtPoint !== "function") return;
  const apply = (option) => {
    const text = view.state.doc.toString();
    if (text.slice(finding.start, finding.end) !== finding.text) {
      return toast("That text has changed since it was checked.", "info");
    }
    view.dispatch({ changes: { from: finding.start, to: finding.end, insert: option } });
    view.focus();
  };
  const items = finding.alternatives.slice(0, DOC_SUGGEST_MAX).map((option) => ({
    group: "fix",
    label: option === "" ? `ph:eraser Remove “${finding.text}”` : option,
    title: finding.message,
    run: () => apply(option),
  }));
  if (!items.length) {
    items.push({ group: "fix", label: `ph:info ${finding.message}`, disabled: true, run: () => {} });
  }
  items.push({
    group: "ignore",
    label: "ph:eye-slash Ignore this one",
    run: () => {
      plugin.findings = plugin.findings.filter((other) => other !== finding);
      view.dispatch({ effects: noteGrammarEffect.of(null) });
    },
  });
  openMenuAtPoint(items, finding.message, x, y);
}

// --- suggestion mode (tracked changes, INBOX 404) ------------------------------
//
// **Stored in the text, as CriticMarkup.** `{++inserted++}` and
// `{--deleted--}` are a published plain-text convention (MultiMarkdown,
// Obsidian and iA Writer read it), and the document's comments already live
// in the text the same way (`%%remark%%`, DOC-COMMENT). So a suggestion is
// saved, versioned, diffed, synced and exported with the document by every
// path that already carries its text, with no field and no migration, and a
// .md download still says what was suggested to anything that reads it. The
// alternative, offsets in a side table, has to be moved through every edit
// by every writer (autosave, restore, the AI, a formatting button), and the
// first writer that forgets moves every mark onto the wrong words.
//
// What is tracked: typing, deleting, pasting and dropping while the mode is
// on. What is not: edits a command makes (a formatting button, a fix from
// the word menu, the AI), which say so by not carrying a user event.
//
// The model between the two markers is pure string work, so
// `tests/test_prose_tools.py` runs it in node.

// DOC-SUGGEST-BEGIN
//: Fenced and inline code: a `{++` in a code sample is the sample.
function docSuggestCodeMask(text) {
  const mask = new Uint8Array(text.length);
  const patterns = [/(^|\n)[ \t]*(```|~~~)[^\n]*\n[\s\S]*?(\n[ \t]*\2[^\n]*|$)/g, /`[^`\n]+`/g];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      if (!match[0].length) {
        pattern.lastIndex += 1;
        continue;
      }
      mask.fill(1, match.index, match.index + match[0].length);
    }
  }
  return mask;
}

//: Every suggestion in the text, in order: its kind, its whole span, and the
//: span of what it suggests (between the three-character markers).
function docSuggestParse(text) {
  const src = String(text == null ? "" : text);
  const code = docSuggestCodeMask(src);
  const pattern = /\{\+\+([\s\S]*?)\+\+\}|\{--([\s\S]*?)--\}/g;
  const out = [];
  let match;
  while ((match = pattern.exec(src)) !== null) {
    if (code[match.index] === 1) continue;
    const ins = match[1] !== undefined;
    const start = match.index;
    const end = start + match[0].length;
    out.push({ kind: ins ? "ins" : "del", start, end, bodyStart: start + 3, bodyEnd: end - 3, body: ins ? match[1] : match[2] });
  }
  return out;
}

//: Two marks of one kind that touch become one, and an empty mark goes, but
//: only in `[lo, hi]`, around the edit that made them: a `--}{--` elsewhere
//: is somebody's text. Returns the text and a function that moves an offset
//: across what was taken out.
function docSuggestNormalize(text, lo, hi) {
  const pattern = /\{\+\+\+\+\}|\{----\}|--\}\{--|\+\+\}\{\+\+/g;
  const cuts = [];
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const end = match.index + match[0].length;
    if (end >= lo && match.index <= hi) cuts.push([match.index, end]);
  }
  let out = "";
  let at = 0;
  for (const [from, to] of cuts) {
    out += text.slice(at, from);
    at = to;
  }
  out += text.slice(at);
  const move = (pos) => {
    let shift = 0;
    for (const [from, to] of cuts) {
      if (pos >= to) shift += to - from;
      else if (pos > from) return from - shift;
    }
    return pos - shift;
  };
  return { text: out, move };
}

//: **One edit, made as a suggestion.** Replacing `[from, to)` of `text` with
//: `insert`; `backward` is a Backspace, which decides where the caret lands.
//:
//: - Deleting words that were themselves suggested as an insertion deletes
//:   them for real: withdrawing your own suggestion is not a new one.
//: - Deleting anything else wraps it in `{--…--}`, merged with a deletion it
//:   touches, so a run of Backspaces is one suggestion.
//: - A marker is never split; an edit that lands only on markers or on text
//:   already suggested for deletion steps over it to the next real letter.
//: - Typing inside an insertion extends it; anywhere else it opens one.
function docSuggestEdit(text, from, to, insert, backward, depth = 0) {
  const src = String(text);
  const marks = docSuggestParse(src);
  const markAt = (i) => marks.find((mark) => mark.start <= i && i < mark.end);
  let region = "";
  let run = "";
  let changed = false;
  const flush = () => {
    if (run) region += `{--${run}--}`;
    run = "";
  };
  for (let i = from; i < to; i += 1) {
    const mark = markAt(i);
    if (mark && mark.kind === "ins" && i >= mark.bodyStart && i < mark.bodyEnd) {
      flush();
      changed = true;
    } else if (mark) {
      flush();
      region += src[i];
    } else {
      run += src[i];
      changed = true;
    }
  }
  flush();
  //: Nothing deletable in the range: a Backspace just after a marker or over
  //: a struck word. Step over the kept characters to the next real one.
  if (to > from && !changed && !insert && depth === 0) {
    let q = backward ? from : to;
    const kept = (i) => {
      const mark = markAt(i);
      return mark && !(mark.kind === "ins" && i >= mark.bodyStart && i < mark.bodyEnd);
    };
    if (backward) {
      while (q > 0 && kept(q - 1)) q -= 1;
      if (q > 0) return docSuggestEdit(src, q - 1, q, "", true, 1);
    } else {
      while (q < src.length && kept(q)) q += 1;
      if (q < src.length) return docSuggestEdit(src, q, q + 1, "", false, 1);
    }
    return { text: src, caret: backward ? from : to };
  }
  let out = src.slice(0, from) + region + src.slice(to);
  let caret = backward ? from : from + region.length;
  let hi = from + region.length;
  if (insert) {
    //: Where the typing goes, in the text after the deletion.
    const after = docSuggestParse(out);
    let p = from + region.length;
    for (const mark of after) {
      if (mark.kind === "del" && p > mark.start && p < mark.end) p = mark.end;
    }
    const host = after.find((mark) => mark.kind === "ins" && p > mark.start && p < mark.end);
    if (host) {
      p = Math.min(Math.max(p, host.bodyStart), host.bodyEnd);
      out = out.slice(0, p) + insert + out.slice(p);
      caret = p + insert.length;
    } else {
      out = `${out.slice(0, p)}{++${insert}++}${out.slice(p)}`;
      caret = p + 3 + insert.length;
    }
    hi = Math.max(hi, caret + 3);
  }
  const tidy = docSuggestNormalize(out, Math.max(0, from - 3), hi + 3);
  caret = tidy.move(caret);
  //: A Backspace leaves the caret in front of the deletion it made, so the
  //: next one reaches the letter before it; a forward delete, behind it.
  for (const mark of docSuggestParse(tidy.text)) {
    if (mark.kind !== "del" || insert) continue;
    if (backward && caret > mark.start && caret <= mark.end) caret = mark.start;
    if (!backward && caret >= mark.start && caret < mark.end) caret = mark.end;
  }
  return { text: tidy.text, caret };
}

//: Accepting or rejecting one suggestion, as an edit over its whole span.
function docSuggestResolve(mark, accept) {
  const keep = (mark.kind === "ins") === accept;
  return { from: mark.start, to: mark.end, insert: keep ? mark.body : "" };
}

//: Every suggestion accepted, or every one rejected: the text as it would be.
function docSuggestResolveAll(text, accept) {
  let out = String(text == null ? "" : text);
  const marks = docSuggestParse(out);
  for (let i = marks.length - 1; i >= 0; i -= 1) {
    const edit = docSuggestResolve(marks[i], accept);
    out = out.slice(0, edit.from) + edit.insert + out.slice(edit.to);
  }
  return out;
}

//: For Read view: struck through and highlighted, in the markdown the
//: renderer already draws, so the page shows what is proposed.
function docSuggestForRead(text) {
  const src = String(text == null ? "" : text);
  const marks = docSuggestParse(src);
  let out = src;
  for (let i = marks.length - 1; i >= 0; i -= 1) {
    const mark = marks[i];
    const body = mark.body.trim() ? (mark.kind === "ins" ? `==${mark.body}==` : `~~${mark.body}~~`) : mark.body;
    out = out.slice(0, mark.start) + body + out.slice(mark.end);
  }
  return out;
}

//: **Which finding a suggested change carries** (INBOX 689). A finding is in
//: the document's own offsets, markers included, so a misspelled word inside
//: `{++faque++}` is a finding whose span lies in the mark's body. The one
//: nearest `offset` (the press, or the caret) wins when a long insertion
//: carries several; with no offset the first does. Null when the body holds
//: none, which is the common case and leaves the menu as it always was.
function docSuggestFindingFor(mark, findings, offset) {
  const inside = (Array.isArray(findings) ? findings : []).filter(
    (finding) => finding.start < mark.bodyEnd && finding.end > mark.bodyStart
  );
  if (!inside.length) return null;
  if (typeof offset === "number") {
    const under = inside.find((finding) => offset >= finding.start && offset <= finding.end);
    if (under) return under;
  }
  return inside[0];
}

//: The rows of the one menu a press on a suggested change opens, as plain
//: data so a test can read them: the change's own answers first, the
//: all-changes rows when there is more than one change, then the finding's
//: answers (`answers`, rows from `docFindingAnswerRows`, the same ones the
//: spelling popover and the panel row are drawn from) as their own group, so
//: one press shows one surface and not a change menu over a spelling one.
//: `run` supplies the actions: `one(accept)`, `all(accept)`, `next()`.
function docSuggestMenuItems(mark, count, answers, run) {
  const what = mark.kind === "ins" ? "insertion" : "deletion";
  const items = [
    { group: "one", label: `ph:check Accept this ${what}`, run: run.one(true) },
    { group: "one", label: `ph:x Reject this ${what}`, run: run.one(false) },
  ];
  if (count > 1) {
    items.push(
      { group: "all", label: `ph:checks Accept all ${count}`, run: run.all(true) },
      { group: "all", label: `ph:x-circle Reject all ${count}`, run: run.all(false) },
      { group: "all", label: "ph:arrow-down Next change", run: run.next() }
    );
  }
  for (const row of answers || []) {
    items.push({ group: "finding", label: row.label, title: row.title, disabled: row.disabled === true, run: () => row.run() });
  }
  return items;
}
// DOC-SUGGEST-END

// --- the accessibility check (INBOX 404) ----------------------------------------
//
// Three things a screen reader user meets in a document and a sighted writer
// never sees: a heading level skipped (the outline a screen reader navigates
// by has a hole in it), an image with no description (it is read as its file
// name), and a link whose text means nothing out of context ("click here",
// read in a list of links). Each is a finding in the suggestions panel under
// Accessibility, with the same underline, menu and "Ignore" as the rest.

// DOC-A11Y-BEGIN
//: Link texts that say nothing on their own. Compared lowercased, with the
//: sentence's closing punctuation off.
const DOC_VAGUE_LINKS = new Set([
  "click here", "click", "here", "this", "this link", "link", "read more",
  "more", "learn more", "see here", "go", "this page", "page", "details",
]);

const DOC_ACCESS_RULES = new Set(["heading-order", "image-alt", "link-text"]);

function docAccessFindings(text) {
  const src = String(text == null ? "" : text);
  const code = docSuggestCodeMask(src);
  const out = [];
  //: Headings, by line: outside fences and the frontmatter block.
  let fence = false;
  let front = src.startsWith("---\n");
  let last = 0;
  let at = 0;
  src.split("\n").forEach((line, index) => {
    const start = at;
    at += line.length + 1;
    if (front) {
      if (index > 0 && /^---\s*$/.test(line)) front = false;
      return;
    }
    if (/^\s*(```|~~~)/.test(line)) {
      fence = !fence;
      return;
    }
    const heading = !fence && /^(#{1,6})\s+\S/.exec(line);
    if (!heading) return;
    const level = heading[1].length;
    if (last && level > last + 1) {
      out.push({
        rule: "heading-order",
        message: `A level ${level} heading under a level ${last}: level ${last + 1} is skipped, which leaves a hole in the outline a screen reader moves by`,
        start,
        end: start + line.length,
        text: line,
        replacement: null,
        alternatives: [`${"#".repeat(last + 1)}${line.slice(level)}`],
      });
    }
    last = level;
  });
  const push = (rule, match, message) => {
    if (code[match.index] === 1) return;
    out.push({ rule, message, start: match.index, end: match.index + match[0].length, text: match[0], replacement: null });
  };
  let match;
  //: Links and images in one pass: `!` in front makes it an image.
  const links = /(!?)\[([^\]\n]*)\]\(([^)\s]+)[^)\n]*\)/g;
  while ((match = links.exec(src)) !== null) {
    const words = match[2].trim();
    if (match[1] === "!") {
      if (!words) push("image-alt", match, "An image with no description: a screen reader says only its file name. Write what it shows between the brackets");
      continue;
    }
    const plain = words.toLowerCase().replace(/[.!?:,;]+$/, "");
    if (!plain) push("link-text", match, "A link with no text: a screen reader has nothing to say for it");
    else if (DOC_VAGUE_LINKS.has(plain)) push("link-text", match, `“${words}” says nothing on its own, and a screen reader lists links out of context: name where it goes`);
    else if (/^(https?:\/\/|www\.)\S+$/i.test(words)) push("link-text", match, "A web address as the link's text is read out a character at a time: name the page instead");
  }
  const images = /<img\b[^>]*>/gi;
  while ((match = images.exec(src)) !== null) {
    if (!/\balt\s*=\s*("[^"]*\S[^"]*"|'[^']*\S[^']*')/i.test(match[0])) {
      push("image-alt", match, "An image with no alt text: a screen reader says only its file name");
    }
  }
  return out.sort((a, b) => a.start - b.start);
}
// DOC-A11Y-END

//: Per document and per viewer, like the reading width: whether *this*
//: reader is suggesting in *this* document is not a fact about the text.
const DOC_SUGGEST_KEY = "docSuggestMode";

function docSuggestModes() {
  try {
    return prefs.json(DOC_SUGGEST_KEY, {}) || {};
  } catch {
    return {};
  }
}

function docSuggestActive() {
  if (!currentDoc || !currentDoc.id || !docFileType().previewable) return false;
  return docSuggestModes()[currentDoc.id] === true;
}

function setDocSuggestMode(on) {
  if (!currentDoc || !currentDoc.id) {
    renderDocSuggestState();
    return toast("Save the document first.", "info");
  }
  //: Suggestions are prose markup; a code or plain-text file has none. The
  //: switch used to flip back off with no word why (the owner, 2026-10-07:
  //: "this suggest changes toggle doesnt work").
  if (on && !docFileType().previewable) {
    renderDocSuggestState();
    return toast("Suggest changes works in text documents, not code or plain files.", "info");
  }
  const modes = docSuggestModes();
  if (on) modes[currentDoc.id] = true;
  else delete modes[currentDoc.id];
  try {
    prefs.set(DOC_SUGGEST_KEY, JSON.stringify(modes));
  } catch {
    /* the mode still holds for this session through the checkbox */
  }
  renderDocSuggestState();
}

let docSuggestAnnotation = null;
let docSuggestEffect = null;

//: The filter that turns a user's edit into a suggestion, and the plugin that
//: draws suggestions and keeps their markers whole.
function docSuggestExtensions(CM) {
  const { Decoration, ViewPlugin, EditorView } = CM.view;
  if (!docSuggestAnnotation) docSuggestAnnotation = CM.state.Annotation.define();
  if (!docSuggestEffect) docSuggestEffect = CM.state.StateEffect.define();
  const filter = CM.state.EditorState.transactionFilter.of((tr) => {
    if (!tr.docChanged || tr.annotation(docSuggestAnnotation) || !docSuggestActive()) return tr;
    if (!["input", "delete", "move"].some((event) => tr.isUserEvent(event))) return tr;
    const changes = [];
    tr.changes.iterChanges((fromA, toA, _fromB, _toB, inserted) => changes.push([fromA, toA, inserted.toString()]));
    const before = tr.startState.doc.toString();
    const backward = tr.isUserEvent("delete.backward");
    let text = before;
    let caret = 0;
    for (let i = changes.length - 1; i >= 0; i -= 1) {
      const [from, to, insert] = changes[i];
      const result = docSuggestEdit(text, from, to, insert, backward);
      text = result.text;
      if (i === 0) caret = result.caret;
    }
    let head = 0;
    const limit = Math.min(before.length, text.length);
    while (head < limit && before.charCodeAt(head) === text.charCodeAt(head)) head += 1;
    let tail = 0;
    while (tail < limit - head && before.charCodeAt(before.length - 1 - tail) === text.charCodeAt(text.length - 1 - tail)) {
      tail += 1;
    }
    return {
      changes: { from: head, to: before.length - tail, insert: text.slice(head, text.length - tail) },
      selection: { anchor: caret },
      scrollIntoView: true,
      annotations: [
        docSuggestAnnotation.of(true),
        CM.state.Transaction.userEvent.of(tr.annotation(CM.state.Transaction.userEvent) || "input"),
      ],
    };
  });

  function build(view) {
    const marks = [];
    const hidden = [];
    const hide = docView === "live";
    for (const mark of docSuggestParse(view.state.doc.toString())) {
      const cls = mark.kind === "ins" ? "cm-suggest-ins" : "cm-suggest-del";
      const title = mark.kind === "ins" ? "Suggested insertion: click to accept or reject" : "Suggested deletion: click to accept or reject";
      const edges = [[mark.start, mark.bodyStart], [mark.bodyEnd, mark.end]];
      for (const [from, to] of edges) {
        hidden.push(Decoration.replace({}).range(from, to));
        if (!hide) marks.push(Decoration.mark({ class: "cm-suggest-marker" }).range(from, to));
      }
      if (mark.bodyEnd > mark.bodyStart) {
        marks.push(
          Decoration.mark({ class: cls, attributes: { "data-doc-suggest": String(mark.start), title } }).range(mark.bodyStart, mark.bodyEnd)
        );
      }
    }
    return {
      decorations: Decoration.set(hide ? marks.concat(hidden) : marks, true),
      atomic: Decoration.set(hidden, true),
    };
  }

  const plugin = ViewPlugin.fromClass(
    class {
      constructor(view) {
        Object.assign(this, build(view));
      }
      update(update) {
        const told = update.transactions.some((tr) => tr.effects.length);
        if (update.docChanged || told) {
          Object.assign(this, build(update.view));
          renderDocSuggestState();
        }
      }
    },
    {
      decorations: (value) => value.decorations,
      eventHandlers: {
        mousedown(event, view) {
          const el = event.target instanceof Element && event.target.closest("[data-doc-suggest]");
          if (!el || event.button !== 0) return false;
          event.preventDefault();
          docSuggestMenu(view, Number(el.getAttribute("data-doc-suggest")), event.clientX, event.clientY);
          return true;
        },
      },
    }
  );
  return [
    filter,
    plugin,
    EditorView.atomicRanges.of((view) => view.plugin(plugin)?.atomic || Decoration.none),
  ];
}

function docSuggestApply(view, edit, message) {
  view.dispatch({
    changes: edit,
    annotations: [docSuggestAnnotation.of(true), window.CM6.state.Transaction.userEvent.of("input.review")],
  });
  if (message) toast(message);
}

//: The answers to one suggestion, at the pointer (or at the change, from the
//: keyboard). Recomputed from the text at the press: the mark is found again
//: by where it starts, and a mark no longer there says so.
function docSuggestMenu(view, start, x, y) {
  const mark = docSuggestParse(view.state.doc.toString()).find((m) => m.start === start);
  if (!mark || typeof openMenuAtPoint !== "function") return;
  const what = mark.kind === "ins" ? "insertion" : "deletion";
  const count = docSuggestParse(view.state.doc.toString()).length;
  //: **One surface** (INBOX 689). A word that is a suggested insertion and
  //: also a spelling finding used to open this menu and, from the same press,
  //: the finding's popover over it. The finding's answers join this menu as
  //: their own group instead, and the popover is shut here and kept shut
  //: while this menu is open (`docOpenSuggestFor`).
  closeDocSuggest();
  const offset = docCmView === view ? view.posAtCoords({ x, y }) : null;
  const finding = docSuggestFindingFor(mark, docProseFound, offset);
  //: The finding's own sentence heads its group, a row that cannot be
  //: pressed, so the candidates below it say what they are candidates for
  //: (the popover this replaces opened with the same line).
  const said = finding ? String(finding.message || "") : "";
  const answers = finding
    ? [
        ...(said ? [{ label: `ph:info ${said.length > 60 ? `${said.slice(0, 57)}\u2026` : said}`, title: said, disabled: true, run: () => {} }] : []),
        ...docFindingAnswerRows(finding),
      ]
    : [];
  const items = docSuggestMenuItems(mark, count, answers, {
    one: (accept) => () => docSuggestApply(view, docSuggestResolve(mark, accept)),
    all: (accept) => () => docSuggestAll(accept),
    next: () => () => docSuggestNext(),
  });
  openMenuAtPoint(items, `Suggested ${what}`, x, y);
}

function docSuggestAll(accept) {
  const view = docCmView;
  if (!view) return;
  const before = view.state.doc.toString();
  const count = docSuggestParse(before).length;
  if (!count) return toast("No suggested changes in this document.");
  docSuggestApply(
    view,
    { from: 0, to: before.length, insert: docSuggestResolveAll(before, accept) },
    `${accept ? "Accepted" : "Rejected"} ${count} change${count === 1 ? "" : "s"}. Ctrl+Z undoes it.`
  );
}

//: The next suggestion after the caret, wrapping, selected and answered: the
//: keyboard's way to every change, since a mark is otherwise a pointer target.
function docSuggestNext() {
  const view = docCmView;
  if (!view) return;
  const marks = docSuggestParse(view.state.doc.toString());
  if (!marks.length) return toast("No suggested changes in this document.");
  const here = view.state.selection.main.head;
  const mark = marks.find((m) => m.start > here) || marks[0];
  view.dispatch({ selection: { anchor: mark.bodyStart, head: mark.bodyEnd }, scrollIntoView: true });
  view.focus();
  requestAnimationFrame(() => {
    const at = view.coordsAtPos(mark.bodyStart) || view.contentDOM.getBoundingClientRect();
    docSuggestMenu(view, mark.start, at.left, at.bottom);
  });
}

//: The chip in the status bar and the rows in the ⋯ menu, from one count.
function renderDocSuggestState() {
  const on = docSuggestActive();
  const count = docCmView ? docSuggestParse(docCmView.state.doc.toString()).length : 0;
  const box = $("doc-suggest-mode");
  if (box) box.checked = on;
  const row = $("doc-suggest-row");
  if (row) row.hidden = !!currentDoc && !docFileType().previewable;
  const chip = $("doc-suggest-status");
  if (chip) {
    chip.hidden = !on && !count;
    const changes = `${count} change${count === 1 ? "" : "s"}`;
    setLabel(chip, `ph:pencil-simple-line ${on ? `Suggesting, ${changes}` : `${changes} suggested`}`);
    chip.title = count ? "Review the next suggested change" : "Suggestion mode is on: what you type and delete is marked for review";
  }
  for (const id of ["doc-suggest-next", "doc-suggest-accept-all", "doc-suggest-reject-all"]) {
    const row = $(id);
    if (row) row.hidden = !count;
  }
}

$("doc-suggest-mode")?.addEventListener("change", (event) => setDocSuggestMode(event.currentTarget.checked));
$("doc-suggest-next")?.addEventListener("click", () => docSuggestNext());
$("doc-suggest-accept-all")?.addEventListener("click", () => docSuggestAll(true));
$("doc-suggest-reject-all")?.addEventListener("click", () => docSuggestAll(false));
$("doc-suggest-status")?.addEventListener("click", () => docSuggestNext());
//: The rows are brought up to date as the menu opens, not only as the text
//: changes: opening a different document changes the answer without an edit.
$("doc-dock-menu")?.addEventListener("toggle", () => {
  renderDocSuggestState();
  renderDocReadAloudState();
});

// --- read aloud (INBOX 404) -----------------------------------------------------
//
// The browser's own `speechSynthesis`, with the voices the operating system
// already has: nothing to download and nothing leaves the machine, so it is
// offline by construction. One sentence per utterance, for two reasons: the
// sentence being spoken can be highlighted (an utterance has no reliable
// "where am I" for markdown the voice never sees), and Chromium cuts a long
// utterance off after about fifteen seconds with no event, which a sentence
// never reaches. Voices marked `localService` are preferred: Chrome also
// lists network voices, and a network voice is exactly what this app does
// not use.

//: Markdown read as words: the syntax is not said, a deletion suggested in
//: suggestion mode is not said, a link says its text and a comment nothing.
function docSpeakable(text) {
  return String(text || "")
    .replace(/\{--[\s\S]*?--\}/g, "")
    .replace(/\{\+\+|\+\+\}/g, "")
    .replace(/%%[^%\n]*%%/g, "")
    .replace(/!\[([^[\]\n]*)\]\([^()\n]*\)/g, "$1")
    .replace(/\[\[(?:[^\]|]*\|)?([^\]]*)\]\]/g, "$1")
    .replace(/\[([^[\]\n]*)\]\([^()\n]*\)/g, "$1")
    .replace(/^\s{0,3}(?:#{1,6}|>|[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?/, "")
    .replace(/\^[A-Za-z0-9-]+$/, "")
    .replace(/<[^>]+>/g, "")
    .replace(/[*_~=`|]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

//: The sentences of `text` between `from` and `to`, each with its span in
//: the document. Per line, because a heading or a list item has no full
//: stop and would otherwise run into the paragraph under it; fenced code is
//: not read.
function docReadAloudSentences(text, from, to) {
  const out = [];
  const segmenter =
    typeof Intl === "object" && typeof Intl.Segmenter === "function"
      ? new Intl.Segmenter(undefined, { granularity: "sentence" })
      : null;
  let fence = false;
  let at = 0;
  for (const line of text.split("\n")) {
    const start = at;
    at += line.length + 1;
    if (/^\s*(```|~~~)/.test(line)) {
      fence = !fence;
      continue;
    }
    if (fence || start + line.length < from || start >= to) continue;
    const pieces = segmenter
      ? [...segmenter.segment(line)].map((s) => [s.index, s.segment])
      : (line.match(/[^.!?]+[.!?]*\s*/g) || []).reduce((list, s) => {
          const index = list.length ? list[list.length - 1][0] + list[list.length - 1][1].length : 0;
          list.push([index, s]);
          return list;
        }, []);
    for (const [index, segment] of pieces) {
      const lead = segment.length - segment.trimStart().length;
      const s = start + index + lead;
      const e = start + index + segment.trimEnd().length;
      if (e <= s || e <= from || s >= to || !docSpeakable(segment)) continue;
      out.push({ from: Math.max(s, from), to: Math.min(e, to) });
    }
  }
  return out;
}

let docReadAloud = null;
let docReadAloudEffect = null;

function docReadAloudVoice(lang) {
  if (!window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices() || [];
  const local = voices.filter((voice) => voice.localService !== false);
  const prefix = String(lang || "en").slice(0, 2).toLowerCase();
  return (
    local.find((voice) => voice.default && voice.lang.toLowerCase().startsWith(prefix)) ||
    local.find((voice) => voice.lang.toLowerCase().startsWith(prefix)) ||
    local.find((voice) => voice.default) ||
    local[0] ||
    null
  );
}

//: From the selection, or from the start of the sentence the caret is in to
//: the end of the document.
function docReadAloudStart() {
  const view = docCmView;
  if (!view) return;
  if (!window.speechSynthesis || typeof SpeechSynthesisUtterance !== "function") {
    return toast("This window has no speech voices to read with.", "info");
  }
  docReadAloudStop();
  const text = view.state.doc.toString();
  const selection = view.state.selection.main;
  const from = selection.empty ? view.state.doc.lineAt(selection.head).from : selection.from;
  const to = selection.empty ? text.length : selection.to;
  const queue = docReadAloudSentences(text, from, to).filter(
    (sentence) => !selection.empty || sentence.to > selection.head || sentence.to === text.length
  );
  if (!queue.length) return toast("Nothing to read from here.");
  docReadAloud = { queue, index: 0, docId: currentDoc && currentDoc.id, utterance: null };
  renderDocReadAloudState();
  docReadAloudNext();
}

function docReadAloudNext() {
  const state = docReadAloud;
  const view = docCmView;
  if (!state || !view) return;
  if (state.index >= state.queue.length || (currentDoc && currentDoc.id) !== state.docId) {
    return docReadAloudStop();
  }
  const sentence = state.queue[state.index];
  const words = docSpeakable(view.state.doc.sliceString(sentence.from, sentence.to));
  if (!words) {
    state.index += 1;
    return docReadAloudNext();
  }
  const utterance = new SpeechSynthesisUtterance(words);
  utterance.lang = document.documentElement.lang || navigator.language || "en";
  const voice = docReadAloudVoice(utterance.lang);
  try {
    if (voice) utterance.voice = voice;
  } catch {
    //: Not a voice this engine will take: its own default speaks instead.
  }
  utterance.onend = () => {
    if (docReadAloud !== state) return;
    state.index += 1;
    docReadAloudNext();
  };
  utterance.onerror = (event) => {
    if (docReadAloud !== state) return;
    if (event.error === "canceled" || event.error === "interrupted") return;
    toast(`Reading stopped: ${event.error || "the voice did not answer"}.`, "info");
    docReadAloudStop();
  };
  //: Held on the state, not only in a closure: Chromium collects an
  //: utterance nothing references and then never fires its `end`.
  state.utterance = utterance;
  view.dispatch({
    effects: [
      docReadAloudEffect.of(sentence),
      window.CM6.view.EditorView.scrollIntoView(sentence.from, { y: "nearest" }),
    ],
  });
  try {
    window.speechSynthesis.speak(utterance);
  } catch (error) {
    toast(`Reading stopped: ${error && error.message ? error.message : "the voice did not answer"}.`, true);
    docReadAloudStop();
  }
}

function docReadAloudStop() {
  const was = docReadAloud;
  docReadAloud = null;
  if (was && window.speechSynthesis) window.speechSynthesis.cancel();
  if (was && docCmView && docReadAloudEffect) docCmView.dispatch({ effects: docReadAloudEffect.of(null) });
  renderDocReadAloudState();
}

function renderDocReadAloudState() {
  const on = Boolean(docReadAloud);
  const row = $("doc-read-aloud");
  if (row) {
    setLabel(row, on ? "ph:stop Stop reading" : "ph:speaker-high Read aloud");
    row.setAttribute("aria-pressed", on ? "true" : "false");
  }
  const stop = $("doc-read-stop");
  if (stop) stop.hidden = !on;
}

//: The highlight, and the queue kept in step with typing while it reads: the
//: sentences still to come are moved through each edit, so reading carries
//: on over the words as they now are.
function docReadAloudExtension(CM) {
  const { Decoration, EditorView } = CM.view;
  if (!docReadAloudEffect) docReadAloudEffect = CM.state.StateEffect.define();
  const effect = docReadAloudEffect;
  const field = CM.state.StateField.define({
    create: () => Decoration.none,
    update(deco, tr) {
      let next = deco.map(tr.changes);
      for (const e of tr.effects) {
        if (!e.is(effect)) continue;
        next = e.value && e.value.to > e.value.from
          ? Decoration.set([Decoration.mark({ class: "cm-read-aloud" }).range(e.value.from, e.value.to)])
          : Decoration.none;
      }
      return next;
    },
    provide: (f) => EditorView.decorations.from(f),
  });
  return [
    field,
    EditorView.updateListener.of((update) => {
      if (!update.docChanged || !docReadAloud) return;
      for (const sentence of docReadAloud.queue) {
        sentence.from = update.changes.mapPos(sentence.from, 1);
        sentence.to = update.changes.mapPos(sentence.to, -1);
      }
    }),
    CM.state.Prec.high(
      CM.view.keymap.of([{ key: "Escape", run: () => (docReadAloud ? (docReadAloudStop(), true) : false) }])
    ),
  ];
}

$("doc-read-aloud")?.addEventListener("click", () => {
  const menu = $("doc-dock-menu");
  if (menu) menu.open = false;
  if (docReadAloud) docReadAloudStop();
  else docReadAloudStart();
});
$("doc-read-stop")?.addEventListener("click", () => docReadAloudStop());
//: Leaving the page stops the voice: speech outlives the tab otherwise.
window.addEventListener("pagehide", () => docReadAloudStop());

//: One hook in `docCmExtensions` for every tool in this region.
function docProseToolExtensions(CM) {
  //: Autofill's pairs, smart punctuation and ghost text (the section after
  //: this region).
  return [docSuggestExtensions(CM), docReadAloudExtension(CM), docProseFillExtensions(CM)];
}
// PROSE-TOOLS-END

// =============================================================================
// Autofill for prose (the owner, 2026-09-24)
// =============================================================================
//
// "I want cool features for autofill and easy life stuff in the documents
// editor like if I type lorem and press enter or a popup that appears, then it
// will autofill the lorem ipsum filler text and stuff."
//
// The code side already had this (Emmet, snippets, the list and its ghost text
// in documents-code.js). Prose had word suggestions and nothing that *made*
// text. What is added, all offered through the one popup prose already had
// (`#doc-complete-list`, `renderDocComplete` in documents.js), so there is
// still one list at the caret, never two:
//
// - **Expansions**: `lorem` (a paragraph), `lorem20` (twenty words),
//   `table 3x4` (three columns, four rows; `/table 3x4` too), and, on a line of
//   their own, `today`, `date`, `now`, `time`, `iso`, `todo`, `callout`, `hr`,
//   `toc` (the headings as links) and `sig` (the name from Settings). Tab or
//   Enter takes the chosen row; its first line is drawn after the caret in
//   muted ink first, as the code side's ghost text is.
// - **`:emoji:` shortcodes**: a colon and two letters open the list with the
//   glyphs, which is the picker.
// - **Pairs as you type**: `**`, `_`, backticks and brackets close themselves,
//   step over their closer and wrap a selection; Backspace in an empty pair
//   takes both halves.
// - **Smart quotes and dashes**, off unless switched on in Settings,
//   Preferences (the app's own no-em-dash rule is about the app's copy, not the
//   writer's).
//
// **Why a bare word only counts on a line of its own.** `now`, `date`, `todo`
// and `hr` are words people write. Offered after any occurrence, Enter at the
// end of "I will do it now" would stamp a time into the sentence. A line that
// is nothing but `now` is somebody asking. `lorem` and the shortcodes are not
// words anyone writes by accident, so they count anywhere.
//
// List continuation on Enter and outdent on an empty item were already there:
// the markdown package's own keymap (`insertNewlineContinueMarkup`,
// `deleteMarkupBackward`), which `markdown()` installs by default. Measured,
// not rebuilt (`scratchpad/ui-sweeps/proseautofill.js`).
//
// The pure half is the region below: `tests/test_prose_autofill.py` runs it in
// node and holds every expansion to the exact text it must produce.

// PROSE-FILL-BEGIN (tests/test_prose_autofill.py runs this region in node)
const DOC_LOREM_TEXT =
  "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor " +
  "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud " +
  "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure " +
  "dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. " +
  "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt " +
  "mollit anim id est laborum.";

//: A thousand words is a lot of filler and still a string the editor inserts in
//: one frame; `lorem9999` is a typo, not a request for a novel.
const DOC_LOREM_MAX_WORDS = 1000;

//: `count` words of filler, as a sentence with a capital and a full stop; no
//: count (or zero) is the whole paragraph.
function docLorem(count) {
  if (!count) return DOC_LOREM_TEXT;
  const words = DOC_LOREM_TEXT.replace(/[.,]/g, "").toLowerCase().split(" ");
  const n = Math.min(count, DOC_LOREM_MAX_WORDS);
  const out = [];
  for (let i = 0; i < n; i += 1) out.push(words[i % words.length]);
  out[0] = out[0][0].toUpperCase() + out[0].slice(1);
  return `${out.join(" ")}.`;
}

//: The local day as YYYY-MM-DD, built by hand for the reason `docTemplateFill`
//: gives: `toISOString` is UTC and names yesterday east of Greenwich after dark.
function docIsoDay(now) {
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

//: A date in the writer's locale. `locale` undefined is the browser's own,
//: which is the point; the tests pass one so the answer is fixed.
function docFillDate(kind, now, locale) {
  const loc = locale || undefined;
  if (kind === "today") return now.toLocaleDateString(loc, { year: "numeric", month: "long", day: "numeric" });
  if (kind === "date") return now.toLocaleDateString(loc, { year: "numeric", month: "2-digit", day: "2-digit" });
  if (kind === "time") return now.toLocaleTimeString(loc, { hour: "numeric", minute: "2-digit" });
  if (kind === "now") {
    return now.toLocaleString(loc, {
      year: "numeric", month: "long", day: "numeric", hour: "numeric", minute: "2-digit",
    });
  }
  return docIsoDay(now);
}

//: A GFM table, the same shape the toolbar's Table makes (`applyMarkdown`'s
//: `custom: "table"`): "Column" headers and blank cells with their outer pipes,
//: so every cell is one GFM can see. `select` is the first header, chosen, so
//: typing names it.
function docFillTable(cols, rows) {
  const c = Math.max(1, Math.min(12, cols));
  const r = Math.max(1, Math.min(50, rows));
  const line = (cell) => `| ${Array(c).fill(cell).join(" | ")} |`;
  const lines = [line("Column"), line("---")];
  for (let i = 0; i < r; i += 1) lines.push(`|${"  |".repeat(c)}`);
  return { text: `${lines.join("\n")}\n`, select: [2, 2 + "Column".length] };
}

//: The document's headings as a nested list of links, each to the id the
//: renderer gives that heading (`slug`, which is markdown.js's `mdHeadingId` in the
//: browser, so a link here is the anchor there). A lone first-level heading at
//: the top is the document's title, not a section of it, and is left out.
//: Null when there is nothing to list.
function docFillToc(text, slug) {
  const heads = [];
  let fence = null;
  for (const line of String(text || "").split("\n")) {
    const open = /^\s{0,3}(`{3,}|~{3,})/.exec(line);
    if (open) {
      if (!fence) fence = open[1][0];
      else if (open[1][0] === fence) fence = null;
      continue;
    }
    if (fence) continue;
    const m = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (m) heads.push([m[1].length, m[2]]);
  }
  if (heads.length && heads[0][0] === 1 && heads.filter(([l]) => l === 1).length === 1) heads.shift();
  if (!heads.length) return null;
  const top = Math.min(...heads.map(([l]) => l));
  const taken = new Set();
  const plain = (t) => t.replace(/\[([^[\]\n]*)\]\([^()\n]*\)/g, "$1").replace(/[`*_~]/g, "");
  const lines = heads.map(([l, t]) => `${"  ".repeat(l - top)}- [${plain(t)}](#${slug(t, taken)})`);
  return `${lines.join("\n")}\n`;
}

//: A sign-off: a line, then the name from Settings. The break is a blank line
//: because a single newline inside a paragraph renders as a space. With no
//: name set the placeholder is chosen, so typing replaces it.
function docFillSig(name) {
  const who = String(name || "").trim();
  const head = "Kind regards,\n\n";
  if (who) return { text: `${head}${who}\n`, detail: who };
  return {
    text: `${head}Your name\n`,
    select: [head.length, head.length + "Your name".length],
    detail: "Your name (set it in Settings)",
  };
}

//: The shortcodes, GitHub's names. One string, `name=glyph,` per entry, parsed
//: once: a table of a few hundred glyphs is data, and a string whose every edge
//: is a letter or a comma is not a glyph standing where an icon belongs
//: (`tests/test_no_glyph_icons.py` reads string edges).
const DOC_EMOJI_SOURCE =
  "smile=\u{1F604},grin=\u{1F601},joy=\u{1F602},rofl=\u{1F923},smiley=\u{1F603},laughing=\u{1F606}," +
  "sweat_smile=\u{1F605},wink=\u{1F609},blush=\u{1F60A},innocent=\u{1F607},slightly_smiling_face=\u{1F642}," +
  "upside_down_face=\u{1F643},heart_eyes=\u{1F60D},star_struck=\u{1F929},kissing_heart=\u{1F618},yum=\u{1F60B}," +
  "stuck_out_tongue=\u{1F61B},zany_face=\u{1F92A},hugs=\u{1F917},thinking=\u{1F914},shushing_face=\u{1F92B}," +
  "zipper_mouth_face=\u{1F910},raised_eyebrow=\u{1F928},neutral_face=\u{1F610},expressionless=\u{1F611}," +
  "no_mouth=\u{1F636},smirk=\u{1F60F},unamused=\u{1F612},roll_eyes=\u{1F644},grimacing=\u{1F62C}," +
  "relieved=\u{1F60C},pensive=\u{1F614},sleepy=\u{1F62A},sleeping=\u{1F634},mask=\u{1F637}," +
  "nerd_face=\u{1F913},face_with_monocle=\u{1F9D0},sunglasses=\u{1F60E},partying_face=\u{1F973}," +
  "cowboy_hat_face=\u{1F920},confused=\u{1F615},worried=\u{1F61F},slightly_frowning_face=\u{1F641}," +
  "open_mouth=\u{1F62E},astonished=\u{1F632},flushed=\u{1F633},pleading_face=\u{1F97A},cry=\u{1F622}," +
  "sob=\u{1F62D},scream=\u{1F631},exploding_head=\u{1F92F},cold_sweat=\u{1F630},hot_face=\u{1F975}," +
  "cold_face=\u{1F976},woozy_face=\u{1F974},confounded=\u{1F616},tired_face=\u{1F62B},yawning_face=\u{1F971}," +
  "triumph=\u{1F624},rage=\u{1F621},angry=\u{1F620},money_mouth_face=\u{1F911},skull=\u{1F480}," +
  "poop=\u{1F4A9},clown_face=\u{1F921},ghost=\u{1F47B},alien=\u{1F47D},robot=\u{1F916}," +
  "see_no_evil=\u{1F648},hear_no_evil=\u{1F649},speak_no_evil=\u{1F64A},wave=\u{1F44B},raised_hand=✋," +
  "ok_hand=\u{1F44C},v=✌️,crossed_fingers=\u{1F91E},point_up=☝️,point_right=\u{1F449}," +
  "point_left=\u{1F448},point_down=\u{1F447},thumbsup=\u{1F44D},+1=\u{1F44D},thumbsdown=\u{1F44E},-1=\u{1F44E}," +
  "fist=\u{1F44A},clap=\u{1F44F},raised_hands=\u{1F64C},open_hands=\u{1F450},pray=\u{1F64F}," +
  "handshake=\u{1F91D},muscle=\u{1F4AA},writing_hand=✍️,eyes=\u{1F440},brain=\u{1F9E0}," +
  "heart=❤️,orange_heart=\u{1F9E1},yellow_heart=\u{1F49B},green_heart=\u{1F49A},blue_heart=\u{1F499}," +
  "purple_heart=\u{1F49C},black_heart=\u{1F5A4},broken_heart=\u{1F494},sparkling_heart=\u{1F496}," +
  "100=\u{1F4AF},boom=\u{1F4A5},sparkles=✨,star=⭐,star2=\u{1F31F},dizzy=\u{1F4AB},fire=\u{1F525}," + // unslop-ignore: :shortcode: data, not icons
  "zap=⚡,rainbow=\u{1F308},sunny=☀️,cloud=☁️,umbrella=☂️,snowflake=❄️," + // unslop-ignore
  "droplet=\u{1F4A7},ocean=\u{1F30A},earth_africa=\u{1F30D},seedling=\u{1F331},evergreen_tree=\u{1F332}," +
  "deciduous_tree=\u{1F333},four_leaf_clover=\u{1F340},rose=\u{1F339},sunflower=\u{1F33B}," +
  "cherry_blossom=\u{1F338},apple=\u{1F34E},banana=\u{1F34C},avocado=\u{1F951},pizza=\u{1F355}," +
  "hamburger=\u{1F354},taco=\u{1F32E},cake=\u{1F370},birthday=\u{1F382},coffee=☕,tea=\u{1F375}," +
  "beer=\u{1F37A},wine_glass=\u{1F377},tada=\u{1F389},confetti_ball=\u{1F38A},balloon=\u{1F388}," +
  "gift=\u{1F381},trophy=\u{1F3C6},medal_sports=\u{1F3C5},soccer=⚽,basketball=\u{1F3C0},dart=\u{1F3AF}," +
  "video_game=\u{1F3AE},musical_note=\u{1F3B5},headphones=\u{1F3A7},art=\u{1F3A8},camera=\u{1F4F7}," +
  "movie_camera=\u{1F3A5},tv=\u{1F4FA},computer=\u{1F4BB},keyboard=⌨️,iphone=\u{1F4F1}," +
  "phone=☎️,bulb=\u{1F4A1},flashlight=\u{1F526},book=\u{1F4D6},books=\u{1F4DA},notebook=\u{1F4D3}," +
  "memo=\u{1F4DD},pencil2=✏️,pen=\u{1F58A}️,paperclip=\u{1F4CE},pushpin=\u{1F4CC}," +
  "scissors=✂️,calendar=\u{1F4C5},clipboard=\u{1F4CB},file_folder=\u{1F4C1}," +
  "chart_with_upwards_trend=\u{1F4C8},chart_with_downwards_trend=\u{1F4C9},bar_chart=\u{1F4CA}," +
  "email=\u{1F4E7},envelope=✉️,inbox_tray=\u{1F4E5},outbox_tray=\u{1F4E4},package=\u{1F4E6}," +
  "bell=\u{1F514},mega=\u{1F4E3},lock=\u{1F512},unlock=\u{1F513},key=\u{1F511},hammer=\u{1F528}," +
  "wrench=\u{1F527},gear=⚙️,link=\u{1F517},mag=\u{1F50D},hourglass=⌛,alarm_clock=⏰," +
  "watch=⌚,money_with_wings=\u{1F4B8},moneybag=\u{1F4B0},dollar=\u{1F4B5},credit_card=\u{1F4B3}," +
  "rocket=\u{1F680},airplane=✈️,car=\u{1F697},bike=\u{1F6B2},train=\u{1F686},house=\u{1F3E0}," +
  "office=\u{1F3E2},school=\u{1F3EB},hospital=\u{1F3E5},globe_with_meridians=\u{1F310}," +
  "world_map=\u{1F5FA}️,round_pushpin=\u{1F4CD},warning=⚠️,no_entry=⛔,x=❌," + // unslop-ignore
  "heavy_check_mark=✔️,white_check_mark=✅,ballot_box_with_check=☑️," + // unslop-ignore
  "question=❓,exclamation=❗,bangbang=‼️,heavy_plus_sign=➕,heavy_minus_sign=➖," +
  "arrow_right=➡️,arrow_left=⬅️,arrow_up=⬆️,arrow_down=⬇️," +
  "recycle=♻️,red_circle=\u{1F534},green_circle=\u{1F7E2},yellow_circle=\u{1F7E1}," +
  "blue_circle=\u{1F535},white_circle=⚪,black_circle=⚫,cat=\u{1F431},dog=\u{1F436}," +
  "fox_face=\u{1F98A},bear=\u{1F43B},panda_face=\u{1F43C},unicorn=\u{1F984},bee=\u{1F41D}," +
  "butterfly=\u{1F98B},turtle=\u{1F422},snake=\u{1F40D},octopus=\u{1F419},whale=\u{1F433}," +
  "penguin=\u{1F427},owl=\u{1F989},bug=\u{1F41B},checkered_flag=\u{1F3C1},triangular_flag_on_post=\u{1F6A9},";

let docEmojiTable = null;

//: `[name, glyph]` pairs, parsed on first use.
function docEmojiList() {
  if (!docEmojiTable) {
    docEmojiTable = DOC_EMOJI_SOURCE.split(",").filter(Boolean).map((pair) => {
      const at = pair.indexOf("=");
      return [pair.slice(0, at), pair.slice(at + 1)];
    });
  }
  return docEmojiTable;
}

//: The shortcodes matching what was typed after the colon: names that start
//: with it first, then names with a later word that starts with it (`:heart`
//: finds `broken_heart`), at most `limit`.
function docEmojiMatches(query, limit = 8) {
  const q = String(query || "").toLowerCase();
  if (!q) return [];
  const all = docEmojiList();
  //: The exact name first, then the shorter: `:heart` is the heart, not
  //: `heart_eyes` because it happens to come first in the table.
  const starts = all
    .filter(([name]) => name.startsWith(q))
    .sort((a, b) => (a[0] !== q) - (b[0] !== q) || a[0].length - b[0].length);
  const words = all.filter(([name]) => !name.startsWith(q) && name.split("_").some((w) => w.startsWith(q)));
  return [...starts, ...words].slice(0, limit);
}

//: The words that expand only on a line of their own (this section's header
//: says why).
const DOC_FILL_LINE_WORDS = new Set(["today", "date", "now", "time", "iso", "todo", "callout", "hr", "toc", "sig"]);

//: **What the caret is at the end of, if it is something that expands.**
//: `before` and `after` are the caret's line either side of it. Null inside a
//: word (a caret in "lor|em" is somebody fixing a letter), and for anything
//: that is not a trigger. `start` is the column the replacement begins at.
function docFillToken(before, after) {
  if (after && /^[\w:]/.test(after)) return null;
  let m = /(^|[\s(])(:([a-z0-9_+-]{2,}))$/i.exec(before);
  if (m) return { kind: "emoji", start: before.length - m[2].length, query: m[3] };
  m = /(^|\s)(lorem(\d{0,4}))$/.exec(before);
  if (m) return { kind: "lorem", start: before.length - m[2].length, count: Number(m[3]) || 0, token: m[2] };
  if (!after.trim()) {
    m = /^(\s*)(\/?table ?(\d{1,2})x(\d{1,2}))$/.exec(before);
    if (m) return { kind: "table", start: m[1].length, cols: Number(m[3]), rows: Number(m[4]), token: m[2] };
    m = /^(\s*)([a-z]+)$/.exec(before);
    if (m && DOC_FILL_LINE_WORDS.has(m[2])) return { kind: m[2], start: m[1].length, token: m[2] };
  }
  return null;
}

//: **The rows the list offers for a token**: each `{label, detail, text}`,
//: with `select` ([from, to] inside `text`) when part of it should be chosen
//: after it lands. `ctx` is `{now, locale, name, doc, slug}`: everything that
//: is not the token, passed in so this stays a pure function.
function docFillOptions(tok, ctx) {
  if (!tok) return [];
  const now = ctx.now || new Date();
  const date = (kind) => docFillDate(kind, now, ctx.locale);
  switch (tok.kind) {
    case "emoji":
      return docEmojiMatches(tok.query).map(([name, glyph]) => ({
        label: `:${name}:`, detail: "", glyph, text: glyph,
      }));
    case "lorem": {
      const detail = tok.count
        ? `${Math.min(tok.count, DOC_LOREM_MAX_WORDS)} words of filler text`
        : "A paragraph of filler text";
      return [{ label: tok.token, detail, text: docLorem(tok.count) }];
    }
    case "table": {
      const t = docFillTable(tok.cols, tok.rows);
      const c = Math.max(1, Math.min(12, tok.cols));
      const r = Math.max(1, Math.min(50, tok.rows));
      const detail = `A table, ${c} column${c === 1 ? "" : "s"} by ${r} row${r === 1 ? "" : "s"}`;
      return [{ label: tok.token, detail, text: t.text, select: t.select }];
    }
    case "today":
      return [
        { label: "today", detail: date("today"), text: date("today") },
        { label: "today", detail: date("iso"), text: date("iso") },
      ];
    case "date":
      return [
        { label: "date", detail: date("date"), text: date("date") },
        { label: "date", detail: date("today"), text: date("today") },
        { label: "date", detail: date("iso"), text: date("iso") },
      ];
    case "now":
      return [{ label: "now", detail: date("now"), text: date("now") }];
    case "time":
      return [{ label: "time", detail: date("time"), text: date("time") }];
    case "iso":
      return [{ label: "iso", detail: date("iso"), text: date("iso") }];
    case "todo":
      return [{ label: "todo", detail: "A task to tick", text: "- [ ] " }];
    case "hr":
      return [{ label: "hr", detail: "A divider", text: "---\n" }];
    case "callout":
      return [
        { label: "callout", detail: "A note box", text: "> [!note]\n> " },
        { label: "callout", detail: "A tip box", text: "> [!tip]\n> " },
        { label: "callout", detail: "A warning box", text: "> [!warning]\n> " },
      ];
    case "toc": {
      const toc = docFillToc(ctx.doc, ctx.slug);
      if (!toc) return [];
      const n = toc.trim().split("\n").length;
      return [{ label: "toc", detail: `Contents, ${n} heading${n === 1 ? "" : "s"}`, text: toc }];
    }
    case "sig": {
      const sig = docFillSig(ctx.name);
      return [{ label: "sig", detail: sig.detail, text: sig.text, select: sig.select }];
    }
    default:
      return [];
  }
}

//: What the ghost after the caret shows for a row: the first line of what it
//: would write, cut to a glance.
function docFillGhost(option) {
  const first = String(option.text || "").split("\n")[0];
  return first.length > 48 ? `${first.slice(0, 47)}…` : first;
}

//: A letter or a digit in any script, for the pairs below.
const DOC_WORD_CHAR = /[\p{L}\p{N}]/u;

//: **Smart quotes and dashes, for one typed character.** Returns
//: `{back, insert}` (how many characters before the caret to replace, and with
//: what) or null to type the character as it is. A quote opens after a space,
//: an opening bracket or a dash, and closes anywhere else, which also makes the
//: one in `don't` an apostrophe. Two hyphens become an em dash, the one dash
//: every word processor makes from them; never at the start of a line, where
//: `--` is on its way to a `---` divider or front matter, and never after a
//: pipe or a colon, where it is a table's rule. Inside `inline code` nothing
//: changes (an odd number of backticks before the caret).
function docSmartPunct(before, ch) {
  if (((before.match(/`/g) || []).length % 2) === 1) return null;
  if (ch === '"' || ch === "'") {
    const prev = before.slice(-1);
    const opens = !prev || /[\s([{\u2014\u2013-]/.test(prev);
    if (ch === '"') return { back: 0, insert: opens ? "“" : "”" };
    return { back: 0, insert: opens ? "‘" : "’" };
  }
  if (ch === "-" && before.endsWith("-")) {
    if (/^\s*-$/.test(before) || /[|:]\s*-$/.test(before) || before.endsWith("--")) return null;
    return { back: 1, insert: "\u2014" };
  }
  return null;
}

//: The characters that pair, and what closes each.
const DOC_PAIR_CLOSE = { "(": ")", "[": "]", "{": "}", "`": "`", "_": "_", "*": "*" };
const DOC_PAIR_CLOSERS = new Set([")", "]", "}"]);

//: **Pairs, for one typed character.** Returns `{insert, caret}` (the text
//: that replaces the selection and where in it the caret lands), `{insert,
//: select}` (the part of it to select), `{step: 1}` (type nothing, move past
//: the closer) or null to type the character as it is; `removeAfter` is how
//: many characters after the caret go too. `markdown` is false for a plain
//: text file, which pairs brackets and nothing else.
//:
//: - A selection is wrapped, and stays selected, so `*` twice makes it bold.
//: - A bracket closes itself before a space, the end of the line or a closer;
//:   its closer typed in front of itself is stepped over. `[` typed inside an
//:   empty `[]` gives `[[` with no closers, because the `[[` link menu writes
//:   its own `]]` (editor.js's `editorRunItem`).
//: - A backtick pairs away from a word and never after another one, so three
//:   typed in a row are a fence, not a pair and a spare.
//: - `*` does not pair alone (a bullet, `2*3`); the second of two opens bold,
//:   `**|**`. `_` pairs alone away from a word (never in `snake_case`), and the
//:   second makes `__|__`. A third in an empty double pair is a divider
//:   (`***`), so the pairs collapse.
//: - The closer of an emphasis, typed after a word, steps over.
function docPairInput(before, after, ch, selected, markdown = true) {
  const next = after[0] || "";
  if (!(ch in DOC_PAIR_CLOSE)) {
    if (DOC_PAIR_CLOSERS.has(ch) && next === ch) return { step: 1 };
    return null;
  }
  const isBracket = ch === "(" || ch === "[" || ch === "{";
  if (!markdown && !isBracket) return null;
  const close = DOC_PAIR_CLOSE[ch];
  if (selected) return { insert: `${ch}${selected}${close}`, select: [1, 1 + selected.length] };
  const prev = before.slice(-1);
  const prev2 = before.slice(-2, -1);
  const clear = !next || /[\s)\]}.,;:!?]/.test(next);
  const opening = (c) => !c || /[\s([{>"'“‘]/.test(c);
  if (isBracket) {
    if (ch === "[" && prev === "[" && next === "]") return { insert: "[", caret: 1, removeAfter: 1 };
    if (!clear) return null;
    return { insert: `${ch}${close}`, caret: 1 };
  }
  if (ch === "`") {
    if (next === "`") return { step: 1 };
    if (prev === "`" || DOC_WORD_CHAR.test(prev) || !clear) return null;
    return { insert: "``", caret: 1 };
  }
  // `*` and `_`.
  if (next === ch) {
    if (before.endsWith(ch + ch) && after.startsWith(ch + ch) && opening(before.slice(-3, -2))) {
      return { insert: ch, caret: 1, removeAfter: 2 };
    }
    if (prev === ch && opening(prev2)) return { insert: ch + ch, caret: 1 };
    if (prev && !/\s/.test(prev)) return { step: 1 };
    return null;
  }
  if (!clear) return null;
  if (ch === "*") return prev === "*" && opening(prev2) ? { insert: "***", caret: 1 } : null;
  return opening(prev) ? { insert: "__", caret: 1 } : null;
}

//: Backspace between the two halves of an empty pair takes both. Returns how
//: many characters to delete on each side, or 0 to leave Backspace alone.
function docPairBackspace(before, after) {
  const prev = before.slice(-1);
  const next = after[0];
  if (!prev || !next || DOC_PAIR_CLOSE[prev] !== next) return 0;
  if (prev === "*" && !(before.endsWith("**") && after.startsWith("**"))) return 0;
  return 1;
}
//: **Enter on an empty list item ends the list, or steps it out one level.**
//: The markdown keymap's own answer (`insertNewlineContinueMarkup`) to an
//: empty item in a tight list is to make the list loose: measured, `- [ ] Buy
//: milk`, Enter, Enter left `- [ ] Buy milk`, a blank line and a fresh empty
//: item, so leaving a list took three presses and changed its spacing on the
//: way. Every editor the owner compares this with ends the list on the second
//: Enter. Returns the line's new text, or null when the line is not an empty
//: item (the keymap's continuation then runs as before).
function docListEnter(line) {
  const m = /^(\s*)(?:[-*+]|\d{1,9}[.)])(?: \[[ xX]\])? ?$/.exec(line);
  if (!m) return null;
  const indent = m[1];
  if (!indent) return "";
  //: One level out: a tab, or four spaces where the indent is in fours, or two.
  if (indent.endsWith("\t")) return line.slice(1);
  const step = indent.length >= 4 && indent.length % 4 === 0 ? 4 : 2;
  return line.slice(Math.min(step, indent.length));
}
//: **Ending a list leaves the blank line after it** (dog2 item 6). The empty
//: item became an empty line directly under the last item, so a heading or a
//: fence typed next sat flush against the list. `next` is `docListEnter`'s
//: answer and `prev` the line above; only a top-level exit under a real line
//: gets the extra newline, so the caret lands one line below a blank one.
function docListExitText(next, prev) {
  return next === "" && typeof prev === "string" && prev.trim() !== "" ? "\n" : next;
}
//: **Retyping "- " on an auto-bullet does not nest** (dogfood item 3). `before`
//: is the line up to the caret with the dash already typed ("- -"), `typed`
//: the space. Returns the line to keep ("- "), or null.
function docBulletRetype(before, typed) {
  if (typed !== " ") return null;
  const m = /^(\s*)([-*+]) [-*+]$/.exec(before);
  return m ? `${m[1]}${m[2]} ` : null;
}

//: **A closing fence goes back to the opening fence's indent** (dogfood item
//: 4: Enter kept the code's indent). `above` is the lines before, `line` the
//: current one. Returns the indent it should have, or null.
function docFenceCloseIndent(above, line) {
  const close = /^(\s*)(`{3,}|~{3,})$/.exec(line);
  if (!close) return null;
  let open = null;
  for (const text of above) {
    const f = /^(\s*)(`{3,}|~{3,})(.*)$/.exec(text);
    if (!f) continue;
    if (!open) {
      if (f[2][0] === "`" && f[3].includes("`")) continue;
      open = { indent: f[1], ch: f[2][0], len: f[2].length };
    } else if (f[2][0] === open.ch && f[2].length >= open.len && !f[3].trim()) {
      open = null;
    }
  }
  if (!open || close[2][0] !== open.ch || close[2].length < open.len) return null;
  return close[1] === open.indent ? null : open.indent;
}
// PROSE-FILL-END

//: Whether the open document is prose for these purposes: markdown and plain
//: text, never a code file (which has its own list) or CSV.
function docProseFillOn() {
  if (typeof docFileType !== "function") return false;
  const ext = docFileType().ext;
  return ext === "md" || ext === "txt";
}

//: The Settings switch; off unless turned on.
function docSmartPunctOn() {
  return typeof prefsCache === "object" && !!prefsCache && prefsCache.smart_punctuation === true;
}

//: Inside a fenced or indented code block, inline code or raw HTML, by the
//: parse. The pure functions above see one line; this is the part only the
//: tree knows.
function docInCodeAt(CM, state, pos, anyHost = false) {
  if (!anyHost && docFileType().ext !== "md") return false;
  let node = CM.language.syntaxTree(state).resolveInner(pos, -1);
  for (let k = 0; node && k < 6; node = node.parent, k += 1) {
    if (/^(FencedCode|CodeBlock|InlineCode|CodeText|HTMLBlock)$/.test(node.name)) return true;
  }
  return false;
}

//: **The one typed-character hook for the pairs and the smart punctuation.**
//: An input handler rather than a keymap because it has to see the character
//: after the keyboard layout has made it (a `"` is Shift+2 on some layouts and
//: its own key on others). Never during an IME composition, never in a code
//: file, never inside code.
function docProseInputHandler(CM) {
  return CM.view.EditorView.inputHandler.of((view, from, to, text) => {
    if (view.composing || text.length !== 1 || !docProseFillOn()) return false;
    const state = view.state;
    if (state.selection.ranges.length > 1) return false;
    const line = state.doc.lineAt(from);
    if (to > line.to) return false;
    const before = line.text.slice(0, from - line.from);
    const after = line.text.slice(to - line.from);
    const markdown = docFileType().ext === "md";
    if (markdown && docInCodeAt(CM, state, from)) return false;
    const pair = docPairInput(before, after, text, state.sliceDoc(from, to), markdown);
    if (pair) {
      if (pair.step) {
        view.dispatch({ selection: { anchor: from + pair.step }, userEvent: "input.type" });
        return true;
      }
      const selection = pair.select
        ? { anchor: from + pair.select[0], head: from + pair.select[1] }
        : { anchor: from + pair.caret };
      view.dispatch({
        changes: { from, to: to + (pair.removeAfter || 0), insert: pair.insert },
        selection,
        userEvent: "input.type",
      });
      return true;
    }
    if (from === to && docSmartPunctOn()) {
      const smart = docSmartPunct(before, text);
      if (smart) {
        const start = from - smart.back;
        view.dispatch({
          changes: { from: start, to, insert: smart.insert },
          selection: { anchor: start + smart.insert.length },
          userEvent: "input.type",
        });
        return true;
      }
    }
    return false;
  });
}

//: The ghost after the caret: the rest of the chosen word, or the first line
//: of what the chosen expansion would write. Set by `renderDocComplete` in
//: documents.js through `docProseGhostSet`, which asks the view to repaint on
//: the next microtask (it is called from inside the view's own update, where a
//: dispatch is refused).
let docProseGhost = null;
let docProseGhostEffect = null;
let docProseGhostCache = null;

function docProseGhostSet(pos, text) {
  const next = pos === null || !text ? null : { pos, text };
  const same = (a, b) => (!a && !b) || (a && b && a.pos === b.pos && a.text === b.text);
  if (same(docProseGhost, next)) return;
  docProseGhost = next;
  if (!docProseGhostEffect || typeof docCmView === "undefined" || !docCmView) return;
  queueMicrotask(() => {
    try {
      docCmView?.dispatch({ effects: docProseGhostEffect.of(null) });
    } catch {
      /* the view was swapped between the call and the microtask */
    }
  });
}

function docProseGhostPlugin(CM) {
  if (docProseGhostCache) return docProseGhostCache;
  const { Decoration, ViewPlugin, WidgetType } = CM.view;
  docProseGhostEffect = CM.state.StateEffect.define();
  class Ghost extends WidgetType {
    constructor(text) {
      super();
      this.text = text;
    }
    eq(other) {
      return other.text === this.text;
    }
    toDOM() {
      const span = document.createElement("span");
      //: The code side's own class, so the two ghosts are one look.
      span.className = "cm-ghostText";
      span.setAttribute("aria-hidden", "true");
      span.textContent = this.text;
      return span;
    }
    ignoreEvent() {
      return true;
    }
  }
  const build = (state) => {
    const g = docProseGhost;
    const range = state.selection.main;
    if (!g || !range.empty || range.head !== g.pos || g.pos > state.doc.length) return Decoration.none;
    return Decoration.set([Decoration.widget({ widget: new Ghost(g.text), side: 1 }).range(g.pos)]);
  };
  docProseGhostCache = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = build(view.state);
      }
      update(update) {
        this.decorations = build(update.state);
      }
    },
    { decorations: (plugin) => plugin.decorations }
  );
  return docProseGhostCache;
}

//: Backspace in an empty pair, and Enter on an empty list item, ahead of the
//: editor's own.
function docProsePairKeymap(CM, anyHost = false) {
  return CM.state.Prec.high(CM.view.keymap.of([{
    key: "Enter",
    run: (view) => {
      if (!anyHost && (!docProseFillOn() || docFileType().ext !== "md")) return false;
      const range = view.state.selection.main;
      if (!range.empty || view.state.selection.ranges.length > 1) return false;
      const line = view.state.doc.lineAt(range.head);
      if (range.head !== line.to || docInCodeAt(CM, view.state, range.head, anyHost)) return false;
      const exit = docListEnter(line.text);
      if (exit === null) return false;
      const next = docListExitText(exit, line.number > 1 ? view.state.doc.line(line.number - 1).text : null);
      view.dispatch({
        changes: { from: line.from, to: line.to, insert: next },
        selection: { anchor: line.from + next.length },
        userEvent: "input",
      });
      return true;
    },
  }, {
    key: "Backspace",
    run: (view) => {
      if (!docProseFillOn()) return false;
      const range = view.state.selection.main;
      if (!range.empty || view.state.selection.ranges.length > 1) return false;
      const line = view.state.doc.lineAt(range.head);
      const col = range.head - line.from;
      const n = docPairBackspace(line.text.slice(0, col), line.text.slice(col));
      if (!n) return false;
      view.dispatch({
        changes: { from: range.head - n, to: range.head + n },
        selection: { anchor: range.head - n },
        userEvent: "delete.backward",
      });
      return true;
    },
  }]));
}

//: **List and fence typing, for documents and note boxes.** A note has no file
//: type, and a fence being closed is inside the block the parse sees as open,
//: so neither guard applies. Enter on an empty item is the document's own
//: (`docProsePairKeymap`); notes get it here.
function docListFenceExtensions(CM, inDocument) {
  //: A document only in markdown; a note box always (it has no file type).
  const on = () => !inDocument || (docProseFillOn() && docFileType().ext === "md");
  const input = CM.view.EditorView.inputHandler.of((view, from, to, text) => {
    if (view.composing || text.length !== 1 || !on()) return false;
    const state = view.state;
    if (state.selection.ranges.length > 1 || from !== to) return false;
    const line = state.doc.lineAt(from);
    if (to !== line.to) return false;
    const before = line.text.slice(0, from - line.from);
    const dup = docBulletRetype(before, text);
    if (dup !== null && !docInCodeAt(CM, state, from, true)) {
      view.dispatch({
        changes: { from: line.from + dup.length, to: from },
        selection: { anchor: line.from + dup.length },
        userEvent: "input.type",
      });
      return true;
    }
    if (text === "`" || text === "~") {
      const above = [];
      for (let n = 1; n < line.number; n += 1) above.push(state.doc.line(n).text);
      const indent = docFenceCloseIndent(above, before + text);
      if (indent !== null) {
        const lead = /^\s*/.exec(line.text)[0].length;
        view.dispatch({
          changes: [{ from: line.from, to: line.from + lead, insert: indent }, { from, insert: text }],
          selection: { anchor: from + indent.length - lead + 1 },
          userEvent: "input.type",
        });
        return true;
      }
    }
    return false;
  });
  return inDocument ? [input] : [input, docProsePairKeymap(CM, true)];
}

//: Everything above, as one set of extensions for `docProseToolExtensions`.
function docProseFillExtensions(CM) {
  return [docProseInputHandler(CM), docProseGhostPlugin(CM), docProsePairKeymap(CM), docListFenceExtensions(CM, true)];
}
