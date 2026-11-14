// INBOX 311: the nav history says you have been to Notes on a fresh load.
//
// The owner, 2026-09-21: "when I load up the application, the bottom nav
// history dropdown shows me being in the notes tab and having been to the
// notes tab even when I havent moved from the dashboard". The screenshot
// shows the pin on a "Notes -> Your notes" row above a "Dashboard" row.
//
// The measurement is the stack itself, not the menu: a menu drawn correctly
// from a wrong stack is still wrong, and the stack is one `page.evaluate`
// away. A fresh context, a login, no navigation at all, then read
// `tabHistory`.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

(async () => {
  const { browser, page } = await boot();
  //: Give every postponed initialiser its chance to run. The fault is a boot
  //: step, so a probe that reads too early would miss it.
  await page.waitForTimeout(3000);

  const read = () =>
    page.evaluate(() => ({
      stack: tabHistory.stack.map((e) => `${e.tab}${e.section ? ":" + e.section : ""}`),
      index: tabHistory.index,
      activeTab: localStorage.getItem("activeTab"),
      visible: [...document.querySelectorAll("#tabs button, .tab-button")]
        .filter((b) => b.classList.contains("active"))
        .map((b) => b.dataset.tab),
      menu: null,
    }));

  const fresh = await read();
  console.log("  fresh load:", JSON.stringify(fresh));
  ok(
    "a fresh load has visited exactly one place",
    fresh.stack.length === 1,
    `${fresh.stack.length} entries: ${JSON.stringify(fresh.stack)}`
  );
  ok(
    "and that place is the tab on screen",
    fresh.stack.length === 1 && fresh.stack[0].startsWith(fresh.activeTab || "dashboard"),
    `stack ${JSON.stringify(fresh.stack)} against activeTab ${fresh.activeTab}`
  );
  ok("with the pin on it", fresh.index === fresh.stack.length - 1, `index ${fresh.index}`);

  //: Back must be dead on arrival: there is nowhere behind you.
  const backOff = await page.evaluate(() => {
    const b = document.getElementById("status-back");
    return b ? b.disabled : null;
  });
  ok("and Back disabled, because there is nowhere behind you", backOff === true, String(backOff));

  //: And the tab really is a navigation once you make one, so the fix must
  //: not buy a clean boot by breaking the feature.
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(1200);
  const moved = await read();
  console.log("  after one move:", JSON.stringify(moved));
  ok(
    "moving to Notes records one step, not two",
    moved.stack.length === 2,
    JSON.stringify(moved.stack)
  );
  ok(
    "and lands on Notes",
    moved.stack[moved.index] && moved.stack[moved.index].startsWith("notes"),
    `${moved.stack[moved.index]} at index ${moved.index}`
  );
  const backOn = await page.evaluate(() => document.getElementById("status-back")?.disabled);
  ok("with Back live now", backOn === false, String(backOn));

  //: Going back must return to the dashboard in one press, which is the
  //: other half of the original report ("I need to click back twice").
  await page.evaluate(() => document.getElementById("status-back")?.click());
  await page.waitForTimeout(1200);
  const back = await read();
  ok(
    "one Back press returns to the dashboard",
    back.activeTab === "dashboard",
    `activeTab ${back.activeTab}, index ${back.index}, stack ${JSON.stringify(back.stack)}`
  );

  console.log(bad ? `FAILURES: ${bad}` : "ALL PASS");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
