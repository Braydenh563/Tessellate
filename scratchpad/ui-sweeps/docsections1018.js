// INBOX 904 B18: a library of text sections for ordinary documents. The
// Snippets panel is open to a markdown document too, as Sections: curated
// blocks that go in at the caret (or where a row is dropped) on their own
// lines, with today's date and stops Tab walks; your own are saved from the
// selection. Real mouse and keyboard in Chromium, numbers from the editor.
//
// Usage: BASE=http://127.0.0.1:8792 [WIDTH=390] [THEME=dark] node docsections1018.js
const { boot } = require("./lib.js");

const WIDTH = Number(process.env.WIDTH || 1440);
let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

const DOC = "# Plan\n\nThe first paragraph.\n\nThe second paragraph.\n";

(async () => {
  const phone = WIDTH < 600;
  const { browser, page } = await boot(phone
    ? { viewport: { width: WIDTH, height: 844 }, hasTouch: true, isMobile: true }
    : { viewport: { width: WIDTH, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => {
    if (!/about:srcdoc|blob:null/.test(String(e.stack))) errors.push(e.message);
  });
  await page.evaluate(() => { localStorage.setItem("docSectionsSide", ""); localStorage.setItem("docCodeSide", ""); });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2500);
  await page.evaluate(async (c) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Sections probe", content: c }) });
    await loadDocuments(d.id);
  }, DOC);
  await page.waitForTimeout(2000);
  await page.evaluate(() => setDocView("live"));
  await page.waitForTimeout(1500);

  const text = () => page.evaluate(() => docCmView.state.doc.toString());
  const shownText = (sel) => page.evaluate((s) => { const e = document.querySelector(s); return e && getComputedStyle(e).display !== "none" && e.getBoundingClientRect().width > 0 ? e.innerText.trim() : null; }, sel);
  const rows = () => page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-row")].map((r) => ({ key: r.dataset.key, name: r.querySelector(".doc-snippet-name").textContent })));
  const visible = (sel) => page.evaluate((s) => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== "none" && e.getBoundingClientRect().width > 0; }, sel);
  const undo = async () => {
    await page.evaluate(() => docCmView.focus());
    await page.keyboard.press("Control+z");
    await page.waitForTimeout(350);
  };
  const caretAt = (needle, end = true) => page.evaluate(([n, e]) => {
    const s = docCmView.state.doc.toString();
    const i = s.indexOf(n);
    docCmView.dispatch({ selection: { anchor: e ? i + n.length : i } });
    docCmView.focus();
  }, [needle, end]);

  // 1. The way in: Sections beside prose, no Assistant.
  //: A phone's dock is icons only (the word is hidden), so its name is the aria-label.
  const wayIn = phone ? await page.evaluate(() => $("doc-code-snippets-open").getAttribute("aria-label")) : await shownText("#doc-code-snippets-open");
  ok("the dock's way in reads Sections for a text document", wayIn === "Sections", wayIn);
  ok("the Assistant's way in is not offered", !(await visible("#doc-code-assist-open")));
  await page.locator("#doc-code-snippets-open").click();
  await page.waitForTimeout(900);
  ok("the panel opens", await visible("#doc-code-side"));
  if (process.env.DEBUG) console.log("  tabs", JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("#doc-code-side-tabs [data-side]")].map((t) => [t.dataset.side, t.innerText, getComputedStyle(t).display]))));
  ok("with one tab, Sections", (await visible('#doc-code-side-tabs [data-side="snippets"]')) && !(await visible('#doc-code-side-tabs [data-side="assist"]')) && (await shownText('#doc-code-side-tabs [data-side="snippets"]')) === "Sections");
  const all = await rows();
  ok("it lists the curated sections (24)", all.length === 24 && all.every((r) => r.key.startsWith("builtin:md:")), `${all.length} rows, first ${all[0] && all[0].name}`);
  const head = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-group")].map((h) => h.textContent));
  ok("under one head, Text sections, with no Show every language", head.length === 1 && head[0] === "Text sections" && !(await visible(".doc-snippet-more")), JSON.stringify(head));
  ok("the search and save wording follows the type", (await page.evaluate(() => $("doc-snippet-search").placeholder)) === "Search sections…" && /section/.test(await page.evaluate(() => $("doc-snippet-save").title)));

  // 2. Search.
  await page.fill("#doc-snippet-search", "risk");
  await page.waitForTimeout(250);
  const risk = await rows();
  ok("searching risk finds the Risk table, and only sections", risk.length >= 1 && risk.some((r) => r.name === "Risk table") && risk.every((r) => r.key.startsWith("builtin:md:")), JSON.stringify(risk.map((r) => r.name)));
  await page.fill("#doc-snippet-search", "#callouts");
  await page.waitForTimeout(250);
  const callouts = await rows();
  ok("#callouts finds the four callouts", callouts.length === 4, JSON.stringify(callouts.map((r) => r.name)));
  await page.fill("#doc-snippet-search", "table");
  await page.waitForTimeout(250);
  const tables = await rows();
  ok("searching table brings no code snippet in from another language", tables.length >= 2 && tables.every((r) => r.key.startsWith("builtin:md:")), `${tables.length} rows`);
  await page.fill("#doc-snippet-search", "");
  await page.waitForTimeout(250);

  // 3. Click: a block at the end of a paragraph, with its date and stops.
  await caretAt("The first paragraph.");
  const before = await text();
  await page.locator('.doc-snippet-row[data-key="builtin:md:meeting"]').click();
  await page.waitForTimeout(450);
  const after = await text();
  const inserted = after.slice(before.indexOf("The first paragraph.") + "The first paragraph.".length);
  ok("a click inserts the meeting block under the paragraph, a blank line between", /^\n\n## Meeting title\n\n\*\*Date:\*\* /.test(inserted) || /^\n\n## Meeting title/.test(inserted), JSON.stringify(inserted.slice(0, 60)));
  ok("with today's date in the person's words, not the placeholder", !after.includes("{{date}}") && /\*\*Date:\*\* .*\d{4}/.test(after), (after.match(/\*\*Date:\*\* .*/) || [""])[0]);
  ok("a blank line follows it, before the next paragraph", /- \[ \] Who, what, by when\n\nThe second paragraph\./.test(after), JSON.stringify(after.slice(after.indexOf("Who, what") - 12, after.indexOf("Who, what") + 60)));
  const sel1 = await page.evaluate(() => { const r = docCmView.state.selection.main; return docCmView.state.sliceDoc(r.from, r.to); });
  ok("the first prompt is selected", sel1 === "Meeting title", sel1);
  await page.keyboard.press("Tab");
  await page.waitForTimeout(150);
  const sel2 = await page.evaluate(() => { const r = docCmView.state.selection.main; return docCmView.state.sliceDoc(r.from, r.to); });
  ok("Tab walks to the next, Names", sel2 === "Names", sel2);
  await undo();
  ok("one Ctrl+Z takes the whole block out", (await text()) === before);
  if (phone) ok("on a phone the sheet closed with the insert", !(await visible("#doc-code-side")));

  // 4. The caret on an empty line between two paragraphs: no extra blank lines.
  if (!phone) {
    await page.evaluate(() => { const s = docCmView.state.doc.toString(); const i = s.indexOf("The second paragraph."); docCmView.dispatch({ selection: { anchor: i - 1 } }); docCmView.focus(); });
    await page.locator('.doc-snippet-row[data-key="builtin:md:risks"]').click();
    await page.waitForTimeout(400);
    const t = await text();
    ok("on the blank line between paragraphs: one blank line each side, no more", /The first paragraph\.\n\n\| Risk \|[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n\nThe second paragraph\./.test(t), JSON.stringify(t.slice(t.indexOf("first") - 2, t.indexOf("first") + 40)));
    await undo();
    ok("and one Ctrl+Z puts it back", (await text()) === before);

    // 5. Drag a row into the middle of a sentence: the block gets its own lines.
    await page.locator('.doc-snippet-row[data-key="builtin:md:tip"]').scrollIntoViewIfNeeded();
    const row = await page.locator('.doc-snippet-row[data-key="builtin:md:tip"]').boundingBox();
    const target = await page.evaluate(() => {
      const view = docCmView;
      const s = view.state.doc.toString();
      const pos = s.indexOf("second") + 3;
      const c = view.coordsAtPos(pos);
      return { x: c.left, y: (c.top + c.bottom) / 2, pos };
    });
    await page.mouse.move(row.x + row.width / 2, row.y + row.height / 2);
    await page.mouse.down();
    await page.mouse.move(row.x - 30, row.y + 10, { steps: 4 });
    await page.mouse.move(target.x, target.y, { steps: 14 });
    await page.mouse.move(target.x + 1, target.y);
    await page.waitForTimeout(200);
    await page.mouse.up();
    await page.waitForTimeout(500);
    const dropped = await text();
    if (process.env.DEBUG) console.log("  dropped", JSON.stringify(dropped), JSON.stringify(target));
    ok("dropping a row inside a sentence splits it, the block on its own lines", /The sec\n\n> \[!tip\] A better way\n> How to do it\.\n\nond paragraph\./.test(dropped), JSON.stringify(dropped.slice(dropped.indexOf("The sec") - 2, dropped.indexOf("The sec") + 70)));
    await undo();
    ok("one Ctrl+Z undoes the drop", (await text()) === before);
  }

  if (phone) {
    await page.locator("#doc-code-snippets-open").click();
    await page.waitForTimeout(900);
  }
  // 6. Save the selection as a section of your own; it lists, inserts and deletes.
  await page.evaluate(() => { const s = docCmView.state.doc.toString(); const i = s.indexOf("The first paragraph."); docCmView.dispatch({ selection: { anchor: i, head: i + "The first paragraph.".length } }); });
  await page.evaluate(() => { window.__prompt = promptDialog; promptDialog = async () => "My opener #writing #probe"; });
  await page.locator("#doc-snippet-save").click();
  await page.waitForTimeout(900);
  await page.evaluate(() => { promptDialog = window.__prompt; });
  const mine = await page.evaluate(() => [...document.querySelectorAll("#doc-snippet-list .doc-snippet-row")].filter((r) => !r.dataset.key.startsWith("builtin:")).map((r) => r.querySelector(".doc-snippet-name").textContent));
  ok("Save keeps the selected text as a section of your own", mine.includes("My opener"), JSON.stringify(mine));
  await page.fill("#doc-snippet-search", "#probe");
  await page.waitForTimeout(250);
  ok("its #tags search", (await rows()).length === 1);
  await caretAt("The second paragraph.");
  await page.locator("#doc-snippet-list .doc-snippet-row").first().click();
  await page.waitForTimeout(400);
  const own = await text();
  ok("your own goes in as written, as a block", /The second paragraph\.\n\nThe first paragraph\.\n$/.test(own) || /The second paragraph\.\n\nThe first paragraph\./.test(own), JSON.stringify(own.slice(-60)));
  await undo();
  // Clean up: delete it through the row's own menu.
  const id = await page.evaluate(() => { const r = docKit.items.find((i) => i.name === "My opener"); return r && r.id; });
  if (id) await page.evaluate((i) => apiJson(`/board-library/${i}`, { method: "DELETE" }), id);
  await page.evaluate(() => docKitFetch(true));

  // 7. The panel does not take the editor's width away.
  if (!phone) {
    const widths = await page.evaluate(() => ({ editor: Math.round(docCmView.scrollDOM.getBoundingClientRect().width), panel: Math.round($("doc-code-side").getBoundingClientRect().width) }));
    ok("the editor keeps at least 500px beside the panel", widths.editor >= 500, JSON.stringify(widths));
  }

  // 8. The remembered state is the prose document's own.
  const prefs = await page.evaluate(() => ({ sections: localStorage.getItem("docSectionsSide"), code: localStorage.getItem("docCodeSide") }));
  ok("the panel is remembered under its own key, not the code panel's", prefs.code === "" || prefs.code === null, JSON.stringify(prefs));

  // 9. A code file keeps its Snippets and Assistant, and none of the sections.
  await page.evaluate(async () => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Code probe", content: "x = 1\n", file_type: "py" }) });
    await loadDocuments(d.id);
  });
  await page.waitForTimeout(2200);
  if (phone) {
    // The sheet is a phone's: open it and read the same facts.
    await page.evaluate(() => docCodeSideFrom("snippets"));
    await page.waitForTimeout(900);
  } else {
    ok("a code file closes the prose panel (its own remembered state is empty)", !(await visible("#doc-code-side")), "");
    await page.locator("#doc-code-snippets-open").click();
    await page.waitForTimeout(900);
  }
  const codeWayIn = phone ? await page.evaluate(() => $("doc-code-snippets-open").getAttribute("aria-label")) : await shownText("#doc-code-snippets-open");
  ok("a code file's way in reads Snippets and the Assistant is offered", codeWayIn === "Snippets" && (await visible("#doc-code-assist-open")), codeWayIn);
  ok("with both tabs", (await visible('#doc-code-side-tabs [data-side="assist"]')) && (await shownText('#doc-code-side-tabs [data-side="snippets"]')) === "Snippets");
  await page.fill("#doc-snippet-search", "");
  await page.waitForTimeout(250);
  const codeRows = await rows();
  if (process.env.DEBUG) console.log("  render", await page.evaluate(() => { try { docSnippetsRender(); return "ok " + $("doc-snippet-list").children.length; } catch (e) { return String(e.stack).slice(0, 300); } }));
  if (process.env.DEBUG) console.log("  code state", JSON.stringify(await page.evaluate(() => ({ ext: docFileType().ext, tab: docKit.tab, open: !$("doc-code-side").classList.contains("hidden"), items: $("doc-snippet-list").children.length }))));
  ok("and no text section among the Python rows", codeRows.length > 0 && codeRows.every((r) => !r.key.startsWith("builtin:md:")), `${codeRows.length} rows`);
  ok("the code panel keeps its wording", (await page.evaluate(() => $("doc-snippet-search").placeholder)) === "Search snippets…");

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
