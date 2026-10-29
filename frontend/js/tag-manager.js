// Lazily loaded (LAZY_MODULES.tagManager in app.js): the tag manager and the
// bulk tag dialog run only when someone opens them, so they stay off the boot
// scripts' gzip budget (tests/test_static_compression.py).
//
//: **Tag manager** (INBOX 447 (4), the owner: "a way to more easily manage
//: tags in, between, and across individual and multiple notes. like a tag
//: manager"). It replaces the sidebar's Tags sheet (INBOX 432), which listed
//: tags with two bare buttons each. This is DESIGN.md's "A list you manage"
//: recipe, the Manage categories panel's twin: a grid of quiet rows (a hash,
//: the name, a muted count pill and a ghost ⋯), a roving stop, Space to
//: select, Enter to show a tag's notes, F2 to rename, Delete to remove, and a
//: sticky footer for what can be done to the selected tags together. Every
//: change is one call (routes_tags.py), one transaction, one revision and
//: event per note it touched, and one Undo that puts each note's tags back.
//:
//: The same module holds the bulk dialog for the Notes selection bar: add
//: tags to, and take tags off, every selected note in one action.

const tagNotesWord = (n) => nounCount(n, "note");

//: “a”, “b” and “c”; past three, “a”, “b”, “c” and 4 more.
function tagNamesWords(names) {
  const quoted = names.map((name) => `“${name}”`);
  if (quoted.length <= 3) return quoted.length > 1 ? `${quoted.slice(0, -1).join(", ")} and ${quoted[quoted.length - 1]}` : quoted[0] || "";
  return `${quoted.slice(0, 3).join(", ")} and ${quoted.length - 3} more`;
}

let tagManagerRedraw = null;

async function fetchTagCounts() {
  return apiJson("/tags?limit=5000").catch(() => ({}));
}

//: After any change: the notes redrawn, and the open manager with fresh counts.
async function refreshAfterTagEdit() {
  await loadEntries();
  await tagManagerRedraw?.();
}

//: **Every tag change goes through here**: one POST, one toast and one entry
//: on the undo stack, so the toast's Undo and Ctrl+Z are the same act. The
//: server answers with the tags each changed note had (`before`), and
//: `/tags/restore` puts exactly those back in one transaction.
//: A Notes filter on a tag that was just renamed, merged or removed follows
//: it (to the new name) or clears, instead of showing a list filtered on a
//: tag that no longer exists.
function retargetTagFilter(moves) {
  const current = (noteSearch || "").trim();
  const match = current.match(/^tag:(?:"([^"]+)"|(\S+))$/i);
  if (!match) return;
  const was = (match[1] || match[2]).toLowerCase();
  const hit = Object.keys(moves).find((name) => name.toLowerCase() === was);
  if (hit === undefined) return;
  const next = moves[hit];
  if (next) {
    filterNotesByTag(next);
  } else {
    noteSearch = "";
    $("note-search").value = "";
    $("save-search")?.classList.add("hidden");
    renderEntries();
  }
}

async function runTagEdit(message, path, body, moves = null) {
  let result;
  try {
    result = await apiJson(path, { method: "POST", body: JSON.stringify(body) });
  } catch (error) {
    toast(error.message, true);
    return null;
  }
  if (!result.changed) {
    toast("Nothing needed changing.");
    return result;
  }
  let before = result.before;
  await refreshAfterTagEdit();
  if (moves) retargetTagFilter(moves);
  const undo = async () => {
    await apiJson("/tags/restore", { method: "POST", body: JSON.stringify({ notes: before }) });
    await refreshAfterTagEdit();
  };
  const redo = async () => {
    const again = await apiJson(path, { method: "POST", body: JSON.stringify(body) });
    before = again.before;
    await refreshAfterTagEdit();
  };
  const action = pushUndo(message, undo, redo);
  toastAction(`${message} (${tagNotesWord(result.changed)}).`, "Undo", async () => {
    settleUndoFromToast(action);
    await undo();
  });
  return result;
}

