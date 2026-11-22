// Lazily loaded (LAZY_MODULES.noteGroups in app.js): the sheets for groups of
// notes gathered by hand (L-world-class-172) and for a note's further
// categories (L-world-class-173), so they stay off the boot scripts' gzip
// budget (tests/test_static_compression.py).
//
//: A group is a set a person makes: no model files into it and no sort moves
//: a note out of it. It is filtered like a tag, as `group:"Name"` in the Notes
//: box (notes-list.js `matchesSearch`). A note's "also in" categories sit
//: beside the one the filer decides (`entries.category_id`); only a person
//: sets them (`PUT /entries/{id}/also-in`). Both are DESIGN.md's sheet recipe:
//: `openSheet` with `sheetRow`s, a check mark for what is on.

(() => {
  const groupQuery = (name) => `group:"${name.replace(/"/g, "")}"`;

  async function afterChange() {
    await loadEntries();
    renderSidebar();
  }

  //: Ask for a name, then make the group; the new group's id, or null.
  async function newGroup() {
    const name = await promptDialog("Name the new group", "", { confirmLabel: "Create" });
    if (!name || !name.trim()) return null;
    try {
      return await apiJson("/groups", { method: "POST", body: JSON.stringify({ name: name.trim() }) });
    } catch (error) {
      toast(error.message, true);
      return null;
    }
  }

  //: Every group; a press opens that group's own sheet.
  async function listGroupsSheet() {
    const groups = await apiJson("/groups").catch(() => null);
    if (!groups) return;
    openSheet({
      label: "Groups",
      sub: groups.length ? "Notes you gathered by hand. No sorting moves a note out of one." : "Gather notes by hand: no sorting moves them. Add a note from its category menu.",
      name: "note-groups",
      build: (card, close) => {
        const list = document.createElement("div");
        list.className = "sheet-list";
        for (const group of groups) {
          list.appendChild(sheetRow("ph ph-folders", `${group.name} (${group.count})`, () => {
            close();
            openGroupSheet(group);
          }));
        }
        list.appendChild(sheetRow("ph ph-plus", "New group…", async () => {
          close();
          if (await newGroup()) listGroupsSheet();
        }));
        card.appendChild(list);
      },
    });
  }

  function openGroupSheet(group) {
    openSheet({
      label: group.name,
      name: "note-group",
      build: (card, close) => {
        const list = document.createElement("div");
        list.className = "sheet-list";
        list.append(
          sheetRow("ph ph-eye", `Show its ${nounCount(group.count, "note")}`, () => {
            close();
            filterNotesBy(groupQuery(group.name));
          }),
          sheetRow("ph ph-pencil-simple", "Rename…", async () => {
            close();
            const name = await promptDialog("Rename the group", group.name, { confirmLabel: "Rename" });
            if (!name || !name.trim() || name.trim() === group.name) return;
            try {
              await apiJson(`/groups/${group.id}`, { method: "PATCH", body: JSON.stringify({ name: name.trim() }) });
              await afterChange();
            } catch (error) {
              toast(error.message, true);
            }
          }),
          sheetRow("ph ph-trash", "Delete the group", async () => {
            close();
            if (!(await confirmDialog(`Delete the group “${group.name}”? Its notes are kept.`, { confirmLabel: "Delete" }))) return;
            await apiJson(`/groups/${group.id}`, { method: "DELETE" }).catch((error) => toast(error.message, true));
            await afterChange();
          })
        );
        card.appendChild(list);
      },
    });
  }

  //: The groups a note is in: a press toggles it, and the sheet stays open.
  async function chooseNoteGroups(entry) {
    const groups = await apiJson("/groups").catch(() => null);
    if (!groups) return;
    const here = new Set(entry.groups || []);
    openSheet({
      label: "Add to a group",
      sub: groups.length ? "" : "No groups yet. Make one to gather notes by hand.",
      name: "note-groups-pick",
      onClose: () => afterChange(),
      build: (card, close) => {
        const list = document.createElement("div");
        list.className = "sheet-list";
        const toggle = async (group, row) => {
          const on = row !== null && here.has(group.name);
          const path = on ? `/groups/${group.id}/notes/remove` : `/groups/${group.id}/notes`;
          try {
            await apiJson(path, { method: "POST", body: JSON.stringify({ ids: [entry.id] }) });
          } catch (error) {
            toast(error.message, true);
            return;
          }
          if (on) here.delete(group.name);
          else here.add(group.name);
          if (!row) return;
          row.firstChild.className = here.has(group.name) ? "ph ph-check-square" : "ph ph-square";
          row.setAttribute("aria-pressed", String(here.has(group.name)));
        };
        const add = (group) => {
          const row = sheetRow(here.has(group.name) ? "ph ph-check-square" : "ph ph-square", group.name, () => toggle(group, row));
          row.setAttribute("aria-pressed", String(here.has(group.name)));
          list.insertBefore(row, list.lastChild);
        };
        list.appendChild(sheetRow("ph ph-plus", "New group…", async () => {
          const made = await newGroup();
          if (!made) return;
          await toggle(made, null);
          add(made);
        }));
        for (const group of groups) add(group);
        card.appendChild(list);
      },
    });
  }

  //: The categories a note is also in, besides the one it is filed under.
  function chooseAlsoCategories(entry) {
    const chosen = new Set(entry.also_in || []);
    openSheet({
      label: "Also file under",
      sub: `Filed under ${entry.category}. These are extra places it shows up; the sorting leaves them alone.`,
      name: "note-also-in",
      onClose: () => afterChange(),
      build: (card) => {
        const list = document.createElement("div");
        list.className = "sheet-list";
        const save = async () => {
          try {
            await apiJson(`/entries/${entry.id}/also-in`, { method: "PUT", body: JSON.stringify({ categories: [...chosen] }) });
          } catch (error) {
            toast(error.message, true);
          }
        };
        const add = (name) => {
          const row = sheetRow(chosen.has(name) ? "ph ph-check-square" : "ph ph-square", name, async () => {
            if (chosen.has(name)) chosen.delete(name);
            else chosen.add(name);
            row.firstChild.className = chosen.has(name) ? "ph ph-check-square" : "ph ph-square";
            row.setAttribute("aria-pressed", String(chosen.has(name)));
            await save();
          });
          row.setAttribute("aria-pressed", String(chosen.has(name)));
          list.insertBefore(row, list.lastChild);
        };
        list.appendChild(sheetRow("ph ph-plus", "New category…", async () => {
          const name = await promptDialog("Name the category", "", { confirmLabel: "Add" });
          if (!name || !name.trim() || chosen.has(name.trim())) return;
          chosen.add(name.trim());
          await save();
          add(name.trim());
        }));
        const names = [...categoryMeta.keys()].filter((n) => n !== entry.category && n !== "Uncategorised");
        for (const name of [...new Set([...names, ...chosen])].sort((a, b) => a.localeCompare(b))) add(name);
        card.appendChild(list);
      },
    });
  }

  //: The one export (the shared scope's names are counted): the groups list
  //: with no arguments, or one note's sheet, `"groups"` or `"also"`.
  function openNoteGroupsSheet(entry, kind) {
    if (!entry) return listGroupsSheet();
    return kind === "also" ? chooseAlsoCategories(entry) : chooseNoteGroups(entry);
  }

  Object.assign(window, { openNoteGroupsSheet });
})();
