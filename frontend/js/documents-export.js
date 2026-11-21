// documents-export.js: the HTML file and the PDF export (split out of
// documents.js, audit 1031 DC13).
//
// What is here: the one-file HTML export (its shell, stylesheet, inlined
// images and the run), and Print or save as PDF (the page-setup step, the
// listing a code file prints, and the run). Nothing else reads any of it.
// What stayed in documents.js is what other code shares: `docExportClean`
// (the note exporters call it), the markdown, zip and Word exports, and the
// print state a plain Ctrl+P needs before this file could ever have loaded
// (`docPrintBegin`, the `beforeprint` and `afterprint` listeners, the page
// setup read and apply).
//
// **Loaded on the first press** of either export, by the two stand-ins in
// documents.js (`exportDocumentHtml`, `exportDocumentPdf`), the way
// documents-word.js is. Its top level is declarations only.

// DOC-EXPORT-HTML-BEGIN
//: **A document as one HTML file that needs nothing else**
//: (DOCUMENTS_PLAN Phase 7, the decision recorded in that plan's section 13).
//:
//: The short version, because the shape of this code only makes sense with it:
//: there is no server-side markdown renderer in this app and the plan forbids
//: adding one, so the only faithful source of a rendered document is the
//: rendered document, which lives in `#doc-preview` in the browser. The export
//: is therefore built here, from that DOM, exactly the way the whiteboard's PNG
//: export is built from the canvas that is already drawn.
//:
//: "Self-contained" is the whole requirement and it is what most of this file
//: is about: the page that lands in somebody's downloads folder must open with
//: no network, no app, and no account. So the stylesheet is written out in
//: full below rather than the app's eleven sheets being inlined (they are 400KB
//: of tokens, docks and dialogs for a page with none of those in it), images
//: become `data:` URIs, icons and controls are dropped rather than shipped
//: broken, and a link that points back into this app loses its href and keeps
//: its words. `tests/test_document_export_html.py` is what holds that line.

