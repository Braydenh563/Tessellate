// note-properties.js: a note's properties and the note types (GRAPH_PLAN
// KG4, INBOX 528).
//
// Lazy, in the suggestions inbox's bundle (app.js, `LAZY_MODULES.inbox`):
// `openNotePropertiesSheet(entry)` from a note's ⋯ (Properties),
// `openNoteTypesSheet()` from the command palette. The properties are the
// `---` block at the top of the note's own text; this sheet is a table over
// it, and Save rewrites only that block (`PUT /entries/{id}/properties`). A
// type's fields come first, each with the control its kind needs; a note
// field is a [[link]], so it is a real link too.

const NOTE_FIELD_KINDS = ["text", "number", "date", "note", "list", "checkbox"];

function propInput(kind, value) {
  const v = Array.isArray(value) ? value : value == null ? [] : [String(value)];
  const input = document.createElement("input");
  input.className = "prop-value";
  if (kind === "checkbox") {
    input.type = "checkbox";
    input.checked = /^(true|yes)$/i.test(v[0] || "");
    return input;
  }
  input.type = kind === "number" ? "number" : kind === "date" ? "date" : "text";
  input.value = kind === "list" ? v.join(", ") : kind === "note" ? (v[0] || "").replace(/^\[\[|\]\]$/g, "") : v[0] || "";
  if (kind === "note") input.setAttribute("list", "prop-note-names");
  if (kind === "list") input.placeholder = "a, b, c";
  return input;
}

function propRead(kind, input) {
  if (kind === "checkbox") return input.checked;
  const text = input.value.trim();
  if (kind === "list") return text.split(",").map((x) => x.trim()).filter(Boolean);
  if (kind === "note") return text ? `[[${text}]]` : "";
  return text;
}

