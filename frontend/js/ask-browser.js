// ask-browser.js: the Ask tab as a smart browser for your notes (INBOX 1743,
// LEDGER L-chat-58). Lazy, in the askCompose bundle after ask-compose.js.
//
// Slice 1: a woven overview sends its threads on `support.threads` as
// `{label, note_ids}` (composer_story.threads). They are drawn as one chip row
// above Matching records; a press narrows that column to the thread's notes
// (client only: the cards are already loaded), a second press clears it, and
// the heading says "3 of 11". The answer text is untouched, and a chip is
// never an act, so no consent applies.

(() => {
  const browse = { threads: [], lit: -1 };
  const cards = () => [...document.querySelectorAll("#raw-results > li[data-id]")];

  //: One thread as the recipe's counted filter chip (DESIGN.md, a filter that carries a count).
  function askThreadChip(label, count, pressed, onClick) {
    const el = chip(label, "tag graph-filter-chip", onClick);
    el.setAttribute("aria-pressed", String(pressed));
    el.classList.toggle("is-lit", pressed);
    el.title = pressed ? "Show every record again" : `Show only the ${count} records in this thread`;
    const n = document.createElement("span");
    n.className = "library-chip-count";
    n.textContent = String(count);
    el.append(n);
    return el;
  }

  function paint() {
    const row = $("ask-threads");
    const all = cards();
    const lit = browse.threads[browse.lit];
    const keep = lit ? new Set(lit.note_ids.map(String)) : null;
    let shown = 0;
    for (const li of all) {
      const out = !!keep && !keep.has(li.dataset.id);
      li.classList.toggle("hidden", out);
      if (!out) shown += 1;
    }
    const tag = $("ask-records-shown");
    tag.textContent = `${shown} of ${all.length}`;
    tag.classList.toggle("hidden", !keep);
    //: Under 600px the heading is hidden and this one row stands for it (INBOX 1843).
    $("ask-records-count").textContent = keep ? `${shown} of ${all.length}` : String(all.length);
    row.replaceChildren(
      ...browse.threads.map((thread, i) =>
        askThreadChip(thread.label, thread.note_ids.length, i === browse.lit, () => {
          browse.lit = browse.lit === i ? -1 : i;
          paint();
          row.children[browse.lit === -1 ? i : browse.lit]?.focus();
        })
      )
    );
  }

  //: Draw the chips for an answer's threads, or clear them (null) when the cards are replaced.
  function drawThreads(threads) {
    const row = $("ask-threads");
    if (!row) return;
    const present = new Set(cards().map((li) => li.dataset.id));
    browse.lit = -1;
    browse.threads = (threads || [])
      .map((t) => ({ label: t.label, note_ids: (t.note_ids || []).filter((id) => present.has(String(id))) }))
      .filter((t) => t.note_ids.length > 1);
    row.classList.toggle("hidden", !browse.threads.length);
    if (!browse.threads.length) {
      row.replaceChildren();
      $("ask-records-shown").classList.add("hidden");
      $("ask-records-count").textContent = String(cards().length || "");
      return;
    }
    paint();
  }

  //: Slice 2: "Around this note" opens a note's linked and similar notes under its card, indented one
  //: step, as the Connections recipe's rows. The answer text and the column's cards are untouched; a
  //: row opens the note (`flashEntry`). A second press closes it. Both routes are the ones the note's
  //: own panels use (`/connections`, `/related`), so nothing new is asked of the server.
  async function around(li, button) {
    const open = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", String(open));
    li.querySelector(":scope > .ask-around")?.remove();
    if (!open) return;
    const id = li.dataset.id;
    const box = document.createElement("div");
    box.className = "ask-around";
    box.setAttribute("role", "group");
    box.setAttribute("aria-label", "Notes around this one");
    const say = (text) => {
      const p = document.createElement("p");
      p.className = "muted ask-around-note";
      p.textContent = text;
      box.append(p);
    };
    say("Looking for neighbours…");
    button.after(box);
    const [joined, like] = await Promise.all([
      lazyScript("/js/connections.js").catch(() => null),
      apiJson(`/entries/${id}/connections`, { silent: true }).catch(() => null),
      apiJson(`/entries/${id}/related`, { silent: true }).catch(() => []),
    ]).then(([, a, b]) => [a, b]);
    if (button.getAttribute("aria-expanded") !== "true") return;
    box.replaceChildren();
    if (!joined) return say("Could not load this note's neighbours.");
    const seen = new Set([Number(id)]);
    const rows = [];
    const add = (note, how) => {
      if (!note || seen.has(note.id)) return;
      seen.add(note.id);
      const name = note.is_private ? "Private note" : note.preview || note.title || `Note ${note.id}`;
      const sub = [how, note.category].filter(Boolean).join(" · ");
      rows.push(connectionRowEl(note.is_private ? "ph:lock" : "ph:note", name, `Open this note\n${note.reason || ""}`.trim(), sub, () => flashEntry(note.id)));
    };
    for (const note of joined.outgoing || []) add(note, "Linked");
    for (const note of joined.incoming || []) add(note, "Links here");
    for (const note of like || []) add({ ...note, preview: noteNamePlain(note.content, 80), reason: note.link_reason }, "Similar");
    if (!rows.length) return say("No linked or similar notes.");
    box.append(...rows);
  }
  digestMore.around = around;

  digestMore.threads = drawThreads;
})();
