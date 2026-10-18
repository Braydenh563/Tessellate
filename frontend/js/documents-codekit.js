// -----------------------------------------------------------------------------
// Code as documents: the code panel and its snippets library (INBOX 788)
// -----------------------------------------------------------------------------
//
// The owner, 2026-10-10: "maybe even add a code modules library like with the
// whiteboard and mindmap??". A column beside a code file's editor
// (`#doc-code-side`, the margin reader's place in `.doc-source-wrap`'s row),
// VS Code's secondary side bar, with a tab per tool. Snippets: the editor's
// built-in snippets (`DOC_CODE_SNIPPETS`, documents-code.js, the same rows
// completion offers) and the person's own, saved notebook-wide through
// `/code-snippets` (routes_code_snippets.py), by language and tag, with a
// search. A row inserts at the caret in one editor transaction, so Ctrl+Z
// takes it out; Save and Delete are each one step on the app's
// undo stack.
//
// Lazy: fetched by documents.js on the first press of a way in
// (`docCodeSideFrom`), after the Library bundle, so everything it calls there
// is already defined. Its top level declares and wires its own controls.

//: Which tab the panel last showed, or "" when it is closed: per device.
//: Per kind of document (see syncDocFileType): the code file's panel and the prose document's sections are remembered apart.
const docCodeSideKey = () => (docFileType().previewable ? "docSectionsSide" : "docCodeSide");

//: Open the panel on a tab. Above 600 it is a column the editor makes room
//: for (a flex row); on a phone the same element is moved into a bottom
//: sheet (`openSheet`, the recipe's modal sheet) and back when it is gone,
//: as a ⋯ menu is. `auto` is a code file reopening it: a phone never has a
//: sheet arrive unasked.
function docCodeSideOpen(tab = "snippets", { auto = false } = {}) {
  //: The Assistant is a code file's (it explains and refactors code): prose
  //: has the sections tab only.
  if (docFileType().previewable) tab = "snippets";
  //: Before the panel shows, so the Assistant tab is never seen for a frame in prose.
  docKitSyncLabels();
  const side = $("doc-code-side");
  const phone = window.matchMedia(PHONE_TABS).matches;
  if (phone && auto) return;
  for (const button of document.querySelectorAll("#doc-code-side-tabs [data-side]")) {
    const on = button.dataset.side === tab;
    button.setAttribute("aria-selected", String(on));
    button.classList.toggle("active", on);
    button.tabIndex = on ? 0 : -1;
    $(button.getAttribute("aria-controls")).classList.toggle("hidden", !on);
  }
  for (const opener of document.querySelectorAll('[aria-controls="doc-code-side"]')) {
    opener.setAttribute("aria-expanded", String(opener.dataset.side === tab));
  }
  if (phone) docCodeSideSheet(side);
  else {
    side.classList.remove("hidden");
    $("doc-source-wrap").classList.add("has-code-side");
    prefs.set(docCodeSideKey(), tab);
  }
  docKit.tab = tab;
  if (tab === "snippets") docSnippetsShow();
  if (tab === "assist") docAssistSyncScope();
}

function docCodeSideSheet(side) {
  if (docKit.sheetClose) return;
  const home = side.parentElement;
  const next = side.nextSibling;
  docKit.sheetClose = openSheet({
    label: "Code panel",
    name: "code-side",
    build: (card) => {
      side.classList.remove("hidden");
      card.appendChild(side);
    },
    onClose: () => {
      docKit.sheetClose = null;
      docKit.tab = "";
      for (const opener of document.querySelectorAll('[aria-controls="doc-code-side"]')) opener.setAttribute("aria-expanded", "false");
    },
    onGone: () => {
      side.classList.add("hidden");
      home.insertBefore(side, next);
    },
  });
}

function docCodeSideClose() {
  if (docKit.sheetClose) return docKit.sheetClose();
  $("doc-code-side").classList.add("hidden");
  $("doc-source-wrap").classList.remove("has-code-side");
  for (const opener of document.querySelectorAll('[aria-controls="doc-code-side"]')) opener.setAttribute("aria-expanded", "false");
  prefs.set(docCodeSideKey(), "");
  docKit.tab = "";
  docCmView?.focus();
}

//: A way in pressed again on the tab it opens closes the panel, as VS Code's
//: side bar buttons do.
function docCodeSideToggle(tab) {
  if (docKit.tab === tab) docCodeSideClose();
  else docCodeSideOpen(tab);
}

//: The Snippets tab's state, one name in the shared scope. `items` is the person's
//: snippets as the server last listed them (null until the first fetch),
//: `all` whether every language is shown with no search.
//: `tab` is the panel's open tab ("" when closed), `sheetClose` the phone
//: sheet's close while it is up.
const docKit = { items: null, all: false, loading: null, tab: "", sheetClose: null };

