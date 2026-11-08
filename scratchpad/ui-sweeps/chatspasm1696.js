// INBOX 1696: "sending a message to the chat still causes it to spasm up and
// down really fast". Records, per animation frame for ~3s after Send, the
// composer height, the chat scroller's scrollTop/scrollHeight and the top of
// the last message and of the composer, then counts direction reversals
// (a sample whose move is opposite in sign to the previous non-zero move)
// and the px amplitude. Also long tasks / LoAF with the script that ran.
//   BASE=http://127.0.0.1:8795 FAKE=http://127.0.0.1:8796/v1 CPU=4 PRE=3 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node chatspasm1696.js
const { boot } = require('./lib.js');
const FAKE = process.env.FAKE || 'http://127.0.0.1:8796/v1';
const CPU = Number(process.env.CPU || 4);
const PRE = Number(process.env.PRE || 3);

(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async (base) => {
    await api('/models/provider', { method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: base }) });
    await api('/models/chat-model', { method: 'POST', body: JSON.stringify({ name: 'fake-answerer' }) }).catch(() => null);
    for (let i = 0; i < 4; i += 1) await api('/entries', { method: 'POST', body: JSON.stringify({ content: `Sprint note ${i}: the board has three columns, backlog, doing and review, and the team moves cards across during the week.`, category: 'General' }) });
  }, FAKE);
  if (process.env.BUDDY) {
    await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'always'; prefs.set('avatar-buddy', 'atlas'); });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    console.log('buddy', await page.evaluate(() => !!document.getElementById('nm-buddy')));
  }
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(1500);
  await page.evaluate(() => newChatConversation());
  await page.waitForTimeout(500);
  const dlg = await page.evaluate(() => [...document.querySelectorAll('.confirm-overlay')].map((o) => o.textContent.slice(0, 200)));
  if (dlg.length) console.log('DIALOG', dlg);
  // Prior turns so the scroller overflows (the owner's chats are long).
  for (let i = 0; i < PRE; i += 1) {
    await page.click('#chat-input');
    await page.keyboard.type(`Earlier question ${i} about the sprint board columns`);
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => !chatController, null, { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(600);
  }
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU });
  await page.evaluate(() => {
    window.__f = []; window.__lt = [];
    const pane = document.getElementById('chat-messages');
    const box = document.getElementById('chat-input');
    window.__t0 = performance.now();
    try {
      new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push({ type: e.entryType, at: Math.round(e.startTime - window.__t0), dur: Math.round(e.duration), scripts: (e.scripts || []).map((s) => `${s.sourceFunctionName || s.invoker}@${(s.sourceURL || '').split('/').pop()}:${s.sourceCharPosition} ${Math.round(s.duration)}ms forced ${Math.round(s.forcedStyleAndLayoutDuration || 0)}`) }); }).observe({ entryTypes: ['long-animation-frame', 'longtask'] });
    } catch (e) {}
    const tick = () => {
      const msgs = pane.querySelectorAll('.msg');
      const last = msgs[msgs.length - 1];
      window.__f.push({
        t: Math.round(performance.now() - window.__t0), inH: box.offsetHeight, top: Math.round(pane.scrollTop * 10) / 10, sh: pane.scrollHeight, ch: pane.clientHeight,
        lastTop: last ? Math.round(last.getBoundingClientRect().top * 10) / 10 : null, lastBot: last ? Math.round(last.getBoundingClientRect().bottom * 10) / 10 : null,
        boxTop: Math.round(box.getBoundingClientRect().top * 10) / 10,
      });
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  await page.click('#chat-input');
  await page.keyboard.type('What columns does the sprint board have');
  await page.evaluate(() => { window.__f.length = 0; window.__t0 = performance.now(); window.__lt.length = 0; });
  await page.keyboard.press('Enter');
  await page.waitForTimeout(Number(process.env.MS || 3500));
  const r = await page.evaluate(() => ({ f: window.__f, lt: window.__lt }));
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  const rev = (key) => {
    let prev = 0, n = 0, amp = 0, min = Infinity, max = -Infinity;
    for (let i = 1; i < r.f.length; i += 1) {
      const a = r.f[i][key], b = r.f[i - 1][key];
      if (a == null || b == null) continue;
      const d = a - b;
      min = Math.min(min, a); max = Math.max(max, a);
      if (Math.abs(d) < 0.5) continue;
      if (prev && Math.sign(d) !== Math.sign(prev)) { n += 1; amp = Math.max(amp, Math.abs(d)); }
      prev = d;
    }
    return { reversals: n, maxStepAtReversal: Math.round(amp), range: Math.round(max - min) };
  };
  const out = {};
  for (const k of ['inH', 'top', 'sh', 'lastTop', 'boxTop']) out[k] = rev(k);
  console.log('frames', r.f.length, 'cpu', CPU);
  console.log('reversals', JSON.stringify(out));
  const loaf = r.lt.filter((e) => e.type === 'long-animation-frame');
  const tempo = loaf.filter((e) => e.scripts.some((x) => /nameMarkBuddyTempo/.test(x)));
  console.log('SUMMARY loaf', loaf.length, 'max', Math.max(0, ...loaf.map((e) => e.dur)), 'sum', loaf.reduce((a, e) => a + e.dur, 0), 'tempoFrames', tempo.length, 'tempoMax', Math.max(0, ...tempo.map((e) => e.dur)));
  console.log('long', JSON.stringify(r.lt.filter((e) => e.dur >= 80), null, 1));
  if (process.env.DUMP) console.log(r.f.map((x) => JSON.stringify(x)).join('\n'));
  await browser.close();
})();
