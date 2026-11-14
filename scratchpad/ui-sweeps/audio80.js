// Brief 80 (WORLD_CLASS_PLAN 28.5 rows 1, 3 to 6): drives the recorder with
// Chromium's fake microphone. ACT=record|recover|reach|undo|library, W=1440|390.
// BASE=http://127.0.0.1:8837 node scratchpad/ui-sweeps/audio80.js
const pw = require('playwright');
const launch = pw.chromium.launch.bind(pw.chromium);
pw.chromium.launch = (opts = {}) => launch({ ...opts, args: [...(opts.args || []), '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'] });
const L = require('./lib.js');
const W = Number(process.env.W || 1440);
const ACT = process.env.ACT || 'record';
const SECS = Number(process.env.SECS || 5);

async function record(page, secs) {
  await page.evaluate(() => openMeetingRecorder());
  await page.waitForFunction(() => document.getElementById('meeting-overlay') && !document.getElementById('meeting-overlay').classList.contains('hidden'), null, { timeout: 15000 });
  await page.fill('#meeting-title', 'Sweep take');
  await page.click('#meeting-record');
  await page.waitForTimeout(secs * 1000);
}

async function stop(page) {
  await page.click('#meeting-record');
  await page.waitForFunction(() => ['saved', 'review'].includes(document.getElementById('meeting-card').dataset.state), null, { timeout: 30000 });
  return page.evaluate(() => ({ state: document.getElementById('meeting-card').dataset.state, status: document.getElementById('meeting-status').textContent }));
}

