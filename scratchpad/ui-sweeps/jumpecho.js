// P32: the phone's jump list repeats a pane's title, so the pane's h3 is dropped
// from view (`.jump-echo`). It must stay in the accessibility tree: clipped to
// 1px, not display: none. Measures Memory, Logs and Models at 390 (phone) and a
// wide window, and the dock the hidden title leaves behind.
//   LIB=$PWD/scratchpad/ui-sweeps/lib.js BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/jumpecho.js
const { boot } = require(process.env.LIB || "./lib.js");

(async () => {
  let failures = 0;
  for (const vp of [{ width: 390, height: 844, phone: true }, { width: 1440, height: 900, phone: false }]) {
    const { page, browser } = await boot({ viewport: { width: vp.width, height: vp.height }, isMobile: vp.phone });
    await page.evaluate(() => openSettingsModal("general"));
    await page.waitForSelector("#settings-modal:not(.hidden)", { timeout: 15000 });
    await page.waitForTimeout(800);
    const panes = await page.evaluate(() => [...document.querySelectorAll("#settings-modal .settings-section")].map((s) => s.id.replace("settings-", "")));
    const rows = [];
    for (const id of panes) {
      await page.evaluate((id) => openSettingsModal(id), id).catch(() => null);
      await page.waitForTimeout(250);
      const r = await page.evaluate((id) => {
        const h = document.querySelector(`#settings-${CSS.escape(id)} h3.jump-echo`);
        if (!h) return null;
        const b = h.getBoundingClientRect();
        const cs = getComputedStyle(h);
        const dock = h.closest(".dock");
        const d = dock ? dock.getBoundingClientRect() : null;
        return { id, text: h.textContent.trim(), display: cs.display, w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10, clip: cs.clipPath, dockH: d ? Math.round(d.height) : null, dockDisplay: dock ? getComputedStyle(dock).display : null };
      }, id);
      if (r) rows.push(r);
    }
    console.log(vp.width, JSON.stringify(rows));
    if (vp.phone) {
      for (const r of rows) {
        const bad = r.display === "none" || r.w > 1.5 || r.h > 1.5 || r.dockDisplay === "none";
        if (bad) { failures += 1; console.log("FAIL", r.id, JSON.stringify(r)); }
      }
      if (!rows.length) { failures += 1; console.log("FAIL no echoed title found at 390"); }
    }
    await browser.close();
  }
  console.log(failures ? `FAILURES: ${failures}` : "ALL PASS");
  process.exit(failures ? 1 : 0);
})();
