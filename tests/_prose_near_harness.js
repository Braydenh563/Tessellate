// Runs the page's own prose rule pass in node, once the old way (the whole text)
// and once the keystroke way (`docProse.rules` with `typing`, which reads the
// paragraph that was edited), over a scenario of edits. Used by
// tests/test_prose_near_1101.py. The page's functions are cut out of the source
// by name, so what is compared is the shipped code.
//
//   node tests/_prose_near_harness.js <repo root> <scenario.json>
//
// scenario: {docs: [{name, text, edits: [{find, offset, remove, insert}], window}], dictionary: [...]}
// prints JSON: {docs: [{name, steps: [{kind, zone, equal, only_near, only_full}], settled, window}]}
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(process.argv[2]);
const scenario = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
// A wrapped script (ranked row 37a) is cut as it was before its closure: the two closure
// lines off, the two-space indent back, the export line gone (`tests/_js_scope.py: unwrapped`).
function unwrapped(src) {
  const lines = src.split("\n");
  const first = lines.indexOf("(() => {");
  const last = lines.lastIndexOf("})();");
  if (first < 0 || last < 0) return src;
  const body = lines.slice(first + 1, last).map((l) => (l.startsWith("  ") ? l.slice(2) : l)).filter((l) => !/^Object\.assign\(window, \{ [\w$, ]+ \}\);$/.test(l));
  return [...lines.slice(0, first), ...body, ...lines.slice(last + 1)].join("\n");
}

const SOURCES = [
  // documents.js and the pieces split out of it (L335), joined: the first source is "the documents editor".
  ["documents.js", "documents-prose-check.js", "documents-suggest-panel.js", "documents-commands.js", "documents-templates.js", "documents-cm-load.js", "documents-tablemenu.js", "documents-preview.js", "documents-edit-keys.js", "documents-richpaste.js", "documents-block-ids.js", "documents-links-panels.js", "documents-save.js"],
  ["documents-prose.js"],
  ["prefs.js"],
  ["autocorrect.js"],
].map((names) => names.map((name) => unwrapped(fs.readFileSync(path.join(root, "frontend", "js", name), "utf8"))).join("\n"));

function declaration(name) {
  const head = new RegExp(`^(?:async function|function|const|let) ${name}\\b`, "m");
  for (const src of SOURCES) {
    const m = head.exec(src);
    if (!m) continue;
    const lines = src.slice(m.index).split("\n");
    const out = [];
    for (let i = 0; i < lines.length; i += 1) {
      out.push(lines[i]);
      const single = i === 0 && /;\s*(\/\/.*)?$/.test(lines[0]) && !/[{[(]\s*$/.test(lines[0]);
      if (single) break;
      if (i > 0 && /^(\}|\]|\)|\};|\];|\);|\}\)?;)\s*$/.test(lines[i])) break;
      if (i === 0 && /^function .*\}\s*$/.test(lines[0])) break;
    }
    return out.join("\n");
  }
  throw new Error(`declaration not found: ${name}`);
}

const NAMES = [
  "DOC_PROSE_RULES", "AUTOCORRECT_TYPOS", "autocorrectRefused", "autocorrectState", "autocorrectFind", "DOC_AUTOCORRECT", "DOC_LONG_SENTENCE_WORDS", "DOC_PROSE_SKIP", "docProseSkipMask",
  "docProseFindings", "docSpellable", "docWordKnown", "docSpellRoot", "docEditsOnce", "docSpellConfident",
  "docSpellLookup", "DOC_CONFIDENT_MIN", "DOC_ALPHABET", "DOC_EDIT_SWAP", "DOC_EDIT_DROP", "DOC_EDIT_ADD",
  "DOC_EDIT_SWAP_LETTER", "docMatchCase", "docWordlistReady", "DOC_VARIANT_LABEL", "DOC_PROSE_SKIP_LINK_TEXT",
  "docSpellNameKind", "docSpellTransposed", "DOC_STRUCTURAL_LINE", "docStructuralBlank", "nounCount",
  "DOC_PROSE_WINDOW_CHARS", "docProseWindow", "docProse",
];
const body = NAMES.map(declaration).join("\n\n");

