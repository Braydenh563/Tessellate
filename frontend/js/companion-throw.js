//: **Thrown, and what can happen on the way** (INBOX 1301 D6, the owner:
//: "If I flick the companion near the top bar or top screen elements, I
//: want there to be the chance that the compainon an datlas will land up
//: there or catch the rop elements and/or climb on to them, or maybe eve
//: splat on the edge of the screen and slide down to land on a platform,
//: maybe even the chance to go off one side and come back on the other").
//: A lazy file (`companionThrow` in app.js's LAZY_MODULES), fetched on the
//: first carry, so boot pays nothing for it; a let-go before it arrives is
//: a drop. The flight's physics stays avatars.js's (`nameMarkBuddyFlightStep`,
//: INBOX 882); `companionThrowStep` wraps each step and, the first time the
//: flight meets the top bar, a side of the window or a panel's top edge from
//: below, rolls once for what happens there:
//: - the top bar's underside, met going up: caught, it hangs there (`hang`);
//: - a panel's top edge, passed going up or reached at the top of the arc:
//:   caught by the hands, it hangs a moment, dips and climbs on (`climb`);
//: - a side, met fast: it splats flat against it, holds, and slides down to
//:   the first ledge under it or the floor (`splat`); faster still, it may go
//:   off that side and come back on the other (`wrap`);
//: - coming down just past a panel's end, a hand may catch its edge
//:   (`grab`); sliding off the end of one it landed on, it may catch the
//:   edge as it goes (`slip`): either way it hangs a moment and pulls itself
//:   up on to it (K12, the owner: "catch a higher or lower ui element and
//:   perch on that ... or nearly slip off a ui element but manage to grab on
//:   and pull itself up");
//: - otherwise the bounce it always had, and its landing on the first ledge
//:   or the floor under its path.
//: How long it hangs before pulling up is rolled too (`fate.ms`), so no two
//: catches are timed alike.
//: Then it settles into one of the postures its perch allows
//: (`companionThrowSettle`: sitting with its legs dangling or kicking,
//: lying down, a stretch, a swing from the bar). Every place it ends is the
//: drop's (`nameMarkBuddyThrowSpot`), so it never ends over a control.
//: Pure apart from `nameMarkBuddyThrow` and the three DOM helpers under it;
//: the rolls come from `rand`, seeded by `companionThrowSeed` in the sweep
//: (scratchpad/ui-sweeps/throwfates.js) and in tests/test_companion_throw_fates.py.
const COMPANION_THROW_ODDS = { hang: 0.55, climb: 0.45, wrap: 0.3, splat: 0.4, grab: 0.5, slip: 0.6 };
//: The speed, px per ms, each needs where it meets the edge: a lob that
//: barely reaches the bar is not caught, a nudge into a side does not splat.
//: The bar was 0.35 and 0.4 odds: most throws to it bounced off (K12, the
//: owner: "every time I throw the companion to the roof it just bounces off").
const COMPANION_THROW_NEEDS = { hang: 0.2, splat: 0.9, wrap: 1.4 };
//: How far under an edge its hands still catch it at the top of the arc.
const COMPANION_THROW_REACH = 26;
//: How far past a panel's end a falling hand still catches its edge.
const COMPANION_THROW_GRAB = 22;
//: Flat against a side this long before it slides, at most this fast.
const COMPANION_THROW_HOLD = 240;
const COMPANION_THROW_SLIDE = 0.32;
//: Hanging from the edge it caught before it pulls itself up: this, times
//: 0.8 to 1.6 by a roll.
const COMPANION_THROW_CLIMB_MS = 520;
//: A seed for the rolls (0: `Math.random`); the sweep sets it.
//: The sweep sets `.seed`; 0 is Math.random.
const companionThrowSeed = { seed: 0 };

//: Mulberry32: the same rolls for the same seed, in node and the browser.
function companionThrowRng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

//: One step of a throw, pure: `base` is the flight's own step, `world` its
//: room plus `w` (its width, for going off a side), `hang` (its corner's y
//: hanging under the top bar, null with no bar) and `climb` (from standing
//: on a ledge down to hanging from that ledge's edge). `s.tried` keeps each
//: contact rolled once; `s.fate` is what happened.
function companionThrowStep(s, dt, world, k, base, rand) {
  if (s.rest) return s;
  if (s.splat) return companionThrowSlide(s, dt, world, k);
  if (s.wrap) return companionThrowWrapOn(base(s, dt, { ...world, left: -Infinity, right: Infinity }, k), world, dt);
  const n = companionThrowDown(s, companionThrowUp(s, companionThrowSide(s, base(s, dt, world, k), world, rand), world, rand), world, rand);
  if (n.rest && !n.fate) n.fate = { kind: n.on === "floor" ? "floor" : n.on ? "ledge" : "air" };
  return n;
}

