// How much of a phone is chrome, tab by tab (INBOX 392, UI_MODERNISATION_PLAN
// Phase 11 item 12). The owner: "the mobile view is still very broken, takes
// up a lot of the screen".
//
//   BASE=http://127.0.0.1:8794 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     timeout 110 node scratchpad/ui-sweeps/phonechrome.js
//
// Seed first (seed.js, seed-boards.js): an empty list measures an empty
// state, and a board is opened by the id `BOARD` (default: the newest).
//
// **Chrome, defined so it can be counted.** Everything that does not scroll
// with the tab's content: the shell's bars (the header, the status bar, the
// tab bar), anything `fixed`, anything `sticky`, and any band that sits
// outside the content's own scroller (a chat composer, a board's top bar).
// It is the union of their vertical extents inside the window, so two bars
// that overlap are not counted twice. A band is at least half the window
// wide, which leaves out the floating + (a button, not a bar) and a toast.
//
// Per tab it gates on four things, each the brief's:
//   1. chrome at most 25% of the window height;
//   2. no sideways scroll (the page, and any box wider than itself with no
//      scroller of its own);
//   3. nothing clipped: a control whose text is wider than its box;
//   4. no control under 44px (touch.js's exclusions, copied).
//   5. the content begins in the top 40% at rest (a dock that scrolls away
//      is not chrome, but it is what the first screen shows);
//   6. a list row at rest draws nothing of its own over its text.
// `WIDTH=768 HEIGHT=1024` and `WIDTH=1024 HEIGHT=768` run the same gate on a
// tablet.
const { boot, openBoardsTab, waitForBoardOpen } = require('./lib.js');

const W = Number(process.env.WIDTH || 390);
const H = Number(process.env.HEIGHT || 844);
const MAX_CHROME = 0.25;
// Where the thing a person came to the tab for begins, at rest. A dock that
// scrolls away is not chrome, but a list first shown at y=836 in 844 (the
// reminders tab, measured) is a first screen of nothing but controls.
const MAX_CONTENT_TOP = 0.4;
const MIN = 44;

