// L-documents-86: the Ask box and Suggestions on the five chart kinds, answered by rule (no model).
//   BASE=http://127.0.0.1:8858 node scratchpad/ui-sweeps/diagram-ask-kinds.js [width]
const os = require("os");
process.env.BASE ||= "http://127.0.0.1:8858";
process.env.SCRATCH ||= os.tmpdir();
const { boot } = require("./lib.js");
const CASES = {
  gantt: ["gantt\n    title Plan\n    section Build\n    Code :a1, 2026-01-05, 5d\n", "add task Test under Build"],
  pie: ['pie title Pets\n    "Dogs" : 40\n    "Cats" : 25\n', "add slice Birds 30"],
  state: ["stateDiagram-v2\n    state Idle\n    state Busy\n", "add transition from Idle to Busy called go"],
  class: ["classDiagram\n    class Order\n    class Customer\n", "add relation from Order to Customer"],
  er: ["erDiagram\n    ORDER\n    CUSTOMER\n", "add relationship from CUSTOMER to ORDER called places"],
};
(async () => {
  const { page } = await boot(Number(process.argv[2] || 1440));
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  for (const [kind, [src, ask]] of Object.entries(CASES)) {
    await page.evaluate(async ([t, c]) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: "mmd" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
    }, [`ask ${kind}`, src]);
    await page.waitForSelector(".dgm-ai-form", { timeout: 15000 });
    await page.waitForTimeout(500);
    await page.fill(".dgm-ai-form input", ask);
    await page.keyboard.press("Enter");
    await page.waitForSelector(".dgm-ai-preview:not(.hidden)", { timeout: 10000 }).catch(() => {});
    const preview = await page.evaluate(() => [...document.querySelectorAll(".dgm-ai-changes li")].map((l) => l.textContent));
    const said = await page.evaluate(() => document.querySelector(".dgm-ai-said")?.textContent);
    await page.click(".dgm-ai-foot button:has-text('Apply')").catch(() => {});
    await page.waitForTimeout(500);
    const text = await page.evaluate(() => docText());
    const lint = await page.evaluate(() => document.querySelector(".dgm-ai-lints-words")?.textContent);
    console.log(kind, JSON.stringify({ preview, said, text, lint }));
  }
  console.log("errors", JSON.stringify(errs));
  process.exit(0);
})();
