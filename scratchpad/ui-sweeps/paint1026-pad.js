// INBOX 1352 and the owner's 10-26 Quick sketch brief: the redesigned pad
// (sketch-pad.js), every tool end to end in the app. Fit at W (no overflow,
// the card inside the window), every tool's key in its tooltip and on the
// keyboard, shapes from the corner and with Alt from the centre, Shift
// squares and 45 degrees, the three shape styles, fill, the picker, text in
// place, polygon, select and move, undo and redo, Escape mid-shape, zoom, the
// status line, PNG download, and the frame time of a long brush stroke.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=1440 node scratchpad/ui-sweeps/paint1026-pad.js
//   STANDALONE=http://127.0.0.1:8862/tools/sketch-standalone/ runs it on the page of its own.
const { boot } = require("./lib.js");
const PW = "/opt/node22/lib/node_modules/playwright";
const W = Number(process.env.W || 1440);
const HGT = Number(process.env.H || (W < 600 ? 844 : 900));
const PHONE = W < 600;
const STANDALONE = process.env.STANDALONE || "";

let pass = 0, fail = 0;
function check(name, good, detail) {
  if (good) pass++; else fail++;
  console.log(`${good ? "PASS" : "FAIL"}  ${name}${detail !== undefined ? "  " + JSON.stringify(detail) : ""}`);
}

async function open() {
  if (!STANDALONE) {
    const { browser, page } = await boot({ viewport: { width: W, height: HGT }, ...(PHONE ? { hasTouch: true, isMobile: true } : {}) });
    return { browser, page };
  }
  const { chromium } = require(PW);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: HGT }, acceptDownloads: true, ...(PHONE ? { hasTouch: true, isMobile: true } : {}) });
  const page = await ctx.newPage();
  await page.goto(STANDALONE, { waitUntil: "domcontentloaded" });
  return { browser, page };
}

