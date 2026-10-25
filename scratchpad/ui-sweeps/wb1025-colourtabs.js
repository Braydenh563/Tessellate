// The 22-10 bug doc: pressing the Fill tab in the colour popup moved the
// popup to the top left. Every Fill/Border pair the board has, opened from
// whichever of its two wells is on screen, then switched to the other tab
// and back: the popup must stay put (within 2px) each time.
//   VW=1440 BASE=http://127.0.0.1:8791 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1025-colourtabs.js
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
const VW = Number(process.env.VW || 1440), VH = Number(process.env.VH || 900);
let pass = 0, fail = 0;
const ok = (l, g, d) => { g ? pass++ : fail++; console.log(`${g ? "OK  " : "FAIL"} ${l}${d ? "  " + d : ""}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const boardId = await page.evaluate(async () => (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Tabs ${Date.now()}` }) })).id);
  await openBoardsTab(page);
  await page.evaluate((id) => openWhiteboardBoard(id), boardId);
  await waitForBoardOpen(page);
  const box = await page.evaluate(() => { const r = document.getElementById("whiteboard-container").getBoundingClientRect(); return { x: r.left, y: r.top }; });
  const run = async (label) => {
    const wells = await page.evaluate(() => WB_COLOUR_PAIRS.flatMap((p) => [p.fill, p.border]).filter((id) => { const el = document.getElementById(id); const r = el?.getBoundingClientRect(); return r && r.width > 0 && el.getClientRects().length; }));
    for (const id of wells) {
      // Closed the way an outside press closes it; Escape on the board would
      // also drop the selection, and with it the bar's wells.
      await page.evaluate(() => closeActionMenus());
      await page.evaluate((id) => document.getElementById(id).click(), id);
      await page.waitForTimeout(300);
      const pos = () => page.evaluate(() => {
        const m = [...document.querySelectorAll(".wb-colour-menu")].find((x) => !x.classList.contains("hidden"));
        if (!m) return null;
        const r = m.getBoundingClientRect();
        const tabs = [...m.querySelectorAll('.wb-colour-pair [role="tab"]')].map((t) => t.textContent.trim());
        return { x: Math.round(r.left), y: Math.round(r.top), tabs, title: m.querySelector(".wb-colour-title, h3, header")?.textContent?.trim()?.slice(0, 40) };
      });
      const p0 = await pos();
      if (!p0 || !p0.tabs.length) continue;
      const moves = [];
      for (const tab of [...p0.tabs.slice().reverse(), ...p0.tabs]) {
        await page.evaluate((t) => [...document.querySelectorAll('.wb-colour-menu:not(.hidden) .wb-colour-pair [role="tab"]')].find((b) => b.textContent.trim() === t)?.click(), tab);
        await page.waitForTimeout(200);
        const p = await pos();
        moves.push(p ? Math.max(Math.abs(p.x - p0.x), Math.abs(p.y - p0.y)) : -1);
      }
      await page.evaluate(() => closeActionMenus());
      ok(`${label}: from #${id}, switching tabs keeps the popup in place`, moves.every((m) => m >= 0 && m <= 2), `${JSON.stringify(p0)} moves ${moves.join(",")}`);
    }
  };
  // Nothing selected (the rail's pair).
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await run("nothing selected");
  // A drawn rectangle, selected.
  await page.evaluate(() => { document.getElementById("wb-colour-menu")?.classList.add("hidden"); document.getElementById("whiteboard-container").focus(); });
  await page.keyboard.press("r");
  await page.mouse.move(box.x + 500, box.y + 300);
  await page.mouse.down();
  await page.mouse.move(box.x + 680, box.y + 420, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(700);
  await page.keyboard.press("v");
  await page.mouse.click(box.x + 500, box.y + 360);
  await page.waitForTimeout(500);
  await run("a shape");
  // The rectangle tool held, nothing selected.
  await page.evaluate(() => { document.getElementById("wb-colour-menu")?.classList.add("hidden"); document.getElementById("whiteboard-container").focus(); });
  await page.keyboard.press("Escape");
  await page.keyboard.press("r");
  await page.waitForTimeout(300);
  await run("a shape tool held");
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
