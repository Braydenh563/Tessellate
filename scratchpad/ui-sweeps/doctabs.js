// D52 (audit 1028): the code editor's open files as a tab strip
// (documents-tabs.js). Opens three code files and a prose one, and measures
// when the strip shows, what a click, the Close button and a middle-click do,
// and the strip's box at desktop and phone widths.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

(async () => {
  const width = Number(process.env.W) || 1440;
  const { browser, page } = await boot({ viewport: { width, height: 900 } });
  //: A fresh data dir asks about updates first (any time in the first seconds): answer it.
  const dismiss = async () => {
    const no = page.locator(".confirm-overlay button", { hasText: "Don't check" });
    if (await no.count()) await no.first().click();
  };
  await page.waitForTimeout(2500);
  await dismiss();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2200);
  const ids = await page.evaluate(async () => {
    localStorage.removeItem("doc-tabs");
    const make = async (title, file_type, content) =>
      (await apiJson("/documents", { method: "POST", body: JSON.stringify({ title, content, file_type }) })).id;
    return {
      a: await make("alpha.py", "py", "print('a')\n"),
      b: await make("beta.js", "js", "console.log('b')\n"),
      c: await make("a-very-long-file-name-that-should-be-cut-with-an-ellipsis.css", "css", "a { color: red }\n"),
      p: await make("Prose note", "md", "# prose\n"),
    };
  });
  await page.evaluate(() => loadDocuments());
  const open = async (id) => {
    await dismiss();
    await page.evaluate((i) => openDocument(i), id);
    await page.waitForTimeout(1500);
  };
  const state = () =>
    page.evaluate(() => {
      const row = document.getElementById("doc-tabs-row");
      const tabs = [...document.querySelectorAll("#doc-tabs .doc-tab")];
      const r = row.getBoundingClientRect();
      return {
        hidden: row.classList.contains("hidden"),
        labels: tabs.map((t) => t.textContent),
        selected: tabs.filter((t) => t.getAttribute("aria-selected") === "true").map((t) => t.textContent),
        cur: currentDoc && currentDoc.id,
        h: Math.round(r.height),
        w: Math.round(r.width),
        stripScroll: document.getElementById("doc-tabs").scrollWidth,
        stripClient: document.getElementById("doc-tabs").clientWidth,
        pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        tabW: tabs.map((t) => Math.round(t.getBoundingClientRect().width)),
        tabH: tabs.map((t) => Math.round(t.getBoundingClientRect().height)),
      };
    });

  await open(ids.a);
  let s = await state();
  ok("one code file: no strip", s.hidden && s.labels.length === 0, JSON.stringify(s.labels));
  await open(ids.b);
  s = await state();
  ok("two code files: strip shows both", !s.hidden && s.labels.join("|") === "alpha.py|beta.js", s.labels.join("|"));
  ok("the open file is the selected tab", s.selected.join() === "beta.js");
  await open(ids.c);
  s = await state();
  ok("three tabs in the order opened", s.labels.length === 3 && s.labels[2].startsWith("a-very-long"));
  console.log(`  strip ${s.w}x${s.h}, tab widths ${s.tabW}, tab heights ${s.tabH}, strip scroll ${s.stripScroll}/${s.stripClient}, page overflow ${s.pageOverflow}`);
  ok("a long name is cut at 14rem (224px)", Math.max(...s.tabW) <= 226);
  ok("no horizontal page overflow", s.pageOverflow <= 0);
  await dismiss();
  await page.click('#doc-tabs .doc-tab:has-text("alpha.py")');
  await page.waitForTimeout(1500);
  s = await state();
  ok("a click opens that file and keeps the order", s.cur === ids.a && s.labels[0] === "alpha.py" && s.selected.join() === "alpha.py", s.labels.join("|"));
  await page.keyboard.press("Tab");
  await page.focus('#doc-tabs .doc-tab[aria-selected="true"]');
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(1500);
  s = await state();
  ok("ArrowRight opens the next tab", s.cur === ids.b, String(s.cur));
  await page.click("#doc-tab-end");
  await page.waitForTimeout(1500);
  s = await state();
  ok("Close file drops the open tab and opens its neighbour", s.labels.length === 2 && s.cur === ids.a && !s.labels.includes("beta.js"), `${s.labels.join("|")} cur ${s.cur}`);
  await page.click('#doc-tabs .doc-tab:has-text("a-very-long")', { button: "middle" });
  await page.waitForTimeout(800);
  s = await state();
  ok("middle-click closes another tab; one left hides the strip", s.hidden && s.cur === ids.a, `${s.labels.join("|")} hidden ${s.hidden}`);
  await open(ids.b);
  await open(ids.p);
  s = await state();
  ok("a prose document hides the strip", s.hidden);
  await open(ids.b);
  s = await state();
  ok("back on a code file the strip returns with its tabs", !s.hidden && s.labels.length === 2, s.labels.join("|"));
  await page.evaluate(() => $("doc-back").click());
  await page.waitForTimeout(800);
  s = await state();
  const shownOnList = await page.evaluate(() => document.getElementById("doc-tabs-row").offsetParent !== null);
  ok("the Library list does not show the strip", !shownOnList);
  await page.evaluate(async (id) => apiJson(`/documents/${id}`, { method: "DELETE" }), ids.b);
  await page.evaluate(() => loadDocuments());
  await page.waitForTimeout(1200);
  await open(ids.c);
  s = await state();
  ok("a deleted file leaves the strip", !s.labels.includes("beta.js"), s.labels.join("|"));
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
