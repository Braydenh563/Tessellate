// What an open reading does to the cards beside it, on both media sub-tabs.
//
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     timeout 110 node scratchpad/ui-sweeps/imagefold.js
//
// **This probe was stale and said so by passing.** It was written against the
// picture card's own `<details>` reading fold: seven cards in one row at 1440,
// read shut and with one fold open, and the number it was about was the *tail*,
// the distance from the last thing painted in a card to the card's bottom edge.
// It measured 240.7px cards with a 42.6px tail shut and 411.1px cards with a
// 213px tail open, on five row-mates that had nothing to show for it.
//
// That fold no longer exists on a picture card. `35a9ef9` replaced it with the
// `.library-chip` "Text" recipe (DESIGN.md's index, INBOX 279) precisely
// because a 180px tile has nowhere to open into, and the chip opens the
// lightbox instead. So `document.querySelector('.library-image-tile
// .library-image-card-fold')` found nothing, `.open = true` on nothing changed
// nothing, and the probe printed its "shut" numbers twice and exited 0.
//
// Told apart from a regression the way this project does, by serving the
// frontend at the commit before that one (`35a9ef9^`, b90d208) and running the
// same file: there, shut 240.7px with 42.6px tails, one open 411.1px against
// 199.1px row-mates with 1px tails. It works there and finds nothing here, and
// the change between them is a commit that says it removed the fold. Stale.
//
// What it measures now is the same question on the surface that still has a
// fold at rest. The Files sub-tab draws through the same tile builder
// (`renderLibraryImagesGallery`) and keeps the `<details>` (`.library-image-
// reading`, summary "Text extracted from this file"), because a document's
// reading is pages long and has no lightbox-sized answer. The Images half is
// now the ratchet for INBOX 279: a picture card must have nothing to open at
// rest, and every card in a row must stand at the same height.
//
// Measured on the Files sub-tab for the first time (its rows had never been
// on screen in this sandbox): it is `display: flex`, one row per line, not the
// pictures' grid, so opening a fold there moved 0 of 0 row-mates and pushed
// its own row from 160 to 167.5px. That half is therefore a ratchet rather
// than a live finding: the cost the picture cards paid comes back the moment
// those rows are laid out as a grid again.
//
// It fails rather than passing when it has nothing to measure. That is the
// whole reason it was worth keeping: a probe whose subject has been deleted
// must say so, not report silence as a pass.
const { boot } = require('./lib.js');

const PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8DAwMDAxMDAwAAADwEBAAyEAvUAAAAASUVORK5CYII=';
const OCR = 'INGEST -> PARSE -> STORE\nnightly batch?\nask Priya about the retry budget\n'.repeat(12);

