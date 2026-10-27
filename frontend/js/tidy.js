// tidy.js: Tidy, the notebook's housekeeping as rules (INBOX 691).
//
// Lazy (app.js `LAZY_MODULES.tidy`), fetched a few seconds after boot so the
// Notes dock's count is there without the boot scripts carrying it, and
// entered through `openTidySheet`, a `LAZY_ENTRY_POINTS` stand-in. The owner:
// "a way to better sort through links and tags without the ai ... needs to
// also be known to the user, no use having them if the user doesnt know about
// them". The rules are the server's (`entry/tidy.py`, `/tidy`): this file
// draws them as one sheet on the suggestions inbox's recipe: an overview of
// all nine reviews (icon, name, count, one line on what it finds; the ones
// with nothing to tidy last), and, pressed, one review with a back button
// (one line of description naming what its button changes; the rows) on the
// Attach picker's checkable rows (`note-picker-row`), a tool row (the
// review's level, its Apply automatically switch, Select all and none) and a
// foot whose one filled button applies the ticked rows. Each apply is one
// Undo, in the toast, on Ctrl+Z and in the sheet's Recent runs.

//: The '?' holds four short lines (INBOX 718: "massive"); what each review
//: finds and changes is in that review's own description, not here.
const TIDY_HELP = [
  "Tidy finds clean-up jobs by rule, with no AI.",
  "Open a review, tick rows, press its button.",
  "One Undo reverses a batch; the cross hides a row.",
  "Confirm keeps a pattern; Not right hides it.",
];

//: The open sheet's state, and the count's last fetch and its pending
//: redraw timer: one host object, not three top-level lets (the global-scope
//: ratchet, tests/test_global_scope_ratchet.py).
const TIDY = { state: null, badgeAt: 0, badgeTimer: 0 };

//: The Notes dock's count: how many rows every review finds. Fetched when the
//: module arrives, after a change made here, and when the notes list redraws
//: (debounced, at most every 20 s), so a note filed elsewhere moves it.
async function tidyBadge(force = false) {
  //: Not while locked. `wiring.js` loads this module 4 s after the page does,
  //: and on a lock screen that ran `GET /tidy` with no token: a 401 and a
  //: console error on every launch (audit 2026-10-10). The notes list redraws
  //: after unlock and the watcher below asks again then.
  if (!authToken()) return;
  const now = Date.now();
  if (!force && now - TIDY.badgeAt < 20000) return;
  TIDY.badgeAt = now;
  const body = await apiJson("/tidy", { silent: true }).catch(() => null);
  if (!body) return;
  if (TIDY.state) tidyCounts(body);
  const count = $("notes-tidy-count");
  const button = $("notes-tidy");
  if (!count || !button) return;
  count.textContent = body.total > 99 ? "99+" : body.total ? String(body.total) : "";
  count.hidden = !body.total;
  const words = body.total ? `Tidy, ${body.total} to look at` : "Tidy";
  button.setAttribute("aria-label", words);
  button.title = body.total
    ? `Tidy: ${body.total} things to look at (weak links, stray tags, uncategorised and duplicate notes, old reminders)`
    : "Tidy: weak links, stray tags, uncategorised and duplicate notes, old reminders";
}

function tidyWatchList() {
  const list = $("entry-list");
  if (!list || list.dataset.tidyWatched) return;
  list.dataset.tidyWatched = "1";
  new MutationObserver(() => {
    clearTimeout(TIDY.badgeTimer);
    TIDY.badgeTimer = setTimeout(() => tidyBadge(), 3000);
  }).observe(list, { childList: true });
}

//: One glyph per rule, for the overview's rows.
const TIDY_ICONS = {
  "link-reasons": "link-simple",
  "weak-links": "link-break",
  "auto-tags": "tag",
  "rare-tags": "hash",
  "lookalike-tags": "arrows-merge",
  uncategorised: "folder-dashed",
  duplicates: "copy",
  "similar-categories": "folders",
  "category-names": "textbox",
  "short-notes": "note-blank",
  "stale-reminders": "clock-countdown",
};

