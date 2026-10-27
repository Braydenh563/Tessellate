// atlas-life.js: Atlas's living tail, its rings' loops and its props' own
// motion (INBOX 623). The tail and the rings moved out of
// atlas.js on 2026-10-05 (the boot-script gzip budget, tests/test_boot_budget.py):
// the figure draws whole without either, its tail in its drawn shape and its
// rings at rest, so nothing here is needed for the first frame. Loaded by
// `LAZY_MODULES.atlasLife` (app.js) when a layered figure is first made
// (`atlasFigure`, which then calls `atlasRigLowerAttach`, `atlasRingLoops`,
// `atlasPropLoops` and `atlasTailAttach`); the lower body's pose for the
// state (`atlasRigLower`) came with them the same day, for the same budget;
// `atlasTailWake` stays in atlas.js, since the rig calls it on every wake and
// a figure only has a tail to wake once this file has attached one.

//: The rings' and the planets' loops for a figure, as Web Animations (the
//: boot stylesheets are at their budget): each ring's sway, shared by its
//: two halves and its planets' frame so they stay one ring; its dust's
//: turn, the next ring the other way; each planet's glow and swirl. Every
//: one starts at a random point of its own clock. Paused and played with
//: the tail's loop (`atlasTailFrame`), which knows when the figure is off
//: screen, hidden or still by setting.
function atlasRingLoops(box) {
  if (!box.animate) return [];
  const { cx, cy, flat, tilt } = ATLAS_GEO.ringFrame;
  const loops = [];
  const loop = (el, frames, ms, delay, opts = {}) => loops.push(el.animate(frames, { duration: ms, delay: -delay * ms, iterations: Infinity, direction: "alternate", easing: "ease-in-out", ...opts }));
  ATLAS_GEO.rings.forEach((ring, k) => {
    const [secs, deg, squash] = ATLAS_RING_SWAY[k];
    const at = (d, f) => ({ transform: `translate(${cx}px, ${cy}px) rotate(${tilt + d}deg) scale(1, ${+(flat * f).toFixed(4)})` });
    const sway = Math.random();
    for (const el of box.querySelectorAll(`.atl-ring-frame-${k}, .atl-orbit-${k}`)) loop(el, [at(-deg, 1 - squash), at(deg, 1 + squash)], secs * 1000, sway);
    const spin = Math.random();
    for (const el of box.querySelectorAll(`.atl-ring-frame-${k} .atl-ring-spin`)) loop(el, [{ rotate: "0deg" }, { rotate: `${k % 2 ? -360 : 360}deg` }], (34 + 9 * k) * 1000, spin, { direction: "normal", easing: "linear" });
  });
  for (const el of box.querySelectorAll(".atl-orbiter-glow")) loop(el, [{ scale: 0.8, opacity: 0.35 }, { scale: 1.2, opacity: 0.9 }], 2200 + Math.random() * 2400, Math.random());
  box.querySelectorAll(".atl-orbiter-swirl").forEach((el, i) => loop(el, [{ rotate: "0deg", opacity: 0.45 }, { rotate: `${i % 2 ? -180 : 180}deg`, opacity: 0.9 }, { rotate: `${i % 2 ? -360 : 360}deg`, opacity: 0.45 }], 6000 + Math.random() * 5000, Math.random(), { direction: "normal", easing: "linear" }));
  return loops;
}

