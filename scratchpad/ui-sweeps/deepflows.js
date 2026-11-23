// Interaction bug sweep, deeper than smoke.js: real flows through the UI at a
// desktop and a phone width, in light and dark, and a failure on anything that
// should never happen while a person uses the app.
//
//   BASE=http://127.0.0.1:8801 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/deepflows.js            # every flow, 4 runs
//   ... ONLY=note,graph WIDTHS=1440 THEMES=light node scratchpad/ui-sweeps/deepflows.js
//   ... SKIP=settings node scratchpad/ui-sweeps/deepflows.js   # settings is the slow one
//
// Seed the data dir first: `node scratchpad/ui-sweeps/deepflows-seed.js`
// (about 40 notes, four private, properties, [[links]] and [[A|B]], tags, two
// documents, a board, a mind map, reminders). The flows are in
// deepflows-flows.js, one function each:
//   note        create, edit, move to the bin, Undo, restore from the Library bin
//   private     Make private (the confirm), the chip, Make readable, text intact
//   link        Link to another on two notes; an aliased [[A|B]] draws "B"
//   graph       click a node (popup) and a link (peek) through the canvas hit-test
//   mindmap     open a map, select a topic, add a child, the count goes up
//   whiteboard  Insert > Sticky note, click the canvas, type, it is stored
//   document    type, add a `---` block, set the property in the panel, it saves
//   ask         no model: the graceful answer and the way to connect one
//   notifications  the bell, remove one, mark one read, close
//   settings    press every switch (by its row), reload, read back, put back
//   palette     open, find a note, run a command, open a note, Escape
//   tabs        every tab by its button (the phone bar and its More sheet)
//   dashboard   every widget draws, no properties block printed as words
//   picker      the [[ picker in Capture lists the note being named first
//   select      Select mode: tick two notes (a tap does not open a page), batch Tags
//   views       every Library view, the Create sheet, Timeline and Reminders modes
//   find        Find anything (the status bar, or the top bar's More on a phone)
// A phone has no way to open the command palette (Find is the search), so the
// palette flow opens it by its function at 390: reported, not fixed.
//
// What fails a flow, besides the flow's own assertions:
//   - a `pageerror` or a `console.error` while it ran;
//   - a request that answered 4xx/5xx or never finished, unless the flow said
//     it expected that status (`expect(status, urlPart)`);
//   - the page scrolling sideways, or a visible element that sticks out past
//     the viewport edge and is not inside something that scrolls or clips it.
// A failed flow keeps a screenshot in $SCRATCH/shots/deepflows-*.png.
//
// Each width x theme gets its own browser context, so the flows share a
// signed-in notebook and a flow that leaves a mess (an open sheet, a form)
// must clean up: `reset()` runs between flows and closes everything.
// Exit code is the number of failures.
const fs = require('fs');
const { boot, OUT } = require('./lib.js');

const WIDTHS = (process.env.WIDTHS || '1440,390').split(',').map(Number);
const THEMES = (process.env.THEMES || 'light,dark').split(',');
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
const SKIP = (process.env.SKIP || '').split(',').filter(Boolean);
const STAMP = `df${Date.now() % 1000000}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

//: The in-page overflow probe. Serialised into the page, so it carries no
//: closure. Returns a list of strings, empty when the screen is whole.
function overflowProbe() {
  const vw = document.documentElement.clientWidth;
  const out = [];
  const se = document.scrollingElement;
  if (se.scrollWidth > vw + 1) out.push(`page scrolls sideways: scrollWidth ${se.scrollWidth} > ${vw}`);
  const describe = (el) => {
    const id = el.id ? `#${el.id}` : '';
    const cls = typeof el.className === 'string' && el.className ? `.${el.className.trim().split(/\s+/).slice(0, 2).join('.')}` : '';
    const label = (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return `${el.tagName.toLowerCase()}${id}${cls} "${label}"`;
  };
  let reported = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (reported >= 6) break;
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right <= vw + 1 && r.left >= -1) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
    if (cs.position === 'absolute' && cs.clip && cs.clip !== 'auto') continue; // visually-hidden text
    //: Anything the app itself has put away: hidden, inert, aria-hidden, or an
    //: ancestor that is display:none / not rendered.
    if (el.closest('.hidden, [hidden], [inert], [aria-hidden="true"]')) continue;
    let clipped = false;
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const pc = getComputedStyle(p);
      if (pc.visibility === 'hidden' || pc.display === 'none' || Number(pc.opacity) === 0) { clipped = true; break; }
      if (/(auto|scroll|hidden|clip)/.test(pc.overflowX)) {
        const pr = p.getBoundingClientRect();
        if (pr.right <= vw + 1 && pr.left >= -1) { clipped = true; break; }
      }
    }
    if (clipped) continue;
    out.push(`${describe(el)} spans ${Math.round(r.left)}..${Math.round(r.right)} of ${vw}`);
    reported++;
  }
  return out;
}

