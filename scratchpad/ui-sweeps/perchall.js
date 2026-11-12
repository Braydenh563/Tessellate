// INBOX 521, the owner: "the companion perching needs fixing for many of the
// library tabs as well as for the whiteboard and mindmap" (a screenshot: on
// Library, Files, it stood ~30px under the card's bottom edge, on nothing).
//
// Visits every tab, every Library sub-tab, an open whiteboard and an open
// mind map, and on each measures, from the drawn box (not `nmb`):
//   gap   the px between the line it touches its perch on (soles, seat or
//         hands, `nameMarkBuddyOrigin`) and the edge of the surface it says
//         it is on (top edge, or underside when hanging);
//   paint whether a painted surface actually starts within 4px of that line
//         under its middle (elementsFromPoint, not the claim);
//   over  any visible control (button, input, tab, link) its shape covers.
// Then it switches sub-tab, resizes and grows content, measuring at 900ms
// and again after its beat (the re-perch).
// Env: KIND (atlas), W (1440), H (900), WAIT (2600), ONLY (comma list of
// labels), PANEL_OPTIONAL (a window bar passes on the Library and boards).
// Needs a seeded notebook with a board (whiteboard) and a map. Exits
// 1 on any surface whose gap is over 4px, with no painted edge, or over a
// control (on a phone, a dock's, a bar's or a floating one, marked `!`), or,
// on a desktop, on a window bar in the Library or on a board while a panel
// was free.
const { boot } = require("./lib.js");

const W = Number(process.env.W || 1440);
const H = Number(process.env.H || 900);
const WAIT = Number(process.env.WAIT || 2600);
const phone = W < 600;

// Still for 400ms (no walk, glide or entrance under way), or 6s have passed:
// a figure measured mid-walk is between perches, not off one.
async function settle(page) {
  await page.evaluate(async () => {
    const buddy = document.getElementById("nm-buddy");
    const at = () => { const b = buddy?.getBoundingClientRect(); return b ? `${Math.round(b.left)},${Math.round(b.top)},${buddy.dataset.pose}` : ""; };
    const t0 = performance.now();
    let last = at();
    let still = 0;
    while (performance.now() - t0 < 6000 && still < 4) {
      await new Promise((r) => setTimeout(r, 100));
      const now = at();
      const busy = buddy?.getAnimations({ subtree: true }).some((a) => a.playState === "running" && a.effect?.getComputedTiming?.().iterations !== Infinity && !(a instanceof CSSAnimation));
      still = now === last && !busy ? still + 1 : 0;
      last = now;
    }
  });
}

