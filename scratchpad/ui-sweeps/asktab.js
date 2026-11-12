// The Ask sub-tab in notes, four owner reports in one pass (CHAT_PLAN,
// "Placed from INBOX, 2026-09-21", INBOX 297 to 300).
//
//   297  "make sure there are appropriate gaps between uploaded files and
//         attachments and the badges and make sure all the badges show"
//   298  "there's no generating animation while the model is thinking and
//         streaming in the ask tab either"
//   299  "can the notes in the matching records that appear in the ask tab be
//         numbered accordingly to match the inline referencing??"
//   300  "fix the ui of this sources button in the ask tab"
//
// **Every finding here is a number, never a screenshot.** The four reports
// are about one row of chips, one animation, two numberings and one box, and
// each of those is a rect or a computed style. A capture would show all four
// and prove none of them.
//
// Nothing in `tests/` can see any of it: the badge row is built by
// `entryItem` at runtime from an entry's own fields, the busy affordance is a
// class added during a stream, the record numbers come from `citationNumbers`
// against prose that has to exist, and the sources control's shape is CSS.
//
// This sandbox has no model, so the stream is driven by
// `scratchpad/fake_answer_server.py` (the same stand-in `askgrounding.js`
// uses: it answers with sentences built from the notes it was given, so the
// grounding is real rather than canned). It is started here rather than
// required from outside, so `scripts/gate.sh --sweeps` needs nothing but a
// running app.
//
//   BASE=http://127.0.0.1:8802 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/asktab.js
const { boot } = require('./lib.js');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const ROOT = path.resolve(__dirname, '..', '..');
// Absolute, and never a symlink into the worktree: a `.venv` link committed
// from a worktree destroyed the real environment once tonight.
// CI has no .venv: it exports VENV (sys.prefix of its Python), as serve.sh reads.
const PY = process.env.SWEEP_PY || path.join(process.env.VENV || path.resolve(ROOT, '.venv'), 'bin', 'python');
const FAKE_PORT = Number(process.env.FAKE_PORT || 8811);
const FAKE = `http://127.0.0.1:${FAKE_PORT}/v1`;
// Slow enough that a stream is a state the page is *in* rather than an event
// that has already finished: the busy affordance is only measurable while the
// stream is open, and the fixture used to send a whole answer inside one tick.
const FAKE_DELAY_MS = Number(process.env.FAKE_DELAY_MS || 260);

// Distinct vocabulary per note: grounding scores by shared words, so notes
// that rhyme would make a wrong attribution look right.
const NOTES = [
  { content: 'The sourdough starter is fed with rye flour every morning at seven.',
    category: 'Courses & Study', tags: ['baking', 'kitchen'] },
  { content: 'My hiking boots need resoling before the Snowdon trip in October.',
    category: 'Courses & Study', tags: ['gear'] },
  { content: 'The garage door opener responds to the blue remote but not the grey one.',
    category: 'Courses & Study', tags: [] },
];

function waitForFake() {
  return new Promise((resolve) => {
    let tries = 0;
    const poke = () => {
      const req = http.get(`http://127.0.0.1:${FAKE_PORT}/v1/models`, (res) => {
        res.resume();
        resolve(true);
      });
      req.on('error', () => (++tries > 40 ? resolve(false) : setTimeout(poke, 250)));
    };
    poke();
  });
}

