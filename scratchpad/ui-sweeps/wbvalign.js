// The owner, 2026-10-10: "there's no way to vertically centre text". A tall
// text box and a tall rectangle with a few words each; the Format panel's
// Vertical row is pressed (top, middle, bottom) and the words' box is
// measured against the item's: its middle against the item's middle, its
// top and foot against the item's edges.
//   BASE=http://127.0.0.1:8783 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbvalign.js
const { boot } = require("./lib.js");
let fails = 0, passes = 0;
const check = (ok, what) => { console.log(`${ok ? "PASS" : "FAIL"}  ${what}`); ok ? passes++ : fails++; };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  const board = await page.evaluate(async () => {
    await initWhiteboard();
    return apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "Valign " + Date.now() }) });
  });
  await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, board.id);
  await page.waitForTimeout(1000);
  const ids = await page.evaluate(async (b) => {
    const text = await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "Two words" }, board_id: b, x: 300, y: 260, z: 1, width: 220, height: 260 }) });
    const rect = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 1, data: JSON.stringify({ d: "M 700 260 L 920 260 L 920 520 L 700 520 Z", shape: "rect", color: "#333333", width: 2, label: "Two words" }) }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return { text: text.id, rect: rect.id };
  }, board.id);
  await page.waitForTimeout(600);
  const measure = (kind, id) => page.evaluate(({ kind, id }) => {
    if (kind === "object") {
      const box = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect();
      const content = document.querySelector(`.wb-object[data-id="${id}"] .wb-text-content`);
      const range = document.createRange();
      range.selectNodeContents(content);
      const r = range.getBoundingClientRect();
      return { top: r.top - box.top, bottom: box.bottom - r.bottom, mid: (r.top + r.bottom) / 2 - (box.top + box.bottom) / 2 };
    }
    const box = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-path`).getBoundingClientRect();
    const r = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-label`).getBoundingClientRect();
    return { top: r.top - box.top, bottom: box.bottom - r.bottom, mid: (r.top + r.bottom) / 2 - (box.top + box.bottom) / 2 };
  }, { kind, id });
  for (const [kind, id, name] of [["object", ids.text, "text box"], ["sketch", ids.rect, "rectangle"]]) {
    await page.evaluate(({ kind, id }) => { selectWbItem(kind, id); wbFormatOpen?.(); }, { kind, id });
    await page.waitForTimeout(300);
    await page.evaluate(() => { wbFmtState.fmtTab = "text"; wbFormatSync(); });
    await page.waitForTimeout(200);
    const visible = await page.evaluate(() => { const r = document.getElementById("wb-fmt-valign")?.getBoundingClientRect(); return Boolean(r && r.width); });
    check(visible, `${name}: the Format panel's Text tab shows a Vertical row`);
    const start = await measure(kind, id);
    console.log(`  ${name} before: ${JSON.stringify(start)}`);
    for (const at of ["middle", "bottom", "top"]) {
      await page.click(`#wb-fmt-valign [data-valign="${at}"]`);
      await page.waitForTimeout(700);
      const m = await measure(kind, id);
      const ok = at === "middle" ? Math.abs(m.mid) <= 2 : at === "bottom" ? m.bottom <= 16 && m.top > 100 : m.top <= 16 && m.bottom > 100;
      check(ok, `${name}: ${at} (words ${Math.round(m.top)}px from the top, ${Math.round(m.bottom)}px from the foot, middle off by ${Math.round(m.mid)})`);
      const pressed = await page.evaluate((at) => document.querySelector(`#wb-fmt-valign [data-valign="${at}"]`)?.getAttribute("aria-pressed"), at);
      check(pressed === "true", `${name}: ${at} reads as pressed`);
    }
  }
  console.log(`${passes}/${passes + fails}`);
  await browser.close();
  process.exit(fails ? 1 : 0);
})();
