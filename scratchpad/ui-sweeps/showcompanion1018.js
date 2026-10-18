// The "Companion hidden" notice measured against the toast-with-action recipe (INBOX 743 tail).
//   BASE=http://127.0.0.1:8798 node scratchpad/ui-sweeps/showcompanion1018.js
const { boot } = require('./lib.js');
(async () => {
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const { browser, page } = await boot({ viewport: vp });
    await page.evaluate(() => { prefs.set('avatar-buddy', 'me'); syncNameMarkBuddy(); });
    await page.waitForTimeout(2500);
    const had = await page.evaluate(() => !!document.getElementById('nm-buddy'));
    await page.evaluate(() => nameMarkBuddyHide(document.getElementById('nm-buddy')));
    await page.waitForTimeout(900);
    const m = await page.evaluate(() => {
      const t = document.querySelector('#toast-box .toast');
      if (!t) return null;
      const q = (s) => {
        const e = t.querySelector(s);
        if (!e) return null;
        const r = e.getBoundingClientRect();
        const c = getComputedStyle(e);
        return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), color: c.color, weight: c.fontWeight, bg: c.backgroundColor, border: c.borderTopWidth };
      };
      const r = t.getBoundingClientRect();
      return { toast: { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), vw: innerWidth }, msg: q('.toast-msg'), actions: q('.toast-actions'), action: q('.toast-action'), close: q('button:not(.toast-action)'), text: t.innerText.replace(/\n/g, ' | ') };
    });
    console.log(vp.width, 'companion was on', had, JSON.stringify(m, null, 1));
    await browser.close();
  }
})();