(async () => {
  const { browser, page } = await open();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let prompted = 0;
  page.on("dialog", (d) => { prompted++; d.dismiss(); });
  if (!STANDALONE) await page.evaluate(() => openSketch());
  await page.waitForFunction(() => window.SketchPad?.isOpen());
  await page.waitForTimeout(500);

  // --- fit ---
  const fit = await page.evaluate(() => {
    const root = document.querySelector(".sp-root");
    const card = root.getBoundingClientRect();
    const over = [...root.querySelectorAll("button, input, label, output, .sp-viewport, .sp-rail, .sp-bar, .sp-status, .sp-foot")]
      .filter((e) => e.getClientRects().length && !e.closest(".sp-hidden, .hidden, .sp-visually-hidden"))
      .filter((e) => { const r = e.getBoundingClientRect(); return r.right > card.right + 1 || r.left < card.left - 1 || r.bottom > card.bottom + 1; })
      .map((e) => e.className || e.tagName).slice(0, 5);
    const tools = [...root.querySelectorAll(".sp-tool")];
    const titled = [...root.querySelectorAll("button")].filter((b) => b.getClientRects().length && !(b.title || b.textContent.trim()));
    const sizes = [...root.querySelectorAll(".sp-btn")].filter((b) => b.getClientRects().length).map((b) => Math.round(b.getBoundingClientRect().height));
    const vp = root.querySelector(".sp-viewport").getBoundingClientRect();
    const stage = root.querySelector(".sp-stage").getBoundingClientRect();
    return {
      vw: innerWidth, vh: innerHeight, pageOverflow: document.documentElement.scrollWidth > innerWidth,
      card: [Math.round(card.width), Math.round(card.height), Math.round(card.bottom)], over,
      tools: tools.length, keyed: tools.filter((b) => /^[^:]+ \([A-Z]\): ./.test(b.title)).length, untitled: titled.length,
      btnHeights: [...new Set(sizes)], page: [Math.round(stage.width), Math.round(stage.height)], viewport: [Math.round(vp.width), Math.round(vp.height)],
      zoom: root.querySelector("[data-sp=zoom]").textContent, dims: root.querySelector("[data-sp=dims]").textContent,
      barRows: new Set([...root.querySelectorAll(".sp-bar > .sp-group")].map((g) => Math.round(g.getBoundingClientRect().top))).size,
    };
  });
  console.log("fit", JSON.stringify(fit));
  check("no sideways page scroll", !fit.pageOverflow);
  check("the card is inside the window", fit.card[2] <= fit.vh && fit.card[0] <= fit.vw, fit.card);
  check("no control sticks out of the card", fit.over.length === 0, fit.over);
  check("13 tools, each tooltip names its key and its modifiers", fit.tools === 13 && fit.keyed === 13, `${fit.keyed}/${fit.tools}`);
  check("every button has a name", fit.untitled === 0, fit.untitled);
  check("one button height", fit.btnHeights.length === 1, fit.btnHeights);
  check("the whole page shows at the fit zoom", fit.page[0] <= fit.viewport[0] && fit.page[1] <= fit.viewport[1], { page: fit.page, viewport: fit.viewport, zoom: fit.zoom });

  // --- helpers in page pixels ---
  const stage = await page.evaluate(() => { const r = document.querySelector(".sp-ink").getBoundingClientRect(); return { x: r.left, y: r.top, s: r.width / 960 }; });
  const at = (x, y) => [stage.x + x * stage.s, stage.y + y * stage.s];
  const clear = () => page.evaluate(() => { const S = SketchPad._state; S.el.inkCtx.clearRect(0, 0, 960, 600); S.undo = []; S.redo = []; S.sel = null; });
  const key = (k) => page.keyboard.press(k);
  const ink = () => page.evaluate(() => {
    const d = SketchPad._state.el.inkCtx.getImageData(0, 0, 960, 600).data;
    let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1, n = 0;
    for (let y = 0; y < 600; y++) for (let x = 0; x < 960; x++) if (d[(y * 960 + x) * 4 + 3] > 8) { n++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    return n ? { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1, n } : { n: 0 };
  });
  const px = (x, y) => page.evaluate(([x, y]) => [...SketchPad._state.el.inkCtx.getImageData(x, y, 1, 1).data], [x, y]);
  const drag = async (from, to, mods = [], steps = 10) => {
    const a = at(...from), b = at(...to);
    for (const m of mods) await page.keyboard.down(m);
    await page.mouse.move(a[0], a[1]);
    await page.mouse.down();
    for (let i = 1; i <= steps; i++) await page.mouse.move(a[0] + ((b[0] - a[0]) * i) / steps, a[1] + ((b[1] - a[1]) * i) / steps);
    await page.mouse.up();
    for (const m of mods) await page.keyboard.up(m);
    await page.waitForTimeout(80);
  };
  const near = (a, b, tol) => Math.abs(a - b) <= tol;

  // --- keys pick tools ---
  const picked = [];
  for (const k of ["s", "p", "b", "h", "e", "l", "a", "r", "o", "g", "t", "f", "i"]) {
    await page.mouse.move(...at(480, 300));
    await key(k);
    picked.push(await page.evaluate(() => SketchPad._state.tool));
  }
  check("one letter picks each tool", new Set(picked).size === 13, picked);

  // --- rectangle: corner, Shift up-left, Alt centre ---
  await key("r");
  await page.evaluate(() => { const S = SketchPad._state; S.size = 2; S.el.size.value = "2"; });
  await clear();
  await drag([400, 300], [520, 360]);
  let b = await ink();
  check("a rectangle runs corner to corner (120x60)", near(b.x, 399, 2) && near(b.w, 122, 3) && near(b.h, 62, 3), b);
  await clear();
  await drag([400, 300], [280, 260], ["Shift"]);
  b = await ink();
  check("Shift up and left: a square that ends at the pointer", near(b.w, b.h, 2) && near(b.x + b.w, 401, 3) && near(b.w, 122, 3), b);
  await clear();
  await drag([400, 300], [460, 330], ["Alt"]);
  b = await ink();
  check("Alt: the press is the centre (120x60 about 400,300)", near(b.x + b.w / 2, 400, 2) && near(b.y + b.h / 2, 300, 2) && near(b.w, 122, 3), b);

  // --- ellipse corner to corner, Shift circle ---
  await key("o");
  await clear();
  await drag([300, 200], [420, 260]);
  b = await ink();
  check("an ellipse fills its drag box (120x60)", near(b.w, 122, 3) && near(b.h, 62, 3), b);
  await clear();
  await drag([300, 200], [420, 260], ["Shift"]);
  b = await ink();
  check("Shift: a circle", near(b.w, b.h, 2), b);

  // --- line Shift 45 ---
  await key("l");
  await clear();
  await drag([200, 300], [320, 314], ["Shift"]);
  b = await ink();
  check("Shift snaps a line flat", b.h <= 4, b);
  await clear();
  await drag([200, 300], [300, 390], ["Shift"]);
  b = await ink();
  check("and to 45 degrees", near(b.w, b.h, 3), b);

  // --- fill modes and bucket ---
  await key("r");
  await page.evaluate(() => { const S = SketchPad._state; S.ink = "#1f2430"; S.fill = "#22c55e"; });
  await page.click('.sp-mode[data-mode="both"]');
  await clear();
  await drag([100, 100], [200, 200]);
  const inside = await px(150, 150);
  check("Outline and fill: the inside is the fill colour", inside[1] > 150 && inside[0] < 80 && inside[3] === 255, inside);
  await page.click('.sp-mode[data-mode="outline"]');
  await clear();
  await drag([100, 100], [200, 200]);
  check("Outline only: the inside is empty", (await px(150, 150))[3] === 0);
  await key("f");
  await page.evaluate(() => { SketchPad._state.ink = "#ef4444"; });
  await page.mouse.click(...at(150, 150));
  await page.waitForTimeout(80);
  const filled = await px(150, 150);
  const outside = await px(300, 300);
  check("the bucket fills inside the box and not outside it", filled[0] > 200 && filled[3] === 255 && outside[3] === 0, { filled, outside });

  // --- picker ---
  await key("i");
  await page.mouse.click(...at(150, 150));
  await page.waitForTimeout(80);
  const got = await page.evaluate(() => ({ ink: SketchPad._state.ink, tool: SketchPad._state.tool }));
  check("the picker takes the colour and gives the last tool back", got.ink === "#ef4444" && got.tool === "fill", got);

  // --- undo and redo ---
  const before = (await ink()).n;
  await key("Control+z");
  const undone = (await ink()).n;
  await key("Control+y");
  const redone = (await ink()).n;
  check("Ctrl+Z takes the fill back, Ctrl+Y puts it back", undone < before && redone === before, { before, undone, redone });

  // --- Escape mid-shape ---
  await key("r");
  await clear();
  const a0 = at(500, 400), a1 = at(600, 480);
  await page.mouse.move(...a0);
  await page.mouse.down();
  await page.mouse.move(...a1, { steps: 5 });
  await key("Escape");
  await page.mouse.up();
  await page.waitForTimeout(80);
  const stillOpen = await page.evaluate(() => SketchPad.isOpen());
  check("Escape mid-shape draws nothing and keeps the pad open", (await ink()).n === 0 && stillOpen, { open: stillOpen });

  // --- text in place ---
  await key("t");
  await clear();
  await page.mouse.click(...at(600, 100));
  await page.waitForTimeout(150);
  const editor = await page.evaluate(() => document.activeElement?.classList.contains("sp-text-editor"));
  await page.keyboard.type("Hello");
  await key("Enter");
  await page.waitForTimeout(80);
  b = await ink();
  check("text is typed in place (no prompt) and lands on Enter", editor && prompted === 0 && b.n > 50 && near(b.x, 602, 4), { editor, prompted, b });

  // --- polygon ---
  await key("g");
  await clear();
  for (const p of [[100, 400], [220, 400], [160, 500]]) { await page.mouse.click(...at(...p)); await page.waitForTimeout(40); }
  await key("Enter");
  b = await ink();
  check("a polygon closes on Enter", b.n > 100 && near(b.w, 124, 4) && near(b.h, 104, 4), b);

  // --- select and move ---
  await key("s");
  await drag([90, 390], [235, 510]);
  await drag([160, 450], [460, 450]);
  await key("Escape");
  b = await ink();
  check("select, drag: the triangle moves 300 right", near(b.x, 398, 4), b);
  await key("Control+a");
  await key("Delete");
  check("Ctrl+A then Delete clears the page", (await ink()).n === 0);

  // --- size keys, zoom, status ---
  await page.evaluate(() => { const S = SketchPad._state; S.size = 4; S.el.size.value = "4"; });
  await key("]");
  await key("]");
  const size = await page.evaluate(() => SketchPad._state.size);
  check("] grows the size", size === 6, size);
  const z0 = await page.evaluate(() => document.querySelector("[data-sp=zoom]").textContent);
  await key("+");
  const z1 = await page.evaluate(() => document.querySelector("[data-sp=zoom]").textContent);
  await key("0");
  const z2 = await page.evaluate(() => document.querySelector("[data-sp=zoom]").textContent);
  check("+ zooms in and 0 fits again", z1 !== z0 && z2 === z0, [z0, z1, z2]);
  await page.mouse.move(...at(321, 123));
  await page.waitForTimeout(60);
  const pos = await page.evaluate(() => document.querySelector("[data-sp=pos]").textContent);
  check("the status line says where the pointer is", pos === "321, 123", pos);
  check("and the page size", fit.dims === "960 × 600 px", fit.dims);

  // --- highlighter is translucent ---
  await key("h");
  await clear();
  await page.evaluate(() => { SketchPad._state.ink = "#eab308"; });
  await drag([100, 300], [400, 300]);
  const hl = await px(250, 300);
  check("the highlighter is one see-through band", hl[3] > 60 && hl[3] < 160, hl);

  // --- brush frame time ---
  await key("b");
  await clear();
  const frames = await page.evaluate(() => {
    window.__f = []; window.__long = [];
    let last = performance.now();
    const tick = (t) => { window.__f.push(t - last); last = t; window.__raf = requestAnimationFrame(tick); };
    window.__raf = requestAnimationFrame(tick);
    try { window.__po = new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(Math.round(e.duration)); }); window.__po.observe({ type: "longtask" }); } catch {}
  });
  void frames;
  const s0 = at(100, 100);
  await page.mouse.move(...s0);
  await page.mouse.down();
  for (let i = 1; i <= 120; i++) await page.mouse.move(s0[0] + i * 5 * stage.s, s0[1] + Math.sin(i / 8) * 80 * stage.s);
  await page.mouse.up();
  const ft = await page.evaluate(() => {
    cancelAnimationFrame(window.__raf); window.__po?.disconnect();
    const f = window.__f.slice(1).sort((a, b) => a - b);
    const q = (p) => +(f[Math.min(f.length - 1, Math.floor(f.length * p))] || 0).toFixed(1);
    return { frames: f.length, p50: q(0.5), p95: q(0.95), max: +(f[f.length - 1] || 0).toFixed(1), long: window.__long };
  });
  console.log("brush frames", JSON.stringify(ft));
  check("a 120-move brush stroke: p95 under 34 ms, no long task", ft.p95 < 34 && ft.long.length === 0, ft);

  // --- download ---
  const dl = page.waitForEvent("download", { timeout: 15000 }).catch(() => null);
  await page.click("[data-sp=download]");
  const file = await dl;
  check("Download PNG saves a sketch-*.png", Boolean(file && /^sketch-.*\.png$/.test(file.suggestedFilename())), file && file.suggestedFilename());

  // --- close asks first ---
  if (!STANDALONE) {
    await page.click("[data-sp=close]");
    await page.waitForTimeout(300);
    const asked = await page.evaluate(() => Boolean(document.querySelector(".modal-overlay:not(.hidden)")) && SketchPad.isOpen());
    check("closing a drawing asks first", asked);
  }
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  console.log(`${pass}/${pass + fail}`);
  await browser.close();
})();