//: Met a side: off it and round to the other, flat against it, or the bounce.
function companionThrowSide(s, n, world, rand) {
  const side = n.x <= world.left && s.x > world.left ? "l" : n.x >= world.right && s.x < world.right ? "r" : "";
  if (!side || s.tried?.side) return n;
  const tried = { ...s.tried, side: true };
  const speed = Math.abs(s.vx);
  const wrap = speed >= COMPANION_THROW_NEEDS.wrap ? COMPANION_THROW_ODDS.wrap : 0;
  const splat = speed >= COMPANION_THROW_NEEDS.splat ? COMPANION_THROW_ODDS.splat : 0;
  const r = rand();
  if (r < wrap) return { ...n, tried, x: side === "l" ? world.left - 1 : world.right + 1, vx: s.vx, wrap: side, fate: { kind: "wrap", side } };
  if (r < wrap + splat) return { ...n, tried, x: side === "l" ? world.left : world.right, vx: 0, vy: 0, rot: 0, splat: { side, hold: COMPANION_THROW_HOLD }, fate: { kind: "splat", side } };
  return { ...n, tried };
}

//: Going off a side: once wholly out of the window it is gone a moment
//: (`COMPANION_THROW_GONE`, so at least two frames show it neither side),
//: comes in at the other side, and flies on as before once wholly back in.
//: Come to rest outside (a floor's grip, the flight's time), it is put back
//: just inside.
const COMPANION_THROW_GONE = 60;
function companionThrowWrapOn(n, world, dt) {
  const m = { ...n };
  if ((m.wrap === "l" && m.x < world.left - world.w) || (m.wrap === "r" && m.x > world.right + world.w)) {
    m.gone = { from: m.wrap, left: COMPANION_THROW_GONE };
    m.wrap = "gone";
  } else if (m.wrap === "gone") {
    m.gone = { ...m.gone, left: m.gone.left - dt };
    if (m.gone.left <= 0) Object.assign(m, { x: m.gone.from === "l" ? world.right + world.w : world.left - world.w, wrap: "in" });
  } else if (m.wrap === "in" && m.x >= world.left && m.x <= world.right) m.wrap = null;
  if (m.rest) {
    m.x = Math.min(Math.max(m.x, world.left), world.right);
    m.wrap = null;
  }
  return m;
}

//: Flat against a side: held, then sliding down at no more than
//: `COMPANION_THROW_SLIDE` until the first ledge under it or the floor.
function companionThrowSlide(s, dt, world, k) {
  const n = { ...s, t: s.t + dt, hit: 0 };
  if (n.splat.hold > 0) return { ...n, splat: { ...n.splat, hold: n.splat.hold - dt } };
  const py = n.y;
  n.vy = Math.min(COMPANION_THROW_SLIDE, Math.max(0, n.vy) + k.g * 0.3 * dt);
  n.y += n.vy * dt;
  let land = null;
  for (const l of world.ledges || []) {
    if (py < l.y && n.y >= l.y && n.x >= l.left && n.x <= l.right && (!land || l.y < land.y)) land = l;
  }
  if (land || n.y >= world.floor) {
    n.y = land ? land.y : world.floor;
    n.on = land || "floor";
    n.hit = n.vy;
    n.rest = true;
  }
  return n;
}

//: Going up: the top bar caught, or a panel's top edge caught by the hands.
function companionThrowUp(s, n, world, rand) {
  if (n.rest || n.splat || n.wrap || s.vy >= 0) return n;
  if (world.hang !== null && world.hang !== undefined && n.y <= world.top && s.y > world.top && !n.tried?.roof) {
    const tried = { ...n.tried, roof: true };
    if (-s.vy >= COMPANION_THROW_NEEDS.hang && rand() < COMPANION_THROW_ODDS.hang) return { ...n, tried, y: world.hang, vx: 0, vy: 0, rot: 0, rest: true, fate: { kind: "hang" } };
    return { ...n, tried };
  }
  let m = n;
  for (const l of world.ledges || []) {
    const grip = l.y + world.climb;
    const key = `l${Math.round(l.left)},${Math.round(l.y)}`;
    if (m.x < l.left || m.x > l.right || m.tried?.[key]) continue;
    const passes = s.y >= grip && m.y < grip;
    const reaches = m.vy >= 0 && m.y >= grip && m.y - grip <= COMPANION_THROW_REACH;
    if (!passes && !reaches) continue;
    const tried = { ...m.tried, [key]: true };
    if (rand() < COMPANION_THROW_ODDS.climb) return companionThrowHold({ ...m, tried }, l, world, "climb", rand);
    m = { ...m, tried };
  }
  return m;
}

