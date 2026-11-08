// Runs the pull-grab block of frontend/js/avatars.js (INBOX 1696 bb) against a fake document,
// for tests/test_pull_grab_1696.py. Prints one JSON object per scenario.
//
//   node tests/_pull_grab_harness.js
//
// The fake page: the companion's drawing is the two rects below (a body and a pair of legs that
// reaches past the handle); the handle is not in play here (a press on it targets the buddy).
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const src = fs.readFileSync(path.resolve(__dirname, "..", "frontend", "js", "avatars.js"), "utf8");
const block = src.slice(src.indexOf("// pull-grab:begin"), src.indexOf("// pull-grab:end"));
if (!block) throw new Error("pull-grab block missing");

const DRAWN = [
  { left: 640, top: 420, right: 704, bottom: 512 },
  { left: 624, top: 500, right: 718, bottom: 560 },
];

function world() {
  const handlers = {};
  const log = { faceDown: [], selection: 0, prevented: [], stopped: 0 };
  const face = { dispatchEvent: (e) => { if (e.type === "pointerdown") log.faceDown.push([e.clientX, e.clientY, e.pointerId]); } };
  const buddy = {
    querySelector: (s) => (s === ".nm-buddy-face" ? face : null),
    querySelectorAll: () => DRAWN.map((r) => ({ getBoundingClientRect: () => r })),
  };
  const document = {
    getElementById: (id) => (id === "nm-buddy" ? buddy : null),
    addEventListener: (type, fn) => { (handlers[type] ||= []).push(fn); },
  };
  class PointerEvent { constructor(type, init) { this.type = type; Object.assign(this, init); } }
  const ctx = { document, PointerEvent, Math, getSelection: () => ({ removeAllRanges: () => { log.selection += 1; } }) };
  vm.runInNewContext(block, ctx);
  const fire = (type, init = {}) => {
    const ev = { type, button: 0, pointerId: 1, clientX: 0, clientY: 0, target: { closest: () => null }, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { log.stopped += 1; }, ...init };
    for (const fn of handlers[type] || []) fn(ev);
    return ev;
  };
  return { fire, log };
}

const out = {};
const pull = (x, y, dy = 30, init = {}) => {
  const w = world();
  w.fire("pointerdown", { clientX: x, clientY: y, ...init });
  w.fire("pointermove", { clientX: x + 1, clientY: y + dy });
  const sel = w.fire("selectstart");
  const click = w.fire("click");
  return { w, grabbed: w.log.faceDown.length === 1, selectionBlocked: sel.defaultPrevented, clickSwallowed: click.defaultPrevented };
};

// Every sampled point on either drawn rect: a pull is a grab, the selection never starts.
let points = 0, grabs = 0, blocked = 0;
for (const r of DRAWN) for (let x = r.left + 2; x < r.right; x += 9) for (let y = r.top + 2; y < r.bottom; y += 9) {
  const p = pull(x, y);
  points += 1; grabs += p.grabbed ? 1 : 0; blocked += p.selectionBlocked && p.clickSwallowed ? 1 : 0;
}
out.regions = { points, grabs, blocked };

// The press is handed on at the pressed point, with the pointer's own id.
const one = pull(660, 530);
out.handed = one.w.log.faceDown[0];
out.clearedSelection = one.w.log.selection;

// A plain click: no grab, the selection is the page's, the click goes through.
const w2 = world();
w2.fire("pointerdown", { clientX: 660, clientY: 530 });
w2.fire("pointerup", { clientX: 660, clientY: 530 });
const sel2 = w2.fire("selectstart");
const click2 = w2.fire("click");
out.click = { grabbed: w2.log.faceDown.length, selectionBlocked: sel2.defaultPrevented, clickSwallowed: click2.defaultPrevented };

// A wobble under 4px: no grab.
const w3 = world();
w3.fire("pointerdown", { clientX: 660, clientY: 530 });
w3.fire("pointermove", { clientX: 662, clientY: 532 });
out.wobble = w3.log.faceDown.length;

// Off the drawing, on the companion itself, or another button: the page's.
out.outside = pull(300, 300).grabbed;
out.onBuddy = pull(660, 530, 30, { target: { closest: (s) => (s === "#nm-buddy" ? {} : null) } }).grabbed;
out.rightButton = pull(660, 530, 30, { button: 2 }).grabbed;
// Another pointer moving does not take the press.
const w4 = world();
w4.fire("pointerdown", { clientX: 660, clientY: 530 });
w4.fire("pointermove", { pointerId: 2, clientX: 700, clientY: 600 });
out.otherPointer = w4.log.faceDown.length;

console.log(JSON.stringify(out));
