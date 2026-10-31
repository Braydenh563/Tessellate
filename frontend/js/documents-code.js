// documents-code.js: the document editor's code side (split out of
// documents.js on 2026-09-24).
//
// What is here: everything that makes a code document behave like a code
// editor rather than a text box. The syntax checks and the lint source
// (DOC-JSON), the completion sources, snippets and the Emmet glue
// (DOC-COMPLETE), hover docs, colour swatches, indent guides and bracket
// colours, the outline's code symbols and sticky scroll, go to definition,
// references and find in documents, the Run panel, and the scanner, the
// formatter and the quick fixes (DOC-CODE). It moved verbatim, one
// contiguous block: no function was renamed and none changed.
//
// What stayed in documents.js, and why: the CodeMirror engine itself
// (`loadCodeMirror`, the theme, the highlighter, the keymap) and
// `docCmExtensions`, which assembles the editor from both files, because
// markdown documents and the note boxes mount the same engine and need none
// of this file.
//
// **Loaded in the Library bundle, before documents.js**, not after it
// (`LAZY_MODULES` in app.js). Measured on the split, with a scope analysis
// of both files: this file's own top-level code reads nothing from
// documents.js (its top level is declarations, tables and constants), while
// documents.js has top-level wiring (`onDomReady` callbacks, the command
// tables, listeners registered while it evaluates) that names functions
// defined here. `ensureModule` runs the bundle's files in order with a
// microtask checkpoint after each, so a microtask documents.js queued would
// run before a file listed after it. Listed first, every name documents.js
// could reach is already defined when documents.js runs, which makes the
// order a guarantee rather than an argument. Nothing outside the bundle
// calls in here before the bundle's promise resolves.

// -----------------------------------------------------------------------------
// Code documents as a code editor: diagnostics and completions (INBOX 392)
// -----------------------------------------------------------------------------
//
// The owner: "the code document types dont act like a code editor with
// errors, suggestions and that needs to be improved." Before this the editor
// mounted no linter and no completion source at all (this file had no use of
// `CM.lint` or `CM.autocomplete`), in a bundle that already carried
// CodeMirror's own linter, lint gutter and completion engine, exported by
// `frontend/vendor/codemirror/entry.js` since it was first built; nothing
// needed rebuilding.
//
// **Where each language is checked, and why there.** The browser checks what
// it has a real parser for and the server checks the rest, never the other
// way round, because a round trip per pause in typing is only worth paying
// where the browser cannot answer:
//
// - JSON: `JSON.parse`, whose error names the offset.
// - JavaScript, TypeScript and CSS: the Lezer tree CodeMirror has already
//   built to colour the file. A node the grammar could not place is an error
//   node, so this costs nothing the highlighter had not already spent. Never
//   `new Function` or `eval`: the CSP forbids both, and running somebody's
//   file to find out whether it parses is not a check, it is execution.
// - Python, TOML, XML and YAML: `POST /documents/check-syntax`, which uses
//   `ast.parse`, `tomllib`, `defusedxml` and PyYAML's composer
//   (`src/tessellate/core/syntaxcheck.py`). Offline, stateless, capped.
//
// Only for code: a markdown document is prose, and its checker is the
// writing panel's. Plain view turns these off with the highlighting, because
// Plain is defined as the editor with nothing interpreting the text.

//: The languages the server checks. A 400 from it (PyYAML not installed, say)
//: takes that language out of this set for the session, so a file is not
//: asked about again on every pause in typing.
const DOC_CHECK_REMOTE = new Set(["py", "toml", "xml", "svg", "yaml"]);
//: Mirrors `syntaxcheck.MAX_CHARS`: past it the server answers 422, so the
//: request is not made.
const DOC_CHECK_MAX_CHARS = 200000;
//: How long typing has to pause before a check runs. Long enough that a
//: half-typed line is not underlined while it is being typed.
const DOC_CHECK_DELAY_MS = 750;
//: Languages whose grammar in the bundle is a Lezer grammar with honest
//: error recovery, so an error node means the text does not parse.
const DOC_CHECK_TREE = new Set(["js", "ts", "css"]);

//: A 1-based line and column from a checker, as the offsets CodeMirror
//: underlines. The range runs to the end of the word at that column, so the
//: underline sits under the token that is wrong rather than under one letter
//: of it; at the end of a line it takes the last character instead, because
//: an empty range draws no underline at all.
function docDiagnosticRange(doc, lineNo, col) {
  const line = doc.line(Math.max(1, Math.min(lineNo, doc.lines)));
  let from = Math.min(line.from + Math.max(0, col - 1), line.to);
  const rest = doc.sliceString(from, line.to);
  const word = /^[\w$]+|^\S/.exec(rest);
  let to = from + (word ? word[0].length : 0);
  if (to === from && from > line.from) from -= 1;
  if (to === from && from < doc.length) to = from + 1;
  return { from, to: Math.min(to, doc.length) };
}

// DOC-JSON-BEGIN (tests/test_syntax_check.py runs this region in node)
//: **Where a JSON text stops being JSON**, as an offset and a sentence.
//:
//: `JSON.parse` says whether, and is the fast path, but not reliably where:
//: measured in this build of Chromium, a trailing comma before `}` throws
//: `Unexpected token '}', ..."b": \n}" is not valid JSON` with no position at
//: all, so the underline had nowhere to go. This walks the grammar once, only
//: after `JSON.parse` has already failed, and stops at the first character
//: that cannot continue it. Recursion is bounded by the text's own nesting,
//: which the size of a document caps.
function docJsonErrorAt(text) {
  let i = 0;
  const fail = (message) => {
    throw { at: i, message };
  };
  const ws = () => {
    while (i < text.length && " \t\n\r".includes(text[i])) i += 1;
  };
  const literal = (word) => {
    if (text.startsWith(word, i)) i += word.length;
    else fail("Expected a value");
  };
  const string = () => {
    i += 1;
    while (i < text.length) {
      const ch = text[i];
      if (ch === '"') {
        i += 1;
        return;
      }
      if (ch === "\\") {
        i += 1;
        if (!'"\\/bfnrtu'.includes(text[i] || "")) fail("Not a valid escape in a string");
        if (text[i] === "u" && !/^[0-9a-fA-F]{4}$/.test(text.slice(i + 1, i + 5))) {
          fail("A \\u escape needs four hex digits");
        }
      } else if (ch === "\n") fail("A string cannot run onto the next line");
      else if (ch < " ") fail("A control character has to be escaped in a string");
      i += 1;
    }
    fail("This string is never closed");
  };
  const number = () => {
    const match = /^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?/.exec(text.slice(i, i + 400));
    if (!match) fail("Expected a value");
    i += match[0].length;
  };
  const value = () => {
    ws();
    const ch = text[i];
    if (ch === "{") return object();
    if (ch === "[") return array();
    if (ch === '"') return string();
    if (ch === "t") return literal("true");
    if (ch === "f") return literal("false");
    if (ch === "n") return literal("null");
    if (ch === "-" || (ch >= "0" && ch <= "9")) return number();
    return fail(i >= text.length ? "The text ends where a value was expected" : "Expected a value");
  };
  const object = () => {
    i += 1;
    ws();
    if (text[i] === "}") {
      i += 1;
      return;
    }
    for (;;) {
      ws();
      if (text[i] !== '"') {
        fail(text[i] === "}" ? "A comma with nothing after it" : "Expected a property name in double quotes");
      }
      string();
      ws();
      if (text[i] !== ":") fail("Expected a colon after the property name");
      i += 1;
      value();
      ws();
      if (text[i] === ",") {
        i += 1;
        continue;
      }
      if (text[i] === "}") {
        i += 1;
        return;
      }
      fail("Expected a comma or a closing brace");
    }
  };
  const array = () => {
    i += 1;
    ws();
    if (text[i] === "]") {
      i += 1;
      return;
    }
    for (;;) {
      ws();
      if (text[i] === "]") fail("A comma with nothing after it");
      value();
      ws();
      if (text[i] === ",") {
        i += 1;
        continue;
      }
      if (text[i] === "]") {
        i += 1;
        return;
      }
      fail("Expected a comma or a closing bracket");
    }
  };
  try {
    value();
    ws();
    if (i < text.length) fail("There is more text after the value");
    return null;
  } catch (error) {
    if (error && typeof error.at === "number") return error;
    throw error;
  }
}

// DOC-JSON-END

//: JSON, checked in the browser: `JSON.parse` says whether, and
//: `docJsonErrorAt` says where. If the two ever disagree the error goes on
//: the last character of the text with the engine's own words, which is
//: still true and still somewhere a person can find.
function docJsonDiagnostics(doc) {
  const text = doc.toString();
  if (!text.trim()) return [];
  try {
    JSON.parse(text);
    return [];
  } catch (error) {
    const found = docJsonErrorAt(text);
    let offset = found ? found.at : text.trimEnd().length - 1;
    offset = Math.max(0, Math.min(offset, doc.length));
    const line = doc.lineAt(offset);
    const range = docDiagnosticRange(doc, line.number, offset - line.from + 1);
    const message = found ? found.message : String(error.message || "Not valid JSON");
    return [{ ...range, severity: "error", message }];
  }
}

//: JavaScript, TypeScript and CSS, from the parse tree. The whole document is
//: parsed first (`ensureSyntaxTree`, with a time budget) because the tree the
//: highlighter keeps may stop at the viewport, and an error below it would
//: otherwise appear only when scrolled to. One diagnostic per line: a single
//: missing bracket can leave several error nodes on one line, and five
//: underlines for one mistake reads as five mistakes.
function docTreeDiagnostics(CM, state) {
  const tree =
    CM.language.ensureSyntaxTree(state, state.doc.length, 200) || CM.language.syntaxTree(state);
  const found = [];
  const lines = new Set();
  tree.iterate({
    enter: (node) => {
      if (!node.type.isError || found.length >= 50) return;
      const line = state.doc.lineAt(node.from);
      if (lines.has(line.number)) return;
      lines.add(line.number);
      const text = state.doc.sliceString(node.from, Math.min(node.to, node.from + 24)).trim();
      const range = docDiagnosticRange(state.doc, line.number, node.from - line.from + 1);
      found.push({
        ...range,
        severity: "error",
        message: text ? `Unexpected “${text.split("\n")[0]}”` : "Something is missing here",
      });
    },
  });
  return found;
}

//: HTML's check (Brief 71, for the Problems tab): a closing tag that closes
//: nothing open here, and an element left open that HTML does not close by
//: itself. A void element, or one whose end tag is optional, is not one.
function docHtmlDiagnostics(CM, state) {
  const tree = CM.language.ensureSyntaxTree(state, state.doc.length, 200) || CM.language.syntaxTree(state);
  const found = [];
  const at = (from, severity, message) => {
    const line = state.doc.lineAt(from);
    found.push({ ...docDiagnosticRange(state.doc, line.number, from - line.from + 1), severity, message });
  };
  tree.iterate({
    enter: (node) => {
      if (found.length >= 50) return false;
      if (node.name === "MismatchedCloseTag") {
        at(node.from, "error", `\u201c${state.doc.sliceString(node.from, Math.min(node.to, node.from + 40))}\u201d closes nothing that is open here`);
        return;
      }
      if (node.name !== "Element") return;
      const open = node.node.firstChild;
      const last = node.node.lastChild;
      if (!open || open.name !== "OpenTag" || (last && last.name === "CloseTag")) return;
      const tag = open.getChild("TagName");
      const name = tag ? state.doc.sliceString(tag.from, tag.to).toLowerCase() : "";
      if (!name || DOC_HTML_VOID.has(name) || DOC_HTML_OPTIONAL.has(name)) return;
      at(open.from, "warning", `<${name}> is never closed`);
    },
  });
  return found;
}

//: The server's checkers. Resolves to `[]` on any failure: an editor that
//: underlines nothing because the check could not run is honest, one that
//: underlines the wrong thing is not.
async function docRemoteDiagnostics(ext, doc) {
  const text = doc.toString();
  if (!text.trim() || text.length > DOC_CHECK_MAX_CHARS) return [];
  let found;
  try {
    const response = await api("/documents/check-syntax", {
      method: "POST",
      body: JSON.stringify({ language: ext, text }),
      silent: true,
      readOnly: true,
    });
    found = await response.json();
  } catch (error) {
    //: The route answers 400 only for a language it has no checker for, so the
    //: status says it; the sentence is for a person, not for this code to read.
    if (error && error.status === 400) DOC_CHECK_REMOTE.delete(ext);
    return [];
  }
  return (Array.isArray(found) ? found : []).map((d) => ({
    ...docDiagnosticRange(doc, d.line, d.col),
    severity: ["error", "warning", "info"].includes(d.severity) ? d.severity : "error",
    message: String(d.message || "Syntax error"),
  }));
}

//: The one lint source, dispatching on the open file's type at the moment it
//: runs rather than when the extension was built, so a type change between
//: two checks is answered by the new type.
//:
//: **With the fixes attached** (the quick fixes, further down this file).
//: Each checker's diagnostics carry the fixes that follow from them as
//: CodeMirror actions, which the hover card draws as buttons and Alt+Enter
//: lists at the caret. For the languages no checker here parses (C, Java, Go,
//: Rust and the rest of `DOC_CHECK_SCAN`) the structure scan is the check: a
//: bracket that closes nothing, one never closed, a string or a comment left
//: open. For JavaScript, TypeScript and CSS the tree still decides *whether*
//: there is an error and the scan is asked only then, for *which bracket*
//: and how to fix it, so a construct the scan does not know (a regex it
//: misreads) can never underline valid code. And for every code type, a note
//: where the indentation mixes tabs and spaces.
function docCodeLintSource(CM) {
  return async (view) => {
    const type = docFileType();
    const ext = type.ext;
    const state = view.state;
    const text = docStr(state.doc);
    const unit = type.indent || "  ";
    let found = [];
    if (ext === "json") {
      found = docJsonDiagnostics(state.doc);
      if (found.length) {
        const fixes = docJsonFixes(text, docJsonErrorAt(text), unit);
        found = found.map((d) => ({
          ...d,
          actions: fixes.map((fix) => ({
            name: fix.name,
            apply: (v, from) => docApplyCodeFix(v, "json", "json", fix.name, from),
          })),
        }));
      }
    } else if (DOC_CHECK_TREE.has(ext)) {
      found = docTreeDiagnostics(CM, state);
      if (found.length && !(ext === "js" && docTreeHasJsx(CM, state))) {
        const scanned = docCodeFixes(text, ext, unit);
        if (scanned.length) found = docCodeActions("scan", scanned);
      }
    } else if (ext === "html") {
      found = docHtmlDiagnostics(CM, state);
    } else if (DOC_CHECK_REMOTE.has(ext)) {
      found = await docRemoteDiagnostics(ext, state.doc);
      if (ext === "py") {
        //: The compiler's "expected ':'" has one fix, and it is certain.
        found = found.map((d) => {
          //: Case-blind: `syntaxcheck.py` capitalises the compiler's words.
          if (!/expected ':'/i.test(d.message)) return d;
          const fix = docPythonColonFix(text, state.doc.lineAt(d.from).number);
          if (!fix) return d;
          return { ...d, actions: [{ name: fix.name, apply: (v, from) => docApplyCodeFix(v, "py-colon", "", fix.name, from) }] };
        });
      }
    } else if (DOC_CHECK_SCAN.has(ext)) {
      found = docCodeActions("scan", docCodeFixes(text, ext, unit));
    }
    return found.concat(docCodeActions("indent-mix", docIndentMixFixes(text, unit, state.tabSize, ext)), docRunTestDiagnostics(state));
  };
}

//: The languages the structure scan checks, because nothing else in the
//: bundle or on the server parses them. Shell, Ruby, TOML's neighbours and
//: the rest are left out: their quoting and bracket rules are loose enough
//: (a shell `case` pattern's lone `)`) that a scan would underline valid
//: files, and an underline under valid code teaches a reader to ignore them.
const DOC_CHECK_SCAN = new Set(["c", "cpp", "cs", "java", "kt", "go", "rs", "swift", "php", "r", "sql"]);

//: The words each language reserves, for the languages whose grammar in the
//: bundle brings no completions of its own. JavaScript, TypeScript, Python,
//: CSS and HTML are absent on purpose: their CodeMirror packages already
//: complete keywords, snippets and the names in scope at the caret, which is
//: better than a flat list, so this adds nothing there.
const DOC_CODE_KEYWORDS = {
  go: "break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var nil true false append cap close copy delete len make new panic print println recover string int int64 float64 bool byte rune error",
  rs: "as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while Some None Ok Err Vec String Option Result Box println",
  c: "auto break case char const continue default do double else enum extern float for goto if inline int long register return short signed sizeof static struct switch typedef union unsigned void volatile while NULL include define printf malloc free",
  cpp: "auto bool break case catch char class const constexpr continue default delete do double else enum explicit false float for friend if inline int long namespace new nullptr operator private protected public return short static struct switch template this throw true try typedef typename using virtual void while std vector string include",
  cs: "abstract as async await base bool break case catch class const continue decimal default delegate do double else enum event false finally float for foreach get if int interface internal is lock long namespace new null object out override private protected public readonly ref return set static string struct switch this throw true try using var virtual void while",
  java: "abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for if implements import instanceof int interface long new null package private protected public return short static super switch this throw throws true false try void while String System",
  kt: "as break class continue do else false for fun if in interface is null object package return super this throw true try typealias val var when while companion data override private public internal open sealed suspend println",
  rb: "alias and begin break case class def defined do else elsif end ensure false for if in module next nil not or redo rescue retry return self super then true undef unless until when while yield puts require attr_accessor",
  swift: "associatedtype class deinit enum extension func import init inout internal let operator private protocol public static struct subscript typealias var break case continue default defer do else fallthrough for guard if in repeat return switch where while as false is nil self Self super throw throws true try print",
  r: "if else repeat while function for in next break TRUE FALSE NULL Inf NaN NA library return print list",
  php: "abstract and array as break callable case catch class clone const continue declare default do echo else elseif empty extends final finally fn for foreach function global if implements include instanceof interface isset list match namespace new or print private protected public readonly require return static switch throw trait try unset use var while yield true false null",
  sql: "select from where and or not insert into values update set delete create table drop alter add column index primary key foreign references join left right inner outer on group by order having limit offset as distinct union all null is in like between case when then else end count sum avg min max",
  bash: "if then else elif fi case esac for while until do done in function select time return exit export local readonly echo printf read cd pwd source shift set unset true false",
  json: "true false null",
  yaml: "true false null",
  toml: "true false",
};

//: Keywords, then every name already written in the document, through
//: `completeFromList`. The names are read at the moment the list is asked
//: for, so a function defined a second ago is offered, and the word being
//: typed is left out so the list never offers you what you have already got.
//:
//: **One function, kept, and it is not a style point.** The completion engine
//: tells a source it is still waiting on from a new one by identity, and the
//: language-data callback below runs on every transaction: returning a fresh
//: closure each time made every keystroke a new source, the answer to the
//: last one was thrown away as stale, and the list sat at "pending" forever
//: (measured: `completionStatus` read "pending" 800ms after typing "hel",
//: while the same source called by hand returned fifty options).
//: **Snippets, per language** (INBOX 404): the short words VS Code expands
//: into a statement's whole shape, through the same completion list, Enter
//: or Tab to take, Tab to walk the stops. `[label, detail, template]`, the
//: template in CodeMirror's snippet syntax (`${name}` a stop, `${}` the
//: last), a tab at a line's start being one indent unit of the file's own.
//: JavaScript, TypeScript and Python already have the packages' own set
//: (function, for, if, try, class, import); these add what they lack.
const DOC_CODE_SNIPPETS = {
  java: [
    ["main", "public static void main", "public static void main(String[] args) {\n\t${}\n}"],
    ["sout", "System.out.println", "System.out.println(${});"],
    ["fori", "for loop with an index", "for (int ${i} = 0; ${i} < ${n}; ${i}++) {\n\t${}\n}"],
    ["foreach", "for each item", "for (${Type} ${item} : ${items}) {\n\t${}\n}"],
    ["if", "if block", "if (${condition}) {\n\t${}\n}"],
    ["ifelse", "if, else", "if (${condition}) {\n\t${}\n} else {\n\t\n}"],
    ["while", "while loop", "while (${condition}) {\n\t${}\n}"],
    ["try", "try, catch", "try {\n\t${}\n} catch (${Exception} ${e}) {\n\t\n}"],
    ["class", "class", "public class ${Name} {\n\t${}\n}"],
    ["switch", "switch", "switch (${value}) {\n\tcase ${a}:\n\t\t${}\n\t\tbreak;\n\tdefault:\n\t\tbreak;\n}"],
  ],
  cs: [
    ["svm", "static void Main", "static void Main(string[] args)\n{\n\t${}\n}"],
    ["cw", "Console.WriteLine", "Console.WriteLine(${});"],
    ["prop", "property", "public ${int} ${Name} { get; set; }"],
    ["ctor", "constructor", "public ${Name}()\n{\n\t${}\n}"],
    ["for", "for loop", "for (int ${i} = 0; ${i} < ${n}; ${i}++)\n{\n\t${}\n}"],
    ["foreach", "foreach", "foreach (var ${item} in ${items})\n{\n\t${}\n}"],
    ["if", "if block", "if (${condition})\n{\n\t${}\n}"],
    ["while", "while loop", "while (${condition})\n{\n\t${}\n}"],
    ["try", "try, catch", "try\n{\n\t${}\n}\ncatch (${Exception} ${e})\n{\n\t\n}"],
    ["class", "class", "public class ${Name}\n{\n\t${}\n}"],
  ],
  c: [
    ["main", "int main", "int main(void) {\n\t${}\n\treturn 0;\n}"],
    ["include", "#include", "#include <${stdio.h}>"],
    ["printf", "printf", "printf(\"${}\\n\");"],
    ["for", "for loop", "for (int ${i} = 0; ${i} < ${n}; ${i}++) {\n\t${}\n}"],
    ["if", "if block", "if (${condition}) {\n\t${}\n}"],
    ["while", "while loop", "while (${condition}) {\n\t${}\n}"],
    ["struct", "struct", "struct ${name} {\n\t${}\n};"],
  ],
  cpp: [
    ["main", "int main", "int main() {\n\t${}\n\treturn 0;\n}"],
    ["include", "#include", "#include <${iostream}>"],
    ["cout", "std::cout", "std::cout << ${} << std::endl;"],
    ["for", "for loop", "for (int ${i} = 0; ${i} < ${n}; ++${i}) {\n\t${}\n}"],
    ["forr", "range for", "for (auto& ${item} : ${items}) {\n\t${}\n}"],
    ["if", "if block", "if (${condition}) {\n\t${}\n}"],
    ["while", "while loop", "while (${condition}) {\n\t${}\n}"],
    ["class", "class", "class ${Name} {\npublic:\n\t${Name}();\n\t${}\n};"],
    ["struct", "struct", "struct ${Name} {\n\t${}\n};"],
  ],
  go: [
    ["main", "package main", "package main\n\nimport \"fmt\"\n\nfunc main() {\n\t${}\n}"],
    ["func", "function", "func ${name}(${params}) ${error} {\n\t${}\n}"],
    ["fp", "fmt.Println", "fmt.Println(${})"],
    ["for", "for loop", "for ${i} := 0; ${i} < ${n}; ${i}++ {\n\t${}\n}"],
    ["forr", "for range", "for ${_}, ${v} := range ${items} {\n\t${}\n}"],
    ["if", "if block", "if ${condition} {\n\t${}\n}"],
    ["iferr", "if err != nil", "if err != nil {\n\treturn ${err}\n}"],
    ["struct", "struct type", "type ${Name} struct {\n\t${}\n}"],
  ],
  rs: [
    ["main", "fn main", "fn main() {\n\t${}\n}"],
    ["fn", "function", "fn ${name}(${params}) -> ${Type} {\n\t${}\n}"],
    ["println", "println!", "println!(\"${}\");"],
    ["for", "for loop", "for ${item} in ${items} {\n\t${}\n}"],
    ["if", "if block", "if ${condition} {\n\t${}\n}"],
    ["match", "match", "match ${value} {\n\t${pattern} => ${},\n\t_ => {}\n}"],
    ["struct", "struct", "struct ${Name} {\n\t${}\n}"],
    ["impl", "impl block", "impl ${Name} {\n\t${}\n}"],
  ],
  kt: [
    ["main", "fun main", "fun main() {\n\t${}\n}"],
    ["fun", "function", "fun ${name}(${params}): ${Unit} {\n\t${}\n}"],
    ["println", "println", "println(${})"],
    ["for", "for loop", "for (${item} in ${items}) {\n\t${}\n}"],
    ["if", "if block", "if (${condition}) {\n\t${}\n}"],
    ["when", "when", "when (${value}) {\n\t${a} -> ${}\n\telse -> {}\n}"],
    ["class", "class", "class ${Name} {\n\t${}\n}"],
  ],
  swift: [
    ["func", "function", "func ${name}(${params}) -> ${Void} {\n\t${}\n}"],
    ["print", "print", "print(${})"],
    ["for", "for loop", "for ${item} in ${items} {\n\t${}\n}"],
    ["if", "if block", "if ${condition} {\n\t${}\n}"],
    ["guard", "guard", "guard ${condition} else {\n\treturn${}\n}"],
    ["struct", "struct", "struct ${Name} {\n\t${}\n}"],
    ["class", "class", "class ${Name} {\n\t${}\n}"],
  ],
  rb: [
    ["def", "method", "def ${name}(${params})\n\t${}\nend"],
    ["class", "class", "class ${Name}\n\t${}\nend"],
    ["each", "each block", "${items}.each do |${item}|\n\t${}\nend"],
    ["if", "if block", "if ${condition}\n\t${}\nend"],
    ["puts", "puts", "puts ${}"],
  ],
  php: [
    ["function", "function", "function ${name}(${params}) {\n\t${}\n}"],
    ["foreach", "foreach", "foreach (${$items} as ${$item}) {\n\t${}\n}"],
    ["if", "if block", "if (${condition}) {\n\t${}\n}"],
    ["class", "class", "class ${Name} {\n\t${}\n}"],
    ["echo", "echo", "echo ${};"],
  ],
  r: [
    ["function", "function", "${name} <- function(${params}) {\n\t${}\n}"],
    ["for", "for loop", "for (${i} in ${seq}) {\n\t${}\n}"],
    ["if", "if block", "if (${condition}) {\n\t${}\n}"],
  ],
  sql: [
    ["sel", "SELECT ... FROM", "SELECT ${*} FROM ${table};"],
    ["selw", "SELECT ... WHERE", "SELECT ${*} FROM ${table} WHERE ${condition};"],
    ["ins", "INSERT INTO", "INSERT INTO ${table} (${columns}) VALUES (${values});"],
    ["upd", "UPDATE ... SET", "UPDATE ${table} SET ${column} = ${value} WHERE ${condition};"],
    ["del", "DELETE FROM", "DELETE FROM ${table} WHERE ${condition};"],
    ["ct", "CREATE TABLE", "CREATE TABLE ${name} (\n\t${id} INTEGER PRIMARY KEY,\n\t${}\n);"],
    ["join", "JOIN ... ON", "JOIN ${table} ON ${a} = ${b}"],
  ],
  bash: [
    ["shebang", "#!/usr/bin/env bash", "#!/usr/bin/env bash\nset -euo pipefail\n${}"],
    ["if", "if block", "if [ ${condition} ]; then\n\t${}\nfi"],
    ["for", "for loop", "for ${item} in ${items}; do\n\t${}\ndone"],
    ["while", "while loop", "while ${condition}; do\n\t${}\ndone"],
    ["func", "function", "${name}() {\n\t${}\n}"],
    ["case", "case", "case ${value} in\n\t${pattern})\n\t\t${}\n\t\t;;\n\t*)\n\t\t;;\nesac"],
  ],
  py: [
    ["main", "if __name__ == \"__main__\"", "if __name__ == \"__main__\":\n\t${main()}"],
    ["with", "with block", "with ${open(path)} as ${f}:\n\t${}"],
    ["adef", "async def", "async def ${name}(${params}):\n\t${}"],
    ["elif", "elif", "elif ${condition}:\n\t${}"],
  ],
  js: [
    ["log", "console.log", "console.log(${});"],
    ["arrow", "arrow function", "const ${name} = (${params}) => {\n\t${}\n};"],
    ["afn", "async function", "async function ${name}(${params}) {\n\t${}\n}"],
    ["switch", "switch", "switch (${value}) {\n\tcase ${a}:\n\t\t${}\n\t\tbreak;\n\tdefault:\n\t\tbreak;\n}"],
  ],
};
DOC_CODE_SNIPPETS.ts = DOC_CODE_SNIPPETS.js;

//: The snippet rows for a file type, built once per type (the engine tells
//: options apart by identity too, and a list rebuilt per keystroke resets
//: the chosen row). Above the keywords, so `for` offers the loop's shape
//: before the bare word.
const docCodeSnippetCache = new Map();

function docCodeSnippetOptions(CM, ext) {
  if (docCodeSnippetCache.has(ext)) return docCodeSnippetCache.get(ext);
  const options = (DOC_CODE_SNIPPETS[ext] || []).map(([label, detail, template]) =>
    CM.autocomplete.snippetCompletion(template, { label, detail, type: "keyword", boost: 1 })
  );
  docCodeSnippetCache.set(ext, options);
  return options;
}

//: For JavaScript, TypeScript and Python, whose packages bring their own
//: snippets and sources: the rows they lack, as language data on their own
//: language, never inside a string or a comment.
let docNativeSnippetCache = null;

