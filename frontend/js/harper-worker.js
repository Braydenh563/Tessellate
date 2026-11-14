// Tessellate: grammar and style checking, off the main thread (INBOX 401).
//
// Harper (Automattic, Apache-2.0, vendored in `frontend/vendor/harper/` with
// its licence) is a grammar checker compiled to WebAssembly. It runs here, in
// a module worker, for two reasons that are both measured rather than assumed
// (`scratchpad/ui-sweeps/p2-harper.js`): compiling its 15.9 MB binary takes
// long enough that doing it on the main thread would freeze the editor on the
// first open of a prose document, and a lint of a long document is tens of
// milliseconds, which is a dropped frame on every pause in typing.
//
// **Not `harper.js`'s own `WorkerLinter`.** That one builds its worker from a
// `blob:` URL, which this app's CSP refuses (`worker-src 'self'`,
// `core/security.py`), and a refused worker fails with nothing thrown. So the
// worker is this same-origin file and it talks to the binary directly through
// the vendored module's `createLinter`, which is all `LocalLinter` does.
//
// The CSP does need one word for this: `'wasm-unsafe-eval'` in `script-src`,
// which permits compiling WebAssembly and nothing else (no `eval`, no
// `new Function`). Without it `WebAssembly.instantiate` throws a CompileError
// naming the policy.
//
// Protocol:
//   in  {id, text, dialect}          dialect: "us" | "uk" | "au" | "ca" | "in"
//                                    ("off" is us)
//   in  {type: "own", words}         the person's own words (no reply); also
//                                    Harper's own dictionary (`import_words`)
//   in  {id, text, dialect, ignored} `ignored`: the problem texts (lower case)
//                                    the person put away in this document,
//                                    kept dismissed by Harper (`ignore_lints`)
//   in  {id, text, dialect, groupsOff}  kind groups the person turned off
//                                    ("style", "punctuation", "capitalization",
//                                    "wording"); their lints are not returned
//   in  {id, type: "spell", words, dialect}
//   out {id, ok: true, spell: {word: {known, suggestions}}}
//   out {id, ok: true, ms, lints: [{start, end, kind, message, problem,
//                                    suggestions: [{kind, text}]}]}
//   out {id, ok: false, error}       the binary did not load; the caller
//                                    stops asking for this session
//
// Offsets arrive in UTF-16 units already, the editor's own: measured with an
// emoji before the finding (`p2-harper.js`, "has" at 5 after a two-unit
// emoji), so nothing here converts them.

import { Dialect, Language, SuggestionKind } from "../vendor/harper/BinaryModule-BmeyZWwZ.js";
import { slimBinary } from "../vendor/harper/slimBinary.js";
import "./spell-second.js";

const linters = new Map();
//: The person's own words, kept to hand to a linter built after they arrived.
let ownWords = [];
//: What each linter has been told to ignore, as a signature, so the ignore is
//: redone only when the person's list changes (it is by context hash, so it
//: holds as the text is edited).
const ignoredSig = new WeakMap();

//: Words Harper should treat as spelt right: a name is a word to the dictionary
//: as soon as the notebook uses it twice. Whole list each time, not appended.
function giveWords(linter) {
  linter.clear_words();
  if (ownWords.length) linter.import_words(ownWords);
}

//: Keep the person's dismissed findings dismissed inside Harper: ignore every
//: lint of `source` whose problem text is in `ignored`. A list that did not change
//: costs nothing; a changed one clears Harper's list first so a restore shows again.
function keepIgnored(linter, source, ignored) {
  const wanted = [...new Set((ignored || []).map((t) => String(t).toLowerCase()))].sort();
  const sig = JSON.stringify(wanted);
  if (!wanted.length && ignoredSig.get(linter) === undefined) return;
  if (ignoredSig.get(linter) === sig) return;
  ignoredSig.set(linter, sig);
  linter.clear_ignored_lints();
  if (!wanted.length) return;
  const keep = [];
  for (const lint of linter.lint(source, Language.Markdown, false, undefined, true, false)) {
    if (wanted.includes(lint.get_problem_text().toLowerCase())) keep.push(lint);
    else lint.free();
  }
  if (keep.length) linter.ignore_lints(source, keep);
}

//: **Harper's rules this app turns off**, by the names Harper's lint config
//: uses. `UseTitleCase` ("Try to use title case in headings") asks for the
//: opposite of this app's own copy rule, sentence case everywhere (CLAUDE.md
//: standing order 6, DESIGN.md "Voice"): it flagged every heading of a
//: document written the way the app writes, four of the six suggestions on
//: the README's focus-mode shot. Every other rule keeps Harper's default,
//: except the classes below (INBOX 1357, `tests/test_grammar_classes_1026.py`,
//: measured on `tests/grammar_fixture_1026.json`):
//:   - `NumericRangeEnDash`: "10-20 min" and "pp. 34-51" are written with a
//:     hyphen in every note; 8 of 77 clean fixture lines were underlined.
//:   - `OxfordComma`: a house style rather than an error; it put a mark on
//:     "milk, eggs and bread".
//:   - `ToDoHyphen` and `ForYourInformation`: all-caps tags like FYI are what a
//:     notebook says.
//:   - every `Expand*` rule: they ask for "minimum" for "min", "configuration"
//:     for "config", "seconds" for "sec" and so on. Abbreviations are how
//:     notes are written (owner K4b: "10-20 min" read as "minimum").
//: `tests/test_prose_tools.py` runs this worker in node and holds it.
const HARPER_RULES_OFF = ["UseTitleCase", "NumericRangeEnDash", "OxfordComma", "ToDoHyphen", "ForYourInformation"];
const HARPER_RULE_PREFIXES_OFF = ["Expand"];

