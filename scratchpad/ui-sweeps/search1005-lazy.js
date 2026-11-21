// Every lazy bundle that search-boot-1005 moved boot code into loads before its
// first use, with no console error and no page error. Per bundle: the moved
// names are NOT real functions at boot (so the move happened), the bundle's own
// entry gesture loads it, and then the names are functions and one of them runs.
//   settingsControls (Settings window), appPalette (Ctrl+K), lightbox
//   (highlightCodeInto), library bundle (showDetailDialog, calloutMenuItems,
//   pickNotesDialog, addBoardToNote), chordGuide (the "m" chord).
//   BASE=http://127.0.0.1:8811 SCRATCH=/tmp/x [W=390] [THEME=dark] node search1005-lazy.js
//
// FIRST=1 is the other half (qa-1005, step 3): every lazily loaded feature
// works on its FIRST gesture, made within 500ms of the shell appearing, which
// is before app.js's three-second preload (`quickNote`, `fieldClear`,
// `chordGuide`, `notePanels`, `dragEdge`) has fetched anything. One fresh
// browser per feature, so no feature rides on another's load. Per feature it
// prints when the gesture landed (ms after the shell), whether the bundle had
// been asked for before it, and whether the gesture did its thing.
//   BASE=... FIRST=1 [W=390] [THEME=dark] [ONLY=edit] node search1005-lazy.js
const { boot, PW } = require('./lib.js');
if (process.env.FIRST) { firstUse(); return; }

