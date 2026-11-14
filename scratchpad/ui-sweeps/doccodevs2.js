// INBOX 402, the second half of the VS Code features (doccodevs.js has the
// first): colour swatches, hover docs, indentation guides and bracket
// colours, the outline jump, wrap and whitespace, sticky scroll. Measured in
// Chromium, numbers not looks: computed colours, rects, the text produced.
//
// Usage: BASE=http://127.0.0.1:8799 [THEME=dark] node doccodevs2.js
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

  const open = async (title, fileType, marked) => {
    const at = marked.indexOf("|");
    const content = at >= 0 ? marked.slice(0, at) + marked.slice(at + 1) : marked;
    await page.evaluate(
      async ([t, f, c]) => {
        const d = await apiJson("/documents", {
          method: "POST",
          body: JSON.stringify({ title: t, content: c, file_type: f }),
        });
        await loadDocuments(d.id);
      },
      [title, fileType, content]
    );
    await page.waitForTimeout(1200);
    await page.evaluate((a) => {
      docCmView.focus();
      docCmView.dispatch({ selection: { anchor: a < 0 ? docCmView.state.doc.length : a } });
    }, at);
  };
  const text = () => page.evaluate(() => docCmView.state.doc.toString());
  const J = JSON.stringify;

  // --- 4. colour swatches ---------------------------------------------------------
  await open(
    "colours.css",
    "css",
    "a {\n  color: #ff0000;\n  background: rgb(0, 128, 0);\n  border-color: red;\n}\n/* red and #00f in a comment */"
  );
  await page.waitForTimeout(300);
  const swatches = await page.evaluate(() =>
    [...document.querySelectorAll(".cm-color-swatch")].map((s) => {
      const cs = getComputedStyle(s);
      const r = s.getBoundingClientRect();
      return { bg: cs.backgroundColor, w: Math.round(r.width), h: Math.round(r.height), border: cs.borderTopWidth };
    })
  );
  ok("three values, three swatches, none for the comment", swatches.length === 3, J(swatches));
  ok(
    "each in its own colour",
    J(swatches.map((s) => s.bg)) === J(["rgb(255, 0, 0)", "rgb(0, 128, 0)", "rgb(255, 0, 0)"]),
    J(swatches.map((s) => s.bg))
  );
  ok("a small square on a hairline", swatches.every((s) => s.w === s.h && s.w >= 8 && s.w <= 16 && s.border === "1px"), J(swatches[0]));
  const pick = async (index, value) => {
    const box = await page.evaluate((i) => {
      const r = document.querySelectorAll(".cm-color-swatch")[i].getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }, index);
    await page.mouse.click(box.x, box.y);
    await page.waitForTimeout(200);
    return page.evaluate((v) => {
      const input = document.querySelector(".doc-color-input");
      if (!input) return null;
      const before = input.value;
      input.value = v;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return { before, left: document.querySelector(".doc-color-input") !== null };
    }, value);
  };
  let picked = await pick(0, "#00ff00");
  let t = await text();
  ok("a click opens the picker on the value's colour", picked && picked.before === "#ff0000", J(picked));
  ok("and a pick writes the hex back", t.includes("color: #00ff00;"), J(t.split("\n")[1]));
  ok("the picker's input goes when it closes", picked && picked.left === false);
  picked = await pick(1, "#0000ff");
  t = await text();
  ok("rgb() stays rgb()", t.includes("background: rgb(0, 0, 255);"), J(t.split("\n")[2]));

  await open("style.html", "html", "<style>\n  p { color: teal; }\n</style>\n<p>teal</p>");
  await page.waitForTimeout(300);
  const inHtml = await page.evaluate(() => document.querySelectorAll(".cm-color-swatch").length);
  ok("an HTML file's <style> gets them, its text does not", inHtml === 1, `${inHtml} swatches`);

  // --- 5. hover docs ----------------------------------------------------------------
  //: Hover the middle of the word at `offset`, wait for the card, read it.
  const hoverAt = async (offset) => {
    await page.mouse.move(5, 5);
    await page.waitForTimeout(150);
    const at = await page.evaluate((o) => {
      const a = docCmView.coordsAtPos(o);
      const b = docCmView.coordsAtPos(o + 2);
      return { x: (a.left + b.left) / 2, y: (a.top + a.bottom) / 2 };
    }, offset);
    await page.mouse.move(at.x, at.y);
    await page.waitForTimeout(700);
    return page.evaluate(() => {
      const card = document.querySelector(".cm-hover-doc");
      if (!card) return null;
      const tip = card.closest(".cm-tooltip");
      return { text: card.innerText, bg: tip ? getComputedStyle(tip).backgroundColor : null };
    });
  };
  await open("hover.css", "css", "a {\n  display: flex;\n}\n/* display */");
  let card = await hoverAt(7);
  ok("hovering a CSS property shows its line and its values", !!card && card.text.includes("How the box is laid out") && card.text.includes("Values: block"), J(card));
  ok("on an opaque card", !!card && card.bg && !/, 0(\.\d+)?\)$/.test(card.bg), card && card.bg);
  card = await hoverAt(24);
  ok("a word in a comment gets nothing", card === null, J(card));
  await open("hover.html", "html", '<nav>\n  <a href="#">nav</a>\n</nav>');
  card = await hoverAt(1);
  ok("hovering an element shows its line", !!card && card.text.includes("<nav>") && card.text.includes("navigation links"), J(card));
  card = await hoverAt(11);
  ok("and an attribute", !!card && card.text.includes("The address a link points to."), J(card));
  card = await hoverAt(18);
  ok("and the same word as text gets nothing", card === null, J(card));

  // --- 6. indentation guides and bracket pair colours ------------------------------
  await open("guides.py", "py", 'def f():\n    if x:\n        return (a[b({})], "(")\n');
  await page.mouse.move(5, 5);
  await page.waitForTimeout(400);
  //: Guides are line classes now (documents-code.js docIndentGuides, INBOX 1562): `cm-indent-nN` on a line cuts one gradient to N steps of 2em.
  const guides = await page.evaluate(() => {
    const lines = [...document.querySelectorAll(".cm-line")];
    const em = parseFloat(getComputedStyle(lines[1]).fontSize);
    const info = (el) => ({ cls: [...el.classList].filter((c) => /^cm-indent-n\d$/.test(c)).join(), w: parseFloat(getComputedStyle(el).backgroundSize), img: getComputedStyle(el).backgroundImage !== "none" });
    return { em, l1: info(lines[0]), l2: info(lines[1]), l3: info(lines[2]) };
  });
  ok("no guide on line 1, one step on line 2, two on line 3", guides.l1.cls === "" && guides.l2.cls === "cm-indent-n1" && guides.l3.cls === "cm-indent-n2" && guides.l2.img && guides.l3.img, J(guides));
  ok("each step is 2em wide", Math.abs(guides.l2.w - 2 * guides.em) <= 1 && Math.abs(guides.l3.w - 4 * guides.em) <= 1, J(guides));
  const brackets = await page.evaluate(() => {
    const colour = (k) => [...document.querySelectorAll(`.cm-bracket-${k}`)].map((e) => [e.textContent, getComputedStyle(e).color]);
    const text = getComputedStyle(document.querySelector(".cm-content")).color;
    return { b0: colour(0), b1: colour(1), b2: colour(2), text };
  });
  const tones = [brackets.b0, brackets.b1, brackets.b2].map((b) => b[0] && b[0][1]);
  ok("pairs by depth, three tones in turn", J(brackets.b0.map((b) => b[0])) === J(["(", ")", "(", "{", "}", ")"]) && J(brackets.b1.map((b) => b[0])) === J(["[", "]"]) && J(brackets.b2.map((b) => b[0])) === J(["(", ")"]), J(brackets));
  ok("three different tones, none the text's", new Set(tones).size === 3 && !tones.includes(brackets.text), J({ tones, text: brackets.text }));
  ok("the ( in a string is not a bracket", brackets.b0.length + brackets.b1.length + brackets.b2.length === 10, J(brackets));

  // --- 7. symbols in the outline, the breadcrumb and the palette ---------------------
  await open("symbols.py", "py", "# class Comment:\ndef f(x):\n    pass\nclass A:\n    def m(self):\n        return 1|\n");
  await page.evaluate(() => renderDocOutline());
  await page.waitForTimeout(400);
  const outline = await page.evaluate(() => ({
    rows: [...document.querySelectorAll("#doc-outline li")].map((li) => li.textContent.trim()),
    draggable: [...document.querySelectorAll("#doc-outline li")].some((li) => li.draggable),
    crumbs: [...document.querySelectorAll("#doc-crumbs .doc-crumb")].map((b) => b.textContent),
  }));
  ok("a Python file's outline is its symbols, not its # comments", J(outline.rows) === J(["f()", "class A", "m()"]), J(outline));
  ok("and its rows jump, they do not move", outline.draggable === false);
  ok("the breadcrumb follows the caret into the method", J(outline.crumbs.slice(1)) === J(["class A", "m()"]), J(outline.crumbs));
  await page.evaluate(() => docOpenSymbols());
  await page.waitForTimeout(300);
  const menu = await page.evaluate(() => { const m = [...document.querySelectorAll(".action-menu")].find((el) => !el.classList.contains("hidden")); return m ? [...m.querySelectorAll(".menu-item")].map((b) => b.textContent.trim()) : []; });
  ok("Go to a symbol lists them at the caret", menu.length === 3 && menu[1].includes("class A"), J(menu));
  await page.evaluate(() => [...document.querySelectorAll(".action-menu")].find((el) => !el.classList.contains("hidden")).querySelector(".menu-item").click());
  await page.waitForTimeout(300);
  const line = await page.evaluate(() => docCmView.state.doc.lineAt(docCmView.state.selection.main.head).number);
  ok("and choosing one goes to its line", line === 2, `line ${line}`);

  // --- 8. Alt+Z and shown whitespace -------------------------------------------------
  await page.evaluate(() => {
    try { localStorage.removeItem("doc-code-wrap"); localStorage.removeItem("doc-whitespace"); } catch {}
  });
  await open("long.js", "js", `const s = "${"word ".repeat(80)}";\n\tlet t = 1;|`);
  const lines = () => page.evaluate(() => {
    const first = docCmView.contentDOM.querySelector(".cm-line");
    const h = first.getBoundingClientRect().height;
    const lh = parseFloat(getComputedStyle(first).lineHeight) || 20;
    return Math.round(h / lh);
  });
  const before = await lines();
  await page.keyboard.press("Alt+z");
  await page.waitForTimeout(250);
  const wrapped = await lines();
  ok("Alt+Z wraps a long line of code", before === 1 && wrapped > 1, J({ before, wrapped }));
  const rows = await page.evaluate(() => ({
    wrapBox: document.getElementById("doc-code-wrap").checked,
    wrapRowHidden: document.getElementById("doc-code-wrap-row").classList.contains("hidden"),
    stored: localStorage.getItem("doc-code-wrap"),
  }));
  ok("the menu's row agrees and it is remembered", rows.wrapBox === true && rows.wrapRowHidden === false && rows.stored === "1", J(rows));
  await page.keyboard.press("Alt+z");
  await page.waitForTimeout(250);
  ok("and Alt+Z again unwraps it", (await lines()) === 1);
  await page.evaluate(() => {
    const box = document.getElementById("doc-whitespace");
    box.checked = true;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForTimeout(250);
  const ws = await page.evaluate(() => ({
    spaces: document.querySelectorAll(".cm-highlightSpace").length,
    tabs: document.querySelectorAll(".cm-highlightTab").length,
    image: document.querySelector(".cm-highlightSpace") && getComputedStyle(document.querySelector(".cm-highlightSpace")).backgroundImage,
  }));
  ok("Show whitespace marks spaces and the tab", ws.spaces > 0 && ws.tabs === 1, J(ws));
  ok("in muted ink, not the library's grey", !!ws.image && !ws.image.includes("170, 170, 170"), J(ws.image));
  await page.evaluate(() => {
    const box = document.getElementById("doc-whitespace");
    box.checked = false;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await open("prose2.md", "md", "Words");
  const prose = await page.evaluate(() => ({
    wrapHidden: document.getElementById("doc-code-wrap-row").classList.contains("hidden"),
    wsHidden: document.getElementById("doc-whitespace-row").classList.contains("hidden"),
  }));
  ok("prose hides both rows", prose.wrapHidden && prose.wsHidden, J(prose));

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
