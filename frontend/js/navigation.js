// navigation.js: long-press, list conventions, tabs, back and forward,
// sub-tabs, back to top, overlay scroll lock. Moved out of app.js on 2026-09-26
// as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

//: Touch has no right-click, so a hold stands in, at the same 500ms the
//: whiteboard's own link gesture uses (`wbWireMapEdgeGestures`) so the app
//: answers a long press at one speed. Cancelled by a move, because a hold
//: that turns into a scroll is a scroll.
// --- a long-press is a right-click on a phone (UI Phase 11 item 9) ------------
// A finger has no second button. Every right-click menu in the app gets the
// same menu on a 500ms hold that neither moves nor lifts; `target` is the
// element the hold is on, or `document` with a `selector` for holds that
// land on elements built later (a link inside a rendered note). The handler
// receives the pointer event of the press and the point to open at. Touch
// only: a mouse held down is a drag waiting to happen, and it has the
// button. `tests/test_ui_recipes.py` holds every contextmenu listener in
// app.js and documents.js to a wireLongPress twin.
const LONG_PRESS_MS = 500;
const LONG_PRESS_CANCELS = ["pointerup", "pointercancel", "pointermove"];

function wireLongPress(target, handler, { selector = null } = {}) {
  if (!target) return;
  target.addEventListener(
    "pointerdown",
    (event) => {
      if (event.pointerType !== "touch") return;
      const hit = selector
        ? event.target instanceof Element && event.target.closest(selector)
        : target;
      if (!hit) return;
      const { clientX, clientY } = event;
      const cancel = () => {
        clearTimeout(timer);
        for (const name of LONG_PRESS_CANCELS) {
          document.removeEventListener(name, cancel, true);
        }
      };
      const timer = setTimeout(() => {
        cancel();
        //: **The lift-off is swallowed.** A hold ends like every other touch,
        //: with a click, and the element under it is the element the hold was
        //: about: measured on the graph at 390, holding a node opened its menu
        //: and lifting the finger opened that node's panel underneath it, so
        //: the gesture did two things and the second one took the focus the
        //: menu had just been given (the menu was still open, and Escape
        //: closed the panel instead of it). Captured, so it never reaches the
        //: surface, and `once` so only that one click is taken; the timer is
        //: the belt for a press that ends in a `pointercancel` and therefore
        //: sends no click at all, which would otherwise leave the swallow
        //: waiting for the *next* tap, on a menu row.
        //: All three of the mouse events a tap synthesises, not the click
        //: alone: Chromium sends `mousedown`, `mouseup` and `click` when the
        //: finger lifts, and it is the first of them that moves the focus.
        //: Measured on the graph: with only the click taken, the menu opened
        //: with its first row focused and the lift then put the focus on
        //: `#graph-box`, so Escape reached the map instead of the menu and
        //: the menu stayed open. `preventDefault` on the `mousedown` is what
        //: leaves the focus where the hold put it.
        const swallowed = ["mousedown", "mouseup", "click"];
        const done = () => {
          for (const type of swallowed) document.removeEventListener(type, swallow, true);
        };
        const swallow = (lift) => {
          lift.preventDefault();
          lift.stopPropagation();
          if (lift.type === "click") done();
        };
        for (const type of swallowed) document.addEventListener(type, swallow, true);
        setTimeout(done, 1200);
        handler(event, { x: clientX, y: clientY, el: hit });
      }, LONG_PRESS_MS);
      for (const name of LONG_PRESS_CANCELS) {
        document.addEventListener(name, cancel, { capture: true, passive: true });
      }
    },
    { passive: true }
  );
}

wireLongPress(
  document,
  (event, point) => {
    const found = linkAtEvent(event);
    if (found) openMenuAtPoint(found.items, "Link actions", point.x, point.y);
  },
  { selector: "a[href], .wiki-link" }
);

// --- the conventions a list is expected to keep (pass2.md, micro-conventions)
//
// Measured in the running app before any of this existed (1440, Quiet, a
// seeded notebook): a right-click on a Library card, a Documents row or a
// note opened the browser's own menu; the arrow keys did nothing on a
// Library card; Shift+click ticked one box, not the run between two; Ctrl+A
// with a selection open selected the page's text (1,876 characters) instead
// of the rows; Escape left the selection where it was. Every file manager,
// mail client and photo library does all five, so their absence reads as
// the app being unfinished rather than as a choice.
//
// One section, delegated from the document, for the same reason the link
// menu above is one listener: the lists are rebuilt on every render and a
// listener per row is a listener some render forgets.

//: The rows that carry their own ⋯. A right-click (or a hold, on a phone)
//: anywhere on one opens that same menu, so what the row can do is found the
//: way people look for it first.
const ROW_MENU_HOSTS = [
  //: First, so a right-click on a file inside a note card opens the file's
  //: menu rather than the note's (`closest` takes the nearest match).
  ".att-card",
  ".library-card",
  ".doc-list-item",
  ".bookmark-row",
  ".library-image-tile",
  "#entry-list > li[data-id]",
  "#conversation-list > li",
  "#web-results .web-result",
].join(", ");

function rowMenuAtEvent(event) {
  const target = event.target;
  if (!(target instanceof Element)) return null;
  //: Where the browser's menu is the right one, it stays: a field (spelling,
  //: paste), a link (the link menu above), a menu already open, and a
  //: selection somebody made to copy.
  if (target.closest("input, textarea, select, [contenteditable='true'], a[href], .wiki-link, .action-menu, [data-chip-menu]")) {
    return null;
  }
  if (String(window.getSelection?.() || "").trim()) return null;
  const host = target.closest(ROW_MENU_HOSTS);
  if (!host) return null;
  const opener = [...host.querySelectorAll('.menu-wrap > [aria-haspopup="menu"]')].find(
    (button) => button.closest(ROW_MENU_HOSTS) === host
  );
  return opener ? { host, opener } : null;
}

//: At the pointer when the menu's items are known (every `kebabMenu`), and
//: from the row's own ⋯ otherwise (a note's menu builds its rows on first
//: open and carries flyouts, so it is opened the way its button opens it).
function openRowMenu(opener, x, y) {
  const wrap = opener.closest(".menu-wrap");
  if (wrap && wrap.rowMenu) openMenuAtPoint(wrap.rowMenu.items, wrap.rowMenu.ariaLabel, x, y);
  else opener.click();
}

document.addEventListener("contextmenu", (event) => {
  if (event.defaultPrevented) return;
  const found = rowMenuAtEvent(event);
  if (!found) return;
  event.preventDefault();
  openRowMenu(found.opener, event.clientX, event.clientY);
});

wireLongPress(
  document,
  (event, point) => {
    const found = rowMenuAtEvent(event);
    if (found) openRowMenu(found.opener, point.x, point.y);
  },
  { selector: ROW_MENU_HOSTS }
);

//: **F2 renames**, the desktop convention for "rename the thing I am on",
//: here because a double-click cannot: a single click on every one of these
//: rows opens it, so the first half of a double-click would already have
//: left the list. Runs the row's own Rename item, so there is one rename.
document.addEventListener("keydown", (event) => {
  if (event.key !== "F2" || event.defaultPrevented) return;
  const host = event.target instanceof Element ? event.target.closest(ROW_MENU_HOSTS) : null;
  if (!host) return;
  const wrap = host.querySelector(".menu-wrap");
  const item = wrap?.rowMenu?.items.find((it) => /^ph:\S+ Rename\b/.test(it.label || ""));
  if (!item) return;
  event.preventDefault();
  item.run();
});

//: **Arrow keys between cards and rows, Home and End to the ends.** Chosen by
//: where the items are drawn rather than by their order in the DOM: the
//: Library's cards are dealt into columns (library.js), so the card beside
//: this one is in another column element, and a Rows list and a grid of
//: tiles are the same code. Only when the focus is on an item itself, so a
//: field or a button inside one keeps its own keys.
const ARROW_NAV_LISTS = [
  //: A card's one stop is its title (`cardOpener`, INBOX 433), so that is
  //: what the keys move between; the card is a box, not a control.
  ["#library-grid", ".library-card .card-open"],
  ["#library-boards-grid", ".library-card .card-open"],
  ["#library-docs-list", ".doc-list-item .card-open"],
  ["#library-images-grid", ".library-image-tile [role='button'][tabindex='0']"],
  ["#bookmark-list", ".bookmark-title"],
  //: The Web panel's results: the title is each row's one tab stop, and the
  //: field above hands the focus down with ArrowDown (app.js, `web-query`).
  ["#web-results", ".web-result-title"],
];

function arrowNavTarget(items, current, key) {
  if (key === "Home") return items[0];
  if (key === "End") return items[items.length - 1];
  const from = current.getBoundingClientRect();
  const cx = from.left + from.width / 2;
  const cy = from.top + from.height / 2;
  let best = null;
  let bestScore = Infinity;
  for (const item of items) {
    if (item === current) continue;
    const r = item.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    const dx = x - cx;
    const dy = y - cy;
    //: In the direction pressed, past the current item's own edge, and
    //: nearest along that axis first, then across it.
    let along;
    let across;
    if (key === "ArrowRight") { if (r.left < from.right - 1) continue; along = dx; across = Math.abs(dy); }
    else if (key === "ArrowLeft") { if (r.right > from.left + 1) continue; along = -dx; across = Math.abs(dy); }
    else if (key === "ArrowDown") { if (r.top < from.bottom - 1) continue; along = dy; across = Math.abs(dx); }
    else { if (r.bottom > from.top + 1) continue; along = -dy; across = Math.abs(dx); }
    const score = across * 2 + along;
    if (score < bestScore) { bestScore = score; best = item; }
  }
  return best;
}