const wordlist = new Set(
  fs.readFileSync(path.join(root, "frontend", "vendor", "wordlist", "en.txt"), "utf8").split("\n").map((w) => w.trim()).filter(Boolean)
);
const extraWords = /const DOC_EXTRA_WORDS = \[([\s\S]*?)\n\];/.exec(SOURCES[0]);
for (const w of extraWords ? extraWords[1].match(/"([^"]+)"/g) || [] : []) wordlist.add(w.slice(1, -1));

const factory = new Function(
  "__env",
  `"use strict";
  let docWordlist = __env.wordlist;
  let docSpellCache = new Map();
  const docProseIgnored = new Set();
  const currentDoc = null;
  const docDictionary = () => __env.dictionary;
  const docVariantLookup = () => new Map();
  const docSpellingVariant = () => "off";
  const docSpell = { answer: () => null, want: () => false, ownWordsSend: () => {}, dictionaryRow: () => ({}), packKey: () => "" };
  const docLoadWordlist = () => {};
  const docCheckLinkText = () => false;
  const docProseKey = (f) => f.rule + ":" + f.text.toLowerCase();
  const timers = [];
  const setTimeout = (fn) => { timers.push(fn); return timers.length; };
  const clearTimeout = (id) => { if (id) timers[id - 1] = null; };
  let docCmView = null;
  let current = "";
  let settled = 0;
  //: What the page's render does with the rules, and nothing else.
  const renderDocProse = () => { settled += 1; docProse.rules(current, false); };
  ${body}
  const calls = [];
  const real = docProseFindings;
  docProseFindings = function (text) { calls.push(text.length); return real(text); };
  return {
    docProse, docProseWindow, docProseSkipMask,
    full: (text) => real(text),
    take: () => calls.splice(0),
    set: (text) => { current = text; },
    view: (ranges) => { docCmView = { visibleRanges: ranges }; },
    flush: () => { for (const fn of timers.splice(0)) if (fn) fn(); },
    settled: () => settled,
  };`
);

const norm = (list) =>
  list.map((f) => `${f.start}-${f.end} ${f.rule} ${f.text} | ${f.message} | ${f.replacement}`).sort();

const out = { docs: [] };
for (const doc of scenario.docs) {
  const page = factory({ wordlist, dictionary: new Set((scenario.dictionary || []).map((w) => w.toLowerCase())) });
  let text = doc.text;
  page.set(text);
  page.docProse.typing = false;
  page.docProse.rules(text, false); // the pass that opened the document
  page.take();
  const result = { name: doc.name, steps: [] };
  for (const edit of doc.edits) {
    const base = edit.find === undefined ? 0 : text.indexOf(edit.find);
    if (base < 0) throw new Error(`marker not found: ${edit.find}`);
    const at = base + (edit.offset || 0);
    text = text.slice(0, at) + edit.insert + text.slice(at + edit.remove);
    page.set(text);
    page.docProse.typing = true;
    const near = page.docProse.rules(text, false);
    page.docProse.typing = false;
    const calls = page.take();
    const want = norm(page.full(text));
    page.take();
    const got = norm(near);
    result.steps.push({
      label: edit.label || "",
      zone: calls.length === 1 ? calls[0] : calls.length === 0 ? 0 : -calls.length,
      textLength: text.length,
      equal: JSON.stringify(got) === JSON.stringify(want),
      only_near: got.filter((x) => !want.includes(x)).slice(0, 5),
      only_full: want.filter((x) => !got.includes(x)).slice(0, 5),
      dirty: page.docProse.dirty,
    });
  }
  // The pause: the settle timer runs the page's own render, which is the full pass.
  const before = page.settled();
  page.flush();
  const settled = norm(page.docProse.memo.found);
  result.settled = {
    ran: page.settled() - before,
    equal: JSON.stringify(settled) === JSON.stringify(norm(page.full(text))),
    dirty: page.docProse.dirty,
  };
  page.take();
  // The window a long text is read through.
  if (doc.window) {
    page.view([{ from: doc.window.from, to: doc.window.to }]);
    const w = page.docProseWindow(text);
    result.window = w && { from: w.from, to: w.to, atLineStart: w.from === 0 || text[w.from - 1] === "\n", atLineEnd: w.to === text.length || text[w.to] === "\n" };
  }
  out.docs.push(result);
}
process.stdout.write(JSON.stringify(out));
process.exit(0);
