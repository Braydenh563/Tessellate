// connections.js: the Connections sheet and the rows the Notes column shares
// with it. A lazy piece (app.js LAZY_MODULES), moved out of menus.js on
// 2026-10-10 (INBOX 784) to keep the boot scripts under their gzip total when
// the rows became a list: boot code reaches `openConnections` through
// LAZY_ENTRY_POINTS, and the Notes column (notes-list.js) loads it before it
// draws. `docBacklinkContext` stays in menus.js, which a document's panel shares.

// The Connections block (REDESIGN.md §R7.3 item 1), for a note or a document.
// `kind` is the API prefix ("entries" or "documents"). Direction is kept: "this
// points at that" and "that points at this" are different facts.
async function openConnections(kind, id, subject) {
  const overlay = $("connections-overlay");
  const list = $("connections-list");
  const status = $("connections-status");
  status.classList.remove("error");
  status.textContent = "Loading…";
  list.replaceChildren();
  $("connections-subject").textContent = subject || "";
  overlay.classList.remove("hidden");
  //: "Open in the sidebar" is the same answer drawn as the Notes column, so it
  //: is offered where that column fits (a note, on a window wide enough).
  const dock = $("connections-dock");
  dock.dataset.id = kind === "entries" ? String(id) : "";
  dock.classList.toggle("hidden", !(kind === "entries" && typeof notesRailWide !== "undefined" && notesRailWide.matches));
  $("connections-close").focus();

  let data;
  try {
    data = await apiJson(`/${kind}/${id}/connections`);
    if (kind === "entries") data = withBacklinks(data, await apiJson(`/entries/${id}/backlinks`, { silent: true }).catch(() => null), id);
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
    return;
  }
  status.textContent = "";

  const shown = buildConnectionGroups(list, kind, data, () => overlay.classList.add("hidden"));
  if (!shown) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent =
      kind === "entries"
        ? "Nothing is joined to this note yet. Link it to another note, attach it to a document, or drop it on a whiteboard."
        : "Nothing is joined to this document yet. Attach a note or a reference to it.";
    list.appendChild(empty);
  }
}

//: Rows whose titles collide get a second cue: the category, else the day,
//: else day and time, else the note's number. Pure, tested in node
//: (tests/test_connection_row_cues.py).
function connectionRowCues(rows) {
  const byTitle = new Map();
  for (const r of rows) {
    const key = r.is_private ? "\u0000private" : String(r.preview || "").trim().toLowerCase();
    if (!byTitle.has(key)) byTitle.set(key, new Map());
    byTitle.get(key).set(r.id, r);
  }
  const when = (iso, withTime) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    //: The year only when it is not this one: a cue has to fit beside a
    //: title in a 17rem column.
    const thisYear = d.getFullYear() === new Date().getFullYear();
    const day = d.toLocaleDateString(undefined, thisYear
      ? { day: "numeric", month: "short" }
      : { day: "numeric", month: "short", year: "numeric" });
    return withTime ? `${day}, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", ...clockOptions() })}` : day;
  };
  //: The first of these that tells every note in the clash apart wins; the
  //: note's own number is the last resort, because two notes written in the
  //: same minute in the same category are otherwise identical to a reader.
  const ladder = [
    (n) => n.category || "",
    (n) => when(n.created_at, false),
    (n) => when(n.created_at, true),
    (n) => [n.category, when(n.created_at, true), `note ${n.id}`].filter(Boolean).join(", "),
  ];
  const cues = new Map();
  for (const group of byTitle.values()) {
    if (group.size < 2) continue;
    const notes = [...group.values()];
    for (const cueOf of ladder) {
      const labels = notes.map(cueOf);
      if (labels.every(Boolean) && new Set(labels).size === notes.length) {
        notes.forEach((n, i) => cues.set(n.id, labels[i]));
        break;
      }
    }
  }
  return cues;
}

//: GRAPH_PLAN KG1: `/entries/{id}/backlinks` folded into a note's connections.
//: An incoming note row gains the sentence that links it; the text-only
//: "Mentions it" rows give way to the Unlinked mentions group, which says the
//: same with its sentence and a Link button.
function withBacklinks(data, back, id) {
  if (!data || !back) return data;
  const context = new Map();
  for (const row of back.links || []) if (row.kind === "note" && !context.has(row.id)) context.set(row.id, row);
  const incoming = (data.incoming || []).filter((r) => !(r.link_id == null && r.reason === "Mentions it"));
  return { ...data, incoming, mentions: back.mentions || [], backlinkContext: context, subjectId: id };
}

