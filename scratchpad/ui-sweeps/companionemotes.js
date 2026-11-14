// The owner: "should there be more emotes like zzzz coming off it for
// sleeping, wearing a night cap etc." As you (a generated face): asleep, the
// three z's drift in turn (their opacities differ at one moment) and the
// night cap is on; woken, the cap goes; a confused face shows its "?", a
// happy one its sparkle; a change of face is a crossfade (two figures for a
// moment, then one), and after a laugh it comes down through a smile.
// Env: VW, VH. Exits 1 on any of those missing.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.VW || 1440), height: Number(process.env.VH || 900) } });
  await page.evaluate(async () => { prefs.set('avatar-buddy', 'me'); await ensureModule('characters'); syncNameMarkBuddy(); });
  await page.waitForTimeout(6000);
  const out = await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const op = (sel) => Number(getComputedStyle(buddy.querySelector(sel)).opacity);
    nameMarkBuddyAct('');
    // The cap shows only sitting or lying (the owner: never asleep standing).
    const pose = buddy.dataset.pose;
    buddy.dataset.pose = 'sit';
    buddy.classList.add('nmb-sleep');
    await wait(1400);
    const zs = [...buddy.querySelectorAll('.nm-buddy-z i')].map((z) => Math.round(Number(getComputedStyle(z).opacity) * 100) / 100);
    const capAsleep = buddy.querySelector('.nmp-nightcap') ? op('.nmp-nightcap') : null;
    buddy.classList.remove('nmb-sleep');
    if (pose === undefined) delete buddy.dataset.pose; else buddy.dataset.pose = pose;
    await wait(900);
    const capAwake = buddy.querySelector('.nmp-nightcap') ? op('.nmp-nightcap') : null;
    nameMarkBuddyExpress('confused', 2500);
    await wait(40);
    const figuresDuring = buddy.querySelectorAll('.nm-buddy-char .nm-figure').length;
    await wait(260);
    const q = op('.nmb-emote-q');
    await wait(500);
    const figuresAfter = buddy.querySelectorAll('.nm-buddy-char .nm-figure').length;
    nameMarkBuddyExpress('laughing', 600);
    await wait(300);
    const spark = op('.nmb-emote-spark');
    await wait(700);
    const between = nmb.expr;
    return { zs, capAsleep, capAwake, figuresDuring, figuresAfter, q, spark, afterLaugh: between };
  });
  console.log(JSON.stringify(out));
  await browser.close();
  const ok = new Set(out.zs).size > 1 && out.capAsleep > 0.9 && out.capAwake < 0.1 && out.figuresDuring === 2 && out.figuresAfter === 1 && out.q > 0.5 && out.spark > 0.5 && out.afterLaugh === 'happy';
  process.exit(ok ? 0 : 1);
})();
