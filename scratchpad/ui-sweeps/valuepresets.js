// I25: the value fields' preset dropdowns (value-field.js), driven by clicks.
// The board's zoom percent and the lightbox's zoom percent each have a chevron
// that opens 25, 50, 75, 100, 150, 200, 400 and Fit. For each: open the list
// (inside the window, every row at least --target-min tall on a phone), pick
// 200%, and the field and the thing it zooms agree; type 150 and Enter, same;
// Fit puts it back and reads a different number; Escape on a typed value puts
// the old one back. The present bar's page field is covered by
// tests/test_present_page_field_1110.py and HISTORY (INBOX 1694 b3); a real
// trackpad's pinch rate cannot be measured without the hardware.
//   LIB=$PWD/scratchpad/ui-sweeps/lib.js BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/valuepresets.js
const { boot } = require(process.env.LIB || "./lib.js");

let failures = 0;
const check = (label, ok, detail) => {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
};

//: The open menu's rows and box, read from the page.
const menuBox = () => {
  const m = document.querySelector(".action-menu:not(.hidden)");
  if (!m) return null;
  const r = m.getBoundingClientRect();
  const rows = [...m.querySelectorAll(".menu-item")].map((i) => ({ t: i.textContent.trim(), h: Math.round(i.getBoundingClientRect().height) }));
  return { l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom), rows, vw: innerWidth, vh: innerHeight };
};

