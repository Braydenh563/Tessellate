// WHITEBOARD_PLAN 1355 item 6: line spacing, letter spacing, fill opacity apply, persist, undo.
const { openFresh } = require("./wb3-lib.js");
(async () => {
  const env = await openFresh(); const { page } = env;
  const bid = env.board.id;
  const ids = await page.evaluate(async (bid) => {
    const t = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", board_id: bid, x: 100, y: 100, width: 240, height: 140, data: { content: "one two three four five six seven" } }) });
    const s = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: bid, x: 0, y: 0, data: JSON.stringify({ type: "rect", d: "M400 100 L620 100 L620 240 L400 240 Z", color: "#2563eb", fill: "#93c5fd", width: 2, label: "alpha beta gamma delta" }) }) });
    return { t: t.id, s: s.id };
  }, bid);
  await env.open(bid);
  const res = []; const check = (l, ok, d = "") => { res.push(ok); console.log(ok ? "PASS" : "FAIL", l, d); };
  const open = async (kind, id) => {
    await page.evaluate(([k, i]) => selectWbItem(k, i), [kind, id]); await page.waitForTimeout(300);
    if (await page.evaluate(() => document.getElementById("wb-format").classList.contains("hidden"))) await page.click("#wb-format-btn");
    await page.waitForTimeout(300);
  };
  const setNum = async (sel, v) => { await page.fill(sel, String(v)); await page.dispatchEvent(sel, "change"); await page.waitForTimeout(600); };
  // format panel open time + long tasks
  await page.evaluate(() => { window.__lt = []; new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push(e.duration))).observe({ entryTypes: ["longtask"] }); });
  const t0 = Date.now(); await open("object", ids.t); console.log("format panel open ms", Date.now() - t0, "longtasks", await page.evaluate(() => JSON.stringify(window.__lt)));
  await page.click("#wb-format-tab-text");
  const vis = await page.evaluate(() => ["wb-fmt-lh", "wb-fmt-ls"].map((i) => { const r = document.getElementById(i).getBoundingClientRect(); return r.width > 0 && r.height > 0; }));
  check("text rows visible for a text object", vis.every(Boolean), JSON.stringify(vis));
  const read = () => page.evaluate((id) => { const o = wbState.objects.find((o) => o.id === id); const el = document.querySelector(`[data-object-id="${id}"] .wb-text, [data-id="${id}"] .wb-text`); return { lh: o.data.line_height, ls: o.data.letter_spacing }; }, ids.t);
  await setNum("#wb-fmt-lh", 1.8); await setNum("#wb-fmt-ls", 3);
  let r = await read(); check("text lh/ls applied to state", r.lh === 1.8 && r.ls === 3, JSON.stringify(r));
  const css = await page.evaluate((id) => { for (const e of document.querySelectorAll("#whiteboard-container *")) { const s = e.style; if (s.lineHeight === "1.8" && s.letterSpacing === "3px") return true; } return false; });
  check("text paints line-height 1.8 + letter-spacing 3px", css);
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(500);
  r = await read(); check("one undo reverts letter spacing only", r.lh === 1.8 && !r.ls, JSON.stringify(r));
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(500);
  r = await read(); check("second undo reverts line spacing", !r.lh && !r.ls, JSON.stringify(r));
  await page.evaluate(() => wbRedo()); await page.evaluate(() => wbRedo()); await page.waitForTimeout(600);
  await env.open(bid);
  r = await read(); check("text spacing persists after reload", r.lh === 1.8 && r.ls === 3, JSON.stringify(r));
  // shape
  await open("sketch", ids.s); await page.click("#wb-format-tab-text");
  await setNum("#wb-fmt-lh", 2); await setNum("#wb-fmt-ls", 2);
  const sh = () => page.evaluate((id) => { const p = JSON.parse(wbState.sketches.find((s) => s.id === id).data); return { lh: p.label_lh, ls: p.label_ls, fo: p.fillOpacity }; }, ids.s);
  let q = await sh(); check("shape label lh/ls stored", q.lh === 2 && q.ls === 2, JSON.stringify(q));
  const lab = await page.evaluate((id) => { const g = document.querySelector(`[data-sketch-id="${id}"]`) || document.querySelector(`[data-id="${id}"]`); const l = [...document.querySelectorAll("#whiteboard-container .wb-shape-label, #whiteboard-container [data-lh]")].find((e) => e.dataset.lh === "2"); return l ? { lh: l.dataset.lh, ls: l.style.letterSpacing } : null; }, ids.s);
  check("shape label paints spacing", !!lab && lab.ls === "2px", JSON.stringify(lab));
  await page.click("#wb-format-tab-style");
  const fa = await page.evaluate(() => { const r = document.getElementById("wb-fmt-fillalpha").getBoundingClientRect(); return r.width > 0; });
  check("fill opacity slider visible on a filled shape", fa);
  await page.evaluate(() => { const e = document.getElementById("wb-fmt-fillalpha"); e.value = 40; e.dispatchEvent(new Event("change", { bubbles: true })); }); await page.waitForTimeout(600);
  q = await sh(); check("fill opacity stored 0.4", q.fo === 0.4, JSON.stringify(q));
  const paint = await page.evaluate((id) => { const el = [...document.querySelectorAll("#whiteboard-container [fill-opacity], #whiteboard-container [style*='opacity']")].find((e) => /0\.4/.test(e.getAttribute("fill-opacity") || e.style.fillOpacity || "")); return !!el; }, ids.s);
  check("fill opacity paints", paint);
  await page.evaluate(() => wbUndo()); await page.waitForTimeout(500);
  q = await sh(); check("undo restores fill opacity", q.fo === undefined || q.fo === 1, JSON.stringify(q));
  await page.evaluate(() => wbRedo()); await page.waitForTimeout(600);
  await env.open(bid);
  q = await sh(); check("shape props persist after reload", q.fo === 0.4 && q.lh === 2 && q.ls === 2, JSON.stringify(q));
  console.log(res.every(Boolean) ? "ALL PASS" : "SOME FAIL"); await env.browser?.close?.(); process.exit(res.every(Boolean) ? 0 : 1);
})();