async function measure(page) {
  await settle(page);
  return page.evaluate(() => {
    const buddy = document.getElementById("nm-buddy");
    if (!buddy || buddy.classList.contains("hidden")) return { err: "no companion" };
    const b = buddy.getBoundingClientRect();
    const pose = buddy.dataset.pose || nmb.pose;
    const legs = buddy.dataset.legs || nmb.legs || "";
    const [cx, line] = nmb.inner.nameMarkBuddyOrigin(b.left, b.top, pose);
    const name = (el) => (el ? `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${el.classList.length ? `.${[...el.classList].slice(0, 2).join(".")}` : ""}` : "-");
    const glue = nmb.glue?.el;
    let claim = null;
    let gap = null;
    if (pose === "float") {
      gap = Infinity;
    } else if (glue && glue.isConnected) {
      claim = glue;
      const r = glue.getBoundingClientRect();
      gap = pose === "hang" ? line - r.bottom : r.top - line;
    } else {
      const top = document.getElementById("top-bar").getBoundingClientRect();
      const dock = document.getElementById("phone-tab-dock");
      const sb = dock && dock.getBoundingClientRect().height ? dock : document.getElementById("status-bar");
      const bot = sb.getBoundingClientRect();
      claim = pose === "hang" ? document.getElementById("top-bar") : sb;
      gap = pose === "hang" ? line - top.bottom : bot.top - line;
    }
    // What is really there: under its middle and a third in from each side,
    // the first painted box whose own top (or bottom, hanging) is near the line.
    const painted = (el) => {
      const cs = getComputedStyle(el);
      return cs.backgroundColor !== "rgba(0, 0, 0, 0)" || cs.borderTopWidth !== "0px" || cs.borderBottomWidth !== "0px" || cs.boxShadow !== "none" || el.matches("button, canvas, svg");
    };
    let paint = null;
    const probeY = pose === "hang" ? line - 3 : line + 3;
    for (const fx of [0, -14, 14]) {
      const px = cx + fx;
      if (px < 0 || px >= innerWidth || probeY < 0 || probeY >= innerHeight) continue;
      for (const el of document.elementsFromPoint(px, probeY)) {
        if (el.closest("#nm-buddy, #nm-buddy-band") || el === document.body || el === document.documentElement) continue;
        const r = el.getBoundingClientRect();
        const edge = pose === "hang" ? r.bottom : r.top;
        if (Math.abs(edge - line) <= 4 && painted(el)) {
          paint = name(el);
          break;
        }
      }
      if (paint) break;
    }
    const shape = nmb.inner.nameMarkBuddyShape(b.left, b.top, pose, legs);
    const over = [];
    const sel = "button, a[href], input:not([type='hidden']), select, textarea, [role='tab'], [role='button']";
    for (const el of document.querySelectorAll(sel)) {
      if (el.closest("#nm-buddy")) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))) continue;
      // Hit-test, not just overlap: a control under the figure but itself
      // covered (another layer) is not reachable anyway.
      for (const p of shape) {
        const w = Math.min(p.right, r.right) - Math.max(p.left, r.left);
        const h = Math.min(p.bottom, r.bottom) - Math.max(p.top, r.top);
        if (w > 2 && h > 2) {
          const hx = Math.max(p.left, r.left) + w / 2;
          const hy = Math.max(p.top, r.top) + h / 2;
          const top = document.elementsFromPoint(hx, hy).find((n) => !n.closest("#nm-buddy, #nm-buddy-band"));
          if (top && (top === el || el.contains(top))) {
            // A dock's, a bar's or a floating control (`!`), or one in the
            // page's content, which scrolls out from under it.
            over.push(`${el.closest(".dock, [role='toolbar'], [role='tablist'], .chat-dock, .wb-topbar, .wb-rail, #top-bar, #status-bar, #phone-tab-dock") || el.matches(".dock-fab, #scroll-top, .chat-jump-latest") ? "!" : ""}${name(el)}`);
            break;
          }
        }
      }
    }
    // On a window bar: was a panel free by its own measure (no control, no
    // words, nothing covered)? A bar is right only when none was.
    let free = null;
    if (["bar", "hang", "corner"].includes(nmb.perch)) {
      const tab = nameMarkBuddyTab();
      nmb.inner.nameMarkBuddyIndexReset();
      const ob = nmb.inner.nameMarkBuddyObstacles(tab);
      for (const p of nmb.inner.nameMarkBuddyPerches(tab)) {
        if (["bar", "hang"].includes(p.kind) || p.y < 0 || p.y + NMB_H > innerHeight) continue;
        if (nmb.inner.nameMarkBuddyHits(p.x, p.y, p.pose, ob, p.legs) || nmb.inner.nameMarkBuddyCovers(p.x, p.y, p.pose, p.legs)) continue;
        if (nmb.inner.nameMarkBuddyWordsUnder(p.x, p.y, p.pose, p.legs) > 12) continue;
        free = `${p.kind} ${name(p.edge.el)} at ${p.x},${Math.round(p.y)}`;
        break;
      }
    }
    return {
      perch: nmb.perch, pose, legs, free, claim: name(claim), gap: gap === Infinity ? "air" : Math.round(gap), paint,
      over: over.slice(0, 3), at: [Math.round(b.left), Math.round(b.top)],
    };
  });
}

// A Library sub-tab, a board and a map have panels of their own (the brief:
// "the visible card or the dock"): a window bar there fails when a panel
// perch was free by the app's own measure (no control, no words, nothing
// covered), unless PANEL_OPTIONAL is set or on a phone.
const PANELLED = /^(library\/|whiteboard|mind map|switch )/;
function verdict(r, label = "") {
  if (r.err) return r.err;
  const bad = [];
  if (PANELLED.test(label) && !phone && !process.env.PANEL_OPTIONAL && r.free) bad.push(`window bar while a panel was free (${r.free})`);
  if (r.gap === "air" || Math.abs(r.gap) > 4) bad.push(`gap ${r.gap}`);
  if (!r.paint && r.legs !== "peek") bad.push("no painted edge");
  // On a phone a full list leaves nowhere clear: there it peeks over a row's
  // edge at worst, never over a dock's or a floating button.
  const over = phone ? r.over.filter((o) => o.startsWith("!")) : r.over;
  if (over.length) bad.push(`over ${over.join(",")}`);
  return bad.join("; ");
}

