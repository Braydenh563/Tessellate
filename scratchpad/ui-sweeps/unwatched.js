// An answer that finishes while its panel is shut posts a notification that
// opens the panel on it (owner ask, 2026-09-23). Both panels: the popup agent
// and Atlas.
//
// The model is faked at the network: `/chat/stream` and `/help/ask/stream`
// are routed and held for two seconds, then answered in one NDJSON body. That
// is the shape of the case (a slow answer, a panel closed meanwhile) without
// needing a model; what a real model streams is not exercised here.
//
// Checks per panel: closed before the answer, one notification is recorded
// with a panel action and a toast carries "Open"; pressing it reopens the
// panel scrolled to that answer; asked with the panel kept open, nothing is
// recorded. Exit 1 on any failure.
//
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/unwatched.js
const {boot} = require('./lib.js');
(async () => {
  const {browser, page} = await boot({viewport: {width: 1184, height: 760}});
  const hold = (body) => async (route) => {
    await new Promise((r) => setTimeout(r, 2000));
    await route.fulfill({status: 200, contentType: 'application/x-ndjson', body});
  };
  await page.route('**/chat/stream', hold(
    JSON.stringify({type: 'answer', delta: 'The answer from the popup agent.'}) + '\n'));
  await page.route('**/help/ask/stream', hold(
    JSON.stringify({type: 'delta', text: 'The answer from Atlas.'}) + '\n' +
    JSON.stringify({type: 'done', content: 'The answer from Atlas.'}) + '\n'));
  const fails = [];
  const notes = () => page.evaluate(() => JSON.parse(localStorage.getItem(NOTIFICATIONS_KEY) || '[]')
    .filter((n) => n.action && n.action.panel));
  await page.evaluate(() => localStorage.setItem(NOTIFICATIONS_KEY, '[]'));

  // --- the popup agent, closed mid-answer ---------------------------------
  await page.evaluate(() => { toggleAgentPalette(); cmdPaletteAsk('What did I write about tides?'); });
  await page.waitForTimeout(300);
  await page.evaluate(() => toggleAgentPalette());
  await page.waitForTimeout(2600);
  let got = await notes();
  const toast1 = await page.evaluate(() => [...document.querySelectorAll('#toast-box .toast')].map((t) => t.textContent));
  console.log('agent', JSON.stringify(got), JSON.stringify(toast1));
  if (got.length !== 1 || got[0].action.panel !== 'agent') fails.push('agent: no notification');
  if (!toast1.some((t) => /Popup agent answered/.test(t) && /Open/.test(t))) fails.push('agent: no toast with Open');
  await page.evaluate(() => [...document.querySelectorAll('#toast-box .toast-action')].find((b) => /Open/.test(b.textContent))?.click());
  await page.waitForTimeout(400);
  const agentBack = await page.evaluate((id) => {
    const open = !cmdPaletteOverlay.classList.contains('hidden');
    const row = [...cmdPaletteResults.querySelectorAll('[data-answer-id]')].find((el) => el.dataset.answerId === id);
    const list = cmdPaletteResults.getBoundingClientRect();
    const r = row?.getBoundingClientRect();
    return {open, found: Boolean(row), inView: Boolean(r && r.top >= list.top - 1 && r.top < list.bottom), text: row?.textContent.slice(0, 40)};
  }, got[0]?.action.answer);
  console.log('agent reopened', JSON.stringify(agentBack));
  if (!agentBack.open || !agentBack.found || !agentBack.inView) fails.push('agent: did not reopen on the answer');

  // --- the popup agent, kept open: nothing is posted ----------------------
  await page.evaluate(() => { localStorage.setItem(NOTIFICATIONS_KEY, '[]'); cmdPaletteAsk('And again?'); });
  await page.waitForTimeout(2600);
  got = await notes();
  if (got.length) fails.push('agent: posted while open');
  await page.evaluate(() => toggleAgentPalette());

  // --- Atlas, closed mid-answer ---------------------------------------------
  await page.evaluate(() => { localStorage.setItem(NOTIFICATIONS_KEY, '[]'); openHelpChat(); submitHelpChatQuestion('How do I make a mind map?'); });
  await page.waitForTimeout(300);
  await page.evaluate(() => document.querySelector('[data-sheet="guide"] .sheet-close')?.click());
  await page.waitForTimeout(300);
  const closed = await page.evaluate(() => !document.querySelector('[data-sheet="guide"]'));
  await page.waitForTimeout(2600);
  got = await notes();
  console.log('guide closed', closed, JSON.stringify(got));
  if (got.length !== 1 || got[0].action.panel !== 'guide') fails.push('guide: no notification');
  // Through the bell this time, the other way back.
  await page.evaluate(() => openNotifications());
  await page.waitForTimeout(300);
  await page.evaluate(() => [...document.querySelectorAll('.notif-actionable')].find((r) => /Atlas answered/.test(r.textContent))?.click());
  await page.waitForTimeout(500);
  const guideBack = await page.evaluate((id) => {
    const sheet = document.querySelector('[data-sheet="guide"]');
    const list = document.getElementById('help-chat-messages');
    const row = [...(list?.querySelectorAll('[data-answer-id]') || [])].find((el) => el.dataset.answerId === id);
    const lr = list?.getBoundingClientRect();
    const r = row?.getBoundingClientRect();
    return {open: Boolean(sheet), found: Boolean(row), inView: Boolean(r && lr && r.top >= lr.top - 1 && r.top < lr.bottom), text: row?.textContent.slice(0, 40)};
  }, got[0]?.action.answer);
  console.log('guide reopened', JSON.stringify(guideBack));
  if (!guideBack.open || !guideBack.found || !guideBack.inView) fails.push('guide: did not reopen on the answer');

  // --- Atlas, kept open --------------------------------------------------------
  await page.evaluate(() => { localStorage.setItem(NOTIFICATIONS_KEY, '[]'); submitHelpChatQuestion('And a tree?'); });
  await page.waitForTimeout(2600);
  got = await notes();
  if (got.length) fails.push('guide: posted while open');

  console.log(fails.length ? 'FAIL ' + fails.join('; ') : 'OK unwatched answers');
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})();
