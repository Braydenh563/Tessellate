// The generative background (Settings, Appearance, Background art): what
// each style draws, and the runtime that mounts, pauses, stills and removes
// it. settings.js decides *whether* and *how* (the setting, the motion and
// performance rules, the intensity, the accent) and calls `bgArtRun` and
// `bgArtHalt` here. This file is fetched by settings.js, whose
// own tail starts the art; nothing here runs at parse time except
// definitions and three window listeners. It is a lazy bundle (`bgArt`):
// settings.js fetches it when the art is on or the Appearance grid draws.
//
// **Three kinds of style, cheapest first.**
//
// 1. CSS styles (`dom: true`; none at present). The mesh and the bubbles
//    were CSS animations: no page work, but the compositor redrew their
//    large layers at the display's full rate, and the whole browser spent
//    about a core on them (bgartcost.js's browser CPU), more than any
//    canvas style, so both became canvas styles. The runtime keeps the path.
// 2. Canvas styles (every style now): they draw on a plain canvas with
//    a loop of their own (no p5; see the runtime below). Their per-frame
//    rules: particles live in typed arrays, not an object each; nothing is
//    allocated per frame (colour strings, gradients, sprites and grids are
//    built once in `init`, and a mark's fade is `globalAlpha`, not a new
//    colour string); neighbour searches go through a counting-sort grid, not
//    every pair; anything repeated is a pre-rendered sprite; anything soft
//    is drawn at a reduced pixel density and scaled up by the compositor,
//    never by `drawImage` (a scaled full-window `drawImage` costs 5ms a
//    frame in software, 34ms at "high" smoothing, measured at 1440x900);
//    the pixel density is never above 1; and the loop draws 30 frames a
//    second, 20 on a small machine or on battery.
// 3. Still (Reduce motion, Movement "Still", Performance or Battery mode):
//    a canvas style renders one frame off the page, the frame is captured
//    to an image (`toBlob` to an object URL), and the image becomes the CSS
//    background of one fixed element. No loop runs and no canvas is left in
//    the page. A CSS style is simply mounted without its animations. The
//    capture is redone only when something that changes the picture changes
//    (theme, accent, style, intensity, a resize, debounced).
//
// A moving style also stops when the window is hidden, when it has been
// unfocused for thirty seconds, when nothing has been touched for two
// minutes, and when something opaque covers the whole window (checked
// every two seconds by `bgArtCovered`).
//
// Measured by `scratchpad/ui-sweeps/bgartcost.js`: paint time per frame
// (the draw plus the raster it causes), allocations over ten seconds, and
// requestAnimationFrame callbacks in still mode.
//
// Colour comes from the accent (`ctx.baseHue`) and a few hue offsets from
// it, never a fixed palette, so a palette or accent change repaints the art
// in the new colour. Dark mode adds light ("lighter" compositing, luminous
// marks); light mode lays down ink (mid lightness, more saturation), since
// the art sits at `--bg-art-opacity` over a near-white page.

// --- shared helpers -------------------------------------------------------------

// **The dark theme's luminance cap.** Text that sits straight on the page
// (the Dashboard's section labels, a search hint) is muted grey at about
// 5:1 against the dark page with the art off, so there is very little room:
// a bright mark behind it takes it under AA. Measured with
// `scratchpad/ui-sweeps/bgartcontrast.js`, the first bright aurora and the
// constellation both did, where the old styles had not. So while a style
// builds its colours in the dark theme (its `init` or `mount`, never per
// frame), every colour is scaled down to at most the relative luminance the
// style names as `darkCap`: the hue and saturation stay, the light is
// lowered to what the text can bear. `bgLumCap` is 0 the rest of the time.
//
// The light theme is the same problem the other way up: dark muted text on
// a pale page loses contrast to anything darker behind it, so a style can
// name a `lightFloor`, and its colours are mixed toward white until their
// luminance reaches it (`bgLumFloor`).
let bgLumCap = 0;
let bgLumFloor = 0;

// `bgLuma` is settings.js's (boot code needs it for the accent contrast).

function bgCapRgb(rgb) {
  if (bgLumCap) {
    const y = bgLuma(rgb);
    if (y > bgLumCap) {
      const k = (bgLumCap / y) ** (1 / 2.2);
      return [rgb[0] * k, rgb[1] * k, rgb[2] * k];
    }
  }
  if (bgLumFloor && bgLuma(rgb) < bgLumFloor) {
    // Toward white by the least that reaches the floor (a few halvings; a
    // colour is built once per style, never per frame).
    let lo = 0, hi = 1;
    for (let i = 0; i < 12; i++) {
      const m = (lo + hi) / 2;
      const mixed = [rgb[0] + (255 - rgb[0]) * m, rgb[1] + (255 - rgb[1]) * m, rgb[2] + (255 - rgb[2]) * m];
      if (bgLuma(mixed) < bgLumFloor) lo = m;
      else hi = m;
    }
    return [rgb[0] + (255 - rgb[0]) * hi, rgb[1] + (255 - rgb[1]) * hi, rgb[2] + (255 - rgb[2]) * hi];
  }
  return rgb;
}

function bgHsla(h, s, l, a) {
  const hue = ((h % 360) + 360) % 360;
  const al = Math.max(0, Math.min(1, a)).toFixed(3);
  if (bgLumCap || bgLumFloor) {
    const [r, g, b] = bgHslToRgb(hue, s, l);
    return `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},${al})`;
  }
  return `hsla(${hue.toFixed(1)},${s}%,${l}%,${al})`;
}

// The styles' noise: smooth along one axis, changing with time, as two
// layers of a table sliding past each other (so a second axis can ride on
// the time argument where a field is wanted). It replaced p5's Perlin noise,
// four octaves in a loop, which V8 would not inline: called with fractional
// arguments it boxed every one of them, and the aurora alone, at about
// 2,500 values a frame, made 22MB of garbage every ten seconds (measured).
// This is small enough to inline where it is called, and allocates nothing.
const BG_FLOW = new Float32Array(1024);
for (let i = 0; i < 1024; i++) BG_FLOW[i] = Math.random();

function bgFlow(x, t) {
  const u = x + t, v = x * 1.13 - t * 0.71 + 311;
  let i = Math.floor(u), f = u - i;
  f = f * f * (3 - 2 * f);
  const a = BG_FLOW[i & 1023] + (BG_FLOW[(i + 1) & 1023] - BG_FLOW[i & 1023]) * f;
  i = Math.floor(v);
  f = v - i;
  f = f * f * (3 - 2 * f);
  const b = BG_FLOW[i & 1023] + (BG_FLOW[(i + 1) & 1023] - BG_FLOW[i & 1023]) * f;
  return (a + b) * 0.5;
}

// Drift's noise (INBOX 1436, from the owner's wallpaper renderer): value noise
// on a hashed lattice with a smoothstep blend, three octaves. `bgHash2` is an
// integer hash of a lattice point and a seed, 0..1.
function bgHash2(ix, iy, seed) {
  let h = (Math.imul(ix, 374761393) + Math.imul(iy, 668265263) + Math.imul(seed, 1274126177)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

// The lattice itself: 256 by 256 hashed values, built once per style so the
// per-pixel loop reads a table instead of hashing (a hash per corner per
// octave per pixel is where the first version spent its time and its garbage).
function bgLattice(seed) {
  const t = new Float32Array(65536);
  for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) t[y * 256 + x] = bgHash2(x, y, seed);
  return t;
}

// One row of Drift's field: `n` samples of three-octave value noise (smoothstep
// blend, each octave half the weight and twice the frequency) from `x0` in
// steps of `dx` along the row at height `y`, as bytes in `out`. Everything is
// in this one function on purpose: called per pixel with fractional
// arguments, the three helpers it replaced boxed every one of them (58MB of
// garbage in ten seconds, measured), and V8 would not inline them.
function bgFbmRow(lat, out, n, x0, dx, y) {
  for (let i = 0; i < n; i++) {
    let sum = 0, amp = 1, f = 1;
    for (let o = 0; o < 3; o++) {
      const u = (x0 + i * dx) * f, v = y * f;
      const ix = Math.floor(u), iy = Math.floor(v);
      let fx = u - ix, fy = v - iy;
      fx = fx * fx * (3 - 2 * fx);
      fy = fy * fy * (3 - 2 * fy);
      const r0 = (iy & 255) << 8, r1 = ((iy + 1) & 255) << 8, c0 = ix & 255, c1 = (ix + 1) & 255;
      const a = lat[r0 + c0], b = lat[r0 + c1], c = lat[r1 + c0], d = lat[r1 + c1];
      sum += amp * (a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy);
      amp *= 0.5; f *= 2;
    }
    out[i] = (sum / 1.75 * 255) | 0;
  }
}

// Wander's edge rule: a step heading out of [lo, hi] turns round; one
// already heading in is left alone.
function bgTurnBack(p, v, lo, hi) {
  return (p < lo && v < 0) || (p > hi && v > 0) ? -v : v;
}

// p5's `random`: nothing, one bound, or two.
function bgRand(a, b) {
  const r = Math.random();
  if (a === undefined) return r;
  if (b === undefined) return r * a;
  return a + r * (b - a);
}

// The exact string p5's `color(h, s, l, a).toString()` gives in
// `colorMode(HSL, 360, 100, 100, 1)` (its `hslaToRGBA`, levels rounded to
// 0..255), so the waves, drawn without p5 now, set the same fill as before.
function bgP5Rgba(h, s, l, a) {
  const S = s / 100, L = l / 100;
  let r = L, g = L, b = L;
  if (S !== 0) {
    const r6 = 6 * (h / 360);
    const q = L < 0.5 ? (1 + S) * L : L + S - L * S;
    const p0 = 2 * L - q;
    const f = (e) => {
      let u = e;
      if (u < 0) u += 6;
      else if (u >= 6) u -= 6;
      return u < 1 ? p0 + (q - p0) * u : u < 3 ? q : u < 4 ? p0 + (q - p0) * (4 - u) : p0;
    };
    r = f(2 + r6); g = f(r6); b = f(r6 - 2);
  }
  return `rgba(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)},${a})`;
}

// HSL (degrees, percent, percent) to RGB in 0..255, for the styles that
// write pixels themselves.
function bgHslToRgb(h, s, l) {
  const hue = (((h % 360) + 360) % 360) / 360;
  const sat = s / 100, lig = l / 100;
  if (!sat) return bgCapRgb([lig * 255, lig * 255, lig * 255]);
  const q = lig < 0.5 ? lig * (1 + sat) : lig + sat - lig * sat;
  const pp = 2 * lig - q;
  const ch = (t) => {
    let u = t;
    if (u < 0) u += 1;
    if (u > 1) u -= 1;
    if (u < 1 / 6) return pp + (q - pp) * 6 * u;
    if (u < 1 / 2) return q;
    if (u < 2 / 3) return pp + (q - pp) * (2 / 3 - u) * 6;
    return pp;
  };
  return bgCapRgb([ch(hue + 1 / 3) * 255, ch(hue) * 255, ch(hue - 1 / 3) * 255]);
}

// The hue of a CSS colour, the same number p5's `hue()` gave for it (the
// CSS styles need it without loading p5 at all). Reads #rgb, #rrggbb and
// rgb()/rgba(); anything else falls back to the default indigo's hue.
function bgColourHue(colour) {
  const c = String(colour || "").trim();
  let r, g, b;
  let m = /^#([0-9a-f]{3})$/i.exec(c);
  if (m) {
    [r, g, b] = m[1].split("").map((d) => parseInt(d + d, 16));
  } else if ((m = /^#([0-9a-f]{6})/i.exec(c))) {
    r = parseInt(m[1].slice(0, 2), 16);
    g = parseInt(m[1].slice(2, 4), 16);
    b = parseInt(m[1].slice(4, 6), 16);
  } else if ((m = /rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)/i.exec(c))) {
    r = Number(m[1]); g = Number(m[2]); b = Number(m[3]);
  } else {
    return 230;
  }
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const d = max - min;
  if (!d) return 0;
  let h;
  if (max === r) h = ((g - b) / d) % 6;
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return (h * 60 + 360) % 360;
}

// A small offscreen canvas, painted once.
function bgSprite(w, h, paint) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  // Under the cost sweep's CPU-canvas hook (see bgArtSurface) the sprites
  // are CPU-backed as well, as they would be on a machine with no GPU
  // canvas: a GPU sprite drawn into a CPU canvas is a readback per draw,
  // which no real frame pays and which would swamp the measurement.
  paint(c.getContext("2d", window.__bgArtCpu === true ? { willReadFrequently: true } : undefined), c.width, c.height);
  return c;
}

// A soft round glow: a star's halo, an organism's aura, a soft dot.
function bgGlowSprite(hue, sat, light, alpha, size = 64, core = 0.35) {
  return bgSprite(size, size, (g, w) => {
    const r = w / 2;
    const grad = g.createRadialGradient(r, r, 0, r, r, r);
    grad.addColorStop(0, bgHsla(hue, sat, light, alpha));
    grad.addColorStop(core, bgHsla(hue, sat, light, alpha * 0.45));
    grad.addColorStop(1, bgHsla(hue, sat, light, 0));
    g.fillStyle = grad;
    g.fillRect(0, 0, w, w);
  });
}

function bgClamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