//: **p5.js names in a sketch** (OPEN 1139): a JavaScript document that
//: defines `setup` or `draw` (run-core.js's test for a sketch) is offered the
//: vendored p5.min.js's most used names with their arguments. Written here
//: rather than read out of the 1 MB bundle while typing;
//: tests/test_code_documents.py checks every name is in that bundle.
const DOC_P5_SKETCH = /\bfunction\s+(?:setup|draw)\s*\(/;
const DOC_P5_NAMES = [
  ["createCanvas", "(w, h)"], ["resizeCanvas", "(w, h)"], ["background", "(colour)"], ["clear", "()"],
  ["fill", "(colour)"], ["noFill", "()"], ["stroke", "(colour)"], ["noStroke", "()"], ["strokeWeight", "(weight)"],
  ["colorMode", "(mode, max)"], ["color", "(r, g, b, a)"], ["lerpColor", "(from, to, amount)"],
  ["ellipse", "(x, y, w, h)"], ["circle", "(x, y, d)"], ["rect", "(x, y, w, h)"], ["square", "(x, y, s)"],
  ["line", "(x1, y1, x2, y2)"], ["point", "(x, y)"], ["triangle", "(x1, y1, x2, y2, x3, y3)"],
  ["quad", "(x1, y1, x2, y2, x3, y3, x4, y4)"], ["arc", "(x, y, w, h, start, stop)"],
  ["beginShape", "()"], ["vertex", "(x, y)"], ["endShape", "(CLOSE)"],
  ["text", "(str, x, y)"], ["textSize", "(size)"], ["textAlign", "(horizontal, vertical)"], ["textFont", "(font)"],
  ["push", "()"], ["pop", "()"], ["translate", "(x, y)"], ["rotate", "(angle)"], ["scale", "(s)"], ["angleMode", "(DEGREES)"],
  ["random", "(min, max)"], ["randomSeed", "(seed)"], ["noise", "(x, y)"], ["map", "(value, start1, stop1, start2, stop2)"],
  ["constrain", "(n, low, high)"], ["dist", "(x1, y1, x2, y2)"], ["lerp", "(start, stop, amount)"],
  ["radians", "(degrees)"], ["degrees", "(radians)"],
  ["frameRate", "(fps)"], ["noLoop", "()"], ["loop", "()"], ["redraw", "()"], ["millis", "()"],
  ["createVector", "(x, y)"], ["loadImage", "(path)"], ["image", "(img, x, y, w, h)"],
  ["imageMode", "(CENTER)"], ["rectMode", "(CENTER)"], ["ellipseMode", "(CORNER)"], ["keyIsDown", "(keyCode)"],
  ["width", ""], ["height", ""], ["mouseX", ""], ["mouseY", ""], ["pmouseX", ""], ["pmouseY", ""],
  ["mouseIsPressed", ""], ["keyIsPressed", ""], ["key", ""], ["keyCode", ""], ["frameCount", ""],
  ["windowWidth", ""], ["windowHeight", ""], ["PI", ""], ["TWO_PI", ""], ["HALF_PI", ""],
  ["CENTER", ""], ["CORNER", ""], ["CLOSE", ""], ["DEGREES", ""], ["RADIANS", ""],
  ["preload", "()"], ["windowResized", "()"], ["mousePressed", "()"], ["mouseReleased", "()"],
  ["mouseDragged", "()"], ["keyPressed", "()"], ["keyReleased", "()"],
];

function docP5Source() {
  const options = DOC_P5_NAMES.map(([label, args]) => ({
    label,
    type: args ? "function" : /^[A-Z_]+$/.test(label) ? "constant" : "variable",
    detail: args ? `${args} p5` : "p5",
    boost: 1,
  }));
  return (context) => {
    if (context.matchBefore(/\.\w*$/)) return null;
    const word = context.matchBefore(/[A-Za-z_]\w*/);
    if (!word || (word.from === word.to && !context.explicit)) return null;
    if (!DOC_P5_SKETCH.test(docStr(context.state.doc))) return null;
    return { from: word.from, options, validFor: /^\w*$/ };
  };
}

function docNativeSnippets(CM, ext) {
  if (!docNativeSnippetCache) {
    const quiet = ["String", "FormatString", "TemplateString", "Comment", "LineComment", "BlockComment", "RegExp"];
    //: Never after a dot: `math.` is a member, not the start of a statement.
    const source = (key) => {
      const list = CM.autocomplete.ifNotIn(quiet, CM.autocomplete.completeFromList(docCodeSnippetOptions(CM, key)));
      return (context) => (context.matchBefore(/\.\w*$/) ? null : list(context));
    };
    docNativeSnippetCache = {
      py: [
        CM.python.pythonLanguage.data.of({ autocomplete: source("py") }),
        CM.python.pythonLanguage.data.of({ autocomplete: CM.autocomplete.ifNotIn(quiet, docPyStdlibSource(CM)) }),
      ],
      js: [
        CM.javascript.javascriptLanguage.data.of({ autocomplete: source("js") }),
        CM.javascript.javascriptLanguage.data.of({ autocomplete: CM.autocomplete.ifNotIn(quiet, docP5Source()) }),
      ],
    };
  }
  if (ext === "py") return docNativeSnippetCache.py;
  if (ext === "js" || ext === "ts") return docNativeSnippetCache.js;
  return [];
}

//: **The standard library after a dot** (D9, OPEN 1070): `math.` offers
//: math's names, each with its signature and its doc's first line, from a
//: table generated from CPython's `inspect` (scripts/gen_python_completions.py,
//: frontend/vendor/python-stdlib/stdlib.json, 28 KB gzipped, fetched the first time a
//: Python file asks). A module counts when the file imports it, by its name
//: or its `as` name; `from os import path` makes `path.` os.path's.
let docPyStdlibLoad = null;

function docPyStdlibTable() {
  if (!docPyStdlibLoad) {
    docPyStdlibLoad = api("/vendor/python-stdlib/stdlib.json", { silent: true })
      .then((response) => response.json())
      .then((table) => table?.modules || {})
      .catch(() => {
        docPyStdlibLoad = null;
        return {};
      });
  }
  return docPyStdlibLoad;
}

//: The file's module names: alias to module, from its import lines.
function docPyImports(text) {
  const found = new Map();
  for (const m of String(text).matchAll(/^[ \t]*import[ \t]+([^\n#]+)/gm)) {
    for (const part of m[1].split(",")) {
      const [, mod, alias] = /^\s*([\w.]+)(?:\s+as\s+(\w+))?\s*$/.exec(part) || [];
      if (mod) found.set(alias || mod, mod);
    }
  }
  for (const m of String(text).matchAll(/^[ \t]*from[ \t]+([\w.]+)[ \t]+import[ \t]+\(?([^\n#)]+)/gm)) {
    for (const part of m[2].split(",")) {
      const [, name, alias] = /^\s*(\w+)(?:\s+as\s+(\w+))?\s*$/.exec(part) || [];
      if (name) found.set(alias || name, `${m[1]}.${name}`);
    }
  }
  return found;
}

//: The rows for `name.` (or `a.b.`) in a file, or null.
function docPyStdlibRows(modules, imports, dotted) {
  const head = dotted.split(".")[0];
  const base = imports.get(head);
  if (!base) return null;
  const full = [base, ...dotted.split(".").slice(1)].join(".");
  return modules[full] || null;
}

function docPyStdlibSource(CM) {
  return async (context) => {
    const before = context.matchBefore(/[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*\.\w*/);
    if (!before) return null;
    const dot = before.text.lastIndexOf(".");
    const modules = await docPyStdlibTable();
    const rows = docPyStdlibRows(modules, docPyImports(docStr(context.state.doc)), before.text.slice(0, dot));
    if (!rows) return null;
    const type = { function: "function", class: "class", constant: "constant", namespace: "namespace" };
    return {
      from: before.from + dot + 1,
      validFor: /^\w*$/,
      options: rows.map(([label, kind, signature, doc]) => ({
        label,
        boost: 2,
        type: type[kind] || "variable",
        detail: signature ? signature.slice(label.length) : "",
        info: doc || undefined,
      })),
    };
  };
}

let docCodeCompletionCache = null;

function docCodeCompletionSource(CM) {
  if (docCodeCompletionCache) return docCodeCompletionCache;
  docCodeCompletionCache = (context) => {
    const word = context.matchBefore(/[A-Za-z_$][\w$]*/);
    if (!word || (word.from === word.to && !context.explicit)) return null;
    const ext = docFileType().ext;
    const snippets = docCodeSnippetOptions(CM, ext);
    const keywords = (DOC_CODE_KEYWORDS[ext] || "").split(" ").filter(Boolean);
    const seen = new Set(keywords);
    const snipped = new Set(snippets.map((o) => o.label));
    for (const label of snipped) seen.add(label);
    const options = [...snippets, ...keywords.filter((k) => !snipped.has(k)).map((label) => ({ label, type: "keyword" }))];
    const text = docStr(context.state.doc);
    const names = /[A-Za-z_$][\w$]{2,}/g;
    let match;
    while ((match = names.exec(text)) !== null && options.length < 2000) {
      if (match.index === word.from) continue;
      if (seen.has(match[0])) continue;
      seen.add(match[0]);
      options.push({ label: match[0], type: "variable" });
    }
    return CM.autocomplete.completeFromList(options)(context);
  };
  return docCodeCompletionCache;
}

//: The language-data entry, built once for the same reason as the source.
let docCodeCompletionDataCache = null;

function docCodeCompletionData(CM) {
  if (!docCodeCompletionDataCache) {
    const entry = [{ autocomplete: docCodeCompletionSource(CM) }];
    docCodeCompletionDataCache = CM.state.EditorState.languageData.of(() => entry);
  }
  return docCodeCompletionDataCache;
}

//: The checks' timing, and no hover card of findings while a pointer menu
//: is open (OPEN 1089): the menu is what the pointer is on, and prose
//: documents already hold their own finding cards back the same way
//: (`docOpenSuggestFor`).
const DOC_LINT_CONFIG = {
  delay: DOC_CHECK_DELAY_MS,
  tooltipFilter: (diagnostics) => (docPointerMenuOpen() ? [] : diagnostics),
};

//: The code tools for the open document, or nothing. Whether a type counts
//: as code is the file-type table's own answer (`previewable` is prose);
//: plain text and CSV have no syntax and no vocabulary, so they get neither.
function docCodeTools(CM) {
  const type = docFileType();
  if (type.previewable || docView === "plain" || ["txt", "csv"].includes(type.ext)) {
    //: **An inert completer, so the field always exists.** The bundled
    //: autocomplete (6.20.3) has no `destroy` that clears its debounce
    //: timer, and `docResetDocument` swaps states on one view: a keystroke in
    //: a code file followed within ~100ms by opening a markdown one fired
    //: the old timer into a state with no completion field, which throws
    //: "Field is not present in this state" (found by the code editor pass).
    //: No sources and no typing trigger, so prose behaves exactly as before.
    return [CM.autocomplete.autocompletion({ override: [], activateOnTyping: false })];
  }
  const native = ["js", "ts", "py", "css", "html"].includes(type.ext);
  return [
    CM.lint.linter(docCodeLintSource(CM), DOC_LINT_CONFIG),
    CM.lint.lintGutter(),
    //: The list, opening as you type; Emmet, the CSS values, the ghost text
    //: and Tab (`docCompletionExtras`, part three below).
    docCompletionExtras(CM, type),
    //: Beside the language's own sources, not instead of them: `override`
    //: would switch off the scope-aware completion the JavaScript and
    //: Python packages bring.
    native ? [] : docCodeCompletionData(CM),
    //: Pairs, Enter and the indent unit (`docCodeEditing`, below).
    docCodeEditing(CM, type),
  ];
}

//: The file type or the view changed: the code tools follow, by compartment,
//: so the caret, the scroll position and the undo history survive.
function docCmSyncCodeTools() {
  const CM = window.CM6;
  if (!docCmView || !CM || !docCmParts.code) return;
  docCmView.dispatch({ effects: docCmParts.code.reconfigure(docCodeTools(CM)) });
}

// -----------------------------------------------------------------------------
// Code documents as a code editor, part three: completions, Emmet and the
// ghost text
// -----------------------------------------------------------------------------
//
// The owner, 2026-09-23 (INBOX 394 (c)): "on the document editor code files I
// want ALL THE PREFILL SUGGESTIONS AND POPUP BOXES FOR OPTIONS. like if I do
// just '!' on a document and press enter it does base html code, or for all
// the available css properties for that css feature, or doinf inline
// suggestions."
//
// Three things, each on the editor's own machinery rather than beside it:
//
// - **Emmet**, the abbreviation language VS Code expands (`!`, `ul>li*3`,
//   `a[href]`, `m10`), vendored as its core expander (frontend/vendor/emmet,
//   MIT, loaded the first time an HTML or CSS document opens) and offered as
//   a row in the completion list, so Enter takes it exactly as it takes any
//   other row, and Tab expands it with the list closed.
// - **Each CSS property's own values.** The CSS package completes every
//   property, but a value from one flat list of four hundred keywords;
//   `display: ` should offer `flex` and `grid`, not `dashed`. The values are
//   read out of Emmet's own CSS snippet table (the `display:block|flex|...`
//   rows it expands from), so there is no second table here to fall behind.
// - **Ghost text**: the rest of the chosen row after the caret, in muted ink,
//   taken with Tab. Enter stays the list's key, as it is in VS Code.
//
// The pure half is the region below; `tests/test_code_completion.py` runs it
// in node against the vendored bundle. The wiring after it is measured in
// Chromium by `scratchpad/ui-sweeps/doccomplete.js`.

// DOC-COMPLETE-BEGIN (tests/test_code_completion.py runs this region in node)
//: The element names of HTML's living standard (and `svg`), which is the test
//: for whether a bare word on its own line is an element being written or a
//: word of the page's text. Emmet itself would expand any word into a tag.
const DOC_HTML_TAGS = new Set((
  "a abbr address area article aside audio b base bdi bdo blockquote body br button canvas caption " +
  "cite code col colgroup data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption " +
  "figure footer form h1 h2 h3 h4 h5 h6 head header hgroup hr html i iframe img input ins kbd label " +
  "legend li link main map mark menu meta meter nav noscript object ol optgroup option output p picture " +
  "pre progress q rp rt ruby s samp script search section select slot small source span strong style " +
  "sub summary sup table tbody td template textarea tfoot th thead time title tr track u ul var video wbr svg"
).split(" "));

//: CSS's named colours, for any property whose value is a colour. Emmet's
//: table gives `color` a `#000` placeholder and no names.
const DOC_CSS_COLORS = (
  "transparent currentcolor aliceblue antiquewhite aqua aquamarine azure beige bisque black " +
  "blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue " +
  "cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki " +
  "darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue " +
  "darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue " +
  "firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow " +
  "grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon " +
  "lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink " +
  "lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime " +
  "limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen " +
  "mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose " +
  "moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen " +
  "paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red " +
  "rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue " +
  "slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white " +
  "whitesmoke yellow yellowgreen"
).split(" ");

//: The properties whose value is, or may begin with, a colour.
const DOC_CSS_COLOR_PROPERTY = /(^|-)color$|^(fill|stroke|background|border(-(top|right|bottom|left))?|outline|text-decoration|column-rule)$/;

//: The four every property takes, offered last.
const DOC_CSS_GLOBALS = ["inherit", "initial", "unset", "revert"];

//: **What Emmet's table is missing, and what in it is dead.** Its rows are
//: the abbreviations it expands, not a reference, so it predates `sticky`,
//: `flow-root` and `fit-content`, has no list at all for `width` or
//: `font-size`, and still carries IE's `hand` cursor and the pre-standard
//: `lr-tb` writing modes. Measured against its 2.4.11 table; each row here is
//: added after that property's own.
const DOC_CSS_VALUES_EXTRA = {
  position: "sticky",
  display: "flow-root",
  cursor: "grab grabbing not-allowed wait progress context-menu copy alias zoom-in zoom-out col-resize row-resize ew-resize ns-resize none",
  overflow: "clip",
  "overflow-x": "clip",
  "overflow-y": "clip",
  "overflow-wrap": "normal break-word anywhere",
  "word-break": "break-word",
  "white-space": "break-spaces",
  "text-align": "start end",
  "font-size": "xx-small x-small small medium large x-large xx-large smaller larger",
  "font-weight": "100 200 300 400 500 600 700 800 900",
  "font-family": "system-ui ui-sans-serif ui-serif ui-monospace",
  "line-height": "normal",
  "writing-mode": "horizontal-tb vertical-rl vertical-lr",
  "object-fit": "fill contain cover none scale-down",
  "object-position": "center top bottom left right",
  "pointer-events": "auto none",
  "user-select": "auto text all",
  "scroll-behavior": "auto smooth",
  isolation: "auto isolate",
  "mix-blend-mode": "normal multiply screen overlay darken lighten difference",
  "place-items": "center start end stretch",
  "place-content": "center start end stretch space-between space-around space-evenly",
  "transition-timing-function": "linear ease ease-in ease-out ease-in-out step-start step-end",
  "transition-property": "all none opacity transform",
  "animation-fill-mode": "none",
  "background-repeat": "repeat",
  "background-size": "auto",
  "background-position": "center top bottom left right",
  "list-style-type": "none",
  "list-style": "none",
  "table-layout": "auto",
  "aspect-ratio": "auto",
  "will-change": "auto transform opacity scroll-position",
  "z-index": "auto",
  flex: "none auto",
  border: "none",
  outline: "none",
  content: "none",
  gap: "normal",
  "row-gap": "normal",
  "column-gap": "normal",
  "grid-template-columns": "none subgrid",
  "grid-template-rows": "none subgrid",
  ...Object.fromEntries(["top", "right", "bottom", "left", "margin", "margin-top", "margin-right", "margin-bottom", "margin-left"].map((p) => [p, "auto"])),
  ...Object.fromEntries(["width", "height", "min-width", "min-height", "inline-size", "block-size"].map((p) => [p, "auto fit-content max-content min-content"])),
  ...Object.fromEntries(["max-width", "max-height"].map((p) => [p, "none fit-content max-content min-content"])),
};

const DOC_CSS_VALUES_DEAD = new Set(["time", "hand", "no-clip", "lr-tb", "lr-bt", "rl-tb", "rl-bt", "tb-rl", "tb-lr", "bt-lr", "bt-rl"]);

//: Emmet's snippet table for "markup" or "stylesheet", resolved once per
//: bundle: it is read on every keystroke that could be an abbreviation.
const docEmmetSnippetCache = new Map();

function docEmmetSnippets(E, type) {
  const cached = docEmmetSnippetCache.get(type);
  if (cached?.E === E) return cached.snippets;
  const snippets = E.resolveConfig({ type }).snippets;
  docEmmetSnippetCache.set(type, { E, snippets });
  return snippets;
}

//: Whether `abbr` reads as an abbreviation someone meant, rather than a word
//: Emmet would happily make a tag of. Markup: it starts with an element name,
//: one of Emmet's own snippet names (`link:css`, `!`), or an operator that
//: only means Emmet (`.card`, `#main`, `(`, `[`, `{`). CSS: one of Emmet's
//: shorthands of two letters or more that expand to a declaration with a
//: value (`df`, `bgc`, `m10`, `p10-20`). A property name being typed (`col`,
//: `pos`, the start of the property it becomes) is left to the language's
//: own list, which does it better, and so is anything Emmet can only turn
//: into an empty `columns: ;`.
function docEmmetIntended(abbr, syntax, E, anywhere = false) {
  if (!abbr || /^\d/.test(abbr)) return false;
  if (syntax === "css") {
    if (abbr.length < 2 || !/^[a-z]/i.test(abbr)) return false;
    let out = "";
    try {
      out = E.expand(abbr, { type: "stylesheet" });
    } catch {
      return false;
    }
    const declaration = /^([a-z-]+): (.+);$/.exec(out);
    return Boolean(declaration) && !declaration[1].startsWith(abbr.toLowerCase());
  }
  //: XML has no vocabulary to check a name against, so on typing only an
  //: operator says "Emmet" (`item>name`, `row*3`); Tab on a bare name is a
  //: request and makes the pair.
  if (syntax === "xml") {
    if (!/^[a-zA-Z_]/.test(abbr)) return false;
    return anywhere || /[>+*^[{(]/.test(abbr);
  }
  const snippets = docEmmetSnippets(E, "markup");
  const name = (/^[a-zA-Z][\w-]*(?::[\w-]+)*/.exec(abbr) || [""])[0];
  //: JSX: an HTML element or a component (a capital), never `!`, which is a
  //: whole page and has no place inside a component.
  if (!name) return syntax === "jsx" ? /^[.#([]/.test(abbr) : /^[.#!([{]/.test(abbr);
  if (syntax === "jsx" && /^[A-Z]/.test(name)) return true;
  return DOC_HTML_TAGS.has(name.toLowerCase()) || (syntax === "html" && Object.hasOwn(snippets, name));
}

//: The abbreviation that ends at column `col` of `line`, as `{ abbr, start,
//: end }` in the line's own columns, or null. `end` can pass `col`: the
//: closers `closeBrackets` typed ahead of the caret (`a[href|]`) are part of
//: what was written, and Emmet's `lookAhead` takes them in.
//:
//: **Where, as well as what.** On typing (`anywhere` false) an abbreviation
//: is offered only where markup starts a line or follows a tag (`<p>ul>li`),
//: and in CSS only where a declaration starts; mid-sentence in a paragraph,
//: every "a" and "p" would open a list and Enter would take it. Tab passes
//: `anywhere`, because a Tab on a word is a request.
function docEmmetAt(line, col, syntax, E, anywhere) {
  if (/^[\w$-]/.test(line.slice(col))) return null;
  const css = syntax === "css";
  let found = null;
  try {
    found = E.extract(line, col, { type: css ? "stylesheet" : "markup", lookAhead: !css });
  } catch {
    return null;
  }
  if (!found || !found.abbreviation) return null;
  const before = line.slice(0, found.start);
  if (!anywhere) {
    const place = css ? /(^|[{;])\s*$/ : /(^|>)\s*$/;
    if (!place.test(before)) return null;
  }
  if (!docEmmetIntended(found.abbreviation, syntax, E, anywhere)) return null;
  return { abbr: found.abbreviation, start: found.start, end: Math.max(found.end, col) };
}

//: An abbreviation's expansion twice over: `preview`, the text as it will
//: read (for the row's detail pane), and `template`, the same text in
//: CodeMirror's snippet syntax so Tab walks Emmet's own stops. Null when
//: Emmet cannot read it. The parser takes `${n}` and `#{n}` as fields and
//: `\{` `\}` as braces, so every brace that is text is escaped first and
//: the fields are written after, from markers no text contains.
//:
//: **A default inside an attribute is text, not a stop.** Emmet's `!` makes
//: the viewport's `device-width` and `1.0` its first two stops, so Enter
//: left `device-width` selected and the title third; nobody writing a page
//: starts there. An empty attribute (`a[href]`) keeps its stop, because
//: that is the thing to fill in.
//:
//: `text`, when given, is what the abbreviation wraps (Wrap with
//: abbreviation): a string goes in whole, an array of lines one per repeat
//: (`ul>li*` makes a list item of each line).
function docEmmetExpansion(E, abbr, syntax, text) {
  const type = syntax === "css" ? "stylesheet" : "markup";
  const config = type === "markup" ? { type, syntax } : { type };
  if (text !== undefined) config.text = text;
  try {
    const preview = E.expand(abbr, config);
    if (!preview.trim()) return null;
    const field = (index, placeholder) => `\u0001${index}\u0002${placeholder || ""}\u0003`;
    const marked = E.expand(abbr, { ...config, options: { "output.field": field } });
    const template = marked
      .replace(/[{}]/g, "\\$&")
      .replace(/\u0001(\d+)\u0002([^\u0003]*)\u0003/g, (_, index, placeholder, offset, whole) => {
        const text = placeholder.replace(/\\?[{}]/g, "");
        const head = whole.slice(0, offset);
        const tag = head.slice(head.lastIndexOf("<"));
        const inValue = type === "markup" && head.lastIndexOf("<") > head.lastIndexOf(">") && tag.split('"').length % 2 === 0;
        if (inValue && text) return text;
        return text ? `\${${index}:${text}}` : `\${${index}}`;
      });
    return { preview, template };
  } catch {
    return null;
  }
}

//: The property a value is being typed for, and the word typed so far, from
//: the text before the caret; null anywhere but a value. Whether the caret
//: is inside a rule at all is the tree's question, asked by the caller.
function docCssValueContext(before) {
  const cut = Math.max(before.lastIndexOf("{"), before.lastIndexOf(";"), before.lastIndexOf("}"));
  const match = /^\s*(-{0,2}[a-zA-Z][\w-]*)\s*:\s*([^:]*)$/.exec(before.slice(cut + 1));
  if (!match) return null;
  return { property: match[1].toLowerCase(), word: /[\w-]*$/.exec(match[2])[0] };
}

//: Property to its keyword values, read once per bundle out of Emmet's CSS
//: table, whose rows are `property:value|value|...` (a row with a field in
//: it, `color:${1:#000}`, is a placeholder and has no keywords to give).
let docCssValueTableCache = null;

function docCssValueTable(E) {
  if (docCssValueTableCache?.E === E) return docCssValueTableCache.table;
  const table = new Map();
  const snippets = E ? docEmmetSnippets(E, "stylesheet") : {};
  for (const row of Object.values(snippets)) {
    const colon = row.indexOf(":");
    if (colon < 1 || row.includes("$")) continue;
    const property = row.slice(0, colon).trim();
    if (!/^[a-z-]+$/.test(property)) continue;
    const values = row.slice(colon + 1).split("|").map((v) => v.trim()).filter((v) => /^[\w-]+$/.test(v));
    if (!values.length) continue;
    const known = table.get(property) || [];
    for (const value of values) if (!known.includes(value)) known.push(value);
    table.set(property, known);
  }
  for (const [property, extra] of Object.entries(DOC_CSS_VALUES_EXTRA)) {
    const known = table.get(property) || [];
    for (const value of extra.split(" ")) if (!known.includes(value)) known.push(value);
    table.set(property, known);
  }
  for (const [property, known] of table) {
    table.set(property, known.filter((v) => !DOC_CSS_VALUES_DEAD.has(v) && !DOC_CSS_GLOBALS.includes(v)));
  }
  docCssValueTableCache = { E, table };
  return table;
}

//: The rows for a property's value: its own keywords first, then colours
//: where it takes one, then the four global keywords, each once.
function docCssValueOptions(property, table) {
  const labels = [...(table.get(property) || [])];
  if (DOC_CSS_COLOR_PROPERTY.test(property)) labels.push(...DOC_CSS_COLORS);
  labels.push(...DOC_CSS_GLOBALS);
  const own = new Set(table.get(property) || []);
  //: Boosts, because the list sorts by match and then by name: a
  //: property's own words first, then `currentcolor` and `transparent`
  //: above the named colours, the global four last.
  const boost = (label) =>
    own.has(label) ? 2 : label === "currentcolor" || label === "transparent" ? 1 : DOC_CSS_GLOBALS.includes(label) ? -2 : 0;
  return [...new Set(labels)].map((label) => ({ label, boost: boost(label) }));
}

//: The ghost text for the chosen row: the rest of `label` after the part of
//: it already typed, or "". Only when the caret ends a word (`after` does
//: not continue it), only when what was typed is the start of `label` from
//: the start of a word (a fuzzy match, `bgc` for `background-color`, has no
//: "rest"), and never for a row of more than one line.
function docGhostSuffix(before, after, label) {
  if (!label || label.includes("\n") || /^[\w$-]/.test(after)) return "";
  for (let k = Math.min(label.length - 1, before.length); k >= 1; k -= 1) {
    const typed = before.slice(before.length - k);
    if (typed.toLowerCase() !== label.slice(0, k).toLowerCase()) continue;
    const prev = before[before.length - k - 1];
    if (prev !== undefined && /[\w$-]/.test(prev) && /[\w$-]/.test(typed[0])) continue;
    return label.slice(k);
  }
  return "";
}

//: Balance, VS Code's "Emmet: Balance": the next selection out from (or in
//: to) `from`..`to`, given the tags around the caret as the matcher lists
//: them (`{ open: [a, b], close: [c, d] }`, innermost first going out,
//: outermost first going in). Each tag offers its content, then itself, so
//: repeated presses step content, element, parent's content, parent. Null
//: at the edge.
function docBalanceRange(tags, from, to, inward) {
  const spans = [];
  for (const tag of tags) {
    const whole = [tag.open[0], (tag.close || tag.open)[1]];
    const inner = tag.close ? [tag.open[1], tag.close[0]] : null;
    if (inward) spans.push(whole, ...(inner ? [inner] : []));
    else spans.push(...(inner ? [inner] : []), whole);
  }
  for (const [a, b] of spans) {
    const grows = a <= from && b >= to && (a < from || b > to);
    const shrinks = a >= from && b <= to && (a > from || b < to);
    if (inward ? shrinks && from !== to : grows) return [a, b];
  }
  return null;
}

//: The text Wrap hands Emmet: lines after the first lose the first line's
//: indentation, because the snippet puts it back (every line of a snippet is
//: indented to the line it starts on) and the wrapped block would otherwise
//: drift one level right each time. An array when the abbreviation repeats
//: without a count (`ul>li*`), so each line becomes one item.
function docEmmetWrapText(text, indent, abbr) {
  const lines = text.split("\n").map((line, i) => (i && line.startsWith(indent) ? line.slice(indent.length) : line));
  return lines.length > 1 && /\*(?!\d)/.test(abbr) ? lines.filter((l) => l.trim()) : lines.join("\n");
}

//: **Rename the matching tag** (VS Code's linked editing): an edit inside
//: one tag's name, made to `oldText` as `fromA`..`toA` becoming `insert`,
//: and the same rename for its partner, as `{ from, to, insert }` in the
//: edited document's positions; null when the edit is not inside a paired
//: tag's name, or makes something that is no longer a name (a space starts
//: the attributes, and the partner is then left alone).
function docTagRename(E, oldText, fromA, toA, insert, xml) {
  let tag = null;
  try {
    tag = E.matchTag(oldText, fromA, { xml });
  } catch {
    return null;
  }
  if (!tag || !tag.close) return null;
  const open = [tag.open[0] + 1, tag.open[0] + 1 + tag.name.length];
  const close = [tag.close[0] + 2, tag.close[0] + 2 + tag.name.length];
  const inside = ([a, b]) => fromA >= a && toA <= b;
  const edited = inside(open) ? open : inside(close) ? close : null;
  if (!edited) return null;
  const name = tag.name.slice(0, fromA - edited[0]) + insert + tag.name.slice(toA - edited[0]);
  if (!/^[\w:.-]*$/.test(name)) return null;
  const partner = edited === open ? close : open;
  const shift = partner[0] > fromA ? insert.length - (toA - fromA) : 0;
  return { from: partner[0] + shift, to: partner[1] + shift, insert: name };
}

//: XML's auto-close, which the stream mode does not have and HTML's and
//: JSX's grammars do: the name of the tag a `>` typed now would open, or
//: null (a self-closing `/>`, a comment, a declaration, a closing tag).
function docXmlOpenedBy(before) {
  const match = /<([A-Za-z_][\w:.-]*)(?:\s[^<>]*)?$/.exec(before);
  return match && !before.endsWith("/") ? match[1] : null;
}

//: The innermost element still open at the end of `before`, for `</`: the
//: close it should be finished with, or null.
function docXmlUnclosed(before) {
  const stack = [];
  const tags = /<(\/?)([A-Za-z_][\w:.-]*)(?:\s[^<>]*?)?(\/?)>/g;
  const text = before.replace(/<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>/g, "");
  let match;
  while ((match = tags.exec(text)) !== null) {
    if (match[3]) continue;
    if (!match[1]) stack.push(match[2]);
    else {
      const at = stack.lastIndexOf(match[2]);
      if (at >= 0) stack.length = at;
    }
  }
  return stack.length ? stack[stack.length - 1] : null;
}

//: A computed colour (`rgb(1, 2, 3)` or `rgba(1, 2, 3, 0.5)`, which is what
//: the browser answers for any colour) as `#rrggbb`, the only form the
//: native picker takes; null for anything else.
function docRgbToHex(rgb) {
  const match = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i.exec(rgb || "");
  if (!match) return null;
  return `#${match.slice(1, 4).map((n) => Math.min(255, Number(n)).toString(16).padStart(2, "0")).join("")}`;
}

//: The picker's `#rrggbb`, written back in the form the value was in, as
//: VS Code does: a hex stays hex (its case and its alpha kept), `rgb()` and
//: `rgba()` stay functions (comma or space syntax, the alpha kept); `hsl()`
//: and a named colour become hex, because the picker has no other answer.
function docCssColorFormat(original, hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const hash = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.exec(original);
  if (hash) {
    const digits = hash[1];
    const alpha = digits.length === 4 ? digits[3].repeat(2) : digits.length === 8 ? digits.slice(6) : "";
    const out = hex + alpha;
    return /[A-F]/.test(digits) && !/[a-f]/.test(digits) ? out.toUpperCase() : out.toLowerCase();
  }
  const fn = /^(rgba?)\(([^)]*)\)$/i.exec(original.trim());
  if (fn) {
    const parts = fn[2].split(/[\s,/]+/).filter(Boolean);
    const alpha = parts[3];
    if (fn[2].includes(",")) return `${fn[1]}(${r}, ${g}, ${b}${alpha ? `, ${alpha}` : ""})`;
    return `${fn[1]}(${r} ${g} ${b}${alpha ? ` / ${alpha}` : ""})`;
  }
  return hex;
}
//: **One line on what a name is for** (INBOX 402, hover docs), written here
//: for this app rather than lifted: the packages ship names but no prose, and
//: the prose VS Code shows is MDN's, under CC-BY-SA, which this AGPL project
//: does not take in quietly. `name|line`, one per row; an element's row
//: says what it is, a property's what it sets, an attribute's what it means.
const DOC_HOVER_HTML = `
a|A link to another page, a place on this one, a file or an address.
abbr|An abbreviation; its title attribute gives the full form.
address|Contact details for the page or the article it is in.
area|A clickable region of an image map.
article|A self-contained piece: a post, a story, a card that stands alone.
aside|Content beside the main flow: a sidebar, a pull quote, notes.
audio|Sound, with the browser's own controls when asked for.
b|Text set apart in bold without extra importance.
base|The base address every relative link on the page resolves against.
bdi|Text whose direction is isolated from the text around it.
bdo|Text whose direction is overridden by its dir attribute.
blockquote|A quotation set as its own block; cite names the source.
body|The page's content: everything that is shown.
br|A line break inside text.
button|A control that does something when pressed.
canvas|A surface drawn on by script.
caption|A table's title.
cite|The title of a creative work.
code|A fragment of computer code.
col|One column of a table, for styling it as a whole.
colgroup|A group of table columns.
data|A value with a machine-readable form in its value attribute.
datalist|Suggested values for an input's list attribute.
dd|The description of a term in a description list.
del|Text that has been removed from the document.
details|A disclosure box that opens and closes; summary is its label.
dfn|The defining instance of a term.
dialog|A dialog box or modal.
div|A generic block container with no meaning of its own.
dl|A description list of terms and their descriptions.
dt|A term in a description list.
em|Stressed text, read with emphasis.
embed|External content from a plugin or another type.
fieldset|A group of form controls, with a legend.
figcaption|The caption of a figure.
figure|Self-contained content, such as an image with its caption.
footer|The footer of the page or of its section.
form|A form whose controls are sent together.
h1|A heading, level 1: the page's title.
h2|A heading, level 2.
h3|A heading, level 3.
h4|A heading, level 4.
h5|A heading, level 5.
h6|A heading, level 6.
head|The page's metadata: title, links, scripts, styles.
header|The introductory part of the page or of its section.
hgroup|A heading with its subtitle or tagline.
hr|A thematic break between paragraphs.
html|The root of the page.
i|Text in an alternate voice, usually italic.
iframe|Another page embedded in this one.
img|An image.
input|A form field; its type decides which kind.
ins|Text that has been added to the document.
kbd|Keyboard input, a key or a chord.
label|The label of a form control.
legend|The caption of a fieldset.
li|An item in a list.
link|A link to an external resource: a stylesheet, an icon, a font.
main|The page's main content, once per page.
map|An image map, with its areas.
mark|Text highlighted for reference.
menu|A list of commands.
meta|Metadata that other elements cannot give: charset, viewport, description.
meter|A measurement within a known range.
nav|A block of navigation links.
noscript|Content shown when scripts are off.
object|An external resource: an image, a page, a plugin.
ol|An ordered, numbered list.
optgroup|A labelled group of options in a select.
option|One choice in a select or a datalist.
output|The result of a calculation or an action.
p|A paragraph.
picture|Several sources for one image, chosen by the browser.
pre|Preformatted text, shown exactly as written.
progress|How far a task has got.
q|A short inline quotation.
rp|Fallback parentheses for a ruby annotation.
rt|The text of a ruby annotation.
ruby|A ruby annotation, for pronunciation of East Asian characters.
s|Text that is no longer accurate or relevant.
samp|Sample output from a program.
script|A script, inline or from its src.
search|A block of search controls.
section|A thematic section of the page, usually with a heading.
select|A drop-down of options.
slot|A placeholder in a web component's shadow tree.
small|Side comments and small print.
source|One media source for picture, audio or video.
span|A generic inline container with no meaning of its own.
strong|Text of strong importance.
style|A stylesheet written in the page.
sub|Subscript.
summary|The label of a details box.
sup|Superscript.
svg|An inline SVG drawing.
table|A table of rows and columns.
tbody|The body rows of a table.
td|A data cell.
template|Markup kept for script to clone, not shown.
textarea|A multi-line text field.
tfoot|The footer rows of a table.
th|A header cell.
thead|The header rows of a table.
time|A date or time, machine-readable in datetime.
title|The page's title, shown in the tab.
tr|A table row.
track|Timed text for audio or video: captions, subtitles.
u|Text with an unarticulated annotation, underlined.
ul|An unordered, bulleted list.
var|A variable in maths or programming.
video|A video, with the browser's own controls when asked for.
wbr|A place a long word may break.
`;

const DOC_HOVER_HTML_ATTRS = `
id|A name unique in the page, for links, labels, CSS and script.
class|Space-separated class names, for CSS and script.
style|CSS for this element alone.
title|Advisory text, shown as a tooltip.
lang|The language of the element's text.
dir|The direction of its text: ltr, rtl or auto.
hidden|Not shown, and not in the accessibility tree.
tabindex|Whether and in which order it takes keyboard focus.
href|The address a link points to.
src|The address of the resource to embed.
alt|Text in place of an image, for when it is not seen.
rel|How the linked resource relates to this page.
target|Where to open the link: _self, _blank, a frame's name.
type|The kind of control, script, button or resource.
name|The name a form control is sent under.
value|The control's current or initial value.
placeholder|A hint shown in an empty field.
disabled|The control cannot be used.
required|The field must be filled before the form is sent.
checked|The checkbox or radio is selected.
for|The id of the control a label is for.
action|Where a form is sent.
method|How a form is sent: get or post.
width|The width, in pixels.
height|The height, in pixels.
charset|The page's character encoding.
content|The value of a meta element.
role|The element's role for assistive technology.
download|Download the link's target instead of opening it.
loading|When to load: eager, or lazy near the viewport.
defer|Run the script after the page is parsed.
async|Run the script as soon as it arrives.
`;

const DOC_HOVER_CSS = `
display|How the box is laid out, and how its children are.
position|How the box is placed: in the flow, relative, absolute, fixed or sticky.
top|The offset from the top edge of the containing block.
right|The offset from the right edge of the containing block.
bottom|The offset from the bottom edge of the containing block.
left|The offset from the left edge of the containing block.
inset|The four offsets at once: top, right, bottom, left.
z-index|The stacking order of a positioned box.
width|The width of the content box, or the border box with border-box sizing.
height|The height of the content box, or the border box with border-box sizing.
min-width|The smallest the width may become.
max-width|The largest the width may become.
min-height|The smallest the height may become.
max-height|The largest the height may become.
margin|The space outside the border, on all four sides.
padding|The space inside the border, on all four sides.
border|The border's width, style and colour at once.
border-radius|How round the corners are.
box-sizing|Whether width and height include the padding and border.
box-shadow|Shadows cast by the box.
overflow|What happens to content bigger than the box.
color|The colour of the text.
background|The background's colour, image, position and repeat at once.
background-color|The colour behind the content.
background-image|An image or a gradient behind the content.
opacity|How opaque the whole element is, from 0 to 1.
font|The font's style, weight, size, line height and family at once.
font-family|The fonts to use, in order of preference.
font-size|The size of the text.
font-weight|How bold the text is.
font-style|Normal, italic or oblique text.
line-height|The height of each line of text.
letter-spacing|Extra space between letters.
text-align|How lines of text are aligned in their box.
text-decoration|Underlines, overlines and strike-throughs.
text-transform|Upper case, lower case or capitalised text.
text-overflow|How text that overflows its box is shown.
white-space|How spaces and line breaks in the text are handled.
word-break|Where lines may break inside words.
vertical-align|How an inline box sits on its line.
cursor|The pointer shown over the element.
visibility|Whether the box is seen, while still taking its space.
flex|How a flex item grows, shrinks and its starting size.
flex-direction|The direction flex items are laid out in.
flex-wrap|Whether flex items wrap onto more lines.
justify-content|How items are spaced along the main axis.
align-items|How items are aligned across the cross axis.
align-self|How this item is aligned across the cross axis.
align-content|How lines of items are spaced across the cross axis.
gap|The space between rows and columns of a flex or grid layout.
grid-template-columns|The columns of a grid and their sizes.
grid-template-rows|The rows of a grid and their sizes.
grid-column|Which grid columns an item spans.
grid-row|Which grid rows an item spans.
grid-area|The grid area an item is placed in.
place-items|align-items and justify-items at once.
transform|Moves, rotates, scales or skews the element.
transition|How changes to properties are animated.
animation|A keyframe animation's name, timing and repetition at once.
object-fit|How an image or video fills its box.
pointer-events|Whether the element can be the target of the pointer.
user-select|Whether its text can be selected.
content|What a ::before or ::after pseudo-element shows.
list-style|The marker of a list item: its type, position and image.
outline|A line drawn outside the border, not taking space.
filter|Visual effects such as blur or brightness.
aspect-ratio|The preferred ratio of width to height.
`;

const docHoverTables = {};

//: The line for `name` of `kind` ("html", "attr" or "css"), or null. A CSS
//: property's line is followed by the keywords it takes, from the same
//: table the value list uses, so the hover and the list cannot disagree.
function docHoverLine(kind, name, valueTable) {
  const source = { html: DOC_HOVER_HTML, attr: DOC_HOVER_HTML_ATTRS, css: DOC_HOVER_CSS }[kind];
  if (!source) return null;
  if (!docHoverTables[kind]) {
    docHoverTables[kind] = new Map(source.trim().split("\n").map((row) => row.split("|")));
  }
  const key = name.toLowerCase();
  const line = docHoverTables[kind].get(key);
  if (kind !== "css") return line || null;
  const values = (valueTable && valueTable.get(key)) || [];
  if (!line && !values.length) return null;
  const shown = values.slice(0, 12).join(", ") + (values.length > 12 ? ", and more" : "");
  return [line, values.length ? `Values: ${shown}.` : ""].filter(Boolean).join("\n");
}
// DOC-COMPLETE-END

//: Where Emmet comes from. Loaded the first time a document it serves is
//: opened, never at boot, as the editor bundle is; like it, the vendor URL
//: carries no `?v=` stamp (the version is the pin in package.json there).
const DOC_EMMET_BUNDLE = "/vendor/emmet/emmet.min.js";

//: The file types Emmet serves, and the dialect for each (INBOX 402). A
//: `.js` file is mounted with JSX, so there it is `className` and only
//: inside JSX; TypeScript is mounted without JSX and gets none. SCSS, Less
//: and SVG are not file types here, so they are not in the list.
const DOC_EMMET_SYNTAX = { html: "html", css: "css", xml: "xml", js: "jsx" };
let docEmmetLoad = null;

//: Fire and forget. The sources read `window.EMMET` when they are asked, so
//: nothing has to be reconfigured when it lands; until then the lists are
//: the language's own, and if it never loads they stay that way.
function docLoadEmmet() {
  if (window.EMMET) return Promise.resolve(true);
  if (docEmmetLoad) return docEmmetLoad;
  docEmmetLoad = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = DOC_EMMET_BUNDLE;
    script.async = true;
    script.addEventListener("load", () => resolve(true));
    script.addEventListener("error", () => {
      console.warn("Tessellate: the Emmet bundle could not be loaded; completions are the language's own.");
      resolve(false);
    });
    document.head.appendChild(script);
  });
  return docEmmetLoad;
}

//: **js-beautify, for Format on a whole JavaScript, CSS or HTML document**
//: (Brief 42, kept in the vendoring table at a third of prettier's size).
//: Loaded the first time Format runs on one of the three, never at boot, as
//: Emmet is; every other type, and a failed load, keep the conservative
//: re-indent below, which never moves a token. A selection of whole lines
//: goes through the library at its first line's indent level (ledger 1565).
const DOC_BEAUTIFY_BUNDLE = "/vendor/js-beautify/beautify.min.js";
const DOC_BEAUTIFY_TYPES = new Set(["js", "css", "html"]);
const docBeautify = { load: null };

function docLoadBeautify() {
  if (window.JSBEAUTIFY) return Promise.resolve(true);
  if (docBeautify.load) return docBeautify.load;
  docBeautify.load = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = DOC_BEAUTIFY_BUNDLE;
    script.async = true;
    script.addEventListener("load", () => resolve(Boolean(window.JSBEAUTIFY)));
    script.addEventListener("error", () => {
      docBeautify.load = null;
      resolve(false);
    });
    document.head.appendChild(script);
  });
  return docBeautify.load;
}

//: The file type's own indent unit, blank lines kept (at most one in a
//: row), and one line break at the end, as the conservative path does.
function docBeautifyText(text, ext, unit, { level = 0, endWithNewline = true } = {}) {
  if (!text.trim()) return { text, changed: false };
  const tabs = unit === "\t";
  const base = {
    indent_size: tabs ? 1 : unit.length,
    indent_char: tabs ? "\t" : " ",
    indent_with_tabs: tabs,
    end_with_newline: endWithNewline,
    indent_level: level,
    preserve_newlines: true,
    max_preserve_newlines: 2,
  };
  //: `e4x` because a `.js` document is mounted with JSX; a wrap width of 0
  //: because Format here never re-flows a line.
  const out = ext === "js" ? JSBEAUTIFY.js(text, { ...base, e4x: true })
    : ext === "css" ? JSBEAUTIFY.css(text, base)
      : JSBEAUTIFY.html(text, { ...base, wrap_line_length: 0 });
  return { text: out, changed: out !== text };
}

//: Whether the caret is where markup's text goes, rather than inside a tag,
//: an attribute, a comment or a doctype. Inside `<script>` and `<style>` the
//: source is not asked at all: it is mounted on HTML's own language data.
function docHtmlTextAt(CM, state, pos) {
  for (let node = CM.language.syntaxTree(state).resolveInner(pos, -1); node; node = node.parent) {
    if (/Tag$|^(TagName|Attribute|AttributeName|AttributeValue|Comment|DoctypeDecl|ProcessingInst)$/.test(node.name)) return false;
  }
  return true;
}

//: The same question in JSX: inside an element's children, and not in a
//: tag, an attribute or a `{...}` expression (which is JavaScript again).
//: Everywhere else in a `.js` file the answer is no, because `a`, `b`, `i`,
//: `p` and `s` are the commonest names in JavaScript and every one is a tag.
function docJsxChildAt(CM, state, pos) {
  for (let node = CM.language.syntaxTree(state).resolveInner(pos, -1); node; node = node.parent) {
    if (/^JSX(OpenTag|CloseTag|SelfClosingTag|Attribute|AttributeValue|Escape|FragmentTag)$/.test(node.name)) return false;
    if (node.name === "JSXElement" || node.name === "JSXFragment") return true;
  }
  return false;
}

//: XML is a stream mode here, with no tree to ask: outside a tag is after
//: the last `>` rather than the last `<`.
function docXmlTextAt(state, pos) {
  const before = state.sliceDoc(Math.max(0, pos - 4000), pos);
  return before.lastIndexOf("<") <= before.lastIndexOf(">");
}

function docEmmetPlace(CM, state, pos, syntax) {
  if (syntax === "css") return docCssInBlock(CM, state, pos);
  if (syntax === "jsx") return docJsxChildAt(CM, state, pos);
  if (syntax === "xml") return docXmlTextAt(state, pos);
  return docHtmlTextAt(CM, state, pos);
}

//: Whether the caret is inside a CSS rule's braces.
function docCssInBlock(CM, state, pos) {
  for (let node = CM.language.syntaxTree(state).resolveInner(pos, -1); node; node = node.parent) {
    if (node.name === "Block") return true;
  }
  return false;
}

//: The Emmet row at the caret, or null: `{ from, to, template, preview, abbr }`
//: in document positions.
function docEmmetMatch(CM, state, pos, syntax, anywhere) {
  const E = window.EMMET;
  if (!E) return null;
  if (!docEmmetPlace(CM, state, pos, syntax)) return null;
  const line = state.doc.lineAt(pos);
  const found = docEmmetAt(line.text, pos - line.from, syntax, E, anywhere);
  if (!found) return null;
  const expansion = docEmmetExpansion(E, found.abbr, syntax);
  if (!expansion) return null;
  return { from: line.from + found.start, to: line.from + found.end, abbr: found.abbr, ...expansion };
}

//: The detail pane for an Emmet row: the expansion as it will read, cut at
//: twenty lines.
function docEmmetInfo(preview) {
  const pre = document.createElement("pre");
  pre.className = "cm-emmet-preview";
  const lines = preview.split("\n");
  pre.textContent = lines.length > 20 ? [...lines.slice(0, 20), "…"].join("\n") : preview;
  return pre;
}

//: One stable function per syntax, for the reason `docCodeCompletionSource`
//: gives: the engine tells sources apart by identity.
const docEmmetSourceCache = {};

function docEmmetSource(CM, syntax) {
  if (docEmmetSourceCache[syntax]) return docEmmetSourceCache[syntax];
  docEmmetSourceCache[syntax] = (context) => {
    const found = docEmmetMatch(CM, context.state, context.pos, syntax, context.explicit);
    if (!found) return null;
    return {
      from: found.from,
      to: found.to,
      filter: false,
      options: [{
        label: found.abbr,
        detail: "Emmet",
        type: "keyword",
        boost: 50,
        info: () => docEmmetInfo(found.preview),
        apply: CM.autocomplete.snippet(found.template),
      }],
    };
  };
  return docEmmetSourceCache[syntax];
}

//: Tab with the list closed: expand the abbreviation before the caret, as
//: VS Code's `emmet.triggerExpansionOnTab` does. False when there is none,
//: so Tab goes on to indent.
function docEmmetExpandAtCaret(view, CM) {
  const syntax = DOC_EMMET_SYNTAX[docFileType().ext];
  const range = view.state.selection.main;
  if (!syntax || !range.empty) return false;
  const found = docEmmetMatch(CM, view.state, range.head, syntax, true);
  if (!found) return false;
  CM.autocomplete.snippet(found.template)(view, null, found.from, found.to);
  return true;
}

//: The markup dialect of the open code document, or null (CSS has no tags
//: to wrap or balance).
function docEmmetMarkupSyntax() {
  const type = docFileType();
  const syntax = DOC_EMMET_SYNTAX[type.ext];
  if (!docCmView || !window.CM6 || type.previewable || docView === "plain") return null;
  return syntax && syntax !== "css" ? syntax : null;
}

//: **Wrap with abbreviation**, VS Code's Emmet command: the selection (or
//: the line, without its indentation) goes inside what an abbreviation
//: makes, `ul>li*` taking one item per line. The abbreviation is asked for
//: in the app's own dialog; the last one is offered again.
let docEmmetLastWrap = "div";

async function docEmmetWrap() {
  const syntax = docEmmetMarkupSyntax();
  if (!syntax) {
    toast("Wrap with an abbreviation works in HTML, XML and JSX files.");
    return false;
  }
  const view = docCmView;
  const CM = window.CM6;
  if (!(await docLoadEmmet()) || !window.EMMET) {
    toast("Emmet could not be loaded, so nothing was wrapped.", true);
    return false;
  }
  let { from, to } = view.state.selection.main;
  const first = view.state.doc.lineAt(from);
  const indent = /^\s*/.exec(first.text)[0];
  if (from === to) {
    from = first.from + indent.length;
    to = first.to;
  }
  const abbr = await promptDialog("Wrap with an abbreviation", docEmmetLastWrap, { confirmLabel: "Wrap" });
  if (!abbr || !docCmView) return false;
  const text = docEmmetWrapText(view.state.sliceDoc(from, to), indent, abbr);
  const expansion = docEmmetExpansion(window.EMMET, abbr, syntax, text);
  if (!expansion) {
    toast(`Emmet cannot read "${abbr}" as an abbreviation.`, "info");
    return false;
  }
  docEmmetLastWrap = abbr;
  view.focus();
  CM.autocomplete.snippet(expansion.template)(view, null, from, to);
  markDocDirty();
  return true;
}

//: **Balance**, VS Code's Emmet command: select the tag around the
//: selection's content, then the tag, then its parent's content and so on
//: (outward), or back in (inward). From the text, by Emmet's own matcher, so
//: HTML, XML and JSX all work the same way.
function docEmmetBalance(inward) {
  const syntax = docEmmetMarkupSyntax();
  const E = window.EMMET;
  if (!syntax || !E) return false;
  const view = docCmView;
  const text = docStr(view.state.doc);
  const { from, to } = view.state.selection.main;
  const options = { xml: syntax !== "html" };
  const into = inward && from !== to;
  const tags = into ? E.balancedInward(text, from, options) : E.balancedOutward(text, from, options);
  const range = docBalanceRange(tags, from, to, into);
  if (!range) return false;
  view.dispatch({ selection: { anchor: range[0], head: range[1] }, scrollIntoView: true });
  view.focus();
  return true;
}

//: A CSS property's row, taken: the name, then `: `, then the value list
//: opened straight away, VS Code's order. Not where a colon already follows.
function docCssPropertyApply(CM) {
  return (view, completion, from, to) => {
    const colon = /^\s*:/.test(view.state.sliceDoc(to, to + 40));
    const insert = colon ? completion.label : `${completion.label}: `;
    view.dispatch({
      changes: { from, to, insert },
      selection: { anchor: from + insert.length },
      userEvent: "input.complete",
      annotations: CM.autocomplete.pickedCompletion.of(completion),
    });
    if (!colon) CM.autocomplete.startCompletion(view);
  };
}

//: The CSS document's list: the package's own properties, pseudo-classes and
//: at-rules, with each property's own values in place of its flat list.
let docCssCompletionCache = null;

function docCssCompletionSource(CM) {
  if (docCssCompletionCache) return docCssCompletionCache;
  const applyProperty = docCssPropertyApply(CM);
  docCssCompletionCache = (context) => {
    const { state, pos } = context;
    const native = CM.css.cssCompletionSource(context);
    const value = docCssInBlock(CM, state, pos)
      ? docCssValueContext(state.sliceDoc(Math.max(0, pos - 400), pos))
      : null;
    if (value) {
      const table = docCssValueTable(window.EMMET);
      const own = docCssValueOptions(value.property, table);
      //: A property whose values are known gets those and nothing else:
      //: `display: f` offering `fantasy` and `firebrick` is the flat list
      //: this replaces. One that is not known (`width`, a custom property)
      //: keeps the package's list after its own, as a fallback.
      const known = table.has(value.property) || DOC_CSS_COLOR_PROPERTY.test(value.property);
      const seen = new Set(own.map((o) => o.label));
      const rest = known ? [] : (native?.options || []).filter((o) => !seen.has(o.label)).map((o) => ({ ...o, boost: -5 }));
      return {
        from: pos - value.word.length,
        options: [...own.map((o) => ({ ...o, type: "constant" })), ...rest],
        validFor: /^[\w-]*$/,
      };
    }
    if (!native) return null;
    return {
      ...native,
      options: native.options.map((o) => (o.type === "property" ? { ...o, apply: applyProperty } : o)),
    };
  };
  return docCssCompletionCache;
}

let docCssSourcesCache = null;

function docCssSources(CM) {
  if (!docCssSourcesCache) docCssSourcesCache = [docCssCompletionSource(CM), docEmmetSource(CM, "css")];
  return docCssSourcesCache;
}

//: Tab: the chosen row when the list is open (the ghost text shows which),
//: else an Emmet abbreviation, else nothing, so the editor's own Tab
//: indents. Enter is not here: it is the list's, in its own keymap.
function docCompleteTab(view, CM) {
  const ac = CM.autocomplete;
  if (ac.completionStatus(view.state) === "active" && ac.selectedCompletion(view.state)) {
    return ac.acceptCompletion(view);
  }
  return docEmmetExpandAtCaret(view, CM);
}

//: The ghost text: a widget after the caret holding the rest of the chosen
//: row, rebuilt on every update (the list's choice moves with the arrows).
let docGhostPluginCache = null;

function docGhostPlugin(CM) {
  if (docGhostPluginCache) return docGhostPluginCache;
  const { Decoration, ViewPlugin, WidgetType } = CM.view;
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
    const ac = CM.autocomplete;
    const range = state.selection.main;
    if (!range.empty || ac.completionStatus(state) !== "active") return Decoration.none;
    const chosen = ac.selectedCompletion(state);
    if (!chosen) return Decoration.none;
    const line = state.doc.lineAt(range.head);
    const col = range.head - line.from;
    const rest = docGhostSuffix(line.text.slice(0, col), line.text.slice(col), chosen.label);
    if (!rest) return Decoration.none;
    return Decoration.set([Decoration.widget({ widget: new Ghost(rest), side: 1 }).range(range.head)]);
  };
  docGhostPluginCache = ViewPlugin.fromClass(
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
  return docGhostPluginCache;
}

//: Everything above, for a code document: the list opening as you type,
//: Emmet where the type has it, the ghost text and Tab.
//: **Rename the matching tag, as you type** (INBOX 402). A transaction
//: filter rather than a second dispatch, so the partner's rename rides in
//: the same transaction as the keystroke: one undo step takes both back.
//: Only a user's own typing or deleting inside a tag's name is followed, and
//: in a `.js` file only inside JSX, where the tree says the caret is in a
//: JSX tag (the matcher reads text, and `a <b` in JavaScript is not a tag).
const docTagLinkCache = {};

function docTagLink(CM, syntax) {
  if (docTagLinkCache[syntax]) return docTagLinkCache[syntax];
  docTagLinkCache[syntax] = CM.state.EditorState.transactionFilter.of((tr) => {
    if (!tr.docChanged || !(tr.isUserEvent("input.type") || tr.isUserEvent("delete"))) return tr;
    const E = window.EMMET;
    if (!E) return tr;
    const edits = [];
    tr.changes.iterChanges((fromA, toA, _fromB, _toB, inserted) => edits.push([fromA, toA, inserted.toString()]));
    if (edits.length !== 1) return tr;
    const [fromA, toA, insert] = edits[0];
    const start = tr.startState;
    const line = start.doc.lineAt(fromA);
    //: The cheap test first: the edit touches `<name` or `</name` on its
    //: line. Only then is the whole text handed to the matcher.
    if (!/<\/?[\w:.-]*$/.test(line.text.slice(0, fromA - line.from))) return tr;
    if (syntax === "jsx") {
      let inTag = false;
      for (let node = CM.language.syntaxTree(start).resolveInner(fromA, -1), k = 0; node && k < 4; node = node.parent, k += 1) {
        if (/^JSX(OpenTag|CloseTag)$/.test(node.name)) inTag = true;
      }
      if (!inTag) return tr;
    }
    const partner = docTagRename(E, docStr(start.doc), fromA, toA, insert, syntax !== "html");
    if (!partner) return tr;
    return [tr, { changes: partner, sequential: true }];
  });
  return docTagLinkCache[syntax];
}

//: XML's auto-close and `</` completion, as an input handler: `>` after
//: `<item` writes `></item>` with the caret between, and `/` after `<`
//: finishes the innermost open element's close. HTML and JSX already have
//: both from their grammars (`autoCloseTags`).
let docXmlCloseCache = null;

function docXmlAutoClose(CM) {
  if (docXmlCloseCache) return docXmlCloseCache;
  docXmlCloseCache = CM.view.EditorView.inputHandler.of((view, from, to, text) => {
    if ((text !== ">" && text !== "/") || from !== to || view.state.readOnly) return false;
    const before = view.state.sliceDoc(Math.max(0, from - 20000), from);
    if (text === ">") {
      const name = docXmlOpenedBy(before);
      if (!name) return false;
      view.dispatch({
        changes: { from, insert: `></${name}>` },
        selection: { anchor: from + 1 },
        userEvent: "input.type",
      });
      return true;
    }
    if (!before.endsWith("<")) return false;
    const name = docXmlUnclosed(before.slice(0, -1));
    if (!name) return false;
    view.dispatch({
      changes: { from, insert: `/${name}>` },
      selection: { anchor: from + name.length + 2 },
      userEvent: "input.type",
    });
    return true;
  });
  return docXmlCloseCache;
}

//: **Colour swatches** (INBOX 402), VS Code's colour decorators: a small
//: square before each colour in a CSS value (a hex, `rgb()`, `hsl()` and
//: their alpha forms, a named colour), in the colour itself, and a click on
//: it opens the browser's own colour picker. From the tree, so only real
//: values get one (a colour word in a comment or a selector does not), and
//: only over the visible lines. HTML's `<style>` is the same CSS tree.
function docColorAt(view, swatch, from, to) {
  const original = view.state.sliceDoc(from, to);
  const probe = document.createElement("span");
  probe.style.color = original;
  document.body.appendChild(probe);
  const hex = docRgbToHex(getComputedStyle(probe).color) || "#000000";
  probe.remove();
  const input = document.createElement("input");
  input.type = "color";
  input.value = hex;
  input.className = "doc-color-input";
  input.setAttribute("aria-label", "Pick a colour");
  //: Where the swatch is, because the picker opens beside its input; not
  //: seen and not in the way. Set as properties: the CSP refuses `style=`.
  const box = swatch.getBoundingClientRect();
  Object.assign(input.style, {
    position: "fixed", left: `${box.left}px`, top: `${box.bottom}px`,
    width: "1px", height: "1px", opacity: "0", border: "0", padding: "0",
  });
  document.body.appendChild(input);
  let range = { from, to };
  input.addEventListener("input", () => {
    const text = docCssColorFormat(view.state.sliceDoc(range.from, range.to), input.value);
    view.dispatch({ changes: { from: range.from, to: range.to, insert: text }, userEvent: "input.color" });
    range = { from: range.from, to: range.from + text.length };
    markDocDirty();
  });
  const done = () => input.remove();
  input.addEventListener("change", done);
  input.addEventListener("blur", done);
  try {
    input.showPicker();
  } catch {
    input.click();
  }
  return input;
}

let docColorPluginCache = null;

function docColorSwatches(CM) {
  if (docColorPluginCache) return docColorPluginCache;
  const { Decoration, ViewPlugin, WidgetType } = CM.view;
  class Swatch extends WidgetType {
    constructor(color, from, to) {
      super();
      this.color = color;
      this.from = from;
      this.to = to;
    }
    eq(other) {
      return other.color === this.color && other.from === this.from;
    }
    toDOM(view) {
      const el = document.createElement("span");
      el.className = "cm-color-swatch";
      el.setAttribute("role", "button");
      el.setAttribute("aria-label", `Pick a colour for ${this.color}`);
      el.title = "Pick a colour";
      el.style.backgroundColor = this.color;
      el.addEventListener("mousedown", (event) => {
        event.preventDefault();
        docColorAt(view, el, this.from, this.to);
      });
      return el;
    }
    ignoreEvent() {
      return true;
    }
  }
  const named = new Set(DOC_CSS_COLORS.filter((c) => c !== "transparent" && c !== "currentcolor"));
  const build = (view) => {
    const found = [];
    const { state } = view;
    for (const { from, to } of view.visibleRanges) {
      CM.language.syntaxTree(state).iterate({
        from,
        to,
        enter: (node) => {
          if (node.name === "CallExpression") {
            const callee = node.node.getChild("Callee");
            const name = callee ? state.sliceDoc(callee.from, callee.to) : "";
            if (!/^(rgba?|hsla?|hwb|lab|lch|oklab|oklch)$/i.test(name)) return;
          } else if (node.name === "ValueName") {
            if (!named.has(state.sliceDoc(node.from, node.to).toLowerCase())) return;
          } else if (node.name !== "ColorLiteral") return;
          const text = state.sliceDoc(node.from, node.to);
          if (typeof CSS !== "undefined" && !CSS.supports("color", text)) return false;
          found.push(Decoration.widget({ widget: new Swatch(text, node.from, node.to), side: -1 }).range(node.from));
          return false;
        },
      });
    }
    return Decoration.set(found, true);
  };
  docColorPluginCache = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = build(view);
      }
      update(update) {
        if (update.docChanged || update.viewportChanged || CM.language.syntaxTree(update.startState) !== CM.language.syntaxTree(update.state)) {
          this.decorations = build(update.view);
        }
      }
    },
    { decorations: (plugin) => plugin.decorations }
  );
  return docColorPluginCache;
}

//: **Hover docs** (INBOX 402): a CSS property, an HTML element or an HTML
//: attribute under the pointer gets its one line (`docHoverLine`), on the
//: hover card the diagnostics already use. From the tree, so a word in text
//: or in a comment gets nothing.
let docHoverDocsCache = null;

function docHoverDocs(CM) {
  if (docHoverDocsCache) return docHoverDocsCache;
  docHoverDocsCache = CM.view.hoverTooltip((view, pos, side) => {
    if (docFileType().ext === "py") return docPyHover(CM, view, pos, side);
    const node = CM.language.syntaxTree(view.state).resolveInner(pos, side);
    const kind = { PropertyName: "css", TagName: "html", AttributeName: "attr" }[node.name];
    if (!kind) return null;
    const name = view.state.sliceDoc(node.from, node.to);
    const line = docHoverLine(kind, name, docCssValueTable(window.EMMET));
    if (!line) return null;
    return {
      pos: node.from,
      end: node.to,
      above: true,
      create: () => {
        const dom = document.createElement("div");
        dom.className = "cm-hover-doc";
        const head = document.createElement("code");
        head.textContent = kind === "html" ? `<${name}>` : name;
        dom.appendChild(head);
        for (const part of line.split("\n")) {
          const row = document.createElement("div");
          row.className = part.startsWith("Values:") ? "cm-hover-doc-values" : "cm-hover-doc-line";
          row.textContent = part;
          dom.appendChild(row);
        }
        return { dom };
      },
    };
  });
  return docHoverDocsCache;
}

//: A standard library name under the pointer in a Python file (`math.sqrt`,
//: OPEN 1070): its signature and its doc's first line, the signature help
//: VS Code's hover gives. Only once the table has been fetched (the first
//: completion after a dot fetches it), so a hover never waits on a request.
async function docPyHover(CM, view, pos, side) {
  const node = CM.language.syntaxTree(view.state).resolveInner(pos, side);
  if (node.name !== "PropertyName" || node.parent?.name !== "MemberExpression") return null;
  const dotted = view.state.sliceDoc(node.parent.from, node.from).replace(/\.\s*$/, "").replace(/\s+/g, "");
  if (!/^[A-Za-z_][\w.]*$/.test(dotted)) return null;
  const rows = docPyStdlibRows(await docPyStdlibTable(), docPyImports(docStr(view.state.doc)), dotted);
  const name = view.state.sliceDoc(node.from, node.to);
  const row = rows?.find((r) => r[0] === name);
  if (!row) return null;
  return {
    pos: node.from,
    end: node.to,
    above: true,
    create: () => {
      const dom = document.createElement("div");
      dom.className = "cm-hover-doc";
      const head = document.createElement("code");
      head.textContent = row[2] || `${dotted}.${name}`;
      dom.appendChild(head);
      if (row[3]) {
        const line = document.createElement("div");
        line.className = "cm-hover-doc-line";
        line.textContent = row[3];
        dom.appendChild(line);
      }
      return { dom };
    },
  };
}

//: **Indentation guides** (INBOX 402): a hairline at each indent step of a
//: line's leading whitespace, VS Code's guides. One mark per step of the
//: whitespace (a tab, or the unit's run of spaces), each drawing a
//: one-pixel line at its own left edge, so a guide sits exactly where the
//: step starts whatever the face (the code face's space is not its `ch`,
//: measured: 5.1px against 10.2px, so a background stepped in `ch` drifted
//: a guide per level) and can never reach past the indentation into the
//: code. Quiet on purpose: `--border`, the hairline the app uses everywhere.
const docIndentGuideCache = new Map();

//: The steps of a line's leading whitespace, as `[from, to]` columns: each
//: tab, and each full run of `unit` spaces; a short run left over is not a
//: step and gets no guide.
function docIndentSteps(lead, unit) {
  const steps = [];
  const size = unit === "\t" ? 4 : Math.max(1, unit.length);
  let col = 0;
  while (col < lead.length) {
    if (lead[col] === "\t") {
      steps.push([col, col + 1]);
      col += 1;
      continue;
    }
    let run = 0;
    while (col + run < lead.length && lead[col + run] === " " && run < size) run += 1;
    if (run < size) break;
    steps.push([col, col + run]);
    col += run;
  }
  return steps;
}

function docIndentGuides(CM, unit) {
  if (docIndentGuideCache.has(unit)) return docIndentGuideCache.get(unit);
  const { Decoration, ViewPlugin } = CM.view;
  //: **Every step is drawn one fixed width, 2em, whatever the file's unit**
  //: (the owner, 2026-09-24, INBOX 409: "the degree of indenting is shallow,
  //: I think it should be more prominent", on a two-space .json). The code
  //: face is proportional, so a space is narrow: measured, four spaces drew
  //: 2.6 character widths and two drew 1.3. The file keeps its own spaces;
  //: only their drawn width changes, by letter-spacing on the step this
  //: plugin already marks (`calc(2em / N - space)`, the space measured from
  //: the editor's own font below). CodeMirror reads the caret from the DOM,
  //: so clicks and arrows land where the text is drawn. Tabs are left as
  //: they are.
  const size = unit === "\t" ? 0 : Math.max(1, Math.min(8, unit.length));
  const mark = Decoration.mark({ class: size ? `cm-indent-guide cm-indent-w${size}` : "cm-indent-guide" });
  const measureSpace = (view) => {
    const ctx = (docIndentGuides.canvas ||= document.createElement("canvas")).getContext("2d");
    ctx.font = getComputedStyle(view.contentDOM).font;
    view.contentDOM.style.setProperty("--doc-space-w", `${ctx.measureText(" ").width}px`);
  };
  const build = (view) => {
    const found = [];
    for (const { from, to } of view.visibleRanges) {
      for (let pos = from; pos <= to; ) {
        const line = view.state.doc.lineAt(pos);
        const lead = /^[ \t]*/.exec(line.text)[0];
        for (const [a, b] of docIndentSteps(lead, unit)) found.push(mark.range(line.from + a, line.from + b));
        pos = line.to + 1;
      }
    }
    return Decoration.set(found);
  };
  const plugin = ViewPlugin.fromClass(
    class {
      constructor(view) {
        measureSpace(view);
        this.decorations = build(view);
      }
      update(update) {
        if (update.geometryChanged) measureSpace(update.view);
        if (update.docChanged || update.viewportChanged) this.decorations = build(update.view);
      }
    },
    { decorations: (p) => p.decorations }
  );
  docIndentGuideCache.set(unit, plugin);
  return plugin;
}

//: **Bracket pair colours** (INBOX 402): `()`, `[]` and `{}` coloured by how
//: deep they sit, three tones in turn, VS Code's colouriser. A bracket inside
//: a string, a comment, a regular expression or HTML's text is not a bracket
//: and is left alone: the tree says which, for the full grammars and for the
//: stream modes alike (their tokens are named `string` and `comment`). The
//: depth is counted from the top of the file to the end of what is shown, so
//: it is right wherever the view scrolls to; past the checker's own size cap
//: it is not worth a keystroke and nothing is coloured.
const DOC_BRACKET_NOT_CODE = /String|string|Comment|comment|RegExp|regexp|^Text$|AttributeValue|^Escape$|^meta$/;

//: `[position, depth]` for each bracket of `text` from `start` on, the depth
//: counted from the top; `inCode(i)` says whether position `i` is code.
function docBracketDepths(text, start, inCode) {
  const found = [];
  let depth = 0;
  for (let i = 0; i < text.length; i += 1) {
    const open = "([{".indexOf(text[i]);
    const close = open < 0 ? ")]}".indexOf(text[i]) : -1;
    if (open < 0 && close < 0) continue;
    if (!inCode(i)) continue;
    if (close >= 0) depth = Math.max(0, depth - 1);
    if (i >= start) found.push([i, depth]);
    if (open >= 0) depth += 1;
  }
  return found;
}

let docBracketColourCache = null;

function docBracketColours(CM) {
  if (docBracketColourCache) return docBracketColourCache;
  const { Decoration, ViewPlugin } = CM.view;
  const marks = [0, 1, 2].map((k) => Decoration.mark({ class: `cm-bracket-${k}` }));
  const build = (view) => {
    const ranges = view.visibleRanges;
    if (!ranges.length) return Decoration.none;
    const end = ranges[ranges.length - 1].to;
    if (end > DOC_CHECK_MAX_CHARS) return Decoration.none;
    const tree = CM.language.syntaxTree(view.state);
    const inCode = (i) => !DOC_BRACKET_NOT_CODE.test(tree.resolveInner(i, 1).name);
    const found = docBracketDepths(view.state.sliceDoc(0, end), ranges[0].from, inCode);
    return Decoration.set(found.map(([i, depth]) => marks[depth % 3].range(i, i + 1)));
  };
  docBracketColourCache = ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = build(view);
      }
      update(update) {
        if (update.docChanged || update.viewportChanged || CM.language.syntaxTree(update.startState) !== CM.language.syntaxTree(update.state)) {
          this.decorations = build(update.view);
        }
      }
    },
    { decorations: (p) => p.decorations }
  );
  return docBracketColourCache;
}

//: **A code file's symbols, as the outline's headings** (INBOX 402, VS
//: Code's outline and breadcrumbs): its functions, classes and methods (and
//: a TypeScript file's interfaces, types and enums, a CSS file's rules and
//: at-rules), in the shape `docScanHeadings` gives a markdown file's
//: headings, `{ line, text, level }`, so the outline panel, its filter, its
//: current-row mark and the breadcrumb all read them unchanged. `level` is
//: the nesting: a method sits under its class. From the Lezer tree, so a
//: word in a string or a comment is never a symbol. `symbol: true` marks
//: the rows the outline must not offer to move: a heading's section is a
//: run of lines, a function is not.
const DOC_SYMBOL_EXTS = new Set(["js", "ts", "py", "css"]);

function docCodeSymbols(CM, state, ext) {
  if (!DOC_SYMBOL_EXTS.has(ext)) return [];
  const tree = CM.language.ensureSyntaxTree(state, state.doc.length, 50) || CM.language.syntaxTree(state);
  const text = (node) => state.sliceDoc(node.from, node.to);
  const nameOf = (node, ...kinds) => {
    for (const kind of kinds) {
      const child = node.getChild(kind);
      if (child) return text(child);
    }
    return "";
  };
  const found = [];
  const stack = [];
  tree.iterate({
    enter: (ref) => {
      const node = ref.node;
      let label = "";
      switch (node.name) {
        case "FunctionDeclaration":
          label = `${nameOf(node, "VariableDefinition")}()`;
          break;
        case "ClassDeclaration":
          label = `class ${nameOf(node, "VariableDefinition", "TypeDefinition")}`;
          break;
        case "MethodDeclaration":
          label = `${nameOf(node, "PropertyDefinition", "PrivatePropertyDefinition")}()`;
          break;
        case "InterfaceDeclaration":
          label = `interface ${nameOf(node, "TypeDefinition")}`;
          break;
        case "TypeAliasDeclaration":
          label = `type ${nameOf(node, "TypeDefinition")}`;
          break;
        case "EnumDeclaration":
          label = `enum ${nameOf(node, "TypeDefinition")}`;
          break;
        case "VariableDeclaration": {
          //: Only a name bound to a function: `const f = () => ...` is a
          //: function in all but keyword; `const n = 3` is not a symbol.
          if (node.getChild("ArrowFunction") || node.getChild("FunctionExpression")) {
            label = `${nameOf(node, "VariableDefinition")}()`;
          }
          break;
        }
        case "FunctionDefinition":
          label = `${nameOf(node, "VariableName")}()`;
          break;
        case "ClassDefinition":
          label = `class ${nameOf(node, "VariableName")}`;
          break;
        case "RuleSet":
        case "MediaStatement":
        case "KeyframesStatement":
        case "SupportsStatement": {
          const block = node.getChild("Block");
          label = state.sliceDoc(node.from, block ? block.from : node.to).replace(/\s+/g, " ").trim();
          if (label.length > 60) label = `${label.slice(0, 57)}…`;
          break;
        }
        default:
          return;
      }
      if (!label || /^(class |interface |type |enum )?\(?\)?$/.test(label)) return;
      while (stack.length && stack[stack.length - 1] <= node.from) stack.pop();
      found.push({ line: state.doc.lineAt(node.from).number - 1, text: label, level: stack.length + 1, symbol: true, from: node.from, to: node.to });
      stack.push(node.to);
    },
  });
  return found;
}

//: The symbols a position is inside whose first line is above `topLine`
//: (1-based), outermost first, at most `max`: the lines sticky scroll pins.
function docStickyHeaders(symbols, pos, topLine, max = 3) {
  return symbols
    .filter((s) => s.from <= pos && pos < s.to && s.line + 1 < topLine)
    .sort((a, b) => a.from - b.from)
    .slice(-max);
}

//: **A plugin never asks for a measure from inside CodeMirror's measure loop**
//: (INBOX 1492, "Measure loop restarted more than 5 times"). `geometryChanged`,
//: `viewportChanged` and `heightChanged` are set on the updates the loop itself
//: produces, so a `requestMeasure` from `update` on one of them adds a pass to
//: the loop it is in, and a document whose lines take four passes to settle
//: reaches the sixth. This asks once per frame instead, from outside the loop:
//: any number of calls in a frame are one request (`plugin.measureFrame` is
//: the pending frame), and a destroyed plugin's is dropped. The class is
//: pinned by tests/test_cm_measure_loop_1031.py.
function docMeasureNextFrame(plugin, view, spec) {
  if (plugin.measureFrame) return;
  plugin.measureFrame = requestAnimationFrame(() => {
    plugin.measureFrame = 0;
    if (!plugin.measureDead) view.requestMeasure(spec);
  });
}

//: **Sticky scroll** (INBOX 402, VS Code's): while the view is scrolled into
//: a function, a class or a rule, its first line stays pinned at the top of
//: the pane, and the lines of the scopes around it above that, so the reader
//: always knows what they are inside. An overlay laid over the top of the
//: scroller rather than a panel, because a panel would shrink and grow the
//: scroller as scopes are entered and the text would jump under the pointer.
//: Opaque, as anything laid over words is; a click jumps to that line. The
//: symbols are read once per tree, not per scroll event.
let docStickyCache = null;

function docStickyScroll(CM) {
  if (docStickyCache) return docStickyCache;
  docStickyCache = CM.view.ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.view = view;
        this.dom = document.createElement("div");
        this.dom.className = "cm-sticky hidden";
        this.dom.setAttribute("aria-hidden", "true");
        view.dom.appendChild(this.dom);
        this.symbols = null;
        this.tree = null;
        this.key = "";
        this.spec = { key: this, read: () => this.read(), write: (m) => this.write(m) };
        this.onScroll = () => this.schedule();
        view.scrollDOM.addEventListener("scroll", this.onScroll, { passive: true });
        this.schedule();
      }
      update(update) {
        if (update.docChanged) this.schedule();
        else if (update.viewportChanged || update.geometryChanged) docMeasureNextFrame(this, this.view, this.spec);
      }
      schedule() {
        this.view.requestMeasure(this.spec);
      }
      read() {
        const view = this.view;
        const tree = CM.language.syntaxTree(view.state);
        if (tree !== this.tree) {
          this.tree = tree;
          this.symbols = docCodeSymbols(CM, view.state, docFileType().ext);
        }
        const scroller = view.scrollDOM.getBoundingClientRect();
        const outer = view.dom.getBoundingClientRect();
        const content = view.contentDOM.getBoundingClientRect();
        const lineHeight = view.defaultLineHeight;
        let top = view.lineBlockAtHeight(Math.max(0, scroller.top - view.documentTop));
        let headers = docStickyHeaders(this.symbols, top.from, view.state.doc.lineAt(top.from).number);
        //: The pinned lines cover the lines under them: ask again from the
        //: first line they leave showing, so a scope that ends under the
        //: overlay is not still pinned.
        if (headers.length) {
          top = view.lineBlockAtHeight(Math.max(0, scroller.top - view.documentTop + headers.length * lineHeight));
          headers = docStickyHeaders(this.symbols, top.from, view.state.doc.lineAt(top.from).number);
        }
        //: The code's own face and line box, and its lines' left padding, so
        //: a pinned line sits column for column over the line it repeats.
        //: Measured from a line rather than the content box, whose own
        //: padding (the reading measure's inset) is not the line's.
        const face = getComputedStyle(view.contentDOM);
        const firstLine = view.contentDOM.querySelector(".cm-line");
        const lineBox = firstLine ? firstLine.getBoundingClientRect() : content;
        return {
          headers,
          top: scroller.top - outer.top,
          left: lineBox.left - outer.left,
          width: Math.min(lineBox.width, scroller.right - lineBox.left),
          font: face.font,
          lineHeight: `${lineHeight}px`,
          pad: firstLine ? getComputedStyle(firstLine).paddingLeft : "0px",
        };
      }
      write({ headers, top, left, width, font, lineHeight, pad }) {
        const key = headers.map((h) => h.line).join(",");
        this.dom.classList.toggle("hidden", !headers.length);
        Object.assign(this.dom.style, { top: `${top}px`, left: `${left}px`, width: `${width}px`, font, lineHeight });
        this.dom.style.setProperty("--sticky-pad", pad);
        if (key === this.key) return;
        this.key = key;
        this.dom.replaceChildren(
          ...headers.map((h) => {
            const row = document.createElement("div");
            row.className = "cm-sticky-line";
            row.textContent = this.view.state.doc.line(h.line + 1).text;
            row.title = `Go to line ${h.line + 1}`;
            row.addEventListener("mousedown", (event) => {
              event.preventDefault();
              jumpToDocLine(h.line);
            });
            return row;
          })
        );
      }
      destroy() {
        this.measureDead = true;
        this.view.scrollDOM.removeEventListener("scroll", this.onScroll);
        this.dom.remove();
      }
    }
  );
  return docStickyCache;
}