//: Coming down: off the end of the ledge it slid along (`slip`), or
//: falling just past a ledge's end as its hands pass the edge (`grab`).
function companionThrowDown(s, n, world, rand) {
  if (n.rest || n.splat || n.wrap) return n;
  const slid = s.on && s.on !== "floor" && !n.on ? s.on : null;
  if (slid) return rand() < COMPANION_THROW_ODDS.slip ? companionThrowHold(n, slid, world, "slip", rand) : n;
  if (n.on || s.vy <= 0) return n;
  let m = n;
  for (const l of world.ledges || []) {
    const grip = l.y + world.climb;
    const key = `g${Math.round(l.left)},${Math.round(l.y)}`;
    const past = Math.max(l.left - m.x, m.x - l.right);
    if (past <= 0 || past > COMPANION_THROW_GRAB || m.tried?.[key] || s.y >= grip || m.y < grip) continue;
    const tried = { ...m.tried, [key]: true };
    if (rand() < COMPANION_THROW_ODDS.grab) return companionThrowHold({ ...m, tried }, l, world, "grab", rand);
    m = { ...m, tried };
  }
  return m;
}

//: Hanging by its hands from ledge `l`'s edge, at the end nearest, to pull
//: itself up on to it after a rolled while.
function companionThrowHold(n, l, world, kind, rand) {
  const x = Math.min(Math.max(n.x, l.left), l.right);
  const ms = Math.round(COMPANION_THROW_CLIMB_MS * (0.8 + rand() * 0.8));
  return { ...n, x, y: l.y + world.climb, vx: 0, vy: 0, rot: 0, rest: true, on: null, fate: { kind, at: [Math.round(x), l.y], ms } };
}

//: Where the drop looks for its place: a climb's is the top of the edge it
//: caught, everything else's where it stopped.
function companionThrowAt(s) {
  return s.fate?.at ? { ...s, x: s.fate.at[0], y: s.fate.at[1] } : s;
}

//: **What it does once it is down**, by the pose its place gave it and a
//: roll: more than one way to sit, lie, hang and stand (the owner: "more
//: variety in body posture like sitting down, lying down, in different
//: ways, leaning"). Off a side it is dazed first. Each is one of the
//: companion's own acts (avatars.js, NAME_MARK_BUDDY_ACTS).
const COMPANION_THROW_SETTLE = {
  hang: ["swing", "onehand", "feet", "sloth"],
  sit: ["dangle", "kick", "dangle", "shrug"],
  stand: ["lie", "stretch", "shrug", "scratch"],
  lean: ["shrug", "scratch", "wave"],
  float: ["shrug", "wave"],
};
function companionThrowSettle(kind, pose, roll) {
  if ((kind === "splat" || kind === "slip") && pose !== "hang") return roll < 0.6 ? "scratch" : "shrug";
  const list = COMPANION_THROW_SETTLE[pose] || [];
  return list[Math.min(list.length - 1, Math.floor(roll * list.length))] || "";
}

