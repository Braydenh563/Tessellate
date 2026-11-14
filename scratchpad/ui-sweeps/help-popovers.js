// Every '?' in Settings opens a popover that is inside the window.
//
// The sweep OPEN.md named ("help-popovers.js is not built: open every '?' on
// Settings, assert each popover rect is inside the viewport at 1440 and 390").
// It walks every `.settings-section`, shows it through `showSettingsSection`
// (the same door the nav uses), presses each visible `[data-help-for]` toggle
// with a trusted click, and measures the panel it opened: on screen at all,
// inside the viewport on all four sides (a 1px tolerance for subpixel rounding),
// and closed again by a second press. A toggle that opens nothing is reported
// as such, never as a pass.
//
//   BASE=http://127.0.0.1:8801 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/help-popovers.js
const { boot } = require('./lib.js');

(async () => {
  let fails = 0;
  let measured = 0;
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const { browser, page } = await boot({ viewport });
    await page.evaluate(() => openSettingsModal('models'));
    await page.waitForTimeout(800);
    const sections = await page.evaluate(() =>
      [...document.querySelectorAll('#settings-modal .settings-section[id^="settings-"]')].map((s) => s.id.slice(9)));
    for (const name of sections) {
      await page.evaluate((n) => showSettingsSection(n), name);
      await page.waitForTimeout(500);
      const ids = await page.evaluate((n) => {
        const sec = document.getElementById(`settings-${n}`);
        return [...sec.querySelectorAll('[data-help-for]')]
          .filter((t) => t.getBoundingClientRect().width > 0 && t.offsetParent !== null)
          .map((t) => t.dataset.helpFor);
      }, name);
      for (const id of ids) {
        const trigger = `#settings-${name} [data-help-for="${id}"]`;
        // A '?' inside a closed fold is not on screen for a person either: they open the fold first.
        await page.evaluate((sel) => {
          for (let d = document.querySelector(sel)?.closest('details'); d; d = d.parentElement?.closest('details')) d.open = true;
        }, trigger);
        await page.waitForTimeout(150);
        await page.locator(trigger).first().scrollIntoViewIfNeeded().catch(() => {});
        // Settings scrolls smoothly: a scroll event after the press closes the popover (menus.js), so let it settle.
        await page.waitForTimeout(500);
        const clicked = await page.locator(trigger).first().click({ timeout: 3000 }).then(() => true).catch(() => false);
        await page.waitForTimeout(250);
        const r = await page.evaluate((pid) => {
          const p = document.getElementById(pid);
          if (!p) return null;
          const b = p.getBoundingClientRect();
          const open = !p.classList.contains('hidden') && b.width > 0 && b.height > 0;
          return { open, l: Math.round(b.left), t: Math.round(b.top), r: Math.round(b.right), b: Math.round(b.bottom),
            vw: innerWidth, vh: innerHeight };
        }, id);
        const where = `${viewport.width} ${name} #${id}`;
        if (!clicked || !r || !r.open) {
          console.log(`FAIL ${where}: did not open (clicked ${clicked})`);
          fails++;
          continue;
        }
        measured++;
        const inside = r.l >= -1 && r.t >= -1 && r.r <= r.vw + 1 && r.b <= r.vh + 1;
        if (!inside) {
          console.log(`FAIL ${where}: ${r.l},${r.t} to ${r.r},${r.b} in ${r.vw}x${r.vh}`);
          fails++;
        }
        await page.locator(trigger).first().click({ timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(150);
        const closed = await page.evaluate((pid) => {
          const p = document.getElementById(pid);
          return p.classList.contains('hidden') || p.getBoundingClientRect().height === 0;
        }, id);
        if (!closed) {
          console.log(`FAIL ${where}: a second press did not close it`);
          fails++;
          await page.keyboard.press('Escape');
        }
      }
    }
    await browser.close();
  }
  console.log(`measured ${measured} popovers; findings: ${fails}`);
  process.exit(fails ? 1 : 0);
})();
