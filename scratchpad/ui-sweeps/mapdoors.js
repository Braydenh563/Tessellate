// **Every door into the map's tools, counted** (MINDMAP_PLAN.md §13, the
// owner: "Tools and utilities are really awkward to use and dont show
// themselves how id expect", and §13.3's "what the surface offers, and by how
// many doors").
//
// What it asserts, and why each one is a number rather than an opinion:
//
// 1. **The two gestures a blank part of a map has to answer.** Both were
//    measured doing nothing at all: a right-click on empty map canvas opened
//    no menu of any kind, and a double-click added no topic (3 topics before,
//    3 after), so the first two things anybody tries on a blank part of a
//    mind map were dead. The right-click is the app's `openMenuAtPoint`
//    recipe; the double-click makes a trunk where the pointer was.
// 2. **Nothing is built and shut.** §13.3 found the Insert and Arrange menus
//    in a map's top bar with no opener on screen. This counts, for every menu
//    in the bar, whether its toggle is really reachable, and fails on a menu
//    that holds controls nobody can get to.
// 3. **Every control on a map says what it is.** DESIGN.md's icon-only rule
//    is `title` as well as `aria-label`: an `aria-label` alone answers a
//    screen reader and nobody else, which on a rail of twelve glyphs is the
//    whole complaint.
// 4. It prints the control count and the route depth per surface, which is
//    the table §13.3 is written from, so the next pass re-measures rather
//    than re-reads.
//
//   BASE=http://127.0.0.1:8794 SCRATCH=/tmp/mm-mapux2 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapdoors.js
const { boot } = require("./lib.js");

const VIEWPORT = (() => {
  const raw = process.env.VIEWPORT;
  if (!raw) return { width: 1440, height: 900 };
  const [w, h] = raw.split("x").map(Number);
  return { width: w || 1440, height: h || 900 };
})();

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}
const show = (o) => console.log("    " + JSON.stringify(o));

