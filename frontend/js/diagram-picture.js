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
      const tail = svg.slice(g.index + g[0].length, g.index + g[0].length + 900);
      const rect = /<rect\b[^>]*>/.exec(tail)?.[0] || "";
      const poly = /<polygon\b[^>]*\bpoints="([^"]+)"/.exec(tail)?.[1].trim().split(/[ ,]+/).map(Number) || [];
      const xs = poly.filter((_, i) => i % 2 === 0);
      const ys = poly.filter((_, i) => i % 2 === 1);
      const r = num(/<circle\b[^>]*>/.exec(tail)?.[0] || "", "r") * 2;
      found.push({
        id: g[1], x: Number(at[1]), y: Number(at[2]),
        w: num(rect, "width") || (xs.length ? Math.max(...xs) - Math.min(...xs) : 0) || r || 80,
        h: num(rect, "height") || (ys.length ? Math.max(...ys) - Math.min(...ys) : 0) || r || 40,
      });
    }
    return found.length ? { vb, boxes: found } : null;
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
