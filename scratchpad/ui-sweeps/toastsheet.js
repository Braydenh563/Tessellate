// A toast fired while a phone sheet is open must be the thing at its own
// centre (GRAPH_PLAN, "After KG1 to KG9"). Opens `openSheet` from
// openers at several layers, fires a toast, and asks `elementFromPoint` at the
// toast's centre who answers. Exit code 1 when any case is covered.
//
//   BASE=http://127.0.0.1:8798 node scratchpad/ui-sweeps/toastsheet.js
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({
    viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true,
  });
  const results = [];
  for (const layer of [0, 1010, 1020, 1045, 1050, 2000, 2550, 2600]) {
    const r = await page.evaluate(async (layer) => {
      document.querySelectorAll('.sheet-overlay').forEach((s) => s.remove());
      document.querySelectorAll('#toast-box > .toast').forEach((t) => t.remove());
      let opener = null;
      if (layer) {
        opener = document.createElement('button');
        opener.textContent = 'opener';
        opener.style.position = 'fixed';
        opener.style.zIndex = String(layer);
        opener.style.top = '0';
        document.body.appendChild(opener);
      }
      const close = openSheet({
        label: 'Probe', name: 'probe', returnFocus: opener || undefined,
        build(card) {
          card.append(sheetRow('ph ph-star', 'First row', () => {}));
          card.append(sheetRow('ph ph-star', 'Second row', () => {}));
        },
      });
      toast('Probe toast ' + layer, false, { exempt: true });
      await new Promise((res) => setTimeout(res, 400));
      const t = [...document.querySelectorAll('.toast')].pop();
      const b = t.getBoundingClientRect();
      const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
      const hit = document.elementFromPoint(cx, cy);
      const sheet = document.querySelector('.sheet-overlay');
      const out = {
        layer, toast: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)],
        answered: !!hit && !!hit.closest('.toast'),
        hit: hit ? (hit.className || hit.tagName) : null,
        sheetZ: getComputedStyle(sheet).zIndex, boxZ: getComputedStyle(document.getElementById('toast-box')).zIndex,
      };
      close();
      opener?.remove();
      t.remove();
      return out;
    }, layer);
    results.push(r);
    console.log(JSON.stringify(r));
  }
  await browser.close();
  const bad = results.filter((r) => !r.answered);
  console.log(bad.length ? `COVERED in ${bad.length} case(s)` : 'ok: the toast answers its own centre in every case');
  process.exit(bad.length ? 1 : 0);
})();