// --- Go to definition, references, find in documents (INBOX 404) ---------------
//
// Within one file, from the tree: F12 goes to where the name at the caret is
// defined, Shift+F12 lists every place it is used. A name in a string or a
// comment is text, not a use (the bracket colours' own test, so the two
// cannot disagree about what is code). Across documents, Ctrl+Shift+F opens
// the app's own Find anything on documents, with the selection or the word.

//: The identifier at `pos`, as `{ from, to, name }`, or null.
function docWordAt(state, pos) {
  const line = state.doc.lineAt(pos);
  const col = pos - line.from;
  const before = /[\w$]*$/.exec(line.text.slice(0, col))[0];
  const after = /^[\w$]*/.exec(line.text.slice(col))[0];
  const name = before + after;
  if (!name || /^\d/.test(name)) return null;
  return { from: pos - before.length, to: pos + after.length, name };
}

//: Every use of `name` as a whole word in code, as `{ from, to }`.
function docReferencesOf(CM, state, name) {
  const text = docStr(state.doc);
  if (text.length > DOC_CHECK_MAX_CHARS) return [];
  const tree = CM.language.ensureSyntaxTree(state, state.doc.length, 200) || CM.language.syntaxTree(state);
  const found = [];
  const escaped = name.replace(/\$/g, "\\$");
  const re = new RegExp(`(?<![\\w$])${escaped}(?![\\w$])`, "g");
  let match;
  while ((match = re.exec(text)) !== null) {
    if (DOC_BRACKET_NOT_CODE.test(tree.resolveInner(match.index, 1).name)) continue;
    found.push({ from: match.index, to: match.index + name.length });
  }
  return found;
}

