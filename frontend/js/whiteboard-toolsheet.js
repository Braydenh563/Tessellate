(() => {
  // The phone tools sheet, the docked tool menus and the toggle gestures, carved from initWhiteboard (L634).
  // Wrapped: initWhiteboard calls it once, passing the names it shares; nothing here runs at load.
  function wbInitToolsSheet({ toolGroup, wbToolsOpenerSync, selectWbTool }) {
    // --- the tools as a sheet on a phone ---------------------------------------
    // UI_MODERNISATION_PLAN Phase 11 item 7, "creation tools in a sheet".
    // Measured at 390x844 first: the rail is a 364x56 band under a 364x604
    // canvas, and the band holds 835px of tools scrolled through a 358px
    // window, so 16 of its 31 buttons were on screen at once and the Shapes
    // section showed one of its seven. A row you scroll sideways to find a tool
    // in is not a palette, and it is 56px of a 844px screen either way.
    //
    // What opens is `openSheet`, and what is in it is `#wb-tool-group` itself,
    // moved in and put back on close. That is the whole design: the delegated
    // `[data-tool]` listener above, every section label, every key and the
    // shape menu are the ones that were already there, so a tool added to the
    // rail is in the sheet without anybody remembering to add it twice.
    let wbToolsSheetClose = null;
    let wbToolsWords = [];
    const toolsOpener = document.getElementById("wb-tools-opener");

    function wbSyncToolsOpener() {
      const label = document.getElementById("wb-tools-opener-label");
      if (!label || !toolGroup) return;
      //: The opener says which tool is in hand, because on a phone it is the
      //: only place the rail's own "active" mark can be read.
      const active = toolGroup.querySelector("button[data-tool].active");
      //: The key in brackets is for a keyboard; on a phone it read "Select (V)".
      const name = (active?.getAttribute("aria-label") || active?.title || "").split(" (")[0];
      label.textContent = name ? name.replace(/ tool$/i, "") : "Tools";
    }

    function wbOpenToolsSheet() {
      if (wbToolsSheetClose || !toolGroup || typeof openSheet !== "function") return;
      const home = { parent: toolGroup.parentNode, next: toolGroup.nextSibling };
      toolsOpener?.setAttribute("aria-expanded", "true");
      wbToolsSheetClose = openSheet({
        label: "Tools",
        name: "wb-tools",
        returnFocus: toolsOpener,
        build: (card, close) => {
          const body = document.createElement("div");
          body.className = "wb-tools-palette";
          body.appendChild(toolGroup);
          card.appendChild(body);
          //: **A word under every icon** (audit 1028 U21: 31 icon-only tiles, and
          //: a touch screen has no tooltip to ask). The word is the button's own
          //: name without its key, so the accessible name still contains it (WCAG
          //: 2.5.3), and it is taken out again on close: the rail above 600px is
          //: icons by design.
          for (const button of toolGroup.querySelectorAll("button[aria-label], button[title]")) {
            if (button.textContent.trim()) continue;
            const full = (button.getAttribute("aria-label") || button.title || "").replace(/\s*\(.*$/, "").replace(/ tool$/i, "").trim();
            // A name too long for one line of a tile gets its short word; the short word is still inside the full name.
            const short = {
              "Upload an image onto the board": "Image",
              "Emoji and icons": "Emoji",
              "Lasso select": "Lasso",
              "Sticky note": "Sticky",
              "Straight link": "Straight",
              "Curved link": "Curved",
            };
            const name = short[full] || full;
            if (!name) continue;
            const word = document.createElement("span");
            word.className = "wb-tool-word";
            word.textContent = name;
            button.appendChild(word);
            button.classList.add("wb-tool-worded");
            wbToolsWords.push(word);
          }
          //: Picking a tool is the end of the errand, so the sheet gets out of
          //: the way and the board is there to draw on. The `close` the recipe
          //: hands `build`, not the variable the call assigns afterwards, and
          //: bound on the card so it cannot outlive the sheet.
          //:
          //: **Captured**, because the shape menu's rows stop their own click
          //: from bubbling (they have to: a docked menu is reparented to
          //: `<body>` while it is open, so it cannot rely on reaching
          //: `#wb-tool-group`'s delegated listener). Measured: picking
          //: Rectangle set the tool and left the sheet open over the board it
          //: had just been chosen for.
          card.addEventListener(
            "click",
            (event) => {
              if (event.target.closest("button[data-tool]")) close();
            },
            true
          );
        },
        onClose: () => {
          for (const word of wbToolsWords) {
            word.parentElement?.classList.remove("wb-tool-worded");
            word.remove();
          }
          wbToolsWords = [];
          home.parent.insertBefore(toolGroup, home.next);
          wbToolsSheetClose = null;
          toolsOpener?.setAttribute("aria-expanded", "false");
          wbSyncToolsOpener();
        },
      });
    }

    if (toolsOpener) {
      toolsOpener.addEventListener("click", () => {
        if (wbToolsSheetClose) wbToolsSheetClose();
        else wbOpenToolsSheet();
      });
      //: A window dragged past the band with the sheet open would leave the
      //: rail's own tools inside a dialog the desktop layout has no opener for.
      WB_PHONE.addEventListener("change", () => wbToolsSheetClose?.());
      wbSyncToolsOpener();
      wbToolsOpenerSync.fn = wbSyncToolsOpener;
    }

    // Docked as a sidebar, the toolbar panel scrolls (`overflow-y: auto`, so a
    // tall tool column fits above the canvas), three attempts at this,
    // reported directly each time: (1) CSS-only positioning was clipped by
    // that same overflow (setting only `overflow-y` coerces `overflow-x` to
    // `auto` too, clipping both axes, a real CSS rule, not a bug in that one
    // declaration). (2) `position: fixed` should escape an ancestor's overflow
    // entirely, but this panel's `.glass` class sets `backdrop-filter`, which: 
    // like `transform`/`filter`, creates a new containing block for fixed
    // descendants and traps them right back inside it. (3) toggling the whole
    // panel's `overflow` to `visible` while a menu was open avoided the clip,
    // but also uncapped the tool column's own `max-height` for as long as the
    // menu stayed open, spilling tools out past the panel's bottom edge with
    // no scrollbar to reach them.
    //
    // The only thing that both escapes the clip *and* leaves the scrolling
    // tool column alone is not being inside it: the open menu is reparented to
    // <body> (remembering where it came from, to put it back on close) and
    // positioned from the toggle's own `getBoundingClientRect()`, same as any
    // popover library would. Its own click listener below (rather than relying
    // on bubbling to #wb-tool-group's delegated one) is what makes that safe, 
    // a tool button click needs to work identically whether the menu is
    // sitting in its normal spot (bottom-docked) or reparented to <body>
    // (side-docked, open).
    function wbOpenDockedMenu(menu, toggle) {
      menu.classList.remove("hidden");
      toggle.setAttribute("aria-expanded", "true");
      const panel = toggle.closest(".whiteboard-floating-panel");
      if (panel?.dataset.dock === "side" && !menu._wbHome) {
        menu._wbHome = { parent: menu.parentNode, next: menu.nextSibling };
        document.body.appendChild(menu);
        const toggleRect = toggle.getBoundingClientRect();
        menu.style.position = "fixed";
        menu.style.left = `${toggleRect.right + 8}px`;
        menu.style.top = `${toggleRect.top}px`;
        menu.style.bottom = "auto";
        menu.style.transform = "none";
        menu.style.zIndex = "200";
        // The menu can be bigger than the toggle it opened from, the shape
        // menu's fill/stroke/guide-colour rows run well past the toolbar's
        // own height, and a toggle near the bottom of a tall docked column
        // put `top: toggleRect.top` most of the way down the screen already.
        // Reported directly ("go out of the window"). Clamped against the
        // real viewport rather than just the toggle's position: measured
        // after being placed, since its actual rendered size isn't known
        // until it's in the DOM and visible.
        const margin = 8;
        const menuRect = menu.getBoundingClientRect();
        if (menuRect.right > window.innerWidth - margin) {
          menu.style.left = `${Math.max(margin, window.innerWidth - menuRect.width - margin)}px`;
        }
        if (menuRect.bottom > window.innerHeight - margin) {
          menu.style.top = `${Math.max(margin, window.innerHeight - menuRect.height - margin)}px`;
        }
      }
      wbLiftMenuOffOptionsBar(menu);
    }

    //: **A tool's kind popover and its options bar are one surface, not two
    //: that cross** (INBOX 823, the owner's screenshot: the Line and Arrow
    //: choice drawn under the bar holding Size, Plain and Solid). Measured at
    //: 1440 (`scratchpad/ui-sweeps/toolpop.js`): the popover (z 20) sat 6,232px2
    //: under the bar (z 22) it opens next to. Lifted clear of the bar, an 8px
    //: gap above it, with the individual `translate` property so it composes
    //: with whichever placement the dock gave it.
    function wbLiftMenuOffOptionsBar(menu) {
      menu.style.translate = "";
      const bar = document.getElementById("wb-context");
      if (!bar || bar.classList.contains("hidden")) return;
      const b = bar.getBoundingClientRect();
      const m = menu.getBoundingClientRect();
      if (!b.width || !m.width) return;
      const across = m.left < b.right && m.right > b.left && m.top < b.bottom && m.bottom > b.top;
      if (across) menu.style.translate = `0 ${Math.round(b.top - 8 - m.bottom)}px`;
    }

    function wbCloseDockedMenu(menu, toggle) {
      menu.classList.add("hidden");
      toggle.setAttribute("aria-expanded", "false");
      if (menu._wbHome) {
        menu._wbHome.parent.insertBefore(menu, menu._wbHome.next);
        menu._wbHome = null;
        menu.style.position = "";
        menu.style.left = "";
        menu.style.top = "";
        menu.style.bottom = "";
        menu.style.transform = "";
        menu.style.zIndex = "";
      }
      menu.style.translate = "";
    }

    // Asked for directly: a plain click/tap on the toggle's icon selects the
    // tool it's already showing (matching every other toolbar button, and
    // matching what the toggle looks like it should do). The picker only
    // opens from the caret, a right-click, a double-click, or, touch has
    // neither of those: holding the tool down.
    //: **The caret is a target** (OPEN row 847): it had `pointer-events: none`,
    //: so its own test never matched and a click on it picked the tool. It is
    //: 10px across, so the toggle's right 14px count as the caret too; a
    //: keyboard press (no pointer, `detail` 0) still picks the tool.
    function wbToggleCaretHit(toggle, e) {
      const caret = toggle.querySelector(".wb-shape-caret");
      if (!caret) return false;
      if (e.target.closest(".wb-shape-caret")) return true;
      return e.detail > 0 && e.clientX >= toggle.getBoundingClientRect().right - 14;
    }
    function wbWireToggleGestures(toggle, menu, getLastTool) {
      if (!toggle || !menu) return;
      const picker = toggle.parentElement; // #wb-shape-picker / #wb-select-picker
      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (wbToggleCaretHit(toggle, e)) {
          if (menu.classList.contains("hidden")) wbOpenDockedMenu(menu, toggle);
          else wbCloseDockedMenu(menu, toggle);
        } else {
          //: A press on the control that opened the list shuts it (INBOX 681), and
          //: still picks the tool the button shows.
          if (!menu.classList.contains("hidden")) wbCloseDockedMenu(menu, toggle);
          selectWbTool(getLastTool());
        }
      });
      toggle.addEventListener("dblclick", (e) => {
        e.stopPropagation();
        wbOpenDockedMenu(menu, toggle);
      });
      //: The right-click and the hold open the list and, pressed again, shut it.
      const toggleDocked = () => {
        if (menu.classList.contains("hidden")) wbOpenDockedMenu(menu, toggle);
        else wbCloseDockedMenu(menu, toggle);
      };
      toggle.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleDocked();
      });
      //: The hold, through the app's own `wireLongPress` (navigation.js) rather than
      //: a fourth copy of a 500ms timer with its own cancel set. It also
      //: removes the `suppressClick` latch this carried: the recipe swallows
      //: the click the lift synthesises, which is the thing that latch was
      //: written to survive, and a latch that is only cleared by the *next*
      //: click is a click lost whenever no click follows.
      wireLongPress(toggle, toggleDocked);
      //: **And from the keyboard.** Enter on the toggle picks the tool it shows
      //: (the click above), and the caret, the right-click, the double-click
      //: and the hold are all pointer gestures, so a keyboard had no way into
      //: the shapes at all (menus.js: "nothing opened"). ArrowDown and ArrowUp
      //: are the menu button's own keys (WAI-ARIA): open, and land on the
      //: first or last shape; the menu's own arrows and Escape take it from
      //: there.
      toggle.setAttribute("aria-controls", menu.id);
      //: The roles at boot, never in the markup (the rule `wbStampMenuRoles`
      //: keeps for the top-bar menus): a `role="menu"` with no menuitems in it
      //: is announced as an empty menu, and `wireMenuKeyboard` walks menuitems.
      for (const group of menu.querySelectorAll(".wb-shape-menu-group")) group.setAttribute("role", "group");
      for (const item of menu.querySelectorAll("button[data-tool]")) item.setAttribute("role", "menuitem");
      wireMenuKeyboard(menu, toggle);
      //: `wireMenuKeyboard`'s Escape closes `.action-menu`s, which this is not,
      //: and it stops the key there, so the board's own Escape never saw it
      //: either: measured, Escape left the shapes open (menus.js at 1024).
      menu.addEventListener("keydown", (e) => {
        if (e.key !== "Escape" || menu.classList.contains("hidden")) return;
        wbCloseDockedMenu(menu, toggle);
        toggle.focus({ preventScroll: true });
      });
      toggle.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
        if (!menu.classList.contains("hidden")) return;
        e.preventDefault();
        wbOpenDockedMenu(menu, toggle);
        const items = [...menu.querySelectorAll('[role="menuitem"], button')].filter(
          (b) => !b.disabled && b.getClientRects().length > 0
        );
        (e.key === "ArrowDown" ? items[0] : items[items.length - 1])?.focus();
      });

      // Handled directly rather than relying on the click bubbling up to
      // #wb-tool-group's own delegated listener: once open+side-docked, the
      // menu is reparented to <body> (see wbOpenDockedMenu) and is no longer
      // a descendant of #wb-tool-group at all, so that bubbling path stops
      // reaching it. stopPropagation here is what it is safe now, unlike the
      // old bottom-docked-only version of this handler, this is the only
      // listener that will ever see the click, in either dock mode.
      menu.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-tool]");
        if (btn) {
          e.stopPropagation();
          selectWbTool(btn.dataset.tool);
        }
      });
      document.addEventListener("click", (e) => {
        if (!menu.classList.contains("hidden") && !picker.contains(e.target) && !menu.contains(e.target)) {
          wbCloseDockedMenu(menu, toggle);
        }
      });
    }
    return { wbCloseDockedMenu, wbWireToggleGestures };
  }

  //: The file's surface: what other files call (L634).
  Object.assign(window, { wbInitToolsSheet });
})();
