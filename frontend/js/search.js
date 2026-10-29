// search.js: the search box, "Find anything" (WORLD_CLASS_PLAN decision 46,
// phase 25a, Brief 47). One box over every kind the index holds (notes,
// documents, boards, mind maps, files, bookmarks, reminders and chats), the
// operators in its '?' help, saved searches as rows in the Notes sidebar,
// and the keyboard alone: arrows walk, Enter opens, Escape closes.
//
// Lazy (app.js `LAZY_MODULES.search`, fetched a few seconds after boot or
// on first use; `openFinder` is its stand-in until then). The engine is the
// server's (`GET /search`, search/engine.py); this file reads no query
// itself: the operators are `search/query.py`'s (tests/test_one_reader.py).
// Moved whole out of spaces-find.js, where it was boot code.
//
//: **One search over everything you keep, and over the app itself.**
//:
//: INBOX 270, the owner: *"this is a search for any and all content, items,
//: text, files everything. a full application wide semantic search which shows
//: content as well as features and actions etc. absolutely everything and what
//: shows can be filtered, sorted and toggled."*
//:
//: The engine was already here and nothing called it. `/search`
//: (routes_search.py over `search/engine.py`) ranks notes, documents, boards,
//: files, bookmarks and reminders in one list, keyword and meaning together,
//: with three scores, a plain-English explanation per hit and a count per kind
//: so an empty result can say whether nothing matched or nothing of that kind
//: is indexed. Measured against a live server before any of this was written:
//: a three-note, one-document notebook answers `?q=sourdough` with all four,
//: correctly ranked. The only reader of anything under `/search` in the whole
//: frontend was Settings, asking for a number.
//:
//: So this file is a front door, not a second search. What it adds on top of
//: the route is the half the route cannot have: the app's own actions. A
//: person looking for "dark mode" or "tensions" is searching, and a search
//: that answers only with documents sends them to the settings tree to hunt.
//: `paletteCommands()` is the existing list, so a command added there appears
//: here without anyone remembering this exists.

//: One icon per kind, the same glyph that kind wears everywhere else, plus
//: "action", which is this surface's own and is not a kind the index knows.
const FINDER_KINDS = [
  { key: "note", icon: "ph:note-pencil", one: "note", many: "notes" },
  { key: "document", icon: "ph:file-text", one: "document", many: "documents" },
  { key: "board", icon: "ph:squares-four", one: "board", many: "boards" },
  //: Its own kind since the index learned to tell a map from a board.
  //: Reported: "Mind maps don't show in the Find anything universal search".
  //: A previous pass renamed the board chip "boards & maps" and left the
  //: map filed as a board, so a map still wore a board's meaning and could
  //: not be asked for on its own; `search/index.py` now indexes it as `map`,
  //: with the words on its topics, and it wears the glyph a map wears in the
  //: Library and the tab strip.
  { key: "map", icon: "ph:tree-structure", one: "mind map", many: "mind maps" },
  { key: "file", icon: "ph:paperclip", one: "file", many: "files" },
  { key: "bookmark", icon: "ph:bookmark-simple", one: "bookmark", many: "bookmarks" },
  { key: "reminder", icon: "ph:alarm", one: "reminder", many: "reminders" },
  //: A saved chat and an Ask turn, both `chat` in the index (decision 46).
  { key: "chat", icon: "ph:chat-circle", one: "chat", many: "chats" },
  //: A kept recording, found by its name and by what was said in it.
  { key: "recording", icon: "ph:microphone", one: "recording", many: "recordings" },
  { key: "action", icon: "ph:lightning", one: "action", many: "actions" },
];

let finderKind = "";       // "" is everything
let finderQuery = "";
let finderHits = [];
let finderCounts = {};
//: UX-04: the index's size per kind, for "nothing is indexed yet"; the
//: chips count this query's hits, so they cannot say it.
let finderIndexTotals = {};
//: The corrected query the hits are for, if the route fixed a typo.
//: `page` and `more`: the route's paging, for "Show more".
const finderState = { corrected: "", notices: [], page: 1, more: false, timer: null, run: 0, active: -1, opener: null };
//: The box's private counters live on `finderState` rather than as four more
//: top-level lets (tests/test_global_scope_ratchet.py): `timer` the typing
//: pause, `run` so a slow answer cannot paint over a newer one, `active` the
//: row the keyboard is on, `opener` what to give focus back to.