//: The node names that define a name, by grammar, and the scopes a
//: definition belongs to; a definition in a scope around the caret wins
//: over one elsewhere, the innermost first.
const DOC_DEFINING = /^(VariableDefinition|TypeDefinition|PropertyDefinition|PrivatePropertyDefinition)$/;
const DOC_SCOPES = /^(Script|Block|ClassBody|FunctionDeclaration|FunctionExpression|ArrowFunction|MethodDeclaration|FunctionDefinition|ClassDefinition|Body)$/;

//: Whether the Python name at `node` is being defined: a def's or a class's
//: name, a parameter, an assignment's target, a for loop's variable, an
//: import.
function docPythonDefines(node) {
  const parent = node.parent;
  if (!parent) return false;
  if (/^(FunctionDefinition|ClassDefinition)$/.test(parent.name)) return parent.getChild("VariableName")?.from === node.from;
  if (parent.name === "ParamList" || parent.name === "ImportStatement" || parent.name === "ForStatement") return true;
  if (parent.name === "AssignStatement") return parent.firstChild?.from === node.from;
  return false;
}

//: The definitions of `name`, as `{ from, to, scope }`; the scope is the
//: range the definition is visible in, for choosing among several.
function docDefinitionsOf(CM, state, name, ext) {
  const refs = docReferencesOf(CM, state, name);
  const tree = CM.language.syntaxTree(state);
  const defs = [];
  if (["js", "ts", "py"].includes(ext)) {
    for (const ref of refs) {
      const node = tree.resolveInner(ref.from, 1);
      const defining = ext === "py" ? node.name === "VariableName" && docPythonDefines(node) : DOC_DEFINING.test(node.name);
      if (!defining) continue;
      let scope = node.parent;
      //: A function's own name belongs to the scope around the function, its
      //: parameters to the function.
      if (scope && /^(FunctionDeclaration|ClassDeclaration|FunctionDefinition|ClassDefinition)$/.test(scope.name)) scope = scope.parent;
      while (scope && !DOC_SCOPES.test(scope.name)) scope = scope.parent;
      defs.push({ ...ref, scope: scope ? [scope.from, scope.to] : [0, state.doc.length] });
    }
    return defs;
  }
  //: A grammar with no tree to ask: a definition is the name after a word
  //: that defines one, or a C-family type in front of it.
  const keyword = /\b(func|fn|def|class|struct|interface|enum|type|trait|impl|var|let|const|val|fun|function|module|record|typedef|sub|proc)\s+[*&]?$/;
  const cType = /\b(int|void|char|float|double|bool|long|short|auto|unsigned|static|String|string|[A-Z][\w<>[\],]*)\s+[*&]?$/;
  for (const ref of refs) {
    const line = state.doc.lineAt(ref.from);
    const before = line.text.slice(0, ref.from - line.from);
    if (keyword.test(before) || cType.test(before)) defs.push({ ...ref, scope: [0, state.doc.length] });
  }
  return defs;
}

//: The definition F12 should go to from `pos`: among those whose scope holds
//: the caret, the innermost, and the nearest before the caret within it;
//: else the first there is.
function docPickDefinition(defs, pos) {
  const visible = defs.filter((d) => d.scope[0] <= pos && pos <= d.scope[1]);
  const pool = visible.length ? visible : defs;
  if (!pool.length) return null;
  const width = (d) => d.scope[1] - d.scope[0];
  const inner = Math.min(...pool.map(width));
  const inScope = pool.filter((d) => width(d) === inner);
  const before = inScope.filter((d) => d.from <= pos);
  return before.length ? before[before.length - 1] : inScope[0];
}

function docGoToDefinition() {
  const CM = window.CM6;
  const view = docCmView;
  if (!CM || !view) return false;
  const pos = view.state.selection.main.head;
  const word = docWordAt(view.state, pos);
  if (!word) return false;
  const def = docPickDefinition(docDefinitionsOf(CM, view.state, word.name, docFileType().ext), pos);
  if (!def) {
    toast(`No definition of ${word.name} in this file.`);
    return true;
  }
  if (def.from <= pos && pos <= def.to) {
    toast(`This is where ${word.name} is defined. Shift+F12 lists its uses.`);
    return true;
  }
  view.dispatch({ selection: { anchor: def.from, head: def.to }, scrollIntoView: true });
  view.focus();
  return true;
}

function docShowReferences() {
  const CM = window.CM6;
  const view = docCmView;
  if (!CM || !view || typeof openMenuAtPoint !== "function") return false;
  const pos = view.state.selection.main.head;
  const word = docWordAt(view.state, pos);
  if (!word) return false;
  const refs = docReferencesOf(CM, view.state, word.name);
  const items = refs.slice(0, 200).map((ref) => {
    const line = view.state.doc.lineAt(ref.from);
    return {
      label: `ph:arrow-right Line ${line.number}: ${line.text.trim().slice(0, 70)}`,
      title: `Go to this use of ${word.name}`,
      run: () => {
        view.dispatch({ selection: { anchor: ref.from, head: ref.to }, scrollIntoView: true });
        view.focus();
      },
    };
  });
  const at = view.coordsAtPos(pos) || view.contentDOM.getBoundingClientRect();
  openMenuAtPoint(items, `${refs.length} ${refs.length === 1 ? "use" : "uses"} of ${word.name}`, at.left, at.bottom);
  return true;
}

//: Ctrl+Shift+F: the app's Find anything, on documents, with the selection
//: (one line of it) or the word at the caret.
function docFindInDocuments() {
  const view = docCmView;
  let query = "";
  if (view) {
    const range = view.state.selection.main;
    if (!range.empty) query = view.state.sliceDoc(range.from, range.to).split("\n")[0].slice(0, 100);
    else query = docWordAt(view.state, range.head)?.name || "";
  }
  openFinder(query, { kind: "document" });
  return true;
}

// --- Run, and its output (INBOX 404) ------------------------------------------
//
// The owner: "what about code errors, debugging console or smth??" A `.js`
// file runs in a worker and an `.html` file renders in a frame, both inside
// `/documents/run-sandbox`, a page served under its own policy (an opaque
// origin with no network; `api/run_sandbox.py` says why each line is there).
// What comes back is `console.*` and uncaught errors as text, each with the
// line it came from, into a panel under the editor. Stop ends the run; so do
// ten seconds of a top level that never finishes, and five hundred lines of
// output. Nothing is compiled, so TypeScript says what it would need rather
// than pretending.
//
// A `.py` file runs too, once the Pyodide extra is installed (the owner,
// 2026-09-24: "Run Python files: yes, as an opt-in extra"): in the same
// sandbox's Python twin, `/documents/run-sandbox/python`, which may read the
// runtime's own files and nothing else. Until it is installed, Run says so
// and offers the button that installs it.

//: The types that run, and the sandbox page each runs in. The languages
//: themselves (what a run sends) are `RUN_LANGS` in run-core.js, the lazy
//: bundle loaded on the first Run; this table is only what the toolbar and
//: the panel need before it is in.
const DOC_RUN_KINDS = { js: "main", ts: "main", sql: "main", html: "main", css: "main", svg: "main", py: "python" };
//: Preview live (D6): how long after the last keystroke a preview refreshes.
const DOC_RUN_LIVE_MS = 400;
//: The types whose tests run (D7): the panel's Run tests button.
const DOC_RUN_TESTS = new Set(["js", "ts", "py"]);
//: The last test run's failures, as diagnostics on their lines in the
//: editor (D7), for the document they came from. One object, not a `let`.
const DOC_RUN_TEST_MARKS = { doc: null, marks: [] };
//: What each document's Input box held (D9), for this tab's life.
const DOC_RUN_STDIN = new Map();
//: A run still going after this long is listed in Activity with Stop
//: (DOCUMENTS_PLAN 25 row 9, decision 70), renewed this often.
const DOC_RUN_JOB_AFTER_MS = 2000;
const DOC_RUN_JOB_BEAT_MS = 1000;
const DOC_RUN_SANDBOX_URL = "/documents/run-sandbox";
const DOC_RUN_SANDBOX_PY_URL = "/documents/run-sandbox/python";
const DOC_RUN_TIMEOUT_MS = 10000;
//: Python's first run loads the runtime (a 10 MB WebAssembly compile) before
//: the script starts; the ten seconds start when the script does, and this
//: bounds the load.
const DOC_RUN_START_MS = 60000;
const DOC_RUN_MAX_ROWS = 500;

//: Why a type shows Run and cannot run, in the panel, in one line. Empty
//: since TypeScript runs (D4); kept for the next type that cannot.
const DOC_RUN_CANNOT = {};

//: Whether a type shows Run: the three that run, and the one that says why not.
function docRunnable(type) {
  return Boolean(DOC_RUN_KINDS[type.ext] || DOC_RUN_CANNOT[type.ext]);
}

//: Is the Pyodide extra installed? Asked on each Python run (one small
//: request), so an install in Settings counts at the next Run without a
//: reload.
async function docRunPythonReady() {
  if (typeof apiJson !== "function") return false;
  const body = await apiJson("/extras", { silent: true }).catch(() => null);
  return Boolean(body?.extras?.find((e) => e.id === "pyodide")?.installed);
}

//: **The Python page lives for the session** (Brief 101c, the owner
//: 2026-10-07: the runtime reloaded on every document opened, 5.9 to 7.0 s
//: cold). The runtime loads in a worker inside the Python sandbox page, and
//: the page used to be the panel's own frame, so each new document's panel
//: made a new page, a new worker and a new load. Now the page is one hidden
//: frame on the document body, made the first time a Python document opens
//: and kept; panels talk to it and leave it alone. Stop still ends the
//: worker, as it always did, so a stopped run's next start loads again.
const DOC_PY_HOST = { frame: null, warm: false };

function docPyHost() {
  let frame = DOC_PY_HOST.frame;
  if (frame && frame.isConnected) return frame;
  frame = document.createElement("iframe");
  frame.hidden = true;
  frame.setAttribute("aria-hidden", "true");
  frame.setAttribute("sandbox", "allow-scripts");
  frame.setAttribute("allow", "cross-origin-isolated");
  frame.title = "The Python runner";
  frame.dataset.runner = DOC_RUN_SANDBOX_PY_URL;
  frame.mmReady = false;
  frame.src = DOC_RUN_SANDBOX_PY_URL;
  document.body.appendChild(frame);
  DOC_PY_HOST.frame = frame;
  return frame;
}

//: Start loading the runtime before Run is pressed: a Python document is
//: open and the extra is installed. The page ignores it when its worker
//: already holds, or is loading, the runtime.
function docPyWarm() {
  const host = docPyHost();
  if (host.mmReady) host.contentWindow?.postMessage({ type: "warm", mmRun: 0 }, "*");
  else DOC_PY_HOST.warm = true;
}

//: Which frame the panel talks to for this runner: Python's is the shared
//: page above, every other language has the panel's own frame, switched to
//: the page it needs (a switch reloads it and the run waits for `ready`).
function docRunSelectFrame(runner) {
  if (!docRun) return;
  if (runner === DOC_RUN_SANDBOX_PY_URL) {
    docRun.frame = docPyHost();
    return;
  }
  const own = docRun.ownFrame;
  docRun.frame = own;
  if (own.dataset.runner !== runner) {
    own.mmReady = false;
    own.dataset.runner = runner;
    own.src = runner;
  }
}

//: Run's state for the open type (25 row 2): a .py document with no Python
//: installed shows Run disabled and the one line that leads to the install.
//: Asked again on every open, so an install counts at the next document.
async function docRunSyncAvailability(type) {
  const run = $("doc-code-run");
  const why = $("doc-code-run-why");
  if (!run || !why) return;
  const python = DOC_RUN_KINDS[type.ext] === "python";
  const ready = python ? await docRunPythonReady() : true;
  //: Another document opened while that was asked: its own call decides.
  if (docFileType().ext !== type.ext) return;
  if (python && ready) docPyWarm();
  run.disabled = !ready;
  run.title = ready ? "Run this file in a sandbox and show its output (Ctrl+Shift+Enter)" : "Running Python needs the Python package: install it in Settings, Packages";
  why.classList.toggle("hidden", ready || !docRunnable(type));
}

//: Settings, Packages, with the Python row in view and its button focused.
async function docRunOpenPythonExtra() {
  if (typeof openSettingsModal !== "function") return;
  await openSettingsModal("extras");
  for (let i = 0; i < 30; i += 1) {
    const row = document.getElementById("extra-row-pyodide");
    if (row) {
      row.scrollIntoView({ block: "center" });
      row.querySelector("button")?.focus();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

// --- Debug (DOCUMENTS_PLAN 23, I2: D2 Python, D3 JavaScript) ---------------
//
//: The session, one object rather than lets: whether a debug run is in
//: flight, the stop on show, the watch list, each document's breakpoints
//: (line and condition, for the tab's life), and the editor parts built once.
const DOC_DEBUG = { on: false, stop: null, said: "", watches: [], breaks: new Map(), parts: null };

function docDebugOn() {
  return Boolean(DOC_DEBUG.on && docRun && docRun.debug);
}

//: The types Debug steps: Python through `bdb` in the Pyodide worker (D2),
//: JavaScript and TypeScript through JS-Interpreter (D3).
const DOC_DEBUG_KINDS = new Set(["js", "ts", "py"]);
//: Why Debug does not start where Run can, in one line (DOC_RUN_CANNOT's shape).
const DOC_DEBUG_CANNOT = {
  kind: "Debug steps JavaScript, TypeScript and Python files; this one runs with Run.",
  isolation: "Debug needs SharedArrayBuffer, and this window is not cross-origin isolated (a webview without the two headers): Run still works.",
};
//: How a stop's reason reads in the Debug tab's head.
const DOC_DEBUG_REASONS = { breakpoint: "on a breakpoint", step: "after a step", exception: "on an exception" };

//: A stop from the sandbox (D2, D3): the stopped line, its variables, the
//: stack and the watches. The line is lit and brought into view; the caret
//: stays where it was, as VS Code leaves it.
function docDebugStopped(data) {
  if (!docRun || !docRun.debug) return;
  DOC_DEBUG.stop = data;
  const line = Number(data.line) || 0;
  docDebugHere(line, true);
  //: One word in the head: the line and why are the Debug tab's first row.
  docRunSetStatus("Paused", true);
  docRunShowTab("debug");
  docDebugRender();
}

//: A run is about to start: a debug one turns the session on, any other
//: turns it off.
function docDebugBegin(prepared) {
  if (!docRun) return;
  docRun.debug = Boolean(prepared.debug);
  DOC_DEBUG.on = docRun.debug;
  DOC_DEBUG.stop = null;
  DOC_DEBUG.said = "";
  docDebugHere(0);
  if (!docRun.debug) {
    docRunShowTab("output");
    return;
  }
  if (prepared.message?.dom) docRunRow("info", "This script uses the page: Debug runs it against a stand-in document, so nothing is drawn.", null);
  docRunShowTab("debug");
  docDebugRender();
}

//: The session is over: finished, stopped or ended by an error. `quiet`
//: leaves the status to the caller (Stop says its own words).
function docDebugEnded(ended, quiet = false) {
  DOC_DEBUG.on = false;
  DOC_DEBUG.stop = null;
  docDebugHere(0);
  if (!docRun) return;
  docRun.debug = false;
  if (!quiet) docRunSetStatus(ended === "stopped" ? "Stopped." : ended === "error" ? "Stopped by an error." : "Finished.", false);
  docDebugRender();
}

//: The five actions, and `eval` (new watches or breakpoints, answered with
//: a fresh stop). Continue with no session starts one, as F5 does in VS Code.
function docDebugAct(cmd) {
  if (!docRun || !docRun.debug) {
    if (cmd === "continue" && docCmView && DOC_RUN_KINDS[docFileType().ext]) {
      docRunCode({ mode: "debug" });
      return true;
    }
    return false;
  }
  const paused = DOC_DEBUG.stop;
  if (cmd === "stop") {
    if (paused) docRunSend({ type: "reply", mmRun: docRun.id, value: { cmd: "stop" } });
    else docRunStop("Stopped.");
    return true;
  }
  if (!paused) return true;
  docRunSend({ type: "reply", mmRun: docRun.id, value: { cmd, breaks: docDebugBreaks(), watches: DOC_DEBUG.watches.slice() } });
  if (cmd === "eval") return true;
  DOC_DEBUG.stop = null;
  docDebugHere(0);
  docRunSetStatus("Debugging", true);
  docRunArmTimeout(docRun.id);
  docDebugRender();
  return true;
}

//: F5, F10, F11, Shift+F11 and Shift+F5 with the focus in the panel (the
//: editor's own keymap has them for the text): a stepping key never reloads
//: the page or toggles full screen while a session is on.
function docDebugKey(event) {
  const keys = { F5: event.shiftKey ? "stop" : "continue", F10: "over", F11: event.shiftKey ? "out" : "in" };
  const cmd = keys[event.key];
  if (!cmd || event.ctrlKey || event.metaKey || event.altKey) return;
  if (!docRun?.debug && cmd !== "continue") return;
  event.preventDefault();
  docDebugAct(cmd);
}

//: The open document's breakpoints, `{line, cond}`, from the gutter's field.
function docDebugBreaks() {
  const field = DOC_DEBUG.parts?.field;
  if (!docCmView || !field) return [];
  const state = docCmView.state;
  let marks;
  try {
    marks = state.field(field);
  } catch {
    return [];
  }
  const rows = [];
  marks.between(0, state.doc.length, (from, _to, mark) => {
    rows.push({ line: state.doc.lineAt(from).number, cond: mark.cond || "" });
  });
  return rows;
}

//: A document's breakpoints outlive a reload (OPEN row 1059), as VS Code
//: keeps them in the workspace: kept on this device per document, the
//: DOC_DEBUG_BREAKS_DOCS most recently set, read once into DOC_DEBUG.breaks.
const DOC_DEBUG_BREAKS_KEY = "doc-debug-breakpoints";
const DOC_DEBUG_BREAKS_DOCS = 100;

function docDebugSavedBreaks(id) {
  if (DOC_DEBUG.breaks.has(id)) return DOC_DEBUG.breaks.get(id);
  let rows = [];
  try {
    const saved = prefs.json(DOC_DEBUG_BREAKS_KEY, {})[id];
    if (Array.isArray(saved)) rows = saved.filter((r) => Number.isInteger(r?.line)).map((r) => ({ line: r.line, cond: String(r.cond || "") }));
  } catch { /* storage refused or unreadable: this tab's breakpoints only */ }
  DOC_DEBUG.breaks.set(id, rows);
  return rows;
}

function docDebugKeepBreaks(id, rows) {
  //: Typing calls this on every key; storage is written only on a change.
  const same = JSON.stringify(DOC_DEBUG.breaks.get(id) || []) === JSON.stringify(rows);
  DOC_DEBUG.breaks.set(id, rows);
  if (same) return;
  try {
    const saved = prefs.json(DOC_DEBUG_BREAKS_KEY, {});
    delete saved[id];
    if (rows.length) saved[id] = rows.map((r) => ({ line: r.line, cond: r.cond || "" }));
    const ids = Object.keys(saved);
    for (const old of ids.slice(0, Math.max(0, ids.length - DOC_DEBUG_BREAKS_DOCS))) delete saved[old];
    prefs.set(DOC_DEBUG_BREAKS_KEY, JSON.stringify(saved));
  } catch { /* storage refused: kept for this tab only */ }
}

//: The gutter, the lit line and the keys, built once (the field keeps its
//: identity across documents; each document's breakpoints come back from
//: DOC_DEBUG.breaks when its state is made).
function docDebugExtension(CM) {
  if (DOC_DEBUG.parts) return DOC_DEBUG.parts.ext;
  class DebugMark extends CM.view.GutterMarker {
    constructor(cond) {
      super();
      this.cond = cond || "";
    }
    eq(other) {
      return other.cond === this.cond;
    }
    toDOM() {
      const dot = document.createElement("span");
      dot.className = `cm-debug-bp${this.cond ? " is-cond" : ""}`;
      dot.title = this.cond ? `Breakpoint when ${this.cond}` : "Breakpoint";
      return dot;
    }
  }
  const toggle = CM.state.StateEffect.define({ map: (value, mapping) => ({ ...value, pos: mapping.mapPos(value.pos) }) });
  const field = CM.state.StateField.define({
    create: (state) => {
      const rows = docHistoryOwner == null ? [] : docDebugSavedBreaks(docHistoryOwner);
      const ranges = rows.filter((r) => r.line >= 1 && r.line <= state.doc.lines).map((r) => new DebugMark(r.cond).range(state.doc.line(r.line).from));
      return CM.state.RangeSet.of(ranges, true);
    },
    update: (marks, tr) => {
      let next = marks.map(tr.changes);
      for (const e of tr.effects) {
        if (!e.is(toggle)) continue;
        next = next.update({ filter: (from) => from !== e.value.pos });
        if (e.value.on) next = next.update({ add: [new DebugMark(e.value.cond).range(e.value.pos)] });
      }
      return next;
    },
  });
  const here = CM.state.StateEffect.define();
  const hereField = CM.state.StateField.define({
    create: () => CM.view.Decoration.none,
    update: (deco, tr) => {
      let next = deco.map(tr.changes);
      for (const e of tr.effects) {
        if (!e.is(here)) continue;
        const n = e.value;
        next = n >= 1 && n <= tr.state.doc.lines
          ? CM.view.Decoration.set([CM.view.Decoration.line({ class: "cm-debug-here" }).range(tr.state.doc.line(n).from)])
          : CM.view.Decoration.none;
      }
      return next;
    },
    provide: (f) => CM.view.EditorView.decorations.from(f),
  });
  const gutter = CM.view.gutter({
    class: "cm-debug-gutter",
    renderEmptyElements: true,
    markers: (view) => view.state.field(field),
    initialSpacer: () => new DebugMark(""),
    domEventHandlers: {
      mousedown: (view, line, event) => {
        if (event.button !== 0) return false;
        docDebugToggleAt(view, line.from);
        return true;
      },
      contextmenu: (view, line, event) => {
        event.preventDefault();
        docDebugBreakMenu(view, line.from, event.clientX, event.clientY);
        return true;
      },
    },
  });
  const keys = CM.view.keymap.of([
    { key: "F5", run: () => { docDebugAct("continue"); return true; } },
    { key: "Shift-F5", run: () => { docDebugAct("stop"); return true; } },
    { key: "F9", run: (view) => docDebugToggleAt(view, view.state.selection.main.head) },
    //: The stepping keys only while a session is on: F11 is otherwise
    //: Focus mode's (documents.js), F10 and Shift+F11 the browser's.
    { key: "F10", run: () => docDebugOn() && docDebugAct("over") },
    { key: "F11", run: () => docDebugOn() && docDebugAct("in") },
    { key: "Shift-F11", run: () => docDebugOn() && docDebugAct("out") },
  ]);
  //: Every change to a document's breakpoints is kept for it, and sent to a
  //: session stopped on it, which answers with a fresh stop.
  const keep = CM.view.EditorView.updateListener.of((update) => {
    const changed = update.transactions.some((tr) => tr.effects.some((e) => e.is(toggle)));
    if (!changed && !update.docChanged) return;
    if (docHistoryOwner != null) docDebugKeepBreaks(docHistoryOwner, docDebugBreaks());
    if (changed) {
      docDebugRender();
      if (DOC_DEBUG.stop) docDebugAct("eval");
    }
  });
  DOC_DEBUG.parts = { DebugMark, toggle, field, here, ext: [field, hereField, CM.state.Prec.highest(gutter), CM.state.Prec.high(keys), keep] };
  return DOC_DEBUG.parts.ext;
}

//: A breakpoint on the line at `pos`, on or off; `cond` sets its condition
//: (an empty one is a plain breakpoint).
function docDebugToggleAt(view, pos, cond) {
  const parts = DOC_DEBUG.parts;
  if (!parts || !view) return false;
  const from = view.state.doc.lineAt(pos).from;
  let had = null;
  view.state.field(parts.field).between(from, from, (at, _to, mark) => {
    if (at === from) had = mark;
  });
  const on = cond !== undefined ? true : !had;
  view.dispatch({ effects: parts.toggle.of({ pos: from, on, cond: cond ?? "" }) });
  return true;
}

//: F9 and the palette's row: the caret's line.
function docDebugToggleHere() {
  if (!docCmView || !DOC_DEBUG_KINDS.has(docFileType().ext)) return false;
  return docDebugToggleAt(docCmView, docCmView.state.selection.main.head);
}

//: The gutter's right-click: add, remove, or give a breakpoint a condition
//: (VS Code's "Edit Breakpoint"), through the app's own small prompt.
function docDebugBreakMenu(view, pos, x, y) {
  const parts = DOC_DEBUG.parts;
  if (!parts) return;
  const line = view.state.doc.lineAt(pos);
  let had = null;
  view.state.field(parts.field).between(line.from, line.from, (at, _to, mark) => {
    if (at === line.from) had = mark;
  });
  const ask = async () => {
    const cond = await promptDialog(`Stop on line ${line.number} only when this is true (empty for always)`, had?.cond || "", { confirmLabel: "Set" });
    if (cond === null || cond === undefined) return;
    docDebugToggleAt(view, line.from, String(cond).trim());
  };
  const items = had
    ? [
      { label: "ph:pencil-simple Edit condition", run: ask },
      { label: "ph:x Remove breakpoint", run: () => docDebugToggleAt(view, line.from) },
    ]
    : [
      { label: "ph:circle Add breakpoint", run: () => docDebugToggleAt(view, line.from) },
      { label: "ph:funnel Add conditional breakpoint", run: ask },
    ];
  openMenuAtPoint(items, `Breakpoint on line ${line.number}`, x, y);
}

//: Light the stopped line (0 clears it), and bring it into view.
function docDebugHere(line, reveal = false) {
  const parts = DOC_DEBUG.parts;
  if (!parts || !docCmView) return;
  const effects = [parts.here.of(line)];
  if (reveal && line >= 1 && line <= docCmView.state.doc.lines) {
    effects.push(window.CM6.view.EditorView.scrollIntoView(docCmView.state.doc.line(line).from, { y: "center" }));
  }
  docCmView.dispatch({ effects });
}

//: The Debug tab's DOM: the five actions, where it stopped, then Variables,
//: Watch, Call stack and Breakpoints. Rebuilt with the panel; filled by
//: `docDebugRender`.
function docDebugView() {
  const view = document.createElement("div");
  view.className = "cm-debug";
  view.id = "doc-run-debug";
  view.setAttribute("role", "tabpanel");
  view.setAttribute("aria-labelledby", "doc-run-tab-debug");
  const bar = document.createElement("div");
  bar.className = "cm-debug-bar";
  bar.setAttribute("role", "toolbar");
  bar.setAttribute("aria-label", "Debug actions");
  const act = (cmd, label, icon, key) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "icon-only ghost small cm-debug-act";
    b.dataset.cmd = cmd;
    b.title = `${label} (${key})`;
    b.setAttribute("aria-label", label);
    const i = document.createElement("i");
    i.className = `ph ${icon}`;
    i.setAttribute("aria-hidden", "true");
    b.appendChild(i);
    b.addEventListener("click", () => docDebugAct(cmd));
    return b;
  };
  bar.append(
    act("continue", "Continue", "ph-play", "F5"),
    act("over", "Step over", "ph-arrow-bend-down-right", "F10"),
    act("in", "Step in", "ph-arrow-elbow-down-right", "F11"),
    act("out", "Step out", "ph-arrow-elbow-left-up", "Shift+F11"),
    act("stop", "Stop", "ph-stop", "Shift+F5"),
  );
  const where = document.createElement("span");
  where.className = "cm-debug-where";
  bar.appendChild(where);
  const thrown = document.createElement("pre");
  thrown.className = "cm-debug-thrown hidden";
  const grid = document.createElement("div");
  grid.className = "cm-debug-grid";
  const section = (key, title) => {
    const box = document.createElement("section");
    box.className = `cm-debug-section cm-debug-${key}`;
    const h = document.createElement("h3");
    h.className = "cm-debug-title";
    h.textContent = title;
    const list = document.createElement("ul");
    list.className = "cm-debug-list";
    list.setAttribute("aria-label", title);
    box.append(h, list);
    grid.appendChild(box);
    return list;
  };
  const vars = section("vars", "Variables");
  const watch = section("watch", "Watch");
  const add = document.createElement("input");
  add.type = "text";
  add.className = "cm-debug-watch-add";
  add.placeholder = "Add an expression to watch";
  add.setAttribute("aria-label", "Add an expression to watch");
  add.spellcheck = false;
  add.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || !add.value.trim()) return;
    event.preventDefault();
    DOC_DEBUG.watches.push(add.value.trim());
    add.value = "";
    if (DOC_DEBUG.stop) docDebugAct("eval");
    docDebugRender();
  });
  watch.parentElement.appendChild(add);
  const stack = section("stack", "Call stack");
  const breaks = section("breaks", "Breakpoints");
  view.append(bar, thrown, grid);
  view.mmParts = { bar, where, thrown, vars, watch, stack, breaks };
  return view;
}

