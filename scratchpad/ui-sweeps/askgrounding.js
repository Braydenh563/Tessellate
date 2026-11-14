// INBOX 267, written twice by the owner: "In-text referencing and grounding
// in the ask subtab doesn't stick, the wrong numbers will be used and in the
// wrong spot, and the numbers wont match the grounding" and "Grounding and
// in-text referencing not working now?? Needs fix."
//
// **Nothing in the suite can see this.** `tests/test_inline_citations.py`
// greps app.js: it proves `addInlineCitations` exists and is called with the
// right arguments, which is exactly as true when the feature is broken. So
// this drives a real Ask against a stand-in model
// (`scratchpad/fake_answer_server.py`, which answers with sentences built
// from the notes it was given, so grounding has something real to match) and
// reads what actually lands on the page.
//
// Three questions, which are the owner's three:
//   1. Do inline markers appear at all?
//   2. Are they in the right spot: does the marker on a sentence point at
//      the note that sentence came from?
//   3. Do the three numberings agree: the markers in the prose, the
//      "Grounded in" chips, and the Sources panel?
//
//   BASE=http://127.0.0.1:8803 FAKE=http://127.0.0.1:8809/v1 \
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node askgrounding.js
const { boot } = require('./lib.js');

const FAKE = process.env.FAKE || 'http://127.0.0.1:8809/v1';

// Distinctive on purpose: grounding scores by shared meaningful words, so
// notes that share vocabulary would make a wrong attribution look right.
const NOTES = [
  'The sourdough starter is fed with rye flour every morning at seven.',
  'My hiking boots need resoling before the Snowdon trip in October.',
  'The garage door opener responds to the blue remote but not the grey one.',
];

