(() => {
  // whiteboard-toolbar.js: the tool rail is a few tab stops, not forty (L269, DESIGN.md "A toolbar of many tools").
  // Each labelled section of `#wb-tool-group` (Select and move, Draw, Shapes, Add, Connect, Edit, Ink) is one stop: Tab
  // lands on the section's current tool (the one last focused, else the one in hand, else the first), the arrows walk the
  // tools of that section, Home and End jump to its first and last, and Tab leaves for the next section. Only buttons
  // rove; a colour field, slider or select in a section keeps its own tab stop and its own arrow keys. The shapes list
  // (`.wb-shape-menu`) is a menu with its own keys and is left alone.
  const GROUP = "wb-tool-group";

  //: Pure: which of `count` tools a key lands on, or -1 for a key that is not ours. `from` is the focused index. Left
  //: and Right always walk (the rail is a row); Up and Down walk only in a column (the side dock), and wrap round.
  function step(count, from, key, vertical) {
    if (count < 1 || from < 0) return -1;
    if (key === "Home") return 0;
    if (key === "End") return count - 1;
    const next = key === "ArrowRight" || (vertical && key === "ArrowDown");
    const back = key === "ArrowLeft" || (vertical && key === "ArrowUp");
    if (next) return (from + 1) % count;
    if (back) return (from - 1 + count) % count;
    return -1;
  }

  //: The roving tools of one section: its buttons that are on screen, outside the shapes list.
  const toolsOf = (section) => [...section.querySelectorAll("button")].filter((b) => !b.closest(".wb-shape-menu") && b.getClientRects().length > 0);

  //: Which tool of the section holds the tab stop: the last one focused, else the one in hand, else the first.
  function currentOf(section, tools) {
    return tools.find((b) => b === section._rovingLast) || tools.find((b) => b.classList.contains("active")) || tools[0];
  }

  function sync(group) {
    for (const section of group.querySelectorAll(".wb-tool-section")) {
      const tools = toolsOf(section);
      const keep = currentOf(section, tools);
      for (const button of section.querySelectorAll("button")) button.tabIndex = button === keep ? 0 : -1;
    }
  }

  function wire() {
    const group = document.getElementById(GROUP);
    if (!group || group._rovingWired) return;
    group._rovingWired = true;
    let queued = false;
    const later = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; sync(group); });
    };
    //: A tool coming or going (the Map and Layout sections follow the board's kind) and the tool in hand changing both
    //: show up as class, hidden or style changes; tabindex is not watched, so the sync does not wake itself.
    new MutationObserver(later).observe(group, { subtree: true, childList: true, attributes: true, attributeFilter: ["class", "hidden", "style"] });
    group.addEventListener("focusin", (e) => {
      const section = e.target.closest?.(".wb-tool-section");
      if (!section || !(e.target instanceof HTMLButtonElement) || e.target.closest(".wb-shape-menu")) return;
      section._rovingLast = e.target;
      sync(group);
    });
    group.addEventListener("keydown", (e) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
      const button = e.target.closest?.("button");
      const section = button?.closest(".wb-tool-section");
      if (!section || button.closest(".wb-shape-menu")) return;
      const vertical = document.getElementById("wb-tools-panel")?.dataset.dock === "side";
      const tools = toolsOf(section);
      const to = step(tools.length, tools.indexOf(button), e.key, vertical);
      if (to < 0) return;
      e.preventDefault();
      e.stopPropagation();
      tools[to].focus();
    });
    sync(group);
  }
  onSurface("board", wire);

  wbFmtState.toolbar = { step, toolsOf, currentOf, sync };
})();
