// INBOX 401: Harper's cost, measured before it was wired, and the wiring.
// Cold: worker start to first lint (fetch + compile + dictionary). Warm: a
// lint of a ~1,400-word document, median of five. Boot: whether anything of
// Harper is requested before a prose document is opened. Then the document
// (underline, panel group, a fix through the word menu) and a note box.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  : " + d}`); };
const SAMPLE = "Their is a problem with this sentence. He go to the store yesterday. " +
  "I has an apple and a orange. The the cat sat on the mat. This is a test of an grammar checker. ";
(async () => {
  const { browser, page } = await boot();
  const requested = [];
  page.on("request", (r) => { if (/harper/.test(r.url())) requested.push(r.url()); });
  await page.waitForTimeout(1500);
  ok("nothing of Harper is fetched at boot", requested.length === 0, requested.join(", ") || "none");
  const out = await page.evaluate(async (sample) => {
    const w = new Worker("/js/harper-worker.js", { type: "module" });
    let n = 0;
    const ask = (text) => new Promise((res) => {
      const id = ++n;
      const on = (e) => { if (e.data.id === id) { w.removeEventListener("message", on); res(e.data); } };
      w.addEventListener("message", on);
      w.postMessage({ id, text, dialect: "us" });
    });
    const t0 = performance.now();
    const first = await ask(sample);
    const cold = performance.now() - t0;
    const long = Array(40).fill(sample).join("\n\n");
    const times = [];
    let last;
    for (let i = 0; i < 5; i++) {
      const t = performance.now();
      last = await ask(long + " " + i);
      times.push(performance.now() - t);
    }
    times.sort((a, b) => a - b);
    const emoji = await ask("\u{1F600} I has a apple.");
    w.terminate();
    return { ok: first.ok, error: first.error, cold: Math.round(cold), firstLints: first.lints && first.lints.map((l) => `${l.kind}:${l.problem}`),
      words: long.split(/\s+/).length, warm: Math.round(times[2]), longLints: last.lints && last.lints.length,
      emoji: emoji.lints.map((l) => [l.start, l.end, l.problem]) };
  }, SAMPLE);
  console.log("      first lints:", JSON.stringify(out.firstLints));
  ok("the binary loads under the app's CSP", out.ok === true, out.error || "ok");
  ok("first lint arrives", out.cold > 0, `${out.cold} ms cold`);
  ok("warm lint of a long document under 300ms, in the worker", out.warm < 300, `${out.warm} ms for ${out.words} words`);
  const e0 = out.emoji.find((x) => x[2] === "has");
  ok("offsets are UTF-16 after an emoji", e0 && e0[0] === 5, JSON.stringify(out.emoji));

  // The document.
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  await page.evaluate(async (sample) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Grammar probe", content: "# Grammar\n\n" + sample + "\n" }) });
    await loadDocuments(d.id);
    setDocView("live");
  }, SAMPLE);
  await page.waitForTimeout(4000);
  const doc = await page.evaluate(() => ({
    marks: [...document.querySelectorAll(".cm-finding-grammar")].map((m) => m.textContent),
    found: docProseFound.filter((f) => f.rule === "grammar").map((f) => `${f.harperKind}:${f.text}`),
    deco: getComputedStyle(document.querySelector(".cm-finding-grammar") || document.body).textDecorationStyle,
    spellingFromHarper: docProseFound.some((f) => f.rule === "grammar" && f.harperKind === "Spelling"),
    doubled: docProseFound.filter((f) => f.text.toLowerCase() === "the the").length,
  }));
  console.log("      doc:", JSON.stringify(doc));
  ok("grammar underlines drawn in the document", doc.marks.length >= 3, doc.marks.join(", "));
  ok("the grammar underline is a double line", doc.deco === "double", doc.deco);
  ok("Harper's spelling kind is not taken", !doc.spellingFromHarper);
  ok("a span the repeat rule holds is not claimed twice", doc.doubled <= 1, String(doc.doubled));

  // The panel group.
  await page.click("#doc-prose");
  await page.waitForTimeout(400);
  const groups = await page.evaluate(() => [...document.querySelectorAll("#doc-prose-panel .doc-prose-group")].map((g) => g.textContent));
  ok("the panel files them under Grammar", groups.some((g) => /^Grammar\d+$/.test(g)), groups.join(" | "));
  await page.click("#doc-prose-panel .doc-prose-close");

  // A fix through the word's own menu.
  const target = await page.evaluate(() => {
    const m = [...document.querySelectorAll(".cm-finding-grammar")].find((x) => x.textContent === "has");
    if (!m) return null;
    const r = m.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (target) {
    await page.mouse.click(target.x, target.y);
    await page.waitForTimeout(500);
    const menu = await page.evaluate(() => [...document.querySelectorAll("#doc-suggest-menu:not(.hidden) .doc-suggest-list .doc-suggest-item")].map((b) => b.textContent));
    ok("the word menu offers Harper's answer", menu.includes("have"), menu.join(", "));
    await page.evaluate(() => [...document.querySelectorAll("#doc-suggest-menu .doc-suggest-item")].find((b) => b.textContent === "have")?.click());
    await page.waitForTimeout(400);
    const fixed = await page.evaluate(() => docText().includes("I have an apple"));
    ok("choosing it rewrites the sentence", fixed);
  } else ok("found the 'has' underline to press", false);

  // Main-thread cost of merging per pass, on a long document.
  const merge = await page.evaluate(async (sample) => {
    const long = "# Long\n\n" + Array(40).fill(sample).join("\n\n");
    docSurface().value = long;
    await new Promise((r) => setTimeout(r, 3000));
    const t = performance.now();
    for (let i = 0; i < 10; i++) renderDocProse();
    return { ms: (performance.now() - t) / 10, grammar: docProseFound.filter((f) => f.rule === "grammar").length };
  }, SAMPLE);
  ok("a prose pass with grammar merged stays under 50ms", merge.ms < 50, `${merge.ms.toFixed(1)} ms, ${merge.grammar} grammar findings`);

  // A note box.
  await page.evaluate(() => { switchTab("notes"); showNotesSection("capture"); });
  await page.waitForTimeout(1500);
  await page.click("#entry-content").catch(() => {});
  await page.waitForTimeout(800);
  await page.keyboard.type("She go to school and I has a apple.");
  await page.waitForTimeout(2500);
  console.log("      note box:", JSON.stringify(await page.evaluate(() => ({
    surfaces: document.querySelectorAll(".note-surface").length,
    value: document.getElementById("entry-content")?.value,
    active: document.activeElement && (document.activeElement.id || document.activeElement.className),
    visible: !!document.getElementById("entry-content")?.getClientRects().length,
  }))));
  const note = await page.evaluate(() => [...document.querySelectorAll(".note-surface .cm-finding-grammar")].map((m) => m.textContent));
  ok("a note box underlines grammar too", note.length >= 2, note.join(", "));
  const spot = await page.evaluate(() => {
    const m = [...document.querySelectorAll(".note-surface .cm-finding-grammar")].find((x) => x.textContent === "go");
    if (!m) return null;
    const r = m.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (spot) {
    await page.mouse.click(spot.x, spot.y);
    await page.waitForTimeout(400);
    const rows = await page.evaluate(() => [...document.querySelectorAll('[role="menuitem"]')].filter((r) => r.getClientRects().length).map((r) => r.textContent.trim()).filter(Boolean));
    ok("its menu offers the fix", rows.includes("goes"), rows.join(", "));
    await page.evaluate(() => [...document.querySelectorAll('[role="menuitem"]')].filter((r) => r.getClientRects().length).find((r) => r.textContent.trim() === "goes")?.click());
    await page.waitForTimeout(300);
    const value = await page.evaluate(() => document.getElementById("entry-content").value);
    ok("choosing it rewrites the note", value.startsWith("She goes to school"), value);
  } else ok("found the 'go' underline in the note", false);
  await page.evaluate(() => { const b = document.getElementById("entry-content"); b.value = ""; b.dispatchEvent(new Event("input", { bubbles: true })); });

  console.log(bad ? `${bad} FAILED` : "all passed");
  await browser.close();
})();
