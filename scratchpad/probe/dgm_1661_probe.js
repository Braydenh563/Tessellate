// dgm_1661_probe.js: measures the Diagram builder (INBOX 1661), read-only. Re-run it after each stage to compare.
//
//   bash scratchpad/ui-sweeps/serve.sh 8881 /dev/shm/dgm-m
//   BASE=http://127.0.0.1:8881 node scratchpad/probe/dgm_1661_probe.js [layout|tasks|all] > /dev/shm/dgm_1661.json
//
// layout: for 1024, 1280, 1440, 1920, 2560 and 390, light and dark (a fresh browser each, so the first open is cold):
//   toolbar rows and wrapped buttons, time to the pane and to the first picture (cold and warm), Tab stops from the top of the
//   builder to the first block, interactive targets under 44 px, the page's sideways overflow.
// tasks (1440, light): clicks to add a decision with two labelled branches (picture path and list path), relabel an edge,
//   delete an edge, restyle a block, plus how a connection is shown (list rows, picture).
// A click is a primary pointer press (a drag counts one); keys are counted apart as typed characters and special keys.
// Run the layout half in the background: it takes about a minute (Bash times out at 120 s).
process.env.BASE ||= "http://127.0.0.1:8881";
process.env.SCRATCH ||= "/dev/shm/dgm-probe-shots";
const { boot } = require("../ui-sweeps/lib.js");
const MODE = process.argv[2] || "all";
const SEED = "flowchart TD\n  A[Start] --> B{Ok?}\n  B -->|yes| C[Go]\n  B -->|no| D[Stop]\n";

async function openDoc(page, title, content) {
  return page.evaluate(async ([t, c]) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: "mmd" }) });
    const d = await r.json();
    switchTab("documents");
    const t0 = performance.now();
    const out = { pane: -1, picture: -1 };
    const poll = new Promise((done) => {
      const tick = () => {
        const now = performance.now() - t0;
        if (out.pane < 0 && document.querySelector(".dgm-pane")) out.pane = Math.round(now);
        const img = document.querySelector(".dgm-picture img");
        if (out.picture < 0 && img && img.complete && img.naturalWidth > 0) out.picture = Math.round(now);
        if ((out.pane >= 0 && out.picture >= 0) || now > 15000) return done();
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    openDocument(d.id);
    await poll;
    return out;
  }, [title, content]);
}

const measure = () => {
  const shown = (b) => b.getClientRects().length && getComputedStyle(b).visibility !== "hidden" && !b.closest(".action-menu");
  const sel = "button, [role=button], [role=treeitem], input, select, a, .dgm-handle";
  const dock = document.querySelector(".dgm-dock");
  const dockBtns = [...dock.querySelectorAll("button, [role=button], input, select")].filter(shown).map((b) => {
    const r = b.getBoundingClientRect();
    return { n: (b.getAttribute("aria-label") || b.title || b.textContent).trim().slice(0, 28), top: Math.round(r.top), cy: r.top + r.height / 2, w: Math.round(r.width), h: Math.round(r.height) };
  });
  const rows = [];
  for (const b of dockBtns.sort((a, c) => a.cy - c.cy)) {
    const row = rows.find((r) => Math.abs(r.cy - b.cy) <= 10);
    if (row) row.items.push(b); else rows.push({ cy: b.cy, items: [b] });
  }
  const wrapped = rows.slice(1).flatMap((r) => r.items.map((b) => b.n));
  const small = [...document.querySelectorAll(".dgm " + sel.split(", ").join(", .dgm "))].filter(shown).map((b) => {
    const r = b.getBoundingClientRect();
    return { n: ((b.getAttribute("aria-label") || b.title || b.textContent || b.className) + "").trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height) };
  });
  const under = small.filter((s) => s.w < 44 || s.h < 44);
  const dr = dock.getBoundingClientRect();
  return {
    distinctTops: new Set(dockBtns.map((b) => b.top)).size,
    rows: rows.length,
    wrapped,
    dockH: Math.round(dr.height),
    buttons: dockBtns.length,
    pageOverflowX: document.documentElement.scrollWidth - innerWidth,
    interactive: small.length,
    under44: under.length,
    under44Sample: [...new Set(under.map((s) => `${s.n} ${s.w}x${s.h}`))].slice(0, 6),
  };
};

