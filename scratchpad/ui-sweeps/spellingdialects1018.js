// VC6 (DOCUMENTS_PLAN, Brief 75): five spelling dialects. Picks each one in
// the writing panel's select, then reads the editor's own findings and
// Harper's through the real worker on one fixed sentence.
//
// Usage: BASE=http://127.0.0.1:8792 [THEME=dark] node spellingdialects1018.js
const { boot } = require("./lib.js");

let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};
const TEXT = "The colour of the centre, the color of the center: we organise and organize it.\n";

(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  await page.evaluate(async (text) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Dialects", content: text, file_type: "md" }) });
    await loadDocuments(d.id);
  }, TEXT);
  await page.waitForTimeout(1500);
  await page.evaluate(() => $("doc-dictionary-dialog")?.showModal());
  await page.waitForTimeout(300);
  const options = await page.evaluate(() => [...document.querySelectorAll("#doc-spelling-variant option")].map((o) => o.value));
  ok("select lists off and the five dialects", JSON.stringify(options) === JSON.stringify(["off", "uk", "us", "au", "ca", "in"]), options.join());
  const want = {
    us: ["colour", "centre", "organise"],
    uk: ["color", "center", "organize"],
    au: ["color", "center", "organize"],
    ca: ["color", "center", "organise"],
    in: ["color", "center", "organize"],
  };
  for (const [value, flagged] of Object.entries(want)) {
    await page.selectOption("#doc-spelling-variant", value);
    await page.waitForTimeout(400);
    const saved = await page.evaluate(async () => (await apiJson("/preferences")).spelling_variant);
    const got = await page.evaluate((text) => {
      const own = docProseFindings(text).filter((f) => f.rule === "variant");
      return { words: own.map((f) => f.text.toLowerCase()).sort(), message: own[0] && own[0].message };
    }, TEXT);
    const harper = await page.evaluate(
      (text) =>
        new Promise((resolve) => {
          const w = new Worker(lazyAssetStamp ? `/js/harper-worker.js${lazyAssetStamp("/js/harper-worker.js")}` : "/js/harper-worker.js", { type: "module" });
          w.onmessage = (e) => resolve((e.data.lints || []).map((l) => l.problem.toLowerCase()).sort());
          w.postMessage({ id: 1, text, dialect: document.getElementById("doc-spelling-variant").value });
        }),
      TEXT
    );
    ok(`${value}: saved, own findings are ${flagged.join(", ")}`, saved === value && JSON.stringify(got.words) === JSON.stringify([...flagged].sort()), JSON.stringify(got));
    //: Harper accepts -ize in British, Australian and Indian (Oxford spelling), so
    //: it flags the -our and -re forms only; the editor's own table is stricter.
    const harperWant = flagged.filter((w) => !(["uk", "au", "in"].includes(value) && w === "organize"));
    const spellings = harper.filter((w) => ["colour", "color", "centre", "center", "organise", "organize"].includes(w));
    ok(`${value}: Harper flags ${harperWant.join(", ")}`, JSON.stringify(spellings) === JSON.stringify([...harperWant].sort()), harper.join());
  }
  await page.selectOption("#doc-spelling-variant", "off");
  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
