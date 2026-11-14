// L-documents-88: every chart-kind template draws (mermaid parses and renders it) and opens as blocks.
//   BASE=http://127.0.0.1:8858 node scratchpad/ui-sweeps/diagram-templates-kinds.js
const os = require("os");
process.env.BASE ||= "http://127.0.0.1:8858";
process.env.SCRATCH ||= os.tmpdir();
const { boot } = require("./lib.js");
(async () => {
  const { page } = await boot(1440);
  const rows = await page.evaluate(async () => (await (await fetch("/board-library/diagram-templates.json")).json()).templates.filter((t) => ["gantt", "pie", "state", "class", "er"].includes(t.kind)));
  for (const t of rows) {
    await page.evaluate(async (t) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: `tpl ${t.id}`, content: t.source, file_type: "mmd" }) });
      switchTab("documents");
      await openDocument((await r.json()).id);
    }, t);
    await page.waitForSelector(".dgm-pane", { timeout: 15000 });
    await page.waitForTimeout(1500);
    const got = await page.evaluate(() => ({ blocks: document.querySelectorAll(".dgm-block").length, picture: document.querySelector(".dgm-picture img")?.naturalWidth || 0, err: document.querySelector(".dgm-error, .md-mermaid-error")?.textContent || "" }));
    console.log(t.id, JSON.stringify(got));
  }
  process.exit(0);
})();
