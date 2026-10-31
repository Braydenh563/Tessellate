// Live view: do the markdown markers go invisible, and come back when the
// selection reaches them?
//
// The owner: "md formatting should go invisible unless i click back on that
// word or section or navigate with backspace, delete or arrow keys etc to
// where those formatting markers are."
//
// Two halves, and the second is the one nothing checked before. The first is
// an inventory: with the caret parked away from everything, which constructs
// still render their own syntax? That is how the two gaps this sweep was
// written alongside were found (`---` drew a border *and* its three dashes;
// `> [!note]` hid its `>` and kept its `[!note]`). The second is the reveal
// itself, driven through the three gestures the owner named, because they are
// three different code paths into the same selection change and only one of
// them is a keypress the plugin could plausibly miss.
//
// `- a bullet`, `1. a number` and a fenced block's ``` are expected to keep
// their markers: a list without bullets is not a list, and a fence with no
// boundary has none. Tables are Phase 3. Those are recorded as expected
// rather than skipped, so a change that starts hiding them fails here.
//
//   BASE=http://127.0.0.1:8830 node scratchpad/ui-sweeps/cm-reveal.js
const { boot } = require('./lib.js');
const { openDoc } = require('./docopen.js');

// Each line, and what it should render as with the caret elsewhere.
const CASES = [
  ['# H1 heading', 'H1 heading'],
  ['Some **bold** and *em* and ~~struck~~ and `code`.', 'Some bold and em and struck and code.'],
  ['> a block quote', 'a block quote'],
  // A dash is drawn as a bullet while the caret is elsewhere
  // (`DocBulletWidget` in documents.js): one character standing in for one,
  // so the marker is still there, just not as the character that was typed.
  // These two expectations predated that widget and failed against every
  // head since it landed.
  ['- a bullet', '\u2022 a bullet'],
  ['1. a number', '1. a number'],
  ['- [ ] a task', '\u2022  a task'],
  ['---', ''],
  ['==highlighted== and [[wikilink]] and [label](/path).', 'highlighted and wikilink and label.'],
];
// The `Title` / `=====` form. Its underline is a HeaderMark like any other, so
// it was already being hidden while the heading branch matched `ATXHeading`
// only: the markers went and the line stayed body text. Both lines are checked
// here, the second for the hidden underline and the first for the class.
const SETEXT = ['A setext heading', '================'];
// A callout is its own block: put it after a blank line, or the blockquote
// above swallows it and the first line the plugin reads is that one instead.
const CALLOUT = '> [!warning] a callout';

