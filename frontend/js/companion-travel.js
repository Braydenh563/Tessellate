//: **How it gets somewhere far, and what it does instead of going** (INBOX
//: 1429, the owner: "the companion always chooses to jump across the screen
//: and it is very visually distracting. I need it to choose more things, like
//: summoning a portal and walking through it, vanishing in a puff of smoke,
//: walking off the edge of the screen and coming out somewhere else, ducking
//: below the bottom bar and climbing down from the top and vice versa. more
//: varied biological actions. the companion needs to be a companion, not
//: something that distracts the user from their work").
//: A lazy file with its own sheet, fetched by companion-menu.js (the
//: companion's mind, `companionMenu` in app.js's LAZY_MODULES, at its first
//: tick), so boot pays nothing for it. Until it is here a far move walks.
//:
//: `nameMarkBuddyGo` (avatars.js) asks `nmb.travelPlay` for a move past
//: `NMB_FAR_SIZES` of itself. `companionTravelChoose` is pure: the last move,
//: where it goes and the window in, a weighted pick among the calm ways, never
//: the one before:
//:   portal  a ring opens beside it, it walks in; one opens where it is going
//:   smoke   a puff, gone; a puff there, back
//:   edge    off the nearest side of the window, in from the side nearest there
//:   walk    on foot (avatars.js's own: a level way, or a climb across levels)
//:   fade    reduced motion: a crossfade, and nothing else
//: Every move is one animation of the host's `translate` and `opacity`, on the
//: compositor, plus a few small elements for the rings and the puffs (the lazy
//: sheet). **It never passes through a bar** (INBOX 1463, the owner: "the
//: companion just went through the bottom bar and started falling from the top
//: bar and ... part of its body was missing"): the duck move, which hid it
//: behind one bar with a `clip-path` and let it down from the other, is gone,
//: and no move leaves the window by its top or bottom (the edge move leaves by
//: a side only). Nothing here clips it.
//: `nmb.travelForce` names a move to play whatever the chooser would say (the
//: sweep, scratchpad/ui-sweeps/companiontravel.js).
//: INBOX 1692 (the owner: "no real animation or life", "a portal or like magic ... float on a cloud"): three more calm
//: ways, and the edge walk wraps with an exit and an entry.
//:   blink   sparkles gather, it is gone, sparkles scatter where it lands
//:   cloud   a small cloud forms under it and it rides it, bobbing, to the place
//:   bubble  it is lifted inside a bubble that rises, drifts and sets it down
const COMPANION_TRAVEL_MOVES = ["walk", "portal", "smoke", "edge", "blink", "cloud", "bubble"];
//: A way on foot off the window and back in may not be longer than this many of its own widths.
const COMPANION_TRAVEL_EDGE_SIZES = 14;

//: The weight of each move, pure. `o`: `last` (the move before), `dx`, `dy`
//: (back to where it was), `size` its width, `reduced`, `win` [width,
//: height], `x0` where it was and `x1` where it goes.
function companionTravelWeights(o) {
  if (o.reduced) return { fade: 1 };
  const s = o.size;
  const d = Math.hypot(o.dx, o.dy);
  const [width] = o.win;
  //: A puff is rare (INBOX 1683 u: the owner saw only puffs); the portal and the edge walk lead, a walk keeps the near.
  const w = { walk: d <= s * 8 ? 3 : 1.2, portal: d > s * 2.5 ? 3 : 0, smoke: d > s * 2 ? 0.25 : 0, edge: 0, blink: d > s * 2 ? 2 : 0, cloud: d > s * 2.5 ? 2.5 : 0, bubble: d > s * 2.5 ? 1.8 : 0 };
  const out = Math.min(o.x0, width - s - o.x0);
  const into = Math.min(o.x1, width - s - o.x1);
  if (d > s * 3 && out + into + s * 2 <= s * COMPANION_TRAVEL_EDGE_SIZES) w.edge = 2.5;
  if (o.last in w) w[o.last] = 0;
  return w;
}

