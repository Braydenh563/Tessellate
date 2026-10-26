// K9/K10: shift-drag box select, selection bar Pin/Unpin, Unpin all in the ... menu, Reset unpins with Undo.
// BASE=http://127.0.0.1:PORT W=1440 H=900
const { boot } = require("./lib.js");
(async () => {
  const W = +(process.env.W || 1440), H = +(process.env.H || 900);
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  await page.evaluate(() => { try { prefs.set("graph-layout", "force"); } catch (e) {} });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(6000);
  const out = {};
  const pinned = () => page.evaluate(() => gcTab.nodes.filter((n) => n.fx != null && !n.isGroup).length);
  const rect = await page.evaluate(() => { const r = gcTab.canvas.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
  // box: a straight-ish drag across the middle of the map, from an empty corner
  await page.keyboard.down("Shift");
  await page.mouse.move(rect.x + 6, rect.y + rect.h - 6);
  await page.mouse.down();
  await page.mouse.move(rect.x + rect.w * 0.5, rect.y + rect.h * 0.5, { steps: 6 });
  await page.mouse.move(rect.x + rect.w - 6, rect.y + 6, { steps: 6 });
  await page.mouse.up();
  await page.keyboard.up("Shift");
  await page.waitForTimeout(300);
  out.selected = await page.evaluate(() => gcTab.selected.size);
  out.dockVisible = await page.evaluate(() => !document.getElementById("graph-selection-dock").classList.contains("hidden"));
  out.pinDisabled = await page.evaluate(() => document.getElementById("graph-selection-pin").disabled);
  await page.click("#graph-selection-pin");
  await page.waitForTimeout(600);
  out.pinnedAfterPin = await pinned();
  await page.click("#graph-selection-unpin");
  await page.waitForTimeout(600);
  out.pinnedAfterUnpin = await pinned();
  await page.click("#graph-selection-pin");
  await page.waitForTimeout(600);
  // Unpin all from the ... menu, then Undo
  await page.click("#graph-more-menu > summary");
  await page.click("#graph-unpin-all-menu");
  await page.waitForTimeout(1500);
  out.afterUnpinAll = await pinned();
  await page.click(".toast-action", { timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(2000);
  out.afterUnpinAllUndo = await pinned();
  // Reset to defaults unpins too, Undo restores
  await page.evaluate(() => document.getElementById("graph-options-reset").click());
  await page.waitForTimeout(2000);
  out.afterReset = await pinned();
  await page.click(".toast-action", { timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(2500);
  out.afterResetUndo = await pinned();
  console.log(JSON.stringify(out));
  await browser.close();
})();