//: **A living tail** (INBOX 601, the owner: "make it smooth and biological.
//: also add more movement and variation to the tail position, behaviour,
//: movement"). Before, the tail was one fixed drawing turned a degree or
//: three about its root by CSS loops, with its tip half turned about a
//: joint a beat behind (`tailWave`): a stiff flame swinging, every cycle
//: the same. Now its centreline bends along its whole length, every frame,
//: as a spine does: the rest centreline sampled at `ATLAS_TAIL_N` points,
//: each step between them turned by the angle the tail has bent through
//: by then (`atlasTailBend`), so the root never moves, the bend grows
//: toward the tip and the outline stays one smooth tapered stem (the same
//: `atlasStem` and widths the drawing has). The angle is a curl along the
//: length (the tail held up, held down, wrapped round) plus a wave that
//: travels from root to tip, and a second, slower one out of step with it.
//: What it does is a behaviour, `ATLAS_TAIL_ACTS`: a lazy sway, a curl
//: (its tip up like a question), a wrap (round toward its feet), a flick
//: (a quick ripple, a second and a half), a wag (pleased), a trail (on the
//: move), a droop (low, asleep) and a stiff hold (startled). The state the
//: rig reads (`atlasLowerState`) picks one by weight (`ATLAS_TAIL_BY_STATE`)
//: and holds it 4 to 9 seconds at random, never the same twice running, so
//: it never repeats; every number eases to the next on a critically damped
//: spring and the wave's phase is carried across a change of speed, so no
//: change is a jump. A slow drift on two clocks that never line up (11.3s,
//: 17.9s) bends it a little more or less all the time. It draws 30 times
//: a second while the figure is on screen and motion is on; off screen,
//: on a hidden tab, with Avatar animation off or under Reduce motion, it
//: rests in its drawn shape and costs nothing. It is the tail's own layer
//: that repaints (one small svg), nothing is laid out.
const ATLAS_TAIL_N = 32;
const ATLAS_TAIL_ACTS = {
  //: curl: radians the tail bends through root to tip (+ is clockwise on
  //: screen: down and round under; - lifts it); amp: the wave's swing,
  //: radians at the tip; period: seconds a wave; k: radians of phase from
  //: root to tip (how many bends it shows at once).
  sway: { curl: 0.15, amp: 0.34, period: 3.9, k: 3.4 },
  curl: { curl: -1.3, amp: 0.19, period: 4.6, k: 2.4 },
  wrap: { curl: 1.1, amp: 0.17, period: 4.9, k: 2.2 },
  flick: { curl: -0.25, amp: 0.62, period: 0.95, k: 4.6, ms: 1500 },
  wag: { curl: -0.4, amp: 0.46, period: 0.66, k: 2.4 },
  trail: { curl: 0.4, amp: 0.22, period: 1.6, k: 3.8 },
  droop: { curl: 0.6, amp: 0.11, period: 5.6, k: 1.8 },
  stiff: { curl: -0.12, amp: 0.08, period: 2.1, k: 2 },
};
const ATLAS_TAIL_BY_STATE = {
  idle: [["sway", 3], ["curl", 2], ["wrap", 1.4], ["flick", 1]],
  walk: [["trail", 1]],
  sit: [["wrap", 2], ["sway", 1], ["curl", 1]],
  lie: [["wrap", 2], ["droop", 1]],
  gesture: [["sway", 2], ["flick", 1]],
  think: [["curl", 2], ["sway", 1]],
  happy: [["wag", 3], ["flick", 1]],
  sad: [["droop", 1]],
  startle: [["stiff", 1]],
};
//: The angle the tail has turned through at `s` (0 at the root, 1 at the
//: tip), in radians, for its state `p` at phase `ph` (`ph2` the second
//: wave's) and the slow drift `drift`. Zero at the root, so the root and
//: its direction never move; the wave's envelope grows along the length.
//: A third, small ripple (`ph3`, on a 1.73s clock no other one shares)
//: swings it nearly as one, rising fast from the root (square root) with
//: a short wave down it (0.8 radians root to tip): the main waves alone
//: can reach their turning points together with their pulls opposed, and
//: atlas601-tail.js read the tip held within 0.75px for 850ms on a quiet
//: machine that way. Weighted to the tip (s squared) the ripple did next
//: to nothing, since the tail curls back on itself and its tip turns about
//: a point close by; with as many bends as the main waves it cancelled
//: itself along the length. With it, and the stretch on the same clock
//: (`atlasTailFrame`), no behaviour holds its tip still over about 0.6s.
function atlasTailBend(s, p, ph, ph2, drift, ph3 = 0) {
  const e = s ** 1.5;
  return (p.curl + drift) * s * s + p.amp * e * Math.sin(ph - p.k * s) + Math.max(0.13, 0.35 * p.amp) * e * Math.sin(ph2 - 1.7 * p.k * s + 0.7) + 0.07 * Math.sqrt(s) * Math.sin(ph3 - 0.8 * s);
}
//: The tail's centreline bent as `bend(s)` says, as a run of cubics
//: through the bent points (Catmull-Rom), each an equal share of the
//: length as `atlasStemSides` samples them; and each sample's turn, for
//: what rides on the tail.
//: `stretch(s)`, when given, scales each step's length: the tail's tip
//: draws out and back a little as it breathes (`atlasTailFrame`).
function atlasTailShape(rest, bend, stretch) {
  const n = rest.length - 1;
  const pts = [rest[0].slice()];
  const turn = [0];
  for (let i = 0; i < n; i += 1) {
    const a = bend((i + 0.5) / n);
    const g = stretch ? stretch((i + 0.5) / n) : 1;
    const dx = (rest[i + 1][0] - rest[i][0]) * g;
    const dy = (rest[i + 1][1] - rest[i][1]) * g;
    const [x, y] = pts[i];
    pts.push([x + dx * Math.cos(a) - dy * Math.sin(a), y + dx * Math.sin(a) + dy * Math.cos(a)]);
    turn.push(bend((i + 1) / n));
  }
  const segs = [];
  for (let i = 0; i < n; i += 1) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(n, i + 2)];
    segs.push([p1[0], p1[1], p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6, p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1]]);
  }
  return { pts, turn, segs };
}
//: The paths the tail is drawn with, for a centreline (the same recipe as
//: `atlasBuild`'s, sampled finer per curve since there are more of them).
function atlasTailPaths(spec, segs) {
  const w = spec.tailWidth;
  const s = 2;
  return {
    body: atlasStem(segs, w, { samples: s, round: !!spec.tailRound }),
    stream: atlasStem(segs, (t) => w(t) * 0.26, { samples: s, shift: (t) => w(t) * 0.22 * Math.sin(Math.PI * 2.6 * t) }),
    silk: atlasStem(segs, (t) => w(t) * 0.24, { samples: s, shift: (t) => -w(t) * 0.3 * Math.sin(Math.PI * 2.6 * t + 1.1) }),
    filaments: (spec.tailFilaments || []).map((k) => {
      const pts = atlasStemSides(segs, () => 0, s, (t) => (w(t) / 2) * k).left;
      const run = pts.slice(Math.round(pts.length * 0.18), Math.round(pts.length * 0.92));
      return `M${atlasFix(run[0][0])} ${atlasFix(run[0][1])}${atlasSmooth(run)}`;
    }).join(""),
  };
}
function atlasTailAttach(box) {
  const spec = ATLAS_LOOKS[box.dataset.atlasLook];
  const svg = box.querySelector("svg.atl-layer-tail:not(.atl-layer-tail-tip)");
  if (!spec?.tailSegsNow || !svg || box.atlasTail) return;
  const id = `atl-${box.dataset.atlasLook}`;
  const segs = spec.tailSegsNow;
  const rest = Array.from({ length: ATLAS_TAIL_N + 1 }, (_, i) => atlasSegsAt(segs, i / ATLAS_TAIL_N));
  const near = (x, y) => {
    let best = 0;
    rest.forEach(([px, py], i) => {
      if (Math.hypot(px - x, py - y) < Math.hypot(rest[best][0] - x, rest[best][1] - y)) best = i;
    });
    return best;
  };
  //: The whole tail in one layer: the tip half's own layer (the old wave)
  //: is hidden, and the root half's masks give way to the root's fade.
  //: The layer's swish and wag give way to the bend (the box's slow flow
  //: and the rig's pose for the state still turn it about its root), and a
  //: mood's or a pose's lift (`--atl-tail`) eases over 1.1s, in and out, as
  //: a tail moves, not the face's 0.2s (INBOX 600: a poke's lift moved its
  //: stars 11px in a frame in the large view). Inline, from here: the boot
  //: stylesheets are at their budget.
  box.querySelector(".atl-lw-tip")?.style.setProperty("display", "none");
  svg.style.setProperty("animation", "none", "important");
  for (const g of svg.querySelectorAll(".atl-tail")) g.style.transition = "transform 1.1s cubic-bezier(0.45, 0, 0.55, 1)";
  const fade = `url(#${id}-tailroot)`;
  for (const el of svg.querySelectorAll(".atl-tail-swish > *")) {
    if (el.matches(".atl-fills .atl-skin")) el.removeAttribute("mask");
    else if (el.tagName === "path") el.setAttribute("mask", fade);
    else el.removeAttribute("mask");
  }
  const fills = svg.querySelector(".atl-fills .atl-tail-swish");
  const core = fills?.querySelector(".atl-tail-core");
  //: What sits at the tip (its glow, its core, its sparks) rides it as one.
  const tipG = core ? atlasMake("g", { class: "atl-tail-tipg" }, core) : null;
  if (core) for (const el of [...core.children]) if (el !== tipG && !el.classList.contains("atl-speck")) tipG.appendChild(el);
  const specks = core?.querySelector(".atl-speck");
  const tail = {
    box,
    svg,
    spec,
    rest,
    paths: {
      edge: svg.querySelector(".atl-edges .atl-tail-swish > .atl-edge"),
      body: fills ? [...fills.querySelectorAll(":scope > :is(.atl-tail-glow, .atl-skin, .atl-tail-galaxy, .atl-tail-edge)")] : [],
      silk: fills?.querySelector(".atl-tail-silk"),
      stream: fills?.querySelector(".atl-tail-stream"),
      filaments: fills?.querySelector(".atl-tail-filament"),
    },
    specks,
    stars: (spec.tailStarsNow || []).map(([x, y, r]) => ({ x, y, r, i: near(x, y) })),
    tipG,
    tipAt: rest[ATLAS_TAIL_N],
    p: Object.fromEntries(Object.entries(ATLAS_TAIL_ACTS.sway).map(([k, v]) => [k, { x: v, v: 0 }])),
    act: "",
    state: "",
    until: 0,
    ph: Math.random() * 6.28,
    ph2: Math.random() * 6.28,
    ph3: Math.random() * 6.28,
    goal: null,
    t0: performance.now() - Math.random() * 20000,
    at: 0,
    raf: 0,
    tick: 0,
    drawn: false,
    settle: 0,
    resting: false,
    sway: null,
  };
  box.atlasTail = tail;
  box.dataset.atlTail = "live";
  atlasTailWake(box);
}
function atlasTailPick(tail, state, now) {
  const list = ATLAS_TAIL_BY_STATE[state] || ATLAS_TAIL_BY_STATE.idle;
  const choices = list.length > 1 ? list.filter(([name]) => name !== tail.act) : list;
  let r = Math.random() * choices.reduce((sum, [, w]) => sum + w, 0);
  let act = choices[0][0];
  for (const [name, w] of choices) {
    r -= w;
    if (r <= 0) {
      act = name;
      break;
    }
  }
  //: Each time a behaviour is taken up it is its own: its swing, its speed
  //: and how far it curls vary a little about the table's (INBOX 601, the
  //: owner: "more movement and variation"), so two sways in a row of the
  //: same state never look alike.
  const base = ATLAS_TAIL_ACTS[act];
  const jit = (lo, hi) => lo + Math.random() * (hi - lo);
  tail.goal = { curl: base.curl + jit(-0.18, 0.18), amp: base.amp * jit(0.8, 1.25), period: base.period * jit(0.85, 1.2), k: base.k * jit(0.85, 1.15) };
  tail.act = act;
  tail.state = state;
  const calm = !base.ms && atlasTailCalm(tail, tail.box);
  tail.until = now + (base.ms || (calm ? 9000 + Math.random() * 9000 : 4000 + Math.random() * 5000));
  tail.settle = now + ATLAS_TAIL_SETTLE_MS;
}
function atlasTailFrame(tail, now) {
  tail.raf = 0;
  const { box, spec } = tail;
  if (!box.isConnected) return;
  //: `data-atlas-hidden`: a hidden window, or the app locked (atlas.js).
  const live = atlasMotionOK(box) && !box.classList.contains("atl-off") && !document.hidden && !document.documentElement.hasAttribute("data-atlas-hidden");
  //: The rings' and the planets' loops run and rest with it (`atlasRingLoops`).
  //: And hold while it is carried or thrown, as its CSS loops do there
  //: (atlas-lazy.css, B87a): drawn every frame then, each one restyles.
  const loops = live && !box.closest("#nm-buddy.nm-buddy-dragging");
  for (const anim of box.atlasLoops || []) if (loops !== (anim.playState === "running")) loops ? anim.play() : anim.pause();
  //: Thirty a second: each draw repaints the tail's layer.
  tail.tick += 1;
  //: The props' own loops, while each is shown (`atlasPropsFrame`).
  atlasPropsFrame(box, live, tail.tick);
  //: And the chest's breath (`atlasBreathFrame`).
  atlasBreathFrame(box, live, now);
  //: Resting on the compositor (`atlasTailRest`): nothing to draw while the
  //: state holds and the act has not run out; the breath and the props
  //: above are all this beat does.
  if (tail.resting) {
    if (live && atlasTailCalm(tail, box) && atlasLowerState(box.closest("#nm-buddy"), box) === tail.state && now < tail.until) {
      tail.raf = setTimeout(() => atlasTailFrame(tail, performance.now()), ATLAS_TAIL_REST_BEAT_MS);
      return;
    }
    atlasTailUnrest(tail);
  }
  if (live && tail.tick % 2 && tail.drawn && !tail.calm) {
    tail.raf = requestAnimationFrame((t) => atlasTailFrame(tail, t));
    return;
  }
  //: The clock runs at the wall's speed up to half a second a frame, so a
  //: slow frame does not slow the tail (atlas601-tail.js, under load: at
  //: four frames a second a 0.1s cap ran it at 40% and read the tip still
  //: for over a second); the springs step in thirtieths, where they are
  //: stable, however long the frame.
  const dt = tail.at ? Math.min(0.5, (now - tail.at) / 1000) : 1 / 30;
  tail.at = now;
  if (live) {
    const buddy = box.closest("#nm-buddy");
    const state = atlasLowerState(buddy, box);
    if (state !== tail.state || now >= tail.until) atlasTailPick(tail, state, now);
    const goal = tail.goal || ATLAS_TAIL_ACTS[tail.act];
    //: Critically damped springs: a flick comes in fast, the rest ease.
    const w = tail.act === "flick" || tail.act === "stiff" ? 7 : 2.6;
    const steps = Math.ceil(dt * 30);
    for (const [k, j] of Object.entries(tail.p)) {
      if (!(k in goal)) continue;
      for (let i = 0; i < steps; i += 1) {
        j.v += (w * w * (goal[k] - j.x) - 2 * w * j.v) * (dt / steps);
        j.x += j.v * (dt / steps);
      }
    }
    tail.ph += (2 * Math.PI * dt) / tail.p.period.x;
    //: The second wave keeps its own steady clock (2.9s), whatever the first
    //: does, so the tip is never still at both waves' turning points.
    tail.ph2 += (2 * Math.PI * dt) / 2.9;
    tail.ph3 += (2 * Math.PI * dt) / 1.73;
  }
  const secs = (now - tail.t0) / 1000;
  const p = Object.fromEntries(Object.entries(tail.p).map(([k, j]) => [k, live ? j.x : k === "curl" || k === "amp" ? 0 : j.x]));
  const drift = live ? 0.13 * Math.sin((2 * Math.PI * secs) / 11.3) + 0.08 * Math.sin((2 * Math.PI * secs) / 17.9 + 1.3) : 0;
  //: The ripple's clock also draws the tail out and back along its length
  //: (3%, a quarter turn behind the ripple), so its tip goes round a small
  //: ellipse that the waves can never all cancel: bending alone moves the
  //: tip one way only, across the tail, and dwells at each turning point
  //: (a stepped 60s of `stiff` read 1.4s still at the tip with bends only).
  const stretch = live ? () => 1 + 0.03 * Math.cos(tail.ph3) : null;
  atlasTailDraw(tail, (s) => atlasTailBend(s, p, live ? tail.ph : 0, live ? tail.ph2 : 0, drift, live ? tail.ph3 : 0), stretch);
  tail.drawn = true;
  //: **At rest in its corner, fifteen draws a second, not thirty** (Brief 34
  //: decision 7: the companion must never cost the rest of the app).
  //: Measured at 1440 on the dashboard (companionperf.js IDLE=1, a loaded
  //: machine): the corner Atlas idle cost 35s of main thread a minute and
  //: 1,399 layouts, against 0.5s and 3 with the companion off, most of it
  //: this loop: a frame asked for sixty times a second to draw the tail's
  //: paths on every other one. Resting, sitting, lying, thinking or low,
  //: the tail moves on clocks of 1.7s and longer, so fifteen steps a second
  //: read as the same sway, and a timer between them asks for no frames.
  //: Walking, carried, gesturing, startled or glad, and always in the large
  //: view, where it is the one thing on screen, it keeps the frame loop.
  tail.calm = live && atlasTailCalm(tail, box);
  if (live && tail.calm && now >= tail.settle) {
    atlasTailRest(tail, p);
    tail.raf = setTimeout(() => atlasTailFrame(tail, performance.now()), ATLAS_TAIL_REST_BEAT_MS);
  } else if (live && tail.calm) {
    tail.raf = setTimeout(() => {
      tail.raf = requestAnimationFrame((t) => atlasTailFrame(tail, t));
    }, ATLAS_TAIL_CALM_MS);
  } else if (live) tail.raf = requestAnimationFrame((t) => atlasTailFrame(tail, t));
  else tail.at = 0;
}
const ATLAS_TAIL_CALM = new Set(["idle", "sit", "lie", "think", "sad"]);
const ATLAS_TAIL_CALM_MS = 66;
function atlasTailCalm(tail, box) {
  return ATLAS_TAIL_CALM.has(tail.state) && !!box.closest("#nm-buddy") && !box.closest(".nm-viewer-figure");
}
//: **At rest the tail goes to the compositor** (Brief 34 continues, step 2;
//: decision 7, under 1ms a minute beyond the face): fifteen path draws a
//: second were about 770 layouts and 2s of script a minute at rest in the
//: corner. A calm act now draws for `ATLAS_TAIL_SETTLE_MS` while its springs
//: ease into it (no snap), then holds that drawn shape and sways the tail's
//: own layer root about its root, a Web Animation of `transform` only (the
//: companion's pacer leaves layer roots alone), the act's swing and period
//: from its table, so a curl sways slow and small and a sway wide. Calm acts
//: hold 9 to 18s here, not 4 to 9, so the redraws are rare; a new act, a new
//: state, the large view or a walk takes the live loop back, the layer
//: easing home from wherever its sway was. `data-atl-tail` says which.
const ATLAS_TAIL_SETTLE_MS = 1600;
//: The resting beat is also the chest's (`atlasBreathFrame`): at 2.5 steps a
//: second its 0.7px swell moves under 0.2px a step, and each step is a style
//: recalc and a layout of the body's drawing (recalc.js: the breath at 10 a
//: second was 550 recalcs and 200 layouts a minute of Atlas at rest).
const ATLAS_TAIL_REST_BEAT_MS = 400;
function atlasTailRest(tail, p) {
  const { box, svg } = tail;
  tail.resting = true;
  box.dataset.atlTail = "rest";
  if (!svg?.animate) return;
  const vb = svg.viewBox?.baseVal;
  const [rx, ry] = tail.rest[0];
  if (vb?.width) svg.style.transformOrigin = `${atlasFix(((rx - vb.x) / vb.width) * 100)}% ${atlasFix(((ry - vb.y) / vb.height) * 100)}%`;
  const deg = atlasFix(Math.min(7, Math.max(1.5, (p.amp * 180) / Math.PI * 0.3)));
  const at = (d, k) => ({ transform: `rotate(${d}deg) scale(${k})` });
  tail.sway = svg.animate([at(0, 1), at(deg, 1.015), at(0, 1), at(-deg, 0.99), at(0, 1)], {
    duration: Math.round(Math.max(2.4, p.period) * 1000), iterations: Infinity, easing: "ease-in-out",
  });
}
function atlasTailUnrest(tail) {
  const { box, svg } = tail;
  tail.resting = false;
  box.dataset.atlTail = "live";
  if (!tail.sway) return;
  const from = getComputedStyle(svg).transform;
  tail.sway.cancel();
  tail.sway = null;
  if (from && from !== "none") svg.animate([{ transform: from }, { transform: "none" }], { duration: 400, easing: "cubic-bezier(0.33, 0, 0.2, 1)" });
}
function atlasTailDraw(tail, bend, stretch) {
  const { pts, turn, segs } = atlasTailShape(tail.rest, bend, stretch);
  const d = atlasTailPaths(tail.spec, segs);
  const { paths } = tail;
  paths.edge?.setAttribute("d", d.body);
  for (const el of paths.body) el.setAttribute("d", d.body);
  paths.silk?.setAttribute("d", d.silk);
  paths.stream?.setAttribute("d", d.stream);
  if (paths.filaments) paths.filaments.setAttribute("d", d.filaments);
  const f = atlasFix;
  //: Each star rides the sample nearest it, turned with it.
  if (tail.specks) {
    tail.specks.setAttribute("d", tail.stars.map(({ x, y, r, i }) => {
      const a = turn[i];
      const ox = x - tail.rest[i][0];
      const oy = y - tail.rest[i][1];
      const sx = pts[i][0] + ox * Math.cos(a) - oy * Math.sin(a);
      const sy = pts[i][1] + ox * Math.sin(a) + oy * Math.cos(a);
      return `M${f(sx - r)} ${f(sy)}a${r} ${r} 0 1 0 ${f(2 * r)} 0a${r} ${r} 0 1 0 ${f(-2 * r)} 0`;
    }).join(""));
  }
  if (tail.tipG) {
    const [tx, ty] = tail.tipAt;
    const [ex, ey] = pts[pts.length - 1];
    tail.tipG.setAttribute("transform", `translate(${f(ex - tx)} ${f(ey - ty)}) rotate(${f((turn[turn.length - 1] * 180) / Math.PI)} ${f(tx)} ${f(ty)})`);
  }
  tail.shape = { pts, turn };
}

