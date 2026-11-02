// tag-suggest.js: the tag list under a tags field (INBOX 435), loaded on the
// first focus of one (app.js `LAZY_MODULES.tagSuggest`).
//
// It replaces a native `<datalist>`. The owner, with a screenshot of
// Capture: "the dropdown arrow on the tags row in the capture subtab is not
// aligned vertically and the popup is awkwardly sized". Both were the
// browser's: Chromium draws the arrow and a list of its own size, and takes
// none of the app's styles. This is the rich picker's row (DESIGN.md, "a
// suggest list"), sized to the field and placed under it, and it knows what
// a datalist cannot: the field holds a comma-separated list, so it completes
// the tag being typed after the last comma and leaves out the ones already
// there, and each row says how many notes use the tag.
//
// Keys, the field keeping the focus throughout (a combobox): Down and Up move
// the lit row, Enter or Tab takes it, Escape closes. A press takes a row too.

let tagSuggest = null;

function tagSuggestToken(input) {
  const value = input.value;
  const cut = value.lastIndexOf(",");
  return { head: cut === -1 ? "" : value.slice(0, cut + 1), token: value.slice(cut + 1).trim() };
}

function closeTagSuggest() {
  if (!tagSuggest) return;
  const { input, box, onInput, onKey, onBlur, onWindow } = tagSuggest;
  input.removeEventListener("input", onInput);
  input.removeEventListener("keydown", onKey, true);
  input.removeEventListener("blur", onBlur);
  window.removeEventListener("resize", onWindow);
  window.removeEventListener("scroll", onWindow, true);
  input.setAttribute("aria-expanded", "false");
  input.removeAttribute("aria-activedescendant");
  box.remove();
  tagSuggest = null;
}

function placeTagSuggest() {
  const { input, box } = tagSuggest;
  const field = input.getBoundingClientRect();
  const room = { below: window.innerHeight - field.bottom, above: field.top };
  box.style.left = `${Math.max(8, field.left)}px`;
  box.style.width = `${Math.min(field.width, window.innerWidth - 16)}px`;
  //: Below when it fits, above when the field is near the window's foot
  //: (Capture's tags row usually is), never over the field itself.
  if (room.below >= 180 || room.below >= room.above) {
    box.style.top = `${field.bottom + 4}px`;
    box.style.bottom = "auto";
    box.style.maxHeight = `${Math.max(120, Math.min(280, room.below - 12))}px`;
  } else {
    box.style.top = "auto";
    box.style.bottom = `${window.innerHeight - field.top + 4}px`;
    box.style.maxHeight = `${Math.max(120, Math.min(280, room.above - 12))}px`;
  }
}

function fillTagSuggest() {
  const { input, list, counts } = tagSuggest;
  const { token } = tagSuggestToken(input);
  //: A tag just taken or entered in the note form: shut until the next key.
  if (!token && input.dataset.tagged) {
    tagSuggest.box.classList.add("hidden");
    input.setAttribute("aria-expanded", "false");
    return;
  }
  const have = new Set(input.value.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean));
  const wanted = token.toLowerCase().replace(/^#/, "");
  const names = Object.keys(counts).filter((tag) => {
    const lower = tag.toLowerCase();
    if (have.has(lower) && lower !== wanted) return false;
    return !wanted || lower.includes(wanted);
  });
  //: Starts-with first, then contains, each most used first (the route's
  //: own order).
  names.sort((a, b) => Number(!a.toLowerCase().startsWith(wanted)) - Number(!b.toLowerCase().startsWith(wanted)));
  //: **Nothing typed: the tags the note says first** (WORLD_CLASS 23, the
  //: "Study" bug). An empty field listed the most used tags first, so
  //: "study" and "university" headed the list on every note whatever it was
  //: about; a tag whose words are in the note's text now leads, and says so.
  const said = wanted ? new Set() : tagSuggestSaid(input, names);
  if (said.size) names.sort((a, b) => Number(!said.has(a)) - Number(!said.has(b)));
  const rows = names.slice(0, 40).map((tag, i) => {
    const row = richPickerRow({
      icon: "ph:hash",
      label: tag,
      about: `${nounCount(counts[tag], "note")}${said.has(tag) ? ", in this note" : ""}`,
      query: wanted,
      id: `tag-suggest-${i}`,
    });
    row.dataset.tag = tag;
    //: Pointing lights the row, as the arrow keys do (INBOX 441: "no
    //: changing hover states for this dropdown menu"): one lit row, whichever
    //: way it was reached, so Enter takes what the pointer is on.
    row.addEventListener("pointermove", () => {
      if (!tagSuggest || tagSuggest.active === i) return;
      tagSuggest.active = i;
      tagSuggest.moved = true;
      richPickerSetActive(list, rows, i);
      input.setAttribute("aria-activedescendant", row.id);
    });
    row.addEventListener("pointerdown", (event) => {
      event.preventDefault(); // keep the focus in the field
      takeTagSuggest(tag);
    });
    return row;
  });
  list.replaceChildren(...rows);
  tagSuggest.rows = rows;
  tagSuggest.moved = false;
  tagSuggest.active = rows.length ? 0 : -1;
  richPickerSetActive(list, rows, tagSuggest.active);
  input.setAttribute("aria-activedescendant", rows.length ? rows[0].id : "");
  tagSuggest.box.classList.toggle("hidden", !rows.length);
  input.setAttribute("aria-expanded", String(rows.length > 0));
  if (rows.length) placeTagSuggest();
}