(async () => {
  const { browser, page } = await boot();
  const fail = [];

  await page.evaluate(async ({ b64, ocr }) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    // A hand-written one-page PDF, the same builder `seed-file.js` uses: the
    // upload route takes images and PDFs only, and the sweeps stay text
    // rather than shipping a binary.
    const pdfBytes = (title) => {
      const body = `BT /F1 12 Tf 40 120 Td (${title}) Tj ET`;
      const objs = [
        '<</Type/Catalog/Pages 2 0 R>>',
        '<</Type/Pages/Kids[3 0 R]/Count 1>>',
        '<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>',
        `<</Length ${body.length}>>\nstream\n${body}\nendstream`,
        '<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>',
      ];
      let pdf = '%PDF-1.4\n';
      const offsets = [];
      objs.forEach((o, i) => { offsets.push(pdf.length); pdf += `${i + 1} 0 obj\n${o}\nendobj\n`; });
      const xref = pdf.length;
      pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
      for (const off of offsets) pdf += String(off).padStart(10, '0') + ' 00000 n \n';
      pdf += `trailer\n<</Size ${objs.length + 1}/Root 1 0 R>>\nstartxref\n${xref}\n%%EOF\n`;
      return pdf;
    };
    const upload = async (blob, name, type) => {
      const fd = new FormData();
      fd.append('file', new File([blob], name, { type }));
      fd.append('direct', 'true');
      // Raw fetch, not `api()`: `api()` forces a JSON content type, which
      // strips the multipart boundary and makes the upload a 422.
      const r = await fetch('/media/upload', {
        method: 'POST', body: fd,
        headers: { 'X-Auth-Token': authToken(), 'X-Workspace-ID': activeSpaceId() },
      });
      return (await r.json()).id;
    };
    for (let i = 0; i < 6; i++) {
      const id = await upload(bytes, `pic-${i}.png`, 'image/png');
      await api(`/media/${id}/caption`, { method: 'POST', body: JSON.stringify({ text: 'A picture with a caption of its own.' }) });
      if (i === 0) await api(`/media/${id}/ocr`, { method: 'POST', body: JSON.stringify({ text: ocr }) });
    }
    // Four documents, so the Files sub-tab has rows at all: they have never
    // been on screen in this sandbox (OPEN.md's Library section).
    //
    // No reading is seeded on them, and not for want of trying: `POST
    // /media/{id}/ocr` and `/vision-ocr` both answer 415 for a PDF
    // (`OCR_SUFFIXES` and `VISION_OCR_SUFFIXES` are the six image types), so
    // an uploaded document's `ocr_text`/`vision_ocr_text` cannot be set from
    // the outside at all. The fold is therefore measured with the body it has
    // for a file nothing has read, which is the state every uploaded document
    // in this sandbox is in.
    for (let i = 0; i < 4; i++) {
      await upload(pdfBytes(`Weekly review ${i}`), `doc-${i}.pdf`, 'application/pdf');
    }
  }, { b64: PNG, ocr: OCR });

  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(800);
  const subtab = async (word) => {
    await page.evaluate((w) => {
      const b = [...document.querySelectorAll('#library-subtabs button, [data-subtab]')]
        .find((e) => new RegExp(w, 'i').test(e.textContent || e.dataset.subtab || ''));
      if (b) b.click();
    }, word);
    await page.waitForTimeout(2500);
  };

  // One read of the row the first card sits in: the heights, the pictures, and
  // the tail under the last painted thing in each card.
  const read = () =>
    page.evaluate(() => {
      const cards = [...document.querySelectorAll('.library-image-tile')];
      if (!cards.length) return { none: true };
      const topRow = Math.round(cards[0].getBoundingClientRect().top);
      const row = cards.filter((c) => Math.abs(c.getBoundingClientRect().top - topRow) < 4);
      const parent = cards[0].parentElement;
      return {
        n: row.length,
        heights: row.map((c) => Math.round(c.getBoundingClientRect().height * 10) / 10),
        pics: row.map((c) => {
          const i = c.querySelector('img');
          return i ? Math.round(i.getBoundingClientRect().height * 10) / 10 : 0;
        }),
        slack: row.map((c) => {
          const box = c.getBoundingClientRect();
          const kids = [...c.querySelectorAll('*')].filter((e) => e.getBoundingClientRect().height > 0);
          const last = Math.max(...kids.map((e) => e.getBoundingClientRect().bottom));
          return Math.round((box.bottom - last) * 10) / 10;
        }),
        // How many of the cards on screen carry a disclosure at all, which is
        // the Images ratchet and the Files precondition in one number.
        folds: cards.filter((c) => c.querySelector('details.library-image-reading')).length,
        align: getComputedStyle(parent).alignItems + ' / ' + getComputedStyle(parent).display,
      };
    });

  await subtab('image');
  const images = await read();
  console.log('images    ' + JSON.stringify(images));
  if (images.none) fail.push('Images sub-tab: no .library-image-tile on screen, nothing measured');
  else {
    // INBOX 279: the reading left the card, so there is nothing on a picture
    // card to open and nothing that can resize its row-mates.
    if (images.folds) fail.push(`Images sub-tab: ${images.folds} picture card${images.folds === 1 ? '' : 's'} carry a reading fold at rest (INBOX 279 put the reading behind a .library-chip)`);
    const spread = Math.max(...images.heights) - Math.min(...images.heights);
    console.log(`images    row spread ${spread.toFixed(1)}px`);
    if (spread > 1) fail.push(`Images sub-tab: cards in one row differ by ${spread.toFixed(1)}px`);
  }

  await subtab('file');
  const filesShut = await read();
  console.log('files shut ' + JSON.stringify(filesShut));
  if (filesShut.none) fail.push('Files sub-tab: no rows on screen, nothing measured');
  else if (!filesShut.folds) fail.push('Files sub-tab: no reading fold on any row, nothing to open');
  else {
    const opened = await page.evaluate(() => {
      const f = document.querySelector('.library-image-tile details.library-image-reading');
      if (!f) return null;
      f.open = true;
      const tile = f.closest('.library-image-tile');
      return [...document.querySelectorAll('.library-image-tile')].indexOf(tile);
    });
    await page.waitForTimeout(700);
    const filesOpen = await read();
    console.log('files open ' + JSON.stringify(filesOpen));
    console.log('files opened card ' + opened);
    // The number this probe has always been about: what an open fold does to
    // the cards that did not open. A row-mate that grows or shrinks is the
    // hole the picture cards were rescued from.
    const moved = filesShut.heights
      .map((h, i) => (i === opened ? 0 : Math.abs((filesOpen.heights[i] ?? h) - h)))
      .filter((d) => d > 1);
    console.log(`files      row-mates moved: ${moved.length} of ${Math.max(filesShut.n - 1, 0)}`);
    if (moved.length) {
      fail.push(`Files sub-tab: opening one row's reading moved ${moved.length} row-mates by up to ${Math.max(...moved).toFixed(1)}px`);
    }
  }

  for (const line of fail) console.log('FAIL: ' + line);
  console.log(fail.length ? `imagefold: ${fail.length} finding(s)` : 'imagefold: pass');
  await browser.close();
  process.exitCode = fail.length ? 1 : 0;
})();
