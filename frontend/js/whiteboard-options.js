(() => {
  // whiteboard-options.js: the board's own options in the Format panel's Board section (WHITEBOARD_PLAN,
  // wbformat2). Each is kept on the board in its `background` settings (`wbSetBackground`), so it syncs, is in
  // a backup, and is undone like the board's colour: grid spacing and colour, alignment guides, page view,
  // the shadow new shapes start with, paper size and orientation, and the units the position and size fields
  // show. Nothing here is a global: the board reads it through `wbFmtState.opts`, which `wbApplyBackground` calls
  // (`sync`) whenever the board's settings load or change.
  const $ = (id) => document.getElementById(id);
  const DEFAULT_GRID = 24;

  //: **Units** (WHITEBOARD_PLAN, rulers and units): board lengths are pixels, 96 to the inch. A board may show them in
  //: another unit: the Format panel's position and size fields and the rulers. Stored and moved in pixels always.
  const PPU = { px: 1, mm: 96 / 25.4, cm: 96 / 2.54, in: 96, pt: 96 / 72 };
  const DECIMALS = { px: 0, mm: 1, cm: 2, in: 3, pt: 1 };
  let unit = "px";
  //: A length in pixels as the text a field shows, in `u` (the board's unit by default).
  function show(px, u = unit) {
    return String(Number((px / PPU[u]).toFixed(DECIMALS[u])));
  }
  //: What was typed, in `u`, as pixels (to the thousandth), or null when it is not a number.
  function read(text, u = unit) {
    const n = Number(String(text).trim() === "" ? NaN : text);
    return Number.isFinite(n) ? Math.round(n * PPU[u] * 1000) / 1000 : null;
  }

  //: The ruler's ticks over a stretch of board (`from` to `to`, pixels) at zoom `k`: a major tick every 1, 2 or 5 times a
  //: power of ten of the unit, the first step that leaves 60 screen pixels for its label, with minor ticks between.
  //: Each is `{v, at, major}`: its value in the unit and where it sits on the board in pixels.
  function ticks(from, to, k, u = unit) {
    const ppu = PPU[u];
    let step = 1, mantissa = 1;
    let power = 1e-3;
    search: for (; power <= 1e9; power *= 10) {
      for (const m of [1, 2, 5]) {
        if (m * power * ppu * k >= 60) {
          step = m * power;
          mantissa = m;
          break search;
        }
      }
    }
    const divisions = mantissa === 2 ? 4 : 5;
    const minor = step / divisions;
    const first = Math.floor(from / ppu / minor), last = Math.ceil(to / ppu / minor);
    const out = [];
    for (let i = first; i <= last && out.length < 600; i += 1) {
      const v = Number((i * minor).toFixed(6));
      out.push({ v, at: v * ppu, major: i % divisions === 0 });
    }
    return out;
  }

  //: **The rulers** (View > Rulers, a switch kept on this device): one strip along the top and one down the left, in the
  //: board's unit, redrawn on each pan and zoom by `drawRulers` (called from the zoom frame). Two SVGs over the canvas
  //: that take no pointer: the ticks are one path each and the labels are text, so a redraw is a handful of nodes.
  const RULER = 20;
  let rulersOn = false, rulersDrawn = false;
  const SVG = "http://www.w3.org/2000/svg";
  function ruler(id, horizontal) {
    let el = $(id);
    if (el) return el;
    const host = $("whiteboard-container");
    if (!host) return null;
    el = document.createElementNS(SVG, "svg");
    el.setAttribute("id", id);
    el.setAttribute("class", `wb-ruler ${horizontal ? "wb-ruler-top" : "wb-ruler-left"}`);
    el.setAttribute("aria-hidden", "true");
    host.append(el);
    return el;
  }
  function drawRulers(t = null) {
    //: Off is the common case and this runs every zoom frame, so it asks nothing of the page.
    if (!rulersOn && !rulersDrawn) return;
    const host = $("whiteboard-container");
    if (!rulersOn || !host || typeof d3 === "undefined") {
      $("wb-ruler-top")?.remove();
      $("wb-ruler-left")?.remove();
      rulersDrawn = false;
      return;
    }
    rulersDrawn = true;
    const tf = t || d3.zoomTransform(host);
    const width = host.clientWidth, height = host.clientHeight;
    for (const [id, horizontal] of [["wb-ruler-top", true], ["wb-ruler-left", false]]) {
      const el = ruler(id, horizontal);
      if (!el) continue;
      const length = horizontal ? width : height, offset = horizontal ? tf.x : tf.y;
      el.setAttribute("width", String(horizontal ? width : RULER));
      el.setAttribute("height", String(horizontal ? RULER : height));
      let d = "";
      const labels = [];
      for (const tick of ticks((0 - offset) / tf.k, (length - offset) / tf.k, tf.k)) {
        const at = Math.round(offset + tick.at * tf.k) + 0.5;
        const len = tick.major ? RULER : RULER / 2;
        d += horizontal ? `M${at} ${RULER}V${RULER - len}` : `M${RULER} ${at}H${RULER - len}`;
        if (tick.major) labels.push([at, String(tick.v)]);
      }
      const path = document.createElementNS(SVG, "path");
      path.setAttribute("d", d);
      el.replaceChildren(path);
      for (const [at, text] of labels) {
        const label = document.createElementNS(SVG, "text");
        label.textContent = text;
        if (horizontal) {
          label.setAttribute("x", String(at + 3));
          label.setAttribute("y", "9");
        } else {
          label.setAttribute("transform", `translate(9 ${at - 3}) rotate(-90)`);
        }
        el.append(label);
      }
    }
  }

  //: Paint the controls from the board's settings; a field being typed in is left alone.
  function sync(bg) {
    const put = (id, value, prop = "value") => {
      const el = $(id);
      if (el && document.activeElement !== el) el[prop] = value;
    };
    put("wb-bo-grid-size", bg.grid_size || "");
    put("wb-bo-guides", bg.guides !== false, "checked");
    put("wb-bo-pageview", bg.page_view === true, "checked");
    put("wb-bo-shadow", bg.shadow_default === true, "checked");
    put("wb-bo-units", bg.units || "px");
    unit = PPU[bg.units] ? bg.units : "px";
    fieldUnits();
    drawRulers();
    put("wb-bo-paper", bg.paper || "a4");
    put("wb-bo-orient", bg.orientation || "portrait");
    put("wb-bo-paper-w", bg.paper_w || "");
    put("wb-bo-paper-h", bg.paper_h || "");
    const custom = $("wb-bo-custom");
    if (custom) custom.hidden = bg.paper !== "custom";
    drawPages(bg);
    put("wb-bo-grid-color", bg.grid_color || "#888888");
  }

  //: **Page view** (draw.io's): the page frames the PDF export prints, dashed, in board units under everything. A
  //: board has no edge, so the pages tile from the origin as far as the content reaches (or one page when it is
  //: empty), at most 100. Drawn into the board's own zoom group, so it pans and zooms with the board for free.
  const MAX_PAGES = 100;
  let pagesKey = "";
  function drawPages(bg) {
    const zoom = $("wb-zoom-group");
    let group = $("wb-page-view");
    if (!zoom || bg.page_view !== true || typeof wbContentBounds !== "function") {
      group?.remove();
      pagesKey = "";
      return;
    }
    const [pw, ph] = wbPdf.pagePx(bg);
    const box = wbContentBounds();
    const cols = box ? Math.max(1, Math.ceil(box.maxX / pw)) : 1, rows = box ? Math.max(1, Math.ceil(box.maxY / ph)) : 1;
    const c0 = box ? Math.min(0, Math.floor(box.minX / pw)) : 0, r0 = box ? Math.min(0, Math.floor(box.minY / ph)) : 0;
    const key = `${pw}x${ph}:${c0},${r0},${cols},${rows}`;
    if (key === pagesKey && group?.isConnected) return;
    pagesKey = key;
    if (!group) {
      group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("id", "wb-page-view");
      group.setAttribute("aria-hidden", "true");
    }
    if (group.parentNode !== zoom || zoom.firstChild !== group) zoom.insertBefore(group, zoom.firstChild);
    group.replaceChildren();
    let made = 0;
    for (let r = r0; r < rows && made < MAX_PAGES; r += 1) {
      for (let c = c0; c < cols && made < MAX_PAGES; c += 1) {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("class", "wb-page-frame");
        rect.setAttribute("x", String(c * pw));
        rect.setAttribute("y", String(r * ph));
        rect.setAttribute("width", String(pw));
        rect.setAttribute("height", String(ph));
        group.append(rect);
        made += 1;
      }
    }
  }

  //: The position and size fields show the unit: its name beside them, whole steps in pixels and any step in the rest.
  function fieldUnits() {
    for (const row of document.querySelectorAll('.wb-fmt-row[data-fmt="geometry"][data-unit]')) row.dataset.unit = unit;
    for (const id of ["wb-fmt-x", "wb-fmt-y", "wb-fmt-w", "wb-fmt-h"]) {
      const el = $(id);
      if (!el) continue;
      el.step = unit === "px" ? "1" : "any";
      if (id === "wb-fmt-w" || id === "wb-fmt-h") el.min = unit === "px" ? "8" : "";
    }
    wbFormatSync();
  }

  //: A number box: blank is the default (the setting is removed), else clamped to the server's bounds.
  const boxValue = (el, min, max) => (el.value === "" ? null : Math.max(min, Math.min(max, Math.round(Number(el.value) || 0))));

  function wire() {
    $("wb-bo-grid-size")?.addEventListener("change", (e) => {
      const size = boxValue(e.target, 4, 200);
      wbSetBackground({ grid_size: size === DEFAULT_GRID ? null : size }).then((ok) => ok && wbAnnounce(size ? `Grid size ${size}.` : "Grid size default."));
    });
    for (const [id, key, off] of [["wb-bo-guides", "guides", false], ["wb-bo-pageview", "page_view", true], ["wb-bo-shadow", "shadow_default", true]]) {
      $(id)?.addEventListener("change", (e) => {
        //: Only the non-default value is stored; the default clears the setting.
        wbSetBackground({ [key]: e.target.checked === off ? off : null }).then((ok) => ok && wbAnnounce(`${e.target.getAttribute("aria-label")} ${e.target.checked ? "on" : "off"}.`));
      });
    }
    for (const [id, key] of [["wb-bo-paper", "paper"], ["wb-bo-orient", "orientation"]]) {
      $(id)?.addEventListener("change", (e) => wbSetBackground({ [key]: e.target.value }).then((ok) => ok && wbAnnounce(`${e.target.getAttribute("aria-label")} ${e.target.selectedOptions[0].textContent}.`)));
    }
    for (const [id, key] of [["wb-bo-paper-w", "paper_w"], ["wb-bo-paper-h", "paper_h"]]) {
      $(id)?.addEventListener("change", (e) => wbSetBackground({ [key]: boxValue(e.target, 50, 2000) }));
    }
    $("wb-bo-units")?.addEventListener("change", (e) => wbSetBackground({ units: e.target.value }).then((ok) => ok && wbAnnounce(`Units ${e.target.selectedOptions[0].textContent}.`)));
    const rulerBox = $("wb-view-rulers");
    if (rulerBox) {
      const apply = (on) => {
        rulersOn = on;
        rulerBox.checked = on;
        drawRulers();
      };
      apply(prefs.get("wb-view-rulers", null) === "on");
      rulerBox.addEventListener("change", () => {
        prefs.set("wb-view-rulers", rulerBox.checked ? "on" : "off");
        apply(rulerBox.checked);
      });
    }
    $("wb-bo-grid-color")?.addEventListener("change", (e) => wbSetBackground({ grid_color: e.target.value }));
    $("wb-bo-grid-reset")?.addEventListener("click", () => wbSetBackground({ grid_color: null }));
  }

  //: After each board render: the page frames follow content that has grown past the last page.
  wbFmtState.opts = { sync, afterRender: () => drawPages(wbBoardBackground()), show, read, ticks, drawRulers };
  onSurface("board", wire);
})();
