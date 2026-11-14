// dash-art.js: the dashboard's "Notebook constellation" (Wave J), moved out of
// dashboard.js for INBOX 1530 (d) with p5's loader from phone-shell.js. The
// widget table's `render` calls `renderArtWidget`, a stand-in until this file
// is in (lazy-entries.js); `stopArt` and `refreshArtForTheme` stay in
// dashboard.js and reach `dashArtStop` and `dashArtRefresh` here once it is.
//
// A living "constellation" of the notebook: each category becomes a
// cluster of drifting stars, more notes, more stars, connected by
// faint lines in the category's own colour. It's seeded from the real
// note counts, so the same notebook always grows the same sky (until
// you hit Regenerate). Purely decorative; nothing depends on it.

(() => {
  //: **p5 is fetched the first time a moving constellation is drawn, not at boot.** It is a
  //: 1,034 KB file (the largest asset the page loads, 18% of all boot JS), and
  //: the dashboard's art, with background art on, is its one use now. Measured 2026-09-13: 13 blocking scripts, 1,698 KB
  //: compressed, before the first tab could draw. Same-origin dynamic scripts
  //: are what the CSP's `script-src 'self'` allows, so this is one element.
  let p5Loading = null;
  function ensureP5() {
    if (typeof p5 !== "undefined") return Promise.resolve(true);
    if (!p5Loading) {
      p5Loading = new Promise((resolve) => {
        //: After the first paint and the boot fetches, not during them: the
        //: emblem is drawn while the shell boots, and a dynamic script is off
        //: the parser's path but still on the network's.
        const later = window.requestIdleCallback || ((fn) => setTimeout(fn, 800));
        const start = () =>
          later(() => {
            const script = document.createElement("script");
            script.src = "/vendor/p5.min.js";
            script.onload = () => resolve(typeof p5 !== "undefined");
            script.onerror = () => resolve(false);
            document.head.appendChild(script);
          });
        //: After the last script, not at the first idle moment: on a slow load
        //: p5 finished first and `renderEmblem` threw on settings.js's `ACCENTS`.
        if (document.readyState === "complete") start();
        else window.addEventListener("load", start, { once: true });
      });
    }
    return p5Loading;
  }

  // A living "constellation" of the notebook: each category becomes a
  // cluster of drifting stars, more notes, more stars, connected by
  // faint lines in the category's own colour. It's seeded from the real
  // note counts, so the same notebook always grows the same sky (until
  // you hit Regenerate). Purely decorative; nothing depends on it.

  let artInstance = null; // the one live sketch (p5's, or the still one below), if any
  let artNonce = 0; // bumped by "Regenerate" for a fresh arrangement
  //: The drift reads a page-lifetime clock, so a rebuilt sketch (theme change,
  //: INBOX 838) carries on instead of restarting every star's drift at phase 0.
  //: A rest while idle moves it on by the rest, so the stars go on from where
  //: they stopped rather than jumping.
  const artClock = { epoch: performance.now() };
  const artDriftMs = () => performance.now() - artClock.epoch;
  // Bumped on every startArt call. A run that finds it has changed while it was
  // waiting knows it was superseded and must not mount its canvas, see the
  // comment in startArt for the stacking bug this fixes (§35G).
  let artRun = 0;
  // Where the constellation is drawn, kept so a theme change can rebuild it.
  //
  // The sketch reads light-or-dark ONCE, when it is built, and paints its wash
  // from that. Nothing rebuilt it when the mode changed, so toggling to dark left
  // the one panel on the dashboard still wearing the light background until you
  // pressed Regenerate: reported, and listed in IDEAS.md.
  let artHolder = null;

  // Stable 0–359 hue from a category name, so a category keeps its colour.
  function hueFor(name) {
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = (hash * 31 + name.charCodeAt(i)) % 360;
    }
    return hash;
  }

  //: The constellation paints in hue, so a colour the person chose (Manage
  //: categories, Colour) gives its hue and an automatic one keeps `hueFor`.
  function categoryHue(name) {
    const hex = categoryColour(name);
    if (!hex) return hueFor(name);
    return Math.round(artHexHue(hex)) % 360;
  }

  //: The hue of a #rgb, #rrggbb or rgb() colour, the number p5's `hue()` gives
  //: in HSL mode (unrounded); anything else is the default indigo's.
  function artHexHue(colour) {
    const c = String(colour || "").trim();
    let m = /^#([0-9a-f]{3})$/i.exec(c);
    let rgb;
    if (m) rgb = m[1].split("").map((x) => parseInt(x + x, 16));
    else if ((m = /^#([0-9a-f]{6})/i.exec(c))) rgb = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
    else if ((m = /rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)/i.exec(c))) rgb = m.slice(1, 4).map(Number);
    else return 230;
    const [r, g, b] = rgb.map((v) => v / 255);
    const spread = Math.max(r, g, b) - Math.min(r, g, b);
    if (!spread) return 0;
    const sector = Math.max(r, g, b) === r ? ((g - b) / spread) % 6 : Math.max(r, g, b) === g ? (b - r) / spread + 2 : (r - g) / spread + 4;
    return (sector * 60 + 360) % 360;
  }

  // A deterministic seed from the category names + counts: the sky is
  // stable for a given notebook, and shifts only as the notebook changes.
  function artSeed(categories) {
    let seed = 1;
    for (const c of categories) {
      seed = (seed * 31 + hueFor(c.name) + c.count) % 1_000_000;
    }
    return seed;
  }

  function stopArt() {
    if (artInstance) {
      artInstance.remove(); // tears down the canvas + draw loop
      artInstance = null;
    }
  }

  // Rebuild the constellation for the mode now in force. Safe to call whenever
  // the theme changes: it does nothing unless the widget is actually on screen,
  // and it keeps `artNonce` so the sky stays the same arrangement, this is a
  // recolour, not a reshuffle, and re-rolling someone's picture because they
  // turned on dark mode would be its own bug.
  //: **A theme change cross-fades the picture, it does not swap it** (INBOX 803,
  //: the owner: "the notebook constellation adjusts suddenly or jolts a bit and
  //: doesn't have a smooth fade transition"). Rebuilding for the new mode took
  //: the old canvas away and drew the new one a frame or more later, 98% of the
  //: change landing in one frame (measured, constellationtheme.js). The old
  //: sky is copied onto a veil that stays over the holder, and fades out over
  //: the new one; with interface animations off or less motion asked for there
  //: is no veil and the change is instant, as before.
  function refreshArtForTheme() {
    if (!artHolder || !artHolder.isConnected) {
      artHolder = null;
      return;
    }
    const holder = artHolder;
    const old = holder.querySelector("canvas:not(.art-veil)");
    const still = reducedMotionWanted() || document.documentElement.dataset.uiMotion === "off";
    holder.querySelector(".art-veil")?.remove();
    if (old && !still) {
      const veil = document.createElement("canvas");
      veil.className = "art-veil";
      veil.width = old.width;
      veil.height = old.height;
      veil.setAttribute("aria-hidden", "true");
      veil.getContext("2d").drawImage(old, 0, 0);
      holder.appendChild(veil);
      const lift = () => {
        //: Two frames on, so the new sky has been drawn under it before it goes.
        afterFrames(() => {
          veil.classList.add("is-leaving");
          veil.addEventListener("transitionend", () => veil.remove(), { once: true });
          setTimeout(() => veil.remove(), 1000);
        });
      };
      startArt(holder).then(lift, lift);
      return;
    }
    startArt(holder);
  }

  function buildArtParticles(p, categories, total, width, height) {
    const groups = categories.length ? categories : [{ name: "Notes", count: 1 }];
    const particles = [];
    for (const group of groups) {
      const hue = categoryHue(group.name);
      // 3 base stars, plus more for a bigger share of the notebook (capped).
      const count = Math.max(3, Math.min(16, Math.round((group.count / total) * 70) + 3));
      const cx = p.random(width * 0.15, width * 0.85);
      const cy = p.random(height * 0.2, height * 0.8);
      for (let i = 0; i < count; i++) {
        particles.push({
          baseX: cx + p.random(-46, 46),
          baseY: cy + p.random(-34, 34),
          x: 0,
          y: 0,
          phase: p.random(p.TWO_PI),
          amp: p.random(2, 9),
          size: p.random(2, 5),
          hue,
          //: Which star this is across a Regenerate (INBOX 686): the n-th star
          //: of a category glides to where the n-th star of that category goes.
          cat: group.name,
          idx: i,
        });
      }
    }
    return particles;
  }

  //: **Regenerate glides (INBOX 686**, the owner: "can you add a smooth
  //: animation for regenerating the notebook constelation??"). It used to tear
  //: the sketch down and mount a new one, so the sky changed in one frame. Now
  //: the live sketch is retargeted: every star eases from where it is drawn to
  //: its place in the new arrangement, a star with no partner fades and grows
  //: in where it lands, one left over fades out where it stands, and the lines
  //: (which read wrong while their stars are travelling) fade out and come back
  //: as the stars settle. A second Regenerate mid-way starts from the drawn
  //: positions, so nothing jumps.
  //:
  //: The bound the owner's ask is measured against: no star moves more than an
  //: eighth of its journey between two frames. A cubic ease-out starts at three
  //: times the average speed, so at the sketch's thirty frames a second over
  //: 800 ms the first frame would be 0.125 of the way, exactly on the line;
  //: the glide runs at sixty (`ART_GLIDE_FPS`) and drops back when it settles,
  //: which halves it. Measured first with the wall clock, the first frame was
  //: still 0.14 of the way: it was drawn 30 to 50 ms after the click, and a
  //: busy machine's late frames did the same mid-glide. Hence the glide's own
  //: clock below. `scratchpad/ui-sweeps/constellation686.js` measures it.
  const ART_GLIDE_MS = 800;
  //: A light-theme star's core lightness: 40, or darker until it is 3:1 on the
  //: well (ledger 934: yellow was 2.1:1, cyan 2.0). Saturation 80, as drawn.
  const artCoreLights = new Map();
  function artCoreLight(hue) {
    if (artCoreLights.has(hue)) return artCoreLights.get(hue);
    const lum = (l) => {
      const a = 0.8 * Math.min(l, 1 - l);
      const c = (n) => { const k = (n + hue / 30) % 12; const v = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)); return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
      return 0.2126 * c(0) + 0.7152 * c(8) + 0.0722 * c(4);
    };
    let l = 40;
    while (l > 20 && 0.83 / (lum(l / 100) + 0.05) < 3) l -= 2;
    artCoreLights.set(hue, l);
    return l;
  }
  const ART_GLIDE_FPS = 60;
  //: The most of the glide's clock one frame may spend: 25 ms is three fifths
  //: of an eighth of the journey even at the ease's fastest, its first frame.
  const ART_GLIDE_STEP_MS = 25;
  //: The quick cross-fade that replaces the glide when interface animations are
  //: off or less motion is asked for: a change of picture, not a journey.
  const ART_FADE_MS = 200;

  function artEaseOut(u) {
    const k = 1 - Math.min(1, Math.max(0, u));
    return 1 - k * k * k;
  }

  //: The ease of a glide that interrupts another: it leaves at rest, so a second Regenerate has no kick
  //: (the ease-out's first step is 3 times the average, 13 to 16 px against 7; this one peaks at 1.5 times).
  function artEaseSoft(u) {
    const k = Math.min(1, Math.max(0, u));
    return k * k * (3 - 2 * k);
  }

  //: The lines' strength through a glide: from wherever they were (a glide
  //: interrupted while they were half gone starts from half), out by a third
  //: of the way, held out while the stars cross, back in over the last half.
  function artLineFade(from, u) {
    if (u <= 0.3) return from * (1 - u / 0.3);
    if (u <= 0.5) return 0;
    return artEaseOut((u - 0.5) / 0.5);
  }

  //: Pair the stars drawn now with the next arrangement's. `shown` carries what
  //: the last frame drew (`x`, `y`, `vis`, `drawSize`); each next star gets a
  //: `from` (a partner's drawn state, or nothing: it grows in where it lands);
  //: unpaired shown stars, and stars still fading from an earlier glide, leave.
  function artRetarget(shown, leaving, next) {
    const key = (s) => `${s.cat}\u0000${s.idx}`;
    const drawn = new Map(shown.map((s) => [key(s), s]));
    for (const star of next) {
      const was = drawn.get(key(star));
      star.from = was ? { x: was.x, y: was.y, vis: was.vis ?? 1, size: was.drawSize ?? was.size } : { x: null, y: null, vis: 0, size: 0 };
      drawn.delete(key(star));
    }
    const gone = [...leaving, ...drawn.values()].filter((s) => (s.vis ?? 1) > 0.01);
    return gone.map((s) => ({ ...s, from: { x: s.x, y: s.y, vis: s.vis ?? 1, size: s.drawSize ?? s.size } }));
  }

  async function renderArtWidget(body) {
    //: A second draw into the same card (the background art changed) replaced
    //: nothing: the owner saw two constellations, the first one empty (owner, 2026-11-10).
    for (const el of body.querySelectorAll(":scope > .art-holder, :scope > .art-caption, :scope > .art-controls, :scope > .art-legend")) el.remove();
    const holder = document.createElement("div");
    holder.className = "art-holder";
    body.appendChild(holder);

    // Say what the picture actually means, until now it was pretty but
    // unlabelled (user asked what the nodes represent).
    const caption = document.createElement("p");
    caption.className = "muted art-caption";
    caption.textContent =
      "Each cluster of stars is one category; the more notes it holds, the more " +
      "stars it gets. Lines link stars that drift close together.";
    body.appendChild(caption);

    const controls = document.createElement("div");
    controls.className = "row art-controls";
    controls.appendChild(
      smallButton("ph:dice-five Regenerate", "A fresh arrangement of the same notes", () => {
        artNonce += 1;
        //: The live sketch glides to it (INBOX 686); only a widget with no
        //: sketch yet (p5 still loading) builds one.
        if (artInstance) artInstance.regenerate();
        else startArt(holder);
      })
    );
    controls.appendChild(
      smallButton("ph:floppy-disk Save PNG", "Save this artwork as an image", () => {
        if (artInstance) artInstance.saveSettled();
      })
    );
    body.appendChild(controls);

    // A colour key so each cluster is identifiable, matching the hue the
    // canvas paints each category with.
    const legend = document.createElement("div");
    legend.className = "art-legend";
    body.appendChild(legend);
    fetchDashStats()
      .then((stats) => {
        const cats = (stats.categories || []).slice(0, 8);
        legend.replaceChildren();
        for (const cat of cats) {
          const item = document.createElement("span");
          item.className = "art-legend-item";
          const dot = document.createElement("span");
          dot.className = "art-legend-dot";
          dot.style.background = categoryColour(cat.name, `hsl(${hueFor(cat.name)}, 70%, 55%)`);
          item.append(dot, document.createTextNode(`${cat.name} · ${cat.count}`));
          legend.appendChild(item);
        }
      })
      .catch(() => {});

    return startArt(holder);
  }

  //: **One path and one fill per colour, not one per shape** (INBOX 1501's
  //: sweep: `scene` was 7 to 18 ms a frame at 4x, most of it a colour string
  //: and a stroke or two fills for every line and every star, a hundred stars
  //: and a few hundred lines thirty times a second). A line's alpha and a
  //: star's twinkle are cut into steps too fine to see (0.03 and a twelfth), so
  //: the lines and the glows fall into a handful of buckets, each drawn as one
  //: `Path2D` with one `strokeStyle`/`fillStyle`; the nearness test compares
  //: squares, and the bucket's colour string is made once (`ART_CSS`).
  const ART_CSS = new Map();
  const artCss = (hue, sat, light, alpha) => {
    const key = `${hue}|${sat}|${light}|${alpha}`;
    let css = ART_CSS.get(key);
    if (!css) ART_CSS.set(key, (css = `hsla(${hue}, ${sat}%, ${light}%, ${alpha})`));
    return css;
  };
  const ART_LINK = 70;
  const ART_LINE_STEP = 0.03;
  const ART_TWINKLE_STEPS = 12;
  //: A bucket is one colour's path, made on first use this frame. Its key is a
  //: number (`hue` times 100 plus the step, no string made per line or star);
  //: the bucket keeps the hue and step it stands for.
  const artBucket = (buckets, hue, step) => {
    const key = hue * 100 + step;
    let bucket = buckets.get(key);
    if (!bucket) buckets.set(key, (bucket = { hue, step, path: new Path2D() }));
    return bucket.path;
  };
  function artDrawLines(ctx, particles, lines, dark) {
    if (lines <= 0) return;
    const buckets = new Map();
    for (let i = 0; i < particles.length; i++) {
      const a = particles[i];
      for (let j = i + 1; j < particles.length; j++) {
        const b = particles[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const near = dx * dx + dy * dy;
        if (near >= ART_LINK * ART_LINK) continue;
        const alpha = 0.45 * (1 - Math.sqrt(near) / ART_LINK) * lines * Math.min(a.vis, b.vis);
        const path = artBucket(buckets, a.hue, Math.round(alpha / ART_LINE_STEP));
        path.moveTo(a.x, a.y);
        path.lineTo(b.x, b.y);
      }
    }
    ctx.lineWidth = 1;
    for (const { hue, step, path } of buckets.values()) {
      ctx.strokeStyle = artCss(hue, 65, dark ? 72 : 55, (step * ART_LINE_STEP).toFixed(3));
      ctx.stroke(path);
    }
  }
  //: The stars: a soft glow halo under a bright core, twinkling. Every halo is
  //: drawn, then every core, so a neighbour's halo never covers a core.
  function artDrawStars(ctx, dots, t, dark) {
    const glows = new Map();
    const cores = new Map();
    for (const dot of dots) {
      const twinkle = (0.6 + 0.4 * Math.sin(t * 2 + dot.phase)) * dot.vis;
      const step = Math.round(twinkle * ART_TWINKLE_STEPS);
      const glow = artBucket(glows, dot.hue, step);
      glow.moveTo(dot.x + dot.drawSize * 2, dot.y);
      glow.arc(dot.x, dot.y, dot.drawSize * 2, 0, Math.PI * 2);
      const core = artBucket(cores, dot.hue, step);
      core.moveTo(dot.x + dot.drawSize / 2, dot.y);
      core.arc(dot.x, dot.y, dot.drawSize / 2, 0, Math.PI * 2);
    }
    for (const { hue, step, path } of glows.values()) {
      ctx.fillStyle = artCss(hue, 75, dark ? 65 : 55, ((0.14 * step) / ART_TWINKLE_STEPS).toFixed(3));
      ctx.fill(path);
    }
    for (const { hue, step, path } of cores.values()) {
      ctx.fillStyle = artCss(hue, 80, dark ? 78 : artCoreLight(hue), (step / ART_TWINKLE_STEPS).toFixed(3));
      ctx.fill(path);
    }
  }

  //: What the dashboard's constellation draws at. See `p.setup` below for why
  //: thirty rather than the sixty p5 defaults to.
  const ART_FRAME_RATE = 30;
  //: How long the drift runs after the pointer was last on the card or Regenerate was
  //: pressed, and how long after the sketch mounts (see `attendUntil`).
  const ART_ATTEND_MS = 8000;
  const ART_SETTLE_MS = 1500;

  async function startArt(holder) {
    // Which run this is. `startArt` awaits /insights/stats before it mounts
    // anything, and `stopArt()` above that await can only remove an instance
    // that already exists: so two overlapping calls each found `artInstance`
    // null, each waited, and each mounted a canvas into the same holder. That
    // is the four-or-five stacked constellations that were screenshotted
    // (§35G), and the same bug is why Regenerate read as "broken and severely
    // glitchy": every click added a canvas and `artInstance` only ever tracked
    // the last one, so nothing could tear the others down.
    const run = ++artRun;
    stopArt();
    artHolder = holder;
    //: **p5 only with background art on** (INBOX 1530 d, audit 1031 row 21).
    //: Off, which is the default, the sky is one still frame drawn by
    //: `artStill` on a plain canvas, the reduced-motion picture, and the 1 MB
    //: p5 is never fetched; on, p5 loads after the page (`ensureP5` above) and
    //: the stars drift. Measured on the dashboard in the 1530 sweep.
    const live = bgArtOn();
    if (live && typeof p5 === "undefined" && !(await ensureP5())) {
      holder.textContent = "The art library didn't load.";
      return;
    }
    if (run !== artRun) return;
    const stats = await fetchDashStats().catch(() => ({
      categories: [],
      total_entries: 0,
    }));
    const categories = (stats.categories || []).slice(0, 8);
    const total = Math.max(1, stats.total_entries || 0);
    //: **Every switch that means "stop moving things", not only the OS hint.**
    //:
    //: This read the media query and nothing else, so the two generative
    //: pictures in the app disagreed about the same question: the background
    //: art (`startBgArt`, settings.js) resolves motion from the app's own
    //: Motion setting and from Performance mode as well, and this one
    //: ignored both. Set Motion to Off and the background froze while this
    //: widget kept running; turn on Performance mode, which DESIGN.md rule 12
    //: says stops every animation but the progress indicators, and this was
    //: the thing that kept going. The background art's own comment notes it
    //: used to be "the one thing that kept running" under Performance mode;
    //: this was the second one, and nobody had looked.
    //:
    //: Measured on the dashboard: this canvas runs at 59 fps in a 306x220 box,
    //: and it is what the owner's "theres a flickering just above the bottom
    //: bar" is looking at (INBOX 226: the pixels change in one column of the
    //: band above the status bar, with no DOM mutation at all, and the
    //: *background* art is off; the earlier investigation measured that one).
    //:
    //: `reducedMotionWanted` (chat.js) is the OS hint or the app's own switch;
    //: `perfModeOn` (settings.js) is the machine judgement. Both reached
    //: through `typeof`, since dashboard.js loads before settings.js and a
    //: render that somehow beat it should fall back to moving rather than
    //: throw.
    //:
    //: Not `bg-motion`: that control is the background's own, is hidden when
    //: the background art is off, and would be a surprising place to find the
    //: switch for a widget.
    //: Three inputs, not two: Battery-efficient mode joins them (INBOX 260).
    //: A setting with "battery" in its name that leaves a canvas drawing is a
    //: setting people read as broken, whatever its help text says.
    const reduceMotion =
      !live ||
      reducedMotionWanted() ||
      (typeof perfModeOn === "function" && perfModeOn()) ||
      batteryModeOn();
    // data-mode is always resolved to light or dark, including under "System",
    // so this no longer has to re-derive it from two sources.
    const dark = resolvedTheme() === "dark";
    // The wash used a hardcoded indigo hue, so on any palette that isn't
    // indigo, Sage, Ocean, Ember, the one generative panel on the dashboard
    // was the only thing on screen still wearing the old theme's colour.
    const accentHex = currentAccentHex();

    const sketch = (p) => {
      let particles = [];
      let width = 0;
      const height = 220;
      //: The glide in hand (INBOX 686): when it began, how strong the lines
      //: were then, and the stars still fading out. `null` at rest.
      let glide = null;
      //: The quick cross-fade's picture of the old sky, and when it began.
      let fade = null;
      //: When the card left the view (`sight` below), 0 while it is in view.
      let hiddenSince = 0;
      //: **The drift runs while somebody is looking** (INBOX 1501: the scene was
      //: 60 percent of the script on a Dashboard click at 4x, a loop nothing
      //: needed). It runs `ART_SETTLE_MS` after the sketch mounts (the Dashboard
      //: mounts a new one on every visit to the tab), and `ART_ATTEND_MS` after a
      //: Regenerate and after the pointer last moved over the card, then the sketch
      //: rests with its last frame on the canvas, no loop and no timer, and a
      //: pointer over the card, a focus in it or a Regenerate wakes it.
      let attendUntil = performance.now() + ART_SETTLE_MS;
      //: The wash's hue and gradient, made once: the accent and the height do not
      //: change for the life of a sketch (a theme change rebuilds it).
      let washHue = null;
      let washGradient = null;
      const washHueOf = () => artHexHue(accentHex);

      //: `settled` draws the arrangement the glide is heading for, whatever
      //: point it has reached: what Save PNG saves.
      const scene = (t, settled = false) => {
        //: **Drawn on the canvas context, not through p5's colour calls.** Idle
        //: on the Dashboard at 4x CPU this scene was 527 ms of the 540 ms the
        //: page was busy in five seconds, 426 ms of it p5 parsing a colour for
        //: each of 55 wash strips, each connecting line and each star's two
        //: fills, thirty times a second. One gradient, the accent's hue read once,
        //: and a colour string per shape say the same thing for a tenth of it.
        const ctx = p.drawingContext;
        //: A soft vertical wash instead of a flat fill, more depth (Wave N).
        //: Light is an off-white well, lightness 95 down to 91, the accent's hue
        //: faintly in it, as dark is a deep one: it was 250 to 240, which HSL
        //: clamps to pure white, the same as the card it sat on (INBOX 803).
        washHue ??= washHueOf();
        if (!washGradient) {
          washGradient = ctx.createLinearGradient(0, 0, 0, height);
          washGradient.addColorStop(0, `hsl(${washHue} 30% ${dark ? 14 : 95}%)`);
          washGradient.addColorStop(1, `hsl(${washHue} 30% ${dark ? 24 : 91}%)`);
        }
        ctx.fillStyle = washGradient;
        ctx.fillRect(0, 0, width, height);
        const now = p.millis();
        //: The glide's own clock, advanced by each drawn frame and by no more
        //: than `ART_GLIDE_STEP_MS` per frame: it starts at the first frame
        //: drawn after the click, not at the click, and a late frame (a busy
        //: machine) stalls the glide rather than jumping it.
        if (glide && !settled) {
          if (glide.last !== null) glide.elapsed += Math.min(now - glide.last, ART_GLIDE_STEP_MS);
          glide.last = now;
        }
        const u = glide && !settled ? Math.min(1, glide.elapsed / ART_GLIDE_MS) : 1;
        const e = glide?.soft ? artEaseSoft(u) : artEaseOut(u);
        //: The drift goes on under the glide: a star eases from where it was
        //: drawn towards its new place as that place drifts, so it arrives on
        //: the moving point rather than on a still one and then lurching.
        for (const dot of particles) {
          const x = dot.baseX + Math.cos(t + dot.phase) * dot.amp;
          const y = dot.baseY + Math.sin(t * 1.3 + dot.phase) * dot.amp;
          const from = u < 1 ? dot.from : null;
          dot.x = from && from.x !== null ? from.x + (x - from.x) * e : x;
          dot.y = from && from.y !== null ? from.y + (y - from.y) * e : y;
          dot.vis = from ? from.vis + (1 - from.vis) * e : 1;
          dot.drawSize = from ? from.size + (dot.size - from.size) * e : dot.size;
        }
        const lines = u < 1 ? artLineFade(glide.lineFrom, u) : 1;
        artDrawLines(ctx, particles, lines, dark);
        //: Stars with no place in the new sky fade where they stand, gone by
        //: six tenths of the way so the arrivals are not crowded by them.
        const leaving = u < 1 ? glide.leaving : [];
        const out = artEaseOut(Math.min(1, u / 0.6));
        for (const dot of leaving) dot.vis = dot.from.vis * (1 - out);
        artDrawStars(ctx, leaving.concat(particles), t, dark);
        if (fade && !settled) {
          const k = 1 - Math.min(1, (now - fade.start) / ART_FADE_MS);
          ctx.save();
          ctx.globalAlpha = k;
          ctx.drawImage(fade.snap, 0, 0, width, height);
          ctx.restore();
        }
      };

      //: Regenerate (INBOX 686): the next arrangement, reached by a glide, or
      //: by a cross-fade when interface animations are off or less motion is
      //: asked for (read now, not at build: the switch may have moved since).
      p.regenerate = () => {
        if (!width) return;
        attend();
        p.randomSeed(artSeed(categories) + artNonce * 997);
        const next = buildArtParticles(p, categories, total, width, height);
        const now = p.millis();
        if (reduceMotion || reducedMotionWanted() || document.documentElement.dataset.uiMotion === "off") {
          const snap = document.createElement("canvas");
          snap.width = p.drawingContext.canvas.width;
          snap.height = p.drawingContext.canvas.height;
          snap.getContext("2d").drawImage(p.drawingContext.canvas, 0, 0);
          fade = { snap, start: now };
          glide = null;
          particles = next;
          p.frameRate(ART_FRAME_RATE);
          p.loop();
          return;
        }
        const u = glide ? Math.min(1, glide.elapsed / ART_GLIDE_MS) : 1;
        const lineFrom = glide && u < 1 ? artLineFade(glide.lineFrom, u) : 1;
        const leaving = artRetarget(particles, glide && u < 1 ? glide.leaving : [], next);
        glide = { elapsed: 0, last: null, lineFrom, leaving, soft: u < 1 && !!glide };
        particles = next;
        p.frameRate(ART_GLIDE_FPS);
      };
      //: Save PNG takes the settled sky, then puts the frame in hand back
      //: before the browser paints, so the save never shows on screen.
      p.saveSettled = () => {
        const t = reduceMotion ? 0 : artDriftMs() * 0.0003;
        scene(t, true);
        p.saveCanvas("tessellate-constellation", "png");
        scene(t);
      };
      //: What the stars are drawn at, for the sweep that measures the glide.
      p.artStars = () => particles;

      p.setup = () => {
        width = holder.clientWidth || 300;
        p.createCanvas(width, height);
        p.colorMode(p.HSL, 360, 100, 100, 1);
        p.randomSeed(artSeed(categories) + artNonce * 997);
        particles = buildArtParticles(p, categories, total, width, height);
        //: **Thirty frames a second, for a drift that takes twenty seconds to
        //: go round.** The motion here is `cos(t + phase) * amp` with `amp`
        //: between 2 and 9 pixels: at sixty frames a second a star moves about
        //: a fiftieth of a pixel between frames, which nobody can see and
        //: everybody's battery pays for. Profiled over fourteen seconds of
        //: ordinary use, p5 was 248 ms of self time, the largest single thing
        //: on screen, and this is the sketch doing it.
        //:
        //: Halving is safe because `scene` runs off the clock below, not `frameCount`.
        p.frameRate(ART_FRAME_RATE);
        if (reduceMotion) {
          scene(0); // one still frame: no animation for reduced-motion users
          p.noLoop();
        }
      };
      //: Resting stops the loop and the drift clock with it: the time spent
      //: resting is added to the epoch on waking, so the stars go on from where
      //: they stood. `p.rested` is the moment it began, 0 while it draws.
      const rest = () => {
        p.noLoop();
        p.rested ||= performance.now();
      };
      const wake = () => {
        if (!p.rested) return;
        artClock.epoch += performance.now() - p.rested;
        p.rested = 0;
        if (!hiddenSince) p.loop();
      };
      //: Somebody is at the card: the window starts again, and a rest ends.
      const attend = () => {
        attendUntil = performance.now() + ART_ATTEND_MS;
        wake();
      };
      //: Wall clock, not `frameCount`, so the drift runs at the speed it was
      //: chosen at whatever the frame rate happens to be, including whatever a
      //: browser throttles a background tab to. The two are the same number:
      //: `frameCount * 0.005` at sixty frames a second advanced `t` by 0.3 a
      //: second, and `millis() * 0.0003` advances it by 0.3 a second full stop.
      p.draw = () => {
        if (hiddenSince) {
          p.noLoop();
          return;
        }
        //: Nothing is drawn behind a modal (INBOX 1620 f); attention ends the rest.
        if (!reduceMotion && !glide && !fade && (performance.now() > attendUntil || document.querySelector(".modal-overlay:not(.hidden)"))) {
          rest();
          return;
        }
        scene(reduceMotion ? 0 : artDriftMs() * 0.0003);
        const now = p.millis();
        if (glide && glide.elapsed >= ART_GLIDE_MS) {
          glide = null;
          p.frameRate(ART_FRAME_RATE);
        }
        if (fade && now - fade.start >= ART_FADE_MS) {
          fade = null;
          if (reduceMotion) p.noLoop();
        }
      };
      // Was missing entirely: width was measured once at setup and never
      // re-synced, so this canvas was the one p5 sketch in the app with no
      // resize handling at all (the sibling in the whiteboard has its own).
      // Reported as the constellation "keeps disappearing": a second trigger
      // on top of the theme-change one ARCHITECTURE §10 already documents and
      // `refreshArtForTheme` already handles. A ResizeObserver on the holder
      // catches both a real window resize *and* the Edit-layout "Wide" toggle
      // (which changes the card's width with no window resize event at all), 
      // `p.windowResized` alone would have missed the second one entirely.
      //: The width comes from the observer's own entry: it reports after layout,
      //: so reading `clientWidth` here forced another one when a keystroke or a
      //: late widget had dirtied the page (INBOX 1465: 64 to 89 ms).
      const resync = (entries) => {
        if (!holder.isConnected) return;
        const next = Math.round(entries?.[0]?.contentRect.width ?? holder.clientWidth);
        // Guarded the same reason `holder.clientWidth || 300` is in setup: a
        // transient 0 mid-reflow must not shrink the canvas to nothing.
        if (!next || next === width) return;
        width = next;
        p.resizeCanvas(width, height);
        glide = null;
        particles = buildArtParticles(p, categories, total, width, height);
        //: **Paint the new size at once.** `resizeCanvas` clears the canvas and
        //: p5's own redraw goes through `draw`, which returns early when the
        //: sketch is resting (after the attend window) or scrolled out of view,
        //: so a resize then left an empty box with the legend under it (INBOX
        //: 1620, measured: 0 star pixels after a window resize at rest).
        scene(reduceMotion ? 0 : artDriftMs() * 0.0003);
      };
      const observer = new ResizeObserver(resync);
      observer.observe(holder);
      //: **Rests while scrolled out of view** (audit 1029 row 38: on a long
      //: Dashboard this scene was 185 ms of every 3 s at 1x with the card off
      //: screen). The clock moves on by the time away, as after the idle rest,
      //: so the drift picks up where it was last drawn.
      const sight = new IntersectionObserver(([entry]) => {
        if (reduceMotion) return;
        if (!entry.isIntersecting) {
          hiddenSince ||= performance.now();
          return;
        }
        if (!hiddenSince) return;
        //: A sketch that rested before it left the view keeps its rest's own count
        //: of the time away (`wake`), so the two are not added twice.
        if (!p.rested) artClock.epoch += performance.now() - hiddenSince;
        hiddenSince = 0;
        //: Back in view with the window gone: no frame is drawn, the canvas
        //: kept its last (a tab click costs the art nothing).
        if (!p.rested) performance.now() > attendUntil ? rest() : p.loop();
      });
      sight.observe(holder);
      const ATTEND_EVENTS = ["pointerenter", "pointermove", "focusin", "touchstart"];
      for (const type of ATTEND_EVENTS) holder.addEventListener(type, attend, { passive: true });
      p.remove = ((original) => () => {
        observer.disconnect();
        sight.disconnect();
        for (const type of ATTEND_EVENTS) holder.removeEventListener(type, attend);
        original.call(p);
      })(p.remove);
    };

    // Superseded while we waited, or the widget was re-rendered out from under
    // us. Either way this run must not mount: it would be the second canvas.
    if (run !== artRun || !holder.isConnected) return;
    // Belt and braces. `stopArt` handles the instance we know about; clearing
    // the holder removes any canvas a previous version of this bug left behind,
    // so an already-stacked dashboard heals on the next render rather than
    // needing a reload.
    stopArt();
    //: Everything but a theme change's veil (`refreshArtForTheme`).
    for (const child of [...holder.children]) if (!child.classList.contains("art-veil")) child.remove();
    holder.replaceChildren(...holder.querySelectorAll(":scope > .art-veil"));
    //: p5 arrives on demand (`ensureP5`); the run check above is
    //: repeated after the wait, since a second render can have superseded us.
    if (live && typeof p5 === "undefined") {
      const ok = await ensureP5();
      if (!ok || run !== artRun || !holder.isConnected) return;
    }
    artInstance = live ? new p5(sketch, holder) : artStill(sketch, holder);
  }

  //: **The few p5 calls the sketch makes, over a plain canvas** (INBOX 1530 d),
  //: for the still sky. The random numbers are p5's own generator (the same
  //: LCG and seed), so the still and the moving sky are one arrangement; the
  //: canvas is sized and scaled as p5 sizes it (`pixelDensity` is the ceiling
  //: of the device ratio). A loop runs only while a Regenerate cross-fades.
  function artStill(sketch, holder) {
    const M = 4294967296;
    const born = performance.now();
    let seed = (Math.random() * M) >>> 0;
    let canvas = null;
    let frame = 0;
    let looping = true;
    let fps = 60;
    let last = 0;
    const p = { TWO_PI: Math.PI * 2, HSL: "hsl" };
    const size = (w, h) => {
      const k = Math.ceil(window.devicePixelRatio) || 1;
      canvas.width = Math.floor(w * k);
      canvas.height = Math.floor(h * k);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      p.drawingContext.setTransform(k, 0, 0, k, 0, 0);
    };
    const next = () => requestAnimationFrame(tick);
    const tick = (now) => {
      frame = looping ? next() : 0;
      if (!looping || now - last < 1000 / fps - 2) return;
      last = now;
      p.draw?.();
    };
    Object.assign(p, {
      randomSeed: (value) => { seed = value >>> 0; },
      random(min, max) {
        seed = (1664525 * seed + 1013904223) % M;
        const r = seed / M;
        if (min === undefined) return r;
        if (max === undefined) return r * min;
        return min > max ? r * (min - max) + max : r * (max - min) + min;
      },
      millis: () => performance.now() - born,
      colorMode() {},
      frameRate: (n) => { fps = n; },
      loop() {
        looping = true;
        frame ||= next();
      },
      noLoop() {
        looping = false;
        cancelAnimationFrame(frame);
        frame = 0;
      },
      createCanvas(w, h) {
        canvas = document.createElement("canvas");
        p.drawingContext = canvas.getContext("2d");
        size(w, h);
        holder.appendChild(canvas);
      },
      resizeCanvas(w, h) {
        size(w, h);
        p.draw?.();
      },
      saveCanvas(name, ext) {
        canvas.toBlob((blob) => {
          const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${name}.${ext}` });
          link.click();
          setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        });
      },
      remove() {
        p.noLoop();
        canvas?.remove();
      },
    });
    sketch(p);
    p.setup();
    if (looping) p.loop();
    return p;
  }

  //: The file's whole surface: what the stand-in and dashboard.js call (ranked row 37a).
  Object.assign(window, { renderArtWidget, dashArtStop: stopArt, dashArtRefresh: refreshArtForTheme });
})();
