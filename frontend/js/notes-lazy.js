// notes-lazy.js: Notes list pieces moved out of notes-list.js (audit 1029
// N9) to pay for the windowed list in the gzip budget
// (tests/test_static_compression.py). A row's expand chevron (reached only by
// a click) and the bell's weekly untagged and review nudges (after the
// notebook loads). No caller reads a return value, so stand-ins
// (`notesLazy`, lazy-entries.js) fetch this file on first use. The empty-filter hint and the
// engine query's bar moved here (audit 1031, gzip budget): both draw after a render.

//: **The whole note behind a list row** (INBOX 1525, audit 1031 BK10). The list holds each note's first 300 characters
//: (`content_truncated`), so an open, an edit or a save reads the text here first. Callers use the object this returns,
//: never the row they held: a list refresh can replace that row with a clipped one while this is asked. The row in
//: `allEntries` at the answer is filled in place, so every holder of it sees the text. A whole row is returned as it is.
//: Asks in one tick go as one request (a board's clipped cards); `GET /entries/{id}` reaches what `?ids=` leaves out
//: (archived notes, which document backlinks list). Rejects when the note is gone or unreachable.
function fullEntry(id) {
  const row = allEntries.find((e) => e.id === id);
  if (row && !row.content_truncated) return Promise.resolve(row);
  const asks = (fullEntry.asks ||= new Map());
  if (!asks.has(id)) {
    if (!asks.size) queueMicrotask(fullEntry.send);
    const ask = {};
    ask.promise = new Promise((resolve, reject) => Object.assign(ask, { resolve, reject }));
    asks.set(id, ask);
  }
  return asks.get(id).promise;
}

fullEntry.send = async () => {
  const asks = fullEntry.asks;
  fullEntry.asks = new Map();
  const ids = [...asks.keys()];
  const got = new Map();
  for (let at = 0; ids.length > 1 && at < ids.length; at += 200) {
    //: A failed batch is not an empty answer: each id is then read on its own below, and one that fails rejects.
    try {
      for (const whole of await apiJson(`/entries?ids=${ids.slice(at, at + 200)}&boards=include`)) got.set(whole.id, whole);
    } catch {}
  }
  await Promise.all(ids.map(async (id) => {
    try {
      const whole = got.get(id) || (await apiJson(`/entries/${id}`));
      const now = allEntries.find((e) => e.id === id);
      asks.get(id).resolve(now ? Object.assign(now, whole) : whole);
    } catch (error) {
      asks.get(id).reject(error?.message ? error : new Error("This note is no longer here."));
    }
  }));
};

function toggleRowExpanded(id) {
  const open = !expandedRows.has(id);
  if (open) {
    expandedRows.add(id);
    notesRailId = id;
  } else {
    expandedRows.delete(id);
    //: Closing the note the rail is about closes the rail's subject with it:
    //: a column describing a note nobody has open is the chrome-with-nothing
    //: the local map already learned not to be.
    if (notesRailId === id) notesRailId = null;
  }
  const li = document.querySelector(`#entry-list > li[data-id="${id}"]`);
  if (!li) return renderEntries();
  //: **In place, and animated** (INBOX 676, the owner: "the dropdown and
  //: collapse should be a smooth animation adn not sudden and janky"). This
  //: was a full list redraw: a new row in one frame (49.6 to 237.8px) and a
  //: new chevron, so its glyph could not turn. The row is the same DOM open
  //: or closed (CSS hides what a closed row does not show), so the class
  //: alone is the change. The height runs from where the row *is*, read
  //: before the previous animation is cancelled, so a second press mid-way
  //: turns back from there instead of snapping; what the change reveals
  //: fades in over the same time. `--ui-slow` is the Interface animations
  //: switch's token: 0s with it off, and then nothing animates.
  const from = li.getBoundingClientRect().height;
  const parts = [...li.querySelectorAll(":scope > :not(.row-expand, .entry-title)")];
  const seen = parts.map((el) => (el.getAnimations().length ? +getComputedStyle(el).opacity : 0));
  for (const el of [li, ...parts]) for (const a of el.getAnimations()) if (a.id === "row") a.cancel();
  li.classList.toggle("row-expanded", open);
  //: An opened-out row shows the whole note: its card fills itself in place (`fillWhole`, entry-card.js), so its
  //: Show more stays bound to the text it shows and a list redraw does not cut the opening short (INBOX 1525 review).
  if (open) li.querySelector(".entry-content")?.fillWhole?.();
  const button = li.querySelector(":scope > .row-expand");
  if (button) {
    button.title = open ? "Show less of this note" : "Show the whole note here";
    button.setAttribute("aria-label", button.title);
    button.setAttribute("aria-expanded", String(open));
  }
  const to = li.getBoundingClientRect().height;
  const style = getComputedStyle(li);
  const duration = parseFloat(style.getPropertyValue("--ui-slow")) * 1000 || 0;
  const easing = style.getPropertyValue("--ease-in-out").trim() || "ease-in-out";
  if (duration && Math.abs(to - from) > 1) {
    li.animate({ height: [`${from}px`, `${to}px`], overflow: ["hidden", "hidden"] }, { id: "row", duration, easing });
    parts.forEach((el, i) => el.animate({ opacity: [seen[i], 1] }, { id: "row", duration, easing }));
  }
  scheduleNotesRail();
  updateExpandAllButton();
}

