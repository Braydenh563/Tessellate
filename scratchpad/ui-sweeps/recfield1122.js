// The recorder's "What is this recording?" field: with the field focused, the gap between the label's
// bottom and the focus ring's top edge (the owner, 2026-11-22). Compared with a Settings text field.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: +(process.env.W || 1440), height: 900 } });
  await page.evaluate(() => openMeetingRecorder());
  await page.waitForSelector('#meeting-title', { state: 'visible', timeout: 15000 });
  await page.focus('#meeting-title');
  await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Tab'); // keyboard focus, so :focus-visible draws
  const m = await page.evaluate(() => {
    const label = document.querySelector('.meeting-title-label').getBoundingClientRect();
    const input = document.getElementById('meeting-title');
    const cs = getComputedStyle(input);
    const ring = (parseFloat(cs.outlineWidth) || 0) + (parseFloat(cs.outlineOffset) || 0);
    const shadow = cs.boxShadow;
    const box = input.getBoundingClientRect();
    return { focused: document.activeElement === input, labelBottom: +label.bottom.toFixed(1), inputTop: +box.top.toFixed(1),
      outline: `${cs.outlineStyle} ${cs.outlineWidth} offset ${cs.outlineOffset}`, shadow: shadow.slice(0, 80),
      gapToBox: +(box.top - label.bottom).toFixed(1), gapToRing: +(box.top - ring - label.bottom).toFixed(1) };
  });
  console.log(JSON.stringify(m));
  await browser.close();
})();
