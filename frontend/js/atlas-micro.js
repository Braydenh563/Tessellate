// atlas-micro.js: Atlas's small behaviours (INBOX 1322b, the owner,
// 2026-10-19: "atlas needs to have its animations and expressions improved
// behaviours, even micro behaviours and movements, small movement
// adjustments, more variety"). Lazy, in the rig's bundle
// (`LAZY_MODULES.atlasMotion`); started by the blink clock
// (`atlasBlinkStart`), so it exists only while a layered figure does.
//
//: **One randomised clock.** Every 1.2 to 11 seconds (mostly 2 to 6, now and
//: then a long stare) the companion does one small thing, chosen by weight
//: from the moment (typing, away a while, the hour, its mood) and never the
//: same as the last: a glance (at the pointer, the field being typed in, or
//: just elsewhere), a head tilt, a shift of weight, an ear flick, a blink
//: that is slow or doubled, or a short passing expression (curious,
//: focused, pleased, drowsy, startled). Each move is a few degrees or a
//: pixel, played as a Web Animation that adds to the loops already running
//: (breath, sway, hair), so it costs the compositor, not a frame loop here.
//: It holds still under reduced motion (`atlasMotionOK`), on a hidden tab
//: and while anything else has the companion: asleep, carried, walking,
//: lying down, in an act, or a menu open. An expression only borrows a calm
//: face; it never replaces a mood something else set.
//:
//: **The feminine look casts stars** (INBOX 1576, the owner: stars "permanently
//: stuck to the end of the feminine atlas ... should instead become a movement
//: or animation or behaviour (the stars in its left hand)"). She wears none at
//: rest; a cast (`atlasMicroCast`) is the one beat only she has, now and then
//: when calm and after a wave, a cheer or the greeting: four small glints rise
//: from her left hand, each fading in over about a second and out again,
//: `transform` and `opacity` only, then they are taken off the figure.
//:
//: **Rare habits, and the part of the day** (INBOX 1581, the owner: "more
//: behaviour and npc improvements"). Four moves come seldom, each at most
//: once in three minutes (`atlasMicroPick.rareMs`): a look around (one side,
//: then the other), a hum (three small nods of the head), a settling breath
//: (the body sinks a pixel and comes up) and a double take at the pointer.
//: Settings, Companion, What it does, "Little habits and reactions" turns them
//: off. The weights lean with the part of the day (`atlasDriftState.phase`):
//: more glances in the morning, more focus in the afternoon, slower blinks
//: and drowsier faces in the evening and at night.
const atlasMicroState = { timer: 0, last: "", sinceMood: 9, castAt: 0, rareAt: {} };
const ATLAS_MICRO_BASE = {
  glance: 4, tilt: 2.2, shift: 2.5, ear: 1.5, blink: 2,
  curious: 0.9, focus: 0.4, pleased: 0.7, sleepy: 0.2, surprised: 0.15, cast: 1.1,
  around: 0.35, hum: 0.3, settle: 0.4, double: 0.3,
};

