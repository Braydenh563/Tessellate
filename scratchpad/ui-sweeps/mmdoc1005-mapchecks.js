// The mind map findings of audit 2026-10-05, checked in the running app:
//   FEAT-05  an imported map opens in tree-right with no overlapping topics
//   FEAT-15  a typed topic is one Undo step (two Ctrl+Z take two topics)
//   FEAT-16  after a name is committed, focus is on the canvas and announced
//   FEAT-17  a laid-out map's topic menu has no Order group
//   FEAT-11  the command palette lists the map's commands with a map open
//
//   BASE=http://127.0.0.1:8844 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/mmdoc1005-mapchecks.js   (VIEWPORT=390x844, THEME=dark)
const { boot } = require("./lib.js");
const VIEWPORT = (() => {
  const [w, h] = (process.env.VIEWPORT || "1440x900").split("x").map(Number);
  return { width: w, height: h };
})();

(async () => {
  const { page, browser } = await boot({ viewport: VIEWPORT });
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  const results = [];
  const check = (name, ok, detail) => {
    results.push(ok);
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`);
  };
  await page.evaluate(() => switchTab("library"));
  await page.waitForTimeout(600);
  await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click());
  await page.waitForTimeout(1200);
  const outline = ["# Imported", "", "- Centre"];
  for (let b = 0; b < 6; b++) {
    outline.push(`  - Branch ${b}`);
    for (let k = 0; k < 5; k++) outline.push(`    - Leaf ${b}.${k}`);
  }
  const imported = await page.evaluate(async (content) => {
    const b = await apiJson("/whiteboard/boards/import", { method: "POST", body: JSON.stringify({ format: "markdown", content }) });
    await openWhiteboardBoard(b.id);
    await wbMapTidyFresh();
    const boxes = [...document.querySelectorAll("#wb-html-layer .wb-object")].map((el) => el.getBoundingClientRect());
    let overlaps = 0;
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], c = boxes[j];
      if (a.left < c.right - 1 && c.left < a.right - 1 && a.top < c.bottom - 1 && c.top < a.bottom - 1) overlaps++;
    }
    return { layout: wbMapLayout(), overlaps, topics: boxes.length, undo: wbStacks.undo.length };
  }, outline.join("\n"));
  check("an imported map opens in tree-right", imported.layout === "tree-right", imported.layout);
  check("and no two topics overlap", imported.overlaps === 0, `${imported.overlaps} pairs over ${imported.topics}`);
  check("and the tidy at open is not an Undo step", imported.undo === 0, `undo ${imported.undo}`);

  // Two topics typed by keyboard, then two Ctrl+Z.
  await page.evaluate(() => {
    const pick = wbState.objects.find((o) => o.data?.content === "Branch 2");
    selectWbItem("object", pick.id);
    document.getElementById("whiteboard-container").focus();
  });
  const count = () => page.evaluate(() => wbState.objects.length);
  const start = await count();
  await page.keyboard.press("Tab");
  await page.keyboard.type("First new");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  const focus = await page.evaluate(() => ({
    id: document.activeElement?.id,
    said: document.getElementById("wb-announcer")?.textContent,
  }));
  check("after a name is committed, focus is on the canvas", focus.id === "whiteboard-container", focus.id);
  check("and the name is announced", focus.said === "First new", focus.said);
  await page.keyboard.press("Enter");
  await page.keyboard.type("Second new");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(900);
  const added = await count();
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(900);
  const afterOne = await count();
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(900);
  const afterTwo = await count();
  check("two typed topics added", added === start + 2, `${start} -> ${added}`);
  check("one Ctrl+Z takes one typed topic away", afterOne === start + 1, `${added} -> ${afterOne}`);
  check("and the second takes the other", afterTwo === start, `${afterOne} -> ${afterTwo}`);
  await page.keyboard.press("Control+Shift+z");
  await page.waitForTimeout(1200);
  const redone = await page.evaluate(() => wbState.objects.some((o) => o.data?.content === "First new"));
  check("Redo brings the topic back with its name", redone);

  // FEAT-09: a nested list pasted onto a selected topic becomes its branch,
  // one Undo step.
  const pasted = await page.evaluate(async () => {
    const pick = wbState.objects.find((o) => o.data?.content === "Branch 4");
    selectWbItem("object", pick.id);
    const before = wbState.objects.length;
    const dt = new DataTransfer();
    dt.setData("text/plain", "- one\n  - one a\n- two");
    document.getElementById("whiteboard-container").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
    await new Promise((r) => setTimeout(r, 1800));
    const tree = await apiJson(`/whiteboard/boards/${window.currentBoardId}/tree`);
    const find = (nodes) => nodes.flatMap((n) => (n.text === "Branch 4" ? [n] : find(n.children)));
    const branch = find(tree.roots)[0];
    return { before, after: wbState.objects.length, kids: branch.children.map((c) => `${c.text}(${c.children.map((g) => g.text).join(",")})`) };
  });
  check("a pasted list becomes the selected topic's branch", pasted.after === pasted.before + 3 && pasted.kids.join() .includes("one(one a)") && pasted.kids.join().includes("two()"), JSON.stringify(pasted));
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(1500);
  const unpasted = await page.evaluate(() => wbState.objects.length);
  check("and one Ctrl+Z takes the whole paste back", unpasted === pasted.before, `${pasted.after} -> ${unpasted}`);

  // The topic menu on a laid-out map: no Order group.
  const menu = await page.evaluate(() => {
    const pick = wbState.objects.find((o) => o.data?.content === "Branch 1");
    const el = document.querySelector(`.wb-object[data-id="${pick.id}"]`);
    const r = el.getBoundingClientRect();
    el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: r.left + 10, clientY: r.top + 10 }));
    const texts = [...document.querySelectorAll(".action-menu:not(.hidden) *, .wb-map-radial *")].map((n) => n.textContent.trim()).filter(Boolean);
    return texts.join(" | ").slice(0, 2000);
  });
  check("a laid-out map's topic menu has no Order group", !/Bring to front|Send to back/.test(menu));
  await page.keyboard.press("Escape");

  // The palette rows.
  const rows = await page.evaluate(() => {
    const pick = wbState.objects.find((o) => o.data?.content === "Branch 1");
    selectWbItem("object", pick.id);
    return paletteCommands().filter((r) => /^(This topic|This map|Map layout|Export the map)$/.test(r.group || "")).map((r) => r.label.replace(/^ph:\S+ /, ""));
  });
  check("the palette lists the map's commands", rows.includes("Tidy the map") && rows.includes("Add a child topic") && rows.includes("Export as OPML"), `${rows.length} rows`);
  const tidied = await page.evaluate(async () => {
    const row = paletteCommands().find((r) => r.label.endsWith("Layout: Tree, downward"));
    row.run();
    await new Promise((r) => setTimeout(r, 1500));
    return wbMapLayout();
  });
  check("a palette row runs", tidied === "tree-down", tidied);
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(800);
  const offMap = await page.evaluate(() => paletteCommands().filter((r) => r.group === "This map").length);
  check("and none are offered off the map", offMap === 0, offMap);

  console.log("errors", errs.length, errs.slice(0, 3));
  console.log(`${results.filter(Boolean).length}/${results.length} passed`);
  await browser.close();
})();
