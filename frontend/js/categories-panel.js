// Lazily loaded (LAZY_MODULES.categories in app.js): the Manage categories
// panel and its merge, split, delete and new-category flows run only when
// the panel or a category's menu is used, so they stay off the boot
// scripts' gzip budget (tests/test_static_compression.py).

let manageCategoriesRedraw = null;

//: **The panel, redesigned** (the owner, of the first draft: "needs some ui
//: redesign and modernisation/professionalisation refinement ... can you
//: also do those button redesigns like the ai assistant panel in the
//: documents editor"). The head is DESIGN.md's dialog head (the Documents AI
//: assistant's): the title, its '?' beside it, a ghost icon Close at the
//: right. One line of description, then one tool row: a filter field and
//: New category. The categories are a grid of quiet rows (the colour dot,
//: the name, its count as quiet text and a ghost ⋯ that shows on hover or focus,
//: always on touch), with a roving focus: arrows and Home/End move, Space
//: selects, Enter shows the category's notes, F2 renames, Delete deletes,
//: and the context-menu key or Shift+F10 opens the ⋯. Selecting rows raises
//: a sticky footer to merge or delete them together. The card is sized to
//: its content up to its cap and the list is its one scroller.
async function openManageCategories(focusName = null) {
  //: The sort, the look-alike merges and the count button are the tag
  //: manager's (INBOX 504), so its module comes first.
  //: The librarian's tidy proposals (WORLD_CLASS_PLAN section 17 row 2),
  //: asked once per opening: merges by name or meaning, and categories empty
  //: for thirty days.
  const [, , tidy] = await Promise.all([
    loadCategories(),
    ensureModule("tagManager"),
    apiJson("/tidy-proposals", { silent: true }).catch(() => null),
  ]);
  openSheet({
    label: "Manage categories",
    name: "categories",
    onClose: () => { manageCategoriesRedraw = null; },
    build: (card, close) => {
      card.classList.add("manage-cat-card");
      manageCatHead(card, close);
      const sub = document.createElement("p");
      sub.className = "muted manage-cat-sub";
      sub.textContent = "Rename, merge, split or delete categories. Your notes are always kept.";
      const helpBody = document.createElement("div");
      helpBody.className = "help-body hidden";
      helpBody.id = "manage-cat-help";
      helpBody.setAttribute("role", "dialog");
      helpBody.setAttribute("aria-label", "About managing categories");
      for (const line of [
        "Merge into folds one category into another: all its notes move across. Select several with Space to merge or delete them together.",
        `Split moves some of a category's notes into a new one. Pick them yourself, or have groups suggested, by their tags or by ${aiNameNow()}, and review them first.`,
        "Colour picks the dot a category wears on its notes, the graph and the timeline. Automatic goes back to a colour chosen from its name. Select several to colour them together.",
        "Sort by name, by how many notes a category holds, or by the one used most recently. Empty shows the categories with no notes. Categories that look like one (Recipe and recipes) are offered as one merge above the list, and the count after a name shows its notes.",
        "Delete asks where its notes should go. Nothing you write is ever deleted here, and every change can be undone.",
        "To move particular notes, tick them in the list and choose Move to, or drag a note's category label onto another category in the sidebar.",
        "Keys: arrows move, Space selects, Enter shows the notes, F2 renames, Delete deletes.",
      ]) {
        const p = document.createElement("p");
        p.textContent = line;
        helpBody.appendChild(p);
      }
      const tools = document.createElement("div");
      tools.className = "manage-cat-tools";
      const filter = document.createElement("input");
      filter.type = "search";
      filter.className = "manage-cat-filter";
      filter.placeholder = "Filter categories";
      filter.setAttribute("aria-label", "Filter categories");
      //: A search field says so: a leading magnifier, and a clear that shows
      //: once there is something to clear (the owner: "the filter has no
      //: search icon").
      const search = document.createElement("span");
      search.className = "manage-cat-search";
      const glass = document.createElement("i");
      glass.className = "ph ph-magnifying-glass manage-cat-search-icon";
      glass.setAttribute("aria-hidden", "true");
      const clear = smallButton("ph:x", "Clear the filter", () => {
        filter.value = "";
        filter.dispatchEvent(new Event("input"));
        filter.focus();
      });
      clear.classList.add("manage-cat-clear", "hidden");
      clear.setAttribute("aria-label", "Clear the filter");
      search.append(glass, filter, clear);
      const create = smallButton("ph:plus New category", "Make an empty category to move notes into", () => createCategoryFromPanel());
      const state = {
        selected: new Set(),
        active: focusName,
        filter: "",
        sort: manageStored("manage-categories-sort", "name"),
        rare: false,
        hideSuggest: false,
        tidy: tidy || { merges: [], empty: [] },
      };
      tools.append(search, ...manageListControls({
        sortKey: "manage-categories-sort",
        state,
        rareLabel: "Empty",
        rareTitle: "Show only the categories with no notes",
        redraw,
      }), create);
      const suggest = document.createElement("div");
      suggest.className = "manage-suggest hidden";
      suggest.setAttribute("role", "region");
      suggest.setAttribute("aria-label", "Categories that look alike");
      state.suggestBox = suggest;
      const list = document.createElement("ul");
      list.className = "manage-cat-list";
      //: A grid, not a listbox (INBOX 433): an option may hold nothing
      //: interactive, and each row carries its ⋯ (axe-core's
      //: nested-interactive, WCAG 4.1.2, counted 7). A grid's cell may: the
      //: rows are selected as rows, the first cell is the roving stop.
      list.setAttribute("role", "grid");
      list.setAttribute("aria-multiselectable", "true");
      list.setAttribute("aria-label", "Categories");
      const footer = document.createElement("div");
      footer.className = "manage-cat-footer hidden";
      footer.setAttribute("role", "region");
      footer.setAttribute("aria-label", "Selected categories");
      card.append(sub, helpBody, tools, suggest, list, footer);
      initHelpToggles(card);
      function redraw() {
        drawManageCategoryRows(list, footer, state);
      }
      manageCategoriesRedraw = redraw;
      filter.addEventListener("input", () => {
        state.filter = filter.value.trim().toLowerCase();
        clear.classList.toggle("hidden", !filter.value);
        redraw();
      });
      //: Down from the filter walks into the list.
      filter.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          list.querySelector(".manage-cat-main")?.focus();
        }
      });
      wireManageCategoryKeys(list, state, redraw);
      redraw();
      //: After the sheet's own first-button focus, which would land on the '?'.
      const start = focusName ? list.querySelector(`[data-category="${CSS.escape(focusName)}"] > .manage-cat-main`) : null;
      requestAnimationFrame(() => (start || filter).focus());
    },
  });
}

