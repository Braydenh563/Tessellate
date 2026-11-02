// note-panels.js: the rows a note card's menu opens under it, "Similar notes",
// "Referenced by", "Forgotten notes like this", and the reminders chip's list.
// Moved out of notes-list.js on 2026-10-05 (the boot-script gzip budget,
// ratchet in tests/test_static_compression.py): each opens only from a menu
// item or a chip a person presses, so none of it is needed to draw the list.
// Loaded on first use by `LAZY_MODULES.notePanels` (app.js), whose stand-ins
// for `toggleRelated`, `toggleReferences`, `toggleFaded` and
// `toggleNoteReminders` fetch this file and then call the real one; all four
// are `async` and nobody reads what they return.
//
// `similarNoteRow` is here too, at the bottom: its only callers are
// `toggleRelated` and the edit form's own "Similar" panel
// (note-edit-panels.js), and it returns an element, which a stand-in could not
// give a caller at boot. The two files load together as one bundle
// (`LAZY_MODULES.notePanels`) so neither can run without it.
// `renderEntries` never reads `notePanel`, so the open-panel state living here
// costs the list nothing while this file is absent.

//: **One open panel, named by which one it is.** Three menu items open a row
//: under a note card: "Similar notes", "Referenced by" and "Forgotten notes
//: like this". Each kept its own open-id, and two of them said in their own
//: comments that there should only be one, which is what happens when a
//: third arrives: opening one left the others' ids set, so the next click on
//: a *different* panel toggled the stale id instead and did nothing visible.
//:
//: One id and one kind, because the panels genuinely are one thing: they draw
//: the same `.entry-links` row in the same place on the same card, and
//: `renderEntries` clears whichever is showing, so only one can ever be on
//: screen anyway. The variable now says that rather than three variables
//: agreeing by accident.
const notePanel = { id: null, kind: null };

//: Toggle the named panel on a note: returns true when it should now be
//: drawn, false when the click closed it. `renderEntries` between the two is
//: what takes the previous panel off, whichever card it was on.
function toggleNotePanel(entry, kind) {
  const open = notePanel.id === entry.id && notePanel.kind === kind;
  Object.assign(notePanel, open ? { id: null, kind: null } : { id: entry.id, kind });
  renderEntries();
  return !open;
}

//: Is the panel this render is finishing still the one that was asked for? An
//: `await` sits between the click and the append, and in that window the
//: reader can open something else or close this one.
function notePanelStillOpen(entry, kind) {
  return notePanel.id === entry.id && notePanel.kind === kind;
}


//: A panel that opens takes the keyboard (audit 1031 N11): the menu that
//: opened it has closed, and focus fell to the page. The panel is a region
//: with no role of its own, so it is focusable by script only.
function focusPanel(row) {
  row.tabIndex = -1;
  restoreFocusTo(row);
}

async function toggleRelated(entry) {
  if (!toggleNotePanel(entry, "related")) return;
  const related = await apiJson(`/entries/${entry.id}/related`).catch(() => []);
  const card = document.querySelector(`#entry-list li[data-id="${entry.id}"]`);
  if (!card || !notePanelStillOpen(entry, "related")) return;
  const row = document.createElement("div");
  row.className = "entry-links";
  const label = document.createElement("span");
  label.className = "muted";
  label.textContent = related.length ? "Similar:" : "No similar notes found.";
  row.appendChild(label);
  //: With no meaning engine the list is empty for a reason the person can fix.
  if (!related.length && meaningEngineMissing()) {
    label.textContent = "No similar notes found: the meaning engine is not ready.";
    const setup = document.createElement("button");
    setup.type = "button";
    setup.className = "ghost small";
    setup.textContent = "Set it up";
    setup.addEventListener("click", () => openSettingsModal("models"));
    row.appendChild(setup);
  }
  for (const other of related) {
    row.appendChild(similarNoteRow(entry, other, () => {
      // Nothing else on this card changes, so re-rendering the whole list
      // would only cost the open panel its place.
      if (!row.querySelector(".entry-related-row")) {
        label.textContent = "All similar notes are linked.";
      }
    }));
  }
  card.appendChild(row);
  focusPanel(row);
}

//: **What points at this note** (INBOX 246, the owner: "I want it to show in
//: notes if they are attached to or referenced in/by a document, note,
//: whiteboard, or mindmap").
//:
//: Deliberately the same shape as `toggleRelated` above, down to the single
//: open-id variable: the two answer neighbouring questions ("what is like
//: this" and "what points at this"), they open in the same place on the same
//: card from the same menu, and a second way of drawing a row under a note
//: would be a second thing to keep consistent for no gain.
//:
//: What each kind of reference is called on the chip, and the icon that says
//: it without being read. A table rather than a chain of ternaries, because
//: the kinds are the four the owner named and a missing one should be
//: obvious rather than silently falling through to "note".
const REFERENCE_KIND_LABELS = {
  document: ["ph:file-text", "document"],
  note: ["ph:note", "note"],
  board: ["ph:squares-four", "board"],
  map: ["ph:tree-structure", "map"],
};

