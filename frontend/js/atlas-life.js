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
(() => {
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
  //: on a hidden tab, with Avatar animation off or under reduced motion, it
  //: rests in its drawn shape and costs nothing. It is the tail's own layer
  //: that repaints (one small svg), nothing is laid out.
  const ATLAS_TAIL_N = 32;
  const ATLAS_TAIL_ACTS = {
    //: curl: radians the tail bends through root to tip (+ is clockwise on
    //: screen: down and round under; - lifts it); amp: the wave's swing,
    //: radians at the tip; period: seconds a wave; k: radians of phase from
    //: root to tip (how many bends it shows at once).
    //: tip: an extra bend (radians) over the last third (a hook); env: the wave's envelope exponent along the
    //: length (1.5 whole tail; high, only the tip moves). Only `sway` states them (the springs are built from its keys).
    sway: { curl: 0.15, amp: 0.34, period: 3.9, k: 3.4, tip: 0, env: 1.5 },
    curl: { curl: -1.3, amp: 0.19, period: 4.6, k: 2.4 },
    wrap: { curl: 1.1, amp: 0.17, period: 4.9, k: 2.2 },
    flick: { curl: -0.25, amp: 0.62, period: 0.95, k: 4.6, ms: 1500 },
    wag: { curl: -0.4, amp: 0.46, period: 0.66, k: 2.4 },
    trail: { curl: 0.4, amp: 0.22, period: 1.6, k: 3.8 },
    droop: { curl: 0.6, amp: 0.11, period: 5.6, k: 1.8 },
    stiff: { curl: -0.12, amp: 0.08, period: 2.1, k: 2 },
    //: atlascat-1108 C2 and C3: the question-mark hook, the tip coiled round a prop, a slow thump, a shiver, tucked in,
    //: a figure of eight, a tip twitch, level for balance, and curled under the head.
    hook: { curl: -0.9, amp: 0.1, period: 4.4, k: 2, tip: 1.4 },
    coil_hold: { curl: 1.3, amp: 0.06, period: 6, k: 1.6, tip: 1.2 },
    thump: { curl: 0.3, amp: 0.3, period: 1.4, k: 1.2 },
    shiver: { curl: 0, amp: 0.08, period: 0.12, k: 5, ms: 1600 },
    tuck: { curl: 1.6, amp: 0.05, period: 6, k: 1.6, tip: 0.4 },
    loop8: { curl: -0.2, amp: 0.55, period: 2.2, k: 2.6 },
    tip_twitch: { curl: 0.25, amp: 0.2, period: 0.9, k: 3.4, env: 6 },
    balance: { curl: 0, amp: 0.06, period: 2.6, k: 2 },
    pillow: { curl: 1.8, amp: 0.05, period: 7, k: 1.6, tip: 0.9 },
  };
  const ATLAS_TAIL_BY_STATE = {
    idle: [["sway", 3], ["curl", 2], ["wrap", 1.4], ["flick", 1], ["tip_twitch", 0.8]],
    walk: [["trail", 1]],
    sit: [["wrap", 2], ["sway", 1], ["curl", 1]],
    lie: [["wrap", 2], ["droop", 1], ["pillow", 2]],
    gesture: [["sway", 2], ["flick", 1]],
    think: [["curl", 2], ["sway", 1], ["tip_twitch", 2]],
    happy: [["wag", 3], ["flick", 1], ["loop8", 1.5]],
    sad: [["droop", 1], ["tuck", 1.5]],
    startle: [["stiff", 2], ["shiver", 1]],
    //: The lower body's own states (atlascat-1108 C5, `atlasRigLower.spell`) pick the tail that goes with them.
    glide: [["balance", 2], ["trail", 1]],
    lounge: [["coil_hold", 2], ["wrap", 1]],
    billow: [["trail", 1]],
    coil: [["wrap", 2], ["tuck", 1]],
    ripple_calm: [["sway", 2], ["curl", 1]],
    flutter: [["wag", 1]],
    pool: [["thump", 2], ["wrap", 1]],
    hem_kick: [["wag", 2], ["flick", 1]],
    spiral: [["loop8", 1]],
    fall: [["shiver", 2], ["flick", 1]],
    heavy: [["droop", 2], ["tuck", 1]],
  };
  //: Moods that pick a tail of their own while the lower body is plain (idle or sitting): a curious one hooks it, a shy
  //: one tucks it in, a worried one shivers, a drowsy one curls it under its head.
  atlasTailPick.byMood = { curious: [["hook", 3], ["curl", 1]], confused: [["hook", 2], ["sway", 1]], shy: [["tuck", 1]], worried: [["shiver", 1], ["droop", 1]], sleepy: [["pillow", 2], ["droop", 1]] };
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
  function atlasTailBend(s, p, ph, ph2, drift, ph3 = 0, follow = 0) {
    const e = s ** (p.env || 1.5);
    const hook = (p.tip || 0) * Math.max(0, (s - 0.62) / 0.38) ** 2;
    return hook + (p.curl + drift + follow) * s * s + p.amp * e * Math.sin(ph - p.k * s) + Math.max(0.13, 0.35 * p.amp) * e * Math.sin(ph2 - 1.7 * p.k * s + 0.7) + 0.07 * Math.sqrt(s) * Math.sin(ph3 - 0.8 * s);
  }
  //: **Follow-through** (INBOX 1670, "its tail needs better and more realistic movement and
  //: physics"): a chain of three springs, each pulled toward the one before it and thrown by the
  //: companion's acceleration, so the tail streams behind a start, swings past on a stop and
  //: round a turn, and settles. Its last link (px) becomes a bend (radians) added to the curl,
  //: which the tail's own acts ride on. Same constants as the desktop companion's `Trail`
  //: (`core/overlay/behaviour.py`). At rest it is exactly 0 and costs a few multiplies a draw.
  function atlasTailFollow(tail, dt, x, y = 0) {
    const f = (tail.follow ||= { pos: [0, 0, 0], vel: [0, 0, 0], x, v: 0, lift: [0, 0, 0], lvel: [0, 0, 0], y, vy: 0 });
    if (!Number.isFinite(x) || dt <= 0) return 0;
    const v = (x - f.x) / dt;
    const vy = Number.isFinite(y) ? (y - f.y) / dt : 0;
    const A = atlasTailFollow.springs;
    const n = Math.max(1, Math.ceil(dt / 0.02));
    atlasTailFollow.chain(f.pos, f.vel, (v - f.v) / dt, A.kick, A.max, dt / n, n);
    //: The vertical chain (INBOX 1719 b): a landing or a hop throws the tip down, then up; softer than the sideways one.
    atlasTailFollow.chain(f.lift, f.lvel, (vy - f.vy) / dt, A.liftKick, A.liftMax, dt / n, n);
    f.x = x;
    f.v = v;
    f.y = Number.isFinite(y) ? y : f.y;
    f.vy = vy;
    return (f.pos[A.links - 1] / A.max) * A.bend + (f.lift[A.links - 1] / A.liftMax) * A.liftBend;
  }
  //: One spring chain advanced `n` steps of `h` seconds, thrown by `accel`; the same springs as the desktop's `Trail`.
  atlasTailFollow.chain = (pos, vel, accel, kick, max, h, n) => {
    const A = atlasTailFollow.springs;
    const push = Math.max(-4000, Math.min(4000, accel)) * kick * 0.01;
    for (let k = 0; k < n; k += 1) {
      let prev = 0;
      for (let i = 0; i < A.links; i += 1) {
        vel[i] += (A.stiff * (prev - pos[i]) - A.damp * vel[i] - push * (1 + i)) * h;
        pos[i] = Math.max(-max, Math.min(max, pos[i] + vel[i] * h));
        prev = pos[i];
      }
    }
  };
  //: On the function, not the shared scope (test_global_scope_ratchet): only it reads them.
  atlasTailFollow.springs = { links: 3, stiff: 90, damp: 9, kick: 0.8, max: 26, bend: 0.55, liftKick: 40, liftMax: 12, liftBend: 0.2, earSide: 40, earLift: 3, earMax: 9 };
  //: **The streams follow the body** (INBOX 1683 c): the tail's three-link chain (`atlasTailFollow`) also
  //: carries the lower body and the wisps a little way, each on its own link and gain, so they lag a start,
  //: swing past a stop and settle a beat apart (the nebula's halves have the lean's spring). It is the
  //: `translate` of their pose boxes (nothing else animates it there: the pose is `transform`, the loops
  //: `rotate` and `scale`),
  //: written only when it moves a twentieth of a px, and cleared when the chain is at rest.
  atlasTailFollow.strands = (box, tail) => {
    const low = box.atlasRig?.lower;
    const pos = tail.follow?.pos;
    if (!low || !pos) return;
    const lift = tail.follow.lift;
    const put = (els, link, gain) => {
      els.forEach((el, i) => {
        const v = Math.round(pos[link] * gain * (1 + 0.15 * i) * 20) / 20;
        const w = Math.round(lift[link] * gain * (1 + 0.15 * i) * 20) / 20;
        if (el.atlasPushed === v && el.atlasLifted === w) return;
        el.atlasPushed = v;
        el.atlasLifted = w;
        el.style.translate = v || w ? `${v}px ${w}px` : "";
      });
    };
    put(low.boxes, 0, 0.04);
    put(low.wisps, 1, 0.07);
    atlasTailFollow.ears(box, tail.follow);
  };
  //: **The ears follow through** (INBOX 1719 b, E3): the chain's last link also tips the ears, a beat behind the tail's own bend, so they
  //: stream back at a start, swing on past a stop and settle after the body has stopped. The ear's `rotate` property is its own (the crest's
  //: `transform` and the flick's keyframes are another), written only when it moves a tenth of a degree and cleared at rest; the ears are
  //: found once and kept on the box, and nothing here reads layout.
  atlasTailFollow.ears = (box, f) => {
    const A = atlasTailFollow.springs;
    const ears = (box.atlasEars ||= [...box.querySelectorAll(".atl-ear")]);
    //: The sideways chain here is gentle (its push is scaled by 0.01: a throw of 4000 px/s2 moves the last link about 0.12 px), so the ears take it in degrees per px, not as a share of its 26 px range.
    const raw = f.pos[A.links - 1] * A.earSide + (f.lift[A.links - 1] / A.liftMax) * A.earLift;
    const deg = Math.round(Math.max(-A.earMax, Math.min(A.earMax, raw)) * 10) / 10;
    for (const el of ears) {
      if ((el.atlasTurned ?? 0) === deg) continue;
      el.atlasTurned = deg;
      el.style.rotate = deg ? `${deg}deg` : "";
    }
  };
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
  //: **One centreline for all of them** (INBOX 1657 round 2: the body, the
  //: stream, the silk and the filaments each re-sampled the same cubics and
  //: normals, 2.7 ms a draw at 4x CPU walking): the samples and the unit
  //: normals are taken once a draw, the widths and shifts, which depend on
  //: `t` alone, once per look (`spec.tailMemo`), and every side is a multiply
  //: and an add on those. The numbers and their order are `atlasStem`'s, so
  //: the path text is the same byte for byte.
  //: One closure, one shared name (the global-names ratchet).
  const atlasTailKit = (() => {
    const ATLAS_TAIL_SAMPLES = 1;
    function atlasTailMemo(spec, count) {
      const kept = spec.tailMemo?.[count];
      if (kept) return kept;
      const w = spec.tailWidth;
      const at = (fn) => Array.from({ length: count }, (_, i) => fn(i / (count - 1)));
      const wide = at(w);
      const memo = {
        body: wide,
        stream: at((t) => w(t) * 0.26),
        streamShift: at((t) => w(t) * 0.22 * Math.sin(Math.PI * 2.6 * t)),
        silk: at((t) => w(t) * 0.24),
        silkShift: at((t) => -w(t) * 0.3 * Math.sin(Math.PI * 2.6 * t + 1.1)),
        filaments: (spec.tailFilaments || []).map((k) => at((t) => (w(t) / 2) * k)),
        buf: Array.from({ length: 4 }, () => new Float64Array(count)),
        run: Array.from({ length: 2 }, () => new Float64Array(count)),
      };
      (spec.tailMemo ||= {})[count] = memo;
      return memo;
    }
    //: The centreline's points and unit normals (`atlasStemSides`' `at`).
    function atlasTailCentre(segs, c, samples) {
      const n = segs.length;
      const total = n * samples;
      for (let i = 0; i <= total; i += 1) {
        const k = Math.min(n - 1, Math.floor(i / samples));
        const s = segs[k];
        const t = (i - k * samples) / samples;
        const u = 1 - t;
        const dx = 3 * u * u * (s[2] - s[0]) + 6 * u * t * (s[4] - s[2]) + 3 * t * t * (s[6] - s[4]);
        const dy = 3 * u * u * (s[3] - s[1]) + 6 * u * t * (s[5] - s[3]) + 3 * t * t * (s[7] - s[5]);
        const len = Math.hypot(dx, dy) || 1;
        c.x[i] = u * u * u * s[0] + 3 * u * u * t * s[2] + 3 * u * t * t * s[4] + t * t * t * s[6];
        c.y[i] = u * u * u * s[1] + 3 * u * u * t * s[3] + 3 * u * t * t * s[5] + t * t * t * s[7];
        c.nx[i] = dy / len;
        c.ny[i] = dx / len;
      }
    }
    //: `atlasFix` as text, without the double-to-string conversion that was
    //: 1.3 ms of the 1.6 a draw at 4x CPU for the ~2,700 numbers of a tail (the
    //: same two decimals, no trailing zeros; checked against `atlasFix` over
    //: two million values).
    function atlasTailNum(v) {
      const n = Math.round(v * 100);
      const a = n < 0 ? -n : n;
      const fr = a % 100;
      if (fr === 0) return "" + n / 100;
      return (n < 0 ? "-" : "") + (a - fr) / 100 + "." + (fr % 10 === 0 ? "" + fr / 10 : fr < 10 ? "0" + fr : "" + fr);
    }
    //: `atlasSmooth` over the run `from`..`to` of two coordinate arrays, in
    //: either direction.
    function atlasTailSmooth(xs, ys, from, to) {
      const f = atlasTailNum;
      const step = to > from ? 1 : -1;
      const last = Math.max(from, to);
      const first = Math.min(from, to);
      let d = "";
      for (let i = from; i !== to; i += step) {
        const a = Math.max(first, Math.min(last, i - step));
        const b = Math.max(first, Math.min(last, i + 2 * step));
        const j = i + step;
        d += `C${f(xs[i] + (xs[j] - xs[a]) / 6)} ${f(ys[i] + (ys[j] - ys[a]) / 6)} ${f(xs[j] - (xs[b] - xs[i]) / 6)} ${f(ys[j] - (ys[b] - ys[i]) / 6)} ${f(xs[j])} ${f(ys[j])}`;
      }
      return d;
    }
    //: One stem (`atlasStem`): its two sides offset from the centreline by half
    //: the widths `wt`, moved sideways by `sh`, closed with a cap or a half
    //: circle at either end.
    function atlasTailStem(c, wt, sh, round, memo) {
      const [lx, ly, rx, ry] = memo.buf;
      const f = atlasTailNum;
      const m = wt.length - 1;
      for (let i = 0; i <= m; i += 1) {
        const hw = wt[i] / 2;
        const s = sh ? sh[i] : 0;
        const cx = c.x[i] - c.nx[i] * s;
        const cy = c.y[i] + c.ny[i] * s;
        lx[i] = cx - c.nx[i] * hw;
        ly[i] = cy + c.ny[i] * hw;
        rx[i] = cx + c.nx[i] * hw;
        ry[i] = cy - c.ny[i] * hw;
      }
      const r = Math.hypot(lx[m] - rx[m], ly[m] - ry[m]) / 2;
      const end = round || r > 0.05 ? `A${f(r)} ${f(r)} 0 0 0 ${f(rx[m])} ${f(ry[m])}` : `L${f(rx[m])} ${f(ry[m])}`;
      let back = "";
      if (round) {
        const r0 = Math.hypot(lx[0] - rx[0], ly[0] - ry[0]) / 2;
        back = `A${f(r0)} ${f(r0)} 0 0 0 ${f(lx[0])} ${f(ly[0])}`;
      }
      return `M${f(lx[0])} ${f(ly[0])}${atlasTailSmooth(lx, ly, 0, m)}${end}${atlasTailSmooth(rx, ry, m, 0)}${back}Z`;
    }
    function atlasTailCentreOf(spec, segs, samples) {
      const count = segs.length * samples + 1;
      const memo = atlasTailMemo(spec, count);
      const c = memo.centre || (memo.centre = { x: new Float64Array(count), y: new Float64Array(count), nx: new Float64Array(count), ny: new Float64Array(count) });
      atlasTailCentre(segs, c, samples);
      return { memo, c, count };
    }
    //: The stems take one sample a curve (the shape's own 32 curves already go
    //: through its points; a second, between each pair, moved the outline by
    //: under 0.05 of a unit and doubled the numbers written); the filaments
    //: keep two, as their run is cut at a fraction of the samples.
    function atlasTailPaths(spec, segs, samples = ATLAS_TAIL_SAMPLES) {
      const { memo, c } = atlasTailCentreOf(spec, segs, samples);
      const out = {
        body: atlasTailStem(c, memo.body, null, !!spec.tailRound, memo),
        stream: atlasTailStem(c, memo.stream, memo.streamShift, false, memo),
        silk: atlasTailStem(c, memo.silk, memo.silkShift, false, memo),
        filaments: "",
      };
      if (!memo.filaments.length) return out;
      const fine = atlasTailCentreOf(spec, segs, 2);
      const [fx, fy] = fine.memo.run;
      out.filaments = fine.memo.filaments.map((wt) => {
        for (let i = 0; i < fine.count; i += 1) {
          fx[i] = fine.c.x[i] - fine.c.nx[i] * wt[i];
          fy[i] = fine.c.y[i] + fine.c.ny[i] * wt[i];
        }
        const from = Math.round(fine.count * 0.18);
        const to = Math.round(fine.count * 0.92) - 1;
        return `M${atlasTailNum(fx[from])} ${atlasTailNum(fy[from])}${atlasTailSmooth(fx, fy, from, to)}`;
      }).join("");
      return out;
    }
    return { paths: atlasTailPaths, num: atlasTailNum };
  })();
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
    const moody = state === "idle" || state === "sit" ? atlasTailPick.byMood[tail.box.dataset.atlasMood] : null;
    const list = moody || ATLAS_TAIL_BY_STATE[state] || ATLAS_TAIL_BY_STATE.idle;
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
    tail.goal = { curl: base.curl + jit(-0.18, 0.18), amp: base.amp * jit(0.8, 1.25), period: base.period * jit(0.85, 1.2), k: base.k * jit(0.85, 1.15), tip: base.tip || 0, env: base.env || 1.5 };
    tail.act = act;
    tail.state = state;
    const calm = !base.ms && atlasTailCalm(tail, tail.box);
    tail.until = now + (base.ms || (calm ? 5000 + Math.random() * 4000 : 4000 + Math.random() * 5000));
    tail.settle = now + ATLAS_TAIL_SETTLE_MS;
  }
  //: **A frame budget** (audit AI1, 2026-10-31: at 4x CPU the companion at
  //: rest was 30 fps and 540 ms of long tasks per 5 s; at 1x, 60 fps and two).
  //: While the companion is on screen and moving, a few seconds of frames are
  //: timed now and then (a rAF loop beside the animations that already force
  //: a frame, so it adds none): when their mean runs past 21 ms (under 48 fps), or a fifth of them run past 32 ms, the page
  //: carries `data-atlas-lite` for the rest of the visit, and the figure keeps
  //: its sway, breath and blink and drops the planets' glow and swirl and
  //: every drift (atlas-lazy.css, and the ring loops below). It waits five
  //: seconds after the first look so the entrance, which is always heavy, is
  //: not what it times, and looks again once a minute while it is not lite.
  const atlasBudget = { at: 0, last: null };
  function atlasFrameBudget(now) {
    const root = document.documentElement;
    if ((atlasBudget.at && now - atlasBudget.at < 60000) || root.hasAttribute("data-atlas-lite")) return;
    const first = !atlasBudget.at;
    atlasBudget.at = now;
    const run = { last: 0, start: 0, n: 0, sum: 0, long: 0 };
    const step = (t) => {
      if (document.hidden || document.querySelector("#nm-buddy.nm-buddy-dragging")) return;
      if (run.last) {
        run.n += 1;
        run.sum += t - run.last;
        if (t - run.last > 32) run.long += 1;
      }
      run.last = t;
      run.start = run.start || t;
      if (t - run.start < 3000) {
        next();
        return;
      }
      atlasBudget.last = { n: run.n, mean: run.n ? +(run.sum / run.n).toFixed(1) : 0, long: run.long };
      if (run.n >= 20 && (run.sum / run.n > 21 || run.long / run.n >= 0.2)) root.setAttribute("data-atlas-lite", "");
    };
    //: One `requestAnimationFrame` site: the first frame waits out the entrance.
    const next = () => requestAnimationFrame(step);
    setTimeout(next, first ? 5000 : 0);
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
    //: And in the lite set (`atlasFrameBudget`), where they are not played at all.
    const loops = live && !box.closest("#nm-buddy.nm-buddy-dragging") && !document.documentElement.hasAttribute("data-atlas-lite");
    if (live) atlasFrameBudget(now);
    //: **Reads, then the tail's one restyle, then the writes** (INBOX 1534: this
    //: beat's own writes, the loops' play and pause and the breath's scale,
    //: made the next read settle style: `atlasPropsFrame` 71ms, the breath's
    //: rise 107ms and the rest's release 73ms at 4x CPU in 45s of idle). The
    //: props read first; the rest's release, which reads where the sway is,
    //: comes before anything is written; the breath and the loops are writes.
    //: Thirty a second: each draw repaints the tail's layer.
    tail.tick += 1;
    //: The props' own loops, while each is shown (`atlasPropsFrame`).
    atlasPropsFrame(box, live, tail.tick);
    //: Resting on the compositor (`atlasTailRest`): nothing to draw while the
    //: state holds and the act has not run out; the breath and the props
    //: are all this beat does.
    const holds = tail.resting && live && atlasTailCalm(tail, box) && atlasRigLower.spell(box.closest("#nm-buddy"), box) === tail.state && (now < tail.until || atlasTailCalm.resting(box, tail.state));
    if (tail.resting && !holds) atlasTailUnrest(tail);
    //: And the chest's breath (`atlasBreathFrame`), at the rate of the moment.
    atlasBreathFrame(box, live);
    atlasBreathFrame.rate(box.atlasBreath, box.closest("#nm-buddy"), box.dataset.atlasMood, now);
    //: The held loops stay held at rest (`atlasTailCalm.rest.sync` plays them again on input).
    //: Read when `loops` flips or once a second, not every beat (B55: 120 style reads a second through an agent turn).
    //: **A nap slows the rings** (INBOX 1770): a third of the pace, by the animations' playback rate, which keeps every
    //: planet where it is (a longer `animation-duration` jumped them up to 50 degrees). Looked at once a second, only
    //: while napping and for the second after; new loops (the calm hold lifting) are caught by the next look.
    const pace = box.closest("#nm-buddy")?.classList.contains("nmb-act-blanket") ? 1 / 3 : 1;
    if ((pace !== 1 || box.atlasPace) && now - (box.atlasPaceAt || 0) > 1000) {
      box.atlasPaceAt = now;
      for (const anim of box.getAnimations({ subtree: true })) if (anim.effect?.target?.closest?.(".atl-orbits")) anim.updatePlaybackRate(pace);
      for (const anim of box.atlasLoops || []) anim.updatePlaybackRate(pace);
      box.atlasPace = pace !== 1;
    }
    if (!atlasTailCalm.resting(box, tail.state) && (box.atlasLoopsOn !== loops || now - (box.atlasLoopsAt || 0) > 1000)) {
      box.atlasLoopsOn = loops;
      box.atlasLoopsAt = now;
      for (const anim of box.atlasLoops || []) if (loops !== (anim.playState === "running")) loops ? anim.play() : anim.pause();
    }
    if (holds) {
      tail.raf = setTimeout(() => atlasTailFrame(tail, performance.now()), ATLAS_TAIL_REST_BEAT_MS);
      return;
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
      const state = atlasRigLower.spell(buddy, box);
      if (state !== tail.state || now >= tail.until) atlasTailPick(tail, state, now);
      const goal = tail.goal || ATLAS_TAIL_ACTS[tail.act];
      //: Critically damped springs: a flick comes in fast, the rest ease.
      const w = ["flick", "stiff", "shiver"].includes(tail.act) ? 7 : 2.6;
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
    const follow = live ? atlasTailFollow(tail, dt, typeof nmb !== "undefined" ? nmb.x : NaN, typeof nmb !== "undefined" ? nmb.y : 0) : 0;
    if (live) atlasTailFollow.strands(box, tail);
    const p = Object.fromEntries(Object.entries(tail.p).map(([k, j]) => [k, live ? j.x : k === "curl" || k === "amp" || k === "tip" ? 0 : j.x]));
    const drift = live ? 0.13 * Math.sin((2 * Math.PI * secs) / 11.3) + 0.08 * Math.sin((2 * Math.PI * secs) / 17.9 + 1.3) : 0;
    //: The ripple's clock also draws the tail out and back along its length
    //: (3%, a quarter turn behind the ripple), so its tip goes round a small
    //: ellipse that the waves can never all cancel: bending alone moves the
    //: tip one way only, across the tail, and dwells at each turning point
    //: (a stepped 60s of `stiff` read 1.4s still at the tip with bends only).
    const stretch = live ? () => 1 + 0.03 * Math.cos(tail.ph3) : null;
    atlasTailDraw(tail, (s) => atlasTailBend(s, p, live ? tail.ph : 0, live ? tail.ph2 : 0, drift, live ? tail.ph3 : 0, follow), stretch);
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
  const ATLAS_TAIL_CALM_MS = 66;
  function atlasTailCalm(tail, box) {
    return atlasTailCalm.states.has(tail.state) && !!box.closest("#nm-buddy") && !box.closest(".nm-viewer-figure");
  }
  //: **Two seconds without input and not walking: the drawn loops stop** (owner decision Q10; the lag log: 21 rig calls a
  //: second, 20 to 27 restyles a second at rest, the dress morph alone 35 path writes a second). The CSS loops (sway,
  //: breath, glow) stay on the compositor; what stops is the script that rewrites SVG paths. `rest.at` is the last
  //: pointer, key, wheel or touch; the first input after a rest calls every waker, so a stopped loop starts within a frame.
  atlasTailCalm.rest = { at: performance.now(), wake: new Set(), after: 2000 };
  //: **Whether the rest may hold now** (the owner, 2026-11-10, decision 55: a setting, the full animation on mains power only): Settings, Appearance,
  //: "Motion at rest" (`avatar-buddy-rest`): "always" never rests, "mains" (the default) rests on battery, "still" always rests. Read once a second;
  //: a machine that cannot say (`getBattery`) is on mains.
  atlasTailCalm.rest.holds = () => {
    const r = atlasTailCalm.rest;
    const t = performance.now();
    if (t - (r.modeAt || -1e9) > 1000) {
      r.modeAt = t;
      try {
        r.mode = (typeof prefs === "object" && prefs.get("avatar-buddy-rest", null)) || "mains";
      } catch (e) {
        r.mode = "mains";
      }
      if (r.mode === "mains" && !r.asked && globalThis.navigator?.getBattery) {
        r.asked = true;
        navigator.getBattery().then((b) => {
          const read = () => (r.battery = !b.charging);
          read();
          b.addEventListener("chargingchange", read);
        }, () => {});
      }
    }
    return r.mode === "still" || (r.mode === "mains" && !!r.battery);
  };
  //: At rest: a corner companion, in a calm lower-body state, not walking, doing no act, and two seconds from the last input.
  atlasTailCalm.resting = (box, state) => {
    const buddy = box.closest("#nm-buddy");
    return !!buddy && atlasTailCalm.states.has(state) && !/\bnmb-(walking|act-|think|music|reading|poofing|dodge|stir|fitting)/.test(buddy.className) && performance.now() - atlasTailCalm.rest.at > atlasTailCalm.rest.after && atlasTailCalm.rest.holds();
  };
  //: Entering a rest pauses the loops that never end (the sway, the breath, the glow: on SVG parts they are drawn on the main
  //: thread, a restyle and layout a frame, 38 a second at rest); leaving it plays the ones this paused. A finite one (a blink
  //: in flight) is left to finish; one that has since been cancelled is idle, not paused, and stays so.
  atlasTailCalm.rest.sync = (box, state) => {
    const r = atlasTailCalm.rest;
    const resting = atlasTailCalm.resting(box, state);
    r.on = resting;
    if (resting && !r.held) {
      r.held = box.closest("#nm-buddy").getAnimations({ subtree: true }).filter((a) => a.playState === "running" && a.effect?.getComputedTiming().iterations === Infinity);
      for (const a of r.held) a.pause();
    } else if (!resting && r.held) {
      for (const a of r.held) if (a.playState === "paused") a.play();
      r.held = null;
    }
    return resting;
  };
  //: Typing in a field is not the companion's business (B54: typing with it on made 3.4 times the layouts, the keydown
  //: 712 ms in the pacer): a key in an input, a textarea or an editor does not wake it, any other input does.
  for (const type of typeof document.addEventListener === "function" ? ["pointermove", "pointerdown", "keydown", "wheel", "touchstart"] : []) {
    document.addEventListener(type, (event) => {
      if (type === "keydown" && event.key !== "Enter" && event.target?.closest?.("input, textarea, select, [contenteditable]")) return;
      const r = atlasTailCalm.rest;
      const was = performance.now() - r.at > r.after;
      r.at = performance.now();
      // In the next frame, not in the input: playing the held loops and the pacer's first beat are the input's own cost otherwise (lag log: input 320ms).
      if (was) setTimeout(() => r.wake.forEach((fn) => fn()), 0);
    }, { passive: true, capture: true });
  }
  //: On the function, not the shared scope (test_global_scope_ratchet): only it reads them.
  atlasTailCalm.states = new Set(["idle", "sit", "lie", "think", "sad", "hang", "coil", "ripple_calm", "pool", "heavy"]);
  //: **At rest the tail goes to the compositor** (Brief 34 continues, step 2;
  //: decision 7, under 1ms a minute beyond the face): fifteen path draws a
  //: second were about 770 layouts and 2s of script a minute at rest in the
  //: corner. A calm act now draws for `ATLAS_TAIL_SETTLE_MS` while its springs
  //: ease into it (no snap), then holds that drawn shape and sways the tail's
  //: own layer root about its root, a Web Animation of `transform` only (the
  //: companion's pacer leaves layer roots alone), the act's swing and period
  //: from its table, so a curl sways slow and small and a sway wide. Calm acts
  //: hold 5 to 9s (9 to 18 read as never changing, INBOX 1659), the sway 4 to 10 degrees; a new act, a new
  //: state, the large view or a walk takes the live loop back, the layer
  //: easing home from wherever its sway was. `data-atl-tail` says which.
  const ATLAS_TAIL_SETTLE_MS = 1600;
  //: The resting beat still carries the motion gates for the chest (`atlasBreathFrame`),
  //: which is a compositor animation now and writes nothing per beat.
  const ATLAS_TAIL_REST_BEAT_MS = 400;
  function atlasTailRest(tail, p) {
    const { box, svg } = tail;
    tail.resting = true;
    box.dataset.atlTail = "rest";
    if (!svg?.animate) return;
    const vb = svg.viewBox?.baseVal;
    const [rx, ry] = tail.rest[0];
    if (vb?.width) svg.style.transformOrigin = `${atlasFix(((rx - vb.x) / vb.width) * 100)}% ${atlasFix(((ry - vb.y) / vb.height) * 100)}%`;
    const deg = atlasFix(Math.min(10, Math.max(4, (p.amp * 180) / Math.PI * 0.6)));
    const at = ([d, k]) => ({ transform: `rotate(${d}deg) scale(${k})` });
    tail.swayKeys = [[0, 1], [deg, 1.015], [0, 1], [-deg, 0.99], [0, 1]];
    tail.sway = svg.animate(tail.swayKeys.map(at), {
      duration: Math.round(Math.max(2.4, p.period) * 1000), iterations: Infinity, easing: "ease-in-out",
    });
  }
  function atlasTailUnrest(tail) {
    const { box, svg } = tail;
    tail.resting = false;
    box.dataset.atlTail = "live";
    if (!tail.sway) return;
    //: Where the sway is, from its own clock and keyframes, not the style (INBOX
    //: 1587): this runs on the rest beat's timer, and the computed transform
    //: read there settled the whole page's style, 567ms at 1x CPU with Settings open
    //: (a 719-element recalc). `progress` is the eased share of the swing.
    const keys = tail.swayKeys || [];
    const share = Number(tail.sway.effect?.getComputedTiming?.().progress);
    let from = "";
    if (Number.isFinite(share) && keys.length > 1) {
      const x = Math.min(1, Math.max(0, share)) * (keys.length - 1);
      const i = Math.min(keys.length - 2, Math.floor(x));
      const [[d0, k0], [d1, k1]] = [keys[i], keys[i + 1]];
      from = `rotate(${atlasFix(d0 + (d1 - d0) * (x - i))}deg) scale(${atlasFix(k0 + (k1 - k0) * (x - i))})`;
    }
    tail.sway.cancel();
    tail.sway = null;
    if (from) svg.animate([{ transform: from }, { transform: "none" }], { duration: 400, easing: "cubic-bezier(0.33, 0, 0.2, 1)" });
  }
  function atlasTailDraw(tail, bend, stretch) {
    if (atlasTailFrame.kit.hold === tail) return;
    const { pts, turn, segs } = atlasTailShape(tail.rest, bend, stretch);
    const d = atlasTailKit.paths(tail.spec, segs);
    const { paths } = tail;
    paths.edge?.setAttribute("d", d.body);
    for (const el of paths.body) el.setAttribute("d", d.body);
    paths.silk?.setAttribute("d", d.silk);
    paths.stream?.setAttribute("d", d.stream);
    if (paths.filaments) paths.filaments.setAttribute("d", d.filaments);
    const f = atlasTailKit.num;
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
    const set = (shown) => {
      for (const loop of loops) {
        const on = shown ? shown.get(loop.root) : false;
        if (on === loop.on) continue;
        loop.on = on;
        if (on) {
          loop.anim.play();
          loop.anim.currentTime = loop.lag;
        } else loop.anim.cancel();
      }
    };
    if (!live) {
      box.atlasPropsAt = 0;
      set(null);
      return;
    }
    if (box.atlasPropsAt > (box.atlasDirtyAt || 0) + 1500 || box.atlasPropsLooking) return;
    box.atlasPropsAt = performance.now();
    //: **The opacity is read in a task after a drawn frame, never in the tail's frame callback** (INBOX 1766, the
    //: owner's Windows log: "animation loops 73 ms", 47 to 137ms of forced style at 4x CPU, once a wake). The tail's
    //: step runs before the frame's style pass, so a read here paid for every class an act or a mood had written
    //: since the last draw; the read in the task that follows the frame (`atlasRigWake.afterPaint`, as the rig's own
    //: look) finds style settled. A prop's fade is 0.16s and the look is a frame late: the loop starts as it is whole.
    box.atlasPropsLooking = true;
    atlasRigWake.afterPaint(() => {
      box.atlasPropsLooking = false;
      //: Gone, hidden or not live since (`atlasPropsAt` zeroed): nothing to read.
      if (!box.isConnected || document.hidden || !box.atlasPropsAt) return;
      const shown = new Map();
      for (const loop of loops) if (!shown.has(loop.root)) shown.set(loop.root, +getComputedStyle(loop.root).opacity > 0.05);
      set(shown);
    }, 1);
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
  //: **On the compositor, set once** (atlasidle2, 2026-11-07). It was written
  //: ten times a second (a CSS loop inside the drawing was refused: it
  //: repainted the large view every frame, 53 frames a second down to 20 to
  //: 31), and that write was one of the two that kept the companion's ~70
  //: animated elements restyling at rest: any style write restyles every
  //: animated element, composited or not (3 torsos x 10 writes a second:
  //: 90 restyles in 6 s of the hanging pose, 2.7 s of main thread at 4x CPU).
  //: Now one Web Animation of `transform` per torso (not the individual
  //: `scale`, which Chromium refuses on an svg box: compositeFailed bit 19),
  //: started on the rise's own start time so the two share a clock for good,
  //: and touched again only when the figure's look (its period) changes or it
  //: comes back from being still. Ease-in-out sine, as the cosine was.
  //: It rides the tail's loop, which already knows when the figure is off
  //: screen, on a hidden tab, or still by setting (Avatar animation Off, reduced
  //: motion, the companion's own Full motion); it cancels the animation then
  //: and puts the chest back at rest.
  //:
  //: On the rise's clock: the swell takes its phase from the box's own
  //: animation, so the chest fills as the shoulders lift.
  const ATLAS_BREATH_SWELL = [0.035, 0.025];
  function atlasBreathFrame(box, live) {
    const look = box.dataset.atlasLook;
    if (!live) {
      if (box.atlasBreath) for (const anim of box.atlasBreath.anims) anim.cancel();
      box.atlasBreath?.rise?.updatePlaybackRate?.(1);
      box.atlasBreath = null;
      return;
    }
    if (box.atlasBreath?.look === look) return;
    //: Not under the entrance fade: started while `#nm-buddy` is opacity 0 the
    //: torso counts as an empty box and the compositor refuses it for good
    //: (Chromium status bit 17; both torsos on the reload path, none when
    //: started a beat later). One style read, only at a start or a retune.
    const faded = box.closest?.("#nm-buddy");
    if (faded && +getComputedStyle(faded).opacity === 0) return;
    box.atlasTorsos ||= [...box.querySelectorAll(".atl-layer-body .nmb-torso")];
    if (box.atlasBreath) for (const anim of box.atlasBreath.anims) anim.cancel();
    box.atlasBreath?.rise?.updatePlaybackRate?.(1);
    //: The rise's clock is read here only, at a start or a retune (`getAnimations`
    //: and an animation's times bring the page's style up to date: B87a, 81
    //: forced restyles in 1.3 s of a carry when this was read each step).
    const rise = box.querySelector(".atl-lw-breathe")?.getAnimations()[0] || null;
    const going = rise && rise.playState !== "idle";
    const period = going ? +rise.effect.getComputedTiming().duration : look === "feminine" ? 4000 : 4600;
    const [sx, sy] = ATLAS_BREATH_SWELL;
    const frames = [{ transform: "scale(1, 1)" }, { transform: `scale(${1 + sx}, ${1 + sy})` }, { transform: "scale(1, 1)" }];
    const anims = box.atlasTorsos.map((el) => {
      const anim = el.animate(frames, { duration: period, iterations: Infinity, easing: "cubic-bezier(0.37, 0, 0.63, 1)", id: "atl-breath" });
      if (going && rise.startTime !== null) anim.startTime = rise.startTime;
      else if (going) anim.currentTime = rise.currentTime;
      return anim;
    });
    box.atlasBreath = { look, anims, rise: going ? rise : null, rate: 1 };
  }
  //: **The breath quickens and eases** (INBOX 1719 b): a walk, a carry or a lively act leaves the figure out of breath and
  //: it eases back over the table's half-life; sleepy it is slower, startled quicker (`atlasBlink.vitals`). The rate is
  //: the animations' playback rate, set only when its 0.05 step changes (`updatePlaybackRate` keeps the phase, so the
  //: chest and the rise stay together); the classes read are the buddy's own, no style.
  atlasBreathFrame.hot = ["nmb-walking", "nm-buddy-dragging", "nmb-act-hop", "nmb-act-cheer", "nmb-act-wiggle", "nmb-act-kick", "nmb-act-swing", "nmb-act-shake", "nmb-act-startle", "nmb-act-land", "nmb-act-carry"];
  atlasBreathFrame.rate = (breath, buddy, mood, now) => {
    if (!breath) return 1;
    const cls = buddy?.classList;
    if (cls && atlasBreathFrame.hot.some((c) => cls.contains(c))) breath.hotAt = now;
    const sleepy = cls?.contains("nmb-drowsy") || cls?.contains("nmb-sleep") ? "sleepy" : mood;
    const rate = Math.round(20 / atlasBlink.vitals(sleepy, 0, now - (breath.hotAt ?? -Infinity)).breath) / 20;
    if (rate !== breath.rate) {
      breath.rate = rate;
      for (const anim of [...breath.anims, breath.rise]) anim?.updatePlaybackRate?.(rate);
    }
    return rate;
  };

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
    //: Asleep (INBOX 1680, the owner: "even when it is sleeping, it still sticks
    //: up"): the lower body curls and droops, a slow ease, shorter and wider
    //: than a lie, the tail wrapped round (a turn well past a lie's).
    curl: { ms: 1600, ease: "cubic-bezier(0.45, 0, 0.35, 1)", v: [[4, 1.1, 0.74, -6, 38], [-3, 1.12, 0.72, 6, -34], [3.5, 1.08, 0.76, -5, 44]] },
    //: INBOX 1681 (the owner: "crouching down ... lounging ... gliding ... hanging"): a squat folds the
    //: lower body short and wide, a lounge lays it out to one side, a glide trails it long and thin behind
    //: the lean, a drift lets it hang loose and slow, a hang lets it swing from the hips. The act's own
    //: variant (`data-variant`) picks the row, so the body and the lower body agree; the turn stays
    //: within 4 degrees (INBOX 615 and 619) and the lean, the tail and the stretch do the posing.
    crouch: { ms: 700, ease: "cubic-bezier(0.34, 1.15, 0.6, 1)", v: [[2, 1.14, 0.7, -3, -16], [-3, 1.1, 0.74, 4, 12], [1.5, 1.18, 0.66, -2, -22]] },
    lounge: { ms: 900, ease: "cubic-bezier(0.4, 1.1, 0.6, 1)", v: [[3.5, 1.06, 0.84, -4, 26], [-2, 1.1, 0.8, 2, -20], [2, 1.04, 0.88, -3, 16]] },
    glide: { ms: 800, ease: "cubic-bezier(0.3, 0.9, 0.5, 1)", v: [[-3.5, 0.9, 1.14, 8, -34], [-2, 0.88, 1.18, 6, -42], [-3.8, 0.92, 1.12, 10, -28]] },
    drift: { ms: 1400, ease: "cubic-bezier(0.45, 0, 0.35, 1)", v: [[2, 1.02, 1.04, -4, 18], [-3, 1.08, 0.88, 3, -24], [3.8, 1, 1.08, -6, 32]] },
    hang: { ms: 700, ease: "cubic-bezier(0.34, 1.2, 0.6, 1)", v: [[1.5, 0.96, 1.08, -2, 10], [-2, 0.95, 1.1, 3, -14], [2.5, 0.97, 1.06, -3, 18]] },
    //: E6 (companion-asks B1, B3: "the lower body follows the pose"): leaning on a wall or edge (the weight on one
    //: hip, the hem pulled to the other side), legs over an edge (the hem let straight down, long, a slow swing), a
    //: kick of them (quick, the hem thrown out), a swing from a bar (the hem a pendulum, wide turns of the tail) and a
    //: sloth hang (limp and long, barely moving). The act or pose names the row; the turn stays inside the 4 degrees.
    lean: { ms: 650, ease: "cubic-bezier(0.4, 1.1, 0.6, 1)", v: [[3, 1.02, 0.96, 7, 14], [-3, 1.02, 0.95, -7, -12], [2, 1.03, 0.97, 5, 18]] },
    dangle: { ms: 900, ease: "cubic-bezier(0.45, 0.1, 0.4, 1)", v: [[1.5, 1.04, 1.08, -3, 12], [-2, 1.05, 1.12, 4, -10], [2.5, 1.03, 1.1, -2, 16]] },
    kick: { ms: 320, ease: "cubic-bezier(0.2, 1.9, 0.4, 1)", v: [[-3.5, 1.02, 1.05, 9, -22], [3, 1.03, 1.03, -9, 24], [-2, 1.02, 1.06, 7, -18]] },
    swing: { ms: 520, ease: "cubic-bezier(0.34, 1.3, 0.6, 1)", v: [[3, 0.96, 1.1, 8, 24], [-3, 0.95, 1.12, -8, -26], [2, 0.97, 1.09, 6, 20]] },
    sloth: { ms: 1500, ease: "cubic-bezier(0.5, 0, 0.6, 1)", v: [[1, 1.02, 1.14, -1, 26], [-1.5, 1.03, 1.16, 1, -22], [1.5, 1.02, 1.12, -2, 30]] },
    //: atlascat-1108 C5 (`atlasRigLower.spell` says when): a gust lifts the hem on a fast glide, the legs tucked under
    //: cross-legged, a slow ripple root to hem in a calm spell, a quick flutter when excited, spread flat after a
    //: long sit, a playful kick of the hem when glad, a spiral that unwinds after a twirl, and heavy when tired.
    billow: { ms: 380, ease: "cubic-bezier(0.25, 1.7, 0.5, 1)", v: [[-3, 0.92, 1.1, 9, -30], [-2, 0.9, 1.14, 11, -38], [-3.5, 0.94, 1.08, 7, -26]] },
    coil: { ms: 800, ease: "cubic-bezier(0.34, 1.15, 0.6, 1)", v: [[2, 1.14, 0.7, -2, 20], [-2, 1.16, 0.68, 2, -18], [1.5, 1.12, 0.72, -3, 26]] },
    ripple_calm: { ms: 1400, ease: "cubic-bezier(0.45, 0, 0.55, 1)", v: [[1.5, 1, 1.03, -3, 8], [-2, 1.02, 1.01, 3, -10], [2.5, 1, 1.04, -2, 12]] },
    flutter: { ms: 300, ease: "cubic-bezier(0.25, 1.8, 0.5, 1)", v: [[-3, 1.03, 0.97, 6, -16], [3, 1.03, 0.96, -6, 18], [-2, 1.04, 0.97, 4, -12]] },
    pool: { ms: 1200, ease: "cubic-bezier(0.4, 1.1, 0.6, 1)", v: [[3, 1.18, 0.62, -3, 30], [-3, 1.2, 0.6, 3, -28], [2, 1.16, 0.64, -2, 24]] },
    hem_kick: { ms: 320, ease: "cubic-bezier(0.2, 2, 0.4, 1)", v: [[-3.5, 1.02, 0.96, 8, -22], [3, 1.03, 0.95, -9, 24], [-2, 1.02, 0.97, 6, -18]] },
    spiral: { ms: 700, ease: "cubic-bezier(0.3, 1.3, 0.5, 1)", v: [[3.8, 0.96, 1.02, 10, 34], [-3.8, 0.95, 1.04, -12, -40], [3, 0.97, 1, 8, 28]] },
    //: atlascat-1108 D5 (`lower.fall`): falling free (a throw's descent, `nmb-falling`), the hem streams up above it,
    //: long and thin, thrown about; fast to take and never at rest.
    fall: { ms: 240, ease: "cubic-bezier(0.2, 1.9, 0.4, 1)", v: [[-2, 0.88, 1.24, 7, -46], [2.5, 0.86, 1.28, -7, -50], [-3, 0.9, 1.22, 9, -42]] },
    heavy: { ms: 1100, ease: "cubic-bezier(0.5, 0, 0.6, 1)", v: [[1, 1.04, 1.1, -1, 20], [-1, 1.05, 1.12, 1, 24], [1.5, 1.03, 1.09, -1, 16]] },
  };
  //: The hair's turn about the crown and the nebula stream's [turn, width,
  //: height] about the figure's middle, per state (INBOX 575, the owner:
  //: "both atlas avatars have a tail as well, same with the hair, and the
  //: nebular stream ... dynamically animated and changed"), a variant each
  //: as the lower body's; a walk's turn takes the way it goes.
  const ATLAS_HAIR_STATES = { idle: [0, 1.6, -1.4, 0.8], walk: [-5, -4, -6], sit: [2, 1, 3], lie: [4, 5, 3], gesture: [-3, -2, -4], think: [2.5, 1.5, 3.5], happy: [-3.5, -2.5, -4], sad: [4, 5, 6], startle: [-6, -7, -5], curl: [6, 8, 7], crouch: [3, 1, 4], lounge: [4, 2, 5], glide: [-7, -9, -6], drift: [3, 5, 2], hang: [2, -2, 3], billow: [-8, -10, -7], coil: [2, 1, 3], ripple_calm: [2, -2, 3], flutter: [-3, 3, -2], pool: [4, 3, 5], hem_kick: [-4, 3, -3], spiral: [6, -6, 5], heavy: [3, 4, 5], fall: [-9, -11, -8], lean: [3, 4, 2], dangle: [2, 3, 1], kick: [-4, 4, -3], swing: [4, -4, 5], sloth: [3, 4, 5] };
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
    curl: [[8, 1.05, 0.82], [-6, 1.07, 0.8], [10, 1.04, 0.83]],
    crouch: [[3, 1.06, 0.88], [-3, 1.05, 0.9], [2, 1.08, 0.86]],
    lounge: [[5, 1.05, 0.9], [-4, 1.06, 0.88], [3, 1.04, 0.92]],
    glide: [[-6, 1.04, 1.06], [-8, 1.03, 1.08], [-5, 1.05, 1.05]],
    drift: [[3, 1.02, 1.03], [-4, 1.03, 1.02], [5, 1.01, 1.04]],
    hang: [[2, 1, 1.03], [-2, 1.01, 1.02], [3, 0.99, 1.04]],
    billow: [[-5, 1.05, 1.05], [-7, 1.04, 1.07], [-4, 1.06, 1.04]],
    fall: [[-8, 1.06, 1.1], [-9, 1.05, 1.12], [-7, 1.07, 1.09]],
    coil: [[3, 1.06, 0.88], [-3, 1.07, 0.86], [2, 1.05, 0.9]],
    ripple_calm: [[2, 1.01, 1.01], [-2, 1, 1.02], [1, 1.02, 1]],
    flutter: [[-2, 1.03, 1.02], [2, 1.02, 1.03], [-1, 1.04, 1.01]],
    pool: [[4, 1.07, 0.84], [-3, 1.08, 0.82], [3, 1.06, 0.86]],
    hem_kick: [[-3, 1.03, 1.03], [3, 1.04, 1.02], [-2, 1.02, 1.04]],
    spiral: [[7, 1.02, 1.02], [-7, 1.03, 1.01], [5, 1.01, 1.03]],
    heavy: [[1, 0.98, 0.95], [-1, 0.97, 0.96], [2, 0.99, 0.94]],
    lean: [[3, 1.03, 0.96], [-3, 1.04, 0.95], [2, 1.02, 0.97]],
    dangle: [[2, 1.02, 1.04], [-2, 1.03, 1.05], [3, 1.01, 1.03]],
    kick: [[-3, 1.04, 1.02], [3, 1.03, 1.03], [-2, 1.05, 1.01]],
    swing: [[4, 1.02, 1.04], [-4, 1.03, 1.05], [3, 1.01, 1.03]],
    sloth: [[1, 0.98, 1.05], [-1, 0.97, 1.06], [2, 0.99, 1.04]],
  };
  //: **More arrangements than the tables hold** (INBOX 1683 B1 and B3, the owner: "they dont even ahve
  //: different variations or change based on body position"): the authored rows above are the corners; the
  //: rows between each pair (and the last back to the first) are blended and added to the end, so a pose of three has six
  //: and standing eight, none like another and none outside the authored range (the lower body's turn stays
  //: inside the 4 degrees the join allows). Hair rows are numbers, the lower body's and the stream's lists.
  atlasRigLower.blend = (rows) => {
    const n = rows.length;
    //: Not always the middle (0.4, 0.6, 0.5 in turn): rows set evenly round a third (walk's) would blend onto each other.
    const mix = (a, b, t) => (Array.isArray(a) ? a.map((v, k) => v + (b[k] - v) * t) : a + (b - a) * t);
    const out = rows.slice();
    for (let i = 0; i < Math.max(3, n); i += 1) out.push(mix(rows[i % n], rows[(i + 1) % n], [0.4, 0.6, 0.5][i % 3]));
    return out;
  };
  //: Memoised per authored list; a property, not a global (`tests/test_global_scope_ratchet.py`).
  atlasRigLower.blend.cache = new Map();
  atlasRigLower.blend.of = (rows) => {
    if (!atlasRigLower.blend.cache.has(rows)) atlasRigLower.blend.cache.set(rows, atlasRigLower.blend(rows));
    return atlasRigLower.blend.cache.get(rows);
  };
  //: **The streams move all the time, and by the pose** (INBOX 1683 B1, B2, B3, B5, B6): beside the pose's
  //: transition each part drifts on a looping path of its own, a Web Animation of `translate`, the one property
  //: nothing else on these boxes sets (the pose is `transform`, the CSS sway `rotate` and `scale`), so it replaces
  //: and the compositor runs it: an added (`composite: "add"`) turn took the whole figure off the compositor
  //: (tests/test_atlas_composite_1101.py). The path is a random walk through `atlasRigLower.flowKeys` points, eased between
  //: them, 14 to 26 s round and a period of its own for every part, so no two move together and none repeats
  //: before the pose changes (a new path every pose or variant, 5 to 9 s at rest). A pose scales it:
  //: [reach, rate], so asleep it is small and slow, walking and glad it is wide and quick. A new path starts
  //: from where the old one is, so a change of pose is never a step.
  atlasRigLower.flowKeys = 7;
  atlasRigLower.flowByState = { idle: [1, 1], walk: [1.5, 0.7], sit: [0.8, 1.15], lie: [0.6, 1.4], curl: [0.45, 1.7], gesture: [1.25, 0.8], think: [0.9, 1.1], happy: [1.45, 0.65], sad: [0.6, 1.5], startle: [1.6, 0.55], crouch: [0.8, 1.2], lounge: [0.9, 1.3], glide: [1.4, 0.75], drift: [1.3, 1.2], hang: [1.1, 0.9], billow: [1.5, 0.7], coil: [0.7, 1.2], ripple_calm: [0.9, 1.4], flutter: [1.4, 0.6], pool: [0.55, 1.5], hem_kick: [1.4, 0.7], spiral: [1.5, 0.65], heavy: [0.5, 1.6], fall: [1.7, 0.5], lean: [0.9, 1.1], dangle: [1.1, 1.0], kick: [1.5, 0.6], swing: [1.4, 0.8], sloth: [0.5, 1.6] };
  //: Per part: [x px, y px] at a reach of 1. The lower body's own box barely moves (its join with the torso
  //: must hold: INBOX 615); the wisps, the stream and the hair move most.
  atlasRigLower.flowParts = { boxes: [0.3, 0.45], wisps: [1.5, 1.1], tails: [0.9, 0.8], hair: [0.9, 0.7], neb: [1.3, 1] };
  //: Where a path is now, from its own keys and clock (not the style: INBOX 1587), eased like the segments.
  atlasRigLower.flowAt = (anim) => {
    const share = Number(anim.effect?.getComputedTiming?.().progress);
    if (!anim.keys || !Number.isFinite(share)) return [0, 0];
    const x = Math.min(1, Math.max(0, share)) * (anim.keys.length - 1);
    const i = Math.min(anim.keys.length - 2, Math.floor(x));
    const u = x - i;
    const e = u * u * (3 - 2 * u);
    return anim.keys[i].map((v, k) => v + (anim.keys[i + 1][k] - v) * e);
  }
  atlasRigLower.flow = (rig, state, live) => {
    const low = rig.lower;
    const loops = (rig.box.atlasLoops ||= []);
    low.from ||= new Map();
    for (const anim of low.flow || []) {
      low.from.set(anim.el, atlasRigLower.flowAt(anim));
      anim.cancel();
      if (loops.includes(anim)) loops.splice(loops.indexOf(anim), 1);
    }
    low.flow = [];
    if (!live || !rig.box.isConnected || !rig.box.animate) {
      low.from.clear();
      return;
    }
    const [reach, rate] = atlasRigLower.flowByState[state] || [1, 1];
    let n = 0;
    for (const [part, gain] of Object.entries(atlasRigLower.flowParts)) {
      for (const el of low[part] || []) {
        n += 1;
        const start = low.from.get(el) || [0, 0];
        const keys = [start];
        for (let j = 1; j < atlasRigLower.flowKeys - 1; j += 1) {
          keys.push(gain.map((g, k) => { const cap = 1.6 * g * reach; return Math.max(-cap, Math.min(cap, keys[j - 1][k] * 0.35 + (Math.random() * 2 - 1) * 1.3 * g * reach)); }));
          //: The stream's own 1 px wobble (it was a CSS `translate` loop on the same box: two animations of one property keep the box off the compositor) rides the path, a swing each key.
          if (part === "neb") keys[j] = keys[j].map((v, k) => v + (j % 2 ? 1 : -1) * (k ? 0.6 : 1));
        }
        keys.push(start);
        const frames = keys.map((v) => ({ translate: `${atlasFix(v[0])}px ${atlasFix(v[1])}px`, easing: "ease-in-out" }));
        const anim = el.animate(frames, { duration: Math.round((14 + ((n * 4.7) % 12)) * 1000 * rate), iterations: Infinity });
        Object.assign(anim, { keys, el });
        low.flow.push(anim);
        loops.push(anim);
      }
    }
  }
  //: **The streams bend, not just drift** (INBOX 1709, the owner: "the in-app companion atlas's nebular flow as well as its lower
  //: body arent animated and have no organic life or feel to them, they are just the same static frame"). The boxes above
  //: move as rigid pieces a pixel or two; the drawings inside them never changed shape. Now the wisps' ribbons, the nebula
  //: band, the dress and the glints are redrawn 10 times a second from their own points, each displaced by a travelling wave
  //: of three octaves (11, 6.7 and 4.8 s, the desk companion's `Flow` periods and weights), so a ribbon sways root to tip with
  //: the tip leading (`ribbon`), the band flows as one stream (`field`) and the hem swings and breathes (`hem`: a taper that
  //: widens and narrows as it sways, still at the waist where the torso joins). A state scales the reach and the speed
  //: (`flowByState`), eased, so walking streams harder and sleep barely moves. Paths are parsed once; a tick is sines and a
  //: string per path, on a 100 ms timer (a path animation would take the figure off the compositor: test_atlas_composite_1101).
  //: Reduced motion, a hidden tab, off screen, dragged and the lite set draw nothing and leave each drawn shape in place.
  atlasRigLower.morph = {
    tick: 100,
    periods: [11, 6.7, 4.8],
    weights: [0.4, 0.6, 1],
    tip: 3.2,
    stream: 1,
    sway: 1.7,
    breath: 0.03,
    cmd: /([MCLQZA])|(-?\d*\.?\d+(?:e-?\d+)?)/gi,
  };
  //: A path's points and the letters between them, or null for a path with relative steps. An arc (`A`, a ribbon's round end)
  //: keeps its radii and flags (`pre`) and moves its end point.
  atlasRigLower.morph.parse = (d) => {
    if (!d || /[^MCLQZA\d.\s,e+-]/.test(d)) return null;
    const lead = [];
    const pre = [];
    const pts = [];
    let cmd = "";
    let pending = "";
    let hold = [];
    let tail = "";
    for (const m of d.matchAll(atlasRigLower.morph.cmd)) {
      if (m[1]) {
        if (m[1].toUpperCase() === "Z") tail += "Z";
        else {
          cmd = m[1].toUpperCase();
          pending = m[1];
        }
        continue;
      }
      hold.push(Number(m[2]));
      if (cmd === "A" ? hold.length === 7 : hold.length === 2) {
        pre.push(cmd === "A" ? hold.slice(0, 5).join(" ") + " " : "");
        pts.push(hold[hold.length - 2], hold[hold.length - 1]);
        lead.push(pending);
        pending = "";
        hold = [];
      }
    }
    return !hold.length && pts.length >= 4 ? { lead, pre, pts, tail } : null;
  };
  //: The wave at a place (`prep` kept its delay along the strand as a cosine and sine per octave) for the octaves' angles now
  //: (`angles`, a cosine and sine each): sin(a - s) = sin a cos s - cos a sin s, so a point costs no trigonometry. -1 to 1.
  atlasRigLower.morph.at = (ang, ks, i) => {
    const w = atlasRigLower.morph.weights;
    return 0.5 * (w[0] * (ang[1] * ks[i] - ang[0] * ks[i + 1]) + w[1] * (ang[3] * ks[i + 2] - ang[2] * ks[i + 3]) + w[2] * (ang[5] * ks[i + 4] - ang[4] * ks[i + 5]));
  };
  atlasRigLower.morph.angles = (t, phase, out) => {
    const M = atlasRigLower.morph;
    for (let h = 0; h < 3; h += 1) {
      const a = (2 * Math.PI * t) / M.periods[h] + phase * (h + 1);
      out[h * 2] = Math.cos(a);
      out[h * 2 + 1] = Math.sin(a);
    }
    return out;
  };
  //: The delays a wave has at a point, for `at`: six numbers a point (the octaves' cosine and sine of `s`, `1 + 0.35 h` times it).
  atlasRigLower.morph.delays = (list) => {
    const ks = new Float32Array(list.length * 6);
    list.forEach((s, n) => {
      for (let h = 0; h < 3; h += 1) {
        ks[n * 6 + h * 2] = Math.cos(s * (1 + h * 0.35));
        ks[n * 6 + h * 2 + 1] = Math.sin(s * (1 + h * 0.35));
      }
    });
    return ks;
  };
  //: One target: a path and how a point of it moves. `put` writes the moved path.
  atlasRigLower.morph.target = (el, kind, group, phase) => {
    const p = atlasRigLower.morph.parse(el.getAttribute("d"));
    if (!p) return null;
    return { el, kind, group, phase, d0: el.getAttribute("d"), ...p, out: new Array(p.pts.length) };
  };
  //: The ribbons of an astral layer, a glow, core and edge to each, share the core's root and reach.
  atlasRigLower.morph.build = (low) => {
    const M = atlasRigLower.morph;
    const targets = [];
    let phase = 0;
    const bounds = (list) => {
      const b = { x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9 };
      for (const t of list) for (let i = 0; i < t.pts.length; i += 2) {
        b.x0 = Math.min(b.x0, t.pts[i]); b.x1 = Math.max(b.x1, t.pts[i]);
        b.y0 = Math.min(b.y0, t.pts[i + 1]); b.y1 = Math.max(b.y1, t.pts[i + 1]);
      }
      return b;
    };
    for (const el of low.wisps) {
      const paths = [...el.querySelectorAll("path.atl-astral-glow, path.atl-astral-core, path.atl-astral-edge")];
      for (let i = 0; i < paths.length; i += 3) {
        const trio = paths.slice(i, i + 3).map((e) => M.target(e, "ribbon", null, 0)).filter(Boolean);
        if (!trio.length) continue;
        const core = trio[Math.min(1, trio.length - 1)];
        const g = { rx: core.pts[0], ry: core.pts[1], far: 1 };
        for (const t of trio) for (let k = 0; k < t.pts.length; k += 2) g.far = Math.max(g.far, Math.hypot(t.pts[k] - g.rx, t.pts[k + 1] - g.ry));
        phase += 1.9;
        for (const t of trio) Object.assign(t, { group: g, phase });
        targets.push(...trio);
      }
      for (const e of el.querySelectorAll("path.atl-wisp-glint")) {
        const t = M.target(e, "field", null, (phase += 0.7));
        if (t) targets.push(t);
      }
    }
    for (const el of low.neb) {
      const own = [...el.querySelectorAll("path")].map((e) => M.target(e, "field", null, 0.4)).filter(Boolean);
      own.forEach((t, i) => (t.phase = 0.4 + i * 0.05));
      targets.push(...own);
      for (const e of el.querySelectorAll("ellipse.atl-band-cloud")) {
        const t = { el, cloud: e, kind: "cloud", cx: Number(e.getAttribute("cx")), cy: Number(e.getAttribute("cy")), phase: (phase += 0.9) };
        if (Number.isFinite(t.cx) && Number.isFinite(t.cy)) targets.push(t);
      }
    }
    for (const el of low.boxes) {
      const own = [...el.querySelectorAll("path")].map((e) => M.target(e, "hem", null, 0)).filter(Boolean);
      const b = bounds(own);
      for (const t of own) Object.assign(t, { group: { ...b, cx: (b.x0 + b.x1) / 2 } });
      targets.push(...own);
    }
    for (const t of targets) M.prep(t);
    return targets;
  };
  //: A target's delays, from where each point sits: a ribbon one (down its length), the band two, the dress three.
  atlasRigLower.morph.prep = (t) => {
    const M = atlasRigLower.morph;
    const g = t.group;
    if (t.kind === "cloud") {
      t.ks = [M.delays([0.2 * t.cy]), M.delays([0.2 * t.cx])];
      t.w = [];
      return;
    }
    const p = t.pts;
    const n = p.length / 2;
    const at = (f) => Array.from({ length: n }, (_, i) => f(p[i * 2], p[i * 2 + 1]));
    if (t.kind === "ribbon") {
      const dist = at((x, y) => Math.hypot(x - g.rx, y - g.ry) || 1);
      t.ks = [M.delays(dist.map((d) => 3.2 * (d / g.far)))];
      t.perp = Float32Array.from(dist.flatMap((d, i) => [(-(p[i * 2 + 1] - g.ry) / d), (p[i * 2] - g.rx) / d]));
      t.w = Float32Array.from(dist.map((d) => Math.pow(Math.min(1, d / g.far), 1.4)));
    } else if (t.kind === "field") t.ks = [M.delays(at((x, y) => 0.16 * y + 0.1 * x)), M.delays(at((x, y) => 0.16 * x - 0.1 * y))];
    else {
      t.ks = [M.delays(at((x, y) => 0.12 * y)), M.delays(at((x, y) => 0.05 * y)), M.delays(at((x, y) => 0.1 * x))];
      t.w = Float32Array.from(at((x, y) => Math.pow(Math.min(1, Math.max(0, (y - g.y0) / Math.max(1, g.y1 - g.y0))), 1.5)));
    }
  };
  atlasRigLower.morph.draw = (t, clock, gain, ang) => {
    const M = atlasRigLower.morph;
    const p = t.pts;
    const o = t.out;
    const f = atlasFix;
    const A = (phase, k) => M.angles(clock, phase, ang[k]);
    if (t.kind === "cloud") {
      t.cloud.setAttribute("cx", f(t.cx + M.stream * gain * M.at(A(t.phase, 0), t.ks[0], 0)));
      t.cloud.setAttribute("cy", f(t.cy + M.stream * gain * M.at(A(t.phase + 1.3, 1), t.ks[1], 0)));
      return;
    }
    const g = t.group;
    const a0 = A(t.kind === "hem" ? 0.3 : t.phase, 0);
    const a1 = t.kind === "ribbon" ? a0 : A(t.kind === "hem" ? 2.4 : t.phase + 2.1, 1);
    const a2 = t.kind === "hem" ? A(1.1, 2) : a0;
    for (let i = 0, n = 0; i < p.length; i += 2, n += 6) {
      const x = p[i];
      const y = p[i + 1];
      let dx;
      let dy;
      if (t.kind === "ribbon") {
        const amp = M.tip * gain * t.w[i / 2] * M.at(a0, t.ks[0], n);
        dx = t.perp[i] * amp;
        dy = t.perp[i + 1] * amp;
      } else if (t.kind === "field") {
        dx = M.stream * gain * M.at(a0, t.ks[0], n);
        dy = 0.7 * M.stream * gain * M.at(a1, t.ks[1], n);
      } else {
        const w = t.w[i / 2];
        dx = w * (M.sway * gain * M.at(a0, t.ks[0], n) + (x - g.cx) * M.breath * gain * M.at(a1, t.ks[1], n));
        dy = w * 0.3 * gain * M.at(a2, t.ks[2], n);
      }
      o[i] = f(x + dx);
      o[i + 1] = f(y + dy);
    }
    let d = "";
    for (let i = 0, n = 0; i < o.length; i += 2, n += 1) d += `${t.lead[n] || " "}${t.pre[n]}${o[i]} ${o[i + 1]}`;
    t.el.setAttribute("d", d.trim() + t.tail);
  };
  //: Put every moved path back to the shape it was drawn in (motion off, the lite set).
  atlasRigLower.morph.rest = (low) => {
    for (const t of low.morph?.targets || []) {
      if (t.kind === "cloud") {
        t.cloud.setAttribute("cx", t.cx);
        t.cloud.setAttribute("cy", t.cy);
      } else t.el.setAttribute("d", t.d0);
    }
    if (low.morph) low.morph.moved = false;
  };
  //: The timer: 100 ms while the figure is live, a second otherwise. It is the rig's, started by `atlasRigLowerAttach`.
  atlasRigLower.morph.run = (rig, buddy) => {
    const M = atlasRigLower.morph;
    const low = rig.lower;
    const m = (low.morph ||= { ang: [[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]], targets: null, clock: Math.random() * 40, gain: 1, speed: 1, n: 0, at: 0, moved: false, timer: 0 });
    const step = () => {
      clearTimeout(m.timer);
      const box = rig.box;
      if (!box.isConnected) return;
      const root = document.documentElement;
      const live = atlasMotionOK(box) && !box.classList.contains("atl-off") && !document.hidden && !root.hasAttribute("data-atlas-hidden") && !root.hasAttribute("data-atlas-lite") && !box.closest("#nm-buddy.nm-buddy-dragging");
      if (!live) {
        if (m.moved) M.rest(low);
        m.at = 0;
        m.timer = setTimeout(step, 1000);
        return;
      }
      const now = performance.now();
      //: At rest the paths keep the shape they have; the first input starts them again (`atlasTailCalm.rest`).
      if (atlasTailCalm.rest.sync(box, low.state)) {
        m.at = 0;
        m.timer = setTimeout(step, 1000);
        return;
      }
      m.targets ||= M.build(low);
      const dt = m.at ? Math.min(0.25, (now - m.at) / 1000) : 0;
      m.at = now;
      const [reach, rate] = atlasRigLower.flowByState[low.state] || [1, 1];
      const ease = 1 - Math.exp(-dt / 0.8);
      m.gain += (reach ** 0.6 - m.gain) * ease;
      m.speed += (1 / rate - m.speed) * ease;
      m.clock += dt * m.speed;
      //: The ribbons every tick (a tip travels furthest); the band, the dress and the glints, which move a pixel, on alternate ticks.
      m.n += 1;
      m.targets.forEach((t, i) => {
        if (t.kind === "ribbon" || (m.n + i) % 2) M.draw(t, m.clock, m.gain, m.ang);
      });
      m.moved = true;
      m.timer = setTimeout(step, M.tick);
    };
    clearTimeout(m.timer);
    m.timer = setTimeout(step, 1500);
    atlasTailCalm.rest.wake.delete(m.wake);
    m.wake = () => {
      if (!rig.box.isConnected) return;
      atlasTailCalm.rest.sync(rig.box, low.state);
      //: The pacer (avatars.js) sleeps a second at a time while it rests; input starts its next beat now.
      if (typeof nmbTempo === "object" && nmbTempo.timer) {
        clearTimeout(nmbTempo.timer);
        nameMarkBuddyTempo();
      }
      if (m.at === 0 && m.targets) step();
    };
    atlasTailCalm.rest.wake.add(m.wake);
  };
  //: **When the lower body spells a state of its own** (atlascat-1108 C5): the base state (`atlasLowerState`) read with how
  //: long it has lasted and what the figure is doing: a fast glide's first 1.5 s billows the hem; cross-legged meditation
  //: is a coil; 40 s of sitting spreads it into a pool; a calm idle ripples for 8 s of every 40 once 24 s in; an excited mood
  //: flutters it; a glad one kicks the hem for 2.5 s of every 12; a twirl (`atl-play-spin`) leaves a spiral that unwinds over
  //: 2.5 s; a tired one (sleepy or drowsy) is heavy. Everything else is the base state. It reads the clock and nothing else,
  //: so a figure at rest costs nothing more: the states that rest re-read it on their 5 to 9 s timer.
  atlasRigLower.spell = (buddy, box) => {
    const base = atlasLowerState(buddy, box);
    const now = performance.now();
    const seen = (box.atlasLowerSeen ||= { key: "", at: now, spun: -1e9 });
    if (seen.key !== base) {
      seen.key = base;
      seen.at = now;
    }
    if (box.classList.contains("atl-play-spin")) seen.spun = now;
    if (now - seen.spun < 2500) return "spiral";
    return atlasRigLower.spell.of(base, (now - seen.at) / 1000, box.dataset.atlasMood || "calm", buddy);
  };
  atlasRigLower.spell.of = (base, held, mood, buddy) => {
    const has = (c) => !!buddy && buddy.classList.contains(c);
    if (base === "glide") return held < 1.5 ? "billow" : base;
    if (base === "sit") return has("nmb-act-meditate") ? "coil" : held >= 40 ? "pool" : base;
    if (base === "idle") return mood === "calm" && held % 40 >= 24 && held % 40 < 32 ? "ripple_calm" : base;
    if (base === "happy") return ["delighted", "laughing"].includes(mood) ? "flutter" : held % 12 < 2.5 ? "hem_kick" : base;
    if (base === "sad") return mood === "sleepy" || has("nmb-drowsy") ? "heavy" : base;
    return base;
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
    atlasRigLower.morph.run(box.atlasRig, box.closest("#nm-buddy"));
  }
  //: The lower body's pose for the state: its variant (a new one as the
  //: state begins, and every 5 to 9 seconds at rest, on a timer), and the
  //: way a walk goes. Each part is a box of its own, and the change is a CSS
  //: transition on it, run by the compositor: the state's own time and
  //: curve, the tail and the hair a beat later and longer (follow-through).
  //: A change mid-way is taken up from where the part is, so nothing snaps.
  function atlasRigLower(rig, now, live, buddy) {
    const low = rig.lower;
    if (!low || !(low.boxes.length || low.tails.length || low.hair.length)) return;
    const base = atlasRigLower.spell(buddy, rig.box);
    const state = base === "lie" && atlasRigLower.asleep(buddy) ? "curl" : base;
    const spec = { ...ATLAS_LOWER_STATES[state], v: atlasRigLower.blend.of(ATLAS_LOWER_STATES[state].v) };
    const fresh = state !== low.state;
    if (fresh || (live && atlasRigLower.rests.has(state) && now >= low.at)) {
      //: Reduced motion keeps each state's first pose and no idle variation.
      const pick = live ? Math.floor(Math.random() * spec.v.length) : 0;
      //: Never the one it took the last time it was in this state (Brief 88:
      //: three or more variants per pose, never the last), on entering it
      //: as well as at rest; reduced motion keeps the first.
      const last = low.last[state] ?? -1;
      low.variant = live && spec.v.length > 1 && pick === last ? (pick + 1 + Math.floor(Math.random() * (spec.v.length - 1))) % spec.v.length : pick;
      low.last[state] = low.variant;
      //: An act's state takes the act's drawn variant (INBOX 1681), so the figure and its lower body agree.
      const posed = atlasRigLower.acts.includes(state) ? Number(buddy?.dataset.variant) : NaN;
      if (Number.isInteger(posed) && posed >= 0 && posed < spec.v.length) low.variant = low.last[state] = posed;
      low.state = state;
      low.at = now + 5000 + Math.random() * 4000;
    }
    clearTimeout(low.timer);
    //: The next idle variant, unless the tab is hidden or the figure gone or
    //: off screen then (it waits, and does nothing meanwhile).
    const next = () => {
      if (!rig.box.isConnected) return;
      if (document.hidden || rig.box.classList.contains("atl-off")) low.timer = setTimeout(next, 4000);
      else atlasRigLower(rig, performance.now(), atlasMotionOK(rig.box), buddy);
    };
    if (live && atlasRigLower.rests.has(state)) low.timer = setTimeout(next, low.at - now + 10);
    const way = state === "walk" ? (parseFloat(buddy?.style.getPropertyValue("--nmb-lean")) < 0 ? -1 : 1) : 1;
    const [rot, sx, sy, skew, tail] = spec.v[low.variant] || spec.v[0];
    const hairs = atlasRigLower.blend.of(ATLAS_HAIR_STATES[state]);
    const nebs = atlasRigLower.blend.of(ATLAS_NEB_STATES[state]);
    const [neb, nsx, nsy] = nebs[low.variant % nebs.length];
    const hair = hairs[low.variant % hairs.length] * way;
    const pose = (k) => `rotate(${atlasFix(rot * way * k)}deg) skewX(${atlasFix(skew * way * k)}deg) scale(${(1 + (sx - 1) * k).toFixed(3)}, ${(1 + (sy - 1) * k).toFixed(3)})`;
    const key = `${state} ${low.variant} ${way} ${live}`;
    if (key === low.shown) return;
    low.shown = key;
    atlasRigLower.flow(rig, state, live);
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
  //: The states that rest: a new variant every 5 to 9 s (INBOX 1680, 1683 B1: only standing did, so a sat or sleeping figure held one pose for minutes).
  atlasRigLower.rests = new Set(["idle", "sit", "lie", "curl", "think", "sad", "hang", "happy", "billow", "coil", "ripple_calm", "flutter", "pool", "hem_kick", "spiral", "heavy"]);
  //: The states an act poses (INBOX 1681): the act's drawn variant picks the row, so the figure and its lower body agree. They last one act, so none re-rolls on the rest timer.
  atlasRigLower.acts = ["crouch", "lounge", "glide", "drift"];
  //: Asleep: the sleeping class, a nap, or a lying or curled pose (a property, not a global: `tests/test_global_scope_ratchet.py`).
  atlasRigLower.asleep = (buddy) => !!buddy && (buddy.classList.contains("nmb-sleep") || buddy.classList.contains("nmb-act-nap") || /^(lie|curl)/.test(buddy.dataset.pose || ""));

  //: What scripts/render_desk_frames.js samples; `hold` is a tail the page's loop may not draw. A property, not a global (the scope ratchet).
  atlasTailFrame.kit = { draw: atlasTailDraw, bend: atlasTailBend, acts: ATLAS_TAIL_ACTS, swell: ATLAS_BREATH_SWELL, hold: null };

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { atlasPropLoops, atlasRigLower, atlasRigLowerAttach, atlasRingLoops, atlasTailAttach, atlasTailCalm, atlasTailFrame });
})();
