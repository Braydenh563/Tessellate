// suggestions-inbox.js: the suggestions inbox (GRAPH_PLAN KG9, INBOX 528).
//
// Lazy (app.js, `LAZY_MODULES.inbox`), entered through `openSuggestionsInbox`,
// a `LAZY_ENTRY_POINTS` stand-in. One sheet for the four things the notebook
// proposes and only a person decides: links to add (`/entries/link-suggestions`),
// disagreements (`/entries/tensions`, a local-model pass started by hand),
// names that are one thing and link types (`/suggestions`). A select picks the
// kind, each row with its count. Every accept and dismissal is a correction the
// next pass reads (`ai/learning.py`): a dismissal never comes back, and both
// move what each kind of evidence is worth. Before this the links were a
// panel under the graph's toolbar and the disagreements a dialog of their own.

const INBOX_KINDS = [
  ["links", "Links", "Notes that look related. Link the ones you agree with."],
  ["tensions", "Tensions", "Notes that may contradict each other, read in pairs by your local model."],
  ["names", "Names", "One person or thing named two ways. Merge them and every mention follows."],
  ["types", "Link types", "Links whose own words say what kind of link they are."],
];

const INBOX_HELP = [
  "The list at the top picks the kind of suggestion; each row says how many are waiting, as in Links (3).",
  "Links: pairs worth connecting, with every reason: similar wording, people or things both name, a note both link with, a rare tag both carry. Add a reason before Link, or leave it to Atlas; Link all above 70% links every pair at least that sure, and the ⋯ beside it has Suggest reasons and Explain your existing links.",
  "Tensions: Start the review reads likely pairs with your local model and shows the two sides with their dates. Nothing runs until you start it.",
  "Names: \"Sam\" and \"Sam Lee\", or one name spelled two ways. Merge keeps the fuller name and moves every mention; the other name is kept as an alias, so it is never found twice.",
  "Link types: a link whose sentence says \"for example\", \"continues\", \"evidence\", \"contradicts\" or \"background\". Accepting gives the link that type; the graph draws it.",
  "Every Link, Merge or type you accept, and every one you dismiss, teaches the inbox which reasons to trust in your notebook. A dismissed suggestion does not come back.",
];

let inboxState = null;

//: "Link all above 70%": the confidence over every reason (`confidence`, or the
//: similarity where a pair has no other signal) at which one click links the lot.
const LINK_ALL_AT = 0.7;

async function openSuggestionsInbox(kind = "links") {
  if (inboxState) {
    inboxShow(kind);
    return;
  }
  const state = { kind, select: null, options: {}, lists: {}, counts: {} };
  inboxState = state;
  state.close = openSheet({
    label: "Suggestions",
    name: "suggestions",
    onClose: () => {
      inboxState = null;
    },
    build: (card) => {
      card.classList.add("inbox-card");
      inboxHead(card);
      //: **A list, not a pill well** (INBOX 670; DESIGN.md `.seg`: two or three
      //: short choices only). Four kinds, each worded and counted, are one
      //: select whose rows carry the counts ("Links (3)"), as Questions' state
      //: does. The panes follow its value, so the list is the one control.
      const kind = document.createElement("select");
      kind.id = "inbox-kind";
      kind.className = "inbox-kind";
      kind.setAttribute("aria-label", "Kind of suggestion");
      kind.title = "Kind of suggestion";
      const body = document.createElement("div");
      body.className = "inbox-body";
      for (const [key, label, line] of INBOX_KINDS) {
        const option = document.createElement("option");
        option.value = key;
        option.dataset.label = label;
        option.textContent = label;
        kind.appendChild(option);
        const pane = document.createElement("div");
        pane.id = `inbox-pane-${key}`;
        pane.className = "inbox-pane";
        pane.setAttribute("role", "group");
        pane.setAttribute("aria-label", label);
        pane.hidden = true;
        const desc = document.createElement("p");
        desc.className = "muted inbox-desc";
        desc.textContent = line;
        const list = document.createElement("div");
        list.className = "inbox-list";
        pane.append(desc, list);
        body.appendChild(pane);
        state.options[key] = option;
        state.lists[key] = list;
      }
      kind.addEventListener("change", () => inboxShow(kind.value));
      state.select = kind;
      card.append(kind, body);
    },
  });
  inboxShow(kind);
  inboxTensionsPane();
  for (const key of ["links", "names", "types"]) setLabel(state.lists[key], "ph:spin Looking…");
  await inboxLoad(state);
}