//: **The faded notes nearest this one** (INBOX 261). `GET
//: /resurface/near/{entry_id}` shipped with the rest of resurfacing and no
//: `frontend/js/*.js` ever named it: found by `scratchpad/probe_dead_routes.py`,
//: the same scan that found WORLD_CLASS_PLAN I9's whole backend built with no
//: screen at all. A ranking nobody can read is a ranking that does not exist.
//:
//: **Not the same question as "Similar notes" above**, which is why it is its
//: own row rather than a filter on that one. `/entries/{id}/related` answers
//: "what means the same as this", newest and busiest notes included;
//: `resurface.for_context` answers "what have you forgotten that bears on
//: this", ranking by age, links and opens first and nearness second. The
//: first is a lookup, the second is the thing this app is for.
//:
//: One open panel at a time across all three: see `notePanel` above, which is
//: the single piece of state the three share.

async function toggleFaded(entry) {
  if (!toggleNotePanel(entry, "faded")) return;
  const answer = await apiJson(`/resurface/near/${entry.id}`, { silent: true }).catch(() => null);
  const card = document.querySelector(`#entry-list li[data-id="${entry.id}"]`);
  if (!card || !notePanelStillOpen(entry, "faded")) return;
  const row = document.createElement("div");
  row.className = "entry-links";
  const label = document.createElement("span");
  label.className = "muted";
  const items = ((answer && answer.items) || []).filter((item) => (item.age_days || 0) >= 3);
  //: Three states, not two, exactly as `toggleReferences` has them: "nothing
  //: is faded near this" and "we could not ask" are different facts, and the
  //: second has a third cause of its own here (a notebook under
  //: `resurface.MIN_NOTEBOOK` is refused a ranking by design, so an empty
  //: answer on a small notebook is not a finding about this note).
  label.textContent = !answer
    ? "Couldn't look for forgotten notes near this one."
    : items.length
      ? "Forgotten, and close to this:"
      : "Nothing faded is close to this note.";
  row.appendChild(label);
  for (const item of items) {
    const wrap = document.createElement("span");
    wrap.className = "entry-related-row";
    const fadedChip = chip("", "link", () => flashEntry(item.id));
    setLabel(fadedChip, `ph:hourglass-medium ${item.title}`);
    //: The card's own sentence, which the route sends precisely so a panel
    //: can say why it chose something: "120 days old, no links, never
    //: opened" is checkable and "0.82" is not.
    fadedChip.title = item.reason || item.preview || "";
    wrap.appendChild(fadedChip);
    const why = document.createElement("span");
    why.className = "muted entry-reference-how";
    why.textContent = item.reason || "";
    wrap.appendChild(why);
    row.appendChild(wrap);
  }
  card.appendChild(row);
  focusPanel(row);
}

//: **This note's reminders, under the card** (INBOX 309). The other half of
//: the chip above.
//:
//: The same shape as `toggleReferences` and `toggleFaded` below, down to the
//: shared `notePanel` state, because it answers a neighbouring question about
//: the same note in the same place: a second way of drawing a row under a
//: note is a second thing to keep consistent for no gain.
//:
//: Live reminders only, which is what the chip counted. A reminder ticked off
//: last month is not something this note still wants from you, and the
//: Reminders tab is where a finished one is still readable.
async function toggleNoteReminders(entry) {
  if (!toggleNotePanel(entry, "reminders")) return;
  const answer = await apiJson(
    `/reminders?entry_id=${entry.id}&include_done=false&limit=20`,
    { silent: true }
  ).catch(() => null);
  const card = document.querySelector(`#entry-list li[data-id="${entry.id}"]`);
  if (!card || !notePanelStillOpen(entry, "reminders")) return;
  const row = document.createElement("div");
  row.className = "entry-links";
  const label = document.createElement("span");
  label.className = "muted";
  const items = Array.isArray(answer) ? answer : [];
  //: Three states, not two, the rule the two panels beside this one already
  //: follow: "nothing is due from this note" and "we could not ask" are
  //: different facts.
  label.textContent = !answer
    ? "Couldn't read this note's reminders."
    : items.length
      ? "Reminds you to:"
      : "Nothing is due from this note.";
  row.appendChild(label);
  for (const item of items) {
    const wrap = document.createElement("span");
    wrap.className = "entry-related-row";
    const due = relativeWhen(item.due_at);
    //: `flashReminder` rather than a jump of this panel's own: a
    //: reminder has one home, it loads the tab's list, clears the filter
    //: that would hide it and highlights the row. A second way in here
    //: would be a fifth place a reminder can be read.
    const alarm = chip("", "link", () => flashReminder(item.id));
    setLabel(alarm, `ph:alarm ${item.text}`);
    alarm.title = `Due ${due}. Press to open it in Reminders`;
    wrap.appendChild(alarm);
    const when = document.createElement("span");
    when.className = "muted entry-reference-how";
    when.textContent = due;
    wrap.appendChild(when);
    row.appendChild(wrap);
  }
  card.appendChild(row);
  focusPanel(row);
}

