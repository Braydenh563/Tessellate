// link-types.js: kinds of link, with the name each has from its other end
// (GRAPH_PLAN KG3, INBOX 528).
//
// Lazy, in the suggestions inbox's bundle (app.js, `LAZY_MODULES.inbox`):
// `openLinkTypeSheet(entryId, link)` from a link's ⋯ (Kind and properties),
// `openRelationTypesSheet()` from the command palette (the kinds a person
// added: rename, the other end's name, delete). The six built-ins are the
// server's (`/relation-types`), listed first and not editable.

async function linkTypesList() {
  return apiJson("/relation-types").catch(() => []);
}

/** "count: 4, since: 2026" and back. Numbers and yes/no read as themselves. */
function linkPropsText(props) {
  return Object.entries(props || {}).map(([k, v]) => `${k}: ${v === true ? "yes" : v === false ? "no" : v}`).join(", ");
}

function linkPropsParse(text) {
  const out = {};
  for (const part of (text || "").split(",")) {
    const [key, ...rest] = part.split(":");
    const name = (key || "").trim();
    if (!name) continue;
    const raw = rest.join(":").trim();
    out[name] = /^-?\d+(\.\d+)?$/.test(raw) ? Number(raw) : raw === "yes" ? true : raw === "no" ? false : raw;
  }
  return out;
}

//: A deleted kind comes back with Undo (undo-1005): the DELETE answers with
//: the row and the links it left untyped, and `restore` makes it again under
//: its own key (a rename kept the key) with those links typed again, unless
//: one was given another kind since. The notes repaint for the link chips.
//: Every note's link chips can carry the kind, so both directions repaint
//: the whole list: one full read, named once.
const relationTypesRepaint = () => loadEntries().catch(() => {});

function relationTypeDeleteUndo(gone) {
  const n = gone.links_untyped || 0;
  const remake = async () => {
    await apiJson("/relation-types", { method: "POST", body: JSON.stringify({ ...gone.restore, restore: true }) });
    relationTypesRepaint();
  };
  const action = pushUndo(`Deleted the kind of link “${gone.restore.name}”`, remake, async () => {
    await apiJson(`/relation-types/${gone.deleted}`, { method: "DELETE" });
    relationTypesRepaint();
  });
  toastAction(n ? `Deleted. ${n} link${n === 1 ? "" : "s"} kept, with no kind.` : "Deleted.", "Undo", async () => {
    settleUndoFromToast(action);
    await remake().catch((e) => toast(e.message, true));
  });
}

async function newRelationType() {
  const name = await promptDialog("Name the kind of link, as read from the note that links (for example: Part of)", "", { confirmLabel: "Next" });
  if (!name || !name.trim()) return null;
  const inverse = await promptDialog(`What is “${name.trim()}” called from the other end? (for example: Has part; leave empty if the same)`, "", { confirmLabel: "Create" });
  if (inverse === null || inverse === undefined) return null;
  const body = { name: name.trim(), inverse: inverse.trim() || null };
  const made = await apiJson("/relation-types", { method: "POST", body: JSON.stringify(body) }).catch((e) => {
    toast(e.message, true);
    return null;
  });
  if (made?.key) {
    pushUndo(
      `Added the kind of link “${body.name}”`,
      async () => {
        await apiJson(`/relation-types/${made.key}`, { method: "DELETE" });
        relationTypesRepaint();
      },
      async () => {
        await apiJson("/relation-types", { method: "POST", body: JSON.stringify(body) });
        relationTypesRepaint();
      }
    );
  }
  return made;
}