(async () => {
  const { browser, page } = await boot();
  const say = (k, v) => console.log(`${k}: ${JSON.stringify(v)}`);
  let bad = 0;
  const fail = (m) => { console.log('FAIL: ' + m); bad++; };

  const body = CASES.map(([src]) => src).join('\n\n') + '\n\n' + CALLOUT
    + '\n\n' + SETEXT.join('\n') + '\n\ntail\n';
  await openDoc(page, { title: 'Reveal', content: body });
  await page.waitForTimeout(1400);
  say('view', await page.evaluate(() => docView));

  const lines = () => page.evaluate(() => [...document.querySelectorAll('#doc-editor .cm-line')].map((l) => l.innerText.replace(/\n/g, '')));

  // The caret goes to the very end, so nothing on any case line is touched.
  await page.evaluate(() => { const s = docSurface(); const n = s.text.length; s.focus(); s.setSelection(n, n); });
  await page.waitForTimeout(500);
  const parked = await lines();
  // Case i sits on rendered line 2i: the body joins the cases with a blank
  // line, and a blank source line is a rendered line of its own.
  for (let i = 0; i < CASES.length; i++) {
    const [src, want] = CASES[i];
    const got = parked[i * 2];
    say(`hidden_${i}`, { src, want, got });
    if (got !== want) fail(`"${src}" rendered as ${JSON.stringify(got)}, wanted ${JSON.stringify(want)}`);
  }
  const setext = await page.evaluate((first) => {
    const line = [...document.querySelectorAll('#doc-editor .cm-line')].find((l) => l.innerText.trim() === first);
    if (!line) return null;
    const next = line.nextElementSibling;
    return { classes: line.className, underlineHidden: next ? next.innerText.trim() === '' : null };
  }, SETEXT[0]);
  say('setext_heading', setext);
  if (!setext) fail('the setext heading is not in the render at all');
  else {
    if (!/cm-md-h1/.test(setext.classes)) fail(`a setext heading gets no heading class (${setext.classes})`);
    if (setext.underlineHidden === false) fail('a setext heading shows its own === underline');
  }

  const label = await page.evaluate(() => {
    const e = document.querySelector('.cm-md-callout-label');
    return e ? e.textContent : null;
  });
  say('callout_label', label);
  if (!label || !/Warning/.test(label)) fail(`the callout kept its [!warning] marker (label ${JSON.stringify(label)})`);

  // The reveal, through each gesture the owner named, and the unit is the
  // **span** (INBOX 1473 b, the owner: "like obsidian where it does it per
  // phrase, word, or whatever text string is formatted when clicked inside or
  // next to"): a span's marks show while the caret is in it or touching it,
  // and every other span on the same line stays rendered. Before 1473 the
  // unit was the line, and this sweep held that.
  const boldAt = await page.evaluate(() => docSurface().text.indexOf('**bold**'));
  const LINE_SRC = CASES[1][0];
  const lineText = () => page.evaluate((src) => {
    const want = src.slice(0, 4);
    const el = [...document.querySelectorAll('#doc-editor .cm-line')].find((l) => l.innerText.startsWith(want));
    return el ? el.innerText : null;
  }, LINE_SRC);
  // `**b...**`: Backspace and Delete below take a letter out of the word.
  const shows = async () => /\*\*b\w*\*\*/.test(await lineText() || '');
  const others = async () => {
    const t = await lineText() || '';
    return ['*em*', '~~struck~~', '`code`'].filter((m) => t.includes(m));
  };
  const park = (n) => page.evaluate((p) => { const s = docSurface(); s.focus(); s.setSelection(p, p); }, n);
  const elsewhere = await page.evaluate(() => docSurface().text.length);
  // The rendered rect of one character of the line, from the DOM.
  const charRect = (word, k) => page.evaluate(({ word, k, src }) => {
    const el = [...document.querySelectorAll('#doc-editor .cm-line')].find((l) => l.innerText.startsWith(src.slice(0, 4)));
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const i = n.data.indexOf(word);
      if (i < 0) continue;
      const r = document.createRange();
      r.setStart(n, i + k);
      r.setEnd(n, i + k + 1);
      const b = r.getBoundingClientRect();
      return { x: b.left, y: b.top + b.height / 2, w: b.width };
    }
    return null;
  }, { word, k, src: LINE_SRC });

  // Click: a real pointer press on the "l" of the rendered "bold", mid-line.
  await park(elsewhere);
  await page.waitForTimeout(300);
  const before = await charRect('bold', 2);
  await page.mouse.click(before.x + before.w * 0.3, before.y);
  await page.waitForTimeout(300);
  const after = await charRect('bold', 2);
  const head = await page.evaluate(() => docCmView.state.selection.main.head);
  const drift = +(after.x - before.x).toFixed(1);
  // The opening `**`'s own width, now that it is drawn.
  const opening = await page.evaluate((at) => {
    const a = docCmView.coordsAtPos(at, 1);
    const b = docCmView.coordsAtPos(at + 2, -1);
    return a && b ? +(b.left - a.left).toFixed(1) : null;
  }, boldAt);
  say('click_inside_bold', { head, want: boldAt + 4, drift, opening, line: await lineText() });
  if (head !== boldAt + 4) fail(`a click on the "l" of bold put the caret at ${head}, not ${boldAt + 4}`);
  if (!(await shows())) fail('a click inside **bold** did not reveal its marks');
  const leaked = await others();
  if (leaked.length) fail(`a click inside **bold** revealed other spans on its line too: ${leaked.join(', ')}`);
  // The clicked character keeps its offset and moves by the opening `**`
  // only, which is the mark appearing in front of it (the line rule moved it
  // by every mark before it on the line). More than that is marks revealed
  // that the caret is not in.
  if (opening === null || drift < 0 || drift > opening + 1) {
    fail(`the clicked character moved ${drift}px on the reveal, the opening mark is ${opening}px`);
  }

  // Elsewhere on the same line: hidden again.
  await park(boldAt + 20);
  await page.waitForTimeout(300);
  say('hidden_elsewhere_on_its_line', !(await shows()));
  if (await shows()) fail('the marks of **bold** stayed up with the caret elsewhere on its line');
  await park(elsewhere);
  await page.waitForTimeout(300);
  if (await shows()) fail('the marks stayed up with the caret on another line');

  // Arrow keys: walk left from past the span into it (reveal), then on out of
  // its left end (hide). `**bold**` is boldAt..boldAt+8.
  await park(boldAt + 11);
  await page.waitForTimeout(250);
  const seen = [];
  for (let i = 0; i < 12; i++) {
    const at = await page.evaluate(() => docCmView.state.selection.main.head);
    seen.push([at, await shows()]);
    await page.keyboard.press('ArrowLeft');
    await page.waitForTimeout(120);
  }
  say('arrow_walk', seen.map(([at, on]) => `${at}${on ? '+' : '-'}`).join(' '));
  for (const [at, on] of seen) {
    const inside = at >= boldAt && at <= boldAt + 8;
    if (inside !== on) fail(`at ${at} the marks were ${on ? 'up' : 'down'}, the span is ${boldAt}..${boldAt + 8}`);
  }

  // Backspace and Delete both move the selection, so both must repaint.
  for (const key of ['Backspace', 'Delete']) {
    await park(elsewhere);
    await page.waitForTimeout(200);
    if (await shows()) fail(`the marks were up before ${key} was pressed`);
    await park(boldAt + 4);
    await page.waitForTimeout(150);
    await page.keyboard.press(key);
    await page.waitForTimeout(300);
    say(`reveal_by_${key.toLowerCase()}`, await shows());
    if (!(await shows())) fail(`${key} inside the span did not reveal its marks`);
    await page.keyboard.press('Control+z');
    await page.waitForTimeout(250);
  }

  // **The caret moves right on a left press only where a span reveals.**
  // The 28.4px jump this once guarded against (four characters appearing to
  // the caret's left as it crossed a span's edge) is Obsidian's behaviour at a
  // span's right end, and the per-span rule brings it back there, once per
  // span entered. Anywhere else a rightward move is a reflow nobody asked for.
  await park(boldAt + 14);
  await page.waitForTimeout(300);
  const walk = [];
  for (let i = 0; i < 14; i++) {
    walk.push(await page.evaluate(() => {
      const head = docCmView.state.selection.main.head;
      const c = docCmView.coordsAtPos(head);
      return { pos: head, x: c ? +c.left.toFixed(1) : null, text: document.querySelector('#doc-editor .cm-content').innerText.length };
    }));
    await page.keyboard.press('ArrowLeft');
    await page.waitForTimeout(110);
  }
  say('caret_walk', walk.map((w) => w.x));
  for (let i = 1; i < walk.length; i++) {
    if (walk[i].x === null || walk[i - 1].x === null) continue;
    if (walk[i].x > walk[i - 1].x && walk[i].text === walk[i - 1].text) {
      fail(`ArrowLeft moved the caret right, ${walk[i - 1].x} to ${walk[i].x}, at position ${walk[i].pos}, with no span revealed`);
    }
  }

  console.log(bad ? `cm-reveal: ${bad} failures` : 'cm-reveal: all checks pass');
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