//: One click: the server checks the span still says the name, rewrites it to
//: [[the words]] and saves through the source's own route (409 if it moved).
async function linkNoteMention(subjectId, row, button) {
  button.disabled = true;
  try {
    //: The source's text is read before and after, because the server rewrites
    //: it in place and Undo puts the old words back (INBOX 898).
    const sourcePath = row.kind === "note" ? `/entries/${row.id}` : `/documents/${row.id}`;
    const textBefore = (await apiJson(sourcePath).catch(() => null))?.content;
    await apiJson(`/entries/${subjectId}/mentions/link`, {
      method: "POST",
      body: JSON.stringify({ kind: row.kind, id: row.id, start: row.start, end: row.end }),
    });
    const textAfter = (await apiJson(sourcePath).catch(() => null))?.content;
    if (typeof textBefore === "string" && typeof textAfter === "string" && textBefore !== textAfter) {
      pushRequestUndo(`Linked a mention in ${row.title}`, sourcePath, "PUT", { content: textBefore }, { content: textAfter }, () => (row.kind === "note" ? refreshEntries([row.id]) : undefined));
    }
    toast(`Linked from ${row.title}.`);
  } catch (error) {
    toast(error.message, true);
  }
  if (row.kind === "note") await refreshEntries([row.id]);
  renderNotesRail();
  if (!$("connections-overlay").classList.contains("hidden")) openConnections("entries", subjectId, $("connections-subject").textContent);
}

//: **One list row** (INBOX 784, the owner: "redesign Connections ... as a list
//: recipe"): a glyph, the title, and a muted subline (the kind, the category
//: or day, the reason it is listed) in one quiet button with a tint on hover,
//: never a bordered button per row. The sheet, the Notes rail and the rail's
//: forgotten notes all draw it here. `sub` is plain text.
function connectionRowEl(icon, name, title, sub, onOpen) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = "connection-row";
  item.title = title;
  const glyph = document.createElement("i");
  glyph.className = `ph ph-${icon.replace(/^ph:/, "")} connection-row-icon`;
  glyph.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.className = "connection-row-text";
  const label = document.createElement("span");
  label.className = "connection-row-title";
  label.textContent = name;
  text.appendChild(label);
  if (sub) {
    const line = document.createElement("span");
    line.className = "connection-row-cue";
    line.textContent = sub;
    text.appendChild(line);
  }
  item.append(glyph, text);
  item.addEventListener("click", onOpen);
  return item;
}

