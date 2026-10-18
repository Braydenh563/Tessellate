// Every framed Atlas keeps its figure inside the frame (INBOX 743 tail).
//   BASE=http://127.0.0.1:8798 node scratchpad/ui-sweeps/atlasframe1018.js
// For each svg.nm-atlas / .nm-figure inside a rounded frame (.atlas-mark,
// .persona-mark, .profile-mark, .rich-picker-tile-face, #onboarding-atlas),
// prints the figure rect against the frame rect and whether it spills.
const { boot } = require('./lib.js');
(async () => {
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const { browser, page } = await boot({ viewport: vp });
    await page.evaluate(async () => {
      document.getElementById('onboarding-overlay')?.classList.remove('hidden');
      try { localStorage.removeItem('onboardingDone'); } catch (e) {}
      if (typeof maybeShowOnboarding === 'function') { try { await maybeShowOnboarding(true); } catch (e) {} }
      if (typeof onboardingRun !== 'undefined' && typeof renderOnboardingSlide === 'function') { onboardingRun.index = 0; renderOnboardingSlide(); }
    });
    await page.waitForTimeout(800);
    // Walk every settings pane, the Atlas chat and the help head so each framed Atlas is on screen once.
    const seen = [];
    const measure = () => page.evaluate(() => {
      const out = [];
      const sel = '.atlas-mark, .persona-mark, .profile-mark, .rich-picker-tile-face, .onboarding-atlas > span, [data-atlas-avatar]';
      for (const frame of new Set(document.querySelectorAll(sel))) {
        const fr = frame.getBoundingClientRect();
        if (!fr.width) continue;
        const fig = frame.querySelector('svg, .nm-figure, .nm-atlas');
        if (!fig) continue;
        const r = fig.getBoundingClientRect();
        const cs = getComputedStyle(frame);
        const clipped = cs.overflow !== 'visible' || getComputedStyle(fig).overflow !== 'visible';
        const spill = Math.round(Math.max(fr.left - r.left, r.right - fr.right, fr.top - r.top, r.bottom - fr.bottom));
        out.push({ frame: frame.className.toString().slice(0, 40) || frame.id, fw: Math.round(fr.width), fh: Math.round(fr.height), fig: [Math.round(r.width), Math.round(r.height)], spill, radius: cs.borderRadius, clipped });
      }
      return out;
    });
    const panes = await page.evaluate(() => [...document.querySelectorAll('.settings-section')].map((p) => p.id.slice(9)));
    seen.push(...(await measure()));
    for (const name of panes) {
      await page.evaluate((n) => openSettingsModal(n), name).catch(() => {});
      await page.waitForTimeout(500);
      seen.push(...(await measure()).map((m) => ({ pane: name, ...m })));
    }
    const uniq = new Map(seen.map((m) => [JSON.stringify([m.frame, m.fw, m.fh, m.fig, m.spill]), m]));
    console.log(vp.width, 'panes', panes.length);
    for (const m of uniq.values()) console.log(JSON.stringify(m));
    await browser.close();
  }
})();
