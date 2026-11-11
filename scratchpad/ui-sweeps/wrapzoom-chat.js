// Wrap/zoom sweep of Chat, Ask, the Guide and Graph (owner, 2026-11-11: "make
// sure the wrapping and ui issues arent an issue anywhere else from zoom or
// resolution"). Read-only: measures, never edits.
//
// Surface: the chat thread header, composer, dock and its More panel, chips,
// the Next row, the answer foot, the attachments strip, the side panels (note
// picker, web panel, persona prompt, compress review, context meter), the
// conversation list and its menus; Notes, Ask (idle, answered, history,
// help); the Guide sheet (empty, asked, its menu and help); Graph (dock,
// More menu, options panel, help, legend, popup, new note, trace, selection
// dock, topic, full screen).
//
// The five detectors (wrap, clip, overlap, overflow, misalign, plus text under
// a sticky or fixed bar) are the ones wrapzoom-shell.js defines: read from
// that file rather than copied, so a fix to the detector reaches every
// surface's sweep. The row test is widened here for this surface's own row
// names (chat-followups, chat-tool-group, graph-zoom, legend, msg-meta...);
// a row that is meant to wrap shows `flexWrap: wrap` in its finding and is
// judged by hand, not counted.
//
// Run (dark matrix, then light at 1440):
//   BASE=http://127.0.0.1:8814 THEME=dark SCRATCH=<dir> node wrapzoom-chat.js
//   BASE=... THEME=light VPS=1440x900@1 SCRATCH=<dir> node wrapzoom-chat.js
//   SUMMARY=1 SCRATCH=<dir> node wrapzoom-chat.js     (de-duplicated table)
// VPS picks viewports (WxH@scale, comma separated); ONLY=<prefix> picks states.
const fs = require('fs');
const path = require('path');
const SCRATCH = process.env.SCRATCH || '.';
const THEME = process.env.THEME || 'dark';
const MATRIX = ['1280x720@1', '1366x768@1', '1440x900@1', '1920x1080@1', '2560x1440@1',
  '1536x864@1.25', '1280x720@1.5', '960x540@2', '1280x720@2', '768x1024@1'];

// ---------------------------------------------------------------- detectors
const { detect, underBars } = (() => {
  const src = fs.readFileSync(path.join(__dirname, 'wrapzoom-shell.js'), 'utf8');
  const a = src.indexOf('function detect()');
  const b = src.indexOf('// ---------------------------------------------------------------- the states');
  if (a < 0 || b < a) throw new Error('wrapzoom-shell.js: detect()/underBars() not found');
  let body = src.slice(a, b);
  const was = body;
  body = body.replace('switcher|identity)($|', 'switcher|identity|followups|tool-group|zoom|legend|legend-row|meta|composer|attachments|suggest|pills|nudge|sources|starters|form|saverow|trail|ends|seg-compact|grounding)($|');
  if (body === was) throw new Error('wrapzoom-shell.js: ROWISH regex moved; update the widening here');
  return new Function(body + '\nreturn { detect, underBars };')();
})();

// Findings that belong to another session's surface (the shell's own rows) or
// were assigned elsewhere (the chat user bubble's hover actions).
const NOT_MINE = /aside#sidebar|#notes-sidebar|#top-bar|#tab-bar|#status-bar|header-controls|space-switcher|msg\.user > \.msg-actions|\.msg\.user .*msg-actions/;

