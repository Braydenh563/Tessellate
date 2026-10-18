// INBOX 1300 C05 (the owner: "when I do / I wouldn't know the other's are
// there unless I scroll down quite far"): type "/" in the chat box and
// measure where the first command row sits against the menu's visible box,
// which row is active, and that ArrowDown and Enter still work. Env: BASE.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(1500);
  await page.click('#chat-input');
  await page.keyboard.type('/');
  await page.waitForTimeout(1500);
  const read = () => page.evaluate(() => {
    const menu = document.getElementById('editor-menu');
    const list = document.getElementById('editor-menu-list') || menu;
    const m = list.getBoundingClientRect();
    const rows = [...list.querySelectorAll('.editor-menu-item')];
    const groupOf = (row) => { let n = row.previousElementSibling; while (n && !n.classList.contains('editor-menu-group')) n = n.previousElementSibling; return n?.textContent.trim(); };
    const firstCmd = rows.find((r) => groupOf(r) === 'Commands');
    const active = list.querySelector('.editor-menu-item[aria-selected="true"], .editor-menu-item.active');
    return {
      menuTop: Math.round(m.top), menuH: Math.round(m.height),
      firstCommandAt: firstCmd ? Math.round(firstCmd.getBoundingClientRect().top - m.top) : null,
      firstCommandVisible: firstCmd ? firstCmd.getBoundingClientRect().bottom <= m.bottom : false,
      groups: [...list.querySelectorAll('.editor-menu-group')].map((g) => g.textContent.trim()),
      active: active ? groupOf(active) + ': ' + active.textContent.trim().slice(0, 30) : null,
    };
  });
  const atSlash = await read();
  await page.keyboard.press('ArrowDown');
  const afterDown = (await read()).active;
  console.log(JSON.stringify({ atSlash, afterDown }));
  await browser.close();
})();
