// Brief 72b (WORLD_CLASS_PLAN 28, decision 71): what each named surface renders
// today, measured: the timeline, reminders and their calendar, the agent panel,
// chat and its deterministic answers with no model, the dashboard's statistics,
// the Guide, the command palette and Find anything. Reuses deepen72a.js's
// `__m` measure (read from its source, so the two can never drift).
// Usage: SEED=1 node deepen72b.js (fixtures, then back-date with
// seed-timeline.py), then BASE=http://127.0.0.1:8790 VW=1440|390 node deepen72b.js > out.json
const fs = require("fs");
const { boot } = require(process.env.SW ? process.env.SW + "/lib.js" : "./lib.js");
const MEASURE = fs.readFileSync(__dirname + "/deepen72a.js", "utf8").match(/const MEASURE = `([\s\S]*?)`;/)[1];
const VW = Number(process.env.VW || 1440);
const phone = VW < 600;
const timed = (page, trigger, ready) => page.evaluate(`(async () => {
  const t0 = performance.now();
  try { (${trigger}); } catch (e) {}
  const until = performance.now() + 15000;
  while (performance.now() < until) {
    await new Promise((res) => requestAnimationFrame(res));
    try { if (${ready}) return Math.round(performance.now() - t0); } catch (e) {}
  }
  return -1;
})()`);
const visible = (sel) => `(() => { const e = document.querySelector(${JSON.stringify(sel)}); return !!(e && e.offsetParent !== null && !e.closest('.hidden')); })()`;
(async () => {
  const opts = phone ? { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: 1440, height: 900 } };
  const { browser, page } = await boot(opts);
  await page.evaluate(MEASURE);
  const out = { VW };
  // ONLY=chat,guide runs just those rows, for a brief that owns them.
  const only = process.env.ONLY ? process.env.ONLY.split(",") : null;
  const run = async (name, fn) => { if (only && !only.includes(name)) return; try { out[name] = await fn(); } catch (e) { out[name] = { error: String(e).slice(0, 200) }; } };
  if (process.env.SEED) {
    out.seed = await page.evaluate(async (notesToo) => {
      const topics = ["harbor survey", "boiler pressure", "lecture on cells", "trip to Lisbon", "budget review", "reading list"];
      if (notesToo) for (let i = 0; i < 48; i++) await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `Note ${i + 1} about the ${topics[i % 6]}. Met Sam at the ${i % 2 ? "office" : "library"} and agreed the next step costs 40 dollars.`, tags: [topics[i % 6].split(" ")[0]] }) });
      const now = Date.now();
      for (let i = 0; i < 12; i++) await apiJson("/reminders", { method: "POST", body: JSON.stringify({ text: `Reminder ${i + 1}: follow up the ${topics[i % 6]}`, due_at: new Date(now + 3600000 + i * 86400000 * 2).toISOString() }) });
      return "ok";
    }, process.env.SEED !== "reminders");
    console.log(JSON.stringify(out)); await browser.close(); return;
  }
  const dash = async () => { await page.evaluate(() => switchTab("dashboard")); await page.waitForTimeout(700); };
  const tabClick = async (tab) => { const sel = `#tab-btn-${tab}`; const shown = await page.evaluate(visible(sel)); if (shown) await page.click(sel); else await page.evaluate((t) => switchTab(t), tab); return shown ? 1 : "no tab button at this width"; };

  await run("dashboard", async () => {
    const r = {};
    await page.evaluate(() => switchTab("notes")); await page.waitForTimeout(500);
    r.openMs = await timed(page, `switchTab("dashboard")`, `(() => { const h = document.getElementById('dash-hero'); return h && h.offsetParent && h.textContent.trim().length > 10; })()`);
    await page.waitForTimeout(1500);
    r.statsMs = await page.evaluate(async () => { const t = performance.now(); const s = await apiJson("/insights/stats"); return { ms: Math.round(performance.now() - t), keys: Object.keys(s).length, keyList: Object.keys(s).slice(0, 30) }; });
    r.widgets = await page.evaluate(() => [...new Set([...document.querySelectorAll('#tab-dashboard [class*="widget"]')].filter((e) => e.offsetParent).flatMap((e) => [...e.classList].filter((c) => /widget/.test(c))))]);
    r.headings = await page.evaluate(() => [...document.querySelectorAll('#tab-dashboard h2, #tab-dashboard h3')].filter((e) => e.offsetParent).map((e) => e.textContent.trim().slice(0, 24)));
    r.numbers = await page.evaluate(() => (document.getElementById('tab-dashboard').innerText.match(/\b\d[\d,.]*\b/g) || []).length);
    r.m = await page.evaluate(() => __m("#tab-dashboard"));
    r.entryButtons = await page.evaluate(() => Object.fromEntries(["status-agent", "status-guide", "tab-btn-timeline", "tab-btn-reminders", "tab-btn-chat"].map((id) => { const e = document.getElementById(id); return [id, !!(e && e.offsetParent && e.getBoundingClientRect().width > 0)]; })));
    return r;
  });

  // A phone keeps the table (timelineViewMode), so its rows are #timeline-table-body > *, not .timeline-rows.
  await run("timeline", async () => {
    const r = {};
    await dash();
    const t0 = Date.now(); r.clicks = await tabClick("timeline");
    await page.waitForFunction(() => document.querySelectorAll("#tab-timeline .timeline-rows > *, #timeline-table-body > *").length > 0, null, { timeout: 15000 });
    r.clickToRowsMs = Date.now() - t0; await page.waitForTimeout(1500);
    r.rows = await page.evaluate(() => document.querySelectorAll("#tab-timeline .timeline-rows > *, #timeline-table-body > *").length);
    r.m = await page.evaluate(() => __m("#tab-timeline"));
    r.views = await page.evaluate(() => [...document.querySelectorAll('#timeline-view-seg button, #timeline-view-seg [role=radio]')].filter((e) => e.offsetParent).map((e) => (e.getAttribute("aria-label") || e.textContent).trim().slice(0, 20)));
    r.dotAlign = await page.evaluate(() => { const d = document.querySelector("#tab-timeline .timeline-day-dot"); if (!d) return null; const row = d.closest("li, .timeline-day, section") || d.parentElement; const t = [...row.querySelectorAll("*")].find((e) => e !== d && e.childElementCount === 0 && e.textContent.trim().length > 2 && e.offsetParent); if (!t) return null; const a = d.getBoundingClientRect(), b = t.getBoundingClientRect(); const lh = parseFloat(getComputedStyle(t).lineHeight) || b.height; return { dotCentre: Math.round(a.top + a.height / 2), firstLineCentre: Math.round(b.top + lh / 2), deltaPx: Math.round(a.top + a.height / 2 - (b.top + lh / 2)) }; });
    r.calendarView = await page.evaluate(() => !!document.querySelector('#tab-timeline [data-view="calendar"], #tab-timeline [value="calendar"]'));
    r.aiCtl = r.m && r.m.aiControls;
    return r;
  });

  await run("reminders", async () => {
    const r = {};
    await dash();
    const t0 = Date.now(); r.clicks = await tabClick("reminders");
    await page.waitForFunction(() => document.querySelectorAll("#reminder-list-card li, #reminder-list-card .reminder-item").length > 0, null, { timeout: 15000 });
    r.clickToListMs = Date.now() - t0; await page.waitForTimeout(1200);
    r.items = await page.evaluate(() => document.querySelectorAll("#reminder-list-card li, #reminder-list-card .reminder-item").length);
    r.m = await page.evaluate(() => __m("#tab-reminders"));
    r.notification = await page.evaluate(() => ({ api: "Notification" in window, permission: "Notification" in window ? Notification.permission : "none", sw: !!navigator.serviceWorker?.controller }));
    // quick add through the magic row
    const magic = await page.evaluate(visible("#reminder-magic"));
    if (magic) {
      await page.fill("#reminder-magic", "dentist friday at 9am");
      const before = r.items; const t1 = Date.now();
      await page.click("#reminder-magic-add").catch(() => {});
      await page.waitForFunction((n) => document.querySelectorAll("#reminder-list-card li, #reminder-list-card .reminder-item").length > n, before, { timeout: 8000 }).catch(() => {});
      r.quickAddMs = Date.now() - t1;
      r.quickAdd = await page.evaluate(() => ({ status: document.getElementById("reminder-magic-status")?.textContent.trim().slice(0, 100), first: [...document.querySelectorAll("#reminder-list-card li, #reminder-list-card .reminder-item")].map((e) => e.textContent.replace(/\s+/g, " ").trim()).find((t) => /dentist/i.test(t))?.slice(0, 100) || null }));
      r.chipsWhileTyping = await page.evaluate(() => document.querySelectorAll("#reminder-magic-row .chip, #reminder-magic-row [class*=chip]").length);
    } else r.quickAdd = "magic row not visible";
    // calendar view: since Brief 55 the button opens the Timeline's calendar, reminders only
    const tc = Date.now();
    await page.evaluate(() => document.querySelector('#reminder-view-toggle [data-view="calendar"]')?.click());
    r.calOpenMs = await page.waitForFunction(() => document.querySelector(".timeline-cal-month, .timeline-cal-weekwrap")?.offsetParent, null, { timeout: 5000 }).then(() => Date.now() - tc, () => -1);
    await page.waitForTimeout(600);
    r.cal = await page.evaluate(() => { const cells = [...document.querySelectorAll(".timeline-cal-monthcell")]; return { cells: cells.length, withItems: cells.filter((c) => c.querySelector(".timeline-cal-item")).length, overflowing: cells.filter((c) => c.scrollHeight > c.clientHeight + 1 || c.scrollWidth > c.clientWidth + 1).length, cellH: cells[10] ? Math.round(cells[10].getBoundingClientRect().height) : 0, cellW: cells[10] ? Math.round(cells[10].getBoundingClientRect().width) : 0, textInCells: cells.some((c) => /Reminder|dentist/.test(c.textContent)), weekView: !!document.querySelector('[data-cal-span="week"]') }; });
    r.calM = await page.evaluate(() => __m("#tab-reminders"));
    await page.evaluate(() => document.querySelector('#reminder-view-toggle [data-view="list"]')?.click());
    return r;
  });

  await run("agent", async () => {
    const r = {};
    await dash();
    r.openMs = await timed(page, `toggleAgentPalette()`, visible("#command-palette-input"));
    await page.waitForTimeout(800);
    //: On a phone the agent is a sheet (Brief 87 row 2): measure that, and
    //: the path a thumb takes to it (More, then Ask the agent).
    const root = phone ? '.sheet-overlay[data-sheet="agent"]' : "#command-palette-overlay";
    r.m = await page.evaluate((sel) => __m(sel), root);
    if (phone) {
      r.sheetBox = await page.evaluate((sel) => { const c = document.querySelector(sel + " .sheet-card"); if (!c) return null; const b = c.getBoundingClientRect(); return { left: Math.round(b.left), right: Math.round(b.right), top: Math.round(b.top), bottom: Math.round(b.bottom), vw: innerWidth, vh: innerHeight, pastEdge: [...c.querySelectorAll("*")].filter((e) => { const x = e.getBoundingClientRect(); return e.offsetParent && x.width && (x.left < -1 || x.right > innerWidth + 1); }).length }; }, root);
      await page.keyboard.press("Escape"); await page.waitForTimeout(500);
      let taps = 0;
      await page.tap("#phone-more-btn"); taps++; await page.waitForTimeout(500);
      await page.locator(".sheet-row", { hasText: "Ask the agent" }).first().tap(); taps++;
      r.moreTaps = await page.waitForFunction(() => document.querySelector('.sheet-overlay[data-sheet="agent"] #command-palette-input'), null, { timeout: 5000 }).then(() => taps, () => -1);
    }
    r.offline = await page.evaluate(() => { const e = document.getElementById("command-palette-offline"); return e && !e.classList.contains("hidden") ? e.textContent.trim().slice(0, 160) : null; });
    r.starters = await page.evaluate(() => document.querySelectorAll("#command-palette-starters [data-example]").length);
    r.inputDisabled = await page.evaluate(() => document.getElementById("command-palette-input").disabled);
    r.disabledControls = await page.evaluate((sel) => [...document.querySelectorAll(`${sel} button, ${sel} textarea, ${sel} input`)].filter((e) => e.offsetParent && e.disabled).map((e) => e.id || e.textContent.trim().slice(0, 16)), root);
    if (!r.inputDisabled) { await page.fill("#command-palette-input", "tag every note about the harbor survey with harbor"); await page.keyboard.press("Enter"); await page.waitForTimeout(3000); }
    r.afterRun = await page.evaluate(() => ({ status: document.getElementById("command-palette-status")?.textContent.trim().slice(0, 120), results: document.getElementById("command-palette-results")?.textContent.replace(/\s+/g, " ").trim().slice(0, 200) }));
    r.monitor = await page.evaluate(() => !!document.getElementById("agent-monitor"));
    return r;
  });

  const closeAgent = async () => { await page.keyboard.press("Escape").catch(() => {}); await page.waitForTimeout(300); await page.evaluate(() => { const o = document.getElementById("command-palette-overlay"); if (o && !o.classList.contains("hidden")) toggleAgentPalette(); }).catch(() => {}); await page.waitForTimeout(300); };
  await closeAgent();
  await run("chat", async () => {
    const r = {};
    await dash();
    const t0 = Date.now(); r.clicks = await tabClick("chat");
    await page.waitForFunction(() => document.getElementById("chat-input")?.offsetParent, null, { timeout: 10000 });
    r.clickToInputMs = Date.now() - t0; await page.waitForTimeout(800);
    r.m = await page.evaluate(() => __m("#tab-chat"));
    // The reply is the last child of #chat-messages once it drops `is-generating`.
    const qs = ["how many notes do I have", "what is 15% of 240", "convert 5 km to miles", "what day is it today", "what did I write last week", "notes about the harbor", "what are my top tags", "remind me to call Sam tomorrow at 9", "what did I agree with Sam", "summarise my week", "how much did the next step cost"];
    r.answers = [];
    for (const q of qs) {
      const n0 = await page.evaluate(() => document.querySelectorAll("#chat-messages > .msg").length);
      await page.fill("#chat-input", q); const t = Date.now(); await page.click("#chat-send");
      let ms = -1, a = "";
      for (let i = 0; i < 120 && ms < 0; i++) {
        await page.waitForTimeout(150);
        const s = await page.evaluate((n) => { const kids = [...document.querySelectorAll("#chat-messages > .msg")].slice(n); const last = kids[kids.length - 1]; return { k: kids.length, gen: !!last && last.classList.contains("is-generating"), t: last ? last.innerText.replace(/\s+/g, " ").trim() : "" }; }, n0);
        if (s.k >= 2 && !s.gen && s.t.length > 8) { ms = Date.now() - t; a = s.t.slice(0, 160); }
      }
      r.answers.push({ q, ms, a });
    }
    r.after = await page.evaluate(() => __m("#tab-chat"));
    return r;
  });

  await run("guide", async () => {
    const r = {};
    await dash();
    r.openMs = await timed(page, `openHelpChat()`, visible("#help-chat-input"));
    await page.waitForTimeout(700);
    r.starters = await page.evaluate(() => document.querySelectorAll("#help-chat-starters > *").length);
    r.m = await page.evaluate(() => __m("#help-chat-group"));
    const qs = ["how do I back up my notes", "can I use it on my iphone", "how do I undo", "where are my reminders", "how do I stop the model", "what is the timeline", "how do I find anything", "reminder notifications on my computer"];
    r.answers = [];
    for (const q of qs) {
      const n0 = await page.evaluate(() => document.querySelectorAll("#help-chat-messages .help-chat-msg.is-assistant:not(.is-pending)").length);
      await page.fill("#help-chat-input", q); const t = Date.now();
      await page.press("#help-chat-input", "Enter");
      const ok = await page.waitForFunction((n) => document.querySelectorAll("#help-chat-messages .help-chat-msg.is-assistant:not(.is-pending)").length > n, n0, { timeout: 10000 }).then(() => true, () => false);
      const a = await page.evaluate(() => { const b = [...document.querySelectorAll("#help-chat-messages .help-chat-msg.is-assistant:not(.is-pending)")].pop(); return b ? { text: (b.querySelector(".help-chat-prose") || b).textContent.replace(/\s+/g, " ").trim().slice(0, 150), opens: b.querySelectorAll(".help-chat-open, button").length } : null; });
      r.answers.push({ q, ms: ok ? Date.now() - t : -1, ...a });
    }
    r.after = await page.evaluate(() => __m("#help-chat-group"));
    return r;
  });

  await run("palette", async () => {
    const r = {};
    await page.evaluate(() => { document.querySelectorAll(".modal:not(.hidden), .lock-overlay:not(.hidden)").forEach(() => {}); }); await page.keyboard.press("Escape"); await dash();
    await page.keyboard.press("Control+k"); await page.waitForTimeout(500);
    r.ctrlKOpens = await page.evaluate(visible("#palette-input"));
    await page.keyboard.press("Escape"); await page.waitForTimeout(300);
    r.openMs = await timed(page, `openPalette()`, `document.querySelectorAll('#palette-list > li').length > 0`);
    await page.waitForTimeout(400);
    r.restRows = await page.evaluate(() => document.querySelectorAll("#palette-list > li").length);
    r.commands = await page.evaluate(() => paletteCommands().length);
    r.m = await page.evaluate(() => __m("#palette-card"));
    r.queries = {};
    for (const q of ["ocr", "read text from image", "reminder", "calendar", "timeline", "undo", "agent", "stop the model", "statistics", "guide", "backup", "calculator", "timer", "convert", "word count", "find anything", "activity", "health"]) {
      await page.fill("#palette-input", q); await page.waitForTimeout(250);
      r.queries[q] = await page.evaluate(() => { const li = [...document.querySelectorAll("#palette-list > li")]; return [li.length, li.slice(0, 4).map((e) => e.textContent.replace(/\s+/g, " ").trim().slice(0, 40)).join(" | ")]; });
    }
    await page.keyboard.press("Escape");
    return r;
  });

  await run("finder", async () => {
    const r = {};
    await dash();
    r.openMs = await timed(page, `openFinder()`, visible("#finder-input"));
    r.m0 = await page.evaluate(() => __m("#finder-overlay"));
    r.queries = {};
    for (const q of ["harbor", "Sam", "last week", "boiler pressur", "reminder", "settings backup", "ocr"]) {
      await page.fill("#finder-input", ""); await page.waitForTimeout(150);
      const t = Date.now(); await page.fill("#finder-input", q);
      const ok = await page.waitForFunction(() => document.querySelectorAll("#finder-results .finder-row").length > 0, null, { timeout: 4000 }).then(() => true, () => false);
      await page.waitForTimeout(500);
      r.queries[q] = await page.evaluate(() => ({ rows: document.querySelectorAll("#finder-results .finder-row").length, groups: [...document.querySelectorAll("#finder-results .finder-group")].map((g) => g.textContent.replace(/\s+/g, " ").trim().slice(0, 18)), summary: document.getElementById("finder-summary")?.textContent.trim().slice(0, 60) }));
      r.queries[q].ms = ok ? Date.now() - t : -1;
    }
    r.m = await page.evaluate(() => __m("#finder-overlay"));
    r.filters = await page.evaluate(() => [...document.querySelectorAll("#finder-filters button, #finder-filters [role=radio], #finder-filters input")].filter((e) => e.offsetParent).map((e) => (e.getAttribute("aria-label") || e.textContent).trim().slice(0, 14)));
    await page.keyboard.press("Escape");
    return r;
  });

  await run("usage", async () => {
    await page.evaluate(() => openSettingsModal("general")); await page.waitForTimeout(1500);
    return await page.evaluate(() => ({ box: !!document.getElementById("usage-box")?.offsetParent, hidden: document.getElementById("usage-box")?.className, most: document.getElementById("usage-most")?.textContent.trim().slice(0, 120), unused: document.getElementById("usage-unused")?.textContent.trim().slice(0, 120), section: document.getElementById("usage-box")?.closest("[data-section-body], section, .settings-section")?.id || null }));
  });
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
