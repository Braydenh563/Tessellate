// WHITEBOARD_PLAN decision 7's other half: the quick-sketch pad and the
// whiteboard are two renderers (a `<canvas>` in app.js, SVG paths in
// whiteboard.js) and they are meant to be one highlighter.
//
//   BASE=http://127.0.0.1:8941 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     NODE_PATH=/opt/node22/lib/node_modules timeout 110 node \
//     scratchpad/ui-sweeps/sketchparity.js
//
// `sketchhighlighter.js` beside it is the other half, INBOX 265's gate: that
// one pad stroke is even along its length and does not darken where it
// crosses itself. This one is about the two surfaces agreeing.
//
// What it measures, in both surfaces, with the same ink at the same size:
//   · the numbers each renderer uses (alpha, width multiplier, clamp, joins,
//     blend), read out of the page rather than off the source;
//   · two crossing strokes, sampled per pixel with pngpixel.py: bare paper,
//     one pass, two passes. A highlighter that multiplies darkens on the
//     second pass; one that only alphas barely moves.
// The two surfaces are compared as numbers, which is the only way to say
// "the same" about a canvas and an SVG.
//
// THEME=dark works (lib.js reads it); the pad's paper is its own white canvas
// in both themes, so only the board's numbers move.
const { boot, OUT, newBoard: libNewBoard } = require("./lib.js");
const { execSync } = require("child_process");

const [VW, VH] = (process.env.VIEWPORT || "1440x900").split("x").map(Number);
const INK = "#eab308"; // the pad's own yellow swatch, set on the board too

let pass = 0;
let fail = 0;
function ok(name, good, detail) {
  if (good) { pass += 1; console.log(`OK   ${name}${detail ? `  ${detail}` : ""}`); }
  else { fail += 1; console.log(`FAIL ${name}${detail ? `  ${detail}` : ""}`); }
}

function lum(line) {
  const m = line.match(/\((\d+), (\d+), (\d+)\)/);
  return m ? 0.299 * Number(m[1]) + 0.587 * Number(m[2]) + 0.114 * Number(m[3]) : null;
}

// Three samples out of one 200x200 clip centred on the crossing: the crossing
// itself, one stroke alone, and paper.
function sample(shotPath) {
  const read = execSync(`python3 ${__dirname}/../pngpixel.py ${shotPath} 100 100 40 100 100 40 20 20`)
    .toString().trim().split("\n").slice(1);
  const [cross, across, down, bare] = read.map(lum);
  return { cross, across, down, bare };
}

async function crossStrokes(page, cx, cy) {
  await page.mouse.move(cx - 120, cy);
  await page.mouse.down();
  for (let i = -110; i <= 120; i += 10) await page.mouse.move(cx + i, cy);
  await page.mouse.up();
  await page.waitForTimeout(400);
  await page.mouse.move(cx, cy - 120);
  await page.mouse.down();
  for (let i = -110; i <= 120; i += 10) await page.mouse.move(cx, cy + i);
  await page.mouse.up();
  await page.waitForTimeout(700);
}

