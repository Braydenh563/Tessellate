// INBOX 553(b): a map's and a document's undo history survive a reload.
//   BASE=http://127.0.0.1:8844 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/mmdoc1005-undoreload.js
const { boot } = require("./lib.js");

(async () => {
  const { page, browser } = await boot();
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  const results = [];
  const check = (name, ok, detail) => {
    results.push(ok);
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`);
  };
  const openLibraryBoards = async () => {
    await page.evaluate(() => switchTab("library"));
    await page.waitForTimeout(600);
    await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click());
    await page.waitForTimeout(1200);
  };
  await openLibraryBoards();
  // A map with two topics typed by keyboard.
  const boardId = await page.evaluate(async () => {
    const b = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content: "# Undo reload\n\n- Centre\n  - A" }) });
    await openWhiteboardBoard(b.id);
    await wbMapTidyFresh();
    selectWbItem("object", wbState.objects.find((o) => o.data.content === "A").id);
    document.getElementById("whiteboard-container").focus();
    return b.id;
  });
  await page.keyboard.press("Tab");
  await page.keyboard.type("Kept one");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(600);
  await page.keyboard.press("Enter");
  await page.keyboard.type("Kept two");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(1600);
  const before = await page.evaluate(() => ({ topics: wbState.objects.length, undo: wbStacks.undo.length }));

  // A document with two edits.
  const docId = await page.evaluate(async () => {
    const r = await fetch("/documents", {
      method: "POST",
      headers: { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Undo reload doc", content: "Start." }),
    });
    const doc = await r.json();
    switchTab("documents");
    await new Promise((res) => setTimeout(res, 400));
    await openDocument(doc.id);
    await new Promise((res) => setTimeout(res, 1500));
    setDocView("live");
    await new Promise((res) => setTimeout(res, 400));
    return doc.id;
  });
  await page.click(".cm-content");
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" Added words.");
  await page.waitForTimeout(2500); // the document's own save, and the history's
  const docBefore = await page.evaluate(() => docText());

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);
  if (await page.$("#lock-password") && await page.isVisible("#lock-password")) {
    await page.fill("#lock-password", "testpassword123");
    await page.click("#lock-submit");
    await page.waitForTimeout(3000);
  }
  await openLibraryBoards();
  const after = await page.evaluate(async (id) => {
    await openWhiteboardBoard(id);
    await new Promise((r) => setTimeout(r, 1200));
    return { topics: wbState.objects.length, undo: wbStacks.undo.length };
  }, boardId);
  check("the map's steps are back after a reload", after.undo === before.undo && after.undo >= 2, `${before.undo} -> ${after.undo}`);
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(1500);
  const undone = await page.evaluate(() => ({ topics: wbState.objects.length, named: wbState.objects.some((o) => o.data?.content === "Kept two") }));
  check("and Ctrl+Z takes the last typed topic away", undone.topics === after.topics - 1 && !undone.named, JSON.stringify(undone));

  const docAfter = await page.evaluate(async (id) => {
    switchTab("documents");
    await new Promise((res) => setTimeout(res, 400));
    await openDocument(id);
    await new Promise((res) => setTimeout(res, 2000));
    setDocView("live");
    return docText();
  }, docId);
  check("the document reopens with its text", docAfter === docBefore, JSON.stringify(docAfter));
  await page.click(".cm-content");
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(500);
  const docUndone = await page.evaluate(() => docText());
  check("and Ctrl+Z after the reload undoes the last edit", docUndone !== docAfter && docUndone.startsWith("Start."), JSON.stringify(docUndone));
  console.log("errors", errs.length, errs.slice(0, 3));
  console.log(`${results.filter(Boolean).length}/${results.length} passed`);
  await browser.close();
})();