async function toggleReferences(entry) {
  if (!toggleNotePanel(entry, "references")) return;
  const answer = await apiJson(`/entries/${entry.id}/references`).catch(() => null);
  const card = document.querySelector(`#entry-list li[data-id="${entry.id}"]`);
  if (!card || !notePanelStillOpen(entry, "references")) return;
  const row = document.createElement("div");
  row.className = "entry-links";
  const label = document.createElement("span");
  label.className = "muted";
  const items = (answer && answer.items) || [];
  //: Three states, not two: "nothing points at this" and "we could not ask"
  //: are different facts and a person acting on the first one deserves to
  //: know it was really the second.
  label.textContent = !answer
    ? "Couldn't check what points at this note."
    : items.length
      ? "Referenced by:"
      : "Nothing points at this note yet.";
  row.appendChild(label);
  for (const item of items) {
    const [icon, word] = REFERENCE_KIND_LABELS[item.kind] || ["ph:note", item.kind];
    const wrap = document.createElement("span");
    wrap.className = "entry-related-row";
    const refChip = chip("", "link", () => {
      //: A board and a map open in the Library, a note in Notes, a document
      //: in its editor. Each already has one way in; this is not a fifth.
      //: Each kind already has exactly one way in, and this uses it rather
      //: than becoming a fifth. The board's opener is a lazy entry point
      //: (app.js stand-in), so a call before the bundle lands loads it.
      if (item.kind === "board" || item.kind === "map") {
        openWhiteboardBoard(item.id);
      } else if (item.kind === "document") {
        openDocumentFromNote(item.id);
      } else {
        flashEntry(item.id);
      }
    });
    setLabel(refChip, `${icon} ${item.label}`);
    //: Read out loud rather than assembled: "This board on it" is what
    //: pasting the server's phrase after the kind gives you, and it is not a
    //: sentence. The phrase beside the chip stays terse because it sits in a
    //: row of them; the tooltip is where there is room to say it properly.
    refChip.title = {
      "on it": `This ${word} has this note on it`,
      "links to it": `This ${word} links to this note`,
      "mentions it": `This ${word} mentions this note by name`,
    }[item.how] || `This ${word} ${item.how}`;
    wrap.appendChild(refChip);
    //: The relationship, beside the thing rather than inside its name: "on
    //: it", "links to it" and "mentions it" are three different strengths of
    //: claim and the middle one is the only one somebody chose.
    const how = document.createElement("span");
    how.className = "muted entry-reference-how";
    how.textContent = item.how;
    wrap.appendChild(how);
    row.appendChild(wrap);
  }
  card.appendChild(row);
  focusPanel(row);
}