//: The tags among `names` whose every word is in the note this field
//: belongs to: Capture's box, or the edit form's.
function tagSuggestSaid(input, names) {
  const box = input.id === "entry-tags" ? document.getElementById("entry-content") : input.closest("form, .card, li")?.querySelector("textarea");
  const words = new Set((box?.value || "").toLowerCase().match(/[a-z0-9]+/g) || []);
  if (!words.size) return new Set();
  const has = (word) => words.has(word) || words.has(`${word}s`) || (word.endsWith("s") && words.has(word.slice(0, -1)));
  return new Set(names.filter((tag) => {
    const parts = tag.toLowerCase().match(/[a-z0-9]+/g) || [];
    return parts.length > 0 && parts.every(has);
  }));
}

function takeTagSuggest(tag) {
  const { input } = tagSuggest;
  const { head } = tagSuggestToken(input);
  input.value = `${head}${head ? " " : ""}${tag}, `;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.setSelectionRange(input.value.length, input.value.length);
}

//: The entry point (app.js `LAZY_ENTRY_POINTS.tagSuggest`): opens the list
//: under `input`, or refreshes it when it is already open there.
//: The open waiting for the tags: its field, the field's text then, and
//: whether it was typed in meanwhile (one object, not a second top-level
//: flag).
let tagSuggestOpening = null;

async function openTagSuggest(input) {
  if (tagSuggest && tagSuggest.input === input) return fillTagSuggest();
  //: A press fires focusin and click together: one open at a time, or the
  //: second orphaned the first's list where Escape could not reach it.
  if (tagSuggestOpening?.input === input) {
    //: Typed in, not only pressed: the click of that same press is no change.
    if (input.value !== tagSuggestOpening.value) tagSuggestOpening.typed = true;
    return;
  }
  closeTagSuggest();
  const opening = (tagSuggestOpening = { input, value: input.value, typed: false });
  const counts = await apiJson("/tags", { silent: true, cacheMs: 30000 }).catch(() => null);
  tagSuggestOpening = null;
  if (!counts || !Object.keys(counts).length || document.activeElement !== input || tagSuggest) return;
  //: **Late is not now.** The first open waits for this file and for the
  //: tags. When they came after a tag was typed and entered (the field
  //: emptied again), the list opened then with every tag in it, over the
  //: note form's Save, and a press meant for Save took a tag nobody chose
  //: (tests-e2e/specs/notes.spec.js). `typed` sees the typing while the tags
  //: were fetched; the form's `data-tagged` sees a tag entered before this
  //: file arrived. Typing again, or a press in the field, opens it as before.
  if (!tagSuggestToken(input).token && (opening.typed || input.dataset.tagged)) return;
  const box = document.createElement("div");
  box.className = "tag-suggest card glass hidden";
  const list = document.createElement("ul");
  list.className = "rich-picker-list";
  list.setAttribute("role", "listbox");
  list.id = "tag-suggest-list";
  list.setAttribute("aria-label", "Tags you have used");
  box.appendChild(list);
  document.body.appendChild(box);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", list.id);
  const onInput = () => tagSuggest && fillTagSuggest();
  const onKey = (event) => {
    const state = tagSuggest;
    if (!state || state.box.classList.contains("hidden")) return;
    const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
    if (step) {
      event.preventDefault();
      state.active = (state.active + step + state.rows.length) % state.rows.length;
      state.moved = true;
      const lit = richPickerSetActive(state.list, state.rows, state.active);
      input.setAttribute("aria-activedescendant", lit?.id || "");
      lit?.scrollIntoView({ block: "nearest" });
    } else if ((event.key === "Enter" || event.key === "Tab") && state.active >= 0 && (state.moved || tagSuggestToken(input).token)) {
      //: Enter or Tab takes the lit row once something is typed or a row was
      //: chosen with the keys or the pointer; Enter on an untouched list
      //: still does what the field's own Enter does.
      event.preventDefault();
      event.stopPropagation();
      takeTagSuggest(state.rows[state.active].dataset.tag);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeTagSuggest();
    }
  };
  const onBlur = () => closeTagSuggest();
  const onWindow = () => tagSuggest && placeTagSuggest();
  input.addEventListener("input", onInput);
  input.addEventListener("keydown", onKey, true);
  input.addEventListener("blur", onBlur);
  window.addEventListener("resize", onWindow);
  window.addEventListener("scroll", onWindow, true);
  tagSuggest = { input, box, list, counts, rows: [], active: -1, moved: false, onInput, onKey, onBlur, onWindow };
  fillTagSuggest();
}

