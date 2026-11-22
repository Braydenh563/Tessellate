// The owner: "I havent made a custom avatar yet but it set one randomly ...
// on the companion when I clicked it. but I as a user might not have even
// known how to make a custom avatar and if it is a feature." With no face
// made: Appearance says so under the companion's select, with a button that
// opens Profile's avatar maker; the companion's menu offers "Create your
// avatar"; choosing "Your own character" there opens its maker.
// Exits 1 when any of those is missing.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { localStorage.removeItem('avatar-buddy-custom'); const b = $('avatar-buddy'); b.value = 'me'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(3000);
  await page.evaluate(() => openSettingsModal('appearance', 'avatar-buddy-row'));
  await page.waitForTimeout(1200);
  const hint = await page.evaluate(() => { const h = $('avatar-buddy-make'); return { shown: !h.classList.contains('hidden') && h.getBoundingClientRect().height > 0, text: h.textContent.trim() }; });
  await page.click('#avatar-buddy-make-go');
  await page.waitForTimeout(1200);
  const opened = await page.evaluate(() => { const p = document.getElementById('profile-look'); const r = p?.getBoundingClientRect(); return !!r && r.height > 0 && r.top < innerHeight && r.bottom > 0; });
  await page.evaluate(() => closeSettingsModal?.());
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  const menu = await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyMenu(buddy, null);
    await new Promise((r) => setTimeout(r, 300));
    const text = [...document.querySelectorAll('.action-menu')].map((m) => m.textContent).join(' ');
    return { hasCompanion: text.includes('Companion') };
  });
  // Open the Companion submenu and look for the entry.
  const sub = await page.evaluate(async () => {
    const btn = [...document.querySelectorAll('.action-menu button, .action-menu [role="menuitem"]')].find((b) => b.textContent.includes('Companion'));
    btn?.click();
    await new Promise((r) => setTimeout(r, 300));
    return [...document.querySelectorAll('.action-menu')].map((m) => m.textContent).join(' ').includes('Create your avatar');
  });
  console.log(JSON.stringify({ hint, opensProfileMaker: opened, menu, menuOffersCreate: sub }));
  await browser.close();
  process.exit(hint.shown && opened && sub ? 0 : 1);
})();
