// INBOX 430: "perch and ride on UI elements on every tab and scroll with
// them, as it does on the Dashboard". For each tab: where the companion
// settles (the perch kind, its pose, the element it is on), whether it
// rides a scroll area, and, where the tab has one that scrolls, whether it
// stays on its element when that area is scrolled 160px (moved with it to
// within 3px). Env: KIND (atlas), TABS (all), W (1440). Exits 1 when a tab
// leaves it on a window bar ("bar" or "hang") while a panel was free, or a
// ride loses its panel.
const { boot } = require("./lib.js");

(async () => {
  const { browser, page, OUT } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 } });
  await page.evaluate(async (k) => { localStorage.removeItem("nm-buddy-spots"); prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, process.env.KIND || "atlas");
  const tabs = (process.env.TABS || "dashboard,notes,chat,graph,library,documents,timeline,reminders").split(",");
  let bad = false;
  for (const tab of tabs) {
    await page.evaluate((t) => switchTab(t), tab);
    await page.waitForTimeout(Number(process.env.WAIT || 2600));
    const r = await page.evaluate(() => {
      const buddy = document.getElementById("nm-buddy");
      const face = buddy?.querySelector(".nm-figure") || buddy;
      const b = face.getBoundingClientRect();
      const anchor = nmb.anchor || null;
      const name = (el) => (el ? `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${el.classList.length ? `.${[...el.classList].slice(0, 2).join(".")}` : ""}` : "");
      return { perch: nmb.perch, pose: nmb.pose, on: name(nmb.glue?.el || nmb.target?.anchor || anchor), ride: name(nmb.ride?.el), box: [b.left, b.top].map(Math.round) };
    });
    if (process.env.SHOT) await page.screenshot({ path: `${OUT}/companiontabs-${tab}-${process.env.SHOT}.png` });
    let rode = "";
    if (r.ride) {
      const moved = await page.evaluate(async () => {
        const el = nmb.ride.el;
        const face = document.getElementById("nm-buddy").querySelector(".nm-figure");
        const y0 = face.getBoundingClientRect().top;
        const s0 = el.scrollTop;
        el.scrollTop = s0 + 160;
        await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
        const y1 = face.getBoundingClientRect().top;
        const by = el.scrollTop - s0;
        el.scrollTop = s0;
        return { by, moved: Math.round(y0 - y1) };
      });
      rode = ` scrolled ${moved.by}px, moved ${moved.moved}px`;
      if (moved.by > 0 && Math.abs(moved.by - moved.moved) > 3) bad = true;
    }
    const onBar = ["bar", "hang", "corner"].includes(r.perch);
    if (onBar && process.env.STRICT) bad = true;
    console.log(`${tab}: ${r.perch}/${r.pose} on ${r.on || "-"} ride ${r.ride || "-"} at ${r.box}${rode}${onBar ? "  (window bar)" : ""}`);
  }
  console.log(bad ? "FAIL" : "PASS");
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
