(() => {
  // whiteboard-map-strip.js: the map's topic strip, its sync with the selected node and the radial ring.
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  function wbSyncToolSurfaces(isMap) {
    wbOutlineAfterSurface();
    //: And the top bar's rows that only a board has (Insert, Frame; View,
    //: Present frames): a map has no frames (decisions 14 and 16).
    for (const section of document.querySelectorAll("#wb-tool-group [data-wb-surface], .wb-board-menu [data-wb-surface]")) {
      section.hidden = section.dataset.wbSurface === (isMap ? "board" : "map");
    }
    //: The Format button too (the owner, 2026-10-19: "useless and empty" on a
    //: map): a topic's look lives on its own toolbar, so the panel had nothing
    //: to show. Its command is already board-only (`surface: "board"`).
    const format = $("wb-format-btn");
    if (format) format.hidden = isMap;
    if (isMap && !$("wb-format")?.classList.contains("hidden")) window.wbFormatClose?.({ restoreFocus: false });
    wbSyncConnectWords(isMap);
    // A tool stays selected across a board switch, so opening a map while the
    // pen was active would leave the pen drawing on a surface whose own button
    // is no longer on screen: a mode with no way out, which is the exact shape
    // of bug the hidden sections are meant to prevent.
    if (isMap && WB_BOARD_ONLY_TOOLS.has(window.currentTool)) wbSelectToolRef?.("select");
    //: The canvas's own name says which keys it answers (INBOX 445): a map's
    //: Tab adds a topic where a board's walks the items.
    document.getElementById("whiteboard-container")?.setAttribute(
      "aria-label",
      isMap
        ? "Mind map. Tab adds a topic under the selected one, Enter adds one beside it, and the arrow keys walk the tree"
        : "Board. Tab moves through the items, the arrow keys move what is selected, and a letter picks a tool"
    );
  }

  //: The map controls that act on the selection, kept honest about whether
  //: there is one.
  //:
  //: Disabled rather than hidden: a control that vanishes teaches nothing, and
  //: what these need to say is "pick a topic first", which the title says while
  //: the button is still there to be read. "Add a top-level topic" is never
  //: disabled, that is the one that has to work on an empty map.
  function wbSyncMapToolState() {
    //: Only Focus reads the selection now. Add a child, add one beside, fold and
    //: the branch colour all left the dock with §12.5: the ring holds the first
    //: three and the strip holds the colour, so the dock keeps what acts on the
    //: *map*. "Add a top-level topic" is never disabled, that is the one that
    //: has to work on an empty map.
    const focus = document.getElementById("wb-map-focus-here");
    if (focus) focus.disabled = !wbSelectedMapNode();
  }

  //: --- the node edit strip (MINDMAP_PLAN.md §12.1 item 2) ---------------------
  //:
  //: Coggle's four are text, link, image and icon. Text and icon are here in
  //: full; link is a web address on the topic, drawn as a marker that opens it;
  //: image is the `image` style, set from a pasted web address through
  //: `POST /links/image` (wbTopicImageFromLink, whiteboard-map-more.js).
  //:
  //: Size and alignment reuse `font_size` and `align`, which a text box already
  //: stores in the same units, rather than inventing a second vocabulary for
  //: the same two ideas. Weight and slant are their own booleans rather than
  //: `**markdown**` written into the label: §12.0 says styling is per node and
  //: in `data`, and a label is already markdown-ish, so a bold *marker* and the
  //: emphasis someone typed would be fighting over the same asterisks.


  //: **Every choice in the topic's bar is one press** (INBOX 610, the owner:
  //: "changing various features ... the popup tool menus (not the radials)"
  //: was "unintuitive"), and **none of them is a pill well** (INBOX 665, the
  //: owner: "clean up or redesign this bit in the mind map popup. also i dont
  //: really like these multi pill elements"). INBOX 610 drew each select as a
  //: `.seg` of words stacked under its name; measured on a themed map at 1440
  //: (`seg665-probe.js`), the Shape door was 333px tall with Box and Fill each
  //: wrapping to two lines of segments (rows of 103px) and the Text door's
  //: icons to three, while "Map" and "As its level (tinted)" sat among the
  //: shapes as if they were one more shape.
  //:
  //: Now each choice is **a row of previews**: an icon-only ghost button per
  //: option, drawing what it makes (a box's corner, the bar down its edge, a
  //: tint, a line's weight and bend; DESIGN.md "A visual choice in a popup"),
  //: beside its name on one line, the way Weight's B and I already were. The
  //: words stay as each button's name and tooltip. "Follow the map" is not a
  //: peer: it is the trailing reset glyph, and the shape the map draws is the
  //: one ringed rather than filled while the topic follows it.
  //:
  //: **The select is still the control.** Every listener in whiteboard.js
  //: reads it, `wbSyncMapStrip` sets it and renames its blank row on a themed
  //: map, `wbSyncMapFill` rewrites its rows; the previews only press it. They
  //: are redrawn from it on its own `change` and on any change to its rows, so
  //: nothing that writes the select has to know they exist.
  const WB_MAP_CHOICE_REDRAWS = [];

  //: What each option looks like, by the select's id and the option's value.
  //: A pin (`WB_MAP_APP_DEFAULT_PINS`) draws what the blank draws on an
  //: unthemed map, so both keys name one glyph. `svg:` is a preview drawn by
  //: `wbMapPickPreview`, `ph:` a Phosphor glyph.
  const WB_MAP_PICK_GLYPHS = {
    "wb-map-align": { "": "ph:magic-wand", auto: "ph:magic-wand", left: "ph:text-align-left", center: "ph:text-align-center", right: "ph:text-align-right" },
    "wb-map-strip-icon": { "": "ph:prohibit" },
    "wb-map-shape": { "": "svg:rounded", rounded: "svg:rounded", pill: "svg:pill", rect: "svg:rect", ellipse: "svg:ellipse", circle: "svg:circle", hexagon: "svg:hexagon", diamond: "svg:diamond", cloud: "svg:cloud", chevron: "svg:chevron", underline: "svg:underline", none: "svg:plain" },
    "wb-map-spine": { "": "svg:bar", solid: "svg:bar", dashed: "svg:bar-dashed", none: "svg:bar-none" },
    "wb-map-fill": { "": "svg:fill-none", none: "svg:fill-none", self: "svg:fill-tint", branch: "svg:fill-branch", solid: "svg:fill-solid" },
    "wb-map-effect": { "": "svg:fill-none", none: "svg:fill-none", shadow: "svg:effect-shadow", glow: "svg:effect-glow" },
    "wb-map-edge-width": { thin: "svg:line-thin", "": "svg:line", normal: "svg:line", thick: "svg:line-thick" },
    "wb-map-edge-shape": { "": "svg:curve", curve: "svg:curve", elbow: "svg:elbow", straight: "svg:straight" },
  };

  //: The previews, on a 20 by 14 box in `currentColor`, so a pressed button's
  //: `--on-accent` and a resting one's ink both reach them with no rule of
  //: their own. Attributes, not `style`: the CSP refuses inline style.
  const WB_MAP_PICK_SHAPES = {
    rounded: [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 2.5 }]],
    pill: [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 4.5 }]],
    rect: [["rect", { x: 2, y: 2.5, width: 16, height: 9 }]],
    ellipse: [["ellipse", { cx: 10, cy: 7, rx: 8, ry: 5 }]],
    circle: [["circle", { cx: 10, cy: 7, r: 5.5 }]],
    hexagon: [["path", { d: "M5 2h10l3.5 5-3.5 5H5L1.5 7z" }]],
    diamond: [["path", { d: "M10 1.5L18.5 7 10 12.5 1.5 7z" }]],
    cloud: [["path", { d: "M6 12a3.5 3.5 0 0 1-.6-7 4.5 4.5 0 0 1 8.6-.6A3.5 3.5 0 1 1 15 12z" }]],
    chevron: [["path", { d: "M2 2.5h11.5l4.5 4.5-4.5 4.5H2z" }]],
    underline: [["path", { d: "M4 6h9" }], ["path", { d: "M2 11h16", "stroke-width": 2.5 }]],
    plain: [["path", { d: "M4 5.5h12M4 8.5h8" }]],
    bar: [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 2 }], ["path", { d: "M4 4.5v5", "stroke-width": 2.5 }]],
    "bar-dashed": [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 2 }], ["path", { d: "M4 4v6", "stroke-width": 2.5, "stroke-dasharray": "1.6 1.4", "stroke-linecap": "butt" }]],
    "bar-none": [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 2 }]],
    "fill-none": [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 2 }]],
    "fill-tint": [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 2, fill: "currentColor", "fill-opacity": 0.35 }]],
    "fill-solid": [["rect", { x: 2, y: 2.5, width: 16, height: 9, rx: 2, fill: "currentColor" }]],
    "fill-branch": [
      ["rect", { x: 1, y: 1, width: 10, height: 6, rx: 1.5, fill: "currentColor", "fill-opacity": 0.35 }],
      ["path", { d: "M6 7v3.5h3" }],
      ["rect", { x: 9, y: 8, width: 10, height: 5, rx: 1.5, fill: "currentColor", "fill-opacity": 0.35 }],
    ],
    //: A box with its shadow below and right of it; a box inside a faint halo.
    "effect-shadow": [
      ["rect", { x: 4, y: 4.5, width: 15, height: 8.5, rx: 2, fill: "currentColor", "fill-opacity": 0.3, stroke: "none" }],
      ["rect", { x: 1.5, y: 2, width: 15, height: 8.5, rx: 2 }],
    ],
    "effect-glow": [
      ["rect", { x: 0.75, y: 0.75, width: 18.5, height: 12.5, rx: 4, "stroke-opacity": 0.35, "stroke-width": 1.5 }],
      ["rect", { x: 3.5, y: 3.5, width: 13, height: 7, rx: 2 }],
    ],
    "line-thin": [["path", { d: "M2 7h16", "stroke-width": 1 }]],
    line: [["path", { d: "M2 7h16", "stroke-width": 2 }]],
    "line-thick": [["path", { d: "M2 7h16", "stroke-width": 3.5 }]],
    curve: [["path", { d: "M2 12C9 12 11 2 18 2" }]],
    elbow: [["path", { d: "M2 12h8V2h8" }]],
    straight: [["path", { d: "M2 12L18 2" }]],
  };

  function wbMapPickPreview(name) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 20 14");
    svg.setAttribute("class", "wb-map-pick-preview");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.5");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    for (const [tag, attrs] of WB_MAP_PICK_SHAPES[name] || []) {
      const part = document.createElementNS(ns, tag);
      for (const [key, value] of Object.entries(attrs)) part.setAttribute(key, String(value));
      svg.appendChild(part);
    }
    return svg;
  }

  //: The glyph for one option: a preview, a Phosphor icon, or (a chosen emoji
  //: in the icon slot, decision 45) the emoji itself.
  function wbMapPickGlyph(selectId, value) {
    const spec = WB_MAP_PICK_GLYPHS[selectId]?.[value]
      || (selectId === "wb-map-strip-icon" && WB_MAP_ICON_NAME.test(value) ? `ph:${value}` : "");
    if (spec.startsWith("svg:")) return wbMapPickPreview(spec.slice(4));
    if (spec.startsWith("ph:")) {
      const glyph = document.createElement("i");
      glyph.className = `ph ph-${spec.slice(3)}`;
      glyph.setAttribute("aria-hidden", "true");
      return glyph;
    }
    const emoji = document.createElement("span");
    emoji.className = "wb-map-pick-emoji";
    emoji.setAttribute("aria-hidden", "true");
    emoji.textContent = value;
    return emoji;
  }

  //: A blank row that means "follow the map" (`data-follow`, written by
  //: `wbSyncMapStrip` and `wbSyncMapFill` while a theme, a level or a filled
  //: branch says what the topic draws) rather than a look of its own.
  function wbMapIsFollow(option) {
    return Boolean(option) && "follow" in option.dataset;
  }

  function wbMapPickRow(select) {
    const row = document.createElement("div");
    row.className = "wb-map-picks";
    //: A row of more than seven previews is a palette, six to a row like the
    //: icon slot's: nine shapes in one run never wrapped and the last two (Cloud,
    //: Plain) sat past the menu's edge, unreachable (measured at 1440: row
    //: 306px in a 220px cell).
    if (select.id === "wb-map-strip-icon" || select.options.length > 7) row.classList.add("is-grid");
    row.setAttribute("role", "group");
    row.setAttribute("aria-label", select.getAttribute("aria-label") || "");
    const press = (value) => {
      if (select.value === value) return;
      select.value = value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      draw();
    };
    //: **The buttons are kept, not rebuilt**, while the select's rows are the
    //: same rows: a rebuilt row would drop the keyboard focus from under the
    //: person pressing. Rebuilt only when the rows themselves change (a themed
    //: map's pin row, the fill's "No fill" row), which is a different set.
    const draw = () => {
      const options = [...select.options];
      const key = options.map((o) => `${wbMapIsFollow(o) ? "~" : ""}${o.value}`).join("|");
      if (row.dataset.rows !== key) {
        row.dataset.rows = key;
        const picks = options.filter((o) => !wbMapIsFollow(o)).map((option) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "ghost small icon-only wb-map-pick";
          button.dataset.value = option.value;
          button.append(wbMapPickGlyph(select.id, option.value));
          button.addEventListener("click", () => press(option.value));
          return button;
        });
        const follow = options.find(wbMapIsFollow);
        if (follow) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "ghost small icon-only wb-map-pick wb-map-pick-follow";
          button.dataset.value = "";
          const glyph = document.createElement("i");
          glyph.className = "ph ph-arrow-counter-clockwise";
          glyph.setAttribute("aria-hidden", "true");
          button.append(glyph);
          button.addEventListener("click", () => press(""));
          picks.push(button);
        }
        row.replaceChildren(...picks);
      }
      const chosen = select.selectedOptions[0];
      const following = !chosen || wbMapIsFollow(chosen);
      const inherits = following ? options.find(wbMapIsFollow)?.dataset.inherits : undefined;
      for (const button of row.children) {
        const isFollow = button.classList.contains("wb-map-pick-follow");
        const option = isFollow ? options.find(wbMapIsFollow)
          : options.find((o) => o.value === button.dataset.value && !wbMapIsFollow(o));
        const words = (option?.textContent || "").trim();
        //: The look a following topic shows is the chosen one (one selected
        //: state); the reset is a way back, pressable only while there is
        //: something to go back from, so it has no pressed state of its own.
        const showsThis = !isFollow && (following ? button.dataset.value === inherits : chosen === option);
        button.classList.toggle("active", showsThis);
        if (isFollow) {
          button.disabled = following;
          button.removeAttribute("aria-pressed");
        } else {
          button.setAttribute("aria-pressed", showsThis ? "true" : "false");
        }
        button.setAttribute("aria-label", words);
        button.title = isFollow ? (following ? words : `Back to the map: ${words.replace(/^As /, "as ")}`) : words;
        //: A hook for the look the map gives a topic that follows it.
        button.classList.toggle("is-inherited", !isFollow && following && button.dataset.value === inherits);
      }
    };
    select.addEventListener("change", draw);
    new MutationObserver(draw).observe(select, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["data-follow", "data-inherits"] });
    WB_MAP_CHOICE_REDRAWS.push(draw);
    draw();
    select.hidden = true;
    select.parentElement.append(row);
    //: Marked on the row that holds it, so the CSS that lays the row out is a
    //: class rather than `:has(> .wb-map-picks)` (tests/test_has_invalidation.py:
    //: a `:has` re-matches on every change below the row).
    select.parentElement.classList.add("has-map-picks");
    if (row.classList.contains("is-grid")) select.parentElement.classList.add("has-map-pick-grid");
    return row;
  }

  //: **The text size is a stepper on the bar** (INBOX 665: the owner's first
  //: screenshot, "S Map M L XL" as a pill well of five on the topic's bar).
  //: DESIGN.md's stepper: a minus, the size it reads now, a plus, one press a
  //: step; S and XL are two presses from M either way, the same as the well's
  //: one-press-anywhere for the sizes beside the one you have, and it is 80px
  //: of the bar where the well was 151. The readout says the size the topic
  //: is drawn at, the map's when it follows the map (ringed, its sentence the
  //: tooltip), so it never reads "M" over a topic the map draws large.
  //: **One scale for the readout** (audit 1028 U28: a root drawn at 22px read
  //: "22px" while its children read "M"). `steps` is the scale, `[{ name, px }]`
  //: smallest first. A size on a step is its name; a size between two is the step
  //: below with a plus ("L+", so it reads as "a little over L" and the minus
  //: button visibly lands on "L"); under the smallest step it is that step.
  //: A property of the stepper, not a shared-scope name (ranked row 37a).
  wbMapSizeStepper.sizeName = function wbMapSizeName(size, steps) {
    if (!steps.length) return `${size}px`;
    const below = [...steps].reverse().find((step) => step.px <= size) || steps[0];
    return below.px === size || size < steps[0].px ? below.name : `${below.name}+`;
  };

  //: **A size in words** (L366): Classic's levels are 17 and 22px, which the
  //: sentences used to say as "17px" beside a bar that reads S, M, L, XL. A size
  //: on the level scale is its word; one off it stays a number.
  wbMapSizeStepper.say = function wbMapSay(size) {
    const row = WB_MAP_LEVEL_ROWS.find((r) => r.key === "font_size");
    return row.options.find(([v]) => Number(v) === Number(size))?.[1] || `${size}px`;
  };

  function wbMapSizeStepper(select) {
    const wrap = document.createElement("div");
    wrap.className = "stepper wb-map-size-stepper";
    wrap.setAttribute("role", "group");
    wrap.setAttribute("aria-label", "Text size");
    const make = (icon, name) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ghost small icon-only stepper-btn";
      setLabel(button, `ph:${icon}`);
      button.setAttribute("aria-label", name);
      return button;
    };
    const minus = make("minus", "Smaller text");
    const plus = make("plus", "Larger text");
    const unit = document.createElement("span");
    unit.className = "stepper-unit wb-map-size-unit";
    //: The size as a number: M is no stored size (the blank) or the pin "0".
    const px = (option) => Number(option.value) || WB_MAP_TEXT_DEFAULT;
    const choices = () => [...select.options].filter((o) => !wbMapIsFollow(o)).sort((a, b) => px(a) - px(b));
    const now = () => {
      const chosen = select.selectedOptions[0];
      if (chosen && !wbMapIsFollow(chosen)) return { size: px(chosen), following: false };
      const drawn = Number(wbMapThemedData(wbSelectedMapNode())?.font_size);
      return { size: drawn > 0 ? drawn : Number(chosen?.dataset.inherits) || WB_MAP_TEXT_DEFAULT, following: true };
    };
    const nameOf = (size) => wbMapSizeStepper.sizeName(size, choices().map((o) => ({ name: o.textContent.trim(), px: px(o) })));
    const step = (dir) => {
      const { size } = now();
      const list = choices();
      const next = dir > 0 ? list.find((o) => px(o) > size) : list.reverse().find((o) => px(o) < size);
      if (!next) return;
      select.value = next.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      draw();
    };
    const draw = () => {
      const { size, following } = now();
      const list = choices();
      const smaller = [...list].reverse().find((o) => px(o) < size);
      const larger = list.find((o) => px(o) > size);
      unit.textContent = nameOf(size);
      unit.classList.toggle("is-inherited", following && Boolean(select.querySelector("option[data-follow]")));
      const said = select.querySelector("option[data-follow]")?.textContent.trim();
      const shown = nameOf(size);
      unit.title = following && said ? said : shown.endsWith("+") ? `Text size ${size}px, a little over ${shown.slice(0, -1)}` : `Text size ${shown}`;
      minus.disabled = !smaller;
      plus.disabled = !larger;
      minus.title = smaller ? `Smaller text (${smaller.textContent.trim()})` : "Already the smallest";
      plus.title = larger ? `Larger text (${larger.textContent.trim()})` : "Already the largest";
    };
    minus.addEventListener("click", () => step(-1));
    plus.addEventListener("click", () => step(1));
    //: Up and down nudge it, the stepper recipe's keys; left and right stay
    //: the toolbar's, which walk the bar.
    wrap.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
      event.preventDefault();
      step(event.key === "ArrowUp" ? 1 : -1);
    });
    wrap.append(minus, unit, plus);
    select.addEventListener("change", draw);
    new MutationObserver(draw).observe(select, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["data-follow", "data-inherits"] });
    WB_MAP_CHOICE_REDRAWS.push(draw);
    draw();
    select.hidden = true;
    select.parentElement.append(wrap);
    return wrap;
  }

  //: A Phosphor name, as against an emoji, in a topic's one icon slot.
  const WB_MAP_ICON_NAME = /^[a-z0-9-]+$/;

  //: **The icon slot's way to every icon and emoji** (decision 43): the Text
  //: menu's quick row keeps its eleven, and this opens the one picker for the
  //: rest. A choice outside the eleven is shown as one more segment, so the row
  //: always says what the topic wears.
  function wbMapSetTopicIcon(node, value) {
    if (!node) return Promise.resolve();
    return wbMapSetNodeStyle(node, { icon: value || null }).then(() => {
      renderWhiteboardNow();
      wbSyncMapStrip(node);
      wbAnnounce(value ? "Icon set." : "Icon removed.");
    });
  }

  function wbMapOpenIconPicker(anchor, node = wbSelectedMapNode()) {
    if (!node) return;
    //: By id at the pick, not the object at the open: a render in between can
    //: replace the objects this tab holds, and a write to the old one is lost.
    const id = node.id;
    pickIconOrEmoji({
      anchor,
      title: "Icon for this topic",
      onPick: (choice) => wbMapSetTopicIcon((wbState.objects || []).find((o) => o.id === id), choice.value),
    });
  }

  //: Keeps one extra row in the quick select for an icon outside its eleven.
  function wbMapIconOption(value) {
    const select = document.getElementById("wb-map-strip-icon");
    if (!select) return;
    const known = [...select.options].some((o) => o.value === value && !("chosen" in o.dataset));
    let chosen = select.querySelector("option[data-chosen]");
    if (!value || known) {
      chosen?.remove();
      return;
    }
    if (chosen?.value === value) return;
    chosen?.remove();
    chosen = document.createElement("option");
    chosen.dataset.chosen = "";
    chosen.value = value;
    chosen.textContent = WB_MAP_ICON_NAME.test(value) ? value.replace(/-/g, " ") : `Emoji ${value}`;
    select.appendChild(chosen);
  }

  function wbWireMapIconMore() {
    const select = document.getElementById("wb-map-strip-icon");
    const row = select?.closest(".wb-menu-row");
    if (!row || row.querySelector(".wb-map-icon-more")) return;
    const more = smallButton("ph:smiley More icons and emoji…", "Every icon and emoji: search, recent and drag", (event) =>
      wbMapOpenIconPicker(event.currentTarget));
    more.classList.add("wb-map-icon-more");
    row.appendChild(more);
  }

  function wbWireMapChoices() {
    wbWireMapIconMore();
    for (const select of document.querySelectorAll("#wb-map-strip select")) {
      if (select.id === "wb-map-text-size") wbMapSizeStepper(select);
      else wbMapPickRow(select);
    }
  }

  // --- several topics at once (INBOX 617) --------------------------------------
  //
  //: **A marquee round topics is a map selection, not a board one** (INBOX 617,
  //: the owner: "on the mind map when selecting a group of nodes, it defaults
  //: to the whiteboard selection and popup menus and right click menus"). With
  //: two or more topics picked, every surface fell back to the board's: the
  //: group box with its eight resize handles and rotate knob (a tidied tree
  //: owns where a topic sits and how it turns, so all nine were grips that
  //: could only fight the layout), the bar's group, align, distribute,
  //: same-size and order rows, and a right-click menu with nothing a mind
  //: mapper does to several topics at once. Measured by
  //: `scratchpad/ui-sweeps/bm1005-mapmulti.js` on the base: a group box with
  //: ten handles, five board groups on the bar, one map row in the menu.
  //:
  //: Now a selection that is only topics, on a map, reads this: no group box
  //: (each topic keeps its own outline), the bar's `mapmulti` group (colour,
  //: bold, task, fold, summarise and delete) and the same five as words in the
  //: right-click menu. A selection that mixes a topic with a card or a drawing
  //: is still the board's, because the board's verbs are the ones that apply
  //: to all of it.
  function wbMapMultiTopics() {
    if (!wbIsMap() || wbMultiSelection.size < 2) return null;
    const topics = [];
    for (const key of wbMultiSelection) {
      const sep = key.indexOf(":");
      if (key.slice(0, sep) !== "object") return null;
      const obj = wbFindItem("object", Number(key.slice(sep + 1)));
      if (!obj || !WB_MAP_KINDS.has(obj.kind)) return null;
      topics.push(obj);
    }
    return topics;
  }

  //: One change to several topics: one undo step for all of them, each saved
  //: in turn (a burst of simultaneous writes races the board's stale-client
  //: recovery, `wbSaveMultiSnapshot` says why), one render at the end.
  //: `patchOf` returns null for a topic the change leaves as it is.
  async function wbMapStyleMany(topics, patchOf) {
    const entries = [];
    const changed = [];
    for (const node of topics) {
      const patch = patchOf(node);
      if (!patch) continue;
      entries.push({ action: "move", kind: "object", id: node.id, before: WB_KIND_INFO.object.payload(node) });
      node.data = { ...node.data, ...patch };
      changed.push(node);
    }
    if (!changed.length) return 0;
    wbPushDragUndo(entries);
    await wbSaveMany(changed.map((item) => ({ kind: "object", item })));
    renderWhiteboardNow();
    return changed.length;
  }

  //: What each of the five does, from the bar and from the menu alike. Each is
  //: a toggle that reads the whole selection: if any picked topic is not yet
  //: bold, Bold makes them all bold; only when every one is does it take bold
  //: off, which is how a word processor's Bold treats a mixed run.
  function wbMapMultiState(topics) {
    const index = wbMapIndex();
    const branches = topics.filter((n) => (index.childrenOf.get(n.id) || []).length);
    const parent = topics[0].parent_id;
    return {
      branches,
      folded: branches.length > 0 && branches.every((n) => n.data?.collapsed),
      bold: topics.every((n) => wbMapThemedData(n).bold),
      tasks: topics.every((n) => n.data?.task === "open" || n.data?.task === "done"),
      siblings: parent != null && index.byId.has(parent) && topics.every((n) => n.parent_id === parent),
    };
  }

  const WB_MAP_MULTI_ACTIONS = {
    async fold(topics) {
      const state = wbMapMultiState(topics);
      if (!state.branches.length) {
        toast("None of these topics has anything under it to fold.");
        return;
      }
      const fold = !state.folded;
      await wbMapStyleMany(state.branches, (n) => (Boolean(n.data?.collapsed) === fold ? null : { collapsed: fold }));
      wbAnnounce(fold ? "Folded." : "Opened.");
    },
    async bold(topics) {
      const want = !wbMapMultiState(topics).bold;
      const fallback = Boolean(wbMapThemeDefault("bold"));
      await wbMapStyleMany(topics, (n) =>
        Boolean(wbMapThemedData(n).bold) === want ? null : { bold: want === fallback ? null : want });
    },
    async task(topics) {
      const make = !wbMapMultiState(topics).tasks;
      await wbMapStyleMany(topics, (n) => {
        const is = n.data?.task === "open" || n.data?.task === "done";
        if (make) return is ? null : { task: "open" };
        return is ? { task: null } : null;
      });
      wbAnnounce(make ? "Tasks, not done yet." : "No longer tasks.");
    },
    async color(topics, value) {
      await wbMapStyleMany(topics, (n) => (n.data?.color === value ? null : { color: value }));
    },
    summary(topics) {
      if (wbMapMultiState(topics).siblings) wbMapSummarise(topics);
      else toast("A summary goes beside topics under one parent: pick siblings to summarise them together.");
    },
  };

  //: The bar's group, set from the selection each time it changes: pressed
  //: states, and Fold and Summarise only when they have something to act on.
  function wbSyncMapMulti(topics) {
    const state = wbMapMultiState(topics);
    const set = (id, fn) => {
      const el = document.getElementById(id);
      if (el) fn(el);
    };
    set("wb-mapmulti-bold", (el) => el.setAttribute("aria-pressed", String(state.bold)));
    set("wb-mapmulti-task", (el) => el.setAttribute("aria-pressed", String(state.tasks)));
    set("wb-mapmulti-fold", (el) => {
      el.classList.toggle("hidden", !state.branches.length);
      el.setAttribute("aria-pressed", String(state.folded));
    });
    set("wb-mapmulti-summary", (el) => el.classList.toggle("hidden", !state.siblings));
    const color = topics.map((n) => n.data?.color).find((c) => /^#[0-9a-f]{6}$/i.test(c || ""));
    set("wb-mapmulti-color", (el) => {
      if (color) el.value = color;
    });
  }

  //: Wired once, from `initWhiteboard`. Each reads the selection when it is
  //: pressed rather than holding one, as the strip's controls do.
  function wbWireMapMulti() {
    const run = (name, ...args) => {
      const topics = wbMapMultiTopics();
      if (topics) WB_MAP_MULTI_ACTIONS[name](topics, ...args);
    };
    for (const name of ["fold", "bold", "task", "summary"]) {
      document.getElementById(`wb-mapmulti-${name}`)?.addEventListener("click", () => run(name));
    }
    document.getElementById("wb-mapmulti-color")?.addEventListener("change", (e) => run("color", e.target.value));
  }

  function wbSyncMapStrip(node) {
    //: **The effective state, not the stored one** (§13e). The arrow button has
    //: always worked this way and says why below; a theme makes it true of the
    //: whole strip, because a control reading the stored field alone would show
    //: "M" over a topic the map draws at 19px.
    const data = wbMapThemedData(node);
    wbMapStripSyncing = true;
    try {
      for (const [id, on] of [
        ["wb-map-bold", data.bold], ["wb-map-italic", data.italic],
        ["wb-map-core", data.core],
      ]) {
        const button = document.getElementById(id);
        if (!button) continue;
        button.classList.toggle("active", Boolean(on));
        button.setAttribute("aria-pressed", on ? "true" : "false");
      }
      //: **The blank option says what it does on a themed map** (§13e). Every
      //: select here stores the app's own default as no value at all, so the
      //: blank row is named after that default: "Rounded", "Line", "M". On a
      //: map whose theme sets the field, choosing it means "follow the map" and
      //: the map draws something else, so a row still labelled "Rounded" is a
      //: control that visibly does nothing, which is the one thing this file's
      //: own comments keep warning about. The label is rewritten to say what it
      //: really does, and put back the moment the map stops theming the field.
      //:
      //: `enhanceSelect` rebuilds its shell from a MutationObserver on the
      //: select's subtree, so changing an option's text reaches the drawn menu
      //: without anything here having to know about the shell.
      const nameBlank = (id, field, pinValue = WB_MAP_APP_DEFAULT_PINS[field]) => {
        const el = document.getElementById(id);
        const blank = el?.querySelector('option[value=""]');
        if (!blank) return;
        if (blank.dataset.appDefault === undefined) blank.dataset.appDefault = blank.textContent;
        const value = wbMapThemeDefault(field);
        //: **And a row for the app's own, while the map says otherwise**
        //: (decision 9). It stores the field's pin (`WB_MAP_APP_DEFAULT_PINS`),
        //: a value, so it beats the theme; it is named exactly what the blank
        //: row says on an unthemed map. Added and removed rather than hidden,
        //: for `wbSyncMapFill`'s reason: `enhanceSelect` rebuilds its menu on a
        //: child-list change, not on an attribute one.
        let pin = el.querySelector("option[data-app-pin]");
        if (value == null) {
          pin?.remove();
          if (blank.textContent !== blank.dataset.appDefault) blank.textContent = blank.dataset.appDefault;
          //: Not following anything: the blank is the app's own look again,
          //: drawn as one more preview (`wbMapPickRow`).
          delete blank.dataset.follow;
          delete blank.dataset.inherits;
          return;
        }
        //: **Following the map** (INBOX 665): the previews draw this row as the
        //: trailing reset, not as a peer, and ring the look the map gives.
        blank.dataset.follow = "";
        if (blank.dataset.inherits !== String(value)) blank.dataset.inherits = String(value);
        if (!pin) {
          pin = document.createElement("option");
          pin.dataset.appPin = "";
          pin.value = String(pinValue);
          pin.textContent = blank.dataset.appDefault;
          blank.after(pin);
        }
        const named = [...el.options].find((o) => o.value === String(value));
        const said = `As the map draws (${(named ? named.textContent : field === "font_size" ? `${value}px` : String(value)).toLowerCase()})`;
        if (blank.textContent !== said) blank.textContent = said;
      };
      for (const [id, field] of [
        ["wb-map-text-size", "font_size"], ["wb-map-align", "align"],
        ["wb-map-shape", "shape"], ["wb-map-spine", "spine"],
        ["wb-map-edge-width", "edge_width"], ["wb-map-edge-shape", "edge_style"],
      ]) nameBlank(id, field);
      //: An effect has no pin of the app's own: its "not here" is `none`.
      nameBlank("wb-map-effect", "effect", "none");
      const setSelect = (id, value) => {
        const el = document.getElementById(id);
        if (!el || el.value === value) return;
        el.value = value;
        el.dispatchEvent(new Event("change", { bubbles: true }));
      };
      //: **M is no stored size at all**, not a number that happens to equal the
      //: stylesheet's. `.wb-map-node` reads at `--text-md`; writing the same
      //: value as a px on the node would pin it there, so a later change to the
      //: type scale would move every map in the app except the nodes somebody
      //: had once set to "medium". The empty option is M for exactly that
      //: reason, and it is also what makes "back to normal" reachable.
      //: What a select shows for a field: its value, with a pin shown as the
      //: pin's own row only while the map themes the field (that row exists
      //: only then) and as the blank row, which draws the same, otherwise.
      const shown = (field) => {
        //: **A topic that was never told follows the map, and says so the same
        //: way for every field** (OPEN row 1370): the blank row, which the pick
        //: row rings as the look the map gives. Setting the themed value onto
        //: the select instead pressed it where the value had an option (a
        //: shape) and rang it where it had none (the 17px size).
        const own = node?.data?.[field];
        if (own === undefined || own === null || own === "") return "";
        const value = data[field];
        if (value === WB_MAP_APP_DEFAULT_PINS[field]) {
          return wbMapThemeDefault(field) == null ? "" : String(value);
        }
        return value == null || value === "" ? "" : String(value);
      };
      //: **A size the strip has no word for gets a row of its own** (L369):
      //: Classic's main topics are 17px, which none of S, M, L, XL is, so the
      //: select could not hold it and the strip rang nothing (the pick row
      //: rings what the select holds). The row is added while the topic uses
      //: that size and removed after, as the icon slot adds its one-off
      //: (`wbMapIconOption`), and named in pixels: its word on the level scale
      //: would collide with the strip's own L.
      const sizeSelect = document.getElementById("wb-map-text-size");
      const wantSize = shown("font_size");
      if (sizeSelect) {
        sizeSelect.querySelector("option[data-off-scale]")?.remove();
        if (wantSize && ![...sizeSelect.options].some((o) => o.value === wantSize)) {
          const extra = document.createElement("option");
          extra.value = wantSize;
          extra.textContent = `${wantSize}px`;
          extra.dataset.offScale = "";
          sizeSelect.append(extra);
        }
      }
      setSelect("wb-map-text-size", wantSize);
      setSelect("wb-map-align", shown("align"));
      wbMapIconOption(data.icon || "");
      setSelect("wb-map-strip-icon", data.icon || "");
      setSelect("wb-map-shape", shown("shape"));
      setSelect("wb-map-spine", shown("spine"));
      setSelect("wb-map-effect", data.effect === "none"
        ? (wbMapThemeDefault("effect") == null ? "" : "none")
        : data.effect || "");
      wbSyncMapFill(node);
      for (const draw of WB_MAP_CHOICE_REDRAWS) draw();
      //: The line into this topic (item 177). A trunk has none, so the group is
      //: put away rather than shown as three controls that write a field
      //: nothing draws: `wbMapEdgeHasArrow` and the rest all read the *child*
      //: of an edge, and a trunk is nobody's child.
      const parented = node.parent_id != null;
      for (const el of document.querySelectorAll("#wb-map-strip [data-wb-map-line]")) {
        //: The shell, where there is one: `enhanceSelect` leaves the real
        //: `<select>` in the DOM at 1px and draws its own opener *beside* it
        //: inside a `.select-shell`, so hiding the select alone would put away
        //: the invisible half and leave the visible one on a trunk that has no
        //: line to style.
        (el.closest(".select-shell") || el).classList.toggle("hidden", !parented);
      }
      if (parented) {
        setSelect("wb-map-edge-width", shown("edge_width"));
        //: The line's shape (§12.5, from the link ring). "Curved" is stored as
        //: no value at all, the same rule "M" and the solid spine follow: the
        //: default has to stay the default so a later change to how a map draws
        //: its lines reaches every map that never chose.
        setSelect("wb-map-edge-shape", shown("edge_style"));
        const dash = document.getElementById("wb-map-edge-dashed");
        if (dash) {
          const on = Boolean(data.edge_dashed);
          dash.classList.toggle("active", on);
          dash.setAttribute("aria-pressed", on ? "true" : "false");
          dash.title = on ? "Draw the line into this topic solid again" : "Dash the line into this topic";
        }
        //: The label's look rows, on the line menu; they read the stored look.
        const size = document.getElementById("wb-map-label-size");
        if (size) size.value = Number(data.edge_label_size) > 0 ? String(data.edge_label_size) : "";
        const ink = document.getElementById("wb-map-label-color");
        if (ink) ink.value = typeof data.edge_label_color === "string" ? data.edge_label_color : "#000000";
        for (const [id, key] of [["wb-map-label-bold", "edge_label_bold"], ["wb-map-label-chip", "edge_label_chip"]]) {
          document.getElementById(id)?.setAttribute("aria-pressed", data[key] ? "true" : "false");
        }
        const arrow = document.getElementById("wb-map-edge-arrow");
        if (arrow) {
          //: The *effective* state, not the stored one: an unset line has a head
          //: when it is a stroke and none when it is a ribbon, so a button
          //: reading the field alone would show "off" on a line that visibly
          //: ends in an arrow.
          const on = wbMapEdgeHasArrow(node);
          arrow.classList.toggle("active", on);
          arrow.setAttribute("aria-pressed", on ? "true" : "false");
          arrow.title = on
            ? "Take the arrowhead off the line into this topic"
            : "Put an arrowhead on the line into this topic";
        }
      }
      const colour = document.getElementById("wb-map-strip-color");
      if (colour) {
        //: **A node carries its colour on its own card, so a trunk can set one
        //: too** (MINDMAP_PLAN.md §12.0). A colour paints the line coming *into*
        //: a node, which a root has none of, and it also paints the card, which
        //: every node has: `wbPaintMapNode` writes `--wb-branch` on all of them
        //: and `.wb-map-node` draws it as the bar down the leading edge. What is
        //: true is that it does not *cascade* from a trunk: the roots' children
        //: start the palette over by design (`wbMapColors`), which is Coggle's
        //: rule. The title says which of the two this press will do. It reads
        //: the colour the node is *actually drawn in*, inherited or its own: a
        //: picker that opens on white over a blue branch is a picker that lies.
        const index = wbMapIndex();
        const isRoot = !(node.parent_id != null && index.byId.has(node.parent_id));
        colour.title = isRoot
          ? "Topic colour: a trunk colours its own card, each branch under it keeps its own"
          : "Branch colour: it carries down to everything under this topic";
        const effective = wbMapColors(index).get(node.id);
        if (effective && /^#[0-9a-f]{6}$/i.test(effective)) colour.value = effective;
      }
    } finally {
      wbMapStripSyncing = false;
    }
  }

  //: **The fill picker says what the topic is drawing**, the rule the rest of
  //: the strip follows. Its blank row is "No fill" on a topic outside any
  //: filled branch and "Filled by its branch" inside one, and only inside one
  //: does "No fill" exist as a choice of its own (`none`): anywhere else it
  //: would be the blank row twice. The option is added and removed rather than
  //: hidden because `enhanceSelect` rebuilds its menu on a child-list change,
  //: not on an attribute one.
  function wbSyncMapFill(node) {
    const el = document.getElementById("wb-map-fill");
    if (!el || !node) return;
    const own = node.data?.fill || "";
    let inherited = false;
    if (!own || own === "none") {
      const index = wbMapIndex();
      let up = index.byId.get(node.parent_id);
      for (let hops = 0; up && hops < 512; hops++) {
        if (up.data?.fill === "branch") {
          inherited = true;
          break;
        }
        up = index.byId.get(up.parent_id);
      }
    }
    //: And its level's (MINDMAP_PLAN.md decision 39): a centre is solid and a
    //: main branch tinted by default, so the blank row says so, and "No fill"
    //: is offered to say otherwise on this one topic.
    const level = !own && !inherited ? wbMapLevelLook(node).fill : null;
    const fromLevel = level === "solid" || level === "tint";
    const blank = el.querySelector('option[value=""]');
    const said = inherited ? "Filled by its branch"
      : fromLevel ? `As its level (${level === "solid" ? "solid" : "tinted"})` : "No fill";
    if (blank && blank.textContent !== said) blank.textContent = said;
    //: The blank follows a filled branch or the level (INBOX 665): the
    //: previews make it the trailing reset and ring the tint or the solid
    //: fill it draws. "No fill" on a topic with neither is a look of its own.
    if (blank && (inherited || fromLevel)) {
      const drawn = fromLevel && level === "solid" ? "solid" : "self";
      blank.dataset.follow = "";
      if (blank.dataset.inherits !== drawn) blank.dataset.inherits = drawn;
    } else if (blank) {
      delete blank.dataset.follow;
      delete blank.dataset.inherits;
    }
    let none = el.querySelector('option[value="none"]');
    const offerNone = inherited || fromLevel || own === "none";
    if (offerNone && !none) {
      none = document.createElement("option");
      none.value = "none";
      none.textContent = "No fill";
      el.appendChild(none);
    } else if (!offerNone && none) {
      none.remove();
    }
    if (el.value !== own) {
      const was = wbMapStripSyncing;
      wbMapStripSyncing = true;
      try {
        el.value = own;
        el.dispatchEvent(new Event("change", { bubbles: true }));
      } finally {
        wbMapStripSyncing = was;
      }
    }
  }

  //: The size a Shift-drag of the resize grip scales from when a node has never
  //: been sized, and the bounds it may scale between (§12.1 item 6, INBOX 610). Measured rather than
  //: assumed: `.wb-map-node` reads at `--text-md`, which computes to 13.6px at
  //: the default root size, so 14 is that rounded to a whole pixel. The strip's
  //: own "M" stores nothing at all instead, see `wbSyncMapStrip`.
  const WB_MAP_TEXT_DEFAULT = 14;
  const WB_MAP_TEXT_MIN = 10;
  const WB_MAP_TEXT_MAX = 44;

  //: One write path for everything the strip and the radial set. Saves, repaints
  //: the node it changed (not the board: a bold toggle is not worth re-binding
  //: every card and sketch, the "glitchy and slow to update" report this file
  //: already carries) and re-places the strip, whose width changes with what it
  //: now says.
  async function wbMapSetNodeStyle(node, patch, { undo = true, rows = null } = {}) {
    if (!node) return;
    //: Every map-topic look goes through here (the strip, the rings, edge
    //: bends, reset to branch), so undo is recorded once here rather than at
    //: each of its dozen callers. The owner: "the undo and redo needs to work
    //: for absolutely everything".
    if (undo) wbPushUndo({ action: "move", kind: "object", id: node.id, before: WB_KIND_INFO.object.payload(node) });
    node.data = { ...node.data, ...patch };
    const el = document.querySelector(`.wb-object[data-id="${node.id}"]`);
    if (el) {
      wbPaintMapNodeStyle(el, node);
      //: Painted outside the render, so the render's paint key (`_wbPaintKey`)
      //: no longer describes what the element shows. Left as it was, an Undo
      //: that put the data back to the key's old value was skipped as "nothing
      //: changed" and the glow stayed on screen (INBOX 1625).
      el._wbPaintKey = null;
    }
    //: A selection passes `rows` and saves them once (BD2: one request, not one per topic).
    if (rows) rows.push({ kind: "object", item: node });
    else await wbSaveObject(node);
    wbUpdateSelectionBar();
  }

  //: **Where a topic points** (§12.1 item 2's "link", moved out of the strip by
  //: §12.5). It is not a look, so it is not the strip's; it is one of the things
  //: the node's own menu offers, beside "add from the library", which is the
  //: other way a topic comes to stand for something else.
  async function wbMapEditLink(node) {
    if (!node) return;
    const current = node.data?.link || "";
    const next = await promptDialog(
      "Where should this topic point? An http, https or mailto address.",
      current,
      { confirmLabel: current ? "Update the link" : "Add the link" }
    );
    //: **An empty answer changes nothing, it does not remove the link.**
    //: `promptDialog` resolves with `""` for Escape, for Cancel and for an
    //: empty field alike (`close("")` on all three paths), so "empty means
    //: remove" would make Escape destructive, which is the one thing Escape
    //: must never be. Removing a link is "Unlink" in the same menu, where a
    //: destructive action can say what it is.
    const trimmed = String(next ?? "").trim();
    if (!trimmed) return;
    if (!WB_MAP_LINK_SCHEMES.test(trimmed)) {
      toast("A topic's link has to be an http, https or mailto address.", "info");
      return;
    }
    await wbMapSetNodeStyle(node, { link: trimmed });
  }

  //: **A picture in a topic** (MINDMAP_PLAN.md §12.1 item 2's fourth, the last
  //: of Coggle's text/link/image/icon).
  //:
  //: **Through `/media/upload`, which is the one upload path this app has.** A
  //: board image, a picture pasted onto a board and a note's own attachment all
  //: already take it, and it is what runs the captioning, the text extraction
  //: and what the orphan sweep in the Library counts: a second route for the
  //: same bytes would be a second place for all three to be forgotten. The node
  //: stores the url it hands back and nothing else, so a topic's picture is the
  //: same upload the Library already lists and the same one `/media` serves.
  //:
  //: In the topic's own menu rather than as a fifth button on the strip, for the
  //: reason §12.5 gives about the link beside it: the strip is how a topic
  //: *looks*, and a picture is what it is. The plan says the same thing from the
  //: other end ("a second node shape, not a fourth button on a strip").
  //: Which topic the file chooser is open for. A module variable rather than a
  //: closure over the node, because the input is the one in the markup
  //: (`#wb-map-picture-input`) rather than one built per click: the file chooser
  //: is modal, so only one of these is ever open, and an id is what survives a
  //: render that replaced the node object in between.
  let wbMapPictureFor = null;

  async function wbMapEditPicture(node) {
    const input = document.getElementById("wb-map-picture-input");
    if (!node || !input) return;
    wbMapPictureFor = node.id;
    //: Cleared before opening, or choosing the same file twice in a row fires
    //: no `change` the second time and the menu looks broken.
    input.value = "";
    input.click();
  }

  //: The upload itself, run from that input's own `change`.
  async function wbMapTakePicture(file) {
    const id = wbMapPictureFor;
    wbMapPictureFor = null;
    const node = id == null ? null : wbMapIndex().byId.get(id);
    if (!file || !node) return;
    if (!file.type || !file.type.startsWith("image/")) {
      toast("That file is not a picture.", "info");
      return;
    }
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("board", "true");
      // The same request `wbPlaceUploadedImage` makes, header and all: the
      // token goes in `X-Auth-Token` because the body is a FormData and
      // `apiJson` leaves the content type to the browser for one.
      const uploaded = await apiJson("/media/upload", {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      await wbMapSetNodeStyle(node, { image: uploaded.url });
      renderWhiteboardNow();
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "add that picture" }), true);
    }
  }

  //: Take the picture off a topic, leaving the upload itself alone: the file is
  //: in the Library, and a topic is one of the places it can appear, not its
  //: home. Deleting the bytes from here would be a delete nobody asked for, in a
  //: menu whose other entries are all about this node.
  async function wbMapRemovePicture(node) {
    if (!node || !node.data?.image) return;
    await wbMapSetNodeStyle(node, { image: null });
    renderWhiteboardNow();
    toast("Picture removed from the topic.");
  }

  //: --- the node radial (MINDMAP_PLAN.md §12.1 item 3) ------------------------
  //:
  //: Coggle's idiom, and the reason §12.1 exists: the controls appear on the
  //: thing you picked. Opened by the same two gestures the board's own context
  //: menu uses (`wbOpenContextMenuFor` hands a map node here), so right-click
  //: and touch-and-hold both reach it without a second gesture to learn.
  //:
  //: Eight slots, in the markup's own order, clockwise from the top. The ring
  //: is not a menu in the ARIA sense and does not claim to be one: a menu is a
  //: list you walk with the arrows, this is a toolbar arranged in a circle, and
  //: `role="toolbar"` is what a screen reader can do something useful with.
  //: (It is also why this adds no hand-built `role="menu"`, which
  //: `tests/test_ui_recipes.py` counts.)


  //: **Show the ring at a point, then slide it back inside the window.**
  //: Both rings are placed from a point with nothing between them and the edge
  //: of the screen: the node ring from the node's own centre, the link ring
  //: from the pointer. A map grows outward, so its newest topics are exactly
  //: the ones nearest an edge, and a ring around one of those lost two or
  //: three of its eight slots off-screen: the control was least reachable
  //: where it was most needed.
  //:
  //: **Why the whole ring moves, rather than the slots being rotated or
  //: reflected into the room that is left.** A ring of eight slots at 45
  //: degrees is its own reflection in both axes and its own rotation by any
  //: multiple of 45, so neither of those changes which directions are covered:
  //: whatever angle the ring is turned through, some slot still points at the
  //: nearest edge, and at 22.5 degrees (the most any rotation can buy) a slot
  //: aimed at the left edge still reaches 68 * cos 22.5 = 63px of the 82px it
  //: needs. Turning the ring also moves every slot away from the position the
  //: person learned it at, to buy 19px. Sliding the whole ring keeps all eight
  //: in their own places and in their own order, and a shift is bounded by the
  //: ring's own reach (82px), which is less than a topic is wide: the ring
  //: still reads as belonging to the node it came from.
  //:
  //: Measured after the ring is shown, not before, which is the ordering
  //: `placeEscapedMenu` in menus.js paid for: a rect read inside a
  //: `display: none` ancestor is all zeroes, and zeroes here would produce a
  //: confident shift from nothing. Measured off the slots rather than off the
  //: ring, for the same reason from the other direction: the ring's own box is
  //: deliberately `width: 0; height: 0` so that it cannot cover the node it
  //: surrounds, so its rect says nothing about where its slots are. The union
  //: of the slots is the honest answer, and it stays honest if the radius, the
  //: slot size or the number of slots ever changes.
  function wbPlaceMapRadial(ring, host, x, y, clear) {
    const margin = 8;
    ring.style.left = `${Math.round(x)}px`;
    ring.style.top = `${Math.round(y)}px`;
    ring.style.removeProperty("--wb-radial-inner");
    ring.style.removeProperty("--wb-radial-outer");
    ring._radial = null;
    ring.classList.remove("hidden");
    const hostRect = host.getBoundingClientRect();
    if (!hostRect.width || !hostRect.height) return { dx: 0, dy: 0 };
    wbSizeMapRadial(ring, hostRect, clear);
    wbFitMapRadialBand(ring);
    let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
    for (const slot of ring.children) {
      const box = slot.getBoundingClientRect();
      if (!box.width && !box.height) continue;
      left = Math.min(left, box.left);
      top = Math.min(top, box.top);
      right = Math.max(right, box.right);
      bottom = Math.max(bottom, box.bottom);
    }
    if (!Number.isFinite(left)) return { dx: 0, dy: 0 };
    //: The window, cut down to the canvas, and then cut down again by the two
    //: panels that float *over* the canvas: on screen is not the same as
    //: reachable. Measured at 1440x900: the host starts at y=128 and the map's
    //: top bar covers 136 to 182 of it, so a trunk near the top of a map (the
    //: common case, that is where a map starts) would have had its upper slots
    //: placed under the bar, which takes the click.
    //:
    //: A panel counts against an edge only when it is a *band* across the
    //: canvas, more than half the host's width for a top or bottom bar and
    //: more than half its height for a side one, because both of these panels
    //: are draggable and one parked in the middle of the board is something to
    //: place a ring beside, not a wall to stay out of. The same rule then
    //: handles the tool panel's own "dock as a sidebar" state without knowing
    //: it exists.
    let loX = Math.max(margin, hostRect.left + margin);
    let hiX = Math.min(window.innerWidth - margin, hostRect.right - margin);
    let loY = Math.max(margin, hostRect.top + margin);
    let hiY = Math.min(window.innerHeight - margin, hostRect.bottom - margin);
    for (const id of ["wb-topbar", "wb-tools-panel"]) {
      const panel = document.getElementById(id);
      if (!panel || panel.hidden || panel.classList.contains("hidden")) continue;
      const bar = panel.getBoundingClientRect();
      if (!bar.width || !bar.height) continue;
      const midY = hostRect.top + hostRect.height / 2;
      const midX = hostRect.left + hostRect.width / 2;
      if (bar.width > hostRect.width / 2) {
        if (bar.bottom < midY) loY = Math.max(loY, bar.bottom + margin);
        else if (bar.top > midY) hiY = Math.min(hiY, bar.top - margin);
      }
      if (bar.height > hostRect.height / 2) {
        if (bar.right < midX) loX = Math.max(loX, bar.right + margin);
        else if (bar.left > midX) hiX = Math.min(hiX, bar.left - margin);
      }
    }
    //: Right edge first and left edge second, so that on a canvas narrower
    //: than the ring (which no real viewport is, 164px against 390, but a
    //: split pane could be) the ring is pinned to the edge a reader starts
    //: from rather than half off both sides.
    let dx = 0, dy = 0;
    if (right > hiX) dx = hiX - right;
    if (left + dx < loX) dx = loX - left;
    if (bottom > hiY) dy = hiY - bottom;
    if (top + dy < loY) dy = loY - top;
    if (dx) ring.style.left = `${Math.round(x + dx)}px`;
    if (dy) ring.style.top = `${Math.round(y + dy)}px`;
    return { dx, dy };
  }

  //: **The ring's hole holds the node, and the ring holds in the canvas.**
  //:
  //: The ring is a pie menu now (the owner, 2026-09-24: the buttons were "just
  //: buttons sitting ontop of" the ring), so the question this answers changed
  //: from "how far out do the tiles go" to "how big is the hole". The answer is
  //: the node: half its on-screen diagonal plus a little room, so the whole
  //: topic sits inside the hole with its corners clear. The band beyond it is a
  //: fixed thickness (`--wb-radial-band`, an icon over one line of word), so
  //: the outer edge follows.
  //:
  //: Three limits. A floor, so a one-word topic still gets sectors wide enough
  //: for their words (at the floor six 60 degree sectors are 84px across their
  //: middle); a ceiling, so a topic resized to 400px wide gets a ring round its
  //: middle rather than a hoop across the board; and the canvas, whose shorter
  //: side the whole ring must fit inside (at 390 the canvas is 364px wide,
  //: which caps the hole at 118px, above the 108px a default topic asks for).
  //: Past the ceiling or the canvas the ring overlaps the topic's ends, which is
  //: the lesser harm than a ring that does not fit.
  //:
  //: Without `clear` (the line ring, opened at the pointer) the stylesheet's
  //: own edges stand: there is no topic to hold.
  function wbMapRadialPx(ring, name) {
    const raw = getComputedStyle(ring).getPropertyValue(name).trim();
    const value = parseFloat(raw);
    if (!Number.isFinite(value)) return 0;
    if (raw.endsWith("rem")) return value * (parseFloat(getComputedStyle(document.documentElement).fontSize) || 16);
    return value;
  }

  function wbSizeMapRadial(ring, hostRect, clear) {
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const band = wbMapRadialPx(ring, "--wb-radial-band") || 4.5 * rem;
    const floor = wbMapRadialPx(ring, "--wb-radial-inner") || 2.75 * rem;
    let inner = floor;
    if (clear && clear.w > 0 && clear.h > 0) {
      const holds = Math.hypot(clear.w / 2, clear.h / 2) + 6;
      inner = Math.min(Math.max(holds, 3.5 * rem), 10 * rem);
    }
    const fits = Math.min(hostRect.width, hostRect.height) / 2 - 8 - band;
    inner = Math.round(Math.max(Math.min(inner, fits), Math.min(floor, fits)));
    ring._radial = { inner, outer: inner + band };
    //: What the band fit may spend if the words need a thicker band: the
    //: canvas's own limit on the outer edge, and the hole's floor.
    ring._radialRoom = { floor, maxOuter: Math.min(hostRect.width, hostRect.height) / 2 - 8 };
    ring.style.setProperty("--wb-radial-inner", `${inner}px`);
    ring.style.setProperty("--wb-radial-outer", `${inner + band}px`);
  }

  //: One sector's outline in its own square (the ring's diameter, centre at
  //: `outer, outer`): the outer arc clockwise from `a0` to `a1`, then the inner
  //: arc back. `gap` is half the hairline between neighbours, taken off each
  //: side as a *length* at each radius rather than as one angle, so the
  //: divider is as wide at the rim as at the hole; `rim` comes off both radii
  //: so the band's own colour edges the ring.
  function wbMapRadialSectorPath(inner, outer, a0, a1, gap = 0, rim = 0) {
    const c = outer;
    const ro = outer - rim, ri = inner + rim;
    const go = gap / ro, gi = gap / ri;
    const pt = (r, a) => `${(c + r * Math.cos(a)).toFixed(2)} ${(c + r * Math.sin(a)).toFixed(2)}`;
    const large = a1 - a0 - 2 * go > Math.PI ? 1 : 0;
    const largeIn = a1 - a0 - 2 * gi > Math.PI ? 1 : 0;
    return `M ${pt(ro, a0 + go)} A ${ro} ${ro} 0 ${large} 1 ${pt(ro, a1 - go)}`
      + ` L ${pt(ri, a1 - gi)} A ${ri} ${ri} 0 ${largeIn} 0 ${pt(ri, a0 + gi)} Z`;
  }

  //: **Cut the ring into its sectors** (the name is the one INBOX 410 gave it,
  //: when the band was cut to its tiles; now the sectors are cut to the band).
  //: Clockwise from the top, in the markup's own order, each sector centred on
  //: its direction: six at 60 degrees round a topic, three at 120 on a line.
  //: Each slot gets its wedge as a clip path and the middle of its wedge as the
  //: point its face is drawn at, both in its own square, which is the ring's
  //: square; `_sector` keeps the angles for the edge a focused sector wears and
  //: for the menu More opens beside it.
  function wbFitMapRadialBand(ring) {
    let { inner, outer } = ring._radial || {
      inner: wbMapRadialPx(ring, "--wb-radial-inner") || 44,
      outer: (wbMapRadialPx(ring, "--wb-radial-inner") || 44) + (wbMapRadialPx(ring, "--wb-radial-band") || 56),
    };
    ring._radial = { inner, outer };
    const slots = [...ring.querySelectorAll(".wb-map-radial-slot")];
    const n = slots.length;
    if (!n) return;
    const step = (2 * Math.PI) / n;
    //: **Thick enough for the widest word, measured** (INBOX 421 a: "the items
    //: like "add beside" and "cross-link" are very close to the edges (inner
    //: and outer) of the radial and arent centered nicely"). The stylesheet's
    //: 4.5rem is the floor, not the answer: on a slanted sector a word lies
    //: across the band, not along it, so its reach towards both arcs is its
    //: width times the sine of the slant plus its height times the cosine. A
    //: fixed band left "Add beside" and "Cross-link" 1.4px from both arcs at
    //: the same time (mapradialfit.js), and a guessed bigger one only moves
    //: the problem to the next longer word or a larger text size.
    const size = wbMapRadialLabelSizes(slots);
    const { inner: fitInner, outer: fitOuter } = wbMapRadialBandFor(ring, inner, outer, size, step);
    if (fitOuter !== outer || fitInner !== inner) {
      inner = fitInner;
      outer = fitOuter;
      ring._radial = { inner, outer };
      ring.style.setProperty("--wb-radial-inner", `${inner}px`);
      ring.style.setProperty("--wb-radial-outer", `${outer}px`);
    }
    //: The band's middle, which is where each label's box is centred: the
    //: face is a fixed box centred on this point and its icon and word are
    //: centred in the face, so the drawn label's middle is the sector's.
    const mid = (inner + outer) / 2;
    slots.forEach((slot, i) => {
      const at = -Math.PI / 2 + i * step;
      const a0 = at - step / 2, a1 = at + step / 2;
      slot.style.clipPath = `path("${wbMapRadialSectorPath(inner, outer, a0, a1, 0.75, 1)}")`;
      slot.style.setProperty("--wb-sector-x", `${(outer + mid * Math.cos(at)).toFixed(1)}px`);
      slot.style.setProperty("--wb-sector-y", `${(outer + mid * Math.sin(at)).toFixed(1)}px`);
      slot._sector = { a0, a1, at, inner, outer };
    });
    wbMarkMapRadialSector(ring, null);
  }

  //: The drawn size of each sector's label: the union of its icon and its
  //: word, which the face centres. Zero for a ring not yet shown (a rect read
  //: under `display: none` is all zeroes), which the band fit then ignores.
  function wbMapRadialLabelSizes(slots) {
    return slots.map((slot) => {
      let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
      for (const el of slot.querySelectorAll(".wb-map-radial-face > *")) {
        const box = el.getBoundingClientRect();
        if (!box.width && !box.height) continue;
        l = Math.min(l, box.left); t = Math.min(t, box.top);
        r = Math.max(r, box.right); b = Math.max(b, box.bottom);
      }
      return Number.isFinite(l) ? { w: r - l, h: b - t } : { w: 0, h: 0 };
    });
  }

  //: How far a label box centred at `rc` along `at` stays from the inner arc,
  //: the outer arc and the two dividers of a sector `step` wide. The box point
  //: nearest the centre measures the inner arc, its farthest corner the outer
  //: one; the dividers are measured from the corners (the box is convex), as a
  //: signed distance so a corner past a divider counts as negative.
  function wbMapRadialClearance(inner, outer, rc, at, step, { w, h }) {
    const cx = rc * Math.cos(at), cy = rc * Math.sin(at);
    const xs = [cx - w / 2, cx + w / 2], ys = [cy - h / 2, cy + h / 2];
    const near = Math.hypot(Math.min(Math.max(0, xs[0]), xs[1]), Math.min(Math.max(0, ys[0]), ys[1]));
    let far = 0, div = Infinity;
    for (const x of xs) for (const y of ys) {
      far = Math.max(far, Math.hypot(x, y));
      for (const [a, side] of [[at - step / 2, 1], [at + step / 2, -1]]) {
        div = Math.min(div, side * (x * Math.sin(a) - y * Math.cos(a)) * -1);
      }
    }
    return Math.min(near - inner, outer - far, div);
  }

  //: The narrowest band at or above the stylesheet's that keeps every label
  //: `WB_MAP_RADIAL_CLEAR` from both arcs and both dividers with each label
  //: centred on its sector's middle radius. When the thicker band would pass
  //: the canvas, the hole gives the room back down to its floor first (a
  //: ring whose words touch its edges is worse than one that overlaps a
  //: long topic's ends); past that the best band the canvas allows stands.
  const WB_MAP_RADIAL_CLEAR = 10;
  function wbMapRadialBandFor(ring, inner, outer, sizes, step) {
    if (!sizes.some((s) => s.w && s.h)) return { inner, outer };
    //: One pixel over the clearance, for the hairline and the rim the sectors
    //: give up to the band (`wbMapRadialSectorPath`'s gap and rim).
    const ok = (ri, ro) => sizes.every((s, i) => !s.w || wbMapRadialClearance(ri, ro, (ri + ro) / 2, -Math.PI / 2 + i * step, step, s) >= WB_MAP_RADIAL_CLEAR + 1);
    const room = ring._radialRoom;
    const band0 = outer - inner;
    let band = band0;
    while (!ok(inner, inner + band) && band < band0 + 96) band += 1;
    if (room && inner + band > room.maxOuter) {
      const ri = Math.min(inner, Math.max(Math.min(room.floor, inner), Math.round(room.maxOuter - band)));
      return { inner: ri, outer: Math.max(ri + band0, Math.min(ri + band, room.maxOuter)) };
    }
    return { inner, outer: inner + band };
  }

  //: **The edge on the sector the keyboard is on.** An outline on a clipped
  //: button is clipped with everything else outside its wedge, so the ring
  //: draws the focused sector's edge itself: one SVG path over the sectors,
  //: made the first time and rewritten per focus. Hover gets the fill alone,
  //: which is what a pointer needs; the keyboard gets the fill and the edge.
  function wbMarkMapRadialSector(ring, slot) {
    let svg = ring.querySelector(".wb-map-radial-edge");
    if (!svg) {
      svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "wb-map-radial-edge");
      svg.setAttribute("aria-hidden", "true");
      svg.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "path"));
      ring.insertBefore(svg, ring.querySelector(".wb-map-radial-caption"));
    }
    const s = slot?._sector;
    const path = svg.firstChild;
    if (!s) {
      path.removeAttribute("d");
      return;
    }
    const size = s.outer * 2;
    svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
    path.setAttribute("d", wbMapRadialSectorPath(s.inner, s.outer, s.a0, s.a1, 0.75, 2));
    svg.classList.toggle("wb-map-radial-edge-danger", slot.classList.contains("wb-map-radial-danger"));
  }

  //: A sector's own box in the window, from its angles rather than from the
  //: button's rect, which is the whole ring's square for every sector. Sampled
  //: along both arcs and at both edges, which is exact enough for placing a
  //: menu beside it and cannot be fooled by the clip.
  function wbMapRadialSectorRect(slot) {
    const s = slot?._sector;
    const ring = slot?.closest(".wb-map-radial");
    if (!s || !ring) return null;
    const o = ring.getBoundingClientRect();
    if (!o.width && !o.height && !o.left && !o.top) return null;
    let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
    for (let k = 0; k <= 12; k++) {
      const a = s.a0 + ((s.a1 - s.a0) * k) / 12;
      for (const r of [s.inner, s.outer]) {
        const x = o.left + r * Math.cos(a), y = o.top + r * Math.sin(a);
        left = Math.min(left, x); right = Math.max(right, x);
        top = Math.min(top, y); bottom = Math.max(bottom, y);
      }
    }
    return { left, top, right, bottom, width: right - left, height: bottom - top, outward: Math.cos(s.at) < 0 ? "left" : "right" };
  }

  //: **Arrows walk the ring** (the brief: arrows move between sectors, Enter
  //: activates, Escape closes). Right and Down go clockwise, Left and Up
  //: back, Home and End to the first and last; a disabled sector is stepped
  //: over. `role="toolbar"` already promises this: a toolbar is walked with
  //: the arrows and left with Tab.
  function wbMapRadialStep(ring, from, delta) {
    const slots = [...ring.querySelectorAll(".wb-map-radial-slot")];
    const live = slots.filter((s) => !s.disabled);
    if (!live.length) return null;
    if (delta === "first") return live[0];
    if (delta === "last") return live[live.length - 1];
    let i = slots.indexOf(from);
    for (let k = 0; k < slots.length; k++) {
      i = (i + delta + slots.length) % slots.length;
      if (!slots[i].disabled) return slots[i];
    }
    return null;
  }

  //: The sector nearest a direction, for the first arrow pressed with the ring
  //: open and the focus still on the canvas: Up goes to the top sector, Right to
  //: the one nearest three o'clock, and so on, which is what pointing with a key
  //: at a pie means.
  function wbMapRadialToward(ring, key) {
    const want = { ArrowUp: -Math.PI / 2, ArrowRight: 0, ArrowDown: Math.PI / 2, ArrowLeft: Math.PI }[key];
    if (want === undefined) return null;
    let best = null, bestGap = Infinity;
    for (const slot of ring.querySelectorAll(".wb-map-radial-slot")) {
      if (slot.disabled || !slot._sector) continue;
      const d = Math.abs(Math.atan2(Math.sin(slot._sector.at - want), Math.cos(slot._sector.at - want)));
      if (d < bestGap - 1e-6) { best = slot; bestGap = d; }
    }
    return best;
  }

  //: The node whose ring is open wears a class while it is open, because two of
  //: its own hover controls (add a branch, add a topic beside) are two of the
  //: ring's eight slots and sit inside the ring's circle. Two buttons for one
  //: action, one of them under the ring, is the clutter the report was about.
  function wbMarkMapRadialNode(id) {
    for (const el of document.querySelectorAll(".wb-object.wb-radial-open")) {
      el.classList.remove("wb-radial-open");
    }
    if (id == null) return;
    document.querySelector(`.wb-object[data-id="${id}"]`)?.classList.add("wb-radial-open");
  }

  function wbCloseMapRadial() {
    const ring = document.getElementById("wb-map-radial");
    if (!ring || ring.classList.contains("hidden")) return;
    //: A sector that held the focus is about to be hidden, and a hidden
    //: element hands the focus to `body`, where no board key reaches: the board
    //: takes it back, so the next Tab or Enter still acts on the topic.
    if (ring.contains(document.activeElement)) document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
    ring.classList.add("hidden");
    wbMapRadialFor = null;
    wbSyncMapRadialAlt(false);
    wbMarkMapRadialNode(null);
    wbUpdateSelectionBar();
  }

  //: Alt held turns the two add slots into the two remove slots (Coggle). The
  //: swap is drawn, not just honoured: a modifier that changes what a button
  //: does without saying so is the "secret" this file's own space-pan comment
  //: warns about.
  function wbSyncMapRadialAlt(alt) {
    const pairs = [
      ["wb-radial-child", alt
        ? ["ph-trash", "Remove branch", "Remove this branch: this topic and everything under it"]
        : ["ph-arrow-elbow-down-right", "Add child", "Add a branch off this topic (Tab). Hold Alt to remove the branch instead"]],
      ["wb-radial-sibling", alt
        ? ["ph-minus-circle", "Remove topic", "Remove this topic only: its branches move up to its parent"]
        : ["ph-arrow-down", "Add beside", "Add a topic beside this one (Enter). Hold Alt to remove this topic and keep its branch"]],
    ];
    for (const [id, [icon, word, title]] of pairs) {
      const button = document.getElementById(id);
      if (!button) continue;
      button.classList.toggle("wb-map-radial-danger", alt);
      button.title = title;
      //: The drawn word opens the name (WCAG 2.5.3, OPEN 1400).
      button.setAttribute("aria-label", `${word}: ${title.split(".")[0]}`);
      //: The half of "how they work" that a label cannot carry: these two slots
      //: are two actions each, and the modifier that swaps them was only ever
      //: stated in a tooltip's second sentence. The ring's caption reads this.
      button.dataset.altHint = alt ? "Let go of Alt to add instead" : "Hold Alt to remove instead";
      //: The drawn word too, not only the icon and the tooltip (§12.5): a slot
      //: that says "Add child" while Alt is held and the icon is a bin is worse
      //: than one that says nothing.
      const name = button.querySelector(".wb-map-radial-name");
      if (name) name.textContent = word;
      const glyph = button.querySelector("i");
      if (glyph) glyph.className = `ph ${icon}`;
    }
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbSyncToolSurfaces, wbSyncMapToolState, wbMapSizeStepper, WB_MAP_ICON_NAME, wbMapSetTopicIcon, wbWireMapChoices, wbMapMultiTopics, wbMapMultiState, WB_MAP_MULTI_ACTIONS, wbSyncMapMulti, wbWireMapMulti, wbSyncMapStrip, wbSyncMapFill, WB_MAP_TEXT_DEFAULT, WB_MAP_TEXT_MIN, WB_MAP_TEXT_MAX, wbMapSetNodeStyle, wbMapEditLink, wbMapEditPicture, wbMapTakePicture, wbMapRemovePicture, wbPlaceMapRadial, wbMarkMapRadialSector, wbMapRadialSectorRect, wbMapRadialStep, wbMapRadialToward, wbMarkMapRadialNode, wbCloseMapRadial, wbSyncMapRadialAlt });
})();