//: What pressing a result does, per kind. A row whose kind has no opener is
//: still drawn: knowing the thing exists and where it lives is most of the
//: answer, and a control that does nothing when pressed is the one thing worse
//: than no control, so those rows are not buttons.
//: Through the Library's own `openLibraryItem` wherever a kind is one of its
//: rows, rather than a second set of "how do I open a board" rules. That
//: function already knows a board opens its board and not the empty note the
//: board is stored in, which is exactly the mistake a fresh copy would make.
const FINDER_OPEN = {
  note: (hit) => { switchTab("notes"); flashEntry(hit.id); },
  document: (hit) => { switchTab("documents"); openDocument(hit.id); },
  board: (hit) => openLibraryItem({ kind: "board", id: hit.id }),
  map: (hit) => openLibraryItem({ kind: "map", id: hit.id }),
  file: (hit) => flashLibraryItem("file", hit.id),
  bookmark: (hit) => flashLibraryItem("link", hit.id),
  reminder: () => switchTab("reminders"),
  recording: (hit) => ensureModule("meetings").then(() => openRecordings(hit.id)),
  //: A chat opens in Chat; an Ask turn where a live answer renders, the Ask
  //: section of Notes (`viewAskHistoryTurn`, ask-history.js).
  chat: (hit) => {
    if (hit.source === "ask_turns") {
      switchTab("notes");
      showNotesSection("ask");
      viewAskHistoryTurn(hit.id);
    } else {
      switchTab("chat");
      openConversation(hit.id);
    }
  },
};

function finderOverlay() { return document.getElementById("finder-overlay"); }

//: The app's own actions, matched here rather than sent to the server: they
//: are not in the index, they change with the tab you are on, and matching a
//: dozen labels in the browser is cheaper than a round trip.
function finderActions(query) {
  //: The palette's rows and its ranking (app-palette.js `paletteFind`, Brief
  //: 90): every feature, act and setting, not only the hand-written commands.
  return paletteFind(query).slice(0, 6).map((command) => {
    const label = richPickerSplitLabel(command.label).text;
    return {
      kind: "action",
      id: label,
      title: label,
      snippet: "",
      explain: ["an action in the app"],
      //: Ranked just under a real content hit on purpose: someone typing
      //: "sourdough" wants their notes, and someone typing "zoom in" gets no
      //: content hits at all, so the ordering only matters in the case where
      //: content exists and should win.
      score: 0.5,
      written: "",
      run: command.run,
    };
  });
}

async function finderSearch(append = false) {
  const run = ++finderState.run;
  finderState.page = append ? finderState.page + 1 : 1;
  const query = finderQuery.trim();
  const results = document.getElementById("finder-results");
  const summary = document.getElementById("finder-summary");
  if (!results) return;
  if (!query) {
    finderHits = [];
    finderCounts = {};
    finderRenderEmpty();
    return;
  }
  //: **No "Searching" flash.** Reported: "the 'searching...' text keeps
  //: suddenly appearing and disappearing and it feels jarring and not
  //: smooth". A local index answers in tens of milliseconds, so on every
  //: keystroke the word appeared and was replaced before it could be read: a
  //: label that existed only to blink. It is written only if the search is
  //: still going after a beat, which on this machine is almost never, and
  //: the previous count stays on screen until the new one replaces it, so
  //: the line never empties between two answers.
  const slow = setTimeout(() => {
    if (run === finderState.run) summary.textContent = "Searching…";
  }, 400);
  //: `kind` is passed to the route, not filtered here, so a filtered search
  //: gets a *full page* of that kind rather than whatever survived a page of
  //: everything. Actions are filtered here because the route has never heard
  //: of them.
  const kindParam = finderKind && finderKind !== "action" ? `&kind=${finderKind}` : "";
  const body = await apiJson(
    `/search?q=${encodeURIComponent(query)}${kindParam}&limit=30&page=${finderState.page}`,
    { silent: true }
  ).catch(() => null);
  clearTimeout(slow);
  if (run !== finderState.run) return; // a newer keystroke owns the screen now
  if (!body) {
    finderHits = [];
    finderCounts = {};
    results.replaceChildren();
    surfaceFailed(results, "the results", () => finderSearch());
    return;
  }
  surfaceRecovered(results);
  finderIndexTotals = body.counts || {};
  finderState.corrected = body.corrected || "";
  finderState.notices = body.notices || [];
  finderState.more = Boolean(body.more);
  if (append) {
    finderHits = [...finderHits.filter((hit) => hit.kind !== "action"), ...(body.hits || []), ...finderHits.filter((hit) => hit.kind === "action")];
    finderRender();
    return;
  }
  //: The palette's file is lazy; in by now on any second search.
  if (!(finderKind && finderKind !== "action")) await ensureModule("appPalette");
  if (run !== finderState.run) return;
  const actions = finderKind && finderKind !== "action" ? [] : finderActions(query);
  const hits = finderKind === "action" ? [] : body.hits || [];
  //: Atlas's face answers a search (INBOX 742: it barely changed): glad at
  //: something found, puzzled at nothing; the last of a burst only (atlas.js).
  if (finderKind !== "action") atlasOn(hits.length ? "found" : "nothing");
  //: **A chip counts what this search found, not what the index holds.**
  //: `body.counts` is the index's size per kind (the route says so), and
  //: beside "3 results" a chip reading "Notes 46" was read as 46 matches.
  //: Counted from an unfiltered page of hits, and kept while a kind filter
  //: is on, so the other chips still say how many of theirs the query
  //: found. A kind the index holds none of stays a zero either way.
  if (!finderKind) {
    const found = {};
    for (const hit of hits) found[hit.kind] = (found[hit.kind] || 0) + 1;
    for (const [kind, total] of Object.entries(body.counts || {})) {
      if (!total) found[kind] = 0;
    }
    finderCounts = found;
  }
  finderHits = [...hits, ...actions];
  finderRender();
}