//: **The whole flight is worked out when it is let go** (the owner,
//: 2026-10-27: "throwing the companion is now framey, not clean or smooth
//: and glitchy"). Its path, 16ms steps from (`x`, `y`) at `vx`, `vy` (px
//: per ms) to rest, and where it comes down (`nameMarkBuddyThrowSpot`, the
//: page measured once) are fixed here, in the release, before it writes
//: anything; the frames only draw the path. Measured (throw5.js, Atlas,
//: 1440x900): the landing was worked out in the frame it came to rest, 11
//: to 40ms at 1x CPU and 217ms (122 of it forced layout) at 4x, in a frame
//: the drawing had already dirtied. Reduce motion: the plain flight, no fates.
function companionThrowPlan(x, y, vx, vy, world) {
  const rand = companionThrowSeed.seed ? companionThrowRng(companionThrowSeed.seed) : Math.random;
  const feel = nameMarkBuddyThrowFeel([rand(), rand(), rand()], Math.hypot(vx, vy));
  const room = { ...world, w: NMB_W, hang: world.top > 0 ? world.top - NMB_GRIP : null, climb: NMB_FEET - 1 - NMB_GRIP };
  const still = nameMarkBuddyNoTravel();
  let s = { x, y, vx, vy, rot: 0, t: 0, on: null, rest: false, tried: {} };
  const path = [s];
  //: A cap past any flight's own (1.2 s, a splat's slide): it always ends.
  while (!s.rest && path.length < 400) {
    s = still ? nameMarkBuddyFlightStep(s, 16, world, feel) : companionThrowStep(s, 16, room, feel, nameMarkBuddyFlightStep, rand);
    path.push(s);
  }
  if (!s.rest) path[path.length - 1] = s = { ...s, rest: true };
  return { path, still, rand, v: [vx, vy], spot: nameMarkBuddyMeasureOnce(() => nameMarkBuddyThrowSpot(companionThrowAt(s))) };
}

//: Where the path has it `ms` into the flight: between its two steps, so
//: a frame that is not a multiple of 16ms is drawn where it is, not where
//: the last step left it. A step that moves it far (round to the other
//: side, on to a ledge's end) is taken as it is, never swept across.
function companionThrowAtTime(path, ms) {
  const i = Math.min(path.length - 1, Math.max(0, Math.floor(ms / 16)));
  const a = path[i];
  const b = path[i + 1];
  if (!b || Math.hypot(b.x - a.x, b.y - a.y) > 60 || Math.abs(b.rot - a.rot) > 90) return a;
  const f = Math.min(1, Math.max(0, (ms - a.t) / Math.max(1, b.t - a.t)));
  return { ...a, x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, rot: a.rot + (b.rot - a.rot) * f };
}

//: The throw itself (moved here from avatars.js, INBOX 882): `plan` from
//: `companionThrowPlan` (made here when a sweep throws it), drawn a frame
//: at a time on transforms only, then its place. Reduce motion: straight
//: to where it comes down, a crossfade.
function nameMarkBuddyThrow(buddy, vx, vy, world, plan = companionThrowPlan(nmb.x, nmb.y, vx, vy, world)) {
  nmb.flight?.stop();
  nmb.home = null;
  const tab = nameMarkBuddyTab();
  const { path, rand } = plan;
  const end = path[path.length - 1];
  const landing = plan.spot;
  nmb.thrown = { v: [+vx.toFixed(2), +vy.toFixed(2)], from: [Math.round(path[0].x), Math.round(path[0].y)] };
  if (plan.still) {
    nameMarkBuddyThrowLand(buddy, end, tab, landing);
    return;
  }
  const char = buddy.querySelector(".nm-buddy-char");
  buddy.classList.add("nm-buddy-dragging");
  //: The flight's own clock: hidden, frames stop and it waits in the air;
  //: back, it flies on from there rather than jumping a long step. Its
  //: first frame is one step: the release's own task (20 to 100ms at 1x
  //: CPU) is not flight, and counted it drew a 55 to 70px jump (throw5.js).
  let then = 0;
  let flown = 0;
  let step = 0;
  const flight = {
    raf: 0,
    timer: 0,
    stop() {
      cancelAnimationFrame(flight.raf);
      clearTimeout(flight.timer);
      if (nmb.flight !== flight) return;
      nmb.flight = null;
      buddy.classList.remove("nm-buddy-dragging", "nmb-splat", "nmb-climb", "nmb-slip");
      delete buddy.dataset.splat;
      nameMarkBuddySway(buddy, 0);
      if (!char) return;
      //: Stopped while still turned (the cap, a grab): eased upright, the
      //: short way, never snapped.
      const r = ((((Number.parseFloat(char.style.rotate) || 0) + 180) % 360) + 360) % 360 - 180;
      char.style.rotate = "";
      char.style.animationDuration = "";
      if (Math.abs(r) > 1 && typeof char.animate === "function") char.animate([{ rotate: `${r}deg` }, { rotate: "0deg" }], { duration: 260, easing: "ease-out" });
    },
  };
  //: Writes only: nothing in a frame reads the page.
  const frame = (now) => {
    if (nmb.flight !== flight) return;
    if (!buddy.isConnected) return flight.stop();
    flown = Math.min(end.t, flown + (then ? Math.min(32, Math.max(0, now - then)) : 16));
    then = now;
    //: The hardest landing among the 16ms steps this frame passed.
    let hit = 0;
    while (step + 1 < path.length && path[step + 1].t <= flown) {
      step += 1;
      hit = Math.max(hit, path[step].hit || 0);
    }
    const s = flown >= end.t ? end : companionThrowAtTime(path, flown);
    nameMarkBuddyPut(buddy, Math.round(s.x), Math.round(s.y));
    if (char) char.style.rotate = `${s.rot.toFixed(1)}deg`;
    nameMarkBuddySway(buddy, Math.max(-28, Math.min(28, -s.vx * 10)));
    if (hit > 0.5 && char && typeof char.animate === "function") {
      //: Squashed by how hard it came down.
      const a = Math.min(0.22, hit * 0.09);
      char.animate([{ scale: "1 1" }, { scale: `${1 + a} ${1 - a}` }, { scale: "1 1" }], { duration: 220, easing: "ease-out" });
    }
    companionThrowFlat(buddy, char, s);
    if (s.rest) {
      const land = () => {
        flight.stop();
        nmb.thrown.fate = s.fate?.kind || "";
        nameMarkBuddyThrowLand(buddy, s, tab, landing);
        companionThrowSettleSoon(buddy, s, landing, rand);
      };
      if (COMPANION_THROW_PULLS.includes(s.fate?.kind) && landing.y < s.y) companionThrowClimb(buddy, flight, land, s.fate);
      else land();
      return;
    }
    next();
  };
  //: Its one frame loop, running only while it flies (the wake-source
  //: seed's one in this file).
  const next = () => {
    flight.raf = requestAnimationFrame(frame);
  };
  nmb.flight = flight;
  next();
}

