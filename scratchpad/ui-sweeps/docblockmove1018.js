// INBOX 904 B20: Alt+Up and Alt+Down move a block of a markdown document (a
// paragraph, a list item with its children, a fenced block, a heading's
// section) instead of welding paragraphs the way the line move does; a code
// file keeps the line move. Real keys in Chromium, numbers from the editor.
//
// Usage: BASE=http://127.0.0.1:8792 [THEME=dark] node docblockmove1018.js
const { boot } = require("./lib.js");

let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

const open = async (page, type, content, view) => {
  await page.evaluate(async ([t, c]) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Block move " + t, content: c, file_type: t }) });
    await loadDocuments(d.id);
  }, [type, content]);
  await page.waitForTimeout(1800);
  if (view) {
    await page.evaluate((v) => setDocView(v), view);
    await page.waitForTimeout(1200);
  }
};
const caretAt = (page, word, add = 1) =>
  page.evaluate(([w, a]) => {
    const s = docCmView.state.doc.toString();
    docCmView.dispatch({ selection: { anchor: s.indexOf(w) + a } });
    docCmView.focus();
  }, [word, add]);
const doc = (page) => page.evaluate(() => docCmView.state.doc.toString());
const caretWord = (page) =>
  page.evaluate(() => {
    const s = docCmView.state.doc.toString();
    const h = docCmView.state.selection.main.head;
    return s.slice(Math.max(0, h - 3), h + 3);
  });

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => {
    if (!/about:srcdoc|blob:null/.test(String(e.stack))) errors.push(e.message);
  });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2500);

  const PROSE = "# Plan\n\nalpha\n\nbeta\n\ngamma\n";
  for (const view of ["live", "source"]) {
    await open(page, "md", PROSE, view);
    await caretAt(page, "beta");
    await page.keyboard.press("Alt+ArrowUp");
    await page.waitForTimeout(250);
    ok(`${view}: paragraph moves above the one before it`, (await doc(page)) === "# Plan\n\nbeta\n\nalpha\n\ngamma\n", JSON.stringify(await doc(page)));
    ok(`${view}: the caret went with it`, (await caretWord(page)).includes("be"), await caretWord(page));
    await page.keyboard.press("Alt+ArrowDown");
    await page.waitForTimeout(250);
    ok(`${view}: moving back is byte-exact`, (await doc(page)) === PROSE);
    await page.keyboard.press("Control+z");
    await page.waitForTimeout(250);
    ok(`${view}: one undo takes back one move`, (await doc(page)) === "# Plan\n\nbeta\n\nalpha\n\ngamma\n", JSON.stringify(await doc(page)));
  }

  await open(page, "md", "# Tasks\n\n- [ ] one\n  - sub\n- [ ] two\n- [ ] three\n\n1. a\n2. b\n3. c\n", "source");
  await caretAt(page, "- [ ] one");
  await page.keyboard.press("Alt+ArrowDown");
  await page.waitForTimeout(250);
  ok("list item goes down with its child", (await doc(page)).startsWith("# Tasks\n\n- [ ] two\n- [ ] one\n  - sub\n- [ ] three\n"), JSON.stringify(await doc(page)));
  await caretAt(page, "2. b");
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(250);
  ok("numbered items keep their numbers", (await doc(page)).endsWith("1. b\n2. a\n3. c\n"), JSON.stringify(await doc(page)));

  await open(page, "md", "# Top\n\n## One\n\none\n\n### Deep\n\ndeep\n\n## Two\n\ntwo\n", "source");
  await caretAt(page, "## Two", 3);
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(250);
  ok("a heading moves with its section, children and all", (await doc(page)) === "# Top\n\n## Two\n\ntwo\n\n## One\n\none\n\n### Deep\n\ndeep\n", JSON.stringify(await doc(page)));
  await caretAt(page, "## Two", 3);
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(250);
  ok("the first section at its level stays put", (await doc(page)).startsWith("# Top\n\n## Two\n"));

  // Live view: a table is one block.
  await open(page, "md", "intro\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\nend\n", "live");
  await caretAt(page, "end");
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(250);
  ok("live: a paragraph moves above a table whole", (await doc(page)) === "intro\n\nend\n\n| a | b |\n| - | - |\n| 1 | 2 |\n", JSON.stringify(await doc(page)));

  // The palette door.
  await caretAt(page, "intro");
  await page.evaluate(() => docBlockMoveCommand(1));
  await page.waitForTimeout(250);
  ok("palette command moves the block", (await doc(page)).startsWith("end\n\nintro\n"), JSON.stringify(await doc(page)));
  const row = await page.evaluate(() => DOC_COMMANDS.filter((c) => /^move-block/.test(c.id)).map((c) => [c.id, c.keys]));
  ok("both commands are in the table with their keys", row.length === 2 && row.every((r) => /Alt/.test(r[1])), JSON.stringify(row));

  // A code file keeps the line move.
  await open(page, "py", "a = 1\nb = 2\nc = 3\n", null);
  await caretAt(page, "b = 2");
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(250);
  ok("a code file keeps the line move", (await doc(page)) === "b = 2\na = 1\nc = 3\n", JSON.stringify(await doc(page)));

  // A selection moves as lines, as before.
  await open(page, "md", "one\ntwo\nthree\n", "source");
  await page.evaluate(() => {
    docCmView.dispatch({ selection: { anchor: 4, head: 7 } });
    docCmView.focus();
  });
  await page.keyboard.press("Alt+ArrowUp");
  await page.waitForTimeout(250);
  ok("a selection keeps the line move", (await doc(page)) === "two\none\nthree\n", JSON.stringify(await doc(page)));

  ok("no page errors", errors.length === 0, errors.join("; "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
