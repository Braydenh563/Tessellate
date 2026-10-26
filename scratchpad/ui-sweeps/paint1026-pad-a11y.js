// Quick sketch, WCAG 2.2 pass on the pad itself (the owner's 10-26 polish
// order): text and icon contrast against the first solid background up the
// tree (4.5:1 text, 3:1 icons and large text), a visible focus ring on every
// control reached by Tab, Tab reaching every visible control, target sizes
// (24px floor, 2.5.8), names, and the help popover by keyboard.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=1440 THEME=dark node scratchpad/ui-sweeps/paint1026-pad-a11y.js
const { boot } = require("./lib.js");
const W = Number(process.env.W || 1440);
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 } });
  await page.evaluate(() => openSketch());
  await page.waitForFunction(() => window.SketchPad?.isOpen());
  await page.waitForTimeout(400);
  const contrast = await page.evaluate(() => {
    const parse = (c) => { const m = c.match(/[\d.]+/g); return m ? m.map(Number) : null; };
    const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
    const toRgb = (c) => { const x = document.createElement("canvas").getContext("2d"); x.fillStyle = c; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data]; };
    const bgOf = (e) => { for (let n = e; n; n = n.parentElement) { const c = toRgb(getComputedStyle(n).backgroundColor); if (c[3] > 240) return c; } return [255, 255, 255, 255]; };
    const out = [];
    for (const e of document.querySelectorAll(".sp-root *")) {
      if (!e.getClientRects().length || e.closest(".hidden, .sp-hidden")) continue;
      const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) || e.matches("i.ph");
      if (!own) continue;
      const cs = getComputedStyle(e);
      if (cs.visibility === "hidden" || Number(cs.opacity) === 0) continue;
      const fg = toRgb(cs.color), bg = bgOf(e);
      const a = fg[3] / 255; const mix = fg.slice(0, 3).map((v, i) => v * a + bg[i] * (1 - a));
      const L1 = lum(mix), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      const big = parseFloat(cs.fontSize) >= 18.66 || (parseFloat(cs.fontSize) >= 14 && Number(cs.fontWeight) >= 700) || e.matches("i.ph");
      const need = big ? 3 : 4.5;
      if (ratio < need) out.push(`${e.tagName}.${[...e.classList].join(".")} "${(e.textContent || "").trim().slice(0, 20)}" ${ratio.toFixed(2)} < ${need}`);
    }
    return out;
  });
  console.log("contrast misses", contrast.length, JSON.stringify(contrast.slice(0, 12)));
  const controls = await page.evaluate(() => [...document.querySelectorAll(".sp-root :is(button, input, select, textarea, [tabindex])")].filter((e) => e.getClientRects().length && !e.closest(".hidden, .sp-hidden") && !e.disabled && e.tabIndex >= 0 && !e.matches(".sp-visually-hidden *, .sp-visually-hidden")).length);
  const small = await page.evaluate(() => [...document.querySelectorAll(".sp-root :is(button, input, label)")].filter((e) => e.getClientRects().length && !e.closest(".hidden, .sp-hidden")).map((e) => { const r = e.getBoundingClientRect(); return [e.className || e.tagName, Math.round(r.width), Math.round(r.height)]; }).filter(([, w, h]) => w < 24 || h < 24));
  console.log("targets under 24px", small.length, JSON.stringify(small.slice(0, 8)));
  await page.evaluate(() => { let i = 0; for (const e of document.querySelectorAll(".sp-root *")) e.dataset.a11y = String(i++); });
  await page.focus("[data-sp=close]");
  const seen = new Set(); const noRing = []; let steps = 0;
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press("Tab"); steps++;
    const f = await page.evaluate(() => {
      const e = document.activeElement; if (!e || !e.closest(".sp-root")) return { out: true, tag: e && e.tagName + "." + e.className };
      const cs = getComputedStyle(e); const ring = (cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) >= 2) || /0px 0px 0px [2-9]/.test(cs.boxShadow);
      return { id: e.dataset.a11y + ":" + (e.dataset.sp || e.dataset.tool || e.dataset.mode || e.getAttribute("aria-label") || ""), ring };
    });
    if (f.out) { console.log("focus left the pad after", steps, f.tag); break; }
    if (seen.has(f.id)) break;
    seen.add(f.id); if (!f.ring) noRing.push(f.id);
  }
  console.log("tab reached", seen.size, "of", controls, "focusable; without a ring", JSON.stringify(noRing));
  await page.focus("[data-help-for=sketch-help]"); await page.keyboard.press("Enter"); await page.waitForTimeout(200);
  const help = await page.evaluate(() => { const p = document.getElementById("sketch-help"); const r = p.getBoundingClientRect(); return { shown: !p.classList.contains("hidden") && r.height > 0, inView: r.bottom <= innerHeight && r.right <= innerWidth && r.left >= 0, h: Math.round(r.height) }; });
  console.log("help by keyboard", JSON.stringify(help));
  await page.keyboard.press("Escape"); await page.waitForTimeout(150);
  console.log("Esc closes help, pad stays", await page.evaluate(() => [document.getElementById("sketch-help").classList.contains("hidden") || !document.getElementById("sketch-help").getClientRects().length, SketchPad.isOpen()]));
  const more = await page.$(".sp-actions [aria-haspopup], .sp-actions .kebab-btn, .sp-actions [aria-label^='More']");
  if (more) {
    await more.focus(); await page.keyboard.press("Enter"); await page.waitForTimeout(250);
    const opened = await page.evaluate(() => [...document.querySelectorAll("[role=menu]")].filter((m) => m.getClientRects().length && getComputedStyle(m).visibility !== "hidden").length);
    await page.keyboard.press("Escape"); await page.waitForTimeout(250);
    const after = await page.evaluate(() => [[...document.querySelectorAll("[role=menu]")].filter((m) => m.getClientRects().length && getComputedStyle(m).visibility !== "hidden").length, SketchPad.isOpen()]);
    console.log("More menu by keyboard: open menus", opened, "after Esc", after[0], "pad open", after[1]);
  } else console.log("More menu: opener not found");
  console.log("the opener got focus back on close:", await page.evaluate(async () => { await SketchPad.requestClose(); return [document.activeElement?.id || document.activeElement?.tagName, SketchPad.isOpen()]; }));
  await browser.close();
})();
