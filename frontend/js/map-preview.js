// map-preview.js: the drawing of a board's miniature (`mapPreviewDraw`, with its
// sizes, label fitting and edges), moved out of note-cards.js on 2026-11-01 for
// the gzip budget (tests/test_static_compression.py, row 21). `mapPreview`
// (note-cards.js) returns the empty svg at once and awaits
// `ensureModule("mapPreview")` before this draws into it, so every caller
// keeps its sync `classList.add` on the result.

//: The sizes a preview is ever drawn at. A named size rather than a pair of
//: numbers per call site: "the Library card's minimap" and "the dashboard
//: row's thumbnail" are the two real cases, and letting each caller pass its
//: own geometry is how the two drifted apart in the first place.
//:
//: `labels` is off at row size deliberately. Sixteen characters beside a 9×6
//: block is a legible texture in a 100×56 card; the same text in a 40×40
//: thumbnail is a smear.
//:
//: `w`/`h` are the *box the picture is letterboxed into*, not the viewBox:
//: since the drawing is now made at the board's own ratio, the two are the
//: same only for a board that happens to be shaped like the card. Everything
//: else here (`pad`, `blockW`, `blockH`, `font`) is a size in that box, and
//: `mapPreview` divides each of them by the scale the browser is about to
//: apply, so a node in a tall map is drawn the same number of pixels across
//: as a node in a wide one. Without that division the block sizes are in
//: viewBox units and a square board's nodes come out 44% smaller than a wide
//: board's, for no reason a reader could see.
(() => {
  const MAP_PREVIEW_SIZES = {
    card: { w: 100, h: 56, pad: 3, blockW: 9, blockH: 6, labels: true, font: 4.2 },
    row: { w: 40, h: 40, pad: 3, blockW: 4, blockH: 3, labels: false, font: 0 },
  };

  //: The long side of the board's own box, in viewBox units. Arbitrary: only
  //: the *ratio* of the viewBox is meaningful, since `preserveAspectRatio`
  //: scales it into the card either way. 100 keeps the numbers in the DOM
  //: readable when someone inspects a thumbnail.
  const MAP_PREVIEW_BASE = 100;

  //: How round a node is, as a fraction of its short side. A node on the canvas
  //: is a rounded card, not a dot and not a pill, and the miniature says the
  //: same thing at a twentieth of the size.
  //:
  //: **Was 0.35, and 0.35 is a blob** (INBOX 164: "board previews need upgrading
  //: and fixing", with a screenshot of a wash of rounded blobs). Measured on a
  //: seeded board at 1440 (`scratchpad/ui-sweeps/boardpreview.js`): every block
  //: came out 52.9x24.7 with a rendered corner radius of 8.66px, which is 35% of
  //: its own short side. A rectangle whose corners eat a third of its height is
  //: not a rounded rectangle, and nothing on the canvas looks like that: a note
  //: card is `--radius`, 10px on a 150px side, which is 7%.
  const MAP_PREVIEW_NODE_ROUNDING = 0.22;

  //: And the ceiling that does the real work, in the nominal units
  //: `MAP_PREVIEW_SIZES` is written in. A fraction of the short side alone cannot
  //: be right at both sizes this preview draws at: the same 22% is a gentle
  //: corner on a 25px-tall block in a Library card and a pill on a 4px one in a
  //: dashboard row. It is divided back out by the box's own scale below, so the
  //: corner is the same size whatever shape the board is, and the fraction is
  //: left as the floor for a block too small to carry it.
  //:
  //: The nominal box is not pixels: a `card` is 100x56 here and measured 293.5px
  //: wide in the Library, so one unit is about 2.9 rendered pixels, and 0.8 of one
  //: is the 2px corner a note card has on the canvas.
  const MAP_PREVIEW_CORNER_UNITS = 0.8;

  //: The floor on a block's drawn size, as a multiple of the size every block
  //: used to be. A small object on a large board is a fraction of a viewBox
  //: unit once it is drawn to scale, and a preview whose smallest things are
  //: invisible is a preview of the big ones only.
  const MAP_PREVIEW_MIN_BLOCK = 0.5;

  //: A character's width as a fraction of the type size. Still here as the
  //: fallback for a browser that cannot measure (see `mapPreviewTextWidth`),
  //: and as the unit the padding around a label is expressed in.
  //:
  //: **It is no longer what decides whether a label fits**, and the reason is a
  //: measurement. An estimate that is 0.55 when the font draws wider puts the
  //: text past the room it was budgeted, and the budget is what every later
  //: decision is made from: measured on a seeded board, "body text" was
  //: budgeted into a margin and painted 20.0 units wide starting at x=100.1 in
  //: a 100-unit-wide viewBox, so the label began past the edge of the paper.
  //: Reported as "the boards and maps previews are kinda a mess".
  const MAP_PREVIEW_CHAR_WIDTH = 0.55;

  //: **What a label paints at font-size 1, cached by string, measured on a
  //: canvas** (INBOX 496, the slow Boards and maps load). The font is read once
  //: from a hidden SVG carrying `.board-minimap`, so the drawn family and weight
  //: apply: measuring in another font is wrong with confidence. It used to be
  //: `getComputedTextLength` on that SVG, and `mapPreviewFitText` asks for every
  //: shorter cut of a long label, so each new string forced a layout of a page
  //: the gallery was still building: profiled at 172 to 213ms in this function
  //: plus most of 475ms of layout on a first visit to 34 boards. A canvas's
  //: `measureText` lays nothing out.
  const MAP_PREVIEW_TEXT_WIDTHS = new Map();
  const MAP_PREVIEW_MEASURE_SIZE = 100;
  let mapPreviewMeasureCtx = null;

  function mapPreviewMeasurer() {
    if (mapPreviewMeasureCtx !== null) return mapPreviewMeasureCtx;
    mapPreviewMeasureCtx = false;
    try {
      const NS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(NS, "svg");
      //: Classes, not `style=` (the CSP): 10-responsive.css places it off screen.
      svg.setAttribute("class", "board-minimap map-preview-measure");
      svg.setAttribute("aria-hidden", "true");
      const node = document.createElementNS(NS, "text");
      svg.appendChild(node);
      document.body.appendChild(svg);
      const font = getComputedStyle(node);
      const ctx = document.createElement("canvas").getContext("2d");
      if (ctx) {
        ctx.font = `${font.fontStyle} ${font.fontWeight} ${MAP_PREVIEW_MEASURE_SIZE}px ${font.fontFamily}`;
        mapPreviewMeasureCtx = ctx;
      }
    } catch {
      //: No canvas or no document: the fixed estimate is what this always used.
    }
    return mapPreviewMeasureCtx;
  }

  function mapPreviewTextWidth(text, fontSize) {
    const body = String(text || "");
    if (!body) return 0;
    let perUnit = MAP_PREVIEW_TEXT_WIDTHS.get(body);
    if (perUnit === undefined) {
      const ctx = mapPreviewMeasurer();
      const measured = ctx ? ctx.measureText(body).width : 0;
      perUnit = measured > 0 ? measured / MAP_PREVIEW_MEASURE_SIZE : null;
      MAP_PREVIEW_TEXT_WIDTHS.set(body, perUnit);
    }
    return perUnit === null
      ? body.length * MAP_PREVIEW_CHAR_WIDTH * fontSize
      : perUnit * fontSize;
  }

  //: Cut a label to the widest it may paint, measuring rather than counting
  //: characters: "Illinois" and "WWWWWWWW" are eight characters and very
  //: different widths, and the second is what runs off the paper. Returns null
  //: when even one character and the ellipsis will not fit, which is the "draw
  //: nothing" case the caller already had.
  function mapPreviewFitText(text, fontSize, room) {
    const body = String(text || "");
    if (!body) return null;
    if (mapPreviewTextWidth(body, fontSize) <= room) return body;
    for (let cut = body.length - 1; cut >= 1; cut--) {
      const shown = `${body.slice(0, cut).trimEnd()}\u2026`;
      if (mapPreviewTextWidth(shown, fontSize) <= room) return shown;
    }
    return null;
  }

  //: Do two boxes share more than a hair? A shared edge is not a collision, and
  //: floating point makes an exactly shared edge rare, so the threshold is a
  //: fraction of a unit rather than zero.
  //: Is a painted box wholly on the thumbnail's paper? The slack is one
  //: hundredth of a unit, which is below what `round2` can express, so a box
  //: that lands exactly on the border is inside rather than half a rounding
  //: error outside it.
  function mapPreviewOnPaper(box, vw, vh) {
    return (
      box.x >= -0.01 && box.y >= -0.01
      && box.x + box.w <= vw + 0.01 && box.y + box.h <= vh + 0.01
    );
  }

  function mapPreviewOverlaps(a, b, slack = 0.35) {
    return (
      Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > slack
      && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > slack
    );
  }

  //: **Which ink a label takes when it sits on a coloured node.** Measured
  //: with `scratchpad/ui-sweeps/preview.js` the day inside labels landed: a
  //: map's branch nodes are drawn at full strength in their branch colour, and
  //: the app's own ink on a mid-tone blue is 3.82:1, under the 4.5 the rest of
  //: the app is held to. White on that same blue is 4.9:1. The rule is the
  //: usual one: pick whichever of the two the colour is further from, and
  //: return the name of the class that paints it (see 10-responsive.css).
  //:
  //: Only for a label *inside* a coloured block. A label beside one sits on the
  //: paper and keeps `--ink` from the stylesheet, which is where the theme
  //: belongs.
  function mapPreviewOnColour(colour) {
    const hex = String(colour || "").trim();
    const m = /^#?([0-9a-f]{6})$/i.exec(hex);
    if (!m) return null;
    const value = parseInt(m[1], 16);
    const channel = (c) => {
      const v = c / 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    const luminance =
      0.2126 * channel((value >> 16) & 255) +
      0.7152 * channel((value >> 8) & 255) +
      0.0722 * channel(value & 255);
    // 0.18 is where white and black are equally far in WCAG terms.
    return luminance > 0.18 ? "dark" : "light";
  }

  //: The shortest label worth putting inside a shape. Below this the block is
  //: too small to hold a word and the label goes beside it, where it has the
  //: whole margin to run into: "M…" on a node says less than nothing.
  const MAP_PREVIEW_MIN_INSIDE_CHARS = 5;

  //: The shortest label worth drawing beside a shape. Under this the margin the
  //: label would hang into holds "C…" and nothing more, which is texture with
  //: a tooltip's worth of meaning and reads as a stray mark.
  const MAP_PREVIEW_MIN_OUTSIDE_CHARS = 4;

  //: How much of the card's width the letterboxed board has to fill before its
  //: labels are worth drawing, as a fraction. See where it is used.
  const MAP_PREVIEW_LABEL_FLOOR = 0.6;

  //: Two decimals, as a number. Every coordinate in a thumbnail is now a
  //: division by a scale factor, so without this the DOM fills with
  //: `x="17.142857142857142"`: bytes, and unreadable when someone inspects a
  //: card to work out what it drew.
  function round2(value) {
    return Math.round(value * 100) / 100;
  }

  //: **One parent→child edge, as a curve.** Straight lines were what the first
  //: version drew, and a tree of straight segments at thumbnail size reads as a
  //: bar chart: the canvas draws cubic curves (`wbMapEdgePathD`), so the
  //: miniature draws them too, and the two pictures of one map agree.
  //:
  //: The control points follow the dominant axis rather than the board's
  //: `layout`: a `tree-right` map curves out sideways and a `tree-down` map
  //: curves downward, and asking each segment which way it actually runs gets
  //: both right, including the nodes someone dragged off the layout by hand.
  //: The caller says how the curve is coloured, because the two ways of doing it
  //: cannot both come from a class: an edge in its branch colour carries a
  //: `stroke` *attribute*, and a presentation attribute loses to any class that
  //: declares `stroke`. So `.board-minimap-edge` is geometry only, and an
  //: uncoloured edge takes `.board-minimap-edge-accent` on top of it. The
  //: alternative, `el.style.stroke`, writes a `style` attribute, which this
  //: app's CSP drops and `mindmap3.js` asserts the absence of.
  function mapPreviewEdge(NS, px, py, blockW, blockH, edge) {
    const curve = document.createElementNS(NS, "path");
    curve.setAttribute("class", "board-minimap-edge");
    // Half a block: a line should meet the centre of what it joins, and a block
    // is drawn from its top-left corner.
    const x1 = px(edge.x1) + blockW / 2;
    const y1 = py(edge.y1) + blockH / 2;
    const x2 = px(edge.x2) + blockW / 2;
    const y2 = py(edge.y2) + blockH / 2;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const d = Math.abs(dx) >= Math.abs(dy)
      ? `M${round2(x1)} ${round2(y1)} C${round2(x1 + dx / 2)} ${round2(y1)} ${round2(x2 - dx / 2)} ${round2(y2)} ${round2(x2)} ${round2(y2)}`
      : `M${round2(x1)} ${round2(y1)} C${round2(x1)} ${round2(y1 + dy / 2)} ${round2(x2)} ${round2(y2 - dy / 2)} ${round2(x2)} ${round2(y2)}`;
    curve.setAttribute("d", d);
    return curve;
  }

  //: **A drawn stroke, drawn as the shape it actually is.** INBOX 164's "one
  //: squiggle": every sketch on a board used to come out as the same small wave
  //: at the same place, because the server sent every sketch at the board's
  //: origin at one default size (fixed in `_sketch_preview`) and this drew one
  //: generic mark whatever had been drawn. A board of eight shapes previewed as a
  //: single scribble in the corner.
  //:
  //: The stroke data itself is still not shipped, and deliberately: a path per
  //: sketch on a twenty-board list is the payload of a board load, for a picture
  //: 290px wide. What is shipped is the tool it was drawn with, which is enough
  //: for the thumbnail to say the true thing about each one: a rectangle is a
  //: rectangle, a circle is a circle, a line runs corner to corner, and a pen
  //: stroke is a scribble that fills its own box. Everything is at the stroke's
  //: real position and size, so eight shapes are eight marks where they were
  //: drawn.
  //:
  //: `stroke-width` and `stroke` arrive as attributes and the stylesheet must not
  //: declare either, which is the trap `mapPreviewEdge` carries the same note
  //: about: a CSS declaration beats a presentation attribute however specific the
  //: attribute looks. `.board-minimap-sketch` is geometry only; an uncoloured
  //: stroke takes `.board-minimap-sketch-accent` on top of it.
  function mapPreviewSketch(NS, x, y, w, h, shape, unit) {
    const r2 = round2;
    const make = (tag) => {
      const el = document.createElementNS(NS, tag);
      el.setAttribute("class", "board-minimap-sketch");
      //: One weight at every size, for the reason the corner cap is in nominal
      //: units: a constant in viewBox units rendered 3.5px in a Library card and
      //: 0.48px in a dashboard row, where it disappeared.
      el.setAttribute("stroke-width", String(r2(1.6 * unit)));
      return el;
    };
    if (shape === "rect") {
      const el = make("rect");
      el.setAttribute("x", String(r2(x)));
      el.setAttribute("y", String(r2(y)));
      el.setAttribute("width", String(r2(w)));
      el.setAttribute("height", String(r2(h)));
      return el;
    }
    if (shape === "circle") {
      const el = make("ellipse");
      el.setAttribute("cx", String(r2(x + w / 2)));
      el.setAttribute("cy", String(r2(y + h / 2)));
      el.setAttribute("rx", String(r2(w / 2)));
      el.setAttribute("ry", String(r2(h / 2)));
      return el;
    }
    if (shape === "triangle" || shape === "diamond") {
      const el = make("polygon");
      const points = shape === "triangle"
        ? [[x + w / 2, y], [x + w, y + h], [x, y + h]]
        : [[x + w / 2, y], [x + w, y + h / 2], [x + w / 2, y + h], [x, y + h / 2]];
      el.setAttribute("points", points.map(([px, py]) => `${r2(px)},${r2(py)}`).join(" "));
      return el;
    }
    if (shape === "line" || shape === "arrow" || shape === "line-flat" || shape === "line-rise") {
      //: Corner to corner, because that is the only thing the box knows: a
      //: line's box is its two ends, and which diagonal it runs along is not
      //: recoverable from a bounding box. The alternative, a horizontal rule
      //: through the middle, says "a line was drawn" while being a different
      //: line from the one on the board; this one is right for half of them and
      //: the right length for all of them.
      const el = make("line");
      //: A link says which way it runs (`_link_preview`): level or climbing.
      const f = shape == "line-flat" ? h / 2 : shape == "line-rise" ? h : 0;
      el.setAttribute("x1", String(r2(x)));
      el.setAttribute("y1", String(r2(y + f)));
      el.setAttribute("x2", String(r2(x + w)));
      el.setAttribute("y2", String(r2(y + h - f)));
      return el;
    }
    //: A pen or highlighter stroke: a scribble that fills the box it was drawn
    //: in, rather than a fixed wave in the corner of the board. Three humps,
    //: because two read as a tick and four as a wave pattern.
    const el = make("path");
    el.setAttribute("d", [
      `M${r2(x)} ${r2(y + h)}`,
      `C${r2(x + w * 0.18)} ${r2(y)} ${r2(x + w * 0.38)} ${r2(y + h)} ${r2(x + w * 0.52)} ${r2(y + h * 0.5)}`,
      `S${r2(x + w * 0.82)} ${r2(y)} ${r2(x + w)} ${r2(y + h * 0.3)}`,
    ].join(" "));
    return el;
  }

  //: A miniature of what is actually on a board, from `preview_items` /
  //: `preview_edges`, positions already normalised into 0..1 against the
  //: board's own bounds by `routes_whiteboard._board_preview`, so this draws the
  //: real layout without the client ever loading the board.
  //:
  //: **An empty board draws the empty state, not nothing.** It used to return
  //: null and each caller improvised: the Library's card mode drew no picture
  //: at all, its rows mode drew a dashed rail so the rows would still line up,
  //: and the dashboard skipped the thumbnail, so three surfaces disagreed about
  //: what an empty map looks like and two of them lost their left edge. The
  //: empty state is drawn here, once, in the same language as a real preview: a
  //: ghost of a three-node map on the same paper, which says "a map goes here"
  //: where a blank box said nothing.
  //:
  //: Built with SVG attributes and never an inline `style` string: this app's
  //: CSP drops those outright, and thirty-five of them once shipped as silently
  //: dead markup (CLAUDE.md, "a policy silently refusing the work").
  function mapPreviewDraw(svg, board, size, opts = {}) {
    const geo = MAP_PREVIEW_SIZES[size] || MAP_PREVIEW_SIZES.card;
    const items = Array.isArray(board?.preview_items) ? board.preview_items : [];
    const NS = "http://www.w3.org/2000/svg";

    //: **The board's own shape, letterboxed into the card's box.** The viewBox
    //: is drawn at `preview_aspect` (the board's width/height, which
    //: normalising the positions into 0..1 threw away) and `meet` fits it
    //: inside the element rather than stretching it to fill: a map that runs
    //: down the page used to come back as the same wide rectangle as one that
    //: runs across, and every board in the Library was the same shape as every
    //: other, which is a picture of the card, not of the board.
    const aspect = Number(board?.preview_aspect) > 0 ? Number(board.preview_aspect) : 1;
    const vw = aspect >= 1 ? MAP_PREVIEW_BASE : MAP_PREVIEW_BASE * aspect;
    const vh = aspect >= 1 ? MAP_PREVIEW_BASE / aspect : MAP_PREVIEW_BASE;
    //: **A tall map in the dashboard's short box is cropped around its centre**
    //: (L778, the owner 2026-11-12): letterboxed, a 25-topic tree drew a thin
    //: strip with no labels. `crop` shows a window of the box's own shape out
    //: of the middle, at the scale the box's width allows.
    const crop = Boolean(opts.crop) && vh / vw > geo.h / geo.w;
    const cropH = vw * (geo.h / geo.w);
    svg.setAttribute("viewBox", crop ? `0 ${round2((vh - cropH) / 2)} ${round2(vw)} ${round2(cropH)}` : `0 0 ${round2(vw)} ${round2(vh)}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    if (crop) svg.dataset.crop = "centre";
    // The scale `meet` is about to apply, so every fixed size below can be
    // expressed in the box's units and divided back out: see MAP_PREVIEW_SIZES.
    const scale = crop ? geo.w / vw : Math.min(geo.w / vw, geo.h / vh);
    const unit = 1 / scale;
    const pad = geo.pad * unit;
    const blockW = geo.blockW * unit;
    const blockH = geo.blockH * unit;
    // The drawable box, inset by the padding on both sides so an item at the
    // extreme edge of the board lands inside the thumbnail rather than half
    // outside it. Floored at zero: an extreme ratio can leave less room than
    // one block needs, and a negative span would mirror the whole picture.
    const spanX = Math.max(0, vw - pad * 2 - blockW);
    const spanY = Math.max(0, vh - pad * 2 - blockH);
    //: **Labels need width, and a letterboxed tall board has not got it.**
    //: Measured on the first run of the redesigned card: a board half as wide as
    //: it is tall draws its paper 82px across inside a 293px card, and the
    //: sixteen-character labels that read as a texture at 293px overlapped each
    //: other and the nodes they belonged to ("First branchRoot"). Below
    //: `MAP_PREVIEW_LABEL_FLOOR` of the box's width the labels come off and the
    //: shape carries the card, which is what the row size already does.
    const labels = geo.labels && vw * scale >= geo.w * MAP_PREVIEW_LABEL_FLOOR;
    const px = (x) => pad + (Number(x) || 0) * spanX;
    const py = (y) => pad + (Number(y) || 0) * spanY;

    //: **The paper.** The frame and fill used to belong to the `<svg>` element
    //: itself, which is the card's box, so the border said "this is the shape
    //: of the board" while being the shape of the card. Drawn as a rect inside
    //: the viewBox instead, it is the letterboxed board, and it is the thing a
    //: sweep can measure: its rendered width/height *is* `preview_aspect`.
    const paper = document.createElementNS(NS, "rect");
    paper.setAttribute("class", "board-minimap-paper");
    paper.setAttribute("x", "0");
    paper.setAttribute("y", "0");
    paper.setAttribute("width", String(round2(vw)));
    paper.setAttribute("height", String(round2(vh)));
    paper.setAttribute("rx", String(round2(2 * unit)));
    svg.appendChild(paper);

    if (!items.length) {
      // The one designed empty state, in the same language as a real preview:
      // a map ghosts a root with two branches; a board ghosts three loose
      // cards with no curves between them, so an empty board does not read as
      // a mind map (audit 1028 U40).
      paper.classList.add("board-minimap-paper-empty");
      const ghost = document.createElementNS(NS, "g");
      ghost.setAttribute("class", "board-minimap-ghost");
      const isMap = board?.type === "map";
      const shape = isMap
        ? [
            { x: 0.04, y: 0.5 },
            { x: 0.72, y: 0.16 },
            { x: 0.72, y: 0.84 },
          ]
        : [
            { x: 0.1, y: 0.18 },
            { x: 0.52, y: 0.4 },
            { x: 0.2, y: 0.7 },
          ];
      for (const child of isMap ? shape.slice(1) : []) {
        ghost.appendChild(
          mapPreviewEdge(NS, px, py, blockW, blockH, {
            x1: shape[0].x,
            y1: shape[0].y,
            x2: child.x,
            y2: child.y,
          })
        );
      }
      for (const node of shape) {
        const block = document.createElementNS(NS, "rect");
        block.setAttribute("x", String(round2(px(node.x))));
        block.setAttribute("y", String(round2(py(node.y))));
        block.setAttribute("width", String(round2(blockW)));
        block.setAttribute("height", String(round2(blockH)));
        block.setAttribute("rx", String(round2(Math.min(blockW, blockH) * MAP_PREVIEW_NODE_ROUNDING)));
        ghost.appendChild(block);
      }
      svg.appendChild(ghost);
      return svg;
    }

    //: **The tree, drawn first so the lines sit under the blocks** rather than
    //: across their labels. `preview_edges` is the parent→child segments in the
    //: same normalised space as the items (§9.1); an ordinary board ships an
    //: empty list and this loop does nothing, which is exactly the difference
    //: between the two kinds that a scatter of dots cannot show.
    for (const edge of Array.isArray(board.preview_edges) ? board.preview_edges : []) {
      const curve = mapPreviewEdge(NS, px, py, blockW, blockH, edge);
      // The branch's colour, from the server (`_map_branch_colors`), so the
      // thumbnail is the same picture as the canvas rather than a grey diagram
      // of it.
      if (edge.color) curve.setAttribute("stroke", edge.color);
      else curve.classList.add("board-minimap-edge-accent");
      svg.appendChild(curve);
    }

    //: **How big this thing is on the board**, in the viewBox's units, from the
    //: `w`/`h` the server now ships as fractions of the same span `x` and `y`
    //: were normalised into (INBOX 68).
    //:
    //: This is the difference between a picture of the board and a picture of
    //: the renderer. Measured before it: every block in every preview came back
    //: at one size (29.1x21.8 in the dashboard, 26.4x17.6 in the Library), so a
    //: banner across the top of a board, the column beside it and a sticky note
    //: were three identical grey rectangles, which is the owner's "grey blobs"
    //: exactly. A board's own shapes are most of what tells two boards apart.
    //:
    //: Floors, not raw values: a small object on a large board is a fraction of
    //: a viewBox unit and would vanish, and something has to be visible for the
    //: preview to be a preview. The ceiling is the drawable span, so one huge
    //: object cannot spill outside the paper it is drawn on. An older payload
    //: (a cached list from before the server sent sizes) has no `w`, and falls
    //: back to the uniform block, which is what this drew for everything.
    const sizeOf = (item) => {
      const w = Number(item.w);
      const h = Number(item.h);
      if (!(w > 0) || !(h > 0)) return { w: blockW, h: blockH };
      return {
        w: Math.min(spanX + blockW, Math.max(blockW * MAP_PREVIEW_MIN_BLOCK, w * spanX)),
        h: Math.min(spanY + blockH, Math.max(blockH * MAP_PREVIEW_MIN_BLOCK, h * spanY)),
      };
    };

    //: **Every block's painted box, collected as they are drawn**, so the label
    //: pass below can ask whether a caption has landed on something that is not
    //: its own (INBOX 263: the previews "are kinda a mess"). A label beside a
    //: block used to be placed from that block alone, with no idea that the
    //: margin it hung into was already full: measured on a six-card board,
    //: "Retry budget" was drawn 10 units into a neighbouring card and 15.9
    //: units across "Ingest pipeline".
    const drawn = [];

    //: **Nothing is drawn past the paper's edge.** `px`/`py` place an item's
    //: *top-left corner* inside the drawable span, and the span is computed
    //: from the default block's width, while `sizeOf` returns the item's own,
    //: which can be many times larger. The server's `w` compounds it: it is a
    //: fraction of the span between the items' corners (`_preview_items`), and
    //: an item wider than the distance between the outermost two corners has a
    //: `w` above 1 quite legitimately. Measured on a six-card board: cards
    //: 39.06 units wide drawn at x=76.28 in a 100-unit-wide viewBox, so a third
    //: of every card in the right-hand column was outside the thumbnail, which
    //: is most of what "the boards and maps previews are kinda a mess" is
    //: looking at.
    //:
    //: The left edge is kept and the far edge trimmed, rather than the block
    //: being moved: where a thing starts is its position, which is information;
    //: where a clipped block ends is not. A thumbnail is a crop of a board, and
    //: a large item running to the edge should be drawn running to the edge.
    //: The floor is the same one `sizeOf` uses (a fraction of the default
    //: block), not a bare number: `MAP_PREVIEW_MIN_BLOCK` is a multiplier, and
    //: reading it as viewBox units would make the smallest allowed block half a
    //: unit, which is a dot.
    const onPaper = (at, extent, floor, from, to) =>
      Math.max(floor, Math.min(extent, to - Math.max(from, at)));

    for (const item of items) {
      const nx = px(item.x);
      const ny = py(item.y);
      const raw = sizeOf(item);
      const size = {
        w: onPaper(nx, raw.w, blockW * MAP_PREVIEW_MIN_BLOCK, pad, vw - pad),
        h: onPaper(ny, raw.h, blockH * MAP_PREVIEW_MIN_BLOCK, pad, vh - pad),
      };
      //: Sketched shapes too: a caption is tested against them as obstacles
      //: (the dashboard's board drew "Store rev…" and "Next" across them).
      drawn.push({ item, x: nx, y: ny, w: size.w, h: size.h });
      if (item.kind === "sketch") {
        // The shape it was drawn with, at the size and place it was drawn, in
        // its own ink: see `mapPreviewSketch`. The stroke data itself is still
        // not shipped, which is the one thing `preview_items` deliberately
        // leaves out.
        const mark = mapPreviewSketch(NS, nx, ny, size.w, size.h, item.shape, unit);
        if (item.color) mark.setAttribute("stroke", item.color);
        else mark.classList.add("board-minimap-sketch-accent");
        svg.appendChild(mark);
        continue;
      }
      const dot = document.createElementNS(NS, "rect");
      //: **A picture gets its own ink and its own mark.** An image object is the
      //: one thing on a board with no words of its own (the server sends no
      //: label for it, and a thumbnail of a thumbnail is a different feature),
      //: so in one flat accent wash it was indistinguishable from a text box
      //: holding a paragraph. Measured on the seeded board: twelve marks, one
      //: ink. It is a quieter grey block with the universal picture glyph over
      //: it, which says "a picture is here" in the language every other surface
      //: uses for one.
      const grey = item.kind === "card"
        ? "board-minimap-card"
        : item.kind === "image"
          ? "board-minimap-image"
          : "board-minimap-object";
      // A branch node takes its own class rather than the grey one, for the
      // reason on `mapPreviewEdge`: the fill arrives as an attribute, and the
      // grey classes declare `fill`, which would win.
      dot.setAttribute("class", item.color ? "board-minimap-branch" : grey);
      dot.setAttribute("x", String(round2(nx)));
      dot.setAttribute("y", String(round2(ny)));
      dot.setAttribute("width", String(round2(size.w)));
      dot.setAttribute("height", String(round2(size.h)));
      // Rounded like the node it stands for, and rounded by its own size rather
      // than by a fixed 1.5: the block is drawn at a different number of viewBox
      // units on every board shape now, so a constant radius was a sharp corner
      // on one card and a pill on the next. Capped at
      // `MAP_PREVIEW_CORNER_UNITS`, which is what stopped these reading as blobs
      // (INBOX 164): the fraction alone was 35% of a block's
      // short side, measured.
      dot.setAttribute("rx", String(round2(Math.min(
        MAP_PREVIEW_CORNER_UNITS * unit,
        Math.min(size.w, size.h) * MAP_PREVIEW_NODE_ROUNDING
      ))));
      // The grey blocks are faded because an unlabelled box is texture; a
      // coloured node is carrying which branch it belongs to, so it is drawn at
      // full strength (`.board-minimap-branch`).
      if (item.color) dot.setAttribute("fill", item.color);
      svg.appendChild(dot);
      if (item.kind === "image") {
        //: The glyph, inside the block and scaled to it: a horizon line with a
        //: sun over it, which is the picture icon everywhere else in the app.
        //: Skipped on a block too small to hold it, where it would be two
        //: smudges on a grey square.
        const short = Math.min(size.w, size.h);
        if (short > 6 * unit) {
          const mark = document.createElementNS(NS, "path");
          mark.setAttribute("class", "board-minimap-image-mark");
          mark.setAttribute("stroke-width", String(round2(1.2 * unit)));
          const x0 = nx + size.w * 0.18;
          const x1 = nx + size.w * 0.82;
          const base = ny + size.h * 0.72;
          mark.setAttribute("d", [
            `M${round2(x0)} ${round2(base)}`,
            `L${round2(nx + size.w * 0.42)} ${round2(ny + size.h * 0.42)}`,
            `L${round2(nx + size.w * 0.6)} ${round2(base)}`,
            `M${round2(nx + size.w * 0.62)} ${round2(base)}`,
            `L${round2(nx + size.w * 0.74)} ${round2(ny + size.h * 0.56)}`,
            `L${round2(x1)} ${round2(base)}`,
          ].join(" "));
          svg.appendChild(mark);
        }
        continue;
      }
    }

    //: **The labels, placed after every block is drawn and against all of
    //: them.** Reported as "the boards and maps previews are kinda a mess", and
    //: measured on a six-card board before this: "Retry budget" drawn 10 units
    //: into a neighbouring card and 15.9 across "Ingest pipeline", and a
    //: caption starting at x=100.1 in a 100-unit-wide viewBox.
    //:
    //: Three things were wrong and each needed the pass to know more than one
    //: item at a time. The width was estimated from a characters-times-0.55
    //: constant, and a budget that under-reports puts the text past the room it
    //: was granted; the margin a label hangs into was treated as empty when it
    //: often holds the next card; and nothing looked at the other labels at
    //: all. So: measure the text, test the box against the blocks and against
    //: the labels already kept, and drop a caption that has nowhere to go.
    //:
    //: **Dropping is the right answer when there is no room**, not shrinking or
    //: overlapping. A preview is a picture you read at a glance, and two
    //: captions across each other are less use than one caption and a block
    //: with no words on it: the block, its size, its place and its colour still
    //: say what is there.
    //:
    //: Biggest first, so when two want the same margin the one on the larger
    //: thing keeps it, which is also the one a reader's eye goes to.
    if (labels) {
      const kept = [];
      const ordered = drawn
        .filter((row) => row.item.label && row.item.kind !== "image" && row.item.kind !== "sketch")
        .sort((a, b) => b.w * b.h - a.w * a.h);
      for (const row of ordered) {
        const { item } = row;
        const fontUnits = geo.font * unit;
        const perChar = fontUnits * MAP_PREVIEW_CHAR_WIDTH;
        const gap = 1.5 * unit;
        //: The label's painted height. `getBBox` would give it exactly, and
        //: cannot be asked here (the preview is not in the document yet), but a
        //: cap height plus descender is a fixed fraction of the type size in
        //: any family, which is enough to test a box with.
        const lineH = fontUnits * 1.15;

        //: **Inside the shape when the shape can hold it**, beside it when it
        //: cannot. Reported as the text "sitting off its shapes": before a
        //: topic was drawn at its own size, a block was a fixed 9x6 units
        //: whatever it stood for and nothing could ever contain a word. A
        //: 200x56 node has room for its own name, which is where a person
        //: reading a map expects to find it.
        //:
        //: Nearly all of it, or none: the earlier version cut to fit and drew
        //: "Retr…", "Inge…" and "Open…" on three cards, which is three cards
        //: that cannot be told apart by the one thing meant to tell them apart.
        const insideRoom = row.w - perChar * 2;
        const tall = row.h >= fontUnits * 1.6;
        const full = mapPreviewTextWidth(item.label, fontUnits);
        const insideChars = Math.floor(insideRoom / perChar);
        const fits = tall && full <= insideRoom
          && insideChars >= MAP_PREVIEW_MIN_INSIDE_CHARS;

        let shown = null;
        let box = null;
        let anchor = "start";
        let x = 0;
        let y = 0;
        if (fits) {
          shown = item.label;
          x = row.x + row.w / 2;
          y = row.y + row.h / 2 + fontUnits * 0.36;
          anchor = "middle";
          box = { x: x - full / 2, y: y - fontUnits * 0.8, w: full, h: lineH };
        } else {
          //: Both margins measured from the block's own edges to the paper's,
          //: and the wider one tried first. `nx > vw / 2` was the old test and
          //: it reads the block's *left* edge, so a wide item just left of
          //: centre was labelled to its right at `nx + size.w + gap`, which on
          //: a 200-unit-wide topic is past the paper (INBOX 174).
          const roomRight = Math.max(0, vw - (row.x + row.w + gap));
          const roomLeft = Math.max(0, row.x - gap);
          const roomBelow = Math.max(0, vh - (row.y + row.h + gap));
          const roomAbove = Math.max(0, row.y - gap);
          //: **Four places, not two: beside, and under or over.** Under a
          //: thumbnail's block is where a caption goes in every file browser
          //: ever written, and it was not tried at all, so a board whose cards
          //: sit in a row lost every title but the outermost: the margin left
          //: and right is the next card, and there was nowhere else to look.
          //: Measured on a six-card board: 2 of 6 titles drawn before these two
          //: positions existed.
          //:
          //: The wider margin first, then the taller one, so the caption lands
          //: where there is most room and a board only falls back to stacking
          //: text under a block when its sides are genuinely full.
          const places = [
            { side: "left", room: roomLeft },
            { side: "right", room: roomRight },
            { side: "below", room: roomBelow },
            { side: "above", room: roomAbove },
          ].sort((a, b) => b.room - a.room);
          //: Each vertical position is tried three ways: centred under its
          //: block, then flushed to the block's left edge, then to its right.
          //: A centred caption is the one to want, and on a crowded board it is
          //: often the only one of the three that meets the neighbour: sliding
          //: it to an edge it already shares with its own block keeps it
          //: attached to the right thing while stepping out of the way.
          const alignments = ["centre", "start", "end"];
          const tries = [];
          for (const place of places) {
            if (place.side === "below" || place.side === "above") {
              for (const align of alignments) tries.push({ ...place, align });
            } else {
              tries.push({ ...place, align: "centre" });
            }
          }
          for (const place of tries) {
            const side = place.side;
            const vertical = side === "below" || side === "above";
            //: A caption under a block is bounded by the *paper's* width, not
            //: by the margin below it, which is what has to hold its height.
            if (vertical && place.room < lineH + gap) continue;
            const room = vertical
              ? Math.min(row.x + row.w, vw - row.x) * 2 - perChar
              : place.room - perChar;
            if (room < perChar * MAP_PREVIEW_MIN_OUTSIDE_CHARS) continue;
            const cut = mapPreviewFitText(item.label, fontUnits, room);
            if (!cut) continue;
            const width = mapPreviewTextWidth(cut, fontUnits);
            const centre = row.x + row.w / 2;
            const baseline = side === "below"
              ? row.y + row.h + gap + fontUnits * 0.8
              : side === "above"
                ? row.y - gap
                : row.y + row.h * 0.73;
            //: Where a vertical caption's own box starts, given the alignment
            //: this attempt is trying.
            const under = place.align === "start"
              ? row.x
              : place.align === "end"
                ? row.x + row.w - width
                : centre - width / 2;
            const left = side === "left"
              ? row.x - gap - width
              : side === "right"
                ? row.x + row.w + gap
                : under;
            const candidate = { x: left, y: baseline - fontUnits * 0.8, w: width, h: lineH };
            //: **Off the paper is a reason to try the next position, not a
            //: reason to give up on the label.** This test used to sit after
            //: the loop, which made the first candidate that missed the other
            //: blocks the last one considered: measured on the seeded board,
            //: "Retry budget" cleared every block centred under its own card,
            //: began at x=-1.21, and was then dropped without the two aligned
            //: positions beside it ever being tried, one of which fits. Two
            //: reasons to reject a place belong in the same list.
            if (!mapPreviewOnPaper(candidate, vw, vh)) continue;
            //: Its own block is not a clash: a caption beside a card may touch
            //: the card it names, and often has to on a crowded board.
            const clash = drawn.some((other) => other !== row && mapPreviewOverlaps(candidate, other))
              || kept.some((other) => mapPreviewOverlaps(candidate, other));
            if (clash) continue;
            shown = cut;
            //: The text anchor has to match the box that was just tested, or
            //: the collision test is about a rectangle the browser never draws.
            anchor = side === "left"
              ? "end"
              : side === "right"
                ? "start"
                : place.align === "start" ? "start" : place.align === "end" ? "end" : "middle";
            x = side === "left"
              ? row.x - gap
              : side === "right"
                ? row.x + row.w + gap
                : place.align === "start" ? row.x : place.align === "end" ? row.x + row.w : centre;
            y = baseline;
            box = candidate;
            break;
          }
        }
        if (!shown || !box) continue;
        //: **A label inside its own block is still checked against the labels
        //: already kept.** Blocks legitimately overlap on a board (a card
        //: dropped on another, a topic over a branch), so two captions drawn in
        //: the middle of two overlapping blocks land on top of each other
        //: however correct each one is on its own: measured on a board with
        //: stacked cards, six pairs of identical titles across each other. It
        //: is not checked against the *blocks*, because sitting on a block is
        //: what an inside label is for.
        if (fits && kept.some((other) => mapPreviewOverlaps(box, other))) continue;
        //: The paper's own edges for the inside case, which has only the one
        //: position to offer and so tests them here rather than in a loop. A
        //: caption sliced by the thumbnail's edge reads as a rendering fault,
        //: which is what it is.
        if (!mapPreviewOnPaper(box, vw, vh)) continue;

        const text = document.createElementNS(NS, "text");
        text.setAttribute("class", "board-minimap-label");
        text.setAttribute("x", String(round2(x)));
        text.setAttribute("y", String(round2(y)));
        if (anchor !== "start") text.setAttribute("text-anchor", anchor);
        // The type size, in the box's units divided back out, for the same
        // reason the blocks are: a fixed CSS `font-size` here is in viewBox
        // units, so the labels on a square board came out half the size of the
        // labels on a wide one. The stylesheet keeps the colour and the family.
        text.setAttribute("font-size", String(round2(fontUnits)));
        if (fits) {
          text.classList.add("board-minimap-label-inside");
          //: A class, not a `fill` attribute, and this is the trap the blocks
          //: above already carry a note about: `.board-minimap-label` declares
          //: `fill` in the stylesheet, and a CSS declaration beats a
          //: presentation attribute however specific the attribute looks.
          //: Setting the attribute changed nothing at all, measured: 3.82:1
          //: before and after.
          const onColour = item.color ? mapPreviewOnColour(item.color) : null;
          if (onColour) text.classList.add(`board-minimap-label-${onColour}`);
        }
        text.textContent = shown;
        svg.appendChild(text);
        kept.push(box);
      }
    }
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { mapPreviewDraw });
})();
