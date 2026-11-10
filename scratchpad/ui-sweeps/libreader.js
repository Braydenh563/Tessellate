// The Library's reader (the OCR workspace) on a phone: UI_MODERNISATION_PLAN
// Phase 11 item 5, "the reader full-screen with a bottom bar".
//
// The reader is a three-pane dialog sized to the viewport: which page, the
// page, and what it says. On a phone the three do not fit beside each other,
// so this measures whether it is the page variant of the sheet recipe (the
// whole screen, no rounded top, a back chevron, the surface's own actions in
// a `.thumb-bar`) the way the note page is, and whether anything is under the
// 44px floor or scrolls sideways.
//
//   BASE=http://127.0.0.1:8994 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     NODE_PATH=/opt/node22/lib/node_modules node scratchpad/ui-sweeps/libreader.js
//
// WIDTH/HEIGHT to move it; 1024 is the desktop check that nothing moved there.
const { boot } = require('./lib.js');

const WIDTH = Number(process.env.WIDTH || 390);
const HEIGHT = Number(process.env.HEIGHT || 844);
const PHONE = WIDTH < 600;

const findings = [];
const check = (ok, what) => { if (!ok) findings.push(what); return ok; };

// A 2x3 PNG, enough for the reader to have a raster to show. Written by hand
// rather than read off disk so this probe needs nothing beside it.
const PNG_B64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAYAAAC56t6BAAAAFUlEQVR4nGP8//8/AzJgYkAD' +
  'IxcAAP//BoUBApDqRMIAAAAASUVORK5CYII=';

