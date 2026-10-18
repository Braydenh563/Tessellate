// The map at phone width, which nothing in `mindmap.js` or `mindmap3.js` had
// ever been run at (the mind map remaining list, item 3). Two things it found
// on the first run are measured here so they stay found: the node's own action
// row sitting on top of its fold chevron, and the templates card over the only
// topic of a brand new map.
//
//   VIEWPORT=390x844 BASE=http://127.0.0.1:8791 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapnarrow.js
const { boot } = require("./lib.js");

const VIEWPORT = (() => {
  const raw = process.env.VIEWPORT;
  if (!raw) return { width: 390, height: 844 };
  const [w, h] = raw.split("x").map(Number);
  return { width: w || 390, height: h || 844 };
})();

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

async function newMap(page) {
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(600);
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(900);
  //: The New map button on the boards list makes the map at once (the
  //: template-name dialog this sweep once filled in is gone).
  await page.evaluate(() => document.getElementById("wb-boards-new-map").click());
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
}

(async () => {
  const { browser, page } = await boot({ viewport: VIEWPORT });
  await newMap(page);

  // --- the templates card over a new map's only topic -----------------------
  const templates = await page.evaluate(() => {
    const card = document.getElementById("wb-map-templates");
    const node = document.querySelector(".wb-object");
    if (!card || !node) return { card: Boolean(card), node: Boolean(node) };
    const c = card.getBoundingClientRect();
    const n = node.getBoundingClientRect();
    const overlap = Math.max(0, Math.min(c.right, n.right) - Math.max(c.left, n.left))
      * Math.max(0, Math.min(c.bottom, n.bottom) - Math.max(c.top, n.top));
    const centre = document.elementFromPoint(Math.round(n.left + n.width / 2), Math.round(n.top + n.height / 2));
    return {
      shown: !card.hidden,
      overlap: Math.round(overlap),
      atNodeCentre: centre ? (centre.closest(".wb-object") ? "the topic" : centre.id || centre.className.toString().slice(0, 40)) : "nothing",
      cardBox: [Math.round(c.left), Math.round(c.top), Math.round(c.width), Math.round(c.height)],
      nodeBox: [Math.round(n.left), Math.round(n.top), Math.round(n.width), Math.round(n.height)],
    };
  });
  console.log("  templates:", JSON.stringify(templates));
  check("the templates card does not cover the map's only topic",
    !templates.shown || (templates.overlap === 0 && templates.atNodeCentre === "the topic"),
    `overlap ${templates.overlap}px2, the point at the topic's centre is ${templates.atNodeCentre}`);
  await page.keyboard.press("Escape");

  // --- the fold chevron under the node's action row -------------------------
  const kidId = await page.evaluate(async () => {
    const root = wbMapIndex().roots[0];
    const kid = await wbMapAddChild(root.id);
    const g = await wbMapAddChild(kid.id);
    return g ? kid.id : kid.id;
  });
  await page.waitForTimeout(1600);
  await page.evaluate(() => wbZoomToFit({ animate: false }));
  await page.waitForTimeout(500);
  await page.evaluate((id) => selectWbItem("object", id), kidId);
  await page.waitForTimeout(400);
  const chev = await page.evaluate((id) => {
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    const c = node.querySelector(".wb-map-collapse");
    const acts = node.querySelector(".wb-map-actions");
    if (!c) return { chevron: false };
    const cr = c.getBoundingClientRect();
    const ar = acts ? acts.getBoundingClientRect() : null;
    const overlap = ar
      ? Math.max(0, Math.min(cr.right, ar.right) - Math.max(cr.left, ar.left))
        * Math.max(0, Math.min(cr.bottom, ar.bottom) - Math.max(cr.top, ar.top))
      : 0;
    const x = Math.round(cr.left + cr.width / 2), y = Math.round(cr.top + cr.height / 2);
    const at = document.elementFromPoint(x, y);
    return {
      chevron: true,
      chevronBox: [Math.round(cr.left), Math.round(cr.top), Math.round(cr.width), Math.round(cr.height)],
      actionsBox: ar ? [Math.round(ar.left), Math.round(ar.top), Math.round(ar.width), Math.round(ar.height)] : null,
      actionsShown: acts ? getComputedStyle(acts).opacity !== "0" : false,
      overlap: Math.round(overlap),
      hit: at ? (at.closest(".wb-map-collapse") ? "the chevron" : at.closest(".wb-map-actions") ? "the action row" : (at.className || at.tagName).toString().slice(0, 50)) : "nothing",
    };
  }, kidId);
  console.log("  chevron:", JSON.stringify(chev));
  check("the node's action row does not sit on its fold chevron",
    chev.chevron && chev.overlap === 0, `${chev.overlap}px2 of overlap`);
  check("a press on the chevron reaches the chevron",
    chev.hit === "the chevron", `it reaches ${chev.hit}`);

  const bad = results.filter((r) => !r.ok);
  console.log(`\n${VIEWPORT.width}x${VIEWPORT.height}: ${results.length - bad.length}/${results.length} passed`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})();
