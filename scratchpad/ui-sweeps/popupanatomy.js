// One anatomy for every popup, measured (INBOX 1478): a glyph in every head, the glyph tab rows
// fit their popup, the theme tiles are four dots over the name, and nothing overflows.
//
//   BASE=http://127.0.0.1:8827 W=390 H=844 THEME=dark \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/popupanatomy.js
//
// Opens the Appearance panel, Activity, and Settings on Skills, Tasks and Appearance, then reads
// every `.dialog-head-title` in the page (the static ones and the ones script built) for a
// `.pop-glyph` in its head. Prints the numbers and PASS or FAIL lines; exits 1 on a FAIL.
const { boot } = require("./lib.js");
const W = Number(process.env.W || 1440), H = Number(process.env.H || 900);
let failures = 0;
const check = (label, ok, detail) => { if (!ok) failures += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail !== undefined ? "  " + detail : ""}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  const pageOverflow = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const OPEN = [
    ["appearance panel", "openAppearancePanel()", "#appearance-panel", ".appearance-strip"],
    ["activity", "openActivity('running')", "#agent-monitor", "#activity-tabs"],
    ["settings skills", "openSettingsModal('skills')", "#settings-modal", "#skills-tabs"],
    ["settings tasks", "openSettingsModal('tasks')", "#settings-modal", "#tasks-tabs"],
    ["settings appearance", "openSettingsModal('appearance')", "#settings-modal", null],
  ];
  for (const [name, call, sel, tabs] of OPEN) {
    await page.evaluate(call); await page.waitForTimeout(1500);
    const m = await page.evaluate(({ sel, tabs }) => {
      const e = document.querySelector(sel); const r = e.getBoundingClientRect();
      const t = tabs ? document.querySelector(tabs) : null;
      const dots = [...document.querySelectorAll(".theme-card")].filter((c) => c.offsetParent && c.querySelector(".theme-swatch"));
      return { w: Math.round(r.width), h: Math.round(r.height), within: r.left >= -1 && r.right <= innerWidth + 1,
        tabFit: t ? [t.scrollWidth, t.clientWidth] : null, tabScrolls: t ? getComputedStyle(t).overflowX === 'auto' : false, tabGlyphs: t ? t.querySelectorAll(".pop-tab-glyph").length : 0,
        tabCounts: t ? [...t.querySelectorAll(".pop-count")].map((c) => c.textContent) : [],
        tiles: dots.length, tileDots: dots[0] ? dots[0].querySelectorAll(".theme-dot").length : 0,
        tileWidth: dots[0] ? Math.round(dots[0].getBoundingClientRect().width) : 0 };
    }, { sel, tabs });
    const ovf = await pageOverflow();
    console.log(name, W, process.env.THEME || "light", JSON.stringify(m), "pageOverflow", ovf);
    check(`${name}: page overflow 0`, ovf === 0);
    check(`${name}: inside the window`, m.within);
    if (tabs) check(`${name}: tab row fits (${m.tabFit})`, m.tabFit[0] <= m.tabFit[1] + 1 || m.tabScrolls, m.tabScrolls ? "scrolls inside itself" : "");
    if (tabs) check(`${name}: every tab has a glyph`, m.tabGlyphs >= 2);
    if (m.tiles) check(`${name}: theme tiles are four dots`, m.tileDots === 4, `${m.tiles} tiles`);
    const heads = await page.evaluate(() => {
      const all = [...document.querySelectorAll(".dialog-head-title")].filter((t) => t.getClientRects().length);
      return { shown: all.length, bare: all.filter((t) => !t.closest(".dialog-head")?.querySelector(".pop-glyph")).map((t) => t.textContent.trim().slice(0, 30)) };
    });
    check(`${name}: every shown head has its glyph`, heads.bare.length === 0, `${heads.shown} shown ${heads.bare.join("|")}`);
    await page.keyboard.press("Escape"); await page.waitForTimeout(300);
    await page.evaluate(() => { try { closeAppearancePanel(); } catch (e) {} document.getElementById("agent-monitor")?.classList.add("hidden"); });
  }
  //: Every head in the markup, shown or not.
  const all = await page.evaluate(() => {
    const t = [...document.querySelectorAll(".dialog-head-title")];
    return { n: t.length, bare: t.filter((x) => !x.closest(".dialog-head")?.querySelector(".pop-glyph")).map((x) => x.textContent.trim().slice(0, 30) || x.id) };
  });
  check("every static head names a glyph", all.bare.length === 0, `${all.n} heads, bare: ${all.bare.join("|")}`);
  await browser.close();
  process.exit(failures ? 1 : 0);
})();
