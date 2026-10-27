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
      rail: (() => { const r = root.querySelector(".sp-rail"); return [r.scrollHeight, r.clientHeight, r.scrollWidth, r.clientWidth]; })(),
      top: [Math.round(document.getElementById("sketch-card").getBoundingClientRect().top), Math.round(root.querySelector(".sp-head").getBoundingClientRect().top)],
      vpShare: Math.round((vp.height / innerHeight) * 100),
      focus: document.activeElement?.dataset?.sp || document.activeElement?.className,
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
  // sketchfix-1026 1, 2, 7, 19
  check("every tool shows: the rail does not scroll (fix 1)", fit.rail[0] <= fit.rail[1] + 1 && fit.rail[2] <= fit.rail[3] + 1, fit.rail);
  check("the card and its head start inside the window (fix 2)", fit.top[0] >= 0 && fit.top[1] >= 0, fit.top);
  if (PHONE) check("a phone's page is at least half the screen (fix 7)", fit.vpShare >= 50, `${fit.vpShare}%`);
  check("the focus starts on the page, not a tool (fix 19)", fit.focus === "viewport", fit.focus);

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
  // Below 820 the palette, size and style are in the "Colour, size and
  // style" popover: open it for the press and close it after with Escape.
  const styleShut = () => page.evaluate(() => { const t = document.querySelector("[data-sp=style-toggle]"); return Boolean(t && t.getClientRects().length && t.getAttribute("aria-expanded") !== "true"); });
  const inStyle = async (fn) => {
    const folded = await styleShut();
    if (folded) await page.click("[data-sp=style-toggle]");
    await fn();
    if (folded) await key("Escape");
  };
  const pickMode = (m) => inStyle(() => page.click(`.sp-mode[data-mode="${m}"]`));

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
  await pickMode("both");
  await clear();
  await drag([100, 100], [200, 200]);
  const inside = await px(150, 150);
  check("Outline and fill: the inside is the fill colour", inside[1] > 150 && inside[0] < 80 && inside[3] === 255, inside);
  await pickMode("outline");
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

  // --- sketchfix-1026 ---
  // 3: with single-key shortcuts off, [ ] + = - 0 do nothing either.
  await page.mouse.move(...at(480, 300));
  const singles = await page.evaluate(() => { const S = SketchPad._state; const was = S.host.singleKeys; S.host.singleKeys = () => false; window.__sk = was; return [S.size, document.querySelector("[data-sp=zoom]").textContent]; });
  for (const k of ["]", "+", "="]) await key(k);
  const singlesAfter = await page.evaluate(() => { const S = SketchPad._state; S.host.singleKeys = window.__sk; return [S.size, document.querySelector("[data-sp=zoom]").textContent]; });
  check("single-key shortcuts off: ] and + do nothing (fix 3)", JSON.stringify(singles) === JSON.stringify(singlesAfter), [singles, singlesAfter]);

  // 9: one Tab stop per group, the arrows walk it.
  await page.evaluate(() => document.querySelector('.sp-tool[data-tool="brush"]').focus());
  await key("ArrowDown");
  const roved = await page.evaluate(() => [document.activeElement?.dataset.tool, [...document.querySelectorAll(".sp-tool")].filter((b) => b.tabIndex === 0).length]);
  check("the rail is one Tab stop and Down moves to the next tool (fix 9)", roved[0] === "highlighter" && roved[1] === 1, roved);

  // 10: the swatch that is on says so.
  await inStyle(() => page.click('.sp-swatch[data-colour="#3b82f6"]'));
  const pressed = await page.evaluate(() => [...document.querySelectorAll(".sp-swatch[aria-pressed=true]")].map((b) => b.dataset.colour));
  check("the active swatch is aria-pressed, the others not (fix 10)", pressed.length === 1 && pressed[0] === "#3b82f6", pressed);

  // 7: the popover opens and closes, and the press that closes it draws nothing.
  if (W < 820) {
    await page.click("[data-sp=style-toggle]");
    const pop = await page.evaluate(() => { const p = document.querySelector("[data-sp=style]"); const r = p.getBoundingClientRect(); return { open: p.classList.contains("open"), swatches: [...p.querySelectorAll(".sp-swatch")].filter((s) => s.getClientRects().length).length, inView: r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight, swatch: Math.round(p.querySelector(".sp-swatch").getBoundingClientRect().width) }; });
    check("Colour, size and style opens the palette, size and style in view (fix 7)", pop.open && pop.swatches === 12 && pop.inView && pop.swatch >= 44, pop);
    await key("r");
    await clear();
    await drag([100, 100], [300, 200]);
    const shut = await page.evaluate(() => !document.querySelector("[data-sp=style]").classList.contains("open"));
    check("a press on the page closes it and draws nothing", shut && (await ink()).n === 0, { shut });
  }

  // 13: Escape places the text being typed.
  await key("t");
  await clear();
  await page.mouse.click(...at(300, 300));
  await page.waitForTimeout(150);
  await page.keyboard.type("Kept");
  await key("Escape");
  await page.waitForTimeout(80);
  check("Escape while typing places the text (fix 13)", (await ink()).n > 30 && (await page.evaluate(() => SketchPad.isOpen())));

  // 18: the slider says text size for Text, and the box stays on the page.
  await key("t");
  const textSize = await page.evaluate(() => [document.querySelector("[data-sp=size-label]").textContent, document.querySelector("[data-sp=size-field]").title]);
  await page.evaluate(() => { const S = SketchPad._state; S.size = 24; S.el.size.value = "24"; });
  await page.mouse.click(...at(700, 500));
  await page.waitForTimeout(150);
  await page.keyboard.type("A long line that runs well past the edge of the page");
  const overhang = await page.evaluate(() => { const e = document.querySelector(".sp-text-editor"); const s = document.querySelector(".sp-stage").getBoundingClientRect(); const r = e.getBoundingClientRect(); return [Math.round(r.right - s.right), Math.round(r.bottom - s.bottom)]; });
  await key("Escape");
  await page.evaluate(() => { const S = SketchPad._state; S.size = 4; S.el.size.value = "4"; });
  check("with Text the slider is the text size (fix 18)", textSize[0] === "Text size" && /^Text size/.test(textSize[1]), textSize);
  check("the text box stays inside the page (fix 18)", overhang[0] <= 1 && overhang[1] <= 1, overhang);

  // 19: Ctrl+Shift+Z redoes, with the focus on the page or on a tool.
  await key("p");
  await clear();
  await drag([100, 450], [300, 520]);
  await key("Control+z");
  const redoA = await page.evaluate(() => SketchPad._state.redo.length);
  await key("Control+Shift+z");
  const redoB = await page.evaluate(() => [SketchPad._state.redo.length, SketchPad._state.undo.length]);
  check("Ctrl+Shift+Z redoes (fix 19)", redoA === 1 && redoB[0] === 0 && redoB[1] === 1, { redoA, redoB });

  // 16: the zoom button's name says the zoom and what a press does.
  const zoomName = await page.evaluate(() => document.querySelector("[data-sp=zoom]").getAttribute("aria-label"));
  check("the zoom button is named for what it does (fix 16)", /^Zoom \d+%, (fit the page|show at 100%)$/.test(zoomName), zoomName);

  // 17: the status row is as tall as its buttons.
  const status = await page.evaluate(() => { const s = document.querySelector(".sp-status").getBoundingClientRect().height; const b = Math.max(...[...document.querySelectorAll(".sp-status button")].map((x) => x.getBoundingClientRect().height)); return [Math.round(s), Math.round(b)]; });
  check("the status row holds its buttons (fix 17)", status[0] >= status[1], status);

  // 15: the More menu stays in the window and the arrows walk it.
  if (STANDALONE) {
    await page.click(".sp-menu-wrap > button");
    const menu = await page.evaluate(() => { const r = document.querySelector(".sp-menu").getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), innerWidth, document.activeElement.textContent]; });
    await key("ArrowDown");
    const moved = await page.evaluate(() => document.activeElement.textContent);
    await key("Escape");
    check("the menu is inside the window (fix 15)", menu[0] >= 0 && menu[1] <= menu[2], menu);
    check("Down moves to the next row", moved !== menu[3] && /Paper/.test(moved), moved);
  }

  if (!STANDALONE) {
    // 11: Save on a blank page saves nothing and says why.
    await clear();
    await page.evaluate(() => { SketchPad._state.dirty = false; });
    await page.evaluate(() => SketchPad._state.el.save && SketchPad._state.el.save.setAttribute("aria-disabled", "true"));
    let posted = 0;
    await page.route("**/media/upload*", (r) => { posted++; return r.continue(); });
    await page.click("[data-sp=save]", { force: true });
    await page.waitForTimeout(200);
    const blank = await page.evaluate(() => [document.querySelector("[data-sp=message]").textContent, document.querySelector("[data-sp=save]").getAttribute("aria-disabled"), SketchPad.isOpen()]);
    check("Save on a blank page saves nothing and says why (fix 11)", posted === 0 && blank[0] === "Draw something first." && blank[1] === "true" && blank[2], { posted, blank });
    await page.unroute("**/media/upload*");

    // 12: a failed save is an error, the page does not move, Save stays.
    await key("p");
    await drag([100, 100], [200, 160]);
    const enabled = await page.evaluate(() => document.querySelector("[data-sp=save]").getAttribute("aria-disabled"));
    await page.route("**/media/upload*", (r) => r.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "The server could not be reached; you may be offline." }) }));
    const vp0 = await page.evaluate(() => JSON.stringify(document.querySelector(".sp-viewport").getBoundingClientRect()));
    await page.click("[data-sp=save]");
    await page.waitForTimeout(600);
    const failed = await page.evaluate(() => { const m = document.querySelector("[data-sp=message]"); return { text: m.textContent, error: m.classList.contains("sp-error"), colour: getComputedStyle(m).color, want: (() => { const x = document.createElement("span"); x.style.color = "var(--error)"; m.append(x); const c = getComputedStyle(x).color; x.remove(); return c; })(), toast: [...document.querySelectorAll(".toast")].some((t) => /offline|reached|save/i.test(t.textContent)), saveOn: !document.querySelector("[data-sp=save]").disabled, open: SketchPad.isOpen() }; });
    const vp1 = await page.evaluate(() => JSON.stringify(document.querySelector(".sp-viewport").getBoundingClientRect()));
    await page.unroute("**/media/upload*");
    check("drawing turns Save on", enabled === "false", enabled);
    check("a failed save: error colour, a toast, Save still there (fix 12)", failed.error && failed.colour === failed.want && failed.toast && failed.saveOn && failed.open, failed);
    check("and the page does not move (fix 12)", vp0 === vp1, [vp0, vp1]);

    // 8 and 14: the close confirm names its action and keeps the keys.
    await key("p");
    await page.click("[data-sp=close]");
    await page.waitForTimeout(300);
    const confirmText = await page.evaluate(() => [...document.querySelectorAll(".confirm-overlay button")].map((b) => b.textContent.trim()));
    await key("b");
    await key("]");
    const behind = await page.evaluate(() => [SketchPad._state.tool, SketchPad._state.size]);
    check("the close confirm says Discard sketch (fix 14)", confirmText.includes("Discard sketch"), confirmText);
    check("keys under the confirm do not reach the pad (fix 8)", behind[0] === "pencil" && behind[1] === 4, behind);
    await key("Escape");
    await page.waitForTimeout(300);
    check("Escape on the confirm keeps the pad open", await page.evaluate(() => SketchPad.isOpen()));
  }

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