async function openTidySheet(review = "") {
  if (TIDY.state) {
    if (review) tidyShow(review);
    return;
  }
  const state = { view: "overview", key: "", reviews: {}, order: [], rows: [], ticked: new Set(), level: "" };
  TIDY.state = state;
  state.close = openSheet({
    label: "Tidy",
    name: "tidy",
    onClose: () => {
      TIDY.state = null;
    },
    build: (card) => {
      card.classList.add("inbox-card", "tidy-card");
      tidyHead(card);
      //: The overview: every review as one row, pressed to open it.
      const overview = document.createElement("ul");
      overview.className = "tidy-overview";
      overview.id = "tidy-overview";
      overview.setAttribute("aria-label", "Reviews");
      //: One review (T1, INBOX 830): a quiet back link over its name, its
      //: description, its tools, its rows and, when it has rows, the foot.
      //: Hidden while the overview is showing.
      const pane = document.createElement("div");
      pane.className = "tidy-review";
      pane.id = "tidy-review";
      pane.hidden = true;
      const nav = document.createElement("div");
      nav.className = "tidy-nav";
      const back = smallButton("ph:arrow-left All reviews", "Back to the list of reviews", () => tidyOverview(state.key));
      back.id = "tidy-back";
      back.classList.add("quiet", "tidy-back-link");
      const title = document.createElement("h3");
      title.className = "tidy-title";
      title.id = "tidy-title";
      nav.append(back, title);
      const about = document.createElement("p");
      about.className = "muted inbox-desc";
      about.id = "tidy-about";
      const tools = document.createElement("div");
      tools.className = "tidy-tools";
      const list = document.createElement("ul");
      list.className = "note-picker-list tidy-list";
      list.id = "tidy-list";
      list.setAttribute("aria-label", "What this review found");
      const foot = document.createElement("div");
      foot.className = "tidy-foot";
      pane.append(nav, about, tools, list, foot);
      //: Recent runs (T2): a quiet disclosure row, closed, so the rows keep
      //: the sheet's height.
      const history = document.createElement("div");
      history.className = "tidy-history";
      history.id = "tidy-history";
      //: The Patterns line (CHAT_PLAN decision 32): what the notes measure,
      //: each a count or a date with one fixed hedge; shown with the overview.
      const patterns = document.createElement("div");
      patterns.className = "muted inbox-desc tidy-patterns";
      patterns.hidden = true;
      Object.assign(state, { overview, patterns, pane, title, about, tools, list, foot, history });
      card.append(overview, patterns, pane, history);
    },
  });
  const body = await apiJson("/tidy", { silent: true }).catch(() => null);
  if (TIDY.state !== state) return;
  if (!body) {
    const failed = document.createElement("li");
    failed.className = "muted";
    setLabel(failed, "ph:warning Couldn't read the reviews. Try again in a moment.");
    state.overview.replaceChildren(failed);
    return;
  }
  tidyCounts(body);
  if (review && state.reviews[review]) await tidyShow(review);
  tidyHistory();
  tidyPatterns(state);
}

//: "Patterns: You have written about golf 4 times since 5 September; that
//: keeps coming up." From `/insights/patterns`, no model; nothing when no
//: rule fires, which is most notebooks most days.
async function tidyPatterns(state) {
  const body = await apiJson("/insights/patterns", { silent: true }).catch(() => null);
  if (TIDY.state !== state || !body?.patterns.length) return;
  //: One line per pattern, each with Confirm and Not right (decision 60); a
  //: confirmed one is said as the person's word and carries neither.
  state.patterns.replaceChildren(
    ...body.patterns.map((pattern) => {
      if (pattern.confirmed && pattern.rule !== "drift") {
        const line = document.createElement("p");
        line.className = "insight-line";
        line.textContent = `Patterns: ${pattern.text}`;
        return line;
      }
      return insightLine(pattern, `Patterns: ${pattern.text}`, (line, verdict, result) => {
        if (verdict === "dismissed" || verdict === "done") line.remove();
        else line.textContent = `Patterns: ${result.line}`;
      });
    })
  );
  state.patterns.hidden = state.view !== "overview";
}

//: The head: the title, its '?', then the close (the inbox's head).
function tidyHead(card) {
  const head = card.querySelector(".sheet-head");
  if (!head) return;
  const help = document.createElement("button");
  help.type = "button";
  help.className = "icon-only ghost small dialog-head-btn";
  help.setAttribute("data-help-for", "tidy-help");
  help.setAttribute("aria-controls", "tidy-help");
  help.setAttribute("aria-expanded", "false");
  help.title = "About Tidy";
  help.setAttribute("aria-label", "About Tidy");
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
  helpBody.id = "tidy-help";
  helpBody.setAttribute("role", "dialog");
  helpBody.setAttribute("aria-label", "About Tidy");
  for (const line of TIDY_HELP) {
    const p = document.createElement("p");
    p.textContent = line;
    helpBody.appendChild(p);
  }
  head.after(helpBody);
}