// A seeded 0..1 generator for the CSS styles, which have no p5 to ask.
function bgRandom(seed) {
  let s = (seed >>> 0) || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

// A counting-sort grid over points held in typed arrays, rebuilt each frame
// into the same buffers: `start[c]..start[c + 1]` indexes `items` for cell
// `c`. Replaces a Map of arrays rebuilt every frame, which was most of what
// the neighbour searches allocated.
function bgGrid(W, H, cell, cap) {
  const cols = Math.ceil((W + 80) / cell) + 1;
  const rows = Math.ceil((H + 80) / cell) + 1;
  const start = new Int32Array(cols * rows + 1);
  const fill = new Int32Array(cols * rows);
  const items = new Int32Array(cap);
  const cellOf = new Int32Array(cap);
  return {
    cols, rows, start, items,
    cellAt(x, y) {
      const cx = bgClamp(Math.floor((x + 40) / cell), 0, cols - 1);
      const cy = bgClamp(Math.floor((y + 40) / cell), 0, rows - 1);
      return cy * cols + cx;
    },
    // Index points `from..to` of `xs`/`ys` into the grid.
    build(xs, ys, from, to) {
      start.fill(0);
      for (let i = from; i < to; i++) {
        const c = this.cellAt(xs[i], ys[i]);
        cellOf[i] = c;
        start[c + 1]++;
      }
      for (let c = 0; c < cols * rows; c++) start[c + 1] += start[c];
      fill.set(start.subarray(0, cols * rows));
      for (let i = from; i < to; i++) items[fill[cellOf[i]]++] = i;
    },
  };
}

// --- genomes: species traits from the letters of a name ----------------------------
//
// Adapted from helixlabs (Braydenh563, MIT licence; `generateDNAProfile` in
// its sketch.js). A string's character codes, each weighted by its position,
// sum to one number, and every trait is that number through a different
// multiplier and modulus, so the same string always grows the same species
// and moving one letter changes all of them. helixlabs builds a species
// from a DNA string a person types; here the string is the person's display
// name (or "Tessellate" when they have not set one), so each person's
// background is an ecosystem of its own.
function bgArtGenome(text) {
  let sum = 0;
  for (let i = 0; i < text.length; i++) sum += text.charCodeAt(i) * (i + 1);
  // One change from helixlabs: each residue is taken from the sum after an
  // integer mix, not from the sum itself. Plain `(sum * 17) % 3` and
  // `(sum * 13 + 53) % 3` both depend only on `sum % 3`, so the glow fixed
  // the wake and a third of all species came out with the same pair; mixed,
  // each trait is its own draw from the same letters.
  const mix = (mul, add) => {
    let h = (Math.imul(sum, mul) + add) | 0;
    h = Math.imul(h ^ (h >>> 16), 0x85ebca6b);
    h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
    return (h ^ (h >>> 16)) >>> 0;
  };
  return {
    sum,
    pick: (list, mul, add = 0) => list[mix(mul, add) % list.length],
    // `lo..hi` from a residue: the same shape as helixlabs'
    // `map((sumCode * 19) % 101, 0, 100, lo, hi)`.
    span: (mul, mod, lo, hi) => lo + ((mix(mul, 0) % mod) / (mod - 1)) * (hi - lo),
    int: (mul, mod, lo) => (mix(mul, 0) % mod) + lo,
  };
}

function bgArtSeedOf(text) {
  const t = text ? String(text).trim() : "";
  return t || "Tessellate";
}

// The strains one name grows. Each is a rotation of the name plus a letter
// for its place, so the rotation changes which character carries which
// weight and every strain's sum differs, even for a name of one repeated
// letter.
function bgArtStrains(text, count) {
  const src = bgArtSeedOf(text);
  const out = [];
  for (let i = 0; i < count; i++) {
    const r = (i * 3) % src.length;
    out.push(src.slice(r) + src.slice(0, r) + String.fromCharCode(65 + i));
  }
  return out;
}

// helixlabs names each species from its sum (`generateSpeciesName`); these
// are this app's own syllables, in the same spirit.
const BG_GENUS_HEAD = ["Lu", "Ve", "Or", "Ta", "Mi", "Sy", "Ca", "Ne", "Pho", "Zo", "Ar", "Hel"];
const BG_GENUS_TAIL = ["mora", "sica", "bella", "nula", "phora", "cilla", "dora", "thea"];
const BG_EPITHET = ["serena", "lucida", "vagans", "gemina", "ornata", "placida", "volans", "minuta", "aurea", "nexa"];

function bgArtSpeciesName(strain) {
  const gene = bgArtGenome(strain);
  return `${gene.pick(BG_GENUS_HEAD, 3, 1)}${gene.pick(BG_GENUS_TAIL, 11, 5)} ${gene.pick(BG_EPITHET, 17, 3)}`;
}

// How many strains a name grows (three to five), read from the whole name.
function bgArtStrainCount(text) {
  return 3 + (bgArtGenome(bgArtSeedOf(text)).sum % 3);
}

// The text every seeded style grows from: the display name from
// Preferences, or the app's name before one is set.
function bgArtSeedText() {
  const name = typeof prefsCache !== "undefined" && prefsCache && prefsCache.display_name;
  return bgArtSeedOf(name);
}

// --- the styles -----------------------------------------------------------------
//
// A canvas style is a factory `(p, ctx) => { init, frame(t), background,
// pixelDensity?, settle?, seeded? }`. `background` says what a frame starts
// from: "wash" paints a translucent rect over the last frame so marks leave
// trails (the waves), "clear" wipes it, "keep" leaves it (the mycelium
// accumulates). `settle` runs a simulation forward before a still frame.
//
// A CSS style is `{ dom: true, mount(layer, ctx, still) }`: it fills the
// layer element with its own elements; the runtime adds `is-moving` when it
// should move.

const BG_ART_BUILDERS = {
  // Curtains of light. Each band is a row of vertical rays, one per backing
  // column, whose height and brightness follow two noise fields: one slow
  // (the folds of the curtain, drifting sideways) and one fine (the
  // striations). Each ray's colour runs from the band's hue at its bright
  // lower edge to a cooler, fainter hue at its top, the way an aurora does.
  // A scatter of motes drifts up through it. The old aurora was particles on
  // a flow field with a rotating emblem ring at the centre; the ring read as
  // an object in the middle of the page and the particles as dust.
  //
  // **Cost.** The curtain is written pixel by pixel into one reused
  // ImageData at a fifth of the pixel density (a twenty-fifth of the
  // pixels; the compositor's upscale is the blur a curtain wants anyway),
  // and only the rows the curtain touched this frame or the last are
  // cleared, converted and put back. The first version drew each ray as a scaled sprite:
  // about 400 `drawImage` calls a frame, 7.7ms in the dark theme, most of it
  // per-call overhead. Each ray's colour profile is a lookup table built once.
  aurora(p, ctx) {
    // Half that again vertically: a ray changes slowly along its length,
    // so ninety rows carry the same curtain as a hundred and eighty, and
    // the per-pixel loop below is the whole cost of this style.
    const PD = 0.2, PDY = 0.1;
    const OFFSETS = [-26, 18, 52];
    const LUT = 96; // steps in a ray's colour profile, top to bottom
    let W = 0, H = 0, bw = 0, bh = 0;
    let img = null, px = null, acc = null;
    let prevTop = 0, prevBottom = -1;
    const bands = [];
    let n = 0, mx, my, mz, mph, mhue;
    const moteFill = [];
    const light = ctx.dark ? 68 : 50;
    const sat = ctx.dark ? 85 : 72;
    // The ray's profile: transparent at the
    // top, a faint cool veil, the band's colour, a bright lower edge, then a
    // quick fade below it. Premultiplied, so bands add or layer directly.
    const profile = (hue) => {
      const stops = [
        [0, hue + 46, light, 0],
        [0.4, hue + 30, light, 0.3],
        [0.78, hue + 8, light + 4, 0.8],
        [0.9, hue, light + (ctx.dark ? 14 : 2), 1],
        [1, hue - 6, light, 0],
      ];
      const lut = new Float32Array(LUT * 4);
      for (let k = 0; k < LUT; k++) {
        const u = k / (LUT - 1);
        let s = 0;
        while (s < stops.length - 2 && u > stops[s + 1][0]) s++;
        const [u0, h0, l0, a0] = stops[s], [u1, h1, l1, a1] = stops[s + 1];
        const f = (u - u0) / (u1 - u0);
        const [r, g, b] = bgHslToRgb(h0 + (h1 - h0) * f, sat, l0 + (l1 - l0) * f);
        const a = a0 + (a1 - a0) * f;
        lut[k * 4] = r * a; lut[k * 4 + 1] = g * a; lut[k * 4 + 2] = b * a; lut[k * 4 + 3] = a;
      }
      return lut;
    };
    return {
      background: "clear",
      pixelDensity: PD,
      pixelDensityY: PDY,
      darkCap: 0.1,
      lightFloor: 0.35,
      init() {
        W = p.width; H = p.height;
        const canvas = p.drawingContext.canvas;
        bw = canvas.width; bh = canvas.height;
        img = p.drawingContext.createImageData(bw, bh);
        px = img.data;
        acc = new Float32Array(bw * bh * 4);
        for (let i = 0; i < OFFSETS.length; i++) {
          bands.push({
            lut: profile(ctx.baseHue + OFFSETS[i]),
            y: 0.34 + i * 0.13 + p.random(-0.03, 0.03),
            amp: 0.16 + p.random(0.05),
            h: 0.34 + p.random(0.12),
            seed: p.random(1000),
            drift: (p.random() < 0.5 ? -1 : 1) * p.random(0.03, 0.06),
            alpha: (ctx.dark ? 1.4 : 0.9) * (i === 1 ? 1 : 0.8),
          });
          moteFill.push(bgHsla(ctx.baseHue + OFFSETS[i], 70, ctx.dark ? 82 : 45, ctx.dark ? 0.9 : 0.7));
        }
        n = Math.max(12, Math.round(56 * ctx.density));
        mx = new Float32Array(n); my = new Float32Array(n);
        mz = new Float32Array(n); mph = new Float32Array(n);
        mhue = new Uint8Array(n);
        for (let i = 0; i < n; i++) {
          mx[i] = p.random(W); my[i] = p.random(H); mz[i] = p.random(0.3, 1);
          mph[i] = p.random(Math.PI * 2); mhue[i] = i % OFFSETS.length;
        }
      },
      frame(t) {
        const g = p.drawingContext;
        // Only the rows written last frame hold anything to clear.
        if (prevBottom >= prevTop) acc.fill(0, prevTop * bw * 4, (prevBottom + 1) * bw * 4);
        let rowTop = bh, rowBottom = -1;
        const add = ctx.dark; // light adds up in the dark, layers like ink in the light
        for (let bi = 0; bi < bands.length; bi++) {
          const b = bands[bi];
          const lut = b.lut;
          for (let x = 0; x < bw; x++) {
            const nx = x / bw;
            // Fade the curtain out at both edges so it hangs in the sky
            // rather than being cut off by the window.
            const edge = Math.min(1, nx * 5, (1 - nx) * 5);
            if (edge <= 0) continue;
            const fold = bgFlow(b.seed + nx * 2.4 + t * b.drift, t * 0.3);
            // The envelope (where the curtain is bright) and the rays inside
            // it: forty noise cycles across the window, a ray every few
            // columns, each its own height.
            const fine = bgFlow(b.seed + 40 + nx * 7 - t * 0.12, t * 0.5);
            const ray = bgFlow(b.seed + 90 + nx * 40 + t * b.drift * 4, t * 0.25);
            let a = fine * fine * 1.9 * b.alpha * edge * (0.45 + fold) * (0.35 + 0.9 * ray);
            if (a < 0.02) continue;
            if (a > 1) a = 1;
            const base = (b.y + (fold - 0.5) * b.amp + Math.sin(nx * 5 + t * 0.7 + b.seed) * 0.015) * bh;
            const h = b.h * bh * (0.45 + fine * 0.5 + ray * 0.45);
            const top = base - h * 0.9;
            const y0 = Math.max(0, Math.ceil(top)), y1 = Math.min(bh - 1, Math.floor(top + h));
            if (y0 < rowTop) rowTop = y0;
            if (y1 > rowBottom) rowBottom = y1;
            const scale = (LUT - 1) / h;
            for (let y = y0; y <= y1; y++) {
              const k = ((y - top) * scale) | 0;
              const l = k * 4;
              const sa = lut[l + 3] * a;
              if (sa < 0.004) continue;
              const o = (y * bw + x) * 4;
              if (add) {
                acc[o] += lut[l] * a; acc[o + 1] += lut[l + 1] * a;
                acc[o + 2] += lut[l + 2] * a; acc[o + 3] += sa;
              } else {
                const keep = 1 - sa;
                acc[o] = lut[l] * a + acc[o] * keep;
                acc[o + 1] = lut[l + 1] * a + acc[o + 1] * keep;
                acc[o + 2] = lut[l + 2] * a + acc[o + 2] * keep;
                acc[o + 3] = sa + acc[o + 3] * keep;
              }
            }
          }
        }
        // Premultiplied to straight alpha, for ImageData, over this frame's
        // rows and last frame's (which may need clearing to nothing).
        const r0 = Math.min(rowTop, prevTop), r1 = Math.max(rowBottom, prevBottom);
        prevTop = rowTop; prevBottom = rowBottom;
        for (let o = r0 * bw * 4, end = (r1 + 1) * bw * 4; o < end; o += 4) {
          const al = acc[o + 3];
          if (al <= 0.002) { px[o + 3] = 0; continue; }
          const A = al < 1 ? al : 1;
          const inv = 1 / al; // the profile is already in 0..255
          px[o] = acc[o] * inv; px[o + 1] = acc[o + 1] * inv; px[o + 2] = acc[o + 2] * inv;
          px[o + 3] = A * 255;
        }
        if (r1 >= r0) g.putImageData(img, 0, 0, 0, r0, bw, r1 - r0 + 1);
        // Motes: at a fifth of the density each is about one soft backing
        // pixel, a speck of light rather than a hard dot.
        g.globalCompositeOperation = ctx.dark ? "lighter" : "source-over";
        let lastHue = -1;
        for (let i = 0; i < n; i++) {
          const z = mz[i];
          my[i] -= 0.12 + z * 0.25;
          mx[i] += (bgFlow(mx[i] * 0.004 + t * 0.2, my[i] * 0.004) - 0.5) * 0.8;
          if (my[i] < -8) { my[i] = H + 8; mx[i] = p.random(W); }
          if (mx[i] < -8) mx[i] = W + 8;
          else if (mx[i] > W + 8) mx[i] = -8;
          if (mhue[i] !== lastHue) { lastHue = mhue[i]; g.fillStyle = moteFill[lastHue]; }
          g.globalAlpha = (0.55 + 0.45 * Math.sin(t * 6 * z + mph[i])) * z;
          const s = 5 + z * 4;
          g.fillRect(mx[i] - s / 2, my[i] - s / 2, s, s);
        }
        g.globalAlpha = 1;
        g.globalCompositeOperation = "source-over";
      },
    };
  },

  // Stars at three depths drifting past at speeds to match, so the field
  // reads as space with distance in it rather than a flat sheet of dots.
  // Stars link to neighbours in their own layer only, which keeps the near
  // layer's web bold and the far layer's a faint lace. They twinkle, the
  // brightest carry a halo, a faint nebula sits behind them, and now and
  // then a meteor crosses. The old version searched every pair (3,486 pairs
  // at 84 stars) and built a colour string per line and per star each
  // frame: 140MB of allocations in ten seconds, measured.
  constellation(p, ctx) {
    const LAYERS = [
      { z: 0.35, link: 95, width: 0.6, alpha: ctx.dark ? 0.2 : 0.24, light: ctx.dark ? 72 : 55, size: 1.3, share: 0.45 },
      { z: 0.65, link: 130, width: 0.8, alpha: ctx.dark ? 0.32 : 0.36, light: ctx.dark ? 78 : 46, size: 1.9, share: 0.35 },
      { z: 1, link: 165, width: 1, alpha: ctx.dark ? 0.48 : 0.5, light: ctx.dark ? 86 : 38, size: 2.8, share: 0.2 },
    ];
    const BUCKETS = 4;
    const HUES = [-24, -10, 0, 12, 26];
    const STAR_SIZES = [0.85, 1.15];
    // The far layer's four twinkle steps: the sprites' 0.62 + 0.38 sin at
    // the middle of each quarter of the swing, times the layer's base
    // strength (0.5 + 0.5z), times 0.8 because a hard square of a given
    // alpha reads brighter than a soft dot of the same.
    const FAR_ALPHA = [0.335, 0.525, 0.715, 0.905].map((a) => a * 0.675 * 0.8);
    let farFill = "", farStep = null;
    let W = 0, H = 0, n = 0;
    let sx, sy, sjx, sjy, ssize, sph, stw, shue;
    const lFrom = [], lTo = [], grids = [], strokes = [], dots = [];
    let seg, segB, segMax = 0, halo = null, nebula = null, tail = null;
    let driftX = 0, driftY = 0;
    const meteor = { on: false, x: 0, y: 0, vx: 0, vy: 0, life: 0 };
    let nextMeteor = 0;
    return {
      background: "clear",
      darkCap: 0.12,
      // The stars move 0.05 to 0.3 pixels a frame: 15 frames a second show
      // the same drift (INBOX 1436). `k` is how many of the old frames one
      // draw stands for, so drift, twinkle and the meteor keep their speed.
      fps: 15,
      init() {
        W = p.width; H = p.height;
        // One star per 8000 square pixels (162 at 1440x900): at 6000 the dark
        // frame measured 2.02ms of CPU, over the 2ms every style keeps under.
        n = bgClamp(Math.round((W * H) / 8000 * ctx.density), 40, 260);
        sx = new Float32Array(n); sy = new Float32Array(n);
        sjx = new Float32Array(n); sjy = new Float32Array(n);
        ssize = new Uint8Array(n); sph = new Float32Array(n);
        stw = new Float32Array(n); shue = new Uint8Array(n);
        const heading = p.random(Math.PI * 2);
        driftX = Math.cos(heading); driftY = Math.sin(heading);
        // Each layer is one contiguous run of the arrays, far to near, so a
        // layer's grid and draw loop are a range, not a filter.
        let at = 0;
        for (let li = 0; li < LAYERS.length; li++) {
          const L = LAYERS[li];
          const count = li === LAYERS.length - 1 ? n - at : Math.round(n * L.share);
          lFrom.push(at); lTo.push(at + count);
          for (let i = at; i < at + count; i++) {
            sx[i] = p.random(W); sy[i] = p.random(H);
            sjx[i] = p.random(-0.05, 0.05); sjy[i] = p.random(-0.05, 0.05);
            // Which of the two painted sizes (see the sprites below).
            ssize[i] = p.random() < 0.5 ? 0 : 1;
            sph[i] = p.random(Math.PI * 2); stw[i] = p.random(0.5, 1.5);
            shue[i] = Math.floor(p.random(HUES.length));
          }
          at += count;
          grids.push(bgGrid(W, H, L.link, n));
          // In the dark theme the stars may be brighter than the darkCap
          // (the nebula's): a star is a point that passes behind a word for
          // a moment, the nebula is a wash that sits there. The lines are
          // between the two.
          const cap = bgLumCap;
          if (cap) bgLumCap = 0.2;
          const row = [];
          for (let k = 0; k < BUCKETS; k++) row.push(bgHsla(ctx.baseHue, 55, L.light, L.alpha * ((k + 1) / BUCKETS)));
          strokes.push(row);
          if (cap) bgLumCap = 0.4;
          // Two sizes per hue, each painted at the size it is drawn (three
          // star radii), so a frame copies it unscaled: 216 scaled copies a
          // frame were a third of this style's cost.
          const drow = [];
          for (const off of HUES) {
            for (const k of STAR_SIZES) {
              drow.push(bgGlowSprite(ctx.baseHue + off, ctx.dark ? 60 : 72, L.light + (ctx.dark ? 6 : -4), 1,
                Math.max(3, Math.round(L.size * k * 3)), 0.6));
            }
          }
          dots.push(drow);
          if (li === 0) farFill = bgHsla(ctx.baseHue, ctx.dark ? 60 : 72, L.light + (ctx.dark ? 6 : -4), 1);
          bgLumCap = cap;
        }
        farStep = new Uint8Array(n);
        segMax = n * 10;
        seg = new Float32Array(segMax * 4);
        segB = new Uint8Array(segMax);
        if (bgLumCap) bgLumCap = 0.4;
        halo = bgGlowSprite(ctx.baseHue, 70, ctx.dark ? 80 : 55, ctx.dark ? 0.5 : 0.28,
          Math.round(LAYERS[2].size * STAR_SIZES[1] * 9));
        if (bgLumCap) bgLumCap = 0.12;
        // The nebula: three soft clouds painted once, small, and set as the
        // canvas element's own CSS background, so the compositor scales it
        // and the frame never draws it. Copied into the canvas every frame
        // it cost 0.7ms at one to one and 5ms scaled; a still frame, which
        // is captured from the canvas alone, draws it once.
        nebula = bgSprite(W / 8, H / 8, (g, w, h) => {
          for (let k = 0; k < 3; k++) {
            const cx = w * p.random(0.15, 0.85), cy = h * p.random(0.15, 0.85);
            const rad = w * p.random(0.22, 0.4);
            const grad = g.createRadialGradient(cx, cy, 0, cx, cy, rad);
            const hue = ctx.baseHue + [-40, 0, 45][k];
            grad.addColorStop(0, bgHsla(hue, 60, ctx.dark ? 45 : 68, ctx.dark ? 0.32 : 0.34));
            grad.addColorStop(1, bgHsla(hue, 60, ctx.dark ? 45 : 70, 0));
            g.fillStyle = grad;
            g.fillRect(0, 0, w, h);
          }
        });
        if (!ctx.still) {
          p.canvas.style.backgroundImage = `url("${nebula.toDataURL()}")`;
          p.canvas.style.backgroundSize = "100% 100%";
        }
        // The meteor's tail, drawn rotated rather than a gradient a frame;
        // as bright as a star, and gone as quickly.
        if (bgLumCap) bgLumCap = 0.4;
        tail = bgSprite(256, 6, (g, w, h) => {
          const grad = g.createLinearGradient(0, 0, w, 0);
          grad.addColorStop(0, bgHsla(ctx.baseHue, 60, ctx.dark ? 85 : 45, 0));
          grad.addColorStop(1, bgHsla(ctx.baseHue, 60, ctx.dark ? 92 : 38, 0.8));
          g.fillStyle = grad;
          g.fillRect(0, h / 2 - 1, w, 2);
        });
        nextMeteor = 240 + Math.floor(p.random(360));
      },
      frame(t) {
        const g = p.drawingContext;
        const k = Math.min(30, bgArtFrameRate()) / Math.min(15, bgArtFrameRate());
        const tk = t * k;
        if (ctx.still) g.drawImage(nebula, 0, 0, W, H);
        g.lineCap = "butt";
        for (let li = 0; li < LAYERS.length; li++) {
          const L = LAYERS[li];
          const from = lFrom[li], to = lTo[li];
          const vx = driftX * 0.22 * L.z * k, vy = driftY * 0.22 * L.z * k;
          for (let i = from; i < to; i++) {
            let x = sx[i] + vx + sjx[i] * k, y = sy[i] + vy + sjy[i] * k;
            if (x < -10) x += W + 20; else if (x > W + 10) x -= W + 20;
            if (y < -10) y += H + 20; else if (y > H + 10) y -= H + 20;
            sx[i] = x; sy[i] = y;
          }
          // Links: every pair within reach, found through the grid, each
          // written once (j > i) into the segment buffer with its strength.
          const grid = grids[li];
          grid.build(sx, sy, from, to);
          const cols = grid.cols, st = grid.start, items = grid.items;
          const reach2 = L.link * L.link;
          let ns = 0;
          for (let i = from; i < to && ns < segMax; i++) {
            const c = grid.cellAt(sx[i], sy[i]);
            const cx = c % cols, cy = (c - cx) / cols;
            for (let oy = -1; oy <= 1; oy++) {
              const ry = cy + oy;
              if (ry < 0 || ry >= grid.rows) continue;
              for (let ox = -1; ox <= 1; ox++) {
                const rx = cx + ox;
                if (rx < 0 || rx >= cols) continue;
                const cell = ry * cols + rx;
                for (let k = st[cell]; k < st[cell + 1]; k++) {
                  const j = items[k];
                  if (j <= i) continue;
                  const dx = sx[j] - sx[i], dy = sy[j] - sy[i];
                  const d2 = dx * dx + dy * dy;
                  if (d2 >= reach2 || ns >= segMax) continue;
                  const o = ns * 4;
                  seg[o] = sx[i]; seg[o + 1] = sy[i]; seg[o + 2] = sx[j]; seg[o + 3] = sy[j];
                  segB[ns] = Math.min(BUCKETS - 1, Math.floor((1 - Math.sqrt(d2) / L.link) * BUCKETS));
                  ns++;
                }
              }
            }
          }
          g.lineWidth = L.width;
          for (let b = 0; b < BUCKETS; b++) {
            g.beginPath();
            let any = false;
            for (let s = 0; s < ns; s++) {
              if (segB[s] !== b) continue;
              const o = s * 4;
              g.moveTo(seg[o], seg[o + 1]);
              g.lineTo(seg[o + 2], seg[o + 3]);
              any = true;
            }
            if (!any) continue;
            g.strokeStyle = strokes[li][b];
            g.stroke();
          }
        }
        // Stars, far to near. The far layer, the most numerous and each
        // under two pixels across, is squares in one path per twinkle step
        // (four fills, not a hundred image copies); the nearer two are soft
        // dot sprites, with halos on the near layer.
        if (ctx.dark) g.globalCompositeOperation = "lighter";
        g.fillStyle = farFill;
        for (let i = lFrom[0]; i < lTo[0]; i++) {
          const tw = Math.sin(tk * 9 * stw[i] + sph[i]);
          farStep[i] = tw > 0.5 ? 3 : tw > 0 ? 2 : tw > -0.5 ? 1 : 0;
        }
        for (let k = 0; k < 4; k++) {
          g.globalAlpha = FAR_ALPHA[k];
          g.beginPath();
          for (let i = lFrom[0]; i < lTo[0]; i++) {
            if (farStep[i] === k) g.rect((sx[i] - 1) | 0, (sy[i] - 1) | 0, 2, 2);
          }
          g.fill();
        }
        for (let li = 1; li < LAYERS.length; li++) {
          const L = LAYERS[li];
          const base = 0.5 + 0.5 * L.z;
          const sprites = dots[li];
          const hh = halo.width / 2;
          for (let i = lFrom[li]; i < lTo[li]; i++) {
            const tw = 0.62 + 0.38 * Math.sin(tk * 9 * stw[i] + sph[i]);
            const big = ssize[i];
            // Whole pixels, like the microbes: a copy at a fractional place
            // is resampled, and a star drifting a fifth of a pixel a frame
            // shows no step.
            if (li === 2 && big) {
              g.globalAlpha = tw * 0.8;
              g.drawImage(halo, (sx[i] - hh) | 0, (sy[i] - hh) | 0);
            }
            g.globalAlpha = base * tw;
            const spr = sprites[shue[i] * 2 + big];
            g.drawImage(spr, (sx[i] - spr.width / 2) | 0, (sy[i] - spr.width / 2) | 0);
          }
        }
        g.globalAlpha = 1;
        // A meteor every twenty seconds or so, faint and quick.
        if (!meteor.on && (nextMeteor -= k) <= 0) {
          const ang = p.random(0.35, 0.75);
          const left = p.random() < 0.5;
          meteor.on = true; meteor.life = 0;
          meteor.x = left ? p.random(W * 0.05, W * 0.45) : p.random(W * 0.55, W * 0.95);
          meteor.y = p.random(H * 0.05, H * 0.35);
          meteor.vx = Math.cos(ang) * 14 * (left ? 1 : -1);
          meteor.vy = Math.sin(ang) * 14;
          nextMeteor = 450 + Math.floor(p.random(450));
        }
        if (meteor.on) {
          meteor.life += k;
          meteor.x += meteor.vx * k; meteor.y += meteor.vy * k;
          g.globalAlpha = Math.sin(Math.min(1, meteor.life / 34) * Math.PI);
          g.save();
          g.translate(meteor.x, meteor.y);
          g.rotate(Math.atan2(meteor.vy, meteor.vx));
          g.drawImage(tail, -110, -3, 110, 6);
          g.restore();
          g.globalAlpha = 1;
          if (meteor.life > 34) meteor.on = false;
        }
        g.globalCompositeOperation = "source-over";
      },
    };
  },

  // Layered scrolling sine waves, looking as they did (the owner likes
  // them): the same layers, curves, colours and trail wash. What changed is
  // only the cost: the colours are built once (the exact string p5's
  // `color(...).toString()` gave, see bgP5Rgba), the curves go straight to
  // the canvas as one path each instead of through p5's vertex list, which
  // allocated per vertex, and the canvas is at half the pixel density: the
  // waves are translucent fills with no line in them, and the compositor's
  // upscale softens their edges by one pixel, which is the only difference.
  waves(p, ctx) {
    let fills = [];
    let layers = 0;
    return {
      background: "wash",
      pixelDensity: 0.5,
      // A crest moves under a pixel a frame (INBOX 1436): 15 frames a second.
      fps: 15,
      init() {
        // Five layers at full intensity, fewer at less.
        layers = Math.max(2, Math.round(5 * ctx.density));
        fills = [];
        for (let l = 0; l < layers; l++) {
          const hue = (ctx.baseHue + l * 12) % 360;
          fills.push(bgP5Rgba(hue, 62, ctx.dark ? 55 : 58, 0.16));
        }
      },
      frame(t0) {
        const g = p.drawingContext;
        const W = p.width, H = p.height;
        const t = t0 * (Math.min(30, bgArtFrameRate()) / Math.min(15, bgArtFrameRate()));
        for (let l = 0; l < layers; l++) {
          const yBase = H * (0.35 + l * 0.13);
          const amp = 26 + l * 10;
          g.fillStyle = fills[l];
          g.beginPath();
          g.moveTo(0, H);
          for (let x = 0; x <= W; x += 14) {
            const y = yBase + Math.sin(x * 0.006 + t * (0.6 + l * 0.18) + l) * amp
              + Math.sin(x * 0.013 - t * 0.4) * (amp * 0.35);
            g.lineTo(x, y);
          }
          // The last step stopped short of the right edge (x is a multiple
          // of 14), which left a sliver of the window uncovered at every
          // width but a multiple of 14: the curve is carried on to the edge.
          if (W % 14) {
            g.lineTo(W, yBase + Math.sin(W * 0.006 + t * (0.6 + l * 0.18) + l) * amp
              + Math.sin(W * 0.013 - t * 0.4) * (amp * 0.35));
          }
          g.lineTo(W, H);
          g.closePath();
          g.fill();
        }
      },
    };
  },

  // Glass bubbles rising at three depths. Each bubble is a pre-rendered
  // image (made once, here); near bubbles are large, quick and out of
  // focus, far ones small, slow and soft, the middle ones in focus: a
  // coloured rim, a clear centre, a highlight and a reflection. Each rises,
  // sways on its own period and wobbles.
  //
  // **Cost.** A frame clears only where each bubble was (its last box, not
  // the window) and copies two dozen images: under a millisecond in a
  // software canvas at 1440x900. The version before this was the same
  // images as seventy-two CSS-animated elements, which cost the page
  // nothing but kept the compositor redrawing at the display's full rate:
  // the whole browser spent about a core on it (1,000ms of CPU a second
  // against 150 with the art off, in software compositing, bgartcost.js),
  // more than any canvas style.
  bubbles(p, ctx) {
    let W = 0, H = 0, n = 0, secs = 0;
    let bx, by, br, bspeed, bdx, bsw, bsp, bww, bwp, balpha, bimg;
    let last = null; // each bubble's last drawn box: x, y, w, h
    const images = [];
    return {
      background: "keep",
      lightFloor: 0.3,
      // The fastest bubble rises 0.72 pixels a frame at 30 (INBOX 1436):
      // `dt` is in seconds, so 15 frames a second move the same.
      fps: 15,
      init() {
        W = p.width; H = p.height;
        const rand = bgRandom(Math.round(ctx.baseHue * 1000) + 7);
        const L = ctx.dark ? 62 : 52;
        const SPRITE = 160;
        const glass = (hue) => bgSprite(SPRITE, SPRITE, (g, w) => {
          const r = w / 2;
          const body = g.createRadialGradient(r, r, r * 0.1, r, r, r);
          body.addColorStop(0, bgHsla(hue, 70, L, 0.04));
          body.addColorStop(0.62, bgHsla(hue, 70, L, 0.1));
          body.addColorStop(0.86, bgHsla(hue + 18, 75, L, 0.34));
          body.addColorStop(0.96, bgHsla(hue + 30, 80, L - 6, 0.55));
          body.addColorStop(1, bgHsla(hue + 30, 80, L, 0));
          g.fillStyle = body;
          g.beginPath(); g.arc(r, r, r, 0, Math.PI * 2); g.fill();
          // The iridescent side: a second tint pooled at the lower right.
          const film = g.createRadialGradient(r * 1.35, r * 1.35, 0, r * 1.35, r * 1.35, r * 0.9);
          film.addColorStop(0, bgHsla(hue + 60, 75, L + 8, 0.22));
          film.addColorStop(1, bgHsla(hue + 60, 75, L + 8, 0));
          g.fillStyle = film;
          g.beginPath(); g.arc(r, r, r * 0.97, 0, Math.PI * 2); g.fill();
          const hx = r * 0.62, hy = r * 0.56;
          const spec = g.createRadialGradient(hx, hy, 0, hx, hy, r * 0.32);
          spec.addColorStop(0, `rgba(255,255,255,${ctx.dark ? 0.7 : 0.9})`);
          spec.addColorStop(1, "rgba(255,255,255,0)");
          g.fillStyle = spec;
          g.beginPath(); g.arc(hx, hy, r * 0.32, 0, Math.PI * 2); g.fill();
          g.strokeStyle = `rgba(255,255,255,${ctx.dark ? 0.28 : 0.5})`;
          g.lineWidth = r * 0.04;
          g.beginPath(); g.arc(r, r, r * 0.8, Math.PI * 0.15, Math.PI * 0.45); g.stroke();
        });
        const bokeh = (hue) => bgSprite(SPRITE / 2, SPRITE / 2, (g, w) => {
          const r = w / 2;
          const body = g.createRadialGradient(r, r, 0, r, r, r);
          body.addColorStop(0, bgHsla(hue, 70, L, 0.3));
          body.addColorStop(0.7, bgHsla(hue, 70, L, 0.22));
          body.addColorStop(0.9, bgHsla(hue, 70, L, 0.1));
          body.addColorStop(1, bgHsla(hue, 70, L, 0));
          g.fillStyle = body;
          g.fillRect(0, 0, w, w);
        });
        const hues = [0, 32, -34].map((o) => ctx.baseHue + o);
        for (const h of hues) images.push(glass(h));
        for (const h of hues) images.push(bokeh(h));
        n = Math.max(6, Math.round(24 * ctx.density));
        const f = () => new Float32Array(n);
        bx = f(); by = f(); br = f(); bspeed = f(); bdx = f(); bsw = f(); bsp = f();
        bww = f(); bwp = f(); balpha = f(); bimg = new Uint8Array(n);
        last = new Float32Array(n * 4);
        for (let i = 0; i < n; i++) {
          // Far to near in order, so near bubbles paint on top.
          const z = i / n;
          const r = 10 + z * z * 88;
          const blurred = z < 0.3 || z > 0.86;
          const kind = Math.floor(rand() * 3);
          br[i] = r;
          bx[i] = (rand() * 1.04 - 0.02) * W;
          // Anywhere on its way up, so the window starts full.
          by[i] = rand() * (H + r * 2) - r;
          // 0.12 to 0.72 pixels a frame at 30 frames a second.
          bspeed[i] = (0.12 + z * 0.6) * 30;
          bdx[i] = (8 + rand() * 26) * (0.4 + z);
          bsw[i] = Math.PI / (4 + rand() * 5);
          bsp[i] = rand() * Math.PI * 2;
          bww[i] = Math.PI / (1.3 + rand() * 0.6);
          bwp[i] = rand() * Math.PI * 2;
          bimg[i] = blurred ? 3 + kind : kind;
          balpha[i] = blurred ? (z < 0.3 ? 0.55 + z : 0.6) : 0.95;
        }
      },
      frame() {
        const g = p.drawingContext;
        const dt = 1 / Math.min(15, bgArtFrameRate());
        secs += dt;
        // Clear each bubble's last box (a pixel wider for the smoothing).
        for (let i = 0; i < n; i++) {
          const o = i * 4;
          if (last[o + 2]) g.clearRect(last[o] - 1, last[o + 1] - 1, last[o + 2] + 2, last[o + 3] + 2);
        }
        for (let i = 0; i < n; i++) {
          const r = br[i];
          by[i] -= bspeed[i] * dt;
          if (by[i] < -r * 1.1) { by[i] = H + r * 1.1; bx[i] = (bgRand() * 1.04 - 0.02) * W; }
          const x = bx[i] + Math.sin(secs * bsw[i] + bsp[i]) * bdx[i];
          // The wobble: wider as it is shorter and back, 3.5% each way.
          const wob = Math.sin(secs * bww[i] + bwp[i]) * 0.035;
          const w = r * 2 * (1 + wob), h = r * 2 * (1 - wob);
          const left = x - w / 2, top = by[i] - h / 2;
          g.globalAlpha = balpha[i];
          g.drawImage(images[bimg[i]], left, top, w, h);
          const o = i * 4;
          last[o] = left; last[o + 1] = top; last[o + 2] = w; last[o + 3] = h;
        }
        g.globalAlpha = 1;
      },
    };
  },

  // A living mesh gradient: a handful of large soft colour fields drifting
  // on slow crossed paths (each axis its own period, so each field traces a
  // Lissajous-like loop) over a tinted ground.
  //
  // **Cost.** Everything here is soft, so it is drawn on a canvas at a
  // fifth of the pixel density (288 by 180 backing pixels at 1440x900; an
  // eighth showed the upscale's grid) and the compositor's upscale is the
  // blur the fields want anyway: a frame is one tinted fill and seven small
  // sprite copies into fifty thousand pixels. And it moves so slowly (a field crosses a few pixels a frame at
  // most) that fifteen frames a second look the same as sixty. The version
  // before this was seven CSS-animated elements up to 120vmax across,
  // composited at the display's full rate: no page work, but the whole
  // browser spent a core on it (1,000ms of CPU a second against 150 with the
  // art off, measured in software compositing by bgartcost.js), more than
  // any canvas style.
  mesh(p, ctx) {
    const offsets = [0, 38, -34, 74, -68, 16, 150];
    const fields = [];
    let ground = "", W = 0, H = 0, secs = 0;
    return {
      background: "keep",
      pixelDensity: 0.2,
      fps: 15,
      darkCap: 0.05,
      lightFloor: 0.55,
      init() {
        W = p.width; H = p.height;
        const rand = bgRandom(Math.round(ctx.baseHue * 1000) + 3);
        ground = bgHsla(ctx.baseHue, ctx.dark ? 35 : 45, ctx.dark ? 13 : 95, 1);
        const n = bgClamp(Math.round(4 + 3 * ctx.density), 4, offsets.length);
        const l = ctx.dark ? 42 : 70;
        const vmax = Math.max(W, H) / 100;
        for (let i = 0; i < n; i++) {
          const hue = ctx.baseHue + offsets[i];
          // The far hues are quieter, so the accent stays the lead.
          const sat = Math.abs(offsets[i]) > 60 ? 50 : 75;
          const r = (38 + rand() * 22) * vmax; // radius
          const cx = (0.2 + rand() * 0.6) * W, cy = (0.2 + rand() * 0.6) * H; // centre
          const ax = (0.18 + rand() * 0.2) * W, ay = (0.16 + rand() * 0.18) * H; // reach
          // A full swing each way takes 20 to 45 seconds.
          const wx = Math.PI / (20 + rand() * 25), wy = Math.PI / (22 + rand() * 25);
          const px = rand() * Math.PI * 2, py = rand() * Math.PI * 2;
          // The field: a radial gradient, strong at the centre, half way at
          // half the radius, gone at the edge, painted once at about the
          // size it is drawn (from 64 pixels, the upscale showed a grid).
          const sprite = bgSprite(256, 256, (g, w) => {
            const c = w / 2;
            const grad = g.createRadialGradient(c, c, 0, c, c, c);
            grad.addColorStop(0, bgHsla(hue, sat, l, ctx.dark ? 0.75 : 0.8));
            grad.addColorStop(0.5, bgHsla(hue, sat, l, ctx.dark ? 0.3 : 0.32));
            grad.addColorStop(1, bgHsla(hue, sat, l, 0));
            g.fillStyle = grad;
            g.fillRect(0, 0, w, w);
          });
          fields.push({ sprite, r, cx, cy, ax, ay, wx, wy, px, py });
        }
      },
      frame() {
        const g = p.drawingContext;
        // Seconds, at whatever rate the loop runs, so the drift keeps its
        // speed at 20 frames a second as at 30.
        secs += 1 / Math.min(15, bgArtFrameRate());
        g.fillStyle = ground;
        // Past the edges: the backing size is rounded, and a part-covered
        // last row showed as a line along the bottom.
        g.fillRect(0, 0, W + 10, H + 10);
        for (let i = 0; i < fields.length; i++) {
          const f = fields[i];
          const x = f.cx + Math.sin(secs * f.wx + f.px) * f.ax;
          const y = f.cy + Math.sin(secs * f.wy + f.py) * f.ay;
          g.drawImage(f.sprite, x - f.r, y - f.r, f.r * 2, f.r * 2);
        }
      },
    };
  },

  // An ecosystem grown from a name (the helixlabs idea, see bgArtGenome).
  // Three to five species, each a strain of the display name, and every
  // trait of a species read from its strain's letters: its body (round,
  // rod, comma, diatom, amoeba, flagellate), how it moves (wandering,
  // schooling with its own kind, orbiting, tracing a Lissajous figure,
  // clustering as a colony), its hue around the accent, its size, speed,
  // glow and wake, and how often it divides. Organisms swim, divide in two
  // when there is room, and fade out with age, so the population holds
  // steady while its members turn over. Every organism is a slot in a set
  // of typed arrays; division takes the next free slot and a death swaps
  // the last slot into its place, so nothing is allocated per frame.
  microbes(p, ctx) {
    const FORMS = ["coccus", "bacillus", "vibrio", "diatom", "amoeba", "flagellate"];
    const MOVES = ["drift", "flock", "orbit", "lissajous", "colony"];
    const GLOWS = ["none", "steady", "pulse"];
    const TRAILS = ["none", "dots", "wake"];
    const HL = 7; // wake points kept per organism
    const CELL = 80;
    let W = 0, H = 0, cap = 0, n = 0, frameNo = 0;
    const species = [];
    let X, Y, VX, VY, ANG, SPIN, AGE, NEXT, LIFE, DIV, BORN, DYING, SEED, OFF, ORBR, ORBD, SP;
    let HX, HY, HN, HH, AQ, FIELDS, grid;
    const AQN = new Int32Array(5 * 5); // bodies per species per opacity quarter
    let nMotes = 0, mx, my, mz, ms, moteFill = "";
    const blob = new Float32Array(16); // the amoeba's outline, reused
    const ink = ctx.dark ? 74 : 40;
    const fillL = ctx.dark ? 58 : 60;

    const place = (i, s, x, y) => {
      const sp = species[s];
      SP[i] = s; X[i] = x; Y[i] = y;
      VX[i] = p.random(-1, 1) * sp.speed; VY[i] = p.random(-1, 1) * sp.speed;
      ANG[i] = p.random(Math.PI * 2); SPIN[i] = p.random(-0.01, 0.01);
      AGE[i] = 0; NEXT[i] = sp.divideAfter * p.random(0.6, 1.4); LIFE[i] = p.random(1800, 3600);
      DIV[i] = -1; BORN[i] = 0; DYING[i] = 0;
      SEED[i] = p.random(1000); OFF[i] = p.random(Math.PI * 2);
      ORBR[i] = p.random(50, 150); ORBD[i] = p.random() < 0.5 ? -1 : 1;
      HN[i] = 0; HH[i] = 0;
    };
    const copySlot = (dst, src) => {
      for (let f = 0; f < FIELDS.length; f++) FIELDS[f][dst] = FIELDS[f][src];
      HX.copyWithin(dst * HL, src * HL, src * HL + HL);
      HY.copyWithin(dst * HL, src * HL, src * HL + HL);
    };

    // The bodies, drawn as vector paths batched per species: every
    // organism of a species adds its outline to one path, which is filled
    // and stroked once, then its organelles to a second and its flagella to
    // a third. Each point is rotated by hand (`c`, `s`: the heading's cosine
    // and sine) instead of through a canvas transform, because a transform
    // per organism means a path per organism. Measured, sixty bodies: a
    // rotated image each cost 3.5ms to raster (rotated bitmaps are the slow
    // path in a software canvas), vector outlines batched like this 0.8ms.
    // `ph` is the organism's animation phase: the flagellum's beat, the
    // amoeba's wobble.
    const PHASE_RATE = { vibrio: 0.3, flagellate: 0.22, amoeba: 0.05 };
    const outline = (g, sp, x, y, c, s, r, ph) => {
      switch (sp.form) {
        case "bacillus": {
          const len = r * 1.4, wid = r * 0.62, th = Math.atan2(s, c);
          const ax = x + c * len, ay = y + s * len, bx = x - c * len, by = y - s * len;
          g.moveTo(bx + s * wid, by - c * wid);
          g.lineTo(ax + s * wid, ay - c * wid);
          g.arc(ax, ay, wid, th - Math.PI / 2, th + Math.PI / 2);
          g.lineTo(bx - s * wid, by + c * wid);
          g.arc(bx, by, wid, th + Math.PI / 2, th + Math.PI * 1.5);
          g.closePath();
          break;
        }
        case "vibrio": {
          const th = Math.atan2(s, c);
          const cx = x - s * r * 0.5, cy = y + c * r * 0.5;
          const a0 = Math.PI * 1.15 + th, a1 = Math.PI * 1.85 + th;
          g.moveTo(cx + Math.cos(a0) * r * 1.2, cy + Math.sin(a0) * r * 1.2);
          g.arc(cx, cy, r * 1.2, a0, a1);
          g.arc(cx, cy, r * 0.55, a1, a0, true);
          g.closePath();
          break;
        }
        case "diatom": {
          const m = sp.sides, th = Math.atan2(s, c);
          for (let ring = 0; ring < 2; ring++) {
            const rr = ring ? r * 0.62 : r * 1.2, off = ring ? Math.PI / m : 0;
            for (let k = 0; k <= m; k++) {
              const q = (k / m) * Math.PI * 2 + off + th;
              const px = x + Math.cos(q) * rr, py = y + Math.sin(q) * rr;
              if (k === 0) g.moveTo(px, py);
              else g.lineTo(px, py);
            }
          }
          break;
        }
        case "amoeba": {
          const m = 8, th = Math.atan2(s, c);
          for (let k = 0; k < m; k++) {
            const q = (k / m) * Math.PI * 2 + th;
            const rr = r * (1 + 0.24 * Math.sin(ph + k * 1.9));
            blob[k * 2] = x + Math.cos(q) * rr;
            blob[k * 2 + 1] = y + Math.sin(q) * rr;
          }
          g.moveTo((blob[0] + blob[2]) / 2, (blob[1] + blob[3]) / 2);
          for (let k = 1; k <= m; k++) {
            const a = (k % m) * 2, b = ((k + 1) % m) * 2;
            g.quadraticCurveTo(blob[a], blob[a + 1], (blob[a] + blob[b]) / 2, (blob[a + 1] + blob[b + 1]) / 2);
          }
          g.closePath();
          break;
        }
        case "flagellate": {
          g.moveTo(x + c * r * 1.25, y + s * r * 1.25);
          g.ellipse(x, y, r * 1.25, r * 0.85, Math.atan2(s, c), 0, Math.PI * 2);
          break;
        }
        default: { // coccus
          g.moveTo(x + r, y);
          g.arc(x, y, r, 0, Math.PI * 2);
        }
      }
    };
    // A point at (lx, ly) in the body's own frame, rotated and placed.
    const dot = (g, x, y, c, s, lx, ly, rad) => {
      const px = x + c * lx - s * ly, py = y + s * lx + c * ly;
      g.moveTo(px + rad, py);
      g.arc(px, py, rad, 0, Math.PI * 2);
    };
    const organelles = (g, sp, x, y, c, s, r) => {
      switch (sp.form) {
        case "bacillus": {
          const len = r * 1.4, wid = r * 0.62;
          dot(g, x, y, c, s, -len * 0.45, 0, wid * 0.32);
          dot(g, x, y, c, s, len * 0.45, 0, wid * 0.32);
          break;
        }
        case "diatom": dot(g, x, y, c, s, 0, 0, r * 0.18); break;
        case "amoeba": dot(g, x, y, c, s, r * 0.2, -r * 0.1, r * 0.3); break;
        case "flagellate": dot(g, x, y, c, s, r * 0.35, 0, r * 0.3); break;
        case "vibrio": break;
        default: dot(g, x, y, c, s, r * 0.25, -r * 0.2, r * 0.34);
      }
    };
    const lash = (g, sp, x, y, c, s, r, ph) => {
      if (sp.form === "vibrio") {
        let lx = -r * 1.1;
        g.moveTo(x + c * lx, y + s * lx);
        for (let k = 1; k <= 6; k++) {
          lx = -r * 1.1 - k * r * 0.45;
          const ly = Math.sin(ph + k * 1.1) * r * 0.25;
          g.lineTo(x + c * lx - s * ly, y + s * lx + c * ly);
        }
      } else if (sp.form === "flagellate") {
        const w = Math.sin(ph);
        const l1 = -r * 1.2, l2x = -r * 2.2, l2y = w * r * 1.1, l3x = -r * 3, l3y = -w * r * 1.1;
        const l4x = -r * 4, l4y = Math.sin(ph + 1) * r * 0.5;
        g.moveTo(x + c * l1, y + s * l1);
        g.bezierCurveTo(
          x + c * l2x - s * l2y, y + s * l2x + c * l2y,
          x + c * l3x - s * l3y, y + s * l3x + c * l3y,
          x + c * l4x - s * l4y, y + s * l4x + c * l4y,
        );
      }
    };
    // Adds every body of species `si` whose opacity rounds to `q` quarters
    // to the current path: its outline (`part` 0), organelles (1) or
    // flagellum (2). Two bodies per organism while it divides.
    const PART = [outline, organelles, lash];
    const bodies = (g, si, q, part) => {
      const sp = species[si];
      const rate = PHASE_RATE[sp.form] || 0;
      const add = PART[part];
      for (let i = 0; i < n; i++) {
        if (SP[i] !== si || AQ[i] !== q) continue;
        const c = Math.cos(ANG[i]), s = Math.sin(ANG[i]);
        const ph = frameNo * rate + OFF[i];
        if (DIV[i] >= 0) {
          // Dividing: two daughters pulling apart along the body's axis,
          // each a little smaller until they separate.
          const d = DIV[i] * sp.size * 1.1;
          const r = sp.size * (1 - 0.18 * Math.sin(DIV[i] * Math.PI));
          add(g, sp, X[i] - c * d, Y[i] - s * d, c, s, r, ph);
          add(g, sp, X[i] + c * d, Y[i] + s * d, c, s, r, ph);
        } else {
          add(g, sp, X[i], Y[i], c, s, sp.size, ph);
        }
      }
    };

    // **The bodies are pre-rendered.** Each species' outline, fill and
    // organelles are painted once into an atlas: one cell per heading (48
    // for a body that points where it swims, 16 for one that only turns, 8
    // for a round one) and, for the amoeba, per step of its wobble. A frame
    // copies one cell per organism, upright, the cheap kind of image draw,
    // where it used to build, fill and stroke every outline: 0.9ms of the
    // frame, measured, for sixty bodies. The flagella still draw as lines,
    // since their beat changes every frame and they are thin.
    const atlasOf = (sp) => {
      const r = sp.size;
      const cell = Math.ceil(r * 4.4 + 4);
      const angles = sp.form === "coccus" ? 8 : sp.turns ? 16 : 48;
      const phases = sp.form === "amoeba" ? 8 : 1;
      const img = bgSprite(cell * angles, cell * phases, (g) => {
        g.lineWidth = 1;
        g.lineJoin = "round";
        for (let ph = 0; ph < phases; ph++) {
          for (let a = 0; a < angles; a++) {
            const th = (a / angles) * Math.PI * 2;
            const c = Math.cos(th), sn = Math.sin(th);
            const x = a * cell + cell / 2, y = ph * cell + cell / 2;
            const phase = (ph / phases) * Math.PI * 2;
            g.beginPath();
            outline(g, sp, x, y, c, sn, r, phase);
            g.fillStyle = sp.cFill;
            g.strokeStyle = sp.cStroke;
            g.fill();
            g.stroke();
            if (sp.form !== "vibrio") {
              g.beginPath();
              organelles(g, sp, x, y, c, sn, r);
              g.fillStyle = sp.cCore;
              g.fill();
            }
          }
        }
      });
      return { img, cell, half: cell / 2, angles, phases };
    };

    const step = () => {
      frameNo++;
      for (const sp of species) {
        sp.cx = W * (0.12 + 0.76 * bgFlow(sp.seed, frameNo * 0.0015));
        sp.cy = H * (0.12 + 0.76 * bgFlow(sp.seed + 91, frameNo * 0.0015));
      }
      grid.build(X, Y, 0, n);
      const cols = grid.cols, st = grid.start, items = grid.items;
      const count = n;
      for (let i = 0; i < count; i++) {
        const sp = species[SP[i]];
        const x = X[i], y = Y[i];
        let dx = 0, dy = 0;
        let sepX = 0, sepY = 0, aliX = 0, aliY = 0, cohX = 0, cohY = 0, mates = 0;
        const c = grid.cellAt(x, y);
        const cx = c % cols, cy = (c - cx) / cols;
        for (let oy = -1; oy <= 1; oy++) {
          const ry = cy + oy;
          if (ry < 0 || ry >= grid.rows) continue;
          for (let ox = -1; ox <= 1; ox++) {
            const rx = cx + ox;
            if (rx < 0 || rx >= cols) continue;
            const cell = ry * cols + rx;
            for (let k = st[cell]; k < st[cell + 1]; k++) {
              const o = items[k];
              if (o === i) continue;
              const ex = x - X[o], ey = y - Y[o];
              const d2 = ex * ex + ey * ey;
              const room = (sp.size + species[SP[o]].size) * 2.2;
              if (d2 > 0 && d2 < room * room) {
                const d = Math.sqrt(d2);
                sepX += (ex / d) * (room - d) / room;
                sepY += (ey / d) * (room - d) / room;
              }
              if (SP[o] === SP[i] && d2 < 5625) {
                aliX += VX[o]; aliY += VY[o]; cohX += X[o]; cohY += Y[o]; mates++;
              }
            }
          }
        }
        switch (sp.move) {
          case "flock": {
            if (mates) {
              dx = (aliX / mates) * 0.6 + (cohX / mates - x) * 0.01;
              dy = (aliY / mates) * 0.6 + (cohY / mates - y) * 0.01;
            }
            dx += VX[i] * 0.5 + (sp.cx - x) * 0.0004;
            dy += VY[i] * 0.5 + (sp.cy - y) * 0.0004;
            break;
          }
          case "orbit": {
            OFF[i] += sp.speed * 0.006 * ORBD[i];
            dx = (sp.cx + Math.cos(OFF[i]) * ORBR[i] - x) * 0.03;
            dy = (sp.cy + Math.sin(OFF[i]) * ORBR[i] - y) * 0.03;
            break;
          }
          case "lissajous": {
            const tau = frameNo * 0.004 * sp.speed + OFF[i];
            dx = (sp.cx + Math.sin(sp.lisA * tau + sp.lisPhase) * W * 0.18 - x) * 0.02;
            dy = (sp.cy + Math.sin(sp.lisB * tau) * H * 0.18 - y) * 0.02;
            break;
          }
          case "colony": {
            dx = (sp.cx + Math.cos(OFF[i]) * ORBR[i] * 0.5 - x) * 0.004;
            dy = (sp.cy + Math.sin(OFF[i]) * ORBR[i] * 0.5 - y) * 0.004;
            dx += (bgFlow(SEED[i], frameNo * 0.01) - 0.5) * sp.speed;
            dy += (bgFlow(SEED[i] + 7, frameNo * 0.01) - 0.5) * sp.speed;
            break;
          }
          default: { // drift
            const head = bgFlow(SEED[i], frameNo * 0.004) * Math.PI * 4;
            dx = Math.cos(head) * sp.speed;
            dy = Math.sin(head) * sp.speed;
          }
        }
        dx += sepX * 0.9;
        dy += sepY * 0.9;
        const mag = Math.sqrt(dx * dx + dy * dy);
        const lim = sp.speed * 1.4;
        if (mag > lim) { dx = (dx / mag) * lim; dy = (dy / mag) * lim; }
        VX[i] += (dx - VX[i]) * 0.06;
        VY[i] += (dy - VY[i]) * 0.06;
        let nx = x + VX[i], ny = y + VY[i];
        if (nx < -30) nx += W + 60; else if (nx > W + 30) nx -= W + 60;
        if (ny < -30) ny += H + 60; else if (ny > H + 30) ny -= H + 60;
        X[i] = nx; Y[i] = ny;
        // A rod or a flagellate points where it swims; a round or radial
        // body turns slowly on its own.
        if (sp.turns) {
          ANG[i] += SPIN[i];
        } else if (VX[i] * VX[i] + VY[i] * VY[i] > 0.0025) {
          let d = Math.atan2(VY[i], VX[i]) - ANG[i];
          d = Math.atan2(Math.sin(d), Math.cos(d));
          ANG[i] += d * 0.08;
        }
        if (sp.trail !== "none" && frameNo % 5 === 0) {
          const h = i * HL + HH[i];
          HX[h] = nx; HY[h] = ny;
          HH[i] = (HH[i] + 1) % HL;
          if (HN[i] < HL) HN[i]++;
        }
        AGE[i]++;
        if (BORN[i] < 1) BORN[i] = Math.min(1, BORN[i] + 0.02);
        if (DYING[i] > 0) DYING[i] += 0.012;
        else if (AGE[i] > LIFE[i] && n >= cap * 0.8) DYING[i] = 0.012;
        if (DIV[i] >= 0) {
          DIV[i] += 1 / 75;
          if (DIV[i] >= 1) {
            DIV[i] = -1;
            AGE[i] = 0;
            NEXT[i] = sp.divideAfter * p.random(0.7, 1.3);
            if (n < cap) {
              const ax = Math.cos(ANG[i]) * sp.size * 1.1, ay = Math.sin(ANG[i]) * sp.size * 1.1;
              const kid = n++;
              place(kid, SP[i], X[i] + ax, Y[i] + ay);
              ANG[kid] = ANG[i]; BORN[kid] = 1; VX[kid] = VX[i]; VY[kid] = VY[i];
              X[i] -= ax; Y[i] -= ay;
            }
          }
        } else if (DYING[i] === 0 && AGE[i] > NEXT[i] && n < cap) {
          DIV[i] = 0;
        }
      }
      // The dead leave by swapping the last slot into theirs.
      for (let i = n - 1; i >= 0; i--) {
        if (DYING[i] >= 1) {
          n--;
          if (i !== n) copySlot(i, n);
        }
      }
      for (let i = 0; i < nMotes; i++) {
        mx[i] += (bgFlow(ms[i], frameNo * 0.003) - 0.5) * 0.5 * mz[i];
        my[i] += (bgFlow(ms[i] + 5, frameNo * 0.003) - 0.5) * 0.5 * mz[i] - 0.05;
        if (my[i] < -3) my[i] = H + 3;
        if (mx[i] < -3) mx[i] = W + 3; else if (mx[i] > W + 3) mx[i] = -3;
      }
    };

    return {
      background: "clear",
      seeded: true,
      init() {
        W = p.width; H = p.height;
        const seed = bgArtSeedOf(ctx.seedText);
        const strains = bgArtStrains(seed, bgArtStrainCount(seed));
        const used = new Set();
        strains.forEach((strain, i) => {
          const gene = bgArtGenome(strain);
          let lisA = gene.int(37, 4, 1), lisB = gene.int(41, 4, 1);
          if (lisA === lisB) lisB = (lisB % 4) + 1;
          // Every species in one ecosystem has its own body: a form already
          // taken passes to the next one in the list.
          let form = gene.pick(FORMS, 7, 31);
          while (used.has(form)) form = FORMS[(FORMS.indexOf(form) + 1) % FORMS.length];
          used.add(form);
          const hue = ctx.baseHue + gene.span(5, 61, -60, 60);
          species.push({
            strain,
            name: bgArtSpeciesName(strain),
            form,
            turns: form === "coccus" || form === "diatom" || form === "amoeba",
            move: gene.pick(MOVES, 7),
            glow: gene.pick(GLOWS, 17),
            trail: gene.pick(TRAILS, 13, 53),
            hue,
            speed: gene.span(19, 101, 0.3, 0.85),
            size: gene.span(29, 97, 6, 12),
            sides: gene.int(23, 4, 5),
            divideAfter: gene.span(31, 83, 600, 1500),
            lisA, lisB, lisPhase: gene.span(43, 50, 0, Math.PI * 2),
            seed: 100 + i * 37 + (gene.sum % 50),
            cx: W / 2, cy: H / 2,
            cFill: bgHsla(hue, 62, fillL, 0.28),
            cStroke: bgHsla(hue, 70, ink, 0.8),
            cCore: bgHsla(hue + 12, 72, ink, 0.75),
            glowSprite: null,
            glowHalf: 0,
            cWake: bgHsla(hue, 60, ink, 0.18),
            cDots: bgHsla(hue, 60, ink, 0.3),
          });
          // The glow, painted at the size it is drawn (five body radii).
          const sp = species[species.length - 1];
          const gs = Math.round(sp.size * 5);
          sp.glowSprite = bgGlowSprite(hue, 70, ctx.dark ? 66 : 55, ctx.dark ? 0.55 : 0.3, gs);
          sp.glowHalf = gs / 2;
          sp.atlas = atlasOf(sp);
        });
        cap = bgClamp(Math.round((W * H) / 22000 * ctx.density), 14, 80);
        const f = () => new Float32Array(cap);
        X = f(); Y = f(); VX = f(); VY = f(); ANG = f(); SPIN = f(); AGE = f(); NEXT = f();
        LIFE = f(); DIV = f(); BORN = f(); DYING = f(); SEED = f(); OFF = f(); ORBR = f();
        ORBD = new Float32Array(cap); SP = new Uint8Array(cap);
        HN = new Uint8Array(cap); HH = new Uint8Array(cap); AQ = new Uint8Array(cap);
        HX = new Float32Array(cap * HL); HY = new Float32Array(cap * HL);
        FIELDS = [X, Y, VX, VY, ANG, SPIN, AGE, NEXT, LIFE, DIV, BORN, DYING, SEED, OFF, ORBR, ORBD, SP, HN, HH];
        grid = bgGrid(W, H, CELL, cap);
        n = Math.round(cap * 0.7);
        for (let i = 0; i < n; i++) {
          place(i, i % species.length, p.random(W), p.random(H));
          BORN[i] = 1;
          AGE[i] = p.random(NEXT[i]);
        }
        nMotes = Math.round(40 * ctx.density);
        mx = new Float32Array(nMotes); my = new Float32Array(nMotes);
        mz = new Float32Array(nMotes); ms = new Float32Array(nMotes);
        for (let i = 0; i < nMotes; i++) {
          mx[i] = p.random(W); my[i] = p.random(H); mz[i] = p.random(0.3, 1); ms[i] = p.random(1000);
        }
        moteFill = bgHsla(ctx.baseHue, 30, ctx.dark ? 70 : 50, 0.3);
      },
      // A still frame shows the ecosystem after it has settled, not the
      // scatter it starts from.
      settle() {
        for (let i = 0; i < 90; i++) step();
      },
      frame() {
        step();
        const g = p.drawingContext;
        // Motes in three strengths, one path each.
        g.fillStyle = moteFill;
        for (let band = 0; band < 3; band++) {
          g.globalAlpha = 0.45 + band * 0.25;
          g.beginPath();
          for (let i = band; i < nMotes; i += 3) {
            const sz = 1.4 * mz[i] + 0.4;
            g.rect(mx[i], my[i], sz, sz);
          }
          g.fill();
        }
        g.globalAlpha = 1;
        // Wakes under the bodies: one path per species, one stroke or fill.
        g.lineCap = "round";
        for (let si = 0; si < species.length; si++) {
          const sp = species[si];
          if (sp.trail === "none") continue;
          const wake = sp.trail === "wake";
          g.beginPath();
          for (let i = 0; i < n; i++) {
            const hn = HN[i];
            if (SP[i] !== si || hn < 2) continue;
            const first = (HH[i] - hn + HL) % HL;
            for (let k = 0; k < hn; k++) {
              const h = i * HL + ((first + k) % HL);
              if (wake) {
                if (k === 0) g.moveTo(HX[h], HY[h]);
                else g.lineTo(HX[h], HY[h]);
              } else {
                const sz = 0.6 + (k / HL) * sp.size * 0.7;
                g.rect(HX[h] - sz / 2, HY[h] - sz / 2, sz, sz);
              }
            }
            if (wake) g.lineTo(X[i], Y[i]);
          }
          if (wake) {
            g.strokeStyle = sp.cWake;
            // Thin: a wide stroke was the single most expensive thing in
            // this style to raster (1.4ms of strokes a frame, measured with
            // the strokes switched off).
            g.lineWidth = 1;
            g.stroke();
          } else {
            g.fillStyle = sp.cDots;
            g.fill();
          }
        }
        // Glows: upright sprites (a glow looks the same at any heading, and
        // an upright image is the cheap kind), each at its organism's own
        // strength, pulsing for a pulsing species.
        AQN.fill(0);
        for (let i = 0; i < n; i++) {
          const a = BORN[i] * (1 - Math.min(1, DYING[i]));
          // Opacity in quarters, for batching the bodies below.
          AQ[i] = Math.ceil(a * 4);
          AQN[SP[i] * 5 + AQ[i]]++;
          const sp = species[SP[i]];
          if (sp.glow === "none" || a <= 0.01) continue;
          const pulse = sp.glow === "pulse" ? 0.55 + 0.45 * Math.sin(frameNo * 0.06 + OFF[i]) : 0.8;
          g.globalAlpha = pulse * a;
          if (ctx.dark) g.globalCompositeOperation = "lighter";
          // At its own size and on whole pixels, the plain copy: no
          // resampling and no boxed coordinates.
          g.drawImage(sp.glowSprite, (X[i] - sp.glowHalf) | 0, (Y[i] - sp.glowHalf) | 0);
        }
        g.globalCompositeOperation = "source-over";
        // Bodies: one atlas cell each, at the organism's own strength; a
        // dividing organism is two, a little smaller, pulling apart. On
        // whole pixels: at a fractional place every copy is resampled, which
        // measured twice the cost (1.3ms against 0.6ms for sixty bodies in a
        // CPU canvas), and a body crawling under a pixel a frame shows no
        // step.
        const TAU = Math.PI * 2;
        for (let i = 0; i < n; i++) {
          const sp = species[SP[i]];
          const at = sp.atlas;
          const a = BORN[i] * (1 - Math.min(1, DYING[i]));
          if (a <= 0.01) continue;
          g.globalAlpha = a;
          let turn = ANG[i] % TAU;
          if (turn < 0) turn += TAU;
          const col = Math.round((turn / TAU) * at.angles) % at.angles;
          let row = 0;
          if (at.phases > 1) {
            let ph = (frameNo * (PHASE_RATE[sp.form] || 0) + OFF[i]) % TAU;
            if (ph < 0) ph += TAU;
            row = Math.floor((ph / TAU) * at.phases) % at.phases;
          }
          const sx = col * at.cell, sy = row * at.cell, cell = at.cell;
          if (DIV[i] >= 0) {
            const c = Math.cos(ANG[i]), sn = Math.sin(ANG[i]);
            const d = DIV[i] * sp.size * 1.1;
            const k = 1 - 0.18 * Math.sin(DIV[i] * Math.PI);
            const w = cell * k, hw = w / 2;
            g.drawImage(at.img, sx, sy, cell, cell, X[i] - c * d - hw, Y[i] - sn * d - hw, w, w);
            g.drawImage(at.img, sx, sy, cell, cell, X[i] + c * d - hw, Y[i] + sn * d - hw, w, w);
          } else {
            g.drawImage(at.img, sx, sy, cell, cell, (X[i] - at.half) | 0, (Y[i] - at.half) | 0, cell, cell);
          }
        }
        // Flagella: per species and per quarter of opacity, one path each.
        g.lineWidth = 1;
        for (let si = 0; si < species.length; si++) {
          const sp = species[si];
          if (sp.form !== "vibrio" && sp.form !== "flagellate") continue;
          g.strokeStyle = sp.cStroke;
          for (let q = 1; q <= 4; q++) {
            if (!AQN[si * 5 + q]) continue;
            g.globalAlpha = q / 4;
            g.beginPath();
            bodies(g, si, q, 2);
            g.stroke();
          }
        }
        g.globalAlpha = 1;
      },
    };
  },

  // A mycelium grown from a name, the second helixlabs-style ecosystem:
  // each colony is a strain of the display name, and its hue, how often it
  // branches, how wide the branches split, how much the threads curl, how
  // fast they grow, how thick they are and whether it sets nodes where it
  // forks are all read from the strain's letters. Growth is drawn once and
  // kept (only the new segment of each thread is drawn a frame), so a frame
  // costs the growing tips and nothing else. Tips live in typed arrays, and
  // each frame's new segments go into preallocated buffers, one per colony
  // and thickness, stroked as one path each.
  //
  // **Where it starts and how it ends** (the owner: "the start points need
  // to be more organic and also the transition between them disappearing
  // and reappearing needs to be smoother and maybe faded"). A colony's
  // spores are scattered with a minimum distance between them (never a grid,
  // never a ring), each sends out two to five threads at uneven angles from
  // a few pixels apart, and each thread waits its own moment to start, so a
  // colony wakes up rather than bursting out of a point. A generation's
  // first strokes are laid down faint and strengthen over two seconds, so
  // every thread fades in from its spore. And a generation does not vanish:
  // the next one germinates on a second canvas (`twin`, from the runtime)
  // while the old canvas fades out over about two seconds by its own
  // opacity, which the compositor does for free; the old one is cleared only
  // once it is invisible. The fade used to be `destination-out` over the
  // whole window for 75 frames, then a hard clear and every colony at once.
  mycelium(p, ctx) {
    const FORMS = ["hyphae", "rhizome", "lace"];
    const WIDTHS = [0.55, 1, 1.7];
    const FADE_IN = 60; // frames over which a generation's strokes reach full strength
    const FADE_OUT = 56; // frames over which the old generation's canvas fades
    let W = 0, H = 0, maxTips = 0, n = 0;
    let TX, TY, TA, TW, TL, TG, TC, TD;
    let SEG, SEGN, NODE, NODEC, nNodes = 0;
    const colonies = [];
    let phase = "grow", phaseFrame = 0, growFrame = 0;
    let tipFill = "";
    const ink = ctx.dark ? 68 : 40;
    // The two canvases a moving mycelium alternates between, and the
    // opacity strings a fade steps through (built once: a fade is a string
    // assignment a frame, not a string built a frame).
    let layers = null, cur = 0, fading = -1, fadeFrame = 0;
    const FADE_STEPS = 24;
    const fadeOpacity = [];
    for (let k = 0; k <= FADE_STEPS; k++) {
      fadeOpacity.push(`calc(var(--bg-art-opacity, 0.9) * ${(k / FADE_STEPS).toFixed(3)})`);
    }
    // The spores placed this generation, x and y (a buffer made once).
    let spores = null;

    const germinate = () => {
      n = 0;
      growFrame = 0;
      let ns = 0;
      const gap = Math.min(W, H) * 0.2;
      for (let ci = 0; ci < colonies.length; ci++) {
        const col = colonies[ci];
        const count = 1 + (p.random() < 0.6 ? 1 : 0) + (p.random() < 0.2 ? 1 : 0);
        for (let s = 0; s < count && ns < spores.length / 2; s++) {
          // The first place far enough from every spore so far, from a
          // dozen tries; the last try stands if none is (a crowded window
          // still gets its colonies).
          let x = 0, y = 0;
          for (let tries = 0; tries < 12; tries++) {
            x = p.random(W * 0.05, W * 0.95);
            y = p.random(H * 0.07, H * 0.93);
            let clear = true;
            for (let k = 0; k < ns; k++) {
              const dx = spores[k * 2] - x, dy = spores[k * 2 + 1] - y;
              if (dx * dx + dy * dy < gap * gap) { clear = false; break; }
            }
            if (clear) break;
          }
          spores[ns * 2] = x; spores[ns * 2 + 1] = y; ns++;
          const threads = 2 + Math.floor(p.random(4));
          const turn = p.random(Math.PI * 2);
          for (let k = 0; k < threads && n < maxTips; k++) {
            TX[n] = x + p.random(-7, 7); TY[n] = y + p.random(-7, 7);
            TA[n] = turn + ((k + p.random(-0.38, 0.38)) / threads) * Math.PI * 2;
            TW[n] = col.weight * p.random(0.75, 1.1);
            TL[n] = p.random(220, 440); TG[n] = 0; TC[n] = ci;
            // Each thread starts in its own time, the first at once.
            TD[n] = k === 0 ? 0 : Math.floor(p.random(8, 90));
            n++;
          }
        }
      }
      phase = "grow";
      phaseFrame = 0;
    };

    const addNode = (ci, x, y, r) => {
      if (nNodes >= maxTips * 2) return;
      NODE[nNodes * 3] = x; NODE[nNodes * 3 + 1] = y; NODE[nNodes * 3 + 2] = r;
      NODEC[nNodes++] = ci;
    };

    const grow = (g) => {
      SEGN.fill(0);
      nNodes = 0;
      growFrame++;
      const count = n;
      for (let i = 0; i < count; i++) {
        if (TD[i] > 0) { TD[i]--; continue; }
        const ci = TC[i], col = colonies[ci];
        TA[i] += (bgFlow(TX[i] * 0.008 + col.seed, TY[i] * 0.008) - 0.5) * col.curl * 2.2;
        const nx = TX[i] + Math.cos(TA[i]) * col.step;
        const ny = TY[i] + Math.sin(TA[i]) * col.step;
        const cls = TW[i] > 1.4 ? 2 : TW[i] > 0.8 ? 1 : 0;
        const b = ci * 3 + cls;
        const o = (b * maxTips + SEGN[b]) * 4;
        SEG[o] = TX[i]; SEG[o + 1] = TY[i]; SEG[o + 2] = nx; SEG[o + 3] = ny;
        SEGN[b]++;
        TX[i] = nx; TY[i] = ny;
        TL[i]--;
        TW[i] *= 0.9985;
        const out = nx < -10 || nx > W + 10 || ny < -10 || ny > H + 10;
        if (TL[i] <= 0 || out) {
          if (!out && col.form !== "rhizome") addNode(ci, nx, ny, TW[i] * 1.3);
          TL[i] = -1; // marked; removed below
          continue;
        }
        if (n < maxTips && TG[i] < 7 && p.random() < col.branch) {
          const side = p.random() < 0.5 ? -1 : 1;
          TX[n] = nx; TY[n] = ny; TA[n] = TA[i] + side * col.angle * p.random(0.7, 1.3);
          TW[n] = TW[i] * 0.78; TL[n] = TL[i] * p.random(0.55, 0.85);
          TG[n] = TG[i] + 1; TC[n] = ci; TD[n] = 0;
          n++;
          if (col.form === "lace") addNode(ci, nx, ny, TW[i] * 1.6);
        }
      }
      for (let i = n - 1; i >= 0; i--) {
        if (TL[i] >= 0) continue;
        n--;
        if (i !== n) {
          TX[i] = TX[n]; TY[i] = TY[n]; TA[i] = TA[n]; TW[i] = TW[n];
          TL[i] = TL[n]; TG[i] = TG[n]; TC[i] = TC[n]; TD[i] = TD[n];
        }
      }
      // The fade in: a generation's first strokes are faint and the later
      // ones full, so each thread strengthens away from its spore.
      g.globalAlpha = growFrame < FADE_IN ? 0.15 + 0.85 * (growFrame / FADE_IN) : 1;
      g.lineCap = "round";
      for (let ci = 0; ci < colonies.length; ci++) {
        const col = colonies[ci];
        for (let cls = 0; cls < 3; cls++) {
          const b = ci * 3 + cls;
          const segs = SEGN[b];
          if (!segs) continue;
          g.strokeStyle = col.stroke;
          g.lineWidth = WIDTHS[cls] * col.weight;
          g.beginPath();
          for (let k = 0; k < segs; k++) {
            const o = (b * maxTips + k) * 4;
            g.moveTo(SEG[o], SEG[o + 1]);
            g.lineTo(SEG[o + 2], SEG[o + 3]);
          }
          g.stroke();
        }
      }
      for (let k = 0; k < nNodes; k++) {
        g.fillStyle = colonies[NODEC[k]].node;
        g.beginPath();
        g.arc(NODE[k * 3], NODE[k * 3 + 1], Math.max(1.2, NODE[k * 3 + 2]), 0, Math.PI * 2);
        g.fill();
      }
      g.globalAlpha = 1;
    };

    return {
      background: "keep",
      seeded: true,
      twin: true,
      darkCap: 0.1,
      lightFloor: 0.3,
      init() {
        W = p.width; H = p.height;
        const seed = bgArtSeedOf(ctx.seedText);
        const strains = bgArtStrains(seed, bgArtStrainCount(seed));
        strains.forEach((strain, i) => {
          const gene = bgArtGenome(strain);
          const form = gene.pick(FORMS, 7, 31);
          const hue = ctx.baseHue + gene.span(5, 61, -55, 55);
          colonies.push({
            index: i, strain, form, hue,
            branch: gene.span(19, 101, 0.025, 0.055) * (form === "rhizome" ? 0.6 : 1),
            angle: gene.span(29, 97, 0.35, 0.95),
            curl: gene.span(31, 83, 0.03, 0.12),
            step: gene.span(11, 71, 0.8, 1.4),
            weight: gene.span(13, 59, 0.8, 1.5) * (form === "rhizome" ? 1.35 : 1),
            seed: (gene.sum % 997) / 10,
            stroke: bgHsla(hue, 58, ink, ctx.dark ? 0.55 : 0.5),
            node: bgHsla(hue, 65, ink, ctx.dark ? 0.6 : 0.55),
          });
        });
        tipFill = bgHsla(ctx.baseHue, 70, ctx.dark ? 80 : 45, 0.35);
        maxTips = bgClamp(Math.round(180 * ctx.density), 70, 240);
        TX = new Float32Array(maxTips); TY = new Float32Array(maxTips);
        TA = new Float32Array(maxTips); TW = new Float32Array(maxTips);
        TL = new Float32Array(maxTips); TG = new Uint8Array(maxTips); TC = new Uint8Array(maxTips);
        TD = new Uint8Array(maxTips);
        SEG = new Float32Array(colonies.length * 3 * maxTips * 4);
        SEGN = new Int32Array(colonies.length * 3);
        NODE = new Float32Array(maxTips * 2 * 3);
        NODEC = new Uint8Array(maxTips * 2);
        spores = new Float32Array(colonies.length * 3 * 2);
        layers = [{ canvas: p.canvas, g: p.drawingContext, clear: () => p.clear() }];
        if (p.twin) layers.push(p.twin);
        p.clear();
        germinate();
      },
      settle() {
        const g = p.drawingContext;
        for (let i = 0; i < 420 && n; i++) grow(g);
      },
      frame() {
        const layer = layers[cur];
        const g = layer.g;
        phaseFrame++;
        if (fading >= 0) {
          // The old generation fades by its canvas's opacity, then is
          // cleared and put back to full strength, empty, for next time.
          fadeFrame++;
          const old = layers[fading];
          const k = Math.max(0, FADE_STEPS - Math.round((fadeFrame / FADE_OUT) * FADE_STEPS));
          old.canvas.style.opacity = fadeOpacity[k];
          if (fadeFrame >= FADE_OUT) {
            old.clear();
            old.canvas.style.opacity = "";
            fading = -1;
          }
        }
        if (phase === "grow") {
          grow(g);
          // Growing tips glow faintly: the living front of the colony.
          if (ctx.dark) g.globalCompositeOperation = "lighter";
          g.fillStyle = tipFill;
          // Whole pixels: every fractional argument to a canvas call is
          // boxed, an allocation each, and a tip needs no finer place.
          for (let i = 0; i < n; i++) if (!TD[i]) g.fillRect((TX[i] - 1) | 0, (TY[i] - 1) | 0, 2, 2);
          g.globalCompositeOperation = "source-over";
          if (!n || phaseFrame > 1500) { phase = "rest"; phaseFrame = 0; }
        } else if (phase === "rest" && phaseFrame > 240 && fading < 0) {
          if (layers.length > 1) {
            // Hand over: this generation fades while the next grows on the
            // other canvas.
            fading = cur;
            fadeFrame = 0;
            cur = 1 - cur;
            germinate();
          } else {
            // No second canvas (a moving mycelium always has one): clear
            // and start again.
            layer.clear();
            germinate();
          }
        }
      },
    };
  },

  // **The light end** (Brief 95, INBOX 858: "varied from simple, to complex,
  // heavy, and light"). Four styles drawn for cost first: each is a handful
  // of canvas calls a frame into a small backing store, at a low frame rate,
  // with every colour and sprite built in `init`. Their measured frame costs
  // are in `BG_ART_COST` below.
  //
  // Dusk: a sky graded from the accent's deep to a pale horizon, and a glow
  // that breathes and drifts along the horizon. A tenth of the pixel density
  // (144 by 90 backing pixels at 1440x900) and ten frames a second: the
  // compositor's upscale is the softness a sky wants, and a frame is one
  // stretched one-pixel-wide strip and one sprite copy.
  dusk(p, ctx) {
    let sky = null, glow = null, W = 0, H = 0, secs = 0;
    return {
      background: "keep",
      pixelDensity: 0.1,
      // The glow crosses 4 pixels a draw at 5 frames a second, 0.4 of this
      // canvas's own: the compositor's upscale shows no step (INBOX 1436).
      fps: 5,
      darkCap: 0.05,
      lightFloor: 0.55,
      init() {
        W = p.width; H = p.height;
        const h = ctx.baseHue;
        sky = bgSprite(1, 64, (g) => {
          const grad = g.createLinearGradient(0, 0, 0, 64);
          grad.addColorStop(0, bgHsla(h + 20, ctx.dark ? 45 : 50, ctx.dark ? 9 : 93, 1));
          grad.addColorStop(0.6, bgHsla(h, ctx.dark ? 40 : 55, ctx.dark ? 16 : 90, 1));
          grad.addColorStop(1, bgHsla(h - 30, ctx.dark ? 50 : 65, ctx.dark ? 24 : 86, 1));
          g.fillStyle = grad;
          g.fillRect(0, 0, 1, 64);
        });
        glow = bgSprite(64, 64, (g) => {
          const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
          grad.addColorStop(0, bgHsla(h - 40, 70, ctx.dark ? 40 : 75, ctx.dark ? 0.6 : 0.7));
          grad.addColorStop(1, bgHsla(h - 40, 70, ctx.dark ? 40 : 75, 0));
          g.fillStyle = grad;
          g.fillRect(0, 0, 64, 64);
        });
      },
      frame() {
        const g = p.drawingContext;
        secs += 1 / Math.min(5, bgArtFrameRate());
        g.drawImage(sky, 0, 0, W + 20, H + 20);
        const r = Math.max(W, H) * (0.35 + 0.05 * Math.sin(secs * 0.3)) * (0.7 + 0.3 * ctx.density);
        const x = W * (0.5 + 0.3 * Math.sin(secs * 0.05));
        g.drawImage(glow, x - r, H * 0.95 - r, r * 2, r * 2);
      },
    };
  },

  // Ripples: rings widening and fading from a few points, as rain on still
  // water seen from above. At most eight at once, each three strokes of one
  // circle; half the pixel density, twenty frames a second at most.
  ripples(p, ctx) {
    const N = 8;
    const rx = new Float32Array(N), ry = new Float32Array(N), age = new Float32Array(N), life = new Float32Array(N);
    let ink = "", W = 0, H = 0, rand = Math.random;
    const respawn = (i) => {
      rx[i] = rand() * W; ry[i] = rand() * H;
      life[i] = 5 + rand() * 4; age[i] = -rand() * 3;
    };
    return {
      background: "clear",
      pixelDensity: 0.5,
      fps: 20,
      darkCap: 0.1,
      lightFloor: 0.35,
      init() {
        W = p.width; H = p.height;
        rand = bgRandom(Math.round(ctx.baseHue * 7) + 11);
        ink = bgHsla(ctx.baseHue, 60, ctx.dark ? 60 : 45, 1);
        for (let i = 0; i < N; i++) { respawn(i); age[i] = rand() * life[i]; }
      },
      frame() {
        const g = p.drawingContext;
        const n = Math.max(3, Math.round(N * ctx.density));
        const step = 1 / Math.min(20, bgArtFrameRate());
        g.strokeStyle = ink;
        g.lineWidth = 1.5;
        for (let i = 0; i < n; i++) {
          age[i] += step;
          if (age[i] > life[i]) respawn(i);
          if (age[i] < 0) continue;
          const k = age[i] / life[i];
          for (let ring = 0; ring < 3; ring++) {
            const r = (k * 180) - ring * 22;
            if (r <= 2) continue;
            g.globalAlpha = (1 - k) * (0.5 - ring * 0.13);
            g.beginPath();
            g.arc(rx[i], ry[i], r, 0, Math.PI * 2);
            g.stroke();
          }
        }
        g.globalAlpha = 1;
      },
    };
  },

  // Fireflies: soft lights wandering on a slow noise field, each pulsing on
  // its own period. One glow sprite made once, copied per light with a
  // `globalAlpha`; positions in typed arrays.
  fireflies(p, ctx) {
    const MAX = 48;
    const fx = new Float32Array(MAX), fy = new Float32Array(MAX), fp = new Float32Array(MAX), fs = new Float32Array(MAX);
    let sprite = null, W = 0, H = 0, n = 0, secs = 0;
    return {
      background: "clear",
      pixelDensity: 0.5,
      // A light moves 0.5 to 1.1 pixels a frame at 20 (INBOX 1436): 15 a
      // second, each draw carrying a third more motion.
      fps: 15,
      darkCap: 0.12,
      lightFloor: 0.3,
      init() {
        W = p.width; H = p.height;
        const rand = bgRandom(Math.round(ctx.baseHue * 13) + 5);
        n = Math.round(16 + 32 * ctx.density);
        for (let i = 0; i < n; i++) {
          fx[i] = rand() * W; fy[i] = rand() * H; fp[i] = rand() * 6.28; fs[i] = 0.6 + rand() * 0.8;
        }
        const hue = ctx.baseHue + 40;
        sprite = bgSprite(32, 32, (g) => {
          const grad = g.createRadialGradient(16, 16, 0, 16, 16, 16);
          grad.addColorStop(0, bgHsla(hue, 90, ctx.dark ? 75 : 45, 1));
          grad.addColorStop(0.25, bgHsla(hue, 90, ctx.dark ? 60 : 50, 0.6));
          grad.addColorStop(1, bgHsla(hue, 90, ctx.dark ? 50 : 55, 0));
          g.fillStyle = grad;
          g.fillRect(0, 0, 32, 32);
        });
      },
      frame() {
        const g = p.drawingContext;
        secs += 1 / Math.min(15, bgArtFrameRate());
        const k = Math.min(20, bgArtFrameRate()) / Math.min(15, bgArtFrameRate());
        for (let i = 0; i < n; i++) {
          const a = bgFlow(i * 0.37, secs * 0.05) * 6.28;
          fx[i] += Math.cos(a) * fs[i] * 0.8 * k;
          fy[i] += (Math.sin(a) * fs[i] * 0.8 - 0.1) * k;
          if (fx[i] < -20) fx[i] += W + 40; else if (fx[i] > W + 20) fx[i] -= W + 40;
          if (fy[i] < -20) fy[i] += H + 40; else if (fy[i] > H + 20) fy[i] -= H + 40;
          g.globalAlpha = 0.25 + 0.75 * Math.max(0, Math.sin(secs * fs[i] + fp[i]));
          const s = 10 + fs[i] * 10;
          g.drawImage(sprite, fx[i] - s, fy[i] - s, s * 2, s * 2);
        }
        g.globalAlpha = 1;
      },
    };
  },

  // Rain: fine slanted streaks at two depths, the far ones slower and
  // fainter. Every streak of a depth is one segment in one path, stroked
  // once: two strokes a frame however many drops.
  rain(p, ctx) {
    const MAX = 220;
    const dx = new Float32Array(MAX), dy = new Float32Array(MAX), dv = new Float32Array(MAX);
    const inks = [];
    let W = 0, H = 0, n = 0;
    return {
      background: "clear",
      pixelDensity: 0.5,
      fps: 30,
      darkCap: 0.1,
      lightFloor: 0.35,
      init() {
        W = p.width; H = p.height;
        const rand = bgRandom(Math.round(ctx.baseHue * 17) + 3);
        n = Math.round(80 + 140 * ctx.density);
        for (let i = 0; i < n; i++) {
          dx[i] = rand() * W; dy[i] = rand() * H; dv[i] = i % 2 ? 9 + rand() * 4 : 5 + rand() * 3;
        }
        inks.length = 0;
        inks.push(bgHsla(ctx.baseHue, 40, ctx.dark ? 60 : 45, ctx.dark ? 0.3 : 0.28));
        inks.push(bgHsla(ctx.baseHue, 50, ctx.dark ? 70 : 40, ctx.dark ? 0.55 : 0.45));
      },
      frame() {
        const g = p.drawingContext;
        const step = 30 / Math.min(30, bgArtFrameRate());
        g.lineWidth = 1.2;
        for (let depth = 0; depth < 2; depth++) {
          g.strokeStyle = inks[depth];
          g.beginPath();
          for (let i = depth; i < n; i += 2) {
            dy[i] += dv[i] * step;
            dx[i] += dv[i] * step * 0.18;
            if (dy[i] > H + 20) { dy[i] = -20; dx[i] = (dx[i] * 7.31) % W; }
            if (dx[i] > W) dx[i] -= W;
            const len = dv[i] * 2.2;
            g.moveTo(dx[i], dy[i]);
            g.lineTo(dx[i] - len * 0.18, dy[i] - len);
          }
          g.stroke();
        }
      },
    };
  },

  // Wander: pen strokes that walk. A few strokes (the accent's hue and two
  // offsets from it) each take a handful of small random steps a frame, each
  // frame's steps one path onto a canvas that is never cleared, so the drawing
  // grows as it goes. A stroke that reaches the window's edge turns back. Old
  // marks go by a faint clear every few seconds (`destination-out`, one
  // fillRect), not a redraw: a frame is a few line segments and nothing
  // else. The pen keeps a little of its last heading, so it travels instead of
  // shivering in place. Still: a finished drawing (`settle` walks it ahead).
  wander(p, ctx) {
    const MAX = 6, STEPS = 7, LIFE = 2600;
    const px = new Float32Array(MAX), py = new Float32Array(MAX);
    const vx = new Float32Array(MAX), vy = new Float32Array(MAX), age = new Int32Array(MAX);
    const inks = [];
    let W = 0, H = 0, n = 0, rand = Math.random, fadeEvery = 80;
    const respawn = (i) => {
      px[i] = W * (0.1 + 0.8 * rand()); py[i] = H * (0.1 + 0.8 * rand());
      vx[i] = 0; vy[i] = 0; age[i] = 0;
    };
    // One frame's steps for every stroke: a path per stroke, stroked once.
    const walk = (g) => {
      g.lineWidth = 2;
      for (let i = 0; i < n; i++) {
        g.strokeStyle = inks[i % inks.length];
        g.beginPath();
        g.moveTo(px[i], py[i]);
        for (let s = 0; s < STEPS; s++) {
          vx[i] = vx[i] * 0.82 + (rand() - 0.5) * 3.2;
          vy[i] = vy[i] * 0.82 + (rand() - 0.5) * 3.2;
          vx[i] = bgTurnBack(px[i], vx[i], 0, W);
          vy[i] = bgTurnBack(py[i], vy[i], 0, H);
          px[i] += vx[i]; py[i] += vy[i];
          g.lineTo(px[i], py[i]);
        }
        g.stroke();
        if (++age[i] > LIFE) respawn(i);
      }
    };
    return {
      background: "keep",
      pixelDensity: 0.5,
      fps: 20,
      darkCap: 0.14,
      lightFloor: 0.3,
      init() {
        W = p.width; H = p.height;
        rand = bgRandom(Math.round(ctx.baseHue * 19) + 23);
        n = Math.max(3, Math.round(MAX * (0.5 + 0.5 * ctx.density)));
        inks.length = 0;
        for (const off of [0, 40, -40]) inks.push(bgHsla(ctx.baseHue + off, ctx.dark ? 70 : 62, ctx.dark ? 66 : 42, ctx.dark ? 0.7 : 0.6));
        for (let i = 0; i < n; i++) respawn(i);
        fadeEvery = Math.round(Math.min(20, bgArtFrameRate()) * 4);
      },
      settle() {
        const g = p.drawingContext;
        for (let i = 0; i < 70; i++) walk(g);
      },
      frame() {
        const g = p.drawingContext;
        walk(g);
        // Every few seconds the drawing loses a tenth of its ink.
        if (p.frameCount % fadeEvery === 0) {
          g.globalCompositeOperation = "destination-out";
          g.globalAlpha = 0.1;
          g.fillRect(0, 0, W, H);
          g.globalAlpha = 1;
          g.globalCompositeOperation = "source-over";
        }
      },
    };
  },

  // Drift: value noise as slow weather. Three octaves of hashed-lattice noise
  // (`bgFbmRow`) mapped through a table of colours between a dark and a light
  // tone of the accent forty degrees apart, written into one reused
  // ImageData at an eighth of the window a side, and put on a canvas the
  // compositor stretches (never `drawImage`). The field slides slowly across
  // the lattice; only a third of the rows are recomputed a frame, at twelve
  // frames a second, so the whole picture is refreshed four times a second.
  drift(p, ctx) {
    const LUT = new Uint32Array(256);
    let img = null, px = null, row = null, lat = null, bw = 0, bh = 0, ox = 0, oy = 0, phase = 0;
    return {
      background: "keep",
      pixelDensity: 0.125,
      fps: 12,
      darkCap: 0.06,
      lightFloor: 0.6,
      init() {
        const g = p.drawingContext;
        bw = p.canvas.width; bh = p.canvas.height;
        img = g.createImageData(bw, bh);
        px = new Uint32Array(img.data.buffer);
        const seed = Math.round(ctx.baseHue * 31) + 7;
        lat = bgLattice(seed);
        row = new Uint8Array(bw);
        ox = (seed % 97) * 0.7; oy = (seed % 53) * 0.9;
        // The tones: dark mode adds light (deep to glowing), light mode lays ink
        // (pale wash to a mid tone), both capped by the runtime's luminance rules.
        const lo = bgHslToRgb(ctx.baseHue, ctx.dark ? 50 : 55, ctx.dark ? 9 : 80);
        const hi = bgHslToRgb(ctx.baseHue + 40, ctx.dark ? 60 : 62, ctx.dark ? 30 : 64);
        for (let i = 0; i < 256; i++) {
          const k = i / 255;
          LUT[i] = (255 << 24) | ((lo[2] + (hi[2] - lo[2]) * k) << 16) | ((lo[1] + (hi[1] - lo[1]) * k) << 8) | (lo[0] + (hi[0] - lo[0]) * k);
        }
      },
      settle() {
        for (phase = 0; phase < 3; phase++) this.rows();
      },
      // Rows `phase`, `phase + 3`, ... at the field's present offset.
      rows() {
        const scale = 6 / bw; // about six lattice cells across the window
        for (let y = phase; y < bh; y += 3) {
          bgFbmRow(lat, row, bw, ox, scale, y * scale + oy);
          const at = y * bw;
          for (let x = 0; x < bw; x++) px[at + x] = LUT[row[x]];
        }
      },
      frame() {
        ox += 0.011; oy += 0.004;
        phase = (phase + 1) % 3;
        this.rows();
        p.drawingContext.putImageData(img, 0, 0);
      },
    };
  },
};

// --- the runtime ------------------------------------------------------------------
//
// No p5. The canvas styles were written against a few of p5's calls, and
// `bgArtSurface` gives them those they still use (`width`, `height`,
// `drawingContext`, `random`, `clear`, `pixelDensity`; the noise is
// `bgFlow`) over a plain canvas, with a loop of its own. p5 cost the art its whole per-frame
// machinery (about 1MB of allocations every ten seconds in its draw loop
// alone, measured) and a 1MB script to load for nothing but that.

let bgArtInstance = null; // the running loop, when a canvas style is moving
let bgArtLayer = null; // the element a CSS style or a still frame lives on
let bgArtStillUrl = ""; // the captured still's object URL, revoked when replaced
let bgArtGeneration = 0; // bumped by every run and halt; a late capture from an old run is dropped
let bgArtSeedUsed = null; // the name a seeded style grew from, or null
let bgArtCoverTimer = 0;
let bgArtBlurTimer = 0;
let bgArtResizeTimer = 0;
let bgArtRestart = null; // settings.js's startBgArt, for a resize to call
let bgArtLastInput = 0;
// Pictures on their way out: [element, object URL] pairs kept on screen
// until whatever replaces them is ready, so a theme or accent change swaps
// one picture for the next instead of flashing the bare page between. A
// run that is itself replaced before it is ready hands them on.
let bgArtRetiring = [];
//: `pointerAt`: the last pointer move, press or touch, for the calm rate.
const bgArtPaused = { hidden: false, blurred: false, covered: false, idle: false, pointerAt: performance.now() };

// **A long pause becomes a picture** (INBOX 1436). A pause already stops the
// loop, but the live canvas stays mounted, holding its bitmap. After
// `BG_ART_FREEZE_MS` of pause the canvas is captured through the same path a
// still takes (`bgArtMountStill`: `toBlob`, an object URL, one fixed element
// with the image as its background) and taken out of the page; the element
// keeps the style's state (its typed arrays, its seed, its place in time),
// and a resume puts the canvas back and carries on from there. The kept state
// includes the canvas bitmap, so the page's memory is not freed, only its
// layers and its compositor work; restarting the style from its seed instead
// would free the bitmap but lose the picture the person was looking at.
const BG_ART_FREEZE_MS = 20000;
const BG_FREEZE = { pausedAt: 0, timer: 0, frozen: null }; // pausedAt is performance.now() at pause; frozen is { layer, url } while the picture stands in

// Pure: has this pause lasted long enough, and is it not frozen already?
function bgArtShouldFreeze(pausedAt, now, frozen) {
  return !frozen && pausedAt > 0 && now - pausedAt >= BG_ART_FREEZE_MS;
}

// Idle: no pointer, key or wheel for two minutes. The art holds still
// until the next one, and carries on from where it was.
const BG_ART_IDLE_MS = 120000;

// Thirty frames a second, twenty on a machine that says it is small (four
// cores or fewer, or four gigabytes of memory or less) or on battery. The
// motion is per frame, so at twenty it is two thirds as fast rather than
// jumping to keep up: calmer, and cheaper still.
const BG_ART_SMALL_MACHINE =
  (navigator.hardwareConcurrency || 8) <= 4 || (navigator.deviceMemory || 8) <= 4;
let bgArtOnBattery = false;

//: No pointer for 30 s: nobody is watching it move, so it draws 12 frames a
//: second (a style's own per-frame step scales with the rate it asks for).
//: Keys do not count: typing is not looking.
const BG_ART_CALM_MS = 30000;
const BG_ART_CALM_FPS = 12;

function bgArtCalm() {
  return performance.now() - bgArtPaused.pointerAt > BG_ART_CALM_MS;
}

function bgArtFrameRate() {
  const base = BG_ART_SMALL_MACHINE || bgArtOnBattery ? 20 : 30;
  return bgArtCalm() ? Math.min(base, BG_ART_CALM_FPS) : base;
}

if (typeof navigator.getBattery === "function") {
  navigator.getBattery().then((battery) => {
    const read = () => { bgArtOnBattery = !battery.charging; };
    read();
    battery.addEventListener("chargingchange", read);
  }).catch(() => {});
}

// The surface a canvas style draws on: a canvas at the style's pixel
// density (at most 1: on a 2x screen, a quarter of the pixels, for marks
// that sit behind frosted glass at partial opacity), with the few p5 calls
// the styles use.
function bgArtSurface(pd, pdY = pd, W = window.innerWidth, H = window.innerHeight) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(W * pd));
  canvas.height = Math.max(1, Math.round(H * pdY));
  // `__bgArtCpu` is a measurement hook (scratchpad/ui-sweeps/bgartcost.js):
  // a CPU-backed canvas rasterises on the page's own thread, as it would on
  // a machine without GPU canvas, so the sweep can time that honestly
  // instead of timing a GPU readback. Nothing in the app sets it.
  const g = canvas.getContext("2d", window.__bgArtCpu === true ? { willReadFrequently: true } : undefined);
  g.setTransform(pd, 0, 0, pdY, 0, 0);
  return {
    canvas, width: W, height: H, drawingContext: g, frameCount: 0,
    random: bgRand,
    pixelDensity: () => pd,
    clear() {
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, canvas.width, canvas.height);
      g.setTransform(pd, 0, 0, pdY, 0, 0);
    },
  };
}

