// UX audit 1018 (uxfix2). MODE picks the check; BASE=http://127.0.0.1:8809
//   MODE=map      a new empty map shows one empty state (item 3)
//   MODE=boards   the boards header count and the picker agree (item 11)
//   MODE=palette  open time (median of 5) and a note found by name (items 5, 10)
//   MODE=bell     the first-run bell badge ignores system-log lines (item 12)
//   MODE=more     the tab bar's More shows the reminders due count (item 8)
// VIEWPORT=390x844 for the phone checks.
const { boot, openBoardsTab, waitForBoardOpen } = require("./lib.js");
const [W, H] = (process.env.VIEWPORT || "1440x900").split("x").map(Number);
const median = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];

(async () => {
  const phone = W < 600;
  const { page, browser } = await boot({ viewport: { width: W, height: H }, hasTouch: phone, isMobile: phone });
  const mode = process.env.MODE || "map";
  if (mode === "map") {
    await openBoardsTab(page);
    await page.evaluate(async () => {
      const board = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `m ${Date.now()}`, type: "map" }) });
      await openWhiteboardBoard(board.id);
    });
    await waitForBoardOpen(page, 0);
    await page.waitForTimeout(800);
    console.log("map", JSON.stringify(await page.evaluate(() => {
      const v = (id) => { const e = document.getElementById(id); if (!e || e.hidden || !e.offsetParent) return null; const r = e.getBoundingClientRect(); return Math.round(r.width) + "x" + Math.round(r.height); };
      return { templates: v("wb-map-templates"), empty: v("wb-map-empty") };
    })));
  } else if (mode === "boards") {
    await page.evaluate(async () => {
      for (const b of await apiJson("/whiteboard/boards")) if (b.id != null) await apiJson("/entries/" + b.id, { method: "DELETE" });
    });
    await openBoardsTab(page);
    await page.waitForTimeout(1500);
    console.log("boards", JSON.stringify(await page.evaluate(() => ({
      chips: [...document.querySelectorAll("#library-boards-filter button")].map((b) => b.innerText.replace(/\s+/g, " ")),
      options: [...document.getElementById("wb-board-select").options].map((o) => o.textContent),
    }))));
  } else if (mode === "palette") {
    await page.evaluate(async () => {
      const have = await apiJson("/search?q=Lisbon&kind=note&limit=1").catch(() => null);
      if (!have?.hits?.length) await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "# Trip to Lisbon\nbook flights", category: "Notes" }) }).catch(() => null);
    });
    await page.waitForTimeout(500);
    const open = [];
    const shown = [];
    for (let i = 0; i < 5; i++) {
      const r = await page.evaluate(() => new Promise((resolve) => {
        const t0 = performance.now();
        const input = document.getElementById("palette-input");
        let focused = null;
        input.addEventListener("focus", () => { if (focused === null) focused = performance.now() - t0; }, { once: true });
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }));
        const sync = Math.round(performance.now() - t0);
        window.__paletteSync = sync;
        const tick = () => {
          const rows = document.querySelectorAll("#palette-list [role=option]").length;
          if (focused !== null && rows > 20) return resolve({ sync, focused: Math.round(focused), rows: Math.round(performance.now() - t0) });
          if (performance.now() - t0 > 3000) return resolve({ focused: Math.round(focused ?? -1), rows: -1 });
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }));
      console.log('sync ms', r.sync, 'focus', r.focused, 'rows', r.rows);
      open.push(r.focused);
      shown.push(r.rows);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }
    console.log("palette open ms: focus", JSON.stringify(open), "median", median(open), "| rows", JSON.stringify(shown), "median", median(shown));
    await page.keyboard.press("Control+k");
    await page.waitForTimeout(500);
    await page.keyboard.type("Trip", { delay: 30 });
    await page.waitForTimeout(1200);
    console.log("rows for Trip", JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("#palette-list [role=option]")].map((r) => r.innerText.replace(/\s+/g, " ").slice(0, 70)))));
    await page.keyboard.press("ArrowDown"); await page.keyboard.press("ArrowDown"); await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(1200);
    console.log("after Enter", JSON.stringify(await page.evaluate(() => ({ paletteHidden: document.getElementById("palette-overlay").classList.contains("hidden"), tab: document.querySelector(".tab.active, [data-tab].active")?.dataset?.tab }))));
  } else if (mode === "bell") {
    await page.waitForTimeout(2500);
    console.log("bell", JSON.stringify(await page.evaluate(async () => {
      const badge = document.querySelector("#notif-badge, .notif-badge, #bell-badge");
      return { badge: badge ? badge.textContent : null, badgeId: badge?.id || null };
    })));
  } else if (mode === "more") {
    await page.waitForTimeout(1500);
    console.log("more", JSON.stringify(await page.evaluate(() => {
      const more = document.querySelector('[data-tab="more"], #tab-more, .tab-more');
      return { more: more ? more.innerText.replace(/\s+/g, " ") : null, badge: more?.querySelector(".badge, .tab-badge, [class*=badge]")?.textContent ?? null };
    })));
  }
  await browser.close();
})();
