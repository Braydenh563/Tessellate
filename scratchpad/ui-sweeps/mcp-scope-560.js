// L-world-class-560: Settings, Tools it can use, the MCP link scope fields and
// the Waiting to sign in list. Measures the two inputs, the waiting row with
// its Approve and Deny, and page errors.
const { boot, BASE } = require('./lib.js');
(async () => {
  const { page, browser } = await boot();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
  await page.waitForTimeout(2500);
  await page.evaluate(async (base) => {
    const reg = await (await fetch(base + '/oauth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client_name: 'Claude', redirect_uris: ['https://claude.ai/api/mcp/auth_callback'] }) })).json();
    const q = new URLSearchParams({ response_type: 'code', client_id: reg.client_id, redirect_uri: 'https://claude.ai/api/mcp/auth_callback', code_challenge: 'x'.repeat(43), code_challenge_method: 'S256' });
    await fetch(base + '/oauth/authorize?' + q, { redirect: 'manual' });
  }, BASE);
  await page.evaluate(() => openSettingsModal('tools'));
  await page.waitForTimeout(3000);
  const out = await page.evaluate(() => {
    const box = (id) => { const el = document.getElementById(id); if (!el) return null; const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), visible: r.height > 0 && !el.closest('.hidden') }; };
    const list = document.getElementById('mcp-oauth-list');
    const row = list && list.querySelector('li');
    return {
      cats: box('mcp-client-cats'), tags: box('mcp-client-tags'),
      head: document.getElementById('mcp-oauth-head')?.textContent, headHidden: document.getElementById('mcp-oauth-head')?.classList.contains('hidden'),
      rows: list ? list.children.length : -1, rowText: row ? row.textContent.replace(/\s+/g, ' ').trim().slice(0, 160) : null,
      buttons: row ? [...row.querySelectorAll('button')].map((b) => b.textContent.trim() || b.getAttribute('aria-label')) : [],
      scrollX: document.documentElement.scrollWidth > innerWidth,
    };
  });
  console.log(JSON.stringify(out));
  console.log('errors', errors.length, errors.join(' | '));
  await browser.close();
})();
