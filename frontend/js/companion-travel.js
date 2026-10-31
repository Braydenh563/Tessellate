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
//:   fade    Reduce motion: a crossfade, and nothing else
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
const COMPANION_TRAVEL_MOVES = ["walk", "portal", "smoke", "edge"];
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
  const w = { walk: d <= s * 8 ? 3 : 0.6, portal: d > s * 2.5 ? 3 : 0, smoke: d > s * 2 ? 3 : 0, edge: 0 };
  const out = Math.min(o.x0, width - s - o.x0);
  const into = Math.min(o.x1, width - s - o.x1);
  if (d > s * 3 && out + into + s * 2 <= s * COMPANION_TRAVEL_EDGE_SIZES) w.edge = 2;
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

function companionTravelAt(ms, fn) {
  nmb.travelTimers.push(setTimeout(fn, ms));
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
  //: Off the side of the window nearest where it was, in from the side nearest where it goes.
  edge(buddy, dx, dy, ctx) {
    const W = innerWidth;
    const was = ctx.was;
    const outTo = was.x + NMB_W / 2 < W / 2 ? -(was.x + NMB_W + 8) : W - was.x + 8;
    const inFrom = nmb.x + NMB_W / 2 < W / 2 ? -(nmb.x + NMB_W + 8) : W - nmb.x + 8;
    const t1 = Math.max(500, Math.abs(outTo) * COMPANION_TRAVEL_PACE);
    const t2 = Math.max(500, Math.abs(inFrom) * COMPANION_TRAVEL_PACE);
    const gap = 260;
    const T = t1 + gap + t2;
    const a = t1 / T;
    ctx.frames = [
      { translate: `${dx}px ${dy}px`, offset: 0 },
      { translate: `${dx + outTo}px ${dy}px`, offset: a },
      { translate: `${inFrom}px 0px`, offset: a + 0.001 },
      { translate: `${inFrom}px 0px`, offset: (t1 + gap) / T },
      { translate: "0px 0px", offset: 1 },
    ];
    ctx.ms = T;
    ctx.turn = outTo < 0 ? "l" : "r";
    companionTravelSteps(buddy, 0, t1);
    companionTravelSteps(buddy, t1 + gap, t2);
    companionTravelAt(t1 + gap, () => (buddy.dataset.turn = inFrom < 0 ? "r" : "l"));
  },
};

//: Play a far move; false when it should be walked (the chooser's "walk", or no player for it).
function companionTravelPlay(buddy, dx, dy, size, flies, was) {
  const o = { last: nmb.travelLast || "", dx, dy, size, flies, reduced: nameMarkBuddyNoTravel(), win: [innerWidth, innerHeight], x0: was.x, x1: nmb.x };
  const move = nmb.travelForce || companionTravelChoose(o, Math.random());
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
