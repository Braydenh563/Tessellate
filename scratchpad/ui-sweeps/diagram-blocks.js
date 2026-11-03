// 1546 P2: a mouse run and a keyboard-only run build the same diagram in the block pane; the
// picture draws, no CSP error, no sideways scroll. The mouse run is drag (palette tile, a drop on
// a node's middle to join, a group's body to nest, a drop above a node to reorder) and a double
// click to relabel; the keyboard run is N, N, N, G, arrows, Enter, J, Alt+Right, Alt+Up.
//
//   bash scratchpad/ui-sweeps/serve.sh 8781 <scratch dir>
//   BASE=http://127.0.0.1:8781 THEME=dark node scratchpad/ui-sweeps/diagram-blocks.js [mouse|key|both] [width] [height]
//
// At 390 the blocks pane scrolls inside a short window, so the mouse run needs a height of about
// 1300 there (a drop target has to be on screen); the keyboard run does not.
const os = require("os");
process.env.BASE ||= "http://127.0.0.1:8781";
const SC = process.env.SCRATCH || os.tmpdir();
process.env.SCRATCH = SC;
const { boot } = require("./lib.js");
const MODE = process.argv[2] || "both";
const WIDTH = Number(process.argv[3] || 1440);

async function openNew(page, title) {
  await page.evaluate(async (t) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: t, content: "", file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
  }, title);
  await page.waitForSelector(".dgm-pane", { timeout: 15000 });
  await page.waitForTimeout(500);
}
const source = (page) => page.evaluate(() => docText());
const keys = (page) => page.evaluate(() => [...document.querySelectorAll(".dgm-block")].map((b) => b.dataset.key));
const press = async (page, k, n = 1) => { for (let i = 0; i < n; i++) { await page.keyboard.press(k); await page.waitForTimeout(90); } };

async function drag(page, from, to, opts = {}) {
  const a = await from.boundingBox();
  const b = await to.boundingBox();
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(opts.hold ?? 0);
  await page.mouse.move(a.x + a.width / 2 + 6, a.y + a.height / 2 + 6, { steps: 3 });
  await page.mouse.move(b.x + b.width * 0.5, b.y + b.height * (opts.fy ?? 0.5), { steps: 10 });
  await page.waitForTimeout(80);
  await page.mouse.up();
  await page.waitForTimeout(250);
  if (process.env.DEBUG) console.log("after drag", JSON.stringify(await page.evaluate(() => docText())), JSON.stringify(await page.evaluate(() => ({ y: scrollY, vis: [...document.querySelectorAll(".dgm-block > .dgm-card")].map((c) => { const b = c.getBoundingClientRect(); return [c.parentElement.dataset.key, Math.round(b.y), Math.round(b.height)]; }), pane: (() => { const b = document.querySelector(".dgm-pane").getBoundingClientRect(); return [Math.round(b.y), Math.round(b.height)]; })() }))));
}

async function mouseRun(page) {
  await openNew(page, "Mouse run");
  const tile = (shape) => page.locator(`.dgm-tile[data-shape="${shape}"]`);
  const block = (k) => page.locator(`.dgm-block[data-key="${k}"] > .dgm-card`);
  // place three: one dragged out of the palette, two pressed
  await drag(page, tile("rect"), page.locator(".dgm-pane"), { fy: 0.6 });
  await press(page, "Escape");
  await tile("rect").click(); await press(page, "Escape");
  await tile("rect").click(); await press(page, "Escape");
  await tile("group").click(); await press(page, "Escape");
  // join A to B: drop A on the middle of B
  await drag(page, block("n:A"), block("n:B"), { hold: 300, fy: 0.5 });
  // nest C into the group
  await drag(page, block("n:C"), block("g:G1"), { hold: 300, fy: 0.7 });
  // relabel B by double click
  await block("n:B").locator(".dgm-label").dblclick();
  await page.keyboard.type("Ready?");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(200);
  // reorder: drag B to above A
  await drag(page, block("n:B"), block("n:A"), { hold: 300, fy: 0.1 });
  await page.waitForTimeout(500);
  return source(page);
}

async function keyRun(page) {
  await openNew(page, "Keyboard run");
  await page.focus(".dgm-pane");
  await press(page, "n"); await press(page, "Escape");
  await press(page, "n"); await press(page, "Escape");
  await press(page, "n"); await press(page, "Escape");
  await press(page, "g"); await press(page, "Escape");
  // tree now: G1, A, B, C with G1 focused
  await press(page, "ArrowDown", 2);          // B
  await press(page, "Enter");
  await page.keyboard.type("Ready?"); await page.keyboard.press("Enter"); await page.waitForTimeout(150);
  await press(page, "ArrowUp");               // A
  await press(page, "j");
  await page.waitForTimeout(300);
  await page.keyboard.type("Ready");
  await page.waitForTimeout(200);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
  await press(page, "ArrowDown", 2);          // C
  await press(page, "Alt+ArrowRight");        // nest into G1
  // visible order: G1, C, A, B ; focus on C
  await press(page, "ArrowDown", 2);          // B
  await press(page, "Alt+ArrowUp");           // B before A
  await page.waitForTimeout(500);
  return source(page);
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: WIDTH, height: Number(process.argv[4] || 900) } });
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 160)));
  await page.evaluate(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push([e.sourceFile, e.lineNumber, e.violatedDirective])); });
  const out = {};
  if (MODE !== "key") out.mouse = await mouseRun(page);
  if (MODE !== "mouse") out.key = await keyRun(page);
  console.log(JSON.stringify(out, null, 1));
  if (out.mouse && out.key) console.log("SAME SOURCE:", out.mouse === out.key);
  const t0 = Date.now();
  const nat = await page.waitForFunction(() => document.querySelector(".dgm-picture img")?.naturalWidth > 0, null, { timeout: 5000 }).then(() => Date.now() - t0).catch(() => -1);
  console.log("picture naturalWidth>0 after (ms from the last change):", nat, "width", await page.evaluate(() => document.querySelector(".dgm-picture img")?.naturalWidth));
  console.log("csp violations:", JSON.stringify(await page.evaluate(() => window.__csp)), "console errors:", errors.length, errors.slice(0, 3));
  console.log("scroll:", JSON.stringify(await page.evaluate(() => ({ doc: [document.documentElement.scrollWidth, document.documentElement.clientWidth], dgm: [document.querySelector(".dgm")?.scrollWidth, document.querySelector(".dgm")?.clientWidth] }))));
  await page.screenshot({ path: SC + `/p2-${MODE}-${WIDTH}.png` });
  await browser.close();
})();