// ---------------------------------------------------------------- the states
const wait = (p, ms) => p.waitForTimeout(ms);
const tab = (t) => async (p) => { await p.evaluate((t) => switchTab(t), t); await wait(p, 1200); };
const esc = async (p) => { for (let i = 0; i < 3; i++) await p.keyboard.press('Escape'); await wait(p, 200); };
const closeAll = async (p) => {
  await esc(p);
  await p.evaluate(() => {
    document.querySelectorAll('dialog[open]').forEach((d) => d.close());
    document.querySelectorAll('.help-body:not(.hidden)').forEach((h) => h.classList.add('hidden'));
    document.querySelectorAll('.action-menu:not(.hidden)').forEach((m) => m.classList.add('hidden'));
    document.querySelectorAll('details[open]').forEach((d) => { if (d.closest('#tab-graph, #tab-chat, #ask')) d.open = false; });
    try { if (typeof closeChatDockMore === 'function') closeChatDockMore(); } catch (e) {}
    try { if (typeof closeNotePicker === 'function') closeNotePicker(); } catch (e) {}
    try { if (typeof toggleWebPanel === 'function') toggleWebPanel(false); } catch (e) {}
    document.querySelector('[data-sheet="guide"] .sheet-close, [data-sheet="guide"] [data-sheet-close]')?.click();
  }).catch(() => {});
  await wait(p, 200);
};
const click = (sel) => (p) => p.evaluate((s) => { const e = document.querySelector(s); if (!e) throw new Error('missing ' + s); e.click(); }, sel);
const STATES = [];
const S = (name, setup, opts = {}) => STATES.push({ name, setup, ...opts });

// ----- Chat
const openThread = async (p) => {
  await tab('chat')(p);
  await p.evaluate(async () => {
    const list = await apiJson('/conversations');
    const conv = (list.conversations || list).find((c) => /Zoom thread/.test(c.title || ''));
    await openConversation(conv.id);
    await new Promise((r) => setTimeout(r, 600));
    const last = [...document.querySelectorAll('#chat-messages .msg.assistant')].at(-1);
    if (last && typeof renderFollowups === 'function') renderFollowups(last, ['What did the finance team say about the quarterly report?', 'Which notes mention the design review?', 'Summarise the autumn plan']);
  });
  await wait(p, 900);
};
S('chat-empty', async (p) => { await tab('chat')(p); await p.evaluate(() => newChatConversation()); await wait(p, 900); });
S('chat-thread', openThread);
S('chat-thread-top', async (p) => { await openThread(p); await p.evaluate(() => { document.getElementById('chat-messages').scrollTop = 0; }); await wait(p, 500); });
S('chat-assistant-hover', async (p) => {
  await openThread(p);
  const box = await p.evaluate(() => { const m = [...document.querySelectorAll('#chat-messages .msg.assistant')].at(-1); m.scrollIntoView({ block: 'center' }); const r = m.getBoundingClientRect(); return [r.left + r.width / 2, r.top + Math.min(40, r.height / 2)]; });
  await p.mouse.move(box[0], box[1]); await wait(p, 500);
});
S('chat-context-pop', async (p) => { await openThread(p); await p.evaluate(() => { const b = document.getElementById('chat-context'); if (b.hidden) renderChatContextMeter({ prompt_tokens: 3900, context_tokens: 8192 }); if (b.hidden) throw new Error('context pill hidden'); b.click(); }); await wait(p, 500); });
S('chat-actions-menu', async (p) => { await openThread(p); await p.evaluate(() => document.querySelector('#chat-actions-menu button, #chat-actions-menu summary').click()); await wait(p, 500); });
S('chat-help', async (p) => { await openThread(p); await click('#chat-help-toggle')(p); await wait(p, 500); });
S('chat-conv-menu', async (p) => { await openThread(p); await p.evaluate(() => document.querySelector('#conversation-list .kebab-opener, #conversation-list [aria-haspopup="menu"], #conversation-list .dock-more button').click()); await wait(p, 500); });
S('chat-attachments', async (p) => {
  await openThread(p);
  await p.evaluate(async () => {
    const docs = await apiJson('/documents');
    for (const d of (docs.documents || docs).slice(0, 3)) attachDocumentToChat(d.id, d.title, 'document');
    attachSelectionContext({ title: 'Meeting notes: design review with the long title', line: 12, text: 'A selected passage of some length from the design review notes', kind: 'text' });
    const notes = await apiJson('/entries?limit=4'); const ids = (Array.isArray(notes) ? notes : (notes.entries || notes.items || [])).slice(0, 3).map((e) => e.id);
    if (typeof setActiveChoice === 'function') { try { for (const id of ids) attachedNoteIds?.add?.(id); } catch (e) {} }
    try { renderAttachments(); } catch (e) {}
  });
  await wait(p, 700);
});
S('chat-composer-long', async (p) => { await openThread(p); await p.fill('#chat-input', 'A question long enough to run onto a few lines in the composer so its controls have to share the row with a growing box of text, and then a little more to be sure it wraps twice at the narrow windows.'); await wait(p, 500); });
S('chat-note-picker', async (p) => { await openThread(p); await p.evaluate(() => openNotePicker()); await wait(p, 1200); });
S('chat-note-picker-help', async (p) => { await openThread(p); await p.evaluate(() => openNotePicker()); await wait(p, 900); await click('[data-help-for="note-picker-help"]')(p); await wait(p, 400); });
S('chat-dock-more', async (p) => { await openThread(p); await p.evaluate(() => openChatDockMore()); await wait(p, 600); });
S('chat-persona-peek', async (p) => { await openThread(p); await p.evaluate(() => openChatDockMore()); await wait(p, 400); await click('#persona-peek')(p); await wait(p, 500); });
S('chat-web-panel', async (p) => { await openThread(p); await p.evaluate(() => toggleWebPanel(true)); await wait(p, 900); });
S('chat-web-panel-menu', async (p) => { await openThread(p); await p.evaluate(() => toggleWebPanel(true)); await wait(p, 700); await p.evaluate(() => document.querySelector('#web-panel-menu button, #web-panel-menu summary').click()); await wait(p, 500); });
S('chat-compress-review', async (p) => {
  await openThread(p);
  await p.evaluate(() => { const panel = document.getElementById('chat-compress-panel'); panel.classList.remove('hidden'); document.getElementById('chat-compress-stats').textContent = '14 turns, 6.2k tokens down to 1.1k'; document.getElementById('chat-compress-text').value = 'A summary of the conversation so far, about the quarterly report and the autumn plan.'; });
  await wait(p, 400);
});
S('chat-sidebar-search', async (p) => { await openThread(p); await p.fill('#chat-sidebar-search', 'zoom').catch(() => {}); await wait(p, 800); });

