// Sh2 X1 (ledger-1112): record, then reload, with Chromium's fake microphone.
// The beforeunload guard (navigation.js `recordingLive`) must ask while a
// recording is live; dismissing keeps the page and the recorder, accepting
// reloads. BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/x1reload.js
const pw = require('playwright');
const launch = pw.chromium.launch.bind(pw.chromium);
pw.chromium.launch = (opts = {}) => launch({ ...opts, args: [...(opts.args || []), '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'] });
const L = require('./lib.js');
(async () => {
  const { browser, ctx, page } = await L.boot({ viewport: { width: 1440, height: 900 } });
  await ctx.grantPermissions(['microphone']);
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  const dialogs = [];
  let mode = 'dismiss';
  page.on('dialog', async (d) => { dialogs.push(d.type()); if (mode === 'dismiss') await d.dismiss(); else await d.accept(); });
  // Control: nothing live, a reload asks nothing.
  await page.click('body');
  const idle = await page.evaluate(() => ({ live: window.meetingRecordingLive?.() ?? 'not loaded' }));
  console.log('idle', JSON.stringify(idle));
  await page.evaluate(() => openMeetingRecorder());
  await page.waitForFunction(() => document.getElementById('meeting-overlay') && !document.getElementById('meeting-overlay').classList.contains('hidden'), null, { timeout: 15000 });
  await page.fill('#meeting-title', 'X1 take');
  await page.click('#meeting-record');
  await page.waitForTimeout(4000);
  const live = await page.evaluate(async () => { const rows = await apiJson('/recordings'); const list = Array.isArray(rows) ? rows : (rows.items || rows.recordings || []); return { live: meetingRecordingLive(), id: list.length ? list[0].id : null, n: list.length, state: document.getElementById('meeting-card').dataset.state }; });
  console.log('recording', JSON.stringify(live));
  // Reload while recording: the guard asks; dismissing keeps the page and the recorder.
  mode = 'dismiss';
  await page.evaluate(() => { setTimeout(() => location.reload(), 0); });
  await page.waitForTimeout(1500);
  const kept = await page.evaluate(() => ({ live: meetingRecordingLive(), t: performance.now() > 5000 }));
  console.log('after dismiss', JSON.stringify({ dialogs, ...kept }));
  // Accept: the reload goes ahead; what the server holds of the take is what is kept.
  mode = 'accept';
  await page.evaluate(() => { setTimeout(() => location.reload(), 0); });
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(3500);
  const after = await page.evaluate(async (id) => {
    const row = await apiJson(`/recordings/${id}`).catch((e) => ({ error: e.message }));
    return { state: row.state, error: row.error, duration_ms: row.duration_ms, live: window.meetingRecordingLive?.() ?? 'not loaded' };
  }, live.id);
  console.log('after accept', JSON.stringify({ dialogs, ...after }));
  console.log('errs', JSON.stringify(errs));
  await browser.close();
})();
