// The rotating thinking word beside the dots (chat.js's `progressLine` /
// `typingDots` / `startThinkingWordRotation`), built directly with no model
// and no chat turn needed: the owner reported "the dots, a long line, then
// the phrase far right and off-centre, with an annoying pulse" (screenshots,
// INBOX 431). Root cause: `.typing-dots span` (dot styling: a 0.45rem
// circle, `border-radius: 50%`, `background: var(--muted)`, the
// `dot-bounce` animation) matched the rotating word too, since it used to
// be just a fourth bare `<span>` in the same row -- stretched by its own
// `min-width` into a flattened pill (the line), painted solid (part of the
// off-centre look) and bouncing (the pulse). Fixed by giving the three real
// dots their own `.typing-dot` class and scoping every dot rule to it.
//
// Measures the row width, whether the word's box actually widens the
// hairline it sits beside (the regression shape: `.typing-dots::before`'s
// own width, not `.typing-dots`'s full rect), and the word's own box shape
// (border-radius, background, animation-name) so a future `<span>` added to
// this row that repeats the leak fails loudly here rather than needing a
// screenshot to notice.
const { boot } = require('./lib.js');

(async () => {
  const { page, browser } = await boot({ viewport: { width: 1093, height: 700 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  await page.waitForTimeout(800);

  const measured = await page.evaluate(() => {
    const host = document.createElement('div');
    host.id = 'thinkingwords-sweep-host';
    document.body.appendChild(host);
    const line = progressLine('Thinking…', { persona: 'Atlas', words: true });
    host.appendChild(line);
    const dots = line.querySelector('.typing-dots');
    const word = line.querySelector('.typing-thinking-word');
    const dot1 = line.querySelector('.typing-dot');
    const beforeWidth = parseFloat(getComputedStyle(dots, '::before').width);
    const wordCS = getComputedStyle(word);
    const dotCS = getComputedStyle(dot1);
    const dotsRect = dots.getBoundingClientRect();
    const wordRect = word.getBoundingClientRect();
    return {
      dotsWidth: Math.round(dotsRect.width),
      hairlineWidth: Math.round(beforeWidth),
      word: {
        text: word.textContent,
        borderRadius: wordCS.borderRadius,
        background: wordCS.backgroundColor,
        animationName: wordCS.animationName,
        fontWeight: wordCS.fontWeight,
        boxWidth: Math.round(wordRect.width),
        boxHeight: Math.round(wordRect.height),
      },
      dot: {
        borderRadius: dotCS.borderRadius,
        animationName: dotCS.animationName,
      },
    };
  });

  const problems = [];
  // The regression shape: the hairline tracking the FULL row (dots + word)
  // instead of just the three-dot cluster, which is what "a long line"
  // measured as before the fix (up to 245px; the dot cluster alone is
  // under 25px regardless of density scale).
  if (measured.hairlineWidth > 30) {
    problems.push(`hairline is ${measured.hairlineWidth}px wide, not scoped to the dot cluster (expected well under 30px)`);
  }
  // The word picking up dot styling: round, filled, bouncing.
  if (parseFloat(measured.word.borderRadius) > 4) {
    problems.push(`thinking word has border-radius ${measured.word.borderRadius} (a dot's 50% leaking onto it)`);
  }
  if (measured.word.animationName && measured.word.animationName !== 'none') {
    problems.push(`thinking word carries an animation (${measured.word.animationName}); it should only opacity-transition between rotations`);
  }
  if (measured.word.background !== 'rgba(0, 0, 0, 0)') {
    problems.push(`thinking word has a background fill (${measured.word.background}), a dot's solid circle leaking onto it`);
  }
  if (parseFloat(measured.word.fontWeight) < 600) {
    problems.push(`thinking word is not bold (font-weight ${measured.word.fontWeight})`);
  }
  // The radius token is a pill now (999px), which on a square dot is the same circle as 50%.
  if (!(measured.dot.borderRadius === '50%' || parseFloat(measured.dot.borderRadius) >= 999)) {
    problems.push(`a real dot lost its own circle shape (border-radius ${measured.dot.borderRadius})`);
  }
  if (!measured.dot.animationName || measured.dot.animationName === 'none') {
    problems.push('a real dot is not animating (dot-bounce missing)');
  }

  console.log(JSON.stringify({ theme: process.env.THEME || 'light', measured, problems, errors }, null, 2));
  await browser.close();
  if (problems.length || errors.length) process.exit(1);
})().catch((e) => { console.error('SWEEP_ERROR', e.message, e.stack); process.exit(1); });
