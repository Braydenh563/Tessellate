// 1546 P3 adds a `suggest` mode: the eight templates (blocks and joins counted after each), a
// checklist note and a document's headings through From my notes, Describe it (dimmed with its
// reason with no model; a mocked reply with one on), and the ghosts (Tab takes, Enter adds, one undo
// step, Escape drops). Light or dark by THEME, 1440 or 390 by the width argument.
//
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

const counts = (page) => page.evaluate(() => ({
  nodes: document.querySelectorAll('.dgm-block[data-key^="n:"]').length,
  groups: document.querySelectorAll('.dgm-block[data-key^="g:"]').length,
  joins: document.querySelectorAll(".dgm-join").length,
}));
const menuItem = (page, name) => page.locator(".action-menu:not(.hidden) .menu-item", { hasText: name });
async function suggestMenu(page, name) {
  await page.click(".dgm-suggest");
  await menuItem(page, name).first().click();
}

async function suggestRun(page) {
  const out = { templates: {}, paths: {}, quiet: {} };
  const templates = JSON.parse(require("fs").readFileSync(require("path").join(__dirname, "../../frontend/board-library/diagram-templates.json"), "utf8")).templates;
  for (const t of templates) {
    await openNew(page, "Template " + t.id);
    out.quiet.suggest ||= await page.evaluate(() => { const b = document.querySelector(".dgm-suggest"); const c = getComputedStyle(b); const r = b.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), border: c.borderTopColor, bg: c.backgroundColor, word: getComputedStyle(b.querySelector(".ph-text") || b).display }; });
    await page.click(".dgm-empty button");
    await page.waitForSelector(".dgm-template-dialog[open]");
    await page.click(`.doc-template-choice[data-template="${t.id}"]`);
    await page.waitForTimeout(700);
    if (t.id === "decision") out.quiet.dialog = await page.evaluate(() => { const d = document.querySelector(".dgm-template-dialog"); return { rows: d.querySelectorAll(".doc-template-choice").length, previewImg: Boolean(d.querySelector(".dgm-template-figure img")), filled: d.querySelectorAll("button.accent").length, width: Math.round(d.getBoundingClientRect().width), fits: d.scrollWidth <= d.clientWidth }; });
    await page.click(".dgm-template-dialog button.accent");
    await page.waitForTimeout(500);
    const want = await page.evaluate((src) => { const m = diagramModel.parse(src); return { nodes: m.nodes.length, groups: m.subgraphs.length, joins: m.edges.length }; }, t.source);
    const got = await counts(page);
    out.templates[t.id] = { want, got, same: JSON.stringify(want) === JSON.stringify(got) && (await source(page)) === t.source };
  }
  // From my notes: a five-item checklist is five blocks and four joins
  await page.evaluate(async () => {
    await api("/entries", { method: "POST", body: JSON.stringify({ content: "- [ ] Draft the brief\n- [ ] Review with Sam\n- [ ] Fix comments\n- [ ] Send to client\n- [ ] Archive the file" }) });
    await api("/documents", { method: "POST", body: JSON.stringify({ title: "Garden plan", content: "# Garden plan\n\n## Soil\n- test ph\n- add compost\n\n## Seeds\n- tomatoes\n\n## Water\n- weekly\n" }) });
    await loadEntries();
  });
  await openNew(page, "From notes");
  await suggestMenu(page, "From my notes");
  await page.waitForSelector(".entry-pick-card");
  await page.fill(".entry-pick-card input[type=search]", "Draft the brief");
  await page.waitForTimeout(400);
  await page.locator(".entry-pick-row").first().click();
  await page.waitForFunction(() => document.querySelectorAll('.dgm-block[data-key^="n:"]').length >= 5, null, { timeout: 8000 }).catch(() => {});
  out.paths.checklist = { ...(await counts(page)), want: { nodes: 5, groups: 0, joins: 4 } };
  // a document's headings are a mind map: the source is one and the picture draws
  await openNew(page, "From headings");
  await suggestMenu(page, "From my notes");
  await page.waitForSelector(".entry-pick-card");
  await page.locator('[data-pick-kind="document"]').click();
  await page.fill(".entry-pick-card input[type=search]", "Garden plan");
  await page.waitForTimeout(500);
  await page.locator(".entry-pick-row").first().click();
  await page.waitForFunction(() => /^mindmap/.test(docText()), null, { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(800);
  out.paths.headings = await page.evaluate(() => ({ source: docText().split("\n").slice(0, 4), picture: document.querySelector(".dgm-picture img")?.naturalWidth || 0, note: document.querySelector(".dgm-hint:not(.hidden)")?.textContent.slice(0, 80) }));
  // the ghosts: a template on a diagram with blocks arrives as suggestions
  await openNew(page, "Ghosts");
  await page.click(".dgm-empty button");
  await page.waitForSelector(".dgm-template-dialog[open]");
  await page.click(".dgm-template-dialog button.accent");
  await page.waitForTimeout(400);
  const before = await counts(page);
  await suggestMenu(page, "Templates");
  await page.waitForSelector(".dgm-template-dialog[open]");
  await page.click('.doc-template-choice[data-template="decision"]');
  await page.click(".dgm-template-dialog button.accent");
  await page.waitForSelector(".dgm-ghost");
  const ghost = await page.evaluate(() => { const g = document.querySelector(".dgm-ghost"); const c = getComputedStyle(g); return { ghosts: document.querySelectorAll(".dgm-ghost").length, focused: document.activeElement?.className, border: c.borderTopStyle, opacity: c.opacity, transition: c.transitionDuration, noSideScroll: document.querySelector(".dgm-pane").scrollWidth <= document.querySelector(".dgm-pane").clientWidth }; });
  const src0 = await source(page);
  await page.keyboard.press("Tab"); await page.keyboard.press("Tab");
  const taken = await page.evaluate(() => document.querySelectorAll('.dgm-ghost[aria-pressed="true"]').length);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(500);
  const after = await counts(page);
  const ids = await page.evaluate(() => [...document.querySelectorAll('.dgm-block[data-key^="n:"]')].map((b) => b.dataset.key.slice(2)).join(""));
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(500);
  const undone = await counts(page);
  out.paths.ghosts = { before, ghost, taken, after, ids, undone, sourceBackAfterUndo: (await source(page)) === src0 };
  await suggestMenu(page, "Templates");
  await page.waitForSelector(".dgm-template-dialog[open]");
  await page.click(".dgm-template-dialog button.accent");
  await page.waitForSelector(".dgm-ghost");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  out.paths.escape = { ghosts: await page.evaluate(() => document.querySelectorAll(".dgm-ghost").length), counts: await counts(page) };
  // Describe it: dimmed with its reason with no model; with one (a mocked reply) it drafts
  await page.click(".dgm-suggest");
  await page.waitForTimeout(400);
  out.paths.describeOff = await page.evaluate(() => { const i = [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")].find((x) => /Describe/.test(x.textContent)); return { disabled: i?.getAttribute("aria-disabled"), cls: i?.className, title: i?.title.slice(0, 60), opacity: i ? getComputedStyle(i).opacity : null }; });
  await menuItem(page, "Describe it").click({ force: true });
  await page.waitForTimeout(300);
  out.paths.describeOff.reason = await page.evaluate(() => document.querySelector(".dgm-hint:not(.hidden)")?.textContent.slice(0, 90) || null);
  await openNew(page, "Describe");
  await page.route("**/drafts/compose", (route) => route.fulfill({ json: { draft: "", diagram: 'flowchart TD\n  a["Plan"] --> b["Do"]\n', diagram_error: "", said: "Drafted by the model.", ollama_running: true } }));
  await page.evaluate(() => { modelStatus = { ...(modelStatus || {}), ollama_running: true, model_ready: true }; });
  await suggestMenu(page, "Describe it");
  await page.waitForSelector(".prompt-card input");
  await page.fill(".prompt-card input", "plan then do");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(800);
  out.paths.describeOn = await counts(page);
  await page.unroute("**/drafts/compose");
  await page.route("**/drafts/compose", (route) => route.fulfill({ json: { draft: "```mermaid\nflowchart TD\n  a[", diagram: "", diagram_error: "The model's diagram was cut off before the fence closed. Try again, or describe fewer steps.", ollama_running: true } }));
  await openNew(page, "Describe broken");
  await page.evaluate(() => { modelStatus = { ...(modelStatus || {}), ollama_running: true, model_ready: true }; });
  await suggestMenu(page, "Describe it");
  await page.waitForSelector(".prompt-card input");
  await page.fill(".prompt-card input", "anything");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(800);
  out.paths.describeBroken = { ...(await counts(page)), reason: await page.evaluate(() => document.querySelector(".dgm-hint:not(.hidden)")?.textContent.slice(0, 70) || null), sourceKept: (await source(page)).trim() === "" };
  return out;
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
  if (MODE === "suggest") out.suggest = await suggestRun(page);
  if (MODE !== "key" && MODE !== "suggest") out.mouse = await mouseRun(page);
  if (MODE !== "mouse" && MODE !== "suggest") out.key = await keyRun(page);
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