document.addEventListener("keydown", (event) => {
  if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const target = event.target;
  if (!(target instanceof Element)) return;
  for (const [listSel, itemSel] of ARROW_NAV_LISTS) {
    const list = target.closest(listSel);
    if (!list || !target.matches(itemSel)) continue;
    const items = [...list.querySelectorAll(itemSel)].filter((el) => el.offsetParent);
    const next = arrowNavTarget(items, target, event.key);
    event.preventDefault();
    if (next) {
      next.focus({ preventScroll: true });
      next.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    return;
  }
});

//: **Shift+click ticks the run.** The second tick of a Shift+click sets every
//: tick between it and the one ticked before it to its own state, through
//: each tick's own `change` handler, so every list's own set stays the one
//: place that owns its selection. Works on the tick and on a note card in
//: select mode alike, because both end in the tick's `change`.
const RANGE_TICKS = ".library-card-tick, .doc-list-tick, .library-tile-tick, #entry-list .select-check";
const RANGE_LISTS = "#library-grid, #library-boards-grid, #library-docs-list, #library-images-grid, #bookmark-list, #entry-list";
let rangeShiftHeld = false;
let rangeAnchor = null;
let rangeApplying = false;

document.addEventListener("click", (event) => { rangeShiftHeld = event.shiftKey; }, true);
//: A tick toggled from the keyboard is never a range, whatever the last
//: click held.
document.addEventListener("keydown", () => { rangeShiftHeld = false; }, true);

document.addEventListener("change", (event) => {
  const tick = event.target;
  if (rangeApplying || !(tick instanceof HTMLInputElement) || !tick.matches(RANGE_TICKS)) return;
  const list = tick.closest(RANGE_LISTS);
  if (!list) return;
  const anchor = rangeAnchor;
  rangeAnchor = tick;
  if (!rangeShiftHeld || !anchor || !anchor.isConnected || anchor.closest(RANGE_LISTS) !== list) return;
  //: In the order the rows are drawn, not the DOM's: the Library's columns
  //: put its cards in column order.
  const ticks = [...list.querySelectorAll(RANGE_TICKS)].filter((t) => t.closest(RANGE_LISTS) === list);
  const pos = (t) => {
    const r = t.getBoundingClientRect();
    return [Math.round(r.top), Math.round(r.left)];
  };
  ticks.sort((a, b) => {
    const [at, al] = pos(a);
    const [bt, bl] = pos(b);
    return Math.abs(at - bt) > 8 ? at - bt : al - bl;
  });
  const from = ticks.indexOf(anchor);
  const to = ticks.indexOf(tick);
  if (from === -1 || to === -1) return;
  rangeApplying = true;
  try {
    for (const other of ticks.slice(Math.min(from, to), Math.max(from, to) + 1)) {
      if (other === tick || other.checked === tick.checked) continue;
      other.checked = tick.checked;
      other.dispatchEvent(new Event("change", { bubbles: true }));
      other.closest("li")?.classList.toggle("is-selected", other.checked);
    }
  } finally {
    rangeApplying = false;
  }
});

//: **Escape, Ctrl+A and Delete while a selection is open.** The Library's
//: sub-tabs each show a select bar while anything is ticked; the Notes list
//: has its select mode. Each key presses the bar's own control (Done, Select
//: all, Delete), so the keyboard does exactly what the pointer does, the
//: same confirm or the same Undo included. Never from inside a field, where
//: all three keys already mean something.
function openSelectionScope() {
  const bar = [...document.querySelectorAll("#tab-library .selectbar:not(.hidden)")].find((b) => b.offsetParent);
  if (bar) {
    return {
      clear: () => bar.querySelector('[id$="-clear-selection"]')?.click(),
      selectAll: () => {
        const listId = bar.querySelector("[data-select-all-for]")?.dataset.selectAllFor;
        const list = listId ? document.getElementById(listId) : bar.parentElement;
        const ticks = list ? [...list.querySelectorAll(RANGE_TICKS)] : [];
        if (ticks.some((t) => !t.checked)) bar.querySelector("[data-select-all-for]")?.click();
      },
      remove: () => bar.querySelector('[id$="-bulk-delete"]')?.click(),
    };
  }
  if (typeof selectMode !== "undefined" && selectMode && $("tab-notes") && !$("tab-notes").classList.contains("hidden")) {
    return {
      clear: () => exitSelectMode(),
      selectAll: () => {
        const rows = libraryVisibleRows();
        if (rows.some((row) => !selectedIds.has(row.id))) toggleSelectAllRows(rows, renderEntries);
      },
      remove: () => batchDelete(),
    };
  }
  return null;
}

document.addEventListener("keydown", (event) => {
  if (event.defaultPrevented || event.altKey) return;
  const el = event.target;
  if (el instanceof Element && (el.closest("input:not([type='checkbox']), textarea, select, [contenteditable='true']") || el.closest(".modal-overlay:not(.hidden)"))) {
    return;
  }
  const mod = event.ctrlKey || event.metaKey;
  const isSelectAll = mod && !event.shiftKey && event.key.toLowerCase() === "a";
  const isEscape = event.key === "Escape" && !mod;
  const isDelete = (event.key === "Delete" || (event.key === "Backspace" && event.metaKey)) && !event.shiftKey;
  if (!isSelectAll && !isEscape && !isDelete) return;
  //: An open menu or popover owns Escape first.
  if (isEscape && document.querySelector(".action-menu:not(.hidden), details[open].dock-menu")) return;
  const scope = openSelectionScope();
  if (!scope) return;
  event.preventDefault();
  if (isSelectAll) scope.selectAll();
  else if (isEscape) scope.clear();
  else scope.remove();
});

function renderMarkdown(container, text, depth = 0) {
  container.replaceChildren();
  let lines = unlatex(text).replace(/\r\n/g, "\n").split("\n");
  const footnotes = depth === 0 ? mdFootnotePrepare(lines) : null;
  if (footnotes) lines = footnotes.lines;
  //: The text before `unlatex` swapped its symbols, line for line (it never
  //: crosses a newline): a `$$` block is handed to the maths renderer as it
  //: was written, not with `\alpha` already turned into a letter.
  const rawLines = String(text ?? "").replace(/\r\n/g, "\n").split("\n");
  let i = 0;
  let list = null; // the <ul>/<ol> currently being filled, or null
  const headingIds = new Set(); // so two "Notes" headings get distinct anchors

  //: **Which source line each rendered block came from**, written on the
  //: block as `data-src-line`. The split document view needs it to line its
  //: two panes up: a scroll fraction is exact at both ends and wrong
  //: everywhere a picture, a table or a code fence takes a different amount
  //: of room in the two halves, which is the owner's report of 2026-09-20
  //: ("the scrolling is off in the split document view because of the md
  //: rendering"). See `docScrollAnchors` in documents.js.
  //:
  //: Stamped here rather than worked out afterwards, because this loop is the
  //: only thing that knows which lines produced which element. Any other
  //: answer is a second parser standing beside this one, and two parsers
  //: disagree the first time either is changed.
  //:
  //: The bookkeeping is deliberately outside the branches: a block is
  //: appended at eight different points in this loop, several of them after
  //: `i` has already moved past the lines they consumed, so the line is
  //: remembered at the top of the iteration and everything the iteration
  //: appended is stamped at the top of the next one. A list is the exception,
  //: since `closeList` appends it in a later iteration than the one that
  //: started it, so it carries its own start line.
  let blockLine = 0;
  let listLine = 0;
  let stamped = 0;
  const stampNewBlocks = () => {
    while (stamped < container.childElementCount) {
      container.children[stamped].dataset.srcLine = String(blockLine);
      stamped += 1;
    }
  };

  const closeList = () => {
    if (list) {
      list.dataset.srcLine = String(listLine);
      container.appendChild(list);
      stamped = container.childElementCount;
    }
    list = null;
  };

  while (i < lines.length) {
    stampNewBlocks();
    blockLine = i;
    const line = lines[i];

    // Fenced code block. Gets a header strip with the language (when the
    // fence names one) and a copy button: selecting a code block by hand is
    // the one thing every other chat interface saves you from, and getting
    // it slightly wrong, a stray line, a missing last character, is the
    // kind of mistake you only notice after pasting it somewhere.
    if (line.trim().startsWith("```")) {
      closeList();
      const language = line.trim().slice(3).trim().split(/\s+/)[0] || "";
      const code = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i++;
      }
      i++; // skip the closing fence
      const text = code.join("\n");

      const block = document.createElement("div");
      block.className = "code-block";
      const bar = document.createElement("div");
      bar.className = "code-bar";
      const label = document.createElement("span");
      label.className = "code-lang";
      label.textContent = language || "code";
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "ghost small code-copy";
      //: The app's own copy icon, not a typed `⧉`: see the note on the table
      //: bar's `button` helper above, and `tests/test_no_glyph_icons.py`.
      setLabel(copy, "ph:copy Copy");
      copy.title = "Copy this code block";
      copy.addEventListener("click", (event) =>
        copyToClipboard(text, event.currentTarget)
      );
      //: Save as a file too (INBOX 172: "export, copy, or save etc things
      //: such as tables, code blocks etc that the ai generates"): through
      //: the app's own save route, so it lands in the exports folder and in
      //: the bell like every other export.
      const save = document.createElement("button");
      save.type = "button";
      save.className = "ghost small code-copy";
      //: With its own icon, because the pair sit in one bar: an icon beside
      //: "Copy" and nothing beside "Save" reads as two different kinds of
      //: control. `ph:download-simple` is what the app already puts on a
      //: "Save this to your computer" (the image reader's, app.js ~6328).
      setLabel(save, "ph:download-simple Save");
      save.title = "Save this code block to the exports folder";
      save.addEventListener("click", () =>
        saveFile(`code-${Date.now()}.${language || "txt"}`, new Blob([text], { type: "text/plain" }))
      );
      const actions = document.createElement("span");
      actions.className = "code-actions";
      actions.append(copy, save);
      bar.append(label, actions);

      const pre = document.createElement("pre");
      const codeEl = document.createElement("code");
      if (language) codeEl.dataset.lang = language;
      codeEl.textContent = text;
      pre.appendChild(codeEl);
      block.append(bar, pre);
      container.appendChild(block);
      continue;
    }

    // GFM pipe table: a row of "| … |" immediately followed by a
    // "| --- | --- |" separator turns into a real <table>.
    if (
      line.includes("|") &&
      i + 1 < lines.length &&
      isTableSeparator(lines[i + 1])
    ) {
      closeList();
      const headers = splitTableRow(line);
      const aligns = splitTableRow(lines[i + 1]).map(columnAlign);
      const rawTable = [line, lines[i + 1]]; // as written, for "copy as markdown"
      i += 2; // consume header + separator
      const bodyRows = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        rawTable.push(lines[i]);
        bodyRows.push(splitTableRow(lines[i]));
        i++;
      }
      const table = document.createElement("table");
      table.className = "md-table";
      const thead = document.createElement("thead");
      const headTr = document.createElement("tr");
      headers.forEach((cell, c) => {
        const th = document.createElement("th");
        if (aligns[c]) th.style.textAlign = aligns[c];
        appendInline(th, cell.trim());
        headTr.appendChild(th);
      });
      thead.appendChild(headTr);
      table.appendChild(thead);
      const tbody = document.createElement("tbody");
      for (const row of bodyRows) {
        const tr = document.createElement("tr");
        for (let c = 0; c < headers.length; c++) {
          const td = document.createElement("td");
          if (aligns[c]) td.style.textAlign = aligns[c];
          appendInline(td, (row[c] || "").trim());
          tr.appendChild(td);
        }
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      // Let wide tables scroll sideways instead of breaking the layout.
      const scroller = document.createElement("div");
      scroller.className = "md-table-wrap";
      scroller.appendChild(table);
      container.appendChild(buildTableBlock(scroller, headers, bodyRows, rawTable));
      continue;
    }

    //: **Columns, side by side, in every view** (INBOX 421 b). This used to
    //: be the document editor's alone (`docRenderBody` splits them before
    //: this renderer runs), so the same text was two columns in a document
    //: and three lines of `:::` in a note or a chat answer. Each column is
    //: rendered by this function, one level deeper, so a column holds lists,
    //: callouts and code like the page around it.
    const columns = depth < MD_MAX_DEPTH ? mdColumnsFrom(lines, i) : null;
    if (columns) {
      closeList();
      container.appendChild(
        mdColumnsElement(columns.columns, (host, body) => renderMarkdown(host, body, depth + 1))
      );
      i = columns.end;
      continue;
    }

    //: `[TOC]`: a placeholder, filled once the whole text is rendered
    //: (`mdFillTocs`), because the headings it lists are below it.
    if (MD_TOC_LINE.test(line)) {
      closeList();
      container.appendChild(mdTocElement());
      i++;
      continue;
    }

    //: Display maths, `$$` to `$$`. Drawn by the document editor's own TeX to
    //: MathML renderer (`docMathRender`, documents.js) when it is loaded,
    //: which it always is under a document; elsewhere the source stands in a
    //: maths-set block rather than being mangled.
    const maths = mdMathBlockFrom(rawLines, i);
    if (maths) {
      closeList();
      container.appendChild(mdMathElement(maths.tex));
      i = maths.end;
      continue;
    }

    // Horizontal rule: ---, ***, or ___ on their own line. The three draw
    // differently here (a hairline, a three-dot section break, a strong
    // rule) and are one `<hr>` to every other reader.
    if (MD_PAGE_BREAK.test(line)) {
      closeList();
      container.appendChild(mdPageBreakElement());
      i++;
      continue;
    }
    const rule = mdDividerKind(line);
    if (rule) {
      closeList();
      container.appendChild(mdRuleElement(rule));
      i++;
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeList();
      // Map #→h3 … ######→h6 (the app reserves h1/h2 for its own chrome).
      const level = Math.min(6, heading[1].length + 2);
      const el = document.createElement(`h${level}`);
      //: **And the source level as a class, because the tag has lost it.**
      //: Demoting by two is right for the document outline and wrong for
      //: everything else: three source levels (`####`, `#####`, `######`) all
      //: land on `h6`, and nothing in the stylesheet catches `h5` or `h6` at
      //: all, so they fall through to the browser's own defaults, which are
      //: *smaller than body text*. Measured in the rendered pane against a
      //: 16px paragraph: `# Heading one` 12px, `## Heading two` 16px, `###`
      //: 13.3px, `####` and `#####` both 10.7px. The document's largest
      //: heading was its smallest text, and two levels were identical.
      //:
      //: The live view of the same document is 28.8 / 24 / 20 / 17.6, so the
      //: two views of one file disagreed about what a heading is. `md-h1`..
      //: `md-h6` carry the level the person actually typed, and the
      //: stylesheet keys the scale off that.
      el.classList.add(`md-h${heading[1].length}`);
      // An id makes the heading a real jump target, for the outline and for
      // any [](#anchor) link written into the text.
      el.id = mdHeadingId(heading[2], headingIds);
      appendInline(el, heading[2]);
      container.appendChild(el);
      i++;
      continue;
    }

    // Transclusion: a line that is nothing but ![[name]] inlines that note's
    // text here, rather than linking to it. This is what makes a document
    // genuinely *composed of* notes instead of merely pointing at them.
    //
    // **Notes only, deliberately.** GET /documents returns id/title/words and
    // no content (routes_documents._summary), so embedding a document would
    // need a fetch: and renderMarkdown runs on every streamed chat chunk, so
    // a fetch in this path is a request storm waiting to happen. A document
    // target therefore renders as a labelled link, and the inline version
    // waits for a content-bearing endpoint rather than being bolted on here.
    const embedded = line.match(/^\s*!\[\[([^[\]]{1,120})\]\]\s*$/);
    if (embedded) {
      closeList();
      const name = embedded[1].trim();
      container.appendChild(mdEmbedElement(name, depth));
      i++;
      continue;
    }

    // Blockquote, and its dressed-up form the callout.
    //
    // `> [!warning] Watch out` on the first quoted line turns the whole quote
    // into a titled box. The syntax is GitHub/Obsidian's, chosen because it
    // degrades to an ordinary blockquote everywhere else, a note that leaves
    // this app stays readable, which a custom fence would not.
    if (/^\s*>\s?/.test(line)) {
      closeList();
      const quoted = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quoted.push(lines[i].replace(/^\s*>\s?/, ""));
        i++;
      }

      const box = mdCalloutElement(quoted, depth);
      if (box) {
        container.appendChild(box);
        continue;
      }

      //: `-- Name` as the quote's last line is its attribution: a figure
      //: with the words and a caption, which is how a pull quote is marked
      //: up, and still a quote with a signature line to any other reader.
      container.appendChild(mdQuoteElement(quoted, (host, body) => appendInline(host, body.join(" "))));
      continue;
    }

    const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+\.\s+(.*)$/);
    if (bullet || numbered) {
      const wantOrdered = Boolean(numbered);
      if (!list || (list.tagName === "OL") !== wantOrdered) {
        closeList();
        list = document.createElement(wantOrdered ? "ol" : "ul");
        listLine = i;
        // Start where the author started. Without this a list written as
        // "3. 4. 5." renders as 1, 2, 3, and, more importantly, a list that
        // resumes after a paragraph restarts from 1.
        if (wantOrdered) {
          const first = Number.parseInt(line.trim(), 10);
          if (Number.isFinite(first) && first !== 1) list.start = first;
        }
      }
      const li = document.createElement("li");
      let itemText = (bullet || numbered)[1];
      // GFM task list: "- [ ] todo" / "- [x] done" → a real checkbox.
      const task = itemText.match(/^\[([ xX])\]\s+(.*)$/);
      if (task) {
        li.className = "md-task";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.disabled = true;
        box.checked = task[1].toLowerCase() === "x";
        li.appendChild(box);
        itemText = task[2];
      }
      appendInline(li, itemText);
      list.appendChild(li);
      i++;
      continue;
    }

    if (line.trim() === "") {
      // A blank line only ends a list if what follows isn't another item of
      // the same kind. Models write "1.\n\n2.\n\n3." far more often than
      // they write it tightly, and closing the <ol> on each gap restarted the
      // numbering at 1 every single time (user-reported).
      let next = i + 1;
      while (next < lines.length && lines[next].trim() === "") next++;
      const continues =
        list &&
        next < lines.length &&
        (list.tagName === "OL"
          ? /^\s*\d+\.\s+/.test(lines[next])
          : /^\s*[-*+]\s+/.test(lines[next]));
      if (!continues) closeList();
      i++;
      continue;
    }

    // Plain paragraph: gather consecutive non-blank, non-special lines.
    closeList();
    const para = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].trim().startsWith("```") &&
      !lines[i].match(/^(#{1,6})\s+/) &&
      !lines[i].match(/^\s*>\s?/) &&
      !/^\s*([-*_])(\s*\1){2,}\s*$/.test(lines[i]) &&
      !MD_COLS_OPEN.test(lines[i]) &&
      !MD_TOC_LINE.test(lines[i]) &&
      !MD_PAGE_BREAK.test(lines[i]) &&
      lines[i].trim() !== "$$" &&
      !lines[i].match(/^\s*[-*+]\s+/) &&
      !lines[i].match(/^\s*\d+\.\s+/) &&
      !(lines[i].includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1]))
    ) {
      para.push(lines[i]);
      i++;
    }
    //: **A link on a line of its own is a card** (CHAT_PLAN.md decision 12,
    //: INBOX 172: web links the AI writes, "better and more modern cool").
    //: A link inside a sentence stays inline, because a card in the middle of
    //: a sentence breaks the sentence; a link a model puts on its own line is
    //: a thing being handed to you, and it deserves a title, its host and a
    //: hit area rather than eleven characters of underlined prose.
    const lone = para.length === 1 ? LONE_LINK.exec(para[0]) : null;
    if (lone) {
      const url = lone[2] || lone[3];
      if (isRenderableUrl(url)) {
        container.appendChild(linkCard(url, lone[1] || ""));
        continue;
      }
    }
    const p = document.createElement("p");
    //: `<br>` is the one tag models write inside prose that means something
    //: (INBOX 172: "<br> md tags arent rendered properly"): a line break
    //: within the paragraph, not a paragraph break and not the literal text.
    para.join(" ").split(/<br\s*\/?>/i).forEach((piece, index) => {
      if (index) p.appendChild(document.createElement("br"));
      appendInline(p, piece);
    });
    container.appendChild(p);
  }
  //: The last iteration's blocks, which no next iteration is coming to stamp,
  //: and then the list the document may have ended in the middle of.
  stampNewBlocks();
  closeList();
  if (footnotes) mdFootnotesFinish(container, footnotes.notes);
  if (depth === 0) mdFillTocs(container);
}

// --- tabs (Wave A) ----------------------------------------------------------------

// TABS drives which pages hide; the arrow-key order comes from the bar's own
// buttons, so this list's order is not load-bearing. "documents" sits last
// because it has no button of its own, it is reached from the Library.
const TABS = ["dashboard", "notes", "chat", "graph", "library", "timeline", "reminders", "documents"];