//: A name and its value, as one row: text only, never markup.
//: A list, a dict or an object opens one level into its children, as VS
//: Code's Variables tree does (OPEN row 1058); the row is a disclosure then.
function docDebugValueRow(name, value, type, error = false, children = null) {
  const li = document.createElement("li");
  li.className = `cm-debug-row${error ? " is-error" : ""}`;
  const n = document.createElement("span");
  n.className = "cm-debug-name";
  n.textContent = name;
  const v = document.createElement("span");
  v.className = "cm-debug-value";
  v.textContent = value;
  if (type) v.title = type;
  if (!Array.isArray(children) || !children.length) {
    li.append(n, v);
    return li;
  }
  li.classList.add("has-children");
  const tree = document.createElement("details");
  tree.className = "cm-debug-tree";
  const summary = document.createElement("summary");
  summary.append(n, v);
  const list = document.createElement("ul");
  list.className = "cm-debug-list cm-debug-children";
  for (const child of children) list.appendChild(docDebugValueRow(String(child.name), String(child.value), String(child.type || "")));
  tree.append(summary, list);
  li.appendChild(tree);
  return li;
}

function docDebugEmpty(list, text) {
  const li = document.createElement("li");
  li.className = "cm-debug-empty";
  li.textContent = text;
  list.appendChild(li);
}

//: A row that goes to a line: the call stack's frames and the breakpoints.
function docDebugLineButton(text, line) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "ghost small cm-debug-go";
  b.textContent = text;
  b.title = `Go to line ${line}`;
  b.addEventListener("click", () => {
    jumpToDocLine(line - 1);
    docCmView?.focus();
  });
  return b;
}

function docDebugRemoveButton(label, run) {
  const x = document.createElement("button");
  x.type = "button";
  x.className = "icon-only ghost small cm-debug-remove";
  x.title = label;
  x.setAttribute("aria-label", label);
  const i = document.createElement("i");
  i.className = "ph ph-x";
  i.setAttribute("aria-hidden", "true");
  x.appendChild(i);
  x.addEventListener("click", run);
  return x;
}

//: Fill the Debug tab from the session: the stop on show, the watch list,
//: the open document's breakpoints.
function docDebugRender() {
  const parts = docRun?.debugView?.mmParts;
  if (!parts) return;
  const stop = DOC_DEBUG.stop;
  const on = Boolean(docRun.debug);
  for (const b of parts.bar.querySelectorAll(".cm-debug-act")) {
    const cmd = b.dataset.cmd;
    b.disabled = cmd === "continue" ? on && !stop : cmd === "stop" ? !on : !stop;
    //: The first action starts a session when there is none (F5 either way).
    if (cmd === "continue") {
      const label = on ? "Continue" : "Start debugging";
      b.setAttribute("aria-label", label);
      b.title = `${label} (F5)`;
    }
  }
  const line = Number(stop?.line) || 0;
  parts.where.textContent = stop
    ? `Paused at line ${line}, ${DOC_DEBUG_REASONS[stop.reason] || "stopped"}.`
    : on ? "Running to the next breakpoint." : DOC_DEBUG.said || "Debug (F5) runs to the first breakpoint, then steps.";
  const thrownText = stop?.reason === "exception" ? String(stop.text || "") : "";
  parts.thrown.textContent = thrownText;
  parts.thrown.classList.toggle("hidden", !thrownText);

  parts.vars.replaceChildren();
  if (!stop) docDebugEmpty(parts.vars, "Shown while the run is paused.");
  else {
    const locals = Array.isArray(stop.locals) ? stop.locals : [];
    const globals = Array.isArray(stop.globals) ? stop.globals : [];
    for (const row of locals) parts.vars.appendChild(docDebugValueRow(String(row.name), String(row.value), String(row.type || ""), false, row.children));
    if (!locals.length) docDebugEmpty(parts.vars, "No local names yet.");
    if (globals.length) {
      const head = document.createElement("li");
      head.className = "cm-debug-sub";
      head.textContent = "Globals";
      parts.vars.appendChild(head);
      for (const row of globals) parts.vars.appendChild(docDebugValueRow(String(row.name), String(row.value), String(row.type || ""), false, row.children));
    }
  }

  parts.watch.replaceChildren();
  const values = new Map((Array.isArray(stop?.watches) ? stop.watches : []).map((w) => [String(w.expr), w]));
  DOC_DEBUG.watches.forEach((expr, index) => {
    const w = values.get(expr);
    const row = docDebugValueRow(expr, w ? (w.error ? String(w.error) : String(w.value)) : "not evaluated", "", Boolean(w?.error));
    row.appendChild(docDebugRemoveButton(`Stop watching ${expr}`, () => {
      DOC_DEBUG.watches.splice(index, 1);
      if (DOC_DEBUG.stop) docDebugAct("eval");
      docDebugRender();
    }));
    parts.watch.appendChild(row);
  });
  if (!DOC_DEBUG.watches.length) docDebugEmpty(parts.watch, "An expression typed below is evaluated at every stop.");

  parts.stack.replaceChildren();
  const frames = Array.isArray(stop?.stack) ? stop.stack : [];
  for (const frame of frames) {
    const li = document.createElement("li");
    li.className = "cm-debug-row";
    const n = Number(frame.line) || 0;
    li.appendChild(n ? docDebugLineButton(`${frame.name}, line ${n}`, n) : document.createTextNode(String(frame.name)));
    parts.stack.appendChild(li);
  }
  if (!frames.length) docDebugEmpty(parts.stack, "Shown while the run is paused.");

  parts.breaks.replaceChildren();
  const breaks = docDebugBreaks();
  for (const b of breaks) {
    const li = document.createElement("li");
    li.className = "cm-debug-row";
    li.appendChild(docDebugLineButton(b.cond ? `Line ${b.line}, when ${b.cond}` : `Line ${b.line}`, b.line));
    li.appendChild(docDebugRemoveButton(`Remove the breakpoint on line ${b.line}`, () => {
      if (docCmView && b.line <= docCmView.state.doc.lines) docDebugToggleAt(docCmView, docCmView.state.doc.line(b.line).from);
    }));
    parts.breaks.appendChild(li);
  }
  if (!breaks.length) docDebugEmpty(parts.breaks, "Click beside a line number, or press F9, to add one.");
}

//: The run in flight and the panel it writes to, or null.
let docRun = null;
let docRunSeq = 0;
let docRunPanelField = null;
let docRunToggle = null;

const DOC_RUN_EMPTY = {
  Output: "Nothing has run yet. Run the file to see what it prints here.",
  Problems: "No problems found in this file.",
  Tests: "Run tests to list each one here.",
  Console: "Type a line below to run it in what the last run left.",
};

//: The run panel's '?' (the `data-help-for` recipe): what a run is, in
//: three lines, the Guide's "Running code" topic at length.
const DOC_RUN_HELP = [
  "Run sends this file to a sandbox with no network and none of your notes. What it prints and its errors come back in Output; Line N goes to the line.",
  "JavaScript, TypeScript (types removed, not checked), SQL (a SQLite per run, with any CSV document the query names as a table) and Python (once installed; Input feeds input()) run. HTML, CSS, SVG and p5.js sketches show as a page; Live refreshes it as you type.",
  "Problems lists every finding the checks underline. Tests lists each test with its time, a failure underlined on its line. Console evaluates a line in what the last run left: Python for a .py file, JavaScript for the rest.",
  "Debug (F5, or the Debug tab's first button) runs JavaScript, TypeScript or Python to the first breakpoint (F9, or click beside a line number; right-click for a condition), then steps: F10 over, F11 in, Shift+F11 out, Shift+F5 stop. The tab shows variables, watches, the call stack and the breakpoints.",
  "The head's buttons are icons; point at one for its name. Ctrl+J shows or hides the panel, Ctrl+Shift+M opens Problems, Ctrl+Shift+Y the Console, Ctrl+Shift+D Debug; drag the top edge for its height, kept for each tab. A run still going after two seconds is in Activity, where Stop ends it too.",
];

//: The panel's tabs (D8), one row each: its words, the chord that shows it
//: (VS Code's) or "none". A tab is added here and nowhere else: the head,
//: the keys (`docPanelChord`), the grip's heights and the sheet read it.
const DOC_PANEL_TABS = [
  { id: "output", label: "Output", keys: "none" },
  { id: "problems", label: "Problems", keys: "Ctrl+Shift+M" },
  { id: "tests", label: "Tests", keys: "none" },
  { id: "console", label: "Console", keys: "Ctrl+Shift+Y" },
  { id: "debug", label: "Debug", keys: "Ctrl+Shift+D" },
];

//: The tab last shown (one choice for every document this session), the
//: console's history per language, where Up has walked to in it, and the
//: number of the last line sent to be evaluated. One object, not a `let`.
const DOC_PANEL = { tab: "output", history: { python: [], js: [] }, at: -1, evalSeq: 0 };

//: The panel's DOM, built when it opens; the sandbox frame lives in it, so
//: closing the panel removes the frame and whatever was running with it.
//: Its head is a dock (DESIGN.md's recipe): the tabs as its identity
//: (`.tabs-line`), the run's status beside them, then the worded ghosts and
//: the icon run, help and Close, last.
function docRunPanel(view) {
  const dom = document.createElement("div");
  dom.className = "cm-run-panel";
  const head = document.createElement("div");
  head.className = "cm-run-head dock";
  const identity = document.createElement("div");
  identity.className = "dock-identity cm-run-identity";
  const tabList = document.createElement("div");
  tabList.className = "tabs-line cm-panel-tabs";
  tabList.setAttribute("role", "tablist");
  tabList.setAttribute("aria-label", "Panels");
  const status = document.createElement("span");
  status.className = "cm-run-status";
  status.setAttribute("role", "status");
  identity.append(tabList, status);
  const actions = document.createElement("div");
  actions.className = "dock-actions cm-run-actions";
  //: **Icons, with their words as the tooltip and the accessible name**
  //: (the owner, 2026-10-10: the head ran onto a second row). Eight actions
  //: with words need 480px the head does not have beside five tabs; as the
  //: app's one icon button they are 28px each at every width.
  const button = (label, icon, action, hint) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small icon-only";
    b.title = hint;
    const i = document.createElement("i");
    i.className = `ph ${icon}`;
    i.setAttribute("aria-hidden", "true");
    b.setAttribute("aria-label", label);
    b.append(i);
    b.addEventListener("click", action);
    return b;
  };
  const again = button("Run again", "ph-play", () => docRunCode(), "Run the file again (Ctrl+Shift+Enter)");
  const tests = button("Run tests", "ph-flask", () => docRunCode({ mode: "test" }), "Run the tests in this file and list each one");
  tests.classList.add("cm-run-tests-btn");
  tests.classList.toggle("hidden", !DOC_RUN_TESTS.has(docFileType().ext));
  //: Preview live (D6): shown once a run is a preview; pressed, the preview
  //: refreshes 400 ms after the typing stops, and on every save.
  const live = button("Live", "ph-lightning", () => docRunSetLive(!docRunLiveOn()), "Preview live: refresh as you type");
  live.classList.add("cm-run-live", "hidden");
  live.setAttribute("aria-pressed", String(docRunLiveOn()));
  const stopButton = button("Stop", "ph-stop", () => docRunStop("Stopped."), "Stop the run");
  const clear = button("Clear", "ph-eraser", () => docRunClearTab(), "Clear this tab");
  //: Input (D9): Python's `input()` reads its lines from this box, one
  //: per call. Shown with its button for Python, and opened by itself when
  //: the file calls `input(`.
  const isPy = docFileType().ext === "py";
  const stdinButton = button("Input", "ph-keyboard", () => docRunShowStdin(stdinWrap.classList.contains("hidden")), "Show the lines input() reads");
  stdinButton.classList.add("cm-run-stdin-btn");
  stdinButton.classList.toggle("hidden", !isPy);
  stdinButton.setAttribute("aria-expanded", "false");
  const stdinWrap = document.createElement("label");
  stdinWrap.className = "cm-run-stdin-wrap hidden";
  const stdinLabel = document.createElement("span");
  stdinLabel.className = "cm-run-stdin-label";
  stdinLabel.textContent = "Input, one line for each input() call";
  const stdin = document.createElement("textarea");
  stdin.className = "cm-run-stdin";
  stdin.rows = 2;
  stdin.spellcheck = false;
  stdin.value = (currentDoc && DOC_RUN_STDIN.get(currentDoc.id)) || "";
  stdin.addEventListener("input", () => {
    if (currentDoc) DOC_RUN_STDIN.set(currentDoc.id, stdin.value);
  });
  stdinWrap.append(stdinLabel, stdin);
  const iconButton = (label, icon, hint) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "icon-only ghost small";
    b.title = hint;
    b.setAttribute("aria-label", label);
    const i = document.createElement("i");
    i.className = `ph ${icon}`;
    i.setAttribute("aria-hidden", "true");
    b.appendChild(i);
    return b;
  };
  const help = iconButton("About the panel", "ph-question", "About the panel");
  help.classList.add("cm-run-help");
  help.setAttribute("data-help-for", "doc-run-help");
  help.setAttribute("aria-controls", "doc-run-help");
  help.setAttribute("aria-expanded", "false");
  const close = iconButton("Close", "ph-x", "Close the panel (Ctrl+J)");
  close.classList.add("cm-run-close");
  close.addEventListener("click", () => docRunClose());
  const helpBody = document.createElement("div");
  helpBody.className = "help-body hidden";
  helpBody.id = "doc-run-help";
  helpBody.setAttribute("role", "dialog");
  helpBody.setAttribute("aria-label", "About the panel");
  for (const line of DOC_RUN_HELP) {
    const p = document.createElement("p");
    p.textContent = line;
    helpBody.appendChild(p);
  }
  actions.append(live, stdinButton, tests, again, stopButton, clear, help, close);
  head.append(identity, actions);
  //: Output: the page a file makes over the log of what it printed.
  const body = document.createElement("div");
  body.className = "cm-run-body cm-run-pane";
  const frame = document.createElement("iframe");
  frame.className = "cm-run-frame";
  frame.setAttribute("sandbox", "allow-scripts");
  //: The sandbox is another origin, so isolation (SharedArrayBuffer, D2) is
  //: delegated to it by name; the app's own page is isolated by its headers.
  frame.setAttribute("allow", "cross-origin-isolated");
  frame.title = "The page this file makes";
  //: The runner this file needs from the start, so a first run is not a
  //: switch (see the `ready` check in the message listener).
  //: A Python document's panel has no page of its own to load: it talks to
  //: the shared one (`docPyHost`), and this frame stays blank until a
  //: language that needs it runs.
  const pythonFile = DOC_RUN_KINDS[docFileType().ext] === "python";
  frame.mmReady = false;
  if (!pythonFile) {
    frame.src = DOC_RUN_SANDBOX_URL;
    frame.dataset.runner = DOC_RUN_SANDBOX_URL;
  }
  const logList = (name) => {
    const list = document.createElement("ol");
    list.className = "cm-run-log";
    list.setAttribute("role", "log");
    list.setAttribute("aria-label", name);
    //: What an empty log says (CSS draws it from this, `:empty::before`), so
    //: a pane with nothing in it is a sentence, not a blank slab.
    list.dataset.empty = DOC_RUN_EMPTY[name] || "";
    return list;
  };
  const log = logList("Output");
  body.append(frame, log);
  const pane = (id, ...children) => {
    const own = id === "output" ? body : id === "debug" ? children[0] : null;
    const p = own || document.createElement("div");
    if (!own) {
      p.className = "cm-run-pane";
      p.append(...children);
    }
    p.dataset.pane = id;
    p.id = `doc-panel-${id}`;
    p.setAttribute("role", "tabpanel");
    p.setAttribute("aria-labelledby", `doc-panel-tab-${id}`);
    return p;
  };
  const problemsLog = logList("Problems");
  const testsLog = logList("Tests");
  //: The console (D8): its log over one line to type in, `>>>` for Python
  //: and `>` for JavaScript, as their own consoles write them.
  const python = DOC_RUN_KINDS[docFileType().ext] === "python";
  const consoleLog = logList("Console");
  const consoleForm = document.createElement("form");
  consoleForm.className = "cm-console-line";
  const prompt = document.createElement("span");
  prompt.className = "cm-console-prompt";
  prompt.setAttribute("aria-hidden", "true");
  prompt.textContent = python ? ">>>" : ">";
  const consoleInput = document.createElement("input");
  consoleInput.type = "text";
  consoleInput.className = "cm-console-input";
  consoleInput.spellcheck = false;
  consoleInput.autocomplete = "off";
  consoleInput.placeholder = python ? "A line of Python, in what the last run left" : "A line of JavaScript, in what the last run left";
  consoleInput.setAttribute("aria-label", python ? "Python console: a line to evaluate" : "JavaScript console: a line to evaluate");
  consoleInput.addEventListener("keydown", (event) => docConsoleKey(event));
  consoleForm.append(prompt, consoleInput);
  consoleForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = consoleInput.value;
    consoleInput.value = "";
    docConsoleEval(text);
  });
  //: Debug (Brief 70, D2 and D3): its five actions and four views, as
  //: `docDebugView` builds them, are the pane itself.
  const debugView = docDebugView();
  const panes = new Map([
    ["output", pane("output")],
    ["problems", pane("problems", problemsLog)],
    ["tests", pane("tests", testsLog)],
    ["console", pane("console", consoleLog, consoleForm)],
    ["debug", pane("debug", debugView)],
  ]);
  const tabs = new Map();
  for (const tab of DOC_PANEL_TABS) {
    if (!panes.has(tab.id)) continue;
    const b = document.createElement("button");
    b.type = "button";
    b.id = `doc-panel-tab-${tab.id}`;
    b.className = "cm-panel-tab";
    b.dataset.tab = tab.id;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-controls", `doc-panel-${tab.id}`);
    b.title = tab.keys === "none" ? tab.label : `${tab.label} (${tab.keys})`;
    const word = document.createElement("span");
    word.textContent = tab.label;
    //: A count beside the word (Problems, Tests) is quiet text, the dock's
    //: `.dock-chip`, never a pill.
    const count = document.createElement("span");
    count.className = "dock-chip cm-panel-count";
    b.append(word, count);
    b.addEventListener("click", () => docRunShowTab(tab.id));
    tabList.appendChild(b);
    tabs.set(tab.id, b);
  }
  //: The tablist's keys (WAI-ARIA): the arrows move between tabs, and a
  //: tab shows as the focus reaches it.
  tabList.addEventListener("keydown", (event) => {
    const ids = [...tabs.keys()];
    const at = ids.indexOf(event.target.dataset?.tab);
    if (at < 0) return;
    const next = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: ids.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    docRunShowTab(ids[(next + ids.length) % ids.length], true);
  });
  dom.append(head, helpBody, stdinWrap, ...panes.values());
  //: The debugger's keys (F9, F10, F11 while a session is on, Shift+F5).
  dom.addEventListener("keydown", (event) => docDebugKey(event));
  wireHelpPopover(help, helpBody);
  //: The panel's own chords while the focus is in it (the console, a tab):
  //: the editor's keymap does not see a key typed here.
  dom.addEventListener("keydown", (event) => {
    if (event.target.closest?.(".cm-panel-tabs") && !event.ctrlKey && !event.metaKey) return;
    if (!docPanelChord(event)) return;
    event.preventDefault();
    event.stopPropagation();
  });
  docRun = { view, dom, frame: pythonFile ? docPyHost() : frame, ownFrame: frame, log, status, stopButton, live, stdin, stdinWrap, stdinButton, tabs, panes, problemsLog, testsLog, consoleLog, consoleInput, debugView, debug: false, tab: "output", evalId: 0, pending: null, id: 0, rows: 0, timer: null, running: false, preview: false, liveTimer: null, options: {}, job: null, jobWait: null, jobBeat: null };
  //: A new document's panel on the shared page: what the last document's
  //: run left in the console's namespace is not this document's.
  if (pythonFile && docRun.frame.mmReady) docRun.frame.contentWindow?.postMessage({ type: "forget", mmRun: 0 }, "*");
  if (typeof docIdeRunGrip === "function") docIdeRunGrip(dom, view);
  docRunShowTab(DOC_PANEL.tab);
  return {
    dom,
    top: false,
    destroy: () => {
      if (docRun && docRun.dom === dom) {
        clearTimeout(docRun.timer);
        clearTimeout(docRun.liveTimer);
        docRunJobEnd(docRun);
        //: The shared page outlives the panel, so a script still going would
        //: run on: closing the panel ends it, as removing the frame did.
        if (docRun.running && docRun.frame === DOC_PY_HOST.frame) {
          docRun.frame.contentWindow?.postMessage({ type: "stop", mmRun: docRun.id }, "*");
        }
        if (docRun.debug) {
          //: The session ends with the panel, but its lit line is cleared
          //: after: a panel is destroyed inside the editor's own update,
          //: where a dispatch throws (measured: "Calls to EditorView.update
          //: are not allowed while an update is in progress", Ctrl+J while
          //: paused).
          DOC_DEBUG.on = false;
          DOC_DEBUG.stop = null;
          queueMicrotask(() => docDebugHere(0));
        }
        docRun = null;
      }
    },
  };
}

//: Show one of the panel's tabs. Problems is drawn as it is shown; the
//: grip (documents-ide.js) hears `mm-panel-tab` and sets that tab's height.
function docRunShowTab(id, focus = false) {
  if (!docRun || !docRun.panes.has(id)) return false;
  DOC_PANEL.tab = id;
  docRun.tab = id;
  for (const [tab, button] of docRun.tabs) {
    const on = tab === id;
    button.setAttribute("aria-selected", String(on));
    button.tabIndex = on ? 0 : -1;
    docRun.panes.get(tab).classList.toggle("hidden", !on);
  }
  if (id === "problems") docProblemsRender();
  docRun.dom.dispatchEvent(new CustomEvent("mm-panel-tab", { detail: id }));
  docRun.view.requestMeasure();
  if (focus) (id === "console" ? docRun.consoleInput : docRun.tabs.get(id))?.focus();
  return true;
}

//: Ctrl+J (no tab): the panel shown or hidden, on the tab it had. A tab's
//: own chord shows the panel on that tab, or hides it when that tab is
//: already the one showing: VS Code's toggles.
function docPanelToggle(tab = null) {
  const CM = window.CM6;
  if (!docCmView || !CM || !docRunToggle) return false;
  if (docRun && (tab === null || docRun.tab === tab)) {
    docRunClose();
    return true;
  }
  if (!docRun) docCmView.dispatch({ effects: docRunToggle.of(true) });
  if (!docRun) return false;
  const next = tab || DOC_PANEL.tab;
  docRunShowTab(next, next === "console");
  return true;
}

//: The panel's chords, from `DOC_PANEL_TABS`: true when one was pressed and
//: done. Read by the editor's keymap (documents-ide.js) and the panel's own.
function docPanelChord(event) {
  if (matchesShortcut(event, "Ctrl+J")) return docPanelToggle(null);
  for (const tab of DOC_PANEL_TABS) {
    if (tab.keys !== "none" && matchesShortcut(event, tab.keys)) return docPanelToggle(tab.id);
  }
  return false;
}

//: Clear clears the tab you are looking at; Problems is the checks', not
//: yours to clear.
function docRunClearTab() {
  if (!docRun) return;
  if (docRun.tab === "console") docRun.consoleLog.replaceChildren();
  else if (docRun.tab === "tests") docRun.testsLog.replaceChildren();
  else if (docRun.tab === "output") docRunClear();
}

//: Problems (D8): every diagnostic the editor holds, whichever check made it
//: (the structure checks, Python's compiler on the server, the scans, the
//: indentation mix, a failed test), in line order, each row a link to its
//: line; the count in the tab whether it is showing or not.
function docProblemsRender() {
  const lint = window.CM6?.lint;
  if (!docRun || !docCmView || !lint) return;
  const state = docCmView.state;
  const found = [];
  lint.forEachDiagnostic(state, (d, from) => found.push({ d, from }));
  found.sort((a, b) => a.from - b.from);
  const count = docRun.tabs.get("problems")?.querySelector(".cm-panel-count");
  if (count) count.textContent = found.length ? String(found.length) : "";
  if (docRun.tab !== "problems") return;
  const list = docRun.problemsLog;
  list.replaceChildren();
  if (!found.length) {
    docRunRow("info", "No problems in this file.", null, list);
    return;
  }
  for (const { d, from } of found.slice(0, DOC_RUN_MAX_ROWS)) {
    const level = d.severity === "error" ? "error" : d.severity === "warning" ? "warn" : "info";
    const line = state.doc.lineAt(Math.min(from, state.doc.length)).number;
    docRunRow(level, `${d.message}${d.source ? ` (${d.source})` : ""}`, line, list, false);
  }
}

//: The console's language: Python for a .py file, JavaScript for the rest.
function docConsoleLang() {
  return DOC_RUN_KINDS[docFileType().ext] === "python" ? "python" : "js";
}

//: Evaluate one line (D8) in what the last run left: the worker's global
//: for JavaScript (a fresh one when nothing has run), the document's
//: namespace for Python. The sandbox's `eval` message (api/run_sandbox.py);
//: what comes back carries `mmEval` and is routed here, not to Output.
async function docConsoleEval(source) {
  if (!docRun) return false;
  const text = String(source || "");
  if (!text.trim()) return false;
  const lang = docConsoleLang();
  const history = DOC_PANEL.history[lang];
  if (history[history.length - 1] !== text) history.push(text);
  if (history.length > 100) history.shift();
  DOC_PANEL.at = -1;
  const log = docRun.consoleLog;
  docRunRow("input", `${lang === "python" ? ">>>" : ">"} ${text}`, null, log);
  if (docRun.running) {
    docRunRow("info", "A run is still going: stop it, or wait for it to finish.", null, log, false);
    return false;
  }
  if (lang === "python") {
    docRunSetStatus("Checking for Python", true);
    const ready = await docRunPythonReady();
    if (!docRun) return false;
    if (!ready) {
      docRunSetStatus("Not run.", false);
      docRunRow("info", "The Python console needs the Pyodide extra: install it in Settings, Packages, Run Python files.", null, log, false);
      return false;
    }
  }
  docRunSelectFrame(lang === "python" ? DOC_RUN_SANDBOX_PY_URL : DOC_RUN_SANDBOX_URL);
  DOC_PANEL.evalSeq += 1;
  const seq = DOC_PANEL.evalSeq;
  docRun.evalId = seq;
  docRunSetStatus("Evaluating", true);
  docRunSend({ type: "eval", mmRun: Math.max(0, docRun.id), mmEval: seq, source: text });
  clearTimeout(docRun.timer);
  //: Python's first line may start the runtime: a minute, as a run's start,
  //: until the sandbox says the line has started (`docConsoleMessage`).
  docRun.timer = setTimeout(() => docConsoleOvertime(seq, lang), lang === "python" ? DOC_RUN_START_MS : DOC_RUN_TIMEOUT_MS);
  return true;
}

//: A console line still running at its limit (OPEN row 1065). Python is
//: interrupted (KeyboardInterrupt in the line, through Pyodide's interrupt
//: buffer), so the namespace the last run left is kept; the worker goes only
//: if that does not answer within DOC_CONSOLE_INTERRUPT_MS. A JavaScript
//: loop cannot be interrupted inside its worker, so that worker goes.
const DOC_CONSOLE_INTERRUPT_MS = 3000;

function docConsoleOvertime(seq, lang) {
  if (!docRun || docRun.evalId !== seq) return;
  if (lang !== "python" || docRun.interrupted === seq) {
    docRunStop("Stopped: the line was still running.");
    return;
  }
  docRun.interrupted = seq;
  docRunSend({ type: "interrupt", mmRun: Math.max(0, docRun.id) });
  docRun.timer = setTimeout(() => docConsoleOvertime(seq, lang), DOC_CONSOLE_INTERRUPT_MS);
}

//: What the sandbox says about an evaluation: its prints and errors as rows,
//: then its value (`eval-done`), and the console is ready again.
function docConsoleMessage(data) {
  if (!docRun || data.mmEval !== docRun.evalId) return;
  const log = docRun.consoleLog;
  if (data.t === "status") {
    docRunSetStatus(String(data.text || "Evaluating"), true);
    return;
  }
  if (data.t === "started") {
    //: The runtime is up and the line is running: its own ten seconds now.
    const seq = docRun.evalId;
    clearTimeout(docRun.timer);
    docRun.timer = setTimeout(() => docConsoleOvertime(seq, docConsoleLang()), DOC_RUN_TIMEOUT_MS);
    return;
  }
  if (data.t === "log") {
    docRunRow(String(data.level || "log"), String(data.text ?? ""), Number(data.line) || null, log);
    return;
  }
  if (data.t !== "eval-done") return;
  clearTimeout(docRun.timer);
  const interrupted = docRun.interrupted === docRun.evalId;
  docRun.evalId = 0;
  docRun.interrupted = 0;
  if (typeof data.text === "string" && data.text !== "") docRunRow(data.ok === false ? "error" : "result", String(data.text), null, log);
  if (interrupted) docRunRow("info", `Stopped after ${DOC_RUN_TIMEOUT_MS / 1000} seconds. The names the last run left are kept.`, null, log, false);
  docRunSetStatus("Ready.", false);
}

//: Up and Down walk the history (newest first), as a terminal's do;
//: Ctrl+L clears, as it does in both consoles.
function docConsoleKey(event) {
  const input = event.target;
  if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "l") {
    event.preventDefault();
    docRun?.consoleLog.replaceChildren();
    return;
  }
  if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
  const history = DOC_PANEL.history[docConsoleLang()];
  if (!history.length) return;
  event.preventDefault();
  let at = DOC_PANEL.at === -1 ? history.length : DOC_PANEL.at;
  at += event.key === "ArrowUp" ? -1 : 1;
  if (at >= history.length) {
    DOC_PANEL.at = -1;
    input.value = "";
    return;
  }
  DOC_PANEL.at = Math.max(0, at);
  input.value = history[DOC_PANEL.at];
  input.setSelectionRange(input.value.length, input.value.length);
}

//: Show or hide the Input box (D9).
function docRunShowStdin(show) {
  if (!docRun) return;
  docRun.stdinWrap.classList.toggle("hidden", !show);
  docRun.stdinButton.setAttribute("aria-expanded", String(show));
  docRun.view.requestMeasure();
  if (show) docRun.stdin.focus();
}