async function tabStops(page) {
  await page.evaluate(() => {
    const s = document.createElement("button");
    s.id = "probe-sentinel";
    s.textContent = "s";
    document.querySelector(".dgm").before(s);
    s.focus();
  });
  let n = 0;
  const seq = [];
  for (; n < 60; n++) {
    await page.keyboard.press("Tab");
    const a = await page.evaluate(() => {
      const e = document.activeElement;
      return { block: !!e?.classList?.contains("dgm-block"), n: (e?.getAttribute("aria-label") || e?.title || e?.textContent || "").trim().slice(0, 24) };
    });
    seq.push(a.n);
    if (a.block) break;
  }
  await page.evaluate(() => document.getElementById("probe-sentinel")?.remove());
  return { stops: n >= 60 ? -1 : n + 1, first: seq.slice(0, 3) };
}

async function layoutRun(width, theme) {
  process.env.THEME = theme;
  const phone = width === 390;
  const { browser, page } = await boot({
    viewport: { width, height: phone ? 844 : 900 },
    ...(phone ? { isMobile: true, hasTouch: true, deviceScaleFactor: 2 } : {}),
  });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).slice(0, 80)));
  try {
    const cold = await openDoc(page, "L1", SEED);
    await page.waitForTimeout(1200);
    const out = { width, theme, cold, ...(await page.evaluate(measure)) };
    out.tab = await tabStops(page);
    await page.evaluate(() => switchTab("documents"));
    out.warm = await openDoc(page, "L2", SEED);
    await page.waitForTimeout(800);
    out.errors = errs;
    return out;
  } finally {
    await browser.close();
  }
}

