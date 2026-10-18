// The owner, 2026-10-10: "there's no real way to visually distinguish
// between a text box and a note. and note appearances arent changable".
// A sticky is paper (its colour, a lift, a folded corner); a text box is
// words on the board (no fill, no lift, a faint dashed edge). A sticky's
// bar offers its papers; a text box's does not. Measured: fill, shadow,
// the fold, the ink's contrast on every paper and on the board.
//   BASE=http://127.0.0.1:8783 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers [THEME=dark] node scratchpad/ui-sweeps/wbstickylook.js
const { boot } = require("./lib.js");
let fails = 0, passes = 0;
const check = (ok, what) => { console.log(`${ok ? "PASS" : "FAIL"}  ${what}`); ok ? passes++ : fails++; };
const rgb = (s) => (s.match(/[\d.]+/g) || []).slice(0, 4).map(Number);
const lum = ([r, g, b]) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.click('[data-tab="library"]'); await page.waitForTimeout(600);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]'); await page.waitForTimeout(1000);
  const b = await page.evaluate(async () => { await initWhiteboard(); return apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "Sticky look " + Date.now() }) }); });
  await page.evaluate(async (id) => { await openWhiteboardBoard(id); }, b.id); await page.waitForTimeout(900);
  const ids = await page.evaluate(async () => {
    await wbCreateSticky(300, 320); await new Promise((r) => setTimeout(r, 300));
    const sticky = wbState.objects.slice(-1)[0];
    document.activeElement?.blur?.();
    const text = await wbCreateObject("text", { content: "Words on the board" }, 600, 260, 220, 80);
    //: A sticky made before the flag: the old yellow and warm edge.
    const old = await wbCreateObject("text", { content: "Old note", bg: "#fff4a3", border_color: "#e8d56a", color: "#2a2a1f" }, 900, 260, 180, 140);
    sticky.data = { ...sticky.data, content: "A note" };
    await wbSaveObject(sticky);
    renderWhiteboardNow();
    return { sticky: sticky.id, text: text.id, old: old.id };
  });
  await page.keyboard.press("Escape"); await page.waitForTimeout(400);
  const look = await page.evaluate((ids) => {
    const one = (id) => {
      const el = document.querySelector(`.wb-object[data-id="${id}"]`);
      const cs = getComputedStyle(el);
      const after = getComputedStyle(el, "::after");
      return { cls: el.className, bg: cs.backgroundColor, shadow: cs.boxShadow, border: cs.borderTopStyle + " " + cs.borderTopWidth, fold: after.content !== "none" && after.width !== "auto" ? after.width : null, ink: getComputedStyle(el.querySelector(".wb-text-content")).color };
    };
    const ground = getComputedStyle(document.getElementById("whiteboard-container")).getPropertyValue("--wb-board-bg").trim();
    const probe = document.createElement("div"); probe.style.color = ground; document.body.appendChild(probe);
    const groundRgb = getComputedStyle(probe).color; probe.remove();
    return { sticky: one(ids.sticky), text: one(ids.text), old: one(ids.old), ground: groundRgb };
  }, ids);
  check(look.sticky.cls.includes("wb-sticky") && rgb(look.sticky.bg)[2] < 200, `a sticky is paper (${look.sticky.bg})`);
  check(look.sticky.shadow !== "none" && Boolean(look.sticky.fold), `a sticky is lifted, with a folded corner (${look.sticky.shadow.slice(0, 40)}; fold ${look.sticky.fold})`);
  check(look.old.cls.includes("wb-sticky"), "a sticky made before the flag is drawn as one");
  const tbg = rgb(look.text.bg);
  check(!look.text.cls.includes("wb-sticky") && (tbg.length === 4 ? tbg[3] === 0 : false) && look.text.shadow === "none", `a text box has no fill and no lift (${look.text.bg}, ${look.text.shadow})`);
  check(/dashed/.test(look.text.border), `a text box keeps a faint dashed edge (${look.text.border})`);
  const textRatio = ratio(rgb(look.text.ink), rgb(look.ground));
  check(textRatio >= 4.5, `a text box's words on the board ${textRatio.toFixed(2)}:1`);
  // The bar: a sticky offers its papers; a text box does not.
  const pick = async (id) => {
    await page.evaluate((id) => { clearWbSelection(); wbHandleItemClick("object", id, new MouseEvent("click")); }, id);
    await page.waitForTimeout(400);
    return page.evaluate(() => { const g = document.querySelector('#wb-context [data-wb-ctx="paper"]'); return { shown: Boolean(g && !g.classList.contains("hidden") && g.offsetParent), n: g?.children.length || 0, pressed: g?.querySelector('.wb-paper-trigger')?.dataset.paper }; });
  };
  let bar = await pick(ids.sticky);
  check(bar.shown && bar.n === 1 && bar.pressed === "#fff4a3", `a sticky's bar offers one Paper dropdown, the yellow current (${JSON.stringify(bar)})`);
  const papers = await page.evaluate(() => WB_STICKY_PAPERS.map((p) => p.value));
  for (const paper of papers) {
    await page.click("#wb-context .wb-paper-trigger"); await page.waitForTimeout(200);
    const label = await page.evaluate((v) => WB_STICKY_PAPERS.find((p) => p.value === v).label, paper);
    await page.click(`#wb-colour-menu [role="radio"][aria-label="${label}"]`);
    await page.waitForTimeout(350);
    const now = await page.evaluate((id) => { const el = document.querySelector(`.wb-object[data-id="${id}"]`); return { bg: getComputedStyle(el).backgroundColor, ink: getComputedStyle(el.querySelector(".wb-text-content")).color, saved: wbState.objects.find((o) => o.id === id).data.bg }; }, ids.sticky);
    const r = ratio(rgb(now.ink), rgb(now.bg));
    check(now.saved === paper && r >= 4.5, `paper ${paper}: kept, ink ${r.toFixed(2)}:1`);
  }
  bar = await pick(ids.text);
  check(!bar.shown, "a text box's bar has no papers");
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z"); await page.waitForTimeout(500);
  const undone = await page.evaluate((id) => wbState.objects.find((o) => o.id === id).data.bg, ids.sticky);
  check(undone === papers[papers.length - 2], `Ctrl+Z takes one paper back (${undone})`);
  if (process.env.SHOT) await page.screenshot({ path: `${process.env.SCRATCH}/wbstickylook-${process.env.THEME || "light"}.png` });
  check(!errors.length, `no page errors ${errors.join(" | ").slice(0, 200)}`);
  console.log(`${passes}/${passes + fails}`);
  await browser.close();
  process.exit(fails ? 1 : 0);
})();