//: Deliberately small and deliberately not the app's. The one thing it has to
//: get right is the reading measure and the vertical rhythm; everything else
//: is the browser's own defaults doing their job. Dark is a media query rather
//: than a choice, because the file has no settings in it and the reader's
//: system is the only preference there is.
const DOC_EXPORT_CSS = `
:root {
  color-scheme: light dark;
  --ink: #1c1d22;
  --muted: #5b6070;
  --ground: #ffffff;
  --rule: #e2e4eb;
  --inner: #f5f6f9;
  --accent: #4f6df5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e8e9ee;
    --muted: #a2a7b8;
    --ground: #16171b;
    --rule: #2c2e36;
    --inner: #1e2026;
    --accent: #8ea2ff;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 3rem 1.5rem 6rem;
  background: var(--ground);
  color: var(--ink);
  font: 16px/1.65 "Iowan Old Style", Palatino, Georgia, "Times New Roman", serif;
}
main { max-width: 42rem; margin: 0 auto; }
h1, h2, h3, h4, h5, h6 {
  margin: 2.2em 0 0.6em;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  line-height: 1.25;
}
h1 { font-size: 2rem; margin-top: 0; }
h2 { font-size: 1.5rem; }
h3 { font-size: 1.2rem; }
p, ul, ol, blockquote, table, pre { margin: 0 0 1.1em; }
a { color: var(--accent); }
img { max-width: 100%; height: auto; border-radius: 4px; }
figure { margin: 1.5em 0; }
figcaption { color: var(--muted); font-size: 0.9rem; text-align: center; }
blockquote {
  margin-left: 0;
  padding: 0.2em 0 0.2em 1em;
  border-left: 3px solid var(--rule);
  color: var(--muted);
}
code, pre, kbd { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 0.92em; }
code { padding: 0.1em 0.3em; border-radius: 3px; background: var(--inner); }
pre {
  padding: 1em;
  overflow-x: auto;
  border-radius: 6px;
  background: var(--inner);
}
pre code { padding: 0; background: none; }
table { width: 100%; border-collapse: collapse; font-size: 0.95em; }
th, td { padding: 0.45em 0.7em; border: 1px solid var(--rule); text-align: left; }
/* A plotted graph and a table of notes: the picture's own lines, not the app's tokens (documents-graph.js, documents-base.js). */
.dg-title, .db-label { color: var(--muted); font-size: 0.9rem; }
.dg-plot { border: 1px solid var(--rule); border-radius: 6px; }
.dg-svg { display: block; width: 100%; height: auto; }
.dg-svg text { fill: var(--muted); font-size: 11px; }
.dg-line, .dg-frame { stroke: var(--rule); stroke-width: 1; }
.dg-axis { stroke: var(--muted); stroke-width: 1.25; }
.dg-curve { stroke-width: 2.25; stroke-linejoin: round; stroke-linecap: round; }
.dg-key { display: flex; flex-wrap: wrap; gap: 0.8em; margin-top: 0.4em; color: var(--muted); font-size: 0.9rem; }
.db-scroll { overflow-x: auto; }
th { background: var(--inner); }
hr { height: 1px; margin: 2.5em 0; border: 0; background: var(--rule); }
ul.task-list, .task-list { list-style: none; padding-left: 1.2em; }
.md-ul-circle { list-style-type: circle; }
.md-ul-square { list-style-type: square; }
.md-ul-dash { list-style-type: "\\2013  "; }
.md-ol-a-dot { list-style-type: lower-alpha; }
.md-ol-i-dot { list-style-type: lower-roman; }
.md-ol-1-paren > li::marker { content: counter(list-item) ") "; }
input[type="checkbox"] { margin-right: 0.4em; }
.callout {
  margin: 1.5em 0;
  padding: 0.8em 1em;
  border-left: 3px solid var(--kind, var(--accent));
  border-radius: 0 6px 6px 0;
  background: var(--inner);
}
.callout-head { margin: 0 0 0.4em; font-weight: 700; list-style: none; }
.callout-head::-webkit-details-marker { display: none; }
details.callout > .callout-head::before { content: "\\25B8\\2002"; color: var(--muted); }
details.callout[open] > .callout-head::before { content: "\\25BE\\2002"; }
.callout-icon:empty { display: none; }
.callout-body > :last-child { margin-bottom: 0; }
.callout-success, .callout-tip, .callout-abstract { --kind: #2f9e6e; }
.callout-warning, .callout-question { --kind: #c98a12; }
.callout-danger, .callout-failure, .callout-bug { --kind: #d0443c; }
.callout-example { --kind: #8a5cd6; }
.callout-quote, .callout-toggle { --kind: var(--rule); }
.callout-toggle { background: none; }
.doc-cols { display: grid; grid-template-columns: repeat(var(--doc-cols, 2), minmax(0, 1fr)); gap: 1.5em; }
.doc-cols.md-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.doc-col > :first-child { margin-top: 0; }
@media (max-width: 600px) { .doc-cols { grid-template-columns: 1fr; } }
.md-rule-thick { height: 3px; }
.md-rule-dots { height: auto; background: none; text-align: center; color: var(--muted); }
.md-rule-dots::before { content: "\\2022\\2003\\2022\\2003\\2022"; }
.md-quote { margin: 1.5em 0; }
.md-quote > blockquote { margin-bottom: 0.3em; }
.md-quote-cite { padding-left: 1.2em; color: var(--muted); font-size: 0.9em; }
.md-quote-cite::before { content: "\\2013\\2002"; }
.md-toc { margin: 1.5em 0; padding: 0.8em 1em; border: 1px solid var(--rule); border-radius: 6px; }
.md-toc-head { margin: 0 0 0.4em; color: var(--muted); font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.04em; }
.md-toc-list { margin: 0; padding: 0; list-style: none; }
.md-toc-depth-1 { padding-left: 1.2em; }
.md-toc-depth-2 { padding-left: 2.4em; }
.md-toc-depth-3 { padding-left: 3.6em; }
.md-math-block { margin: 1.5em 0; text-align: center; overflow-x: auto; }
.md-page-break { break-before: page; height: 0; overflow: hidden; }
.md-page-break > span { display: none; }
.md-footnotes {
  margin-top: 3em;
  padding-top: 1em;
  border-top: 1px solid var(--rule);
  color: var(--muted);
  font-size: 0.9em;
}
.doc-export-missing { color: var(--muted); font-style: italic; }
.doc-export-link { border-bottom: 1px dotted var(--rule); }
.doc-export-meta {
  margin: 0 0 2.5em;
  color: var(--muted);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 0.85rem;
}
.md-mermaid { margin: 1.2em 0; overflow-x: auto; color: var(--ink); }
.md-mermaid img { display: block; max-width: 100%; height: auto; margin: 0 auto; }
.md-mermaid-reason { color: var(--muted); font-size: 0.85em; }
`;

