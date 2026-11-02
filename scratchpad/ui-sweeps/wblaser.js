// canvasdepth: the laser pointer while presenting, measured.
//   BASE=http://127.0.0.1:8850 W=1440 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wblaser.js
const { openFresh, checker } = require("./cdlib.js");
(async () => {
  const W = Number(process.env.W || 1440);
  const { browser, page, errors, phone } = await openFresh({ width: W });
  const { check, summary } = checker();
  await page.evaluate(async () => { await wbCreateObject("frame", { content: "Slide" }, 0, 0, 480, 320); wbStartPresenting(); });
  await page.waitForTimeout(800);
  const btn = await page.evaluate(() => { const b = document.getElementById("wb-present-laser"); const r = b?.getBoundingClientRect(); return b ? { w: r.width, h: r.height, pressed: b.getAttribute("aria-pressed") } : null; });
  const min = phone ? 44 : 24;
  check("the bar has the laser button", btn && btn.pressed === "false" && btn.w >= min && btn.h >= min, btn);
  await page.keyboard.press("l");
  const H = phone ? 844 : 900;
  for (let i = 0; i < 20; i++) await page.mouse.move(W * 0.3 + i * 10, H * 0.5 + i * 3);
  const on = await page.evaluate(() => {
    const dots = [...document.querySelectorAll("#wb-laser-layer .wb-laser-dot")];
    const last = dots[dots.length - 1]?.getBoundingClientRect();
    return { n: dots.length, pressed: document.getElementById("wb-present-laser").getAttribute("aria-pressed"), cursor: getComputedStyle(document.getElementById("whiteboard-container")).cursor, last: last && { x: last.x + last.width / 2, y: last.y + last.height / 2 }, z: getComputedStyle(document.getElementById("wb-laser-layer")).zIndex, sketches: wbState.sketches.length };
  });
  check("L turns it on and the pointer leaves dots", on.pressed === "true" && on.n >= 10 && on.cursor === "none", on);
  check("the last dot sits on the pointer", on.last && Math.abs(on.last.x - (W * 0.3 + 190)) <= 2 && Math.abs(on.last.y - (H * 0.5 + 57)) <= 2, on.last);
  check("nothing is drawn on the board", on.sketches === 0, on.sketches);
  await page.waitForTimeout(1000);
  const faded = await page.evaluate(() => document.querySelectorAll("#wb-laser-layer .wb-laser-dot").length);
  check("the trail fades away by itself", faded === 0, faded);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const off = await page.evaluate(() => ({ layer: Boolean(document.getElementById("wb-laser-layer")), cls: document.getElementById("whiteboard-container").classList.contains("wb-laser-on") }));
  check("ending the presentation turns it off", !off.layer && !off.cls, off);
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
