// library-links.js: the Links tab's look, card, folders and views (INBOX 827 L3 to L6). Loaded with
// library.js (`LAZY_MODULES.libraryList`), after it: library.js's `bookmarkRow`, `renderBookmarkGroupChips`
// and `filterBookmarks` call `LinkShelf`, and this file uses their globals (`bookmarksCache`,
// `renderBookmarks`, `pushBookmarksPutUndo`) at run time only. Wrapped whole: one export.
//
// A link and a folder each take an icon and a highlight colour from one small dialog. The colour is a
// palette key drawn from `LOOKS` below (set as `--swatch`, the token the app's swatches share), never a free
// colour, so both themes stay readable. A
// folder is still the `group_name` a link carries (no table): nesting is one level, "Parent/Child".
(() => {
  //: Medium lightness, so the tint and the glyph read on both grounds. The keys are what the server keeps.
  const LOOKS = {
    red: "oklch(0.62 0.19 25)", orange: "oklch(0.68 0.16 55)", yellow: "oklch(0.76 0.15 95)",
    green: "oklch(0.62 0.15 150)", teal: "oklch(0.63 0.11 195)", blue: "oklch(0.6 0.16 255)",
    purple: "oklch(0.6 0.18 300)", pink: "oklch(0.66 0.18 350)", gray: "oklch(0.6 0.02 260)",
  };
  const FOLDER_LOOKS_KEY = "library-links-folder-looks";
  const VIEW_KEY = "library-links-view";
  const LINK_DRAG = "application/x-tessellate-link";
  const FOLDER_DRAG = "application/x-tessellate-folder";

  // ---- look: icon and colour ----------------------------------------------------------------------------

  function withLook(el, color) {
    const value = LOOKS[color];
    if (value) el.style.setProperty("--swatch", value);
    else el.style.removeProperty("--swatch");
    el.classList.toggle("has-look", Boolean(value));
  }

  //: What a mark shows, first match wins: the icon the person chose, the site's own icon when the last
  //: fetch found one, the glyph of the link's kind. The favicon is a data address the server fetched at
  //: save (web on only), so drawing it asks the network for nothing.
  function fillMark(mark, item, fallback) {
    withLook(mark, item.color);
    const icon = item.icon || "";
    mark.replaceChildren();
    mark.classList.remove("has-favicon");
    if (icon.startsWith("ph:")) setLabel(mark, icon);
    else if (icon) mark.textContent = icon;
    else if (item.favicon) {
      const img = document.createElement("img");
      img.src = item.favicon;
      img.alt = "";
      img.className = "bookmark-favicon";
      img.addEventListener("error", () => setLabel(mark, fallback), { once: true });
      mark.append(img);
      mark.classList.add("has-favicon");
    } else setLabel(mark, fallback);
  }

  //: The app's one swatch picker (categories bundle), over this file's palette; "No colour" clears it.
  function swatches(value, onPick) {
    const group = document.createElement("div");
    group.className = "look-swatches";
    let picker = null;
    const build = (current) => {
      picker = swatchPicker({ label: "Highlight colour", value: current || null, palette: LOOKS, none: "No colour", onChoose: (key) => onPick(key || "") });
      group.replaceChildren(picker);
    };
    //: The picker lives in the categories bundle; the dialog draws the row as soon as it is here.
    ensureModule("categories").then(() => build(value));
    return { group, mark: (current) => picker && build(current) };
  }

  //: The look dialog for a link or a folder. `change(patch)` writes it (the caller saves and repaints); the
  //: dialog keeps its own copy so the preview follows every press without waiting for the list to reload.
  function chooseLook({ title, icon, color, fallback, favicon = "", change }) {
    const state = { icon: icon || "", color: color || "" };
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Icon and colour");
    const card = document.createElement("div");
    card.className = "card modal-card confirm-card look-card";
    //: The head is the app's `.dialog-head` recipe (title and Close).
    const returnFocus = document.activeElement;
    let settled = false;
    const close = () => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      returnFocus?.focus?.();
    };
    const onKey = (event) => {
      if (event.key === "Escape" && !document.querySelector(".icon-picker")) {
        event.preventDefault();
        event.stopPropagation();
        close();
      }
    };
    const name = document.createElement("p");
    name.className = "look-card-name";
    const preview = document.createElement("span");
    preview.className = "bookmark-mark look-preview";
    preview.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = title;
    name.append(preview, label);
    const paint = () => {
      fillMark(preview, { ...state, favicon }, fallback);
      colours.mark(state.color);
      clearIcon.hidden = !state.icon;
    };
    const apply = async (patch) => {
      Object.assign(state, patch);
      paint();
      await change(patch);
    };
    const colours = swatches(state.color, (key) => apply({ color: key }));
    const row = document.createElement("div");
    row.className = "row look-card-actions";
    const pick = smallButton("ph:smiley Choose an icon", "Pick an icon or an emoji", () => {
      pickIconOrEmoji({
        anchor: pick,
        title: "Icon",
        onPick: ({ kind, value }) => apply({ icon: kind === "icon" ? `ph:${value}` : value }),
      });
    });
    const clearIcon = smallButton("Automatic icon", favicon ? "Use the site's own icon" : "Use the icon for this kind of link", () => apply({ icon: "" }));
    row.append(pick, clearIcon);
    const done = document.createElement("div");
    done.className = "row confirm-actions";
    done.append(smallButton("Done", "Close", close, false));
    card.append(dialogHead("Icon and colour", close), name, colours.group, row, done);
    overlay.append(card);
    wireBackdropClose(overlay, close);
    document.addEventListener("keydown", onKey, true);
    document.body.append(overlay);
    paint();
    pick.focus();
  }

  function chooseBookmarkLook(bookmark, kind) {
    chooseLook({
      title: bookmark.title || bookmark.url,
      icon: bookmark.icon,
      color: bookmark.color,
      favicon: bookmark.favicon,
      fallback: kind.icon,
      change: async (patch) => {
        const before = { icon: bookmark.icon || "", color: bookmark.color || "" };
        const body = { ...before, ...patch };
        Object.assign(bookmark, body);
        await apiJson(`/bookmarks/${bookmark.id}`, { method: "PUT", body: JSON.stringify(body) });
        pushBookmarksPutUndo("Changed a bookmark's icon or colour", [{ id: bookmark.id, before, after: body }]);
        renderBookmarks();
      },
    });
  }

  // ---- the details card ---------------------------------------------------------------------------------

  const siteOf = (url) => bookmarkAddress(url).site || "";

  //: The link as a card: its icon and title, the site, two lines of what the page said, and the whole text
  //: only behind "Show page text" (it can be long, and the list never carries it).
  function detailsCard(bookmark, { kind, done }) {
    const box = document.createElement("div");
    box.className = "bookmark-detail bookmark-card-detail";
    const head = document.createElement("div");
    head.className = "bookmark-detail-head";
    const mark = document.createElement("span");
    mark.className = "bookmark-mark bookmark-detail-mark";
    mark.setAttribute("aria-hidden", "true");
    fillMark(mark, bookmark, kind.icon);
    const names = document.createElement("div");
    names.className = "bookmark-detail-names";
    const title = document.createElement("strong");
    title.textContent = bookmark.title || siteOf(bookmark.url);
    const site = document.createElement("span");
    site.className = "muted text-sm";
    site.textContent = siteOf(bookmark.url);
    names.append(title, site);
    head.append(mark, names);
    box.append(head);
    if (bookmark.excerpt) {
      const excerpt = document.createElement("p");
      excerpt.className = "bookmark-detail-excerpt";
      excerpt.textContent = bookmark.excerpt;
      box.append(excerpt);
    }
    const addr = document.createElement("code");
    addr.className = "bookmark-detail-url";
    addr.textContent = bookmark.url;
    box.append(addr);
    const facts = [kind.label];
    if (bookmark.group_name) facts.push(bookmark.group_name.split("/").join(" / "));
    if ((bookmark.tags || []).length) facts.push(bookmark.tags.map((tag) => `#${tag}`).join(" "));
    const saved = new Date(bookmark.created_at);
    if (!Number.isNaN(saved.getTime())) facts.push(`saved ${saved.toLocaleDateString()}`);
    facts.push(bookmark.is_read ? "read" : "unread");
    box.append(metaLine(facts, "bookmark-detail-meta"));
    if (bookmark.note) {
      const note = document.createElement("p");
      note.className = "bookmark-detail-note";
      note.textContent = bookmark.note;
      box.append(note);
    }
    const actions = document.createElement("div");
    actions.className = "row bookmark-detail-actions";
    const text = document.createElement("div");
    text.className = "bookmark-detail-text hidden";
    if (bookmark.has_text) {
      const show = smallButton("ph:article Show page text", "Read the text kept from this page", async () => {
        const opening = text.classList.contains("hidden");
        text.classList.toggle("hidden", !opening);
        setLabel(show, opening ? "ph:article Hide page text" : "ph:article Show page text");
        show.setAttribute("aria-expanded", String(opening));
        if (opening && !text.childElementCount) await readText(bookmark, text);
      });
      show.setAttribute("aria-expanded", "false");
      actions.append(show);
    }
    actions.append(
      smallButton("ph:arrows-clockwise Refresh", "Fetch the page again for its icon and text (needs the web switched on)", () => refresh(bookmark, done)),
      smallButton("ph:palette Icon and colour", "Choose an icon and a highlight colour", () => chooseBookmarkLook(bookmark, kind)),
    );
    box.append(actions, text);
    return box;
  }

  async function readText(bookmark, holder) {
    let body = "";
    try {
      body = (await apiJson(`/bookmarks/${bookmark.id}/text`)).text || "";
    } catch (error) {
      toast(error.message, true, { retry: () => readText(bookmark, holder) });
      return;
    }
    const reading = document.createElement("div");
    reading.className = "library-file-reading-text bookmark-page-text";
    reading.tabIndex = 0;
    reading.setAttribute("aria-label", "Page text");
    for (const part of body.split(/\n{2,}/)) {
      if (!part.trim()) continue;
      const p = document.createElement("p");
      p.className = "library-file-page-text";
      p.textContent = part.trim();
      reading.append(p);
    }
    holder.append(reading);
    //: After the card is in the page, so the column has a height to measure.
    setTimeout(() => {
      if (reading.isConnected && reading.scrollHeight > reading.clientHeight + 1) holder.insertBefore(buildReadingFind(reading), reading);
    }, 0);
    const copy = smallButton("ph:copy Copy text", "Copy the page text", async () => {
      if (await copyToClipboard(body)) toast("Page text copied.");
    });
    holder.append(copy);
  }

  async function refresh(bookmark, done) {
    try {
      await apiJson(`/bookmarks/${bookmark.id}/refresh`, { method: "POST" });
      toast("Fetched the page again.", "info");
    } catch (error) {
      toast(error.message, true);
      return;
    }
    done?.();
  }

  //: A save fetches the page behind the answer, when the web is on, so the icon arrives a moment later:
  //: one quiet reload then, unless the person is in the middle of something.
  function afterSave() {
    setTimeout(() => {
      if (document.querySelector(".bookmark-edit-form, .bookmark-folder-edit, .look-card, .modal-overlay")) return;
      renderBookmarks();
    }, 2500);
  }

  // ---- folders ------------------------------------------------------------------------------------------

  const inFolder = (group, folder) => Boolean(group) && (group === folder || group.startsWith(`${folder}/`));
  const leaf = (name) => name.slice(name.lastIndexOf("/") + 1);
  const parentOf = (name) => (name.includes("/") ? name.slice(0, name.indexOf("/")) : "");

  function folderLooks() {
    try {
      const stored = prefs.json(FOLDER_LOOKS_KEY, {});
      return stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
    } catch {
      return {};
    }
  }
  const folderLook = (name) => folderLooks()[name] || {};
  function setFolderLook(name, look) {
    const all = folderLooks();
    if (look.icon || look.color) all[name] = { icon: look.icon || "", color: look.color || "" };
    else delete all[name];
    prefs.set(FOLDER_LOOKS_KEY, JSON.stringify(all));
  }

  //: Every folder the chips show: the names links carry, the empty ones, and the parent of a nested name
  //: (a "Work/Reading" link makes a Work folder even if nothing sits directly in it).
  function folders(names) {
    const all = new Set(names);
    for (const name of names) if (parentOf(name)) all.add(parentOf(name));
    return [...all].sort();
  }
  const countIn = (name) => bookmarksCache.filter((b) => inFolder(b.group_name, name)).length;

  //: Rename or move a folder: its links, its nested folders, its look and its empty-folder placeholder, as one
  //: step on the undo stack. Nesting is one level: a folder with children cannot go inside another.
  async function moveFolder(from, to) {
    to = to.trim().replace(/\s*\/\s*/g, "/");
    if (!to || to === from) return false;
    if (to.split("/").length > 2 || to.split("/").some((part) => !part)) {
      toast("Folders nest one level: a folder can go inside another, not inside a nested one.", "info");
      return false;
    }
    const hasChildren = folders(allBookmarkGroups()).some((name) => name.startsWith(`${from}/`));
    if (to.includes("/") && (from.includes("/") ? false : hasChildren)) {
      toast("That folder has folders of its own, so it cannot go inside another.", "info");
      return false;
    }
    if (folders(allBookmarkGroups()).includes(to)) {
      toast(`A folder called “${to}” already exists.`, "info");
      return false;
    }
    const written = [];
    for (const bookmark of bookmarksCache.filter((b) => inFolder(b.group_name, from))) {
      const next = to + bookmark.group_name.slice(from.length);
      try {
        await apiJson(`/bookmarks/${bookmark.id}`, { method: "PUT", body: JSON.stringify({ group_name: next }) });
        written.push({ id: bookmark.id, before: { group_name: bookmark.group_name }, after: { group_name: next } });
      } catch (error) {
        toast(error.message, true);
      }
    }
    const renamed = (name) => (inFolder(name, from) ? to + name.slice(from.length) : name);
    setEmptyBookmarkGroups(emptyBookmarkGroups().map(renamed).concat(written.length ? [] : [to]));
    const looks = folderLooks();
    for (const key of Object.keys(looks)) {
      if (inFolder(key, from)) {
        looks[renamed(key)] = looks[key];
        delete looks[key];
      }
    }
    prefs.set(FOLDER_LOOKS_KEY, JSON.stringify(looks));
    if (bookmarkScope.group && inFolder(bookmarkScope.group, from)) bookmarkScope.group = renamed(bookmarkScope.group);
    if (written.length) pushBookmarksPutUndo(`Moved the folder “${from}”`, written);
    await renderBookmarks();
    return true;
  }

  async function putGroup(links, group, label) {
    const written = [];
    for (const link of links) {
      if ((link.group_name || "") === group) continue;
      try {
        await apiJson(`/bookmarks/${link.id}`, { method: "PUT", body: JSON.stringify({ group_name: group }) });
        written.push({ id: link.id, before: { group_name: link.group_name || "" }, after: { group_name: group } });
      } catch (error) {
        toast(error.message, true);
      }
    }
    if (written.length) pushBookmarksPutUndo(label, written);
    libraryLinksSelection.clear();
    await renderBookmarks();
    return written.length;
  }

  //: Which links a drag carries: the ticked ones when the dragged link is among them, else just it.
  function draggedLinks(id) {
    const ids = libraryLinksSelection.has(id) ? [...libraryLinksSelection.keys()] : [id];
    return bookmarksCache.filter((b) => ids.includes(b.id));
  }

  const dragKind = (event) => {
    const types = [...(event.dataTransfer?.types || [])];
    return types.includes(LINK_DRAG) ? "link" : types.includes(FOLDER_DRAG) ? "folder" : "";
  };

  function dropTarget(el, accept, onDrop) {
    el.addEventListener("dragover", (event) => {
      const kind = dragKind(event);
      if (!kind || !accept(kind)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      el.classList.add("is-drop-target");
    });
    el.addEventListener("dragleave", () => el.classList.remove("is-drop-target"));
    el.addEventListener("drop", (event) => {
      el.classList.remove("is-drop-target");
      const kind = dragKind(event);
      if (!kind || !accept(kind)) return;
      event.preventDefault();
      event.stopPropagation();
      onDrop(kind, event.dataTransfer.getData(kind === "link" ? LINK_DRAG : FOLDER_DRAG));
    });
  }

  //: A row drags (alone or with the ticked ones) and takes a drop: a link on a link files both together,
  //: in the folder the target is in, or in a new one named on the spot.
  function wireRow(row, bookmark) {
    row.draggable = true;
    row.addEventListener("dragstart", (event) => {
      if (event.target.closest?.("input, form, textarea")) {
        event.preventDefault();
        return;
      }
      event.dataTransfer.setData(LINK_DRAG, String(bookmark.id));
      event.dataTransfer.setData("text/plain", bookmark.url);
      event.dataTransfer.effectAllowed = "move";
      row.classList.add("is-dragging");
    });
    row.addEventListener("dragend", () => row.classList.remove("is-dragging"));
    dropTarget(row, (kind) => kind === "link", async (_kind, raw) => {
      const id = Number(raw);
      if (id === bookmark.id) return;
      const links = draggedLinks(id);
      if (links.some((link) => link.id === bookmark.id)) return;
      let folder = bookmark.group_name;
      if (!folder) {
        folder = (await promptDialog("Name for the new folder", "New folder")).trim();
        if (!folder) return;
        links.push(bookmark);
      }
      const moved = await putGroup(links, folder, `Filed bookmarks in “${folder}”`);
      if (moved) toast(`Filed ${nounCount(moved, "bookmark")} in “${folder}”.`);
    });
  }

  function wireChip(chip, folder) {
    if (folder === null) {
      //: All: a link dropped here leaves its folder; a nested folder moves up to the top.
      dropTarget(chip, () => true, async (kind, raw) => {
        if (kind === "link") await putGroup(draggedLinks(Number(raw)), "", "Took bookmarks out of their folder");
        else if (raw.includes("/")) await moveFolder(raw, leaf(raw));
      });
      return;
    }
    chip.draggable = true;
    chip.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData(FOLDER_DRAG, folder);
      event.dataTransfer.effectAllowed = "move";
      chip.classList.add("is-dragging");
    });
    chip.addEventListener("dragend", () => chip.classList.remove("is-dragging"));
    chip.addEventListener("keydown", (event) => {
      if (event.key === "F2") {
        event.preventDefault();
        renameInPlace(chip, folder);
      }
    });
    dropTarget(chip, (kind) => kind === "link" || !folder.includes("/"), async (kind, raw) => {
      if (kind === "link") {
        const moved = await putGroup(draggedLinks(Number(raw)), folder, `Filed bookmarks in “${folder}”`);
        if (moved) toast(`Filed ${nounCount(moved, "bookmark")} in “${folder}”.`);
      } else if (raw !== folder && !raw.startsWith(`${folder}/`)) {
        await moveFolder(raw, `${folder}/${leaf(raw)}`);
      }
    });
  }

  //: The chip becomes a field: Enter keeps the name, Escape and a click away leave it as it was.
  function renameInPlace(chip, folder) {
    if (chip.querySelector("input")) return;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "bookmark-folder-edit";
    input.value = leaf(folder);
    input.setAttribute("aria-label", `Rename the folder “${folder}”`);
    chip.replaceWith(input);
    let finished = false;
    const finish = async (keep) => {
      if (finished) return;
      finished = true;
      const name = input.value.trim().replace(/\//g, "");
      if (keep && name && name !== leaf(folder)) {
        const parent = parentOf(folder);
        if (await moveFolder(folder, parent ? `${parent}/${name}` : name)) return;
      }
      renderBookmarkGroupChips();
    };
    input.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Enter") finish(true);
      else if (event.key === "Escape") finish(false);
    });
    input.addEventListener("click", (event) => event.stopPropagation());
    input.addEventListener("blur", () => finish(true));
    input.focus();
    input.select();
  }

  //: New folder: made at once as an empty folder and opened for its name, so naming it is typing, not a dialog.
  async function newFolder(parent = "") {
    const taken = new Set(folders(allBookmarkGroups()));
    let name = parent ? `${parent}/New folder` : "New folder";
    for (let n = 2; taken.has(name); n++) name = `${parent ? `${parent}/` : ""}New folder ${n}`;
    setEmptyBookmarkGroups([...emptyBookmarkGroups(), name]);
    bookmarkScope.group = name;
    const groupInput = $("bookmark-group-input");
    if (groupInput) groupInput.value = name;
    await renderBookmarks();
    const chip = [...document.querySelectorAll("#bookmark-group-chips [data-folder]")].find((el) => el.dataset.folder === name);
    if (chip) renameInPlace(chip, name);
  }

  function chooseFolderLook(folder) {
    const look = folderLook(folder);
    chooseLook({
      title: folder.split("/").join(" / "),
      icon: look.icon,
      color: look.color,
      fallback: "ph:folder-simple",
      change: async (patch) => {
        setFolderLook(folder, { ...folderLook(folder), ...patch });
        renderBookmarkGroupChips();
      },
    });
  }

  async function deleteFolder(folder) {
    const links = bookmarksCache.filter((b) => inFolder(b.group_name, folder));
    const ok = await confirmDialog(
      links.length
        ? `Delete the folder “${folder}”? Its ${nounCount(links.length, "bookmark")} stay: they just stop being filed.`
        : `Delete the empty folder “${folder}”?`
    );
    if (!ok) return;
    setEmptyBookmarkGroups(emptyBookmarkGroups().filter((name) => !inFolder(name, folder)));
    setFolderLook(folder, {});
    if (bookmarkScope.group && inFolder(bookmarkScope.group, folder)) bookmarkScope.group = null;
    await putGroup(links, "", `Deleted the folder “${folder}”`);
  }

  //: The bar over the list while a folder is open: its name and one menu for what you do to a folder.
  function scopeBar() {
    const bar = $("bookmark-folder-bar");
    if (!bar) return;
    const folder = bookmarkScope.group;
    bar.replaceChildren();
    bar.classList.toggle("hidden", !folder && !bookmarkScope.dupes);
    if (bookmarkScope.dupes) {
      const say = document.createElement("span");
      say.className = "muted text-sm";
      say.textContent = `${nounCount(duplicateSets().length, "address")} saved more than once, side by side.`;
      bar.append(say, smallButton("ph:broom Keep one of each", "Delete the extra copies; the pinned or unread one stays, else the oldest", keepOneOfEach));
      return;
    }
    if (!folder) return;
    const look = folderLook(folder);
    const mark = document.createElement("span");
    mark.className = "bookmark-mark";
    mark.setAttribute("aria-hidden", "true");
    fillMark(mark, look, "ph:folder-simple");
    const name = document.createElement("strong");
    name.textContent = folder.split("/").join(" / ");
    const items = [
      { ...makeMenuItem("ph:palette Icon and colour", "Choose an icon and a colour for this folder", () => chooseFolderLook(folder)), group: "change" },
      { ...makeMenuItem("ph:pencil-simple Rename", "Rename this folder (double-click its chip to do it in place)", () => {
        const chip = [...document.querySelectorAll("#bookmark-group-chips [data-folder]")].find((el) => el.dataset.folder === folder);
        if (chip) renameInPlace(chip, folder);
      }), group: "change" },
    ];
    if (!folder.includes("/")) {
      items.push({ ...makeMenuItem("ph:folder-plus New folder inside", "Make a folder inside this one", () => newFolder(folder)), group: "change" });
    }
    items.push({ ...makeMenuItem("ph:trash Delete folder", "Delete the folder and keep its bookmarks", () => deleteFolder(folder)), danger: true, group: "danger" });
    bar.append(mark, name, kebabMenu(items, `Actions for the folder ${folder}`));
  }

  //: One chip per folder: its icon, its name, its count; a drag source and a drop target.
  function folderChip(box, name, active, onPress) {
    const look = folderLook(name);
    const chip = document.createElement("button");
    chip.type = "button";
    chip.dataset.folder = name;
    chip.className = `library-chip bookmark-folder-chip${active ? " active" : ""}`;
    withLook(chip, look.color);
    chip.setAttribute("aria-pressed", active ? "true" : "false");
    chip.title = "Press to filter. Double-click or F2 to rename. Drag onto another folder to nest it.";
    const icon = document.createElement("span");
    icon.className = "bookmark-folder-icon";
    icon.setAttribute("aria-hidden", "true");
    if (look.icon && !look.icon.startsWith("ph:")) icon.textContent = look.icon;
    else setLabel(icon, look.icon || "ph:folder-simple");
    const count = document.createElement("span");
    count.className = "library-chip-count";
    count.textContent = countIn(name);
    chip.append(icon, document.createTextNode(` ${name.includes("/") ? leaf(name) : name} `), count);
    if (name.includes("/")) chip.classList.add("is-nested");
    //: A press filters and redraws the chips, so the second press of a double-click lands on the new chip: it is
    //: told apart by `detail`, not by a `dblclick` the first redraw would have swallowed.
    chip.addEventListener("click", (event) => {
      if (event.detail >= 2) renameInPlace(chip, name);
      else onPress();
    });
    wireChip(chip, name);
    box.append(chip);
    return chip;
  }

  // ---- view and duplicates ------------------------------------------------------------------------------

  const view = () => (prefs.get(VIEW_KEY, "list") === "cards" ? "cards" : "list");

  function applyView() {
    const list = $("bookmark-list");
    const mode = view();
    list?.classList.toggle("is-cards", mode === "cards");
    const select = $("bookmark-view");
    if (select && select.value !== mode) select.value = mode;
  }

  //: Two addresses are the same link when they differ only in scheme, a leading www, case, a trailing slash,
  //: the fragment, or tracking parameters: found here, on what is already loaded.
  function sameKey(raw) {
    try {
      const u = new URL(/^[a-z][a-z0-9+.-]*:/i.test(raw) ? raw : `https://${raw}`);
      const params = [...u.searchParams].filter(([key]) => !/^(utm_|fbclid$|gclid$|mc_|ref$)/i.test(key));
      params.sort(([a], [b]) => a.localeCompare(b));
      const query = params.map(([key, value]) => `${key}=${value}`).join("&");
      return `${u.hostname.toLowerCase().replace(/^www\./, "")}${u.pathname.replace(/\/+$/, "")}${query ? `?${query}` : ""}`;
    } catch {
      return raw.trim().toLowerCase();
    }
  }

  function duplicateSets() {
    const byKey = new Map();
    for (const link of bookmarksCache) {
      const key = sameKey(link.url);
      byKey.set(key, [...(byKey.get(key) || []), link]);
    }
    return [...byKey.values()].filter((set) => set.length > 1);
  }

  //: Keep the oldest of each set (a pin or an unread mark outranks age: it is the one that was cared for)
  //: and delete the rest through the same undoable delete the row's menu uses.
  async function keepOneOfEach() {
    const doomed = [];
    for (const set of duplicateSets()) {
      const rank = (b) => (b.pinned ? 2 : 0) + (b.is_read ? 0 : 1);
      const keep = [...set].sort((a, b) => rank(b) - rank(a) || String(a.created_at).localeCompare(String(b.created_at)))[0];
      doomed.push(...set.filter((b) => b !== keep));
    }
    if (!doomed.length) return;
    if (!(await confirmDialog(`Delete ${nounCount(doomed.length, "duplicate bookmark")}? One of each stays (the pinned or unread one, else the oldest).`))) return;
    bookmarkScope.dupes = false;
    await deleteBookmarksWithUndo(doomed);
  }

  //: library.js calls it as `LinkShelf.readingFind` for a long file reading.
  //: The find box over a long reading (L1): a count and Enter or the arrows to the
  //: next match, drawn with the CSS highlight where the browser has it. Nothing
  //: is rewritten, so the text and Copy stay exactly what was read.
  function buildReadingFind(box) {
    const bar = document.createElement("div");
    bar.className = "library-file-find search-field";
    bar.addEventListener("click", (event) => event.stopPropagation());
    const icon = document.createElement("i");
    icon.className = "ph ph-magnifying-glass search-field-icon";
    icon.setAttribute("aria-hidden", "true");
    const input = document.createElement("input");
    input.type = "search";
    input.className = "search-field-input";
    input.placeholder = "Find in this text";
    input.setAttribute("aria-label", "Find in this text");
    const count = document.createElement("span");
    count.className = "muted text-xs library-file-find-count";
    count.setAttribute("role", "status");
    bar.append(icon, input, count);
    let ranges = [];
    let at = 0;
    const show = () => {
      if (!ranges.length) {
        count.textContent = input.value.trim() ? "No matches" : "";
        globalThis.CSS?.highlights?.delete("reading-find");
        return;
      }
      count.textContent = `${at + 1} of ${ranges.length}`;
      if (globalThis.CSS?.highlights && globalThis.Highlight) {
        globalThis.CSS.highlights.set("reading-find", new globalThis.Highlight(...ranges));
      }
      const rect = ranges[at].getBoundingClientRect();
      const frame = box.getBoundingClientRect();
      box.scrollTop += rect.top - frame.top - frame.height / 3;
    };
    const search = () => {
      ranges = [];
      at = 0;
      const needle = input.value.trim().toLowerCase();
      if (needle) {
        const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node && ranges.length < 500; node = walker.nextNode()) {
          const hay = node.nodeValue.toLowerCase();
          for (let i = hay.indexOf(needle); i >= 0 && ranges.length < 500; i = hay.indexOf(needle, i + needle.length)) {
            const range = document.createRange();
            range.setStart(node, i);
            range.setEnd(node, i + needle.length);
            ranges.push(range);
          }
        }
      }
      show();
    };
    input.addEventListener("input", search);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && ranges.length) {
        event.preventDefault();
        at = (at + (event.shiftKey ? ranges.length - 1 : 1)) % ranges.length;
        show();
      } else if (event.key === "Escape" && input.value) {
        event.stopPropagation();
        input.value = "";
        search();
      }
    });
    return bar;
  }

  window.LinkShelf = {
    afterSave, applyView, chooseBookmarkLook, detailsCard, duplicateSets, fillMark, folderChip, folders, inFolder,
    newFolder, readingFind: buildReadingFind, scopeBar, wireChip, wireRow, withLook,
  };

  onDomReady(() => {
    const select = $("bookmark-view");
    if (!select) return;
    select.value = view();
    select.addEventListener("change", () => {
      prefs.set(VIEW_KEY, select.value);
      applyView();
    });
  });
})();