//: Sorting is done here rather than asked of the route because two of the
//: three orders are about the answer set on screen, and one of them ("best
//: match") is the order the route already returned. Re-querying to reverse a
//: list would be a round trip to rearrange thirty rows.
function finderSorted() {
  const rows = [...finderHits];
  const sort = document.getElementById("finder-sort")?.value || "best";
  if (sort === "best" || sort === "category") return rows.sort((a, b) => (b.score || 0) - (a.score || 0));
  const dir = sort === "newest" ? -1 : 1;
  return rows.sort((a, b) => {
    //: An action has no date, and an undated row sorted as the empty string
    //: would bunch every one of them at one end of a date sort. They keep
    //: their relative order and go last either way.
    if (!a.written && !b.written) return 0;
    if (!a.written) return 1;
    if (!b.written) return -1;
    return a.written < b.written ? dir : a.written > b.written ? -dir : 0;
  });
}

//: A listbox only while it lists something (WCAG 4.1.2); a group otherwise,
//: which may keep the name "Results".
function finderResultsRole(results, listing) {
  results.setAttribute("role", listing ? "listbox" : "group");
}

function finderRenderEmpty() {
  const results = document.getElementById("finder-results");
  const summary = document.getElementById("finder-summary");
  if (summary) summary.textContent = "";
  if (!results) return;
  results.replaceChildren();
  finderResultsRole(results, false);
  const box = document.createElement("div");
  box.className = "empty-state";
  const icon = document.createElement("i");
  icon.className = "ph ph-magnifying-glass empty-icon";
  icon.setAttribute("aria-hidden", "true");
  const title = document.createElement("p");
  title.className = "empty-title";
  title.textContent = "Search everything you keep";
  const body = document.createElement("p");
  body.textContent =
    "Notes, documents, boards, mind maps, files, bookmarks, reminders and chats at once, by your words and by what they mean. Type to begin.";
  box.append(icon, title, body);
  results.appendChild(box);
  finderRenderFilters();
}

//: **Nothing matched says why, and offers one way on** (row 3, CHAT_PLAN
//: decision 49; DESIGN.md's empty state: one sentence and one action). The
//: way on is the first of: every kind, when a kind filter is on; the word as
//: spelled in the dictionary (frontend/vendor/wordlist), when that spelling
//: finds something; the nearest feature by name (the palette's own rows).
function finderRenderNothing(results) {
  const query = finderQuery.trim();
  const box = document.createElement("div");
  box.className = "empty-state";
  const title = document.createElement("p");
  title.className = "empty-title";
  title.textContent = "Nothing matched";
  const body = document.createElement("p");
  const indexed = Object.values(finderIndexTotals).reduce((sum, n) => sum + (n || 0), 0);
  body.textContent = indexed ? finderWhyNothing(query) : "Nothing is indexed yet. Save a note and it will appear here.";
  const action = document.createElement("button");
  action.type = "button";
  action.className = "ghost small hidden finder-nothing-action";
  box.append(title, body, action);
  results.appendChild(box);
  if (indexed && query) finderOffer(action, query);
}

function finderWhyNothing(query) {
  const kind = FINDER_KINDS.find((k) => k.key === finderKind);
  if (kind) return `No ${kind.many} hold “${query}”.`;
  return `No note, document, board, file, bookmark, reminder or chat holds “${query}”, and no part of the app is called that.`;
}

async function finderOffer(button, query) {
  const run = finderState.run;
  const offer = finderKindOffer() || (await finderSpellingOffer(query)) || (await finderFeatureOffer(query));
  if (!offer || run !== finderState.run || !button.isConnected) return;
  setLabel(button, offer.label);
  button.addEventListener("click", offer.run);
  button.classList.remove("hidden");
}

function finderKindOffer() {
  if (!finderKind) return null;
  return {
    label: "ph:funnel-simple Search every kind",
    run: () => {
      finderKind = "";
      finderSearch();
    },
  };
}

