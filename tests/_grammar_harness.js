// Runs the page's own prose pipeline (the rule engine, the dictionary check
// and the filtering of Harper's lints) on a fixture, in node, with the real
// Harper worker. Used by tests/test_grammar_classes_1026.py (and by hand to
// measure false positives). The page's functions are cut out of the source
// by name, so what is measured is the shipped code, not a copy of it.
//
//   node tests/_grammar_harness.js <repo root> <fixture.json> [options json]
//
// options: {"prefs": {...}, "dictionary": [...], "timing": true}
// prints JSON: {clean: [{tag, text, findings}], planted: [...], timing}
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = path.resolve(process.argv[2]);
const fixture = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const options = JSON.parse(process.argv[4] || "{}");

const SOURCES = ["documents.js", "documents-prose.js"].map((name) =>
  fs.readFileSync(path.join(root, "frontend", "js", name), "utf8")
);

// A top-level declaration: from its first line to the closing line at column 0.
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

const NAMES = options.names || [
  "DOC_PROSE_RULES", "DOC_AUTOCORRECT", "DOC_LONG_SENTENCE_WORDS", "DOC_PROSE_SKIP", "docProseSkipMask",
  "docProseFindings", "docSpellable", "docWordKnown", "docSpellRoot", "docEditsOnce", "docSpellConfident",
  "docSpellLookup", "DOC_CONFIDENT_MIN", "DOC_ALPHABET", "DOC_EDIT_SWAP", "DOC_EDIT_DROP", "DOC_EDIT_ADD",
  "DOC_EDIT_SWAP_LETTER", "docMatchCase", "docWordlistReady", "DOC_VARIANT_LABEL",
  "DOC_GRAMMAR_SKIP_KINDS", "DOC_GRAMMAR_DASH", "docGrammarMessage", "docGrammarFindings", "DOC_GRAMMAR_WIKI", "docGrammarOutside",
  "docProseRemap", "docProseExtras", "DOC_FINDING_SKIP", "docCheckLinkText", "DOC_PROSE_SKIP_LINK_TEXT",
  "docSpellNameKind", "docSpellTransposed","DOC_STRUCTURAL_LINE", "docStructuralMask", "docStructuralBlank",
  "DOC_GRAMMAR_SENTENCE_KINDS", "DOC_GRAMMAR_ABBREVIATION", "docGrammarKeeps",
  ...(options.extraNames || []),
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
  let docGrammarCache = { text: null, findings: [] };
  const docProseIgnored = new Set();
  const prefsCache = __env.prefs;
  const currentDoc = null;
  const docDictionary = () => __env.dictionary;
  const docVariantLookup = () => new Map();
  const docSpellingVariant = () => "off";
  const docLoadWordlist = () => {};
  const docProseKey = (f) => f.rule + ":" + f.text.toLowerCase();
  const docGrammarEnabled = () => true;
  const docGrammarRequest = () => {};
  const docAccessFindings = () => [];
  const docLinkOfferRequest = () => {};
  const docLinkOfferCurrent = () => [];
  ${body}
  return {
    docProseFindings, docProseExtras, docGrammarFindings, docProseSkipMask,
    setGrammar(text, lints) { docGrammarCache = { text, findings: docGrammarFindings(lints, text) }; },
  };`
);
const page = factory({
  wordlist,
  dictionary: new Set((options.dictionary || []).map((w) => w.toLowerCase())),
  prefs: options.prefs || { grammar_check: true },
});

// --- Harper, through the real worker ------------------------------------------
async function startWorker() {
  const { readFile } = require("node:fs/promises");
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    const href = String(url && url.href ? url.href : url);
    if (href.startsWith("file:")) {
      return new Response(await readFile(new URL(href)), { headers: { "Content-Type": "application/wasm" } });
    }
    return realFetch(url, init);
  };
  let handler = null;
  const waiting = new Map();
  globalThis.self = {
    addEventListener: (type, fn) => { if (type === "message") handler = fn; },
    postMessage: (message) => { const r = waiting.get(message.id); if (r) { waiting.delete(message.id); r(message); } },
  };
  await import(pathToFileURL(path.join(root, "frontend", "js", "harper-worker.js")).href + `?${Date.now()}`);
  let n = 0;
  return (text) => new Promise((resolve) => {
    const id = ++n;
    waiting.set(id, resolve);
    handler({ data: { id, text, dialect: "us" } });
  });
}

function summary(findings) {
  return findings.map((f) => ({ rule: f.rule, kind: f.harperKind || "", text: f.text, message: f.message }));
}

async function main() {
  const ask = await startWorker();
  await ask("warm up");
  const run = async (text) => {
    const reply = await ask(text);
    if (!reply.ok) throw new Error(reply.error);
    raw.push(reply.lints.map((lint) => ({ kind: lint.kind, message: lint.message, problem: lint.problem })));
    page.setGrammar(text, reply.lints);
    return page.docProseExtras(text, page.docProseFindings(text)).filter((f) => f.rule !== "long-sentence" || options.longSentence);
  };
  const out = { clean: [], planted: [] };
  const raw = [];
  //: `lints` is what Harper itself said about the line, before the page's filtering.
  for (const item of fixture.clean) out.clean.push({ ...item, findings: summary(await run(item.text)), lints: raw[raw.length - 1] });
  for (const item of fixture.planted) out.planted.push({ ...item, findings: summary(await run(item.text)), lints: raw[raw.length - 1] });
  if (options.timing) {
    const sample = fixture.clean.map((c) => c.text).join("\n\n");
    const words = sample.split(/\s+/).length;
    const long = Array(Math.ceil(1000 / words)).fill(sample).join("\n\n");
    const n = long.split(/\s+/).length;
    const time = async (fn) => {
      const samples = [];
      for (let i = 0; i < 5; i += 1) { const t = performance.now(); await fn(i); samples.push(performance.now() - t); }
      return Math.round(samples.sort((a, b) => a - b)[2] * 10) / 10;
    };
    out.timing = {
      words: n,
      rulesMs: await time(() => page.docProseFindings(long)),
      harperMs: await time(async (i) => { await ask(long + " " + "x".repeat(i)); }),
      extrasMs: await time(() => page.docProseExtras(long, page.docProseFindings(long))),
    };
  }
  process.stdout.write(JSON.stringify(out));
}
main().catch((error) => { process.stderr.write(String(error && error.stack || error)); process.exit(1); });