//: A tag chosen from the others, or typed: the Merge into step. Answers the
//: name (an existing tag keeps its spelling) or null.
function chooseTagSheet({ label, sub, exclude = [], counts }) {
  return new Promise((resolve) => {
    let chosen = null;
    const skip = new Set(exclude.map((name) => name.toLowerCase()));
    openSheet({
      label,
      sub,
      name: "tag-choice",
      onClose: () => resolve(chosen),
      build: (card, close) => {
        const input = document.createElement("input");
        input.type = "text";
        input.maxLength = 60;
        input.placeholder = "Find a tag, or type a new one";
        input.setAttribute("aria-label", "Tag name");
        const list = document.createElement("div");
        list.className = "sheet-list";
        const pick = (name) => {
          chosen = name;
          close();
        };
        const draw = () => {
          const typed = input.value.trim().replace(/^#/, "");
          const needle = typed.toLowerCase();
          list.replaceChildren();
          const names = Object.keys(counts).filter((name) => !skip.has(name.toLowerCase()) && (!needle || name.toLowerCase().includes(needle)));
          for (const name of names.slice(0, 60)) list.appendChild(sheetRow("ph ph-hash", `${name} (${counts[name]})`, () => pick(name)));
          if (typed && !skip.has(needle) && !names.some((name) => name.toLowerCase() === needle)) {
            list.appendChild(sheetRow("ph ph-plus", `Use “${typed}” as a new tag`, () => pick(typed)));
          }
          if (!list.children.length) {
            const none = document.createElement("p");
            none.className = "muted";
            none.textContent = "There is no other tag yet. Type a name to make one.";
            list.appendChild(none);
          }
        };
        input.addEventListener("input", draw);
        input.addEventListener("keydown", (event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            list.querySelector(".sheet-row")?.focus();
          } else if (event.key === "Enter") {
            event.preventDefault();
            const typed = input.value.trim().replace(/^#/, "");
            if (!typed || skip.has(typed.toLowerCase())) return;
            pick(Object.keys(counts).find((name) => name.toLowerCase() === typed.toLowerCase()) || typed);
          }
        });
        draw();
        card.append(input, list);
      },
    });
  });
}

async function renameTagEverywhere(tag) {
  const counts = await fetchTagCounts();
  const answer = await promptDialog(`Rename the tag “${tag}” to:`, tag, { confirmLabel: "Rename" });
  const next = (answer || "").trim().replace(/^#/, "");
  if (!next || next === tag) return;
  const existing = Object.keys(counts).find((name) => name !== tag && name.toLowerCase() === next.toLowerCase());
  if (existing) {
    const ok = await confirmDialog(
      `“${existing}” already exists. Merge “${tag}” into it?\n\nThe ${tagNotesWord(counts[tag] || 0)} tagged “${tag}” will carry “${existing}” instead. Nothing is deleted.`,
      { confirmLabel: "Merge", danger: false }
    );
    if (!ok) return;
  }
  await runTagEdit(
    existing ? `Merged “${tag}” into “${existing}”` : `Renamed “${tag}” to “${next}”`,
    "/tags/rename",
    { old: tag, new: existing || next },
    { [tag]: existing || next }
  );
}

async function mergeTagsInto(names) {
  const counts = await fetchTagCounts();
  const target = await chooseTagSheet({
    label: names.length === 1 ? `Merge ${names[0]} into` : `Merge ${names.length} tags into`,
    sub: "Every note with these tags gets the one you choose, once. Nothing is deleted.",
    exclude: names,
    counts,
  });
  if (!target) return;
  await runTagEdit(`Merged ${tagNamesWords(names)} into “${target}”`, "/tags/merge", { names, into: target },
    Object.fromEntries(names.map((name) => [name, target])));
}

async function removeTagsEverywhere(names) {
  const counts = await fetchTagCounts();
  const total = names.length === 1 ? counts[names[0]] || 0 : null;
  const ok = await confirmDialog(
    names.length === 1
      ? `Remove the tag “${names[0]}” from the ${tagNotesWord(total)} that carry it?\n\nThe notes are untouched.`
      : `Remove ${nounCount(names.length, "tag")} (${tagNamesWords(names)}) from every note that carries them?\n\nThe notes are untouched.`,
    { confirmLabel: "Remove" }
  );
  if (!ok) return;
  await runTagEdit(`Removed ${tagNamesWords(names)} from every note`, "/tags/delete", { names },
    Object.fromEntries(names.map((name) => [name, null])));
}

//: The chip's "Remove from this note": the same call as the bulk dialog, for
//: one note, so it has a revision, an event and an Undo like the rest.
async function removeTagFromNote(entry, tag) {
  await runTagEdit(`Removed “${tag}” from this note`, "/tags/bulk", { ids: [entry.id], remove: [tag] });
}

function showTagNotes(name) {
  //: The notes are behind the manager, so it gets out of their way.
  document.querySelector('.sheet-overlay[data-sheet="tags"] .sheet-close')?.click();
  filterNotesByTag(name);
}

function tagMenuItems(name) {
  return [
    { label: "ph:eye Show notes", title: `Show every note tagged ${name}`, run: () => showTagNotes(name) },
    { label: "ph:pencil-simple Rename…", title: `Rename ${name} on every note that has it`, run: () => renameTagEverywhere(name) },
    { label: "ph:arrows-merge Merge into…", title: `Fold ${name} into another tag`, run: () => mergeTagsInto([name]) },
    { label: "ph:trash Remove from all notes…", title: `Take ${name} off every note; the notes are kept`, danger: true, group: "danger", run: () => removeTagsEverywhere([name]) },
  ];
}

// --- What both managers share (INBOX 504, the owner: "add more capablilty
// and utility to the manage tags and categories panels"): a sort, a filter
// for the ones that are hardly used, look-alike names offered as one merge,
// and a count that opens the notes. Here because the categories panel
// loads this module first (`openManageCategories`); a second file loaded by
// both would declare these twice.

//: The sorts, in the select's order. Recently used reads the notes already
//: in memory: the newest edit of a note that carries the name.
const MANAGE_SORTS = [
  ["name", "Name"],
  ["count", "Most notes"],
  ["recent", "Recently used"],
];

function manageStored(key, fallback) {
  try {
    return prefs.get(key, null) || fallback;
  } catch {
    return fallback;
  }
}

function manageStore(key, value) {
  try {
    prefs.set(key, value);
  } catch {
    // A blocked storage only forgets the choice.
  }
}

//: name -> the newest time a note carrying it was written to.
function manageRecent(namesOf) {
  const recent = new Map();
  for (const entry of allEntries) {
    if (entry.deleted_at) continue;
    const when = Date.parse(entry.updated_at || entry.created_at) || 0;
    for (const name of namesOf(entry)) if (when > (recent.get(name) || 0)) recent.set(name, when);
  }
  return recent;
}

function manageSorted(names, sort, countOf, recent) {
  const byName = (a, b) => a.localeCompare(b, undefined, { sensitivity: "base" });
  if (sort === "count") return names.sort((a, b) => countOf(b) - countOf(a) || byName(a, b));
  if (sort === "recent") return names.sort((a, b) => (recent.get(b) || 0) - (recent.get(a) || 0) || byName(a, b));
  return names.sort(byName);
}

//: The sort select and the hardly-used toggle, for the tool row.
function manageListControls({ sortKey, state, rareLabel, rareTitle, redraw }) {
  const select = document.createElement("select");
  select.className = "manage-cat-sort";
  select.setAttribute("aria-label", "Sort by");
  select.title = "Sort by";
  for (const [value, label] of MANAGE_SORTS) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  }
  select.value = state.sort;
  select.addEventListener("change", () => {
    state.sort = select.value;
    manageStore(sortKey, state.sort);
    redraw();
  });
  const rare = document.createElement("button");
  rare.type = "button";
  rare.className = "library-chip manage-cat-rare";
  rare.textContent = rareLabel;
  rare.title = rareTitle;
  rare.setAttribute("aria-pressed", "false");
  rare.addEventListener("click", () => {
    state.rare = !state.rare;
    rare.setAttribute("aria-pressed", String(state.rare));
    rare.classList.toggle("active", state.rare);
    redraw();
  });
  return [select, rare];
}

//: **Names that are probably one name**: the same once case, spaces,
//: hyphens and underscores are set aside and a plural is made singular
//: ("Idea", "ideas", "to-do", "todo"). Each group keeps the name with the
//: most notes first, which is the one the others would merge into.
function manageLookAlikeKey(name) {
  let key = String(name).toLowerCase().replace(/[\s_\-.]+/g, "");
  if (key.length > 3 && key.endsWith("ies")) key = `${key.slice(0, -3)}y`;
  else if (key.length > 3 && key.endsWith("s") && !key.endsWith("ss")) key = key.slice(0, -1);
  return key;
}

function manageLookAlikes(names, countOf) {
  const groups = new Map();
  for (const name of names) {
    const key = manageLookAlikeKey(name);
    if (!key) continue;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(name);
  }
  return [...groups.values()]
    .filter((group) => group.length > 1)
    .map((group) => group.sort((a, b) => countOf(b) - countOf(a) || a.localeCompare(b)));
}

//: The suggestions, above the list: one line per group, its names and one
//: Merge into the busiest of them, three at most with how many more there are.
//: "Not now" hides them until the panel is opened again.
function drawManageSuggestions(box, { groups, nouns, state, onMerge }) {
  box.replaceChildren();
  const show = groups.length > 0 && !state.hideSuggest;
  box.classList.toggle("hidden", !show);
  if (!show) return;
  const head = document.createElement("p");
  head.className = "manage-suggest-head";
  setLabel(head, `ph:copy-simple ${groups.length === 1 ? `These ${nouns} look like one` : `${groups.length} sets of ${nouns} look alike`}`);
  const later = smallButton("Not now", "Hide these suggestions until the panel is opened again", () => {
    state.hideSuggest = true;
    box.classList.add("hidden");
  });
  later.classList.add("manage-suggest-later");
  head.appendChild(later);
  box.appendChild(head);
  for (const group of groups.slice(0, 3)) {
    const row = document.createElement("div");
    row.className = "manage-suggest-row";
    const names = document.createElement("span");
    names.className = "manage-suggest-names";
    //: What goes where, in words: the busiest name keeps its notes.
    names.textContent = `${group.slice(1).join(", ")} into ${group[0]}`;
    names.title = names.textContent;
    const merge = smallButton("ph:arrows-merge Merge", `Fold ${names.textContent}`, () => onMerge(group[0], group.slice(1)));
    merge.setAttribute("aria-label", `Merge ${names.textContent}`);
    row.append(names, merge);
    box.appendChild(row);
  }
  if (groups.length > 3) {
    const more = document.createElement("p");
    more.className = "muted manage-suggest-more";
    more.textContent = `And ${groups.length - 3} more; merge these first.`;
    box.appendChild(more);
  }
}

//: The count after a name is the way to its notes: a quiet link-like button,
//: not a pill (INBOX 466), out of the tab order (Enter on the row does it).
function manageCountButton(count, onShow) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "manage-cat-count";
  button.tabIndex = -1;
  button.textContent = String(count);
  button.title = `Show the ${nounCount(count, "note")}`;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onShow();
  });
  button.addEventListener("dblclick", (event) => event.stopPropagation());
  return button;
}