async function openNotePropertiesSheet(entry) {
  const [got, types] = await Promise.all([
    apiJson(`/entries/${entry.id}/properties`).catch(() => null),
    apiJson("/note-types").catch(() => []),
  ]);
  if (!got) {
    toast("Couldn't read this note's properties.", true);
    return;
  }
  const rows = [];
  openSheet({
    label: "Properties",
    sub: "Kept at the top of the note's own text, where any markdown app can read them.",
    name: "note-properties",
    build: (card, close) => {
      card.classList.add("inbox-card");
      const body = document.createElement("div");
      body.className = "inbox-body";
      const names = document.createElement("datalist");
      names.id = "prop-note-names";
      for (const e of (typeof allEntries !== "undefined" ? allEntries : []).slice(0, 300)) {
        const opt = document.createElement("option");
        opt.value = noteNamePlain(e.title || e.content).slice(0, 80);
        names.appendChild(opt);
      }
      //: The type first: a select of the note types; choosing one adds its
      //: fields (empty) to the rows below.
      const typeRow = document.createElement("div");
      typeRow.className = "prop-row";
      const typeLabel = document.createElement("span");
      typeLabel.className = "prop-key muted";
      typeLabel.textContent = "Type";
      const typeSelect = document.createElement("select");
      typeSelect.className = "prop-value";
      typeSelect.setAttribute("aria-label", "Note type");
      for (const [value, label] of [["", "No type"], ...types.map((t) => [t.name, t.name])]) {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        typeSelect.appendChild(opt);
      }
      if (got.type && !types.some((t) => t.name === got.type)) {
        const opt = document.createElement("option");
        opt.value = got.type;
        opt.textContent = got.type;
        typeSelect.appendChild(opt);
      }
      typeSelect.value = got.type || "";
      typeRow.append(typeLabel, typeSelect);
      const list = document.createElement("div");
      const addRow = (key, kind, value, fixed) => {
        if (rows.some((r) => r.keyValue() === key && key)) return;
        const row = document.createElement("div");
        row.className = "prop-row";
        const keyInput = document.createElement("input");
        keyInput.type = "text";
        keyInput.className = "prop-key";
        keyInput.value = key;
        keyInput.placeholder = "Name";
        keyInput.setAttribute("aria-label", "Property name");
        keyInput.readOnly = Boolean(fixed);
        const input = propInput(kind, value);
        input.setAttribute("aria-label", key ? `Value of ${key}` : "Value");
        const remove = smallButton("ph:x", "Remove this property", () => {
          row.remove();
          rows.splice(rows.indexOf(entryRow), 1);
        });
        remove.classList.add("icon-only");
        const entryRow = { keyValue: () => keyInput.value.trim(), read: () => propRead(kind, input) };
        rows.push(entryRow);
        //: KG4: a note field searches the notebook, not only the datalist's
        //: first 300 titles.
        if (kind === "note") row.append(keyInput, input, noteFieldPickButton(input), remove);
        else row.append(keyInput, input, remove);
        list.appendChild(row);
      };
      const fieldsOf = (name) => (types.find((t) => t.name === name)?.fields || []);
      for (const field of fieldsOf(got.type)) addRow(field.name, field.kind, got.properties[field.name], true);
      for (const [key, values] of Object.entries(got.properties || {})) {
        if (key !== "type") addRow(key, values.length > 1 ? "list" : "text", values);
      }
      typeSelect.addEventListener("change", () => {
        for (const field of fieldsOf(typeSelect.value)) addRow(field.name, field.kind, null, true);
      });
      const add = smallButton("ph:plus Add a property", "A new name and value", () => {
        addRow("", "text", null);
        list.lastElementChild?.querySelector(".prop-key")?.focus();
      });
      const actions = document.createElement("div");
      actions.className = "row right space-dialog-actions";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "ghost small";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", close);
      const save = document.createElement("button");
      save.type = "button";
      save.className = "accent small";
      save.textContent = "Save";
      save.addEventListener("click", async () => {
        const properties = {};
        if (typeSelect.value) properties.type = typeSelect.value;
        for (const r of rows) if (r.keyValue()) properties[r.keyValue()] = r.read();
        save.disabled = true;
        const done = await apiJson(`/entries/${entry.id}/properties`, {
          method: "PUT",
          body: JSON.stringify({ properties, base_hash: entry.content_hash || null }),
        }).catch((e) => {
          toast(e.message, true);
          return null;
        });
        save.disabled = false;
        if (!done) return;
        if (typeof done.content === "string" && typeof entry.content === "string" && done.content !== entry.content) {
          pushEntryPutUndo(entry.id, "Changed a note's properties", { content: entry.content }, { content: done.content });
        }
        close();
        toast("Properties saved.");
        loadEntries().catch(() => {});
      });
      actions.append(cancel, save);
      body.append(names, typeRow, list, add);
      card.append(body, actions);
    },
  });
}

/** The note types: each with its fields, a New note of that type, and
 *  Delete (its notes keep their properties). */