//: The lists, read again: the first open, and an Undo or Redo of a decision.
async function inboxLoad(state) {
  const [links, rest] = await Promise.all([
    apiJson("/entries/link-suggestions", { silent: true }).catch(() => []),
    apiJson("/suggestions", { silent: true }).catch(() => ({ merges: [], types: [] })),
  ]);
  if (inboxState !== state) return;
  inboxLinksPane(links || []);
  inboxRows("names", rest.merges || [], inboxMergeRow, "No names to merge. Two names for one person or thing show up here.");
  inboxRows("types", rest.types || [], inboxTypeRow, "No links to type. A link whose sentence says \"for example\" or \"continues\" shows up here.");
}

/** The head: the title, its '?', then the close, as every dialog head. */
function inboxHead(card) {
  const head = card.querySelector(".sheet-head");
  if (!head) return;
  const help = document.createElement("button");
  help.type = "button";
  help.className = "icon-only ghost small dialog-head-btn";
  help.setAttribute("data-help-for", "inbox-help");
  help.setAttribute("aria-controls", "inbox-help");
  help.setAttribute("aria-expanded", "false");
  help.title = "About suggestions";
  help.setAttribute("aria-label", "About suggestions");
  const icon = document.createElement("i");
  icon.className = "ph ph-question";
  icon.setAttribute("aria-hidden", "true");
  help.appendChild(icon);
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  const closeButton = head.querySelector(".sheet-close");
  if (closeButton) actions.appendChild(closeButton);
  head.querySelector(".sheet-title")?.after(help);
  head.appendChild(actions);
  const helpBody = document.createElement("div");
  helpBody.className = "help-body hidden";
  helpBody.id = "inbox-help";
  helpBody.setAttribute("role", "dialog");
  helpBody.setAttribute("aria-label", "About suggestions");
  for (const line of INBOX_HELP) {
    const p = document.createElement("p");
    p.textContent = line;
    helpBody.appendChild(p);
  }
  head.after(helpBody);
}

function inboxShow(kind) {
  const state = inboxState;
  if (!state || !state.options[kind]) return;
  state.kind = kind;
  if (state.select && state.select.value !== kind) state.select.value = kind;
  for (const key of Object.keys(state.options)) {
    document.getElementById(`inbox-pane-${key}`).hidden = key !== kind;
  }
}

//: The count rides on the kind's row in the list, "Links (3)", and a kind
//: with none reads as its word alone.
function inboxCount(kind, n) {
  const state = inboxState;
  if (!state) return;
  state.counts[kind] = n;
  const option = state.options[kind];
  if (!option) return;
  const text = n ? `${option.dataset.label} (${n})` : option.dataset.label;
  if (option.textContent !== text) option.textContent = text;
  //: The opener shows the chosen row's words; a select assigned its own
  //: value re-reads them, one whose row text changed does not.
  if (state.select && state.select.value === kind) state.select.value = kind;
}

/** One kind's rows, or its empty line; a row removing itself recounts. */
function inboxRows(kind, rows, build, empty) {
  const list = inboxState?.lists[kind];
  if (!list) return;
  list.replaceChildren();
  for (const row of rows) list.appendChild(build(row));
  inboxCount(kind, rows.length);
  if (!rows.length) inboxEmpty(list, empty);
  list.dataset.empty = empty;
}

function inboxEmpty(list, text) {
  const line = document.createElement("p");
  line.className = "muted inbox-empty";
  line.textContent = text;
  list.appendChild(line);
}

/** Take a decided row out and recount; the next row takes the focus. */
function inboxDone(kind, row) {
  const list = row.parentElement;
  const next = row.nextElementSibling || row.previousElementSibling;
  row.remove();
  inboxCount(kind, Math.max(0, (inboxState?.counts[kind] || 1) - 1));
  if (list && !list.querySelector(".inbox-row, .link-suggestion")) inboxEmpty(list, list.dataset.empty || "Nothing left.");
  next?.querySelector("button")?.focus();
}