//: The dialog head: the title, its '?' beside it, a ghost icon Close at the

//: right (the Manage categories panel's head, `manageCatHead`).
function tagManagerHead(card) {
  const head = card.querySelector(".sheet-head");
  if (!head) return;
  head.classList.add("dialog-head");
  const help = document.createElement("button");
  help.type = "button";
  help.className = "icon-only ghost small dialog-head-btn";
  help.setAttribute("data-help-for", "manage-tags-help");
  help.setAttribute("aria-controls", "manage-tags-help");
  help.setAttribute("aria-expanded", "false");
  help.title = "About managing tags";
  help.setAttribute("aria-label", "About managing tags");
  const icon = document.createElement("i");
  icon.className = "ph ph-question";
  icon.setAttribute("aria-hidden", "true");
  help.appendChild(icon);
  const closeButton = head.querySelector(".sheet-close");
  closeButton?.classList.add("dialog-head-btn");
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  if (closeButton) actions.appendChild(closeButton);
  head.querySelector(".sheet-title")?.after(help);
  head.appendChild(actions);
}

async function openTagsSheet(focusName = null) {
  const state = {
    counts: await fetchTagCounts(),
    selected: new Set(),
    active: focusName,
    filter: "",
    sort: manageStored("manage-tags-sort", "count"),
    rare: false,
    hideSuggest: false,
  };
  openSheet({
    label: "Manage tags",
    name: "tags",
    onClose: () => { tagManagerRedraw = null; },
    build: (card) => {
      card.classList.add("manage-cat-card");
      tagManagerHead(card);
      const sub = document.createElement("p");
      sub.className = "muted manage-cat-sub";
      sub.textContent = "Rename, merge or remove tags across every note. Your notes are always kept.";
      const helpBody = document.createElement("div");
      helpBody.className = "help-body hidden";
      helpBody.id = "manage-tags-help";
      helpBody.setAttribute("role", "dialog");
      helpBody.setAttribute("aria-label", "About managing tags");
      for (const line of [
        "Rename changes a tag on every note that has it. Renaming onto a tag that exists merges the two.",
        "Merge into folds one or more tags into another. Select several with Space to merge or remove them together. Tags that look like one (Idea and ideas, to-do and todo) are offered as one merge above the list.",
        "Sort by name, by how many notes carry a tag, or by the one used most recently. Used once shows the tags only one note carries, the usual place for a typo. The count after a tag shows its notes.",
        "Remove from all notes takes the tag off every note. The notes themselves are never deleted, and every change can be undone.",
        "To add or remove tags on particular notes, choose Select in the Notes list, tick them and press Tags. To change one note's tags, right-click a tag on its card.",
        "A suggested tag you turn down on three notes or more is offered less on every note. Turned down, under the list, lists them; Offer again puts one back.",
        "Keys: arrows move, Space selects, Enter shows the notes, F2 renames, Delete removes.",
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
      filter.placeholder = "Filter tags";
      filter.setAttribute("aria-label", "Filter tags");
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
      search.append(glass, filter, clear);
      tools.append(search, ...manageListControls({
        sortKey: "manage-tags-sort",
        state,
        rareLabel: "Used once",
        rareTitle: "Show only the tags one note carries",
        redraw,
      }));
      const suggest = document.createElement("div");
      suggest.className = "manage-suggest hidden";
      suggest.setAttribute("role", "region");
      suggest.setAttribute("aria-label", "Tags that look alike");
      state.suggestBox = suggest;
      const list = document.createElement("ul");
      list.className = "manage-cat-list";
      //: A grid, not a listbox (INBOX 433): each row carries its own ⋯.
      list.setAttribute("role", "grid");
      list.setAttribute("aria-multiselectable", "true");
      list.setAttribute("aria-label", "Tags");
      const footer = document.createElement("div");
      footer.className = "manage-cat-footer hidden";
      footer.setAttribute("role", "region");
      footer.setAttribute("aria-label", "Selected tags");
      const turnedDown = document.createElement("div");
      turnedDown.className = "manage-suggest hidden";
      turnedDown.setAttribute("role", "region");
      turnedDown.setAttribute("aria-label", "Tags turned down often");
      card.append(sub, helpBody, tools, suggest, list, footer, turnedDown);
      drawTurnedDown(turnedDown);
      initHelpToggles(card);
      function redraw() {
        drawTagRows(list, footer, state);
      }
      tagManagerRedraw = async () => {
        state.counts = await fetchTagCounts();
        redraw();
      };
      filter.addEventListener("input", () => {
        state.filter = filter.value.trim().replace(/^#/, "").toLowerCase();
        clear.classList.toggle("hidden", !filter.value);
        redraw();
      });
      filter.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          list.querySelector(".manage-cat-main")?.focus();
        }
      });
      wireTagKeys(list, state, redraw);
      redraw();
      const start = focusName ? list.querySelector(`[data-tag="${CSS.escape(focusName)}"] > .manage-cat-main`) : null;
      requestAnimationFrame(() => (start || filter).focus());
    },
  });
}

