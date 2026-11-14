// Every anchored surface, with reduced motion on and off (the companion's
// menu, 2026-09-27: the reduced-motion blanket gave every element a 0.01ms
// transition on every property, so a box read right after a move was where
// the element had been, and a surface placed from it landed hundreds of
// pixels from its anchor; the owner has reduced motion on).
//
// For each surface, opened the way a person opens it, the gap between the
// surface's box and its anchor's (0 when they touch or overlap; a point for
// a surface opened at the pointer), and the surface's own top left, in both
// motion settings. A case fails when its gap is past its limit in either
// setting, or when the two settings put the surface more than 2px apart.
//
//   surfaces  a note card's kebab, a Library card's kebab (escaped), a
//             select's list, a '?' help popover, a row menu at the pointer,
//             the graph's node panel, the tour card, the command palette,
//             the text selection popup, the chat's citation peek (with the
//             fake answer model), and the companion's menu
//   not here  the date and time fields are the browser's own pickers; the
//             graph's node tooltip is the canvas's `title`
//
//   BASE=http://127.0.0.1:8830 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/anchorsmotion.js        (exits 1 on a miss)
//   SIZES=1440x900,1440x600  ONLY=kebab,help,...  NOPEEK=1 skips the chat
//   OVERRIDE_CSS=02-chat-graph.css=<file> measures an older stylesheet
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const { boot } = require('./lib.js');

const ROOT = path.resolve(__dirname, '..', '..');
const PY = process.env.SWEEP_PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
const FAKE_PORT = Number(process.env.FAKE_PORT || 8932);
const FAKE = `http://127.0.0.1:${FAKE_PORT}/v1`;
const SIZES = (process.env.SIZES || '1440x900,1440x600').split(',');
const ONLY = process.env.ONLY ? new Set(process.env.ONLY.split(',')) : null;
const NOTES = [
  'Kyoto trip: book the ryokan in Arashiyama six months out; the trains can wait.',
  'Half marathon week 4: easy pace is still too fast, slow the Tuesday run until it is boring.',
  'Questions for Thursday: who owns the migration after launch, and the old export format.',
  'Sourdough, third attempt: a 20 hour cold proof gave a better crumb, the base is still pale.',
];

//: How far a surface may sit from its anchor. A menu hangs 4px under its
//: opener; a popover 10px; a panel at the pointer 12px; the tour card beside
//: its control within its own gap; the palette has no anchor (its limit is
//: only the agreement between the two settings).
const LIMIT = { kebab: 8, libkebab: 8, select: 8, help: 14, rowmenu: 4, graph: 16, tour: 24, palette: Infinity, selection: 16, peek: 14, companion: 8 };

