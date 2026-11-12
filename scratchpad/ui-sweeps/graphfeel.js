// **The graph's feel** (INBOX 775, 792, 796 and their round 2), one sweep, MODE picks the check:
//   feel (default): fill of the fitted map against the canvas and its free part (dock, legend,
//     minimap, zoom strip cleared), overlapping dots at rest, visible layout travel after the
//     reveal. Seeds N notes (default 34) in seven categories with about N links. W, H, DPR, RM=1
//     (reduced motion), SERIES=1 (samples to stderr).
//   settle: travel per 100 ms for 7 s after opening Graph (ROWS=1 prints them); run it against
//     origin/main for "how it used to move".
//   viewchange: per layout change, Refresh and a return to the tab: samples with the canvas
//     hidden or empty, the largest single-sample move, travel.
//   menus: every pair of the head's '?', settings and ⋯ (INBOX 796): none may stack open.
//   panels: Options opening and closing refits a fitted map, not a zoomed one (INBOX 792).
//   resize: the map stays framed as its card changes width (INBOX 613; was graphfit.js).
//   BASE=http://127.0.0.1:PORT MODE=feel node scratchpad/ui-sweeps/graphfeel.js
const { boot } = require("./lib.js");
const modes = {};

modes["feel"] = async () => {
// Graph feel measure (INBOX 775). N=notes, W,H viewport. Seeds once if fewer notes exist.
const N = Number(process.env.N || 34), W = Number(process.env.W || 1440), H = Number(process.env.H || 900);

  const { browser, page } = await boot({ viewport: { width: W, height: H }, scale: Number(process.env.DPR || 1), ...(process.env.RM ? { reducedMotion: "reduce" } : {}) });
  const seeded = await page.evaluate(async (N) => {
    const r = await (await api("/entries?limit=1000")).json();
    let rows = r.items || r;
    if (rows.length >= N) return rows.length;
    const topics = ["garden soil compost", "marathon running pace", "python async code", "kyoto travel temple", "tomato soup recipe", "budget tax insurance", "book reading novel"];
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const ids = [];
    for (let i = rows.length; i < N; i++) {
      const t = topics[i % topics.length];
      const res = await api("/entries", { method: "POST", body: JSON.stringify({ content: `Note ${i} on ${t} with detail ${i * 3}`, tags: [t.split(" ")[0]], category: ["Garden","Health","Work","Travel","Cooking","Money","Reading"][i % topics.length] }) });
      ids.push((await res.json()).id);
    }
    // ~N links on the first 2/3 of the notes (hubs and leaves), the rest unlinked, as a real notebook is.
    const core = ids.slice(0, Math.ceil(ids.length * 0.65));
    // A pair is linked once either way round: the API answers a repeat with a 400.
    const pairs = new Set();
    let made = 0, guard = 0;
    while (made < ids.length && guard++ < ids.length * 6) {
      const a = core[Math.floor(Math.pow(rnd(), 2) * core.length)], b = core[Math.floor(rnd() * core.length)];
      const pair = a < b ? `${a}:${b}` : `${b}:${a}`;
      if (a === b || pairs.has(pair)) continue;
      pairs.add(pair);
      const res = await api(`/entries/${a}/links`, { method: "POST", body: JSON.stringify({ target_id: b, reason: rnd() < 0.5 ? "Same subject" : "" }) }).catch(() => null);
      if (res && res.ok) made++;
    }
    return N;
  }, N);
  await page.evaluate(() => switchTab("graph"));
  // Sample every 100 ms for 4 s: visibility and node motion on screen.
  const samples = [];
  for (let i = 0; i < 40; i++) {
    samples.push(await page.evaluate(() => {
      const s = gcTab; if (!s || !s.nodes || !s.transform) return null;
      const t = s.transform;
      return { op: getComputedStyle(s.canvas).opacity, a: s.alpha, k: t.k, p: s.nodes.map((n) => [t.applyX(n.x), t.applyY(n.y)]), w: s.nodes.map((n) => [n.x, n.y]) };
    }));
    await page.waitForTimeout(100);
  }
  const series = []; let moving = 0, visibleMoving = 0, firstVisible = -1, travel = 0, lastMove = 0, wtravel = 0, wframes = 0;
  for (let i = 1; i < samples.length; i++) {
    const a = samples[i - 1], b = samples[i];
    if (!a || !b || a.p.length !== b.p.length || !b.p.length) continue;
    let d = 0; for (let j = 0; j < b.p.length; j++) d += Math.hypot(b.p[j][0] - a.p[j][0], b.p[j][1] - a.p[j][1]);
    d /= b.p.length;
    let dw = 0; for (let j = 0; j < b.w.length; j++) dw += Math.hypot(b.w[j][0] - a.w[j][0], b.w[j][1] - a.w[j][1]);
    dw = (dw / b.w.length) * b.k;
    if (Number(b.op) > 0.5 && dw > 0.5) { wtravel += dw; wframes++; }
    if (d > 0.5) { moving++; if (Number(b.op) > 0.5) { visibleMoving++; travel += d; if (d > 2) lastMove = i * 100; } }
    if (firstVisible < 0 && Number(b.op) > 0.5) firstVisible = i * 100;
    if (process.env.SERIES) series.push(`${i * 100}:${Number(b.op).toFixed(1)}/k${b.k.toFixed(2)}/a${(b.a || 0).toFixed(3)}/d${d.toFixed(0)}/w${dw.toFixed(0)}`);
  }
  await page.waitForTimeout(Number(process.env.SETTLE || 6000));
  const measure = () => page.evaluate(() => {
    const s = gcTab, t = s.transform, c = s.canvas.getBoundingClientRect();
    const notes = s.nodes;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const n of notes) { const x = t.applyX(n.x), y = t.applyY(n.y), r = n.r * t.k;
      x0 = Math.min(x0, x - r); x1 = Math.max(x1, x + r); y0 = Math.min(y0, y - r); y1 = Math.max(y1, y + r); }
    const rect = (id) => { const e = document.getElementById(id); if (!e || e.offsetParent === null) return null; const b = e.getBoundingClientRect(); return { l: Math.round(b.left - c.left), t: Math.round(b.top - c.top), w: Math.round(b.width), h: Math.round(b.height) }; };
    let ov = 0, ovRing = 0, minGap = Infinity;
    for (let i = 0; i < notes.length; i++) for (let j = i + 1; j < notes.length; j++) {
      const a = notes[i], b = notes[j], d = Math.hypot(a.x - b.x, a.y - b.y);
      if (d < a.r + b.r) ov++;
      const ra = a.r + Math.max(1, Math.round(a.r * 0.18)), rb = b.r + Math.max(1, Math.round(b.r * 0.18));
      if (d < ra + rb) ovRing++;
      minGap = Math.min(minGap, d - a.r - b.r);
    }
    const bw = x1 - x0, bh = y1 - y0;
    // The free rect, measured here on its own: each overlay counted against the edge it costs least to clear.
    const ins = { top: 0, right: 0, bottom: 0, left: 0 };
    for (const sel of ["#graph-card > .graph-overlay > .dock", "#graph-card .graph-legend-row", "#graph-minimap", "#graph-zoom"]) {
      const e = document.querySelector(sel); if (!e || e.offsetParent === null) continue; const b = e.getBoundingClientRect();
      if (!b.width || b.right <= c.left || b.left >= c.right || b.bottom <= c.top || b.top >= c.bottom) continue;
      const d = { top: b.bottom - c.top, bottom: c.bottom - b.top, left: b.right - c.left, right: c.right - b.left };
      const side = Object.keys(d).sort((p, q) => d[p] / (p === "top" || p === "bottom" ? c.height : c.width) - d[q] / (q === "top" || q === "bottom" ? c.height : c.width))[0];
      ins[side] = Math.max(ins[side], d[side]);
    }
    const fw = c.width - ins.left - ins.right, fh = c.height - ins.top - ins.bottom;
    const freeFill = +Math.max(bw / fw, bh / fh).toFixed(3);
    const under = notes.filter((n) => { const x = t.applyX(n.x), y = t.applyY(n.y); return x < ins.left || x > c.width - ins.right || y < ins.top || y > c.height - ins.bottom; }).length;
    return { k: +t.k.toFixed(3), canvas: [Math.round(c.width), Math.round(c.height)], dims: [s.dims.w, s.dims.h], bbox: [Math.round(x0), Math.round(y0), Math.round(bw), Math.round(bh)],
      fillW: +(bw / c.width).toFixed(3), fillH: +(bh / c.height).toFixed(3), fill: +Math.max(bw / c.width, bh / c.height).toFixed(3), freeFill, free: [Math.round(fw), Math.round(fh)], centresUnderOverlays: under,
      minimap: rect("graph-minimap"), zoom: rect("graph-zoom"), overlaps: ov, overlapsRing: ovRing, minGap: +minGap.toFixed(1), alpha: s.alpha, n: notes.length,
      rmax: Math.max(...notes.map((n) => n.r)) };
  });
  const first = await measure();
  await page.evaluate(() => document.getElementById("graph-zoom-fit").click());
  await page.waitForTimeout(1500);
  const fit = await measure();
  if (process.env.SERIES) console.error(series.join(' '));
  console.log(JSON.stringify({ N: seeded, W, H, firstVisibleMs: firstVisible, motionSamples: moving, visibleMotionSamples: visibleMoving, visibleTravelPx: Math.round(travel), layoutTravelPx: Math.round(wtravel), layoutMovingSamples: wframes, bigMoveUntilMs: lastMove, first, fit }));
  await browser.close();
};

