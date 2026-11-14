// Trust contract rule 1 (WORLD_CLASS_PLAN 28.1): undo and redo everywhere.
// For each surface: find the controls (buttons, and the items of every menu
// the surface opens) whose label says they change data, perform each one for
// real, and ask whether Ctrl+Z puts the data back and Ctrl+Shift+Z does it
// again. Prints "<surface>: actions N, undoable M" and the ones that are not.
//
//   BASE=http://127.0.0.1:8791 [THEME=dark] [ONLY="notes list,documents"] [LIMIT=40] node undo.js
//
// **What "changed" means is the notebook, not the screen.** Every probe takes a
// snapshot of the API's lists (notes, documents and their text, reminders,
// bookmarks, boards and their cards, tags, categories, skills, preferences)
// before and after, with ids and timestamps stripped so a restore that mints a
// new row still counts as restored. A control whose snapshot does not move
// (a view switch, a copy) is not an action and is listed separately.
// **Limits, stated:** right-click menus and keyboard-only acts (Tab for a
// branch) are not walked, a control that needs a typed value gets "Probe
// name", and a few settings that would lock or wipe the notebook are skipped
// and counted.
const L = require('./trustlib.js');
const crypto = require('crypto');
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
const LIMIT = Number(process.env.LIMIT || 60);
const WAIT = Number(process.env.WAIT || 1500);

// A label that says the control changes data. Over-inclusive on purpose: the
// snapshot decides whether it did.
const MUT = /\b(delete|remove|bin|trash|archive|rename|move|merge|clear|add|new|create|duplicate|pin|unpin|favourite|favorite|tag|untag|link|unlink|reset|restore|resolve|dismiss|accept|reject|done|complete|snooze|mark|set|change|edit|save|apply|group|ungroup|lock|unlock|align|distribute|flip|rotate|bold|italic|underline|strike|strikethrough|heading|list|quote|code|indent|outdent|colou?r|fill|sort|arrange|tidy|replace|split|join|convert|insert|paste|cut|toggle|hide|enable|disable|turn|bring|send|front|back|forward|branch|child|sibling|topic|sticky|card|note|text|shape|frame|task|checkbox|todo|reminder|bookmark|skill|category|tags?)\b/i;
// Controls whose action leaves the notebook or the screen's data, or would
// lock, wipe or download: never pressed.
const SKIP = /(export|download|import|print|share|open|go to|close|cancel|help|about|search|find|zoom|fit|sidebar|filter|view|expand|collapse|customi[sz]e|more actions|copy|speak|dictat|record|upload|attach|wipe|erase|factory|password|encrypt|vault|recover|uninstall|install|update|restart|quit|sign out|log ?out|lock the|emergency|new window|ask atlas|generate|summar|rewrite|ai |model)/i;
const HARD_SKIP = /(password|passcode|encrypt|vault|wipe|erase|factory|recover|uninstall|install|update|restart|quit|sign out|log ?out|lan\b|certificate|phone|backup|restore from|model|download|server|port\b|proxy|launch|login)/i;


