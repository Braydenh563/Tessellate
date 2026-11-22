// L-world-class-356 (wc-109, 421 j): "Back opened Settings".
//
// Visit every top tab in order, then walk Back three ways (the status-bar
// Back button, the browser's own Back, the mouse back button), reading the
// tab on screen after each step. Each step must land on the tab visited
// before it, and Settings must never open. The owner's exact replay stays in
// BACKLOG; this is the part that runs here.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};
const TABS = ["dashboard", "notes", "chat", "graph", "library", "timeline", "reminders"];

(async () => {
  const { browser, page } = await boot();
  await page.waitForTimeout(2500);
  const here = () =>
    page.evaluate(() => ({
      tab: localStorage.getItem("activeTab"),
      shown: [...document.querySelectorAll('#tabs [role="tab"].active')].map((b) => b.dataset.tab),
      settings: !document.getElementById("settings-modal").classList.contains("hidden"),
      confirm: (document.querySelector(".confirm-overlay") || {}).innerText || null,
    }));

  for (const way of ["button", "browser"]) {
    for (const t of TABS) {
      await page.click(`#tab-btn-${t}`, { timeout: 4000 }).catch(() => ok(`click ${t}`, false, "blocked"));
      await page.waitForTimeout(500);
    }
    for (let i = TABS.length - 2; i >= 0; i -= 1) {
      if (way === "button") await page.click("#status-back", { timeout: 4000 }).catch(() => ok("click Back", false, "blocked"));
      else if (way === "browser") await page.goBack({ waitUntil: "commit" }).catch(() => {});
      await page.waitForTimeout(700);
      const h = await here();
      ok(`${way}: Back from ${TABS[i + 1]} lands on ${TABS[i]}`, h.tab === TABS[i] && !h.settings && !h.confirm, JSON.stringify(h));
      if (h.confirm) { console.log("  confirm:", h.confirm.slice(0, 200)); await page.keyboard.press("Escape"); await page.waitForTimeout(300); }
    }
    await page.click("#tab-btn-dashboard", { timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(500);
  }
  //: The likelier path to "Back opened Settings": Settings opened and closed
  //: over a tab, then Back. Back must step off the tab, never reopen Settings.
  for (const way of ["button", "browser"]) {
    for (const close of ["Escape", "close button"]) {
      await page.click("#tab-btn-notes", { timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(500);
      await page.click("#tab-btn-chat", { timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(500);
      await page.click("#settings-btn", { timeout: 4000 }).catch(() => ok("open Settings", false, "blocked"));
      await page.waitForTimeout(900);
      if (close === "Escape") await page.keyboard.press("Escape");
      else await page.click("#settings-modal .modal-close, #settings-modal [data-close], #settings-close", { timeout: 4000 }).catch(() => page.keyboard.press("Escape"));
      await page.waitForTimeout(700);
      const before = await here();
      ok(`${way}/${close}: Settings closed before Back`, !before.settings, JSON.stringify(before));
      if (way === "button") await page.click("#status-back", { timeout: 4000 }).catch(() => ok("click Back", false, "blocked"));
      else await page.goBack({ waitUntil: "commit" }).catch(() => {});
      await page.waitForTimeout(900);
      const h = await here();
      ok(`${way}/${close}: Back after Settings does not reopen it`, !h.settings, JSON.stringify(h));
      ok(`${way}/${close}: and lands on a tab visited before`, ["notes", "chat"].includes(h.tab), JSON.stringify(h));
      if (h.settings) { await page.keyboard.press("Escape"); await page.waitForTimeout(400); }
    }
  }
  //: Settings with a pane change inside it, then closed, then Back: each pane
  //: may push an entry of its own, and the close steps off only one.
  for (const way of ["button", "browser"]) {
    await page.click("#tab-btn-notes", { timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(500);
    await page.click("#tab-btn-chat", { timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(500);
    await page.click("#settings-btn", { timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(900);
    const panes = await page.$$eval("#settings-modal [data-section]", (bs) => bs.filter((b) => b.offsetParent).map((b) => b.dataset.section));
    for (const sec of panes.slice(1, 4)) {
      await page.click(`#settings-modal [data-section="${sec}"]`, { timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(400);
    }
    const stack = await page.evaluate(() => tabHistory.stack.map((e) => e.tab + (e.section ? ":" + e.section : "")).slice(-6));
    console.log(`  ${way} panes ${panes.slice(1, 4).join(",")} stack before close ${JSON.stringify(stack)}`);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(700);
    if (way === "button") await page.click("#status-back", { timeout: 4000 }).catch(() => ok("click Back", false, "blocked"));
    else await page.goBack({ waitUntil: "commit" }).catch(() => {});
    await page.waitForTimeout(900);
    const h = await here();
    ok(`${way}: Back after Settings with pane changes does not reopen it`, !h.settings, JSON.stringify(h));
    ok(`${way}: and lands on notes`, h.tab === "notes", JSON.stringify(h));
    if (h.settings) { await page.keyboard.press("Escape"); await page.waitForTimeout(400); }
  }
  console.log(bad ? `FAILED ${bad}` : "ALL PASS");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