function bgArtApplyPause() {
  const b = bgArtPaused;
  const paused = b.hidden || b.blurred || b.covered || b.idle;
  if (bgArtInstance) {
    if (paused && bgArtInstance.isLooping()) bgArtInstance.noLoop();
    else if (!paused && !bgArtInstance.isLooping()) {
      bgArtThaw();
      bgArtInstance.loop();
    }
    if (paused && !BG_FREEZE.pausedAt) {
      BG_FREEZE.pausedAt = performance.now();
      clearTimeout(BG_FREEZE.timer);
      BG_FREEZE.timer = setTimeout(bgArtFreeze, BG_ART_FREEZE_MS);
    } else if (!paused) {
      BG_FREEZE.pausedAt = 0;
      clearTimeout(BG_FREEZE.timer);
    }
  }
  if (bgArtLayer && bgArtLayer.classList.contains("bg-art-layer")) {
    bgArtLayer.classList.toggle("is-paused", paused);
  }
}

// The pause has run its time: swap the canvas for its picture. A timer that
// fires early (a throttled background tab) waits out the rest.
function bgArtFreeze() {
  BG_FREEZE.timer = 0;
  const inst = bgArtInstance;
  if (!inst || BG_FREEZE.frozen || inst.isLooping() || !BG_FREEZE.pausedAt) return;
  const left = BG_ART_FREEZE_MS - (performance.now() - BG_FREEZE.pausedAt);
  if (!bgArtShouldFreeze(BG_FREEZE.pausedAt, performance.now(), false)) {
    BG_FREEZE.timer = setTimeout(bgArtFreeze, Math.max(250, left));
    return;
  }
  const pausedAt = BG_FREEZE.pausedAt;
  inst.capture(bgArtGeneration, (layer, url) => {
    // Resumed, or replaced, while the picture was encoding: it is not needed.
    if (bgArtInstance !== inst || BG_FREEZE.pausedAt !== pausedAt) {
      layer.remove();
      URL.revokeObjectURL(url);
      return;
    }
    // Take the canvas out only once the picture can be drawn, so there is no
    // frame with neither.
    const done = () => {
      if (bgArtInstance !== inst || BG_FREEZE.pausedAt !== pausedAt) {
        layer.remove();
        URL.revokeObjectURL(url);
        return;
      }
      inst.detach();
      BG_FREEZE.frozen = { layer, url };
    };
    const probe = new Image();
    probe.src = url;
    (probe.decode ? probe.decode() : Promise.resolve()).then(done, done);
  });
}

