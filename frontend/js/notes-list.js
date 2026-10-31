// notes-list.js: the edit form, the notes filter, incremental rendering, list
// keyboard (a note card's menu panels are in note-panels.js, loaded on first use).
// Moved out of app.js on 2026-09-26 as one contiguous
// range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md). A classic
// script sharing app.js's globals, loaded in app.js's old order; nothing in an
// earlier file calls into it while the page loads (scratchpad/appjs-map.js
// --check).

//: **Capture's strip is the shape it ends up in from its first paint.** The
//: fold, the name and the tools group (More, layout, line numbers) are drawn
//: by documents.js, which loads after the first paint: at 390 the strip drew
//: expanded (two rows, 104px) and folded to the 54px collapsed bar when the
//: bundle landed, a 50px shift. The markup says collapsed, which is the
//: default (`docToolbarCollapsed`: collapsed unless the saved choice is "0");
//: this undoes it for a saved "0" and keeps the key and the default in step
//: with that reading (tests/test_capture_strip_first_paint.py).
function foldNoteToolbarForFirstPaint() {
  const bar = document.getElementById("note-toolbar");
  if (!bar) return;
  let collapsed = true;
  try {
    collapsed = (prefs.get("doc-toolbar-collapsed", null) ?? "1") === "1";
  } catch {
    collapsed = false; // private mode: the expanded shape is the safe default, as the bundle's
  }
  bar.classList.toggle("is-collapsed", collapsed);
  //: **The folded strip opens when pressed** (the owner, 2026-10-10: "The
  //: note capture subtab formatting toolbar wont open"). Until the note box
  //: is first focused its tools are not mounted, and "Formatting" is a
  //: label with nothing behind it; a press focuses the box, which mounts
  //: the editor and the tools with it.
  bar.addEventListener("click", (event) => {
    if (!bar.querySelector(".doc-toolbar-tools") && !event.target.closest("button")) startNewNote();
  });
}
foldNoteToolbarForFirstPaint();

//: Read by navigation.js's `hasUnsavedWork` (WORLD_CLASS_PLAN 22.1 item 4).
//: `editingId` alone says a form is *open*, not that anything in it has
//: changed; comparing every field back to `entry` at guard time would need
//: the same `entry` object this closure already has, so it is cheaper and
//: less to keep in step to set this once, here, than to reconstruct it from
//: the DOM later. Reset to false at the top of every fresh form (only one is
//: ever open, per the comment on `textarea.id` below) and on both ways out.
let noteFormDirty = false;
//: **The open form's unsaved fields, kept across redraws** (INBOX 432). The
//: form is rebuilt from `entry` by every `renderEntries()`, and that runs on
//: a star pressed elsewhere, a filter keystroke, a background filing, a tab
//: switch: measured, two edits typed into an open note were silently put
//: back to the saved text by the next redraw. Keyed by the note's id; cleared
//: on Save and on Cancel, the only two ways the form closes on purpose.
let noteFormDraft = null;

//: Ask before throwing away a form with changes in it. Answers true when it
//: is fine to leave (nothing changed, or the person agreed).
async function noteFormMayClose() {
  if (editingId === null || !noteFormDirty) return true;
  return confirmDialog("Discard your changes to this note?", { confirmLabel: "Discard" });
}

//: The keyboard back on a note's row after a redraw, unless it went somewhere.
function focusNoteRow(id) {
  requestAnimationFrame(() => {
    const active = document.activeElement;
    if (active && active !== document.body && active.isConnected) return;
    const row = document.querySelector(`#entry-list > li[data-id="${id}"]`);
    if (!row) return;
    for (const other of document.querySelectorAll("#entry-list > li[tabindex='0']")) other.tabIndex = -1;
    row.tabIndex = 0;
    row.focus({ preventScroll: true });
  });
}

//: Every "edit this note" goes through here, so a form with changes is
//: never swapped for another note's without asking.
async function openNoteEditor(id, { focusTags = false } = {}) {
  if (editingId !== null && editingId !== id && !(await noteFormMayClose())) return false;
  if (editingId !== id) {
    noteFormDirty = false;
    noteFormDraft = null;
    //: The copy kept on this device goes with it (note-edit-panels.js).
    if (typeof forgetNoteEditLocally === "function") forgetNoteEditLocally();
  }
  editingId = id;
  //: **On a phone the note page is put away first.** Tapping a note opens it
  //: as a full-page sheet (`openNotePage`, phone-shell.js) and its Edit button
  //: lands here, but the form is drawn into the list, which is behind that
  //: sheet: Edit did nothing anyone could see (found by the deepflows sweep at
  //: 390 wide). The page closes, and the form is there to type in.
  if (typeof notePageClose === "function") notePageClose();
  //: The caret goes into the form (WCAG 2.4.3); it was left on <body>.
  if (focusTags) focusTagsAfterRender = id;
  else focusBodyAfterRender = id;
  renderEntries();
  requestAnimationFrame(() => scrollEditingEntryIntoView(id));
  return true;
}

// Category <select> shared by capture (guided mode) and the edit form.
function fillCategoryOptions(select, selected) {
  select.replaceChildren();
  //: Every category, empty ones included, in the sidebar's order (INBOX 432).
  const names = [...new Set([...categoryMeta.keys(), ...allEntries.map((e) => e.category)])]
    .filter(Boolean)
    .sort(compareCategoryNames);
  if (selected === null) {
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "Let Atlas decide";
    select.appendChild(auto);
  }
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (name === selected) option.selected = true;
    select.appendChild(option);
  }
  const custom = document.createElement("option");
  custom.value = "__new__";
  custom.textContent = "+ New category…";
  select.appendChild(custom);
}

// "" → null (AI decides); "__new__" → ask for a name; else the value.
// Returns undefined when the user cancels the prompt.
async function resolveCategoryChoice(select) {
  if (select.value === "") return null;
  if (select.value !== "__new__") return select.value;
  // promptDialog resolves to trimmed text, or "" for cancel: one shape for
  // both, so there is no null to check the way window.prompt needed.
  const name = await promptDialog("Name for the new category", "", { confirmLabel: "Create" });
  return name || undefined;
}

// Text filter (Wave J): match note content or any tag, case-insensitive.
// --- the notes filter ------------------------------------------------------------
// Same lesson as the server's keyword search: a single substring match means
// the words have to be typed in the order they appear, which nobody can guess.
// This one also understands a few operators, because narrowing by tag or
// category is the thing you actually want once you have more than a few
// hundred notes: and it needs no AI whatsoever.
//
//   tag:work            only notes tagged "work"
//   cat:recipes         only notes in that category (category: also works)
//   is:favourite        favourite (is:pinned too) / private / linked / untagged
//   is:review           filings to check: unsure, or left in Uncategorised
//   tags:<2             fewer than 2 tags, also <=, >, >=, = (or bare N)
//   -picnic             notes that do NOT mention "picnic"
//   "exact phrase"      that phrase, verbatim
//   type: prop: links: rel: entity:   the structure (GRAPH_PLAN KG7), asked
//                       of the server (`/entries/query`), which the table and
//                       the graph ask too, so all three show the same notes
//
// Anything else is a plain word: all of them must appear, in any order.

//: KG7: the structural terms, `-` included, quoted or [[bracketed]] values whole.
//: And `prop:key="a value"` whole (query.py's `_TOKEN`).
const LIVE_QUERY_RE = /(^|\s)(-?(?:type|prop|links|rel|entity):(?:\[\[[^\]]{1,120}\]\]|"[^"]{1,200}"|[^\s"=<>!]{1,60}[=<>!]{1,2}"[^"]{1,200}"|\S+))/gi;
let liveQuery = { q: "", ids: null, pending: "" };

//: The ids the server gives for these terms, or null while it is asked.
function liveQueryIds(q) {
  if (liveQuery.q === q && liveQuery.ids) return liveQuery.ids;
  if (liveQuery.pending !== q) {
    liveQuery.pending = q;
    apiJson(`/entries/query?q=${encodeURIComponent(q)}`, { silent: true })
      .then((body) => {
        if (liveQuery.pending !== q) return;
        liveQuery = { q, ids: new Set(body.ids || []), pending: "" };
        renderEntries();
      })
      .catch(() => {
        if (liveQuery.pending === q) liveQuery = { q, ids: new Set(), pending: "" };
      });
  }
  return null;
}

//: **The operators the engine owns** (`kind:`, `has:`, `space:`): the Notes
//: parser had no meaning for them (each was a plain word that matched
//: nothing), and `GET /search` (`search/query.py`) has all three. They are
//: asked of the engine, the way `type:` and `prop:` are asked of
//: `/entries/query`, and the list keeps its own order and its own look.
const ENGINE_QUERY_RE = /(^|\s)((?:kind|has|space):(?:"[^"]{1,200}"|[^\s"]+))/gi;
//: One object for this file's engine state (the global-scope ratchet counts
//: top-level `let`s): `ids` answers `q`, `pending` is the question in the air,
//: `capped` says the engine's page (50) was full, `semanticFor` is the box text
//: the Semantic toggle's results were loaded for, and `rank` their order.
//: `jumpId` is set by `flashEntry` while it renders: the first paint must reach that id.
const noteEngine = { q: "", ids: null, pending: "", capped: false, semanticFor: "", rank: new Map(), jumpId: null };

//: The ids the engine gives for these operators, or null while it is asked.
//: Notes only (`kind=note`) unless the terms name a kind themselves.
function engineQueryIds(q) {
  if (noteEngine.q === q && noteEngine.ids) return noteEngine.ids;
  if (noteEngine.pending !== q) {
    noteEngine.pending = q;
    const kind = /(^|\s)kind:/i.test(q) ? "" : "&kind=note";
    apiJson(`/search?q=${encodeURIComponent(q)}${kind}&limit=50`, { silent: true })
      .then((body) => {
        if (noteEngine.pending !== q) return;
        const hits = (body.hits || []).filter((hit) => hit.kind === "note");
        noteEngine.q = q;
        noteEngine.ids = new Set(hits.map((hit) => hit.id));
        noteEngine.capped = (body.hits || []).length >= 50;
        noteEngine.pending = "";
        renderEntries();
      })
      .catch(() => {
        if (noteEngine.pending === q) Object.assign(noteEngine, { q, ids: new Set(), capped: false, pending: "" });
      });
  }
  return null;
}

// `tags:<2`, `tags:<=1`, `tags:0` and so on: "how many tags", not "which
// ones" (that's plain `tag:`). Asked for directly: a way to find the notes
// that only ever got the janitor's default filing and never a second look,
// since `is:untagged` alone only ever answered the zero case.
const TAG_COUNT_RE = /^tags:(<=|>=|<|>|=)?(\d+)$/;

//: The review queue (WORLD_CLASS_PLAN section 17, row 1): the janitor was
//: unsure, or left the note in Uncategorised, and nobody has decided since.
//: The server's `review_queue_count` is the same rule.
function entryNeedsReview(entry) {
  if (!entry || entry.user_filed || entry.is_draft || entry.is_board || entry.filing_state === "pending") return false;
  const unsure = entry.ai_confidence > 0 && entry.ai_confidence < REVIEW_THRESHOLD;
  return unsure || !entry.category || entry.category === "Uncategorised";
}

//: **The Notes tab, filtered, from anywhere.** The palette's "Show untagged
//: notes", the dashboard's Loose ends widget and the untagged nudge in the
//: bell all land here (INBOX 162: "notes with no tags or other things arent
//: highlighted"): one route to "the notes I mean" rather than three copies
//: of the same four lines.
function showNotesFilter(query) {
  switchTab("notes");
  //: Your notes, whichever sub-tab was last open (the owner, 2026-10-10: "I
  //: pressed show them, but it just navigated me to the Ask subtab").
  showNotesSection("browse");
  const search = $("note-search");
  search.value = query;
  search.dispatchEvent(new Event("input"));
  search.focus();
}

