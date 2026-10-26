// K24: the selection bar while editing a board text box or sticky. Selects
// "hello", presses Bold on the bar, checks the box reads "**hello** world",
// the bar sits above the selection, Ctrl+Z puts the text back, Ctrl+B and
// a second Bold toggle it off, and the saved data holds the markdown.
//
//   BASE=http://127.0.0.1:8796 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node wbinlinefmt.js
const { boot, openBoardsTab, waitForBoardOpen } = require('./lib.js');

async function probe(page, label, data) {
  const id = await page.evaluate(async (d) => {
    const r = await api('/whiteboard/objects', { method: 'POST', body: JSON.stringify({ kind: 'text', board_id: window.currentBoardId, x: 200, y: 220, width: 220, height: 90, data: d }) });
    const o = await r.json();
    await fetchWhiteboardState();
    renderWhiteboard();
    return o.id;
  }, data);
  await page.waitForTimeout(600);
  const sel = `.wb-object[data-id="${id}"] .wb-text-content`;
  await page.dblclick(sel);
  await page.waitForTimeout(200);
  if (!data.content) await page.keyboard.type('hello world');
  const pick = (from, to) => page.evaluate(([s, a, b]) => {
    const el = document.querySelector(s);
    el.wbEditorSurface.setSelectionRange(a, b);
  }, [sel, from, to]);
  await pick(0, 5);
  await page.waitForTimeout(150);
  const bar = await page.evaluate((s) => {
    const b = document.getElementById('selection-bar');
    const r = window.getSelection().getRangeAt(0).getBoundingClientRect();
    const br = b?.getBoundingClientRect();
    const shown = b ? [...b.querySelectorAll('button')].filter((x) => !x.hidden).map((x) => x.dataset.md || x.dataset.boardMd || x.title) : [];
    return { visible: b && !b.classList.contains('hidden'), gap: br ? Math.round(r.top - br.bottom) : null, dx: br ? Math.round(br.left - r.left) : null, shown };
  }, sel);
  const press = (md) => page.evaluate((m) => {
    const b = document.querySelector(`#selection-bar [data-md="${m}"], #selection-bar [data-board-md="${m}"]`);
    if (!b) return false;
    b.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
  }, md);
  const text = () => page.evaluate((s) => wbEditedText(document.querySelector(s)), sel);
  await press('bold');
  const afterBold = await text();
  await press('bold');
  const toggledOff = await text();
  await page.keyboard.press('Control+z');
  const undone = await text();
  await page.keyboard.press('Control+z');
  const undoneBold = await text();
  await pick(0, 5);
  await page.keyboard.press('Control+b');
  const ctrlB = await text();
  await pick(10, 15);
  await page.keyboard.press('Control+i');
  const ctrlI = await text();
  await pick(0, 3);
  await page.waitForTimeout(100);
  await press('ul');
  const list = await text();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);
  const saved = await page.evaluate(async (i) => {
    await fetchWhiteboardState();
    const o = wbState.objects.find((x) => x.id === i);
    return { content: o.data.content, md: o.data.md };
  }, id);
  console.log(JSON.stringify({ label, bar, afterBold, toggledOff, undone, undoneBold, ctrlB, ctrlI, list, saved }));
}

(async () => {
  const { page, browser } = await boot({});
  await page.waitForTimeout(2500);
  await openBoardsTab(page);
  await page.evaluate(() => document.getElementById('wb-boards-new').click());
  await page.waitForTimeout(1500);
  await waitForBoardOpen(page).catch(() => {});
  await probe(page, 'text', { content: 'hello world' });
  await probe(page, 'sticky', { content: '', sticky: true, bg: '#fff59d', color: '#2a2a1f', font_size: 16 });
  // Back on a note box, the bar is the documents' own again.
  const note = await page.evaluate(() => {
    const box = document.getElementById('entry-content');
    selectionBarShow(asSurface(box));
    const b = document.getElementById('selection-bar');
    return [...b.querySelectorAll('button')].filter((x) => !x.hidden).map((x) => x.dataset.md || x.dataset.boardMd || x.title);
  });
  console.log(JSON.stringify({ label: 'note box after board', shown: note }));
  await browser.close();
})();
