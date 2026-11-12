//: L815 to L818: the headless part of the graph's hand checks, with numbers.
//: BASE=http://localhost:PORT node scratchpad/ui-sweeps/graph-handchecks.js
//: Saved views (a view restores its layout and positions after a reshuffle),
//: focus and global switching (node counts and time each way), reduced motion
//: (glide 0 ms, gcStill), the keyboard (arrow keys put a note under the ring;
//: the canvas shows a focus outline), and the hover frame (median full-draw
//: ms over 30 hovers). What stays for the owner: drag feel by hand, a real
//: embedding model for Close in meaning, a real GPU frame.
const {boot} = require(process.cwd() + "/scratchpad/ui-sweeps/lib.js");
(async () => {
  const {browser, page} = await boot();
  await page.evaluate(() => prefs.set("graph-layout", "force"));
  await page.click("#tab-btn-graph");
  await page.waitForFunction(() => window.gcTab && gcTab.nodes && gcTab.nodes.length && gcTab.alpha < 0.03, null, {timeout: 90000}).catch(() => {});
  await page.waitForTimeout(1500);
  const out = {notes: await page.evaluate(() => gcTab.nodes.length)};

  // Saved views: capture, reshuffle, apply; positions back within a pixel.
  out.views = await page.evaluate(async () => {
    const at = () => Object.fromEntries(gcTab.nodes.map((n) => [n.id, [n.x, n.y]]));
    const view = {name: "Sweep view", ...graphCaptureView()};
    prefs.set(GRAPH_VIEWS_KEY, JSON.stringify([...graphSavedViews().filter((v) => v.name !== view.name), view]));
    renderGraphViews();
    const listed = [...document.querySelectorAll("#graph-view-picker option")].some((o) => o.textContent.includes("Sweep view"));
    const before = at();
    gcReshuffle();
    await new Promise((r) => setTimeout(r, 2500));
    const moved = gcTab.nodes.filter((n) => Math.hypot(n.x - before[n.id][0], n.y - before[n.id][1]) > 5).length;
    graphApplyView(view);
    await new Promise((r) => setTimeout(r, 2500));
    const drift = gcTab.nodes.map((n) => (before[n.id] ? Math.hypot(n.x - before[n.id][0], n.y - before[n.id][1]) : 0));
    drift.sort((a, b) => a - b);
    return {listed, movedByReshuffle: moved, driftMedian: +drift[drift.length >> 1].toFixed(1), driftMax: +drift[drift.length - 1].toFixed(1), layout: gcTab.layoutKind};
  });

  // Focus and back.
  out.focus = await page.evaluate(async () => {
    const global = gcTab.nodes.length;
    const hub = [...gcTab.nodes].filter((n) => typeof n.id === "number").sort((a, b) => (b.degree || 0) - (a.degree || 0))[0];
    let t = performance.now();
    graphFocusModeId = hub.id;
    await renderGraph();
    const into = performance.now() - t;
    const local = gcTab.nodes.length;
    const chip = Boolean(document.getElementById("graph-focus-chip"));
    t = performance.now();
    document.getElementById("graph-focus-chip").click();
    await new Promise((r) => setTimeout(r, 50));
    await (window.graphDrawing || Promise.resolve());
    for (let i = 0; i < 100 && gcTab.nodes.length !== global; i++) await new Promise((r) => setTimeout(r, 50));
    return {global, local, chip, back: gcTab.nodes.length, intoMs: Math.round(into), backMs: Math.round(performance.now() - t)};
  });

  // Keyboard: Tab onto the canvas, an arrow puts the ring on a note.
  await page.focus("#graph-box");
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(300);
  out.keyboard = await page.evaluate(() => {
    const c = document.getElementById("graph-box");
    const cs = getComputedStyle(c);
    return {focused: document.activeElement === c, keyboardId: graphKeyboardId, outline: `${cs.outlineStyle} ${cs.outlineWidth}`};
  });

  // Hover frame: full draws while hovering hubs.
  out.hover = await page.evaluate(async () => {
    const s = gcTab;
    const t = s.transform;
    const box = s.canvas.getBoundingClientRect();
    const hubs = [...s.nodes].sort((a, b) => (b.degree || 0) - (a.degree || 0)).slice(0, 30);
    const times = [];
    for (const n of hubs) {
      const x = box.left + t.applyX(n.x), y = box.top + t.applyY(n.y);
      s.canvas.dispatchEvent(new PointerEvent("pointermove", {clientX: x, clientY: y, bubbles: true, pointerType: "mouse"}));
      const t0 = performance.now();
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      times.push(performance.now() - t0);
    }
    times.sort((a, b) => a - b);
    return {hovers: times.length, frameMedianMs: +times[times.length >> 1].toFixed(1), drawCostMs: +(s.drawCost || 0).toFixed(1)};
  });

  // Reduced motion.
  await browser.close();
  // Reduced motion, asked by the system before the page loads.
  const still = await boot({reducedMotion: "reduce"});
  await still.page.click("#tab-btn-graph");
  await still.page.waitForTimeout(2000);
  out.reduced = await still.page.evaluate(() => ({motion: document.documentElement.dataset.motion, still: gcStill(), glideMs: graphGlideMs(500)}));
  await still.browser.close();
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