// ----- Ask (Notes, Ask)
const askOpen = async (p) => { await tab('notes')(p); await p.evaluate(() => showNotesSection('ask')); await wait(p, 900); };
S('ask-idle', askOpen);
S('ask-answer', async (p) => {
  await askOpen(p);
  await p.evaluate(async () => {
    const sw = document.getElementById('ask-use-ai'); if (sw && sw.checked) sw.click();
    document.getElementById('question').value = 'What is the plan for the quarterly planning review?';
    await askQuestion();
  });
  await p.waitForFunction(() => { const a = document.getElementById('ai-answer'); return a && a.textContent.trim().length > 20; }, null, { timeout: 20000 }).catch(() => {});
  await wait(p, 1500);
});
S('ask-history', async (p) => { await askOpen(p); await p.evaluate(() => toggleAskHistoryPanel()); await wait(p, 1000); });
S('ask-help', async (p) => { await askOpen(p); await click('[data-help-for="ask-source-help"]')(p); await wait(p, 400); });

// ----- Guide
const guideOpen = async (p) => { await tab('notes')(p); await p.evaluate(() => openHelpChat()); await wait(p, 1200); };
S('guide-empty', guideOpen);
S('guide-asked', async (p) => {
  await guideOpen(p);
  await p.fill('#help-chat-input', 'How do I attach a note to a chat?');
  await p.evaluate(() => document.getElementById('help-chat-send').click());
  await wait(p, 6000);
});
S('guide-menu', async (p) => { await guideOpen(p); await p.evaluate(() => document.querySelector('#help-chat-menu button, #help-chat-menu summary').click()); await wait(p, 500); });
S('guide-help', async (p) => { await guideOpen(p); await p.evaluate(() => document.querySelector('[data-help-for="help-chat-help"]').click()); await wait(p, 400); });

