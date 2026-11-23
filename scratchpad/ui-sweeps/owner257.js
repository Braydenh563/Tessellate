// Owner bugs on #257: the notes sidebar on its first open, folded, collapsed and peeked (4 to 6), the
// chats sidebar's peek (6), and no Settings group flush against what is above it (the Atlas memory page).
//
//   4  "Categories" folded with no way back but Manage categories: the rows were never drawn on the
//      first Notes open (the sidebar's render debt was lost), so there was no fold caret either.
//   5  The collapsed rail's hover peek stayed 48px and showed the list squeezed into it.
//
// Every check is a number: row counts, widths, the content's x, children past the sidebar's edge.
// Run: BASE=http://127.0.0.1:8781 THEME=dark node scratchpad/ui-sweeps/owner257.js
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
  // Owner bug 6: the chats sidebar's peek came out wider than the sidebar when its stored width was
  // above the window's 24% cap (stored 520, open 346 at 1440, peek 520). The peek is the open width.
  await page.evaluate(() => [...document.querySelectorAll('[data-tab="chat"]')].find((b) => b.offsetParent)?.click());
  await page.waitForSelector("#chat-sidebar[data-resizable] .sidebar-collapse-toggle", { timeout: 15000 });
  await page.focus("#chat-sidebar .sidebar-resize");
  for (let i = 0; i < 40; i++) await page.keyboard.press("ArrowRight");
  const cw = () => page.evaluate(() => Math.round(document.getElementById("chat-sidebar").getBoundingClientRect().width));
  const chatOpen = await cw();
  await page.click("#chat-sidebar .sidebar-collapse-toggle"); await page.mouse.move(1000, 500); await page.waitForTimeout(700);
  const cat = await page.evaluate(() => { const x = document.getElementById("chat-sidebar").getBoundingClientRect(); return { x: x.x + 24, y: x.y + 300 }; });
  await page.mouse.move(cat.x, cat.y); await page.waitForTimeout(1000);
  const chatPeek = await cw();
  console.log(JSON.stringify({ chatOpen, chatPeek }));
  ok(chatPeek === chatOpen, `6: chat peek ${chatPeek} is not the open ${chatOpen}`);
  await page.click("#chat-sidebar .sidebar-collapse-toggle"); await page.mouse.move(1000, 500);
  await page.focus("#chat-sidebar .sidebar-resize"); await page.keyboard.press("Home");
  // Settings: a group never sits flush on the element above it (What it remembers had 0px above
  // Confirmed patterns; Skills, Tasks and What it learned the same). Every page, every gap.
  await page.evaluate(() => openSettingsModal("memory")); await page.waitForTimeout(1500);
  const names = await page.evaluate(() => [...new Set([...document.querySelectorAll("[data-section]")].map((b) => b.dataset.section))]);
  for (const n of names) {
    await page.evaluate((n) => showSettingsSection(n), n); await page.waitForTimeout(500);
    const flush = await page.evaluate((n) => {
      const sec = document.getElementById("settings-" + n); if (!sec) return [];
      const kids = [...sec.children].filter((e) => e.tagName !== "TEMPLATE" && e.getBoundingClientRect().height > 0);
      const out = [];
      for (let i = 1; i < kids.length; i++) {
        const g = kids[i].getBoundingClientRect().top - kids[i - 1].getBoundingClientRect().bottom;
        if (g < 4 && kids[i].classList.contains("settings-group")) out.push(`${n}: ${kids[i - 1].id || kids[i - 1].className} gap ${Math.round(g)}`);
      }
      return out;
    }, n);
    for (const f of flush) fails.push("settings: " + f);
  }
  // Skill logs peek: no sideways scroll at the peek width (its empty line kept the rail's nowrap).
  await page.keyboard.press("Escape"); await page.waitForTimeout(300);
  await page.evaluate(() => switchTab("library")); await page.waitForTimeout(1500);
  await page.click('[data-target="library-view-skills"]'); await page.waitForTimeout(1500);
  await page.click("#skills-sidebar .sidebar-collapse-toggle"); await page.waitForTimeout(400);
  const sk = await page.locator("#skills-sidebar").boundingBox(); await page.mouse.move(sk.x + 20, sk.y + 100); await page.waitForTimeout(1000);
  const skh = await page.evaluate(() => [...document.querySelectorAll("#skills-sidebar, #skills-sidebar *")].filter((e) => e.scrollWidth > e.clientWidth + 1 && /auto|scroll/.test(getComputedStyle(e).overflowX)).map((e) => e.id || e.className));
  ok(!skh.length, `6: skill logs peek scrolls sideways in ${skh.join(",")}`);
  await page.mouse.move(700, 400); await page.click("#skills-sidebar .sidebar-collapse-toggle");
  await page.keyboard.press("Escape");
  // Documents sidebar at the default and the minimum width: New shows its icon (it was a blank
  // 26px), nothing scrolls sideways, the tabs fit, card meta keeps one line, and both All in
  // Library links have a 6.4px icon gap on one line.
  await page.evaluate(() => switchTab("documents")); await page.waitForTimeout(2500);
  const docs = async (tag) => {
    const r = await page.evaluate(() => {
      const box = (e) => e && e.getBoundingClientRect();
      const icon = box(document.querySelector("#doc-new .ph-lead"));
      const side = box(document.getElementById("doc-sidebar-list"));
      const hs = [...document.querySelectorAll("#doc-sidebar, #doc-sidebar *")].filter((e) => e.scrollWidth > e.clientWidth + 1 && /auto|scroll/.test(getComputedStyle(e).overflowX)).map((e) => e.id || e.className);
      const tabs = [...document.querySelectorAll(".doc-sidebar-tabs > [role=tab]")].filter((t) => t.scrollWidth > t.clientWidth + 1 && getComputedStyle(t).textOverflow !== "ellipsis").length;
      const meta = [...document.querySelectorAll(".doc-item-meta")].filter((m) => m.getBoundingClientRect().height > 24).length;
      const link = document.getElementById("doc-browse-all"); const li = link.querySelector(".ph"); const lt = [...link.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
      const rg = document.createRange(); if (lt) rg.selectNodeContents(lt);
      const tools = box(document.querySelector("#doc-sidebar-list > .sidebar-head > .row"));
      return { icon: icon ? Math.round(icon.width) : 0, hs, tabs, meta, toolsOver: tools && side ? Math.round(tools.right - side.right) : 0,
        gap: lt ? Math.round((rg.getBoundingClientRect().left - li.getBoundingClientRect().right) * 10) / 10 : -1 };
    });
    console.log(JSON.stringify({ tag, ...r }));
    ok(r.icon >= 14, `docs ${tag}: New icon ${r.icon}px`);
    ok(!r.hs.length, `docs ${tag}: sideways scroll in ${r.hs.join(",")}`);
    ok(!r.tabs, `docs ${tag}: ${r.tabs} tabs clip without an ellipsis`);
    ok(!r.meta, `docs ${tag}: ${r.meta} card meta lines wrap`);
    ok(r.toolsOver <= 1, `docs ${tag}: head tools run ${r.toolsOver}px past the edge`);
    ok(r.gap >= 6, `docs ${tag}: All in Library icon gap ${r.gap}`);
  };
  await docs("default");
  await page.focus("#doc-sidebar .sidebar-resize"); for (let i = 0; i < 60; i++) await page.keyboard.press("ArrowLeft"); await page.waitForTimeout(500);
  await docs("min");
  await page.focus("#doc-sidebar .sidebar-resize"); await page.keyboard.press("Home");
  await browser.close();
  console.log(fails.length ? "FAIL\n" + fails.join("\n") : "PASS");
  process.exit(fails.length ? 1 : 0);
})();
