// L636: the surfaces no sweep covered together, asserted as numbers. Each check
// prints PASS or FAIL with the measured values; exit 1 on any FAIL.
//   open a board and a map (the canvas has a real box and its cards render),
//   the graph popup at 390 (inside the window, dock above the status bar),
//   the lightbox (inside the window, controls >= 24px, Escape closes),
//   the confirm dialog (inside the window, buttons >= 24px, text ink >= 4.5:1,
//   Escape answers false), every theme look (body ink >= 4.5:1 on its ground),
//   forced colours (a selected tab keeps an outline, a button a border, the
//   confirm card an edge), and the print stylesheet through
//   page.emulateMedia('print') (the print dialog cannot be automated).
//
//   BASE=http://127.0.0.1:8799 [THEME=dark] node scratchpad/ui-sweeps/coverage636.js
const { boot } = require('./lib.js');
const L = require('./trustlib.js');
const { openBoardsTab, waitForBoardOpen } = require('./lib.js');

let fails = 0;
const check = (name, ok, nums) => { if (!ok) fails++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}  ${JSON.stringify(nums)}`); };

// Contrast helpers, shared with every page.evaluate below as a source string.
const CONTRAST = `
// Any CSS colour (rgb, color(srgb ...), color-mix results) through a canvas, so the parser never guesses.
const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', { willReadFrequently: true });
const rgba = (c) => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 }; };
const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const over = (top, under) => ({ r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1 });
// The page paints its ground from the --bg gradient (no element has a background colour), so the
// gradient's middle stop is the ground a transparent chain ends on.
const pageGround = () => { const v = getComputedStyle(document.documentElement).getPropertyValue('--bg'); const hex = (v.match(/#[0-9a-f]{6}/gi) || [])[1] || (v.match(/#[0-9a-f]{6}/i) || [])[0]; if (!hex) return { r: 255, g: 255, b: 255, a: 1 }; return { r: parseInt(hex.slice(1, 3), 16), g: parseInt(hex.slice(3, 5), 16), b: parseInt(hex.slice(5, 7), 16), a: 1 }; };
const ground = (el) => { const layers = []; for (let n = el; n; n = n.parentElement) layers.push(rgba(getComputedStyle(n).backgroundColor)); let acc = pageGround(); for (const l of layers.reverse()) acc = over(l, acc); return acc; };
const ratio = (el) => { const bg = ground(el); const fg = over(rgba(getComputedStyle(el).color), bg); const a = lum(fg) + 0.05, b = lum(bg) + 0.05; return Math.max(a, b) / Math.min(a, b); };
`;
const inView = (r, w, h) => r.left >= -1 && r.top >= -1 && r.right <= w + 1 && r.bottom <= h + 1;

const PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mP8z8BQz0AEYBxVSF+FABJADveWkH6oAAAAAElFTkSuQmCC';

async function desktopAndPhone() {
  // ---- desktop context: boards, maps, confirm, lightbox, looks, print
  const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
  await L.ensureSeed(page);
  const ids = await L.boardIds(page);
  for (const [name, id] of [['board', ids.board], ['map', ids.map]]) {
    await openBoardsTab(page).catch(() => {});
    await page.evaluate((i) => openWhiteboardBoard(i), id);
    await waitForBoardOpen(page, 0).catch(() => {});
    await page.waitForTimeout(900);
    const m = await page.evaluate(() => {
      const c = document.getElementById('whiteboard-container');
      const r = c ? c.getBoundingClientRect() : { width: 0, height: 0 };
      return { w: Math.round(r.width), h: Math.round(r.height), cards: document.querySelectorAll('#whiteboard-container .wb-card').length };
    });
    check(`open ${name}: canvas has a box and cards render`, m.w > 300 && m.h > 200 && m.cards >= 1, m);
  }
  await page.evaluate(() => switchTab('dashboard'));
  await page.waitForTimeout(600);

  // ---- confirm dialog
  const pending = page.evaluate(() => { window.__c = undefined; confirmDialog('Delete this note?\n\nThis cannot be undone.').then((v) => { window.__c = v; }); });
  await page.waitForSelector('.confirm-card', { timeout: 5000 });
  await pending;
  const cm = await page.evaluate(`(() => { ${CONTRAST}
    const card = document.querySelector('.confirm-card'); const r = card.getBoundingClientRect();
    const btns = [...card.querySelectorAll('button')].map((b) => { const q = b.getBoundingClientRect(); return [Math.round(q.width), Math.round(q.height)]; });
    const t = card.querySelector('.confirm-text span, .confirm-text'); const bd = getComputedStyle(card);
    return { r: { left: r.left, top: r.top, right: r.right, bottom: r.bottom }, btns, ink: +ratio(t).toFixed(2), focusIn: card.contains(document.activeElement), border: bd.borderTopWidth + ' ' + bd.borderTopStyle };
  })()`);
  check('confirm: inside the window', inView(cm.r, 1280, 800), cm.r);
  check('confirm: buttons at least 24px', cm.btns.length >= 2 && cm.btns.every(([w, h]) => w >= 24 && h >= 24), cm.btns);
  check('confirm: text ink at least 4.5:1', cm.ink >= 4.5, { ink: cm.ink });
  check('confirm: focus is inside the card', cm.focusIn, {});
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('.confirm-card'), null, { timeout: 4000 }).catch(() => {});
  const after = await page.evaluate(() => ({ open: !!document.querySelector('.confirm-card'), answer: String(window.__c) }));
  // Leaving is not a "no": Escape answers undefined (app.js, X12).
  check('confirm: Escape closes it and answers undefined, not false', !after.open && after.answer === 'undefined', after);

  // ---- lightbox
  await page.evaluate((src) => openLightbox([{ filename: 'probe.png', getUrl: () => src }], 0), PNG);
  await page.waitForSelector('.lightbox', { timeout: 5000 });
  await page.waitForTimeout(500);
  const lb = await page.evaluate(() => {
    const e = document.querySelector('.lightbox'); const r = e.getBoundingClientRect();
    const small = [...e.querySelectorAll('button')].filter((b) => { const q = b.getBoundingClientRect(); return q.width > 0 && (q.width < 24 || q.height < 24); }).length;
    return { r: { left: r.left, top: r.top, right: r.right, bottom: r.bottom }, buttons: e.querySelectorAll('button').length, small, scrolls: e.scrollHeight > e.clientHeight + 1 };
  });
  check('lightbox: fills the window', inView(lb.r, 1280, 800) && lb.r.right - lb.r.left >= 1270, lb.r);
  check('lightbox: every visible control at least 24px', lb.buttons >= 1 && lb.small === 0, { buttons: lb.buttons, small: lb.small });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  check('lightbox: Escape closes it', (await page.$('.lightbox')) === null, {});

  // ---- every theme look: body ink on its ground
  // Colours transition on a look change: read after they settle, or the numbers are a blend of two looks.
  const looks = await page.evaluate(`(async () => { ${CONTRAST}
    const out = []; const keep = activeThemePreset();
    for (const name of Object.keys(THEME_PRESETS)) {
      applyThemePreset(name, false);
      await new Promise((r) => setTimeout(r, 900));
      const els = [document.body, document.querySelector('#tab-bar button:not(.active)') || document.body, [...document.querySelectorAll('.card')].find((c) => c.getBoundingClientRect().width > 100 && c.textContent.trim()) || document.body];
      out.push({ name, ink: els.map((e) => +ratio(e).toFixed(2)) });
    }
    applyThemePreset(keep, false);
    return out;
  })()`);
  const bad = looks.filter((l) => l.ink.some((v) => v < 4.5));
  check(`looks: ${looks.length} presets, body, tab and card ink at least 4.5:1`, looks.length > 3 && bad.length === 0, bad.length ? bad : { presets: looks.length, lowest: Math.min(...looks.flatMap((l) => l.ink)) });

  // ---- print stylesheet through emulation (the dialog itself cannot be driven)
  await openBoardsTab(page).catch(() => {});
  await page.evaluate(() => switchTab('library'));
  await page.waitForTimeout(500);
  await page.click('#library-subtabs [data-target="library-view-docs"]', { timeout: 4000 }).catch(() => {});
  await page.click('.doc-list-item', { timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(1200);
  await page.evaluate(() => { document.body.classList.add('printing-doc'); const p = document.getElementById('doc-preview'); if (p) p.classList.remove('hidden'); });
  await page.emulateMedia({ media: 'print' });
  await page.waitForTimeout(400);
  const pr = await page.evaluate(() => {
    const d = (s) => { const e = document.querySelector(s); return e ? getComputedStyle(e).display : 'absent'; };
    const pv = document.getElementById('doc-preview');
    return { tabBar: d('#tab-bar'), sidebar: d('.doc-sidebar'), toolbar: d('.doc-toolbar'), dock: d('.doc-dock'), page: d('#tab-documents'), previewInk: pv ? getComputedStyle(pv).color : 'absent', overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth };
  });
  check('print: chrome hidden, the document page kept', pr.tabBar === 'none' && pr.sidebar === 'none' && pr.toolbar === 'none' && pr.dock === 'none' && pr.page !== 'none', pr);
  check('print: preview ink is black and nothing runs off the page', pr.previewInk === 'rgb(0, 0, 0)' && pr.overflowX <= 1, { ink: pr.previewInk, overflowX: pr.overflowX });
  await page.emulateMedia({ media: 'screen' });
  await page.evaluate(() => document.body.classList.remove('printing-doc'));
  await browser.close();
}

async function phone() {
  const { browser, page } = await boot({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const id = await page.evaluate(async () => {
    const body = Array.from({ length: 30 }, (_, i) => `Line ${i + 1} of a long note about the schedule.`).join('\n');
    const e = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: 'Popup probe\n' + body, tags: ['schedule'] }) }).catch(() => ({}));
    return e.id;
  });
  await page.evaluate(() => switchTab('graph'));
  await page.waitForTimeout(3500);
  const box = await page.evaluate(() => { const b = document.getElementById('graph-box').getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; });
  await page.evaluate(async ([i, x, y]) => { await openGraphPopup({ stopPropagation() {}, clientX: x, clientY: y }, { id: i, preview: 'Popup probe' }); }, [id, box[0] + box[2] * 0.5, box[1] + box[3] - 30]);
  await page.waitForTimeout(1200);
  const g = await page.evaluate(() => {
    const pop = document.getElementById('graph-popup'); if (!pop) return null;
    const sb = document.getElementById('status-bar'); const sbr = sb && getComputedStyle(sb).display !== 'none' ? sb.getBoundingClientRect() : null;
    const dock = pop.querySelector('.graph-popup-actions') || pop.lastElementChild; const r = pop.getBoundingClientRect(), d = dock.getBoundingClientRect();
    return { left: Math.round(r.left), right: Math.round(r.right), dockBottom: Math.round(d.bottom), limit: Math.round(sbr && sbr.height ? sbr.top : innerHeight), w: innerWidth };
  });
  check('graph popup at 390: inside the width, dock above the status bar', !!g && g.left >= 0 && g.right <= g.w + 1 && g.dockBottom <= g.limit + 1, g);
  await page.keyboard.press('Escape');

  // lightbox and confirm at 390
  await page.evaluate((src) => openLightbox([{ filename: 'probe.png', getUrl: () => src }], 0), PNG);
  await page.waitForSelector('.lightbox', { timeout: 5000 });
  await page.waitForTimeout(500);
  const lb = await page.evaluate(() => { const r = document.querySelector('.lightbox').getBoundingClientRect(); const small = [...document.querySelectorAll('.lightbox button')].filter((b) => { const q = b.getBoundingClientRect(); return q.width > 0 && (q.width < 24 || q.height < 24); }).length; return { l: r.left, r: r.right, t: r.top, b: r.bottom, small }; });
  check('lightbox at 390: inside the window, controls at least 24px', lb.l >= -1 && lb.r <= 391 && lb.b <= 845 && lb.small === 0, lb);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  page.evaluate(() => { confirmDialog('Delete this note?\n\nThis cannot be undone.'); });
  await page.waitForSelector('.confirm-card', { timeout: 5000 });
  const cm = await page.evaluate(() => { const r = document.querySelector('.confirm-card').getBoundingClientRect(); const btn = [...document.querySelectorAll('.confirm-card button')].map((b) => Math.round(b.getBoundingClientRect().height)); return { l: Math.round(r.left), r: Math.round(r.right), b: Math.round(r.bottom), btn }; });
  check('confirm at 390: inside the window, buttons at least 24px', cm.l >= 0 && cm.r <= 390 && cm.b <= 844 && cm.btn.every((h) => h >= 24), cm);
  await browser.close();
}

async function forced() {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 800 }, forcedColors: 'active' });
  await page.waitForTimeout(1500);
  const m = await page.evaluate(() => {
    const tab = document.querySelector('#tab-bar [aria-selected="true"], #tab-bar .active');
    const btn = document.querySelector('button.small, button.accent');
    const t = tab && getComputedStyle(tab), b = btn && getComputedStyle(btn);
    return { forced: matchMedia('(forced-colors: active)').matches, tabOutline: t ? t.outlineWidth + ' ' + t.outlineStyle : 'no tab', btnBorder: b ? b.borderTopWidth + ' ' + b.borderTopStyle : 'no button' };
  });
  check('forced colours: matches, a selected tab is outlined, a filled button has a border', m.forced && /^[2-9]px solid/.test(m.tabOutline) && /^[1-9]\d*px (solid|outset|inset|groove|ridge)/.test(m.btnBorder), m);
  page.evaluate(() => { confirmDialog('Delete this note?\n\nThis cannot be undone.'); });
  await page.waitForSelector('.confirm-card', { timeout: 5000 });
  const c = await page.evaluate(() => { const s = getComputedStyle(document.querySelector('.confirm-card')); const p = [...document.querySelectorAll('.confirm-card button')].map((b) => { const q = getComputedStyle(b); return parseFloat(q.borderTopWidth) > 0 || (parseFloat(q.outlineWidth) > 0 && q.outlineStyle !== 'none'); }); return { edge: s.borderTopWidth + ' ' + s.borderTopStyle, buttonsEdged: p }; });
  check('forced colours: the confirm card has an edge and each button too', parseFloat(c.edge) >= 1 && !/none/.test(c.edge) && c.buttonsEdged.every(Boolean), c);
  await browser.close();
}

(async () => {
  console.log(`coverage636 (${process.env.THEME || 'light'})`);
  await desktopAndPhone();
  await phone();
  await forced();
  console.log(fails ? `FAILED ${fails}` : 'ALL PASS');
  process.exit(fails ? 1 : 0);
})();
