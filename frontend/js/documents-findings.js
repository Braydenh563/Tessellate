// documents-findings.js: the three shapes a finding is drawn in: gutter, margin and the suggestions panel.
// Moved out of documents.js whole (L-documents-117) and wrapped: only what other files call goes on `window`.
(() => {
  //: State that moved here from documents.js (L-documents-118).
  let docFirstPress = null;
  // =============================================================================
  // The three shapes a finding is drawn in (DOCUMENTS_PLAN Phase 0 and Phase 2)
  // =============================================================================
  //
  // **What used to be here, and where it went.** Phase 0 drew the findings on a
  // `<div>` behind the textarea: same text, same type, same size, with the
  // textarea's own ink turned transparent so the reader looked at the div and
  // typed into the box. It was the standard technique and it was the right
  // answer while the surface was a textarea, but it cost twenty-six computed
  // properties copied on every resize to keep two layers of glyphs on top of
  // each other, and the comment it carried recorded what happens when one of
  // them is missed: the underline is right at the top of the file and a word
  // out by the bottom.
  //
  // Phase 2 decision 5 retires it. The findings are mark decorations inside the
  // engine now (`docFindingsPlugin`), which have no geometry to keep in step
  // because they *are* the text, and they are drawn in every view rather than
  // only in the two the backdrop could cover. What is left here is the part
  // that was never about the layer: which findings are drawable at all, and
  // what shape each kind gets.


  // --- inline completion --------------------------------------------------------
  //
  // **Where the words come from, and why not a dictionary.** A generic English
  // word list would suggest "thereabouts" while you are writing about your own
  // project and never once offer the word you actually use twenty times a day.
  // The useful vocabulary of a document is the document, plus the notebook it
  // sits in: your project names, your people, your jargon, spelled the way you
  // spell them. So the index is built from this document's own words and the
  // notebook's note titles and tags, which also means it needs no download, no
  // model, and no network, and it is *right* on the first character rather than
  // after a paragraph of context.




  // --- autocorrect --------------------------------------------------------------


  // --- wiring -------------------------------------------------------------------
  //
  // One delegated pair on `document` rather than listeners per box: the live
  // view replaces its textareas on every render, and per-box listeners are the
  // shape that silently accumulates duplicates (tests/test_frontend_handlers.py
  // exists because of exactly that).



  //: **Tab moves between table cells**, on the one model the renderer and the
  //: cell menu also use.
  //:
  //: This was a second reading of the line before Phase 3: it found the pipes
  //: with a scan that required the row to *start* with one, so a table written
  //: without outer pipes (which GFM allows and people write) had no Tab at all;
  //: it could not tell a header from a body row except by a regex for dashes;
  //: and the row it added was `| | |` whatever the table around it looked like.
  //: All three are properties of the parse, and there is a parse now. Returns
  //: false anywhere that is not a table, so the indent behaviour below is
  //: untouched.
  function docTableTab(event, box) {
    const context = docTableContext(box);
    if (!context) return false;
    event.preventDefault();
    docTableTabStep(event.shiftKey, context);
    return true;
  }




  //: **Clicking the flagged word itself.** Reported: "I cant click on the
  //: flagged word or phrase and see a popup for suggested fixes."
  //:
  //: A `<textarea>` cannot carry marks inside its text, its value is a string,
  //: not a DOM: so there is nothing there to underline and nothing to click.
  //: What there *is* is a caret with an offset, which is exactly what a finding
  //: is expressed in. So: double-click (or right-click) a word, and if a finding
  //: covers that offset its menu opens at the caret. Stated plainly because the
  //: absence of a squiggle is a real difference from Word, and the reason for it
  //: is structural rather than an omission.
  //:
  //: With CodeMirror under the editor the squiggle is a real decoration in
  //: every view, so the gesture below is no longer the substitute it was: it is
  //: the keyboard route to the same menu the underline opens.
  function docFindingAtOffset(offset) {
    return docProseFound.find((finding) => offset >= finding.start && offset <= finding.end) || null;
  }

  //: The caret, in the document's own coordinates. One editor, one set of
  //: offsets: the live-block translation this used to carry went with the
  //: per-paragraph boxes.
  function docOffsetOf(box) {
    return box ? box.selection().from : null;
  }

  //: **The word under the pointer, found by asking the marks rather than the
  //: textarea.** Right-clicking a word is how everyone expects to be offered a
  //: correction for *that* word, and a right-click does not reliably move the
  //: caret first, so reading `selectionStart` answered a question about wherever
  //: the caret was last left. That is half of "i still cant select on an
  //: underlined incorrectly spelled word and have a popup with suggestions".
  //:
  //: This used to call `document.caretPositionFromPoint`, and **that was wrong
  //: in a way nothing here could see.** Measured in Chromium against a running
  //: app: inside a `<textarea>` it returns the offset *within the visual line*,
  //: not within the value. A caret at document offset 29 hit-tests as 6, at 50
  //: as 5, at 60 as 15. So on every line but the first it looked up a finding at
  //: an offset tens or hundreds of characters earlier, which either opened the
  //: wrong word's menu or, far more often, silently found nothing and let the
  //: browser's own menu through. The feature read as "sometimes it works".
  //:
  //: Since Phase 0 there is a better answer than an offset: there is a real
  //: element at the exact place the finding is, so the question "which finding
  //: is under this point" is a rectangle test against boxes the browser itself
  //: laid out. No arithmetic, nothing to get wrong about wrapping, and it is the
  //: same element the menu is then anchored to.
  //:
  //: The engine's marks carry the finding's *index* in an attribute rather than
  //: a reference: a decoration's DOM is rebuilt whenever the view repaints, so
  //: anything hung on the element itself would be gone by the time it was
  //: needed. The index is resolved back here, once, against the list the
  //: decorations were drawn from.
  function docFindingMarks() {
    const marks = [];
    if (docCmView) {
      for (const el of docCmView.dom.querySelectorAll("[data-doc-finding]")) {
        const finding = docProseFound[Number(el.dataset.docFinding)];
        if (!finding) continue;
        el._docFinding = finding;
        marks.push(el);
      }
    }
    return marks;
  }

  //: **A mark is one element and can be several boxes, and this is the whole of
  //: INBOX 128.** A finding that crosses a soft wrap is drawn as two fragments of
  //: one inline element, and `getBoundingClientRect()` answers with the *union*
  //: of them, which is a box neither fragment occupies: measured on a doubled
  //: "the the" at a wrap point, fragments at `1187..1218` on one line and
  //: `471..497` on the next, union `471..1218`, 747px wide and two lines tall.
  //: Anchoring a menu to that opened it 716px to the left of the words that were
  //: clicked ("the popup didnt appear right next to it but off to the side with a
  //: wide gap"), and hit-testing against it claimed every unrelated word inside
  //: those 747px as well. `getClientRects()` is the per-fragment answer, so both
  //: the question "is the pointer on this finding" and the question "where do I
  //: put the menu" are asked of the box the reader can actually see.
  function docMarkRects(mark) {
    const rects = [...mark.getClientRects()].filter((rect) => rect.width || rect.height);
    return rects.length ? rects : [mark.getBoundingClientRect()];
  }

  function docRectHolds(rect, x, y) {
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }

  //: The fragment the pointer is in, or, for a route with no pointer (the
  //: keyboard, a panel row), the first one: a finding is read from its start, so
  //: its first line is where someone looking for it will be looking.
  function docMarkAnchor(mark, point) {
    const rects = docMarkRects(mark);
    if (point && rects.length > 1) {
      const hit = rects.find((rect) => docRectHolds(rect, point.x, point.y));
      if (hit) return hit;
    }
    return rects[0];
  }

  //: **Where a finding is on screen now, asked of the finding rather than of an
  //: element somebody held on to** (INBOX 421 c: "sometimes document editor
  //: dropdowns appear at the top of the screen ... sometimes it doesnt open at
  //: all"). The Live view redraws the line under the pointer the moment a press
  //: puts the caret on it (the line's markup is revealed), so the element a
  //: right-click or a long-press started on can be detached by the time the
  //: menu is placed, and a detached element measures `0,0,0,0`: the clamps then
  //: put the menu in the top left of the window, which is the screenshot. The
  //: live mark first; failing that the engine's own coordinates for the
  //: finding's span; failing that null, and the caller reveals the word or does
  //: not open, never opens at the origin.
  function docRectUsable(rect) {
    return Boolean(rect) && Number.isFinite(rect.top) && Number.isFinite(rect.left)
      && !(rect.top === 0 && rect.left === 0 && rect.bottom === 0 && (rect.right || 0) === 0);
  }

  function docFindingAnchor(finding, point) {
    if (!finding) return null;
    const mark = docFindingMarks().find((el) => el._docFinding === finding);
    if (mark && mark.isConnected) {
      const rect = docMarkAnchor(mark, point);
      if (docRectUsable(rect)) return rect;
    }
    if (docCmView && Number.isFinite(finding.start)) {
      const size = docCmView.state.doc.length;
      const from = docCmView.coordsAtPos(Math.max(0, Math.min(finding.start, size)), 1);
      const to = docCmView.coordsAtPos(Math.max(0, Math.min(finding.end ?? finding.start, size)), -1);
      if (from && docRectUsable(from)) {
        const sameLine = to && Math.abs(to.top - from.top) < 2;
        return {
          left: from.left,
          right: sameLine ? Math.max(to.right, from.left) : from.left,
          top: from.top,
          bottom: from.bottom,
        };
      }
    }
    return null;
  }

  //: The finding a mark element stands for, even after the engine has thrown
  //: the element away: `_docFinding` is only attached to marks that are in the
  //: document when `docFindingMarks` runs, but the index on the element is
  //: still the finding's index.
  function docFindingOfMark(el) {
    if (!el) return null;
    if (el._docFinding) return el._docFinding;
    const index = Number(el.dataset?.docFinding);
    return Number.isInteger(index) ? docProseFound[index] || null : null;
  }

  //: **Where the first press of a double-click landed, in the text.** The press
  //: puts the caret on the line and the Live view reveals its markup, so the
  //: words shift right under a still pointer (measured: 16px for a line with
  //: one `**bold**` span), and the second press lands on whatever slid under
  //: it, not on the word that was double-clicked. Read in the capture phase,
  //: before the engine handles the press and before anything moves.

  //: Whether a menu from `openMenuAtPoint` is showing. Its host is parked in
  //: the body and the menu may have been reparented there by
  //: `escapeMenuIfClipped`, so it is found by its opener's class.
  function docPointerMenuOpen() {
    for (const menu of document.querySelectorAll(".action-menu:not(.hidden)")) {
      if (menu.closest(".pointer-menu-host") || menu._escapedOpener?.classList.contains("pointer-menu-anchor")) {
        return true;
      }
    }
    return false;
  }

  function docFindingAtPoint(x, y) {
    if (typeof x !== "number" || typeof y !== "number") return null;
    for (const mark of docFindingMarks()) {
      if (!mark._docFinding) continue;
      if (docMarkRects(mark).some((rect) => docRectHolds(rect, x, y))) return mark._docFinding;
    }
    return null;
  }

  //: Anchored to the word, not to the caret, wherever the word is a real
  //: element. A menu that opens at the caret when the pointer is on the word is
  //: a menu you have to look away to find.
  //: **Put the word on screen before opening a menu about it** (DOCUMENTS_PLAN 12
  //: D4). A mark's box is where the text *is laid out*, which is not the same as
  //: where it can be seen: the editor clips its own overflow, so a finding one
  //: screen below the fold measures at `top 651` inside an editor whose visible
  //: box ends at `588`, and a menu anchored there is a menu pointing at nothing.
  //: Centred rather than scrolled minimally, for the same reason the panel centres
  //: (D3): a word brought just inside the bottom edge leaves the menu nowhere to
  //: open but over the panel that asked for it.
  //:
  //: Returns whether it moved, because CodeMirror applies a scroll effect in its
  //: own measure cycle: the mark's box is the old one until the next frame, and
  //: the caller has to re-measure rather than trust what it just read.
  function docRevealForSuggest(anchor, finding) {
    const host = docCmView ? docCmView.dom.getBoundingClientRect() : null;
    const CM = window.CM6;
    if (!host || !CM || !docCmView) return false;
    if (anchor.top >= host.top && anchor.bottom <= host.bottom) return false;
    docCmView.dispatch({
      effects: CM.view.EditorView.scrollIntoView(finding.start, { y: "center" }),
    });
    return true;
  }

  function docOpenSuggestFor(finding, focus = true, point = null, revealed = false) {
    //: **One surface** (INBOX 689): a menu opened at the pointer (a suggested
    //: change's, a link's) is the answer the press asked for, and the finding's
    //: popover opened over it is the overlap the owner reported. The change's
    //: menu carries the finding's answers itself (`docSuggestMenu`).
    if (docPointerMenuOpen()) return false;
    const anchor = docFindingAnchor(finding, point);
    if (anchor) {
      //: Once only: a finding the editor cannot bring into view (a folded
      //: construct, a zero-height line) would otherwise ask for a frame forever.
      if (!revealed && docRevealForSuggest(anchor, finding)) {
        requestAnimationFrame(() => docOpenSuggestFor(finding, focus, null, true));
        return true;
      }
      openDocSuggest(finding, anchor, focus);
      return true;
    }
    //: Not drawn at all: the finding is outside the lines the engine has laid
    //: out. Scrolled to, then asked again on the next frame, once. The caret
    //: used to be the fallback here, and the caret's own fallback, when the
    //: engine had no coordinates for it either, was the editor's top left
    //: corner: a menu about a word, opened at the top of the screen.
    if (!revealed && docCmView && window.CM6 && Number.isFinite(finding.start)) {
      docCmView.dispatch({
        effects: window.CM6.view.EditorView.scrollIntoView(finding.start, { y: "center" }),
      });
      requestAnimationFrame(() => docOpenSuggestFor(finding, focus, null, true));
      return true;
    }
    return false;
  }

  function docOpenSuggestAtCaret(box, point = null, focus = true, pressed = null) {
    let finding = point ? docFindingAtPoint(point.x, point.y) : null;
    //: The word the first press of a double-click was on, before the line
    //: shifted under the pointer (`docFirstPress`).
    if (!finding && pressed != null) finding = docFindingAtOffset(pressed);
    if (!finding) {
      //: The fallback, and it is the right one for a double-click: that gesture
      //: selects the word first, so the caret really is inside it.
      const offset = docOffsetOf(box);
      if (offset === null) return false;
      finding = docFindingAtOffset(offset);
    }
    if (!finding) return false;
    return docOpenSuggestFor(finding, focus, point);
  }



    //: **The underlined word is a real element, so right-clicking it must work.**
    //: The other half of the same report. `docToolsBoxFor` only ever matched a
    //: `<textarea>`, so in Live view, the one view that *can* draw a squiggle,
    //: and therefore the view where anyone would try this, right-clicking the
    //: mark fell straight through to the browser's own menu. The app's menu was
    //: reachable only by left-clicking, which is not what an underline means
    //: anywhere else.
  //: One body for the right-click and the long-press (UI Phase 11 item 9): a
  //: flag opens its suggestion at the point, and a right-click or a hold on
  //: the box itself opens the suggestion at the caret, only when there is
  //: something to say (swallowing the browser's own menu over ordinary text
  //: would take away spell-check, paste and everything else it carries for
  //: the sake of a menu with nothing in it). Returns whether it opened
  //: anything, so the mouse path keeps the browser's menu otherwise.
  function docOpenSuggestAtPoint(target, point) {
    const flag = target instanceof Element ? target.closest(".doc-flag, .cm-finding") : null;
    if (flag) docFindingMarks(); // resolves the engine's marks back to findings
    //: Resolved to the *finding* and placed from that, never from `flag`'s own
    //: box: the press that raised this event may already have made the engine
    //: redraw the line, and then `flag` is a detached element measuring
    //: `0,0,0,0`, which is the menu at the top of the window (INBOX 421 c).
    const flagged = docFindingOfMark(flag);
    if (flagged) return docOpenSuggestFor(flagged, true, point);
    const box = docToolsBoxFor(target);
    if (!box) return false;
    return Boolean(docOpenSuggestAtCaret(box, point));
  }

  //: **The editor's own menu, last of the three.** Not for Shift+right-click
  //: (the browser's menu: native spelling, Look up, Translate), not for a code
  //: file (its own handler), not for the plain-textarea fallback. A press outside
  //: the selection moves the caret there first, as a native menu would. A word
  //: the app flagged keeps its suggestion popover, which is asked first.
  function docEditorMenuAtPoint(event, point) {
    if (event.shiftKey || !(event.target instanceof Element)) return false;
    const surface = docToolsBoxFor(event.target);
    const view = surface && surface.view;
    if (!view || typeof docEditorMenuItems !== "function") return false;
    //: A code file keeps the browser's menu, except over a selection: there the menu carries the two note rows.
    const code = view.dom.classList.contains("doc-content-code");
    const sel = view.state.selection.main;
    if (code && sel.empty) return false;
    const at = view.posAtCoords(point);
    if (!code && at != null && (at < sel.from || at > sel.to)) view.dispatch({ selection: { anchor: at } });
    const items = code ? [...docClipboardMenuItems(view), ...docSelectionNoteItems(surface)] : docEditorMenuItems(view, point.x, point.y);
    openMenuAtPoint(items, "Document editor actions", point.x, point.y, view.contentDOM);
    return true;
  }


  //: **A right-click or a hold on a Live table cell opens the table's menu at
  //: the pointer** (INBOX 904 B23: "I'm not given a popup menu for tables when I
  //: right click them"). The same list as the ⋯ at the header's end
  //: (`docTableMenuItems`). The caret goes to the pressed cell first, unless the
  //: press is inside what is already selected (a column the person just
  //: selected keeps its ranges); a misspelt word in the cell keeps its own menu,
  //: which is the listener above. Anywhere else the browser's menu stays.
  function docTableMenuAtPoint(target, x, y) {
    if (target instanceof Element && target.closest(".doc-flag, .cm-finding")) return false;
    const grip = target instanceof Element ? target.closest(".doc-table-grip") : null;
    if (grip) return docTableGripMenu(grip, x, y);
    //: By the element under the pointer when the event's own target is not a
    //: cell: with a selection drawn, the press can land on the selection layer.
    let cell = target instanceof Element ? target.closest(".cm-md-td") : null;
    if (!cell && target instanceof Element && target.closest(".cm-editor")) {
      cell = document.elementsFromPoint(x, y).map((el) => el.closest(".cm-md-td")).find(Boolean) || null;
    }
    const surface = cell && asSurface(cell);
    const view = surface && surface.view;
    if (!view) return false;
    //: The pressed cell comes from the element, not from the pixel: the empty
    //: part of a short cell maps to the start of the next one (the hidden pipe
    //: is between them), which put the caret a column to the right. The press
    //: point is only used inside the cell's own span.
    const from = view.posAtDOM(cell);
    const to = from + cell.textContent.length;
    //: A column's ranges, or a row's, press through; one range across several
    //: rows (the whole table) does not, since a menu acting on its first cell
    //: would not be acting on the cell that was pressed.
    const { doc, selection } = view.state;
    const touched = selection.ranges.some(
      (range) =>
        range.from <= to && range.to >= from && range.to > range.from &&
        (selection.ranges.length > 1 || doc.lineAt(range.from).number === doc.lineAt(range.to).number)
    );
    if (!touched) {
      const at = view.posAtCoords({ x, y });
      view.dispatch({ selection: { anchor: at == null ? from : Math.max(from, Math.min(at, to)) } });
    }
    const context = docTableContext(surface);
    if (!context) return false;
    //: The browser's own menu is replaced by this one, so it carries the three
    //: rows people reach for first (review note on PR 191: no Copy or Paste).
    openMenuAtPoint([...docClipboardMenuItems(view), ...docTableMenuItems(context)], "Table row and column actions", x, y);
    return true;
  }

  //: Copy, Cut and Paste for the right-click menu over a Live table. Plain text
  //: only, which is all a cell holds. Paste reads the clipboard API, which a
  //: webview may refuse; then it says so rather than doing nothing.
  function docClipboardMenuItems(view) {
    const ranges = () => view.state.selection.ranges.filter((range) => !range.empty);
    const selected = () => ranges().map((range) => view.state.sliceDoc(range.from, range.to)).join("\n");
    const none = !ranges().length;
    return [
      {
        label: "Copy",
        group: "Clipboard",
        disabled: none,
        run: async () => {
          await copyToClipboard(selected());
          view.focus();
        },
      },
      {
        label: "Cut",
        group: "Clipboard",
        disabled: none,
        run: async () => {
          const text = selected();
          await copyToClipboard(text);
          view.dispatch(view.state.replaceSelection(""));
          view.focus();
        },
      },
      {
        label: "Paste",
        group: "Clipboard",
        run: async () => {
          let text = "";
          try {
            text = await navigator.clipboard.readText();
          } catch (error) {
            toast("Paste is blocked here. Press Ctrl+V in the cell.", "info");
            view.focus();
            return;
          }
          if (text) view.dispatch(view.state.replaceSelection(text.replace(/\r?\n/g, " ")));
          view.focus();
        },
      },
    ];
  }

  //: The same menu from an edge grip: the caret goes into the grip's own row or
  //: column first (the column's header cell, or the row's first cell), so the
  //: menu's "this row" and "this column" are the ones the grip stands for.
  function docTableGripMenu(grip, x, y) {
    const surface = asSurface(grip);
    const view = surface && surface.view;
    const context = view && docTableContext(surface);
    if (!context) return false;
    const kind = grip.dataset.kind;
    const index = Number(grip.dataset.index);
    const cell = kind === "row"
      ? { row: index, col: Math.min(context.cell.col, context.table.columns - 1) }
      : { row: context.cell.row === context.table.delim ? 0 : context.cell.row, col: index };
    const span = docTableCellSpan(context.table, cell.row, cell.col);
    if (span) view.dispatch({ selection: { anchor: span.from } });
    const next = docTableContext(surface);
    if (!next) return false;
    openMenuAtPoint(docTableMenuItems(next), "Table row and column actions", x, y);
    return true;
  }


  //: **Hover opens it too, in a code file** (the owner, 2026-10-11): a squiggle
  //: under a comment's or a string's word answers a pause of the pointer as it
  //: answers a click or a right-click, with the same popover. A pause, not a
  //: pass: moving across a line must not open a menu per word. Not focused, like
  //: the plain click, so typing carries on; prose keeps click and right-click.
  const DOC_HOVER_SUGGEST_MS = 450;
  const docHoverSuggest = { timer: 0, mark: null };



  //: **The keyboard half of "click the underline", and both gestures are
  //: borrowed rather than invented.** `Alt+Enter` on a flagged word opens its
  //: menu and `F8`/`Shift+F8` walk the findings, which is what VS Code has
  //: bound to exactly these two jobs; anyone who writes code already knows
  //: them, and anyone who does not loses nothing. Word's own F7 is taken by
  //: this app's shortcuts, and stepping through problems is the half people
  //: actually use.
  //:
  //: They work from the menu as well as from the text: after F8 the focus is on
  //: the first suggestion, and pressing F8 again there has to mean "the next
  //: one" rather than nothing at all.
  function docFindingKeyBox(target) {
    const box = docToolsBoxFor(target);
    if (box) return box;
    const menu = $("doc-suggest-menu");
    if (menu && !menu.classList.contains("hidden") && menu.contains(target)) {
      return docActiveBox() || docSurface();
    }
    return null;
  }

  //: The next finding after the caret, wrapping at the end. Wrapping rather than
  //: stopping, because a stepper that goes quiet at the last item reads as
  //: broken; the flash `docProseJump` draws is what says "back to the top".
  function docFindingStep(box, backwards) {
    if (!docProseFound.length) return null;
    const here = docSuggestOpenFor && docProseFound.includes(docSuggestOpenFor)
      ? docSuggestOpenFor
      : null;
    //: Measured from the open menu's finding when there is one, so a run of F8s
    //: advances instead of returning to the same word: opening a menu leaves
    //: the caret inside the finding, and "the next one after the caret" would
    //: then be this one again.
    const from = here ? (backwards ? here.start : here.end) : docOffsetOf(box) ?? 0;
    if (backwards) {
      const before = docProseFound.filter((finding) => finding.end < from);
      return before.length ? before[before.length - 1] : docProseFound[docProseFound.length - 1];
    }
    return docProseFound.find((finding) => finding.start > from) || docProseFound[0];
  }

  function docGoToFinding(finding) {
    if (!finding) return false;
    docProseJump(finding);
    //: One frame, because `docProseJump` may have switched the view, scrolled a
    //: textarea or re-rendered the Live blocks, and the menu is anchored to a
    //: rectangle that none of those had settled yet.
    requestAnimationFrame(() => docOpenSuggestFor(finding, true));
    return true;
  }






  // --- where the suggestions panel sits (INBOX 410) ---------------------------
  //
  // The owner, 2026-09-24: "allow the suggestions panel to be docked on the
  // right instead if the user wishes." Under the editor it takes height from a
  // document that is usually taller than it is wide; beside it, on a wide
  // window, it takes width the text column was not using. So both, the writer's
  // choice from the panel's own head, remembered per browser (a layout
  // preference about this screen, not about the notebook), and a column that
  // resizes by the sidebars' own handle (`makeSidebarResizable` in sheets-selects.js: a
  // `role="separator"` grip, drag, arrow keys, Home or a double click to reset).
  //
  // **Right means a column in `#doc-panes`**, beside the source and the preview,
  // so split view and the right dock share one row and the editor gives up
  // width rather than height. The panel element moves; nothing is rebuilt, so
  // an open row and its scroll position survive the move. At 720px and below
  // (where the sidebars' own handles stop, there being no room beside anything)
  // it is always under the editor, whatever was chosen.
  const DOC_PROSE_DOCK_KEY = "docProseDock";
  const DOC_PROSE_WIDTH_KEY = "docProseWidth";
  const DOC_PROSE_WIDTH_DEFAULT = 320;
  const DOC_PROSE_WIDTH_MIN = 240;
  const DOC_PROSE_NARROW = "(max-width: 720px)";

  function docProseDockChoice() {
    try {
      return prefs.get(DOC_PROSE_DOCK_KEY, null) === "right" ? "right" : "bottom";
    } catch {
      return "bottom";
    }
  }

  //: The side in effect: the choice, except where there is no room for it.
  function docProseDockSide() {
    return window.matchMedia(DOC_PROSE_NARROW).matches ? "bottom" : docProseDockChoice();
  }

  //: Clamped against the room there is: never under the floor, never more than
  //: half the editor's row, so the text column is always the larger of the two.
  function docProseApplyWidth(width) {
    const panel = $("doc-prose-panel");
    const panes = $("doc-panes");
    if (!panel || !panes) return DOC_PROSE_WIDTH_DEFAULT;
    const room = panes.getBoundingClientRect().width || window.innerWidth;
    const max = Math.max(DOC_PROSE_WIDTH_MIN, Math.round(room * 0.5));
    const clamped = Math.min(Math.max(Math.round(width), DOC_PROSE_WIDTH_MIN), max);
    //: On the tab page, not the panel: focus mode's side panel and the page's
    //: padding beside it read the same property (07-whiteboard-misc.css).
    ($("tab-documents") || panel).style.setProperty("--doc-prose-w", `${clamped}px`);
    try {
      prefs.set(DOC_PROSE_WIDTH_KEY, String(clamped));
    } catch {
      /* private mode: it just won't be remembered */
    }
    return clamped;
  }

  function docProseSavedWidth() {
    try {
      return Number(prefs.get(DOC_PROSE_WIDTH_KEY, null)) || DOC_PROSE_WIDTH_DEFAULT;
    } catch {
      return DOC_PROSE_WIDTH_DEFAULT;
    }
  }

  //: The grip, built once and moved with the panel: the sidebars' handle
  //: (`.sidebar-resize`, the same role, keys and double click), on the panel's
  //: leading edge because the panel grows away from the text, as the web panel's
  //: does in chat.
  let docProseGrip = null;

  function docProseResizeHandle() {
    let handle = docProseGrip;
    if (handle) return handle;
    handle = document.createElement("div");
    docProseGrip = handle;
    handle.className = "sidebar-resize doc-prose-resize";
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-orientation", "vertical");
    handle.setAttribute("tabindex", "0");
    handle.setAttribute("aria-label", "Resize the suggestions: arrow keys, or drag");
    handle.title = "Drag to resize, double-click to reset";
    const panel = () => $("doc-prose-panel");
    //: The value it says (WCAG 4.1.2): the panel's own width, at most half the
    //: editor, so the stated maximum is the window's half.
    if ($("doc-prose-panel")) trackSeparatorValue(handle, $("doc-prose-panel"), DOC_PROSE_WIDTH_MIN, Math.max(DOC_PROSE_WIDTH_MIN, Math.round(window.innerWidth / 2)));
    handle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = panel().getBoundingClientRect().width;
      //: Dragging left (a negative delta) widens it: the mirror of a sidebar.
      trackSeparatorValue.drag((e) => docProseApplyWidth(startWidth - (e.clientX - startX)));
    });
    handle.addEventListener("keydown", (event) => {
      const step = event.shiftKey ? 40 : 12;
      const current = panel().getBoundingClientRect().width;
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        docProseApplyWidth(current + step);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        docProseApplyWidth(current - step);
      } else if (event.key === "Home") {
        event.preventDefault();
        docProseApplyWidth(DOC_PROSE_WIDTH_DEFAULT);
      }
    });
    handle.addEventListener("dblclick", () => docProseApplyWidth(DOC_PROSE_WIDTH_DEFAULT));
    return handle;
  }

  //: Put the panel where the side in effect says, and say so on the head's
  //: toggle. Safe to call any number of times: a panel already in place is not
  //: moved again.
  function applyDocProseDock() {
    const panel = $("doc-prose-panel");
    const panes = $("doc-panes");
    const bar = $("doc-statusbar");
    if (!panel || !panes || !bar) return;
    const right = docProseDockSide() === "right";
    const handle = docProseResizeHandle();
    const focus = $("tab-documents")?.classList.contains("doc-focus") === true;
    if (right) {
      if (panel.parentElement !== panes) panes.append(handle, panel);
      docProseApplyWidth(docProseSavedWidth());
    } else {
      //: In focus mode the panel is a fixed side panel whatever side was chosen,
      //: so it has the grip and the remembered width too (INBOX 1408); the grip
      //: is fixed there, so it only has to sit before the panel.
      handle.remove();
      if (panel.previousElementSibling !== bar) bar.after(panel);
      if (focus) {
        panel.before(handle);
        docProseApplyWidth(docProseSavedWidth());
      }
    }
    panes.classList.toggle("doc-prose-right", right);
    panel.classList.toggle("doc-prose-right", right);
    //: The ⋯ names the side it would move to, so its head is drawn again (the
    //: head only: an open row and the scroll survive the move).
    panel.querySelector(".doc-prose-head")?.replaceWith(docProseHeader());
  }

  function toggleDocProseDock() {
    const next = docProseDockChoice() === "right" ? "bottom" : "right";
    try {
      prefs.set(DOC_PROSE_DOCK_KEY, next);
    } catch {
      /* private mode: it moves for this session only */
    }
    applyDocProseDock();
    //: Focus goes to the ⋯ the move was chosen from, which moved with the
    //: panel: the press that moved it should not lose the reader's place.
    $("doc-prose-panel")?.querySelector(".doc-prose-more button")?.focus();
  }

  //: The file's surface: what other files call (L-documents-117).
  Object.assign(window, { docTableTab, docFindingAtOffset, docOffsetOf, docRectUsable, docFindingAnchor, docPointerMenuOpen, docFindingAtPoint, docOpenSuggestFor, docOpenSuggestAtCaret, docClipboardMenuItems, docFindingKeyBox, docFindingStep, docGoToFinding, DOC_PROSE_NARROW, docProseDockSide, applyDocProseDock, toggleDocProseDock });

  //: These lets keep their bare names for the other files as window accessors, so one store answers every reader and writer (L-documents-118).
  for (const [name, get, set] of [
    ["docFirstPress", () => docFirstPress, (value) => { docFirstPress = value; }],
  ]) Object.defineProperty(window, name, { get, set, configurable: true });

  //: The table's menu goes first (`docTableMenuAtPoint`, below), and takes the
  //: press from the caret-level suggestion: the one this listener opens on any
  //: press in a box with something to say. A misspelt word keeps its own. One
  //: listener, because the long-press twin below is one call (a lint counts both).
  document.addEventListener("contextmenu", (event) => {
    const point = { x: event.clientX, y: event.clientY };
    if (
      docTableMenuAtPoint(event.target, point.x, point.y) ||
      docOpenSuggestAtPoint(event.target, point) ||
      docEditorMenuAtPoint(event, point)
    ) {
      event.preventDefault();
    }
  });

  //: The hold does not open the editor's own menu (`docEditorMenuAtPoint`): on a
  //: phone a hold in text is how a word gets selected, with the browser's handles.
  //: The menu answers the contextmenu event a device sends, and the phone bar and
  //: selection bar carry Turn into.
  if (typeof wireLongPress === "function") {
    wireLongPress(
      document,
      (event, point) =>
        docTableMenuAtPoint(event.target, point.x, point.y) ||
        docOpenSuggestAtPoint(event.target, point),
      { selector: ".doc-flag, .cm-finding, .cm-content, .doc-table-grip, textarea" }
    );
  }

  docListen("mouseover", (event) => {
    const mark = event.target instanceof Element ? event.target.closest(".cm-finding") : null;
    if (mark === docHoverSuggest.mark) return;
    clearTimeout(docHoverSuggest.timer);
    docHoverSuggest.mark = mark;
    if (!mark || docFileType().previewable || !docToolsBoxFor(mark)) return;
    const point = { x: event.clientX, y: event.clientY };
    docHoverSuggest.timer = setTimeout(() => {
      if (docHoverSuggest.mark !== mark || !mark.isConnected) return;
      const finding = docFindingOfMark(mark);
      if (!finding || docSuggestOpenFor === finding) return;
      docOpenSuggestFor(finding, false, point);
    }, DOC_HOVER_SUGGEST_MS);
  });

  $("doc-prose")?.addEventListener("click", () => {
    const panel = $("doc-prose-panel");
    const chip = $("doc-prose");
    if (!panel || !chip) return;
    const open = panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !open);
    chip.setAttribute("aria-expanded", String(open));
    if (open) renderDocProsePanel();
    docFocusSyncProse();
  });

  $("doc-focus-prose")?.addEventListener("click", () => {
    if (window.matchMedia(DOC_FOCUS_NARROW).matches && $("doc-prose-panel")?.classList.contains("hidden")) {
      setDocFocusSidebar(false);
    }
    $("doc-prose")?.click();
  });

  window.matchMedia(DOC_PROSE_NARROW).addEventListener("change", applyDocProseDock);

  applyDocProseDock();
})();
