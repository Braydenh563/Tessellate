// The lightbox's controls, measured (INBOX 1300 C30, the owner: "Can the
// lightbox controls and elements have a new redesign and upgrade in ui and ux
// usability??"). Before and after numbers for the redesign, per width:
// every visible control's box (hit targets under 24px fail WCAG 2.2 2.5.8),
// its ink against what it sits on, whether the dialog scrolls, the keyboard
// (arrows, + / - / 0, Escape, Tab staying inside), wheel and double-click
// zoom, and at 390 a touch swipe and a two-finger pinch. Numbers only.
//
//   BASE=http://127.0.0.1:8803 SCRATCH=/tmp/mm-design7 THEME=dark \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/lightbox1300.js
const { boot } = require("./lib.js");

const PDF = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R 5 0 R]/Count 2>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 400]/Contents 4 0 R/Resources<<>>>>endobj
4 0 obj<</Length 30>>stream
0 0 1 rg 20 20 260 360 re f
endstream endobj
5 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 400]/Contents 6 0 R/Resources<<>>>>endobj
6 0 obj<</Length 30>>stream
1 0 0 rg 20 20 260 360 re f
endstream endobj
trailer<</Root 1 0 R>>
%%EOF
`;

function measure() {
  const lb = document.querySelector(".lightbox");
  if (!lb) return null;
  const parse = (c) => (c.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  // What a control sits on: its own fill and every ancestor's, composited
  // over the page's background.
  const ground = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c.length >= 3 && (c[3] === undefined || c[3] > 0)) layers.push([c[0], c[1], c[2], c[3] === undefined ? 1 : c[3]]);
      if (c[3] === undefined && c.length >= 3) break;
    }
    let out = [255, 255, 255];
    const body = parse(getComputedStyle(document.body).backgroundColor);
    if (body.length >= 3) out = body.slice(0, 3);
    for (const [r, g, b, a] of layers.reverse()) out = [r * a + out[0] * (1 - a), g * a + out[1] * (1 - a), b * a + out[2] * (1 - a)];
    return out;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && (el.offsetParent !== null || cs.position === "fixed");
  };
  const controls = [...lb.querySelectorAll("button, [role=button], input, select")].filter(visible)
    .filter((el) => !el.closest(".menu-list, .lightbox-info"));
  const rows = controls.map((el) => {
    const r = el.getBoundingClientRect();
    const fg = parse(getComputedStyle(el).color);
    const bg = ground(el);
    const a = lum(fg.slice(0, 3)), b = lum(bg);
    return {
      name: el.getAttribute("aria-label") || el.title || el.textContent.trim().slice(0, 20) || el.className,
      w: Math.round(r.width), h: Math.round(r.height),
      contrast: Math.round(((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)) * 100) / 100,
    };
  });
  const pos = lb.querySelector(".lightbox-position") || lb.querySelector(".lightbox-meta");
  const img = lb.querySelector(".lightbox-stage img");
  const ir = img ? img.getBoundingClientRect() : null;
  return {
    controls: rows.length,
    under24: rows.filter((r) => r.w < 24 || r.h < 24).map((r) => `${r.name} ${r.w}x${r.h}`),
    under44: rows.filter((r) => r.w < 44 || r.h < 44).length,
    minContrast: rows.length ? Math.min(...rows.map((r) => r.contrast)) : 0,
    lowContrast: rows.filter((r) => r.contrast < 3).map((r) => `${r.name} ${r.contrast}`),
    scrolls: lb.scrollHeight > lb.clientHeight + 1,
    overflowX: document.documentElement.scrollWidth > innerWidth,
    position: (pos?.textContent || "").trim(),
    zoom: (lb.querySelector(".lightbox-zoom-label")?.textContent || "").trim(),
    img: ir ? `${Math.round(ir.width)}x${Math.round(ir.height)} at ${Math.round(ir.left)},${Math.round(ir.top)}` : "",
    imgShare: ir ? Math.round((ir.width * ir.height) / (innerWidth * innerHeight) * 100) : 0,
    focusInside: lb.contains(document.activeElement),
    // Picture area under a bar (px2): must be 0 at Fit.
    underBars: ir ? Math.round([...lb.querySelectorAll(".lightbox-topbar, .lightbox-bottom > :not(:empty)")].reduce((sum, el) => {
      const b = el.getBoundingClientRect();
      if (!b.width) return sum;
      return sum + Math.max(0, Math.min(ir.right, b.right) - Math.max(ir.left, b.left)) * Math.max(0, Math.min(ir.bottom, b.bottom) - Math.max(ir.top, b.top));
    }, 0)) : 0,
    names: rows.map((r) => r.name),
    // The controls' layer, for the idle check: lowest opacity among bars.
    chromeOpacity: Math.min(1, ...[...lb.querySelectorAll(".lightbox-topbar, .lightbox-dock, .lightbox-nav, .lightbox-actions, .lightbox-close")]
      .map((el) => Number(getComputedStyle(el).opacity))),
  };
}

(async () => {
  const sizes = (process.env.WIDTHS || "1440,390").split(",").map(Number);
  for (const w of sizes) {
    const phone = w < 600;
    const { browser, page } = await boot({ viewport: { width: w, height: phone ? 844 : 900 }, ...(phone ? { hasTouch: true, isMobile: true } : {}), ...(process.env.REDUCED ? { reducedMotion: "reduce" } : {}) });
    const rows = await page.evaluate(async (pdf) => {
      const listed0 = await apiJson("/media");
      const make = (cw, ch, hue) => new Promise((resolve) => {
        const c = document.createElement("canvas");
        c.width = cw; c.height = ch;
        const g = c.getContext("2d");
        g.fillStyle = `hsl(${hue} 60% 50%)`;
        g.fillRect(0, 0, cw, ch);
        g.fillStyle = "#fff"; g.font = "80px sans-serif"; g.fillText("Tessellate", 40, 120);
        c.toBlob(resolve, "image/png");
      });
      const specs = [["lb1300-wide.png", 2400, 1000, 200], ["lb1300-tall.png", 700, 1600, 20], ["lb1300-square.png", 1400, 1400, 120], ["lb1300-doc.pdf"]];
      const ids = [];
      for (const [name, cw, ch, hue] of specs) {
        const had = listed0.find((r) => r.original_name === name);
        if (had) { ids.push(had.id); continue; }
        const blob = cw ? await make(cw, ch, hue) : new Blob([pdf], { type: "application/pdf" });
        const fd = new FormData();
        fd.append("file", new File([blob], name, { type: blob.type }));
        const r = await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } });
        ids.push((await r.json()).id);
      }
      const listed = await apiJson("/media");
      return ids.map((id) => listed.find((row) => row.id === id)).filter(Boolean);
    }, PDF);
    await page.evaluate(() => switchTab("library"));
    await page.waitForFunction(() => typeof libraryLightboxItems === "function", null, { timeout: 90000 });
    await page.evaluate((rows) => openLightbox(libraryLightboxItems(rows), 0), rows);
    await page.waitForTimeout(1500);
    const out = {};
    out.open = await page.evaluate(measure);
    const center = await page.evaluate(() => { const r = document.querySelector(".lightbox-stage img").getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
    if (!phone) {
      // Idle: a mouse resting on the picture for 4 s, before any key.
      await page.mouse.move(center[0], center[1]);
      await page.mouse.move(center[0] + 5, center[1] + 5);
      await page.waitForTimeout(4000);
      out.idleOpacity = (await page.evaluate(measure)).chromeOpacity;
      await page.mouse.move(center[0] - 40, center[1]); await page.waitForTimeout(400);
      out.revealOpacity = (await page.evaluate(measure)).chromeOpacity;
    }
    // Keyboard.
    await page.keyboard.press("ArrowRight"); await page.waitForTimeout(600);
    out.arrowRight = (await page.evaluate(measure)).position;
    await page.keyboard.press("ArrowLeft"); await page.waitForTimeout(600);
    out.arrowLeft = (await page.evaluate(measure)).position;
    await page.keyboard.press("+"); await page.waitForTimeout(250);
    out.plusKey = (await page.evaluate(measure)).zoom;
    await page.keyboard.press("0"); await page.waitForTimeout(250);
    out.zeroKey = (await page.evaluate(measure)).zoom;
    let escaped = 0;
    for (let i = 0; i < 40; i++) {
      await page.keyboard.press("Tab");
      if (!(await page.evaluate(() => !!document.querySelector(".lightbox")?.contains(document.activeElement)))) escaped += 1;
    }
    out.tabEscapes = escaped;
    // Pointer: wheel about the pointer, double-click toggle.
    const stage = await page.evaluate(() => { const r = document.querySelector(".lightbox-stage img").getBoundingClientRect(); return [r.left + r.width * 0.75, r.top + r.height * 0.5]; });
    if (!phone) {
      await page.mouse.move(stage[0], stage[1]);
      await page.mouse.wheel(0, -200); await page.waitForTimeout(250);
      out.wheel = (await page.evaluate(measure)).zoom;
      // The picture point under the pointer after the zoom: should still be 75% across.
      out.wheelAnchor = await page.evaluate(([x]) => { const r = document.querySelector(".lightbox-stage img").getBoundingClientRect(); return Math.round(((x - r.left) / r.width) * 100); }, stage);
      await page.mouse.dblclick(stage[0], stage[1]); await page.waitForTimeout(300);
      out.dblclick = (await page.evaluate(measure)).zoom;
      await page.mouse.dblclick(stage[0], stage[1]); await page.waitForTimeout(300);
      out.dblclick2 = (await page.evaluate(measure)).zoom;
      // After keys, resting the mouse must not hide anything.
      await page.mouse.move(stage[0] + 5, stage[1] + 5);
      await page.waitForTimeout(4000);
      out.idleAfterKeys = (await page.evaluate(measure)).chromeOpacity;
    } else {
      const cdp = await page.context().newCDPSession(page);
      const touch = async (type, pts) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: pts.map(([x, y], id) => ({ x, y, id })) });
      const before = (await page.evaluate(measure)).position;
      const y = stage[1];
      await touch("touchStart", [[320, y]]);
      for (let x = 300; x >= 80; x -= 20) await touch("touchMove", [[x, y]]);
      await touch("touchEnd", []);
      await page.waitForTimeout(800);
      out.swipe = `${before} -> ${(await page.evaluate(measure)).position}`;
      const cx = 195, cy = y;
      await touch("touchStart", [[cx - 30, cy], [cx + 30, cy]]);
      for (let d = 30; d <= 130; d += 10) await touch("touchMove", [[cx - d, cy], [cx + d, cy]]);
      await touch("touchEnd", []);
      await page.waitForTimeout(400);
      out.pinch = (await page.evaluate(measure)).zoom;
    }
    // The PDF.
    await page.evaluate(() => document.querySelector(".lightbox-stage img") && null);
    await page.keyboard.press("Escape"); await page.waitForTimeout(400);
    out.escapeClosed = await page.evaluate(() => !document.querySelector(".lightbox"));
    await page.evaluate((rows) => openLightbox(libraryLightboxItems(rows), 3), rows);
    await page.waitForTimeout(3000);
    const pdf = await page.evaluate(measure);
    out.pdf = { controls: pdf.controls, under24: pdf.under24, position: pdf.position, scrolls: pdf.scrolls, names: pdf.names };
    console.log(`=== ${w} ${process.env.THEME || "light"}`);
    console.log(JSON.stringify(out, null, 1));
    await page.screenshot({ path: `${process.env.SCRATCH || "."}/shots/lightbox1300-${w}-${process.env.THEME || "light"}.png` });
    await browser.close();
  }
})();
