// WHITEBOARD_PLAN section 7's unsettled question, measured: should the context bar
// pin to the top of the canvas at phone width, or keep floating above the
// selection?
//
//   BASE=http://127.0.0.1:8941 VIEWPORT=390x844 SCRATCH=/tmp/mm-wbfab \
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers NODE_PATH=/opt/node22/lib/node_modules \
//     timeout 115 node scratchpad/ui-sweeps/wbcontextphone.js
//
// The five kinds the plan names (an image, a line, a shape, a text box, an
// arrow), each selected in turn, and for each one the four numbers that decide
// it: the bar's own box, how much of the canvas it covers, whether it covers
// the thing it is editing, and whether it stays inside the canvas. The bar
// moves with the selection when it floats, so the same five are measured with
// the selection near the top of the board and near the bottom.
//
// Run it at 1440x900 too: the desktop placement must not change.
const { boot } = require("./lib.js");

const [VW, VH] = (process.env.VIEWPORT || "390x844").split("x").map(Number);

let pass = 0;
let fail = 0;
function ok(name, good, detail) {
  if (good) { pass += 1; console.log(`OK   ${name}${detail ? `  ${detail}` : ""}`); }
  else { fail += 1; console.log(`FAIL ${name}${detail ? `  ${detail}` : ""}`); }
}