//: **The props and icons have a life of their own** (INBOX 623, the owner:
//: "can the atlas agent also animate the props and icons as well for
//: various actions and behaviours??"). Each prop Atlas holds or shows is
//: drawn in the arm, the head or the body it belongs to, so it already
//: moves with the hand and the body (and the rig's and the act's hand-overs
//: ease it, 250 to 500ms); here each gets a small motion of its own while it
//: is shown: the lantern swings on its string and its star flickers, the
//: bell sways from its top, the offline link sparks, the music's cups pulse,
//: the moon on its ear rocks, the reading lenses catch the light, the book's
//: pages lift and its constellation twinkles, the map's stars twinkle and
//: the map rocks on its corner, the coil breathes, the startle's bubble
//: wobbles and its "!" pops. Every turn is about the prop's grip (its
//: string's top, its hinge, its corner, the ear), so the grip never leaves
//: what holds it (atlas623-props.js). Each loop starts and ends at rest, so
//: a still frame is the drawn pose: with Avatar animation off, under reduce
//: motion, off screen or on a hidden tab they rest there (`atlasPropsFrame`).
//: Web Animations of transform, rotate, scale and opacity only (the boot
//: stylesheets are at their budget), run only while the prop is shown.
//: [selector, grip [x, y] in the drawing's units (null: the element's own
//: box, `box` its centre, `top` its top middle), frames, ms, stagger]
const ATLAS_PROP_LOOPS = [
  //: Hand props: the lantern on its string (48.2, 61), the bell from its top.
  [".nmp-lantern", [48.2, 61], [{ rotate: "0deg" }, { rotate: "6deg" }, { rotate: "0deg" }, { rotate: "-5deg" }, { rotate: "0deg" }], 2600, 0],
  [".nmp-lantern .atl-sparkle", "box", [{ opacity: 1, scale: 1 }, { opacity: 0.55, scale: 0.86 }, { opacity: 0.95, scale: 1.08 }, { opacity: 0.7, scale: 0.94 }, { opacity: 1, scale: 1 }], 900, 0],
  [".nmp-bell", "top", [{ rotate: "0deg" }, { rotate: "4deg" }, { rotate: "0deg" }, { rotate: "-4deg" }, { rotate: "0deg" }], 2200, 0],
  [".nmp-cable .atl-prop-zap", null, [{ opacity: 1 }, { opacity: 0.15 }, { opacity: 1 }, { opacity: 0.4 }, { opacity: 1 }], 700, 0],
  //: Head props: the cups' glow to a beat, the moon rocking from its top
  //: (hung on the ear), the lenses' light.
  [".nmp-headphones .atl-prop-cup-glow", "box", [{ opacity: 1, scale: 1 }, { opacity: 0.5, scale: 0.75 }, { opacity: 1, scale: 1 }], 1000, 0.5],
  [".nmp-nightcap", "top", [{ rotate: "0deg" }, { rotate: "-7deg" }, { rotate: "0deg" }, { rotate: "5deg" }, { rotate: "0deg" }], 4200, 0],
  [".nmp-glasses .atl-prop-lens", null, [{ opacity: 1 }, { opacity: 0.72 }, { opacity: 1 }], 3200, 0.4],
  //: Ground props: the book's right page lifts from the spine and its left
  //: settles, its stars twinkle; the map rocks on its lower corner, its
  //: stars twinkle; the coil breathes about its middle.
  [".nmp-book .atl-prop-page:nth-of-type(2)", [31, 59.3], [{ scale: "1 1" }, { scale: "1 0.86" }, { scale: "1 1" }], 1700, 0],
  [".nmp-book .atl-prop-page:nth-of-type(1)", [31, 59.3], [{ scale: "1 1" }, { scale: "1 0.95" }, { scale: "1 1" }], 2300, 0],
  [".nmp-book .atl-node-dot", null, [{ opacity: 1 }, { opacity: 0.3 }, { opacity: 1 }], 1600, 0.2],
  [".nmp-map", [42, 92.4], [{ rotate: "0deg" }, { rotate: "1.6deg" }, { rotate: "0deg" }, { rotate: "-1.2deg" }, { rotate: "0deg" }], 3800, 0],
  [".nmp-map .atl-node-dot", null, [{ opacity: 1 }, { opacity: 0.3 }, { opacity: 1 }], 1800, 0.25],
  [".nmp-coil", [31, 72], [{ scale: "1 1" }, { scale: "1.03 1.06" }, { scale: "1 1" }], 3000, 0],
  //: Icons: the startle's bubble wobbles about its middle, its "!" pops.
  [".nmp-bubble", "box", [{ scale: "1 1" }, { scale: "1.03 0.97" }, { scale: "0.98 1.02" }, { scale: "1 1" }], 900, 0],
  [".atl-fx-bang", [10, 10], [{ scale: 1, rotate: "0deg" }, { scale: 1.18, rotate: "-6deg" }, { scale: 1, rotate: "0deg" }], 600, 0],
];
function atlasPropLoops(box) {
  if (!box.animate) return [];
  const loops = [];
  for (const [sel, grip, frames, ms, stagger] of ATLAS_PROP_LOOPS) {
    box.querySelectorAll(sel).forEach((el, k) => {
      if (grip === "box" || grip === "top") {
        el.style.transformBox = "fill-box";
        el.style.transformOrigin = grip === "box" ? "50% 50%" : "50% 0";
      } else if (grip) el.style.transformOrigin = `${grip[0]}px ${grip[1]}px`;
      const anim = el.animate(frames, { duration: ms, iterations: Infinity, easing: "ease-in-out", id: "atl-prop" });
      anim.cancel();
      //: Staggered rows (a constellation's stars) start a step apart.
      loops.push({ anim, el, root: el.closest(".nmp, .atl-fx-bang") || el, lag: (k * stagger * ms) % ms, on: false });
    });
  }
  return loops;
}
//: Each loop runs while its prop shows and motion is live, and is cancelled
//: (its drawn pose) otherwise, not paused: the companion's pacer
//: (`nameMarkBuddyTempo`) holds and steps by hand whatever animates inside
//: its drawing while it idles, so a paused loop would still be stepped, and
//: playing state is the pacer's to set while one runs. Read every eighth
//: frame of the tail's loop: a prop's own fade-in is 0.16s, so it is moving
//: by the time it is whole.
//: A prop shows by a class (an act, a mood), which wakes the rig
//: (`atlasRigWake`, `box.atlasDirtyAt`): it is looked for in the 1.5 s after
//: a wake, its fade's time and more, and not again until the next (B87a: an
//: opacity read every eighth frame was 22 forced restyles in a 1.3 s carry).
function atlasPropsFrame(box, live, tick) {
  const loops = box.atlasPropLoops;
  if (!loops?.length || (live && tick % 8)) return;
  if (!live) box.atlasPropsAt = 0;
  else if (box.atlasPropsAt > (box.atlasDirtyAt || 0) + 1500) return;
  else box.atlasPropsAt = performance.now();
  const shown = new Map();
  for (const loop of loops) {
    if (!shown.has(loop.root)) shown.set(loop.root, live && +getComputedStyle(loop.root).opacity > 0.05);
    const on = shown.get(loop.root);
    if (on === loop.on) continue;
    loop.on = on;
    if (on) {
      loop.anim.play();
      loop.anim.currentTime = loop.lag;
    } else loop.anim.cancel();
  }
}