//: The move for a roll in [0, 1): by weight, never `o.last` unless nothing else suits.
function companionTravelChoose(o, roll) {
  const w = companionTravelWeights(o);
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  if (!total) return o.reduced ? "fade" : "walk";
  let left = roll * total;
  for (const [move, weight] of Object.entries(w)) {
    left -= weight;
    if (weight > 0 && left <= 0) return move;
  }
  return Object.keys(w).filter((move) => w[move] > 0).pop();
}

//: ---- Playing a move
//:
//: Each is one `buddy.animate` for the host (`nmb.anim`, so a move that
//: starts while it is on its way takes over like any other), its body's
//: scale on `nmb.hopAnim`, and the rings or puffs as small elements beside
//: it, gone when it ends or is cut. Nothing in here is called per frame.
function companionTravelFx(buddy, cls, dx, dy, delay, parts, life) {
  const host = buddy.parentElement;
  if (!host) return;
  const fx = document.createElement("span");
  fx.className = cls;
  fx.setAttribute("aria-hidden", "true");
  fx.style.transform = `translate(${nmb.lx + dx}px, ${nmb.ly + dy}px)`;
  fx.style.setProperty("--nmb-burst-delay", `${delay}ms`);
  for (let i = 0; i < parts; i += 1) {
    const part = document.createElement("i");
    part.style.setProperty("--nmb-burst-a", `${Math.round((i / parts) * 360 + Math.random() * 40 - 20)}deg`);
    part.style.setProperty("--nmb-burst-r", `${14 + Math.round(Math.random() * 12)}px`);
    fx.appendChild(part);
  }
  host.appendChild(fx);
  nmb.travelFx.push(fx);
  setTimeout(() => fx.remove(), delay + life);
}

//: The end of a move, or its being cut: everything it set comes off.
function companionTravelEnd(buddy, anim) {
  if (nmb.anim !== anim) return;
  for (const t of nmb.travelTimers) clearTimeout(t);
  nmb.travelTimers = [];
  for (const fx of nmb.travelFx) fx.remove();
  nmb.travelFx = [];
  buddy.classList.remove("nmb-poofing");
  if (buddy.classList.contains("nmb-walking")) nameMarkBuddyBlend(buddy, () => buddy.classList.remove("nmb-walking"));
  delete buddy.dataset.turn;
  nameMarkBuddyTravel(buddy, "");
}

//: **On a page a frame has drawn** (INBOX 1667: `companion-travel.js:106` 30ms of forced layout at 4x): a
//: step's `nameMarkBuddyBlend` reads the parts it moves, and a timer lands between the page's writes and
//: its frame. The step runs a frame on (`nmb.afterClean`), unless the move ended or was cut meanwhile
//: (the list it was filed in is gone).
function companionTravelAt(ms, fn) {
  const list = nmb.travelTimers;
  list.push(setTimeout(() => nmb.afterClean(() => nmb.travelTimers === list && fn()), ms));
}

//: Its legs walking from `ms` for `len` ms.
function companionTravelSteps(buddy, ms, len) {
  companionTravelAt(ms, () => {
    nameMarkBuddyBlend(buddy, () => buddy.classList.add("nmb-walking"), NMB_BLEND_IN_MS);
    nmbTempo.seen = 0;
    clearTimeout(nmbTempo.timer);
    nmbTempo.timer = setTimeout(nameMarkBuddyTempo, 0);
  });
  companionTravelAt(ms + len, () => nameMarkBuddyBlend(buddy, () => buddy.classList.remove("nmb-walking")));
}

