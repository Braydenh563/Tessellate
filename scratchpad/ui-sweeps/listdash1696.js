// INBOX 1696 cc: which "- " lines keep a raw dash with the caret elsewhere?
//   BASE=http://127.0.0.1:8781 node scratchpad/ui-sweeps/listdash1696.js
const { boot } = require('./lib.js');
const { openDoc } = require('./docopen.js');
const LONG = 'a long item that wraps across the measure because it carries many many words so the view has to fold it onto a second row and maybe a third row as well';
const VARIANTS = {
  plain: `- one\n- two\n- Wizard covers: three`,
  afterWrapped: `- ${LONG}\n- Wizard covers: three`,
  afterLazy: `- first line\ncontinued lazily\n- Wizard covers: three`,
  afterPara: `A paragraph line\n- Wizard covers: three`,
  afterNum: `1. ${LONG}\n- Wizard covers: three`,
  nestedAfterWrapped: `- ${LONG}\n  - Wizard covers: three`,
  threeSpace: `1. one\n   - Wizard covers: three`,
  afterBold: `**Heading words**\n- Wizard covers: three`,
  afterHeading: `## Head\n- Wizard covers: three`,
  starMix: `* one\n- Wizard covers: three`,
  afterTask: `- [ ] task ${LONG}\n- Wizard covers: three`,
  tabIndent: `- one\n\t- Wizard covers: three`,
  twoBlank: `- one\n\n\n- Wizard covers: three`,
  afterCode: "```\ncode\n```\n- Wizard covers: three",
  afterQuote: `> quoted\n- Wizard covers: three`,
};
(async () => {
  const { browser, page } = await boot();
  const body = Object.entries(VARIANTS).map(([k, v]) => `KEY ${k}\n\n${v}`).join('\n\n') + '\n\ntail\n';
  await openDoc(page, { title: 'List dash', content: body });
  await page.waitForTimeout(1500);
  await page.evaluate(() => { const s = docSurface(); const n = s.text.length; s.focus(); s.setSelection(n, n); });
  await page.waitForTimeout(600);
  // CodeMirror draws only the viewport: scroll through and keep every row seen.
  const seen = new Map();
  for (let y = 0; y < 40; y++) {
    const got = await page.evaluate((y) => {
      const sc = document.querySelector('#doc-editor .cm-scroller');
      sc.scrollTop = y * 300;
      return { rows: [...document.querySelectorAll('#doc-editor .cm-line')].map((l) => ({ t: l.innerText.replace(/\n/g, ''), c: l.className, top: l.getBoundingClientRect().top + sc.scrollTop })), end: sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 2 };
    }, y);
    await page.waitForTimeout(120);
    for (const r of got.rows) seen.set(Math.round(r.top) + '|' + r.t, r);
    if (got.end) break;
  }
  const rows = [...seen.values()].sort((a, b) => a.top - b.top);
  let key = '';
  for (const r of rows) {
    if (r.t.startsWith('KEY ')) { key = r.t.slice(4); continue; }
    if (/Wizard covers/.test(r.t)) console.log(`${/^\s*-\s/.test(r.t) ? 'RAW ' : 'ok  '} ${key}: ${JSON.stringify(r.t.slice(0, 30))} [${r.c}]`);
  }
  await browser.close();
})();
