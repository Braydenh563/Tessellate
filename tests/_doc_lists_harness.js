// Runs the list-styles block of frontend/js/documents-cm.js (INBOX 1696 cc) against stubs, for
// tests/test_doc_lists_1696.py. Prints one JSON object.
//
//   node tests/_doc_lists_harness.js
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const src = fs.readFileSync(path.resolve(__dirname, "..", "frontend", "js", "documents-cm.js"), "utf8");
const block = src.slice(src.indexOf("// list-styles:begin"), src.indexOf("// list-styles:end"));
if (!block.includes("globalThis.docLists")) throw new Error("list-styles block missing");

const listeners = {};
const buttons = {};
const menus = [];
const state = { box: null, undoBreaks: 0, finished: 0, dispatched: null, view: null };
const ctx = {
  console, Math, Object, Array, Boolean, String,
  window: { addEventListener: (type, fn, capture) => { listeners[type] = { fn, capture }; } },
  document: {
    querySelector: (sel) => {
      const md = /data-md="(\w+)"/.exec(sel)?.[1];
      return (buttons[md] ||= { nextElementSibling: null, after(el) { this.nextElementSibling = el; } });
    },
  },
  kebabMenu: (items, label) => { const wrap = { items, label, classList: { add() {}, contains: (c) => c === "doc-list-styles" } }; menus.push(wrap); return wrap; },
  docSurfaceById: () => state.box,
  docUndoBreak: () => { state.undoBreaks += 1; },
  finishMarkdownEdit: () => { state.finished += 1; },
  get docCmView() { return state.view; },
};
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(block, ctx);
const L = ctx.docLists;

const out = {};
const doc = (lines) => lines.join("\n");

// The marker is the style.
out.bulletStyles = ["- a", "* a", "+ a", "-  a", "- [ ] a", "  * a", "-   a"].map((t) => L.bulletStyle(t));
out.parsed = ["1. a", "2) a", "a. a", "- a", "plain"].map((t) => { const p = L.parse(t); return p && [p.kind, p.style || null]; });

// Letters and roman numerals are lists only as a run.
const kinds = (lines) => L.classify(lines).map((c) => (c ? c.style : null));
out.alphaRun = kinds(["a. one", "b. two", "c. three"]);
out.romanRun = kinds(["i. one", "ii. two", "iii. three", "iv. four", "v. five"]);
out.alphaThroughI = kinds("abcdefghij".split("").map((c) => `${c}. x`));
out.romanAlone = kinds(["i. i"]);
out.lonely = kinds(["A. Smith wrote this", "b. not a start", "x. nor this"]);
out.sentence = kinds(["a. only one"]);

// Restyle a list at the caret, per list; nested levels and other lists keep theirs.
const base = ["Intro", "- one", "- two", "  - nested", "- three", "", "Other", "* keep", "* keep too"];
const r1 = L.restyle(base, 2, 2, "square");
out.square = { range: [r1.from, r1.to], lines: r1.lines };
const r2 = L.restyle(base, 1, 1, "dash");
out.dash = r2.lines;
const nums = L.restyle(["- one", "- two", "- three"], 0, 0, "roman");
out.roman = nums.lines;
out.alpha = L.restyle(["1. one", "2. two", "3. three"], 1, 1, "alpha").lines;
out.paren = L.restyle(["- one", "- two"], 0, 1, "paren").lines;
out.backToDots = L.restyle(["a. one", "b. two", "c. three"], 0, 0, "disc").lines;
out.taskKept = L.restyle(["- [ ] a", "- b"], 0, 1, "circle").lines;
out.looseList = L.restyle(["- a", "", "- b"], 0, 0, "square").lines;
out.newList = L.restyle(["alpha", "", "beta"], 0, 2, "decimal").lines;
const lists = ["- a", "- b", "", "* c", "", "1. x", "2. y", "", "1) p", "2) q"];
out.neighbourNumbers = L.restyle(lists, 5, 5, "roman");
out.neighbourDots = L.restyle(lists, 0, 0, "square");
out.neighbourBracket = L.restyle(lists, 9, 9, "alpha");
out.nestedOnly = L.restyle(["1. top", "   - sub", "   - sub two"], 1, 1, "circle").lines;

// A pasted look-alike marker at a line start becomes "- ".
out.paste = [
  "• one\n◦ two\n▪ three",
  "‐ a\n‑ b\n‒ c\n– d\n— e",
  "  • indented",
  "no marker • inside stays",
  "•nospace",
  "x\n• y",
].map((t) => L.pasteFix(t));
out.pasteMid = L.pasteFix("• first stays\n• second goes", false);

// The menus: one per button, a row per style, each writing through the editor's own box.
L.mount();
out.menus = menus.map((m) => ({ label: m.label, rows: m.items.map((i) => i.label), titles: m.items.map((i) => i.title) }));
const run = (menu, row, value, s, e) => {
  state.box = { value, selectionStart: s, selectionEnd: e, setSelectionRange(a, b) { this.selectionStart = a; this.selectionEnd = b; } };
  menus[menu].items[row].run();
  return state.box.value;
};
out.menuSquare = run(0, 2, "- a\n- b\n\nrest", 0, 0);
out.menuRoman = run(1, 3, "1. a\n2. b", 3, 3);
out.menuNew = run(1, 2, "one\ntwo", 0, 7);
out.undoBreaks = state.undoBreaks;
out.finished = state.finished;
out.mountedTwice = (() => { L.mount(); return menus.length; })();

// The paste handler, on a view stub.
const pasteWith = (text, before) => {
  let default_ = false;
  state.dispatched = null;
  state.view = {
    dom: { contains: () => true, classList: { contains: () => false } },
    state: {
      readOnly: false,
      selection: { main: { from: before.length } },
      doc: { lineAt: () => ({ from: 0 }) },
      sliceDoc: () => before,
      replaceSelection: (t) => ({ changes: t }),
    },
    dispatch: (spec) => { state.dispatched = spec.changes; },
  };
  listeners.paste.fn({ target: {}, clipboardData: { getData: () => text }, preventDefault: () => { default_ = true; }, stopPropagation() {} });
  return { prevented: default_, inserted: state.dispatched };
};
out.pasteEvent = pasteWith("• one\n• two", "");
out.pasteEventMid = pasteWith("• one", "abc ");
out.pasteEventPlain = pasteWith("plain text", "");

console.log(JSON.stringify(out));