//: **The built-in library** (the board library's built-in sets, for code):
//: the pieces people retype, per language, as `[keyword, name, tags,
//: template]`, templates in the engine's snippet syntax (`${name}` a stop,
//: `${}` the last). Listed above the completion rows (`DOC_CODE_SNIPPETS`),
//: which are the short shapes; these are the small modules.
const DOC_KIT_LIBRARY = {
  py: [
    ["readfile", "Read a text file", ["io", "files"], "from pathlib import Path\n\ntext = Path(${\"notes.txt\"}).read_text(encoding=\"utf-8\")\n${}"],
    ["json", "Load and save JSON", ["io", "json"], "import json\nfrom pathlib import Path\n\n\ndef load(path):\n\treturn json.loads(Path(path).read_text(encoding=\"utf-8\"))\n\n\ndef save(path, data):\n\tPath(path).write_text(json.dumps(data, indent=2), encoding=\"utf-8\")\n${}"],
    ["csv", "Read CSV rows as dicts", ["io", "csv"], "import csv\n\nwith open(${\"data.csv\"}, newline=\"\", encoding=\"utf-8\") as f:\n\tfor row in csv.DictReader(f):\n\t\t${print(row)}"],
    ["dataclass", "Dataclass", ["types"], "from dataclasses import dataclass, field\n\n\n@dataclass\nclass ${Item}:\n\t${name}: str\n\ttags: list[str] = field(default_factory=list)\n${}"],
    ["argparse", "Command line arguments", ["cli"], "import argparse\n\nparser = argparse.ArgumentParser(description=${\"What this does.\"})\nparser.add_argument(${\"--name\"}, default=\"world\")\nargs = parser.parse_args()\n${}"],
    ["logging", "Logging setup", ["debug"], "import logging\n\nlogging.basicConfig(level=logging.INFO, format=\"%(asctime)s %(levelname)s %(message)s\")\nlog = logging.getLogger(${__name__})\n${}"],
    ["testcase", "unittest test case", ["tests"], "import unittest\n\n\nclass ${Thing}Test(unittest.TestCase):\n\tdef test_${it_works}(self):\n\t\tself.assertEqual(${1 + 1}, ${2})\n${}"],
    ["timer", "Time a block", ["debug", "performance"], "import time\n\nstart = time.perf_counter()\n${}\nprint(f\"took {time.perf_counter() - start:.3f}s\")"],
  ],
  js: [
    //: The call is split so `tests/test_no_bare_fetch.py`, which reads this
    //: file as the app's code, does not count a snippet's text as a request.
    ["fetchjson", "Fetch JSON", ["http", "async"], "async function ${getJson}(url) {\n\tconst response = await fetch" + "(url);\n\tif (!response.ok) throw new Error(\"HTTP \" + response.status);\n\treturn response.json();\n}\n${}"],
    ["debounce", "Debounce", ["timing"], "function debounce(fn, ms = ${250}) {\n\tlet timer = 0;\n\treturn (...args) => {\n\t\tclearTimeout(timer);\n\t\ttimer = setTimeout(() => fn(...args), ms);\n\t};\n}\n${}"],
    ["sleep", "Sleep", ["timing", "async"], "const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));\n${}"],
    ["groupby", "Group an array by a key", ["arrays"], "function groupBy(items, key) {\n\tconst groups = new Map();\n\tfor (const item of items) {\n\t\tconst k = item[key];\n\t\tif (!groups.has(k)) groups.set(k, []);\n\t\tgroups.get(k).push(item);\n\t}\n\treturn groups;\n}\n${}"],
    ["describe", "A test block", ["tests"], "describe(${\"thing\"}, () => {\n\tit(${\"works\"}, () => {\n\t\texpect(${1 + 1}).toBe(${2});\n\t});\n});\n${}"],
    ["class", "Class with a constructor", ["types"], "class ${Name} {\n\tconstructor(${value}) {\n\t\tthis.${value} = ${value};\n\t}\n}\n${}"],
  ],
  html: [
    ["page", "Page skeleton", ["layout"], "<!doctype html>\n<html lang=\"en\">\n<head>\n\t<meta charset=\"utf-8\">\n\t<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n\t<title>${Title}</title>\n</head>\n<body>\n\t${}\n</body>\n</html>"],
    ["form", "Form with a label", ["forms"], "<form>\n\t<label for=\"${name}\">${Name}</label>\n\t<input id=\"${name}\" name=\"${name}\" type=\"text\">\n\t<button type=\"submit\">${Send}</button>\n</form>"],
    ["table", "Table", ["layout"], "<table>\n\t<thead>\n\t\t<tr><th>${A}</th><th>${B}</th></tr>\n\t</thead>\n\t<tbody>\n\t\t<tr><td>${}</td><td></td></tr>\n\t</tbody>\n</table>"],
  ],
  css: [
    ["flexrow", "Flex row", ["layout"], "${.row} {\n\tdisplay: flex;\n\talign-items: center;\n\tgap: ${1rem};\n}"],
    ["grid", "Responsive grid", ["layout"], "${.grid} {\n\tdisplay: grid;\n\tgrid-template-columns: repeat(auto-fill, minmax(${12rem}, 1fr));\n\tgap: ${1rem};\n}"],
    ["dark", "Dark mode colours", ["theme"], "@media (prefers-color-scheme: dark) {\n\t:root {\n\t\t--bg: ${#111};\n\t\t--text: ${#eee};\n\t}\n}"],
  ],
  sql: [
    ["upsert", "Insert or update", ["writes"], "INSERT INTO ${table} (${id}, ${name})\nVALUES (${1}, ${'a'})\nON CONFLICT (${id}) DO UPDATE SET ${name} = excluded.${name};"],
    ["count", "Count by group", ["reports"], "SELECT ${column}, COUNT(*) AS n\nFROM ${table}\nGROUP BY ${column}\nORDER BY n DESC;"],
    ["cte", "WITH a named query", ["reports"], "WITH ${recent} AS (\n\tSELECT * FROM ${table} WHERE ${created_at} > ${'2026-01-01'}\n)\nSELECT * FROM ${recent};"],
  ],
};
DOC_KIT_LIBRARY.ts = DOC_KIT_LIBRARY.js;

