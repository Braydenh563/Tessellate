(() => {
  // whiteboard-link-edge.js: a connector whose end sits on another connector, edge to edge (L-whiteboard-43;
  // WHITEBOARD_PLAN section 4, source and target). The end keeps `sourceEdge` or `targetEdge`, `{ id, t }`: the other
  // connector's sketch id and the fraction `t` (0 to 1) along its drawn line, beside the end's own `sourcePoint` or
  // `targetPoint`, which is the last place it was seen. No `sourceId` or `targetId` is written, so the server's
  // sweep of links to deleted items (wb_board.py) never reads it as a stale end and drops the connector.
  //
  // Drawing: `wbResolveLinkEndpoints` asks `pinned` first, which swaps an attached end for the point at `t` along the
  // line as it is drawn now, so the end follows when that connector moves, bends or is re-ended. Every other code
  // path that draws a connector already goes through that one resolver. While a gesture moves a connector, `follow`
  // redraws the ones that hang on it. Deleting the connector floats its dependants free at the last point they had
  // (`beforeDelete`, `afterDelete`), and the undo step for the delete re-attaches them to the restored line
  // (`reattach`). Held on `wbFmtState.linkEdge`, no new global name.
  const ENDS = ["source", "target"];
  //: How near the pointer must be to a line, in screen pixels, for an end to take hold of it.
  const REACH = 12;
  const STEPS = 48;
  const MAX_DEPTH = 4;
  let depth = 0;
  let following = 0;
  //: The last point an attachment resolved to, for when its connector has gone since this page loaded.
  const lastSeen = new Map();

  //: whiteboard.js keeps its own zoomK inside its closure, so the zoom is read here the way the other board files do.
  const zoomK = () => d3.zoomTransform(document.getElementById("whiteboard-container")).k || 1;
  const clamp01 = (n) => Math.max(0, Math.min(1, n));
  const round = (n) => Math.round(n * 10) / 10;

  //: Pure (node-tested): a stored `{ id, t }`, or null for anything that is not one.
  function edgeOf(parsed, end) {
    const edge = parsed?.[`${end}Edge`];
    if (!edge || !Number.isInteger(edge.id) || !Number.isFinite(Number(edge.t))) return null;
    return { id: edge.id, t: clamp01(Number(edge.t)) };
  }

  //: The drawn line of a connector as one path string, or null when it has no line of its own (a map's cross-link).
  function lineD(parsed) {
    if (!parsed || wbMapCrossLinkLook(parsed)) return null;
    const ends = wbResolveLinkEndpoints(parsed);
    if (!ends) return null;
    return wbLinkPathD(parsed.type, ends.source, ends.target, wbLinkCaps(parsed), parsed.width, parsed.bend, wbLinkShape(parsed));
  }

  //: Where fraction `t` along a connector's line is now, or null (no such connector, or too deep a chain of them).
  function pointOn(sketch, t) {
    if (!sketch || depth >= MAX_DEPTH) return null;
    const parsed = wbParsedLink(sketch);
    if (!parsed) return null;
    depth += 1;
    try {
      const d = lineD(parsed);
      return d ? wbLinkMidpoint(d, t) : null;
    } finally {
      depth -= 1;
    }
  }

  //: The connector as the resolver should read it: each attached end carries the point it resolves to as its own
  //: free point. A connector that is gone leaves the end at the last point it had. Returns `parsed` itself when
  //: nothing is attached, so an ordinary connector costs one property read.
  function pinned(parsed) {
    let out = parsed;
    for (const end of ENDS) {
      const edge = edgeOf(parsed, end);
      if (!edge || parsed[`${end}Id`] != null) continue;
      const key = `${edge.id}:${edge.t}`;
      const found = pointOn(wbLinkItem("sketch", edge.id), edge.t);
      if (found) lastSeen.set(key, { x: found.x, y: found.y });
      const at = found || lastSeen.get(key);
      if (!at) continue;
      if (out === parsed) out = { ...parsed };
      out[`${end}Point`] = { x: at.x, y: at.y };
    }
    return out;
  }

  const hangsOn = (parsed, id, level = 0) => ENDS.some((end) => {
    const edge = edgeOf(parsed, end);
    if (!edge) return false;
    if (edge.id === id) return true;
    const other = level < MAX_DEPTH ? wbLinkItem("sketch", edge.id) : null;
    return Boolean(other) && hangsOn(wbParsedLink(other), id, level + 1);
  });

  //: The connector nearest `(x, y)` within reach, as `{ id, t, x, y }`, or null. `skipId` is the connector being
  //: drawn or re-ended: it and anything that hangs on it are never a target, so two connectors cannot hold each other.
  function hitAt(x, y, skipId = null) {
    const reach = REACH / zoomK();
    let best = null;
    for (const sketch of wbState.sketches || []) {
      if (sketch.id === skipId) continue;
      const parsed = wbParsedLink(sketch);
      if (!parsed || (skipId != null && hangsOn(parsed, skipId))) continue;
      const d = lineD(parsed);
      if (!d) continue;
      const near = (t) => {
        const p = wbLinkMidpoint(d, t);
        return p ? { t, x: p.x, y: p.y, dist: Math.hypot(p.x - x, p.y - y) } : null;
      };
      let top = null;
      for (let i = 0; i <= STEPS; i += 1) {
        const hit = near(i / STEPS);
        if (hit && (!top || hit.dist < top.dist)) top = hit;
      }
      if (!top || top.dist > reach * 2) continue;
      //: A finer look either side of the best sample.
      for (let i = -8; i <= 8; i += 1) {
        const hit = near(clamp01(top.t + i / (STEPS * 8)));
        if (hit && hit.dist < top.dist) top = hit;
      }
      if (top.dist <= reach && (!best || top.dist < best.dist)) best = { id: sketch.id, t: Math.round(top.t * 1000) / 1000, x: round(top.x), y: round(top.y), dist: top.dist };
    }
    return best ? { id: best.id, t: best.t, x: best.x, y: best.y } : null;
  }

  //: Every connector with an end on connector `id`: `{ sketch, parsed }`. A string test first, so a board with no
  //: edge-to-edge connector (nearly all of them) is not parsed on every frame of a drag.
  function dependents(id) {
    const out = [];
    for (const sketch of wbState.sketches || []) {
      const raw = sketch.data;
      if (typeof raw !== "string" || !(raw.includes('"sourceEdge"') || raw.includes('"targetEdge"'))) continue;
      const parsed = wbParsedLink(sketch);
      if (parsed && ENDS.some((end) => edgeOf(parsed, end)?.id === id)) out.push({ sketch, parsed });
    }
    return out;
  }

  //: Called as a gesture redraws connector `id`: redraws the ones attached to it (`update` is wbUpdateLinkedSketches).
  function follow(id, update) {
    if (following >= MAX_DEPTH) return;
    const deps = dependents(id);
    if (!deps.length) return;
    following += 1;
    try {
      update(null, deps);
    } finally {
      following -= 1;
    }
  }

  //: Before connector `sketch` is deleted: which ends hang on it and where each is now, read while it still exists.
  function beforeDelete(sketch) {
    const out = [];
    for (const { sketch: dep, parsed } of dependents(sketch.id)) {
      for (const end of ENDS) {
        const edge = edgeOf(parsed, end);
        if (edge?.id !== sketch.id) continue;
        const at = pointOn(sketch, edge.t) || lastSeen.get(`${edge.id}:${edge.t}`) || parsed[`${end}Point`];
        if (at) out.push({ sketchId: dep.id, end, t: edge.t, x: round(at.x), y: round(at.y) });
      }
    }
    return out;
  }

  //: After the delete went through: each of those ends keeps its last point and lets go of the line.
  async function afterDelete(list) {
    for (const item of list || []) {
      const dep = wbLinkItem("sketch", item.sketchId);
      if (dep) await wbSaveSketchProps(dep, { [`${item.end}Point`]: { x: item.x, y: item.y }, [`${item.end}Edge`]: undefined });
    }
  }

  //: Undo of the delete: the restored connector has a new id, and the ends that hung on the old one hang on it again.
  async function reattach(list, newId) {
    for (const item of list || []) {
      const dep = wbLinkItem("sketch", item.sketchId);
      if (dep) await wbSaveSketchProps(dep, { [`${item.end}Edge`]: { id: newId, t: item.t } });
    }
  }

  wbFmtState.linkEdge = { edgeOf, pinned, pointOn, hitAt, hangsOn, dependents, follow, beforeDelete, afterDelete, reattach, ENDS };
})();
