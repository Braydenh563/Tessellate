// Brief 71 (DOCUMENTS_PLAN 23 I3, section 25 row 6): every key on the editor's
// keybindings sheet, pressed in Chromium, and its effect asserted. The rows
// are read from the sheet itself (Ctrl+K Ctrl+S), which is drawn from the
// command table, so a row added there without an entry below fails here.
// Prose rows run on a markdown document, code rows on a JavaScript one.
// Also prints the palette's command count (Ctrl+Shift+P on a code file).
//
// Usage: BASE=http://127.0.0.1:8827 node code-keys.js
const { boot } = require("./lib.js");

let good = 0;
let bad = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};
const J = JSON.stringify;

//: The sheet's caps to Playwright's names: one entry per chord in a sequence.
function presses(keys) {
  const map = { "↑": "ArrowUp", "↓": "ArrowDown", "[": "BracketLeft", "]": "BracketRight", "\\": "Backslash", "/": "Slash", Ctrl: "Control" };
  //: A letter is pressed as written with Shift, lower case without it.
  //: A cap's own words ("F11 while debugging") are a note, not keys.
  return keys.replace(/ while debugging$/, "").split(" ").map((chord) => {
    const shift = /(^|\+)Shift\+/.test(chord);
    return chord.split("+").map((k) => map[k] || (k.length === 1 && /[a-z]/i.test(k) ? (shift ? k.toUpperCase() : k.toLowerCase()) : /^\d$/.test(k) ? `Digit${k}` : k)).join("+");
  });
}

