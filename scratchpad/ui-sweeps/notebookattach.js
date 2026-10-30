// Notebook attachments in Chat (INBOX 1460, DESIGN.md "A notebook item on a
// message"): the staged card and the sent card are the file card's recipe.
// At 1280 and 390, in the theme THEME names, asserts: a card per note (glyph
// tile, name, one facts line, a labelled x when staged), none wider than its
// strip or the window, a long title cut at its end only (the stem's ellipsis,
// the card never clipped on both sides), a title-less note named "Untitled
// note", the sent cards above the bubble, on its side, removed with it, the
// same height as a staged file card, a press opening the preview with an Open
// button, Escape closing it, five attachments wrapping inside the bubble.
//
//   BASE=http://127.0.0.1:8803 THEME=dark SCRATCH=/tmp/x PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/notebookattach.js
const { boot } = require('./lib.js');

(async () => {
  let fails = 0;
  const check = (name, ok, detail) => {
    if (!ok) fails += 1;
    console.log(ok ? 'ok  ' : 'FAIL', name, ok ? '' : JSON.stringify(detail));
  };
  for (const width of [1280, 390]) {
    const { browser, page, OUT } = await boot({ viewport: { width, height: 900 } });
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(600);
    const ids = await page.evaluate(async () => {
      const make = async (content) => (await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content }) })).id;
      const out = {
        long: await make('A very long single line note title that just keeps going and going without any punctuation to give the card a reason to cut it at the end of the line only'),
        short: await make('# Weekly review\n\nWent well.'),
        bare: await make('![](/media/none.png)'),
        a: await make('**Ice Breakers:** ideas for the team day'),
        b: await make('Short'),
      };
      await loadEntries();
      return out;
    });
    const staged = await page.evaluate(async (ids) => {
      attachedNoteIds = [ids.long, ids.short, ids.bare, ids.a, ids.b];
      renderAttachments();
      const box = document.getElementById('chat-attachments');
      const br = box.getBoundingClientRect();
      return {
        boxRight: br.right, win: innerWidth,
        cards: [...box.querySelectorAll('.att-chip')].map((c) => {
          const r = c.getBoundingClientRect();
          const stem = c.querySelector('.att-chip-stem');
          const x = c.querySelector('.att-chip-x');
          return {
            right: r.right, w: r.width, h: r.height,
            name: stem.textContent, facts: c.querySelector('.att-chip-facts').textContent,
            cut: stem.scrollWidth > stem.clientWidth, tile: c.querySelector('.att-chip-tile').className,
            xLabel: x?.getAttribute('aria-label'), xw: x?.getBoundingClientRect().width,
            open: !!c.querySelector('button.att-chip-open'),
            openOverflow: (() => { const o = c.querySelector('.att-chip-open'); return o.scrollWidth - o.clientWidth; })(),
          };
        }),
      };
    }, ids);
    check(`${width} five staged cards`, staged.cards.length === 5, staged);
    check(`${width} staged cards inside the window`, staged.cards.every((c) => c.right <= staged.win), staged.cards.map((c) => c.right));
    check(`${width} every x labelled and 24px+`, staged.cards.every((c) => /^Remove/.test(c.xLabel) && c.xw >= 24), staged.cards.map((c) => [c.xLabel, c.xw]));
    check(`${width} the long name ends in an ellipsis, the card is not clipped`, staged.cards[0].cut && staged.cards[0].openOverflow <= 1, staged.cards[0]);
    check(`${width} a title-less note is named`, staged.cards[2].name === 'Untitled note', staged.cards[2].name);
    check(`${width} markdown is words`, staged.cards[1].name === 'Weekly review' && staged.cards[3].name.startsWith('Ice Breakers'), staged.cards.map((c) => c.name));
    check(`${width} facts name the kind`, staged.cards.every((c) => /^Note/.test(c.facts)), staged.cards.map((c) => c.facts));
    console.log('     staged heights', staged.cards.map((c) => Math.round(c.h)), 'widths', staged.cards.map((c) => Math.round(c.w)));

    // A staged file card, for the same-height comparison.
    const fileH = await page.evaluate(() => {
      attachedImages = [{ key: 'k', id: 0, name: 'photo.png', file: new File(['x'], 'photo.png'), url: '' }];
      renderImageAttachments();
      const c = document.querySelector('#chat-image-attachments .att-chip');
      const h = c.getBoundingClientRect().height;
      attachedImages = [];
      renderImageAttachments();
      return h;
    });
    check(`${width} the note card is the file card's height`, Math.abs(fileH - staged.cards[0].h) < 1.5, [fileH, staged.cards[0].h]);

    // Remove one: gone from the list.
    await page.click('#chat-attachments .att-chip:nth-child(5) .att-chip-x');
    check(`${width} remove takes the card away`, (await page.$$('#chat-attachments .att-chip')).length === 4, null);

    // Sent: one then five.
    for (const count of [1, 5]) {
      const m = await page.evaluate((args) => {
        const { ids, count } = args;
        const list = [ids.long, ids.short, ids.bare, ids.a, ids.b].slice(0, count);
        addBubble('user', 'when did I make this note?', list.map((id) => ({ kind: 'note', id, name: '' })));
        const b = [...document.querySelectorAll('.msg.user')].pop();
        const br = b.getBoundingClientRect();
        const strip = b.cards.getBoundingClientRect();
        const body = br;
        const mark = { left: 0, right: 0, top: 0, bottom: 0 };
        const cards = [...b.cards.querySelectorAll('.att-chip')].map((c) => {
          const r = c.getBoundingClientRect();
          return { r: r.right, l: r.left, h: r.height, w: r.width, over: c.scrollWidth - c.clientWidth, bg: getComputedStyle(c).backgroundColor, ink: getComputedStyle(c.querySelector('.att-chip-stem')).color };
        });
        const hit = cards.some((c, i) => {
          const r = [...b.cards.querySelectorAll('.att-chip')][i].getBoundingClientRect();
          return !(r.right <= mark.left || r.left >= mark.right || r.bottom <= mark.top || r.top >= mark.bottom);
        });
        return { bubble: { w: br.width, h: br.height, right: br.right }, stripBottom: strip.bottom, bodyTop: body.top, stripRight: strip.right, stripLeft: strip.left, gap: br.top - strip.bottom, sibling: b.previousElementSibling === b.cards, cards, markHit: hit, win: innerWidth,
          bubbleBg: getComputedStyle(b).backgroundColor };
      }, { ids, count });
      check(`${width} sent x${count}: cards above the bubble, on its side`, m.stripBottom <= m.bodyTop + 1 && Math.abs(m.stripRight - m.bubble.right) < 2 && m.sibling, m);
      check(`${width} sent x${count}: no wider than the bubble's measure`, m.cards.every((c) => c.r <= m.bubble.right + 1 && c.r <= m.win), m);
      check(`${width} sent x${count}: inside the window`, m.stripLeft >= 0, m);
      check(`${width} sent x${count}: no card overflows`, m.cards.every((c) => c.over <= 1), m.cards.map((c) => c.over));
      console.log(`     sent x${count}: bubble h`, Math.round(m.bubble.h), 'gap to bubble', Math.round(m.gap), 'card h', Math.round(m.cards[0].h), 'w', m.cards.map((c) => Math.round(c.w)), 'bubble bg', m.bubbleBg, 'card bg', m.cards[0].bg);
    }
    await page.waitForTimeout(900);
    const settled = await page.evaluate(() => {
      const b = [...document.querySelectorAll('.msg.user')].reverse().find((x) => x.cards && x.cards.querySelectorAll('.att-chip').length === 5);
      return { gap: b.getBoundingClientRect().top - b.cards.getBoundingClientRect().bottom, noteHeights: [...b.cards.querySelectorAll('.att-chip')].map((c) => Math.round(c.getBoundingClientRect().height)), lines: [...b.cards.querySelectorAll('.att-chip-lines')].map((e) => [Math.round(e.getBoundingClientRect().height), e.textContent]) };
    });
    check(`${width} settled gap between cards and bubble is small`, settled.gap >= 0 && settled.gap <= 16, settled);
    console.log('     settled', JSON.stringify(settled));
    await page.screenshot({ path: `${OUT}/nbattach-${width}-${process.env.THEME || 'light'}.png` });

    // Press the first sent card: preview with Open, Escape closes, focus returns.
    const door = '.msg.user:last-of-type .att-chip-open, .msg.user .att-chip-open';
    const first = (await page.$$('#chat-messages > .msg-attachments .att-chip-open')).slice(-5)[0];
    await first.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(700);
    const peek = await page.evaluate(() => {
      const p = document.getElementById('citation-peek');
      if (!p) return null;
      const r = p.getBoundingClientRect();
      return { label: p.getAttribute('aria-label'), open: p.querySelector('.citation-peek-foot button')?.textContent.trim(), title: p.querySelector('.citation-peek-title')?.textContent, focusIn: p.contains(document.activeElement), r: [r.left, r.right, r.top, r.bottom], win: [innerWidth, innerHeight], numHidden: getComputedStyle(p.querySelector('.citation-peek-number')).display };
    });
    check(`${width} a press previews with an Open button`, !!peek && /Open note/.test(peek.open) && /^Preview of /.test(peek.label), peek);
    check(`${width} the preview is on screen and takes focus from the keyboard`, !!peek && peek.r[0] >= 0 && peek.r[1] <= peek.win[0] && peek.r[2] >= 0 && peek.r[3] <= peek.win[1] && peek.focusIn, peek);
    check(`${width} the empty number slot is not drawn`, peek && peek.numHidden === 'none', peek);
    await page.screenshot({ path: `${OUT}/nbattach-peek-${width}-${process.env.THEME || 'light'}.png` });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    const after = await page.evaluate(() => ({ gone: !document.getElementById('citation-peek'), onCard: document.activeElement?.classList.contains('att-chip-open') }));
    check(`${width} Escape closes it and returns to the card`, after.gone && after.onCard, after);

    // Removing the bubble takes its cards with it.
    const gone = await page.evaluate(async () => {
      addBubble('user', 'to be removed', [{ kind: 'note', id: 1, name: '' }]);
      const b = [...document.querySelectorAll('.msg.user')].pop();
      const strip = b.cards;
      dropChatBubble(b);
      return !strip.isConnected && !b.isConnected;
    });
    check(`${width} a removed bubble takes its cards with it`, gone, gone);

    // The other kinds: a document (its opening words fetched), a map and a file.
    const doc = await page.evaluate(async () => {
      const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'Quarterly plan', content: 'Goals for the quarter: ship the notebook cards and keep the boot light.' }) });
      addBubble('user', 'what is in these?', [
        { kind: 'document', id: d.id, name: 'Quarterly plan' },
        { kind: 'map', id: 987654, name: 'Project map' },
        { kind: 'file', id: 987655, name: 'minutes-of-the-long-meeting-with-everyone.pdf' },
      ]);
      const b = [...document.querySelectorAll('.msg.user')].pop();
      return { id: d.id, cards: [...b.cards.querySelectorAll('.att-chip')].map((c) => [c.querySelector('.att-chip-stem').textContent, c.querySelector('.att-chip-facts').textContent, c.querySelector('.att-chip-tile').className, c.querySelector('.att-chip-ext')?.textContent || '']) };
    });
    check(`${width} document, map and file cards`, doc.cards.length === 3 && doc.cards[0][1] === 'Document' && /Mind map/.test(doc.cards[1][1]) && /PDF/.test(doc.cards[2][1]), doc.cards);
    for (const [index, what] of [[0, /Open document/], [1, /Open mind map/], [2, /Open file/]]) {
      const btn = (await page.$$('#chat-messages > .msg-attachments:nth-last-child(2) .att-chip-open'))[index];
      await btn.click();
      await page.waitForTimeout(700);
      const p = await page.evaluate(() => {
        const el = document.getElementById('citation-peek');
        return el && { open: el.querySelector('.citation-peek-foot button')?.textContent.trim(), title: el.querySelector('.citation-peek-title')?.textContent, body: el.querySelector('.citation-peek-body')?.textContent.slice(0, 60) };
      });
      check(`${width} kind ${index} previews with ${what}`, !!p && what.test(p.open), p);
      await page.keyboard.press('Escape');
    }
    await browser.close();
  }
  console.log(fails ? `${fails} FAILED` : 'all ok');
  process.exit(fails ? 1 : 0);
})();