function canon(v) {
  if (Array.isArray(v)) return v.map(canon).map((x) => JSON.stringify(x)).sort();
  if (v && typeof v === 'object') {
    const o = {};
    for (const k of Object.keys(v).sort()) {
      if (/(^|_)ids?$|(tab|view|filter|sort|last|open|collapsed|sidebar|section|page_size|expanded|recent|seen|dismissed|layout_mode|zoom|pos)$|^(created|updated|edited|modified|saved|opened|viewed|accessed|last_\w+)_at$|^at$|hash|^preview|updated|modified|version|^rev$|^seq$|count$|_ts$|^ts$|saved|token|etag/i.test(k)) continue;
      o[k] = canon(v[k]);
    }
    return o;
  }
  return v;
}
async function snapshot(page, withStorage) {
  const raw = await page.evaluate(async ({ base, withStorage }) => {
    const H = { 'X-Auth-Token': localStorage.getItem('token') || '' };
    const get = async (p) => { try { return await (await fetch(base + p, { headers: H })).json(); } catch (e) { return null; } };
    const out = {};
    for (const p of ['/entries?limit=500', '/documents', '/reminders', '/bookmarks', '/whiteboard/boards', '/tags', '/categories', '/skills', '/preferences', '/entities', '/chat/tools', '/learned/switches', '/models/sampling', '/websearch/providers', '/models/utility-model', '/conversations']) out[p] = await get(p);
    const docs = out['/documents'] || [];
    for (const d of docs.slice(0, 6)) out['/documents/' + d.id] = await get('/documents/' + d.id);
    for (const b of (out['/whiteboard/boards'] || []).filter((b) => /^Probe/.test(b.title || ''))) out['/whiteboard/?board_id=' + b.id] = await get('/whiteboard/?board_id=' + b.id);
    if (window.undoProbeMedia) out['/media/meta'] = await get('/media/meta/' + encodeURIComponent(window.undoProbeMedia.split('/').pop()));
    // Bookkeeping no setting owns is left out: the reminder poll's clock and the
    // Library's view defaults, written by a timer or a first bundle load, made a
    // different control "not undone" each run (L-world-class-49).
    if (withStorage) { const ls = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (!/^(token|nm-|undo|draft|recent|nav|last|tour|onboarding|boot|doc-view-mode|docSidebarSection)/i.test(k) && !/settingsHistory|PolledAt$/.test(k)) ls[k] = localStorage.getItem(k); } out.ls = ls; }
    return out;
  }, { base: L.BASE, withStorage });
  const parts = {};
  for (const k of Object.keys(raw)) parts[k] = crypto.createHash('sha1').update(JSON.stringify(canon(raw[k]))).digest('hex').slice(0, 8);
  const snap = new String(crypto.createHash('sha1').update(JSON.stringify(parts)).digest('hex'));
  snap.parts = parts;
  return snap;
}
// Which lists moved between two snapshots, for the report: a probe that moves
// only /preferences is a view setting, not a change to the notebook.
function moved(a, b) { return Object.keys(b.parts).filter((k) => a.parts[k] !== b.parts[k]).map((k) => k.replace(/\?.*/, '').replace(/\/\d+$/, '/#')); }

async function closeMenus(page) {
  await page.evaluate(() => { try { closeActionMenus(); } catch (e) {} });
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(120);
}
async function clearStacks(page) {
  await page.evaluate(() => {
    try { undoStack.length = 0; redoStack.length = 0; } catch (e) {}
    try { wbUndoStack = []; wbRedoStack = []; wbUpdateUndoRedoButtons(); } catch (e) {}
  });
}
async function stackState(page) {
  return page.evaluate(() => {
    let a = 0, w = 0;
    try { a = undoStack.length; } catch (e) {}
    try { w = wbUndoStack.length; } catch (e) {}
    const bar = document.getElementById('status-undo');
    const toastUndo = [...document.querySelectorAll('.toast button, #toast button, .toast-action')].some((b) => /undo/i.test(b.textContent));
    return { app: a, board: w, bar: !!bar && !bar.disabled, toastUndo };
  });
}