//: The doc-ai head built into the sheet's own head: the '?' goes beside the
//: title, and the Close moves into the icon group as a ghost icon.
function manageCatHead(card, close) {
  const head = card.querySelector(".sheet-head");
  if (!head) return;
  head.classList.add("dialog-head");
  const help = document.createElement("button");
  help.type = "button";
  help.className = "icon-only ghost small dialog-head-btn";
  help.setAttribute("data-help-for", "manage-cat-help");
  help.setAttribute("aria-controls", "manage-cat-help");
  help.setAttribute("aria-expanded", "false");
  help.title = "About managing categories";
  help.setAttribute("aria-label", "About managing categories");
  const helpIcon = document.createElement("i");
  helpIcon.className = "ph ph-question";
  helpIcon.setAttribute("aria-hidden", "true");
  help.appendChild(helpIcon);
  const closeButton = head.querySelector(".sheet-close");
  closeButton?.classList.add("dialog-head-btn");
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  if (closeButton) actions.appendChild(closeButton);
  head.querySelector(".sheet-title")?.after(help);
  head.appendChild(actions);
  void close;
}

function drawManageCategoryRows(list, footer, state) {
  //: The focus is on a row's first cell (or its ⋯); the row says which.
  const hadFocus = list.contains(document.activeElement)
    ? document.activeElement.closest("[data-category]")?.dataset.category || null
    : null;
  list.replaceChildren();
  const countOf = (name) => categoryMeta.get(name)?.count || 0;
  const recent = state.sort === "recent" ? manageRecent((entry) => [entry.category || "Uncategorised"]) : null;
  const shown = manageSorted(
    [...categoryMeta.keys()].filter(
      (name) => (!state.filter || name.toLowerCase().includes(state.filter)) && (!state.rare || countOf(name) === 0)
    ),
    state.sort,
    countOf,
    recent
  ).map((name) => categoryMeta.get(name));
  for (const name of [...state.selected]) if (!categoryMeta.has(name)) state.selected.delete(name);
  if (state.suggestBox) drawCategoryTidy(state.suggestBox, state);
  if (!shown.length) {
    const none = document.createElement("li");
    none.className = "muted manage-cat-empty";
    none.setAttribute("role", "row");
    const cell = document.createElement("span");
    cell.setAttribute("role", "gridcell");
    cell.textContent = state.filter ? "No category matches that." : state.rare ? "Every category holds a note." : "No categories yet.";
    none.appendChild(cell);
    list.appendChild(none);
  }
  const current = shown.some((meta) => meta.name === (hadFocus || state.active)) ? (hadFocus || state.active) : shown[0]?.name;
  for (const meta of shown) {
    const li = document.createElement("li");
    li.className = "manage-cat-row";
    li.dataset.category = meta.name;
    li.setAttribute("role", "row");
    li.setAttribute("aria-selected", String(state.selected.has(meta.name)));
    //: The row's stop and its name: the dot, the name and the count, one
    //: cell, so arrowing down the grid reads "Work, 3 notes" per row.
    const main = document.createElement("span");
    main.className = "manage-cat-main";
    main.setAttribute("role", "gridcell");
    main.tabIndex = meta.name === current ? 0 : -1;
    const dot = document.createElement("span");
    dot.className = "manage-cat-dot";
    paintCategoryDot(dot, meta.name);
    dot.setAttribute("aria-hidden", "true");
    const name = document.createElement("span");
    name.className = "manage-cat-name";
    name.textContent = meta.name;
    name.title = meta.name;
    main.setAttribute("aria-label", `${meta.name}, ${nounCount(meta.count, "note")}`);
    main.append(dot, name, manageCountButton(meta.count, () => showCategoryNotes(meta.name)));
    li.appendChild(main);
    if (meta.name !== "Uncategorised") {
      const menu = kebabMenu(categoryMenuItems(meta, { inPanel: true }), `Actions for ${meta.name}`, { vertical: true });
      menu.classList.add("manage-cat-menu");
      menu.setAttribute("role", "gridcell");
      menu.addEventListener("click", (event) => event.stopPropagation());
      menu.addEventListener("keydown", (event) => {
        event.stopPropagation();
        //: Left from the ⋯ goes back to the row's first cell, as Right
        //: came here (`wireManageCategoryKeys`).
        if (event.key === "ArrowLeft" && event.target === menu.querySelector(":scope > button")) {
          event.preventDefault();
          main.focus();
        }
      });
      li.appendChild(menu);
    } else {
      const spacer = document.createElement("span");
      spacer.className = "manage-cat-spacer";
      spacer.setAttribute("role", "gridcell");
      li.appendChild(spacer);
    }
    //: A click selects (with Ctrl or Shift it adds to the selection); a
    //: double click shows the category's notes.
    li.addEventListener("click", (event) => {
      if (meta.name === "Uncategorised") return showCategoryNotes(meta.name);
      if (!(event.ctrlKey || event.metaKey || event.shiftKey)) {
        const only = state.selected.size === 1 && state.selected.has(meta.name);
        state.selected.clear();
        if (!only) state.selected.add(meta.name);
      } else if (state.selected.has(meta.name)) state.selected.delete(meta.name);
      else state.selected.add(meta.name);
      state.active = meta.name;
      drawManageCategoryRows(list, footer, state);
      list.querySelector(`[data-category="${CSS.escape(meta.name)}"] > .manage-cat-main`)?.focus();
    });
    li.addEventListener("dblclick", () => showCategoryNotes(meta.name));
    list.appendChild(li);
  }
  if (hadFocus) list.querySelector(`[data-category="${CSS.escape(hadFocus)}"] > .manage-cat-main`)?.focus();
  drawManageCategoryFooter(footer, state, () => drawManageCategoryRows(list, footer, state));
}

