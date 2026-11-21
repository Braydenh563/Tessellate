// INBOX 431 (5), the owner: "if it is perched on like a chat message bubble
// or a library card, when it scrolls with them it should probably go behind
// the top bar like the thing it is perched on not in front of it. If say it
// is sitting on or perched on an element like the top bar, then it would be
// in front".
//
// Per case, the companion is put on a panel the way a drag puts it there
// (`nameMarkBuddyDrop` then `nameMarkBuddyMoveTo`, as the release does), on
// a chat message, a library card and a note card, each placed twice: low
// (the card well inside its scroll area) and high (the card's top edge just
// under the area's top, so the figure's head is over the gap or the bar).
// The area is then scrolled with the wheel so the perch passes under the top
// bar, and back the other way so it passes under the bottom bar. Every frame
// records how many px of the drawn figure are visible (the figure's box
// clipped by the band's box, and by the shutter's inside it, when it rides):
//   overTop   rows inside the top bar's rect;
//   overBot   rows inside the bottom bar's rect;
//   pastClip  rows outside the perch's own clip box (its scroll area's
//             visible box under the top bar and any bar sticking in it, over
//             the bottom bar: `nameMarkBuddyBand`).
// Each is judged only on the frames its perch (the card's top edge) has
// itself gone under that line: "exactly like its perch". At rest, a head
// over a bar is drawn whole, by design (the band is widened for it), so
// rest frames are reported (`restPastClip`) and not failed.
// A last case hangs it under the top bar (a perch on the bar itself) and
// checks it is drawn in front: not riding, band z-index over the bar's.
// Env: BASE, KIND (atlas), CASES (chat,library,notes,dashboard), SCALE (1;
// 1.5 is Large). Exits 1 when any such frame shows a figure row over a bar
// or past its perch's clip, or when the bar perch is not in front.
const { boot } = require('./lib.js');
const KIND = process.env.KIND || 'atlas';
const CASES = (process.env.CASES || 'chat,library,notes,dashboard').split(',');
const SCALE = Number(process.env.SCALE || 1);
const CARD = {
  chat: '#chat-messages > .msg',
  library: '#tab-library article.library-card',
  notes: '#entry-list > li',
  dashboard: '#tab-dashboard .dash-widget',
};