//: A ride (cloud, bubble): it is carried the whole way, an element of its own (the cloud, the bubble) moving with it
//: on the same eased path, formed in the first tenth and thinned at the last. `o.bob` is how far the path arcs up
//: (a cloud a little, a bubble a lot); `o.rise` the figure's lift onto it.
function companionTravelRide(buddy, dx, dy, ctx, cls, o) {
  const host = buddy.parentElement;
  const T = Math.min(3400, 1800 + Math.hypot(dx, dy) * 1.2);
  const path = (k) => `${Math.round(dx * (1 - k))}px ${Math.round(dy * (1 - k) - o.bob * Math.sin(Math.PI * k))}px`;
  const marks = [0, 0.1, 0.3, 0.5, 0.7, 0.9, 1];
  ctx.ms = T;
  ctx.frames = marks.map((k, i) => ({ translate: path(k), opacity: 1, offset: k, easing: i ? "ease-in-out" : "ease-in" }));
  ctx.body = [{ translate: "0px 0px", scale: "1", offset: 0 }, { translate: `0px ${o.rise}px`, scale: o.scale, offset: 0.12, easing: "ease-out" }, { translate: `0px ${o.rise}px`, scale: o.scale, offset: 0.88 }, { translate: "0px 0px", scale: "1", offset: 1 }];
  ctx.turn = dx > 0 ? "l" : "r";
  if (!host) return;
  const el = document.createElement("span");
  el.className = cls;
  el.setAttribute("aria-hidden", "true");
  el.style.left = `${nmb.lx}px`;
  el.style.top = `${nmb.ly}px`;
  const at = (k) => ({ translate: path(k) });
  el.animate(marks.map((k, i) => ({ ...at(k), opacity: i === 0 || i === 6 ? 0 : 1, scale: i === 0 || i === 6 ? "0.3" : "1", offset: k })), { duration: T, easing: "ease-in-out" });
  host.appendChild(el);
  nmb.travelFx.push(el);
  setTimeout(() => el.remove(), T + 80);
}