//: Only with a model running (`modelStatus` is the status poll's, status.js).
function reviewNudgeWanted() {
  return typeof modelStatus !== "undefined" && modelStatus?.model_ready === true;
}

//: The bell says so once a week, past a handful, as it does for untagged.
async function nudgeReviewQueue() {
  //: "Atlas was unsure" is about a model's choices: with none running, the
  //: queue is only notes nobody has filed yet, and the line would be untrue
  //: (blind test 2026-10-31).
  if (!reviewNudgeWanted()) return;
  const queue = await apiJson("/review-queue?limit=1", { silent: true, cacheMs: 60000 }).catch(() => null);
  if (!queue || queue.count < UNTAGGED_NUDGE_MIN) return;
  const now = new Date();
  const week = Math.floor((now - new Date(now.getFullYear(), 0, 1)) / (7 * 86400000));
  recordNotification({
    kind: "assist",
    title: `${queue.count} filings to check`,
    detail: "Atlas was unsure where these belong. Accept each, or move it.",
    key: `review:${now.getFullYear()}-${week}`,
    action: { tab: "notes", filter: "is:review" },
  });
}

//: **The app notices what the person has not got round to** (INBOX 162).
//: Once the notebook is loaded, a bell entry counts the real notes with no
//: tag and offers the filtered list. Keyed by the ISO week, so it is said
//: once a week at most however often the list reloads, and only past a
//: handful: three untagged notes is a Tuesday, not a backlog.
const UNTAGGED_NUDGE_MIN = 5;

function nudgeUntaggedNotes() {
  const untagged = allEntries.filter((e) => !e.is_board && !e.is_draft && !e.map_topic && !(e.tags || []).length);
  if (untagged.length < UNTAGGED_NUDGE_MIN) return;
  const now = new Date();
  const week = Math.floor((now - new Date(now.getFullYear(), 0, 1)) / (7 * 86400000));
  recordNotification({
    kind: "assist",
    title: `${untagged.length} notes have no tags`,
    detail: "Tags are how notes find each other. Open the list and add a few.",
    key: `untagged:${now.getFullYear()}-${week}`,
    action: { tab: "notes", filter: "is:untagged" },
  });
}

