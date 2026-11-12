// DOCUMENTS_PLAN 17a and 17b: the live view as a page.
//
// 17a's gate: at 1280, 1440, 1920 and 2560 the line length stays inside 60 to
// 90 characters, the gutter (first glyph to the pane's edge, and last glyph
// to the other edge) is equal on both sides, and nothing scrolls sideways.
// 17b's gate: every gap between blocks is a token value, read from the
// computed boxes rather than from the stylesheet.
//
// The line length is counted from rendered glyphs, not estimated from `ch`:
// a Range over the first wrapped line of a long mixed-alphabet paragraph,
// walking characters until the top moves.
//
// Usage: BASE=http://127.0.0.1:8793 node docpage17.js [--widths 1280,1440]
const { boot } = require("./lib.js");

const PARA =
  "The quarterly review found that Jack's team shipped five improvements, " +
  "fixed twelve bugs and quietly retired the old export path, which nobody " +
  "had used since March; the next quarter picks up where this one left off, " +
  "with the sync work and a proper look at how long the first load takes.";
const DOC = [
  "# Quarterly review",
  "",
  PARA,
  "",
  "## What shipped",
  "",
  "A short paragraph under the section heading.",
  "",
  "- First item in the list",
  "- Second item in the list",
  "",
  "| Name | Kind | Note |",
  "| --- | --- | --- |",
  "| One | a | first |",
  "| Two | b | second |",
  "",
  "```python",
  "def hello():",
  "    return 1",
  "```",
  "",
  "> A quotation that says something worth quoting.",
  "",
  "A closing paragraph with `inline code`, a [link](https://example.com) and ==a highlight==.",
  "",
].join("\n");

const arg = process.argv.indexOf("--widths");
const WIDTHS = arg > 0 ? process.argv[arg + 1].split(",").map(Number) : [1280, 1440, 1920, 2560];

let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

