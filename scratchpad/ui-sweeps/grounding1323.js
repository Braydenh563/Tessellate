// INBOX 1323: the "Grounded in" row as a source list. Renders the row with
// a front-matter note and a picture note, and measures it.
//   BASE=http://127.0.0.1:8781 THEME=dark node grounding1323.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1280, height: 800 }, theme: process.env.THEME });
  await page.waitForTimeout(2500);
  const out = await page.evaluate(async () => {
    await ensureModule('replyKit');
    const host = document.createElement('div');
    host.className = 'answer-grounding';
    host.style.width = '520px';
    document.querySelector('main, body').prepend(host);
    const raw = [
      { id: 9001, content: '---\ntype: Meeting\ndate: 2026-10-15 12:55\nattendees: []\n---\n# Planning sync\nWe agreed the launch date.' },
      { id: 9002, content: 'random sketch notes ![hill](/media/hill.png)' },
    ];
    const sentences = [
      { note_id: 9001, sentence: 'We agreed the launch date.' },
      { note_id: 9002, sentence: 'A sketch.' },
    ];
    renderAnswerGrounding(host, sentences, raw, null, '');
    const chips = [...host.querySelectorAll('.answer-grounding-chip')];
    const r = (el) => el.getBoundingClientRect();
    return {
      label: host.querySelector('.answer-grounding-label').textContent,
      labelTransform: getComputedStyle(host.querySelector('.answer-grounding-label')).textTransform,
      texts: chips.map((c) => c.textContent.trim()),
      tops: chips.map((c) => Math.round(r(c).top - r(host).top)),
      badge: (() => { const b = host.querySelector('.note-label-prefix'); const s = getComputedStyle(b); return [s.display, s.borderRadius, Math.round(r(b).width), Math.round(r(b).height)]; })(),
      border: getComputedStyle(chips[0]).borderTopWidth,
      thumbInItem: !!host.querySelector('.answer-grounding-item .answer-grounding-thumbs'),
      overflow: chips.map((c) => c.scrollWidth > c.clientWidth + 1),
    };
  });
  console.log(JSON.stringify(out));
  await browser.close();
})();
