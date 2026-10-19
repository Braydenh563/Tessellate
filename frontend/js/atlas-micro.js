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
const atlasMicroState = { timer: 0, last: "", sinceMood: 9 };
const ATLAS_MICRO_BASE = {
  glance: 4, tilt: 2.2, shift: 2.5, ear: 1.5, blink: 2,
  curious: 0.9, focus: 0.4, pleased: 0.7, sleepy: 0.2, surprised: 0.15,
};
const ATLAS_MICRO_MOOD = { curious: "curious", focus: "determined", pleased: "happy", sleepy: "sleepy", surprised: "surprised" };
function atlasMicroGap() {
  //: Skewed short: a quarter of the gaps are over six seconds.
  return 1200 + Math.random() ** 1.7 * 9800;
}
function atlasMicroPick(c, last = "") {
  const w = { ...ATLAS_MICRO_BASE };
  const night = c.hour >= 22 || c.hour < 6;
  if (c.typing) Object.assign(w, { glance: w.glance * 0.4, tilt: w.tilt * 0.5, curious: w.curious * 0.5, focus: w.focus * 6, sleepy: w.sleepy * 0.1, surprised: 0 });
  if (c.idle > 60000) Object.assign(w, { sleepy: w.sleepy * 4, shift: w.shift * 1.5, glance: w.glance * 0.6, focus: 0 });
  if (night) w.sleepy *= 5;
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
function atlasMicroMay(box) {
  const buddy = box.closest("#nm-buddy");
  if (!box.isConnected || !buddy || document.hidden || document.documentElement.hasAttribute("data-atlas-hidden") || !atlasMotionOK(box)) return false;
  if (box.classList.contains("atl-off") || nameMarkBuddyMenuOpen() || /^(lie|curl)/.test(buddy.dataset.pose || "")) return false;
  for (const c of buddy.classList) if (c.startsWith("nmb-act-") || c === "nmb-sleep" || c === "nmb-walking" || c === "nm-buddy-dragging") return false;
  return true;
}
//: Plays `frames` on `el`, added to whatever else moves that property.
function atlasMicroPlay(el, frames, ms) {
  el?.animate?.(frames, { duration: ms, easing: "ease-in-out", composite: "add" });
}
function atlasMicroGlance(box) {
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
}
function atlasMicroDo(kind, box) {
  const sign = Math.random() < 0.5 ? -1 : 1;
  if (kind === "glance") return atlasMicroGlance(box);
  if (kind === "tilt") {
    const d = sign * (1.8 + Math.random() * 2.4);
    const ms = 1700 + Math.random() * 1900;
    (box.atlasRig?.heads || []).forEach((head, k) => {
      const a = `${(d * (k ? 1.3 : 1)).toFixed(2)}deg`;
      atlasMicroPlay(head, [{ rotate: "0deg" }, { rotate: a, offset: 0.3 }, { rotate: a, offset: 0.72 }, { rotate: "0deg" }], ms);
    });
    return;
  }
  if (kind === "shift") {
    const dx = sign * (0.5 + Math.random() * 0.6);
    const a = { translate: `${dx.toFixed(2)}px 0px`, rotate: `${(dx * 0.7).toFixed(2)}deg` };
    atlasMicroPlay(box.querySelector(".atl-lw-body"), [{ translate: "0px 0px", rotate: "0deg" }, { ...a, offset: 0.4 }, { ...a, offset: 0.65 }, { translate: "0px 0px", rotate: "0deg" }], 2000 + Math.random() * 1400);
    return;
  }
  if (kind === "ear") {
    const ears = [...box.querySelectorAll(".atl-ear")];
    const ear = ears[Math.floor(Math.random() * ears.length)];
    if (!ear) return;
    ear.style.transformBox = "fill-box";
    ear.style.transformOrigin = "50% 90%";
    const a = `${(sign * (3.5 + Math.random() * 2)).toFixed(1)}deg`;
    const ms = 220 + Math.random() * 160;
    atlasMicroPlay(ear, [{ rotate: "0deg" }, { rotate: a, offset: 0.35 }, { rotate: "0deg" }], ms);
    if (Math.random() < 0.3) setTimeout(() => atlasMicroPlay(ear, [{ rotate: "0deg" }, { rotate: a, offset: 0.35 }, { rotate: "0deg" }], ms), ms + 90);
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
  const kind = atlasMicroPick({ typing: now - (nmb.keyAt || 0) < 5000, idle: now - (nmb.lastInput || 0), hour: new Date().getHours(), mood: atlasMoodNow }, atlasMicroState.last);
  atlasMicroState.last = kind;
  atlasMicroDo(kind, box);
}
function atlasMicroStart() {
  if (!atlasMicroState.timer) atlasMicroState.timer = setTimeout(atlasMicroTick, 2500 + Math.random() * 2500);
}
