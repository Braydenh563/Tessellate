// DOCUMENTS_PLAN Phase 2's three deliberate omissions, measured and then
// decided (plan section 16).
//
// Two of them are questions about the caret and one is about a chip, and all
// three are the sort of thing a lint cannot see and a screenshot cannot
// settle. This walks the caret through a document with one of everything in
// it and reports, at each stop, what the toolbar says and where the caret
// actually landed.
//
//   1. **The toolbar's own state**: built. Every stop below asserts the
//      buttons that are on against the marks the caret is inside.
//   2. **Atomic ranges**: measured, and decided against. The numbers this
//      prints are the argument: see the plan.
//   3. **`Mod+click` on a link chip**: the affordance, measured as a cursor
//      and a tooltip rather than reasoned about.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  — " + d}`);
};

const DOC = [
  "# A heading",
  "",
  "Plain prose, then **a bold run**, then *an italic one*, then `some code`.",
  "",
  "## A second heading",
  "",
  "- a bullet",
  "- [ ] a task",
  "",
  "1. a number",
  "",
  "> a quote",
  "",
  "A [link to somewhere](https://example.com) in a sentence.",
  "",
].join("\n");

//: Where in the document to stand, and what the strip should say there. The
//: offsets are found by searching the text so a line added above cannot
//: silently move every expectation.
const STOPS = [
  //: Heading and quote have no strip button since DX6/DX26 (they are rows of
  //: Insert and Turn into, Ctrl+1 to 3 still set a heading), so the strip must
  //: stay unlit there; the guard below checks the buttons really are gone.
  { find: "A heading", into: 2, want: [] },
  { find: "Plain prose", into: 3, want: [] },
  { find: "a bold run", into: 4, want: ["bold"] },
  { find: "an italic one", into: 4, want: ["italic"] },
  { find: "some code", into: 4, want: ["code"] },
  { find: "A second heading", into: 3, want: [] },
  { find: "a bullet", into: 3, want: ["ul"] },
  { find: "a task", into: 3, want: ["task"] },
  { find: "a number", into: 3, want: ["ol"] },
  { find: "a quote", into: 3, want: [] },
  { find: "link to somewhere", into: 4, want: ["link"] },
];

