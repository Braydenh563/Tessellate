// notes-sidebar.js: the category list's draw (`drawSidebar`, with `sidebarRovingRows` and `markSidebarRowCurrent`).
// Moved out of notes-list.js (LEDGER L-world-class-810) to come off the boot file: lazy, the `notesSidebar`
// bundle with a stand-in for `drawSidebar` in lazy-entries.js. `renderSidebar` (notes-list.js) keeps the
// "owed while the tab is hidden" guard, so the file is fetched only when a list is really drawn; nobody
// reads a return value.

(() => {
function drawSidebar() {
  // Categories + counts are derived from the loaded entries, the
  // simplest thing that works; no extra endpoint needed yet.
  // Drafts only belong in the Drafts row (user-reported: they were still
  // showing under All/category counts, undercutting the point of a
  // separate section): until saved as a real note, a draft doesn't count.
  const counts = new Map();
  //: Every category the notebook has, not only the ones a loaded note is in:
  //: one made in Manage categories was in the panel and nowhere else
  //: (INBOX 432). Uncategorised only while something is in it.
  for (const name of categoryMeta.keys()) if (name !== "Uncategorised") counts.set(name, 0);
  for (const entry of allEntries) {
    if (!noteListed(entry)) continue;
    for (const name of [entry.category, ...(entry.also_in || [])]) counts.set(name, (counts.get(name) || 0) + 1);
  }

  const ul = $("category-list");
  ul.replaceChildren();

  const addRow = (label, count, category) => {
    const li = document.createElement("li");
    //: "All" is the row for no filter at all, so it is not lit while Drafts
    //: or Favourites is (INBOX 432: two rows looked chosen at once).
    if (category === activeCategory && !draftsOnly && !favouritesOnly && !(!category && noteSearch === "tag:meeting")) markSidebarRowCurrent(li);
    //: The row a carried note is dropped on (obj-carry.js `OBJ_FILE_DESTS`).
    if (category && category !== "Uncategorised") li.dataset.category = category;
    const name = document.createElement("span");
    name.className = "category-name";
    //: Every name on one edge (INBOX 437 (4)): All takes a glyph as Drafts
    //: does, a category its colour dot, as on a note's own chip.
    if (!category) setLabel(name, `ph:stack ${label}`);
    else {
      name.textContent = label;
      const dot = document.createElement("i");
      dot.className = "ph category-row-dot ph-lead";
      dot.setAttribute("aria-hidden", "true");
      paintCategoryDot(dot, category);
      name.prepend(dot);
    }
    name.title = label;
    const badge = document.createElement("span");
    badge.className = "count";
    badge.textContent = count;
    li.append(name, badge);
    li.addEventListener("click", () => {
      activeCategory = category;
      draftsOnly = false; // exclusive with the Drafts filter below
      favouritesOnly = false; // and with Favourites, for the same reason
      // The list this filters lives in the "browse" sub-tab, and the sidebar
      // is visible from all four, so picking a category while writing a note
      // or asking a question filtered a list that was `display: none`, and the
      // click appeared to do nothing at all. Reported. The same fix
      // `flashEntry` already carries for jumping to a note, for the same
      // reason: a sidebar that is always on screen must be able to bring the
      // thing it controls on screen with it.
      showNotesSection("browse");
      renderSidebar();
      renderEntries();
    });

    // Rename/delete for real categories only, "All" is a filter, and
    // Uncategorised is where notes land when a category goes away.
    const meta = category ? categoryMeta.get(category) : null;
    //: Round 9 (INBOX 431 (e)): the row's ⋯ is the Manage categories panel's
    //: own menu (Rename, Merge into, Split, Delete, the panel), where two
    //: bare buttons were; and every real category takes a dropped note.
    if (meta && category !== "Uncategorised") {
      const actions = document.createElement("span");
      actions.className = "category-actions";
      const menu = kebabMenu(categoryMenuItems(meta), `Actions for ${category}`, { vertical: true });
      menu.addEventListener("click", (event) => event.stopPropagation());
      actions.appendChild(menu);
      li.appendChild(actions);
    }
    if (category) wireCategoryDropTarget(li, category);
    wireSidebarRowKeys(li);
    ul.appendChild(li);
  };

  addRow("All", allEntries.filter(noteListed).length, null);

  //: **One shape for the rows that are not categories** (Drafts, Favourites,
  //: Meetings): a glyph and a name, a count, the current one marked, a press
  //: that filters. Three hand-built copies of these eleven lines were how the
  //: second and third came to exist; INBOX 644's Meetings made it a helper.
  const filterRow = (label, count, current, title, run) => {
    const li = document.createElement("li");
    li.className = "category-drafts-row";
    if (current) markSidebarRowCurrent(li);
    wireSidebarRowKeys(li);
    const name = document.createElement("span");
    name.className = "category-name";
    setLabel(name, label);
    const badge = document.createElement("span");
    badge.className = "count";
    badge.textContent = count;
    li.append(name, badge);
    if (title) li.title = title;
    li.addEventListener("click", run);
    ul.appendChild(li);
    return li;
  };
  const toggleFilter = (drafts) => () => {
    if (drafts) draftsOnly = !draftsOnly;
    else favouritesOnly = !favouritesOnly;
    if (drafts) favouritesOnly = false;
    else draftsOnly = false;
    activeCategory = null;
    showNotesSection("browse");
    renderSidebar();
    renderEntries();
  };

  // Drafts: a filter row beside the categories, always shown (even at 0) so it stays findable.
  filterRow("ph:pencil-simple-line Drafts", allEntries.filter((e) => e.is_draft).length, draftsOnly, "", toggleFilter(true));

  // **Favourites**: built like Drafts, over the pinned notes (see `favouritesOnly`); no second place to star.
  filterRow(
    "ph:star Favourites",
    allEntries.filter((e) => e.pinned && noteListed(e)).length,
    favouritesOnly,
    "Notes you have starred, they also float to the top of every list",
    toggleFilter(false)
  );

  //: **Meetings** (INBOX 644: "tucked away"; the Library had a Meetings chip,
  //: the Notes tab nothing). Over what every meeting already carries, the
  //: `meeting` tag (`entry/meetings.py`), so the filter is `tag:meeting` in
  //: the box, visible and editable as a tag chip's is. Always shown, so it is
  //: there to find before the first meeting.
  //: **Private** (INBOX 1695 c) is the same shape over `is:private`.
  const queryRow = (label, keep, query, title) =>
    filterRow(label, allEntries.filter((e) => keep(e) && noteListed(e)).length, noteSearch === query && !draftsOnly && !favouritesOnly, title, () => filterNotesBy(query));
  queryRow("ph:users-three Meetings", (e) => e.tags.includes("meeting"), "tag:meeting", "").classList.add("category-meetings-row");
  queryRow("ph:lock Private", (e) => e.is_private, "is:private", "");
  //: Tags, beside Drafts and Favourites (INBOX 432): a sheet of every tag
  //: (categories-panel.js `openTagsSheet`), not a second long list here.
  const sheetRow = (label, title, open) => {
    const row = document.createElement("li");
    row.className = "category-drafts-row";
    const name = document.createElement("span");
    name.className = "category-name";
    setLabel(name, label);
    row.append(name);
    row.title = title;
    row.addEventListener("click", open);
    wireSidebarRowKeys(row);
    ul.appendChild(row);
  };
  sheetRow("ph:hash Tags", "Every tag: see its notes, rename, merge or remove it", () => openTagsSheet());
  //: Groups of notes gathered by hand (L-world-class-172), a sheet too.
  sheetRow("ph:folders Groups", "Notes you gathered by hand, apart from categories and tags", () => openNoteGroupsSheet());

  //: One order everywhere a list of categories is shown: by name, ignoring
  //: case and accents, numbers in number order (INBOX 432: a bare `.sort()`
  //: put "Zebra" before "alpha" and "Émigré" last).
  for (const [category, count] of [...counts.entries()].sort((a, b) => compareCategoryNames(a[0], b[0]))) {
    addRow(category, count, category);
  }
  sidebarRovingRows(ul);
  foldSide();
}

//: **One tab stop for the whole category list** (UX1: 62 stops for 31
//: categories, every name and then its ⋯, before the first note). The row that
//: is current (else the first) is the stop; the arrows, Home and End walk the
//: rows (`wireSidebarRowKeys`), and the right arrow reaches a row's ⋯, which
//: is also on Shift+F10 and the context key like every row menu. The stop
//: follows focus, so Tab back into the list lands where it left.
function sidebarRovingRows(ul) {
  const rows = [...ul.children];
  const stop = rows.find((li) => li.getAttribute("aria-current") === "true") || rows[0];
  for (const li of rows) {
    li.tabIndex = li === stop ? 0 : -1;
    for (const button of li.querySelectorAll(".category-actions button")) button.tabIndex = -1;
  }
  if (ul.dataset.roving) return;
  ul.dataset.roving = "1";
  ul.addEventListener("focusin", (event) => {
    const row = event.target.closest?.("#category-list > li");
    if (!row) return;
    for (const li of ul.children) li.tabIndex = li === row ? 0 : -1;
  });
}

function markSidebarRowCurrent(li) {
  li.classList.add("active");
  li.setAttribute("aria-current", "true");
}

  window.drawSidebar = drawSidebar;
})();