modes["settle"] = async () => {
// Settle profile: mean node travel on screen and in the layout per 100 ms for 7 s after switching to Graph.

  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { prefs.set("graph-layout", "force"); prefs.set("graph-colour", "category"); });
  await page.evaluate(() => switchTab("graph"));
  const rows = [];
  let prev = null;
  for (let i = 0; i < 70; i++) {
    const s = await page.evaluate(() => { const s = gcTab; if (!s?.nodes?.length || !s.transform) return null; const t = s.transform; return { op: +getComputedStyle(s.canvas).opacity, a: s.alpha, k: t.k, w: s.nodes.map((n) => [n.x, n.y]), p: s.nodes.map((n) => [t.applyX(n.x), t.applyY(n.y)]) }; });
    if (s && prev && s.w.length === prev.w.length) {
      let dw = 0, dp = 0; for (let j = 0; j < s.w.length; j++) { dw += Math.hypot(s.w[j][0] - prev.w[j][0], s.w[j][1] - prev.w[j][1]); dp += Math.hypot(s.p[j][0] - prev.p[j][0], s.p[j][1] - prev.p[j][1]); }
      rows.push([i * 100, s.op > 0.5 ? 1 : 0, +(s.a || 0).toFixed(3), +s.k.toFixed(2), Math.round(dw / s.w.length * s.k), Math.round(dp / s.w.length)]);
    }
    prev = s;
    await page.waitForTimeout(100);
  }
  const vis = rows.filter((r) => r[1]);
  const lay = vis.reduce((a, r) => a + r[4], 0), scr = vis.reduce((a, r) => a + r[5], 0);
  const moving = vis.filter((r) => r[4] > 1);
  console.log(JSON.stringify({ layoutTravelPx: lay, screenTravelPx: scr, layoutMovingFrom: moving[0]?.[0], layoutMovingUntil: moving[moving.length - 1]?.[0], kFirstVisible: vis[0]?.[3], kLast: rows[rows.length - 1]?.[3] }));
  if (process.env.ROWS) console.log(rows.map((r) => r.join("/")).join(" "));
  await browser.close();
};