//: Preview live, remembered for every document (a preference, not a
//: property of one file).
function docRunLiveOn() {
  return docToolPref("runLive", false);
}

function docRunSetLive(on) {
  prefs.set(DOC_TOOL_KEYS.runLive, on ? "1" : "0");
  if (!docRun) return;
  docRun.live.setAttribute("aria-pressed", String(on));
  if (on && docRun.preview) docRunCode(docRun.options);
}

//: A change to the text, while a preview is open with Live on: run again
//: once the typing has stopped for 400 ms.
function docRunLiveSchedule() {
  if (!docRun || !docRun.preview || !docRunLiveOn()) return;
  clearTimeout(docRun.liveTimer);
  docRun.liveTimer = setTimeout(() => {
    if (docRun && docRun.preview) docRunCode(docRun.options);
  }, DOC_RUN_LIVE_MS);
}

//: A save refreshes an open preview (D6); with Live on, the typing already has.
function docRunAfterSave() {
  if (docRun && docRun.preview && !docRunLiveOn()) docRunCode(docRun.options);
}

//: The field that says whether the panel is open, and the effect that
//: flips it; the panel follows it through `showPanel`. With it, the
//: listener that feeds Preview live.
function docRunExtension(CM) {
  if (!docRunPanelField) {
    docRunToggle = CM.state.StateEffect.define();
    docRunPanelField = CM.state.StateField.define({
      create: () => false,
      update: (open, tr) => {
        for (const e of tr.effects) if (e.is(docRunToggle)) open = e.value;
        return open;
      },
      provide: (field) => CM.view.showPanel.from(field, (open) => (open ? docRunPanel : null)),
    });
    docRunPanelField = [docRunPanelField, CM.view.EditorView.updateListener.of((update) => {
      if (update.docChanged) docRunLiveSchedule();
      //: Problems follows the checks: redrawn when their answer changes.
      if (docRun && update.transactions.some((tr) => tr.effects.some((e) => e.is(CM.lint.setDiagnosticsEffect)))) docProblemsRender();
    })];
  }
  return docRunPanelField;
}

function docRunSetStatus(text, running) {
  if (!docRun) return;
  docRun.status.textContent = text;
  docRun.running = running;
  docRun.stopButton.disabled = !running;
  if (!running) docRunJobEnd(docRun);
}

//: A long run in Activity (25 row 9): listed once it has gone on for two
//: seconds, renewed every second, and stopped when Activity's Stop was
//: pressed (the renewal's answer). Its row goes when the run ends here.
//: The Activity row is a courtesy: the run goes on whether or not it is
//: listed, and a beat a second would bury a person in toasts. So a refusal is
//: written to the Logs (Settings, Logs) instead of shown, and the call answers
//: null.
function docRunJobCall(path, options) {
  return apiJson(path, { ...options, silent: true }).catch((error) => {
    recordBrowserLog("WARN", [`[Run] Activity row ${options.method} ${path}: ${error.message}`]);
    return null;
  });
}

function docRunJobArm(id) {
  if (!docRun) return;
  const run = docRun;
  docRunJobEnd(run);
  run.jobWait = setTimeout(async () => {
    if (docRun !== run || run.id !== id || !run.running) return;
    const label = `Running ${currentDoc?.title || "a code document"}`.slice(0, 120);
    const body = await docRunJobCall("/documents/run-jobs", { method: "POST", body: JSON.stringify({ label }) });
    if (!body?.id) return;
    if (docRun !== run || run.id !== id || !run.running) {
      docRunJobCall(`/documents/run-jobs/${encodeURIComponent(body.id)}`, { method: "DELETE" });
      return;
    }
    run.job = body.id;
    run.jobBeat = setInterval(async () => {
      const job = run.job;
      if (!job) return;
      const beat = await docRunJobCall(`/documents/run-jobs/${encodeURIComponent(job)}/beat`, { method: "POST" });
      if (beat?.stopped && docRun === run && run.id === id && run.job === job) docRunStop("Stopped from Activity.");
    }, DOC_RUN_JOB_BEAT_MS);
  }, DOC_RUN_JOB_AFTER_MS);
}

function docRunJobEnd(run) {
  if (!run) return;
  clearTimeout(run.jobWait);
  clearInterval(run.jobBeat);
  const job = run.job;
  run.job = null;
  if (job) docRunJobCall(`/documents/run-jobs/${encodeURIComponent(job)}`, { method: "DELETE" });
}

function docRunClear() {
  if (!docRun) return;
  docRun.log.replaceChildren();
  docRun.rows = 0;
}

//: One row of output: its text, and the line it came from as a link back to
//: the editor. Text only, never markup: this is the one place in the app
//: that shows words a program chose.
function docRunRow(level, text, line, into = null, follow = true) {
  if (!docRun) return;
  //: `into` is another tab's list (Problems, Tests, Console); only Output's
  //: rows count toward its cap.
  const list = into || docRun.log;
  const row = document.createElement("li");
  row.className = `cm-run-row is-${["error", "warn", "info", "debug"].includes(level) ? level : "log"}`;
  //: A console's typed line and the value it gave back.
  if (level === "input" || level === "result") row.classList.add(`is-${level}`);
  if (level === "result") {
    //: The value's mark is a Phosphor icon, never a glyph in CSS content
    //: (tests/test_no_ui_emoji.py).
    const mark = document.createElement("i");
    mark.className = "ph ph-arrow-elbow-down-right cm-run-mark";
    mark.setAttribute("aria-hidden", "true");
    row.appendChild(mark);
  }
  const words = document.createElement("span");
  words.className = "cm-run-text";
  words.textContent = String(text).slice(0, 4000);
  row.appendChild(words);
  if (Number.isInteger(line) && line > 0) {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "linklike cm-run-line";
    link.textContent = `Line ${line}`;
    link.title = `Go to line ${line}`;
    link.addEventListener("click", () => {
      jumpToDocLine(line - 1);
      docCmView?.focus();
    });
    row.appendChild(link);
  }
  list.appendChild(row);
  if (list === docRun.log) docRun.rows += 1;
  if (follow) row.scrollIntoView({ block: "nearest" });
}

//: A statement's result (SQL, D5): a table row in the log, its cells as
//: text (never markup), NULL shown as such, and how many rows were left out.
function docRunTable(columns, rows, more, line) {
  if (!docRun) return;
  docRunRow("log", rows.length || more ? `${rows.length + more} row${rows.length + more === 1 ? "" : "s"}` : "No rows.", line);
  const row = docRun.log.lastElementChild;
  row.classList.add("is-table");
  const wrap = document.createElement("div");
  wrap.className = "cm-run-table-wrap";
  const table = document.createElement("table");
  table.className = "cm-run-table";
  const head = table.createTHead().insertRow();
  for (const name of columns.slice(0, 64)) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = String(name);
    head.appendChild(th);
  }
  const body = table.createTBody();
  for (const values of rows.slice(0, 200)) {
    const tr = body.insertRow();
    for (const value of (Array.isArray(values) ? values : []).slice(0, 64)) {
      const td = tr.insertCell();
      td.textContent = value === null ? "NULL" : String(value).slice(0, 400);
      if (value === null) td.className = "is-null";
    }
  }
  wrap.appendChild(table);
  if (more > 0) {
    const note = document.createElement("p");
    note.className = "cm-run-more";
    note.textContent = `${more} more not shown.`;
    wrap.appendChild(note);
  }
  row.appendChild(wrap);
}

//: One test (D7): its state as an icon and a word for the screen reader,
//: its name, its time, the line it is on; a failure's message (the diff
//: unittest or `expect` wrote) under it, as text.
function docRunTestRow(name, state, ms, text, line) {
  if (!docRun) return;
  const kind = ["pass", "fail", "skip"].includes(state) ? state : "fail";
  docRunRow(kind === "fail" ? "error" : kind === "skip" ? "info" : "log", name, line, docRun.testsLog);
  const row = docRun.testsLog.lastElementChild;
  row.classList.add("cm-run-test", `is-${kind}`);
  row.dataset.state = kind;
  const icon = document.createElement("i");
  icon.className = `ph ${{ pass: "ph-check-circle", fail: "ph-x-circle", skip: "ph-minus-circle" }[kind]}`;
  //: The state in words for a screen reader: the icon's colour and shape
  //: alone would be colour alone.
  icon.setAttribute("role", "img");
  icon.setAttribute("aria-label", { pass: "Passed", fail: "Failed", skip: "Skipped" }[kind]);
  row.prepend(icon);
  const time = document.createElement("span");
  time.className = "cm-run-ms";
  time.textContent = `${Math.max(0, Math.round(ms))} ms`;
  row.querySelector(".cm-run-text").after(time);
  if (text) {
    const why = document.createElement("pre");
    why.className = "cm-run-why";
    why.textContent = String(text).slice(0, 4000);
    row.appendChild(why);
  }
  if (kind === "fail" && Number.isInteger(line) && line > 0) {
    DOC_RUN_TEST_MARKS.marks.push({ line, message: `Test failed: ${name}. ${String(text || "").split("\n")[0]}`.slice(0, 400) });
  }
}

//: The failures of the last test run, as the linter's diagnostics, while
//: the document they came from is the one open.
function docRunTestDiagnostics(state) {
  if (!currentDoc || DOC_RUN_TEST_MARKS.doc !== currentDoc.id) return [];
  const out = [];
  for (const mark of DOC_RUN_TEST_MARKS.marks) {
    if (mark.line > state.doc.lines) continue;
    const line = state.doc.line(mark.line);
    out.push({ from: line.from, to: line.to, severity: "error", source: "tests", message: mark.message });
  }
  return out;
}

//: The totals, as the run's last row and its status; the editor's
//: diagnostics are asked for again so the failures show on their lines.
function docRunTestsDone(data) {
  if (!docRun) return;
  const passed = Number(data.passed) || 0;
  const failed = Number(data.failed) || 0;
  const skipped = Number(data.skipped) || 0;
  const parts = [`${passed} passed`, `${failed} failed`];
  if (skipped) parts.push(`${skipped} skipped`);
  const said = `${parts.join(", ")} in ${Math.max(0, Math.round(Number(data.ms) || 0))} ms.`;
  docRunRow(failed ? "error" : "info", said, null, docRun.testsLog);
  docRun.testsLog.lastElementChild.classList.add("cm-run-summary");
  const count = docRun.tabs.get("tests")?.querySelector(".cm-panel-count");
  if (count) count.textContent = String(passed + failed + skipped);
  clearTimeout(docRun.timer);
  docRunSetStatus(passed + failed + skipped ? `${parts.join(", ")}.` : "No tests ran.", false);
  docRunShowTestMarks();
}

//: The failures on their lines now, without waiting for an edit: the
//: linter only runs again on a change (`forceLinting` does nothing until
//: one), so its last answer, less any older test marks, plus these. The
//: linter's own source adds them too, so the next pass keeps them.
function docRunShowTestMarks() {
  const lint = window.CM6?.lint;
  if (!docCmView || !lint?.setDiagnostics) return;
  const kept = [];
  lint.forEachDiagnostic(docCmView.state, (d, from, to) => {
    if (d.source !== "tests") kept.push({ ...d, from, to });
  });
  docCmView.dispatch(lint.setDiagnostics(docCmView.state, kept.concat(docRunTestDiagnostics(docCmView.state))));
}

//: A line for input(), typed in the log where the prompt is (Brief 70):
//: Enter sends it and the run goes on; Escape sends none (input() raises
//: EOFError, as at the end of a file). The prompt and the answer then come
//: back as one row, as a terminal shows them.
function docRunAsk(prompt) {
  if (!docRun) return;
  clearTimeout(docRun.timer);
  docRunSetStatus("Waiting for input", true);
  const id = docRun.id;
  const row = document.createElement("li");
  row.className = "cm-run-row is-ask";
  const label = document.createElement("label");
  label.className = "cm-run-ask";
  const said = document.createElement("span");
  said.className = "cm-run-text";
  said.textContent = prompt.slice(0, 400);
  const field = document.createElement("input");
  field.type = "text";
  field.className = "cm-run-ask-field";
  field.spellcheck = false;
  field.setAttribute("aria-label", prompt.trim() ? `Input: ${prompt.trim().slice(0, 80)}` : "Input for input()");
  label.append(said, field);
  row.appendChild(label);
  const answer = (line) => {
    if (!docRun || docRun.id !== id || !row.isConnected) return;
    row.remove();
    docRunSend({ type: "reply", mmRun: id, value: { line } });
    docRunSetStatus(docDebugOn() ? "Debugging" : "Running", true);
    if (!docDebugOn()) docRunArmTimeout(id);
  };
  field.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      answer(field.value);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      answer(null);
    }
  });
  docRun.log.appendChild(row);
  row.scrollIntoView({ block: "nearest" });
  field.focus();
}

function docRunSend(message) {
  if (!docRun) return;
  if (!docRun.frame.mmReady) {
    docRun.pending = message;
    return;
  }
  docRun.frame.contentWindow?.postMessage(message, "*");
}

function docRunStop(why) {
  if (!docRun) return;
  clearTimeout(docRun.timer);
  docRunSend({ type: "stop", mmRun: docRun.id });
  //: A later message from this run is dropped: the id no longer matches.
  docRun.id = -1;
  docRun.evalId = 0;
  if (docRun.debug) docDebugEnded("stopped", true);
  docRunSetStatus(why, false);
}

function docRunClose() {
  const CM = window.CM6;
  if (docCmView && CM && docRunToggle) docCmView.dispatch({ effects: docRunToggle.of(false) });
  docCmView?.focus();
}

//: The Python prompt, in place of output: what is missing, and the button
//: that installs it. The button is the Settings row's own, reached.
function docRunPythonMissing() {
  if (!docRun) return;
  docRunRow("info", "Running Python needs the Pyodide extra: a one-time download of about 7 MB, and it works offline from then on.", null);
  const row = docRun.log.lastElementChild;
  const install = document.createElement("button");
  install.type = "button";
  install.className = "ghost small cm-run-install";
  const icon = document.createElement("i");
  icon.className = "ph ph-download-simple ph-lead";
  icon.setAttribute("aria-hidden", "true");
  install.append(icon, " Install Python");
  install.title = "Open Settings, Packages, at Run Python files";
  install.addEventListener("click", () => docRunOpenPythonExtra());
  row?.appendChild(install);
  docRunSetStatus("Not run.", false);
}

//: The ten seconds, from now, for run `id`.
function docRunArmTimeout(id) {
  if (!docRun) return;
  clearTimeout(docRun.timer);
  docRun.timer = setTimeout(() => {
    if (docRun && docRun.id === id && docRun.running) {
      docRunStop("Stopped after 10 seconds: the script was still running.");
    }
  }, DOC_RUN_TIMEOUT_MS);
}

//: **A CSV document is a table to a SQL run** (D5, OPEN 1069). A query that
//: names a CSV document's table (its title without ".csv", in lower case
//: with anything but letters, digits and _ as _: "Sales 2026.csv" is
//: `sales_2026`) gets that document loaded first, its first row the column
//: names. Nothing to pick: writing the name is the choice, as it is in any
//: database. Numbers stay numbers, so `WHERE amount > 9` compares as numbers.
const DOC_SQL_CSV_TABLES = 8;
const DOC_SQL_CSV_ROWS = 50000;

function docSqlTableName(title) {
  const base = String(title || "").replace(/\.csv$/i, "").trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
  if (!base) return "";
  return /^[0-9]/.test(base) ? `t_${base}` : base;
}

