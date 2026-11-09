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
//:   blink   sparkles, gone, sparkles there, back (also a far move a new view asked for)
//:   cloud   a small cloud forms under it and carries it there, with a bob
//:   bubble  it floats up in a bubble, drifts there and the bubble pops
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
  const w = { walk: d <= s * 8 ? 3 : 1.2, portal: d > s * 2.5 ? 3 : 0, smoke: d > s * 2 ? 0.25 : 0, edge: 0 };
  const out = Math.min(o.x0, width - s - o.x0);
  const into = Math.min(o.x1, width - s - o.x1);
  if (d > s * 3 && out + into + s * 2 <= s * COMPANION_TRAVEL_EDGE_SIZES) w.edge = 2.5;
  //: The new ways are seen, not rare (INBOX 1692: "more life to it"); each wants a way worth the show.
  Object.assign(w, { blink: d > s * 2 ? 1.5 : 0, cloud: d > s * 3 ? 1.5 : 0, bubble: d > s * 3 ? 1 : 0 });
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
const COMPANION_TRAVEL_PACE = 3.4;

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
  return fx;
}

//: The end of a move, or its being cut: everything it set comes off.
function companionTravelEnd(buddy, anim) {
  if (nmb.anim !== anim) return;
  for (const t of nmb.travelTimers) clearTimeout(t);
  nmb.travelTimers = [];
  for (const fx of nmb.travelFx) fx.remove();
  nmb.travelFx = [];
  buddy.classList.remove("nmb-poofing");
  if (nmb.pose && buddy.dataset.pose !== nmb.pose) buddy.dataset.pose = nmb.pose;
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

//: Its legs walking from `ms` for `len` ms. Not a way out that sets off from a hang, nor `arrive`, a way in to one
//: (INBOX 1698: it came out under the top bar walking, hanging by its hands).
function companionTravelSteps(buddy, ms, len, arrive = false) {
  companionTravelAt(ms, () => {
    if (nmb.feetDown() && !(arrive && nmb.pose === "hang")) nameMarkBuddyBlend(buddy, () => buddy.classList.add("nmb-walking"), NMB_BLEND_IN_MS);
    nmbTempo.seen = 0;
    clearTimeout(nmbTempo.timer);
    nmbTempo.timer = setTimeout(nameMarkBuddyTempo, 0);
  });
  companionTravelAt(ms + len, () => nameMarkBuddyBlend(buddy, () => buddy.classList.remove("nmb-walking")));
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
    companionTravelSteps(buddy, T * 0.61, T * 0.29, true);
  },
  //: **Out through the edge and in through the edge** (INBOX 1692: "transformed sideways off the screen at the
  //: top and on the screen at the bottom, no real animation"). A hang lets go and drifts down first, still
  //: hanging until it does; it walks to the side eased in, squeezing narrow into the edge with wisps behind
  //: it, and comes in from the other side the mirror way: wisps, then widening, eased out.
  edge(buddy, dx, dy, ctx) {
    const W = innerWidth;
    const was = ctx.was;
    const outTo = was.x + NMB_W / 2 < W / 2 ? -(was.x + NMB_W + 8) : W - was.x + 8;
    const inFrom = nmb.x + NMB_W / 2 < W / 2 ? -(nmb.x + NMB_W + 8) : W - nmb.x + 8;
    const hung = ctx.poseWas === "hang" && buddy.dataset.pose !== "hang";
    const lead = hung ? 280 : 0;
    const t1 = Math.max(700, Math.abs(outTo) * COMPANION_TRAVEL_PACE);
    const t2 = Math.max(700, Math.abs(inFrom) * COMPANION_TRAVEL_PACE);
    const gap = 260;
    const T = lead + t1 + gap + t2;
    const at = (ms) => ms / T;
    const squeeze = 0.2;
    if (hung) buddy.dataset.pose = "hang";
    ctx.frames = [
      { translate: `${dx}px ${dy}px`, offset: 0 },
      { translate: `${dx}px ${dy + (hung ? 26 : 0)}px`, offset: at(lead), easing: "ease-in" },
      { translate: `${dx + outTo}px ${dy + (hung ? 26 : 0)}px`, offset: at(lead + t1) },
      { translate: `${inFrom}px 0px`, offset: at(lead + t1) + 0.001 },
      { translate: `${inFrom}px 0px`, offset: at(lead + t1 + gap), easing: "ease-out" },
      { translate: "0px 0px", offset: 1 },
    ];
    ctx.ms = T;
    const near = 0.8;
    const sq = { scale: `${squeeze} 1`, opacity: 0.2 };
    ctx.body = [
      { scale: "1 1", opacity: 1, offset: 0 },
      { scale: "1 1", opacity: 1, offset: at(lead + t1 * near), easing: "ease-in" },
      { ...sq, offset: at(lead + t1) },
      { ...sq, offset: at(lead + t1 + gap) },
      { scale: "1 1", opacity: 1, offset: at(lead + t1 + gap + t2 * 0.3), easing: "ease-out" },
      { scale: "1 1", opacity: 1, offset: 1 },
    ];
    ctx.turn = outTo < 0 ? "l" : "r";
    for (let i = 0; i < 3; i += 1) {
      const f = near + (i / 3) * (1 - near);
      companionTravelFx(buddy, "nmb-wisp", dx + outTo * f, dy, lead + t1 * f, 4, 520);
      companionTravelFx(buddy, "nmb-wisp", inFrom * (1 - i * 0.12), 0, lead + t1 + gap - 120 + i * 90, 4, 520);
    }
    companionTravelSteps(buddy, lead, t1);
    companionTravelSteps(buddy, lead + t1 + gap, t2, true);
    if (hung) companionTravelAt(lead, () => (buddy.dataset.pose = nmb.pose));
    companionTravelAt(lead + t1 + gap, () => (buddy.dataset.turn = inFrom < 0 ? "r" : "l"));
  },
  //: Sparkles over it, it spins small and is gone; sparkles there, it spins back. 1.1s.
  blink(buddy, dx, dy, ctx) {
    const T = 1100;
    const cut = 0.3;
    const pos = (x, y, extra = {}) => ({ translate: `${x}px ${y}px`, ...extra });
    ctx.frames = [
      pos(dx, dy, { opacity: 1, offset: 0 }),
      pos(dx, dy, { opacity: 0, offset: cut }),
      pos(0, 0, { opacity: 0, offset: cut + 0.001 }),
      pos(0, 0, { opacity: 0, offset: 0.5 }),
      pos(0, 0, { opacity: 1, offset: 0.78 }),
      pos(0, 0, { opacity: 1, offset: 1 }),
    ];
    ctx.ms = T;
    ctx.body = [
      { scale: "1", rotate: "0deg", offset: 0 },
      { scale: "0.1", rotate: "200deg", offset: cut, easing: "ease-in" },
      { scale: "0.1", rotate: "200deg", offset: 0.5 },
      { scale: "1", rotate: "360deg", offset: 0.8, easing: "ease-out" },
      { scale: "1", rotate: "360deg", offset: 1 },
    ];
    companionTravelFx(buddy, "nmb-spark", dx, dy, 0, 7, 700);
    companionTravelFx(buddy, "nmb-spark", 0, 0, T * 0.46, 7, 700);
  },
  //: A cloud forms under it, it steps on and is carried, bobbing, and steps off as it thins. 1.4 to 2.6s.
  cloud(buddy, dx, dy, ctx) {
    const T = Math.round(Math.min(2600, Math.max(1400, Math.hypot(dx, dy) * 2.4)));
    const pos = (x, y, extra = {}) => ({ translate: `${x}px ${y}px`, ...extra });
    ctx.frames = [pos(dx, dy, { offset: 0 }), pos(dx, dy, { offset: 0.2, easing: "ease-in-out" }), pos(0, 0, { offset: 0.85 }), pos(0, 0, { offset: 1 })];
    ctx.ms = T;
    ctx.body = [{ translate: "0px 0px", offset: 0 }, { translate: "0px -6px", offset: 0.2 }, { translate: "0px -2px", offset: 0.4 }, { translate: "0px -7px", offset: 0.6 }, { translate: "0px -2px", offset: 0.85 }, { translate: "0px 0px", offset: 1 }];
    const fx = companionTravelFx(buddy, "nmb-cloud", dx, dy, 0, 0, T + 50);
    fx?.animate([{ translate: "0px 0px", opacity: 0, offset: 0 }, { translate: "0px 0px", opacity: 1, offset: 0.14 }, { translate: "0px 0px", opacity: 1, offset: 0.2, easing: "ease-in-out" }, { translate: `${-dx}px ${-dy}px`, opacity: 1, offset: 0.85 }, { translate: `${-dx}px ${-dy}px`, opacity: 0, offset: 1 }], { duration: T, easing: "linear" });
    companionTravelFx(buddy, "nmb-wisp", 0, 0, T * 0.86, 4, 520);
  },
  //: It floats up in a bubble, drifts across on a shallow sway and the bubble pops over where it goes. 1.8 to 3.2s.
  bubble(buddy, dx, dy, ctx) {
    const T = Math.round(Math.min(3200, Math.max(1800, Math.hypot(dx, dy) * 3)));
    const steps = 6;
    const lift = 46;
    const pos = (u) => {
      const sway = Math.sin(u * Math.PI * 3) * 10 * (1 - u);
      return { translate: `${dx * (1 - u) + sway}px ${dy * (1 - u) - Math.sin(u * Math.PI) * lift}px`, offset: 0.16 + u * 0.7 };
    };
    ctx.frames = [{ translate: `${dx}px ${dy}px`, offset: 0 }, ...Array.from({ length: steps + 1 }, (_, i) => pos(i / steps)), { translate: "0px 0px", offset: 1 }];
    ctx.ms = T;
    const fx = companionTravelFx(buddy, "nmb-bubble", dx, dy, 0, 0, T + 50);
    const path = ctx.frames.slice(1, -1).map((f) => {
      const [x, y] = f.translate.split(" ").map(Number.parseFloat);
      return { translate: `${x - dx}px ${y - dy}px`, offset: f.offset };
    });
    fx?.animate([{ translate: "0px 0px", opacity: 0, scale: "0.3", offset: 0 }, { translate: "0px 0px", opacity: 1, scale: "1", offset: 0.16 }, ...path, { translate: `${-dx}px ${-dy}px`, opacity: 1, scale: "1", offset: 0.88 }, { translate: `${-dx}px ${-dy}px`, opacity: 0, scale: "1.35", offset: 0.95 }, { translate: `${-dx}px ${-dy}px`, opacity: 0, scale: "1.35", offset: 1 }], { duration: T, easing: "ease-in-out" });
    companionTravelFx(buddy, "nmb-wisp", 0, 0, T * 0.87, 5, 520);
  },
};