async function openNoteTypesSheet() {
  const types = await apiJson("/note-types").catch(() => []);
  openSheet({
    label: "Note types",
    sub: "A kind of note with its own fields, written at the top of each new note of that type.",
    name: "note-types",
    build: (card, close) => {
      card.classList.add("inbox-card");
      const list = document.createElement("div");
      list.className = "sheet-list inbox-body";
      for (const t of types) {
        const row = document.createElement("div");
        row.className = "row relation-type-row";
        const name = document.createElement("span");
        name.className = "relation-type-name";
        name.textContent = t.name;
        //: The type's colour (D5), the Manage categories dot, only when one
        //: was chosen: an automatic type has no colour of its own to show.
        if (t.colour) {
          const dot = document.createElement("span");
          dot.className = "manage-cat-dot";
          dot.setAttribute("aria-hidden", "true");
          dot.style.setProperty("--category-dot", noteTypeColourHex(t.colour));
          row.appendChild(dot);
        }
        const fields = document.createElement("span");
        fields.className = "muted relation-type-hint";
        fields.textContent = t.fields.map((f) => `${f.name} (${f.kind})`).join(", ") || "No fields";
        row.append(name, fields, kebabMenu([
          { label: "ph:note-pencil New note of this type", title: `A new note with ${t.name}'s fields at the top`, run: async () => {
            const made = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `# New ${t.name.toLowerCase()}`, note_type: t.name, category: "Uncategorised" }) }).catch((e) => {
              toast(e.message, true);
              return null;
            });
            if (!made) return;
            pushEntryCreateUndo(made, `Made a ${t.name} note`);
            close();
            await loadEntries().catch(() => {});
            await switchTab("notes");
            flashEntry(made.id);
          } },
          { label: "ph:list-plus Fields", title: "Its fields, as name: kind, separated by commas", run: async () => {
            const text = await promptDialog(`Fields, as name: kind, separated by commas. Kinds: ${NOTE_FIELD_KINDS.join(", ")}`, t.fields.map((f) => `${f.name}: ${f.kind}`).join(", "));
            if (text === null || text === undefined) return;
            const ok = await apiJson(`/note-types/${t.id}`, { method: "PATCH", body: JSON.stringify({ fields: noteTypeFieldsParse(text) }) }).catch((e) => {
              toast(e.message, true);
              return null;
            });
            if (!ok) return;
            pushRequestUndo(`Changed the fields of ${t.name}`, `/note-types/${t.id}`, "PATCH", { fields: (t.fields || []).map((f) => ({ name: f.name, kind: f.kind })) }, { fields: noteTypeFieldsParse(text) });
            close();
            openNoteTypesSheet();
          } },
          { label: "ph:palette Colour…", title: `The colour ${t.name} notes take on the graph`, run: () => {
            close();
            noteTypePickColour(t);
          } },
          { label: "ph:trash Delete", title: "Delete this type; its notes keep their properties", group: "delete", run: async () => {
            if (!(await confirmDialog(`Delete the note type “${t.name}”?\n\nIts notes keep every property, type included.`))) return;
            const gone = await apiJson(`/note-types/${t.id}`, { method: "DELETE" }).catch((e) => {
              toast(e.message, true);
              return null;
            });
            close();
            openNoteTypesSheet();
            if (gone?.type) noteTypeDeleteUndo(gone.type);
          } },
        ], `Actions for ${t.name}`, { vertical: true }));
        list.appendChild(row);
      }
      list.appendChild(sheetRow("ph ph-plus", "New note type…", async () => {
        close();
        const name = await promptDialog("Name the note type (for example: Meeting)", "", { confirmLabel: "Next" });
        if (!name || !name.trim()) return;
        const text = await promptDialog(`Its fields, as name: kind, separated by commas (for example: attendees: list, date: date). Kinds: ${NOTE_FIELD_KINDS.join(", ")}`, "", { confirmLabel: "Create" });
        if (text === null || text === undefined) return;
        const made = await apiJson("/note-types", { method: "POST", body: JSON.stringify({ name: name.trim(), fields: noteTypeFieldsParse(text) }) }).catch((e) => {
          toast(e.message, true);
          return null;
        });
        if (made) {
          const body = { name: name.trim(), fields: noteTypeFieldsParse(text) };
          let liveId = made.id;
          pushUndo(
            `Added the note type “${body.name}”`,
            async () => {
              await apiJson(`/note-types/${liveId}`, { method: "DELETE" });
            },
            async () => {
              const again = await apiJson("/note-types", { method: "POST", body: JSON.stringify(body) });
              liveId = again?.id ?? liveId;
            }
          );
          openNoteTypesSheet();
        }
      }));
      card.appendChild(list);
    },
  });
}

//: A type's colour as stored: one of the category palette's keys (what the
//: swatch picker chooses), or a hex an import or the API wrote.
function noteTypeColourHex(colour) {
  return typeof CATEGORY_PALETTE !== "undefined" && Object.hasOwn(CATEGORY_PALETTE, colour) ? CATEGORY_PALETTE[colour] : colour;
}