(async () => {
  const { page, browser } = await boot({
    viewport: { width: WIDTH, height: HEIGHT },
    hasTouch: PHONE,
    isMobile: PHONE,
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2000);

  // A picture in the notebook, so the reader has something to open.
  const uploaded = await page.evaluate(async (b64) => {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const form = new FormData();
    form.append('file', new File([bytes], 'reader-probe.png', { type: 'image/png' }));
    // Headers replaced, not merged: `api()`'s default JSON content type would
    // be the wrong one for a FormData body, whose boundary the browser sets.
    const res = await apiJson('/media/upload', {
      method: 'POST',
      headers: { 'X-Auth-Token': authToken() },
      body: form,
    }).catch((e) => ({ error: String(e) }));
    return res;
  }, PNG_B64);
  console.log('upload', JSON.stringify(uploaded).slice(0, 200));

  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(1200);
  const opened = await page.evaluate(() => openPageReader());
  await page.waitForTimeout(2500);
  check(opened !== false, 'the reader would not open on the uploaded picture');

  const m = await page.evaluate((min) => {
    const card = document.querySelector('#ocr-workspace .ocr-card');
    const overlay = document.getElementById('ocr-workspace');
    if (!card || overlay.classList.contains('hidden')) return { open: false };
    const cs = getComputedStyle(card);
    const b = card.getBoundingClientRect();
    const panes = document.querySelector('.ocr-panes');
    const pcs = panes ? getComputedStyle(panes) : null;
    const box = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y) };
    };
    // Every control the reader owns that a finger has to hit, filtered by
    // touch.js's own rules so the two sweeps count the same things: the
    // deliberately unreachable natives stand behind a visible control, a
    // `.seg` is measured through its buttons, and a checkbox, radio or
    // slider is measured through the label that is its hit area.
    const visible = (e) => e.checkVisibility
      && e.checkVisibility({ visibilityProperty: true, opacityProperty: true, contentVisibilityAuto: true });
    const target = (e) => {
      const kind = (e.getAttribute('type') || '').toLowerCase();
      if (e.tagName !== 'INPUT' || !['checkbox', 'radio', 'range'].includes(kind)) return e;
      return e.closest('label') || document.querySelector(`label[for="${CSS.escape(e.id)}"]`) || e;
    };
    const controls = [...card.querySelectorAll('button, select, summary, input:not([type="hidden"]), .seg')]
      .filter(visible)
      .filter((e) => !e.closest('.dock-native-hidden, .visually-hidden, .sr-only'))
      .filter((e) => !e.classList.contains('seg'))
      .map(target);
    const small = [...new Set(controls)]
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { id: el.id || el.className.toString().slice(0, 28), w: Math.round(r.width), h: Math.round(r.height) };
      })
      .filter((c) => c.w > 0 && c.h > 0 && (c.h < min || c.w < min));
    const sideways = (sel) => {
      const el = document.querySelector(sel);
      return el ? Math.round(el.scrollWidth) - Math.round(el.clientWidth) : null;
    };
    const bar = document.querySelector('#ocr-workspace .thumb-bar');
    return {
      open: true,
      card: { w: Math.round(b.width), h: Math.round(b.height), x: Math.round(b.x), y: Math.round(b.y), radius: cs.borderRadius },
      panesColumns: pcs ? pcs.gridTemplateColumns : null,
      pagePane: box('#ocr-page-pane'),
      regions: box('.ocr-regions'),
      rail: box('.ocr-rail-column'),
      toolbarOverflow: sideways('.ocr-toolbar'),
      pageOverflow: Math.round(document.documentElement.scrollWidth) - Math.round(document.documentElement.clientWidth),
      controls: controls.length,
      small,
      close: (() => { const c = document.getElementById('ocr-close'); return c ? { label: (c.getAttribute('aria-label') || c.textContent).trim(), icon: c.querySelector('i')?.className || '' } : null; })(),
      thumbBar: bar ? { shown: getComputedStyle(bar).display !== 'none', buttons: bar.querySelectorAll('button').length, bottom: Math.round(bar.getBoundingClientRect().bottom) } : null,
      footActions: [...document.querySelectorAll('.ocr-regions-foot button')].filter((b2) => b2.offsetParent !== null).map((b2) => b2.id),
    };
  }, 44);
  console.log(JSON.stringify(m, null, 1));

  if (m.open) {
    if (PHONE) {
      check(m.card.w >= WIDTH - 1, `the reader is ${m.card.w} wide in ${WIDTH}, not the whole screen`);
      check(m.card.h >= HEIGHT - 1, `the reader is ${m.card.h} tall in ${HEIGHT}, not the whole screen`);
      check(m.card.y === 0, `the reader starts at y=${m.card.y}, not the top of the screen`);
      check(/^0px/.test(m.card.radius), `the reader has a rounded top on a phone: ${m.card.radius}`);
      check(!m.small.length, `${m.small.length} reader controls under 44px: ${JSON.stringify(m.small)}`);
      check(m.thumbBar && m.thumbBar.shown, 'the reader has no .thumb-bar on a phone');
      if (m.thumbBar && m.thumbBar.shown) {
        check(m.thumbBar.bottom <= HEIGHT, `the thumb bar's bottom is ${m.thumbBar.bottom} in ${HEIGHT}`);
        check(m.thumbBar.buttons >= 3, `the thumb bar holds ${m.thumbBar.buttons} buttons`);
      }
      check(!m.rail || m.rail.w === 0, `the page rail is still ${m.rail && m.rail.w}px wide on a phone`);
      check(m.pagePane && m.pagePane.w >= WIDTH * 0.8,
        `the page pane is ${m.pagePane && m.pagePane.w} wide in ${WIDTH}: the page is not the page`);
      check(m.close && /back/i.test(m.close.label), `the way out says "${m.close && m.close.label}", not Back`);
    } else {
      check(!m.thumbBar || !m.thumbBar.shown, 'the phone thumb bar is showing at desktop width');
      // The rail goes at 1100 on purpose: which page you are on is answerable
      // from the title, where a line sits on the page is not. What the fix
      // here is about is that the *column* goes with it, so the two panes
      // that are left take the two columns instead of leaving one empty and
      // pushing the reading into a row of its own.
      if (WIDTH > 1100) check(m.rail && m.rail.w > 0, 'the page rail is missing above 1100');
      else check(!m.rail || m.rail.w === 0, `the rail column is still ${m.rail && m.rail.w}px wide under 1100`);
      check(m.pagePane && m.regions && m.pagePane.y === m.regions.y,
        `the page and the reading are not side by side: page at y=${m.pagePane && m.pagePane.y}, reading at y=${m.regions && m.regions.y}`);
      check(m.pagePane && m.regions && m.pagePane.w > m.regions.w,
        `the page pane (${m.pagePane && m.pagePane.w}) is narrower than the reading (${m.regions && m.regions.w})`);
    }
    check(m.pageOverflow <= 0, `the page scrolls sideways by ${m.pageOverflow}px with the reader open`);
  }

  // The band is crossed while the reader is open: the actions go back into
  // the reading's own foot, the bar goes away, and the way out is an X again.
  // A move that only runs on open leaves a phone bar on a desktop window.
  if (PHONE && m.open) {
    await page.setViewportSize({ width: 1024, height: 900 });
    await page.waitForTimeout(700);
    const wide = await page.evaluate(() => ({
      bar: !!document.getElementById('ocr-phone-bar'),
      foot: [...document.querySelectorAll('.ocr-regions-foot button')].map((b) => b.id),
      close: (document.getElementById('ocr-close').getAttribute('aria-label') || '').trim(),
      page: document.querySelector('.ocr-card').classList.contains('sheet-card-page'),
    }));
    console.log('back at 1024', JSON.stringify(wide));
    check(!wide.bar, 'the phone thumb bar survived the move to 1024');
    check(wide.foot.length >= 4, `the reading's actions did not come back: ${JSON.stringify(wide.foot)}`);
    check(wide.close === 'Close', `the way out still says "${wide.close}" at 1024`);
    check(!wide.page, 'the card kept the page variant at 1024');
    await page.setViewportSize({ width: WIDTH, height: HEIGHT });
    await page.waitForTimeout(700);
  }

  // Escape closes it, wherever the actions are.
  if (m.open) {
    await page.keyboard.press('Escape');
    await page.waitForTimeout(600);
    const shut = await page.evaluate(() => document.getElementById('ocr-workspace').classList.contains('hidden'));
    check(shut, 'Escape did not close the reader');
  }

  if (errors.length) findings.push('page errors: ' + errors.join(' | '));
  console.log(findings.length ? `FAIL (${WIDTH}x${HEIGHT}): ` + findings.join('\n  ') : `PASS (${WIDTH}x${HEIGHT}): 0 findings`);
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