(async () => {
  const { browser, ctx, page } = await boot({ viewport: { width: 1440, height: 900 } });
  void ctx;
  const have = await page.evaluate(async () => (await apiJson('/entries?limit=60')).length || 0);
  if (have < 40) {
    await page.evaluate(async (n) => {
      for (let i = 0; i < n; i += 1) {
        await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `Stack probe note ${i}. A line of words so the card has a body to it, and a second sentence for height.` }) });
      }
    }, 44 - have);
  }
  const docs = await page.evaluate(async () => (await apiJson('/documents?limit=60')).length || 0);
  if (docs < 30) {
    await page.evaluate(async (n) => {
      for (let i = 0; i < n; i += 1) {
        await apiJson('/documents', { method: 'POST', body: JSON.stringify({ title: `Stack probe document ${i}`, content: `A document with a few words in it, number ${i}.`, file_type: 'md' }) });
      }
    }, 32 - docs);
  }
  await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, KIND);
  await page.evaluate(() => localStorage.removeItem('nm-buddy-spots'));
  if (SCALE !== 1) await page.evaluate((s) => nameMarkBuddySetSize(s, true), SCALE);
  let bad = 0;
  const results = [];
  for (const tab of CASES) {
    await page.evaluate((t) => revealTab(t), tab);
    await page.waitForTimeout(1200);
    if (tab === 'notes') await page.evaluate(() => typeof loadEntries === 'function' && loadEntries()).catch(() => {});
    if (tab === 'library') await page.evaluate(async () => { await ensureModule('library'); await loadLibrary(); }).catch(() => {});
    if (tab === 'chat') {
      await page.evaluate(async () => { await ensureModule('chatTurn');
        if (document.querySelectorAll('#chat-messages > .msg').length > 20) return;
        for (let i = 0; i < 14; i += 1) {
          addBubble('user', `Question number ${i} about my notes, with a few more words`);
          addBubble('assistant', `Answer ${i}. A longer reply with a couple of sentences so the bubble has some height to it. And another line after that.`);
        }
      });
    }
    await page.waitForTimeout(1500);
    for (const where of ['low', 'high']) {
      const setup = await page.evaluate(({ sel, where }) => {
        const cards = [...document.querySelectorAll(sel)].filter((el) => el.getBoundingClientRect().width > 200);
        if (!cards.length) return { error: `no ${sel}` };
        const scroller = nmb.inner.nameMarkBuddyScroller(cards[0]);
        if (!scroller) return { error: 'no scroller', n: cards.length };
        const card = cards[Math.min(cards.length - 1, Math.floor(cards.length * 0.5))];
        // The line its perch is cut at: the area's visible box, under the top
        // bar and any bar that sticks in the area, over the bottom bar.
        const { lo: clipTop, hi: clipBot } = nmb.inner.nameMarkBuddyBand(scroller, card);
        // A card half way down the list, scrolled to where the case wants
        // its top edge: 260px under the area's top (low), or 20px (high), so
        // its figure's head is over whatever is above the area.
        for (const c of document.querySelectorAll('[data-probe-card]')) delete c.dataset.probeCard;
        card.dataset.probeCard = '1';
        const want = clipTop + (where === 'low' ? 260 : 20);
        scroller.scrollTop += card.getBoundingClientRect().top - want;
        const r = card.getBoundingClientRect();
        const buddy = document.getElementById('nm-buddy');
        nameMarkBuddyIndexReset();
        // Let go along the card's top edge, as a drag would be, at the first
        // place it lands on this card (a control above it pushes it along).
        let landed = null;
        for (let x = r.left + 8; x < r.right - 72; x += 32) {
          const at = nameMarkBuddyDrop(Math.round(x), Math.round(r.top - 74));
          const on = at.edge?.el && (at.edge.el === card || card.contains(at.edge.el));
          if (on && (!landed || at.y < landed.y)) landed = at;
          if (on && where === 'low') break;
        }
        if (!landed) landed = nameMarkBuddyDrop(Math.round(r.left + Math.min(360, r.width / 2)), Math.round(r.top - 74));
        nameMarkBuddyMoveTo(buddy, landed, true);
        return { cardTop: Math.round(r.top), clipTop, clipBot, landed: { kind: landed.kind, pose: landed.pose, y: landed.y, edge: landed.edge?.kind }, riding: !!nmb.ride, glued: nmb.glue ? nmb.glue.el === card || card.contains(nmb.glue.el) || nmb.glue.el.contains(card) : false, st: scroller.scrollTop, max: scroller.scrollHeight - scroller.clientHeight };
      }, { sel: CARD[tab], where });
      if (setup.error) { console.log(tab, where, JSON.stringify(setup)); bad += 1; continue; }
      await page.waitForTimeout(700);
      await page.evaluate(({ clipTop, clipBot }) => {
        window.__trace = [];
        window.__stop = false;
        const buddy = document.getElementById('nm-buddy');
        const face = buddy.querySelector('.nm-buddy-face');
        const band = document.getElementById('nm-buddy-band');
        const shutter = band.querySelector('.nm-buddy-shutter');
        const card = document.querySelector('[data-probe-card]');
        const tb = document.getElementById('top-bar');
        const bb = document.getElementById('phone-tab-dock')?.getBoundingClientRect().height ? document.getElementById('phone-tab-dock') : document.getElementById('status-bar');
        const cut = (a, b) => ({ left: Math.max(a.left, b.left), top: Math.max(a.top, b.top), right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom) });
        const area = (r) => Math.max(0, r.right - r.left) * Math.max(0, r.bottom - r.top);
        const rows = (r) => (r.right > r.left ? Math.max(0, r.bottom - r.top) : 0);
        const record = () => {
          const f = face.getBoundingClientRect();
          const riding = band.classList.contains('nmb-riding');
          let seen = riding ? cut(f, band.getBoundingClientRect()) : { left: f.left, top: f.top, right: f.right, bottom: f.bottom };
          if (riding && shutter) seen = cut(seen, shutter.getBoundingClientRect());
          const t = tb.getBoundingClientRect();
          const b = bb.getBoundingClientRect();
          const c = card.getBoundingClientRect();
          const win = { left: -1e5, right: 1e5 };
          window.__trace.push({
            riding,
            glued: !!nmb.glue && (nmb.glue.el === card || card.contains(nmb.glue.el)),
            overTop: Math.round(rows(cut(seen, t))),
            overBot: Math.round(rows(cut(seen, b))),
            pastTop: Math.round(rows(cut(seen, { ...win, top: -1e5, bottom: clipTop }))),
            pastBot: Math.round(rows(cut(seen, { ...win, top: clipBot, bottom: 1e5 }))),
            tbBottom: t.bottom,
            bbTop: b.top,
            cardTopF: c.top,
            seenPx: Math.round(area(seen)),
            figTop: Math.round(f.top),
            cardTop: Math.round(c.top),
            bandTop: riding ? Math.round(band.getBoundingClientRect().top) : null,
          });
        };
        const loop = () => { if (!window.__stop) requestAnimationFrame(loop); setTimeout(record, 0); };
        requestAnimationFrame(loop);
      }, setup);
      await page.mouse.move(720, Math.round((setup.clipTop + setup.clipBot) / 2));
      // Up under the top bar: the content moves up, so the wheel goes down.
      for (let i = 0; i < 14; i += 1) { await page.mouse.wheel(0, 40); await page.waitForTimeout(50); }
      await page.waitForTimeout(300);
      // And down past the bottom bar.
      for (let i = 0; i < 40; i += 1) { await page.mouse.wheel(0, -40); await page.waitForTimeout(40); }
      await page.waitForTimeout(300);
      const trace = await page.evaluate(() => { window.__stop = true; return window.__trace; });
      const ride = trace.filter((r) => r.riding && r.glued);
      // Judged only where the perch itself has gone under the line.
      const underTop = ride.filter((r) => r.cardTopF < setup.clipTop);
      const underBot = ride.filter((r) => r.cardTopF > setup.clipBot);
      const past = [...underTop.map((r) => r.pastTop), ...underBot.map((r) => r.pastBot)];
      const rest = ride.length ? ride[0] : null;
      const sum = {
        tab, where, landed: setup.landed, ridingFrames: ride.length, frames: trace.length,
        underFrames: underTop.length + underBot.length,
        overTopMax: Math.max(0, ...ride.filter((r) => r.cardTopF < r.tbBottom).map((r) => r.overTop)),
        overBotMax: Math.max(0, ...ride.filter((r) => r.cardTopF > r.bbTop).map((r) => r.overBot)),
        pastClipMax: Math.max(0, ...past),
        pastClipFrames: past.filter((n) => n > 0).length,
        restPastClip: rest ? rest.pastTop + rest.pastBot : null,
        bandTops: [...new Set(ride.map((r) => r.bandTop))].slice(0, 4),
        clipTop: setup.clipTop,
        notRidingOverTop: Math.max(0, ...trace.filter((r) => !r.riding).map((r) => r.overTop)),
      };
      results.push(sum);
      console.log(JSON.stringify(sum));
      if (!ride.length || sum.overTopMax > 0 || sum.overBotMax > 0 || sum.pastClipMax > 0) bad += 1;
      await page.evaluate(() => { const s = nmb.inner.nameMarkBuddyScroller(document.querySelector('[data-probe-card]')); if (s) s.scrollTop = 0; });
      await page.waitForTimeout(400);
    }
  }
  // On the top bar itself: hanging from its underside, it is in front.
  const bar = await page.evaluate(() => {
    const buddy = document.getElementById('nm-buddy');
    const { top } = nameMarkBuddyLedges();
    nameMarkBuddyIndexReset();
    const obstacles = nmb.inner.nameMarkBuddyObstacles(nameMarkBuddyTab());
    const landed = nmb.inner.nameMarkBuddyPerches(nameMarkBuddyTab()).find((p) => p.kind === 'hang' && !nmb.inner.nameMarkBuddyHits(p.x, p.y, p.pose, obstacles, p.legs));
    if (!landed) return { error: 'no hang perch' };
    nameMarkBuddyMoveTo(buddy, landed, true);
    const band = document.getElementById('nm-buddy-band');
    const f = buddy.querySelector('.nm-buddy-face').getBoundingClientRect();
    return {
      landed: { kind: landed.kind, pose: landed.pose, edge: landed.edge?.kind },
      riding: band.classList.contains('nmb-riding'),
      bandZ: Number(getComputedStyle(band).zIndex),
      barZ: Number(getComputedStyle(document.getElementById('top-bar')).zIndex),
      overTop: Math.round(Math.max(0, Math.min(f.bottom, top.bottom) - Math.max(f.top, top.top))),
    };
  });
  console.log('bar', JSON.stringify(bar));
  if (bar.error || bar.riding || bar.bandZ <= bar.barZ) bad += 1;
  await browser.close();
  console.log(bad ? `FAIL ${bad}` : 'ok');
  process.exit(bad ? 1 : 0);
})();
