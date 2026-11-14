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

  digestMore.threads = drawThreads;
})();
