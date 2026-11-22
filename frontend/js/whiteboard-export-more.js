(() => {
  // whiteboard-export-more.js: what a PNG can carry beyond its pixels (its resolution and, if asked, the board
  // itself), and the board as one self-contained .html file (WHITEBOARD_PLAN, wbformat2). Pure byte and string work:
  // nothing here touches the page, so tests run it in node. The export dialog (whiteboard.js) calls it through
  // `wbFmtState.exporters`, which is the only name this file adds to the shared scope.
  const SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10];
  const KEYWORD = "tessellate-board";
  //: The four resolutions the dialog offers; 96 is a screen, 72 the old Mac screen, 150 and 300 print.
  const DPIS = [72, 96, 150, 300];

  let crcTable = null;
  function crc32(bytes) {
    if (!crcTable) {
      crcTable = new Uint32Array(256);
      for (let n = 0; n < 256; n += 1) {
        let c = n;
        for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        crcTable[n] = c >>> 0;
      }
    }
    let crc = 0xffffffff;
    for (const byte of bytes) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }

  const ascii = (text) => Uint8Array.from(text, (ch) => ch.charCodeAt(0) & 0xff);

  //: A PNG chunk: length, type, data, and the CRC of type plus data.
  function chunk(type, data) {
    const out = new Uint8Array(12 + data.length);
    const view = new DataView(out.buffer);
    view.setUint32(0, data.length);
    out.set(ascii(type), 4);
    out.set(data, 8);
    view.setUint32(8 + data.length, crc32(out.subarray(4, 8 + data.length)));
    return out;
  }

  //: Pixels per metre, which is what a PNG stores a resolution as (unit byte 1).
  function physChunk(dpi) {
    const data = new Uint8Array(9);
    const ppm = Math.round(dpi / 0.0254);
    new DataView(data.buffer).setUint32(0, ppm);
    new DataView(data.buffer).setUint32(4, ppm);
    data[8] = 1;
    return chunk("pHYs", data);
  }

  //: JSON that is plain ASCII, which is what a tEXt chunk (Latin-1) can hold: every other character is a \u escape.
  const asciiJson = (value) => JSON.stringify(value).replace(/[\u007f-￿]/g, (ch) => `\\u${ch.charCodeAt(0).toString(16).padStart(4, "0")}`);

  function textChunk(keyword, text) {
    const data = new Uint8Array(keyword.length + 1 + text.length);
    data.set(ascii(keyword), 0);
    data.set(ascii(text), keyword.length + 1);
    return chunk("tEXt", data);
  }

  const isPng = (bytes) => SIGNATURE.every((b, i) => bytes[i] === b);

  //: The chunks of a PNG in order, as `{type, data}`.
  function chunksOf(bytes) {
    const found = [];
    if (!isPng(bytes)) return found;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let at = 8;
    while (at + 12 <= bytes.length) {
      const length = view.getUint32(at);
      const type = String.fromCharCode(...bytes.subarray(at + 4, at + 8));
      if (at + 12 + length > bytes.length) break;
      found.push({ type, data: bytes.subarray(at + 8, at + 8 + length) });
      at += 12 + length;
    }
    return found;
  }

  //: The PNG with its resolution written in (`dpi`) and, if `rows` is given, a copy of the board in a tEXt chunk. Both
  //: go straight after the header chunk. A file that is not a PNG comes back as it was.
  function pngWith(bytes, { dpi = 0, rows = null } = {}) {
    if (!isPng(bytes)) return bytes;
    const extra = [];
    if (DPIS.includes(dpi)) extra.push(physChunk(dpi));
    if (rows) extra.push(textChunk(KEYWORD, asciiJson({ app: "memorymap-board", v: 1, rows })));
    if (!extra.length) return bytes;
    const headerEnd = 8 + 12 + 13;
    const size = extra.reduce((n, part) => n + part.length, 0);
    const out = new Uint8Array(bytes.length + size);
    out.set(bytes.subarray(0, headerEnd), 0);
    let at = headerEnd;
    for (const part of extra) {
      out.set(part, at);
      at += part.length;
    }
    out.set(bytes.subarray(headerEnd), at);
    return out;
  }

  //: The resolution a PNG says it has, in dots per inch, or 0.
  function dpiOf(bytes) {
    const phys = chunksOf(bytes).find((c) => c.type === "pHYs");
    if (!phys || phys.data.length < 9 || phys.data[8] !== 1) return 0;
    return Math.round(new DataView(phys.data.buffer, phys.data.byteOffset).getUint32(0) * 0.0254);
  }

  //: The board rows a PNG carries, or null: the same `{app, rows}` an exported SVG holds in its metadata.
  function rowsOf(bytes) {
    try {
      const found = chunksOf(bytes).find((c) => c.type === "tEXt" && String.fromCharCode(...c.data.subarray(0, KEYWORD.length + 1)) === `${KEYWORD}\0`);
      if (!found) return null;
      const parsed = JSON.parse(String.fromCharCode(...found.data.subarray(KEYWORD.length + 1)));
      return parsed?.app === "memorymap-board" && Array.isArray(parsed.rows) ? parsed.rows : null;
    } catch {
      return null;
    }
  }

  const escapeHtml = (text) => String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  //: The viewer a .html export holds: wheel zooms about the pointer, a drag pans, a double click fits again. It moves
  //: the SVG's own viewBox, so there is no library, no network and no second copy of the picture.
  const VIEWER = `(() => {
  const svg = document.querySelector("svg");
  const home = svg.getAttribute("viewBox").split(/[\\s,]+/).map(Number);
  let [x, y, w, h] = home;
  const put = () => svg.setAttribute("viewBox", [x, y, w, h].join(" "));
  const at = (e) => {
    const r = svg.getBoundingClientRect();
    const k = Math.min(r.width / w, r.height / h);
    return { k, bx: x + (e.clientX - r.left - (r.width - w * k) / 2) / k, by: y + (e.clientY - r.top - (r.height - h * k) / 2) / k, r };
  };
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const p = at(e);
    const f = Math.min(4, Math.max(0.25, Math.exp(e.deltaY * 0.0015)));
    w *= f;
    h *= f;
    const k = Math.min(p.r.width / w, p.r.height / h);
    x = p.bx - (e.clientX - p.r.left - (p.r.width - w * k) / 2) / k;
    y = p.by - (e.clientY - p.r.top - (p.r.height - h * k) / 2) / k;
    put();
  }, { passive: false });
  let drag = null;
  svg.addEventListener("pointerdown", (e) => { drag = { sx: e.clientX, sy: e.clientY, x, y, k: at(e).k }; svg.setPointerCapture(e.pointerId); svg.classList.add("drag"); });
  svg.addEventListener("pointermove", (e) => {
    if (!drag) return;
    x = drag.x - (e.clientX - drag.sx) / drag.k;
    y = drag.y - (e.clientY - drag.sy) / drag.k;
    put();
  });
  const stop = () => { drag = null; svg.classList.remove("drag"); };
  svg.addEventListener("pointerup", stop);
  svg.addEventListener("pointercancel", stop);
  svg.addEventListener("dblclick", () => { [x, y, w, h] = home; put(); });
})();`;

  //: One .html file: the picture fills the window and can be panned and zoomed. The page carries no link, no font, no
  //: image address and no inline style attribute, and its one script and one style block are its own, so it opens offline
  //: and under a strict policy that allows inline blocks.
  function htmlPage(svg, title) {
    const fitted = svg.replace(/^(<svg\b[^>]*?) width="[^"]*" height="[^"]*"/, "$1");
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>
html, body { margin: 0; height: 100%; overflow: hidden; background: #f4f4f4; font-family: system-ui, sans-serif; }
svg { display: block; width: 100%; height: 100%; cursor: grab; touch-action: none; }
svg.drag { cursor: grabbing; }
.hint { position: fixed; left: 12px; bottom: 10px; margin: 0; font-size: 12px; color: #555; background: #ffffffcc; padding: 4px 8px; border-radius: 6px; pointer-events: none; }
</style>
</head>
<body>
${fitted}
<p class="hint">Scroll to zoom, drag to pan, double-click to fit.</p>
<script>
${VIEWER}
</script>
</body>
</html>
`;
  }

  wbFmtState.exporters = { pngWith, dpiOf, rowsOf, htmlPage, dpis: DPIS };
})();
