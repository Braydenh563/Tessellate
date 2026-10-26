// WHITEBOARD_PLAN 1355 item 4: the template picker, measured at 960 and 390, open time and long tasks.
const { openFresh } = require("./wb3-lib.js");
(async () => {
  for (const vp of [{ width: 1440, height: 900 }, { width: 960, height: 700 }, { width: 390, height: 844 }]) {
    const env = await openFresh({ viewport: vp, ...(vp.width < 500 ? { hasTouch: true, isMobile: true } : {}) }); const { page } = env;
    for (const kind of ["board", "map"]) {
      const m = await page.evaluate(async (kind) => {
        const longs = []; const po = new PerformanceObserver((l) => longs.push(...l.getEntries().map((e) => Math.round(e.duration)))); po.observe({ entryTypes: ["longtask"] });
        const t0 = performance.now();
        const p = wbOpenTemplateGallery(kind);
        const dlg = document.getElementById("wb-template-dialog");
        while (!dlg.open) await new Promise((r) => setTimeout(r, 10));
        const open = Math.round(performance.now() - t0);
        await new Promise((r) => setTimeout(r, 200));
        const r = dlg.getBoundingClientRect();
        const list = document.getElementById("wb-template-list");
        const rows = list.querySelectorAll(".doc-template-choice").length;
        const prev = document.getElementById("wb-template-preview").getBoundingClientRect();
        const use = document.getElementById("wb-template-use")?.getBoundingClientRect();
        const out = { open, rows, dlg: [Math.round(r.width), Math.round(r.height)], vw: innerWidth, vh: innerHeight, scrollW: dlg.scrollWidth, clientW: dlg.clientWidth, prevH: Math.round(prev.height), listH: [list.scrollHeight, list.clientHeight], useVisible: use ? use.bottom <= innerHeight && use.top >= 0 : null, longs, domNodes: dlg.querySelectorAll("*").length };
        dlg.querySelector("[data-wb-template-cancel], #wb-template-cancel")?.click();
        if (dlg.open) dlg.close();
        return out;
      }, kind);
      console.log(vp.width, kind, JSON.stringify(m));
    }
    await env.browser.close();
  }
})();