//: **Text sections for ordinary documents** (INBOX 904 B18: "a library of
//: prefilled templates and curated text sections and stuff like the code
//: snippets but for general documents as well"). The whole-page templates are
//: `DOC_TEMPLATES`; these are the blocks people retype inside a page: as
//: `[keyword, name, tags, template]` like the code rows, in the engine's snippet
//: syntax (`${prompt}` a stop Tab walks to, one `${}` the last). A stop's name
//: is used once in a template, since a repeat would mirror itself; `{{date}}`
//: is today, filled when the section goes in (`docSectionFill`).
const DOC_SECTIONS = [
  ["meeting", "Meeting notes", ["meetings"], [
    "## ${Meeting title}", "", "**Date:** {{date}}", "**Attendees:** ${Names}", "",
    "### Agenda", "", "1. ${First topic}", "",
    "### Notes", "", "${What was said}", "",
    "### Decisions", "", "- ${What was decided}", "",
    "### Actions", "", "- [ ] ${Who, what, by when}",
  ].join("\n")],
  ["agenda", "Agenda", ["meetings"], [
    "### Agenda", "", "1. ${First topic}", "2. ${Second topic}", "3. ${Third topic}",
  ].join("\n")],
  ["actions", "Action items", ["meetings", "tasks"], [
    "### Actions", "", "- [ ] ${Who, what, by when}", "- [ ] ${Next action}", "- [ ] ${Another action}",
  ].join("\n")],
  ["decision", "Decision record", ["planning"], [
    "## ${Decision title}", "", "**Date:** {{date}}", "**Status:** ${proposed}", "",
    "### Context", "", "${Why this came up}", "",
    "### Options considered", "", "1. ${First option}", "2. ${Second option}", "",
    "### Decision", "", "${What we chose, and why}", "",
    "### Consequences", "", "- ${What changes because of it}",
  ].join("\n")],
  ["status", "Status update", ["planning", "reviews"], [
    "### Status, {{date}}", "", "**Done**", "", "- ${What shipped}", "",
    "**Next**", "", "- ${What is next}", "",
    "**Blocked**", "", "- ${What is in the way, or nothing}",
  ].join("\n")],
  ["brief", "Project brief", ["planning"], [
    "## ${Project name}", "", "**Goal:** ${One sentence}", "",
    "### Scope", "", "- ${In scope}", "",
    "### Out of scope", "", "- ${Not now}", "",
    "### Milestones", "", "| When | What |", "| --- | --- |", "| ${Date} | ${Milestone} |", "",
    "### Risks", "", "- ${What could go wrong}",
  ].join("\n")],
  ["risks", "Risk table", ["planning"], [
    "| Risk | Likelihood | Impact | What we do |", "| --- | --- | --- | --- |",
    "| ${A risk} | ${Low} | ${High} | ${The plan} |", "|  |  |  |  |",
  ].join("\n")],
  ["milestones", "Milestones", ["planning"], [
    "| When | What | Who |", "| --- | --- | --- |", "| ${Date} | ${First milestone} | ${Name} |", "|  |  |  |",
  ].join("\n")],
  ["timeline", "Timeline", ["planning", "reference"], [
    "| When | What happened |", "| --- | --- |", "| ${Date} | ${Event} |", "|  |  |",
  ].join("\n")],
  ["proscons", "Pros and cons", ["writing"], [
    "| Pros | Cons |", "| --- | --- |", "| ${A strength} | ${A weakness} |", "|  |  |",
  ].join("\n")],
  ["compare", "Comparison table", ["writing", "reference"], [
    "| Option | ${First measure} | ${Second measure} |", "| --- | --- | --- |",
    "| ${Option A} |  |  |", "| ${Option B} |  |  |",
  ].join("\n")],
  ["faq", "Questions and answers", ["reference"], [
    "### Frequently asked questions", "", "**${First question}**", "", "${Its answer}", "",
    "**${Second question}**", "", "${Its answer, too}",
  ].join("\n")],
  ["glossary", "Glossary", ["reference"], [
    "| Term | Meaning |", "| --- | --- |", "| ${A term} | ${What it means} |", "|  |  |",
  ].join("\n")],
  ["summary", "Summary callout", ["writing", "callouts"], [
    "> [!summary] ${The short version}", "> ${Two or three sentences.}",
  ].join("\n")],
  ["note", "Note callout", ["callouts"], ["> [!note] ${A point worth setting apart}", "> ${The detail.}"].join("\n")],
  ["tip", "Tip callout", ["callouts"], ["> [!tip] ${A better way}", "> ${How to do it.}"].join("\n")],
  ["warning", "Warning callout", ["callouts"], ["> [!warning] ${What can go wrong}", "> ${How to avoid it.}"].join("\n")],
  ["questions", "Open questions", ["writing", "tasks"], [
    "### Open questions", "", "- [ ] ${A question to answer}", "- [ ] ${Another question}",
  ].join("\n")],
  ["retro", "Retrospective", ["reviews"], [
    "### Went well", "", "- ${A win}", "",
    "### Did not go well", "", "- ${A problem}", "",
    "### Try next", "", "- [ ] ${One change}",
  ].join("\n")],
  ["daylog", "Day log", ["reviews"], [
    "### {{date}}", "", "**Today**", "", "- ${What happened}", "",
    "**Tomorrow**", "", "- [ ] ${What is next}",
  ].join("\n")],
  ["reading", "Reading notes", ["study"], [
    "## ${Title}", "", "**Author:** ${Name}", "**Read:** {{date}}", "",
    "### Key ideas", "", "- ${An idea}", "",
    "### Quotes", "", "> ${A line worth keeping}", "",
    "### My take", "", "${What I think}",
  ].join("\n")],
  ["outline", "Essay outline", ["study", "writing"], [
    "## ${Working title}", "", "**Thesis:** ${The claim in one sentence}", "",
    "1. ${First argument}", "2. ${Second argument}", "3. ${Counter-argument and reply}", "",
    "**Conclusion:** ${What follows}",
  ].join("\n")],
  ["checklist", "Checklist", ["tasks"], [
    "- [ ] ${First item}", "- [ ] ${Second item}", "- [ ] ${Third item}",
  ].join("\n")],
  ["quote", "Quote", ["writing"], ["> ${The quote}", ">", "> ${Who said it, and where}"].join("\n")],
];

//: A language's name for a group head: the server's own type table.
function docKitLanguageName(ext) {
  return (docFileTypes.find((t) => t.ext === ext) || {}).label || ext.toUpperCase();
}

//: The built-in rows, one list per language. TypeScript shares JavaScript's
//: array, which is listed under JavaScript unless TypeScript is the file's.
function docKitBuiltins(current) {
  const seen = new Map();
  const out = [];
  for (const [ext, rows] of Object.entries(DOC_KIT_LIBRARY)) {
    if (seen.has(rows) && ext !== current) continue;
    seen.set(rows, ext);
    for (const [label, name, tags, template] of rows) {
      out.push({ key: `builtin:${ext}:${label}`, name, keyword: label, language: ext, tags, template, builtin: true });
    }
  }
  seen.clear();
  for (const [ext, rows] of Object.entries(DOC_CODE_SNIPPETS)) {
    if (seen.has(rows) && ext !== current) continue;
    seen.set(rows, ext);
    for (const [label, detail, template] of rows) {
      out.push({ key: `builtin:${ext}:${label}`, name: detail, keyword: label, language: ext, tags: [], template, builtin: true });
    }
  }
  //: The text sections are Markdown's: listed first for a prose document,
  //: under "Show every language" in a code file like any other language.
  for (const [label, name, tags, template] of DOC_SECTIONS) {
    out.push({ key: `builtin:md:${label}`, name, keyword: label, language: "md", tags, template, builtin: true });
  }
  return out;
}

