// entity-page.js: a person, place, project, organisation or thing, as a page
// (GRAPH_PLAN KG5, INBOX 528).
//
// Lazy, in the suggestions inbox's bundle (app.js, `LAZY_MODULES.inbox`):
// `openEntityPage(id)` from a graph's entity node and the inbox's Names rows,
// `openEntitiesSheet()` from the command palette. The page is a sheet: where
// the name is said (each note's sentence, the name marked), what it is named
// with, the dates its notes resolve; its ⋯ holds Kind, Rename, Other names and
// Merge into. Every change is the server's (`/entities`), never browser state.

const ENTITY_KIND_WORDS = { person: "Person", place: "Place", project: "Project", organisation: "Organisation", thing: "Thing" };
const ENTITY_KIND_ICONS = { person: "ph-user", place: "ph-map-pin", project: "ph-kanban", organisation: "ph-buildings", thing: "ph-cube" };

function entityIcon(kind) {
  const icon = document.createElement("i");
  icon.className = `ph ${ENTITY_KIND_ICONS[kind] || "ph-at"} ph-lead`;
  icon.setAttribute("aria-hidden", "true");
  return icon;
}

function entityWhen(iso) {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
}

let entityPageClose = null;

//: INBOX 553(a), the owner's decision: an entity merge has Undo, in its toast
//: and on the app's stack. Undo splits the two back exactly (the server kept
//: both as they were, with every mention, `POST /entities/merges/{id}/undo`);
//: Redo merges again, and the next Undo takes that merge's own snapshot.
//: `after(merged)` redraws whatever the caller shows. Also used by the
//: suggestions inbox (loaded with this file).
function toastEntityMerge(done, mergeId, intoId, after, learned) {
  let undoId = done.undo_id;
  //: A merge accepted from the inbox also taught the learning loop; Undo takes
  //: that correction away and Redo teaches it again (`learned` is its request).
  let learnedId = done.correction_id;
  const undo = async () => {
    await apiJson(`/entities/merges/${undoId}/undo`, { method: "POST" });
    if (learnedId != null) await api(`/learned/corrections/${learnedId}`, { method: "DELETE" });
    if (after) await after(false);
  };
  const redo = async () => {
    const again = await apiJson(`/entities/${mergeId}/merge`, { method: "POST", body: JSON.stringify({ into_id: intoId }) });
    undoId = again.undo_id;
    if (learned) learnedId = (await apiJson("/learned/corrections", { method: "POST", body: JSON.stringify(learned) }))?.id ?? learnedId;
    if (after) await after(true);
  };
  const action = pushUndo(`Merged into “${done.name}”`, undo, redo);
  toastAction(`Merged into “${done.name}”.`, "Undo", async () => {
    settleUndoFromToast(action);
    try {
      await undo();
      toast("Merge undone.");
    } catch (error) {
      toast(error.message, true);
    }
  });
}

async function openEntityPage(id) {
  const page = await apiJson(`/entities/${id}`).catch((e) => {
    toast(e.message, true);
    return null;
  });
  if (!page) return;
  entityPageClose?.();
  const facts = [ENTITY_KIND_WORDS[page.kind] || "No kind yet", `named in ${nounCount(page.notes, "note")}`];
  const [first, last] = [entityWhen(page.first_seen), entityWhen(page.last_seen)];
  if (first) facts.push(first === last ? first : `${first} to ${last}`);
  if (page.aliases.length) facts.push(`also ${page.aliases.join(", ")}`);
  entityPageClose = openSheet({
    label: page.name,
    sub: facts.join(" · "),
    name: "entity",
    onClose: () => {
      entityPageClose = null;
    },
    build: (card) => {
      card.classList.add("inbox-card", "entity-card");
      const head = card.querySelector(".sheet-head");
      const actions = document.createElement("span");
      actions.className = "dialog-head-actions";
      const menu = kebabMenu(entityMenuItems(page), `Actions for ${page.name}`);
      menu.querySelector("button")?.classList.add("dialog-head-btn");
      const closeButton = head.querySelector(".sheet-close");
      actions.append(menu, ...(closeButton ? [closeButton] : []));
      head.appendChild(actions);
      const body = document.createElement("div");
      body.className = "inbox-body";
      body.append(entitySection("Mentioned in", page.mentions.map(entityMentionRow), "No visible note names it."));
      const related = document.createElement("div");
      related.className = "row entity-related";
      for (const other of page.related) {
        const b = smallButton(`${other.name} · ${other.notes}`, `Open ${other.name}: named together in ${nounCount(other.notes, "note")}`, () => openEntityPage(other.id));
        b.prepend(entityIcon(other.kind));
        related.appendChild(b);
      }
      body.append(entitySection("Named with", page.related.length ? [related] : [], "Nothing else is named in its notes."));
      body.append(entitySection("Dates", page.dates.map(entityDateRow), "Its notes name no dates."));
      card.appendChild(body);
    },
  });
}

function entitySection(title, rows, empty) {
  const section = document.createElement("section");
  section.className = "entity-section";
  const h = document.createElement("h3");
  h.className = "entity-section-title";
  h.textContent = title;
  section.appendChild(h);
  if (rows.length) section.append(...rows);
  else {
    const p = document.createElement("p");
    p.className = "muted inbox-empty";
    p.textContent = empty;
    section.appendChild(p);
  }
  return section;
}