// The DOM-only half of switchTab: which panel is visible, which tab button
// is active. No network calls here, so this is safe to run before a token
// exists: see revealTab("dashboard")'s module-level call below, and why
// it's this instead of a full switchTab().
function revealTab(name) {
  for (const tab of TABS) {
    $(`tab-${tab}`).classList.toggle("hidden", tab !== name);
  }
  if (typeof scheduleUndoBar === "function") scheduleUndoBar();
  // `documents` is a sub-view of Library, there is no `data-tab="documents"`
  // button in the tab bar, so the name that determines which button is active
  // must be "library" whenever we are showing the documents pane. Without
  // this, switchTab("documents") leaves every tab button deactivated, making
  // it look as though nothing is selected while the Documents page is visible.
  //
  // This was briefly removed when Documents was promoted to a top-level tab,
  // and restored when that was reversed, the real fix for "documents feel
  // inaccessible" was giving them their own section in the Library instead of
  // leaving them inside a catch-all view called "Documents" that showed
  // everything. Worth the note so the next session does not re-derive it.
  //: The companion finds its perch on the tab it is now on (avatars.js).
  if (typeof nameMarkBuddyTabChanged === "function") nameMarkBuddyTabChanged();
  const activeTabName = name === "documents" ? "library" : name;
  for (const button of document.querySelectorAll("#tab-bar button")) {
    const active = button.dataset.tab === activeTabName;
    button.classList.toggle("active", active);
    // Real tab semantics (Wave L): one tab stop for the whole list
    // (roving tabindex), arrow keys move between tabs.
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  }
  // When the strip is narrow enough to scroll, the tab you just chose is the
  // one that must be legible, see revealActiveTab.
  revealActiveTab?.();
  // And on a phone three of the seven are not in the strip at all.
  syncPhoneMoreButton?.(activeTabName);
  prefs.set("activeTab", name); // reopen where you left off
  // A new tab starts at its own top, and the back-to-top button re-evaluates
  // (it stays off the graph). Each page keeps its own scroll position now, so
  // this is a deliberate reset rather than a side effect of one shared one.
  scrollingPage()?.scrollTo({ top: 0, behavior: "auto" });
  scrollTopUpdate?.();
  // Any autogrow box that was measured while hidden gets its real height now
  // that its page is on screen. See autoGrow() for why a hidden measurement is
  // refused rather than applied, and autoGrowVisible() for which boxes that is.
  autoGrowVisible();
}

// --- back / forward through the pages you have visited ----------------------
//
// Asked for directly. Deliberately *not* the browser's own history: this app
// is a single page with no routing, so pushState would put entries in the
// browser's stack that its Back button would then walk out of the app
// entirely on the first press past the start. This is a small stack of its
// own, capped, and behaving the way the browser's does: visiting a page
// while somewhere in the middle of the stack discards what was ahead.
//
//: **It has a router now** (router.js, WORLD_CLASS_PLAN 22.1 item 1). This
//: stack stays what a step is and how to return to one; each entry is
//: mirrored into the browser's history with its own id, so the browser's Back
//: and this one walk the same list, and the address names the view. The
//: objection above answered: the browser's entries are this app's own views,
//: and the first one is the page's own load, so Back past the start leaves
//: the app exactly where a browser's Back would.
const TAB_HISTORY_CAP = 50;
const tabHistory = { stack: [], index: -1, navigating: false };

// **The navigation-history popup**: asked for directly: "if they are right
// clicked, a little popup shows above with the navigation history to fast
// track back to a place (or maybe it can be a little button next to it??)".
// Built as both: a dedicated button beside Back/Forward, and right-click on
// either of them, opening the same list. Most-recent-first (a browser's own
// history dropdown reads the same way), with the current entry marked
// rather than clickable: jumping to where you already are is not a step.
function closeNavHistoryMenu() {
  const menu = $("status-nav-history-menu");
  if (!menu || menu.classList.contains("hidden")) return;
  //: Escape from inside the list dropped the focus on `body` (menus.js):
  //: a closed menu hands it back to the button that opened it.
  const held = menu.contains(document.activeElement);
  menu.classList.add("hidden");
  $("status-nav-history")?.setAttribute("aria-expanded", "false");
  if (held) $("status-nav-history")?.focus({ preventScroll: true });
}

//: The rows (`renderNavHistoryMenu`) are nav-history.js's, a lazy bundle
//: fetched by the first press (`LAZY_MODULES.navHistory`).

// Opens upward, anchored to whichever of the three triggers was used, the
// status bar sits at the very bottom of the screen, so there is no "below"
// to open into. `position: fixed` (nav-history-menu's own CSS) plus an
// inline top/left computed here is the same escape-a-container shape
// `wireEscapedActionMenu` already uses for the Documents kebab, just
// triggered manually instead of by a class toggle.
async function openNavHistoryMenu(anchorEl) {
  const menu = $("status-nav-history-menu");
  if (!menu || !(await ensureModule("navHistory"))) return;
  renderNavHistoryMenu();
  menu.classList.remove("hidden");
  $("status-nav-history")?.setAttribute("aria-expanded", "true");
  // `bottom` is fixed in CSS (nav-history-menu's own rule, anchored off the
  // status bar): only `left` needs computing, and only after the menu is
  // visible and populated, so its real width is known.
  const margin = 8;
  const anchor = anchorEl.getBoundingClientRect();
  menu.style.left = "0px";
  const box = menu.getBoundingClientRect();
  let left = anchor.left;
  if (left + box.width > window.innerWidth - margin) {
    left = Math.max(margin, window.innerWidth - margin - box.width);
  }
  menu.style.left = `${Math.round(left)}px`;
  //: **4px above the button that opened it, like every other menu.** The
  //: stylesheet's `bottom` is measured from the bar's top edge, and the button
  //: sits inside the bar, so the menu floated 13px clear of it (menus.js, the
  //: only menu in the app past 8px from its opener). The bar is at the bottom
  //: of the window, so this is still "always upward"; it is just from the
  //: button rather than from the bar.
  menu.style.bottom = `${Math.round(window.innerHeight - anchor.top + 4)}px`;
}

function paintTabHistory() {
  const back = $("status-back");
  const forward = $("status-forward");
  if (!back || !forward) return;
  back.disabled = tabHistory.index <= 0;
  forward.disabled = tabHistory.index >= tabHistory.stack.length - 1;
  // Named pages in the tooltip, not a bare "Back": knowing where it goes is
  // the difference between using it and guessing. paintStatusItem mirrors
  // title into aria-label centrally, so the disabled state is honest to a
  // screen reader too rather than still promising a previous page.
  const prev = tabHistory.stack[tabHistory.index - 1];
  const next = tabHistory.stack[tabHistory.index + 1];
  paintStatusItem("status-back", {
    icon: "ph:caret-left",
    title: prev ? `Back to ${entryLabel(prev)}` : "Nothing to go back to",
    shortcut: prev ? "navigateBack" : "",
  });
  paintStatusItem("status-forward", {
    icon: "ph:caret-right",
    title: next ? `Forward to ${entryLabel(next)}` : "Nothing to go forward to",
    shortcut: next ? "navigateForward" : "",
  });
  // The settings modal's own copy of these two buttons, see their markup
  // comment for why a second copy exists instead of just raising the status
  // bar's z-index above every modal in the app.
  const modalBack = $("settings-nav-back");
  const modalForward = $("settings-nav-forward");
  if (modalBack && modalForward) {
    modalBack.disabled = back.disabled;
    modalForward.disabled = forward.disabled;
    modalBack.title = prev ? `Back to ${entryLabel(prev)}` : "Nothing to go back to";
    modalForward.title = next ? `Forward to ${entryLabel(next)}` : "Nothing to go forward to";
    modalBack.setAttribute("aria-label", modalBack.title);
    modalForward.setAttribute("aria-label", modalForward.title);
  }
}

// The tab's own visible name, so a tooltip says "Back to Documents" rather
// than "Back to documents" or, worse, an internal id.
function tabLabel(name) {
  // Not a real tab-page, see stepTabHistory's own "settings" branch, so
  // there is no `#tab-bar` button to read a label from.
  if (name === "settings") return "Settings";
  //: The document editor is a page, not a tab, so it has no button either.
  if (name === "documents") return "Documents";
  const button = document.querySelector(`#tab-bar button[data-tab="${name}"]`);
  return button?.textContent?.trim() || name;
}

// "Notes → Capture" rather than just "Notes", so Back names the step it
// actually takes when the move was between sub-tabs of one tab.
function entryLabel(entry) {
  const tab = tabLabel(entry.tab);
  if (!entry.section) return tab;
  // Chat's section is a conversation id ("conv:42") or "new", neither is a
  // button with real text the way Notes'/Library's sub-tabs are, so there is
  // no good short label to build; naming the tab is honest instead of
  // printing the raw id.
  if (entry.tab === "chat") return tab;
  //: A document, board or focus is named by what it is, never by its id
  //: (owner's screenshot: "documents → doc:4", "Library → library-view-docs").
  const named = historyTitles.get(entry.section);
  if (named) return `${tab}: ${named}`;
  if (/^(doc|board|focus|conv|note):/.test(entry.section)) {
    const kind = entry.section.split(":")[0];
    return `${tab}: ${{ doc: "a document", board: "a board", focus: "a note", conv: "a chat", note: "a note" }[kind]}`;
  }
  //: `library-view-media:files`: the media view's kind picks its button.
  const [target, kind] = entry.section.split(":");
  const button = kind
    ? document.querySelector(`[data-target="${target}"][data-media-kind="${kind}"]`)
    : document.querySelector(
      `[data-section="${entry.section}"], [data-target="${entry.section}"], [aria-controls="${entry.section}"]`
    );
  const section = button?.textContent?.trim().replace(/\s+/g, " ");
  return section ? `${tab}: ${section}` : tab;
}

// One history entry. `section` is the sub-tab within a tab, when that tab has
// them: asked for directly: "have the back and forward navigation also handle
// navigation between sub tabs as well." Notes has four (browse / capture /
// writing-room / ask) and moving between them is as much a navigation as
// moving between tabs, so Back should undo it.
//: The human name of a history step that is a thing rather than a sub-tab
//: (a document, a board), recorded by whoever opens it, so the Back menu can
//: say "Documents: Weekly plan" instead of "documents → doc:4".
const historyTitles = new Map();

function recordTabVisit(name, section = null, title = "", { refine = false } = {}) {
  if (section && title) historyTitles.set(section, String(title).trim());
  // A back/forward press is a move *through* history, not a new entry.
  if (tabHistory.navigating) return;
  const current = tabHistory.stack[tabHistory.index];
  // Re-selecting exactly where you already are is not a step.
  if (current && current.tab === name && current.section === section) {
    //: Its title may have arrived since (a note's words, a document's name).
    if (typeof routerOnVisit === "function") routerOnVisit(current, false);
    return;
  }
  //: `refine`: this is a closer look at the view already on top, not a new
  //: one (a note opened in the Notes list is the list, scrolled to it), so it
  //: replaces the entry and the address rather than adding a step.
  if (refine && current && current.tab === name) {
    current.section = section;
    paintTabHistory();
    if (typeof routerOnVisit === "function") routerOnVisit(current, false);
    return;
  }
  // One entry per visit. A Notes arrival is recorded twice, as {notes,
  // "browse"} by showNotesSection and as {notes, null} by switchTab (in
  // either order), so Back from the next tab landed on the duplicate first
  // and looked like it did nothing (reported: "I need to click back or
  // forwards twice"). When the tab on top is this tab and one of the two
  // sections is null, the entry is refined in place rather than pushed.
  if (current && current.tab === name && (current.section == null || section == null)) {
    if (section != null) current.section = section;
    paintTabHistory();
    if (typeof routerOnVisit === "function") routerOnVisit(current, false);
    return;
  }
  tabHistory.stack = tabHistory.stack.slice(0, tabHistory.index + 1);
  const entry = { tab: name, section };
  tabHistory.stack.push(entry);
  if (tabHistory.stack.length > TAB_HISTORY_CAP) tabHistory.stack.shift();
  tabHistory.index = tabHistory.stack.length - 1;
  paintTabHistory();
  if (typeof routerOnVisit === "function") routerOnVisit(entry, true);
}

//: Back and Forward go through the browser's history when the router is
//: mirroring it (`routerGo`, router.js), which answers with `popstate` and
//: lands in `goToTabHistory` below; the stack walks on its own otherwise.
function stepTabHistory(delta) {
  if (typeof routerGo === "function" && routerGo(delta)) return;
  return goToTabHistory(tabHistory.index + delta);
}

// The shared jump used by both Back/Forward (one step) and the history
// popup below (any step at once), asked for directly: "a little popup
// shows above with the navigation history to fast track back to a place".
// stepTabHistory used to inline this with a fixed +1/-1, which had no way
// to land on an arbitrary earlier or later entry.
async function goToTabHistory(next, { fromBrowser = false } = {}) {
  if (next < 0 || next >= tabHistory.stack.length) return;
  //: A jump from the history menu is a walk through the browser's history
  //: too, for the same reason Back is (`stepTabHistory`).
  if (!fromBrowser && typeof routerGo === "function" && routerGo(next - tabHistory.index)) return;
  const entry = tabHistory.stack[next];
  const from = tabHistory.index;
  tabHistory.index = next;
  tabHistory.navigating = true;
  tabSwitchDeclined = false;
  const scroll = entry.scroll;
  try {
    await openHistoryEntry(entry);
    if (entry.tab === "settings" && scroll) restoreSettingsScroll(entry.section, scroll);
  } finally {
    // Cleared in a finally so a throw inside a tab's own setup cannot strand
    // the flag on and silently stop recording every later visit.
    tabHistory.navigating = false;
  }
  //: Declined at "Leave without saving?": the stack stays where it was, and
  //: a step the browser already took (Back) is taken back, so the address,
  //: the history menu and the tab on screen agree again.
  if (tabSwitchDeclined) {
    tabHistory.index = from;
    if (fromBrowser && next !== from) history.go(from - next);
  }
  paintTabHistory();
}

//: **Where in a Settings section you were** (the owner at release: "I keep
//: having to open settings, go to the right page and then scroll to the
//: right section"). Back already reopened the section, at its top, because
//: showSettingsSection resets the scroll on every switch. The entry on top
//: now follows its section's scroll as it happens (a capture listener, since
//: scroll does not bubble), so closing Settings, or moving to another
//: section, leaves the last position on the entry it belongs to; a restore
//: puts it back. Ignored while a back/forward move is in progress, whose
//: own reset to the top would otherwise overwrite the value being restored.
document.addEventListener("scroll", (event) => {
  if (tabHistory.navigating) return;
  const current = tabHistory.stack[tabHistory.index];
  if (current?.tab !== "settings" || typeof settingsScroller !== "function") return;
  if (event.target === settingsScroller(current.section)) current.scroll = event.target.scrollTop;
}, { passive: true, capture: true });

//: Set now and again a frame later: a section built on open can still be
//: growing when the restore lands, and a scrollTop past its height clamps.
function restoreSettingsScroll(section, top) {
  const put = () => {
    const el = settingsScroller(section);
    if (el) el.scrollTop = top;
  };
  put();
  requestAnimationFrame(put);
}

