// Mermaid fences drawn by the vendored library in its own frame (BACKLOG,
// "Diagrams: mermaid as the interchange format", steps 8 and 12b).
//
// One document with a fence of each of ten kinds and one broken fence; in Read
// view the ten must be pictures (naturalWidth > 0) and the broken one the code
// block with a reason under it, with no console error and no CSP violation in
// the page or the frame. Then the theme switches and every picture is redrawn,
// the Live view draws the same, and a chat reply draws its fence.
//
// Usage: BASE=http://127.0.0.1:8786 [THEME=dark] node mermaid.js
const { boot } = require("./lib.js");

let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

const FENCES = {
  flowchart: "flowchart TD\n  A[Start] --> B{Ready?}\n  B -->|yes| C[Go]\n  B -->|no| D[Wait]\n  subgraph S[Group]\n    C --> E[Done]\n  end",
  sequence: "sequenceDiagram\n  Alice->>Bob: Hello\n  Bob-->>Alice: Hi back",
  class: "classDiagram\n  Animal <|-- Dog\n  Animal : +int age\n  Dog : +bark()",
  state: "stateDiagram-v2\n  [*] --> Idle\n  Idle --> Busy : start\n  Busy --> [*]",
  er: "erDiagram\n  CUSTOMER ||--o{ ORDER : places\n  ORDER ||--|{ LINE : contains",
  gantt: "gantt\n  title Plan\n  dateFormat YYYY-MM-DD\n  section A\n  Task one :a1, 2026-01-01, 5d\n  Task two :after a1, 3d",
  pie: 'pie title Pets\n  "Dogs" : 5\n  "Cats" : 3\n  "Fish" : 2',
  mindmap: "mindmap\n  root((Ideas))\n    Alpha\n    Beta\n      Gamma",
  timeline: "timeline\n  title History\n  2020 : Start\n  2021 : Grow\n  2022 : Ship",
  journey: "journey\n  title My day\n  section Work\n    Write code: 5: Me\n    Review: 3: Me, Team",
  broken: "flowchart TD\n  A --> \n  B[[[ oops",
};

