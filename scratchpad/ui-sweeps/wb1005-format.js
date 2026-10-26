// The Format panel (WHITEBOARD_PLAN decision 19): Ctrl+Shift+P opens it on
// the board's right edge; each tab changes the selection, one undo each; the
// numbers round-trip; the arrange buttons are the command table's; Escape
// closes it and gives the focus back. At 390 it spans the board.
//   BASE=http://127.0.0.1:8845 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=1440 node scratchpad/ui-sweeps/wb1005-format.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = Number(process.env.W || 1440);

(async () => {
  const { browser, page, errors, board } = await openBoard({ viewport: { width: W, height: W < 600 ? 844 : 900 } });
  const id = await page.evaluate(async (bid) => {
    const s = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: "M 100 100 L 260 100 L 260 200 L 100 200 Z", shape: "rect", color: "#335599", width: 2, fill: "#ffcc00", label: "Hello" }),
      x: 0, y: 0, z: 1, board_id: bid,
    }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    selectWbItem("sketch", s.id);
    return s.id;
  }, board.id);
  await page.waitForTimeout(500);
  await page.keyboard.press("Control+Shift+P");
  await page.waitForTimeout(600);
  const open = await page.evaluate(() => {
    const p = document.getElementById("wb-format");
    const r = p.getBoundingClientRect();
    const view = document.getElementById("library-view-whiteboard").getBoundingClientRect();
    return {
      shown: !p.classList.contains("hidden") && r.width > 0,
      right: Math.round(view.right - r.right),
      left: Math.round(r.left - view.left),
      focus: document.activeElement?.id,
      scrollX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      chat: !document.getElementById("library-view-whiteboard").classList.contains("hidden"),
    };
  });
  check("Ctrl+Shift+P opens the panel and stays on the board", open.shown && open.chat, open);
  check("the focus is on the open tab", open.focus === "wb-format-tab-style", open);
  check(W < 600 ? "at phone width it spans the board" : "it sits on the board's right edge", W < 600 ? open.left < 20 && open.right < 20 : open.right < 20, open);
  check("no page scroll sideways", open.scrollX <= 0, open);

  // Style: opacity and shadow.
  const style = await page.evaluate(async (sid) => {
    const visible = [...document.querySelectorAll('#wb-format [data-format-panel="style"] [data-fmt]')].filter((r) => !r.hidden).map((r) => r.dataset.fmt);
    const alpha = document.getElementById("wb-fmt-alpha");
    alpha.value = "50";
    alpha.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 700));
    const shadow = document.getElementById("wb-fmt-shadow");
    shadow.click();
    await new Promise((r) => setTimeout(r, 700));
    const g = document.querySelector(`.sketch-group[data-id="${sid}"]`);
    const parsed = JSON.parse(wbFindItem("sketch", sid).data);
    return { visible, alpha: parsed.alpha, shadow: parsed.shadow, drawnAlpha: g.getAttribute("opacity"), filter: getComputedStyle(g).filter };
  }, id);
  check("a shape's Style tab shows line, fill, opacity and shadow", ["stroke", "fill", "alpha", "shadow"].every((f) => style.visible.includes(f)) && !style.visible.includes("route"), style.visible);
  check("opacity 50% is stored and drawn", style.alpha === 0.5 && style.drawnAlpha === "0.5", style);
  check("the shadow is stored and drawn", style.shadow === true && /drop-shadow/.test(style.filter), style);
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(700);
  const afterUndo = await page.evaluate((sid) => JSON.parse(wbFindItem("sketch", sid).data), id);
  check("one Undo takes the shadow off and leaves the opacity", !afterUndo.shadow && afterUndo.alpha === 0.5, afterUndo);

  // Text: size and alignment on the shape's own text.
  await page.click("#wb-format-tab-text");
  await page.waitForTimeout(300);
  const text = await page.evaluate(async (sid) => {
    const size = document.getElementById("wb-fmt-size");
    size.value = "28";
    size.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 700));
    document.querySelector('#wb-fmt-align [data-align="left"]').click();
    await new Promise((r) => setTimeout(r, 700));
    const label = document.querySelector(`.sketch-group[data-id="${sid}"] .sketch-label`);
    const box = wbItemBBox("sketch", wbFindItem("sketch", sid));
    return { size: getComputedStyle(label).fontSize, anchor: label.getAttribute("text-anchor"), x: Number(label.getAttribute("x")), minX: box.minX, pressed: document.querySelector('#wb-fmt-align [data-align="left"]').getAttribute("aria-pressed") };
  }, id);
  check("the shape's text takes a size", text.size === "28px", text);
  check("and sits to the left", text.anchor === "start" && text.x < text.minX + 40 && text.pressed === "true", text);

  // Arrange: numbers round-trip; the command buttons are the table's.
  await page.click("#wb-format-tab-arrange");
  await page.waitForTimeout(300);
  const arrange = await page.evaluate(async (sid) => {
    const x = document.getElementById("wb-fmt-x");
    x.value = "400";
    x.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 800));
    const w = document.getElementById("wb-fmt-w");
    w.value = "200";
    w.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 800));
    const box = wbItemBBox("sketch", wbFindItem("sketch", sid));
    const buttons = [...document.querySelectorAll("#wb-format-commands [data-wb-cmd]")];
    return {
      minX: Math.round(box.minX), width: Math.round(box.maxX - box.minX),
      fieldX: document.getElementById("wb-fmt-x").value,
      buttons: buttons.length,
      named: buttons.every((b) => b.getAttribute("aria-label") && b.title),
      muted: buttons.filter((b) => b.getAttribute("aria-disabled") === "true").map((b) => b.dataset.wbCmd),
    };
  }, id);
  check("X moves the shape to the number", Math.abs(arrange.minX - 400) <= 2 && arrange.fieldX === String(arrange.minX), arrange);
  check("W sizes it to the number", Math.abs(arrange.width - 200) <= 2, arrange);
  check("seventeen named arrange buttons from the table", arrange.buttons === 17 && arrange.named, arrange);
  check("the two-item ones are greyed with one item", arrange.muted.includes("align-left") && arrange.muted.includes("group"), arrange.muted);

  // Keyboard: the tabs walk with the arrows; Escape closes and returns focus.
  await page.click("#wb-format-tab-data");
  await page.keyboard.press("ArrowRight");
  const walked = await page.evaluate(() => document.activeElement?.id);
  check("Right from the last tab (Data) wraps to the first", walked === "wb-format-tab-style", walked);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const closed = await page.evaluate(() => ({ hidden: document.getElementById("wb-format").classList.contains("hidden"), focus: document.activeElement?.id || document.activeElement?.tagName }));
  check("Escape closes the panel and gives the focus to the board", closed.hidden && closed.focus === "whiteboard-container", closed);

  // A map topic says where its style lives.
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
