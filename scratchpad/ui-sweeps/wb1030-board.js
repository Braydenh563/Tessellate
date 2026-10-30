// Audit 1028 board rows B31 and B6, measured: what a board switch leaves
// pending (B31) and how many listeners a board switch or a re-init adds (B6).
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1030-board.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const other = await page.evaluate(async () => apiJson("/whiteboard/boards", {
    method: "POST", body: JSON.stringify({ name: "wb1030 b " + Date.now(), type: "board" }),
  }));
  // B31: queue frames and timers on this board, then switch.
  const pend = await page.evaluate(async (id) => {
    wbMarkMoving(); wbQueueReveal(); wbScheduleRender(); wbScheduleStickyDates(); wbScheduleCull();
    const before = { moving: document.getElementById("wb-canvas-view").classList.contains("wb-moving"), reveal: wbRevealTimer, render: wbRenderFrame, cull: wbCullFrame, dates: wbStickyDates.timer };
    const p = openWhiteboardBoard(id);
    const during = { moving: document.getElementById("wb-canvas-view").classList.contains("wb-moving"), reveal: wbRevealTimer, render: wbRenderFrame, cull: wbCullFrame, dates: wbStickyDates.timer };
    await p;
    return { before, during };
  }, other.id);
  console.log("B31 pending", JSON.stringify(pend));
  check("B31: nothing queued survives the switch call", !pend.during.moving && !pend.during.reveal && !pend.during.dates, pend);
  await page.waitForTimeout(800);
  // B6: listeners added by a board switch and by a second initWhiteboard.
  const counts = await page.evaluate(async ([a, b]) => {
    const n = { window: 0, document: 0, other: 0 };
    const orig = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (...args) {
      if (this === window) n.window++; else if (this === document) n.document++; else n.other++;
      return orig.apply(this, args);
    };
    await openWhiteboardBoard(a);
    const switchAdds = { ...n };
    n.window = n.document = n.other = 0;
    await initWhiteboard();
    const reinitAdds = { ...n };
    EventTarget.prototype.addEventListener = orig;
    return { switchAdds, reinitAdds };
  }, [board.id, other.id]);
  console.log("B6 listeners", JSON.stringify(counts));
  check("B6: re-init adds no window or document listener", counts.reinitAdds.window === 0 && counts.reinitAdds.document === 0, counts);
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