//: **Lint kinds the person can turn off** (L333), grouped as the Checks sheet names
//: them: `groupsOff` on a lint message holds the group ids, and every lint whose
//: Harper kind is in one is dropped here, before the page ever sees it. Spelling and
//: grammar proper are not a group: they are what the checker is for.
const KIND_GROUPS = {
  style: ["Style", "Readability", "Redundancy", "Enhancement", "Formatting", "Miscellaneous"],
  punctuation: ["Punctuation"],
  capitalization: ["Capitalization"],
  wording: ["WordChoice", "Usage", "Nonstandard", "Eggcorn", "Malapropism", "Regionalism"],
};

//: The five dialects Harper ships (VC6): the setting's value to its name.
const DIALECTS = {
  us: Dialect.American,
  uk: Dialect.British,
  au: Dialect.Australian,
  ca: Dialect.Canadian,
  in: Dialect.Indian,
};

function dialectOf(key) {
  return DIALECTS[key];
}

async function linterFor(name) {
  const key = Object.hasOwn(DIALECTS, name) ? name : "us";
  let linter = linters.get(key);
  if (!linter) {
    linter = slimBinary.createLinter(dialectOf(key)).then((made) => {
      //: The whole config, defaults and all, with the rules above set false:
      //: read back and written whole, so no rule's state is left to however
      //: this build treats a key that is missing.
      const config = made.get_lint_config_as_object();
      for (const rule of HARPER_RULES_OFF) config[rule] = false;
      for (const rule of Object.keys(config)) {
        if (HARPER_RULE_PREFIXES_OFF.some((prefix) => rule.startsWith(prefix))) config[rule] = false;
      }
      made.set_lint_config_from_object(config);
      giveWords(made);
      return made;
    });
    linters.set(key, linter);
  }
  return linter;
}

function suggestionOf(suggestion) {
  const kind = suggestion.kind();
  const text = kind === SuggestionKind.Remove ? "" : suggestion.get_replacement_text();
  const out = { kind: SuggestionKind[kind] || "Replace", text };
  suggestion.free();
  return out;
}

// The second opinion on words (INBOX 1731) is spell-second.js: a Hunspell
// dictionary for the dialect, the person's own words, suggestions capped and
// ranked by how common the word is. It puts `spellSecond` on `self`.

self.addEventListener("message", async (event) => {
  const { id, text, dialect, type } = event.data || {};
  const second = self.spellSecond;
  //: The person's own words, sent whole each time they change; no reply.
  if (type === "own") {
    second.setOwnWords(event.data.words);
    ownWords = [...new Set((event.data.words || []).map(String).filter((w) => /^\p{L}[\p{L}'-]*$/u.test(w) && w.length > 1))];
    await Promise.all([...linters.values()].map((made) => made.then(giveWords, () => {})));
    return;
  }
  const started = performance.now();
  try {
    //: A spelling pack for another language (D30): load its two Hunspell files once, then ask.
    if (type === "packload") {
      //: Answered `ok` either way, with `loaded` in the `spell` slot the page reads: a pack that
      //: will not parse must not take the grammar check down (the page treats `ok: false` as that).
      const loaded = await second.packLoad(event.data.lang, String(event.data.aff || ""), String(event.data.dic || "")).then(() => true, () => false);
      self.postMessage({ id, ok: true, ms: Math.round(performance.now() - started), spell: { loaded } });
      return;
    }
    if (type === "packspell") {
      self.postMessage({ id, ok: true, ms: Math.round(performance.now() - started), spell: second.packAnswers(event.data.lang, event.data.words || []) });
      return;
    }
    if (type === "spell") {
      //: No answer rather than a failure: the page falls back to its own list.
      const spell = await second.spellAnswers(dialect, event.data.words || []).catch(() => ({}));
      self.postMessage({ id, ok: true, ms: Math.round(performance.now() - started), spell });
      return;
    }
    const linter = await linterFor(dialect);
    const source = String(text || "");
    keepIgnored(linter, source, event.data.ignored);
    const lints = linter.lint(source, Language.Markdown, false, undefined, true, false);
    const out = [];
    const dropped = new Set((Array.isArray(event.data.groupsOff) ? event.data.groupsOff : []).flatMap((group) => KIND_GROUPS[group] || []));
    for (const lint of lints) {
      if (dropped.has(lint.lint_kind())) {
        lint.free();
        continue;
      }
      const span = lint.span();
      const made = {
        start: span.start,
        end: span.end,
        kind: lint.lint_kind(),
        message: lint.message(),
        problem: lint.get_problem_text(),
        suggestions: lint.suggestions().map(suggestionOf),
      };
      span.free();
      lint.free();
      //: A dictionary that did not load leaves Harper's own lint standing
      //: rather than taking the grammar check down with it.
      const kept = await second.refined(made, dialect, source).catch(() => made);
      if (kept) out.push(kept);
    }
    self.postMessage({ id, ok: true, ms: Math.round(performance.now() - started), lints: out });
  } catch (error) {
    self.postMessage({ id, ok: false, error: String((error && error.message) || error) });
  }
});