async function inboxCorrection(kind, subject, undoLabel) {
  const body = { kind, subject };
  const made = await apiJson("/learned/corrections", { method: "POST", silent: true, body: JSON.stringify(body) }).catch(() => null);
  //: A verdict that dismisses is a step of its own; one that accompanies a
  //: link or a merge rides on that act's step.
  if (made && undoLabel) pushCorrectionUndo(undoLabel, body, made, () => (inboxState ? inboxLoad(inboxState) : null));
  return made;
}

/** The reasons under a row, each with its own percentage. */
function inboxWhy(signals) {
  const why = document.createElement("p");
  why.className = "muted link-suggestion-why";
  why.textContent = (signals || []).map((g) => `${g.reason} (${Math.round(g.confidence * 100)}%)`).join(" · ");
  return why;
}

//: The score as a small bar with its number (item 92): how sure reads at a
//: glance down a column of rows, where a column of percent chips had to be
//: read one by one.
function inboxScoreBar(confidence) {
  const pct = Math.round((confidence || 0) * 100);
  const score = document.createElement("span");
  score.className = "link-suggestion-score";
  score.title = "How sure, over every reason";
  const bar = document.createElement("span");
  bar.className = "link-suggestion-bar";
  bar.setAttribute("aria-hidden", "true");
  const fill = document.createElement("span");
  fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  bar.appendChild(fill);
  const number = document.createElement("span");
  number.textContent = `${pct}%`;
  score.append(bar, number);
  return score;
}

function inboxScore(confidence) {
  const score = chip(`${Math.round((confidence || 0) * 100)}%`, "confidence");
  score.title = "How sure, over every reason";
  return score;
}

// --- Names: two names for one thing (KG5's merge, decided here) -------------

function inboxMergeRow(m) {
  const row = document.createElement("div");
  row.className = "inbox-row";
  row.setAttribute("role", "group");
  const notes = (n) => `${n} note${n === 1 ? "" : "s"}`;
  const title = document.createElement("p");
  title.className = "inbox-row-title";
  title.textContent = `“${m.merge_name}” (${notes(m.merge_notes)}) into “${m.keep_name}” (${notes(m.keep_notes)})`;
  row.setAttribute("aria-label", `Merge ${m.merge_name} into ${m.keep_name}`);
  const signals = (m.signals || []).map((g) => g.signal);
  const merge = smallButton("ph:arrows-merge Merge", `Fold “${m.merge_name}” into “${m.keep_name}”: every mention moves, and the old name is kept as an alias`, async () => {
    merge.disabled = true;
    const done = await apiJson("/suggestions/merges/accept", {
      method: "POST",
      body: JSON.stringify({ keep_id: m.keep_id, merge_id: m.merge_id, signals }),
    }).catch((e) => {
      toast(e.message, true);
      return null;
    });
    merge.disabled = false;
    if (!done) return;
    //: Undo puts the pair back as two names; the row stays gone, since the
    //: suggestion was answered.
    toastEntityMerge(done, m.merge_id, m.keep_id, null, { kind: "accept_merge", subject: { a: m.keep_id, b: m.merge_id, signals } });
    inboxDone("names", row);
  });
  const dismiss = smallButton("ph:x", "Not the same: never suggest this pair again", () => {
    inboxCorrection("dismiss_merge", { a: m.keep_id, b: m.merge_id, signals }, "Dismissed a name merge");
    inboxDone("names", row);
  });
  const actions = document.createElement("div");
  actions.className = "row inbox-row-actions";
  actions.append(inboxScore(m.confidence), merge, dismiss);
  row.append(title, inboxWhy(m.signals), actions);
  return row;
}

// --- Link types: a link whose own words name its kind -----------------------