async function newBoard(page, name) {
  await libNewBoard(page, name, 'board');
  await page.keyboard.press("Escape");
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });

  // --- the quick-sketch pad -------------------------------------------------
  await page.click('[data-tab="notes"]');
  await page.waitForTimeout(400);
  // The pad lives in the Capture section, which is not the Notes tab's
  // default one (`showNotesSection`): #sketch-btn is in the DOM but inside a
  // hidden card until this sub-tab is picked.
  await page.click('#notes-subtabs [data-section="capture"]');
  await page.waitForTimeout(500);
  await page.click("#sketch-btn");
  await page.waitForTimeout(700);
  await page.click("#sketch-tool-highlighter");
  await page.click(`.sketch-color[data-color="${INK}"]`);
  await page.waitForTimeout(200);

  const padNumbers = await page.evaluate(() => {
    const t = (typeof HIGHLIGHTER_STYLE !== "undefined" && HIGHLIGHTER_STYLE) || null;
    return {
      shared: !!t,
      table: t ? JSON.parse(JSON.stringify(t)) : null,
      alpha: t ? t.alpha : null,
      composite: typeof highlighterBlend === "function" ? highlighterBlend(false) : null,
      join: t ? t.lineJoin : null,
      mult: t ? t.widthMultiplier : null,
      penSize: typeof sketchPen !== "undefined" ? sketchPen.size : null,
      tool: typeof sketchTool !== "undefined" ? sketchTool : null,
      width: typeof highlighterWidth === "function" && typeof sketchPen !== "undefined" ? highlighterWidth(sketchPen.size) : null,
    };
  });

  const padBox = await page.evaluate(() => document.getElementById("sketch-canvas").getBoundingClientRect().toJSON());
  const pcx = Math.round(padBox.x + padBox.width / 2);
  const pcy = Math.round(padBox.y + padBox.height / 2);
  await crossStrokes(page, pcx, pcy);
  const padShot = `${OUT}/sketch-highlighter-pad.png`;
  await page.screenshot({ path: padShot, clip: { x: pcx - 100, y: pcy - 100, width: 200, height: 200 } });
  const pad = sample(padShot);
  // What the canvas actually drew, read out of the pixels rather than off the
  // context: `sketchPaintHighlighter` paints through a save/restore pair, so
  // the context's own state after a stroke is the default one and says
  // nothing about what was painted. The ink's own alpha is the measurement.
  const padUsed = await page.evaluate(() => {
    const c = document.getElementById("sketch-canvas");
    const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    let minX = 1e9, maxX = -1, minY = 1e9, maxY = -1;
    for (let y = 0; y < c.height; y++) {
      for (let x = 0; x < c.width; x++) {
        const a = d[(y * c.width + x) * 4 + 3];
        if (a > 5) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }
    // One pass, not two: the far left of the horizontal arm, well clear of
    // the vertical stroke that crosses it in the middle, where the alpha is
    // 1-(1-a)^2 by design.
    let maxAlpha = 0;
    for (let x = minX + 4; x < minX + 24; x++) {
      for (let y = 0; y < c.height; y++) maxAlpha = Math.max(maxAlpha, d[(y * c.width + x) * 4 + 3]);
    }
    return {
      alpha: Math.round((maxAlpha / 255) * 100) / 100,
      width: typeof highlighterWidth === "function" ? highlighterWidth(sketchPen.size) : null,
      cap: HIGHLIGHTER_STYLE.lineCap,
      join: HIGHLIGHTER_STYLE.lineJoin,
      // Where the ink landed against where the pointer went: the two strokes
      // cross at the canvas's middle, so the inked box is centred on it when
      // the painter and the pointer agree.
      centre: [Math.round((minX + maxX) / 2), Math.round((minY + maxY) / 2)],
      want: [Math.round(c.width / 2), Math.round(c.height / 2)],
    };
  });
  console.log(`pad   numbers ${JSON.stringify(padNumbers)}`);
  console.log(`pad   context ${JSON.stringify(padUsed)}`);
  console.log(`pad   luminance: crossing ${pad.cross?.toFixed(1)}, across ${pad.across?.toFixed(1)}, down ${pad.down?.toFixed(1)}, bare ${pad.bare?.toFixed(1)}`);
  // Closing a pad with strokes on it asks first, which is right and which
  // silently ate the rest of this sweep the first time (a `.confirm-overlay`
  // intercepting every later click).
  await page.click("#sketch-close");
  await page.waitForTimeout(600);
  if (await page.$(".confirm-overlay")) {
    await page.click(".confirm-overlay .confirm-actions button:last-child");
    await page.waitForTimeout(600);
  }

  // --- the whiteboard -------------------------------------------------------
  await newBoard(page, "Highlighter parity");
  await page.click('#wb-tool-group [data-tool="highlighter"]');
  await page.waitForTimeout(200);
  await page.evaluate((ink) => {
    const sw = document.getElementById("wb-rail-ink");
    sw.value = ink;
    sw.dispatchEvent(new Event("change", { bubbles: true }));
  }, INK);
  await page.waitForTimeout(300);
  const boardBox = await page.evaluate(() => document.getElementById("whiteboard-container").getBoundingClientRect().toJSON());
  const bcx = Math.round(boardBox.x + boardBox.width / 2);
  const bcy = Math.round(boardBox.y + boardBox.height / 2);
  await crossStrokes(page, bcx, bcy);
  const boardShot = `${OUT}/sketch-highlighter-board.png`;
  await page.screenshot({ path: boardShot, clip: { x: bcx - 100, y: bcy - 100, width: 200, height: 200 } });
  const board = sample(boardShot);
  const boardNumbers = await page.evaluate(() => {
    const t = (typeof HIGHLIGHTER_STYLE !== "undefined" && HIGHLIGHTER_STYLE) || null;
    const paths = [...document.querySelectorAll(".sketch-path")];
    return {
      shared: !!t,
      alpha: t ? t.alpha : null,
      min: t ? t.minWidth : null,
      max: t ? t.maxWidth : null,
      wanted: typeof wbHighlighterBlend === "function" ? wbHighlighterBlend() : null,
      strokes: paths.length,
      blend: paths.map((el) => el.style.mixBlendMode),
      opacity: paths.map((el) => el.getAttribute("stroke-opacity")),
      width: paths.map((el) => el.getAttribute("stroke-width")),
      cap: paths.map((el) => getComputedStyle(el).strokeLinecap),
      join: paths.map((el) => getComputedStyle(el).strokeLinejoin),
      theme: document.documentElement.getAttribute("data-theme"),
    };
  });
  console.log(`board numbers ${JSON.stringify(boardNumbers)}`);
  console.log(`board luminance: crossing ${board.cross?.toFixed(1)}, across ${board.across?.toFixed(1)}, down ${board.down?.toFixed(1)}, bare ${board.bare?.toFixed(1)}`);

  // --- the checks -----------------------------------------------------------
  ok("one shared definition is on the page", padNumbers.shared && boardNumbers.shared,
    padNumbers.table ? JSON.stringify(padNumbers.table) : "no HIGHLIGHTER_STYLE");
  ok("both renderers use the same alpha", padNumbers.alpha !== null && padNumbers.alpha === boardNumbers.alpha
      && Number(boardNumbers.opacity[0]) === padNumbers.alpha && Math.abs(padUsed.alpha - padNumbers.alpha) <= 0.02,
    `table ${padNumbers.alpha}, pad ink ${padUsed.alpha}, board stroke-opacity ${boardNumbers.opacity.join(",")}`);
  ok("the pad's ink lands where the pointer went",
    Math.abs(padUsed.centre[0] - padUsed.want[0]) <= 3 && Math.abs(padUsed.centre[1] - padUsed.want[1]) <= 3,
    `inked centre ${padUsed.centre.join(",")}, pointer centre ${padUsed.want.join(",")}`);
  ok("the board's blend is the one the mode asks for",
    boardNumbers.blend.length > 0 && boardNumbers.blend.every((b) => b === boardNumbers.wanted),
    `mode ${boardNumbers.theme}, blend ${boardNumbers.blend.join(",")}, wanted ${boardNumbers.wanted}`);
  ok("the pad's stroke tints rather than covers", pad.across !== null && pad.across < pad.bare - 5 && pad.across > 40,
    `bare ${pad.bare?.toFixed(1)}, one pass ${pad.across?.toFixed(1)}`);
  // "Darker" is the wrong word for half of this. A multiplying highlighter
  // darkens the second pass and a screening one lightens it; what both mean
  // is that a second pass reads as a second pass, so the check is that the
  // crossing moves further from the paper than one stroke did, in whichever
  // direction the blend goes.
  const secondPass = (m) => {
    if (m.cross === null || m.across === null || m.bare === null) return { good: false, by: null };
    const one = Math.abs(m.across - m.bare);
    const two = Math.abs(m.cross - m.bare);
    return { good: two > one + 1 && Math.abs(m.down - m.bare) > 1, by: two - one };
  };
  const padSecond = secondPass(pad);
  const boardSecond = secondPass(board);
  ok("a second pass reads as a second pass on the pad", padSecond.good,
    `paper ${pad.bare?.toFixed(1)}, one pass ${pad.across?.toFixed(1)}, crossing ${pad.cross?.toFixed(1)}, second pass worth ${padSecond.by?.toFixed(1)}`);
  ok("a second pass reads as a second pass on the board", boardSecond.good,
    `paper ${board.bare?.toFixed(1)}, one pass ${board.across?.toFixed(1)}, crossing ${board.cross?.toFixed(1)}, second pass worth ${boardSecond.by?.toFixed(1)}`);
  ok("both stroke widths come from one multiplier",
    padUsed.width !== null && boardNumbers.width.length > 0
      && Number(boardNumbers.width[0]) >= boardNumbers.min && Number(boardNumbers.width[0]) <= boardNumbers.max,
    `pad ${padUsed.width}px, board ${boardNumbers.width.join(",")}px, clamp ${boardNumbers.min}-${boardNumbers.max}`);
  ok("both ends and joins match", padUsed.cap === "square" && padUsed.join === "round"
      && boardNumbers.cap.every((c) => c === padUsed.cap) && boardNumbers.join.every((j) => j === padUsed.join),
    `table ${padUsed.cap}/${padUsed.join}, board ${boardNumbers.cap.join(",")}/${boardNumbers.join.join(",")}`);

  // The mode changing under an open board. The blend is an inline style (the
  // export clones these nodes), so it does not follow a stylesheet: this is
  // the check that something re-applies it, with no re-render in between.
  const flipped = await page.evaluate(async () => {
    const before = [...document.querySelectorAll(".sketch-path")].map((el) => el.style.mixBlendMode);
    const mode = document.documentElement.dataset.mode;
    applyThemeChoice(mode === "dark" ? "light" : "dark");
    await new Promise((r) => setTimeout(r, 600));
    return {
      before,
      after: [...document.querySelectorAll(".sketch-path")].map((el) => el.style.mixBlendMode),
      mode: document.documentElement.dataset.mode,
      wanted: wbHighlighterBlend(),
    };
  });
  ok("the blend follows a mode change on an open board",
    flipped.after.length > 0 && flipped.after.every((b) => b === flipped.wanted) && flipped.after[0] !== flipped.before[0],
    `${flipped.before.join(",")} then ${flipped.after.join(",")} in ${flipped.mode}`);

  console.log(`\n${pass}/${pass + fail} checks pass at ${VW}x${VH} (${process.env.THEME || "light"})`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
