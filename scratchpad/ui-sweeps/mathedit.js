// The guided equation editor (DOCUMENTS_PLAN 16, math-editor.js), driven in
// the note capture box, a document, the Chat box and the Ask box.
//
// Per surface: "/equation" (or Alt+=) opens the panel, the panel sits inside
// the window with no sideways page scroll, guided typing makes structure
// ("a/" a fraction, "^" a slot, "alpha " the letter), the preview draws
// MathML, a palette tile inserts, Ctrl+Enter writes `$...$` into the box, and
// the cursor in an equation reopens it to edit.
//
//   BASE=http://127.0.0.1:8937 VIEW=390 node scratchpad/ui-sweeps/mathedit.js
const { boot } = require("./lib.js");

const WIDTH = Number(process.env.VIEW || 1440);

(async () => {
  const { page, browser } = await boot({ viewport: { width: WIDTH, height: WIDTH < 600 ? 844 : 900 } });
  let fails = 0;
  const check = (name, ok, detail) => {
    if (!ok) fails += 1;
    console.log(`${ok ? "ok  " : "FAIL"} ${name}${detail !== undefined ? ": " + JSON.stringify(detail) : ""}`);
  };
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message).slice(0, 200)));
  const panel = () => page.evaluate(() => {
    const p = document.querySelector(".math-editor");
    if (!p) return null;
    const r = p.getBoundingClientRect();
    const list = p.querySelector(".math-editor-list");
    const input = p.querySelector(".math-editor-input");
    const wide = [...p.querySelectorAll("*")].filter((el) => el.getBoundingClientRect().right > r.right + 1 && !el.closest(".math-editor-preview math")).length;
    return {
      box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
      inView: r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1,
      pageScrollX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      listScrolls: list.scrollHeight > list.clientHeight,
      listH: list.clientHeight,
      tiles: p.querySelectorAll(".math-editor-tile").length,
      mathTiles: p.querySelectorAll(".math-editor-tile math").length,
      groups: [...p.querySelectorAll(".math-editor-group")].map((g) => g.textContent).join(","),
      spill: wide,
      value: input.value,
      focus: document.activeElement === input,
      preview: p.querySelector(".math-editor-preview").innerHTML.slice(0, 160),
      title: p.querySelector(".dialog-head-title").textContent,
      tileMin: Math.round(Math.min(...[...p.querySelectorAll(".math-editor-tile")].slice(0, 40).map((t) => t.getBoundingClientRect().height))),
    };
  });
  try {
    await page.waitForTimeout(3500);
    const doc = await page.evaluate(async () => {
      const headers = { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" };
      const d = await (await fetch("/documents", { method: "POST", headers, body: JSON.stringify({ title: "Maths probe", content: "Maths probe\n\n" }) })).json();
      return d.id;
    });
    for (const surface of ["note", "document", "chat", "ask"]) {
      console.log(`--- ${surface} at ${WIDTH}`);
      if (surface === "note") {
        await page.evaluate(async () => { switchTab("notes"); showNotesSection("capture"); await new Promise((r) => setTimeout(r, 1200)); });
        await page.click("#entry-content");
      } else if (surface === "document") {
        await page.evaluate(async (id) => {
          switchTab("documents");
          await new Promise((r) => setTimeout(r, 500));
          await openDocument(id);
          await new Promise((r) => setTimeout(r, 2000));
          if (typeof setDocView === "function") setDocView("live");
          await new Promise((r) => setTimeout(r, 500));
          docCmView.focus();
          docCmView.dispatch({ selection: { anchor: docCmView.state.doc.length } });
        }, doc);
      } else if (surface === "chat") {
        await page.evaluate(async () => { switchTab("chat"); await new Promise((r) => setTimeout(r, 1200)); });
        await page.click("#chat-input");
      } else {
        await page.evaluate(async () => { switchTab("notes"); showNotesSection("ask"); await new Promise((r) => setTimeout(r, 1200)); });
        await page.click("#question");
      }
      const text = () => page.evaluate((s) => {
        if (s === "document") return docCmView.state.doc.toString();
        const id = { note: "entry-content", chat: "chat-input", ask: "question" }[s];
        return document.getElementById(id).value;
      }, surface);
      if (surface === "ask") {
        await page.keyboard.press("Alt+Equal");
      } else {
        await page.keyboard.type("/equation");
        await page.waitForTimeout(400);
        await page.keyboard.press("Enter");
      }
      await page.waitForTimeout(900);
      let s = await panel();
      check(`${surface}: opens`, !!s, s);
      if (!s) continue;
      check(`${surface}: in the window, no page scroll`, s.inView && s.pageScrollX <= 0, { box: s.box, x: s.pageScrollX });
      check(`${surface}: nothing spills sideways`, s.spill === 0, s.spill);
      check(`${surface}: palette`, s.tiles > 100 && s.mathTiles >= 20 && s.groups.split(",").length === 7, { tiles: s.tiles, math: s.mathTiles, groups: s.groups });
      check(`${surface}: palette scrolls in itself`, s.listScrolls && s.listH >= 100, s.listH);
      check(`${surface}: tiles meet the target`, s.tileMin >= 24, s.tileMin);
      check(`${surface}: focus in the box`, s.focus);
      await page.keyboard.type("a/b");
      await page.keyboard.press("Tab");
      await page.keyboard.type("+x^2+alpha ");
      s = await panel();
      check(`${surface}: guided typing`, s.value === "\\frac{a}{b}+x^{2}+\\alpha ", s.value);
      check(`${surface}: preview is MathML`, /<math[^>]*><mrow><mfrac>/.test(s.preview), s.preview);
      // Backspace straight after a change undoes it, as Word's autocorrect does.
      await page.keyboard.press("Backspace");
      s = await panel();
      check(`${surface}: backspace undoes the change`, s.value === "\\frac{a}{b}+x^{2}+alpha ", s.value);
      for (let i = 0; i < 6; i += 1) await page.keyboard.press("Backspace");
      await page.keyboard.type("\\alpha");
      s = await panel();
      check(`${surface}: TeX typed as TeX stands`, s.value === "\\frac{a}{b}+x^{2}+\\alpha", s.value);
      await page.click('.math-editor-tile[aria-label="pi"]');
      s = await panel();
      check(`${surface}: tile inserts`, s.value === "\\frac{a}{b}+x^{2}+\\alpha\\pi ", s.value);
      await page.keyboard.press("Control+Enter");
      await page.waitForTimeout(400);
      const written = await text();
      check(`${surface}: written`, written.includes("$\\frac{a}{b}+x^{2}+\\alpha\\pi$") && !(await panel()), written.slice(-60));
      if (surface === "note" || surface === "document") {
        // The caret back inside the equation reopens it to edit.
        await page.keyboard.press("ArrowLeft");
        await page.keyboard.press("ArrowLeft");
        await page.keyboard.press("Alt+Equal");
        await page.waitForTimeout(600);
        s = await panel();
        check(`${surface}: reopens to edit`, s && s.title === "Edit equation" && s.value === "\\frac{a}{b}+x^{2}+\\alpha\\pi", s && [s.title, s.value]);
        await page.keyboard.press("Escape");
        await page.waitForTimeout(300);
        check(`${surface}: Escape closes`, !(await panel()));
      }
      if (surface === "document") {
        // A display matrix from the palette, drawn by the Live view.
        await page.evaluate(() => docCmView.dispatch({ selection: { anchor: docCmView.state.doc.length } }));
        await page.keyboard.press("Alt+Equal");
        await page.waitForTimeout(600);
        await page.click('.math-editor-mode [data-value="display"]');
        await page.click('.math-editor-tile[aria-label="matrix"]');
        await page.keyboard.type("1");
        await page.keyboard.press("Tab");
        await page.keyboard.type("0");
        await page.keyboard.press("Control+Enter");
        await page.waitForTimeout(900);
        const doc2 = await text();
        // The Live view shows a block's source while the caret is in it.
        await page.evaluate(() => docCmView.dispatch({ selection: { anchor: 0 } }));
        await page.waitForTimeout(600);
        const drawn = await page.evaluate(() => {
          const t = [...document.querySelectorAll("mtable")].find((el) => !el.closest(".math-editor") && el.getClientRects().length);
          return t ? t.querySelectorAll("mtd").length : 0;
        });
        check("document: display matrix written", doc2.includes("\n\n$$\\begin{pmatrix} {1} & {0} \\\\ {} & {} \\end{pmatrix}$$"), doc2.slice(-80));
        check("document: matrix drawn as a table", drawn === 4, drawn);
      }
    }
  } catch (error) {
    check("ran", false, String(error.message).slice(0, 300));
  }
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  console.log(fails ? `${fails} failed` : "all passed");
  await browser.close();
  process.exit(fails ? 1 : 0);
})();
