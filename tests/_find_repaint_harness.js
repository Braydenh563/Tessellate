// Runs the page's own findings plugin and its repaint call in node against a
// small fake of the engine, over a scenario of edits. Used by
// tests/test_find_repaint_1526.py. The page's functions are cut out of the
// source by name, so what is checked is the shipped code.
//
//   node tests/_find_repaint_harness.js <repo root>
//
// prints JSON: {kept: {...}, repaint: {...}}
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(process.argv[2]);
function unwrapped(src) {
  const lines = src.split("\n");
  const first = lines.indexOf("(() => {");
  const last = lines.lastIndexOf("})();");
  if (first < 0 || last < 0) return src;
  const body = lines.slice(first + 1, last).map((l) => (l.startsWith("  ") ? l.slice(2) : l)).filter((l) => !/^Object\.assign\(window, \{ [\w$, ]+ \}\);$/.test(l));
  return [...lines.slice(0, first), ...body, ...lines.slice(last + 1)].join("\n");
}

const SOURCE = ["documents.js", "documents-prose-check.js", "documents-suggest-panel.js", "documents-commands.js", "documents-templates.js", "documents-cm-load.js", "documents-tablemenu.js", "documents-preview.js", "documents-edit-keys.js", "documents-richpaste.js", "documents-block-ids.js", "documents-links-panels.js", "documents-save.js", "documents-view.js"]
  .map((f) => unwrapped(fs.readFileSync(path.join(root, "frontend", "js", f), "utf8")))
  .join("\n");

function declaration(name) {
  const head = new RegExp(`^(?:async function|function|const|let) ${name}\\b`, "m");
  const m = head.exec(SOURCE);
  if (!m) throw new Error(`declaration not found: ${name}`);
  const lines = SOURCE.slice(m.index).split("\n");
  const out = [];
  for (let i = 0; i < lines.length; i += 1) {
    out.push(lines[i]);
    if (i === 0 && /;\s*(\/\/.*)?$/.test(lines[0]) && !/[{[(]\s*$/.test(lines[0])) break;
    if (i > 0 && /^(\}|\]|\)|\};|\];|\);|\}\)?;)\s*$/.test(lines[i])) break;
  }
  return out.join("\n");
}

const body = ["DOC_FINDING_SKIP", "docFindingKind", "docProse", "docFindingsPluginCache", "docFindingsPlugin", "docCmRepaintFindings"]
  .map(declaration)
  .join("\n\n");

const factory = new Function(
  "__env",
  `"use strict";
  let docProseFound = __env.found;
  let docCmView = __env.view;
  let docFindingsEffect = __env.effect;
  const docStr = (doc) => doc.sliceString(0, doc.length);
  const DOC_ACCESS_RULES = new Set();
  const docProseIgnored = new Set();
  const docDictionary = () => new Set();
  const docSpellingVariant = () => "off";
  const docCheckLinkText = () => false;
  const docWordlist = null;
  const setTimeout = (fn) => { __env.frames.push(fn); return __env.frames.length; };
  const clearTimeout = (id) => { if (id) __env.frames[id - 1] = () => {}; };
  const document = { hidden: false };
  ${body}
  return { docProse, docFindingsPlugin, docCmRepaintFindings, found: () => docProseFound, set: (list) => { docProseFound = list; } };`
);

// A fake of the pieces of the engine the plugin touches.
const CM = {
  view: {
    Decoration: {
      mark: (spec) => ({ range: (from, to) => ({ from, to, spec }) }),
      set: (ranges) => ranges.slice().sort((a, b) => a.from - b.from),
    },
    ViewPlugin: { fromClass: (cls, spec) => ({ cls, spec }) },
  },
};
const fakeDoc = (text) => ({ length: text.length, sliceString: (from, to) => text.slice(from, to) });
// An insertion of `put` at `at` (and removal of `gone` characters), as a ChangeDesc answers mapPos.
function edit(text, at, gone, put) {
  const next = text.slice(0, at) + put + text.slice(at + gone);
  const shift = put.length - gone;
  const mapPos = (pos, assoc = -1) => {
    if (pos < at) return pos;
    if (pos > at + gone) return pos + shift;
    if (pos === at && gone === 0) return assoc > 0 ? pos + put.length : pos;
    return assoc > 0 ? at + put.length : at;
  };
  return { next, changes: { mapPos } };
}

