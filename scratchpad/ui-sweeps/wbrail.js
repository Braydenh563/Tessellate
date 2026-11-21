// INBOX 43's second half (the mind map remaining list, item 5): the
// whiteboard's bottom tool rail and its floating panels against the bar recipe
// in `08-consistency.css`.
//
// Measured before anything is changed, because "onto the recipe" is a
// sentence and the recipe is a set of numbers: the Notes dock is the recipe as
// it renders, and the rail and the panels are read against it property by
// property. A floating rail over a canvas is deliberately not a tab dock (it
// is glass, it moves, it has no identity zone), so what is compared here is
// the shared vocabulary: the radius, the padding rhythm, the gap, the control
// height, and whether a control inside carries its own surface.
//
//   BASE=http://127.0.0.1:8791 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/wbrail.js
const { boot, newBoard: libNewBoard } = require("./lib.js");

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

const box = (sel) => (page) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const buttons = [...el.querySelectorAll("button.ghost")].filter((b) => b.getBoundingClientRect().height > 0);
  const heights = [...new Set(buttons.map((b) => Math.round(b.getBoundingClientRect().height)))];
  const radii = [...new Set(buttons.map((b) => getComputedStyle(b).borderRadius))];
  return {
    radius: cs.borderRadius,
    padding: `${cs.paddingTop}/${cs.paddingRight}/${cs.paddingBottom}/${cs.paddingLeft}`,
    gap: cs.gap,
    border: cs.borderTopWidth + " " + cs.borderTopStyle,
    buttons: buttons.length,
    buttonHeights: heights,
    buttonRadii: radii,
  };
}, sel);

(async () => {
  const { browser, page } = await boot({});
  // The Notes dock is the recipe as it renders.
  await page.click('[data-tab="notes"]');
  await page.waitForTimeout(900);
  const dock = await box('.dock[data-dock-name="notes"]')(page);
  console.log("  dock  :", JSON.stringify(dock));

  await libNewBoard(page, `Rail ${Date.now()}`, 'board');
  await page.keyboard.press("Escape");

  const rail = await box("#wb-tools-panel")(page);
  console.log("  rail  :", JSON.stringify(rail));
  // The board's own properties/look panel, opened from the View menu's Panels.
  await page.evaluate(() => {
    for (const el of document.querySelectorAll(".whiteboard-floating-panel")) el.classList.remove("hidden");
  });
  await page.waitForTimeout(400);
  const panels = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll(".whiteboard-floating-panel")) {
      const cs = getComputedStyle(el);
      if (el.getBoundingClientRect().height === 0) continue;
      out.push({
        id: el.id || el.dataset.panelId || "(unnamed)",
        radius: cs.borderRadius,
        padding: `${cs.paddingTop}/${cs.paddingRight}/${cs.paddingBottom}/${cs.paddingLeft}`,
        gap: cs.gap,
        border: cs.borderTopWidth + " " + cs.borderTopStyle,
      });
    }
    return out;
  });
  for (const p of panels) console.log("  panel :", JSON.stringify(p));

  const one = (values) => new Set(values.filter(Boolean)).size === 1;
  check("every floating panel on the board draws one radius",
    one(panels.map((p) => p.radius).concat(rail ? [rail.radius] : [])),
    panels.map((p) => `${p.id} ${p.radius}`).concat(`rail ${rail && rail.radius}`).join(", "));
  check("every floating panel on the board draws one padding",
    one(panels.map((p) => p.padding)),
    panels.map((p) => `${p.id} ${p.padding}`).join(", "));
  // Not "the rail's radius is the dock's": a floating rail over a canvas is a
  // pill and a tab dock is a card, and that is a decision with its rule
  // written down (06-timeline-dialogs.css, "a pill is a single row of
  // controls"). What has to hold is that each is its own shape and neither is
  // a third one.
  check("the floating rail is a pill and the tab dock is a card",
    rail && dock && rail.radius === "999px" && dock.radius !== rail.radius,
    `rail ${rail && rail.radius}, dock ${dock && dock.radius}`);
  check("a control in the rail is one height",
    rail && rail.buttonHeights.length === 1,
    `${rail && rail.buttonHeights.join("/")} over ${rail && rail.buttons} controls`);
  check("and the dock's own height",
    rail && dock && rail.buttonHeights[0] === dock.buttonHeights[0],
    `rail ${rail && rail.buttonHeights.join("/")}, dock ${dock && dock.buttonHeights.join("/")}`);
  check("a control in the rail is one radius",
    rail && rail.buttonRadii.length === 1, `${rail && rail.buttonRadii.join(" | ")}`);

  const bad = results.filter((r) => !r.ok);
  console.log(`\n${results.length - bad.length}/${results.length} passed`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})();
