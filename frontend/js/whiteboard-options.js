(() => {
  // whiteboard-options.js: the board's own options in the Format panel's Board section (WHITEBOARD_PLAN,
  // wbformat2). Each is kept on the board in its `background` settings (`wbSetBackground`), so it syncs, is in
  // a backup, and is undone like the board's colour: grid spacing and colour, alignment guides, page view,
  // the shadow new shapes start with, paper size and orientation, and the units the position and size fields
  // show. Nothing here is a global: the board reads it through `wbFmtState.opts`, which `wbApplyBackground` calls
  // (`sync`) whenever the board's settings load or change.
  const $ = (id) => document.getElementById(id);
  const DEFAULT_GRID = 24;

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
    $("wb-bo-grid-color")?.addEventListener("change", (e) => wbSetBackground({ grid_color: e.target.value }));
    $("wb-bo-grid-reset")?.addEventListener("click", () => wbSetBackground({ grid_color: null }));
  }

  //: After each board render: the page frames follow content that has grown past the last page.
  wbFmtState.opts = { sync, afterRender: () => drawPages(wbBoardBackground()) };
  onSurface("board", wire);
})();
