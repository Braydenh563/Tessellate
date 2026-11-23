// Presenting a board (the owner, 2026-11-22): over the slide the cursor is the
// plain arrow and hides at rest, over the bar it is the normal one; H or the
// bar's caret folds the bar to a handle, kept after a reload; the arrows,
// Space, Page Down and Home page through the frames.
//   BASE=http://127.0.0.1:8781 node scratchpad/ui-sweeps/wbpresent-cursor.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async (bid) => {
    const frame = (x, y, title) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({
      kind: "frame", data: { content: title }, board_id: bid, x, y, width: 240, height: 140, z: 0,
    }) });
    await frame(0, 0, "Intro");
    await frame(320, 0, "Middle");
    await frame(0, 260, "End");
    localStorage.removeItem("wb-present-bar-folded");
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbInstances.container().style.cursor = "crosshair"; // a drawing tool's inline cursor
    wbStartPresenting();
  }, board.id);
  await page.waitForTimeout(800);
  const at = () => page.evaluate(() => document.querySelector("#wb-present-count .wb-present-pick-title")?.textContent?.trim() || "");
  const cursorAt = (x, y) => page.evaluate(([x, y]) => {
    const el = document.elementFromPoint(x, y);
    return { cursor: getComputedStyle(el).cursor, tag: el.tagName + "." + [...el.classList].join(".") };
  }, [x, y]);
  const bar = await page.evaluate(() => { const r = document.getElementById("wb-present-bar").getBoundingClientRect(); return { x: r.x + 8, y: r.y + r.height / 2 }; });
  const pick = await page.evaluate(() => { const r = document.getElementById("wb-present-next").getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
  const slide = await page.evaluate(() => {
    const el = document.querySelector("#whiteboard-container .wb-frame, #whiteboard-container [data-kind='frame'], #whiteboard-container .whiteboard-node") || document.getElementById("whiteboard-container");
    const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  await page.mouse.move(slide.x, slide.y);
  await page.waitForTimeout(100);
  const moving = await cursorAt(slide.x, slide.y);
  check("over the slide, moving: the plain arrow, not an item's hover cursor", moving.cursor === "default", moving);
  await page.waitForTimeout(1900);
  const rest = await cursorAt(slide.x, slide.y);
  check("over the slide, at rest: no cursor", rest.cursor === "none", rest);
  await page.mouse.move(slide.x + 5, slide.y + 5);
  await page.waitForTimeout(100);
  const woke = await cursorAt(slide.x + 5, slide.y + 5);
  check("a move brings it back", woke.cursor === "default", woke);
  await page.mouse.move(pick.x, pick.y);
  await page.waitForTimeout(1900);
  const onBar = await cursorAt(pick.x, pick.y);
  const onBarEdge = await cursorAt(bar.x, bar.y);
  check("over the bar's button, even at rest: the normal cursor", onBar.cursor !== "none", onBar);
  check("over the bar itself: not hidden", onBarEdge.cursor !== "none", onBarEdge);

  const p0 = await at();
  await page.keyboard.press("ArrowRight"); await page.waitForTimeout(450);
  const p1 = await at();
  await page.keyboard.press(" "); await page.waitForTimeout(450);
  const p2 = await at();
  await page.keyboard.press("ArrowLeft"); await page.waitForTimeout(450);
  const p3 = await at();
  await page.keyboard.press("Home"); await page.waitForTimeout(450);
  const p4 = await at();
  await page.keyboard.press("PageDown"); await page.waitForTimeout(450);
  const p5 = await at();
  check("arrows, Space, Home and Page Down page", [p0, p1, p2, p3, p4, p5].map((t) => t.replace(/^of \d+: /, "")).join(",") === "Intro,Middle,End,Middle,Intro,Middle", [p0, p1, p2, p3, p4, p5]);
  const tips = await page.evaluate(() => ["wb-present-prev", "wb-present-next", "wb-present-fold"].map((id) => document.getElementById(id)?.title));
  check("the bar's tooltips name the keys", /Page Up/.test(tips[0]) && /Space/.test(tips[1]) && /\(H\)/.test(tips[2]), tips);

  await page.keyboard.press("h"); await page.waitForTimeout(450);
  const folded = await page.evaluate(() => ({
    bar: getComputedStyle(document.getElementById("wb-present-bar")).display,
    handle: document.getElementById("wb-present-handle").getBoundingClientRect().toJSON(),
    stored: localStorage.getItem("wb-present-bar-folded"),
  }));
  check("H folds the bar to a handle, remembered", folded.bar === "none" && folded.handle.width > 0 && folded.handle.width <= 48 && folded.stored === "1", folded);
  const hc = { x: folded.handle.x + folded.handle.width / 2, y: folded.handle.y + folded.handle.height / 2 };
  await page.mouse.move(hc.x, hc.y); await page.waitForTimeout(1900);
  const onHandle = await cursorAt(hc.x, hc.y);
  check("over the handle: the normal cursor", onHandle.cursor !== "none", onHandle);
  await page.keyboard.press("ArrowRight"); await page.waitForTimeout(450);
  check("paging still works with the bar folded", /End$/.test(await at()), await at());
  await page.keyboard.press("Escape"); await page.waitForTimeout(400);
  const again = await page.evaluate(async () => {
    wbStartPresenting(); await new Promise((r) => setTimeout(r, 600));
    return { bar: document.getElementById("wb-present-bar").classList.contains("hidden"), handle: document.getElementById("wb-present-handle").classList.contains("hidden") };
  });
  const viaStore = await page.evaluate(() => localStorage.getItem("wb-present-bar-folded"));
  check("the fold is kept for the next presentation", viaStore === "1" && again.bar && !again.handle, { again, viaStore });
  await page.evaluate(() => document.getElementById("wb-present-handle")?.click());
  await page.waitForTimeout(400);
  const back = await page.evaluate(() => ({ bar: document.getElementById("wb-present-bar").classList.contains("hidden"), stored: localStorage.getItem("wb-present-bar-folded") }));
  check("the handle brings the bar back", !back.bar && back.stored === "0", back);
  await page.keyboard.press("Escape"); await page.waitForTimeout(300);
  const after = await page.evaluate(() => wbInstances.container().style.cursor);
  check("the tool's own cursor is back after the presentation", after === "crosshair", after);
  check("no page errors", errors.length === 0, errors);
  await browser.close();
  if (!summary()) process.exitCode = 1;
})();