// ----- Graph
const graphOpen = async (p) => { await tab('graph')(p); await p.waitForFunction(() => typeof gcTab !== 'undefined' && gcTab.byId && gcTab.byId.size > 0, null, { timeout: 15000 }).catch(() => {}); await wait(p, 1500); };
S('graph-default', graphOpen);
S('graph-more-menu', async (p) => { await graphOpen(p); await click('#graph-more-menu summary')(p); await wait(p, 500); });
S('graph-help', async (p) => { await graphOpen(p); await click('#graph-help-toggle')(p); await wait(p, 500); });
S('graph-options', async (p) => { await graphOpen(p); await p.evaluate(() => { const o = document.getElementById('graph-options'); if (o.classList.contains('hidden')) document.getElementById('graph-options-toggle').click(); o.querySelectorAll('details').forEach((d) => { d.open = true; }); }); await wait(p, 800); });
S('graph-options-helps', async (p) => {
  await graphOpen(p);
  await p.evaluate(() => { const o = document.getElementById('graph-options'); if (o.classList.contains('hidden')) document.getElementById('graph-options-toggle').click(); o.querySelectorAll('details').forEach((d) => { d.open = true; }); o.querySelectorAll('[data-help-for]').forEach((b) => b.click()); });
  await wait(p, 800);
});
S('graph-legend', async (p) => { await graphOpen(p); await p.evaluate(() => { const t = document.getElementById('graph-legend-toggle'); if (t && !t.checked) t.click(); }); await wait(p, 900); });
S('graph-popup', async (p) => {
  await graphOpen(p);
  await p.evaluate(async () => { const n = [...gcTab.byId.values()].find((x) => typeof x.id === 'number' || /^\d+$/.test(String(x.id))) || [...gcTab.byId.values()][0]; await openGraphPopup({ stopPropagation() {}, clientX: innerWidth / 2, clientY: innerHeight / 2 }, n); });
  await wait(p, 1500);
});
// The panel eases into place and is re-placed once its content lands: 0.8 s
// after opening it still ran 31px past the graph box, settled at 1.5 s.
S('graph-new', async (p) => { await graphOpen(p); await p.evaluate(() => openGraphNewNote({ clientX: innerWidth / 2, clientY: innerHeight / 2 })); await wait(p, 2000); });
S('graph-trace', async (p) => { await graphOpen(p); await p.evaluate(() => setTracePanelOpen(true)); await wait(p, 700); });
S('graph-selection', async (p) => { await graphOpen(p); await p.evaluate(() => { gcTab.selected = new Set([...gcTab.byId.keys()].slice(0, 3)); gcSelectionChanged(); }); await wait(p, 600); });
S('graph-topic', async (p) => {
  await graphOpen(p);
  // Topics are only worked out in the topic colouring (graph-canvas.js, `graphStructure`).
  await p.evaluate(() => { const c = document.getElementById('graph-colour'); if (c.value !== 'topic') { c.value = 'topic'; c.dispatchEvent(new Event('change', { bubbles: true })); } });
  await p.waitForFunction(() => graphStructure?.topics?.length, null, { timeout: 8000 }).catch(() => {});
  await p.evaluate(() => { const t = (graphStructure?.topics || [])[0]; if (!t) throw new Error('no topics in graphStructure'); gcOpenTopic(t); });
  await wait(p, 800);
}, { after: (p) => p.evaluate(() => { const c = document.getElementById('graph-colour'); c.value = 'category'; c.dispatchEvent(new Event('change', { bubbles: true })); }) });
S('graph-search', async (p) => { await graphOpen(p); await p.fill('#graph-search', 'zoom note planning'); await wait(p, 900); });
S('graph-fullscreen', async (p) => { await graphOpen(p); await p.evaluate(() => toggleGraphFullscreen()); await wait(p, 1200); }, { after: (p) => p.evaluate(() => { if (document.querySelector('.graph-fullscreen, :fullscreen, [data-graph-full]')) toggleGraphFullscreen(); }) });