const COMPANION_TRAVEL_PLAYERS = {
  //: A puff over it, gone, a puff there, back. 900ms.
  smoke(buddy, dx, dy, ctx) {
    const T = 900;
    const cut = 0.27;
    const pos = (x, y, extra = {}) => ({ translate: `${x}px ${y}px`, ...extra });
    ctx.frames = [
      pos(dx, dy, { opacity: 1, offset: 0 }),
      pos(dx, dy, { opacity: 1, offset: 0.1 }),
      pos(dx, dy, { opacity: 0, offset: cut }),
      pos(0, 0, { opacity: 0, offset: cut + 0.001 }),
      pos(0, 0, { opacity: 0, offset: 0.52 }),
      pos(0, 0, { opacity: 1, offset: 0.72 }),
      pos(0, 0, { opacity: 1, offset: 1 }),
    ];
    ctx.ms = T;
    ctx.body = [{ scale: "1", offset: 0 }, { scale: "0.8", offset: cut }, { scale: "0.8", offset: 0.52 }, { scale: "1.04", offset: 0.8, easing: "ease-out" }, { scale: "1", offset: 1 }];
    companionTravelFx(buddy, "nmb-smoke", dx, dy, 0, 6, 760);
    companionTravelFx(buddy, "nmb-smoke", 0, 0, T * 0.48, 6, 760);
  },
  //: A ring beside it opens, it walks into it small; one opens beside where
  //: it goes and it walks out of that. 2.1s.
  portal(buddy, dx, dy, ctx) {
    const T = 2100;
    const dir = dx > 0 ? -1 : 1;
    const step = 40 * dir;
    const pos = (x, y, extra = {}) => ({ translate: `${x}px ${y}px`, ...extra });
    ctx.frames = [
      pos(dx, dy, { opacity: 1, offset: 0 }),
      pos(dx, dy, { opacity: 1, offset: 0.14 }),
      pos(dx + step, dy, { opacity: 0, offset: 0.42, easing: "ease-in" }),
      pos(-step, 0, { opacity: 0, offset: 0.43 }),
      pos(-step, 0, { opacity: 0, offset: 0.6 }),
      pos(-step, 0, { opacity: 1, offset: 0.61 }),
      pos(0, 0, { opacity: 1, offset: 0.9, easing: "ease-out" }),
      pos(0, 0, { opacity: 1, offset: 1 }),
    ];
    ctx.ms = T;
    ctx.body = [{ scale: "1", offset: 0 }, { scale: "1", offset: 0.14 }, { scale: "0.15", offset: 0.42, easing: "ease-in" }, { scale: "0.15", offset: 0.6 }, { scale: "1", offset: 0.9, easing: "ease-out" }, { scale: "1", offset: 1 }];
    ctx.turn = dir > 0 ? "r" : "l";
    companionTravelFx(buddy, "nmb-portal", dx + step, dy, 0, 0, 1260);
    companionTravelFx(buddy, "nmb-portal", -step, 0, T * 0.46, 0, 1260);
    companionTravelSteps(buddy, T * 0.14, T * 0.28);
    companionTravelSteps(buddy, T * 0.61, T * 0.29);
  },
  //: Off the side of the window nearest where it was, in from the side nearest where it goes. It keeps the pose it
  //: had until it is out of sight (a hang does not stand up on the spot), squeezes thin through the edge with wisps
  //: trailing and, mirrored, comes in the same way; each run is eased, never one linear slide (INBOX 1692).
  edge(buddy, dx, dy, ctx) {
    const W = innerWidth;
    const was = ctx.was;
    const pace = 3.4; // ms per px of the walk off and on
    const outTo = was.x + NMB_W / 2 < W / 2 ? -(was.x + NMB_W + 8) : W - was.x + 8;
    const inFrom = nmb.x + NMB_W / 2 < W / 2 ? -(nmb.x + NMB_W + 8) : W - nmb.x + 8;
    const t1 = Math.max(700, Math.abs(outTo) * pace);
    const t2 = Math.max(700, Math.abs(inFrom) * pace);
    const gap = 260;
    const T = t1 + gap + t2;
    const a = t1 / T;
    const b = (t1 + gap) / T;
    const thin = "0.2 1.06";
    ctx.frames = [
      { translate: `${dx}px ${dy}px`, opacity: 1, offset: 0, easing: "ease-in" },
      { translate: `${dx + outTo * 0.8}px ${dy}px`, opacity: 1, offset: a * 0.8 },
      { translate: `${dx + outTo}px ${dy}px`, opacity: 0, offset: a },
      { translate: `${inFrom}px 0px`, opacity: 0, offset: a + 0.001 },
      { translate: `${inFrom}px 0px`, opacity: 0, offset: b, easing: "ease-out" },
      { translate: `${inFrom * 0.2}px 0px`, opacity: 1, offset: b + (1 - b) * 0.2 },
      { translate: "0px 0px", opacity: 1, offset: 1 },
    ];
    ctx.body = [
      { scale: "1 1", offset: 0 }, { scale: "1 1", offset: a * 0.5 }, { scale: thin, offset: a * 0.85, easing: "ease-in" },
      { scale: thin, offset: b }, { scale: thin, offset: b + (1 - b) * 0.15, easing: "ease-out" }, { scale: "1.04 0.98", offset: b + (1 - b) * 0.75 }, { scale: "1 1", offset: 1 },
    ];
    ctx.ms = T;
    ctx.turn = outTo < 0 ? "l" : "r";
    const hung = was.pose === "hang";
    if (was.pose && was.pose !== nmb.pose) {
      buddy.dataset.pose = was.pose;
      companionTravelAt(t1 + gap * 0.5, () => (buddy.dataset.pose = nmb.pose));
    }
    if (!hung) companionTravelSteps(buddy, 0, t1);
    companionTravelSteps(buddy, t1 + gap, t2);
    companionTravelAt(t1 + gap, () => (buddy.dataset.turn = inFrom < 0 ? "r" : "l"));
    for (let i = 0; i < 3; i += 1) {
      companionTravelFx(buddy, "nmb-wisp", dx + outTo * (0.5 + i * 0.18), dy, a * T * (0.6 + i * 0.12), 1, 700);
      companionTravelFx(buddy, "nmb-wisp", inFrom * (0.5 - i * 0.15), 0, (b + 0.04 + i * 0.05) * T, 1, 700);
    }
  },
  //: Sparkles gather round it, it is gone, sparkles scatter where it lands. 1.5s.
  blink(buddy, dx, dy, ctx) {
    const T = 1500;
    const cut = 0.34;
    const pos = (x, y, extra = {}) => ({ translate: `${x}px ${y}px`, ...extra });
    ctx.frames = [pos(dx, dy, { opacity: 1, offset: 0 }), pos(dx, dy, { opacity: 1, offset: 0.12 }), pos(dx, dy, { opacity: 0, offset: cut }), pos(0, 0, { opacity: 0, offset: cut + 0.001 }), pos(0, 0, { opacity: 0, offset: 0.52 }), pos(0, 0, { opacity: 1, offset: 0.78 }), pos(0, 0, { opacity: 1, offset: 1 })];
    ctx.ms = T;
    ctx.body = [{ scale: "1", offset: 0 }, { scale: "1.12", offset: 0.2, easing: "ease-in" }, { scale: "0.3", offset: cut }, { scale: "0.3", offset: 0.52 }, { scale: "1.08", offset: 0.82, easing: "ease-out" }, { scale: "1", offset: 1 }];
    companionTravelFx(buddy, "nmb-spark", dx, dy, 0, 8, 900);
    companionTravelFx(buddy, "nmb-spark", 0, 0, T * 0.5, 8, 900);
  },
  //: A cloud forms under it; it steps up, rides it (eased, with a slow bob) and steps off. 1.8s to 3.4s by the way.
  cloud(buddy, dx, dy, ctx) {
    companionTravelRide(buddy, dx, dy, ctx, "nmb-cloud", { rise: -8, bob: 6, scale: "1" });
  },
  //: Lifted in a bubble that rises, drifts over and sets it down. The same time.
  bubble(buddy, dx, dy, ctx) {
    companionTravelRide(buddy, dx, dy, ctx, "nmb-bubble", { rise: -14, bob: 70, scale: "0.9" });
  },
};