function parseNoteQuery(raw) {
  const query = {
    words: [],
    phrases: [],
    exclude: [],
    tags: [],
    categories: [],
    flags: [],
    tagCount: null,
    titles: [],
    before: null,
    after: null,
    structural: [],
    engine: [],
  };
  raw = (raw || "").replace(LIVE_QUERY_RE, (_, lead, term) => {
    query.structural.push(term);
    return lead || " ";
  });
  raw = raw.replace(ENGINE_QUERY_RE, (_, lead, term) => {
    query.engine.push(term);
    return lead || " ";
  });
  //: `tag:"two words"` and `cat:"Home office"` first, then bare quoted
  //: phrases, so neither's spaces become word breaks.
  const named = (raw || "").replace(/\b(tag|cat|category|in|title):"([^"]+)"/gi, (_, key, value) => {
    const v = value.toLowerCase().trim();
    const k = key.toLowerCase();
    if (k === "tag") query.tags.push(v);
    else if (k === "title") query.titles.push(v);
    else query.categories.push(v);
    return " ";
  });
  // Pull quoted phrases out first so their spaces don't become word breaks.
  const remainder = named.replace(/"([^"]+)"/g, (_, phrase) => {
    query.phrases.push(phrase.toLowerCase().trim());
    return " ";
  });
  for (const token of remainder.split(/\s+/)) {
    if (!token) continue;
    const lower = token.toLowerCase();
    const tagCountMatch = TAG_COUNT_RE.exec(lower);
    //: `#trip` is how a card shows a tag, so it is how people type one
    //: (INBOX 432: it matched nothing); `tag:#trip` the same.
    //: A bare `tag:` is still being typed: it narrows nothing yet.
    if (/^(tag:#?|#|category:|cat:|in:|title:|is:|kind:|has:|space:)$/.test(lower)) continue;
    if (lower.startsWith("tag:")) query.tags.push(lower.slice(4).replace(/^#/, ""));
    else if (lower.startsWith("#") && lower.length > 1) query.tags.push(lower.slice(1));
    else if (lower.startsWith("category:")) query.categories.push(lower.slice(9));
    else if (lower.startsWith("cat:")) query.categories.push(lower.slice(4));
    else if (lower.startsWith("in:")) query.categories.push(lower.slice(3));
    else if (lower.startsWith("title:")) query.titles.push(lower.slice(6));
    else if (/^(before|after):\d{4}-\d{2}(-\d{2})?$/.test(lower)) {
      const [key, day] = lower.split(":");
      query[key] = day.length === 7 ? `${day}-01` : day;
    }
    else if (lower.startsWith("is:")) query.flags.push(lower.slice(3));
    else if (tagCountMatch) {
      query.tagCount = { op: tagCountMatch[1] || "=", n: Number(tagCountMatch[2]) };
    } else if (lower.startsWith("-") && lower.length > 1) query.exclude.push(lower.slice(1));
    else query.words.push(lower);
  }
  return query;
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
  //: The engine answers one page (50); a full page says so rather than
  //: letting the count pass for the whole of a larger answer.
  count.textContent = parsed.engine.length > 0 && noteEngine.capped
    ? `The first ${ids.length} notes that match this query`
    : `${nounCount(ids.length, "note")} match this query`;
  bar.replaceChildren(
    count,
    smallButton("ph:table Table", "These notes as a table, their properties as columns", () => openQueryTable(ids)),
    smallButton("ph:graph Show on graph", "Light these notes on the graph", () => showQueryOnGraph(ids)),
  );
}

function noteQueryIsEmpty(query) {
  return (
    !query.words.length &&
    !query.phrases.length &&
    !query.exclude.length &&
    !query.tags.length &&
    !query.categories.length &&
    !query.flags.length &&
    !query.tagCount &&
    !query.titles.length &&
    !query.before &&
    !query.after &&
    !query.structural.length &&
    !query.engine.length
  );
}

function matchesTagCount(tagCount, n) {
  switch (tagCount.op) {
    case "<":
      return n < tagCount.n;
    case "<=":
      return n <= tagCount.n;
    case ">":
      return n > tagCount.n;
    case ">=":
      return n >= tagCount.n;
    default:
      return n === tagCount.n;
  }
}

//: True while the list on screen is the engine's answer to the box (the
//: Semantic toggle is on and its results were loaded for this very text).
function noteSemanticLoaded() {
  return Boolean(noteSearch) && noteEngine.semanticFor === noteSearch && Boolean($("semantic-search-toggle")?.checked);
}

function matchesSearch(entry) {
  if (!noteSearch) return true;
  const query = parseNoteQuery(noteSearch);
  if (noteQueryIsEmpty(query)) return true;

  if (query.structural.length) {
    const ids = liveQueryIds(query.structural.join(" "));
    if (!ids || !ids.has(entry.id)) return false;
  }
  if (query.engine.length) {
    const ids = engineQueryIds(query.engine.join(" "));
    if (!ids || !ids.has(entry.id)) return false;
  }
  const content = (entry.content || "").toLowerCase();
  const tags = (entry.tags || []).map((t) => t.toLowerCase());
  const category = (entry.category || "").toLowerCase();
  const haystack = `${content} ${tags.join(" ")}`;

  // A tag: or cat: filter is a statement about which notes count at all.
  //: A tag matches whole, or as the parent of a nested one (`tag:home`
  //: finds "home" and "home/garden", not "homework": INBOX 432).
  if (query.tags.length && !query.tags.every((t) => tags.some((tag) => tag === t || tag.startsWith(`${t}/`)))) {
    return false;
  }
  if (query.titles.length) {
    const title = noteSortName(entry).toLowerCase();
    if (!query.titles.every((t) => title.includes(t))) return false;
  }
  //: Days compared as YYYY-MM-DD in local time, the date the card shows.
  if (query.before || query.after) {
    const made = entry.created_at ? new Date(entry.created_at) : null;
    if (!made || Number.isNaN(made.getTime())) return false;
    const day = `${made.getFullYear()}-${String(made.getMonth() + 1).padStart(2, "0")}-${String(made.getDate()).padStart(2, "0")}`;
    if (query.before && !(day < query.before)) return false;
    if (query.after && !(day > query.after)) return false;
  }
  if (query.categories.length && !query.categories.some((c) => category.includes(c))) {
    return false;
  }
  for (const flag of query.flags) {
    //: `is:favourite` is the name the rest of the app now uses; `is:pinned` is
    //: kept because it is in this app's own help text, in saved filters people
    //: already have, and in muscle memory. Two spellings of one flag is a
    //: smaller cost than breaking a filter somebody saved.
    if ((flag === "pinned" || flag === "favourite" || flag === "favourites") && !entry.pinned) {
      return false;
    }
    if (flag === "private" && !entry.is_private) return false;
    //: A [[wiki link]] in the text is a link too (INBOX 432).
    if (flag === "linked" && !(entry.links || []).length && !/\[\[[^\]\n]{1,120}\]\]/.test(entry.content || "")) return false;
    if ((flag === "draft" || flag === "drafts") && !entry.is_draft) return false;
    if (flag === "untagged" && tags.length) return false;
    //: The review queue (section 17, row 1): unsure or Uncategorised filings
    //: nobody has decided on (`entryNeedsReview`, above).
    if (flag === "review" && !entryNeedsReview(entry)) return false;
  }
  if (query.tagCount && !matchesTagCount(query.tagCount, tags.length)) return false;
  if (query.exclude.some((word) => haystack.includes(word))) return false;
  //: With Semantic on, the list *is* the engine's answer for these words, which
  //: includes notes that share none of them; testing the words again here
  //: would drop exactly the notes the toggle exists to find.
  if (noteSemanticLoaded()) return true;
  if (!query.phrases.every((phrase) => content.includes(phrase))) return false;
  // Every word must appear somewhere, in any order.
  return query.words.every((word) => haystack.includes(word));
}

// The inline marks the writing side inserts (MD_ACTIONS' toolbars in
// documents.js, which editor.js's "/" menu reuses) and INLINE_MD below reads
// back. One table, so a mark cannot be written that the renderer does not
// draw: the Red/Grey highlight bug lived in the gap between the two.
// tests/test_code_documents.py runs each mark through INLINE_MD. `$` math is
// drawn by documents.js's docMathTree; `%%` comments are never rendered.
const MD_INLINE_MARKS = {
  bold: "**",
  italic: "*",
  strike: "~~",
  code: "`",
  highlight: "==",
};

// Code spans match first and are never re-read, so `**x**` in backticks stays
// literal; `_` italics are left out because snake_case is common in notes.
// Images and links come after the original four groups so callers keyed to
// m[1]..m[4] (`notePreviewText`) keep working; both accept a same-origin
// `/media/...` URL, where a note's uploads live.
// **The link and image groups are length-bounded on purpose**: an unbounded
// `[^\]\n]+` against an unclosed `[` is O(n²) per line (CodeQL's
// js/polynomial-redos); 200 and 500 characters are far past any real link.
// `==text==` highlights are characters in `content`, like every other mark,
// so search, export and the AI read them with no new column; bounded by
// excluding their own delimiter. The eight colours are the toolbars' eight
// (MD_COLOURS, documents.js) and the stylesheet's: a missing one printed its
// own name ("red|text"). tests/test_highlight_colours.py pins all three.
// The last alternative is a board text run, `{{size=24 ink=red|words}}`: the
// grammar is read here, at boot, and drawn by documents.js (`MD_RUN`, `mdRunNode`).
const INLINE_MD =
  /`([^`\n]+)`|\*\*([^*\n]+?)\*\*|~~([^~\n]+?)~~|==(?:(yellow|green|blue|pink|purple|orange|red|grey)\|)?([^=\n]+?)==|\+\+(yellow|green|blue|pink|purple|orange|red|grey)\|([^+\n]+?)\+\+|\*([^*\n]+?)\*|!\[([^\]\n]{0,200})\]\(([^)\n]{1,500})\)|\[([^\]\n]{0,200})\]\(([^)\n]{1,500})\)|\{\{((?:(?:size|font|ink|hl)=[a-z0-9]{1,12} ?){1,4})\|([^}\n]{1,2000}?)\}\}/g;

// `appendInline`'s own grammar, before it was merged into renderInlineMarkdown
// below: adds `__bold__`/`_italic_` and bare `https://…` autolinking, and its
// Kept textually separate from INLINE_MD so neither caller's matching moves; selected by `options.underscoreSyntax`.
const INLINE_MD_LEGACY =
  /`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|~~([^~]+)~~|==(?:(yellow|green|blue|pink|purple|orange|red|grey)\|)?([^=]+?)==|\+\+(yellow|green|blue|pink|purple|orange|red|grey)\|([^+]+?)\+\+|\*([^*]+)\*|(?<![\w])_([^_]+)_(?![\w])|!\[([^\]]{0,200})\]\(([^)\s]{1,500})\)|\[([^\]]{0,200})\]\(([^)\s]{1,500})\)|(https?:\/\/[^\s)]+)|\{\{((?:(?:size|font|ink|hl)=[a-z0-9]{1,12} ?){1,4})\|([^}\n]{1,2000}?)\}\}/g;

// Same allowlist an <img src> or <a href> built from note text has to pass:
// an absolute http(s) URL, or a same-origin relative path (one leading
// slash, not two: `//evil.com/x` is also "one string starting with /" but
// is a protocol-relative link off this origin). Rejects `javascript:`,
// `data:`, and anything else a pasted note could contain.
function isRenderableUrl(url) {
  //: `staged:` is this app's own scheme for a picture whose bytes are still
  //: in the browser (see `captureStagedImages`), renderable, because the
  //: preview draws it from the Blob, and never saved, because the save path
  //: rewrites every one of them to a real url first.
  if (typeof url === "string" && url.startsWith(STAGED_URL_PREFIX)) return true;
  //: An address of this app ("#/notes", "#/notes/12": what the tool answers
  //: link to, `ai/tool_say.py`), only when the router opens it (the owner,
  //: 2026-10-12: "[Open your notes](#/notes)" showed as raw text).
  if (/^#\//.test(url) && appAddressHash(url)) return true;
  return /^https?:\/\//i.test(url) || (url.startsWith("/") && !url.startsWith("//"));
}

// A non-image attachment (handleFileUpload's link-syntax branch) previously
// rendered as a bare link, indistinguishable at a glance from an ordinary
// URL: BACKLOG §4's "genuinely still open" follow-up. Only applied to our
// own /media/ uploads, not arbitrary external links, since a random web
// page's URL extension says nothing reliable about its content.
const ATTACHMENT_ICONS = {
  pdf: "ph-file-pdf", doc: "ph-file-doc", docx: "ph-file-doc", rtf: "ph-file-doc",
  xls: "ph-file-xls", xlsx: "ph-file-xls", csv: "ph-file-csv",
  ppt: "ph-file-ppt", pptx: "ph-file-ppt",
  zip: "ph-file-archive", rar: "ph-file-archive", "7z": "ph-file-archive",
  mp3: "ph-file-audio", wav: "ph-file-audio", ogg: "ph-file-audio", m4a: "ph-file-audio", webm: "ph-file-audio",
  mp4: "ph-file-video", mov: "ph-file-video",
  txt: "ph-file-text", md: "ph-file-md", json: "ph-file-code",
  png: "ph-file-image", jpg: "ph-file-image", jpeg: "ph-file-image",
  gif: "ph-file-image", webp: "ph-file-image", heic: "ph-file-image", heif: "ph-file-image",
};

// `name` is optional and only matters for a `/files/{id}` URL: the
// note-attachment download endpoint, opaque and extension-less by design
// (unlike `/media/<filename>.ext`, which pasted/dropped inline images use).
// Without it, a note's attached PDF/docx/etc. had no extension anywhere in
// its URL to read a type from, so every non-image attachment fell through
// to nothing rendering at all wherever a caller built the URL that way.
function attachmentIconClass(url, name) {
  const source = name || (url.startsWith("/media/") ? url : "");
  if (!source) return null;
  const ext = source.split(".").pop().split(/[?#]/)[0].toLowerCase();
  return ATTACHMENT_ICONS[ext] || "ph-file";
}

//: Extensions the file card labels by name rather than by the generic
//: "File", the type is the second most useful thing about a file after
//: what it is called, and "PDF · Open" reads as a thing you can do where
//: "myfile.pdf" alone reads as text that happens to end in .pdf.
const FILE_KIND_LABELS = {
  pdf: "PDF", doc: "Word", docx: "Word", odt: "Document", rtf: "Document",
  xls: "Sheet", xlsx: "Sheet", ods: "Sheet", csv: "CSV",
  ppt: "Slides", pptx: "Slides", odp: "Slides",
  txt: "Text", md: "Markdown", markdown: "Markdown",
  json: "JSON", xml: "XML", yaml: "YAML", yml: "YAML",
  html: "HTML", htm: "HTML", css: "CSS",
  js: "Code", ts: "Code", jsx: "Code", tsx: "Code", py: "Code", java: "Code",
  c: "Code", h: "Code", cpp: "Code", hpp: "Code", cs: "Code", go: "Code",
  rs: "Code", rb: "Code", php: "Code", sh: "Code", sql: "SQL",
  swift: "Code", kt: "Code", vb: "Code", vbs: "Code", diff: "Code", patch: "Code",
  zip: "Archive", mp3: "Audio", wav: "Audio", m4a: "Audio",
  mp4: "Video", mov: "Video", webm: "Video",
};

function fileKindLabel(url, name) {
  const source = name || url;
  const ext = source.split(".").pop().split(/[?#]/)[0].toLowerCase();
  return FILE_KIND_LABELS[ext] || "File";
}

/** The one-line form of the attachment card, for a surface too small for a card. */
function fileChip(name, url) {
  const label = name && name !== url ? name : url.split("/").pop();
  const chipEl = document.createElement("span");
  chipEl.className = "chip file-chip";
  setLabel(chipEl, `${(attachmentIconClass(url, name) || "ph-file").replace("ph-", "ph:")} ${label}`);
  chipEl.title = `${fileKindLabel(url, name)}: ${label}`;
  return chipEl;
}

//: **One card for every file attached to anything** (INBOX 440 (2), DESIGN.md
//: "A file attached to a note"). The owner: "all of the attachment cards ui
//: and ux and utility need a massive redesign and upgrade." One note measured
//: five shapes for the same idea (an inline thumbnail with a round x, a file
//: card with a save button, a bare thumbnail, two chips stretched to its
//: height), and the edit form's picture card was the one in the report: a
//: name cut to "Gary The Moss Mons...", three unlabelled glyphs under it, no
//: kind, no size, no open, no download, no rename.
//:
//: Now: a tile (the picture, or the kind's glyph on a tint), the whole name
//: on up to two lines, one line of facts, and the card itself is the button
//: that opens the file. Everything else is one ⋯ menu, so a card with seven
//: things it can do still shows one control. What a click *does* lives in
//: attachment-actions.js, loaded on the first click (`attachmentAction` is a
//: lazy entry point): the boot scripts were 79 bytes under their gzip total.
//:
//: `spec`: `name`, `url` (`/media/…`, `/files/{id}`, `staged:…` or "" for a
//: file not uploaded yet), and what the surface knows: `size`, `added`,
//: `thumb()` (a picture's src, for a `/files` image that needs a blob url),
//: `gallery()` (`{items, index}` to page through in the lightbox), and where
//: the file is written down, which is what decides Rename and Remove:
//: `textarea` + `markdown` (the box it is a link in), `attachment` +
//: `onChange` (a note's own file), `staged` (Capture, before Save).
const ATT_KINDS = { pdf: "pdf", mp3: "audio", wav: "audio", ogg: "audio", m4a: "audio", flac: "audio", aac: "audio", opus: "audio", mp4: "video", mov: "video", webm: "video", mkv: "video", m4v: "video" };

function attachmentExt(...sources) {
  for (const source of sources) {
    const match = /\.([a-z0-9]{1,5})(?:[?#].*)?$/i.exec(source || "");
    if (match) return match[1].toLowerCase();
  }
  return "";
}

function attachmentKind(name, url) {
  const ext = attachmentExt(name, url);
  return /^(png|jpe?g|gif|webp|bmp|svg|avif|heic|heif|ico)$/.test(ext) ? "image" : ATT_KINDS[ext] || "file";
}

//: Facts already known are written at once; a `/media` file's size and day
//: are asked of `/media/meta` once per url (the lightbox's own lookup).
const attachmentMetaCache = new Map();

function attachmentFacts(meta, ext, spec) {
  const day = (iso) => {
    const date = new Date(iso);
    if (!iso || Number.isNaN(date.getTime())) return "";
    const year = date.getFullYear() === new Date().getFullYear() ? undefined : "numeric";
    return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year });
  };
  const write = (size, added) => {
    const parts = [ext ? ext.toUpperCase() : "File", formatFileSize(size), spec.staged ? "attaches on save" : day(added)];
    meta.replaceChildren();
    parts.filter(Boolean).forEach((part, i) => {
      if (i) {
        const dot = document.createElement("span");
        dot.className = "library-file-meta-sep";
        dot.textContent = "·";
        dot.setAttribute("aria-hidden", "true");
        meta.append(dot);
      }
      meta.append(part);
    });
  };
  write(spec.size, spec.added);
  meta.title = "Kind, size and the day it was added";
  const stored = /^\/media\/([^/?#]+)$/.exec(spec.url || "");
  if (!stored || spec.size) return;
  if (!attachmentMetaCache.has(stored[1])) {
    attachmentMetaCache.set(stored[1], apiJson(`/media/meta/${stored[1]}`).catch(() => null));
  }
  attachmentMetaCache.get(stored[1]).then((row) => row && write(row.size, row.created_at));
}

function attachmentCard(spec) {
  const url = spec.url || "";
  const label = spec.name && spec.name !== url ? spec.name : url.split("/").pop();
  const ext = attachmentExt(label, url);
  const kind = attachmentKind(label, url);
  const card = document.createElement("div");
  card.className = "att-card";
  card.dataset.kind = kind;
  if (spec.staged) card.dataset.state = "staged";
  const run = (action) => () => attachmentAction(action, spec, card);

  const open = document.createElement("button");
  open.type = "button";
  open.className = "att-card-open";
  const playable = kind === "audio" || kind === "video";
  const canOpen = !!url;
  open.title = canOpen ? `${playable ? "Play" : "Open"} “${label}”` : `“${label}” attaches when you save`;
  if (!canOpen) open.setAttribute("aria-disabled", "true");
  else open.addEventListener("click", run("open"));
  const tile = document.createElement("span");
  tile.className = "att-card-tile";
  tile.setAttribute("aria-hidden", "true");
  const glyph = document.createElement("i");
  glyph.className = `ph ${attachmentIconClass(url, label) || "ph-file"}`;
  tile.append(glyph);
  if (kind === "image" && url) {
    const img = document.createElement("img");
    img.className = "att-card-thumb";
    img.alt = "";
    img.loading = "lazy";
    img.addEventListener("load", () => tile.classList.add("has-thumb"));
    img.addEventListener("error", () => img.remove());
    Promise.resolve(spec.thumb ? spec.thumb() : mediaSrc(url)).then((src) => (img.src = src), () => img.remove());
    tile.append(img);
  }
  const text = document.createElement("span");
  text.className = "att-card-text";
  const nameEl = document.createElement("span");
  nameEl.className = "att-card-name";
  nameEl.textContent = label;
  nameEl.title = label;
  const meta = document.createElement("span");
  meta.className = "library-file-meta att-card-meta";
  attachmentFacts(meta, ext, spec);
  text.append(nameEl, meta);
  open.append(tile, text);

  //: Grouped: past five rows a menu draws its breaks (DESIGN.md).
  const items = [];
  const add = (action, labelText, title, group, extra = {}) =>
    items.push({ label: labelText, title, group, run: run(action), ...extra });
  const stored = /^\/(?:media|files)\//.test(url) && !spec.staged;
  const editable = !!(spec.textarea || spec.staged || (spec.attachment && spec.onChange));
  if (canOpen) add("open", `ph:${playable ? "play" : "arrow-square-out"} ${playable ? "Play" : "Open"}`, open.title, "open");
  if (stored) add("download", "ph:download-simple Download", `Save “${label}” to this computer`, "open");
  if (spec.textarea || (spec.attachment && spec.onChange)) add("rename", "ph:pencil-simple Rename…", "Change the name this file is shown under", "edit");
  if (stored && !playable) {
    const off = aiIsOff();
    add("describe", "ph:sparkle Describe with AI", off ? `Describing a file needs the local AI. ${AI_OFFLINE_HINT}.` : "Write a short description of this file with the local AI", "edit", { disabled: off });
    add("caption", "ph:text-align-left Edit description…", "Type or change this file's description yourself", "edit");
  }
  if (kind === "image" && url) add("annotate", "ph:pencil-simple Annotate a copy", "Draw on a copy of this picture, saved as a new note", "edit");
  if (stored) add("copy", "ph:link Copy as a link", "Copy the markdown that shows this file in a note or document", "share");
  if (editable) add("remove", "ph:trash Remove", spec.attachment ? `Delete “${label}” from this note` : `Take “${label}” out of this note`, "remove", { danger: true });
  const more = kebabMenu(items, `Actions for “${label}”`);
  more.querySelector("button").classList.add("att-card-more");
  card.append(open, more);
  return card;
}

//: The name every read-only surface already calls (a note's text, a
//: document, the graph's panel, the timeline): the card, with no Rename or
//: Remove, because none of those surfaces is where the file is written down.
function fileCard(name, url, size) {
  return attachmentCard({ name, url, size });
}

// LaTeX escapes that models reach for when they want a symbol (§35H).
//
// Screenshotted: a bullet reading "Jokes $\rightarrow$ Social Skills", with
// the LaTeX printed literally. That is not a markdown gap, the model was
// asked for an arrow and reached for the notation it saw most in training.
// Rendering a whole maths engine for this would be absurd; translating the
// dozen symbols that actually show up costs nothing and covers all of it.
//
// The prompt also asks for plain Unicode, which prevents most of these. This
// is the half that catches the model doing it anyway.
const LATEX_SYMBOLS = {
  rightarrow: "\u2192", to: "\u2192", longrightarrow: "\u27f6", Rightarrow: "\u21d2",
  leftarrow: "\u2190", gets: "\u2190", Leftarrow: "\u21d0",
  leftrightarrow: "\u2194", Leftrightarrow: "\u21d4", uparrow: "\u2191", downarrow: "\u2193",
  times: "\u00d7", div: "\u00f7", pm: "\u00b1", mp: "\u2213", cdot: "\u00b7",
  leq: "\u2264", le: "\u2264", geq: "\u2265", ge: "\u2265",
  neq: "\u2260", ne: "\u2260", approx: "\u2248", equiv: "\u2261", sim: "\u223c",
  ldots: "\u2026", dots: "\u2026", cdots: "\u22ef",
  infty: "\u221e", deg: "\u00b0", bullet: "\u2022", star: "\u2605",
  checkmark: "\u2713", surd: "\u221a", propto: "\u221d", therefore: "\u2234",
  alpha: "\u03b1", beta: "\u03b2", gamma: "\u03b3", delta: "\u03b4",
  lambda: "\u03bb", mu: "\u03bc", pi: "\u03c0", sigma: "\u03c3", omega: "\u03c9",
  Delta: "\u0394", Sigma: "\u03a3", Omega: "\u03a9",
};

//: **Inline maths, `$formula$` on one line** (INBOX 423c). Mirrors the
//: block delimiter's own currency guard (see `mdMathBlockFrom`'s comment):
//: no space just inside either `$` (a genuine `$ x $` is vanishingly rare
//: and a stray space is nearly always somebody's sentence), and the closing
//: `$` may not be immediately followed by a digit or a second `$` (a price
//: range, "$20 and $30", or a `$$…$$` display block's own second dollar).
//: The two lookarounds around the *opening* `$` (`(?<!\$)`, `(?!\$|\s)`) are
//: what keeps this from ever matching inside a `$$…$$` run at all: both
//: dollars of that pair fail one side or the other, so a display block is
//: never mistaken for two stray inline ones. Read by `unlatex` (which
//: decides what survives to be drawn as maths) and by `renderInlineMarkdown`
//: (which actually draws it); the same object so the two can never
//: disagree about what counts.
const INLINE_MATH_RE = /(?<!\$)\$(?!\$|\s)([^$\n]{1,300}?)(?<!\s)\$(?!\$|\d)/g;

function unlatex(text) {
  // The overwhelmingly common case: nothing to do, and not worth two regex
  // passes over every note and every streaming frame to find that out.
  if (!text || (!text.includes("\\") && !text.includes("$"))) return text;
  const swap = (s) =>
    s.replace(/\\([A-Za-z]+)/g, (whole, name) =>
      Object.prototype.hasOwnProperty.call(LATEX_SYMBOLS, name)
        ? LATEX_SYMBOLS[name]
        : whole
    );
  // The old rule, for everything INLINE_MATH_RE does not claim below:
  // inline maths delimiters are dropped only when the span is actually
  // maths *and* everything in it became plain characters.
  //
  // Both halves are load-bearing. Without the first, "cost $5 and $10 today"
  // is a matching span containing no commands, and the dollars vanish, a
  // notebook full of prices is a much more likely thing than a notebook full
  // of LaTeX. Without the second, a span still holding \frac or \sum gets
  // stripped of its delimiters and left as half-translated notation, which is
  // worse than leaving it alone: the user can at least read the source.
  const swapDollarSpans = (s) =>
    s.replace(/\$([^$\n]{1,200})\$/g, (whole, inner) => {
      if (!/\\[A-Za-z]/.test(inner)) return whole; // not maths: currency, prose
      const plain = swap(inner);
      return /\\[A-Za-z]/.test(plain) ? whole : plain;
    });
  //: A span INLINE_MATH_RE claims is carried through byte for byte, dollar
  //: signs and all: `renderInlineMarkdown` draws it as real maths, through
  //: the same TeX-to-MathML renderer the `$$` blocks already use, rather
  //: than this function reducing it to a Unicode stand-in symbol (what used
  //: to happen to `$\alpha$`, and what always happened to `$x$`: it has no
  //: `\command` for the old rule above to even notice). Everything between
  //: two such spans still gets the old rule, which is why this walks the
  //: text in segments instead of running one `.replace` over the whole
  //: string: the old rule's own `$…$` regex is looser than INLINE_MATH_RE
  //: (no spacing or digit guard) and would otherwise re-match and mangle
  //: the very span just carried through.
  INLINE_MATH_RE.lastIndex = 0;
  let out = "";
  let cursor = 0;
  let m;
  while ((m = INLINE_MATH_RE.exec(text))) {
    out += swap(swapDollarSpans(text.slice(cursor, m.index))) + m[0];
    cursor = INLINE_MATH_RE.lastIndex;
  }
  out += swap(swapDollarSpans(text.slice(cursor)));
  return out;
}

// `compact`: skip the actual <img> and show the alt text instead, for a
// label-sized surface (a link chip, a document sidebar button) where a
// note's own image markdown would otherwise cram a thumbnail into a spot
// sized for a line of text. The note card's own body always gets the real
// image; everywhere smaller gets the same treatment `notePreviewText`
// already gives one to a plain-text preview.
//
// `options`: appendInline's five differences from the note-card grammar:
//   - `dismissible` (default true): render an image with the note-card
//     delete/lightbox chrome. appendInline's callers (chat, documents, table
//     cells) pass false: there is no note markdown line for a "remove this
//     image" click to edit there, so they get a plain <img>.
//   - `autolinkBareUrls` (default false): turn a plain `https://…` run into
//     a real link. Off for note cards (unchanged), on for appendInline.
//   - `underscoreSyntax` (default false): also recognize `__bold__`/
//     `_italic_` and bare-URL autolinking, using INLINE_MD_LEGACY instead of
//     INLINE_MD: see that constant's comment for why this is a second
//     literal pattern rather than a superset with the extra alternatives
//     suppressed after matching.
//   - `strikeTag` (default "s"): appendInline's callers always used <del>,
//     not the note-card renderer's <s>; style.css has separate rules for
//     `.entry-content s` vs `.answer/.bubble-answer/.dash-body del`.
//   - `applyLatex` (default true): appendInline never ran unlatex() on its
//     text, so it stays off for that mode to keep behaviour unchanged.
// The allow-list for anything a note's own text can turn into an href:
// web links, mail, this app's own paths and in-page anchors. Everything
// else (javascript:, data:, vbscript:, file:) becomes a dead link rather
// than a live one. Kept beside the renderer that needs it.
function safeHref(url) {
  const value = String(url || "").trim();
  // As a browser reads it: controls dropped (audit 1028 D14).
  const probe = value.replace(/[\0- \x7f]/g, "");
  if (/^(https?:|mailto:|tel:)/i.test(probe)) return value;
  if (/^[/#?.]/.test(probe) || !/^[a-z][a-z0-9+.-]*:/i.test(probe)) return value;
  return "#";
}

//: **CommonMark's angle-bracket autolink, `<https://example.com>`.** INBOX
//: 81: "Web search results in the Sources dropdown: links rendered as
//: Markdown links", with a screenshot of a model's table showing the raw
//: `<https://...>` text. Neither inline pattern here has ever matched that
//: form, so it fell through to plain prose and the reader saw the brackets.
//:
//: Rewritten to `[url](url)` *before* matching rather than added as another
//: alternative to `INLINE_MD`. That pattern's capture groups are addressed by
//: number in the renderer below, and its own comment records a bug where two
//: indices were off by two and every image in the app rendered "undefined":
//: adding a group in the middle of it is exactly how that happens again. A
//: pre-pass cannot move an index.
//:
//: Only http and https, which is the same allowlist `isRenderableUrl`
//: applies afterwards; the point of the check here is to leave anything else
//: (an HTML tag, `<3`, a generic like `Array<T>`) exactly as it was.
function expandAngleAutolinks(text) {
  return String(text || "").replace(
    /<(https?:\/\/[^\s<>]{1,500})>/g,
    (whole, url) => `[${url}](${url})`,
  );
}

//: A bare app address becomes `[Note 12](address)` before matching, as the
//: angle form above does (note text never autolinked a bare URL, and an app
//: link is the one a person pastes to click). Not inside a link, a code span
//: or angle brackets.
function linkAppAddresses(text) {
  return String(text || "").replace(/https?:\/\/[^\s<>()[\]`]*[^\s<>()[\]`.,;:!?]/g, (url, at, whole) => {
    const hash = appAddressHash(url);
    return hash && !/[([`<]/.test(whole.charAt(at - 1)) ? `[${appAddressLabel(hash).replace(/[[\]\n]/g, " ")}](${url})` : url;
  });
}

//: What a bare URL is shown as: the host without its `www.`, then the path
//: shortened to its last meaningful segment, so
//: `https://www.goodreads.com/series/319859-he-who-fights-with-monsters`
//: reads "goodreads.com / …he-who-fights-with-monsters". The query string and
//: fragment are dropped from the label (never from the link): they are
//: tracking and position, not identity. A string the URL parser refuses comes
//: back as it was, so a malformed address is still shown rather than hidden.
const READABLE_URL_SEGMENT = 40;

function readableUrl(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  const host = parsed.hostname.replace(/^www\./i, "");
  const segments = parsed.pathname.split("/").filter(Boolean);
  if (!segments.length) return host;
  let last = decodeURIComponent(segments.at(-1));
  if (last.length > READABLE_URL_SEGMENT) last = last.slice(0, READABLE_URL_SEGMENT - 1) + "\u2026";
  //: An ellipsis stands in for the middle of a deep path, so "site / … / page"
  //: still says there was more between them.
  return segments.length > 1 ? `${host} / \u2026 / ${last}` : `${host} / ${last}`;
}

//: **A picture at another address is never asked for** (audit 1029 N7). The
//: page's CSP (`img-src 'self' data: blob:`) refuses it, which read as
//: "deleted" and logged four errors a render. The card says so and links to
//: it instead of building the `<img>`.
//: The blank lines before a picture on its own line are the markdown's, not
//: the note's: kept, they stacked on the box's own margin into a 33px gap
//: under a sketch's caption (dog3-1026 row 15).
function appendPictureBox(element, box) {
  const before = element.lastChild?.lastChild || element.lastChild;
  if (before?.nodeType === Node.TEXT_NODE) before.textContent = before.textContent.trimEnd();
  element.appendChild(box);
}

function isRemoteImage(url) {
  return /^https?:\/\//i.test(url) && !url.startsWith(`${location.origin}/`);
}

function remoteImageNote(url) {
  const note = document.createElement("span");
  note.className = "entry-image-note";
  note.title = "This notebook works offline, so pictures from the web are not loaded.";
  const open = document.createElement("a");
  open.href = safeHref(url);
  open.target = "_blank";
  open.rel = "noopener noreferrer";
  open.textContent = "Open link";
  note.append("Remote image not loaded. ", open);
  return note;
}

//: A link label worth reading as inline markdown: it holds emphasis or code.
const LINK_LABEL_MARKUP = /[*_`~=]/;

function renderInlineMarkdown(element, text, terms, compact = false, options = {}) {
  const { underscoreSyntax = false, applyLatex = true } = options;
  // appendInline never cleared `element`, it only ever appended into a
  // freshly created element, except the task-list-checkbox case, which
  // appends a <input type=checkbox> *before* calling appendInline on the
  // rest of the item text. A `replaceChildren()` here would delete that
  // checkbox out from under it, so the note-card renderer's clear-first
  // behaviour is kept only for its own (non-legacy) callers.
  if (!underscoreSyntax) element.replaceChildren();
  if (applyLatex) text = unlatex(text);
  text = expandAngleAutolinks(text);
  if (!compact) text = linkAppAddresses(text);
  //: **Inline maths, cut out before the `**bold**`/`` `code` ``/link
  //: grammar below ever sees it** (INBOX 423c). A span INLINE_MATH_RE
  //: claims (its own comment has the exact rule) is drawn by the same
  //: TeX-to-MathML renderer the `$$` blocks use, one run of ordinary
  //: grammar-matching per gap between formulas rather than one run over the
  //: whole string, so `**bold**` either side of a formula still matches.
  //: A formula *inside* `**bold $x$ text**` does not come out bold: that
  //: would need maths as a token of the grammar below rather than a cut
  //: made before it runs, and nothing reported here asked for that.
  INLINE_MATH_RE.lastIndex = 0;
  let mathCursor = 0;
  let mathMatch;
  let sawMath = false;
  while ((mathMatch = INLINE_MATH_RE.exec(text))) {
    sawMath = true;
    if (mathMatch.index > mathCursor) {
      appendInlineRun(element, text.slice(mathCursor, mathMatch.index), terms, compact, options);
    }
    element.appendChild(mdInlineMathElement(mathMatch[1].trim()));
    mathCursor = INLINE_MATH_RE.lastIndex;
  }
  if (sawMath) {
    if (mathCursor < text.length) appendInlineRun(element, text.slice(mathCursor), terms, compact, options);
    return;
  }
  appendInlineRun(element, text, terms, compact, options);
}

//: The `**bold**`/`` `code` ``/link/image/highlight/bare-url grammar,
//: over one run of text `renderInlineMarkdown` has already established
//: holds no inline maths. Never clears `element`: a run is one piece of a
//: larger call that may already have appended earlier runs and maths nodes.
function appendInlineRun(element, text, terms, compact, options) {
  const { dismissible = true, autolinkBareUrls = false, underscoreSyntax = false, strikeTag = "s" } = options;
  const pattern = new RegExp((underscoreSyntax ? INLINE_MD_LEGACY : INLINE_MD).source, "g");
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      const chunk = text.slice(cursor, match.index);
      // Same reasoning as the clear-first skip above: appendInline appended
      // plain prose as a bare text node, never wrapped in a <span> (it never
      // had search terms to mark). Keeping that distinction means neither
      // mode's DOM shape moves for its own callers.
      if (underscoreSyntax) {
        appendPlainText(element, chunk);
      } else {
        const before = document.createElement("span");
        highlightIconsInto(before, chunk, terms);
        element.appendChild(before);
      }
    }
    let code, bold, strike, markColour, mark, inkColour, ink, italic, imageAlt, imageUrl, linkText, linkUrl, bareUrl, runSpec, runText;
    if (underscoreSyntax) {
      let boldStar, boldUnderscore, italicStar, italicUnderscore;
      [
        , code, boldStar, boldUnderscore, strike, markColour, mark, inkColour, ink, italicStar, italicUnderscore,
        imageAlt, imageUrl, linkText, linkUrl, bareUrl, runSpec, runText,
      ] = match;
      bold = boldStar ?? boldUnderscore;
      italic = italicStar ?? italicUnderscore;
    } else {
      [, code, bold, strike, markColour, mark, inkColour, ink, italic, imageAlt, imageUrl, linkText, linkUrl, runSpec, runText] = match;
    }
    // Images and links are their own element kinds, not a wrap-in-a-tag like
    // the four above: built and appended directly rather than falling
    // through to the generic `tag`/`node` shape below, since neither one
    // takes searched-term highlighting inside it (an <img> has no text to
    // highlight, and a link's own text isn't split into marks any more than
    // a code span's is).
    if (imageUrl !== undefined) {
      if (compact) {
        element.appendChild(document.createTextNode(imageAlt || "Image"));
      } else if (isRemoteImage(imageUrl)) {
        appendPictureBox(element, remoteImageNote(imageUrl));
      } else if (isRenderableUrl(imageUrl)) {
        if (!dismissible) {
          const img = document.createElement("img");
          img.src = mediaSrc(imageUrl);
          img.alt = imageAlt || "";
          img.className = "entry-inline-image";
          img.loading = "lazy";
          element.appendChild(img);
          cursor = pattern.lastIndex;
          continue;
        }
        const wrapper = document.createElement("span");
        wrapper.className = "thumb-wrap";
        const img = document.createElement("img");
        img.src = mediaSrc(imageUrl);
        img.alt = imageAlt || "";
        img.className = "attachment-thumb";
        img.loading = "lazy";
        img.style.cursor = "zoom-in";
        img.addEventListener("click", (e) => {
          e.stopPropagation();
          openLightbox([{ filename: imageAlt || "Image", getUrl: () => mediaSrc(imageUrl) }], 0);
        });
        const dismissBtn = document.createElement("span");
        dismissBtn.className = "unlink";
        dismissBtn.title = "Remove image from note";
        setLabel(dismissBtn, "ph:x"); // raw "×" glyph vs Phosphor icon font mismatch mis-centers the icon
        // `match` is one `let` reused by every pass of the while loop and is
        // `null` by the time anyone clicks, so each button captures its own
        // text here ("the remove button doesn't work").
        const originalText = match[0];
        dismissBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          wrapper.dispatchEvent(new CustomEvent("remove-inline-image", {
            bubbles: true,
            detail: { originalText }
          }));
        });
        makeUnlinkAccessible(dismissBtn);
        wrapper.appendChild(img);
        wrapper.appendChild(dismissBtn);
        // Asked for directly: a deleted image left a broken-image glyph in
        // the note that referenced it, a closable "deleted" box instead.
        // Only dismisses the placeholder from this render; the note's own
        // markdown line is left alone; editing it back out is a further,
        // separate feature.
        img.addEventListener("error", () => {
          const placeholder = document.createElement("span");
          placeholder.className = "entry-image-note";
          placeholder.append(document.createTextNode(`${imageAlt || "Image"} deleted`));
          const dismiss = document.createElement("span");
          dismiss.className = "unlink";
          dismiss.title = "Dismiss";
          setLabel(dismiss, "ph:x"); // raw "×" glyph vs Phosphor icon font mismatch mis-centers the icon
          dismiss.addEventListener("click", (e) => { e.stopPropagation(); placeholder.remove(); });
          makeUnlinkAccessible(dismiss);
          placeholder.appendChild(dismiss);
          wrapper.replaceWith(placeholder);
        });
        appendPictureBox(element, wrapper);
      } else {
        element.appendChild(document.createTextNode(match[0]));
      }
      cursor = pattern.lastIndex;
      continue;
    }
    if (linkUrl !== undefined) {
      if (isRenderableUrl(linkUrl)) {
        const iconClass = attachmentIconClass(linkUrl);
        if (iconClass) {
          // **A file, not a link: this fixes a dead end.** A plain
          // `<a href="/media/x.pdf">` navigates without the `X-Auth-Token`
          // header, so the browser left the app for the unlock guard's 401
          // JSON, with no way back in the desktop shell. The lightbox already
          // reads these files (`/media/text`); a note's own files now go to
          // it. `compact` (a preview row, a chip) has room for a line, not a card.
          element.appendChild(
            compact ? fileChip(linkText, linkUrl) : fileCard(linkText, linkUrl)
          );
        } else {
          const a = document.createElement("a");
          // Only schemes a note may point at. A `[x](javascript:...)` link
          // would otherwise be a click-to-run script in a note that came
          // from an import or a shared file; the CSP blocks it today, and
          // this is the second lock in case the CSP is ever loosened.
          //: An address of this app (INBOX 483) is the hash alone, so a click
          //: opens the view in this window; other web links open a new tab.
          const linkTarget = appAddressHash(linkUrl) || linkUrl;
          a.href = safeHref(linkTarget);
          if (linkTarget === linkUrl && /^https?:\/\//i.test(linkUrl)) {
            a.target = "_blank";
            a.rel = "noopener noreferrer";
          }
          //: `[https://x.com/a/b](https://x.com/a/b)` is how a model writes a
          //: bare URL when it has been told to use markdown: the same address
          //: twice, and the same wall of slug on screen. Shown as the bare
          //: form is (see `readableUrl` below); a link whose words differ from
          //: its address is a real label and is left alone.
          const labelIsTheUrl = !linkText.trim() || linkText.trim() === linkUrl.trim();
          if (labelIsTheUrl) a.title = linkUrl;
          if (!labelIsTheUrl && LINK_LABEL_MARKUP.test(linkText)) {
            //: `[**Title**](#/note/3)`: the composer's own link for a bold
            //: title (owner, 2026-10-27: the weekly digest showed the
            //: asterisks). The label is read as inline text again, so bold,
            //: italic and code draw inside the link; no bare-URL autolink
            //: (no link inside a link) and compact (no picture inside one).
            appendInlineRun(a, linkText, terms, true, { ...options, autolinkBareUrls: false, dismissible: false });
          } else {
            highlightInto(a, labelIsTheUrl ? (/^https?:/i.test(linkUrl) ? readableUrl(linkUrl) : appAddressLabel(linkTarget)) : linkText, terms);
          }
          element.appendChild(a);
        }
      } else {
        element.appendChild(document.createTextNode(match[0]));
      }
      cursor = pattern.lastIndex;
      continue;
    }
    if (bareUrl !== undefined) {
      if (autolinkBareUrls) {
        const a = document.createElement("a");
        a.href = bareUrl;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        //: The address is the tooltip; the words are the site and the path
        //: (`readableUrl`), since nobody reads a hundred-character slug.
        a.title = bareUrl;
        highlightInto(a, readableUrl(bareUrl), terms);
        element.appendChild(a);
      } else {
        const span = document.createElement("span");
        highlightInto(span, bareUrl, terms);
        element.appendChild(span);
      }
      cursor = pattern.lastIndex;
      continue;
    }
    //: A run (`{{size=24 ink=red|words}}`, documents.js `mdRunNode`): its words
    //: are read as inline text again, so bold or a link inside it still draws.
    //: Drawn plain until the Library's scripts are in (the grammar is here so
    //: a preview and a search read the words either way).
    if (runText !== undefined) {
      const [node, host] = typeof mdRunNode === "function" ? mdRunNode(runSpec) : Array(2).fill(document.createElement("span"));
      appendInlineRun(host, runText, terms, compact, options);
      element.appendChild(node);
      cursor = pattern.lastIndex;
      continue;
    }
    const tag = code
      ? "code"
      : bold
        ? "strong"
        : strike
          ? strikeTag
          : mark
            ? "mark"
            : ink
              ? "span"
              : "em";
    const node = document.createElement(tag);
    // Distinguishes a `==highlight==` from highlightInto's own <mark> below
    // (used for search-term matches), same tag, different meaning, so they
    // need different styling or a highlighted note reads as "this matched
    // your search" with no search active.
    // `++red|text++`, a foreground colour, the counterpart to the highlight's
    // background one. The colour is part of a class name, never an inline
    // style: this app's CSP rejects inline styles outright (a whole batch of
    // them was found doing nothing once), and a closed allowlist means every
    // colour that can be typed has a theme-aware rule written for it.
    if (ink) node.className = `text-ink text-ink-${inkColour}`;
    if (mark) {
      // `==text==` is the plain (yellow) highlight; `==green|text==` picks one
      // of a small named set. An allowlist baked into the pattern itself, not
      // a free-form colour: the value lands in a class name, and every colour
      // that can appear here therefore has a stylesheet rule written for it
      // (05-sidebars-themes.css) that is theme-aware in both light and dark.
      node.className = markColour
        ? `text-highlight text-highlight-${markColour}`
        : "text-highlight";
    }
    // A code span is literal by definition, so it is never searched-highlighted
    // into pieces: the rest still is, or filtering would stop marking any
    // word that happened to sit inside emphasis.
    if (code) node.textContent = code;
    else highlightInto(node, bold || strike || mark || ink || italic, terms);
    element.appendChild(node);
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) {
    const rest = text.slice(cursor);
    if (underscoreSyntax) {
      appendPlainText(element, rest);
    } else {
      const restSpan = document.createElement("span");
      highlightIconsInto(restSpan, rest, terms);
      element.appendChild(restSpan);
    }
  }
}

// Inline formatting: **bold**/__bold__, *italic*/_italic_, `code`, ~~strike~~,
// ==highlight==, [text](http…url), images, and bare http(s) URLs. Built with textContent
// only: note/answer text can never inject markup. Was its own ~90-line
// hand-rolled parser with its own `isRenderableUrl` gate call; now a thin
// wrapper over renderInlineMarkdown (ROADMAP.md §0/§2): see that function's
// `options` comment for exactly which behaviours these five overrides
// reproduce and why each one is there.
function appendInline(parent, text) {
  renderInlineMarkdown(parent, text, [], false, {
    dismissible: false,
    autolinkBareUrls: true,
    underscoreSyntax: true,
    // `.answer del`/`.bubble-answer del`/`.dash-body del` (style.css) style
    // this tag specifically: appendInline's own callers always used <del>,
    // not the note-card renderer's <s>, and the CSS was written for that.
    strikeTag: "del",
    applyLatex: false,
  });
}

// Mirrors manager.extract_title's own rule (the first non-blank line, and
// only that line) so the body shown under a title never repeats it, called
// only when the backend has already said this note has a title, so this
// never has to decide on its own whether a line "looks like" a heading.
function bodyWithoutTitleLine(content) {
  const lines = stripFrontmatter(content).split("\n");
  let i = 0;
  while (i < lines.length && lines[i].trim() === "") i++;
  if (i >= lines.length) return content;
  lines.splice(i, 1);
  //: Every blank line after the title, not one: a second left the clamped
  //: preview with nothing but its "..." (INBOX 458).
  while (lines[i] !== undefined && lines[i].trim() === "") lines.splice(i, 1);
  return lines.join("\n");
}

// The note a [[wiki link]] names, or null.
//
// One resolver, because there were two: renderNoteText matched notes by the
// opening words and layerDocWikiLinks matched documents by exact title, so the
// same [[name]] meant different things depending on which pane rendered it.
// Notes are matched first and by prefix (that is what the "[[" menu inserts:
// a note's opening words, `editorLinkMatches`); documents fall back to an exact,
// case-insensitive title. Private notes are never a target: they cannot be
// linked, and resolving to one would leak that it exists.
//: **The lowercased forms a wiki lookup compares against, computed once per
//: note rather than once per note per link.**
//:
//: `resolveWikiTarget` runs for every `[[link]]` that renders, and it used to
//: lowercase every note's whole body, twice (once plain, once with the
//: heading marker stripped by a regex), on every one of those calls. At four
//: thousand notes averaging 594 bytes that is up to 4.8 MB of string work per
//: link, and a note list draws sixty cards at a time. Profiled over fourteen
//: seconds of ordinary use, `opening` and `openingTitle` and their caller
//: came to 267 ms of self time, more than the dashboard's p5 sketch.
//:
//: Two things fix it and neither can go stale. The forms are cached **on the
//: entry, keyed by the content string they were derived from**, so an edit
//: invalidates them by construction: no generation counter to forget to bump,
//: no cache to clear when `allEntries` is replaced. And only the first
//: `WIKI_PREFIX_MAX` characters are lowercased, because every comparison here
//: is `startsWith` against a needle that is a title. A needle longer than that
//: falls back to the full string, so the bound is an optimisation and never a
//: behaviour.
const WIKI_PREFIX_MAX = 300;

function wikiForms(entry, needleLength) {
  const content = entry.content || "";
  if (needleLength > WIKI_PREFIX_MAX) {
    const full = content.toLowerCase();
    return { opening: full, title: full.replace(/^#{1,6}[ \t]*/, "") };
  }
  if (entry._wikiSrc !== content) {
    const head = content.slice(0, WIKI_PREFIX_MAX).toLowerCase();
    entry._wikiSrc = content;
    entry._wikiOpening = head;
    entry._wikiTitle = head.replace(/^#{1,6}[ \t]*/, "");
  }
  return { opening: entry._wikiOpening, title: entry._wikiTitle };
}

//: The same trick for the imported-vault path: a file stem is derived from
//: `source_path` with a split, a pop and a regex, which was also being redone
//: per link per note.
function wikiStem(entry) {
  const path = entry.source_path || "";
  if (entry._wikiStemSrc !== path) {
    entry._wikiStemSrc = path;
    entry._wikiStem = path.split("/").pop().replace(/\.(md|markdown)$/i, "").toLowerCase();
  }
  return entry._wikiStem;
}

//: **A board or a map named by its id**, the form the "/" menu and the
//: board's own "Add to a note" write: `board:12|House jobs`, or `map:12|The
//: house`.
//:
//: Why an id rather than the title every other `[[link]]` uses (INBOX 309,
//: the owner: "there is also no way to attach a whiteboard or mindmap to a
//: note as like an object in the notes"). A title-addressed object breaks the
//: moment the board is renamed, and it breaks *silently*: a renamed board and
//: a deleted one look identical to the resolver, so the note either points at
//: nothing or tombstones a board that is still there. A board is an `Entry`,
//: so its id is stable, and renaming it now leaves every note that carries it
//: pointing at the same board.
//:
//: **The title travels with the id anyway**, for two reasons that are not
//: decoration. It is what a tombstone says when the board really is gone
//: ("Old plan" beats "board 12"), and it is what the backend's own reference
//: scan matches on: `_reference_rows` in routes_entries.py finds a board's
//: references with a LIKE over note content for the board's label, so a note
//: carrying the title still counts towards the card's "on 1 board" chip with
//: no backend change at all.
//:
//: `whiteboard` and `mindmap` are accepted as spellings of the same two
//: things because somebody typing this by hand will write one of them.
const BOARD_REF_PATTERN = /^\s*(board|whiteboard|map|mindmap)\s*:\s*(\d{1,9})\s*(?:\|\s*([^|]*))?$/i;

function boardEmbedRef(name) {
  const match = BOARD_REF_PATTERN.exec(String(name || ""));
  if (!match) return null;
  return {
    id: Number(match[2]),
    title: (match[3] || "").trim(),
    //: What the writer *said* it was, used only until the board itself is
    //: found: the board's own `type` is the truth, and a map turned into a
    //: whiteboard after the note was written should draw as a whiteboard.
    map: /map/i.test(match[1]),
  };
}

//: The board a reference points at, or null when it is really gone.
//:
//: Two lookups, in this order. The id is exact and is what the writer meant.
//: The title is the fallback for the one case an id cannot survive: a board
//: exported and imported again, or restored from a backup, keeps its name and
//: takes a new id. Trying it before calling anything missing is the difference
//: between a tombstone that is right and one that is merely early.
function boardEmbedTarget(ref) {
  if (!ref || !ref.id) return null;
  const byId = mapBoardById(ref.id);
  if (byId) return byId;
  if (!ref.title || typeof mapBoardTitled !== "function") return null;
  return mapBoardTitled(ref.title.toLowerCase());
}

function resolveWikiTarget(name) {
  //: An id-addressed board is answered before anything is lower-cased or
  //: scanned: it names exactly one thing, and the notes-then-documents walk
  //: below could only ever find something else called "board:12".
  const ref = boardEmbedRef(name);
  if (ref) {
    const board = boardEmbedTarget(ref);
    return board ? { kind: "board", entry: board } : null;
  }
  //: `[[Target|Shown]]` finds the note by its target (`wikiLinkTarget`).
  const needle = String(wikiLinkTarget(name) || "").trim().toLowerCase();
  if (!needle) return null;
  const entries = typeof allEntries !== "undefined" ? allEntries : [];
  //: **A vault's links name the file.** An imported note carries the path it
  //: came from, and Obsidian writes `[[Roadmap]]` for `Projects/Roadmap.md`, 
  //: so this is tried first, and matched exactly: a file called "Index"
  //: should not lose to a note that merely opens with the word "index". Same
  //: rule as `find_by_wiki_name` in entry/manager.py, which is what makes the
  //: link the backend stores and the link this pane draws point at one note.
  const vaultNote = entries.find(
    (e) => !e.is_private && e.source_path && wikiStem(e) === needle
  );
  if (vaultNote) return { kind: "note", entry: vaultNote };
  //: **A board is a link target, and it is not a note.** MINDMAP_PLAN.md §5
  //: item 12 asks for a map chip in note bodies, and the `@`/`[[` picker in
  //: editor.js has offered boards as targets since it was written, so the
  //: link could already be *typed* and resolved to something. What it resolved
  //: to was `{kind: "note"}`, and the click called `flashEntry`, which scrolls
  //: the Notes tab to a row that is not there: a board is filtered out of
  //: every note list in the app. So the link worked, looked like a note, and
  //: went nowhere.
  //:
  //: Matched on the board's *title* with the `# ` stripped, and by prefix on
  //: the raw content underneath, because both forms exist in real notes: the
  //: picker used to insert the whole first line (`[[# My map]]`) and now
  //: inserts the title (`[[My map]]`).
  //:
  //: **Read from the board index, not from `allEntries`.** `GET /entries` is
  //: the notes list and no longer carries boards at all (see its `boards`
  //: parameter, a map called "test" was showing up as a note, reported), so
  //: this used to resolve against a list that will not have the board in it.
  //: `mapBoardIndexCache` is `/whiteboard/boards`, which is the list of
  //: boards by definition, and it is already loaded for the map chips.
  const board = mapBoardTitled(needle);
  if (board) return { kind: "board", entry: board };
  //: **Two ways a note's opening words can be written, and both resolve.** The
  //: `[[` picker inserts the note's first line *verbatim*, `# ` and all, so
  //: matching the content by prefix is what makes `[[# Girl with bell]]`
  //: resolve. Anybody typing a link by hand writes the title they can see,
  //: `[[Girl with bell]]`, and that matched nothing at all: the note's content
  //: starts with the hash, so the prefix test failed on the first character.
  //: Reported by the agent that built the document embeds, which had to avoid
  //: the shape in its own fixture.
  //:
  //: The second comparison strips a leading heading marker from the *content*
  //: rather than adding one to the needle, because the marker is one to six
  //: hashes and any amount of space, and the content is where that is known.
  //: One pass, not a `filter` into a four thousand entry array followed by
  //: two `find`s over it. The plain-opening match still wins over the
  //: marker-stripped one, which is what the two passes were for: it is
  //: remembered rather than searched for twice.
  let note = null;
  let titleMatch = null;
  for (const entry of entries) {
    if (entry.is_private || entry.is_board) continue;
    const forms = wikiForms(entry, needle.length);
    if (forms.opening.startsWith(needle)) {
      note = entry;
      break;
    }
    if (!titleMatch && forms.title.startsWith(needle)) titleMatch = entry;
  }
  note = note || titleMatch;
  if (note) return { kind: "note", entry: note };
  //: **The document list the documents editor holds, when this one is
  //: empty.** `editorDocumentCache` is filled only once the `[[` picker has
  //: been opened, so until then every `![[A document]]` in the Read view said
  //: "Nothing called A document yet" while the Live view of the same line,
  //: which resolves through documents.js's own `docs`, drew it: two views of
  //: one line disagreeing (found by `scratchpad/ui-sweeps/blockbar.js`).
  const cached = typeof editorDocumentCache !== "undefined" && editorDocumentCache && editorDocumentCache.length
    ? editorDocumentCache
    : null;
  const documents = cached || (typeof docs !== "undefined" && Array.isArray(docs) ? docs : null);
  const docList = documents || [];
  const doc =
    docList.find((d) => (d.title || "").trim().toLowerCase() === needle) ||
    //: Reported directly: "still cant open note links from the document
    //: editor", on a link whose visible text ended mid-word ("...and
    //: progr"). Exact match only fails both plausible causes of that: a
    //: shorter string was written into the `[[...]]` than the document's
    //: current title (however that happened), or the document was
    //: retitled after the link was made. A prefix match is the same
    //: fallback `note` above already gets for exactly the same reason,
    //: and a link that is a genuine prefix of a longer title is a much
    //: likelier accident than two documents sharing one.
    docList.find((d) => (d.title || "").trim().toLowerCase().startsWith(needle));
  if (doc) return { kind: "document", doc };
  return null;
}

// A note card's text: block constructs first, then the inline pass.
//
// Notes deliberately do not go through renderMarkdown, this pass keeps
// search-term highlighting, which that renderer has no concept of. So the two
// block constructs the "/" menu can insert are handled here explicitly and
// everything else falls through to exactly the inline rendering this function
// always did. When a note contains neither, the DOM produced is identical to
// before, which is why the fall-through appends to `element` directly rather
// than wrapping runs in a container.
function renderNoteText(element, text, terms, prose = (s) => s) {
  element.replaceChildren();
  const lines = String(text ?? "").replace(/\r\n/g, "\n").split("\n");
  let buffer = [];
  const flush = () => {
    if (!buffer.length) return;
    renderNoteInline(element, prose(buffer.join("\n")), terms);
    buffer = [];
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    const embedded = line.match(/^\s*!\[\[([^[\]]{1,120})\]\]\s*$/);
    if (embedded) {
      flush();
      element.appendChild(mdEmbedElement(embedded[1].trim(), 0));
      i++;
      continue;
    }

    //: The structural blocks the "/" menu writes (INBOX 421 b: they had to
    //: work "in documents and notes"), through the same builders the page
    //: renderer uses. A column is rendered by this function, so it keeps the
    //: card's search highlighting.
    const columns = mdColumnsFrom(lines, i);
    if (columns) {
      flush();
      element.appendChild(mdColumnsElement(columns.columns, (host, body) => renderNoteText(host, body, terms, prose)));
      i = columns.end;
      continue;
    }
    //: **A table or a code fence draws as it does everywhere else** (audit
    //: 1029 N8: the card showed `| a | b |` and the fence's backticks as
    //: text). Search terms are not marked inside the block.
    const blockEnd = mdBlockEnd(lines, i);
    if (blockEnd) {
      flush();
      const box = document.createElement("div");
      box.className = "entry-md-block";
      renderMarkdown(box, lines.slice(i, blockEnd).join("\n"));
      element.appendChild(box);
      i = blockEnd;
      continue;
    }
    const maths = mdMathBlockFrom(lines, i);
    if (maths) {
      flush();
      element.appendChild(mdMathElement(maths.tex));
      i = maths.end;
      continue;
    }
    const rule = mdDividerKind(line);
    if (rule) {
      flush();
      element.appendChild(mdRuleElement(rule));
      i++;
      continue;
    }
    //: A card's headings are not elements to jump to (the card is one
    //: paragraph of text), so its contents block is the outline itself: the
    //: note's headings, indented by level, as a list to read.
    if (MD_TOC_LINE.test(line)) {
      flush();
      const toc = mdTocElement();
      const list = toc.querySelector(".md-toc-list");
      const entries = mdTocEntries(lines.join("\n"));
      const top = entries.length ? Math.min(...entries.map((e) => e.level)) : 1;
      for (const entry of entries) {
        const item = document.createElement("li");
        item.className = `md-toc-item md-toc-depth-${Math.min(3, entry.level - top)}`;
        renderInlineMarkdown(item, entry.text, terms);
        list.appendChild(item);
      }
      if (!entries.length) {
        const empty = document.createElement("li");
        empty.className = "md-toc-empty";
        empty.textContent = "Headings you add appear here.";
        list.appendChild(empty);
      }
      element.appendChild(toc);
      i++;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quoted = [];
      let j = i;
      while (j < lines.length && /^\s*>\s?/.test(lines[j])) {
        quoted.push(lines[j].replace(/^\s*>\s?/, ""));
        j++;
      }
      const box = mdCalloutElement(quoted, 0);
      if (box) {
        flush();
        element.appendChild(box);
        i = j;
        continue;
      }
      // An ordinary blockquote, not a callout: leave it to the inline pass
      // exactly as it was written, rather than eating the "> " markers.
    }

    //: **A task reads as a task** (qa-1005): "- [x] Beta invite list" was the
    //: card's own text, dash and brackets included, where the note page and a
    //: document draw the same line as a box (`.md-task`, navigation.js).
    //: Inline, so the card stays one paragraph and its clamp and highlighting
    //: work as before; the line breaks either side stay in the text, and the
    //: empty buffer entry is the break after it (`flush` joins with "\n").
    const task = line.match(/^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/);
    if (task) {
      flush();
      if (element.childNodes.length) element.append("\n");
      const item = document.createElement("span");
      item.className = "entry-task";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.disabled = true;
      box.checked = task[1].toLowerCase() === "x";
      //: axe `label` (critical, 20 boxes): the box sat beside its words with
      //: no name of its own. The state comes first so a screen reader says it
      //: before the sentence, and the words are the task with its markdown
      //: marks taken off, as the card draws them.
      box.setAttribute("aria-label", `${box.checked ? "Done" : "To do"}: ${task[2].replace(/[*_`~]|\[\[|\]\]/g, "").trim()}`);
      //: A disabled control says why (vibecheck, "muted disabled"): the card is
      //: a preview, and a note's tasks are ticked on its own page.
      box.title = "Open the note to tick this off";
      item.appendChild(box);
      renderNoteInline(item, task[2], terms);
      element.appendChild(item);
      buffer.push("");
      i++;
      continue;
    }

    buffer.push(line);
    i++;
  }
  flush();
}

// The inline half: [[wiki links]], emphasis, and search-term highlighting.
// Appends to `parent`; does not clear it.
function renderNoteInline(element, text, terms) {
  const pattern = /\[\[([^[\]]{1,120})\]\]/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      const span = document.createElement("span");
      renderInlineMarkdown(span, text.slice(cursor, match.index), terms);
      element.appendChild(span);
    }
    const name = match[1].trim();
    //: **A link that names a map draws as a map chip** (MINDMAP_PLAN.md §5
    //: item 12: "note bodies"). Resolved here rather than on click, which is
    //: what every other kind still does, because the *shape* of the control
    //: depends on the answer: a chip carries the map's icon and node count,
    //: and neither can be decided after the element is already on screen.
    //: One `find` over `allEntries` per wiki link, on a list that is already
    //: in memory: the same lookup the click handler was doing anyway.
    const mapTarget = resolveWikiTarget(name);
    if (mapTarget && mapTarget.kind === "board") {
      const board = mapBoardById(mapTarget.entry.id) || {
        id: mapTarget.entry.id,
        title: name,
        type: "map",
      };
      element.appendChild(mapChip(board));
      cursor = pattern.lastIndex;
      continue;
    }
    const link = document.createElement("button");
    link.type = "button";
    link.className = "wiki-link";
    const label = wikiLinkLabel(name);
    link.textContent = label;
    link.title = `Go to the note starting "${label}"`;
    link.addEventListener("click", (event) => {
      event.stopPropagation();
      const target = resolveWikiTarget(name);
      if (target && target.kind === "note") flashEntry(target.entry.id);
      else if (target && target.kind === "board") openWhiteboardBoard(target.entry.id);
      else if (target && target.kind === "document") openDocument(target.doc.id);
      // Nothing by that name yet, offer to make it rather than dead-ending.
      // A link you typed on purpose is the clearest possible statement that
      // the thing should exist; making the user go and create it by hand, then
      // come back, is the friction this removes.
      else offerToCreateWikiTarget(name);
    });
    element.appendChild(link);
    //: A link to nothing says so and offers the note (audit 1029 N22).
    if (!mapTarget && wikiLinkTarget(name).trim()) {
      element.appendChild(chip("Create", "", (event) => { event.stopPropagation(); offerToCreateWikiTarget(name); }));
    }
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) {
    const span = document.createElement("span");
    renderInlineMarkdown(span, text.slice(cursor), terms);
    element.appendChild(span);
  }
}

//: `terms` is "the words to highlight", and **every caller that has nothing to
//: highlight passes something falsy rather than `[]`**, `chatSourcesPanel`
//: passes a literal `null`, which is what a snippet with no search behind it
//: honestly is. This read `terms.length` directly and threw
//: `Cannot read properties of null (reading 'length')`.
//:
//: The throw is worth recording because of where it landed rather than what it
//: was. `renderInlineMarkdown` is called while a saved conversation's Sources
//: panel is being built, which happens inside `openConversation`, so the
//: exception aborted the rest of that function, including the
//: `loadConversationList()` at its end that repaints the sidebar. Reported as
//: "I clicked on other chat conversations in the chat sidebar but the
//: conversations didnt visibly select in the sidebar": the click worked, the
//: fetch worked, and an unrelated null check three calls down stopped the row
//: from ever being marked. Nothing was logged where anyone would look.
//:
//: Normalised here, at the one place that reads it, rather than at each call
//: site: the next caller to pass `null` should not have to know either.
//: **`:ph-name:` is an icon in the reading view** (MINDMAP_PLAN.md decision
//: 46): the token the icon and emoji picker inserts for a Phosphor icon,
//: drawn as the glyph in prose (never inside code: only the plain runs of
//: `appendInlineRun` come here) and left as its words for every other reader.
//: The name is held to Phosphor's own character set, and it is only ever a
//: class: nothing typed reaches the markup.
const INLINE_ICON_RE = /:ph-([a-z0-9-]{1,40}):/g;

function appendPlainText(element, text) {
  let cursor = 0;
  for (const match of text.matchAll(/\[([ xX])\](?!\S)/g)) {
    element.append(text.slice(cursor, match.index));
    const box = document.createElement("input");
    box.type = "checkbox";
    box.className = "md-task-inline";
    box.disabled = true;
    box.checked = match[1] !== " ";
    box.ariaLabel = box.checked ? "Done" : "Not done";
    element.append(box);
    cursor = match.index + 3;
  }
  element.append(text.slice(cursor));
}

function highlightIconsInto(element, text, terms) {
  if (!text.includes(":ph-")) {
    highlightInto(element, text, terms);
    return;
  }
  element.replaceChildren();
  let cursor = 0;
  for (const match of text.matchAll(INLINE_ICON_RE)) {
    if (match.index > cursor) {
      const part = document.createElement("span");
      highlightInto(part, text.slice(cursor, match.index), terms);
      element.appendChild(part);
    }
    const icon = document.createElement("i");
    icon.className = `ph ph-${match[1]} md-inline-icon`;
    icon.setAttribute("role", "img");
    icon.setAttribute("aria-label", match[1].replace(/-/g, " "));
    element.appendChild(icon);
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) {
    const part = document.createElement("span");
    highlightInto(part, text.slice(cursor), terms);
    element.appendChild(part);
  }
}

function highlightInto(element, text, terms) {
  element.replaceChildren();
  if (!terms || !terms.length) {
    element.textContent = text;
    return;
  }
  // One pass, longest terms first so "bread rolls" wins over "bread".
  const ordered = [...terms].sort((a, b) => b.length - a.length);
  const lower = text.toLowerCase();
  let cursor = 0;
  while (cursor < text.length) {
    let bestAt = -1;
    let bestTerm = "";
    for (const term of ordered) {
      const at = lower.indexOf(term, cursor);
      if (at !== -1 && (bestAt === -1 || at < bestAt)) {
        bestAt = at;
        bestTerm = term;
      }
    }
    if (bestAt === -1) {
      element.appendChild(document.createTextNode(text.slice(cursor)));
      return;
    }
    if (bestAt > cursor) {
      element.appendChild(document.createTextNode(text.slice(cursor, bestAt)));
    }
    const mark = document.createElement("mark");
    mark.textContent = text.slice(bestAt, bestAt + bestTerm.length);
    element.appendChild(mark);
    cursor = bestAt + bestTerm.length;
  }
}

// The words worth highlighting in a result, operators aren't text to find.
function searchHighlightTerms() {
  if (!noteSearch) return [];
  const query = parseNoteQuery(noteSearch);
  return [...query.phrases, ...query.words].filter((t) => t.length > 1);
}

// "Why this result", in words rather than a number, from the three scores the
// engine returns with every hit (`search/engine.py`). Asked for by Brief 11
// directly: the list says *matched the title*, *similar meaning*, *linked to
// the open note*, and the exact percentages sit in the tooltip for anyone who
// disagrees with the order. The chip recipe is the one the chat results
// already use (`.chip.result-reason-chip`), not a new look.
function whyThisResultChip(entry) {
  const hit = noteSearchWhy.get(entry.id);
  const words = hit?.explain?.join(" · ");
  if (!words) return null;
  const badge = chip(`ph:sparkle ${words}`, "result-reason-chip result-reason-why");
  const percent = (value) => Math.round((value || 0) * 100);
  badge.title =
    `Why this result: words ${percent(hit.scores?.bm25)}%, ` +
    `meaning ${percent(hit.scores?.cosine)}%, ` +
    `links ${percent(hit.scores?.graph)}%.`;
  return badge;
}

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
  // note" on a note linked to something nobody is reading.
  const open =
    editingId || (expandedRows.size === 1 ? [...expandedRows][0] : null);
  let body;
  try {
    // 50 is the endpoint's own ceiling (`routes_search.MAX_LIMIT`): a search
    // box shows a page, not a notebook, and a note past the fiftieth best
    // match simply carries no reason chip rather than a wrong one.
    body = await apiJson(
      `/search?q=${encodeURIComponent(asked)}&kind=note,board,map&limit=50` +
        (open ? `&entry_id=${open}` : "")
    );
  } catch {
    // The list is already rendered and already correct; the reasons are the
    // only thing missing, so a failed call leaves the notes alone.
    return;
  }
  if (noteSearch !== asked) return;
  noteSearchWhy.clear();
  for (const hit of body?.hits || []) noteSearchWhy.set(hit.id, hit);
  noteSearchCorrection = body?.corrected
    ? { asked, corrected: body.corrected, ids: new Set((body.hits || []).map((hit) => hit.id)) }
    : null;
  renderEntries();
}

// Sort comparator for the chosen mode (Wave J). Pinned always floats to
// the top first, matching the server's own ordering.
function noteEditedTime(entry) {
  return Date.parse(entry.edited_at || entry.created_at || "") || 0;
}

function noteSortName(entry) {
  return (entry.title || notePreviewText(entry.content || "") || "").replace(/^[#\s]+/, "").trim();
}

function sortEntries(entries) {
  const byPinned = (a, b) => Number(b.pinned) - Number(a.pinned);
  const modes = {
    newest: (a, b) => b.id - a.id,
    oldest: (a, b) => a.id - b.id,
    //: `edited_at` is set only when a person changes the text, title, tags or
    //: category (not on opening or filing); a note never edited counts from
    //: when it was written (INBOX 432).
    edited: (a, b) => noteEditedTime(b) - noteEditedTime(a) || b.id - a.id,
    //: By what the card shows as its name, not the raw text (INBOX 432:
    //: every "# " heading sorted first), and "note 2" before "note 10".
    az: (a, b) => noteSortName(a).localeCompare(noteSortName(b), undefined, { numeric: true, sensitivity: "base" }),
    "most-used": (a, b) => b.access_count - a.access_count || b.id - a.id,
    //: The server's own fading order, by position rather than by a score
    //: recomputed here: `ai/resurface.py` weighs age, links and opens, and a
    //: second copy of those weights in the browser is the two-answers shape
    //: this app has paid for before. A note the ranking has not reached (it
    //: is capped, and a dismissed note is not in it) sorts after every note
    //: that is in it, rather than jumping to the top on a missing key.
    forgotten: (a, b) => {
      const far = forgottenOrder.size + 1;
      return (forgottenOrder.get(a.id) ?? far) - (forgottenOrder.get(b.id) ?? far) || b.id - a.id;
    },
  };
  //: A Semantic search under the default order is a ranking, so it is shown
  //: ranked (best first); it used to be re-sorted newest first here, which
  //: threw away the only thing the toggle computes. Any other sort the person
  //: chose is still theirs.
  const ranked = noteSort === "newest" && noteSemanticLoaded() && noteEngine.rank.size;
  const place = (e) => noteEngine.rank.get(e.id) ?? noteEngine.rank.size;
  const cmp = ranked ? (a, b) => place(a) - place(b) : modes[noteSort] || modes.newest;
  return [...entries].sort((a, b) => byPinned(a, b) || cmp(a, b));
}

//: **The Notes list is windowed** (audit 1029 N9). `renderIncrementally` (now library.js)
//: only ever added: a list scrolled to its end held every card, 300 notes
//: 12,126 elements, and each redraw rebuilt sixty or more. Here every note
//: is an empty `<li class="row-shell">` holding its place (its id, its
//: index, the height it last drew at), and only the rows within
//: `NOTE_WINDOW_MARGIN` of the scroller's window are built; a built row that
//: leaves the margin becomes a shell again. The shells keep keyboard order
//: (`entryListItems` walks them, and the keyboard builds the row it moves
//: to, `noteWindow.fill`) and the selection lives in `selectedIds`, so neither
//: depends on what is built. Built rows say where they are in the whole list
//: (`aria-posinset`, `aria-setsize`), the shells are hidden from screen
//: readers. Never hollowed: the row being edited, holding focus, an open
//: disclosure or an open menu. A redraw builds the rows that were built
//: before it (the same place in the list), the note being jumped to or
//: edited, or the first screenful.
const NOTE_WINDOW_MARGIN = "1200px 0px";
const NOTE_WINDOW_FIRST = 12;
const NOTE_WINDOW_BATCH = 6;
const NOTE_WINDOW_KEEP = 30;
const noteWindow = { observer: null, fill: (li) => li, timer: 0, heights: new Map(), mode: "", slot: new WeakMap() };

function notesScroller(list) {
  for (let el = list.parentElement; el && el !== document.body; el = el.parentElement) {
    if (/(auto|scroll)/.test(getComputedStyle(el).overflowY)) return el;
  }
  return null;
}

function renderWindowed(list, items, buildItem, { keep, afterChunk, settled } = {}) {
  noteWindow.observer?.disconnect();
  if (noteWindow.mode !== notesViewMode) noteWindow.heights.clear();
  noteWindow.mode = notesViewMode;
  const size = String(items.length);
  const guess = notesViewMode === "rows" ? 50 : 132;
  const shellFor = (item, i, from = null) => {
    const li = document.createElement("li");
    li.dataset.id = item[0].id;
    li.className = "row-shell";
    li.setAttribute("aria-hidden", "true");
    //: Hidden inline, not by a rule: the boot stylesheets are at their cap.
    li.style.cssText = `visibility:hidden;height:${noteWindow.heights.get(item[0].id) || guess}px`;
    li.tabIndex = from ? from.tabIndex : -1;
    for (const name of ["rail-subject", "flash"]) if (from?.classList.contains(name)) li.classList.add(name);
    noteWindow.slot.set(li, i);
    return li;
  };
  const build = (i, from = null) => {
    const li = buildItem(items[i], i);
    li.setAttribute("aria-posinset", String(i + 1));
    li.setAttribute("aria-setsize", size);
    noteWindow.slot.set(li, i);
    if (from) {
      li.tabIndex = from.tabIndex;
      for (const name of ["rail-subject", "flash"]) if (from.classList.contains(name)) li.classList.add(name);
    }
    return li;
  };
  const stays = (li) => li.contains(document.activeElement) || Number(li.dataset.id) === editingId
    || li.matches(':has(textarea, details[open], [contenteditable="true"], .action-menu:not(.hidden))');

  const fragment = document.createDocumentFragment();
  const first = keep.size ? 0 : Math.min(NOTE_WINDOW_FIRST, items.length);
  items.forEach((item, i) => fragment.appendChild(i < first || keep.has(item[0].id) ? build(i) : shellFor(item, i)));
  list.appendChild(fragment);

  //: Rows are emptied once the scroll settles, never on the frame they
  //: left, and only past `NOTE_WINDOW_KEEP` rows from the window: building a
  //: card is mostly the browser styling its forty elements, so a row read a
  //: moment ago and scrolled back to is kept rather than built again. The
  //: count chips (`settled`) are asked for then too, once per pause.
  const near = new Set();
  const settle = () => {
    if (noteWindow.observer !== observer || !near.size) return;
    const lo = Math.min(...near) - NOTE_WINDOW_KEEP;
    const hi = Math.max(...near) + NOTE_WINDOW_KEEP;
    for (const target of list.querySelectorAll(":scope > li[data-id]:not(.row-shell)")) {
      const i = noteWindow.slot.get(target);
      if (i === undefined || (i >= lo && i <= hi) || stays(target)) continue;
      const li = shellFor(items[i], i, target);
      target.replaceWith(li);
      observer.observe(li);
    }
    settled?.();
  };
  const observer = new IntersectionObserver((seen) => {
    if (noteWindow.observer !== observer) return;
    for (const { target, isIntersecting, boundingClientRect, rootBounds } of seen) {
      const i = noteWindow.slot.get(target);
      if (i === undefined || target.parentElement !== list) continue;
      if (isIntersecting) near.add(i);
      else near.delete(i);
      if (!target.classList.contains("row-shell")) {
        if (boundingClientRect.height) noteWindow.heights.set(items[i][0].id, boundingClientRect.height);
      } else if (isIntersecting) {
        //: The rows beyond it come with it, further from the window: a few
        //: rows in one frame cost less than a row in every frame of a scroll.
        const run = [target];
        const step = rootBounds && boundingClientRect.top < rootBounds.top ? "previousElementSibling" : "nextElementSibling";
        for (let el = target[step]; el?.classList.contains("row-shell") && run.length < NOTE_WINDOW_BATCH; el = el[step]) run.push(el);
        for (const shell of run) fill(shell);
      }
    }
    clearTimeout(noteWindow.timer);
    noteWindow.timer = setTimeout(settle, 300);
  }, { root: notesScroller(list), rootMargin: NOTE_WINDOW_MARGIN });
  noteWindow.observer = observer;
  //: A shell is hidden, so it cannot take focus: the keyboard (Home, End,
  //: the arrows) builds the row it is moving to first (`noteWindow.fill`).
  function fill(shell) {
    const at = noteWindow.slot.get(shell);
    if (at === undefined || !shell.classList.contains("row-shell") || shell.parentElement !== list) return shell;
    const li = build(at, shell);
    shell.replaceWith(li);
    entryCardControls(li, li.tabIndex === 0);
    observer.observe(li);
    return li;
  }
  noteWindow.fill = fill;
  for (const li of list.querySelectorAll(":scope > li[data-id]")) if (noteWindow.slot.has(li)) observer.observe(li);
  afterChunk?.();
}

// BACKLOG §77 item 1, the user-facing page-size control, deliberately kept
// separate from §86's scroll-chunking (`renderIncrementally`, library.js): that stays
// one continuous scroll under "All notes" (the default, and this function's
// no-op path). A numeric size instead slices whatever list renderEntries was
// about to paint down to one page and updates the Prev/Next bar.
//
// Threads are the one place this is a known, accepted simplification: a
// thread and its children can, at a page boundary, split across two pages
// (part 2 of §77, routing a wiki-link click to the *right* page, depends
// on sort/filter state and is scoped separately, not solved here).
function paginateNotesForDisplay(items) {
  const bar = $("notes-pagination");
  if (notesPageSize === "all") {
    bar.classList.add("hidden");
    return items;
  }
  const pageSize = Number(notesPageSize);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  notesCurrentPage = Math.min(Math.max(1, notesCurrentPage), totalPages);
  const start = (notesCurrentPage - 1) * pageSize;
  //: One page is not paging: "Page 1 of 1" under a single note was a bar
  //: with nothing to do (INBOX 432).
  bar.classList.toggle("hidden", totalPages <= 1);
  $("notes-page-status").textContent = `Page ${notesCurrentPage} of ${totalPages}`;
  $("notes-page-prev").disabled = notesCurrentPage <= 1;
  $("notes-page-next").disabled = notesCurrentPage >= totalPages;
  return items.slice(start, start + pageSize);
}

// **The exact order the Notes list would paint, computed without painting
// it.** Split out of `renderEntries` (BACKLOG §77 item 2, routing a
// wiki-link click to the right *page*) so there is exactly one place that
// decides "what order do these notes render in", used both to actually
// render them and to answer "which page would note N land on" before a
// jump. Threads are the reason this can't be a plain sort-then-slice: a
// child's position depends on its parent's position, not on the child's own
// sort key, so `renderEntries`'s own thread-flattening (`ordered`,
// `addWithChildren`) lives here, and `renderEntries` calls it.
//
// Reads the same module-level filter state `renderEntries` does
// (`draftsOnly`, `activeCategory`, `noteSearch`, `noteSort`), a caller that
// wants a *different* view's ordering (see `resolveNotePage` below) sets
// those first, the same way `flashEntry` already resets category/search/
// drafts before it ever draws anything.
function orderedNotesForCurrentView(visible = libraryVisibleRows()) {
  const flat = Boolean(noteSearch) || noteSort !== "newest";
  if (flat) return sortEntries(visible).map((entry) => [entry, 0]);

  const visibleIds = new Set(visible.map((e) => e.id));
  const childrenOf = new Map();
  for (const entry of visible) {
    if (entry.parent_id && visibleIds.has(entry.parent_id)) {
      if (!childrenOf.has(entry.parent_id)) childrenOf.set(entry.parent_id, []);
      childrenOf.get(entry.parent_id).push(entry);
    }
  }
  const ordered = [];
  const addWithChildren = (entry, depth) => {
    ordered.push([entry, depth]);
    const children = (childrenOf.get(entry.id) || []).slice().reverse();
    for (const child of children) addWithChildren(child, depth + 1);
  };
  for (const entry of visible) {
    const parentVisible = entry.parent_id && visibleIds.has(entry.parent_id);
    if (!parentVisible) addWithChildren(entry, 0);
  }
  return ordered;
}

// Which page (1-based) a note lands on in the Notes list's *current*
// filter/sort: the arithmetic half of BACKLOG §77 item 2. "All notes" (no
// pagination) always answers page 1, since there is only one. Returns null
// for a note the current filters would hide entirely (a category filter
// excluding it, say): a page number for a note that isn't in the list
// would be a lie, not an answer.
function resolveNotePage(id) {
  if (notesPageSize === "all") return 1;
  const order = orderedNotesForCurrentView();
  const index = order.findIndex(([entry]) => entry.id === id);
  if (index === -1) return null;
  return Math.floor(index / Number(notesPageSize)) + 1;
}

//: Rows or cards.
//:
//: **Cards is the default, by direct instruction**, "maybe make the cards
//: notes view default", after rows shipped as the default first. Rows
//: exist because a two-line note was a 111px card plus a 10px gap, so a
//: 900px window showed five notes; they fit twelve. But density is not the
//: only thing a list of notes is for, and a card shows the note rather than
//: a clipped line of it. Both are one click apart, and a row expands in
//: place (see `row-expanded` below), so the compact view is no longer a
//: view that *withholds* things.
//:
//: **The choice is remembered**, also asked for directly. localStorage
//: rather than a server preference: it is a property of this screen on this
//: machine, the same family as the expanded/collapsed sets above, and a
//: round trip to change how a list looks would be the wrong trade. Read as
//: "rows only if rows was explicitly chosen", so a profile that has never
//: touched the toggle gets cards.
let notesViewMode = prefs.get("notesViewMode", null) === "rows" ? "rows" : "cards";

function applyNotesViewMode() {
  const list = $("entry-list");
  if (list) list.classList.toggle("is-rows", notesViewMode === "rows");
  $("notes-view-rows")?.classList.toggle("active", notesViewMode === "rows");
  $("notes-view-cards")?.classList.toggle("active", notesViewMode === "cards");
  $("notes-view-rows")?.setAttribute("aria-pressed", String(notesViewMode === "rows"));
  $("notes-view-cards")?.setAttribute("aria-pressed", String(notesViewMode === "cards"));
  updateExpandAllButton();
}

//: **Expand / collapse every row in the list you are looking at.** Asked for
//: directly ("on the collapsed note view mode there should be an expand
//: and/or collapse all button"). One button rather than two, because the
//: only two states it can be in each have exactly one useful next move.
//:
//: It reads the rendered `<li>`s rather than recomputing which notes are
//: visible. Filtering, sorting, threading and pagination all decide that
//: between them, and a second implementation of "which notes are on screen"
//: is a second thing to keep in step, the DOM already holds the answer.
function listedNoteIds() {
  return [...document.querySelectorAll("#entry-list > li[data-id]")].map((li) =>
    Number(li.dataset.id)
  );
}

function updateExpandAllButton() {
  const button = $("notes-expand-all");
  if (!button) return;
  // Cards view opens every note by definition, so the control would say
  // nothing there.
  button.classList.toggle("hidden", notesViewMode !== "rows");
  if (notesViewMode !== "rows") return;
  const ids = listedNoteIds();
  const anyCollapsed = ids.some((id) => !expandedRows.has(id));
  setLabel(
    button,
    anyCollapsed ? "ph:arrows-out-line-vertical Expand all" : "ph:arrows-in-line-vertical Collapse all"
  );
  button.title = anyCollapsed
    ? "Open every note in this list"
    : "Close every note back to a single line";
  button.setAttribute("aria-label", button.title);
  button.disabled = ids.length === 0;
}

function toggleExpandAllRows() {
  const ids = listedNoteIds();
  if (!ids.length) return;
  const anyCollapsed = ids.some((id) => !expandedRows.has(id));
  for (const id of ids) {
    if (anyCollapsed) expandedRows.add(id);
    else expandedRows.delete(id);
  }
  renderEntries();
}

function setNotesViewMode(mode) {
  notesViewMode = mode === "cards" ? "cards" : "rows";
  prefs.set("notesViewMode", notesViewMode);
  applyNotesViewMode();
}

//: Which rows the reader has opened out. Asked for directly: "I think the
//: compact cards need to be expandable to show all the note details and
//: features."
//:
//: A row is a summary, it clips the body to one line and hides images, file
//: cards and link chips, which is what makes twelve of them fit. That is the
//: right default and the wrong dead end: wanting to *see* one of them should
//: not mean switching the whole list to cards and losing your place. An
//: expanded row drops back to the full card layout in place, so one note can
//: be open inside an otherwise compact list.
//:
//: Not persisted, deliberately. It is a reading position, not a preference, 
//: coming back to a list with six notes arbitrarily open would be worse than
//: coming back to a tidy one.
const expandedRows = new Set();

$("notes-expand-all")?.addEventListener("click", toggleExpandAllRows);
$("notes-view-rows")?.addEventListener("click", () => setNotesViewMode("rows"));
$("notes-view-cards")?.addEventListener("click", () => setNotesViewMode("cards"));

//: **A map's topics live on their map** (audit 2026-10-05, UX-06). Each
//: topic a concept map's Tab or Enter makes is a note (`map_topic`), and a
//: map of forty put forty one-word rows at the top of All. They stay out of
//: All, the categories and Favourites, and come back for a search, which is
//: how a person looks for one; Drafts keeps its own row as before.
function noteListed(e) {
  return !e.is_draft && (!e.map_topic || Boolean(noteSearch));
}

function noteCountExcludingDrafts() {
  let n = 0;
  for (const e of allEntries) if (!e.is_draft) n += 1;
  return n;
}

//: **A tag chip filters by its tag** (INBOX 432: it was inert, and the one
//: way to see a tag's notes was typing `tag:` by hand). The box shows the
//: query, so the filter is visible and editable; the tag chips on the
//: dashboard use the same path.
function filterNotesByTag(tag) {
  filterNotesBy(/\s/.test(tag) ? `tag:"${tag}"` : `tag:${tag}`);
}

//: A property's value as a filter (the owner, 2026-10-10: "is it possible to
//: add and customise the metadata a little more??"): `prop:key=value`, the
//: value quoted when it has a space (query.py's `_TOKEN`), a [[note]] by name.
function propQuery(key, value) {
  const v = String(value).replace(/^\[\[|\]\]$/g, "").replace(/"/g, "");
  return `prop:${key}=${/[\s=<>!]/.test(v) ? `"${v}"` : v}`;
}

//: The Notes list filtered by one query, as the box would be typed.
function filterNotesBy(value) {
  $("note-search").value = value;
  noteSearch = value;
  $("save-search")?.classList.remove("hidden");
  draftsOnly = false;
  favouritesOnly = false;
  activeCategory = null;
  notesCurrentPage = 1;
  if (prefs.get("activeTab", null) !== "notes") switchTab("notes");
  showNotesSection("browse");
  renderSidebar();
  renderEntries();
}

function libraryVisibleRows() {
  //: `is:draft` in the box reaches the drafts the other views leave out.
  const wantsDrafts = Boolean(noteSearch) && /(^|\s)is:drafts?(\s|$)/i.test(noteSearch);
  let visible = draftsOnly || wantsDrafts
    ? allEntries.filter((e) => e.is_draft)
    : favouritesOnly
      ? allEntries.filter((e) => e.pinned && noteListed(e))
      : activeCategory
        ? allEntries.filter((e) => e.category === activeCategory && noteListed(e))
        : allEntries.filter(noteListed);
  const matched = visible.filter(matchesSearch);
  //: UX-04: no match, and /search corrected a typo: show what it found.
  noteSearchCorrectionShown = false;
  const fix = noteSearchCorrection;
  if (!matched.length && fix && fix.asked === noteSearch && fix.ids.size) {
    noteSearchCorrectionShown = true;
    return visible.filter((e) => fix.ids.has(e.id));
  }
  return matched;
}

//: Ids on screen before this render, or null outside the second after one.
let rowEnterIds = null;
let rowEnterTimer = 0;

function renderEntries() {
  closeNotePageIfGone();
  notesRailSync();
  // A cleared box clears its reasons here rather than at each of the five
  // places that can clear the box: a reason for a query nobody typed is
  // worse than no reason at all.
  if (!noteSearch && noteSearchWhy.size) noteSearchWhy.clear();
  const list = $("entry-list");
  const empty = $("empty-message");
  const noMatch = $("no-match-message");
  //: **A row that arrives after the first render fades in** (ledger 1538). The
  //: list redraws whole, so what was on screen is remembered by id and a card
  //: whose id was not there is marked (`entryItem` reads `rowEnterIds`). The
  //: first render, and a render after the list was empty, mark nothing.
  rowEnterIds = new Set([...list.querySelectorAll(":scope > li[data-id]")].map((li) => li.dataset.id));
  //: The rows built now are where the reader is: the redraw builds them again.
  const keep = new Set([...list.querySelectorAll(":scope > li[data-id]:not(.row-shell)")].map((li) => Number(li.dataset.id)));
  if (noteEngine.jumpId != null) keep.add(noteEngine.jumpId);
  if (editingId != null) keep.add(editingId);
  clearTimeout(rowEnterTimer);
  rowEnterTimer = setTimeout(() => { rowEnterIds = null; }, 1000);
  list.replaceChildren();
  // Re-applied on every render, not just on a click: `replaceChildren`
  // above leaves the class alone, but a later render that rebuilt the <ul>
  // itself would not: and this failing silently would look like the
  // toggle not working rather than a class being dropped.
  applyNotesViewMode();
  //: Held notes first (quick-note.js); loads it only when one is held.
  if (prefs.get("noteOutbox", null)) renderPendingNoteRows();

  // Drafts stay out of All/category views entirely, user-reported: they
  // should only show up in the Drafts filter until saved as a real note.
  const visible = libraryVisibleRows();
  //: **A selection is of what is on screen** (INBOX 432). Ticking five notes
  //: and then choosing a category left "5 selected" over two visible rows,
  //: and Tag or Delete then acted on all five, three of them out of sight.
  //: Notes leave the selection when the view leaves them. Only on the Notes
  //: tab: the Timeline ticks into the same set (TIMELINE_PLAN decision 6).
  if (selectMode && selectedIds.size && prefs.get("activeTab", null) === "notes") {
    const shown = new Set(visible.map((e) => e.id));
    let dropped = 0;
    for (const id of [...selectedIds]) if (!shown.has(id)) { selectedIds.delete(id); dropped++; }
    if (dropped) updateBatchCount();
  }

  // "Notes" everywhere else on this tab ("Your notes", "notebook", the
  // status-bar note count): this heading used to say "entries" (the API's
  // internal name, /entries), the one place on the tab that didn't match
  // (Part C terminology audit).
  const scope = draftsOnly
    ? "Drafts"
    : favouritesOnly
      ? "Favourites"
      : activeCategory
        ? `${activeCategory} notes`
        : noteSearch === "tag:meeting"
          ? "Meetings"
          : "All notes";
  // Say how many matched out of how many there are. Without it a filter that
  // hides most of the notebook looks identical to a notebook that's nearly
  // empty, and there's no signal that a filter is even active.
  const total = draftsOnly
    ? allEntries.filter((e) => e.is_draft).length
    : favouritesOnly
      ? allEntries.filter((e) => e.pinned && noteListed(e)).length
      : activeCategory
        ? allEntries.filter((e) => e.category === activeCategory && noteListed(e)).length
        : allEntries.filter(noteListed).length;
  $("entries-heading-label").textContent =
    noteSearchCorrectionShown
      ? `${scope}: showing results for “${noteSearchCorrection.corrected}”`
      : noteSearch && visible.length !== total
        ? `${scope}: ${visible.length} of ${total}`
        : scope;
  liveQueryBar(visible);
  // Distinguish "empty notebook" from "filter matched nothing".
  const notebookEmpty = allEntries.length === 0;
  empty.classList.toggle("hidden", !notebookEmpty);
  noMatch.classList.toggle("hidden", notebookEmpty || visible.length > 0);

  // Flat for a search or non-default sort, threaded for newest: one ordering
  // with `resolveNotePage`, so a jump's page is the page that renders.
  const ordered = paginateNotesForDisplay(orderedNotesForCurrentView(visible));
  renderWindowed(
    list,
    ordered,
    ([entry, depth]) => {
      const li = entryItem(entry, { actions: true });
      if (depth > 0) {
        li.classList.add("thread-child");
        li.style.marginLeft = `${Math.min(depth, 4) * 1.4}rem`;
      }
      return li;
    },
    {
      keep,
      afterChunk: () => {
        applyEntryListTabOrder(list);
        ensureCardCounts(list, _entriesLoadGeneration);
        // Expand-all reads the rendered rows, and `applyNotesViewMode` runs
        // at the *top* of this function, when the list is empty: refreshed
        // here, once the rows exist.
        updateExpandAllButton();
      },
      settled: () => ensureCardCounts(list, _entriesLoadGeneration),
    }
  );
}

// --- note-list keyboard navigation (ROADMAP Tier 3 §30a / BACKLOG §16) ------------
// Named directly as "the one interaction pattern used constantly enough that
// its absence would be felt every session, not just noticed in an audit."
// A roving tabindex: only one <li> is ever a Tab stop, so the list is one
// stop in the page's tab order rather than one per note, matching the
// standard listbox/grid keyboard pattern.
// `li[data-id]`, not `list.children`: the incremental renderer parks a
// zero-height sentinel `<li>` at the end of the list to know when to paint the
// next chunk, and it is not a note. Left in `children` it would join the
// roving tabindex and the arrow-key walk below, so ArrowDown at the bottom of
// the list would focus an invisible element and appear to do nothing.
const entryListItems = (list) => Array.from(list.querySelectorAll(":scope > li[data-id]"));

//: A shift-click range over every row between the two, built or not.
function selectNoteRange(list, fromId, toId, on) {
  const rows = entryListItems(list);
  const a = rows.findIndex((li) => li.dataset.id === fromId);
  const b = rows.findIndex((li) => li.dataset.id === toId);
  if (a === -1 || b === -1) return;
  for (const li of rows.slice(Math.min(a, b), Math.max(a, b) + 1)) {
    if (on) selectedIds.add(Number(li.dataset.id));
    else selectedIds.delete(Number(li.dataset.id));
    const check = li.querySelector(":scope > .select-check");
    if (check) check.checked = on;
    if (!li.classList.contains("row-shell")) li.classList.toggle("is-selected", on);
  }
  updateBatchCount();
}

function applyEntryListTabOrder(list) {
  const items = entryListItems(list);
  const current = document.activeElement;
  // Re-renders happen constantly (search-as-you-type, sort, edits): if the
  // previously-focused note is still present, keep it as the one Tab stop
  // instead of silently resetting focus back to the top of the list.
  const holder = current && items.find((li) => li === current || li.contains(current));
  entryListSetStop(items, holder || items[0] || null);
}

function initEntryListKeyboardNav() {
  const list = $("entry-list");
  list.addEventListener("focusin", entryListFocusStop);
  list.addEventListener("keydown", (event) => {
    //: Home/End, Delete (to the bin, with Undo) and F2 (edit) on a focused
    //: row, as a notes list answers them everywhere else (INBOX 432: only
    //: the arrows and Enter did anything).
    const keys = ["ArrowDown", "ArrowUp", "Enter", "Home", "End", "Delete", "F2"];
    if (!keys.includes(event.key)) return;
    //: A note's own ⋯ menu lives inside its row, so its arrow keys bubble
    //: here too: ArrowDown in the menu moved to the next item and then this
    //: moved the focus out of the menu onto the row (measured, menus.js).
    if (event.target.closest('.action-menu, [role="menu"], [role="listbox"]')) return;
    //: **A text field keeps its own keys.** A note's edit form lives inside
    //: its row, so the title box, the tags box and the body editor sent their
    //: Home, End and arrow keys here: the caret never moved, the focus jumped
    //: to another row, and what was typed next went nowhere (found by the
    //: deepflows sweep: click into the editor, press End, type). Checkboxes
    //: and buttons are not fields, so the row's arrows still work from them.
    if (event.target.closest('textarea, select, [contenteditable], .cm-editor, input:not([type="checkbox"]):not([type="radio"]):not([type="button"])')) return;
    const items = entryListItems(list);
    const current = event.target.closest("li");
    const index = current ? items.indexOf(current) : -1;
    if (index === -1) return;

    if (event.target === current && (event.key === "Delete" || event.key === "F2")) {
      const entry = allEntries.find((e) => e.id === Number(current.dataset.id));
      if (!entry || editingId === entry.id) return;
      event.preventDefault();
      const next = items[index + 1] || items[index - 1];
      if (event.key === "F2") openNoteEditor(entry.id);
      else binNoteWithUndo(entry).then(() => {
        const again = next && document.querySelector(`#entry-list li[data-id="${next.dataset.id}"]`);
        again?.focus();
      });
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const nextIndex =
        event.key === "Home" ? 0
          : event.key === "End" ? items.length - 1
            : Math.min(Math.max(index + (event.key === "ArrowDown" ? 1 : -1), 0), items.length - 1);
      const target = noteWindow.fill(items[nextIndex]);
      entryListSetStop(entryListItems(list), target);
      target.focus();
      // .focus() alone scrolls in most browsers, but not predictably, 
      // explicit and consistent with the same fix on the command palette's
      // own arrow-key nav, which has no focus to lean on at all.
      target.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter" && event.target === current) {
      // Only when the <li> itself has focus, not a button/link/textarea
      // inside it: those already handle their own Enter behaviour, and
      // this app has no separate "note view" to open: editing in place is
      // what opening a note means here.
      event.preventDefault();
      current.querySelector(".entry-actions [title='Edit this entry']")?.click();
    }
  });
}

//: **A category's colour, from one function.** The one the person chose
//: (Manage categories, Colour; `categoryMeta`, just below, carries it as a palette key or a
//: `#rrggbb`), else `automatic`, which each surface passes in because they
//: have always drawn their own: a hash of the name into the ten hues the
//: graph's legend uses for a dot, the place in the sorted list for a graph
//: node. Every dot, chip, node and legend swatch asks here, so a choice
//: shows everywhere at once. A dot carries it, never the text, so the name
//: stays at full contrast. The twelve hues are the swatches the picker draws
//: and each reads at 3:1 or better as a dot on the lightest and darkest
//: surface of both themes (tests/test_category_colour.py computes it);
//: routes_categories.py holds the same keys.
const CATEGORY_PALETTE = {
  red: "#da5252", orange: "#ba6d36", amber: "#9e7c17", lime: "#6d8a14", green: "#15952b", teal: "#159172",
  cyan: "#178ca3", blue: "#387fe3", indigo: "#6a74ea", violet: "#9b63e9", magenta: "#d332e2", pink: "#ce5591",
};
const CATEGORY_AUTO_COLOURS = [
  "#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f",
  "#edc949", "#af7aa1", "#ff9da7", "#9c755f", "#8cd17d",
];
function categoryColour(name, automatic = null) {
  const chosen = categoryMeta.get(name)?.colour;
  if (chosen) return Object.hasOwn(CATEGORY_PALETTE, chosen) ? CATEGORY_PALETTE[chosen] : chosen;
  return automatic;
}
function categoryAutoDot(name) {
  let h = 0;
  for (const ch of String(name || "")) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return CATEGORY_AUTO_COLOURS[h % CATEGORY_AUTO_COLOURS.length];
}
const categoryDotColour = (name) => categoryColour(name, categoryAutoDot(name));
//: A dot that can be repainted: it remembers whose it is, so a colour chosen
//: while it is on screen reaches it without a redraw of the list.
function paintCategoryDot(el, name) {
  el.dataset.categoryDot = name;
  el.style.setProperty("--category-dot", categoryDotColour(name));
}
function categoryColoursChanged() {
  for (const el of document.querySelectorAll("[data-category-dot]")) paintCategoryDot(el, el.dataset.categoryDot);
  document.dispatchEvent(new Event("categorycolours"));
}

// name -> {id, count}. Needed because renaming and deleting work on ids,
// while the sidebar itself is built from the entries already in memory.
let categoryMeta = new Map();

async function loadCategories() {
  const rows = await apiJson("/categories", { silent: true }).catch(() => []);
  const was = categoryMeta;
  //: In All spaces two spaces can each have a "Work"; the server lists the
  //: bigger first, and the first is kept (INBOX 432: the empty one used to
  //: overwrite it, so the panel said "Work, 0 notes" and renamed the wrong
  //: one). The other is still there in its own space's view.
  categoryMeta = new Map();
  for (const row of rows) if (!categoryMeta.has(row.name)) categoryMeta.set(row.name, row);
  renderSidebar();
  //: Only when a colour moved: this runs after every category change, and the
  //: map and the dashboard redraw when told.
  if (rows.some((c) => (c.colour || null) !== (was.get(c.name)?.colour || null))) categoryColoursChanged();
}

function renderSidebar() {
  // Categories + counts are derived from the loaded entries, the
  // simplest thing that works; no extra endpoint needed yet.
  // Drafts only belong in the Drafts row (user-reported: they were still
  // showing under All/category counts, undercutting the point of a
  // separate section): until saved as a real note, a draft doesn't count.
  const counts = new Map();
  //: Every category the notebook has, not only the ones a loaded note is in:
  //: one made in Manage categories was in the panel and nowhere else
  //: (INBOX 432). Uncategorised only while something is in it.
  for (const name of categoryMeta.keys()) if (name !== "Uncategorised") counts.set(name, 0);
  for (const entry of allEntries) {
    if (!noteListed(entry)) continue;
    counts.set(entry.category, (counts.get(entry.category) || 0) + 1);
  }

  const ul = $("category-list");
  ul.replaceChildren();

  const addRow = (label, count, category) => {
    const li = document.createElement("li");
    //: "All" is the row for no filter at all, so it is not lit while Drafts
    //: or Favourites is (INBOX 432: two rows looked chosen at once).
    if (category === activeCategory && !draftsOnly && !favouritesOnly && !(!category && noteSearch === "tag:meeting")) markSidebarRowCurrent(li);
    const name = document.createElement("span");
    name.className = "category-name";
    //: Every name on one edge (INBOX 437 (4)): All takes a glyph as Drafts
    //: does, a category its colour dot, as on a note's own chip.
    if (!category) setLabel(name, `ph:stack ${label}`);
    else {
      name.textContent = label;
      const dot = document.createElement("i");
      dot.className = "ph category-row-dot ph-lead";
      dot.setAttribute("aria-hidden", "true");
      paintCategoryDot(dot, category);
      name.prepend(dot);
    }
    name.title = label;
    const badge = document.createElement("span");
    badge.className = "count";
    badge.textContent = count;
    li.append(name, badge);
    li.addEventListener("click", () => {
      activeCategory = category;
      draftsOnly = false; // exclusive with the Drafts filter below
      favouritesOnly = false; // and with Favourites, for the same reason
      // The list this filters lives in the "browse" sub-tab, and the sidebar
      // is visible from all four, so picking a category while writing a note
      // or asking a question filtered a list that was `display: none`, and the
      // click appeared to do nothing at all. Reported. The same fix
      // `flashEntry` already carries for jumping to a note, for the same
      // reason: a sidebar that is always on screen must be able to bring the
      // thing it controls on screen with it.
      showNotesSection("browse");
      renderSidebar();
      renderEntries();
    });

    // Rename/delete for real categories only, "All" is a filter, and
    // Uncategorised is where notes land when a category goes away.
    const meta = category ? categoryMeta.get(category) : null;
    //: Round 9 (INBOX 431 (e)): the row's ⋯ is the Manage categories panel's
    //: own menu (Rename, Merge into, Split, Delete, the panel), where two
    //: bare buttons were; and every real category takes a dropped note.
    if (meta && category !== "Uncategorised") {
      const actions = document.createElement("span");
      actions.className = "category-actions";
      const menu = kebabMenu(categoryMenuItems(meta), `Actions for ${category}`, { vertical: true });
      menu.addEventListener("click", (event) => event.stopPropagation());
      actions.appendChild(menu);
      li.appendChild(actions);
    }
    if (category) wireCategoryDropTarget(li, category);
    wireSidebarRowKeys(li);
    ul.appendChild(li);
  };

  addRow("All", allEntries.filter(noteListed).length, null);

  //: **One shape for the rows that are not categories** (Drafts, Favourites,
  //: Meetings): a glyph and a name, a count, the current one marked, a press
  //: that filters. Three hand-built copies of these eleven lines were how the
  //: second and third came to exist; INBOX 644's Meetings made it a helper.
  const filterRow = (label, count, current, title, run) => {
    const li = document.createElement("li");
    li.className = "category-drafts-row";
    if (current) markSidebarRowCurrent(li);
    wireSidebarRowKeys(li);
    const name = document.createElement("span");
    name.className = "category-name";
    setLabel(name, label);
    const badge = document.createElement("span");
    badge.className = "count";
    badge.textContent = count;
    li.append(name, badge);
    if (title) li.title = title;
    li.addEventListener("click", run);
    ul.appendChild(li);
    return li;
  };
  const toggleFilter = (drafts) => () => {
    if (drafts) draftsOnly = !draftsOnly;
    else favouritesOnly = !favouritesOnly;
    if (drafts) favouritesOnly = false;
    else draftsOnly = false;
    activeCategory = null;
    showNotesSection("browse");
    renderSidebar();
    renderEntries();
  };

  // A drafts count, not a category, asked for directly: a Drafts filter
  // findable in the same place categories are, so a note drafted with the
  // AI (Writing Room) or captured from a selection isn't only markable one
  // at a time via its own chip (entryItem). Always shown, even at 0, so it
  // stays discoverable rather than appearing only once something lands in it.
  filterRow("ph:pencil-simple-line Drafts", allEntries.filter((e) => e.is_draft).length, draftsOnly, "", toggleFilter(true));

  // **Favourites.** Asked for as "a favourites folder or side parallel category
  // that isnt an actual category but could be treated as one if toggled", so
  // it is built exactly like Drafts directly above: a row where the categories
  // are, a count, a toggle, and mutually exclusive with the other two filters.
  // This app already has one pseudo-category, and a second that behaved
  // differently would be a second sign for the same idea.
  //
  // The notes it collects are the pinned ones (see `favouritesOnly`), no new
  // flag, no second place to star something.
  filterRow(
    "ph:star Favourites",
    allEntries.filter((e) => e.pinned && noteListed(e)).length,
    favouritesOnly,
    "Notes you have starred, they also float to the top of every list",
    toggleFilter(false)
  );

  //: **Meetings** (INBOX 644: "tucked away"; the Library had a Meetings chip,
  //: the Notes tab nothing). Over what every meeting already carries, the
  //: `meeting` tag (`entry/meetings.py`), so the filter is `tag:meeting` in
  //: the box, visible and editable as a tag chip's is. Always shown, so it is
  //: there to find before the first meeting.
  filterRow(
    "ph:users-three Meetings",
    allEntries.filter((e) => e.tags.includes("meeting") && noteListed(e)).length,
    noteSearch === "tag:meeting" && !draftsOnly && !favouritesOnly,
    "",
    () => filterNotesByTag("meeting")
  ).classList.add("category-meetings-row");
  //: Tags, beside Drafts and Favourites (INBOX 432): a sheet of every tag
  //: (categories-panel.js `openTagsSheet`), not a second long list here.
  const tagRow = document.createElement("li");
  tagRow.className = "category-drafts-row";
  const tagName = document.createElement("span");
  tagName.className = "category-name";
  setLabel(tagName, "ph:hash Tags");
  tagRow.append(tagName);
  tagRow.title = "Every tag: see its notes, rename, merge or remove it";
  tagRow.addEventListener("click", () => openTagsSheet());
  wireSidebarRowKeys(tagRow);
  ul.appendChild(tagRow);

  //: One order everywhere a list of categories is shown: by name, ignoring
  //: case and accents, numbers in number order (INBOX 432: a bare `.sort()`
  //: put "Zebra" before "alpha" and "Émigré" last).
  for (const [category, count] of [...counts.entries()].sort((a, b) => compareCategoryNames(a[0], b[0]))) {
    addRow(category, count, category);
  }
  foldSide();
}

function compareCategoryNames(a, b) {
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

function markSidebarRowCurrent(li) {
  li.classList.add("active");
  li.setAttribute("aria-current", "true");
}

//: **The rows are reachable by keyboard** (INBOX 432: a Tab walk reached
//: only their ⋯ buttons). Each row is one tab stop that Enter or Space
//: chooses, and the arrows walk the list, as a sidebar does in every
//: notes app.
function wireSidebarRowKeys(li) {
  li.tabIndex = 0;
  li.addEventListener("keydown", (event) => {
    if (event.target !== li) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      li.click();
      requestAnimationFrame(() => $("category-list").querySelector('li[aria-current="true"]')?.focus());
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = event.key === "ArrowDown" ? li.nextElementSibling : li.previousElementSibling;
      next?.focus();
    }
  });
}

// --- Manage categories ----------------------------------------------------------
//: **Manage categories** (INBOX 431 (e), the owner: "a better, easier and more
//: accessible and learnable way to [manually] edit categories like with
//: merging them, splitting them, moving notes between them etc. accessible
//: from the notes tab, and settings ... the user needs to be able to easily
//: do anything the ai can do"). One sheet (DESIGN.md's sheet recipe), opened
//: from the Categories head in the notes sidebar, from each category's ⋯
//: menu and from Settings: a row per category with its colour and count and
//: a ⋯ of Rename, Merge into, Split and Delete, and New category at the top.
//: Every change answers with the notes it moved (routes_categories.py), and
//: every change offers Undo, in a toast and on the global undo stack.
//: Notes also move by ticking them in the list and choosing Move to (the
//: batch bar), or by dragging a note's category label onto a category in
//: the sidebar.

function categoryMenuItems(meta, { inPanel = false } = {}) {
  const items = [
    { label: "ph:pencil-simple Rename…", title: `Rename ${meta.name}`, run: () => renameCategory(meta, meta.name) },
    { label: "ph:palette Colour…", title: `Choose the colour of ${meta.name}`, run: () => pickCategoryColour(meta) },
    { label: "ph:arrows-merge Merge into…", title: `Move every note in ${meta.name} into another category`, run: () => mergeCategoryFromPanel(meta) },
    { label: "ph:arrows-split Split…", title: `Move some of ${meta.name}'s notes into a new category`, run: () => splitCategoryFromPanel(meta) },
    { label: "ph:trash Delete…", title: `Delete ${meta.name}; its notes are kept`, danger: true, group: "danger", run: () => deleteCategoryFromPanel(meta) },
    { label: "ph:sliders-horizontal Manage categories", title: "Open the panel with every category", group: "all", run: () => openManageCategories(meta.name) },
  ];
  //: Inside the panel itself, "Manage categories" opened a second copy over
  //: the first (reported at release).
  return inPanel ? items.filter((item) => item.group !== "all") : items;
}

//: **Dragging a note onto a category** in the sidebar moves it there, with
//: the same undo. What is dragged is the note's category label (its chip in
//: the card's meta line, `text/x-memorymap-note`): the card itself is not
//: draggable, because a draggable card would steal every text selection
//: made in it.
function wireCategoryDropTarget(li, category) {
  li.addEventListener("dragover", (event) => {
    if (!event.dataTransfer?.types?.includes("text/x-memorymap-note")) return;
    event.preventDefault();
    li.classList.add("is-drop-target");
  });
  li.addEventListener("dragleave", () => li.classList.remove("is-drop-target"));
  li.addEventListener("drop", async (event) => {
    li.classList.remove("is-drop-target");
    const id = Number(event.dataTransfer?.getData("text/x-memorymap-note"));
    if (!id) return;
    event.preventDefault();
    await moveNotesToCategory([id], category);
  });
}

// Loading skeletons (Wave I): shimmer placeholders instead of a blank
// list on the very first load, so a slow disk never looks broken.
function showEntrySkeletons() {
  const list = $("entry-list");
  if (list.children.length > 0) return; // only ever on a truly empty list
  for (let i = 0; i < 3; i++) {
    const li = document.createElement("li");
    li.className = "skeleton";
    li.setAttribute("aria-hidden", "true");
    list.appendChild(li);
  }
}

//: The same placeholders for any list that fetches before it can draw
//: (INBOX 399 (4)): the Library's grid and the Timeline's feed showed a blank
//: card until their first response, which on a slow disk reads as an empty
//: notebook. Only into a list with nothing in it, so a refresh never covers
//: what is already there; the list's own render replaces them, and
//: `clearSkeletons` takes them out on a path that draws nothing (a failed
//: request). `aria-busy` tells a screen reader the list is on its way.
//: K1: a skeleton stands for what the last render drew in this container,
//: as many rows as were on screen then at their mean height (kept per
//: id), so the swap does not jump. `count` is only the first-visit guess.
function showSkeletons(container, count = 3, tag = "div") {
  if (!container || container.children.length > 0) return;
  const seen = container.id && prefs.json("skeleton-seen", {})[container.id];
  container.setAttribute("aria-busy", "true");
  for (let i = 0; i < (seen?.[0] || count); i++) {
    const el = document.createElement(tag);
    el.className = "skeleton";
    if (seen) el.style.height = `${seen[1]}px`;
    el.setAttribute("aria-hidden", "true");
    container.appendChild(el);
  }
  //: Real rows and skeletons have different gaps between them, so the
  //: skeletons are then sized to cover the same span the rows did.
  const span = seen?.[2];
  const first = container.firstElementChild;
  if (span && first) {
    const drawn = container.lastElementChild.getBoundingClientRect().bottom - first.getBoundingClientRect().top;
    const height = Math.max(8, seen[1] + (span - drawn) / seen[0]);
    if (drawn > 0) for (const el of container.children) el.style.height = `${height}px`;
  }
}

function skeletonRemember(container) {
  const rows = [...container.children].filter((el) => !el.classList.contains("skeleton"));
  //: The mean, not the first row: a group's heading would make every one short.
  //: Rows run down the page, so the walk stops at the first one below the
  //: fold; measuring every row of a long list read the whole list's layout
  //: (INBOX 1426 L6, the notes list's 255 to 372ms response frame).
  const shown = [];
  for (const el of rows) {
    if (el.getBoundingClientRect().top >= innerHeight) break;
    shown.push(el);
  }
  if (!shown.length) return;
  const height = Math.round(shown.reduce((sum, el) => sum + el.offsetHeight, 0) / shown.length);
  if (!height) return;
  const seen = prefs.json("skeleton-seen", {});
  const n = Math.min(shown.length, 30);
  const span = shown[n - 1].getBoundingClientRect().bottom - shown[0].getBoundingClientRect().top;
  seen[container.id] = [n, height, Math.round(span)];
  prefs.setJSON("skeleton-seen", seen);
}

function clearSkeletons(container) {
  if (!container) return;
  container.removeAttribute("aria-busy");
  const held = container.querySelectorAll(":scope > .skeleton");
  for (const el of held) el.remove();
  //: The caller draws its rows right after this in the same task, so a
  //: microtask sees them (K1; no observer or frame loop, test_frontend_wake_sources).
  if (held.length && container.id) queueMicrotask(() => skeletonRemember(container));
  //: **What replaces them settles in** (the motion pass, 2026-10-05): the
  //: first rows fade up a step, staggered (`.ui-settle`, 08-consistency.css),
  //: instead of popping in where the skeletons were. Only on this first
  //: swap: the class is gone before any later redraw.
  if (held.length) {
    container.classList.add("ui-settle");
    setTimeout(() => container.classList.remove("ui-settle"), 600);
  }
}

// A page of the plain list. Smaller than the backend's own default
// (`ENTRIES_PAGE_SIZE = 1000` in routes_entries.py, still the cap a caller
// gets by asking for nothing) on purpose, WORLD_CLASS_PLAN A2: the boot
// request for the whole notebook was the slowest fetch a cold start made, 258
// ms measured, and everything it carried past the first screenful was paid for
// before anything drew. The loop below renders each page as it lands, so this
// is the size of the first paint, not of the list: a notebook larger than this
// still ends up exactly as complete, one page later.
const ENTRIES_PAGE_SIZE = 200;

//: How long the list may go without showing a newly arrived page while the
//: background paging runs. Short enough that a big notebook still visibly
//: fills in, long enough that twenty-one pages are a handful of repaints
//: rather than twenty-one.
const ENTRIES_PROGRESS_MS = 250;
let _entriesProgressTimer = null;

function paintEntriesProgress() {
  clearTimeout(_entriesProgressTimer);
  _entriesProgressTimer = null;
  renderStatusBar(); // the notebook's size changed, and the bar reads it here
  renderEntries();
}

function scheduleEntriesProgress() {
  if (_entriesProgressTimer !== null) return;
  //: A repaint costs more as the list grows (27 to 46ms over eight at 2,000 notes), so the gap grows with it.
  _entriesProgressTimer = setTimeout(paintEntriesProgress, ENTRIES_PROGRESS_MS * Math.max(1, allEntries.length / 800));
}

async function loadEntries() {
  //: Wrapped, because every path below this either paints the notebook or
  //: throws, and a throw used to leave the skeletons and then the empty state
  //: on screen: "Your notebook is empty" is a claim about the person's own
  //: notes that a failed GET is no basis for. See `surfaceFailed`.
  return loadSurface($("empty-message"), "your notes", _loadEntries);
}

async function _loadEntries() {
  const generation = ++_entriesLoadGeneration;
  entriesComplete = false;
  referenceCountsCache.clear();
  reminderCountsCache.clear();
  noteTopicsCache.clear();
  showEntrySkeletons();

  const isSemantic = $("semantic-search-toggle")?.checked;
  if (isSemantic && noteSearch) {
    //: **The Semantic toggle asks the engine** (`GET /search`), the one place
    //: words, meaning and the links are ranked together, rather than a second
    //: cosine-only list path (retired). The engine's page
    //: is at most 50 hits, so nothing here needs paging; the list is then read
    //: by id, which is also what keeps the bin, the archive and the boards out
    //: of it (the index holds them, flagged), and put in the engine's order.
    const asked = noteSearch;
    const found = await apiJson(`/search?q=${encodeURIComponent(asked)}&kind=note&limit=50`);
    const order = (found.hits || []).map((hit) => hit.id);
    const rows = order.length ? await apiJson(`/entries?ids=${order.join(",")}`) : [];
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
    return;
  }

  // Paginated: GET /entries used to return the whole notebook in one
  // response, which is fine at a few hundred notes and a real risk of
  // timing out (or just feeling broken) at the size a "just works" notebook
  // reaches after years of use. The first page paints immediately, for
  // most notebooks that's everything, indistinguishable from before, and
  // any further pages fill in the background, so nothing downstream of
  // allEntries (search, keyboard nav, the sidebar, tag suggestions) had to
  // change: it still ends up exactly as complete as it always was.
  let offset = 0;
  let total = Infinity; // discovered from the first response's X-Total-Count
  //: Any repaint this load still owes. Cleared by `paintEntriesProgress`, so
  //: the immediate paint on the last page cannot be followed by a stale
  //: throttled one a moment later.
  clearTimeout(_entriesProgressTimer);
  _entriesProgressTimer = null;
  let first = true;
  //: The next page by the server's cursor (WORLD_CLASS_PLAN B7), not by
  //: offset: a note saved while page one is on screen would push a row of
  //: page one onto page two as well, and the list would show it twice.
  let cursor = "";
  while (offset < total) {
    const after = cursor ? `&cursor=${encodeURIComponent(cursor)}` : "";
    const response = await api(`/entries?limit=${ENTRIES_PAGE_SIZE}${after}`);
    const page = await response.json();
    if (generation !== _entriesLoadGeneration) return; // superseded mid-load

    allEntries = first ? page : allEntries.concat(page);
    entriesEverLoaded = true;
    publishNotes(allEntries);
    offset += page.length;
    cursor = response.headers.get("X-Next-Cursor") || "";
    const reported = Number(response.headers.get("X-Total-Count"));
    total = !cursor ? offset : Number.isFinite(reported) ? reported : allEntries.length;

    ensureMapChipsFor(page, generation);
    //: **Twenty-one pages used to mean twenty-one full re-renders.**
    //: `renderEntries()` costs 79 ms on a four thousand note list (measured
    //: at 1440x900), and the loop called it for every page, so a notebook
    //: that pages twenty-one times spent about 1.7 s of main thread redrawing
    //: a list that nobody had asked to change. The first page is what the
    //: reader is actually looking at; the pages after it are background.
    //:
    //: So the first page and the last one paint at once, the ones in between
    //: are throttled. The list still visibly grows, which is the point of
    //: painting during the load at all, it just grows in steps of a quarter
    //: second rather than in twenty-one full repaints.
    const lastPage = offset >= total || page.length === 0;
    if (first || lastPage) paintEntriesProgress();
    else scheduleEntriesProgress();
    if (first || offset >= total) {
      renderSidebar();
      // Categories the AI has filed notes into since the last load need
      // their ids fetched before rename/delete can work on them.
      // Deliberately not awaited: the list renders now and the controls
      // light up a moment later.
      loadCategories();
      fillCategoryOptions($("entry-category"), null);
    }
    first = false;
    if (page.length === 0) break; // safety: never loop forever on a stale total
  }
  if (generation === _entriesLoadGeneration) entriesComplete = true;
  nudgeUntaggedNotes();
  nudgeReviewQueue();
}

//: **Re-read the notes a change touched, not the notebook** (audit
//: 2026-10-05, FE-05). Every save, delete, undo, link and filing completion
//: called `loadEntries()`, which pages through the whole notebook: measured at
//: 5,010 notes, 27 sequential requests, 5.3 MB of JSON and up to 1.1 s of
//: long tasks, per save. This asks for just these ids (`GET /entries?ids=`,
//: one request) and patches them into `allEntries`: a note the answer leaves
//: out has left the list (binned, archived, turned into a board), one it
//: carries is replaced or added, and the list is put back in the server's
//: order (pinned first, then newest). The answer's `X-Total-Count` is the
//: whole list's size, so a patched list that disagrees with it (something
//: else changed meanwhile) falls back to the full read. So does anything
//: this cannot patch: a load still paging in, a semantic search's result
//: list, more ids than one read takes. `loadEntries()` stays for unlock, the
//: refresh button, a space switch and every change whose notes are unknown.
const REFRESH_ENTRIES_MAX = 200; // `ENTRIES_BY_IDS_MAX` in routes_entries.py
let entriesComplete = false;

function entryListOrder(a, b) {
  if (Boolean(a.pinned) !== Boolean(b.pinned)) return a.pinned ? -1 : 1;
  const ac = String(a.created_at || "");
  const bc = String(b.created_at || "");
  if (ac !== bc) return ac < bc ? 1 : -1;
  return b.id - a.id;
}

async function refreshEntries(ids) {
  const wanted = [...new Set((ids || []).map(Number).filter((id) => Number.isInteger(id) && id > 0))];
  //: The sidebar's Most used follows a write at once (OPEN: "keeps a binned
  //: note for up to 30 s"): the write emptied the read cache, so this is one
  //: fresh GET, not the 30 s copy.
  if (typeof loadMostUsed === "function") loadMostUsed().catch(() => {});
  const semantic = $("semantic-search-toggle")?.checked && noteSearch;
  if (!wanted.length || wanted.length > REFRESH_ENTRIES_MAX || !entriesComplete || semantic) {
    return loadEntries();
  }
  const generation = _entriesLoadGeneration;
  let rows;
  let total;
  try {
    const response = await api(`/entries?ids=${wanted.join(",")}`);
    rows = await response.json();
    total = Number(response.headers.get("X-Total-Count"));
  } catch {
    return loadEntries(); // which says what went wrong, where the list is
  }
  if (generation !== _entriesLoadGeneration || !entriesComplete) return; // a full read took over
  const touched = new Set(wanted);
  const next = allEntries.filter((entry) => !touched.has(entry.id));
  next.push(...rows);
  next.sort(entryListOrder);
  if (Number.isFinite(total) && total !== next.length) return loadEntries();
  allEntries = next;
  publishNotes(allEntries);
  for (const id of wanted) {
    referenceCountsCache.delete(id);
    reminderCountsCache.delete(id);
  }
  //: The side rail keys its answer on the load generation, which a patch does
  //: not move: dropped so a changed link shows on the next paint.
  notesRailCache.clear();
  const railBody = $("notes-rail-body");
  if (railBody) delete railBody.dataset.key;
  ensureMapChipsFor(rows, generation);
  renderStatusBar();
  renderSidebar();
  renderEntries();
  //: Categories the AI filed into since the last read need their ids.
  loadCategories();
  fillCategoryOptions($("entry-category"), null);
}

//: **A change made on another device shows here** (INBOX 881, the owner
//: 2026-10-11: "what if I make a change on my phone?? does it live
//: update??"). Every `NOTE_CHANGES_MS` while the page is visible, and at once
//: when it comes back (the phone's browser brought forward), the list asks
//: `GET /entries/changes` which notes moved since its last answer and
//: patches those in with `refreshEntries`. The note being edited is left
//: alone: its Save sends `base_hash`, so a newer text from elsewhere still
//: gets the Keep mine / Take theirs prompt rather than being overwritten
//: under the person's cursor. `seen` drops an id already refreshed at the
//: same `updated_at` (the server's stamp overlaps by two seconds).
const NOTE_CHANGES_MS = 15_000;
const noteChanges = { since: "", seen: new Map(), timer: 0, busy: false, quiet: 0 };
async function followNoteChanges() {
  clearTimeout(noteChanges.timer);
  if (document.hidden) return;
  noteChanges.timer = setTimeout(followNoteChanges, noteChanges.since ? NOTE_CHANGES_MS * (noteChanges.quiet >= 4 ? 2 : 1) : 2000);
  //: The first stamp is taken as soon as there is a session, before the list
  //: has finished loading, so a change made while it loads is not missed.
  if (noteChanges.busy || !authToken() || (noteChanges.since && !entriesComplete)) return;
  noteChanges.busy = true;
  try {
    const body = await apiJson(`/entries/changes?since=${encodeURIComponent(noteChanges.since)}`, { silent: true });
    const first = !noteChanges.since;
    noteChanges.since = body.since;
    if (first) return;
    //: More than one answer holds: an empty patch is `refreshEntries`'s full read.
    if (body.more) return void refreshEntries([]);
    const ids = body.ids.filter((id) => id !== editingId && noteChanges.seen.get(id) !== body.stamps[id]);
    if (noteChanges.seen.size > 500) noteChanges.seen.clear();
    for (const id of body.ids) noteChanges.seen.set(id, body.stamps[id]);
    //: Battery: four empty answers in a row slow the ask to 30 s; a change or a return to the tab restores 15 s.
    noteChanges.quiet = body.ids.length ? 0 : noteChanges.quiet + 1;
    if (!ids.length) return;
    await refreshEntries(ids);
    if (typeof refreshNotePage === "function") refreshNotePage(ids);
  } catch {
    /* offline or locked: the next tick asks again */
  } finally {
    noteChanges.busy = false;
  }
}
document.addEventListener("visibilitychange", () => {
  noteChanges.quiet = 0;
  followNoteChanges();
});
followNoteChanges();

//: **What the note list needs to draw a `[[map]]` as a map chip**, fetched
//: once and only for a notebook that has one.
//:
//: `renderNoteInline` is synchronous and runs once per wiki link, so it cannot
//: fetch; the index has to be in memory before the render. It used to be
//: filled unconditionally at the top of `loadEntries`, which meant
//: `GET /whiteboard/boards?limit=200` on every cold start, 204 ms measured,
//: for a notebook that may contain no `[[` at all (WORLD_CLASS_PLAN A2). Now
//: the page that has just arrived is asked first, so a notebook with no wiki
//: links never asks for boards and one that has them asks once.
//:
//: The re-render is the half the old placement never had: fired and not
//: awaited, the index always landed *after* the render it was for, and the
//: chips stayed plain text until something else redrew the list. Guarded on
//: the load generation, because a newer `loadEntries` may have taken over
//: while this was in flight and its list is the one on screen.
//: **"In 2 documents · on 1 board · linked by 3 notes", on the card.**
//: INBOX 246's third gap: a card showed nothing until Connections was opened,
//: so a note on two boards and in three documents looked exactly like a
//: note nothing had ever touched. One muted chip on the card, opening
//: Connections, from one batched call per page (`/entries/reference-counts
//: ?ids=`): fifty cards asking `/references` each would be fifty scans per
//: render. Cleared with every reload (`_loadEntries`), which is also what
//: both attach panels call after a write, so a fresh attachment shows on
//: the next paint without a second cache to keep honest.
const referenceCountsCache = new Map();
const _referenceCountsInFlight = new Set();
const REFERENCE_COUNTS_BATCH = 60; // `REFERENCE_COUNT_IDS_MAX` in routes_entries.py
const REFERENCE_COUNT_PHRASES = [
  ["document", "in", "document", "documents"],
  ["board", "on", "board", "boards"],
  ["map", "on", "map", "maps"],
  ["note", "linked by", "note", "notes"],
];

function referenceCountText(counts) {
  const parts = [];
  for (const [kind, verb, one, many] of REFERENCE_COUNT_PHRASES) {
    const n = counts[kind] || 0;
    if (n) parts.push(`${verb} ${n} ${n === 1 ? one : many}`);
  }
  if (!parts.length) return "";
  // Read out loud as one line, sentence case on the first word only.
  const line = parts.join(" · ");
  return line[0].toUpperCase() + line.slice(1);
}

function referenceCountChip(entry, options = {}) {
  //: `facts` as well as `actions` (INBOX 297): what a note is joined to is
  //: true of the note wherever it is drawn, and this chip is DESIGN.md's
  //: "a fact on a facts line that is also the way in" rather than an action.
  if ((!options.actions && !options.facts) || entry.is_board || entry.is_draft) return null;
  const counts = referenceCountsCache.get(entry.id);
  if (!counts || !counts.total) return null;
  const refChip = chip(`ph:graph ${referenceCountText(counts)}`, "refs", (event) => {
    event.stopPropagation();
    lazyScript("/js/connections.js").then(() => openConnections(
      "entries",
      entry.id,
      entry.title || noteNamePlain(entry.content, 80)
    ));
  });
  refChip.title = "Everything this note is joined to. Open Connections";
  return refChip;
}

//: Called from the list's `afterChunk`, so it sees exactly the cards that
//: are in the DOM and asks for the ones the cache has not met. Cards are
//: patched in place rather than re-rendered: a re-render mid-chunking would
//: restart the incremental renderer that called this.
//: **What this note made you promise to do** (INBOX 309, the owner: "or to
//: link reminders to notes").
//:
//: The link itself was never missing: `Reminder.entry_id` has existed since
//: reminders did, the note card's own "Remind me" passes it, and the
//: `set_reminder` tool takes a `note_id`. One end of it was drawn and the
//: other was not: a reminder says which note it came from, and a note that
//: caused three reminders looked exactly like a note that caused none. So
//: this is the same answer INBOX 246 gave for boards and documents: one
//: muted chip on the card, from one batched count per page.
//:
//: **A chip on the facts line, not a section under the note.** The card is
//: already a title, a body and one line of facts about it, and a second
//: block under every note with a reminder would push the next note off the
//: screen for a fact that is usually one word long. It presses open the same
//: `.entry-links` row "Referenced by" and "Similar notes" use, which is also
//: what keeps it to one open panel per card.
const reminderCountsCache = new Map();
const _reminderCountsInFlight = new Set();

function reminderCountChip(entry, options = {}) {
  if ((!options.actions && !options.facts) || entry.is_board || entry.is_draft) return null;
  const count = reminderCountsCache.get(entry.id) || 0;
  if (!count) return null;
  const alarm = chip(`ph:alarm ${nounCount(count, "reminder")}`, "reminders", (event) => {
    event.stopPropagation();
    toggleNoteReminders(entry);
  });
  alarm.title = "What this note made you promise to do. Press to see them";
  return alarm;
}

//: **A note's topic, on its card** (the owner, 2026-10-10: "Should topics
//: from the graph be more integrated app wide??"). A topic is found by the
//: graph (`/graph/topics/of`, renames applied); the chip says which one this
//: note is in and opens the graph on it. Quiet like the counts: a fact about
//: the note, not a warning. A rename clears the cache (`gcSaveTopicName`).
const noteTopicsCache = new Map();
const _noteTopicsInFlight = new Set();

//: A topic the graph named after a tag repeats the tag chip already on the
//: card, so it is left off there; case, a leading # and separators do not count.
function topicRepeatsTag(name, tags) {
  const key = (text) => String(text || "").toLowerCase().replace(/^#/, "").replace(/[\s_-]+/g, " ").trim();
  const topic = key(name);
  return Boolean(topic) && (tags || []).some((tag) => key(tag) === topic);
}

function noteTopicChip(entry) {
  const topic = noteTopicsCache.get(entry.id);
  if (!topic || entry.is_board || entry.is_draft) return null;
  if (topicRepeatsTag(topic.name, entry.tags)) return null;
  const mark = chip(`ph:circles-three ${topic.name}`, "refs topic", async (event) => {
    event.stopPropagation();
    await switchTab("graph");
    showTopicInGraph(entry.id);
  });
  mark.title = `In the topic ${topic.name}, ${nounCount(topic.size, "note")}. Open it on the graph`;
  return mark;
}

//: **The count strips a card carries, as data.**
//:
//: They are the same mechanism twice over: read the ids on screen, ask once
//: for all of them, patch the chip onto the cards that are still there. The
//: reference counts had it first and the reminders would have been a second
//: copy of it, which is how the two would come to disagree about batching,
//: about a note deleted mid-flight, or about which generation of the list
//: they belong to. One walker, one table of what differs.
const CARD_COUNT_SOURCES = [
  {
    cache: referenceCountsCache,
    inFlight: _referenceCountsInFlight,
    path: (ids) => `/entries/reference-counts?ids=${ids}`,
    marker: ".chip.refs",
    //: A note the server did not answer for (deleted under us) is recorded
    //: as empty, not left unknown, or it would be asked for again on every
    //: chunk.
    empty: { total: 0 },
    chip: (entry) => referenceCountChip(entry, { actions: true }),
  },
  {
    cache: reminderCountsCache,
    inFlight: _reminderCountsInFlight,
    path: (ids) => `/reminders/counts?ids=${ids}`,
    marker: ".chip.reminders",
    empty: 0,
    chip: (entry) => reminderCountChip(entry, { actions: true }),
  },
  {
    cache: noteTopicsCache,
    inFlight: _noteTopicsInFlight,
    path: (ids) => `/graph/topics/of?ids=${ids}`,
    key: "topics",
    marker: ".chip.topic",
    empty: null,
    chip: noteTopicChip,
  },
  //: **A note's own open questions** (INBOX 745 (c): "there is no way to view
  //: the questions asked by notes ... from the notes themselves"): a count
  //: that opens Notes, Questions kept to this note.
  {
    cache: new Map(),
    inFlight: new Set(),
    path: (ids) => `/questions/counts?ids=${ids}`,
    marker: ".chip.questions",
    empty: 0,
    chip(entry) {
      const count = this.cache.get(entry.id);
      return count ? chip(`ph:question ${count} open question${count === 1 ? "" : "s"}`, "questions", (event) => {
        event.stopPropagation();
        showNotesSection("questions");
        ensureModule("questionsView").then(() => questionsForNote(entry.id));
      }) : null;
    },
  },
];

function ensureCardCounts(list, generation) {
  for (const source of CARD_COUNT_SOURCES) ensureOneCardCount(list, generation, source);
}

function ensureOneCardCount(list, generation, source) {
  const wanted = [];
  for (const li of list.querySelectorAll("li[data-id]:not(.row-shell)")) {
    const id = Number(li.dataset.id);
    if (!id || source.cache.has(id) || source.inFlight.has(id)) continue;
    wanted.push(id);
    if (wanted.length >= REFERENCE_COUNTS_BATCH) break;
  }
  if (!wanted.length) return;
  for (const id of wanted) source.inFlight.add(id);
  apiJson(source.path(wanted.join(",")), { silent: true })
    .then((answer) => {
      if (generation !== _entriesLoadGeneration) return;
      const counts = (answer && answer[source.key || "counts"]) || {};
      for (const id of wanted) {
        const given = counts[String(id)];
        source.cache.set(id, given === undefined || given === null ? source.empty : given);
      }
      //: Every chip in, then one fit: a fit reads widths (INBOX 1446).
      const fitted = [];
      for (const id of wanted) {
        const li = list.querySelector(`li[data-id="${id}"]`);
        const meta = li && li.querySelector(":scope > .entry-meta");
        if (!meta || meta.querySelector(source.marker)) continue;
        const entry = allEntries.find((e) => e.id === id);
        const built = entry && source.chip(entry);
        if (!built) continue;
        meta.insertBefore(built, meta.querySelector(":scope > .entry-date, :scope > .entry-meta-end"));
        fitted.push(meta);
      }
      fitNoteMetas(fitted);
      // The page may hold more than one batch; the next call finds the rest.
      if (list.querySelectorAll("li[data-id]:not(.row-shell)").length > wanted.length) {
        ensureOneCardCount(list, generation, source);
      }
    })
    .catch(() => {})
    .finally(() => {
      for (const id of wanted) source.inFlight.delete(id);
    });
}

function ensureMapChipsFor(page, generation) {
  if (mapBoardIndexCache) return; // one index per session, as it always was
  if (!page.some((entry) => String(entry.content || "").includes("[["))) return;
  loadMapBoardIndex()
    .then(() => {
      if (generation === _entriesLoadGeneration) renderEntries();
    })
    .catch(() => {});
}

// --- the connections rail (WORLD_CLASS_PLAN D2) --------------------------------
//: **What the open note is joined to, beside it, on a desktop.** The same
//: answer the card menu's Connections sheet gives (`openConnections`,
//: menus.js, which draws with the same `buildConnectionGroups`), kept in a
//: column that stays while you read, plus the one ranking that had nowhere to
//: be read beside a note: the forgotten notes close to it
//: (`GET /resurface/near`, INBOX 261).
//:
//: **When it is on screen.** Four things, all of them:
//:   - the window is at least NOTES_RAIL_MIN_WIDTH wide. Measured before it
//:     was built (1440x900, the default sidebar): the list's column is 1132px
//:     at 1440, 974 at 1280 and 795 at 1024, so a rail of about 17rem leaves
//:     the reading column above 600px from 1280 up and would take it to about
//:     500 at 1024. Below the number the note's own Connections sheet is the
//:     way in, as it has always been, and the stylesheet takes the column away
//:     at the same width so no frame drawn before this runs can show it;
//:   - the Notes tab is showing its list (Browse): the other three sections
//:     have no note open;
//:   - a note is open or selected: the one being edited, the row expanded
//:     last, the note a link or a search jumped to (`flashEntry`, which is
//:     what `lastOpenedEntryId` records), or the row the keyboard or a click
//:     is on (focus inside the list). Whichever of those happened last;
//:   - it has not been hidden. Hiding is remembered (NOTES_RAIL_KEY), because
//:     a column somebody has closed is a preference, and the More menu brings
//:     it back.
const NOTES_RAIL_MIN_WIDTH = 1280;
//: The narrowest the list may be with the rail beside it (WORLD_CLASS_PLAN
//: D2's gate: "the reading column keeps at least 600px").
const NOTES_RAIL_MIN_READING = 600;
const NOTES_RAIL_KEY = "notes-rail";
const notesRailWide = window.matchMedia(`(min-width: ${NOTES_RAIL_MIN_WIDTH}px)`);
let notesRailId = null;
let notesRailSeenEditing = null;
let notesRailSeenOpened = null;
let notesRailTimer = 0;
let notesRailSeq = 0;
//: Answers kept per note and per load of the notebook, so walking the list
//: with the arrow keys and back again asks the server once per note, and a
//: save (which bumps the generation) is never answered from before it.
const notesRailCache = new Map();

function notesRailHiddenByChoice() {
  try {
    return prefs.get(NOTES_RAIL_KEY, null) === "off";
  } catch {
    return false;
  }
}

//: Called at the top of every list render: an edit that has just begun and a
//: jump that has just landed are both things the render is the first to know
//: about, and neither has a hook of its own in this file.
function notesRailSync() {
  if (editingId != null && editingId !== notesRailSeenEditing) notesRailId = editingId;
  notesRailSeenEditing = editingId;
  const opened = typeof lastOpenedEntryId === "number" ? lastOpenedEntryId : null;
  if (opened != null && opened !== notesRailSeenOpened) notesRailId = opened;
  notesRailSeenOpened = opened;
  scheduleNotesRail();
}

//: A short wait, not a frame: arrow keys walk the list a row a keypress, and
//: the column should follow where the walk stops rather than fetch every row
//: it passes.
function scheduleNotesRail() {
  clearTimeout(notesRailTimer);
  notesRailTimer = setTimeout(renderNotesRail, 120);
}

function notesRailWanted() {
  if (!notesRailWide.matches || notesRailHiddenByChoice()) return null;
  if ((prefs.get("activeTab", null) || "dashboard") !== "notes") return null;
  if ($("browse")?.classList.contains("hidden")) return null;
  if (notesRailId == null) return null;
  return allEntries.find((entry) => entry.id === notesRailId && !entry.is_draft) || null;
}

function syncNotesRailToggle() {
  const toggle = $("notes-rail-toggle");
  if (!toggle) return;
  toggle.classList.toggle("hidden", !notesRailWide.matches);
  //: A setting, said as one (INBOX 432): "Hide connections" read as an
  //: action on a column that was not there when no note was open.
  const on = !notesRailHiddenByChoice();
  setLabel(toggle, `${on ? "ph:check-square" : "ph:square"} Connections beside the note you're reading`);
  toggle.setAttribute("aria-pressed", String(on));
}

async function renderNotesRail() {
  const rail = $("notes-rail");
  if (!rail) return;
  syncNotesRailToggle();
  //: INBOX 571: the rail follows the note in view (notes-rail-spy.js).
  if (notesRailWide.matches) ensureModule("notesRail");
  const mark = typeof notesRailMark === "function" ? notesRailMark : () => {};
  const entry = notesRailWanted();
  if (!entry) {
    if (rail.contains(document.activeElement)) notesRailFocusSubject();
    rail.hidden = true;
    mark(null);
    return;
  }
  rail.hidden = false;
  //: **The reading column comes first.** The rail's width is set against the
  //: default sidebar; a sidebar dragged to its widest (24% of the window,
  //: `applySidebarWidth`) left the list 573px at 1280 with the rail beside
  //: it (`notesrail.js` with SIDEBAR=wide). So the rail measures the list
  //: once it is in, in the same task and so before anything is painted, and
  //: gives way to the note's Connections sheet when the list would be
  //: narrower than NOTES_RAIL_MIN_READING, exactly as it does below 1280.
  const list = $("entry-list");
  if (list && list.getBoundingClientRect().width < NOTES_RAIL_MIN_READING) {
    rail.hidden = true;
    rail.dataset.cramped = "1";
    mark(null);
    return;
  }
  delete rail.dataset.cramped;
  const subject = $("notes-rail-subject");
  subject.textContent = entry.is_private ? "Private note" : entry.title || notePreviewText(entry.content);
  subject.title = subject.textContent;
  mark(entry);
  const body = $("notes-rail-body");
  const key = `${entry.id}:${_entriesLoadGeneration}`;
  if (body.dataset.key === key) return;
  const seq = ++notesRailSeq;
  body.setAttribute("aria-busy", "true");
  //: The rows are drawn by connections.js (the sheet's own bundle).
  await lazyScript("/js/connections.js");
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

//: Back to the note the column is about, in the list: where Escape and hiding
//: the column put the keyboard, so focus is never left on something that has
//: just gone.
function notesRailFocusSubject() {
  const li = document.querySelector(`#entry-list li[data-id="${notesRailId}"]`);
  if (li) li.focus({ preventScroll: true });
}

//: The Connections sheet's "Open in the sidebar" (INBOX 784): the column
//: shown for that note, from wherever the sheet was opened.
function dockConnectionsInRail(id) {
  if ((prefs.get("activeTab", null) || "dashboard") !== "notes") switchTab("notes");
  notesRailId = id;
  setNotesRailHidden(false);
}

function setNotesRailHidden(hidden) {
  try {
    prefs.set(NOTES_RAIL_KEY, hidden ? "off" : "on");
  } catch {
    /* private mode: the choice lasts this visit */
  }
  renderNotesRail();
}

(function wireNotesRail() {
  const rail = $("notes-rail");
  const list = $("entry-list");
  if (!rail || !list) return;
  //: Selecting a row is focusing it: a click on a card's body focuses its
  //: `<li>` (the list's roving tabindex), and so does every arrow key.
  list.addEventListener("focusin", (event) => {
    const li = event.target.closest?.("li[data-id]");
    if (!li || li.parentElement !== list) return;
    //: **Not a card's menu.** Its ⋯ is a button inside the row, so pressing it
    //: is focus in the row, and the rail opened 120ms later: the column takes
    //: 318px from the list and its dock wraps to two lines, so the row moved
    //: 318px left and 44px down under a menu already placed beside where the
    //: ⋯ had been (the review, 2026-09-27, `anchorsmotion.js`: 118px from its
    //: opener at 1440x600, over the rail). A menu acts on a note; it does not
    //: choose one to read.
    if (event.target.closest?.(".menu-wrap, .action-menu")) return;
    //: INBOX 571: a card chosen by hand is the subject (it is pinned in
    //: notes-rail-spy.js); the rail is already drawn, so nothing moves.
    const id = Number(li.dataset.id);
    if (!Number.isFinite(id) || id === notesRailId) return;
    notesRailId = id;
    scheduleNotesRail();
  });
  $("notes-rail-close")?.addEventListener("click", () => {
    notesRailFocusSubject();
    setNotesRailHidden(true);
    toast("Connections hidden. The notes list's More menu brings them back.");
  });
  $("notes-rail-toggle")?.addEventListener("click", () => {
    setNotesRailHidden(!notesRailHiddenByChoice());
    $("notes-more-menu")?.removeAttribute("open");
  });
  //: The keys every list here keeps (WORLD_CLASS_PLAN 1.6): arrows walk the
  //: rows, Enter opens one (they are buttons), Escape goes back to the list.
  rail.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      notesRailFocusSubject();
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const rows = [...rail.querySelectorAll("button.connection-row")];
    const at = rows.indexOf(document.activeElement);
    if (at < 0) return;
    event.preventDefault();
    const next = rows[Math.min(rows.length - 1, Math.max(0, at + (event.key === "ArrowDown" ? 1 : -1)))];
    next?.focus();
  });
  notesRailWide.addEventListener("change", renderNotesRail);
  //: A sidebar dragged wider or narrower, or collapsed, changes the room the
  //: list has, which is what decides whether the rail fits. Observed on the
  //: sidebar itself rather than on the window, because the window does not
  //: change when the sidebar is dragged.
  if (typeof ResizeObserver === "function" && $("sidebar")) {
    let last = 0;
    new ResizeObserver((entries) => {
      const w = Math.round(entries[0].contentRect.width);
      if (w === last) return;
      last = w;
      scheduleNotesRail();
    }).observe($("sidebar"));
  }
  syncNotesRailToggle();
})();

//: GRAPH_PLAN 518: a save that renamed a note while other notes still write
//: its old [[name]] offers to rewrite them as the new one.
function offerWikiRename(entryId, saved) {
  const offer = saved && saved.wiki_rename;
  if (!offer) return;
  const who = offer.notes === 1 ? "1 note still links" : `${offer.notes} notes still link`;
  toastAction(`${who} to [[${offer.old}]].`, `Rename to [[${offer.new}]]`, async () => {
    try {
      const done = await apiJson(`/entries/${entryId}/wiki-rename`, { method: "POST", body: JSON.stringify({ old: offer.old }) });
      pushWikiRenameUndo(entryId, offer.old, done);
      toast(`Updated ${nounCount(done.rewritten, "note")}.`);
      await loadEntries().catch(() => {});
    } catch (error) {
      toast(error.message || "Couldn't update those links.", true);
    }
  });
}
