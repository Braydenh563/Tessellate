// Sort branches (INBOX 1308): a topic's children reorder by their words, one Undo step.
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/map1019-sort.js
const { openFresh, checker, openMap, overlapIn } = require("./cd2lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page } = await openFresh();
  await openMap(page, "# Root\n- Root\n  - Step 10\n  - banana\n  - Step 2\n  - Apple");
  const names = () => page.evaluate(() => { const i = wbMapIndex(); return i.childrenOf.get(i.roots[0].id).map((o) => wbMapLabel(o)); });
  const before = await names();
  await page.evaluate(() => { const i = wbMapIndex(); selectWbItem("object", i.roots[0].id); });
  await page.evaluate(() => wbMapSortChildren(wbSelectedMapNode().id, 1));
  await page.waitForTimeout(800);
  const az = await names();
  check("A to Z with numbers read as numbers", JSON.stringify(az) === JSON.stringify(["Apple", "banana", "Step 2", "Step 10"]), { before, az });
  check("no topics overlap after the tidy", (await overlapIn(page)) === 0);
  await page.evaluate(() => wbMapSortChildren(wbSelectedMapNode().id, -1));
  await page.waitForTimeout(800);
  const za = await names();
  check("Z to A reverses it", za.join() === ["Step 10", "Step 2", "banana", "Apple"].join(), za);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(800);
  const undone = await names();
  check("one Undo returns the A to Z order", undone.join() === az.join(), undone);
  await browser.close();
  summary();
})();