//: Play a far move; false when it should be walked (the chooser's "walk", or no player for it).
function companionTravelPlay(buddy, dx, dy, size, flies, was, force = "") {
  const o = { last: nmb.travelLast || "", dx, dy, size, flies, reduced: nameMarkBuddyNoTravel(), win: [innerWidth, innerHeight], x0: was.x, x1: nmb.x };
  const move = force || nmb.travelForce || companionTravelChoose(o, Math.random());
  nmb.travelLast = move;
  const player = COMPANION_TRAVEL_PLAYERS[move];
  if (!player) return false;
  const ctx = { was, frames: [], body: null, ms: 0, turn: "" };
  for (const t of nmb.travelTimers) clearTimeout(t);
  nmb.travelTimers = [];
  for (const fx of nmb.travelFx) fx.remove();
  nmb.travelFx = [];
  player(buddy, dx, dy, ctx);
  buddy.dataset.route = move;
  if (ctx.turn) buddy.dataset.turn = ctx.turn;
  nmb.anim = buddy.animate(ctx.frames, { duration: ctx.ms, easing: "linear" });
  const anim = nmb.anim;
  const char = buddy.querySelector(".nm-buddy-char");
  nmb.hopAnim = ctx.body && char ? char.animate(ctx.body, { duration: ctx.ms, easing: "ease-in-out" }) : null;
  nmb.moveSpeed = 0;
  buddy.classList.add("nmb-poofing");
  const end = () => companionTravelEnd(buddy, anim);
  anim.onfinish = end;
  anim.oncancel = end;
  return true;
}
nmb.travelPlay = companionTravelPlay;
