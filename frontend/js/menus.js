// menus.js: action menus and their escape, help popovers, connections, history,
// the menu keyboard, the note's overflow menu. Moved out of app.js on
// 2026-09-26 as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

function inlineActionIs(id, kind) {
  return inlineAction && inlineAction.id === id && inlineAction.kind === kind;
}

// Close every open ⋯ menu (shared by outside-click and Esc, Wave L).
// A kebab menu that stays where it opened while the list scrolls under it
// ends up beside the wrong note (reported: "they stay sticky on the screen
// even when I scroll putting the note I clicked it for off the page"). Any
// scroll outside the open menu closes it; a scroll inside a long menu is
// the menu's own and is left alone.
//: Walked from a live collection rather than asked of the whole document:
//: this runs on every scroll event on every tab (it is a capturing listener),
//: nearly always with nothing open, and a `:not(.hidden)` selector over the
//: app's 10,700 elements was the second-largest script cost of a 30-step
//: wheel scroll (27ms on the Library). The collection holds only the menus.
const ACTION_MENUS = document.getElementsByClassName("action-menu");

function closeActionMenusOnScroll(event) {
  const openMenus = [];
  for (const menu of ACTION_MENUS) if (!menu.classList.contains("hidden")) openMenus.push(menu);
  if (openMenus.length === 0) return;
  //: **A scroll already on its way does not close a menu just opened.** A
  //: scroll's event is dispatched with the next frame, so a right-click
  //: while a scroll is settling (a trackpad's momentum, a smooth scroll)
  //: opened a menu that this closed a moment later: measured on the
  //: companion, 17 right-clicks in 20 made in the frame of a scroll showed
  //: no menu (round 5; the `companionmenu.js` flake). A scroll the reader
  //: makes after the menu is open still closes it.
  if (performance.now() - (window._menuOpenedAt || 0) < 200) return;

  // Trackpads send small deltaX values along with deltaY when scrolling vertically.
  // If a dropdown lacks horizontal scroll, browsers often chain the deltaX to the 
  // nearest horizontally scrollable ancestor. If that ancestor scrolls, this function
  // fires. By ignoring the scroll while the user is actively hovering the menu, we 
  // prevent the menu from abruptly closing during trackpad scrolling.
  // We also track the last wheel event time, as :hover is often lost during 
  // momentum scrolling on touchpads.
  const timeSinceLastMenuWheel = Date.now() - (window._lastMenuWheelTime || 0);
  if (
    timeSinceLastMenuWheel < 500 || 
    document.querySelector(".select-menu:hover, .action-menu:hover, .doc-dock-menu-list:hover, .library-image-menu-list:hover, .wb-board-menu:hover")
  ) {
    return;
  }

  if (event.target instanceof Node) {
    for (const open of openMenus) {
      if (open.contains(event.target)) return;
    }
  }
  closeActionMenus();
}
window.addEventListener("scroll", closeActionMenusOnScroll, true);

// Track recent wheel events over menus to prevent them from closing during 
// momentum scrolls where the :hover state might temporarily detach.
window.addEventListener("wheel", (event) => {
  if (event.target.closest(".select-menu, .action-menu, .doc-dock-menu-list, .library-image-menu-list, .wb-board-menu")) {
    window._lastMenuWheelTime = Date.now();
  }
}, { passive: true, capture: true });

function closeActionMenus() {
  for (const menu of document.querySelectorAll(".action-menu:not(.hidden)")) {
    //: Read before the menu hides: a hidden element cannot hold the focus,
    //: and the browser hands it to `body`, which is nowhere a keyboard user
    //: can continue from.
    const held = menu.contains(document.activeElement);
    menu.classList.add("hidden");
    restoreEscapedMenuAfterExit(menu);
    // `menu._escapedOpener` (set by wireEscapedActionMenu) wins when
    // present: a menu reparented to <body> has no useful `.parentElement`
    // to search: `document.body.querySelector` would find the *first*
    // `[aria-haspopup]` anywhere on the page, not this menu's own opener,
    // and set the wrong button's aria-expanded. Undefined for every other
    // menu, so this changes nothing for them.
    const opener = menu._escapedOpener || menu.parentElement.querySelector("[aria-haspopup]");
    if (opener) opener.setAttribute("aria-expanded", "false");
    if (held && opener?.isConnected) opener.focus({ preventScroll: true });
  }
  for (const strip of document.querySelectorAll(".menu-open")) {
    strip.classList.remove("menu-open");
  }
}

// Opening one, shared by the note cards and the sidebar kebabs so the two
// cannot drift apart.
//
// **`menu-open` is the fix for a reported bug, and it is not cosmetic.** On a
// note card, `.entry-actions` is `position: absolute; z-index: 1`, which
// makes it a *stacking context*, so the menu's own `z-index: 30` is resolved
// inside it and counts for nothing outside it. Every other note's action strip
// is also `z-index: 1`, and later in the document, so it paints on top of an
// open menu. Reported as "the other buttons in notes go over the popup options
// from above notes", and measured: with the first note's menu open, the topmost
// element at three separate points *inside* the menu was a button belonging to
// a different note. So it was not only a menu with buttons drawn over it, it
// was a menu whose items clicked the wrong note's controls.
//
// Raising the owning strip lifts the whole context, menu included. 5 rather
// than something larger because the only thing it has to beat is the 1 on its
// siblings; the page's own chrome is a different context and a big number here
// would only be a number waiting to collide with one.
// The nearest ancestor that actually clips overflow, walking up past plain
// flow containers. `.action-menu` is `position: absolute` inside a `.menu-wrap`
// that is itself absolutely positioned on the row, it never escapes an
// `overflow: auto` ancestor the way a portal would, so a row near the bottom
// of a scrolling list grows that ancestor's scrollHeight by however far the
// menu spills past it, and the menu itself is clipped at the same edge.
// Reported on the Documents subtab: the last row's ⋯ menu appeared cut off
// *and* a scrollbar showed up in a panel that fit without one a moment
// before opening it.
function nearestScrollParent(el) {
  let node = el.parentElement;
  while (node && node !== document.body) {
    if (/(auto|scroll)/.test(getComputedStyle(node).overflowY)) return node;
    node = node.parentElement;
  }
  return document.documentElement;
}

// **One help popover, for every "?" in the app.** Reported directly, with a
// screenshot of Settings' own Search-relevance hint: "the search relevance
// '?' popup tooltip is completely different from all other tooltips like it,
// same with the 'keep the ai on this machine' tooltip… all the ui and ux
// needs to be consistent in how it looks, how it functions, and where it is
// placed."
//
// It genuinely was three different things wearing the same "?" icon:
//   1. `.graph-help-panel`, a floating glass card (Graph, Timeline, three
//      Library sub-tabs).
//   2. the same class inside `.settings-section`, where a CSS override made
//      it `position: static`, so it was not a popover at all, it was a
//      bordered paragraph that shoved the rest of the form down the page.
//      That is the "just text in a box" in the screenshot.
//   3. `.setting-hint`, Settings' own long hints, which expanded inline
//      with no surface, border or shadow whatsoever.
//
// This makes all three the same control: a real popover, lifted to <body> so
// no card's `overflow` or `backdrop-filter` can clip it (the same escape
// `wireEscapedActionMenu` above makes, for the same reason), anchored under
// its own trigger with a caret pointing back at it, and closed the three
// ways every other popover here closes.
function placeHelpPopover(panel, trigger, retry = true) {
  const margin = 8;
  const anchor = trigger.getBoundingClientRect();
  //: **The other half of the flicker, which this function did not have.**
  //: Reported again after the dropdowns were fixed: "the flickering popup
  //: panels and dropdown panels are still happening", "still happen on some
  //: tooltips". `wireEscapedActionMenu`'s `place` already refuses an
  //: all-zero anchor rect (what a trigger inside a `display: none` or
  //: not-yet-laid-out ancestor reports, which collapses every sum below to
  //: the margin and puts the panel in the top corner); this one measured
  //: the same way and trusted it. Same guard, same shape: one retry on the
  //: next frame, held invisible rather than painted in the corner while it
  //: waits, and out of retries it places as best it can rather than
  //: flashing. A "?" whose trigger is genuinely at the origin also has zero
  //: width and height, so the three-way test cannot mistake a real corner
  //: trigger for an unmeasured one.
  if (!anchor.width && !anchor.height && !anchor.top) {
    if (retry) {
      panel.style.visibility = "hidden";
      requestAnimationFrame(() => placeHelpPopover(panel, trigger, false));
      return;
    }
  }
  // Measured while invisible: the panel is shown at 0,0 for the measure
  // and only then moved, which painted one frame in the top-left corner
  // (reported: "they flicker somewhere else on the screen for a split
  // second"). visibility keeps layout and geometry, so the measure is the
  // same, and nothing paints until the position is set.
  panel.style.visibility = "hidden";
  panel.style.left = "0px";
  panel.style.top = "0px";
  const box = panel.getBoundingClientRect();
  // Centred on the trigger, then pulled inside the window, a "?" sitting in
  // a right-hand control cluster would otherwise open half off-screen.
  //: **Clamped to the surface the trigger lives on, not to the window.**
  //: Reported with a screenshot of the search-relevance help hanging off the
  //: right edge of the Settings dialog and over the page behind it: a modal is
  //: narrower than the viewport, so "inside the window" let the popover leave
  //: the thing it belongs to while still being technically on screen. The
  //: window is the fallback for a "?" that is not inside a dialog at all.
  const surface = trigger.closest(".modal-card, .card") || null;
  const bounds = surface ? surface.getBoundingClientRect() : null;
  const minLeft = bounds ? Math.max(margin, bounds.left + margin) : margin;
  const maxLeft = bounds
    ? Math.min(window.innerWidth - margin - box.width, bounds.right - margin - box.width)
    : window.innerWidth - margin - box.width;
  let left = anchor.left + anchor.width / 2 - box.width / 2;
  left = Math.min(Math.max(left, minLeft), Math.max(minLeft, maxLeft));
  //: **The window is the hard bound, the surface is the preference** (INBOX
  //: 206, measured at 390x844: the capture popover sat at x=73 with a 358px
  //: body and ran 41px past the right edge of the screen). When the surface
  //: is narrower than the popover plus its margins, which is every card on a
  //: phone, `maxLeft` falls below `minLeft` and the clamp above resolves to
  //: `minLeft`, the card's own left edge, with nothing left to stop the
  //: right-hand side leaving the window. Clamping to the viewport last cannot
  //: make the surface fit worse: it only ever pulls the panel back towards
  //: the middle of the screen.
  left = Math.min(Math.max(left, margin), Math.max(margin, window.innerWidth - margin - box.width));
  //: **Never over its own '?'** (INBOX 718: "this popup covers the ? button").
  //: Below the trigger when the whole panel fits there, above when it fits
  //: there, else on the side with more room with its height capped to that
  //: room and scrolling inside (`menuSidePlan`, the menus' rule). The old last
  //: resort, pinning a too-tall panel to the window's bottom edge, slid it up
  //: over the trigger whenever the trigger sat in the lower half.
  const plan = menuSidePlan(box.height, anchor, 10, margin);
  const above = plan.up;
  let height = box.height;
  if (plan.cap !== null) {
    panel.style.maxHeight = `${plan.cap}px`;
    height = Math.min(box.height, plan.cap);
  }
  const top = above ? anchor.top - 10 - height : anchor.bottom + 10;
  panel.style.left = `${Math.round(left)}px`;
  panel.style.top = `${Math.round(top)}px`;
  panel.style.visibility = "";
  panel.classList.toggle("help-popover-above", above);
  // The caret is positioned against the panel, but it has to point at the
  // trigger: which is only the panel's own centre when nothing clamped it.
  const caretX = Math.min(Math.max(anchor.left + anchor.width / 2 - left, 14), Math.max(box.width - 14, 14));
  panel.style.setProperty("--help-caret-x", `${Math.round(caretX)}px`);
}

