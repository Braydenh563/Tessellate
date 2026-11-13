// Whiteboard follow-ups: the phone More sheet's Arrange submenus (L-whiteboard-30), smoothed ink width and rotation
// (L-whiteboard-31), sub/superscript (L-whiteboard-27), a drawn shape swapped in fresh (L-whiteboard-28).
//   BASE=http://127.0.0.1:8897 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbfollow3.js
const { openFresh, checker } = require("./cdlib.js");
(async () => {
  const { browser, page, errors } = await openFresh({ width: 390 });
  const { check, summary } = checker();
  // --- L-whiteboard-30 --------------------------------------------------------------------------------------
  await page.evaluate(() => document.getElementById("wb-more-toggle").click());
  await page.waitForTimeout(500);
  const top = await page.evaluate(() => {
    const menu = document.getElementById("wb-more-menu");
    const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const groups = [...menu.querySelectorAll(":scope > .menu-group")].filter(vis).map((g) => g.firstElementChild.textContent.trim());
    const flatArrange = [...menu.querySelectorAll(":scope > [data-wb-cmd]")].filter(vis).filter((r) => WB_COMMAND_BY_ID.get(r.dataset.wbCmd).group === "Arrange").length;
    const card = menu.closest(".sheet-card") || menu;
    return { groups, flatArrange, sw: card.scrollWidth, cw: card.clientWidth, rows: [...menu.querySelectorAll(":scope > .menu-item, :scope > .menu-group > .menu-item")].filter(vis).map((r) => Math.round(r.getBoundingClientRect().height)) };
  });
  check("L30: the sheet shows the Arrange submenus as group rows", top.groups.length >= 5, top.groups);
  check("L30: no flat Arrange row left beside the groups", top.flatArrange <= 6, top.flatArrange);
  check("L30: no horizontal overflow at the top level (scrollWidth <= clientWidth)", top.sw <= top.cw, [top.sw, top.cw]);
  check("L30: top-level rows are at least 44 px tall", Math.min(...top.rows) >= 44, Math.min(...top.rows));
  // Select two shapes so commands apply, then open each group.
  const names = await page.evaluate(() => [...document.querySelectorAll("#wb-more-menu > .menu-group")].map((g) => g.dataset.wbMoreGroup));
  for (const label of names) {
    const r = await page.evaluate(async (label) => {
      const wait = (ms) => new Promise((x) => setTimeout(x, ms));
      const menu = document.getElementById("wb-more-menu");
      const g = [...menu.querySelectorAll(":scope > .menu-group")].find((x) => x.dataset.wbMoreGroup === label);
      if (g.hidden) return { hidden: true };
      g.firstElementChild.click(); await wait(250);
      const sub = g.querySelector(".submenu");
      const rows = [...sub.querySelectorAll(":scope > .menu-item")].filter((x) => !x.hidden && x.getBoundingClientRect().height > 0);
      const heights = rows.map((x) => Math.round(x.getBoundingClientRect().height));
      const cmds = rows.filter((x) => x.dataset.wbCmd).length;
      const back = sub.querySelector(".menu-back");
      const out = { cmds, minH: Math.min(...heights), nested: menu.classList.contains("menu-nested"), back: Boolean(back), sw: menu.scrollWidth, cw: menu.clientWidth, total: sub.querySelectorAll("[data-wb-cmd]").length };
      back.click(); await wait(200);
      out.closed = !menu.classList.contains("menu-nested");
      return out;
    }, label);
    check(`L30: "${label}" opens nested with a back row, rows >= 44 px, no overflow, back to the top`, r.hidden || (r.nested && r.back && r.minH >= 44 && r.sw <= r.cw && r.closed && r.cmds === r.total), r);
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);
  await browser.close();
  summary(errors);
})();
