// A picture on a board survives the board's PNG export (OPEN.md, world-class
// rows 1, 2 and 9: "whiteboard PNG/PDF export rasterises an SVG through <img>,
// which never loads external <image href>s, so pictures on a board are likely
// missing from the export"). Read, not reproduced, until this: puts a solid
// red picture on the board, builds the export SVG, rasterises it the way the
// PNG button does (`wbRasterizeSvg`) and reads the pixel where the picture is.
//
//   BASE=http://127.0.0.1:8799 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node wbexportimage.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  let failed = 0;
  const ok = (name, pass, detail) => { if (!pass) failed++; console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}  ${detail || ''}`); };
  // Through the real UI: `openWhiteboardBoard` from script leaves the boards
  // landing showing (see whiteboard.js, `newBoard`).
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(500);
  await page.click('[data-target="library-view-whiteboard"]');
  await page.waitForTimeout(700);
  await page.evaluate(() => document.getElementById('wb-boards-new-template').click());
  await page.waitForTimeout(700);
  await page.fill('#wb-template-name', 'Export picture');
  await page.click('#wb-template-create');
  await page.waitForTimeout(2500);
  await page.keyboard.press('Escape');
  const made = await page.evaluate(async () => {
    const cv = document.createElement('canvas'); cv.width = cv.height = 32;
    const cx = cv.getContext('2d'); cx.fillStyle = '#ff0000'; cx.fillRect(0, 0, 32, 32);
    const blob = await new Promise((r) => cv.toBlob(r, 'image/png'));
    const fd = new FormData();
    fd.append('file', new File([blob], 'export-red.png', { type: 'image/png' }));
    fd.append('direct', 'true');
    const up = await (await fetch('/media/upload', { method: 'POST', body: fd,
      headers: { 'X-Auth-Token': authToken(), 'X-Workspace-ID': activeSpaceId() } })).json();
    const res = await api('/whiteboard/objects', { method: 'POST', body: JSON.stringify({
      kind: 'image', board_id: window.currentBoardId, x: 100, y: 100, width: 200, height: 200, data: { url: up.url } }) });
    await fetchWhiteboardState();
    return { url: up.url, status: res.status };
  });
  ok('a picture is on the board', made.status < 300 && !!made.url, JSON.stringify(made));
  const read = await page.evaluate(async () => {
    const { svg, width, height } = wbBuildExportSvg('board');
    const hasImage = /<image /.test(svg);
    const hrefIsData = /<image href="data:/.test(svg);
    const blob = await wbRasterizeSvg(svg, width, height, 'image/png');
    const bmp = await createImageBitmap(blob);
    const cv = document.createElement('canvas'); cv.width = bmp.width; cv.height = bmp.height;
    const cx = cv.getContext('2d'); cx.drawImage(bmp, 0, 0);
    // The board's bounds start at the picture's corner (it is the only object
    // near the origin), so the middle of the export is the middle of the picture.
    const px = cx.getImageData(Math.floor(bmp.width / 2), Math.floor(bmp.height / 2), 1, 1).data;
    return { hasImage, hrefIsData, size: [bmp.width, bmp.height], px: [px[0], px[1], px[2]] };
  });
  ok('the export SVG carries the picture', read.hasImage, JSON.stringify({ data: read.hrefIsData }));
  ok('the rasterised PNG shows the picture, not the board behind it', read.px[0] > 200 && read.px[1] < 60 && read.px[2] < 60,
    `pixel at the middle of ${read.size.join('x')}: rgb(${read.px.join(', ')})`);
  console.log(failed ? `${failed} failed` : 'all passed');
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
