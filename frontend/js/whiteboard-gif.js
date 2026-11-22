(() => {
  // whiteboard-gif.js: a small animated-GIF writer (the GIF export of the ink replay, L-whiteboard-4). Written from the
  // GIF89a spec, offline and with no library: a fixed 256-colour palette (a 6x6x6 colour cube plus 40 greys, so a pen
  // drawing's anti-aliased greys stay grey), no dithering, the standard variable-width LZW. Pure; node-tested in
  // tests/test_wb_gif.py.
  const GREYS = 40;
  const ascii = (s) => [...s].map((c) => c.charCodeAt(0));

  //: The palette as a flat [r, g, b, ...] of 256 entries.
  function palette() {
    const out = [];
    for (let r = 0; r < 6; r++) for (let g = 0; g < 6; g++) for (let b = 0; b < 6; b++) out.push(r * 51, g * 51, b * 51);
    for (let i = 0; i < GREYS; i++) { const v = Math.round((i * 255) / (GREYS - 1)); out.push(v, v, v); }
    return out;
  }

  //: The palette index for one colour: a near-grey takes the grey ramp, anything else the nearest cube cell.
  function indexOf(r, g, b) {
    if (Math.abs(r - g) < 10 && Math.abs(g - b) < 10) return 216 + Math.round(((r + g + b) / 3 / 255) * (GREYS - 1));
    return 36 * Math.round(r / 51) + 6 * Math.round(g / 51) + Math.round(b / 51);
  }

  //: RGBA pixels as palette indexes (a transparent pixel is read as white, the ground of an export).
  function quantise(rgba) {
    const out = new Uint8Array(rgba.length / 4);
    for (let i = 0, j = 0; i < rgba.length; i += 4, j++) {
      const a = rgba[i + 3] / 255, back = 255 * (1 - a);
      out[j] = indexOf(Math.round(rgba[i] * a + back), Math.round(rgba[i + 1] * a + back), Math.round(rgba[i + 2] * a + back));
    }
    return out;
  }

  //: GIF's LZW over 8-bit indexes: clear 256, end 257, codes grow from 9 to 12 bits, the table is cleared when full.
  function lzw(indexes) {
    const bytes = [];
    let acc = 0, bits = 0, size = 9, next = 258;
    const put = (code) => {
      acc |= code << bits; bits += size;
      while (bits >= 8) { bytes.push(acc & 255); acc >>>= 8; bits -= 8; }
    };
    let table = new Map();
    put(256);
    let prefix = indexes[0];
    for (let i = 1; i < indexes.length; i++) {
      const k = indexes[i], key = prefix * 256 + k;
      if (table.has(key)) { prefix = table.get(key); continue; }
      put(prefix);
      if (next < 4096) {
        table.set(key, next++);
        if (next - 1 === 1 << size && size < 12) size++;
      } else { put(256); table = new Map(); next = 258; size = 9; }
      prefix = k;
    }
    put(prefix);
    put(257);
    if (bits) bytes.push(acc & 255);
    return bytes;
  }

  //: `frames`: RGBA arrays of width * height * 4. `delay` is the time on each frame in 1/100 s; the last frame waits
  //: `hold`. Returns the file's bytes. It loops forever.
  function encode({ width, height, frames, delay = 12, hold = 150 }) {
    const out = [];
    const u16 = (n) => out.push(n & 255, (n >> 8) & 255);
    out.push(...ascii("GIF89a"));
    u16(width); u16(height);
    out.push(0xf7, 0, 0, ...palette());
    out.push(0x21, 0xff, 11, ...ascii("NETSCAPE2.0"), 3, 1, 0, 0, 0);
    frames.forEach((rgba, n) => {
      out.push(0x21, 0xf9, 4, 4);
      u16(n === frames.length - 1 ? hold : delay);
      out.push(0, 0);
      out.push(0x2c); u16(0); u16(0); u16(width); u16(height); out.push(0);
      out.push(8);
      const data = lzw(quantise(rgba));
      for (let i = 0; i < data.length; i += 255) { const part = data.slice(i, i + 255); out.push(part.length, ...part); }
      out.push(0);
    });
    out.push(0x3b);
    return Uint8Array.from(out);
  }

  Object.assign((wbFmtState.gif ||= {}), { encode, palette, indexOf, quantise, lzw });
})();
