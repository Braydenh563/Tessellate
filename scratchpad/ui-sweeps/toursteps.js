// Every step of every tour section, at a desktop width and a phone width.
//
// `tourdim.js` measures one step very closely: that the dim covers the window
// and the card has a ground. This walks the whole surface shallowly instead,
// because the owner's report was not about one step ("the whole tour is
// completely and utterly broken", 2026-09-21), and the faults a tour actually
// has are per-step: a card placed off the window at a width nobody tried, a
// card that covers the very control it is describing, text that does not fit
// so the card scrolls, a step whose target went off screen so there is nothing
// lit. None of those is visible from one step at one size.
//
// Six checks per step, all from geometry rather than from a screenshot
// (CLAUDE.md section 5: a screenshot you look at is not a measurement).
const { boot } = require("./lib.js");

let failures = 0;
function ok(label, pass, detail) {
  console.log(`${pass ? "PASS" : "FAIL"}  ${label}  — ${detail}`);
  if (!pass) failures += 1;
}

(async () => {
  let steps = 0;
  const faults = [];
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const { page, browser } = await boot({ viewport: vp, isMobile: vp.width < 500 });
    // tour.js is a lazy bundle now; load it before reading its table.
    await page.evaluate(() => (typeof ensureModule === "function" ? ensureModule("tour") : null));
    // tour.js is one closure, so its table is read from the file (a literal of
    // plain strings): each section's id and, per card title, the target
    // selectors the tour resolves (`tourResolve`: `target`, else `or`).
    const tourSrc = require("fs").readFileSync(require("path").join(__dirname, "..", "..", "frontend", "js", "tour.js"), "utf8");
    const from = tourSrc.indexOf("const TOUR_SECTIONS = [");
    const table = new Function("return " + tourSrc.slice(tourSrc.indexOf("[", from), tourSrc.indexOf("\n  ];", from) + 4).trim().replace(/;$/, ""))();
    const sections = table.map((s) => s.id);
    // Two cards can share a title and differ by `media` (Your conversations: a
    // sidebar on a desktop, its opener on a phone), so each key lists them all.
    const targets = {};
    for (const s of table) for (const st of s.steps) (targets[`${s.id}|${st.title}`] ||= []).push({ target: st.target, or: st.or, media: st.media || null });
    for (const sec of sections) {
      const res = await page.evaluate(async ({ sec, targets }) => {
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        openTour(sec);
        await wait(700);
        const out = [];
        for (let i = 0; i < 40; i += 1) {
          const spot = document.getElementById("tour-spot");
          const card = document.getElementById("tour-card");
          if (card.classList.contains("hidden")) break;
          // Measured once the cut-out and the card have stopped moving (the
          // same box on three reads, 100ms apart), not after a fixed pause:
          // while it travels to the next control it is over something else.
          const boxKey = () => ["tour-spot", "tour-card"].map((id) => {
            const b = document.getElementById(id).getBoundingClientRect();
            return [b.left, b.top, b.width, b.height].map(Math.round).join(",");
          }).join("|");
          for (let steady = 0, last = "", n = 0; steady < 3 && n < 30; n += 1) {
            await wait(100);
            const now = boxKey();
            steady = now === last ? steady + 1 : 0;
            last = now;
          }
          // The last card of a section hands over to the next one by name, so
          // Next would walk every later section again from here (the run took
          // longer than five minutes that way): a card that belongs to another
          // section is that section's own turn, walked there.
          const here = document.getElementById("tour-title").textContent;
          if (!targets[`${sec}|${here}`] && Object.keys(targets).some((k) => k.endsWith(`|${here}`))) break;
          const s = spot.getBoundingClientRect();
          const c = card.getBoundingClientRect();
          const w = window.innerWidth;
          const h = window.innerHeight;
          let bare = 0;
          for (let x = 3; x < w - 3; x += 23) {
            for (let y = 3; y < h - 3; y += 23) {
              const inSpot = x >= s.left - 6 && x <= s.right + 6 && y >= s.top - 6 && y <= s.bottom + 6;
              const inCard = x >= c.left - 2 && x <= c.right + 2 && y >= c.top - 2 && y <= c.bottom + 2;
              if (inSpot || inCard) continue;
              if (!document.elementsFromPoint(x, y).some((e) => e.classList.contains("tour-block-panel"))) {
                bare += 1;
              }
            }
          }
          out.push({
            n: document.getElementById("tour-count").textContent,
            title: document.getElementById("tour-title").textContent,
            // A card outside the window is a step the person cannot read at
            // all, and it is always a width thing: it passes at 1440 and
            // fails at 390, which is why this probe takes two.
            offscreen: c.left < -1 || c.top < -1 || c.right > w + 1 || c.bottom > h + 1,
            collapsed: c.height < 40 || c.width < 40,
            // The card over its own cut-out is the tour describing something
            // it is covering, which is the surface's whole purpose inverted.
            covers: !(c.right <= s.left || c.left >= s.right || c.bottom <= s.top || c.top >= s.bottom),
            bare,
            lit: !spot.classList.contains("hidden") && s.width > 0 && s.left < w && s.right > 0 && s.top < h && s.bottom > 0,
            // A scrolling step card means the text was written for a width
            // this is not: nobody scrolls a tooltip, they press Next.
            scrolls: card.scrollHeight > card.clientHeight + 1,
            // INBOX 745 (d): the lit control must be painted, not just laid
            // out. Opacity multiplies down the tree and is not inherited, so a
            // button in a wrapper faded to 0 until hover reads 1 on itself;
            // the product of its ancestors' is what the eye gets. And the
            // control has to be the thing at its own centre (nothing drawn
            // over it), or the ring frames an empty square.
            target: (() => {
              // `tourRun` is closure-private, and the title lags the target by a
              // frame or two while one section hands over to the next, so the lit
              // control is found by where the cut-out is: the element, among every
              // step's `target` and `or`, whose box is nearest the spotlight's.
              const shown = (e) => { const b = e && e.getBoundingClientRect(); return !!b && b.width > 0 && b.height > 0; };
              const lift = (e) => (e ? e.closest(".select-shell") || e : e);
              let el = null;
              let best = Infinity;
              for (const list of Object.values(targets)) {
                for (const st of list) {
                  if (st.media && !matchMedia(st.media).matches) continue;
                  for (const sel of [st.target, st.or]) {
                    const cand = sel ? lift(document.querySelector(sel)) : null;
                    if (!shown(cand)) continue;
                    const b = cand.getBoundingClientRect();
                    const d = Math.abs(b.left - s.left) + Math.abs(b.top - s.top) + Math.abs(b.width - s.width) + Math.abs(b.height - s.height);
                    if (d < best) { best = d; el = cand; }
                  }
                }
              }
              // The cut-out pads its control by a few pixels: farther than that
              // and the spotlight is on something this table does not name.
              if (!el || best > 60) return null;
              let o = 1;
              for (let n = el; n && n !== document.documentElement; n = n.parentElement) o *= Number(getComputedStyle(n).opacity || "1");
              const r = el.getBoundingClientRect();
              const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
              return { o: Math.round(o * 100) / 100, hit: Boolean(hit && (el.contains(hit) || hit.contains(el))), w: Math.round(r.width), h: Math.round(r.height) };
            })(),
          });
          const next = document.getElementById("tour-next");
          if (!next) break;
          next.click();
          await wait(650);
        }
        return out;
      }, { sec, targets });
      for (const r of res) {
        steps += 1;
        const tag = `${vp.width} ${sec} "${r.title}" ${r.n}`;
        if (r.offscreen) faults.push(`${tag}: card off the window`);
        if (r.collapsed) faults.push(`${tag}: card collapsed`);
        if (r.covers) faults.push(`${tag}: card covers its own cut-out`);
        if (r.bare) faults.push(`${tag}: ${r.bare} undimmed points`);
        if (!r.lit) faults.push(`${tag}: nothing lit`);
        if (r.scrolls) faults.push(`${tag}: card scrolls, the text does not fit`);
        if (r.target && r.target.o < 0.5) faults.push(`${tag}: target faded (opacity ${r.target.o})`);
        if (r.target && !r.target.hit) faults.push(`${tag}: target is not what is drawn at its centre`);
        if (r.target && (r.target.w < 4 || r.target.h < 4)) faults.push(`${tag}: target is empty (${r.target.w}x${r.target.h})`);
      }
    }
    await browser.close();
  }
  ok(
    "every tour step reads correctly at 1440 and at 390",
    steps > 20 && faults.length === 0,
    `${steps} steps walked, ${faults.length} faults${faults.length ? ": " + faults.slice(0, 6).join("; ") : ""}`
  );
  console.log(failures ? `FAILURES: ${failures}` : "ALL PASS");
  process.exit(failures ? 1 : 0);
})();
