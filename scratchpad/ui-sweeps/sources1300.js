// INBOX 1300 C29: the popup agent's Sources fold says it folds and whether
// it is open. Builds the popup's panel (`cmdPaletteSources`, the popup's own
// builder) and the Chat card panel, and reads the caret (::before glyph and
// turn), the open state at rest, and the rail joining the list to its
// summary. Env: BASE.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const out = await page.evaluate(async () => {
    const meta = { raw_results: [{ id: 1, title: 'Porto trip', content: 'Porto trip plans', category: 'Travel', timestamp: '2026-10-01' }, { id: 2, title: 'Dentist', content: 'Dentist on Tuesday', category: 'Health', timestamp: '2026-10-02' }] };
    const read = async (panel) => {
      const host = document.createElement('div');
      host.className = 'card';
      document.body.appendChild(host);
      host.appendChild(panel);
      const sum = panel.querySelector('summary');
      const cs = () => getComputedStyle(sum, '::before');
      const shut = { open: panel.open, glyph: cs().content.codePointAt(1)?.toString(16), turn: cs().transform };
      panel.open = true;
      await new Promise((r) => setTimeout(r, 400));
      const body = panel.querySelector('.chat-sources-body');
      const b = getComputedStyle(body);
      const open = { glyph: cs().content.codePointAt(1)?.toString(16), turn: cs().transform, rail: b.borderLeftWidth + ' ' + b.borderLeftStyle, railX: Math.round(body.getBoundingClientRect().left - sum.getBoundingClientRect().left) };
      host.remove();
      return { shut, open };
    };
    const sources = chatSourcesFrom({ meta, touched: [] });
    const popup = typeof cmdPaletteSources === 'function' ? cmdPaletteSources({ meta, touched: [] }) : null;
    return {
      n: sources.length,
      popup: popup ? await read(popup.matches('details') ? popup : popup.querySelector('details')) : 'no builder',
      chat: await read(chatSourcesPanel({ sources })),
    };
  });
  console.log(JSON.stringify(out));
  await browser.close();
})();
