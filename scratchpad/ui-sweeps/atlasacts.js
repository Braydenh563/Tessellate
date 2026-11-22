// Brief 88, the owner: "more behaviours and actions especially for atlas".
// Atlas's own acts (juggle, map, meditate) were drawn and never played.
// Plays each where it may (standing on the bottom bar, floating), and reads
// after 1.6 s: the act's class on, its prop shown (the stars, the map), both
// arms' rig angles, and the figure inside the window. SHOTS=1 saves a crop.
// PASS when each act ran with its prop.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = $('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(4000);
  let bad = 0;
  for (const [act, pose, prop] of [['juggle', 'stand', '.nmp-stars'], ['map', 'stand', '.nmp-map'], ['juggle', 'float', '.nmp-stars'], ['meditate', 'float', '']]) {
    const r = await page.evaluate(async ([act, pose, prop]) => {
      const b = document.getElementById('nm-buddy');
      const top = document.getElementById('status-bar').getBoundingClientRect().top;
      DOMTokenList.prototype.remove.call(b.classList, 'nmb-sleep', 'nmb-drowsy');
      nameMarkBuddyAct('');
      nameMarkBuddyMoveTo(b, { kind: 'yours', pose, legs: '', x: 600, y: Math.round(pose === 'float' ? 400 : top - NMB_FEET + 1) }, true);
      await new Promise((r) => setTimeout(r, 1200));
      const ran = !!NAME_MARK_BUDDY_ACTS[act] && NAME_MARK_BUDDY_ACTS[act].poses.includes(nmb.pose);
      nameMarkBuddyAct(act);
      await new Promise((r) => setTimeout(r, 1600));
      const shown = prop ? Number(getComputedStyle(b.querySelector(`.atl-figure ${prop}, ${prop}`)).opacity) : 1;
      const rig = b.querySelector('.atl-figure-box')?.atlasRig;
      const arms = rig ? rig.arms.map((a) => `${a.side} ${Math.round(a.j.sh.x)}/${Math.round(a.j.el.x)}`).join(' ') : '';
      const box = b.getBoundingClientRect();
      return { on: b.classList.contains(`nmb-act-${act}`), ran, pose: nmb.pose, shown, arms, box: [Math.round(box.left), Math.round(box.top), Math.round(box.width), Math.round(box.height)] };
    }, [act, pose, prop]);
    if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SCRATCH || '.'}/atlasact-${act}-${pose}.png`, clip: { x: r.box[0] - 30, y: r.box[1] - 30, width: r.box[2] + 60, height: r.box[3] + 60 } });
    const ok = r.on && r.shown > 0.9;
    if (!ok) bad += 1;
    console.log(`${ok ? 'ok  ' : 'BAD '} ${act} ${pose}: class ${r.on}, allowed ${r.ran} (pose ${r.pose}), prop ${r.shown}, arms ${r.arms}`);
  }
  console.log(bad ? 'FAIL' : 'PASS');
  await browser.close();
})();