//: Each opener runs in the page, opens its surface, and returns
//: { anchor: [l, t, r, b] } or { point: [x, y] }, plus how to find the
//: surface; `surface` below reads it once things have settled.
const OPEN = {
  async kebab(page) {
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(1200);
    const at = await page.evaluate(() => {
      const opener = [...document.querySelectorAll('#entry-list > li .menu-wrap > button[aria-haspopup]')].find((b) => b.getClientRects().length);
      if (!opener) return null;
      opener.scrollIntoView({ block: 'center' });
      const r = opener.getBoundingClientRect();
      return [r.left + r.width / 2, r.top + r.height / 2];
    });
    if (!at) return null;
    await page.mouse.move(at[0], at[1]);
    await page.mouse.click(at[0], at[1]);
    return { anchorSel: '#entry-list [aria-expanded="true"]', surfaceSel: '.action-menu:not(.hidden)' };
  },
  async libkebab(page) {
    await page.evaluate(() => switchTab('library'));
    await page.waitForTimeout(1500);
    const at = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('#library-grid .library-card')].filter((c) => c.getClientRects().length);
      //: The lowest card on screen, so the menu has to flip or escape.
      const card = cards.filter((c) => c.getBoundingClientRect().bottom < innerHeight - 40)[0];
      const opener = card?.querySelector('.library-card-menu > button');
      if (!opener) return null;
      const r = opener.getBoundingClientRect();
      return [r.left + r.width / 2, r.top + r.height / 2];
    });
    if (!at) return null;
    await page.mouse.move(at[0], at[1]);
    await page.waitForTimeout(150);
    await page.mouse.click(at[0], at[1]);
    return { anchorSel: '#library-grid [aria-expanded="true"]', surfaceSel: '.action-menu:not(.hidden)' };
  },
  async select(page) {
    await page.evaluate(() => switchTab('library'));
    await page.waitForTimeout(1000);
    const ok = await page.evaluate(() => Boolean(document.getElementById('library-sort')?.closest('.select-shell')?.querySelector('.select-opener')?.getClientRects().length));
    if (!ok) return null;
    await page.click('#library-sort ~ .select-opener');
    return { anchorSel: '.select-opener[aria-expanded="true"]', surfaceSel: '.select-menu:not(.hidden)' };
  },
  async help(page) {
    //: Settings, where most of the '?'s are, and a dialog narrower than the
    //: window, which is what the popover clamps itself to. The lowest one
    //: whose button is on screen and on top, so it has to choose a side.
    await page.evaluate(() => openSettingsModal('models'));
    await page.waitForTimeout(1200);
    const id = await page.evaluate(() => {
      const shown = [...document.querySelectorAll('#settings-modal [data-help-for]')].filter((b) => {
        const r = b.getBoundingClientRect();
        return r.width && r.top > 40 && r.bottom < innerHeight - 40 && b.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2));
      });
      const trigger = shown.pop();
      if (!trigger) return null;
      trigger.dataset.sweepHelp = '1';
      return trigger.dataset.helpFor;
    });
    if (!id) return null;
    await page.click('[data-sweep-help="1"]');
    return { anchorSel: '[data-sweep-help="1"]', surfaceSel: `#${id}`, close: async () => { await page.keyboard.press('Escape'); await page.keyboard.press('Escape'); await page.evaluate(() => { if (typeof closeSettingsModal === 'function') closeSettingsModal(); }).catch(() => null); } };
  },
  async rowmenu(page) {
    await page.evaluate(() => switchTab('library'));
    await page.waitForTimeout(1200);
    //: The grid fills in batches: "the last card in view" was a different card in each motion run
    //: (y 668 and 783 at 1440x900), so the two placements were 110px apart for no motion reason; the first
    //: card in view, after the grid settles, is the same card in both.
    await page.waitForFunction(() => {
      const n = document.querySelectorAll('#library-grid .library-card').length;
      const w = window.__amGrid || (window.__amGrid = { n: -1, at: 0 });
      if (n !== w.n) { w.n = n; w.at = performance.now(); return false; }
      return n > 0 && performance.now() - w.at > 800;
    }, null, { polling: 100, timeout: 15000 }).catch(() => {});
    const at = await page.evaluate(() => {
      const card = [...document.querySelectorAll('#library-grid .library-card')].filter((c) => c.getClientRects().length && c.getBoundingClientRect().bottom < innerHeight - 40)[0];
      if (!card) return null;
      const r = card.getBoundingClientRect();
      return [Math.round(r.left + 30), Math.round(r.top + r.height / 2)];
    });
    if (!at) return null;
    await page.mouse.click(at[0], at[1], { button: 'right' });
    return { point: at, surfaceSel: '.action-menu:not(.hidden)' };
  },
  async graph(page) {
    await page.evaluate(() => switchTab('graph'));
    await page.waitForTimeout(3500);
    const at = await page.evaluate(async () => {
      //: Pressed on the node itself: an undragged popup stands beside its own node (INBOX 1413,
      //: `graphPopupFollowSpot`), so a press at a fixed point away from it measured the distance
      //: to that point, not to the anchor (L-general-56: 135px).
      const s = typeof gcTab !== 'undefined' ? gcTab : null;
      const box = document.getElementById('graph-box').getBoundingClientRect();
      const c = s?.canvas?.getBoundingClientRect();
      const t = s?.transform;
      const at = (n) => [c.left + n.x * t.k + t.x, c.top + n.y * t.k + t.y];
      const inside = ([x, y]) => x > box.left + box.width * 0.2 && x < box.left + box.width * 0.7 && y > box.top + box.height * 0.2 && y < box.bottom - box.height * 0.2;
      const node = c && t ? [...(s.byId?.values() || [])].find((n) => Number.isFinite(n.x) && inside(at(n))) : null;
      if (!node) return null;
      const [x, y] = at(node).map(Math.round);
      await openGraphPopup({ clientX: x, clientY: y, stopPropagation() {}, preventDefault() {} }, node);
      return [x, y];
    });
    if (!at) return null;
    return { point: at, surfaceSel: '#graph-popup:not(.hidden)' };
  },
  async tour(page) {
    await page.evaluate(() => switchTab('dashboard'));
    await page.waitForTimeout(800);
    const ok = await page.evaluate(() => { if (typeof openTour !== 'function') return false; openTour(); return true; });
    if (!ok) return null;
    await page.waitForTimeout(1500);
    //: A step that points at a control (the first one may be a welcome).
    for (let i = 0; i < 4; i += 1) {
      const has = await page.evaluate(() => Boolean(openTour.inspect.run && openTour.inspect.run.el));
      if (has) break;
      await page.click('#tour-next').catch(() => null);
      await page.waitForTimeout(1200);
    }
    await page.evaluate(() => { if (openTour.inspect.run?.el) openTour.inspect.run.el.dataset.sweepTour = '1'; });
    return { anchorSel: '[data-sweep-tour="1"]', surfaceSel: '#tour-card:not(.hidden)', close: async () => { await page.evaluate(() => { document.querySelector('[data-sweep-tour]')?.removeAttribute('data-sweep-tour'); if (typeof closeTour === 'function') closeTour(); else document.getElementById('tour-skip')?.click(); }); } };
  },
  async palette(page) {
    await page.evaluate(() => switchTab('dashboard'));
    await page.waitForTimeout(500);
    await page.evaluate(() => openPalette());
    return { surfaceSel: '#palette-overlay:not(.hidden) .palette-card, #palette-overlay:not(.hidden) > *' };
  },
  async selection(page) {
    await page.evaluate(() => switchTab('notes'));
    await page.waitForTimeout(1000);
    const found = await page.evaluate(() => {
      const body = [...document.querySelectorAll('#entry-list > li .entry-content, #entry-list > li .entry-body, #entry-list > li p')].find((el) => el.textContent.trim().length > 30 && el.getClientRects().length);
      if (!body) return null;
      body.scrollIntoView({ block: 'center', behavior: 'instant' });
      return true;
    });
    // The list scrolls smoothly (the app's own scroll-behavior), so the card is measured after it has
    // stopped; measured at once, the pointer went where the text had been 117px away.
    await page.waitForTimeout(900);
    const rect = !found ? null : await page.evaluate(() => {
      const body = [...document.querySelectorAll('#entry-list > li .entry-content, #entry-list > li .entry-body, #entry-list > li p')].find((el) => el.textContent.trim().length > 30 && el.getClientRects().length);
      const r = body.getBoundingClientRect();
      // The popup sits at the pointer's release (selection.js, "off the cursor"), so the drag ends on the
      // first line's own last character: a drag that runs past a short line parked the pointer, and the
      // popup, 117px from the text the anchor is measured on.
      const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      while (node && !node.textContent.trim()) node = walker.nextNode();
      const line = document.createRange();
      line.selectNodeContents(node);
      const first = line.getClientRects()[0];
      return [r.left + 4, first.top + first.height / 2, Math.min(r.left + 200, first.right - 2)];
    });
    if (!rect) return null;
    await page.mouse.move(rect[0], rect[1]);
    await page.mouse.down();
    await page.mouse.move(rect[2], rect[1], { steps: 6 });
    await page.mouse.up();
    const sel = await page.evaluate(() => {
      const s = getSelection();
      if (!s || s.isCollapsed) return null;
      const r = s.getRangeAt(0).getBoundingClientRect();
      return [r.left, r.top, r.right, r.bottom];
    });
    if (!sel) return null;
    return { anchor: sel, surfaceSel: '#selection-popup:not(.hidden), .selection-popup:not(.hidden)' };
  },
  async companion(page) {
    await page.evaluate(() => switchTab('dashboard'));
    await page.waitForTimeout(600);
    const at = await page.evaluate(() => {
      const buddy = document.getElementById('nm-buddy');
      if (!buddy || typeof nameMarkBuddyDrop !== 'function') return null;
      nameMarkBuddyMoveTo(buddy, nameMarkBuddyDrop(300, innerHeight - 45), true);
      clearTimeout(nmb.timer);
      clearTimeout(nmb.placeTimer);
      nmb.placeTimer = 1;
      return true;
    });
    if (!at) return null;
    await page.waitForTimeout(300);
    const face = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height * 0.45]; });
    await page.mouse.click(face[0], face[1], { button: 'right' });
    return { anchorSel: '#nm-buddy .nm-buddy-face', surfaceSel: '.action-menu:not(.hidden)' };
  },
};

