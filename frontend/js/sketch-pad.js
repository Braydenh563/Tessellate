// The sketch pad's wiring, loaded by the first `openSketch` (`lazyScript`,
// media.js; INBOX 839): its tool, size, paper, image, undo and ink handlers,
// the ink chip's palette and the Ctrl+Z keys. Nothing here can be pressed
// before the pad is open, and the pad's drawing code stays in media.js.

function sketchShowInk(color) {
  const dot = document.querySelector(".sketch-ink-dot");
  if (dot) dot.style.background = color;
}

$("sketch-clear").addEventListener("click", () => {
  // Clears strokes only: the background layer (§37G's uploaded image, or
  // blank white) is untouched, so Clear can't lose the photo being annotated.
  const canvas = $("sketch-canvas");
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
});
$("sketch-upload-image").addEventListener("click", () => $("sketch-image-input").click());
$("sketch-image-input").addEventListener("change", () => {
  const file = $("sketch-image-input").files[0];
  $("sketch-image-input").value = ""; // lets the same file be picked again
  sketchUploadImage(file);
});
$("sketch-size").addEventListener("input", () => {
  sketchPen.size = Number($("sketch-size").value);
  syncSketchSizeReadout();
});
// `input` previews live while dragging the swatch; `change` (fires once, on
// release) is what persists, dragging across ten hues shouldn't write ten
// times, same reasoning as the whiteboard's own background picker.
$("sketch-bg-color-picker").addEventListener("input", (e) => {
  sketchBgColor = e.target.value;
  sketchDrawBackground();
  sketchDirty = true; // a background colour is as much a change as a stroke
});
$("sketch-bg-color-picker").addEventListener("change", (e) => {
  prefs.set(SKETCH_BG_KEY, e.target.value);
});
for (const button of document.querySelectorAll(".sketch-color")) {
  button.addEventListener("click", () => {
    sketchPen.color = button.dataset.color;
    // Picking a colour means you want to draw, not erase. The eraser button
    // was renamed `sketch-tool-eraser` when the toolbar became icons, and this
    // one call kept the old `sketch-eraser` id: so the optional-chain
    // swallowed it and the eraser stayed lit while the pen drew, which reads
    // as the colour swatches not working.
    //
    // **It does not mean you want the pen**, which is what this did until it
    // was measured: "highlighter, then yellow" left `sketchTool` at "pen" and
    // drew an opaque yellow line (one pass at 176.0 luminance on a 255.0
    // paper, which is the ink's own value, so no translucency at all). The
    // highlighter, the shapes and the text tool all take the ink too, so only
    // the eraser is switched away from here.
    const wasErasing = sketchPen.eraser;
    sketchPen.eraser = false;
    if (wasErasing) {
      sketchTool = "pen";
      $("sketch-tool-eraser")?.classList.remove("active");
      $("sketch-tool-pen")?.classList.add("active");
    }
    document
      .querySelectorAll(".sketch-color")
      .forEach((b) => b.classList.toggle("active", b === button));
    sketchShowInk(button.dataset.color);
    sketchTogglePalette(false);
    $("sketch-ink-chip")?.focus();
  });
}
$("sketch-ink-chip")?.addEventListener("click", () => sketchTogglePalette());
const sketchCanvas = $("sketch-canvas");
sketchCanvas.addEventListener("pointerdown", sketchStart);
sketchCanvas.addEventListener("pointermove", sketchMove);
sketchCanvas.addEventListener("pointerup", sketchEnd);
sketchCanvas.addEventListener("pointerleave", sketchEnd);

$("sketch-undo").addEventListener("click", () => {
  if (sketchHistory.length === 0) return;
  const canvas = $("sketch-canvas");
  const ctx = canvas.getContext("2d");
  sketchRedoStack.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
  const last = sketchHistory.pop();
  ctx.putImageData(last, 0, 0);
  sketchDirty = true;
});
$("sketch-redo").addEventListener("click", () => {
  if (sketchRedoStack.length === 0) return;
  const canvas = $("sketch-canvas");
  const ctx = canvas.getContext("2d");
  sketchHistory.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
  const next = sketchRedoStack.pop();
  ctx.putImageData(next, 0, 0);
  sketchDirty = true;
});

const sketchToolsList = ["pen", "highlighter", "eraser", "line", "rect", "circ", "arrow", "text"];
for (const tool of sketchToolsList) {
  const btn = $(`sketch-tool-${tool}`);
  if (btn) {
    btn.addEventListener("click", () => {
      sketchTool = tool === "eraser" ? "pen" : tool;
      sketchPen.eraser = (tool === "eraser");
      for (const t of sketchToolsList) {
        const tBtn = $(`sketch-tool-${t}`);
        if (tBtn) tBtn.classList.toggle("active", t === tool);
      }
    });
  }
}

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && !$("sketch-overlay").classList.contains("hidden")) {
    if (e.key === "z") {
      if (e.shiftKey) $("sketch-redo").click();
      else $("sketch-undo").click();
      e.preventDefault();
    } else if (e.key === "y") {
      $("sketch-redo").click();
      e.preventDefault();
    }
  }
});

