// L883 and L885: IME composition in the document editor (CodeMirror), driven by CDP
// Input.imeSetComposition (real composition events, no real IME). Autocorrect must not
// rewrite a preedit; the committed text must land once; the blocked-bundle fallback must
// still take typing. BASE=http://127.0.0.1:8856 node hw883.js
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`); };
(async () => {
  const { browser, ctx, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
  await page.waitForTimeout(1500);
  const dc = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  if (await dc.count()) await dc.first().click();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const acOnNow = () => page.evaluate(() => { const c = document.getElementById("doc-autocorrect"); if (c && !c.checked) { c.checked = true; c.dispatchEvent(new Event("change", { bubbles: true })); } return !!(c && c.checked); });
  const open = async (title, content) => {
    await page.evaluate(async ([t, c]) => {
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c }) });
      await loadDocuments(d.id);
    }, [title, content]);
    await page.waitForTimeout(1500);
  };
  await open("IME check", "");
  await acOnNow();
  const cdp = await ctx.newCDPSession(page);
  const text = () => page.evaluate(() => (docCmView ? docCmView.state.doc.toString() : docBoxEl().value));
  await page.evaluate(() => { window.__ev = []; for (const t of ["compositionstart", "compositionupdate", "compositionend"]) document.addEventListener(t, (e) => window.__ev.push(t + ":" + e.data), true); });
  const focusEnd = () => page.evaluate(() => { docCmView.focus(); docCmView.dispatch({ selection: { anchor: docCmView.state.doc.length } }); });
  // Control: autocorrect is on and fixes a typed typo.
  await focusEnd();
  await page.keyboard.type("teh ");
  await page.waitForTimeout(300);
  const typed = await text();
  const acOn = await page.evaluate(() => docAutocorrectEnabled());
  ok("control: autocorrect on, typed 'teh ' becomes 'the '", acOn && typed === "the ", JSON.stringify({ acOn, typed }));
  // 1. A pinyin-style preedit that looks like a typo plus a space.
  await page.evaluate(() => docCmView.dispatch({ changes: { from: 0, to: docCmView.state.doc.length, insert: "" } }));
  await focusEnd();
  await cdp.send("Input.imeSetComposition", { text: "teh ", selectionStart: 4, selectionEnd: 4 });
  await page.waitForTimeout(300);
  const during = await text();
  const comp = await page.evaluate(() => docCmView.composing);
  ok("preedit 'teh ' is not rewritten while composing", comp && during === "teh ", JSON.stringify({ comp, during }));
  await cdp.send("Input.imeSetComposition", { text: "tehe ", selectionStart: 5, selectionEnd: 5 });
  await page.waitForTimeout(200);
  ok("the preedit grows as the IME says", (await text()) === "tehe ", JSON.stringify(await text()));
  // commit a CJK string in place of the preedit
  await cdp.send("Input.insertText", { text: "你好" });
  await page.waitForTimeout(400);
  const after = await text();
  ok("commit lands once: '你好', no stray preedit", after === "你好", JSON.stringify(after));
  const evs = await page.evaluate(() => window.__ev);
  ok("composition events fired (start, update, end)", evs.some((e) => /^compositionstart/.test(e)) && evs.some((e) => /^compositionupdate/.test(e)) && evs.some((e) => /^compositionend/.test(e)), JSON.stringify(evs));
  // 2. Preedit committed as a Latin typo: corrected only after the commit, once.
  await page.evaluate(() => docCmView.dispatch({ changes: { from: 0, to: docCmView.state.doc.length, insert: "" } }));
  await focusEnd();
  await cdp.send("Input.imeSetComposition", { text: "adn", selectionStart: 3, selectionEnd: 3 });
  await cdp.send("Input.insertText", { text: "adn" });
  await page.keyboard.type(" ");
  await page.waitForTimeout(400);
  const t2 = await text();
  ok("a word committed by the IME then a space is autocorrected once", t2 === "and ", JSON.stringify(t2));
  // 3. Enter during composition does not split the line or run a handler.
  await page.evaluate(() => docCmView.dispatch({ changes: { from: 0, to: docCmView.state.doc.length, insert: "- item" } }));
  await focusEnd();
  await cdp.send("Input.imeSetComposition", { text: "にほん", selectionStart: 3, selectionEnd: 3 });
  await cdp.send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 229 });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await page.waitForTimeout(250);
  const t3 = await text();
  ok("Enter that picks a candidate (keyCode 229) adds no new list line", !/\n- /.test(t3), JSON.stringify(t3));
  await cdp.send("Input.insertText", { text: "日本" });
  await page.waitForTimeout(250);
  ok("the picked candidate is inserted on the same line", (await text()) === "- item日本", JSON.stringify(await text()));
  // 4. Title field Enter during composition stays in the title.
  await page.focus("#doc-title");
  await cdp.send("Input.imeSetComposition", { text: "ぶんしょ", selectionStart: 4, selectionEnd: 4 });
  await cdp.send("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 229 });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await page.waitForTimeout(200);
  const still = await page.evaluate(() => document.activeElement && document.activeElement.id);
  ok("Enter on a title candidate does not jump to the body", still === "doc-title", still);
  await cdp.send("Input.insertText", { text: "文書" });

  // ---- L885: fallback when the bundle request is blocked ----
  await page.waitForTimeout(500);
  await ctx.route("**/vendor/codemirror/codemirror.min.js*", (r) => r.abort("failed"));
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const dc2 = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  if (await dc2.count()) await dc2.first().click();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(1500);
  await open("IME fallback", "");
  await acOnNow();
  const mode = await page.evaluate(() => ({ cm: !!(typeof docCmView !== "undefined" && docCmView && docCmView.dom.isConnected), box: !!(docBoxEl() && docBoxEl().offsetParent) }));
  ok("with the bundle blocked the plain textarea is the editor", !mode.cm && mode.box, JSON.stringify(mode));
  await page.evaluate(() => docBoxEl().focus());
  await cdp.send("Input.imeSetComposition", { text: "teh ", selectionStart: 4, selectionEnd: 4 });
  await page.waitForTimeout(250);
  const v1 = await page.evaluate(() => docBoxEl().value);
  ok("fallback: preedit 'teh ' left alone while composing", v1 === "teh ", JSON.stringify(v1));
  await cdp.send("Input.insertText", { text: "你好" });
  await page.waitForTimeout(300);
  ok("fallback: commit lands once", (await page.evaluate(() => docBoxEl().value)) === "你好", JSON.stringify(await page.evaluate(() => docBoxEl().value)));
  await page.keyboard.type(" teh ");
  await page.waitForTimeout(300);
  const v2 = await page.evaluate(() => docBoxEl().value);
  ok("fallback: ordinary typing still autocorrects after IME text", v2 === "你好 the ", JSON.stringify(v2));
  await page.waitForTimeout(1800);
  const saved = await page.evaluate(async () => (await apiJson(`/documents/${currentDoc.id}`)).content);
  ok("fallback: the document saved with the IME text", /你好 the/.test(saved), JSON.stringify(saved));
  console.log(bad ? `FAILED ${bad}` : "ALL PASS");
  await browser.close();
})().catch((e) => { console.log("ERR", e.message); process.exit(1); });