modes["viewchange"] = async () => {
// Round 2: changing view animates. Per action: samples (50 ms, 2.5 s) with the canvas hidden or empty,
// the largest single-sample move (a jump), and the samples that moved (travel spread over time).

  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { prefs.set("graph-layout", "force"); prefs.set("graph-colour", "category"); });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(7000);
  const snap = () => page.evaluate(() => { const s = gcTab, t = s.transform; return { op: +getComputedStyle(s.canvas).opacity, m: Object.fromEntries((s.nodes || []).filter((n) => !n.isGroup).map((n) => [n.id, [t.applyX(n.x), t.applyY(n.y)]])) }; });
  const setLayout = (l) => page.evaluate((l) => { const a = document.getElementById("graph-layout"); a.value = l; a.dispatchEvent(new Event("change", { bubbles: true })); }, l);
  const actions = [
    ["tree", () => setLayout("tree")], ["force from tree", () => setLayout("force")],
    ["radial", () => setLayout("radial")], ["arc", () => setLayout("arc")], ["force from arc", () => setLayout("force")],
    ["refresh", () => page.evaluate(() => document.getElementById("graph-refresh").click())],
    ["revisit", async () => { await page.evaluate(() => switchTab("notes")); await page.waitForTimeout(500); await page.evaluate(() => switchTab("graph")); }],
  ];
  const out = {};
  for (const [name, act] of actions) {
    let prev = await snap();
    await act();
    let hidden = 0, maxJump = 0, movingSamples = 0, travel = 0;
    for (let i = 0; i < 50; i++) {
      await page.waitForTimeout(50);
      const cur = await snap();
      const ids = Object.keys(cur.m);
      if (cur.op < 0.5 || !ids.length) hidden++;
      let d = 0, c = 0; for (const id of ids) { const p = prev.m[id]; if (p) { d += Math.hypot(cur.m[id][0] - p[0], cur.m[id][1] - p[1]); c++; } }
      if (c) { d /= c; maxJump = Math.max(maxJump, d); if (d > 2) { movingSamples++; travel += d; } }
      prev = cur;
    }
    out[name] = { hidden, maxJumpPx: Math.round(maxJump), movingSamples, travelPx: Math.round(travel) };
    await page.waitForTimeout(3000);
  }
  console.log(JSON.stringify(out));
  await browser.close();
};