(async () => {
  const { browser, page } = await boot();
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2200);
  await page.evaluate(async (text) => {
    const d = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: "Marks", content: text }),
    });
    await loadDocuments(d.id);
    setDocView("live");
  }, DOC);
  await page.waitForTimeout(2400);
  //: The strip is off until it is turned on, and it is a remembered
  //: preference, so this presses until it is shown rather than blindly.
  await page.evaluate(async () => {
    const el = document.getElementById("doc-toolbar");
    for (let press = 0; press < 2 && getComputedStyle(el).display === "none"; press += 1) {
      document.getElementById("doc-format-toggle").click();
      await new Promise((r) => setTimeout(r, 700));
    }
  });
  await page.waitForTimeout(700);

  const shown = await page.evaluate(() => {
    const el = document.getElementById("doc-toolbar");
    return {
      display: getComputedStyle(el).display,
      stateful: [...el.querySelectorAll("button[data-md]")].filter((b) => b.hasAttribute("aria-pressed")).length,
      total: el.querySelectorAll("button[data-md]").length,
    };
  });
  console.log("      strip:", JSON.stringify(shown));
  ok("the formatting strip is on screen", shown.display !== "none", shown.display);
  //: Only the buttons with a state to be in carry `aria-pressed`. A strip
  //: where every button claims to be a toggle lies to a screen reader.
  ok(
    "and only some of its buttons claim to be toggles",
    shown.stateful > 0 && shown.stateful < shown.total,
    `${shown.stateful} of ${shown.total}`
  );

  const gone = await page.evaluate(() =>
    ["h1", "h2", "h3", "quote"].filter((m) => document.querySelector(`#doc-toolbar button[data-md="${m}"]`)));
  ok("the strip has no heading or quote button (Turn into owns those)", gone.length === 0, JSON.stringify(gone));

  for (const stop of STOPS) {
    const seen = await page.evaluate((s) => {
      const text = docText();
      const at = text.indexOf(s.find) + s.into;
      docCmView.dispatch({ selection: { anchor: at } });
      return new Promise((r) =>
        setTimeout(() => {
          const bar = document.getElementById("doc-toolbar");
          r({
            at,
            //: Deduplicated: `#doc-toolbar` legitimately holds two buttons
            //: for some marks, the one in the strip and the one in the block
            //: menu it mounts, and both are lit by the same rule.
            on: [
              ...new Set(
                [...bar.querySelectorAll('button[data-md][aria-pressed="true"]')].map((b) => b.dataset.md)
              ),
            ].sort(),
          });
        }, 220)
      );
    }, stop);
    const same =
      seen.on.length === stop.want.length && stop.want.every((w) => seen.on.includes(w));
    ok(`in "${stop.find}" the strip says ${JSON.stringify(stop.want)}`, same, `it says ${JSON.stringify(seen.on)} at ${seen.at}`);
  }

  //: **The atomic-ranges measurement.** Walk the caret left to right across a
  //: bold run with the arrow key and record where it lands and how wide the
  //: line is at each step. The claim in the engine file is that entering the
  //: hidden `**` "means the caret appears to jump two characters"; this turns
  //: that into two numbers, the offsets visited and the line's rendered width
  //: before and inside the run, so the decision rests on what the walk costs
  //: rather than on how it is described.
  const walk = await page.evaluate(async () => {
    const text = docText();
    const start = text.indexOf("**a bold run**") - 2;
    docCmView.dispatch({ selection: { anchor: start } });
    docCmView.focus();
    const line = () => {
      const l = docCmView.dom.querySelector(".cm-line.cm-md-has-caret") ||
        docCmView.dom.querySelectorAll(".cm-line")[2];
      return Math.round(l.getBoundingClientRect().width);
    };
    const steps = [];
    for (let i = 0; i < 8; i += 1) {
      const head = docCmView.state.selection.main.head;
      const coords = docCmView.coordsAtPos(head);
      steps.push({ head, x: coords ? Math.round(coords.left) : null, w: line() });
      docCmView.dispatch({ selection: { anchor: head + 1 } });
      await new Promise((r) => setTimeout(r, 90));
    }
    return { start, steps };
  });
  console.log("      walking into a bold run:", JSON.stringify(walk.steps));
  //: Every offset is visited exactly once and in order: nothing is skipped,
  //: which is what "the caret can be put between the two asterisks" means and
  //: is precisely what atomic ranges would take away.
  const heads = walk.steps.map((s) => s.head);
  ok(
    "the caret visits every offset, skipping none",
    heads.every((h, i) => i === 0 || h === heads[i - 1] + 1),
    JSON.stringify(heads)
  );
  //: And the horizontal jump when the markers come back, which is the whole
  //: of the reported cost, in pixels.
  const jumps = walk.steps.map((s, i) => (i === 0 ? 0 : s.x - walk.steps[i - 1].x));
  console.log("      per-step x movement:", JSON.stringify(jumps));

  //: **And the reflow, which is what the note is actually about.** Entering
  //: the range reveals the hidden `**`, so everything after it on that line
  //: moves right by their width. Measured as the x of a word further along
  //: the same line with the caret outside the run and then inside it: that
  //: difference is the "appears to jump" in pixels, and it is the number the
  //: decision is made on.
  const reflow = await page.evaluate(async () => {
    const text = docText();
    const anchorWord = "italic";
    const at = (offset) => {
      docCmView.dispatch({ selection: { anchor: offset } });
      return new Promise((r) => setTimeout(r, 160));
    };
    const xOf = (offset) => {
      const c = docCmView.coordsAtPos(offset);
      return c ? Math.round(c.left) : null;
    };
    const later = text.indexOf(anchorWord);
    //: **On another line, not merely outside the run.** The reveal is decided
    //: per line, so a caret elsewhere on the same line has already brought the
    //: markers back and the two measurements are identical: an earlier draft
    //: of this probe stood at "Plain prose" and reported a 0px shift, which
    //: was true and about nothing.
    await at(text.indexOf("A heading"));
    const outside = xOf(later);
    await at(text.indexOf("a bold run") + 3);
    const inside = xOf(later);
    await at(text.indexOf("A heading"));
    return { outside, inside, shift: inside - outside };
  });
  console.log("      reflow when the markers come back:", JSON.stringify(reflow));
  ok(
    "entering a hidden range moves the rest of the line by the markers' width",
    Math.abs(reflow.shift) > 0,
    `${reflow.outside}px to ${reflow.inside}px, a shift of ${reflow.shift}px`
  );

  //: **The link chip's affordance.** The plan's note is that nothing says
  //: `Mod+click` opens a chip beyond the tooltip, so the tooltip is what gets
  //: measured: it either names the chord or it does not.
  const chip = await page.evaluate(() => {
    const el = docCmView.dom.querySelector(".cm-md-link, .cm-md-wiki, .cm-md-link-chip");
    if (!el) return { error: "no link chip in the live view" };
    const cs = getComputedStyle(el);
    return {
      cls: el.className,
      cursor: cs.cursor,
      title: el.getAttribute("title") || el.dataset.tip || null,
    };
  });
  console.log("      link chip:", JSON.stringify(chip));
  ok("a link renders as a chip in the live view", !chip.error, JSON.stringify(chip));
  //: The affordance, measured rather than argued about: a pointer cursor and
  //: a tooltip that names the chord and the target. The engine file's note
  //: said there was nothing "beyond the tooltip"; this says what the tooltip
  //: is, which is what the decision in section 16 rests on.
  ok(
    "the chip's tooltip names the chord",
    /ctrl\+click|cmd\+click/i.test(chip.title || ""),
    JSON.stringify(chip.title)
  );

  //: **The table cell menu's grouping** (section 16, the fourth item). Ten
  //: rows covering rows, columns, alignment and the table read as one list of
  //: ten; `kebabMenu` now draws a hairline wherever `group` changes.
  const menu = await page.evaluate(async () => {
    const text = docText();
    const table = ["", "| A | B |", "| --- | --- |", "| one | two |", ""].join("\n");
    docCmView.dispatch({ changes: { from: text.length, to: text.length, insert: table } });
    await new Promise((r) => setTimeout(r, 1000));
    //: **The caret has to be in the table.** The menu is a widget decoration
    //: on the row the caret is in, so with the caret anywhere else the table
    //: renders and there is no menu to open: the first run of this block
    //: reported "no table menu" and was reporting where the caret was.
    const body = docText();
    docCmView.dispatch({ selection: { anchor: body.indexOf("| one |") + 3 } });
    docCmView.focus();
    await new Promise((r) => setTimeout(r, 1200));
    const opener = docCmView.dom.querySelector(".cm-md-table-menu button");
    if (!opener) return { error: "no table menu in the live view" };
    opener.click();
    await new Promise((r) => setTimeout(r, 600));
    //: The open menu, found globally: `wireEscapedActionMenu` reparents it to
      //: the body so a scrolling or blurred ancestor cannot clip it, so it is
      //: no longer inside the `.menu-wrap` it was built in.
      const el =
        opener.closest(".menu-wrap").querySelector(".action-menu") ||
        document.querySelector(".action-menu:not(.hidden)");
      if (!el) return { error: "the menu did not open" };
    const sep = [...el.querySelectorAll(".menu-sep")];
    return {
      items: el.querySelectorAll(".menu-item").length,
      separators: sep.length,
      sepHeights: sep.map((s) => Math.round(s.getBoundingClientRect().height)),
      sepWidths: sep.map((s) => Math.round(s.getBoundingClientRect().width)),
      //: A separator must not be a keyboard stop, and must not be a menuitem.
      menuItemRoles: el.querySelectorAll('[role="menuitem"]').length,
      separatorRoles: el.querySelectorAll('[role="separator"]').length,
      order: [...el.children].map((c) => (c.classList.contains("menu-sep") ? "---" : c.textContent.trim())),
    };
  });
  console.log("      table menu:", JSON.stringify(menu));
  //: The menu grew from ten rows in four groups to two dozen (sort, filter, totals); the grammar is what is kept:
  //: at least the first four groups, a hairline only between rows, drawn one pixel tall, never a menu item.
  const seps = menu.separators || 0;
  const order = menu.order || [];
  ok("the table cell menu still offers its ten commands and more", menu.items >= 10, `${menu.items} items`);
  ok("in groups, so at least three hairlines", seps >= 3, `${seps} separators`);
  ok("and a hairline sits between rows, never first, last or doubled", order.length > 0 && order[0] !== "---" && order[order.length - 1] !== "---" && order.every((c, i) => c !== "---" || order[i - 1] !== "---"), JSON.stringify(order.slice(0, 5)));
  ok("each hairline is drawn and is one pixel tall", (menu.sepHeights || []).length === seps && (menu.sepHeights || []).every((h) => h === 1), JSON.stringify(menu.sepHeights));
  ok("and spans the menu's rows rather than collapsing", (menu.sepWidths || []).length === seps && menu.sepWidths.every((w) => w > 80), JSON.stringify(menu.sepWidths));
  ok("a hairline is a separator, never a menu item", menu.menuItemRoles === menu.items && menu.separatorRoles === seps, `${menu.menuItemRoles} menuitems, ${menu.separatorRoles} separators`);
  console.log("      menu order:", JSON.stringify(menu.order));

  console.log(bad ? `${bad} FAILURES` : "all clear");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