//: Fresh counts from the server: the overview is drawn again (its rows
//: sorted, the ones with nothing to tidy last) or, inside a review, only its
//: title's count moves.
function tidyCounts(body) {
  const state = TIDY.state;
  if (!state) return;
  state.order = body.reviews.map((r) => r.key);
  for (const r of body.reviews) state.reviews[r.key] = { ...state.reviews[r.key], ...r };
  if (state.view === "review") tidyTitle();
  else tidyOverviewDraw();
}

function tidyTitle() {
  const state = TIDY.state;
  const review = state?.reviews[state.key];
  if (!review) return;
  state.title.textContent = review.count ? `${review.label} (${review.count})` : review.label;
}

//: The overview: one row for each of the nine reviews, the ones with rows
//: first (the server's order among them), the ones with nothing to tidy last
//: and muted. `sort` is stable, so the order among equals is the server's.
function tidyOverviewDraw() {
  const state = TIDY.state;
  if (!state) return;
  const held = document.activeElement?.closest?.(".tidy-overview-row")?.dataset.review;
  const sorted = [...state.order].sort((a, b) => !state.reviews[a].count - !state.reviews[b].count);
  state.overview.replaceChildren(...sorted.map((key) => tidyOverviewRow(state.reviews[key])));
  if (held) state.overview.querySelector(`[data-review="${held}"]`)?.focus();
}

function tidyOverviewRow(review) {
  const li = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "note-picker-row tidy-overview-row";
  button.dataset.review = review.key;
  button.classList.toggle("is-empty", !review.count);
  const icon = document.createElement("i");
  icon.className = `ph ph-${TIDY_ICONS[review.key] || "broom"} tidy-overview-icon`;
  icon.setAttribute("aria-hidden", "true");
  const lines = document.createElement("span");
  lines.className = "note-picker-lines";
  const name = document.createElement("span");
  name.className = "note-picker-text";
  name.textContent = review.label;
  const meta = document.createElement("span");
  meta.className = "note-picker-meta";
  meta.textContent = review.finds;
  meta.title = review.finds;
  lines.append(name, meta);
  const count = document.createElement("span");
  count.className = "tidy-overview-count";
  if (review.count) {
    const number = document.createElement("span");
    number.textContent = String(review.count);
    const words = document.createElement("span");
    words.className = "visually-hidden";
    words.textContent = " to tidy";
    count.append(number, words);
  } else {
    count.textContent = "Nothing to tidy";
  }
  const caret = document.createElement("i");
  caret.className = "ph ph-caret-right tidy-overview-caret";
  caret.setAttribute("aria-hidden", "true");
  button.append(icon, lines, count, caret);
  button.addEventListener("click", () => tidyShow(review.key));
  li.appendChild(button);
  return li;
}

//: Back to the overview, with the focus on the row it came from.
function tidyOverview(focusKey = "") {
  const state = TIDY.state;
  if (!state) return;
  state.view = "overview";
  state.key = "";
  state.overview.hidden = false;
  if (state.patterns.textContent) state.patterns.hidden = false;
  state.pane.hidden = true;
  tidyOverviewDraw();
  state.overview.querySelector(`[data-review="${focusKey}"]`)?.focus();
}

async function tidyShow(key, level = "") {
  const state = TIDY.state;
  if (!state || !state.reviews[key]) return;
  const arriving = state.view !== "review";
  state.view = "review";
  state.key = key;
  state.overview.hidden = true;
  state.patterns.hidden = true;
  state.pane.hidden = false;
  const review = state.reviews[key];
  state.level = level || review.level || "";
  state.about.textContent = review.about;
  tidyTitle();
  state.list.replaceChildren();
  state.foot.replaceChildren();
  setLabel(state.list, "ph:spin Looking…");
  tidyTools(review);
  if (arriving) $("tidy-back")?.focus();
  const query = state.level ? `?level=${encodeURIComponent(state.level)}` : "";
  const body = await apiJson(`/tidy/${encodeURIComponent(key)}${query}`, { silent: true }).catch(() => null);
  if (TIDY.state !== state || state.key !== key) return;
  state.rows = body ? body.rows : [];
  state.ticked = new Set(state.rows.filter((r) => r.ticked).map((r) => r.id));
  tidyRows();
  if (body) {
    review.count = body.count;
    tidyTitle();
  }
}

