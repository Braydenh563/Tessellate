// Drives minimise then restore from the pill on every panel that shows .panel-min.
process.env.BASE = process.env.BASE || "http://127.0.0.1:8793";
const { boot } = require("./lib.js");
const OPENERS = {
  emoji: `pickIconOrEmoji({ anchor: null, title: "Insert an emoji or icon", onPick: () => {} })`,
  "emoji-anchored": `(() => { const a = document.createElement("div"); a.style.cssText = "position:fixed;left:300px;top:250px;width:2px;height:18px"; document.body.appendChild(a); return pickIconOrEmoji({ anchor: a, title: "Emoji", onPick: () => {} }); })()`,
  calculator: `ensureModule("replyKit").then(() => openCalculator("", "work"))`,
  equation: `ensureModule("replyKit").then(() => openCalculator("", "equation", { target: docSurface() }))`,
  settings: `openSettingsModal()`,
  shortcuts: `openShortcuts()`,
  appearance: `openAppearancePanel()`,
  guide: `(typeof openHelpChat === "function" ? openHelpChat() : ensureModule("helpChat").then(() => openHelpChat()))`,
};
const ONLY = (process.env.ONLY || "").split(",").filter(Boolean);
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(1500);
  await page.evaluate(async () => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Min", content: "Hello\n\nthere " }) });
    await loadDocuments(d.id); setDocView("live");
  });
  await page.waitForTimeout(2000);
  for (const [name, code] of Object.entries(OPENERS)) {
    if (ONLY.length && !ONLY.includes(name)) continue;
    const res = { name };
    try {
      await page.evaluate(`(async () => { try { await (${code}); } catch (e) { window.__openErr = String(e); } })()`);
      await page.waitForTimeout(1200);
      // adopt: hover the head
      const headSel = await page.evaluate(() => {
        const heads = [...document.querySelectorAll(".dialog-head")].filter((h) => h.getClientRects().length);
        const h = heads[heads.length - 1];
        if (!h) return null;
        h.dataset.sweepHead = "1";
        return "[data-sweep-head]";
      });
      if (!headSel) { res.err = "no panel head"; console.log(JSON.stringify(res)); continue; }
      const hb = await (await page.$(headSel)).boundingBox();
      await page.mouse.move(hb.x + 30, hb.y + 10);
      await page.waitForTimeout(300);
      res.hasMin = await page.evaluate(() => !!document.querySelector("[data-sweep-head]").closest("[role=dialog], dialog")?.querySelector(".panel-min") || !!document.querySelector("[data-sweep-head] .panel-min"));
      if (!res.hasMin) { res.note = "no .panel-min"; console.log(JSON.stringify(res)); await page.keyboard.press("Escape"); await page.evaluate(() => document.querySelector("[data-sweep-head]")?.removeAttribute("data-sweep-head")); continue; }
      await page.evaluate(() => { const h = document.querySelector("[data-sweep-head]"); (h.closest("[role=dialog], dialog") || h).querySelector(".panel-min").click(); });
      await page.waitForTimeout(500);
      res.pill = await page.evaluate(() => document.querySelectorAll("#panel-min-tray .minimised-pill").length);
      const pb = await (await page.$("#panel-min-tray .minimised-pill-open")).boundingBox();
      await page.mouse.click(pb.x + pb.width / 2, pb.y + pb.height / 2);
      await page.waitForTimeout(600);
      res.restored = await page.evaluate(() => {
        const h = document.querySelector("[data-sweep-head]");
        return !!h && h.isConnected && h.getClientRects().length > 0 && !h.closest("[data-panel-min]") && !h.closest("[inert]");
      });
      res.pillsLeft = await page.evaluate(() => document.querySelectorAll("#panel-min-tray .minimised-pill").length);
    } catch (e) { res.err = String(e).slice(0, 120); }
    console.log(JSON.stringify(res));
    // clean up: close everything
    await page.evaluate(() => { document.querySelector("[data-sweep-head]")?.removeAttribute("data-sweep-head"); document.querySelectorAll("#panel-min-tray .minimised-pill-x").forEach((b) => b.click()); });
    for (let i = 0; i < 3; i++) { await page.keyboard.press("Escape"); await page.waitForTimeout(150); }
    await page.evaluate(() => { document.querySelectorAll(".icon-picker").forEach((p) => p.remove()); });
    await page.waitForTimeout(300);
  }
  await browser.close();
})();