(async () => {
  const viewport = W <= 400 ? { width: W, height: 844 } : { width: W, height: 900 };
  const { browser, ctx, page } = await L.boot({ viewport, hasTouch: W <= 400, isMobile: W <= 400 });
  await ctx.grantPermissions(['microphone']);
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  if (ACT === 'record') {
    const t0 = Date.now();
    await record(page, SECS);
    const out = await stop(page);
    const list = await page.evaluate(() => apiJson('/recordings'));
    const r = list.recordings[0];
    console.log(JSON.stringify({ W, ...out, recordings: list.recordings.length, mime: r && r.mime, duration_ms: r && r.duration_ms, size: r && r.size_bytes, peaks: r && r.peaks.length, ms: Date.now() - t0 }));
  }
  if (ACT === 'recover') {
    // Row 5: record SECS (120), kill the tab with no stop, wait past the
    // server's stale window, reopen: the app says "Recording recovered".
    await record(page, SECS);
    const id = await page.evaluate(() => meetingTake.id);
    await page.close({ runBeforeUnload: false });
    await new Promise((r) => setTimeout(r, Number(process.env.STALE || 50) * 1000));
    const again = await ctx.newPage();
    await again.goto(L.BASE + '/', { waitUntil: 'domcontentloaded' });
    const toastText = await again.waitForFunction(() => [...document.querySelectorAll('.toast')].map((t) => t.textContent).find((t) => /Recording recovered/.test(t)), null, { timeout: 30000, polling: 200 }).then((h) => h.jsonValue()).catch(() => null);
    const got = await again.evaluate(async (rid) => {
      const row = await apiJson(`/recordings/${rid}`);
      const buf = await (await fetch(`/media/recordings/${rid}`, { credentials: 'same-origin' })).arrayBuffer();
      let decoded = null;
      try { decoded = (await new AudioContext().decodeAudioData(buf)).duration; } catch (e) { decoded = 'decode failed: ' + e.message; }
      return { state: row.state, recovered: row.recovered, duration_ms: row.duration_ms, bytes: buf.byteLength, decoded_s: decoded };
    }, id);
    console.log(JSON.stringify({ W, recorded_s: SECS, toast: toastText, ...got }));
  }
  if (ACT === 'library') {
    // Row 6, one measure per act: markers while recording, play, speed,
    // waveform and seek, trim (a new object, the original kept), delete.
    await record(page, 2);
    await page.click('#meeting-marker');
    await page.waitForTimeout(1200);
    await page.keyboard.press('m');
    await page.waitForTimeout(1200);
    const out = await stop(page);
    await page.evaluate(() => closeMeetingRecorder());
    await page.evaluate(() => openRecordings());
    await page.waitForSelector('#recordings-list .recording-row', { timeout: 15000 });
    const row = '#recordings-list .recording-row';
    const facts = await page.$eval(row, (r) => r.querySelector('.recording-facts').textContent);
    const markers = await page.$$eval(`${row}:first-child .recording-markers button`, (b) => b.length);
    await page.click(`${row}:first-child .recording-play`);
    await page.waitForTimeout(800);
    const playing = await page.$eval(`${row}:first-child audio`, (a) => ({ paused: a.paused, t: a.currentTime }));
    await page.$eval(`${row}:first-child select.recording-speed`, (s) => { s.value = '2'; s.dispatchEvent(new Event('change')); });
    const rate = await page.$eval(`${row}:first-child audio`, (a) => a.playbackRate);
    const wave = await page.$eval(`${row}:first-child canvas.recording-wave`, (c) => { const b = c.getBoundingClientRect(); return { w: Math.round(b.width), h: Math.round(b.height), backing: c.width }; });
    const box = await page.$eval(`${row}:first-child canvas.recording-wave`, (c) => c.getBoundingClientRect().toJSON());
    await page.$eval(`${row}:first-child audio`, (a) => a.pause());
    const hit = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.className, { x: box.x + box.width * 0.5, y: box.y + box.height / 2 });
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height / 2);
    await page.waitForTimeout(300);
    const seeked = await page.$eval(`${row}:first-child audio`, (a) => ({ t: a.currentTime, d: a.duration, want: a.duration / 2 }));
    seeked.hit = hit;
    const before = await page.$$eval(row, (r) => r.length);
    await page.evaluate(() => { const r = document.querySelector('#recordings-list .recording-row'); const id = Number(r.dataset.recordingId); return apiJson(`/recordings/${id}`).then(openRecordingTrim); });
    await page.waitForSelector('#recording-trim-save');
    await page.$eval('#recording-trim-start', (i) => { i.value = '1000'; i.dispatchEvent(new Event('input')); });
    await page.click('#recording-trim-save');
    await page.waitForFunction((n) => document.querySelectorAll('#recordings-list .recording-row').length === n + 1, before, { timeout: 20000 }).catch(() => {});
    const afterTrim = await page.evaluate(() => apiJson('/recordings').then((b) => b.recordings.map((r) => ({ id: r.id, mime: r.mime, ms: r.duration_ms, src: r.source_id }))));
    const overflow = await page.evaluate(() => ({ page: document.documentElement.scrollWidth - document.documentElement.clientWidth, rows: [...document.querySelectorAll('#recordings-list .recording-row')].filter((r) => r.scrollWidth > r.clientWidth + 1).length }));
    const first = afterTrim[0].id;
    await page.evaluate((id) => apiJson(`/recordings/${id}`).then(binRecording), first);
    await page.waitForTimeout(800);
    const afterDelete = await page.$$eval(row, (r) => r.length);
    console.log(JSON.stringify({ W, out: out.state, facts, markers, playing, rate, wave, seeked, before, afterTrim: afterTrim.slice(0, 2), overflow, afterDelete }));
  }
  if (ACT === 'undo') {
    // Row 4: the five meeting acts with no undo, each pressed, then Undo
    // (performUndo, the undo bar's own), then checked reverted. Summarise,
    // the sixth, needs a model and had undo already. The transcript saves
    // are driven from the review state with typed text (no add-on here).
    const top = () => page.evaluate(() => (undoStack[undoStack.length - 1] || {}).label || null);
    const results = {};
    // 1. create
    await page.evaluate(() => openNewMeeting());
    await page.waitForSelector('#meeting-new-title');
    await page.fill('#meeting-new-title', 'Undo sweep sync');
    await page.click('#meeting-new-create');
    await page.waitForTimeout(1500);
    const label1 = await top();
    const made = await page.evaluate(() => apiJson('/meetings?limit=1').catch(() => null));
    const id = await page.evaluate(() => (allEntries.find((e) => /Undo sweep sync/.test(e.content || '')) || {}).id);
    await page.evaluate(() => performUndo());
    await page.waitForTimeout(800);
    results.create = { label: label1, binned: await page.evaluate((i) => apiJson(`/entries/${i}`).then((e) => e.is_deleted).catch(() => 'gone'), id) };
    await page.evaluate((i) => apiJson(`/entries/${i}/restore`, { method: 'POST' }), id);
    // 2. remind: an action item with a date
    await page.evaluate((i) => apiJson(`/entries/${i}/meeting/append`, { method: 'POST', body: JSON.stringify({ section: 'Action items', lines: ['- [ ] Send the deck by Friday'] }) }), id);
    await page.evaluate((i) => openMeetingSheet(i), id);
    await page.waitForSelector('.meeting-remind');
    await page.click('.meeting-remind');
    await page.waitForTimeout(1200);
    const label2 = await top();
    const rid = await page.evaluate(() => apiJson('/reminders').then((b) => (Array.isArray(b) ? b : b.reminders || b.items || []).find((r) => /deck/.test(r.text)).id));
    await page.evaluate(() => performUndo());
    await page.waitForTimeout(800);
    results.remind = { label: label2, listed: await page.evaluate((r) => apiJson('/reminders').then((b) => (Array.isArray(b) ? b : b.reminders || b.items || []).some((x) => x.id === r)), rid) };
    await L.closeOverlays?.(page);
    await page.keyboard.press('Escape');
    // 3, 4, 5: the recorder's three saves, from the review state
    const review = async (into) => {
      await page.evaluate((i) => (i ? meetingRecordInto(i) : openMeetingRecorder()), into);
      await page.waitForTimeout(300);
      await page.evaluate(() => { $('meeting-transcript').value = 'We agreed to ship on Monday.'; setMeetingState('review'); });
    };
    await review(id);
    const beforeContent = await page.evaluate((i) => apiJson(`/entries/${i}`).then((e) => e.content), id);
    await page.click('#meeting-save');
    await page.waitForTimeout(1500);
    const label3 = await top();
    await page.evaluate(() => performUndo());
    await page.waitForTimeout(800);
    results.saveInto = { label: label3, restored: await page.evaluate((i) => apiJson(`/entries/${i}`).then((e) => e.content), id) === beforeContent };
    await review(null);
    await page.click('#meeting-save');
    await page.waitForTimeout(1500);
    const label4 = await top();
    const newId = await page.evaluate(() => Math.max(...allEntries.map((e) => e.id)));
    await page.evaluate(() => performUndo());
    await page.waitForTimeout(800);
    results.saveAsNote = { label: label4, binned: await page.evaluate((i) => apiJson(`/entries/${i}`).then((e) => e.is_deleted).catch(() => 'gone'), newId) };
    await review(null);
    await page.click('#meeting-save-doc');
    await page.waitForTimeout(2000);
    const label5 = await top();
    const docs = await page.evaluate(() => apiJson('/documents').then((b) => (Array.isArray(b) ? b : b.documents || b.items || []).length));
    // On the Documents tab Ctrl+Z is the editor's; the app's entry is the toast's Undo.
    await page.evaluate(() => [...document.querySelectorAll('.toast')].find((t) => /to your documents/.test(t.textContent)).querySelector('.toast-action').click());
    await page.waitForTimeout(800);
    await page.waitForTimeout(800);
    results.saveAsDoc = { label: label5, docsBefore: docs, docsAfter: await page.evaluate(() => apiJson('/documents').then((b) => (Array.isArray(b) ? b : b.documents || b.items || []).length)) };
    const ok = [results.create.binned !== false, results.remind.listed === false, results.saveInto.restored, results.saveAsNote.binned !== false, results.saveAsDoc.docsAfter === results.saveAsDoc.docsBefore - 1].filter(Boolean).length;
    console.log(JSON.stringify({ W, results, undone: `${ok + 1}/6 (Summarise had undo)` }));
  }
  if (ACT === 'reach') {
    // Row 3: each Audio entry one press from the palette (after Ctrl+K) and
    // one click as a Quick access tile on the dashboard.
    const DEST = {
      'New meeting': () => !!document.querySelector('[data-sheet="new-meeting"]'),
      'Record a meeting or lecture': () => !document.getElementById('meeting-overlay').classList.contains('hidden') && !document.getElementById('meeting-overlay').classList.contains('voice-note'),
      'Voice note': () => document.getElementById('meeting-overlay').classList.contains('voice-note') && !document.getElementById('meeting-overlay').classList.contains('hidden'),
      'Dictate a note': () => !!document.getElementById('mic-note')?.offsetParent,
      'Recordings': () => !document.getElementById('library-view-recordings').classList.contains('hidden') && !!document.getElementById('library-view-recordings').offsetParent,
    };
    const home = async () => { await page.keyboard.press('Escape'); await page.keyboard.press('Escape'); await page.evaluate(() => { closeMeetingRecorder?.(); document.querySelectorAll('.sheet-overlay').forEach((o) => o.remove()); switchTab('dashboard'); }).catch(() => {}); await page.waitForTimeout(700); };
    const out = {};
    for (const [name, check] of Object.entries(DEST)) {
      await home();
      await page.keyboard.press('Control+k');
      await page.waitForSelector('#palette-input');
      await page.fill('#palette-input', name);
      await page.waitForTimeout(400);
      const first = await page.evaluate(() => (document.querySelector('#palette-list [aria-selected="true"], #palette-list .active, #palette-list li') || {}).textContent || '');
      await page.keyboard.press('Enter');
      await page.waitForTimeout(1500);
      out[name] = { palette: await page.evaluate(check), firstRow: first.trim().slice(0, 40) };
    }
    const ids = { 'New meeting': 'reveal:meeting-new', 'Record a meeting or lecture': 'reveal:meeting', 'Voice note': 'reveal:voice-note', 'Dictate a note': 'reveal:notes-dictation', 'Recordings': 'reveal:recordings' };
    await home();
    await page.evaluate((list) => saveQuickAccess(list).then(() => renderQuickLinks()), Object.values(ids));
    for (const [name, check] of Object.entries(DEST)) {
      await home();
      const label = await page.evaluate((n) => { const b = [...document.querySelectorAll('#dash-quicklinks .quick-link')].find((x) => (x.querySelector('.quick-link-label') || x).textContent.trim().startsWith(n.split(' or ')[0])); if (b) b.setAttribute('data-probe', '1'); return b ? b.textContent.trim().slice(0, 30) : null; }, name);
      if (label) await page.click('[data-probe="1"]');
      await page.waitForTimeout(1500);
      out[name].tile = label ? await page.evaluate(check) : 'no tile';
      await page.evaluate(() => document.querySelectorAll('[data-probe]').forEach((e) => e.removeAttribute('data-probe')));
    }
    await page.evaluate(() => saveQuickAccess([]));
    console.log(JSON.stringify({ W, reach: out }));
  }
  console.log('pageerrors', errors.length, errors.slice(0, 3));
  await browser.close();
})();