(async () => {
  const opts = { viewport: { width: W, height: H } };
  if (phone) Object.assign(opts, { hasTouch: true, isMobile: true });
  const { browser, page } = await boot(opts);
  // The Settings select (#avatar-buddy) is not in the page until Settings opens, so
  // choose the companion the way the other companion sweeps do: the pref, then the module.
  await page.evaluate(async (k) => {
    localStorage.removeItem("nm-buddy-spots");
    prefs.set("avatar-buddy", k);
    await ensureModule("characters");
    syncNameMarkBuddy();
  }, process.env.KIND || "atlas");
  const boards = await page.evaluate(async () => {
    const r = await (await api("/whiteboard/boards")).json();
    const list = (r.boards || r.items || r).filter((x) => x.id != null);
    const wb = list.find((x) => x.type === "board");
    const mm = list.find((x) => x.type === "map");
    return { wb: wb?.id, mm: mm?.id };
  });
  const subs = ["All", "Documents", "Boards & maps", "Images", "Files", "AI skills", "Bookmarks", "Contents"];
  const steps = [];
  for (const t of ["dashboard", "notes", "chat", "graph", "timeline", "reminders"]) steps.push({ label: t, go: (p) => p.evaluate((x) => switchTab(x), t) });
  for (const s of subs) {
    steps.push({
      label: `library/${s}`,
      go: (p) => p.evaluate((name) => {
        if (window.currentBoardId && typeof wbShowListView === "function") wbShowListView();
        switchTab("library");
        const btn = [...document.querySelectorAll("#library-subtabs button")].find((x) => x.textContent.trim() === name);
        btn?.click();
      }, s),
    });
  }
  if (boards.wb) steps.push({ label: "whiteboard", go: (p) => p.evaluate((id) => openWhiteboardBoard(id), boards.wb) });
  if (boards.mm) steps.push({ label: "mind map", go: (p) => p.evaluate((id) => openWhiteboardBoard(id), boards.mm) });
  const only = process.env.ONLY ? process.env.ONLY.split(",") : null;
  let fails = 0;
  const row = (label, r, early = false) => {
    const v = verdict(r, early ? "" : label);
    if (v) fails += 1;
    console.log(`${v ? "FAIL" : "ok  "} ${label.padEnd(26)} ${r.err || `${r.perch}/${r.pose}${r.legs ? `/${r.legs}` : ""} on ${r.claim} gap ${r.gap} paint ${r.paint || "-"} at ${r.at}`}${v ? `  [${v}]` : ""}`);
  };
  for (const s of steps) {
    if (only && !only.includes(s.label)) continue;
    await s.go(page);
    await page.waitForTimeout(WAIT);
    row(s.label, await measure(page));
    if (process.env.SHOT) await page.screenshot({ path: `${require("./lib.js").OUT}/perchall-${W}-${s.label.replace(/[^a-z]+/gi, "_")}.png` });
  }
  // The re-perch: a sub-tab switch inside the Library, a resize, and the
  // content under it changing height. Twice each: at 900ms, before its own
  // beat, nowhere in the air and over no control (`early`, a window bar
  // allowed); and after the beat (BEAT, 5500ms: never within five seconds of
  // its last move, by design), on a panel.
  const BEAT = Number(process.env.BEAT || 5500);
  const twice = async (label) => {
    await page.waitForTimeout(900);
    row(`${label} (900ms)`, await measure(page), true);
    await page.waitForTimeout(BEAT - 900);
    row(`${label} (beat)`, await measure(page));
  };
  if (!only) {
    await steps.find((s) => s.label === "library/All").go(page);
    await page.waitForTimeout(WAIT);
    for (const s of ["Files", "Images", "Bookmarks", "All"]) {
      await steps.find((x) => x.label === `library/${s}`).go(page);
      await twice(`switch -> ${s}`);
    }
    await page.setViewportSize({ width: Math.round(W * 0.8), height: Math.round(H * 0.85) });
    await twice("resize");
    await page.setViewportSize({ width: W, height: H });
    await page.waitForTimeout(WAIT);
    await page.evaluate(() => {
      const g = nmb.glue?.el;
      const host = g?.closest(".library-view-section") || document.querySelector("#tab-library .library-view-section:not(.hidden)");
      const pad = document.createElement("div");
      pad.id = "perchall-pad";
      pad.style.height = "140px";
      host?.prepend(pad);
    });
    await twice("content grew");
    await page.evaluate(() => document.getElementById("perchall-pad")?.remove());
  }
  console.log(`${W}x${H}: ${fails ? `FAIL ${fails}` : "PASS"}`);
  process.exitCode = fails ? 1 : 0;
  await browser.close();
})();