//: Which list the panel shows first: a prose document's is the text sections
//: (`md`), a code file's its own language.
function docKitCurrent() {
  const type = docFileType();
  return type.previewable ? "md" : type.ext;
}

const docKitNoun = () => (docFileType().previewable ? "section" : "snippet");

//: The words follow the document: the same panel is "Snippets" beside code and
//: "Sections" beside prose, and what it saves and searches says so.
function docKitSyncLabels() {
  const prose = docFileType().previewable;
  $("doc-snippet-search").placeholder = prose ? "Search sections…" : "Search snippets…";
  $("doc-snippet-search").setAttribute("aria-label", prose ? "Search sections" : "Search snippets");
  const save = $("doc-snippet-save");
  const saveTitle = prose ? "Save the selected text as a section" : "Save the selected code as a snippet";
  save.title = saveTitle;
  save.setAttribute("aria-label", saveTitle);
  const sections = $("doc-code-snippets");
  sections.setAttribute("aria-label", prose ? "Sections" : "Snippets");
  $("doc-snippet-list").setAttribute("aria-label", prose ? "Sections" : "Snippets");
  const tab = document.querySelector('#doc-code-side-tabs [data-side="snippets"]');
  if (tab) tab.textContent = prose ? "Sections" : "Snippets";
  const side = $("doc-code-side");
  side.classList.toggle("is-prose", prose);
  side.setAttribute("aria-label", prose ? "Sections panel" : "Code panel");
  $("doc-code-side-close").title = prose ? "Close the sections panel" : "Close the code panel";
  $("doc-code-side-close").setAttribute("aria-label", $("doc-code-side-close").title);
}

//: The blank lines a section needs round it, from the line it lands on: a
//: block starts on its own line with a blank line above and ends with one
//: below, whether the caret is at the end of a paragraph, on an empty line or
//: in the middle of a sentence. `prev` and `next` are the neighbouring lines'
//: text, or null at either end of the document.
function docSectionPad(before, after, prev, next) {
  const lead = before.trim() ? "\n\n" : prev !== null && prev.trim() ? "\n" : "";
  const trail = after.trim() ? "\n\n" : next !== null && next.trim() ? "\n" : "";
  return { lead, trail };
}

//: `{{date}}` in a section, as in a page template: today, in the person's words.
function docSectionFill(text) {
  return docTemplateFill({ id: "section", title: "", content: text }).content;
}

function docKitEntries(current) {
  const yours = (docKit.items || []).map((item) => ({
    key: `item:${item.id}`, id: item.id, name: item.name, keyword: "", language: item.payload.language,
    tags: item.tags || [], code: item.payload.code, builtin: false,
  }));
  return [...yours, ...docKitBuiltins(current)];
}

//: Words match the name, the keyword, the language (its extension or its
//: name) or a tag; a word written `#io` matches the tag `io` only.
function docKitMatches(entry, words) {
  const hay = [entry.name, entry.keyword, entry.language, docKitLanguageName(entry.language), ...entry.tags].join(" ").toLowerCase();
  return words.every((w) => (w.startsWith("#") ? entry.tags.includes(w.slice(1)) : hay.includes(w)));
}

async function docKitFetch(force = false) {
  if (docKit.items && !force) return docKit.items;
  if (!docKit.loading) {
    docKit.loading = apiJson("/code-snippets", { silent: true })
      .then((body) => (docKit.items = body.items || []))
      .catch(() => (docKit.items = docKit.items || []))
      .finally(() => (docKit.loading = null));
  }
  return docKit.loading;
}

//: The tab, drawn: this file's language first, then the rest by name.
async function docSnippetsShow() {
  await docKitFetch();
  docSnippetsRender();
}

function docSnippetsRender() {
  const list = $("doc-snippet-list");
  const empty = $("doc-snippet-empty");
  if (!list || !empty) return;
  const current = docKitCurrent();
  const prose = docFileType().previewable;
  docKitSyncLabels();
  const words = ($("doc-snippet-search").value || "").toLowerCase().split(/\s+/).filter(Boolean);
  const wide = docKit.all || words.length > 0;
  //: A prose document is offered sections only, never the code rows a search
  //: word would otherwise pull in from every language.
  const shown = docKitEntries(current).filter(
    (e) => (prose ? e.language === "md" : wide || e.language === current) && docKitMatches(e, words)
  );
  const groups = new Map();
  for (const entry of shown) {
    if (!groups.has(entry.language)) groups.set(entry.language, []);
    groups.get(entry.language).push(entry);
  }
  const order = [...groups.keys()].sort((a, b) =>
    a === current ? -1 : b === current ? 1 : docKitLanguageName(a).localeCompare(docKitLanguageName(b))
  );
  list.replaceChildren();
  for (const ext of order) {
    const head = document.createElement("li");
    head.className = "doc-snippet-group muted text-xs";
    head.setAttribute("role", "presentation");
    head.textContent = ext === "md" ? "Text sections" : ext === current ? `${docKitLanguageName(ext)}, this file` : docKitLanguageName(ext);
    list.appendChild(head);
    for (const entry of groups.get(ext)) list.appendChild(docSnippetRow(entry));
  }
  //: Every language is a code file's question; a prose document's list is the
  //: sections, with nothing more to show.
  if (!wide && !prose) list.appendChild(docSnippetMoreRow());
  empty.classList.toggle("hidden", shown.length > 0);
  empty.textContent = words.length
    ? prose ? "No section matches that. Try a word or a #tag." : "No snippet matches that. Try a language, a name or a #tag."
    : `No snippets for ${docKitLanguageName(current)} yet. Select some code and press Save.`;
}