const TIDY_LEVEL_WORDS = {
  weak: "Strength: weak",
  some: "Strength: weak or some",
  strong: "Strength: any",
  low: "Fit under 25%",
  medium: "Fit under 50%",
  high: "Fit under 75%",
};

//: The tool row: the review's level, its automatic switch, then the doors to
//: the tool it belongs with (the tag manager, the filings to check).
function tidyTools(review) {
  const state = TIDY.state;
  state.tools.replaceChildren();
  if (review.levels?.length) {
    const level = document.createElement("select");
    level.id = "tidy-level";
    level.setAttribute("aria-label", "Which rows to list");
    level.title = "Which rows to list";
    for (const value of review.levels) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = TIDY_LEVEL_WORDS[value] || value;
      level.appendChild(option);
    }
    level.value = state.level;
    level.addEventListener("change", () => tidyShow(review.key, level.value));
    state.tools.appendChild(level);
  }
  if (review.can_auto) {
    const label = document.createElement("label");
    label.className = "setting-check tidy-auto";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = "tidy-auto";
    box.checked = !!review.auto;
    const words = document.createElement("span");
    words.textContent = "Apply automatically";
    label.title = "Run this review after each note is filed; every run is listed below with its Undo";
    box.addEventListener("change", async () => {
      const result = await apiJson("/tidy/auto", { method: "PUT", body: JSON.stringify({ key: review.key, on: box.checked }) }).catch((e) => {
        toast(e.message, true);
        return null;
      });
      if (!result) {
        box.checked = !box.checked;
        return;
      }
      review.auto = result.auto;
      toast(result.auto ? `${review.label} now runs after each note is filed.` : `${review.label} waits for you again.`);
    });
    label.append(box, words);
    state.tools.appendChild(label);
  }
  const doors = {
    "rare-tags": ["ph:hash Tag manager", "Rename, merge or remove tags by hand", () => openTagsSheet()],
    "lookalike-tags": ["ph:hash Tag manager", "Rename, merge or remove tags by hand", () => openTagsSheet()],
    uncategorised: ["ph:check-square Filings to check", "The Notes list filtered to is:review: filings Atlas was unsure of", () => {
      state.close();
      showNotesFilter("is:review");
    }],
    "weak-links": ["ph:lightbulb Suggestions", "Links to add, decided one by one", () => openSuggestionsInbox("links")],
  };
  const door = doors[review.key];
  if (door) {
    const button = smallButton(door[0], door[1], door[2]);
    button.classList.add("tidy-door");
    state.tools.appendChild(button);
  }
}

function tidyRows() {
  const state = TIDY.state;
  state.list.replaceChildren();
  if (!state.rows.length) {
    const empty = document.createElement("li");
    empty.className = "muted empty-line tidy-empty";
    empty.textContent = "Nothing to tidy here.";
    state.list.appendChild(empty);
  }
  for (const row of state.rows) state.list.appendChild(tidyRow(row));
  tidyFoot();
}

function tidyRow(row) {
  const state = TIDY.state;
  const li = document.createElement("li");
  const label = document.createElement("label");
  label.className = "note-picker-row tidy-row";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.className = "visually-hidden note-picker-box";
  box.checked = state.ticked.has(row.id);
  box.disabled = !row.selectable;
  box.addEventListener("change", () => {
    if (box.checked) state.ticked.add(row.id);
    else state.ticked.delete(row.id);
    tidyFoot();
  });
  const lines = document.createElement("span");
  lines.className = "note-picker-lines";
  const name = document.createElement("span");
  name.className = "note-picker-text";
  name.textContent = row.title;
  name.title = row.title;
  const meta = document.createElement("span");
  meta.className = "note-picker-meta";
  meta.textContent = row.detail;
  meta.title = row.detail;
  const change = document.createElement("span");
  change.className = "tidy-change";
  setLabel(change, `ph:arrow-right ${row.change}`);
  change.title = row.change;
  lines.append(name, meta, change);
  const check = document.createElement("span");
  check.className = "note-picker-check";
  check.setAttribute("aria-hidden", "true");
  const tick = document.createElement("i");
  tick.className = "ph ph-check";
  check.appendChild(tick);
  label.append(box, lines, check);
  if (!row.selectable) label.classList.add("is-off");
  //: **Dismiss for good** (INBOX 783, the owner: "how do I delete a
  //: suggestion??"): a cross beside the row, not inside its label (a button in
  //: a label is a second control in the first). The server remembers it, so the
  //: row is not listed, counted or applied again; the toast's Undo brings it back.
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "ghost icon-only small tidy-dismiss";
  dismiss.title = "Dismiss: do not suggest this again";
  dismiss.setAttribute("aria-label", `Dismiss “${row.title}”`);
  setLabel(dismiss, "ph:x");
  dismiss.addEventListener("click", () => tidyDismiss(row));
  li.className = "tidy-row-item";
  li.append(label, dismiss);
  return li;
}

