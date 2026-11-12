// INBOX 279 (3) and (4): the two Library blocks the owner asked to be
// redesigned, counted as ranks rather than described.
//
//   (3) "I want you to better redesign the content in the text extracted from
//       this file dropdown in the files subtab"
//   (4) "I als want you to better design the bottom text for captions and ocr
//       in the image cards in the library images subtab"
//
// Both reports are about the same thing: how many rows of chrome one fact is
// wearing. So both halves of this print the *rows* under the thing the surface
// is about, with each one's class and height, at rest and once opened, and the
// checks are counts.
//
// Seed first: seed-libtext.js, then seed-libtext.py against the data dir.
//
//   BASE=http://127.0.0.1:8991 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     NODE_PATH=/opt/node22/lib/node_modules SCRATCH=/tmp/claude-0 \
//     timeout 115 node libreadingfoot.js
const { boot } = require('./lib.js');

let failures = 0;
const check = (label, ok, detail) => {
  if (!ok) failures += 1;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}  ${detail}`);
};

// Every box in a subtree that is really drawn, with the handle that names it.
// `offsetParent` is null for a `display: none` ancestor, which is how a closed
// fold's body is kept out of the count.
const WALK = `
  (root) => {
    const seen = (el) => {
      if (!el || !el.offsetParent) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    const name = (el) =>
      (el.className || '').toString().split(' ').filter((c) => c.startsWith('library-')).join('.')
      || el.tagName.toLowerCase();
    const out = [];
    const walk = (el, depth) => {
      for (const child of el.children) {
        if (!seen(child)) continue;
        const r = child.getBoundingClientRect();
        out.push({ cls: name(child), h: Math.round(r.height * 10) / 10, depth });
        if (depth < 3) walk(child, depth + 1);
      }
    };
    walk(root, 0);
    return out;
  }
`;

async function openLibrary(page, subtab) {
  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(800);
  await page.evaluate((want) => {
    const b = [...document.querySelectorAll('#library-subtabs button, [data-subtab]')].find(
      (e) => new RegExp(want, 'i').test(e.textContent || e.dataset.subtab || '')
    );
    if (b) b.click();
  }, subtab);
  await page.waitForTimeout(1800);
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 950 } });

  // --- (3) the Files sub-tab's reading block ------------------------------
  await openLibrary(page, 'file');
  const fileRest = await page.evaluate((walk) => {
    const fold = document.querySelector('.library-file-facts, .library-image-tile .library-image-reading');
    const tile = document.querySelector('.library-image-tile');
    const reading = tile.querySelector('.library-image-reading');
    return {
      tile: Math.round(tile.getBoundingClientRect().height * 10) / 10,
      summary: reading ? reading.querySelector('summary').textContent : null,
      rows: reading ? eval(walk)(reading) : [],
      controls: [...tile.querySelectorAll('button, summary')].filter((e) => e.offsetParent).length,
      _f: Boolean(fold),
    };
  }, WALK);
  console.log(`files at rest: tile ${fileRest.tile}px, summary "${fileRest.summary}", ${fileRest.controls} controls`);

  // The first tile is whichever file sorts first; on a notebook where it has no
  // extracted text its fold holds the empty note, not a reading. Open the first
  // tile that has one (marked so the measure below reads the same tile).
  await page.evaluate(() => {
    const d = [...document.querySelectorAll('.library-image-tile .library-image-reading')].find((e) =>
      e.querySelector('.library-file-reading-text')
    );
    if (d) { d.open = true; d.closest('.library-image-tile').dataset.rf = '1'; }
  });
  await page.waitForTimeout(500);
  const fileOpen = await page.evaluate((walk) => {
    const tile = document.querySelector('.library-image-tile[data-rf]') || document.querySelector('.library-image-tile');
    const reading = tile.querySelector('.library-image-reading');
    const body = reading.querySelector('.library-image-reading-body');
    return {
      tile: Math.round(tile.getBoundingClientRect().height * 10) / 10,
      block: Math.round(body.getBoundingClientRect().height * 10) / 10,
      rows: eval(walk)(body),
      controls: [...body.querySelectorAll('button, summary')].filter((e) => e.offsetParent).length,
      meta: (body.querySelector('.library-file-summary-meta') || {}).textContent || null,
      readingShown: Boolean(
        body.querySelector('.library-file-reading-text') &&
          body.querySelector('.library-file-reading-text').offsetParent
      ),
    };
  }, WALK);
  console.log(`files open:  tile ${fileOpen.tile}px, block ${fileOpen.block}px, ${fileOpen.controls} controls, meta "${fileOpen.meta}"`);
  for (const r of fileOpen.rows) console.log(`   ${'  '.repeat(r.depth)}${r.cls}  ${r.h}`);
  check(
    'files: the open reading block is at most two controls',
    fileOpen.controls <= 2,
    `${fileOpen.controls} controls under the fold`
  );
  check(
    'files: the reading itself is on screen once the fold is open',
    fileOpen.readingShown,
    `reading visible: ${fileOpen.readingShown}`
  );

  // --- (4) the Images sub-tab's card foot ---------------------------------
  await openLibrary(page, 'image');
  const cards = await page.evaluate((walk) => {
    const out = [];
    for (const tile of document.querySelectorAll('.library-image-tile')) {
      const frame = tile.querySelector('.library-image-frame');
      const fields = tile.querySelector('.library-image-fields');
      out.push({
        name: (tile.querySelector('.library-image-caption') || {}).textContent || '',
        card: Math.round(tile.getBoundingClientRect().height * 10) / 10,
        picture: frame ? Math.round(frame.getBoundingClientRect().height * 10) / 10 : null,
        foot: frame
          ? Math.round((tile.getBoundingClientRect().bottom - frame.getBoundingClientRect().bottom) * 10) / 10
          : null,
        rows: fields ? eval(walk)(fields) : [],
        provenanceOnFace: Boolean(
          tile.querySelector('.library-image-provenance') &&
            tile.querySelector('.library-image-provenance').offsetParent
        ),
        title: tile.title || '',
      });
    }
    return out;
  }, WALK);
  for (const c of cards) {
    console.log(`card ${c.card}px  picture ${c.picture}  foot ${c.foot}  rows ${c.rows.length}  title "${c.title}"`);
    for (const r of c.rows) console.log(`   ${'  '.repeat(r.depth)}${r.cls}  ${r.h}`);
  }
  const feet = cards.map((c) => c.foot);
  check(
    'images: the feet agree to within a row',
    Math.max(...feet) - Math.min(...feet) <= 44,
    `feet ${feet.join(' / ')}`
  );

  // And the state the report's screenshot is of: the reading asked for. Today
  // that is a `<details>` opening in place; the ask is that it stops being six
  // rows of chrome under one thumbnail.
  const opened = await page.evaluate((walk) => {
    const tile = [...document.querySelectorAll('.library-image-tile')].find((t) =>
      t.querySelector('.library-image-reading, .library-image-text-chip')
    );
    if (!tile) return null;
    const chip = tile.querySelector('.library-image-text-chip');
    const fold = tile.querySelector('.library-image-reading');
    if (fold) fold.open = true;
    const fields = tile.querySelector('.library-image-fields');
    return {
      opensADialog: Boolean(chip),
      card: Math.round(tile.getBoundingClientRect().height * 10) / 10,
      rows: eval(walk)(fields),
      provenanceOnFace: Boolean(
        tile.querySelector('.library-image-provenance') &&
          tile.querySelector('.library-image-provenance').offsetParent
      ),
      title: tile.title || '',
    };
  }, WALK);
  if (opened) {
    console.log(
      `reading asked for: card ${opened.card}px, ${opened.rows.length} boxes, chip ${opened.opensADialog}, title "${opened.title}"`
    );
    for (const r of opened.rows) console.log(`   ${'  '.repeat(r.depth)}${r.cls}  ${r.h}`);
  }
  check(
    'images: the model names are on the card, not in it',
    Boolean(opened) && !opened.provenanceOnFace && /escribed by/.test(opened.title),
    opened ? `title "${opened.title}"` : 'no card with a reading'
  );
  check(
    'images: asking for the text does not grow the card',
    Boolean(opened) && Math.abs(opened.card - cards[cards.length - 1].card) < 1,
    opened ? `${cards[cards.length - 1].card} -> ${opened.card}` : 'no card with a reading'
  );

  // The capability the chip must not have taken with the fold: correcting a
  // reading by hand. The menu's "Type the text in this picture" mounts the
  // editable panel (`revealReading`), and it has to still be there.
  await page.evaluate(() => {
    const tile = document.querySelectorAll('.library-image-tile')[0];
    tile.querySelector('.menu-wrap > button[aria-haspopup="menu"]')?.click();
  });
  await page.waitForTimeout(400);
  await page.evaluate(() => {
    const row = [...document.querySelectorAll('.action-menu:not(.hidden) [role="menuitem"]')].find(
      (b) => /Type the text/.test(b.textContent || '')
    );
    if (row) row.click();
  });
  await page.waitForTimeout(700);
  const editing = await page.evaluate(() => {
    const tile = document.querySelectorAll('.library-image-tile')[0];
    const panel = tile.querySelector('.library-image-reading');
    return {
      mounted: Boolean(panel && panel.offsetParent),
      open: Boolean(panel && panel.open),
      box: Boolean(tile.querySelector('.library-image-vision-ocr, .library-image-reading textarea')),
    };
  });
  check(
    'images: the menu can still put the editable reading on the card',
    editing.mounted && editing.open && editing.box,
    JSON.stringify(editing)
  );

  console.log(failures ? `FAILURES ${failures}` : 'all checks passed');
  await browser.close();
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