function inboxTypeRow(t) {
  const row = document.createElement("div");
  row.className = "inbox-row";
  row.setAttribute("role", "group");
  row.setAttribute("aria-label", `${t.source_label} to ${t.target_label}: ${t.type_label}`);
  const title = document.createElement("p");
  title.className = "inbox-row-title";
  title.textContent = `${t.source_label} → ${t.target_label}`;
  row.appendChild(title);
  if (t.context) row.appendChild(docBacklinkContext(t));
  const set = smallButton(`ph:check ${t.type_label}`, `Give this link the type ${t.type_label}`, async () => {
    set.disabled = true;
    const done = await apiJson("/suggestions/types/accept", {
      method: "POST",
      body: JSON.stringify({ link_id: t.link_id, link_type: t.link_type }),
    }).catch((e) => {
      toast(e.message, true);
      return null;
    });
    set.disabled = false;
    if (!done) return;
    toast(`Link type set: ${t.type_label}.`);
    //: Undo takes the type off and the correction it taught; Redo does both again.
    let learnedId = done.correction_id;
    const redraw = () => Promise.all([refreshEntries([t.source_id, t.target_id]).catch(() => {}), inboxState && inboxLoad(inboxState)]);
    const linkPath = `/entries/${t.source_id}/links/${t.link_id}`;
    const learned = { kind: "accept_link_type", subject: { link_id: t.link_id, link_type: t.link_type, signals: [t.link_type] } };
    pushUndo(
      `Gave a link the type ${t.type_label}`,
      async () => {
        await apiJson(linkPath, { method: "PATCH", body: JSON.stringify({ link_type: null }) });
        if (learnedId != null) await api(`/learned/corrections/${learnedId}`, { method: "DELETE" });
        await redraw();
      },
      async () => {
        await apiJson(linkPath, { method: "PATCH", body: JSON.stringify({ link_type: t.link_type }) });
        learnedId = (await apiJson("/learned/corrections", { method: "POST", body: JSON.stringify(learned) }))?.id ?? learnedId;
        await redraw();
      }
    );
    inboxDone("types", row);
  });
  const dismiss = smallButton("ph:x", "Not this type: never suggest it for this link again", () => {
    inboxCorrection("dismiss_link_type", { link_id: t.link_id, link_type: t.link_type, signals: [t.link_type] }, "Dismissed a link type suggestion");
    inboxDone("types", row);
  });
  const actions = document.createElement("div");
  actions.className = "row inbox-row-actions";
  actions.append(inboxScore(t.confidence), set, dismiss);
  row.append(inboxWhy(t.signals), actions);
  return row;
}

// --- Disagreements: where the notebook disagrees with itself ----------------
//
// Similarity answers "are these about the same thing", and two notes that flatly
// contradict each other are, to a vector, maximally similar; only a model
// reading both can tell agreement from disagreement (`ai/tensions.py`). The
// pass is never started by opening the sheet: it is free but not instant.

const TENSION_STATUS_TEXT = {
  no_model: "No local model is running, so nothing can read your notes. Start Ollama and try again.",
  no_embeddings: "Semantic search is off, so there is no shortlist of notes to compare. Turn it on in Settings, Models.",
  too_few_notes: "Not enough notes yet, there is nothing to compare.",
  no_candidates: "No pairs were close enough in subject to be worth reading. Contradictions only show up between notes about the same thing.",
  none_found: "Nothing contradicted itself, as far as this pass could tell.",
};

function inboxTensionsPane() {
  const list = inboxState?.lists.tensions;
  if (!list) return;
  const tools = document.createElement("div");
  tools.className = "row inbox-tools";
  const status = document.createElement("span");
  status.className = "muted inbox-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const run = document.createElement("button");
  run.type = "button";
  run.className = "accent small";
  run.textContent = "Start the review";
  const results = document.createElement("div");
  results.className = "tensions-results";
  run.addEventListener("click", async () => {
    run.disabled = true;
    results.replaceChildren();
    setLabel(status, "ph:spin Reading your notes… this runs on your machine and can take a minute.");
    const body = await apiJson("/entries/tensions", { silent: true }).catch(() => null);
    run.disabled = false;
    if (!body) {
      status.textContent = "The review could not run. Nothing was changed.";
      return;
    }
    const found = body.tensions || [];
    inboxCount("tensions", found.length);
    if (!found.length) {
      status.textContent = TENSION_STATUS_TEXT[body.status] || "Nothing found.";
      return;
    }
    const checked = body.pairs_checked || 0;
    status.textContent = `${found.length} to look at, from ${checked} pair${checked === 1 ? "" : "s"} read.`;
    for (const tension of found) results.appendChild(tensionCard(tension));
  });
  tools.append(status, run);
  list.replaceChildren(tools, results);
  //: WORLD_CLASS_PLAN B4: what an earlier review or the night shift found and
  //: nobody decided yet is listed at once, from the tensions table; Start the
  //: review only asks the model about pairs not read before.
  apiJson("/entries/tensions/known?limit=20", { silent: true })
    .then((known) => {
      const waiting = (known && known.tensions) || [];
      if (!waiting.length || results.childElementCount) return;
      inboxCount("tensions", waiting.length);
      status.textContent = `${waiting.length} found earlier, still to decide.`;
      for (const tension of waiting) results.appendChild(tensionCard(tension));
    })
    .catch(() => {});
}