// --- tasks ---------------------------------------------------------------------------------------------
const count = (page) => page.evaluate(() => ({ p: __n.p, k: __n.k, s: __n.s }));
async function counter(page) {
  await page.evaluate(() => {
    window.__n = { p: 0, k: 0, s: 0 };
    if (window.__nOn) return;
    window.__nOn = true;
    document.addEventListener("pointerdown", (e) => e.isPrimary && __n.p++, true);
    document.addEventListener("keydown", (e) => (e.key.length === 1 && !e.ctrlKey && !e.metaKey ? __n.k++ : ["Enter", "Escape", "Tab", "Delete"].includes(e.key) && __n.s++), true);
  });
}
const state = (page) => page.evaluate(() => ({ src: docText(), rename: !!document.querySelector(".dgm-rename"), editing: !!document.querySelector(".dgm-editing") }));
const box = (page, id) => page.evaluate((i) => { const r = document.querySelector(`.dgm-box[data-node="${i}"]`)?.getBoundingClientRect(); return r && { x: r.left, y: r.top, w: r.width, h: r.height }; }, id);
async function fresh(page, title, content) {
  await openDoc(page, title, content);
  await page.waitForTimeout(1200);
  await counter(page);
}
async function typeIn(page, text) {
  await page.keyboard.type(text);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(1000);
}
async function dragHandle(page, id, dx, dy) {
  const b = await box(page, id);
  await page.mouse.move(b.x + b.w / 2, b.y + b.h / 2);
  await page.waitForTimeout(500);
  const h = await page.evaluate(() => { const r = document.querySelector(".dgm-handle")?.getBoundingClientRect(); return r && [r.left + r.width / 2, r.top + r.height / 2]; });
  if (!h) return false;
  await page.mouse.move(h[0], h[1]);
  await page.mouse.down();
  await page.mouse.move(h[0] + dx / 2, h[1] + dy / 2, { steps: 5 });
  await page.mouse.move(h[0] + dx, h[1] + dy, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(1500);
  return true;
}
//: Where an arrow's midpoint lies on the picture: halfway between the two node boxes' facing sides (a straight run).
async function edgeMid(page, from, to) {
  const a = await box(page, from);
  const b = await box(page, to);
  if (!a || !b) return null;
  const ac = [a.x + a.w / 2, a.y + a.h / 2];
  const bc = [b.x + b.w / 2, b.y + b.h / 2];
  const vertical = Math.abs(bc[1] - ac[1]) >= Math.abs(bc[0] - ac[0]);
  return vertical ? [(ac[0] + bc[0]) / 2, (bc[1] > ac[1] ? (a.y + a.h + b.y) / 2 : (b.y + b.h + a.y) / 2)] : [(bc[0] > ac[0] ? (a.x + a.w + b.x) / 2 : (b.x + b.w + a.x) / 2), (ac[1] + bc[1]) / 2];
}
const labels = (src) => [...src.matchAll(/-->\|([^|]*)\|/g)].map((m) => m[1]);
const menuItem = (page, name) => page.locator(".action-menu:not(.hidden) .menu-item", { hasText: name }).first();

async function tasksRun() {
  process.env.THEME = "light";
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const out = {};
  try {
    // T1a: picture path. Tile, type, then pull a new connected block off the decision's handle twice.
    await fresh(page, "T1a", "");
    await page.click('.dgm-tile[aria-label^="Add a decision"]');
    await page.waitForTimeout(300);
    await typeIn(page, "Ok?");
    const prompts = [];
    for (const [dx, dy, word] of [[220, -200, "Yes"], [220, 200, "No"]]) {
      if (!(await dragHandle(page, "A", dx, dy))) { prompts.push("no handle"); continue; }
      for (let i = 0; i < 3; i++) {
        const s = await state(page);
        if (!s.rename && !s.editing) break;
        prompts.push(word + (i ? "(label)" : ""));
        await typeIn(page, i ? word : word);
        if (i === 0) break;
      }
    }
    let s = await state(page);
    // The branch words: a second prompt may not appear; label an unlabelled edge with a double click on the picture.
    let extra = 0;
    for (const to of ["B", "C"]) {
      if (labels(s.src).length >= 2) break;
      const missing = s.src.split("\n").find((l) => new RegExp(`A\\s*-->\\s*${to}$`).test(l.trim()));
      if (!missing) continue;
      const m = await edgeMid(page, "A", to);
      if (!m) continue;
      await page.mouse.dblclick(m[0], m[1]);
      await page.waitForTimeout(500);
      if ((await state(page)).rename) { await typeIn(page, to === "B" ? "Yes" : "No"); extra++; }
      s = await state(page);
    }
    out.addDecision_picture = { ...(await count(page)), prompts, extraEdgeLabelDblclicks: extra, labelsSet: labels(s.src), nodes: (s.src.match(/^\s+\w+[\[({]/gm) || []).length, src: s.src };

    // T1b: list path. Three tiles, then Connect to… + a row in its picker dialog, then the chip menu's Label, twice.
    await fresh(page, "T1b", "");
    await page.click('.dgm-tile[aria-label^="Add a decision"]'); await page.waitForTimeout(300); await typeIn(page, "Ok?");
    await page.click('.dgm-tile[aria-label^="Add a box"]'); await page.waitForTimeout(300); await typeIn(page, "Go");
    await page.click('.dgm-tile[aria-label^="Add a box"]'); await page.waitForTimeout(300); await typeIn(page, "Stop");
    const listTrace = [];
    for (const [target, word] of [["Go", "yes"], ["Stop", "no"]]) {
      await page.click('.dgm-block[data-key="n:A"] .dgm-connect');
      await page.waitForTimeout(500);
      //: Connect to… opens a modal list of blocks, not a pick on the list or the picture.
      await page.locator(`.rich-picker-row[title="${target}"]`).click();
      await page.waitForTimeout(700);
      listTrace.push((await state(page)).src.split("\n").length);
      //: A second branch off a decision asks for its words at once (a prompt); the first one is labelled through its chip.
      if (await page.locator(".prompt-card input").count()) { listTrace.push("auto prompt"); await typeIn(page, word); continue; }
      await page.locator(".dgm-join", { hasText: `Ok? to ${target}` }).first().click();
      await page.waitForTimeout(300);
      await menuItem(page, "Label").click();
      await page.waitForTimeout(500);
      await typeIn(page, word);
    }
    s = await state(page);
    out.addDecision_list = { ...(await count(page)), labelsSet: labels(s.src), src: s.src };

    // T2/T3/T4 on the seed.
    await fresh(page, "T2", SEED);
    const before = await page.evaluate(() => ({ chips: [...document.querySelectorAll(".dgm-join")].map((c) => c.textContent.trim()), chipH: Math.round(document.querySelector(".dgm-join").getBoundingClientRect().height), boxes: document.querySelectorAll(".dgm-box").length }));
    // How a connection is shown. One click on an arrow of the picture: does anything open or select?
    //: The straight Start to Ok? arrow: a branch's midpoint is diagonal and cannot be read off the boxes.
    const mid = await edgeMid(page, "A", "B");
    const c0 = await count(page);
    await page.mouse.click(mid[0], mid[1]);
    await page.waitForTimeout(500);
    const single = await page.evaluate(() => ({ menus: [...document.querySelectorAll(".action-menu:not(.hidden)")].length, pickedChips: document.querySelectorAll(".dgm-join[aria-pressed=true], .dgm-join.on").length, selected: document.querySelectorAll('.dgm-block[aria-selected="true"]').length }));
    out.connectionShown = { listRowsForThreeEdges: before.chips, chipHeightPx: before.chipH, pictureBoxes: before.boxes, singleClickOnPictureArrow: single, pictureEdgeActions: "double click relabels only (diagram-edges.js); no select, restyle or delete on the picture" };

    // T2 relabel an edge, on the picture: double click on the arrow, type, Enter.
    await counter(page);
    await page.mouse.dblclick(mid[0], mid[1]);
    await page.waitForTimeout(500);
    const opened = (await state(page)).rename;
    if (opened) await typeIn(page, "go on");
    out.relabelEdge_picture = { ...(await count(page)), opened, src: (await state(page)).src.split("\n").filter((l) => /-->/.test(l)).join(" / ") };
    // T2b in the list: chip, Label, type, Enter.
    await counter(page);
    await page.locator(".dgm-join", { hasText: "Ok? to Stop" }).first().click();
    await menuItem(page, "Label").click();
    await page.waitForTimeout(400);
    await typeIn(page, "else");
    out.relabelEdge_list = { ...(await count(page)), labels: labels((await state(page)).src) };
    // T3 delete an edge: chip, Remove connector.
    await counter(page);
    const e0 = (await state(page)).src.split("-->").length - 1;
    await page.locator(".dgm-join", { hasText: "Ok? to Stop" }).first().click();
    await menuItem(page, "Remove connector").click();
    await page.waitForTimeout(600);
    out.deleteEdge_list = { ...(await count(page)), edgesBeforeAfter: [e0, (await state(page)).src.split("-->").length - 1], onPicture: "no way to select an arrow on the picture" };
    // T4 restyle a block: swatch, pick Pill. Colour and fill have no control at all.
    await counter(page);
    await page.click('.dgm-block[data-key="n:C"] .dgm-swatch');
    await menuItem(page, "Pill").click();
    await page.waitForTimeout(600);
    out.restyleBlock_shape = { ...(await count(page)), src: (await state(page)).src.split("\n").find((l) => /C[\[(]/.test(l)) };
    out.restyleBlock_colour = await page.evaluate(() => ({ colourControls: document.querySelectorAll('.dgm [aria-label*="olour" i], .dgm [aria-label*="color" i], .dgm [title*="olour" i]').length }));
  } finally {
    await browser.close();
  }
  return out;
}

(async () => {
  const result = {};
  if (MODE !== "tasks") {
    result.layout = [];
    for (const width of [1024, 1280, 1440, 1920, 2560, 390]) {
      for (const theme of ["light", "dark"]) {
        try { result.layout.push(await layoutRun(width, theme)); } catch (e) { result.layout.push({ width, theme, error: String(e).slice(0, 160) }); }
      }
    }
  }
  if (MODE !== "layout") result.tasks = await tasksRun();
  console.log(JSON.stringify(result, null, 1));
})();
