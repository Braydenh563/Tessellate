// INBOX 410: "when I relink or newly link two mindmap nodes, they clump
// together??" A topic dropped on another topic (a relink), or a loose topic
// joined to the tree by a line (a new link), has to be laid out as the new
// parent's child, like a topic added with Tab, with its own branch carried
// along, and one Undo has to put it all back.
//
// Measured per layout (the default sideways tree, and Free): the drawn boxes
// of every topic after the move, the largest overlap between any two, where
// the moved topic sits against its new parent, whether its own child still
// sits beside it, and what one Undo restores.
//
//   BASE=http://127.0.0.1:8785 SCRATCH=/tmp/mm-mapfix \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/maprelink.js
const { boot, newBoard: libNewBoard } = require("./lib.js");

let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

async function newMap(page, name) {
  await libNewBoard(page, name, 'map');
  await page.waitForFunction(() => wbIsMap() && wbMapIndex().roots.length > 0, null, { timeout: 90000 });
  await page.waitForTimeout(1500);
  await page.keyboard.press("Escape");
}

function boxes() {
  const out = {};
  for (const el of document.querySelectorAll("#wb-html-layer .wb-object")) {
    const r = el.getBoundingClientRect();
    if (r.width) out[el.dataset.id] = { l: r.left, t: r.top, r: r.right, b: r.bottom };
  }
  return out;
}

function worstOverlap(b) {
  const ids = Object.keys(b);
  let worst = { area: 0 };
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
    const a = b[ids[i]], c = b[ids[j]];
    const w = Math.min(a.r, c.r) - Math.max(a.l, c.l);
    const h = Math.min(a.b, c.b) - Math.max(a.t, c.t);
    if (w > 0 && h > 0 && w * h > worst.area) worst = { area: Math.round(w * h), pair: [ids[i], ids[j]] };
  }
  return worst;
}

async function run(layout, how) {
  const { browser, page } = await boot({});
  await newMap(page, `Relink ${layout} ${how}`);
  const ids = await page.evaluate(async ({ layout, how }) => {
    if (layout !== wbMapLayout()) await wbMapSetLayout(layout);
    const root = wbMapIndex().roots[0];
    const tasks = await wbMapAddChild(root.id);
    await wbMapAddChild(root.id);
    const mover = await wbMapAddChild(root.id);
    const grandchild = await wbMapAddChild(mover.id);
    // The mover leaves the tree for the new-link case: cut loose first, as
    // the line ring's Cut does, then joined back by a drawn line.
    if (how === "link") {
      await apiJson(`/whiteboard/boards/${window.currentBoardId}/nodes/${mover.id}/move`,
        { method: "PUT", body: JSON.stringify({ parent_id: null }) });
      mover.parent_id = null;
      renderWhiteboardNow();
    }
    return { root: root.id, tasks: tasks.id, mover: mover.id, grandchild: grandchild.id };
  }, { layout, how });
  await page.waitForTimeout(800);
  await page.mouse.click(1300, 700);
  await page.waitForTimeout(300);
  const before = await page.evaluate(boxes);
  // Dropped on "Tasks" (a drag lets go of the topic on top of its target),
  // or joined to it by a line from where it stands.
  await page.evaluate(async ({ ids, how }) => {
    const mover = wbState.objects.find((o) => o.id === ids.mover);
    const tasks = wbState.objects.find((o) => o.id === ids.tasks);
    if (how === "drop") {
      const dx = tasks.x + 10 - mover.x, dy = tasks.y + 6 - mover.y;
      // Saved where it was let go, as a real drag saves its branch before
      // the transplant runs (`objDragEnd`): so a layout that does nothing
      // leaves it on top of Tasks, which is the report.
      for (const o of wbMapSubtree(wbMapIndex(), mover.id)) {
        o.x += dx; o.y += dy;
        await wbSaveObject(o);
      }
      renderWhiteboardNow();
      await wbMapTransplant(mover, tasks.id, false);
    } else {
      await wbMapJoinByLink(tasks, mover);
    }
  }, { ids, how });
  await page.waitForTimeout(1200);
  const after = await page.evaluate(boxes);
  const state = await page.evaluate((ids) => {
    const o = (id) => wbState.objects.find((x) => x.id === id);
    return { parent: o(ids.mover).parent_id, gcParent: o(ids.grandchild).parent_id };
  }, ids);
  const label = `${layout} ${how}`;
  check(`${label}: re-parented under Tasks`, state.parent === ids.tasks, `parent ${state.parent}`);
  const worst = worstOverlap(after);
  check(`${label}: no two topics overlap`, worst.area === 0, `largest ${worst.area}px2 ${worst.pair ? worst.pair.join("/") : ""}`);
  const m = after[ids.mover], t = after[ids.tasks], g = after[ids.grandchild];
  if (!m || !t || !g) {
    check(`${label}: all three topics drawn`, false, `drawn ${Object.keys(after).join(",")} wanted ${JSON.stringify(ids)}`);
    await browser.close();
    return;
  }
  const side = layout === "tree-down" ? m.t >= t.b : m.l >= t.r;
  check(`${label}: laid out beside Tasks as its child`, side,
    `mover ${Math.round(m.l)},${Math.round(m.t)} tasks right ${Math.round(t.r)} bottom ${Math.round(t.b)}`);
  check(`${label}: its own child came with it`, g.l >= m.r, `child left ${Math.round(g.l)} mover right ${Math.round(m.r)}`);
  // One Undo puts the parent and the places back.
  await page.evaluate(() => wbUndo());
  await page.waitForTimeout(1500);
  const undone = await page.evaluate((ids) => {
    const o = (id) => wbState.objects.find((x) => x.id === id);
    return { parent: o(ids.mover).parent_id };
  }, ids);
  const back = await page.evaluate(boxes);
  const origParent = how === "link" ? null : ids.root;
  const drift = Math.max(...Object.keys(before).map((id) => back[id]
    ? Math.hypot(back[id].l - before[id].l, back[id].t - before[id].t) : 0));
  check(`${label}: one Undo restores the parent`, undone.parent === origParent, `parent ${undone.parent}`);
  check(`${label}: one Undo restores the places`, how === "drop" || drift < 2, `largest drift ${drift.toFixed(1)}px`);
  await browser.close();
}

(async () => {
  for (const layout of ["tree-right", "free"]) {
    for (const how of ["drop", "link"]) await run(layout, how);
  }
  console.log(failures ? `${failures} failed` : "all passed");
  process.exit(failures ? 1 : 0);
})();