//: Every language, one press away when the list shows only this file's.
function docSnippetMoreRow() {
  const li = document.createElement("li");
  li.setAttribute("role", "presentation");
  const more = document.createElement("button");
  more.type = "button";
  more.className = "linklike small doc-snippet-more";
  more.textContent = "Show every language";
  more.addEventListener("click", () => {
    docKit.all = true;
    docSnippetsRender();
  });
  li.appendChild(more);
  return li;
}

function docSnippetRow(entry) {
  const li = document.createElement("li");
  li.className = "doc-snippet-item";
  const row = document.createElement("button");
  row.type = "button";
  row.className = "doc-snippet-row";
  row.dataset.key = entry.key;
  row.title = entry.builtin ? `Insert ${entry.name} (Tab walks its stops)` : `Insert ${entry.name}`;
  const name = document.createElement("span");
  name.className = "doc-snippet-name";
  name.textContent = entry.name;
  const facts = document.createElement("span");
  facts.className = "doc-snippet-facts muted text-xs";
  const first = (entry.code || entry.template || "").split("\n")[0].replace(/\$\{(\w*)\}/g, "$1");
  facts.textContent = [entry.keyword, ...entry.tags.map((t) => `#${t}`)].filter(Boolean).join(" ") || first;
  row.append(name, facts);
  if (entry.builtin) {
    const label = document.createElement("span");
    label.className = "chip item-label";
    chipWords(label, "Built-in");
    row.appendChild(label);
  }
  row.addEventListener("click", () => docSnippetInsert(entry));
  row.draggable = true;
  row.addEventListener("dragstart", (event) => docSnippetDragStart(event, entry));
  li.appendChild(row);
  if (!entry.builtin) {
    li.appendChild(kebabMenu([
      { label: "ph:arrow-line-down Insert at the caret", run: () => docSnippetInsert(entry) },
      { label: "ph:pencil-simple Rename or retag", run: () => docSnippetRename(entry) },
      { label: "ph:trash Delete", danger: true, run: () => docSnippetDelete(entry) },
    ], `Actions for ${entry.name}`, { vertical: true }));
  }
  return li;
}

//: One transaction, so one Ctrl+Z takes it out. A built-in goes in through
//: the engine's own snippet, so its stops are live; a saved one is text,
//: since `${` in it is code, not a stop.
function docSnippetInsert(entry, { at = null } = {}) {
  const view = docCmView;
  const CM = window.CM6;
  const prose = docFileType().previewable;
  if (!view || !CM || !currentDoc) return toast(prose ? "Open a document first." : "Open a code document first.", "info");
  //: `at` is where a drag was dropped; a click or Enter uses the caret.
  const { from, to } = at == null ? view.state.selection.main : { from: at, to: at };
  //: A section is a block: it gets its own lines and a blank line either side
  //: wherever it lands (`docSectionPad`), and today's date where it asks.
  let lead = "";
  let trail = "";
  if (prose) {
    const doc = view.state.doc;
    const head = doc.lineAt(from);
    const tail = doc.lineAt(to);
    ({ lead, trail } = docSectionPad(
      doc.sliceString(head.from, from),
      doc.sliceString(to, tail.to),
      head.number > 1 ? doc.line(head.number - 1).text : null,
      tail.number < doc.lines ? doc.line(tail.number + 1).text : null
    ));
  }
  if (entry.template) {
    const template = prose ? lead + docSectionFill(entry.template) + trail : entry.template;
    CM.autocomplete.snippet(template)(view, null, from, to);
  } else {
    //: Saved text goes in as it was written: a `{{date}}` in it is the
    //: person's own words, not the built-in sections' placeholder.
    const insert = lead + entry.code + trail;
    view.dispatch({
      changes: { from, to, insert },
      selection: { anchor: from + insert.length - trail.length },
      scrollIntoView: true,
      userEvent: "input.paste",
    });
  }
  //: On a phone the sheet covers the editor: it goes, so the insert shows.
  if (docKit.sheetClose) docKit.sheetClose();
  view.focus();
}

//: **Drag a row into the text** (INBOX 904 B19). The row carries its plain
//: text (so a drop anywhere else still pastes something sensible); over the
//: editor a caret-high accent bar shows where it will land and the text
//: scrolls when the pointer sits in the band at its top or bottom edge; the
//: drop inserts there, through the same one-transaction insert a click uses.
//: The listeners are on the document in the capture phase, so the editor's
//: own drop handler never also pastes the text/plain it was handed.
const docDrag = { entry: null, x: 0, y: 0, raf: 0, ghost: null };

//: Pixels to scroll this frame for a pointer at `y` over an editor spanning
//: `top` to `bottom`: nothing in the middle, one to `fastest` inside the
//: `band` at either edge (more the closer), the cap beyond it.
function docSnippetScrollSpeed(y, top, bottom, band = 48, fastest = 20) {
  if (y < top + band) return -Math.min(fastest, Math.ceil((fastest * (top + band - y)) / band));
  if (y > bottom - band) return Math.min(fastest, Math.ceil((fastest * (y - (bottom - band))) / band));
  return 0;
}

//: The text a drag carries: a snippet's stops (`${name}`, `${}`) read as
//: their names, a saved snippet as it is.
function docSnippetPlain(entry) {
  return entry.template ? entry.template.replace(/\$\{(\w*)\}/g, "$1") : entry.code || "";
}

function docSnippetDragStart(event, entry) {
  if (!docCmView || !currentDoc) {
    event.preventDefault();
    return toast("Open a code document first.", "info");
  }
  docDrag.entry = entry;
  event.dataTransfer.setData("text/plain", docSnippetPlain(entry));
  event.dataTransfer.effectAllowed = "copy";
}

function docSnippetDragEnd() {
  cancelAnimationFrame(docDrag.raf);
  docDrag.raf = 0;
  docDrag.ghost?.remove();
  docDrag.ghost = null;
  docDrag.entry = null;
}