// A resume: the canvas goes back where it was, then the picture goes.
function bgArtThaw() {
  if (!BG_FREEZE.frozen) return;
  const { layer, url } = BG_FREEZE.frozen;
  BG_FREEZE.frozen = null;
  if (bgArtInstance) bgArtInstance.attach();
  layer.remove();
  URL.revokeObjectURL(url);
}

// Is the whole window covered by something opaque? The topmost element at
// the centre, and each of its ancestors short of <body>, is checked for
// covering the full viewport with an opaque background and full opacity.
// A colour this cannot read (a wide-gamut `color()` value, say) counts as
// not opaque, so the art keeps drawing: a wrong "covered" would freeze art
// someone can see, a wrong "not covered" only spends a frame.
function bgArtCovered() {
  const w = window.innerWidth, h = window.innerHeight;
  let el = document.elementFromPoint(w / 2, h / 2);
  while (el && el !== document.body && el !== document.documentElement) {
    const r = el.getBoundingClientRect();
    if (r.left <= 0 && r.top <= 0 && r.right >= w && r.bottom >= h) {
      const cs = getComputedStyle(el);
      const m = /^rgba?\(([^)]*)\)$/.exec(cs.backgroundColor);
      if (m && Number(cs.opacity) >= 1) {
        const parts = m[1].split(/[\s,/]+/).filter(Boolean);
        const alpha = parts.length > 3 ? Number(parts[3]) : 1;
        if (alpha >= 1) return true;
      }
    }
    el = el.parentElement;
  }
  return false;
}