//: **The chest breathes** (INBOX 687, the owner: "does the companion or at
//: least atlas have a subtle breathing look??"). It did not, to the eye:
//: sampled at rest for 10 s (breath687.js), the layered figure's breath, a
//: 0.45px lift and a 0.6% widening of the whole upper body (`.atl-lw-breathe`,
//: the CSS), swung the torso 0.1px on the companion and 0.2px in the large
//: view, and the head as much. The torso now swells 3.5% wide and 2.5% tall
//: about the hips while the head, the arms and the face, other groups, keep
//: their size: 0.7px on the companion, 1.5px in the large view.
//:
//: **Here, ten times a second, not a CSS animation.** It is inside the body's
//: drawing, so every step repaints that layer. As a CSS loop it ran at the
//: frame rate in the large view, which nothing paces, and took the view from
//: 53 frames a second to 20 to 31 on the sweep's machine. Ten a second is
//: the companion pacer's rate for what animates inside an Atlas layer
//: (`nameMarkBuddyTempo`), and a step of a tenth of a second moves the chest
//: about a tenth of a pixel even at 2.2 times, so it reads as the same
//: breath. By the clock, not by frames, so a slow machine does not step it
//: more often than that. It rides the tail's loop, which already knows when the
//: figure is off screen, on a hidden tab, or still by setting (Avatar
//: animation Off, Reduce motion, the companion's own Full motion), and puts
//: the chest back at rest then.
//:
//: On the rise's clock: the swell takes its phase from the box's own
//: animation, so the chest fills as the shoulders lift. Written as the
//: individual `scale`, so a transform a gesture or a mood gives the torso
//: composes with it rather than being overwritten.
const ATLAS_BREATH_SWELL = [0.035, 0.025];
const ATLAS_BREATH_STEP_MS = 100;
function atlasBreathFrame(box, live, now) {
  if (live && now - (box.atlasBreathAt || 0) < ATLAS_BREATH_STEP_MS) return;
  box.atlasBreathAt = live ? now : 0;
  box.atlasTorsos ||= [...box.querySelectorAll(".atl-layer-body .nmb-torso")];
  let k = 0;
  if (live) {
    //: The rise's clock is read once in a while, not every step, and run on
    //: by the wall's between: `getAnimations`, and an animation's
    //: `playState` and `currentTime`, each bring the page's style up to date
    //: to answer (B87a: 81 forced restyles and layouts in 1.3 s of a carry).
    if (now > (box.atlasRiseAt || 0)) {
      const rise = box.querySelector(".atl-lw-breathe")?.getAnimations()[0] || null;
      const at = rise && rise.playState !== "idle" ? rise.currentTime : null;
      box.atlasRisePeriod = at !== null ? +rise.effect.getComputedTiming().duration : 0;
      box.atlasRiseOff = at !== null ? +at - now : null;
      box.atlasRiseAt = now + 5000;
    }
    const rise = box.atlasRiseOff !== null && box.atlasRisePeriod > 0;
    const period = rise ? box.atlasRisePeriod : box.dataset.atlasLook === "feminine" ? 4000 : 4600;
    const at = rise ? now + box.atlasRiseOff : now;
    k = (1 - Math.cos((2 * Math.PI * at) / period)) / 2;
  }
  const scale = k ? `${(1 + ATLAS_BREATH_SWELL[0] * k).toFixed(4)} ${(1 + ATLAS_BREATH_SWELL[1] * k).toFixed(4)}` : "";
  for (const el of box.atlasTorsos) if (el.style.scale !== scale) el.style.scale = scale;
}

