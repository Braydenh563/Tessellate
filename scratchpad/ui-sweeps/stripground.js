// The note strip's ground against its surface's (INBOX 616): the strip is
// sticky, so it needs an opaque ground, and at rest that ground must read as
// the surface it sits on, not a band. Screenshots the edit form and reads
// the pixel in the strip's empty middle and in the title row's empty right.
// Prints both colours and their largest channel difference; exit 1 over 6.
//   BASE=http://127.0.0.1:8877 THEME=dark node stripground.js
const { boot } = require("./lib.js");
const [vw, vh] = (process.env.VIEWPORT || "1440x900").split("x").map(Number);
(async () => {
  const { page, browser } = await boot({ viewport: { width: vw, height: vh } });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(1200);
  await page.evaluate(async () => {
    // Its own note when the data dir has none (the seed it was written on had one).
    let e = allEntries.find((x) => (x.content || "").includes("Edit form probe 1"));
    if (!e) {
      e = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "Edit form probe 1" }) });
      await loadEntries?.();
    }
    await openNoteEditor(e.id);
  });
  await page.waitForTimeout(2000);
  // Off the field, so the surface draws its resting edge, not the focus ring.
  await page.evaluate(() => document.activeElement?.blur());
  const pts = await page.evaluate(() => {
    const li = document.querySelector("#entry-edit-content").closest("li");
    li.scrollIntoView({ block: "center" });
    const stripEl = li.querySelector(".note-edit-toolbar");
    const strip = stripEl.getBoundingClientRect();
    const title = li.querySelector(".note-edit-title").getBoundingClientRect();
    // An empty spot is one where the strip itself is the element under the
    // point: at 390 the strip is full of controls and a fixed offset from its
    // tools landed on an icon (diff 44 against the title row). The middle of
    // the widest run of such points along the strip's centre line is sampled.
    const y = Math.round(strip.top + strip.height / 2);
    let best = null, run = null;
    for (let x = Math.ceil(strip.left) + 2; x < strip.right - 2; x += 2) {
      const bare = document.elementFromPoint(x, y) === stripEl;
      if (bare && !run) run = { from: x, to: x };
      if (bare && run) run.to = x;
      if (!bare && run) { if (!best || run.to - run.from > best.to - best.from) best = run; run = null; }
    }
    if (run && (!best || run.to - run.from > best.to - best.from)) best = run;
    const sx = best ? Math.round((best.from + best.to) / 2) : Math.round(strip.right - 60);
    return { strip: [sx, y], bare: best ? best.to - best.from : 0, title: [Math.round(title.right - 20), Math.round(title.top + title.height / 2)] };
  });
  // Decoded in the page: no PNG library in the sandbox, and the browser has one.
  const buf = await page.screenshot();
  const [a, b] = await page.evaluate(async ({ src, pts }) => {
    const img = new Image();
    img.src = src;
    await img.decode();
    const c = new OffscreenCanvas(img.width, img.height);
    const g = c.getContext("2d");
    g.drawImage(img, 0, 0);
    return [pts.strip, pts.title].map(([x, y]) => [...g.getImageData(x, y, 1, 1).data.slice(0, 3)]);
  }, { src: "data:image/png;base64," + buf.toString("base64"), pts });
  const out = { strip: a, title: b, bareRun: pts.bare, diff: Math.max(...a.map((v, i) => Math.abs(v - b[i]))) };
  console.log(`stripground ${vw} ${process.env.THEME || "light"}: ${JSON.stringify(out)}`);
  await browser.close();
  process.exit(out.diff > 6 ? 1 : 0);
})();