//: The groups for the sheet and the Notes rail (one builder, so they agree);
//: `beforeOpen` is what leaving means; returns the rows drawn. Each group is
//: [heading, rows, row builder], as data so none loses its keyboard handling.
function buildConnectionGroups(list, kind, data, beforeOpen = () => {}) {
  const groups =
    kind === "entries"
      ? [
          ["ph:arrow-up-right This note links to", data.outgoing, noteRow, "out"],
          ["ph:arrow-down-left Notes that link here", data.incoming, (l) => withContext(noteRow(l), data.backlinkContext?.get(l.id)), "in"],
          ["ph:link-break Mentioned, not linked", data.mentions, mentionRow, "unlinked"],
          ["ph:file-text In these documents", data.documents, docRow, "documents"],
          ["ph:squares-four On these boards and maps", data.boards, boardRow, "boards"],
          ["ph:image Files it uses", data.files, fileRow, "files"],
          ["ph:users People and projects it names", data.names, nameRow, "names"],
        ]
      : [
          ["ph:note Notes attached", data.notes, noteRow, "notes"],
          ["ph:bookmark-simple References", data.bookmarks, bookmarkRow, "references"],
          ["ph:image Files it uses", data.files, fileRow, "files"],
        ];

  function row(label, title, onOpen, sub = "") {
    const [icon, ...words] = label.split(" ");
    return connectionRowEl(icon, words.join(" "), title, sub, () => {
      beforeOpen();
      onOpen();
    });
  }
  //: Two rows whose titles collide carry a quiet second cue
  //: (`connectionRowCues`); the rest carry none.
  const noteRows = kind === "entries"
    ? [...(data.outgoing || []), ...(data.incoming || [])]
    : [...(data.notes || [])];
  const cues = connectionRowCues(noteRows);
  function noteRow(link) {
    // A private note contributes the fact of the connection and not its
    // words: the server sends "Private note" as the preview, and the flag
    // is what lets this say so rather than showing a label that reads like
    // a real (empty-looking) note title.
    const label = link.is_private ? "ph:lock Private note" : `ph:note ${link.preview}`;
    const why = link.reason ? `\nWhy: ${link.reason}` : "";
    const cue = cues.get(link.id);
    //: KG3: the link's kind, named from this end (an incoming row reads the
    //: inverse: "Has part").
    const kindName = link.link_label && link.link_type !== "related" ? link.link_label : "";
    //: The subline: the link's kind, then what tells this note apart (the
    //: category, or the day and time when two titles collide).
    const sub = [kindName, cue || link.category || ""].filter(Boolean).join(" · ");
    return row(label, `Open this note${cue ? ` (${cue})` : ""}${kindName ? `\nKind: ${kindName}` : ""}${why}`, () => flashEntry(link.id), sub);
  }
  function withContext(item, context) {
    if (!context) return item;
    const both = document.createDocumentFragment();
    both.append(item, docBacklinkContext(context));
    return both;
  }
  function mentionRow(m) {
    const isDoc = m.kind === "document";
    const item = row(`${isDoc ? "ph:file-text" : "ph:note"} ${m.title}`, isDoc ? `Open “${m.title}”` : "Open this note", () =>
      isDoc ? openDocumentFromNote(m.id) : flashEntry(m.id), isDoc ? "Document" : "Note"
    );
    const foot = document.createElement("div");
    foot.className = "doc-backlink-foot";
    const link = smallButton("ph:link Link", "Turn these words into a link to this note", () => linkNoteMention(data.subjectId, m, link));
    link.classList.add("doc-backlink-action");
    //: A name with a square bracket cannot be written as a [[link]] (the
    //: server says so per row): disabled with its reason on the title, as
    //: DESIGN.md asks of any disabled control, not a button that reports
    //: "Linked" and links nothing.
    if (m.linkable === false) {
      link.disabled = true;
      link.title = m.why || "This name can't be written as a [[link]].";
    }
    foot.appendChild(link);
    const both = withContext(item, m);
    both.appendChild(foot);
    return both;
  }
  function docRow(doc) {
    return row(`ph:file-text ${doc.title}`, `Open “${doc.title}”`, () =>
      openDocumentFromNote(doc.id), doc.file_type ? String(doc.file_type) : "Document"
    );
  }
  function boardRow(board) {
    // `kind` is "board" or "map" from the one reader the Referenced-by row
    // uses (INBOX 246): a map is a different surface and gets its own icon.
    const icon = board.kind === "map" ? "ph:tree-structure" : "ph:squares-four";
    return row(`${icon} ${board.title}`, `Open “${board.title}”`, () =>
      openWhiteboardBoard(board.id ?? null), board.kind === "map" ? "Mind map" : "Whiteboard"
    );
  }
  //: WORLD_CLASS B4: a name the note says opens its person or project page.
  function nameRow(entity) {
    const icon = { person: "ph:user", project: "ph:kanban", place: "ph:map-pin", organisation: "ph:buildings" }[entity.kind] || "ph:at";
    const kind = entity.kind ? entity.kind[0].toUpperCase() + entity.kind.slice(1) : "Name";
    return row(`${icon} ${entity.name}`, `Open the page for ${entity.name}`, () => openEntityPage(entity.id), kind);
  }
  function bookmarkRow(mark) {
    return row(`ph:bookmark-simple ${mark.title || mark.url}`, `Open ${mark.url}`, () =>
      window.open(safeHref(mark.url), "_blank", "noopener,noreferrer"), mark.url
    );
  }
  function fileRow(file) {
    const name = file.original_name || file.name;
    // `focusLibraryFile` (library.js) rather than the three steps this used
    // to take inline: the media view is two sub-tabs now, so which one to
    // click depends on whether the file is an image, and that decision
    // belongs in one place.
    return row(`ph:image ${name}`, `Find “${name}” in the Library`, () =>
      focusLibraryFile(name, file.url || file.name), "File"
    );
  }

  let shown = 0;
  const counts = [];
  for (const [heading, rows, build, short] of groups) {
    if (!rows || !rows.length) continue;
    shown += rows.length;
    counts.push([heading, rows.length, short]);
    const section = document.createElement("div");
    section.className = "connection-group";
    const head = document.createElement("p");
    head.className = "connection-heading";
    setLabel(head, heading);
    const count = document.createElement("span");
    count.className = "connection-count";
    count.textContent = String(rows.length);
    head.appendChild(count);
    section.appendChild(head);
    const holder = document.createElement("div");
    holder.className = "connection-rows";
    for (const item of rows) holder.appendChild(build(item));
    section.appendChild(holder);
    list.appendChild(section);
  }
  //: The tally as chips at the top, when there is more than one kind of thing
  //: to tell apart: each is the group's glyph and its count, and its name is
  //: the group's heading (so a screen reader hears "3 Files it uses").
  if (counts.length > 1) {
    const stats = document.createElement("div");
    stats.className = "connection-stats";
    for (const [heading, n, short] of counts) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.title = heading.split(" ").slice(1).join(" ");
      setLabel(chip, `${heading.split(" ")[0]} ${n} ${short}`);
      stats.appendChild(chip);
    }
    list.prepend(stats);
  }
  return shown;
}