(async () => {
  const { page, browser } = await boot({});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(3500);

  const wired = await page.evaluate(async ({ base, notes }) => {
    for (const content of notes) {
      await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content, category: 'General' }) });
    }
    const provider = await api('/models/provider', {
      method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: base }),
    }).then((r) => r.json());
    const model = await api('/models/chat-model', {
      method: 'POST', body: JSON.stringify({ name: 'fake-answerer' }),
    }).then((r) => r.json()).catch(() => null);
    return { provider: provider.provider, reachable: provider.reachable, model };
  }, { base: FAKE, notes: NOTES });
  console.log('provider:', JSON.stringify(wired));

  // Recorded rather than inferred: when no marker appears, the only two
  // candidates are "the backend sent no rows" and "the rows do not match the
  // rendered prose", and the difference is invisible from the page.
  await page.evaluate(() => {
    window.__ground = [];
    // Who rebuilds the answer element after the markers are in it. A
    // MutationObserver says *when* they vanished, never *who*, and the whole
    // question here is which second pass throws them away.
    window.__rebuilds = [];
    const rm = window.renderMarkdown;
    window.renderMarkdown = function (el, text) {
      if (el && el.id === 'ai-answer') {
        window.__rebuilds.push({
          had: el.querySelectorAll('.answer-citation').length,
          stack: String(new Error('here').stack || '').split('\n').slice(1, 5).join(' <- '),
        });
      }
      return rm.apply(this, arguments);
    };
    const orig = window.addInlineCitations;
    window.addInlineCitations = function (answerEl, sentences, rawResults, ordered) {
      window.__ground.push({
        sentences: (sentences || []).map((g) => ({ note_id: g.note_id, sentence: g.sentence })),
        rawIds: (rawResults || []).map((r) => r.id),
        ordered: (ordered || []).map((s) => `${s.kind}:${s.id}`),
        targetText: [...(answerEl && !answerEl.nodeType ? answerEl : answerEl ? [answerEl] : [])]
          .map((el) => el.textContent).join(' | ').slice(0, 400),
      });
      const r = orig.apply(this, arguments);
      // The count the instant the function returns, against the count the
      // probe reads later: the difference is "never placed" versus "placed
      // and then wiped by something that ran afterwards".
      window.__ground[window.__ground.length - 1].placedNow =
        document.querySelectorAll('#ai-answer .answer-citation').length;
      return r;
    };
  });

  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(800);
  // The Ask sub-tab, which is where the report is.
  await page.evaluate(() => { if (typeof showChatSection === 'function') showChatSection('ask'); });
  await page.waitForTimeout(1200);

  const asked = await page.evaluate(async () => {
    const box = document.getElementById('question');
    if (!box) return { ok: false, why: 'no #question on the page' };
    box.value = 'What do my notes say about the starter and the boots?';
    const btn = document.getElementById('ask-btn');
    if (!btn) return { ok: false, why: 'no ask button' };
    //: INBOX 320: when does the first number reach the Matching records
    //: column, against when the answer stops generating? Polled per frame
    //: from the click, because both moments are gone by the time the probe
    //: reads the page.
    window.__timing = { firstNumber: null, firstMarker: null, done: null, t0: performance.now() };
    const tick = () => {
      const t = performance.now() - window.__timing.t0;
      const box = document.getElementById('ai-answer');
      if (window.__timing.firstNumber == null && document.querySelector('#raw-results .record-index')) {
        window.__timing.firstNumber = t;
      }
      if (window.__timing.firstMarker == null && box?.querySelector('.answer-citation')) {
        window.__timing.firstMarker = t;
      }
      if (box && !box.classList.contains('is-generating') && t > 300) {
        window.__timing.done = t;
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    btn.click();
    return { ok: true };
  });
  if (!asked.ok) { console.log('ERR', asked.why); await browser.close(); process.exit(1); }

  // The answer streams; wait for it to settle rather than for a fixed time.
  await page.waitForFunction(() => {
    const a = document.getElementById('ai-answer');
    //: `is-generating` rather than `is-streaming`: the second only goes on
    //: with the first answer token, so during the retrieval wait the box was
    //: already "not streaming" and the probe read the progress line as the
    //: answer (it did, 2026-09-23, and reported no markers for that reason).
    return a && a.textContent.trim().length > 20 && !a.classList.contains('is-generating');
  }, { timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(2500);

  const read = await page.evaluate(() => {
    const answer = document.getElementById('ai-answer');
    const markers = [...(answer?.querySelectorAll('.answer-citation') || [])].map((m) => ({
      n: m.textContent.replace(/\D/g, ''),
      noteId: m.dataset.noteId || null,
      // The sentence the marker sits at the end of, for "the wrong spot".
      before: (m.previousSibling?.textContent || '').trim().slice(-60),
    }));
    const chips = [...document.querySelectorAll('#ai-answer-grounding *')]
      .filter((c) => c.matches('.chip, .answer-grounding-chip, li, button'))
      .map((c) => c.textContent.replace(/\s+/g, ' ').trim().slice(0, 40))
      .filter(Boolean);
    // The panel builds `.chat-source-card` rows wherever it is drawn: the Ask
    // foot and the Chat bubble share one builder (`chatSourcesPanel`), so the
    // card class is the honest selector and an id guess is not.
    const sources = [...document.querySelectorAll('.chat-source-card')]
      .map((s, i) => `${s.querySelector('.chat-source-index')?.textContent || i + 1}. ${s.textContent.replace(/\s+/g, ' ').trim().slice(0, 40)}`);
    return {
      answer: (answer?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 240),
      markers, chips, sources,
      groundingBox: !!document.getElementById('ai-answer-grounding'),
      groundingVisible: !!document.querySelector('#ai-answer-grounding:not(.hidden)'),
    };
  });

  const ground = await page.evaluate(() => window.__ground || []);
  console.log('addInlineCitations calls:', ground.length);
  for (const call of ground) {
    console.log('  sentences:', JSON.stringify(call.sentences));
    console.log('  rawIds:', JSON.stringify(call.rawIds), 'ordered:', JSON.stringify(call.ordered));
    console.log('  targetText:', JSON.stringify(call.targetText));
    console.log('  markers immediately after the call:', call.placedNow);
  }
  for (const r of await page.evaluate(() => window.__rebuilds || [])) {
    console.log(`  rebuild of #ai-answer, markers present at the time: ${r.had} :: ${r.stack}`);
  }
  console.log('answer:', read.answer);
  console.log(`markers: ${read.markers.length}`, JSON.stringify(read.markers.slice(0, 6)));
  console.log(`chips:   ${read.chips.length}`, JSON.stringify(read.chips.slice(0, 6)));
  console.log(`sources: ${read.sources.length}`, JSON.stringify(read.sources.slice(0, 6)));

  const timing = await page.evaluate(() => window.__timing || {});
  const fmt = (v) => (v == null ? 'never' : `${Math.round(v)} ms`);
  console.log(`timing: first record number ${fmt(timing.firstNumber)}, first marker ${fmt(timing.firstMarker)}, answer done ${fmt(timing.done)}`);
  //: INBOX 318's question, answered with numbers: how many (sentence, note)
  //: rows the backend attributed, against how many of them reached the prose.
  const last = ground[ground.length - 1] || { sentences: [] };
  const groundedNotes = new Set(last.sentences.map((g) => String(g.note_id)));
  const markedNotes = new Set(read.markers.map((m) => m.noteId).filter(Boolean));
  const groundedSentences = new Set(last.sentences.map((g) => g.sentence));
  console.log(`grounded: ${last.sentences.length} rows, ${groundedSentences.size} sentences, ${groundedNotes.size} notes; placed: ${read.markers.length} markers, ${markedNotes.size} notes`);
  const findings = [];
  const unplaced = [...groundedNotes].filter((id) => !markedNotes.has(id));
  if (unplaced.length) findings.push(`grounded note(s) ${unplaced.join(', ')} have no marker in the prose`);
  //: Runs of sentences on the same notes in one paragraph share one mark
  //: since 2026-09-24 (`collapseCitationRuns`), so fewer marks than rows is
  //: by design; what must hold is at least one mark per paragraph-run, which
  //: the note-level check above and this lower bound (one per note) cover.
  if (read.markers.length < groundedNotes.size) {
    findings.push(`${last.sentences.length - read.markers.length} grounded row(s) never became a marker`);
  }
  if (process.env.EXPECT_LIVE && timing.done != null && (timing.firstNumber == null || timing.firstNumber >= timing.done)) {
    findings.push('no Matching records number appeared before the answer finished');
  }
  if (!read.answer || read.answer.length < 20) findings.push('no answer came back, so nothing could be grounded');
  else if (!read.markers.length) findings.push('the answer has no inline citation markers at all');
  if (read.markers.length && !read.chips.length) findings.push('markers are in the prose but nothing is listed under "Grounded in"');
  // The numbers a reader sees must be the numbers the lists use.
  const ns = read.markers.map((m) => Number(m.n)).filter(Boolean);
  if (ns.length && read.sources.length && Math.max(...ns) > read.sources.length + read.chips.length) {
    findings.push(`a marker is numbered ${Math.max(...ns)} with only ${read.sources.length} sources listed`);
  }
  if (errors.length) findings.push(`${errors.length} page error(s): ${errors.slice(0, 2)}`);
  for (const line of findings) console.log(`    ${line}`);
  console.log(findings.length ? `FAIL: ${findings.length} findings` : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})().catch((e) => { console.log('ERR ' + e.message); process.exit(1); });