function finderUse(text) {
  const input = document.getElementById("finder-input");
  if (input) input.value = text;
  finderQuery = text;
  finderSearch();
}

//: The dictionary, fetched on the first search that finds nothing (871KB,
//: the documents' spelling list; never at open).
const finderWords = { load: null };
function finderWordlist() {
  if (!finderWords.load) finderWords.load = api("/vendor/wordlist/en.txt", { silent: true })
    .then((response) => response.text())
    .then((text) => new Set(text.split("\n").map((w) => w.trim()).filter(Boolean)))
    .catch(() => new Set());
  return finderWords.load;
}

//: Words one edit away that the dictionary holds: a swap, a letter added, a
//: letter changed, a letter dropped, in that order (a missed key is the
//: commonest slip).
function finderSpellings(word, words) {
  const letters = "abcdefghijklmnopqrstuvwxyz";
  const tries = [];
  for (let i = 0; i < word.length - 1; i++) tries.push(word.slice(0, i) + word[i + 1] + word[i] + word.slice(i + 2));
  for (let i = 0; i <= word.length; i++) for (const c of letters) tries.push(word.slice(0, i) + c + word.slice(i));
  for (let i = 0; i < word.length; i++) for (const c of letters) tries.push(word.slice(0, i) + c + word.slice(i + 1));
  for (let i = 0; i < word.length; i++) tries.push(word.slice(0, i) + word.slice(i + 1));
  return [...new Set(tries.filter((t) => t !== word && t.length > 2 && words.has(t)))];
}

//: The first respelling that finds something, three tried at most: a
//: suggestion that also finds nothing is no way on.
async function finderSpellingOffer(query) {
  const words = await finderWordlist();
  const said = query.toLowerCase().split(/\s+/).filter(Boolean);
  const wrong = said.findIndex((w) => w.length > 2 && /^[a-z]+$/.test(w) && !words.has(w));
  if (!words.size || wrong < 0) return null;
  for (const spelled of finderSpellings(said[wrong], words).slice(0, 3)) {
    const guess = said.map((w, i) => (i === wrong ? spelled : w)).join(" ");
    const body = await apiJson(`/search?q=${encodeURIComponent(guess)}&limit=1`, { silent: true }).catch(() => null);
    if (body?.hits?.length) return { label: `ph:text-aa Search for “${guess}”`, run: () => finderUse(guess) };
  }
  return null;
}

async function finderFeatureOffer(query) {
  await ensureModule("appPalette");
  const row = paletteNearestCommand(query);
  if (!row) return null;
  const { icon, text } = richPickerSplitLabel(row.label);
  return {
    label: `${icon || "ph:compass"} Open ${text}`,
    run: () => {
      closeFinder();
      row.run();
    },
  };
}

//: **Built once, updated in place.** Every search refreshes the counts, and a
//: first version rebuilt the whole row to show them. Measured: the chip you
//: had just pressed was replaced by a new node a moment later, so it reported
//: itself unpressed to anything reading it, and a keyboard user lost focus to
//: <body> on every filter change. The row is furniture; only its numbers and
//: its pressed state change.
//: Which ends of the kind row can still scroll, so the fade sits only on
//: an edge with more behind it (the owner, 2026-09-24: the last chip,
//: Actions, was faded with the row scrolled all the way to it).
function finderSyncFilterEdges(bar) {
  const max = bar.scrollWidth - bar.clientWidth;
  bar.classList.toggle("fade-start", bar.scrollLeft > 1);
  bar.classList.toggle("fade-end", max - bar.scrollLeft > 1);
}

