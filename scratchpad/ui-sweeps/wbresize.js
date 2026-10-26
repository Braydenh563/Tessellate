// wbresize-1026: a grip drag tracks the pointer 1:1, no first-move jump, the
// content fills the box and the arrow grips follow. Sticky, text, picture, picture card.
//   BASE=http://127.0.0.1:8951 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbresize.js
const { openBoard, checker } = require("./wb1005-lib.js");

(async () => {
  const { check, summary } = checker();
  const { browser, page, errors } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const ids = await page.evaluate(async () => {
    const mk = async (kind, x, y, w, h, data) => {
      const o = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind, x, y, width: w, height: h, z: 2, board_id: window.currentBoardId, data }) });
      wbState.objects.push(o);
      return o.id;
    };
    const cv = document.createElement("canvas"); cv.width = 300; cv.height = 200;
    const cx = cv.getContext("2d"); cx.fillStyle = "#3a7"; cx.fillRect(0, 0, 300, 200);
    const blob = await new Promise((r) => cv.toBlob(r, "image/png"));
    const fd = new FormData(); fd.append("file", new File([blob], "p.png", { type: "image/png" }));
    const up = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: fd });
    const out = {
      sticky: await mk("text", 100, 100, 200, 160, { content: "sticky", sticky: true, bg: "#ffe680" }),
      text: await mk("text", 400, 100, 200, 100, { content: "a text card" }),
      image: await mk("image", 700, 100, 240, 160, { url: up.url }),
    };
    const entry = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `random ahh sketch\n\n![sketch](${up.url})`, defer_filing: true }) });
    const node = await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify({ entry_id: entry.id, board_id: window.currentBoardId, x: 1000, y: 100, width: 260, height: 220, z: 1 }) });
    wbState.nodes.push(node);
    await refreshEntries([entry.id]);
    out.card = node.id;
    return out;
  });
  await page.evaluate(() => renderWhiteboardNow());
  await page.waitForTimeout(1500);
  const items = [["sticky", "object", ids.sticky], ["text", "object", ids.text], ["image", "object", ids.image], ["card", "node", ids.card]];
  const sel = (kind) => (kind === "node" ? ".node-card" : ".wb-object");
  const measure = ([kind, id]) => page.evaluate(([kind, id, s]) => {
    const el = document.querySelector(`${s}[data-id="${id}"]`);
    const r = el.getBoundingClientRect();
    const im = el.querySelector("img"); const ir = im && im.getBoundingClientRect();
    const grips = [...document.querySelectorAll("#wb-clone-grips > g")].map((g) => { const b = g.firstChild.getBoundingClientRect(); return { n: g.dataset.dir, cx: b.left + b.width / 2, cy: b.top + b.height / 2 }; });
    return { l: r.left, t: r.top, w: r.width, h: r.height, img: ir && { w: ir.width, h: ir.height }, grips };
  }, [kind, id, sel(kind)]);
  for (const zoom of [1, 0.5]) {
    await page.evaluate((z) => {
      const c = d3.select(document.getElementById("whiteboard-container"));
      c.call(wbZoom.transform, d3.zoomIdentity.translate(60, 60).scale(z));
    }, zoom);
    await page.waitForTimeout(500);
    for (const [name, kind, id] of items) {
      for (const handle of ["se", "e", "nw"]) {
        await page.evaluate(([k, i, z]) => {
          const it = wbFindItem(k, i);
          const c = document.getElementById("whiteboard-container"), r = c.getBoundingClientRect();
          const cx = it.x + it.width / 2, cy = it.y + it.height / 2;
          d3.select(c).call(wbZoom.transform, d3.zoomIdentity.translate(r.width / 2 - cx * z, r.height / 2 - cy * z).scale(z));
          selectWbItem(k, i);
        }, [kind, id, zoom]);
        await page.waitForTimeout(600);
        const b0 = await measure([kind, id]);
        const hd = await page.evaluate(([s, i, h]) => {
          const e = document.querySelector(`${s}[data-id="${i}"] .wb-resize-handle[data-handle="${h}"]`);
          const b = e.getBoundingClientRect();
          return { x: b.left + b.width / 2, y: b.top + b.height / 2 };
        }, [sel(kind), id, handle]);
        await page.mouse.move(hd.x, hd.y);
        await page.mouse.down();
        const sx = handle.includes("e") ? 1 : handle.includes("w") ? -1 : 0, sy = handle.includes("s") ? 1 : handle.includes("n") ? -1 : 0;
        const rows = [];
        for (const d of [20, 40, 60]) {
          await page.mouse.move(hd.x + (sx || 0) * d, hd.y + (sy || 0) * d, { steps: 3 });
          await page.waitForTimeout(100);
          const m = await measure([kind, id]);
          rows.push({ d, dw: +(m.w - b0.w).toFixed(1), dh: +(m.h - b0.h).toFixed(1), m });
        }
        await page.mouse.up();
        await page.waitForTimeout(500);
        // screen pixels: the box delta is the pointer delta (drag distance d), at any zoom
        const want = (d) => d;
        console.log(`${name} z${zoom} ${handle} base ${b0.w.toFixed(0)}x${b0.h.toFixed(0)}`, JSON.stringify(rows.map((r) => [r.d, r.dw, r.dh, r.m.img && [+r.m.img.w.toFixed(0), +r.m.img.h.toFixed(0)]])));
        check(`${name} ${handle} z${zoom}: box delta equals pointer delta`, rows.every((r) => (!sx || Math.abs(Math.abs(r.dw) - want(r.d)) < 3) && (!sy || Math.abs(Math.abs(r.dh) - want(r.d)) < 3)), rows.map((r) => [r.d, r.dw, r.dh]));
        const m = rows[rows.length - 1].m;
        if (m.img) check(`${name} ${handle} z${zoom}: picture fills the box`, m.img.w >= m.w * 0.6 && m.img.h >= m.h * 0.4 && m.img.w <= m.w + 1.5 && m.img.h <= m.h + 1.5, [m.w, m.h, m.img]);
        const fin = await measure([kind, id]);
        if (kind !== "node" || true) {
          const g = fin.grips;
          
          const at = (n) => g.find((x) => x.n === n);
          const tight = g.length === 4 && Math.abs(at("right").cx - (fin.l + fin.w)) < 45 && Math.abs(at("left").cx - fin.l) < 45 && Math.abs(at("down").cy - (fin.t + fin.h)) < 45 && Math.abs(at("up").cy - fin.t) < 90;
          if (g.length) check(`${name} ${handle} z${zoom}: arrows hug the new box sides`, tight, { box: [fin.l, fin.t, fin.w, fin.h], g });
        }
      }
    }
  }
  check("no console errors", errors.length === 0, errors);
  const ok = summary();
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