//: **A note type's colour** (WORLD_CLASS_PLAN row 10, D5): DESIGN.md's swatch
//: picker in a sheet, the category picker's own, under a preview that is the
//: type's name with its dot. Stored on the type (`PATCH /note-types/{id}`),
//: read by the graph's "Note type" colour rule; Automatic clears it. Undo puts
//: the previous colour back.
async function noteTypePickColour(t) {
  //: The picker lives with the Manage categories panel (lazy).
  if (typeof swatchPicker !== "function" && !(await ensureModule("categories"))) return;
  const before = t.colour || null;
  const save = async (key) => {
    await apiJson(`/note-types/${t.id}`, { method: "PATCH", body: JSON.stringify({ colour: key }) });
    t.colour = key;
    if (typeof renderGraph === "function" && graphColourMode() === "type") renderGraph();
  };
  openSheet({
    label: `Colour for ${t.name}`,
    sub: "Shown on the graph when its colours follow the note type. Automatic picks one from the name.",
    name: "note-type-colour",
    build: (card, close) => {
      card.classList.add("swatch-card");
      const preview = document.createElement("p");
      preview.className = "swatch-preview";
      preview.textContent = t.name;
      const show = (key) => preview.style.setProperty("--category-dot", key ? noteTypeColourHex(key) : categoryAutoDot(t.name));
      const picker = swatchPicker({
        label: `Colour for ${t.name}`,
        value: before,
        onChange: show,
        onChoose: async (key) => {
          close();
          if (key === before) return;
          try {
            await save(key);
          } catch (error) {
            toast(error.message, true);
            return;
          }
          const message = `${t.name} is now ${categoryColourName(key).toLowerCase()}.`;
          const action = pushUndo(message, () => save(before), () => save(key));
          toastAction(message, "Undo", async () => {
            settleUndoFromToast(action);
            await save(before).catch((error) => toast(error.message, true));
          });
        },
      });
      card.append(preview, picker);
      requestAnimationFrame(() => picker.querySelector('[tabindex="0"]')?.focus());
    },
  });
}

//: A deleted note type comes back with Undo (undo-1005): the DELETE answers
//: with the row, `restore` makes it again under its own id, and no note needs
//: touching because a note names its type in its own text.
function noteTypeDeleteUndo(row) {
  const remake = async () => {
    await apiJson("/note-types", { method: "POST", body: JSON.stringify({ ...row, restore: true }) });
  };
  const action = pushUndo(`Deleted the note type “${row.name}”`, remake, async () => {
    await apiJson(`/note-types/${row.id}`, { method: "DELETE" });
  });
  toastAction(`Deleted “${row.name}”.`, "Undo", async () => {
    settleUndoFromToast(action);
    await remake().catch((e) => toast(e.message, true));
  });
}

function noteTypeFieldsParse(text) {
  return (text || "").split(",").map((part) => {
    const [name, kind] = part.split(":").map((x) => (x || "").trim());
    return name ? { name, kind: NOTE_FIELD_KINDS.includes((kind || "").toLowerCase()) ? kind.toLowerCase() : "text" } : null;
  }).filter(Boolean);
}

// --- KG7: a live query's notes as a table, and on the graph -----------------

/** The notes a query matched (the list's ids, so the same notes), with the
 *  properties they carry as columns, `type` first, most common next. */
function openQueryTable(ids) {
  const byId = new Map((typeof allEntries !== "undefined" ? allEntries : []).map((e) => [e.id, e]));
  const rows = ids.map((id) => byId.get(id)).filter(Boolean);
  const counts = new Map();
  for (const e of rows) for (const key of Object.keys(e.properties || {})) counts.set(key, (counts.get(key) || 0) + 1);
  const columns = [...counts.keys()].sort((a, b) => (a === "type" ? -1 : b === "type" ? 1 : counts.get(b) - counts.get(a) || a.localeCompare(b))).slice(0, 8);
  openSheet({
    label: "Query table",
    sub: `${nounCount(rows.length, "note")} · ${noteSearch}`,
    name: "query-table",
    build: (card, close) => {
      card.classList.add("inbox-card");
      const wrap = document.createElement("div");
      wrap.className = "inbox-body query-table-wrap";
      const table = document.createElement("table");
      table.className = "query-table";
      const head = document.createElement("tr");
      for (const label of ["Note", ...columns]) {
        const th = document.createElement("th");
        th.scope = "col";
        th.textContent = label;
        head.appendChild(th);
      }
      const thead = document.createElement("thead");
      thead.appendChild(head);
      const tbody = document.createElement("tbody");
      for (const e of rows) {
        const tr = document.createElement("tr");
        const name = document.createElement("td");
        const open = document.createElement("button");
        open.type = "button";
        open.className = "linklike";
        open.textContent = noteNamePlain(e.title || e.content).slice(0, 80) || "Untitled note";
        open.addEventListener("click", () => {
          close();
          flashEntry(e.id);
        });
        name.appendChild(open);
        tr.appendChild(name);
        for (const key of columns) {
          const td = document.createElement("td");
          td.textContent = ((e.properties || {})[key] || []).join(", ").replace(/\[\[([^[\]]{1,120})\]\]/g, "$1");
          tr.appendChild(td);
        }
        tbody.appendChild(tr);
      }
      table.append(thead, tbody);
      if (columns.length) table.appendChild(queryTableRollupFoot(columns));
      wrap.appendChild(table);
      card.appendChild(wrap);
    },
  });
}