(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(`pageerror ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error" || /Content Security Policy|Refused to/i.test(m.text())) errors.push(`${m.type()} ${m.text().slice(0, 200)}`);
  });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);

  const content = Object.entries(FENCES)
    .map(([kind, src]) => `## ${kind}\n\n\`\`\`mermaid\n${src}\n\`\`\`\n`)
    .join("\n");
  await page.evaluate(async (c) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Diagrams", content: c, file_type: "md" }) });
    await loadDocuments(d.id);
  }, content);
  await page.waitForTimeout(1500);
  await page.evaluate(() => setDocView("rendered"));

  const t0 = Date.now();
  await page.waitForFunction(() => document.querySelectorAll("#doc-preview figure.md-mermaid img").length >= 9, null, { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(2500);
  const first = Date.now() - t0;

  const read = () =>
    page.evaluate(() => {
      const root = document.getElementById("doc-preview");
      const imgs = [...root.querySelectorAll("figure.md-mermaid img")];
      return {
        figures: root.querySelectorAll("figure.md-mermaid").length,
        pending: root.querySelectorAll(".md-mermaid-pending").length,
        imgs: imgs.length,
        sized: imgs.filter((i) => i.naturalWidth > 0 && i.naturalHeight > 0).length,
        widths: imgs.map((i) => i.naturalWidth),
        alts: imgs.map((i) => i.alt),
        codeBlocks: root.querySelectorAll('.code-block code[data-lang="mermaid"]').length,
        reasons: [...root.querySelectorAll(".md-mermaid-reason")].map((r) => r.textContent),
        frames: document.querySelectorAll("iframe.mermaid-frame").length,
        theme: document.documentElement.dataset.theme || "(system)",
        keys: imgs.map((i) => i.parentElement.mermaidKey && i.parentElement.mermaidKey.length),
      };
    });
  const a = await read();
  console.log(JSON.stringify({ theme: a.theme, firstDrawMs: first, ...a, keys: undefined }));
  ok("ten kinds drawn as images", a.imgs === 10, `${a.imgs} images`);
  ok("every image has a size", a.sized === a.imgs, `${a.sized}/${a.imgs} naturalWidth > 0`);
  ok("the broken fence is a code block with one reason", a.codeBlocks === 1 && a.reasons.length === 1, JSON.stringify(a.reasons));
  ok("nothing left pending", a.pending === 0);
  ok("one frame only", a.frames === 1);

  // Theme switch: the same pictures are redrawn in the other theme.
  const darkNow = a.theme === "dark";
  const imgSrcBefore = await page.evaluate(() => [...document.querySelectorAll("#doc-preview figure.md-mermaid img")].map((i) => i.src));
  const keyBefore = await page.evaluate(() => document.querySelector("#doc-preview figure.md-mermaid").mermaidKey);
  await page.evaluate((to) => applyThemeChoice(to), darkNow ? "light" : "dark");
  await page.waitForTimeout(6000);
  const b = await read();
  const keyAfter = await page.evaluate(() => document.querySelector("#doc-preview figure.md-mermaid").mermaidKey);
  const imgSrcAfter = await page.evaluate(() => [...document.querySelectorAll("#doc-preview figure.md-mermaid img")].map((i) => i.src));
  console.log(JSON.stringify({ afterSwitch: b.theme, imgs: b.imgs, sized: b.sized }));
  ok("theme switch redraws every picture", keyBefore !== keyAfter && imgSrcBefore.every((s, i) => s !== imgSrcAfter[i]), `${imgSrcAfter.filter((s, i) => s !== imgSrcBefore[i]).length}/${imgSrcAfter.length} new`);
  ok("after the switch all still sized", b.sized === b.imgs && b.imgs === a.imgs);

  // High contrast redraws too (the key carries the strong ink and borders).
  const keyBeforeContrast = await page.evaluate(() => document.querySelector("#doc-preview figure.md-mermaid").mermaidKey);
  await page.evaluate(() => applyContrast(true));
  await page.waitForTimeout(6000);
  const keyAfterContrast = await page.evaluate(() => document.querySelector("#doc-preview figure.md-mermaid").mermaidKey);
  ok("high contrast redraws", keyBeforeContrast !== keyAfterContrast);
  await page.evaluate(() => applyContrast(false));
  await page.waitForTimeout(3000);

  // The HTML export carries each picture as a data: URL of its own SVG, and a
  // print shows them at their size.
  const exported = await page.evaluate(() => {
    const live = document.getElementById("doc-preview");
    const clone = live.cloneNode(true);
    mermaidInlineForExport(live, clone);
    const imgs = [...clone.querySelectorAll(".md-mermaid img")];
    return {
      imgs: imgs.length,
      data: imgs.filter((i) => i.getAttribute("src").startsWith("data:image/svg+xml")).length,
      svgs: imgs.filter((i) => decodeURIComponent(i.getAttribute("src").split(",")[1]).startsWith("<svg")).length,
    };
  });
  ok("HTML export inlines every picture as a data URL", exported.imgs === 10 && exported.data === 10 && exported.svgs === 10, JSON.stringify(exported));
  await page.emulateMedia({ media: "print" });
  const printed = await page.evaluate(() => {
    const imgs = [...document.querySelectorAll("#doc-preview figure.md-mermaid img")];
    return { shown: imgs.filter((i) => i.getBoundingClientRect().width > 0 && getComputedStyle(i).display !== "none").length, total: imgs.length };
  });
  await page.emulateMedia({ media: "screen" });
  ok("print media shows every picture", printed.shown === 10 && printed.total === 10, JSON.stringify(printed));

  // Live: a short document (CodeMirror draws only what is on screen).
  await page.evaluate(async () => {
    const live = "Text\n\n```mermaid\npie title X\n  \"a\" : 1\n  \"b\" : 2\n```\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n```mermaid\nflowchart TD\n  A --> \n  B[[[ oops\n```\n\nEnd\n";
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Live", content: live, file_type: "md" }) });
    await loadDocuments(d.id);
  });
  await page.waitForTimeout(1500);
  await page.evaluate(() => setDocView("live"));
  await page.waitForTimeout(6000);
  const live = await page.evaluate(() => {
    const root = document.getElementById("doc-editor");
    const imgs = [...root.querySelectorAll("figure.md-mermaid img")];
    return {
      imgs: imgs.length,
      sized: imgs.filter((i) => i.naturalWidth > 0).length,
      pending: root.querySelectorAll(".md-mermaid-pending").length,
      reasons: [...root.querySelectorAll(".md-mermaid-reason")].length,
    };
  });
  console.log(JSON.stringify({ live }));
  ok("Live draws the pictures", live.imgs === 2 && live.sized === 2 && live.pending === 0, JSON.stringify(live));
  ok("Live leaves the broken fence as code with its reason", live.reasons === 1);

  // Chat / Ask: renderMarkdown into a detached-then-attached holder.
  const chat = await page.evaluate(async () => {
    const holder = document.createElement("div");
    document.body.appendChild(holder);
    renderMarkdown(holder, "Here:\n\n```mermaid\npie title X\n  \"a\" : 1\n  \"b\" : 2\n```\n\nand\n\n```mermaid\nnot a diagram at all\n```\n");
    await new Promise((r) => setTimeout(r, 5000));
    const out = {
      imgs: holder.querySelectorAll("figure.md-mermaid img").length,
      sized: [...holder.querySelectorAll("img")].filter((i) => i.naturalWidth > 0).length,
      code: holder.querySelectorAll('.code-block code[data-lang="mermaid"]').length,
      reasons: holder.querySelectorAll(".md-mermaid-reason").length,
    };
    holder.remove();
    return out;
  });
  console.log(JSON.stringify({ chat }));
  ok("chat reply draws its fence and keeps a bad one as code", chat.imgs === 1 && chat.sized === 1 && chat.code === 1 && chat.reasons === 1, JSON.stringify(chat));

  // The boot never loaded the library.
  const loaded = await page.evaluate(() => performance.getEntriesByType("resource").map((r) => r.name).filter((n) => /mermaid/.test(n)));
  console.log(JSON.stringify({ mermaidResources: loaded.map((n) => n.replace(/^https?:\/\/[^/]+/, "")) }));

  ok("no console errors or CSP violations", errors.length === 0, errors.slice(0, 4).join(" | "));
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