const PROSE = "# Title\n\nhello world\n\n- one\n- two\n\n## Second\n\nmore text\n\n## Third\n\nlast\n";
const CODE = "function alpha(n) {\n  if (n) {\n    return n + 1;\n  }\n  return 0;\n}\nconst beta = alpha(2);\nconsole.log(beta);\nfunction messy(){return   1}\n";

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, permissions: ["clipboard-read", "clipboard-write"] });
  const errors = [];
  page.on("pageerror", (e) => {
    if (!/about:srcdoc|blob:null/.test(String(e.stack))) errors.push(e.message);
  });
  const saves = { n: 0 };
  page.on("request", (r) => {
    if (/\/documents\/\d+/.test(r.url()) && ["PUT", "PATCH"].includes(r.method())) saves.n += 1;
  });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const open = async (title, type, content) => {
    await page.evaluate(async ([t, f, c]) => {
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) });
      await loadDocuments(d.id);
    }, [title, type, content]);
    await page.waitForTimeout(2500);
  };
  //: Back to a known state: overlays shut, the panel and the split closed,
  //: focus mode off, the text and the caret as given.
  const reset = async (text, caretLine, caretCol = 0, selectWord = "") => {
    //: Escape shuts what is open; an arrow after it, because Escape then
    //: Tab is the editor's way out (`docTabEscapes`), not an indent.
    await page.keyboard.press("Escape").catch(() => {});
    await page.keyboard.press("ArrowLeft").catch(() => {});
    await page.evaluate(([t, line, col, word]) => {
      for (const id of ["palette-overlay", "finder-overlay", "doc-keys-overlay"]) {
        const el = document.getElementById(id);
        if (el && !el.classList.contains("hidden")) {
          if (id === "palette-overlay") closePalette();
          else if (id === "finder-overlay") closeFinder();
          else document.querySelector("#doc-keys-overlay button[aria-label=\"Close\"]")?.click();
        }
      }
      if (docRun) docRunClose();
      DOC_DEBUG.on = false;
      //: The split lives in documents-ide.js's closure (no global): the toggle (an export) closes one when its class is on.
      if (document.querySelector(".doc-split-on")) docIdeToggleSplit();
      if (document.body.classList.contains("doc-focus-mode") && typeof toggleDocFocusMode === "function") toggleDocFocusMode();
      const v = docCmView;
      if (v.state.doc.toString() !== t) v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: t } });
      const l = v.state.doc.line(line);
      let anchor = l.from + col;
      let head = anchor;
      if (word) {
        anchor = v.state.doc.toString().indexOf(word);
        head = anchor + word.length;
      }
      v.dispatch({ selection: { anchor, head } });
      v.focus();
      //: The Escape above may have reached the editor and armed its way out.
      docTabEscapes = false;
    }, [text, caretLine, caretCol, selectWord]);
    await page.waitForTimeout(250);
  };
  const snap = () => page.evaluate(() => {
    const v = docCmView;
    const visible = (sel) => [...document.querySelectorAll(sel)].filter((e) => e.getClientRects().length && getComputedStyle(e).visibility !== "hidden").length;
    return {
      text: v.state.doc.toString(),
      head: v.state.selection.main.head,
      panels: [...v.dom.querySelectorAll(".cm-panel")].map((p) => p.className).join("|"),
      tab: docRun ? docRun.tab : null,
      palette: !document.getElementById("palette-overlay").classList.contains("hidden") ? document.getElementById("palette-input").value : null,
      finder: !document.getElementById("finder-overlay")?.classList.contains("hidden"),
      keys: Boolean(document.getElementById("doc-keys-overlay") && !document.getElementById("doc-keys-overlay").classList.contains("hidden")),
      menus: visible("[role=menu], .kebab-menu"),
      tooltips: visible(".cm-tooltip"),
      folds: v.dom.querySelectorAll(".cm-foldPlaceholder").length,
      wrap: v.contentDOM.classList.contains("cm-lineWrapping"),
      split: Boolean(document.querySelector(".doc-split-on")),
      breaks: docDebugBreaks().length,
      paused: DOC_DEBUG.on && DOC_DEBUG.stop ? Number(DOC_DEBUG.stop.line) : null,
      debugOn: Boolean(DOC_DEBUG.on),
      bodyCls: document.body.className,
      tabCls: document.getElementById("tab-documents")?.className || "",
      shown: visible("#tab-documents *"),
      active: (document.activeElement?.id || "") + "." + String(document.activeElement?.className || ""),
    };
  });
  const changed = (a, b, keys) => keys.some((k) => J(a[k]) !== J(b[k]));
  const after = async (keys) => {
    for (const k of presses(keys)) {
      await page.keyboard.press(k);
      await page.waitForTimeout(120);
    }
    await page.waitForTimeout(900);
    //: A debugger key answers when the sandbox has stepped: wait for a stop.
    for (let t = 0; t < 20 && (await page.evaluate(() => DOC_DEBUG.on && !DOC_DEBUG.stop)); t++) await page.waitForTimeout(200);
    return snap();
  };

  //: Each keyed row: the document, the caret (line, column or a word to
  //: select), and what must be true after the key.
  const EXPECT = {
    underline: { on: "prose", word: "hello", check: (a, b) => b.text.includes("<u>hello</u>") },
    h4: { on: "prose", line: 10, check: (a, b) => b.text.includes("\n#### more text") },
    h5: { on: "prose", line: 10, check: (a, b) => b.text.includes("\n##### more text") },
    h6: { on: "prose", line: 10, check: (a, b) => b.text.includes("\n###### more text") },
    "move-block-up": { on: "prose", line: 6, check: (a, b) => b.text.indexOf("- two") < b.text.indexOf("- one") },
    "move-block-down": { on: "prose", line: 5, check: (a, b) => b.text.indexOf("- two") < b.text.indexOf("- one") },
    link: { on: "prose", word: "hello", check: (a, b) => /\[hello\]\(/.test(b.text) },
    "insert-emoji": { on: "prose", line: 3, check: (a, b) => changed(a, b, ["shown", "active", "menus", "tooltips"]) },
    "insert-icon": { on: "prose", line: 3, check: (a, b) => changed(a, b, ["shown", "active", "menus", "tooltips"]) },
    "insert-symbol": { on: "prose", line: 3, check: (a, b) => changed(a, b, ["shown", "active", "menus", "tooltips"]) },
    "insert-equation": { on: "prose", line: 3, check: (a, b) => changed(a, b, ["shown", "active", "menus", "tooltips", "text"]) },
    "insert-calculator": { on: "prose", line: 3, check: (a, b) => changed(a, b, ["shown", "active", "menus", "tooltips"]) },
    "paste-plain": { on: "prose", line: 3, paste: "PASTED", check: (a, b) => b.text.includes("PASTED") },
    "replace-here": { on: "prose", line: 3, check: (a, b) => changed(a, b, ["panels", "shown", "active"]) },
    "goto-line-text": { on: "prose", line: 3, check: (a, b) => changed(a, b, ["panels", "shown", "active"]) },
    "find-next": { on: "prose", line: 1, query: "text", check: (a, b) => b.head !== a.head },
    save: { on: "prose", line: 3, edit: true, check: (a, b) => saves.n > a.saves },
    find: { on: "prose", line: 3, check: (a, b) => changed(a, b, ["panels", "shown", "active"]) },
    bold: { on: "prose", word: "hello", check: (a, b) => b.text.includes("**hello**") },
    italic: { on: "prose", word: "hello", check: (a, b) => /[*_]hello[*_]/.test(b.text) && !b.text.includes("**hello**") },
    strike: { on: "prose", word: "hello", check: (a, b) => b.text.includes("~~hello~~") },
    code: { on: "prose", word: "hello", check: (a, b) => b.text.includes("`hello`") },
    h1: { on: "prose", line: 10, check: (a, b) => b.text.includes("\n# more text") },
    h2: { on: "prose", line: 10, check: (a, b) => b.text.includes("\n## more text") },
    h3: { on: "prose", line: 10, check: (a, b) => b.text.includes("\n### more text") },
    comment: { on: "prose", word: "hello", check: (a, b) => changed(a, b, ["shown", "active", "menus", "tooltips"]) },
    indent: { on: "prose", line: 6, col: 3, check: (a, b) => /\n\s+- two/.test(b.text) },
    outdent: { on: "prose", line: 6, col: 5, before: PROSE.replace("\n- two", "\n  - two"), check: (a, b) => b.text.includes("\n- two") && !/\n\s+- two/.test(b.text) },
    "move-section": { on: "prose", outline: "Third", check: (a, b) => b.text.indexOf("## Third") < b.text.indexOf("## Second") },
    ul: { on: "prose", line: 10, check: (a, b) => b.text.includes("\n- more text") },
    ol: { on: "prose", line: 10, check: (a, b) => /\n1\. more text/.test(b.text) },
    task: { on: "prose", line: 10, check: (a, b) => /\n- \[ \] more text/.test(b.text) },
    formatting: { on: "prose", line: 3, check: (a, b) => changed(a, b, ["shown", "tabCls", "bodyCls"]) },
    focus: { on: "prose", line: 3, check: (a, b) => changed(a, b, ["shown", "tabCls", "bodyCls"]) },
    format: { on: "code", line: 9, check: (a, b) => b.text !== a.text && !b.text.includes("return   1") },
    "quick-fix": { on: "code", line: 9, before: CODE.replace("const beta = alpha(2);", "const beta = alpha(2;"), lineOf: "const beta", check: (a, b) => changed(a, b, ["menus", "tooltips", "shown", "text"]) },
    "block-comment": { on: "code", word: "alpha(2)", check: (a, b) => b.text.includes("/* alpha(2) */") || b.text.includes("/*alpha(2)*/") },
    definition: { on: "code", line: 7, col: 15, check: (a, b) => b.head < a.head },
    references: { on: "code", line: 7, col: 15, check: (a, b) => changed(a, b, ["menus", "panels", "tooltips", "shown"]) },
    "find-documents": { on: "code", line: 1, check: (a, b) => changed(a, b, ["finder", "shown", "active", "palette"]) },
    run: { on: "code", line: 1, check: (a, b) => b.tab === "output" },
    "code-wrap": { on: "code", line: 1, check: (a, b) => a.wrap !== b.wrap },
    "fold-all": { on: "code", line: 1, check: (a, b) => b.folds > 0 && a.folds === 0 },
    "unfold-all": { on: "code", line: 1, folded: true, check: (a, b) => a.folds > 0 && b.folds === 0 },
    problems: { on: "code", line: 1, check: (a, b) => b.tab === "problems" },
    panel: { on: "code", line: 1, check: (a, b) => a.tab === null && b.tab !== null },
    console: { on: "code", line: 1, check: (a, b) => b.tab === "console" && /cm-console-input/.test(b.active) },
    "command-palette": { on: "code", line: 1, check: (a, b) => b.palette !== null && b.palette.startsWith(">") },
    split: { on: "code", line: 1, check: (a, b) => !a.split && b.split },
    keybindings: { on: "code", line: 1, check: (a, b) => b.keys },
    //: Brief 70's debugger keys. A session is started by the keys themselves
    //: (F9 on the line, then F5 until it pauses there) before the row's key.
    "debug-breakpoint": { on: "code", line: 3, check: (a, b) => a.breaks !== b.breaks },
    debug: { on: "code", line: 7, breakAt: 7, check: (a, b) => b.tab === "debug" && b.paused === 7 },
    "debug-over": { on: "code", line: 7, debugAt: 7, check: (a, b) => a.paused === 7 && b.paused === 8 },
    "debug-in": { on: "code", line: 7, debugAt: 7, check: (a, b) => a.paused === 7 && b.paused !== null && b.paused <= 5 },
    "debug-out": { on: "code", line: 2, debugAt: 2, check: (a, b) => a.paused === 2 && b.paused !== null && b.paused >= 7 },
    "debug-stop": { on: "code", line: 7, debugAt: 7, check: (a, b) => a.debugOn && !b.debugOn },
  };

  //: The rows, from the sheet as it draws.
  await open("keys.md", "md", PROSE);
  const sheet = await page.evaluate(() => {
    docIdeOpenKeys();
    const rows = [...document.querySelectorAll("#doc-keys-sections .wb-help-row")].map((li) => ({
      id: li.dataset.command,
      keys: [...li.querySelectorAll("kbd")].map((k) => k.textContent),
    }));
    document.querySelector("#doc-keys-overlay button[aria-label=\"Close\"]")?.click();
    return rows;
  });
  const keyed = sheet.filter((r) => r.keys.length);
  console.log(`sheet: ${sheet.length} commands, ${keyed.length} with a key`);
  ok("every keyed row has an expectation here", keyed.every((r) => EXPECT[r.id]), J(keyed.filter((r) => !EXPECT[r.id]).map((r) => r.id)));

  let exercised = 0;
  for (const on of ["prose", "code"]) {
    if (on === "code") await open("keys.js", "js", CODE);
    for (const row of keyed.filter((r) => EXPECT[r.id]?.on === on)) {
      const want = EXPECT[row.id];
      const base = want.before || (on === "prose" ? PROSE : CODE);
      let line = want.line || 1;
      if (want.lineOf) line = base.split("\n").findIndex((l) => l.includes(want.lineOf)) + 1;
      await reset(base, line, want.col || 0, want.word || "");
      if (want.edit) {
        await page.keyboard.type("x");
        await page.waitForTimeout(200);
      }
      if (want.paste) await page.evaluate((t) => navigator.clipboard.writeText(t), want.paste);
      if (want.query) await page.evaluate((q) => docCmView.dispatch({ effects: window.CM6.search.setSearchQuery.of(new window.CM6.search.SearchQuery({ search: q })) }), want.query);
      if (want.folded) await page.evaluate(() => docIdeFoldAll(false));
      if (want.breakAt || want.debugAt) {
        await page.evaluate(() => { for (const b of docDebugBreaks()) docDebugToggleAt(docCmView, docCmView.state.doc.line(b.line).from); });
        await page.keyboard.press("F9");
        await page.waitForTimeout(200);
      }
      if (want.debugAt) {
        for (let i = 0; i < 4; i++) {
          await page.keyboard.press("F5");
          for (let t = 0; t < 30; t++) {
            await page.waitForTimeout(200);
            if (await page.evaluate(() => DOC_DEBUG.on && Boolean(DOC_DEBUG.stop))) break;
          }
          if ((await page.evaluate(() => Number(DOC_DEBUG.stop?.line))) === want.debugAt) break;
        }
        await page.evaluate(() => docCmView.focus());
      }
      if (want.outline) {
        await page.evaluate(() => showDocSidebarSection("outline"));
        await page.waitForTimeout(400);
        await page.evaluate((name) => {
          const hit = [...document.querySelectorAll("#doc-outline button, #doc-outline [tabindex]")].find((e) => e.textContent.includes(name));
          hit?.focus();
        }, want.outline);
      }
      await page.waitForTimeout(300);
      const a = { ...(await snap()), saves: saves.n };
      //: Each chord in a row ("Alt+↑ / Alt+↓") is its own key: the first is
      //: pressed, and is the one checked.
      const b = await after(row.keys[0]);
      const pass = Boolean(want.check(a, b));
      ok(`${row.id} (${row.keys.join(" / ")})`, pass, pass ? undefined : J({ before: { ...a, text: a.text.slice(0, 80) }, after: { ...b, text: b.text.slice(0, 80) } }));
      if (pass) exercised += 1;
    }
  }
  console.log(`keys exercised: ${exercised}/${keyed.length}`);

  //: The palette on a code file: its rows, all the editor's.
  await reset(CODE, 1);
  await page.keyboard.press("Control+Shift+P");
  await page.waitForTimeout(900);
  const palette = await page.evaluate(() => ({
    rows: document.querySelectorAll("#palette-list [role=option]").length,
    table: docPaletteCommands().length,
    groups: [...document.querySelectorAll("#palette-list .palette-group-header")].map((g) => g.textContent),
    keyed: [...document.querySelectorAll("#palette-list [role=option]")].filter((r) => /\S/.test(r.querySelector("kbd, .rich-picker-keys, [class*=key]")?.textContent || "")).length,
  }));
  console.log(`palette commands: ${palette.rows} (the editor's ${palette.table}), ${palette.keyed} showing a key`);
  //: The palette draws its first PALETTE_WINDOW (24) rows and more as the lit row nears the end (app-palette.js), so the drawn count is the window, not the table.
  ok("the palette lists the editor's commands, a window of them, and nothing else", palette.rows === Math.min(palette.table, 24) && palette.groups.join() === "This document", J(palette));
  await page.keyboard.type("run tests");
  await page.waitForTimeout(400);
  const fuzzy = await page.evaluate(() => [...document.querySelectorAll("#palette-list [role=option]")].slice(0, 3).map((r) => r.textContent.slice(0, 60)));
  ok("fuzzy: 'run tests' finds Run the tests in this file first", /Run the tests in this file/.test(fuzzy[0] || ""), J(fuzzy));
  ok("no page errors", errors.length === 0, J(errors));
  console.log(`${good}/${good + bad}`);
  await browser.close();
})();
