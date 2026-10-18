const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const OUT = (process.env.SCRATCH||'.') + '/shots';
require('fs').mkdirSync(OUT,{recursive:true});
const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
// The browser-context options a sweep may ask for, beyond the viewport.
//
// This list is why INBOX 284 existed: `boot` used to pass `opts.viewport` and
// nothing else, so a sweep that wrote `boot({viewport:{width:390...},
// hasTouch:true, isMobile:true})` got a *desktop* context at a phone's width
// and measured every `(pointer: coarse)` and `(hover: none)` rule on the wrong
// side of its own media query, silently. Two sweeps built their own context to
// get around it (graphtouch.js, then graphphone.js and wbphone.js) rather than
// fix it here. Passing them through is the fix; naming them in one list is so
// the next option a sweep needs is added once, here, rather than worked around
// a fourth time.
//
// `isMobile` also turns on Chromium's mobile viewport and a mobile user agent,
// which is what makes `(pointer: coarse)` match; `hasTouch` alone gives the
// touch API without the media query, so the two are asked for together
// everywhere in this directory.
// `serviceWorkers: "block"` (OPEN 1108): `context.route` does not see what
// the app's service worker serves after the first load, so a sweep that
// overrides a CSS or JS file passes it or its override silently does nothing.
const CTX_OPTS = ['hasTouch', 'isMobile', 'deviceScaleFactor', 'locale',
  'timezoneId', 'colorScheme', 'reducedMotion', 'forcedColors', 'userAgent', 'permissions',
  'serviceWorkers'];