/** One proposed disagreement, with both notes and the two decisions. */
function tensionCard(tension) {
  const card = document.createElement("div");
  card.className = "card tension-card";
  card.setAttribute("role", "group");
  card.setAttribute("aria-label", `Possible contradiction: ${tension.explanation}`);
  const why = document.createElement("p");
  why.className = "tension-why";
  why.textContent = tension.explanation;
  const gap = document.createElement("p");
  gap.className = "muted tension-gap";
  //: The gap is the finding as much as the text: "you thought this, then
  //: months later that".
  gap.textContent = tension.gap_days ? `${tensionGapText(tension.gap_days)} apart` : "Written around the same time";
  const pair = document.createElement("div");
  pair.className = "tension-pair";
  pair.append(
    tensionSide("Earlier", tension.earlier_at, tension.earlier_excerpt, tension.earlier_id),
    tensionSide("Later", tension.later_at, tension.later_excerpt, tension.later_id),
  );
  const actions = document.createElement("div");
  actions.className = "row tension-actions";
  const ids = JSON.stringify({ earlier_id: tension.earlier_id, later_id: tension.later_id });
  const accept = document.createElement("button");
  accept.type = "button";
  accept.className = "accent small";
  accept.textContent = "Yes: link these as contradicting";
  accept.addEventListener("click", async () => {
    //: Only a write that happened says so (audit 2026-10-05, FE-12): the
    //: card used to read "Linked as contradicting." when the POST had failed.
    try {
      const done = await apiJson("/entries/tensions/accept", { method: "POST", body: ids });
      pushTensionLinkUndo(tension.earlier_id, tension.later_id, "accept", done?.created !== false);
    } catch (error) {
      toast(error.message || "Couldn't link these notes.", true);
      return;
    }
    tensionResolve(card, "Linked as contradicting.");
  });
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "ghost small";
  dismiss.textContent = "Not a contradiction";
  dismiss.addEventListener("click", async () => {
    try {
      await apiJson("/entries/tensions/dismiss", { method: "POST", body: ids });
      pushTensionLinkUndo(tension.earlier_id, tension.later_id, "dismiss");
    } catch (error) {
      toast(error.message || "Couldn't dismiss this pair.", true);
      return;
    }
    tensionResolve(card, "Dismissed: this pair won't come back.");
  });
  actions.append(accept, dismiss);
  card.append(why, gap, pair, actions);
  return card;
}

/** Replace a card's controls with what happened, announced (the pressed
 *  button is gone, and without `role="status"` a screen reader hears nothing). */
function tensionResolve(card, message) {
  card.classList.add("is-resolved");
  const actions = card.querySelector(".tension-actions");
  if (!actions) return;
  const done = document.createElement("p");
  done.className = "muted tension-done";
  done.setAttribute("role", "status");
  done.textContent = message;
  actions.replaceWith(done);
  inboxCount("tensions", Math.max(0, (inboxState?.counts.tensions || 1) - 1));
}

function tensionGapText(days) {
  if (days < 31) return `${days} day${days === 1 ? "" : "s"}`;
  const months = Math.round(days / 30);
  if (months < 18) return `${months} month${months === 1 ? "" : "s"}`;
  const years = (days / 365).toFixed(1).replace(/\.0$/, "");
  return `${years} year${years === "1" ? "" : "s"}`;
}