(async () => {
  const { browser, page } = await boot({ viewport: VIEWPORT });

  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  await page.waitForTimeout(500);

  await page.evaluate(async () => {
    const content = ["# Doors", "- Trunk"];
    for (let b = 1; b <= 3; b++) {
      content.push(`  - Branch ${b}`);
      content.push(`    - Leaf ${b}a`);
    }
    const board = await apiJson("/whiteboard/boards/import", {
      method: "POST",
      body: JSON.stringify({ format: "markdown", content: content.join("\n"), name: "Doors" }),
    });
    await openWhiteboardBoard(board.id);
    await new Promise((r) => setTimeout(r, 1500));
  });
  const topics = await page.evaluate(() => wbMapIndex().nodes.length);
  check("a map to count the doors of", topics === 7, `${topics} topics`);

  // --- 1. the canvas's own two gestures ---
  const empty = await page.evaluate(() => {
    const c = document.getElementById("whiteboard-container").getBoundingClientRect();
    // The top-left corner of the canvas, which the tidy leaves clear on a map
    // laid out sideways from the middle.
    return { x: Math.round(c.left + 110), y: Math.round(c.top + 110) };
  });
  await page.mouse.click(empty.x, empty.y, { button: "right" });
  await page.waitForTimeout(600);
  const canvasMenu = await page.evaluate(() => {
    const open = [...document.querySelectorAll(".action-menu")]
      .filter((m) => !m.classList.contains("hidden") && m.getBoundingClientRect().width > 0);
    return {
      menus: open.length,
      items: open.length ? [...open[0].querySelectorAll("button")].map((b) => b.textContent.trim()) : [],
      label: open.length ? open[0].getAttribute("aria-label") : null,
    };
  });
  show(canvasMenu);
  check("a right-click on empty map canvas opens the map's own menu",
    canvasMenu.menus === 1 && canvasMenu.items.length >= 4,
    canvasMenu.items.join(" | ") || "nothing opened");
  check("and it offers the four map-level actions, in words",
    /Add a topic here/.test(canvasMenu.items[0] || "")
      && canvasMenu.items.some((t) => /Tidy the map/.test(t))
      && canvasMenu.items.some((t) => /folded branch/.test(t))
      && canvasMenu.items.some((t) => /Fit everything/.test(t)),
    canvasMenu.items.join(" | "));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  const before = await page.evaluate(() => wbMapIndex().nodes.length);
  const dbl = { x: empty.x + 150, y: empty.y + 150 };
  await page.mouse.dblclick(dbl.x, dbl.y);
  await page.waitForTimeout(1400);
  const added = await page.evaluate(([x, y]) => {
    const index = wbMapIndex();
    const roots = index.roots;
    const made = roots[roots.length - 1];
    const el = document.querySelector(`.wb-object[data-id="${made.id}"]`);
    const box = el ? el.getBoundingClientRect() : null;
    return {
      nodes: index.nodes.length,
      roots: roots.length,
      pinned: Boolean(made.data?.pinned),
      dx: box ? Math.round(box.left + box.width / 2 - x) : null,
      dy: box ? Math.round(box.top + box.height / 2 - y) : null,
      editing: Boolean(document.querySelector(".wb-object.wb-text-editing")),
    };
  }, [dbl.x, dbl.y]);
  show(added);
  check("a double-click on empty map canvas adds a trunk", added.nodes === before + 1,
    `${before} topics to ${added.nodes}`);
  check("it lands where the pointer was, pinned, ready to be typed",
    Math.abs(added.dx) <= 24 && Math.abs(added.dy) <= 24 && added.pinned && added.editing,
    `${added.dx},${added.dy}px from the press, pinned ${added.pinned}, editing ${added.editing}`);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);

  // --- 2. nothing built and shut, 3. everything named ---
  const audit = await page.evaluate(() => {
    const visible = (el) => {
      if (!el || el.hidden || el.closest("[hidden]")) return false;
      const cs = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      return cs.display !== "none" && cs.visibility !== "hidden" && b.width > 0 && b.height > 0;
    };
    const named = (c) => ({
      label: (c.getAttribute("aria-label") || "").trim(),
      title: (c.title || "").trim(),
      word: (c.textContent || "").trim(),
    });
    const bar = document.getElementById("wb-topbar");
    const rail = document.getElementById("wb-tool-group");
    const strip = document.getElementById("wb-map-strip");
    const controls = (root, skipMenus) => [...root.querySelectorAll("button, select, input")]
      .filter((c) => {
        if (c.closest(".select-menu") || c.classList.contains("select-opener")) return false;
        if (skipMenus && c.closest(".wb-board-menu")) return false;
        return visible(c);
      });
    //: **What counts as a shut door.** §13.3 read the Insert and Arrange
    //: menus as "in the DOM with no opener on screen", and re-measured here
    //: that is half true and the harmless half: `wbSyncMapChrome` sets
    //: `hidden` on the whole wrap on a map, so the menu is neither drawn nor
    //: exposed to a screen reader, and it is `hidden` that carries both. What
    //: would be a real shut door is a menu a person or a reader can still
    //: reach into while its toggle is gone, so that is what this asks: for
    //: every menu with controls in it, either the toggle is on screen or the
    //: menu itself is not exposed at all.
    const shut = [];
    for (const menu of document.querySelectorAll("#wb-topbar .wb-board-menu")) {
      const toggle = document.querySelector(`#wb-topbar [aria-controls="${menu.id}"]`);
      const items = menu.querySelectorAll("button, select, input").length;
      if (!items || (toggle && visible(toggle))) continue;
      const exposed = typeof menu.checkVisibility === "function"
        ? menu.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
        : getComputedStyle(menu).display !== "none";
      if (exposed) shut.push({ menu: menu.id, items, exposed });
    }
    const unnamed = [];
    for (const c of [...controls(bar, true), ...controls(rail, false)]) {
      const n = named(c);
      // A control with a word on it is named by the word; everything else on
      // these two surfaces is a glyph and needs both, per DESIGN.md.
      if (n.word && n.title) continue;
      if (!n.title || !n.label) unnamed.push(n.label || n.word || c.id || c.className);
    }
    return {
      topbar: controls(bar, true).length,
      topbarInMenus: [...document.querySelectorAll("#wb-topbar .wb-board-menu")]
        .reduce((n, m) => n + m.querySelectorAll("button, select, input").length, 0),
      rail: controls(rail, false).length,
      strip: strip ? controls(strip, true).length : 0,
      shut,
      unnamed,
    };
  });
  show(audit);
  check("no menu in a map's top bar is exposed without a toggle", audit.shut.length === 0,
    audit.shut.length ? JSON.stringify(audit.shut) : `${audit.topbarInMenus} controls in menus, every one behind a toggle on screen or put away with it`);
  check("every control on a map's bar and rail has a name and a tooltip",
    audit.unnamed.length === 0, audit.unnamed.length ? audit.unnamed.join(", ") : `${audit.topbar + audit.rail} controls`);

  const ok = results.filter((r) => r.ok).length;
  console.log(`\n${ok}/${results.length} checks passed`);
  await browser.close();
  process.exit(ok === results.length ? 0 : 1);
})();
