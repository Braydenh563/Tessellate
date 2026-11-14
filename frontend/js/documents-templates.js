// documents-templates.js: the new-document templates and the dialog that picks one.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  const DOC_TEMPLATES = [
    {
      id: "blank", title: "Blank", hint: "An empty page.", content: "",
    },
    {
      id: "lecture", title: "Lecture notes", hint: "Cornell-style: cues, notes, summary.",
      content: "# {{title}}\n\n**Date:** {{date}}\n**Unit / lecturer:** \n\n## Key questions\n\n- \n\n## Notes\n\n\n## Terms\n\n| Term | Meaning |\n| --- | --- |\n|  |  |\n\n## Summary (three sentences)\n\n\n## To follow up\n\n- [ ] \n",
    },
    //: The writing staples (audit 1102 DX30): the gallery had no letter, report,
    //: essay, CV or one-pager, the five a word processor opens with.
    {
      id: "letter", title: "Letter", hint: "Date, greeting, body and sign-off.",
      content: "# {{title}}\n\n{{date}}\n\nDear ,\n\n\n\nYours sincerely,\n\n",
    },
    {
      id: "report", title: "Report", hint: "Summary, background, findings, recommendations.",
      content: "# {{title}}\n\n**Date:** {{date}}\n**Prepared by:** \n\n## Summary\n\n\n## Background\n\n\n## Findings\n\n1. \n\n## Recommendations\n\n- \n\n## Appendix\n\n",
    },
    {
      id: "essay", title: "Essay", hint: "Thesis, three points, conclusion, references.",
      content: "# {{title}}\n\n## Introduction\n\nThesis: \n\n## First point\n\n\n## Second point\n\n\n## Third point\n\n\n## Conclusion\n\n\n## References\n\n1. \n",
    },
    {
      id: "cv", title: "CV", hint: "Profile, experience, education, skills.",
      content: "# {{title}}\n\nEmail · Phone · Place\n\n## Profile\n\n\n## Experience\n\n### Role, company (from to)\n\n- \n\n## Education\n\n### Qualification, place (year)\n\n## Skills\n\n- \n",
    },
    {
      id: "proposal", title: "One-page proposal", hint: "The problem, the idea, why now, cost, the ask.",
      content: "# {{title}}\n\n**Date:** {{date}}\n**From:** \n\n## The problem\n\n\n## The idea\n\n\n## Why now\n\n\n## Cost and time\n\n\n## The ask\n\n",
    },
    {
      id: "assignment", group: "planning", title: "Assignment plan", hint: "Brief, criteria, sections, sources, timeline.",
      content: "# {{title}}\n\n**Due:** \n**Unit:** \n**Weight:** \n\n## The brief, in my own words\n\n\n## Marking criteria\n\n- [ ] \n- [ ] \n\n## Outline\n\n1. Introduction, \n2. \n3. \n4. Conclusion, \n\n## Sources\n\n- \n\n## Timeline\n\n| When | What |\n| --- | --- |\n| {{date}} | Plan written |\n|  | Draft |\n|  | Edit and submit |\n",
    },
    {
      id: "meeting", group: "planning", title: "Meeting notes", hint: "Attendees, agenda, decisions, actions.",
      content: "# {{title}}\n\n**Date:** {{date}}\n**Attendees:** \n\n## Agenda\n\n1. \n\n## Notes\n\n\n## Decisions\n\n- \n\n## Actions\n\n- [ ] Who, what, by when\n",
    },
    {
      id: "decision", group: "planning", title: "Decision record", hint: "Context, options, decision, consequences.",
      content: "# {{title}}\n\n**Date:** {{date}}\n**Status:** proposed\n\n## Context\n\n\n## Options considered\n\n1. \n2. \n\n## Decision\n\n\n## Consequences\n\n- \n",
    },
    {
      id: "weekly", group: "planning", title: "Weekly review", hint: "What happened, what's next, what to drop.",
      content: "# Week of {{date}}\n\n## Went well\n\n- \n\n## Didn't\n\n- \n\n## Next week\n\n- [ ] \n\n## Stop doing\n\n- \n",
    },
    //: **The day's page** (DOCUMENTS_PLAN section 14). The whole of "daily notes"
    //: on this surface is this row: the Timeline owns the journal, its endpoints,
    //: its streak and its calendar strip, and a second create-or-return here
    //: would be the second implementation of one idea. What this adds is what a
    //: document is and a note is not, for a day that grows past a capture.
    //:
    //: `docTitle` is the ISO day and not the gallery's label, because the day's
    //: page is called by its day: it is the exact string `dailyNoteTitle` writes
    //: in app.js, which is the only thing that lets the Timeline recognise a day
    //: written here as that day's page.
    {
      id: "daily", group: "planning", title: "Daily", hint: "Today's page: what happened, what is open, what is next.",
      docTitle: "{{isodate}}",
      content: "# {{isodate}}\n\n## What happened\n\n- \n\n## Still open\n\n- [ ] \n\n## Next\n\n- \n",
    },
    //: **A p5.js sketch** (INBOX 735, the owner: "since p5.js is vendored, can
    //: it be a document option in the text editor??"). A JavaScript document
    //: whose Run shows the canvas beside the code, through the vendored p5
    //: only (run-core.js finds `setup` and `createCanvas`; Brief 69, D6).
    {
      id: "p5", title: "p5.js sketch", group: "code", hint: "Code and a live canvas: Run draws it beside the editor.",
      docTitle: "Sketch {{isodate}}",
      fileType: "js",
      content: "// A p5.js sketch: Run (Ctrl+Shift+Enter) draws it in the panel below.\nfunction setup() {\n  createCanvas(400, 300);\n}\n\nfunction draw() {\n  background(240);\n  circle(mouseX, mouseY, 40);\n}\n",
    },
    //: **Code templates** (INBOX 788, the owner: "can you add code templates
    //: as document templates as well??"). One starter per language the editor
    //: runs or highlights, each a document of its own type so it opens in the
    //: code view (`fileType`), and each one that runs says how in its first
    //: lines. `group` puts them under the gallery's Code heading. Template
    //: literals, so a `${` inside the code is escaped as `\${`.
    {
      id: "py-script", group: "code", title: "Python script", hint: "A main function and a test: Run runs the test.",
      docTitle: "Script {{isodate}}", fileType: "py",
      content: `"""{{title}}: what this script does, in one line."""


def greet(name: str) -> str:
    return f"Hello, {name}"


def main() -> None:
    print(greet("world"))


# Run (Ctrl+Shift+Enter) runs a file's tests when it has any, so it runs
# this one; move the test to its own file to run main() instead.
def test_greet():
    assert greet("Ada") == "Hello, Ada"


if __name__ == "__main__":
    main()
`,
    },
    {
      id: "py-cli", group: "code", title: "Command line tool", hint: "Python with argparse: options, help and an exit code.",
      docTitle: "CLI {{isodate}}", fileType: "py",
      content: `"""{{title}}: a command line tool.

From a terminal: python cli.py --name Ada --times 2
"""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Say hello.")
    parser.add_argument("--name", default="world", help="who to greet")
    parser.add_argument("--times", type=int, default=1, help="how many times")
    parser.add_argument("-v", "--verbose", action="store_true", help="say more")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for _ in range(args.times):
        print(f"Hello, {args.name}")
    if args.verbose:
        print(f"Greeted {args.times} time(s).")
    return 0


if __name__ == "__main__":
    # The sandbox has no command line, so Run passes these arguments.
    main(["--name", "Ada", "--times", "2", "--verbose"])
`,
    },
    {
      id: "fastapi", group: "code", title: "FastAPI endpoint", hint: "A small API: a model, a read route and a create route.",
      docTitle: "API {{isodate}}", fileType: "py",
      content: `"""{{title}}: a FastAPI app.

Serve it from a terminal with fastapi and uvicorn installed:
    uvicorn app:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


ITEMS: dict[int, Item] = {}


@app.get("/items/{item_id}")
def read_item(item_id: int) -> Item:
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="Item not found")
    return ITEMS[item_id]


@app.post("/items/{item_id}", status_code=201)
def create_item(item_id: int, item: Item) -> Item:
    ITEMS[item_id] = item
    return item
`,
    },
    {
      id: "js-module", group: "code", title: "JavaScript with tests", hint: "Functions and their tests: Run runs describe, it and expect.",
      docTitle: "Module {{isodate}}", fileType: "js",
      content: `// {{title}}: functions, then their tests.
// Run (Ctrl+Shift+Enter) runs the tests with describe, it and expect.

function slugify(text) {
  return String(text)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

describe("slugify", () => {
  it("joins words with hyphens", () => {
    expect(slugify("Hello World")).toBe("hello-world");
  });

  it("drops punctuation at the ends", () => {
    expect(slugify("  Hi, there.  ")).toBe("hi-there");
  });
});
`,
    },
    {
      id: "html-page", group: "code", title: "HTML page", hint: "A page with a style and a script: Run shows it below.",
      docTitle: "Page {{isodate}}", fileType: "html",
      content: `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }
    button { padding: 0.5rem 1rem; }
  </style>
</head>
<body>
  <h1>{{title}}</h1>
  <p>Run (Ctrl+Shift+Enter) shows this page in the panel below.</p>
  <button id="count" type="button">Clicked 0 times</button>
  <script>
    let clicks = 0;
    document.getElementById("count").addEventListener("click", (event) => {
      clicks += 1;
      event.target.textContent = \`Clicked \${clicks} times\`;
    });
  </script>
</body>
</html>
`,
    },
    {
      id: "sql-schema", group: "code", title: "SQL schema", hint: "Two tables, some rows and a join: Run shows each result.",
      docTitle: "Schema {{isodate}}", fileType: "sql",
      content: `-- {{title}}: Run (Ctrl+Shift+Enter) runs each statement against an
-- empty in-memory SQLite database and shows every result as a table.

CREATE TABLE authors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors (id),
    title TEXT NOT NULL,
    published INTEGER
);

INSERT INTO authors (name) VALUES ('Ursula K. Le Guin'), ('Italo Calvino');
INSERT INTO books (author_id, title, published) VALUES
    (1, 'The Dispossessed', 1974),
    (2, 'Invisible Cities', 1972);

SELECT authors.name, books.title, books.published
FROM books
JOIN authors ON authors.id = books.author_id
ORDER BY books.published;
`,
    },
    {
      id: "readme", group: "code", title: "README", hint: "What it is, how to install, use and test it.",
      docTitle: "README",
      content: "# {{title}}\n\nOne sentence on what this is and who it is for.\n\n## Install\n\n```bash\npip install -r requirements.txt\n```\n\n## Use\n\n```bash\npython main.py --help\n```\n\n## Test\n\n```bash\npython -m pytest\n```\n\n## Licence\n\n\n",
    },
    {
      id: "notebook", group: "code", title: "Notebook", hint: "Notes and code in cells, Jupyter style, in one Python file.",
      docTitle: "Notebook {{isodate}}", fileType: "py",
      content: `# %% [markdown]
# # {{title}}
# Notes and code in one file, Jupyter style. Each \`# %%\` line starts a
# cell. Run (Ctrl+Shift+Enter) runs the file; the palette's Run the cell
# at the caret (Ctrl+Shift+P) runs one.

# %%
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
total = sum(numbers)
print(f"{len(numbers)} numbers, total {total}")

# %% [markdown]
# ## What the numbers say

# %%
mean = total / len(numbers)
print(f"mean {mean:.2f}, largest {max(numbers)}")
`,
    },
  ];
  function docTemplateFill(template, typedTitle = "") {
    const now = new Date();
    const date = now.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
    //: **`{{isodate}}` is the local day, built by hand rather than from
    //: `toISOString()`**, which converts to UTC first and so names yesterday for
    //: anyone east of it after their evening. "Today" is a fact about where the
    //: person is sitting; `routes_entries.py`'s D6 block makes the same argument
    //: for the server, which is why the day is the caller's there too.
    const iso = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
    const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const fill = (text) => (text || "").replaceAll("{{date}}", date).replaceAll("{{isodate}}", iso).replaceAll("{{time}}", time);
    //: A template's gallery label and the title it gives the document are not
    //: always the same words: "Daily" names the choice in the gallery, and the
    //: document it makes is called by its day (`docTitle`, section 14).
    //: A title the person already typed is the name they chose (audit 1028 U34).
    const title = typedTitle || (template.id === "blank" ? docNextName() : fill(template.docTitle || template.title));
    //: `{{cursor}}` is where the caret lands (the note templates' word for it): taken out here, its offset handed back as `cursor`
    //: (-1 for none) for the caller to place; a section's fill keeps only `content`.
    const text = fill(template.content).replaceAll("{{title}}", title);
    const cursor = text.indexOf("{{cursor}}");
    return {
      title,
      content: text.replaceAll("{{cursor}}", ""),
      cursor,
      //: A code template (the p5 sketch) makes a document of its own type.
      ...(template.fileType ? { file_type: template.fileType } : {}),
    };
  }
  // DOC-UNTITLED-BEGIN
  function docUntitledName(titles) {
    //: The bare "Untitled document" is number one; the next is "... 2".
    const pattern = /^untitled document(?: (\d{1,6}))?$/i;
    let top = 0;
    for (const title of titles || []) {
      const match = pattern.exec(String(title || "").trim());
      if (match) top = Math.max(top, match[1] ? Number(match[1]) : 1);
    }
    return top ? `Untitled document ${top + 1}` : "Untitled document";
  }
  function docIsUntouched(title, text) {
    return /^(?:untitled(?: document)?(?: \d{1,6})?)?$/i.test(String(title || "").trim()) && !String(text || "").trim();
  }
  // DOC-UNTITLED-END
  const docNextName = () => docUntitledName(docs.map((d) => d.title));
  async function docDropIfUntouched(nextId = null, { titled = false } = {}) {
    const doc = currentDoc;
    //: `titled`: a template is about to be made from the title the person typed, so
    //: the empty document that title started is the stray (audit 1028 U34).
    const untouched = titled ? !docText().trim() : docIsUntouched($("doc-title").value, docText());
    // Only a document made in this session: an older empty "Untitled document N" is the owner's.
    if (!doc || !docsMadeThisSession.has(doc.id) || doc.id === nextId || creatingDocument || !untouched) return;
    currentDoc = null;
    docs = docs.filter((d) => d.id !== doc.id);
    //: A delete that failed leaves the row on the server, so it goes back in the list (D36).
    await apiJson(`/documents/${doc.id}`, { method: "DELETE" }).catch(() => { docs = [doc, ...docs]; });
    renderDocList();
  }
  async function startBlankDocument(fileType = null) {
    const seq = ++docOpenSeq;
    docRememberPositionNow();
    if (docDirty) await saveDocument({ silent: true });
    await docDropIfUntouched();
    await ensureDocEditor();
    if (seq !== docOpenSeq) return;
    showNoDocument();
    //: A file of another type (New's caret): said in the empty page's own words.
    docTypeState.pending = fileType && fileType !== "md" ? fileType : null;
    if (docTypeState.pending) docSetPlaceholder(docBlankPlaceholder());
    syncDocFileType({ prose: false });
    docDirty = false;
    renderDocList();
    $("doc-title").focus();
  }
  async function createDocument(template = null) {
    if (!template) return startBlankDocument();
    //: A titled blank the person started and then swapped for a template is not
    //: left behind empty: its title carries into the template's document (U34).
    const started = currentDoc && docsMadeThisSession.has(currentDoc.id) && !docText().trim() ? $("doc-title").value.trim() : "";
    await docDropIfUntouched(null, { titled: true });
    const { cursor, ...body } = docTemplateFill(template, started && !docIsUntouched(started, "") ? started : "");
    const doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify(body),
    });
    loadCaptureDocuments(); // so Capture can attach to it straight away
    await loadDocuments(doc.id);
    offerCreateUndo(doc);
    //: A template with a `{{cursor}}` puts the caret there; without one the title is selected to be typed over.
    if (cursor >= 0 && docSurface()) {
      docSurface().focus?.();
      docSurface().setSelection(cursor);
      return;
    }
    $("doc-title").focus();
    $("doc-title").select();
  }
  let docTemplateChoice = null;
  function chooseDocTemplate(template, { focus = false } = {}) {
    if (!template) return;
    docTemplateChoice = template;
    for (const row of document.querySelectorAll("#doc-template-list .doc-template-choice")) {
      const on = row.dataset.template === template.id;
      row.setAttribute("aria-checked", String(on));
      //: The radio pattern's roving tab stop: Tab reaches the chosen row only,
      //: the arrows move between rows.
      row.tabIndex = on ? 0 : -1;
      if (on && focus) row.focus();
    }
    showDocTemplatePreview(template);
  }
  async function useDocTemplate() {
    //: A double click is a click and then a dblclick, and Enter can follow
    //: either: one document per opening, whichever way it was confirmed.
    if (docTemplateMade || !docTemplateChoice) return;
    docTemplateMade = true;
    $("doc-template-dialog")?.close();
    await createDocument(docTemplateChoice);
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { DOC_TEMPLATES, docTemplateFill, docNextName, docDropIfUntouched, startBlankDocument, createDocument, chooseDocTemplate, useDocTemplate });
})();