function tensionSide(label, when, excerpt, entryId) {
  const side = document.createElement("div");
  side.className = "tension-side";
  const head = document.createElement("p");
  head.className = "tension-side-head";
  const tag = document.createElement("strong");
  tag.textContent = label;
  head.appendChild(tag);
  if (when) {
    const date = document.createElement("span");
    date.className = "muted tension-date";
    date.textContent = when;
    head.appendChild(date);
  }
  const text = document.createElement("p");
  text.className = "tension-excerpt";
  text.textContent = excerpt || "(empty note)";
  const open = document.createElement("button");
  open.type = "button";
  open.className = "ghost small";
  open.textContent = "Open this note";
  open.addEventListener("click", () => {
    inboxState?.close?.();
    flashEntry(entryId);
  });
  side.append(head, text, open);
  return side;
}

// --- Links: the auto-linker, approve each (GRAPH_PLAN KG2) ------------------

function inboxLinksPane(suggestions) {
  const list = inboxState?.lists.links;
  if (!list) return;
  list.replaceChildren();
  list.dataset.empty = "No new links to suggest: everything related is linked already.";
  const rowReasons = [];
  //: Explains links that already exist (similarity, then Atlas names the
  //: connection); not the rows below, which are not links yet.
  //: **One bar, one button** (INBOX 1329, the owner: "the suggestions panel
  //: needs a better redesign and restructuring"): three bordered buttons in a
  //: row read as three equal choices over the list. The pane's one bulk act
  //: (link the sure ones) stays a button; the two that ask Atlas fold into the
  //: bar's ⋯ (DESIGN.md "A menu behind a button"), and the status line beside
  //: them says when "Explain" last ran and what is working now.
  const status = jobLineEl("link-reasons");
  status.classList.add("inbox-status");
  const working = (text) => {
    const opener = more.querySelector("button");
    if (text) opener?.setAttribute("aria-busy", "true");
    else opener?.removeAttribute("aria-busy");
    if (text) {
      status.dataset.jobSig = "";
      setLabel(status, `ph:spin ${text}`);
    } else paintJobLine(status);
  };
  const backfill = {
    label: "ph:lightbulb Explain your existing links",
    title: "For links you've already made elsewhere: work out why each one exists, first from how alike the notes are, then by asking Atlas to name the actual connection. Doesn't touch the suggestions below, which aren't links yet.",
    run: async () => {
      working("Explaining your links…");
      const result = await apiJson("/entries/links/backfill-reasons", { method: "POST", body: JSON.stringify({ ai: true }) }).catch((e) => {
        toast(e.message, true);
        return null;
      });
      working("");
      refreshJobRuns();
      if (!result) return;
      const parts = [];
      if (result.updated) parts.push(`marked ${result.updated}`);
      if (result.rewritten) parts.push(`wrote a real reason for ${result.rewritten}`);
      if (parts.length) toast(`Links: ${parts.join(", ")}.`);
      else if (result.ai_unavailable) toast("Marked what I could, Atlas isn't running, so none could be put into words yet.", "info");
      else toast("Every link already has a reason.");
    },
  };
  //: An AI guess for these rows' own Why boxes, written in as a real value
  //: (editable, and used as-is by Link if left alone).
  const fillReasons = async (targets, quiet) => {
    const result = await apiJson("/entries/link-suggestions/reasons", {
      method: "POST",
      silent: quiet,
      body: JSON.stringify({ pairs: targets.map((r) => ({ source_id: r.s.source_id, target_id: r.s.target_id })) }),
    }).catch((e) => {
      if (!quiet) toast(e.message, true);
      return null;
    });
    if (!result) return null;
    const byPair = new Map(result.reasons.map((r) => [`${r.source_id}:${r.target_id}`, r.reason]));
    let filled = 0;
    for (const r of targets) {
      //: Never over something typed while the request was in flight.
      if (r.input.dataset.userEdited && quiet) continue;
      const reason = byPair.get(`${r.s.source_id}:${r.s.target_id}`);
      if (reason) {
        r.input.value = reason;
        r.reveal?.();
        filled++;
      }
    }
    return { filled, result };
  };
  const suggestReasons = {
    label: "ph:sparkle Suggest reasons",
    title: "Ask Atlas to guess why each note pair below might be connected, and fill in any empty reason with its answer, still yours to edit or clear before linking.",
    run: async () => {
      const targets = rowReasons.filter((r) => r.input.isConnected && !r.input.value.trim());
      if (!targets.length) {
        toast("Every visible suggestion already has a reason.");
        return;
      }
      working("Suggesting reasons…");
      const done = await fillReasons(targets, false);
      working("");
      if (!done) return;
      if (done.filled) toast(`Filled in ${done.filled} reason${done.filled === 1 ? "" : "s"}.`);
      else if (done.result.ai_unavailable) toast("Atlas isn't running, so no reasons could be guessed.", "info");
      else toast("Couldn't guess a reason for any of these.");
    },
  };
  //: **Every sure one at once** (WORLD_CLASS_PLAN, Placed 2026-09-09 item
  //: 92): the rows at 70% or more, linked through each row's own Link, so a
  //: typed reason and the learning go with each as they would one by one.
  const linkSure = smallButton(
    "ph:link Link all above 70%",
    "Link every suggestion below that is at least 70% sure, each with its reason; a link can be removed from either note.",
    async () => {
      const sure = rowReasons.filter((r) => r.input.isConnected && (r.s.confidence ?? r.s.similarity ?? 0) >= LINK_ALL_AT);
      if (!sure.length) return toast("None of these is 70% sure or more.");
      const many = `${sure.length} pair${sure.length === 1 ? "" : "s"}`;
      if (!(await confirmDialog(`Link ${many} of notes? Each is linked with its reason; a link can be removed from either note.`, { confirmLabel: "Link them" }))) return;
      setBusy(linkSure, true, "Linking…");
      //: Quiet per row: one toast and one reload for the lot, not one each.
      let linked = 0;
      for (const r of sure) if (await r.link({ quiet: true })) linked++;
      setBusy(linkSure, false);
      refreshEntries(sure.flatMap((r) => [r.s.source_id, r.s.target_id])).catch(() => {});
      toast(`Linked ${linked} of ${many}.`, linked < sure.length);
    },
  );
  const more = kebabMenu([suggestReasons, backfill], "More ways to fill in reasons");
  const tools = document.createElement("div");
  tools.className = "row inbox-tools";
  //: When "Explain your existing links" last ran (INBOX 438); settings.js.
  tools.append(linkSure, more, status);
  list.appendChild(tools);
  for (const s of suggestions) list.appendChild(inboxLinkRow(s, rowReasons));
  inboxCount("links", suggestions.length);
  if (!suggestions.length) inboxEmpty(list, list.dataset.empty);
  //: Reasons arrive on their own for the top six (each is a model round trip
  //: on a slow local model); failure is silent, the deduced text stands.
  const pending = rowReasons.slice(0, 6);
  if (pending.length) requestAnimationFrame(() => fillReasons(pending, true));
}