//: Open the view one history entry names: the tab, then its sub-tab or the
//: thing open in it. Shared by the history walk above and the router's fresh
//: visits (a reload, a pasted link: `routerOpen`, router.js), which are the
//: same question asked from an address instead of from the stack.
async function openHistoryEntry(entry) {
  // Settings is a modal overlay, not one of the tab-pages switchTab knows
  // about: asked for directly: "the back and forward buttons should cover
  // going in and out of settings too", which they didn't, because nothing
  // ever called recordTabVisit for it. Restoring a settings entry opens the
  // modal (or moves it to a different section) instead of going through
  // switchTab at all; restoring anything else closes it first if it was
  // left open, the same way clicking Close would.
  if (entry.tab === "settings") {
    await openSettingsModal(entry.section || "models");
    paintTabHistory();
    return;
  }
  if (settingsModalOpen()) closeSettingsModal();
  //: Awaited: every branch below reaches straight into the tab's own file
  //: (`openWhiteboardBoard`, `openDocument`, `graphFocusModeId`), and two of
  //: those are lazily loaded now (A1). `graphFocusModeId` in particular is a
  //: `let` in graph.js, which no stand-in can supply.
  await switchTab(entry.tab);
  if (tabSwitchDeclined) return;
  // The sub-tab is restored after the tab, because both restore paths below
  // act on elements the tab switch has just revealed.
  if (entry.tab === "notes" && entry.section?.startsWith("note:")) {
    //: A note: the list, scrolled to it and lit (`flashEntry`, which every
    //: way to a note already goes through).
    flashEntry(Number(entry.section.slice("note:".length)));
  } else if (entry.tab === "notes" && entry.section) {
    showNotesSection(entry.section);
  } else if (entry.tab === "library") {
    // Reuses the real click handler (whiteboard.js) rather than
    // duplicating its section-show/whiteboard-landing/gallery-render
    // logic here: a second copy is exactly the shape this codebase keeps
    // getting bitten by. `tabHistory.navigating` (set above) makes the
    // handler's own `recordTabVisit` call a no-op, the same guard
    // `showNotesSection`'s call already relies on above. A bare `{tab:
    // "library"}` entry (recorded the moment the tab itself was opened,
    // before any sub-tab click) has no `section`, falls back to "All"
    // (`library-view-documents`, the sub-tab that kept its old id) rather
    // than leaving whatever sub-view happened to be on screen already.
    //: **A board is a place, and `board:{id}` is not a sub-tab id.**
    //: `openWhiteboardBoard` records one now (see whiteboard.js), so this
    //: has to know how to go back to one, without this branch the selector
    //: below would look for `button[data-target="board:12"]`, match nothing,
    //: and Back would silently do nothing at all. Recording a place you
    //: cannot return to is worse than not recording it: the entry appears in
    //: the history popup and then refuses to work.
    if (entry.section?.startsWith("board:")) {
      //: Awaited for the same reason chat's `conv:` and documents' `doc:`
      //: branches are: it fetches before it finishes, and returning early
      //: would clear `tabHistory.navigating` in the `finally` below: turning
      //: every back/forward through a board into a fresh history entry
      //: instead of a no-op.
      await openWhiteboardBoard(Number(entry.section.slice("board:".length)));
    } else {
      //: `library-view-media:files`: the view and, for the media view, its
      //: kind (library.js records both).
      const [target, kind] = (entry.section || "library-view-documents").split(":");
      document
        .querySelector(
          `#library-subtabs button[data-target="${target}"]${kind ? `[data-media-kind="${kind}"]` : ""}`
        )
        ?.click();
    }
  } else if (entry.tab === "chat" && entry.section) {
    if (entry.section.startsWith("conv:")) {
      // Awaited deliberately: openConversation does its own network fetch
      // before calling recordTabVisit, so returning early here would clear
      // tabHistory.navigating (in the finally below) before that call runs
      //, turning every back/forward through a saved chat into a fresh,
      // spurious history entry instead of a no-op.
      await openConversation(Number(entry.section.slice("conv:".length)));
    } else if (entry.section === "new") {
      newChatConversation();
    }
  } else if (entry.tab === "documents" && entry.section?.startsWith("doc:")) {
    // Same awaited-before-finally shape as chat's conv: branch above, for
    // the same reason: openDocument does its own network fetch before
    // calling recordTabVisit, so an un-awaited call here would clear
    // tabHistory.navigating too early and turn this into a fresh entry.
    await openDocument(Number(entry.section.slice("doc:".length)));
  } else if (entry.tab === "graph") {
    // switchTab's own "graph" branch above already rendered once with
    // whatever graphFocusModeId happened to hold; set it to match this
    // history entry and render again so Focus Mode itself is part of what
    // back/forward restores, not just the tab underneath it.
    graphFocusModeId = entry.section?.startsWith("focus:")
      ? Number(entry.section.slice("focus:".length))
      : null;
    $("graph-focus-clear")?.classList.toggle("hidden", !graphFocusModeId);
    await renderGraph();
  }
}

//: **A surface whose data did not arrive says so, instead of saying it is
//: empty.** Measured across seven tabs with every `/api` call failing
//: (`scratchpad/ui-sweeps/vibefail.js`): four of them drew their empty state,
//: so a notebook of four hundred notes read "Your notebook is empty", and the
//: other three drew nothing at all. Both are the app claiming a fact about
//: the person's own data that it has no basis for, which is the exact shape
//: the owner described as breaking trust in an application.
//:
//: The same `.empty-state` component, told the truth, rather than a second
//: component: it is already the thing in the middle of an empty surface, it
//: already has an icon, a title, a sentence and room for one action, and
//: DESIGN.md's Voice section says errors say what to do next. So this swaps
//: its contents and puts them back, which also means a surface only needs the
//: element it already has.
//:
//: `role="alert"` while it is failed and not otherwise: a screen reader should
//: hear this when it appears, and should not hear the ordinary empty state
//: announced every time a filter clears.
const _surfaceFailedContents = new WeakMap();

function surfaceFailed(el, what, retry) {
  if (!el) return;
  //: Saved once. A second failure while already failed must not capture the
  //: failure message as "the original contents", which would make the real
  //: empty state unrecoverable for the rest of the session.
  if (!_surfaceFailedContents.has(el)) {
    _surfaceFailedContents.set(el, { nodes: [...el.childNodes], display: el.style.display });
  }
  el.classList.add("is-failed");
  el.classList.remove("hidden");
  //: **And any inline `display` it is carrying.** The graph's empty state is
  //: hidden with `style.display = "none"` rather than the class, deliberately
  //: ("inline display beats every stylesheet rule", graph.js), so removing
  //: `hidden` left the failure message in the document at 0 by 0 pixels:
  //: present to every assertion and invisible to every reader. Measured, and
  //: exactly the kind of fix that reports itself as working.
  el.style.display = "";
  el.replaceChildren();
  const icon = document.createElement("i");
  icon.className = "ph ph-warning-circle empty-icon";
  icon.setAttribute("aria-hidden", "true");
  const title = document.createElement("p");
  title.className = "empty-title";
  title.textContent = `Could not load your ${what}`;
  const body = document.createElement("p");
  //: Says what is and is not true, because the first thing a person fears
  //: here is that the notes are gone.
  body.textContent =
    "Nothing has been lost: the app could not read its own data just now.";
  el.append(icon, title, body);
  if (typeof retry === "function") {
    const again = document.createElement("button");
    again.type = "button";
    again.className = "ghost small";
    setLabel(again, "ph:arrow-clockwise Try again");
    again.addEventListener("click", () => {
      surfaceRecovered(el);
      retry();
    });
    el.appendChild(again);
  }
  el.setAttribute("role", "alert");
}

//: The other half, and the reason the contents are saved rather than rebuilt:
//: an empty state's markup is written in index.html, per surface, with its own
//: wording and its own action, and none of that is knowable from here.
function surfaceRecovered(el) {
  if (!el || !_surfaceFailedContents.has(el)) return;
  const saved = _surfaceFailedContents.get(el);
  el.replaceChildren(...saved.nodes);
  //: Put back exactly what was there, empty string included: the surface's own
  //: renderer sets this on every pass and must not find a value this helper
  //: invented.
  el.style.display = saved.display;
  _surfaceFailedContents.delete(el);
  el.classList.remove("is-failed");
  el.removeAttribute("role");
}

//: What a loader wraps its own body in. Kept to one helper so a surface added
//: later gets the behaviour by naming its empty element, and so no loader has
//: to decide for itself what a failure looks like (which is how the four
//: surfaces that *do* have an empty state came to disagree with the three
//: that do not).
//:
//: It swallows the error deliberately: the failure is now on screen, with the
//: way out beside it, and a rethrow here is an unhandled rejection in the
//: console and nothing more.
async function loadSurface(el, what, run) {
  try {
    const result = await run();
    surfaceRecovered(el);
    return result;
  } catch (error) {
    surfaceFailed(el, what, () => loadSurface(el, what, run));
    //: Locked is the expected state on the lock screen (`api()` marks that 401
    //: `isLockout`), not a failure worth a WARN: the log opened with
    //: "[notes] could not load: Locked" on every boot. The failed state above
    //: is kept (Retry works once unlocked); real failures are still logged.
    if (!error?.isLockout) recordBrowserLog("WARN", [`[${what}] could not load: ${error?.message || error}`]);
    return null;
  }
}

// Empty states carry one action (DESIGN.md → Voice), the surface's own verb
// (Images and Files: Upload, as their dock says). One delegated listener, so
// a new empty state adds a `data-empty-action` and nothing else.
//: Every dock menu (UI_MODERNISATION_PLAN.md Phase 8) is a `<details>`: the
//: browser gives open-on-click, Enter/Space, Escape and the ARIA. What it does
//: not give is closing when you pick an item or click away, and both are what
//: make a menu feel like a menu rather than a panel you have to shut. One
//: delegated pair for every `.dock-menu` on every tab: the same shape the
//: documents kebab wires for itself in documents.js, so a dock added later
//: gets the behaviour without anyone remembering to add it. A segmented
//: control inside a menu (Layout, Colour) keeps the menu open: picking a
//: layout and then a colour is one visit, not two.
document.addEventListener("click", (event) => {
  // `.action-menu-escaped` covers a list `escapeMenuIfClipped` has reparented
  // to <body> (see the toggle listener below): it is then a sibling of its
  // `details.dock-menu`, not a descendant, so `menu.contains(event.target)`
  // below would read every click inside the still-open list as an outside
  // click and shut it on the first interaction. Same widening
  // `.action-menu-escaped` already gets in the pointerdown-close listener
  // for `.action-menu` (search this file for that class).
  const item = event.target.closest(".dock-menu .doc-dock-menu-item, .action-menu-escaped .doc-dock-menu-item");
  //: Except a switch, which is the exception documents.js already makes for
  //: its own dock kebab and makes for the same reason: every other row does
  //: one thing and is finished, so closing is right, while a switch has a
  //: state you have to be able to see move, and a menu that shuts on the click
  //: hides the only feedback it gives. Added with INBOX 214, where the
  //: Timeline's four kind toggles moved into a dock menu and turning two of
  //: them off meant opening it twice.
  if (item && !event.target.closest(".doc-dock-menu-check")) {
    const menu = item.closest("details.dock-menu") || item.closest(".doc-dock-menu-list")?._escapedHome?.parent;
    // After the item's own handler has run: closing first would move focus
    // and, for a toggle, leave its aria-expanded one step behind.
    if (menu) setTimeout(() => { menu.open = false; }, 0);
  }
  for (const menu of document.querySelectorAll("details.dock-menu[open]")) {
    if (menu.contains(event.target)) continue;
    if (event.target.closest(".action-menu-escaped")) continue;
    menu.open = false;
  }
});
//: A dock menu opens under its own button; near the right edge it flips to
//: right-align (measured: Timeline's Options ran 41px past the viewport), a
//: class rather than a computed left, so the stylesheet owns the geometry.
//:
//: **Vertical clipping too** (INBOX 31: "dropdown menus clip off the bottom
//: of the panel and do not scroll"): the flat `calc(100vh - space-9*2)` cap
//: is blind to where the menu opened (Reminders' Quick set at 1024x560 ended
//: 172px past the window, nothing to scroll). `escapeAndCapMenu` escapes a
//: clipping ancestor, then caps from the list's own top on every open; the
//: whiteboard's top-bar menus call it too.
//: **The document dock's ⋯ joined late** (INBOX 233: 17 rows wanting 704px
//: drawn from y=178 at 1440x700, "Delete document" unreachable): it carries
//: neither `.dock-menu` nor `.doc-toolbar-menu`, so nothing measured it.
//: `placeDockMenuInWindow` adds the side to open on: upward when there is
//: more room above, since capping downward is useless near the bottom edge.
function placeDockMenuInWindow(details, list) {
  const opener = details.querySelector("summary") || details;
  const margin = 8;
  //: Every open starts from the stylesheet's own geometry: a stale cap or a
  //: stale side changes the measurement that decides this one.
  details.classList.remove("doc-dock-menu-up");
  list.style.maxHeight = "none";
  list.style.overflowY = "";
  list.style.transform = "";
  list.style.maxWidth = "";
  const anchor = opener.getBoundingClientRect();
  const box = list.getBoundingClientRect();
  //: Not laid out (a `<details>` in a hidden pane, the all-zero rect
  //: `clampToolbarMenu` documents): leave the stylesheet's cap alone rather
  //: than write a number derived from zeroes.
  if (!box.height || !anchor.height) {
    list.style.maxHeight = "";
    return;
  }
  //: The gap is measured, not assumed: it is `top: calc(100% + var(--space-2))`
  //: today and a token is free to change.
  const gap = Math.max(0, Math.round(box.top - anchor.bottom));
  //: **Below, else above, else capped** (INBOX 712), the one rule
  //: (`menuSidePlan`, menus.js). This used to move above only when the room
  //: below was under 240px, so a menu that fitted above but not below, with
  //: 300px of room under it, stayed down and scrolled.
  const plan = menuSidePlan(box.height, anchor, gap, margin);
  if (plan.up) details.classList.add("doc-dock-menu-up");
  if (plan.cap !== null) {
    list.style.maxHeight = `${plan.cap}px`;
    list.style.overflowY = "auto";
  }

  //: **And sideways, which this never checked** (INBOX 262). The stylesheet
  //: anchors these to the opener's *right* edge and grows them leftwards,
  //: which is right beside a button at the end of a row and wrong when the
  //: window is narrower than the menu plus whatever is to the opener's left.
  //: Measured at 390x844 on the document editor's ⋯: a 286px menu in a 390px
  //: window sat at left -53, so the first 53px of every label was off the
  //: screen with no way to scroll to it.
  //:
  //: A `transform`, not a `left`: these are anchored with `right: 0` against
  //: their own `<details>`, so switching to a left offset would mean
  //: recomputing the anchoring this rule deliberately leaves to the
  //: stylesheet. A translate moves the painted box and changes no layout.
  //: The width cap comes first, because a menu wider than the window cannot
  //: be shifted into it.
  const wide = window.innerWidth - margin * 2;
  if (box.width > wide) list.style.maxWidth = `${wide}px`;
  const shifted = list.getBoundingClientRect();
  const dx = shifted.left < margin
    ? margin - shifted.left
    : Math.min(0, window.innerWidth - margin - shifted.right);
  if (dx) list.style.transform = `translateX(${Math.round(dx)}px)`;
}

//: **A placement measured once is wrong the moment the window or the rows
//: change** (INBOX 712). An open kebab is placed again when the window is
//: resized (zoom, a docked panel opening, a rotated tablet) and when one of
//: its rows is shown or hidden (the suggestion and read-aloud rows appear as
//: the menu opens, after the first measurement), so the last row is never
//: left past the window's edge by a number that was true a moment ago.
function watchDockMenuPlacement(menu, list) {
  menu._placementWatch?.disconnect();
  let frame = 0;
  const again = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (menu.open) placeDockMenuInWindow(menu, list);
    });
  };
  const observer = new MutationObserver(again);
  observer.observe(list, { subtree: true, childList: true, attributes: true, attributeFilter: ["hidden"] });
  window.addEventListener("resize", again);
  menu._placementWatch = {
    disconnect() {
      observer.disconnect();
      window.removeEventListener("resize", again);
      cancelAnimationFrame(frame);
      frame = 0;
      menu._placementWatch = null;
    },
  };
}

