// Every control has a name, and every control the Tab key reaches shows it
// has been reached.
//
//   BASE=http://127.0.0.1:8813 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/a11yname.js
//
// Two questions per surface (every tab, Notes' and Library's sub-tabs, an open
// document, a board, Settings):
//
//   name   a visible button, link, summary, select opener or field with no
//          accessible name: no text, no aria-label, no aria-labelledby that
//          resolves, no <label>, no title. An icon-only button is the usual
//          culprit: a screen reader says "button" and nothing else.
//   focus  the first TABS presses of the Tab key from the top of the surface:
//          each element that takes the focus must look different from how it
//          looked a moment before (outline, box-shadow, border or background),
//          or a keyboard user cannot see where they are.
//
// Prints findings only, one line each, then a count per surface.
const { chromium } = require('playwright');
const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const TABS_N = Number(process.env.TABS || 40);
const SURFACES = [
  ['dashboard'], ['notes', 'browse'], ['notes', 'capture'], ['notes', 'writing-room'], ['notes', 'ask'],
  ['chat'], ['graph'], ['library', 'docs'], ['library', 'images'], ['library', 'files'], ['library', 'skills'],
  ['library', 'links'], ['timeline'], ['reminders'],
];

function unnamed(scope) {
  const vis = (e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && e.getBoundingClientRect().width > 0;
  const root = document.querySelector(scope) || document.body;
  const out = [];
  for (const e of root.querySelectorAll('button, a[href], summary, input:not([type="hidden"]), textarea, select, [role="button"], [role="tab"], [role="menuitem"], [role="option"], [role="switch"], [role="checkbox"]')) {
    if (!vis(e) || e.closest('[aria-hidden="true"]')) continue;
    //: textContent as the fallback: innerText is empty for a button inside a
    //: `content-visibility: auto` note card that is off screen, which made
    //: "Show more" (`button.entry-more`) report as unnamed when it has words.
    const text = (e.innerText || e.textContent || e.value || '').trim();
    const al = (e.getAttribute('aria-label') || '').trim();
    const lb = (e.getAttribute('aria-labelledby') || '').split(/\s+/).map((id) => id && document.getElementById(id)?.textContent.trim()).filter(Boolean).join(' ');
    const lab = e.labels && e.labels.length ? [...e.labels].map((l) => l.textContent.trim()).join(' ') : '';
    const wrapped = e.closest('label') ? e.closest('label').textContent.trim() : '';
    const ph = e.getAttribute('placeholder') || '';
    const title = (e.getAttribute('title') || '').trim();
    if (text || al || lb || lab || wrapped || title || (e.matches('input, textarea') && ph)) continue;
    out.push(`${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}.${String(e.className).split(' ').slice(0, 3).join('.')} ${e.type ? '[' + e.type + ']' : ''} in #${e.closest('[id]')?.id || '?'}`);
  }
  return out;
}

function snapshot() {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  return {
    id: `${a.tagName.toLowerCase()}${a.id ? '#' + a.id : ''}.${String(a.className).split(' ').slice(0, 2).join('.')}`,
    //: The element and two ancestors: a field inside a composer, or a
    //: CodeMirror content box, shows its focus on the frame around it
    //: (`:focus-within`), which is as visible as a ring on itself.
    //: Plus the note box's own frame (`.note-surface`), three levels above
    //: its content box: it draws the ring, and a 2px accent outline there
    //: was reported "not visible" (2026-10-03).
    look: [a, a.parentElement, a.parentElement && a.parentElement.parentElement, a.closest && a.closest('.note-surface'), a.closest && a.closest('.note-composer')].filter(Boolean).map((e) => {
      const c = getComputedStyle(e);
      return [c.outlineStyle, c.outlineWidth, c.outlineColor, c.boxShadow, c.borderColor, c.backgroundColor].join('|');
    }).join('||'),
  };
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript((t) => { try { localStorage.setItem('theme', t); localStorage.setItem('onboardingDone', '1'); localStorage.setItem('tourDone', '1'); } catch (e) {} }, process.env.THEME || 'light');
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(2500);
  //: **Transitions off, or every focus ring reads as missing.** The ring's
  //: colour eases in (transparent to the accent), so the style read 60 ms after
  //: Tab, and the one read after the blur that starts easing it back, are the
  //: same half-way colour: 326 "focus not visible" findings on 2026-10-10, every
  //: one of them a ring that measured fully visible 500 ms later. A constructed
  //: stylesheet, because the CSP refuses an injected <style>.
  await page.evaluate(() => {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync('*, *::before, *::after { transition: none !important; animation: none !important; }');
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  });
  let total = 0;
  const report = async (where, scope) => {
    const names = await page.evaluate(unnamed, scope);
    for (const n of names) console.log(`  [${where}] no name: ${n}`);
    // Focus: walk Tab from the start of the surface.
    await page.evaluate((s) => { const r = document.querySelector(s); if (r) { r.setAttribute('tabindex', '-1'); r.focus(); } }, scope);
    const unseen = new Set();
    for (let i = 0; i < TABS_N; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(60);
      const on = await page.evaluate(snapshot);
      if (!on) continue;
      // The same element's look with the focus moved off it (to body), which
      // is what "looks different when focused" is measured against.
      const off = await page.evaluate(() => {
        const a = document.activeElement;
        const keep = a;
        a.blur();
        const look = [keep, keep.parentElement, keep.parentElement && keep.parentElement.parentElement, keep.closest && keep.closest('.note-surface'), keep.closest && keep.closest('.note-composer')].filter(Boolean).map((e) => {
          const c = getComputedStyle(e);
          return [c.outlineStyle, c.outlineWidth, c.outlineColor, c.boxShadow, c.borderColor, c.backgroundColor].join('|');
        }).join('||');
        keep.focus({ focusVisible: true });
        return look;
      });
      if (off === on.look) unseen.add(on.id);
    }
    for (const u of unseen) console.log(`  [${where}] focus not visible: ${u}`);
    total += names.length + unseen.size;
  };
  for (const [tab, sub] of SURFACES) {
    await page.evaluate((n) => { try { switchTab(n); } catch (e) {} }, tab);
    await page.waitForTimeout(800);
    if (sub) {
      await page.evaluate(([t, s]) => document.querySelector(`#tab-${t} [data-section="${s}"], #tab-${t} [data-view="${s}"]`)?.click(), [tab, sub]);
      await page.waitForTimeout(700);
    }
    await report(sub ? `${tab}/${sub}` : tab, `#tab-${tab}`);
  }
  await report('chrome', 'body > header, #top-bar');
  await report('status bar', '#status-bar');
  await page.evaluate(() => document.getElementById('settings-btn')?.click());
  await page.waitForTimeout(700);
  for (const s of ['account', 'appearance', 'preferences', 'models', 'tools', 'data', 'about']) {
    await page.evaluate((ss) => document.querySelector(`#settings-modal [data-section="${ss}"]`)?.click(), s);
    await page.waitForTimeout(400);
    await report(`settings/${s}`, `#settings-${s}`);
  }
  console.log(`== ${total} findings`);
  await browser.close();
})();