//: **Take, discard or restore a suggested tag** (INBOX 440), moved here from
//: note-cards.js for the boot gzip ratchet (`answerTags` fetches this file).
//: The list redraws from the server's answer, so the card and every other
//: view agree. A tag turned down says so with an Undo (the owner, 2026-10-10:
//: "if I click the not about [this tag], don't show this again, is there a
//: way to undo it or see the list"); the list is the note's edit form's
//: "Not suggested" line (note-edit-panels.js).
async function answerSuggestedTags(entry, body) {
  try {
    const wasTags = [...(entry.tags || [])];
    await apiJson(`/entries/${entry.id}/suggested-tags`, { method: "POST", body: JSON.stringify(body) });
    await refreshEntries([entry.id]);
    const tag = (body.take || body.discard || body.restore || [])[0];
    //: Each answer is a step on the stack (INBOX 898); its undo and redo post
    //: the opposite answer directly, so they do not push steps of their own.
    const post = (answer) => () => apiJson(`/entries/${entry.id}/suggested-tags`, { method: "POST", body: JSON.stringify(answer) }).then(() => refreshEntries([entry.id]));
    if (body.mute === true) {
      offerUndo("Turned off tag suggestions for a note", "Won't suggest tags for this note.", post({ mute: false }), post(body), { record: false });
    } else if (body.mute === false) {
      toast("Tags can be suggested for this note again.");
    } else if (body.take) {
      pushEntryPutUndo(entry.id, `Tagged a note #${tag}`, { tags: wasTags }, { tags: [...new Set([...wasTags, ...body.take])] });
      toast(`Tagged #${tag}.`);
    } else if (body.restore) {
      pushUndo(`Allowed #${tag} to be suggested again`, post({ discard: body.restore }), post(body));
      toast(`#${tag} can be suggested for this note again.`);
    } else {
      offerUndo(`Turned down #${tag}`, `Won't suggest #${tag} for this note again.`, post({ restore: [tag] }), post(body), { record: false });
    }
  } catch (error) {
    toast(error.message || "Couldn't change the tags.", true);
  }
}

//: **The "+ Tag" chip's popover** (brief 89, the owner: "should add tags show
//: for notes with 0-2/3 tags on them?? with suggested tags as well?? and also
//: an option for dont suggest tags for this note"). Up to three suggested tags
//: as one-click chips above the field (the ones kept on the note first, then
//: the notebook's own ranking from `/entries/suggest-tags`), the field, and a
//: menu that turns suggestions off for this note and back on. A private note
//: gets no live suggestions: they would be derived from its text.
let noteTagPop = null;

function closeNoteTagPopover({ restoreFocus = false } = {}) {
  if (!noteTagPop) return;
  const { panel, anchor, outside, entryId } = noteTagPop;
  document.removeEventListener("pointerdown", outside, true);
  closeHelpPopovers();
  closeActionMenus();
  panel.remove();
  anchor.setAttribute("aria-expanded", "false");
  noteTagPop = null;
  if (restoreFocus) noteTagFocusTarget(anchor, entryId)?.focus({ preventScroll: true });
}

