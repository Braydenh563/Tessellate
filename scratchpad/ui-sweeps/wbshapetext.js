// WHITEBOARD_PLAN decision 12: text inside a shape.
//
// A rectangle is drawn with the R tool and double-clicked: an editor opens
// over it, what is typed is saved on the shape as `label` and drawn centred
// inside it. Then the label is followed through what a shape goes through: a
// move (mid-drag and after), a resize (re-wrapped inside the new width),
// undo and redo, Enter on a selected diamond, Escape to finish, a dark fill
// (the label turns white), the right-click menu's words, a line (which takes
// no text), the export (the text, with a real colour rather than a
// stylesheet variable) and, with THEME=dark, the contrast on the board.
//
//   BASE=http://127.0.0.1:8850 SCRATCH=/tmp/x THEME=light \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbshapetext.js
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
const rgb = (s) => (String(s).match(/[\d.]+/g) || []).slice(0, 3).map(Number);

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(500);
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById("wb-boards-new-template").click());
  await page.waitForTimeout(700);
  await page.fill("#wb-template-name", "Shape text sweep");
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");
  const box = await page.evaluate(() => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: r.left, y: r.top };
  });
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());

  async function draw(key, x, y, w, h) {
    await page.keyboard.press("Escape");
    await page.keyboard.press(key);
    await page.mouse.move(box.x + x, box.y + y);
    await page.mouse.down();
    await page.mouse.move(box.x + x + w, box.y + y + h, { steps: 6 });
    await page.mouse.up();
    await page.waitForTimeout(700);
    await page.keyboard.press("v");
    return page.evaluate(() => wbState.sketches[wbState.sketches.length - 1].id);
  }
  const shapeState = (id) =>
    page.evaluate((sid) => {
      const s = wbState.sketches.find((x) => x.id === sid);
      const data = JSON.parse(s.data);
      const g = document.querySelector(`.sketch-group[data-id="${sid}"]`);
      const path = g.querySelector(".sketch-path").getBoundingClientRect();
      const label = g.querySelector(".sketch-label");
      const lr = label ? label.getBoundingClientRect() : null;
      return {
        label: data.label || null,
        drawn: label ? label.textContent : null,
        lines: label ? label.children.length : 0,
        pathBox: { l: path.left, t: path.top, w: path.width, h: path.height },
        labelBox: lr ? { l: lr.left, t: lr.top, w: lr.width, h: lr.height } : null,
        fill: label ? getComputedStyle(label).fill : null,
      };
    }, id);
  const centreGap = (st) =>
    st.labelBox
      ? Math.max(
          Math.abs(st.labelBox.l + st.labelBox.w / 2 - (st.pathBox.l + st.pathBox.w / 2)),
          Math.abs(st.labelBox.t + st.labelBox.h / 2 - (st.pathBox.t + st.pathBox.h / 2))
        )
      : Infinity;

  // 1. Double-click a rectangle: an editor, focused, over the shape.
  const rect = await draw("r", 300, 200, 220, 120);
  await page.mouse.dblclick(box.x + 410, box.y + 260);
  await page.waitForTimeout(300);
  const editor = await page.evaluate(() => {
    const el = document.querySelector(".wb-shape-label-editor");
    return el ? { focused: document.activeElement === el, editable: el.isContentEditable } : null;
  });
  ok("a double-click on a rectangle opens a text editor in it", Boolean(editor && editor.focused && editor.editable), JSON.stringify(editor));

  // 2. Typed and Enter: saved on the shape, drawn centred in it.
  await page.keyboard.type("Start here");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(600);
  let st = await shapeState(rect);
  ok("Enter saves the text on the shape and draws it", st.label === "Start here" && st.drawn === "Start here", `${st.label} / ${st.drawn}`);
  ok("the text is centred in the shape (within 2px)", centreGap(st) <= 2, `gap ${centreGap(st).toFixed(1)}px`);
  const closed = await page.evaluate(() => !document.querySelector(".wb-shape-label-editor"));
  ok("and the editor is gone", closed);

  // 3. Undo takes it off, redo puts it back.
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(600);
  const undone = (await shapeState(rect)).label;
  await page.keyboard.press("Control+Shift+z");
  await page.waitForTimeout(600);
  const redone = (await shapeState(rect)).label;
  ok("undo takes the text off and redo puts it back", undone === null && redone === "Start here", `${undone} / ${redone}`);

  // 4. A move carries it, mid-drag and after.
  st = await shapeState(rect);
  const sx = st.pathBox.l + 20;
  const sy = st.pathBox.t + st.pathBox.h - 15;
  await page.mouse.move(sx, sy);
  await page.mouse.down();
  await page.mouse.move(sx + 100, sy + 60, { steps: 8 });
  await page.waitForTimeout(100);
  const mid = await shapeState(rect);
  await page.mouse.up();
  await page.waitForTimeout(700);
  const after = await shapeState(rect);
  ok("a drag carries the text with the shape, mid-drag", centreGap(mid) <= 2 && Math.abs(mid.pathBox.l - st.pathBox.l - 100) <= 2, `gap ${centreGap(mid).toFixed(1)}px, moved ${(mid.pathBox.l - st.pathBox.l).toFixed(0)}px`);
  ok("and after it lands", centreGap(after) <= 2, `gap ${centreGap(after).toFixed(1)}px`);

  // 5. A long label wraps inside the shape; a narrower shape wraps it again.
  await page.evaluate(async (sid) => {
    const s = wbState.sketches.find((x) => x.id === sid);
    await wbSaveSketchProps(s, { label: "A much longer label that cannot fit on one line of this box" });
    renderWhiteboardNow();
  }, rect);
  await page.waitForTimeout(400);
  const wide = await shapeState(rect);
  ok("a long label wraps inside the shape's width", wide.lines >= 2 && wide.labelBox.w <= wide.pathBox.w, `${wide.lines} lines, ${wide.labelBox.w.toFixed(0)} in ${wide.pathBox.w.toFixed(0)}`);
  await page.evaluate((sid) => selectWbItem("sketch", sid), rect);
  await page.waitForTimeout(300);
  const grip = await page.evaluate(() => {
    const h = document.querySelector('.wb-sketch-resize-handle[data-handle="e"], .wb-sketch-handle[data-handle="e"]');
    if (!h) return null;
    const r = h.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  if (grip) {
    await page.mouse.move(grip.x, grip.y);
    await page.mouse.down();
    await page.mouse.move(grip.x - 90, grip.y, { steps: 8 });
    await page.waitForTimeout(100);
    const squeezed = await shapeState(rect);
    await page.mouse.up();
    await page.waitForTimeout(700);
    const landed = await shapeState(rect);
    ok("a resize re-wraps it to the new width, mid-drag", squeezed.lines > wide.lines && squeezed.labelBox.w <= squeezed.pathBox.w + 1, `${wide.lines} to ${squeezed.lines} lines, ${squeezed.labelBox.w.toFixed(0)} in ${squeezed.pathBox.w.toFixed(0)}`);
    ok("and keeps it centred after", centreGap(landed) <= 2, `gap ${centreGap(landed).toFixed(1)}px`);
  } else {
    ok("a resize re-wraps it to the new width, mid-drag", false, "no east grip found");
    ok("and keeps it centred after", false, "no east grip found");
  }

  // 6. Enter on a selected diamond, Escape to finish.
  const diamond = await draw("d", 700, 220, 180, 140);
  await page.evaluate((sid) => {
    selectWbItem("sketch", sid);
    document.getElementById("whiteboard-container").focus();
  }, diamond);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(250);
  await page.keyboard.type("Yes?");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  const dia = await shapeState(diamond);
  ok("Enter on a selected diamond types into it, Escape ends", dia.label === "Yes?" && centreGap(dia) <= 2, `${dia.label}, gap ${centreGap(dia).toFixed(1)}px`);

  // 7. A dark fill turns the label white.
  await page.evaluate(async (sid) => {
    const s = wbState.sketches.find((x) => x.id === sid);
    await wbSaveSketchProps(s, { fill: "#1d3557", fillOpacity: 1 });
    renderWhiteboardNow();
  }, diamond);
  await page.waitForTimeout(300);
  const dark = await shapeState(diamond);
  ok("on a dark fill the label is white", rgb(dark.fill).join(",") === "255,255,255", dark.fill);

  // 8. The menu says it in words; a line takes no text.
  await page.evaluate((sid) => selectWbItem("sketch", sid), rect);
  const rb = await shapeState(rect);
  await page.mouse.click(rb.pathBox.l + 10, rb.pathBox.t + 10, { button: "right" });
  await page.waitForTimeout(300);
  const words = await page.evaluate(() =>
    [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")].map((b) => b.textContent.trim())
  );
  ok("the shape's right-click menu offers to edit its text", words.includes("Edit the text"), words.join(", "));
  await page.keyboard.press("Escape");
  const line = await draw("l", 300, 520, 240, 0.5);
  const lb = await page.evaluate((sid) => {
    const r = document.querySelector(`.sketch-group[data-id="${sid}"] .sketch-path`).getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }, line);
  await page.mouse.dblclick(lb.x, lb.y);
  await page.waitForTimeout(300);
  const noEditor = await page.evaluate(() => !document.querySelector(".wb-shape-label-editor"));
  ok("a line takes no text", noEditor);
  await page.keyboard.press("Escape");

  // 9. The export carries the text with a real colour.
  const svg = await page.evaluate(() => wbBuildExportSvg("board").svg);
  const textTag = (svg.match(/<text[^>]*>(?:(?!<\/text>).)*Yes\?/) || [""])[0];
  ok("the export carries the text, painted without a stylesheet", Boolean(textTag) && /fill="rgb/.test(textTag) && !/var\(/.test(textTag), textTag.slice(0, 160));

  // 10. Contrast against the board, in whichever theme this run is.
  const contrast = await page.evaluate((sid) => {
    const label = document.querySelector(`.sketch-group[data-id="${sid}"] .sketch-label`);
    return { ink: getComputedStyle(label).fill, ground: getComputedStyle(document.getElementById("whiteboard-container")).backgroundColor };
  }, rect);
  const cr = ratio(rgb(contrast.ink), rgb(contrast.ground));
  ok("an unfilled shape's text reads on the board (4.5:1)", cr >= 4.5, `${cr.toFixed(2)}:1, ${contrast.ink} on ${contrast.ground}`);

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`${pass} ok, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