const ATLAS_MICRO_MOOD = { curious: "curious", focus: "determined", pleased: "happy", sleepy: "sleepy", surprised: "surprised" };
function atlasMicroGap() {
  //: Skewed short: a quarter of the gaps are over six seconds.
  return 1200 + Math.random() ** 1.7 * 9800;
}
function atlasMicroPick(c, last = "") {
  const w = { ...ATLAS_MICRO_BASE };
  const night = c.hour >= 22 || c.hour < 6;
  if (c.typing) Object.assign(w, { glance: w.glance * 0.4, tilt: w.tilt * 0.5, curious: w.curious * 0.5, focus: w.focus * 6, sleepy: w.sleepy * 0.1, surprised: 0, around: 0, hum: 0, double: 0 });
  if (c.idle > 60000) Object.assign(w, { sleepy: w.sleepy * 4, shift: w.shift * 1.5, glance: w.glance * 0.6, focus: 0 });
  if (night) w.sleepy *= 5;
  for (const [k, f] of Object.entries(atlasMicroPick.phase[c.phase] || {})) w[k] *= f;
  //: The rare ones: switched off, too soon after the last of their kind, a double take with no pointer.
  for (const k of atlasMicroPick.rare) if (c.rareOff || (c.now || 0) - (c.rareAt?.[k] ?? -Infinity) < atlasMicroPick.rareMs) w[k] = 0;
  if (!c.pointer) w.double = 0;
  //: Hers alone, and a pause (30 s) between two casts, a gesture's included.
  if (c.look !== "feminine" || c.sinceCast < 30000) w.cast = 0;
  if (c.typing) w.cast *= 0.3;
  if (c.mood && c.mood !== "calm") for (const k of Object.keys(ATLAS_MICRO_MOOD)) w[k] = 0;
  let total = 0;
  for (const k of Object.keys(w)) {
    if (k === last) w[k] = 0;
    total += w[k];
  }
  let r = Math.random() * total;
  for (const [k, v] of Object.entries(w)) {
    r -= v;
    if (v > 0 && r <= 0) return k;
  }
  return "shift";
}
//: The rare ones, their pause, and the part of the day's lean: function
//: properties, not globals (the shared scope's cap, `tests/test_global_scope_ratchet.py`).
atlasMicroPick.rare = ["around", "hum", "settle", "double"];
atlasMicroPick.rareMs = 180000;
atlasMicroPick.phase = {
  morning: { glance: 1.3, shift: 1.2, curious: 1.3, sleepy: 0.3, around: 1.4 },
  afternoon: { focus: 1.5, tilt: 1.2, hum: 1.3 },
  evening: { blink: 1.3, sleepy: 2, glance: 0.85, settle: 1.5 },
  night: { blink: 1.4, settle: 1.6, around: 0.5, hum: 0.4 },
};
function atlasMicroMay(box) {
  const buddy = box.closest("#nm-buddy");
  if (!box.isConnected || !buddy || document.hidden || document.documentElement.hasAttribute("data-atlas-hidden") || !atlasMotionOK(box)) return false;
  if (box.classList.contains("atl-off") || nameMarkBuddyMenuOpen() || /^(lie|curl)/.test(buddy.dataset.pose || "")) return false;
  for (const c of buddy.classList) if (c.startsWith("nmb-act-") || c === "nmb-sleep" || c === "nmb-walking" || c === "nm-buddy-dragging") return false;
  //: Not at rest (owner decision Q10): a glance or a tilt on an SVG head is ten to thirty layouts, and two seconds from
  //: the last input the drawn loops stop (`atlasTailCalm.rest`, atlas-life.js); the clock goes on, the next input ends the rest.
  if (globalThis.atlasTailCalm?.rest.on) return false;
  return true;
}
//: Plays `frames` on `el`, in place of whatever else moves that property
//: (never added to it: `composite: "add"` is not the compositor's).
function atlasMicroPlay(el, frames, ms) {
  el?.animate?.(frames, { duration: ms, easing: "ease-in-out" });
}
//: A function property, not a global: the shared scope has a cap on names (`tests/test_global_scope_ratchet.py`).
atlasMicroDo.glance = function (box) {
  const field = document.activeElement;
  const fr = field && field !== document.body ? field.getBoundingClientRect?.() : null;
  const r = Math.random();
  let point;
  if (fr && fr.width && r < 0.4) point = [fr.left + fr.width / 2, fr.top + Math.min(fr.height / 2, 80)];
  else if (nmb.pointer && r < 0.8) point = nmb.pointer;
  else point = [Math.random() * innerWidth, Math.random() * innerHeight];
  nameMarkBuddyAim(point);
  setTimeout(() => {
    //: Back to the pointer if it moved lately, else to looking ahead.
    nameMarkBuddyAim(nmb.pointer && Date.now() - (nmb.lastInput || 0) < 4000 ? nmb.pointer : null);
    if (Math.random() < 0.35 && atlasMicroMay(box)) atlasBlink(box);
  }, 700 + Math.random() * 1300);
};
//: A cast from her left hand (on screen the right one, the arm drawn `r`, which
//: wore the seeds): `only` is one figure's box, none is every figure on the
//: page (the corner's and the large view's). Returns whether a cast began.
//: Each star is a glint drawn in the hand's own group, so it rides with the
//: hand; it is invisible (the CSS) until its animation plays, and is removed
//: when that ends, so nothing of it is left at rest.
//: **The stars are that arm's own state** (INBOX 1589, the owner: the star
//: hand "still has starts permanently coming from it", and a cheer "spawns a
//: 3rd arm"): no cast while the companion is in an act that has the arms (a
//: wave, a cheer, a book: any but the small ones that leave them be), and an
//: act that starts stops a cast under way (`atlasMicroCast.stop`). A wave or
//: a cheer casts as it ends, from the hand come back to her side.
function atlasMicroCast(only) {
  if (document.hidden) return false;
  if (nmb.act && !NMB_FACELESS_ACTS.includes(nmb.act) && document.getElementById("nm-buddy")) return false;
  let cast = false;
  for (const box of only ? [only] : document.querySelectorAll(".atl-figure-box")) {
    const arm = box.atlasRig?.arms?.find((a) => a.side === "r");
    const wrist = arm?.geo?.segs?.[1];
    if (box.dataset.atlasLook !== "feminine" || !arm?.hand || !wrist || box.atlasCasting || !box.isConnected || box.classList.contains("atl-off") || !atlasMotionOK(box)) continue;
    cast = true;
    box.atlasCasting = true;
    box.atlasCastAnims = [];
    atlasMicroState.castAt = Date.now();
    //: Outward from the body, and up.
    const out = Math.sign(wrist[6] - 32) || 1;
    let live = 0;
    for (const [i, size] of [2.4, 1.7, 2.1, 1.4].entries()) {
      const star = atlasSpark(arm.hand, wrist[6], wrist[7], size, "atl-cast-star");
      const dx = out * (2.4 + i * 1.8 + Math.random() * 1.4);
      const dy = -(4 + i * 2.2 + Math.random() * 2);
      const at = (k, scale) => `translate(${(dx * k).toFixed(2)}px, ${(dy * k).toFixed(2)}px) scale(${scale})`;
      const ms = 2300 + Math.random() * 400;
      //: Up by 42% of its time (about a second), held, then away.
      const frames = [
        { transform: at(0, 0.2), opacity: 0 },
        { transform: at(0.55, 1), opacity: 1, offset: 0.42 },
        { transform: at(0.8, 0.9), opacity: 1, offset: 0.7 },
        { transform: at(1, 0.5), opacity: 0 },
      ];
      live += 1;
      const done = () => {
        star.remove();
        live -= 1;
        if (!live) box.atlasCasting = false;
      };
      const anim = star.animate?.(frames, { duration: ms, delay: i * 260, easing: "ease-out", fill: "backwards" });
      if (anim?.finished) {
        box.atlasCastAnims.push(anim);
        anim.finished.then(done, done);
      } else done();
    }
  }
  return cast;
}
//: An act that takes the arms stops a cast under way: each star's animation is
//: cancelled, and a cancelled one is removed (its `finished` rejects). The
//: cast's own list, not a scan of the page's animations.
atlasMicroCast.stop = function () {
  for (const box of document.querySelectorAll(".atl-figure-box")) for (const anim of box.atlasCastAnims || []) anim.cancel();
};
//: The rare habits: the head's `transform` and the body's `translate`, as
//: the tilt and the shift play them, and the look as a glance aims it.
atlasMicroDo.rare = function (kind, box, sign) {
  atlasMicroState.rareAt[kind] = Date.now();
  const back = () => atlasMicroMay(box) && nameMarkBuddyAim(nmb.pointer && Date.now() - (nmb.lastInput || 0) < 4000 ? nmb.pointer : null);
  if (kind === "around") {
    const y = innerHeight * (0.35 + Math.random() * 0.2);
    const side = (k) => [k < 0 ? innerWidth * 0.08 : innerWidth * 0.92, y];
    nameMarkBuddyAim(side(sign));
    setTimeout(() => atlasMicroMay(box) && nameMarkBuddyAim(side(-sign)), 900 + Math.random() * 300);
    setTimeout(back, 2000 + Math.random() * 400);
  } else if (kind === "double") {
    const p = nmb.pointer;
    nameMarkBuddyAim(p);
    setTimeout(() => atlasMicroMay(box) && nameMarkBuddyAim(null), 420);
    setTimeout(() => {
      if (!atlasMicroMay(box)) return;
      nameMarkBuddyAim(p);
      atlasBlink(box);
    }, 760);
    setTimeout(back, 2200);
  } else if (kind === "hum") {
    const nod = (deg) => ({ transform: `rotate(${(sign * deg).toFixed(2)}deg)` });
    const frames = [nod(0), { ...nod(1.4), offset: 0.17 }, { ...nod(-0.6), offset: 0.33 }, { ...nod(1.2), offset: 0.5 }, { ...nod(-0.5), offset: 0.67 }, { ...nod(1), offset: 0.83 }, nod(0)];
    for (const head of box.atlasRig?.heads || []) atlasMicroPlay(head, frames, 1800 + Math.random() * 400);
  } else {
    const sink = (y) => ({ translate: `0px ${y}px` });
    atlasMicroPlay(box.querySelector(".atl-lw-body"), [sink(0), { ...sink(0.9), offset: 0.45 }, { ...sink(0.9), offset: 0.6 }, sink(0)], 2200 + Math.random() * 600);
  }
};
//: The breath let out after a startle: the shoulders sink two pixels over about a second and a half and come
//: back, deeper than the rare settle and not rationed by it; skipped if the figure has begun something else.
atlasMicroDo.exhale = function (box) {
  if (!box || !atlasMicroMay(box)) return;
  const sink = (y) => ({ translate: `0px ${y}px` });
  atlasMicroPlay(box.querySelector(".atl-lw-body"), [sink(0), { ...sink(2), offset: 0.4 }, { ...sink(2), offset: 0.55 }, sink(0)], 1500);
};
function atlasMicroDo(kind, box) {
  const sign = Math.random() < 0.5 ? -1 : 1;
  if (kind === "glance") return atlasMicroDo.glance(box);
  if (atlasMicroPick.rare.includes(kind)) return atlasMicroDo.rare(kind, box, sign);
  if (kind === "cast") return atlasMicroCast(box);
  if (kind === "tilt") {
    const d = sign * (1.8 + Math.random() * 2.4);
    const ms = 1700 + Math.random() * 1900;
    (box.atlasRig?.heads || []).forEach((head, k) => {
      //: The head's own `rotate` is the rig's (written every wake), and an
      //: svg part's individual `rotate` is the main thread's whatever the
      //: composite; `transform` on it is the compositor's, and the head has
      //: none of its own, so the tilt replaces it (audit 1031 row 17).
      const a = `rotate(${(d * (k ? 1.3 : 1)).toFixed(2)}deg)`;
      atlasMicroPlay(head, [{ transform: "none" }, { transform: a, offset: 0.3 }, { transform: a, offset: 0.72 }, { transform: "none" }], ms);
    });
    return;
  }
  if (kind === "shift") {
    const dx = sign * (0.5 + Math.random() * 0.6);
    //: **A shift moves only `translate`, and replaces** (audit 1031 row 17):
    //: the body's sway loop owns `rotate`, and a Web Animation that adds to
    //: it (`composite: "add"`) or shares its property cannot be composited,
    //: so every shift put the whole figure's loops back on the main thread
    //: for its two to three seconds (60 style recalcs a second, measured).
    //: The body has no translate of its own, so a replacing one needs no add.
    const a = { translate: `${dx.toFixed(2)}px 0px` };
    atlasMicroPlay(box.querySelector(".atl-lw-body"), [{ translate: "0px 0px" }, { ...a, offset: 0.4 }, { ...a, offset: 0.65 }, { translate: "0px 0px" }], 2000 + Math.random() * 1400);
    return;
  }
  if (kind === "ear") {
    const ears = [...box.querySelectorAll(".atl-ear")];
    const ear = ears[Math.floor(Math.random() * ears.length)];
    if (!ear) return;
    ear.style.transformBox = "fill-box";
    ear.style.transformOrigin = "50% 90%";
    //: **The flick replaces the crest's `transform`** (audit 1101, row 17's
    //: leftover): it added an individual `rotate` over it (`composite: "add"`),
    //: which is the main thread's, so each flick put the figure's loops back
    //: there for its third of a second. The ear's own turn (`--atl-crest`,
    //: mirrored on the left ear: characters-lazy.css) is written into the
    //: keyframes, so the ear tips from where the mood holds it and back.
    const turn = (deg) => ({ transform: `rotate(calc(var(--atl-crest) * ${ear.classList.contains("atl-ear-l") ? -1 : 1} + ${deg}deg))` });
    const a = Number((sign * (3.5 + Math.random() * 2)).toFixed(1));
    const ms = 220 + Math.random() * 160;
    const frames = [turn(0), { ...turn(a), offset: 0.35 }, turn(0)];
    atlasMicroPlay(ear, frames, ms);
    if (Math.random() < 0.3) setTimeout(() => atlasMicroPlay(ear, frames, ms), ms + 90);
    return;
  }
  if (kind === "blink") {
    const slow = Math.random() < 0.25;
    atlasBlink(box, slow);
    if (!slow && Math.random() < 0.4) setTimeout(() => atlasMicroMay(box) && atlasBlink(box), 340);
    return;
  }
  //: A passing expression, only over a calm face, and not twice in a row
  //: of ticks: it lasts 1.4 to 3.4 seconds and eases back.
  if (atlasMoodNow !== "calm" || atlasMicroState.sinceMood < 3 || Date.now() - atlasDriftState.changedAt < 8000) return;
  atlasMicroState.sinceMood = 0;
  setAtlasMood(ATLAS_MICRO_MOOD[kind], kind === "surprised" ? 1400 : 1800 + Math.random() * 1600, { quiet: true, backEaseMs: 900 });
}
function atlasMicroTick() {
  atlasMicroState.timer = 0;
  const box = document.querySelector("#nm-buddy .atl-figure-box");
  if (!box) return;
  atlasMicroState.timer = setTimeout(atlasMicroTick, atlasMicroGap());
  atlasMicroState.sinceMood += 1;
  if (!atlasMicroMay(box)) return;
  const now = Date.now();
  const hour = new Date().getHours();
  const kind = atlasMicroPick({
    typing: now - (nmb.keyAt || 0) < 5000, idle: now - (nmb.lastInput || 0), hour, phase: atlasDriftState.phase?.(hour), mood: atlasMoodNow, look: box.dataset.atlasLook,
    sinceCast: now - atlasMicroState.castAt, now, rareAt: atlasMicroState.rareAt, rareOff: nameMarkBuddyActOff("habits") || document.documentElement.dataset.motion === "reduced", pointer: !!nmb.pointer,
  }, atlasMicroState.last);
  atlasMicroState.last = kind;
  //: **On a page a frame has drawn** (INBOX 1667: `atlas-micro.js:272` 118ms of forced layout at 4x; a glance
  //: reads the focused field's box, a blink the mood's, a cast the hand's): the tick's timer lands between
  //: the page's writes and its frame. Still allowed a frame on, or it is dropped.
  nmb.afterClean(() => atlasMicroMay(box) && atlasMicroDo(kind, box));
}
function atlasMicroStart() {
  if (!atlasMicroState.timer) atlasMicroState.timer = setTimeout(atlasMicroTick, 2500 + Math.random() * 2500);
}