//: Play a far move; false when it should be walked (the chooser's "walk", or no player for it).
function companionTravelPlay(buddy, dx, dy, size, flies, was, force = "") {
  const o = { last: nmb.travelLast || "", dx, dy, size, flies, reduced: nameMarkBuddyNoTravel(), win: [innerWidth, innerHeight], x0: was.x, x1: nmb.x };
  const move = force || nmb.travelForce || companionTravelChoose(o, Math.random());
  nmb.travelLast = move;
  const player = COMPANION_TRAVEL_PLAYERS[move];
  if (!player) return false;
  const ctx = { was, frames: [], body: null, ms: 0, turn: "", poseWas: nmb.poseWas };
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

//: **The grab** (`trans.upright>hang`, 0.4 to 1.4 s): it came up from its feet in a leap (`nameMarkBuddyGo`) and
//: takes hold at the end of it: dropped a little under the bar by its own weight, hauled up taut, then a swing
//: that settles. `ms` is the leap's length; on the character's own `translate` and `rotate`, which add to the
//: landing squash's `scale` and the pose's transform. Nothing under Still motion.
nmb.leapGrab = function (buddy, char, ms) {
  if (!char || typeof char.animate !== "function" || nameMarkBuddyStill()) return;
  const dir = buddy.dataset.turn === "l" ? 1 : -1;
  nmb.grabAnim?.cancel();
  nmb.grabAnim = char.animate([
    { translate: "0px 0px", rotate: "0deg" },
    { translate: "0px 7px", rotate: "0deg", offset: 0.22 },
    { translate: "0px -3px", rotate: `${dir * 5}deg`, offset: 0.5 },
    { translate: "0px 1px", rotate: `${-dir * 3}deg`, offset: 0.78 },
    { translate: "0px 0px", rotate: "0deg" },
  ], { duration: 620, delay: Math.max(0, ms - 140), easing: "ease-out" });
};
