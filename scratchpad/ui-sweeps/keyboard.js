// Where does the Tab key actually land?
//
//   BASE=http://127.0.0.1:8781 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node keyboard.js
//
// WORLD_CLASS_PLAN H6 asks for a keyboard-complete app and nothing in the
// project could see the tab order, so this presses Tab and records what has
// focus, which is the only thing that settles the question.
//
// **Ground truth, not a DOM heuristic.** The first attempt at this counted
// elements that were focusable-but-not-visible in the DOM and reported ~2,300
// per tab, which meant nothing: this app keeps every tab's page in the
// document, and a `display: none` subtree is skipped by the browser's own tab
// order, so it is never reached whatever the count says. Walking the order
// instead reaches about thirty elements a tab, which is the real number.
//
// **Settle before reading**, which is the second thing the first attempt got
// wrong. A control revealed on `:focus-within` through an opacity transition
// (the notes sidebar's rename and delete buttons) reads `opacity: 0` in the
// same tick as the key press and is fully visible 150ms later. Twenty
// findings came from that one mistake. The wait below is what makes the
// remaining findings real.
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const PW = 'testpassword123';
const TABS = ['dashboard', 'notes', 'library', 'chat', 'graph', 'timeline', 'reminders'];
//: Enough presses to wrap past the end of every tab's order and back into the
//: browser chrome; measured, the longest surface reaches 39 distinct stops.
const PRESSES = Number(process.env.PRESSES || 90);
//: The reveal transition is `--motion-fast`; this is several times it, and
//: the cost is bounded because it is only paid on a stop that first read as
//: invisible, which is a handful per run rather than one per press.
const SETTLE_MS = 350;

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => {
    try { localStorage.setItem('theme', 'light'); localStorage.setItem('onboardingDone', '1'); } catch (e) {}
  });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  if (await page.$('#lock-password') && await page.isVisible('#lock-password')) {
    await page.fill('#lock-password', PW); await page.click('#lock-submit'); await page.waitForTimeout(3000);
  }
  await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
  await page.waitForTimeout(4000);

  const read = () => page.evaluate(() => {
    const a = document.activeElement;
    if (!a || a === document.body || a === document.documentElement) return null;
    const box = a.getBoundingClientRect();
    // `aria-labelledby` and `alt` count too: several icon buttons name
    // themselves through a sibling rather than an attribute of their own.
    const labelledBy = (a.getAttribute('aria-labelledby') || '')
      .split(/\s+/).filter(Boolean)
      .map((id) => document.getElementById(id)?.textContent || '').join(' ');
    const name = (
      a.getAttribute('aria-label') || labelledBy || a.textContent.trim() ||
      a.getAttribute('title') || a.getAttribute('placeholder') ||
      a.getAttribute('alt') || a.value || ''
    ).trim();
    return {
      id: `${a.tagName.toLowerCase()}${a.id ? '#' + a.id : ''}` +
          (typeof a.className === 'string' && a.className
            ? '.' + a.className.split(/\s+/).slice(0, 2).join('.') : ''),
      name: name.slice(0, 40),
      visible: Boolean(a.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true })),
      sized: box.width > 0 && box.height > 0,
      hiddenTab: Boolean(a.closest(".tab-page.hidden")),
      positive: Number(a.getAttribute('tabindex') || 0) > 0,
    };
  });

  const findings = [];
  for (const tab of TABS) {
    await page.evaluate((n) => { try { switchTab(n); } catch (e) {} }, tab);
    await page.waitForTimeout(900);
    await page.evaluate(() => document.body.focus());
    const seen = new Set();
    const here = new Set();
    for (let i = 0; i < PRESSES; i++) {
      await page.keyboard.press('Tab');
      let r = await read();
      if (!r) continue;
      // Only a stop that looks wrong is worth waiting on, and it may be
      // mid-reveal rather than genuinely hidden. Re-read once it has settled.
      if (!r.visible || !r.sized || r.hiddenTab) {
        await page.waitForTimeout(SETTLE_MS);
        r = (await read()) || r;
      }
      seen.add(r.id);
      if (!r.visible || !r.sized) here.add(`${r.id} takes focus while invisible, name="${r.name}"`);
      else if (!r.name) here.add(`${r.id} takes focus with no accessible name`);
      if (r.positive) here.add(`${r.id} has a positive tabindex, which reorders the whole page`);
    }
    console.log(`${tab.padEnd(10)} ${String(seen.size).padStart(3)} stops, ${here.size} findings`);
    for (const line of here) findings.push(`[${tab}] ${line}`);
  }

  for (const line of findings) console.log(`    ${line}`);
  console.log(findings.length ? `FAIL: ${findings.length} findings` : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
