// The map's own node controls: the edit strip, the node radial, the link
// radial, the edge handles, the text-size grip, transplant and sever
// (MINDMAP_PLAN.md §12.1 items 2 to 9).
//
// Drives a real Chromium against a running app and asserts numbers, not
// screenshots: what the strip writes on the node, where it sits, that the
// board's own selection bar stands down on a map node, and that every action
// the radial offers is reachable.
//
//   BASE=http://127.0.0.1:8803 SCRATCH=/tmp/mm-map9 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/mapstrip.js
const { boot } = require("./lib.js");

// SHOW_ERRORS=1 prints the body of any 4xx the page receives. Off by default
// because a sweep that passes should say nothing, and on demand because the
// alternative is guessing: a failing check here reports what it measured, not
// which field the server refused, and that difference cost a debugging round.
const SHOW_ERRORS = process.env.SHOW_ERRORS === "1";

// VIEWPORT=390x844 drives the same checks at phone width: everything in this
// file was written at 1440x900 and nothing here had been seen narrow.
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

async function newBoard(page, name, type) {
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(500);
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById("wb-boards-new-template").click());
  await page.waitForTimeout(700);
  await page.fill("#wb-template-name", name);
  if (type === "map") await page.click('#wb-template-kind button[data-value="map"]');
  await page.click("#wb-template-create");
  await page.waitForTimeout(2500);
  await page.keyboard.press("Escape");
}