function docExportEscape(text) {
  return String(text == null ? "" : text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

//: No `<h1>` of the title above the body: a document here almost always opens
//: with its own heading, and printing the title again would give every
//: exported page a duplicated first line. The name travels in `<title>`, which
//: is what names a tab, a bookmark and a saved file.
//:
//: The meta line is one line and it is the provenance: what this was and when
//: it was taken. Without it an exported page is undated, and a document that
//: is edited weekly becomes several undated files with the same name.
function docExportHtmlDocument(title, bodyHtml, savedOn, extraCss = "") {
  const name = docExportEscape(title || "Untitled document");
  const meta = savedOn ? `<p class="doc-export-meta">${docExportEscape(savedOn)}</p>\n` : "";
  return (
    "<!doctype html>\n" +
    '<html lang="en">\n<head>\n<meta charset="utf-8">\n' +
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n' +
    `<title>${name}</title>\n<style>${DOC_EXPORT_CSS}${extraCss}</style>\n</head>\n` +
    `<body>\n<main>\n${meta}${bodyHtml}\n</main>\n</body>\n</html>\n`
  );
}
// DOC-EXPORT-HTML-END

// DOC-SLIDES-BEGIN
//: **A document as a slide deck** (DOCUMENTS_PLAN gap row 15), through the
//: HTML export's own shell and the same cleaned copy of the rendered page.
//: A level-1 or level-2 heading starts a slide and so does a horizontal rule
//: (which is not drawn); everything up to the next one is that slide. Pure, so
//: it runs in node (`tests/test_doc_slides.py`): `blocks` is
//: `[{tag, html}]`, the page's top-level elements in order.
docExportHtmlDocument.slides = (blocks) => {
  const slides = [];
  let open = [];
  const close = () => {
    if (open.length) slides.push(open.join("\n"));
    open = [];
  };
  for (const { tag, html } of blocks) {
    if (tag === "HR") close();
    else {
      if (tag === "H1" || tag === "H2") close();
      open.push(html);
    }
  }
  close();
  return slides;
};

//: One slide on screen at a time, a sheet each when printed. The file has no
//: settings, so the colours are the export's own (`DOC_EXPORT_CSS`).
docExportHtmlDocument.deckCss = `
body { padding: 0; overflow: hidden; }
main { max-width: none; margin: 0; }
.slide { display: none; box-sizing: border-box; min-height: 100vh; padding: 6vh 8vw; font-size: clamp(1.1rem, 2.4vw, 2rem); overflow: auto; }
.slide.on { display: block; }
.slide h1, .slide h2 { margin-top: 0; }
.deck-count { position: fixed; right: 1rem; bottom: 0.6rem; color: var(--muted); font: 0.85rem system-ui, sans-serif; }
@media print {
  body { overflow: visible; }
  .slide { display: block; min-height: 0; page-break-after: always; break-after: page; }
  .deck-count { display: none; }
}
`;

//: Arrow keys, Page Up and Down, space, Home and End, or a click on the right
//: or left half; the slide number is in the address so a refresh keeps place.
docExportHtmlDocument.deckScript = `(function () {
  var slides = [].slice.call(document.querySelectorAll(".slide")), at = 0, count = document.querySelector(".deck-count");
  function show(n) {
    at = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function (s, k) { s.classList.toggle("on", k === at); });
    count.textContent = (at + 1) + " / " + slides.length;
    history.replaceState(null, "", "#" + (at + 1));
  }
  document.addEventListener("keydown", function (e) {
    var k = e.key;
    if (k === "ArrowRight" || k === "PageDown" || k === " ") show(at + 1);
    else if (k === "ArrowLeft" || k === "PageUp") show(at - 1);
    else if (k === "Home") show(0);
    else if (k === "End") show(slides.length - 1);
    else return;
    e.preventDefault();
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest("a")) show(e.clientX > window.innerWidth / 2 ? at + 1 : at - 1);
  });
  show((parseInt(location.hash.slice(1), 10) || 1) - 1);
})();`;

//: The whole file: the cleaned copy of the page cut into slides.
docExportHtmlDocument.deck = (title, clone, iconCss) => {
  //: The page's own title line is the first slide's heading, unless the
  //: document opens with a heading of its own (then it would be said twice).
  const kids = [...clone.children];
  const own = (el, k) => el.classList.contains("doc-preview-title") && kids[k + 1]?.tagName === "H1";
  const blocks = kids.filter((el, k) => !own(el, k)).map((el) => ({ tag: el.tagName, html: el.outerHTML }));
  const cut = docExportHtmlDocument.slides(blocks);
  const sheets = cut.map((html, k) => `<section class="slide" aria-label="Slide ${k + 1} of ${cut.length}">${html}</section>`);
  const body = `${sheets.join("\n")}\n<div class="deck-count" aria-live="polite"></div>\n<script>${docExportHtmlDocument.deckScript}</script>`;
  return docExportHtmlDocument(title, body, "", iconCss + docExportHtmlDocument.deckCss);
};
// DOC-SLIDES-END

//: **A `:ph-name:` icon travels as its glyph** (INBOX 1545), with the font that
//: draws it written into the file once, as a `data:` URI, and only when the
//: page has an icon. Run on the clone before `docExportClean`, which drops the
//: app's own `i.ph` because its font is not in the file. Returns the CSS to add.
//: A property of `docExportHtmlDocument`, not a new name in the shared scope.
//: Every glyph is read first and the swaps made after: reading a pseudo-element
//: between writes would lay the page out once per icon.
docExportHtmlDocument.icons = async (root, clone) => {
  const copies = [...clone.querySelectorAll("i.md-inline-icon")];
  const glyphs = [...root.querySelectorAll("i.md-inline-icon")].map((icon) => [icon.getAttribute("aria-label"), getComputedStyle(icon, "::before").content.slice(1, -1)]);
  glyphs.forEach(([label, char], at) => {
    const glyph = document.createElement("span");
    glyph.className = "doc-export-icon";
    glyph.setAttribute("role", "img");
    glyph.setAttribute("aria-label", label);
    glyph.textContent = char;
    copies[at].replaceWith(glyph);
  });
  if (!copies.length) return "";
  const font = await (await fetch("/vendor/phosphor/Phosphor-full.woff2")).blob();
  const url = await new Promise((resolve) => Object.assign(new FileReader(), { onload: (e) => resolve(e.target.result) }).readAsDataURL(font));
  return `@font-face{font-family:"Phosphor";src:url(${url}) format("woff2")}.doc-export-icon{font-family:"Phosphor";font-style:normal;line-height:1}`;
};

//: Eight megabytes of data URIs is a file that opens; eighty is one that
//: hangs the tab it is dropped into. Past the budget an image becomes its own
//: alt text, which says what was there rather than drawing a broken frame.
const DOC_EXPORT_IMAGE_BUDGET = 8 * 1024 * 1024;

async function docExportInlineImages(root) {
  let spent = 0;
  let inlined = 0;
  let dropped = 0;
  for (const img of [...root.querySelectorAll("img")]) {
    const src = img.getAttribute("src") || "";
    if (src.startsWith("data:")) {
      inlined++;
      continue;
    }
    let dataUri = null;
    if (src && !/^https?:/i.test(src) && spent < DOC_EXPORT_IMAGE_BUDGET) {
      try {
        // `api()` (F5), silent: a picture that will not load is dropped below.
        const response = await api(src, { silent: true });
        {
          const blob = await response.blob();
          if (spent + blob.size <= DOC_EXPORT_IMAGE_BUDGET) {
            dataUri = `data:${blob.type || "application/octet-stream"};base64,${await blobToBase64(blob)}`;
            spent += blob.size;
          }
        }
      } catch {
        // A file that cannot be read is a file that cannot be embedded; the
        // alt text below says so rather than the export failing over it.
      }
    }
    if (dataUri) {
      img.setAttribute("src", dataUri);
      img.removeAttribute("srcset");
      img.removeAttribute("loading");
      inlined++;
    } else {
      const note = document.createElement("span");
      note.className = "doc-export-missing";
      note.textContent = `[image: ${img.getAttribute("alt") || "not included"}]`;
      img.replaceWith(note);
      dropped++;
    }
  }
  return { inlined, dropped, bytes: spent };
}

//: A ```base block reads its rows from the server after the preview is drawn, so a file saved at once would hold its "Reading the
//: notes" line instead of the table. Wait until none is left, for three seconds at most (the table is a read of a list, not a job).
//: A property of the run, not a name of its own: the shared scope's name count has no slack.
docExportHtmlRun.settled = async (root) => {
  const waiting = () => [...root.querySelectorAll(".db-empty")].some((n) => n.textContent === "Reading the notes");
  for (let tries = 0; tries < 30 && waiting(); tries++) await new Promise((resolve) => setTimeout(resolve, 100));
};

async function docExportHtmlRun(slides = false) {
  if (!currentDoc || (slides && !docFileType().previewable)) return;
  const status = $("doc-status");
  //: No rendered form means the preview is empty: the page came out as the
  //: title line alone. The source goes in as preformatted text instead.
  if (!docFileType().previewable) {
    const source = docSurface()?.value ?? currentDoc.content ?? "";
    const savedOn = `${currentDoc.title || "Untitled"} · exported ${new Date().toLocaleDateString()}`;
    const html = docExportHtmlDocument(currentDoc.title, `<pre><code>${docExportEscape(source)}</code></pre>`, savedOn);
    await saveFile(docExportName(currentDoc.title, "html"), new Blob([html], { type: "text/html" }));
    return;
  }
  //: The remarks travel as footnotes, exactly as they do in a PDF: a document
  //: handed to somebody carries what was said about it rather than dropping it
  //: silently. Set before `withDocPreviewShown`, which renders on the way in.
  docPrintComments = true;
  let done;
  const finished = new Promise((resolve) => {
    done = resolve;
  });
  withDocPreviewShown(async (restore) => {
    try {
      await docMermaidWhenDrawn();
      await docExportHtmlRun.settled($("doc-preview"));
      const clone = $("doc-preview").cloneNode(true);
      clone.removeAttribute("id");
      clone.removeAttribute("class");
      //: A saved file outlives this page's blob: URLs, so each diagram goes in as
      //: a data: URL of its own SVG, before the image pass below can drop it.
      if (await lazyModuleLoads.get("mermaid")) mermaidInlineForExport($("doc-preview"), clone);
      const iconCss = await docExportHtmlDocument.icons($("doc-preview"), clone);
      docExportClean(clone);
      const images = await docExportInlineImages(clone);
      const savedOn = `${currentDoc.title || "Untitled"} · exported ${new Date().toLocaleDateString()}`;
      const html = slides
        ? docExportHtmlDocument.deck(currentDoc.title, clone, iconCss)
        : docExportHtmlDocument(currentDoc.title, clone.innerHTML, savedOn, iconCss);
      await saveFile(docExportName(slides ? `${currentDoc.title || "Untitled"} slides` : currentDoc.title, "html"), new Blob([html], { type: "text/html" }));
      if (images.dropped) {
        toast(`Saved. ${images.dropped} image(s) could not be embedded and are named in the text.`);
      }
    } catch (error) {
      if (status) {
        status.classList.add("error");
        status.textContent = error.message || "Couldn't export this document.";
      }
    } finally {
      docPrintComments = false;
      restore();
      renderDocPreview();
      done();
    }
  });
  return finished;
}

//: The one step before the browser's dialog: four choices and Print.
function docPrintSetupDialog() {
  return new Promise((resolve) => {
    const setup = docPrintSetupRead();
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Print or save as PDF");
    const card = document.createElement("div");
    card.className = "card modal-card space-dialog doc-print-card";
    const returnFocus = document.activeElement;
    let settled = false;
    const close = (go) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      if (!go) returnFocus?.focus?.();
      resolve(go ? setup : null);
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close(false);
      } else if (event.key === "Enter" && !(event.target instanceof HTMLButtonElement)) {
        event.preventDefault();
        event.stopPropagation();
        close(true);
      }
    };
    const seg = (label, key, options) => {
      const row = document.createElement("div");
      row.className = "doc-print-row";
      const name = document.createElement("span");
      name.className = "doc-print-label";
      name.textContent = label;
      const group = document.createElement("div");
      group.className = "seg";
      group.setAttribute("role", "group");
      group.setAttribute("aria-label", label);
      for (const [value, words] of options) {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = words;
        b.dataset.value = value;
        b.setAttribute("aria-pressed", String(setup[key] === value));
        b.classList.toggle("active", setup[key] === value);
        b.addEventListener("click", () => {
          setup[key] = value;
          for (const other of group.children) {
            other.setAttribute("aria-pressed", String(other === b));
            other.classList.toggle("active", other === b);
          }
        });
        group.appendChild(b);
      }
      row.append(name, group);
      return row;
    };
    const numbers = document.createElement("label");
    numbers.className = "setting-check doc-print-numbers";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = "doc-print-numbers";
    const can = docPrintMarginBoxes();
    box.checked = setup.numbers && can;
    box.disabled = !can;
    box.addEventListener("change", () => { setup.numbers = box.checked; });
    const words = document.createElement("span");
    words.textContent = "Page numbers and the title";
    const small = document.createElement("small");
    small.className = "muted";
    small.textContent = can
      ? "The number at the foot of each page, the title at the head."
      : "This browser cannot print them; your print dialog's own headers and footers can.";
    words.append(document.createElement("br"), small);
    numbers.append(box, words);
    const foot = document.createElement("div");
    foot.className = "row space-dialog-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ghost";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => close(false));
    const go = document.createElement("button");
    go.type = "button";
    go.id = "doc-print-go";
    setLabel(go, "ph:printer Print");
    go.addEventListener("click", () => close(true));
    foot.append(cancel, go);
    const body = document.createElement("div");
    body.className = "doc-print-body";
    body.append(
      seg("Page size", "size", [["A4", "A4"], ["Letter", "Letter"]]),
      seg("Orientation", "orientation", [["portrait", "Portrait"], ["landscape", "Landscape"]]),
      seg("Margins", "margin", [["narrow", "Narrow"], ["normal", "Normal"], ["wide", "Wide"]]),
      numbers,
    );
    card.append(dialogHead("Print or save as PDF", () => close(false)), body, foot);
    overlay.appendChild(card);
    wireBackdropClose(overlay, () => close(false));
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(overlay);
    go.focus();
  }).then((setup) => {
    if (!setup) return null;
    try {
      prefs.set(DOC_PRINT_KEY, JSON.stringify(setup));
    } catch {
      /* this print still uses it */
    }
    return setup;
  });
}