// Every two seconds while something moves: covered? idle?
function bgArtWatch() {
  clearInterval(bgArtCoverTimer);
  bgArtLastInput = performance.now();
  bgArtPaused.hidden = document.hidden;
  bgArtPaused.covered = bgArtCovered();
  bgArtPaused.idle = false;
  bgArtApplyPause();
  bgArtCoverTimer = setInterval(() => {
    const covered = bgArtCovered();
    const idle = performance.now() - bgArtLastInput > BG_ART_IDLE_MS;
    if (covered !== bgArtPaused.covered || idle !== bgArtPaused.idle) {
      bgArtPaused.covered = covered;
      bgArtPaused.idle = idle;
      bgArtApplyPause();
    }
  }, 2000);
}

function bgArtRetire() {
  for (const [el, url] of bgArtRetiring) {
    el.remove();
    if (url) URL.revokeObjectURL(url);
  }
  bgArtRetiring = [];
}

// Stops everything. `handingOver`: a new run is about to start, so the
// current picture is kept on screen (see bgArtRetiring) rather than removed.
function bgArtHalt(handingOver = false) {
  bgArtGeneration++;
  clearInterval(bgArtCoverTimer);
  bgArtCoverTimer = 0;
  clearTimeout(BG_FREEZE.timer);
  BG_FREEZE.timer = 0;
  BG_FREEZE.pausedAt = 0;
  if (BG_FREEZE.frozen) {
    // The picture of a paused canvas stands in for it until what replaces it
    // is ready, as a moving canvas does.
    if (handingOver) bgArtRetiring.push([BG_FREEZE.frozen.layer, BG_FREEZE.frozen.url]);
    else {
      BG_FREEZE.frozen.layer.remove();
      URL.revokeObjectURL(BG_FREEZE.frozen.url);
    }
    BG_FREEZE.frozen = null;
  }
  const canvas = document.getElementById("bg-art-canvas");
  if (bgArtInstance) {
    // Handing over, a moving canvas stops but stays on screen until its
    // replacement is ready: a still frame takes most of a second to encode.
    if (handingOver && canvas) bgArtInstance.noLoop();
    else bgArtInstance.remove();
    bgArtInstance = null;
  }
  for (const el of [canvas, document.getElementById("bg-art-twin")]) {
    if (!el) continue;
    if (handingOver) {
      el.id = "";
      bgArtRetiring.push([el, ""]);
    } else {
      el.remove();
    }
  }
  if (bgArtLayer) bgArtRetiring.push([bgArtLayer, bgArtStillUrl]);
  bgArtLayer = null;
  bgArtStillUrl = "";
  if (!handingOver) bgArtRetire();
  bgArtSeedUsed = null;
}