//: Every open popover this session, so a second one closes the first and
//: nothing is left stranded at <body> after a tab switch.
const openHelpPopovers = new Set();

function closeHelpPopovers() {
  for (const entry of [...openHelpPopovers]) entry.close();
}

//: **One set of page listeners for every popover, here, not four per
//: wiring.** They used to be added inside `wireHelpPopover`, so each of the
//: fifty-odd '?'s on the page put its own four on document and window, and a
//: '?' built after boot (the chat welcome's, rebuilt on every new chat) added
//: four more each time, each closure holding the welcome it was built for:
//: listenerrounds.js measured +27 listeners a rebuild, for the life of the
//: page. These read the open set instead, so wiring a popover costs the two
//: listeners on its own elements, collected with them.
document.addEventListener("click", (event) => {
  for (const entry of [...openHelpPopovers]) {
    if (entry.panel.contains(event.target) || entry.trigger.contains(event.target)) continue;
    entry.close();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  //: Marked so a handler further down this same press can tell it was spent
  //: closing a popover (the Graph's full-screen exit: one Escape closes the
  //: '?' and the map stays full screen, as the hand-wired Graph help did).
  if (openHelpPopovers.size) event.helpPopoverSpent = true;
  //: A "?" open inside a modal takes this Escape for itself: without the
  //: default, the press also asked the dialog to close, and the Quick note
  //: went with its help (INBOX 667). The next Escape closes the dialog.
  if ([...openHelpPopovers].some((entry) => entry.panel.closest("dialog[open]"))) event.preventDefault();
  closeHelpPopovers();
});
window.addEventListener("resize", () => {
  for (const entry of openHelpPopovers) placeHelpPopover(entry.panel, entry.trigger);
}, { passive: true });
// A popover is anchored to a rect that scrolls away underneath it; every
// other floating thing in this app closes rather than chasing it.
//
// But the popover's own body scrolls too (INBOX 430: a two-finger touchpad
// scroll doesn't scroll the popover): it is `overflow-y: auto`, and a
// `scroll` event fired on it still ran this capturing listener, closing
// every open popover, because capture reaches every ancestor on the way
// down to the target regardless of whether the event itself bubbles. With
// no guard, the first frame of a two-finger scroll on the popover's own
// text closed it instead of scrolling it, so the gesture looked dead rather
// than merely closing the thing it was scrolling. `event.target` is the
// element that actually scrolled; only close a popover for the page moving
// under its anchor, never for the popover scrolling itself.
window.addEventListener("scroll", (event) => {
  for (const entry of [...openHelpPopovers]) {
    if (entry.panel.contains(event.target)) continue;
    entry.close();
  }
}, true);

function wireHelpPopover(trigger, panel) {
  if (!trigger || !panel || panel.dataset.helpPopover) return;
  panel.dataset.helpPopover = "1";
  let homeParent = null;
  let homeNext = null;
  const entry = {
    panel,
    trigger,
    close() {
      if (!openHelpPopovers.has(entry)) return;
      openHelpPopovers.delete(entry);
      panel.classList.add("hidden");
      trigger.setAttribute("aria-expanded", "false");
      //: **After the exit, not now** (motion-1005: "Help popovers close at
      //: once"): moving the node home cancelled its fade, so the placement
      //: and the move wait for `.help-popover.hidden`'s transition, as an
      //: escaped menu does (`afterMenuExit`). Skipped when it opened again.
      afterMenuExit(panel, () => {
        if (openHelpPopovers.has(entry)) return;
        panel.classList.remove("help-popover", "help-popover-above");
        panel.style.left = "";
        panel.style.top = "";
        panel.style.maxHeight = "";
        //: Cleared with the rest of the inline placement: an element left
        //: `visibility: hidden` in its home tree is an element some other
        //: feature will one day show and find invisible.
        panel.style.visibility = "";
        if (homeParent && panel.parentElement !== homeParent) homeParent.insertBefore(panel, homeNext);
      });
    },
  };
  const open = () => {
    closeHelpPopovers();
    //: Still leaving from the last close: its home is the one already known.
    clearTimeout(panel._exitTimer);
    //: The '?' stops its click (below), so the page's outside-click close
    //: never reaches an open menu: they stacked (INBOX 796, app-wide as
    //: ledger 936). Opening one shuts the others.
    if (!trigger.closest(".action-menu")) closeActionMenus();
    const home = trigger.closest(".doc-dock-menu-list")?._escapedHome?.parent;
    for (const menu of document.querySelectorAll("details.dock-menu[open]")) if (menu !== home && !menu.contains(trigger)) menu.open = false;
    if (!panel.classList.contains("help-popover")) {
      homeParent = panel.parentElement;
      homeNext = panel.nextSibling;
    }
    //: **Into the open modal, not `<body>`, when the "?" is inside one**
    //: (INBOX 667: the Quick note's "?" showed nothing). A `showModal()`
    //: dialog is in the top layer, above the whole document whatever the
    //: z-index, and makes everything outside it inert, so a panel moved to
    //: `<body>` opened underneath it and could not be reached. The same
    //: escape `wireEscapedActionMenu` uses for its menus.
    (trigger.closest("dialog[open]") || document.body).appendChild(panel);
    //: **Hidden before it is shown, revealed only by the placement**
    //: (INBOX 206: "popups still flicker for a split second at the top left
    //: and then appear in the right place"). Removing `hidden` first and
    //: placing afterwards is safe only while nothing between the two can
    //: yield to the compositor, which is true of this function today and is
    //: not a property anyone editing it can see. Setting `visibility` here
    //: makes the invariant local: the panel is laid out, so it can be
    //: measured, and the only line that can make it visible is the one in
    //: `placeHelpPopover` that runs after `left`/`top` are written.
    panel.style.visibility = "hidden";
    panel.classList.remove("hidden");
    // `.setting-hint`'s own collapsed state is a max-height animation, not a
    // `hidden` class: an inline hint has to be un-collapsed as well, or the
    // popover opens at zero height.
    panel.classList.remove("is-collapsed");
    panel.classList.add("help-popover");
    trigger.setAttribute("aria-expanded", "true");
    openHelpPopovers.add(entry);
    placeHelpPopover(panel, trigger);
  };
  trigger.addEventListener("click", (event) => {
    // These triggers live inside <label>s often enough that a bare click
    // would toggle the setting they explain.
    event.preventDefault();
    event.stopPropagation();
    if (openHelpPopovers.has(entry)) entry.close();
    else open();
  });
  panel.addEventListener("click", (event) => event.stopPropagation());
}
window.wireHelpPopover = wireHelpPopover;

//: **The accessible card: the title opens it, not the card** (INBOX 433,
//: WCAG 4.1.2). A Library card was an `<article role="button">` holding its
//: own tick and its own ⋯, and axe-core counted 35 controls nested inside
//: controls: a screen reader announced one button and could not reach the
//: two inside it as themselves. Now the card is only a box, and its title is
//: the one control that opens it: a button by role, a Tab stop, Enter or
//: Space to open. Its click area is stretched over the whole card by
//: `.card-open::after` (08-consistency.css), so a press anywhere on the card
//: still lands on the title and opens it, and the tick, the ⋯ and a link in
//: the preview sit above that overlay as controls of their own. The host
//: keeps its own click listener, which the overlay's press bubbles to, so
//: nothing about the mouse changed.
//:
//: `name` is what the button is called aloud when the title alone would not
//: say enough (the Library card says its kind and its category too).
function cardOpener(title, open, name) {
  //: A title is a name. A link its markdown drew would be a control inside
  //: this one again, so it is kept as words.
  for (const link of title.querySelectorAll("a[href], [tabindex]")) link.replaceWith(...link.childNodes);
  title.classList.add("card-open");
  title.setAttribute("role", "button");
  title.tabIndex = 0;
  if (name) title.setAttribute("aria-label", name);
  title.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    open();
  });
  return title;
}
window.cardOpener = cardOpener;

//: **One vertical rule for every menu that hangs from its opener** (INBOX 712:
//: the document editor's ⋯ "goes off the bottom of the screen"): below the
//: opener when the whole menu fits there, else above it when it fits there,
//: else on whichever side has more room, its height capped to that room with
//: the list scrolling inside it (the 120px floor keeps a menu a menu, not a
//: slit). Pure, so the callers (the document dock's ⋯, the generic
//: `openActionMenu`, and a menu re-placed after its window or its rows
//: changed) cannot decide differently. `anchor` is the opener's rect.
function menuSidePlan(height, anchor, gap = 4, margin = 8) {
  //: The window's usable foot is the status bar's top, not the window's edge
  //: (the owner, 2026-10-06: the document ⋯ "still overflows off the page",
  //: its last rows under the fixed status bar).
  const bar = document.getElementById("status-bar")?.getBoundingClientRect();
  const foot = bar && bar.height && bar.top < window.innerHeight ? bar.top : window.innerHeight;
  const below = Math.floor(foot - anchor.bottom - gap - margin);
  const above = Math.floor(anchor.top - gap - margin);
  const need = Math.ceil(height);
  if (need <= below) return { up: false, cap: null };
  if (need <= above) return { up: true, cap: null };
  const up = above > below;
  return { up, cap: Math.max(120, up ? above : below) };
}

//: The last step of `openActionMenu` for a menu that stayed where its
//: stylesheet put it (an escaped menu is placed by `placeEscapedMenu`, which
//: already keeps the whole box in the window). The earlier flip only asks
//: whether the menu spills past its nearest scrolling ancestor, and that can
//: be a box taller than the window, so a menu near the bottom of a tall page
//: still ran off the screen. A menu already inside the window is left as the
//: flip chose; one that spills is re-decided by `menuSidePlan`.
function fitActionMenuInWindow(menu, opener) {
  const margin = 8;
  const anchor = opener.getBoundingClientRect();
  //: Not laid out (an opener in a hidden pane): nothing to measure against.
  if (!anchor.width && !anchor.height) return;
  let box = menu.getBoundingClientRect();
  if (box.top >= margin - 1 && box.bottom <= window.innerHeight - margin + 1) return;
  menu.classList.remove("action-menu-flip");
  menu.style.maxHeight = "none";
  box = menu.getBoundingClientRect();
  const plan = menuSidePlan(box.height, anchor);
  menu.classList.toggle("action-menu-flip", plan.up);
  if (plan.cap !== null) {
    menu.style.maxHeight = `${plan.cap}px`;
    menu._fitCap = true;
  } else {
    menu.style.maxHeight = "";
  }
}