(async () => {
  const { browser, page } = await boot({ viewport: VIEWPORT });
  if (SHOW_ERRORS) {
    page.on("response", async (r) => {
      if (r.status() >= 400) {
        let body = "";
        try { body = (await r.text()).slice(0, 400); } catch (e) { body = "(unreadable)"; }
        console.log(`HTTP ${r.status()} ${r.request().method()} ${r.url()}\n   ${body}`);
      }
    });
  }

  // At phone width the canvas is 364px and a trunk with one child is 440px of
  // tree, so a tidy leaves the trunk's own centre off the left edge and a
  // click on it lands on the shell behind the canvas (measured at 390x844:
  // the root's box at x=-95, `elementFromPoint` at its centre returning
  // `#tab-library`). A person would reach for Fit; this does the same, with
  // the app's own function, before each gesture that has to land on a node.
  // A no-op at 1440, where nothing is ever off the canvas.
  const frame = async () => {
    if (VIEWPORT.width >= 900) return;
    await page.evaluate(() => wbZoomToFit({ animate: false }));
    await page.waitForTimeout(400);
  };

  await newBoard(page, "Strip map", "map");
  // A root plus one child, so there is a branch as well as a trunk.
  await page.evaluate(async () => {
    const root = wbMapIndex().roots[0];
    await wbMapAddChild(root.id);
  });
  await page.waitForTimeout(1700);
  await page.keyboard.press("Escape");

  const kidId = await page.evaluate(() => {
    const i = wbMapIndex();
    return i.childrenOf.get(i.roots[0].id)[0].id;
  });

  // --- the strip stands in the board bar's place ----------------------------
  await page.evaluate((id) => selectWbItem("object", id), kidId);
  await page.waitForTimeout(400);
  const placed = await page.evaluate((id) => {
    const strip = document.getElementById("wb-map-strip");
    const bar = document.getElementById("wb-context");
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    const s = strip.getBoundingClientRect();
    const n = node.getBoundingClientRect();
    return {
      stripShown: !strip.classList.contains("hidden") && s.width > 0,
      barHidden: bar.classList.contains("hidden"),
      above: Math.round(n.top - s.bottom),
      below: Math.round(s.top - n.bottom),
      dx: Math.round((s.left + s.width / 2) - (n.left + n.width / 2)),
      w: Math.round(s.width),
      h: Math.round(s.height),
      hostW: Math.round(document.getElementById("library-view-whiteboard").getBoundingClientRect().width),
      hostRight: Math.round(document.getElementById("library-view-whiteboard").getBoundingClientRect().right),
      hostLeft: Math.round(document.getElementById("library-view-whiteboard").getBoundingClientRect().left),
      right: Math.round(s.right),
      left: Math.round(s.left),
      view: window.innerWidth,
      pageScroll: document.documentElement.scrollWidth,
    };
  }, kidId);
  check("a map node gets the strip and the board's context bar stands down",
    placed.stripShown && placed.barHidden, JSON.stringify(placed));
  check("the strip sits clear of the node and centred on it",
    // Above the node, or below it when it no longer fits above: that is
    // `wbUpdateSelectionBar`'s own documented fallback, and at 390 the strip
    // is two rows tall and takes it. Centred on the node unless the canvas is
    // too narrow to centre it there, where the 8px clamp pins it inside.
    // ...or pinned against an edge by that clamp, which is what a strip wider
    // than the room beside the node it belongs to has to do. Measured at 1440:
    // the strip is 959px and the node sits right of centre, so centring it
    // would put its right edge past the canvas and it stops 8px inside instead.
    ((placed.above > 20 && placed.above < 90) || (placed.below >= 10 && placed.below < 40))
      && (Math.abs(placed.dx) <= 2 || placed.w >= placed.hostW - 16
        || placed.hostRight - placed.right <= 10 || placed.left - placed.hostLeft <= 10),
    JSON.stringify(placed));
  // At 1440 this is the same single row it always was; at 390 it wraps to two
  // instead of standing 392px wide in a 364px canvas and out of the window.
  // `pageScroll` is reported, not asserted: at 390 the whole shell overflows
  // by 7px (43 elements, `.header-controls` among them), which is nothing to
  // do with the map and is written down in archive/agent-remaining/mindmap.md.
  check("the strip stays inside the canvas",
    placed.w <= placed.hostW && placed.right <= placed.view,
    JSON.stringify({ w: placed.w, hostW: placed.hostW, right: placed.right,
      view: placed.view, pageScroll: placed.pageScroll, h: placed.h }));

  const boardBar = await page.evaluate(() => {
    // A board's own object still gets the board's bar: the split is the map's,
    // not a replacement of the bar everywhere.
    const strip = document.getElementById("wb-map-strip");
    clearWbSelection();
    return strip.classList.contains("hidden");
  });
  check("clearing the selection puts the strip away", boardBar === true);

  // --- what the strip writes -----------------------------------------------
  await page.evaluate((id) => selectWbItem("object", id), kidId);
  await page.waitForTimeout(300);
  // Bold and italic are behind the strip's Text door since MINDMAP_PLAN §13b,
  // so a person presses the door and then the control, and so does this: a
  // `page.click` on a control inside a closed menu waits for a visibility
  // that never arrives, which is how this sweep reports the regrouping.
  await page.click('#wb-map-strip [aria-controls="wb-map-text-menu"]');
  await page.waitForTimeout(400);
  await page.click("#wb-map-bold");
  await page.waitForTimeout(700);
  await page.click("#wb-map-italic");
  await page.waitForTimeout(700);
  // Shut it with its own toggle, not with Escape: Escape on a map clears the
  // selection, and everything below this line is about the topic still being
  // the selected one.
  await page.click('#wb-map-strip [aria-controls="wb-map-text-menu"]');
  await page.waitForTimeout(300);
  const marks = await page.evaluate((id) => {
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    const text = node.querySelector(".wb-map-text");
    const obj = wbMapIndex().byId.get(id);
    return {
      bold: obj.data?.bold, italic: obj.data?.italic,
      weight: getComputedStyle(text).fontWeight,
      style: getComputedStyle(text).fontStyle,
      pressed: document.getElementById("wb-map-bold").getAttribute("aria-pressed"),
    };
  }, kidId);
  check("bold and italic are stored and drawn",
    marks.bold === true && marks.italic === true
      && Number(marks.weight) >= 600 && marks.style === "italic"
      && marks.pressed === "true",
    JSON.stringify(marks));

  const sized = await page.evaluate(async (id) => {
    const before = getComputedStyle(
      document.querySelector(`.wb-object[data-id="${id}"] .wb-map-text`)).fontSize;
    const select = document.getElementById("wb-map-text-size");
    select.value = "25";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 900));
    const after = getComputedStyle(
      document.querySelector(`.wb-object[data-id="${id}"] .wb-map-text`)).fontSize;
    return { before, after, stored: wbMapIndex().byId.get(id).data?.font_size };
  }, kidId);
  check("the size select changes the node's own text size",
    sized.stored === 25 && parseFloat(sized.after) > parseFloat(sized.before),
    JSON.stringify(sized));

  const aligned = await page.evaluate(async (id) => {
    const select = document.getElementById("wb-map-align");
    select.value = "center";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 900));
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    return {
      stored: wbMapIndex().byId.get(id).data?.align,
      align: getComputedStyle(node.querySelector(".wb-map-text")).textAlign,
    };
  }, kidId);
  check("alignment is stored and drawn", aligned.stored === "center" && aligned.align === "center",
    JSON.stringify(aligned));

  const iconed = await page.evaluate(async (id) => {
    const select = document.getElementById("wb-map-strip-icon");
    select.value = "star";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 900));
    const icon = document.querySelector(`.wb-object[data-id="${id}"] .wb-map-node-icon`);
    return {
      stored: wbMapIndex().byId.get(id).data?.icon,
      cls: icon ? icon.className : "",
      shown: icon ? !icon.hidden : false,
      w: icon ? Math.round(icon.getBoundingClientRect().width) : 0,
    };
  }, kidId);
  check("an icon is stored, shown and drawn from Phosphor",
    iconed.stored === "star" && iconed.cls.includes("ph-star") && iconed.shown && iconed.w > 6,
    JSON.stringify(iconed));

  // The four shapes (§12.1 item 3). Measured on the node, not on the select:
  // the radius and the surface are what a shape *is*, and a select that
  // stores a value nothing draws is the failure worth catching.
  const shaped = await page.evaluate(async (id) => {
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    const select = document.getElementById("wb-map-shape");
    const read = () => {
      const cs = getComputedStyle(node);
      return {
        radius: Math.round(parseFloat(cs.borderTopLeftRadius)),
        fill: cs.backgroundColor,
        spine: cs.borderLeftColor,
        w: Math.round(node.getBoundingClientRect().width),
        h: Math.round(node.getBoundingClientRect().height),
      };
    };
    const rounded = read();
    const out = { rounded };
    for (const value of ["pill", "rect", "none"]) {
      select.value = value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      await new Promise((r) => setTimeout(r, 900));
      out[value] = { ...read(), stored: wbMapIndex().byId.get(id).data?.shape,
        shown: node.dataset.shape };
    }
    select.value = "";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 900));
    out.back = { ...read(), stored: wbMapIndex().byId.get(id).data?.shape ?? null,
      shown: node.dataset.shape ?? null };
    return out;
  }, kidId);
  check("each of the four shapes is stored and drawn",
    shaped.pill.stored === "pill" && shaped.pill.radius > shaped.rounded.radius
      && shaped.rect.stored === "rect" && shaped.rect.radius === 0
      //: Plain takes the box and its edge away, not the fill: a fill is its own
      //: choice (or the level's, decision 39) and `.wb-map-filled` is drawn
      //: after `[data-shape="none"]`, so the tint the rounded one had stays.
      && shaped.none.stored === "none" && shaped.none.fill === shaped.rounded.fill
      && shaped.none.spine === "rgba(0, 0, 0, 0)"
      && shaped.back.stored === null && shaped.back.shown === null
      && shaped.back.radius === shaped.rounded.radius,
    JSON.stringify(shaped));
  // A shape may not resize the node: the layout, the edge anchors and both
  // rings all measure this box, so a plain topic that lost its 5.5px of
  // border would move under everything already drawn against it.
  check("and no shape changes the size of the node",
    [shaped.pill, shaped.rect, shaped.none, shaped.back]
      .every((s) => s.w === shaped.rounded.w && s.h === shaped.rounded.h),
    JSON.stringify({ rounded: [shaped.rounded.w, shaped.rounded.h],
      none: [shaped.none.w, shaped.none.h] }));

  // Read back from the server, which is the only proof the schema kept them:
  // a field Pydantic does not name is dropped silently on the way in, and the
  // browser's own copy would still be showing the value it sent.
  const persisted = await page.evaluate(async (id) => {
    await fetchWhiteboardState();
    const obj = (wbState.objects || []).find((o) => o.id === id);
    return obj ? { bold: obj.data?.bold, italic: obj.data?.italic,
      size: obj.data?.font_size, align: obj.data?.align, icon: obj.data?.icon } : null;
  }, kidId);
  check("and every one of them comes back from the server",
    persisted && persisted.bold === true && persisted.italic === true
      && persisted.size === 25 && persisted.align === "center" && persisted.icon === "star",
    JSON.stringify(persisted));

  // --- the link ------------------------------------------------------------
  const linked = await page.evaluate(async (id) => {
    const obj = (wbState.objects || []).find((o) => o.id === id);
    await wbMapSetNodeStyle(obj, { link: "https://example.org/notes" });
    await new Promise((r) => setTimeout(r, 600));
    const marker = document.querySelector(`.wb-object[data-id="${id}"] .wb-map-link`);
    return { stored: obj.data?.link, shown: marker ? !marker.hidden : false };
  }, kidId);
  check("a topic's link is stored and marked on the node",
    linked.stored === "https://example.org/notes" && linked.shown, JSON.stringify(linked));

  const refused = await page.evaluate(async (id) => {
    const obj = (wbState.objects || []).find((o) => o.id === id);
    try {
      await window.apiJson(`/whiteboard/objects/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          kind: obj.kind, x: obj.x, y: obj.y, width: obj.width, height: obj.height,
          data: { ...obj.data, link: "javascript:alert(1)" },
        }),
      });
      return "accepted";
    } catch (e) {
      return "refused";
    }
  }, kidId);
  check("and a javascript: link is refused by the schema", refused === "refused", refused);

  // --- the node radial (§12.1 item 3) ---------------------------------------
  // Opened by the gesture, not by calling the function: the point of the ring
  // is that right-click reaches it.
  await page.evaluate((id) => selectWbItem("object", id), kidId);
  await page.waitForTimeout(300);
  await frame();
  await page.click(`.wb-object[data-id="${kidId}"]`, { button: "right" });
  await page.waitForTimeout(500);
  const ring = await page.evaluate((id) => {
    const el = document.getElementById("wb-map-radial");
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    const n = node.getBoundingClientRect();
    const cx = n.left + n.width / 2, cy = n.top + n.height / 2;
    // The pie-ring rewrite (ccd1b48) made every slot's own box the whole
    // ring's square (clip-path only clips the paint), so averaging slot
    // centres no longer finds the ring's own centre, it always collapses to
    // that same square's own centre regardless of where the ring sits. The
    // ring itself is width:0 height:0, positioned at its own centre, so its
    // own rect's left/top *is* that centre; each slot's real radius is its
    // wedge's middle radius, from `_sector` (wbFitMapRadialBand).
    const o = el.getBoundingClientRect();
    const slots = [...el.querySelectorAll(".wb-map-radial-slot")].filter((s) => s._sector);
    const radii = slots.map((s) => Math.round((s._sector.inner + s._sector.outer) / 2));
    return {
      open: !el.classList.contains("hidden"),
      role: el.getAttribute("role"),
      flat: document.querySelector(".wb-ctx-menu:not(.hidden)") === null,
      n: slots.length,
      radii,
      spread: radii.length ? Math.max(...radii) - Math.min(...radii) : null,
      // A node near an edge slides its ring inside the window
      // (`wbPlaceMapRadial`); how far it has moved, bounded by the ring's
      // reach so that it still lands on the topic it belongs to.
      offset: Math.round(Math.hypot(o.left - cx, o.top - cy)),
    };
  }, kidId);
  check("right-click on a topic opens the ring, not the board's flat menu",
    ring.open && ring.flat && ring.n === 6 && ring.role === "toolbar",
    JSON.stringify({ open: ring.open, flat: ring.flat, n: ring.n, role: ring.role }));
  // Six since §12.5, which took the other two to the topic's own menu.
  check("its six slots sit on one circle around the node",
    ring.spread <= 2 && Math.min(...ring.radii) > 40 && ring.offset <= 82,
    JSON.stringify({ radii: ring.radii, spread: ring.spread, offset: ring.offset }));

  // Alt re-labels the two add slots rather than keeping the swap a secret.
  await page.keyboard.down("Alt");
  await page.waitForTimeout(250);
  const alted = await page.evaluate(() => ({
    icon: document.querySelector("#wb-radial-child i").className,
    danger: document.getElementById("wb-radial-child").classList.contains("wb-map-radial-danger"),
    title: document.getElementById("wb-radial-sibling").title,
  }));
  await page.keyboard.up("Alt");
  await page.waitForTimeout(250);
  const unalted = await page.evaluate(() =>
    document.querySelector("#wb-radial-child i").className);
  check("Alt turns the add slots into the remove slots, and says so",
    alted.icon.includes("ph-trash") && alted.danger
      && /Remove this topic only/.test(alted.title)
      && unalted.includes("arrow-elbow-down-right"),
    JSON.stringify({ alted, unalted }));

  // Cutting a topic free left the ring for the topic's own menu (§12.5), and
  // there it is not offered at all on a trunk rather than offered and refused:
  // a menu is a list of what you can do, so the item that cannot apply is the
  // one that is not written. The menu is opened from the keyboard (Shift+F10),
  // which is also the §12.5 claim that the menu is reachable without a pointer.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  const rootId = await page.evaluate(() => wbMapIndex().roots[0].id);
  await page.evaluate((id) => selectWbItem("object", id), rootId);
  await frame();
  await page.keyboard.press("Shift+F10");
  await page.waitForTimeout(400);
  const trunkMenu = await page.evaluate(() =>
    [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")].map((i) => i.textContent.trim()));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  await page.evaluate((id) => selectWbItem("object", id), kidId);
  await frame();
  await page.keyboard.press("Shift+F10");
  await page.waitForTimeout(400);
  const kidMenu = await page.evaluate(() =>
    [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")].map((i) => i.textContent.trim()));
  const cutOf = (rows) => rows.filter((r) => /Cut this topic free/.test(r)).length;
  check("cutting free is offered on a branch and withheld on a trunk",
    cutOf(kidMenu) === 1 && cutOf(trunkMenu) === 0 && trunkMenu.length > 6,
    `trunk ${trunkMenu.length} items, branch ${kidMenu.length}`);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);

  // Copy a branch: a grandchild first, so there is a shape to copy.
  await page.evaluate(async (id) => {
    await wbMapAddChild(id);
  }, kidId);
  await page.waitForTimeout(1700);
  await page.keyboard.press("Escape");
  const before = await page.evaluate(() => wbMapIndex().nodes.length);
  await page.evaluate((id) => selectWbItem("object", id), kidId);
  await frame();
  // Copy a branch is the topic's menu now too (§12.5), reached by its words.
  await page.keyboard.press("Shift+F10");
  await page.waitForTimeout(400);
  await page.evaluate(() => {
    const row = [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")]
      .find((i) => /Copy this branch/.test(i.textContent));
    row.click();
  });
  await page.waitForTimeout(3000);
  const copied = await page.evaluate((id) => {
    const i = wbMapIndex();
    const source = i.byId.get(id);
    const siblings = i.childrenOf.get(source.parent_id) || [];
    const twin = siblings.find((o) => o.id !== id && o.data?.icon === "star");
    return {
      n: i.nodes.length,
      twin: Boolean(twin),
      twinKids: twin ? (i.childrenOf.get(twin.id) || []).length : 0,
      style: twin ? { icon: twin.data?.icon, bold: twin.data?.bold, size: twin.data?.font_size } : null,
    };
  }, kidId);
  check("copy branch duplicates the whole branch beside it, styling and all",
    copied.n === before + 2 && copied.twin && copied.twinKids === 1
      && copied.style.bold === true && copied.style.size === 25,
    JSON.stringify(copied));

  // Label the line into a topic, and see it drawn.
  const labelled = await page.evaluate(async (id) => {
    const node = wbMapIndex().byId.get(id);
    await wbMapSetNodeStyle(node, { edge_label: "because" });
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 400));
    const text = document.querySelector(".wb-map-edges .wb-map-edge-label");
    const edge = document.querySelector(`.wb-map-edge[data-child="${id}"]`);
    if (!text || !edge) return { drawn: false };
    const t = text.getBoundingClientRect(), e = edge.getBoundingClientRect();
    return {
      drawn: true,
      words: text.textContent,
      onTheEdge: t.left > e.left - 40 && t.right < e.right + 40,
      size: getComputedStyle(text).fontSize,
    };
  }, kidId);
  check("a line's label is drawn on the line it belongs to",
    labelled.drawn && labelled.words === "because" && labelled.onTheEdge,
    JSON.stringify(labelled));

  // Sever, then put it back: the map keeps one more trunk and then loses it.
  const severed = await page.evaluate(async (id) => {
    const roots = wbMapIndex().roots.length;
    await wbMapSever(id);
    await new Promise((r) => setTimeout(r, 1200));
    const after = wbMapIndex();
    return {
      roots, now: after.roots.length,
      parent: after.byId.get(id).parent_id,
      colour: after.byId.get(id).data?.color,
    };
  }, kidId);
  check("sever makes a topic a trunk of its own, branch and all",
    severed.now === severed.roots + 1 && severed.parent === null, JSON.stringify(severed));

  // Back to the branch clears everything the strip and the ring can set.
  const reset = await page.evaluate(async (id) => {
    await wbMapResetToBranch(id);
    await new Promise((r) => setTimeout(r, 900));
    await fetchWhiteboardState();
    const obj = (wbState.objects || []).find((o) => o.id === id);
    return { bold: obj.data?.bold, icon: obj.data?.icon, size: obj.data?.font_size,
      align: obj.data?.align, link: obj.data?.link, label: obj.data?.edge_label };
  }, kidId);
  check("back to the branch drops every look the strip and the ring can set",
    reset && !reset.bold && !reset.icon && !reset.size && !reset.align
      && !reset.link && !reset.label,
    JSON.stringify(reset));

  // --- the link radial (§12.1 item 4) ---------------------------------------
  // Rebuild a parent/child pair: the sever above left `kidId` a trunk.
  await page.evaluate(async (id) => {
    const roots = wbMapIndex().roots;
    const other = roots.find((r) => r.id !== id);
    await window.apiJson(`/whiteboard/boards/${window.currentBoardId}/nodes/${id}/move`, {
      method: "PUT", body: JSON.stringify({ parent_id: other.id }),
    });
    await fetchWhiteboardState();
    renderWhiteboardNow();
  }, kidId);
  await page.waitForTimeout(900);

  const hit = await page.evaluate((id) => {
    const h = document.querySelector(`.wb-map-edge-hit[data-child="${id}"]`);
    const line = document.querySelector(`.wb-map-edge[data-child="${id}"]`);
    if (!h || !line) return null;
    return {
      width: getComputedStyle(h).strokeWidth,
      lineWidth: getComputedStyle(line).strokeWidth,
      events: getComputedStyle(h).pointerEvents,
      groupEvents: getComputedStyle(document.querySelector(".wb-map-edges")).pointerEvents,
      // NOT the same `d` as the visible line, and deliberately: a tree edge's
      // default shape is a ribbon, a filled closed outline, and a stroke
      // around a closed shape is a hit area shaped like a hoop with a hole
      // down the middle of the line it is meant to catch. So the hit path is
      // the centreline (`wbMapEdgePathD`) while the drawn one is the ribbon.
      // What can be measured is that the two cover the same run of the canvas:
      // the ribbon is that centreline thickened, so their boxes agree to
      // within the ribbon's own half-width.
      open: !/[zZ]/.test(h.getAttribute("d")),
      box: (() => {
        const a = h.getBBox();
        const b = line.getBBox();
        return [a.x - b.x, a.y - b.y, a.width - b.width, a.height - b.height].map((n) => Math.round(n));
      })(),
    };
  }, kidId);
  check("a line has a target wide enough to hit, over an inert group",
    hit && hit.events === "stroke" && hit.groupEvents === "none"
      && parseFloat(hit.width) >= 12 && parseFloat(hit.lineWidth) <= 3
      && hit.open && hit.box.every((n) => Math.abs(n) <= 12),
    JSON.stringify(hit));

  const box = await page.evaluate((id) => {
    const h = document.querySelector(`.wb-map-edge-hit[data-child="${id}"]`);
    const r = h.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }, kidId);
  await page.mouse.click(box.x, box.y, { button: "right" });
  await page.waitForTimeout(500);
  const linkRing = await page.evaluate(() => {
    const el = document.getElementById("wb-map-link-radial");
    return {
      open: !el.classList.contains("hidden"),
      slots: el.querySelectorAll(".wb-map-radial-slot").length,
      words: [...el.querySelectorAll(".wb-map-radial-slot")].map((b) => b.id),
      nodeRingClosed: document.getElementById("wb-map-radial").classList.contains("hidden"),
    };
  });
  check("right-click on a line opens the line's own ring, and it keeps three",
    linkRing.open && linkRing.slots === 3 && linkRing.nodeRingClosed
      && linkRing.words.join(",") === "wb-link-reverse,wb-link-label,wb-link-cut",
    JSON.stringify(linkRing));

  // The three line shapes are one picker in the strip now (§12.5: a shape is a
  // look, and the ring's curve/elbow/straight wrote the same field the strip
  // does). Driven here through the strip, on the child whose line it is.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(250);
  await page.evaluate((id) => selectWbItem("object", id), kidId);
  await page.waitForTimeout(500);
  // Behind the strip's Branch line door since §13b, so it is opened first,
  // the way a person opens it.
  await page.click('#wb-map-strip [aria-controls="wb-map-line-menu"]');
  await page.waitForTimeout(400);
  // The native select is the enhanced picker's hidden twin now; set it the way
  // its listener hears it (force skips the visibility wait on the hidden one).
  await page.selectOption("#wb-map-edge-shape", "elbow", { force: true });
  await page.waitForTimeout(1100);
  await page.click('#wb-map-strip [aria-controls="wb-map-line-menu"]');
  await page.waitForTimeout(250);
  const elbowed = await page.evaluate((id) => {
    const line = document.querySelector(`.wb-map-edge[data-child="${id}"]`);
    return { stored: wbMapIndex().byId.get(id).data?.edge_style, d: line.getAttribute("d") };
  }, kidId);
  check("the elbow is stored and the line is redrawn with corners",
    elbowed.stored === "elbow" && elbowed.d.includes("L") && !elbowed.d.includes("C"),
    JSON.stringify(elbowed));

  const dashed = await page.evaluate(async (id) => {
    const node = wbMapIndex().byId.get(id);
    await wbMapSetNodeStyle(node, { edge_dashed: true });
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 500));
    const line = document.querySelector(`.wb-map-edge[data-child="${id}"]`);
    return { dash: getComputedStyle(line).strokeDasharray, cls: line.getAttribute("class") };
  }, kidId);
  check("a dashed line is drawn dashed", /\d/.test(dashed.dash) && dashed.cls.includes("dashed"),
    JSON.stringify(dashed));

  const reversed = await page.evaluate(async (id) => {
    const i = wbMapIndex();
    const child = i.byId.get(id);
    const parentId = child.parent_id;
    await wbMapReverseEdge(id);
    await new Promise((r) => setTimeout(r, 2000));
    const after = wbMapIndex();
    return {
      parentId,
      childNowParentOf: (after.childrenOf.get(id) || []).map((o) => o.id).includes(parentId),
      childParent: after.byId.get(id).parent_id,
    };
  }, kidId);
  check("turning a line around swaps the two topics without a cycle",
    reversed.childNowParentOf && reversed.childParent !== reversed.parentId,
    JSON.stringify(reversed));

  // --- the mid-line plus (§12.1 item 5) -------------------------------------
  const plus = await page.evaluate(() => {
    const layer = document.querySelector(".wb-map-plus-layer");
    const buttons = [...document.querySelectorAll(".wb-map-edge-plus")];
    const edges = document.querySelectorAll(".wb-map-edges .wb-map-edge").length;
    if (!layer || !buttons.length) return null;
    const first = buttons[0];
    const child = first.nextElementSibling;
    return {
      n: buttons.length,
      edges,
      hiddenAtRest: getComputedStyle(first).opacity === "0",
      grabbable: getComputedStyle(first).pointerEvents === "auto",
      layerInert: getComputedStyle(layer).pointerEvents === "none",
      onALine: Boolean(child === null || true),
    };
  });
  check("every visible line carries a mid-point plus, invisible until pointed at",
    plus && plus.n === plus.edges && plus.hiddenAtRest && plus.grabbable && plus.layerInert,
    JSON.stringify(plus));

  // It lands on the line it belongs to: measured against the edge's own path.
  const onLine = await page.evaluate(() => {
    const button = document.querySelector(".wb-map-edge-plus");
    const b = button.getBoundingClientRect();
    const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
    let best = Infinity;
    for (const edge of document.querySelectorAll(".wb-map-edges .wb-map-edge")) {
      const len = edge.getTotalLength();
      for (let i = 0; i <= 40; i += 1) {
        const p = edge.getPointAtLength((len * i) / 40);
        const svg = edge.ownerSVGElement;
        const pt = svg.createSVGPoint();
        pt.x = p.x; pt.y = p.y;
        const screen = pt.matrixTransform(edge.getScreenCTM());
        best = Math.min(best, Math.hypot(screen.x - cx, screen.y - cy));
      }
    }
    return Math.round(best);
  });
  check("and it sits on the line, not beside it", onLine <= 6, `${onLine}px from the nearest line`);

  const inserted = await page.evaluate(async () => {
    const before = wbMapIndex().nodes.length;
    const button = document.querySelector(".wb-map-edge-plus");
    const parentId = Number(document.querySelector(".wb-map-edges .wb-map-edge")
      .getAttribute("data-parent"));
    const childId = Number(document.querySelector(".wb-map-edges .wb-map-edge")
      .getAttribute("data-child"));
    button.click();
    await new Promise((r) => setTimeout(r, 2500));
    const i = wbMapIndex();
    const child = i.byId.get(childId);
    const middle = child ? i.byId.get(child.parent_id) : null;
    return {
      before, after: i.nodes.length,
      middleIsNew: Boolean(middle) && middle.id !== parentId,
      middleUnderParent: middle ? middle.parent_id === parentId : false,
    };
  });
  await page.keyboard.press("Escape");
  check("the plus puts a new topic between the two it was drawn on",
    inserted.after === inserted.before + 1 && inserted.middleIsNew
      && inserted.middleUnderParent,
    JSON.stringify(inserted));

  // --- the corner resize grip (§12.1 item 6; INBOX 610 replaced the text-size
  // grip, `.wb-map-size-grip`, with `.wb-map-resize-grip`) ---------------------
  // Plain drag resizes the box; Shift scales the words with it. Driven with the
  // real mouse: the grip takes pointer capture, which a synthetic event with an
  // invented pointer id cannot.
  await page.mouse.move(4, 4);
  await page.waitForTimeout(250);
  const grip0 = await page.evaluate((id) => {
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    const grip = node.querySelector(".wb-map-resize-grip");
    if (!grip) return null;
    // At rest means neither hovered nor selected: the node is still selected
    // from the checks above, so the class comes off to read the resting state
    // and goes straight back on.
    node.classList.remove("wb-selected");
    const atRest = getComputedStyle(grip).display;
    node.classList.add("wb-selected");
    const shown = getComputedStyle(grip).display;
    const r = grip.getBoundingClientRect();
    return { atRest, shown, cursor: getComputedStyle(grip).cursor, w: Math.round(r.width), h: Math.round(r.height),
      x: r.left + r.width / 2, y: r.top + r.height / 2,
      tool: document.getElementById("whiteboard-container").dataset.currentTool };
  }, kidId);
  check("the corner grip is absent until the node is selected or pointed at, and says it drags",
    grip0 && grip0.atRest === "none" && grip0.shown === "block" && grip0.cursor === "nwse-resize"
      && grip0.w >= 24 && grip0.h >= 24,
    JSON.stringify(grip0));
  const dragGrip = async (g, dx, dy, shift) => {
    if (shift) await page.keyboard.down("Shift");
    await page.mouse.move(g.x, g.y);
    await page.mouse.down();
    await page.mouse.move(g.x + dx / 2, g.y + dy / 2, { steps: 4 });
    await page.mouse.move(g.x + dx, g.y + dy, { steps: 4 });
    const live = await page.evaluate((id) => {
      const node = document.querySelector(`.wb-object[data-id="${id}"]`);
      return { w: node.offsetWidth, h: node.offsetHeight, font: parseFloat(getComputedStyle(node).fontSize) };
    }, kidId);
    await page.mouse.up();
    if (shift) await page.keyboard.up("Shift");
    await page.waitForTimeout(1300);
    const stored = await page.evaluate(async (id) => {
      await fetchWhiteboardState();
      const o = (wbState.objects || []).find((x) => x.id === id);
      return { w: o?.width, h: o?.height, font: o?.data?.font_size };
    }, kidId);
    return { live, stored };
  };
  const regrip = () => page.evaluate((id) => {
    const node = document.querySelector(`.wb-object[data-id="${id}"]`);
    const r = node.querySelector(".wb-map-resize-grip").getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2,
      w: node.offsetWidth, font: parseFloat(getComputedStyle(node).fontSize) };
  }, kidId);
  await page.evaluate(() => {
    const orig = window.wbMapStartResizeDrag;
    window.wbMapStartResizeDrag = (g, e, d) => {
      window.__dd = { same: d === wbMapIndex().byId.get(d.id), font: d.data?.font_size, curFont: wbMapIndex().byId.get(d.id)?.data?.font_size };
      return orig(g, e, d);
    };
  });
  const g1 = await regrip();
  const plain = await dragGrip(g1, 70, 30, false);
  // The grip is built once, as the node enters; a state refresh replaces the
  // object and the grip's closure keeps the old one (`wbMapLiveDatum`). Here
  // the sweep has refreshed the state several times since the node was built.
  const handed = await page.evaluate(() => window.__dd);
  check("the grip is handed the topic's current object, not the one it was built with",
    handed && handed.same === true && handed.font === handed.curFont, JSON.stringify(handed));
  check("dragging the grip grows the box, stores width and height, and leaves the text alone",
    plain.live.w > g1.w && plain.stored.w === plain.live.w && plain.stored.h >= 40
      && plain.live.font === g1.font,
    JSON.stringify({ before: g1, ...plain }));
  const g2 = await regrip();
  const shifted = await dragGrip(g2, 120, 0, true);
  check("with Shift the words scale with the box and the size is stored",
    shifted.live.font > g2.font && shifted.stored.font === Math.round(shifted.live.font),
    JSON.stringify({ before: g2, ...shifted }));
  const g3 = await regrip();
  const smallest = await dragGrip(g3, -2000, -2000, true);
  check("and it cannot be dragged smaller than a node can read at (72 x 40, text 10)",
    smallest.live.w >= 72 && smallest.live.font >= 10 && smallest.stored.w >= 72 && smallest.stored.h >= 40,
    JSON.stringify(smallest));
  const g4 = await regrip();
  const biggest = await dragGrip(g4, 1500, 0, true);
  check("nor have its text pass the largest size (44)",
    biggest.live.font <= 44 && (biggest.stored.font ?? 0) <= 44,
    JSON.stringify(biggest));

  // --- drag a branch onto a new parent (§12.1 item 8) -----------------------
  // A fresh map, so the shape under test is plain: root, two children, and a
  // grandchild under the first child.
  await newBoard(page, "Transplant map", "map");
  const ids = await page.evaluate(async () => {
    const root = wbMapIndex().roots[0];
    const a = await wbMapAddChild(root.id);
    const b = await wbMapAddChild(root.id);
    const kid = await wbMapAddChild(a.id);
    return { root: root.id, a: a.id, b: b.id, kid: kid.id };
  });
  await page.waitForTimeout(3600);
  await page.keyboard.press("Escape");

  // The branch follows the topic, and the topic under the pointer lights up.
  const dragging = await page.evaluate((ids) => {
    const container = document.getElementById("whiteboard-container");
    const rect = container.getBoundingClientRect();
    const t = d3.zoomTransform(container);
    const at = (node) => {
      const size = wbMapNodeSize(node);
      const [sx, sy] = t.apply([node.x + size.w / 2, node.y + size.h / 2]);
      return { x: rect.left + sx, y: rect.top + sy };
    };
    const i = wbMapIndex();
    const a = i.byId.get(ids.a), b = i.byId.get(ids.b);
    const kidBefore = { x: i.byId.get(ids.kid).x, y: i.byId.get(ids.kid).y };
    const from = at(a), to = at(b);
    const el = document.querySelector(`.wb-object[data-id="${ids.a}"]`);
    const mouse = (type, x, y, buttons) => new MouseEvent(type, {
      bubbles: true, cancelable: true, view: window, button: 0, buttons,
      clientX: x, clientY: y,
    });
    el.dispatchEvent(mouse("mousedown", from.x, from.y, 1));
    window.dispatchEvent(mouse("mousemove", from.x + 6, from.y + 4, 1));
    window.dispatchEvent(mouse("mousemove", to.x, to.y, 1));
    const lit = document.querySelectorAll(".wb-map-drop-target");
    const kidNow = wbMapIndex().byId.get(ids.kid);
    return {
      lit: lit.length,
      litId: lit.length ? Number(lit[0].getAttribute("data-id")) : null,
      kidMoved: Math.round(Math.hypot(kidNow.x - kidBefore.x, kidNow.y - kidBefore.y)),
      to,
    };
  }, ids);
  check("dragging a topic takes its branch and lights the topic under the pointer",
    dragging.lit === 1 && dragging.litId === ids.b && dragging.kidMoved > 10,
    JSON.stringify({ lit: dragging.lit, litId: dragging.litId, kidMoved: dragging.kidMoved }));

  const dropped = await page.evaluate(async (ids) => {
    const container = document.getElementById("whiteboard-container");
    const rect = container.getBoundingClientRect();
    const t = d3.zoomTransform(container);
    const i = wbMapIndex();
    const b = i.byId.get(ids.b);
    const size = wbMapNodeSize(b);
    const [sx, sy] = t.apply([b.x + size.w / 2, b.y + size.h / 2]);
    window.dispatchEvent(new MouseEvent("mouseup", {
      bubbles: true, cancelable: true, view: window, button: 0, buttons: 0,
      clientX: rect.left + sx, clientY: rect.top + sy,
    }));
    await new Promise((r) => setTimeout(r, 3000));
    await fetchWhiteboardState();
    const after = wbMapIndex();
    return {
      aParent: after.byId.get(ids.a).parent_id,
      kidParent: after.byId.get(ids.kid).parent_id,
      pinned: Boolean(after.byId.get(ids.a).data?.pinned),
      lit: document.querySelectorAll(".wb-map-drop-target").length,
    };
  }, ids);
  check("the drop re-parents the whole branch and clears the cue",
    dropped.aParent === ids.b && dropped.kidParent === ids.a
      && dropped.pinned === false && dropped.lit === 0,
    JSON.stringify(dropped));

  // Ctrl held: the topic goes alone and its children go up to its old parent.
  const alone = await page.evaluate(async (ids) => {
    const container = document.getElementById("whiteboard-container");
    const rect = container.getBoundingClientRect();
    const t = d3.zoomTransform(container);
    const at = (node) => {
      const size = wbMapNodeSize(node);
      const [sx, sy] = t.apply([node.x + size.w / 2, node.y + size.h / 2]);
      return { x: rect.left + sx, y: rect.top + sy };
    };
    const i = wbMapIndex();
    const from = at(i.byId.get(ids.a)), to = at(i.byId.get(ids.root));
    const el = document.querySelector(`.wb-object[data-id="${ids.a}"]`);
    const mouse = (type, x, y, buttons) => new MouseEvent(type, {
      bubbles: true, cancelable: true, view: window, button: 0, buttons,
      clientX: x, clientY: y, ctrlKey: true,
    });
    el.dispatchEvent(mouse("mousedown", from.x, from.y, 1));
    window.dispatchEvent(mouse("mousemove", from.x + 6, from.y + 4, 1));
    window.dispatchEvent(mouse("mousemove", to.x, to.y, 1));
    window.dispatchEvent(mouse("mouseup", to.x, to.y, 0));
    await new Promise((r) => setTimeout(r, 3000));
    await fetchWhiteboardState();
    const after = wbMapIndex();
    return {
      aParent: after.byId.get(ids.a).parent_id,
      kidParent: after.byId.get(ids.kid).parent_id,
      oldParent: ids.b,
    };
  }, ids);
  check("Ctrl held moves the topic alone and lets its branch up to its old parent",
    alone.aParent === ids.root && alone.kidParent === ids.b, JSON.stringify(alone));

  // A branch cannot be dropped inside itself: the offer is never made.
  const noCycle = await page.evaluate((ids) => {
    // A pair that really is ancestor and descendant *now*: the moves above
    // have rearranged the tree, and asking about a pair that used to be
    // related would have measured nothing (it did, once).
    const i = wbMapIndex();
    const a = i.byId.get(ids.root);
    const kid = wbMapSubtree(i, ids.root).find((o) => o.id !== ids.root);
    const container = document.getElementById("whiteboard-container");
    const rect = container.getBoundingClientRect();
    const t = d3.zoomTransform(container);
    const size = wbMapNodeSize(kid);
    const [sx, sy] = t.apply([kid.x + size.w / 2, kid.y + size.h / 2]);
    return wbMapDropTargetAt(a, rect.left + sx, rect.top + sy);
  }, ids);
  check("and a branch is never offered its own descendant as a parent",
    noCycle === null, JSON.stringify(noCycle && { id: noCycle.id, parent: noCycle.parent_id }));

  // --- both rings stay inside the window (§12.1 items 3 and 4) --------------
  // A map grows outward, so the topics nearest an edge are the newest ones,
  // and a ring that loses slots off-screen is least reachable exactly where
  // it is most wanted. Driven by panning the canvas until a real topic sits
  // in the corner, then opening the ring on it with the gesture.
  const cornered = await page.evaluate(() => {
    const container = document.getElementById("whiteboard-container");
    const host = document.getElementById("library-view-whiteboard");
    const hostRect = host.getBoundingClientRect();
    const rect = container.getBoundingClientRect();
    const index = wbMapIndex();
    const node = index.roots[0];
    const size = wbMapNodeSize(node);
    const t = d3.zoomTransform(container);
    // Just inside the left edge, and just under the top bar so the topic is
    // still clickable: the ring reaches 82px, so both edges are short of it
    // and both have to give. (The bar floats over the canvas, which is why
    // the ring's own bound is the canvas minus the bands across it.)
    const bar = document.getElementById("wb-topbar").getBoundingClientRect();
    //: Clear of the board's sidebar rail where there is one (1440): the right
    //: click aimed at a centre 40px in landed on the rail, not on the topic,
    //: and the ring never opened.
    const side = document.getElementById("wb-sidebar");
    const sideRight = side && side.checkVisibility() ? side.getBoundingClientRect().right : hostRect.left;
    const want = { x: Math.max(hostRect.left + 40, sideRight + 40), y: bar.bottom + 20 };
    // Solve for the pan that puts this node's centre there:
    // screen = rect.left + k * world + tx.
    const tx = want.x - rect.left - t.k * (node.x + size.w / 2);
    const ty = want.y - rect.top - t.k * (node.y + size.h / 2);
    d3.select(container).call(wbZoom.transform, d3.zoomIdentity.translate(tx, ty).scale(t.k));
    const live = document.querySelector(`.wb-object[data-id="${node.id}"]`);
    return { id: node.id, want, size, stored: [node.width, node.height], live: live ? [live.offsetWidth, live.offsetHeight] : null };
  });
  // The pan's own transforms are written in a `requestAnimationFrame`
  // (`handleWbZoom`, panlag.js), so the node's new rect is not there in the
  // same tick that asked for the pan: reading it there measured the position
  // it had *before* the pan, and the right-click then landed on bare canvas.
  await page.waitForTimeout(600);
  // Then correct the pan against where the node actually landed, and say by
  // how much: the arithmetic above goes through `wbMapNodeSize`, and a
  // node whose rendered box is not the size that function reports puts the
  // whole calculation out (measured 47px out at 390x844). One correction is
  // enough because the second pan is measured, not derived.
  const at = await page.evaluate(({ id, want }) => {
    const container = document.getElementById("whiteboard-container");
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    const first = el.getBoundingClientRect();
    const t = d3.zoomTransform(container);
    const dx = want.x - (first.left + first.width / 2);
    const dy = want.y - (first.top + first.height / 2);
    if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
      d3.select(container).call(wbZoom.transform,
        d3.zoomIdentity.translate(t.x + dx, t.y + dy).scale(t.k));
    }
    return { drift: [Math.round(dx), Math.round(dy)] };
  }, cornered);
  await page.waitForTimeout(500);
  //: The 94px row (OPEN.md: `wbMapNodeSize` and the rendered node disagreed by
  //: 94px at 390x844, once, not reproduced): the first pan is derived from the
  //: reported size, so how far the node landed from where it was aimed IS the
  //: disagreement. Printed every run and held to 4px.
  console.log("corner pan drift (first pan, px):", JSON.stringify(at.drift), "reported size", JSON.stringify(cornered.size), "stored", JSON.stringify(cornered.stored), "rendered", JSON.stringify(cornered.live));
  check("wbMapNodeSize agrees with the rendered box: the first pan lands within 4px", Math.abs(at.drift[0]) <= 4 && Math.abs(at.drift[1]) <= 4, JSON.stringify(at.drift));
  Object.assign(at, await page.evaluate((id) => {
    const box = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect();
    return { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) };
  }, cornered.id));
  await page.mouse.click(at.x, at.y, { button: "right" });
  await page.waitForTimeout(500);
  const ringed = await page.evaluate(() => {
    const el = document.getElementById("wb-map-radial");
    const host = document.getElementById("library-view-whiteboard");
    const hostRect = host.getBoundingClientRect();
    const slotEls = [...el.querySelectorAll(".wb-map-radial-slot")];
    const slots = slotEls.map((b) => b.getBoundingClientRect());
    // Same box for every slot now (the pie ring, ccd1b48): min/max across
    // them still reads the ring's true circular extent (a circle inscribed
    // in that square touches all four of its edges), but a radius has to
    // come from the wedge each slot owns (`_sector`), not from its box.
    const radii = slotEls.filter((s) => s._sector).map((s) => Math.round((s._sector.inner + s._sector.outer) / 2));
    return {
      open: !el.classList.contains("hidden"),
      n: slots.length,
      minLeft: Math.round(Math.min(...slots.map((r) => r.left))),
      minTop: Math.round(Math.min(...slots.map((r) => r.top))),
      maxRight: Math.round(Math.max(...slots.map((r) => r.right))),
      maxBottom: Math.round(Math.max(...slots.map((r) => r.bottom))),
      hostLeft: Math.round(hostRect.left),
      barBottom: Math.round(document.getElementById("wb-topbar").getBoundingClientRect().bottom),
      w: window.innerWidth,
      h: window.innerHeight,
      spread: radii.length ? Math.max(...radii) - Math.min(...radii) : null,
      radius: radii.length ? Math.min(...radii) : 0,
    };
  });
  check("a topic in the corner keeps all six of its ring's slots reachable",
    ringed.open && ringed.n === 6
      && ringed.minLeft >= ringed.hostLeft && ringed.minTop >= ringed.barBottom
      && ringed.maxRight <= ringed.w && ringed.maxBottom <= ringed.h,
    JSON.stringify(ringed));
  check("and the slid ring is still a ring, not six clamped buttons",
    ringed.spread <= 2 && ringed.radius > 60,
    JSON.stringify({ spread: ringed.spread, radius: ringed.radius }));

  // The line ring is placed from the pointer, so the pointer is what this
  // drives: `wbOpenMapLinkRadial`'s own two arguments, at the far corner of
  // the window. The hit target itself has its own check above.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  const linkClamped = await page.evaluate(() => {
    const index = wbMapIndex();
    const child = [...index.byId.values()].find((o) => index.byId.has(o.parent_id));
    wbOpenMapLinkRadial(child.id, window.innerWidth - 6, window.innerHeight - 6);
    const el = document.getElementById("wb-map-link-radial");
    const slots = [...el.querySelectorAll(".wb-map-radial-slot")].map((b) => b.getBoundingClientRect());
    return {
      open: !el.classList.contains("hidden"),
      n: slots.length,
      maxRight: Math.round(Math.max(...slots.map((r) => r.right))),
      maxBottom: Math.round(Math.max(...slots.map((r) => r.bottom))),
      w: window.innerWidth,
      h: window.innerHeight,
    };
  });
  check("a line ring opened at the far corner stays inside the window too",
    linkClamped.open && linkClamped.n === 3
      && linkClamped.maxRight <= linkClamped.w && linkClamped.maxBottom <= linkClamped.h,
    JSON.stringify(linkClamped));

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})();
