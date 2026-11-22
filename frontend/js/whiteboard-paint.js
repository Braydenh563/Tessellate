(() => {
  // whiteboard-paint.js: background, cursors, highlighter, votes and timer, moved out of whiteboard.js (L634).
  // Wrapped: only what other files call goes on `window`; nothing here runs at load.

  //: The theme's own board colour as a hex string, read with no colour of the
  //: board's on the container, so "reset" still means the current theme.
  function wbThemeBoardHex() {
    const el = wbInstances.container();
    if (!el) return null;
    const rgb = getComputedStyle(el).backgroundColor;
    const m = rgb.match(/(\d+),\s*(\d+),\s*(\d+)/);
    return m ? "#" + m.slice(1, 4).map((n) => Number(n).toString(16).padStart(2, "0")).join("") : null;
  }

  function wbApplyBackground() {
    const el = wbInstances.container();
    if (!el) return;
    const bg = wbBoardBackground();
    el.style.removeProperty("--wb-board-bg");
    const themeHex = bg.color ? null : wbThemeBoardHex();
    if (bg.color) el.style.setProperty("--wb-board-bg", bg.color);
    // `mediaSrc`, not the bare url, a CSS `background-image: url(...)` is a
    // plain resource load, same as `<img src>`, so it never attaches
    // X-Auth-Token either.
    el.style.setProperty("--wb-bg-image", bg.image ? `url("${mediaSrc(bg.image)}")` : "none");
    const picker = document.getElementById("wb-bg-color-picker");
    if (picker && (bg.color || themeHex)) picker.value = bg.color || themeHex;
    //: The board's grid: its spacing and its colour (the theme's own tint when none is set).
    WB_GRID_SPACING = bg.grid_size || 24;
    if (bg.grid_color) el.style.setProperty("--wb-grid-ink", bg.grid_color);
    else el.style.removeProperty("--wb-grid-ink");
    wbSyncGridToTransform();
    wbFmtState.opts?.sync(bg);
    const fold = document.getElementById("wb-sticky-fold");
    if (fold) fold.checked = bg.sticky_fold !== false;
    const rough = document.getElementById("wb-rough-toggle");
    if (rough) rough.checked = bg.rough === true;
    const imageButton = document.getElementById("wb-bg-image");
    if (imageButton) {
      const words = bg.image ? "Remove the background image" : "Set a background image";
      imageButton.title = words;
      imageButton.setAttribute("aria-label", words);
    }
  }

  //: Writes a patch of the board's look and pushes one undo step for it. The
  //: default scratch board has no note to keep settings on, so it says so.
  async function wbSetBackground(patch, { undo = true } = {}) {
    const id = window.currentBoardId;
    if (!id) {
      toast("The default board keeps the theme's look. Make a board of your own to give it one.", "info");
      wbApplyBackground();
      return false;
    }
    const before = { ...wbBoardBackground() };
    try {
      const out = await apiJson(`/whiteboard/boards/${id}`, { method: "PUT", body: JSON.stringify({ background: patch }) });
      if (String(window.currentBoardId ?? "") !== String(id)) return false;
      wbState.background = out.background || {};
    } catch (err) {
      toast(err.message || voiceLine("failed", "change the background"), true);
      wbApplyBackground();
      return false;
    }
    wbApplyBackground();
    //: The sticky notes' fold and the hand-drawn look follow the board's.
    if ("sticky_fold" in patch || "rough" in patch) wbScheduleRender();
    if (undo) wbPushUndo({ action: "background", before });
    return true;
  }

  //: **Once per board on this device, the old per-browser look moves onto the
  //: board.** A board that already has a look of its own is never overwritten.
  //: The per-board image key is removed once moved; the old colour was one key
  //: for every board, so it stays until each board this device opens has taken
  //: it, and a flag per board says which have.
  async function wbMigrateBackground() {
    const id = window.currentBoardId;
    if (!id || wbIsMap()) return;
    let image = null, color = null, done = false;
    try {
      image = prefs.get(`wb-bg-image-${id}`, null);
      color = prefs.get("wb-bg-color", null);
      done = prefs.get(`wb-bg-moved-${id}`, null) === "1";
    } catch {
      return;
    }
    if (done || (!image && !color)) return;
    const have = wbBoardBackground();
    const patch = {};
    if (image && !have.image && /^\/media\/[A-Za-z0-9]/.test(image)) patch.image = image;
    if (color && !have.color && /^#[0-9a-f]{6}$/i.test(color)) patch.color = color;
    if (Object.keys(patch).length && !(await wbSetBackground(patch, { undo: false }))) return;
    try {
      prefs.remove(`wb-bg-image-${id}`);
      prefs.set(`wb-bg-moved-${id}`, "1");
    } catch {
      // Private mode: it is on the board now either way.
    }
  }

  // A tiny inline SVG baked into a `cursor:` value, so the OS/GPU renders and
  // positions it: zero JS on the hot path. This replaces an earlier version
  // that tracked the pointer with a `mousemove`-positioned `<div>`: reported
  // (and reproduced) as "my mouse keeps snapping to an invisible grid", a
  // JS-positioned cursor only moves on however often `mousemove` actually
  // fires, which is both slower and less regular than the compositor placing
  // a real cursor image, so on a fast swipe the dot visibly lagged and then
  // jumped to catch up. A `cursor:` image has no such step: once set, the
  // browser draws it exactly like the system arrow.
  function wbCursorUrl(inner, { size = 26, hx = 3, hy = size - 3 } = {}) {
    const svg =
      `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" ` +
      `viewBox="0 0 ${size} ${size}">${inner}</svg>`;
    return `url("data:image/svg+xml,${encodeURIComponent(svg)}") ${hx} ${hy}`;
  }
  //: Takes the pen width rather than reading it: `WB_STROKE_WIDTH` is a `let`
  //: inside `initWhiteboard`, not a module constant, so a module-level function
  //: that read it threw `WB_STROKE_WIDTH is not defined` on the first stroke
  //: (found by the sweep, which drew nothing at all and said so).
  function wbHighlighterWidth(penWidth) {
    return highlighterWidth(penWidth);
  }

  //: **The blend follows the backdrop.** Multiply is worth 20 luminance units a
  //: pass on a light board and 3 on a dark one (measured with pngpixel.py on
  //: two crossing strokes: 252.9 / 229.6 / 211.5 light, 26.4 / 23.6 / 22.0
  //: dark), so on a dark board it is a blend that costs the ink its colour and
  //: buys almost nothing. `screen` is the same signal in the direction a dark
  //: surface can move. Inline rather than a class because the export clones
  //: these nodes into a standalone SVG where a stylesheet does not follow them,
  //: which is also why it has to be re-applied when the mode changes: see
  //: `wbRefreshHighlighterBlend`.
  function wbHighlighterBlend() {
    return highlighterBlend(document.documentElement.dataset.mode === "dark");
  }

  //: The Format panel's shadow (decision 19): one soft drop on a shape, a line,
  //: a text box and a picture, and in the export. The offset and blur are the
  //: item's own (`shadow_x`, `shadow_y`, `shadow_blur`; wb5), and an item that
  //: set none keeps the original 0, 2 and 4.
  function wbShadowOf(look) {
    const n = (v, d) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? d : Number(v));
    return { x: n(look?.shadow_x, 0), y: n(look?.shadow_y, 2), blur: n(look?.shadow_blur, 4) };
  }

  //: **A rectangle crop** (`data.trim`, percent of the picture cut from the top, right, bottom and left) shares
  //: this clip: the shape (or a plain rectangle) is fitted inside what the trim leaves. With `size` ([w, h]) the
  //: answer is the export's SVG path at that size, without it the board's CSS `clip-path`; "" clips nothing.
  function wbCropClip(crop, trim, size) {
    const known = Object.prototype.hasOwnProperty.call(WB_CROPS, crop);
    const [top, right, bottom, left] = [0, 1, 2, 3].map((i) => Math.max(0, Math.min(90, Number(trim?.[i]) || 0)) / 100);
    const fits = left + right < 0.95 && top + bottom < 0.95;
    const [x0, y0, x1, y1] = fits ? [left, top, 1 - right, 1 - bottom] : [0, 0, 1, 1];
    if (!known && x0 + y0 + (1 - x1) + (1 - y1) === 0) return "";
    const [w, h] = size || [100, 100];
    const num = (v) => +(v * 100).toFixed(2);
    const points = (known ? WB_CROPS[crop] : [[0, 0], [1, 0], [1, 1], [0, 1]]);
    if (points) {
      const at = points.map(([x, y]) => [x0 + x * (x1 - x0), y0 + y * (y1 - y0)]);
      return size ? `M ${at.map(([x, y]) => `${+(x * w).toFixed(2)} ${+(y * h).toFixed(2)}`).join(" L ")} Z`
        : `polygon(${at.map(([x, y]) => `${num(x)}% ${num(y)}%`).join(", ")})`;
    }
    if (!size) return `ellipse(${num((x1 - x0) / 2)}% ${num((y1 - y0) / 2)}% at ${num((x0 + x1) / 2)}% ${num((y0 + y1) / 2)}%)`;
    const [rx, ry, cy] = [(x1 - x0) * w / 2, (y1 - y0) * h / 2, (y0 + y1) * h / 2];
    return `M ${x0 * w} ${cy} A ${rx} ${ry} 0 1 0 ${x1 * w} ${cy} A ${rx} ${ry} 0 1 0 ${x0 * w} ${cy} Z`;
  }

  function wbCropPath(crop, w, h, trim) {
    return wbCropClip(crop, trim, [w, h]);
  }

  //: **Edit image** (WHITEBOARD_PLAN section 1): a picture's quarter turn, flips
  //: and filters live in `data` (`turn`, `flip_x`, `flip_y`, `grey`, `bright`,
  //: `contrast`) and are drawn over the untouched file, so Undo and "Reset" are
  //: exact. The crop, trim and corner clips sit on the picture's own (turned)
  //: frame, so they turn with it; a quarter turn swaps that frame's width and height.
  //: One function (the shared scope has a name cap): `filter` is the CSS filter, `w`/`h` the picture's own frame,
  //: `transform` the CSS one and `svg` the export's.
  function wbPixel(data, w, h) {
    const level = (v) => (Number.isInteger(v) && v >= 20 && v <= 200 && v !== 100 ? v / 100 : 0);
    const filter = [data?.grey === true ? "grayscale(1)" : "", level(data?.bright) ? `brightness(${level(data.bright)})` : "",
      level(data?.contrast) ? `contrast(${level(data.contrast)})` : ""].filter(Boolean).join(" ");
    const turn = [90, 180, 270].includes(data?.turn) ? data.turn : 0;
    const quarter = turn === 90 || turn === 270;
    const fx = data?.flip_x === true ? -1 : 1;
    const fy = data?.flip_y === true ? -1 : 1;
    const parts = [];
    if (quarter) parts.push("translate(-50%, -50%)");
    if (fx < 0 || fy < 0) parts.push(`scale(${fx}, ${fy})`);
    if (turn) parts.push(`rotate(${turn}deg)`);
    const [lw, lh] = quarter ? [h, w] : [w, h];
    const plain = !turn && fx > 0 && fy > 0;
    return { w: lw, h: lh, turn, filter, transform: parts.join(" "),
      svg: plain ? "" : `translate(${w / 2} ${h / 2}) scale(${fx} ${fy}) rotate(${turn}) translate(${-lw / 2} ${-lh / 2})` };
  }

  function wbVotesAfter(current, delta) {
    const next = Math.max(0, Math.min(WB_VOTE_MAX, (Number(current) || 0) + delta));
    return next || undefined;
  }

  function wbVoteTargets() {
    return wbFmtEntries().filter((e) => e.kind === "object" && !WB_MAP_KINDS.has(e.item.kind) && !wbIsLocked(e.kind, e.item));
  }

  async function wbSetVotes(entries, change) {
    await wbRecordGesture(async () => {
      for (const e of entries) {
        const votes = change(e.item.data?.votes);
        const data = { ...e.item.data };
        if (votes) data.votes = votes;
        else delete data.votes;
        e.item.data = data;
      }
      await wbSaveMany(entries.map((e) => ({ kind: "object", item: e.item })));
    });
    wbScheduleRender();
  }

  async function wbVoteSelection(delta) {
    const targets = wbVoteTargets();
    if (!targets.length) {
      toast("Select a note, text box, picture or frame to vote on.");
      return;
    }
    await wbSetVotes(targets, (n) => wbVotesAfter(n, delta));
    const total = targets.reduce((sum, e) => sum + (e.item.data?.votes || 0), 0);
    wbAnnounce(delta > 0 ? `Dot added: ${nounCount(total, "dot")} on the selection.` : `Dot taken off: ${nounCount(total, "dot")} on the selection.`);
  }

  async function wbClearVotes() {
    const held = (wbState.objects || []).filter((o) => !WB_MAP_KINDS.has(o.kind) && o.data?.votes && !wbIsLocked("object", o));
    if (!held.length) {
      toast("No item on this board has a vote dot.");
      return;
    }
    await wbSetVotes(held.map((item) => ({ kind: "object", item })), () => undefined);
    wbAnnounce(`Dots cleared from ${nounCount(held.length, "item")}.`);
  }

  //: The dots in an export: the same pill, at the corner the board draws it,
  //: in the colours the live badge shows.
  function wbSvgVotes(obj) {
    const badge = wbInstances.query(`#wb-html-layer .wb-object[data-id="${obj.id}"] > .wb-votes`);
    const fill = badge ? wbExportColour(getComputedStyle(badge).backgroundColor) : "#2f5bd3";
    const ink = badge ? wbExportColour(getComputedStyle(badge).color) : "#ffffff";
    const w = Math.max(16, 8 + String(obj.data.votes).length * 7);
    return `<rect x="${obj.width - w + 8}" y="-8" width="${w}" height="16" rx="8" fill="${fill}" />` +
      `<text x="${obj.width - w / 2 + 8}" y="0" font-size="11" font-weight="700" text-anchor="middle" dominant-baseline="central" fill="${ink}">${obj.data.votes}</text>`;
  }

  function wbPaintVotes(el, d) {
    wbMapLazy.paintStamps(el, d);
    const n = d.data?.votes || 0;
    let badge = el.querySelector(":scope > .wb-votes");
    if (!n) {
      badge?.remove();
      return;
    }
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "wb-votes";
      badge.setAttribute("role", "img");
      el.appendChild(badge);
    }
    badge.textContent = String(n);
    badge.setAttribute("aria-label", n === 1 ? "1 vote" : `${n} votes`);
  }

  function wbTimerLeft(end, now) {
    return Math.max(0, end - now);
  }

  function wbTimerText(ms) {
    const seconds = Math.ceil(Math.max(0, ms) / 1000);
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function wbTimerBar() {
    if (wbTimer.bar?.isConnected) return wbTimer.bar;
    const host = document.getElementById("wb-present-bar")?.parentElement;
    if (!host) return null;
    const bar = document.createElement("div");
    bar.id = "wb-timer-bar";
    bar.className = "whiteboard-floating-panel wb-timer-bar card glass hidden";
    bar.setAttribute("role", "timer");
    bar.setAttribute("aria-label", "Workshop timer");
    const glyph = document.createElement("i");
    glyph.className = "ph ph-timer";
    glyph.setAttribute("aria-hidden", "true");
    const time = document.createElement("span");
    time.className = "wb-timer-time";
    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "ghost small icon-only";
    stop.title = "Stop the timer";
    stop.setAttribute("aria-label", "Stop the timer");
    const x = document.createElement("i");
    x.className = "ph ph-x";
    x.setAttribute("aria-hidden", "true");
    stop.appendChild(x);
    stop.addEventListener("click", () => wbTimerStop());
    bar.append(glyph, time, stop);
    host.appendChild(bar);
    Object.assign(wbTimer, { bar, time });
    return bar;
  }

  function wbTimerStart(minutes) {
    wbTimerStop(true);
    const bar = wbTimerBar();
    if (!bar) return;
    wbTimer.end = Date.now() + minutes * 60000;
    bar.classList.remove("hidden", "wb-timer-done");
    wbTimerPaint();
    wbAnnounce(`Timer started: ${nounCount(minutes, "minute")}.`);
  }

  function wbTimerPaint() {
    const left = wbTimerLeft(wbTimer.end, Date.now());
    wbTimer.time.textContent = wbTimerText(left);
    //: Just under the board's top bar wherever it wraps to (measured: the
    //: bar's two rows at a phone's width), read once a second, never on a frame.
    const top = document.getElementById("wb-topbar")?.getBoundingClientRect().bottom;
    const box = wbTimer.bar.offsetParent?.getBoundingClientRect();
    if (top != null && box) wbTimer.bar.style.top = `${Math.round(top - box.top + 8)}px`;
    if (left > 0) {
      clearTimeout(wbTimer.tick);
      wbTimer.tick = setTimeout(wbTimerPaint, (left % 1000 || 1000) + 5);
      return;
    }
    wbTimer.tick = 0;
    wbTimer.bar.classList.add("wb-timer-done");
    toast("Time is up.");
    wbAnnounce("Time is up.");
  }

  function wbTimerStop(quiet) {
    clearTimeout(wbTimer.tick);
    wbTimer.tick = 0;
    wbTimer.bar?.classList.add("hidden");
    wbTimer.bar?.classList.remove("wb-timer-done");
    if (!quiet) wbAnnounce("Timer stopped.");
  }

  function wbOpenTimerMenu() {
    const items = [1, 3, 5, 10, 15, 30].map((m) => makeMenuItem(`ph:timer ${nounCount(m, "minute")}`, `Count down ${nounCount(m, "minute")} on the board`, () => wbTimerStart(m)));
    if (wbTimer.bar && !wbTimer.bar.classList.contains("hidden")) items.push(makeMenuItem("ph:x Stop the timer", "Take the timer off the board", () => wbTimerStop()));
    const at = wbInstances.container()?.getBoundingClientRect();
    openMenuAtPoint(items, "Workshop timer", at ? at.left + at.width / 2 - 80 : 120, at ? at.top + 64 : 120);
  }

  function wbShadowCss(look) {
    if (!look?.shadow) return null;
    const { x, y, blur } = wbShadowOf(look);
    return `drop-shadow(${x}px ${y}px ${blur}px rgb(0 0 0 / 0.28))`;
  }

  //: The same shadow as an SVG filter for the exported picture: defined once in
  //: `parts` under an id that names its numbers, and the attribute that uses it.
  //: A blur is a standard deviation of half its pixels, as in CSS.
  function wbExportShadow(parts, look) {
    const { x, y, blur } = wbShadowOf(look);
    const id = `wb-export-shadow-${x}_${y}_${blur}`;
    const def = `<defs><filter id="${id}" x="-30%" y="-30%" width="160%" height="160%">` +
      `<feDropShadow dx="${x}" dy="${y}" stdDeviation="${blur / 2}" flood-color="#000" flood-opacity="0.28"/></filter></defs>`;
    if (!parts.includes(def)) parts.push(def);
    return ` filter="url(#${id})"`;
  }

  //: SVG `stroke-dasharray` for each style, scaled to the actual stroke width
  //: so a thick dashed line doesn't look like a row of dots. `null` (solid)
  //: means "don't set the attribute at all", not "set it to empty".
  //: A custom `pattern` (draw.io's "8 4": dash, gap, dash... in line widths,
  //: `wbDashPatternOf`) wins over the named style.
  function wbDashArray(style, width, pattern = null) {
    if (pattern) return pattern.map((n) => Math.round(n * width * 100) / 100).join(" ");
    if (style === "dashed") return `${width * 3} ${width * 2}`;
    if (style === "dotted") return `${width} ${width * 1.6}`;
    return null;
  }

  //: **Flow** (draw.io's flowAnimation, `data.flow`): the dashes march along
  //: the line, one loop per dash pattern so it never jumps. A Web Animation on
  //: the path, not a stylesheet rule, because the loop's length is the
  //: element's own and the sheets declare no per-element token for it. Kept on
  //: the element and replaced only when the period changes, so a render does not
  //: restart it; held still under the OS hint and both of the app's switches.
  //: The export clones the attributes, so it draws the dashes still.
  function wbSetFlowAnimation(path, period) {
    if (!path) return;
    const root = document.documentElement;
    const still = reducedMotionWanted() || root.dataset.uiMotion === "off";
    const want = period > 0 && !still && typeof path.animate === "function" ? period : 0;
    if (path.__wbFlowPeriod === want) return;
    path.__wbFlowAnim?.cancel();
    path.__wbFlowAnim = null;
    path.__wbFlowPeriod = want;
    if (want) {
      path.__wbFlowAnim = path.animate(
        [{ strokeDashoffset: "0px" }, { strokeDashoffset: `${-want}px` }],
        { duration: 800, iterations: Infinity, easing: "linear" },
      );
    }
  }

  //: A typed dash pattern as numbers, or null when it is not one: one to six
  //: positive numbers of at most 200, split by spaces or commas.
  function wbDashPatternOf(text) {
    const parts = String(text ?? "").split(/[\s,]+/).filter(Boolean);
    if (!parts.length || parts.length > 6) return null;
    const numbers = parts.map(Number);
    return numbers.every((n) => Number.isFinite(n) && n > 0 && n <= 200) ? numbers : null;
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbApplyBackground, wbSetBackground, wbMigrateBackground, wbCursorUrl, wbHighlighterWidth, wbHighlighterBlend, wbCropClip, wbCropPath, wbPixel, wbVoteTargets, wbVoteSelection, wbClearVotes, wbSvgVotes, wbPaintVotes, wbOpenTimerMenu, wbShadowCss, wbExportShadow, wbDashArray, wbSetFlowAnimation, wbDashPatternOf });
})();