(async () => {
  const fake = spawn(PY, [path.join(ROOT, 'scratchpad', 'fake_answer_server.py'), String(FAKE_PORT)],
    { cwd: ROOT, env: { ...process.env, FAKE_DELAY_MS: String(FAKE_DELAY_MS) }, stdio: 'ignore' });
  const fakeUp = await waitForFake();
  const findings = [];
  const numbers = {};
  const { page, browser } = await boot({});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(2500);

  // --- seed -----------------------------------------------------------------
  // One note carries a file attachment, which is the row in the owner's
  // screenshot: a file chip with a download button sitting over the badges.
  const seeded = await page.evaluate(async ({ notes, base }) => {
    const made = [];
    for (const note of notes) {
      const entry = await apiJson('/entries', {
        method: 'POST',
        body: JSON.stringify({ content: note.content, category: note.category, tags: note.tags }),
      });
      made.push(entry.id);
    }
    // A real upload through the real route: an attachment built by hand in
    // the page would not carry the size or the id the chip prints.
    const form = new FormData();
    form.append('file', new File(['lecture notes on agents'], 'cab432_lecture_agents.pdf',
      { type: 'application/pdf' }));
    // The same raw fetch the app's own uploader makes: `api()` forces a JSON
    // content type, which multipart must not have (422), and a bare fetch
    // with no `X-Auth-Token` is a 401. Both were measured here in one run.
    await fetch(`/entries/${made[0]}/files`, {
      method: 'POST',
      headers: { 'X-Auth-Token': authToken(), 'X-Workspace-ID': activeSpaceId() },
      body: form,
    }).catch(() => null);
    const provider = await api('/models/provider', {
      method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: base }),
    }).then((r) => r.json()).catch(() => null);
    await api('/models/chat-model', {
      method: 'POST', body: JSON.stringify({ name: 'fake-answerer' }),
    }).catch(() => null);
    return { ids: made, provider: provider && provider.provider, reachable: provider && provider.reachable };
  }, { notes: NOTES, base: FAKE });
  console.log('seeded:', JSON.stringify(seeded), 'fake up:', fakeUp);

  // Notes, then its Ask sub-tab. **Not the Chat tab**: `#ask` lives inside
  // `#tab-notes`, and a probe that switched to Chat measured every rect in
  // this file at 0 for a run, which is the display:none trap this codebase
  // has been caught by five times.
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(700);

  // **The same note, in the list the owner reads it in everywhere else.**
  // "Make sure all the badges show" has three possible causes and they need
  // three different fixes: a truncation, a wrap, or a condition that never
  // fires. This is the third: the Ask column builds its rows through
  // `clickableResult`, which calls `entryItem` with no options at all, so
  // every chip gated on `options.actions` is missing from a row that is
  // otherwise the same note. Browse is the control group.
  await page.evaluate(() => window.showNotesSection && showNotesSection('browse'));
  // The list on screen was rendered at boot, before this probe wrote its
  // notes: without this it is a stale page and the control row is simply not
  // in it, which reads exactly like a row that draws no chips.
  await page.evaluate(() => window.loadEntries && loadEntries());
  // Waited for, not slept through: the note list renders in chunks, so a
  // fixed pause read an empty `#entry-list` and reported no control row.
  await page.waitForSelector(`#entry-list li[data-id="${seeded.ids[2]}"]`, { timeout: 20000 })
    .catch(() => null);
  await page.waitForTimeout(700);
  const browse = await page.evaluate((id) => {
    const li = document.querySelector(`#entry-list li[data-id="${id}"]`);
    if (!li) return null;
    return [...li.querySelectorAll('.entry-meta .chip:not([hidden])')]
      .map((c) => c.textContent.replace(/\s+/g, ' ').trim());
  }, seeded.ids[2]);
  // The one chip that is deliberately not carried over: "Tag with Atlas" is a
  // model call, which is an action, and a search result row is read-only
  // (CHAT_PLAN's decision for INBOX 297). Named by class rather than by its
  // words so a rewording does not quietly widen the exception.
  const ACTION_ONLY = ['untagged-ai'];
  const browseUntagged = await page.evaluate((id) => {
    const li = document.querySelector(`#entry-list li[data-id="${id}"]`);
    return li ? [...li.querySelectorAll('.entry-meta .chip:not([hidden])')]
      .map((c) => ({ text: c.textContent.replace(/\s+/g, ' ').trim(), cls: c.className })) : null;
  }, seeded.ids[2]);
  console.log(`297 browse row (the note with no tags): ${JSON.stringify(browse)}`);

  await page.evaluate(() => window.showNotesSection && showNotesSection('ask'));
  await page.waitForTimeout(900);

  // --- 297: the gap, and every badge the data implies -----------------------
  // `renderChatMeta` is the real renderer the Ask tab calls when its results
  // land, given a real entry payload with one field set that no model is here
  // to set (`ai_confidence`, the "AI 72%" chip in the report). Measuring the
  // renderer against data it will really be handed is the point; inventing
  // the row in the probe would measure the probe.
  const row = await page.evaluate(async (ids) => {
    const entries = await apiJson('/entries');
    const mine = ids.map((id) => entries.find((e) => e.id === id)).filter(Boolean);
    if (!mine.length) return { ok: false, why: 'seeded notes did not come back' };
    mine[0] = { ...mine[0], ai_confidence: 72, user_filed: false };
    renderChatMeta({
      raw_results: mine, search_mode: 'hybrid', connected_ids: [], match_info: {},
      answered_by: 'fake-answerer', ollama_running: true,
    });
    // The record card replaces the note card's chips a moment after the rows land (`replyRecordCards`).
    await new Promise((r) => setTimeout(r, 500));
    const li = document.querySelector(`#raw-results li[data-id="${mine[0].id}"]`);
    if (!li) return { ok: false, why: 'no row rendered for the attached note' };
    const links = li.querySelector('.entry-links, .disclosure-row');
    const meta = li.querySelector('.record-meta');
    const gap = links && meta
      ? Math.round((meta.getBoundingClientRect().top - links.getBoundingClientRect().bottom) * 10) / 10
      : null;

    // What the data says the row must carry, from the same fields `entryItem`
    // reads. A count alone would hide *which* one is missing, which is the
    // half of "make sure all the badges show" that decides the fix.
    const entry = mine[0];
    // Ask's Matching records are record cards now (INBOX 1735, DESIGN.md): one facts line,
    // `.record-meta`, carries the category and the date, and the tags, files and dates stay on the
    // note itself. So what the data implies for this row is the category and the date.
    const want = [entry.category];

    const liBox = li.getBoundingClientRect();
    // A chip folded into "+N" is [hidden], not a badge that failed to draw.
    const chips = [...li.querySelectorAll('.record-meta > span:not([hidden])')].map((c) => {
      const r = c.getBoundingClientRect();
      return {
        text: c.textContent.replace(/\s+/g, ' ').trim(),
        w: Math.round(r.width), h: Math.round(r.height),
        // Off the row's own box, or zero-sized: two different ways a badge
        // that exists in the DOM is not a badge anybody can read.
        clipped: r.width < 1 || r.height < 1 || r.right > liBox.right + 1 || r.left < liBox.left - 1,
      };
    });
    // A tag folded into "+N" is still on the card (its menu lists it).
    const folded = [];
    const shown = chips.map((c) => c.text).concat(folded).join(' | ');
    const missing = want.filter((label) => !shown.includes(String(label)));
    // A lane that scrolls is a lane that hides: the same measurement for the
    // meta row itself, since a chip inside an overflowing box has a rect on
    // the page whether or not it is in view.
    const overflow = meta
      ? { scrollW: meta.scrollWidth, clientW: meta.clientWidth, overflowX: getComputedStyle(meta).overflowX }
      : null;
    return {
      ok: true, gap, want, missing,
      chips: chips.map((c) => c.text),
      clipped: chips.filter((c) => c.clipped).map((c) => c.text),
      overflow,
      linksH: links ? Math.round(links.getBoundingClientRect().height) : null,
      metaMarginTop: meta ? getComputedStyle(meta).marginTop : null,
      linksMarginBottom: links ? getComputedStyle(links).marginBottom : null,
    };
  }, seeded.ids);
  if (!row.ok) findings.push(`297: ${row.why}`);
  else {
    numbers.gapAttachmentsToBadges = row.gap;
    numbers.badgesImplied = row.want.length;
    numbers.badgesShown = row.chips.length;
    console.log(`297 gap attachments -> badges: ${row.gap}px ` +
      `(.entry-links margin-bottom ${row.linksMarginBottom}, .entry-meta margin-top ${row.metaMarginTop})`);
    console.log(`297 badges implied ${row.want.length}: ${JSON.stringify(row.want)}`);
    console.log(`297 badges shown   ${row.chips.length}: ${JSON.stringify(row.chips)}`);
    console.log(`297 meta lane: ${JSON.stringify(row.overflow)}`);
    // A file row touching the badges under it is the report. One step of the
    // scale is the floor: anything under it is the two rows reading as one.
    if (row.gap !== null && row.gap < 6) findings.push(`297: ${row.gap}px between the attachment row and the badge row`);
    if (row.missing.length) findings.push(`297: badges the data implies but nothing draws: ${JSON.stringify(row.missing)}`);
    if (row.clipped.length) findings.push(`297: badges drawn outside the row's own box: ${JSON.stringify(row.clipped)}`);
  }

  // The same note, in the Ask column, chip for chip against Browse.
  const askSame = await page.evaluate((id) => {
    const li = document.querySelector(`#raw-results li[data-id="${id}"]`);
    return li ? [...li.querySelectorAll('.record-meta > span:not([hidden])')]
      .map((c) => c.textContent.replace(/\s+/g, ' ').trim()) : null;
  }, seeded.ids[2]);
  console.log(`297 ask row    (the same note):        ${JSON.stringify(askSame)}`);
  if (browse && askSame) {
    const actionOnly = new Set((browseUntagged || [])
      .filter((c) => ACTION_ONLY.some((name) => c.cls.split(/\s+/).includes(name)))
      .map((c) => c.text));
    // "Add tags" (a control in Browse) is "No tags yet" in Ask, where the row is read-only.
    const same = (t) => (t === 'Add tags' ? 'No tags yet' : t);
    // A record card keeps the category and the date only (INBOX 1735): the tags and the Browse
    // controls ("Add tags") are not on it by design, so the category is what must carry across.
    const lost = browse.slice(0, 1).filter((b) => !askSame.map(same).includes(same(b)) && !actionOnly.has(b));
    numbers.badgesInBrowse = browse.length;
    numbers.badgesInAsk = askSame.length;
    numbers.badgesLostInAsk = lost;
    if (lost.length) findings.push(`297: badges this note carries in Browse and not in Ask: ${JSON.stringify(lost)}`);
  } else if (!browse) {
    console.log('297: the control row was not found in Browse, so no comparison was made');
  }
  console.log(`297 browse chip classes: ${JSON.stringify((browseUntagged || []).map((c) => c.cls))}`);

  // And the same row at the widths the column actually narrows to. "Make sure
  // all the badges show" can be a truncation rather than a missing chip, and a
  // lane that scrolls or a chip drawn past the card's edge is only visible as
  // a number at the width where it happens.
  numbers.narrow = {};
  for (const width of [1024, 820, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(500);
    const at = await page.evaluate((id) => {
      const li = document.querySelector(`#raw-results li[data-id="${id}"]`);
      if (!li) return null;
      const meta = li.querySelector('.record-meta');
      const links = li.querySelector('.entry-links, .disclosure-row');
      const box = li.getBoundingClientRect();
      const chips = [...li.querySelectorAll('.record-meta > span:not([hidden])')];
      const cut = chips.filter((c) => {
        const r = c.getBoundingClientRect();
        return r.width < 1 || r.right > box.right + 1 || r.left < box.left - 1;
      }).map((c) => c.textContent.replace(/\s+/g, ' ').trim());
      return {
        shown: chips.length,
        cut,
        hiddenByOverflow: meta ? meta.scrollWidth - meta.clientWidth : 0,
        gap: links && meta
          ? Math.round((meta.getBoundingClientRect().top - links.getBoundingClientRect().bottom) * 10) / 10
          : null,
      };
    }, seeded.ids[0]);
    numbers.narrow[width] = at;
    console.log(`297 at ${width}: ${JSON.stringify(at)}`);
    if (at && at.cut.length) findings.push(`297: at ${width}px, badges drawn outside the card: ${JSON.stringify(at.cut)}`);
    if (at && at.hiddenByOverflow > 0) findings.push(`297: at ${width}px, ${at.hiddenByOverflow}px of the badge lane is scrolled out of sight`);
    if (at && at.gap !== null && at.gap < 6) findings.push(`297: at ${width}px, ${at.gap}px between the attachment row and the badge row`);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(400);

  // --- 298: is anything moving while the model writes? ----------------------
  // Polled during a real stream, not asserted after it: the affordance the
  // report is about only exists between the first request and the last token.
  await page.evaluate(() => {
    window.__busy = [];
    const look = () => {
      const answer = document.getElementById('ai-answer');
      const streaming = !!answer && answer.classList.contains('is-streaming');
      const asking = !document.getElementById('stop-btn')?.classList.contains('hidden');
      if (!asking && !streaming) return requestAnimationFrame(look);
      // Anywhere on this surface, not only in the answer box: the point of
      // the report is that *nothing* moves, so the probe must not be fussy
      // about which of the app's indicators is the one doing the moving.
      const dots = document.querySelector(
        '#ai-answer .typing-dots, #ai-answer .typing-label, #ask-status .typing-dots, #ask-status .progress-line');
      const spinner = document.querySelector('#chat-results .spinner, #ask-status .spinner, .ask-composer .spinner');
      const busyChip = document.querySelector('#chat-results .chip-busy, #ask-status .chip-busy');
      const vis = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
      };
      window.__busy.push({
        t: Math.round(performance.now()),
        streaming,
        generating: !!answer && answer.classList.contains('is-generating'),
        // The ring is a CSS animation on the answer box itself, so it has no
        // element to find: the computed animation name is the only honest
        // way to say whether it is actually running.
        ring: !!answer && /generating-glow/.test(getComputedStyle(answer).animationName || ''),
        dots: vis(dots),
        spinner: vis(spinner),
        busyChip: vis(busyChip),
        status: (document.getElementById('ask-status')?.textContent || '').trim(),
        // The progress line is a two-row grid (indicator, then the label with
        // the musing under it): its own box says whether it laid out as that
        // or collapsed into one run-on sentence.
        statusH: Math.round(document.getElementById('ask-status')?.getBoundingClientRect().height || 0),
        lineW: Math.round(document.querySelector('#ask-status .progress-line')?.getBoundingClientRect().width || 0),
      });
      requestAnimationFrame(look);
    };
    requestAnimationFrame(look);
  });

  const asked = await page.evaluate(() => {
    const box = document.getElementById('question');
    if (!box) return false;
    box.value = 'What do my notes say about the starter and the boots?';
    document.getElementById('ask-btn')?.click();
    return true;
  });
  if (!asked) findings.push('298/299: no #question box to ask with');

  await page.waitForFunction(() => {
    const a = document.getElementById('ai-answer');
    return a && a.textContent.trim().length > 20 && !a.classList.contains('is-streaming');
  }, { timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(2500);

  const busy = await page.evaluate(() => window.__busy || []);
  const frames = busy.length;
  const withSomething = busy.filter((b) => b.dots || b.spinner || b.busyChip).length;
  const streamFrames = busy.filter((b) => b.streaming);
  const streamWith = streamFrames.filter((b) => b.dots || b.spinner || b.busyChip).length;
  numbers.busyFramesTotal = frames;
  numbers.busyFramesWithAffordance = withSomething;
  numbers.streamFrames = streamFrames.length;
  numbers.streamFramesWithAffordance = streamWith;
  console.log(`298 frames observed while asking: ${frames}, of them showing a busy affordance: ${withSomething}`);
  console.log(`298 frames with the answer actually streaming: ${streamFrames.length}, ` +
    `of them showing one: ${streamWith}`);
  const statusH = Math.max(0, ...busy.map((b) => b.statusH || 0));
  const lineW = Math.max(0, ...busy.map((b) => b.lineW || 0));
  numbers.statusBoxTallest = statusH;
  numbers.progressLineWidest = lineW;
  console.log(`298 ask status box, tallest during the turn: ${statusH}px; progress line widest: ${lineW}px`);
  const ringFrames = streamFrames.filter((b) => b.ring).length;
  numbers.streamFramesWithRing = ringFrames;
  console.log(`298 streaming frames with the generating ring running: ${ringFrames}`);
  console.log(`298 last status line: ${JSON.stringify(busy.length ? busy[busy.length - 1].status : '')}`);
  // The generating ring on the answer box is the affordance once text streams.
  if (frames && withSomething === 0 && ringFrames === 0) findings.push('298: nothing on screen moves while the answer is being produced');
  else if (streamFrames.length && streamWith === 0 && ringFrames < streamFrames.length) {
    findings.push(`298: the affordance stops at the first token (${streamFrames.length} streaming frames with none)`);
  }
  if (!frames) findings.push('298: the ask never reached a busy state, so nothing could be measured');

  // --- 299: one numbering, two places ---------------------------------------
  const cites = await page.evaluate(() => {
    const marks = [...document.querySelectorAll('#ai-answer .answer-citation')].map((m) => ({
      n: Number(m.textContent.replace(/\D/g, '')),
      noteId: m.dataset.noteId || m.querySelector('[data-note-id]')?.dataset.noteId || null,
      label: (m.textContent || '').trim(),
    }));
    const rows = [...document.querySelectorAll('#raw-results li[data-id]')].map((li, i) => {
      const mark = li.querySelector('.chat-source-index, .record-index');
      const r = mark ? mark.getBoundingClientRect() : null;
      // A number pinned into a gutter is only right if the gutter is really
      // reserved: the row's own text must start to the right of the mark, not
      // under it.
      const body = li.querySelector('.entry-title, .entry-content');
      const br = body ? body.getBoundingClientRect() : null;
      return {
        pos: i + 1,
        id: li.dataset.id,
        n: mark ? Number(mark.textContent.replace(/\D/g, '')) : null,
        visible: !!r && r.width > 0 && r.height > 0,
        // Horizontal intersection: the number sits in a gutter on either side.
        // Both axes, against the words' own line boxes: the card puts the number in a corner of a
        // body box that spans the card (INBOX 1735), so the box overlapping it is not the words.
        overlap: r && body ? Math.round(Math.max(0, ...[...(() => { const g = document.createRange(); g.selectNodeContents(body); return g.getClientRects(); })()].map((t) => Math.min(r.right, t.right) - Math.max(r.left, t.left) > 0 && Math.min(r.bottom, t.bottom) - Math.max(r.top, t.top) > 0 ? Math.min(r.right, t.right) - Math.max(r.left, t.left) : 0)) * 10) / 10 : null,
      };
    });
    return { marks, rows };
  });
  const numbered = cites.rows.filter((r) => r.n && r.visible).length;
  numbers.recordsRendered = cites.rows.length;
  numbers.recordsNumbered = numbered;
  numbers.inlineMarks = cites.marks.length;
  console.log(`299 inline marks: ${cites.marks.length} ${JSON.stringify(cites.marks)}`);
  console.log(`299 record rows: ${cites.rows.length}, numbered: ${numbered} ${JSON.stringify(cites.rows)}`);
  const overlapping = cites.rows.filter((r) => r.overlap !== null && r.overlap > 0.5);
  numbers.recordNumberOverlaps = overlapping.length;
  if (overlapping.length) {
    findings.push(`299: ${overlapping.length} record number(s) drawn over the row's own text ` +
      `(worst ${Math.max(...overlapping.map((r) => r.overlap))}px)`);
  }
  if (!cites.marks.length) findings.push('299: no inline citation marks, so there is nothing to match');
  else if (!numbered) findings.push('299: the matching records carry no numbers at all');
  else {
    // The real question: does the row a mark points at carry that mark's own
    // digit? Compared by note id, which is the only thing both sides share.
    const byId = new Map(cites.rows.filter((r) => r.n).map((r) => [String(r.id), r.n]));
    const disagree = cites.marks.filter((m) => m.noteId && byId.has(String(m.noteId))
      && byId.get(String(m.noteId)) !== m.n);
    numbers.numberDisagreements = disagree.length;
    if (disagree.length) findings.push(`299: ${disagree.length} mark(s) numbered differently from their own record row`);
    const cited = cites.marks.filter((m) => m.noteId).length;
    if (cited && !cites.marks.some((m) => m.noteId && byId.has(String(m.noteId)))) {
      findings.push('299: no cited note has a numbered row beside it');
    }
  }

  // --- 300: the sources control ---------------------------------------------
  const sources = await page.evaluate(() => {
    const el = document.querySelector('.ask-sources-line');
    if (!el) return { present: false };
    const r = el.getBoundingClientRect();
    const col = el.closest('.chat-half') || el.parentElement;
    const cr = col.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      present: true,
      tag: el.tagName.toLowerCase(),
      text: el.textContent.replace(/\s+/g, ' ').trim(),
      w: Math.round(r.width), h: Math.round(r.height),
      colW: Math.round(cr.width),
      share: Math.round((r.width / cr.width) * 1000) / 10,
      display: cs.display, width: cs.width, justify: cs.justifyContent,
      title: el.getAttribute('title') || '',
      ariaControls: el.getAttribute('aria-controls') || '',
    };
  });
  console.log('300 sources control:', JSON.stringify(sources));

  // **And pressing it has to do something.** The whole objection in the
  // report is that the control described a place instead of acting, so the
  // measurement is the page moving: the first cited record's distance from
  // the top of the window, before the press and after it.
  const acted = await page.evaluate(async () => {
    const el = document.querySelector('.ask-sources-line');
    const first = document.querySelector('#raw-results li[data-id]');
    if (!el || !first) return null;
    // Shrunk first, so the column really is out of reach and a press has
    // somewhere to move to: on a tall window everything is already in view
    // and a control that works would measure the same as one that does not.
    const scroller = (() => {
      let n = first.parentElement;
      while (n && n !== document.body) {
        const st = getComputedStyle(n);
        if (/(auto|scroll)/.test(st.overflowY) && n.scrollHeight > n.clientHeight + 1) return n;
        n = n.parentElement;
      }
      return document.scrollingElement || document.documentElement;
    })();
    const before = Math.round(scroller.scrollTop);
    const beforeTop = Math.round(first.getBoundingClientRect().top);
    el.click();
    await new Promise((r) => setTimeout(r, 400));
    return {
      scrollBefore: before,
      scrollAfter: Math.round(scroller.scrollTop),
      rowTopBefore: beforeTop,
      rowTopAfter: Math.round(first.getBoundingClientRect().top),
      scroller: `${scroller.tagName}#${scroller.id || ''}`,
    };
  });
  console.log('300 what the press did:', JSON.stringify(acted));
  if (acted) {
    numbers.sourcesPressMovedPage = Math.abs(acted.rowTopAfter - acted.rowTopBefore);
  }
  if (sources.present) {
    numbers.sourcesWidthPct = sources.share;
    numbers.sourcesWidthPx = sources.w;
    // A control the width of the column it sits in is a banner. The number is
    // the report: a pill spanning the answer column reads as a heading for
    // what is under it rather than as something to press.
    if (sources.share > 70) findings.push(`300: the sources control spans ${sources.share}% of its column (${sources.w}px of ${sources.colW}px)`);
    if (/on the right/i.test(sources.text)) findings.push(`300: the control describes where to look rather than what it does: "${sources.text}"`);
  } else {
    // The owner removed the button (16ccf9d79: each cited note shows once), so
    // there is nothing to measure; it is a note, not a finding.
    console.log('300: no .ask-sources-line (removed by the owner, 16ccf9d79)');
  }

  if (errors.length) findings.push(`${errors.length} page error(s): ${errors.slice(0, 2)}`);
  console.log('NUMBERS ' + JSON.stringify(numbers));
  for (const line of findings) console.log(`    ${line}`);
  console.log(findings.length ? `FAIL: ${findings.length} findings` : 'PASS: 0 findings');
  await browser.close();
  fake.kill();
  process.exit(findings.length ? 1 : 0);
})().catch((e) => { console.log('ERR ' + e.message); process.exit(1); });
