// The lightbox, the owner 2026-09-24: "the image clashes with the side left
// and right arrow buttons on the lightbox", an info card 680px wide in one
// screenshot and 1200px in another, and "the description that was auto
// generated said it was typed by hand".
//
// Per width (1440, 1184, 390): three pictures (wide, tall, square) opened in
// the Library's own lightbox. For each, at Fit and zoomed in twice: the
// visible part of the picture (its box cut to the stage's scrollport)
// against both arrows' boxes, which must not overlap. Then the info card's
// width on each picture (a short and a long caption), which must be one
// width, and its left and right edges against the toolbar's. And the byline
// on the picture whose caption the app wrote.
//
//   BASE=http://127.0.0.1:8785 SCRATCH=/tmp/mm-mapfix THEME=light \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/lightboxfit.js
const { boot } = require("./lib.js");

const WIDTHS = [[1440, 900], [1184, 800], [390, 844]];
let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

function measure() {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width };
  };
  const lb = document.querySelector(".lightbox");
  const img = lb.querySelector(".lightbox-stage img");
  const stage = box(lb.querySelector(".lightbox-stage"));
  const pic = box(img);
  // What of the picture can be seen: its box cut to the stage's scrollport.
  const seen = pic && stage ? {
    l: Math.max(pic.l, stage.l), r: Math.min(pic.r, stage.r),
    t: Math.max(pic.t, stage.t), b: Math.min(pic.b, stage.b),
  } : null;
  const overlap = (a, b) => (a && b)
    ? Math.max(0, Math.min(a.r, b.r) - Math.max(a.l, b.l)) * Math.max(0, Math.min(a.b, b.b) - Math.max(a.t, b.t))
    : 0;
  const prev = box(lb.querySelector(".lightbox-prev"));
  const next = box(lb.querySelector(".lightbox-next"));
  const info = lb.querySelector(".lightbox-info");
  return {
    seen, prev, next,
    hitPrev: Math.round(overlap(seen, prev)), hitNext: Math.round(overlap(seen, next)),
    info: info && !info.classList.contains("hidden") ? box(info) : null,
    actions: lb.querySelector(".lightbox-actions")?.offsetParent ? box(lb.querySelector(".lightbox-actions")) : null,
    byline: [...lb.querySelectorAll(".lightbox-byline")].map((e) => e.textContent.trim()).filter(Boolean),
    natural: img ? [img.naturalWidth, img.naturalHeight] : null,
  };
}

(async () => {
  for (const [w, h] of WIDTHS) {
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    const rows = await page.evaluate(async () => {
      const make = (cw, ch, hue) => new Promise((resolve) => {
        const c = document.createElement("canvas");
        c.width = cw; c.height = ch;
        const g = c.getContext("2d");
        g.fillStyle = `hsl(${hue} 60% 50%)`;
        g.fillRect(0, 0, cw, ch);
        c.toBlob(resolve, "image/png");
      });
      const out = [];
      const specs = [["lbfit-wide.png", 2400, 1000, 200], ["lbfit-tall.png", 700, 1600, 20], ["lbfit-square.png", 1400, 1400, 120]];
      for (const [name, cw, ch, hue] of specs) {
        const fd = new FormData();
        fd.append("file", new File([await make(cw, ch, hue)], name, { type: "image/png" }));
        const r = await fetch("/media/upload", {
          method: "POST", body: fd,
          headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() },
        });
        out.push(await r.json());
      }
      await apiJson(`/media/${out[0].id}/caption`, { method: "POST", body: JSON.stringify({ text: "Part of the mind map \"Plans\", exported from MemoryMap.", source: "app" }) });
      await apiJson(`/media/${out[1].id}/caption`, { method: "POST", body: JSON.stringify({ text: "A long description typed by hand. ".repeat(14) }) });
      const listed = await apiJson("/media");
      return out.map((o) => listed.find((row) => row.id === o.id));
    });
    // The Library's own item builder lives in library.js, which loads with
    // the tab.
    await page.evaluate(() => switchTab("library"));
    await page.waitForFunction(() => typeof libraryLightboxItems === "function", null, { timeout: 90000 });
    await page.evaluate((rows) => openLightbox(libraryLightboxItems(rows), 0), rows);
    await page.waitForTimeout(1500);
    const widths = [];
    for (let i = 0; i < 3; i++) {
      const fit = await page.evaluate(measure);
      const label = `${w} picture ${i + 1} (${fit.natural})`;
      check(`${label}: at Fit, clear of both arrows`, fit.hitPrev === 0 && fit.hitNext === 0,
        `overlap prev ${fit.hitPrev}px2 next ${fit.hitNext}px2, seen ${Math.round(fit.seen.l)}..${Math.round(fit.seen.r)}, arrows end ${Math.round(fit.prev.r)} and start ${Math.round(fit.next.l)}`);
      if (fit.info) widths.push(Math.round(fit.info.w));
      if (fit.info && fit.actions) {
        console.log(`  ${label}: info ${Math.round(fit.info.l)}..${Math.round(fit.info.r)} (${Math.round(fit.info.w)}), toolbar ${Math.round(fit.actions.l)}..${Math.round(fit.actions.r)} (${Math.round(fit.actions.w)})`);
        check(`${label}: info card aligned with the toolbar`,
          Math.abs(fit.info.l - fit.actions.l) <= 1 && Math.abs(fit.info.r - fit.actions.r) <= 1);
      }
      if (i === 0) {
        check(`${w}: the app's own caption says who wrote it`, fit.byline.some((b) => /Written by (MemoryMap|Tessellate)/.test(b))
          && !fit.byline.some((b) => /typed by hand/.test(b)), JSON.stringify(fit.byline));
      }
      // Zoomed in twice, then scrolled to each end of the picture.
      await page.evaluate(() => {
        const zoomIn = [...document.querySelectorAll(".lightbox .lightbox-action")].find((b) => b.title.startsWith("Zoom in"));
        zoomIn.click(); zoomIn.click();
      });
      await page.waitForTimeout(300);
      for (const end of ["start", "end"]) {
        await page.evaluate((end) => {
          const s = document.querySelector(".lightbox-stage");
          s.scrollLeft = end === "start" ? 0 : s.scrollWidth;
        }, end);
        await page.waitForTimeout(150);
        const z = await page.evaluate(measure);
        check(`${label}: zoomed, scrolled to the ${end}, clear of both arrows`, z.hitPrev === 0 && z.hitNext === 0,
          `overlap prev ${z.hitPrev}px2 next ${z.hitNext}px2`);
      }
      await page.evaluate(() => {
        [...document.querySelectorAll(".lightbox .lightbox-action")].find((b) => b.title.startsWith("Back to fit")).click();
        document.querySelector(".lightbox-next").click();
      });
      await page.waitForTimeout(1200);
    }
    check(`${w}: the info card is one width on every picture`, new Set(widths).size <= 1, `widths ${widths.join(", ")}`);
    await page.screenshot({ path: `${process.env.SCRATCH || "."}/shots/lightboxfit-${w}-${process.env.THEME || "light"}.png` });
    await browser.close();
  }
  console.log(failures ? `${failures} failed` : "all passed");
  process.exit(failures ? 1 : 0);
})();
