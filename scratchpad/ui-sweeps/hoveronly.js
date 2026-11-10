// No hover-only affordance: UI_MODERNISATION_PLAN Phase 11 item 9's other
// half. "Every hover state has a tap equivalent" is only checkable on a
// browser that says it cannot hover, and until `lib.js` passed `hasTouch` and
// `isMobile` through (INBOX 284) no sweep here ever got one.
//
// How it measures, rather than guesses. It reads the app's own stylesheets for
// every rule whose selector carries `:hover` and whose body sets `opacity`,
// `visibility` or `display`, which is the shape of a reveal. For each it takes
// the same selector with `:hover` struck out (so `.row:hover .x` becomes
// `.row .x`, the element at rest), walks every tab, and measures what that
// element's computed style actually is with no pointer near it. An element
// that is laid out on screen and transparent, hidden or undisplayed at rest,
// while the hover rule would show it, is a control a finger can never reach.
//
// It emulates `hover: none` explicitly through CDP rather than trusting what
// `isMobile` implies, and refuses to report anything if the emulation did not
// take: a sweep that silently measured `hover: hover` is exactly the failure
// INBOX 284 was.
//
//   BASE=http://127.0.0.1:8994 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     NODE_PATH=/opt/node22/lib/node_modules node scratchpad/ui-sweeps/hoveronly.js
const { boot } = require('./lib.js');

const WIDTH = Number(process.env.WIDTH || 390);
const HEIGHT = Number(process.env.HEIGHT || 844);

// Where a control can hide: every tab, and the sub-tabs that are a surface of
// their own rather than a filter over the same rows.
const STOPS = [
  { tab: 'dashboard' },
  { tab: 'notes' },
  { tab: 'notes', open: '#notes-subtabs button[data-target="notes-view-capture"]', label: 'notes capture' },
  { tab: 'chat' },
  { tab: 'graph' },
  // The sub-tab is named even for the default one: the Library remembers the
  // last sub-tab, so a stop that only calls `switchTab` lands wherever the
  // stop before it left off, and the second pass then cannot find what the
  // first one measured.
  { tab: 'library', open: '#library-subtabs button[data-target="library-view-documents"]', label: 'library' },
  { tab: 'library', open: '#library-subtabs button[data-target="library-view-docs"]', label: 'library documents' },
  { tab: 'library', open: '#library-subtabs button[data-media-kind="images"]', label: 'library images' },
  { tab: 'library', open: '#library-subtabs button[data-target="library-view-links"]', label: 'library links' },
  { tab: 'timeline' },
  { tab: 'reminders' },
];

// Under this an element is not there to be read: it is the hover's to reveal.
const GONE = 0.35;