// The content of each tab: the thing chrome is measured against.
const TABS = [
  ['dashboard', '#dash-hero'],
  ['notes', '#entry-list'],
  ['chat', '.chat-transcript'],
  ['library', '#library-grid'],
  ['timeline', '#timeline-scroll'],
  ['reminders', '#reminder-groups'],
  ['board', '#whiteboard-container'],
];

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: H }, hasTouch: true, isMobile: true });
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 140)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 140)); });
  let failures = 0;
  console.log(`--- ${W}x${H}, hasTouch + isMobile; chrome budget ${Math.round(H * MAX_CHROME)}px`);

  for (const [tab, contentSel] of TABS) {
    if (tab === 'board') {
      await openBoardsTab(page);
      const id = Number(process.env.BOARD || 0) || await page.evaluate(async () => {
        const r = await (await api('/whiteboard/boards')).json();
        const list = Array.isArray(r) ? r : (r.boards || []);
        const b = list.find((x) => (x.board_type || x.type || 'board') === 'board') || list[0];
        return b ? b.id : 0;
      }).catch(() => 0);
      await page.evaluate((i) => openWhiteboardBoard(i), id).catch((e) => errs.push('open board: ' + e.message.slice(0, 80)));
      await waitForBoardOpen(page).catch((e) => errs.push('board not on screen: ' + e.message.slice(0, 80)));
      // A fresh text box in its editing state: it read 203>198 here once (its
      // grips, not its content: see `drawnPast`), and nothing else puts one
      // on the board, so the check below would never see it.
      await page.evaluate(() => wbCreateTextBox(120, 200)).catch((e) => errs.push('text box: ' + e.message.slice(0, 80)));
      await page.waitForTimeout(500);
    } else {
      await page.evaluate((t) => switchTab(t), tab);
      await page.waitForTimeout(1500);
    }
    // Two transient things that have landed on the tab bar: a toast, raised
    // on every tab, and the agent activity panel, shown on the first.
    await page.evaluate((first) => {
      if (typeof toast === 'function') toast('Sweep probe: where a toast lands');
      if (first) document.getElementById('agent-monitor')?.classList.remove('hidden');
    }, tab === TABS[0][0]);
    await page.waitForTimeout(300);
    const r = await page.evaluate(({ sel, W, H, MIN }) => {
      const round = (n) => Math.round(n);
      const vis = (el) => el.checkVisibility
        && el.checkVisibility({ visibilityProperty: true, opacityProperty: true })
        && (() => { const b = el.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.right > 0 && b.left < W && b.bottom > 0 && b.top < H; })();
      const name = (el) => el.id ? '#' + el.id : (el.tagName.toLowerCase() + (el.classList[0] ? '.' + el.classList[0] : ''));
      const content = [...document.querySelectorAll(sel)].find(vis);
      if (!content) return { none: true };
      const scroller = (() => {
        for (let p = content.parentElement; p; p = p.parentElement) {
          const o = getComputedStyle(p).overflowY;
          // Whether it overflows today or not: an empty chat's transcript
          // still has the scroller it will scroll in.
          if (o === 'auto' || o === 'scroll') return p;
        }
        return document.documentElement;
      })();
      const pinnedInScroller = (el) => {
        for (let p = el; p && p !== scroller; p = p.parentElement) {
          const pos = getComputedStyle(p).position;
          if (pos === 'sticky' || pos === 'fixed') return true;
        }
        return false;
      };
      const bands = [];
      for (const el of document.body.querySelectorAll('*')) {
        if (content.contains(el) || el.contains(content)) continue;
        if (el.closest('.modal-overlay, .toast, .toast-container, #toast-box, #agent-monitor, .action-menu, [role="tooltip"], .ai-status-popup')) continue;
        const pos = getComputedStyle(el).position;
        const b = el.getBoundingClientRect();
        if (b.width < W * 0.5 || b.height < 16 || b.height > H * 0.6) continue;
        if (!vis(el)) continue;
        const shell = el.closest('#top-bar, #status-bar, #phone-tab-dock');
        const outside = shell || (!scroller.contains(el) && scroller !== document.documentElement);
        const pinned = pos === 'fixed' || pos === 'sticky' || outside || (scroller.contains(el) && pinnedInScroller(el));
        if (!pinned) continue;
        // Only the outermost band of a nest counts; its children are inside it.
        bands.push({ el, top: Math.max(0, b.top), bottom: Math.min(H, b.bottom) });
      }
      const outer = bands.filter((a) => !bands.some((o) => o !== a && o.el.contains(a.el)));
      const iv = outer.map((a) => [a.top, a.bottom]).sort((x, y) => x[0] - y[0]);
      let total = 0; let cur = null;
      for (const [a, b] of iv) {
        if (!cur || a > cur[1]) { if (cur) total += cur[1] - cur[0]; cur = [a, b]; } else cur[1] = Math.max(cur[1], b);
      }
      if (cur) total += cur[1] - cur[0];
      const firstItem = content.firstElementChild && vis(content.firstElementChild) ? content.firstElementChild : content;
      // Controls: touch.js's exclusions.
      const scope = [document.querySelector('.tab-page:not(.hidden)'), document.getElementById('top-bar'),
        document.getElementById('status-bar'), document.getElementById('phone-tab-dock'),
        ...document.querySelectorAll('.dock-fab')].filter(Boolean);
      const controls = [...new Set(scope.flatMap((s) => [...s.querySelectorAll('button, a[href], input:not([type="hidden"]), select, summary, [role="tab"]')]))]
        .filter(vis)
        .filter((el) => !el.closest('.modal-overlay, .action-menu, [hidden], .dock-native-hidden, .visually-hidden, .sr-only, .dock-menu-list'))
        .filter((el) => !el.classList.contains('seg'))
        .filter((el) => !(el.tagName === 'INPUT' && ['checkbox', 'radio', 'range', 'color'].includes(el.type)))
        // Scrolled out of a sideways strip is not on screen; a control only
        // partly inside the window still is, and is reported as cut below.
        .filter((el) => { const b = el.getBoundingClientRect(); return b.left < W - 1 && b.right > 1; });
      const small = controls.filter((el) => { const b = el.getBoundingClientRect(); return b.width + 0.5 < MIN || b.height + 0.5 < MIN; })
        .map((el) => { const b = el.getBoundingClientRect(); return `${name(el)} ${round(b.width)}x${round(b.height)}`; });
      //: Less a corner count hung over the edge on purpose (the Tidy broom's).
      const clipped = controls.filter((el) => el.tagName !== 'INPUT' && el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX !== 'auto'
        && ![...el.children].some((k) => k.classList.contains('tab-badge') && getComputedStyle(k).position === 'absolute'))
        .map((el) => `${name(el)} ${el.scrollWidth}>${el.clientWidth}`);
      // A control cut by an ancestor that clips without scrolling (the chat
      // composer's model picker read "Inherited: llam" this way): its box
      // runs past the edge of a box that hides the overflow. A strip that
      // scrolls sideways is the edge-fade recipe and is not a cut for a tab or
      // a chip, which a finger drags into view; it is for a picker, whose
      // value is the thing being read, and that is the case reported.
      for (const el of controls) {
        const b = el.getBoundingClientRect();
        const picker = el.tagName === 'SELECT' || el.classList.contains('select-opener') || el.tagName === 'INPUT';
        for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
          const cs = getComputedStyle(p);
          if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && !picker) break;
          if (cs.overflowX === 'visible') continue;
          const pb = p.getBoundingClientRect();
          if (b.right > pb.right + 1 || b.left < pb.left - 1) clipped.push(`${name(el)} cut by ${name(p)} at ${round(pb.right)} (ends ${round(b.right)})`);
          break;
        }
      }
      // A select's chosen text cut by its own box: measured by drawing it.
      const cv = document.createElement('canvas').getContext('2d');
      for (const s of controls.filter((el) => el.tagName === 'SELECT')) {
        const cs = getComputedStyle(s); cv.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
        const t = s.options[s.selectedIndex] ? s.options[s.selectedIndex].text : '';
        const room = s.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        if (cv.measureText(t).width > room + 1) clipped.push(`${name(s)} "${t.slice(0, 24)}" ${round(cv.measureText(t).width)}>${round(room)}`);
      }
      // 3px of slack: the bell's unread dot hangs 2px over its button's corner
      // by design (measured), and that is not a box too narrow for its text.
      // **What overflows has to be content, not a grip placed on the edge.**
      // A board's card and text box carry eight resize grips centred on their
      // border (10px, `-5px` offsets), which is where a grip goes in every
      // drawing app: they made a fresh text box read as 203>198 and a card as
      // 253>248 here (measured: the grips on the right edge and nothing else,
      // at opacity 1 because the emulated tap leaves the pointer hovering the
      // card). That is placement, not a box too narrow for what it holds, which
      // is this check's question. So an overflow counts when what runs past
      // the edge is drawn and is either in flow or carries text: an
      // absolutely placed piece with no text of its own is a grip, a badge or
      // a dot, and hangs over the edge on purpose.
      // Returns what is drawn past the edge (named in the finding), or null.
      const drawnPast = (el) => {
        const right = el.getBoundingClientRect().right;
        const child = [...el.querySelectorAll('*')].find((d) => {
          if (d.getBoundingClientRect().right <= right + 1) return false;
          const own = getComputedStyle(d);
          if ((own.position === 'absolute' || own.position === 'fixed') && !d.textContent.trim()) return false;
          //: A deliberate bleed (a negative inline margin: the ring-room rule,
          //: the timeline's day well below 400) runs past by that margin only.
          //: A corner count (`.tab-badge` on the Tidy broom) hangs over on
          //: purpose; and the ring-room bleed (`margin-inline: -ring-room`
          //: with the same padding, 08-consistency.css) keeps its content
          //: inside the box: only its padding runs past (INBOX 1314).
          if (own.position === 'absolute' && d.classList.contains('tab-badge')) return false;
          if (parseFloat(own.marginRight) < 0 && d.getBoundingClientRect().right <= right + 1 - parseFloat(own.marginRight)) return false;
          for (let p = d; p && p !== el; p = p.parentElement) {
            const cs = getComputedStyle(p);
            if (Number(cs.opacity) === 0 || cs.visibility === 'hidden' || cs.display === 'none') return false;
            //: Inside a strip that scrolls or clips on its own, what is past
            //: the edge is that strip's to show (INBOX 1314).
            if (p !== d && cs.overflowX !== 'visible') return false;
          }
          return true;
        });
        if (child) return name(child);
        const text = [...el.childNodes].some((n) => {
          if (n.nodeType !== 3 || !n.textContent.trim()) return false;
          const range = document.createRange();
          range.selectNodeContents(n);
          return range.getBoundingClientRect().right > right + 1;
        });
        return text ? 'its text' : null;
      };
      const wide = [...document.querySelectorAll('.tab-page:not(.hidden) *, #top-bar *, #phone-tab-dock *')]
        .filter((el) => vis(el) && el.scrollWidth > el.clientWidth + 3 && getComputedStyle(el).overflowX === 'visible' && el.clientWidth > 0)
        .map((el) => [el, drawnPast(el)])
        .filter(([, past]) => past)
        .slice(0, 4).map(([el, past]) => `${name(el)} ${el.scrollWidth}>${el.clientWidth} (${past})`);
      // A row designed for touch: nothing of a row's own drawn over its text
      // at rest. Two shapes were reported on Notes at 390: the row's action
      // strip sitting on its chips, and a red and a blue strip at the row's
      // edges, which are the swipe underlays showing their padding at 0px.
      const rowFaults = [];
      for (const li of [...content.querySelectorAll(':scope > li')].filter(vis).slice(0, 4)) {
        for (const pe of ['::before', '::after']) {
          const cs = getComputedStyle(li, pe);
          if (cs.content === 'none' || cs.display === 'none' || cs.visibility === 'hidden') continue;
          const w = parseFloat(cs.width) + parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
          if (cs.position === 'absolute' && w > 0.5) rowFaults.push(`${pe} ${round(w)}px wide at rest`);
        }
        const texts = [...li.querySelectorAll('.entry-content, .entry-title, .chip, .entry-date')].filter(vis);
        for (const btn of [...li.querySelectorAll('button')].filter(vis)) {
          const b = btn.getBoundingClientRect();
          const hit = texts.find((t) => !t.contains(btn) && !btn.contains(t) && (() => {
            const a = t.getBoundingClientRect();
            return Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2;
          })());
          if (hit) rowFaults.push(`${name(btn)} ${btn.getAttribute('aria-label') || ''} over ${name(hit)}`);
        }
      }
      // Nothing fixed lands on the tab bar: a toast and the agent activity
      // panel both did (INBOX 392), and the bar is the one way between tabs.
      const tabBar = document.getElementById('phone-tab-dock');
      const onBar = [];
      if (tabBar && vis(tabBar)) {
        const t = tabBar.getBoundingClientRect();
        for (const el of document.body.querySelectorAll('*')) {
          if (tabBar.contains(el) || el.contains(tabBar)) continue;
          if (el.closest('.modal-overlay, .action-menu, .select-menu, [role="tooltip"]')) continue;
          if (getComputedStyle(el).position !== 'fixed' || !vis(el)) continue;
          const b = el.getBoundingClientRect();
          if (b.bottom > t.top + 1 && b.top < t.bottom && b.right > t.left && b.left < t.right) onBar.push(`${name(el)} ${round(b.top)}-${round(b.bottom)}`);
        }
      }
      return {
        onBar: onBar.slice(0, 4),
        rowFaults: [...new Set(rowFaults)].slice(0, 4),
        chrome: round(total),
        bands: outer.map((a) => `${name(a.el)} ${round(a.bottom - a.top)}`),
        contentTop: round(firstItem.getBoundingClientRect().top),
        scroller: name(scroller),
        pageW: document.documentElement.scrollWidth,
        small: [...new Set(small)].slice(0, 6),
        clipped: [...new Set(clipped)].slice(0, 6),
        wide,
      };
    }, { sel: contentSel, W, H, MIN });
    await page.evaluate(() => document.getElementById('agent-monitor')?.classList.add('hidden'));
    const bad = [];
    if (r.none) bad.push('no content found for ' + contentSel);
    else {
      if (r.chrome > H * MAX_CHROME) bad.push(`chrome ${r.chrome}px is ${Math.round(r.chrome / H * 100)}% of ${H}`);
      if (r.pageW > W) bad.push(`page is ${r.pageW} wide in ${W}`);
      if (r.wide.length) bad.push('wider than its box: ' + r.wide.join(', '));
      if (r.clipped.length) bad.push('clipped: ' + r.clipped.join(', '));
      if (r.small.length) bad.push(`under ${MIN}px: ` + r.small.join(', '));
      if (r.rowFaults.length) bad.push('row at rest: ' + r.rowFaults.join(', '));
      if (r.onBar.length) bad.push('on the tab bar: ' + r.onBar.join(', '));
      if (r.contentTop > H * MAX_CONTENT_TOP) bad.push(`content starts at y=${r.contentTop}, below ${Math.round(H * MAX_CONTENT_TOP)}`);
    }
    failures += bad.length;
    console.log(`  ${tab.padEnd(10)} chrome ${String(r.chrome ?? '-').padStart(3)}px (${r.chrome ? Math.round(r.chrome / H * 100) : '-'}%)  content at y=${r.contentTop ?? '-'}  [${(r.bands || []).join(', ')}]`);
    for (const line of bad) console.log('      ' + line);
  }
  // Where the page stops and the status bar begins, on every tab at the width
  // asked for (OPEN.md: "the status bar folds into the top bar under 680";
  // measured, it is not folded at any width and does not overlap: 1093x614,
  // 1024x600, 820x600, 700x700, 681x800, 640x700, 600x700 all end the page
  // exactly where the bar begins, 37 to 52px of it). The bar's own height is
  // printed, so a fold that someday happens is a change in a number.
  {
    const stops = [];
    for (const tab of ['dashboard', 'notes', 'chat', 'library', 'timeline', 'reminders']) {
      await page.evaluate((t) => switchTab(t), tab);
      await page.waitForTimeout(700);
      const g = await page.evaluate(() => {
        const sb = document.getElementById('status-bar').getBoundingClientRect();
        const dock = document.getElementById('phone-tab-dock');
        const pg = document.querySelector('.tab-page:not(.hidden)').getBoundingClientRect();
        const foot = dock && dock.checkVisibility() ? dock.getBoundingClientRect().top : sb.top;
        return { sbH: Math.round(sb.height), pageBottom: Math.round(pg.bottom), foot: Math.round(Math.min(foot, sb.height ? sb.top : foot)) };
      });
      if (g.pageBottom > g.foot + 1) { console.log(`      ${tab}: the page runs to ${g.pageBottom}, under the bar or dock at ${g.foot}`); failures += 1; }
      stops.push(`${tab} ${g.pageBottom}/${g.foot}`);
    }
    console.log(`  page end / bar top: ${stops.join(', ')}  (status bar ${W < 600 ? 'folded away below 600' : 'its own band'})`);
  }
  // The status bar's transient state below 600: it comes back for the three
  // things a person has to see without asking (a running job, offline, power
  // saver: `10-responsive.css`, "one bar at the foot of a phone"), and when it
  // does it must be a touch bar standing on the tab bar, not the desktop strip
  // of seven 28px items it once came back as. The agent's runs and the plain
  // activity are NOT among them (INBOX 430: folded into More), so showing
  // either must leave the bar at 0px. This probe un-hid `#status-activity` and
  // read "0px tall" as a finding for a long time: it was reading the one
  // element the phone bar deliberately keeps away.
  if (W < 600) {
    const read = (id, text) => page.evaluate(({ id, text }) => {
      const el = document.getElementById(id);
      const was = el.classList.contains('hidden');
      const off = el.classList.contains('status-slot-off');
      el.classList.remove('hidden', 'status-slot-off');
      const kept = el.textContent;
      if (!el.textContent.trim()) el.textContent = text;
      const bar = document.getElementById('status-bar').getBoundingClientRect();
      const tabs = document.getElementById('phone-tab-dock').getBoundingClientRect();
      const items = [...document.querySelectorAll('#status-bar button, #status-bar .chip')]
        .filter((e) => e.checkVisibility())
        .map((e) => ({ id: e.id, tag: e.tagName, h: Math.round(e.getBoundingClientRect().height) }));
      const out = { barH: Math.round(bar.height), barBottom: Math.round(bar.bottom), tabsTop: Math.round(tabs.top), items };
      el.textContent = kept;
      if (was) el.classList.add('hidden');
      if (off) el.classList.add('status-slot-off');
      return out;
    }, { id, text });
    for (const [id, text] of [['status-task', 'Sweep probe job'], ['offline-indicator', 'Offline'], ['power-saver-indicator', 'Power saver']]) {
      const t = await read(id, text);
      const bad = [];
      if (t.barH < 44) bad.push(`the bar came back ${t.barH}px tall`);
      if (t.barBottom > t.tabsTop + 1) bad.push(`the bar runs under the tab bar (${t.barBottom} past ${t.tabsTop})`);
      // Controls only: the offline and power saver chips are `role="status"` labels, not something a finger presses.
      const small = t.items.filter((i) => i.tag === 'BUTTON' && i.h < 44);
      if (small.length) bad.push('items under 44px: ' + small.map((i) => `${i.id} ${i.h}`).join(', '));
      console.log(`  status bar, transient (${id}): ${t.barH}px, ${t.items.length} item(s)`);
      for (const line of bad) console.log('      ' + line);
      failures += bad.length;
    }
    const quiet = await read('status-activity', 'Sweep probe activity');
    console.log(`  status bar with only the activity showing: ${quiet.barH}px (must stay 0: folded into More)`);
    if (quiet.barH !== 0) { console.log(`      the activity brought the bar back at ${quiet.barH}px`); failures += 1; }
  }
  for (const line of [...new Set(errs)]) console.log('  ' + line);
  failures += new Set(errs).size;
  console.log(failures ? `\nFAIL: ${failures} findings` : '\nPASS: 0 findings');
  await browser.close();
  process.exit(failures ? 1 : 0);
})();