// The controls a surface exposes: plain buttons, plus the items of each distinct menu.
async function inventory(page, rootSel) {
  const direct = await page.evaluate(({ rootSel }) => {
    const vis = (e) => { const b = e.getBoundingClientRect(); const s = getComputedStyle(e); return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const out = new Map();
    for (const r of [...document.querySelectorAll(rootSel)].filter(vis)) {
      for (const e of r.querySelectorAll('button, [role="button"], input[type="checkbox"], [role="switch"]')) {
        if (!vis(e) || e.closest('.action-menu, .toast') || e.matches('.kebab-opener, [aria-haspopup="menu"]') || e.disabled) continue;
        const label = (e.getAttribute('aria-label') || e.title || e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60);
        if (label && !out.has(label)) out.set(label, 'direct');
      }
    }
    return [...out.keys()];
  }, { rootSel });
  const menus = new Map();
  const openers = await page.$$(`${rootSel.split(',')[0]} .kebab-opener, ${rootSel.split(',')[0]} [aria-haspopup="menu"]`);
  const seenSets = new Set();
  let tried = 0;
  for (const o of openers) {
    if (tried >= 14) break;
    if (!(await o.isVisible().catch(() => false))) continue;
    tried++;
    await o.click({ timeout: 1500 }).catch(() => {});
    await page.waitForTimeout(180);
    const items = await page.evaluate(() => [...document.querySelectorAll('.action-menu:not(.hidden) button, [role="menu"]:not(.hidden) [role="menuitem"], .sheet .action-menu button')]
      .filter((b) => b.getBoundingClientRect().width > 0 && !b.disabled).map((b) => (b.getAttribute('aria-label') || b.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60)).filter(Boolean));
    const key = items.join('|');
    if (items.length && !seenSets.has(key)) { seenSets.add(key); for (const i of items) if (!menus.has(i)) menus.set(i, 'menu'); }
    await closeMenus(page);
  }
  const all = new Map();
  for (const l of direct) all.set(l, 'direct');
  for (const [l, k] of menus) if (!all.has(l)) all.set(l, k);
  return [...all.entries()].map(([label, via]) => ({ label, via }));
}

async function press(page, ctl, rootSel) {
  if (ctl.via === 'direct') {
    const ok = await page.evaluate(({ label, rootSel }) => {
      const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
      for (const r of [...document.querySelectorAll(rootSel)].filter(vis)) {
        for (const e of r.querySelectorAll('button, [role="button"], input[type="checkbox"], [role="switch"]')) {
          const l = (e.getAttribute('aria-label') || e.title || e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60);
          if (l === label && vis(e) && !e.closest('.action-menu') && !e.disabled) { e.setAttribute('data-probe', '1'); return e.matches('[aria-pressed], [aria-selected], [role="tab"], [aria-expanded], input[type="checkbox"]') ? 'stateful' : true; }
        }
      }
      return false;
    }, { label: ctl.label, rootSel });
    if (!ok) return false;
    // A form's required text, so Add and Save have something to add and save.
    await page.evaluate(() => {
      const el = document.querySelector('[data-probe="1"]');
      const scope = el.closest('form, .card, section, .row, .dock') || el.parentElement;
      for (const i of scope.querySelectorAll('input[type="text"], input:not([type]), textarea')) {
        const b = i.getBoundingClientRect();
        if (b.width > 0 && !i.value && !i.readOnly && !/search|find|filter/i.test(i.id + i.placeholder + (i.getAttribute('aria-label') || ''))) {
          i.value = 'Probe text'; i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }
    });
    const done = await page.click('[data-probe="1"]', { timeout: 4000 }).then(() => (ok === 'stateful' ? 'stateful' : true)).catch((e) => { if (process.env.DEBUG) console.log('   click failed:', e.message.split('\n')[0].slice(0, 90), (e.message.match(/intercepts pointer events/) ? e.message.split('\n').find((l) => /subtree intercepts/.test(l) || /<.*>/.test(l) ) : '').slice(0, 160)); return false; });
    await page.evaluate(() => document.querySelectorAll('[data-probe]').forEach((e) => e.removeAttribute('data-probe')));
    return done;
  }
  const openers = await page.$$(`${rootSel.split(',')[0]} .kebab-opener, ${rootSel.split(',')[0]} [aria-haspopup="menu"]`);
  let n = 0;
  for (const o of openers) {
    if (n++ > 14) break;
    if (!(await o.isVisible().catch(() => false))) continue;
    await o.click({ timeout: 1500 }).catch(() => {});
    await page.waitForTimeout(160);
    const ok = await page.evaluate((label) => {
      for (const b of document.querySelectorAll('.action-menu:not(.hidden) button, [role="menu"]:not(.hidden) [role="menuitem"], .sheet .action-menu button')) {
        const l = (b.getAttribute('aria-label') || b.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60);
        if (l === label && b.getBoundingClientRect().width > 0 && !b.disabled) { b.setAttribute('data-probe', '1'); return true; }
      }
      return false;
    }, ctl.label);
    if (ok) {
      const done = await page.click('[data-probe="1"]', { timeout: 4000 }).then(() => true).catch((e) => { if (process.env.DEBUG) console.log('   click failed:', e.message.split('\n')[0].slice(0, 90), (e.message.match(/intercepts pointer events/) ? e.message.split('\n').find((l) => /subtree intercepts/.test(l) || /<.*>/.test(l) ) : '').slice(0, 160)); return false; });
      await page.evaluate(() => document.querySelectorAll('[data-probe]').forEach((e) => e.removeAttribute('data-probe')));
      return done;
    }
    await closeMenus(page);
    if (CURRENT && CURRENT.again) await CURRENT.again(page);
  }
  return false;
}

// A confirm or a naming prompt that the press raised: answer it the way a
// person who meant the action would.
async function answerDialogs(page) {
  let answered = 0;
  // A prompt is opened by an awaited handler, and a sheet's file is loaded
  // first: asked at once, both were "no dialog" and the act "no change".
  await page.waitForTimeout(400);
  for (let i = 0; i < 3; i++) {
    const found = await page.evaluate(() => {
      const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
      const dlg = [...document.querySelectorAll('.confirm-overlay, .prompt-overlay, .dialog-overlay, .sheet-overlay, [role="alertdialog"], dialog[open]')]
        .filter((d) => vis(d) && !d.classList.contains('hidden') && !d.matches('#settings-modal, #palette-overlay, #onboarding-overlay, #lock-overlay'))[0];
      if (!dlg) return false;
      const input = dlg.querySelector('input[type="text"], input:not([type]), textarea');
      if (input && !input.value) { input.value = 'Probe name'; input.dispatchEvent(new Event('input', { bubbles: true })); }
      const aff = /^(delete|remove|move|bin|clear|yes|confirm|ok|merge|rename|save|create|add|apply|done|continue|discard|replace|restore|accept|go|start|set|reset|archive)/i;
      const btns = [...dlg.querySelectorAll('button')].filter(vis);
      const pick = btns.find((b) => b.matches('.danger, .primary, [data-confirm]')) || btns.find((b) => aff.test(b.textContent.trim()));
      if (!pick) return 'none';
      pick.setAttribute('data-probe', '1');
      return 'ok';
    });
    if (found === false) break;
    if (found === 'none') { await page.keyboard.press('Escape'); break; }
    await page.click('[data-probe="1"]', { timeout: 1500 }).catch(() => {});
    await page.evaluate(() => document.querySelectorAll('[data-probe]').forEach((e) => e.removeAttribute('data-probe')));
    answered++;
    await page.waitForTimeout(350);
  }
  return answered;
}

// Surfaces that are a mode of another one. The timeline's selection bar
// (TIMELINE_PLAN 10 row 3): the table view, Select on, the first two rows
// ticked, so every act the bar offers (move, tag, favourite, archive, delete)
// is pressed for real. The bar runs the Notes list's own batch acts.
const EXTRA = [
  // Every row of the bar is an act; a Move to row is named by its category.
  { name: 'timeline selection', root: '#timeline-batch-bar', mut: /./, open: async (p) => {
    await p.evaluate(() => switchTab('timeline'));
    await p.waitForTimeout(900);
    await p.evaluate(() => {
      if (timelineViewMode() !== 'table') document.querySelector('[data-timeline-view="table"]').click();
      if (!selectMode) enterSelectMode();
    });
    await p.waitForTimeout(500);
    await tickTwo(p);
  },
  // The Escape that closes one menu before the next is tried also ends the
  // selection (navigation.js's Escape stack): put it back.
  again: tickTwo },
  // The OCR workspace (L543; ocr79.js measures its three acts one by one): one
  // probe image with a reading, opened in the workspace. `undoProbeMedia` puts its
  // media row (the readings) in every snapshot, so an edit there counts.
  { name: 'ocr workspace', root: '#ocr-workspace', mut: /(clean|delete|edit|save|clear|reading)/i, open: openOcrProbe },
];
async function openOcrProbe(p) {
  await p.waitForFunction(() => typeof openOcrWorkspace === 'function', null, { timeout: 20000 });
  await p.evaluate(async () => {
    if (!window.undoProbeMedia) {
      const c = document.createElement('canvas'); c.width = 600; c.height = 200;
      const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, 600, 200); g.fillStyle = '#000'; g.font = '28px serif'; g.fillText('Read chapter 7 before Friday.', 20, 100);
      const blob = await new Promise((r) => c.toBlob(r, 'image/png'));
      const fd = new FormData(); fd.append('file', new File([blob], 'undo-probe.png', { type: 'image/png' })); fd.append('direct', 'true');
      const res = await fetch('/media/upload', { method: 'POST', body: fd, headers: { 'X-Auth-Token': authToken(), 'X-Workspace-ID': activeSpaceId() } });
      window.undoProbeMedia = (await res.json()).url;
    }
    const row = await apiJson('/media/meta/' + encodeURIComponent(window.undoProbeMedia.split('/').pop()));
    if (!row.vision_ocr_text) await apiJson(`/media/${row.id}/vision-ocr`, { method: 'POST', body: JSON.stringify({ text: Array(6).fill('Test, Test').join('\n') + '\nRead chapter 7 before Friday.' }) });
    const fresh = await apiJson('/media/meta/' + encodeURIComponent(window.undoProbeMedia.split('/').pop()));
    openOcrWorkspace({ ...fresh, _isImage: true }, [{ ...fresh, _isImage: true }]);
  });
  await p.waitForFunction(() => { const w = document.getElementById('ocr-workspace'); return w && !w.classList.contains('hidden'); }, null, { timeout: 15000 });
  await p.waitForTimeout(1200);
}
async function tickTwo(p) {
  await p.evaluate(() => {
    if (!selectMode) enterSelectMode();
    if (selectedIds.size) return;
    for (const tr of [...document.querySelectorAll('#timeline-table-body tr[data-kind="note"]')].slice(0, 2)) tr.click();
  });
  await p.waitForTimeout(250);
}
let CURRENT = null;

let needSeed = true;
async function probe(page, surface, ctl, storage) {
  if (needSeed) { await L.ensureSeed(page); needSeed = false; }
  await L.closeOverlays(page);
  await surface.open(page);
  CURRENT = surface;
  await clearStacks(page);
  const s0 = await snapshot(page, storage);
  const saved = await L.saveLocal(page);
  const pressed = await press(page, ctl, surface.root);
  if (!pressed) { await L.reboot(page, saved); return { label: ctl.label, status: 'unfound' }; }
  const dlg = await answerDialogs(page);
  await page.waitForTimeout(WAIT);
  const st = await stackState(page);
  const s1 = await snapshot(page, storage);
  // A view switch leaves its state in the page (a filter, a tab): the page is
  // loaded afresh so it cannot colour the next probe. Anything else only gets
  // its remembered keys put back.
  if (String(s1) === String(s0)) { if (pressed === 'stateful') await L.reboot(page, saved); else await page.evaluate((o) => { for (const k of Object.keys(localStorage)) if (!(k in o)) localStorage.removeItem(k); for (const k of Object.keys(o)) localStorage.setItem(k, o[k]); }, saved); return { label: ctl.label, status: 'nochange', dlg }; }
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(WAIT);
  const s2 = await snapshot(page, storage);
  needSeed = true;
  const row = { label: ctl.label, via: ctl.via, dlg, ...st, undone: String(s2) === String(s0), redone: null, moved: [...new Set(moved(s0, s1))].join(',') };
  if (!row.undone) row.left = [...new Set(moved(s0, s2))].join(',');
  if (row.undone) {
    await page.keyboard.press('Control+Shift+z');
    await page.waitForTimeout(WAIT);
    row.redone = String(await snapshot(page, storage)) === String(s1);
  }
  return row;
}

// Settings: every switch and choice in every pane that does not lock or wipe.
async function settingsControls(page) {
  return page.evaluate(() => {
    const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
    const nm = (e) => (e.getAttribute('aria-label') || e.id || (e.closest('label') || {}).textContent || (e.parentElement && e.parentElement.textContent) || e.name || '').trim().replace(/\s+/g, ' ').slice(0, 50);
    const out = [];
    const pane = document.querySelector('#settings-modal [data-section].active')?.dataset.section || '';
    for (const e of document.querySelectorAll('#settings-modal input[type="checkbox"], #settings-modal select')) {
      const box = (e.closest('label, .switch, .toggle, .select-shell') || e);
      if (!vis(box) && !vis(e)) continue;
      out.push({ key: pane + ' / ' + nm(e) + ' / ' + (e.id || e.name || ''), kind: e.tagName === 'SELECT' ? 'select' : 'switch' });
    }
    return out;
  });
}
async function touchSetting(page, key) {
  return page.evaluate((key) => {
    const nm = (e) => (e.getAttribute('aria-label') || e.id || (e.closest('label') || {}).textContent || (e.parentElement && e.parentElement.textContent) || e.name || '').trim().replace(/\s+/g, ' ').slice(0, 50);
    const pane = document.querySelector('#settings-modal [data-section].active')?.dataset.section || '';
    for (const e of document.querySelectorAll('#settings-modal input[type="checkbox"], #settings-modal select')) {
      if (pane + ' / ' + nm(e) + ' / ' + (e.id || e.name || '') !== key) continue;
      if (e.tagName === 'SELECT') {
        const other = [...e.options].find((o) => o.value !== e.value && !o.disabled);
        if (!other) return false;
        e.value = other.value; e.dispatchEvent(new Event('change', { bubbles: true }));
      } else { e.click(); }
      return true;
    }
    return false;
  }, key);
}

(async () => {
  const { browser, page } = await L.boot();
  await L.ensureSeed(page);
  const total = { actions: 0, undoable: 0, redoable: 0, exposed: 0 };
  const rows = [];
  for (const surface of [...L.SURFACES, ...EXTRA]) {
    if (ONLY.length && !ONLY.includes(surface.name)) continue;
    await L.closeOverlays(page);
    await surface.open(page);
    let ctls = [];
    let skipped = 0;
    const settings = surface.name === 'settings';
    if (settings) {
      const panes = await page.evaluate(() => [...document.querySelectorAll('#settings-nav [data-section]')].map((b) => b.dataset.section));
      for (const p of panes) {
        if (/^(account|logs|about|help|extras|tasks|data|shortcuts|models)$/.test(p)) { skipped++; continue; }
        await page.evaluate((p) => showSettingsSection(p), p).catch(() => {});
        await page.waitForTimeout(500);
        // Two per pane, so the sample spans the panes instead of being the
        // one pane with forty switches (the skills' tool list).
        let taken = 0;
        for (const c of await settingsControls(page)) { if (HARD_SKIP.test(c.key)) skipped++; else if (taken++ < 2) ctls.push({ label: c.key, via: c.kind, pane: p }); else skipped++; }
      }
    } else {
      const inv = await inventory(page, surface.root);
      // A control is probed when its label names a change and nothing in the
      // skip list; the rest are exposed but not pressed.
      ctls = inv.filter((c) => (MUT.test(c.label) || (surface.mut && surface.mut.test(c.label))) && !SKIP.test(c.label));
      skipped = inv.length - ctls.length;
      total.exposed += inv.length;
    }
    // The acts that matter most for trust go first, so a cap drops the least.
    const HOT = /(delete|remove|bin|trash|archive|rename|move|merge|clear|add|new|create|duplicate|pin|favourite|tag|link|done|snooze|reset|restore|group|colou?r|bold|italic|heading)/i;
    ctls.sort((a, b) => HOT.test(b.label) - HOT.test(a.label));
    const results = [];
    for (const ctl of ctls.slice(0, LIMIT)) {
      let r;
      try {
        if (settings) {
          await L.ensureSeed(page); await L.closeOverlays(page); await surface.open(page);
          await page.evaluate((p) => showSettingsSection(p), ctl.pane); await page.waitForTimeout(450);
          await clearStacks(page);
          const s0 = await snapshot(page, true);
          if (!(await touchSetting(page, ctl.label))) { r = { label: ctl.label, status: 'unfound' }; }
          else {
            await page.waitForTimeout(WAIT);
            const st = await stackState(page); const s1 = await snapshot(page, true);
            if (String(s1) === String(s0)) r = { label: ctl.label, status: 'nochange' };
            else {
              await page.keyboard.press('Control+z'); await page.waitForTimeout(WAIT);
              const s2 = await snapshot(page, true);
              r = { label: ctl.label, ...st, undone: String(s2) === String(s0), redone: null };
              if (r.undone) { await page.keyboard.press('Control+Shift+z'); await page.waitForTimeout(WAIT); r.redone = String(await snapshot(page, true)) === String(s1); }
            }
          }
        } else r = await probe(page, surface, ctl, false);
      } catch (e) { r = { label: ctl.label, status: 'error ' + e.message.slice(0, 60) }; }
      if (process.env.DEBUG) console.log('   ', JSON.stringify(r));
      results.push(r);
    }
    const acts = results.filter((r) => !r.status);
    const undo = acts.filter((r) => r.undone);
    const redo = acts.filter((r) => r.redone);
    total.actions += acts.length; total.undoable += undo.length; total.redoable += redo.length;
    console.log(`${surface.name}: actions ${acts.length}, undoable ${undo.length}, redoable ${redo.length} (probed ${results.length}, no change ${results.filter((r) => r.status === 'nochange').length}, unfound/error ${results.filter((r) => r.status && r.status !== 'nochange').length}, skipped ${skipped}${ctls.length > LIMIT ? ', capped at ' + LIMIT : ''})`);
    for (const r of acts.filter((r) => !r.undone)) console.log(`  NOT UNDONE: ${r.label}  [moved ${r.moved || 'settings'}; stack app ${r.app} board ${r.board}, bar ${r.bar}, toast ${r.toastUndo}]`);
    for (const r of acts.filter((r) => r.undone && !r.redone)) console.log(`  NO REDO: ${r.label}`);
    rows.push({ surface: surface.name, acts: acts.length, undo: undo.length });
  }
  console.log(`TOTAL: actions ${total.actions}, undoable ${total.undoable}, redoable ${total.redoable}, controls exposed ${total.exposed} (${process.env.THEME || 'light'})`);
  await browser.close();
})();