// ---------------------------------------------------------------- the driver
async function seed(page) {
  await page.evaluate(async () => {
    const have = await apiJson('/conversations');
    if ((have.conversations || have).some((c) => /Zoom thread/.test(c.title || ''))) return;
    const cats = ['Research', 'Work projects', 'Personal and family admin'];
    const ids = [];
    for (let i = 0; i < 12; i++) {
      const e = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Zoom note ${i}: the quarterly planning review needs a line of text long enough to wrap, and the design review follow up ${i}. - [ ] follow up with the team`, tags: [`zoom${i % 3}`, 'planning', 'long-tag-name-here'] }) });
      ids.push(e.id);
    }
    for (let i = 0; i < ids.length; i++) await api(`/entries/${ids[i]}`, { method: 'PUT', body: JSON.stringify({ category: cats[i % 3], pinned: i < 2 }) });
    const docIds = [];
    for (const t of ['Zoom plan for the autumn term with a long document title', 'Meeting notes: design review', 'Reading list']) {
      const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: t, content: `# ${t}\n\nSome text about the quarterly planning review.\n` }) });
      docIds.push(d.id);
    }
    const day = 86400000;
    for (const [t, d] of [['Send the quarterly report to the finance team before the board meeting', 2 * day], ['Renew passport', 5 * day], ['Water the plants', 3600000]]) {
      await api('/reminders', { method: 'POST', body: JSON.stringify({ text: t, due_at: new Date(Date.now() + d).toISOString() }) });
    }
    const turn = (i) => ({
      question: `Question ${i}: what does the quarterly planning review say about the autumn term, and who follows up with the finance team?`,
      answer: `Answer ${i}. The review [1] sets out the autumn plan, and the design review [2] has the follow ups.\n\n- one point about the **budget**\n- a second point with a longer line that has to wrap inside the bubble at narrow widths\n\n| Column | Another column |\n|---|---|\n| a | b |`,
      tools: [{ label: 'Searched your notes', ok: true }, { label: 'Read Zoom plan for the autumn term', ok: true }],
      raw_results: ids.slice(0, 4).map((id, k) => ({ id, content: `Zoom note ${k}: the quarterly planning review`, category: cats[k % 3], score: 0.8 - k * 0.1, tags: ['planning'] })),
      search_mode: 'hybrid',
      sentence_grounding: [{ note_id: ids[0], sentence: 'The review sets out the autumn plan.' }, { note_id: ids[1], sentence: 'The design review has the follow ups.' }],
      stats: { model: 'llama-3.2-3b-instruct-q4_k_m', prompt_tokens: 3900, completion_tokens: 412, context_tokens: 8192, tps: 12.4, elapsed_ms: 8300 },
      tokens: 4312,
      elapsed_ms: 8300,
      document_ids: i === 0 ? docIds.slice(0, 2) : undefined,
      note_ids: i === 0 ? ids.slice(0, 2) : undefined,
    });
    const first = await apiJson('/conversations', { method: 'POST', body: JSON.stringify({ ...turn(0), title: 'Zoom thread about the quarterly planning review and the autumn term' }) });
    for (let i = 1; i < 6; i++) await api(`/conversations/${first.id}/turns`, { method: 'POST', body: JSON.stringify(turn(i)) });
    try { await api(`/conversations/${first.id}`, { method: 'PUT', body: JSON.stringify({ title: 'Zoom thread about the quarterly planning review and the autumn term' }) }); } catch (e) {}
    for (let k = 0; k < 4; k++) await apiJson('/conversations', { method: 'POST', body: JSON.stringify({ question: `Another conversation ${k} with a fairly long first question to name it`, answer: 'Short answer.' }) });
  });
}

