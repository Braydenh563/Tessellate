// D47 (audit 1028): the textarea fallback is the safety net when the
// CodeMirror bundle cannot load, and nothing exercised it. This sweep blocks
// the bundle, opens two documents, types into the plain editor, and checks
// the save, the single warning and the single request (`docCmBroken`).
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

(async () => {
  const { browser, ctx, page } = await boot({ serviceWorkers: "block" });
  let bundleRequests = 0;
  await ctx.route("**/vendor/codemirror/codemirror.min.js*", (route) => {
    bundleRequests += 1;
    return route.abort("failed");
  });
  const warnings = [];
  page.on("console", (m) => {
    if (m.type() === "warning" && /editor bundle/.test(m.text())) warnings.push(m.text());
  });
  //: A fresh data dir asks about updates first; answer it so it cannot sit over the editor.
  await page.waitForTimeout(1500);
  const dontCheck = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  if (await dontCheck.count()) await dontCheck.first().click();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2200);
  const open = async (title, content) => {
    await page.evaluate(
      async ([t, c]) => {
        const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c }) });
        await loadDocuments(d.id);
      },
      [title, content]
    );
    await page.waitForTimeout(1800);
  };
  await open("Fallback one", "# One\n\nplain words");
  const first = await page.evaluate(() => {
    const el = document.getElementById("doc-content");
    const r = el && el.getBoundingClientRect();
    return { broken: docCmBroken, tag: el && el.tagName, w: r && Math.round(r.width), h: r && Math.round(r.height),
      value: el && el.value, cm: !!document.querySelector(".cm-editor") };
  });
  ok("the bundle failure is recorded", first.broken === true);
  ok("the editor is a visible textarea", first.tag === "TEXTAREA" && first.w > 200 && first.h > 100, `${first.w}x${first.h}`);
  ok("the document text is in it", /plain words/.test(first.value || ""));
  ok("no CodeMirror view mounted", !first.cm);
  await page.click("#doc-content");
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" and typed in the fallback");
  await page.waitForTimeout(2500);
  const saved = await page.evaluate(async () => {
    const list = await apiJson("/documents");
    const row = (list.documents || list).find((d) => d.title === "Fallback one");
    const full = await apiJson(`/documents/${row.id}`);
    return full.content;
  });
  ok("typing saves", /typed in the fallback/.test(saved), JSON.stringify(saved.slice(-40)));
  await open("Fallback two", "second document");
  const second = await page.evaluate(() => document.getElementById("doc-content").value);
  ok("a second document opens in the textarea", /second document/.test(second));
  ok("the bundle was asked for once", bundleRequests === 1, `requests ${bundleRequests}`);
  ok("one warning says why", warnings.length === 1, `warnings ${warnings.length}`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