//: Where focus goes when the popover closes. A list re-render under an open
//: popover replaces the "+ Tag" chip it was opened from, and focus then fell to
//: the body: the chip the new card drew, else that card's tag area, else the
//: list's heading.
function noteTagFocusTarget(anchor, entryId) {
  if (anchor.isConnected) return anchor;
  const card = document.querySelector(`li[data-id="${CSS.escape(String(entryId))}"]`);
  const chip = card?.querySelector(".note-meta > .tag-add");
  if (chip) return chip;
  const target = card?.querySelector(".note-meta") || document.getElementById("entries-heading");
  if (target) target.tabIndex = -1;
  return target;
}

async function noteTagChoices(entry, { fetchMore = true } = {}) {
  if (entry.tag_suggest_off) return [];
  const have = new Set((entry.tags || []).map((t) => t.toLowerCase()));
  const gone = new Set((entry.discarded_tags || []).map((t) => t.toLowerCase()));
  const picked = [];
  const add = (tag) => {
    const key = String(tag).toLowerCase();
    if (picked.length < 3 && !have.has(key) && !gone.has(key) && !picked.some((t) => t.toLowerCase() === key)) picked.push(tag);
  };
  (entry.suggested_tags || []).forEach(add);
  if (fetchMore && picked.length < 3 && !entry.is_private && entry.content) {
    const more = await apiJson("/entries/suggest-tags", {
      method: "POST", silent: true, body: JSON.stringify({ content: entry.content.slice(0, 4000), tags: entry.tags || [] }),
    }).catch((e) => console.warn("Tag suggestions were not fetched:", e.message) || null);
    for (const tag of more?.suggested_tags || []) add(tag);
    for (const [tag, why] of Object.entries(more?.suggested_tag_reasons || {})) entry.suggested_tag_reasons = { ...entry.suggested_tag_reasons, [tag]: why };
  }
  return picked;
}