//: **Rollups** (GRAPH_PLAN, after KG9): the footer says one thing per column
//: about every note the query matched, not only the rows drawn: count, and
//: sum, min and max when the values read as numbers, earliest and latest when
//: they read as dates. The server computes them from the property index
//: (`entry/query.rollups`), the same `noteSearch` the list ran; the choice per
//: column is remembered on this device, a column's own default is the first
//: of sum, latest and count it has.
const QUERY_ROLLUP_NAMES = { count: "Count", sum: "Sum", min: "Min", max: "Max", earliest: "Earliest", latest: "Latest" };

function queryTableRollupFoot(columns) {
  const foot = document.createElement("tfoot");
  const row = document.createElement("tr");
  const lead = document.createElement("th");
  lead.scope = "row";
  lead.textContent = "Roll up";
  row.appendChild(lead);
  const cells = new Map();
  for (const key of columns) {
    const td = document.createElement("td");
    td.className = "query-rollup";
    td.dataset.key = key;
    cells.set(key, td);
    row.appendChild(td);
  }
  foot.appendChild(row);
  apiJson(`/entries/query?q=${encodeURIComponent(noteSearch || "")}`)
    .then((body) => fillQueryRollups(cells, (body && body.rollups) || {}))
    .catch(() => {
      for (const td of cells.values()) td.textContent = "";
    });
  return foot;
}

function fillQueryRollups(cells, rollups) {
  for (const [key, td] of cells) {
    td.replaceChildren();
    const block = rollups[key];
    if (!block) continue;
    const kinds = Object.keys(QUERY_ROLLUP_NAMES).filter((k) => block[k] !== undefined);
    const storeKey = `query-rollup:${key}`;
    let chosen = "";
    try {
      chosen = prefs.get(storeKey, null) || "";
    } catch {
      chosen = "";
    }
    if (!kinds.includes(chosen)) chosen = ["sum", "latest", "count"].find((k) => kinds.includes(k));
    const value = document.createElement("span");
    value.className = "query-rollup-value";
    //: Words only: a count and nothing to choose, so no dead one-item select.
    if (kinds.length === 1) {
      const name = document.createElement("span");
      name.className = "muted";
      name.textContent = QUERY_ROLLUP_NAMES[chosen];
      value.textContent = String(block[chosen]);
      td.append(name, value);
      continue;
    }
    const select = document.createElement("select");
    select.className = "query-rollup-kind";
    select.setAttribute("aria-label", `Roll up ${key}`);
    for (const k of kinds) select.add(new Option(QUERY_ROLLUP_NAMES[k], k, false, k === chosen));
    const show = () => {
      const v = block[select.value];
      value.textContent = typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v;
    };
    select.addEventListener("change", () => {
      try {
        prefs.set(storeKey, select.value);
      } catch {
        /* this device only; nothing lost */
      }
      show();
    });
    show();
    td.append(select, value);
  }
}

/** The same notes, lit on the graph (the topic legend's highlight). */
async function showQueryOnGraph(ids) {
  await switchTab("graph");
  const deadline = Date.now() + 4000;
  while (Date.now() < deadline && !(typeof graphNodesRef !== "undefined" && graphNodesRef?.length)) {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  if (typeof applyGraphHighlight !== "function") return;
  graphHighlightIds = new Set(ids);
  applyGraphHighlight();
  toast(`${nounCount(ids.length, "note")} lit. Clear highlight puts the map back.`);
}
