// Brief 72a (WORLD_CLASS_PLAN 28, decision 71): what each named surface renders
// today, measured, for the "Deepened 2026-10-10" blocks. Per surface: controls,
// time from the call to the painted surface, controls past the viewport, clipped
// text, overlapping controls, AI controls and how many are disabled, and an undo
// round trip where one is cheap to drive. Run on a fresh data dir with no model.
// Usage: BASE=http://127.0.0.1:8790 VW=1440|390 node deepen72a.js > out.json
const { boot } = require(process.env.SW ? process.env.SW + "/lib.js" : "./lib.js");
const VW = Number(process.env.VW || 1440);
const phone = VW < 600;
// SURF="documents,code" measures only those surfaces (Brief 76 before and after).
const SURF = (process.env.SURF || "").split(",").filter(Boolean);
const MEASURE = `window.__m = (rootSel) => {
  const root = typeof rootSel === 'string' ? document.querySelector(rootSel) : rootSel;
  if (!root) return null;
  // checkVisibility: a closed <details> keeps its children's stale boxes, so the
  // chat's folded source cards counted as 82 and 136 overlaps nobody can see.
  const vis = (e) => { if (e.closest('[hidden]') || !e.checkVisibility({ contentVisibilityAuto: true }) || getComputedStyle(e).clipPath === 'inset(50%)') return false; const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const ctrls = [...root.querySelectorAll('button, select, input, textarea, [role=button], [role=menuitem], [role=tab], a[href]')].filter((c) => !c.closest('.select-menu') && !c.classList.contains('select-opener') && vis(c));
  const W = innerWidth;
  const scrollAnc = (e) => { for (let p = e.parentElement; p; p = p.parentElement) { const cs = getComputedStyle(p); if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true; } return false; };
  const off = ctrls.filter((c) => { const r = c.getBoundingClientRect(); return (r.right > W + 1 || r.left < -1) && !scrollAnc(c); });
  const clipped = [...root.querySelectorAll('*')].filter((e) => e.childElementCount === 0 && e.textContent.trim() && vis(e) && e.getBoundingClientRect().width > 1 && e.scrollWidth > e.clientWidth + 1 && /hidden|clip/.test(getComputedStyle(e).overflowX) && getComputedStyle(e).textOverflow !== 'ellipsis' && !e.closest('.cm-editor'));
  // A hit box drawn by ::after (the citation mark's) takes the click too.
  const hitBox = (c) => { const r = c.getBoundingClientRect(); const a = getComputedStyle(c, '::after'); if (a.content === 'none' || a.position !== 'absolute') return r; return { width: Math.max(r.width, parseFloat(a.width) || 0), height: Math.max(r.height, parseFloat(a.height) || 0) }; };
  const small = ctrls.filter((c) => { const r = hitBox(c); return (r.width < 24 || r.height < 24) && c.type !== 'checkbox' && c.type !== 'radio' && c.tagName !== 'A' && !c.classList.contains('select-native-hidden'); });
  let overlaps = 0; const ovl = [];
  // What is on screen of each control: its box cut by every ancestor that
  // clips (overflow other than visible), so a row scrolled under a list's
  // edge is not counted as lying over the button past that edge (Brief 87:
  // the agent's starters, clipped at the intro's foot, were 2 "overlaps").
  const seen = (c) => { let r = c.getBoundingClientRect(); let t = r.top, b = r.bottom, l = r.left, rt = r.right; for (let p = c.parentElement; p; p = p.parentElement) { const cs = getComputedStyle(p); if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue; const q = p.getBoundingClientRect(); t = Math.max(t, q.top); b = Math.min(b, q.bottom); l = Math.max(l, q.left); rt = Math.min(rt, q.right); } return { top: t, bottom: b, left: l, right: rt }; };
  const rs = ctrls.map(seen);
  for (let i = 0; i < ctrls.length; i++) for (let j = i + 1; j < ctrls.length; j++) {
    if (ctrls[i].contains(ctrls[j]) || ctrls[j].contains(ctrls[i])) continue;
    // A rail row's own ⋮ overlays its title by design (INBOX 722, DOCUMENTS_PLAN 1121 row 7, decided:
    // keep the overlay); within one row it is no overlap. Across rows it still counts.
    const ownMenu = (c, d) => { const m = c.closest('.doc-item-menu, .entry-actions, .category-actions'); const row = m && m.closest('li, .doc-item'); return !!(row && row.contains(d) && !m.contains(d)); };
    if (ownMenu(ctrls[i], ctrls[j]) || ownMenu(ctrls[j], ctrls[i])) continue;
    const a = rs[i], b = rs[j];
    const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left), iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ix > 2 && iy > 2) { overlaps++; if (ovl.length < 4) ovl.push((ctrls[i].id || ctrls[i].className.toString().slice(0,20) + ':' + ctrls[i].textContent.trim().slice(0, 10)) + '|' + (ctrls[j].id || ctrls[j].className.toString().slice(0,20) + ':' + (ctrls[j].getAttribute('aria-label')||ctrls[j].textContent).trim().slice(0, 14))); }
  }
  const ai = ctrls.filter((c) => c.querySelector('.ph-sparkle, .ph-magic-wand, .ph-robot') || /\\bAI\\b|Summari[sz]e|Describe|Explain with/.test((c.getAttribute('aria-label') || '') + ' ' + (c.title || '') + ' ' + c.textContent));
  const aiDisabled = ai.filter((c) => c.disabled || c.getAttribute('aria-disabled') === 'true');
  return { controls: ctrls.length, offscreen: off.length, offList: off.slice(0, 5).map((c) => c.id || c.textContent.trim().slice(0, 18)), clipped: clipped.length, clipList: clipped.slice(0, 4).map((e) => e.className.toString().slice(0, 30) + ':' + e.textContent.trim().slice(0, 18)), smallTargets: small.length, overlaps, ovl, aiControls: ai.length, aiDisabled: aiDisabled.length, pageHScroll: document.documentElement.scrollWidth > innerWidth + 1, rootW: Math.round(root.getBoundingClientRect().width) };
};`;
const timed = (page, trigger, ready) => page.evaluate(`(async () => {
  const t0 = performance.now();
  const p = (${trigger});
  const until = performance.now() + 15000;
  while (performance.now() < until) {
    await new Promise((res) => requestAnimationFrame(res));
    if (${ready}) return Math.round(performance.now() - t0);
  }
  try { await p; } catch (e) {}
  return -1;
})()`);
const clickText = (page, text) => page.getByText(text).first().evaluate((e) => { const t = e.closest('button, a, [role=button], [role=option], [tabindex], .doc-row, .wb-board-card') || e; t.click(); return t.tagName + '.' + String(t.className).slice(0, 40); });
(async () => {
  const opts = phone ? { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: 1440, height: 900 } };
  const { browser, page } = await boot(opts);
  await page.evaluate(MEASURE);
  const out = { VW };
  const toasts = [];
  await page.exposeFunction("__toast", (t) => toasts.push(t));
  await page.evaluate(() => new MutationObserver((l) => { for (const m of l) for (const n of m.addedNodes) if (n.nodeType === 1 && n.classList?.contains("toast")) window.__toast(n.textContent.trim().slice(0, 140)); }).observe(document.getElementById("toast-box"), { childList: true }));
  const stamp = Date.now();
  // Fixtures
  const fx = await page.evaluate(async (st) => {
    const para = "The quick brown fox studies the notebook and writes careful notes about each lecture. ";
    let prose = "# Lecture notes\n\n";
    for (let i = 0; i < 40; i++) prose += `## Section ${i + 1}\n\n` + para.repeat(6) + "\n\n- a point\n- another point\n\n";
    let code = "";
    for (let i = 0; i < 60; i++) code += `def f${i}(x):\n    \"\"\"Doc ${i}.\"\"\"\n    return x + ${i}\n\n`;
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Deep prose " + st, content: prose, file_type: "md" }) });
    const c = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "deep_code_" + st + ".py", content: code, file_type: "py" }) });
    return { doc: d.id, code: c.id, words: prose.split(/\s+/).length, lines: code.split("\n").length };
  }, stamp);
  out.fixtures = fx;
  const run = async (name, fn) => { if (SURF.length && !SURF.includes(name)) return; try { out[name] = await fn(); } catch (e) { out[name] = { error: String(e).slice(0, 200) }; } };

  // 1. Documents editor
  await run("documents", async () => {
    const r = {};
    if (!phone) {
      // click path from the dashboard
      await page.evaluate(() => switchTab("dashboard")); await page.waitForTimeout(600);
      let clicks = 0;
      await page.click('[data-tab="library"]'); clicks++; await page.waitForTimeout(800);
      await page.click('#library-subtabs [data-target="library-view-docs"]'); clicks++; await page.waitForTimeout(1200);
      const tc = Date.now(); r.rowClicked = await clickText(page, "Deep prose " + stamp); clicks++;
      await page.waitForFunction((id) => typeof currentDoc !== 'undefined' && currentDoc && currentDoc.id === id && document.querySelector('#tab-documents .cm-content')?.offsetParent, fx.doc, { timeout: 15000 });
      r.clickToEditorMs = Date.now() - tc; await page.waitForTimeout(1000);
      r.clicksToOpen = clicks; r.openedByClicks = await page.evaluate(`typeof currentDoc !== 'undefined' && !!currentDoc && currentDoc.id === ${fx.doc}`);
    }
    await page.evaluate(() => switchTab("documents")); await page.waitForTimeout(800);
    r.openMs = await timed(page, `loadDocuments(${fx.doc})`, `(() => { const e = document.querySelector('#tab-documents .cm-editor .cm-content'); return e && e.offsetParent && e.textContent.includes('Section 1') && currentDoc && currentDoc.id === ${fx.doc}; })()`);
    await page.waitForTimeout(1500);
    r.m = await page.evaluate(() => __m("#tab-documents"));
    // undo: type then Ctrl+Z
    await page.evaluate(() => { docCmView.focus(); docCmView.dispatch({ selection: { anchor: docCmView.state.doc.length } }); });
    const before = await page.evaluate(() => docCmView.state.doc.length);
    await page.keyboard.type(" extra words");
    await page.keyboard.press("Control+z"); await page.waitForTimeout(300);
    r.undoText = (await page.evaluate(() => docCmView.state.doc.length)) === before;
    await page.keyboard.press("Control+Shift+z"); await page.waitForTimeout(300);
    r.redoText = (await page.evaluate(() => docCmView.state.doc.length)) > before;
    r.paletteDocCmds = await page.evaluate(() => (typeof docPaletteCommands === "function" ? docPaletteCommands().length : -1));
    // toolbar/menus: count kebab menu items in the doc header menu if present
    r.menus = await page.evaluate(() => [...document.querySelectorAll('#tab-documents [aria-haspopup]')].filter((e) => e.offsetParent).length);
    return r;
  });

  // 2. Code editor
  await run("code", async () => {
    const r = {};
    await page.evaluate(() => switchTab("documents")); await page.waitForTimeout(500);
    r.openMs = await timed(page, `loadDocuments(${fx.code})`, `(() => { const e = document.querySelector('#tab-documents .cm-editor .cm-content'); return e && e.offsetParent && e.textContent.includes('def f0') && currentDoc && currentDoc.id === ${fx.code}; })()`);
    await page.waitForTimeout(1500);
    r.m = await page.evaluate(() => __m("#tab-documents"));
    r.cm = await page.evaluate(() => ({
      foldGutter: !!document.querySelector('#tab-documents .cm-foldGutter'),
      lineNumbers: !!document.querySelector('#tab-documents .cm-lineNumbers'),
      lint: !!document.querySelector('#tab-documents .cm-lint-marker, #tab-documents .cm-gutter-lint'),
      minimap: !!document.querySelector('#tab-documents .cm-minimap, #tab-documents [class*=minimap]'),
      runBtn: [...document.querySelectorAll('#tab-documents button')].filter((b) => b.offsetParent && /\bRun\b/.test(b.textContent + b.title)).length,
      paletteCmds: typeof docPaletteCommands === "function" ? docPaletteCommands().length : -1,
    }));
    // multi-cursor check: Ctrl+D (select next occurrence) and Alt+click
    await page.evaluate(() => { docCmView.focus(); const t = docCmView.state.doc.toString(); const i = t.indexOf('return'); docCmView.dispatch({ selection: { anchor: i, head: i + 6 } }); });
    await page.keyboard.press("Control+d"); await page.waitForTimeout(200);
    r.ctrlDRanges = await page.evaluate(() => docCmView.state.selection.ranges.length);
    await page.keyboard.press("Escape");
    // find/replace panel
    const js = await page.evaluate(async () => (await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "deep.js", content: "console.log(1)", file_type: "js" }) })).id);
    await page.evaluate(`loadDocuments(${js})`); await page.waitForTimeout(1500);
    r.jsRunButtons = await page.evaluate(() => [...document.querySelectorAll('#tab-documents button')].filter((b) => b.offsetParent && /\bRun\b/.test(b.textContent + ' ' + b.title + ' ' + (b.getAttribute('aria-label') || ''))).map((b) => (b.getAttribute('aria-label') || b.title || b.textContent).trim().slice(0, 30)));
    r.reopenProseMs = await timed(page, `loadDocuments(${fx.doc})`, `(() => { const e = document.querySelector('#tab-documents .cm-editor .cm-content'); return e && e.offsetParent && currentDoc && currentDoc.id === ${fx.doc} && docCmView.state.doc.length > 1000; })()`);
    await page.evaluate(`loadDocuments(${fx.code})`); await page.waitForTimeout(1500);
    await page.evaluate(() => { docCmView.focus(); }); await page.keyboard.press("Control+h"); await page.waitForTimeout(400);
    r.replacePanel = await page.evaluate(() => !!document.querySelector('#tab-documents .cm-search, .doc-find, [id*=doc-find]:not(.hidden)'));
    await page.keyboard.press("Escape");
    return r;
  });

  // 3. Whiteboard (and 4. map)
  const mkBoard = async (name, type) => page.evaluate(async ([n, t]) => (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: n, type: t }) })).id, [name, type]);
  await run("whiteboard", async () => {
    const r = {};
    const id = await mkBoard("Deep board " + stamp, "board");
    if (!phone) {
      await page.evaluate(() => switchTab("dashboard")); await page.waitForTimeout(600);
      let clicks = 0;
      await page.click('[data-tab="library"]'); clicks++; await page.waitForTimeout(800);
      await page.click('#library-subtabs [data-target="library-view-whiteboard"]'); clicks++; await page.waitForTimeout(2500);
      r.rowClicked = await clickText(page, "Deep board " + stamp); clicks++;
      await page.waitForTimeout(2500);
      r.clicksToOpen = clicks; r.openedByClicks = await page.evaluate(() => !!document.getElementById("wb-topbar")?.offsetParent);
    } else {
      await page.evaluate(() => switchTab("library")); await page.waitForTimeout(800);
      await page.evaluate(() => document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click()); await page.waitForTimeout(3000);
    }
    const id2 = await mkBoard("Deep board two " + stamp, "board");
    r.openMs = await timed(page, `openWhiteboardBoard(${id2})`, `(() => { const b = document.getElementById('wb-topbar'); const c = document.getElementById('whiteboard-container'); return b && b.offsetParent && c && c.offsetParent && window.currentBoardId == ${id2}; })()`);
    await page.waitForTimeout(1500);
    r.m = await page.evaluate(() => __m("#library-view-whiteboard"));
    r.topbar = await page.evaluate(() => __m("#wb-topbar")?.controls);
    return r;
  });
  await run("map", async () => {
    const r = {};
    let clicks = 0;
    if (!phone) {
      await page.evaluate(() => switchTab("dashboard")); await page.waitForTimeout(600);
      await page.evaluate(() => document.querySelector('[data-tab="library"]').click()); clicks++; await page.waitForTimeout(800);
      await page.evaluate(() => { const b = document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]'); b.click(); if (typeof wbShowBoardsLanding === "function") wbShowBoardsLanding(); }); clicks++; await page.waitForTimeout(1500);
    } else {
      await page.evaluate(() => { switchTab("library"); document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]')?.click(); }); await page.waitForTimeout(1500);
    }
    await page.evaluate(() => document.getElementById("wb-boards-new").click()); clicks++; await page.waitForTimeout(800);
    await page.fill("#wb-template-name", "Deep map " + stamp);
    await page.evaluate(() => document.querySelector('#wb-template-kind button[data-value="map"]').click()); clicks++;
    const t0 = Date.now();
    await page.evaluate(() => document.getElementById("wb-template-create").click()); clicks++;
    await page.waitForFunction(() => window.currentBoardId && document.querySelectorAll('#whiteboard-container .wb-object').length > 0, null, { timeout: 15000 });
    r.createToFirstTopicMs = Date.now() - t0;
    r.clicksToNewMap = clicks;
    await page.keyboard.press("Escape");
    await page.waitForTimeout(1200);
    const add = await page.evaluate(async () => {
      try { const root = wbMapIndex().roots[0]; for (let i = 0; i < 4; i++) await wbMapAddChild(root.id); return wbMapIndex().nodes.length; } catch (e) { return String(e); }
    });
    await page.waitForTimeout(1500);
    r.nodes = add;
    r.m = await page.evaluate(() => __m("#library-view-whiteboard"));
    r.topbar = await page.evaluate(() => __m("#wb-topbar")?.controls);
    r.mapPaletteCmds = await page.evaluate(() => (typeof mapPaletteCommands === "function" ? mapPaletteCommands().length : -1));
    // undo add child
    const n0 = await page.evaluate(() => wbMapIndex().nodes.length);
    await page.evaluate(async () => { await wbUndo(); }); await page.waitForTimeout(600);
    r.undoAddChild = (await page.evaluate(() => wbMapIndex().nodes.length)) === n0 - 1;
    await page.evaluate(async () => { await wbRedo(); }); await page.waitForTimeout(600);
    r.redoAddChild = (await page.evaluate(() => wbMapIndex().nodes.length)) === n0;
    // perf: time to add 50 topics
    const t = await page.evaluate(async () => { const t0 = performance.now(); const root = wbMapIndex().roots[0]; for (let i = 0; i < 20; i++) await wbMapAddChild(root.id); return Math.round((performance.now() - t0) / 20); });
    r.msPerAddChild = t;
    return r;
  });

  // 5. OCR workspace
  await run("ocr", async () => {
    const r = {};
    const scan = await page.context().newPage();
    await scan.setViewportSize({ width: 900, height: 400 });
    await scan.setContent('<body style="font:28px serif;padding:30px;background:#fff"><h1>Lecture 4: memory</h1><p>Spaced repetition beats cramming for long term recall.</p><p>Read chapter 7 before Friday.</p></body>');
    const png = (await scan.screenshot({ type: "png" })).toString("base64");
    await scan.close();
    const media = await page.evaluate(async (b64) => {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const fd = new FormData();
      fd.append("file", new File([bytes], `deep-ocr-${Date.now()}.png`, { type: "image/png" }));
      fd.append("direct", "true");
      const res = await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } });
      return res.json();
    }, png);
    await page.evaluate(() => switchTab("library")); await page.waitForTimeout(1200);
    r.openMs = await timed(page, `(async () => { const row = await apiJson('/media/meta/' + encodeURIComponent('${media.url}'.split('/').pop())); openOcrWorkspace({ ...row, _isImage: true }, [{ ...row, _isImage: true }]); })()`, `(() => { const w = document.getElementById('ocr-workspace'); const img = w && w.querySelector('img'); return w && !w.classList.contains('hidden') && img && img.complete && img.naturalWidth > 0; })()`);
    await page.waitForTimeout(2500);
    r.m = await page.evaluate(() => __m("#ocr-workspace"));
    r.engine = await page.evaluate(() => (document.getElementById("ocr-engine")?.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160));
    r.readers = await page.evaluate(() => [...document.querySelectorAll('#ocr-workspace button')].filter((b) => b.offsetParent).map((b) => (b.getAttribute('aria-label') || b.textContent).trim().slice(0, 24)).join(' / ').slice(0, 900));
    r.paletteOcr = await page.evaluate(() => paletteCommands().filter((c) => /ocr|read text|read a document/i.test(c.label)).map((c) => c.label));
    r.quickAccessOcr = await page.evaluate(() => [...document.querySelectorAll('.quick-access *, #quick-access *')].some((e) => /OCR|Read text/i.test(e.textContent || '')));
    await page.evaluate(() => closeOcrWorkspace()); await page.waitForTimeout(300);
    return r;
  });

  // 6. Meetings
  await run("meetings", async () => {
    const r = {};
    await page.evaluate(() => switchTab("dashboard")); await page.waitForTimeout(800);
    if (!phone) {
      r.newMs = await timed(page, `document.querySelector('.quick-action[data-action], .quick-action') && [...document.querySelectorAll('.quick-action')].find((b) => /New meeting/.test(b.textContent)).click()`, `(() => { const b = document.getElementById('meeting-new-create'); return b && b.offsetParent; })()`);
    } else {
      r.newMs = await timed(page, `openNewMeeting({})`, `(() => { const b = document.getElementById('meeting-new-create'); return b && b.offsetParent; })()`);
    }
    await page.waitForTimeout(600);
    r.newForm = await page.evaluate(() => __m(document.getElementById('meeting-new-create').closest('.modal-card, .sheet-card, .card')));
    await page.evaluate(() => { const t = document.querySelector('#meeting-new-title, [id^=meeting-new] input[type=text]'); if (t) t.value = 'Deep sync'; });
    await page.click('#meeting-new-create'); await page.waitForTimeout(2500);
    const entryId = await page.evaluate(() => editingId);
    r.entryId = entryId;
    await page.evaluate(() => { try { editingId = null; noteFormDirty = false; renderEntries(); } catch (e) {} });
    await page.waitForTimeout(800);
    r.sheetMs = await timed(page, `openMeetingSheet(${entryId})`, `(() => { const c = document.querySelector('.meeting-view'); return c && c.offsetParent; })()`);
    await page.waitForTimeout(800);
    r.sheet = await page.evaluate(() => __m(document.querySelector('.meeting-view')));
    r.sheetButtons = await page.evaluate(() => [...document.querySelectorAll('.meeting-view button')].filter((b) => b.offsetParent).map((b) => (b.getAttribute('aria-label') || b.textContent).trim().slice(0, 22)).join(' / '));
    await page.keyboard.press("Escape"); await page.waitForTimeout(500);
    r.recMs = await timed(page, `openMeetingRecorder()`, `(() => { const o = document.getElementById('meeting-overlay'); return o && !o.classList.contains('hidden') && document.getElementById('meeting-record').offsetParent; })()`);
    await page.waitForTimeout(800);
    r.recorder = await page.evaluate(() => __m('#meeting-card'));
    r.recorderStatus = await page.evaluate(() => (document.getElementById('meeting-status')?.textContent || '').trim().slice(0, 200));
    r.recordDisabled = await page.evaluate(() => document.getElementById('meeting-record').disabled);
    await page.evaluate(() => document.getElementById('meeting-record').click()); await page.waitForTimeout(1500);
    r.afterRecordStatus = await page.evaluate(() => (document.getElementById('meeting-status')?.textContent || '').trim().slice(0, 200));
    await page.evaluate(() => closeMeetingRecorder()); await page.waitForTimeout(300);
    r.dictation = await page.evaluate(() => typeof toggleDictation === "function");
    r.speech = await page.evaluate(() => ({ webSpeech: "webkitSpeechRecognition" in window || "SpeechRecognition" in window, tts: "speechSynthesis" in window }));
    return r;
  });
  out.toasts = toasts.slice(0, 12);
  console.log(JSON.stringify(out));
  await browser.close();
})();