//: **Learning from turn-downs, with a way back** (INBOX 781). A suggested tag
//: discarded on several notes is offered less everywhere (`ai/tagging.py`,
//: `TURNED_DOWN_OFTEN`); this lists those, the look-alike rows' recipe, and
//: Offer again forgets the turn-downs so far.
async function drawTurnedDown(box) {
  const rows = ((await apiJson("/tags/turned-down", { silent: true }).catch(() => [])) || []).filter((row) => row.damped);
  box.replaceChildren();
  box.classList.toggle("hidden", !rows.length);
  if (!rows.length) return;
  const head = document.createElement("p");
  head.className = "manage-suggest-head";
  setLabel(head, "ph:thumbs-down Turned down: offered less");
  box.appendChild(head);
  for (const { tag, notes } of rows.slice(0, 5)) {
    const row = document.createElement("div");
    row.className = "manage-suggest-row";
    const names = document.createElement("span");
    names.className = "manage-suggest-names";
    names.textContent = `${tag}, turned down on ${nounCount(notes, "note")}`;
    const again = smallButton("ph:arrow-counter-clockwise Offer again", `Suggest ${tag} as before`, async () => {
      try {
        await apiJson("/tags/turned-down/offer-again", { method: "POST", body: JSON.stringify({ tag }) });
        toast(`${tag} is suggested again.`);
      } catch (error) {
        toast(`Could not offer ${tag} again: ${error.message}`, true);
      }
      drawTurnedDown(box);
    });
    again.setAttribute("aria-label", `Offer again: ${tag}`);
    row.append(names, again);
    box.appendChild(row);
  }
}