async function tidyDismiss(row) {
  const state = TIDY.state;
  const key = state.key;
  const path = `/tidy/${encodeURIComponent(key)}`;
  const body = JSON.stringify({ ids: [row.id] });
  const sent = await apiJson(`${path}/dismiss`, { method: "POST", body }).catch((e) => {
    toast(e.message, true);
    return null;
  });
  if (!sent) return;
  await tidyAfterChange([]);
  const send = (verb) => async () => {
    await apiJson(`${path}/${verb}`, { method: "POST", body });
    await tidyAfterChange([]);
  };
  offerUndo("Dismissed a tidy suggestion", "Dismissed. It will not be suggested again.", send("undismiss"), send("dismiss"));
}

//: The foot: how many are ticked, Select all and none, then the one filled
//: button; the link reasons review adds the whole-notebook background pass.
function tidyFoot() {
  const state = TIDY.state;
  const review = state.reviews[state.key];
  state.foot.replaceChildren();
  const selectable = state.rows.filter((r) => r.selectable);
  const n = selectable.filter((r) => state.ticked.has(r.id)).length;
  const count = document.createElement("span");
  count.className = "muted tidy-count";
  count.setAttribute("role", "status");
  count.textContent = selectable.length ? `${n} of ${selectable.length} ticked` : "";
  //: An empty review is its one line, with no selection bar (T1).
  state.foot.hidden = !state.rows.length;
  if (!state.rows.length) return;
  const all = smallButton("ph:checks All", "Tick every row", () => {
    for (const r of selectable) state.ticked.add(r.id);
    tidyRows();
  });
  const none = smallButton("ph:square None", "Untick every row", () => {
    state.ticked.clear();
    tidyRows();
  });
  all.disabled = !selectable.length;
  none.disabled = !n;
  const end = document.createElement("span");
  end.className = "tidy-foot-end";
  if (review?.key === "link-reasons") {
    end.appendChild(smallButton("ph:play Add reasons to all in the background", "Add a reason to every link the notes can explain, as a background job you can stop from Settings, Background tasks", tidyRunLinkReasons));
  }
  const apply = smallButton(`ph:check ${tidyApplyWords(review?.key, n)}`, "Make the change on every ticked row", () => tidyApply(apply), false);
  apply.id = "tidy-apply";
  apply.disabled = !n;
  end.appendChild(apply);
  state.foot.append(count, all, none, end);
}

//: What Apply does, in the plain words of the change (INBOX 718: "what is
//: naming???"): the bare verb while nothing is ticked, then the verb with
//: the number and the thing it counts. Each review's description (`about`,
//: tidy.py) uses the same words, so the button is never a word the sheet has
//: not already said.
const TIDY_APPLY = {
  "link-reasons": ["Add reasons", "Add {n} reason", "Add {n} reasons"],
  "weak-links": ["Remove links", "Remove {n} link", "Remove {n} links"],
  "auto-tags": ["Remove tags", "Remove {n} tag", "Remove {n} tags"],
  "rare-tags": ["Remove tags", "Remove {n} tag", "Remove {n} tags"],
  "lookalike-tags": ["Merge tags", "Merge {n} set of tags", "Merge {n} sets of tags"],
  uncategorised: ["Move notes", "Move {n} note", "Move {n} notes"],
  duplicates: ["Merge notes", "Merge {n} set of notes", "Merge {n} sets of notes"],
  "similar-categories": ["Merge categories", "Merge {n} group", "Merge {n} groups"],
  "category-names": ["Rename", "Rename {n} category", "Rename {n} categories"],
  "short-notes": ["Move to bin", "Move {n} note to bin", "Move {n} notes to bin"],
  "stale-reminders": ["Mark done", "Mark {n} done", "Mark {n} done"],
};

function tidyApplyWords(key, n) {
  const words = TIDY_APPLY[key];
  if (!words) return n ? `Apply to ${n}` : "Apply";
  return n ? words[n === 1 ? 1 : 2].replace("{n}", String(n)) : words[0];
}