//: Flat against a side while it holds and slides (the lazy CSS,
//: `.nmb-splat`), squashed into it on the frame it hits; a class change only
//: when that changes.
function companionThrowFlat(buddy, char, s) {
  const flat = !!s.splat && !s.rest;
  if (flat === buddy.classList.contains("nmb-splat")) return;
  buddy.classList.toggle("nmb-splat", flat);
  if (!flat) {
    delete buddy.dataset.splat;
    return;
  }
  buddy.dataset.splat = s.splat.side;
  nameMarkBuddyExpress("surprised", 1400, { drift: true });
  if (char && typeof char.animate === "function") char.animate([{ scale: "0.6 1.2" }, { scale: "0.84 1.08" }], { duration: 240, easing: "ease-out" });
}

//: Caught by its hands on a panel's top edge (going up, coming down past
//: its end, or slipping off it): it hangs there, dips and pulls
//: (`.nmb-climb`, the lazy CSS, over the rolled `fate.ms`), then climbs on
//: (the move to its place). A grab in the meantime stops the flight, and
//: the climb with it.
const COMPANION_THROW_PULLS = ["climb", "grab", "slip"];
function companionThrowClimb(buddy, flight, land, fate) {
  buddy.classList.remove("nm-buddy-dragging");
  buddy.dataset.pose = "hang";
  buddy.dataset.legs = "";
  const char = buddy.querySelector(".nm-buddy-char");
  if (char) char.style.animationDuration = `${fate.ms}ms`;
  buddy.classList.add("nmb-climb");
  //: Nearly gone: a jolt as the hand catches, and a startled face.
  if (fate.kind === "slip") {
    buddy.classList.add("nmb-slip");
    nameMarkBuddyExpress("surprised", fate.ms + 600, { drift: true });
  }
  flight.timer = setTimeout(land, fate.ms);
}

//: Once it has landed (and the landing's own act is over), one of the
//: postures its place allows, if it is still there and nothing else has
//: started.
function companionThrowSettleSoon(buddy, s, spot, rand) {
  const act = companionThrowSettle(s.fate?.kind || "", spot.pose, rand());
  if (!NAME_MARK_BUDDY_ACTS[act] || nameMarkBuddyActOff(act) || (act === "lie" && !nameMarkBuddyLieRoom())) return;
  setTimeout(() => {
    if (nmb.spot === spot && !nmb.act && !nmb.flight && !nameMarkBuddyStill() && buddy.isConnected) nameMarkBuddyAct(act);
  }, 900);
}