function drawTagRows(list, footer, state) {
  const hadFocus = list.contains(document.activeElement) ? document.activeElement.closest("[data-tag]")?.dataset.tag || null : null;
  list.replaceChildren();
  const countOf = (name) => state.counts[name] || 0;
  const recent = state.sort === "recent" ? manageRecent((entry) => entry.tags || []) : null;
  const names = manageSorted(
    Object.keys(state.counts).filter(
      (name) => (!state.filter || name.toLowerCase().includes(state.filter)) && (!state.rare || countOf(name) === 1)
    ),
    state.sort,
    countOf,
    recent
  );
  for (const name of [...state.selected]) if (!(name in state.counts)) state.selected.delete(name);
  if (state.suggestBox) {
    drawManageSuggestions(state.suggestBox, {
      groups: manageLookAlikes(Object.keys(state.counts), countOf),
      nouns: "tags",
      state,
      onMerge: (into, names) =>
        runTagEdit(`Merged ${tagNamesWords(names)} into “${into}”`, "/tags/merge", { names, into },
          Object.fromEntries(names.map((name) => [name, into]))),
    });
  }
  if (!names.length) {
    const none = document.createElement("li");
    none.className = "muted manage-cat-empty";
    none.setAttribute("role", "row");
    const cell = document.createElement("span");
    cell.setAttribute("role", "gridcell");
    cell.textContent = state.filter
      ? "No tag matches that."
      : state.rare
        ? "Every tag is on more than one note."
        : `No tags yet. Add some to a note, or let ${aiNameNow()} suggest them as you write.`;
    none.appendChild(cell);
    list.appendChild(none);
  }
  const current = names.includes(hadFocus || state.active) ? hadFocus || state.active : names[0];
  for (const name of names) {
    const count = state.counts[name];
    const li = document.createElement("li");
    li.className = "manage-cat-row";
    li.dataset.tag = name;
    li.setAttribute("role", "row");
    li.setAttribute("aria-selected", String(state.selected.has(name)));
    const main = document.createElement("span");
    main.className = "manage-cat-main";
    main.setAttribute("role", "gridcell");
    main.tabIndex = name === current ? 0 : -1;
    main.setAttribute("aria-label", `${name}, ${tagNotesWord(count)}`);
    const glyph = document.createElement("i");
    glyph.className = "ph ph-hash manage-tag-glyph";
    glyph.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.className = "manage-cat-name";
    label.textContent = `${name} `;
    label.title = name;
    main.append(glyph, label, manageCountButton(count, () => showTagNotes(name)));
    li.appendChild(main);
    const menu = kebabMenu(tagMenuItems(name), `Actions for ${name}`, { vertical: true });
    menu.classList.add("manage-cat-menu");
    menu.setAttribute("role", "gridcell");
    menu.addEventListener("click", (event) => event.stopPropagation());
    menu.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "ArrowLeft" && event.target === menu.querySelector(":scope > button")) {
        event.preventDefault();
        main.focus();
      }
    });
    li.appendChild(menu);
    //: A click selects (Ctrl or Shift adds); a double click shows the notes.
    li.addEventListener("click", (event) => {
      if (!(event.ctrlKey || event.metaKey || event.shiftKey)) {
        const only = state.selected.size === 1 && state.selected.has(name);
        state.selected.clear();
        if (!only) state.selected.add(name);
      } else if (state.selected.has(name)) state.selected.delete(name);
      else state.selected.add(name);
      state.active = name;
      drawTagRows(list, footer, state);
      list.querySelector(`[data-tag="${CSS.escape(name)}"] > .manage-cat-main`)?.focus();
    });
    li.addEventListener("dblclick", () => showTagNotes(name));
    list.appendChild(li);
  }
  if (hadFocus) list.querySelector(`[data-tag="${CSS.escape(hadFocus)}"] > .manage-cat-main`)?.focus();
  drawTagFooter(footer, state, () => drawTagRows(list, footer, state));
}