async function boot(opts={}) {
  //: SCROLLBARS=1 draws real scrollbars, as Windows does (17px, taking
  //: layout width). Headless Chromium hides them by default, which is the
  //: one difference between a sweep and the owner's desktop window that no
  //: viewport or scale setting reproduces (INBOX 397).
  //: `opts.args` are extra Chromium flags (the captions sweep's fake
  //: microphone: --use-fake-device-for-media-stream and a WAV to play).
  const browser = await chromium.launch({
    ...(process.env.SCROLLBARS ? { ignoreDefaultArgs: ["--hide-scrollbars"] } : {}),
    ...(opts.args ? { args: opts.args } : {}),
  });
  const ctxOpts = {viewport: opts.viewport||{width:1440,height:900}, deviceScaleFactor: opts.scale || 1};
  for (const k of CTX_OPTS) if (opts[k] !== undefined) ctxOpts[k] = opts[k];
  const ctx = await browser.newContext(ctxOpts);
  // Deterministic theme: the app remembers the last theme server-side, so a
  // sweep after a dark screenshot run would otherwise measure dark. THEME=dark
  // to sweep the other one.
  // The welcome tour is a race, not a step. Every context is a fresh profile,
  // so `maybeShowOnboarding` opens it after unlock, sometimes *after* the
  // hide below has already run, and then every click times out on
  // "#onboarding-overlay intercepts pointer events" (it cost two sweep runs).
  // Marking it done before the app boots is the only ordering that cannot
  // lose; the hide below stays as the belt to this braces.
  // `tourDone` for the same reason, and it is the same race one step along:
  // an install that has already seen the welcome is offered the guided tour
  // once, in a toast with a "Take the tour" button (maybeShowOnboarding in
  // app.js). A sweep that let that offer appear would measure a toast nobody
  // asked about, and a click landing on it. A sweep that wants the tour opens
  // it itself (scratchpad/ui-sweeps/tour.js does).
  // LOOK picks a look by its preset id (`default` is Classic), for a sweep
  // that has to hold in more than the default look. Unset means whatever the
  // app's own default is, which is what every older sweep measured.
  await ctx.addInitScript((look) => {
    try {
      if (look) localStorage.setItem('themePreset', look);
    } catch (e) {}
  }, process.env.LOOK || '');
  // LOOK= must not leak into the data dir (ledger 1541): the app mirrors the
  // look to the server's preferences, so a later sweep on the same dir would
  // inherit it. The preset stays in this context's localStorage (set above);
  // the write that would carry it to the server loses the key.
  if (process.env.LOOK) {
    await ctx.route((url) => /\/preferences$/.test(url.pathname), async (route) => {
      const req = route.request();
      if (req.method() !== 'PUT') return route.continue();
      try {
        const body = JSON.parse(req.postData() || '{}');
        const strip = (o) => { if (o && typeof o === 'object') { delete o.themePreset; for (const k of Object.keys(o)) strip(o[k]); } };
        strip(body);
        return route.continue({ postData: JSON.stringify(body) });
      } catch (e) { return route.continue(); }
    });
  }
  // GLASS=off (or on) sets the glass preference over whatever the look says,
  // for a sweep that has to hold with the glass-off list applied.
  await ctx.addInitScript((glass) => {
    try {
      if (glass) localStorage.setItem('glass', glass);
    } catch (e) {}
  }, process.env.GLASS || '');
  // FONT=mono (or any `#font-seg` value) sweeps that Appearance font, so
  // touch.js, docks.js and every sweep on this boot can run the font matrix
  // (fontmatrix.js) the way errors.js does.
  await ctx.addInitScript((font) => {
    try {
      if (font) localStorage.setItem('font', font);
    } catch (e) {}
  }, process.env.FONT || '');
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem('theme', t);
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
      // The companion's one-time nudge is a toast too (avatars.js,
      // `nameMarkBuddyHint`): marked seen for the same reason. A sweep that
      // wants it clears this key.
      if (!localStorage.getItem('nm-buddy-hint-sweep')) localStorage.setItem('nm-buddy-hint', 'done');
    } catch (e) {}
  }, process.env.THEME || 'light');
  // OVERRIDE_JS="whiteboard.js=/tmp/base/whiteboard.js" serves that file in
  // place of the app's own, so a "before" can be measured against a base
  // commit's script on the same server and data dir as the "after".
  // Several at once, comma separated: "a.js=/p/a.js,b.js=/p/b.js".
  for (const pair of (process.env.OVERRIDE_JS || '').split(',').filter(Boolean)) {
    const [name, file] = pair.split('=');
    const body = require('fs').readFileSync(file, 'utf8');
    await ctx.route(`**/${name}*`, (route) => route.fulfill({ body, contentType: 'application/javascript' }));
  }
  // The same for one stylesheet: OVERRIDE_CSS="07-whiteboard-misc.css=/path".
  if (process.env.OVERRIDE_CSS) {
    const [name, file] = process.env.OVERRIDE_CSS.split('=');
    const body = require('fs').readFileSync(file, 'utf8');
    await ctx.route(`**/css/${name}*`, (route) => route.fulfill({ body, contentType: 'text/css' }));
  }
  const page = await ctx.newPage();
  //: SLOW=1 (a loaded machine, load past 30): every wait and the boot get
  //: four times as long, so a sweep measures rather than times out.
  if (process.env.SLOW) page.setDefaultTimeout(120000);
  page.on('pageerror', e=>console.log('PAGEERROR:', e.message, '\n', (e.stack||'').split('\n').slice(0,6).join('\n')));
  page.on('console', m=>{ if(m.type()==='error') console.log('CONSOLE-ERR:', m.text().slice(0,160)); });
  //: `clock`: the page's clock starts there and runs on (quickadd.js's phrase
  //: set is written for one "now").
  if (opts.clock) await page.clock.install({ time: new Date(opts.clock) });
  //: PW_TIMEOUT=120000 on a machine so loaded that a page takes over 30 s to
  //: answer (load average 40+): every wait in the sweep gets the longer limit.
  if (process.env.PW_TIMEOUT) page.setDefaultTimeout(Number(process.env.PW_TIMEOUT));
  await page.goto(BASE + '/', {waitUntil:'domcontentloaded', timeout: Number(process.env.PW_TIMEOUT) || 30000});
  //: **Two ways in** (OPEN.md, 0.3.3): a notebook with "Ask for a password
  //: when the app opens" turned off never shows `#lock-password` on this
  //: computer, and waiting for it timed out every sweep on such a data dir.
  //: So wait for whichever comes first: the lock field, or the app itself
  //: (the boot splash down, the lock overlay hidden, a token stored).
  const way = await (await page.waitForFunction(() => {
    const field = document.getElementById('lock-password');
    const overlay = document.getElementById('lock-overlay');
    const splash = document.getElementById('boot-splash');
    if (field && overlay && !overlay.classList.contains('hidden') && field.offsetParent !== null) return 'lock';
    const settled = !splash || splash.classList.contains('hidden');
    if (settled && overlay && overlay.classList.contains('hidden') && localStorage.getItem('token')) return 'app';
    return false;
  }, null, {timeout:Number(process.env.BOOT_MS||(process.env.SLOW?90000:20000)), polling:100})).jsonValue();
  if (way === 'lock') {
    await page.fill('#lock-password', PW);
    await page.click('#lock-submit');
  }
  await page.waitForTimeout(3000);
  //: **The opening curtain** (INBOX 577): after a good password the lock
  //: screen stays up, its button saying "Opening…", while the first tab
  //: draws (`curtainShell`), and fades once it has. Waited out here, or a
  //: loaded machine's slow first tab read as a failed unlock and the field
  //: was filled again as it faded.
  await page.waitForFunction(() => !document.documentElement.classList.contains('shell-curtain')
    && !document.querySelector('#lock-overlay.lock-leaving'), null, { timeout: 15000, polling: 100 }).catch(() => {});
  //: On a loaded machine the unlock answer lands after the fixed waits above, and the
  //: field is still on screen (disabled, "Opening…"). Refilling it then waits on a
  //: disabled input until the timeout. Give the first unlock the time it needs.
  if (way === 'lock') await page.waitForFunction(() => document.getElementById('lock-overlay')?.classList.contains('hidden'), null, { timeout: Number(process.env.BOOT_MS||20000), polling: 200 }).catch(() => {});
  if (way === 'lock' && await page.$('#lock-password') && await page.isVisible('#lock-password')) {
    await page.fill('#lock-password', PW); await page.click('#lock-submit'); await page.waitForTimeout(3000);
  }
  //: **The server preference wins over localStorage** (UX audit, 2026-10-18):
  //: THEME=dark wrote the key before load, but the saved theme then won, so
  //: every "dark" sweep measured light. Set it through the app's own
  //: choice function once unlocked, and the data-theme is checked.
  {
    const want = process.env.THEME || 'light';
    await page.evaluate((t) => { if (document.documentElement.dataset.theme !== t && typeof applyThemeChoice === 'function') applyThemeChoice(t); }, want).catch(() => {});
    await page.waitForTimeout(400);
    const got = await page.evaluate(() => document.documentElement.dataset.theme).catch(() => '');
    if (got !== want) console.log('BOOT-WARN: data-theme is', JSON.stringify(got), 'not', want);
  }
  await page.evaluate(()=>{ const o=document.getElementById('onboarding-overlay'); if(o) o.classList.add('hidden'); });
  await page.waitForTimeout(800);
  //: **Updates ask once** (the owner, 2026-10-05): a fresh data dir is asked
  //: "Check for updates automatically?" after unlock, a dialog that would sit
  //: over every click a sweep makes. Answered "Don't check" here (nothing
  //: touches the network either way); UPDATE_ASK=1 leaves it for a sweep
  //: that measures the dialog itself.
  if (!process.env.UPDATE_ASK) {
    await page.waitForFunction(() => {
      const card = [...document.querySelectorAll('.confirm-overlay')]
        .find((o) => /Check for updates automatically/.test(o.textContent));
      if (!card) return !!(window.prefsCache && window.prefsCache.update_choice_made !== false) || document.readyState === 'complete';
      const no = [...card.querySelectorAll('button')].find((b) => /Don.t check/.test(b.textContent));
      if (no) no.click();
      return true;
    }, null, {timeout: 4000, polling: 200}).catch(() => {});
  }
  //: A fresh data dir shows the recovery-key dialog after the first password;
  //: closed here so it cannot intercept a sweep's clicks. RECOVERY_ASK=1 keeps it.
  if (!process.env.RECOVERY_ASK) {
    await page.evaluate(() => { const d = document.getElementById('recovery-key-dialog'); if (d && d.open) d.close(); });
  }
  //: `signIn` says which way it came in: 'lock' or 'app' (sign-in off).
  return {browser, ctx, page, OUT, signIn: way};
}
// Open the Library on its Boards & maps sub-tab and wait until the board code
// has arrived, for a sweep that is about a board (OPEN.md: "board sweeps that
// only click the Library tab time out").
//
// Two traps, both measured. The Library reopens on the sub-tab it was last
// left on (it is mirrored to the server, so a fresh browser context inherits
// whatever another sweep left), so a sweep that only presses the Library tab
// can land on Files or Images and wait for a board that never loads. And the
// board code is a lazy bundle that the Boards sub-tab fetches: a fixed sleep
// after the press is a guess at how long that takes on a loaded machine, so it
// waits for the functions instead. The press is repeated inside the wait, since
// switching to the Library restores the last sub-tab a moment *after* the
// switch and can undo a press made too early (`skeletons.js` found that).
//
// `fns` are the functions to wait for: `initWhiteboard` and `wbOpenSidebar` are
// defined only by the bundle (a stand-in answers to `openWhiteboardBoard` and a
// few more from the start, so those say nothing about whether it has loaded).
async function openBoardsTab(page, fns = ['initWhiteboard', 'wbOpenSidebar'], timeout = 20000) {
  await page.evaluate(() => switchTab('library'));
  await page.waitForFunction(({ names }) => {
    const button = document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]');
    if (!button) return false;
    if (!button.classList.contains('active')) { button.click(); return false; }
    return names.every((f) => typeof window[f] === 'function');
  }, { names: fns }, { timeout, polling: 100 });
}

