// INBOX 1301 D4 ("the half lidded eyes on atlas look creepy and like fnaf"):
// how far the upper lid covers Atlas's eye in each companion state and mood,
// both looks, measured as drawn: the lid's lash line's lowest point near the
// eye's middle, in the eye white's own coordinates, as a share of its
// height. Target: every resting pose at 30% or less. Env: BASE.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(2500);
  const states = ['', 'nmb-drowsy', 'nmb-groggy', 'nmb-pout', 'nmb-grumpy', 'nmb-night', 'nmb-reading'];
  const moods = ['calm', 'sad', 'shy', 'determined', 'happy'];
  const out = {};
  for (const look of ['masculine', 'feminine']) {
    for (const st of states) {
      for (const mood of st ? ['calm'] : moods) {
        const r = await page.evaluate(async ([lk, cls, md]) => {
          const buddy = document.getElementById('nm-buddy');
          nameMarkBuddyAct('');
          buddy.querySelectorAll('.nm-atlas').forEach((a) => { a.dataset.atlasLook = lk; a.dataset.atlasMood = md; });
          ['nmb-drowsy', 'nmb-groggy', 'nmb-pout', 'nmb-grumpy', 'nmb-night', 'nmb-reading'].forEach((c) => buddy.classList.remove(c));
          if (cls) buddy.classList.add(cls);
          await new Promise((d) => setTimeout(d, 1400));
          const eye = [...buddy.querySelectorAll('.atl-eye-l')].find((e) => e.querySelector('.atl-lid .atl-lash'));
          if (!eye) return null;
          // In the eye white's own coordinates (a head tilt turns both), the
          // lash line sampled across its middle: its lowest point among the
          // samples within 3.5px of the eye's centre, against the white's box.
          const white = eye.querySelector('.atl-sclera');
          const lash = eye.querySelector('.atl-lid .atl-lash');
          const wb = white.getBBox();
          const to = white.getCTM().inverse().multiply(lash.getCTM());
          const len = lash.getTotalLength();
          let low = -Infinity;
          for (let i = 0; i <= 20; i += 1) {
            const p = lash.getPointAtLength((len * i) / 20).matrixTransform(to);
            if (Math.abs(p.x - (wb.x + wb.width / 2)) <= 3.5) low = Math.max(low, p.y);
          }
          const lashBox = { bottom: low };
          const whiteTop = wb.y;
          const open = Number(getComputedStyle(eye.querySelector('.atl-eye-open')).opacity);
          return { closed: +((lashBox.bottom - whiteTop) / wb.height).toFixed(3), open, lid: getComputedStyle(eye.closest('.nm-atlas')).getPropertyValue('--atl-lid').trim() };
        }, [look, st, mood]);
        out[`${look}|${st || 'mood'}|${mood}`] = r;
      }
    }
  }
  const worst = Object.entries(out).filter(([, v]) => v && v.open > 0.5).sort((a, b) => b[1].closed - a[1].closed)[0];
  console.log(JSON.stringify({ worst, out }));
  await browser.close();
})();
