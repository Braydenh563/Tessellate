// The one attachment chip (DESIGN.md "A file waiting on the next message",
// attach-1026 A1 to A3) on the popup agent and the Chat composer. At 1440,
// 720 and 390 asserts: a chip per staged file (kind glyph or thumbnail, name
// with the extension kept, facts line, a labelled x), no chip wider than its
// strip or the window, the x a 24px target, an uploading chip with a bar and
// no x, an error chip with its reason, remove-before-send leaving no request,
// any file kind accepted by the popup agent (no 415 on a .docx or .txt).
//
//   BASE=http://127.0.0.1:8941 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/attachchips.js
const { boot } = require('./lib.js');

(async () => {
  let fails = 0;
  const check = (name, ok, detail) => {
    if (!ok) fails += 1;
    console.log(ok ? 'ok  ' : 'FAIL', name, ok ? '' : JSON.stringify(detail));
  };
  for (const viewport of [{ width: 1440, height: 900 }, { width: 720, height: 900 }, { width: 390, height: 844 }]) {
    const w = viewport.width;
    const { browser, page } = await boot({ viewport });
    const uploads = [];
    page.on('request', (r) => { if (/\/(media\/upload|documents\/import)/.test(r.url())) uploads.push(r.url()); });

    // Popup agent: stage three files through the real paste/drop path.
    await page.evaluate(() => runShortcut('askAgent'));
    await page.waitForTimeout(600);
    const staged = await page.evaluate(() => {
      const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='), (c) => c.charCodeAt(0));
      agentStageFiles([
        new File([png], 'a-rather-long-screenshot-name-from-the-desktop-final-v2.png', { type: 'image/png' }),
        new File([new Uint8Array(2300000)], 'Quarterly report with a very long title that cannot fit.docx', { type: '' }),
        new File(['hello'], 'notes.txt', { type: 'text/plain' }),
      ]);
      return true;
    });
    await page.waitForTimeout(300);
    const m = await page.evaluate(() => {
      const strip = document.getElementById('command-palette-attachments');
      const sr = strip.getBoundingClientRect();
      return {
        hidden: strip.classList.contains('hidden'),
        stripRight: sr.right,
        win: innerWidth,
        chips: [...strip.querySelectorAll('.att-chip')].map((c) => {
          const r = c.getBoundingClientRect();
          const x = c.querySelector('.att-chip-x');
          const xr = x.getBoundingClientRect();
          const stem = c.querySelector('.att-chip-stem');
          return {
            right: r.right, width: r.width, height: r.height,
            name: c.querySelector('.att-chip-name').textContent,
            facts: c.querySelector('.att-chip-facts').textContent,
            xLabel: x.getAttribute('aria-label'), xw: xr.width, xh: xr.height,
            clipped: stem.scrollWidth > stem.clientWidth,
            ext: c.querySelector('.att-chip-ext')?.textContent || '',
            extVisible: (() => { const e = c.querySelector('.att-chip-ext'); return !e || e.getBoundingClientRect().right <= r.right + 0.5; })(),
            thumb: !!c.querySelector('img.att-chip-tile'), glyph: c.querySelector('i.att-chip-tile')?.className || '',
          };
        }),
        pageOverflow: document.documentElement.scrollWidth > innerWidth,
      };
    });
    check(`${w} three chips shown`, !m.hidden && m.chips.length === 3, m);
    check(`${w} chips inside the strip and window`, m.chips.every((c) => c.right <= m.stripRight + 1 && c.right <= m.win), m);
    check(`${w} no page overflow`, !m.pageOverflow, m);
    check(`${w} every x is labelled and 24px+`, m.chips.every((c) => /^Remove/.test(c.xLabel) && c.xw >= 24 && c.xh >= 24), m.chips.map((c) => [c.xLabel, c.xw, c.xh]));
    check(`${w} extension kept when the stem is cut`, m.chips.every((c) => c.extVisible) && m.chips[1].clipped && m.chips[1].ext === '.docx', m.chips[1]);
    check(`${w} png has a thumbnail, docx a glyph, facts say kind and size`, m.chips[0].thumb && m.chips[1].glyph.includes('ph-file') && /Word · 2\.2 MB/.test(m.chips[1].facts), m.chips);
    console.log('     chip height', m.chips.map((c) => Math.round(c.height)), 'widths', m.chips.map((c) => Math.round(c.width)));

    // Remove one before sending: chip gone, nothing sent to the server.
    await page.click('#command-palette-attachments .att-chip:nth-child(2) .att-chip-x');
    await page.waitForTimeout(150);
    const left = await page.evaluate(() => [...document.querySelectorAll('#command-palette-attachments .att-chip-name')].map((e) => e.textContent));
    check(`${w} remove takes the chip away`, left.length === 2 && !left.some((n) => n.includes('Quarterly')), left);
    check(`${w} nothing was uploaded by staging or removing`, uploads.length === 0, uploads);

    // Uploading and error states from the one builder.
    const states = await page.evaluate(() => {
      const host = document.createElement('div');
      host.id = 'sweep-states';
      host.className = 'chat-attachments';
      host.append(
        attachmentChip({ name: 'big.pdf', size: 5e6, state: 'uploading', progress: 0.4, onRemove: null }),
        attachmentChip({ name: 'bad.svg', state: 'error', error: 'Only images and PDFs can be dropped in here.', onRemove: () => {} }),
      );
      document.getElementById('command-palette-attachments').after(host);
      const [up, bad] = host.children;
      return {
        bar: up.querySelector('progress')?.value, upX: !!up.querySelector('.att-chip-x'), upFacts: up.querySelector('.att-chip-facts').textContent,
        badFacts: bad.querySelector('.att-chip-facts').textContent, badBorder: getComputedStyle(bad).borderTopColor,
      };
    });
    check(`${w} uploading shows a bar and no x; error shows its reason`, states.bar === 40 && !states.upX && /40%/.test(states.upFacts) && /Only images/.test(states.badFacts), states);

    // Send with a .txt and a png: the agent accepts both (A3), uploads happen now.
    await page.evaluate(() => document.getElementById('sweep-states')?.remove());
    await page.fill('#command-palette-input', 'What is in these files?');
    await page.press('#command-palette-input', 'Enter');
    await page.waitForTimeout(2500);
    check(`${w} send uploads one image and imports one document, no 415`, uploads.some((u) => /media\/upload/.test(u)) && uploads.some((u) => /documents\/import/.test(u)), uploads);
    const after = await page.evaluate(() => ({
      strip: document.getElementById('command-palette-attachments').classList.contains('hidden'),
      bubbleChips: document.querySelectorAll('#command-palette-results .msg.user .att-chip').length,
    }));
    check(`${w} strip clears and the sent bubble carries the chips`, after.strip && after.bubbleChips === 2, after);
    await page.keyboard.press('Escape');

    // Chat composer: the same chip.
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(500);
    const chat = await page.evaluate(() => {
      const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='), (c) => c.charCodeAt(0));
      attachedImages.push({ key: 'k1', file: new File([png], 'photo.png', { type: 'image/png' }), objectUrl: '', name: 'photo.png' });
      attachedFiles.push({ id: 1, name: 'contract-with-a-really-long-name-for-the-wrap-test.pdf' });
      renderImageAttachments();
      renderFileAttachments();
      const chips = [...document.querySelectorAll('#chat-image-attachments .att-chip, #chat-file-attachments .att-chip')];
      return chips.map((c) => ({ right: c.getBoundingClientRect().right, label: c.querySelector('.att-chip-x').getAttribute('aria-label'), win: innerWidth }));
    });
    check(`${w} chat chips are the same chip, inside the window`, chat.length === 2 && chat.every((c) => c.right <= c.win && c.label), chat);
    await browser.close();
  }
  console.log(fails ? `${fails} FAILED` : 'all ok');
  process.exit(fails ? 1 : 0);
})();