async function openNoteTagPopover(entry, anchor) {
  if (noteTagPop?.anchor === anchor) {
    closeNoteTagPopover({ restoreFocus: true });
    return;
  }
  closeNoteTagPopover();
  //: Open at once on the suggestions already held, then top them up from the
  //: server (owner, 2026-10-12: "slow to open", "I cant click off"). Waiting
  //: for the fetch first also let a second press open a second panel that
  //: nothing tracked, so no outside click could close it.
  const choices = await noteTagChoices(entry, { fetchMore: false });
  if (!anchor.isConnected || noteTagPop) return;
  const panel = document.createElement("div");
  panel.className = "help-popover note-tag-pop";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Add tags to this note");
  const head = document.createElement("div");
  head.className = "note-tag-pop-head";
  const title = document.createElement("strong");
  title.textContent = "Add tags";
  const help = document.createElement("button");
  help.type = "button";
  help.className = "icon-only ghost small";
  help.setAttribute("data-help-for", "note-tag-pop-help");
  help.setAttribute("aria-controls", "note-tag-pop-help");
  help.setAttribute("aria-expanded", "false");
  help.setAttribute("aria-label", "About adding tags");
  help.title = "About adding tags";
  help.append(Object.assign(document.createElement("i"), { className: "ph ph-question" }));
  help.firstChild.setAttribute("aria-hidden", "true");
  const helpBody = document.createElement("div");
  helpBody.className = "help-body hidden";
  helpBody.id = "note-tag-pop-help";
  helpBody.setAttribute("role", "dialog");
  helpBody.setAttribute("aria-label", "About adding tags");
  helpBody.textContent = "A note with fewer than three tags shows + Tag. The suggested tags come from the words in the note and from your own tags; one press adds one. Don't suggest tags for this note stops the suggestions on this card only, and the same menu turns them back on.";
  const off = Boolean(entry.tag_suggest_off);
  const menu = kebabMenu(
    [off
      ? { label: "ph:arrow-counter-clockwise Suggest tags for this note again", title: "Show suggested tags on this note again", run: () => { closeNoteTagPopover(); answerSuggestedTags(entry, { mute: false }); } }
      : { label: "ph:bell-slash Don't suggest tags for this note", title: "Stop suggesting tags on this note; you can turn them back on from this menu", run: () => { closeNoteTagPopover(); answerSuggestedTags(entry, { mute: true }); } }],
    "Tag suggestions for this note"
  );
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "icon-only ghost small";
  closeBtn.title = "Close (Esc)";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.append(Object.assign(document.createElement("i"), { className: "ph ph-x" }));
  closeBtn.firstChild.setAttribute("aria-hidden", "true");
  closeBtn.addEventListener("click", () => closeNoteTagPopover({ restoreFocus: true }));
  head.append(title, help, menu, closeBtn);
  panel.append(head, helpBody);
  const suggestions = document.createElement("div");
  suggestions.className = "note-tag-pop-suggested";
  suggestions.setAttribute("role", "group");
  suggestions.setAttribute("aria-label", "Suggested tags");
  if (off) {
    suggestions.append(Object.assign(document.createElement("p"), { className: "muted note-tag-pop-line", textContent: "Suggestions are off for this note." }));
  } else if (choices.length) {
    for (const tag of choices) {
      const reason = entry.suggested_tag_reasons?.[tag];
      const pick = chip(`ph:plus ${tag}`, "tag suggested-tag", () => {
        closeNoteTagPopover();
        answerSuggestedTags(entry, { take: [tag] });
      });
      pick.title = reason ? `Add #${tag}. ${reason}` : `Add #${tag}`;
      suggestions.append(pick);
    }
  } else {
    suggestions.append(Object.assign(document.createElement("p"), { className: "muted note-tag-pop-line", textContent: "No suggestions for this note yet." }));
  }
  const input = document.createElement("input");
  input.type = "text";
  input.className = "note-tag-pop-input";
  input.placeholder = "Type a tag and press Enter";
  input.setAttribute("aria-label", "New tag");
  input.autocomplete = "off";
  input.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      closeNoteTagPopover({ restoreFocus: true });
    } else if (event.key === "Enter") {
      event.preventDefault();
      const typed = input.value.split(",").map((t) => t.replace(/^#/, "").trim()).filter(Boolean);
      if (!typed.length) return;
      closeNoteTagPopover();
      answerSuggestedTags(entry, { take: typed });
    }
  });
  panel.append(suggestions, input);
  const outside = (event) => {
    const t = event.target;
    if (panel.contains(t) || anchor.contains(t) || t.closest?.(".help-popover, .action-menu, .sheet-overlay")) return;
    closeNoteTagPopover();
  };
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !event.defaultPrevented) {
      event.stopPropagation();
      closeNoteTagPopover({ restoreFocus: true });
    }
  });
  document.addEventListener("pointerdown", outside, true);
  document.body.appendChild(panel);
  noteTagPop = { panel, anchor, outside, entryId: entry.id };
  anchor.setAttribute("aria-expanded", "true");
  wireHelpPopover(help, helpBody);
  placeHelpPopover(panel, anchor);
  input.focus({ preventScroll: true });
  if (!off && choices.length < 3 && !entry.is_private && entry.content) {
    const mine = noteTagPop;
    noteTagChoices(entry).then((more) => {
      if (noteTagPop !== mine || more.length <= choices.length) return;
      suggestions.replaceChildren();
      for (const tag of more) {
        const reason = entry.suggested_tag_reasons?.[tag];
        const pick = chip(`ph:plus ${tag}`, "tag suggested-tag", () => {
          closeNoteTagPopover();
          answerSuggestedTags(entry, { take: [tag] });
        });
        pick.title = reason ? `Add #${tag}. ${reason}` : `Add #${tag}`;
        suggestions.append(pick);
      }
      placeHelpPopover(panel, anchor);
    }).catch(() => {});
  }
}
//: Tag a note: one PUT, one toast, one undo. True when it took.
async function addTagTo(entry, tag) {
  if (!tag || entry.tags.includes(tag)) return false;
  try {
    await api(`/entries/${entry.id}`, { method: "PUT", body: JSON.stringify({ tags: [...entry.tags, tag] }) });
    pushEntryPutUndo(entry.id, `Tagged a note “${tag}”`, { tags: [...entry.tags] }, { tags: [...entry.tags, tag] });
    toast(`Tagged “${tag}”.`);
    loadEntries();
    return true;
  } catch (error) {
    toast(error.message, true);
    return false;
  }
}

