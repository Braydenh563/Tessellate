// Popup glass, measured (INBOX 1478, the owner: how does the reference app do glass).
// Text contrast of a floating popup under the reference's glass values, over the real
// dashboard and over a black and white stripe backdrop (the worst case):
//
//   BASE=http://127.0.0.1:8827 THEME=dark PANEL=appearance|activity \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/popupglass.js
//
// Per variant: text runs, the lowest ratio, the runs under AA (4.5:1, 3:1 for large text).
// `current` is the shipped CSS; the others are injected through a constructed sheet (the CSP
// refuses a style element) over it: `reference` is the reference's own tint, highlight, blur and
// border, `tint72` and `tint90` the panel colour at that opacity with the reference blur.
const { boot } = require("./lib.js");
const PANEL = process.env.PANEL || "appearance";
const SEL = PANEL === "activity" ? "#agent-monitor" : "#appearance-panel";
const VARIANTS = {
  current: "",
  reference: `${SEL}{background-color:color-mix(in srgb, var(--panel) 32%, transparent)!important;background-image:linear-gradient(180deg,color-mix(in srgb,var(--ink) 14%,transparent) 0%,color-mix(in srgb,var(--ink) 4%,transparent) 26%,transparent 55%)!important;backdrop-filter:blur(24px) saturate(170%)!important;border-color:color-mix(in srgb,var(--ink) 22%,transparent)!important}`,
  tint72: `${SEL}{background-color:color-mix(in srgb, var(--panel) 72%, transparent)!important;backdrop-filter:blur(24px) saturate(170%)!important}`,
  tint90: `${SEL}{background-color:color-mix(in srgb, var(--panel) 90%, transparent)!important;backdrop-filter:blur(24px) saturate(170%)!important}`,
};
(async () => {
  const th = process.env.THEME || "light";
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate((w) => (w === "activity" ? openActivity("running") : openAppearancePanel()), PANEL); await page.waitForTimeout(1500);
  const out = {};
  for (const back of ["page", "stripes"]) {
    for (const [name, css] of Object.entries(VARIANTS)) {
      await page.evaluate(({ css, back }) => {
        document.getElementById("glassback")?.remove();
        const sheet = new CSSStyleSheet(); sheet.replaceSync(css);
        document.adoptedStyleSheets = [sheet];
        if (back === "stripes") {
          const d = document.createElement("div"); d.id = "glassback";
          d.style.position = "fixed"; d.style.inset = "0"; d.style.zIndex = "1";
          d.style.background = "repeating-linear-gradient(90deg,#000 0 6px,#fff 6px 12px)";
          document.body.appendChild(d);
        }
      }, { css, back });
      await page.waitForTimeout(400);
      const buf = await page.screenshot();
      const res = await page.evaluate(async ({ b64, SEL }) => {
        const img = new Image(); img.src = "data:image/png;base64," + b64; await img.decode();
        const cv = document.createElement("canvas"); cv.width = img.width; cv.height = img.height;
        const cx = cv.getContext("2d", { willReadFrequently: true }); cx.drawImage(img, 0, 0);
        const panel = document.querySelector(SEL);
        const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
        const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
        const rows = [];
        const pr = panel.getBoundingClientRect();
        const w = document.createTreeWalker(panel, NodeFilter.SHOW_TEXT);
        let n;
        while ((n = w.nextNode())) {
          if (!n.textContent.trim()) continue;
          const el = n.parentElement; const cs = getComputedStyle(el);
          if (cs.visibility === "hidden" || cs.display === "none") continue;
          const range = document.createRange(); range.selectNodeContents(n); const r = range.getBoundingClientRect();
          if (r.width < 4 || r.height < 4 || r.bottom > pr.bottom || r.top < pr.top || r.right > pr.right) continue;
          const c1 = document.createElement('canvas'); c1.width = c1.height = 1; const x1 = c1.getContext('2d', { willReadFrequently: true }); x1.fillStyle = cs.color; x1.fillRect(0, 0, 1, 1); const fg = [...x1.getImageData(0, 0, 1, 1).data].slice(0, 3);
          const x = Math.round(r.left), y = Math.round(r.top), ww = Math.max(1, Math.round(r.width)), hh = Math.max(1, Math.round(r.height));
          const d = cx.getImageData(x, y, ww, hh).data; const cnt = new Map();
          for (let i = 0; i < d.length; i += 4) { const k = (d[i] >> 3) + "," + (d[i + 1] >> 3) + "," + (d[i + 2] >> 3); cnt.set(k, (cnt.get(k) || 0) + 1); }
          let best = null, bc = 0; for (const [k, c] of cnt) if (c > bc) { bc = c; best = k; }
          const bg = best.split(",").map((v) => v * 8 + 4);
          const size = parseFloat(cs.fontSize); const large = size >= 24 || (size >= 18.66 && parseInt(cs.fontWeight) >= 700);
          rows.push({ t: n.textContent.trim().slice(0, 18), ratio: ratio(fg, bg), need: large ? 3 : 4.5 });
        }
        const fails = rows.filter((r) => r.ratio < r.need);
        return { n: rows.length, min: Math.min(...rows.map((r) => r.ratio)).toFixed(2), fails: fails.length, worst: fails.sort((a, b) => a.ratio - b.ratio).slice(0, 3).map((f) => f.t + ":" + f.ratio.toFixed(2)) };
      }, { b64: buf.toString("base64"), SEL });
      console.log(th, back.padEnd(8), name.padEnd(9), JSON.stringify(res));
    }
  }
  await browser.close();
})();
