// INBOX 1679 diagram sweeps in one file (the scratchpad count is capped): node diagram-escape.js <mode> [width], BASE=http://127.0.0.1:PORT.
// Modes: escape (Escape mid-drag, slice 4), keys (Alt+Up in the flow-ordered list), sheet-escape (390: the Connect picker and the Blocks sheet),
// phone-picture (390 picture share, slice 11), fit-floor (Fit floor, slice 7), open-new (New diagram dialog).
process.env.BASE ||= "http://127.0.0.1:8781";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
const modes = {};
modes["escape"] = () => {
const W = Number(process.argv[3] || 1440);
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: 900 } });
  const src = "flowchart TD\n  A[One] --> B[Two]\n  B --> C[Three]\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Escape " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector(".dgm-picture .md-mermaid-img", { timeout: 15000 });
  await page.waitForTimeout(1500);
  // The first arrow's midpoint on screen, from the drawing's own path and viewBox.
  const mid = await page.evaluate(() => {
    const img = document.querySelector(".dgm-picture .md-mermaid-img");
    const svg = img.mermaidSvg;
    const vb = /viewBox="\s*([-\d.e]+)[ ,]+([-\d.e]+)[ ,]+([\d.e]+)[ ,]+([\d.e]+)/.exec(svg).slice(1).map(Number);
    const d = /<path[^>]*class="[^"]*flowchart-link[^"]*"[^>]*\sd="([^"]+)"/.exec(svg)?.[1] || /<path[^>]*\sd="([^"]+)"[^>]*class="[^"]*flowchart-link/.exec(svg)?.[1];
    const n = d.match(/-?\d+(\.\d+)?/g).map(Number);
    const pts = [];
    for (let i = 0; i + 1 < n.length; i += 2) pts.push([n[i], n[i + 1]]);
    const p = pts[Math.floor(pts.length / 2)];
    const r = img.getBoundingClientRect();
    return { x: r.left + ((p[0] - vb[0]) / vb[2]) * r.width, y: r.top + ((p[1] - vb[1]) / vb[3]) * r.height };
  });
  await page.mouse.click(mid.x, mid.y);
  await page.waitForTimeout(400);
  const dot = await page.evaluate(() => { const d = document.querySelector(".dgm-end[data-end=to]"); if (!d || d.classList.contains("hidden")) return null; const r = d.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
  const out = { picked: Boolean(dot) };
  if (!dot) { console.log(JSON.stringify(out)); await browser.close(); process.exit(1); }
  const before = await page.evaluate(() => (typeof docText === "function" ? docText() : currentDoc?.content));
  await page.mouse.move(dot.x, dot.y);
  await page.mouse.down();
  await page.mouse.move(dot.x - 60, dot.y - 40, { steps: 6 });
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  await page.mouse.up();
  await page.waitForTimeout(900);
  out.after = await page.evaluate(() => ({
    source: typeof docText === "function" ? docText() : currentDoc?.content,
    question: Boolean(document.querySelector(".confirm-card, .prompt-card, [role=alertdialog], .modal-overlay:not(.hidden) .confirm-actions")),
    stillPicked: Boolean(document.querySelector(".dgm-end[data-end=to]:not(.hidden)")),
    builderOpen: Boolean(document.querySelector(".dgm-picture")),
  }));
  out.unchanged = out.after.source === before;
  console.log(JSON.stringify(out));
  await browser.close();
  process.exit(out.unchanged && !out.after.question && out.after.builderOpen ? 0 : 1);
})();

};
modes["keys"] = () => {
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const src = "flowchart TD\n  CEO --> Sales\n  CEO --> Design\n  CEO --> Eng\n  Eng --> Front\n  Eng --> Back\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Keys " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector(".dgm-tree .dgm-block", { timeout: 15000 });
  await page.waitForTimeout(1500);
  const keys = () => page.$$eval(".dgm-tree .dgm-block", (b) => b.map((x) => x.dataset.key));
  const before = await keys();
  await page.focus('.dgm-tree .dgm-block[data-key="n:Design"]');
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(500);
  const after = await keys();
  const active = await page.evaluate(() => document.activeElement?.dataset?.key);
  const ok = JSON.stringify(before) === JSON.stringify(after) && active === "n:Design";
  console.log(JSON.stringify({ before, after, active, ok }));
  await browser.close();
  process.exit(ok ? 0 : 1);
})();

};
modes["sheet-escape"] = () => {
(async () => {
  const { browser, page } = await boot({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const src = "flowchart TD\n  A[One] --> B[Two]\n  B --> C[Three]\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Sheet " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector('[aria-label="Blocks list"]', { timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.click('[aria-label="Blocks list"]');
  await page.waitForSelector(".sheet-overlay .dgm-block");
  await page.focus('.sheet-overlay .dgm-block[data-key="n:A"]');
  await page.click(".sheet-overlay .dgm-block[data-key=\"n:A\"] >> text=Connect to");
  await page.waitForSelector(".confirm-overlay:not(.hidden)", { timeout: 5000 }).catch(() => {});
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  const sheetAfterOne = await page.$(".sheet-overlay:not(.hidden):not(.sheet-leaving)");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(800);
  const sheetAfterTwo = await page.$(".sheet-overlay:not(.hidden):not(.sheet-leaving)");
  const ok = Boolean(sheetAfterOne) && !sheetAfterTwo;
  console.log(JSON.stringify({ sheetAfterOne: Boolean(sheetAfterOne), sheetAfterTwo: Boolean(sheetAfterTwo), ok }));
  await browser.close();
  process.exit(ok ? 0 : 1);
})();

};
modes["phone-picture"] = () => {
(async () => {
  const { browser, page } = await boot({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const src = "flowchart TD\n  A[Start]-->B[Middle]\n  B-->C[End]\n  C-->D[More]\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Phone " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector(".dgm-picture", { timeout: 12000 });
  await page.waitForTimeout(2000);
  const out = {};
  out.closed = await page.evaluate(() => {
    const fig = document.querySelector(".dgm-picture").getBoundingClientRect();
    const pane = document.querySelector(".dgm-pane");
    return { figH: Math.round(fig.height), frac: +(fig.height / innerHeight).toFixed(3), paneShown: pane.getBoundingClientRect().height > 0, btn: !!document.querySelector(".dgm-listbtn"), btnRect: (() => { const r = document.querySelector(".dgm-listbtn")?.getBoundingClientRect(); return r && [Math.round(r.width), Math.round(r.height)]; })() };
  });
  out.below = await page.evaluate(() => { const els = [...document.querySelectorAll("body *")].filter((e) => { const r = e.getBoundingClientRect(); return r.top > 600 && r.height > 20 && r.width > 200 && getComputedStyle(e).position !== "static"; }).slice(0, 8); return els.map((e) => [e.id || e.className.toString().slice(0, 30), Math.round(e.getBoundingClientRect().top), Math.round(e.getBoundingClientRect().height)]); });
  out.chain = await page.evaluate(() => ["dgm", "dgm-body", "dgm-stage", "dgm-picture", "dgm-zoom"].map((c) => { const e = document.querySelector("." + c); const r = e?.getBoundingClientRect(); return [c, r && Math.round(r.top), r && Math.round(r.height)]; }));
  out.sheets0 = await page.evaluate(() => document.querySelectorAll(".sheet-overlay:not(.sheet-leaving)").length);
  await page.tap(".dgm-listbtn");
  await page.waitForTimeout(600);
  out.open = await page.evaluate(() => {
    const sheet = document.querySelector('.sheet-overlay[data-sheet="diagram-blocks"]');
    const small = [...sheet.querySelectorAll("button, [role=button], .dgm-grip")].filter((e) => e.offsetParent).map((e) => [e.className.toString().slice(0, 28), Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)]).filter(([, w, h]) => w < 44 || h < 44);
    const grip = sheet.querySelector(".dgm-grip").getBoundingClientRect();
    return { rows: sheet.querySelectorAll(".dgm-block").length, grip: [Math.round(grip.width), Math.round(grip.height)], small };
  });
  await page.screenshot({ path: process.env.SCRATCH + "/s11-open.png" });
  // tap Connect on the first row
  await page.tap('.sheet-overlay[data-sheet="diagram-blocks"] .dgm-connect >> nth=0');
  await page.waitForTimeout(700);
  out.picker = await page.evaluate(() => ({ active: document.activeElement?.tagName + "." + (document.activeElement?.className || "").toString().slice(0, 30), inSearch: !!document.activeElement?.closest?.(".picker-search, .picker-card, .modal-card") }));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(700);
  out.after = await page.evaluate(() => ({ sheets: document.querySelectorAll(".sheet-overlay:not(.sheet-leaving)").length, paneBack: document.querySelector(".dgm-body > .dgm-pane") !== null, paneShown: document.querySelector(".dgm-pane").getBoundingClientRect().height > 0 }));
  console.log(JSON.stringify(out));
  await browser.close();
})();

};
modes["fit-floor"] = () => {
const W = Number(process.argv[3] || 1440), touch = W < 600;
const tall = "flowchart TD\n  A[Start]-->B[One]\n  B-->C[Two]\n  C-->D[Three]\n  D-->E[Four]\n  E-->F[Five]\n  F-->G[Six]\n  G-->H[Seven]\n  H-->I[Eight]\n  I-->J[Nine]\n  J-->K[Ten]\n  K-->L[Eleven]\n  L-->M[Twelve]\n";
const lr = tall.replace("TD", "LR");
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: touch ? 844 : 900 }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  const open = async (c) => {
    await page.evaluate(async (c) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Tall " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
      setDocView("canvas", { persist: false });
    }, c);
    await page.waitForSelector(".dgm-block", { timeout: 12000 });
    await page.waitForTimeout(1800);
  };
  const read = () => page.evaluate(() => {
    const img = document.querySelector(".dgm-picture .md-mermaid-img");
    const o = document.querySelector(".dgm-sideways");
    const fig = document.querySelector(".dgm-picture");
    return { zoom: document.querySelector(".dgm-picture").dataset.zoom, pct: [...document.querySelectorAll(".dgm-picture ~ * button, .dgm-stage button")].map((b) => b.textContent).filter((t) => /%/.test(t))[0], imgW: img && Math.round(img.getBoundingClientRect().width), figScroll: [fig.scrollHeight, fig.clientHeight], offer: !!o && !o.classList.contains("hidden"), offerText: o?.textContent };
  });
  await open(tall);
  const a = await read();
  const dir = await page.evaluate(() => { const b = document.querySelector(".dgm-dirs"); return { text: b.textContent, aria: b.getAttribute("aria-label"), popup: b.getAttribute("aria-haspopup") }; });
  await page.click(".dgm-dirs");
  await page.waitForTimeout(300);
  const menu = await page.evaluate(() => [...document.querySelectorAll(".pointer-menu-host button, .pointer-menu-host [role=menuitem], .action-menu:not(.hidden) button")].map((i) => i.textContent.trim()));
  await page.keyboard.press("Escape");
  let turned = null;
  if (await page.$(".dgm-sideways:not(.hidden) button")) {
    await page.click(".dgm-sideways:not(.hidden) button >> nth=0");
    await page.waitForTimeout(1200);
    turned = await page.evaluate(() => [document.querySelector(".dgm-dirs").dataset.dir, !!document.querySelector(".dgm-sideways:not(.hidden)")]);
  }
  console.log(JSON.stringify({ W, a, dir, menu, turned, after: await read() }));
  await page.screenshot({ path: process.env.SCRATCH + `/s7-${W}.png` });
  await open(lr);
  console.log(JSON.stringify({ lr: await read() }));
  await browser.close();
})();

};
modes["open-new"] = () => {
const W = Number(process.argv[2] || 390), touch = W < 600;
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: touch ? 844 : 900 }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  await page.evaluate(async () => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Open " + Date.now() + ".mmd", content: "flowchart TD\n  A-->B\n", file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  });
  await page.waitForSelector(".dgm-picture", { timeout: 12000 });
  await page.waitForTimeout(1500);
  const out = { W };
  out.btn = await page.evaluate(() => {
    const b = document.getElementById("doc-new-diagram");
    if (!b) return null;
    const r = b.getBoundingClientRect();
    const chain = [];
    for (let e = b; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden" || e.classList.contains("hidden") || e.hidden) chain.push(e.id || e.className.toString().slice(0, 30)); }
    return { rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], hiddenBy: chain, inView: r.width > 0 && r.top >= 0 && r.top < innerHeight };
  });
  // the library door
  out.nav = await page.evaluate(() => [...document.querySelectorAll("#phone-tab-dock button, #phone-tab-dock a")].map((e) => (e.getAttribute("aria-label") || e.textContent).trim().slice(0, 20)));
  if (out.btn?.inView && !process.env.NOTAP) {
    await (touch ? page.tap("#doc-new-diagram") : page.click("#doc-new-diagram"));
    await page.waitForTimeout(1500);
    out.after = await page.evaluate(() => {
      const dlg = document.querySelector(".dgm-dialog");
      const ov = dlg?.closest(".modal-overlay, .sheet-overlay, [role=dialog]") || dlg;
      const r = dlg?.getBoundingClientRect();
      return { dialog: Boolean(dlg), cls: ov?.className?.toString().slice(0, 50), rect: r && [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], role: ov?.getAttribute?.("role") };
    });
  }
  console.log(JSON.stringify(out));
  await page.screenshot({ path: process.env.SCRATCH + `/open-new-${W}.png` });
  await browser.close();
})();

};
(modes[process.argv[2]] || (() => { console.log("modes: " + Object.keys(modes).join(", ")); process.exit(2); }))();