//: The assignments a click on the sidebar's row makes (`renderSidebar`), for
//: the panel's Enter and the category chip's "Show notes in" (INBOX 447 (5)).
//: `clearSearch` empties the box first: from a card that is showing a search
//: or a tag, "show this category" means this category, not its overlap.
//: **The librarian's tidy proposals** (WORLD_CLASS_PLAN section 17 row 2):
//: from `GET /tidy-proposals`, which finds names alike or alike in meaning,
//: never merges away a name the person chose by renaming, and drops a pair
//: someone answered "Not these" to, for good; and categories empty for thirty
//: days. Nothing moves until Merge or Remove is pressed. In this panel rather
//: than Settings, where the look-alike merges already were (INBOX 504).
function drawCategoryTidy(box, state) {
  box.replaceChildren();
  const merges = (state.tidy.merges || []).filter((m) => categoryMeta.has(m.keep.name) && categoryMeta.has(m.merge.name));
  const empty = (state.tidy.empty || []).filter((c) => categoryMeta.has(c.name) && !(categoryMeta.get(c.name).count > 0));
  const show = (merges.length || empty.length) && !state.hideSuggest;
  box.classList.toggle("hidden", !show);
  if (!show) return;
  const head = document.createElement("p");
  head.className = "manage-suggest-head";
  setLabel(head, `ph:broom Tidy suggestions (${merges.length + empty.length})`);
  const later = smallButton("Not now", "Hide these suggestions until the panel is opened again", () => {
    state.hideSuggest = true;
    box.classList.add("hidden");
  });
  later.classList.add("manage-suggest-later");
  head.appendChild(later);
  box.appendChild(head);
  const row = (text, title, ...buttons) => {
    const el = document.createElement("div");
    el.className = "manage-suggest-row";
    const names = document.createElement("span");
    names.className = "manage-suggest-names";
    names.textContent = text;
    names.title = title;
    el.append(names, ...buttons);
    box.appendChild(el);
  };
  for (const m of merges.slice(0, 4)) {
    const text = `${m.merge.name} into ${m.keep.name}`;
    const merge = smallButton("ph:arrows-merge Merge", `Fold ${text}`, () =>
      mergeCategoriesFromPanel([categoryMeta.get(m.merge.name)], categoryMeta.get(m.keep.name))
    );
    merge.setAttribute("aria-label", `Merge ${text}`);
    const no = smallButton("Not these", "Never suggest this pair again", async () => {
      //: The person's own choice: a refusal says so and keeps the row.
      const pair = { a: m.keep.name, b: m.merge.name };
      const ok = await apiJson("/tidy-proposals/dismiss", { method: "POST", body: JSON.stringify(pair) }).then(
        () => {
          pushRoutePairUndo("Dismissed a merge suggestion", ["/tidy-proposals/undismiss", "POST", pair], ["/tidy-proposals/dismiss", "POST", pair], async () => {
            state.tidy = (await apiJson("/tidy-proposals", { silent: true }).catch(() => null)) || state.tidy;
            drawCategoryTidy(box, state);
          });
          return true;
        },
        (error) => {
          toast(error.message, true);
          return false;
        }
      );
      if (!ok) return;
      state.tidy.merges = state.tidy.merges.filter((x) => x !== m);
      drawCategoryTidy(box, state);
    });
    row(text, `${text}: ${m.why}`, merge, no);
  }
  for (const c of empty.slice(0, 4)) {
    const remove = smallButton("ph:trash Remove", `Remove the empty category ${c.name}`, () => deleteCategoryFromPanel(categoryMeta.get(c.name)));
    remove.setAttribute("aria-label", `Remove ${c.name}`);
    row(`${c.name} has been empty for ${state.tidy.empty_days || 30} days`, c.name, remove);
  }
}

function showCategoryNotes(name, { clearSearch = false } = {}) {
  //: The notes are behind the panel, so the panel gets out of their way
  //: (INBOX 432: the list filtered under an open modal).
  document.querySelector('.sheet-overlay[data-sheet="categories"] .sheet-close')?.click();
  if (clearSearch) {
    noteSearch = "";
    const box = $("note-search");
    if (box) box.value = "";
  }
  activeCategory = name;
  draftsOnly = false;
  favouritesOnly = false;
  if (prefs.get("activeTab", null) !== "notes") switchTab("notes");
  showNotesSection("browse");
  renderSidebar();
  renderEntries();
}

//: The grid's keys, on the list so they survive every redraw. They act from
//: a row's first cell, `.manage-cat-main`, the one stop of the grid; the ⋯
//: cell keeps its own keys (its menu stops them) bar Left, which comes back.
function wireManageCategoryKeys(list, state, redraw) {
  list.addEventListener("keydown", (event) => {
    if (!event.target.matches?.(".manage-cat-main")) return;
    const row = event.target.closest("[data-category]");
    if (!row) return;
    const rows = [...list.querySelectorAll(".manage-cat-row")];
    const at = rows.indexOf(row);
    const move = (to) => {
      const next = rows[Math.max(0, Math.min(rows.length - 1, to))];
      if (!next) return;
      for (const r of rows) r.querySelector(":scope > .manage-cat-main").tabIndex = r === next ? 0 : -1;
      state.active = next.dataset.category;
      next.querySelector(":scope > .manage-cat-main").focus();
      next.scrollIntoView({ block: "nearest" });
    };
    const meta = categoryMeta.get(row.dataset.category);
    if (event.key === "ArrowDown") move(at + 1);
    else if (event.key === "ArrowUp") move(at - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(rows.length - 1);
    else if (event.key === "ArrowRight") row.querySelector(".manage-cat-menu > button")?.focus();
    else if (event.key === " ") {
      if (meta && meta.name !== "Uncategorised") {
        if (state.selected.has(meta.name)) state.selected.delete(meta.name);
        else state.selected.add(meta.name);
        redraw();
      }
    } else if (event.key === "Enter") showCategoryNotes(row.dataset.category);
    else if (event.key === "F2" && meta && meta.name !== "Uncategorised") renameCategory(meta, meta.name);
    else if ((event.key === "Delete" || event.key === "Backspace") && meta && meta.name !== "Uncategorised") deleteCategoryFromPanel(meta);
    else if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) row.querySelector(".manage-cat-menu > button")?.click();
    else return;
    event.preventDefault();
  });
}

