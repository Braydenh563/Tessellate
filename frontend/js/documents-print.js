// documents-print.js: a plain Ctrl+P and the page a document prints on (split
// out of documents.js, audit 1031 DC13 remainder).
//
// What is here: the print state a plain Ctrl+P needs before documents-export.js
// could ever have loaded (`docPrintBegin`, the `beforeprint` and `afterprint`
// listeners, the rows a code file prints) and the page setup (`docPrintSetupRead`,
// `docApplyPrintSetup`, the constructed stylesheet). What stayed in
// documents.js: `docPhase2State.printSheet`, the one sheet the setup writes, and
// `docPrintComments`, which documents-export.js sets; documents-export.js reads
// the exports at the foot from inside functions.
//
// **Loaded in the Library bundle, before documents.js**, the way
// documents-props.js is: this file's own top level declares functions and binds
// the two print listeners, whose handlers reach `setDocView` and the surface
// only when a print starts. One closure; what other files call is the
// `Object.assign` at the foot.
(() => {
  //: **A plain Ctrl+P prints the document, not the application**
  //: (DOCUMENTS_PLAN Phase 5 item 4, the print stylesheet).
  //:
  //: The Export menu's "Print or save as PDF" already did the right thing: it
  //: shows the preview, sets `printing-doc` and calls `window.print()`. Nothing
  //: covered the other door, which is the one most people use. Measured on the
  //: branch head with `emulateMedia({ media: "print" })`, a plain print from the
  //: editor put the tab bar (693x44), the sidebar (260x767), the dock (1082x78)
  //: and the status bar (1082x38) on the page around the text.
  //:
  //: So the class is set for *any* print of an open document, and the same
  //: stylesheet governs both routes. Two things it deliberately does not do:
  //: it does not set `docPrintComments`, because a plain print was not asked for
  //: footnotes, and it does not touch a print started from anywhere else in the
  //: app, which is somebody printing a different surface.
  //:
  //: `withDocPreviewShown` cannot be used here: it takes a callback and restores
  //: on the way out, and `beforeprint` has to leave the pane shown until
  //: `afterprint`. The same two calls are made by hand, which is why the restore
  //: is remembered rather than derived.
  let docPrintRestore = null;

  function docPrintIsOurs() {
    if (!currentDoc) return false;
    try {
      return prefs.get("activeTab", null) === "documents";
    } catch {
      //: Private mode: the tab the reader is on is still knowable from the DOM,
      //: and printing the chrome is worse than printing the document.
      return !$("tab-documents")?.classList.contains("hidden");
    }
  }

  //: The lines a code file prints: one row per line, and the newline that ends
  //: the last one is not a row of its own.
  function docCodePrintRows(text) {
    const value = String(text || "").replace(/\r\n?/g, "\n");
    if (!value) return [];
    const rows = value.split("\n");
    if (rows[rows.length - 1] === "") rows.pop();
    return rows;
  }

  //: **A code file prints as code** (the owner's dogfood, 2026-10-26: "no print
  //: or export path for code files"). It has no rendered form, so the preview
  //: pane that every prose print goes through is filled with a listing instead:
  //: one row per line, the line number in a column of its own, the text
  //: monospaced and wrapping inside its row. The same pane, the same page setup
  //: and the same `printing-doc` rules (the editor, the dock and the panels go),
  //: so Ctrl+P and the menu's Print or save as PDF put the same page on paper.
  //: Measured before: a plain Ctrl+P printed the live editor, 1408px wide and
  //: only as much of a long file as the editor had drawn.
  function docCodePrintFill() {
    const rows = docCodePrintRows(docText());
    const listing = document.createElement("div");
    listing.className = "doc-code-print";
    //: The number column is as wide as the last number, set on each row (the
    //: stylesheet's own 3ch is the width before it is known).
    const columns = `${String(rows.length).length}ch minmax(0, 1fr)`;
    const frame = document.createDocumentFragment();
    rows.forEach((line, index) => {
      const row = document.createElement("div");
      row.className = "doc-code-print-line";
      row.style.gridTemplateColumns = columns;
      const number = document.createElement("span");
      number.className = "doc-code-print-no";
      number.textContent = String(index + 1);
      const text = document.createElement("span");
      text.className = "doc-code-print-text";
      text.textContent = line;
      row.append(number, text);
      frame.appendChild(row);
    });
    listing.appendChild(frame);
    $("doc-preview").replaceChildren(listing);
    document.body.classList.add("printing-code");
  }

  function docCodePrintClear() {
    document.body.classList.remove("printing-code");
    $("doc-preview").replaceChildren();
  }

  //: The start of a plain Ctrl+P: the page the print will show, and the class
  //: that lets the print stylesheet take the application away.
  function docPrintBegin() {
    if (docIsCodeFile()) {
      docCodePrintFill();
      docPrintRestore = docCodePrintClear;
    } else {
      const wasView = docView;
      if (docView !== "rendered") {
        setDocView("rendered");
        docPrintRestore = () => setDocView(wasView);
      }
      renderDocPreview();
    }
    //: A plain Ctrl+P prints on the page last chosen (decision 7).
    docApplyPrintSetup();
    document.body.classList.add("printing-doc");
  }

  window.addEventListener("beforeprint", () => {
    //: Already set means the Export menu started this print and has its own
    //: cleanup, including the footnotes it asked for. Left alone entirely.
    if (document.body.classList.contains("printing-doc")) return;
    if (!docPrintIsOurs()) return;
    docPrintBegin();
  });

  window.addEventListener("afterprint", () => {
    if (!docPrintRestore && !document.body.classList.contains("printing-doc")) return;
    document.body.classList.remove("printing-doc");
    const restore = docPrintRestore;
    docPrintRestore = null;
    restore?.();
  });

  //: **The page a document prints on** (DOCUMENTS_PLAN decision 7, the audit's
  //: D4): size, orientation, margins, and the page number and title in the
  //: page's own margin, chosen in one step before the browser's print dialog and
  //: remembered on this computer. Written as a constructed stylesheet
  //: (`adoptedStyleSheets`), because the CSP refuses a `<style>` element and an
  //: `@page` rule has no element to put a class on. The number and the title are
  //: CSS page-margin boxes (`@bottom-center`, `@top-center`), which Chromium
  //: draws from version 131; where the browser has no `CSSMarginRule` the
  //: switch says it cannot, rather than printing nothing silently.
  const DOC_PRINT_KEY = "docPrintSetup";
  const DOC_PRINT_MARGINS = { narrow: "12mm", normal: "20mm", wide: "28mm" };

  function docPrintSetupRead() {
    const saved = prefs.json(DOC_PRINT_KEY, {});
    //: Letter where the reader's own locale says it (the US and Canada print on
    //: it), A4 everywhere else, until they choose.
    const letter = /-(US|CA)$/i.test(navigator.language || "");
    return {
      size: saved.size === "Letter" || saved.size === "A4" ? saved.size : letter ? "Letter" : "A4",
      orientation: saved.orientation === "landscape" ? "landscape" : "portrait",
      margin: DOC_PRINT_MARGINS[saved.margin] ? saved.margin : "normal",
      numbers: saved.numbers !== false,
    };
  }

  function docPrintMarginBoxes() {
    return typeof window.CSSMarginRule === "function";
  }

  //: A title as a CSS string: quotes and backslashes escaped, line breaks gone.
  function docPrintCssString(text) {
    return `"${String(text || "").replace(/[\\"]/g, "\\$&").replace(/[\r\n]+/g, " ").slice(0, 120)}"`;
  }

  function docApplyPrintSetup(setup = docPrintSetupRead(), title = currentDoc?.title || "") {
    if (typeof CSSStyleSheet !== "function" || !("adoptedStyleSheets" in document)) return false;
    if (!docPhase2State.printSheet) {
      docPhase2State.printSheet = new CSSStyleSheet();
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, docPhase2State.printSheet];
    }
    const boxes = setup.numbers && docPrintMarginBoxes()
      ? ` @top-center { content: ${docPrintCssString(title)}; font: 9pt system-ui, sans-serif; color: #555; }` +
        ` @bottom-center { content: counter(page) " / " counter(pages); font: 9pt system-ui, sans-serif; color: #555; }`
      : "";
    docPhase2State.printSheet.replaceSync(`@media print { @page { size: ${setup.size} ${setup.orientation}; margin: ${DOC_PRINT_MARGINS[setup.margin]};${boxes} } }`);
    return true;
  }

  //: The file's whole surface: what documents.js and documents-cm.js call.
  Object.assign(window, { docCodePrintFill, docCodePrintClear, DOC_PRINT_KEY, docPrintSetupRead, docPrintMarginBoxes, docApplyPrintSetup });
})();
