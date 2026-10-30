// INBOX 1452: a left drag on empty board or map canvas draws the selection
// box; a right drag pans; a plain right click still opens the menu.
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/wbleftdrag1452.js
const { openFresh } = require("./cdlib.js");
(async () => {
  for (const type of ["board", "map"]) {
    const { browser, page, errors, board } = await openFresh({ type, title: "ld1452" });
    await page.evaluate(async (id) => {
      const mk = (x, y, t) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: id, kind: "text", x, y, width: 160, height: 80, data: { content: t } }) });
      await mk(100, 100, "one"); await mk(320, 100, "two");
      await fetchWhiteboardState(id); renderWhiteboard();
    }, board.id);
    await page.waitForTimeout(500);
    const t = () => page.evaluate(() => { const z = d3.zoomTransform(document.getElementById("whiteboard-container") || document.querySelector(".wb-canvas, svg")); return [Math.round(z.x), Math.round(z.y)]; });
    const rects = await page.evaluate(() => [...document.querySelectorAll(".wb-object")].map((n) => { const r = n.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom].map(Math.round); }));
    const [l, tp, r, b] = rects[0];
    const menuCount = () => page.evaluate(() => [...document.querySelectorAll("button, [role=menuitem], li, div")].filter((m) => m.offsetParent && m.childElementCount < 4 && /Paste special|Add a topic|Add a text box here/.test(m.textContent)).length);
    console.log(`${type}: menu baseline ${await menuCount()}`);
    const t0 = await t();
    await page.mouse.move(l - 30, tp - 30); await page.mouse.down();
    await page.mouse.move(l + 40, tp + 30, { steps: 4 }); await page.mouse.move(r + 20, b + 20, { steps: 6 });
    const mid = await page.evaluate(([x, y]) => { const el = document.elementFromPoint(x, y); return [el?.id, el?.className?.baseVal ?? el?.className, document.querySelectorAll("[class*=marquee]").length]; }, [l - 30, tp - 30]);
    console.log(`${type}: under press`, mid);
    await page.mouse.up();
    await page.waitForTimeout(200);
    const t1 = await t();
    const sel = await page.evaluate(() => (typeof wbMultiSelection !== "undefined" ? [wbMultiSelection.size, wbSelectedItem?.kind || null] : -1));
    console.log(`${type}: left drag view ${t0} -> ${t1}, selected ${sel}`);
    await page.mouse.move(r + 200, b + 200); await page.mouse.down({ button: "right" });
    await page.mouse.move(r + 120, b + 140, { steps: 8 }); await page.mouse.up({ button: "right" });
    await page.waitForTimeout(250);
    const t2 = await t();
    const menu = await page.evaluate(() => [...document.querySelectorAll("button, [role=menuitem], li, div")].filter((m) => m.offsetParent && m.childElementCount < 4 && /Paste special|Add a topic|Add a text box here/.test(m.textContent)).length);
    console.log(`${type}: right drag view ${t1} -> ${t2}, menus open ${menu}`);
    await page.keyboard.press("Escape");
    await page.mouse.click(r + 250, b + 250, { button: "right" }); await page.waitForTimeout(250);
    const menu2 = await page.evaluate(() => [...document.querySelectorAll("button, [role=menuitem], li, div")].filter((m) => m.offsetParent && m.childElementCount < 4 && /Paste special|Add a topic|Add a text box here/.test(m.textContent)).length);
    console.log(`${type}: plain right click menus open ${menu2}; errors ${errors.length} ${errors.slice(0, 2)}`);
    await browser.close();
  }
})();