//: One frame of an active drag: scroll if the pointer is at an edge, then
//: put the ghost caret where the text under the pointer says it will land.
function docSnippetDragFrame() {
  const view = docCmView;
  if (!docDrag.entry || !view) return docSnippetDragEnd();
  const box = view.scrollDOM.getBoundingClientRect();
  //: Only while the pointer is over the editor's columns: a drag passing
  //: the sidebar at the editor's height must not scroll it.
  const over = docDrag.x >= box.left && docDrag.x <= box.right;
  const speed = over ? docSnippetScrollSpeed(docDrag.y, box.top, box.bottom) : 0;
  if (speed) view.scrollDOM.scrollTop += speed;
  const pos = view.posAtCoords({ x: docDrag.x, y: docDrag.y }, false);
  const at = pos == null ? null : view.coordsAtPos(pos);
  if (!docDrag.ghost) {
    docDrag.ghost = document.createElement("div");
    docDrag.ghost.className = "doc-drop-ghost";
    docDrag.ghost.setAttribute("aria-hidden", "true");
    document.body.appendChild(docDrag.ghost);
  }
  const ghost = docDrag.ghost;
  //: A line cut by the editor's edge keeps its visible part; one wholly
  //: outside has no ghost.
  const top = at ? Math.max(at.top, box.top) : 0;
  const bottom = at ? Math.min(at.bottom, box.bottom) : 0;
  const within = over && docDrag.y >= box.top && docDrag.y <= box.bottom && bottom > top;
  ghost.classList.toggle("hidden", !within);
  if (within) {
    ghost.style.left = `${Math.round(at.left)}px`;
    ghost.style.top = `${Math.round(top)}px`;
    ghost.style.height = `${Math.round(bottom - top)}px`;
  }
  docDrag.raf = requestAnimationFrame(docSnippetDragFrame);
}

document.addEventListener(
  "dragover",
  (event) => {
    if (!docDrag.entry) return;
    docDrag.x = event.clientX;
    docDrag.y = event.clientY;
    if (!docCmView || !docCmView.dom.contains(event.target)) {
      docDrag.ghost?.classList.add("hidden");
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    if (!docDrag.raf) docDrag.raf = requestAnimationFrame(docSnippetDragFrame);
  },
  true
);

document.addEventListener(
  "drop",
  (event) => {
    if (!docDrag.entry) return;
    const view = docCmView;
    const entry = docDrag.entry;
    const inside = view && view.dom.contains(event.target);
    docSnippetDragEnd();
    if (!inside) return;
    event.preventDefault();
    event.stopPropagation();
    const pos = view.posAtCoords({ x: event.clientX, y: event.clientY }, false);
    if (pos != null) docSnippetInsert(entry, { at: pos });
  },
  true
);
document.addEventListener("dragend", docSnippetDragEnd, true);

//: "Read a file #io #files": the words are the name, the #words its tags.
function docKitSplitName(text) {
  const tags = [];
  const name = String(text || "")
    .replace(/(^|\s)#([\w-]{1,40})/g, (_, lead, tag) => {
      tags.push(tag.toLowerCase());
      return lead;
    })
    .replace(/\s+/g, " ")
    .trim();
  return { name, tags };
}

async function docSnippetSave() {
  const view = docCmView;
  const prose = docFileType().previewable;
  const noun = prose ? "section" : "snippet";
  if (!view || !currentDoc) return toast(prose ? "Open a document first." : "Open a code document first.", "info");
  const { from, to } = view.state.selection.main;
  const code = view.state.sliceDoc(from, to);
  if (!code.trim()) return toast(prose ? "Select some text first, then save it as a section." : "Select some code first, then save it as a snippet.", "info");
  const suggested = code.trim().split("\n")[0].slice(0, 60);
  const answer = await promptDialog(`Name the ${noun} (#words become tags)`, suggested, { confirmLabel: `Save ${noun}` });
  if (answer === null || answer === undefined) return;
  const { name, tags } = docKitSplitName(answer);
  if (!name) return toast(`A ${noun} needs a name.`, "info");
  const made = await apiJson("/code-snippets", {
    method: "POST",
    body: JSON.stringify({ name, tags, language: docKitCurrent(), code }),
  }).catch((error) => toast(error.message, true));
  if (!made) return;
  await docKitFetch(true);
  docSnippetsRender();
  offerUndo(
    `Save ${noun} "${name}"`,
    `Saved "${name}" to your ${noun}s.`,
    () => docKitBin(made.id, true),
    () => docKitBin(made.id, false)
  );
}

//: Into the library's bin, or back out of it: the board library's own pair
//: (`DELETE /board-library/{id}` and its `restore`), which a snippet shares.
async function docKitBin(id, binned) {
  await apiJson(binned ? `/board-library/${id}` : `/board-library/${id}/restore`, { method: binned ? "DELETE" : "POST" });
  await docKitFetch(true);
  docSnippetsRender();
}

async function docSnippetDelete(entry) {
  await docKitBin(entry.id, true).catch((error) => toast(error.message, true));
  offerUndo(
    `Delete ${docKitNoun()} "${entry.name}"`,
    `Deleted "${entry.name}".`,
    () => docKitBin(entry.id, false),
    () => docKitBin(entry.id, true)
  );
}

async function docSnippetRename(entry) {
  const shown = [entry.name, ...entry.tags.map((t) => `#${t}`)].join(" ");
  const answer = await promptDialog(`Rename the ${docKitNoun()} (#words become tags)`, shown, { confirmLabel: "Rename" });
  if (answer === null || answer === undefined || answer.trim() === shown) return;
  const { name, tags } = docKitSplitName(answer);
  if (!name) return toast(`A ${docKitNoun()} needs a name.`, "info");
  const put = async (body) => {
    await apiJson(`/code-snippets/${entry.id}`, { method: "PUT", body: JSON.stringify(body) });
    await docKitFetch(true);
    docSnippetsRender();
  };
  await put({ name, tags }).catch((error) => toast(error.message, true));
  offerUndo(`Rename ${docKitNoun()} "${name}"`, `Renamed to "${name}".`, () => put({ name: entry.name, tags: entry.tags }), () => put({ name, tags }));
}

