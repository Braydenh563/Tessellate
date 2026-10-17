// B04/B09: the autocorrect underline and its menu, driven in the real boxes:
// a plain textarea, the mounted CodeMirror note box (Capture) and the document
// editor. Prints numbers: mark rect against the word's rect, the menu rect,
// the box text after each choice. BASE=http://127.0.0.1:PORT node autocorrectmenu.js
const { boot } = require('./lib.js');

const read = (page, sel) => page.evaluate((s) => {
  const e = document.querySelector(s);
  if (!e) return null;
  return e.value ?? e.innerText;
}, sel);

const markRect = (page) => page.evaluate(() => {
  const m = document.querySelector('.autocorrect-mark');
  if (!m) return null;
  const r = m.getBoundingClientRect();
  return { l: Math.round(r.left), t: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), hidden: m.hidden };
});

const menuRect = (page) => page.evaluate(() => {
  const m = [...document.querySelectorAll('.action-menu')].find((x) => /Put back/.test(x.innerText));
  if (!m) return null;
  const r = m.getBoundingClientRect();
  return { l: Math.round(r.left), t: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), text: m.innerText.replace(/\n/g, ' | ') };
});

async function probe(page, label, focusSel, readSel, how = 'click') {
  const out = {};
  await page.click(focusSel, { force: true });
  await page.waitForTimeout(500);
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Delete');
  await page.keyboard.type('I ran a teh ', { delay: 30 });
  await page.waitForTimeout(300);
  out.text = await read(page, readSel);
  out.mark = await markRect(page);
  // The corrected word's own box in the editor's DOM, to compare with the mark.
  out.word = await page.evaluate((sel) => {
    const root = document.querySelector(sel.replace(/ \.cm-content$/, '') + ' .cm-content') || document.querySelector('.cm-content');
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const i = n.data.lastIndexOf('the');
      if (i < 0) continue;
      const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 3);
      const b = r.getBoundingClientRect();
      return { l: Math.round(b.left), t: Math.round(b.top), w: Math.round(b.width), h: Math.round(b.height) };
    }
    return null;
  }, readSel);
  if (!out.mark) return out;
  const cx = out.mark.l + out.mark.w / 2, cy = out.mark.t + out.mark.h / 2;
  if (how === 'ctrlz') {
    await page.keyboard.press('Control+z');
    await page.waitForTimeout(400);
    out.textAfterCtrlZ = await read(page, readSel);
    out.markAfterCtrlZ = await markRect(page);
    return out;
  }
  if (how === 'hover') {
    await page.mouse.move(cx, cy);
    await page.waitForTimeout(700);
  } else {
    await page.mouse.click(cx, cy);
    await page.waitForTimeout(400);
  }
  out.menu = await menuRect(page);
  out.textAfterOpen = await read(page, readSel);
  if (out.menu) {
    await page.getByText(/Put back/).first().click();
    await page.waitForTimeout(300);
    out.textAfterPutBack = await read(page, readSel);
  }
  return out;
}

(async () => {
  const { browser, page } = await boot();
  const out = {};
  let probes = JSON.parse(process.env.PROBES || '[["capture","#entry-content","#entry-content"]]');
  if (process.env.DOC) {
    probes = [['document', '#doc-editor .cm-content', '#doc-editor .cm-content']];
    await page.evaluate(() => switchTab('documents'));
    await page.waitForTimeout(1500);
    await page.evaluate(async () => {
      const d = await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: 'Plan', content: 'Start.\n', file_type: 'md' }) });
      await loadDocuments(d.id);
    });
    await page.waitForTimeout(1500);
    await page.evaluate(() => { const c = document.getElementById('doc-autocorrect'); if (c) c.checked = true; });
  } else {
  await page.evaluate(() => switchTab('notes'));
  await page.waitForTimeout(1000);
  await page.evaluate(() => [...document.querySelectorAll('#tab-notes button')].find((x) => x.textContent.trim() === 'Capture' && x.offsetParent)?.click());
  await page.waitForTimeout(800);
  await page.evaluate(() => document.getElementById('entry-content').focus());
  await page.waitForTimeout(2500);
  }
  for (const [label, focus, read_] of probes) out[label] = await probe(page, label, focus, read_ || focus, process.env.HOW || 'click');
  out.cm = await page.evaluate(() => document.querySelectorAll('.cm-editor').length);
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
