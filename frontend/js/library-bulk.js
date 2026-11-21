// library-bulk.js: tags, a category and a property for the documents and files
// a Library selection holds (WORLD_CLASS_PLAN decision 65, L-world-class-392
// and 393). Lazy: the Documents and Media bars' ⋯ menus (library.js
// `libraryMetaMenu`) call the `libraryMeta` stand-in, which fetches this file.
// One request, one toast, one Undo, the shape the Notes bar has.

(() => {
  //: `kind` is "document" or "media"; `after` repaints the list once it is done.
  async function libraryMeta(action, kind, ids, after, bar) {
    if (action === "menu") return libraryMetaMenu(bar, kind, ids, after);
    ids = ids.map(Number).filter(Boolean);
    if (!ids.length) return;
    const noun = kind === "media" ? "file" : "document";
    const write = async (body, label) => {
      let out;
      try {
        out = await apiJson("/library/meta/bulk", { method: "POST", body: JSON.stringify({ kind, ids, ...body }) });
      } catch (err) {
        return toast(err.message || "That did not save.", true);
      }
      const undo = async () => {
        await apiJson("/library/meta/restore", { method: "POST", body: JSON.stringify({ kind, items: out.before }) });
        await after?.();
      };
      const redo = async () => {
        await apiJson("/library/meta/bulk", { method: "POST", body: JSON.stringify({ kind, ids, ...body }) });
        await after?.();
      };
      await after?.();
      const text = `${label} on ${nounCount(out.changed, noun)}`;
      const entry = pushUndo(text, undo, redo);
      toastAction(`${text}.`, "Undo", async () => {
        settleUndoFromToast(entry);
        await undo();
      });
    };
    if (action === "tags") return libraryMetaTags(kind, ids, noun, write);
    if (action === "category") return libraryMetaCategory(write);
    if (action === "property") return libraryMetaProperty(write);
  }

  async function libraryMetaTags(kind, ids, noun, write) {
    //: `tagNamesWords` (the toast's wording) lives with the tag manager.
    await ensureModule("tagManager");
    const have = await apiJson(`/library/meta?kind=${kind}&ids=${ids.join(",")}`).catch(() => ({ items: [] }));
    const held = new Map();
    for (const item of have.items) {
      for (const tag of item.tags) {
        const entry = held.get(tag.toLowerCase()) || { name: tag, count: 0 };
        entry.count += 1;
        held.set(tag.toLowerCase(), entry);
      }
    }
    const present = [...held.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
    openSheet({
      label: `Tags for ${nounCount(ids.length, noun)}`,
      sub: "Add tags to everything selected, take tags off it, or both. One Undo covers all of it.",
      name: "library-bulk-tags",
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
          none.textContent = `None of these ${noun}s has a tag yet.`;
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
          on.textContent = tag.count === ids.length ? "all of them" : `${tag.count} of ${ids.length}`;
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
          const added = [...new Set(add.value.split(",").map((t) => t.trim().replace(/^#/, "")).filter(Boolean))];
          const removed = [...boxes].filter(([, box]) => box.checked).map(([name]) => name);
          if (!added.length && !removed.length) return toast("Type a tag to add, or tick one to remove.", "info");
          if (apply.disabled) return;
          setBusy(apply, true);
          const parts = [];
          if (added.length) parts.push(`Added ${tagNamesWords(added)}`);
          if (removed.length) parts.push(`${added.length ? "removed" : "Removed"} ${tagNamesWords(removed)}`);
          await write({ add: added, remove: removed }, parts.join("; "));
          setBusy(apply, false);
          close();
        });
        card.appendChild(form);
        setTimeout(() => add.focus(), 0);
      },
    });
  }

  async function libraryMetaCategory(write) {
    const rows = await apiJson("/categories").catch(() => []);
    const names = rows.map((row) => row.name).sort((a, b) => a.localeCompare(b));
    openSheet({
      label: "Move to category",
      name: "library-bulk-category",
      build: (card, close) => {
        const list = document.createElement("div");
        list.className = "sheet-list";
        for (const name of names) {
          list.appendChild(sheetRow("ph ph-folder", name, async () => {
            close();
            await write({ category: name }, `Filed under ${name}`);
          }));
        }
        list.appendChild(sheetRow("ph ph-plus", "New category…", async () => {
          close();
          const name = await promptDialog("Name the new category", "", { confirmLabel: "Move" });
          if (name && name.trim()) await write({ category: name.trim() }, `Filed under ${name.trim()}`);
        }));
        list.appendChild(sheetRow("ph ph-x", "No category", async () => {
          close();
          await write({ clear_category: true }, "Category cleared");
        }));
        card.appendChild(list);
      },
    });
  }

  async function libraryMetaProperty(write) {
    const typed = await promptDialog("name: value (no value removes it)", "", { confirmLabel: "Set" });
    if (!typed) return;
    const [name, value] = String(typed).split(/:(.*)/s).map((s) => (s || "").trim());
    if (!typed.includes(":") || !name) return toast("Write it as name: value.", "info");
    await write({ property_name: name, property_value: value }, `${value ? "Set" : "Cleared"} ${name}`);
  }

  //: The ⋯ menu of a Documents or Media selection bar, built once, before Delete.
  function libraryMetaMenu(bar, kind, ids, after) {
    const end = bar?.querySelector(".library-contextbar-end");
    if (!end || end.querySelector(".menu-wrap")) return;
    const run = (action) => () => libraryMeta(action, kind, ids(), after);
    end.prepend(kebabMenu([
      { label: "ph:tag Tags…", run: run("tags"), group: "edit" },
      { label: "ph:folder-simple Move to category…", run: run("category"), group: "edit" },
      { label: "ph:list-dashes Set a property…", run: run("property"), group: "edit" },
    ], `More for the selected ${kind === "media" ? "files" : "documents"}`));
  }

  Object.assign(window, { libraryMeta });
})();
