// gl1005: INBOX 578, "this section in the chat sidebar looks awkward". The
// Chats sidebar head beside the Notes one: one row, one centre line, every
// control the same height as its neighbours, nothing filled, nothing past the
// card's edge, at the sidebar's narrowest and widest.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   [VIEWPORT=390x844] [THEME=dark] node gl1005-chathead.js
const { boot, OUT } = require("./lib.js");
const [W, H] = (process.env.VIEWPORT || "1440x900").split("x").map(Number);
const phone = W < 600;
(async () => {
  const { page, browser } = await boot({ viewport: { width: W, height: H }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message || e)));
  const measure = (sidebarId) =>
    page.evaluate((id) => {
      const aside = document.getElementById(id);
      const head = aside.querySelector(".sidebar-head");
      const box = (el) => {
        if (!el || !el.checkVisibility?.()) return null;
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return null;
        return { l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), h: Math.round(r.height), cy: Math.round((r.top + r.height / 2) * 2) / 2 };
      };
      const a = aside.getBoundingClientRect();
      const parts = {
        title: box(head.querySelector("h2")),
        toggle: box(aside.querySelector(":scope > .sidebar-collapse-toggle")),
      };
      for (const el of head.querySelectorAll("button, .select-shell, select")) {
        if (el.closest(".select-shell") && el.tagName !== "DIV" && !el.classList.contains("select-shell")) continue;
        const b = box(el);
        if (b) parts[el.id || el.className.split(" ")[0]] = b;
      }
      const filled = [...aside.querySelectorAll("button:not(.ghost):not(.sidebar-collapse-toggle):not(.select-opener):not(.conv-item)")].filter((b) => b.checkVisibility?.() && getComputedStyle(b).backgroundColor !== "rgba(0, 0, 0, 0)" && !b.closest("#conversation-list"));
      const under = head.nextElementSibling;
      const centres = Object.values(parts).filter(Boolean).map((p) => p.cy);
      const controls = Object.entries(parts).filter(([k, p]) => p && k !== "title");
      const overflow = Object.values(parts).filter(Boolean).filter((p) => p.l < a.left - 0.5 || p.r > a.right + 0.5);
      const sorted = Object.values(parts).filter(Boolean).sort((p, q) => p.l - q.l);
      let overlaps = 0;
      for (let i = 1; i < sorted.length; i++) if (sorted[i].l < sorted[i - 1].r - 0.5 && Math.abs(sorted[i].cy - sorted[i - 1].cy) < 10) overlaps++;
      return {
        width: Math.round(a.width),
        parts,
        rows: new Set(centres.map((c) => Math.round(c / 6))).size,
        centreSpread: centres.length ? Math.max(...centres) - Math.min(...centres) : 0,
        heights: [...new Set(controls.map(([, p]) => p.h))],
        filled: filled.map((b) => b.id || b.className),
        overflow: overflow.length,
        overlaps,
        headScroll: head.scrollWidth - head.clientWidth,
        titleClipped: (() => {
          const h = head.querySelector("h2");
          const r = document.createRange();
          r.selectNodeContents(h);
          return Math.round(r.getBoundingClientRect().width - h.getBoundingClientRect().width) > 0 || h.scrollWidth > h.clientWidth;
        })(),
        nextIs: under ? under.id || under.className : null,
      };
    }, sidebarId);
  const out = {};
  if (!phone) {
    await page.evaluate(() => document.getElementById("tab-btn-notes")?.click());
    await page.waitForTimeout(800);
    out.notes = await measure("sidebar");
  }
  await page.evaluate(() => document.getElementById("tab-btn-chat")?.click());
  await page.waitForTimeout(1200);
  if (phone) {
    // Below 600 the sidebar is a sheet opened from the dock's leading button.
    await page.evaluate(() => document.querySelector("#tab-chat .dock-nav, #chat-sidebar .sidebar-collapse-toggle")?.click());
    await page.waitForTimeout(600);
  }
  out.chat = await measure("chat-sidebar");
  await page.screenshot({ path: `${OUT}/gl1005-chathead-${W}-${process.env.THEME || "light"}.png`, clip: { x: 0, y: 0, width: Math.min(W, 700), height: 260 } });
  if (!phone) {
    for (const width of [170, 200, 216, 230, 520]) {
      await page.evaluate((w) => {
        const aside = document.getElementById("chat-sidebar");
        applySidebarWidth(aside, w, { remember: false });
      }, width);
      await page.waitForTimeout(400);
      out[`chat@${width}`] = await measure("chat-sidebar");
      await page.screenshot({ path: `${OUT}/gl1005-chathead-${W}-${process.env.THEME || "light"}-${width}.png`, clip: { x: 0, y: 0, width: 700, height: 260 } });
    }
  }
  // The sort still works from the head: pick Name in the menu and read the stored view.
  out.sortWorks = await page.evaluate(async () => {
    document.querySelector("#chat-sidebar-view .kebab-opener").click();
    const row = [...document.querySelectorAll("#chat-sidebar-view .menu-item")].find((b) => /Name/.test(b.textContent));
    row.click();
    await new Promise((r) => setTimeout(r, 400));
    const ok = (await (await fetch("/conversations/view")).json()).sort === "name";
    await fetch("/conversations/view", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sort: "recent" }) });
    return ok;
  });
  const bad = [];
  for (const [k, m] of Object.entries(out)) {
    if (typeof m !== "object") continue;
    if (m.rows > 1) bad.push(`${k}: ${m.rows} rows`);
    if (m.centreSpread > 1) bad.push(`${k}: centres ${m.centreSpread}px apart`);
    if (m.heights.length > 1) bad.push(`${k}: heights ${m.heights}`);
    if (m.titleClipped) bad.push(`${k}: title clipped`);
    if (m.filled.length) bad.push(`${k}: filled ${m.filled}`);
    if (m.overflow || m.overlaps || m.headScroll > 0) bad.push(`${k}: overflow ${m.overflow} overlaps ${m.overlaps} scroll ${m.headScroll}`);
  }
  if (!out.sortWorks) bad.push("sort");
  // The sort lives in the head now: the row under the head is the list.
  for (const k of Object.keys(out).filter((k) => k.startsWith("chat"))) {
    if (out[k].nextIs !== "conversation-list") bad.push(`${k}: under the head is ${out[k].nextIs}`);
  }
  console.log(JSON.stringify({ viewport: `${W}x${H}`, theme: process.env.THEME || "light", ...out, errors }));
  console.log(bad.length || errors.length ? `FAIL ${bad.join("; ")}` : "PASS");
  await browser.close();
})();