/** One link's kind and properties. */
async function openLinkTypeSheet(entryId, link) {
  const types = await linkTypesList();
  //: Each change has an app Undo (INBOX 537): the kind or properties it had.
  const send = (body) => apiJson(`/entries/${entryId}/links/${link.link_id}`, { method: "PATCH", body: JSON.stringify(body) })
    .then((saved) => { refreshEntries([entryId, link.entry_id]).catch(() => {}); return saved; });
  const patch = async (body, done) => {
    const before = "props" in body ? { props: link.props || {} } : { link_type: link.link_type ?? null };
    const saved = await send(body).catch((e) => {
      toast(e.message, true);
      return null;
    });
    if (!saved) return false;
    Object.assign(link, body);
    pushUndo(done.replace(/\.$/, ""), () => send(before), () => send(body));
    toast(done);
    return true;
  };
  openSheet({
    label: "Kind of link",
    sub: link.link_label ? `From this note: ${link.link_label}` : "No kind yet",
    name: "link-type",
    build: (card, close) => {
      const list = document.createElement("div");
      list.className = "sheet-list";
      const outgoing = link.direction !== "in";
      for (const t of types) {
        const label = !outgoing && t.directed && t.inverse ? t.inverse : t.name;
        //: The ticked kind is a toggle: pressing it again clears it (C31).
        const current = link.link_type === t.key;
        const row = sheetRow(`ph ${current ? "ph-check-circle" : "ph-circle"}`, label, async () => {
          const body = current ? { link_type: null } : { link_type: t.key };
          if (await patch(body, current ? "Kind cleared." : `Marked as ${label}.`)) close();
        });
        if (link.link_type === t.key) row.setAttribute("aria-current", "true");
        if (t.directed && t.inverse) {
          const other = document.createElement("span");
          other.className = "muted relation-type-hint";
          other.textContent = `⇄ ${outgoing ? t.inverse : t.name}`;
          other.title = `From the other end: ${outgoing ? t.inverse : t.name}`;
          row.appendChild(other);
        }
        list.appendChild(row);
      }
      list.appendChild(sheetRow("ph ph-minus-circle", "No kind", async () => {
        if (await patch({ link_type: null }, "Kind cleared.")) close();
      }));
      list.appendChild(sheetRow("ph ph-plus", "New kind…", async () => {
        close();
        const made = await newRelationType();
        if (made) await patch({ link_type: made.key }, `Marked as ${made.name}.`);
      }));
      list.appendChild(sheetRow("ph ph-list-bullets", link.props && Object.keys(link.props).length ? `Properties: ${linkPropsText(link.props)}` : "Properties…", async () => {
        close();
        const text = await promptDialog("Properties, as name: value, separated by commas (for example: count: 4, since: 2026)", linkPropsText(link.props));
        if (text === null || text === undefined) return;
        await patch({ props: linkPropsParse(text) }, "Properties saved.");
      }));
      card.appendChild(list);
    },
  });
}

/** The kinds of link, the built-ins first; the added ones can be renamed,
 *  given the other end's name, or deleted (their links keep no kind). */
async function openRelationTypesSheet() {
  const types = await linkTypesList();
  openSheet({
    label: "Kinds of link",
    sub: "A link can say what it is: Part of, Cites, Supports. Each has a name from the other end.",
    name: "relation-types",
    build: (card, close) => {
      const list = document.createElement("div");
      list.className = "sheet-list";
      for (const t of types) {
        const row = document.createElement("div");
        row.className = "row relation-type-row";
        const name = document.createElement("span");
        name.className = "relation-type-name";
        name.textContent = t.inverse ? `${t.name} / ${t.inverse}` : t.name;
        const note = document.createElement("span");
        note.className = "muted entity-count";
        note.textContent = t.built_in ? "Built in" : "Yours";
        row.append(name, note);
        if (!t.built_in) {
          const edit = async (body, done) => {
            const ok = await apiJson(`/relation-types/${t.key}`, { method: "PATCH", body: JSON.stringify(body) }).catch((e) => {
              toast(e.message, true);
              return null;
            });
            if (!ok) return;
            const wasKind = Object.fromEntries(Object.keys(body).map((key) => [key, t[key] ?? null]));
            pushRequestUndo(`Changed the kind of link “${t.name}”`, `/relation-types/${t.key}`, "PATCH", wasKind, body, relationTypesRepaint);
            toast(done);
            close();
            openRelationTypesSheet();
          };
          row.appendChild(kebabMenu([
            { label: "ph:pencil-simple Rename", title: "Change its name; links keep it", run: async () => {
              const next = await promptDialog("Rename", t.name, { confirmLabel: "Rename" });
              if (next && next.trim()) edit({ name: next.trim() }, "Renamed.");
            } },
            { label: "ph:arrows-left-right Name from the other end", title: "What it is called from the note linked to", run: async () => {
              const next = await promptDialog("Name from the other end (empty for the same)", t.inverse || "");
              if (next !== null && next !== undefined) edit({ inverse: next.trim() || null }, "Saved.");
            } },
            { label: "ph:trash Delete", title: "Delete this kind; its links stay, with no kind", group: "delete", run: async () => {
              if (!(await confirmDialog(`Delete “${t.name}”?\n\nIts links stay; they just lose their kind.`))) return;
              const gone = await apiJson(`/relation-types/${t.key}`, { method: "DELETE" }).catch((e) => {
                toast(e.message, true);
                return null;
              });
              if (!gone) return;
              close();
              openRelationTypesSheet();
              relationTypeDeleteUndo(gone);
            } },
          ], `Actions for ${t.name}`, { vertical: true }));
        }
        list.appendChild(row);
      }
      list.appendChild(sheetRow("ph ph-plus", "New kind…", async () => {
        close();
        if (await newRelationType()) openRelationTypesSheet();
      }));
      card.appendChild(list);
    },
  });
}