function finderRenderFilters() {
  const bar = document.getElementById("finder-filters");
  if (!bar) return;
  if (!bar.dataset.edgesWired) {
    bar.dataset.edgesWired = "1";
    bar.addEventListener("scroll", () => finderSyncFilterEdges(bar), { passive: true });
    new ResizeObserver(() => finderSyncFilterEdges(bar)).observe(bar);
  }
  requestAnimationFrame(() => finderSyncFilterEdges(bar));
  const wanted = [
    { key: "", label: "Everything", count: null },
    ...FINDER_KINDS.map((kind) => ({
      key: kind.key,
      label: kind.many.charAt(0).toUpperCase() + kind.many.slice(1),
      //: A kind with nothing indexed still gets a chip, showing its own zero,
      //: because "there are no files" is an answer and a missing chip is not.
      //: Actions are counted by whatever the current query matches, so they
      //: carry no number at all rather than a misleading one.
      count: kind.key === "action" ? null : finderCounts[kind.key] ?? 0,
    })),
  ];
  if (!bar.children.length) {
    for (const row of wanted) {
      const chip = document.createElement("button");
      chip.type = "button";
      //: `.library-chip`, the app's own interactive filter chip
      //: (UI_MODERNISATION_PLAN Phase 2), not `.chip`, which is a *display*
      //: chip: accent-soft, 0.75rem, weight 600, meant for a status label.
      //: Reported with a screenshot: eight of them in a row read as eight
      //: badges rather than eight controls, at a size nothing else here uses.
      chip.className = "library-chip finder-chip";
      chip.dataset.kind = row.key;
      chip.addEventListener("click", () => {
        finderKind = finderKind === row.key ? "" : row.key;
        finderSearch();
      });
      bar.appendChild(chip);
    }
  }
  [...bar.children].forEach((chip, index) => {
    const row = wanted[index];
    if (!row) return;
    //: **A count only once there is something to count.** The chips used to
    //: read "Notes 0, Documents 0, Boards 0" before a single character had
    //: been typed, which is eight confident zeroes about a notebook nobody
    //: had searched: they are the index's counts for the *query*, and with
    //: no query they mean nothing. Reported with a screenshot.
    const showCount = row.count != null && finderQuery.trim();
    chip.textContent = showCount ? `${row.label} ${row.count}` : row.label;
    //: Kept, by the decision above ("there are no files" is an answer), but
    //: quieter: a zero is a fact, not a filter worth reaching for.
    chip.classList.toggle("is-zero", Boolean(showCount && row.count === 0 && finderKind !== row.key));
    //: `aria-pressed`, not a class alone: this is a filter that is on or off
    //: and a screen reader has to hear which. `.active` is the class the
    //: chip recipe paints from, and it is painted from the same fact rather
    //: than being the fact.
    chip.setAttribute("aria-pressed", String(finderKind === row.key));
    chip.classList.toggle("active", finderKind === row.key);
  });
}

