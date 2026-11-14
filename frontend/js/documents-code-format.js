// documents-code-format.js: Format for code documents (split out of documents-code.js, DOCUMENTS_PLAN L327).
//
// js-beautify's loader, the conservative re-indent (`docFormatCodeText`), the HTML and XML formatter, the JSON
// formatter, and the command that applies them (`docFormatCode`). **Loaded on the first Format**: the dock button,
// Shift+Alt+F, the palette row and the quick-fix menu all call the stand-in `docFormatCode` in documents-code.js, which
// fetches this file and calls the function of the same name that replaces it. Left unindented, as moved, so the
// DOC-FORMAT region below still runs in node (tests/test_code_editing.py). The scanner (`docCodeScan`), the HTML sets
// (`DOC_HTML_VOID`, `DOC_HTML_OPTIONAL`, `DOC_HTML_RAW`) and `docTreeHasJsx` stay in documents-code.js: the checks use them.
(() => {
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

  // DOC-FORMAT-BEGIN (tests/test_code_editing.py runs this region in node)
  //: The file types whose indentation is the brackets' business, so the
  //: formatter re-indents them. Everything else with a profile has its
  //: whitespace tidied and its indentation left exactly as written: Python's
  //: and YAML's indentation *is* their syntax, and shell, SQL, Ruby, TOML and
  //: INI have no bracket structure an indent could be derived from.
  const DOC_FORMAT_REINDENT = new Set(["c", "cpp", "cs", "java", "kt", "go", "rs", "swift", "php", "js", "ts", "css", "r"]);

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
  // DOC-FORMAT-END

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

  //: What the stand-in in documents-code.js is replaced by.
  //: One name in the shared scope: documents.js keeps a stand-in per function
  //: (same name), which calls through this once the file is in.
  Object.assign(window, { docCodeFormatPiece: { docFormatCode } });
})();
