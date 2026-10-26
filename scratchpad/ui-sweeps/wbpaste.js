// wbpaste-1026: the board's paste options chip, Paste special, pasted pictures
// and the map's chip, driven with ClipboardEvents at two viewports.
//   BASE=http://127.0.0.1:8799 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbpaste.js
const { openBoard, checker } = require("./wb1005-lib.js");

async function run(viewport) {
  const { check, summary } = checker();
  console.log(`--- ${viewport.width}x${viewport.height}`);
  const { browser, ctx, page, errors } = await openBoard({ viewport });
  await ctx.grantPermissions(["clipboard-read", "clipboard-write"]);
  const objs = () => page.evaluate(() => (wbState.objects || []).length);
  const sketches = () => page.evaluate(() => (wbState.sketches || []).length);
  const paste = (data) => page.evaluate((d) => {
    const dt = new DataTransfer();
    for (const [type, value] of Object.entries(d)) dt.setData(type, value);
    document.getElementById("whiteboard-container").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  }, data);
  const chip = () => page.evaluate(() => {
    const el = document.querySelector(".wb-paste-chip");
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { l: r.left, t: r.top, r: r.right, b: r.bottom, vw: innerWidth, vh: innerHeight };
  });
  const fits = (c) => c && c.l >= 0 && c.t >= 0 && c.r <= c.vw && c.b <= c.vh;
  const undo = async () => { await page.evaluate(() => wbUndo()); await page.waitForTimeout(700); };
  const pickFromMenu = async (label) => {
    await page.keyboard.down("Control");
    await page.keyboard.up("Control");
    await page.waitForTimeout(250);
    await page.click(`.action-menu:not(.hidden) >> text=${label}`);
    await page.waitForTimeout(1200);
  };

  // 1. a spreadsheet copy is a table object, with a chip
  let n0 = await objs();
  await paste({ "text/plain": "name\tqty\nmilk\t2\neggs\t12" });
  await page.waitForTimeout(1200);
  const kinds = await page.evaluate(() => (wbState.objects || []).map((o) => o.kind));
  check("a tab-separated copy makes one table object", (await objs()) === n0 + 1 && kinds.includes("table"), kinds);
  let c = await chip();
  check("the chip shows and fits the viewport", fits(c), c);
  // choose stickies from the chip menu: one undo step per choice
  await pickFromMenu("Stickies");
  check("choosing Stickies swaps the table for one sticky per row", (await objs()) === n0 + 3, await objs());
  await undo();
  check("one Undo takes the whole paste back", (await objs()) === n0, await objs());

  // 2. a list: stickies, then a mind map branch by key letter
  await paste({ "text/plain": "- Plan\n  - Research\n    - Read\n  - Build" });
  await page.waitForTimeout(1200);
  check("a list makes four stickies", (await objs()) === n0 + 4, await objs());
  await page.keyboard.down("Control");
  await page.keyboard.up("Control");
  await page.waitForTimeout(250);
  await page.keyboard.press("m");
  await page.waitForTimeout(1500);
  check("M picks Mind map branch: four boxes and three links", (await objs()) === n0 + 4 && (await sketches()) >= 3, [await objs(), await sketches()]);
  c = await chip();
  check("the chip stays after a choice and fits", fits(c), c);
  await undo();
  check("one Undo removes the branch and its links", (await objs()) === n0 && (await sketches()) === 0, [await objs(), await sketches()]);

  // 3. bullets in a shape
  await paste({ "text/plain": "- one\n- two\n- three" });
  await page.waitForTimeout(1000);
  await pickFromMenu("Bullet list in a shape");
  const label = await page.evaluate(() => { const s = (wbState.sketches || [])[0]; return s ? JSON.parse(s.data).label : null; });
  check("Bullet list in a shape makes one labelled shape", label === "• one\n• two\n• three" && (await objs()) === n0, label);
  // Escape dismisses
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  check("Escape dismisses the chip", (await chip()) === null);
  await undo();

  // 4. Paste special from the command, reading the real clipboard
  await page.evaluate(() => navigator.clipboard.writeText("a\tb\nc\td"));
  const cmdMenu = await page.evaluate(() => { WB_COMMANDS.find((x) => x.id === "paste-special").run(); return true; });
  await page.waitForTimeout(400);
  const items = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) [role=menuitem], .action-menu:not(.hidden) button")].map((b) => b.textContent.trim()));
  check("Paste special lists the readings", items.some((t) => /table/i.test(t)) && items.some((t) => /bullet/i.test(t)), items);
  await page.click(".action-menu:not(.hidden) >> text=Paste as table");
  await page.waitForTimeout(1200);
  check("Paste special as table makes a table", (await page.evaluate(() => (wbState.objects || []).filter((o) => o.kind === "table").length)) === 1);
  await undo();

  // 5. paste into the selected shape's text
  await page.evaluate(async () => {
    const made = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify({ d: "M 100 100 h 200 v 120 h -200 Z", shape: "rect", color: "#4a90d9", width: 2 }), x: 0, y: 0, z: 1, board_id: window.currentBoardId }) });
    wbState.sketches.push(made);
    wbScheduleRender();
    selectWbItem("sketch", made.id);
  });
  await page.evaluate(() => navigator.clipboard.writeText("hello shape"));
  await page.evaluate(() => WB_COMMANDS.find((x) => x.id === "paste-into-shape").run());
  await page.waitForTimeout(900);
  const shapeLabel = await page.evaluate(() => JSON.parse(wbState.sketches.find((s) => JSON.parse(s.data).shape === "rect").data).label);
  check("Paste into the shape's text sets its label", shapeLabel === "hello shape", shapeLabel);

  // 6. a picture keeps its size, inside the view
  const before = await objs();
  await page.evaluate(async () => {
    const cv = document.createElement("canvas");
    cv.width = 3000; cv.height = 2000;
    cv.getContext("2d").fillRect(0, 0, 3000, 2000);
    const blob = await new Promise((r) => cv.toBlob(r, "image/png"));
    const dt = new DataTransfer();
    dt.items.add(new File([blob], "big.png", { type: "image/png" }));
    document.getElementById("whiteboard-container").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  });
  await page.waitForTimeout(2500);
  const img = await page.evaluate(() => { const o = (wbState.objects || []).find((x) => x.kind === "image"); return o ? { w: o.width, h: o.height } : null; });
  const view = await page.evaluate(() => { const r = wbVisibleCanvasRect(); const a = wbClientToBoard(r.left, r.top), b = wbClientToBoard(r.right, r.bottom); return { w: b[0] - a[0], h: b[1] - a[1] }; });
  check("a large picture is shrunk to sit inside the view", img && img.w <= view.w && img.h <= view.h && Math.abs(img.w / img.h - 1.5) < 0.02, { img, view });
  check("one picture, one object", (await objs()) === before + 1);

  // 7. fast path: copied objects still paste in one request
  await page.evaluate(() => { wbSelectAllItems(); wbCopySelection(); });
  let posts = 0;
  page.on("request", (r) => { if (r.method() === "POST" && /\/whiteboard\//.test(r.url())) posts += 1; });
  await page.evaluate(() => wbPasteClipboard());
  await page.waitForTimeout(1200);
  check("pasting copied objects is one POST", posts === 1, posts);


  // 8. the map: pasted lines become child branches, and the chip offers one topic
  const map = await page.evaluate(async () => apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "wbpaste map " + Date.now(), type: "map" }) }));
  await page.evaluate(async (id) => { await openWhiteboardBoard(id); }, map.id);
  await page.waitForFunction((id) => window.currentBoardId === id && wbIsMap(), map.id, { timeout: 10000 });
  await page.evaluate(() => { clearWbSelection(); });
  await page.waitForTimeout(1500);
  const topics = () => page.evaluate(() => (wbState.objects || []).length);
  const t0 = await topics();
  await paste({ "text/plain": "Root\n  Alpha\n    Deep\n  Beta" });
  await page.waitForTimeout(2000);
  check("a map paste makes four topics", (await topics()) === t0 + 4, [t0, await topics()]);
  c = await chip();
  check("the map's chip shows and fits", fits(c), c);
  await pickFromMenu("One topic");
  check("One topic swaps four topics for one", (await topics()) === t0 + 1, [t0, await topics()]);
  await undo();
  check("one Undo takes the topic back", (await topics()) === t0, [t0, await topics()]);

  // 9. Paste without comments: a commented object and a commented shape
  await page.evaluate(async () => {
    const obj = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", x: 40, y: 400, width: 200, height: 80, z: 3, board_id: window.currentBoardId, data: { content: "has a thread" } }) });
    wbState.objects.push(obj);
    const sk = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify({ d: "M 400 400 h 100 v 60 h -100 Z", shape: "rect", color: "#4a90d9", width: 2 }), x: 0, y: 0, z: 1, board_id: window.currentBoardId }) });
    wbState.sketches.push(sk);
    await wbSetComments("object", obj, [{ id: "c1", text: "note one", at: "2026-10-26" }]);
    await wbSetComments("sketch", sk, [{ id: "c2", text: "note two", at: "2026-10-26" }]);
    window.__cm = { o: obj.id, s: sk.id };
    wbSelectExactly([["object", obj], ["sketch", sk]]);
    wbCopySelection();
  });
  const threads = () => page.evaluate(() => {
    const m = window.__cm;
    const o = wbState.objects.filter((x) => x.id !== m.o && x.data?.content === "has a thread");
    const s = wbState.sketches.filter((x) => x.id !== m.s && /h 100 v 60/.test(x.data));
    return { o: o.map((x) => (x.data.comments || []).length), s: s.map((x) => (JSON.parse(x.data).comments || []).length) };
  });
  await page.evaluate(() => wbPasteClipboard({ noComments: true }));
  await page.waitForTimeout(1200);
  const bare = await threads();
  check("Paste without comments drops the thread from an object and a shape", bare.o.length === 1 && bare.o[0] === 0 && bare.s.length === 1 && bare.s[0] === 0, bare);
  await page.evaluate(() => wbPasteClipboard());
  await page.waitForTimeout(1200);
  const kept = await threads();
  check("a plain paste keeps the threads", kept.o.length === 2 && kept.o[1] === 1 && kept.s.length === 2 && kept.s[1] === 1, kept);
  check("the originals keep theirs", await page.evaluate(() => wbItemComments("object", wbFindItem("object", window.__cm.o)).length === 1 && wbItemComments("sketch", wbFindItem("sketch", window.__cm.s)).length === 1));

  // 10. the zoom dock stays at half-screen widths and clears the tools row (it was display:none under 820px)
  const dock = await page.evaluate(() => {
    const lvl = document.getElementById("wb-zoom-level");
    const p = lvl.closest(".whiteboard-floating-panel").getBoundingClientRect();
    const t = document.querySelector(".whiteboard-floating-panel.bottom-center").getBoundingClientRect();
    return { shown: p.width > 0 && /%$/.test(lvl.textContent), clear: p.bottom <= t.top + 0.5 || p.left >= t.right, inView: p.right <= innerWidth && p.left >= 0 };
  });
  check("the zoom level is shown and clears the tools row", dock.shown && dock.clear && dock.inView, dock);
  check("no console errors", errors.length === 0, errors);
  const ok = summary();
  await browser.close();
  return ok;
}

(async () => {
  let all = true;
  for (const vp of [{ width: 1440, height: 900 }, { width: 720, height: 900 }]) all = (await run(vp)) && all;
  process.exit(all ? 0 : 1);
})();