//: The sticky footer: shown while rows are selected, with what can be done
//: to them together.
function drawManageCategoryFooter(footer, state, redraw) {
  footer.replaceChildren();
  const names = [...state.selected].filter((name) => categoryMeta.has(name));
  footer.classList.toggle("hidden", names.length === 0);
  if (!names.length) return;
  const label = document.createElement("span");
  label.className = "manage-cat-footer-label";
  label.textContent = `${names.length} selected`;
  const clear = smallButton("Clear", "Clear the selection", () => { state.selected.clear(); redraw(); });
  const merge = smallButton("ph:arrows-merge Merge into…", "Move every note in the selected categories into one category", async () => {
    await mergeCategoriesFromPanel(names.map((name) => categoryMeta.get(name)));
    state.selected.clear();
    redraw();
  }, false);
  const remove = smallButton("ph:trash Delete…", "Delete the selected categories; their notes are kept", async () => {
    const metas = names.map((name) => categoryMeta.get(name)).filter(Boolean);
    if (metas.length === 1) await deleteCategoryFromPanel(metas[0]);
    else await deleteCategoriesFromPanel(metas);
    state.selected.clear();
    redraw();
  });
  const colour = smallButton("ph:palette Colour…", "Give the selected categories one colour", async () => {
    await colourCategoriesFromPanel(names.map((name) => categoryMeta.get(name)).filter(Boolean));
    redraw();
  });
  footer.append(label, clear, remove, colour, merge);
}

//: **Several categories deleted with one question** (INBOX 504): where all
//: their notes go, asked once rather than once per category, and one Undo
//: that puts every note back and every empty category back.
async function deleteCategoriesFromPanel(metas) {
  const names = metas.map((m) => m.name);
  const total = metas.reduce((n, m) => n + m.count, 0);
  const target = total
    ? await chooseCategorySheet({ label: `Delete ${metas.length} categories`, sub: `Where should their ${nounCount(total, "note")} go? Nothing is deleted but the categories.`, exclude: null, excludeAll: names, includeUncategorised: true })
    : { name: "Uncategorised", id: null };
  if (!target) return;
  const into = target.name === "Uncategorised" ? "" : `?into=${target.id}`;
  const done = [];
  try {
    for (const meta of metas) {
      done.push(await apiJson(`/categories/${meta.id}${into}`, { method: "DELETE" }));
      if (activeCategory === meta.name) activeCategory = null;
    }
  } catch (error) {
    toast(error.message, true);
  }
  if (!done.length) return;
  offerCategoryUndo(
    `Deleted ${nounCount(done.length, "category", "categories")}. Their notes are in ${target.name}.`,
    async () => {
      for (const result of done) {
        if (result.moved_ids.length) await apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: result.moved_ids, category: result.name }) });
        else await apiJson("/categories", { method: "POST", body: JSON.stringify({ name: result.name }) });
      }
    },
    async () => {
      await loadCategories();
      for (const result of done) {
        const again = categoryMeta.get(result.name);
        if (again) await apiJson(`/categories/${again.id}${into}`, { method: "DELETE" });
      }
    }
  );
  await refreshAfterCategoryChange();
}

//: **One colour for several categories** (INBOX 504): the swatch sheet once,
//: one Undo that gives each its own colour back.
function colourCategoriesFromPanel(metas) {
  if (metas.length === 1) return pickCategoryColour(metas[0]);
  const before = new Map(metas.map((meta) => [meta.name, categoryMeta.get(meta.name)?.colour || null]));
  return new Promise((resolve) => {
    openSheet({
      label: `Colour for ${nounCount(metas.length, "category", "categories")}`,
      sub: "Shown on their dots, labels, graph nodes and timeline. Automatic picks one from each name.",
      name: "category-colour",
      onClose: () => resolve(),
      build: (card, close) => {
        card.classList.add("swatch-card");
        const preview = document.createElement("p");
        preview.className = "swatch-preview";
        preview.textContent = metas.map((meta) => meta.name).join(", ");
        const show = (key) => preview.style.setProperty("--category-dot", key ? CATEGORY_PALETTE[key] || key : "var(--muted)");
        const apply = async (pick) => {
          for (const meta of metas) {
            const fresh = categoryMeta.get(meta.name) || meta;
            await apiJson(`/categories/${fresh.id}/colour`, { method: "PUT", body: JSON.stringify({ colour: pick(meta.name) }) });
          }
          await loadCategories();
          manageCategoriesRedraw?.();
        };
        const picker = swatchPicker({
          label: `Colour for ${nounCount(metas.length, "category", "categories")}`,
          value: undefined,
          onChange: show,
          onChoose: async (key) => {
            close();
            try {
              await apply(() => key);
            } catch (error) {
              toast(error.message, true);
              return;
            }
            const message = `${metas.length} categories are now ${categoryColourName(key).toLowerCase()}.`;
            offerUndo(message, message, () => apply((name) => before.get(name)), () => apply(() => key));
          },
        });
        card.append(preview, picker);
        requestAnimationFrame(() => picker.querySelector('[tabindex="0"]')?.focus());
      },
    });
  });
}

//: Several categories folded into one, one undo for the lot. `target` given
//: (a look-alike suggestion's busiest name) skips the choice.
async function mergeCategoriesFromPanel(metas, target = null) {
  if (metas.length === 1 && !target) return mergeCategoryFromPanel(metas[0]);
  const names = metas.map((m) => m.name);
  target = target || await chooseCategorySheet({ label: `Merge ${nounCount(metas.length, "category", "categories")} into`, sub: "Their notes move across and they go.", exclude: null, excludeAll: names });
  if (!target) return;
  const done = [];
  try {
    for (const meta of metas) {
      const result = await apiJson(`/categories/${meta.id}/merge`, { method: "POST", body: JSON.stringify({ into: target.id }) });
      done.push(result);
      if (activeCategory === meta.name) activeCategory = result.into;
    }
  } catch (error) {
    toast(error.message, true);
  }
  if (!done.length) return;
  offerCategoryUndo(
    `Merged ${nounCount(done.length, "category", "categories")} into "${target.name}".`,
    async () => {
      for (const result of done) {
        if (result.moved_ids.length) await apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: result.moved_ids, category: result.from }) });
        else await apiJson("/categories", { method: "POST", body: JSON.stringify({ name: result.from }) });
      }
    },
    async () => {
      const ids = done.flatMap((result) => result.moved_ids);
      if (ids.length) await apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: ids, category: target.name }) });
    }
  );
  await refreshAfterCategoryChange();
}

//: The one list of what can be done to a category: the panel's ⋯ and the
//: sidebar row's ⋯ both draw from it.

async function createCategoryFromPanel() {
  const name = await promptDialog("Name the new category:", "", { confirmLabel: "Create" });
  if (!name || !name.trim()) return;
  try {
    const made = await apiJson("/categories", { method: "POST", body: JSON.stringify({ name: name.trim() }) });
    if (made.created) {
      pushUndo(
        `Made the category “${made.name}”`,
        async () => {
          await dropEmptyCategory(made.name);
          await refreshAfterCategoryChange();
        },
        async () => {
          await apiJson("/categories", { method: "POST", body: JSON.stringify({ name: made.name }) });
          await refreshAfterCategoryChange();
        }
      );
    }
    toast(made.created ? `Made "${made.name}".` : `"${made.name}" already exists.`);
    await refreshAfterCategoryChange();
  } catch (error) {
    toast(error.message, true);
  }
}

