// INBOX 591 (the owner: "the regular companion enlarged panel view has no
// life to it like with atlas and the companion itself"): open the large view
// of a plain face (SEED, default "Brayden") and, over 2s, read every
// element's transform in the figure every frame: how many elements move,
// which, and the loops running; then move the pointer to the dialog's right
// and down and read its eyes' and head's pull. The same under reduced motion.
// Opacity is not read and a face the reaction crossfade removed is skipped (B62: the swap is an opacity change by design, also under reduced motion).
// Exits 1 when, motion on, fewer than 6 parts move or the pointer is not
// followed, or, reduced, anything but the blink moves or the pointer is.
//   BASE=... node atlasmo1005-viewerlife.js
//   SHOTS=1 also saves the card, motion on, with every loop held at each
//   end of its swing and the pointer pulling (shots/atlasmo1005-viewer-*.png).
const { boot, OUT } = require('./lib.js');
(async () => {
  const out = {};
  for (const [name, opts] of [['on', {}], ['reduced', { reducedMotion: 'reduce' }]]) {
    const { browser, page } = await boot({ viewport: { width: 1280, height: 800 }, ...opts });
    const got = await page.evaluate(async (seed) => {
      document.documentElement.dataset.avatarMotion = 'always';
      openNameMarkViewer(seed);
      await new Promise((r) => setTimeout(r, 600));
      const fig = document.querySelector('.nm-viewer .nm-viewer-figure');
      const els = [fig, ...fig.querySelectorAll('*')];
      const read = () => els.map((el) => { const cs = getComputedStyle(el); return `${cs.transform}|${cs.translate}|${cs.rotate}|${cs.scale}`; });
      const first = read();
      const moved = new Set();
      const t0 = performance.now();
      while (performance.now() - t0 < 2000) {
        await new Promise((r) => requestAnimationFrame(r));
        read().forEach((v, i) => { if (els[i].isConnected && v !== first[i]) moved.add(i); });
      }
      const loops = [...new Set(fig.getAnimations({ subtree: true }).filter((a) => a.effect?.getTiming().iterations === Infinity).map((a) => a.animationName || a.id))].sort();
      return { elements: els.length, moved: moved.size, movedWhat: [...moved].map((i) => (els[i].getAttribute('class') || els[i].tagName).split(' ').slice(0, 2).join('.')), loops };
    }, process.env.SEED || 'Brayden');
    await page.mouse.move(640, 400);
    await page.mouse.move(1100, 700, { steps: 6 });
    await page.waitForTimeout(900);
    got.pointer = await page.evaluate(() => {
      const fig = document.querySelector('.nm-viewer .nm-viewer-figure > .nm-figure');
      const eyes = fig.querySelector('.nm-eyes');
      const head = fig.querySelector('.nm-buddy-head');
      return { x: fig.style.getPropertyValue('--nmv-x'), y: fig.style.getPropertyValue('--nmv-y'), eyes: getComputedStyle(eyes).translate, head: getComputedStyle(head).rotate };
    });
    if (process.env.SHOTS && name === 'on') {
      for (const [tag, at] of [['a', 0], ['b', 0.5]]) {
        await page.evaluate((f) => {
          for (const a of document.querySelector('.nm-viewer-figure').getAnimations({ subtree: true })) {
            const d = a.effect.getTiming().duration;
            if (typeof d === 'number' && a.effect.getTiming().iterations === Infinity) { a.pause(); a.currentTime = d * f; }
          }
        }, at);
        await page.waitForTimeout(300);
        const box = await page.evaluate(() => { const r = document.querySelector('.nm-viewer-card').getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; });
        await page.screenshot({ path: `${OUT}/atlasmo1005-viewer-${tag}.png`, clip: box });
      }
    }
    out[name] = got;
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
  const fails = [];
  if (out.on.moved < 6) fails.push(`motion on: ${out.on.moved} parts moved, under 6`);
  if (!(parseFloat(out.on.pointer.x) > 0.3)) fails.push('motion on: the pointer is not followed');
  //: Every face's own breath stays, slowed, under the hint (its reduce
  //: block keeps it); nothing this view adds may move.
  if (out.reduced.movedWhat.some((c) => !/blink|nm-body/.test(c))) fails.push(`reduced: ${out.reduced.movedWhat.join(', ')} moved`);
  //: A face reaction's crossfade copies the old face's --nmv-x ("0") onto the new one, so a set property is not following; a nonzero pull is.
  if (parseFloat(out.reduced.pointer.x) || 0) fails.push('reduced: the pointer is followed');
  console.log(fails.length ? `FAIL\n  ${fails.join('\n  ')}` : 'ok');
  process.exit(fails.length ? 1 : 0);
})();