function renderReevaluateResult(entry, wrap) {
  const data = inlineAction.data;
  const confidence = data.entry ? data.entry.ai_confidence : entry.ai_confidence;

  const head = document.createElement("p");
  head.className = "muted";
  head.textContent = data.recategorised_to
    ? `Read: confidence ${confidence}%, moved to “${data.recategorised_to}”.`
    : `Read: confidence now ${confidence}%.`;
  wrap.appendChild(head);

  // Drop suggestions the user already applied (the card re-renders after each).
  const haveTags = new Set(entry.tags);
  const linkedIds = new Set((entry.links || []).map((l) => l.entry_id));
  const tags = (data.suggested_tags || []).filter((t) => !haveTags.has(t));
  const links = (data.suggested_links || []).filter((l) => !linkedIds.has(l.id));

  if (tags.length) {
    const tagRow = document.createElement("div");
    tagRow.className = "recent";
    const label = document.createElement("span");
    label.className = "muted";
    label.textContent = "Add tags:";
    tagRow.appendChild(label);
    for (const tag of tags) {
      const tagChip = chip(`ph:plus ${tag}`, "tag", async () => {
        if (await addTagTo(entry, tag)) tagChip.remove();
      });
      tagChip.title = data.suggested_tag_reasons?.[tag] || `Add the “${tag}” tag`;
      tagRow.appendChild(tagChip);
    }
    wrap.appendChild(tagRow);
  }

  if (links.length) {
    const label = document.createElement("p");
    label.className = "muted";
    label.textContent = "Link to related notes:";
    wrap.appendChild(label);
    for (const link of links) {
      const row = document.createElement("div");
      row.className = "row space-between reevaluate-link";
      const preview = document.createElement("span");
      renderInlineMarkdown(preview, link.preview, [], true);
      row.appendChild(preview);
      row.appendChild(
        smallButton("ph:link Link", "Link these two notes", async () => {
          try {
            const updated = await apiJson(`/entries/${entry.id}/links`, {
              method: "POST",
              body: JSON.stringify({ target_id: link.id }),
            });
            row.remove();
            toast("Notes linked.");
            refreshEntries([entry.id, link.id]);
            let liveLinkId = updated.links.find((l) => l.entry_id === link.id)?.link_id;
            pushUndo(
              "Linked two notes",
              async () => {
                if (liveLinkId == null) return;
                await api(`/entries/${entry.id}/links/${liveLinkId}`, { method: "DELETE" });
                await refreshEntries([entry.id, link.id]);
              },
              async () => {
                const redone = await apiJson(`/entries/${entry.id}/links`, {
                  method: "POST",
                  body: JSON.stringify({ target_id: link.id }),
                });
                liveLinkId = redone.links.find((l) => l.entry_id === link.id)?.link_id ?? liveLinkId;
                await refreshEntries([entry.id, link.id]);
              }
            );
          } catch (error) {
            toast(error.message, true);
          }
        })
      );
      wrap.appendChild(row);
    }
  }

  //: Where else the note could live, with the reason on hover (owner,
  //: 2026-10-17: Tag with Atlas offered only links). One tap moves it, the
  //: same call and undo as the batch bar's Move to.
  const categories = (data.suggested_categories || []).filter((c) => c.name !== entry.category);
  if (categories.length) {
    const catRow = document.createElement("div");
    catRow.className = "recent";
    const catLabel = document.createElement("span");
    catLabel.className = "muted";
    catLabel.textContent = "Could also go in:";
    catRow.appendChild(catLabel);
    for (const option of categories) {
      const catChip = chip(`ph:folder-simple ${option.name}`, "tag", async () => {
        await moveNotesToCategory([entry.id], option.name);
        inlineAction = null;
        renderEntries();
      });
      catChip.title = option.why || `Move this note to “${option.name}”`;
      catRow.appendChild(catChip);
    }
    wrap.appendChild(catRow);
  }

  if (!tags.length && !links.length && !categories.length) {
    const none = document.createElement("p");
    none.className = "muted";
    none.textContent = "No new tags, links or categories to suggest right now.";
    wrap.appendChild(none);
  } else if (!tags.length) {
    const noTags = document.createElement("p");
    noTags.className = "muted";
    noTags.textContent = "No tags to suggest for this one.";
    wrap.appendChild(noTags);
  }

  //: A field of one's own, always: the suggestions can come back empty and
  //: the person still wants to tag the note from here.
  const own = document.createElement("form");
  own.className = "row";
  const ownInput = document.createElement("input");
  ownInput.placeholder = "Add a tag of your own";
  ownInput.setAttribute("aria-label", "Add a tag of your own");
  own.append(ownInput, smallButton("Add", "Add this tag to the note", () => {}));
  own.lastChild.type = "submit";
  own.addEventListener("submit", (event) => {
    event.preventDefault();
    addTagTo(entry, ownInput.value.trim().replace(/^#/, ""));
  });
  wrap.appendChild(own);

  wrap.appendChild(
    smallButton("Done", "Close", () => {
      inlineAction = null;
      renderEntries();
    })
  );
}