//: RFC 4180: quoted fields may hold commas, quotes ("") and line breaks.
//: One row past the cap is read, so a cut table can say it was cut.
function docSqlCsvRows(text, cap = DOC_SQL_CSV_ROWS + 2) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  const src = String(text || "").replace(/^\uFEFF/, "");
  for (let i = 0; i < src.length && rows.length < cap; i += 1) {
    const ch = src[i];
    if (quoted) {
      if (ch === '"' && src[i + 1] === '"') { cell += '"'; i += 1; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"' && cell === "") quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && src[i + 1] === "\n") i += 1;
      row.push(cell); cell = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (rows.length < cap && (cell !== "" || row.length)) { row.push(cell); rows.push(row); }
  return rows;
}

function docSqlCsvTable(name, text) {
  const rows = docSqlCsvRows(text);
  if (!rows.length) return null;
  const seen = new Set();
  const columns = rows[0].map((head, i) => {
    let col = String(head).trim() || `column_${i + 1}`;
    while (seen.has(col.toLowerCase())) col = `${col}_${i + 1}`;
    seen.add(col.toLowerCase());
    return col;
  });
  const number = /^-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/;
  const body = rows.slice(1, DOC_SQL_CSV_ROWS + 1).map((r) =>
    columns.map((_, i) => {
      const v = r[i] === undefined ? null : r[i];
      return v !== null && number.test(v.trim()) ? Number(v) : v;
    })
  );
  return { name, columns, rows: body, cut: rows.length - 1 > DOC_SQL_CSV_ROWS };
}

//: The CSV documents the query names, read in one request.
async function docSqlCsvTables(sql) {
  const words = new Set(String(sql || "").toLowerCase().match(/[a-z_][a-z0-9_]*/g) || []);
  const docs = await apiJson("/documents/contents?file_type=csv");
  const tables = [];
  const taken = new Set();
  for (const doc of docs || []) {
    const name = docSqlTableName(doc.title);
    if (!name || taken.has(name) || !words.has(name) || doc.id === currentDoc?.id) continue;
    const table = docSqlCsvTable(name, doc.content);
    if (!table) continue;
    taken.add(name);
    tables.push(table);
    if (tables.length >= DOC_SQL_CSV_TABLES) break;
  }
  return tables;
}

//: Run the open file: the panel opens (or is reused), the output is
//: cleared, and the text as it is now goes to the sandbox as one request of
//: the run protocol (run-core.js). `options.mode` is "run" or "test";
//: `options.range` runs part of the file (a selection or a cell) with its
//: line numbers kept.
async function docRunCode(options = {}) {
  const CM = window.CM6;
  const type = docFileType();
  if (!docCmView || !CM || !docRunToggle) return false;
  const page = DOC_RUN_KINDS[type.ext];
  if (!docRun) docCmView.dispatch({ effects: docRunToggle.of(true) });
  if (!docRun) return false;
  docRunClear();
  //: A run's output is what a run is for: the panel shows it (and Tests,
  //: once the run turns out to be one).
  if (docRun.tab !== "output") docRunShowTab("output");
  clearTimeout(docRun.timer);
  docRun.dom.classList.remove("is-page");
  if (!page) {
    docRunRow("info", DOC_RUN_CANNOT[type.ext] || "This kind of file does not run here.", null);
    docRunSetStatus("Not run.", false);
    return false;
  }
  const debug = options.mode === "debug";
  //: Debug's one line where it cannot run (D2): another kind of file, or a
  //: Python run in a window without SharedArrayBuffer. Run still works.
  const cannot = !debug ? "" : !DOC_DEBUG_KINDS.has(type.ext) ? DOC_DEBUG_CANNOT.kind : page === "python" && !self.crossOriginIsolated ? DOC_DEBUG_CANNOT.isolation : "";
  if (cannot) {
    docRunShowTab("debug");
    docRunRow("info", cannot, null);
    docDebugEnded("done", true);
    DOC_DEBUG.said = cannot;
    docDebugRender();
    docRunSetStatus("Not run.", false);
    return false;
  }
  const doc = docCmView.state.doc;
  const range = options.range || null;
  //: A Python file that asks for input with the box closed: open it, so the
  //: lines it reads have somewhere to be typed (the run still goes ahead).
  if (page === "python" && docRun.stdinWrap.classList.contains("hidden") && /\binput\s*\(/.test(doc.toString())) {
    docRun.stdinWrap.classList.remove("hidden");
    docRun.stdinButton.setAttribute("aria-expanded", "true");
  }
  let source = range ? doc.sliceString(range.from, range.to) : doc.toString();
  if (range && options.dedent) {
    const lines = source.split("\n");
    const indents = lines.filter((l) => l.trim()).map((l) => /^[ \t]*/.exec(l)[0].length);
    const cut = indents.length ? Math.min(...indents) : 0;
    if (cut) source = lines.map((l) => l.slice(Math.min(cut, /^[ \t]*/.exec(l)[0].length))).join("\n");
  }
  const request = {
    ext: type.ext,
    source,
    lineOffset: range ? doc.lineAt(range.from).number - 1 : 0,
    path: currentDoc?.title || "",
    stdin: docRun.stdin?.value || "",
  };
  if (type.ext === "sql") {
    try {
      request.tables = await docSqlCsvTables(source);
      for (const t of request.tables) {
        if (t.cut) docRunRow("info", `${t.name}: only the first ${DOC_SQL_CSV_ROWS.toLocaleString("en")} rows were loaded.`, null);
      }
    } catch {
      request.tables = [];
    }
  }
  const id = ++docRunSeq;
  docRun.id = id;
  docRunSetStatus("Preparing", true);
  let prepared;
  try {
    if (!(await ensureModule("run"))) throw new Error("The runner did not load. Check the connection to the app and run again.");
    prepared = await runPrepare(request, options.mode || "run");
  } catch (error) {
    if (!docRun || docRun.id !== id) return false;
    docRunRow("error", String(error?.message || error), Number.isInteger(error?.line) ? error.line + request.lineOffset : null);
    docRunSetStatus("Not run.", false);
    return false;
  }
  //: Another Run, a Stop or a closed panel while that was loading: this run
  //: is not the current one any more.
  if (!docRun || docRun.id !== id) return false;
  docRun.dom.classList.toggle("is-page", prepared.shows && !prepared.debug);
  docRun.preview = prepared.preview && !prepared.debug;
  docRun.tests = prepared.tests;
  docDebugBegin(prepared);
  if (prepared.tests) {
    DOC_RUN_TEST_MARKS.doc = currentDoc?.id ?? null;
    DOC_RUN_TEST_MARKS.marks = [];
    docRun.testsLog.replaceChildren();
    //: Debug keeps its own pane in front; the Tests tab fills behind it.
    if (!prepared.debug) docRunShowTab("tests");
  }
  docRun.options = { mode: options.mode, range: options.range };
  docRun.live.classList.toggle("hidden", !prepared.preview);
  if (prepared.notice) docRunRow("info", prepared.notice, null);
  if (prepared.page === "python") {
    docRunSetStatus("Checking for Python", true);
    const ready = await docRunPythonReady();
    if (!docRun || docRun.id !== id) return false;
    if (!ready) {
      docRunPythonMissing();
      return false;
    }
  }
  //: One frame, two pages: Python's for .py, the other for the rest. A
  //: switch reloads the frame, and the run waits for its `ready`.
  const runner = prepared.page === "python" ? DOC_RUN_SANDBOX_PY_URL : DOC_RUN_SANDBOX_URL;
  docRunSelectFrame(runner);
  docRunSetStatus(prepared.page === "python" ? "Starting Python" : prepared.debug ? "Debugging" : "Running", true);
  docRunSend({ ...prepared.message, ...(prepared.debug ? { breaks: docDebugBreaks(), watches: DOC_DEBUG.watches.slice() } : {}), type: "run", mmRun: id });
  docRunJobArm(id);
  if (prepared.page === "python") {
    docRun.timer = setTimeout(() => {
      if (docRun && docRun.id === id && docRun.running) {
        docRunStop("Stopped: Python did not start within a minute.");
      }
    }, DOC_RUN_START_MS);
  } else {
    docRunArmTimeout(id);
  }
  return true;
}

//: Run the selected lines (D9), or the caret's line: whole lines, their
//: shared indent taken off so a block's body runs on its own, its line
//: numbers the document's (the protocol's `lineOffset`).
function docRunSelection() {
  if (!docCmView || !DOC_RUN_KINDS[docFileType().ext]) return false;
  const { doc, selection } = docCmView.state;
  const from = doc.lineAt(selection.main.from);
  const to = doc.lineAt(selection.main.to);
  return docRunCode({ range: { from: from.from, to: to.to }, dedent: true });
}

//: The cell at the caret (D9): from the `# %%` (or `// %%`, `-- %%`) line
//: at or above it to the line before the next one. With no markers, the
//: whole file.
function docRunCell() {
  if (!docCmView || !DOC_RUN_KINDS[docFileType().ext]) return false;
  const { doc, selection } = docCmView.state;
  const marker = /^\s*(?:#|\/\/|--)\s*%%/;
  const here = doc.lineAt(selection.main.head).number;
  let start = 1;
  for (let n = here; n >= 1; n -= 1) {
    if (marker.test(doc.line(n).text)) {
      start = n;
      break;
    }
  }
  let end = doc.lines;
  for (let n = Math.max(here, start) + 1; n <= doc.lines; n += 1) {
    if (marker.test(doc.line(n).text)) {
      end = n - 1;
      break;
    }
  }
  return docRunCode({ range: { from: doc.line(start).from, to: doc.line(end).to } });
}

//: The sandbox's messages. Only from the panel's own frame, only for the run
//: in flight; everything in them is treated as text.
//: The shared Python page says `ready` whether or not a panel is open: it
//: loads when a Python document does, before any panel exists, so this does
//: not wait for one (the listener below only hears the panel's own frame).
window.addEventListener("message", (event) => {
  const host = DOC_PY_HOST.frame;
  if (!host || event.source !== host.contentWindow) return;
  const data = event.data && typeof event.data === "object" ? event.data : {};
  if (data.t !== "ready" || data.mmRun !== 0 || data.runner !== "python") return;
  host.mmReady = true;
  if (DOC_PY_HOST.warm) {
    DOC_PY_HOST.warm = false;
    host.contentWindow.postMessage({ type: "warm", mmRun: 0 }, "*");
  }
});

window.addEventListener("message", (event) => {
  if (!docRun || event.source !== docRun.frame.contentWindow) return;
  const data = event.data && typeof event.data === "object" ? event.data : {};
  if (data.t === "ready" && data.mmRun === 0) {
    //: Only the runner the frame is on now. Measured in Chromium: a panel
    //: opened on a .py file loaded the JavaScript runner, switched to the
    //: Python one, and the first runner's late `ready` released the run
    //: into a page already on its way out; the run never started. The
    //: Python page says which it is; the JavaScript page says nothing.
    const wanted = docRun.frame.dataset.runner === DOC_RUN_SANDBOX_PY_URL ? "python" : undefined;
    if (data.runner !== wanted) return;
    docRun.frame.mmReady = true;
    if (docRun.pending) {
      const message = docRun.pending;
      docRun.pending = null;
      docRunSend(message);
    }
    return;
  }
  //: The console's answers (D8), tagged by the sandbox with the line's number.
  if (typeof data.mmEval === "number" && data.mmEval > 0) {
    docConsoleMessage(data);
    return;
  }
  if (data.mmRun !== docRun.id) return;
  //: Python's runner says when its runtime is loading and when the script
  //: itself begins; the ten seconds start then.
  if (data.t === "status") {
    if (docRun.running) docRunSetStatus(String(data.text || "Running"), true);
    return;
  }
  if (data.t === "started") {
    if (docRun.running) docRunSetStatus(docRun.debug ? "Debugging" : "Running", true);
    docRunArmTimeout(docRun.id);
    return;
  }
  //: input() past the Input box's lines, asked mid-run (Brief 70): the
  //: worker waits on D2's buffer for the answer, so the ten seconds wait too.
  if (data.t === "input") {
    docRunAsk(String(data.prompt || ""));
    return;
  }
  //: A debugger stop (D2, D3): the Debug tab shows it; the ten seconds wait.
  if (data.t === "stop") {
    clearTimeout(docRun.timer);
    docDebugStopped(data);
    return;
  }
  //: INBOX 736: Stop stayed enabled after "Finished.". A script is over
  //: when its top level is and no timer of its own is pending (the worker
  //: counts them and says `idle` when the last one goes); a page stays live.
  if (data.t === "done") {
    clearTimeout(docRun.timer);
    if (docRun.debug) {
      docDebugEnded(String(data.ended || "done"));
      return;
    }
    if (!docRun.running) return;
    if (docRun.tests) {
      //: The harness's totals are the run's end; `done` comes after them.
      docRunSetStatus(docRun.status.textContent, false);
      return;
    }
    //: A stylesheet or an SVG is a still picture: nothing left to stop.
    if (["css", "svg"].includes(docFileType().ext)) docRunSetStatus("Preview shown.", false);
    else if (docRun.dom.classList.contains("is-page")) docRunSetStatus("Page loaded.", true);
    else if (data.pending > 0) docRunSetStatus("Waiting on timers", true);
    else docRunSetStatus("Finished.", false);
    return;
  }
  if (data.t === "idle") {
    if (docRun.running) docRunSetStatus("Finished.", false);
    return;
  }
  if (data.t === "test") {
    docRunTestRow(String(data.name || "test"), String(data.state || "fail"), Number(data.ms) || 0, String(data.text || ""), Number(data.line) || null);
    return;
  }
  if (data.t === "tests-done") {
    docRunTestsDone(data);
    return;
  }
  if (data.t === "table") {
    docRunTable(Array.isArray(data.columns) ? data.columns : [], Array.isArray(data.rows) ? data.rows : [], Number(data.more) || 0, Number(data.line) || null);
    if (docRun.rows >= DOC_RUN_MAX_ROWS) docRunStop(`Stopped after ${DOC_RUN_MAX_ROWS} lines of output.`);
    return;
  }
  if (data.t !== "log") return;
  docRunRow(String(data.level || "log"), String(data.text ?? ""), Number(data.line) || null);
  //: An uncaught error ends a script's top level as surely as its last line
  //: does: the run is over, not still going for the timeout to find.
  //: A still preview (a stylesheet, an SVG) that fails to read is over too.
  if (data.uncaught && docRun.running && (!docRun.dom.classList.contains("is-page") || ["css", "svg"].includes(docFileType().ext))) {
    clearTimeout(docRun.timer);
    docRunSetStatus("Stopped by an error.", false);
  }
  if (docRun.rows >= DOC_RUN_MAX_ROWS) docRunStop(`Stopped after ${DOC_RUN_MAX_ROWS} lines of output.`);
});

//: Go to a symbol, from the palette: the file's symbols in the menu at the
//: caret, VS Code's Ctrl+Shift+O list. Not on that chord: this app's
//: registry gives Ctrl+Shift+O to starting a new chat.
function docOpenSymbols() {
  const CM = window.CM6;
  const view = docCmView;
  if (!CM || !view || typeof openMenuAtPoint !== "function") return false;
  const symbols = docCodeSymbols(CM, view.state, docFileType().ext);
  const items = symbols.length
    ? symbols.slice(0, 200).map((s) => ({
      label: `${s.text.startsWith("class ") ? "ph:cube" : /\(\)$/.test(s.text) ? "ph:function" : "ph:hash"} ${s.text}`,
      title: `Line ${s.line + 1}`,
      run: () => jumpToDocLine(s.line),
    }))
    : [{ label: "ph:info No symbols in this file", disabled: true, run: () => {} }];
  const at = view.coordsAtPos(view.state.selection.main.head) || view.contentDOM.getBoundingClientRect();
  openMenuAtPoint(items, "Symbols in this file", at.left, at.bottom);
  return true;
}

//: XML's Emmet source, as language data for the stream mode: one stable
//: array, for the identity reason above.
let docEmmetXmlData = null;

function docCompletionExtras(CM, type) {
  if (DOC_EMMET_SYNTAX[type.ext]) docLoadEmmet();
  if (!docEmmetXmlData) docEmmetXmlData = [{ autocomplete: docEmmetSource(CM, "xml") }];
  const config = { activateOnTyping: true, maxRenderedOptions: 60 };
  if (type.ext === "css") config.override = docCssSources(CM);
  return [
    CM.autocomplete.autocompletion(config),
    type.ext === "html" ? CM.html.htmlLanguage.data.of({ autocomplete: docEmmetSource(CM, "html") }) : [],
    //: The JSX dialect shares JavaScript's language data, so this reaches a
    //: `.js` file; the source itself answers only inside JSX.
    type.ext === "js" ? CM.javascript.javascriptLanguage.data.of({ autocomplete: docEmmetSource(CM, "jsx") }) : [],
    type.ext === "xml" ? CM.state.EditorState.languageData.of(() => docEmmetXmlData) : [],
    type.ext === "xml" ? docXmlAutoClose(CM) : [],
    ["css", "html"].includes(type.ext) ? docColorSwatches(CM) : [],
    ["css", "html", "py"].includes(type.ext) ? docHoverDocs(CM) : [],
    docIndentGuides(CM, type.indent || "  "),
    DOC_SYMBOL_EXTS.has(type.ext) ? docStickyScroll(CM) : [],
    docNativeSnippets(CM, type.ext),
    //: Every code file has the panel (Problems, Console); Run says itself
    //: when a kind does not run.
    docRunExtension(CM),
    DOC_DEBUG_KINDS.has(type.ext) ? docDebugExtension(CM) : [],
    docBracketColours(CM),
    ["html", "xml", "js"].includes(type.ext) ? docTagLink(CM, DOC_EMMET_SYNTAX[type.ext]) : [],
    docGhostPlugin(CM),
    //: documents-ide.js: the minimap, the merge view, Ctrl+Shift+M.
    typeof docIdeExtensions === "function" ? docIdeExtensions(CM, type) : [],
    CM.state.Prec.highest(CM.view.keymap.of([{ key: "Tab", run: (view) => docCompleteTab(view, CM) }])),
  ];
}

// -----------------------------------------------------------------------------
// Code documents as a code editor, part two: pairs, indentation, formatting
// and quick fixes
// -----------------------------------------------------------------------------
//
// The owner, 2026-09-23: "on the code document types as well, can you add
// the things like with vs code how if I write a \" it automatically does \"\"
// and puts my cursor position in between them ... if Im writing in a c
// language or java or smth where I write var_name { and it automatically
// does {} and then if I press enter it automatically indents and code
// structures them?? also a button to automatically format the whole
// document, ot just a selection ... also recommended fixes to apply like the
// other autocorrect feature."
//
// The pure half first: everything here is string work with no editor in
// it, so `tests/test_code_editing.py` runs it in node and holds every
// indent, every format and every fix to the exact text it must produce.

// DOC-CODE-BEGIN (tests/test_code_editing.py runs this region in node)
//: **What the editor has to know about a language to leave its strings and
//: comments alone**, per file type. Not a grammar: the four things a
//: bracket, an indent or a trailing space depends on, which are where a
//: comment starts, where a string starts and ends, whether a string may run
//: onto the next line, and the handful of oddities (a C++ raw string, a
//: Rust lifetime, a JavaScript regex) that would otherwise be read as an
//: unclosed quote or an unmatched bracket. The Lezer grammars in the bundle
//: know more than this for five languages; the other seventeen have a
//: highlighter that colours a line at a time and cannot answer "which `{`
//: does this `}` close", so this is the one answer all of them share.
//:
//: Each quote is `[open, close, multi, escape, doubled]`: `multi` is whether
//: the string may cross a line break, `escape` whether a backslash escapes
//: the next character, `doubled` whether writing the quote twice is how the
//: language escapes it (SQL's `'it''s'`). Longer openers come first, so a
//: `"""` is never read as three empty strings.
function docCodeProfile(ext) {
  const q = (open, close, multi, escape = true, doubled = false) => ({ open, close, multi, escape, doubled });
  const dq = q('"', '"', false);
  const sq = q("'", "'", false);
  const slash = { line: ["//"], block: ["/*", "*/"] };
  const cLike = { ...slash, quotes: [dq, sq], stmt: true, caseStyle: "indent" };
  switch (ext) {
    case "c": return { ...cLike, preproc: true };
    case "cpp": return { ...cLike, preproc: true, rawCpp: true, digitSep: true };
    case "cs": return { ...cLike, quotes: [q('"""', '"""', true, false), dq, sq], verbatimCs: true };
    case "java": return { ...cLike, quotes: [q('"""', '"""', true), dq, sq] };
    case "kt": return { ...cLike, nest: true, quotes: [q('"""', '"""', true, false), dq, sq], caseStyle: null };
    case "go": return { ...cLike, quotes: [dq, sq, q("`", "`", true, false)], caseStyle: "flush" };
    case "rs": return { ...cLike, nest: true, quotes: [q('"', '"', true)], rustChars: true, rustRaw: true, caseStyle: null };
    case "swift": return { ...cLike, nest: true, quotes: [q('"""', '"""', true), dq], caseStyle: "flush" };
    case "php":
      return { ...cLike, line: ["//", "#"], quotes: [q('"', '"', true), q("'", "'", true)], phpTags: true,
        heredoc: /^<<<[ \t]*(['"]?)([A-Za-z_]\w*)\1/ };
    case "js":
    case "ts":
      return { ...cLike, quotes: [dq, sq, q("`", "`", true)], template: true, regex: true };
    case "css": return { line: [], block: ["/*", "*/"], quotes: [dq, sq] };
    case "json": return { line: [], block: null, quotes: [dq] };
    case "r": return { line: ["#"], block: null, quotes: [q('"', '"', true), q("'", "'", true), q("`", "`", true)], stmt: true };
    case "sql":
      return { line: ["--"], block: ["/*", "*/"],
        quotes: [q("'", "'", true, false, true), q('"', '"', true, false, true), q("`", "`", true, false, true)] };
    case "bash":
      return { line: ["#"], hashAtWord: true, block: null, heredoc: /^<<-?[ \t]*(['"]?)([A-Za-z_]\w*)\1/,
        quotes: [q('"', '"', true), q("'", "'", true, false), q("`", "`", true)] };
    case "toml":
      return { line: ["#"], block: null,
        quotes: [q('"""', '"""', true), q("'''", "'''", true, false), dq, q("'", "'", false, false)] };
    case "ini": return { line: [";", "#"], block: null, quotes: [] };
    case "py":
      return { line: ["#"], block: null,
        quotes: [q('"""', '"""', true), q("'''", "'''", true), dq, sq] };
    case "rb":
      return { line: ["#"], block: null, heredoc: /^<<[-~]?(['"]?)([A-Z_]\w*)\1/,
        quotes: [q('"', '"', true), q("'", "'", true), q("`", "`", true)] };
    //: No quotes for YAML: a quote only opens a string at the start of a
    //: value there, so `note: don't` is an apostrophe, and reading it as a
    //: string that never closes would refuse to tidy a valid file. What YAML
    //: does have that matters here is the block scalar, handled by the
    //: formatter itself.
    case "yaml": return { line: ["#"], hashAtWord: true, block: null, quotes: [] };
    default: return null;
  }
}

const DOC_CODE_OPEN = { "(": ")", "[": "]", "{": "}" };
const DOC_CODE_CLOSE = { ")": "(", "]": "[", "}": "{" };

//: **One pass over the text: where every string and comment is, which
//: bracket each closer closes, and how deep every line sits.** Everything
//: this section does (the indent on Enter, the formatter, the bracket
//: diagnostics and their fixes) reads this one answer, so the three cannot
//: disagree about whether a `{` inside a string counts.
//:
//: Each line comes back with:
//:
//: - `startsIn`: `null` when it starts in code, else `"string"`,
//:   `"comment"`, `"preproc"` (the continuation of a C `#define`) or
//:   `"outside"` (HTML around a PHP block). Such a line is never re-indented,
//:   because its leading spaces are part of something else.
//: - `endsIn`: the same question asked at its end, which is what decides
//:   whether its trailing spaces are content.
//: - `level`: how many indent units deep it belongs, or `null` when
//:   `startsIn` says it is not code's to move.
//: - `code`: the line with every comment removed and every string reduced
//:   to its quotes, which is what the rules below match against.
//:
//: And `problems`: an unmatched or wrong closer, an opener never closed, a
//: string or a comment that never ends, each with its offset.
//:
//: **How deep a line is.** A frame's lines sit one unit in from the line
//: that opened it, however many brackets that line opened (`foo(bar, {`
//: indents its body once, not twice), and a line that starts by closing
//: frames sits where the line that opened the last of them sat. That is the
//: rule every editor's "increase indent after an opener" pattern
//: approximates, stated structurally, so it gives the same answer for a
//: line typed now and for the same line reformatted later. Three further
//: rules for statement languages: a `case` label and its body (indented
//: under a C, Java or JavaScript `switch`, flush under Go's and Swift's, as
//: their own formatters put them); the one statement under a brace-less
//: `if`, `for`, `while` or `else`; and a line that continues an expression
//: (the previous line ended on an operator, or this one starts with `.`,
//: `?`, `:`, `&&` or `||`), each one unit further in.
function docCodeScan(text, ext) {
  const profile = docCodeProfile(ext);
  const lines = [];
  const problems = [];
  if (!profile) return { lines: text.split("\n").map(() => ({ level: null })), problems, profile };
  const stack = [];
  const n = text.length;
  //: `mode` is what the scanner is inside: code, a string (`quote` says
  //: which), a block comment, a preprocessor line, or HTML outside `<?php`.
  let mode = profile.phpTags ? "outside" : "code";
  let quote = null;
  let quoteAt = 0;
  let commentAt = 0;
  let commentDepth = 0;
  let rawClose = "";
  let heredoc = null;
  //: The last significant code character and word, across lines, which is
  //: what tells a regex from a division in JavaScript.
  let lastSig = "";
  let lastWord = "";
  let prevCode = null;
  let i = 0;
  let lineNo = 0;

  const newLine = (from) => {
    const startsIn = mode === "code" ? null : mode;
    const line = {
      from, to: from, startsIn, endsIn: null, level: null, code: "",
      commentOpenLine: startsIn === "comment" ? commentOpenLine : null,
      preproc: startsIn === "preproc",
      pending: startsIn === null,
      lastPopped: null,
    };
    lines.push(line);
    return line;
  };
  let commentOpenLine = null;
  let line = newLine(0);

  const top = () => stack[stack.length - 1] || null;
  const labelRe = profile.caseStyle === "flush"
    ? /^(case\b[^\n]*|default\s*):\s*(\/\/.*)?$/
    : /^(case\b|default\s*:)/;
  const bracelessRe = /^(\}\s*)?(else\s+)?(if|for|foreach|while)\b.*\)$|^(\}\s*)?else$|^do$/;
  const endOpRe = /(?:[*/%=&|^?]|(?<!\+)\+|(?<!-)-)$/;
  const startOpRe = /^(\.(?!\.)|\?|:(?!:)|&&|\|\|)/;

  //: The level of the line in hand, decided at its first character that is
  //: not a leading closer: that is the first moment all of the above is
  //: known.
  const settle = (at) => {
    if (!line.pending) return;
    line.pending = false;
    const rest = text.slice(at, text.indexOf("\n", at) === -1 ? n : text.indexOf("\n", at));
    const t = top();
    if (line.lastPopped) {
      line.level = line.lastPopped.lineLevel;
      return;
    }
    let level = t ? t.inner : 0;
    if (profile.stmt) {
      const inBraces = !t || t.ch === "{";
      if (t && t.ch === "{" && profile.caseStyle && labelRe.test(rest)) {
        t.inCase = true;
        level += profile.caseStyle === "flush" ? -1 : 0;
      } else if (t && t.inCase) {
        level += profile.caseStyle === "flush" ? 0 : 1;
      }
      const sameFrame = prevCode && prevCode.frame === t;
      const prev = sameFrame ? prevCode.code.trim() : "";
      if (sameFrame && inBraces && bracelessRe.test(prev) && !rest.startsWith("{")) level += 1;
      else if (sameFrame && inBraces && endOpRe.test(prev)) level += 1;
      else if (startOpRe.test(rest)) level += 1;
    }
    line.level = Math.max(0, level);
  };

  const push = (ch, at, extra = {}) => {
    const level = line.level === null ? (top() ? top().inner : 0) : line.level;
    stack.push({ ch, at, line: lineNo, lineLevel: level, inner: level + 1, inCase: false, ...extra });
  };

  const close = (ch, at) => {
    const want = DOC_CODE_CLOSE[ch];
    let k = stack.length - 1;
    while (k >= 0 && stack[k].ch !== want) k -= 1;
    if (k < 0 || (k < stack.length - 1 && stack.length - 1 - k > 3)) {
      const t = top();
      problems.push({ kind: "stray", at, ch, expect: t ? DOC_CODE_OPEN[t.ch] : null, line: lineNo });
      return null;
    }
    while (stack.length - 1 > k) {
      const lost = stack.pop();
      problems.push({ kind: "unclosed", at: lost.at, ch: lost.ch, line: lost.line, before: at });
    }
    return stack.pop();
  };

  const startsWithAt = (s, at) => text.startsWith(s, at);

  while (i < n) {
    const ch = text[i];
    if (ch === "\n") {
      if (mode === "string" && !quote.multi) {
        problems.push({ kind: "string", at: quoteAt, ch: quote.open, line: lineNo });
        mode = "code";
      }
      if (mode === "preproc" && text[i - 1] !== "\\" && !(text[i - 1] === "\r" && text[i - 2] === "\\")) mode = "code";
      if (mode === "line") mode = "code";
      //: A heredoc's body starts on the line after its `<<EOF`, and is a
      //: string until a line that is just the word.
      if (heredoc && mode === "code") {
        mode = "string";
        quote = { open: "<<", close: "\n", multi: true, escape: false, heredoc };
        quoteAt = i;
        heredoc = null;
      }
      line.to = i;
      line.endsIn = mode === "code" ? null : mode;
      if (line.pending) {
        //: A blank line, or one that was nothing but closers.
        settle(i);
        line.blank = true;
      }
      if (line.code.trim() && !line.preproc) prevCode = { code: line.code, frame: top() };
      i += 1;
      lineNo += 1;
      line = newLine(i);
      continue;
    }
    if (mode === "outside") {
      if (startsWithAt("<?php", i) || startsWithAt("<?=", i) || startsWithAt("<?", i)) {
        mode = "code";
        i += startsWithAt("<?php", i) ? 5 : startsWithAt("<?=", i) ? 3 : 2;
        line.pending = false;
        continue;
      }
      i += 1;
      continue;
    }
    if (mode === "line") {
      i += 1;
      continue;
    }
    if (mode === "preproc") {
      i += 1;
      continue;
    }
    if (mode === "comment") {
      if (profile.nest && startsWithAt(profile.block[0], i)) {
        commentDepth += 1;
        i += profile.block[0].length;
        continue;
      }
      if (startsWithAt(profile.block[1], i)) {
        i += profile.block[1].length;
        commentDepth -= 1;
        if (commentDepth <= 0) mode = "code";
        continue;
      }
      i += 1;
      continue;
    }
    if (mode === "string") {
      if (quote.heredoc) {
        let end = text.indexOf("\n", i);
        if (end === -1) end = n;
        const body = text.slice(i, end);
        const word = body.indexOf(quote.heredoc);
        if (i === line.from && word !== -1 && body.trim().replace(/[;,)]+$/, "") === quote.heredoc) {
          mode = "code";
          i += word + quote.heredoc.length;
          lastSig = "0";
          continue;
        }
        i = end;
        continue;
      }
      if (rawClose) {
        if (startsWithAt(rawClose, i)) {
          i += rawClose.length;
          rawClose = "";
          mode = "code";
          line.code += '"';
          lastSig = "0";
          continue;
        }
        i += 1;
        continue;
      }
      if (quote.escape && ch === "\\") {
        i += 2;
        continue;
      }
      if (quote.template && ch === "$" && text[i + 1] === "{") {
        push("{", i, { template: quote });
        mode = "code";
        i += 2;
        lastSig = "{";
        continue;
      }
      if (startsWithAt(quote.close, i)) {
        if (quote.doubled && startsWithAt(quote.close, i + quote.close.length)) {
          i += quote.close.length * 2;
          continue;
        }
        i += quote.close.length;
        mode = "code";
        line.code += quote.close;
        lastSig = "0";
        continue;
      }
      i += 1;
      continue;
    }

    // --- code ---
    if (ch === " " || ch === "\t" || ch === "\r") {
      line.code += ch;
      i += 1;
      continue;
    }
    if (profile.phpTags && startsWithAt("?>", i)) {
      mode = "outside";
      i += 2;
      continue;
    }
    if (line.pending && profile.preproc && ch === "#") {
      line.pending = false;
      line.level = 0;
      line.preproc = true;
      mode = "preproc";
      i += 1;
      continue;
    }
    if (profile.block && startsWithAt(profile.block[0], i)) {
      mode = "comment";
      commentAt = i;
      commentDepth = 1;
      commentOpenLine = lineNo;
      i += profile.block[0].length;
      continue;
    }
    const lineComment = profile.line.find((tok) => startsWithAt(tok, i));
    if (lineComment && (!profile.hashAtWord || i === 0 || /\s/.test(text[i - 1]))) {
      mode = "line";
      line.commentAt = i;
      i += lineComment.length;
      continue;
    }
    if (line.pending && DOC_CODE_CLOSE[ch]) {
      const popped = close(ch, i);
      if (popped) line.lastPopped = popped;
      line.code += ch;
      lastSig = ch;
      if (popped && popped.template) {
        //: The `}` of a `${ }` goes back into the template string.
        quote = popped.template;
        mode = "string";
        quoteAt = i;
      }
      i += 1;
      continue;
    }
    settle(i);
    //: A C++ raw string, `R"delim( ... )delim"`, which may hold anything.
    if (profile.rawCpp && ch === "R" && text[i + 1] === '"' && !/[\w]/.test(text[i - 1] || "")) {
      const open = /^R"([^()\\\s]{0,16})\(/.exec(text.slice(i, i + 20));
      if (open) {
        rawClose = `)${open[1]}"`;
        mode = "string";
        quote = { open: '"', close: rawClose, multi: true, escape: false };
        quoteAt = i;
        line.code += '"';
        i += open[0].length;
        continue;
      }
    }
    //: Rust's raw strings (`r"…"`, `r#"…"#`) and its lifetimes and chars.
    if (profile.rustRaw && (ch === "r" || ch === "b") && !/[\w]/.test(text[i - 1] || "")) {
      const open = /^b?r(#*)"/.exec(text.slice(i, i + 20));
      if (open) {
        rawClose = `"${open[1]}`;
        mode = "string";
        quote = { open: '"', close: rawClose, multi: true, escape: false };
        quoteAt = i;
        line.code += '"';
        i += open[0].length;
        continue;
      }
    }
    if (profile.rustChars && ch === "'") {
      const lit = /^'(?:\\(?:u\{[0-9a-fA-F]{1,6}\}|x[0-9a-fA-F]{2}|.)|[^\\'\n])'/.exec(text.slice(i, i + 12));
      i += lit ? lit[0].length : 1;
      line.code += lit ? "''" : "'";
      lastSig = "0";
      continue;
    }
    if (profile.digitSep && ch === "'" && /[0-9A-Za-z]/.test(text[i - 1] || "") && /[0-9A-Fa-f]/.test(text[i + 1] || "")) {
      i += 1;
      continue;
    }
    //: C#'s verbatim strings, `@"…"`, where `""` is a quote and a line
    //: break is content.
    if (profile.verbatimCs && (startsWithAt('@"', i) || startsWithAt('$@"', i) || startsWithAt('@$"', i))) {
      const len = text[i] === "@" && text[i + 1] === '"' ? 2 : 3;
      mode = "string";
      quote = { open: '"', close: '"', multi: true, escape: false, doubled: true };
      quoteAt = i;
      line.code += '"';
      i += len;
      continue;
    }
    if (profile.heredoc && ch === "<") {
      const doc = profile.heredoc.exec(text.slice(i, i + 80));
      if (doc) {
        heredoc = doc[2];
        line.code += "<<";
        i += doc[0].length;
        continue;
      }
    }
    const opened = profile.quotes.find((qq) => startsWithAt(qq.open, i));
    if (opened) {
      mode = "string";
      quote = profile.template && opened.open === "`" ? { ...opened, template: true } : opened;
      quoteAt = i;
      line.code += opened.open;
      i += opened.open.length;
      continue;
    }
    //: A JavaScript regex literal, whose brackets and quotes are not code.
    //: A `/` is a regex where a value may start: after an operator, an
    //: opener, a comma, a keyword that takes a value, or at the start.
    if (profile.regex && ch === "/" && (!lastSig || "(,=:[!&|?{};+-*%<>~^".includes(lastSig) ||
      /^(return|typeof|case|do|else|in|of|new|delete|void|throw|yield|await)$/.test(lastWord))) {
      let j = i + 1;
      let inClass = false;
      let ok = false;
      while (j < n && text[j] !== "\n") {
        const c = text[j];
        if (c === "\\") {
          j += 2;
          continue;
        }
        if (c === "[") inClass = true;
        else if (c === "]") inClass = false;
        else if (c === "/" && !inClass) {
          ok = true;
          break;
        }
        j += 1;
      }
      if (ok) {
        j += 1;
        while (j < n && /[a-z]/i.test(text[j])) j += 1;
        line.code += "/r/";
        lastSig = "0";
        lastWord = "";
        i = j;
        continue;
      }
    }
    if (DOC_CODE_OPEN[ch]) {
      push(ch, i);
      line.code += ch;
      lastSig = ch;
      lastWord = "";
      i += 1;
      continue;
    }
    if (DOC_CODE_CLOSE[ch]) {
      const popped = close(ch, i);
      line.code += ch;
      lastSig = ch;
      lastWord = "";
      if (popped && popped.template) {
        quote = popped.template;
        mode = "string";
        quoteAt = i;
      }
      i += 1;
      continue;
    }
    const word = /^[A-Za-z_$][\w$]*/.exec(text.slice(i, i + 64));
    if (word) {
      line.code += word[0];
      lastSig = "a";
      lastWord = word[0];
      i += word[0].length;
      continue;
    }
    line.code += ch;
    lastSig = ch;
    lastWord = "";
    i += 1;
  }
  line.to = n;
  line.endsIn = mode === "code" ? null : mode;
  if (line.pending) {
    settle(n);
    line.blank = true;
  }
  if (mode === "string" && (quote.multi || rawClose)) {
    problems.push({ kind: "string", at: quoteAt, ch: quote.open, line: docCodeLineOf(text, quoteAt), eof: true });
  } else if (mode === "string") {
    problems.push({ kind: "string", at: quoteAt, ch: quote.open, line: lineNo });
  }
  if (mode === "comment") {
    problems.push({ kind: "comment", at: commentAt, ch: profile.block[0], line: docCodeLineOf(text, commentAt) });
  }
  while (stack.length) {
    const lost = stack.pop();
    problems.push({ kind: "unclosed", at: lost.at, ch: lost.ch, line: lost.line, before: n });
  }
  //: **One mistake, one report.** A string left open on its line swallows
  //: the `)` and `;` after it, so the `(` before it then reads as unclosed
  //: too: two underlines for one missing quote, and a second "fix" that
  //: would add a bracket the code never lacked. The string is the cause, so
  //: a bracket opened earlier on the same line is not reported beside it.
  const open = problems.filter((p) => p.kind === "string");
  const kept = problems.filter((p) => !(p.kind === "unclosed" && open.some((s) => s.line === p.line && p.at < s.at)));
  kept.sort((a, b) => a.at - b.at);
  return { lines, problems: kept, profile };
}

//: The 0-based line an offset is on.
function docCodeLineOf(text, at) {
  let count = 0;
  for (let k = text.indexOf("\n"); k !== -1 && k < at; k = text.indexOf("\n", k + 1)) count += 1;
  return count;
}

//: **How deep a new line belongs, for Enter and for a typed closer.**
//: `before` is everything above the line, `lineText` the text that will be
//: on it; `null` means the line is inside a string or a comment and is not
//: this function's to place, which hands the choice back to the editor
//: (it keeps the line above's indent, which is what a comment wants).
function docCodeIndentLevel(before, lineText, ext) {
  const joined = before && !before.endsWith("\n") ? `${before}\n${lineText}` : `${before}${lineText}`;
  const scan = docCodeScan(joined, ext);
  const last = scan.lines[scan.lines.length - 1];
  return last ? last.level : null;
}

//: The file types whose indentation is the brackets' business, so the
//: formatter re-indents them. Everything else with a profile has its
//: whitespace tidied and its indentation left exactly as written: Python's
//: and YAML's indentation *is* their syntax, and shell, SQL, Ruby, TOML and
//: INI have no bracket structure an indent could be derived from.
const DOC_FORMAT_REINDENT = new Set(["c", "cpp", "cs", "java", "kt", "go", "rs", "swift", "php", "js", "ts", "css", "r"]);

//: What a scanner problem says, in words, for a toast or an underline.
function docCodeProblemMessage(problem) {
  const q = (ch) => `“${ch}”`;
  switch (problem.kind) {
    case "unclosed": return `This ${q(problem.ch)} is never closed`;
    case "stray":
      return problem.expect
        ? `Expected ${q(problem.expect)} here, found ${q(problem.ch)}`
        : `Nothing is open for this ${q(problem.ch)} to close`;
    case "string": return "This string is never closed";
    case "comment": return "This comment is never closed";
    default: return "This does not parse";
  }
}

//: **Format: the brackets decide the indentation, and nothing else moves.**
//: `unit` is the file type's indent (four spaces, two, or a tab). `range`,
//: when given, is the first and last 0-based line to touch, which is how
//: "format the selection" is the same function as "format the document".
//:
//: What it does to each line, and only this:
//:
//: - a code line gets `level` units of indent in place of whatever it had
//:   (for the types in `DOC_FORMAT_REINDENT`);
//: - trailing spaces and tabs go, unless the line ends inside a string,
//:   where they are the string's, or ends in a backslash, where removing
//:   them would turn the next line into a continuation;
//: - a line that is only whitespace becomes empty;
//: - a line inside a block comment moves by exactly as much as the line the
//:   comment opened on, so a ` * ` column stays under its `/*`;
//: - a line inside a string (a template literal, a heredoc, a raw string)
//:   is not touched at all, not its indent and not its end;
//: - the document ends in exactly one line break (whole-document only).
//:
//: It never adds, removes or reorders a token, which is the whole of what
//: "conservative" means here, and it refuses outright when the brackets or
//: strings do not balance, because a re-indent computed from a structure
//: that is not there would scatter the text rather than tidy it.
function docFormatCodeText(text, ext, unit, range = null) {
  const scan = docCodeScan(text, ext);
  if (!scan.profile) return { error: `There is no formatter for .${ext} files yet.` };
  if (scan.problems.length) {
    //: The cause before its consequences: an open string or comment
    //: explains the brackets after it, not the other way round.
    const first = scan.problems.find((p) => p.kind === "string" || p.kind === "comment") ||
      scan.problems.find((p) => p.kind === "stray") || scan.problems[0];
    return { error: `Not formatted: line ${first.line + 1}, ${docCodeProblemMessage(first).toLowerCase()}.`, problem: first };
  }
  const reindent = DOC_FORMAT_REINDENT.has(ext);
  const lines = text.split("\n");
  const from = range ? Math.max(0, range[0]) : 0;
  const to = range ? Math.min(lines.length - 1, range[1]) : lines.length - 1;
  const oldLead = [];
  const newLead = [];
  const keep = ext === "yaml" ? docYamlBlockLines(lines) : null;
  const out = lines.map((raw, k) => {
    const info = scan.lines[k] || { level: null, startsIn: null, endsIn: null };
    if (keep && keep.has(k)) return raw;
    const lead = /^[ \t]*/.exec(raw)[0];
    oldLead[k] = lead;
    newLead[k] = lead;
    if (k < from || k > to) return raw;
    let head = lead;
    let body = raw.slice(lead.length);
    if (info.startsIn === "string") {
      //: The string's line: its start is content, whatever it looks like.
      head = "";
      body = raw;
    } else if (info.startsIn === "comment") {
      const open = info.commentOpenLine;
      if (open !== null && open !== undefined && oldLead[open] !== newLead[open] && lead.startsWith(oldLead[open])) {
        head = newLead[open] + lead.slice(oldLead[open].length);
      }
    } else if (reindent && info.level !== null && info.startsIn === null) {
      head = unit.repeat(info.level);
    }
    if (info.endsIn !== "string") {
      const trimmed = body.replace(/[ \t]+$/, "");
      if (!trimmed.endsWith("\\")) body = trimmed;
    }
    if (!body) head = "";
    newLead[k] = info.startsIn === "string" ? lead : head;
    return head + body;
  });
  let result = out.join("\n");
  if (!range || to === lines.length - 1) {
    if (!range) result = result.replace(/\n*$/, "") + (result.trim() ? "\n" : "");
  }
  return { text: result, changed: result !== text };
}

//: HTML's elements that never hold anything, the ones whose end tag may be
//: left out (a `<li>` ends at the next `<li>`), and the ones whose text is
//: not markup at all.
const DOC_HTML_VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
  "param", "source", "track", "wbr"]);
const DOC_HTML_OPTIONAL = new Set(["li", "dt", "dd", "p", "tr", "td", "th", "option", "optgroup", "thead",
  "tbody", "tfoot", "colgroup", "caption", "rt", "rp", "html", "head", "body"]);
const DOC_HTML_RAW = new Set(["script", "style", "textarea", "pre", "title"]);
//: Opening one of these closes the element on the left of each pair, as a
//: browser's parser does, so a list written without `</li>` still nests.
const DOC_HTML_IMPLIED = {
  li: ["li"], dt: ["dt", "dd"], dd: ["dt", "dd"], tr: ["tr", "td", "th"], td: ["td", "th"], th: ["td", "th"],
  option: ["option"], optgroup: ["optgroup", "option"], thead: ["tbody", "tfoot", "tr", "td", "th"],
  tbody: ["thead", "tbody", "tr", "td", "th"], tfoot: ["thead", "tbody", "tr", "td", "th"],
};
const DOC_HTML_BLOCK = new Set(["address", "article", "aside", "blockquote", "div", "dl", "fieldset", "footer",
  "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section",
  "table", "ul", "figure", "details"]);

//: **HTML and XML, indented by their elements.** The same contract as
//: `docFormatCodeText` (only whitespace moves, the refusal when the
//: structure does not balance), with elements where the other has brackets:
//: a line sits one unit inside the element that holds it, a line that
//: starts by closing an element sits where that element opened. A line
//: that starts inside a comment, a tag whose attributes run across lines,
//: or the text of a `<pre>`, `<script>`, `<style>` or `<textarea>` is not
//: touched, because its leading spaces are part of what it is.
function docFormatMarkupText(text, ext, unit, range = null) {
  const html = ext === "html";
  const lines = text.split("\n");
  const levels = [];
  const verbatim = [];
  //: Whether a line *ends* inside something whose spaces are content (a
  //: `<pre>`, a comment, an attribute value), so its trailing spaces stay.
  const endsInside = [];
  //: For a line inside a comment or a script, the line whose move it follows.
  const shiftWith = [];
  let shiftFrom = -1;
  const stack = [];
  let tagInHand = null;
  let mode = "text";
  let rawEnd = "";
  let i = 0;
  let lineNo = 0;
  let pending = true;
  let lastPopped = null;
  let lineLevel = 0;
  const fail = (message) => ({ error: `Not formatted: line ${lineNo + 1}, ${message}.` });
  const settle = () => {
    if (!pending) return;
    pending = false;
    lineLevel = lastPopped ? lastPopped.lineLevel : stack.length ? stack[stack.length - 1].inner : 0;
    levels[lineNo] = lineLevel;
  };
  const popTo = (name) => {
    let k = stack.length - 1;
    while (k >= 0 && stack[k].name !== name) {
      if (!html || !DOC_HTML_OPTIONAL.has(stack[k].name)) return null;
      k -= 1;
    }
    if (k < 0) return null;
    const frame = stack[k];
    stack.length = k;
    return frame;
  };
  verbatim[0] = false;
  while (i < text.length) {
    const ch = text[i];
    if (ch === "\n") {
      if (pending) settle();
      endsInside[lineNo] = mode !== "text";
      i += 1;
      lineNo += 1;
      pending = mode === "text";
      lastPopped = null;
      verbatim[lineNo] = mode !== "text";
      shiftWith[lineNo] = mode === "comment" || mode === "tag" || (mode === "raw" && shiftFrom >= 0) ? shiftFrom : -1;
      //: A `</script>` or `</style>` that starts its line is markup again,
      //: and lines up with its `<script>` like any other end tag.
      if (mode === "raw" && shiftFrom >= 0 && text.slice(i, i + 200).trimStart().toLowerCase().startsWith(rawEnd)) {
        verbatim[lineNo] = false;
        shiftWith[lineNo] = -1;
        pending = true;
      }
      continue;
    }
    if (mode === "comment") {
      if (text.startsWith("-->", i)) {
        mode = "text";
        i += 3;
      } else i += 1;
      continue;
    }
    if (mode === "cdata") {
      if (text.startsWith("]]>", i)) {
        mode = "text";
        i += 3;
      } else i += 1;
      continue;
    }
    if (mode === "raw") {
      if (text.slice(i, i + rawEnd.length).toLowerCase() === rawEnd) {
        mode = "text";
        continue;
      }
      i += 1;
      continue;
    }
    if (mode === "tag") {
      //: Inside `<name …>`: quotes may hold a `>`.
      if (ch === '"' || ch === "'") {
        const close = text.indexOf(ch, i + 1);
        if (close === -1) return fail("an attribute's quote is never closed");
        //: A value that runs across lines: those lines are the value's.
        const crossed = (text.slice(i, close).match(/\n/g) || []).length;
        for (let k = 1; k <= crossed; k += 1) {
          verbatim[lineNo + k] = true;
          endsInside[lineNo + k - 1] = true;
        }
        lineNo += crossed;
        i = close + 1;
        continue;
      }
      if (ch === ">") {
        mode = "text";
        const tag = tagInHand;
        tagInHand = null;
        const selfClosed = text[i - 1] === "/";
        i += 1;
        if (tag && !selfClosed && !(html && DOC_HTML_VOID.has(tag.name))) {
          stack.push(tag);
          if (html && DOC_HTML_RAW.has(tag.name)) {
            mode = "raw";
            rawEnd = `</${tag.name}`;
            //: A script's or a style's lines move with their tag; a
            //: `<pre>`'s and a `<textarea>`'s spaces are their text.
            shiftFrom = tag.name === "script" || tag.name === "style" ? lineNo : -1;
          }
        }
        continue;
      }
      i += 1;
      continue;
    }
    // --- text ---
    if (ch === " " || ch === "\t" || ch === "\r") {
      i += 1;
      continue;
    }
    if (text.startsWith("<!--", i)) {
      settle();
      mode = "comment";
      shiftFrom = lineNo;
      i += 4;
      continue;
    }
    if (text.startsWith("<![CDATA[", i)) {
      settle();
      mode = "cdata";
      i += 9;
      continue;
    }
    if (text.startsWith("<!", i) || text.startsWith("<?", i)) {
      settle();
      const end = text.indexOf(">", i);
      if (end === -1) return fail("a declaration is never closed");
      i = end + 1;
      continue;
    }
    const close = /^<\/([A-Za-z][\w:.-]*)\s*>/.exec(text.slice(i, i + 200));
    if (close) {
      const name = html ? close[1].toLowerCase() : close[1];
      const frame = popTo(name);
      if (!frame) return fail(`nothing is open for “</${close[1]}>” to close`);
      if (pending) lastPopped = frame;
      i += close[0].length;
      continue;
    }
    const open = /^<([A-Za-z][\w:.-]*)/.exec(text.slice(i, i + 200));
    if (open) {
      const name = html ? open[1].toLowerCase() : open[1];
      if (html) {
        //: What a browser closes for you before this element opens.
        const implied = DOC_HTML_IMPLIED[name] || [];
        while (stack.length && (implied.includes(stack[stack.length - 1].name) ||
          (DOC_HTML_BLOCK.has(name) && stack[stack.length - 1].name === "p"))) {
          const frame = stack.pop();
          if (pending) lastPopped = frame;
        }
      }
      settle();
      tagInHand = { name, lineLevel, inner: lineLevel + 1 };
      shiftFrom = lineNo;
      mode = "tag";
      i += open[0].length;
      continue;
    }
    settle();
    i += 1;
  }
  if (pending) settle();
  endsInside[lineNo] = mode !== "text";
  if (mode === "tag") return fail("a tag is never closed");
  if (mode === "comment") return fail("a comment is never closed");
  const left = stack.filter((frame) => !(html && DOC_HTML_OPTIONAL.has(frame.name)));
  if (left.length) {
    return { error: `Not formatted: “<${left[left.length - 1].name}>” is never closed.` };
  }
  const from = range ? Math.max(0, range[0]) : 0;
  const to = range ? Math.min(lines.length - 1, range[1]) : lines.length - 1;
  const oldLead = [];
  const newLead = [];
  const out = lines.map((raw, k) => {
    const lead = /^[ \t]*/.exec(raw)[0];
    oldLead[k] = lead;
    newLead[k] = lead;
    if (k < from || k > to) return raw;
    if (verbatim[k]) {
      const open = shiftWith[k];
      if (open >= 0 && oldLead[open] !== newLead[open] && lead.startsWith(oldLead[open]) && raw.trim()) {
        newLead[k] = newLead[open] + lead.slice(oldLead[open].length);
        return newLead[k] + raw.slice(lead.length);
      }
      return raw;
    }
    const body = endsInside[k] ? raw.replace(/^[ \t]+/, "") : raw.trim();
    newLead[k] = body ? unit.repeat(levels[k] || 0) : "";
    return newLead[k] + body;
  });
  let result = out.join("\n");
  if (!range) result = result.replace(/\n*$/, "") + (result.trim() ? "\n" : "");
  return { text: result, changed: result !== text };
}

//: The lines of a YAML block scalar (`key: |`, `- >-`): every line more
//: indented than its key, blank ones included, is the value's text, and a
//: `|` value keeps its trailing spaces, so none of it is touched.
function docYamlBlockLines(lines) {
  const keep = new Set();
  let owner = -1;
  lines.forEach((raw, k) => {
    const indent = /^ */.exec(raw)[0].length;
    if (owner >= 0) {
      if (!raw.trim() || indent > owner) {
        keep.add(k);
        return;
      }
      owner = -1;
    }
    if (/(^|[:-])\s*[|>][+-]?\d*[+-]?\s*(#.*)?$/.test(raw)) owner = indent;
  });
  return keep;
}

//: **JSON, re-printed from its own tokens rather than from `JSON.parse`.**
//: Parsing and stringifying would be shorter and would quietly change the
//: data: a number past 2^53 loses digits (`12345678901234567890` comes back
//: as `12345678901234567000`), `1.0` becomes `1`, `1e5` becomes `100000`, a
//: repeated key loses all but its last value, and `é` becomes `é`.
//: This keeps every token exactly as written and only decides the space
//: between them, in `JSON.stringify`'s layout. `JSON.parse` still runs
//: first, as the gate: a text that is not JSON is refused, not guessed at.
//: `base` is prepended to every line after the first, which is how a
//: selection nested inside a larger document keeps its place.
function docFormatJsonText(text, unit, base = "", whole = true) {
  const body = text.trim();
  if (!body) return { text, changed: false };
  try {
    JSON.parse(body);
  } catch {
    const found = docJsonErrorAt(body);
    const line = found ? docCodeLineOf(body, found.at) + 1 : null;
    return { error: `Not formatted: ${found ? `line ${line}, ${found.message.toLowerCase()}` : "this is not valid JSON"}.` };
  }
  const tokens = [];
  for (let i = 0; i < body.length;) {
    const ch = body[i];
    if (" \t\n\r".includes(ch)) {
      i += 1;
    } else if (ch === '"') {
      let j = i + 1;
      while (j < body.length && body[j] !== '"') j += body[j] === "\\" ? 2 : 1;
      tokens.push(body.slice(i, j + 1));
      i = j + 1;
    } else if ("{}[],:".includes(ch)) {
      tokens.push(ch);
      i += 1;
    } else {
      const word = /^[^\s{}[\],:"]+/.exec(body.slice(i))[0];
      tokens.push(word);
      i += word.length;
    }
  }
  let out = "";
  let depth = 0;
  const pad = () => `\n${base}${unit.repeat(depth)}`;
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t === "{" || t === "[") {
      const shut = t === "{" ? "}" : "]";
      if (tokens[k + 1] === shut) {
        out += t + shut;
        k += 1;
        continue;
      }
      depth += 1;
      out += t + pad();
    } else if (t === "}" || t === "]") {
      depth -= 1;
      out += pad() + t;
    } else if (t === ",") {
      out += `,${pad()}`;
    } else if (t === ":") {
      out += ": ";
    } else {
      out += t;
    }
  }
  //: The whole document ends in one line break; a selection keeps the space
  //: it had around it, so the lines on either side do not move.
  const final = whole ? `${out}\n` : `${/^\s*/.exec(text)[0]}${out}${/\s*$/.exec(text)[0]}`;
  return { text: final, changed: final !== text };
}

//: **The quick fixes, as edits on the text.** Each problem the checks find
//: comes back as a diagnostic with the fixes that are certain enough to
//: offer: a fix here is a small, mechanical edit whose result can be stated
//: before it is made ("add the missing `}`"), never a guess at what the code
//: meant. Every fix is a list of `{from, to, insert}` against the text it
//: was computed from, so the editor recomputes them against the text at the
//: moment one is chosen rather than applying offsets that have gone stale.
//:
//: `key` names the problem so the editor can find the same one again after
//: the text has moved.

//: Where a missing closer goes on a line: before the run of `;` and `{` the
//: line ends with, and before its trailing comment, so `foo(a;` becomes
//: `foo(a);` and `if (x > 1 {` becomes `if (x > 1) {`.
function docCodeInsertPoint(text, info, floor) {
  let end = info.commentAt !== undefined ? info.commentAt : info.to;
  while (end > info.from && /[ \t]/.test(text[end - 1])) end -= 1;
  let at = end;
  while (at > info.from && /[;{ \t]/.test(text[at - 1])) at -= 1;
  if (at <= floor) at = end;
  return at;
}

function docCodeFixes(text, ext, unit) {
  const scan = docCodeScan(text, ext);
  const out = [];
  const q = (ch) => `“${ch}”`;
  for (const p of scan.problems.slice(0, 50)) {
    const info = scan.lines[p.line];
    const diag = {
      from: p.at,
      to: p.at + (p.ch ? p.ch.length : 1),
      severity: "error",
      message: docCodeProblemMessage(p),
      key: `${p.kind}:${p.ch}`,
      fixes: [],
    };
    if (p.kind === "stray") {
      if (p.expect) {
        diag.fixes.push({ name: `Change it to ${q(p.expect)}`, edits: [{ from: p.at, to: p.at + 1, insert: p.expect }] });
      }
      diag.fixes.push({ name: `Remove this ${q(p.ch)}`, edits: [{ from: p.at, to: p.at + 1, insert: "" }] });
    } else if (p.kind === "unclosed") {
      const shut = DOC_CODE_OPEN[p.ch];
      const level = info.level !== null ? info.level : 0;
      const rest = text.slice(p.at + 1, info.commentAt !== undefined ? info.commentAt : info.to);
      let edit;
      if (p.ch !== "{" && /\{[ \t]*$/.test(rest)) {
        //: `if (x > 1 {`: the bracket closes where the block opens.
        const at = docCodeInsertPoint(text, info, p.at);
        edit = { from: at, to: at, insert: shut };
      } else {
        //: Otherwise after the last code before whatever gave it away: the
        //: closer that closed its parent, or the end of the file. A brace
        //: gets a line of its own at the opener's indent; a bracket that
        //: spans lines does too; a parenthesis closes inline, before the
        //: `;` its statement ends with.
        const end = docCodeLastCodeBefore(scan, text, p.before, p.line, p.at);
        const multi = docCodeLineOf(text, end) > p.line;
        if (p.ch === "{" || (p.ch === "[" && multi)) {
          edit = { from: end, to: end, insert: `\n${unit.repeat(level)}${shut}` };
        } else {
          let at = end;
          while (at > p.at + 1 && /[;{ \t]/.test(text[at - 1])) at -= 1;
          edit = { from: at, to: at, insert: shut };
        }
      }
      diag.fixes.push({ name: `Add the missing ${q(shut)}`, edits: [edit] });
    } else if (p.kind === "string" && !p.eof) {
      const at = docCodeInsertPointForString(text, info, p.at);
      diag.fixes.push({ name: "Close the string", edits: [{ from: at, to: at, insert: p.ch }] });
    } else if (p.kind === "comment") {
      const end = text.replace(/\s+$/, "").length;
      diag.fixes.push({ name: "Close the comment", edits: [{ from: end, to: end, insert: ` ${scan.profile.block[1]}` }] });
    }
    out.push(diag);
  }
  return out;
}

//: The offset just after the last code at or before `before`, looking no
//: higher than line `minLine` and no earlier than the opener at `floor`.
//: Comments and blank lines are stepped over, so a fix never lands inside a
//: `// note` at the end of the line it belongs on.
function docCodeLastCodeBefore(scan, text, before, minLine, floor) {
  for (let k = docCodeLineOf(text, before); k >= minLine; k -= 1) {
    const info = scan.lines[k];
    if (!info || (info.startsIn && k !== minLine)) continue;
    let end = info.commentAt !== undefined ? info.commentAt : info.to;
    if (before < end) end = before;
    const start = k === minLine ? floor + 1 : info.from;
    while (end > start && /[ \t]/.test(text[end - 1])) end -= 1;
    if (end > start) return end;
  }
  return floor + 1;
}

//: A string left open on its line closes before the `);` or `;` the line
//: ends with, which is where it was meant to end in every case that is not
//: a string with a bracket inside it: `printf("hi);` becomes
//: `printf("hi");`.
function docCodeInsertPointForString(text, info, openAt) {
  let end = info.to;
  while (end > openAt + 1 && /[ \t]/.test(text[end - 1])) end -= 1;
  let at = end;
  while (at > openAt + 1 && /[;,)\] \t]/.test(text[at - 1])) at -= 1;
  return at;
}

//: The JSON checker's own messages, with the fixes that follow from each.
//: `found` is `docJsonErrorAt`'s answer for the text.
function docJsonFixes(text, found, unit) {
  const fixes = [];
  if (!found) return fixes;
  const at = found.at;
  const back = (from) => {
    let k = from;
    while (k > 0 && " \t\n\r".includes(text[k - 1])) k -= 1;
    return k;
  };
  if (found.message === "A comma with nothing after it") {
    const comma = back(at) - 1;
    if (text[comma] === ",") fixes.push({ name: "Remove the trailing comma", edits: [{ from: comma, to: comma + 1, insert: "" }] });
  } else if (/^Expected a comma/.test(found.message) && at < text.length && /["{[\-0-9tfn]/.test(text[at])) {
    const end = back(at);
    fixes.push({ name: "Add the missing comma", edits: [{ from: end, to: end, insert: "," }] });
  } else if (found.message === "Expected a property name in double quotes") {
    const single = /^'([^'"\\\n]*)'/.exec(text.slice(at));
    const bare = /^([A-Za-z_$][\w$]*)(?=\s*:)/.exec(text.slice(at));
    if (single) {
      fixes.push({ name: "Use double quotes", edits: [{ from: at, to: at + single[0].length, insert: `"${single[1]}"` }] });
    } else if (bare) {
      fixes.push({ name: "Put the name in double quotes", edits: [{ from: at, to: at + bare[0].length, insert: `"${bare[1]}"` }] });
    }
  } else if (found.message === "Expected a value" && text[at] === "'") {
    const single = /^'([^'"\\\n]*)'/.exec(text.slice(at));
    if (single) fixes.push({ name: "Use double quotes", edits: [{ from: at, to: at + single[0].length, insert: `"${single[1]}"` }] });
  }
  //: At the end of the text with brackets still open: close them all, each
  //: on its own line, innermost first.
  if (at >= text.trimEnd().length) {
    const scan = docCodeScan(text, "json");
    const open = scan.problems.filter((p) => p.kind === "unclosed").sort((a, b) => b.at - a.at);
    if (open.length && !scan.problems.some((p) => p.kind !== "unclosed")) {
      let end = text.trimEnd().length;
      let insert = "";
      if (text[end - 1] === ",") {
        end -= 1;
        insert = "";
      }
      const from = end;
      for (const p of open) {
        const level = Math.max(0, (scan.lines[p.line] && scan.lines[p.line].level) || 0);
        insert += `\n${unit.repeat(level)}${DOC_CODE_OPEN[p.ch]}`;
      }
      fixes.push({ name: "Close what is still open", edits: [{ from, to: text.trimEnd().length, insert }] });
    }
  }
  return fixes;
}

//: **Python's missing colon.** The compiler says "expected ':'" and points
//: at the line; the fix is the colon, at the end of the line's code and
//: before any comment, and only on a line that opens a block.
function docPythonColonFix(text, lineNo) {
  const lines = text.split("\n");
  const raw = lines[lineNo - 1];
  if (raw === undefined) return null;
  const head = /^\s*(async\s+)?(def|class|if|elif|else|for|while|try|except|finally|with|match|case)\b/;
  if (!head.test(raw)) return null;
  const scan = docCodeScan(raw, "py");
  const info = scan.lines[0];
  let end = info.commentAt !== undefined ? info.commentAt : raw.length;
  while (end > 0 && /[ \t]/.test(raw[end - 1])) end -= 1;
  if (raw[end - 1] === ":") return null;
  let from = 0;
  for (let k = 0; k < lineNo - 1; k += 1) from += lines[k].length + 1;
  return { name: "Add the missing colon", edits: [{ from: from + end, to: from + end, insert: ":" }] };
}

//: **Indentation that mixes tabs and spaces**, reported only where the file
//: really is mixed: a line whose indent holds the character the rest of the
//: file does not use. A file indented wholly with tabs is somebody's
//: choice, not a mistake, and is left alone. Offered for every code type,
//: as a note rather than an error, with the conversion of this line and of
//: every line as its two fixes. `tabWidth` is how many columns a tab counts
//: for when it becomes spaces.
function docIndentMixFixes(text, unit, tabWidth, ext = null) {
  const lines = text.split("\n");
  const wantTabs = unit === "\t";
  const leads = lines.map((l) => /^[ \t]*/.exec(l)[0]);
  //: A line inside a string or a comment is somebody's content.
  const scan = ext ? docCodeScan(text, ext) : null;
  const content = (k) => Boolean(scan && scan.lines[k] && scan.lines[k].startsIn);
  const good = leads.some((lead, k) => lead && !content(k) && !lead.includes(wantTabs ? " " : "\t"));
  if (!good) return [];
  const convert = (lead) => {
    let cols = 0;
    for (const ch of lead) cols = ch === "\t" ? cols + tabWidth - (cols % tabWidth) : cols + 1;
    return wantTabs ? "\t".repeat(Math.floor(cols / tabWidth)) + " ".repeat(cols % tabWidth) : " ".repeat(cols);
  };
  const bad = [];
  let at = 0;
  lines.forEach((line, k) => {
    const lead = leads[k];
    //: In a tab-indented file, spaces *after* the tabs are alignment (Go's
    //: own formatter writes them); spaces before a tab, or a whole indent of
    //: spaces, are the mix.
    const wrong = wantTabs
      ? / \t/.test(lead) || (/^ +$/.test(lead) && lead.length >= tabWidth)
      : lead.includes("\t");
    if (wrong && line.trim() && !content(k)) bad.push({ from: at, to: at + lead.length, lead });
    at += line.length + 1;
  });
  const all = bad.map((b) => ({ from: b.from, to: b.to, insert: convert(b.lead) }));
  const word = wantTabs ? "tabs" : "spaces";
  return bad.slice(0, 50).map((b) => ({
    from: b.from,
    to: Math.max(b.to, b.from + 1),
    severity: "info",
    message: wantTabs
      ? "Indented with spaces, where the rest of the file uses tabs"
      : "Indented with tabs, where the rest of the file uses spaces",
    key: "indent-mix",
    fixes: [
      { name: `Convert this line to ${word}`, edits: [{ from: b.from, to: b.to, insert: convert(b.lead) }] },
      ...(bad.length > 1 ? [{ name: `Convert every line to ${word}`, edits: all }] : []),
    ],
  }));
}
// DOC-CODE-END

// --- the editor half: pairs, Enter and the indent unit ----------------------
//
// **Pairs.** CodeMirror's own `closeBrackets`, which the bundle has always
// carried and this editor never mounted: typing `"` gives `""` with the caret
// between, `(` `[` `{` likewise, typing the closer it inserted steps over it,
// Backspace between an empty pair takes both, and a pair typed over a
// selection wraps it. Which characters pair is the language's own answer:
// the JavaScript, TypeScript, Python, CSS and HTML packages each declare
// theirs (backticks, triple quotes, string prefixes); for the rest this says,
// through the same language-data facet, so a Rust lifetime `'a` is not closed
// into `'a'` and Go's raw-string backtick is.
//
// **Enter.** The same packages indent from their grammars. The other
// seventeen types have a line-at-a-time highlighter, or nothing, and
// CodeMirror's fallback is "copy the line above's indent", which is why
// `{` then Enter in a C file gave `{`, a blank line at the same depth, and
// `}` beside the caret. `docCodeIndentAt` answers from the structure scan
// instead, so the three-line split every code editor does (`{`, the caret
// one unit in, `}` back at the opener's depth) happens for every code type,
// and a typed `}` snaps back to its opener through `indentOnInput`.
//
// **Tab** is unchanged, on purpose: `indentDocSelection` already indents the
// caret or the selected lines by the file type's own unit and Shift+Tab takes
// it back, in code and prose alike, with Escape then Tab as the way out of
// the editor (`docTabEscapes`). The unit below is that same `type.indent`, so
// Enter, Tab and the formatter all indent by one amount.

//: The types whose indentation this file answers, because the bundle has no
//: grammar for them that could: every code type except the five with Lezer
//: grammars (and YAML and JSON, whose packages indent) and Ruby and XML,
//: whose legacy modes do indent by their own keywords and tags.
const DOC_CODE_INDENT_OWN = new Set(["c", "cpp", "cs", "java", "kt", "go", "rs", "swift", "php", "r", "sql",
  "bash", "toml", "ini"]);

//: The packages that bring their own pairs and their own indent-on-input.
const DOC_CODE_NATIVE = new Set(["js", "ts", "py", "css", "html"]);

//: What auto-closes, for the types whose package does not say. A single
//: quote is a lifetime in Rust and not a string in Swift; a backtick is a raw
//: string in Go, a command in shell and an identifier in SQL and R.
function docCodePairs(ext) {
  if (ext === "rs" || ext === "swift") return ["(", "[", "{", '"'];
  if (ext === "json") return ["[", "{", '"'];
  if (["go", "bash", "sql", "r", "rb"].includes(ext)) return ["(", "[", "{", "'", '"', "`"];
  return ["(", "[", "{", "'", '"'];
}

//: The indent service. Asked for a line's indent in columns; answers from the
//: structure scan for the types above and passes (undefined) for the rest, so
//: a grammar that knows better is never overruled. `null` means "inside a
//: string or a comment", where the editor then keeps the line above's indent.
function docCodeIndentAt(cx, pos) {
  const ext = docFileType().ext;
  if (!DOC_CODE_INDENT_OWN.has(ext) || docView === "plain") return undefined;
  const doc = cx.state.doc;
  //: The scan is linear, measured at a few milliseconds for a long file;
  //: past the checker's own cap it is not worth a keystroke.
  if (doc.length > DOC_CHECK_MAX_CHARS) return undefined;
  const level = docCodeIndentLevel(doc.sliceString(0, pos), cx.textAfterPos(pos, 1), ext);
  if (level === null || level === undefined) return null;
  return level * cx.unit;
}

//: Pairs, Enter and the unit, for the open code document. Part of
//: `docCodeTools`, so it is in the same compartment and follows the file
//: type and Plain the same way the diagnostics do.
function docCodeEditing(CM, type) {
  const ext = type.ext;
  const parts = [
    CM.language.indentUnit.of(type.indent || "  "),
    CM.autocomplete.closeBrackets(),
    CM.view.keymap.of([
      ...CM.autocomplete.closeBracketsKeymap,
      //: VS Code's chord for Format Document, which formats the selection
      //: when there is one, as the dock's button does.
      { key: "Shift-Alt-f", run: () => { docFormatCode("auto"); return true; } },
      //: VS Code's word-wrap toggle (INBOX 402); free in the registry.
      { key: "Alt-z", run: () => { docToggleCodeDraw("codeWrap"); return true; } },
      //: Run (INBOX 404). Not F5, which reloads the page in a browser, and
      //: not Ctrl+Alt+R, which the registry gives to a forced reload.
      { key: "Mod-Shift-Enter", run: () => { if (!docRunnable(docFileType())) return false; docRunCode(); return true; } },
      //: VS Code's own keys for these two (INBOX 404), free in the registry.
      { key: "F12", run: () => docGoToDefinition() },
      { key: "Shift-F12", run: () => docShowReferences() },
      //: The quick fixes at the caret, on the prose menu's own chord, and the
      //: problems one at a time on the prose findings' own keys.
      { key: "Alt-Enter", run: () => docOpenCodeFixes() },
      { key: "F8", run: CM.lint.nextDiagnostic },
      { key: "Shift-F8", run: CM.lint.previousDiagnostic },
    ]),
  ];
  if (!DOC_CODE_NATIVE.has(ext)) {
    const data = [{ closeBrackets: { brackets: docCodePairs(ext) }, indentOnInput: /^\s*[}\])]$/ }];
    parts.push(CM.state.EditorState.languageData.of(() => data));
  }
  if (DOC_CODE_INDENT_OWN.has(ext)) parts.push(CM.language.indentService.of(docCodeIndentAt));
  return parts;
}

// --- Format: the dock button, Shift+Alt+F and the palette -------------------
//
// One command with two scopes, VS Code's: with text selected it formats the
// lines the selection touches, with nothing selected the whole document. The
// dock's Format button, Shift+Alt+F and the palette's row all call
// `docFormatCode`, and the Alt+Enter menu offers both scopes by name.
//
// **Refused before it is attempted** wherever the file does not parse,
// because the layout is computed from structure and a structure that is not
// there gives a layout that scatters the text: the Lezer tree's errors for
// JavaScript, TypeScript and CSS, the server's own check for Python, TOML and
// YAML (the same `POST /documents/check-syntax` the underline uses, so no new
// endpoint), `JSON.parse` for JSON, and the scan's own balance for the rest.
// A refusal says which line and why, in a toast, and changes nothing.
//
// **One undo step.** The result goes in as one transaction, isolated in the
// history, and only the lines that changed are touched, so the caret and the
// scroll position stay where they were.

//: Whether a JavaScript file's tree holds JSX. The structure scan reads
//: JSX's text as code (an apostrophe in `<p>Don't</p>` would open a
//: string), so neither the formatter nor the bracket fixes go near one.
function docTreeHasJsx(CM, state) {
  const tree = CM.language.ensureSyntaxTree(state, state.doc.length, 200) || CM.language.syntaxTree(state);
  let jsx = false;
  tree.iterate({
    enter: (node) => {
      if (/^JSX/.test(node.name)) jsx = true;
      return !jsx;
    },
  });
  return jsx;
}

//: The first line the Lezer tree could not place, or null. JavaScript with
//: JSX in it is parsed (the package is mounted with `jsx: true`) and then
//: refused by name, because nothing here lays out markup inside code.
function docFormatTreeRefusal(CM, state, ext) {
  if (ext === "js" && docTreeHasJsx(CM, state)) {
    return "Not formatted: this file has JSX in it, which the formatter leaves as written.";
  }
  const found = docTreeDiagnostics(CM, state);
  if (!found.length) return null;
  const line = state.doc.lineAt(found[0].from).number;
  return `Not formatted: line ${line} does not parse (${found[0].message.toLowerCase()}).`;
}

//: The server's word on a Python, TOML or YAML file, or null when it has no
//: complaint or could not be asked. Could-not-ask formats anyway: the scan
//: itself still refuses an open string, and whitespace outside strings is
//: all these three ever have changed.
async function docFormatRemoteRefusal(ext, text) {
  if (!DOC_CHECK_REMOTE.has(ext) || !text.trim() || text.length > DOC_CHECK_MAX_CHARS) return null;
  try {
    const response = await api("/documents/check-syntax", {
      method: "POST",
      body: JSON.stringify({ language: ext, text }),
      silent: true,
      readOnly: true,
    });
    const found = await response.json();
    const error = (Array.isArray(found) ? found : []).find((d) => d.severity !== "info" && d.severity !== "warning");
    return error ? `Not formatted: line ${error.line}, ${String(error.message || "does not parse").replace(/\.$/, "")}.` : null;
  } catch {
    return null;
  }
}

//: The change set that turns `before` into `after`, line by line, touching
//: only what differs within each line. The formatter keeps the line count
//: everywhere but the end of the file, so lines are paired from the top and
//: whatever is left at the bottom is one change.
function docFormatChanges(before, after, offset = 0) {
  const a = before.split("\n");
  const b = after.split("\n");
  const changes = [];
  const diff = (x, y, at) => {
    if (x === y) return;
    let p = 0;
    while (p < x.length && p < y.length && x[p] === y[p]) p += 1;
    let s = 0;
    while (s < x.length - p && s < y.length - p && x[x.length - 1 - s] === y[y.length - 1 - s]) s += 1;
    changes.push({ from: at + p, to: at + x.length - s, insert: y.slice(p, y.length - s) });
  };
  const paired = a.length === b.length ? a.length : Math.min(a.length, b.length) - 1;
  let at = offset;
  for (let k = 0; k < paired; k += 1) {
    diff(a[k], b[k], at);
    at += a[k].length + 1;
  }
  if (paired < a.length) diff(a.slice(paired).join("\n"), b.slice(paired).join("\n"), at);
  return changes;
}

//: `scope` is "auto" (the selection if there is one, else the document),
//: "document" or "selection". Resolves to whether anything was done.
async function docFormatCode(scope = "auto") {
  const CM = window.CM6;
  const type = docFileType();
  const view = docCmView;
  if (type.previewable || ["txt", "csv"].includes(type.ext)) {
    toast("Formatting is for code documents.", "info");
    return false;
  }
  if (!view || !CM) {
    toast("Formatting needs the code editor, which has not loaded.", "info");
    return false;
  }
  const state = view.state;
  const text = docStr(state.doc);
  const sel = state.selection.main;
  const selection = scope === "selection" || (scope === "auto" && !sel.empty);
  if (selection && sel.empty) {
    toast("Select the lines to format first.", "info");
    return false;
  }
  const refusal = DOC_CHECK_TREE.has(type.ext)
    ? docFormatTreeRefusal(CM, state, type.ext)
    : await docFormatRemoteRefusal(type.ext, text);
  if (refusal) {
    toast(refusal, "info");
    return false;
  }
  const beautify = DOC_BEAUTIFY_TYPES.has(type.ext) && (await docLoadBeautify());
  //: The server check is a round trip, and so is the formatter's first
  //: load; typing during either would make the result a format of text
  //: that is no longer there.
  if (docCmView !== view || docStr(view.state.doc) !== text) {
    toast("The text changed while it was being checked. Format again.", "info");
    return false;
  }
  const unit = type.indent || "  ";
  const first = state.doc.lineAt(sel.from);
  //: A selection that ends at the very start of a line does not take that
  //: line with it, as in every editor's "indent the selected lines".
  const last = state.doc.lineAt(sel.to > sel.from && sel.to === state.doc.lineAt(sel.to).from ? sel.to - 1 : sel.to);
  const range = selection ? [first.number - 1, last.number - 1] : null;
  let result;
  let changes;
  if (type.ext === "json" && selection) {
    //: A JSON selection has to be a whole value on its own; its lines
    //: keep the indent of the line it starts on.
    const piece = state.sliceDoc(sel.from, sel.to);
    result = docFormatJsonText(piece, unit, /^[ \t]*/.exec(first.text)[0], false);
    if (result.error) result.error = result.error.replace("Not formatted:", "Not formatted, the selection is not a whole JSON value:");
    if (!result.error) changes = docFormatChanges(piece, result.text, sel.from);
  } else if (selection && beautify) {
    //: A selection of whole lines goes through js-beautify too (ledger 1565),
    //: at the indent level of the line it starts on and with no newline added
    //: at its end, so it drops back into the document where it came from.
    const piece = state.sliceDoc(first.from, last.to);
    const lead = /^[ \t]*/.exec(first.text)[0];
    const level = unit === "\t" ? lead.split("\t").length - 1 : Math.floor(lead.length / unit.length);
    result = docBeautifyText(piece, type.ext, unit, { level, endWithNewline: false });
    if (!result.error) changes = docFormatChanges(piece, result.text, first.from);
  } else {
    if (type.ext === "json") result = docFormatJsonText(text, unit);
    else if (beautify) result = docBeautifyText(text, type.ext, unit);
    else if (type.ext === "html" || type.ext === "xml") result = docFormatMarkupText(text, type.ext, unit, range);
    else result = docFormatCodeText(text, type.ext, unit, range);
    if (!result.error) changes = docFormatChanges(text, result.text);
  }
  if (result.error) {
    toast(result.error, "info");
    return false;
  }
  if (!changes.length) {
    toast(selection ? "The selection is already formatted." : "Already formatted.");
    return true;
  }
  view.dispatch({
    changes,
    annotations: [CM.commands.isolateHistory.of("full"), CM.state.Transaction.userEvent.of("format")],
  });
  toast(`${selection ? "Formatted the selection" : "Formatted the document"}. Ctrl+Z undoes it.`);
  return true;
}

// --- Quick fixes -------------------------------------------------------------
//
// "Recommended fixes to apply like the other autocorrect feature." The prose
// checker's shape, in code: the underline says where, hovering it says what
// and offers the fixes as buttons (CodeMirror's own lint tooltip, restyled in
// `docCmTheme`), and the keyboard reaches the same list with the prose menu's
// own chord, Alt+Enter, opening at the caret through the app's one
// menu-at-a-point recipe (`openMenuAtPoint`). F8 and Shift+F8 walk the
// problems, as they walk the prose findings.
//
// **Not Ctrl+.**, which is what VS Code binds: this app already gives that
// chord to "stop the answer being written" (app.js's shortcut registry), and
// taking it inside the editor would make the one shortcut whose whole value is
// being reachable in a hurry stop working exactly when a writer is in a code
// file. Alt+Enter is the chord the prose menu already uses for the same job,
// and JetBrains' for this one.
//
// **A fix is recomputed at the moment it is chosen.** The list was built
// against the text of the last check, up to 750ms and any number of
// keystrokes ago; applying its offsets then would edit the wrong place. So a
// fix carries only which check it came from, which problem and which fix,
// and `docCodeFixNow` asks that check again of the text as it is now and
// applies what it answers. When the problem has gone the fix says so and does
// nothing.

//: Which of the pure checks a diagnostic came from, so the fix can be asked
//: for again: "scan" (brackets, strings, comments), "json", "py-colon",
//: "indent-mix".
function docCodeFixNow(view, source, key, name, from) {
  const text = docStr(view.state.doc);
  const type = docFileType();
  const unit = type.indent || "  ";
  if (source === "py-colon") {
    const fix = docPythonColonFix(text, view.state.doc.lineAt(from).number);
    return fix && fix.name === name ? fix : null;
  }
  if (source === "json") {
    return docJsonFixes(text, docJsonErrorAt(text), unit).find((fix) => fix.name === name) || null;
  }
  const found = source === "indent-mix"
    ? docIndentMixFixes(text, unit, view.state.tabSize, type.ext)
    : docCodeFixes(text, type.ext, unit);
  const diag = found.find((d) => d.key === key && d.from === from);
  return diag ? diag.fixes.find((fix) => fix.name === name) || null : null;
}

function docApplyCodeFix(view, source, key, name, from) {
  const CM = window.CM6;
  const fix = CM && docCodeFixNow(view, source, key, name, from);
  if (!fix) {
    toast("That fix no longer applies: the text has changed since it was offered.", "info");
    return;
  }
  view.dispatch({
    changes: fix.edits,
    annotations: [CM.commands.isolateHistory.of("full"), CM.state.Transaction.userEvent.of("input.fix")],
  });
  view.focus();
}

//: A pure check's answer as CodeMirror diagnostics, each fix an action.
function docCodeActions(source, list) {
  return list.map((d) => ({
    from: d.from,
    to: d.to,
    severity: d.severity || "error",
    message: d.message,
    actions: (d.fixes || []).map((fix) => ({
      name: fix.name,
      apply: (view, from) => docApplyCodeFix(view, source, d.key, fix.name, from),
    })),
  }));
}

//: The quick-fix menu at the caret: the fixes for every problem under it,
//: then the two formats, so the one chord is also where "tidy this" lives.
function docOpenCodeFixes() {
  const CM = window.CM6;
  const view = docCmView;
  if (!CM || !view || typeof openMenuAtPoint !== "function") return false;
  const state = view.state;
  const pos = state.selection.main.head;
  const items = [];
  //: The problems under the caret, or failing that the ones on its line: a
  //: compiler puts "expected ':'" at the end of `def f(x)`, and a caret
  //: anywhere in that line is asking about it.
  const here = [];
  const line = state.doc.lineAt(pos);
  CM.lint.forEachDiagnostic(state, (d, from, to) => {
    if (from <= pos && pos <= to) here.push({ d, from, to, exact: true });
    else if (from <= line.to && to >= line.from) here.push({ d, from, to, exact: false });
  });
  const chosen = here.some((h) => h.exact) ? here.filter((h) => h.exact) : here;
  for (const { d, from, to } of chosen) {
    for (const action of d.actions || []) {
      items.push({
        group: "fix",
        label: `ph:wrench ${action.name}`,
        title: d.message,
        run: () => action.apply(view, from, to),
      });
    }
  }
  if (!items.length) {
    items.push({
      group: "fix",
      label: "ph:info No quick fix at the caret",
      title: "F8 goes to the next problem",
      disabled: true,
      run: () => toast("Nothing to fix at the caret. F8 goes to the next problem."),
    });
  }
  items.push({
    group: "format",
    label: "ph:brackets-curly Format the document",
    title: "Shift+Alt+F with nothing selected",
    run: () => docFormatCode("document"),
  });
  if (!state.selection.main.empty) {
    items.push({
      group: "format",
      label: "ph:brackets-curly Format the selection",
      title: "Shift+Alt+F with text selected",
      run: () => docFormatCode("selection"),
    });
  }
  const at = view.coordsAtPos(pos) || view.contentDOM.getBoundingClientRect();
  openMenuAtPoint(items, "Quick fixes", at.left, at.bottom);
  return true;
}

// -----------------------------------------------------------------------------
// A code file's keys on the phone (INBOX 1400 dogfood)
// -----------------------------------------------------------------------------
//
// A phone has no Tab key and buries the brackets two layers down, so a code
// file could not be indented or closed off with touch alone, and the bar at
// the thumb offered Bold, Italic and Heading for a Python file. The same bar
// (`#doc-phone-bar`, which already rides above the keyboard) carries these
// buttons instead of the markdown ones for a code file; `.doc-is-code` on the
// tab picks the half that shows (10-responsive.css). Each is one editor step,
// so Undo takes it back.

//: A pair wraps the selection or, with none, lands with the caret inside.
const DOC_CODE_KEY_PAIRS = new Set(["{}", "()", "[]", '""']);

function docCodeKeyPress(key) {
  if (key === "undo") return docUndo();
  if (key === "redo") return docRedo();
  const box = docSurface();
  if (!box) return;
  if (key === "tab" || key === "outdent") return indentDocSelection(box, key === "outdent");
  const start = box.selectionStart;
  const end = box.selectionEnd;
  const pair = DOC_CODE_KEY_PAIRS.has(key);
  const text = pair ? key[0] + box.value.slice(start, end) + key[1] : key;
  docUndoBreak();
  docReplaceRange(box, start, end, text);
  const caret = pair && start === end ? start + 1 : start + text.length;
  box.setSelectionRange(caret, caret);
  box.focus();
}

//: Pressed, a key must not take the focus: the keyboard would close and the
//: caret would go with it.
$("doc-phone-bar")?.addEventListener("pointerdown", (event) => {
  if (event.target.closest(".doc-code-key")) event.preventDefault();
});
$("doc-phone-bar")?.addEventListener("click", (event) => {
  const button = event.target.closest(".doc-code-key");
  if (button) docCodeKeyPress(button.dataset.codeKey);
});