//: A choice of category in a sheet of its own: every other category as a
//: row, and optionally Uncategorised; answers the chosen meta or null.
function chooseCategorySheet({ label, sub, exclude, excludeAll = [], includeUncategorised = false }) {
  return new Promise((resolve) => {
    let chosen = null;
    openSheet({
      label,
      sub,
      name: "category-choice",
      onClose: () => resolve(chosen),
      build: (card, close) => {
        const list = document.createElement("div");
        list.className = "sheet-list";
        //: Uncategorised is offered whether or not it exists yet: deleting
        //: a category on a fresh notebook had no "keep them unfiled" choice
        //: (INBOX 432). In the sidebar's order, after it.
        const metas = [...categoryMeta.values()].sort((a, b) => compareCategoryNames(a.name, b.name));
        if (includeUncategorised && !categoryMeta.has("Uncategorised")) metas.push({ name: "Uncategorised", id: null, count: 0 });
        for (const meta of metas) {
          if (meta.name === exclude || excludeAll.includes(meta.name)) continue;
          if (meta.name === "Uncategorised" && !includeUncategorised) continue;
          list.appendChild(sheetRow("ph ph-folder", `${meta.name} (${meta.count})`, () => { chosen = meta; close(); }));
        }
        if (!list.children.length) {
          const none = document.createElement("p");
          none.className = "muted";
          none.textContent = "There is no other category yet. Make one with New category.";
          list.appendChild(none);
        }
        card.appendChild(list);
      },
    });
  });
}

async function mergeCategoryFromPanel(meta) {
  const target = await chooseCategorySheet({ label: `Merge ${meta.name} into`, sub: `Its ${nounCount(meta.count, "note")} move across and ${meta.name} goes.`, exclude: meta.name });
  if (!target) return;
  try {
    const result = await apiJson(`/categories/${meta.id}/merge`, { method: "POST", body: JSON.stringify({ into: target.id }) });
    if (activeCategory === meta.name) activeCategory = result.into;
    const ids = result.moved_ids;
    offerCategoryUndo(
      `Merged "${result.from}" into "${result.into}".`,
      () => (ids.length ? apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: ids, category: result.from }) }) : apiJson("/categories", { method: "POST", body: JSON.stringify({ name: result.from }) })),
      () => apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: ids.length ? ids : [0], category: result.into }) }).catch(() => null)
    );
    await refreshAfterCategoryChange();
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteCategoryFromPanel(meta) {
  const target = meta.count
    ? await chooseCategorySheet({ label: `Delete ${meta.name}`, sub: `Where should its ${nounCount(meta.count, "note")} go? Nothing is deleted but the category.`, exclude: meta.name, includeUncategorised: true })
    : { name: "Uncategorised", id: null };
  if (!target) return;
  try {
    const into = target.name === "Uncategorised" ? "" : `?into=${target.id}`;
    const result = await apiJson(`/categories/${meta.id}${into}`, { method: "DELETE" });
    if (activeCategory === meta.name) activeCategory = null;
    const ids = result.moved_ids;
    offerCategoryUndo(
      `Deleted "${result.name}". Its notes are in ${result.into || "Uncategorised"}.`,
      () => (ids.length ? apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: ids, category: result.name }) }) : apiJson("/categories", { method: "POST", body: JSON.stringify({ name: result.name }) })),
      async () => {
        await loadCategories();
        const again = categoryMeta.get(result.name);
        if (again) await apiJson(`/categories/${again.id}${into}`, { method: "DELETE" });
      }
    );
    await refreshAfterCategoryChange();
  } catch (error) {
    toast(error.message, true);
  }
}