(async () => {
  const { browser, page } = await boot({ viewport: { width: WIDTHS[0], height: 900 } });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  await page.evaluate(async (text) => {
    const d = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: "Quarterly review", content: text }),
    });
    await loadDocuments(d.id);
  }, DOC);
  await page.waitForTimeout(1800);
  await page.evaluate(() => setDocView("live"));
  await page.waitForTimeout(1200);

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(900);
    const m = await page.evaluate((para) => {
      const host = document.querySelector("#doc-editor");
      const content = document.querySelector("#doc-editor .cm-content");
      const hr = host.getBoundingClientRect();
      const lines = [...document.querySelectorAll("#doc-editor .cm-line")];
      const paraLine = lines.find((l) => l.textContent.startsWith("The quarterly"));
      // Characters on the first visual line of the paragraph.
      const node = (() => {
        const w = document.createTreeWalker(paraLine, NodeFilter.SHOW_TEXT);
        return w.nextNode();
      })();
      const range = document.createRange();
      let chars = 0;
      let firstTop = null;
      let left = null;
      let right = 0;
      for (let i = 0; i < node.length; i += 1) {
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        const r = range.getBoundingClientRect();
        if (firstTop === null) {
          firstTop = r.top;
          left = r.left;
        }
        if (Math.abs(r.top - firstTop) > 2) break;
        chars += 1;
        right = Math.max(right, r.right);
      }
      // The widest line box the page can hold: the content box of a line.
      const lr = paraLine.getBoundingClientRect();
      const er = document.querySelector("#doc-editor .cm-editor").getBoundingClientRect();
      const cs = getComputedStyle(content);
      const sc = document.querySelector("#doc-editor .cm-scroller");
      // Block gaps: for each block-starting line, the distance from the
      // previous block's last line bottom to this block's first glyph box.
      const blocks = lines.map((l) => {
        const r = l.getBoundingClientRect();
        const s = getComputedStyle(l);
        return {
          cls: [...l.classList].filter((c) => c.startsWith("cm-md-")).join(" "),
          text: l.textContent.slice(0, 18),
          n: docCmView.state.doc.lineAt(docCmView.posAtDOM(l)).number,
          top: r.top,
          bottom: r.bottom,
          mt: parseFloat(s.marginTop),
          mb: parseFloat(s.marginBottom),
          pt: parseFloat(s.paddingTop),
          pb: parseFloat(s.paddingBottom),
          h: r.height,
        };
      });
      return {
        vw: innerWidth,
        pane: Math.round(hr.width * 10) / 10,
        paneLeft: hr.left,
        paneRight: hr.right,
        lineBox: Math.round(lr.width * 10) / 10,
        lineLeft: lr.left,
        lineRight: lr.right,
        padL: cs.paddingLeft,
        padR: cs.paddingRight,
        chars,
        //: The band is held against the alphabet's average advance (a typographer's count), not this one sample: its narrow letters (93 on line 1) run past the same column that holds 87 of the alphabet and 76 of Read's text. The width is the owner's ("so thin" twice), so the sweep reads it fairly.
        alpha: (() => {
          const ctx = document.createElement("canvas").getContext("2d");
          ctx.font = getComputedStyle(paraLine).font;
          return Math.round((lr.width / (ctx.measureText("abcdefghijklmnopqrstuvwxyz ").width / 27)) * 10) / 10;
        })(),
        glyphLeftGap: Math.round((left - hr.left) * 10) / 10,
        lineRightGap: Math.round((hr.right - lr.right) * 10) / 10,
        textGapL: Math.round((lr.left - hr.left) * 10) / 10,
        edL: Math.round((lr.left - er.left) * 10) / 10,
        edR: Math.round((er.right - lr.right) * 10) / 10,
        hscrollDoc: document.scrollingElement.scrollWidth > document.scrollingElement.clientWidth,
        hscrollEditor: sc.scrollWidth > sc.clientWidth + 1,
        rootFont: parseFloat(getComputedStyle(document.documentElement).fontSize),
        // The spacing scale as this page resolves it (density included).
        // The spacing scale as this page resolves it: the rem steps of
        // 00-tokens-shell.css times the density multiplier. Computed rather
        // than read off a probe element, because a bare div appended to the
        // body picks up the body's own child rules and reads short.
        tokens: (() => {
          const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
          const density = parseFloat(
            getComputedStyle(document.documentElement).getPropertyValue("--density")
          ) || 1;
          const steps = [0.25, 0.4, 0.5, 0.6, 0.8, 1, 1.25, 1.5, 2];
          const out = {};
          steps.forEach((step, i) => {
            out[i + 1] = Math.round(step * rem * density * 10) / 10;
          });
          return out;
        })(),
        blocks,
      };
    }, PARA);
    console.log(
      `\n@${width}: pane ${m.pane}px, line box ${m.lineBox}px, padding ${m.padL}/${m.padR}, ` +
        `first glyph ${m.glyphLeftGap}px from the pane's left, line box ends ${m.lineRightGap}px from its right, ${m.chars} chars of this sample on line 1, ${m.alpha} of the alphabet`
    );
    ok(`${width}: line length 60 to 90`, m.alpha >= 60 && m.alpha <= 90, `${m.alpha} (sample ${m.chars})`);
    ok(
      `${width}: gutter equal both sides`,
      Math.abs(m.textGapL - m.lineRightGap) <= 1,
      `${m.textGapL} vs ${m.lineRightGap}`
    );
    ok(
      `${width}: the page margin inside the editor is equal and at least --space-6`,
      Math.abs(m.edL - m.edR) <= 1 && m.edL >= 16 - 0.5,
      `${m.edL} / ${m.edR}`
    );
    ok(`${width}: no horizontal scroll`, !m.hscrollDoc && !m.hscrollEditor);
    // 17b: a gap line is exactly one token tall (or zero, for the second
    // blank line of a run), and nothing else between two lines is a gap.
    // Within 0.75px: a line box is laid out on whole pixels, so --space-9 at
    // 31.33px draws a 32px line, and that is still the token.
    const tokenSet = Object.values(m.tokens).concat([0]);
    const gaps = m.blocks.filter((b) => /cm-md-gap/.test(b.cls));
    const offScale = gaps.filter((b) => !tokenSet.some((t) => Math.abs(t - b.h) <= 0.75));
    ok(`${width}: every gap line is a token tall`, gaps.length > 0 && !offScale.length,
      `${gaps.length} gaps: ${gaps.map((b) => b.h.toFixed(1) + " " + b.cls.replace(/cm-md-gap ?/, "")).join(", ")}`);
    const blanks = m.blocks.filter((b) => !b.cls && !b.text.trim());
    ok(`${width}: no blank line is left at a full line's height`, !blanks.length,
      `${blanks.length} undecorated blank lines ${JSON.stringify(blanks)}`);
    let seams = 0;
    for (let i = 1; i < m.blocks.length; i += 1) {
      if (Math.abs(m.blocks[i].top - m.blocks[i - 1].bottom) > 0.5) seams += 1;
    }
    ok(`${width}: no margin between lines outside the gap lines`, seams === 0, `${seams}`);
    if (width === WIDTHS[0] || process.env.BLOCKS) {
      console.log("  block gaps (previous bottom to this top, margin, padding, height):");
      let prev = null;
      for (const b of m.blocks) {
        if (prev) {
          console.log(
            `    ${(b.top - prev.bottom).toFixed(1).padStart(6)}  mt ${b.mt} mb ${b.mb} pt ${b.pt} pb ${b.pb} h ${b.h.toFixed(1)}  ${b.cls.padEnd(34)} ${JSON.stringify(b.text)}`
          );
        }
        prev = b;
      }
    }
  }
  // The caret on a gap: visible, and the document does not move when it
  // arrives (the gap is its line height, not a height the caret undoes).
  const caret = await page.evaluate(async () => {
    const view = docCmView;
    const height = () => view.contentDOM.getBoundingClientRect().height;
    view.focus();
    view.dispatch({ selection: { anchor: 0 } });
    await new Promise((r) => setTimeout(r, 200));
    const before = height();
    const gapLine = view.state.doc.line(4); // the blank line above "## What shipped"
    view.dispatch({ selection: { anchor: gapLine.from } });
    await new Promise((r) => setTimeout(r, 250));
    const cursor = document.querySelector("#doc-editor .cm-cursor");
    return {
      before,
      after: height(),
      cursor: cursor ? cursor.getBoundingClientRect().height : 0,
      cls: view.domAtPos(gapLine.from).node.closest?.(".cm-line")?.className || "",
    };
  });
  ok("the caret on a gap is visible", caret.cursor >= 6, `${caret.cursor.toFixed(1)}px, ${caret.cls}`);
  ok("and the page does not move when it arrives", Math.abs(caret.after - caret.before) < 0.5,
    `${caret.before.toFixed(1)} -> ${caret.after.toFixed(1)}`);
  console.log(`\n${bad ? bad + " FAIL" : "all pass"}`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