async function firstUse() {
  const { chromium } = require('playwright');
  const BASE = process.env.BASE || 'http://127.0.0.1:8781';
  const width = Number(process.env.W || 1440);
  const phone = width < 600;
  const browser = await chromium.launch();
  const FEATURES = {
    // The note edit form (notePanels: note-panels.js, note-edit-panels.js).
    edit: {
      bundle: 'notePanels',
      files: ['note-panels.js', 'note-edit-panels.js'],
      async gesture(page) {
        await page.click('[data-tab="notes"]');
        //: A phone opens the note as a page first, and its Edit is there.
        if (phone) {
          await page.locator('#entry-list > li .entry-content').first().click({ timeout: 10000 });
          await page.locator('.note-page-bar button[aria-label="Edit this entry"]').first().click({ timeout: 10000 });
          return;
        }
        const button = page.locator('#entry-list > li button[aria-label="Edit this entry"]').first();
        await button.click({ force: true, timeout: 4000 });
      },
      //: The caret in the body (WCAG 2.4.3), as on every later edit.
      result: () => {
        const box = document.getElementById('entry-edit-content');
        const focused = document.activeElement?.id || document.activeElement?.tagName || '';
        return { ok: Boolean(box && box.getBoundingClientRect().height > 0 && box.closest('li')) && focused === 'entry-edit-content', focused };
      },
    },
    // The companion's menu (companion-menu.js), by a right-click on its face.
    companion: {
      bundle: 'companionMenu',
      files: ['companion-menu.js'],
      skip: phone,
      async gesture(page) {
        //: The face mounts at the corner and is placed a beat later, under
        //: the top bar until then: clicked at the first moment a pointer
        //: could actually reach it (its middle is the face itself).
        const face = await (await page.waitForFunction(() => {
          const f = document.querySelector('#nm-buddy .nm-buddy-face');
          if (!f) return false;
          const r = f.getBoundingClientRect();
          const p = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
          return f.contains(document.elementFromPoint(p.x, p.y)) ? p : false;
        }, null, { timeout: 4000, polling: 20 })).jsonValue();
        await page.mouse.click(face.x, face.y, { button: 'right' });
      },
      result: () => ({ ok: Boolean(typeof nmb === 'object' && nmb.menu && nmb.menu.isConnected && !nmb.menu.classList.contains('hidden') && nmb.menu.getBoundingClientRect().height > 0) }),
    },
    // A held drag-selection near the bottom of the note list scrolls it (drag-edge.js).
    dragEdge: {
      bundle: 'dragEdge',
      files: ['drag-edge.js'],
      skip: phone,
      async gesture(page) {
        await page.click('[data-tab="notes"]');
        await page.waitForSelector('#entry-list > li .entry-content, #entry-list > li', { timeout: 4000 });
        const at = await page.evaluate(() => {
          let el = document.querySelector('#entry-list');
          while (el && el !== document.documentElement && !(/auto|scroll/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight)) el = el.parentElement;
          window.__dragScroller = el;
          window.__dragTop = el.scrollTop;
          const box = el.getBoundingClientRect();
          const text = [...document.querySelectorAll('#entry-list > li p, #entry-list > li .entry-content')].find((p) => { const b = p.getBoundingClientRect(); return b.top > box.top + 10 && b.bottom < box.top + 300 && b.width > 40; });
          const b = text.getBoundingClientRect();
          return { x: b.left + 8, y: b.top + 6, edge: Math.min(box.bottom, innerHeight) - 30 };
        });
        await page.mouse.move(at.x, at.y);
        await page.mouse.down();
        await page.mouse.move(at.x + 40, at.edge, { steps: 6 });
        //: Held still at the edge past the slowed file's arrival: no move
        //: after it lands, which is the hand that rests there.
        await page.waitForTimeout(900 + Number(process.env.SLOW ?? 1500));
        await page.mouse.up();
      },
      result: () => ({ ok: window.__dragScroller.scrollTop - window.__dragTop > 40, scrolled: window.__dragScroller.scrollTop - window.__dragTop }),
    },
    // The "m" chord's guide (chord-guide.js).
    chord: {
      bundle: 'chordGuide',
      files: ['chord-guide.js'],
      async gesture(page) {
        await page.evaluate(() => document.activeElement?.blur?.());
        await page.keyboard.press('m');
      },
      result: () => { const el = document.getElementById('chord-guide'); return { ok: Boolean(el) && !el.classList.contains('hidden') && el.querySelectorAll('.chord-guide-row').length === 12 }; },
    },
    // Four more doors a person reaches in the first seconds: Ctrl+K, the
    // status bar's Guide, a note card's category chip, and Manage categories.
    palette: {
      bundle: 'appPalette',
      files: ['app-palette.js'],
      async gesture(page) {
        await page.evaluate(() => document.activeElement?.blur?.());
        await page.keyboard.press('Control+k');
      },
      result: () => { const o = document.getElementById('palette-overlay'); return { ok: Boolean(o && !o.classList.contains('hidden') && document.querySelectorAll('#palette-list > *').length > 0) }; },
    },
    guide: {
      bundle: 'helpChat',
      files: ['help-chat.js'],
      async gesture(page) {
        if (phone) await page.evaluate(() => openHelpChat());
        else await page.click('#status-guide');
      },
      result: () => { const i = document.getElementById('help-chat-input'); return { ok: Boolean(i && i.getBoundingClientRect().height > 0) }; },
    },
    categoryChip: {
      bundle: 'chipMenus',
      files: ['chip-menus.js'],
      async gesture(page) {
        await page.click('[data-tab="notes"]');
        await page.locator('#entry-list > li .chip-interactive[aria-haspopup="menu"]').first().click({ timeout: 4000 });
      },
      result: () => ({ ok: [...document.querySelectorAll('[role="menu"]')].some((m) => !m.closest('.hidden') && m.getBoundingClientRect().height > 20) }),
    },
    categories: {
      bundle: 'categories',
      files: ['categories-panel.js'],
      async gesture(page) {
        if (phone) await page.evaluate(() => openManageCategories());
        else { await page.click('[data-tab="notes"]'); await page.click('#manage-categories-btn', { timeout: 4000 }); }
      },
      result: () => ({ ok: [...document.querySelectorAll('.modal-overlay:not(.hidden), .sheet-overlay:not(.hidden), dialog[open]')].some((d) => /categor/i.test(d.textContent) && d.getBoundingClientRect().height > 50) }),
    },
    // The Settings window's handlers (settings-controls.js): the gear, the
    // Data pane, then Find duplicates, whose handler that file binds.
    settings: {
      bundle: 'settingsControls',
      files: ['settings-controls.js'],
      async gesture(page) {
        if (phone) await page.evaluate(() => openSettingsModal());
        else await page.click('#settings-btn');
        await page.waitForSelector('#settings-modal:not(.hidden), .settings-modal:not(.hidden)', { timeout: 6000 }).catch(() => {});
        await page.evaluate(() => openSettingsModal('data'));
        await page.waitForSelector('#find-duplicates', { state: 'visible', timeout: 6000 });
        await page.click('#find-duplicates');
      },
      result: () => ({ ok: (document.getElementById('duplicate-status')?.textContent || '').trim().length > 0, text: (document.getElementById('duplicate-status')?.textContent || '').trim().slice(0, 60) }),
    },
  };
  let failed = 0;
  for (const [name, f] of Object.entries(FEATURES)) {
    if (process.env.ONLY && process.env.ONLY !== name) continue;
    if (f.skip) { console.log(`skip ${name} at ${width} (no mouse gesture on a phone)`); continue; }
    const ctx = await browser.newContext({ viewport: { width, height: phone ? 844 : 900 }, hasTouch: phone, isMobile: phone });
    await ctx.addInitScript((t) => {
      try {
        localStorage.setItem('theme', t.theme);
        localStorage.setItem('onboardingDone', '1');
        localStorage.setItem('tourDone', '1');
        localStorage.setItem('nm-buddy-hint', 'done');
        //: The companion is off on a fresh profile; its feature turns it on.
        if (t.buddy) localStorage.setItem('avatar-buddy', 'atlas');
      } catch (e) {}
    }, { theme: process.env.THEME || 'light', buddy: name === 'companion' });
    //: The bundle's files arrive SLOW ms late (default 1500), so the gesture
    //: always meets the stand-in, never a file the preload or a fast disk
    //: happened to fetch first: the path a slow machine takes every time.
    const SLOW = Number(process.env.SLOW ?? 1500);
    for (const file of f.files) {
      await ctx.route(`**/js/${file}*`, async (route) => { await new Promise((r) => setTimeout(r, SLOW)); await route.continue(); });
    }
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
    page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160)); });
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 }).catch(() => {});
    if (await page.isVisible('#lock-password')) { await page.fill('#lock-password', PW); await page.click('#lock-submit'); }
    //: Whether the bundle was already asked for is read in the same poll
    //: that sees the shell, so no extra round trip (over a second each on a
    //: loaded machine) sits between the shell and the gesture.
    const before = await (await page.waitForFunction((b) => {
      const overlay = document.getElementById('lock-overlay');
      const up = !document.documentElement.classList.contains('shell-curtain') && (!overlay || overlay.classList.contains('hidden')) && typeof ensureModule === 'function';
      return up ? { asked: lazyModuleLoads.has(b) } : false;
    }, f.bundle, { timeout: 20000, polling: 20 })).jsonValue().then((v) => v.asked);
    const t0 = Date.now();
    let gestureError = '';
    const gestureStart = Date.now() - t0;
    try { await f.gesture(page); } catch (e) {
      gestureError = e.message.split('\n')[0];
      //: What sat over the notes tab when a click could not land.
      gestureError += ' over the notes tab: ' + await page.evaluate(() => { const t = document.querySelector('[data-tab="notes"]'); if (!t) return 'no tab'; const b = t.getBoundingClientRect(); const at = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return at ? (at.id || at.className || at.tagName) : 'nothing'; }).catch(() => '?');
    }
    const landed = Date.now() - t0;
    let res = { ok: false };
    for (let i = 0; i < 30; i++) {
      res = await page.evaluate(f.result).catch((e) => ({ ok: false, err: e.message }));
      if (res.ok) break;
      await page.waitForTimeout(100);
    }
    const ok = res.ok && !gestureError && errors.length === 0 && gestureStart <= 500;
    if (!ok) failed += 1;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}: gesture began ${gestureStart}ms, done ${landed}ms after the shell; bundle asked for before it: ${before}; result ${JSON.stringify(res)}${gestureError ? ' gesture error: ' + gestureError : ''}${errors.length ? ' errors ' + JSON.stringify(errors.slice(0, 4)) : ''}`);
    await ctx.close();
  }
  console.log(failed ? `FAIL first use at ${width}: ${failed}` : `PASS first use at ${width}`);
  await browser.close();
  process.exit(failed ? 1 : 0);
}

const W = Number(process.env.W || 1440);
const SETTINGS = ['runEmbeddingFallback', 'resetAllFeatureModels', 'applyChatModel', 'applyOcrModel', 'applyUtilityModel', 'applyVisionModel', 'addTemplate', 'saveRunBudget', 'saveWebSearchSettings', 'restartMemoryMap', 'findDuplicates', 'renderDuplicateGroups', 'mergeDuplicateGroup', 'saveExportSaveDir', 'addMemoryByHand', 'refreshSearxngHost', 'applyBackendChoice', 'saveModelContextWindow', 'addPersona'];
const LIBRARY = ['showDetailDialog', 'calloutMenuItems', 'pickNotesDialog', 'addBoardToNote'];

(async () => {
  const errors = [];
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 800 : 900 } });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('requestfailed', (r) => errors.push('requestfailed: ' + r.url()));
  const checks = {};
  const types = (names) => page.evaluate((ns) => Object.fromEntries(ns.map((n) => [n, typeof window[n] === 'function' ? (window[n].toString().length < 220 ? 'stand-in' : 'real') : typeof window[n]])), names);
  const allReal = (t) => Object.values(t).every((v) => v === 'real');
  const noneReal = (t) => Object.values(t).every((v) => v !== 'real');

  // --- Settings ------------------------------------------------------------
  const sBefore = await types(SETTINGS.filter((n) => n !== 'refreshSearxngHost'));
  checks['settings: handlers are not loaded at boot'] = noneReal(sBefore);
  await page.evaluate(() => openSettingsModal('websearch'));
  await page.waitForTimeout(2500);
  const sAfter = await types(SETTINGS);
  console.log('settings after', JSON.stringify(sAfter));
  checks['settings: every moved handler is real once the window is open'] = allReal(sAfter);
  await page.evaluate(() => openSettingsModal('data'));
  await page.waitForTimeout(800);
  await page.evaluate(() => document.getElementById('find-duplicates')?.click());
  await page.waitForTimeout(2500);
  const dup = await page.evaluate(() => (document.getElementById('duplicates-result')?.textContent || document.getElementById('find-duplicates')?.parentElement?.textContent || '').trim().slice(0, 80));
  console.log('find duplicates ->', JSON.stringify(dup));
  checks['settings: Find duplicates ran (some text came back)'] = dup.length > 0;
  await page.evaluate(() => {
    const box = document.getElementById('run-budget-tokens');
    if (box) { box.value = '12000'; box.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await page.waitForTimeout(800);
  await page.evaluate(() => closeSettingsModal?.());
  await page.keyboard.press('Escape');

  // --- Command palette ---------------------------------------------------------
  checks['palette: not loaded at boot'] = noneReal(await types(['notesPaletteCommands']));
  await page.evaluate(() => openPalette());
  await page.waitForSelector('#palette-overlay:not(.hidden)', { timeout: 8000 });
  await page.fill('#palette-input', '');
  await page.type('#palette-input', 'manage cat', { delay: 20 });
  await page.waitForTimeout(800);
  const pal = await page.evaluate(() => [...document.querySelectorAll('#palette-list > *')].map((e) => e.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 8));
  console.log('palette rows', JSON.stringify(pal));
  checks['palette: the notes rows draw (Manage categories)'] = pal.some((t) => /Manage categories/i.test(t));
  await page.keyboard.press('Escape');

  // --- Lightbox: the code highlighter -------------------------------------------------
  checks['lightbox: highlighter not loaded at boot'] = noneReal(await types(['highlightCodeInto', 'codeScanner']));
  await page.evaluate(() => ensureModule('lightbox'));
  const lb = await page.evaluate(() => {
    const out = document.createElement('div');
    highlightCodeInto(out, 'const x = 1; // note\nfunction f() { return "s"; }', 'a.js');
    return { spans: out.querySelectorAll('span').length, keyword: out.querySelectorAll('.tok-keyword').length, text: out.textContent.length };
  });
  console.log('highlighter', JSON.stringify(lb));
  checks['lightbox: highlightCodeInto runs and paints keywords'] = lb.keyword > 0 && lb.text > 20;

  // --- The library bundle (Library, Documents, Whiteboard) ------------------------------------
  checks['library bundle: names not loaded at boot'] = noneReal(await types(LIBRARY));
  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(3500);
  const lAfter = await types(LIBRARY);
  console.log('library after', JSON.stringify(lAfter));
  checks['library bundle: every moved name is real once the tab is open'] = allReal(lAfter);
  const detail = await page.evaluate(() => {
    showDetailDialog('Lazy sweep', 'The whole record.');
    const ok = [...document.querySelectorAll('.confirm-card, .dialog, [role=dialog]')].some((d) => /The whole record/.test(d.textContent));
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return ok;
  });
  checks['library bundle: showDetailDialog shows the text'] = detail;
  await page.evaluate(async () => { await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'A note for the picker, lazy sweep' }) }); });
  const picker = await page.evaluate(async () => {
    const p = pickNotesDialog('Which notes?', { confirmLabel: 'Go' });
    await new Promise((r) => setTimeout(r, 1200));
    const rows = document.querySelectorAll('.note-picker-list li, .note-picker-list .note-picker-row, .entry-pick-list > *').length;
    const cancel = [...document.querySelectorAll('button')].find((b) => /^\s*(Cancel|Close)/i.test(b.textContent));
    cancel?.click();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await Promise.race([p, new Promise((r) => setTimeout(r, 1000))]);
    return rows;
  });
  console.log('notes picker rows', picker);
  checks['library bundle: pickNotesDialog lists notes'] = picker > 0;
  const callout = await page.evaluate(() => { try { return calloutMenuItems('note', false, () => {}).length; } catch (e) { return 'ERR ' + e.message; } });
  console.log('callout items', callout);
  checks['library bundle: calloutMenuItems returns menu items'] = typeof callout === 'number' && callout > 0;

  // --- The "m" chord --------------------------------------------------------------------------
  await page.waitForTimeout(3500);
  await page.evaluate(() => { document.activeElement?.blur?.(); });
  await page.keyboard.press('m');
  await page.waitForTimeout(400);
  const guide = await page.evaluate(() => {
    const el = document.getElementById('chord-guide');
    return { shown: Boolean(el) && !el.classList.contains('hidden'), rows: el ? el.querySelectorAll('.chord-guide-row').length : 0 };
  });
  console.log('chord guide', JSON.stringify(guide));
  checks['chord: m draws the 12-row guide'] = guide.shown && guide.rows === 12;

  checks['zero console / page errors'] = errors.length === 0;
  if (errors.length) console.log('ERRORS', JSON.stringify(errors.slice(0, 8)));
  let ok = true;
  for (const [name, pass] of Object.entries(checks)) { console.log(pass ? 'ok  ' : 'FAIL', name); ok = ok && pass; }
  console.log(ok ? `PASS at ${W}` : `FAIL at ${W}`);
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