function openActionMenu(menu, opener) {
  closeActionMenus(); // only one open at a time
  window._menuOpenedAt = performance.now();
  //: **Measured while invisible, revealed once.** Reported alongside the
  //: collapsed menu above: "the popup sitll has the left corner screen flicker
  //: before it shows in the right place". Everything below this line needs the
  //: menu laid out to do its job (the flip test reads its rect, and
  //: `escapeMenuIfClipped` reparents it to `<body>` and writes a `top` only
  //: after measuring), and `hidden` is `display: none`, so the menu has to be
  //: shown before any of it can run. That leaves at least one painted frame
  //: where a menu about to be moved is visible where it started, which for an
  //: escaped menu is wherever `<body>` puts an unpositioned child.
  //:
  //: `visibility: hidden` is the difference: the box is laid out and
  //: measurable, and it paints nothing until the last line puts it back. The
  //: same two-step `showSelectionPopupAt` uses, and for the same reason.
  const wasVisibility = menu.style.visibility;
  menu.style.visibility = "hidden";
  //: A cap `fitActionMenuInWindow` wrote on the last open is this open's
  //: measurement error, so it goes before anything is measured.
  if (menu._fitCap) {
    menu.style.maxHeight = "";
    menu._fitCap = false;
  }
  menu.classList.remove("hidden", "action-menu-flip");
  opener.setAttribute("aria-expanded", "true");
  // Whichever ancestor is the stacking context this menu is trapped in. On a
  // note card that is `.entry-actions` (positioned, z-index 1); on a Library
  // card it is the card itself, because `backdrop-filter` creates a stacking
  // context too: which is why the same "menu behind the next card" bug turned
  // up again on a surface with no z-index in sight.
  menu.closest(".entry-actions, .library-card")?.classList.add("menu-open");
  // Opens downward by default; flip upward only when that would spill past
  // the nearest clipping ancestor, so a menu near the top of a short list
  // still opens the normal way.
  const bound = nearestScrollParent(opener).getBoundingClientRect();
  if (menu.getBoundingClientRect().bottom > bound.bottom) {
    menu.classList.add("action-menu-flip");
  }
  //: **A select's list starts under its own box** (the owner, with a
  //: screenshot: the Corner companion list opened out to the left of its
  //: select, over the section nav). Menus hang from their opener's right
  //: edge, which suits a ⋯ at the end of a row; a select's list is read
  //: down from the value it replaces, so it takes the opener's left edge
  //: whenever it fits that way, and keeps the right edge only when it
  //: would otherwise run past its container.
  menu.classList.remove("action-menu-start");
  if (opener.closest(".select-shell")) {
    const openerBox = opener.getBoundingClientRect();
    const width = menu.getBoundingClientRect().width;
    if (openerBox.left + width <= Math.min(bound.right, window.innerWidth) - 4) {
      menu.classList.add("action-menu-start");
    }
  }
  //: **And if flipping is not enough, leave the box entirely.** Asked for
  //: app-wide: "make sure the popup menus dont get clipped or go off the
  //: screen." Measured on the live app: **21** absolutely-positioned menus sit
  //: inside an ancestor with `overflow` set: every enhanced `<select>` inside
  //: a scrolling panel, the document dock's own list, the whiteboard's menus.
  //: Flipping upward only helps when the spill is downward and the clipper is
  //: tall enough; sideways, or in a short panel, the menu is simply cut.
  //:
  //: `wireEscapedActionMenu` has solved this since the Library's kebab was
  //: reported: but only for the callers that remembered to ask for it, one at
  //: a time. This makes it the default *when it is needed*: nothing changes for
  //: a menu that fits, and a menu that does not gets the same reparent-to-body
  //: treatment rather than being clipped.
  escapeMenuIfClipped(menu, opener);
  if (!menu._escapedHome && !menu._escapeWired && !menu.classList.contains("submenu")) {
    fitActionMenuInWindow(menu, opener);
  }
  //: Placed, so it can be seen. Restored rather than cleared, in case a caller
  //: had its own reason to hide this menu.
  menu.style.visibility = wasVisibility;
  focusMenuItem(menu.querySelector("button"), menu);
}

//: **Focusing the first row of a menu must never scroll the page behind it.**
//:
//: Measured, not reasoned. The reader picker at the top of the OCR workspace
//: (`#ocr-reader`) would not open at all: one real Chromium click produced,
//: in order, `openActionMenu` (the menu unhides and escapes to <body>), a
//: `focusin` on the chosen row, a `scroll` event on `.ocr-toolbar`, and then
//: `closeActionMenusOnScroll` shutting the menu it had just opened, 3 option
//: rows built and 0 visible. `.ocr-toolbar` is `overflow-x: auto` (it scrolls
//: sideways rather than wrapping, by design), the menu is still a child of
//: that toolbar at the moment the focus lands, and a plain `.focus()` asks
//: the browser to scroll every ancestor until the focused element is in view.
//: So the open *caused* the scroll, and the scroll-away rule, which exists
//: for a real one (a kebab left beside the wrong note while its list scrolls
//: under it), could not tell the two apart.
//:
//: The fix is at the cause rather than at that rule: this app positions its
//: own menus, from the opener's rect, escaping to <body> when they would be
//: clipped, so an ancestor scrolling to "reveal" a menu item is never what is
//: wanted and is the browser undoing the placement. `preventScroll` says
//: exactly that, with no timer for anyone to tune.
//:
//: What it must not lose is the scrolling that *is* wanted: a long menu (the
//: model picker, a 30-option select) whose chosen row is below its own fold
//: has to bring that row into view. So the menu scrolls itself, by the two
//: lines below, and nothing above it moves.
function focusMenuItem(item, menu) {
  if (!item) return;
  item.focus({ preventScroll: true });
  const box = menu || item.closest(".action-menu");
  if (!box || box.scrollHeight <= box.clientHeight) return;
  const top = item.offsetTop;
  const bottom = top + item.offsetHeight;
  if (top < box.scrollTop) box.scrollTop = top;
  else if (bottom > box.scrollTop + box.clientHeight) box.scrollTop = bottom - box.clientHeight;
}

//: The nearest ancestor that would clip this menu, `overflow` anything but
//: `visible` makes a box a clipping context, and `clip` and `hidden` clip
//: without even offering a scrollbar to reach what they cut off.
function menuClippingAncestor(el) {
  let node = el?.parentElement;
  while (node && node !== document.body) {
    const cs = getComputedStyle(node);
    const clips = (value) => value === "auto" || value === "scroll" || value === "hidden" || value === "clip";
    if (clips(cs.overflowX) || clips(cs.overflowY)) return node;
    node = node.parentElement;
  }
  return null;
}

//: The placement `wireEscapedActionMenu` has always used, factored out so the
//: automatic path and the hand-wired one cannot drift into placing the same
//: menu differently. Right-aligned to the opener, flipped above when the whole
//: box fits there, and clamped to the viewport on both axes, which is the
//: "or go off the screen" half of the same report.
//:
//: **This is deliberately not `place()`'s vertical rule** (see
//: `wireEscapedActionMenu` below), and the difference was measured rather
//: than assumed, on the note cards' own kebab menus, which are the automatic
//: path's largest population. `place()` decides between the room above the
//: trigger and the room below it and scrolls inside whichever is larger; this
//: one is allowed to span *across* the trigger and use the whole window. For
//: a menu taller than either side, that is the difference between showing all
//: of it and showing part of it: at 1280x640 a 375px menu opened from a card
//: at y=313 sits 257 to 632 here and needs no scrollbar at all, while
//: `place()`'s rule caps it to the 301px above the card and makes it scroll;
//: at 1280x360 the same menu shows 294px of itself against `place()`'s 207px,
//: with 143px of empty window left under it. A kebab covering its own three
//: dots for as long as it is open costs nothing. A `<select>` dropdown
//: covering the field you are choosing a value in is a different matter,
//: which is why `place()`, whose callers are that shell and the wrap kebabs,
//: keeps the trigger clear and takes the scrollbar instead.
//:
//: What is shared is everything else: the horizontal clamp, the 8px margin,
//: the 4px gap, and the rule that the whole box lands inside the window.
//: Neither can run past the bottom, because `07-whiteboard-misc.css` caps
//: every `.action-menu` at `calc(100vh - var(--space-9) * 2)` with
//: `overflow-y: auto`, measured as 576px in a 640px window and 296px in a
//: 360px one, so a menu is never taller than the window it is placed in.
function placeEscapedMenu(menu, opener) {
  const margin = 8;
  const anchor = opener.getBoundingClientRect();
  // Same reason as placeHelpPopover: no frame at 0,0 before the move.
  menu.style.visibility = "hidden";
  menu.style.left = "0px";
  menu.style.top = "0px";
  const box = menu.getBoundingClientRect();
  let left = anchor.right - box.width;
  let top = anchor.bottom + 4;
  if (left < margin) left = margin;
  if (left + box.width > window.innerWidth - margin) {
    left = Math.max(margin, window.innerWidth - margin - box.width);
  }
  if (top + box.height > window.innerHeight - margin) {
    const above = anchor.top - 4 - box.height;
    //: **Both edges, not just the top.** This branch used to accept `above`
    //: on `above >= margin` alone, which is only half the question: with a
    //: trigger below the fold (a card the list has scrolled past, a menu
    //: opened from script), "above the trigger" is itself off the bottom of
    //: the window. Measured at 1280x360 on the third note card, whose kebab
    //: sits at y=405: the menu landed at top 105, bottom 401, with 41px of it
    //: past the window and nothing able to bring that back. The fallback
    //: below, which pins the box to the last position that fits, was always
    //: the right answer for that case.
    const fits = above >= margin && above + box.height <= window.innerHeight - margin;
    top = fits ? above : Math.max(margin, window.innerHeight - margin - box.height);
  }
  menu.style.left = `${Math.round(left)}px`;
  menu.style.top = `${Math.round(top)}px`;
  menu.style.visibility = "";
}

function escapeMenuIfClipped(menu, opener) {
  //: A menu that already has its own escape wiring is left alone: two
  //: mechanisms reparenting the same node would fight over where home is.
  if (menu._escapeWired || menu._escapedHome) return;
  const clipper = menuClippingAncestor(menu);
  if (!clipper) return;
  const box = menu.getBoundingClientRect();
  const bound = clipper.getBoundingClientRect();
  //: A pixel of tolerance, because a menu whose edge lands exactly on its
  //: container's is not clipped and reparenting it would be a visible jump for
  //: no reason.
  const spills =
    box.right > bound.right + 1 ||
    box.left < bound.left - 1 ||
    box.bottom > bound.bottom + 1 ||
    box.top < bound.top - 1;
  if (!spills) return;
  escapeMenuToBody(menu, opener);
}

//: The reparent itself, for a caller that decides to escape for a reason of
//: its own (the topic strip's doors, which must not sit on their own topic).
function escapeMenuToBody(menu, opener) {
  if (menu._escapedHome) return;
  menu._escapedHome = { parent: menu.parentElement, next: menu.nextSibling };
  //: Read by `closeActionMenus`, which otherwise looks for the opener among
  //: the menu's siblings: and once the menu is a child of <body> that search
  //: finds the first `[aria-haspopup]` on the page, which is the wrong button.
  menu._escapedOpener = opener;
  document.body.appendChild(menu);
  menu.classList.add("action-menu-escaped");
  //: `action-menu-flip` pins `bottom`; `placeEscapedMenu` sets `top`. Both at
  //: once over-constrains an auto-height box, which reproduced as the menu
  //: collapsing to its own padding, see `wireEscapedActionMenu`'s note.
  menu.classList.remove("action-menu-flip");
  placeEscapedMenu(menu, opener);
}

//: **A menu reparented to the body leaves after its exit, not before it**
//: (perfpolish). `.action-menu.hidden` fades out over --motion-fast
//: (10-responsive.css), but moving a node in the DOM cancels a transition, so
//: an escaped menu (every kebab on a phone, and any menu a scroller clips)
//: went home at once and vanished with no exit. It now goes home when the exit
//: is over. A menu opened again inside that window is not hidden any more and
//: is left where it is (an open escaped menu lives in the body anyway; the
//: next close puts it back). No exit runs under reduced motion, where the
//: transition is 0s, and then it goes home at once as it always did.
function restoreEscapedMenuAfterExit(menu) {
  if (menu._escapedHome) afterMenuExit(menu, () => menu.classList.contains("hidden") && restoreEscapedMenu(menu));
}

//: After the menu's exit fade (`menuExitMs`), or now when it has none.
function afterMenuExit(menu, fn) {
  const exit = menuExitMs(menu);
  clearTimeout(menu._exitTimer);
  if (exit) menu._exitTimer = setTimeout(fn, exit);
  else fn();
}

function menuExitMs(menu) {
  const style = getComputedStyle(menu);
  if (!style.transitionProperty.split(",").some((name) => name.trim() === "display")) return 0;
  const seconds = Math.max(0, ...style.transitionDuration.split(",").map(parseFloat).filter(Number.isFinite));
  return seconds ? Math.round(seconds * 1000) + 40 : 0;
}