//: **The lower body by what it is doing** (INBOX 575, the owner: "have the
//: lower body of both atlas avatars change around in position and how it
//: is sitting ect with different variations and changes based off the
//: current action or behaviour"). Her dress and his cloak (with her wisps,
//: which wrap the dress) and both tails take a pose per state, on top of
//: the pose's own CSS: each variant is [turn about the hips, width, length,
//: lean (skew), the tail's turn], in degrees and scales; `ms` and `ease`
//: are the change's time and curve (a curve past 1 overshoots and settles,
//: a flick or a snap; an ease in and out is a slow curl). A walk's turns and lean take
//: the way it goes (it trails behind and stretches). One variant is picked
//: at random as a state begins, and at rest a new one every 8 to 14
//: seconds, so no two repeats look alike.
//: INBOX 615 and 619 (the owner: "the lower body ... slightly misaligned",
//: "her lower body actually rotates halfway off her upperbody"): sitting,
//: lying and startled, the lower body turned 8 to 16 degrees off the torso
//: (and the CSS 42 more lying down); it turns at most 4 now, about the join,
//: and takes its width from the torso there, so the two read as one chain.
const ATLAS_LOWER_STATES = {
  idle: { ms: 900, ease: "cubic-bezier(0.45, 0, 0.35, 1)", v: [[-2.5, 1, 1, 2, -5], [2, 1, 1.02, -2, 4], [3.5, 0.98, 1, 1, 7], [-1, 1.02, 0.99, -3, -2]] },
  walk: { ms: 450, ease: "cubic-bezier(0.34, 1.3, 0.64, 1)", v: [[-9, 0.94, 1.08, 6, -12], [-7, 0.95, 1.1, 8, -9], [-11, 0.93, 1.06, 4, -15]] },
  sit: { ms: 550, ease: "cubic-bezier(0.34, 1.25, 0.6, 1)", v: [[3, 1.1, 0.86, -3, -14], [-3, 1.08, 0.88, 3, 14], [2, 1.12, 0.84, -2, -10]] },
  lie: { ms: 600, ease: "cubic-bezier(0.4, 1.15, 0.6, 1)", v: [[3, 1, 0.86, -3, 24], [2, 1.02, 0.9, -2, 30], [4, 0.99, 0.88, -4, 19]] },
  gesture: { ms: 350, ease: "cubic-bezier(0.3, 1.6, 0.6, 1)", v: [[-5, 0.98, 0.95, 4, 9], [-3, 1, 0.94, 6, 12], [-6, 0.97, 0.96, 3, 7]] },
  think: { ms: 900, ease: "cubic-bezier(0.45, 0, 0.55, 1)", v: [[6, 1, 0.97, -4, 12], [4, 0.99, 0.96, -6, 16], [-3, 1, 0.98, 3, 9]] },
  happy: { ms: 380, ease: "cubic-bezier(0.25, 1.8, 0.5, 1)", v: [[-6, 1.02, 0.94, 5, -10], [5, 1.02, 0.95, -5, -14], [-4, 1.03, 0.93, 3, -8]] },
  sad: { ms: 800, ease: "cubic-bezier(0.5, 0, 0.6, 1)", v: [[1.5, 0.96, 1.07, -1, 16], [-1.5, 0.97, 1.06, 1, 20], [0.5, 0.95, 1.08, -2, 24]] },
  startle: { ms: 260, ease: "cubic-bezier(0.2, 2, 0.4, 1)", v: [[-4, 0.94, 0.9, 4, -18], [-3, 0.95, 0.92, 5, -22], [3, 0.93, 0.91, -4, -14]] },
};
//: The hair's turn about the crown and the nebula stream's [turn, width,
//: height] about the figure's middle, per state (INBOX 575, the owner:
//: "both atlas avatars have a tail as well, same with the hair, and the
//: nebular stream ... dynamically animated and changed"), a variant each
//: as the lower body's; a walk's turn takes the way it goes.
const ATLAS_HAIR_STATES = { idle: [0, 1.6, -1.4, 0.8], walk: [-5, -4, -6], sit: [2, 1, 3], lie: [4, 5, 3], gesture: [-3, -2, -4], think: [2.5, 1.5, 3.5], happy: [-3.5, -2.5, -4], sad: [4, 5, 6], startle: [-6, -7, -5] };
const ATLAS_NEB_STATES = {
  idle: [[0, 1, 1], [2, 1.02, 0.98], [-2, 0.98, 1.02], [1, 1.01, 1]],
  walk: [[-4, 1.05, 0.95], [-3, 1.06, 0.94], [-5, 1.04, 0.96]],
  sit: [[3, 1.06, 0.9], [-3, 1.08, 0.88], [1, 1.07, 0.89]],
  lie: [[6, 1.04, 0.86], [4, 1.06, 0.84], [8, 1.03, 0.87]],
  gesture: [[-2, 1.03, 1.03], [-3, 1.02, 1.04], [-1, 1.04, 1.02]],
  think: [[5, 0.97, 1], [7, 0.96, 1.01], [3, 0.98, 0.99]],
  happy: [[-3, 1.04, 1.04], [3, 1.05, 1.03], [-2, 1.03, 1.05]],
  sad: [[2, 0.97, 0.94], [-1, 0.96, 0.95], [1, 0.95, 0.96]],
  startle: [[-6, 1.08, 1.08], [-5, 1.1, 1.06], [-7, 1.07, 1.09]],
};
//: The rig's lower body (atlas.js, `atlasRigAttach`, which makes the rest of
//: the rig at once): the boxes the state's pose turns, attached when this
//: file arrives; until then the lower body stands in its drawn pose.
function atlasRigLowerAttach(box) {
  const rig = box.atlasRig;
  if (!rig || rig.lower) return;
  rig.lower = {
    boxes: [...box.querySelectorAll(".atl-lw-pose-lower")],
    wisps: [...box.querySelectorAll(".atl-lw-pose-wisps, .atl-lw-pose-wisps-back, .atl-lw-pose-glint-a, .atl-lw-pose-glint-b")],
    tails: [...box.querySelectorAll(".atl-lw-pose-tail")],
    hair: [...box.querySelectorAll(".atl-lw-pose-hair")],
    neb: [...box.querySelectorAll(".atl-lw-pose-neb, .atl-lw-pose-neb-front")],
    state: "",
    variant: 0,
    last: {},
    at: 0,
    shown: "",
    timer: 0,
  };
  atlasRigWake(box);
}
//: The lower body's pose for the state: its variant (a new one as the
//: state begins, and every 8 to 14 seconds at rest, on a timer), and the
//: way a walk goes. Each part is a box of its own, and the change is a CSS
//: transition on it, run by the compositor: the state's own time and
//: curve, the tail and the hair a beat later and longer (follow-through).
//: A change mid-way is taken up from where the part is, so nothing snaps.
function atlasRigLower(rig, now, live, buddy) {
  const low = rig.lower;
  if (!low || !(low.boxes.length || low.tails.length || low.hair.length)) return;
  const state = atlasLowerState(buddy, rig.box);
  const spec = ATLAS_LOWER_STATES[state];
  const fresh = state !== low.state;
  if (fresh || (live && state === "idle" && now >= low.at)) {
    //: Reduced motion keeps each state's first pose and no idle variation.
    const pick = live ? Math.floor(Math.random() * spec.v.length) : 0;
    //: Never the one it took the last time it was in this state (Brief 88:
    //: three or more variants per pose, never the last), on entering it
    //: as well as at rest; reduced motion keeps the first.
    const last = low.last[state] ?? -1;
    low.variant = live && spec.v.length > 1 && pick === last ? (pick + 1 + Math.floor(Math.random() * (spec.v.length - 1))) % spec.v.length : pick;
    low.last[state] = low.variant;
    low.state = state;
    low.at = now + 8000 + Math.random() * 6000;
  }
  clearTimeout(low.timer);
  //: The next idle variant, unless the tab is hidden or the figure gone or
  //: off screen then (it waits, and does nothing meanwhile).
  const next = () => {
    if (!rig.box.isConnected) return;
    if (document.hidden || rig.box.classList.contains("atl-off")) low.timer = setTimeout(next, 4000);
    else atlasRigLower(rig, performance.now(), atlasMotionOK(rig.box), buddy);
  };
  if (live && state === "idle") low.timer = setTimeout(next, low.at - now + 10);
  const way = state === "walk" ? (parseFloat(buddy?.style.getPropertyValue("--nmb-lean")) < 0 ? -1 : 1) : 1;
  const [rot, sx, sy, skew, tail] = spec.v[low.variant] || spec.v[0];
  const hairs = ATLAS_HAIR_STATES[state];
  const [neb, nsx, nsy] = ATLAS_NEB_STATES[state][low.variant % ATLAS_NEB_STATES[state].length];
  const hair = hairs[low.variant % hairs.length] * way;
  const pose = (k) => `rotate(${atlasFix(rot * way * k)}deg) skewX(${atlasFix(skew * way * k)}deg) scale(${(1 + (sx - 1) * k).toFixed(3)}, ${(1 + (sy - 1) * k).toFixed(3)})`;
  const key = `${state} ${low.variant} ${way} ${live}`;
  if (key === low.shown) return;
  low.shown = key;
  const go = (el, transform, lag = 0) => {
    el.style.transition = live ? `transform ${spec.ms + lag * 2}ms ${spec.ease} ${lag}ms` : "none";
    el.style.transform = transform;
  };
  //: The lower body's own box shears about the join rather than turning
  //: (INBOX 615): a turn, even about the join, moves the outline's sides up
  //: and down there, and where they slope that is a step against the torso
  //: (atlas615-join.js: 1.07 to 1.49px at 2.2x at rest); a shear leaves
  //: the join's row where it is and swings the hem. At 0.4 of the pose's
  //: lean and half its stretch: the torso's fade is three units deep, and a
  //: startle's full 8 degrees still opened 1.8px there. The tails and her
  //: wisps, which leave the body, take the whole pose.
  for (const el of low.boxes) go(el, `skewX(${atlasFix((skew - rot) * way * 0.4)}deg) scale(1, ${(1 + (sy - 1) * 0.5).toFixed(3)})`);
  for (const el of low.wisps) go(el, pose(0.7), 40);
  for (const el of low.tails) go(el, `rotate(${atlasFix(tail * way)}deg)`, 70);
  for (const el of low.hair) go(el, `rotate(${atlasFix(hair)}deg)`, 90);
  //: The stream's two halves move as one ribbon.
  for (const el of low.neb) go(el, `rotate(${atlasFix(neb * way)}deg) scale(${nsx}, ${nsy})`, 120);
}
