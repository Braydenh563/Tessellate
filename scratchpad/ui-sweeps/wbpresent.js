// WHITEBOARD_PLAN decision 16: presenting a board's frames.
//
// A board with no frame: View, Present frames says how to make one. Three
// frames (two side by side, one below): Present frames hides the chrome, shows
// one bar, and fits the first frame to the screen; the arrows, Space, Home,
// End and the bar's buttons walk them in reading order; a tool letter and an
// arrow change nothing on the board; Escape ends it and puts the camera, the
// chrome and the window back. A map offers no Present row. The bar stays in
// the window and its text reads (4.5:1).
//
//   BASE=http://127.0.0.1:8800 SCRATCH=/tmp/x THEME=light VW=1440 VH=900 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbpresent.js
//
// MODE=build (INBOX 1774): a 15-topic map built up branch by branch and taken
// apart again. The visible topic count per step rises then falls on Previous,
// no write goes to the server, Escape gives every topic back, the shown topics
// sit inside the board above the bar, Alt+= / Alt+- step real folds (one Undo
// each); VW=390 taps instead of keys; REDUCE=1 checks no transition runs.
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

async function buildMain() {
  const phone = VW < 600;
  const reduce = process.env.REDUCE === "1";
  const { browser, page } = await boot({
    viewport: { width: VW, height: VH },
    ...(phone ? { hasTouch: true, isMobile: true } : {}),
  });
  if (reduce) await page.emulateMedia({ reducedMotion: "reduce" });
  const errors = [];
  const writes = [];
  let counting = false;
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => {
    if (counting && !["GET", "HEAD", "OPTIONS"].includes(r.method()) && !/\/usage$|\/thumbnail$/.test(new URL(r.url()).pathname)) writes.push(`${r.method()} ${new URL(r.url()).pathname}`);
  });
  await page.evaluate(() => document.querySelector('[data-tab="library"]').click());
  await page.waitForTimeout(500);
  await page.evaluate(() => document.querySelector('[data-target="library-view-whiteboard"]').click());
  await page.waitForTimeout(1200);
  await page.evaluate(async () => {
    await initWhiteboard();
    const md = ["- Atlas"];
    const tree = {
      Costs: { Hardware: ["Servers", "Network"], Software: ["Licences"] },
      Plan: { "Quarter one": ["Hire", "Train"], "Quarter two": [] },
      Risks: { Delay: [] },
      Team: {},
    };
    for (const [b, kids] of Object.entries(tree)) {
      md.push(`  - ${b}`);
      for (const [k, leaves] of Object.entries(kids)) {
        md.push(`    - ${k}`);
        for (const l of leaves) md.push(`      - ${l}`);
      }
    }
    const board = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content: md.join("\n"), name: `Build sweep ${Date.now()}` }) });
    await openWhiteboardBoard(board.id);
    await new Promise((r) => setTimeout(r, 1800));
  });
  const ready = await page.evaluate(() => ({ map: wbIsMap(), topics: wbMapIndex().nodes.length }));
  ok("a 15-topic map is open", ready.map && ready.topics === 15, JSON.stringify(ready));
  const objs = () =>
    page.evaluate(() => {
      const c = document.getElementById("whiteboard-container").getBoundingClientRect();
      return [...document.querySelectorAll("#whiteboard-container .wb-object")]
        .filter((el) => {
          const r = el.getBoundingClientRect();
          return r.width > 0 && getComputedStyle(el).display !== "none" && getComputedStyle(el).visibility !== "hidden";
        })
        .map((el) => ({ id: Number(el.dataset.id), text: el.textContent.trim().slice(0, 20), ring: el.classList.contains("flash-target"), r: el.getBoundingClientRect().toJSON(), c: c.toJSON() }));
    });
  const count = async () => (await objs()).length;
  const caption = () => page.evaluate(() => document.getElementById("wb-present-pick")?.textContent || "");
  const state = () => page.evaluate(() => wbState.objects.map((o) => `${o.id}:${o.x}:${o.y}:${JSON.stringify({ ...o.data, collapsed: Boolean(o.data?.collapsed) })}`).join("|"));

  // 1. Stepping outside presenting: real folds, one Undo each.
  await page.evaluate(() => { window.currentTool = "select"; document.getElementById("whiteboard-container").focus(); });
  const start = await state();
  const less = [];
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press("Alt+Minus");
    await page.waitForTimeout(700);
    less.push(await count());
  }
  const lessToast = await page.evaluate(() => [...document.querySelectorAll(".toast")].map((t) => t.textContent).join(" | "));
  ok("Alt+- folds the deepest open ring each press, down to the trunks, then says so", less[0] < 15 && less.every((n, i) => i === 0 || n <= less[i - 1]) && less[4] === less[3] && /Only the centre is showing/.test(lessToast), JSON.stringify(less) + " " + lessToast);
  const more = [];
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press("Alt+Equal");
    await page.waitForTimeout(700);
    more.push(await count());
  }
  const moreToast = await page.evaluate(() => [...document.querySelectorAll(".toast")].map((t) => t.textContent).join(" | "));
  ok("Alt+= opens the shallowest folded ring each press, back to every topic, then says so", more[3] === 15 && more.every((n, i) => i === 0 || n >= more[i - 1]) && /Every level is showing/.test(moreToast), JSON.stringify(more) + " " + moreToast);
  await page.keyboard.press("Alt+Minus");
  await page.waitForTimeout(600);
  const folded1 = await count();
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(700);
  const undone = await count();
  ok("one Undo puts back exactly one step", folded1 < 15 && undone === 15 && (await state()) === start, `${folded1} -> ${undone}`);

  // 2. Build up.
  const rowState = await page.evaluate(() => {
    const el = document.getElementById("wb-map-build");
    return { exists: Boolean(el), text: el?.textContent.trim(), title: el?.title };
  });
  ok("the board menu has Build up branch by branch", rowState.exists && rowState.text === "Build up branch by branch", JSON.stringify(rowState));
  counting = true;
  writes.length = 0;
  await page.evaluate(() => document.getElementById("wb-map-build").click());
  await page.waitForTimeout(1300);
  const expectCount = [1, 2, 4, 7, 8, 10, 12, 13, 14, 15, 15];
  const expectCap = ["Atlas", "Costs", "Costs, level 2", "Costs, level 3", "Plan", "Plan, level 2", "Plan, level 3", "Risks", "Risks, level 2", "Team", "The whole map"];
  const total = expectCount.length;
  const up = [];
  for (let i = 0; i < total; i++) {
    const list = await objs();
    const cap = await caption();
    const bar = await page.evaluate(() => document.getElementById("wb-present-bar").getBoundingClientRect().toJSON());
    const c = list[0]?.c;
    //: A branch step fits the trunk and the branch on show, so a branch shown earlier may be off screen by design.
    const mine = i === total - 1 ? list : list.filter((o) => o.ring || o.text.startsWith("Atlas") || o.text.startsWith(expectCap[i].split(",")[0]));
    const ok1 = (o) => o.r.left >= c.left - 1 && o.r.right <= c.right + 1 && o.r.top >= c.top - 1 && o.r.bottom <= bar.top + 1;
    const inside = mine.every(ok1);
    if (!inside && process.env.DEBUG) console.log("   outside at", i, JSON.stringify(mine.filter((o) => !ok1(o)).map((o) => [o.text, Math.round(o.r.left), Math.round(o.r.right), Math.round(o.r.top), Math.round(o.r.bottom)])), "bar top", Math.round(bar.top));
    up.push({ list, cap, inside, ring: list.filter((o) => o.ring).length, bar });
    if (i === 5) await page.screenshot({ path: `${process.env.SCRATCH || "."}/wbbuild-${VW}-${process.env.THEME || "light"}-${reduce ? "rm" : "m"}-step6.png` });
    if (i < total - 1) {
      if (phone) await page.tap("#wb-present-next");
      else await page.keyboard.press("ArrowRight");
      await page.waitForTimeout(reduce ? 250 : 700);
    }
  }
  ok(`the visible topics rise step by step ${expectCount.join(", ")}`, JSON.stringify(up.map((u) => u.list.length)) === JSON.stringify(expectCount), JSON.stringify(up.map((u) => u.list.length)));
  ok("the captions name the branch and its level", up.every((u, i) => u.cap.includes(`of ${total}: ${expectCap[i]}`)), up.map((u) => u.cap).join(" | "));
  ok("the trunk and the branch on show sit inside the board, above the bar (the whole map on the last)", up.every((u) => u.inside), JSON.stringify(up.map((u) => u.inside)));
  ok("only what a step revealed wears the ring; the whole map none", up.slice(0, -1).every((u, i) => u.ring === expectCount[i] - (expectCount[i - 1] || 0)) && up[total - 1].ring === 0, JSON.stringify(up.map((u) => u.ring)));
  console.log("   page width", VW, "bar", JSON.stringify(up[3].bar), "caption", up[3].cap);
  await page.screenshot({ path: `${process.env.SCRATCH || "."}/wbbuild-${VW}-${process.env.THEME || "light"}-${reduce ? "rm" : "m"}.png` });

  // 3. Taken apart: Previous, outer to inner.
  const down = [];
  for (let i = total - 2; i >= 0; i--) {
    if (phone) await page.tap("#wb-present-prev");
    else await page.keyboard.press("ArrowLeft");
    await page.waitForTimeout(reduce ? 250 : 700);
    down.push((await objs()).length);
  }
  ok("Previous takes the same parts away, last first", JSON.stringify(down) === JSON.stringify(expectCount.slice(0, total - 1).reverse()), JSON.stringify(down));

  // 4. Jumps land right: End, Home, a typed page, the picker.
  await page.keyboard.press("End");
  await page.waitForTimeout(500);
  const end = await count();
  await page.keyboard.press("Home");
  await page.waitForTimeout(500);
  const home = await count();
  await page.evaluate(() => wbPresentShow(5));
  await page.waitForTimeout(500);
  const jump = await count();
  await page.click("#wb-present-pick");
  await page.waitForTimeout(300);
  const rows = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")].map((r) => r.textContent.trim()));
  await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")][8]?.click());
  await page.waitForTimeout(600);
  const picked = await count();
  ok("End shows the whole map, Home the centre, a jump to page 6 and the picker's page 9 land right", end === 15 && home === 1 && jump === 10 && picked === 14, JSON.stringify({ end, home, jump, picked }));
  ok("the picker lists every step with its words", rows.length === total && /Costs, level 3/.test(rows[3] || ""), rows.join(" | "));

  // 5. A view: no key edits the map, and the level keys do nothing now.
  const mid = await state();
  await page.keyboard.press("Alt+Minus");
  await page.keyboard.press("Delete");
  await page.keyboard.press("Tab");
  await page.waitForTimeout(400);
  ok("keys while presenting change nothing and no write reached the server", writes.length === 0 && (await state()) === mid, writes.join(" | "));

  // 6. Escape: every topic back, the map exactly as it was.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(800);
  const after = await page.evaluate(() => ({
    presenting: document.getElementById("library-view-whiteboard").classList.contains("wb-presenting"),
    on: wbMapBuild.on, hidden: wbMapBuild.hidden.size, steps: wbMapBuild.steps.length,
    ring: document.querySelectorAll(".wb-object.flash-target").length,
  }));
  ok("Escape gives every topic back, nothing left over", !after.presenting && !after.on && after.hidden === 0 && after.steps === 0 && (await count()) === 15 && after.ring === 0, JSON.stringify(after));
  ok("the map is exactly as it was (positions, folds, text)", (await state()) === start);
  counting = false;

  // 7. The other mode still runs on its own; a bare map says what to add.
  await page.evaluate(() => document.getElementById("wb-map-study")?.click());
  await page.waitForTimeout(900);
  const study = await page.evaluate(() => ({ study: wbStudy.on, build: wbMapBuild.on }));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  ok("Study the map still runs on its own, not in build mode", study.study && !study.build, JSON.stringify(study));
  const empty = await page.evaluate(async () => {
    const board = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Bare ${Date.now()}`, type: "map", layout: "tree-right" }) });
    await openWhiteboardBoard(board.id);
    await new Promise((r) => setTimeout(r, 1200));
    wbMapBuild.start();
    await new Promise((r) => setTimeout(r, 300));
    return { on: wbMapBuild.on, toast: [...document.querySelectorAll(".toast")].map((t) => t.textContent).join(" | ") };
  });
  ok("a map with no branch says to add one", !empty.on && /Nothing to build up yet/.test(empty.toast), JSON.stringify(empty));

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
}

(async () => {
  if (process.env.MODE === "build") return buildMain();
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
  // "New board" is an empty canvas with no dialog now; the name dialog is the
  // menu's "From a template" row (as wbphone.js does).
  for (let attempt = 0; attempt < 5; attempt++) {
    await page.evaluate(() => document.getElementById("wb-boards-new-template").click());
    try { await page.waitForSelector("#wb-template-dialog[open]", { timeout: 12000 }); break; } catch (e) { if (attempt === 4) throw e; }
  }
  await page.fill("#wb-template-name", `Present sweep ${Date.now()}`);
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");

  const present = () => page.evaluate(() => document.querySelector('.wb-board-menu [data-wb-fn="present"][data-wb-surface="board"]').click());

  // 1. No frame yet.
  await present();
  await page.waitForTimeout(500);
  const empty = await page.evaluate(() => ({
    presenting: document.getElementById("library-view-whiteboard").classList.contains("wb-presenting"),
    toast: [...document.querySelectorAll(".toast")].map((t) => t.textContent).join(" | "),
  }));
  ok("with no frame, Present says how to make one", !empty.presenting && /Add a frame first/.test(empty.toast), JSON.stringify(empty));

  // 2. Three frames and something in each.
  await page.evaluate(async () => {
    await wbCreateObject("frame", { content: "Second" }, 700, 40, 500, 320, -1);
    await wbCreateObject("frame", { content: "First" }, 100, 60, 500, 320, -1);
    await wbCreateObject("frame", { content: "Third" }, 300, 600, 600, 400, -1);
    await wbCreateObject("text", { content: "In the first" }, 160, 140, 200, 80);
    await fetchWhiteboardState();
    renderWhiteboardNow();
  });
  const before = await page.evaluate(() => {
    const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
    return { k: t.k, x: t.x, y: t.y, tool: window.currentTool, sticky: wbState.objects.find((o) => o.kind === "text").x };
  });
  await present();
  await page.waitForTimeout(900);
  const state = () =>
    page.evaluate(() => {
      const host = document.getElementById("library-view-whiteboard");
      const bar = document.getElementById("wb-present-bar");
      const br = bar.getBoundingClientRect();
      const c = document.getElementById("whiteboard-container").getBoundingClientRect();
      const shown = (sel) => {
        const el = document.querySelector(sel);
        return Boolean(el && getComputedStyle(el).display !== "none" && el.getBoundingClientRect().width > 0);
      };
      const title = document.getElementById("wb-present-count").textContent;
      const name = title.split(": ")[1];
      const frame = wbState.objects.find((o) => o.kind === "frame" && o.data.content === name);
      const fr = frame ? document.querySelector(`.wb-object[data-id="${frame.id}"]`).getBoundingClientRect() : null;
      return {
        presenting: host.classList.contains("wb-presenting"),
        full: host.classList.contains("wb-fullscreen"),
        topbar: shown(".wb-topbar"), rail: shown("#wb-tools-panel"), zoom: shown('[data-panel-id="zoom"]'),
        bar: !bar.classList.contains("hidden") && br.width > 0,
        barInside: br.left >= c.left - 0.5 && br.right <= c.right + 0.5 && br.bottom <= c.bottom + 0.5,
        title,
        fill: fr ? Math.max(fr.width / c.width, fr.height / c.height) : 0,
        frameInside: fr ? fr.left >= c.left - 1 && fr.right <= c.right + 1 && fr.top >= c.top - 1 && fr.bottom <= c.bottom + 1 : false,
        clearOfBar: fr ? fr.bottom <= br.top + 0.5 : false,
        prevDisabled: document.getElementById("wb-present-prev").disabled,
        nextDisabled: document.getElementById("wb-present-next").disabled,
      };
    });
  const s1 = await state();
  ok("Present frames hides the chrome and shows one bar, full screen", s1.presenting && s1.full && !s1.topbar && !s1.rail && !s1.zoom && s1.bar, JSON.stringify(s1));
  ok("it opens on the first frame in reading order, fitted to the screen", s1.title === "1 of 3: First" && s1.fill >= 0.7 && s1.frameInside, `${s1.title} fill ${s1.fill.toFixed(2)}`);
  ok("the bar sits inside the board, below the frame", s1.barInside && s1.clearOfBar);
  ok("Previous is off on the first frame", s1.prevDisabled && !s1.nextDisabled);

  // 3. Walking.
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(600);
  const s2 = await state();
  ok("the right arrow goes to the frame beside it", s2.title === "2 of 3: Second" && s2.fill >= 0.7 && s2.frameInside, `${s2.title} fill ${s2.fill.toFixed(2)}`);
  await page.keyboard.press(" ");
  await page.waitForTimeout(600);
  const s3 = await state();
  ok("Space goes to the next row", s3.title === "3 of 3: Third" && s3.frameInside && s3.nextDisabled, s3.title);
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(400);
  ok("past the last frame it stays on the last", (await state()).title === "3 of 3: Third");
  await page.keyboard.press("Home");
  await page.waitForTimeout(600);
  ok("Home goes back to the first", (await state()).title === "1 of 3: First");
  await page.keyboard.press("End");
  await page.waitForTimeout(600);
  ok("End goes to the last", (await state()).title === "3 of 3: Third");
  await page.keyboard.press("ArrowLeft");
  await page.waitForTimeout(600);
  ok("the left arrow goes back one", (await state()).title === "2 of 3: Second");
  await page.evaluate(() => document.getElementById("wb-present-prev").click());
  await page.waitForTimeout(600);
  ok("the bar's Previous button walks too", (await state()).title === "1 of 3: First");

  // 4. A view: letters and arrows change nothing on the board.
  await page.keyboard.press("r");
  await page.keyboard.press("Delete");
  const still = await page.evaluate(() => ({ tool: window.currentTool, sticky: wbState.objects.find((o) => o.kind === "text")?.x, frames: wbState.objects.filter((o) => o.kind === "frame").length }));
  ok("a tool letter and Delete do nothing while presenting", still.tool === before.tool && still.sticky === before.sticky && still.frames === 3, JSON.stringify(still));

  // 5. The bar's text reads.
  const ink = await page.evaluate(() => {
    const bar = document.getElementById("wb-present-bar");
    const count = document.getElementById("wb-present-count");
    const probe = document.createElement("canvas").getContext("2d");
    const flat = (c, under) => {
      probe.clearRect(0, 0, 1, 1);
      probe.fillStyle = under; probe.fillRect(0, 0, 1, 1);
      probe.fillStyle = c; probe.fillRect(0, 0, 1, 1);
      return [...probe.getImageData(0, 0, 1, 1).data].slice(0, 3);
    };
    const board = getComputedStyle(document.getElementById("whiteboard-container")).backgroundColor;
    const bg = flat(getComputedStyle(bar).backgroundColor, board);
    return { text: flat(getComputedStyle(count).color, `rgb(${bg.join(",")})`), bg };
  });
  const r = ratio(ink.text, ink.bg);
  ok("the bar's count reads (4.5:1)", r >= 4.5, r.toFixed(2));
  await page.screenshot({ path: `${process.env.SCRATCH || "."}/wbpresent-${VW}-${process.env.THEME || "light"}.png` });

  // 6. Escape ends it and puts everything back.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(700);
  const after = await page.evaluate(() => {
    const host = document.getElementById("library-view-whiteboard");
    const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
    return {
      presenting: host.classList.contains("wb-presenting"), full: host.classList.contains("wb-fullscreen"),
      bar: !document.getElementById("wb-present-bar").classList.contains("hidden"),
      topbar: getComputedStyle(document.querySelector(".wb-topbar")).display !== "none",
      k: t.k, x: t.x, y: t.y,
    };
  });
  ok("Escape ends it: chrome back, bar gone, window as it was", !after.presenting && !after.full && !after.bar && after.topbar, JSON.stringify(after));
  ok("and the camera where it was", Math.abs(after.k - before.k) < 1e-6 && Math.abs(after.x - before.x) < 0.5 && Math.abs(after.y - before.y) < 0.5, JSON.stringify({ before, after }));

  // 7. A map has no Present frames row (it has its own, mappresent.js).
  const mapRow = await page.evaluate(async () => {
    const board = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Present map ${Date.now()}`, type: "map", layout: "tree-right" }) });
    window.currentBoardId = board.id;
    await fetchWhiteboardState();
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 600));
    const row = document.querySelector('.wb-board-menu [data-wb-fn="present"][data-wb-surface="board"]');
    const frameRow = document.querySelector('.wb-board-menu [data-wb-insert="frame"]');
    return { isMap: wbIsMap(), present: row.hidden, frame: frameRow.hidden };
  });
  if (mapRow.isMap) ok("a map offers neither Present frames nor Frame", mapRow.present && mapRow.frame, JSON.stringify(mapRow));
  else console.log("SKIP map row check: could not open a map from the sweep", JSON.stringify(mapRow));

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(2);
});
