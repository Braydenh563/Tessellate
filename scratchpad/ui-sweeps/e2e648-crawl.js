// INBOX 648, no-model walk: on a seeded notebook with no AI model, press every
// visible, enabled, non-destructive button on each surface and record what
// happened. A press that changes nothing in the page and fetches nothing is a
// dead button; a spinner or busy marker still showing 5 s later (WAIT) is an endless
// spinner; a 5xx, a page error or a toast saying "failed" is a fallback that
// is not clear. One JSON line per press to stdout; review the flagged ones.
//
//   STATE=tests-e2e/.auth-state.json BASE=http://127.0.0.1:8808 \
//   ROUTES="#/notes,#/chat" node scratchpad/ui-sweeps/e2e648-crawl.js
const { chromium } = require("/opt/node22/lib/node_modules/playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8808";
const STATE = process.env.STATE;
const ROUTES = (process.env.ROUTES ||
  "#/dashboard,#/notes/capture,#/notes/browse,#/notes/ask,#/chat,#/graph,#/library,#/timeline,#/reminders").split(",");
// Never press: anything that deletes, ends the session or leaves the app.
const SKIP = /delete|remove|bin|trash|lock|sign out|log out|reset|clear|erase|wipe|uninstall|restore|discard|forget|empty|quit|close app|download|export|print|backup|install|update|shut/i;

async function pressAll(page, route, out) {
  let home = "";
  const go = async () => {
    // A goto that changes only the hash is not a load: blank first.
    await page.goto("about:blank");
    await page.goto(BASE + "/" + route, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#tab-bar, nav", { timeout: 20000 }).catch(() => {});
    await page.waitForTimeout(1500);
    home = page.url();
    await tag();
  };
  // Every candidate is tagged data-crawl=<n> in document order; after a fresh
  // load the same walk tags the same controls again.
  const tag = () => page.evaluate(() => {
    const seen = new Set();
    const name = (b) => (b.getAttribute("aria-label") || b.textContent || b.title || "").trim().replace(/\s+/g, " ").slice(0, 60);
    const list = [];
    for (const b of document.querySelectorAll("main button, main [role=button], main summary, .tab-panel button, .tab-panel summary")) {
      const r = b.getBoundingClientRect();
      if (!r.width || !r.height || b.disabled || b.getAttribute("aria-disabled") === "true") continue;
      if (getComputedStyle(b).visibility === "hidden") continue;
      const n = name(b);
      const key = (b.id || "") + "|" + n;
      if (!n || seen.has(key)) continue;
      seen.add(key);
      b.dataset.crawl = String(list.length);
      list.push({ id: b.id, name: n, idx: list.length });
    }
    return list;
  });
  await go();
  const labels = await tag();
  for (const { id, name, idx } of labels) {
    if (SKIP.test(name) || SKIP.test(id || "")) continue;
    if (page.url() !== home || (await page.locator(".confirm-overlay, [role=dialog]:visible").count())) await go();
    else { await page.keyboard.press("Escape"); await page.keyboard.press("Escape"); }
    const find = () => page.evaluateHandle(([wantId, wantName]) => {
      const name = (b) => (b.getAttribute("aria-label") || b.textContent || b.title || "").trim().replace(/\s+/g, " ").slice(0, 60);
      return [...document.querySelectorAll("main button, main [role=button], main summary, .tab-panel button, .tab-panel summary")]
        .find((b) => (b.id || "") === (wantId || "") && name(b) === wantName && b.getBoundingClientRect().width > 0) || null;
    }, [id, name]);
    let handle = (await find()).asElement();
    if (!handle) { out({ route, id, name, gone: true }); continue; }
    const target = { click: async (o) => { await handle.hover({ timeout: 1500 }).catch(() => {}); return handle.click(o); }, isVisible: () => handle.isVisible() };
    if (!(await target.isVisible().catch(() => false))) continue;
    const errors = [];
    const bad = [];
    let fetches = 0;
    const onErr = (e) => errors.push(String(e.message).slice(0, 160));
    const onResp = (r) => {
      if (r.request().resourceType() === "fetch" || r.request().resourceType() === "xhr") fetches++;
      if (r.status() >= 500) bad.push(`${r.status()} ${r.url().replace(BASE, "")}`);
    };
    page.on("pageerror", onErr);
    page.on("response", onResp);
    await page.evaluate(() => {
      window.__mut = 0;
      window.__mo && window.__mo.disconnect();
      window.__mo = new MutationObserver((m) => {
        for (const x of m) if (!x.target.closest || !x.target.closest("#status-bar, .clock, #ai-status")) window.__mut++;
      });
      window.__mo.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
    });
    const href0 = page.url();
    let clicked = true;
    let why = "";
    await target.click({ timeout: 3000 }).catch(async () => {
      // Something kept open by the last press: start the surface again.
      await go();
      handle = (await find()).asElement();
      await (handle ? handle.click({ timeout: 3000 }) : Promise.reject(new Error("gone after reload"))).catch((e) => { clicked = false; why = String(e.message).split("\n").slice(0, 3).join(" ").slice(0, 200); });
    });
    await page.waitForTimeout(+(process.env.WAIT || 5000));
    const after = await page.evaluate(() => {
      const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden"; };
      const spin = [...document.querySelectorAll(".spinner, [aria-busy=true], .thinking, .busy, .is-loading")].filter(vis)
        .map((e) => (e.id || e.className || e.tagName).toString().slice(0, 60));
      const toasts = [...document.querySelectorAll(".toast")].filter(vis).map((e) => e.textContent.trim().replace(/\s+/g, " ").slice(0, 140));
      return { mut: window.__mut, spin, toasts };
    });
    page.off("pageerror", onErr);
    page.off("response", onResp);
    const row = { route, id, name, clicked, why, mut: after.mut, fetches, nav: page.url() !== href0, spin: after.spin, toasts: after.toasts, bad, errors };
    row.flag = !clicked ? "" : errors.length || bad.length ? "ERROR" : after.spin.length ? "SPIN" : !after.mut && !fetches && !row.nav ? "DEAD" : /fail|error|could not|couldn't|unavailable/i.test(after.toasts.join(" ")) ? "TOAST" : "";
    out(row);
  }
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, storageState: STATE });
  await ctx.addInitScript(() => {
    try { localStorage.setItem("onboardingDone", "1"); localStorage.setItem("tourDone", "1"); localStorage.setItem("nm-buddy-hint", "done"); } catch (e) {}
  });
  const page = await ctx.newPage();
  page.on("dialog", (d) => d.dismiss());
  for (const route of ROUTES) {
    await pressAll(page, route, (row) => console.log(JSON.stringify(row))).catch((e) => console.log(JSON.stringify({ route, crash: String(e).slice(0, 200) })));
  }
  await browser.close();
})();