const text0 = "Teh first line is here.\nA second line has recieve in it.\nThe third line is clean and the the end.";
const finding = (word, rule, nth = 0) => {
  let start = -1;
  for (let i = 0; i <= nth; i += 1) start = text0.indexOf(word, start + 1);
  return { rule, start, end: start + word.length, text: word, message: `${rule}: ${word}`, replacement: "x" };
};
const base = () => [finding("Teh", "spelling"), finding("recieve", "spelling"), finding("the the", "repeat")];

function plugin(found, text) {
  const dispatched = [];
  const frames = [];
  const view = { state: { doc: fakeDoc(text) }, visibleRanges: [{ from: 0, to: text.length }], dispatch: (spec) => dispatched.push(spec) };
  const effect = { of: (v) => ({ effect: true, v }), is: () => false };
  const api = factory({ found, view, effect, frames });
  return { api, view, dispatched, frames, effect };
}

const out = { kept: {}, repaint: {} };

// 1. An edit before the line: every underline keeps its word.
{
  const { api, view } = plugin(base(), text0);
  const p = api.docFindingsPlugin(CM);
  const inst = new p.cls(view);
  const before = inst.decorations.map((d) => text0.slice(d.from, d.to));
  const e = edit(text0, 0, 0, "Xx ");
  view.state.doc = fakeDoc(e.next);
  view.visibleRanges = [{ from: 0, to: e.next.length }];
  inst.update({ docChanged: true, viewportChanged: false, transactions: [], changes: e.changes, view });
  out.kept.before = before;
  out.kept.after = inst.decorations.map((d) => e.next.slice(d.from, d.to));
  out.kept.found = api.found().map((f) => e.next.slice(f.start, f.end) === f.text);
  // The edit lands inside a finding: that one goes, the others stay.
  const inside = edit(e.next, e.next.indexOf("recieve") + 2, 0, "Q");
  view.state.doc = fakeDoc(inside.next);
  view.visibleRanges = [{ from: 0, to: inside.next.length }];
  inst.update({ docChanged: true, viewportChanged: false, transactions: [], changes: inside.changes, view });
  out.kept.edited = inst.decorations.map((d) => inside.next.slice(d.from, d.to));
  // A letter typed right after a finding's last character does not stretch it, nor one at its start move it.
  const tail = edit(inside.next, inside.next.indexOf("Teh") + 3, 0, "s");
  view.state.doc = fakeDoc(tail.next);
  view.visibleRanges = [{ from: 0, to: tail.next.length }];
  inst.update({ docChanged: true, viewportChanged: false, transactions: [], changes: tail.changes, view });
  out.kept.tail = api.found().map((f) => [f.start, f.end]);
}

// 2. Answers that arrive in one frame are one dispatch; an unchanged list is none.
{
  const { api, dispatched, frames } = plugin(base(), text0);
  api.docCmRepaintFindings(true);
  api.docCmRepaintFindings(true);
  api.docCmRepaintFindings(true);
  out.repaint.beforeFrame = dispatched.length;
  out.repaint.frames = frames.length;
  frames.splice(0).forEach((fn) => fn());
  out.repaint.afterFrame = dispatched.length;
  api.docCmRepaintFindings(true);
  frames.splice(0).forEach((fn) => fn());
  out.repaint.unchanged = dispatched.length;
  api.set(base().slice(0, 2));
  api.docCmRepaintFindings(true);
  frames.splice(0).forEach((fn) => fn());
  out.repaint.changed = dispatched.length;
  api.set(base());
  api.docCmRepaintFindings();
  out.repaint.immediate = dispatched.length;
}
console.log(JSON.stringify(out));
