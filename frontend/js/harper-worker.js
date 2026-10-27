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

const linters = new Map();

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
//:   - `ToDoHyphen` and `ForYourInformation`: "TODO" and "FYI" are what a
//:     notebook says.
//:   - every `Expand*` rule: they ask for "minimum" for "min", "configuration"
//:     for "config", "seconds" for "sec" and so on. Abbreviations are how
//:     notes are written (owner K4b: "10-20 min" read as "minimum").
//: `tests/test_prose_tools.py` runs this worker in node and holds it.
const HARPER_RULES_OFF = ["UseTitleCase", "NumericRangeEnDash", "OxfordComma", "ToDoHyphen", "ForYourInformation"];
const HARPER_RULE_PREFIXES_OFF = ["Expand"];

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

self.addEventListener("message", async (event) => {
  const { id, text, dialect } = event.data || {};
  const started = performance.now();
  try {
    const linter = await linterFor(dialect);
    const lints = linter.lint(String(text || ""), Language.Markdown, false, undefined, true, false);
    const out = [];
    for (const lint of lints) {
      const span = lint.span();
      out.push({
        start: span.start,
        end: span.end,
        kind: lint.lint_kind(),
        message: lint.message(),
        problem: lint.get_problem_text(),
        suggestions: lint.suggestions().map(suggestionOf),
      });
      span.free();
      lint.free();
    }
    self.postMessage({ id, ok: true, ms: Math.round(performance.now() - started), lints: out });
  } catch (error) {
    self.postMessage({ id, ok: false, error: String((error && error.message) || error) });
  }
});