function finderRender() {
  const results = document.getElementById("finder-results");
  const summary = document.getElementById("finder-summary");
  if (!results) return;
  finderRenderFilters();
  let rows = finderSorted();
  results.replaceChildren();
  finderState.active = -1;
  finderResultsRole(results, rows.length > 0);
  if (!rows.length) {
    finderRenderNothing(results);
    if (summary) summary.textContent = finderState.notices.join(" ");
    return;
  }
  if (summary) {
    summary.textContent = `${nounCount(rows.length, "result")}${
      finderState.corrected ? `, showing results for “${finderState.corrected}”` : ""
    }${finderState.notices.length ? `. ${finderState.notices.join(" ")}` : ""}`;
  }
  const icons = Object.fromEntries(FINDER_KINDS.map((k) => [k.key, k.icon]));
  const names = Object.fromEntries(FINDER_KINDS.map((k) => [k.key, k]));
  //: **Grouped by kind, once there is more than one kind on screen.**
  //: Reported: "the results could have better Information Architecture". A
  //: flat list of thirty rows mixing notes, documents and actions asks the
  //: reader to sort them by eye, which is the work the app should have done.
  //: A heading per kind, in the order the filter chips run, so the two agree
  //: about what order the world is in.
  //:
  //: Only when it helps: one kind, or a sort other than best match, and a
  //: heading would be a label on a list that needs none. A date sort in
  //: particular is a *cross-kind* question ("what changed lately"), and
  //: grouping it by kind would break exactly the order that was asked for.
  const sortMode = document.getElementById("finder-sort")?.value || "best";
  const kinds = [...new Set(rows.map((hit) => hit.kind))];
  //: **Or by category** (INBOX 1332, "Sort, Group by category"): a note under
  //: the category it is filed in, anything else under its kind, in the order of
  //: each group's best row, which is the order `finderSorted` left them in.
  const byCategory = sortMode === "category";
  const groupOf = (hit) => (byCategory && hit.kind === "note" ? `c:${hit.category || "Uncategorised"}` : `k:${hit.kind}`);
  const grouped = (sortMode === "best" && kinds.length > 1) || (byCategory && new Set(rows.map(groupOf)).size > 1);
  if (grouped && !byCategory) {
    //: By kind in the chips' own order, and within a kind by the score the
    //: sort already put them in. A stable sort is what keeps that second
    //: half true without sorting twice.
    const rank = Object.fromEntries(FINDER_KINDS.map((k, i) => [k.key, i]));
    rows = [...rows].sort((a, b) => (rank[a.kind] ?? 99) - (rank[b.kind] ?? 99));
  } else if (grouped) {
    const first = new Map();
    rows.forEach((hit) => first.has(groupOf(hit)) || first.set(groupOf(hit), first.size));
    rows = [...rows].sort((a, b) => first.get(groupOf(a)) - first.get(groupOf(b)));
  }
  let lastKind = null;
  rows.forEach((hit, index) => {
    if (grouped && groupOf(hit) !== lastKind) {
      lastKind = groupOf(hit);
      const head = document.createElement("p");
      head.className = "finder-group muted";
      const many = rows.filter((row) => groupOf(row) === lastKind).length;
      const kind = names[hit.kind];
      //: A heading, so it starts with a capital: the names are the in-sentence
      //: nouns ("3 notes"), and printed alone they read as lowercase labels
      //: once the uppercase transform went (the owner: "all lowercase and
      //: hard to see"). The group's size beside it, muted.
      const word = byCategory && hit.kind === "note" ? hit.category || "Uncategorised" : kind ? (many === 1 ? kind.one : kind.many) : hit.kind;
      const label = document.createElement("span");
      label.textContent = word.charAt(0).toUpperCase() + word.slice(1);
      const count = document.createElement("span");
      count.className = "finder-group-count";
      count.textContent = String(many);
      head.replaceChildren(label, count);
      //: Not a `role="option"` inside the listbox: a heading is not
      //: selectable, and a screen reader walking the options would otherwise
      //: read the word "notes" as a result.
      head.setAttribute("aria-hidden", "true");
      results.appendChild(head);
    }
    const open = hit.run || FINDER_OPEN[hit.kind];
    const row = document.createElement(open ? "button" : "div");
    if (open) row.type = "button";
    row.className = "finder-row";
    row.setAttribute("role", "option");
    row.setAttribute("aria-selected", "false");
    row.dataset.index = String(index);
    const head = document.createElement("span");
    head.className = "finder-row-head";
    const title = document.createElement("span");
    title.className = "finder-row-title";
    //: `setNoteLabel`, not `setLabel`: a hit's title is the thing's own text
    //: and can begin with anything, a `#` or a `1.` included, so it must not
    //: go through the markdown renderer joined to an app-written icon token.
    setNoteLabel(title, icons[hit.kind] || "ph:dot", hit.title || "(untitled)", 70);
    head.appendChild(title);
    //: **A kind chip on every row** (decision 46): the group heading names a
    //: kind only while the list is grouped, and a date sort or a filtered
    //: list is not. The display chip, the one the quick-add row draws under
    //: a field (quickadd.js), not a control: the row is the control.
    const kindName = names[hit.kind];
    if (kindName) {
      const word = kindName.one.charAt(0).toUpperCase() + kindName.one.slice(1);
      head.appendChild(chip(word, "tag finder-kind"));
    }
    if (hit.written) {
      const when = document.createElement("span");
      when.className = "finder-row-when muted text-xs";
      //: A day the way the rest of the app writes one ("23 Sept"), not the
      //: ISO date the API sends; the year only when it is not this one.
      const day = /^\d{4}-\d\d-\d\d$/.test(hit.written) ? new Date(`${hit.written}T00:00:00`) : null;
      when.textContent = day && !Number.isNaN(day.getTime())
        ? day.toLocaleDateString(undefined, {
          day: "numeric",
          month: "short",
          year: day.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
        })
        : hit.written;
      if (day) when.title = day.toLocaleDateString(undefined, { dateStyle: "full" });
      head.appendChild(when);
    }
    row.appendChild(head);
    if (hit.snippet && hit.snippet !== hit.title) {
      const snippet = document.createElement("span");
      snippet.className = "finder-row-snippet muted";
      //: **Rendered, not printed.** Reported: "in the universal search,
      //: inline md isnt rendered or handled". `textContent` on a note's own
      //: text prints its asterisks and the literal text of any image it
      //: holds, which is the same report the chat's source cards had and is
      //: fixed here the same way. `compact`, because this is a two-line
      //: preview inside a row rather than a note body, and wiki links are
      //: unwrapped first since `renderInlineMarkdown` is inline-only and does
      //: not know `[[…]]`: without that a linked note prints its brackets.
      renderInlineMarkdown(
        snippet,
        //: Block markers go too: the snippet is a note's lines run together,
        //: so a heading's `##` lands mid-line ("test ## Introduction ... ###
        //: Adding"), where an inline renderer prints it. Stripped wherever
        //: one starts a word, the same rule the link labels use.
        hit.snippet
          .slice(0, 200)
          .replace(/\[\[([^[\]]{1,120})\]\]/g, "$1")
          .replace(/(^|\s)#{1,6}\s+/g, "$1")
          .replace(/(^|\s)>\s+/g, "$1"),
        null,
        true
      );
      row.appendChild(snippet);
    }
    //: One line of facts, not a row of chips: this is what the row *is*,
    //: which is DESIGN.md's `.library-file-meta` recipe ("short statements,
    //: dot separators, `--text-xs`, `--muted`, one rank"). Chips here read as
    //: things you could press, and two of them under every row turned the
    //: list into a field of badges. Reported with a screenshot.
    const reasons = (hit.explain || []).filter(Boolean);
    if (reasons.length) {
      const why = document.createElement("span");
      why.className = "finder-why muted";
      why.textContent = reasons.join(" \u00b7 ");
      row.appendChild(why);
    }
    if (open) {
      row.addEventListener("click", () => {
        closeFinder();
        open(hit);
      });
    }
    results.appendChild(row);
  });
  if (finderState.more) {
    //: Past the list's options, not one of them: a listbox holds results, and
    //: this is an action on the list, reached by Tab or the pointer.
    const more = document.createElement("button");
    more.type = "button";
    more.className = "ghost small finder-more";
    setLabel(more, "ph:caret-down Show more results");
    more.addEventListener("click", () => finderSearch(true));
    results.appendChild(more);
  }
}

//: Up and down move a highlight rather than focus, so the input keeps the
//: caret and you can keep typing: the shape every search field in the world
//: has, and the reason this is a `listbox` with `aria-activedescendant`
//: behaviour rather than a list of focusable buttons you tab through.
function finderMove(step) {
  const rows = [...document.querySelectorAll("#finder-results .finder-row")];
  if (!rows.length) return;
  if (finderState.active >= 0 && rows[finderState.active]) {
    rows[finderState.active].setAttribute("aria-selected", "false");
    rows[finderState.active].classList.remove("is-active");
  }
  finderState.active = (finderState.active + step + rows.length) % rows.length;
  const row = rows[finderState.active];
  row.setAttribute("aria-selected", "true");
  row.classList.add("is-active");
  //: The list's own `scrollTop`, never `scrollIntoView`, which walks every
  //: scrolling ancestor including the page (DESIGN.md, the recipe index).
  const box = row.parentElement;
  const top = row.offsetTop;
  const bottom = top + row.offsetHeight;
  if (top < box.scrollTop) box.scrollTop = top;
  else if (bottom > box.scrollTop + box.clientHeight) box.scrollTop = bottom - box.clientHeight;
}

//: `opts.kind` opens on one kind's filter (the code editor's Ctrl+Shift+F
//: asks for documents); a caller cannot set `finderKind` itself before this
//: file has loaded.
function openFinder(prefill = "", opts = {}) {
  const overlay = finderOverlay();
  if (!overlay) return;
  if (typeof opts.kind === "string") finderKind = opts.kind;
  finderState.opener = document.activeElement;
  overlay.classList.remove("hidden");
  const input = document.getElementById("finder-input");
  if (input) {
    if (prefill) input.value = prefill;
    finderQuery = input.value;
    input.focus();
    input.select();
  }
  syncFinderStar();
  if (finderQuery.trim()) finderSearch();
  else finderRenderEmpty();
}

function closeFinder() {
  const overlay = finderOverlay();
  if (!overlay || overlay.classList.contains("hidden")) return;
  overlay.classList.add("hidden");
  //: Focus goes back where it came from. A dialog that drops focus on <body>
  //: sends the next Tab to the top of the page, which is how a keyboard user
  //: loses their place.
  if (finderState.opener && document.contains(finderState.opener)) finderState.opener.focus();
  finderState.opener = null;
}

//: The star is a favourite toggle: filled while the words in the box are a
//: saved search (INBOX 790), pressed again it forgets that search.
function finderSavedAs(query) {
  return savedFinds().filter((item) => item.query === query.trim().slice(0, 200));
}

function syncFinderStar() {
  const button = document.getElementById("finder-save");
  if (!button) return;
  const on = Boolean(document.getElementById("finder-input")?.value.trim()) && finderSavedAs(document.getElementById("finder-input").value).length > 0;
  button.firstElementChild?.classList.toggle("star-fill", on);
  button.setAttribute("aria-pressed", String(on));
  button.setAttribute("aria-label", on ? "Remove this saved search" : "Save this search");
  button.title = on ? "Remove this saved search from the Notes sidebar" : "Save this search to the Notes sidebar";
}

function wireFinder() {
  const overlay = finderOverlay();
  const input = document.getElementById("finder-input");
  if (!overlay || !input) return;
  input.addEventListener("input", () => {
    finderQuery = input.value;
    syncFinderStar();
    clearTimeout(finderState.timer);
    //: Long enough that a typist does not fire a query per letter, short
    //: enough that the list feels attached to the keyboard. The abort is the
    //: `finderState.run` counter rather than an AbortController because the route
    //: is cheap and a cancelled fetch mid-index-read is not.
    finderState.timer = setTimeout(finderSearch, 180);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") { event.preventDefault(); finderMove(1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); finderMove(-1); }
    else if (event.key === "Enter") {
      const rows = [...document.querySelectorAll("#finder-results .finder-row")];
      const row = rows[finderState.active] || rows[0];
      if (row) { event.preventDefault(); row.click(); }
    }
  });
  document.getElementById("finder-sort")?.addEventListener("change", finderRender);
  document.getElementById("finder-save")?.addEventListener("click", saveFinderSearch);
  document.getElementById("finder-close")?.addEventListener("click", closeFinder);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeFinder();
  });
  document.addEventListener("keydown", (event) => {
    //: A dialog over the box (naming a saved search) takes its own Escape.
    if (event.key === "Escape" && !overlay.classList.contains("hidden") && !document.querySelector(".confirm-overlay")) {
      //: Captured before anything else can treat Escape as its own: this is
      //: the topmost surface while it is open.
      event.stopPropagation();
      closeFinder();
    }
  }, true);
}
wireFinder();