//: The reviews that change categories ask first (WORLD_CLASS 23, decision
//: 4: "applying asks"); Undo is still one press after.
const TIDY_ASKS = {
  "similar-categories": "Merge these categories?\n\nTheir notes move into the largest one; Undo puts them back.",
  "category-names": "Rename these categories?\n\nUndo puts the old names back.",
};

async function tidyApply(button) {
  const state = TIDY.state;
  const key = state.key;
  const ids = [...state.ticked];
  const level = state.level;
  if (TIDY_ASKS[key] && !(await confirmDialog(TIDY_ASKS[key], { confirmLabel: tidyApplyWords(key, ids.length), danger: false }))) return;
  setBusy(button, true, "Working…");
  const result = await apiJson(`/tidy/${encodeURIComponent(key)}/apply`, { method: "POST", body: JSON.stringify({ ids, level }) }).catch((e) => {
    toast(e.message, true);
    return null;
  });
  setBusy(button, false);
  if (!result) return;
  if (!result.applied) {
    toast(result.message || "Nothing to change.", "info");
    return;
  }
  let undoId = result.undo_id;
  const undo = async () => {
    const back = await apiJson(`/tidy/undo/${undoId}`, { method: "POST" });
    await tidyAfterChange(back.entry_ids);
  };
  const redo = async () => {
    const again = await apiJson(`/tidy/${encodeURIComponent(key)}/apply`, { method: "POST", body: JSON.stringify({ ids, level }) });
    undoId = again.undo_id;
    await tidyAfterChange(again.entry_ids);
  };
  const action = pushUndo(result.message, undo, redo);
  toastAction(`${result.message}.`, "Undo", async () => {
    settleUndoFromToast(action);
    await undo();
  });
  await tidyAfterChange(result.entry_ids);
}

//: `entryIds` are the notes the run or its undo changed (the server reads them
//: off the undo payload), so only those rows are patched and the notebook is
//: not read again (tests/test_refresh_entries.py). A run that touched no note
//: (old reminders) patches none.
async function tidyAfterChange(entryIds) {
  if (entryIds && entryIds.length) await refreshEntries(entryIds);
  await tidyBadge(true);
  if (TIDY.state) {
    if (TIDY.state.view === "review") await tidyShow(TIDY.state.key, TIDY.state.level);
    tidyHistory();
  }
}

async function tidyRunLinkReasons() {
  const result = await apiJson("/tidy/link-reasons/run", { method: "POST" }).catch((e) => {
    toast(e.message, true);
    return null;
  });
  if (result) toast("Adding reasons in the background. Stop it from Settings, Background tasks.");
}

//: Recent runs: the last five, each with its Undo until it has been undone.
async function tidyHistory() {
  const state = TIDY.state;
  if (!state) return;
  const body = await apiJson("/tidy/history?limit=5", { silent: true }).catch(() => null);
  if (TIDY.state !== state) return;
  state.history.replaceChildren();
  const runs = body?.runs || [];
  if (!runs.length) return;
  const head = document.createElement("button");
  head.type = "button";
  head.className = "ghost small disclosure-row tidy-history-head";
  const caret = document.createElement("i");
  caret.className = "ph ph-caret-down contents-caret";
  caret.setAttribute("aria-hidden", "true");
  head.append(caret, ` Recent runs (${runs.length})`);
  const list = document.createElement("ul");
  list.className = "tidy-history-list";
  list.id = "tidy-history-list";
  list.hidden = true;
  head.setAttribute("aria-expanded", "false");
  head.setAttribute("aria-controls", list.id);
  head.addEventListener("click", () => {
    list.hidden = !list.hidden;
    head.setAttribute("aria-expanded", String(!list.hidden));
  });
  for (const run of runs) {
    const li = document.createElement("li");
    li.className = "tidy-history-row";
    const text = document.createElement("span");
    text.className = "tidy-history-text";
    text.textContent = `${run.message}${run.automatic ? ", automatically" : ""} · ${relativeTime(run.at)}`;
    li.appendChild(text);
    if (run.undone) {
      const done = document.createElement("span");
      done.className = "muted";
      done.textContent = "Undone";
      li.appendChild(done);
    } else {
      li.appendChild(smallButton("ph:arrow-counter-clockwise Undo", `Put back: ${run.message}`, async () => {
        const back = await apiJson(`/tidy/undo/${run.undo_id}`, { method: "POST" }).catch((e) => toast(e.message, true));
        toast(`Undid: ${run.message}.`);
        await tidyAfterChange(back?.entry_ids);
      }));
    }
    list.appendChild(li);
  }
  state.history.append(head, list);
}

tidyWatchList();
tidyBadge(true);
