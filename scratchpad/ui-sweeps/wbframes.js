// WHITEBOARD_PLAN decision 14: frames.
//
// F picks the frame tool; a drag draws a frame that size, below everything,
// titled "Frame 1". A rectangle and a sticky drawn inside it and a sticky
// outside it, then the frame dragged by its title: the two inside travel with
// it by the same amount, the one outside stays, and it all survives a reload.
// One Ctrl+Z puts all three back. Ctrl held moves the frame alone. A press
// inside the frame selects what is under it (the frame's inside lets the
// pointer through). The title renames in place (Enter keeps, Escape puts it
// back). Delete takes the frame and leaves what it held. The export draws the
// frame and its title. The edge and the title are measured for contrast on
// the board. The Insert menu's Frame row picks the tool; a map's F does not.
//
//   BASE=http://127.0.0.1:8800 SCRATCH=/tmp/x THEME=light VW=1440 VH=900 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbframes.js
const { boot } = require("./lib.js");

let pass = 0;
let fail = 0;
function ok(label, good, detail) {
  if (good) pass += 1;
  else fail += 1;
  console.log(`${good ? "OK  " : "FAIL"} ${label}${detail ? "  " + detail : ""}`);
}

function lum([r, g, b]) {
  const f = (c) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);

(async () => {
  const phone = VW < 600;
  const { browser, page } = await boot({
    viewport: { width: VW, height: VH },
    ...(phone ? { hasTouch: true, isMobile: true } : {}),
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.evaluate(() => document.querySelector('[data-tab="library"]').click());
  await page.waitForTimeout(500);
  await page.evaluate(() => document.querySelector('[data-target="library-view-whiteboard"]').click());
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById("wb-boards-new-template").click());
  await page.waitForTimeout(700);
  await page.fill("#wb-template-name", `Frames sweep ${Date.now()}`);
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");
  const box = await page.evaluate(() => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  });
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());

  // Phone: the rail is not where a finger goes first; the Insert menu is.
  // The frame tool is picked through it, which is also the check that the row
  // exists and works.
  if (phone) {
    const picked = await page.evaluate(() => {
      document.querySelector('#wb-insert-menu [data-wb-insert="frame"]').click();
      return window.currentTool;
    });
    ok("phone: the Insert menu's Frame row picks the frame tool", picked === "frame", picked);
    await page.evaluate(() => {
      const r = document.getElementById("whiteboard-container").getBoundingClientRect();
      const ev = new MouseEvent("click", { bubbles: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 });
      document.getElementById("whiteboard-container").dispatchEvent(ev);
    });
    await page.waitForTimeout(1200);
    const made = await page.evaluate(() => {
      const f = (wbState.objects || []).find((o) => o.kind === "frame");
      const el = f && document.querySelector(`.wb-object[data-id="${f.id}"]`);
      const r = el?.getBoundingClientRect();
      const t = el?.querySelector(".wb-frame-title")?.getBoundingClientRect();
      return f ? { w: f.width, h: f.height, title: f.data.content, inView: r && r.left >= 0 && r.right <= innerWidth + 1, titleH: t?.height, cls: el.className } : null;
    });
    await page.screenshot({ path: `${process.env.SCRATCH || "."}/wbframes-phone-${process.env.THEME || "light"}.png` });
    ok("phone: a tap drops a frame titled Frame 1, inside the screen", made && made.title === "Frame 1" && made.inView, JSON.stringify(made));
    ok("phone: its title is drawn", made && made.titleH > 8, String(made?.titleH));
    ok("phone: no page errors", errors.length === 0, errors.join(" | "));
    console.log(`\n${pass} passed, ${fail} failed`);
    await browser.close();
    process.exit(fail ? 1 : 0);
  }

  // 1. F picks the tool, and the rail shows it held.
  await page.keyboard.press("f");
  const held = await page.evaluate(() => ({
    tool: window.currentTool,
    active: document.querySelector('#wb-tool-group [data-tool="frame"]')?.classList.contains("active"),
    cursor: getComputedStyle(document.getElementById("whiteboard-container")).cursor,
  }));
  ok("F picks the frame tool and the rail shows it", held.tool === "frame" && held.active, JSON.stringify(held));

  // 2. A drag draws the frame that size.
  const fx = 300, fy = 200, fw = 500, fh = 340;
  await page.mouse.move(box.x + fx, box.y + fy);
  await page.mouse.down();
  await page.mouse.move(box.x + fx + fw, box.y + fy + fh, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(1000);
  const frame = await page.evaluate(() => {
    const f = (wbState.objects || []).find((o) => o.kind === "frame");
    const k = d3.zoomTransform(document.getElementById("whiteboard-container")).k;
    return f ? { id: f.id, w: Math.round(f.width * k), h: Math.round(f.height * k), z: f.z, title: f.data.content, tool: window.currentTool,
      selected: wbMultiSelection.has(`object:${f.id}`) || document.querySelector(`.wb-object[data-id="${f.id}"]`)?.classList.contains("wb-selected") } : null;
  });
  ok("a drag draws a frame of that size, titled Frame 1, back on Select", frame && Math.abs(frame.w - fw) <= 2 && Math.abs(frame.h - fh) <= 2 && frame.title === "Frame 1" && frame.tool === "select",
    JSON.stringify(frame));
  const handles = await page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    return { resize: el.querySelectorAll(".wb-resize-handle").length, rotate: el.querySelectorAll(".wb-rotate-handle").length };
  }, frame.id);
  ok("a frame has its eight resize handles and no rotate grip", handles.resize === 8 && handles.rotate === 0, JSON.stringify(handles));

  // 3. Things inside and outside it.
  await page.keyboard.press("Escape");
  await page.keyboard.press("r");
  await page.mouse.move(box.x + fx + 40, box.y + fy + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + fx + 160, box.y + fy + 120, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(800);
  await page.keyboard.press("Escape");
  await page.keyboard.press("n");
  await page.mouse.click(box.x + fx + 330, box.y + fy + 200);
  await page.waitForTimeout(1000);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.keyboard.press("n");
  await page.mouse.click(box.x + fx + fw + 250, box.y + fy + 100);
  await page.waitForTimeout(1000);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.keyboard.press("v");
  const ids = await page.evaluate((frameId) => {
    const stickies = wbState.objects.filter((o) => o.kind === "text").sort((a, b) => a.x - b.x);
    return { rect: wbState.sketches[wbState.sketches.length - 1].id, inside: stickies[0].id, outside: stickies[1].id, frame: frameId };
  }, frame.id);
  const where = () =>
    page.evaluate((ids) => {
      const o = (id) => wbState.objects.find((x) => x.id === id);
      const s = wbState.sketches.find((x) => x.id === ids.rect);
      const b = wbItemBBox("sketch", s);
      return { frame: [o(ids.frame).x, o(ids.frame).y], inside: [o(ids.inside).x, o(ids.inside).y], outside: [o(ids.outside).x, o(ids.outside).y], rect: [Math.round(b.minX), Math.round(b.minY)] };
    }, ids);
  const before = await where();
  // A sticky is on top of the frame: its z is above.
  const stack = await page.evaluate((ids) => {
    const z = (id) => Number(getComputedStyle(document.querySelector(`.wb-object[data-id="${id}"]`)).zIndex);
    return { frame: z(ids.frame), sticky: z(ids.inside) };
  }, ids);
  ok("the frame stacks below what is placed in it", stack.frame < stack.sticky, JSON.stringify(stack));

  // 4. A press inside the frame's empty middle reaches the board, not the frame.
  const hit = await page.evaluate(({ x, y }) => {
    const el = document.elementFromPoint(x, y);
    return el ? (el.closest(".wb-object") ? "object" : el.id || el.tagName) : null;
  }, { x: box.x + fx + 420, y: box.y + fy + 300 });
  ok("the frame's inside lets the pointer through to the board", hit !== "object", hit);

  // 5. Drag by the title.
  const title = await page.evaluate((id) => {
    const r = document.querySelector(`.wb-object[data-id="${id}"] .wb-frame-title`).getBoundingClientRect();
    return { x: r.left + Math.min(20, r.width / 2), y: r.top + r.height / 2, h: r.height };
  }, frame.id);
  ok("the title is drawn above the frame", title.y < box.y + fy && title.h > 8, JSON.stringify(title));
  await page.mouse.move(title.x, title.y);
  await page.mouse.down();
  await page.mouse.move(title.x + 60, title.y + 30, { steps: 4 });
  await page.mouse.move(title.x + 100, title.y + 60, { steps: 6 });
  await page.waitForTimeout(100);
  const mid = await page.evaluate((ids) => {
    const tr = (id) => document.querySelector(`.wb-object[data-id="${id}"]`).style.transform;
    return { frame: tr(ids.frame), inside: tr(ids.inside) };
  }, ids);
  await page.mouse.up();
  await page.waitForTimeout(1200);
  const after = await where();
  const k = await page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).k);
  const moved = (a, b) => [Math.round(b[0] - a[0]), Math.round(b[1] - a[1])];
  const fMove = moved(before.frame, after.frame);
  ok("the title drags the frame", fMove[0] !== 0 && fMove[1] !== 0, `${fMove} at k=${k}`);
  ok("what is inside travels by the same amount",
    JSON.stringify(moved(before.inside, after.inside)) === JSON.stringify(fMove) && JSON.stringify(moved(before.rect, after.rect)) === JSON.stringify(fMove),
    `sticky ${moved(before.inside, after.inside)}, rect ${moved(before.rect, after.rect)}`);
  ok("what is outside stays", JSON.stringify(before.outside) === JSON.stringify(after.outside));
  ok("mid-drag, the sticky inside is already moving", mid.inside && mid.inside.includes("translate"), JSON.stringify(mid));

  // 6. Saved: a fresh read of the board says the same.
  const saved = await page.evaluate(async ({ ids, boardId }) => {
    const st = await apiJson(`/whiteboard/?board_id=${boardId}`);
    const o = (id) => st.objects.find((x) => x.id === id);
    return { frame: [o(ids.frame).x, o(ids.frame).y], inside: [o(ids.inside).x, o(ids.inside).y] };
  }, { ids, boardId: await page.evaluate(() => window.currentBoardId) });
  ok("the move is saved for the frame and what it carried",
    JSON.stringify(saved.frame) === JSON.stringify(after.frame) && JSON.stringify(saved.inside) === JSON.stringify(after.inside), JSON.stringify(saved));

  // 7. One undo puts all three back.
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(1200);
  const undone = await where();
  ok("one Ctrl+Z puts the frame and what it carried back",
    JSON.stringify(undone.frame) === JSON.stringify(before.frame) && JSON.stringify(undone.inside) === JSON.stringify(before.inside) && JSON.stringify(undone.rect) === JSON.stringify(before.rect),
    JSON.stringify(undone));

  // 8. Ctrl held moves the frame alone.
  const title2 = await page.evaluate((id) => {
    const r = document.querySelector(`.wb-object[data-id="${id}"] .wb-frame-title`).getBoundingClientRect();
    return { x: r.left + Math.min(20, r.width / 2), y: r.top + r.height / 2 };
  }, frame.id);
  await page.keyboard.down("Control");
  await page.mouse.move(title2.x, title2.y);
  await page.mouse.down();
  await page.mouse.move(title2.x - 40, title2.y - 30, { steps: 6 });
  await page.mouse.up();
  await page.keyboard.up("Control");
  await page.waitForTimeout(1000);
  const alone = await where();
  ok("Ctrl and drag moves the frame alone",
    JSON.stringify(alone.frame) !== JSON.stringify(undone.frame) && JSON.stringify(alone.inside) === JSON.stringify(undone.inside), JSON.stringify(alone));
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(1000);

  // 9. Rename in place.
  const titlePos = await page.evaluate((id) => {
    const r = document.querySelector(`.wb-object[data-id="${id}"] .wb-frame-title`).getBoundingClientRect();
    return { x: r.left + Math.min(20, r.width / 2), y: r.top + r.height / 2 };
  }, frame.id);
  await page.mouse.dblclick(titlePos.x, titlePos.y);
  await page.waitForTimeout(300);
  const editing = await page.evaluate(() => document.activeElement?.classList.contains("wb-frame-title") && document.activeElement.isContentEditable);
  ok("double-clicking the title edits it", editing);
  await page.keyboard.type("Ideas");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(800);
  const renamed = await page.evaluate((id) => ({
    data: wbState.objects.find((o) => o.id === id).data.content,
    shown: document.querySelector(`.wb-object[data-id="${id}"] .wb-frame-title`).textContent,
    tool: window.currentTool,
  }), frame.id);
  ok("Enter keeps the new name, and the letters typed picked no tool", renamed.data === "Ideas" && renamed.shown === "Ideas" && renamed.tool === "select", JSON.stringify(renamed));
  await page.mouse.dblclick(titlePos.x, titlePos.y);
  await page.waitForTimeout(300);
  await page.keyboard.type("Nope");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  const kept = await page.evaluate((id) => wbState.objects.find((o) => o.id === id).data.content, frame.id);
  ok("Escape puts the old name back", kept === "Ideas", kept);

  // 10. Contrast on the board: the edge (a UI component, 3:1) and the title (text, 4.5:1).
  const paint = await page.evaluate((id) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    const bg = getComputedStyle(document.getElementById("whiteboard-container")).backgroundColor;
    const probe = document.createElement("canvas").getContext("2d");
    const flat = (c) => { probe.clearRect(0, 0, 1, 1); probe.fillStyle = bg; probe.fillRect(0, 0, 1, 1); probe.fillStyle = c; probe.fillRect(0, 0, 1, 1); return [...probe.getImageData(0, 0, 1, 1).data].slice(0, 3); };
    return { edge: flat(getComputedStyle(el).borderTopColor), title: flat(getComputedStyle(el.querySelector(".wb-frame-title")).color), bg: flat(bg) };
  }, frame.id);
  const edgeRatio = ratio(paint.edge, paint.bg);
  const titleRatio = ratio(paint.title, paint.bg);
  ok("the frame's edge reads on the board (3:1)", edgeRatio >= 3, edgeRatio.toFixed(2));
  ok("the frame's title reads on the board (4.5:1)", titleRatio >= 4.5, titleRatio.toFixed(2));

  // 11. The export draws it.
  const svg = await page.evaluate(() => wbBuildExportSvg("board").svg);
  if (process.env.DEBUG) console.log(svg.slice(0, 1200));
  ok("the export draws the frame and its title", /Ideas/.test(svg) && /<rect[^>]*fill="none"[^>]*stroke=/.test(svg) && !/var\(--/.test(svg));

  // 12. The agent reads it.
  const read = await page.evaluate(async () => {
    const st = await apiJson(`/whiteboard/?board_id=${window.currentBoardId}`);
    return st.objects.filter((o) => o.kind === "frame").map((o) => o.data.content);
  });
  ok("the board's state names the frame", read.includes("Ideas"), JSON.stringify(read));

  // 13. Delete takes the frame and leaves what it held.
  await page.mouse.click(titlePos.x, titlePos.y);
  await page.waitForTimeout(300);
  const selectedFrame = await page.evaluate((id) => document.querySelector(`.wb-object[data-id="${id}"]`).classList.contains("wb-selected"), frame.id);
  ok("a click on the title selects the frame", selectedFrame);
  const bar = await page.evaluate(() =>
    ["ink", "caps", "stroke", "fill", "text", "arrange", "order"].filter((g) => {
      const el = document.querySelector(`#wb-context [data-wb-ctx="${g}"]`);
      return el && !el.classList.contains("hidden") && el.getBoundingClientRect().width > 0;
    })
  );
  ok("a selected frame's bar offers no style or order controls", bar.length === 0, JSON.stringify(bar));
  await page.keyboard.press("Delete");
  await page.waitForTimeout(1000);
  const left = await page.evaluate((ids) => ({
    frame: wbState.objects.some((o) => o.id === ids.frame),
    inside: wbState.objects.some((o) => o.id === ids.inside),
    rect: wbState.sketches.some((s) => s.id === ids.rect),
  }), ids);
  ok("Delete takes the frame and leaves what it held", !left.frame && left.inside && left.rect, JSON.stringify(left));

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(2);
});
