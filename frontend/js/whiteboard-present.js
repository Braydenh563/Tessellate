(() => {
  // whiteboard-present.js: presenting a board's frames: the slide walk, the laser pointer and the bar (decision 16).
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: --- Presenting a board's frames (WHITEBOARD_PLAN decision 16) -------------
  //:
  //: tldraw's and Miro's shape: the frames are the slides. View, Present frames
  //: fills the window with the board, hides every control but one small bar, and
  //: shows the frames one at a time in reading order (rows from the top, left to
  //: right in a row: the Tab walk's order), each zoomed to fill the screen with
  //: its title. The arrow keys, Space, Page Up and Page Down, Home and End walk;
  //: Escape or the bar's X ends it and puts the board back as it was. It is a
  //: view: no key edits the board while it runs. A board with no frame says how
  //: to make one rather than presenting nothing.

  //: Rows first: two frames whose tops are closer than half the shorter one's
  //: height sit in one row, read left to right; rows are read top to bottom.
  function wbFramesInOrder() {
    const frames = (wbState.objects || []).filter((o) => o.kind === "frame").sort((a, b) => a.y - b.y);
    const rows = [];
    for (const frame of frames) {
      const row = rows[rows.length - 1];
      if (row && Math.abs(frame.y - row[0].y) < Math.min(frame.height, row[0].height) / 2) row.push(frame);
      else rows.push([frame]);
    }
    const reading = rows.flatMap((row) => row.sort((a, b) => a.x - b.x));
    //: **A page number wins** (decision 22): the sidebar's Pages tab writes
    //: `page` on every frame when it reorders them; a frame without one (made
    //: since) follows the numbered ones in reading order.
    if (!reading.some((f) => Number.isFinite(f.data?.page))) return reading;
    const at = new Map(reading.map((f, i) => [f, i]));
    const page = (f) => (Number.isFinite(f.data?.page) ? f.data.page : Infinity);
    return reading.slice().sort((a, b) => page(a) - page(b) || at.get(a) - at.get(b));
  }

  //: The steps: a board's frames, or a map's branches (MINDMAP_PLAN decision
  //: 21). Each step answers its box live (a title's strip included), so a
  //: frame deleted or a branch folded mid-run is followed, not remembered.
  function wbPresentSteps() {
    if (!wbIsMap()) {
      return wbFramesInOrder().map((f) => {
        const frame = () => (wbState.objects || []).find((o) => o.id === f.id);
        return {
          title: () => wbFrameTitle(frame()),
          box: () => {
            const now = frame();
            return now ? { x: now.x, y: now.y - 28, w: now.width, h: now.height + 28 } : null;
          },
        };
      });
    }
    if (wbMapBuild.on) return wbMapBuild.steps;
    return wbStudy.on ? wbMapStudySteps() : wbMapPresentSteps();
  }

  function wbStartPresenting() {
    const steps = wbPresentSteps();
    if (!steps.length) {
      toast(wbIsMap() ? "This map has no topics to present." : "Add a frame first (F): each frame is one step of the presentation.");
      return;
    }
    const host = document.getElementById("library-view-whiteboard");
    const container = document.getElementById("whiteboard-container");
    if (!host || !container) return;
    clearWbSelection();
    wbPresent = {
      steps,
      at: 0,
      wasFull: host.classList.contains("wb-fullscreen"),
      camera: d3.zoomTransform(container),
      focus: document.activeElement,
    };
    toggleWhiteboardFullscreen(true);
    wbPresentLaserButton();
    host.classList.add("wb-presenting");
    document.getElementById("wb-present-bar")?.classList.remove("hidden");
    //: After the chrome has gone, so the frame is fitted to the room it has.
    requestAnimationFrame(() => {
      wbPresentShow(0);
      document.getElementById("wb-present-next")?.focus({ preventScroll: true });
    });
  }

  function wbPresentShow(index) {
    if (!wbPresent) return;
    const steps = wbPresent.steps.filter((step) => step.box());
    if (!steps.length) {
      wbStopPresenting();
      return;
    }
    wbPresent.steps = steps;
    const at = Math.max(0, Math.min(steps.length - 1, index));
    wbPresent.at = at;
    //: A mode's own part of the step (Build up shows its topics) before the caption and the fit.
    steps[at].enter?.();
    wbPresentCaption(at, steps);
    //: **The page number, typeable** (INBOX 1694 b, value-field.js): a small field before the page picker, "2" then
    //: "of 5: Title". Type a number and Enter to go there; Escape puts it back. Built on a presentation's first step,
    //: removed with it; the picker beside it is the list of every page with its title.
    if (!wbPresent.pageField) {
      const slot = document.getElementById("wb-present-count");
      const host = document.createElement("span");
      host.className = "wb-present-page";
      slot?.before(host);
      wbPresent.pageField = valueField(host, {
        value: at + 1,
        min: 1,
        max: () => wbPresent?.steps.length || 1,
        label: "Page number",
        onCommit: (n) => wbPresentShow(n - 1),
      });
    }
    wbPresent.pageField.set(at + 1);
    const box = steps[at].box();
    const container = document.getElementById("whiteboard-container");
    const rect = container.getBoundingClientRect();
    const pad = Math.min(48, rect.width * 0.05);
    //: And the bar keeps its own strip at the foot, so it never sits on the frame.
    const bar = document.getElementById("wb-present-bar");
    const foot = bar ? bar.offsetHeight + 16 : 0;
    const w = Math.max(1, box.w), h = Math.max(1, box.h);
    const room = rect.height - pad * 2 - foot;
    const k = Math.max(0.1, Math.min(4, (rect.width - pad * 2) / w, room / h));
    const cx = box.x + w / 2, cy = box.y + h / 2;
    const target = d3.zoomIdentity.translate(rect.width / 2 - k * cx, pad + room / 2 - k * cy).scale(k);
    const reduce = reducedMotionWanted();
    const sel = d3.select(container);
    (reduce ? sel : sel.transition().duration(320)).call(wbZoom.transform, target);
  }

  //: The bar's caption for a step, set before the frame is fitted because a
  //: caption that wraps makes the bar taller and the frame keeps clear of it.
  //: The caption is the page picker (INBOX 1425): one `kebabMenu` whose opener
  //: shows "N of M: title" centred with a caret and whose rows are every step,
  //: so a click jumps to any page. The menu is built once per presentation and
  //: its rows are refreshed here, so the opener (and the focus on it) survives
  //: a step. A caption the bar's width would cut (a study question on a phone,
  //: a study note's answer) takes a line of its own above the buttons instead,
  //: whole on hover as well.
  function wbPresentCaption(at, steps) {
    const slot = document.getElementById("wb-present-count");
    const bar = document.getElementById("wb-present-bar");
    const prev = document.getElementById("wb-present-prev");
    const next = document.getElementById("wb-present-next");
    if (prev) prev.disabled = at === 0;
    if (next) next.disabled = at === steps.length - 1;
    if (wbStudy.on) wbMapStudySyncBar();
    if (!slot) return;
    //: The page number is the bar's typeable field (`wbPresentPageField`); the opener says the rest.
    const caption = `of ${steps.length}: ${steps[at].title()}`;
    const items = steps.map((step, i) => ({
      label: `${i + 1}. ${step.title()}`,
      run: () => wbPresentShow(i),
    }));
    const fresh = kebabMenu(items, "Go to a page");
    let wrap = slot.querySelector(":scope > .menu-wrap");
    if (!wrap) {
      wrap = fresh;
      const first = wrap.querySelector(":scope > button");
      first.id = "wb-present-pick";
      first.classList.remove("icon-only", "kebab-opener");
      first.classList.add("wb-present-pick");
      first.replaceChildren();
      const label = document.createElement("span");
      label.className = "wb-present-pick-title";
      const caret = document.createElement("i");
      caret.className = "ph ph-caret-up wb-present-pick-caret";
      caret.setAttribute("aria-hidden", "true");
      first.append(label, caret);
      //: Opened, the menu lands on the current page rather than the first.
      first.addEventListener("click", () => {
        const row = document.querySelector(".action-menu:not(.hidden) .menu-item[aria-current]");
        row?.focus({ preventScroll: true });
        row?.scrollIntoView({ block: "nearest" });
      });
      //: Kept, as the laser menu's is: an open menu is parked on the body, and
      //: a row's `run` steps the page (and lands here) before it is back, so a
      //: lookup through the wrap finds nothing and the rows stay the old page's.
      wrap.pickMenu = wrap.querySelector(".action-menu");
      slot.replaceChildren(wrap);
    } else {
      wrap.pickMenu.replaceChildren(...fresh.querySelector(".action-menu").children);
    }
    const opener = wrap.querySelector(":scope > button");
    const words = opener.querySelector(".wb-present-pick-title");
    words.textContent = caption;
    opener.title = caption;
    opener.setAttribute("aria-label", `${caption}. Go to a page`);
    const rows = [...wrap.pickMenu.querySelectorAll(".menu-item")];
    if (rows[at]) {
      rows[at].setAttribute("aria-current", "step");
      rows[at].classList.add("wb-present-pick-row");
      const mark = document.createElement("i");
      mark.className = "ph ph-check wb-present-pick-check";
      mark.setAttribute("aria-hidden", "true");
      rows[at].append(mark);
    }
    //: A board's frame title keeps the cell's fixed width and ellipsis, so the
    //: arrows sit at the same x on every page (INBOX K32); only a study note
    //: (long question or answer) takes a line of its own.
    slot.classList.remove("is-wide");
    if (bar) bar.style.flexWrap = "";
    if (!bar || !wbStudy.on || words.scrollWidth <= words.clientWidth) return;
    slot.classList.add("is-wide");
    bar.style.flexWrap = "wrap";
  }

  //: **A laser pointer while presenting** (canvasdepth; Excalidraw's and
  //: tldraw's): L or the bar's button; the pointer leaves a short trail that
  //: fades by CSS (`wb-laser-fade`), so no frame loop runs for it, and it
  //: draws nothing on the board. Beside the button a small `kebabMenu` sets
  //: how it looks (INBOX 1577): the trail on or off, the ring's pulse on or off (1628), a look (dot, trail, ring,
  //: spotlight) and a colour from the board's palette, kept in this browser
  //: like the board's other display choices (`prefs`, key `wb-laser`). The
  //: looks animate with transform and opacity only, and under reduced motion
  //: the trail is off whatever was chosen.
  const wbLaser = {
    looks: { dot: "Dot", trail: "Trail", ring: "Ring", spotlight: "Spotlight" },
    prefs() {
      const saved = prefs.json("wb-laser", {});
      return {
        trail: saved.trail !== false,
        //: The ring's pulse, a switch like the trail (the owner, 2026-11-04, INBOX 1628).
        pulse: saved.pulse !== false,
        look: Object.hasOwn(wbLaser.looks, saved.look) ? saved.look : "trail",
        colour: Object.hasOwn(WB_RUN_SWATCHES, saved.colour) ? saved.colour : "red",
      };
    },
    set(change) {
      prefs.setJSON("wb-laser", { ...wbLaser.prefs(), ...change });
      wbLaser.apply();
      wbLaser.menu();
    },
    //: The layer wears the look and the colour as a data attribute and a custom
    //: property, so a change repaints the head and the tail without rebuilding.
    apply() {
      const layer = document.getElementById("wb-laser-layer");
      if (!layer) return;
      const { look, colour, pulse } = wbLaser.prefs();
      layer.dataset.look = look;
      layer.dataset.pulse = pulse ? "on" : "off";
      layer.style.setProperty("--wb-laser", colour === "red" ? "var(--error)" : WB_RUN_SWATCHES[colour]);
    },
    //: Rows are rebuilt on each change so the chosen ones carry a check, the way
    //: the page picker marks its current page.
    menu() {
      const button = document.getElementById("wb-present-laser");
      if (!button) return;
      const now = wbLaser.prefs();
      const items = [
        { label: now.trail ? "Trail: on" : "Trail: off", group: "trail", run: () => wbLaser.set({ trail: !now.trail }) },
        //: Only the ring pulses, so the row shows while the ring is the look.
        ...(now.look === "ring" ? [{ label: now.pulse ? "Pulse: on" : "Pulse: off", group: "trail", run: () => wbLaser.set({ pulse: !now.pulse }) }] : []),
        ...Object.entries(wbLaser.looks).map(([key, name]) => ({ label: name, group: "look", run: () => wbLaser.set({ look: key }) })),
        {
          label: "Colour",
          group: "colour",
          items: Object.keys(WB_RUN_SWATCHES).map((key) => ({
            label: key[0].toUpperCase() + key.slice(1),
            run: () => wbLaser.set({ colour: key }),
          })),
        },
      ];
      const fresh = kebabMenu(items, "Laser pointer options");
      let wrap = document.getElementById("wb-present-laser-menu");
      if (!wrap) {
        wrap = fresh;
        wrap.id = "wb-present-laser-menu";
        wrap.querySelector(":scope > button").id = "wb-present-laser-opener";
        //: Kept, because an open menu is moved to the body and a row's `run`
        //: fires before it is back, so a lookup through the wrap finds nothing.
        wrap.laserMenu = wrap.querySelector(".action-menu");
        button.after(wrap);
      } else {
        wrap.laserMenu.replaceChildren(...fresh.querySelector(".action-menu").children);
      }
      const chosen = new Set([wbLaser.looks[now.look], now.colour[0].toUpperCase() + now.colour.slice(1)]);
      for (const row of wrap.laserMenu.querySelectorAll(".menu-item")) {
        if (!chosen.has(row.textContent.trim())) continue;
        row.setAttribute("aria-current", "true");
        const mark = document.createElement("i");
        mark.className = "ph ph-check wb-present-pick-check";
        mark.setAttribute("aria-hidden", "true");
        row.append(mark);
      }
    },
  };

  function wbPresentLaserButton() {
    if (document.getElementById("wb-present-laser")) return;
    const button = smallButton("ph:cursor-click", "Laser pointer (L)", () => {});
    button.id = "wb-present-laser";
    button.setAttribute("aria-pressed", "false");
    document.getElementById("wb-present-end")?.before(button);
    wbLaser.menu();
  }

  function wbPresentLaser(on = null) {
    const container = document.getElementById("whiteboard-container");
    const show = on ?? !container?.classList.contains("wb-laser-on");
    if (!container || (show && !wbPresent)) return;
    //: The tool's cursor is set inline (`updateWbCursor`), so it is kept and
    //: swapped inline too: the dot is the pointer while the laser is on.
    if (show && !container.classList.contains("wb-laser-on")) {
      wbPresentLaser.cursor = container.style.cursor;
      container.style.cursor = "none";
    } else if (!show && container.classList.contains("wb-laser-on")) {
      container.style.cursor = wbPresentLaser.cursor || "";
    }
    container.classList.toggle("wb-laser-on", show);
    document.getElementById("wb-present-laser")?.setAttribute("aria-pressed", String(show));
    let layer = document.getElementById("wb-laser-layer");
    if (show && !layer) {
      layer = document.createElement("div");
      layer.id = "wb-laser-layer";
      layer.className = "wb-laser-layer";
      layer.setAttribute("aria-hidden", "true");
      const head = document.createElement("span");
      head.className = "wb-laser-head";
      head.hidden = true;
      layer.append(head);
      document.body.append(layer);
      wbLaser.apply();
      container.addEventListener("pointermove", wbLaserTrail);
      container.addEventListener("pointerleave", wbLaserLeave);
    }
    if (!show && layer) {
      container.removeEventListener("pointermove", wbLaserTrail);
      container.removeEventListener("pointerleave", wbLaserLeave);
      layer.remove();
    }
    if (on === null) wbAnnounce(show ? "Laser pointer on." : "Laser pointer off.");
  }

  function wbLaserTrail(event) {
    const layer = document.getElementById("wb-laser-layer");
    if (!layer) return;
    //: The head is the pointer itself: one element that follows every move and
    //: is never faded, so it cannot flicker when the pointer slows or stops.
    const head = layer.firstElementChild;
    if (head?.classList.contains("wb-laser-head")) {
      head.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
      head.hidden = false;
    }
    //: reduced motion has no trail, whatever was chosen: the head alone shows
    //: where the pointer is.
    if (!wbLaser.prefs().trail || reducedMotionWanted()) return;
    const dot = document.createElement("span");
    dot.className = "wb-laser-dot";
    dot.style.left = `${event.clientX}px`;
    dot.style.top = `${event.clientY}px`;
    dot.addEventListener("animationend", () => dot.remove(), { once: true });
    // Under reduced motion no animation runs, so animationend never fires.
    setTimeout(() => dot.remove(), 800);
    layer.append(dot);
    while (layer.childElementCount > 48) layer.firstElementChild.remove();
  }

  function wbLaserLeave() {
    const head = document.querySelector("#wb-laser-layer .wb-laser-head");
    if (head) head.hidden = true;
  }

  function wbStopPresenting() {
    if (!wbPresent) return;
    const { wasFull, camera, focus } = wbPresent;
    wbPresent = null;
    wbPresentLaser(false);
    wbMapEndStudy();
    wbMapBuild.end();
    closeActionMenus();
    document.getElementById("wb-present-count")?.replaceChildren();
    document.querySelector(".wb-present-page")?.remove();
    document.getElementById("library-view-whiteboard")?.classList.remove("wb-presenting");
    document.getElementById("wb-present-bar")?.classList.add("hidden");
    if (!wasFull) toggleWhiteboardFullscreen(false);
    //: Back to where the board was looked at from before.
    const container = document.getElementById("whiteboard-container");
    if (container && camera) d3.select(container).call(wbZoom.transform, camera);
    //: Only an element on screen: Present starts from a menu item, in a menu that
    //: has closed by now, and focusing it left focus on `<body>` (boardfix-1108).
    const back = focus && document.contains(focus) && focus.getClientRects().length ? focus : container;
    (back ?? container)?.focus?.({ preventScroll: true });
  }

  //: While it runs the keys are the presentation's, ahead of the board's own
  //: (capture, on the window): an arrow walks the slides rather than nudging,
  //: and a tool letter does nothing at all rather than changing a hidden tool.
  window.addEventListener("keydown", (event) => {
    if (!wbPresent) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    //: A number being typed in the bar's page field keeps its own keys (value-field.js).
    if (event.target.closest?.(".value-field")) return;
    const step = {
      ArrowRight: 1, ArrowDown: 1, PageDown: 1, " ": 1, Enter: 1,
      ArrowLeft: -1, ArrowUp: -1, PageUp: -1,
    }[event.key];
    if (event.key === "Tab") return;
    //: While the page picker is open its own keys rule (arrows, Home, End, Enter,
    //: Esc); the presentation's shortcuts wait, and Esc closes the menu first.
    const picker = document.querySelector(".action-menu:not(.hidden)");
    if (picker && document.getElementById("wb-present-count")?.contains(picker._escapedOpener || picker.parentElement)) {
      if (event.key === "Escape" && !picker.contains(event.target)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeActionMenus();
        document.getElementById("wb-present-pick")?.focus({ preventScroll: true });
      }
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    //: Enter and Space on a focused bar button press that button, here rather
    //: than by the browser: the board's own Space (pan) would cancel it.
    const button = (event.key === "Enter" || event.key === " ") && event.target.closest?.("#wb-present-bar button");
    if (button) {
      if (!button.disabled) button.click();
      return;
    }
    //: Studying, Enter and Space draw the answer before they move on.
    const asking = wbStudy.on && !document.getElementById("wb-study-show")?.classList.contains("hidden");
    if (asking && (event.key === "Enter" || event.key === " ")) {
      wbMapStudyShow();
      return;
    }
    if (event.key === "Escape") wbStopPresenting();
    else if (event.key === "l" || event.key === "L") wbPresentLaser();
    else if (event.key === "Home") wbPresentShow(0);
    else if (event.key === "End") wbPresentShow(wbPresent.steps.length - 1);
    else if (step) wbPresentShow(wbPresent.at + step);
  }, true);

  //: The bar's three, by delegation: the script can run before the bar is parsed.
  document.addEventListener("click", (event) => {
    const button = event.target.closest?.("#wb-present-bar button");
    if (!button || !wbPresent) return;
    if (button.id === "wb-present-prev") wbPresentShow(wbPresent.at - 1);
    else if (button.id === "wb-present-next") wbPresentShow(wbPresent.at + 1);
    else if (button.id === "wb-present-end") wbStopPresenting();
    else if (button.id === "wb-present-laser") wbPresentLaser();
    else if (button.id === "wb-study-show") wbMapStudyShow();
    else if (button.id === "wb-study-knew") wbMapStudyMark(true);
    else if (button.id === "wb-study-missed") wbMapStudyMark(false);
  });

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbFramesInOrder, wbStartPresenting, wbPresentShow, wbStopPresenting });
})();