//: (Moved here from notes-list.js to pay for the paint gate in the gzip budget.)
// One call per settled query, not per keystroke: the caller debounces, and a
// reply that arrives after the box has moved on is dropped rather than
// painting reasons for a query nobody is looking at any more.
async function refreshNoteSearchWhy() {
  const asked = noteSearch;
  if (!asked) {
    noteSearchWhy.clear();
    return;
  }
  // What the person is looking at, when that is unambiguous: one note opened
  // out in the list is the app's own "open note", and it is what makes the
  // third signal (distance over the links) mean anything. Two open rows, or
  // none, is not a context, and passing a guess would put "linked to the open
  // note" on a note linked to something nobody is reading. On card view the
  // last card clicked or focused counts (L709, the owner 2026-11-12).
  const open =
    editingId || (expandedRows.size === 1 ? [...expandedRows][0] : null) || Number($("entry-list")?.dataset.lastCard) || null;
  let body;
  try {
    // 50 is the endpoint's own ceiling (`routes_search.MAX_LIMIT`): a search
    // box shows a page, not a notebook, and a note past the fiftieth best
    // match simply carries no reason chip rather than a wrong one.
    body = await apiJson(
      `/search?q=${encodeURIComponent(clipFor("search", asked))}&kind=note,board,map&limit=50` +
        (open ? `&entry_id=${open}` : "")
    );
  } catch {
    // The list is already rendered and already correct; the reasons are the
    // only thing missing, so a failed call leaves the notes alone.
    return;
  }
  //: A draw that is still waiting for the card file would paint without the reasons.
  await renderEntries.waiting;
  if (noteSearch !== asked) return;
  noteSearchWhy.clear();
  for (const hit of body?.hits || []) noteSearchWhy.set(hit.id, hit);
  noteSearchCorrection = body?.corrected
    ? { asked, corrected: body.corrected, ids: new Set((body.hits || []).map((hit) => hit.id)) }
    : null;
  //: **In place when the reasons change nothing but themselves** (perf-1031
  //: item 5). The list was rebuilt a second time per settled query only to
  //: draw the reason lines (180 ms each at 4x, 2,000 notes). A correction
  //: ("showing results for") lists other notes when nothing matched, or stops
  //: doing so; only then does the list redraw.
  const noRows = !$("entry-list").querySelector(":scope > li[data-id]");
  if (noteSearchCorrectionShown || (noteSearchCorrection && noRows)) renderEntries();
  else paintSearchWhy();
}

function paintSearchWhy() {
  const byId = new Map(allEntries.map((entry) => [entry.id, entry]));
  for (const li of $("entry-list").querySelectorAll(":scope > li[data-id]:not(.row-shell)")) {
    li.querySelector(":scope > .entry-why")?.remove();
    const badge = whyThisResultChip(byId.get(Number(li.dataset.id)) || {});
    if (!badge) continue;
    const line = document.createElement("div");
    line.className = "entry-why";
    line.append(badge);
    li.querySelector(":scope > .entry-meta")?.after(line);
  }
}

function noMatchHint(box) {
  const line = box.querySelector(".muted");
  const bad = noteSearch && parseNoteQuery(noteSearch).flags.find((flag) => !NOTE_FLAGS.includes(flag));
  line.dataset.was ??= line.textContent;
  line.textContent = bad ? `No filter named is:${bad}. Try is:favourite, is:private, is:linked, is:draft, is:untagged, is:untitled or is:review.` : line.dataset.was;
}

//: KG7: a structural query's bar over the list: how many, and the same notes
//: as a table and on the graph.
function liveQueryBar(visible) {
  const list = $("entry-list");
  let bar = list.parentElement?.querySelector(":scope > .note-query-bar");
  const parsed = noteSearch ? parseNoteQuery(noteSearch) : null;
  const live = Boolean(parsed) && (parsed.structural.length > 0 || parsed.engine.length > 0);
  if (!live) {
    bar?.remove();
    return;
  }
  if (!bar) {
    bar = document.createElement("div");
    bar.className = "row note-query-bar";
    list.before(bar);
  }
  const ids = visible.map((e) => e.id);
  const count = document.createElement("span");
  count.className = "muted";
  //: Up to ten pages of 50 are read; past that it says so rather than
  //: letting the count pass for the whole of a larger answer.
  count.textContent = parsed.engine.length > 0 && noteEngine.capped
    ? `The first ${ids.length} notes that match this query, add words to narrow it`
    : `${nounCount(ids.length, "note")} match this query`;
  bar.replaceChildren(
    count,
    smallButton("ph:table Table", "These notes as a table, their properties as columns", () => openQueryTable(ids)),
    smallButton("ph:graph Show on graph", "Light these notes on the graph", () => showQueryOnGraph(ids)),
  );
}

