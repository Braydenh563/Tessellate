// The owner, 2026-09-24: "I want cool features for autofill and easy life
// stuff in the documents editor like if I type lorem and press enter or a
// popup that appears, then it will autofill the lorem ipsum filler text and
// stuff."
//
// Types into a real markdown document in Chromium, key by key, and asserts the
// list, the ghost text and the resulting text: `lorem` + Enter, `lorem3` +
// Tab, `today` alone + Enter and `now` inside a sentence (no list), `table 3x4`,
// `:thumbsu`, the to-do item and the list continuing on Enter, the pairs (`**`, `(`,
// backticks, Backspace), smart quotes off then on, and that a code file gets
// none of it. tests/test_prose_autofill.py holds the string work to exact
// output.
//
// Usage: BASE=http://127.0.0.1:8792 [THEME=dark] node proseautofill.js
const { boot } = require("./lib.js");

let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const J = JSON.stringify;

  const open = async (title, fileType, content) => {
    await page.evaluate(
      async ([t, f, c]) => {
        const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) });
        await loadDocuments(d.id);
      },
      [title, fileType, content]
    );
    await page.waitForTimeout(1200);
    await page.evaluate(() => {
      docCmView.focus();
      docCmView.dispatch({ selection: { anchor: docCmView.state.doc.length } });
    });
  };
  const state = () =>
    page.evaluate(() => {
      const s = docCmView.state;
      const r = s.selection.main;
      return { text: s.doc.toString(), head: r.head, selected: s.sliceDoc(r.from, r.to) };
    });
  const list = () =>
    page.evaluate(() => {
      const box = document.getElementById("doc-complete-list");
      if (!box || box.classList.contains("hidden")) return null;
      const rows = [...box.querySelectorAll("li")].map((li) => ({
        label: li.querySelector("b")?.textContent || "",
        detail: li.querySelector(".doc-complete-detail")?.textContent || "",
        glyph: li.querySelector(".doc-complete-glyph")?.textContent || "",
        fill: li.classList.contains("doc-complete-fill"),
        active: li.classList.contains("active"),
      }));
      const r = box.getBoundingClientRect();
      return { rows, w: Math.round(r.width), h: Math.round(r.height), bg: getComputedStyle(box).backgroundColor };
    });
  const ghost = () =>
    page.evaluate(() => {
      const g = document.querySelector(".cm-content .cm-ghostText");
      return g ? { text: g.textContent, color: getComputedStyle(g).color } : null;
    });
  const settle = () => page.waitForTimeout(250);
  const clear = async () => {
    await page.evaluate(() => docCmView.dispatch({ changes: { from: 0, to: docCmView.state.doc.length, insert: "" } }));
    await settle();
  };

  await open("autofill.md", "md", "");

  // --- lorem + Enter ------------------------------------------------------------
  await page.keyboard.type("lorem");
  await settle();
  let l = await list();
  ok("typing lorem opens the list with an expansion row", !!l && l.rows[0]?.fill && l.rows[0].label === "lorem", J(l));
  ok("the row says what it writes", l?.rows[0]?.detail === "A paragraph of filler text", l?.rows[0]?.detail);
  ok("the list is opaque", !!l && !/rgba\(.*, 0(\.\d+)?\)$/.test(l.bg), l?.bg);
  let g = await ghost();
  ok("the ghost after the caret previews the paragraph", !!g && g.text.startsWith("Lorem ipsum dolor"), J(g));
  await page.keyboard.press("Enter");
  await settle();
  let s = await state();
  ok("lorem then Enter writes the paragraph", s.text.startsWith("Lorem ipsum dolor sit amet") && s.text.endsWith("laborum."), J(s.text.slice(0, 40)));
  ok("and the list and the ghost are gone", !(await list()) && !(await ghost()));

  // --- lorem3 + Tab --------------------------------------------------------------
  await clear();
  await page.keyboard.type("Start lorem3");
  await settle();
  l = await list();
  ok("lorem3 mid-line is offered as three words", !!l && l.rows[0]?.detail === "3 words of filler text", J(l && l.rows[0]));
  await page.keyboard.press("Tab");
  await settle();
  s = await state();
  ok("Tab takes it", s.text === "Start Lorem ipsum dolor.", J(s.text));

  // --- a bare word on its own line, and not in a sentence -------------------------
  await clear();
  await page.keyboard.type("I will do it now");
  await settle();
  ok("now at the end of a sentence opens nothing", !(await list()), J(await list()));
  await page.keyboard.press("Enter");
  await page.keyboard.type("today");
  await settle();
  l = await list();
  const expected = await page.evaluate(() => new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }));
  ok("today alone on its line offers the date", !!l && l.rows[0]?.detail === expected, J(l && l.rows));
  await page.keyboard.press("Enter");
  await settle();
  s = await state();
  ok("and Enter writes it", s.text === `I will do it now\n${expected}`, J(s.text));

  // --- table 3x4 --------------------------------------------------------------------
  await clear();
  await page.keyboard.type("table 3x4");
  await settle();
  l = await list();
  ok("table 3x4 is offered", !!l && l.rows[0]?.detail === "A table, 3 columns by 4 rows", J(l && l.rows[0]));
  await page.keyboard.press("Enter");
  await settle();
  s = await state();
  ok("Enter writes a 3 by 4 table", s.text.split("\n").filter((x) => x.startsWith("|")).length === 6 && s.text.startsWith("| Column | Column | Column |"), J(s.text));
  ok("with the first header chosen", s.selected === "Column", J(s.selected));

  // --- shortcodes -----------------------------------------------------------------
  await clear();
  await page.keyboard.type("Nice :thumbsu");
  await settle();
  l = await list();
  ok(":thumbsu offers the glyph", !!l && l.rows[0]?.label === ":thumbsup:" && l.rows[0].glyph === "\u{1F44D}", J(l && l.rows[0]));
  await page.keyboard.press("Enter");
  await settle();
  s = await state();
  ok("Enter writes it", s.text === "Nice \u{1F44D}", J(s.text));

  // --- the to-do item, and the list continuing (already the markdown keymap's) ----------------
  await clear();
  await page.keyboard.type("todo");
  await settle();
  await page.keyboard.press("Enter");
  await settle();
  await page.keyboard.type("Buy milk");
  await page.keyboard.press("Enter");
  await settle();
  s = await state();
  ok("todo writes a task and Enter continues the list", s.text === "- [ ] Buy milk\n- [ ] ", J(s.text));
  await page.keyboard.press("Enter");
  await settle();
  s = await state();
  ok("Enter on an empty item ends the list", s.text === "- [ ] Buy milk\n", J(s.text));
  await clear();
  await page.keyboard.type("- one");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await settle();
  s = await state();
  const lastLine = s.text.split("\n").pop();
  ok("and on an empty nested item it steps out a level", /^- $/.test(lastLine), J(s.text));

  // --- pairs ------------------------------------------------------------------------
  await clear();
  await page.keyboard.type("A **");
  await settle();
  s = await state();
  ok("** opens bold with the caret inside", s.text === "A ****" && s.head === 4, J(s));
  await page.keyboard.type("bold**");
  await settle();
  s = await state();
  ok("typing the closer steps over it", s.text === "A **bold**" && s.head === s.text.length, J(s));
  await page.keyboard.type(" (x");
  await settle();
  s = await state();
  ok("( closes itself", s.text === "A **bold** (x)", J(s.text));
  await page.keyboard.type(")");
  await page.keyboard.type(" `");
  await settle();
  s = await state();
  ok("a backtick pairs", s.text === "A **bold** (x) ``", J(s.text));
  await page.keyboard.press("Backspace");
  await settle();
  s = await state();
  ok("Backspace in the empty pair takes both", s.text === "A **bold** (x) ", J(s.text));

  // --- smart quotes: off, then on ---------------------------------------------------
  await clear();
  await page.keyboard.type('He said "hi"');
  await settle();
  s = await state();
  ok("smart quotes are off by default", s.text === 'He said "hi"', J(s.text));
  await clear();
  await page.evaluate(() => { prefsCache.smart_punctuation = true; });
  await page.keyboard.type(`He said "hi" and didn't--really`);
  await settle();
  s = await state();
  ok("on, quotes curl and two hyphens make a dash", s.text === "He said “hi” and didn’t—really", J(s.text));
  await page.evaluate(() => { prefsCache.smart_punctuation = false; });

  // --- the word switch off: expansions stay -------------------------------------------
  await clear();
  await page.evaluate(() => { document.getElementById("doc-complete").checked = false; });
  await page.keyboard.type("lorem");
  await settle();
  ok("with word suggestions off, lorem is still offered", !!(await list()));
  await page.keyboard.press("Escape");
  await page.keyboard.press("Enter");
  await settle();
  s = await state();
  ok("Escape then Enter is a plain new line", s.text === "lorem\n", J(s.text));
  await page.evaluate(() => { document.getElementById("doc-complete").checked = true; });

  // --- a code file gets none of it ----------------------------------------------------
  await open("code.js", "js", "");
  await page.keyboard.type("lorem");
  await settle();
  ok("a code file offers no prose expansion", !(await list()));
  await page.keyboard.type(" (");
  s = await state();
  ok("and its own pairs are its own", s.text.startsWith("lorem ("), J(s.text));

  const shotDir = (process.env.SCRATCH || ".") + "/shots";
  await open("shot.md", "md", "# Notes\n\n");
  await page.keyboard.type(":hear");
  await settle();
  await page.screenshot({ path: `${shotDir}/proseautofill-${process.env.THEME || "light"}.png` });
  l = await list();
  g = await ghost();
  console.log("measure:", J({ list: l && { w: l.w, h: l.h, rows: l.rows.length, bg: l.bg }, ghost: g }));

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