// One similar note, with the button that turns it into a real link.
//
// Shared by both places this app shows "≈ Similar", the panel that stays
// open while a note is being edited, and the "≈ Similar notes" menu item on
// a note card. They were already two near-identical loops; adding an action
// to only one of them is exactly how the two would have drifted, and the
// ask named the card one specifically ("like in the similar notes shown in
// the notes tab").
//
// A button, not something either view does on its own: `≈` is a resemblance
// the embedding noticed, while a link is a claim the user makes. The reason
// is deduced server-side for a pair this similar (create_link's
// AUTO_REASON_THRESHOLD) and stays editable wherever links are shown, so
// nothing is asked for at this point.
function similarNoteRow(entry, other, onLinked) {
  //: The note's words without its "# " (INBOX 606: "≈ # Edit form probe 2").
  const shown = stripFrontmatter(other.content).trim().replace(/^#+[ \t]+/, "");
  const preview = shown.length > 50 ? shown.slice(0, 49) + "…" : shown;
  const wrap = document.createElement("span");
  wrap.className = "entry-related-row";
  //: **One chip, the + inside its end** (INBOX 709, the owner: "these plus
  //: buttons feel too separate from their notes"). The note and its Link were
  //: a chip and a button side by side; now the chip is the control, the whole
  //: of it the hover and the press, named for what pressing does.
  const linkIt = async () => {
    if (relChip.getAttribute("aria-disabled") === "true") return;
    relChip.setAttribute("aria-disabled", "true");
    try {
      const made = await apiJson(`/entries/${entry.id}/links`, {
        method: "POST",
        body: JSON.stringify({ target_id: other.id }),
      });
      pushLinkCreateUndo(entry.id, other.id, made, { target_id: other.id });
      toast("Linked.");
      wrap.remove();
      onLinked?.();
    } catch (error) {
      relChip.removeAttribute("aria-disabled");
      toast(error.message || "Couldn't link those notes.", true);
    }
  };
  const relChip = chip("", "link entry-related-chip", linkIt);
  //: Named by the note's first line, the way a person calls it.
  const name = noteNamePlain(preview) || preview;
  relChip.setAttribute("aria-label", `Link to ${name}`);
  relChip.title = `Link this note to “${preview}”`;
  //: The same mark the menu item that opens this row wears, drawn the same
  //: way: an `<i class="ph">` rather than the character U+2248, which came
  //: out in the page font at the text's own weight beside Phosphor icons in
  //: every neighbouring chip (INBOX 263).
  const relMark = document.createElement("i");
  relMark.className = "ph ph-approximate-equals ph-lead";
  relMark.setAttribute("aria-hidden", "true");
  relChip.appendChild(relMark);
  const previewSpan = document.createElement("span");
  renderInlineMarkdown(previewSpan, preview, [], true);
  relChip.appendChild(previewSpan);
  const add = document.createElement("i");
  add.className = "ph ph-plus entry-related-add";
  add.setAttribute("aria-hidden", "true");
  relChip.appendChild(add);
  wrap.appendChild(relChip);
  return wrap;
}

//: **Link mode** (a note card's "Link to another", the graph's link gesture):
//: moved here from notes-list.js on 2026-10-06 for the boot-script gzip
//: budget (INBOX 676 needed the room). Reached only by a gesture, called for
//: its effect, so `LAZY_ENTRY_POINTS.notePanels` stands in for it until this
//: file arrives (three seconds after boot at the latest).
//: Cancelling takes the instruction down with it: "Esc cancels" stayed up its
//: full life after Esc had (audit 1029 N14).
function linkCancel() {
  linkSource = null;
  for (const note of document.querySelectorAll("#toast-box .toast")) {
    if (note.textContent.startsWith("Now click Link")) dismissToast(note);
  }
  renderEntries();
}
function beginOrCompleteLink(entry) {
  //: **A draft and a saved note cannot be connected**, asked for directly,
  //: and refused by `manager.create_link` whichever route asks. Caught here as
  //: well so the answer arrives before the click that would fail: starting a
  //: link from a draft and hunting for a target, only to be told no at the
  //: end, is the worst order to learn a rule in.
  //:
  //: Two drafts are still fine; the rule is that drafts stay separate from the
  //: notebook, not from each other.
  if (linkSource !== null && linkSource !== entry.id) {
    const source = allEntries.find((e) => e.id === linkSource);
    if (source && Boolean(source.is_draft) !== Boolean(entry.is_draft)) {
      const draftFirst = Boolean(source.is_draft);
      linkCancel();
      toast(
        draftFirst
          ? "A draft can't be linked to a saved note. Save the draft first."
          : "A saved note can't be linked to a draft. Save the draft first.",
        "info"
      );
      return;
    }
  }
  if (linkSource === null) {
    linkSource = entry.id;
    toast("Now click Link on the entry you want to connect it to (Esc cancels).");
    renderEntries();
    return;
  }
  if (linkSource === entry.id) {
    linkCancel(); // clicked the same one again = cancel
    return;
  }
  const source = linkSource;
  const target = entry.id;
  linkSource = null;
  apiJson(`/entries/${source}/links`, {
    method: "POST",
    body: JSON.stringify({ target_id: target }),
  })
    .then((updated) => {
      toast("Linked.");
      let liveLinkId = updated.links.find((l) => l.entry_id === target)?.link_id;
      pushUndo(
        "Linked two notes",
        async () => {
          if (liveLinkId == null) return;
          await api(`/entries/${source}/links/${liveLinkId}`, { method: "DELETE" });
          await refreshEntries([source, target]);
        },
        async () => {
          const redone = await apiJson(`/entries/${source}/links`, {
            method: "POST",
            body: JSON.stringify({ target_id: target }),
          });
          liveLinkId = redone.links.find((l) => l.entry_id === target)?.link_id ?? liveLinkId;
          await refreshEntries([source, target]);
        }
      );
      return refreshEntries([source, target]);
    })
    .catch((error) => {
      toast(error.message, true);
      renderEntries();
    });
}