modes["menus"] = async () => {
// INBOX 796: the Graph head's '?', gear and ⋯ close each other; Esc and an outside click close each.

  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(3000);
  const st = () => page.evaluate(() => ({
    help: !document.getElementById("graph-help-panel").classList.contains("hidden"),
    opts: !document.getElementById("graph-options").classList.contains("hidden"),
    more: document.getElementById("graph-more-menu").open,
  }));
  const click = async (sel) => { await page.click(sel); await page.waitForTimeout(300); return st(); };
  const out = {};
  out.help = await click("#graph-help-toggle");
  out.helpThenOpts = await click("#graph-options-toggle");
  out.optsThenMore = await click("#graph-more-menu > summary");
  out.moreThenHelp = await click("#graph-help-toggle");
  out.helpThenMore = await click("#graph-more-menu > summary");
  out.moreThenOpts = await click("#graph-options-toggle");
  out.optsThenHelp = await click("#graph-help-toggle");
  await page.keyboard.press("Escape"); await page.waitForTimeout(300); out.escHelp = await st();
  out.opts2 = await click("#graph-options-toggle");
  await page.keyboard.press("Escape"); await page.waitForTimeout(300); out.escOpts = await st();
  out.more2 = await click("#graph-more-menu > summary");
  await page.mouse.click(700, 500); await page.waitForTimeout(300); out.outsideMore = await st();
  const bad = Object.entries(out).filter(([, v]) => [v.help, v.opts, v.more].filter(Boolean).length > 1).map(([k]) => k);
  console.log(JSON.stringify({ bad, out }));
  await browser.close();
};

modes["panels"] = async () => {
// INBOX 792: a fitted map refits when a panel opens or closes; a zoomed one does not.

  const W = Number(process.env.W || 1440), H = Number(process.env.H || 900);
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(6000);
  const state = () => page.evaluate(() => {
    const s = gcTab, t = s.transform, c = s.canvas.getBoundingClientRect();
    const o = document.getElementById("graph-options"); const ob = o.getClientRects().length ? o.getBoundingClientRect() : null;
    let under = 0, maxX = -Infinity;
    for (const n of s.nodes) { const x = c.left + t.applyX(n.x), y = c.top + t.applyY(n.y); maxX = Math.max(maxX, x + n.r * t.k); if (ob && x > ob.left && x < ob.right && y > ob.top && y < ob.bottom) under++; }
    return { k: +t.k.toFixed(3), open: !!ob, panelLeft: ob ? Math.round(ob.left) : null, dotsRight: Math.round(maxX), under };
  });
  const out = { start: await state() };
  await page.evaluate(() => document.getElementById("graph-options-toggle").click());
  await page.waitForTimeout(1200); out.opened = await state();
  await page.evaluate(() => document.getElementById("graph-options-toggle").click());
  await page.waitForTimeout(1200); out.closed = await state();
  await page.evaluate(() => document.getElementById("graph-zoom-in").click());
  await page.waitForTimeout(600); out.zoomed = await state();
  await page.evaluate(() => document.getElementById("graph-options-toggle").click());
  await page.waitForTimeout(1200); out.zoomedOpened = await state();
  console.log(JSON.stringify(out));
  await browser.close();
};

modes["resize"] = async () => {
// **The graph stays framed when its card changes size** (INBOX 613). Pass: offX near 0 at every step (the dots' middle; since 2026-10-10 a fit centres the drawing, names included, `gcBalanceFit`, so the names' overhang leaves offX within about 20; graphfitmargins.js measures the drawing itself); base -200 after the card widened back.

  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async () => {
    for (let i = 0; i < 12; i++) await api("/entries", { method: "POST", body: JSON.stringify({ content: `fit note ${i} about topic ${i % 3}` }) });
  });
  await page.evaluate(() => switchTab("graph"));
  await page.waitForTimeout(5000);
  const centre = () => page.evaluate(() => {
    const s = gcTab, t = s.transform, xs = s.nodes.map((n) => t.applyX(n.x)), ys = s.nodes.map((n) => t.applyY(n.y));
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    return { offX: Math.round(cx - s.dims.w / 2), offY: Math.round(cy - s.dims.h / 2), w: s.dims.w };
  });
  const a = await centre();
  await page.evaluate(() => { const box = document.getElementById(gcTab.boxId); box.style.width = `${box.clientWidth - 400}px`; });
  await page.waitForTimeout(1500);
  const b = await centre();
  await page.evaluate(() => { const box = document.getElementById(gcTab.boxId); box.style.width = ""; });
  await page.waitForTimeout(1500);
  const c = await centre();
  console.log(JSON.stringify({ start: a, narrower: b, back: c }));
  await browser.close();
};

modes[process.env.MODE || "feel"]();