// The still path, shared by a still frame and a long pause: encode `source`
// (a canvas) to a PNG, and hand `done` a fixed element with that image as its
// background and the image's object URL. `extra` is a CSS background the
// canvas element itself carried (the constellation's nebula), laid under it.
// A capture from a run that has since been replaced is dropped.
function bgArtMountStill(source, gen, extra, done) {
  source.toBlob((blob) => {
    if (gen !== bgArtGeneration || !blob) return;
    const url = URL.createObjectURL(blob);
    const layer = document.createElement("div");
    layer.id = "bg-art-still";
    layer.className = "bg-art-canvas bg-art-still";
    layer.setAttribute("aria-hidden", "true");
    layer.style.backgroundImage = extra ? `url("${url}"), ${extra}` : `url("${url}")`;
    document.body.appendChild(layer);
    done(layer, url);
  }, "image/png");
}

// Mount one style. `o`: { style, dark, accent, density, seedText, still,
// requested (Movement is explicitly "Moving"), restart }.
function bgArtRun(o) {
  bgArtHalt(true);
  const retire = bgArtRetire;
  const gen = bgArtGeneration;
  bgArtRestart = o.restart || null;
  const entry = BG_ART_BUILDERS[o.style] || BG_ART_BUILDERS.aurora;
  const ctx = {
    dark: o.dark,
    baseHue: bgColourHue(o.accent),
    density: o.density,
    seedText: o.seedText,
    still: !!o.still,
  };

  if (entry.dom) {
    const layer = document.createElement("div");
    layer.id = "bg-art-layer";
    layer.className = "bg-art-canvas bg-art-layer";
    layer.setAttribute("aria-hidden", "true");
    bgLumCap = o.dark ? entry.darkCap || 0 : 0;
    bgLumFloor = o.dark ? 0 : entry.lightFloor || 0;
    try {
      entry.mount(layer, ctx, o.still);
    } finally {
      bgLumCap = 0;
      bgLumFloor = 0;
    }
    if (!o.still) layer.classList.add("is-moving");
    if (o.requested) layer.classList.add("is-requested");
    document.body.appendChild(layer);
    bgArtLayer = layer;
    retire();
    if (!o.still) bgArtWatch();
    return;
  }

  // The factory runs before the surface exists (it only defines), so the
  // style can say what pixel density it wants first.
  let surface = null;
  const shim = {};
  const style = entry(shim, ctx);
  const pd = Math.min(style.pixelDensity || 1, 1, window.devicePixelRatio || 1);
  surface = bgArtSurface(pd, Math.min(style.pixelDensityY || pd, pd));
  Object.assign(shim, surface);
  // Getters rather than copies: the frame counter moves.
  Object.defineProperty(shim, "frameCount", { get: () => surface.frameCount });
  bgArtSeedUsed = style.seeded ? bgArtSeedOf(o.seedText) : null;
  // A second canvas the same size, for a style that cross-fades one
  // picture into the next (the mycelium's generations): the old picture
  // fades by its element's opacity, which costs the page nothing a frame.
  // Only while moving; a still frame is one picture.
  let twin = null;
  if (style.twin && !o.still) {
    const t = bgArtSurface(pd, Math.min(style.pixelDensityY || pd, pd));
    t.canvas.id = "bg-art-twin";
    t.canvas.className = "bg-art-canvas";
    t.canvas.setAttribute("aria-hidden", "true");
    twin = { canvas: t.canvas, g: t.drawingContext, clear: t.clear };
  }
  shim.twin = twin;
  const { canvas, drawingContext: g } = surface;
  canvas.id = "bg-art-canvas";
  canvas.className = "bg-art-canvas";
  canvas.setAttribute("aria-hidden", "true");
  const wash = bgP5Rgba(0, 0, o.dark ? 12 : 98, o.dark ? 0.1 : 0.12);
  bgLumCap = o.dark ? style.darkCap || 0 : 0;
  bgLumFloor = o.dark ? 0 : style.lightFloor || 0;
  try {
    style.init();
  } finally {
    bgLumCap = 0;
    bgLumFloor = 0;
  }

  if (o.still) {
    // One frame, captured to an image; the canvas is never put in the page
    // and nothing is left running.
    if (style.background === "wash") {
      g.fillStyle = bgP5Rgba(0, 0, o.dark ? 12 : 98, 1);
      g.fillRect(0, 0, surface.width, surface.height);
    }
    if (style.settle) style.settle();
    style.frame(0);
    bgArtMountStill(canvas, gen, "", (layer, url) => {
      bgArtStillUrl = url;
      bgArtLayer = layer;
      retire();
    });
    return;
  }

  document.body.appendChild(canvas);
  if (twin) document.body.appendChild(twin.canvas);
  retire();
  let raf = 0, looping = false, last = 0;
  const handle = {
    drawingContext: g,
    // Called by the loop through the handle, so a measurement can wrap it
    // (scratchpad/ui-sweeps/bgartcost.js).
    draw() {
      surface.frameCount++;
      if (style.background === "wash") {
        // A translucent wash over the last frame, so marks leave gentle
        // trails instead of hard clears.
        g.fillStyle = wash;
        g.fillRect(0, 0, surface.width, surface.height);
      } else if (style.background === "clear") {
        surface.clear();
      }
      style.frame(surface.frameCount * 0.01);
    },
    isLooping: () => looping,
    loop() {
      if (looping) return;
      looping = true;
      last = 0;
      raf = requestAnimationFrame(tick);
    },
    noLoop() {
      looping = false;
      cancelAnimationFrame(raf);
    },
    remove() {
      handle.noLoop();
      canvas.remove();
      if (twin) twin.canvas.remove();
    },
    // The long pause (see BG_ART_FREEZE_MS): the picture of what is on
    // screen, the canvas out of the page, the canvas back.
    capture(gen, done) {
      let source = canvas;
      if (twin) {
        // Two generations cross-fading: flatten them as they stand.
        source = document.createElement("canvas");
        source.width = canvas.width; source.height = canvas.height;
        const c = source.getContext("2d");
        for (const el of [canvas, twin.canvas]) {
          const k = /\* ([\d.]+)\)$/.exec(el.style.opacity);
          c.globalAlpha = k ? Number(k[1]) : 1;
          c.drawImage(el, 0, 0);
        }
      }
      bgArtMountStill(source, gen, canvas.style.backgroundImage, done);
    },
    detach() {
      canvas.remove();
      if (twin) twin.canvas.remove();
    },
    attach() {
      if (!canvas.isConnected) document.body.appendChild(canvas);
      if (twin && !twin.canvas.isConnected) document.body.appendChild(twin.canvas);
    },
  };
  // A timestamp gate: the browser offers every display frame, and a frame
  // is drawn only when a thirtieth (or twentieth) of a second has passed.
  // `last` advances by whole intervals, so the rate holds steady instead of
  // drifting down to every other offer at the edge.
  function tick(now) {
    if (!looping) return;
    raf = requestAnimationFrame(tick);
    // A style may ask for fewer (the mesh moves too slowly to need more
    // than fifteen), never more.
    const interval = 1000 / Math.min(style.fps || 30, bgArtFrameRate());
    if (last && now - last < interval - 1) return;
    last = last && now - last < interval * 2 ? last + interval : now;
    handle.draw();
  }
  bgArtInstance = handle;
  handle.draw();
  bgArtWatch();
}

