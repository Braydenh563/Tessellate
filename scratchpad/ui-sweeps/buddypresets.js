// The owner: "I want to be able to save custom companions like with the
// custom themes". In Appearance: set Atlas at Large with Fades only, save it
// as "Night owl"; switch to you at Small; apply "Night owl" and read what the
// companion is; rename it; delete it. Exits 1 on any step not as described.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => openSettingsModal('appearance', 'avatar-buddy-row'));
  await page.waitForTimeout(1200);
  const pick = (id, v) => page.evaluate(([id, v]) => { const s = document.getElementById(id); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }, [id, v]);
  await pick('avatar-buddy', 'atlas');
  await pick('avatar-buddy-size', '1.3');
  await pick('avatar-buddy-motion', 'fades');
  await page.evaluate(() => { $('avatar-buddy-presets-fold').open = true; });
  await page.fill('#avatar-buddy-preset-name', 'Night owl');
  await page.click('#avatar-buddy-preset-save');
  await page.waitForTimeout(300);
  await pick('avatar-buddy', 'me');
  await pick('avatar-buddy-size', '0.8');
  await pick('avatar-buddy-motion', 'follow');
  await page.waitForTimeout(500);
  await page.click('.avatar-buddy-preset button:first-child');
  await page.waitForTimeout(800);
  const applied = await page.evaluate(() => ({ who: $('avatar-buddy').value, seed: document.getElementById('nm-buddy')?.dataset.seed, scale: nmb.scale, motion: localStorage.getItem('avatar-buddy-motion'), motionSelect: $('avatar-buddy-motion').value }));
  await page.click('.avatar-buddy-preset button:nth-child(2)');
  await page.fill('#avatar-buddy-preset-name', 'Owl');
  await page.click('#avatar-buddy-preset-save');
  await page.waitForTimeout(300);
  const renamed = await page.evaluate(() => [...document.querySelectorAll('.avatar-buddy-preset button:first-child')].map((b) => b.textContent));
  await page.click('.avatar-buddy-preset button:nth-child(3)');
  await page.waitForTimeout(300);
  const left = await page.evaluate(() => document.querySelectorAll('.avatar-buddy-preset').length);
  console.log(JSON.stringify({ applied, renamed, left }));
  await browser.close();
  process.exit(applied.who === 'atlas' && applied.seed === 'Atlas' && applied.scale === 1.3 && applied.motion === 'fades' && applied.motionSelect === 'fades' && renamed.join() === 'Owl' && left === 0 ? 0 : 1);
})();
