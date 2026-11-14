// L-documents-41: with Vim keys on, Escape then dd deletes a line and the dock shows the mode; off, it does not.
// Usage: BASE=http://127.0.0.1:8811 node vim-keys-l41.js
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}  - ${JSON.stringify(d)}`); };

(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const vimFetches = [];
  page.on("request", (r) => r.url().includes("vim.min.js") && vimFetches.push(r.url()));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);

  const open = async (title, fileType) => {
    await page.evaluate(async ([t, f]) => {
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: "one\ntwo\nthree", file_type: f }) });
      await loadDocuments(d.id);
    }, [title, fileType]);
    await page.waitForTimeout(1500);
    await page.evaluate(() => { docCmView.focus(); docCmView.dispatch({ selection: { anchor: 4 } }); });
  };
  const text = () => page.evaluate(() => docCmView.state.doc.toString());
  const chip = () => page.evaluate(() => { const c = document.getElementById("doc-vim-mode"); return { text: c.textContent, hidden: c.classList.contains("hidden") }; });

  for (const [title, ft] of [["vim-code.py", "py"], ["vim-prose.md", "md"]]) {
    // OFF (default)
    await page.evaluate(() => Object.keys(localStorage).filter((k) => k.includes("doc-vim")).forEach((k) => localStorage.removeItem(k)));
    await open(title + "-off", ft);
    const stored0 = await page.evaluate(() => docToolPref("vimKeys", false));
    await page.keyboard.press("Escape");
    await page.keyboard.type("dd");
    const off = await text();
    ok(`${ft} off: default false, Escape dd does not delete a line`, stored0 === false && off.includes("two") === false ? false : stored0 === false, { stored0, off });
    ok(`${ft} off: the text now has the typed letters, not a deleted line`, off.split("\n").length === 3 && off.includes("dd"), off);
    ok(`${ft} off: chip hidden, vim file not fetched`, (await chip()).hidden && (ft === "md" || vimFetches.length === 0), { chip: await chip(), vimFetches });

    // ON
    await page.evaluate(() => { const b = document.getElementById("doc-vim"); b.checked = true; b.dispatchEvent(new Event("change", { bubbles: true })); });
    await page.waitForTimeout(1500);
    await open(title + "-on", ft);
    await page.waitForTimeout(800);
    const c1 = await chip();
    ok(`${ft} on: stored and chip shows NORMAL`, (await page.evaluate(() => docToolPref("vimKeys", false))) === true && c1.text === "NORMAL" && !c1.hidden, c1);
    await page.keyboard.press("Escape");
    await page.keyboard.type("dd");
    const on = await text();
    ok(`${ft} on: Escape dd deletes line two`, on === "one\nthree", on);
    await page.keyboard.type("i");
    const c2 = await chip();
    ok(`${ft} on: i shows INSERT`, c2.text === "INSERT", c2);
    await page.keyboard.press("Escape");
    await page.keyboard.type("v");
    const c3 = await chip();
    ok(`${ft} on: v shows VISUAL`, c3.text === "VISUAL", c3);
    await page.keyboard.press("Escape");
    // OFF again, live
    await page.evaluate(() => { const b = document.getElementById("doc-vim"); b.checked = false; b.dispatchEvent(new Event("change", { bubbles: true })); });
    await page.waitForTimeout(500);
    const c4 = await chip();
    await page.evaluate(() => docCmView.focus());
    const before = await text();
    await page.keyboard.press("Escape");
    await page.keyboard.type("dd");
    const after = await text();
    ok(`${ft} toggled off live: chip hidden, dd types letters`, c4.hidden && after.length === before.length + 2, { c4, before, after });
    // persistence across reload
    await page.evaluate(() => { const b = document.getElementById("doc-vim"); b.checked = true; b.dispatchEvent(new Event("change", { bubbles: true })); });
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  ok("persists across reload", await page.evaluate(() => localStorage.getItem(Object.keys(localStorage).find((k) => k.includes("doc-vim")) || "x")), await page.evaluate(() => Object.entries(localStorage).filter(([k]) => k.includes("doc-vim"))));
  ok("no page errors", errors.length === 0, errors);
  console.log(bad ? `${bad} FAILED` : "ALL PASS", { vimFetches });
  await browser.close();
})();
