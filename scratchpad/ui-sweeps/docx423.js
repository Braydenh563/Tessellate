// WORLD_CLASS 423 (b): the Word export of a document with [TOC], a callout and
// `::: columns`, opened as XML. Prints one line per claim.
//   BASE=http://127.0.0.1:8797 node scratchpad/ui-sweeps/docx423.js
const { boot } = require('./lib.js');
const { execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const TEXT = [
  '# Report', '', '[TOC]', '', '## Plan', '',
  '> [!warning] Heads up', '> Check the **dates**.', '> - one', '> - two', '',
  '::: columns', 'Left column text.', '', ':::column', 'Right column text.', ':::', '',
  '## After', '', 'Plain closing text.', '',
].join('\n');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab('documents')); await page.waitForTimeout(2500);
  await page.evaluate(() => { window.__saved = null; saveFile = async (name, blob) => { window.__saved = blob; return true; }; });
  await page.evaluate((text) => { currentDoc = { title: 'Export check', content: text }; docCmView = null; }, TEXT);
  const ok = await page.evaluate(async () => { await lazyScript("/js/documents-word.js"); return docWordExport(); });
  console.log("ok=", ok, await page.evaluate(() => [...document.querySelectorAll(".toast")].map((t) => t.textContent).join("|")));
  const b64 = await page.evaluate(async () => {
    if (!window.__saved) return '';
    const buf = new Uint8Array(await window.__saved.arrayBuffer());
    let s = '';
    for (const x of buf) s += String.fromCharCode(x);
    return btoa(s);
  });
  const file = path.join(os.tmpdir(), `docx423-${process.pid}.docx`);
  fs.writeFileSync(file, Buffer.from(b64, 'base64'));
  const py = path.resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
  const out = execFileSync(py, ['-I', '-c', `
import re, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
x = z.read('word/document.xml').decode()
s = z.read('word/settings.xml').decode()
print('export ok:', sys.argv[2])
print('TOC instrText:', bool(re.search(r'<w:instrText[^>]*>TOC ', x)))
print('updateFields:', '<w:updateFields/>' in s)
print('shd fills:', re.findall(r'<w:shd [^>]*w:fill="([0-9A-F]{6})"', x))
print('cols num:', re.findall(r'<w:cols [^>]*w:num="(\\d+)"', x))
print('column breaks:', x.count('w:type="column"'))
print('callout title bold run:', bool(re.search(r'<w:b/>.{0,200}Heads up|Heads up', x)))
print('stray Contents para text:', x.count('>Contents<'))
`, file, String(ok)], { encoding: 'utf8' });
  console.log(out);
  fs.unlinkSync(file);
  await browser.close();
})();