function sketchTogglePalette(open) {
  const palette = $("sketch-palette");
  const chip = $("sketch-ink-chip");
  if (!palette || !chip) return;
  const willOpen = open === undefined ? palette.classList.contains("hidden") : open;
  palette.classList.toggle("hidden", !willOpen);
  chip.setAttribute("aria-expanded", String(willOpen));
  if (willOpen) palette.querySelector(".sketch-color.active, .sketch-color")?.focus();
}

// Closes on a press elsewhere, and on Escape without closing the dialog.
document.addEventListener("click", (event) => {
  if (!event.target.closest?.(".sketch-ink")) sketchTogglePalette(false);
});
document.addEventListener(
  "keydown",
  (event) => {
    const palette = $("sketch-palette");
    if (event.key !== "Escape" || !palette || palette.classList.contains("hidden")) return;
    event.stopPropagation();
    sketchTogglePalette(false);
    $("sketch-ink-chip").focus();
  },
  true
);

function sketchStart(event) {
  //: A pen or a drag on the canvas is ink, never a text selection (INBOX 1303).
  event.preventDefault();
  sketchDrawing = true;
  sketchDirty = true;
  sketchMoved = false;
  const { x, y } = sketchPointer(event);
  sketchStartX = x;
  sketchStartY = y;
  
  if (sketchTool === "text") {
    const text = prompt("Enter text:");
    if (text) {
      sketchSaveSnapshot();
      const context = sketchContext();
      context.font = `${sketchPen.size * 6}px sans-serif`;
      context.fillStyle = sketchPen.color;
      context.fillText(text, x, y);
    }
    sketchDrawing = false;
    return;
  }

  sketchSaveSnapshot();
  const context = sketchContext();
  // The highlighter keeps its own polyline (see `sketchPaintHighlighter`):
  // the points are this stroke's, so they are cleared at the start of every
  // stroke rather than when the tool changes.
  sketchStrokePoints = sketchTool === "highlighter" ? [{ x, y }] : [];
  if (sketchTool === "pen") {
    context.beginPath();
    context.moveTo(x, y);
  }
  event.target.setPointerCapture(event.pointerId);
}

function sketchMove(event) {
  if (!sketchDrawing) return;
  const { x, y } = sketchPointer(event);
  const context = sketchContext();
  if (x === sketchStartX && y === sketchStartY) return;
  sketchMoved = true;
  
  //: The highlighter is painted whole, from the snapshot up, every frame:
  //: see `sketchPaintHighlighter` for why it cannot be drawn a segment at a
  //: time. Everything below this is the per-segment path the pen and the
  //: shapes use.
  if (sketchTool === "highlighter") {
    sketchStrokePoints.push({ x, y });
    sketchPaintHighlighter(context);
    return;
  }

  if (sketchTool !== "pen") {
    const last = sketchHistory[sketchHistory.length - 1];
    if (last) context.putImageData(last, 0, 0);
    else context.clearRect(0, 0, context.canvas.width, context.canvas.height);
  }

  sketchApplyBrush(context);

  if (sketchTool === "pen") {
    context.lineTo(x, y);
    context.stroke();
    //: A fresh single-segment path per move, so a hundred-point stroke does
    //: not re-composite its first segment a hundred times. Harmless at the
    //: pen's full opacity and load-bearing for anything translucent, which
    //: is why the highlighter was here once and is not any more: one segment
    //: drawn once is still not one *stroke* drawn once, and the overlap at
    //: each joint is what `sketchPaintHighlighter` exists to remove.
    context.beginPath();
    context.moveTo(x, y);
  } else if (sketchTool === "line") {
    context.beginPath();
    context.moveTo(sketchStartX, sketchStartY);
    context.lineTo(x, y);
    context.stroke();
  } else if (sketchTool === "rect") {
    // Shift locks proportions: a square instead of whatever rectangle the
    // pointer happens to trace, the same convention every other drawing
    // tool uses, asked for directly. `circ` needs no equivalent: it has
    // always drawn from a single radius (`context.arc`), never width/height
    // independently, so it was already a perfect circle with no ellipse
    // mode to lock out of.
    let w = x - sketchStartX;
    let h = y - sketchStartY;
    if (event.shiftKey) {
      const side = Math.max(Math.abs(w), Math.abs(h));
      w = Math.sign(w || 1) * side;
      h = Math.sign(h || 1) * side;
    }
    context.beginPath();
    context.rect(sketchStartX, sketchStartY, w, h);
    context.stroke();
  } else if (sketchTool === "circ") {
    context.beginPath();
    const r = Math.sqrt(Math.pow(x - sketchStartX, 2) + Math.pow(y - sketchStartY, 2));
    context.arc(sketchStartX, sketchStartY, r, 0, 2 * Math.PI);
    context.stroke();
  } else if (sketchTool === "arrow") {
    context.beginPath();
    context.moveTo(sketchStartX, sketchStartY);
    context.lineTo(x, y);
    context.stroke();
    const angle = Math.atan2(y - sketchStartY, x - sketchStartX);
    const headLen = sketchPen.size * 3 + 5;
    context.beginPath();
    context.moveTo(x, y);
    context.lineTo(x - headLen * Math.cos(angle - Math.PI / 6), y - headLen * Math.sin(angle - Math.PI / 6));
    context.moveTo(x, y);
    context.lineTo(x - headLen * Math.cos(angle + Math.PI / 6), y - headLen * Math.sin(angle + Math.PI / 6));
    context.stroke();
  }
}