//: The menu's print of a code file: the listing in the preview pane, the
//: print class on for as long as the browser's dialog is open.
function docCodePrintNow() {
  docCodePrintFill();
  document.body.classList.add("printing-doc");
  const cleanup = () => {
    document.body.classList.remove("printing-doc");
    docCodePrintClear();
    window.removeEventListener("afterprint", cleanup);
  };
  window.addEventListener("afterprint", cleanup);
  setTimeout(() => window.print(), 150);
}

// PDF via the browser's own print dialog: it renders the preview exactly as
// shown and every platform already has "Save as PDF" there. Bundling a PDF
// engine would add a heavy dependency to produce a worse-looking result.
async function docExportPdfRun() {
  if (!currentDoc) return;
  const setup = await docPrintSetupDialog();
  if (!setup) return;
  docApplyPrintSetup(setup);
  //: A code file has no rendered form to show: it prints its listing.
  if (docIsCodeFile()) return docCodePrintNow();
  //: Set *before* `withDocPreviewShown`, which renders the pane on the way in:
  //: the whole point of the flag is that the render it triggers is the one that
  //: carries the footnotes (DOCUMENTS_PLAN Phase 5 item 1, "exported as
  //: footnotes"). Cleared in the same place the print class is, and the pane is
  //: drawn once more on the way out so what is left on screen after the dialog
  //: closes is Read view again, without the remarks in it.
  docPrintComments = true;
  withDocPreviewShown((restore) => {
    document.body.classList.add("printing-doc");
    const cleanup = () => {
      document.body.classList.remove("printing-doc");
      docPrintComments = false;
      restore();
      renderDocPreview();
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    //: A diagram still being drawn would print as its placeholder.
    docMermaidWhenDrawn().then(() => setTimeout(() => window.print(), 150));
  });
}
