// The owner, 2026-11-10: "I feel like paste should be a submenu". Opens the document editor's
// right-click menu, lists its top rows, opens "Paste as" and lists the flyout's rows and whether it fits.
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const ev = (fn, a) => page.evaluate(fn, a);
  const id = await ev(async () => (await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: `Sub ${Date.now()}`, content: "alpha beta gamma\n", file_type: "md" }) })).id);
  await ev(() => switchTab("documents")); await page.waitForTimeout(700);
  await ev((id) => loadDocuments(id), id); await page.waitForTimeout(3000);
  await ev(() => { const b = [...document.querySelectorAll(".confirm-overlay button")].find((x) => /Don.t check/.test(x.textContent)); if (b) b.click(); });
  await ev(() => setDocView("live")); await page.waitForTimeout(600);
  await ev(() => { const v = docSurface().view; v.focus(); const at = v.coordsAtPos(7);
    v.contentDOM.querySelector(".cm-line").dispatchEvent(new MouseEvent("contextmenu", { clientX: at.left, clientY: at.top + 4, bubbles: true, cancelable: true })); });
  await page.waitForTimeout(500);
  const top = await ev(() => [...document.querySelectorAll(".action-menu:not(.hidden):not(.submenu) > :is(button, .menu-group) ")].map((b) => b.textContent.trim().replace(/\s+/g, " ")));
  const btn = page.locator(".action-menu:not(.hidden):not(.submenu) button", { hasText: "Paste as" }).first();
  await btn.hover(); await btn.click().catch(() => {}); await page.waitForTimeout(500);
  const sub = await ev(() => { const m = [...document.querySelectorAll(".action-menu.submenu")].find((x) => !x.classList.contains("hidden") && x.offsetParent);
    if (!m) return null; const b = m.getBoundingClientRect();
    return { rows: [...m.querySelectorAll(".menu-item")].map((x) => x.textContent.trim()), fits: b.left >= 0 && b.top >= 0 && b.right <= innerWidth && b.bottom <= innerHeight }; });
  console.log(JSON.stringify({ top, sub }));
  await page.screenshot({ path: process.env.OUT || "/tmp/dps.png" });
  await browser.close();
})();
