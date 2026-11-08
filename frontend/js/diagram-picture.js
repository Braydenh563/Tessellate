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
      const whole = rest.slice(0, rest.search(/\bid="[^"]*flowchart-/) >= 0 ? rest.search(/\bid="[^"]*flowchart-/) : 8000);
      //: The shape is drawn before the label, and the label carries a small <rect> of its own (its background): read the
      //: shape from the text before the label group, so the handles sit on the outline, not the words (owner, 2026-11-05).
      const cut = whole.search(/\bclass="(?:[^"]*\s)?label(?:\s[^"]*)?"/);
      const own = cut > 0 && /<(?:rect|polygon|circle|path)\b/.test(whole.slice(0, cut)) ? whole.slice(0, cut) : whole;
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
  //: an arrow has no size, but keeps its path: `pts` the polyline, `d` the drawn path, for diagram-edge-pick.js). A group is Mermaid's `cluster` group, its id the picture's own id then the subgraph's; an arrow is
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
      const raw = /\sd="([^"]+)"/.exec(p[0])?.[1] || "";
      const d = raw.match(/-?\d*\.?\d+/g)?.map(Number) || [];
      const pts = [];
      for (let i = 0; i + 1 < d.length; i += 2) pts.push([d[i], d[i + 1]]);
      //: Half way along the points' own polyline (a corner's control point counts as a point).
      const len = pts.slice(1).map((q, i) => Math.hypot(q[0] - pts[i][0], q[1] - pts[i][1]));
      let rest = len.reduce((a, b) => a + b, 0) / 2;
      let i = 0;
      while (i < len.length - 1 && rest > len[i]) rest -= len[i++];
      if (pts.length > 1) edges.push({ id: p[1], x: pts[i][0] + ((pts[i + 1][0] - pts[i][0]) * rest) / (len[i] || 1), y: pts[i][1] + ((pts[i + 1][1] - pts[i][1]) * rest) / (len[i] || 1), w: 0, h: 0, pts, d: raw });
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

  //: A source that will not draw (DD-4, 1107): the last good picture stays, dimmed, with the reason under it, instead of an empty
  //: pane. The reason is an alert the first time a given error shows and a status when the same one is drawn again; the line it
  //: names is `data-line` and a button puts the caret there, another undoes the last edit; the "tall for this pane" offer is for a picture that is not there.
  function failure(S, result, source, smallButton) {
    S.fig.classList.toggle("dgm-picture-stale", !result.svg);
    const field = S.root.closest(".dgm-dialog")?.querySelector(".dgm-source");
    //: The text field's gutter marks the line (DD-5): set with the note, cleared when the picture draws.
    const mark = (line) => {
      if (!field || field.dataset.errorLine === (line || undefined)) return;
      if (line) field.dataset.errorLine = line;
      else delete field.dataset.errorLine;
      field.dispatchEvent(new Event("dgmerror"));
    };
    if (result.svg) return void ((S.errorSeen = ""), delete S.fig.dataset.errorLine, mark(""));
    S.fig.classList.remove("md-mermaid-pending");
    S.fig.removeAttribute("aria-busy");
    const error = result.error;
    const note = mermaidFailure.note(error, source);
    const plain = mermaidFailure.plain(error, source);
    const fresh = S.errorSeen !== plain;
    S.errorSeen = plain;
    note.setAttribute("role", fresh ? "alert" : "status");
    S.sideways?.classList.add("hidden");
    const line = /^Line (\d+):/.exec(plain)?.[1];
    mark(line);
    if (line) {
      note.dataset.line = line;
      S.fig.dataset.errorLine = line;
    } else delete S.fig.dataset.errorLine;
    if (line && field) {
      const go = smallButton(`Go to line ${line}`, "Put the cursor on the line the message names", () => {
        const lines = field.value.split("\n");
        const from = lines.slice(0, Number(line) - 1).join("\n").length + (line > 1 ? 1 : 0);
        field.focus();
        field.setSelectionRange(from, from + (lines[Number(line) - 1] || "").length);
      });
      note.prepend(go);
    }
    //: A bad edit is one press from undone, whichever pane made it (DD-4).
    //: Not offered where there is no earlier step (a bad file opened as it is). The note leaves when the old picture draws, with the focus
    //: in it, so focus goes to the picture first (measured: the body, and the first Tab was "Skip to content").
    if (S.io?.undo && S.io.canUndo !== false) {
      note.prepend(smallButton("ph:arrow-u-up-left Undo the last edit", "Go back to the diagram before this change", () => {
        (S.fig?.isConnected ? S.fig : field)?.focus?.({ preventScroll: true });
        S.io.undo();
      }));
    }
    if (!S.fig.querySelector(":scope > .md-mermaid-img")) return S.fig.replaceChildren(note);
    S.fig.querySelector(":scope > .md-mermaid-reason")?.remove();
    S.fig.append(note);
  }

  //: A relabel shows in the drawn picture before the redraw (1108 P3): the node's one row of words (a tspan per word)
  //: becomes one tspan of the new words and the picture is shown again: a blob swap, not a Mermaid render. Skipped unless
  //: the node has one row reading as the old words; the redraw that follows replaces it either way.
  function patch(S, key, was, text) {
    const id = diagramModel.ops.split(key)[1];
    const svg = S.fig.querySelector(":scope > img.md-mermaid-img")?.mermaidSvg;
    const at = svg && new RegExp('<g\\b[^>]*\\bid="(?:[^"]*?-)?flowchart-' + id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + '-\\d+"').exec(svg);
    if (!at) return;
    const rest = svg.slice(at.index + at[0].length);
    const next = rest.search(/\bid="[^"]*flowchart-/);
    const end = at.index + at[0].length + (next < 0 ? rest.length : next);
    const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const part = svg.slice(at.index, end);
    const rows = [...part.matchAll(/(<tspan\b[^>]*text-outer-tspan[^>]*>)((?:<tspan\b[^>]*>[^<]*<\/tspan>)+)<\/tspan>/g)];
    if (rows.length !== 1 || [...rows[0][2].matchAll(/>([^<]*)<\/tspan>/g)].map((m) => m[1]).join("") !== esc(was)) return;
    const words = '<tspan font-style="normal" class="text-inner-tspan" font-weight="normal">' + esc(text) + "</tspan>";
    const from = at.index + rows[0].index;
    mermaidShow(S.fig, { svg: svg.slice(0, from) + rows[0][1] + words + "</tspan>" + svg.slice(from + rows[0][0].length), key: S.fig.mermaidKey }, S.source);
    for (const paint of S.fig.onpaint || []) paint();
  }

  //: Resolves in an idle slice (at most 400 ms), and not while a label is being typed (1108 P3): a draw starts between
  //: keys, never on one, and Enter or blur brings it. A newer change drops the older draw by its stamp.
  const idle = (S) => new Promise((done) => {
    const go = () => (S.tree.querySelector(".dgm-editing") ? setTimeout(go, 150) : (window.requestIdleCallback || setTimeout)(done, { timeout: 400 }));
    go();
  });

  diagramModel.picture = { boxes, pick, failure, patch, idle };
})();