function restoreEscapedMenu(menu) {
  const home = menu._escapedHome;
  if (!home) return;
  //: Put back rather than left in <body>: a page that never restores an
  //: escaped menu accumulates stray fixed nodes forever, and the next
  //: `openActionMenu` expects to find it where it was built.
  home.parent.insertBefore(menu, home.next);
  menu.classList.remove("action-menu-escaped");
  menu.style.left = "";
  menu.style.top = "";
  menu._escapedHome = null;
}

//: **Escape a clipping ancestor, then cap to the room really left below.**
//: The second of this file's two menu recipes, and the one for a menu whose
//: ordinary position comes from the stylesheet rather than from us:
//: `details.dock-menu`'s panel (INBOX 31) and the whiteboard's five top-bar
//: menus (INBOX 43). It was written twice, once in each place, with the same
//: margin, the same floor and the same order; the second copy's own comment
//: said it was "the same recipe ... not a third scheme", which is exactly the
//: state in which a reader improves one of them and leaves the other behind.
//: Measured identical before and after on the whiteboard's own menus at
//: 1440x900, 1280x640 and 1024x560 (View: escaped at the two smaller sizes,
//: capped to 576px and 496px, 20px and 100px of scroll inside it).
//:
//: **Not** folded into `wireEscapedActionMenu`'s `place()`, this file's other
//: recipe, and the difference is not a detail: `place()` *positions* the menu
//: itself, fixed and right-aligned under its opener, every time it opens,
//: because the `.action-menu` it is wired to has no position of its own once
//: it is a child of <body>. These menus do have one. A dock menu that nothing
//: clips is still anchored by CSS under its own summary, and a whiteboard menu
//: under its own toolbar button, so running them through `place()` would move
//: menus that were never in the wrong place to satisfy a shared function. Here
//: the escape stays conditional (a no-op when nothing clips) and only the
//: height is decided.
function escapeAndCapMenu(menu, opener) {
  //: **Measured with every cap off, not just this function's own.**
  //: The inline cap is cleared before the measurement rather than after the
  //: close: the `top` read below has to be this open's real one, and a cap
  //: left over from the last open changes it (a menu that would have flipped
  //: above no longer needs to) as well as hiding the fact that the menu wants
  //: more room.
  //:
  //: `none` rather than empty, because clearing the inline value only hands
  //: the menu back to the *stylesheet's* cap, and that is the same lie one
  //: level down. Measured on the map's View menu at 1440x760 (INBOX 114, "the
  //: view dropdown menu in the whiteboard and mindmap is still broken", with
  //: "Snap to grid" cut in half and a scrollbar): 714px of content, held to
  //: 616 by `.wb-board-menu`'s own `calc(100vh - 9rem)`, so `placeEscapedMenu`
  //: measured 616, found that it fitted under the opener, and left the menu at
  //: top 56. It was then capped to the 696px of room under *that* line and
  //: scrolled 18px of content it had the window height to show: placed at the
  //: top of the window instead, all 714 fit. A menu is moved up by how tall it
  //: really is, or it is moved for the wrong reason.
  menu.style.maxHeight = "none";
  escapeMenuIfClipped(menu, opener);
  const margin = 8;
  //: After the escape, so the number is measured against wherever the menu
  //: has ended up: `placeEscapedMenu` may have flipped it above the opener or
  //: clamped it to the top of the window, and a cap computed from the old top
  //: would be the wrong one for the new position.
  const box = menu.getBoundingClientRect();
  //: **The cap is the room under where the menu was actually put.** A rect read
  //: inside a hidden ancestor is all zeroes (measured on a hidden board: a
  //: 892px cap from `top: 0`), so the opener's bottom, which is laid out, is the
  //: fallback, and with neither laid out the stylesheet's cap stands. And
  //: `placeEscapedMenu` may pin the menu higher than the opener (it only writes
  //: `top`), so its own top beats the opener's bottom (INBOX 107c: a View menu
  //: at top 96 capped to 507 with 604px of room).
  const anchor = opener ? opener.getBoundingClientRect() : null;
  const laidOut = (rect) => rect && (rect.width || rect.height || rect.top);
  const top = laidOut(box) ? box.top : laidOut(anchor) ? anchor.bottom + margin : null;
  //: Nothing measurable to cap against: the stylesheet's own cap is the right
  //: thing to fall back to, and `none` above must not be what is left behind.
  if (top === null) {
    menu.style.maxHeight = "";
    return;
  }
  //: The floor keeps a menu opened near the bottom edge a menu rather than a
  //: slit; under it, scrolling inside the panel is the affordance.
  menu.style.maxHeight = `${Math.max(120, Math.round(window.innerHeight - top - margin))}px`;
}

