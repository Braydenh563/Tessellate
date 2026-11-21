// ask-browser.js: the Ask tab as a smart browser for your notes (INBOX 1743,
// LEDGER L-chat-58). Lazy, in the askCompose bundle after ask-compose.js.
//
// Slice 1: a woven overview sends its threads on `support.threads` as
// `{label, note_ids}` (composer_story.threads). They are drawn as one chip row
// above Matching records; a press narrows that column to the thread's notes
// (client only: the cards are already loaded), a second press clears it, and
// the heading says "3 of 11". The answer text is untouched, and a chip is
// never an act, so no consent applies.
//
// Slice 3: the trail. Answer, then the thread filtered to, then the note opened
// around, is one small stack shown as a breadcrumb above the chips; its arrow,
// a crumb and the browser's Back each pop it. Each step pushes one history
// entry that keeps the Ask entry's `navId`, and `routerBack.browse`
// (router-overlays.js) hands a popstate to `onBack` first. A reload keeps the
// answer and not the trail: nothing here is stored.

(() => {
  const browse = { threads: [], lit: -1, note: null, pushed: 0, swallow: 0, wired: false };
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

  //: The trail as steps, root first: `pop` takes the stack back to that step.
  function steps() {
    const out = [{ text: "Answer", title: "Back to the whole answer", to: 0 }];
    const lit = browse.threads[browse.lit];
    if (lit) out.push({ text: lit.label, title: `Back to the ${lit.label} thread`, to: 1 });
    if (browse.note) out.push({ text: browse.note.name, title: browse.note.name, to: out.length });
    return out;
  }

  function paintTrail() {
    const list = steps();
    const nav = $("ask-browse-trail");
    nav.classList.toggle("hidden", list.length < 2);
    nav.querySelector("ol").replaceChildren(
      ...list.map((step, i) => {
        const li = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "linklike doc-crumb";
        button.textContent = step.text;
        button.title = step.title;
        if (i === list.length - 1) button.setAttribute("aria-current", "location");
        else button.addEventListener("click", () => popTo(i));
        li.append(button);
        return li;
      })
    );
    syncHistory(list.length - 1);
  }

  //: One browser-history entry a step, so the browser's Back is a step back. What is pushed is
  //: rewound when the trail shrinks by any other road (the arrow, a crumb, a new answer), so the
  //: app's own Back still counts the entries it made.
  function syncHistory(depth) {
    if (!browse.wired) return;
    try {
      for (; browse.pushed < depth; browse.pushed += 1) history.pushState({ ...history.state, browse: browse.pushed + 1 }, "", location.href);
      if (browse.pushed > depth) {
        browse.swallow = 1;
        history.go(-(browse.pushed - depth));
        browse.pushed = depth;
      }
    } catch {
      browse.wired = false;
    }
  }

  //: The stack back to `depth` steps under the answer: the note's neighbourhood first, then the thread.
  function popTo(depth) {
    while (steps().length - 1 > depth) {
      if (browse.note) closeNote();
      else browse.lit = -1;
    }
    paint();
  }

  function closeNote() {
    const { li, button } = browse.note;
    li.querySelector(":scope > .ask-around")?.remove();
    button.setAttribute("aria-expanded", "false");
    browse.note = null;
  }

  //: The browser's Back or Forward (router-overlays.js `routerBackHook`): true when it was spent on a step.
  function onBack(state) {
    if (browse.swallow) {
      browse.swallow = 0;
      return true;
    }
    const depth = (state && state.browse) || 0;
    if (steps().length - 1 <= depth) return false;
    browse.pushed = depth;
    popTo(depth);
    return true;
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
          if (browse.note) closeNote();
          browse.lit = browse.lit === i ? -1 : i;
          paint();
          row.children[browse.lit === -1 ? i : browse.lit]?.focus();
        })
      )
    );
    paintTrail();
  }

  //: Draw the chips for an answer's threads, or clear them (null) when the cards are replaced.
  function drawThreads(threads) {
    const row = $("ask-threads");
    if (!row) return;
    const present = new Set(cards().map((li) => li.dataset.id));
    browse.note = null;
    browse.lit = -1;
    browse.threads = (threads || [])
      .map((t) => ({ label: t.label, note_ids: (t.note_ids || []).filter((id) => present.has(String(id))) }))
      .filter((t) => t.note_ids.length > 1);
    row.classList.toggle("hidden", !browse.threads.length);
    if (!browse.threads.length) {
      row.replaceChildren();
      $("ask-records-shown").classList.add("hidden");
      $("ask-records-count").textContent = String(cards().length || "");
      paintTrail();
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
    if (browse.note) closeNote();
    if (!open) return paintTrail();
    button.setAttribute("aria-expanded", "true");
    const name = noteNamePlain(li.querySelector(":scope > .entry-content")?.textContent || "", 28) || "This note";
    browse.note = { li, button, name };
    paintTrail();
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
      apiJson(`/entries/${id}/related`, { silent: true }).catch(() => null),
    ]).then(([, a, b]) => [a, b]);
    if (browse.note?.button !== button) return;
    box.replaceChildren();
    if (!joined) return say("Couldn't load this note's neighbours.");
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

  //: Back's arrow, once. The history hook rides with the quick-note bundle (router-overlays.js);
  //: without it the trail still works in the page, with no browser-history entries.
  $("ask-browse-back").addEventListener("click", () => popTo(steps().length - 2));
  ensureModule("quickNote").then(() => {
    routerBack.browse = onBack;
    browse.wired = true;
  }).catch(() => {});

  digestMore.threads = drawThreads;
})();