// --- saved searches -------------------------------------------------------------
//
//: **Rows in the Notes sidebar, kept in preferences** (`saved_finds`). The
//: sidebar's other rows are drawn from the notes, not stored, and the one
//: stored list beside them, the Notes filter's saved filters, lives in
//: preferences (`saved_searches`, settings-wiring.js): a short list the
//: person names, too small for a table of its own. Two keys rather than one
//: because a saved filter narrows the notes list and a saved search opens
//: this box over everything; one list meaning both would make a row do a
//: different thing depending on where it was pressed.

function savedFinds() {
  return (prefsCache && prefsCache.saved_finds) || [];
}

async function persistSavedFinds(next) {
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ saved_finds: next }),
  });
  renderSavedFinds();
  syncFinderStar();
}

async function saveFinderSearch() {
  const query = (document.getElementById("finder-input")?.value || "").trim();
  if (!query) {
    toast("Type a search first, then save it.", "info");
    return;
  }
  const already = finderSavedAs(query);
  if (already.length) {
    await persistSavedFinds(savedFinds().filter((item) => !already.includes(item)));
    toast("Removed the saved search.");
    return;
  }
  const name = await promptDialog("Name this search:", query.slice(0, 40), { confirmLabel: "Save search" });
  if (!name) return;
  //: Saving a name again replaces it, as the saved filters do.
  const next = savedFinds().filter((item) => item.name !== name);
  next.push({ name: name.slice(0, 40), query: query.slice(0, 200) });
  await persistSavedFinds(next.slice(-30));
  toast(`Saved "${name}" to the Notes sidebar.`);
}

