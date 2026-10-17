// New chat page: when do the mark and the heading paint, and does anything move
// when the starters arrive? (BACKLOG "New chat page", ui-1017b.)
//
// A frame-by-frame sample from the moment the new chat is asked for: the
// card's opacity, the heading's and the mark's boxes, the skeleton pills, the
// starter chips. DELAY=ms holds /chat/suggestions that long (a slow disk);
// the owner's "a second or two late" is the DELAY=1200 row.
//   BASE=http://127.0.0.1:8791 DELAY=1200 W=1440 node chatemptypaint.js
const { boot } = require('./lib.js');
(async () => {
  const delay = Number(process.env.DELAY || 0);
  const { browser, ctx, page } = await boot({ serviceWorkers: 'block', viewport: { width: Number(process.env.W || 1440), height: 900 } });
  if (delay) {
    await ctx.route('**/chat/suggestions', async (route) => {
      await new Promise((r) => setTimeout(r, delay));
      await route.continue();
    });
  }
  // COLD=1 (default): the session's first visit to Chat. COLD=0: a return.
  if (process.env.COLD === '0') {
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(2500);
    await page.evaluate(() => switchTab('dashboard'));
  }
  await page.waitForTimeout(800);
  if (process.env.NEW === '1') {
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(2500);
    await page.evaluate(() => { window.__newChat = true; });
  }
  const result = await page.evaluate(() => new Promise((resolve) => {
    const samples = [];
    const t0 = performance.now();
    const read = () => {
      const card = document.querySelector('#chat-messages .chat-empty');
      const title = card?.querySelector('.empty-title');
      const emblem = card?.querySelector('#chat-empty-emblem');
      const rect = (el) => { const r = el?.getBoundingClientRect(); return r ? [Math.round(r.top * 10) / 10, Math.round(r.height * 10) / 10] : null; };
      return {
        t: Math.round(performance.now() - t0),
        card: !!card,
        opacity: card ? Number(getComputedStyle(card).opacity) : null,
        title: rect(title),
        titleVisible: !!title && Number(getComputedStyle(card).opacity) > 0.99,
        emblem: rect(emblem),
        cardH: rect(card)?.[1] ?? null,
        pills: card ? card.querySelectorAll('.skeleton').length : 0,
        chips: card ? card.querySelectorAll('#chat-suggest > .chip').length : 0,
        link: card ? getComputedStyle(card.querySelector('.help-atlas') || card).visibility : null,
      };
    };
    const tick = () => {
      samples.push(read());
      if (performance.now() - t0 < 3500) requestAnimationFrame(tick);
      else resolve(samples);
    };
    if (window.__newChat) newChatConversation(); else switchTab('chat');
    requestAnimationFrame(tick);
  }));
  const first = (f) => result.find(f)?.t ?? null;
  const last = result[result.length - 1];
  const titleTops = result.filter((s) => s.title).map((s) => s.title[0]);
  const heights = result.filter((s) => s.cardH != null).map((s) => s.cardH);
  console.log(JSON.stringify({
    delay,
    firstCard: first((s) => s.card),
    firstTitleVisible: first((s) => s.titleVisible),
    firstSkeleton: first((s) => s.pills > 0),
    firstChips: first((s) => s.chips > 0),
    titleTopMin: Math.min(...titleTops), titleTopMax: Math.max(...titleTops),
    cardHFirst: heights[0], cardHLast: heights[heights.length - 1], cardHMin: Math.min(...heights), cardHMax: Math.max(...heights),
    final: { chips: last.chips, pills: last.pills, opacity: last.opacity },
  }, null, 1));
  await browser.close();
})();
