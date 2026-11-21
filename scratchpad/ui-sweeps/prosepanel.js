// The suggestions panel answers in place (DOCUMENTS_PLAN 12 D3): pressing a row
// opens no floating surface, the answers appear inside the panel, the word is
// scrolled into the middle of the editor, and only one row is ever open.
//
// Reported: "when I click on the issue from the suggestions thing, the box just
// appears right there in my face."
const { boot } = require("./lib.js");

const FILL = "The quick brown fox jumped over the lazy dog and then went home again. ";
const CONTENT = [
  "Writing probe",
  "",
  "A short line with teh first typo in it, and recieve as well.",
  "",
  `A wrapped line: ${FILL}${FILL}with the the doubled pair in it ${FILL}`,
  "",
  ...Array.from({ length: 30 }, (_, i) => `Filler paragraph ${i + 1}. ${FILL}`),
  "",
  "The last line ends with definately and seperate.",
].join("\n");

(async () => {
  const { page, browser } = await boot({});
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 140)); });
  await page.click('[data-tab="library"]').catch(() => {});
  await page.waitForTimeout(900);
  console.log("seeded: " + await page.evaluate(async (content) => {
    const r = await fetch("/documents", {
      method: "POST",
      headers: { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Panel probe", content }),
    });
    const doc = await r.json();
    switchTab("documents");
    await new Promise((res) => setTimeout(res, 400));
    await openDocument(doc.id);
    await new Promise((res) => setTimeout(res, 2500));
    document.querySelector("[aria-controls='doc-prose-panel']")?.click();
    await new Promise((res) => setTimeout(res, 600));
    return JSON.stringify({ findings: docProseFound.length });
  }, CONTENT));

  const fails = [];
  const shares = await page.evaluate(() => {
    const panel = document.getElementById("doc-prose-panel");
    const editor = document.querySelector(".cm-editor");
    const pr = panel.getBoundingClientRect(), er = editor.getBoundingClientRect();
    return {
      panel: { h: Math.round(pr.height), pct: Math.round((pr.height / innerHeight) * 100) },
      editor: { h: Math.round(er.height), pct: Math.round((er.height / innerHeight) * 100) },
    };
  });
  console.log("shares (panel closed rows): " + JSON.stringify(shares));

  // Press the last row, the one whose word needs a scroll to reach.
  const pressed = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll("#doc-prose-panel .doc-prose-jump")];
    const row = rows.find((r) => /definately/i.test(r.textContent)) || rows[rows.length - 1];
    row.click();
    await new Promise((r) => setTimeout(r, 900));
    const li = row.closest(".doc-prose-row");
    const answers = li.querySelector(".doc-prose-answers");
    const menu = document.getElementById("doc-suggest-menu");
    const ar = answers.getBoundingClientRect();
    const lr = li.getBoundingClientRect();
    const panel = document.getElementById("doc-prose-panel").getBoundingClientRect();
    const ed = document.querySelector(".cm-editor").getBoundingClientRect();
    const sel = document.querySelector(".cm-selectionBackground")?.getBoundingClientRect();
    return {
      floatingOpen: menu ? !menu.classList.contains("hidden") : false,
      expanded: row.getAttribute("aria-expanded"),
      current: li.getAttribute("aria-current"),
      answerRows: answers.querySelectorAll("button").length,
      answersHidden: answers.classList.contains("hidden"),
      answersH: Math.round(ar.height),
      rowH: Math.round(lr.height),
      rowInsidePanel: lr.top >= panel.top - 1 && lr.bottom <= panel.bottom + 1,
      panelH: Math.round(panel.height),
      panelPct: Math.round((panel.height / innerHeight) * 100),
      word: sel ? { top: Math.round(sel.top), bottom: Math.round(sel.bottom) } : null,
      editor: { top: Math.round(ed.top), bottom: Math.round(ed.bottom) },
      wordVisible: sel ? sel.top >= ed.top && sel.bottom <= ed.bottom : null,
      wordFromMiddle: sel ? Math.round(Math.abs((sel.top + sel.bottom) / 2 - (ed.top + ed.bottom) / 2)) : null,
      openRows: document.querySelectorAll('#doc-prose-panel .doc-prose-jump[aria-expanded="true"]').length,
    };
  });
  console.log("row pressed -> " + JSON.stringify(pressed));
  if (pressed.floatingOpen) fails.push("the floating menu opened from a panel row");
  if (pressed.expanded !== "true" || pressed.current !== "location") fails.push("the open row does not say so (aria-expanded/aria-current)");
  if (pressed.answersHidden || pressed.answerRows < 2) fails.push("no answers appeared in the row");
  if (!pressed.wordVisible) fails.push("the word is not visible in the editor");
  if (pressed.wordFromMiddle > 120) fails.push(`the word is ${pressed.wordFromMiddle}px off the middle of the editor`);
  if (!pressed.rowInsidePanel) fails.push("the open row is not inside the panel's own box");

  // A second row closes the first.
  const second = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll("#doc-prose-panel .doc-prose-jump")];
    rows[0].click();
    await new Promise((r) => setTimeout(r, 800));
    return {
      openRows: document.querySelectorAll('#doc-prose-panel .doc-prose-jump[aria-expanded="true"]').length,
      currentRows: document.querySelectorAll("#doc-prose-panel .doc-prose-row[aria-current]").length,
      floatingOpen: !document.getElementById("doc-suggest-menu").classList.contains("hidden"),
    };
  });
  console.log("second row -> " + JSON.stringify(second));
  if (second.openRows !== 1 || second.currentRows !== 1) fails.push(`${second.openRows} rows open at once`);
  if (second.floatingOpen) fails.push("the floating menu opened from the second row");

  // The same row again closes its answers.
  const again = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll("#doc-prose-panel .doc-prose-jump")];
    rows[0].click();
    await new Promise((r) => setTimeout(r, 600));
    return document.querySelectorAll('#doc-prose-panel .doc-prose-jump[aria-expanded="true"]').length;
  });
  console.log("same row again -> open rows: " + again);
  if (again !== 0) fails.push("pressing the open row again did not close it");

  // Applying the first candidate from inside the panel fixes the text.
  const fixed = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll("#doc-prose-panel .doc-prose-jump")];
    const row = rows.find((r) => /teh/i.test(r.textContent)) || rows[0];
    row.click();
    await new Promise((r) => setTimeout(r, 700));
    const before = docText();
    const best = row.closest(".doc-prose-row").querySelector(".doc-suggest-best");
    const word = best ? best.textContent : null;
    best?.click();
    await new Promise((r) => setTimeout(r, 900));
    return { word, changed: docText() !== before, hasTeh: /\bteh\b/.test(docText()) };
  });
  console.log("fix from the panel -> " + JSON.stringify(fixed));
  if (!fixed.changed) fails.push("pressing a candidate in the panel changed nothing");

  // The floating menu still belongs to the text. A row is kept open as well, so
  // the contrast pass below sees both row states and the menu at once.
  const fromText = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll("#doc-prose-panel .doc-prose-jump")];
    if (rows.length > 1) { rows[1].click(); await new Promise((r) => setTimeout(r, 600)); }
    const box = docSurface(); if (box) box.setSelection(0, 0);
    await new Promise((r) => setTimeout(r, 300));
    const el = [...document.querySelectorAll("[data-doc-finding]")][0];
    if (!el) return "no mark";
    const f = [...el.getClientRects()][0];
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: f.left + f.width / 2, clientY: f.top + f.height / 2 }));
    await new Promise((r) => setTimeout(r, 700));
    const menu = document.getElementById("doc-suggest-menu");
    const m = menu.getBoundingClientRect();
    return JSON.stringify({
      open: !menu.classList.contains("hidden"),
      rows: menu.querySelectorAll("button").length,
      h: Math.round(m.height), w: Math.round(m.width),
      gapX: Math.max(0, Math.round(f.left - m.right), Math.round(m.left - f.right)),
      gapY: Math.max(0, Math.round(f.top - m.bottom), Math.round(m.top - f.bottom)),
    });
  });
  console.log("click the underline -> " + fromText);

  // Contrast on the new text, from the painted pixels rather than from a walk
  // up the tree. These surfaces are translucent over a gradient, and compositing
  // them by hand bottoms out on `body`, which is not what is painted: measured
  // that way the app's own `.doc-hint` reads 2.24:1, which would be a
  // catastrophe nobody has ever seen. So the background is sampled from a real
  // screenshot (scratchpad/pngpixel.py) at a point inside each surface where no
  // glyph sits, and the text colour comes from `getComputedStyle`.
  const theme = process.env.THEME || "light";
  const shotPath = `${require("os").tmpdir()}/prose-${theme}.png`;
  const samples = await page.evaluate(() => {
    const pick = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { color: cs.color, size: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight, 10) };
    };
    const boxOf = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    };
    return {
      panel: boxOf("#doc-prose-panel"),
      openRow: boxOf('.doc-prose-row[aria-current] .doc-prose-jump'),
      plainRow: boxOf('.doc-prose-row:not([aria-current]) .doc-prose-jump'),
      menu: boxOf("#doc-suggest-menu"),
      answers: boxOf(".doc-prose-answers .doc-suggest-best"),
      text: {
        words: pick(".doc-prose-row:not([aria-current]) .doc-finding-words"),
        why: pick(".doc-prose-row:not([aria-current]) .doc-finding-why"),
        openWords: pick('.doc-prose-row[aria-current] .doc-finding-words'),
        openWhy: pick('.doc-prose-row[aria-current] .doc-finding-why'),
        candidate: pick(".doc-prose-answers .doc-suggest-best"),
        menuWords: pick("#doc-suggest-menu .doc-finding-words"),
        menuWhy: pick("#doc-suggest-menu .doc-finding-why"),
        menuItem: pick("#doc-suggest-menu .doc-suggest-item"),
      },
    };
  });
  await page.screenshot({ path: shotPath });
  // One point per surface, chosen inside it and clear of its text: the right
  // inset of a row, the top inset of the menu.
  const points = [];
  const add = (name, box, dx, dy) => {
    if (!box) return;
    points.push({ name, x: Math.round(box.right - dx), y: Math.round(box.top + dy) });
  };
  add("plainRow", samples.plainRow, 6, 8);
  add("openRow", samples.openRow, 6, 8);
  add("answers", samples.answers, 2, 2);
  add("menu", samples.menu, 6, 6);
  add("panel", samples.panel, 4, 4);
  const out = require("child_process").execFileSync("python3", [
    require('path').resolve(__dirname, '..', 'pngpixel.py'), shotPath,
    ...points.flatMap((p) => [String(p.x), String(p.y)]),
  ], { encoding: "utf8" }).trim().split("\n").slice(1);
  const painted = {};
  out.forEach((line, i) => {
    const m = line.match(/\((\d+), (\d+), (\d+)/);
    if (m) painted[points[i].name] = { r: +m[1], g: +m[2], b: +m[3] };
  });
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
  const rgb = (c) => { const m = String(c).match(/(\d+), (\d+), (\d+)/); return m ? { r: +m[1], g: +m[2], b: +m[3] } : null; };
  const pairs = [
    ["a row's words", samples.text.words, "plainRow"],
    ["a row's reason", samples.text.why, "plainRow"],
    ["the open row's words", samples.text.openWords, "openRow"],
    ["the open row's reason", samples.text.openWhy, "openRow"],
    ["a candidate in the panel", samples.text.candidate, "answers"],
    ["the menu's words", samples.text.menuWords, "menu"],
    ["the menu's reason", samples.text.menuWhy, "menu"],
    ["a menu row", samples.text.menuItem, "menu"],
  ];
  const lines = [];
  for (const [label, text, surface] of pairs) {
    if (!text || !painted[surface]) { lines.push(`${label}: not measured`); continue; }
    const r = ratio(rgb(text.color), painted[surface]);
    const need = (text.size >= 18.66 || (text.weight >= 700 && text.size >= 14)) ? 3 : 4.5;
    const low = r < need;
    lines.push(`${label}: ${r.toFixed(2)} (needs ${need}, ${text.color} on rgb(${painted[surface].r},${painted[surface].g},${painted[surface].b}))${low ? "  <<< LOW" : ""}`);
    if (low) fails.push(`${label} is ${r.toFixed(2)}:1 in ${theme}`);
  }
  console.log(`contrast (${theme}, painted pixels from ${shotPath}):\n  ` + lines.join("\n  "));

  console.log("console errors: " + (errs.length ? errs.join(" | ") : "0"));
  console.log(fails.length ? "FAIL:\n  " + fails.join("\n  ") : "prosepanel: all checks pass");
  await browser.close();
  process.exit(fails.length ? 1 : 0);
})().catch((e) => { console.log("ERR " + e.message); process.exit(1); });
