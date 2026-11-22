// The owner: "I just switched tab, and my companion just appeared on it
// after a bit. no animation or special transition". At 1093x614, under four
// motion states (normal; Performance mode's reduced page motion; the app's
// Motion set to Reduce; the system asking for less motion), switches tab by
// clicking the tab bar and by the keyboard (focus a tab button, Enter), and
// samples the companion every frame after each switch. Reports, per switch:
// how it came in (the entrance's animations running in its first visible
// frame), and whether any frame showed it fully (opacity 0.95+) with no
// frame of arrival before it (a pop).
// Exits 1 on a pop or an arrival with no animation.
const { boot } = require('./lib.js');
const STATES = ['normal', 'perf', 'app-reduce', 'os-reduce'];

(async () => {
  const rows = [];
  for (const state of STATES) {
    const opts = { viewport: { width: 1093, height: 614 } };
    if (state === 'os-reduce') opts.reducedMotion = 'reduce';
    const { browser, page } = await boot(opts);
    await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, 'me');
    await page.evaluate((st) => {
      const root = document.documentElement;
      if (st === 'perf') { root.dataset.perf = 'on'; root.dataset.motion = 'reduced'; }
      if (st === 'app-reduce') { localStorage.setItem('motion', 'reduced'); if (typeof applyAppearance === 'function') applyAppearance(); }
      nameMarkBuddyMotionApply();
    }, state);
    await page.waitForTimeout(5000);
    for (const [how, tab] of [['click', 'notes'], ['keys', 'chat'], ['click', 'dashboard']]) {
      await page.evaluate(() => {
        const buddy = document.getElementById('nm-buddy');
        window.__f = [];
        window.__stop = false;
        const tick = () => {
          const ch = buddy.querySelector('.nm-buddy-char');
          let op = 1;
          for (let el = ch; el && el !== document.body; el = el.parentElement) { const cs = getComputedStyle(el); op *= Number(cs.opacity); if (cs.visibility === 'hidden') op = 0; }
          const anims = [buddy, ch].flatMap((el) => el.getAnimations()).filter((a) => a.playState === 'running' && !(a.timeline instanceof ScrollTimeline));
          window.__f.push({ op: Math.round(op * 100) / 100, anim: anims.length > 0 || buddy.classList.contains('nmb-walking') || buddy.classList.contains('nmb-poofing') });
          if (!window.__stop) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      if (how === 'click') await page.click(`#tab-btn-${tab}`);
      else { await page.focus(`#tab-btn-${tab}`); await page.keyboard.press('Enter'); }
      await page.waitForTimeout(4500);
      const r = await page.evaluate(() => {
        window.__stop = true;
        const f = window.__f;
        let hidden = false; let first = -1;
        for (let i = 0; i < f.length; i += 1) { if (f[i].op <= 0.05) hidden = true; if (hidden && f[i].op > 0.05) { first = i; break; } }
        if (first < 0) return { hid: hidden, arrived: false };
        const pop = f[first].op >= 0.95 && !f[first].anim;
        return { hid: hidden, arrived: true, entered: nmb.enteredBy, firstOp: f[first].op, animated: f[first].anim, pop };
      });
      rows.push({ state, how, tab, ...r });
    }
    await browser.close();
  }
  console.log(JSON.stringify(rows));
  process.exit(rows.some((r) => r.pop || (r.arrived && !r.animated)) ? 1 : 0);
})();