async function measure(page) {
  const a = await page.evaluate(detect);
  const b = await page.evaluate(underBars).catch((e) => [{ kind: 'error', sel: 'underBars', text: String(e.message).slice(0, 80) }]);
  // A select-shell's native <select> sits under its opener by design.
  return [...a, ...b].filter((f) => !NOT_MINE.test((f.sel || '') + ' ' + (f.by || '')) && !(f.kind === 'overlap' && /^select#/.test(f.sel) && /select-shell/.test(f.over || '')));
}

async function runViewport(spec, rows) {
  const { boot } = require('./lib.js');
  const [wh, sc] = spec.split('@'); const [w, h] = wh.split('x').map(Number); const scale = Number(sc || 1);
  let { browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: scale });
  try {
    if (!process.env.NOSEED) await seed(page);
    const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
    const push = (state, found) => {
      const seen = new Map();
      for (const f of found) { const k = f.kind + f.sel + (f.what || '') + (f.over || '') + (f.end || ''); if (seen.has(k)) { seen.get(k).count++; continue; } const row = { vp: spec, theme: THEME, state, count: 1, ...f }; seen.set(k, row); rows.push(row); }
      rows.push({ vp: spec, theme: THEME, state, kind: 'measured', n: found.length });
    };
    for (const st of STATES) {
      if (ONLY.length && !ONLY.some((o) => st.name.startsWith(o))) continue;
      try {
        await closeAll(page);
        await st.setup(page);
        push(st.name, await measure(page));
        if (st.after) await st.after(page).catch(() => {});
      } catch (e) {
        rows.push({ vp: spec, theme: THEME, state: st.name, kind: 'error', sel: String(e.message).split('\n')[0].slice(0, 140) });
        if (/crash|closed|Target/i.test(e.message)) { await browser.close().catch(() => {}); ({ browser, page } = await boot({ viewport: { width: w, height: h }, deviceScaleFactor: scale })); }
      }
    }
  } finally { await browser.close().catch(() => {}); }
}

function summary() {
  const rows = [];
  for (const f of fs.readdirSync(SCRATCH).filter((f) => /^wrapzoom-chat-.*\.json$/.test(f))) rows.push(...JSON.parse(fs.readFileSync(`${SCRATCH}/${f}`, 'utf8')));
  const measured = rows.filter((r) => r.kind === 'measured');
  const errors = rows.filter((r) => r.kind === 'error');
  const groups = new Map();
  for (const r of rows) {
    if (r.kind === 'measured' || r.kind === 'error') continue;
    const k = `${r.kind}${r.what ? '/' + r.what : ''} ${r.sel}${r.over ? ' OVER ' + r.over : ''}`;
    if (!groups.has(k)) groups.set(k, { k, vps: new Set(), states: new Set(), themes: new Set(), sample: r });
    const g = groups.get(k); g.vps.add(r.vp); g.states.add(r.state); g.themes.add(r.theme);
  }
  console.log(`${measured.length} state measurements across ${new Set(measured.map((r) => r.vp + r.theme)).size} viewport/theme runs; ${errors.length} errors`);
  const errs = new Map(); for (const e of errors) { const k = e.state + ': ' + e.sel; errs.set(k, (errs.get(k) || []).concat(e.vp + '/' + e.theme)); }
  for (const [k, v] of errs) console.log('ERROR', k, '@', v.length, 'runs');
  for (const g of [...groups.values()].sort((a, b) => a.k.localeCompare(b.k))) {
    const { vp, theme, state, kind, sel, ...nums } = g.sample;
    console.log(`${g.k}\n   vps=${[...g.vps].join(',')} themes=${[...g.themes].join(',')} states=${[...g.states].slice(0, 8).join(',')}${g.states.size > 8 ? '…' : ''}\n   sample(${vp},${state}) ${JSON.stringify(nums)}`);
  }
}

(async () => {
  if (process.env.SUMMARY) return summary();
  const vps = (process.env.VPS || MATRIX.join(',')).split(',');
  for (const spec of vps) {
    const rows = [];
    try { await runViewport(spec, rows); } catch (e) { rows.push({ vp: spec, theme: THEME, state: 'boot', kind: 'error', sel: String(e.message).slice(0, 140) }); }
    const file = `${SCRATCH}/wrapzoom-chat-${THEME}-${spec.replace(/[@.]/g, '_')}.json`;
    fs.writeFileSync(file, JSON.stringify(rows, null, 1));
    console.log(spec, THEME, 'states', rows.filter((r) => r.kind === 'measured').length, 'findings', rows.filter((r) => !['measured', 'error'].includes(r.kind)).length, 'errors', rows.filter((r) => r.kind === 'error').length, '->', file);
  }
})();