document.addEventListener(
  "toggle",
  (event) => {
    const menu = event.target;
    if (!(menu instanceof HTMLElement)) return;
    const isDock = menu.matches("details.dock-menu");
    //: The dock kebab's own shape: a `.doc-dock-menu` that is neither a dock
    //: menu nor one of the editor toolbars `clampToolbarMenu` owns.
    const isDockKebab = !isDock && menu.matches("details.doc-dock-menu:not(.doc-toolbar-menu)");
    if (!isDock && !isDockKebab) return;
    // Once escaped, the list is a child of <body>, not of `menu`: cache the
    // reference the first time so a later close/reopen can still find it.
    const list = menu._dockMenuList || menu.querySelector(".dock-menu-list, .doc-dock-menu-list");
    if (!list) return;
    menu._dockMenuList = list;
    //: A closed menu's list is `hidden`, not only unpainted: a closed
    //: `<details>` still lays its content out, so its rows sat over the
    //: controls below it for every probe (TIMELINE_PLAN 10 row 1, 11 row 2:
    //: the timeline's folded view segment past the edge at 390, the reminder
    //: presets over the Open, All and Done chips). Shown before anything here
    //: measures it.
    list.hidden = !menu.open;
    if (!menu.open) {
      // Closed: put an escaped list back where it lives in the DOM (a no-op
      // if it was never escaped) and drop this open's inline cap, so the
      // next open starts from the stylesheet's own numbers, not a stale one.
      restoreEscapedMenu(list);
      list.style.maxHeight = "";
      list.style.overflowY = "";
      menu.classList.remove("doc-dock-menu-up");
      menu._placementWatch?.disconnect();
      return;
    }
    if (isDockKebab) {
      placeDockMenuInWindow(menu, list);
      watchDockMenuPlacement(menu, list);
      return;
    }
    menu.classList.remove("dock-menu-flip");
    if (list.getBoundingClientRect().right > window.innerWidth - 8) menu.classList.add("dock-menu-flip");
    escapeAndCapMenu(list, menu.querySelector("summary") || menu);
  },
  true
);
for (const list of document.querySelectorAll(
  "details.dock-menu:not([open]) > .dock-menu-list, details.doc-dock-menu:not(.doc-toolbar-menu):not([open]) > .doc-dock-menu-list"
)) {
  list.hidden = true;
}
//: Escape closes an open dock menu and puts focus back on its button, 
//: `<details>` does not do this on its own, whatever a comment elsewhere in
//: this codebase once claimed; measured with a keyboard-only probe. Capture
//: phase, so the graph's own Escape (leave trace mode) and the lock screen's
//: never see a key that was meant for the menu.
//:
//: **Every `details` menu, not only the ones with `.dock-menu`.** The
//: document's own ⋯ (`#doc-dock-menu`) and the editor toolbars' menus are
//: `.doc-dock-menu` without it, and Escape left all of them open (measured,
//: scratchpad/ui-sweeps/menus.js). The class they all share is the one named
//: here.
const DETAILS_MENU_OPEN = "details[open]:is(.dock-menu, .doc-dock-menu)";
document.addEventListener(
  "keydown",
  (event) => {
    if (event.key !== "Escape") return;
    const open = document.querySelector(DETAILS_MENU_OPEN);
    if (!open) return;
    event.preventDefault();
    event.stopPropagation();
    open.open = false;
    open.querySelector("summary")?.focus();
  },
  true
);

//: **The arrow keys, in every menu that is not built by `kebabMenu`.**
//: `wireMenuKeyboard` gives a built menu ↑, ↓, Home and End once the focus is
//: inside it, and nothing gave any of that to the two other shapes: a
//: `details` dock menu (twenty-odd of them, every ⋯ and Options in every dock)
//: and a menu button whose menu is written in markup (the board's Insert,
//: Edit, Arrange, View and Board, the space switcher, navigation history).
//: Measured by scratchpad/ui-sweeps/menus.js at 1440, before this: ArrowDown
//: on any of them left the focus on the button that opened it, which is the
//: one key a person who has just opened a menu will press.
//:
//: Two halves, the WAI-ARIA menu button pattern. On the opener of an open
//: menu, ↓ goes to the first row and ↑ to the last. Inside a `details` menu,
//: ↑ and ↓ walk its rows and Home and End jump to the ends. A field keeps its
//: own keys: a radio group, a slider and a text box already mean something by
//: the arrows, and taking them would break the control to fix the menu.
//: **Inside a closed `details` is not a row**, though it still has a layout box
//: (the tour's recipe says the same of a folded dock): the Graph's More at 1024
//: holds the folded View menu, and ArrowDown from its summary walked onto a
//: Layout radio inside the closed View, which cannot take the focus, so the
//: arrows stopped there (menus.js). Its own summary is the one exception.
function insideClosedDetails(el) {
  for (let p = el.parentElement; p; p = p.parentElement) {
    if (p.tagName === "DETAILS" && !p.open && !(el.tagName === "SUMMARY" && el.parentElement === p)) return true;
  }
  return false;
}

function menuRowsOf(menu) {
  return [
    ...menu.querySelectorAll(
      '[role^="menuitem"], [role="option"], button, a[href], summary, input:not([type="hidden"]), [tabindex="0"]'
    ),
  ].filter(
    (el) =>
      !el.disabled &&
      !el.closest(".select-menu, .hidden, [hidden]") &&
      !insideClosedDetails(el) &&
      el.getClientRects().length > 0 &&
      getComputedStyle(el).visibility !== "hidden"
  );
}

function menuOfOpener(opener) {
  if (opener.tagName === "SUMMARY") {
    const details = opener.parentElement;
    if (!details?.open || !details.matches(".dock-menu, .doc-dock-menu")) return null;
    return (
      details.querySelector(":scope > .doc-dock-menu-list") ||
      document.querySelector(".action-menu-escaped.doc-dock-menu-list:not(.hidden)")
    );
  }
  if (opener.getAttribute("aria-expanded") !== "true") return null;
  const id = opener.getAttribute("aria-controls");
  return id ? document.getElementById(id) : null;
}

document.addEventListener("keydown", (event) => {
  const keys = ["ArrowDown", "ArrowUp", "Home", "End"];
  if (!keys.includes(event.key) || event.altKey || event.ctrlKey || event.metaKey) return;
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  //: A checkbox has no arrow keys of its own, so a tick row in a menu (the
  //: Timeline's kinds) is walked like any other row.
  if (target.matches("input:not([type='checkbox']), textarea, select, [contenteditable='true']")) return;
  //: A ⋯ menu on a phone is a sheet (`openKebabSheet`), and the sheet opens
  //: with the focus on its own close button, above the menu: from there the
  //: arrows go into the menu, as they would from the ⋯ that opened it.
  //: Measured at 390 (menus.js): ArrowDown left the focus on the close button
  //: in every sheet menu.
  const sheetCard = target.closest(".action-menu-card");
  if (sheetCard && !target.closest('[role="menu"]') && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    const menu = sheetCard.querySelector('[role="menu"]');
    const rows = menu ? menuRowsOf(menu) : [];
    if (rows.length) {
      event.preventDefault();
      focusMenuItem(event.key === "ArrowDown" ? rows[0] : rows[rows.length - 1], menu);
      return;
    }
  }
  const opener = target.closest("summary, [aria-haspopup]:not([aria-haspopup='false'])");
  if (opener === target && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    const menu = menuOfOpener(opener);
    const rows = menu ? menuRowsOf(menu) : [];
    //: A closed select standing as a row in a dock menu (the document's
    //: File type) is a row to walk past, not an opener to stop on.
    if (rows.length) {
      event.preventDefault();
      focusMenuItem(event.key === "ArrowDown" ? rows[0] : rows[rows.length - 1], menu);
      return;
    }
  }
  //: Inside the menu: a `details` menu's list, or a markup menu an open
  //: button controls (the space switcher's list). A menu `wireMenuKeyboard`
  //: already walks is left to it, or every key would move two rows.
  const list = target.closest('.doc-dock-menu-list, [role="menu"], [role="listbox"]');
  if (!list || list.dataset.menuKeys || target.closest(".select-menu")) return;
  if (list.matches(".doc-dock-menu-list")) {
    const details = list.closest("details") || list._escapedHome?.parent;
    if (!details?.open) return;
  } else if (!list.id || !document.querySelector(`[aria-controls="${list.id}"][aria-expanded="true"]`)) {
    return;
  }
  const rows = menuRowsOf(list);
  const at = rows.indexOf(target);
  if (at < 0) return;
  event.preventDefault();
  const next =
    event.key === "Home" ? 0
      : event.key === "End" ? rows.length - 1
        : event.key === "ArrowDown" ? (at + 1) % rows.length
          : (at - 1 + rows.length) % rows.length;
  focusMenuItem(rows[next], list);
});

//: A dashboard widget's empty action lives on another tab (INBOX 464 (12)):
//: `data-empty-tab` and `data-empty-sub` (a Library sub-tab) say which, and
//: the tab is opened, and its lazy bundle waited for, before the action runs.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-empty-action]");
  if (!button) return;
  const action = button.dataset.emptyAction;
  const { emptyTab, emptySub } = button.dataset;
  if (emptyTab) await switchTab(emptyTab);
  if (emptySub) document.querySelector(`#library-subtabs button[data-target="${emptySub}"]`)?.click();
  if (action === "tab") {
    // Going there was the whole action.
  } else if (action === "ask") {
    $("chat-input")?.focus();
  } else if (action === "untagged") {
    showNotesFilter("is:untagged");
  } else if (action === "suggest-links") {
    openSuggestionsInbox("links");
  } else if (action === "capture") {
    startNewNote();
  } else if (action === "reminder") {
    // The form is a sheet on a phone; `openReminderCompose` knows which.
    openReminderCompose();
  } else if (action === "clear-filter") {
    // The same path as typing into the box and deleting it: the handler on
    // #note-search owns `noteSearch`, the Save-filter button and the render.
    const search = $("note-search");
    if (search) {
      search.value = "";
      search.dispatchEvent(new Event("input", { bubbles: true }));
      search.focus();
    }
  } else if (action === "search-everything") {
    openFinder($("note-search")?.value || "", { kind: "" });
  } else if (action === "upload") {
    $("library-images-upload")?.click();
  } else if (action === "new-document") {
    $("library-docs-new")?.click();
  } else if (action === "new-board") {
    //: The Library tab loads library.js alone (FE-03(c)); this button's
    //: listener is the boards' bundle's, so it is waited for first
    //: (tests/test_new_document_opens_new.py).
    await ensureModule("library");
    $("wb-boards-new")?.click();
  } else if (action === "add-link") {
    $("bookmark-form")?.classList.remove("hidden");
    $("bookmark-url-input")?.focus();
  }
});

//: The lazy bundles a tab visit has already waited for (see the `inert` in
//: `switchTab`).
const lazyTabsReady = new Set();

// --- leaving with unsaved work (WORLD_CLASS_PLAN 22.1 item 4) ---------------
//
// Reported gap: "No beforeunload guard anywhere; the drafts cover the
// capture box, but a document mid-save, a board mid-drag and a chat
// mid-stream are not checked." This covers the three surfaces whose "has
// this been saved yet" is a plain flag rather than something that needs
// asking a server: the note edit form, the Capture box, and a document
// mid-autosave. Each surface keeps the one flag its own Save button already
// reads (`docDirty` in documents.js, `noteFormDirty` below), so this is a
// second reader of each, never a second writer: no parallel dirty state to
// fall out of step with the original.
//
// `typeof` guards a lazy surface's flag (`docDirty`): the Documents tab's
// own file may not have loaded yet, in which case there is nothing open
// there to lose, the same reasoning `switchTab`'s own `graphSimulation`
// check below already uses for a lazy tab that was never visited.
function hasUnsavedWork() {
  if (typeof docDirty !== "undefined" && docDirty) return true;
  if (typeof noteFormDirty !== "undefined" && noteFormDirty && editingId !== null) return true;
  //: Not the capture box: its text survives a tab switch (the box stays in
  //: the page) and a reload (the draft in localStorage), so leaving loses
  //: nothing, and asking "Leave without saving?" on every tab switch while a
  //: thought sat in the box was a question with no stakes, asked constantly.
  return false;
}

//: The one `beforeunload` guard for all three surfaces above (the narrower,
//: `docDirty`-only listener that used to live in documents.js is folded into
//: this one, so there is one place that decides "would leaving lose
//: something", not one per surface). Native browsers ignore the string and
//: show their own wording; `returnValue` is set for the ones that still read
//: it.
//: A chat answer still coming is lost by a reload or a close (the thread
//: keeps the question and an unfinished answer), so it asks too. Not in
//: `hasUnsavedWork`: a tab switch leaves the stream running (chat-attach.js),
//: so only a departure from the page itself loses it. `typeof`: the chat
//: file loads lazily.
function chatMidStream() {
  return typeof chatStreaming !== "undefined" && !!chatStreaming;
}

window.addEventListener("beforeunload", (event) => {
  if (!hasUnsavedWork() && !chatMidStream()) return;
  event.preventDefault();
  event.returnValue = "";
});

//: The same question, asked in the app's own confirm dialog, for a
//: navigation that stays inside the app (a tab press, a back-stack replay,
//: a deep link) rather than one that leaves it. Only when the destination is
//: actually a different tab: re-pressing the tab already on screen is not a
//: departure. Declining leaves `switchTab` before it touches the DOM, so the
//: page in progress is exactly as the person left it.
//: Whether the last question here was answered "stay": a history step
//: that asked for the switch (Back, the history menu, a link) reads this
//: and puts itself back, rather than recording a visit that never happened
//: and opening a note or a board in a tab that is not on screen.
let tabSwitchDeclined = false;
async function confirmLeavingUnsavedWork(name) {
  tabSwitchDeclined = false;
  if (prefs.get("activeTab", null) === name) return true;
  //: **Only a document can lose words on a tab switch, and it saves first**
  //: (INBOX 711, the owner: asked again and again after Leave, on a
  //: document that read Saved, and "doesnt the document auto save??"). An
  //: open note form stays open in Notes with its words kept (`noteFormDraft`)
  //: and a reload offers them back, like the Capture box, so a switch away
  //: is not a departure; asking about it on every move was the bug. A
  //: document with edits in hand is saved now, and asked about only if
  //: that save fails.
  if (typeof docDirty === "undefined" || !docDirty) return true;
  await saveDocument({ silent: true }).catch(() => {});
  if (!docDirty) return true;
  const leave = await confirmDialog(
    "Leave without saving?\n\nWhat you were working on here hasn't been saved yet."
  );
  tabSwitchDeclined = !leave;
  return leave;
}

//: The local usage ledger (WORLD_CLASS_PLAN H9; core/usage.py): a tab opened
//: or a palette command run is counted here and sent in one request at most
//: every 30 s, and when the page hides. Feature names only, to this app's own
//: server only; Settings, General, What you use reads it back.
//: A write nobody pressed anything for (the usage count, warming the search
//: model): a failure costs the person nothing they asked for, so it goes to
//: the console rather than a toast (tests/test_silent_mutations.py counts the
//: writes that drop a failure with no trace at all).
function backgroundWriteFailed(error) {
  console.debug("A background write failed:", error);
}
const usageQueue = [];
const usageState = { timer: null };
//: A palette command's name in the ledger: its words, without an icon marker.
function usageFeatureName(label) {
  const words = String(label || "").replace(/(^|\s)ph:[\w-]+/g, " ").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return words ? `cmd:${words.slice(0, 55)}` : "";
}
function usageCount(name) {
  usageQueue.push(name);
  if (!usageState.timer) usageState.timer = setTimeout(usageFlush, 30000);
}
function usageFlush() {
  clearTimeout(usageState.timer);
  usageState.timer = null;
  if (!usageQueue.length || !authToken()) return;
  const features = usageQueue.splice(0, 200);
  //: `readOnly`: the count changes nothing the read cache holds.
  api("/usage", { method: "POST", keepalive: true, silent: true, readOnly: true, body: JSON.stringify({ features }) }).catch(backgroundWriteFailed);
}
document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" && usageFlush());

