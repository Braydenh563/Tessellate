// The notes sidebar on its first open, folded, collapsed and peeked (owner bugs 4 and 5 on #257).
//
//   4  "Categories" folded with no way back but Manage categories: the rows were never drawn on the
//      first Notes open (the sidebar's render debt was lost), so there was no fold caret either.
//   5  The collapsed rail's hover peek stayed 48px and showed the list squeezed into it.
//
// Every check is a number: row counts, widths, the content's x, children past the sidebar's edge.
// Run: BASE=http://127.0.0.1:8781 THEME=dark node scratchpad/ui-sweeps/notessidebar257.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({});
  const fails = [];
  const ok = (cond, msg) => { if (!cond) fails.push(msg); };
  await page.evaluate(() => [...document.querySelectorAll('[data-tab="notes"]')].find((b) => b.offsetParent)?.click());
  await page.waitForSelector("#sidebar[data-resizable] > .sidebar-collapse-toggle", { timeout: 5000 }).catch(() => fails.push("notes sidebar not wired within 5 s"));
  await page.waitForTimeout(800);
  const m = (label) => page.evaluate((label) => {
    const sb = document.getElementById("sidebar"); const b = sb.getBoundingClientRect();
    const main = sb.parentElement.querySelector(".tab-main").getBoundingClientRect();
    const seen = (e) => { let o = 1; for (let n = e; n && n !== sb; n = n.parentElement) o *= +getComputedStyle(n).opacity; return o > 0.05 && e.getBoundingClientRect().width > 0; };
    const clipped = [...sb.querySelectorAll("*")].filter((e) => { const x = e.getBoundingClientRect(); return seen(e) && x.height > 0 && getComputedStyle(e).visibility !== "hidden" && (x.right > b.right + 0.5 || x.left < b.left - 0.5); }).length;
    const caret = sb.querySelector(":scope > .sidebar-head .sidebar-fold-toggle");
    return { label, w: Math.round(b.width), mainX: Math.round(main.left), clipped, rows: [...sb.querySelectorAll("#category-list > li")].filter(seen).length,
      caret: caret ? { w: Math.round(caret.getBoundingClientRect().width), expanded: caret.getAttribute("aria-expanded") } : null };
  }, label);
  const open = await m("open"); console.log(JSON.stringify(open));
  ok(open.rows > 0, "4: no category rows on the first Notes open");
  ok(open.caret && open.caret.w > 0, "4: no fold caret");
  await page.click("#sidebar > .sidebar-head .sidebar-fold-toggle"); await page.waitForTimeout(400);
  const folded = await m("folded"); console.log(JSON.stringify(folded));
  ok(folded.rows === 0 && folded.caret?.w > 0 && folded.caret.expanded === "false", "4: folded Categories has no visible expand control");
  await page.click("#sidebar > .sidebar-head .sidebar-fold-toggle"); await page.waitForTimeout(400);
  await page.click("#sidebar .sidebar-collapse-toggle"); await page.mouse.move(900, 500); await page.waitForTimeout(800);
  const rail = await m("rail"); console.log(JSON.stringify(rail));
  ok(rail.w === 48 && rail.rows === 0 && rail.clipped === 0, "5: the rail is not a clean 48px");
  const at = await page.evaluate(() => { const x = document.getElementById("sidebar").getBoundingClientRect(); return { x: x.x + 24, y: x.y + 300 }; });
  await page.mouse.move(at.x, at.y); await page.waitForTimeout(1200);
  const peek = await m("peek"); console.log(JSON.stringify(peek));
  ok(peek.w === open.w, `5: peek ${peek.w} is not the expanded ${open.w}`);
  ok(peek.mainX === rail.mainX, "5: the peek moved the content instead of overlaying it");
  ok(peek.clipped === 0 && peek.rows === open.rows, "5: the peek clips or drops rows");
  await page.mouse.move(900, 500); await page.waitForTimeout(800);
  await page.click("#sidebar .sidebar-collapse-toggle").catch(() => {});
  await browser.close();
  console.log(fails.length ? "FAIL\n" + fails.join("\n") : "PASS");
  process.exit(fails.length ? 1 : 0);
})();
