// INBOX 1549: "CodeMirror plugin crashed" in Documents just before the math
// editor loaded. Inserts an equation from the slash menu in Live and Source
// and in a document holding $...$ maths, and fails on any CM plugin crash.
const { boot } = require("./lib.js");
(async () => {
  const { page, browser } = await boot({});
  const crashes = [];
  page.on("console", async (m) => {
    if (m.type() !== "error") return;
    const t = m.text();
    if (/CodeMirror|plugin crashed/i.test(t)) {
      const args = await Promise.all(m.args().map((a) => a.evaluate((v) => v && v.stack ? v.stack : String(v)).catch(() => "?")));
      crashes.push(args.join(" | ").slice(0, 1500));
    }
  });
  page.on("pageerror", (e) => crashes.push("pageerror " + String(e.stack || e.message).slice(0, 800)));
  await page.waitForTimeout(3500);
  const id = await page.evaluate(async () => {
    const headers = { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" };
    const d = await (await fetch("/documents", { method: "POST", headers, body: JSON.stringify({ title: "Crash probe", content: "Crash probe\n\n[TOC]\n\n## Part\n\nInline $x^2$ and block %%note%% [^1]:\n\n$$\\frac{a}{b}$$\n\n| a | b |\n|---|---|\n| $y$ | 2 |\n\n- [ ] task $z$\n\n```js\nconst a = 1;\n```\n\n```mermaid\ngraph TD; A-->B\n```\n\n> quote $q$\n\n[^1]: foot\n\n" }) })).json();
    return d.id;
  });
  for (const view of ["live", "live"]) {
    await page.evaluate(async ([id, view]) => {
      switchTab("documents"); await new Promise((r) => setTimeout(r, 500));
      await openDocument(id); await new Promise((r) => setTimeout(r, 1500));
      if (typeof setDocView === "function") setDocView(view);
      await new Promise((r) => setTimeout(r, 500));
      docCmView.focus();
      docCmView.dispatch({ selection: { anchor: docCmView.state.doc.length } });
    }, [id, view]);
    await page.keyboard.type("/equation", { delay: 30 });
    await page.waitForTimeout(600);
    console.log("slash menu", await page.evaluate(() => { const m = [...document.querySelectorAll("[class*=slash]")].filter((e) => e.offsetParent); return m.map((e) => e.className).slice(0, 3); }), "active", await page.evaluate(() => document.activeElement && (document.activeElement.className || document.activeElement.tagName)));
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2500);
    await page.keyboard.type("a/b", { delay: 40 });
    await page.keyboard.press("Control+Enter");
    await page.waitForTimeout(1200);
    // Move the cursor through the maths, which reopens and redraws widgets.
    for (let i = 0; i < 12; i++) await page.keyboard.press("ArrowUp");
    await page.waitForTimeout(800);
    const doc = await page.evaluate(() => docCmView.state.doc.toString().slice(-120));
    console.log(view, JSON.stringify(doc));
    // Click a rendered maths widget (click-to-edit), type, commit.
    const box = await page.evaluate(() => { const m = document.querySelector(".cm-md-math"); if (!m) return null; const r = m.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; });
    if (box) { await page.mouse.click(box[0], box[1]); await page.waitForTimeout(2500); await page.keyboard.type("+1", { delay: 40 }); await page.keyboard.press("Enter"); await page.waitForTimeout(1000); }
    console.log("clicked", !!box);
    await page.keyboard.press("Alt+=");
    await page.waitForTimeout(1500);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    await page.keyboard.press("Escape");
  }
  console.log(crashes.length ? "FAIL crashes:\n" + crashes.join("\n---\n") : "ok no CodeMirror crash");
  await browser.close();
})();