//: The arrows walk the rows, from the search field down and back up.
function docSnippetKeys(event) {
  const rows = [...document.querySelectorAll("#doc-snippet-list .doc-snippet-row, #doc-snippet-list .doc-snippet-more")];
  if (!rows.length || !["ArrowDown", "ArrowUp"].includes(event.key)) return;
  const at = rows.indexOf(document.activeElement);
  const next = event.key === "ArrowDown" ? rows[Math.min(at + 1, rows.length - 1)] : at <= 0 ? $("doc-snippet-search") : rows[at - 1];
  event.preventDefault();
  next.focus();
}

$("doc-snippet-search").addEventListener("input", docSnippetsRender);
$("doc-snippet-search").addEventListener("keydown", docSnippetKeys);
$("doc-snippet-list").addEventListener("keydown", docSnippetKeys);
$("doc-snippet-save").addEventListener("click", docSnippetSave);
$("doc-code-side-close").addEventListener("click", docCodeSideClose);
$("doc-code-side-tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-side]");
  if (tab) docCodeSideOpen(tab.dataset.side);
});

// -----------------------------------------------------------------------------
// The Assistant tab (INBOX 788)
// -----------------------------------------------------------------------------
//
// The owner: "a way to better interact with the ai as a coding asistant like
// in vs code??". Explain, Fix, Write tests, Refactor and a question, over the
// selected lines or the whole file, through `/documents/{id}/code-assist`
// (ai/code_assist.py: the documents feature's model, one provider path; with
// no model, the needle extra choosing one of the tools below). A change
// comes back as a diff (`docRenderDiff`, the one diff in the app): Apply
// writes it in one editor transaction, so Ctrl+Z takes it out; Reject leaves
// the file alone. The tools row is deterministic and needs no model.

//: `proposal` is `{docId, from, to, before, insert}` while a change waits,
//: `controller` the ask in flight.
const docAssist = { proposal: null, controller: null };

const docAssistModelOff = () => Boolean(modelStatus && modelStatus.ollama_running === false);

//: What an ask is about: the selected lines, widened to whole lines so a
//: change replaces what it was shown, or the whole file.
function docAssistTarget() {
  const state = docCmView.state;
  const sel = state.selection.main;
  if (sel.empty) return { from: 0, to: state.doc.length, text: state.doc.toString(), whole: true };
  const from = state.doc.lineAt(sel.from).from;
  const to = state.doc.lineAt(sel.to).to;
  return { from, to, text: state.sliceDoc(from, to), whole: false };
}

function docAssistSyncScope() {
  const scope = $("doc-assist-scope");
  if (!scope || !docCmView) return;
  const target = docAssistTarget();
  const lines = target.text ? target.text.replace(/\n$/, "").split("\n").length : 0;
  scope.textContent = target.whole
    ? `About the whole file, ${lines} ${lines === 1 ? "line" : "lines"}. Select lines to ask about those.`
    : `About the ${lines} selected ${lines === 1 ? "line" : "lines"}.`;
}

//: The problem a Fix is about: the one at the caret, else the first in the
//: target, as "line N: message".
function docAssistDiagnostic(target) {
  const CM = window.CM6;
  const state = docCmView.state;
  const caret = state.selection.main.head;
  let here = null;
  let first = null;
  CM.lint.forEachDiagnostic(state, (d, from, to) => {
    const said = `line ${state.doc.lineAt(from).number}: ${d.message}`;
    if (!here && from <= caret && caret <= to) here = said;
    if (!first && from >= target.from && from <= target.to) first = said;
  });
  return here || first || "";
}

function docAssistAnswerArea() {
  const area = $("doc-assist-answer");
  area.replaceChildren();
  return area;
}

function docAssistSay(text, { error = false } = {}) {
  const line = document.createElement("p");
  line.className = error ? "status error" : "muted text-sm";
  line.textContent = text;
  docAssistAnswerArea().appendChild(line);
  return line;
}

//: **A question the tools can answer, answered by them** (CHAT_PLAN
//: decision 75; the owner, 2026-10-11). With no model the field stays live
//: for these: format, run the tests or the file, where a name is used, the
//: quick fix and the symbols. Anything else goes on to the server, which
//: offers it to needle or says plainly that it needs a model.
const DOC_ASSIST_ROUTES = [
  ["format_code", /\b(format|indent|tidy|prettify|reformat)\b/i],
  ["run_tests", /\btests?\b/i],
  ["find_usages", /\b(usages?|uses|used|references?|callers?|calls)\b/i],
  ["quick_fix", /\b(fix|error|problem|warning|underline)\b/i],
  ["symbols", /\b(outline|symbols?|functions|classes|methods)\b/i],
  ["run_file", /\b(run|execute|start)\b/i],
];

function docAssistRouteTool(question) {
  const text = String(question || "");
  const row = DOC_ASSIST_ROUTES.find(([, pattern]) => pattern.test(text));
  if (!row) return null;
  if (row[0] !== "find_usages") return { tool: row[0], args: {} };
  const quoted = /`([A-Za-z_$][\w$]*)`/.exec(text);
  const after = /\b(?:of|is|does|for)\s+([A-Za-z_$][\w$]*)/i.exec(text);
  const name = quoted?.[1] || (after && !/^(the|this|that|it|a)$/i.test(after[1]) ? after[1] : "");
  return { tool: "find_usages", args: name ? { name } : {} };
}

async function docAssistAsk(action) {
  if (!docCmView || !currentDoc) return toast("Open a code document first.", "info");
  docAssistSyncScope();
  const target = docAssistTarget();
  const diagnostic = action === "fix" ? docAssistDiagnostic(target) : "";
  if (action === "fix" && docAssistModelOff()) return docAssistTool("quick_fix");
  if (action === "fix" && !diagnostic) return docAssistSay("No problem is underlined here. Put the caret on one, or ask a question below.");
  const question = action === "ask" ? $("doc-assist-question").value.trim() : "";
  if (action === "ask" && !question) return docAssistSay("Type a question first.");
  const routed = action === "ask" && docAssistModelOff() ? docAssistRouteTool(question) : null;
  if (routed) {
    docAssistSay(`No model is connected, so the tools answered: ${DOC_ASSIST_TOOL_NAMES[routed.tool]}.`);
    return docAssistTool(routed.tool, routed.args, { keep: true });
  }
  docAssist.controller?.abort();
  docAssist.controller = new AbortController();
  docAssist.proposal = null;
  const wait = docAssistSay("");
  setLabel(wait, `ph:spin ${progressPhaseText("reaching")}`);
  try {
    const body = await apiJson(`/documents/${currentDoc.id}/code-assist`, {
      method: "POST",
      signal: docAssist.controller.signal,
      body: JSON.stringify({ action, code: target.text, question, diagnostic }),
    });
    docAssistShow(body, action, target);
  } catch (error) {
    if (error.name !== "AbortError") docAssistSay(error.message, { error: true });
  } finally {
    docAssist.controller = null;
  }
}

