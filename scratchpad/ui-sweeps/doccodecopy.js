// INBOX 232's remainder, measured rather than rebuilt (CLAUDE.md section 1).
//
// The entry's brief asked for three things on a fenced code block in the
// documents editor: hide the fence marker rows when the caret is outside the
// block, "a header row with the language and a copy button", and a check of
// tables, blockquotes and task lists. The first was built on 2026-09-19
// (706e2af) and the third verified the same week. This probe was written to
// build the second and found it already there: the Read pane's renderer
// (`renderMarkdown` in app.js) has drawn a `.code-bar` with the language,
// Copy and Save since INBOX 172. Measured on the branch head, 2026-09-20:
// 2 bars, "python ⧉ Copy Save" and "code ⧉ Copy Save".
//
// What that measurement *did* find is the glyph in those labels: a typed
// U+29C9 standing where an icon belongs, on a Copy button, in an app that
// ships `ph:copy` and uses it in five other places. So this is now a
// verification probe with one real assertion in it, and the glyph is in
// `tests/test_no_glyph_icons.py`'s banned list so it cannot come back.
//
// The live view is deliberately not asked for a button: see DOCUMENTS_PLAN
// section 15.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  — " + d}`);
};

const DOC = [
  "# Copy me",
  "",
  "Some prose before the block.",
  "",
  "```python",
  "def hello(name):",
  '    return f"hello {name}"',
  "```",
  "",
  "And prose after it.",
  "",
  "```",
  "a fence with no language at all",
  "```",
  "",
].join("\n");

(async () => {
  const { browser, page } = await boot();
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2200);

  await page.evaluate(async (text) => {
    const d = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: "Copy me", content: text }),
    });
    await loadDocuments(d.id);
  }, DOC);
  await page.waitForTimeout(2000);

  //: Read view: the pane a person reads, prints and takes code out of.
  const read = await page.evaluate(() => {
    setDocView("rendered");
    return new Promise((r) =>
      setTimeout(() => {
        const bars = [...document.querySelectorAll("#doc-preview .code-bar")];
        r({
          blocks: document.querySelectorAll("#doc-preview pre").length,
          bars: bars.length,
          langs: bars.map((b) => (b.querySelector(".code-lang") || {}).textContent),
          barText: bars.map((b) => b.textContent.replace(/\s+/g, " ").trim()),
          copies: document.querySelectorAll("#doc-preview .code-bar button").length,
          //: The icons, by class, which is what says the labels come through
          //: `setLabel` and not through a character someone typed.
          icons: [...document.querySelectorAll("#doc-preview .code-bar button i.ph")].map(
            (i) => i.className.split(/\s+/).find((c) => c.startsWith("ph-")) || "?"
          ),
        });
      }, 1400)
    );
  });
  console.log("      read:", JSON.stringify(read));
  ok("Read draws both fences as code blocks", read.blocks === 2, `${read.blocks} pre`);
  ok("each one carries a bar", read.bars === 2, `${read.bars} bars`);
  ok(
    "the bar names the language, or says code when there is none",
    JSON.stringify(read.langs) === JSON.stringify(["python", "code"]),
    JSON.stringify(read.langs)
  );
  ok("with a Wrap, a Copy and a Save on each", read.copies === 6, `${read.copies} buttons`);
  //: The fault this probe actually found. A label that is nothing but words
  //: leaves no `i.ph` behind, so counting the icons is the measurement.
  ok(
    "both buttons are drawn with the app's own icons",
    JSON.stringify(read.icons) === JSON.stringify(["ph-text-align-left", "ph-copy", "ph-download-simple", "ph-text-align-left", "ph-copy", "ph-download-simple"]),
    JSON.stringify(read.icons)
  );
  ok(
    "and no typed glyph is left in the labels",
    read.barText.every((t) => !/[⧉✕✓]/.test(t)),
    JSON.stringify(read.barText)
  );

  //: Live view: the language in the corner, by the decision recorded in the
  //: theme (a `.cm-md-fence-label` widget) and in DOCUMENTS_PLAN
  //: section 15. The assertion is that the label is there, not that a button
  //: is: a control inside a contenteditable is a caret trap, and this row is
  //: half a line tall on purpose.
  const live = await page.evaluate(() => {
    setDocView("live");
    return new Promise((r) =>
      setTimeout(() => {
        const opens = [...document.querySelectorAll(".cm-md-fence-open")];
        const quiet = opens.filter((n) => n.classList.contains("cm-md-fence-quiet"));
        r({
          opens: opens.length,
          langs: opens.map((n) => { const b = n.querySelector(".cm-md-fence-label"); return b ? b.textContent : null; }),
          quiet: quiet.length,
          quietHeight: quiet[0] ? Math.round(quiet[0].getBoundingClientRect().height) : null,
          rowHeight: opens[0]
            ? Math.round((document.querySelector(".cm-line:not(.cm-md-fence)") || opens[0]).getBoundingClientRect().height)
            : null,
        });
      }, 1600)
    );
  });
  console.log("      live:", JSON.stringify(live));
  ok("Live draws both fences", live.opens === 2, JSON.stringify(live.opens));
  ok("and labels the one with a language", live.langs[0] === "python", JSON.stringify(live.langs));
  ok(
    "the emptied marker row is well under a full line",
    live.quietHeight !== null && live.rowHeight !== null && live.quietHeight * 2 < live.rowHeight,
    `${live.quietHeight}px against a ${live.rowHeight}px line`
  );

  console.log(bad ? `${bad} FAILURES` : "all clear");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
