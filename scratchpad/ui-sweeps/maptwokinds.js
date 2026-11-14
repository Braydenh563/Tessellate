// **The two kinds of connection, and whether the map surface uses the app's
// own scales** (INBOX 305: "there are two types of connections", and "it just
// feels really unclean and unprofessional").
//
// Part one answers the structural complaint with facts rather than a reading
// of the source: build one map, make a tree edge and a free (cross) link
// between the same kind of nodes, and then ask the running app, for each,
// which gesture opens what, which controls appear, and what a text export
// carries. Both kinds are drawn by the same renderer and look nearly alike,
// which is the whole of why the difference has to be measured at the
// controls rather than looked at.
//
// Part two takes the measurements DOCUMENTS_PLAN section 17 took for the
// live view: the surface's gutters, its rhythm and its type scale, read off
// the computed boxes, and then each value checked against the *token* scales
// read from `:root` in the same browser. A number that is not on the scale is
// the surface writing its own value, which is the measurable half of
// "unclean".
//
//   BASE=http://127.0.0.1:8804 SCRATCH=/tmp/mm-mapread \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/maptwokinds.js
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

  // A trunk with four branches, each with two children: enough that a cross
  // link between two of them is between nodes that are both already in the
  // tree, which is the case that produces a cross link rather than a
  // re-parent (`wbMapJoinByLink`).
  const board = await page.evaluate(async () => {
    const content = ["# Two kinds", "- Trunk"];
    for (let b = 1; b <= 4; b++) {
      content.push(`  - Branch ${b}`);
      content.push(`    - Leaf ${b}a`);
      content.push(`    - Leaf ${b}b`);
    }
    const made = await apiJson("/whiteboard/boards/import", {
      method: "POST",
      body: JSON.stringify({ format: "markdown", content: content.join("\n"), name: "Two kinds" }),
    });
    await openWhiteboardBoard(made.id);
    await new Promise((r) => setTimeout(r, 1200));
    return made;
  });
  check("a map with a tree was made", board && board.id, `${board && board.object_count} nodes`);

  // Make the free link through the code path the connect gesture ends in, so
  // it is the same row the drag would have written.
  const made = await page.evaluate(async () => {
    const index = wbMapIndex();
    const root = index.roots[0];
    const branches = index.childrenOf.get(root.id) || [];
    const a = (index.childrenOf.get(branches[0].id) || [])[0];
    const b = (index.childrenOf.get(branches[3].id) || [])[0];
    const sketch = await apiJson("/whiteboard/sketches", {
      method: "POST",
      body: JSON.stringify({
        board_id: window.currentBoardId,
        x: 0, y: 0, z: 1,
        data: JSON.stringify({
          type: "link-straight", sourceId: a.id, targetId: b.id,
          sourceKind: "object", targetKind: "object", color: "#7dd3c8",
        }),
      }),
    });
    wbState.sketches.push(sketch);
    // What the drag itself now does (`dragEndNode`): a link sketch is only a
    // cross-link once the board tree says so, and this row was written
    // straight to the API rather than drawn.
    await wbRefreshMapState();
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 500));
    return { sketchId: sketch.id, treeChildId: branches[1].id, aId: a.id, bId: b.id };
  });
  check("a free link between two in-tree topics exists", made.sketchId > 0, `sketch ${made.sketchId}`);
  await page.evaluate((id) => { window.__cross = id; }, made.sketchId);

  // Does the backend agree it is a cross link rather than a tree edge?
  const tree = await page.evaluate(() =>
    apiJson(`/whiteboard/boards/${window.currentBoardId}/tree`).then((t) => ({
      crossLinks: (t.cross_links || []).length,
      roots: (t.roots || []).length,
    }))
  );
  show(tree);
  check("the tree endpoint reports it as a cross link", tree.crossLinks === 1, `${tree.crossLinks} cross link(s)`);

  // --- What each kind offers, measured ---
  const controlsIn = (sel) => `(() => {
    const el = document.querySelector("${sel}");
    if (!el) return {present:false};
    const cs = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    const items = [];
    for (const c of el.querySelectorAll("button, select, input")) {
      if (c.hidden || c.closest("[hidden]")) continue;
      if (c.closest(".select-menu") || c.classList.contains("select-opener")) continue;
      const s = getComputedStyle(c);
      if (s.display === "none" || s.visibility === "hidden") continue;
      items.push((c.querySelector(".wb-map-radial-name")?.textContent
        || c.getAttribute("aria-label") || c.title || c.textContent || "").trim().slice(0,40));
    }
    return {present:true, hidden: el.classList.contains("hidden"),
            visible: cs.display !== "none" && !el.classList.contains("hidden"),
            w: Math.round(box.width), h: Math.round(box.height), count: items.length, items};
  })()`;

  // 1. The TREE edge. Right-click the line into a child opens the link ring.
  const treeEdge = await page.evaluate(async (childId) => {
    // The renderer draws a tree edge as a path carrying the child's id.
    const path = document.querySelector(`#whiteboard-canvas [data-map-edge="${childId}"], #whiteboard-canvas [data-edge-child="${childId}"]`);
    return { found: Boolean(path), sel: path ? path.getAttribute("class") : null };
  }, made.treeChildId);
  // Open the ring through the app's own opener rather than guessing a target.
  const treeRing = await page.evaluate(async (childId) => {
    if (typeof wbOpenMapLinkRadial === "function") {
      // It takes the *child's id*, not the node: a tree edge has no row, so
      // the child is what identifies it.
      wbOpenMapLinkRadial(childId, 600, 400);
      await new Promise((r) => setTimeout(r, 300));
      return true;
    }
    return false;
  }, made.treeChildId);
  const treeRingControls = treeRing ? await page.evaluate(controlsIn("#wb-map-link-radial")) : null;
  show({ treeEdgePathFound: treeEdge.found, ringOpened: treeRing, ring: treeRingControls });
  check("the tree edge has a ring of its own", treeRingControls && treeRingControls.count > 0,
    treeRingControls ? `${treeRingControls.count} slots: ${treeRingControls.items.join(", ")}` : "no ring");
  await page.evaluate(() => wbCloseMapLinkRadial && wbCloseMapLinkRadial());

  // The rest of the tree edge's controls live on the child's own strip.
  const stripControls = await page.evaluate(async (childId) => {
    const el = document.querySelector(`#wb-html-layer .wb-map-node[data-id="${childId}"], #wb-html-layer [data-id="${childId}"] .wb-map-node`);
    if (el) el.click();
    await new Promise((r) => setTimeout(r, 600));
    return null;
  }, made.treeChildId);
  const strip = await page.evaluate(controlsIn("#wb-map-strip"));
  show({ strip });
  check("the tree edge's look is set from the topic strip", strip.present, `${strip.count} controls, ${strip.w}x${strip.h}`);

  // 2. The FREE link. Select it and read what the app offers.
  const freeSel = await page.evaluate(async (sketchId) => {
    wbSelectedItem = { kind: "sketch", id: sketchId };
    if (typeof wbUpdateSelectionBar === "function") wbUpdateSelectionBar();
    if (typeof wbSyncContextBar === "function") wbSyncContextBar();
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 500));
    const item = (wbState.sketches || []).find((s) => s.id === sketchId);
    return { kind: typeof wbContextKindOf === "function" ? wbContextKindOf(wbSelectedItem, item) : null };
  }, made.sketchId);
  const ctx = await page.evaluate(controlsIn("#wb-context"));
  const freeRing = await page.evaluate(controlsIn("#wb-map-link-radial"));
  show({ contextKind: freeSel.kind, contextBar: ctx, linkRingVisibleForFreeLink: freeRing.visible });
  //: **Both of these checks were inverted by MINDMAP_PLAN §13c** and the old
  //: wording is kept in the detail so the change is legible: this sweep used
  //: to assert that a cross-link "reads as the board's 'link' row, not the
  //: map's" and that it "does NOT get the map's link ring", which is what
  //: §13.2 measured and what the owner's "there are two types of connections"
  //: was about. The map now answers for both of its own kinds.
  check("a cross-link has no board context row: its surface is the map's", freeSel.kind === null,
    `kind ${freeSel.kind} (was "link")`);
  check("and the board's context bar is not drawn for it", !ctx.visible, `bar visible ${ctx.visible}`);

  // Right-click the cross-link the way a person does: a point on the line
  // itself, after a fit, because a 13-topic map runs off the canvas and a
  // click at the path's bounding-box centre lands on empty space.
  await page.click("#wb-zoom-fit");
  await page.waitForTimeout(900);
  const crossPoint = await page.evaluate(() => {
    const path = document.querySelector(".sketch-group.wb-map-crosslink .sketch-path");
    if (!path) return null;
    // A third of the way along, not the middle: a selected link shows its
    // bend grip at its mid-point, and the grip takes the press (measured: the
    // right-click landed on `circle.wb-link-bend-handle` and did nothing).
    const pt = path.getPointAtLength(path.getTotalLength() * 0.35);
    const m = path.getScreenCTM();
    return { x: pt.x * m.a + pt.y * m.c + m.e, y: pt.x * m.b + pt.y * m.d + m.f };
  });
  check("the cross-link is drawn with the map's own class", Boolean(crossPoint),
    crossPoint ? `mid-point at ${Math.round(crossPoint.x)},${Math.round(crossPoint.y)}` : "no .wb-map-crosslink path");
  if (crossPoint) show({ under: await page.evaluate(([x, y]) => {
    const el = document.elementFromPoint(x, y);
    return el ? `${el.tagName}.${el.getAttribute("class") || ""}` : "none";
  }, [crossPoint.x, crossPoint.y]) });
  if (crossPoint) await page.mouse.click(crossPoint.x, crossPoint.y, { button: "right" });
  await page.waitForTimeout(600);
  const crossRing = await page.evaluate(() => {
    const ring = document.getElementById("wb-map-link-radial");
    const bar = document.getElementById("wb-context");
    return {
      visible: !ring.classList.contains("hidden"),
      slots: [...ring.querySelectorAll(".wb-map-radial-slot")].map((s) => s.querySelector(".wb-map-radial-name").textContent.trim()),
      label: ring.getAttribute("aria-label"),
      caption: ring.querySelector(".wb-map-radial-caption").textContent.trim(),
      barVisible: !bar.classList.contains("hidden"),
    };
  });
  show(crossRing);
  check("right-clicking a cross-link opens the map's own ring", crossRing.visible && !crossRing.barVisible,
    `ring ${crossRing.visible}, board bar ${crossRing.barVisible}`);
  check("and the ring says which of the two kinds it is on",
    crossRing.label.includes("cross-link") && /cross-link/.test(crossRing.caption)
      && crossRing.slots.join(",") === "Reverse,Make branch,Cut",
    `${crossRing.label}: ${crossRing.slots.join(", ")}`);
  await page.evaluate(() => wbCloseMapLinkRadial());

  //: MINDMAP_PLAN 13c's leftover: the selected cross-link's bend grip sits on
  //: its mid-point, in the overlay layer rather than inside the link's own
  //: group, so a right-click there reached neither the link's menu nor the
  //: canvas's and did nothing. It is the most natural place on the line to
  //: right-click, being the thing that is drawn to be grabbed.
  await page.waitForTimeout(300);
  const grip = await page.evaluate(() => {
    const el = document.querySelector("circle.wb-link-bend-handle");
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  if (grip) await page.mouse.click(grip.x, grip.y, { button: "right" });
  await page.waitForTimeout(600);
  const gripRing = await page.evaluate(() => {
    const ring = document.getElementById("wb-map-link-radial");
    return { visible: !ring.classList.contains("hidden"), label: ring.getAttribute("aria-label") || "" };
  });
  check("right-clicking the cross-link's bend grip opens the same ring", Boolean(grip) && gripRing.visible && gripRing.label.includes("cross-link"),
    grip ? `ring ${gripRing.visible}, ${gripRing.label}` : "no bend grip drawn");
  await page.evaluate(() => wbCloseMapLinkRadial());

  // The same ring on the other kind says the other thing.
  const branchRing = await page.evaluate(async (childId) => {
    wbOpenMapLinkRadial(childId, 600, 400);
    await new Promise((r) => setTimeout(r, 300));
    const ring = document.getElementById("wb-map-link-radial");
    return {
      label: ring.getAttribute("aria-label"),
      caption: ring.querySelector(".wb-map-radial-caption").textContent.trim(),
      slots: [...ring.querySelectorAll(".wb-map-radial-slot")].map((s) => s.querySelector(".wb-map-radial-name").textContent.trim()),
    };
  }, made.treeChildId);
  show(branchRing);
  check("and on a branch it says branch, with the branch's own slots",
    branchRing.label.includes("branch") && /branch/i.test(branchRing.caption)
      && branchRing.slots.join(",") === "Reverse,Label,Cut",
    `${branchRing.label}: ${branchRing.slots.join(", ")}`);
  await page.evaluate(() => wbCloseMapLinkRadial());

  // **Revised by the owner 2026-09-23** (MINDMAP_PLAN decisions item 6): a
  // cross-link is now drawn exactly like a branch — `wbMapCrossLinkLook` in
  // frontend/js/whiteboard.js hands it the same ribbon/curve geometry, the same
  // branch colour (its source topic's, falling back to the target's, falling
  // back to the accent), and no dash. What used to distinguish the two kinds
  // by ink alone no longer does; the ring and the context-row checks above
  // are what still tell them apart. Measured (`sw-probe1.js`, kept for the
  // next time this needs re-checking): crossFill and the source branch's own
  // edge fill were both `rgb(78, 121, 167)`, neither dashed, and the cross
  // link's own stroke was `none` because a ribbon fills rather than strokes.
  const inks = await page.evaluate((childId) => {
    const cross = document.querySelector(".sketch-group.wb-map-crosslink .sketch-path");
    const ownBranchEdge = document.querySelector(`.wb-map-edge[data-child="${childId}"]`);
    const anyBranch = document.querySelector(".wb-map-edge");
    const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
    const probe = document.createElement("div");
    probe.style.color = accent;
    document.body.appendChild(probe);
    const accentRgb = getComputedStyle(probe).color;
    probe.remove();
    return {
      crossFill: getComputedStyle(cross).fill,
      crossStroke: getComputedStyle(cross).stroke,
      crossDash: getComputedStyle(cross).strokeDasharray,
      // The source topic's own branch (Leaf 1a's edge, i.e. the child made
      // above): its colour is what the cross-link is meant to carry.
      ownBranchFill: ownBranchEdge ? getComputedStyle(ownBranchEdge).fill : null,
      anyBranchDash: anyBranch ? getComputedStyle(anyBranch).strokeDasharray : null,
      accentRgb,
    };
  }, made.aId);
  show(inks);
  check("a cross-link is drawn like a branch: filled in its own branch's ink, not dashed",
    inks.crossStroke === "none" && inks.crossDash === "none"
      && inks.crossFill === inks.ownBranchFill && inks.anyBranchDash === "none",
    `cross fill ${inks.crossFill} vs branch fill ${inks.ownBranchFill} (accent ${inks.accentRgb}), stroke ${inks.crossStroke}, dash ${inks.crossDash}`);

  // The rail's two Connect tools say which kind they make, on each surface.
  const railWords = await page.evaluate(() => ({
    map: {
      section: document.querySelector('#wb-tool-group .wb-tool-section[aria-label]:has([data-tool="link-straight"])')?.getAttribute("aria-label"),
      straight: document.querySelector('#wb-tool-group [data-tool="link-straight"]')?.getAttribute("aria-label"),
    },
  }));
  show(railWords);
  check("the rail's Connect tools say cross-link on a map",
    /cross-link/i.test(railWords.map.section || "") && /cross-link/i.test(railWords.map.straight || ""),
    `${railWords.map.section}: ${railWords.map.straight}`);

  // 3. Export: does each kind survive?
  const exports = await page.evaluate(async () => {
    const out = {};
    for (const f of ["markdown", "opml", "freemind"]) {
      // `api()`, not a bare `fetch`: the app adds its own auth header, and a
      // raw fetch of this route comes back 401 with a JSON body that is the
      // same length in all three formats, which is exactly how a first run of
      // this probe reported "the export is empty" for a route that works.
      const res = await api(`/whiteboard/boards/${window.currentBoardId}/export?format=${f}`);
      out[f] = await res.text();
    }
    return out;
  });
  const carriesTree = exports.markdown.includes("Leaf 1a") && exports.markdown.includes("Branch 4");
  //: **Inverted by 13d, which is the point of the row.** This used to assert
  //: that a cross-link survives none of the three, which was true and was the
  //: measurement 13.2's table was written from. The two XML formats now carry
  //: it in the place each of them has: FreeMind's own `<arrowlink
  //: DESTINATION>`, and a private `_links` on an OPML outline, which is the
  //: same bargain `_kind` and `_ref` already struck there. Markdown carries
  //: it in neither, deliberately: that file is an outline anybody can paste
  //: anywhere, it already drops everything a node wears, and its own import
  //: reads indentation, so a cross-links section would come back as topics.
  const freemindCarries = /<arrowlink[^>]*DESTINATION="ID_\d+"/.test(exports.freemind);
  const opmlCarries = /_links="ID_\d+/.test(exports.opml);
  const markdownCarries = /arrowlink|_links|ID_\d/.test(exports.markdown);
  show({
    markdownChars: exports.markdown.length,
    opmlChars: exports.opml.length,
    freemindChars: exports.freemind.length,
    leaf1aInMarkdown: exports.markdown.includes("Leaf 1a"),
    freemindCarries,
    opmlCarries,
    markdownCarries,
  });
  check("a tree edge survives the Markdown export", carriesTree, "every parent/child pair is an indent");
  check("a cross-link survives the two formats that have a place for it",
    freemindCarries && opmlCarries,
    `freemind arrowlink ${freemindCarries}, opml _links ${opmlCarries}`);
  check("and the Markdown outline stays an outline", !markdownCarries,
    markdownCarries ? "an id or a link attribute leaked into the outline" : "indentation only");

  // --- Part two: the surface against the app's own scales ---
  const scales = await page.evaluate(() => {
    const cs = getComputedStyle(document.documentElement);
    // `--space-N` is `calc(0.25rem * var(--density))`: getPropertyValue hands
    // back the calc() text, never a length, which is how a previous read of
    // this reported every token as null and every value on the surface as
    // off-scale. The browser is the only thing that can resolve it, so one
    // probe element is given the value as a width and its box is read.
    const probe = document.createElement("div");
    probe.style.position = "absolute";
    probe.style.visibility = "hidden";
    document.body.appendChild(probe);
    const px = (v) => {
      probe.style.width = `var(${v})`;
      const n = probe.getBoundingClientRect().width;
      return Number.isFinite(n) ? Math.round(n * 100) / 100 : null;
    };
    const space = {};
    for (let i = 1; i <= 9; i++) space[`--space-${i}`] = px(`--space-${i}`);
    const out = {
      space,
      radius: cs.getPropertyValue("--radius").trim(),
      radiusMd: cs.getPropertyValue("--radius-md").trim(),
      radiusLg: cs.getPropertyValue("--radius-lg").trim(),
      density: cs.getPropertyValue("--density").trim(),
      remPx: parseFloat(getComputedStyle(document.documentElement).fontSize),
    };
    probe.remove();
    return out;
  });
  show({ spaceScale: scales.space, radius: scales.radius });

  // The strip and the ring only have a box while something is selected and
  // the ring is open: read at the wrong moment both measure 0x0, which is not
  // "no padding", it is "not on screen".
  await page.evaluate(async (childId) => {
    const el = document.querySelector(`#wb-html-layer .wb-map-node[data-id="${childId}"], #wb-html-layer [data-id="${childId}"] .wb-map-node`);
    if (el) el.click();
    await new Promise((r) => setTimeout(r, 700));
    const node = (wbState.objects || []).find((o) => o.id === childId);
    if (typeof wbOpenMapRadial === "function" && node) wbOpenMapRadial(node);
    await new Promise((r) => setTimeout(r, 400));
  }, made.treeChildId);

  const surface = await page.evaluate(() => {
    const read = (sel, extra = []) => {
      const el = document.querySelector(sel);
      if (!el) return { sel, present: false };
      const cs = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      const o = {
        sel, present: true,
        w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10,
        padding: `${cs.paddingTop} ${cs.paddingRight} ${cs.paddingBottom} ${cs.paddingLeft}`,
        gap: cs.gap, radius: cs.borderTopLeftRadius,
        fontSize: cs.fontSize, lineHeight: cs.lineHeight,
      };
      for (const p of extra) o[p] = cs.getPropertyValue(p);
      return o;
    };
    const container = document.getElementById("whiteboard-container").getBoundingClientRect();
    const rail = document.getElementById("wb-tool-group")?.getBoundingClientRect();
    return {
      node: read("#wb-html-layer .wb-map-node"),
      strip: read("#wb-map-strip"),
      ring: read("#wb-map-radial"),
      ringSlot: read("#wb-map-radial .wb-map-radial-slot"),
      rail: read("#wb-tool-group"),
      railSectionLabel: read("#wb-tool-group .wb-tool-section-label"),
      topbar: read("#wb-topbar"),
      // The gutters: how far the rail and the bar sit from the canvas edges.
      gutters: rail ? {
        railBottom: Math.round((container.bottom - rail.bottom) * 10) / 10,
        railLeft: Math.round((rail.left - container.left) * 10) / 10,
      } : null,
    };
  });
  for (const [k, v] of Object.entries(surface)) show({ [k]: v });

  // Which of the read paddings/gaps are on the spacing scale?
  const onScale = (v) => {
    const n = parseFloat(v);
    if (!Number.isFinite(n) || n === 0) return true; // 0 and "normal" are not off-scale
    return Object.values(scales.space).some((s) => s != null && Math.abs(s - n) < 0.6);
  };
  const offScale = [];
  for (const [name, o] of Object.entries(surface)) {
    if (!o || !o.present) continue;
    for (const part of String(o.padding).split(" ")) if (!onScale(part)) offScale.push(`${name}.padding ${part}`);
    if (o.gap && o.gap !== "normal") for (const part of String(o.gap).split(" ")) if (!onScale(part)) offScale.push(`${name}.gap ${part}`);
  }
  show({ offScale });
  check("every padding and gap on the map's own chrome is a spacing token",
    offScale.length === 0, offScale.length ? offScale.join("; ") : "all on --space-1..9");

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  await browser.close();
  process.exit(0);
})();