function entityMentionRow(m) {
  const row = document.createElement("div");
  row.className = "inbox-row";
  const open = document.createElement("button");
  open.type = "button";
  open.className = "linklike inbox-row-title";
  open.textContent = m.title;
  open.title = "Open this note";
  open.addEventListener("click", () => {
    entityPageClose?.();
    flashEntry(m.id);
  });
  row.append(open, docBacklinkContext(m));
  return row;
}

function entityDateRow(d) {
  const row = document.createElement("p");
  row.className = "entity-date";
  const when = document.createElement("strong");
  when.textContent = entityWhen(d.at);
  const phrase = document.createElement("span");
  phrase.className = "muted";
  phrase.textContent = ` “${d.phrase}”`;
  row.append(when, phrase);
  return row;
}

async function entitySave(page, patch, done) {
  const saved = await apiJson(`/entities/${page.id}`, { method: "PATCH", body: JSON.stringify(patch) }).catch((e) => {
    toast(e.message, true);
    return null;
  });
  if (!saved) return;
  const wasFields = Object.fromEntries(Object.keys(patch).map((key) => [key, page[key] ?? null]));
  pushRequestUndo("Changed a name's details", `/entities/${page.id}`, "PATCH", wasFields, patch, () => openEntityPage(page.id));
  toast(done);
  openEntityPage(page.id);
}

function entityMenuItems(page) {
  return [
    {
      label: "ph:tag Kind",
      items: [...Object.entries(ENTITY_KIND_WORDS), ["", "No kind"]].map(([key, word]) => ({
        label: `${page.kind === key || (!key && !page.kind) ? "ph:check" : "ph:circle"} ${word}`,
        title: `Mark it as ${word.toLowerCase()}`,
        run: () => entitySave(page, { kind: key || null }, key ? `Marked as ${word.toLowerCase()}.` : "Kind cleared."),
      })),
    },
    {
      label: "ph:pencil-simple Rename",
      title: "Change its name; the old one is kept as another name",
      run: async () => {
        const name = await promptDialog("Rename", page.name, { confirmLabel: "Rename" });
        if (!name || !name.trim() || name.trim() === page.name) return;
        entitySave(page, { name: name.trim(), aliases: [...page.aliases, page.name] }, "Renamed.");
      },
    },
    {
      label: "ph:list-plus Other names",
      title: "Names it also goes by, separated by commas; extraction lands them here",
      run: async () => {
        const text = await promptDialog("Other names, separated by commas", page.aliases.join(", "));
        if (text === null || text === undefined) return;
        entitySave(page, { aliases: text.split(",").map((a) => a.trim()).filter(Boolean) }, "Other names saved.");
      },
    },
    {
      label: "ph:arrows-merge Merge into…",
      title: "Fold it into another name: every mention moves",
      run: () => openEntitiesSheet({ mergeFrom: page }),
    },
  ];
}

/** Every entity, most named first, with a filter; or, to merge one, the
 *  list of where it can go. */
async function openEntitiesSheet({ mergeFrom = null } = {}) {
  const rows = await apiJson("/entities").catch(() => null);
  if (!rows) return toast("Could not load the people and things in your notes. Try again.", true, { action: ["Try again", () => openEntitiesSheet({ mergeFrom })] });
  openSheet({
    label: mergeFrom ? `Merge “${mergeFrom.name}” into` : "People and things",
    sub: mergeFrom ? "Every mention moves; its names are kept as other names." : "Named in your notes, most named first.",
    name: "entities",
    build: (card, close) => {
      card.classList.add("inbox-card");
      const filter = document.createElement("input");
      filter.type = "search";
      filter.className = "entity-filter";
      filter.placeholder = "Filter names";
      filter.setAttribute("aria-label", "Filter names");
      const list = document.createElement("div");
      list.className = "sheet-list inbox-body";
      const draw = () => {
        const q = filter.value.trim().toLowerCase();
        list.replaceChildren();
        const shown = rows.filter((r) => (!mergeFrom || r.id !== mergeFrom.id) && (!q || r.name.toLowerCase().includes(q) || r.aliases.some((a) => a.toLowerCase().includes(q))));
        for (const r of shown.slice(0, 200)) {
          const row = sheetRow(`ph ${ENTITY_KIND_ICONS[r.kind] || "ph-at"}`, r.name, async () => {
            if (!mergeFrom) {
              close();
              openEntityPage(r.id);
              return;
            }
            const done = await apiJson(`/entities/${mergeFrom.id}/merge`, { method: "POST", body: JSON.stringify({ into_id: r.id }) }).catch((e) => {
              toast(e.message, true);
              return null;
            });
            if (!done) return;
            close();
            const from = mergeFrom.id;
            toastEntityMerge(done, from, r.id, (merged) => openEntityPage(merged ? done.kept : from));
            openEntityPage(done.kept);
          });
          const count = document.createElement("span");
          count.className = "muted entity-count";
          count.textContent = String(r.notes);
          row.appendChild(count);
          list.appendChild(row);
        }
        if (!shown.length) {
          const p = document.createElement("p");
          p.className = "muted inbox-empty";
          p.textContent = rows.length ? "No name matches." : "No people or things yet. Atlas finds them as it reads your notes.";
          list.appendChild(p);
        }
      };
      filter.addEventListener("input", draw);
      draw();
      card.append(filter, list);
    },
  });
}