function inboxLinkRow(s, rowReasons) {
  const row = document.createElement("div");
  row.className = "link-suggestion";
  //: **The two notes are the subject** (INBOX 1329): each name one line, cut
  //: with an ellipsis and whole in its title, an arrow between, where two
  //: wrapping chips of raw file names were the row's tallest thing (measured
  //: at 390: 210px a row, one row in view). Side by side on a wide sheet,
  //: stacked on a phone (inbox-lazy.css).
  const text = document.createElement("span");
  text.className = "link-suggestion-text link-suggestion-pair";
  //: The note's name, not its markdown (`notePreviewText`, as everywhere).
  const name = (raw) => notePreviewText(raw || "").replace(/\s+/g, " ").trim() || "Untitled note";
  const noteName = (raw) => {
    const made = document.createElement("span");
    made.className = "link-suggestion-note";
    const icon = document.createElement("i");
    icon.className = "ph ph-note";
    icon.setAttribute("aria-hidden", "true");
    const words = document.createElement("span");
    words.className = "link-suggestion-name";
    words.textContent = name(raw);
    made.title = name(raw);
    made.append(icon, words);
    return made;
  };
  const join = document.createElement("i");
  join.className = "ph ph-arrows-left-right link-suggestion-join";
  join.setAttribute("aria-hidden", "true");
  text.append(noteName(s.source_preview), join, noteName(s.target_preview));
  text.setAttribute("role", "group");
  text.setAttribute("aria-label", `${name(s.source_preview)} and ${name(s.target_preview)}`);
  //: A reason you can type before you link; left blank, the server deduces.
  const reason = document.createElement("input");
  reason.type = "text";
  reason.className = "link-suggestion-reason";
  reason.maxLength = 80;
  reason.placeholder = s.reason && s.reason !== "similar in meaning" ? s.reason : "Why? (optional: Atlas will work it out)";
  reason.setAttribute("aria-label", "Reason for this link");
  reason.addEventListener("input", () => {
    reason.dataset.userEdited = "1";
  });
  //: The field waits behind "Add a reason" (item 92): most links need none,
  //: and a field on every row was the row's widest thing. A reason Atlas
  //: fills in shows it.
  reason.classList.add("hidden");
  const addReason = smallButton("ph:text-t Add a reason", "Say why these two belong together", () => reveal());
  addReason.classList.add("quiet", "link-suggestion-add-reason");
  const reveal = () => {
    reason.classList.remove("hidden");
    addReason.classList.add("hidden");
    if (document.activeElement === addReason) reason.focus();
  };
  const rowState = { s, input: reason, reveal, link: null };
  rowReasons.push(rowState);
  const sigs = s.signals || [];
  const signals = sigs.map((g) => g.signal);
  const link = smallButton("ph:link Link", "Connect these two notes", () => linkIt());
  const linkIt = async ({ quiet = false } = {}) => {
    //: Left empty, a pair found by structure keeps its reasons and their
    //: confidence (KG9); one found by wording alone lets the server deduce.
    const typed = reason.value.trim();
    const structural = sigs.some((g) => g.signal !== "similarity" && g.signal !== "time");
    const given = typed || (structural ? s.reason : "");
    const body = { target_id: s.target_id };
    if (given) body.reason = given;
    if (!typed && structural) body.reason_confidence = s.confidence;
    //: A link that failed stays in the list, and says so to whoever asked
    //: (`linkSure` counts the ones that worked).
    const made = await apiJson(`/entries/${s.source_id}/links`, { method: "POST", body: JSON.stringify(body) }).catch((e) => {
      toast(e.message, true);
      return null;
    });
    if (!made) return false;
    pushLinkCreateUndo(s.source_id, s.target_id, made, body, "Linked two suggested notes");
    inboxCorrection("accept_link", { a: s.source_id, b: s.target_id, signals });
    if (!quiet) {
      toast(typed ? "Linked, with your reason." : "Linked.");
      refreshEntries([s.source_id, s.target_id]).catch(() => {});
    }
    inboxDone("links", row);
    return true;
  };
  rowState.link = linkIt;
  reason.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      link.click();
    }
  });
  const dismiss = smallButton("ph:x", "Dismiss this suggestion", () => {
    inboxCorrection("dismiss_link", { a: s.source_id, b: s.target_id, signals }, "Dismissed a link suggestion");
    inboxDone("links", row);
  });
  //: How sure and why, one line under the names: the bar and its number,
  //: then the reasons, cut to the line, each with its own percentage in the
  //: title (`inboxWhy` spells them out under the other kinds' rows).
  const facts = document.createElement("p");
  facts.className = "muted link-suggestion-facts";
  facts.appendChild(inboxScoreBar(s.confidence ?? s.similarity));
  if (sigs.length) {
    const why = inboxWhy(sigs);
    why.title = why.textContent;
    why.textContent = sigs.map((g) => g.reason).join(" · ");
    facts.appendChild(why);
  }
  //: The row's actions, one cell: the reason as a quiet word, Link with its
  //: edge (the row's one accept), the dismiss a quiet cross.
  dismiss.classList.add("quiet");
  const actions = document.createElement("span");
  actions.className = "link-suggestion-actions";
  actions.append(addReason, link, dismiss);
  row.append(text, facts, actions, reason);
  return row;
}

// A line for code that builds its control at runtime. Painted at once from
// what is already known, and a refresh is asked for.
function jobLineEl(kind) {
  const el = document.createElement("p");
  el.className = "status job-line";
  el.setAttribute("role", "status");
  el.dataset.jobLine = kind;
  paintJobLine(el);
  refreshJobRuns();
  return el;
}