function wireTagKeys(list, state, redraw) {
  list.addEventListener("keydown", (event) => {
    if (!event.target.matches?.(".manage-cat-main")) return;
    const row = event.target.closest("[data-tag]");
    if (!row) return;
    const rows = [...list.querySelectorAll(".manage-cat-row")];
    const at = rows.indexOf(row);
    const move = (to) => {
      const next = rows[Math.max(0, Math.min(rows.length - 1, to))];
      if (!next) return;
      for (const r of rows) r.querySelector(":scope > .manage-cat-main").tabIndex = r === next ? 0 : -1;
      state.active = next.dataset.tag;
      next.querySelector(":scope > .manage-cat-main").focus();
      next.scrollIntoView({ block: "nearest" });
    };
    const name = row.dataset.tag;
    if (event.key === "ArrowDown") move(at + 1);
    else if (event.key === "ArrowUp") move(at - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(rows.length - 1);
    else if (event.key === "ArrowRight") row.querySelector(".manage-cat-menu > button")?.focus();
    else if (event.key === " ") {
      if (state.selected.has(name)) state.selected.delete(name);
      else state.selected.add(name);
      redraw();
    } else if (event.key === "Enter") showTagNotes(name);
    else if (event.key === "F2") renameTagEverywhere(name);
    else if (event.key === "Delete" || event.key === "Backspace") removeTagsEverywhere([name]);
    else if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) row.querySelector(".manage-cat-menu > button")?.click();
    else return;
    event.preventDefault();
  });
}

