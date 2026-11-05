// INBOX 1679 diagram sweeps in one file (the scratchpad count is capped): node diagram-escape.js <mode> [width], BASE=http://127.0.0.1:PORT.
// Modes: escape (Escape mid-drag, slice 4), keys (Alt+Up in the flow-ordered list), sheet-escape (390: the Connect picker and the Blocks sheet),
// phone-picture (390 picture share, slice 11), fit-floor (Fit floor, slice 7), open-new (New diagram dialog), templates (slice 9), edge-colour (slice 10).
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
modes["templates"] = () => {
const W = Number(process.argv[3] || 1440), touch = W < 600;
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: touch ? 844 : 900 }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  const out = { W };
  await page.evaluate(async () => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Known " + Date.now(), content: "flowchart TD\n  A-->B\n", file_type: "mmd" }) });
    await r.json();
    switchTab("documents");
  });
  await page.waitForTimeout(1500);
  await page.evaluate(() => document.getElementById("doc-new-diagram")?.click());
  await page.waitForSelector(".dgm-dialog", { timeout: 12000 });
  await page.waitForTimeout(800);
  await page.evaluate(() => [...document.querySelectorAll(".dgm-dialog button")].find((b) => /template/i.test(b.textContent))?.click());
  await page.waitForSelector(".dgm-template-dialog .doc-template-choice", { timeout: 8000 });
  await page.waitForTimeout(600);
  out.dialog = await page.evaluate(() => {
    const d = document.querySelector(".dgm-template-dialog");
    const r = d.getBoundingClientRect();
    const f = d.querySelector(".list-filter");
    const fr = f?.getBoundingClientRect();
    return { rows: d.querySelectorAll(".doc-template-choice").length, filter: f ? !f.classList.contains("hidden") : null, filterH: fr && Math.round(fr.height), rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], fits: r.bottom <= innerHeight + 1 && r.right <= innerWidth + 1 };
  });
  await page.fill(".dgm-template-dialog .list-filter input", "swim");
  await page.waitForTimeout(300);
  out.typed = await page.evaluate(() => [...document.querySelectorAll(".dgm-template-dialog .doc-template-choice")].filter((b) => b.offsetParent).map((b) => b.dataset.template));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  out.escapeKeptDialog = await page.evaluate(() => Boolean(document.querySelector(".dgm-template-dialog[open]")));
  // The door: Open an existing diagram.
  await page.evaluate(() => document.querySelector(".dgm-template-dialog")?.close());
  await page.waitForTimeout(300);
  out.known = await page.evaluate(() => {
    const b = [...document.querySelectorAll(".dgm-dialog button")].find((x) => /existing diagram/i.test(x.textContent));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), inView: r.right <= innerWidth && r.bottom <= innerHeight };
  });
  await page.evaluate(() => [...document.querySelectorAll(".dgm-dialog button")].find((x) => /existing diagram/i.test(x.textContent))?.click());
  await page.waitForTimeout(800);
  out.list = await page.evaluate(() => [...document.querySelectorAll("[role=option]")].map((o) => o.textContent.trim().slice(0, 30)));
  await page.keyboard.press("Enter");
  await page.waitForTimeout(2500);
  out.opened = await page.evaluate(() => ({ dlg: Boolean(document.querySelector(".dgm-dialog")), title: document.getElementById("doc-title")?.value, picture: Boolean(document.querySelector(".dgm-picture")) }));
  // Each template: a document made from it renders every box after a reload.
  const all = await page.evaluate(async () => (await (await fetch("/board-library/diagram-templates.json")).json()).templates.filter((t) => !t.kind));
  out.each = [];
  for (const t of all) {
    const id = await page.evaluate(async (t) => { const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "T " + t.id, content: t.source, file_type: "mmd" }) }); return (await r.json()).id; }, t);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    await page.evaluate(async (id) => { switchTab("documents"); await openDocument(id); setDocView("canvas", { persist: false }); }, id);
    try { await page.waitForSelector(".dgm-picture .md-mermaid-img", { timeout: 10000 }); } catch { out.each.push({ id: t.id, error: "no picture" }); continue; }
    await page.waitForFunction((t) => { const m = diagramModel.parse(t.source); return !m.nodes.length || (document.querySelector(".dgm-picture .md-mermaid-img")?.mermaidSvg || "").includes(m.nodes[m.nodes.length - 1].text.split(" ")[0]); }, t, { timeout: 10000 }).catch(() => {});
    out.each.push(await page.evaluate((t) => {
      const img = document.querySelector(".dgm-picture .md-mermaid-img");
      if (!img || !img.mermaidSvg) return { id: t.id, error: "no svg" };
      const m = diagramModel.parse(t.source);
      const boxes = m.nodes.filter((n) => img.mermaidSvg.includes(n.text.split(" ")[0].replace(/&/g, "&amp;"))).length;
      return { id: t.id, nodes: m.nodes.length, drawn: boxes, same: diagramModel.print(m) === t.source };
    }, t));
  }
  console.log(JSON.stringify(out));
  await browser.close();
})();

};
modes["edge-colour"] = () => {
const W = Number(process.argv[3] || 1440), touch = W < 600;
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: touch ? 844 : 900 }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  const out = { W };
  const src = "flowchart TD\n  A[One] --> B[Two]\n  C[Three]\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Colour " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector(".dgm-picture .md-mermaid-img", { timeout: 15000 });
  await page.waitForTimeout(1800);
  const source = () => page.evaluate(() => docText());
  const mid = () => page.evaluate(() => {
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
  const menu = async () => {
    // A picked arrow keeps its end handles over a short arrow's midpoint: drop the pick first.
    await page.keyboard.press("Escape");
    await page.mouse.click(5, 300);
    await page.waitForTimeout(300);
    const m = await mid();
    if (touch) { await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, clientX: x, clientY: y, button: 2 })), m); }
    else await page.mouse.click(m.x, m.y, { button: "right" });
    await page.waitForTimeout(500);
  };
  await menu();
  out.menu = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")].map((b) => b.textContent.trim().replace(/\s+/g, " ")));
  const click = async (re) => page.evaluate((s) => { const b = [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item, .sheet .swatch-option, .swatch-card .swatch-option")].find((x) => new RegExp(s, "i").test(x.getAttribute("aria-label") || x.textContent)); b?.click(); return Boolean(b); }, re);
  out.colourClicked = await click("^\\s*Colour");
  await page.waitForTimeout(600);
  out.swatches = await page.evaluate(() => document.querySelectorAll(".swatch-card .swatch-option").length);
  out.swatchSize = await page.evaluate(() => { const r = document.querySelector(".swatch-card .swatch-option")?.getBoundingClientRect(); return r && [Math.round(r.width), Math.round(r.height)]; });
  await click("^Blue$");
  await page.waitForTimeout(1500);
  out.afterColour = (await source()).split("\n").filter((l) => /linkStyle/.test(l));
  out.drawn = await page.evaluate(() => /#387fe3/i.test(document.querySelector(".dgm-picture .md-mermaid-img").mermaidSvg));
  // contrast of each hue (as the stroke) against the picture's ground
  out.contrast = await page.evaluate(() => {
    const lum = (rgb) => { const c = rgb.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
    const parse = (s) => s.match(/[\d.]+/g).slice(0, 3).map(Number);
    let el = document.querySelector(".dgm-picture"); let bg = [0, 0, 0, 0];
    for (; el; el = el.parentElement) { const c = getComputedStyle(el).backgroundColor; const a = c.match(/[\d.]+/g); if (a && (a.length < 4 || Number(a[3]) > 0.9)) { bg = parse(c); break; } }
    const lb = lum(bg);
    const out = {};
    for (const [k, hex] of Object.entries(CATEGORY_PALETTE)) { const l = lum([1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))); out[k] = Math.round(((Math.max(l, lb) + 0.05) / (Math.min(l, lb) + 0.05)) * 100) / 100; }
    return { ground: bg, min: Math.min(...Object.values(out)), hues: out };
  });
  await menu();
  out.menu2 = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")].map((b) => b.textContent.trim()));
  out.at = await mid();
  out.hit = await page.evaluate(({ x, y }) => { const e = document.elementFromPoint(x, y); return e && (e.tagName + "." + String(e.className).slice(0, 60)); }, out.at);
  out.overlay = await page.evaluate(() => document.querySelectorAll(".sheet, .modal-overlay:not(.hidden), [role=dialog]:not(.hidden)").length);
  out.both = await click("Both ways");
  await page.waitForTimeout(1500);
  out.afterBoth = (await source()).split("\n").filter((l) => /<-->|linkStyle/.test(l));
  out.headAtStart = await page.evaluate(() => /marker-start/.test(document.querySelector(".dgm-picture .md-mermaid-img").mermaidSvg));
  await menu();
  out.menuAgain = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")].map((b) => ({ t: b.textContent.trim(), cur: b.getAttribute("aria-current") })).filter((x) => x.cur));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  // one undo takes the last change back
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(1200);
  out.afterUndo = (await source()).split("\n").filter((l) => /<-->|linkStyle|-->/.test(l));
  // reload keeps the colour
  out.saved = await page.evaluate(async () => { await saveDocument?.(); return currentDoc?.id; });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
  await page.evaluate(async (id) => { switchTab("documents"); await openDocument(id); setDocView("canvas", { persist: false }); }, out.saved);
  await page.waitForTimeout(2500);
  out.reloaded = (await source()).split("\n").filter((l) => /linkStyle|-->/.test(l));
  // the selection bar
  // A phone has no Ctrl+click: the Blocks list opens as a sheet and Shift+Down extends the pick (slice 11's keys).
  if (touch) await page.click('[aria-label="Blocks list"]');
  await page.waitForSelector(".dgm-block", { timeout: 8000 });
  const blocks = await page.$$(".dgm-block");
  await blocks[0].click({ position: { x: 20, y: 8 } });
  if (touch) await page.keyboard.press("Shift+ArrowDown");
  else await blocks[blocks.length - 1].click({ position: { x: 20, y: 8 }, modifiers: ["Control"] });
  await page.waitForTimeout(500);
  out.bar = await page.evaluate(() => { const b = document.querySelector(".dgm-selectbar:not(.hidden)"); return b && [...b.querySelectorAll("button")].map((x) => { const r = x.getBoundingClientRect(); return [x.getAttribute("aria-label") || x.textContent.trim(), Math.round(r.width), Math.round(r.height)]; }); });
  out.barFits = await page.evaluate(() => { const b = document.querySelector(".dgm-selectbar:not(.hidden)"); const r = b?.getBoundingClientRect(); return r && { right: Math.round(r.right), scrollW: b.scrollWidth, clientW: b.clientWidth, vw: innerWidth }; });
  out.smallTargets = (out.bar || []).filter(([, w, h]) => touch && (w < 44 || h < 44)).length;
  const before = await source();
  await page.evaluate(() => [...document.querySelectorAll(".dgm-selectbar button")].find((x) => x.getAttribute("aria-label") === "Connect")?.click());
  await page.waitForTimeout(1200);
  out.connected = (await source()).split("\n").filter((l) => /-->/.test(l));
  out.connectChanged = (await source()) !== before;
  await page.evaluate(() => [...document.querySelectorAll(".dgm-selectbar button")].find((x) => x.getAttribute("aria-label") === "Colour")?.click());
  await page.waitForTimeout(800);
  out.barColour = await page.evaluate(() => document.querySelectorAll(".swatch-card .swatch-option").length);
  console.log(JSON.stringify(out));
  await browser.close();
})();

};
modes["drag-word"] = () => {
const W = Number(process.argv[3] || 1440);
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: 900 } });
  const out = { W };
  const src = "flowchart TD\n  subgraph G [Team]\n    X[Inner]\n  end\n  A[One] --> B[Two]\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Drag " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector(".dgm-picture .md-mermaid-img", { timeout: 15000 });
  await page.waitForTimeout(2200);
  const source = () => page.evaluate(() => docText());
  const rect = (sel) => page.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, l: r.left, t: r.top, r: r.right, b: r.bottom }; }, sel);
  out.boxes = await page.evaluate(() => [...document.querySelectorAll(".dgm-overlay .dgm-box")].map((b) => b.dataset.node || "g:" + b.dataset.group));
  const a = await rect('.dgm-overlay .dgm-box[data-node="A"]');
  let b = null, g = null;
  const stage = await rect(".dgm-stage");
  const before = await source();
  // 1) a box dragged to empty space: no change, snaps back
  const empty = { x: stage.r - 30, y: stage.b - 30 };
  await page.mouse.move(a.x, a.y);
  await page.mouse.down();
  await page.mouse.move(a.x + 20, a.y + 20, { steps: 3 });
  await page.mouse.move(empty.x, empty.y, { steps: 8 });
  out.emptyWord = await page.evaluate(() => { const t = document.querySelector(".dgm-drop-word"); return t && !t.classList.contains("hidden") ? t.textContent : null; });
  out.emptyRing = await page.evaluate(() => document.querySelectorAll(".dgm-target").length);
  await page.mouse.up();
  await page.waitForTimeout(900);
  out.emptyChanged = (await source()) !== before;
  out.wordGone = await page.evaluate(() => { const t = document.querySelector(".dgm-drop-word"); return !t || t.classList.contains("hidden"); });
  out.liftedLeft = await page.evaluate(() => document.querySelectorAll(".dgm-lifted").length);
  // 2) over a box: the caption within 50 ms, and its look
  await page.evaluate(() => {
    window.__t = { move: 0, shown: 0 };
    document.addEventListener("pointermove", () => { const t = document.querySelector(".dgm-drop-word"); if (!t || t.classList.contains("hidden")) { window.__t.move = performance.now(); window.__t.shown = 0; } }, true);
    new MutationObserver(() => { const t = document.querySelector(".dgm-drop-word"); if (t && !t.classList.contains("hidden") && !window.__t.shown) window.__t.shown = performance.now(); }).observe(document.body, { subtree: true, attributes: true, childList: true, characterData: true });
  });
  // The picture refits after a drag: the targets are read again, not carried over.
  b = await rect('.dgm-overlay .dgm-box[data-node="B"]');
  g = await rect('.dgm-overlay .dgm-box.dgm-cluster');
  const a2 = await rect('.dgm-overlay .dgm-box[data-node="A"]');
  await page.mouse.move(a2.x, a2.y);
  await page.mouse.down();
  await page.mouse.move(a2.x + 10, a2.y + 10, { steps: 2 });
  await page.mouse.move(b.x, b.y, { steps: 6 });
  await page.mouse.move(b.x + 2, b.y + 1, { steps: 2 });
  await page.waitForTimeout(150);
  out.geo = await page.evaluate((pt) => { const e = document.elementFromPoint(pt.x, pt.y); return { b: pt, hit: e && (e.tagName + "." + String(e.className).slice(0, 40)), vh: innerHeight }; }, b);
  out.state = await page.evaluate(() => { const t = document.querySelector(".dgm-drop-word"); return { tagClass: t?.className, targets: [...document.querySelectorAll(".dgm-target")].map((e) => e.className.slice(0, 40)), lifted: document.querySelectorAll(".dgm-lifted").length, tagRect: t && JSON.stringify(t.getBoundingClientRect()) }; });
  out.boxWord = await page.evaluate(() => ({ text: document.querySelector(".dgm-drop-word")?.textContent, latencyMs: Math.round(window.__t.shown - window.__t.move) }));
  out.look = await page.evaluate(() => { const t = document.querySelector(".dgm-drop-word"); const cs = getComputedStyle(t); const r = t.getBoundingClientRect(); return { size: cs.fontSize, bg: cs.backgroundColor, color: cs.color, rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], inView: r.right <= innerWidth && r.bottom <= innerHeight && r.left >= 0 && r.top >= 0, token: getComputedStyle(document.documentElement).getPropertyValue("--text-xs").trim() }; });
  // 3) over a group
  await page.mouse.move(g.x, g.t + 6, { steps: 6 });
  await page.waitForTimeout(150);
  out.groupWord = await page.evaluate(() => document.querySelector(".dgm-drop-word")?.textContent);
  await page.keyboard.press("Escape");
  await page.mouse.up();
  await page.waitForTimeout(600);
  // 4) a palette tile dropped on empty space still adds
  await page.evaluate(() => document.querySelector(".dgm-addcaret")?.click());
  await page.waitForTimeout(700);
  const tile = await rect(".dgm-tile");
  out.tile = Boolean(tile);
  if (tile) {
    const n0 = (await source()).split("\n").length;
    await page.mouse.move(tile.x, tile.y);
    await page.mouse.down();
    await page.mouse.move(tile.x + 15, tile.y - 15, { steps: 3 });
    await page.mouse.move(empty.x, empty.y, { steps: 8 });
    out.tileWord = await page.evaluate(() => { const t = document.querySelector(".dgm-drop-word"); return t && !t.classList.contains("hidden") ? t.textContent : null; });
    await page.mouse.up();
    await page.waitForTimeout(1200);
    out.tileAdded = (await source()).split("\n").length - n0;
  }
  out.finalSource = (await source()).split("\n").slice(0, 12);
  console.log(JSON.stringify(out));
  await browser.close();
})();

};
modes["pan-zoom"] = () => {
// Slice 13 (1679 k, l): input-to-paint latency and zoom-step evenness of the picture pane. node diagram-escape.js pan-zoom [width]; THEME=dark for dark.
const W = Number(process.argv[3] || 1440), touch = W < 600;
const small = "flowchart TD\n  A[Start]-->B[Check]\n  B-->C[Done]\n";
const big = "flowchart TD\n  A0[Start]\n" + Array.from({ length: 59 }, (_, i) => `  A${i + 1}[Step ${i + 1}]\n  A${Math.floor(i / 2)}-->A${i + 1}`).join("\n") + "\n";
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: touch ? 844 : 900 }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  const open = async (c) => {
    await page.evaluate(async (c) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "PZ " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
      setDocView("canvas", { persist: false });
    }, c);
    await page.waitForSelector(".dgm-block", { state: "attached", timeout: 15000 });
    await page.waitForTimeout(2500);
  };
  const probe = () => page.evaluate(() => {
    window.__lat = []; window.__sync = [];
    const fig = document.querySelector(".dgm-picture");
    const mc = new MessageChannel();
    let t0 = 0;
    fig.addEventListener("wheel", () => { t0 = performance.now(); }, true);
    fig.addEventListener("pointermove", () => { t0 = performance.now(); }, true);
    document.body.addEventListener("wheel", () => { window.__sync.push(performance.now() - t0); }, false); document.body.addEventListener("pointermove", () => { window.__sync.push(performance.now() - t0); }, false);
    const after = () => requestAnimationFrame(() => { mc.port2.postMessage(0); });
    mc.port1.onmessage = () => { window.__lat.push(performance.now() - t0); };
    for (const t of ["wheel", "pointermove"]) window.addEventListener(t, () => { if (document.querySelector(".dgm-picture").contains(event.target)) after(); }, false);
  });
  const stats = (a) => { const s = [...a].sort((x, y) => x - y); return { n: s.length, med: +(s[Math.floor(s.length / 2)] || 0).toFixed(1), p95: +(s[Math.floor(s.length * 0.95)] || 0).toFixed(1), max: +(s[s.length - 1] || 0).toFixed(1) }; };
  const out = { W, theme: process.env.THEME || "light" };
  for (const [name, src] of [["small", small], ["big", big]]) {
    await open(src);
    await probe();
    const box = await page.evaluate(() => { const r = document.querySelector(".dgm-picture").getBoundingClientRect(); const top = Math.max(r.top, 0), bot = Math.min(r.bottom, innerHeight); return { x: r.x + r.width / 2, y: (top + bot) / 2 }; });
    await page.mouse.move(box.x, box.y);
    const w0 = () => page.evaluate(() => document.querySelector(".dgm-picture .md-mermaid-img").getBoundingClientRect().width);
    const before = await w0();
    // 12 wheel notches (ctrl+wheel as a pinch; plain wheel too), 50 ms apart
    await page.keyboard.down("Control");
    for (let i = 0; i < 12; i++) { await page.mouse.wheel(0, -100); await page.waitForTimeout(50); }
    await page.keyboard.up("Control");
    const afterCtrl = await w0();
    for (let i = 0; i < 12; i++) { await page.mouse.wheel(0, -100); await page.waitForTimeout(50); }
    const afterPlain = await w0();
    // drag pan: 30 moves
    await page.mouse.down();
    for (let i = 0; i < 30; i++) { await page.mouse.move(box.x - i * 6, box.y - i * 3); await page.waitForTimeout(8); }
    await page.mouse.up();
    await page.waitForTimeout(600);
    const lat = await page.evaluate(() => ({ lat: window.__lat, sync: window.__sync }));
    // zoom steps with the + button: widths ratio per press, from Fit
    await page.click(".dgm-zoom button[title='Fit the diagram to the pane']");
    await page.waitForTimeout(200);
    const widths = [await w0()];
    let presses = 0;
    for (let i = 0; i < 9; i++) { if (await page.$eval(".dgm-zoom button[aria-label='Zoom in']", (b) => b.disabled)) break; await page.click(".dgm-zoom button[aria-label='Zoom in']"); presses++; await page.waitForTimeout(60); widths.push(await w0()); }
    const ratios = widths.slice(1).map((w, i) => +(w / widths[i]).toFixed(3));
    // pan reach at fit and a drag at fit
    await page.click(".dgm-zoom button[title='Fit the diagram to the pane']");
    await page.waitForTimeout(200);
    const fig0 = await page.evaluate(() => { const f = document.querySelector(".dgm-picture"); const i = f.querySelector(".md-mermaid-img").getBoundingClientRect(); return [Math.round(i.x), Math.round(i.y)]; });
    await page.mouse.move(box.x, box.y); await page.mouse.down(); await page.mouse.move(box.x + 80, box.y + 40, { steps: 5 }); await page.mouse.up();
    const fig1 = await page.evaluate(() => { const i = document.querySelector(".dgm-picture .md-mermaid-img").getBoundingClientRect(); return [Math.round(i.x), Math.round(i.y)]; });
    // a plain wheel (three notches) from Fit, and a fast drag then release: how far the picture keeps going
    await page.click(".dgm-zoom button[title='Fit the diagram to the pane']");
    await page.waitForTimeout(300);
    await page.mouse.move(box.x, box.y);
    const wFit = await w0();
    for (let i = 0; i < 3; i++) { await page.mouse.wheel(0, -100); await page.waitForTimeout(30); }
    await page.waitForTimeout(350);
    const plain = +((await w0()) / wFit).toFixed(3);
    await page.mouse.move(box.x + 150, box.y);
    const sl = () => page.evaluate(() => document.querySelector(".dgm-picture").scrollLeft);
    await page.mouse.down();
    const s0 = await sl();
    for (let i = 0; i < 12; i++) { await page.mouse.move(box.x + 150 - i * 12, box.y); await page.waitForTimeout(8); }
    const s1 = await sl();
    await page.mouse.up();
    await page.waitForTimeout(700);
    const glide = [s1 - s0, (await sl()) - s1];
    await page.click(".dgm-zoom button[title='Fit the diagram to the pane']");
    await page.waitForTimeout(300);
    out[name] = { w: [Math.round(before), Math.round(afterCtrl), Math.round(afterPlain)], latency: stats(lat.lat), sync: stats(lat.sync), ratios, evenness: +(Math.max(...ratios) / Math.min(...ratios)).toFixed(3), presses, plain, glide, dragAtFitMoved: [fig1[0] - fig0[0], fig1[1] - fig0[1]] };
  }
  console.log(JSON.stringify(out));
  await browser.close();
})();

};
modes["panel"] = () => {
// Slice 14 (1679 k): the blocks pane on first use. node diagram-escape.js panel [width]; THEME=dark for dark.
const W = Number(process.argv[3] || 1440), touch = W < 600;
const src = "flowchart TD\n  A[Start]-->B{Check}\n  B-->|yes|C[Done]\n  B-->|no|D[Retry]\n  D-->B\n";
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: touch ? 844 : 900 }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Panel " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector(".dgm-block", { state: "attached", timeout: 15000 });
  await page.waitForTimeout(2500);
  if (touch) { const b = await page.$(".dgm-listbtn"); if (b) { await b.click(); await page.waitForTimeout(800); } }
  const rest = await page.evaluate(() => {
    const pane = document.querySelector(".dgm-pane");
    const rows = [...pane.querySelectorAll(".dgm-card")];
    const last = rows[rows.length - 1];
    const joins = [...pane.querySelectorAll(".dgm-join")];
    const worded = [...pane.querySelectorAll("button")].filter((b) => (b.textContent || "").trim().length > 1 && getComputedStyle(b).display !== "none");
    const addBtns = [...document.querySelectorAll("button")].filter((b) => /^\s*Add\b/.test(b.textContent || "") && b.offsetParent && !b.closest(".dgm-card"));
    const lb = last.getBoundingClientRect().bottom;
    const near = Math.min(...addBtns.map((b) => Math.abs(b.getBoundingClientRect().top - lb)));
    const iconOnlyPerRow = rows.slice(0, 1).map((r) => [...r.querySelectorAll("button")].filter((b) => !(b.textContent || "").trim() || getComputedStyle(b.querySelector(".ph-text") || b).display === "none").length);
    return { purpose: pane.querySelector(".dgm-purpose")?.textContent || null, foot: [...pane.querySelectorAll(".dgm-foot button")].map((b) => b.textContent.trim()), paneW: Math.round(pane.getBoundingClientRect().width), paneH: Math.round(pane.getBoundingClientRect().height), nearestAddOrConnect: Math.round(near), iconOnlyOnRow1: iconOnlyPerRow[0], scrollOk: pane.scrollHeight <= pane.clientHeight + 1 || getComputedStyle(pane).overflowY !== "visible" };
  });
  const tips = {};
  if (!touch) for (const [name, sel] of [["grip", ".dgm-grip"], ["shape", ".dgm-swatch"], ["label", ".dgm-label"], ["connect", ".dgm-connect"], ["menu", ".dgm-menu button, .dgm-menu"], ["join", ".dgm-join"], ["add", ".dgm-foot button >> nth=0"]]) {
    const el = await page.$(sel.includes(">>") ? sel : sel);
    if (!el) { tips[name] = null; continue; }
    await el.hover();
    await page.waitForTimeout(120);
    tips[name] = await page.evaluate(() => document.querySelector(".dgm-purpose")?.textContent || null);
  }
  // keyboard: focus lands on a grip-less row; Tab to Connect and read the line
  console.log(JSON.stringify({ W, theme: process.env.THEME || "light", rest, tips }));
  await page.screenshot({ path: (process.env.SCRATCH || ".") + `/panel-${W}-${process.env.THEME || "light"}${process.env.TAG || ""}.png` });
  await browser.close();
})();

};
(modes[process.argv[2]] || (() => { console.log("modes: " + Object.keys(modes).join(", ")); process.exit(2); }))();
