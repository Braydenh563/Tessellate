// INBOX 1451: a live Mermaid diagram on the board. Inserts one through the
// dialog, measures its drawn picture, edits it by double-click, exports the
// board SVG, and turns it into shapes. BASE=http://127.0.0.1:8781 node wbdiagram.js
const {openFresh} = require('./cdlib.js');
(async () => {
  const {browser, page, errors} = await openFresh({width: 1440});
  await page.evaluate(() => wbRunCommand('insert-diagram'));
  await page.waitForFunction(() => document.querySelector('#wb-diagram-preview img')?.naturalWidth > 0, null, {timeout: 20000});
  await page.click('#wb-diagram-save');
  await page.waitForFunction(() => document.querySelector('.wb-object-diagram img')?.naturalWidth > 0, null, {timeout: 20000});
  const drawn = await page.evaluate(() => {
    const box = document.querySelector('.wb-object-diagram');
    const img = box.querySelector('img');
    const r = box.getBoundingClientRect(), i = img.getBoundingClientRect();
    return {box: [r.width, r.height], img: [i.width, i.height], natural: [img.naturalWidth, img.naturalHeight], label: box.getAttribute('aria-label'), selected: wbSelectedItem?.kind};
  });
  console.log('drawn', JSON.stringify(drawn));
  await page.dblclick('.wb-object-diagram');
  await page.waitForFunction(() => document.getElementById('wb-diagram-dialog').open);
  const editing = await page.evaluate(() => ({title: document.getElementById('wb-diagram-title').textContent, shapes: !document.getElementById('wb-diagram-shapes').hidden}));
  console.log('editing', JSON.stringify(editing));
  await page.fill('#wb-diagram-text', 'flowchart LR\n  A[One] --> B[Two] --> C[Three]');
  await page.click('#wb-diagram-save');
  await page.waitForTimeout(1500);
  const saved = await page.evaluate(() => ({src: wbState.objects.find((o) => o.kind === 'diagram')?.data.mermaid, box: (() => { const d = wbState.objects.find((o) => o.kind === 'diagram'); return d && +(d.width / d.height).toFixed(2); })(), ratio: (() => { const im = document.querySelector('.wb-object-diagram img'); return im && +(im.naturalWidth / im.naturalHeight).toFixed(2); })()}));
  console.log('saved', JSON.stringify(saved));
  await page.fill('#wb-diagram-text', '').catch(() => {});
  const bad = await page.evaluate(async () => {
    const d = wbState.objects.find((o) => o.kind === 'diagram');
    const r = await mermaidRequest('flowchart LR\n  A --> ');
    return {error: r.error || '', exportHasImage: (typeof wbExportSvgText === 'function') ? null : undefined, url: wbDiagramDataUrl(d).slice(0, 30)};
  });
  console.log('bad', JSON.stringify(bad));
  await page.dblclick('.wb-object-diagram');
  await page.waitForFunction(() => document.getElementById('wb-diagram-dialog').open);
  await page.click('#wb-diagram-shapes');
  await page.waitForTimeout(2500);
  const shapes = await page.evaluate(() => ({diagrams: wbState.objects.filter((o) => o.kind === 'diagram').length, sketches: wbState.sketches.length}));
  console.log('shapes', JSON.stringify(shapes));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(2500);
  const undone = await page.evaluate(() => ({diagrams: wbState.objects.filter((o) => o.kind === 'diagram').length, sketches: wbState.sketches.length}));
  console.log('undone', JSON.stringify(undone));
  console.log('errors', JSON.stringify(errors));
  await browser.close();
})();
