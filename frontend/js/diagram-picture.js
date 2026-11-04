// diagram-picture.js: a press on the drawn picture finds the block under it (1546 P2). Loaded by
// diagram-builder.js's `show` with the drag code, before the first pane is mounted; it was part of the builder
// and left it to keep that file under its size cap. `boxes` reads the node boxes off a drawn SVG, `pick` turns a
// press on the picture into a node id (the builder selects the block).
(() => {
  //: The nodes' boxes, read off the SVG text with patterns: `{id, x, y, w, h}` in the picture's own units, from
  //: Mermaid's `[<svg id>-]flowchart-<id>-<n>` groups (version 12 prefixes the picture's own id). Not through DOMParser: a parsed document keeps the page's policy, and
  //: Mermaid's `style=` attributes were refused one by one (measured: 19 console errors on a 3-node diagram).
  //: Null when the picture has none.
  function boxes(svg) {
    const vb = /<svg\b[^>]*\bviewBox="([^"]+)"/.exec(svg)?.[1].trim().split(/[ ,]+/).map(Number);
    if (!vb || vb.length !== 4 || vb.some(Number.isNaN)) return null;
    const num = (tag, name) => Number(new RegExp("\\b" + name + '="(-?[\\d.]+)"').exec(tag)?.[1]) || 0;
    const found = [];
    for (const g of svg.matchAll(/<g\b[^>]*\bid="(?:[^"]*?-)?flowchart-([^"]+?)-\d+"[^>]*>/g)) {
      const at = /transform="translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)/.exec(g[0]);
      if (!at) continue;
      //: This node's own text: up to the next node's group, so a shape-less node never borrows its neighbour's rect.
      const rest = svg.slice(g.index + g[0].length);
      const own = rest.slice(0, rest.search(/\bid="[^"]*flowchart-/) >= 0 ? rest.search(/\bid="[^"]*flowchart-/) : 8000);
      const tail = own.slice(0, 900);
      const rect = /<rect\b[^>]*>/.exec(tail)?.[0] || "";
      const poly = /<polygon\b[^>]*\bpoints="([^"]+)"/.exec(tail)?.[1].trim().split(/[ ,]+/).map(Number) || [];
      const xs = poly.filter((_, i) => i % 2 === 0);
      const ys = poly.filter((_, i) => i % 2 === 1);
      const r = num(/<circle\b[^>]*>/.exec(tail)?.[0] || "", "r") * 2;
      //: A pill or other rough shape is one path: its extent is the span of the path's own points, read only when no plain shape was found.
      let span = null;
      if (!rect && !xs.length && !r) {
        const d = /<path\b[^>]*\bd="([^"]+)"/.exec(own)?.[1].match(/-?\d*\.?\d+/g)?.map(Number) || [];
        const px = d.filter((_, i) => i % 2 === 0);
        const py = d.filter((_, i) => i % 2 === 1);
        if (px.length > 1) span = [Math.max(...px) - Math.min(...px), Math.max(...py) - Math.min(...py)];
      }
      found.push({
        id: g[1], x: Number(at[1]), y: Number(at[2]),
        w: num(rect, "width") || (xs.length ? Math.max(...xs) - Math.min(...xs) : 0) || r || span?.[0] || 80,
        h: num(rect, "height") || (ys.length ? Math.max(...ys) - Math.min(...ys) : 0) || r || span?.[1] || 40,
      });
    }
    return found.length ? { vb, boxes: found, ...extras(svg) } : null;
  }

  //: The groups' boxes and the arrows' midpoints (R8c), in the same units and the same `{id, x, y, w, h}` shape (x, y the centre;
  //: an arrow has no size). A group is Mermaid's `cluster` group, its id the picture's own id then the subgraph's; an arrow is
  //: its path with the id Mermaid gives it, `L_<from>_<to>_<n>`, placed at the middle point of the path.
  function extras(svg) {
    const lead = /<svg\b[^>]*\bid="([^"]+)"/.exec(svg)?.[1];
    const clusters = [];
    for (const g of svg.matchAll(/<g\b[^>]*\bclass="cluster"[^>]*>\s*<rect\b[^>]*>/g)) {
      const id = /\bid="([^"]+)"/.exec(g[0])?.[1];
      const rect = g[0].slice(g[0].indexOf("<rect"));
      const [x, y, w, h] = ["x", "y", "width", "height"].map((name) => Number(new RegExp("\\s" + name + '="(-?[\\d.]+)"').exec(rect)?.[1]));
      if (id && [x, y, w, h].every(Number.isFinite)) clusters.push({ id: lead && id.startsWith(lead + "-") ? id.slice(lead.length + 1) : id, x: x + w / 2, y: y + h / 2, w, h });
    }
    const edges = [];
    for (const p of svg.matchAll(/<path\b[^>]*\bdata-id="(L_[^"]+)"[^>]*>/g)) {
      const d = /\sd="([^"]+)"/.exec(p[0])?.[1].match(/-?\d*\.?\d+/g)?.map(Number) || [];
      const pts = [];
      for (let i = 0; i + 1 < d.length; i += 2) pts.push([d[i], d[i + 1]]);
      //: Half way along the points' own polyline (a corner's control point counts as a point).
      const len = pts.slice(1).map((q, i) => Math.hypot(q[0] - pts[i][0], q[1] - pts[i][1]));
      let rest = len.reduce((a, b) => a + b, 0) / 2;
      let i = 0;
      while (i < len.length - 1 && rest > len[i]) rest -= len[i++];
      if (pts.length > 1) edges.push({ id: p[1], x: pts[i][0] + ((pts[i + 1][0] - pts[i][0]) * rest) / (len[i] || 1), y: pts[i][1] + ((pts[i + 1][1] - pts[i][1]) * rest) / (len[i] || 1), w: 0, h: 0 });
    }
    return { clusters, edges };
  }

  //: The id of the node drawn under a press on the picture, or "". Not a drag: the picture is not a handle.
  function pick(S, event) {
    const img = event.target.closest?.("img");
    if (!img || !S.hit || !S.m) return "";
    const r = img.getBoundingClientRect();
    const [vx, vy, vw, vh] = S.hit.vb;
    const x = vx + ((event.clientX - r.left) / r.width) * vw;
    const y = vy + ((event.clientY - r.top) / r.height) * vh;
    return S.hit.boxes.find((b) => Math.abs(x - b.x) <= b.w / 2 && Math.abs(y - b.y) <= b.h / 2)?.id || "";
  }

  diagramModel.picture = { boxes, pick };
})();