// **Escapes a `kebabMenu()` dropdown from a clipping scroll ancestor.**
// Reported live, with a screenshot: "the documents popup menu in the
// library subtab gets cut off." `.library-view-section` is
// `overflow-y: auto`, and `.action-menu` is `position: absolute`, the
// same shape as the gallery kebab menu's own clipping bug earlier this
// session (`section.card.glass`'s `backdrop-filter`, there), fixed the
// same way: reparent to `<body>` and position from the opener's own rect,
// which is the only thing that actually escapes an ancestor's `overflow`.
//
// Deliberately **not** folded into `openActionMenu`/`closeActionMenus`
// themselves: `.action-menu` is shared by every note card, the chat
// dock, the selection popup and nested submenus, none of which are
// clipped, and none of which this session re-verified live. Rewriting
// what they all depend on to fix one clipped caller is a bigger, riskier
// change than watching that one caller's own open/close state and acting
// on it: which is what this does, via a MutationObserver on the menu's
// own `hidden` class, so `openActionMenu`'s existing flip logic keeps
// running unmodified underneath it.
//
// Call once, right after building a `kebabMenu()` wrap, for any menu
// known to live inside a scrolling ancestor.
function wireEscapedActionMenu(wrap) {
  const menu = wrap.querySelector(".action-menu");
  const opener = wrap.querySelector("[aria-haspopup]");
  if (!menu || !opener) return;
  // Read by closeActionMenus() in place of a DOM-parent lookup, which
  // would otherwise search the whole <body> for the first [aria-haspopup]
  // it finds, the wrong button, once this menu is no longer a
  // descendant of its own opener's wrapper.
  menu._escapedOpener = opener;
  //: Claimed, so `escapeMenuIfClipped` (the automatic path) does not also try
  //: to reparent this one, two mechanisms with two ideas of "home" would put
  //: it back in the wrong place.
  menu._escapeWired = true;
  let homeParent = null;
  let homeNext = null;
  const place = (retry = true) => {
    const margin = 8;
    const anchor = opener.getBoundingClientRect();
    //: **Never place against a rect that was not laid out.** Reported:
    //: dropdowns and tooltips "flicker into the top corner for a second
    //: then appear in the right place". Reproduced by measuring an open
    //: menu frame by frame: with the opener unmeasurable (all-zero rect,
    //: which is what an element inside a `display: none` or
    //: not-yet-laid-out ancestor reports) the arithmetic below resolves to
    //: the margin in both axes and the menu lands at 8,4: the top corner,
    //: exactly as described. A later pass then places it properly, which
    //: is the "and then it appears in the right place" half.
    //:
    //: So: one retry on the next frame, the same shape `clampToolbarMenu`
    //: already uses, and the menu is held invisible rather than painted in
    //: the corner while it waits. `visibility`, not `.hidden`: the class is
    //: the open/closed state that this observer is driven by, and writing
    //: it here would re-enter.
    if (!anchor.width && !anchor.height && !anchor.top) {
      if (retry) {
        menu.style.visibility = "hidden";
        requestAnimationFrame(() => place(false));
        return;
      }
      //: Out of retries: show it where the stylesheet puts it rather than
      //: never, and rather than in a corner of our own choosing.
      menu.style.visibility = "";
      return;
    }
    // Reset first: a stale left/top from the last open would otherwise
    // seed the width/height measurement below at the wrong size on some
    // browsers' layout of a `position: fixed` element mid-transition.
    menu.style.left = "0px";
    menu.style.top = "0px";
    //: **Measure the menu at its full height, not at whatever a stylesheet
    //: last capped it to.** Written in response to the whiteboard's View
    //: menu (INBOX 57, then 105), but the correction belongs here in the
    //: retest, not in the fix: this `place()` is `wireEscapedActionMenu`'s
    //: own, wired only to `enhanceSelect`'s dropdown shell and `kebabMenu`'s
    //: wrap (this file's own two call sites) -- the whiteboard's
    //: `.wb-board-menu` (Insert, Edit, Arrange, View, Board) never calls it.
    //: It goes through the file's other recipe, `escapeAndCapMenu` above,
    //: which leaves a menu the stylesheet has already anchored where it is
    //: and caps `max-height` to the room below its own final `top`. Read that
    //: function's comment before moving anything between the two: they differ
    //: because one owns the menu's position and the other does not.
    //: (INBOX 105 has the retest numbers for the View menu.)
    //: Whichever rule caps it, an inline `max-height: none` for the
    //: duration of the measurement is what makes `box.height` the height this
    //: menu actually wants, so the choice below is made on the real number.
    //:
    //: **And the cap below is not `placeEscapedMenu`'s job, deliberately.**
    //: Sharing it was tried and measured: giving the automatic path this rule
    //: made a 375px note-card menu that fitted whole at 1280x640 into a 301px
    //: scrolling one, and cost 87px of visible menu at 1280x360, because that
    //: path is allowed to span across its trigger and use the window while
    //: this one keeps the trigger clear. The numbers are at
    //: `placeEscapedMenu`, which is the site a reader is more likely to reach
    //: first.
    menu.style.maxHeight = "none";
    //: A select's list is at least its trigger's width (escaped, CSS's 100%
    //: would be the viewport's), capped at the window.
    if (menu.classList.contains("select-menu")) {
      menu.style.minWidth = `${Math.min(anchor.width, innerWidth - 2 * margin)}px`;
    }
    const box = menu.getBoundingClientRect();
    let left = anchor.right - box.width;
    let top = anchor.bottom + 4;
    if (left < margin) left = margin;
    if (left + box.width > window.innerWidth - margin) {
      left = Math.max(margin, window.innerWidth - margin - box.width);
    }
    //: The room on each side of the trigger, which is the only honest cap:
    //: a fixed figure is either smaller than the window (the reported bug) or
    //: larger than it (a menu running off the bottom).
    const roomBelow = window.innerHeight - margin - (anchor.bottom + 4);
    const roomAbove = anchor.top - 4 - margin;
    if (box.height <= roomBelow) {
      top = anchor.bottom + 4;
      //: **`none`, not `""`.** Clearing the inline cap hands the menu back to
      //: the *stylesheet's* cap, and that is the same lie one level down that
      //: `escapeAndCapMenu` was fixed for in 8b92164: the menu is then placed
      //: by a height it is not drawn at. Downwards that only wastes room;
      //: upwards, the branch below, it is the reported bug. The height was
      //: measured a few lines up with every cap off and found to fit in the
      //: room on this side, so keeping it is exactly what "it fits" meant.
      menu.style.maxHeight = "none";
      menu.style.overflowY = "";
    } else if (box.height <= roomAbove) {
      //: Upwards only when the whole menu fits there. Opening up and *then*
      //: scrolling puts the first row at the bottom of the panel, furthest
      //: from the button that opened it, which reads as a different menu.
      //:
      //: **This is where the cap mattered** (INBOX 119, the owner: "the let
      //: the ai decide button popup is a massive gap above the picker").
      //: Reproduced on :8895, 1440x900 dark, with nine categories in the
      //: notebook (scratchpad/ui-sweeps/notesmenugap3.js): the File under menu
      //: wanted 410.8px, `.select-menu`'s own `max-height: 18rem` drew it at
      //: 288, and `top` was computed from the 410.8, so the menu opened at
      //: y=99 and its bottom landed 127.1px above the opener at y=514.1, with
      //: the gap covering the formatting toolbar and the note body. The
      //: owner's screenshot measures the same 127. Eight categories gave 91px
      //: of gap, ten 163, eleven 199: exactly `wants - drawn + 4` every time,
      //: which is the signature of placing a box by a height something else
      //: then takes away.
      top = anchor.top - 4 - box.height;
      menu.style.maxHeight = "none";
      menu.style.overflowY = "";
    } else {
      //: Taller than both sides: take the larger side and scroll inside it,
      //: with the cut row visible rather than sliced, which is the
      //: affordance. `--space-*` is not reachable from here, so the eight
      //: pixels are the same `margin` the placement already uses.
      const takeBelow = roomBelow >= roomAbove;
      const room = Math.max(120, takeBelow ? roomBelow : roomAbove);
      top = takeBelow ? anchor.bottom + 4 : margin;
      menu.style.maxHeight = `${Math.round(room)}px`;
      menu.style.overflowY = "auto";
    }
    menu.style.left = `${Math.round(left)}px`;
    menu.style.top = `${Math.round(top)}px`;
    //: **Escaping a clipping ancestor can drop the menu below the surface it
    //: belongs to, and that is a second bug wearing the first one's clothes**
    //: (INBOX 239). `<body>` is a lower place to stand than some of the things
    //: this app draws: the escaped menu is `z-index: 1020` from the
    //: stylesheet, and a table block in full view is a fixed panel at 2400, so
    //: the ⋯ menu opened *inside* that panel drew underneath it. Measured on
    //: :8802: the menu's Back row at 1166,248 with `elementFromPoint` at its
    //: centre returning `DIV.md-table-wrap`, and a real click at that point
    //: leaving the panel open, which is the "no way to close it" report.
    //:
    //: The honest rule is the one this reparenting broke: a menu belongs above
    //: the surface it was opened from. So the opener's own positioned
    //: ancestors are read and the highest of them wins, once, at open time.
    //: Nothing is written when the stylesheet's own tier is already higher,
    //: which is every other caller in the app, so this is inert until a menu
    //: is opened inside a surface that outranks it.
    //: Cleared before it is read, or the second pass (a resize, the retry
    //: frame) measures the lift this one wrote and decides it is already high
    //: enough, which alternates between the two values on every resize.
    menu.style.zIndex = "";
    const ownZ = Number(getComputedStyle(menu).zIndex) || 0;
    let over = 0;
    for (let el = opener.parentElement; el && el !== document.body; el = el.parentElement) {
      const z = Number(getComputedStyle(el).zIndex);
      if (Number.isFinite(z) && z > over) over = z;
    }
    menu.style.zIndex = over >= ownZ ? String(over + 1) : "";
    //: Placed, so it may be seen (see the guard at the top of this
    //: function for what this is undoing).
    menu.style.visibility = "";
  };
  //: **A `<select>` inside a native `<dialog>` escapes to the dialog, not to
  //: `<body>`.** Reported directly, on the documents dictionary dialog's
  //: spelling picker: "the dictionary preferences dropdown appears behind
  //: the panel." A `showModal()` dialog paints in the browser's top layer,
  //: which is *always* above the regular document regardless of z-index;
  //: `<body>` is the regular document, so a menu reparented there is behind
  //: every open dialog by construction, not by any z-index this file could
  //: raise. The dialog element itself is still the top-layer root, so
  //: appending inside it keeps the menu in the same painting layer as its
  //: own opener.
  const escapeTarget = () => opener.closest("dialog[open]") || document.body;
  const observer = new MutationObserver(() => {
    // A menu shown as a phone's action sheet (`openKebabSheet`) is already
    // out of every clipping ancestor; escaping it would take it back out of
    // the sheet.
    if (menu._inSheet) return;
    const open = !menu.classList.contains("hidden");
    const target = escapeTarget();
    if (open && menu.parentElement !== target) {
      homeParent = menu.parentElement;
      homeNext = menu.nextSibling;
      //: **Moving a node takes the focus out of it**, and this runs after the
      //: open has already put the focus on the first row (`openActionMenu`,
      //: the select's chosen option): the observer is a microtask, so the
      //: move lands a tick later and the browser drops the focus to `body`.
      //: Measured by scratchpad/ui-sweeps/menus.js at 1440: every select in
      //: the app and every library kebab opened with `document.activeElement`
      //: on `body`, so ArrowDown did nothing and Escape gave the focus to
      //: nobody. Held across the move and handed back.
      const held = menu.contains(document.activeElement) ? document.activeElement : null;
      target.appendChild(menu);
      if (held && held.isConnected) held.focus({ preventScroll: true });
      menu.classList.add("action-menu-escaped");
      // openActionMenu() may have already set `.action-menu-flip` (`bottom:
      // calc(100% + 4px)`) based on the menu's *pre-escape* position. `place()`
      // below sets its own inline `top` to open up-or-down as needed, left
      // together, an element with both `top` and `bottom` pinned and
      // `height: auto` is over-constrained, and reproduced live as the menu's
      // box collapsing to ~15px (just its padding+border) while the buttons
      // still rendered past that line, which is what "background doesn't
      // fill the dropdown, looks transparent" actually was. `place()` makes
      // this class redundant once escaped, so drop it rather than fight it.
      menu.classList.remove("action-menu-flip");
      place();
    } else if (!open && menu.parentElement !== homeParent && homeParent) {
      // Restored on close, not left wherever it escaped to (`<body>` or an
      // open dialog): closeActionMenus() and any future openActionMenu()
      // call both expect to find this menu where it started, and a page
      // that never puts an escaped menu back accumulates stray
      // position:fixed nodes at the end of whichever element it escaped to.
      //: A menu closed with the focus still inside it (Escape handled by
      //: someone other than `wireMenuKeyboard`, a click on a row that opens
      //: nothing) would drop it to `body` on this move; the opener is where it
      //: belongs. Measured on every select: Escape left the focus on `body`.
      const held = menu.contains(document.activeElement);
      //: **After the exit, not before it** (perfpolish; `restoreEscapedMenuAfterExit`
      //: says why): moving the node home cancels the fade `.hidden` starts, so
      //: every menu this wires left at once. The focus still goes to the opener
      //: now; the node goes home when the fade is over, if it is still closed.
      if (held && opener.isConnected) opener.focus({ preventScroll: true });
      afterMenuExit(menu, () => {
        if (!menu.classList.contains("hidden") || menu.parentElement === homeParent || !homeParent) return;
        homeParent.insertBefore(menu, homeNext);
        menu.classList.remove("action-menu-escaped");
        Object.assign(menu.style, { left: "", top: "", visibility: "", maxHeight: "", overflowY: "", zIndex: "" });
      });
    }
  });
  observer.observe(menu, { attributes: true, attributeFilter: ["class"] });
  menu._escapedObserver = observer;
  //: **The re-place on resize is one listener for the whole app, not one per
  //: menu.** This used to be `window.addEventListener("resize", ...)` here,
  //: inside a function that runs once per `kebabMenu()`, which is once per
  //: card. The Library draws sixty cards and rebuilds them on every render,
  //: and `window` is never collected, so every one of those closures stayed
  //: alive holding its own `menu`, `opener` and `place`, and through them the
  //: whole detached card.
  //:
  //: Measured per round (`scratchpad` leak probe, 1440x900, eight rounds of
  //: the seven tabs on a four thousand note notebook, three forced GCs before
  //: each sample), because the question is whether it plateaus. Round one is
  //: one-time: it renders tabs that had never been drawn. A leak keeps
  //: climbing after that, and this did, dead straight:
  //:
  //:              round  1     2     3     4     5     6     7     8
  //:   listeners  3999  4719  5439  6159  6879  7599  8319  9039   (+720 each)
  //:   nodes      26767 28793 30820 32843 34868 36895 38920 40943  (+2025 each)
  //:
  //: with the document itself flat at 13,237 nodes throughout, so every one
  //: of those 2,025 nodes a round was detached and retained. 360 of the 370
  //: observers created and never disconnected came from this function too.
  //:
  //: After: 3,866 listeners and 26,768 nodes on every round from the first,
  //: flat. Heap growth over rounds two to eight went from +1.4 MB to +0.7 MB,
  //: and the `resize` registrations in a run from 657 to 104.
  //:
  //: The listener below is registered once and finds its work in the DOM, so
  //: it holds nothing: a menu that is gone is a menu the query does not
  //: return. `_placeEscaped` is on the element, so the closure lives exactly
  //: as long as the element does.
  menu._placeEscaped = place;
  wireEscapedMenuResize();
}

//: One `resize` listener for every escaped menu there will ever be. See
//: `wireEscapedActionMenu` for the measurement that made this necessary.
//:
//: It asks the document rather than holding a list: `closeActionMenus` can
//: remove a menu, a render can replace the card under it, and either would
//: leave a stale entry in a registry. `:not(.hidden)` because a closed menu
//: has nothing to place, and only an escaped one is positioned by this file
//: at all.
let escapedMenuResizeWired = false;
function wireEscapedMenuResize() {
  if (escapedMenuResizeWired) return;
  escapedMenuResizeWired = true;
  window.addEventListener(
    "resize",
    () => {
      for (const menu of document.querySelectorAll(".action-menu-escaped:not(.hidden)")) {
        menu._placeEscaped?.();
      }
    },
    { passive: true }
  );
}

//: A backlink's sentence with the hit marked, as three nodes (a note's text is
//: not markup); the offsets come from the server, so the hit found is the one
//: marked. Shared by a document's panel and a note's connections (KG1).
function docBacklinkContext(row) {
  const line = document.createElement("p");
  line.className = "doc-backlink-context";
  const text = row.context || "";
  const from = Math.max(0, Math.min(text.length, row.hit_start | 0));
  const to = Math.max(from, Math.min(text.length, row.hit_end | 0));
  const mark = document.createElement("mark");
  mark.textContent = text.slice(from, to);
  line.append(document.createTextNode(text.slice(0, from)), mark, document.createTextNode(text.slice(to)));
  return line;
}

$("connections-close")?.addEventListener("click", () =>
  $("connections-overlay").classList.add("hidden")
);
$("connections-dock")?.addEventListener("click", (event) => {
  $("connections-overlay").classList.add("hidden");
  const id = Number(event.currentTarget.dataset.id);
  if (Number.isFinite(id)) dockConnectionsInRail(id);
});

// The ⋯ overflow menu on each note card (Wave L rework).
// Everything that ever happened to one note, with a way back to any of it.
//
// The rows are the event log (Brief 7): every write through the managers
// records one event with an actor and the whole value of each field it set,
// so a row can say who changed the note, what it became, and put it back by
// replaying the log to that point. `revisions` is the older per-edit snapshot
// list, still written and still restorable, and it is what a note whose
// history predates the event log has instead of rows.
const HISTORY_ACTION_WORDS = {
  created: "Written",
  edited: "Edited",
  restored: "Restored",
  deleted: "Moved to the bin",
  archived: "Archived",
  unarchived: "Taken out of the archive",
  linked: "Linked",
  unlinked: "Unlinked",
  purged: "Deleted for good",
  filed: "Filed", // the auto-filer's own move (manager.record_filing, system:filing)
};

function historyActorLabel(actor) {
  // "ai:summarise" and "system:auto-file" carry the half worth reading after
  // the colon; "user" is everything a person did and needs no chip at all.
  //: Every change says whose it was (INBOX 446, the owner: "I cant
  //: distinguish between personal or ai edits or mixed edits").
  if (!actor || actor === "user") return "You";
  if (actor === "user+ai") return "You and Atlas";
  const [kind, rest] = [actor.slice(0, actor.indexOf(":")), actor.slice(actor.indexOf(":") + 1)];
  //: `ai:<tool>@<model>` since 0.3.32: which model made the change.
  if (kind === "ai") {
    const [tool, model] = rest.split("@");
    return model ? `Atlas (${model}): ${tool.replace(/_/g, " ")}` : `AI: ${rest}`;
  }
  if (kind === "system") return `Background: ${rest}`;
  //: `agent:<tool>@<who>`: an outside agent, through the MCP server or the
  //: API with its name in `X-MemoryMap-Agent` (H4); `api` for a plain write.
  if (kind === "agent") {
    const [tool, who] = rest.split("@");
    return tool === "api" ? `${who} (agent)` : `${who} (agent): ${tool.replace(/_/g, " ")}`;
  }
  return actor;
}

