// Ctrl+Enter on a topic inserts a parent topic in its place; one Undo returns it.
//   BASE=... node scratchpad/ui-sweeps/wb1025-mapparent.js
const { boot, openBoardsTab } = require("./lib.js");
(async () => {
  let fails = 0;
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const d = document.getElementById("recovery-key-dialog"); if (d && d.open) d.close(); });
  await openBoardsTab(page);
  await page.evaluate(async () => {
    const md = ["# Parent", "- Root", "  - A", "    - A1", "    - A2", "  - B", "  - C"].join("\n");
    const board = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content: md, name: "Parent " + Date.now() }) });
    await openWhiteboardBoard(board.id);
    await new Promise((r) => setTimeout(r, 1500));
  });
  const snap = () => page.evaluate(() => {
    const ix = wbMapIndex();
    const name = (n) => n ? (n.data?.content || "").trim() : null;
    const kids = (id) => (ix.childrenOf.get(id) || []).map((n) => name(n));
    const root = ix.nodes.find((n) => name(n) === "Root");
    const b = ix.nodes.find((n) => name(n) === "B");
    return { count: ix.nodes.length, rootKids: kids(root.id), bParent: name(ix.byId.get(b.parent_id)), editing: !!document.querySelector(".wb-object.editing, .wb-map-node [contenteditable=true]") };
  });
  const before = await snap();
  console.log("before", JSON.stringify(before));
  await page.evaluate(() => { const b = wbMapIndex().nodes.find((n) => (n.data?.content || "").trim() === "B"); selectWbItem("object", b.id); });
  await page.waitForTimeout(300);
  await page.keyboard.press("Control+Enter");
  await page.waitForTimeout(1500);
  const typing = await page.evaluate(() => !!document.activeElement?.isContentEditable || document.activeElement?.tagName === "TEXTAREA");
  console.log("editing the new topic", typing);
  if (!typing) { fails++; console.log("FAIL edit"); }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  const after = await snap();
  console.log("after", JSON.stringify(after));
  if (after.count !== before.count + 1) { fails++; console.log("FAIL count"); }
  if (after.rootKids.length !== 3 || after.rootKids[1] === "B" || after.bParent === "Root") { fails++; console.log("FAIL place"); }
  await page.evaluate(() => document.activeElement?.blur?.());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(1500);
  const undone = await snap();
  console.log("undo", JSON.stringify(undone));
  if (undone.count !== before.count || undone.bParent !== "Root" || JSON.stringify(undone.rootKids) !== JSON.stringify(before.rootKids)) { fails++; console.log("FAIL undo"); }
  // the centre refuses
  const centre = await page.evaluate(async () => { const r = wbMapIndex().nodes.find((n) => (n.data?.content || "").trim() === "Root"); const n = wbMapIndex().nodes.length; await wbMapInsertParent(r.id); return wbMapIndex().nodes.length - n; });
  console.log("centre adds", centre);
  if (centre !== 0) { fails++; console.log("FAIL centre"); }
  await browser.close();
  console.log(fails ? `FAIL: ${fails}` : "PASS");
  process.exit(fails ? 1 : 0);
})();
