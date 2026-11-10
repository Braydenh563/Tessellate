// UI Phase 11 item 5: a share from the phone's share sheet. The installed
// app opens at / with share_title, share_text and share_url; after the
// unlock the three land in Capture as one note, the query is cleared, and
// a reload shares nothing twice.
const { boot } = require('./lib.js');
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
(async () => {
  const { page, browser } = await boot({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2000);
  const q = new URLSearchParams({ share_title: 'A page worth keeping', share_text: 'The paragraph someone selected.', share_url: 'https://example.org/page' });
  await page.goto(`${BASE}/?${q}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4500);
  const out = await page.evaluate(() => ({ tab: document.querySelector('#tab-bar button.active')?.dataset.tab, capture: !document.getElementById('capture').classList.contains('hidden'), value: document.getElementById('entry-content').value, search: location.search, active: document.activeElement && (document.activeElement.id || document.activeElement.className.split(' ')[0]) }));
  console.log(JSON.stringify(out));
  const findings = [];
  if (out.tab !== 'notes' || !out.capture) findings.push('the share did not open Capture');
  if (!/^# A page worth keeping\n\nThe paragraph someone selected\.\n\nhttps:\/\/example\.org\/page$/.test(out.value)) findings.push('the capture text is not the share: ' + JSON.stringify(out.value));
  if (out.search !== '') findings.push('the query was not cleared: ' + out.search);
  await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForTimeout(3500);
  const again = await page.evaluate(() => document.getElementById('entry-content').value);
  // The capture box keeps its draft across a reload on purpose; what a
  // reload must not do is add the share a second time.
  if ((again.match(/A page worth keeping/g) || []).length !== 1) findings.push('a reload shared it again: ' + JSON.stringify(again));
  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? 'FAIL: ' + findings.join('\n  ') : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