//: Split: the category's notes with a tick each and a name for the new
//: category, or Suggest a split, which groups them by their tags for review
//: (POST .../split/propose moves nothing); each group applies on its own.
function splitCategoryFromPanel(meta) {
  const notes = allEntries.filter((e) => e.category === meta.name && !e.is_draft);
  openSheet({
    label: `Split ${meta.name}`,
    sub: "Tick the notes to move and name their new category, or let a split be suggested.",
    name: "category-split",
    build: (card, close) => {
      const form = document.createElement("form");
      form.className = "manage-split";
      const nameInput = document.createElement("input");
      nameInput.type = "text";
      nameInput.maxLength = 100;
      nameInput.placeholder = "New category name";
      nameInput.setAttribute("aria-label", "New category name");
      const list = document.createElement("div");
      list.className = "sheet-list manage-split-list";
      const boxes = new Map();
      for (const entry of notes) {
        const label = document.createElement("label");
        label.className = "checkbox-label manage-split-note";
        const box = document.createElement("input");
        box.type = "checkbox";
        boxes.set(entry.id, box);
        //: The note's words, markdown stripped, clamped to two lines with an
        //: ellipsis by the CSS: an 80-character slice cut each row off
        //: mid-sentence with nothing to say it went on ("...Timeline and").
        const text = document.createElement("span");
        //: A note with no text of its own (an image, a voice note) has no
        //: `content` to cut: it threw here and the sheet never opened.
        text.className = "manage-split-text";
        text.textContent = entry.title || stripMarkdownPreview(stripFrontmatter(String(entry.content || "")).slice(0, 240)).replace(/\s+/g, " ").trim() || "Untitled note";
        label.title = text.textContent;
        label.append(box, text);
        list.appendChild(label);
      }
      const suggestions = document.createElement("div");
      suggestions.className = "manage-split-suggestions";
      const row = document.createElement("div");
      row.className = "row confirm-actions";
      //: Two ways to a suggestion (INBOX 431 (e)): by the notes' tags, which
      //: needs nothing, or Ask AI, which has the utility model read the
      //: notes; with the model off the tags answer, and the line says so.
      const propose = async (ai) => {
        //: The model can take a while on a big category: the button says it
        //: is working and cannot be pressed twice meanwhile.
        const button = ai ? askAi : suggest;
        setBusy(button, true);
        const proposal = await apiJson(`/categories/${meta.id}/split/propose${ai ? "?ai=true" : ""}`, { method: "POST" })
          .catch((e) => { toast(e.message, true); return null; })
          .finally(() => setBusy(button, false));
        if (!proposal) return;
        suggestions.replaceChildren();
        //: One line, whichever way it went: two stacked paragraphs ("couldn't
        //: suggest" then "no split to suggest") took 120px of a short sheet.
        const line = (text) => {
          const p = document.createElement("p");
          p.className = "muted manage-split-line";
          p.textContent = text;
          suggestions.appendChild(p);
        };
        if (!proposal.groups.length) {
          line(proposal.ai_unavailable
            ? `${aiNameNow()} couldn't suggest a split just now, and no two notes here share a tag the rest do not. Pick notes by hand.`
            : "No two notes here share a tag that the rest do not, so there is no split to suggest. Pick notes by hand.");
          return;
        }
        if (proposal.ai_unavailable) line(`${aiNameNow()} couldn't suggest a split just now, so these are grouped by tags.`);
        for (const group of proposal.groups) {
          const pick = smallButton(`ph:check-square ${group.name} (${group.entry_ids.length})`, `Tick these ${nounCount(group.entry_ids.length, "note")} and name the category ${group.name}`, () => {
            for (const [id, box] of boxes) box.checked = group.entry_ids.includes(id);
            nameInput.value = group.name;
            nameInput.focus();
          });
          pick.type = "button";
          suggestions.appendChild(pick);
        }
      };
      const suggest = smallButton("ph:tag Suggest by tags", "Group these notes by their tags, to review before anything moves", () => propose(false));
      const askAi = smallButton(`ph:sparkle Ask ${aiNameNow()}`, `Have ${aiNameNow()} read these notes and suggest groups, to review before anything moves`, () => propose(true));
      askAi.type = "button";
      //: Inside a form every button submits unless told otherwise.
      suggest.type = "button";
      const apply = document.createElement("button");
      apply.type = "submit";
      apply.className = "small";
      apply.textContent = "Move to new category";
      row.append(suggest, askAi, apply);
      form.append(nameInput, suggestions, list, row);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = nameInput.value.trim();
        const ids = [...boxes].filter(([, box]) => box.checked).map(([id]) => id);
        if (!name) { toast("Name the new category first.", "info"); nameInput.focus(); return; }
        if (!ids.length) { toast("Tick the notes to move first.", "info"); return; }
        //: One split per press: a second Enter or click while the first is
        //: on its way asked the server to split notes already moved.
        if (apply.disabled) return;
        setBusy(apply, true);
        try {
          const result = await apiJson(`/categories/${meta.id}/split`, { method: "POST", body: JSON.stringify({ name, entry_ids: ids }) });
          close();
          const moved = result.moved_ids;
          offerCategoryUndo(
            `Moved ${nounCount(moved.length, "note")} from "${result.from}" into "${result.name}".`,
            () => apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: moved, category: result.from }) }),
            () => apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: moved, category: result.name }) })
          );
          await refreshAfterCategoryChange();
        } catch (error) {
          toast(error.message, true);
        } finally {
          setBusy(apply, false);
        }
      });
      card.appendChild(form);
      setTimeout(() => nameInput.focus(), 0);
    },
  });
}

// --- Moved from notes-list.js (INBOX 432): category actions that only ever
// run on a click, so they load with this panel instead of at boot. Boot code
// reaches them through LAZY_ENTRY_POINTS (app.js).

async function renameCategory(meta, currentName) {
  const name = await promptDialog(`Rename "${currentName}" to:`, currentName, { confirmLabel: "Rename" });
  if (!name || name === currentName) return;

  // Renaming onto a category that already exists merges them, which is
  // usually the point: but it's destructive-looking, so it's confirmed.
  const target = categoryMeta.get(name);
  if (target) {
    const ok = await confirmDialog(
      `"${name}" already exists. Merge "${currentName}" into it?\n\n` +
        `Its notes move across, nothing is deleted. "${name}" would then ` +
        `hold ${target.count + meta.count} notes.`,
      { confirmLabel: "Merge", danger: false }
    );
    if (!ok) return;
  }
  //: The notes it holds now, so a merge can be undone note by note.
  const ids = allEntries.filter((e) => e.category === currentName).map((e) => e.id);

  try {
    const result = await apiJson(`/categories/${meta.id}`, {
      method: "PUT",
      body: JSON.stringify({ name }),
    });
    if (activeCategory === currentName) activeCategory = name;
    //: Undoable, and the open panel redrawn (INBOX 432: the panel kept the
    //: old name, and neither a rename nor a merge offered Undo).
    const renameTo = async (from, to) => {
      await loadCategories();
      const row = categoryMeta.get(from);
      if (row) await apiJson(`/categories/${row.id}`, { method: "PUT", body: JSON.stringify({ name: to }) });
    };
    offerCategoryUndo(
      result.merged ? `Merged "${currentName}" into "${name}".` : `Renamed "${currentName}" to "${name}".`,
      () => (result.merged
        ? (ids.length
          ? apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: ids, category: currentName }) })
          : apiJson("/categories", { method: "POST", body: JSON.stringify({ name: currentName }) }))
        : renameTo(name, currentName)),
      () => renameTo(currentName, name)
    );
    await refreshAfterCategoryChange();
  } catch (error) {
    toast(error.message, true);
  }
}

//: Kept for the keyboard's Delete on a focused row and older callers; the
//: sidebar's ⋯ now goes through `deleteCategoryFromPanel`, which asks where
//: the notes go.
async function deleteCategory(meta, name, count) {
  const ok = (await confirmDialog(
    `Delete the category "${name}"?\n\n` +
      (count
        ? `Its ${nounCount(count, "note")} are kept and become ` +
          `Uncategorised: deleting a category never deletes notes.`
        : "It has no notes in it.")
  ));
  if (!ok) return;
  try {
    const result = await apiJson(`/categories/${meta.id}`, { method: "DELETE" });
    if (activeCategory === name) activeCategory = null;
    const ids = result.moved_ids || [];
    offerCategoryUndo(
      `Deleted "${name}". Its notes are in Uncategorised.`,
      () => apiJson(ids.length ? "/categories/move" : "/categories", { method: "POST", body: JSON.stringify(ids.length ? { entry_ids: ids, category: name } : { name }) }),
      async () => {
        await loadCategories();
        const again = categoryMeta.get(name);
        if (again) await apiJson(`/categories/${again.id}`, { method: "DELETE" });
      }
    );
    await refreshAfterCategoryChange();
  } catch (error) {
    toast(error.message, true);
  }
}