async function toggleEntryPrivacy(entry) {
  const makingPrivate = !entry.is_private;
  if (makingPrivate) {
    const ok = (await confirmDialog(
      "Make this note private?\n\n" +
        "It gets encrypted with a key derived from your password, so it stays " +
        "unreadable in the database, in backups, and to anyone without that " +
        "password.\n\n" +
        "It also stops appearing in search and stops being given to Atlas.\n\n" +
        "There is no recovery: if you forget your password this note is gone."
    ));
    if (!ok) return;
  }
  // Both directions need the key, which a session without a password lacks.
  if (!(await ensureVaultOpen())) return;
  try {
    await apiJson(`/entries/${entry.id}/privacy`, {
      method: "POST",
      body: JSON.stringify({ private: makingPrivate }),
    });
    const setPrivacy = (value) => async () => {
      await apiJson(`/entries/${entry.id}/privacy`, { method: "POST", body: JSON.stringify({ private: value }) });
      await refreshEntries([entry.id]);
    };
    pushUndo(makingPrivate ? "Made a note private" : "Made a note readable", setPrivacy(!makingPrivate), setPrivacy(makingPrivate));
    toast(makingPrivate ? "Note encrypted." : "Note is readable again.");
    await refreshEntries([entry.id]);
  } catch (error) {
    toast(error.message, true);
  }
}

// Reported: no popup shows when a title is regenerated.
//
// There WAS a toast, and it was being swallowed. `toast()` drops anything
// that is not an error while notifications are muted, which is right for
// background chatter and wrong here: this is the result of a button the user
// just pressed, and a direct action that reports nothing reads as a broken
// button. Muting is about noise you did not ask for.
//
// The "Generating…" toast is also worth keeping distinct from the settled one:
// this call waits on the model, so it can take seconds, and a control that
// looks inert for seconds gets pressed again.
async function generateEntryTitle(entry) {
  const regenerating = Boolean(entry.title);
  try {
    toast(regenerating ? "Regenerating the title…" : "Generating a title…", false, {
      exempt: true,
    });
    const updated = await apiJson(`/entries/${entry.id}/generate-title`, { method: "POST" });
    if (updated?.content) pushEntryPutUndo(entry.id, "Titled a note", { content: entry.content }, { content: updated.content });
    await refreshEntries([entry.id]);
    flashEntry(entry.id);
    const title = updated && updated.title;
    toast(title ? `Titled “${title}”.` : "Titled.", false, { exempt: true });
    // And in the notification centre, so the result survives the 5.5 seconds
    // the toast lives for, the model can finish while you are on another tab.
    recordNotification({
      kind: "task",
      title: regenerating ? "Title regenerated" : "Title generated",
      detail: title ? `“${title}”` : `Note #${entry.id}`,
    });
  } catch (error) {
    toast(error.message || "Couldn't generate a title.", true);
  }
}

async function removeEntryTitle(entry) {
  try {
    const updated = await apiJson(`/entries/${entry.id}/remove-title`, { method: "POST" });
    if (updated?.content) pushEntryPutUndo(entry.id, "Removed a title", { content: entry.content }, { content: updated.content });
    await refreshEntries([entry.id]);
    flashEntry(entry.id);
    // Said out loud: it was silent.
    toast("Title removed.", false, { exempt: true });
  } catch (error) {
    toast(error.message || "Couldn't remove the title.", true);
  }
}

// Arrow-key navigation, as the `role="menu"` contract implies. ↑/↓ move
// between *top-level* items (wrapping): `:scope >` so a hidden submenu's own
// items (handled by their own keydown handler) never get mixed into this list,
// which would desync Home/End and let arrow keys land on an item the user
// can't currently see. Home/End jump to the ends, Esc closes and returns focus
// to the opener.
//
// **Shared, because it used to belong to one menu.** This was written inline
// inside `entryOverflowMenu`, so the note card's ⋯ had full keyboard
// navigation and every menu built by `kebabMenu`, the conversation list, the
// sidebar kebabs, and now the text-selection menu, had none: Tab still
// stepped through the items (they are buttons), but ↑/↓ did nothing, which is
// the one thing a person who has just opened a menu will try. Found by
// driving the new selection menu from the keyboard and watching ArrowDown
// leave focus where it was.
function wireMenuKeyboard(menu, opener) {
  //: Read by the delegated walker for markup menus (search `menuRowsOf`),
  //: which leaves a menu wired here alone.
  menu.dataset.menuKeys = "1";
  menu.addEventListener("keydown", (event) => {
    const menuItems = [
      ...menu.querySelectorAll(
        //: `role="option"` too: an enhanced select's listbox is wired here, and
        //: with menuitems alone its arrow keys found nothing and returned,
        //: which left every select in the app without ArrowDown (and without
        //: this Escape, so inside Settings the Escape went on to close the
        //: whole Settings window and left the list floating over the page).
        ':scope > [role="option"], ' +
        ':scope > [role="menuitem"], :scope > .menu-group > [role="menuitem"], ' +
        //: `role="group"` as well as `.menu-group`, so a menu written in
        //: markup can use the wrapper ARIA actually names. `kebabMenu` builds
        //: its own groups as `.menu-group` divs with no role, and the board's
        //: five top-bar menus are sections in index.html that become
        //: `role="group"` at boot (`wbStampMenuRoles` in whiteboard.js): with
        //: only the class in this list, ArrowDown in those five found no items
        //: at all and left the focus where it was, which is the one thing a
        //: person who has just opened a menu will try.
        ':scope > [role="group"] > [role="menuitem"]'
      ),
    ]
      //: An item nobody can see is not one the arrows may land on. It never
      //: came up while every menu here was built by `kebabMenu`, which draws
      //: only the items it was given; the board's View menu keeps two map rows
      //: `hidden` on an ordinary whiteboard, and walking onto one of those
      //: calls `focus()` on an element that cannot take it, which leaves the
      //: focus where it was and reads as "the arrow keys do nothing".
      .filter((item) => !item.hidden && item.offsetParent !== null);
    if (!menuItems.length) return;
    const current = menuItems.indexOf(document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusMenuItem(menuItems[(current + 1) % menuItems.length], menu);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusMenuItem(menuItems[(current - 1 + menuItems.length) % menuItems.length], menu);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusMenuItem(menuItems[0], menu);
    } else if (event.key === "End") {
      event.preventDefault();
      focusMenuItem(menuItems[menuItems.length - 1], menu);
    } else if (event.key === "Escape") {
      event.preventDefault();
      //: The menu owns this Escape: without the stop, the document's own
      //: Escape handler goes on to close whatever the menu is inside (the
      //: Settings window, a sheet), one key doing two things.
      event.stopPropagation();
      closeActionMenus();
      opener.focus();
    }
  });
}

// A single `role="menuitem"` button: shared by the top-level menu and every
// submenu, so a click behaves identically (close everything, then run) no
// matter how deep the item is nested.
function buildMenuItemButton(item) {
  const button = document.createElement("button");
  button.setAttribute("role", "menuitem");
  button.className = "menu-item" + (item.danger ? " menu-danger" : "");
  setLabel(button, item.label);
  if (item.title) button.title = item.title;
  button.addEventListener("click", () => {
    closeActionMenus();
    item.run();
  });
  return button;
}

// At most one grouped flyout (AI actions / Connect / Add) is ever open at
// once, on any note card: `openActionMenu` already guarantees at most one
// top-level kebab is open on the page, and only one of its own groups can
// be expanded at a time. A single reference here is enough to close a
// sibling group's flyout when another opens, without a DOM search that
// escaping the flyout to `<body>` below has already made impossible (see
// `buildMenuGroupButton`'s own note).
let openGroupSubmenu = null;

// A grouped trigger ("AI AI actions ›") that opens a side flyout of its own
// items: asked for directly, to cut a 15-item flat list down to something
// scannable. Hover opens it on a device that has hover; click/tap opens it
// everywhere, which is the only way in on a touchscreen. Below
// `--menu-submenu-stack-width` (phone-width) there is nowhere for a flyout
// to go without running off-screen, so it drops the side-popup positioning
// entirely and expands in place instead, an accordion, not a flyout, which
// is what "compatible with small screens like iPhones" actually means here.
function buildMenuGroupButton(label, subItems) {
  let openedByHoverAt = 0;
  const groupWrap = document.createElement("div");
  groupWrap.className = "menu-group";

  const trigger = document.createElement("button");
  trigger.setAttribute("role", "menuitem");
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");
  trigger.className = "menu-item has-submenu";
  const labelSpan = document.createElement("span");
  // setLabel, not textContent: these three group triggers ("AI actions",
  // "Connect", "Add") were the one label sink the sweep missed, so the note
  // kebab menu rendered the literal text "ph:sparkle AI actions".
  setLabel(labelSpan, label);
  labelSpan.className = "menu-item-words";
  const arrow = document.createElement("span");
  arrow.className = "menu-submenu-arrow";
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "›";
  trigger.append(labelSpan, arrow);

  const submenu = document.createElement("div");
  submenu.className = "action-menu submenu hidden";
  submenu.setAttribute("role", "menu");
  //: **An entry may be a button that already exists**, not only a descriptor
  //: to build one from. The document editor's ⋯ is static markup whose rows
  //: carry ids that `documents.js` binds handlers to (`doc-export-md` and
  //: four more), so folding them into a group has to *move* those buttons
  //: rather than rebuild them: a rebuilt row is a row with no handler and an
  //: id that two lints watch. Everything else about the group is identical,
  //: which is the point of reusing this recipe rather than writing a second
  //: flyout for one menu.
  for (const item of subItems) {
    submenu.appendChild(item instanceof HTMLElement ? item : buildMenuItemButton(item));
  }

  // **Reparented to `<body>` while open, like `escapeMenuIfClipped` does for
  // the top-level kebab.** Reported: a submenu opened from a kebab near the
  // bottom or right of the viewport (a note card low in the list, or the
  // last card in a row) drew past the window edge with nothing but a
  // scrollbar to show for it. `.action-menu.submenu` was `position:
  // absolute` against its own `.menu-group`, which only ever checked the
  // *horizontal* edge (`submenu-left`, below); there was no vertical check
  // at all, and once the parent kebab is itself escaped (also `position:
  // fixed`, also reparented to `<body>`) the submenu's containing block
  // moves with it, so a flyout that fit its note card could still miss the
  // actual browser window. Reusing `.action-menu-escaped` (`position:
  // fixed`, the same z-index tier) plus this menu's own placement, computed
  // from the trigger's rect and clamped on both axes, fixes both at once:
  // this is why `openSubmenu`/`closeSubmenuState` below write the same
  // `_escapedHome`/`_escapedOpener` fields `restoreEscapedMenu` already
  // knows how to put back, rather than inventing a second bookkeeping
  // scheme `closeActionMenus`' own document-wide sweep would not see.
  const placeSubmenu = () => {
    const margin = 8;
    const anchor = trigger.getBoundingClientRect();
    submenu.style.marginLeft = "0";
    submenu.style.left = "0px";
    submenu.style.top = "0px";
    const box = submenu.getBoundingClientRect();
    let left = anchor.right + 8;
    let onLeft = false;
    if (left + box.width > window.innerWidth - margin) {
      left = anchor.left - 8 - box.width;
      onLeft = true;
    }
    left = Math.max(margin, left);
    let top = anchor.top;
    if (top + box.height > window.innerHeight - margin) {
      top = Math.max(margin, window.innerHeight - margin - box.height);
    }
    submenu.style.left = `${Math.round(left)}px`;
    submenu.style.top = `${Math.round(top)}px`;
    submenu.classList.toggle("submenu-left", onLeft);
  };

  const openSubmenu = () => {
    // Only one flyout open at a time, at this level or any sibling group;
    // a DOM search under `groupWrap.parentElement` cannot find a sibling's
    // flyout once it may live at `<body>`, so this is tracked directly.
    if (openGroupSubmenu && openGroupSubmenu !== submenu) closeSubmenuState(openGroupSubmenu);
    submenu.classList.remove("hidden");
    trigger.setAttribute("aria-expanded", "true");
    submenu.classList.remove("submenu-left");
    // Below phone-width the flyout positioning is dropped for an in-place
    // accordion (CSS media query); escaping it there would strand it at a
    // fixed viewport position while its own trigger scrolls underneath.
    if (window.innerWidth > 720) {
      submenu._escapedHome = { parent: submenu.parentElement, next: submenu.nextSibling };
      submenu._escapedOpener = trigger;
      document.body.appendChild(submenu);
      submenu.classList.add("action-menu-escaped");
      placeSubmenu();
    }
    openGroupSubmenu = submenu;
  };
  function closeSubmenuState(target) {
    target.classList.add("hidden");
    target._escapedOpener?.setAttribute("aria-expanded", "false");
    restoreEscapedMenu(target);
    target.style.marginLeft = "";
    target.classList.remove("submenu-left");
    if (openGroupSubmenu === target) openGroupSubmenu = null;
  }
  const closeSubmenu = () => closeSubmenuState(submenu);

  let hoverTimer = null;
  groupWrap.addEventListener("mouseenter", () => {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      openSubmenu();
      openedByHoverAt = Date.now();
    }, 120); // brief delay: a mouse crossing the item isn't a request to open it
  });
  groupWrap.addEventListener("mouseleave", () => {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(closeSubmenu, 200); // outlives the diagonal move from the trigger into the flyout
  });
  // Once escaped, the submenu is a sibling of `groupWrap` at `<body>`, not
  // its descendant, so `groupWrap`'s own `mouseleave` above fires the
  // instant the pointer crosses onto the (still open) flyout: measured
  // live, the submenu closed under the cursor before a hovering mouse user
  // could ever reach a second-level item. These two mirror the pair above
  // so hovering the flyout itself also keeps it open.
  submenu.addEventListener("mouseenter", () => clearTimeout(hoverTimer));
  submenu.addEventListener("mouseleave", () => {
    hoverTimer = setTimeout(closeSubmenu, 200);
  });
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    //: A click that lands just after the hover opened the flyout is the same
    //: request, not a second one: toggling there closed what the person had
    //: just reached for (measured on the map node menu).
    if (submenu.classList.contains("hidden")) openSubmenu();
    else if (Date.now() - openedByHoverAt > 600) closeSubmenu();
  });
  submenu.addEventListener("keydown", (event) => {
    const subItems = [...submenu.querySelectorAll(':scope > [role="menuitem"]')];
    const current = subItems.indexOf(document.activeElement);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      subItems[(current + 1) % subItems.length]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      subItems[(current - 1 + subItems.length) % subItems.length]?.focus();
    } else if (event.key === "ArrowLeft" || event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation(); // don't also close the whole menu on ArrowLeft
      closeSubmenu();
      trigger.focus();
    }
  });
  trigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openSubmenu();
      submenu.querySelector('[role="menuitem"]')?.focus();
    }
  });

  groupWrap.append(trigger, submenu);
  return groupWrap;
}