async function renameSavedFind(item) {
  const name = await promptDialog("Rename this search:", item.name, { confirmLabel: "Rename" });
  if (!name || name === item.name) return;
  const next = savedFinds()
    .filter((other) => other.name !== name)
    .map((other) => (other.name === item.name ? { ...other, name: name.slice(0, 40) } : other));
  await persistSavedFinds(next);
}

async function forgetSavedFind(item) {
  await persistSavedFinds(savedFinds().filter((other) => other.name !== item.name));
  toast(`Forgot "${item.name}".`);
}

//: The sidebar's row recipe (notes-list.js `renderSidebar`): an `li` that is
//: one tab stop (`wireSidebarRowKeys`), its name in `.category-name`, its
//: ⋯ in `.category-actions`. The name is the person's own words, so it is a
//: text node beside the glyph, never a label through the markdown renderer.
function renderSavedFinds() {
  const box = document.getElementById("saved-finds-box");
  const list = document.getElementById("saved-finds");
  if (!box || !list) return;
  const saved = savedFinds();
  list.replaceChildren();
  box.classList.toggle("hidden", saved.length === 0);
  for (const item of saved) {
    const li = document.createElement("li");
    li.title = item.query;
    const name = document.createElement("span");
    name.className = "category-name";
    const glyph = document.createElement("i");
    glyph.className = "ph ph-magnifying-glass ph-lead";
    glyph.setAttribute("aria-hidden", "true");
    name.append(glyph, document.createTextNode(item.name));
    li.appendChild(name);
    li.addEventListener("click", () => openFinder(item.query, { kind: "" }));
    const actions = document.createElement("span");
    actions.className = "category-actions";
    const menu = kebabMenu(
      [
        { label: "ph:pencil-simple Rename…", title: `Rename ${item.name}`, run: () => renameSavedFind(item) },
        { label: "ph:trash Forget", title: `Take ${item.name} out of the sidebar`, danger: true, run: () => forgetSavedFind(item) },
      ],
      `Actions for ${item.name}`,
      { vertical: true }
    );
    menu.addEventListener("click", (event) => event.stopPropagation());
    actions.appendChild(menu);
    li.appendChild(actions);
    wireSidebarRowKeys(li);
    list.appendChild(li);
  }
}
renderSavedFinds();