//: Speculative retrieval (WORLD_CLASS_PLAN H9; `POST /search/warm`): a pause
//: in the Ask box or the chat box sends the words, so the question's vector
//: is made before Enter and the first token comes that much sooner.
const warmState = { timer: null, last: "", focused: false };
//: Focus is the earliest sign a note or a question is coming: a model not
//: yet loaded starts loading then, once a page, under the person's typing
//: (Capture too: the first note is filed and found by the same model).
document.addEventListener("focusin", (event) => {
  const id = event.target?.id;
  if (warmState.focused || !["question", "chat-input", "entry-content"].includes(id) || !authToken()) return;
  warmState.focused = true;
  apiJson("/search/warm", { method: "POST", body: JSON.stringify({ q: "" }), silent: true }).catch(backgroundWriteFailed);
});
document.addEventListener("input", (event) => {
  const box = event.target;
  if (box?.id !== "question" && box?.id !== "chat-input") return;
  clearTimeout(warmState.timer);
  warmState.timer = setTimeout(() => {
    const q = box.value.trim();
    if (q.split(/\s+/).length < 3 || q === warmState.last || !authToken()) return;
    warmState.last = q;
    apiJson("/search/warm", { method: "POST", body: JSON.stringify({ q }), silent: true }).catch(backgroundWriteFailed);
  }, 600);
});

async function switchTab(name) {
  if (!(await confirmLeavingUnsavedWork(name))) return;
  usageCount(`tab:${name}`);
  // Profiled directly: leaving the Graph tab left `graphSimulation` running
  //, it is only ever `.stop()`-ed "before every rebuild" (graph.js), never
  // on navigating away: so its tick handler kept costing real main-thread
  // time on every *other* tab until its own alpha naturally decayed. Under
  // 6x CPU throttling on a 120-note graph: busy time on the Dashboard tab
  // measured 21% before ever opening Graph, 58% immediately after leaving
  // it, decaying back to ~20% only after roughly 12 more seconds, a
  // background cost with no relation to whatever tab the person actually
  // switched to, and easily misread as "the app feels slow" generally
  // rather than traced back to the Graph tab. `graphSimulation?.stop()` is
  // safe to call unconditionally on leaving: `renderGraph()` already
  // creates a fresh simulation on the next visit regardless of whether the
  // old one was still running or already stopped.
  const leavingGraph = prefs.get("activeTab", null) === "graph" && name !== "graph";
  recordTabVisit(name);
  //: The next 400ms belong to the page arriving (INBOX 580): the companion's
  //: paced animations hold still through them (`nameMarkBuddyTempo`), so the
  //: main thread's frames go to the new page.
  window.uiSettlingUntil = performance.now() + 400;
  revealTab(name);
  if (leavingGraph) {
    //: `typeof` first: leaving Graph before its bundle has arrived (a press on
    //: another tab inside the fetch) reads a name graph.js declares, and a
    //: bare read of an undeclared name throws (`graphcoldlayout.js`). With
    //: no bundle there is no simulation to stop.
    if (typeof graphSimulation !== "undefined") graphSimulation?.stop();
    // The canvas renderer's simulation is in a Worker, so there is no
    // `graphSimulation` to stop: the same "a cooling layout must not go on
    // running in a tab nobody is looking at" rule needs its own message.
    if (typeof gcStop === "function") gcStop();
    // Full screen is a state of the map, not of the app, and it now hides the
    // top bar and the status bar with it. Leaving the tab while it is on (the
    // command palette and the keyboard shortcuts still work with the chrome
    // hidden) would otherwise land somebody on another tab with no tab bar to
    // get back with.
    if ($("graph-card")?.classList.contains("graph-fullscreen")) toggleGraphFullscreen();
  }
  // The generative-art animation only needs to run while it's on screen.
  if (name !== "dashboard") stopArt();
  // The Library's Images/Files sub-tab polls `/media` every six seconds
  // (library.js), and only another Library *sub-tab* stopped it: leaving the
  // Library itself left it fetching on every other tab until the person came
  // back (INBOX 424 d). Stopped on leaving; restarted on return when that
  // sub-tab is still the one showing.
  if (typeof stopLibraryImagesPoll === "function") {
    if (name !== "library") stopLibraryImagesPoll();
    else if ($("library-view-media") && !$("library-view-media").classList.contains("hidden")) startLibraryImagesPoll();
  }
  //: **The page is revealed first and its data loaded second, with the tab's
  //: own code fetched in between** (WORLD_CLASS_PLAN A1). Everything above
  //: this line is DOM and it stays synchronous, so a tab press still paints
  //: the new page in the same frame it was pressed in; everything below calls
  //: into the file that draws the tab, which for Graph, Library and Documents
  //: may not have been fetched yet. `ensureModule` resolves immediately once
  //: a bundle is in, so this costs one microtask on every visit after the
  //: first. Callers do not await this function (a tab press is not something
  //: to wait on), and the three that do need the tab's code on the next line
  //: say so: the back/forward restore, `#conv-browse-all`, and
  //: `refreshActiveTab`.
  const lazy = TAB_MODULES[name];
  //: **The page is inert until its code is in.** The tab is drawn from
  //: index.html, so between the reveal above and the bundle's arrival every
  //: control on it is on screen and live while the functions its listeners
  //: call (here, wiring.js) do not exist yet: measured on a held-back bundle,
  //: changing the graph's layout threw "setGraphPhysicsEnabled is not
  //: defined", and the zoom buttons, the options' switches and the fit button
  //: read graph.js's state the same way (`scratchpad/ui-sweeps/graphcoldlayout.js`).
  //: `inert` closes the window for every control at once, pointer and
  //: keyboard, rather than one guard per listener; it is set only on the
  //: first visit, so a later switch to a tab that holds focus does not blur it.
  const lazyPage = lazy && !lazyTabsReady.has(lazy) ? $(`tab-${name}`) : null;
  if (lazyPage) {
    lazyPage.inert = true;
    tabPlaceholder(lazyPage, true);
  }
  try {
    if (lazy) await ensureModule(lazy);
  } catch (error) {
    if (lazyPage) tabPlaceholder(lazyPage, false);
    throw error;
  } finally {
    if (lazyPage) lazyPage.inert = false;
  }
  if (lazy) lazyTabsReady.add(lazy);
  let drawing = null;
  if (name === "chat") {
    //: The composer paints first (CHAT_PLAN 8 row 6): the welcome and the
    //: starter chips cost 60 to 120 ms of layout at 390 and were drawn
    //: before the frame that showed the box you came to type in.
    requestAnimationFrame(() => setTimeout(() => {
      renderChatEmptyState(); // welcome placeholder when the thread is empty
      loadChatSuggestions();
    }));
    //: **The composer takes the caret, but not the focus ring, on arrival.**
    //: Reported as "chat panel shadow". Measured on a freshly loaded Chat tab
    //: (`scratchpad/ui-sweeps/chatshadow.js`): `.chat-dock` computed
    //: `box-shadow: rgba(79,109,245,0.14) 0 0 0 3px` with an accent-mixed
    //: border, and `dockFocusWithin: true` with `#chat-input` as the active
    //: element, all before anyone had touched anything. It is not a shadow,
    //: it is `.chat-dock:focus-within`'s accent ring, and the focus that
    //: lights it is the line below, not the reader's. So every visit to Chat
    //: opened with a permanent blue halo round the composer, the loudest
    //: thing on the screen and the only element in the app that rings itself
    //: on load.
    //:
    //: The focus stays (arriving able to type is the point of it); the ring
    //: waits until the focus is the reader's own. `chatDockArmRing` below
    //: takes the marker back off at the first key, the first press inside the
    //: dock, or the moment focus leaves it, so a deliberate click into the
    //: composer rings exactly as it did.
    chatDockSuppressRing();
    $("chat-input").focus();
    // Nothing in a hidden tab can be measured, so the composer's fit is done
    // here rather than at startup, the window may well have changed size
    // since the last time this tab was visible.
    refitComposer();
  }
  //: A return to the tab refreshes what is drawn in place (INBOX 602).
  if (name === "dashboard") whenScriptsLoaded().then(() => renderDashboard({ refresh: true }));
  if (name === "graph") {
    // A fresh visit to the tab frames the whole map; the filter/slider
    // changes that call renderGraph() again while already on this tab
    // leave whatever the user last panned or zoomed to alone (graph.js).
    graphAutoFitDone = false;
    const layout = graphLayout();
    const layoutSelect = $("graph-layout");
    if (layoutSelect) layoutSelect.value = layout;
    
    // Same for what the colours mean: a saved setting the control does not
    // show is a control that lies about the map beside it.
    const savedColour = prefs.get("graph-colour", null);
    const colourSelect = document.getElementById("graph-colour");
    if (savedColour && colourSelect && [...colourSelect.options].some((o) => o.value === savedColour)) {
      colourSelect.value = savedColour;
    }
    //: And what the sizes mean (INBOX 430), the same way.
    const savedSize = prefs.get("graph-size", null);
    const sizeSelect = document.getElementById("graph-size");
    if (savedSize && sizeSelect && [...sizeSelect.options].some((o) => o.value === savedSize)) {
      sizeSelect.value = savedSize;
    }
    // Match the saved layout on arrival, not only on change, otherwise a
    // notebook left on Tree comes back with two live-looking dead sliders.
    setGraphPhysicsEnabled(graphLayout());
    setGraphOptionsOpen(prefs.get("graph-options-open", null) === "1");
    setTracePanelOpen(prefs.get("graph-trace-open", null) === "1");
    drawing = renderGraph();
  }
  if (name === "timeline") {
    // Match the saved bucket choice on arrival, not only on change: a notebook
    // left on Month that comes back on Auto is a control that lies about the
    // feed beside it, which is the same bug the graph's layout picker had.
    $("timeline-scale").value = timelineScaleChoice();
    // Same for which view: a saved choice the segment does not show is a
    // control that lies about the thing under it.
    syncTimelineViewSeg();
    renderTimeline();
  }
  if (name === "documents") {
    drawing = loadDocuments();
    renderDocStorage();
  }
  if (name === "library") drawing = loadLibrary();
  if (name === "reminders") {
    refreshReminderDefaults();
    loadReminders();
  }
  //: The first visit's placeholder gives way once the tab has drawn, or
  //: after 800ms whatever it is doing (`tabPlaceholder`).
  if (lazyPage) Promise.race([drawing, new Promise((r) => setTimeout(r, 800))]).finally(() => tabPlaceholder(lazyPage, false));
}