// **What each style costs, measured** (Brief 95): the CPU time of one
// frame, the draw and the raster it causes, at 1440x900 on a CPU-backed
// canvas in this project's four-core sandbox (bgartcpu.js: the renderer
// thread's own time, the least of three runs of 90 frames, the larger of
// the two themes and of two sweeps). The Settings cards grade them from it:
// Light under 0.5ms, Medium under 1.2ms, Heavy above; none may pass 2ms.
const BG_ART_COST = {
  aurora: 0.91, constellation: 1.47, waves: 0.97, bubbles: 1.59, mesh: 1.09, microbes: 1.68,
  mycelium: 0.25, dusk: 0.05, ripples: 0.18, fireflies: 0.38, rain: 0.13, wander: 0.12, drift: 0.41,
};

function bgArtTier(style) {
  const ms = BG_ART_COST[style] ?? 2;
  return ms < 0.5 ? "Light" : ms < 1.2 ? "Medium" : "Heavy";
}

// One still frame of a style for its Settings card, drawn into `target` (a
// small canvas). The style is built at its own pixel density over a window
// three times the card's size (at the window's own size a hairline, the rain
// or a ripple, scaled down nine times, vanished), and scaled down once: a
// preview costs one frame per style when the cards are drawn, and nothing
// after.
function bgArtPreview(name, o, target) {
  const entry = BG_ART_BUILDERS[name];
  if (!entry || entry.dom) return;
  const shim = {};
  const ctx = { dark: o.dark, baseHue: bgColourHue(o.accent), density: o.density, seedText: o.seedText, still: true };
  const style = entry(shim, ctx);
  const pd = Math.min(style.pixelDensity || 1, 1);
  const surface = bgArtSurface(pd, Math.min(style.pixelDensityY || pd, pd), target.width * 3, target.height * 3);
  Object.assign(shim, surface);
  shim.twin = null;
  bgLumCap = o.dark ? style.darkCap || 0 : 0;
  bgLumFloor = o.dark ? 0 : style.lightFloor || 0;
  try {
    style.init();
  } finally {
    bgLumCap = 0;
    bgLumFloor = 0;
  }
  const g = surface.drawingContext;
  if (style.background === "wash") {
    g.fillStyle = bgP5Rgba(0, 0, o.dark ? 12 : 98, 1);
    g.fillRect(0, 0, surface.width, surface.height);
  }
  if (style.settle) style.settle();
  style.frame(0);
  const out = target.getContext("2d");
  out.clearRect(0, 0, target.width, target.height);
  out.drawImage(surface.canvas, 0, 0, target.width, target.height);
}