async function main() {
  const flows = require('./deepflows-flows.js');
  const names = Object.keys(flows).filter((n) => (!ONLY.length || ONLY.includes(n)) && !SKIP.includes(n));
  const table = [];
  let failures = 0;
  const findings = new Map(); // message -> [where]

  for (const width of WIDTHS) {
    for (const theme of THEMES) {
      process.env.THEME = theme;
      const phone = width < 700;
      const { browser, ctx, page } = await boot({
        viewport: { width, height: phone ? 844 : 900 },
        ...(phone ? { hasTouch: true, isMobile: true } : {}),
      });
      page.setDefaultTimeout(8000);
      let current = '(boot)';
      let stepAt = '';
      let bag = [];
      let expected = [];
      const note = (msg) => bag.push(msg);
      page.on('pageerror', (e) => note(`pageerror: ${e.message.slice(0, 200)}`));
      page.on('console', (m) => {
        if (m.type() !== 'error') return;
        const t = m.text().slice(0, 200);
        //: The browser's own line for a failed load repeats what `response`
        //: reports with the URL, so it is judged there, once.
        if (/^Failed to load resource/.test(t)) return;
        note(`console: ${t}`);
      });
      page.on('response', (r) => {
        const s = r.status();
        if (s < 400) return;
        const url = r.url().replace(/^https?:\/\/[^/]+/, '');
        if (expected.some((e) => e.status === s && url.includes(e.part))) return;
        note(`${s} ${r.request().method()} ${url.slice(0, 120)}`);
      });
      page.on('requestfailed', (r) => {
        const url = r.url().replace(/^https?:\/\/[^/]+/, '');
        //: Cancelled by navigation or by the app aborting its own fetch is not
        //: a failure; a real network error is.
        if (/ERR_ABORTED|NS_BINDING_ABORTED/.test(r.failure()?.errorText || '')) return;
        note(`request failed: ${r.method()} ${url.slice(0, 120)} ${r.failure()?.errorText}`);
      });
      const env = {
        page, ctx, width, theme, phone, STAMP, sleep,
        at: (label) => { stepAt = label; },
        info: (msg) => console.log(`       . ${msg}`),
        report: (msg) => note(msg),
        expect: (status, part) => expected.push({ status, part }),
        overflow: async (label) => {
          const o = await page.evaluate(overflowProbe);
          for (const line of o) note(`overflow${label ? ` (${label})` : ''}: ${line}`);
        },
        js: (fn, arg) => page.evaluate(fn, arg),
        wait: (ms) => page.waitForTimeout(ms),
        reset: async () => {
          //: Back to a known place between flows: everything closed, Notes
          //: tab, the notes list in its default state.
          await page.keyboard.press('Escape').catch(() => {});
          await page.evaluate(async () => {
            for (const el of document.querySelectorAll('.sheet-overlay .sheet-close, dialog[open] .close, .modal:not(.hidden) .modal-close')) el.click();
            document.getElementById('settings-modal')?.classList.add('hidden');
            if (typeof switchTab === 'function') switchTab('notes');
          }).catch(() => {});
          await page.waitForTimeout(400);
        },
      };
      for (const name of names) {
        current = name;
        bag = [];
        expected = [];
        stepAt = '';
        const where = `${name} @${width} ${theme}`;
        let problem = null;
        try {
          await flows[name](env);
          await env.overflow('end');
        } catch (e) {
          problem = `${stepAt ? `[${stepAt}] ` : ''}${String(e.message || e).split('\n').slice(0, process.env.DF_FULL ? 12 : 1).join(' | ').slice(0, process.env.DF_FULL ? 1500 : 240)}`;
        }
        const errs = [...new Set(bag)];
        const failed = Boolean(problem) || errs.length > 0;
        if (failed) {
          failures++;
          try { await page.screenshot({ path: `${OUT}/deepflows-${name}-${width}-${theme}.png` }); } catch (e) { /* page gone */ }
        }
        table.push({ where, ok: !failed });
        console.log(`${failed ? 'FAIL' : 'PASS'} ${where}${problem ? `  -> ${problem}` : ''}`);
        for (const e of errs) {
          console.log(`       ${e}`);
          if (!findings.has(e)) findings.set(e, []);
          findings.get(e).push(where);
        }
        await env.reset();
      }
      //: Nothing the flows made is left in the notebook: purge by the stamp
      //: (a flow that died half way never reached its own clean-up).
      try {
        await page.evaluate(async (stamp) => {
          const body = await apiJson('/entries?limit=500');
          for (const e of (Array.isArray(body) ? body : body.entries || [])) {
            if (e.content.includes(stamp)) { await api(`/entries/${e.id}`, { method: 'DELETE' }); await api(`/entries/${e.id}/purge`, { method: 'DELETE' }); }
          }
        }, STAMP);
      } catch (e) { /* page gone */ }
      await browser.close();
    }
  }
  const pass = table.filter((t) => t.ok).length;
  console.log(`\n${pass}/${table.length} flow runs passed (${names.length} flows x ${WIDTHS.length} widths x ${THEMES.length} themes); ${failures} failed`);
  if (findings.size) {
    console.log('\nDistinct page-level findings:');
    for (const [msg, where] of findings) console.log(`  ${msg}\n      in: ${where.slice(0, 4).join('; ')}${where.length > 4 ? ` (+${where.length - 4})` : ''}`);
  }
  process.exit(failures);
}
main().catch((e) => { console.error(e); process.exit(99); });
