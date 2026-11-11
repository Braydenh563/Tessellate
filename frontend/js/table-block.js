// table-block.js: the bar a table in a reply or a note wears (`buildTableBlock`:
// Copy, Markdown, CSV, Full view, the view toggle and the column grips), moved
// out of markdown.js on 2026-11-01 for the boot gzip budget
// (tests/test_static_compression.py, audit row 21). The markdown
// renderer (navigation.js) places the block with its table at once and this adds the bar when the
// bundle `tableBlock` (lazy-entries.js) has arrived.

//: **A table the model wrote is something you can take away** (INBOX 172:
//: "export, copy, or save etc things such as tables, code blocks etc that
//: the ai generates ... scrollable tables in responses are good but
//: sometimes hard or annoying to read, maybe the user can toggle how to
//: view the table"). The same bar the code blocks wear: Copy puts
//: tab-separated cells on the clipboard (what a spreadsheet pastes), Markdown
//: copies the table as written, CSV saves it through the exports route, and
//: Full view lifts the block into a viewport-sized panel (Escape or the same
//: button puts it back) so a wide table reads without the bubble's scroll.
//: `shell` is the block the renderer already placed (navigation.js), so the bar is added to the
//: element the page, its source line and its readers already hold; none is replaced.
function buildTableBlock(scroller, headers, bodyRows, rawTable, shell = null) {
  const block = shell || document.createElement("div");
  block.classList.add("code-block", "md-table-block");
  const bar = document.createElement("div");
  bar.className = "code-bar";
  const label = document.createElement("span");
  label.className = "code-lang";
  label.textContent = bodyRows.length ? `table · header and ${nounCount(bodyRows.length, "row")}` : "table · header only";
  //: The label gives way to the actions in a narrow bubble (it ellipsises), so its title says all of it.
  label.title = label.textContent;
  const cells = (row) => headers.map((_, c) => (row[c] || "").trim());
  const rows = [cells(headers), ...bodyRows.map(cells)];
  const tsv = rows.map((row) => row.map((v) => v.replace(/\t/g, " ")).join("\t")).join("\n");
  const csv = rows.map((row) => row.map((v) => `"${v.replace(/"/g, '""')}"`).join(",")).join("\n");
  const button = (text, title, onClick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small code-copy";
    //: `setLabel`, not `textContent`: the Copy button here said "⧉ Copy", a
    //: typed glyph standing where an icon belongs while the app ships
    //: `ph:copy` and uses it in five other places
    //: (`tests/test_no_glyph_icons.py` names the fault and now names this
    //: glyph). A label with no `ph:` marker comes through unchanged, so the
    //: bar's other buttons are untouched.
    setLabel(b, text);
    b.title = title;
    if (onClick) b.addEventListener("click", onClick);
    return b;
  };
  //: **Fit, or actual size** (INBOX 179: "I want the full view tables to not
  //: be scrollable and to instead adjust the size to fit the panel and for
  //: the full size scrollable view to be togglable"). Fit is the default:
  //: `table-layout: fixed` with wrapped cells, so every column is on screen
  //: and nothing scrolls sideways. The toggle puts the table back at its
  //: natural width, where the panel scrolls as before.
  //: **The reader sets the column widths and the row heights** (INBOX 181,
  //: the owner: "I want the table row and column widths and heights to be
  //: adjustable by the user in the full view"). A grip on every header cell's
  //: right edge and on every body row's bottom edge, in full view only: in a
  //: bubble the table is a few hundred pixels wide and there is nothing to
  //: apportion, and grips on a block that scrolls with the conversation would
  //: be six pixels of drag target next to a wheel.
  //:
  //: The sizes live on this closure, so they last as long as the answer does:
  //: leaving full view puts the table back to the surface's own default and
  //: returning restores what was dragged, which is what "for the session"
  //: means for a block that is rebuilt whenever its answer is re-rendered.
  const tableEl = scroller.querySelector("table");
  const headCells = () => [...tableEl.querySelectorAll("thead th")];
  const bodyRowEls = () => [...tableEl.querySelectorAll("tbody tr")];
  //: A column narrower than this cannot show a word and a row shorter than
  //: this cannot show a line, so neither is a size anybody meant to choose.
  const MIN_COL = 56;
  const MIN_ROW = 28;
  let colSizes = null;
  let rowSizes = null;

  const applyTableSizes = () => {
    if (!colSizes && !rowSizes) return;
    //: `table-layout: fixed` is what makes an explicit width authoritative:
    //: under `auto` the browser treats a width as a suggestion and widens a
    //: column whose content does not fit, which is exactly the drag not
    //: appearing to work.
    if (colSizes) {
      tableEl.style.tableLayout = "fixed";
      tableEl.style.width = `${colSizes.reduce((sum, n) => sum + n, 0)}px`;
      tableEl.style.minWidth = "0";
      headCells().forEach((th, i) => {
        th.style.width = `${colSizes[i]}px`;
      });
    }
    if (rowSizes) {
      bodyRowEls().forEach((tr, i) => {
        tr.style.height = `${rowSizes[i]}px`;
      });
    }
    //: The row grip lives in its row's first cell, because a `<span>` made a
    //: child of a `<tr>` gets wrapped in an anonymous table cell and shows up
    //: as a phantom column. It is given the table's width so the whole row's
    //: bottom edge is draggable rather than only the first column's.
    const width = tableEl.getBoundingClientRect().width;
    for (const grip of block.querySelectorAll(".md-grip-row")) {
      grip.style.width = `${width}px`;
    }
  };

  const stripTableSizes = () => {
    tableEl.style.tableLayout = "";
    tableEl.style.width = "";
    tableEl.style.minWidth = "";
    for (const th of headCells()) th.style.width = "";
    for (const tr of bodyRowEls()) tr.style.height = "";
  };

  const clearTableSizes = () => {
    colSizes = null;
    rowSizes = null;
    stripTableSizes();
  };

  const startGripDrag = (event, axis, index, grip) => {
    event.preventDefault();
    event.stopPropagation();
    //: Both axes are measured on the first drag of either, from what is on
    //: screen: half-measured sizes are how a table jumps on the second drag.
    if (!colSizes) colSizes = headCells().map((th) => th.getBoundingClientRect().width);
    if (!rowSizes) rowSizes = bodyRowEls().map((tr) => tr.getBoundingClientRect().height);
    block.dataset.tableView = "sized";
    applyTableSizes();
    const startX = event.clientX;
    const startY = event.clientY;
    const startW = colSizes[index];
    const startH = rowSizes[index];
    try {
      grip.setPointerCapture(event.pointerId);
    } catch {
      //: A synthetic pointer event has no capture to take; the listeners below
      //: still see the move because they are on the grip itself.
    }
    const move = (e) => {
      if (axis === "col") colSizes[index] = Math.max(MIN_COL, startW + (e.clientX - startX));
      else rowSizes[index] = Math.max(MIN_ROW, startH + (e.clientY - startY));
      applyTableSizes();
    };
    const end = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", end);
      grip.removeEventListener("pointercancel", end);
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
  };

  const gripFor = (axis, index, host) => {
    const grip = document.createElement("span");
    grip.className = `md-grip md-grip-${axis}`;
    grip.setAttribute("role", "separator");
    grip.setAttribute("aria-orientation", axis === "col" ? "vertical" : "horizontal");
    grip.title = axis === "col" ? "Drag to set this column's width" : "Drag to set this row's height";
    grip.addEventListener("pointerdown", (event) => startGripDrag(event, axis, index, grip));
    host.appendChild(grip);
  };

  const addGrips = () => {
    if (block.querySelector(".md-grip")) return;
    headCells().forEach((th, i) => gripFor("col", i, th));
    bodyRowEls().forEach((tr, i) => {
      if (tr.firstElementChild) gripFor("row", i, tr.firstElementChild);
    });
    applyTableSizes();
  };

  const removeGrips = () => {
    for (const grip of block.querySelectorAll(".md-grip")) grip.remove();
  };

  //: **And it has to do something in the bubble too** (INBOX 181, the owner:
  //: "the actual size/fit to panel button in ai written tables doesnt work
  //: when not in the full view"). It did not, and the cause was that every
  //: rule the toggle drove was written `.md-table-block.is-full:not(.is-actual)
  //: …`: pressing it in a bubble added a class nothing was listening for.
  //: Measured before the fix, inline: `table-layout: auto` and
  //: `overflow-x: auto` before the press and `table-layout: auto`,
  //: `overflow-x: auto` after it.
  //:
  //: The class became `data-table-view`, which is the state itself rather than
  //: "not the default", because the two surfaces have opposite defaults: a
  //: table in a bubble is at its natural width and scrolls sideways, and one
  //: in full view fits the panel (INBOX 179's decision, unchanged). One
  //: attribute with the same two values in both places is what makes the
  //: toggle mean the same thing wherever it is pressed.
  //: The wrap toggle is this attribute's switch (the old "Fit to panel" row
  //: of the ⋯, now an icon in the head): pressed is `fit`. A press in the
  //: bubble is remembered for the next table; one in full view is not, since
  //: full view starts fitted whatever the bubble was.
  const wrap = wrapToggle(
    "table",
    (on) => {
      //: A table the reader has dragged columns on is in neither state, so the
      //: toggle takes it back to one, dropping the sizes: the alternative is a
      //: button that appears to do nothing because the explicit widths win.
      clearTableSizes();
      block.dataset.tableView = on ? "fit" : "actual";
    },
    () => !block.classList.contains("is-full")
  );
  const setTableView = (view) => {
    block.dataset.tableView = view;
    wrap.paint(view === "fit");
  };
  const full = button("Full view", "Show this table on its own, at the window's width");
  //: The bubble's own start, said out loud rather than left as the absence of
  //: a class: a table in an answer is at its natural width and scrolls
  //: sideways unless the reader last chose to wrap.
  const bubbleView = () => (wrap.remembered() ? "fit" : "actual");
  //: A view the renderer's caller already chose (a digest's comparison is fitted) stands.
  setTableView(block.dataset.tableView || bubbleView());
  //: **The panel leaves the bubble to be full screen** (reported on the first
  //: cut, with a screenshot: "the table full view is behind a lot of stuff").
  //: A `position: fixed` element is laid out against the nearest ancestor
  //: with a filter, transform or backdrop-filter rather than against the
  //: viewport, and the chat card is a blurred surface: the panel was
  //: therefore trapped inside the card, under its own header, and no
  //: z-index could lift it out of that stacking context. So the block is
  //: moved to `document.body` while it is open and put back exactly where
  //: it was on the way out; `placeholder` is what keeps its place in the
  //: answer, since the surrounding prose has no other mark for it.
  let placeholder = null;
  //: **A panel with no visible way out is a panel people hard-refresh out of**
  //: (INBOX 239, the owner: "I opened up the table full view but there was no
  //: way to close it so I had to hard refresh the app"). Two things were true
  //: at once, and only the second one is a stylesheet's fault:
  //:
  //: - The only route out that was *drawn* was the ⋯ menu's last row, and in
  //:   full view it does not work. `kebabMenu` reparents its dropdown to
  //:   `<body>` to escape clipping ancestors (`wireEscapedActionMenu`), where
  //:   it is `position: fixed; z-index: 1020`, and this panel is a sibling of
  //:   it at `z-index: 2400`. Measured on :8802 in the documents tab: the Back
  //:   row drew at 1166,248 and `elementFromPoint` at its centre returned
  //:   `DIV.md-table-wrap`, so the click landed on the table and the panel
  //:   stayed open. Fixed at the source in `wireEscapedActionMenu`, which now
  //:   lifts an escaped menu above whatever surface its opener sits in.
  //: - Escape worked the whole time, and nothing said so. A keystroke nobody
  //:   is told about is not an affordance, so the panel gets the X every other
  //:   dismissable surface in this app has (`.sheet-close`'s shape, in the
  //:   bar that is already this panel's head) and it names the key in its
  //:   own tooltip.
  const close = smallButton("ph:x", "Close full view (Escape)", () => leave());
  //: `code-copy` is the bar's own segmented grammar, not a copy affordance:
  //: `.code-actions > .code-copy` is what strips a button's border and ground
  //: so it reads as one item of the shell rather than a chip dropped on it
  //: (the rule's own comment, in 05-sidebars-themes.css). Without it this X
  //: arrives as a bordered pill inside a tinted pill, which is the exact
  //: shape INBOX 188 was raised about.
  close.classList.add("code-copy", "md-table-close");
  close.hidden = true;
  //: Where the focus was when the panel opened, so leaving puts it back there
  //: rather than on `<body>`, which is where a removed button leaves it and
  //: from which the next Tab starts the page again.
  let returnFocusTo = null;
  const leave = () => {
    block.classList.remove("is-full");
    //: The dragged sizes stay in `colSizes`/`rowSizes` and come off the DOM:
    //: a bubble is not where a 900px-wide table belongs, and re-entering full
    //: view puts them straight back.
    removeGrips();
    stripTableSizes();
    setTableView(bubbleView());
    if (placeholder && placeholder.parentNode) {
      placeholder.replaceWith(block);
      placeholder = null;
    }
    full.textContent = "Full view";
    close.hidden = true;
    //: The menu is built below and reads these two labels; leaving full view
    //: by Escape has to put its rows back the way pressing Back would.
    syncMenuLabels();
    document.removeEventListener("keydown", onKey, true);
    //: Only when it is still on the page and still focusable: the block is
    //: re-parented on the way out, and an answer that re-rendered underneath
    //: the panel has taken its opener with it.
    if (returnFocusTo && returnFocusTo.isConnected) returnFocusTo.focus();
    returnFocusTo = null;
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      leave();
    }
  };
  full.addEventListener("click", () => {
    if (block.classList.contains("is-full")) return leave();
    //: Read before the move: `document.activeElement` is the ⋯ opener the row
    //: was chosen from, and one line later that button is inside a panel that
    //: has left its bubble.
    returnFocusTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    placeholder = document.createComment("table in full view");
    block.replaceWith(placeholder);
    document.body.appendChild(block);
    block.classList.add("is-full");
    //: Fit is full view's default (INBOX 179) and actual size is the bubble's,
    //: so the state is set on the way in rather than carried across.
    setTableView(colSizes || rowSizes ? "sized" : "fit");
    addGrips();
    full.textContent = "Back";
    close.hidden = false;
    //: The panel's own dismissal takes the focus, so Escape and Tab both act
    //: on the panel rather than on the page it covered, and a keyboard reader
    //: lands on the way out first.
    close.focus();
    document.addEventListener("keydown", onKey, true);
  });
  //: **One Copy button and a ⋯ for the rest** (INBOX 188, the owner: "the
  //: table button option rendering needs to be fixed or refined, especially
  //: in the popup agent, maybe just make it a copy button with an
  //: ellipse/kebab dropdown menu button next to it for the other options").
  //: Five labelled buttons in a row is a bar wider than most of the tables it
  //: sits on, and in the popup agent, which is a 293px card, it wrapped onto
  //: two lines above a three-column table. Copy is the one thing wanted often
  //: enough to cost a click; everything else is a `kebabMenu`, which is the
  //: recipe DESIGN.md's index gives for exactly this (standing order 11)
  //: rather than a second menu shape invented for one bar.
  //:
  //: `full` keeps its own element and its own handler and its row is a press
  //: on it, so the two places that rewrite its label (its own click, and
  //: `leave()`) go on working against the same node. Wrapping left the menu
  //: for the head (a ⋯ row hides a switch the reader wants to see the state of).
  const actions = document.createElement("span");
  actions.className = "code-actions";
  const menu = kebabMenu(
    [
      {
        label: "ph:markdown-logo Copy as markdown",
        title: "Copy the table as markdown",
        run: () => copyToClipboard(rawTable.join("\n")),
      },
      {
        label: "ph:note-pencil Save as a note",
        title: "File this table in your notebook as a new note",
        run: () => saveSelectionAsNote(rawTable.join("\n")),
      },
      {
        label: "ph:file-csv Save as CSV",
        title: "Save this table as a CSV file in the exports folder",
        run: () => saveFile(`table-${Date.now()}.csv`, new Blob([csv], { type: "text/csv" })),
      },
      { label: "ph:frame-corners", title: full.title, run: () => full.click() },
    ],
    "More table actions"
  );
  //: The two toggles' rows are found once and relabelled by the handlers that
  //: already own their wording, so the menu never says "Full view" for a table
  //: that is in full view.
  const menuRows = [...menu.querySelectorAll(".menu-item")];
  const fullRow = menuRows[3];
  const syncMenuLabels = () => {
    setLabel(fullRow, `ph:frame-corners ${full.textContent}`);
  };
  syncMenuLabels();
  full.addEventListener("click", syncMenuLabels);
  //: The button still exists, still carries the state, and is simply not in
  //: the bar: `leave()` writes to it on Escape, and the menu reads it back on
  //: the next open.
  full.hidden = true;
  actions.append(
    wrap.button,
    button("ph:copy Copy", "Copy the cells, tab-separated, for a spreadsheet", (event) => copyToClipboard(tsv, event.currentTarget)),
    menu,
    //: Last in the bar, which puts it at the panel's top-right corner, where
    //: every other X in this app is. Hidden in a bubble: there is nothing to
    //: close there.
    close,
    full
  );
  bar.append(label, actions);
  block.append(bar, scroller);
  return block;
}
