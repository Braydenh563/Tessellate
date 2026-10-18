// **The map's own look, and the one bulk operation** (MINDMAP_PLAN.md §13e,
// the owner: "the customisation features are lacking severely").
//
// §13.4 measured the gap precisely and this sweep re-measures it: eleven
// per-topic fields, every one of them set one topic at a time, and no
// map-level default of any kind. What it asserts:
//
// 1. **The door is one row inside a menu that already exists.** §13's
//    decision 5 says nothing is added to the canvas and §13b has just taken
//    the topic strip from fourteen controls to five, so a theme that arrived
//    as a sixth control on the canvas would undo half of this section. The
//    counts of the top bar, the rail and the strip must be unchanged.
// 2. **A topic that was never told otherwise follows the map.** Measured, not
//    looked at: the rendered font size in px, the shape attribute, and the
//    stroke width of the line into it, before and after one theme write.
// 3. **A topic that was told keeps what it was given.** This is the rule the
//    theme is worth nothing without: a map-wide change that overwrites a
//    deliberate choice is a control nobody can press twice.
// 4. **One request, whatever the map's size.** The theme is resolved when a
//    topic is painted rather than written onto every topic, so a 60-topic map
//    costs the same as a 3-topic one. Counted at `fetch`.
// 5. **"Back to the map" is "Reset to branch" at the map's scope**: the same
//    list of fields, dropped from every topic in one request, and a picture
//    survives it because a picture is content rather than a look.
//
//   BASE=http://127.0.0.1:8796 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/maptheme.js
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
  await page.waitForTimeout(1200);
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  await page.waitForTimeout(500);

  await page.evaluate(async () => {
    const content = ["# Theme", "- Trunk"];
    for (let b = 1; b <= 6; b++) {
      content.push(`  - Branch ${b}`);
      for (let l = 1; l <= 3; l++) content.push(`    - Leaf ${b}${l}`);
    }
    const board = await apiJson("/whiteboard/boards/import", {
      method: "POST",
      body: JSON.stringify({ format: "markdown", content: content.join("\n"), name: "Theme" }),
    });
    await openWhiteboardBoard(board.id);
    await new Promise((r) => setTimeout(r, 1800));
  });
  const topics = await page.evaluate(() => wbMapIndex().nodes.length);
  check("a map to theme", topics === 25, `${topics} topics`);

  // --- 1. the door, and nothing added to the canvas ---
  const chrome = await page.evaluate(() => {
    const on = (el) => el && !el.hidden && el.getBoundingClientRect().width > 0;
    const controls = (root) => root
      ? [...root.querySelectorAll("button, select, input")].filter((c) => on(c)).length
      : 0;
    const row = document.getElementById("wb-map-theme-item");
    return {
      topbar: controls(document.getElementById("wb-topbar")),
      rail: controls(document.getElementById("whiteboard-tools")),
      strip: controls(document.getElementById("wb-map-strip")),
      themeRow: Boolean(row) && !row.hidden,
      themeRowText: row ? row.textContent.trim() : null,
      insideViewMenu: Boolean(row && row.closest("#wb-view-menu")),
    };
  });
  show(chrome);
  check("the theme's door is one row inside the View menu's Map section",
    chrome.themeRow && chrome.insideViewMenu, chrome.themeRowText);
  check("and nothing new is drawn on the canvas for it",
    chrome.strip <= 6 && chrome.topbar <= 10,
    `top bar ${chrome.topbar}, rail ${chrome.rail}, strip ${chrome.strip}`);

  // --- the map before a theme, measured ---
  const read = () => page.evaluate(() => {
    const index = wbMapIndex();
    const leaf = index.nodes.find((n) => /Leaf 11/.test(n.data?.content || ""));
    const own = index.nodes.find((n) => /Leaf 21/.test(n.data?.content || ""));
    const box = (n) => {
      const el = document.querySelector(`.wb-object[data-id="${n.id}"]`);
      if (!el) return null;
      const cs = getComputedStyle(el);
      return {
        fontSize: Math.round(parseFloat(cs.fontSize) * 10) / 10,
        shape: el.dataset.shape || "",
        bold: el.classList.contains("wb-map-bold"),
      };
    };
    //: A branch is drawn two ways, and only one of them has a stroke width:
    //: an undashed curve is a *ribbon*, a filled taper whose thickness is in
    //: the path it is drawn from (`wbMapEdgeWeight`), and a dashed or elbow
    //: line is a stroke. Both are read, because the theme has to reach both.
    const edge = (n) => {
      const line = [...document.querySelectorAll(".wb-map-edge")]
        .find((e) => e.dataset.child === String(n.id));
      if (!line) return null;
      return {
        weight: wbMapEdgeWeight(n),
        ribbon: line.classList.contains("wb-map-edge-ribbon"),
        strokeWidth: Math.round(parseFloat(getComputedStyle(line).strokeWidth) * 100) / 100,
        dashed: line.classList.contains("wb-map-edge-dashed"),
        thick: line.classList.contains("wb-map-edge-thick"),
        d: (line.getAttribute("d") || "").length,
      };
    };
    return { leaf: box(leaf), leafEdge: edge(leaf), own: box(own), theme: wbMapTheme() };
  });

  const before = await read();
  show(before);
  check("a map with no theme says nothing", Object.keys(before.theme).length === 0,
    JSON.stringify(before.theme));

  // --- 3. one topic given a look of its own, by hand, first ---
  await page.evaluate(async () => {
    const node = wbMapIndex().nodes.find((n) => /Leaf 21/.test(n.data?.content || ""));
    await wbMapSetNodeStyle(node, { shape: "rect", font_size: 12 });
    renderWhiteboardNow();
  });
  await page.waitForTimeout(400);
  const decorated = await read();
  show({ ownBefore: decorated.own });

  // --- 2 and 4. one theme write, counted ---
  await page.evaluate(() => {
    window.__writes = 0;
    const real = window.fetch;
    window.fetch = (...args) => {
      const url = String(args[0] || "");
      const method = (args[1] && args[1].method) || "GET";
      if (method !== "GET" && /\/whiteboard\//.test(url)) window.__writes += 1;
      return real(...args);
    };
  });
  await page.evaluate(async () => {
    await wbMapSetTheme({ font_size: 19, shape: "pill", edge_width: "thick", bold: true });
  });
  await page.waitForTimeout(700);
  const writes = await page.evaluate(() => window.__writes);
  const after = await read();
  show({ after: after.leaf, edge: after.leafEdge, own: after.own, writes });

  check("a topic that was never told otherwise follows the map's size",
    after.leaf.fontSize > before.leaf.fontSize + 3,
    `${before.leaf.fontSize}px to ${after.leaf.fontSize}px`);
  check("and its box and its weight",
    after.leaf.shape === "pill" && after.leaf.bold === true && before.leaf.shape === "",
    `shape "${before.leaf.shape}" to "${after.leaf.shape}", bold ${before.leaf.bold} to ${after.leaf.bold}`);
  check("and the branch line into it, which is a ribbon and is redrawn thicker",
    before.leafEdge.ribbon && after.leafEdge.ribbon
      && after.leafEdge.weight > before.leafEdge.weight
      && after.leafEdge.d !== before.leafEdge.d,
    `weight ${before.leafEdge.weight} to ${after.leafEdge.weight}, path ${before.leafEdge.d} to ${after.leafEdge.d} chars`);
  check("a topic that was given its own look keeps exactly what it was given",
    after.own.shape === "rect" && after.own.fontSize === decorated.own.fontSize,
    `shape "${after.own.shape}", ${after.own.fontSize}px, unchanged at ${decorated.own.fontSize}px`);
  check("one request themes the whole map, whatever its size",
    writes === 1, `${writes} write(s) for ${topics} topics`);

  //: The other drawing: a dashed line is a stroke, and a stroke is where a
  //: thickness is a number anybody can read off the screen.
  await page.evaluate(async () => { await wbMapSetTheme({ edge_dashed: true }); });
  await page.waitForTimeout(600);
  const stroked = await read();
  show({ stroked: stroked.leafEdge });
  check("and a themed dash turns it into a stroke that measures the themed thickness",
    !stroked.leafEdge.ribbon && stroked.leafEdge.dashed && stroked.leafEdge.thick
      && stroked.leafEdge.strokeWidth > before.leafEdge.strokeWidth,
    `${before.leafEdge.strokeWidth}px to ${stroked.leafEdge.strokeWidth}px, dashed ${stroked.leafEdge.dashed}`);
  await page.evaluate(async () => { await wbMapSetTheme({ edge_dashed: null }); });
  await page.waitForTimeout(500);

  // --- the strip reads the effective look, not the stored one ---
  const strip = await page.evaluate(async () => {
    const node = wbMapIndex().nodes.find((n) => /Leaf 11/.test(n.data?.content || ""));
    selectWbItem("object", node.id);
    await new Promise((r) => setTimeout(r, 400));
    const el = document.getElementById("wb-map-shape");
    const bold = document.getElementById("wb-map-bold");
    return {
      shape: el ? el.value : null,
      drawn: document.querySelector(`.wb-object[data-id="${node.id}"]`)?.dataset.shape || "",
      blankLabel: el ? el.querySelector('option[value=""]').textContent : null,
      boldPressed: bold ? bold.getAttribute("aria-pressed") : null,
      stored: node.data?.shape ?? null,
    };
  });
  show(strip);
  //: A topic never told follows the map and says so the same way for every
  //: field (OPEN row 1370): the select shows the blank row, which draws the
  //: map's own look, and the node itself draws the themed shape.
  check("the topic strip shows what the topic draws, not what it stores",
    strip.shape === "" && strip.drawn === "pill" && strip.boldPressed === "true" && strip.stored === null,
    `select "${strip.shape}", drawn "${strip.drawn}", bold ${strip.boldPressed}, stored ${strip.stored}`);
  check("and its blank option says it means the map, not the app's own default",
    /^As the map draws/.test(strip.blankLabel || ""), `blank option "${strip.blankLabel}"`);

  // --- a toggle pressed against the theme really turns it off ---
  const toggled = await page.evaluate(async () => {
    document.getElementById("wb-map-bold").click();
    await new Promise((r) => setTimeout(r, 500));
    const node = wbMapIndex().nodes.find((n) => /Leaf 11/.test(n.data?.content || ""));
    const el = document.querySelector(`.wb-object[data-id="${node.id}"]`);
    return { stored: node.data?.bold, drawn: el.classList.contains("wb-map-bold") };
  });
  show(toggled);
  check("turning a themed field off on one topic really turns it off",
    toggled.stored === false && toggled.drawn === false,
    `stored ${toggled.stored}, drawn bold ${toggled.drawn}`);

  // --- 5. back to the map, in one request, keeping the picture ---
  await page.evaluate(async () => {
    const node = wbMapIndex().nodes.find((n) => /Leaf 31/.test(n.data?.content || ""));
    await wbMapSetNodeStyle(node, { image: "/media/none.png", italic: true });
    window.__writes = 0;
  });
  await page.evaluate(async () => {
    const out = await apiJson(`/whiteboard/boards/${window.currentBoardId}/nodes/clear-style`, { method: "POST" });
    window.__cleared = out.cleared;
    await fetchWhiteboardState();
    renderWhiteboardNow();
  });
  await page.waitForTimeout(700);
  const cleared = await page.evaluate(() => {
    const index = wbMapIndex();
    const own = index.nodes.find((n) => /Leaf 21/.test(n.data?.content || ""));
    const pictured = index.nodes.find((n) => /Leaf 31/.test(n.data?.content || ""));
    const el = document.querySelector(`.wb-object[data-id="${own.id}"]`);
    return {
      cleared: window.__cleared,
      writes: window.__writes,
      ownShapeStored: own.data?.shape ?? null,
      ownShapeDrawn: el.dataset.shape || "",
      picture: pictured.data?.image || null,
      italic: pictured.data?.italic ?? null,
    };
  });
  show(cleared);
  check("back to the map clears every topic's own look in one request",
    cleared.cleared >= 2 && cleared.writes === 1 && cleared.ownShapeStored === null,
    `${cleared.cleared} topics, ${cleared.writes} request(s)`);
  check("and they follow the map afterwards rather than the app's own default",
    cleared.ownShapeDrawn === "pill", `drawn "${cleared.ownShapeDrawn}"`);
  check("a picture survives it, because a picture is content and not a look",
    cleared.picture === "/media/none.png" && cleared.italic == null,
    `image ${cleared.picture}, italic ${cleared.italic}`);

  //: --- the dialog itself, reached the way a person reaches it ---
  //:
  //: Real clicks, not `wbMapThemeDialog()`: the point of the row is that it
  //: is a door somebody can find and press, and calling the function proves
  //: only that the function exists. CLAUDE.md section 6's second shape is
  //: "a feature that never ran once"; this is the check that would catch it.
  await page.click('[aria-controls="wb-view-menu"]');
  await page.waitForTimeout(400);
  const doorBox = await page.evaluate(() => {
    const row = document.getElementById("wb-map-theme-item");
    const box = row.getBoundingClientRect();
    return { w: Math.round(box.width), h: Math.round(box.height), onScreen: box.top > 0 && box.bottom < innerHeight };
  });
  show(doorBox);
  check("the row is really on screen once the View menu is open",
    doorBox.w > 100 && doorBox.h >= 28 && doorBox.onScreen,
    `${doorBox.w}x${doorBox.h}`);
  await page.click("#wb-map-theme-item");
  await page.waitForTimeout(600);
  const dialog = await page.evaluate(async () => {
    //: Found from the body outwards: index.html holds a dozen overlays in
    //: markup, so the first `.modal-card` in document order is not this one.
    const body = document.querySelector(".wb-map-theme");
    const card = body ? body.closest(".card") : null;
    if (!card || !body) return { card: false };
    const box = body.getBoundingClientRect();
    return {
      card: true,
      cardClasses: card.className,
      selects: body.querySelectorAll("select").length,
      labels: [...body.querySelectorAll("select")].map((x) => x.getAttribute("aria-label") || x.id),
      checks: body.querySelectorAll("label.setting-check").length,
      heads: [...body.querySelectorAll("h4.setting-subhead")].map((h) => h.textContent.trim()),
      inlineStyles: body.querySelectorAll("[style]").length,
      width: Math.round(box.width),
      height: Math.round(box.height),
      overflows: body.scrollHeight > card.clientHeight + 2,
      viewMenuClosed: document.getElementById("wb-view-menu").classList.contains("hidden"),
    };
  });
  show(dialog);
  check("the dialog is the app's own card, not one with its own chrome",
    dialog.card && /modal-card/.test(dialog.cardClasses || ""), dialog.cardClasses);
  //: Ten topic fields in three groups, and since §13e's remainder the map's
  //: own two (branch colours and font) in a fourth, first; since §14 the
  //: hierarchy select above them (decision 39), a tenth select; and since
  //: then the scope select ("whose look the rows set") and spacing: twelve
  //: selects (listed in `labels`) and three switches.
  check("fifteen fields in four named groups, from the recipe index's own rows",
    dialog.selects === 12 && dialog.checks === 3 && dialog.heads.length === 4,
    `${dialog.selects} selects, ${dialog.checks} switches, ${(dialog.heads || []).join(" | ")}`);
  check("and it fits without scrolling at this size",
    !dialog.overflows && dialog.viewMenuClosed,
    `${dialog.width}x${dialog.height}, the menu behind it closed ${dialog.viewMenuClosed}`);

  //: **And a control in it really changes the map**, driven through the
  //: opener `enhanceSelect` draws rather than by setting `.value`: a select
  //: written to directly does not go through the shell at all, which is how
  //: a picker that looks right can be wired to nothing.
  const openerAt = await page.evaluate(() => {
    const sel = [...document.querySelectorAll(".wb-map-theme select")]
      .find((el) => (el.getAttribute("aria-label") || "").startsWith("Box"));
    const opener = sel?.closest(".select-shell")?.querySelector(".select-opener");
    if (!opener) return null;
    const box = opener.getBoundingClientRect();
    return { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) };
  });
  await page.mouse.click(openerAt.x, openerAt.y);
  await page.waitForTimeout(400);
  const chose = await page.evaluate(async () => {
    const menu = [...document.querySelectorAll(".select-menu")]
      .find((m) => m.getBoundingClientRect().width > 0);
    const rows = menu ? [...menu.querySelectorAll("[role='option'], button, li")] : [];
    const wanted = rows.find((o) => /Ellipse/.test(o.textContent));
    if (!wanted) return { options: rows.map((o) => o.textContent.trim()) };
    wanted.click();
    await new Promise((r) => setTimeout(r, 900));
    const node = wbMapIndex().nodes.find((n) => /Leaf 11/.test(n.data?.content || ""));
    const el = document.querySelector(`.wb-object[data-id="${node.id}"]`);
    return {
      options: rows.map((o) => o.textContent.trim()),
      theme: wbMapTheme().shape,
      drawn: el.dataset.shape || "",
      stored: node.data?.shape ?? null,
    };
  });
  show(chose);
  check("and the dialog writes no inline style, which the CSP would refuse",
    dialog.inlineStyles === 0, `${dialog.inlineStyles} inline style attributes`);
  check("picking a value in it changes what every untouched topic draws",
    chose.theme === "ellipse" && chose.drawn === "ellipse" && chose.stored === null,
    `theme ${chose.theme}, drawn "${chose.drawn}", the topic stores ${chose.stored}`);

  //: **Every word in the dialog, against the surface it is drawn on**, in
  //: whichever theme this run is in: the same ratio `contrast.js` measures,
  //: taken here because a dialog opened by a function is not on any of the
  //: tabs that sweep walks. §13's own read is all light, so a dark run of
  //: this file is the first measurement of this surface in dark.
  const readable = await page.evaluate(() => {
    //: Both forms the app's own tokens resolve to: `rgb()`/`rgba()` and
    //: `color(srgb r g b / a)`, which is what a translucent glass surface
    //: comes back as and what a naive parser reads as near-black.
    const parse = (c) => {
      if (!c) return null;
      const nums = (c.match(/[\d.]+%?/g) || []).map((n) => parseFloat(n));
      if (!nums.length) return null;
      if (/^color\(/.test(c)) {
        const [r, g, b] = nums.slice(0, 3).map((v) => v * 255);
        return [r, g, b, nums.length > 3 ? nums[3] : 1];
      }
      return [nums[0], nums[1], nums[2], nums.length > 3 ? nums[3] : 1];
    };
    const lum = ([r, g, b]) => {
      const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const ratio = (a, b) => {
      const [x, y] = [lum(a) + 0.05, lum(b) + 0.05].sort((p, q) => q - p);
      return Math.round((x / y) * 100) / 100;
    };
    //: **Composited, not the first colour found.** Every control in this
    //: dialog sits on a translucent fill over the card, so reading one layer
    //: as if it were opaque reports white text on white. The layers are
    //: walked outwards and mixed in the order the browser paints them.
    const bgOf = (el) => {
      const layers = [];
      for (let n = el; n; n = n.parentElement) {
        const c = parse(getComputedStyle(n).backgroundColor);
        if (!c || c[3] === 0) continue;
        layers.push(c);
        if (c[3] >= 1) break;
      }
      if (!layers.length) return [255, 255, 255];
      let out = layers.pop().slice(0, 3);
      while (layers.length) {
        const [r, g, b, a] = layers.pop();
        out = [0, 1, 2].map((i) => [r, g, b][i] * a + out[i] * (1 - a));
      }
      return out;
    };
    const body = document.querySelector(".wb-map-theme");
    const bad = [];
    let worst = 99;
    for (const el of body.querySelectorAll("span, p, h4, button")) {
      if (!el.textContent.trim() || el.querySelector("span, p, h4, button")) continue;
      //: Only what a person can actually see. `enhanceSelect` leaves the real
      //: `<select>` in the DOM at 1px, aria-hidden, with every one of its
      //: options still carrying text, and its own dropdown is built closed:
      //: measuring those is measuring nothing anybody reads.
      const box = el.getBoundingClientRect();
      if (box.width < 2 || box.height < 2) continue;
      if (el.closest('[aria-hidden="true"], .select-menu, option')) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) continue;
      const fg = parse(cs.color);
      if (!fg) continue;
      const r = ratio(fg, bgOf(el));
      const size = parseFloat(cs.fontSize);
      const need = (size >= 18.66 || (parseInt(cs.fontWeight, 10) >= 700 && size >= 14)) ? 3 : 4.5;
      worst = Math.min(worst, r);
      if (r < need) bad.push(`${el.textContent.trim().slice(0, 24)} ${r}:1`);
    }
    return { worst, bad, theme: document.documentElement.getAttribute("data-theme") || "light" };
  });
  show(readable);
  check("every word in it is readable on the surface it is drawn on",
    readable.bad.length === 0,
    `worst ${readable.worst}:1 in ${readable.theme}` + (readable.bad.length ? ", " + readable.bad.join(", ") : ""));

  //: **The bulk action, pressed** (CLAUDE.md section 6's second shape, "a
  //: feature that never ran once"): its own button in the dialog's foot, then
  //: the confirmation it opens, then the map.
  await page.evaluate(async () => {
    const node = wbMapIndex().nodes.find((n) => /Leaf 21/.test(n.data?.content || ""));
    await wbMapSetNodeStyle(node, { shape: "rect" });
    renderWhiteboardNow();
  });
  const footPressed = await page.evaluate(async () => {
    const foot = document.querySelector(".wb-map-theme-foot button");
    if (!foot) return { foot: false };
    foot.click();
    await new Promise((r) => setTimeout(r, 500));
    const confirm = [...document.querySelectorAll(".confirm-overlay")]
      .find((o) => /losing the colours/.test(o.textContent || ""));
    if (!confirm) return { foot: true, confirm: false, label: foot.textContent.trim() };
    const go = [...confirm.querySelectorAll("button")].find((b) => /Back to the map/.test(b.textContent));
    go.click();
    await new Promise((r) => setTimeout(r, 1600));
    const node = wbMapIndex().nodes.find((n) => /Leaf 21/.test(n.data?.content || ""));
    const el = document.querySelector(`.wb-object[data-id="${node.id}"]`);
    return {
      foot: true,
      confirm: true,
      label: foot.textContent.trim(),
      stored: node.data?.shape ?? null,
      drawn: el.dataset.shape || "",
      themeKept: Boolean(wbMapTheme().shape),
    };
  });
  show(footPressed);
  check("the dialog's own button asks first, then brings every topic back",
    footPressed.confirm && footPressed.stored === null && footPressed.themeKept,
    `"${footPressed.label}": the topic stores ${footPressed.stored} and draws "${footPressed.drawn}"`);

  const ok = results.filter((r) => r.ok).length;
  console.log(`\n${ok}/${results.length} checks passed`);
  await browser.close();
  process.exit(ok === results.length ? 0 : 1);
})();