//: The Semantic toggle's list (moved out of `_loadEntries` for the gzip budget; INBOX 1525): `asked` is the box text.
async function loadSemanticEntries(asked, generation) {
  //: **The Semantic toggle asks the engine** (`GET /search`), the one place
  //: words, meaning and the links are ranked together, rather than a second
  //: cosine-only list path (retired). The engine's page
  //: is at most 50 hits, so nothing here needs paging; the list is then read
  //: by id, which is also what keeps the bin, the archive and the boards out
  //: of it (the index holds them, flagged), and put in the engine's order.
  const found = await apiJson(`/search?q=${encodeURIComponent(clipFor("search", asked))}&kind=note&limit=50`);
  const order = (found.hits || []).map((hit) => hit.id);
  const rows = order.length ? await apiJson(`/entries?ids=${order.join(",")}&preview=300`) : [];
  if (generation !== _entriesLoadGeneration) return; // a newer load took over
  const byId = new Map(rows.map((row) => [row.id, row]));
  const results = order.filter((id) => byId.has(id)).map((id) => byId.get(id));
  noteEngine.semanticFor = asked;
  noteEngine.rank = new Map(results.map((row, place) => [row.id, place]));
  allEntries = results;
  entriesEverLoaded = true;
  publishNotes(allEntries);
  renderStatusBar();
  renderSidebar();
  loadCategories();
  renderEntries();
  ensureMapChipsFor(results, generation);
  fillCategoryOptions($("entry-category"), null);
}

//: Moved from chat-agent.js (gzip budget): its one caller is the button wired just below.
function undoDraft() {
  const previous = draftUndoStack.pop();
  if (!previous) return;
  //: The same entry the status bar holds, run from the pane's own button, so
  //: its redo knows what the pass had written.
  if (previous.action) {
    settleUndoFromToast(previous.action);
    previous.action.undo();
  } else putDraftBack(previous);
  $("draft-status").classList.remove("error");
  $("draft-status").textContent = "Went back to the previous version.";
  announce("Restored the draft from before the last AI pass.");
}

//: The writing room's buttons (moved from wiring.js, gzip budget): wired when the Notes pane is built, which loads this file.
onSurface("notes", () => {
  $("draft-compose").addEventListener("click", composeDraft);
  $("draft-undo").addEventListener("click", undoDraft);
  $("draft-cancel").addEventListener("click", () => draftController?.abort());
  $("draft-save").addEventListener("click", () => saveDraftAsNote());

  $("draft-title").addEventListener("click", suggestDraftTitle);
  // Refine is Draft with an instruction in hand: the same pass, so it runs the
  // same function rather than a second copy of it that could drift.
  $("draft-refine").addEventListener("click", () => {
    if (!$("draft-instruction").value.trim()) {
      setDraftStatus("Say what to change, then refine.", true);
      $("draft-instruction").focus();
      return;
    }
    composeDraft();
  });
  $("draft-instruction").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    $("draft-refine").click();
  });
  $("draft-copy").addEventListener("click", async (event) => {
    const text = $("draft-text").value.trim();
    if (!text) {
      setDraftStatus("There's no draft to copy yet.", true);
      return;
    }
    if (await copyToClipboard(text, event.currentTarget)) setDraftStatus("Draft copied.");
  });
  // `appendSelectionToNote` is the app's one "add this text to a note you
  // already have" path (the text-selection popup uses it): the same picker, the
  // same undo entry, the same flash on the note it landed in.
  $("draft-insert").addEventListener("click", () => {
    const text = $("draft-text").value.trim();
    if (!text) {
      setDraftStatus("There's no draft to insert yet.", true);
      return;
    }
    // The toast says it landed and offers the trip to it; the status line is
    // not written here because this returns before the picker has been
    // answered, and a line saying it was added is a lie until it was.
    appendSelectionToNote(text, { jump: false });
  });
  $("draft-add-source").addEventListener("click", async () => {
    if (draftSources.length >= DRAFT_MAX_SOURCES) {
      setDraftStatus(`Six notes is the most one draft can be written from.`, true);
      return;
    }
    const entry = await pickEntryDialog("Which note should Atlas write from?");
    if (!entry) return;
    addDraftSource(entry);
  });
  $("draft-continue-note").addEventListener("click", async () => {
    const entry = await pickEntryDialog("Which note should Atlas carry on?");
    if (!entry) return;
    if ($("draft-text").value.trim()) pushDraftUndo();
    $("draft-text").value = entry.content || "";
    draftNoteId = entry.id;
    draftNoteLabel = clipText(entry.title || notePreviewText(entry.content) || "a note", 40);
    $("draft-kind").value = "continue";
    window.markDraftQuickstart?.("continue");
    renderDraftTarget();
    // The note as it stands is version one, so the way back to what it said
    // before Atlas touched it is the same chip row as every other pass.
    rememberDraftVersion($("draft-text").value);
    updateDraftCount();
    saveDraftLocally();
    setDraftStatus("That note is in the draft. Add a thought, then draft to carry it on.");
    $("draft-thoughts").focus();
  });
});