// After `openWhiteboardBoard(id)` has been called: wait until the board is on
// screen (its top bar and its canvas laid out) and its first render has put
// its objects on the page, instead of a sleep sized for an idle machine.
// `objects` is how many `.wb-object` the board is known to hold (0 for an empty
// one, which has nothing to wait for).
async function waitForBoardOpen(page, objects = 0, timeout = 20000) {
  await page.waitForFunction((n) => {
    const bar = document.getElementById('wb-topbar');
    const box = document.getElementById('whiteboard-container');
    if (!bar || !bar.offsetParent || !box || !box.offsetParent) return false;
    return document.querySelectorAll('#whiteboard-container .wb-object').length >= n;
  }, objects, { timeout, polling: 100 });
  // One frame for the render's own follow-ups (the fit, the guides).
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
}

// BEFORE_DIR (a sweep's before and after): a directory of older copies of
// frontend js and css files, by their own names (atlas-life.js,
// 08-consistency.css...), served in place of the current ones; the page is
// reloaded and unlocked under them. Returns whether it routed anything.
async function routeBefore(ctx, page, dir = process.env.BEFORE_DIR) {
  if (!dir) return false;
  const fs = require('fs');
  for (const name of fs.readdirSync(dir)) {
    const kind = name.endsWith('.css') ? 'css' : name.endsWith('.js') ? 'js' : '';
    if (!kind) continue;
    const re = new RegExp(`/${kind}/${name.replace(/[.]/g, '\\.')}(\\?|$)`);
    await ctx.route(re, (r) => r.fulfill({ path: `${dir}/${name}`, contentType: kind === 'css' ? 'text/css' : 'text/javascript' }));
  }
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(800);
  if (await page.isVisible('#lock-password')) { await page.fill('#lock-password', PW); await page.click('#lock-submit'); }
  await page.waitForTimeout(2500);
  return true;
}

module.exports = {boot, OUT, PW, BASE, openBoardsTab, waitForBoardOpen, routeBefore};