function docAssistShow(body, action, target) {
  if (body.kind === "tool") {
    docAssistSay(`${body.answered_by || "The tools"} chose ${body.tool.replace("_", " ")}.`);
    return docAssistTool(body.tool, body.args || {}, { keep: true });
  }
  const area = docAssistAnswerArea();
  if (body.kind === "needs_model") return docAssistSay(body.text);
  if (body.text) {
    const prose = document.createElement("div");
    prose.className = "md doc-assist-prose";
    renderMarkdown(prose, body.text);
    area.appendChild(prose);
  }
  if (body.kind === "change" && body.code) docAssistPropose(area, action, target, body.code);
  if (body.answered_by) {
    const by = document.createElement("p");
    by.className = "muted text-xs";
    by.textContent = `From ${body.answered_by}`;
    area.appendChild(by);
  }
}

//: Tests are added at the end of the file; every other change replaces
//: what it was asked about.
function docAssistPropose(area, action, target, code) {
  const state = docCmView.state;
  const append = action === "tests";
  const end = state.doc.length;
  const tail = state.sliceDoc(Math.max(0, end - 2), end);
  const insert = append ? `${tail.endsWith("\n\n") ? "" : tail.endsWith("\n") ? "\n" : "\n\n"}${code}` : code.replace(/\n$/, target.text.endsWith("\n") ? "\n" : "");
  docAssist.proposal = append
    ? { docId: currentDoc.id, from: end, to: end, before: "", insert }
    : { docId: currentDoc.id, from: target.from, to: target.to, before: target.text, insert };
  const diff = document.createElement("div");
  docRenderDiff(diff, docDiffLines(docAssist.proposal.before, insert), { emptyText: "No change: the model gave back the same code." });
  const bar = document.createElement("div");
  bar.className = "doc-assist-apply";
  const apply = document.createElement("button");
  apply.type = "button";
  apply.className = "accent small";
  setLabel(apply, append ? "ph:plus Add the tests" : "ph:check Apply");
  apply.addEventListener("click", docAssistApply);
  const reject = document.createElement("button");
  reject.type = "button";
  reject.className = "ghost small";
  reject.textContent = "Reject";
  reject.addEventListener("click", () => {
    docAssist.proposal = null;
    docAssistSay("Rejected. The file is as it was.");
  });
  bar.append(apply, reject);
  area.append(diff, bar);
}

//: One editor transaction, so Ctrl+Z takes the whole change out. Refused
//: when the text it was made for has changed since.
function docAssistApply() {
  const p = docAssist.proposal;
  const view = docCmView;
  if (!p || !view || !currentDoc || currentDoc.id !== p.docId) return docAssistSay("That change was for another document.", { error: true });
  if (view.state.sliceDoc(p.from, p.to) !== p.before) return docAssistSay("The code changed since you asked. Ask again.", { error: true });
  view.dispatch({
    changes: { from: p.from, to: p.to, insert: p.insert },
    selection: { anchor: p.from, head: p.from + p.insert.length },
    scrollIntoView: true,
    userEvent: "input.assist",
  });
  docAssist.proposal = null;
  docAssistSay("Applied. Ctrl+Z in the editor takes it out.");
  //: On a phone the sheet covers the editor: it goes, so the change shows.
  if (docKit.sheetClose) docKit.sheetClose();
  view.focus();
}

//: The deterministic tools: the editor's own commands, no model.
const DOC_ASSIST_TOOL_NAMES = {
  format_code: "Format", run_tests: "Run tests", run_file: "Run", find_usages: "Find usages",
  quick_fix: "Quick fix", symbols: "the symbols in this file",
};

function docAssistTool(tool, args = {}, { keep = false } = {}) {
  if (!docCmView) return;
  if (!keep) docAssistAnswerArea();
  //: On a phone the sheet covers the editor, where each tool shows its
  //: result (a menu at the caret, the run panel): it goes first.
  if (docKit.sheetClose) docKit.sheetClose();
  if (tool === "find_usages" && args.name) docAssistCaretTo(String(args.name));
  const run = {
    quick_fix: () => docOpenCodeFixes() || docAssistSay("No quick fix here: put the caret on an underline."),
    format_code: () => docFormatCode("auto"),
    run_tests: () => docRunCode({ mode: "test" }),
    run_file: () => docRunCode(),
    find_usages: () => docShowReferences() || docAssistSay("Put the caret on a name first."),
    symbols: () => docOpenSymbols(),
  }[tool];
  //: After the press that asked has finished: the quick fixes and the uses
  //: open as a menu at the caret, which that same click would close.
  if (run) setTimeout(run, 0);
}

function docAssistCaretTo(name) {
  const text = docCmView.state.doc.toString();
  const match = new RegExp(`\\b${name.replace(/[^\w$]/g, "")}\\b`).exec(text);
  if (match) docCmView.dispatch({ selection: { anchor: match.index }, scrollIntoView: true });
}

for (const button of document.querySelectorAll("#doc-code-assist [data-assist]")) {
  button.addEventListener("click", () => docAssistAsk(button.dataset.assist));
}
for (const button of document.querySelectorAll("#doc-code-assist [data-assist-tool]")) {
  button.addEventListener("click", () => docAssistTool(button.dataset.assistTool));
}
$("doc-assist-form").addEventListener("submit", (event) => {
  event.preventDefault();
  docAssistAsk("ask");
});
$("doc-code-assist").addEventListener("pointerenter", docAssistSyncScope);