function box(page, sel) {
  return page.evaluate((s) => {
    const el = [...document.querySelectorAll(s)].find((e) => e.getClientRects().length && e.getBoundingClientRect().width);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom].map((v) => Math.round(v));
  }, sel);
}

function gapBetween(a, b) {
  const dx = Math.max(0, b[0] - a[2], a[0] - b[2]);
  const dy = Math.max(0, b[1] - a[3], a[1] - b[3]);
  return Math.max(dx, dy);
}

async function closeAll(page) {
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  await page.evaluate(() => {
    document.querySelector('[data-sweep-help]')?.removeAttribute('data-sweep-help');
    if (typeof closeActionMenus === 'function') closeActionMenus();
    if (typeof closeHelpPopovers === 'function') closeHelpPopovers();
    getSelection()?.removeAllRanges();
    document.getElementById('graph-popup')?.classList.add('hidden');
    if (typeof closePalette === 'function' && !document.getElementById('palette-overlay')?.classList.contains('hidden')) closePalette();
  }).catch(() => null);
  await page.waitForTimeout(200);
}

function waitForFake() {
  return new Promise((resolve) => {
    let tries = 0;
    const poke = () => {
      const req = http.get(`${FAKE}/models`, (res) => { res.resume(); resolve(true); });
      req.on('error', () => (++tries > 40 ? resolve(false) : setTimeout(poke, 250)));
    };
    poke();
  });
}