//: **A heavy tab's first visit shows its shape, not its raw insides**
//: (INBOX 580, the owner: "features like the graph etc need to be more
//: smooth in transitions and cheap to hide the ugly loading glitches").
//: Graph, Library and Documents fetch their own code the first time
//: (`TAB_MODULES`), and until it and their first draw are in, the page was
//: its bare markup: measured (`scratchpad/ui-sweeps/smooth1005-tabs.js`,
//: 1440) four frames with nothing of the page under any of nine points,
//: 488 to 550ms before it was whole. Now the page's own controls wait
//: hidden under one skeleton the size of the page, which fades as they
//: fade in (`.tab-loading`, `.tab-revealing`, 08-consistency.css).
//:
//: **The page's shape, and its name when it is slow** (INBOX 598, the owner:
//: "the loading screen on features like the graph tab and library is a blank
//: screen with a horizontal line in the middle ... might have people thinking
//: it is broken"). The one skeleton was a page-sized box whose title bar and
//: sheen were the only marks on it, held 2.4 to 3.3s on a cold bundle at 4x
//: CPU (`scratchpad/ui-sweeps/loading598.js`). Now each lazy surface draws its
//: own outline from `TAB_SKELETONS` (a dock, then the graph's canvas and its
//: dots, the library's chips and tiles, the documents list and the open
//: page), all `.skeleton` pieces, and past `TAB_SKELETON_NAME_MS` a ring and
//: the surface's name ("Opening the graph…") say it is on its way.
//: Inline styles through the CSSOM (the CSP allows those) because the boot
//: stylesheets are at their cap; every length is a token.
const TAB_SKELETON_NAME_MS = 400;
const TAB_SKELETONS = {
  graph: { name: "the graph", rows: "auto 1fr", build: (add) => {
    const canvas = add({ position: "relative" }, false);
    //: A scatter of nodes where the map will be: fixed spots, so the shape
    //: does not jump between visits, sized like the graph's own dots.
    for (const [x, y, r] of [[22, 30, 1.1], [41, 52, 1.6], [58, 34, 0.9], [67, 61, 1.3], [35, 72, 0.8], [76, 24, 1], [50, 44, 0.7], [84, 58, 0.9]]) {
      canvas.appendChild(tabSkeletonBar({ position: "absolute", left: `${x}%`, top: `${y}%`, width: `${r}rem`, height: `${r}rem`, borderRadius: "50%" }));
    }
  } },
  library: { name: "the library", rows: "auto auto 1fr", build: (add) => {
    //: The filter chips, then the tiles.
    const chips = add({ display: "flex", gap: "var(--space-2)", background: "none", border: "0", animation: "none", overflow: "hidden" }, false);
    for (let i = 0; i < 6; i++) chips.appendChild(tabSkeletonBar({ flex: "0 0 auto", width: "5.5rem", height: "1.9rem", borderRadius: "var(--radius-pill)" }));
    const tiles = add({ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(10rem, 1fr))", gridAutoRows: "9rem", gap: "var(--space-4)", alignContent: "start", background: "none", border: "0", animation: "none" }, false);
    for (let i = 0; i < 12; i++) tiles.appendChild(tabSkeletonPiece({}));
  } },
  documents: { name: "documents", rows: "auto 1fr", build: (add) => {
    //: The documents list beside the open page; a phone has the list alone.
    const phone = matchMedia("(max-width: 599.98px)").matches;
    const area = add({ display: "grid", gridTemplateColumns: phone ? "1fr" : "min(18rem, 32%) 1fr", gap: "var(--space-4)", background: "none", border: "0", animation: "none" }, false);
    const list = document.createElement("div");
    for (let i = 0; i < 7; i++) list.appendChild(tabSkeletonPiece({ height: "3.2rem", marginBottom: "var(--space-2)" }));
    area.appendChild(list);
    if (!phone) area.appendChild(tabSkeletonPiece({}));
  } },
};

//: The `.skeleton` bar's own ink (02-chat-graph.css), for marks drawn inside
//: a piece whose own bars are off.
const TAB_SKELETON_INK = "color-mix(in srgb, var(--ink) 10%, transparent)";

function tabSkeletonPiece(style, bars = true) {
  const el = document.createElement("div");
  el.className = "skeleton";
  el.setAttribute("aria-hidden", "true");
  Object.assign(el.style, { margin: "0", height: "auto", minHeight: "0" }, style);
  //: The title and text bars `.skeleton` draws are right on a tile or a row
  //: and wrong on a canvas, a dock or a wrapper: there they are the "line".
  if (!bars) el.style.setProperty("--sk-bar", "transparent");
  return el;
}

function tabSkeletonBar(style) {
  const el = document.createElement("div");
  el.setAttribute("aria-hidden", "true");
  Object.assign(el.style, { background: TAB_SKELETON_INK, borderRadius: "var(--radius-sm)" }, style);
  return el;
}

//: The dock every one of these pages opens with: its name, then its actions.
//: A phone's dock is narrow, and its middle is where the named state goes,
//: so it keeps one action and no name bar.
function tabSkeletonDock() {
  const phone = matchMedia("(max-width: 599.98px)").matches;
  const dock = tabSkeletonPiece({ display: "flex", alignItems: "center", gap: "var(--space-3)", height: "calc(var(--target-min) + var(--space-4))", paddingInline: "var(--space-4)" }, false);
  if (!phone) dock.appendChild(tabSkeletonBar({ width: "min(9rem, 30%)", height: "0.8rem" }));
  dock.appendChild(tabSkeletonBar({ flex: "1", background: "none" }));
  for (let i = 0; i < (phone ? 1 : 3); i++) dock.appendChild(tabSkeletonBar({ width: "2rem", height: "2rem", borderRadius: "var(--radius-md)" }));
  return dock;
}

function tabPlaceholder(page, on) {
  let ph = page.querySelector(":scope > .tab-placeholder");
  if (on) {
    if (ph) return;
    const spec = TAB_SKELETONS[page.id.replace(/^tab-/, "")];
    ph = document.createElement("div");
    ph.className = "tab-placeholder";
    //: **This was the "horizontal line in the middle".** The page is a flex
    //: column that centres its children, and an absolutely placed child of a
    //: flex box takes `align-self` from it: with both insets set it was not
    //: stretched between them but shrunk to its content (49px, the old box's
    //: two bars) and centred, 439px down a 799px page and wider than it
    //: (measured, 1440). Stretched both ways, and `width` back to auto from
    //: the page children's full width, it is the page's own box.
    ph.style.alignSelf = "stretch";
    ph.style.justifySelf = "stretch";
    ph.style.width = "auto";
    if (!spec) {
      ph.classList.add("skeleton");
      ph.setAttribute("aria-hidden", "true");
    } else {
      Object.assign(ph.style, { display: "grid", gridTemplateRows: spec.rows, gap: "var(--space-4)" });
      ph.appendChild(tabSkeletonDock());
      spec.build((style, bars) => ph.appendChild(tabSkeletonPiece(style, bars)));
      const status = document.createElement("p");
      status.className = "muted tab-ph-status";
      status.setAttribute("role", "status");
      //: In the middle of the dock, the one place on every surface the outline
      //: leaves empty, so it never sits over a tile or the canvas.
      Object.assign(status.style, { position: "absolute", insetInline: "0", top: "0", height: "calc(var(--target-min) + var(--space-4))", margin: "0", pointerEvents: "none", display: "flex", justifyContent: "center", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)", opacity: "0", transition: "opacity var(--motion-base) var(--ease-out)" });
      setLabel(status, `ph:spin Opening ${spec.name}…`);
      ph.appendChild(status);
      ph.dataset.late = String(setTimeout(() => (status.style.opacity = "1"), TAB_SKELETON_NAME_MS));
    }
    page.prepend(ph);
    page.classList.add("tab-loading");
    return;
  }
  if (!ph) return;
  clearTimeout(Number(ph.dataset.late));
  page.classList.replace("tab-loading", "tab-revealing");
  ph.classList.add("tab-placeholder-leaving");
  setTimeout(() => {
    ph.remove();
    page.classList.remove("tab-revealing");
  }, 260);
}

// --- Timeline: moved to timeline.js --------------------------------------------
// The Timeline tab (§10B, TIMELINE_PLAN.md) lives in timeline.js, loaded at
// boot right after dashboard.js. Two things that sat inside its old line
// range stay here: `stripMarkdownPreview`, because `plainText` (earlier in
// this file) is built on it and is called app-wide, and the graph's layout picker
// listener, which is the graph's control. See timeline.js's header.

// The preview is the raw note text sliced to 120 chars server-side (§37J): 
// `**bold**` and `# a heading` showed their literal punctuation in the one
// place they're smallest and most cramped to read. Full `renderMarkdown`
// builds block-level DOM (headings, code blocks with a copy button) that
// doesn't make sense clamped to two lines inside a button, so this strips the
// syntax to plain words instead. The slice can land mid-token, `**bold te`
// with no closing `**`, so every rule here deletes delimiter characters
// outright rather than matching opening/closing pairs, which handles a
// truncated run the same way as a complete one.
function stripMarkdownPreview(text) {
  return text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/`{1,3}/g, "")
    .replace(/\*\*/g, "")
    .replace(/__/g, "")
    .replace(/~~/g, "")
    .replace(/[*_](?=\S)|(?<=\S)[*_]/g, "")
    .replace(/!?\[([^[\]\n]*)\]\([^()\n]*\)?/g, "$1");
}

// Layout picker (§9). Stored, because which shape suits a notebook is a
// property of the notebook rather than of one visit.
$("graph-layout").addEventListener("change", async (event) => {
  prefs.set("graph-layout", event.target.value);
  //: The picker is drawn at boot and graph.js is not (`switchTab`'s `inert`
  //: covers a person's press; this covers a change made from script, a saved
  //: view or the palette, before the first visit). `setGraphPhysicsEnabled`
  //: and `renderGraph` are stand-ins that would load it anyway; the await is
  //: for `graphAutoFitDone`, a `let` in graph.js, which a bare assignment on a
  //: cold bundle would write to a stray global that graph.js's own binding
  //: then shadows, so the re-frame asked for here would be lost.
  await ensureModule("graph");
  setGraphPhysicsEnabled(event.target.value);
  // A different layout is a different shape (a radial ring is nothing like
  // a force-directed cloud): re-frame for it, unlike the filter/slider
  // changes that intentionally leave the camera alone.
  graphAutoFitDone = false;
  renderGraph();
});

// --- Notes sub-tabs ---------------------------------------------------------------
// Four full-height cards stacked on one page meant scrolling past three forms
// you weren't using to reach your notes (roadmap §10). Folding each card
// helped, but it was mitigation: you still had four things to manage.
//
// The per-card collapse chevrons are retired here rather than kept alongside.
// Two mechanisms for hiding the same card is exactly the trap that had the
// Notes sections not collapsing at all a few sessions ago, one implementation
// quietly undoing the other.

const NOTES_SECTIONS = ["browse", "capture", "writing-room", "ask", "questions"];
const NOTES_SECTION_STORE = "notesSection";

// --- a new session starts at the front of every tab ----------------------------
//
// Reported directly: "Ive had times where I log into the app, click on the
// notes tab, and the tab is selected on 'Writing room' instead of 'Your
// Notes' because that must have been what I was on last."
//
// **Which sub-tab you are on is not a preference; it is where you happen to
// be standing.** Reopening on the last *tab* is useful, you were working on
// something. Reopening three levels in, on a sub-tab you visited once a week
// ago, is not: it reads as the app being in a state you did not put it in,
// and the deeper the restore the more true that is. So a new session lands on
// each tab's front page.
//
// `sessionStorage`, not a timestamp or a login hook, and the distinction it
// draws is exactly the right one: it survives a reload (F5, or the desktop
// window reloading itself after an update) and is cleared when the tab or the
// app window closes. So "I refreshed" keeps your place and "I started the app
// again" does not.
//
// Only navigation is reset. `library-view`'s grid/list, the timeline's own
// bucket size, reminders' list/calendar and the document editor's Live/Source
// choice are display preferences someone deliberately set, and clearing those
// would be a different, and unwanted, change.
const SESSION_STARTED_KEY = "mm-session-started";
const NAVIGATION_KEYS = [NOTES_SECTION_STORE];

function resetNavigationForNewSession() {
  try {
    if (sessionStorage.getItem(SESSION_STARTED_KEY)) return false;
    sessionStorage.setItem(SESSION_STARTED_KEY, "1");
  } catch {
    // Storage can throw outright (a private window, a shell with site data
    // blocked). Not resetting is the safe answer, it leaves the previous
    // behaviour rather than resetting on every single navigation.
    return false;
  }
  for (const key of NAVIGATION_KEYS) prefs.remove(key);
  return true;
}

// Run at load, before anything can have navigated. One-shot per session: a
// reload inside the same session finds the marker and leaves your place
// alone, which is the distinction sessionStorage draws for free.
resetNavigationForNewSession();

function resetNavigationToDefaults() {
  for (const key of NAVIGATION_KEYS) prefs.remove(key);
  // The Library's switcher keeps its state in the DOM (which button carries
  // `.active`), not in storage, so clearing a key cannot reach it. Clicking
  // its default button reuses the real handler, which also shows the right
  // section, stops the gallery poll and lands the whiteboard view correctly.
  // A second copy of that logic here is exactly the shape this codebase keeps
  // getting bitten by.
  const allTab = document.querySelector(
    '#library-subtabs button[data-target="library-view-documents"]'
  );
  if (allTab && !allTab.classList.contains("active")) allTab.click();
  // If the Notes strip is already built, put it back on its front page now;
  // on a cold load it has not been built yet and will read the cleared key.
  if (document.getElementById("notes-subtabs")?.dataset.ready) {
    showNotesSection("browse");
  }
}

function activeNotesSection() {
  const saved = prefs.get(NOTES_SECTION_STORE, null);
  return NOTES_SECTIONS.includes(saved) ? saved : "browse";
}

function showNotesSection(name, { focus = false } = {}) {
  // The picker lists documents that may have been created since this page
  // loaded: a stale list is how "add to document" ends up offering nothing.
  if (name === "capture") loadCaptureDocuments();
  if (name === "writing-room") draftSaveMenuInit();
  //: Questions (row 7) re-reads its list each time it is shown.
  if (name === "questions") {
    initQuestionsView();
    loadQuestions();
  }
  const wanted = NOTES_SECTIONS.includes(name) ? name : "browse";
  // A sub-tab move is a navigation, so it becomes a history step too. Recorded
  // against the Notes tab specifically because that is the tab these sections
  // belong to: switchTab records its own entry when the *tab* changes, and
  // recordTabVisit ignores a repeat of where you already are, so arriving at
  // Notes and then landing on a section does not produce two entries.
  //
  // **Only when Notes is the tab on screen** (INBOX 311). Setting a hidden
  // tab's default section is not a navigation, and two boot steps do exactly
  // that: `initNotesSubtabs` ends by selecting whichever section was last
  // open, and the first `loadEntries` selects browse. Measured on a fresh
  // load that never left the Dashboard, the stack was
  // `["notes:browse", "dashboard", "notes:browse"]` with the pin on the last,
  // so the history claimed you were in Notes while the Dashboard was drawn,
  // Back went somewhere you had never been, and the owner reported exactly
  // that. `revealTab` writes `activeTab` before any of a tab's own loading
  // runs, so by the time a real arrival calls this, it reads "notes".
  if ((prefs.get("activeTab", null) || "dashboard") === "notes") {
    recordTabVisit("notes", wanted);
  }
  for (const id of NOTES_SECTIONS) {
    const card = document.getElementById(id);
    if (card) card.classList.toggle("hidden", id !== wanted);
  }
  for (const button of document.querySelectorAll("#notes-subtabs button")) {
    const active = button.dataset.section === wanted;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
    // Roving tabindex: the strip is one tab stop, arrows move within it.
    button.tabIndex = active ? 0 : -1;
    if (active && focus) button.focus();
  }
  prefs.set(NOTES_SECTION_STORE, wanted);
  //: Ask's answer and the draft carry static assistant heads (INBOX 471).
  paintAssistantHeads();
  //: The connections rail belongs to the list (notes-list.js): it leaves with
  //: Browse and comes back with it.
  scheduleNotesRail();
  // A textarea measured while its section is display:none reports
  // scrollHeight 0, so autoGrow collapsed the capture box to its minimum and
  // it only sprang open once clicked (user-reported). Re-measure now that the
  // section is actually visible.
  autoGrowVisible();
}

function initNotesSubtabs() {
  const strip = document.getElementById("notes-subtabs");
  if (!strip || strip.dataset.ready) return;
  strip.dataset.ready = "1";
  strip.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-section]");
    if (button) showNotesSection(button.dataset.section);
  });
  strip.addEventListener("keydown", (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const order = [...strip.querySelectorAll("button[data-section]")].map(
      (b) => b.dataset.section
    );
    const index = order.indexOf(activeNotesSection());
    showNotesSection(order[(index + step + order.length) % order.length], {
      focus: true,
    });
  });
  showNotesSection(activeNotesSection());
}

// The Notes tab's bin, activity and tag panels are gone (§36G).
//
// Each of them had a second implementation in the Library, the same list,
// the same controls: and the bin's two could disagree about what was in it,
// because each fetched its own. Three surfaces, three render functions, three
// blocks of markup and a `showPanel` that hid whichever two you were not
// looking at, all replaced by a filter chip on a screen built for exactly
// this. The last thing the panel could do that the Library could not was show
// a binned note in full; `openBinnedNote` above is that, and it is the reason
// this could finally go.
//
// This is the first surface this project has *removed* rather than added.

// The element that actually scrolls (§36A). The window no longer does, the
// visible .tab-page is its own scroll container, so the scrollbar starts below
// the top bar instead of running behind it.
function scrollingPage() {
  return document.querySelector(".tab-page:not(.hidden)");
}

// --- back-to-top button -----------------------------------------------------------
// Shown on every tab except the graph, where the page itself doesn't scroll
// and the button would just sit on top of the map.
//
// Chat, Notes and Library are special cases, not exclusions: `.tab-page`
// itself never scrolls on any of the three, each uses a flex column with a
// nested real scroll container instead (`#tab-chat`/`#tab-notes
// > .layout > .tab-main`, see 04-chat-dock-appearance.css; `#tab-library`'s
// active `.library-view-section`, see 07-whiteboard-misc.css), so a button
// watching `.tab-page.scrollTop` would see 0 forever and never show, and
// clicking it would scroll an element that never moves. Reported as "the
// back-to-top button doesn't appear in all places it should (like the
// Library)" twice: Notes was fixed first, but the *actual* top-level
// Library tab (Documents/AI Skills/Whiteboards/Image Gallery) turned out to
// have the identical shape and was still missing it. One lookup table, one
// target per tab, rather than a growing pile of hardcoded special cases.
//
// **Chat is excluded too, but for the opposite reason (INBOX 34).** This
// button used to flip into a "jump to the newest message" arrow there,
// reading the same distance-from-bottom `#chat-jump-latest` (the pill
// above the composer) already does. Reported and reproduced: both showed
// at once on a brand-new chat with nothing to scroll, because starting one
// clears `#chat-messages` without firing the scroll/resize event this
// button's own `update()` waits for, leaving whichever state the *previous*
// conversation left it in. Decision: one control in chat, the pill (it is
// already wired to `syncChatJumpLatest`, called right after that clear);
// this button simply never shows there any more rather than needing to be
// kept in sync with a second copy of the same "scrolled away" logic.
const NO_SCROLL_TOP_TABS = new Set(["graph", "chat"]);
const NESTED_SCROLL_TABS = {
  chat: () => chatMessagesEl(),
  notes: () => document.querySelector("#tab-notes .layout > .tab-main"),
  // The Whiteboards sub-view pans rather than scrolls (like Graph), so it
  // deliberately returns nothing here, scrollTopTargetEl() then falls
  // back to scrollingPage(), whose scrollTop is always 0 on this tab,
  // which is exactly what keeps the button correctly hidden there.
  library: () => {
    const visible = document.querySelector("#tab-library .library-view-section:not(.hidden)");
    return visible && visible.id !== "library-view-whiteboard" ? visible : null;
  },
};
let scrollTopUpdate = null;

function chatMessagesEl() {
  return document.getElementById("chat-messages");
}

function scrollTopTargetEl() {
  const tab = prefs.get("activeTab", null) || "dashboard";
  return NESTED_SCROLL_TABS[tab]?.() || scrollingPage();
}

// A content panel can be narrower than the viewport and sit behind its own
// real scrollbar, which a fixed CSS `right` offset doesn't know to clear, 
// and the panel's own box can run taller than the viewport, which a fixed
// CSS `bottom` offset doesn't know to stay above. Reported, more than once
// and on more than one tab (first Library, then screenshotted on Notes'
// "Your notes" and "Ask" sub-tabs): the button overlapping the scrollbar and
// the content beside it, or sitting below the visible fold. Computed here
// instead of in CSS, from the *actual scroll target*'s live
// `getBoundingClientRect()`, the same one `scrollTopTargetEl()` already
// resolves per tab: for every tab but Chat (reparented into `.chat-dock`
// and positioned by its own CSS instead), clamped so the button can never
// end up outside the visible viewport no matter how tall the panel's box
// actually is.
function positionScrollTopForNested(button, tab) {
  if (tab === "chat") {
    // Reparented into .chat-dock by the MutationObserver below and
    // positioned by that container's own CSS instead, inline right/bottom
    // here would fight it rather than help it.
    button.style.right = "";
    button.style.bottom = "";
    return;
  }
  // Anchoring to the actual scrolling content panel, not the viewport,
  // for every tab: not just Library and Notes. A flat `right`/`bottom`
  // offset from the *window* edge is correct only when the panel happens to
  // reach that edge; the moment a real (non-overlay) scrollbar reserves
  // layout width the panel's own `getBoundingClientRect()` doesn't subtract
  // for, that flat offset lands the button sitting on top of the scrollbar
  // and the content beside it (reported, screenshotted: an up-arrow button
  // overlapping the scrollbar's own down-arrow and a line of note text on
  // Notes' "Your notes" and "Ask" sub-tabs): and every tab shares the same
  // scroll container shape (`scrollTopTargetEl()`), so the fix has to be
  // general rather than three more special cases in `NESTED_SCROLL_TABS`.
  const panel = scrollTopTargetEl();
  const rect = panel?.getBoundingClientRect();
  if (!panel || !rect) {
    button.style.right = "";
    button.style.bottom = "";
    return;
  }
  const margin = 24; // 1.5rem, matching every other tab's own offset

  // Real (non-overlay) scrollbars reserve layout width that
  // getBoundingClientRect() doesn't subtract for; measuring it live
  // (0 on this project's own sandbox and macOS, 15-17px on most
  // Windows/Linux setups) replaces what used to be a flat guessed
  // constant, wrong in both directions depending on platform.
  const scrollbarClearance = panel.offsetWidth - panel.clientWidth;

  // A right-side element the panel's own edge doesn't already account for, 
  // today only the AI Skills sidebar, sitting *inside* Library's own panel
  // rather than beside it. Notes' sidebar is on the *left*, so it never
  // needs this branch; most panels don't have one at all.
  const rightPanel = document.querySelector("#library-view-skills:not(.hidden) #skills-sidebar");
  if (rightPanel) {
    const rightPanelRect = rightPanel.getBoundingClientRect();
    const right = `${Math.max(margin, window.innerWidth - rightPanelRect.left + margin + scrollbarClearance)}px`;
    if (button.style.right !== right) button.style.right = right;
  } else {
    const right = `${Math.max(margin, window.innerWidth - rect.right + margin + scrollbarClearance)}px`;
    if (button.style.right !== right) button.style.right = right;
  }

  // **Bottom**: a panel shorter than the viewport must not leave the button
  // floating below its own content.
  const bottom = `${Math.max(margin, window.innerHeight - Math.min(rect.bottom, window.innerHeight) + margin)}px`;
  //: Only when it moved: an inline-style write invalidates style even when
  //: the value is the same, and this runs on every scroll frame.
  if (button.style.bottom !== bottom) button.style.bottom = bottom;
}

//: **The back-to-top button must never sit on top of a Save button.**
//: Reported with a screenshot of the capture form: the floating button
//: landed over the one irreversible action on the screen, so the control you
//: reached for was not the one you got.
//:
//: This is a geometric test rather than a bigger `bottom` offset, and that is
//: deliberate. The button is `position: fixed` at the bottom-right of the
//: viewport while a form's footer can be at any scroll position and any
//: width, so "raise it by 3rem" is a value that happens to work at the width
//: it was measured at and silently stops working at the next one. Asking, on
//: every scroll and resize, whether the two boxes actually intersect is the
//: only version of this that is a guarantee.
//:
//: Touching counts as covering: the clearance below is the same step the rest
//: of the app puts between two adjacent controls, because the point is that
//: the floating button and the form's Save must never read as one cluster.
//:
//: Only *primary* buttons count. A form footer also holds ghost buttons
//: (Discard, Undo, Extract notes), and hiding the back-to-top control every
//: time one of those drifted underneath would make it flicker in and out on
//: pages that have no problem at all.
//: **Scopes first, then their buttons, and only the scopes on screen.** This
//: runs on every scroll frame while the button shows, and it used to be one
//: descendant selector over the whole document: every button in the app was
//: matched against six scopes, including the hundreds inside the Settings
//: dialog, which is in the DOM and hidden nearly all the time. Traced over a
//: 30-step wheel scroll at 1184x760: this callback was 185ms on the Library
//: and 203ms on Notes, the largest script cost of the scroll. A scope that is
//: not rendered (`getClientRects()` is empty) is skipped before any of its
//: buttons are looked at. And the scopes are found by id and by live
//: class collections, never by a selector: a `querySelectorAll` of the six
//: scopes alone measured 1.5ms a call over the app's 10,700 elements, where
//: the collections below are kept up to date by the engine and cost nothing
//: to walk (15 elements).
const FORM_PRIMARY_SCOPE_IDS = ["capture", "writing-room", "ask"];
const FORM_PRIMARY_SCOPE_CLASSES = ["doc-ai-card", "extract-card", "modal-card"].map((name) =>
  document.getElementsByClassName(name)
);
const FORM_PRIMARY_BUTTON = "button:not(.ghost):not(.icon-only):not(.linklike)";

function formPrimaryButtons() {
  const out = [];
  const take = (scope) => {
    if (scope && scope.getClientRects().length) out.push(...scope.querySelectorAll(FORM_PRIMARY_BUTTON));
  };
  for (const id of FORM_PRIMARY_SCOPE_IDS) take(document.getElementById(id));
  for (const list of FORM_PRIMARY_SCOPE_CLASSES) for (const scope of list) take(scope);
  return out;
}

//: `--space-3` is declared in rem and wrapped in the density multiplier, so
//: it cannot be read as a pixel count directly. Resolving it through a real
//: element is what makes the clearance track the density setting instead of
//: freezing at one multiplier's value.
//: Cached, because the probe below is a body append: every call forced a
//: whole-document style recalc and layout, and the back-to-top button asked
//: on every scroll frame (traced: 1,732-element recalcs per frame on Notes).
//: A spacing token only moves with the root's text size, density or look,
//: all of which are attributes or inline style on <html>, or with a resize.
const spacingPxCache = new Map();
window.addEventListener("resize", () => spacingPxCache.clear(), { passive: true });
new MutationObserver(() => spacingPxCache.clear()).observe(document.documentElement, { attributes: true });

function spacingPx(name, fallback) {
  if (spacingPxCache.has(name)) return spacingPxCache.get(name);
  const px = measureSpacingPx(name, fallback);
  spacingPxCache.set(name, px);
  return px;
}

function measureSpacingPx(name, fallback) {
  const probe = document.createElement("div");
  probe.style.cssText = `position:absolute;visibility:hidden;width:var(${name})`;
  document.body.appendChild(probe);
  const px = probe.getBoundingClientRect().width;
  probe.remove();
  return px > 0 ? px : fallback;
}

function coversAFormPrimary(button) {
  const f = button.getBoundingClientRect();
  if (!f.width || !f.height) return false;
  const pad = spacingPx("--space-3", 8);
  for (const el of formPrimaryButtons()) {
    const s = el.getBoundingClientRect();
    if (!s.width || !s.height) continue;
    //: Off-screen footers cannot be covered, and skipping them keeps this to
    //: a handful of rect reads per scroll event.
    if (s.bottom < 0 || s.top > window.innerHeight) continue;
    const clear =
      f.right < s.left - pad ||
      f.left > s.right + pad ||
      f.bottom < s.top - pad ||
      f.top > s.bottom + pad;
    if (!clear) return true;
  }
  return false;
}

function initScrollTopButton() {
  const button = document.createElement("button");
  button.id = "scroll-top";
  button.className = "scroll-top";
  button.type = "button";
  setLabel(button, "ph:arrow-up");
  button.title = "Back to top";
  button.setAttribute("aria-label", "Back to top");
  button.addEventListener("click", () => {
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const target = scrollTopTargetEl();
    //: **In a chat, the thing you have scrolled away from is the bottom.**
    //: Reported: *"the back to top button in the chat should be a back to
    //: bottom instead."* A transcript is written downwards and the newest
    //: message, the one being streamed, is the last one; sending a reader
    //: to the top sends them to the oldest question in the thread, which is
    //: the one place nobody scrolled up to look for.
    const toBottom = button.dataset.mode === "bottom";
    target?.scrollTo({
      top: toBottom ? target.scrollHeight : 0,
      behavior: smooth ? "smooth" : "auto",
    });
    // Send focus somewhere sensible rather than leaving it on a button that
    // is about to hide itself.
    if (toBottom) $("chat-input")?.focus();
    else document.querySelector(".tab-page:not(.hidden)")?.focus();
  });
  document.body.appendChild(button);

  let wasVisible = false;
  const update = () => {
    const tab = prefs.get("activeTab", null) || "dashboard";
    const target = scrollTopTargetEl();
    const scrollTop = target?.scrollTop || 0;
    //: Chat flips the button over: it appears when you have scrolled *up*
    //: away from the newest message, and it takes you back down. 200px rather
    //: than 400 because a chat pane is shorter than a page and one message
    //: scrolled past is already enough to lose the live one.
    const chat = tab === "chat";
    const fromBottom = target ? target.scrollHeight - target.clientHeight - scrollTop : 0;
    //: **The dashboard shows it sooner, and that is the report.** The owner:
    //: "also no back to top button appears on the dashboard??" Measured on a
    //: seeded profile at 1440x900 it does appear, but only past 400px, and
    //: the dashboard is the one page in the app whose *first* content sits at
    //: y=613: the hero, the start band and the stats strip are 600px of
    //: preamble before a single widget. So 400px of scrolling is barely one
    //: screen in, on the longest scan-page the app has, and the button that
    //: gets you back is still absent. 200px is chat's figure, for the same
    //: reason chat uses it: this pane is scrolled in short movements and one
    //: screen away is already lost.
    const show = chat
      ? fromBottom > 200
      : scrollTop > (tab === "dashboard" ? 200 : 400) && !NO_SCROLL_TOP_TABS.has(tab);
    //: Written only when they change: this runs on scroll, and a text or
    //: attribute write on every frame invalidates style that the layout reads
    //: just below (`coversAFormPrimary`, `positionScrollTopForNested`) then
    //: have to recompute.
    const mode = chat ? "bottom" : "top";
    if (button.dataset.mode !== mode) {
      button.dataset.mode = mode;
      setLabel(button, chat ? "ph:arrow-down" : "ph:arrow-up");
      const label = chat ? "Jump to the newest message" : "Back to top";
      button.title = label;
      button.setAttribute("aria-label", label);
    }
    const visible = show && !NO_SCROLL_TOP_TABS.has(tab) && !coversAFormPrimary(button);
    button.classList.toggle("visible", visible);
    //: INBOX 33: `--scroll-top-clearance` used to be unconditional
    //: `padding-bottom` on every scrolling list, so a short page (an empty
    //: Ask sub-tab, three notes on a fresh space) scrolled a hundred-odd
    //: pixels of nothing at its own bottom even though this button was
    //: nowhere near visible to need clearing. Read by 04-chat-dock-
    //: appearance.css and 07-whiteboard-misc.css, which now apply the
    //: clearance only while this class says the button is actually there
    //: to clear.
    document.body.classList.toggle("scroll-top-visible", visible);
    //: A hidden button has nowhere to be: its box is only measured while it
    //: shows, and once more on the frame it goes, so it hides where it was.
    if (visible || wasVisible) positionScrollTopForNested(button, tab);
    wasVisible = visible;
  };
  // Capture, because scroll events do not bubble: the listener has to see them
  // on whichever .tab-page is currently the scroll container, and that changes
  // every time the user switches tab.
  //: **Once per frame, not once per scroll event** (INBOX 392's optimisation
  //: pass, the method that fixed the board's pan: trace, then remove the work
  //: nobody sees). A wheel or trackpad sends several scroll events a frame,
  //: and each ran this in full, layout reads included: traced at the desktop
  //: window, 77ms on the dashboard, 194ms on Notes and 267ms on the Library
  //: over a 30-step scroll.
  let updateFrame = 0;
  const scheduleUpdate = () => {
    if (updateFrame) return;
    updateFrame = requestAnimationFrame(() => {
      updateFrame = 0;
      update();
    });
  };
  document.addEventListener("scroll", scheduleUpdate, { passive: true, capture: true });
  window.addEventListener("resize", scheduleUpdate, { passive: true });
  update();
  return update;
}

const chatTabNode = document.getElementById("tab-chat");
if (chatTabNode) {
  new MutationObserver(() => {
    const btn = document.querySelector(".scroll-top");
    const dock = document.querySelector(".chat-dock");
    if (!btn || !dock) return;

    if (!chatTabNode.classList.contains("hidden")) {
      dock.appendChild(btn);
    } else {
      document.body.appendChild(btn);
    }
  }).observe(chatTabNode, { attributes: true, attributeFilter: ["class"] });
}

// Library used to relocate the button into #tab-library's own DOM subtree
// the same way Chat does, relying on CSS `position: absolute` there. Moved
// to a JS-computed `position: fixed` offset instead (positionScrollTopForNested,
// called from initScrollTopButton's own `update()`), reparenting the button
// is no longer needed, and not reparenting it also sidesteps a real CSS trap:
// if any ancestor between it and <body> ever gains a `transform`/`filter`/
// `backdrop-filter` (Library's glass-tier cards are exactly the kind of
// element that might), that ancestor silently becomes the containing block
// for `position: fixed` too, and the button would jump to being positioned
// relative to *that* instead of the viewport again.

// --- overlay focus-return, scroll lock, autogrow textareas -----------------
// SETTINGS_SECTIONS and the settings-modal shell itself moved to
// settings.js (§88.3 item 4). `overlayReturnFocus` stays: it is shared by
// every dialog in the app (the sketch pad, meeting recorder, improve-writing
// panel, onboarding, the command palette and more, grepped every call site
// before deciding, the same check the other three splits in this series
// describe doing), not owned by Settings, and it has to be defined here
// regardless since dashboard.js already reads and writes it as one of the
// app.js globals its own split's header names.

// Where to send focus back when a dialog closes (Wave L).
let overlayReturnFocus = null;

// --- page scroll lock while any overlay is open ---------------------------------
// Every dialog in the app is a `.modal-overlay` toggled by the `hidden` class,
// and the page behind kept scrolling under them, you'd reach for the settings
// scrollbar and move the notebook instead (user-reported). Rather than pairing
// a lock/unlock onto each of the seven open/close sites (and every one added
// later), one observer watches the overlays and derives the lock from whatever
// is actually visible. Overlays created on the fly, the image lightbox, are
// picked up by the same observer watching <body> for added nodes.
// `.lightbox` is the same idea under a different class (it's built at runtime
// rather than living in index.html), so it locks the page too.
const OVERLAY_SELECTOR = ".modal-overlay, .lightbox";

function syncScrollLock() {
  const anyOpen = [...document.querySelectorAll(OVERLAY_SELECTOR)].some(
    (el) => !el.classList.contains("hidden") && el.isConnected
  );
  document.documentElement.classList.toggle("modal-open", anyOpen);
}
