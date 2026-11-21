// INBOX 619 (c) (the owner: "female atlas's eyes went blank white for a sec
// and it looked creepy"). Each look, the Atlas companion on the page and
// Atlas in the large view: through every mood change (calm to each of the
// fourteen others and back, plain and, on the companion, eased as its wake
// and doze are), its transitions paused and stepped by hand every 16ms of
// their own time (so a loaded machine's dropped frames hide nothing), reads each eye's
// white (its open eye's opacity down the chain of groups to the drawing),
// its iris (the same chain, times the iris's own) and its heart eye, and
// counts the frames where the white shows (over 0.4) with neither the iris
// nor the heart over half as strong as it: an eye gone blank. Reports the
// longest such run in ms. Exits 1 when any eye is ever blank.
//   BASE=... THEME=dark node atlas619-eyes.js
const { boot } = require('./lib.js');
(async () => {
  const fails = [];
  for (const look of (process.env.LOOKS || 'feminine,masculine').split(',')) {
    for (const where of ['buddy', 'viewer']) {
      const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
      await page.evaluate(({ look, where }) => {
        localStorage.setItem('atlas-look', look);
        document.documentElement.dataset.avatarMotion = 'always';
        if (where === 'buddy') {
          localStorage.removeItem('nm-buddy-spots');
          const b = $('avatar-buddy');
          b.value = 'atlas';
          b.dispatchEvent(new Event('change', { bubbles: true }));
        } else openNameMarkViewer('Atlas');
      }, { look, where });
      await page.waitForTimeout(3000);
      const got = await page.evaluate(async (where) => {
        const root = where === 'buddy' ? document.getElementById('nm-buddy') : document.querySelector('.nm-viewer');
        const body = root.querySelector('.atl-layer-body');
        const eff = (el) => { let o = 1; for (let e = el; e && e !== body.parentNode; e = e.parentNode) o *= +getComputedStyle(e).opacity; return o; };
        const eyes = [...body.querySelectorAll('.atl-eye')].map((eye) => ({ open: eye.querySelector('.atl-eye-open'), iris: eye.querySelector('.atl-iris'), heart: eye.querySelector('.atl-heart-eye') }));
        const blankNow = () => eyes.some(({ open, iris, heart }) => {
          const w = open ? eff(open) : 0;
          if (w < 0.4) return false;
          const i = iris ? eff(iris) : 0;
          const h = heart ? eff(heart) : 0;
          return Math.max(i, h) < 0.5 * w;
        });
        // Each change of mood, stepped through its transitions by hand
        // (every 16ms of their own time, paused), so a loaded machine's
        // dropped frames cannot hide a blank. Both ways: calm to each mood,
        // and back; plain and eased (the companion's wake and doze).
        const moods = Object.keys(ATLAS_MOODS).filter((m) => m !== 'calm');
        let steps = 0; let blank = 0; let longest = 0; let at = '';
        for (const eased of [false, true]) {
          for (const mood of moods) {
            for (const [from, to] of [['calm', mood], [mood, 'calm']]) {
              setAtlasMood(from, 0, { quiet: true });
              document.getAnimations().forEach((a) => { if (a instanceof CSSTransition) a.finish(); });
              await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
              if (eased && where === 'buddy') nameMarkBuddyEase(root, 2400);
              setAtlasMood(to, 0, { quiet: true });
              const anims = body.getAnimations({ subtree: true }).filter((a) => a instanceof CSSTransition);
              anims.forEach((a) => a.pause());
              const ms = Math.max(0, ...anims.map((a) => (a.effect.getComputedTiming().endTime || 0)));
              let run = 0;
              for (let t = 0; t <= ms + 16; t += 16) {
                anims.forEach((a) => { a.currentTime = Math.min(t, a.effect.getComputedTiming().endTime); });
                steps += 1;
                if (blankNow()) { blank += 1; run += 16; if (run > longest) { longest = run; at = `${from} to ${to}${eased ? ' eased' : ''}`; } } else run = 0;
              }
              anims.forEach((a) => a.finish());
              root.classList.remove('nmb-easing');
            }
          }
        }
        setAtlasMood('calm', 0, { quiet: true });
        return { steps, blank, longestMs: longest, during: at };
      }, where);
      console.log(look, where, JSON.stringify(got));
      if (got.blank) fails.push(`${look} ${where}: an eye blank for ${got.longestMs}ms (${got.during})`);
      await browser.close();
    }
  }
  console.log(fails.length ? `FAIL\n  ${fails.join('\n  ')}` : 'ok');
  process.exit(fails.length ? 1 : 0);
})();