function drawTagFooter(footer, state, redraw) {
  footer.replaceChildren();
  const names = [...state.selected].filter((name) => name in state.counts);
  footer.classList.toggle("hidden", names.length === 0);
  if (!names.length) return;
  const label = document.createElement("span");
  label.className = "manage-cat-footer-label";
  label.textContent = `${names.length} selected`;
  const clear = smallButton("Clear", "Clear the selection", () => {
    state.selected.clear();
    redraw();
  });
  const remove = smallButton("ph:trash Remove…", "Take the selected tags off every note; the notes are kept", async () => {
    await removeTagsEverywhere(names);
    state.selected.clear();
    redraw();
  });
  const merge = smallButton("ph:arrows-merge Merge into…", "Fold the selected tags into one tag", async () => {
    await mergeTagsInto(names);
    state.selected.clear();
    redraw();
  }, false);
  footer.append(label, clear, remove, merge);
}

//: **Tags for the selected notes** (INBOX 447 (4)): one dialog, one action.
//: Tags to add (typed, with the tag list under the field) and tags to take
//: off (a tick each, with how many of the notes carry it), applied together
//: by `POST /tags/bulk` in one transaction, with one Undo.
function openBulkTags(ids) {
  const noteIds = (Array.isArray(ids) ? ids : [ids]).map(Number).filter(Boolean);
  if (!noteIds.length) return;
  const held = new Map();
  for (const id of noteIds) {
    for (const tag of allEntries.find((e) => e.id === id)?.tags || []) {
      const key = tag.toLowerCase();
      const have = held.get(key) || { name: tag, count: 0 };
      have.count += 1;
      held.set(key, have);
    }
  }
  const present = [...held.values()].sort((a, b) => b.count - a.count || compareCategoryNames(a.name, b.name));
  openSheet({
    label: `Tags for ${tagNotesWord(noteIds.length)}`,
    sub: "Add tags to every selected note, take tags off them, or both. One Undo covers all of it.",
    name: "bulk-tags",
    build: (card, close) => {
      const form = document.createElement("form");
      form.className = "manage-split";
      const addLabel = document.createElement("label");
      addLabel.className = "bulk-tags-field";
      const addWord = document.createElement("span");
      addWord.textContent = "Add to all";
      const add = document.createElement("input");
      add.type = "text";
      add.placeholder = "Tags, separated by commas";
      add.autocomplete = "off";
      add.maxLength = 600;
      addLabel.append(addWord, add);
      //: The tag list under the field (tag-suggest.js, lazy).
      for (const type of ["focusin", "input", "click"]) add.addEventListener(type, () => openTagSuggest(add));
      const group = document.createElement("fieldset");
      group.className = "bulk-tags-remove";
      const legend = document.createElement("legend");
      legend.textContent = "Remove from all";
      group.appendChild(legend);
      const boxes = new Map();
      if (!present.length) {
        const none = document.createElement("p");
        none.className = "muted";
        none.textContent = "None of these notes has a tag yet.";
        group.appendChild(none);
      }
      const list = document.createElement("div");
      list.className = "sheet-list manage-split-list";
      for (const tag of present) {
        const row = document.createElement("label");
        row.className = "checkbox-label manage-split-note";
        const box = document.createElement("input");
        box.type = "checkbox";
        boxes.set(tag.name, box);
        const text = document.createElement("span");
        text.className = "manage-split-text";
        text.textContent = `#${tag.name}`;
        const on = document.createElement("span");
        on.className = "muted";
        on.textContent = tag.count === noteIds.length ? "all of them" : `${tag.count} of ${noteIds.length}`;
        row.append(box, text, on);
        list.appendChild(row);
      }
      if (present.length) group.appendChild(list);
      const actions = document.createElement("div");
      actions.className = "row confirm-actions";
      const cancel = smallButton("Cancel", "Close without changing any tags", () => close());
      cancel.type = "button";
      const apply = document.createElement("button");
      apply.type = "submit";
      apply.className = "small";
      apply.textContent = "Apply";
      actions.append(cancel, apply);
      form.append(addLabel, group, actions);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        //: Split on commas as the edit form does (INBOX 432), kept once.
        const added = [...new Set(add.value.split(",").map((t) => t.trim().replace(/^#/, "")).filter(Boolean))];
        const removed = [...boxes].filter(([, box]) => box.checked).map(([name]) => name);
        if (!added.length && !removed.length) {
          toast("Type a tag to add, or tick one to remove.", "info");
          return;
        }
        if (apply.disabled) return;
        setBusy(apply, true);
        const parts = [];
        if (added.length) parts.push(`Added ${tagNamesWords(added)}`);
        if (removed.length) parts.push(`${added.length ? "removed" : "Removed"} ${tagNamesWords(removed)}`);
        const message = parts.join("; ");
        const result = await runTagEdit(message, "/tags/bulk", { ids: noteIds, add: added, remove: removed });
        setBusy(apply, false);
        if (!result) return;
        close();
        if (selectMode) exitSelectMode();
      });
      card.appendChild(form);
      setTimeout(() => add.focus(), 0);
    },
  });
}
