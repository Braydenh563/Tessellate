(() => {
  // whiteboard-ink-replay.js: play a board's pen strokes back in the order they were drawn, and write that as a GIF
  // (L-whiteboard-4). A stroke is saved whole, without timing, so the order is the order they were saved in (a sketch's id only
  // grows) and each stroke appears at once; reduced motion skips straight to the finished board.
  const FRAME_CAP = 40;
  let timer = null, hidden = [];

  //: Pure: the pen and marker strokes among `sketches`, oldest first. `parse` reads a sketch's data (wbSketchParsedData).
  function order(sketches, parse) {
    return (sketches || [])
      .filter((s) => { const p = parse(s); return p && (p.shape === "draw" || p.shape === "highlighter"); })
      .sort((a, b) => a.id - b.id);
  }

  //: Pure: how many strokes each frame shows, at most `cap` frames: always one more than the last, ending on all of them.
  function plan(count, cap = FRAME_CAP) {
    if (count < 1) return [];
    const frames = Math.min(count, cap), out = [];
    for (let i = 1; i <= frames; i++) out.push(Math.round((count * i) / frames));
    return out;
  }

  const strokes = () => order(wbState.sketches, wbSketchParsedData);

  //: Put every hidden stroke back and stop.
  function stop() {
    if (timer) clearTimeout(timer);
    timer = null;
    for (const el of hidden) el.style.visibility = "";
    hidden = [];
  }

  //: **Replay ink** (the Edit menu and the palette): the strokes vanish, then come back one by one, about three seconds in all.
  //: Running it again, or leaving the board, ends it with everything shown.
  function start() {
    stop();
    const list = strokes();
    if (!list.length) { toast("There is no pen drawing on this board to replay."); return false; }
    if (reducedMotionWanted()) { toast("Replay skipped to the end: reduced motion is on."); return true; }
    hidden = list.map((s) => document.querySelector(`.sketch-group[data-id="${s.id}"]`)).filter(Boolean);
    for (const el of hidden) el.style.visibility = "hidden";
    const gap = Math.max(60, Math.min(400, 3000 / list.length));
    let shown = 0;
    const tick = () => {
      if (shown < hidden.length) hidden[shown++].style.visibility = "";
      if (shown < hidden.length) timer = setTimeout(tick, gap);
      else stop();
    };
    timer = setTimeout(tick, 250);
    return true;
  }

  //: Decode a PNG blob to RGBA pixels.
  async function pixels(blob, width, height) {
    const bitmap = await createImageBitmap(blob);
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(bitmap, 0, 0, width, height);
    return ctx.getImageData(0, 0, width, height).data;
  }

  //: **GIF export**: the board drawn again for each step of `plan`, with the strokes not yet drawn left out, as one looping GIF.
  async function exportGif(scope) {
    const list = strokes();
    if (!list.length) { toast("There is no pen drawing on this board to make a GIF of."); return false; }
    const frames = [];
    let size = null;
    for (const count of plan(list.length)) {
      const skip = new Set(list.slice(count).map((s) => s.id));
      const { svg, width, height } = wbBuildExportSvg(scope, { skipSketches: skip });
      //: At most about 900 px on the long side, so a frame stays small; the first frame fixes the size of all.
      const scale = 1 / Math.max(1, Math.ceil(Math.max(width, height) / 900));
      size ||= { w: Math.max(1, Math.round(width * scale)), h: Math.max(1, Math.round(height * scale)) };
      frames.push(await pixels(await wbRasterizeSvg(svg, size.w, size.h, "image/png"), size.w, size.h));
    }
    const bytes = wbFmtState.gif.encode({ width: size.w, height: size.h, frames });
    await saveFile(wbExportFileName(scope, "gif"), new Blob([bytes], { type: "image/gif" }));
    toast(`Board exported as a GIF of ${frames.length} frames.`);
    return true;
  }

  Object.assign((wbFmtState.inkReplay ||= {}), { order, plan, start, stop, exportGif, strokes });
})();