//: Moves notes back to where they were, from the `previous` a move returned.
async function restoreCategoryMoves(previous) {
  //: Grouped by the category and by who filed it: a note the model filed is
  //: the model's to refile again after the undo (`user_filed`).
  const groups = new Map();
  for (const { id, category, user_filed } of previous) {
    const key = JSON.stringify([category, user_filed ?? null]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(id);
  }
  for (const [key, ids] of groups) {
    const [category, filed] = JSON.parse(key);
    await apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: ids, category, user_filed: filed }) });
  }
}

//: **Moving one note is one click on its category** (INBOX 432). Before
//: this, the only ways to change a single note's category were dragging its
//: chip onto the sidebar or opening the whole edit form, and the card's ⋯
//: menu (26 items) had no Move at all: the most common correction a notebook
//: that files for you gets asked for was the hardest one to find. A sheet of
//: every category with its count, the current one marked, and a new one by
//: name; choosing is the move, with the same undo a drop gets.
function chooseNoteCategory(ids, current = "") {
  const noteIds = (Array.isArray(ids) ? ids : [ids]).map(Number).filter(Boolean);
  if (!noteIds.length) return;
  const many = noteIds.length > 1;
  openSheet({
    label: many ? `Move ${nounCount(noteIds.length, "note")} to` : "Move to category",
    sub: current && !many ? `Now in ${current}.` : "",
    name: "note-category",
    build: (card, close) => {
      const list = document.createElement("div");
      list.className = "sheet-list";
      const names = [...categoryMeta.keys()].sort((a, b) => a.localeCompare(b));
      for (const name of names) {
        const meta = categoryMeta.get(name);
        const here = name === current;
        const row = sheetRow(here ? "ph ph-check" : "ph ph-folder", `${name} (${meta?.count ?? 0})`, async () => {
          close();
          if (!here) await moveNotesToCategory(noteIds, name);
          //: The redraw took the chip the sheet gave the focus back to.
          if (!many) focusNoteRow(noteIds[0]);
        });
        if (here) row.setAttribute("aria-current", "true");
        list.appendChild(row);
      }
      list.appendChild(
        sheetRow("ph ph-plus", "New category…", async () => {
          close();
          const name = await promptDialog("Name the new category:", "", { confirmLabel: "Move" });
          if (name && name.trim()) await moveNotesToCategory(noteIds, name.trim());
        })
      );
      card.appendChild(list);
    },
  });
}

//: The tag manager (openTagsSheet and the tag edits) moved to tag-manager.js
//: (INBOX 447): it grew past a sheet of rows, and it is its own lazy piece.

//: Moving chosen notes, from the batch bar's Move to or a drop: one call,
//: one toast, one undo.
async function moveNotesToCategory(ids, category) {
  //: A move to a name typed now makes the category; its undo takes the empty
  //: category away again, or Undo left a stray "Probe" in the sidebar
  //: (TIMELINE_PLAN 10 row 3, measured by undo.js's selection bar).
  const made = !categoryMeta.has(category);
  try {
    const result = await apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: ids, category }) });
    const previous = result.previous;
    if (previous.length) {
      offerCategoryUndo(
        `Moved ${nounCount(previous.length, "note")} to "${category}".`,
        async () => {
          await restoreCategoryMoves(previous);
          if (made) await dropEmptyCategory(category);
        },
        () => apiJson("/categories/move", { method: "POST", body: JSON.stringify({ entry_ids: previous.map((p) => p.id), category }) })
      );
    }
    await refreshAfterCategoryChange();
    return result;
  } catch (error) {
    toast(error.message, true);
    return null;
  }
}

async function dropEmptyCategory(name) {
  const row = (await apiJson("/categories")).find((c) => c.name === name);
  if (row && !row.count) await apiJson(`/categories/${row.id}`, { method: "DELETE" });
}

//: **The colour picker** (INBOX 441 (4), the owner: "there is no way to
//: customise the colour of categories"). DESIGN.md's swatch picker: a
//: `role="radiogroup"` of round swatches, the twelve hues of `CATEGORY_PALETTE`
//: (notes-list.js; each reads at 3:1 as a dot on both themes) and one worded
//: Automatic that clears the choice. Arrows, Home and End move the focus and
//: the check together (the radio pattern), so the preview above follows the
//: keys; Enter, Space or a click commits, Escape leaves it unchanged. The
//: swatch is painted through the CSSOM (`--swatch`), never an inline style.
//: `palette` and `none` make it the one picker for every row of colours
//: (DESIGN.md: "a new row of colours is this recipe with its own palette"):
//: Quick access's tile highlight passes the accent ahead of the twelve and
//: "No highlight" as the worded choice (INBOX 589).
const categoryColourName = (key, none = "Automatic") => (key ? key[0].toUpperCase() + key.slice(1) : none);

function swatchPicker({ label, value, onChange, onChoose, palette = CATEGORY_PALETTE, none = "Automatic" }) {
  const group = document.createElement("div");
  group.className = "swatch-picker";
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-label", label);
  //: `none: null` leaves the worded choice out: a row of colours only (the
  //: board's Recent row, which has nothing to clear).
  const keys = none === null ? Object.keys(palette) : [...Object.keys(palette), null];
  const radios = keys.map((key) => {
    const radio = document.createElement("button");
    radio.type = "button";
    radio.className = key ? "swatch-option" : "swatch-option swatch-auto";
    radio.setAttribute("role", "radio");
    radio.setAttribute("aria-label", categoryColourName(key, none));
    radio.title = categoryColourName(key, none);
    if (key) radio.style.setProperty("--swatch", palette[key]);
    else radio.textContent = none;
    radio.addEventListener("click", () => {
      mark(key);
      onChoose(key);
    });
    return radio;
  });
  //: Only the checked swatch is a Tab stop; a stored hex the swatches do not
  //: include leaves none checked, so the first is the stop instead.
  const mark = (key) => {
    radios.forEach((radio, i) => {
      radio.setAttribute("aria-checked", String(keys[i] === key));
      radio.tabIndex = keys[i] === key ? 0 : -1;
    });
    if (!radios.some((radio) => radio.tabIndex === 0)) radios[0].tabIndex = 0;
    onChange?.(key);
  };
  group.addEventListener("keydown", (event) => {
    const at = radios.indexOf(event.target);
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    const to = step ? (at + step + radios.length) % radios.length : { Home: 0, End: radios.length - 1 }[event.key];
    if (at < 0 || to === undefined) return;
    event.preventDefault();
    radios[to].focus();
    mark(keys[to]);
  });
  group.append(...radios);
  if (radios.length) mark(keys.includes(value) ? value : undefined);
  return group;
}