async function pick(page, scope, label) {
  await page.click(`${scope} .value-field-chevron`);
  await page.waitForTimeout(250);
  const box = await page.evaluate(menuBox);
  await page.evaluate((label) => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")].find((i) => i.textContent.trim() === label)?.click(), label);
  await page.waitForTimeout(700);
  return box;
}

(async () => {
  for (const [w, h, phone] of [[1440, 900, false], [390, 844, true]]) {
    const { browser, page } = await boot({ viewport: { width: w, height: h }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
    const errs = [];
    page.on("pageerror", (e) => errs.push(String(e)));

    // The lightbox.
    await page.evaluate(async () => {
      const c = document.createElement("canvas");
      c.width = 1400; c.height = 1400;
      const g = c.getContext("2d");
      g.fillStyle = "#3a7"; g.fillRect(0, 0, 1400, 1400);
      const blob = await new Promise((r) => c.toBlob(r, "image/png"));
      const fd = new FormData();
      fd.append("file", new File([blob], "vp-square.png", { type: "image/png" }));
      const up = await (await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } })).json();
      const rows = await apiJson("/media");
      window.__vp = rows.filter((r) => r.id === up.id);
    });
    await page.evaluate(() => switchTab("library"));
    await page.waitForFunction(() => typeof libraryLightboxItems === "function", null, { timeout: 90000 });
    await page.evaluate(() => openLightbox(libraryLightboxItems(window.__vp), 0));
    await page.waitForTimeout(1500);
    const lb = ".lightbox .lightbox-zoom-label";
    //: Below 600 the lightbox drops the zoom readout by design (INBOX 430: the buttons say what they do and the
    //: picture shows the zoom), so on a phone the field is checked to be absent, not driven.
    if (phone) {
      const vis = await page.evaluate((s) => getComputedStyle(document.querySelector(s)).display, lb);
      check(`${w} lightbox: the zoom readout is dropped on a phone (INBOX 430)`, vis === "none", vis);
    } else {
      const natural = await page.evaluate(() => document.querySelector(".lightbox .lightbox-stage img").naturalWidth);
      const shown = () => page.evaluate((s) => ({ field: document.querySelector(`${s} input`).value, w: Math.round(document.querySelector(".lightbox .lightbox-stage img").getBoundingClientRect().width) }), lb);
      const fit = await shown();
      const box = await pick(page, lb, "200%");
      check(`${w} lightbox: the list opens inside the window`, box && box.l >= 0 && box.r <= box.vw && box.t >= 0 && box.b <= box.vh, JSON.stringify(box && { l: box.l, r: box.r, t: box.t, b: box.b }));
      check(`${w} lightbox: it lists 25 to 400 and Fit`, box && ["25%", "50%", "75%", "100%", "150%", "200%", "400%", "Fit"].every((t) => box.rows.some((r) => r.t === t)));
      if (phone) check(`${w} lightbox: every row is a touch target`, box.rows.every((r) => r.h >= 40), JSON.stringify(box.rows.map((r) => r.h)));
      const at200 = await shown();
      check(`${w} lightbox: 200% reads 200% and the picture is twice its own pixels`, at200.field === "200%" && Math.abs(at200.w - natural * 2) <= 4, JSON.stringify({ at200, natural }));
      await page.fill(`${lb} input`, "150");
      await page.press(`${lb} input`, "Enter");
      await page.waitForTimeout(700);
      const at150 = await shown();
      check(`${w} lightbox: typing 150 and Enter gives 150%`, at150.field === "150%" && Math.abs(at150.w - natural * 1.5) <= 4, JSON.stringify(at150));
      await page.fill(`${lb} input`, "999");
      await page.press(`${lb} input`, "Escape");
      const esc = await shown();
      check(`${w} lightbox: Escape puts the old value back`, esc.field === "150%", JSON.stringify(esc));
      await pick(page, lb, "Fit");
      const refit = await shown();
      check(`${w} lightbox: Fit returns to the first fit`, Math.abs(refit.w - fit.w) <= 4, JSON.stringify({ fit, refit }));
    }
    await page.evaluate(() => document.querySelector(".lightbox .lightbox-close, .lightbox [aria-label='Close']")?.click());
    await page.waitForFunction(() => !document.querySelector(".lightbox"), null, { timeout: 5000 }).catch(() => null);

    // The whiteboard's zoom percent.
    await page.evaluate(() => document.querySelector('[data-tab="library"]').click());
    await page.evaluate(() => document.querySelector('[data-target="library-view-whiteboard"]').click());
    await page.waitForTimeout(1200);
    await page.evaluate(async () => {
      await initWhiteboard();
      const board = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content: "- Atlas\n  - One\n  - Two", name: "vp zoom board" }) });
      await openWhiteboardBoard(board.id);
    });
    await page.waitForTimeout(2200);
    const wb = "#wb-zoom-level";
    const k = () => page.evaluate((s) => ({ field: document.querySelector(`${s} input`)?.value, pct: wbShowZoomLevel.state?.pct }), wb);
    const wbBox = await pick(page, wb, "200%");
    check(`${w} board: the list opens inside the window`, wbBox && wbBox.l >= 0 && wbBox.r <= wbBox.vw && wbBox.t >= 0 && wbBox.b <= wbBox.vh, JSON.stringify(wbBox && { l: wbBox.l, r: wbBox.r, t: wbBox.t, b: wbBox.b }));
    if (phone) check(`${w} board: every row is a touch target`, wbBox.rows.every((r) => r.h >= 40), JSON.stringify(wbBox.rows.map((r) => r.h)));
    const b200 = await k();
    check(`${w} board: 200% reads 200% and the camera is at 200`, b200.field === "200%" && b200.pct === 200, JSON.stringify(b200));
    await page.fill(`${wb} input`, "75");
    await page.press(`${wb} input`, "Enter");
    await page.waitForTimeout(700);
    const b75 = await k();
    check(`${w} board: typing 75 and Enter gives 75%`, b75.field === "75%" && b75.pct === 75, JSON.stringify(b75));
    await pick(page, wb, "Fit");
    const bfit = await k();
    check(`${w} board: Fit moves off 75%`, bfit.pct !== 75, JSON.stringify(bfit));
    check(`${w}: no page error`, errs.length === 0, errs.join("; "));
    await browser.close();
  }
  console.log(failures ? `FAILURES: ${failures}` : "ALL PASS");
  process.exit(failures ? 1 : 0);
})();
