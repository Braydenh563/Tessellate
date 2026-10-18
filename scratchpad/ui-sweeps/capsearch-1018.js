// Is a caption findable by keyword search? (CHAT_PLAN Open from Phase 6)
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node capsearch-1018.js
const { boot } = require('./lib.js');
const PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8DAwMDAxMDAwAAADwEBAAyEAvUAAAAASUVORK5CYII=';
(async () => {
  const { browser, page } = await boot();
  const out = await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const fd = new FormData();
    fd.append('file', new File([bytes], 'plain.png', { type: 'image/png' }));
    fd.append('direct', 'true');
    const up = await (await fetch('/media/upload', { method: 'POST', body: fd, headers: { 'X-Auth-Token': authToken(), 'X-Workspace-ID': activeSpaceId() } })).json();
    await api(`/media/${up.id}/caption`, { method: 'POST', body: JSON.stringify({ text: 'a zebrafinch on a windowsill' }) });
    const res = {};
    for (const q of ['zebrafinch', 'windowsill']) {
      const r = await apiJson(`/search?q=${q}&hybrid=false`).catch((e) => String(e));
      res[q] = JSON.stringify(r).slice(0, 300);
    }
    return res;
  }, PNG);
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
