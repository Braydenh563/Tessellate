// GRAPH_PLAN KG9 part two: the suggestions inbox. One sheet, four kinds with
// counts; a name merge, a link type and a link accepted from it; nothing
// sideways at either width; the head on the dialog-head recipe.
//
// Entities have no API (a model extracts them), so they are written straight
// into the server's database: DB=<data dir>/memorymap.db. Run on a fresh data
// dir: earlier runs' look-alike notes take the per-note cap on link pairs.
//
//   BASE=http://127.0.0.1:8819 DB=/tmp/mm-k19/memorymap.db WIDTH=1440 \
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/kg9inbox.js
const { execFileSync } = require('child_process');
const { boot } = require('./lib.js');

const check = (label, ok, detail) => console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
const WIDTH = Number(process.env.WIDTH || 1440);

function entity(name, ids) {
  const py = `import sqlite3,sys,datetime
c=sqlite3.connect(sys.argv[1]);cur=c.cursor()
cur.execute("insert into entities(name,created_at) values(?,?)",(sys.argv[2],datetime.datetime.utcnow().isoformat(" ")))
e=cur.lastrowid
for i in sys.argv[3].split(","):
    cur.execute("insert into entity_mentions(entity_id,entry_id,created_at) values(?,?,?)",(e,int(i),datetime.datetime.utcnow().isoformat(" ")))
c.commit();print(e)`;
  return Number(execFileSync('python3', ['-c', py, process.env.DB, name, ids.join(',')]).toString().trim());
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: WIDTH, height: WIDTH < 600 ? 844 : 900 }, ...(WIDTH < 600 ? { hasTouch: true, isMobile: true } : {}) });
  const s = Date.now().toString(36);
  const ids = await page.evaluate(async (s) => {
    const make = (content, tags = []) => apiJson('/entries', { method: 'POST', body: JSON.stringify({ content, tags }) });
    const hub = await make(`# Studio plan ${s}\n\nThe year.`);
    const a = await make(`# Glaze trial ${s}\n\nCone 6 celadon`, [`glz${s}`]);
    const b = await make(`# Firing log ${s}\n\nThursday went well`, [`glz${s}`]);
    for (const n of [a, b]) await apiJson(`/entries/${n.id}/links`, { method: 'POST', body: JSON.stringify({ target_id: hub.id }) });
    const c = await make(`# Kiln note ${s}\n\nCone 10, for example [[Studio plan ${s}]] covers it.`);
    await loadEntries();
    return { hub: hub.id, a: a.id, b: b.id, c: c.id };
  }, s);
  const sam = entity(`Sam${s}`, [ids.a, ids.b]);
  const samLee = entity(`Sam${s} Lee`, [ids.b, ids.hub]);
  await page.evaluate(() => openSuggestionsInbox('links'));
  await page.waitForTimeout(2500);

  const head = await page.evaluate(() => {
    const card = document.querySelector('[data-sheet="suggestions"] .sheet-card');
    const r = card.getBoundingClientRect();
    const tabs = [...card.querySelectorAll('#inbox-kind option')].map((t) => t.textContent.trim());
    return {
      w: Math.round(r.width), h: Math.round(r.height), vw: innerWidth, vh: innerHeight,
      sideways: card.scrollWidth > card.clientWidth + 1 || document.documentElement.scrollWidth > innerWidth,
      help: Boolean(card.querySelector('.dialog-head [data-help-for="inbox-help"]')),
      closeLast: card.querySelector('.dialog-head-actions > :last-child')?.classList.contains('sheet-close'),
      tabs,
      segOver: (() => { const g = card.querySelector('#inbox-kind').closest('.select-shell'); return g.scrollWidth > g.clientWidth + 1 || g.getBoundingClientRect().right > r.right; })(),
      pills: card.querySelectorAll('.seg').length,
    };
  });
  console.log(JSON.stringify(head));
  check('the kinds are one list, no pill well (INBOX 670)', head.pills === 0 && head.tabs.length === 4, `pills ${head.pills}`);
  check('one sheet with four kinds', head.tabs.length === 4, head.tabs.join(' | '));
  check('counts on the kinds', /^Links \(\d+\)$/.test(head.tabs[0]) && /^Names \(\d+\)$/.test(head.tabs[2]) && /^Link types \(\d+\)$/.test(head.tabs[3]), head.tabs.join(' | '));
  check('head: ? beside the title, close last', head.help && head.closeLast);
  check('within the window, nothing sideways', head.h <= head.vh && !head.sideways, `${head.w}x${head.h}`);
  check('the kinds fit on one line', !head.segOver);

  // Links: the structural pair, linked from the sheet.
  const link = await page.evaluate((s) => {
    const r = [...document.querySelectorAll('[data-sheet="suggestions"] .link-suggestion')].find((x) => x.textContent.includes(`Glaze trial ${s}`) && x.textContent.includes(`Firing log ${s}`));
    if (!r) return null;
    const out = { sideways: r.scrollWidth > r.clientWidth + 1, why: r.querySelector('.link-suggestion-why')?.textContent || '' };
    return out;
  }, s);
  check('Links: the structural pair with its reasons', link && /both/.test(link.why) && !link.sideways, link && link.why);

  // Names: Sam into Sam Lee.
  await page.selectOption('#inbox-kind', 'names');
  await page.waitForTimeout(300);
  const nameRow = await page.evaluate((s) => {
    const pane = document.getElementById('inbox-pane-names');
    const r = [...pane.querySelectorAll('.inbox-row')].find((x) => x.textContent.includes(`Sam${s} Lee`));
    if (!r) return { visible: !pane.hidden, text: pane.textContent.slice(0, 200) };
    const box = r.getBoundingClientRect();
    return { visible: !pane.hidden, text: r.querySelector('.link-suggestion-pair').textContent, why: r.querySelector('.link-suggestion-why').textContent, w: Math.round(box.width), sideways: r.scrollWidth > r.clientWidth + 1 };
  }, s);
  console.log(JSON.stringify(nameRow));
  check('Names: the pair, the fuller name kept', nameRow.visible && nameRow.text && nameRow.text.startsWith(`Sam${s}`), nameRow.text);
  await page.evaluate((s) => {
    const r = [...document.querySelectorAll('#inbox-pane-names .inbox-row')].find((x) => x.textContent.includes(`Sam${s} Lee`));
    r?.querySelector('.link-suggestion-actions button')?.click();
  }, s);
  await page.waitForTimeout(1500);
  const merged = execFileSync('python3', ['-c', `import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);print(c.execute("select count(*) from entity_mentions where entity_id=?",(int(sys.argv[2]),)).fetchone()[0], c.execute("select merged_into from entities where id=?",(int(sys.argv[3]),)).fetchone()[0])`, process.env.DB, String(samLee), String(sam)]).toString().trim();
  check('Merge moved every mention', merged === `3 ${samLee}`, merged);
  const namesCount = await page.evaluate(() => document.querySelector('#inbox-kind option[value="names"]').textContent);
  check('the count went down', namesCount === 'Names' || /^Names \(\d+\)$/.test(namesCount), namesCount);

  // Link types: the wiki link whose sentence says "for example".
  await page.selectOption('#inbox-kind', 'types');
  await page.waitForTimeout(300);
  const typeRow = await page.evaluate((s) => {
    const r = [...document.querySelectorAll('#inbox-pane-types .inbox-row')].find((x) => x.textContent.includes(`Kiln note ${s}`));
    if (!r) return null;
    const mark = r.querySelector('.doc-backlink-context mark');
    return { mark: mark?.textContent, button: r.querySelector('.link-suggestion-actions button')?.textContent.trim(), sideways: r.scrollWidth > r.clientWidth + 1 };
  }, s);
  console.log(JSON.stringify(typeRow));
  check('Link types: the cue marked in its sentence', typeRow && /for example/i.test(typeRow.mark || ''), typeRow && typeRow.mark);
  await page.evaluate((s) => {
    const r = [...document.querySelectorAll('#inbox-pane-types .inbox-row')].find((x) => x.textContent.includes(`Kiln note ${s}`));
    r?.querySelector('.link-suggestion-actions button')?.click();
  }, s);
  await page.waitForTimeout(1200);
  const typed = execFileSync('python3', ['-c', `import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);print(c.execute("select link_type from entry_links where source_entry_id=? and target_entry_id=?",(int(sys.argv[2]),int(sys.argv[3]))).fetchone()[0])`, process.env.DB, String(ids.c), String(ids.hub)]).toString().trim();
  check('the link took the type', typed === 'example_of', typed);

  // Disagreements: the pane is there and runs nothing on open.
  await page.selectOption('#inbox-kind', 'tensions');
  await page.waitForTimeout(300);
  const t = await page.evaluate(() => {
    const pane = document.getElementById('inbox-pane-tensions');
    return { visible: !pane.hidden, start: [...pane.querySelectorAll('button')].some((b) => b.textContent === 'Start the review'), cards: pane.querySelectorAll('.tension-card').length };
  });
  check('Disagreements: Start the review, nothing run', t.visible && t.start && t.cards === 0, JSON.stringify(t));

  // Keyboard: the list opens on Enter, Down moves to the next kind, Enter takes it.
  await page.focus('#inbox-kind ~ .select-opener');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(250);
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  const after = await page.evaluate(() => document.getElementById('inbox-kind').value);
  check('the list walks to the next kind from the keyboard', after === 'names', after);

  await page.waitForTimeout(600);
  await page.screenshot({ path: `${process.env.SCRATCH || '.'}/kg9inbox-${WIDTH}-${process.env.THEME || 'light'}.png` });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  check('Escape closes it', await page.evaluate(() => !document.querySelector('[data-sheet="suggestions"]')));
  await browser.close();
})();
