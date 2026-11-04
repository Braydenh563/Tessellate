// INBOX 1646: a long tray item ends in an ellipsis. Measures span.ph-text in .obj-tray-use.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1000, height: 700 } });
  const r = await page.evaluate(() => {
    const b = document.createElement('button');
    b.className = 'ghost quiet obj-tray-use';
    setLabel(b, 'ph:note Played a game of golf for 18 holes at Windarra with a very long title that will not fit');
    const li = document.createElement('li'); li.className = 'obj-tray-item'; li.style.width = '300px';
    li.append(b); document.body.append(li);
    const t = b.querySelector('.ph-text'); const cs = getComputedStyle(t);
    return { textOverflow: cs.textOverflow, overflow: cs.overflowX, whiteSpace: cs.whiteSpace, clipped: t.scrollWidth > t.clientWidth, spanW: t.clientWidth, btnW: b.clientWidth };
  });
  console.log(JSON.stringify(r));
  await browser.close();
})();