async function newBoard(page, name) {
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(500);
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById("wb-boards-new").click());
  await page.waitForTimeout(700);
  await page.fill("#wb-template-name", name);
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  await newBoard(page, "Context bar at phone width");

  // The five kinds, twice over: one set high on the board and one set low, so
  // the floating bar is measured both where it fits above the selection and
  // where it has to drop below it.
  const made = await page.evaluate(async () => {
    const board = window.currentBoardId;
    const post = async (path, body) => (await api(path, { method: "POST", body: JSON.stringify(body) })).json();
    const sketch = async (data, x, y) => post("/whiteboard/sketches", { board_id: board, data: JSON.stringify(data), x, y });
    const set = async (suffix, y) => ({
      [`image${suffix}`]: ["object", (await post("/whiteboard/objects", { kind: "image", board_id: board, x: 40, y, width: 160, height: 120, data: { url: "/media/none.png" } })).id],
      [`line${suffix}`]: ["sketch", (await sketch({ d: `M 40 ${y + 160} L 240 ${y + 200}`, color: "#112233", width: 3, shape: "line" }, 0, 0)).id],
      [`shape${suffix}`]: ["sketch", (await sketch({ d: `M 40 ${y + 240} L 240 ${y + 240} L 240 ${y + 340} L 40 ${y + 340} Z`, color: "#112233", width: 4, shape: "rect" }, 0, 0)).id],
      [`text${suffix}`]: ["object", (await post("/whiteboard/objects", { kind: "text", board_id: board, x: 40, y: y + 380, width: 200, height: 90, data: { content: "hello" } })).id],
      [`arrow${suffix}`]: ["sketch", (await sketch({ d: `M 40 ${y + 500} L 240 ${y + 540}`, color: "#112233", width: 3, shape: "arrow" }, 0, 0)).id],
    });
    const all = { ...(await set("-high", 40)), ...(await set("-low", 240)) };
    await fetchWhiteboardState();
    renderWhiteboard();
    return all;
  });
  await page.waitForTimeout(800);

  const rows = [];
  for (const [label, [kind, id]] of Object.entries(made)) {
    const row = await page.evaluate(([k, i]) => {
      wbMultiSelection.clear();
      selectWbItem(k, i);
      const bar = document.getElementById("wb-context");
      const canvas = document.getElementById("whiteboard-container").getBoundingClientRect();
      const b = bar.getBoundingClientRect();
      const item = document.querySelector(WB_SELECTOR_BY_KIND[k](i))?.getBoundingClientRect();
      const overlap = (a, c) => {
        if (!a || !c) return 0;
        const w = Math.max(0, Math.min(a.right, c.right) - Math.max(a.left, c.left));
        const h = Math.max(0, Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top));
        return Math.round(w * h);
      };
      return {
        hidden: bar.classList.contains("hidden"),
        anchor: bar.dataset.wbAnchor || "float",
        bar: { w: Math.round(b.width), h: Math.round(b.height), x: Math.round(b.left), y: Math.round(b.top) },
        canvas: { w: Math.round(canvas.width), h: Math.round(canvas.height), x: Math.round(canvas.left), y: Math.round(canvas.top) },
        coverPct: Math.round((b.width * b.height) / (canvas.width * canvas.height) * 1000) / 10,
        overSelection: overlap(b, item),
        // The two pieces of chrome that live over the same canvas: a bar that
        // sits on either is a bar you cannot use, and at phone width the rail
        // is a full-width row along the bottom.
        overRail: overlap(b, document.getElementById("wb-tool-group")?.getBoundingClientRect()),
        overTopBar: overlap(b, document.getElementById("wb-topbar")?.getBoundingClientRect()),
        inside: b.left >= canvas.left - 1 && b.right <= canvas.right + 1 && b.top >= canvas.top - 1 && b.bottom <= canvas.bottom + 1,
      };
    }, [kind, id]);
    rows.push([label, row]);
    console.log(`${label.padEnd(12)} ${row.anchor.padEnd(6)} ${row.bar.w}x${row.bar.h} at ${row.bar.x},${row.bar.y}  covers ${row.coverPct}% of the canvas, over the selection ${row.overSelection}px2, over the rail ${row.overRail}px2, over the top bar ${row.overTopBar}px2, inside ${row.inside}`);
  }

  const shown = rows.filter(([, r]) => !r.hidden);
  const phone = VW < 600;
  // A bar pinned to the foot is held by its bottom edge (bars differ in height).
  const ys = new Set(shown.map(([, r]) => (r.anchor === "bottom" ? `foot ${r.bar.y + r.bar.h}` : r.bar.y)));
  const covering = shown.filter(([, r]) => r.overSelection > 0);
  const onChrome = shown.filter(([, r]) => r.overRail > 0 || r.overTopBar > 0);

  ok("the bar appears for all ten selections", shown.length === rows.length, `${shown.length} of ${rows.length}`);
  ok(`every selection gets the ${phone ? "pinned" : "floating"} placement`,
    shown.every(([, r]) => (phone ? ["top", "bottom"].includes(r.anchor) : r.anchor === "float")),
    [...new Set(shown.map(([, r]) => r.anchor))].join(","));
  ok("it never leaves the canvas", shown.every(([, r]) => r.inside),
    shown.filter(([, r]) => !r.inside).map(([l]) => l).join(",") || "all inside");
  // The rule that decided section 7. A bar over the item can be panned out
  // from under; a bar over the rail takes the tools away, and at 390 the
  // floating placement put two of ten there (7759px2 and 1122px2) while
  // sending a third off the canvas.
  ok("it never sits on the rail or the top bar", onChrome.length === 0,
    onChrome.map(([l, r]) => `${l} rail ${r.overRail}px2 top ${r.overTopBar}px2`).join(", ") || "0px2 on all ten");
  if (phone) {
    // Two fixed places, the top of the canvas and the foot above the rail:
    // the foot only for a selection the top band would cover.
    ok("it is pinned to one of two places", ys.size <= 2, `tops ${[...ys].join(",")}`);
    ok("it never covers the item it is editing", covering.length === 0,
      covering.map(([l, r]) => `${l} ${r.overSelection}px2`).join(", ") || "0px2 on all ten");
  } else {
    ok("it never covers the item it is editing", covering.length === 0,
      covering.map(([l, r]) => `${l} ${r.overSelection}px2`).join(", ") || "0px2 on all ten");
  }
  const worst = shown.reduce((a, b) => (b[1].coverPct > a[1].coverPct ? b : a), shown[0]);
  console.log(`worst coverage: ${worst[0]} at ${worst[1].coverPct}% of the canvas`);
  console.log(`distinct bar tops across the ten: ${[...ys].sort((a, b) => a - b).join(", ")}`);

  console.log(`\n${pass}/${pass + fail} checks pass at ${VW}x${VH} (${process.env.THEME || "light"})`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