// A hidden window draws nothing. Chromium already stops requestAnimationFrame
// in a background tab, but the desktop window's WebView is not a tab and a
// minimised window is not always "hidden" to it, so the loop is stopped
// outright rather than trusted to be throttled.
document.addEventListener("visibilitychange", () => {
  bgArtPaused.hidden = document.hidden;
  bgArtApplyPause();
});

// Unfocused for thirty seconds (another app in front, the window left on a
// second screen): stop; focus again: go on.
window.addEventListener("blur", () => {
  clearTimeout(bgArtBlurTimer);
  bgArtBlurTimer = setTimeout(() => {
    bgArtPaused.blurred = true;
    bgArtApplyPause();
  }, 30000);
});
window.addEventListener("focus", () => {
  clearTimeout(bgArtBlurTimer);
  if (bgArtPaused.blurred) {
    bgArtPaused.blurred = false;
    bgArtApplyPause();
  }
});

// Any input ends idle at once; otherwise it only stamps the time, which
// is all a pointer move can afford to cost.
for (const type of ["pointermove", "pointerdown", "keydown", "wheel", "touchstart"]) {
  window.addEventListener(type, () => {
    bgArtLastInput = performance.now();
    if (type !== "keydown") bgArtPaused.pointerAt = performance.now();
    if (bgArtPaused.idle) {
      bgArtPaused.idle = false;
      bgArtApplyPause();
    }
  }, { passive: true, capture: true });
}

// Every canvas style sizes its buffers and population to the window, and a
// still is an image of one size, so a resize rebuilds either, once the
// resizing stops (a drag fires this every frame). A CSS style is laid out
// in viewport units and needs nothing.
window.addEventListener("resize", () => {
  clearTimeout(bgArtResizeTimer);
  bgArtResizeTimer = setTimeout(() => {
    const canvasStyle = bgArtInstance || (bgArtLayer && bgArtLayer.id === "bg-art-still");
    if (canvasStyle && bgArtRestart) bgArtRestart();
  }, 250);
});
