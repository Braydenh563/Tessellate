// L-documents-3: compare a code file with another document; measures the hunks.
// Usage: BASE=http://127.0.0.1:8802 node doccompare-other.js
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const mk = (t, f, c) => page.evaluate(async ([t, f, c]) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) });
    return d.id;
  }, [t, f, c]);
  await mk("other.py", "py", "a = 1\nb = 2\nc = 3\n");
  const mine = await mk("mine.py", "py", "a = 1\nb = 5\nc = 3\nd = 4\n");
  await page.evaluate((id) => loadDocuments(id), mine);
  await page.waitForTimeout(1500);
  await page.evaluate(() => docCmView.focus());
  await page.evaluate(() => docIdeCompareMenu());
  await page.waitForTimeout(400);
  const _l = await page.evaluate(() => [...document.querySelectorAll('[role="menuitem"]')].map((e) => e.textContent.trim()));
  
  await page.evaluate(() => [...document.querySelectorAll('[role="menuitem"]')].find((e) => /Another document/.test(e.textContent)).click());
  await page.waitForTimeout(500);
  const _n = await page.evaluate(() => [...document.querySelectorAll('[role="menuitem"]')].map((e) => e.textContent.trim()));
  
  await page.evaluate(() => [...document.querySelectorAll('[role="menuitem"]')].find((e) => /other\.py/.test(e.textContent)).click());
  await page.waitForTimeout(1200);
  const n = await page.evaluate(() => ({ changed: document.querySelectorAll(".cm-changedLine, .cm-deletedChunk, .cm-insertedLine").length, toast: (document.querySelector(".toast, #toast") || {}).textContent }));
  console.log("compare", JSON.stringify(n));
  await browser.close();
})();