function entryOverflowMenu(entry) {
  const wrap = document.createElement("span");
  wrap.className = "menu-wrap";

  const menu = document.createElement("div");
  menu.className = "action-menu hidden";
  menu.setAttribute("role", "menu");

  //: Same square-kebab rule as `kebabMenu` below: this is the *other* ⋯
  //: builder (note cards, built lazily on first open), and a rule applied to
  //: one of two implementations of the same control is how they drift.
  //:
  //: **And they had.** Reported: "the ellipse kebab icons in the notes on the
  //: your notes tab are not centred." `kebabMenu` draws `ph:dots-three`; this
  //: one drew the literal character `⋯` (U+22EF), and a text glyph is placed
  //: on the *font's* baseline inside a 19.2px line box centred in a 28px
  //: button: U+22EF sits at the em box's midline, which is above the line
  //: box's optical centre, so the dots rode high. No amount of flex centring
  //: fixes that: the box is centred correctly and the glyph is not centred
  //: within the box. The icon font's own glyph is drawn to fill its box, so
  //: using the same icon as the other builder fixes the centring and the
  //: drift in one go.
  const opener = smallButton("ph:dots-three", "More actions", () => {
    // The phone's action sheet, as `kebabMenu` opens (`openKebabSheet`).
    if (window.matchMedia(PHONE_ACTION_SHEET).matches && typeof openSheet === "function") {
      fillMenu();
      openKebabSheet(menu, opener, "Note actions");
      return;
    }
    const willOpen = menu.classList.contains("hidden");
    if (willOpen) {
      fillMenu();
      openActionMenu(menu, opener);
    } else closeActionMenus();
  });
  opener.classList.add("icon-only");
  opener.setAttribute("aria-haspopup", "menu");
  opener.setAttribute("aria-expanded", "false");

  // **Built on first open, not on render: a scale fix.** This menu is about 50
  // nodes and `entryItem()` builds one per note card, on every renderEntries()
  // (every search keystroke, sort, filter and save); a 2,500-note notebook built
  // over a hundred thousand hidden nodes nobody opens. The opener renders eagerly
  // (it carries the aria state and a tab stop); only the contents are deferred,
  // and `openActionMenu` runs after `fillMenu()` so it finds a first item.
  let filled = false;
  function fillMenu() {
    if (filled) return;
    filled = true;
    // Kept flat: the three actions used often enough, or serious enough (a
    // delete), that burying them a level down would cost more than the
    // grouping below saves. Everything else groups into three side flyouts, 
    // asked for directly, to cut what had grown into a 15-item flat list.
    const topLevel = [
      // Direct instruction: a way into multi-select from the row itself,
      // not only the toolbar's own "Select" button: which is real and
      // already works, but requires knowing it exists and is above the
      // list rather than on the note someone actually wants to start
      // selecting from. Reuses that exact same mode (`enterSelectMode`,
      // `selectedIds`) rather than inventing a second one, and seeds it
      // with this note already checked, so choosing "Select" here is a
      // head start rather than an empty selection identical to the
      // toolbar button's own.
      {
        label: "ph:check-square Select",
        title: "Start selecting multiple notes, beginning with this one",
        run: () => {
          enterSelectMode();
          selectedIds.add(entry.id);
          updateBatchCount();
          renderEntries();
        },
      },
      //: The one correction a notebook that files for you is asked for most
      //: (INBOX 432); the card's category chip opens the same sheet.
      {
        label: "ph:folder-open Move to category",
        title: `Now in ${entry.category || "Uncategorised"}; choose another`,
        run: () => chooseNoteCategory([entry.id], entry.category),
      },
      {
        label: entry.is_private ? "ph:lock-open Make readable" : "ph:lock Make private",
        title: entry.is_private
          ? "Decrypt this note so search and Atlas can use it again"
          : "Encrypt this note at rest, and keep it out of search and Atlas",
        run: () => toggleEntryPrivacy(entry),
      },
      {
        // Sits above History because it is the more common question by far:
        // "what else is this about?" is asked of a note every time it is
        // read, and "what did it used to say?" only when something looks
        // wrong.
        label: "ph:graph Connections",
        title: "Everything this note is joined to, links both ways, documents, boards and files",
        // The note's own title when it wrote one, and its first words
        // otherwise: `notePreviewText` alone hands back both lines of a
        // titled note ("Probe A\nrelates to sourdough"), which reads as
        // two sentences jammed together on one line of the dialog.
        run: () =>
          lazyScript("/js/connections.js").then(() => openConnections(
            "entries",
            entry.id,
            entry.title || noteNamePlain(entry.content, 80)
          )),
      },
      {
        label: "ph:clock-counter-clockwise History",
        title: "See earlier versions of this note, and put one back",
        run: () => openEntryHistory(entry),
      },
      // BACKLOG.md §95 item D.14: "Full export exists. There is no way to
      // hand one note to someone." Same route shape and same "download,
      // not navigate" pattern the Documents kebab's own "Download .md"
      // already uses (library.js).
      {
        label: "ph:download-simple Download .md",
        title: "Save a copy of this note as a markdown file",
        run: () => downloadFromApi(`/entries/${entry.id}/export.md`, "note.md"),
      },
    ];

    //: With no model the app does these itself and the menu says so (O7;
    //: BACKLOG "The composer does Improve writing and Generate title").
    const off = aiIsOff();
    const aiItems = [
      {
        //: **Named for what it does, not for what it is called internally**
        //: (INBOX 292, the owner: "i feel like it is more than just
        //: re-evaluating, and it is hidden away"). The route re-files the
        //: note, refreshing its confidence and its category unless the person
        //: filed it themselves, *and* suggests tags and links for them to
        //: apply. "Re-evaluate" named the smallest part of that, and tags,
        //: the part it is actually reached for, were not in the name at all.
        label: off ? "ph:tag Tag and file" : "ph:sparkle Tag and file with Atlas",
        title: "Atlas re-reads the note, suggests tags and links, and may refile it",
        run: () => reevaluateEntry(entry),
      },
      {
        label: off ? "ph:text-aa Proofread" : "ph:sparkle Improve writing",
        title: off ? "Spelling and capitals put right with no model; rewording needs one" : "Proofread or rewrite this note with AI",
        run: async () => {
          if (!(await openNoteEditor(entry.id))) return;
          // The edit textarea now exists, improve it in place.
          const box = document.querySelector(`#entry-list li[data-id="${entry.id}"] textarea`);
          if (box) openImprove(box);
        },
      },
      {
        // Recognising a title the note already wrote (a leading `# Heading`)
        // is free; writing one costs a real model call, so it's this
        // separate, on-request action rather than something automatic.
        label: off ? "ph:text-h Title from its words" : entry.title ? "ph:sparkle Regenerate title" : "ph:sparkle Generate title",
        title: off ? "A title taken from the note's first sentence, with no model" : "Write a short title for this note with AI",
        run: () => generateEntryTitle(entry),
      },
      ...(entry.title
        ? [
            {
              label: "ph:x Remove title",
              title: "Take the title back out, the note's text is unchanged",
              run: () => removeEntryTitle(entry),
            },
          ]
        : []),
    ];

    const connectItems = [
      {
        label: "ph:file-text Add to a document",
        title: "Attach this note to a document you have already started",
        run: () => {
          inlineAction = inlineActionIs(entry.id, "document")
            ? null
            : { id: entry.id, kind: "document" };
          renderEntries();
        },
      },
      {
        //: INBOX 246's first sentence. Next to "Add to a document" because
        //: it is the same act on the other kind of surface, and the note
        //: stays exactly where it is either way.
        label: "ph:squares-four Add to a board or map",
        title: "Put this note on a whiteboard or a mind map",
        run: () => {
          inlineAction = inlineActionIs(entry.id, "board")
            ? null
            : { id: entry.id, kind: "board" };
          renderEntries();
        },
      },
      {
        label: "ph:file-text Expand into a document",
        title: "Start a document from this note, the note stays where it is",
        run: () => expandNoteIntoDocument(entry),
      },
      { label: "ph:link Link to another", run: () => beginOrCompleteLink(entry) },
      //: A meeting's sheet (INBOX 644): its action items, decisions,
      //: Summarise and Record into it. The meeting chip opens the same.
      ...(noteIsMeeting(entry)
        ? [{ label: "ph:users-three Meeting", run: () => openMeetingSheet(entry.id) }]
        : []),
      //: KG4: the note's properties and type, as a table.
      {
        label: "ph:list-bullets Properties",
        title: "Fields at the top of this note (status, due, a type's fields), kept in its text",
        run: () => openNotePropertiesSheet(entry),
      },
      //: The way to point at this note from another one, ready to paste
      //: (INBOX 432: there was no copy link at all). Its name as `[[` finds
      //: it, the title or the first words.
      {
        label: "ph:brackets-square Copy wiki link",
        title: "Copy a [[wiki link]] to this note, to paste into another note or document",
        run: async () => {
          const name = noteNamePlain(entry.title || entry.content).slice(0, 80).trim();
          if (await copyToClipboard(`[[${name}]]`)) toast("Link copied. Paste it into any note.");
        },
      },
      appLinkMenuItem("note", entry.id),
      { label: "ph:approximate-equals Similar notes", run: () => toggleRelated(entry) },
      {
        label: "ph:arrow-u-up-left Referenced by",
        title: "Documents, notes, boards and maps that point at this note",
        run: () => toggleReferences(entry),
      },
      {
        label: "ph:hourglass-medium Forgotten notes like this",
        title: "Notes you have not looked at in a long time that are close to this one",
        run: () => toggleFaded(entry),
      },
      //: **The note's two other homes, one press away** (INBOX 393: "there
      //: needs to be more integration between all the main features"). The
      //: menu could put a note on a board, in a document and in a reminder,
      //: and could not take it to the graph that draws it or to the chat that
      //: answers about it.
      {
        label: "ph:graph Show in graph",
        title: "Open the graph centred on this note, its links lit",
        run: () => showNoteInGraph(entry.id),
      },
      {
        label: "ph:chat-circle Ask Atlas about this note",
        title: "Start a chat about this note and what it connects to",
        run: () => askAtlasAboutNote(entry),
      },
      {
        label: "ph:translate Translate",
        title: "Open this note in the Writing room, set to translate",
        run: () => translateNoteInDesk(entry),
      },
    ];

    const addItems = [
      {
        label: "ph:copy Duplicate",
        title: "Make a copy of this note, opens ready to edit",
        run: async () => {
          closeActionMenus();
          try {
            const copy = await apiJson("/entries", {
              method: "POST",
              body: JSON.stringify({
                //: The copy's title is its first "# " line: the API takes no
                //: `title`, so the "(Copy)" this sent was dropped and the two
                //: notes were indistinguishable (INBOX 432).
                content: /^#\s+\S/.test(entry.content || "")
                  ? entry.content.replace(/^#\s+[^\n]*/, (line) => `${line.trimEnd()} (copy)`)
                  : entry.content,
                category: entry.category,
                tags: entry.tags || [],
              }),
            });
            await loadEntries();
            pushEntryCreateUndo(copy, "Duplicated a note");
            // Open the new note in edit mode straight away.
            if (copy && copy.id) {
              flashEntry(copy.id);
              await openNoteEditor(copy.id);
            }
            toast("Note duplicated.");
          } catch (err) {
            toast(err.message || "Couldn't duplicate note.", true);
          }
        },
      },
      //: OPEN row 566: the note's headings and lists as a mind map, the same
      //: build as the agent's `map_from_note`, so no model is needed.
      ...(entry.is_private ? [] : [{
        label: "ph:tree-structure Make a mind map",
        title: "A mind map of this note: its title in the centre, its headings and lists as branches",
        run: async () => {
          try {
            const board = await apiJson(`/whiteboard/maps/from-note/${entry.id}`, { method: "POST" });
            pushBinPairUndo("Made a mind map from a note", `/entries/${board.id}`, `/entries/${board.id}/restore`, true, () => refreshEntries([board.id]));
            await openWhiteboardBoard(board.id);
          } catch (err) {
            toast(err.message || "Couldn't make a mind map of this note.", true);
          }
        },
      }]),
      //: Section 17 row 1: settle a filing from the note itself.
      ...(entryNeedsReview(entry)
        ? [{
          label: "ph:check-circle Accept the filing",
          title: `Keep it in ${entry.category}; it leaves the review queue`,
          run: async () => {
            const accepted = await apiJson(`/review-queue/${entry.id}/accept`, { method: "POST" }).catch((e) => toast(e.message, true));
            if (accepted !== undefined) {
              const settle = (value) => async () => {
                await apiJson(`/entries/${entry.id}/filing`, { method: "POST", body: JSON.stringify({ accepted: value }) });
                await refreshEntries([entry.id]);
              };
              pushUndo(`Kept a note in ${entry.category}`, settle(false), settle(true));
            }
            await refreshEntries([entry.id]);
            toast(`Kept in ${entry.category}.`);
          },
        }]
        : []),
      //: Section 17 row 6: the note read aloud, then what it links to and why.
      { label: "ph:speaker-high Explain this note", title: "Read it aloud, then what it links to and why", run: () => explainNote(entry) },
      {
        label: "ph:plus Add context",
        title: "Append detail: Atlas may refile it",
        run: () => {
          inlineAction = inlineActionIs(entry.id, "context") ? null : { id: entry.id, kind: "context" };
          renderEntries();
        },
      },
      {
        label: "ph:arrow-bend-down-right Continue thought",
        title: "Start or extend a thread from this note",
        run: () => {
          inlineAction = inlineActionIs(entry.id, "continue") ? null : { id: entry.id, kind: "continue" };
          renderEntries();
        },
      },
      {
        label: "ph:alarm Remind me",
        run: () => {
          inlineAction = inlineActionIs(entry.id, "remind") ? null : { id: entry.id, kind: "remind" };
          renderEntries();
        },
      },
      { label: "ph:paperclip Attach a file", run: () => attachFileTo(entry) },
      { label: "ph:images-square Attach from Library", run: () => attachFromLibrary(entry) },
    ];

    // Not destructive, so not grouped with "danger" below: but visually
    // adjacent to it (asked for directly: a way to keep a note but get it
    // out of the way, distinct from binning it) so the two "get this off my
    // list" actions sit together rather than one being buried in a group.
    const archive = entry.archived_at
      ? {
          label: "ph:arrow-u-up-left Unarchive",
          title: "Bring this note back into your notebook",
          run: async () => {
            await apiJson(`/entries/${entry.id}/unarchive`, { method: "POST" });
            pushRoutePairUndo("Unarchived a note", [`/entries/${entry.id}/archive`, "POST"], [`/entries/${entry.id}/unarchive`, "POST"], () => refreshEntries([entry.id]));
            await refreshEntries([entry.id]);
            toast("Unarchived.");
          },
        }
      : {
          label: "ph:archive Archive",
          title: "Keep it, but out of the way, not the bin",
          //: Undoable like Move to bin beside it (INBOX 432), and it says
          //: where the note went, since nothing in the Notes tab shows it.
          run: async () => {
            const archive = async () => {
              await apiJson(`/entries/${entry.id}/archive`, { method: "POST" });
              await refreshEntries([entry.id]);
            };
            const unarchive = async () => {
              await apiJson(`/entries/${entry.id}/unarchive`, { method: "POST" });
              await refreshEntries([entry.id]);
            };
            await archive();
            const action = pushUndo("Archived a note", unarchive, archive);
            toastAction("Archived. Find it in Library, Archived.", "Undo", async () => {
              settleUndoFromToast(action);
              await unarchive();
            });
          },
        };

    const danger = {
      label: "ph:trash Move to bin",
      danger: true,
      run: () => binNoteWithUndo(entry),
    };

    //: Three groups, broken by the same hairline `kebabMenu` draws for a
    //: grouped menu (DESIGN.md: past five rows a menu is grouped): what you
    //: do to this note, the three families that open further, and the two
    //: that put it away. Ten rows read as one list before this (menus.js).
    const rule = () => {
      const sep = document.createElement("div");
      sep.className = "menu-sep";
      sep.setAttribute("role", "separator");
      return sep;
    };
    for (const item of topLevel) menu.appendChild(buildMenuItemButton(item));
    menu.appendChild(rule());
    //: A private note never goes to a model: the server refuses retitling
    //: and re-filing one, so the menu does not offer what would only toast
    //: a refusal (sweep 1004).
    if (!entry.is_private) menu.appendChild(buildMenuGroupButton("ph:sparkle AI actions", aiItems));
    menu.appendChild(buildMenuGroupButton("ph:link Connect", connectItems));
    menu.appendChild(buildMenuGroupButton("ph:plus Add", addItems));
    menu.appendChild(rule());
    menu.appendChild(buildMenuItemButton(archive));
    menu.appendChild(buildMenuItemButton(danger));
  }

  wireMenuKeyboard(menu, opener);

  wrap.append(opener, menu);
  return wrap;
}

//: Moved from app.js (its gzip ratchet): called only at save time, never at
//: load, so any boot piece may hold it.
//: **Two windows, one note** (WORLD_CLASS_PLAN 22.1 item 5). A save the
//: server refused because the text changed elsewhere since this editor
//: opened it (a 409 whose detail has `code: "edit_conflict"`, see
//: api/edit_conflicts.py) asks what to do instead of losing either side:
//: **Keep mine** saves this editor's text over the other (the filled
//: button, the one the person was already doing), **Take theirs** loads
//: the other window's text into the editor, and **Compare** opens the
//: difference in place, drawn by the app's one diff builder
//: (`docRenderDiff`, DESIGN.md; the library bundle is loaded first when a
//: note's prompt is the first thing to need it), so the choice is made
//: seeing both.
//: Escape, the backdrop or "Not now" answer null: nothing is saved and the
//: editor keeps its text, still unsaved. The dialog is `confirmDialog`'s
//: own card and overlay, so it has its scrim, its tier and its focus trap.
//: Answers "mine", "theirs" or null.
function isEditConflict(error) {
  return error?.status === 409 && error?.detail?.code === "edit_conflict";
}

//: **Explain this note** (WORLD_CLASS_PLAN section 17 row 6, from the owner's
//: first notes: "the AI reads answers aloud; explains what you entered"). The
//: note's words, then each note it links to with the reason the link carries,
//: read with the browser's own voices (`speakText`, which a second press stops)
//: and shown in a sheet as it is read. From the links' reasons, so it works
//: with the model off; a link nobody gave a reason says so.
async function explainNote(entry) {
  const full = await apiJson(`/entries/${entry.id}`).catch(() => null);
  if (!full) return toast("Couldn't read this note.", true, { action: ["Try again", () => explainNote(entry)] });
  const words = stripFrontmatter(full.content || "").replace(/^#+\s*/gm, "").trim();
  const links = full.links || [];
  const name = (link) => noteNamePlain(link.preview).slice(0, 80) || "a note";
  const lines = links.map((link) => `“${name(link)}”: ${link.reason ? link.reason : "no reason was given for this link"}.`);
  const about = links.length
    ? `It links to ${links.length} note${links.length === 1 ? "" : "s"}. ${lines.join(" ")}`
    : "It links to no other notes yet.";
  speakText(`${words}\n\n${about}`);
  openSheet({
    label: "Explain this note",
    name: "explain-note",
    onClose: () => {
      if ("speechSynthesis" in window) speechSynthesis.cancel();
    },
    build: (card) => {
      const body = document.createElement("div");
      body.className = "explain-note-body";
      const text = document.createElement("p");
      text.className = "explain-note-text";
      text.textContent = words || "This note has no words of its own.";
      const head = document.createElement("p");
      head.className = "muted text-sm";
      head.textContent = links.length ? `It links to ${links.length} note${links.length === 1 ? "" : "s"}:` : "It links to no other notes yet.";
      body.append(text, head);
      if (links.length) {
        const list = document.createElement("ul");
        list.className = "explain-note-links";
        for (const [i, link] of links.entries()) {
          const li = document.createElement("li");
          li.textContent = lines[i];
          list.appendChild(li);
        }
        body.appendChild(list);
      }
      const again = smallButton("ph:speaker-high Read again", "Read it aloud again, or stop", () => speakText(`${words}\n\n${about}`));
      body.appendChild(again);
      card.appendChild(body);
    },
  });
}
