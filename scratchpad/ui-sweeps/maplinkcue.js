// MINDMAP_PLAN §13c's remainder: a connect drag says which of the two
// connections it will make while it is in flight, not only after it lands.
//
// A trunk with two branches and one loose topic. Dragged with the connect
// tool from a branch to the other branch, the target wears the dashed
// cross-link ring, the preview line is dashed and the announcer says
// "cross-link"; the release makes a cross-link. Dragged from a branch to the
// loose topic, the target wears the accent ring and the announcer says where
// it will go; the release hangs it there. Moving off every topic, and Escape,
// both take the cue away.
//
//   BASE=http://127.0.0.1:8850 SCRATCH=/tmp/x \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/maplinkcue.js
const { boot } = require("./lib.js");

let pass = 0;
let fail = 0;
function ok(label, good, detail) {
  if (good) pass += 1;
  else fail += 1;
  console.log(`${good ? "OK  " : "FAIL"} ${label}${detail ? "  " + detail : ""}`);
}

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
  await page.fill("#wb-template-name", "Link cue sweep");
  await page.click('#wb-template-kind button[data-value="map"]');
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");

  const ids = await page.evaluate(async () => {
    const root = wbMapIndex().roots[0];
    const a = await wbMapCreateNode({ parentId: root.id, text: "Branch A" });
    const b = await wbMapCreateNode({ parentId: root.id, text: "Branch B" });
    await wbMapTidy({ quiet: true });
    const loose = await wbMapCreateNode({ text: "Loose idea" });
    // 300, not 420: with the map laid out as it is now, +420 put the topic's centre 1px past the right edge of a
    // 1440px window, so the pointer never reached it and no cue could show.
    loose.x = a.x + 300;
    loose.y = a.y + 40;
    loose.data = { ...loose.data, pinned: true };
    await wbSaveObject(loose);
    renderWhiteboardNow();
    clearWbSelection();
    return { root: root.id, a: a.id, b: b.id, loose: loose.id };
  });
  await page.waitForTimeout(700);

  const centre = (id) =>
    page.evaluate((nid) => {
      const r = document.querySelector(`.wb-object[data-id="${nid}"]`).getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }, id);
  const cue = (id) =>
    page.evaluate((nid) => {
      const el = document.querySelector(`.wb-object[data-id="${nid}"]`);
      const path = [...document.querySelectorAll("#wb-zoom-group > path")].pop();
      return {
        branch: el.classList.contains("wb-map-link-cue-branch"),
        cross: el.classList.contains("wb-map-link-cue-cross"),
        outline: getComputedStyle(el).outlineStyle,
        dashed: Boolean(path && path.classList.contains("wb-link-preview-crosslink") && getComputedStyle(path).strokeDasharray !== "none"),
        said: document.getElementById("wb-announcer").textContent,
        any: document.querySelectorAll(".wb-map-link-cue-branch, .wb-map-link-cue-cross").length,
      };
    }, id);

  async function dragTo(from, to, { release = true, escape = false, offTo = null } = {}) {
    await page.evaluate(() => wbSelectToolRef("link-straight"));
    const s = await centre(from);
    const t = await centre(to);
    await page.mouse.move(s.x, s.y);
    await page.mouse.down();
    await page.mouse.move(t.x, t.y, { steps: 10 });
    await page.waitForTimeout(150);
    const mid = await cue(to);
    let off = null;
    if (offTo) {
      await page.mouse.move(offTo.x, offTo.y, { steps: 6 });
      await page.waitForTimeout(100);
      off = await cue(to);
      await page.mouse.move(t.x, t.y, { steps: 6 });
    }
    let afterEscape = null;
    if (escape) {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(100);
      afterEscape = await cue(to);
    }
    await page.mouse.up();
    await page.waitForTimeout(release ? 1200 : 300);
    return { mid, off, afterEscape, after: await cue(to) };
  }

  // 1. Branch to branch: a cross-link, said before it is made.
  const links0 = await page.evaluate(() => wbState.sketches.length);
  const blank = await page.evaluate(() => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    return { x: r.left + 60, y: r.bottom - 160 };
  });
  const one = await dragTo(ids.a, ids.b, { offTo: blank });
  ok("over a topic already in the tree, the target wears the dashed cross-link ring", one.mid.cross && !one.mid.branch && one.mid.outline === "dashed", JSON.stringify(one.mid));
  ok("the preview line is dashed", one.mid.dashed);
  ok("the announcer says cross-link before the release", /cross-link/.test(one.mid.said), one.mid.said);
  ok("off every topic, no cue", one.off && one.off.any === 0, JSON.stringify(one.off));
  const links1 = await page.evaluate(() => wbState.sketches.length);
  ok("the release makes the cross-link it promised", links1 === links0 + 1, `${links0} to ${links1}`);
  ok("and the cue is gone after it", one.after.any === 0, String(one.after.any));

  // 2. Branch to a loose topic: it joins the tree, said before it is made.
  const two = await dragTo(ids.a, ids.loose);
  ok("over a loose topic, the target wears the accent ring", two.mid.branch && !two.mid.cross && two.mid.outline === "solid", JSON.stringify(two.mid));
  ok("the announcer says where it will go", /put "Loose idea" under "Branch A"/.test(two.mid.said), two.mid.said);
  const parent = await page.evaluate((id) => wbState.objects.find((o) => o.id === id).parent_id, ids.loose);
  ok("the release hangs it there, as promised", parent === ids.a, `parent ${parent}`);

  // 3. Escape takes the cue back with the line.
  const three = await dragTo(ids.b, ids.a, { escape: true, release: false });
  ok("Escape mid-drag takes the cue away", three.mid.cross && three.afterEscape.any === 0, JSON.stringify(three.afterEscape));

  // 4. The topic menu's words for the same gesture pick the connect tool
  // (found with this sweep: the row called a function only the board's
  // setup closure can see, and threw).
  await page.keyboard.press("Escape");
  await page.evaluate((id) => {
    wbSelectToolRef("select");
    selectWbItem("object", id);
    document.getElementById("whiteboard-container").focus();
  }, ids.b);
  await page.keyboard.press("Shift+F10");
  await page.waitForTimeout(250);
  const before = errors.length;
  const tool = await page.evaluate(() => {
    const row = [...document.querySelectorAll(".wb-ctx-menu .menu-item")].find((b) => b.textContent.trim() === "Connect this topic to another");
    if (!row) return "no row";
    row.click();
    return window.currentTool;
  });
  await page.waitForTimeout(200);
  ok("the menu's Connect this topic to another picks the connect tool", tool === "link-straight" && errors.length === before, `${tool}${errors.length > before ? ", " + errors.slice(before).join(" | ") : ""}`);

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`${pass} ok, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