async function saveCategoryColour(meta, colour) {
  await apiJson(`/categories/${meta.id}/colour`, { method: "PUT", body: JSON.stringify({ colour }) });
  //: Carries the colour back, and `loadCategories` repaints every dot and
  //: tells the map and the dashboard to redraw.
  await loadCategories();
  manageCategoriesRedraw?.();
}

function pickCategoryColour(meta) {
  const before = categoryMeta.get(meta.name)?.colour || null;
  openSheet({
    label: `Colour for ${meta.name}`,
    sub: "Shown on its dots, labels, graph nodes and timeline. Automatic picks one from its name.",
    name: "category-colour",
    build: (card, close) => {
      card.classList.add("swatch-card");
      const preview = document.createElement("p");
      preview.className = "swatch-preview";
      preview.textContent = meta.name;
      const show = (key) => preview.style.setProperty("--category-dot", key ? CATEGORY_PALETTE[key] || key : categoryAutoDot(meta.name));
      const picker = swatchPicker({
        label: `Colour for ${meta.name}`,
        value: before,
        onChange: show,
        onChoose: async (key) => {
          close();
          if (key === before) return;
          try {
            await saveCategoryColour(meta, key);
          } catch (error) {
            toast(error.message, true);
            return;
          }
          const message = `${meta.name} is now ${categoryColourName(key).toLowerCase()}.`;
          offerUndo(message, message, () => saveCategoryColour(meta, before), () => saveCategoryColour(meta, key));
        },
      });
      card.append(preview, picker);
      requestAnimationFrame(() => picker.querySelector('[tabindex="0"]')?.focus());
    },
  });
}

// ---- from notes-list.js (search-boot-1005): offerCategoryUndo ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

//: One toast and one undo-stack entry per change, so the toast's Undo and
//: Ctrl+Z are the same act.
function offerCategoryUndo(message, undo, redo) {
  const refreshed = (act) => async () => {
    await act();
    await refreshAfterCategoryChange();
  };
  offerUndo(message, message, refreshed(undo), refreshed(redo));
}

// Moved from notes-list.js (boot gzip): every caller is in this file.
//: After any change: the notes, the sidebar, and the open panel, redrawn.
async function refreshAfterCategoryChange() {
  await loadEntries();
  await loadCategories();
  manageCategoriesRedraw?.();
}

// The Notes sidebar's sections, folded and tidied (C43, the owner: "a little
// messy and there is a lot happening and I want to be able to collapse
// sections like with the most used section"). A lazy bundle
// (the Manage categories bundle, loaded by the stand-in for `foldSide`, which `renderSidebar` calls) so
// the boot scripts stay at their cap. Three things, none of them in boot:
//   1. a caret in the Categories, Most used and Saved searches headings that
//      folds the section, the state kept per section in this browser;
//   2. categories with no notes dimmed and behind one "Show N empty" row,
//      kept on screen when chosen (the filter) or when asked for;
//   3. the sidebar is the one scroller (the old inner list scroller is gone).

lazyScript("/css/sidebar-folds-lazy.css");

const SIDEBAR_FOLDS = [
  { key: "cat", what: "categories", host: () => $("sidebar"), head: () => document.querySelector("#sidebar > .sidebar-head h2"), attr: "data-fold-cat" },
  { key: "most", what: "Most used", host: () => $("most-used-box"), head: () => document.querySelector("#most-used-box h2"), attr: "data-folded" },
  { key: "saved", what: "saved searches", host: () => $("saved-finds-box"), head: () => document.querySelector("#saved-finds-box h2"), attr: "data-folded" },
];

function sidebarFoldSet(fold, folded) {
  const host = fold.host();
  const button = fold.head()?.querySelector(".sidebar-fold-toggle");
  if (!host || !button) return;
  host.toggleAttribute(fold.attr, folded);
  button.setAttribute("aria-expanded", String(!folded));
  const label = `${folded ? "Show" : "Hide"} ${fold.what}`;
  button.setAttribute("aria-label", label);
  button.title = label;
  button.querySelector("i")?.classList.toggle("ph-caret-right", folded);
  button.querySelector("i")?.classList.toggle("ph-caret-down", !folded);
}

function sidebarFoldsWire() {
  for (const fold of SIDEBAR_FOLDS) {
    const head = fold.head();
    if (!head || head.querySelector(".sidebar-fold-toggle")) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost small icon-only sidebar-fold-toggle";
    const icon = document.createElement("i");
    icon.className = "ph ph-caret-down";
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);
    head.prepend(button);
    button.addEventListener("click", () => {
      const folded = !fold.host().hasAttribute(fold.attr);
      sidebarFoldSet(fold, folded);
      prefs.set(`sidebarFold:${fold.key}`, folded ? "1" : "0");
    });
    sidebarFoldSet(fold, prefs.bool(`sidebarFold:${fold.key}`, false));
  }
}

//: Empty categories: a row with a count of 0 that is not the one in use.
function sidebarEmptyRows() {
  const ul = $("category-list");
  if (!ul) return;
  ul.querySelector(".category-empty-toggle")?.remove();
  const empty = [...ul.children].filter((li) => !li.classList.contains("category-drafts-row")
    && li.querySelector(".category-actions") && li.querySelector(".count")?.textContent === "0"
    && li.getAttribute("aria-current") !== "true");
  const show = prefs.bool("sidebarShowEmpty", false);
  for (const li of empty) {
    li.classList.add("category-empty");
    if (!show) li.remove();
  }
  if (!empty.length) return;
  const row = document.createElement("li");
  row.className = "category-empty-toggle";
  row.tabIndex = 0;
  row.setAttribute("role", "button");
  row.setAttribute("aria-pressed", String(show));
  const name = document.createElement("span");
  name.className = "category-name";
  name.textContent = show ? `Hide ${empty.length} empty` : `Show ${empty.length} empty`;
  row.title = "Categories with no notes in them";
  row.appendChild(name);
  const flip = () => {
    prefs.set("sidebarShowEmpty", show ? "0" : "1");
    renderSidebar();
    requestAnimationFrame(() => $("category-list").querySelector(".category-empty-toggle")?.focus());
  };
  row.addEventListener("click", flip);
  row.addEventListener("keydown", (event) => {
    if (event.target !== row) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      flip();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      row.previousElementSibling?.focus();
    }
  });
  ul.appendChild(row);
}

function foldSide() {
  sidebarFoldsWire();
  sidebarEmptyRows();
}
