// INBOX 788 (DOCUMENTS_PLAN "Placed from INBOX, 2026-10-10 (code as
// documents)"): code templates in New document, the snippets library, the
// coding assistant panel and the code view's width, driven in Chromium.
//
// Usage: BASE=http://127.0.0.1:8854 [WIDTH=390] [ONLY=templates,width] node codedocs.js
const { boot } = require("./lib.js");

const WIDTH = Number(process.env.WIDTH || 1440);
const ONLY = (process.env.ONLY || "").split(",").filter(Boolean);
const want = (name) => !ONLY.length || ONLY.includes(name);
let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};
const J = JSON.stringify;
//: A name of this run's own, so a second run on the same data dir counts
//: only what it saved.
const SNIP = `Sum a range ${Date.now() % 100000}`;

(async () => {
  const phone = WIDTH < 600;
  const { browser, page } = await boot(phone
    ? { viewport: { width: WIDTH, height: 844 }, hasTouch: true, isMobile: true }
    : { viewport: { width: WIDTH, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => {
    if (!/about:srcdoc|blob:null/.test(String(e.stack))) errors.push(e.message);
  });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2500);
  const open = async (title, fileType, content) => {
    await page.evaluate(async ([t, f, c]) => {
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) });
      await loadDocuments(d.id);
    }, [title, fileType, content]);
    await page.waitForTimeout(1500);
  };

  if (want("templates")) {
    await page.evaluate(() => openDocTemplateDialog());
    await page.waitForTimeout(400);
    const dlg = await page.evaluate(() => {
      const d = document.getElementById("doc-template-dialog");
      const box = d.getBoundingClientRect();
      const heads = [...d.querySelectorAll(".doc-template-group")].map((h) => h.textContent);
      const rows = [...d.querySelectorAll(".doc-template-choice")];
      const list = document.getElementById("doc-template-list");
      return {
        open: d.open, heads, rows: rows.length,
        code: rows.filter((r) => ["py-script", "py-cli", "fastapi", "js-module", "html-page", "sql-schema", "readme", "notebook", "p5"].includes(r.dataset.template)).length,
        inView: box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight,
        listScrolls: list.scrollHeight > list.clientHeight,
        pageScroll: document.documentElement.scrollWidth > innerWidth,
      };
    });
    ok("template dialog open with Writing, Planning and Code heads", dlg.open && J(dlg.heads) === J(["Writing", "Planning", "Code"]), J(dlg));
    ok("nine code templates listed", dlg.code === 9, dlg.code);
    ok("dialog inside the viewport, no page scroll", dlg.inView && !dlg.pageScroll, J(dlg));
    for (const [id, ext] of [["py-script", "py"], ["sql-schema", "sql"], ["html-page", "html"], ["js-module", "js"], ["notebook", "py"]]) {
      await page.evaluate(() => openDocTemplateDialog());
      await page.waitForTimeout(300);
      await page.click(`.doc-template-choice[data-template="${id}"]`);
      const shown = await page.evaluate(() => document.querySelector("#doc-template-preview pre, #doc-template-preview code") !== null);
      await page.click("#doc-template-use");
      await page.waitForTimeout(1800);
      const made = await page.evaluate(() => ({
        type: currentDoc && currentDoc.file_type,
        code: !!document.querySelector(".cm-editor.doc-content-code"),
        lines: document.querySelectorAll(".cm-line").length,
      }));
      ok(`${id}: previews as code, opens in the code view as .${ext}`, shown && made.type === ext && made.code && made.lines > 5, J(made));
    }
  }

  if (want("snippets")) {
    await open("Snippet probe", "py", "def main():\n    total = 0\n    for n in range(3):\n        total += n\n    return total\n");
    const showTab = async () => {
      const open = await page.evaluate(() => !document.getElementById("doc-code-side").classList.contains("hidden"));
      if (!open) await page.click("#doc-code-snippets-open");
      await page.waitForTimeout(900);
    };
    await showTab();
    const tab = await page.evaluate(() => {
      const list = document.getElementById("doc-snippet-list");
      const side = document.getElementById("doc-code-side");
      const b = side.getBoundingClientRect();
      const ed = document.querySelector(".cm-editor").getBoundingClientRect();
      const wrap = document.getElementById("doc-source-wrap").getBoundingClientRect();
      const dock = document.getElementById("doc-code-snippets-open").getBoundingClientRect();
      return {
        shown: b.width > 0 && b.height > 0,
        heads: [...list.querySelectorAll(".doc-snippet-group")].map((h) => h.textContent),
        rows: list.querySelectorAll(".doc-snippet-row").length,
        inView: b.left >= 0 && b.right <= innerWidth + 1 && b.bottom <= innerHeight + 1,
        clipped: [...list.querySelectorAll(".doc-snippet-name")].filter((r) => r.getBoundingClientRect().right > b.right + 1).length,
        rowH: Math.round(list.querySelector(".doc-snippet-row")?.getBoundingClientRect().height || 0),
        side: [Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)],
        editor: [Math.round(ed.x), Math.round(ed.y), Math.round(ed.width), Math.round(ed.height)],
        wrapW: Math.round(wrap.width),
        overlap: !(b.left >= ed.right - 1 || b.top >= ed.bottom - 1),
        dockBtn: [Math.round(dock.x), Math.round(dock.width)],
        expanded: document.getElementById("doc-code-snippets-open").getAttribute("aria-expanded"),
        pageScroll: document.documentElement.scrollWidth > innerWidth,
        sheet: !!side.closest(".sheet-card"),
      };
    });
    console.log("panel", J(tab));
    if (phone) ok("on a phone the panel is a bottom sheet inside the window", tab.shown && tab.sheet && tab.inView && !tab.pageScroll, J(tab));
    else ok("the panel sits beside the editor without covering it", tab.shown && !tab.sheet && !tab.overlap && !tab.pageScroll && tab.editor[2] >= 600, J(tab));
    ok("Snippets tab lists this file's language first", tab.shown && tab.heads[0] === "Python, this file" && tab.rows >= 5, J(tab));
    ok("snippet rows inside the panel, none past its edge", tab.inView && tab.clipped === 0 && tab.rowH >= 36 && tab.expanded === "true", J(tab));
    await page.fill("#doc-snippet-search", "loop");
    await page.waitForTimeout(200);
    const found = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-group")].map((h) => h.textContent).length);
    ok("search reaches every language", found > 3, found);
    await page.fill("#doc-snippet-search", "");
    // Insert a built-in at the end of the file, then undo it.
    await page.evaluate(() => { const v = docCmView; v.dispatch({ selection: { anchor: v.state.doc.length } }); });
    const before = await page.evaluate(() => docText());
    if (!phone) await page.click('#doc-snippet-list .doc-snippet-row[data-key="builtin:py:readfile"]');
    else await page.evaluate(() => document.querySelector('#doc-snippet-list .doc-snippet-row[data-key="builtin:py:readfile"]').click());
    await page.waitForTimeout(300);
    const after = await page.evaluate(() => docText());
    ok("a built-in row inserts at the caret", after.length > before.length && /read_text/.test(after.slice(before.length)), J(after.slice(before.length)));
    await page.evaluate(() => { CM6.commands.undo(docCmView); });
    await page.waitForTimeout(200);
    ok("one Ctrl+Z takes the insert out", (await page.evaluate(() => docText())) === before);
    // Save the selection as a snippet, with a tag, then undo the save.
    await page.evaluate(() => { const v = docCmView; v.dispatch({ selection: { anchor: 0, head: v.state.doc.line(5).to } }); });
    await page.evaluate((n) => { window.__snip = n; }, SNIP);
    await page.evaluate(() => { window.__prompt = promptDialog; promptDialog = async () => `${window.__snip} #loops`; });
    await page.evaluate(() => document.getElementById("doc-snippet-save").click());
    await page.waitForTimeout(1200);
    const saved = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-item")].map((li) => li.textContent).filter((t) => t.includes(window.__snip)));
    ok("Save selection adds a tagged row", saved.length === 1 && saved[0].includes("#loops"), J(saved));
    await page.evaluate(() => performUndo());
    await page.waitForTimeout(1200);
    const undone = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-name")].filter((n) => n.textContent === window.__snip).length);
    ok("Undo takes the saved snippet back out", undone === 0, undone);
    await page.evaluate(() => performRedo());
    await page.waitForTimeout(1200);
    const redone = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-name")].filter((n) => n.textContent === window.__snip).length);
    ok("Redo restores it", redone === 1, redone);
    // Delete through its menu, then undo.
    await page.evaluate(() => {
      const li = [...document.querySelectorAll("#doc-snippet-list .doc-snippet-item")].find((x) => x.textContent.includes(window.__snip));
      li.querySelector(".menu-wrap").rowMenu.items.find((i) => /Delete/.test(i.label)).run();
    });
    await page.waitForTimeout(1200);
    const gone = await page.evaluate(() => document.querySelectorAll("#doc-snippet-list .doc-snippet-item").length);
    await page.evaluate(() => performUndo());
    await page.waitForTimeout(1200);
    const back = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-name")].filter((n) => n.textContent === window.__snip).length);
    ok("Delete, then Undo brings it back", back === 1, J({ gone, back }));
    await page.evaluate(() => { promptDialog = window.__prompt; });
    // A prose document hides the tab and goes back to the list.
    await open("Prose probe", "md", "# Hi\n");
    const prose = await page.evaluate(() => ({
      button: getComputedStyle(document.getElementById("doc-code-snippets-open")).display,
      panel: getComputedStyle(document.getElementById("doc-code-side")).display,
      editor: Math.round(document.querySelector(".cm-editor").getBoundingClientRect().width),
    }));
    // INBOX 904 B18: a prose document keeps the tab, as Sections; only the panel stays shut until asked.
    ok("a prose document keeps the Sections tab and shuts the panel", prose.button !== "none" && prose.panel === "none", J(prose));
    await open("Back to code", "py", "x = 1\n");
    const reopened = await page.evaluate(() => getComputedStyle(document.getElementById("doc-code-side")).display);
    //: A phone never has a sheet arrive unasked.
    ok(phone ? "a code file does not raise the sheet unasked" : "a code file brings the open panel back", phone ? reopened === "none" : reopened !== "none", reopened);
    if (!phone) await page.click("#doc-code-side-close");
    else await page.evaluate(() => docKit.sheetClose?.());
    await page.waitForTimeout(400);
  }

  if (want("assist")) {
    await page.evaluate(() => localStorage.setItem("docCodeSide", ""));
    await open("Assist probe", "py", "def add(a, b):\n    return a - b\n\n\nprint(add(1, 2))\n");
    await page.click("#doc-code-assist-open");
    await page.waitForTimeout(900);
    const shape = await page.evaluate(() => {
      const sec = document.getElementById("doc-code-assist");
      const side = document.getElementById("doc-code-side").getBoundingClientRect();
      // The send button sits inside the Ask field at control height minus 8 px by design (library-lazy.css #doc-assist-send), so it is no target of its own.
      const kids = [...sec.querySelectorAll("button, input")].filter((e) => e.getBoundingClientRect().width > 0 && e.id !== "doc-assist-send");
      const outside = kids.filter((e) => { const b = e.getBoundingClientRect(); return b.left < side.left - 1 || b.right > side.right + 1; }).map((e) => e.textContent.trim() || e.id);
      return {
        shown: !sec.classList.contains("hidden") && sec.getBoundingClientRect().height > 0,
        scope: document.getElementById("doc-assist-scope").textContent,
        aiHidden: getComputedStyle(document.getElementById("doc-ai")).display === "none",
        controls: kids.length, outside,
        minTarget: Math.min(...kids.map((e) => Math.round(e.getBoundingClientRect().height))),
        smallest: kids.map((e) => [e.id || e.textContent.trim(), Math.round(e.getBoundingClientRect().height)]).sort((a, b) => a[1] - b[1])[0],
        modelLine: !document.getElementById("doc-assist-model-line").classList.contains("hidden"),
      };
    });
    ok("Assistant tab: scope line, asks, field and tools inside the panel", shape.shown && /whole file, 5 lines\./.test(shape.scope) && shape.outside.length === 0 && shape.aiHidden, J(shape));
    ok(phone ? "touch targets at least 44px" : "controls at least 28px", shape.minTarget >= (phone ? 44 : 28), shape.minTarget);
    // No model here: the line says so, and a question says what needs one.
    await page.fill("#doc-assist-question", "what does add do");
    await page.click("#doc-assist-send");
    await page.waitForTimeout(1500);
    const said = await page.evaluate(() => document.getElementById("doc-assist-answer").textContent);
    ok("with no model a question says plainly what needs one", shape.modelLine && /need a model/.test(said), J({ said, line: shape.modelLine }));
    // Find usages, a tool with no model.
    await page.evaluate(() => { const v = docCmView; v.dispatch({ selection: { anchor: 5 } }); });
    await page.evaluate(() => document.querySelector('[data-assist-tool="find_usages"]').click());
    await page.waitForTimeout(800);
    const refs = await page.evaluate(() => [...document.querySelectorAll(".action-menu")].filter((m) => !m.classList.contains("hidden") && m.getBoundingClientRect().width > 0).map((m) => m.getAttribute("aria-label") || m.textContent.slice(0, 60)).join(" | "));
    ok("Find usages runs with no model", /uses of add|Line 1/.test(refs), refs);
    await page.keyboard.press("Escape");
    // A model's change, faked at the network: the diff, Apply, one Ctrl+Z.
    await page.route("**/code-assist", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ kind: "change", text: "Add now adds.", code: "def add(a, b):\n    return a + b\n", answered_by: "test-model" }) }));
    await page.evaluate(() => { const v = docCmView; v.dispatch({ selection: { anchor: 0, head: v.state.doc.line(2).to } }); });
    if (phone) { await page.evaluate(() => document.getElementById("doc-code-assist-open").click()); await page.waitForTimeout(700); }
    await page.evaluate(() => { modelStatus = { ...(modelStatus || {}), ollama_running: true }; syncModelGatedControls(); });
    await page.evaluate(() => document.querySelector('#doc-code-assist [data-assist="refactor"]').click());
    await page.waitForTimeout(1200);
    const diff = await page.evaluate(() => {
      const a = document.getElementById("doc-assist-answer");
      const d = a.querySelector(".doc-diff");
      const side = document.getElementById("doc-code-side").getBoundingClientRect();
      const b = d ? d.getBoundingClientRect() : null;
      return { lines: d ? d.querySelectorAll(".doc-diff-line").length : 0, added: d ? d.querySelectorAll(".diff-added").length : 0, removed: d ? d.querySelectorAll(".diff-removed").length : 0, inside: b ? b.right <= side.right + 1 : false, buttons: [...a.querySelectorAll("button")].map((x) => x.textContent.trim()) };
    });
    ok("a change shows as a diff with Apply and Reject", diff.lines >= 2 && diff.added >= 1 && diff.removed >= 1 && diff.inside && J(diff.buttons) === J(["Apply", "Reject"]), J(diff));
    const before = await page.evaluate(() => docText());
    await page.evaluate(() => [...document.querySelectorAll("#doc-assist-answer button")].find((b) => b.textContent.trim() === "Apply").click());
    await page.waitForTimeout(300);
    const after = await page.evaluate(() => docText());
    if (phone) ok("Apply on a phone closes the sheet so the change shows", await page.evaluate(() => !document.querySelector('.sheet-overlay[data-sheet="code-side"]') || !docKit.sheetClose));
    ok("Apply writes the change into the editor", after.includes("return a + b") && !after.includes("return a - b") && after.includes("print(add(1, 2))"), J(after));
    await page.evaluate(() => CM6.commands.undo(docCmView));
    await page.waitForTimeout(200);
    ok("one Ctrl+Z takes the applied change out", (await page.evaluate(() => docText())) === before);
    await page.unroute("**/code-assist");
    await page.evaluate(() => { modelStatus = { ...(modelStatus || {}), ollama_running: false }; syncModelGatedControls(); });
    if (!phone) await page.click("#doc-code-side-close");
  }

  if (want("contrast")) {
    await page.evaluate(() => localStorage.setItem("docCodeSide", ""));
    await open("Contrast probe", "py", "x = 1\n");
    await page.click("#doc-code-snippets-open");
    await page.waitForTimeout(900);
    const measure = () => page.evaluate(() => {
      const rgb = (c) => (c.match(/[\d.]+/g) || []).map(Number);
      const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      const ground = (el) => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length >= 3 && (c.length < 4 || c[3] > 0.9)) return c; } return [255, 255, 255]; };
      const ratio = (el) => { const a = lum(rgb(getComputedStyle(el).color)), b = lum(ground(el)); return Math.round(((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)) * 100) / 100; };
      const pick = ["#doc-code-side-tabs [aria-selected=true]", ".doc-snippet-name", ".doc-snippet-facts", ".doc-snippet-group", "#doc-snippet-search", "#doc-assist-scope", "#doc-assist-model-line", '[data-assist-tool="format_code"]'];
      const out = {};
      for (const sel of pick) { const el = document.querySelector(sel); if (el && el.getBoundingClientRect().width > 0) out[sel] = ratio(el); }
      return out;
    });
    const snip = await measure();
    await page.click('#doc-code-side-tabs [data-side="assist"]');
    await page.waitForTimeout(500);
    const asst = await measure();
    const all = { ...snip, ...asst };
    console.log("contrast", J(all));
    ok("panel text at 4.5:1 or more", Object.values(all).every((r) => r >= 4.5), J(all));
    if (!phone) await page.click("#doc-code-side-close");
    else await page.evaluate(() => docKit.sheetClose?.());
    await page.waitForTimeout(400);
  }

  if (want("width")) {
    await open("Width probe", "py", "def main():\n    print('" + "x".repeat(180) + "')\n");
    const code = await page.evaluate(() => {
      const r = (s) => document.querySelector(s).getBoundingClientRect();
      return { pane: Math.round(r(".doc-editor").width), editor: Math.round(r(".cm-editor").width), left: Math.round(r(".cm-editor").left - r(".doc-editor").left) };
    });
    await open("Width prose", "md", "# Prose\n\nA paragraph of prose. ".repeat(4));
    const prose = await page.evaluate(() => {
      const r = (s) => document.querySelector(s).getBoundingClientRect();
      return { pane: Math.round(r(".doc-editor").width), editor: Math.round(r(".cm-editor").width) };
    });
    console.log("width", J({ code, prose }));
    ok("code view uses the pane's width", code.editor >= code.pane - 2, J(code));
    ok("prose keeps its measure", phone ? prose.editor <= prose.pane : prose.editor < prose.pane - 100, J(prose));
  }

  ok("no page errors", errors.length === 0, J(errors.slice(0, 3)));
  console.log(`${good}/${good + bad} at ${WIDTH}`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