(async () => {
  const { page, browser } = await boot({
    viewport: { width: WIDTH, height: HEIGHT },
    hasTouch: true,
    isMobile: true,
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));

  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setEmulatedMedia', {
    features: [
      { name: 'hover', value: 'none' },
      { name: 'any-hover', value: 'none' },
      { name: 'pointer', value: 'coarse' },
      { name: 'any-pointer', value: 'coarse' },
    ],
  });
  await page.waitForTimeout(500);
  const media = await page.evaluate(() => ({
    hover: matchMedia('(hover: none)').matches,
    anyHover: matchMedia('(any-hover: none)').matches,
    pointer: matchMedia('(pointer: coarse)').matches,
  }));
  console.log('media', JSON.stringify(media));
  if (!media.hover || !media.pointer) {
    console.log('FAIL: the browser still reports a hover, so nothing below would mean anything');
    await browser.close();
    process.exit(1);
  }

  // Every reveal rule in the app's own stylesheets, read once.
  const rules = await page.evaluate(() => {
    const out = [];
    const walk = (list, media) => {
      for (const rule of list) {
        // Order matters, and getting it wrong is silent: since CSS nesting
        // shipped, a plain `CSSStyleRule` carries a `cssRules` list too (an
        // empty one), so a walker that tests `rule.cssRules` before
        // `rule.selectorText` recurses into every style rule and reads none
        // of them. The first run of this sweep found 0 reveal rules out of
        // the app's 243 `:hover` rules that way.
        if (rule.cssRules && rule.cssRules.length) {
          walk(rule.cssRules, rule.conditionText || media);
        }
        if (!rule.selectorText || !rule.selectorText.includes(':hover')) continue;
        const shows = {};
        for (const prop of ['opacity', 'visibility', 'display']) {
          const value = rule.style.getPropertyValue(prop);
          if (value) shows[prop] = value.trim();
        }
        if (!Object.keys(shows).length) continue;
        // A hover that *hides* something is not this sweep's business.
        if (shows.opacity !== undefined && parseFloat(shows.opacity) === 0) continue;
        if (shows.visibility === 'hidden' || shows.display === 'none') continue;
        for (const part of rule.selectorText.split(',')) {
          const one = part.trim();
          if (!one.includes(':hover')) continue;
          out.push({ at: one, rest: one.replaceAll(':hover', ''), media: media || '', shows });
        }
      }
    };
    for (const sheet of document.styleSheets) {
      let list;
      try { list = sheet.cssRules; } catch (e) { continue; }
      if (list) walk(list, '');
    }
    return out;
  });
  console.log(`reveal rules with :hover: ${rules.length}`);

  const found = new Map();
  for (const stop of STOPS) {
    const name = stop.label || stop.tab;
    await page.evaluate((t) => switchTab(t), stop.tab);
    await page.waitForTimeout(1200);
    if (stop.open) {
      const el = await page.$(stop.open);
      if (el) { await el.click().catch(() => {}); await page.waitForTimeout(1200); }
    }
    const hits = await page.evaluate(({ rules, GONE }) => {
      const out = [];
      for (const rule of rules) {
        let nodes;
        try { nodes = document.querySelectorAll(rule.rest); } catch (e) { continue; }
        for (const el of nodes) {
          // Laid out, so this is a control that is on the page rather than one
          // whose whole branch is off: `getClientRects` still reports a box
          // for an element at opacity 0, which is precisely the case wanted.
          if (!el.getClientRects().length) continue;
          const cs = getComputedStyle(el);
          const opacity = parseFloat(cs.opacity);
          const hidden = cs.visibility === 'hidden' || cs.display === 'none' || (opacity === opacity && opacity < GONE);
          if (!hidden) continue;
          const r = el.getBoundingClientRect();
          // Off screen entirely (a parked sheet, a scrolled-away row) is not a
          // hover problem.
          if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
          out.push({
            rule: rule.at,
            rest: rule.rest,
            shows: rule.shows,
            el: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '.' + [...el.classList].slice(0, 3).join('.')),
            opacity: cs.opacity,
            visibility: cs.visibility,
            display: cs.display,
            box: [Math.round(r.width), Math.round(r.height)],
          });
        }
      }
      return out;
    }, { rules, GONE });
    for (const hit of hits) {
      const key = `${hit.rest} :: ${hit.el}`;
      if (!found.has(key)) found.set(key, { ...hit, where: new Set() });
      found.get(key).where.add(name);
    }
    console.log(`${name.padEnd(20)} hover-only: ${hits.length}`);
  }

  // The second pass, which is what makes this a measurement rather than a
  // list of `:hover` rules. A reveal on hover is only a *fault* when nothing
  // a finger can do produces it, and several here are fine: the AI dot's
  // popup, for one, opens on hover and is also pinned open by a tap on the
  // dot (`toggleAiStatusPopup`). So each candidate is tapped, for real,
  // through CDP, on the element the `:hover` is attached to (the part of the
  // selector before it), and measured again. Still invisible after the tap is
  // the finding.
  const tap = async (box) => {
    const points = [{ x: box.x, y: box.y, id: 0 }];
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: points });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  };
  for (const hit of found.values()) {
    const where = [...hit.where][0];
    const stop = STOPS.find((s) => (s.label || s.tab) === where);
    await page.evaluate((t) => switchTab(t), stop.tab);
    await page.waitForTimeout(1000);
    if (stop.open) {
      const el = await page.$(stop.open);
      if (el) { await el.click().catch(() => {}); await page.waitForTimeout(1000); }
    }
    const spot = await page.evaluate(({ rest, at }) => {
      const el = document.querySelector(rest);
      if (!el) return null;
      // The host is what carries the `:hover`: everything up to it in the
      // selector. `.row:hover .x` gives `.row`; `.x:hover` gives `.x` itself.
      const host = at.slice(0, at.indexOf(':hover')).trim().split(/\s+/).pop() || '';
      let target = el;
      try { target = el.closest(host) || el.parentElement || el; } catch (e) { target = el.parentElement || el; }
      const r = target.getBoundingClientRect();
      if (!r.width || !r.height) return null;
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + Math.min(20, r.height / 2)) };
    }, { rest: hit.rest, at: hit.rule });
    if (!spot) { hit.tapped = 'could not find it again'; continue; }
    await tap(spot);
    await page.waitForTimeout(700);
    hit.tapped = await page.evaluate(({ rest, GONE }) => {
      const el = document.querySelector(rest);
      if (!el) return 'gone after the tap';
      const cs = getComputedStyle(el);
      const opacity = parseFloat(cs.opacity);
      const shown = cs.visibility !== 'hidden' && cs.display !== 'none' && !(opacity === opacity && opacity < GONE);
      return shown ? 'revealed by a tap' : `still ${cs.opacity} / ${cs.visibility} after a tap`;
    }, { rest: hit.rest, GONE });
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
  }

  const list = [...found.values()].filter((hit) => hit.tapped !== 'revealed by a tap');
  for (const hit of [...found.values()]) {
    if (hit.tapped === 'revealed by a tap') {
      console.log(`  ok  ${hit.rest} is hidden at rest and ${hit.tapped}`);
    }
  }
  for (const hit of list) {
    console.log(`  ${hit.rest}\n    is ${hit.el} at opacity ${hit.opacity}, visibility ${hit.visibility}, display ${hit.display}, ${hit.box[0]}x${hit.box[1]}` +
      `\n    shown by ${hit.rule} (${JSON.stringify(hit.shows)}) on ${[...hit.where].join(', ')}` +
      `\n    tapped: ${hit.tapped}`);
  }
  if (errors.length) console.log('page errors: ' + errors.join(' | '));
  console.log(list.length ? `FAIL: ${list.length} hover-only affordance(s) at ${WIDTH}` : `PASS: 0 hover-only affordances at ${WIDTH}`);
  await browser.close();
  process.exit(list.length || errors.length ? 1 : 0);
})();