//: The Notes column's answer for one note, drawn (moved out of `renderNotesRail` for the gzip budget; INBOX 1525).
async function drawNotesRail(entry, key) {
  const body = $("notes-rail-body");
  const seq = ++notesRailSeq;
  let answer = notesRailCache.get(key);
  if (!answer) {
    const [links, near, back] = await Promise.all([
      apiJson(`/entries/${entry.id}/connections`, { silent: true }).catch(() => null),
      apiJson(`/resurface/near/${entry.id}`, { silent: true }).catch(() => null),
      apiJson(`/entries/${entry.id}/backlinks`, { silent: true }).catch(() => null),
    ]);
    answer = { links: withBacklinks(links, back, entry.id), near };
    if (links) notesRailCache.set(key, answer);
  }
  if (seq !== notesRailSeq) return;
  body.removeAttribute("aria-busy");
  body.dataset.key = answer.links ? key : "";
  body.replaceChildren();
  const count = $("notes-rail-count");
  if (!answer.links) {
    const failed = document.createElement("p");
    failed.className = "muted notes-rail-note";
    failed.textContent = "Couldn't read this note's connections.";
    body.appendChild(failed);
    count.textContent = "";
    count.hidden = true;
    return;
  }
  const shown = buildConnectionGroups(body, "entries", answer.links);
  //: Forgotten takes days: a note written minutes ago is not slipping away
  //: (dog3-1026 row 14, "Forgotten" on notes seconds old).
  const nearItems = ((answer.near && answer.near.items) || []).filter((item) => (item.age_days || 0) >= 3);
  if (nearItems.length) body.appendChild(notesRailNearGroup(nearItems));
  //: One chip, the panel head's one fact: how many things this note is
  //: joined to. The forgotten notes are suggestions, not connections, so they
  //: are not counted in it.
  //: Unlinked mentions are offers, not links, so they are not counted.
  const linked = shown - (answer.links.mentions || []).length;
  count.textContent = linked === 1 ? "1 link" : `${linked} links`;
  //: "0 links" over a list of suggestions read as a contradiction; the
  //: empty line below says it once there is nothing at all (dog3-1026 row 14).
  count.hidden = !linked;
  if (!shown && !nearItems.length) {
    const empty = document.createElement("p");
    empty.className = "muted notes-rail-note";
    empty.textContent =
      "Nothing is joined to this note yet. Link it to another note, attach it to a document, or drop it on a whiteboard.";
    body.appendChild(empty);
  }
  //: "We could not ask" is a different fact from "nothing is faded near
  //: this", and only the first is worth a line: a notebook too small to rank
  //: (`resurface.MIN_NOTEBOOK`) answers an empty list by design.
  if (!answer.near) {
    const failed = document.createElement("p");
    failed.className = "muted notes-rail-note";
    failed.textContent = "Couldn't look for forgotten notes near this one.";
    body.appendChild(failed);
  }

  //: The forgotten notes, drawn as one more connection group so the column reads
  //: as one list with one row recipe. Each row carries the route's own sentence
  //: for why it was chosen ("120 days old, no links, never opened"), which is
  //: checkable where a score would not be.
  function notesRailNearGroup(items) {
    const section = document.createElement("div");
    section.className = "connection-group notes-rail-near";
    const head = document.createElement("p");
    head.className = "connection-heading";
    setLabel(head, "ph:hourglass-medium Forgotten, and close to this");
    const count = document.createElement("span");
    count.className = "connection-count";
    count.textContent = String(items.length);
    head.appendChild(count);
    section.appendChild(head);
    const holder = document.createElement("div");
    holder.className = "connection-rows";
    for (const item of items) {
      //: The route's own sentence is the row's subline, in the same list recipe
      //: as every other connection row (`connectionRowEl`, menus.js).
      const row = connectionRowEl(
        "ph:note", item.title, item.reason ? `Open this note\nWhy: ${item.reason}` : "Open this note", item.reason || "",
        () => flashEntry(item.id)
      );
      holder.appendChild(row);
    }
    section.appendChild(holder);
    return section;
  }
}

