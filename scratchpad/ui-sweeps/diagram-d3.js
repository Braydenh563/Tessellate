// D3 and the 120-block switch: a kind the blocks do not draw (and a flowchart over 120 blocks) opens
// with its picture and one line, in Split on a document and in Source in the dialog.
process.env.BASE ||= "http://127.0.0.1:8781";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
const W = Number(process.argv[2] || 1440);
const SRC = {
  state: "stateDiagram-v2\n  [*] --> Still\n  Still --> Moving\n  Moving --> [*]\n",
  class: "classDiagram\n  Animal <|-- Duck\n  Animal : +int age\n",
  pie: 'pie title Pets\n  "Dogs" : 386\n  "Cats" : 85\n',
  gantt: "gantt\n  title Plan\n  dateFormat YYYY-MM-DD\n  section A\n  Task one :a1, 2026-01-01, 5d\n",
  journey: "journey\n  title Day\n  section Work\n    Make tea: 5: Me\n",
  er: "erDiagram\n  CUSTOMER ||--o{ ORDER : places\n",
  c4: 'C4Context\n  title Context\n  Person(a, "User")\n  System(b, "App")\n  Rel(a, b, "Uses")\n',
  big: "flowchart TD\n" + Array.from({ length: 130 }, (_, i) => `  N${i}["Step ${i}"]`).join("\n") + "\n" + Array.from({ length: 129 }, (_, i) => `  N${i} --> N${i + 1}`).join("\n") + "\n",
};
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: 900 }, ...(W < 600 ? { hasTouch: true, isMobile: true } : {}) });
  const rows = {};
  for (const [name, src] of Object.entries(SRC)) {
    await page.evaluate(async ([n, c]) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: `D3 ${n} ${Date.now()}`, content: c, file_type: "mmd" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
    }, [name, src]);
    await page.waitForSelector(".dgm", { timeout: 15000 });
    await page.waitForFunction(() => document.querySelector("#doc-preview .dgm-picture img")?.naturalWidth > 0, null, { timeout: 20000 }).catch(() => {});
    await page.waitForTimeout(500);
    rows[name] = await page.evaluate(() => {
      const note = document.querySelector("#doc-preview .dgm-hint:not(.hidden)");
      const img = document.querySelector("#doc-preview .dgm-picture img");
      const pane = document.querySelector("#doc-preview .dgm-pane");
      const ed = document.querySelector("#doc-editor, .doc-source, #doc-source");
      return { view: document.querySelector("#doc-panes")?.className || "", note: note?.textContent || "", pic: img ? [img.naturalWidth, Math.round(img.getBoundingClientRect().width)] : null, pane: pane ? getComputedStyle(pane).display : "none", editor: ed ? Math.round(ed.getBoundingClientRect().width) : null, fits: document.documentElement.scrollWidth <= innerWidth };
    });
  }
  console.log(JSON.stringify(rows, null, 1));
  // the dialog, from a Live figure, on the big one and on a state diagram
  for (const name of ["state", "big"]) {
    await page.evaluate(async ([c]) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "D3 live " + Date.now(), content: "Intro\n\n```mermaid\n" + c + "```\n" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
      setDocView("live", { persist: false });
    }, [SRC[name]]);
    await page.waitForSelector(".md-mermaid-edit", { timeout: 20000 });
    await page.waitForTimeout(1200);
    await page.click(".md-mermaid-edit");
    await page.waitForSelector(".dgm-dialog .dgm-source", { timeout: 15000 });
    await page.waitForTimeout(1500);
    console.log("dialog", name, JSON.stringify(await page.evaluate(() => {
      const d = document.querySelector(".dgm-dialog");
      const src = d.querySelector(".dgm-source");
      const img = d.querySelector(".dgm-picture img");
      return { view: d.dataset.view, note: d.querySelector(".dgm-hint:not(.hidden)")?.textContent || "", srcW: Math.round(src.getBoundingClientRect().width), pic: img ? [img.naturalWidth, Math.round(img.getBoundingClientRect().width)] : null, blocksDisabled: d.querySelector('[data-view="blocks"]').disabled };
    })));
    await page.screenshot({ path: process.env.SCRATCH + `/p3-${name}-${W}.png` });
    await page.click('.dgm-dialog button:text-is("Cancel")');
    await page.waitForTimeout(400);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
