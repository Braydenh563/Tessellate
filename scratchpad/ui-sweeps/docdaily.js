// DOCUMENTS_PLAN Phase 4 item 5's daily notes, and the decision behind them
// (section 14, "what a document daily note is").
//
// The thing this guards is an agreement between two files that share no code:
// `DOC_TEMPLATES`'s daily row in documents.js titles a document with the ISO
// day, and `dailyNoteTitle` in app.js reads that same spelling to decide
// whether a day already has a page. Nothing fails loudly if the two drift; the
// day simply gets offered twice, which is the bug this item was built to end.
// So the probe writes a day as a document and then asks the Timeline what it
// thinks of it, rather than testing either half alone.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  — " + d}`);
};

(async () => {
  const { browser, page } = await boot();
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2200);

  const gallery = await page.evaluate(() => {
    const daily = DOC_TEMPLATES.find((t) => t.id === "daily");
    return {
      ids: DOC_TEMPLATES.map((t) => t.id),
      daily: daily ? { title: daily.title, docTitle: daily.docTitle, hint: daily.hint } : null,
      filled: daily ? docTemplateFill(daily) : null,
      wanted: dailyNoteTitle(timelineBucketKey(new Date(), "day")),
    };
  });
  console.log("      templates:", JSON.stringify(gallery.ids));
  ok("the gallery offers Daily", gallery.daily !== null, JSON.stringify(gallery.daily));
  ok(
    "and the document it makes is titled with the ISO day",
    gallery.filled && gallery.filled.title === gallery.wanted,
    `${gallery.filled && gallery.filled.title} vs ${gallery.wanted}`
  );
  //: The body has to carry the day too: the heading is what a reader sees and
  //: what an export, a search and another editor see.
  ok(
    "and its first line is that day",
    gallery.filled && gallery.filled.content.split("\n")[0].trim() === `# ${gallery.wanted}`,
    JSON.stringify(gallery.filled && gallery.filled.content.slice(0, 24))
  );
  ok(
    "a row says more than its name",
    gallery.daily && gallery.daily.hint.length > 24,
    gallery.daily && gallery.daily.hint
  );

  //: The gallery's own path, not a hand-built POST: the point is that pressing
  //: Daily leaves a document the Timeline recognises.
  const made = await page.evaluate(async () => {
    const before = Date.now();
    document.getElementById("doc-new-template").click();
    await new Promise((r) => setTimeout(r, 500));
    const button = document.querySelector('#doc-template-list [data-template="daily"]');
    if (!button) return { error: "no daily choice in the dialog" };
    //: A click chooses the row; Use this template makes it (INBOX 410).
    button.click();
    document.getElementById("doc-template-use").click();
    await new Promise((r) => setTimeout(r, 2200));
    return { title: document.getElementById("doc-title").value, ms: Date.now() - before };
  });
  console.log("      created:", JSON.stringify(made));
  ok("pressing Daily opens a document titled with the day", made.title === gallery.wanted, JSON.stringify(made));

  await page.evaluate(() => switchTab("timeline"));
  await page.waitForTimeout(3000);
  const timeline = await page.evaluate((wanted) => {
    const rows = [...document.querySelectorAll(".timeline-row")];
    const day = rows.find((r) => (r.dataset.key || "").startsWith("document:"));
    const labels = [...document.querySelectorAll("#timeline-scroll button")].map((b) =>
      b.textContent.trim().replace(/\s+/g, " ")
    );
    return {
      wanted,
      documentRows: rows.filter((r) => (r.dataset.key || "").startsWith("document:")).length,
      glyph: day ? (day.querySelector(".ph") || {}).className : null,
      startOffers: labels.filter((l) => /start today/i.test(l)),
      openOffers: labels.filter((l) => /today's (note|document)/i.test(l)),
    };
  }, gallery.wanted);
  console.log("      timeline:", JSON.stringify(timeline));
  //: The whole point of section 14: the day is begun, so the bucket offers to
  //: open it and never to start a second one.
  ok("the day bucket no longer offers to start a second page", timeline.startOffers.length === 0, JSON.stringify(timeline.startOffers));
  ok("it offers to open the one that exists", timeline.openOffers.length === 1, JSON.stringify(timeline.openOffers));
  ok(
    "and names the kind it found",
    timeline.openOffers.some((l) => /document/i.test(l)),
    JSON.stringify(timeline.openOffers)
  );
  ok(
    "the day's page carries the calendar glyph",
    (timeline.glyph || "").includes("ph-calendar-dot"),
    timeline.glyph
  );

  console.log(bad ? `${bad} FAILURES` : "all clear");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
