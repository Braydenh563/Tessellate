// INBOX 1451 and 1546 P5: a live Mermaid diagram on the board, edited in the block builder (the dialog
// diagram-embed.js opens). Inserts one, double-clicks it open, checks that an open and a Done with no
// change leaves the source byte for byte, changes it (one undo step), turns it into shapes.
//   BASE=http://127.0.0.1:8781 node wbdiagram.js [width]
const {openFresh} = require('./cdlib.js');
const pngMeasure = async (page, source) => page.evaluate(async (src) => {
  const res = await mermaidRequest(src);
  const vb = /viewBox="([^"]+)"/.exec(res.svg)[1].split(/[ ,]+/).map(Number);
  const saved = [];
  const orig = window.saveFile;
  window.saveFile = async (name, blob) => { saved.push({name, blob}); };
  await diagramModel.embed.out('png', src, 'board');
  window.saveFile = orig;
  const bmp = await createImageBitmap(saved[0].blob);
  const cv = Object.assign(document.createElement('canvas'), {width: bmp.width, height: bmp.height});
  const cx = cv.getContext('2d');
  cx.drawImage(bmp, 0, 0);
  const d = cx.getImageData(0, 0, cv.width, cv.height).data;
  let non = 0;
  for (let i = 0; i < d.length; i += 4) if (Math.abs(d[i] - d[0]) + Math.abs(d[i + 1] - d[1]) + Math.abs(d[i + 2] - d[2]) > 24) non++;
  return {viewBox: vb.slice(2), png: [bmp.width, bmp.height], times: [bmp.width / vb[2], bmp.height / vb[3]], nonBackground: +(non / (cv.width * cv.height)).toFixed(3)};
}, source);
(async () => {
  const width = Number(process.argv[2] || 1440);
  const {browser, page, errors} = await openFresh({width});
  const sample = 'flowchart TD\n  A[Start] --> B{Ready?}\n  B -->|yes| C[Ship it]\n\n';
  await page.evaluate((s) => wbInsertDiagram(s), sample);
  await page.waitForFunction(() => document.querySelector('.wb-object-diagram img')?.naturalWidth > 0, null, {timeout: 20000});
  const stored = () => page.evaluate(() => wbState.objects.find((o) => o.kind === 'diagram')?.data.mermaid);
  const first = await stored();
  // Insert asks first (R12): the sheet of diagrams and New; Cancel adds nothing.
  await page.evaluate(() => wbRunCommand('insert-diagram'));
  await page.waitForSelector('.dgm-choose-dialog', {timeout: 15000});
  const insertTitle = await page.evaluate(() => document.querySelector('.dgm-choose-dialog .dialog-head-title').textContent);
  await page.click('.dgm-choose-dialog .space-dialog-actions button:text-is("Cancel")');
  await page.waitForTimeout(300);
  console.log('insert', JSON.stringify({insertTitle, diagrams: await page.evaluate(() => wbState.objects.filter((o) => o.kind === 'diagram').length)}));
  // double-click opens the builder; Done with no change keeps the source byte for byte
  await page.dblclick('.wb-object-diagram');
  await page.waitForSelector('.dgm-dialog .dgm-block', {timeout: 15000});
  const open = await page.evaluate(() => ({title: document.querySelector('.dgm-dialog .dialog-head-title').textContent, blocks: document.querySelectorAll('.dgm-dialog .dgm-block').length, pic: !!document.querySelector('.dgm-dialog .dgm-picture img'), oldDialog: !!document.getElementById('wb-diagram-dialog'), width: Math.round(document.querySelector('.dgm-dialog').getBoundingClientRect().width), fits: document.documentElement.scrollWidth <= innerWidth}));
  console.log('open', JSON.stringify(open));
  await page.click('.dgm-dialog .space-dialog-actions button.accent');
  await page.waitForTimeout(600);
  console.log('byteEqual', (await stored()) === first, JSON.stringify(first.slice(-4)));
  // a change then Done: saved, one undo step
  await page.dblclick('.wb-object-diagram');
  await page.waitForSelector('.dgm-dialog .dgm-block');
  await page.click('.dgm-dialog .dgm-tile[data-shape="round"]');
  await page.waitForTimeout(300);
  await page.keyboard.type('Extra');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  await page.click('.dgm-dialog .space-dialog-actions button.accent');
  await page.waitForTimeout(1500);
  const changed = await stored();
  console.log('changed', JSON.stringify({has: changed.includes('Extra'), differs: changed !== first}));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(1200);
  console.log('undone', (await stored()) === first);
  // exports measured on the board's source
  console.log('png', JSON.stringify(await pngMeasure(page, first.trim())));
  // Turn into shapes from the builder's menu, then undo
  await page.dblclick('.wb-object-diagram');
  await page.waitForSelector('.dgm-dialog .dgm-block');
  await page.click('.dgm-dialog .dgm-more button');
  await page.waitForTimeout(200);
  const rows = await page.evaluate(() => [...document.querySelectorAll('.action-menu:not(.hidden) .menu-item')].map((b) => b.textContent.trim()));
  console.log('menu', JSON.stringify(rows));
  await page.locator('.action-menu:not(.hidden) .menu-item', {hasText: 'Turn into shapes'}).click();
  await page.waitForTimeout(2500);
  console.log('shapes', JSON.stringify(await page.evaluate(() => ({diagrams: wbState.objects.filter((o) => o.kind === 'diagram').length, sketches: wbState.sketches.length, dialog: !!document.querySelector('.dgm-dialog')}))));
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(2500);
  console.log('undoShapes', JSON.stringify(await page.evaluate(() => ({diagrams: wbState.objects.filter((o) => o.kind === 'diagram').length, sketches: wbState.sketches.length}))));
  console.log('errors', JSON.stringify(errors));
  await browser.close();
})();