async function openPeek(page) {
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(800);
  const found = await page.evaluate(async () => {
    const list = await apiJson('/conversations?limit=20');
    for (const conv of list.items || list) {
      await openConversation(conv.id);
      await new Promise((r) => setTimeout(r, 400));
      if (document.querySelector('#chat-messages .answer-citation-link')) return true;
    }
    return false;
  });
  if (!found) return null;
  const at = await page.evaluate(() => {
    const link = document.querySelector('#chat-messages .answer-citation-link');
    link.scrollIntoView({ block: 'center' });
    const r = link.getBoundingClientRect();
    return [r.left + r.width / 2, r.top + r.height / 2];
  });
  await page.mouse.click(at[0], at[1]);
  return { anchorSel: '.answer-citation-link[aria-expanded="true"]', surfaceSel: '#citation-peek' };
}

(async () => {
  let fake = null;
  const peek = !process.env.NOPEEK && (!ONLY || ONLY.has('peek'));
  if (peek) {
    fake = spawn(PY, [path.join(ROOT, 'scratchpad', 'fake_answer_server.py'), String(FAKE_PORT)], { cwd: ROOT, stdio: 'ignore' });
    await waitForFake();
  }
  const results = {};
  try {
    for (const motion of ['reduce', 'no-preference']) {
      for (const size of SIZES) {
        const [w, h] = size.split('x').map(Number);
        const { browser, page } = await boot({ viewport: { width: w, height: h }, reducedMotion: motion });
        try {
          //: The page can reload once more after `boot` returns (a new
          //: service worker after a server restart takes over and reloads,
          //: settings-wiring.js), so the setup is tried again after one.
          const ready = async () => {
            await page.waitForFunction(() => typeof switchTab === 'function' && typeof apiJson === 'function', null, { timeout: 20000 });
            await page.waitForTimeout(1500);
          };
          await ready();
          const setup = (args) => page.evaluate(async ({ notes, base, withPeek }) => {
            //: Performance mode (on by itself on a small machine) stills the
            //: page too; off, so the two settings are the only difference.
            localStorage.setItem('perf', 'off');
            if (typeof applyAppearance === 'function') applyAppearance();
            const have = await apiJson('/entries?limit=10').catch(() => []);
            const n = (have.items || have).length;
            for (let i = n; i < notes.length; i += 1) await api('/entries', { method: 'POST', body: JSON.stringify({ content: notes[i] }) });
            const b = document.getElementById('avatar-buddy');
            if (b) { b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); }
            if (withPeek) {
              await api('/models/provider', { method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: base }) }).catch(() => null);
              await api('/models/chat-model', { method: 'POST', body: JSON.stringify({ name: 'fake-answerer' }) }).catch(() => null);
            }
          }, args);
          const args = { notes: NOTES, base: FAKE, withPeek: peek };
          await setup(args).catch(async () => { await ready(); await setup(args); });
          if (peek) {
            //: One answered chat with citation marks, once per data dir.
            const has = await page.evaluate(async () => {
              const list = await apiJson('/conversations?limit=20');
              return (list.items || list).some((c) => /anchors sweep/.test(c.title || ''));
            });
            if (!has) {
              await page.evaluate(() => switchTab('chat'));
              await page.waitForTimeout(800);
              await page.evaluate(() => newChatConversation());
              await page.click('#chat-input');
              await page.keyboard.type('anchors sweep: what do my notes say about the trip, the run and Thursday?');
              await page.keyboard.press('Enter');
              await page.waitForFunction(() => chatController, null, { timeout: 5000 }).catch(() => null);
              await page.waitForFunction(() => !chatController, null, { timeout: 60000, polling: 200 }).catch(() => null);
              await page.waitForTimeout(800);
            }
          }
          const names = [...Object.keys(OPEN), ...(peek ? ['peek'] : [])].filter((n) => !ONLY || ONLY.has(n));
          for (const name of names) {
            await closeAll(page);
            let how = null;
            try {
              how = name === 'peek' ? await openPeek(page) : await OPEN[name](page);
            } catch (e) {
              how = { error: String(e).slice(0, 120) };
            }
            const key = `${name} ${size}`;
            results[key] = results[key] || {};
            if (!how || how.error) {
              results[key][motion] = { skipped: how?.error || 'could not open' };
              continue;
            }
            await page.waitForTimeout(450);
            const surface = await box(page, how.surfaceSel);
            const anchor = how.point ? [how.point[0], how.point[1], how.point[0], how.point[1]] : how.anchor || (how.anchorSel ? await box(page, how.anchorSel) : null);
            results[key][motion] = {
              surface,
              anchor,
              gap: surface && anchor ? gapBetween(surface, anchor) : null,
              inside: surface ? surface[0] >= 0 && surface[1] >= 0 && surface[2] <= w && surface[3] <= h : false,
            };
            if (how.close) await how.close();
          }
        } finally {
          await browser.close();
        }
      }
    }
  } finally {
    if (fake) fake.kill();
  }
  let failed = 0;
  for (const [key, both] of Object.entries(results)) {
    const name = key.split(' ')[0];
    const on = both.reduce || {};
    const off = both['no-preference'] || {};
    if (on.skipped || off.skipped) {
      console.log(`skip ${key}: ${on.skipped || off.skipped}`);
      continue;
    }
    const problems = [];
    for (const [label, m] of [['reduced', on], ['full', off]]) {
      if (!m.surface) problems.push(`${label}: no surface`);
      else {
        if (m.gap !== null && m.gap > LIMIT[name]) problems.push(`${label}: ${m.gap}px from its anchor`);
        if (!m.inside) problems.push(`${label}: outside the window`);
      }
    }
    if (on.surface && off.surface) {
      const moved = Math.max(Math.abs(on.surface[0] - off.surface[0]), Math.abs(on.surface[1] - off.surface[1]));
      if (moved > 2) problems.push(`the two settings put it ${moved}px apart`);
    }
    if (problems.length) failed += 1;
    console.log(`${problems.length ? 'FAIL' : 'ok  '} ${key}: gap ${on.gap ?? '-'} / ${off.gap ?? '-'} (reduced / full), surface ${JSON.stringify(on.surface)} / ${JSON.stringify(off.surface)}${problems.length ? `: ${problems.join('; ')}` : ''}`);
  }
  console.log(failed ? `FAIL ${failed}` : 'PASS');
  process.exitCode = failed ? 1 : 0;
})();
