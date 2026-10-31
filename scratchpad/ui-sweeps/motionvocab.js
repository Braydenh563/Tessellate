// INBOX 1506 B: the motion vocabulary as numbers (tokens, a menu's row stagger, a plus to a minus, a chevron, a dialog, a tab).
//   MODE=follow|on|off|uioff OSRM=1 BASE=http://127.0.0.1:8873 node scratchpad/ui-sweeps/motionvocab.js
const { boot } = require('./lib.js');
const MODE = process.env.MODE || 'follow';   // follow | on | off | uioff
(async () => {
  const { browser, page } = await boot({ reducedMotion: process.env.OSRM === '1' ? 'reduce' : 'no-preference' });
  if (MODE === 'on' || MODE === 'off') {
    await page.evaluate((c) => document.querySelector(`#motion-seg button[data-motion-choice="${c}"]`).click(), MODE);
    await page.waitForTimeout(400);
  }
  if (MODE === 'uioff') {
    await page.evaluate(() => { document.documentElement.dataset.uiMotion = 'off'; });
    await page.waitForTimeout(200);
  }
  await page.evaluate(() => ensureModule('library'));
  await page.waitForTimeout(1500);
  const out = await page.evaluate(async () => {
    const r = document.documentElement, cs = getComputedStyle(r);
    const o = { motion: r.dataset.motion, uiMotion: r.dataset.uiMotion,
      tokens: ['--ui-fast', '--ui-base', '--ui-slow', '--ease-spring'].map((k) => k + '=' + cs.getPropertyValue(k).trim()).join(' ') };
    // a kebab menu, opened by its own opener
    const opener = [...document.querySelectorAll('.kebab-opener')].find((b) => b.offsetParent);
    if (opener) {
      opener.click();
      await new Promise((r2) => setTimeout(r2, 30));
      o.openerExpanded = opener.getAttribute('aria-expanded'); o.openerFound = (opener.closest('[id]')||{}).id;
      const menu = document.querySelector('.action-menu:not(.hidden)');
      if (menu) {
        const mcs = getComputedStyle(menu);
        const kids = [...menu.children];
        o.menu = { rows: kids.length, anim: mcs.animationName, dur: mcs.animationDuration, ease: mcs.animationTimingFunction.slice(0, 40), origin: mcs.transformOrigin };
        o.rows = kids.slice(0, 10).map((k) => { const c = getComputedStyle(k); return c.animationName + '/' + c.animationDelay + '/' + c.animationDuration; });
        o.rowAnimsRunning = kids.map((k) => k.getAnimations().length);
        await new Promise((r2) => setTimeout(r2, 500));
        o.rowAnimsAfter = kids.reduce((a, k) => a + k.getAnimations().length, 0);
        o.rowProps = kids[0] ? getComputedStyle(kids[0]).opacity + ' ' + getComputedStyle(kids[0]).translate : '';
        opener.click();
      } else o.menu = 'did not open';
    } else o.menu = 'no kebab drawn';
    // a plus that becomes a minus
    const host = document.createElement('button');
    host.setAttribute('aria-expanded', 'false');
    host.innerHTML = '<span class="ui-pm ph-lead" aria-hidden="true"></span> Insert';
    document.body.appendChild(host);
    const pm = host.firstChild;
    const snap = () => ({ t: getComputedStyle(pm).transform, td: getComputedStyle(pm).transitionDuration, tf: getComputedStyle(pm).transitionTimingFunction.slice(0, 30),
      after: getComputedStyle(pm, '::after').transform, afterTd: getComputedStyle(pm, '::after').transitionDuration, w: pm.getBoundingClientRect().width.toFixed(1) });
    o.pmClosed = snap();
    host.setAttribute('aria-expanded', 'true');
    await new Promise((r2) => setTimeout(r2, 700));
    o.pmOpen = snap();
    // a chevron
    const caret = document.createElement('i');
    caret.className = 'ph ph-caret-down';
    document.body.appendChild(caret);
    o.caret = { dur: getComputedStyle(caret).transitionDuration, prop: getComputedStyle(caret).transitionProperty, ease: getComputedStyle(caret).transitionTimingFunction.slice(0, 30) };
    host.remove(); caret.remove();
    // dialog and tab
    const tp = document.querySelector('.tab-page:not(.hidden)');
    o.tabPage = tp && getComputedStyle(tp).transitionDuration;
    const ov = document.createElement('div');
    ov.className = 'modal-overlay';
    ov.innerHTML = '<div class="card modal-card"></div>';
    document.body.appendChild(ov);
    o.dialog = getComputedStyle(ov).transitionDuration + ' / card ' + getComputedStyle(ov.firstElementChild).transitionDuration;
    ov.remove();
    return o;
  });
  console.log(MODE, process.env.OSRM === '1' ? 'os-reduced' : 'os-normal', JSON.stringify(out));
  await browser.close();
})();
